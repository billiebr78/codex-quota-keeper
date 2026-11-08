"""Transactional, privacy-minimal per-session accounting.

SQLite serializes read-modify-write updates from simultaneous hook processes.
Legacy JSON state is imported on first subsequent event, left untouched, and
included read-only in history until imported. No transcripts or raw IDs persist.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

from .installer import codex_home

T = TypeVar("T")
COUNTERS = ("prompts", "tools", "model_requests", "token_usage_reports")
STATUSES = ("completed", "failed", "cancelled")
TOKENS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
MAX_VALUE = 2**63 - 1
MAX_EVENT_TOKENS = 1_000_000_000_000
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_key TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    state_json TEXT NOT NULL
)
"""


def state_path(session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return codex_home() / "quota-keeper" / "state" / f"{digest}.json"


def db_path() -> Path:
    return codex_home() / "quota-keeper" / "history.sqlite3"


def _nonnegative(value: object) -> int:
    return value if type(value) is int and 0 <= value <= MAX_VALUE else 0


def safe_add(current: object, amount: object) -> int:
    return min(MAX_VALUE, _nonnegative(current) + _nonnegative(amount))


def _clean(raw: object) -> dict:
    """Whitelist persisted scalar metrics, never arbitrary model input."""
    if not isinstance(raw, dict):
        raw = {}
    state = {key: _nonnegative(raw.get(key, 0)) for key in COUNTERS}
    statuses = raw.get("model_status")
    state["model_status"] = {
        key: _nonnegative(statuses.get(key, 0)) for key in STATUSES
    } if isinstance(statuses, dict) else {key: 0 for key in STATUSES}
    usage = raw.get("model_tokens")
    state["model_tokens"] = {
        key: _nonnegative(usage.get(key, 0)) for key in TOKENS
    } if isinstance(usage, dict) else {key: 0 for key in TOKENS}
    announced = raw.get("announced")
    state["announced"] = [
        item for item in announced[:100]
        if isinstance(item, str) and re.fullmatch(r"(prompts|tools)-[0-9]{1,7}", item)
    ] if isinstance(announced, list) else []
    return state


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _legacy_data(path: Path) -> dict:
    try:
        if path.stat().st_size > 512_000:
            return _clean({})
        return _clean(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, UnicodeError):
        return _clean({})


def _legacy_time(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return _utc_now()


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=10, isolation_level=None)
    connection.execute("PRAGMA busy_timeout=10000")
    connection.execute(SCHEMA)
    return connection


def transact(session_id: str, callback: Callable[[dict], T]) -> T:
    """Apply a counter mutation under BEGIN IMMEDIATE: no lost updates."""
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(
                "SELECT created_at, state_json FROM sessions WHERE session_key=?",
                (digest,),
            ).fetchone()
            if row:
                created_at = row[0]
                state = _clean(json.loads(row[1]))
            else:
                legacy_path = state_path(session_id)
                state = _legacy_data(legacy_path) if legacy_path.is_file() else _clean({})
                created_at = _legacy_time(legacy_path) if legacy_path.is_file() else _utc_now()
            result = callback(state)
            connection.execute(
                """INSERT INTO sessions(session_key, created_at, updated_at, state_json)
                   VALUES(?, ?, ?, ?)
                   ON CONFLICT(session_key) DO UPDATE SET
                       updated_at=excluded.updated_at, state_json=excluded.state_json""",
                (digest, created_at, _utc_now(), json.dumps(_clean(state), separators=(",", ":"))),
            )
            connection.execute("COMMIT")
            return result
        except Exception:
            connection.execute("ROLLBACK")
            raise


def history(*, limit: int = 10) -> dict:
    if not 1 <= limit <= 1000:
        raise ValueError("--limit must be between 1 and 1000")
    results: dict[str, dict] = {}
    path = db_path()
    if path.exists():
        with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=10) as connection:
            for digest, created, updated, stored in connection.execute(
                "SELECT session_key, created_at, updated_at, state_json FROM sessions"
            ):
                if not HASH_PATTERN.fullmatch(digest):
                    continue
                results[digest] = {
                    "session_hash": digest, "created_at": created,
                    "updated_at": updated, "source": "sqlite",
                    **_clean(json.loads(stored)),
                }
    legacy_folder = codex_home() / "quota-keeper" / "state"
    if legacy_folder.is_dir():
        for item in legacy_folder.glob("*.json"):
            digest = item.stem
            if not HASH_PATTERN.fullmatch(digest) or digest in results:
                continue
            stamp = _legacy_time(item)
            results[digest] = {
                "session_hash": digest, "created_at": stamp,
                "updated_at": stamp, "source": "legacy-json",
                **_legacy_data(item),
            }
    all_sessions = sorted(
        results.values(), key=lambda item: (item["updated_at"], item["session_hash"]), reverse=True
    )
    totals = _clean({})
    for session in all_sessions:
        for key in COUNTERS:
            totals[key] = safe_add(totals[key], session[key])
        for key in STATUSES:
            totals["model_status"][key] = safe_add(
                totals["model_status"][key], session["model_status"][key]
            )
        for key in TOKENS:
            totals["model_tokens"][key] = safe_add(
                totals["model_tokens"][key], session["model_tokens"][key]
            )
    totals.pop("announced", None)
    return {"sessions_total": len(all_sessions), "totals": totals, "sessions": all_sessions[:limit]}


def format_history(report: dict) -> str:
    totals = report["totals"]
    tokens = totals["model_tokens"]
    lines = [
        f"Sessions: {report['sessions_total']} (showing {len(report['sessions'])} most recent)",
        f"Prompts: {totals['prompts']} | Tools: {totals['tools']} | Model requests: {totals['model_requests']}",
        f"Input tokens: {tokens['input_tokens']} (cached subset: {tokens['cached_input_tokens']})",
        f"Output tokens: {tokens['output_tokens']} (reasoning subset: {tokens['reasoning_output_tokens']})",
        f"Usage reports: {totals['token_usage_reports']} (not account quota)",
        "",
        "Last updated (UTC)      Session hash   Prompts Tools Requests Input Output Source",
    ]
    for session in report["sessions"]:
        token = session["model_tokens"]
        lines.append(
            f"{session['updated_at'][:19]:23} {session['session_hash'][:12]:12} "
            f"{session['prompts']:7} {session['tools']:5} {session['model_requests']:8} "
            f"{token['input_tokens']:5} {token['output_tokens']:6} {session['source']}"
        )
    return "\n".join(lines)
