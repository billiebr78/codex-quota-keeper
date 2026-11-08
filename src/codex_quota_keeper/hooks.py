"""Codex lifecycle hooks: anonymous per-session prompt and tool counters.

Reads only session_id, hook_event_name; never persists prompts, tool arguments,
user text or transcript contents. This is not a token/usage monitor.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from .installer import codex_home

PROMPT_THRESHOLDS = (40, 80, 150)
TOOL_THRESHOLDS = (100, 250, 500)
MAX_STDIN_BYTES = 2_000_000


def state_path(session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return codex_home() / "quota-keeper" / "state" / f"{digest}.json"


def _save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".cqk-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(state, target, separators=(",", ":"))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def process(payload: dict) -> dict | None:
    event = payload.get("hook_event_name")
    if event not in ("UserPromptSubmit", "PostToolUse", "PostModelRequest"):
        return None
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id or len(session_id) > 512:
        return None
    path = state_path(session_id)
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (FileNotFoundError, OSError, ValueError):
        state = {}

    if event == "PostModelRequest":
        # PostModelRequest is diagnostic-only. Never inject context into model
        # responses and never save prompts, errors, tool arguments or model text.
        previous = state.get("model_requests", 0)
        state["model_requests"] = (previous if type(previous) is int and previous >= 0 else 0) + 1
        status = payload.get("status")
        if status in ("completed", "failed", "cancelled"):
            statuses = state.get("model_status")
            if not isinstance(statuses, dict):
                statuses = {}
            old_status = statuses.get(status, 0)
            statuses[status] = (old_status if type(old_status) is int and old_status >= 0 else 0) + 1
            state["model_status"] = statuses
        usage = payload.get("token_usage")
        if isinstance(usage, dict):
            allowed = ("input_tokens", "cached_input_tokens", "output_tokens",
                       "reasoning_output_tokens")
            totals = state.get("model_tokens")
            if not isinstance(totals, dict):
                totals = {}
            observed = False
            for field in allowed:
                value = usage.get(field)
                if type(value) is int and value >= 0:
                    old_value = totals.get(field, 0)
                    totals[field] = (old_value if type(old_value) is int and old_value >= 0 else 0) + value
                    observed = True
            if observed:
                state["model_tokens"] = totals
                prev = state.get("token_usage_reports", 0)
                state["token_usage_reports"] = (prev if type(prev) is int and prev >= 0 else 0) + 1
        _save(path, state)
        return None

    key = "prompts" if event == "UserPromptSubmit" else "tools"
    thresholds = PROMPT_THRESHOLDS if key == "prompts" else TOOL_THRESHOLDS
    current = state.get(key, 0)
    current = current if type(current) is int and current >= 0 else 0
    count = current + 1
    state[key] = count
    announced = state.get("announced", [])
    if not isinstance(announced, list):
        announced = []
    reached = [n for n in thresholds if count >= n and f"{key}-{n}" not in announced]
    for n in reached:
        announced.append(f"{key}-{n}")
    state["announced"] = announced
    _save(path, state)

    if not reached:
        return None
    message = (
        f"Codex Quota Keeper: {count} {key} in this session (event counts, not token or quota data). "
        "At the next safe milestone, consider verifying progress, updating HANDOFF.md "
        "and starting a fresh session if the context is large. Do not skip tests."
    )
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message}}


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
        # Advisory feature: never block Codex work because of telemetry failures.
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
