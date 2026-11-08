"""Reversible, project- or user-scoped Codex Quota Keeper installation."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

START = "<!-- codex-quota-keeper:start -->"
END = "<!-- codex-quota-keeper:end -->"
EVENTS = ("UserPromptSubmit", "PostToolUse")
MARK = "-m codex_quota_keeper hook"


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()


def template(name: str) -> str:
    return files("codex_quota_keeper").joinpath("templates", name).read_text(encoding="utf-8")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig") if path.exists() else ""


def _block() -> str:
    return START + "\n" + template("AGENTS.md").rstrip() + "\n" + END


def _inject(old: str) -> str:
    block = _block()
    if (START in old) != (END in old):
        raise ValueError("AGENTS.md has an incomplete managed section")
    if START in old:
        if old.count(START) != 1 or old.count(END) != 1 or old.index(START) > old.index(END):
            raise ValueError("AGENTS.md has duplicated or reversed managed sections")
        return old[:old.index(START)] + block + old[old.index(END) + len(END):]
    return old.rstrip() + ("\n\n" if old.strip() else "") + block + "\n"


def _remove_block(old: str) -> str:
    if START not in old and END not in old:
        return old
    if old.count(START) != 1 or old.count(END) != 1 or old.index(START) > old.index(END):
        raise ValueError("AGENTS.md has malformed managed sections")
    before, after = old.split(START, 1)[0], old.split(END, 1)[1]
    return (before.rstrip() + "\n\n" + after.lstrip()).strip() + "\n" if (before + after).strip() else ""


def _hook_command() -> dict:
    args = [sys.executable, "-m", "codex_quota_keeper", "hook"]
    # Windows Codex supports command_windows; command is the portable fallback.
    return {
        "type": "command",
        "command": shlex.join(args),
        "commandWindows": subprocess.list2cmdline(args),
        "timeout": 10,
        "additionalContextLimit": 350,
        "additionalContextLimit": 350,
        "statusMessage": "Quota Keeper: recording event count",
    }


def _is_ours(handler: dict) -> bool:
    return isinstance(handler, dict) and (
        MARK in str(handler.get("command", ""))
        or MARK in str(handler.get("command_windows", ""))
        or MARK in str(handler.get("commandWindows", ""))
    )


def _hooks_new(old: str, remove: bool) -> str:
    try:
        config = json.loads(old) if old.strip() else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid hooks.json: {exc}") from exc
    if not isinstance(config, dict):
        raise ValueError("hooks.json must contain a JSON object")
    hooks = config.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("hooks.json 'hooks' must be an object")
    for event in EVENTS:
        groups = hooks.get(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"hooks.{event} must be a list")
        cleaned = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ValueError(f"Invalid hooks.{event} entry; refusing to overwrite")
            handlers = group["hooks"]
            kept = [h for h in handlers if not _is_ours(h)]
            if kept:
                cleaned.append({**group, "hooks": kept})
        if not remove:
            cleaned.append({"hooks": [_hook_command()]})
        if cleaned:
            hooks[event] = cleaned
        else:
            hooks.pop(event, None)
    return json.dumps(config, indent=2, ensure_ascii=False) + "\n"


def _backup(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    destination = path.with_name(f"{path.name}.cqk-backup-{stamp}")
    shutil.copy2(path, destination)
    return destination


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".cqk-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _edit(path: Path, content: str, apply: bool, messages: list[str]) -> None:
    current = _read(path)
    if current == content:
        messages.append(f"unchanged: {path}")
        return
    action = "update" if path.exists() else "create"
    messages.append(f"{'apply' if apply else 'preview'} {action}: {path}")
    if apply:
        if path.exists():
            messages.append(f"backup: {_backup(path)}")
        _atomic_write(path, content)


def configure(*, project: Path, scope: str = "project", apply: bool = False, remove: bool = False) -> list[str]:
    """Preview or apply a reversible configuration change.

    Parsing and validation happen before the first write so malformed config fails closed.
    """
    if scope not in ("project", "user"):
        raise ValueError("Scope must be project or user")
    root = codex_home() if scope == "user" else Path(project).expanduser().resolve()
    if scope == "project" and (not root.exists() or not root.is_dir()):
        raise ValueError(f"Project directory does not exist: {root}")
    policy = root / "AGENTS.md"
    hooks_path = root / "hooks.json" if scope == "user" else root / ".codex" / "hooks.json"
    old_policy = _read(policy)
    new_policy = _remove_block(old_policy) if remove else _inject(old_policy)
    old_hooks = _read(hooks_path)
    # Uninstall on an untouched project must not create a hooks.json,
    # and must not rewrite unrelated hooks merely to normalize formatting.
    if remove and MARK not in old_hooks:
        new_hooks = old_hooks
    else:
        new_hooks = _hooks_new(old_hooks, remove)

    # No side effects until both files have passed validation.
    messages: list[str] = []
    _edit(policy, new_policy, apply, messages)
    _edit(hooks_path, new_hooks, apply, messages)

    if not remove and scope == "project":
        handoff = root / "HANDOFF.md"
        if not handoff.exists():
            _edit(handoff, template("HANDOFF.md"), apply, messages)
    return messages


def make_handoff(project: Path, *, apply: bool = True) -> list[str]:
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Project directory does not exist: {root}")
    path = root / "HANDOFF.md"
    if path.exists():
        return [f"exists (not overwritten): {path}"]
    messages: list[str] = []
    _edit(path, template("HANDOFF.md"), apply, messages)
    return messages
