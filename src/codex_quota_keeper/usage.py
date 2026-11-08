"""Parse the documented codex exec --json JSONL stream without assuming plan quota."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def read_events(paths: Iterable[Path]):
    for path in paths:
        with Path(path).expanduser().open("r", encoding="utf-8-sig", errors="replace") as source:
            for line in source:
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except (json.JSONDecodeError, UnicodeError):
                    yield None
                    continue
                yield value if isinstance(value, dict) else None


def summarize(paths: Iterable[Path]) -> dict:
    counts = {
        "completed_turns": 0, "failed_turns": 0, "invalid_lines": 0,
        "input_tokens": 0, "cached_input_tokens": 0,
        "output_tokens": 0, "reasoning_output_tokens": 0,
    }
    for event in read_events(paths):
        if event is None:
            counts["invalid_lines"] += 1
            continue
        kind = event.get("type")
        if kind == "turn.failed":
            counts["failed_turns"] += 1
        if kind != "turn.completed":
            continue
        usage = event.get("usage")
        if not isinstance(usage, dict):
            counts["invalid_lines"] += 1
            continue
        counts["completed_turns"] += 1
        for field in ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens"):
            value = usage.get(field, 0)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                counts[field] += value
    counts["uncached_input_tokens"] = max(0, counts["input_tokens"] - counts["cached_input_tokens"])
    counts["total_tokens"] = counts["input_tokens"] + counts["output_tokens"]
    counts["cache_share_of_input"] = (
        round(counts["cached_input_tokens"] / counts["input_tokens"], 4)
        if counts["input_tokens"] else 0
    )
    return counts


def format_report(report: dict) -> str:
    return "\n".join([
        f"Completed turns: {report['completed_turns']}",
        f"Failed turns: {report['failed_turns']}; invalid JSONL lines/events: {report['invalid_lines']}",
        f"Input tokens (including cached): {report['input_tokens']:,}",
        f"  Cached input:                 {report['cached_input_tokens']:,}",
        f"  Uncached input:               {report['uncached_input_tokens']:,}",
        f"Output tokens:                 {report['output_tokens']:,}",
        f"  Reasoning (subset of output): {report['reasoning_output_tokens']:,}",
        f"Input + output:                {report['total_tokens']:,}",
        f"Cached share of input:         {report['cache_share_of_input']:.1%}",
        "Not a subscription quota, monetary cost, or verified savings figure.",
    ])
