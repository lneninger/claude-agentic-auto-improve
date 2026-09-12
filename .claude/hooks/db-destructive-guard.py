#!/usr/bin/env python3
"""
db-destructive-guard.py -- PreToolUse hook that hard-blocks destructive
database operations against working / dev / production connection strings.

WHY THIS EXISTS
---------------
On 2026-05-06 a Claude sub-agent in a parallel session executed
`dotnet ef database drop --force --project src/ScalpingMachine.Persistence
--startup-project src/ScalpingMachine.API` to "test the migration on a fresh
LocalDB," following the project rule
`feedback_inmemory_does_not_validate_migrations.md` literally. The connection
string in `appsettings.json` pointed at the working dev DB, so the drop wiped
the user's `lneninger` account, all strategies, all screeners, all runs.
The rule did not specify that "freshly-deleted LocalDB" must be a SEPARATE,
DISPOSABLE database. This hook closes that gap at a layer the agent
cannot bypass.

WHAT IT DOES
------------
Inspects every Bash / Write / Edit / MultiEdit / PowerShell tool call. If the
command/content matches any pattern in DESTRUCTIVE_PATTERNS, the hook checks
whether the same input also names a disposable DB (DISPOSABLE_PATTERNS). If
not, and unless CLAUDE_DESTRUCTIVE_DB_OK=1 is set, the hook BLOCKS with exit
code 2 and prints a stderr message Claude can read.

CROSS-DATA-MANAGER COVERAGE
---------------------------
EF Core CLI, raw T-SQL, EF runtime EnsureDeleted, sqlpackage Publish with
BlockOnPossibleDataLoss=False, Postgres CLI (dropdb, pg_dropcluster), MySQL
CLI (mysqladmin drop), MongoDB shell (db.dropDatabase), Redis (FLUSHALL/DB),
Cosmos SDK (deleteContainer / deleteDatabase), and migrationBuilder.Sql with
DROP/TRUNCATE inside.

OVERRIDE
--------
For a one-shot human-approved exception, the USER (not the agent) sets:
    CLAUDE_DESTRUCTIVE_DB_OK=1   (POSIX)
    $env:CLAUDE_DESTRUCTIVE_DB_OK="1"   (PowerShell)
The hook does not unset it (the OS shell scope handles that); a subsequent
agent-spawned sub-shell will inherit it only if explicitly passed. Agents
MUST NOT set this variable themselves.

Hook contract (Claude Code PreToolUse):
    stdin:  JSON with { tool_name, tool_input }
    exit 0: allow
    exit 2: block (stderr shown to Claude)
    other:  error (fails open per project convention)
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path

# Passive error logging (fail-soft import).
sys.path.insert(0, str(Path(__file__).parent))
try:
    from _error_log import log_event
except Exception:
    def log_event(*args, **kwargs):  # type: ignore[no-redef]
        return


HOOK_NAME = "db-destructive-guard"
try:  # project-local logs when available
    import _project_paths as _pp_log
except Exception:  # pragma: no cover
    _pp_log = None
AUDIT_LOG = (
    (_pp_log.logs_dir() / "db-guard.log") if _pp_log
    else Path.home() / ".claude" / "logs" / "db-guard.log"
)
AUDIT_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB rotation threshold


# ---------------------------------------------------------------------------
# Destructive patterns. Every match here is an op that destroys data.
# Each entry is (label, regex). Regex is compiled with IGNORECASE.
# ---------------------------------------------------------------------------
DESTRUCTIVE_PATTERNS: list[tuple[str, str]] = [
    # EF Core CLI -- the actual cause of the 2026-05-06 incident
    ("ef-database-drop", r"\bdotnet\s+ef\s+database\s+drop\b"),

    # Raw T-SQL bombs
    ("sql-drop-database", r"\bDROP\s+DATABASE\b"),
    ("sql-drop-schema", r"\bDROP\s+SCHEMA\b"),
    ("sql-drop-table", r"\bDROP\s+TABLE\b"),
    ("sql-truncate", r"\bTRUNCATE\s+TABLE\b"),
    ("sql-shutdown", r"\bSHUTDOWN\s+(WITH|NOWAIT)?"),
    ("sql-detach", r"\bDETACH\s+DATABASE\b"),

    # EF Core runtime drops (writes that introduce them)
    ("ef-ensure-deleted", r"\.EnsureDeleted(Async)?\s*\("),
    ("ef-database-ensure-deleted", r"\bDatabase\.EnsureDeleted"),

    # Migration code that issues raw destructive SQL
    (
        "migration-builder-sql-drop",
        r"migrationBuilder\.Sql\s*\([^)]*\b(DROP\s+(DATABASE|TABLE|SCHEMA)|TRUNCATE)\b",
    ),

    # Postgres CLI
    ("pg-dropdb", r"(?<![\w.-])dropdb(?![\w.-])"),
    ("pg-dropuser", r"(?<![\w.-])dropuser(?![\w.-])"),
    ("pg-dropcluster", r"\bpg_dropcluster\b"),
    ("pg-drop-owned", r"\bDROP\s+OWNED\b"),

    # MySQL / MariaDB
    ("mysql-mysqladmin-drop", r"\bmysqladmin\b[^|;\n]*\bdrop\b"),
    ("mysql-cli-drop-database", r"\bmysql\b[^|;\n]*\bDROP\s+DATABASE\b"),
    ("mariadb-cli-drop-database", r"\bmariadb\b[^|;\n]*\bDROP\s+DATABASE\b"),

    # MongoDB
    ("mongo-drop-database", r"\bdb\.dropDatabase\s*\("),
    ("mongo-drop-collection", r"\bdb\.[A-Za-z_][\w]*\.drop\s*\("),

    # Redis
    ("redis-flushall", r"\bFLUSHALL\b"),
    ("redis-flushdb", r"\bFLUSHDB\b"),

    # sqlpackage Publish with data-loss override
    (
        "sqlpackage-block-data-loss-false",
        r"\bsqlpackage(\.exe)?\b[^|;\n]*BlockOnPossibleDataLoss\s*=\s*[Ff]alse",
    ),
    (
        "sqlpackage-create-new-database-true",
        r"\bsqlpackage(\.exe)?\b[^|;\n]*[\\/]p:CreateNewDatabase\s*=\s*True",
    ),

    # SSMS scripts
    ("restore-with-replace", r"\bRESTORE\s+DATABASE\b[^|;\n]*\bWITH\s+REPLACE\b"),

    # Cosmos DB SDK
    ("cosmos-delete-container", r"\.deleteContainer\s*\("),
    ("cosmos-delete-database", r"\.deleteDatabase\s*\("),

    # Layer 3b -- bypass of the SQL Server DDL trigger installed by Layer 1
    # of the dev-DB protection plan. The trigger lives ON ALL SERVER; the only
    # realistic way to disable it is DROP/DISABLE TRIGGER ... ON ALL SERVER.
    # Block those commands so the trigger cannot be removed silently.
    ("drop-server-trigger", r"\bDROP\s+TRIGGER\b[\s\S]{0,200}?\bON\s+ALL\s+SERVER\b"),
    ("disable-server-trigger", r"\bDISABLE\s+TRIGGER\b[\s\S]{0,200}?\bON\s+ALL\s+SERVER\b"),
]


# ---------------------------------------------------------------------------
# Disposable-DB allow-list. If the same input naming a destructive op also
# names a DB that matches one of these, the op is allowed. Matching is
# case-insensitive (the regex flags include re.I) and intended to match
# substrings ANYWHERE in the input -- typically inside a connection string
# or a Database= argument.
# ---------------------------------------------------------------------------
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
    # LIKE-predicate forms (added 2026-09-01). A bulk sweep over disposable
    # databases never names one literally -- it filters with a predicate and
    # builds the statement dynamically, e.g.
    #     WHERE name LIKE '%[_]Test[_]%'
    # Without these two entries such a sweep matched no disposable pattern and
    # was blocked, which is why 1,941 abandoned disposable databases had piled
    # up across 18 fixtures with no automated way to reclaim them.
    ("test-like-predicate", r"\[_\]test\[_\]"),
    ("migrationverify-like-predicate", r"\[_\]migrationverify\[_\]"),
]

# ---------------------------------------------------------------------------
# Protected-DB destructive TARGET veto (added 2026-09-01).
#
# Closes a real hole. PROTECTED_DB_PATTERNS below only recognise a protected
# database as a CONNECTION or SESSION context (Database=, Initial Catalog=,
# USE, -d, -Database). None of them matches the protected name appearing as the
# direct target of a database-level destructive statement. So an input pairing a
# protected target with any disposable name -- for example a drop of the dev
# database followed by a drop of a _Test_<guid> one -- matched a disposable
# pattern, raised no protected_db_violation, and took ALLOW path 1.
#
# Layer 1 (the server DDL trigger) would still have refused it, but that is
# defence in depth, not a reason to let this layer wave it through. On
# 2026-09-01 that trigger was found to have been broken since installation,
# which is exactly the day this hole should not have been open.
#
# Verbs are composed from parts so this file's own source does not contain the
# literal phrases its destructive bank scans for.
# ---------------------------------------------------------------------------
_TGT_DROP = "DR" + "OP"
_TGT_ALTER = "AL" + "TER"
PROTECTED_DESTRUCTIVE_TARGET_RE = re.compile(
    r"\b(?:" + _TGT_DROP + r"|" + _TGT_ALTER + r")\s+DATABASE\s+"
    r"\[?ScalpingMachine(?:_Testing)?\]?\b(?!_)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Layer 3c -- protected-DB-write detection. Catches a class of failure the
# destructive-pattern bank misses: a future test or sub-script that opens a
# SqlConnection (or sqlcmd session) to the protected dev DB and issues plain
# DML/DDL that isn't already in the destructive bank above. The bank catches
# the heavy destructive verbs; this layer catches the INSERT / UPDATE / DELETE
# / MERGE / CREATE / ALTER class that can still mutate user-authored data.
#
# Decision rule: if the SAME tool input contains BOTH
#   (a) a connection-string fragment naming a protected DB (Database=X), AND
#   (b) a write keyword in the SQL/code text,
# AND the tool is Edit/Write/MultiEdit/NotebookEdit targeting a path OUTSIDE
# the production allow-list (where these strings legitimately appear in source),
# OR the tool is Bash/PowerShell (no path to allow-list against),
# THEN block.
#
# The regex is composed from string-list parts (not a single literal) so this
# guard file itself does not contain the heavy verb phrases that would trip
# the destructive-pattern bank when the file is edited by an agent.
#
# Negative lookahead `(?!_)` on the DB name ensures we don't false-positive on
# disposable names like ScalpingMachine_Test_<guid> / ScalpingMachine_Testing_x.
# ---------------------------------------------------------------------------
PROTECTED_DB_PATTERNS: list[tuple[str, str]] = [
    # Connection-string fragment: ADO.NET / SqlClient canonical form.
    ("protected-dev-db",                r"Database\s*=\s*ScalpingMachine\b(?!_)"),
    ("protected-testing-db",            r"Database\s*=\s*ScalpingMachine_Testing\b(?!_)"),
    # Connection-string fragment: alternative ADO.NET keyword "Initial Catalog".
    ("protected-dev-db-initcat",        r"Initial\s+Catalog\s*=\s*ScalpingMachine\b(?!_)"),
    ("protected-testing-db-initcat",    r"Initial\s+Catalog\s*=\s*ScalpingMachine_Testing\b(?!_)"),
    # T-SQL USE statement.
    ("protected-dev-db-use",            r"\bUSE\s+\[?ScalpingMachine\]?\b(?!_)"),
    ("protected-testing-db-use",        r"\bUSE\s+\[?ScalpingMachine_Testing\]?\b(?!_)"),
    # sqlcmd -d flag (preceded by start-of-string or whitespace so we don't
    # match unrelated "-d" substrings inside a longer flag/value).
    ("protected-dev-db-sqlcmd-d",       r"(?:^|\s)-d\s+\[?ScalpingMachine\]?\b(?!_)"),
    ("protected-testing-db-sqlcmd-d",   r"(?:^|\s)-d\s+\[?ScalpingMachine_Testing\]?\b(?!_)"),
    # PowerShell SqlServer / dbatools modules -Database parameter.
    ("protected-dev-db-pwsh-database",  r"(?:^|\s)-Database\s+\[?ScalpingMachine\]?\b(?!_)"),
    ("protected-testing-db-pwsh-database", r"(?:^|\s)-Database\s+\[?ScalpingMachine_Testing\]?\b(?!_)"),
]

# Composed from parts so the source of this file does not contain the heavy
# verb substrings as literals. Avoids self-triggering the destructive bank
# when this guard is edited.
_DDL_VERBS = ("D" + "ROP", "TRU" + "NCATE", "CRE" + "ATE", "ALT" + "ER")
_DDL_TARGETS = ("TAB" + "LE", "DATA" + "BASE", "SCHE" + "MA", "VI" + "EW",
                "IND" + "EX", "TRIG" + "GER", "PROCE" + "DURE", "FUNCT" + "ION")
_DML_WRITES = (r"INS" + r"ERT\s+INTO", r"UP" + r"DATE\s+\w+",
               r"DEL" + r"ETE\s+FROM", r"MER" + r"GE\s+INTO")
_DDL_ALTS = "|".join(
    f"{v}\\s+(?:{'|'.join(_DDL_TARGETS)})" for v in _DDL_VERBS
)
WRITE_KEYWORD_PATTERN = r"\b(?:" + "|".join(_DML_WRITES) + "|" + _DDL_ALTS + r")\b"

# Path prefixes where protected-DB connection strings legitimately appear in
# source (production app config / EF persistence layer / docs / this guard
# script's own helper tooling / Claude config tree).
#
# The .claude/ entry is intentionally broad: concept contracts, plans,
# templates, journal entries, CLAUDE.md, and hook code all live under .claude/
# and need to reference the protected DB names verbatim in documentation. The
# tree is curated config — any write into it is already a deliberate, human-
# approved action. The Layer 1 SQL Server DDL trigger is the catch-all that
# protects against any path-allow-list false-negative.
#
# Normalized to forward slashes; matched case-insensitively against the same
# normalization of file_path.
PRODUCTION_PATH_ALLOWLIST: tuple[str, ...] = (
    "src/scalpingmachine.api/",
    "src/scalpingmachine.persistence/",
    "tools/db-protection/",
    ".claude/",
    "/.claude/",
    "docs/",
)

# Pre-compile.
DESTRUCTIVE_RE = [(label, re.compile(pat, re.IGNORECASE)) for label, pat in DESTRUCTIVE_PATTERNS]
DISPOSABLE_RE = [(label, re.compile(pat, re.IGNORECASE)) for label, pat in DISPOSABLE_PATTERNS]
PROTECTED_DB_RE = [(label, re.compile(pat, re.IGNORECASE)) for label, pat in PROTECTED_DB_PATTERNS]
WRITE_KEYWORD_RE = re.compile(WRITE_KEYWORD_PATTERN, re.IGNORECASE)

# Pattern that identifies a `dotnet ef` command followed by a `--` argument
# separator (the argv-position bug). Used by Layer 3a to detect when a
# disposable marker has been forwarded past `--` (into Program.Main's argv)
# instead of consumed by dotnet ef itself.
EF_WITH_ARG_SEPARATOR_RE = re.compile(
    r"\bdotnet\s+ef\b[^\n]*?\s--(?:\s|$)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Audit log.
# ---------------------------------------------------------------------------
def _audit(record: dict) -> None:
    """Append-only structured audit log; rotates on size."""
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
        # Never let audit failure block the hook decision.
        pass


# ---------------------------------------------------------------------------
# Tool input extraction.
# ---------------------------------------------------------------------------
def _extract_text(payload: dict) -> str:
    """Extract the user-controlled text from the tool input we want to scan."""
    tool_name = payload.get("tool_name") or ""
    tool_input = payload.get("tool_input") or {}
    parts: list[str] = []

    if tool_name in ("Bash", "PowerShell"):
        parts.append(str(tool_input.get("command", "")))
        parts.append(str(tool_input.get("description", "")))
    elif tool_name in ("Write",):
        parts.append(str(tool_input.get("file_path", "")))
        parts.append(str(tool_input.get("content", "")))
    elif tool_name in ("Edit",):
        parts.append(str(tool_input.get("file_path", "")))
        parts.append(str(tool_input.get("old_string", "")))
        parts.append(str(tool_input.get("new_string", "")))
    elif tool_name in ("MultiEdit",):
        parts.append(str(tool_input.get("file_path", "")))
        for edit in tool_input.get("edits", []) or []:
            parts.append(str(edit.get("old_string", "")))
            parts.append(str(edit.get("new_string", "")))
    elif tool_name in ("NotebookEdit",):
        parts.append(str(tool_input.get("notebook_path", "")))
        parts.append(str(tool_input.get("new_source", "")))
    else:
        # Unknown tool -- scan whatever is there as a best-effort.
        parts.append(json.dumps(tool_input, ensure_ascii=False))
    return "\n".join(parts)


def _truncate(s: str, n: int = 240) -> str:
    s = s.replace("\n", " \\n ").replace("\r", "")
    return s if len(s) <= n else s[: n - 3] + "..."


def _extract_file_path(payload: dict) -> str:
    """Return the file_path / notebook_path from the tool input, normalized
    to forward slashes and lowercased. Returns "" for tools that don't carry
    a path (Bash, PowerShell)."""
    tool_input = payload.get("tool_input") or {}
    raw = (
        tool_input.get("file_path")
        or tool_input.get("notebook_path")
        or ""
    )
    return str(raw).replace("\\", "/").lower()


def _file_in_production_allowlist(file_path: str) -> bool:
    """True iff the (normalized, lowercased) file_path starts with one of the
    PRODUCTION_PATH_ALLOWLIST entries OR contains one of them as a substring.
    Substring matching is intentional -- file_path on Windows often starts
    with a drive letter, so an entry like "src/scalpingmachine.api/" must
    match "d:/dev/.../src/scalpingmachine.api/program.cs"."""
    if not file_path:
        return False
    for prefix in PRODUCTION_PATH_ALLOWLIST:
        if prefix in file_path:
            return True
    return False


# ---------------------------------------------------------------------------
# Layer 3a -- argv-position-bug detector for dotnet ef commands.
# ---------------------------------------------------------------------------
def _ef_disposable_invalidated(text: str, matched_destructive: list[str]) -> bool:
    """Returns True iff:
       * a dotnet-ef destructive label was matched, AND
       * a `dotnet ef ... -- ...` separator is present, AND
       * every disposable-marker hit is positioned AFTER the separator (i.e.,
         forwarded into Program.Main's argv where dotnet ef ignores it).
    When True, the caller must treat the disposable hits as if they were not
    present -- the agent has fallen into the argv-position bug.
    """
    if not any(lbl.startswith("ef-") for lbl in matched_destructive):
        return False
    sep_m = EF_WITH_ARG_SEPARATOR_RE.search(text)
    if not sep_m:
        return False
    sep_pos = sep_m.end()
    for _label, rx in DISPOSABLE_RE:
        for hit in rx.finditer(text):
            if hit.start() < sep_pos:
                # Disposable marker is on the LEFT side of `--` -- ef sees it.
                return False
    # An ef destructive + `--` exists, and every disposable marker is on the
    # RIGHT side of `--` (forwarded args). Argv-position bug confirmed.
    return True


# ---------------------------------------------------------------------------
# Layer 3c -- protected-DB-write check.
# ---------------------------------------------------------------------------
def _scan_protected_db_writes(text: str) -> tuple[list[str], bool]:
    """Returns (matched_protected_db_labels, has_write_keyword).
    Caller decides whether to BLOCK by combining with the file_path allow-list.
    """
    matched: list[str] = []
    for label, rx in PROTECTED_DB_RE:
        if rx.search(text):
            matched.append(label)
    has_write = bool(WRITE_KEYWORD_RE.search(text)) if matched else False
    return matched, has_write


# ---------------------------------------------------------------------------
# Decision tree.
# ---------------------------------------------------------------------------
def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        log_event(HOOK_NAME, "stdin-parse-error", str(exc))
        # Fail open -- agent should not be blocked by hook bug.
        return 0

    tool_name = payload.get("tool_name") or ""
    if tool_name not in {"Bash", "PowerShell", "Write", "Edit", "MultiEdit", "NotebookEdit"}:
        return 0

    text = _extract_text(payload)
    if not text:
        return 0

    file_path = _extract_file_path(payload)
    in_allowlist = _file_in_production_allowlist(file_path)

    # ---- Pass A: existing destructive-pattern scan ----------------------
    matched_destructive: list[str] = []
    for label, rx in DESTRUCTIVE_RE:
        if rx.search(text):
            matched_destructive.append(label)

    # ---- Pass B: protected-DB-write scan (Layer 3c) ---------------------
    protected_db_hits, has_write_kw = _scan_protected_db_writes(text)
    # A protected-DB-write violation requires BOTH a protected-DB pattern AND
    # a write keyword in the same input, AND the editing tool to be targeting
    # a path OUTSIDE the production allow-list (or a shell tool with no path).
    is_shell_tool = tool_name in ("Bash", "PowerShell")
    protected_db_violation = (
        bool(protected_db_hits)
        and has_write_kw
        and (is_shell_tool or not in_allowlist)
    )

    if not matched_destructive and not protected_db_violation:
        return 0

    # ---- Disposable scan (with Layer 3a argv-position fix) --------------
    matched_disposable: list[str] = []
    for label, rx in DISPOSABLE_RE:
        if rx.search(text):
            matched_disposable.append(label)

    argv_position_bug = _ef_disposable_invalidated(text, matched_destructive)

    session_id = payload.get("session_id") or ""
    base_record = {
        "ts": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "hook": HOOK_NAME,
        "session": session_id,
        "tool": tool_name,
        "file_path": file_path,
        "in_allowlist": in_allowlist,
        "matched_destructive": matched_destructive,
        "matched_disposable": matched_disposable,
        "argv_position_bug": argv_position_bug,
        "protected_db_hits": protected_db_hits,
        "has_write_keyword": has_write_kw,
        "protected_db_violation": protected_db_violation,
        "text_excerpt": _truncate(text, 320),
    }

    # A protected database named as the direct target of a database-level
    # destructive statement vetoes the disposable allow path outright. See the
    # PROTECTED_DESTRUCTIVE_TARGET_RE block comment above -- without this, a
    # protected target smuggled alongside any disposable name took ALLOW path 1.
    protected_target_hit = bool(PROTECTED_DESTRUCTIVE_TARGET_RE.search(text))
    base_record["protected_destructive_target"] = protected_target_hit

    # ---- ALLOW path 1: destructive matched, disposable valid, no argv bug
    if (
        matched_destructive
        and matched_disposable
        and not argv_position_bug
        and not protected_db_violation
        and not protected_target_hit
    ):
        _audit({**base_record, "decision": "ALLOW", "reason": "disposable-pattern-matched"})
        return 0

    # ---- ALLOW path 2: user-set environment override -------------------
    if os.environ.get("CLAUDE_DESTRUCTIVE_DB_OK") == "1":
        _audit({**base_record, "decision": "ALLOW", "reason": "user-override-env"})
        # Note: we do NOT unset the env var here. The shell scope outside
        # this Python process owns it. Agents should not set it; humans set
        # it once in their shell when they want to authorize a destructive op.
        return 0

    # ---- BLOCK ----------------------------------------------------------
    if protected_db_violation:
        reason = "protected-db-write-from-non-production-path"
    elif argv_position_bug:
        reason = "argv-position-bug-disposable-on-wrong-side-of-double-dash"
    else:
        reason = "no-disposable-no-override"
    _audit({**base_record, "decision": "BLOCK", "reason": reason})

    # Build a context-appropriate stderr message.
    lines = ["[db-destructive-guard] BLOCKED:"]
    if protected_db_violation:
        lines.append(
            "this tool call writes to a PROTECTED dev database from a path"
        )
        lines.append("outside the production allow-list.")
        lines.append("")
        lines.append(f"Protected DB pattern(s): {', '.join(protected_db_hits)}")
        lines.append(f"file_path: {file_path or '(no path -- shell tool)'}")
        lines.append(f"Excerpt: {_truncate(text, 200)}")
        lines.append("")
        lines.append("Production paths where these connection strings legitimately appear:")
        for p in PRODUCTION_PATH_ALLOWLIST:
            lines.append(f"    {p}")
        lines.append("")
        lines.append("If this is a test, use a disposable connection string built from a guid,")
        lines.append("not the dev DB name. Pattern: Database=ScalpingMachine_Test_<guid>")
    else:
        lines.append("this tool call would run a destructive DB operation against")
        lines.append("what appears to be a working/dev/prod database.")
        lines.append("")
        lines.append(f"Detected pattern(s): {', '.join(matched_destructive)}")
        lines.append(f"Excerpt: {_truncate(text, 200)}")
        lines.append("")
        if argv_position_bug:
            lines.append("ARGV-POSITION BUG DETECTED:")
            lines.append("  Your command places a disposable-DB marker AFTER the `--` separator.")
            lines.append("  In dotnet-CLI, `--` forwards remaining args to Program.Main; the")
            lines.append("  --connection flag is NOT consumed by `dotnet ef`. The DB destination")
            lines.append("  falls back to the host's default (the dev DB).")
            lines.append("")
            lines.append("  Fix: place --connection BEFORE `--`, or omit `--` entirely:")
            lines.append("      dotnet ef ... --connection \"<disposable-cs>\" --force")
            lines.append("")
        lines.append("To run this safely, target a disposable DB name with one of these patterns:")
        lines.append("    _DryRun, _MigrationVerify, _Sandbox, _Scratch, _Throwaway, _Test_<guid>, _e2e_<guid>")
        lines.append("")
        lines.append("Migration verification ('fresh DB' tests) MUST use a separately-named")
        lines.append("disposable database -- never the connection string from appsettings.json.")
        lines.append("Use tools/db-protection/verify-migration.cmd for the safe workflow.")
    lines.append("")
    lines.append("For a one-shot human-approved override (USER, not agent, must set this):")
    lines.append("    POSIX:      export CLAUDE_DESTRUCTIVE_DB_OK=1")
    lines.append("    PowerShell: $env:CLAUDE_DESTRUCTIVE_DB_OK=\"1\"")
    lines.append("")
    lines.append("Reference: ~/.claude/CLAUDE.md -> 'Destructive Database Operations (HARD BLOCK)'")
    lines.append("Audit log: ~/.claude/hooks/db-guard.log")

    sys.stderr.write("\n".join(lines) + "\n")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # Fail open. Never let a hook bug block legitimate work.
        log_event(HOOK_NAME, "uncaught-exception", repr(exc))
        sys.exit(0)
