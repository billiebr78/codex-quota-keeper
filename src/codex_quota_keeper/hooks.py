"""Privacy-minimal Codex lifecycle hooks and advisory session milestones."""

from __future__ import annotations

import json
import sys

from . import state

PROMPT_THRESHOLDS = (40, 80, 150)
TOOL_THRESHOLDS = (100, 250, 500)
MAX_STDIN_BYTES = 2_000_000
state_path = state.state_path


def process(payload: dict) -> dict | None:
    event = payload.get("hook_event_name")
    if event not in ("UserPromptSubmit", "PostToolUse", "PostModelRequest"):
        return None
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id or len(session_id) > 512:
        return None

    def mutate(values: dict) -> str | None:
        if event == "PostModelRequest":
            values["model_requests"] = state.add(values.get("model_requests"), 1)
            status = payload.get("status")
            if status in state.STATUS_KEYS:
                counters = values["model_status"]
                counters[status] = state.add(counters.get(status), 1)
            usage = payload.get("token_usage")
            if isinstance(usage, dict):
                reported = False
                for field in state.TOKEN_KEYS:
                    value = usage.get(field)
                    if type(value) is int and 0 <= value <= state.MAX_EVENT_TOKENS:
                        tokens = values["model_tokens"]
                        tokens[field] = state.add(tokens.get(field), value)
                        reported = True
                if reported:
                    values["token_usage_reports"] = state.add(
                        values.get("token_usage_reports"), 1
                    )
            return None

        key = "prompts" if event == "UserPromptSubmit" else "tools"
        values[key] = state.add(values.get(key), 1)
        limits = PROMPT_THRESHOLDS if key == "prompts" else TOOL_THRESHOLDS
        announced = values["announced"]
        newly_reached = [
            n for n in limits
            if values[key] >= n and f"{key}-{n}" not in announced
        ]
        announced.extend(f"{key}-{n}" for n in newly_reached)
        if not newly_reached:
            return None
        return (
            f"Codex Quota Keeper: {values[key]} {key} observed (not remaining quota). "
            "At a safe checkpoint, consider reducing repeated context and updating HANDOFF.md. "
            "Do not stop work or skip tests solely for token savings."
        )

    message = state.update(session_id, mutate)
    if not message:
        return None
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}


def main() -> int:
    try:
        raw = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
        if len(raw) > MAX_STDIN_BYTES:
            return 0
        payload = json.loads(raw)
        if isinstance(payload, dict):
            result = process(payload)
            if result:
                print(json.dumps(result))
    except Exception:
        # Advisory only: a telemetry problem must never block Codex.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
