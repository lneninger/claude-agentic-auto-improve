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

OVERRIDE (the Database override arm)
------------------------------------
A person who wants ONE blocked command put in front of them creates the file
<project>/.claude/database-override.once in their own terminal. The arm allows nothing by itself:
the next command this guard would block becomes a Claude Code permission prompt, once, and only
where Claude Code asks (the permission mode is default, acceptEdits or plan). The claim is shared
with db-destructive-guard.py through the tool call identifier. An agent never creates the arm: a
tool call that would write it (a file whose name starts with "database-override.") is refused
first, before Guard deference (the Arm-write rule).

Hook contract (Claude Code PreToolUse):
    stdin:  JSON { tool_name, tool_input, permission_mode, tool_use_id }
    exit 0: allow (or, with an ask JSON on standard output, a permission prompt)
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

#: Guard deference (contract 2026-10-12-dedupe-claude-config, Value Objects "Project guard
#: registration"): bound at import time via ``getattr``. A helper that is missing, stale or raising
#: is treated as "do not defer", so this guard acts exactly as it did before deference existed.
_pp_should_defer = (
    getattr(_pp_log, "should_defer_to_project_guard", None) if _pp_log is not None else None
)
GUARD_FILE_NAME = "db-research-readonly-guard.py"

#: Database override arm (contract 2026-11-16-file-based-switches, Guard fallback mode): the claim is
#: bound with ``getattr``. A missing, stale or raising helper means "no override": the guard blocks.
try:
    import _switches as _sw
except Exception:  # pragma: no cover - fail-soft
    _sw = None
_sw_claim_override = getattr(_sw, "claim_database_override", None) if _sw is not None else None
try:  # the shared shell parser (standard library only)
    import _shell_write_targets as _swt
except Exception:  # pragma: no cover - fail-soft
    _swt = None

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
# blocked unless read-only was enforced (a person's one-shot arm turns a block into a prompt).
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
# `sqlcmd -d <ProtectedName> -Q "INSERT ... -- cleanup X_Test_abc123"` through:
# no protected DROP target, a disposable marker present, yet plain DML aimed
# straight at the dev database. (b) closes that.
#
# The heavy verbs are composed from parts so this file's own source does not
# contain the literal phrases that db-destructive-guard.py's pattern bank
# scans for -- same technique that guard already uses on itself.
# ---------------------------------------------------------------------------
_V_DROP = "DR" + "OP"
_V_ALTER = "AL" + "TER"

# The protected database names are a project fact, so they are NOT written here.
# They come from db-destructive-guard.rules.json -- one rules file, read by both
# database guards, so the two can never disagree about which databases are
# protected.
#
# THE LOADER FAILS CLOSED, exactly as the destructive guard's does. If the rules
# file is missing, unreadable or has an empty list, every database name is
# treated as protected, which makes clause (b) below match every command and so
# withdraws the disposable exemption entirely. Stricter, never looser.
#
# THE RULES FILE IS THE PROJECT'S, NEVER THE PLUGIN'S (INV-O3). This hook runs from the plugin, so
# the file beside it is only a template naming fictional databases. The rules are read from
# <CLAUDE_PROJECT_DIR>/.claude/hooks/ and nowhere else; an unset CLAUDE_PROJECT_DIR reads nothing,
# which takes the fail-closed path above.
_RULES_FILE_NAME = "db-destructive-guard.rules.json"


def _project_rules_path() -> Path | None:
    raw = os.environ.get("CLAUDE_PROJECT_DIR", "").strip()
    if not raw:
        return None
    return Path(raw) / ".claude" / "hooks" / _RULES_FILE_NAME


_RULES_PATH = _project_rules_path() or Path(_RULES_FILE_NAME)


def _load_protected_names() -> tuple[str, ...]:
    project_path = _project_rules_path()
    if project_path is None:
        return ()
    try:
        with project_path.open(encoding="utf-8") as _f:
            data = json.load(_f)
    except Exception:
        return ()
    if not isinstance(data, dict):
        return ()
    # Longest name first, so an alternation never settles on a shorter prefix.
    return tuple(
        sorted(
            (str(n) for n in (data.get("protected_databases") or []) if str(n).strip()),
            key=len,
            reverse=True,
        )
    )


