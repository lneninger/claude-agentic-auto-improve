#!/usr/bin/env python3
"""
memory-pager.py -- Stop hook. Layer 3 (pager) + Layer 2 (loud-fail).

The brain's offline-consolidation trigger, mechanized: at end-of-turn it checks
whether any ALWAYS-ON memory surface (the CLAUDE.md files) has exceeded its
budget in memory-blocks.json. If so, it appends a dated CONSOLIDATION PROPOSAL
to the staging file and logs loudly. It NEVER edits an always-on surface itself
and NEVER blocks the stop -- proposals are staged for human/agent review
(the staging gate against autonomous bad-writes).

Hook contract (Claude Code):
    stdin:  Stop payload (ignored beyond fail-soft consume)
    exit 0: ALWAYS (fail-open -- a broken pager must never wedge a session)
    stderr: free-form diagnostic

Reliability invariants (Layer 2):
    - fail-open: every error path returns 0
    - loud: over-budget + errors go to the shared error log, not /dev/null
    - idempotent: dedupe by (surface-id, size, date) so repeated stops at the
      same state are no-ops

Bypass:
    CLAUDE_MEMORY_PAGER=off   -- disable for a session
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).parent
sys.path.insert(0, str(_HOOKS_DIR))

try:
    from _error_log import log_event  # type: ignore
except Exception:
    def log_event(*args, **kwargs):
        return

try:
    import _memory_common as mc  # type: ignore
    _DEPS_OK = True
except Exception:  # pragma: no cover - fail-soft import
    _DEPS_OK = False


def is_disabled() -> bool:
    return os.environ.get("CLAUDE_MEMORY_PAGER", "").lower() in {
        "off", "0", "false", "no"
    }


def run() -> int:
    if is_disabled() or not _DEPS_OK:
        return 0

    # Consume stdin so the hook plays nice with the harness; content unused.
    try:
        sys.stdin.read()
    except Exception:
        pass

    try:
        config = mc.load_config()
    except Exception as exc:
        log_event(hook="memory-pager", event="config-load-failed",
                  details={"error": str(exc)})
        return 0

    try:
        rows = mc.check_budgets(config.get("always_on", []))
        over = [r for r in rows if r["over_by"] > 0]
        missing = [r for r in rows if not r["exists"]]

        if missing:
            log_event(hook="memory-pager", event="surface-missing",
                      details={"missing": [m["id"] for m in missing]})

        if not over:
            return 0

        staging = mc.expand(config.get("staging", {}).get("path", ""))
        seen_path = mc.expand(config.get("seen_state", ""))
        if not str(staging) or not str(seen_path):
            return 0

        entries = mc.build_pressure_entries(over)
        seen = mc.load_seen(seen_path)
        appended, seen = mc.append_staging(staging, entries, seen)
        if appended:
            mc.save_seen(seen_path, seen)
            log_event(
                hook="memory-pager",
                event="memory-pressure",
                details={
                    "over": [
                        {"id": r["id"], "tokens": r["tokens"],
                         "budget": r["budget"], "over_by": r["over_by"]}
                        for r in over
                    ],
                    "staged": appended,
                    "staging": str(staging),
                },
            )
            # stderr is advisory only (exit 0 -> not shown to Claude, but lands
            # in the harness log -- a loud, non-blocking trail).
            sys.stderr.write(
                f"[memory-pager] {len(over)} always-on surface(s) over budget; "
                f"{appended} proposal(s) staged at {staging}\n"
            )
    except Exception as exc:  # pragma: no cover - fail-soft
        log_event(hook="memory-pager", event="pager-error",
                  details={"error": str(exc)})
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(run())
