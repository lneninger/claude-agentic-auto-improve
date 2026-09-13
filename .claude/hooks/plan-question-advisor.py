#!/usr/bin/env python3
"""
plan-question-advisor.py -- UserPromptSubmit hook injecting question-quality rubric.

When plan mode is active (detected by scanning the transcript file for the
literal phrase "Plan mode is active"), inject a short reminder pointing at
~/.claude/skills/plan-questions/SKILL.md. This gives the agent a just-in-time
nudge to write AskUserQuestion calls developers can actually act on -- with
concrete file references, consequence/cost on every option, single decisions
per question, and a recommended default.

Hook contract (Claude Code):
    stdin:  JSON with { prompt: <user text>, transcript_path: <path>, ... }
    stdout: JSON with { hookSpecificOutput: { hookEventName: 'UserPromptSubmit',
                        additionalContext: <string injected into the prompt> } }
    exit 0: succeed (additionalContext is injected if present)
    other:  non-fatal -- fails open

Bypass:
    CLAUDE_PLAN_QUESTION_ADVISOR=off -- disable for a session
"""

from __future__ import annotations

import json
import os
import sys
from collections import deque

PLAN_MODE_MARKER = "Plan mode is active"
TRANSCRIPT_TAIL_LINES = 200

REMINDER = """\
[plan-question-advisor] Plan mode is active. Before any AskUserQuestion call:

* Open ~/.claude/skills/plan-questions/SKILL.md and apply the 10-rule rubric.
* TL;DR: state the WHY, reference concrete files/symbols, each option lists
  consequence + cost, one decision per question, recommend a default, use
  `preview` for visual/structural choices, skip the question if the answer
  is already in CLAUDE.md or the active concept contract.

The developer flagged earlier plan questions as 'too confusing'. This reminder
is the corrective. Bypass with CLAUDE_PLAN_QUESTION_ADVISOR=off.
"""


def log(msg: str) -> None:
    print(f"[plan-question-advisor] {msg}", file=sys.stderr)


def transcript_contains_plan_marker(transcript_path: str) -> bool:
    """Return True if the marker appears in the last TRANSCRIPT_TAIL_LINES lines."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return False
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fp:
            tail = deque(fp, maxlen=TRANSCRIPT_TAIL_LINES)
    except OSError as e:
        log(f"failed to read transcript: {e}")
        return False
    return any(PLAN_MODE_MARKER in line for line in tail)


def main() -> None:
    if os.environ.get("CLAUDE_PLAN_QUESTION_ADVISOR", "").lower() in {"off", "0", "false", "no"}:
        sys.exit(0)

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        log(f"failed to parse stdin: {e}")
        sys.exit(0)

    transcript_path = payload.get("transcript_path", "")
    if not isinstance(transcript_path, str):
        sys.exit(0)

    if not transcript_contains_plan_marker(transcript_path):
        sys.exit(0)

    output = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": REMINDER,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"internal error (failing open): {e}")
        sys.exit(0)
