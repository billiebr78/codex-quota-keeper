# Contribution instructions

- Keep this repository independent of the JN's Quota Keeper implementation.
- Target Python 3.11+ and Windows / Linux / macOS, with no runtime third-party dependencies.
- Do not assume Codex exposes subscription quota percentages.
- Do not silently change sandbox, approvals, credentials, or user settings.
- Codex hook interfaces and CLI flags must be verified against current documentation before changing integration behavior.
- Keep all installs reversible and idempotent; preserve unrelated existing configuration.
- Do not record prompts or tool arguments in counters or telemetry.
- Run `python -m unittest discover -s tests -v` after every behavior change.
