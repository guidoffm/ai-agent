# AI Agent — Home Assistant Add-on

A Home Assistant add-on that periodically queries an AI provider (Gemini,
Claude, or ChatGPT) with a configurable prompt and writes the response back
into Home Assistant as a sensor state. Entity references in the prompt are
substituted with the current state before the call.

## Installation

In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**,
then add:

```
https://github.com/guidoffm/ai-agent
```

The "AI Agent" add-on will appear in the store. Install it, configure your
API key and prompt (see below), then start it.

## Configuration

| Option | Default | Description |
| --- | --- | --- |
| `provider` | `claude` | One of `gemini`, `claude`, `openai`, `openrouter`. |
| `api_key` | _(required)_ | API key for the selected provider. |
| `model` | _(provider default)_ | Override model. Defaults: Claude `claude-sonnet-4-6`, Gemini `gemini-2.5-flash`, OpenAI `gpt-4o-mini`, OpenRouter `anthropic/claude-sonnet-4-6`. |
| `max_tokens` | `1024` | Maximum tokens in the response. |
| `interval_seconds` | `300` | How often to run the query. |
| `system_prompt` | `""` | Optional system instruction. Supports entity substitution. |
| `prompt` | _(required)_ | The user prompt. Supports entity substitution. |
| `result_entity` | `sensor.ai_agent_result` | HA entity to write the response into. Leave empty to disable. |
| `log_level` | `info` | `trace`, `debug`, `info`, `notice`, `warning`, `error`, `fatal`. |

### Entity substitution

Any `{{domain.entity_id}}` placeholder in `prompt` or `system_prompt` is
replaced with the current state of that entity before the call. Example:

```yaml
prompt: |
  The outside temperature is {{sensor.outside_temperature}} °C and the
  forecast says {{sensor.weather_forecast}}. Should I open the windows?
```

If an entity cannot be read, it is replaced with `<unavailable:entity_id>`
and the call still proceeds.

### Response storage

When `result_entity` is set, the add-on writes a state to that entity:

- `state`: the first 255 characters of the response (HA's state limit)
- `attributes.full_response`: the complete response
- `attributes.provider`, `attributes.model`, `attributes.updated_at`

You can then reference the result in automations, templates, or dashboards.

## Providers

All providers are called via plain HTTPS — no vendor SDKs. See
[`ai-agent/app/providers.py`](ai-agent/app/providers.py).

| Provider | Default model | Endpoint |
| --- | --- | --- |
| `claude` | `claude-sonnet-4-6` | `api.anthropic.com/v1/messages` |
| `gemini` | `gemini-2.5-flash` | `generativelanguage.googleapis.com` |
| `openai` | `gpt-4o-mini` | `api.openai.com/v1/chat/completions` |
| `openrouter` | `anthropic/claude-sonnet-4-6` | `openrouter.ai/api/v1/chat/completions` |

`openrouter` routes through [OpenRouter](https://openrouter.ai), which lets you
reach many models behind a single API key. Use OpenRouter's `vendor/model`
identifiers (e.g. `google/gemini-2.5-flash`, `openai/gpt-4o-mini`) in `model`.

## License

MIT — see source.
