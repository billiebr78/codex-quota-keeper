"""Explicit, bounded continuation through fresh codex exec sessions.

Not a VS Code session switcher. Each CLI round starts with an empty transcript,
reads the project handoff and returns a strict terminal STATUS marker.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .usage import summarize

STATUS = re.compile(r"(?m)^STATUS: (CONTINUE|DONE|QUESTION|ERROR)\s*$")
NEXT = re.compile(r"(?ims)^## Next exact step\s*\n(.+?)(?=^## |\Z)")
PROMPT = """You are one fresh, bounded Codex CLI round.
Read the handoff at {handoff} first. Do ONLY the first actionable item under
'Next exact step'; do not complete unrelated tasks.
After the step, verify what you did, update the handoff with observed facts,
write a NEW next exact step (or put STAGE DONE on its first line when finished).
If a user decision, an unsafe operation or a blocked permission is required,
do not guess or bypass it. Record the blocker under Outstanding questions.
Keep your final answer under 8 lines and end it with exactly one line:
STATUS: CONTINUE
STATUS: DONE
STATUS: QUESTION
STATUS: ERROR
If uncertain, choose QUESTION or ERROR. Don't run unattended other agents.
"""


def _done(content: str) -> bool:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return bool(lines and lines[0].upper() == "STAGE DONE")


def _next_step(content: str) -> str:
    match = NEXT.search(content)
    return match.group(1).strip() if match else ""


def _final_answer(path: Path) -> tuple[str, dict]:
    text = ""
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "item.completed":
            item = event.get("item") or {}
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = str(item.get("text") or "")
    return text, summarize([path])


def run(*, project: Path, handoff: str = "HANDOFF.md", rounds: int = 2,
        timeout: int = 1800, sandbox: str = "read-only", model: str | None = None) -> int:
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Project not found: {root}")
    target = (root / handoff).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Handoff must be inside the selected project")
    if not target.is_file():
        raise ValueError(f"Missing {target}. Run 'cqk handoff' and fill it in first.")
    if rounds < 1 or rounds > 20:
        raise ValueError("Rounds must be between 1 and 20")
    if timeout < 30 or timeout > 86400:
        raise ValueError("Timeout must be 30..86400 seconds per round")
    if sandbox not in ("read-only", "workspace-write"):
        raise ValueError("Unsupported sandbox")
    for index in range(1, rounds + 1):
        before = target.read_text(encoding="utf-8-sig")
        if _done(before):
            print("Stage already complete: STAGE DONE")
            return 0
        step = _next_step(before)
        if not step or step.startswith("<") or "<ONE" in step:
            raise ValueError("Fill in '## Next exact step' in HANDOFF.md before running relay")
        # Validate the handoff before requiring the CLI; this also makes the
        # safety check available on machines with only the VS Code extension.
        executable = shutil.which("codex")
        if not executable:
            raise RuntimeError("Codex CLI not found on PATH; check 'codex --version'")
        cmd = [executable, "exec", "--json", "--sandbox", sandbox]
        if model:
            cmd.extend(["--model", model])
        cmd.append(PROMPT.format(handoff=str(target)))
        print(f"Round {index}/{rounds}: starting new Codex CLI session (sandbox={sandbox})", flush=True)

        # Temporary JSONL is deleted after parsing; it can include sensitive tool outputs.
        with tempfile.TemporaryDirectory(prefix="cqk-relay-") as folder:
            event_path = Path(folder) / "events.jsonl"
            with event_path.open("w", encoding="utf-8") as output:
                try:
                    completed = subprocess.run(
                        cmd, cwd=root, stdout=output, stderr=subprocess.PIPE,
                        text=True, encoding="utf-8", errors="replace", timeout=timeout,
                        check=False,
                    )
                except subprocess.TimeoutExpired:
                    print(f"Stopped: round {index} timed out. Check for child processes and inspect HANDOFF.md.",
                          file=sys.stderr)
                    return 1
            answer, metrics = _final_answer(event_path)

        if completed.returncode != 0:
            tail = (completed.stderr or "").strip()[-500:]
            print(f"Stopped: codex exec returned {completed.returncode}. {tail}", file=sys.stderr)
            return 1
        matches = STATUS.findall(answer)
        status = matches[-1] if matches else "NO_STATUS"
        print(f"Round {index}: {status}; tokens input={metrics['input_tokens']}, "
              f"output={metrics['output_tokens']}, cached={metrics['cached_input_tokens']}", flush=True)
        after = target.read_text(encoding="utf-8-sig")
        if _done(after):
            print("Stage completed and marked in HANDOFF.md")
            return 0
        if status == "DONE":
            print("Reported DONE without STAGE DONE marker: verify HANDOFF.md.", file=sys.stderr)
            return 1
        if status in ("QUESTION", "ERROR", "NO_STATUS"):
            print(f"Stopped: {status}; inspect HANDOFF.md before any further run.", file=sys.stderr)
            return 1
        if after == before:
            print("Stopped: handoff was not updated, so retry could repeat the same work.",
                  file=sys.stderr)
            return 1
    print("Round limit reached. Review HANDOFF.md before starting more rounds.")
    return 0
