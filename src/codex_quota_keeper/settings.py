"""Local-only, validated alert configuration (no Codex config.toml changes)."""

from __future__ import annotations

import json
from pathlib import Path

from .installer import codex_home

DEFAULT_PROMPTS = (40, 80, 150)
DEFAULT_TOOLS = (100, 250, 500)


def config_path() -> Path:
    return codex_home() / "quota-keeper" / "config.json"


def defaults(prompts=DEFAULT_PROMPTS, tools=DEFAULT_TOOLS) -> dict:
    return {
        "alerts": {"prompts": list(prompts), "tools": list(tools)},
        "warnings_enabled": True,
    }


def validate(raw: object, *, prompts=DEFAULT_PROMPTS, tools=DEFAULT_TOOLS) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("CQK config must be a JSON object")
    if set(raw) - {"alerts", "warnings_enabled"}:
        raise ValueError("Unknown CQK config key")
    result = defaults(prompts, tools)
    if "warnings_enabled" in raw:
        if type(raw["warnings_enabled"]) is not bool:
            raise ValueError("warnings_enabled must be boolean")
        result["warnings_enabled"] = raw["warnings_enabled"]
    if "alerts" in raw:
        alerts = raw["alerts"]
        if not isinstance(alerts, dict) or set(alerts) - {"prompts", "tools"}:
            raise ValueError("alerts must contain only prompts and tools")
        for name in ("prompts", "tools"):
            if name not in alerts:
                continue
            values = alerts[name]
            if not isinstance(values, list) or len(values) > 20 or any(
                type(v) is not int or not 1 <= v <= 1_000_000 for v in values
            ) or values != sorted(set(values)):
                raise ValueError(
                    f"alerts.{name} must be an ascending list of up to 20 unique integers from 1 to 1000000"
                )
            result["alerts"][name] = values
    return result


def load(*, prompts=DEFAULT_PROMPTS, tools=DEFAULT_TOOLS) -> dict:
    path = config_path()
    if not path.exists():
        return defaults(prompts, tools)
    try:
        content = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, OSError) as exc:
        raise ValueError(f"Invalid CQK config {path}: {exc}") from exc
    return validate(content, prompts=prompts, tools=tools)


def init() -> tuple[Path, bool]:
    """Create defaults only if absent; never overwrite user edits."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as out:
            json.dump(defaults(), out, indent=2)
            out.write("\n")
    except FileExistsError:
        return path, False
    return path, True
