# Architecture and trust boundaries

## Layers

```text
VS Code Codex / Codex CLI
      │
      ├── AGENTS.md        human-readable, bounded behavioral guidance
      ├── hooks.json       native lifecycle integration (opt-in)
      │       └── cqk hook
      │            └── ~/.codex/quota-keeper/state/<sha256(session_id)>.json
      │
      ├── codex exec --json > events.jsonl
      │       └── cqk report (explicit offline inspection)
      │
      └── HANDOFF.md
              └── cqk relay -> fresh codex exec rounds (explicit opt-in)
```

Nothing in v0.1 changes Codex authentication, account quota, sandbox permissions, or billing. All runtime code uses Python 3.11+ standard-library modules.

## Design decisions

**Do not parse private VS Code rollout internals as a core dependency.** They can change between versions. Only `codex exec --json` output is used for token reporting. Hooks use their documented `session_id` and `hook_event_name` fields only.

**Do not assume a universal token price.** Models, caching and subscription quota enforcement differ. Reporting uses the counters given by a completed turn, not an inferred price.

**Do not implement a VS Code session opener by imitating Claude tools.** The CLI relay starts fresh `codex exec` runs in a bounded loop. It cannot move the active VS Code chat. The default sandbox is read-only. Any file-writing permission must be explicitly requested by the CLI caller.

**Do not store prompts in telemetry.** The hook reads an incoming JSON payload but persists only counters and warning milestones keyed by an irreversible hash of the provided session ID. The JSONL passed to `cqk report` stays on the caller's disk.

**Avoid global configuration mutation by default.** The installer only touches the selected project and leaves `config.toml` unchanged. The user scope is explicit.

## Failure behavior

- Invalid `hooks.json`: refuse installation; leave policy unchanged.
- Incomplete policy block: refuse installation/uninstall rather than removing unknown text.
- Hook parse or state error: log nothing and allow Codex to continue (advisory functionality).
- Unrecognized or absent relay status: stop instead of looping.
- No handoff progress between relay rounds: stop to prevent duplicate work.
- Unknown CLI version or feature: `cqk doctor` reports what it can see; it doesn't guess extension capabilities.

## Current limitations

- Hooks introduce local Python startup overhead for each matched event.
- Counter state uses atomic file replacement but no cross-process counter lock; simultaneous events may lose increments. Warnings are advisory.
- Manual relay timeout can leave child processes on some platforms; verify processes before retrying.
- The installation is not a transactional multi-file change. Backups mitigate but cannot eliminate partial-write failures.
- Unverified Codex CLI or VS Code versions may change event schemas. Run tests in real environments before claiming broad compatibility.

## Threat model

Project content and `HANDOFF.md` may contain untrusted instructions. Codex still evaluates its normal permissions. This tool is **not** a sandbox or a policy enforcement boundary, and its prompts must never be used to bypass approval. Keep `workspace-write` automation limited to trusted repositories and reviewed handoffs.
