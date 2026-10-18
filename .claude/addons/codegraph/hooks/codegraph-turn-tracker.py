#!/usr/bin/env python3
"""
codegraph-turn-tracker.py -- PostToolUse hook that marks the current
investigation turn as having used CodeGraph.

When any mcp__codegraph__* tool completes (even with an error), this hook
writes <cwd>/.claude/.codegraph-used-this-turn. The presence of that
sentinel opens the codegraph-first-guard gate for Read / Grep / Glob
during the rest of the current turn.

Hook contract (Claude Code):
    stdin:  JSON with { tool_name, tool_input: {...}, ... }
    exit 0: always (this hook never blocks)
    other:  fail-soft -- log to stderr, exit 0

Fail-soft is critical: this hook must not impede the PostToolUse pipeline.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

SENTINEL_NAME = ".codegraph-used-this-turn"


def log(msg: str) -> None:
    print(f"[codegraph-turn-tracker] {msg}", file=sys.stderr)


def sentinel_dir() -> Path:
    return Path.cwd() / ".claude"


def sentinel_path() -> Path:
    return sentinel_dir() / SENTINEL_NAME


def write_sentinel(tool_name: str, tool_input: dict) -> None:
    sd = sentinel_dir()
    try:
        sd.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log(f"could not create {sd}: {e}")
        return

    # Best-effort first-80-chars summary of the tool input for debug.
    summary = ""
    try:
        for key in ("query", "pattern", "id", "symbol", "name", "path", "file_path"):
            v = tool_input.get(key)
            if isinstance(v, str) and v:
                summary = v[:80]
                break
        if not summary:
            summary = json.dumps(tool_input, ensure_ascii=False)[:80]
    except Exception:  # noqa: BLE001
        summary = ""

    payload = {
        "ts": int(time.time()),
        "tool": tool_name,
        "summary": summary,
        "pid": os.getpid(),
    }
    try:
        sentinel_path().write_text(
            json.dumps(payload, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        log(f"could not write sentinel {sentinel_path()}: {e}")


def main() -> None:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        log(f"failed to parse stdin payload: {e}")
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    # Match Claude Code MCP tool naming convention: mcp__<server>__<tool>.
    if not tool_name.startswith("mcp__codegraph__"):
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    write_sentinel(tool_name, tool_input)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
