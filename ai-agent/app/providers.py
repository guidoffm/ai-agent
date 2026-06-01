from abc import ABC, abstractmethod
from typing import Optional

import requests


class Provider(ABC):
    name: str

    @abstractmethod
    def complete(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        ...


class OpenAIProvider(Provider):
    name = "openai"
    URL = "https://api.openai.com/v1/chat/completions"
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self, api_key: str, model: Optional[str]):
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL

    def complete(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = requests.post(
            self.URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


class ClaudeProvider(Provider):
    name = "claude"
    URL = "https://api.anthropic.com/v1/messages"
    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str, model: Optional[str]):
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL

    def complete(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        resp = requests.post(
            self.URL,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        parts = resp.json().get("content", [])
        return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


class GeminiProvider(Provider):
    name = "gemini"
    URL_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: Optional[str]):
        self.api_key = api_key
        self.model = model or self.DEFAULT_MODEL

    def complete(self, prompt: str, system: Optional[str], max_tokens: int) -> str:
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        resp = requests.post(
            self.URL_TMPL.format(model=self.model),
            params={"key": self.api_key},
            json=body,
            timeout=60,
        )
        resp.raise_for_status()
        candidates = resp.json().get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)


_REGISTRY = {
    "openai": OpenAIProvider,
    "chatgpt": OpenAIProvider,
    "claude": ClaudeProvider,
    "anthropic": ClaudeProvider,
    "gemini": GeminiProvider,
    "google": GeminiProvider,
}


def make_provider(name: str, api_key: str, model: Optional[str]) -> Provider:
    key = (name or "").strip().lower()
    cls = _REGISTRY.get(key)
    if cls is None:
        raise ValueError(f"unknown provider: {name!r} (expected one of {sorted(set(_REGISTRY))})")
    return cls(api_key, model)
