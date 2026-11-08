"""Codex lifecycle hooks: anonymous, transactional local counters.

Never save prompts, tool arguments, raw session IDs, error text, or transcripts.
Tokens are request-level observations, not an account quota percentage.
"""

from __future__ import annotations

import json
import sys

from . import settings, storage

PROMPT_THRESHOLDS = (40, 80, 150)
TOOL_THRESHOLDS = (100, 250, 500)
MAX_STDIN_BYTES = 2_000_000

# Retained public helper for compatibility with v0.1 tests/scripts.
state_path = storage.state_path


def process(payload: dict) -> dict | None:
    event = payload.get("hook_event_name")
    if event not in ("UserPromptSubmit", "PostToolUse", "PostModelRequest"):
        return None
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id or len(session_id) > 512:
        return None
    try:
        config = settings.load(prompts=PROMPT_THRESHOLDS, tools=TOOL_THRESHOLDS)
    except ValueError:
        # Bad optional config cannot prevent Codex from continuing.
        config = settings.defaults(PROMPT_THRESHOLDS, TOOL_THRESHOLDS)

    def update(state: dict) -> str | None:
        if event == "PostModelRequest":
            state["model_requests"] = storage.safe_add(state.get("model_requests"), 1)
            status = payload.get("status")
            if status in storage.STATUSES:
                statuses = state["model_status"]
                statuses[status] = storage.safe_add(statuses.get(status), 1)
            usage = payload.get("token_usage")
            if isinstance(usage, dict):
                observed = False
                for field in storage.TOKENS:
                    value = usage.get(field)
                    if type(value) is int and 0 <= value <= storage.MAX_EVENT_TOKENS:
                        state["model_tokens"][field] = storage.safe_add(
                            state["model_tokens"].get(field), value
                        )
                        observed = True
                if observed:
                    state["token_usage_reports"] = storage.safe_add(
                        state.get("token_usage_reports"), 1
                    )
            return None

        key = "prompts" if event == "UserPromptSubmit" else "tools"
        count = storage.safe_add(state.get(key), 1)
        state[key] = count
        if not config["warnings_enabled"]:
            return None
        announced = state["announced"]
        reached = [
            value for value in config["alerts"][key]
            if count >= value and f"{key}-{value}" not in announced
        ]
        announced.extend(f"{key}-{value}" for value in reached)
        if not reached:
            return None
        return (
            f"Codex Quota Keeper: {count} {key} in this session (event counts, not token or quota data). "
            "At the next safe milestone, consider verifying progress, updating HANDOFF.md "
            "and starting a fresh session if the context is large. Do not skip tests."
        )

    warning = storage.transact(session_id, update)
    if warning is None:
        return None
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": warning}}


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
        if len(raw) > MAX_STDIN_BYTES:
            return 0
        payload = json.loads(raw)
        if isinstance(payload, dict):
            output = process(payload)
            if output is not None:
                print(json.dumps(output))
    except Exception:
        # Advisory only: never block Codex on optional telemetry failures.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
