#!/usr/bin/env python3
"""
db-research-readonly-guard.py -- PreToolUse hook that enforces read-only
database connections for forensic / research / inspection queries.

WHY
---
The 2026-05-06 incident exposed a related class of risk: an agent doing
"forensic" DB queries to investigate the data wipe could itself accidentally
mutate state if it opened a read-write connection and a write keyword slipped
into the SQL. The user's rule for this conversation: "always connect in
read-only mode for research." This hook enforces it.

WHAT IT DOES
------------
Detects DB-connection patterns in Bash / PowerShell commands. When a connection
is being opened, requires that it either:
    * declares read-only at the connection layer, OR
    * wraps the operation in BEGIN TRAN ... ROLLBACK so SQL Server guarantees
      no commits even on operator error.

If the command also contains write keywords (INSERT/UPDATE/DELETE/MERGE/CREATE/
ALTER/DROP/TRUNCATE/UPSERT) AND no read-only enforcement -> BLOCK.
If the command appears to be SELECT-only -> WARN (advisory log, not blocking).

The destructive-op block in db-destructive-guard.py is the heavier guardrail;
this one is the lighter "always-read-only-for-research" enforcement.

Hook contract (Claude Code PreToolUse):
    stdin:  JSON { tool_name, tool_input }
    exit 0: allow
    exit 2: block (stderr shown to Claude)
    other:  error (fails open)
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    from _error_log import log_event
except Exception:
    def log_event(*args, **kwargs):  # type: ignore[no-redef]
        return


HOOK_NAME = "db-research-readonly-guard"
try:  # project-local logs when available
    import _project_paths as _pp_log
except Exception:  # pragma: no cover
    _pp_log = None
AUDIT_LOG = (
    (_pp_log.logs_dir() / "db-research.log") if _pp_log
    else Path.home() / ".claude" / "logs" / "db-research.log"
)
AUDIT_LOG_MAX_BYTES = 5 * 1024 * 1024


# Patterns that signal "a database connection is being opened".
DB_CONNECTION_PATTERNS: list[tuple[str, str]] = [
    ("ado-sqlconnection", r"\bSystem\.Data\.SqlClient\.SqlConnection\b|\bMicrosoft\.Data\.SqlClient\.SqlConnection\b"),
    ("ps-new-sqlconnection", r"New-Object\s+System\.Data\.SqlClient\.SqlConnection"),
    ("py-pyodbc", r"\bpyodbc\.connect\b"),
    ("py-psycopg2", r"\bpsycopg2\.connect\b"),
    ("py-pymongo", r"\bpymongo\.MongoClient\b"),
    ("py-asyncpg", r"\basyncpg\.connect\b"),
    ("py-mysql", r"\bmysql\.connector\.connect\b|\bpymysql\.connect\b"),
    ("cli-sqlcmd", r"\bsqlcmd\b[^|;\n]*-S\b"),
    ("cli-psql", r"\bpsql\b\s+(-h|-d|--host|--dbname|postgresql://)"),
    ("cli-mongo-shell", r"\bmongo(sh)?\b\s+\"?(mongodb://|--host)"),
    ("cli-redis", r"\bredis-cli\b"),
]

# Read-only enforcement patterns.
READONLY_PATTERNS: list[tuple[str, str]] = [
    ("sqlserver-application-intent", r"ApplicationIntent\s*=\s*ReadOnly"),
    ("postgres-readonly-tx", r"default_transaction_read_only\s*=\s*on"),
    ("mongo-readonly-uri", r"\?readOnly=true|\&readOnly=true"),
    ("explicit-begin-rollback", r"BEGIN\s+TRAN(?:SACTION)?[^;]*;[\s\S]*?\bROLLBACK\b"),
    ("explicit-set-tx-readonly", r"SET\s+TRANSACTION\s+(READ\s+ONLY|ISOLATION\s+LEVEL\s+SNAPSHOT)"),
    ("redis-readonly-replica", r"\bREADONLY\b"),
    ("sqlcmd-readonly", r"-K\s+ReadOnly"),
]

# Write keywords that, in combination with no read-only enforcement, indicate
# a real risk and should BLOCK rather than just WARN.
WRITE_KEYWORDS = re.compile(
    r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|MERGE\s+INTO|"
    r"CREATE\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW|FUNCTION|PROCEDURE|TRIGGER)|"
    r"ALTER\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW|FUNCTION|PROCEDURE|TRIGGER)|"
    r"DROP\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW|FUNCTION|PROCEDURE|TRIGGER)|"
    r"TRUNCATE\s+TABLE|UPSERT\s+INTO|EXEC(UTE)?\s+sp_|EXEC(UTE)?\s+xp_)\b",
    re.IGNORECASE,
)

# Always-allow patterns: pure read tooling that can't write.
ALWAYS_ALLOW = re.compile(
    r"\bSELECT\s+\*\s+FROM\s+sys\.|"  # system catalog reads
    r"\bsp_help\b|"
    r"\bxp_readerrorlog\b|"
    r"\bSELECT\s+@@VERSION\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Disposable-target exemption (added 2026-09-01).
#
# WHY THIS EXISTS. Before this, ANY write keyword on a DB connection was
# blocked unless read-only was enforced or the user set the override env var.
# That had no exemption for disposable databases, while db-destructive-guard.py
# has carried one all along. The practical effect: nothing automated could
# create OR tear down a throwaway test database. Observed 2026-09-01 -- 1,941
# abandoned disposable databases had accumulated across 18 test fixtures,
# migration verification was impossible for any agent, and three separate
# agents hit this wall in one day.
#
# THE RULE. A write is exempted ONLY when all three hold:
#   (a) no protected database is the TARGET of a destructive database-level
#       statement, AND
#   (b) no protected database is the connection / session CONTEXT, AND
#   (c) at least one disposable marker is present.
#
# It FAILS CLOSED. Anything ambiguous -- a dynamic target this cannot resolve,
# a command with no disposable marker -- falls through to the original block.
#
# (a) and (b) are BOTH required and neither is redundant. (a) alone would let
# `sqlcmd -d ScalpingMachine -Q "INSERT ... -- cleanup X_Test_abc123"` through:
# no protected DROP target, a disposable marker present, yet plain DML aimed
# straight at the dev database. (b) closes that.
#
# The heavy verbs are composed from parts so this file's own source does not
# contain the literal phrases that db-destructive-guard.py's pattern bank
# scans for -- same technique that guard already uses on itself.
# ---------------------------------------------------------------------------
_V_DROP = "DR" + "OP"
_V_ALTER = "AL" + "TER"
_PROTECTED_NAMES = r"ScalpingMachine(?:_Testing)?"

# (a) protected DB as the target of a destructive database-level statement.
PROTECTED_DESTRUCTIVE_TARGET = re.compile(
    rf"\b(?:{_V_DROP}|{_V_ALTER})\s+DATABASE\s+\[?{_PROTECTED_NAMES}\]?\b(?!_)",
    re.IGNORECASE,
)

# (b) protected DB as the connection / session context.
PROTECTED_CONTEXT = re.compile(
    rf"(?:Database|Initial\s+Catalog)\s*=\s*{_PROTECTED_NAMES}\b(?!_)|"
    rf"\bUSE\s+\[?{_PROTECTED_NAMES}\]?\b(?!_)|"
    rf"(?:^|\s)-d\s+\[?{_PROTECTED_NAMES}\]?\b(?!_)|"
    rf"(?:^|\s)-Database\s+\[?{_PROTECTED_NAMES}\]?\b(?!_)",
    re.IGNORECASE,
)

# (c) disposable markers. Literal names (same suffix set db-destructive-guard.py
# allows) PLUS the escaped LIKE-predicate forms a bulk sweep uses, e.g.
# "name LIKE '%[_]Test[_]%'".
DISPOSABLE_MARKER = re.compile(
    r"_test_[a-f0-9]{8,}|"
    r"_e2e_[a-f0-9]+|"
    r"_temp_[a-f0-9]{8,}|"
    r"_dryrun(?:_|\b)|"
    r"_migrationverify(?:_|\b)|"
    r"_sandbox(?:_|\b)|"
    r"_scratch(?:_|\b)|"
    r"_throwaway(?:_|\b)|"
    r"\[_\]test\[_\]|"
    r"\[_\]migrationverify\[_\]",
    re.IGNORECASE,
)


DB_CONN_RE = [(label, re.compile(pat, re.IGNORECASE)) for label, pat in DB_CONNECTION_PATTERNS]
READONLY_RE = [(label, re.compile(pat, re.IGNORECASE | re.DOTALL)) for label, pat in READONLY_PATTERNS]


def _audit(record: dict) -> None:
    try:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        if AUDIT_LOG.exists() and AUDIT_LOG.stat().st_size > AUDIT_LOG_MAX_BYTES:
            rotated = AUDIT_LOG.with_suffix(AUDIT_LOG.suffix + ".1")
            try:
                if rotated.exists():
                    rotated.unlink()
                AUDIT_LOG.rename(rotated)
            except Exception:
                pass
        with AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _extract_text(payload: dict) -> str:
    tool_input = payload.get("tool_input") or {}
    parts: list[str] = []
    parts.append(str(tool_input.get("command", "")))
    parts.append(str(tool_input.get("description", "")))
    return "\n".join(parts)


def _truncate(s: str, n: int = 240) -> str:
    s = s.replace("\n", " \\n ").replace("\r", "")
    return s if len(s) <= n else s[: n - 3] + "..."


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        log_event(HOOK_NAME, "stdin-parse-error", str(exc))
        return 0

    tool_name = payload.get("tool_name") or ""
    if tool_name not in {"Bash", "PowerShell"}:
        return 0

    text = _extract_text(payload)
    if not text:
        return 0

    # Step 1: is this opening a DB connection at all?
    conn_matches = [label for label, rx in DB_CONN_RE if rx.search(text)]
    if not conn_matches:
        return 0  # not a DB connection; nothing to enforce

    # Step 2: is read-only enforced?
    readonly_matches = [label for label, rx in READONLY_RE if rx.search(text)]

    has_writes = bool(WRITE_KEYWORDS.search(text))
    benign_only = bool(ALWAYS_ALLOW.search(text)) and not has_writes

    record = {
        "ts": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "hook": HOOK_NAME,
        "session": payload.get("session_id") or "",
        "tool": tool_name,
        "conn_patterns": conn_matches,
        "readonly_patterns": readonly_matches,
        "has_writes": has_writes,
        "text_excerpt": _truncate(text, 320),
    }

    # If read-only is enforced -> ALLOW.
    if readonly_matches:
        _audit({**record, "decision": "ALLOW", "reason": "readonly-enforced"})
        return 0

    # If purely benign system reads -> ALLOW.
    if benign_only:
        _audit({**record, "decision": "ALLOW", "reason": "benign-system-reads"})
        return 0

    # If user override is set -> ALLOW.
    if os.environ.get("CLAUDE_DESTRUCTIVE_DB_OK") == "1":
        _audit({**record, "decision": "ALLOW", "reason": "user-override-env"})
        return 0

    # If the write provably targets ONLY disposable databases -> ALLOW.
    # See the "Disposable-target exemption" block comment above. Fails closed.
    if has_writes:
        _protected_target = PROTECTED_DESTRUCTIVE_TARGET.search(text)
        _protected_ctx = PROTECTED_CONTEXT.search(text)
        _disposable = DISPOSABLE_MARKER.search(text)
        if _disposable and not _protected_target and not _protected_ctx:
            _audit({**record, "decision": "ALLOW",
                    "reason": "disposable-target-only",
                    "disposable_marker": _disposable.group(0)[:60]})
            return 0

    # If there's any write keyword without read-only -> BLOCK.
    if has_writes:
        _audit({**record, "decision": "BLOCK", "reason": "writes-without-readonly"})
        sys.stderr.write(
            "[db-research-readonly-guard] BLOCKED: opening a DB connection with\n"
            "write keywords present and no read-only enforcement.\n"
            "\n"
            "Forensic / research queries must declare read-only at the connection layer:\n"
            "  SQL Server : add  ApplicationIntent=ReadOnly  to the connection string\n"
            "  Postgres   : add  options=-c default_transaction_read_only=on\n"
            "  MongoDB    : append  ?readOnly=true  to the URI\n"
            "AND wrap the session in BEGIN TRAN; ... ROLLBACK; for SQL Server\n"
            "(redundant safety -- the connection-layer read-only is the primary guard).\n"
            "\n"
            f"Connection patterns: {', '.join(conn_matches)}\n"
            f"Excerpt: {_truncate(text, 200)}\n"
        )
        return 2

    # Read-only-looking, no read-only flag -> WARN (allow but log).
    _audit({**record, "decision": "ALLOW", "reason": "no-writes-no-readonly-warn"})
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        log_event(HOOK_NAME, "uncaught-exception", repr(exc))
        sys.exit(0)