PROTECTED_DATABASES = _load_protected_names()

if PROTECTED_DATABASES:
    _PROTECTED_NAMES = r"(?:" + "|".join(re.escape(n) for n in PROTECTED_DATABASES) + r")"
else:
    # No configuration: treat every database name as protected.
    _PROTECTED_NAMES = r"\w+"

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


def _defers_to_project_copy(payload: dict) -> bool:
    """True when the PROJECT registers its own copy of this guard for this event and tool.

    The helper checks conditions (a) to (h) and writes the ``deferred`` decision itself. Anything
    other than a clean ``True`` -- a missing helper, an error, a stale answer -- means act.
    """
    if _pp_should_defer is None:
        return False
    try:
        return _pp_should_defer(GUARD_FILE_NAME, payload, __file__, HOOK_NAME) is True
    except Exception:  # noqa: BLE001 -- every failure resolves toward acting
        return False


# ---------------------------------------------------------------------------
# Database override arm (contract 2026-11-16-file-based-switches, "Override rules"). The name test of
# the Arm-write rule and the prompt output are INLINE copies of db-destructive-guard.py's (Guard
# fallback mode); the claim is the helper's.
# ---------------------------------------------------------------------------
_ARM_NAME_PREFIX = "database-override."
_ARM_FILE_NAME = "database-override.once"
_ARM_NAME_RE = re.compile(r"database-override\.", re.IGNORECASE)
#: Permission modes where Claude Code asks a person. Any other mode, or none, shows no prompt.
_PROMPT_MODES = ("default", "acceptEdits", "plan")
_OVERRIDE_OUTCOMES = ("absent", "stale", "unusable", "claimed", "claimed-by-sibling", "no-prompt-available")
_PROMPT_WORDING = (
    "One-shot destructive database override. A person armed it. "
    "Approve only if you mean to run this exact command."
)


def _last_part_names_arm(path_text: object) -> bool:
    """True when the last part of a path starts with ``database-override.`` (any case, either slash)."""
    last = str(path_text).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return last.lower().startswith(_ARM_NAME_PREFIX)


def _mask_inert_prose(command: str) -> str:
    """The command with the quoted prose a commit, pull request, search or echo only carries blanked.

    This guard has no masker of its own: it borrows db-destructive-guard.py's from the same folder.
    Anything that goes wrong returns the raw text, which only makes the Arm-write rule stricter."""
    try:
        import importlib.util

        path = Path(__file__).resolve().parent / "db-destructive-guard.py"
        spec = importlib.util.spec_from_file_location("_db_destructive_guard_masker", str(path))
        if spec is None or spec.loader is None:
            return command
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return str(module._mask_inert_prose(command))
    except Exception:  # noqa: BLE001 -- fail closed: the raw text
        return command


def _arm_write_match(payload: dict) -> str:
    """Arm-write rule: text naming what would write the arm file, or ``""``. Shell tools only."""
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return ""
    command = str(tool_input.get("command", ""))
    named = bool(_ARM_NAME_RE.search(command))
    if not named and _sw is not None:
        names_test = getattr(_sw, "names_override_file", None)
        try:
            named = bool(names_test is not None and names_test(command))
        except Exception:  # noqa: BLE001 -- the inline test above already ran
            named = False
    if not named:
        return ""
    if _swt is not None:
        try:
            for _kind, target in _swt.parse_redirect_targets(command):
                if _last_part_names_arm(target):
                    return target
        except Exception:  # noqa: BLE001 -- the masked-text test below still runs
            pass
    masked = _mask_inert_prose(command)
    hit = _ARM_NAME_RE.search(masked)
    if hit is None:
        return ""
    return masked[max(0, hit.start() - 30):hit.end() + 30].strip()


def _refuse_arm_write(payload: dict, tool_name: str, matched: str) -> int:
    """Block a tool call that would create the arm. Only a person creates it."""
    _audit({
        "ts": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "hook": HOOK_NAME,
        "session": payload.get("session_id") or "",
        "tool": tool_name,
        "decision": "BLOCK",
        "reason": "override-file-write-refused",
        "matched": _truncate(matched, 200),
    })
    sys.stderr.write(
        "[db-research-readonly-guard] BLOCKED: this tool call would write the database override arm file "
        "(database-override.*).\n"
        "Only a person creates it, in their own terminal; an agent never does.\n"
        f"Matched: {_truncate(matched, 200)}\n"
    )
    return 2


