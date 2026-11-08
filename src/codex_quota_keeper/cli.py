"""Command line for Codex Quota Keeper."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tomllib
from pathlib import Path

from . import __version__
from . import hooks, installer, relay, usage


def _doctor(project: Path) -> int:
    root = Path(project).expanduser().resolve()
    home = installer.codex_home()
    executable = shutil.which("codex")
    user_cfg = home / "config.toml"
    project_cfg = root / ".codex" / "config.toml"
    print(f"Codex Quota Keeper: {__version__}")
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    print(f"Codex CLI: {executable or 'not found on PATH (VS Code may still be installed)'}")
    print(f"CODEX_HOME: {home}")
    print(f"Project: {root} ({'found' if root.is_dir() else 'not found'})")
    for config in (user_cfg, project_cfg):
        if not config.exists():
            print(f"Config: absent: {config}")
            continue
        try:
            with config.open("rb") as stream:
                parsed = tomllib.load(stream)
            hooks_enabled = parsed.get("features", {}).get("hooks", True)
            print(f"Config: valid TOML: {config} (hooks feature={hooks_enabled})")
        except (ValueError, OSError, AttributeError) as exc:
            print(f"Config: INVALID: {config}: {exc}")
    for path in (home / "hooks.json", root / ".codex" / "hooks.json"):
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                print(f"Hooks: valid JSON ({len(data.get('hooks', {}))} event types): {path}")
            except (ValueError, OSError, AttributeError):
                print(f"Hooks: INVALID JSON: {path}")
    print("Note: project trust and live hook execution must be checked inside Codex.")
    return 0


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cqk", description="Context and token-efficiency toolkit for Codex")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="inspect the local Codex environment without changes")
    doctor.add_argument("--project", type=Path, default=Path.cwd())

    for name, desc in (
        ("install", "preview or apply managed AGENTS.md and hooks"),
        ("uninstall", "preview or remove only managed AGENTS.md and hooks"),
    ):
        command = sub.add_parser(name, help=desc)
        command.add_argument("--project", type=Path, default=Path.cwd())
        command.add_argument("--scope", choices=("project", "user"), default="project")
        command.add_argument("--apply", action="store_true", help="apply changes; omitted = dry run")

    handoff = sub.add_parser("handoff", help="create a HANDOFF.md only if absent")
    handoff.add_argument("--project", type=Path, default=Path.cwd())

    report = sub.add_parser("report", help="summarize one or more codex exec --json event files")
    report.add_argument("jsonl", type=Path, nargs="+")
    report.add_argument("--json", action="store_true", help="output structured JSON")

    compare = sub.add_parser("compare", help="compare two equivalent codex exec JSONL workloads")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("optimized", type=Path)
    compare.add_argument("--json", action="store_true", help="output structured JSON")

    sub.add_parser("hook", help="Codex lifecycle integration; reads hook JSON from stdin")

    run = sub.add_parser("relay", help="explicitly run bounded fresh codex exec sessions")
    run.add_argument("--project", type=Path, default=Path.cwd())
    run.add_argument("--handoff", type=str, default="HANDOFF.md")
    run.add_argument("--rounds", type=int, default=2)
    run.add_argument("--timeout", type=int, default=1800, help="seconds allowed per round")
    run.add_argument("--sandbox", choices=("read-only", "workspace-write"), default="read-only")
    run.add_argument("--model", type=str, default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "doctor":
            return _doctor(args.project)
        if args.command in ("install", "uninstall"):
            changes = installer.configure(
                project=args.project, scope=args.scope, apply=args.apply,
                remove=args.command == "uninstall",
            )
            print("\n".join(changes) or "No changes")
            if not args.apply:
                print("DRY RUN: repeat with --apply to perform these changes.")
            return 0
        if args.command == "handoff":
            print("\n".join(installer.make_handoff(args.project)))
            return 0
        if args.command == "report":
            result = usage.summarize(args.jsonl)
            print(json.dumps(result, indent=2) if args.json else usage.format_report(result))
            return 0
        if args.command == "compare":
            result = usage.compare([args.baseline], [args.optimized])
            print(json.dumps(result, indent=2) if args.json else usage.format_comparison(result))
            return 0
        if args.command == "hook":
            return hooks.main()
        if args.command == "relay":
            return relay.run(
                project=args.project, handoff=args.handoff, rounds=args.rounds,
                timeout=args.timeout, sandbox=args.sandbox, model=args.model,
            )
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"cqk error: {exc}", file=sys.stderr)
        return 1
    return 1
