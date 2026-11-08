---
name: codex-quota-keeper
description: Use when asked to reduce Codex token/context use, inspect Codex Quota Keeper setup, compare Codex JSONL usage, or prepare a safe handoff to a fresh coding session. Do not invoke for ordinary implementation tasks unless the user requests quota or session optimization.
---

# Codex Quota Keeper

Use the installed `cqk` CLI where available. Do not install it silently.

1. First run `cqk doctor` for the intended project; inspect the scope, Python interpreter and whether Codex hooks are active.
2. To configure, run `cqk install --project <absolute-project-path>` **without** `--apply` for a dry-run and review each change with the user. Then request the user's approval before applying.
3. For context management: search for symbols before reading whole huge files; keep project rules short; preserve the original code for safe edits and run necessary verification.
4. If work spans sessions, update the existing `HANDOFF.md` with verified progress, commands, outstanding questions and one precise next step. Do not append a raw transcript. A fresh Codex conversation should start by reading that handoff.
5. When evaluating consumption, use `cqk report <codex-exec-jsonl>` or `cqk compare <baseline-jsonl> <optimized-jsonl>`. These are CLI JSONL observations, **not** the weekly subscription quota or proof of saved money.
6. For optional `cqk relay`, verify that the handoff is filled and the project trusted. Do not start unattended runs without explicit user authorization; use the least powerful sandbox and bounded rounds.
7. Never alter account authentication, bypass prompts, sandbox protections or permissions in the name of saving tokens.

If the CLI is unavailable, explain the commands and prepare a safe handoff manually. Do not invent UI controls or hook capabilities.
