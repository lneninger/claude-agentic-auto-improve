#!/usr/bin/env python3
"""
compose_subissue_title.py -- build the GitHub title of a sub-issue from the
declared Sub-issue title format.

Caller
------
  * ``/task`` Parent-aware mode (``skills/task/references/parent-aware-mode.md``),
    before ``gh issue create``. It branches on the exit code and feeds the
    ``title`` field to ``gh`` through a quoted shell variable.

CLI
---
    py -3 .claude/scripts/compose_subissue_title.py --type <TAG> --parent <raw> \
        --subtask <raw> --title <bare> [--json] [--conventions <path>]

Exit 0 = composed, 2 = refused (the halting code ``verify_parent_link.py`` uses).

Contract: .claude/concepts/2026-10-15-subissue-title-parent-ref.md

INVARIANTS THIS FILE OWNS
-------------------------
I-1  A composed title contains ``P:#<n>`` and ``ST:<k>`` (as the declared format
     places them) and matches ``issueTitle.pattern``.
I-2  A refusal never carries a ``title``. There is no fallback shape.
I-3  The format is read from ``issueTitle.subIssue.format`` at call time.
I-4  This module is pure: no subprocess, no ``gh``, no file written.
I-6  With no ``--conventions`` and no ``CLAUDE_PROJECT_DIR`` the project root
     cannot be determined, so it refuses ``conventions-missing`` rather than
     falling through to the plugin's own conventions file.

THE ORDER IS THE ENFORCEMENT
----------------------------
Refusals are checked in the order of ``CAUSES``; the first match wins.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

# Closed, ordered set. Mirrored by name in parent-aware-mode.md and pinned by
# test_compose_subissue_title.py.
CAUSES = [
    "conventions-missing",
    "format-malformed",
    "parent-missing",
    "parent-not-positive-integer",
    "subtask-missing",
    "subtask-not-positive-integer",
    "bare-title-invalid",
    "pattern-mismatch",
]

PLACEHOLDERS = ("<EFFORT>", "<parent>", "<subtask>", "<Title>")
_PLACEHOLDER_RE = re.compile(r"<EFFORT>|<parent>|<subtask>|<Title>")
_DIGITS_RE = re.compile(r"[0-9]+")
_MAX_DIGITS = 18

REMEDIATION = {
    "conventions-missing": (
        "Add issueTitle.subIssue to the project's .claude/work-item-conventions.json: "
        '{"$comment": "...", "legend": "P = parent issue, ST = sub-task (its position in '
        "the parent's plan)\", \"format\": \"[<EFFORT>] P:#<parent> ST:<subtask> - <Title>\"}. "
        "issueTitle.pattern must also be present and a valid regular expression. "
        "Pass --conventions <project .claude/work-item-conventions.json> explicitly."
    ),
    "format-malformed": (
        "Fix issueTitle.subIssue.format: it must begin with [<EFFORT>] and hold each of "
        "<EFFORT>, <parent>, <subtask> and <Title> exactly once."
    ),
    "parent-missing": "Pass the parent issue number (PARENT_ISSUE) as --parent.",
    "parent-not-positive-integer": (
        "--parent must be a positive integer, optionally with one leading '#' (638 or #638)."
    ),
    "subtask-missing": "Pass the sub-task ordinal as --subtask (the 16 in sub-task t16).",
    "subtask-not-positive-integer": (
        "--subtask must be a positive integer (16, not t16 or 16.0)."
    ),
    "bare-title-invalid": (
        "--title must be the bare sub-task name: non-empty, one line, no control "
        "or format characters, and no effort tag already in front."
    ),
    "pattern-mismatch": (
        "The effort tag must be one of issueTitle.effortTypes and the composed title must "
        "match issueTitle.pattern."
    ),
}


def _refuse(cause, reason):
    return {
        "verdict": "refused",
        "cause": cause,
        "reason": reason,
        "remediation": REMEDIATION[cause],
    }


def _load_title_block(conventions_path):
    """Return ``(issueTitle block, refusal-or-None)``."""
    if conventions_path:
        path = Path(conventions_path)
    elif not os.environ.get("CLAUDE_PROJECT_DIR"):
        return None, _refuse(
            "conventions-missing",
            "project conventions root not determinable: no --conventions given and "
            "CLAUDE_PROJECT_DIR is unset.",
        )
    else:
        # Exactly the project's own file: never the shared multi-root locator, never the plugin's copy.
        path = Path(os.environ["CLAUDE_PROJECT_DIR"]) / ".claude" / "work-item-conventions.json"
    if not path.exists():
        return None, _refuse("conventions-missing", "conventions file not found: %s" % path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None, _refuse("conventions-missing", "conventions file unreadable: %s" % path)
    block = payload.get("issueTitle") if isinstance(payload, dict) else None
    if not isinstance(block, dict) or not block:
        return None, _refuse("conventions-missing", "no issueTitle block in %s" % path)
    sub = block.get("subIssue")
    if not isinstance(sub, dict) or not isinstance(sub.get("format"), str) or not sub["format"].strip():
        return None, _refuse("conventions-missing", "no issueTitle.subIssue.format in %s" % path)
    pattern = block.get("pattern")
    try:
        re.compile(pattern)
    except (TypeError, re.error):
        return None, _refuse("conventions-missing", "issueTitle.pattern missing or invalid in %s" % path)
    return block, None


def _positive_int(raw, missing_cause, bad_cause, label, strip_hash=False):
    """Return ``(int, refusal-or-None)`` for a raw numeric input."""
    text = (raw or "").strip()
    if strip_hash and text.startswith("#"):
        text = text[1:]
    # A lone '#' carries no number: it is "not supplied", for either numeric input.
    if not text.strip() or text == "#":
        return None, _refuse(missing_cause, "%s was not supplied." % label)
    # More than _MAX_DIGITS digits is refused before int(): no ValueError, no huge-number work.
    if not _DIGITS_RE.fullmatch(text) or len(text) > _MAX_DIGITS or int(text) < 1:
        return None, _refuse(bad_cause, "%s %r is not a positive integer." % (label, raw))
    return int(text), None


def compose(effort_tag, parent, subtask, bare_title, conventions_path=None):
    """Return the Title composition result as a dict (see module docstring)."""
    block, refusal = _load_title_block(conventions_path)
    if refusal:
        return refusal

    fmt = block["subIssue"]["format"]
    counts_ok = all(fmt.count(p) == 1 for p in PLACEHOLDERS)
    if not counts_ok or not fmt.startswith("[<EFFORT>]"):
        return _refuse(
            "format-malformed",
            "issueTitle.subIssue.format %r must begin with [<EFFORT>] and hold <EFFORT>, "
            "<parent>, <subtask> and <Title> exactly once." % fmt,
        )

    parent_n, refusal = _positive_int(
        parent, "parent-missing", "parent-not-positive-integer", "Parent", strip_hash=True)
    if refusal:
        return refusal
    subtask_k, refusal = _positive_int(
        subtask, "subtask-missing", "subtask-not-positive-integer", "Sub-task ordinal")
    if refusal:
        return refusal

    title = (bare_title or "").strip()
    tags = [t.get("tag") for t in block.get("effortTypes", []) if isinstance(t, dict) and t.get("tag")]
    if not title:
        return _refuse("bare-title-invalid", "The bare title is empty.")
    if any(unicodedata.category(ch) in ("Cc", "Cf", "Zl", "Zp") for ch in title):
        return _refuse(
            "bare-title-invalid", "The bare title contains a line break, control or format character.")
    if any(title.startswith("[%s]" % t) for t in tags):
        return _refuse("bare-title-invalid", "The bare title already starts with an effort tag.")

    if effort_tag not in tags:
        return _refuse("pattern-mismatch", "Effort tag %r is not declared in issueTitle.effortTypes." % effort_tag)
    values = {
        "<EFFORT>": effort_tag,
        "<parent>": str(parent_n),
        "<subtask>": str(subtask_k),
        "<Title>": title,
    }
    # Single pass, so a placeholder-looking string inside the bare title is never expanded.
    composed = _PLACEHOLDER_RE.sub(lambda m: values[m.group(0)], fmt)
    if re.match(block["pattern"], composed) is None:
        return _refuse("pattern-mismatch", "Composed title %r does not match issueTitle.pattern." % composed)

    return {
        "verdict": "composed",
        "title": composed,
        "reason": "Composed from issueTitle.subIssue.format.",
    }


_VALUE_OPTIONS = ("--type", "--parent", "--subtask", "--title", "--conventions")


def _bind_values(argv):
    """Glue each value option to the token after it (``--title X`` -> ``--title=X``).

    argparse would otherwise read a value that starts with '-' (a bare title of
    ``--help`` or ``-x``) as an option. The token after a value option is always
    its value, so the rewrite is lossless; ``--title=X`` passes through as given.
    """
    out, i = [], 0
    while i < len(argv):
        tok = argv[i]
        if tok in _VALUE_OPTIONS and i + 1 < len(argv):
            out.append("%s=%s" % (tok, argv[i + 1]))
            i += 2
        else:
            out.append(tok)
            i += 1
    return out


def main(argv=None):
    argv = _bind_values(list(sys.argv[1:] if argv is None else argv))
    parser = argparse.ArgumentParser(
        description="Compose a sub-issue title with its parent reference.", allow_abbrev=False)
    parser.add_argument("--type", dest="effort", default="", help="Effort tag, e.g. PERF.")
    parser.add_argument("--parent", default="", help="Parent issue number (optional leading #).")
    parser.add_argument("--subtask", default="", help="Sub-task ordinal (the 16 in t16).")
    parser.add_argument("--title", default="", help="Bare sub-task title, no effort tag.")
    parser.add_argument("--conventions", default=None, help="Path to work-item-conventions.json.")
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    args = parser.parse_args(argv)

    result = compose(args.effort, args.parent, args.subtask, args.title, args.conventions)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["verdict"] == "composed":
        print(result["title"])
    else:
        print("verdict: refused")
        print("cause:   %s" % result["cause"])
        print("reason:  %s" % result["reason"])
        print("remediation: %s" % result["remediation"])
    return 0 if result["verdict"] == "composed" else 2


if __name__ == "__main__":
    sys.exit(main())
