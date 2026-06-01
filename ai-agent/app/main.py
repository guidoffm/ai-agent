import json
import logging
import os
import re
import signal
import sys
from datetime import datetime, timezone

import requests
from apscheduler.schedulers.blocking import BlockingScheduler

from providers import make_provider

OPTIONS_PATH = "/data/options.json"
HA_API = "http://supervisor/core/api"

with open(OPTIONS_PATH) as f:
    options = json.load(f)

LOG_LEVEL = options.get("log_level", "info").upper()
INTERVAL_SECONDS = int(options.get("interval_seconds", 300))
PROVIDER = (options.get("provider") or "claude").strip()
API_KEY = (options.get("api_key") or "").strip()
MODEL = (options.get("model") or "").strip() or None
MAX_TOKENS = int(options.get("max_tokens", 1024))
SYSTEM_PROMPT = options.get("system_prompt") or ""
PROMPT = options.get("prompt") or ""
RESULT_ENTITY = (options.get("result_entity") or "").strip()
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("ai-agent")

ENTITY_PATTERN = re.compile(r"\{\{\s*([a-z_]+\.[a-zA-Z0-9_]+)\s*\}\}")


def read_state(entity_id: str) -> str:
    resp = requests.get(
        f"{HA_API}/states/{entity_id}",
        headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["state"]


def render(template: str) -> str:
    def sub(match: re.Match) -> str:
        entity_id = match.group(1)
        try:
            return read_state(entity_id)
        except (requests.RequestException, KeyError) as exc:
            log.warning("entity %s lookup failed: %s", entity_id, exc)
            return f"<unavailable:{entity_id}>"

    return ENTITY_PATTERN.sub(sub, template)


def push_result(text: str) -> None:
    if not RESULT_ENTITY:
        return
    resp = requests.post(
        f"{HA_API}/states/{RESULT_ENTITY}",
        headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
        json={
            "state": text[:255],
            "attributes": {
                "full_response": text,
                "provider": PROVIDER,
                "model": MODEL or "default",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        },
        timeout=10,
    )
    resp.raise_for_status()


def tick() -> None:
    if not SUPERVISOR_TOKEN:
        log.warning("no SUPERVISOR_TOKEN — cannot query HA")
        return
    if not API_KEY:
        log.warning("no api_key configured — skipping query")
        return
    if not PROMPT:
        log.warning("no prompt configured — skipping query")
        return

    rendered_prompt = render(PROMPT)
    rendered_system = render(SYSTEM_PROMPT) if SYSTEM_PROMPT else None

    try:
        provider = make_provider(PROVIDER, API_KEY, MODEL)
        answer = provider.complete(rendered_prompt, rendered_system, MAX_TOKENS)
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        log.warning("AI query failed: %s", exc)
        return

    log.info("AI %s answered (%d chars)", PROVIDER, len(answer))
    log.debug("response: %s", answer)

    try:
        push_result(answer)
    except requests.RequestException as exc:
        log.warning("pushing result to %s failed: %s", RESULT_ENTITY, exc)


def main() -> None:
    log.info(
        "config: provider=%s model=%s interval=%ds result_entity=%s",
        PROVIDER,
        MODEL or "default",
        INTERVAL_SECONDS,
        RESULT_ENTITY or "<none>",
    )

    scheduler = BlockingScheduler(timezone=os.environ.get("TZ", "UTC"))
    scheduler.add_job(
        tick,
        "interval",
        seconds=INTERVAL_SECONDS,
        next_run_time=datetime.now(),
        id="tick",
    )

    def shutdown(signum, _frame):
        log.info("received signal %s — shutting down", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info("scheduler starting (interval=%ds)", INTERVAL_SECONDS)
    scheduler.start()


if __name__ == "__main__":
    main()
