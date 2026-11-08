# Codex configuration and integration

## Supported installations

`cqk install --project <directory> --apply` modifies only:
- `<directory>/AGENTS.md` — one delimited, managed block; keeps existing instructions.
- `<directory>/.codex/hooks.json` — adds `UserPromptSubmit` and `PostToolUse` handlers without removing unrelated handlers.
- `<directory>/HANDOFF.md` — creates a template only when absent.

`cqk install --scope user --apply` uses `$CODEX_HOME` (by default `~/.codex`), writing `AGENTS.md` and `hooks.json` there. No global handoff is created.

The hooks invoke the **same Python interpreter** that installed the tool. If you later delete or move that virtual environment, reinstall from a stable interpreter. In VS Code, local project hooks run only in trusted projects. Hooks can require their own trust confirmation. Reopen the session after changes.

## Optional native Codex tuning (manual, not installed automatically)

Choose settings after examining your account, workload and existing `config.toml`; never blindly replace it.

```toml
# ~/.codex/config.toml or trusted project .codex/config.toml
[agents]
max_concurrent_threads_per_session = 2
default_subagent_reasoning_effort = "low"
# default_subagent_model = "your-supported-model-id"
```

The `agents.default_subagent_model` setting is optional. No model identifier is assumed. An explicit agent model or reasoning effort may take precedence. Low effort may hurt complex tasks; measure task correctness.

To override compaction, the documented key is `model_auto_compact_token_limit`. Set it **only when you know the active model's context limit and have validated behavior**. This project does not select a magic token threshold.

Codex may disable hooks via `[features] hooks = false`. `cqk doctor` checks for this, but the VS Code extension's active configuration, installation and trust decisions should also be verified manually.

## Hooks

The installed hook handlers use the documented hook event protocol:

- `UserPromptSubmit`: increments a per-session prompt counter.
- `PostToolUse`: increments a per-session completed-tool counter.
- Only when a milestone is first crossed, returns `hookSpecificOutput.additionalContext` to recommend checking handoff/context.

Thresholds are hard-coded in `src/codex_quota_keeper/hooks.py` for v0.1. Counts are **not** exact tokens, spend, requests or account quota. No transcript parsing is required. Only a hash of `session_id` and counters are persisted under `$CODEX_HOME/quota-keeper/state`.

The command can be exercised locally with a synthetic event:

```powershell
'{"hook_event_name":"UserPromptSubmit","session_id":"local-test"}' | cqk hook
```

No output is expected on the first event. Warnings occur at configured thresholds. Reset a test by deleting only the corresponding generated state file.

## Usage report

`cqk report session.jsonl` parses the documented event type `turn.completed` emitted by `codex exec --json`. It records input, cached input (a **subset** of input), output and optional reasoning output (a **subset** of output). `total_tokens = input + output`.

This does not cover every Codex VS Code interaction. Counting input and cached input separately as additive would overstate total tokens. No claim about money saved or a ChatGPT plan's percentage quota is supported.

## Optional Skill

Copy `.agents/skills/codex-quota-keeper/SKILL.md` from this repository into the target project's `.agents/skills/codex-quota-keeper/SKILL.md`. It is deliberately not installed by `cqk install`, to keep the managed configuration minimal. Request `$codex-quota-keeper` to use it explicitly. Codex discovers project Skills from `.agents/skills` in trusted local repositories.

## Comparative measurement

Use `cqk compare baseline.jsonl optimized.jsonl` **only** when both runs carried out equivalent tasks and correctness was independently verified. The output reports observed token changes, not proven causal savings or plan quota changes. For better measurements, repeat each condition across several tasks and record test results and elapsed time separately.

## Restore

`cqk uninstall --project <directory> --apply` removes only its managed AGENTS.md block and hook entries. It **does not** delete handoffs, counter files, other hooks or backups. You may manually restore a timestamped `*.cqk-backup-*` if you want the exact original bytes/formatting rather than the semantic merge.

## Documentation references

- [Codex Hooks](https://learn.chatgpt.com/docs/hooks)
- [Codex Configuration Reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- [AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
- [Codex Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode)
