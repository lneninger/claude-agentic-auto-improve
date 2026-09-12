#!/usr/bin/env python3
"""
codegraph-turn-reset.py -- UserPromptSubmit hook that resets the
CodeGraph-first investigation turn.

Each new user prompt starts a new "investigation turn." The first
mcp__codegraph__* call within the turn opens the gate for Read / Grep /
Glob; subsequent prompts close the gate again by deleting the sentinel.

Hook contract (Claude Code):
    stdin:  JSON with { user_prompt, ... }
    exit 0: always (this hook never blocks the prompt)

Fail-soft: any failure is silent.
"""

from __future__ import annotations

import sys
from pathlib import Path

SENTINEL_NAME = ".codegraph-used-this-turn"


def log(msg: str) -> None:
    print(f"[codegraph-turn-reset] {msg}", file=sys.stderr)


def sentinel_path() -> Path:
    return Path.cwd() / ".claude" / SENTINEL_NAME


def main() -> None:
    p = sentinel_path()
    try:
        if p.exists():
            p.unlink()
    except OSError as e:
        log(f"could not delete sentinel {p}: {e}")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
