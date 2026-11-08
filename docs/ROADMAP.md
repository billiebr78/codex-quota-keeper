# Roadmap

## v0.1 — functional, conservative prototype

- [x] Standalone Python package and CLI.
- [x] Project/user scoped installation preview, optional apply, backup and uninstall.
- [x] Native `AGENTS.md` policy and hook integration.
- [x] Anonymous prompt/tool-count milestones.
- [x] Diagnostic PostModelRequest attempt/outcome counters with optional token fields, pending real VS Code validation.
- [x] `codex exec --json` token reports and comparisons of equivalent runs.
- [x] Optional Codex Skill (manual installation).
- [x] Handoff template and bounded opt-in CLI relay.
- [x] Offline unit tests and CI for Windows/Linux.
- [ ] Integration test with a real current Codex CLI installation.
- [ ] Validate VS Code extension hook behavior end-to-end on Windows.

## Next

1. Benchmark the same verified coding task with and without the managed guidance, comparing *tokens per successful task*.
2. Add supported version/capability probing; avoid inventing hooks or settings.
3. Explore persistent lightweight summaries that can be re-read selectively.
4. Improve cross-process state synchronization and relay cancellation on Windows.
5. Consider a small local-only status display **after** measurements justify its complexity.
6. Explore safe session-transfer integrations only if officially supported by Codex and the VS Code extension.

## Out of scope

- Circumventing subscription or rate limits.
- Capturing secrets, prompts, or private transcripts for analytics.
- Changing model, approval or sandbox settings without user intent.
- Unrestricted unattended agents, hidden autonomous trading or deployment.
