---
name: codex-quota-keeper
description: Use on explicit requests to optimize Codex context/tokens, inspect Codex Quota Keeper, compare usage or prepare a handoff. Not for ordinary coding tasks unless requested.
---

# Codex Quota Keeper

1. Treat the user's task and scope as authoritative. Prefer a minimal verified fix; avoid speculative refactors, dependencies and infrastructure.
2. For setup, run `cqk doctor`. Preview `cqk install --project <path>` and obtain approval before `--apply`; never install silently.
3. To reduce overhead, search narrowly before reading large files, limit verbose output and avoid unnecessary delegation. Never omit needed context, verification or tests.
4. Read `cqk stats` for local Codex VS Code hook observations, or `cqk report <file.jsonl>` for Codex CLI observations. Cached and reasoning tokens are subsets, not additive usage. Neither reports remaining subscription quota.
5. For a multi-session task, update `HANDOFF.md` with concise verified progress, unresolved work and a single exact next step. Start a new session by reading that file rather than repeating an entire transcript.
6. To assess savings, compare equivalent tasks and their tests, ideally across repeated runs. Do not present a smaller token total alone as proof of improved efficiency.
7. `cqk relay` is CLI-only and explicitly opt-in. Do not execute unattended work, change permissions, alter secrets, bypass approvals or deploy without authorization.

If a capability is unavailable, say so; do not invent hooks or UI controls.
