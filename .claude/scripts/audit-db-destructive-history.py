#!/usr/bin/env python3
"""
audit-db-destructive-history.py -- retroactive audit of destructive DB ops
across every Claude Code session task transcript on this workstation.

WHY
---
After the 2026-05-06 incident (lneninger / strategies wipe), the user needed
a way to retroactively answer "did any Claude session ever run a destructive
DB op?" The PreToolUse hook prevents future incidents, but historical drops
can only be found by greping past session transcripts. This script does that.

USAGE
-----
    py -3 .claude/scripts/audit-db-destructive-history.py [--since YYYY-MM-DD]

Default: scans every session transcript ever recorded under the local Claude
Code temp directory. Optional --since filters to recent sessions only.

OUTPUT
------
A chronological table of every executed Bash tool call whose command matches
the destructive-op pattern set in db-destructive-guard.py. Each row shows
session UUID, task ID, file mtime, and the truncated command.

Read-only -- never modifies anything.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path


# Reuse the same pattern set as the hook so audit and prevention agree.
DESTRUCTIVE_PATTERNS: list[tuple[str, str]] = [
    ("ef-database-drop", r"\bdotnet\s+ef\s+database\s+drop\b"),
    ("sql-drop-database", r"\bDROP\s+DATABASE\b"),
    ("sql-drop-schema", r"\bDROP\s+SCHEMA\b"),
    ("sql-drop-table", r"\bDROP\s+TABLE\b"),
    ("sql-truncate", r"\bTRUNCATE\s+TABLE\b"),
    ("ef-ensure-deleted", r"\.EnsureDeleted(Async)?\s*\("),
    ("migration-builder-sql-drop", r"migrationBuilder\.Sql\s*\([^)]*\b(DROP\s+(DATABASE|TABLE|SCHEMA)|TRUNCATE)\b"),
    ("pg-dropdb", r"(?<![\w.-])dropdb(?![\w.-])"),
    ("mysql-mysqladmin-drop", r"\bmysqladmin\b[^|;\n]*\bdrop\b"),
    ("mongo-drop-database", r"\bdb\.dropDatabase\s*\("),
    ("redis-flushall", r"\bFLUSHALL\b"),
    ("redis-flushdb", r"\bFLUSHDB\b"),
    ("sqlpackage-block-data-loss-false", r"\bsqlpackage(\.exe)?\b[^|;\n]*BlockOnPossibleDataLoss\s*=\s*[Ff]alse"),
]
DESTRUCTIVE_RE = [(label, re.compile(pat, re.IGNORECASE)) for label, pat in DESTRUCTIVE_PATTERNS]

# Same disposable allow-list as the hook.
DISPOSABLE_PATTERNS: list[tuple[str, str]] = [
    ("dryrun-suffix", r"_dryrun(?:_|\b)"),
    ("migrationverify-suffix", r"_migrationverify(?:_|\b)"),
    ("test-guid-suffix", r"_test_[a-f0-9]{8,}"),
    ("sandbox-suffix", r"_sandbox(?:_|\b)"),
    ("scratch-suffix", r"_scratch(?:_|\b)"),
    ("throwaway-suffix", r"_throwaway(?:_|\b)"),
    ("e2e-guid-suffix", r"_e2e_[a-f0-9]+"),
    ("temp-guid-suffix", r"_temp_[a-f0-9]{8,}"),
    ("sqlite-memory", r":memory:"),
    ("sql-tempdb", r"Database\s*=\s*tempdb\b"),
]
DISPOSABLE_RE = [(label, re.compile(pat, re.IGNORECASE)) for label, pat in DISPOSABLE_PATTERNS]

# Match an executed Bash tool call with destructive op in the command text.
# The transcript JSON has shape: ..."name":"Bash","input":{"command":"...",...}
BASH_CALL_RE = re.compile(
    r'"name"\s*:\s*"Bash"\s*,\s*"input"\s*:\s*\{\s*"command"\s*:\s*"((?:[^"\\]|\\.)*)"',
    re.DOTALL,
)


def _decode(s: str) -> str:
    """JSON string -> Python string (handle \\n, \\", \\\\, \\u escapes)."""
    try:
        return json.loads('"' + s + '"')
    except Exception:
        return s


def find_temp_root() -> Path | None:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Temp" / "claude",
        Path.home() / "AppData" / "Local" / "Temp" / "claude",
        Path("/tmp/claude"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit destructive DB ops across Claude sessions")
    ap.add_argument("--since", help="ISO date YYYY-MM-DD; scan only files mtime >= this", default=None)
    ap.add_argument("--include-disposable", action="store_true", help="also list ops against disposable DBs (default: hide)")
    args = ap.parse_args()

    root = find_temp_root()
    if not root:
        print("ERROR: could not locate Claude Code temp dir", file=sys.stderr)
        return 1

    since: dt.datetime | None = None
    if args.since:
        try:
            since = dt.datetime.fromisoformat(args.since)
        except ValueError:
            print(f"ERROR: bad --since format: {args.since}", file=sys.stderr)
            return 1

    rows: list[dict] = []
    files_scanned = 0
    for output in root.rglob("tasks/*.output"):
        try:
            stat = output.stat()
        except FileNotFoundError:
            continue
        mtime = dt.datetime.fromtimestamp(stat.st_mtime)
        if since and mtime < since:
            continue

        files_scanned += 1
        try:
            text = output.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        # Walk every executed Bash command in this transcript.
        for m in BASH_CALL_RE.finditer(text):
            cmd = _decode(m.group(1))
            destructive_hits = [label for label, rx in DESTRUCTIVE_RE if rx.search(cmd)]
            if not destructive_hits:
                continue
            disposable_hits = [label for label, rx in DISPOSABLE_RE if rx.search(cmd)]
            if disposable_hits and not args.include_disposable:
                continue
            session_uuid = output.parent.parent.name
            task_id = output.stem
            rows.append({
                "mtime": mtime,
                "session": session_uuid,
                "task": task_id,
                "destructive": destructive_hits,
                "disposable": disposable_hits,
                "command": cmd[:200] + ("..." if len(cmd) > 200 else ""),
            })

    rows.sort(key=lambda r: r["mtime"])
    print(f"# Audit of destructive DB ops across Claude Code session transcripts")
    print(f"# Scanned {files_scanned} task output files under: {root}")
    if since:
        print(f"# Filter: mtime >= {since.isoformat()}")
    print(f"# Hits: {len(rows)}")
    print()
    if not rows:
        print("(no destructive ops found)")
        return 0

    for r in rows:
        flag = "DISPOSABLE-OK" if r["disposable"] else "DESTRUCTIVE"
        print(f"[{r['mtime'].isoformat()}] {flag} session={r['session']} task={r['task']}")
        print(f"    patterns: {', '.join(r['destructive'])}")
        if r["disposable"]:
            print(f"    disposable: {', '.join(r['disposable'])}")
        print(f"    command:  {r['command']}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
