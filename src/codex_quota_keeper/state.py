"""Minimal, concurrency-safe JSON counters for Codex VS Code hooks.

Each session uses its existing hashed JSON filename; updates are atomic.
A separate OS file lock prevents lost increments across hook processes.
No prompts, raw session IDs, tool arguments, or transcripts are stored.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from .installer import codex_home

T = TypeVar("T")
COUNT_KEYS = ("prompts", "tools", "model_requests", "token_usage_reports")
TOKEN_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
STATUS_KEYS = ("completed", "failed", "cancelled")
MAX_INT = 2**63 - 1
MAX_EVENT_TOKENS = 1_000_000_000_000
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def state_path(session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return codex_home() / "quota-keeper" / "state" / f"{digest}.json"


def _nonnegative(value: object) -> int:
    return value if type(value) is int and 0 <= value <= MAX_INT else 0


def add(a: object, b: object) -> int:
    return min(MAX_INT, _nonnegative(a) + _nonnegative(b))


def clean(raw: object) -> dict:
    """Retain only approved numerical fields and milestone labels."""
    source = raw if isinstance(raw, dict) else {}
    values = {key: _nonnegative(source.get(key)) for key in COUNT_KEYS}
    usage = source.get("model_tokens")
    statuses = source.get("model_status")
    values["model_tokens"] = {
        key: _nonnegative(usage.get(key)) for key in TOKEN_KEYS
    } if isinstance(usage, dict) else {}
    values["model_status"] = {
        key: _nonnegative(statuses.get(key)) for key in STATUS_KEYS
    } if isinstance(statuses, dict) else {}
    announced = source.get("announced")
    values["announced"] = [
        item for item in announced[:100]
        if isinstance(item, str) and re.fullmatch(r"(prompts|tools)-[0-9]{1,7}", item)
    ] if isinstance(announced, list) else []
    return values


def _read(path: Path) -> dict:
    try:
        if path.stat().st_size > 512_000:
            raise ValueError(f"Counter file is unexpectedly large: {path}")
        return clean(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return clean({})


def _write(path: Path, values: dict) -> None:
    fd, name = tempfile.mkstemp(prefix=".cqk-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(clean(values), output, separators=(",", ":"))
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def _lock(path: Path):
    """Kernel-managed lock: auto-released when a process exits, incl. Windows."""
    lockfile = path.with_suffix(".lock")
    with lockfile.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            def try_acquire():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

            def release():
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            def try_acquire():
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            def release():
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

        deadline = time.monotonic() + 3
        while True:
            try:
                try_acquire()
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError("Unable to acquire CQK session lock")
                time.sleep(0.02)
        try:
            yield
        finally:
            release()


def update(session_id: str, mutate: Callable[[dict], T]) -> T:
    path = state_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock(path):
        values = _read(path)
        result = mutate(values)
        _write(path, values)
    return result


def summary(*, limit: int = 10) -> dict:
    """Read-only totals of hashed JSON files; limit applies to the recent list."""
    if not 1 <= limit <= 1000:
        raise ValueError("--limit must be between 1 and 1000")
    folder = codex_home() / "quota-keeper" / "state"
    sessions = []
    if folder.exists():
        for path in folder.glob("*.json"):
            if not _HASH.fullmatch(path.stem):
                continue
            try:
                values = _read(path)
                modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(
                    timespec="seconds"
                )
            except (OSError, ValueError, UnicodeError):
                continue
            sessions.append({"session_hash": path.stem, "updated_at": modified, **values})
    sessions.sort(key=lambda item: (item["updated_at"], item["session_hash"]), reverse=True)

    total = clean({})
    for session in sessions:
        for key in COUNT_KEYS:
            total[key] = add(total[key], session[key])
        for key in TOKEN_KEYS:
            total["model_tokens"][key] = add(
                total["model_tokens"].get(key), session["model_tokens"].get(key)
            )
        for key in STATUS_KEYS:
            total["model_status"][key] = add(
                total["model_status"].get(key), session["model_status"].get(key)
            )
    total.pop("announced", None)
    return {"sessions_total": len(sessions), "totals": total, "sessions": sessions[:limit]}


def format_summary(report: dict) -> str:
    total = report["totals"]
    usage = total["model_tokens"]
    cached = usage.get("cached_input_tokens", 0)
    input_tokens = usage.get("input_tokens", 0)
    lines = [
        f"Sessions: {report['sessions_total']} (showing {len(report['sessions'])} recent)",
        f"Prompts: {total['prompts']} | Tools: {total['tools']} | Model requests: {total['model_requests']}",
        f"Input tokens: {input_tokens:,} (cached subset: {cached:,}, uncached: {max(0, input_tokens-cached):,})",
        f"Output tokens: {usage.get('output_tokens', 0):,} (reasoning subset: {usage.get('reasoning_output_tokens', 0):,})",
        f"Usage reports: {total['token_usage_reports']} | Not an account quota or context-window estimate.",
    ]
    if report["sessions"]:
        lines.append("")
        lines.append("Updated (UTC)          Session       Prompts Tools Requests Input Output")
        for item in report["sessions"]:
            tokens = item["model_tokens"]
            lines.append(
                f"{item['updated_at'][:19]:22} {item['session_hash'][:12]} "
                f"{item['prompts']:7} {item['tools']:5} {item['model_requests']:8} "
                f"{tokens.get('input_tokens', 0):5} {tokens.get('output_tokens', 0):6}"
            )
    return "\n".join(lines)