def _single_quote_powershell(path: str) -> str:
    return "'" + path.replace("'", "''") + "'"


def _single_quote_posix(path: str) -> str:
    return "'" + path.replace("'", "'\\''") + "'"


def _project_root() -> Path | None:
    try:
        return Path(_pp_log.project_dir()) if _pp_log is not None and _pp_log.project_dir() else None
    except Exception:  # noqa: BLE001
        return None


def _arm_path_text() -> str:
    root = _project_root()
    return str(root / ".claude" / _ARM_FILE_NAME) if root is not None else ".claude/" + _ARM_FILE_NAME


def _arm_present() -> bool:
    root = _project_root()
    return root is not None and os.path.lexists(root / ".claude" / _ARM_FILE_NAME)


def _try_override(payload: dict) -> str:
    """Override outcome for a command this guard is about to block. Claims the arm only when a prompt
    can be shown (Person-present rule); never raises."""
    try:
        root = _project_root()
        if root is None or _sw_claim_override is None:
            return "absent"
        if payload.get("permission_mode") not in _PROMPT_MODES:
            return "no-prompt-available" if _arm_present() else "absent"
        tool_use_id = payload.get("tool_use_id")
        outcome = _sw_claim_override(root, tool_use_id if isinstance(tool_use_id, str) else "")
        return outcome if outcome in _OVERRIDE_OUTCOMES else "unusable"
    except Exception:  # noqa: BLE001 -- no override
        return "unusable"


def _print_ask(reason: str) -> None:
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason,
    }}, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _override_block_lines(outcome: str, mode: object) -> str:
    """Block text for the override: how a person arms, and why an arm that exists did not help."""
    path = _arm_path_text()
    lines = [
        "A person can run this command themselves, in their own terminal.",
        "To get ONE permission prompt for the next blocked command instead, a person (never an agent)",
        "creates the arm file in their own terminal:",
        f"    PowerShell: New-Item -ItemType File -Force {_single_quote_powershell(path)}",
        f"    POSIX:      touch {_single_quote_posix(path)}",
        "The arm lasts 15 minutes and serves one command. It allows nothing by itself: it only leads to a",
        "prompt, and only where Claude Code asks for permission.",
    ]
    if outcome == "stale":
        lines.append("An arm file was found, but it was older than 15 minutes, so it was removed.")
    elif outcome == "unusable":
        lines.append("Something at the arm path was not a usable regular file, so it was removed.")
    elif outcome == "no-prompt-available":
        shown = mode if mode in ("dontAsk", "bypassPermissions", "auto") else "unknown"
        lines.append(f"An arm file exists, but the permission mode ({shown}) shows no prompt, so the command stays blocked.")
    return "".join(line + "\n" for line in lines)


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

    # Arm-write rule: runs before Guard deference and before every other rule, because it reads no
    # project rules. Only a person creates the Database override arm.
    arm_write = _arm_write_match(payload)
    if arm_write:
        return _refuse_arm_write(payload, tool_name, arm_write)

    # Guard deference: after the payload is read, before anything is classified.
    if _defers_to_project_copy(payload):
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
        # Database override arm: a person's arm turns this block into ONE permission prompt. Nothing
        # is allowed here, and a call that reaches no block never touches the arm.
        override_outcome = _try_override(payload)
        if override_outcome in ("claimed", "claimed-by-sibling"):
            _audit({**record, "decision": "ASK", "reason": override_outcome,
                    "block_reason": "writes-without-readonly",
                    "permission_mode": payload.get("permission_mode"),
                    "tool_use_id": payload.get("tool_use_id")})
            _print_ask(_PROMPT_WORDING)
            return 0
        if override_outcome == "absent":
            _audit({**record, "decision": "BLOCK", "reason": "writes-without-readonly"})
        else:
            _audit({**record, "decision": "BLOCK", "reason": override_outcome,
                    "block_reason": "writes-without-readonly",
                    "permission_mode": payload.get("permission_mode")})
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
            "\n"
            + _override_block_lines(override_outcome, payload.get("permission_mode"))
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
