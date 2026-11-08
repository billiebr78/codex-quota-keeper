# Contributing

Use Python 3.11+ and keep runtime dependencies at zero. Prefer small, testable,
reversible changes. Preserve existing user configurations and refuse malformed
inputs rather than guessing or overwriting them.

Local checks:

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src
```

For Codex-specific integration changes, reference current official documentation
and add a fixture or integration test. Do not use undocumented Claude tool names,
assume Codex subscription tokens equal API pricing, or collect user prompts.

Use pull requests for feature work. Never commit authentication tokens,
`codex exec --json` recordings or local counter state.
