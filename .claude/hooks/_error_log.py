#!/usr/bin/env python3
"""
_error_log.py -- shared passive error logger for Claude Code hooks.

All blocking / warning hooks append a structured JSON line to
~/.claude/logs/errors.jsonl on every block or warn event. The log is
passive (no enforcement, no alerting) -- it exists as a data source
for the `/audit-errors` skill to mine weekly for recurring patterns
that should become feedback rules or hook patches.

Import usage from any hook:

    try:
        from _error_log import log_event
    except Exception:
        def log_event(*args, **kwargs):
            return  # fail-soft if the helper is missing

    ...
    log_event(
        hook="concept-gate",
        event="block",
        file=target_path,
        details={"reason": reason, "project": project_hint},
    )
    sys.exit(2)

The function is **fail-soft**: if it cannot write to the log for any reason
(permissions, disk full, encoding error), it returns silently so the caller
hook continues its normal flow. The log exists to observe hook behavior, not
to gate it.

Design goals:
  * One line per event (JSONL, easy to grep, easy to parse)
  * Deterministic schema (timestamp, hook, event, file, agent, session_id, details)
  * No I/O on the fast path if the log directory does not exist
    (the helper does NOT create the directory automatically; the
    `/audit-errors` skill creates it on first run).
  * Atomic append: open-append-close per call so concurrent hook invocations
    from parallel Claude sessions do not corrupt the file on Windows.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping

try:  # project-local logs when available
    import _project_paths as _pp_log
except Exception:  # pragma: no cover
    _pp_log = None
LOG_DIR = _pp_log.logs_dir() if _pp_log else Path.home() / ".claude" / "logs"
LOG_PATH = LOG_DIR / "errors.jsonl"


def _session_id() -> str:
    """Best-effort session id.

    Claude Code does not pass a session id on the stdin payload of every hook,
    so we fall back to an env var or a process-lineage hash. Callers may
    override via the kwarg.
    """
    for key in ("CLAUDE_SESSION_ID", "CLAUDE_CODE_SESSION_ID"):
        val = os.environ.get(key)
        if val:
            return val
    return f"pid-{os.getppid()}"


def log_event(
    hook: str,
    event: str,
    file: str | None = None,
    session_id: str | None = None,
    agent: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    """Append a structured event to ~/.claude/logs/errors.jsonl.

    Fail-soft: returns silently on any error. Never raises.

    Args:
        hook: short hook name without extension (e.g. "concept-gate").
        event: one of {"block", "warn", "redirect", "reconcile"}.
        file: optional target file path, if the event is file-scoped.
        session_id: optional override; defaults to env / parent pid hash.
        agent: optional agent name, if known.
        details: optional mapping of additional structured fields.
    """
    try:
        if not LOG_DIR.exists():
            # Do not auto-create -- the /audit-errors skill owns dir creation.
            # This keeps the fast path truly passive until the user enables it.
            return

        record = {
            "ts": int(time.time()),
            "hook": hook,
            "event": event,
            "file": file,
            "agent": agent,
            "session_id": session_id or _session_id(),
            "details": dict(details) if details else {},
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))

        # Atomic append -- Windows handles concurrent appends OK for short lines.
        with LOG_PATH.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")
    except Exception:
        # Intentionally swallow -- the log is an observation tool, never a gate.
        return


__all__ = ["log_event"]
