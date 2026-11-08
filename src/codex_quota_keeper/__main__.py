"""Allow python -m codex_quota_keeper."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
