#!/usr/bin/env python3
"""
db-destructive-guard.py -- PreToolUse hook that hard-blocks destructive
database operations against working / dev / production connection strings.

WHY THIS EXISTS
---------------
On 2026-05-06 a Claude sub-agent in a parallel session ran the EF Core tool's
forced drop-the-database command to "test the migration on a fresh
LocalDB," following a project rule literally. The connection string in
`appsettings.json` pointed at the working dev DB, so the drop wiped a real user
account and all of that user's data. The rule did not specify that "freshly-deleted LocalDB" must be a SEPARATE,
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

#: Round 3 task D: bound at import time via ``getattr`` (see concept-gate.py's
#: identical comment). A missing function is treated EXACTLY like ``_pp_log``
#: being ``None`` everywhere below, including the fallback-mode banner text.
_pp_checkout_equivalent_path = (
    getattr(_pp_log, "checkout_equivalent_path", None) if _pp_log is not None else None
)

AUDIT_LOG = (
    (_pp_log.logs_dir() / "db-guard.log") if _pp_log
    else Path.home() / ".claude" / "logs" / "db-guard.log"
)
AUDIT_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB rotation threshold

#: The full path this hook's copy of ``_project_paths.py`` would live at, used
#: only to name the missing helper in a fallback-mode block banner (INV-5).
_PROJECT_PATHS_EXPECTED_PATH = str(Path(__file__).resolve().parent / "_project_paths.py")

# Verb fragments for the dev-DB protection hardening patterns (contract
# 2026-10-04). Composed from parts, like the older constants further down, so
# this file never contains the literal phrases its own pattern bank screens for.
_V_DROP = "DR" + "OP"
_V_ALTER = "AL" + "TER"
_V_REMOVE = "re" + "move"
_V_DELETE = "de" + "lete"
_V_DROP_LC = "dr" + "op"
_V_PG_REMOVER = "dr" + "opdb"
# The SqlServer module's and the dbatools module's restore cmdlets, composed from parts.
_PS_RESTORE_CMDLET = r"(?<![\w-])(?:" + "Rest" + "ore-SqlDatabase|" + "Rest" + r"ore-DbaDatabase)(?![\w-])"
_DB_STATE = r"(?:OFFLINE|SINGLE_USER|RESTRICTED_USER|EMERGENCY)"
# One database-name token: bracketed, double-quoted, or a bare word.
#: A bare name stops at the start of a SQL comment (a block comment glued to the name).
_NAME_TOKEN = r"(?:\[[^\]\r\n]*\]|\"[^\"\r\n]*\"|(?:(?!/\*|--)[^\s;,)])+)"
# A quoted string or any character that cannot end a shell command.
_NOT_END = r"(?:[^|;\n\"']|\"[^\"]*\"|'[^']*')*"
# A database-name token that cannot swallow a closing quote (bracketed, quoted or bare).
_NAME_TOKEN_Q = r"(?:\[[^\]\r\n]*\]|\"[^\"\r\n]*\"|(?:(?!/\*|--)[^\s;,)\"'])+)"
# White space, a block comment or a line comment: all of them are white space to SQL Server.
_SQL_WS = r"(?:\s|/\*[\s\S]*?\*/|--[^\n]*)"
# What may follow the database name of a real restore statement (keeps prose out): a clause
# keyword (FROM, WITH, FILE =, FILEGROUP =, PAGE =, READ_WRITE_FILEGROUPS) after any white
# space or comment, or the end of the statement.
_RESTORE_END = (
    rf"(?={_SQL_WS}+(?:(?:FROM|WITH|READ_WRITE_FILEGROUPS)\b|(?:FILE|FILEGROUP|PAGE)\s*=)"
    r"|\s*(?:;|$|[\"']))"
)
# Every spelling of the EF command-line tool (class C): the dotnet host with or without
# .exe, the standalone tool with or without .exe, and the tool-run form, with or without
# a path in front. A closing quote after the executable is part of the match, so a quoted
# host path (a PowerShell call operator, or a quoted path in a shell) is found too.
_EF_TOOL = (
    r"(?<![\w.-])(?:dotnet(?:\.exe)?[\"']?\s+(?:tool\s+run\s+)?dotnet-ef(?:\.exe)?"
    r"|dotnet(?:\.exe)?[\"']?\s+ef|dotnet-ef(?:\.exe)?)[\"']?(?![\w.-])"
)
_EF_TOOL_RE = re.compile(_EF_TOOL, re.IGNORECASE)
#: EF options that take a value; one of these before the noun and verb must not hide them.
_EF_VALUE_FLAG_NAMES = (
    "--project", "-p", "--startup-project", "-s", "--framework", "--configuration",
    "--runtime", "--launch-profile", "--msbuildprojectextensionspath", "--context", "-c",
    "--output-dir", "-o", "--namespace", "-n",
)
_EF_VALUE_FLAG_ALT = "|".join(re.escape(f) for f in sorted(_EF_VALUE_FLAG_NAMES, key=len, reverse=True))
#: Zero or more EF option tokens between the tool and the noun: a value option with its
#: value, or a bare option (`-v`, `--no-color`). A bare `--` is not an option.
_EF_PRE = (
    rf"(?:\s+(?:(?:{_EF_VALUE_FLAG_ALT})(?:\s+|=)(?:\"[^\"]*\"|'[^']*'|[^\s\"']+)|--?[^\s-]\S*))*"
)

#: Case-insensitive via the flag, never a ``.lower()`` copy (see
#: concept-gate.py's identical comment). The optional trailing group after
#: ``worktrees`` folds the Windows aliases the helper recognises (round 3
#: task F).
_FALLBACK_WORKTREE_MARKER_RE = re.compile(
    r"/\.claude/worktrees(?:[.\ ]*|:[^/]*)/[^/]+", re.IGNORECASE
)


def _fallback_checkout_equivalent(path_str: str) -> str:
    """INV-5 fallback: crude stand-in for ``_project_paths.checkout_equivalent_path``.

    Used ONLY when ``import _project_paths`` failed. Strips the segment
    test's input down to the text after the LAST worktree-segment marker, so
    worktree source still gets no bypass while the helper is missing. A path
    with no marker is returned unchanged (today's behaviour).

    "." components are dropped BEFORE doubled separators are collapsed (round
    3 task E) -- see concept-gate.py's identical comment.
    """
    norm = path_str.replace("\\", "/")
    no_dots = re.sub(r"(^|/)\.(?=/|$)", r"\1", norm)
    collapsed = re.sub(r"/{2,}", "/", no_dots)
    matches = list(_FALLBACK_WORKTREE_MARKER_RE.finditer(collapsed))
    if not matches:
        return norm
    return collapsed[matches[-1].end():]


def _segment_test_path(path_str: str) -> str:
    """The text this guard's allow-list substring test should read (INV-2)."""
    if _pp_checkout_equivalent_path is not None:
        return _pp_checkout_equivalent_path(path_str)
    return _fallback_checkout_equivalent(path_str)


# ---------------------------------------------------------------------------
# Destructive patterns. Every match here is an op that destroys data.
# Each entry is (label, regex). Regex is compiled with IGNORECASE.
# ---------------------------------------------------------------------------
DESTRUCTIVE_PATTERNS: list[tuple[str, str]] = [
    # EF Core CLI -- the actual cause of the 2026-05-06 incident
    ("ef-database-drop", _EF_TOOL + _EF_PRE + r"\s+database\s+drop\b"),

    # Raw T-SQL bombs
    ("sql-drop-database", r"\bDROP\s+DATABASE\b"),
    ("sql-drop-schema", r"\bDROP\s+SCHEMA\b"),
    ("sql-drop-table", r"\bDROP\s+TABLE\b"),
    ("sql-truncate", r"\bTRUNCATE\s+TABLE\b"),
    # Issue #272: the server-stop keyword. One label, three alternatives, so a
    # command or prose that merely mentions the keyword is not blocked. The
    # old rule blocked the keyword whenever whitespace followed it, which
    # blocked `dotnet build-server` stops, greps and prose.
    #
    # P1 (statement position, uppercase only) catches the keyword when it
    # starts a statement (line start, after `;` or `(`, or after BEGIN or
    # ELSE) and ends one (line end, `\r`, `;`, a quote, `)`, a `--` or `/*`
    # comment, GO or END). THEN is not in the left anchor because it does not
    # introduce a T-SQL statement. The left anchor deliberately has no quote
    # characters: quotes there made quoted literals, such as grep arguments
    # and commit messages, block. `\r` is accepted as a statement end so
    # Windows line endings still match. P1 is case-sensitive (the inline
    # `(?-i:...)` group): an Edit whose old_string is the lowercase identifier
    # sits alone on its own line of the scanned text, which is the same shape
    # as a bare statement, and that rename must be allowed.
    #
    # P2 (SQL-client context, case-insensitive) catches the keyword as a
    # standalone token anywhere, but only when the same scanned text also
    # names a SQL client or API: sqlcmd, osql, isql, mssql-cli, usql,
    # mysqladmin, mysql, Invoke-DbaQuery, SqlCommand, ExecuteSql*, a
    # `.execute*(` call, or a `.sql` path. Some clients are covered by the
    # broader markers rather than listed: Invoke-Sqlcmd by `sqlcmd`,
    # ExecuteNonQuery by `.execute*(`, and migrationBuilder.Sql by `.sql`.
    # P2 depends on a client list, so it is incomplete by nature.
    #
    # P3 (unconditional, case-insensitive) catches the keyword followed by
    # WITH NOWAIT anywhere, in any case, through any client. It only matches
    # text the old rule matched, so it adds no false positive against it. It
    # exists because P2's list can never name every client. P3 makes a
    # WITH NOWAIT group inside P1 redundant, so P1 has none.
    #
    # Known limits, each a gap or a false block that this rule accepts:
    # - a bare keyword (no WITH NOWAIT) sent through a client not on P2's
    #   list is not caught;
    # - a statement with no separator before it, outside a SQL context (a
    #   SELECT followed by the keyword on one line), is not caught;
    # - IF or TRY before the keyword, outside a SQL context, is not caught;
    # - whitespace other than space or tab around P1's keyword (for example a
    #   form feed or vertical tab) defeats P1;
    # - a lowercase bare keyword alone in a non-SQL file is not caught;
    # - a keyword built by string concatenation is not caught;
    # - a grep of a `.sql` file for the keyword blocks;
    # - a prose sentence that mentions the keyword alongside a client name
    #   blocks.
    ("sql-shutdown",
     r"""(?m)(?-i:(?:^|[;(]|\bBEGIN\b|\bELSE\b)[ \t]*SHUTDOWN[ \t]*(?:$|\r|[;"')]|--|/\*|\bGO\b|\bEND\b))"""
     r"""|\A(?=[\s\S]*?(?:\b(?:sqlcmd|osql|isql|mssql-cli|usql|mysqladmin|mysql|Invoke-DbaQuery|SqlCommand|ExecuteSql\w*)\b|\.execute\w*\(|\.sql\b))[\s\S]*?(?<![-\w.$])SHUTDOWN\b(?![-\w.(])"""
     r"""|\bSHUTDOWN\s+WITH\s+NOWAIT\b"""),
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
        # A quoted connection string may hold a ';', so quoted spans are skipped
        # whole instead of ending the command at the first ';' (class G1).
        r"\bsqlpackage(\.exe)?\b" + _NOT_END + r"BlockOnPossibleDataLoss\s*=\s*[Ff]alse",
    ),
    (
        "sqlpackage-create-new-database-true",
        r"\bsqlpackage(\.exe)?\b" + _NOT_END + r"[\\/]p:CreateNewDatabase\s*=\s*True",
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

    # Dev-DB protection hardening (contract 2026-10-04). Patterns that need a
    # parsed argument list (EF rollback target, data-file deletion, human-only
    # scripts) are NOT here: _dynamic_labels() adds their labels.
    #  - class A: a database taken offline / single-user / restricted / emergency
    ("sql-alter-database-restrict",
     rf"\b{_V_ALTER}\s+DATABASE\s+{_NAME_TOKEN}\s+SET\s+{_DB_STATE}\b"),
    #  - class C: removing a migration
    ("ef-migrations-remove", _EF_TOOL + _EF_PRE + rf"\s+migrations\s+{_V_REMOVE}\b"),
    #  - class A: every restore onto a database (not only the replace form) and a rename
    ("sql-restore-database",
     rf"\bRESTORE\s+DATABASE\s+(?!(?:FROM|WITH)\b){_NAME_TOKEN_Q}{_RESTORE_END}"),
    ("sql-rename-database",
     rf"\b{_V_ALTER}\s+DATABASE\s+{_NAME_TOKEN_Q}\s+MODIFY\s+NAME\s*=\s*{_NAME_TOKEN_Q}"),
    #  - class D: deleting a LocalDB instance, long or short verb, any spelling of the exe
    ("sqllocaldb-delete", rf"(?<![\w-])sqllocaldb(?:\.exe)?[\"']?\s+(?:{_V_DELETE}|d)\b"),
    #  - class A: the SqlServer and dbatools PowerShell restore cmdlets (target read from -Database)
    ("ps-restore-database-cmdlet", _PS_RESTORE_CMDLET),
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


# ---------------------------------------------------------------------------
# Per-project settings, loaded from the rules file beside this hook.
#
# The hook is generic. Every name of this project's own databases and source
# folders lives in db-destructive-guard.rules.json, the same shape as
# architecture-guard.rules.json and plain-language-guard.rules.json.
#
# THE LOADER FAILS CLOSED. If the rules file is missing, unreadable or empty,
# the guard does not fall back to permitting anything: it treats EVERY database
# as protected and narrows the production path allow-list to the two entries
# that name no project. A guard that fails open when its configuration
# disappears is worse than one that never moved -- and this guard is the last
# layer between an agent and a database that has already been destroyed twice.
# ---------------------------------------------------------------------------
#
# THE RULES FILE IS THE PROJECT'S, NEVER THE PLUGIN'S (INV-O3). This hook runs from the plugin,
# so the file beside it is only a template naming fictional databases. The rules are read from
# <CLAUDE_PROJECT_DIR>/.claude/hooks/ and nowhere else; an unset CLAUDE_PROJECT_DIR reads nothing.
# Both cases take the fail-closed path above.
_RULES_FILE_NAME = "db-destructive-guard.rules.json"


def _project_rules_path() -> Path | None:
    raw = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if not raw:
        return None
    return Path(raw) / ".claude" / "hooks" / _RULES_FILE_NAME


_RULES_PATH = _project_rules_path() or Path(_RULES_FILE_NAME)


def _load_guard_rules() -> dict:
    project_path = _project_rules_path()
    if project_path is None:
        return {}
    try:
        with project_path.open(encoding="utf-8") as _f:
            data = json.load(_f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


_RULES = _load_guard_rules()

#: Rules-file keys whose value has the wrong type. A wrong type never widens an
#: allow-list and never disables protection: it narrows to the strict default and
#: the key is named in every block banner (contract rev. 3).
_RULE_PROBLEMS: list[str] = []


def _is_str_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


def _protected_names_from_rules() -> list[str]:
    raw = _RULES.get("protected_databases")
    if raw is None:
        return []
    if not _is_str_list(raw):
        # Wrong type: treat as "no configuration", which protects EVERY database.
        _RULE_PROBLEMS.append("protected_databases")
        return []
    return [n for n in raw if n.strip()]


#: No database name is built into this hook: the names are a project fact and come from the
#: project's rules file. A project without one is protected the strict way (every database).
_BUILTIN_PROTECTED_DATABASES: tuple[str, ...] = ()

_RULES_PROTECTED_NAMES = _protected_names_from_rules()


def _merge_protected_names(extra: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for n in (*_BUILTIN_PROTECTED_DATABASES, *extra):
        if n.lower() not in seen:
            seen.add(n.lower())
            merged.append(n)
    return merged


# Longest name first, so an alternation never settles on a shorter prefix.
PROTECTED_DATABASES: tuple[str, ...] = tuple(
    sorted(_merge_protected_names(_RULES_PROTECTED_NAMES), key=len, reverse=True)
)
#: True only when the rules file itself supplied a usable list. With no usable list the
#: guard still treats EVERY database as protected (fail closed), on top of the built-in names.
RULES_LOADED = bool(_RULES_PROTECTED_NAMES)

if RULES_LOADED:
    _PROTECTED_NAME_ALT = (
        r"\[?(?:" + "|".join(re.escape(n) for n in PROTECTED_DATABASES) + r")\]?\b(?!_)"
    )
else:
    # No configuration: every database name is protected. Only the generic
    # disposable-suffix escape below can still allow an operation through.
    _PROTECTED_NAME_ALT = r"\[?\w+\]?\b(?!_)"

PROTECTED_DESTRUCTIVE_TARGET_RE = re.compile(
    r"\b(?:" + _TGT_DROP + r"|" + _TGT_ALTER + r"|RESTORE)\s+DATABASE\s+"
    + _PROTECTED_NAME_ALT,
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
# disposable names like <ProtectedName>_Test_<guid> / <ProtectedName>_Testing_x.
# ---------------------------------------------------------------------------
def _protected_db_patterns() -> list[tuple[str, str]]:
    """
    One set of five surface patterns per protected database name, built from the
    rules file rather than written out per name. Adding a database to the rules
    file therefore covers every surface at once, instead of needing five more
    hand-written lines that a later reader can silently leave incomplete.

    With no rules file, the name part becomes a bare word match, so every
    database is treated as protected -- see the fail-closed note above.
    """
    if RULES_LOADED:
        named = [(re.sub(r"\W+", "-", n).strip("-").lower(), re.escape(n)) for n in PROTECTED_DATABASES]
    else:
        named = [("unconfigured-any-db", r"\w+")]

    patterns: list[tuple[str, str]] = []
    for label, name in named:
        patterns.extend([
            # Connection-string fragment: ADO.NET / SqlClient canonical form.
            # A quote before the value is allowed (a quoted value is read like a bare one).
            (f"protected-{label}",                 rf"Database\s*=\s*[\"']?{name}\b(?!_)"),
            # Connection-string fragment: alternative ADO.NET keyword "Initial Catalog".
            (f"protected-{label}-initcat",         rf"Initial\s+Catalog\s*=\s*[\"']?{name}\b(?!_)"),
            # T-SQL USE statement.
            (f"protected-{label}-use",             rf"\bUSE\s+\[?{name}\]?\b(?!_)"),
            # sqlcmd -d flag (preceded by start-of-string or whitespace so we
            # don't match unrelated "-d" substrings inside a longer flag/value).
            (f"protected-{label}-sqlcmd-d",        rf"(?:^|\s)-d\s+\[?{name}\]?\b(?!_)"),
            # PowerShell SqlServer / dbatools modules -Database parameter.
            (f"protected-{label}-pwsh-database",   rf"(?:^|\s)-Database\s+\[?{name}\]?\b(?!_)"),
        ])
    return patterns


PROTECTED_DB_PATTERNS: list[tuple[str, str]] = _protected_db_patterns()

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
# Every worktree segment (.claude/worktrees/<name>/) is removed from the
# file_path before this list is matched (issue #222) -- so this entry still
# exempts a worktree's OWN .claude/ file, but no longer exempts worktree
# SOURCE, which is judged exactly like the same file in the main checkout.
#
# Normalized to forward slashes; matched case-insensitively against the same
# normalization of file_path.
# Read from the rules file. With no rules file the list narrows to the two
# entries that name no project, which is the strict direction: fewer paths are
# allowed to carry a protected-database connection string, never more.
_DEFAULT_PATH_ALLOWLIST = [".claude/", "/.claude/"]


def _allowlist_from_rules() -> list[str]:
    raw = _RULES.get("production_path_allowlist")
    if raw is None:
        return list(_DEFAULT_PATH_ALLOWLIST)
    if not _is_str_list(raw):
        # Wrong type: narrow to the built-in defaults, never widen.
        _RULE_PROBLEMS.append("production_path_allowlist")
        return list(_DEFAULT_PATH_ALLOWLIST)
    return raw or list(_DEFAULT_PATH_ALLOWLIST)


PRODUCTION_PATH_ALLOWLIST: tuple[str, ...] = tuple(
    p.strip().lower() for p in _allowlist_from_rules() if p.strip()
)


def _rules_problem_lines() -> list[str]:
    """Banner lines naming every rules-file key that had the wrong type."""
    if not _RULE_PROBLEMS:
        return []
    return [
        "",
        f"NOTE: the rules file has a value of the wrong type for: {', '.join(_RULE_PROBLEMS)}.",
        "The guard failed closed for that key (strict default, never a wider one).",
        f"Fix the value in {_RULES_PATH.name}.",
    ]

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
    _EF_TOOL + r"[^\n]*?\s--(?:\s|$)",
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
        # The human-written description is prose that is never executed: it is not scanned
        # (a description that merely names a guarded command must not block, item 7a).
        parts.append(str(tool_input.get("command", "")))
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
    with a drive letter, so an entry like "src/<backend-project>/" must
    match "d:/dev/.../src/<backend-project>/program.cs"."""
    if not file_path:
        return False
    # INV-2: the substring test reads the checkout-equivalent path (every
    # worktree segment removed) of the already-normalised file_path.
    #
    # Fail CLOSED on any exception (round 3 task D): this function feeds
    # `in_allowlist`, which only ever WIDENS what main() allows -- an
    # exception here must never be allowed to propagate up to main()'s
    # bare `except Exception` (which fails OPEN, exit 0, skipping the
    # destructive-command scan entirely). Returning False keeps the scan
    # running as if the target were NOT in the allow-list.
    try:
        checkout_equivalent = _segment_test_path(file_path)
    except Exception:  # noqa: BLE001
        return False
    for prefix in PRODUCTION_PATH_ALLOWLIST:
        if prefix in checkout_equivalent:
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
# Destructive-target binding (contract 2026-10-04-dev-db-protection-hardening).
#
# A disposable-name suffix exempts a destructive operation ONLY when it sits on
# that operation's own target. Each matched label belongs to one class; the
# class reader returns Destructive Targets {class, kind, name, classification}.
# The operation is allowed only when EVERY target is "disposable" (or "marker",
# the narrowed legacy rule of class G2). Anything the reader cannot read is
# "unresolved" and blocks. A marker anywhere else (a comment, an echo, a second
# statement) exempts nothing.
#
#   A  database statement   name after the DATABASE keyword, every statement
#   A' predicate sweep      the LIKE predicate (disposable form, no protected name)
#   B  table statement      the session database; none named = unresolved
#   C  EF command           Database= inside --connection, before any `--`;
#                           none = the configured database = protected
#   D  LocalDB instance     the instance name
#   E  data file            the file stem; wildcards and folders never pass
#   F  server scope         never exempt (only the human override)
#   G1 other engines        the named database, bound like A
#   G2 untargeted           a marker AND no protected name in a name position
#   H  human-only           never by an agent (shell tools only)
# ---------------------------------------------------------------------------
_READABLE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.$#-]*$")
_DB_KEY_RE = re.compile(r"\b(?:Initial\s+Catalog|Database)\s*=\s*", re.IGNORECASE)
_DB_BARE_VALUE_RE = re.compile(r"[^;\"'\s\]]+")


def _db_literals(text: str) -> list[str]:
    """EVERY database a connection string names (Database= and Initial Catalog=), in order.

    A value may be bare, single-quoted or double-quoted: the quotes are removed. A value
    that opens a quote it never closes (or has no value at all) is returned as "" so the
    caller classifies it as unreadable (unresolved), never as a name.
    """
    out: list[str] = []
    for m in _DB_KEY_RE.finditer(text):
        i = m.end()
        if i < len(text) and text[i] in "\"'":
            j = text.find(text[i], i + 1)
            out.append("" if j == -1 else text[i + 1:j])
        else:
            v = _DB_BARE_VALUE_RE.match(text, i)
            out.append(v.group(0) if v else "")
    return out
_LIKE_RE = re.compile(r"\bLIKE\s+N?'((?:[^']|'')*)'", re.IGNORECASE)
_LIKE_DISPOSABLE_RES = [
    rx for lbl, rx in DISPOSABLE_RE if lbl in ("test-like-predicate", "migrationverify-like-predicate")
]
_PROTECTED_ANYWHERE_RE = (
    re.compile(
        r"(?<![A-Za-z0-9_./\\-])(?:" + "|".join(re.escape(n) for n in PROTECTED_DATABASES)
        + r")(?![A-Za-z0-9_.-])",
        re.IGNORECASE,
    )
    if RULES_LOADED else None
)

_A_RES = (
    re.compile(rf"\b{_V_DROP}\s+DATABASE\s+(?:IF\s+EXISTS\s+)?({_NAME_TOKEN})", re.IGNORECASE),
    re.compile(rf"\bDETACH\s+DATABASE\s+({_NAME_TOKEN})", re.IGNORECASE),
    re.compile(rf"\b{_V_ALTER}\s+DATABASE\s+({_NAME_TOKEN})\s+SET\s+{_DB_STATE}\b", re.IGNORECASE),
    # every restore onto a database, with or without the replace option
    re.compile(rf"\bRESTORE\s+DATABASE\s+(?!(?:FROM|WITH)\b)({_NAME_TOKEN_Q}){_RESTORE_END}", re.IGNORECASE),
)
_RENAME_RE = re.compile(
    rf"\b{_V_ALTER}\s+DATABASE\s+({_NAME_TOKEN_Q})\s+MODIFY\s+NAME\s*=\s*({_NAME_TOKEN_Q})", re.IGNORECASE
)
_SESSION_DB_RES = (
    re.compile(r"(?<![\w])USE\s+(\[[^\]\r\n]+\]|[A-Za-z_][\w$#.-]*)\s*(?=;|\r|\n|\"|'|$|\bGO\b)",
               re.IGNORECASE | re.MULTILINE),
    re.compile(r"(?:^|\s)-d\s+[\"']?(\[[^\]\r\n]+\]|[^\s\"';]+)", re.IGNORECASE),
    re.compile(r"(?:^|\s)-Database\s+[\"']?(\[[^\]\r\n]+\]|[^\s\"';]+)", re.IGNORECASE),
    # Database= and Initial Catalog= (bare, single-quoted or double-quoted) are read by _db_literals().
)
_EF_VALUE_FLAGS = frozenset(_EF_VALUE_FLAG_NAMES)
_D_RE = re.compile(rf"(?<![\w-])sqllocaldb(?:\.exe)?[\"']?\s+(?:{_V_DELETE}|d)\b", re.IGNORECASE)
_E_VERB_RE = re.compile(r"(?<![\w.$/\\-])(?:rm|del|erase|rmdir|rd|ri|remove-item)(?![\w.-])", re.IGNORECASE)
_CMD_FLAG_RE = re.compile(r"^/[A-Za-z?]{1,2}$")
# The user-profile root, bare or followed by one wildcard segment (`/*`, `/*.*`, `/*.txt`).
_ROOT_TAIL = r"(?:/|/[*?][^/]*)?$"
_USER_ROOT_RE = re.compile(
    r"^(?:[a-z]:)?/users/[^/]+" + _ROOT_TAIL
    + r"|^~" + _ROOT_TAIL
    + r"|^\$\{?home\}?" + _ROOT_TAIL
    + r"|^\$env:userprofile" + _ROOT_TAIL
    + r"|^\$\{?userprofile\}?" + _ROOT_TAIL
    + r"|^%userprofile%" + _ROOT_TAIL
)
_TBL_PART = r"(?:\[[^\]\r\n]*\]|\"[^\"\r\n]*\"|[^\s.;,()\[\]\"'`]+)"
# White space or a block comment may sit before or after each dot of a multi-part name.
_TBL_WS = r"(?:\s|/\*[\s\S]*?\*/)*"
_TBL_NAME = rf"{_TBL_PART}(?:{_TBL_WS}\.(?:{_TBL_WS}{_TBL_PART})?)*"
_BLOCK_COMMENT_RE = re.compile(r"/\*[\s\S]*?\*/")
_TABLE_STMT_RE = re.compile(
    rf"\b(?:{_V_DROP}\s+TABLE|TRUNCATE\s+TABLE)\s+(?:IF\s+EXISTS\s+)?({_TBL_NAME}(?:\s*,\s*{_TBL_NAME})*)",
    re.IGNORECASE,
)
_RESTORE_CMDLET_RE = re.compile(_PS_RESTORE_CMDLET, re.IGNORECASE)
_SCHEMA_STMT_RE = re.compile(rf"\b{_V_DROP}\s+SCHEMA\b", re.IGNORECASE)
_VARIABLE_TOKEN_RE = re.compile(r"[$`]|%[^%\s]+%|![^!\s]+!")
_PG_REMOVER_RE = re.compile(r"(?<![\w.-])" + _V_PG_REMOVER + r"(?![\w.-])", re.IGNORECASE)
_PG_VALUE_FLAGS = frozenset({"-h", "-p", "-U", "--host", "--port", "--username", "--maintenance-db"})
_MYSQL_ADMIN = "mysql" + "admin"

#: Which class reader handles each label. A label not listed is class G2.
_LABEL_GROUP: dict[str, str] = {
    "sql-drop-database": "A", "sql-detach": "A", "restore-with-replace": "A",
    "mysql-cli-drop-database": "A", "mariadb-cli-drop-database": "A",
    "sql-alter-database-restrict": "A", "sql-restore-database": "A",
    "sql-rename-database": "A-rename", "ps-restore-database-cmdlet": "A-cmdlet",
    "protected-target-statement": "G2",
    "sql-drop-table": "B", "sql-drop-schema": "B", "sql-truncate": "B",
    "ef-database-drop": "C", "ef-database-update-target": "C", "ef-migrations-remove": "C",
    "ef-unresolved-verb": "C",
    "sqllocaldb-delete": "D",
    "data-file-delete": "E",
    "drop-server-trigger": "F", "disable-server-trigger": "F", "sql-shutdown": "F",
    "sqlpackage-block-data-loss-false": "G1-sqlpackage",
    "sqlpackage-create-new-database-true": "G1-sqlpackage",
    "pg-dropdb": "G1-pg", "mysql-" + _MYSQL_ADMIN + "-" + _V_DROP_LC: "G1-mysql",
    "mongo-drop-database": "G1-mongo", "mongo-drop-collection": "G1-mongo",
    "ef-ensure-deleted": "G1-ensure", "ef-database-ensure-deleted": "G1-ensure",
    "human-only-ef-update": "H", "human-only-command": "H",
}

#: Human-only commands an agent may never invoke. The defaults are ALWAYS in force
#: (INV-9): a missing, unreadable or edited rules file can only ADD entries, never
#: remove these two, so the fail direction is closed.
_HUMAN_ONLY_DEFAULTS: tuple[tuple[str, str], ...] = (
    ("update-dev-database.cmd", ""),
    ("restore-latest.cmd", "--recover-missing-dev-db"),
)


def _human_only_entries() -> tuple[tuple[str, str], ...]:
    entries: list[tuple[str, str]] = list(_HUMAN_ONLY_DEFAULTS)
    raw = _RULES.get("human_only_commands")
    if raw is None:
        return tuple(entries)
    if not isinstance(raw, list):
        _RULE_PROBLEMS.append("human_only_commands")
        return tuple(entries)
    bad = False
    for e in raw:
        script = e.get("script") if isinstance(e, dict) else None
        flag = e.get("flag") if isinstance(e, dict) else None
        if not (isinstance(script, str) and script.strip()) or not (flag is None or isinstance(flag, str)):
            bad = True  # skipped: the built-in entries stay in force
            continue
        base = script.replace("\\", "/").rsplit("/", 1)[-1].strip()
        pair = (base, (flag or "").strip())
        if base and pair not in entries:
            entries.append(pair)
    if bad:
        _RULE_PROBLEMS.append("human_only_commands")
    return tuple(entries)


HUMAN_ONLY_ENTRIES = _human_only_entries()


def _t(cls: str, kind: str, name: str, classification: str) -> dict:
    return {"class": cls, "kind": kind, "name": name, "classification": classification}


def _clean_name(raw: str) -> str:
    n = (raw or "").strip()
    if len(n) >= 2 and n[0] in "\"'" and n[-1] == n[0]:
        n = n[1:-1].strip()
    if len(n) >= 2 and n[0] == "[" and n[-1] == "]":
        n = n[1:-1]
    return n.strip().rstrip(";,)")


def _is_disposable_text(s: str) -> bool:
    return any(rx.search(s) for _l, rx in DISPOSABLE_RE)


def _classify_name(name: str) -> str:
    """protected | disposable | other | unresolved, for one database name."""
    if not name or not _READABLE_NAME_RE.match(name):
        return "unresolved"
    low = name.lower()
    if any(low == p.lower() for p in PROTECTED_DATABASES):
        return "protected"
    if low == "tempdb" or _is_disposable_text(name):
        return "disposable"
    return "other"


def _command_tokens(text: str, start: int) -> list[str]:
    """Shell-ish tokens from ``start`` to the end of the command.

    Quotes are removed (a quoted span is one token and may hold spaces or ';').
    The command ends at an unquoted newline, ';', '&', '|' or a token that
    begins a '#' comment.
    """
    tokens: list[str] = []
    i, n = start, len(text)
    while i < n:
        c = text[i]
        if c in " \t":
            i += 1
            continue
        if c in "\r\n;&|#":
            break
        buf: list[str] = []
        while i < n:
            c = text[i]
            if c in "\"'":
                j = text.find(c, i + 1)
                if j == -1:
                    buf.append(text[i + 1:])
                    i = n
                    break
                buf.append(text[i + 1:j])
                i = j + 1
                continue
            if c in " \t\r\n;&|":
                break
            buf.append(c)
            i += 1
        tokens.append("".join(buf))
    return tokens


def _unreadable_word(t: str) -> bool:
    """A word that cannot be read as a literal: a variable, or a splatted argument list (`@args`)."""
    return bool(_VARIABLE_TOKEN_RE.search(t)) or t.startswith("@")


def _ef_commands(text: str) -> list[dict]:
    """Every `dotnet ef <noun> <verb>` command: verb, positional, --connection.

    Option tokens may sit anywhere, including BEFORE the noun and verb (`--project X`,
    `-p X`, `-v`, `--no-color`): they are skipped, a value option takes its value with it.
    """
    out: list[dict] = []
    for m in _EF_TOOL_RE.finditer(text):
        toks = _command_tokens(text, m.end())
        words: list[str] = []          # the non-option tokens: noun, verb, then a migration target
        conn: str | None = None
        conn_present = False
        i = 0
        while i < len(toks):
            a = toks[i]
            if a == "--":
                break  # everything after is forwarded to Program.Main, not read by dotnet ef
            if a.startswith("--connection="):
                conn_present, conn = True, a.split("=", 1)[1]
                i += 1
            elif a == "--connection":
                conn_present = True
                conn = toks[i + 1] if i + 1 < len(toks) else ""
                i += 2
            elif a.startswith("-"):
                i += 2 if (a in _EF_VALUE_FLAGS) else 1
            else:
                words.append(a)
                i += 1
        # A variable (or a splatted `@args`) in the noun or verb position cannot be read.
        unresolved = any(_unreadable_word(t) for t in words[:2])
        if len(words) < 2:
            if unresolved:
                out.append({"verb": ("", ""), "positional": None, "conn_present": False,
                            "conn_dbs": [], "unresolved": True})
            continue
        verb = (words[0].lower(), words[1].lower())
        positional = words[2] if len(words) > 2 else None
        # EVERY database the connection string names (Database= and Initial Catalog=,
        # repeated or mixed; bare or quoted): the last one wins at connect time, so all must be read.
        conn_dbs = _db_literals(conn) if conn else []
        out.append({"verb": verb, "positional": positional, "conn_present": conn_present,
                    "conn_dbs": conn_dbs, "unresolved": unresolved})
    return out


def _in_command_position(text: str, start: int) -> bool:
    """True when the file name at ``start`` is being INVOKED, not just mentioned."""
    pre = text[:start]
    pre = re.sub(
        r"(?:\"[^\"\n]*[\\/]|'[^'\n]*[\\/]|[\"']?[^\s\"';&|()]*[\\/]|[\"'])$", "", pre
    ).rstrip(" \t")
    if not pre or pre[-1] in ";&|(\n\r{":
        return True
    last = re.split(r"\s+", pre)[-1].lower()
    return last in {"call", "start", "sh", "bash", "source", "exec", "iex", "invoke-expression",
                    "invoke-item", "start-process", "/c", "/k", "-file", "-command", "-c", ".", "&"}


def _human_only_script_hits(text: str) -> list[str]:
    hits: list[str] = []
    for base, flag in HUMAN_ONLY_ENTRIES:
        rx = re.compile(r"(?<![\w.-])" + re.escape(base) + r"(?![\w.-])", re.IGNORECASE)
        for m in rx.finditer(text):
            if not _in_command_position(text, m.start()):
                continue
            if flag and flag.lower() not in text[m.end():].split("\n", 1)[0].lower():
                continue
            hits.append(base + (" " + flag if flag else ""))
            break
    return hits


def _classify_stem(stem: str) -> str:
    if _is_disposable_text(stem):
        return "disposable"
    low = stem.lower()
    if any(low.startswith(p.lower()) for p in PROTECTED_DATABASES):
        return "protected"
    return "other"


def _data_file_targets(text: str) -> list[dict]:
    """Class E: delete commands naming a data/log file, a wildcard of them, or a LocalDB folder."""
    out: list[dict] = []
    for m in _E_VERB_RE.finditer(text):
        for tok in _command_tokens(text, m.end()):
            if tok.startswith("-") or _CMD_FLAG_RE.match(tok):
                continue
            norm = tok.replace("\\", "/")
            low = norm.lower()
            if "microsoft sql server local db" in low or _USER_ROOT_RE.match(low):
                out.append(_t("E", "folder", tok[:120], "unresolved"))
                continue
            base = norm.rsplit("/", 1)[-1]
            if re.search(r"\.(?:mdf|ldf)$", base.lower()):
                if "*" in base or "?" in base:
                    out.append(_t("E", "wildcard", tok[:120], "unresolved"))
                else:
                    stem = base[:-4]
                    out.append(_t("E", "data-file", stem, _classify_stem(stem)))
    return out


def _dynamic_labels(text: str, is_shell: bool) -> list[str]:
    """Labels whose detection needs a parsed argument list rather than one regex."""
    if os.environ.get("DB_GUARD_FAULT_INJECTION") == "parser":
        # Test-only switch (contract Revision 4, item 8): the argument-list parser raises WHATEVER
        # the input. main() then runs the protected-write scan (Pass B) in its handler and fails
        # closed when a pattern matched, a pattern-less trigger is present or Pass B finds a
        # protected-database name, so this can never turn a block into an allow; with no match
        # at all the hook stays fail-open.
        raise RuntimeError("injected fault: DB_GUARD_FAULT_INJECTION=parser")
    labels: list[str] = []
    for c in _ef_commands(text):
        if c["unresolved"] and is_shell:
            # Shell tools only, like class H: authoring a script that holds the verb in a
            # variable (Write or Edit) must stay possible.
            labels.append("ef-unresolved-verb")
        if c["verb"] != ("database", "update"):
            continue
        if c["positional"] is not None:
            labels.append("ef-database-update-target")  # a rollback or pinned target (class C)
        elif is_shell:
            dbs = c["conn_dbs"] if c["conn_present"] else []
            if not (dbs and all(_classify_name(_clean_name(d)) == "disposable" for d in dbs)):
                labels.append("human-only-ef-update")  # forward update of the configured db (class H)
    if is_shell and _human_only_script_hits(text):
        labels.append("human-only-command")
    if _data_file_targets(text):
        labels.append("data-file-delete")
    return list(dict.fromkeys(labels))


def _sweep_target(text: str, operands: list[str]) -> dict:
    disposable_forms = all(any(rx.search(op) for rx in _LIKE_DISPOSABLE_RES) for op in operands)
    protected_named = (_PROTECTED_ANYWHERE_RE is None) or bool(_PROTECTED_ANYWHERE_RE.search(text))
    if disposable_forms and not protected_named:
        cls = "disposable"
    else:
        cls = "protected" if protected_named else "other"
    return _t("A'", "predicate", " | ".join(operands)[:120], cls)


def _bind_a(text: str) -> list[dict]:
    out: list[dict] = []
    dynamic = False
    only_variables = True   # every unreadable name was a variable (`!X!`, `%X%`, `$(X)`)
    for rx in _A_RES:
        for m in rx.finditer(text):
            name = _clean_name(m.group(1))
            if _READABLE_NAME_RE.match(name):
                out.append(_t("A", "database", name, _classify_name(name)))
            else:
                dynamic = True
                if not _unreadable_word(name):
                    only_variables = False
    if dynamic or not out:
        operands = _LIKE_RE.findall(text)
        if dynamic and operands:
            out.append(_sweep_target(text, operands))
        else:
            target = _t("A", "database", "unresolved", "unresolved")
            if dynamic and only_variables:
                # Still unresolved (it blocks), but marked so that authoring a script that holds
                # the statement with a variable target is not mistaken for running it (item 7b).
                target["variable"] = True
            out.append(target)
    return out


def _bind_cmdlet(text: str) -> list[dict]:
    """Class A (PowerShell restore cmdlets): the target is the value of -Database (or -DatabaseName).
    A missing or variable value is unresolved; one target per cmdlet call."""
    out: list[dict] = []
    for m in _RESTORE_CMDLET_RE.finditer(text):
        toks = _command_tokens(text, m.end())
        raw: str | None = None
        for i, t in enumerate(toks):
            low = t.lower()
            if low in ("-database", "-databasename"):
                raw = toks[i + 1] if i + 1 < len(toks) else ""
                break
            kv = re.match(r"-database(?:name)?[:=](.*)$", t, re.IGNORECASE)
            if kv:
                raw = kv.group(1)
                break
        name = _clean_name(raw or "")
        out.append(_t("A", "restore-cmdlet", name or "unresolved", _classify_name(name)))
    return out or [_t("A", "restore-cmdlet", "unresolved", "unresolved")]


def _split_name_parts(name: str) -> list[str]:
    """Split a dotted multi-part name on its separators; brackets and quotes keep their dots."""
    parts: list[str] = []
    cur = ""
    i = 0
    while i < len(name):
        ch = name[i]
        if ch in "[\"":
            close = "]" if ch == "[" else '"'
            j = name.find(close, i + 1)
            j = len(name) - 1 if j == -1 else j
            cur += name[i:j + 1]
            i = j + 1
        elif ch == ".":
            parts.append(cur)
            cur = ""
            i += 1
        else:
            cur += ch
            i += 1
    parts.append(cur)
    return parts


def _bind_b(text: str) -> list[dict]:
    """Class B: a three-part table name (<db>.<schema>.<table>, or <db>..<table>) is
    bound by its database part; any other table name, and a schema statement, falls
    back to the session database; none named = unresolved."""
    out: list[dict] = []
    needs_session = bool(_SCHEMA_STMT_RE.search(text))
    found = False
    for stmt in _TABLE_STMT_RE.finditer(text):
        for nm in re.finditer(_TBL_NAME, stmt.group(1)):
            found = True
            parts = _split_name_parts(_BLOCK_COMMENT_RE.sub("", nm.group(0)))
            if len(parts) == 3:
                db = _clean_name(parts[0])
                out.append(_t("B", "table-db", db or "unresolved", _classify_name(db)))
            elif len(parts) > 3:
                out.append(_t("B", "table-db", nm.group(0)[:120], "unresolved"))  # linked-server form
            else:
                needs_session = True
    if not found:
        needs_session = True
    if needs_session:
        names = [_clean_name(m.group(1)) for rx in _SESSION_DB_RES for m in rx.finditer(text)]
        names += [_clean_name(v) for v in _db_literals(text)]
        if not names:
            out.append(_t("B", "table", "unresolved", "unresolved"))
        else:
            out += [_t("B", "table", n, _classify_name(n)) for n in names]
    return out


def _bind_c(text: str) -> list[dict]:
    out: list[dict] = []
    for c in _ef_commands(text):
        v = c["verb"]
        if c["unresolved"]:
            out.append(_t("C", "ef-verb", "(unreadable verb)", "unresolved"))
            continue
        relevant = (
            v in {("database", _V_DROP_LC), ("migrations", _V_REMOVE)}
            or (v == ("database", "update") and c["positional"] is not None)
        )
        if not relevant:
            continue
        if c["conn_present"]:
            # Every database the string names must be disposable (the last one wins at connect time).
            names = [_clean_name(d) for d in c["conn_dbs"]] or [""]
            out.extend(_t("C", "ef-connection", n or "unresolved", _classify_name(n)) for n in names)
        else:
            out.append(_t("C", "ef-configured", "(configured database)", "protected"))
    return out or [_t("C", "ef", "unresolved", "unresolved")]


def _bind_rename(text: str) -> list[dict]:
    """Class A-rename: the database being renamed AND the new name are both read.
    A protected name on either side blocks; a marker exempts nothing else."""
    out: list[dict] = []
    for m in _RENAME_RE.finditer(text):
        for kind, raw in (("rename-source", m.group(1)), ("rename-new-name", m.group(2))):
            name = _clean_name(raw)
            out.append(_t("A-rename", kind, name or "unresolved", _classify_name(name)))
    return out or [_t("A-rename", "rename-source", "unresolved", "unresolved")]


def _bind_d(text: str) -> list[dict]:
    out: list[dict] = []
    for m in _D_RE.finditer(text):
        toks = [t for t in _command_tokens(text, m.end()) if not t.startswith("-")]
        name = _clean_name(toks[0]) if toks else ""
        out.append(_t("D", "localdb-instance", name or "unresolved", _classify_name(name)))
    return out or [_t("D", "localdb-instance", "unresolved", "unresolved")]


def _names_to_targets(cls: str, kind: str, names: list[str]) -> list[dict]:
    names = [_clean_name(n) for n in names]
    return [_t(cls, kind, n or "unresolved", _classify_name(n)) for n in names]


def _g1_sqlpackage(text: str) -> list[dict]:
    names = [m.group(1) for m in
             re.finditer(r"/(?:TargetDatabaseName|tdn)\s*[:=]\s*[\"']?([^\s\"';]+)", text, re.IGNORECASE)]
    for m in re.finditer(r"/(?:TargetConnectionString|tcs)\s*[:=]\s*(\"[^\"]*\"|'[^']*'|\S+)",
                         text, re.IGNORECASE):
        names.extend(_db_literals(m.group(1)))
    return _names_to_targets("G1", "sqlpackage", names) or [_t("G1", "sqlpackage", "unresolved", "unresolved")]


def _g1_pg(text: str) -> list[dict]:
    names: list[str] = []
    for m in _PG_REMOVER_RE.finditer(text):
        toks = _command_tokens(text, m.end())
        i = 0
        while i < len(toks):
            a = toks[i]
            if a.startswith("-"):
                i += 2 if a in _PG_VALUE_FLAGS else 1
            else:
                names.append(a)
                i += 1
    return _names_to_targets("G1", "postgres", names) or [_t("G1", "postgres", "unresolved", "unresolved")]


def _g1_mysql(text: str) -> list[dict]:
    names: list[str] = []
    for m in re.finditer(r"\b" + _MYSQL_ADMIN + r"(?:\.exe)?\b", text, re.IGNORECASE):
        toks = _command_tokens(text, m.end())
        idx = next((i for i, t in enumerate(toks) if t.lower() == _V_DROP_LC), None)
        if idx is not None:
            rest = [t for t in toks[idx + 1:] if not t.startswith("-")]
            names.append(rest[0] if rest else "")
    return _names_to_targets("G1", "mysql", names) or [_t("G1", "mysql", "unresolved", "unresolved")]


def _mongo_names(text: str) -> list[str]:
    names = re.findall(r"(?<![\w.])use\s+([\w-]+)", text, re.IGNORECASE)
    names += re.findall(r"--db[= ]\s*[\"']?([\w-]+)", text, re.IGNORECASE)
    names += re.findall(r"mongodb(?:\+srv)?://[^/\s\"']+/([\w-]+)", text, re.IGNORECASE)
    return names


def _bind_g2(text: str) -> dict:
    """Class G2: a marker anywhere AND no protected name in a database-name position."""
    marker = _is_disposable_text(text)
    protected_pos = bool(PROTECTED_DESTRUCTIVE_TARGET_RE.search(text)) or any(
        rx.search(text) for _l, rx in PROTECTED_DB_RE
    )
    if protected_pos:
        return _t("G2", "untargeted", "unresolved", "protected")
    return _t("G2", "untargeted", "unresolved", "marker" if marker else "other")


def _bind_targets(text: str, labels: list[str]) -> list[dict]:
    """Read one Destructive Target per matched label group. Raises on an internal fault."""
    if os.environ.get("DB_GUARD_FAULT_INJECTION") == "binder":
        # Test-only switch (contract 2026-10-04). It can only turn an allow into a block.
        raise RuntimeError("injected fault: DB_GUARD_FAULT_INJECTION=binder")
    in_migration = "migration-builder-sql-drop" in labels
    groups: list[str] = []
    for label in labels:
        g = _LABEL_GROUP.get(label, "G2")
        if g == "B" and in_migration:
            g = "G2"  # raw SQL inside a migration is a class G2 case
        if g not in groups:
            groups.append(g)
    targets: list[dict] = []
    for g in groups:
        if g == "A":
            targets += _bind_a(text)
        elif g == "A-rename":
            targets += _bind_rename(text)
        elif g == "A-cmdlet":
            targets += _bind_cmdlet(text)
        elif g == "B":
            targets += _bind_b(text)
        elif g == "C":
            targets += _bind_c(text)
        elif g == "D":
            targets += _bind_d(text)
        elif g == "E":
            targets += _data_file_targets(text) or [_t("E", "data-file", "unresolved", "unresolved")]
        elif g == "F":
            targets.append(_t("F", "server", "", "server-scope"))
        elif g == "H":
            if "human-only-ef-update" in labels:
                targets.append(_t("H", "ef-update", "(configured database)", "human-only"))
            for hit in (_human_only_script_hits(text) if "human-only-command" in labels else []):
                targets.append(_t("H", "script", hit, "human-only"))
        elif g == "G1-sqlpackage":
            targets += _g1_sqlpackage(text)
        elif g == "G1-pg":
            targets += _g1_pg(text)
        elif g == "G1-mysql":
            targets += _g1_mysql(text)
        elif g in ("G1-mongo", "G1-ensure"):
            if g == "G1-mongo":
                names = _mongo_names(text)
            else:
                names = _db_literals(text)
            targets += _names_to_targets("G1", g[3:], names) if names else [_bind_g2(text)]
        else:
            targets.append(_bind_g2(text))
    if labels and not targets:
        targets.append(_t("?", "unknown", "unresolved", "unresolved"))
    return targets


def _targets_allow(targets: list[dict], authoring: bool = False) -> bool:
    """Every target disposable (or the narrowed legacy marker). When ``authoring`` (a whole-file
    Write or Edit of one of the three authoring paths) a target that is only a VARIABLE is not an
    executed statement, so it does not block; a protected or undisposable literal still does."""
    return bool(targets) and all(
        t["classification"] in ("disposable", "marker") or (authoring and t.get("variable"))
        for t in targets
    )


def _targets_summary(targets: list[dict]) -> str:
    return "; ".join(f"{t['class']}:{t['kind']}={t['name'] or '-'} ({t['classification']})" for t in targets)


# ---------------------------------------------------------------------------
# Inert prose (item 7a). A commit message, a pull-request body, a grep pattern or a plain
# echo only CARRIES text: it never runs it. Quoted spans of such a command are blanked before
# any matcher reads the text, so prose that merely names a guarded command does not block.
#
# What is NOT blanked, so nothing executable can hide here:
#   - an echo, printf, grep, rg or gh that is piped on, redirected or fed a here-string (its
#     text may become a SQL batch); gh is masked only for the text-carrying subcommands;
#   - any segment whose unquoted text holds a command substitution, a backtick, a parenthesis,
#     a `<`, or a backslash next to a quote (it runs, or it desyncs the quote pairing);
#   - a double-quoted span with a command substitution other than the heredoc form
#     `$(cat <<'TAG' ... TAG )`, or with a backtick (it runs);
#   - a quote that is escaped with a backslash (the shell sees a plain character);
#   - any other command (sqlcmd -Q "...", pwsh -Command "...", bash -c "...").
# ---------------------------------------------------------------------------
_HEREDOC_SUB_RE = re.compile(r"\$\(\s*cat\s*<<-?\s*(?:'(\w+)'|\"(\w+)\"|\\(\w+))")
_PROSE_GIT_SUBCOMMANDS = frozenset({"commit", "tag", "notes"})
_PROSE_ECHO_COMMANDS = frozenset({"echo", "printf", "write-host", "write-output"})
_PROSE_SEARCH_COMMANDS = frozenset({"grep", "egrep", "fgrep", "rg"})


def _skip_subshell(text: str, j: int) -> int:
    """Index just after the ``)`` that closes a ``$(`` whose body starts at ``j``."""
    n, depth = len(text), 1
    while j < n:
        ch = text[j]
        if ch in "\"'":
            j = _skip_quoted(text, j)[0]
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return n


def _heredoc_tag_end(text: str, start: int, tag: str) -> int | None:
    """Index just after the FIRST line that holds only ``tag`` (after ``start``), or None."""
    m = re.compile(r"\n[ \t]*" + re.escape(tag) + r"[ \t]*(?=\r?\n|$)").search(text, start)
    return None if m is None else m.end()


def _skip_quoted(text: str, i: int) -> tuple[int, bool]:
    """(index after the closing quote, whether the quote was closed) for the quote at ``i``."""
    n = len(text)
    if text[i] == "'":
        k = text.find("'", i + 1)
        return (n, False) if k == -1 else (k + 1, True)
    j = i + 1
    while j < n:
        if text[j] == '"':
            return j + 1, True
        if text.startswith("$(", j):
            hd = _HEREDOC_SUB_RE.match(text, j)
            if hd:
                # The heredoc ends at the FIRST tag line (as the shell reads it); whatever follows
                # is still inside the substitution and is read as commands.
                tag_end = _heredoc_tag_end(text, hd.end(), hd.group(1) or hd.group(2) or hd.group(3))
                if tag_end is None:
                    return n, False
                j = _skip_subshell(text, tag_end)
            else:
                j = _skip_subshell(text, j + 2)
            continue
        j += 1
    return n, False


def _span_is_inert(text: str, start: int, end: int) -> bool:
    """A single-quoted span always is; a double-quoted one only without a running substitution."""
    if text[start] == "'":
        return True
    inner = text[start + 1:end - 1]
    if "`" in inner:
        return False
    pos = 0
    while True:
        m = re.compile(r"\$\(").search(inner, pos)
        if m is None:
            return True
        hd = _HEREDOC_SUB_RE.match(inner, m.start())
        if hd is None:
            return False
        tag_end = _heredoc_tag_end(inner, hd.end(), hd.group(1) or hd.group(2) or hd.group(3))
        if tag_end is None:
            return False
        # Inert only when the closing paren follows the FIRST tag line directly.
        close = re.compile(r"\r?\n\s*\)").match(inner, tag_end)
        if close is None:
            return False
        pos = close.end()


def _segment_is_prose(words: list[str], piped: bool, redirected: bool) -> bool:
    first = re.split(r"[\\/]", words[0])[-1].lower()
    if first.endswith(".exe"):
        first = first[:-4]
    if first == "git":
        sub = next((w.lower() for w in words[1:] if not w.startswith("-")), "")
        return sub in _PROSE_GIT_SUBCOMMANDS
    if piped or redirected:
        return False
    if first == "gh":
        sub = [w.lower() for w in words[1:] if not w.startswith("-")][:2]
        return sub in (["pr", "create"], ["pr", "edit"], ["pr", "comment"],
                       ["issue", "create"], ["issue", "edit"], ["issue", "comment"],
                       ["release", "create"])
    return first in _PROSE_SEARCH_COMMANDS or first in _PROSE_ECHO_COMMANDS


def _mask_inert_prose(text: str) -> str:
    """``text`` with the quoted spans of prose-carrying commands replaced by spaces (same length)."""
    out = list(text)
    n, i = len(text), 0
    words: list[str] = []
    spans: list[tuple[int, int]] = []
    redirected = False
    unsafe = False  # the segment's unquoted text runs something or desyncs the quote pairing

    def flush(piped: bool) -> None:
        nonlocal words, spans, redirected, unsafe
        if words and not unsafe and _segment_is_prose(words, piped, redirected):
            for s, e in spans:
                if _span_is_inert(text, s, e):
                    for k in range(s + 1, e - 1):
                        out[k] = " "
        words, spans, redirected, unsafe = [], [], False, False

    while i < n:
        c = text[i]
        if c in " \t":
            i += 1
            continue
        if c in "\r\n;&|":
            flush(c == "|" and text[i + 1:i + 2] != "|")
            i += 1
            continue
        buf: list[str] = []
        while i < n and text[i] not in " \t\r\n;&|":
            ch = text[i]
            if ch in "(`<" or (ch == "\\" and (text[i + 1:i + 2] in ("'", '"') or text[i - 1:i] in ("'", '"'))):
                unsafe = True  # substitution, group, here-string, or a backslash next to a quote
            if ch in "\"'" and text[i - 1:i] == "\\":
                unsafe = True  # an escaped quote: the shells disagree on how the quotes pair
            if ch in "\"'" and not (i > 0 and text[i - 1] == "\\"):
                end, closed = _skip_quoted(text, i)
                if closed:
                    if ch == '"' and ('\\"' in text[i:end] or '`"' in text[i:end]):
                        unsafe = True  # an escaped quote inside: the span may end early
                    spans.append((i, end))
                    buf.append(text[i + 1:end - 1])
                else:
                    buf.append(text[i + 1:end])
                i = end
                continue
            if ch == ">":
                redirected = True
            buf.append(ch)
            i += 1
        words.append("".join(buf))
    flush(False)
    return "".join(out)


#: The three files an agent may author whole (Write or Edit): the two scripts that legitimately
#: hold a restore / removal statement with a variable target, and their test harness.
_AUTHORING_PATH_RE = re.compile(
    r"(?:^|/)tools/db-protection/(?:restore-latest\.cmd|verify-migration\.cmd|tests/test_db_protection_scripts\.py)$"
)


def _is_authoring_path(file_path: str, tool_name: str) -> bool:
    """True for a Write / Edit / MultiEdit of one of the authoring paths (worktree segments removed)."""
    if tool_name not in ("Write", "Edit", "MultiEdit") or not file_path:
        return False
    try:
        return bool(_AUTHORING_PATH_RE.search(_segment_test_path(file_path)))
    except Exception:  # noqa: BLE001 -- fail closed: not an authoring path
        return False


def _holds_pattern_less_trigger(text: str) -> bool:
    """True when the text holds what the pattern-less classes read: the EF tool, a delete verb,
    or a human-only script name. A parser fault on such text must fail CLOSED (item 8)."""
    if _EF_TOOL_RE.search(text) or _E_VERB_RE.search(text):
        return True
    return any(
        re.search(r"(?<![\w.-])" + re.escape(base) + r"(?![\w.-])", text, re.IGNORECASE)
        for base, _flag in HUMAN_ONLY_ENTRIES
    )


# ---------------------------------------------------------------------------
# Decision tree.
# ---------------------------------------------------------------------------
def _inject_fault(step: str, matched: list[str]) -> None:
    """Test-only switch (contract 2026-10-04): DB_GUARD_FAULT_INJECTION=<step> raises inside
    that step, but ONLY when a destructive pattern already matched, so it can only turn an
    allow into a block and never changes a non-destructive input."""
    if matched and os.environ.get("DB_GUARD_FAULT_INJECTION") == step:
        raise RuntimeError(f"injected fault: DB_GUARD_FAULT_INJECTION={step}")


def _fail_closed(payload: dict, tool_name: str, file_path: str, labels: list[str], exc: Exception) -> int:
    """An internal error AFTER a class matched blocks (exit 2). Never a silent allow."""
    record = {
        "ts": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "hook": HOOK_NAME,
        "session": payload.get("session_id") or "",
        "tool": tool_name,
        "file_path": file_path,
        "matched_destructive": labels,
        "error": repr(exc),
    }
    if os.environ.get("CLAUDE_DESTRUCTIVE_DB_OK") == "1":
        _audit({**record, "decision": "ALLOW", "reason": "user-override-env"})
        return 0
    _audit({**record, "decision": "BLOCK", "reason": "internal-error-after-match"})
    shown = ", ".join(labels) or "(a command read by the argument-list parser)"
    sys.stderr.write(
        f"[db-destructive-guard] BLOCKED: internal error while reading the target of {shown}; "
        "failing closed.\n"
        "A person can run this with the human override (USER sets CLAUDE_DESTRUCTIVE_DB_OK=1).\n"
        + "".join(line + "\n" for line in _rules_problem_lines())
    )
    return 2


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

    raw_text = _extract_text(payload)
    if not raw_text:
        return 0

    is_shell_tool = tool_name in ("Bash", "PowerShell")
    # Quoted prose that a command only carries (a commit message, a pull-request body, a grep
    # pattern, a plain echo) is blanked before any matcher reads it (item 7a). Excerpts keep raw_text.
    text = _mask_inert_prose(raw_text) if is_shell_tool else raw_text

    file_path = _extract_file_path(payload)
    in_allowlist = _file_in_production_allowlist(file_path)
    authoring = _is_authoring_path(file_path, tool_name)

    # ---- Pass A: existing destructive-pattern scan ----------------------
    matched_destructive: list[str] = []
    for label, rx in DESTRUCTIVE_RE:
        if rx.search(text):
            matched_destructive.append(label)
    # A protected database named as the target of a DROP / ALTER / RESTORE DATABASE statement
    # is a match on its own, even when no other pattern lists the statement (item 3).
    if PROTECTED_DESTRUCTIVE_TARGET_RE.search(text):
        matched_destructive.append("protected-target-statement")

    # Labels that need a parsed argument list (EF rollback target, data-file
    # deletion, human-only commands). Shell tools only for the human-only ones.
    protected_db_hits: list[str] = []
    has_write_kw = False
    try:
        _inject_fault("dynamic", matched_destructive)
        for label in _dynamic_labels(text, is_shell_tool):
            if label not in matched_destructive:
                matched_destructive.append(label)

        # ---- Pass B: protected-DB-write scan (Layer 3c) -----------------
        _inject_fault("writes", matched_destructive)
        protected_db_hits, has_write_kw = _scan_protected_db_writes(text)
    except Exception as exc:  # noqa: BLE001 -- deliberate fail-closed catch-all
        # The fault may have fired before Pass B ran: read Pass B here so a protected-database
        # write is never turned into an allow by an internal error.
        try:
            protected_db_hits, has_write_kw = _scan_protected_db_writes(text)
        except Exception:  # noqa: BLE001
            protected_db_hits = []
        if not matched_destructive and not protected_db_hits and not _holds_pattern_less_trigger(text):
            raise  # nothing matched: keep the hook's fail-open contract for a plain bug
        log_event(HOOK_NAME, "internal-error-after-match", repr(exc))
        return _fail_closed(payload, tool_name, file_path, matched_destructive, exc)
    # A protected-DB-write violation requires BOTH a protected-DB pattern AND
    # a write keyword in the same input, AND the editing tool to be targeting
    # a path OUTSIDE the production allow-list (or a shell tool with no path).
    # With a wrong-type production_path_allowlist the guard cannot tell which paths are
    # production, so (fail closed) the write keyword is not required: naming a protected
    # database outside the narrowed default paths blocks.
    protected_db_violation = (
        bool(protected_db_hits)
        and (has_write_kw or "production_path_allowlist" in _RULE_PROBLEMS)
        and (is_shell_tool or not in_allowlist)
    )

    if not matched_destructive and not protected_db_violation:
        return 0

    # A class matched. From here every step that reads a target, classifies it
    # or decides runs inside one guarded section: an exception blocks (exit 2).
    try:
        return _decide(
            payload, tool_name, text, file_path, in_allowlist,
            matched_destructive, protected_db_hits, has_write_kw, protected_db_violation,
            raw_text=raw_text, authoring=authoring,
        )
    except Exception as exc:  # noqa: BLE001 -- deliberate fail-closed catch-all
        log_event(HOOK_NAME, "internal-error-after-match", repr(exc))
        return _fail_closed(payload, tool_name, file_path, matched_destructive, exc)


def _decide(
    payload: dict,
    tool_name: str,
    text: str,
    file_path: str,
    in_allowlist: bool,
    matched_destructive: list[str],
    protected_db_hits: list[str],
    has_write_kw: bool,
    protected_db_violation: bool,
    raw_text: str | None = None,
    authoring: bool = False,
) -> int:
    excerpt_source = text if raw_text is None else raw_text
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
        "text_excerpt": _truncate(excerpt_source, 320),
    }

    # A protected database named as the direct target of a database-level
    # destructive statement vetoes the disposable allow path outright. See the
    # PROTECTED_DESTRUCTIVE_TARGET_RE block comment above -- without this, a
    # protected target smuggled alongside any disposable name took ALLOW path 1.
    protected_target_hit = bool(PROTECTED_DESTRUCTIVE_TARGET_RE.search(text))
    base_record["protected_destructive_target"] = protected_target_hit

    # Read each operation's own target (binding table). A disposable marker
    # counts only when it sits on that target.
    targets = _bind_targets(text, matched_destructive) if matched_destructive else []
    targets_ok = _targets_allow(targets, authoring)
    base_record["destructive_targets"] = targets

    # ---- ALLOW path 1: every destructive target bound to a disposable name
    if (
        matched_destructive
        and targets_ok
        and not argv_position_bug
        and not protected_db_violation
        and not protected_target_hit
    ):
        used_variable = authoring and any(t.get("variable") for t in targets)
        _audit({**base_record, "decision": "ALLOW",
                "reason": "authoring-variable-target" if used_variable else "disposable-bound-to-target"})
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
    elif any(t["classification"] == "human-only" for t in targets):
        reason = "human-only-command"
    elif any(t["classification"] == "server-scope" for t in targets):
        reason = "server-scope-never-exempt"
    elif any(t["classification"] == "unresolved" for t in targets):
        reason = "unresolved-target"
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
        lines.append(f"Excerpt: {_truncate(excerpt_source, 200)}")
        lines.append("")
        lines.append("Production paths where these connection strings legitimately appear:")
        for p in PRODUCTION_PATH_ALLOWLIST:
            lines.append(f"    {p}")
        lines.append("")
        lines.append("If this is a test, use a disposable connection string built from a guid,")
        lines.append("not the dev DB name. Pattern: Database=<AnyName>_Test_<guid>")
        if _pp_checkout_equivalent_path is None:
            lines.append("")
            lines.append(
                f"NOTE: _project_paths.py could not be imported (looked for "
                f"{_PROJECT_PATHS_EXPECTED_PATH}). Fallback mode is in effect: "
                "worktree source gets no bypass until this helper is restored."
            )
    else:
        lines.append("this tool call would run a destructive DB operation against")
        lines.append("what appears to be a working/dev/prod database.")
        lines.append("")
        lines.append(f"Detected pattern(s): {', '.join(matched_destructive)}")
        if targets:
            lines.append(f"Target(s) read: {_targets_summary(targets)}")
        lines.append(f"Excerpt: {_truncate(excerpt_source, 200)}")
        lines.append("")
        if reason == "human-only-command":
            lines.append("This step changes the development database and is run by a person in")
            lines.append("their own terminal, never from Claude Code.")
            lines.append("")
        elif reason == "server-scope-never-exempt":
            lines.append("Server-scope operations are never exempted by a disposable name.")
            lines.append("")
        elif reason == "unresolved-target":
            lines.append("The target of this operation could not be read, so it is treated as")
            lines.append("protected. A disposable name counts only on the operation's own target.")
            lines.append("")
        if argv_position_bug:
            lines.append("ARGV-POSITION BUG DETECTED:")
            lines.append("  Your command places a disposable-DB marker AFTER the `--` separator.")
            lines.append("  In dotnet-CLI, `--` forwards remaining args to Program.Main; the")
            lines.append("  --connection flag is NOT consumed by `dotnet ef`. The DB destination")
            lines.append("  falls back to the host's default (the dev DB).")
            lines.append("")
            lines.append("  Fix: run tools/db-protection/verify-migration.cmd for a safe migration check.")
            lines.append("  The EF database-removal command is run by hand, never by Claude.")
        else:
            lines.append("To run this safely, target a disposable DB name with one of these patterns:")
            lines.append("    _DryRun, _MigrationVerify, _Sandbox, _Scratch, _Throwaway, _Test_<guid>, _e2e_<guid>")
        lines.append("")
        lines.append("Migration verification ('fresh DB' tests) MUST use a separately-named")
        lines.append("disposable database -- never the connection string from appsettings.json.")
        lines.append("Use tools/db-protection/verify-migration.cmd for the safe workflow.")
    lines.extend(_rules_problem_lines())
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
