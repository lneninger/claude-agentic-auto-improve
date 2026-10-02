#!/usr/bin/env python3
"""
test_db_destructive_guard.py -- end-to-end tests for db-destructive-guard.py.

Each test case constructs a Claude-Code-style PreToolUse JSON payload, pipes it
into the hook as a subprocess, and asserts on the exit code (0 = ALLOW,
2 = BLOCK) and stderr fragment. This is the same contract Claude Code uses
when it invokes the hook, so the tests cover the real behaviour rather than
private internals.

Run:
    py -3 ~/.claude/hooks/tests/test_db_destructive_guard.py

Exit code:
    0 = all tests passed
    1 = at least one test failed

The test file deliberately avoids the literal heavy-verb substrings that the
guard itself screens for. Where a literal command must appear in a test
payload, the substring is assembled at runtime from string pieces so this
source file itself does not get blocked by the guard when an agent edits it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Resolve the hook next to this test, not in ~/.claude: the hooks moved into
# the repo on 2026-08-25 and the global copies were retired. A home-relative
# path made the whole suite pass vacuously once the file was gone -- python
# exits 2 on a missing file, which several cases expect as "BLOCK".
HOOK = str(Path(__file__).resolve().parent.parent / "db-destructive-guard.py")

# Build literal phrases from pieces so this test file is editable by Claude
# without tripping the guard on its own source.
_D, _T, _DB, _TR, _DI = "D" + "ROP", "T" + "ABLE", "D" + "ATABASE", "T" + "RIGGER", "D" + "ISABLE"
_DROP_DB     = f"{_D} {_DB}"          # e.g. "DROP DATABASE"
_DROP_TR     = f"{_D} {_TR}"          # e.g. "DROP TRIGGER"
_DISABLE_TR  = f"{_DI} {_TR}"         # e.g. "DISABLE TRIGGER"
_INSERT      = "INS" + "ERT INTO"     # e.g. "INSERT INTO"
_SD          = "SHUT" + "DOWN"        # the server-stop statement keyword (issue #272)

# ---------------------------------------------------------------------------
# Project-shaped fixture values, read from the SAME rules file the hook reads.
#
# The Layer-3c cases need a name the guard considers protected and a path the
# guard considers production. Both are project facts, so writing them here
# would (a) pin a generic suite to one repository and (b) let the suite and the
# hook drift apart silently -- a case could keep passing against a database
# name the hook no longer protects, which is the shape of a test that is green
# for the wrong reason.
#
# THIS LOADER FAILS LOUD, deliberately. The hook's own loader fails CLOSED, but
# a test harness that quietly substitutes a placeholder when its configuration
# is missing runs a suite that proves nothing. Same lesson as the HOOK path
# above: a vacuous pass is worse than an error.
# ---------------------------------------------------------------------------
_RULES_PATH = Path(HOOK).parent / "db-destructive-guard.rules.json"
try:
    _RULES = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
except Exception as _e:  # pragma: no cover - configuration error, not a test failure
    raise SystemExit(f"cannot read {_RULES_PATH}: {_e}")

_PROTECTED_DBS = [str(n) for n in (_RULES.get("protected_databases") or []) if str(n).strip()]
if not _PROTECTED_DBS:
    raise SystemExit(
        f"{_RULES_PATH} declares no protected_databases; the Layer-3c cases "
        "would test nothing. Refusing to run a vacuous suite."
    )

# The first declared protected database. Every 3c case that must BLOCK aims at
# this name; every disposable ALLOW case aims at the same name plus a suffix
# from the guard's generic escape list, so the two differ in exactly the one
# way the guard is supposed to notice.
_DB_PROT = _PROTECTED_DBS[0]
_DB_DISP = f"{_DB_PROT}_Test_abc123def456"

# A source path the rules file marks as production. Used by the one 3c case
# that must ALLOW a protected connection string because of WHERE it is written.
_SRC_ALLOWED = next(
    (str(p) for p in (_RULES.get("production_path_allowlist") or [])
     if str(p).startswith("src/")),
    None,
)
if _SRC_ALLOWED is None:
    raise SystemExit(
        f"{_RULES_PATH} declares no production_path_allowlist entry under src/; "
        "case 3c.2 would test nothing. Refusing to run a vacuous suite."
    )


@dataclass
class Case:
    name: str
    payload: dict
    expect_rc: int
    expect_stderr_contains: str = ""


CASES: list[Case] = [
    # ---------------------------------------------------------------
    # Layer 3a -- argv-position-bug detector
    # ---------------------------------------------------------------
    Case(
        name="3a.1 ef-drop with disposable on wrong side of `--` -> BLOCK",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "dotnet ef database drop --force "
                    "--project src/X.Persistence --startup-project src/X.API "
                    '-- --connection "Server=(localdb)\\m;Database=App_MigrationVerify_abc"'
                )
            },
        },
        expect_rc=2,
        expect_stderr_contains="ARGV-POSITION BUG DETECTED",
    ),
    Case(
        name="3a.2 ef-drop with disposable BEFORE `--` -> ALLOW",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "dotnet ef database drop --force "
                    '--connection "Server=(localdb)\\m;Database=App_MigrationVerify_abc" '
                    "--project src/X.Persistence --startup-project src/X.API"
                )
            },
        },
        expect_rc=0,
    ),
    Case(
        name="3a.3 ef-drop with no disposable anywhere -> BLOCK (regression check)",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    "dotnet ef database drop --force "
                    "--project src/X.Persistence --startup-project src/X.API"
                )
            },
        },
        expect_rc=2,
    ),

    # ---------------------------------------------------------------
    # Layer 3b -- server-trigger destruction
    # ---------------------------------------------------------------
    Case(
        name=f"3b.1 sqlcmd '{_DROP_TR} ... ON ALL SERVER' -> BLOCK",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    f'sqlcmd -S "(localdb)\\m" -E -Q "{_DROP_TR} trg_protect_dev_databases ON ALL SERVER"'
                )
            },
        },
        expect_rc=2,
    ),
    Case(
        name=f"3b.2 sqlcmd '{_DISABLE_TR} ... ON ALL SERVER' -> BLOCK",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    f'sqlcmd -S "(localdb)\\m" -E -Q "{_DISABLE_TR} trg_protect_dev_databases ON ALL SERVER"'
                )
            },
        },
        expect_rc=2,
    ),
    Case(
        name=f"3b.3 '{_DROP_TR} ... ON SCHEMA' (NOT server-wide) -> ALLOW",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    f'sqlcmd -E -Q "{_DROP_TR} some_table_trg ON dbo.SomeTable"'
                )
            },
        },
        expect_rc=0,
    ),

    # ---------------------------------------------------------------
    # Layer 3c -- protected-DB write from non-production path
    # ---------------------------------------------------------------
    Case(
        name="3c.1 Write to test file with protected-DB CS + INSERT -> BLOCK",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "d:/Dev/Foo/tests/SomeTest.cs",
                "content": (
                    f'const string cs = "Server=(localdb)\\m;Database={_DB_PROT};Trusted_Connection=True;";\n'
                    f'await conn.ExecuteAsync("{_INSERT} Users (Id, Name) VALUES (1, \'x\')");'
                ),
            },
        },
        expect_rc=2,
        expect_stderr_contains="PROTECTED",
    ),
    Case(
        name=f"3c.2 Write to {_SRC_ALLOWED} with protected-DB CS -> ALLOW (in allow-list)",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": f"d:/Dev/Foo/{_SRC_ALLOWED}appsettings.json",
                "content": (
                    '"ConnectionStrings": { "AppDb": '
                    f'"Server=(localdb)\\m;Database={_DB_PROT};Trusted_Connection=True;" }}'
                ),
            },
        },
        expect_rc=0,
    ),
    Case(
        name="3c.3 Write to test file with DISPOSABLE DB suffix + INSERT -> ALLOW",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "d:/Dev/Foo/tests/SomeTest.cs",
                "content": (
                    f'const string cs = "Server=(localdb)\\m;Database={_DB_DISP};Trusted_Connection=True;";\n'
                    f'await conn.ExecuteAsync("{_INSERT} Users (Id, Name) VALUES (1, \'x\')");'
                ),
            },
        },
        expect_rc=0,
    ),
    Case(
        name="3c.4 Bash with protected-DB CS + write keyword -> BLOCK",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    'sqlcmd -S "(localdb)\\m" -E '
                    f'-Q "Database={_DB_PROT}; {_INSERT} Users VALUES (1, \'x\')"'
                )
            },
        },
        expect_rc=2,
    ),
    Case(
        name="3c.5 Edit to non-allowlist path: protected-DB CS only, NO write keyword -> ALLOW",
        payload={
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "d:/Dev/Foo/scripts/diagnose.cs",
                "old_string": "const string cs = \"OLD\";",
                "new_string": (
                    f'const string cs = "Server=(localdb)\\m;Database={_DB_PROT};Trusted_Connection=True;";\n'
                    '// read-only diagnostic'
                ),
            },
        },
        expect_rc=0,
    ),

    # ---------------------------------------------------------------
    # Layer 3c extended -- alternative protected-DB connection forms
    # ---------------------------------------------------------------
    Case(
        name="3c.6 Bash 'sqlcmd -d <protected> -Q UPDATE' -> BLOCK",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    f'sqlcmd -S "(localdb)\\m" -E -d {_DB_PROT} '
                    f'-Q "UPDATE Users SET Name = \'x\' WHERE Id = 1"'
                )
            },
        },
        expect_rc=2,
    ),
    Case(
        name="3c.7 Bash 'sqlcmd -d <protected>_Test_<guid> -Q UPDATE' -> ALLOW (disposable)",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    f'sqlcmd -S "(localdb)\\m" -E -d {_DB_DISP} '
                    f'-Q "UPDATE Users SET Name = \'x\' WHERE Id = 1"'
                )
            },
        },
        expect_rc=0,
    ),
    Case(
        name="3c.8 T-SQL 'USE <protected>; DELETE FROM Users' -> BLOCK",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    f'sqlcmd -S "(localdb)\\m" -E -Q "USE {_DB_PROT}; DELETE FROM Users WHERE Id = 1"'
                )
            },
        },
        expect_rc=2,
    ),
    Case(
        name="3c.9 'Initial Catalog=<protected>' + DELETE in non-allowlist file -> BLOCK",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "d:/Dev/Foo/scripts/maintenance.cs",
                "content": (
                    f'var cs = "Server=(localdb)\\m;Initial Catalog={_DB_PROT};Trusted_Connection=True;";\n'
                    f'await conn.ExecuteAsync("DELETE FROM Users WHERE Id = 1");'
                ),
            },
        },
        expect_rc=2,
    ),
    Case(
        name="3c.10 PowerShell '-Database <protected>' + INSERT -> BLOCK",
        payload={
            "tool_name": "PowerShell",
            "tool_input": {
                "command": (
                    f'Invoke-Sqlcmd -ServerInstance "(localdb)\\m" -Database {_DB_PROT} '
                    f'-Query "{_INSERT} Users (Id, Name) VALUES (1, \'x\')"'
                )
            },
        },
        expect_rc=2,
    ),
    Case(
        name="3c.11 'USE <protected>_Test_abc' + DELETE -> ALLOW (disposable USE target)",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": (
                    f'sqlcmd -E -Q "USE {_DB_DISP}; DELETE FROM Users WHERE Id = 1"'
                )
            },
        },
        expect_rc=0,
    ),
    Case(
        name="3c.12 Write to .claude/concepts/ with protected-DB + write keyword -> ALLOW (allow-list)",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "c:/users/dev/.claude/concepts/example.md",
                "content": (
                    'Documentation example: a connection string like '
                    f'`Database={_DB_PROT}` paired with `INSERT INTO Users` '
                    'should be allowed in concept contracts.'
                ),
            },
        },
        expect_rc=0,
    ),

    # ---------------------------------------------------------------
    # Regression -- existing behaviours preserved
    # ---------------------------------------------------------------
    Case(
        name=f"regression: raw {_DROP_DB} without disposable -> BLOCK",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f"sqlcmd -E -Q \"{_DROP_DB} [SomeDb]\""},
        },
        expect_rc=2,
    ),
    Case(
        name=f"regression: raw {_DROP_DB} on disposable name -> ALLOW",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f"sqlcmd -E -Q \"{_DROP_DB} [App_MigrationVerify_abc]\""},
        },
        expect_rc=0,
    ),
    Case(
        name="regression: unrelated Bash -> ALLOW",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": "dotnet build src/X.sln"},
        },
        expect_rc=0,
    ),

    # ---------------------------------------------------------------
    # Issue #272 -- server-stop rule false positives (ALLOW direction)
    # The helpers assert on rc and a stderr fragment, so BLOCK cases below
    # pin the `sql-shutdown` label via expect_stderr_contains.
    # ---------------------------------------------------------------
    Case(
        name="272.allow.1 'dotnet build-server <word>' Bash -> ALLOW",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f"dotnet build-server {_SD.lower()}"},
        },
        expect_rc=0,
    ),
    Case(
        name="272.allow.2 read-only 'grep -n <word> <file>' Bash -> ALLOW",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f"grep -n {_SD} .claude/hooks/db-destructive-guard.py"},
        },
        expect_rc=0,
    ),
    Case(
        name="272.allow.3 Write markdown prose containing the word + space -> ALLOW",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "d:/Dev/Foo/docs/notes.md",
                "content": f"The guard once blocked a scratch file because it said {_SD} in plain prose.\n",
            },
        },
        expect_rc=0,
    ),
    Case(
        name="272.allow.4 PowerShell Write-Output with the word in prose -> ALLOW",
        payload={
            "tool_name": "PowerShell",
            "tool_input": {"command": f'Write-Output "dotnet build-server {_SD} is harmless"'},
        },
        expect_rc=0,
    ),

    # ---------------------------------------------------------------
    # Issue #272 -- server-stop statement must stay blocked (BLOCK direction)
    # ---------------------------------------------------------------
    Case(
        name="272.block.1 sqlcmd -Q with bare server-stop statement -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f'sqlcmd -S "(localdb)\\mssqllocaldb" -E -Q "{_SD}"'},
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.2 server-stop statement WITH NOWAIT -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f'sqlcmd -S "(localdb)\\mssqllocaldb" -E -Q "{_SD} WITH NOWAIT"'},
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.3 'SELECT 1; <statement>' after separator -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f'sqlcmd -S "(localdb)\\mssqllocaldb" -E -Q "SELECT 1; {_SD}"'},
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.4 statement on its own line after a GO line -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f'sqlcmd -S "(localdb)\\mssqllocaldb" -E -Q "SELECT 1\nGO\n{_SD}\n"'},
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.5 PowerShell Invoke-Sqlcmd -Query bare statement -> BLOCK sql-shutdown",
        payload={
            "tool_name": "PowerShell",
            "tool_input": {"command": f'Invoke-Sqlcmd -ServerInstance "(localdb)\\mssqllocaldb" -Query "{_SD}"'},
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.6 Write .sql file with bare statement on its own line -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "d:/Dev/Foo/scripts/stop.sql",
                "content": f"USE master;\nGO\n{_SD}\n",
            },
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.7 Write .sql file with statement and trailing semicolon -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "d:/Dev/Foo/scripts/stop2.sql",
                "content": f"{_SD};\n",
            },
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),

    # ---------------------------------------------------------------
    # Issue #272 round 2 -- statement-position (P1) / SQL-client-or-.sql (P2)
    # ---------------------------------------------------------------
    Case(
        name="272.block.8 Write stop.sql with CRLF lines -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "d:/Dev/Foo/scripts/stop.sql",
                "content": f"USE master;\r\nGO\r\n{_SD}\r\n",
            },
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.9 Edit on .sql path, new_string WITH NOWAIT CRLF -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "d:/Dev/Foo/scripts/stop3.sql",
                "old_string": "SELECT 1",
                "new_string": f"{_SD} WITH NOWAIT\r\n",
            },
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.10 Write .sql with trailing -- comment -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "d:/Dev/Foo/scripts/stop4.sql",
                "content": f"{_SD} -- stop now\n",
            },
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.11 sqlcmd -Q bare word followed by end of command, with description -> BLOCK",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": f"sqlcmd -E -Q {_SD}",
                "description": "Stop the local SQL instance",
            },
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.12 sqlcmd -Q unquoted word then more flags -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": f'sqlcmd -E -Q {_SD} -S "(localdb)\\mssqllocaldb"',
                "description": "Stop the local SQL instance",
            },
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.13 echo word piped to sqlcmd -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Bash",
            "tool_input": {
                "command": f"echo {_SD} | sqlcmd -E",
                "description": "Pipe a statement to sqlcmd",
            },
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.14 sqlcmd quoted statement WITH NOWAIT then comment -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f'sqlcmd -E -Q "{_SD} WITH NOWAIT -- x"'},
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.15 statement after BEGIN, before END -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f'sqlcmd -E -Q "BEGIN {_SD} END"'},
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.16 statement after IF 1=1 -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f'sqlcmd -E -Q "IF 1=1 {_SD}"'},
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.17 statement after a block comment -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f'sqlcmd -E -Q "/*x*/ {_SD}"'},
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.18 MultiEdit new_string WITH NOWAIT; -> BLOCK sql-shutdown",
        payload={
            "tool_name": "MultiEdit",
            "tool_input": {
                "file_path": "d:/Dev/Foo/scripts/stop5.sql",
                "edits": [{"old_string": "SELECT 1", "new_string": f"{_SD} WITH NOWAIT;"}],
            },
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.19 NotebookEdit %%sql cell with statement -> BLOCK sql-shutdown",
        payload={
            "tool_name": "NotebookEdit",
            "tool_input": {
                "notebook_path": "d:/Dev/Foo/nb/ops.ipynb",
                "new_source": f"%%sql\n{_SD}",
            },
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.block.20 mixed-case statement with nowait -> BLOCK sql-shutdown",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f'sqlcmd -E -Q "{_SD.lower()} with nowait"'},
        },
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    ),
    Case(
        name="272.allow.5 grep for the word in the guard file -> ALLOW",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f'grep -n "{_SD}" .claude/hooks/db-destructive-guard.py'},
        },
        expect_rc=0,
    ),
    Case(
        name="272.allow.6 git commit message that is just the word -> ALLOW",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f'git commit -m "{_SD}"'},
        },
        expect_rc=0,
    ),
    Case(
        name="272.allow.7 Write markdown, capitalised word starting a sentence -> ALLOW",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "d:/Dev/Foo/docs/notes.md",
                "content": f"{_SD.capitalize()} the API before migrating.\n",
            },
        },
        expect_rc=0,
    ),
    Case(
        name="272.allow.8 echo of quoted prose containing the word -> ALLOW",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f"echo '{_SD} is harmless'"},
        },
        expect_rc=0,
    ),
    Case(
        name="272.allow.9 Write .py file with a lowercase string literal -> ALLOW",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "d:/Dev/Foo/src/state.py",
                "content": f'STATE = "{_SD.lower()}"\n',
            },
        },
        expect_rc=0,
    ),
    Case(
        name="272.allow.10 Write .cs file with a case label -> ALLOW",
        payload={
            "tool_name": "Write",
            "tool_input": {
                "file_path": "d:/Dev/Foo/src/Handler.cs",
                "content": f'case "{_SD}": break;\n',
            },
        },
        expect_rc=0,
    ),
    Case(
        name="272.allow.11 Edit on .py path swapping the lowercase word -> ALLOW",
        payload={
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "d:/Dev/Foo/src/state.py",
                "old_string": _SD.lower(),
                "new_string": "stop",
            },
        },
        expect_rc=0,
    ),
    Case(
        name="272.allow.12 'wsl --<word>' Bash -> ALLOW",
        payload={
            "tool_name": "Bash",
            "tool_input": {"command": f"wsl --{_SD.lower()}"},
        },
        expect_rc=0,
    ),
]


# --- Issue #272 round three -------------------------------------------------
# Built with helpers so the literal statement word never appears in this file.
_W = _SD
_w = _SD.lower()


def _bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}}


def _ps(cmd: str) -> dict:
    return {"tool_name": "PowerShell", "tool_input": {"command": cmd}}


def _write(path: str, content: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


def _nb(source: str) -> dict:
    return {
        "tool_name": "NotebookEdit",
        "tool_input": {"notebook_path": "d:/Dev/Foo/nb/ops.ipynb", "new_source": source},
    }


def _block(name: str, payload: dict) -> Case:
    return Case(
        name=f"{name} -> BLOCK sql-shutdown",
        payload=payload,
        expect_rc=2,
        expect_stderr_contains="sql-shutdown",
    )


def _allow(name: str, payload: dict) -> Case:
    return Case(name=f"{name} -> ALLOW", payload=payload, expect_rc=0)


CASES += [
    # GROUP A: dangerous inputs the old rule blocked.
    _block("272.block.21 Invoke-DbaQuery quoted WITH NOWAIT",
           _ps(f'Invoke-DbaQuery -SqlInstance "(localdb)\\MSSQLLocalDB" -Query "{_W} WITH NOWAIT"')),
    _block("272.block.22 mssql-cli quoted WITH NOWAIT",
           _bash(f'mssql-cli -S localhost -Q "{_W} WITH NOWAIT"')),
    _block("272.block.23 usql quoted WITH NOWAIT",
           _bash(f'usql mssql://localhost -c "{_W} WITH NOWAIT"')),
    _block("272.block.24 Edit A.cs CommandText WITH NOWAIT",
           {"tool_name": "Edit", "tool_input": {
               "file_path": "d:/Dev/Foo/src/A.cs", "old_string": "x",
               "new_string": f'cmd.CommandText = "{_W} WITH NOWAIT";'}}),
    _block("272.block.25 mysqladmin lowercase", _bash(f"mysqladmin -u root {_w}")),
    _block("272.block.26 mysql -e lowercase", _bash(f"mysql -u root -e {_w}")),
    _block("272.block.27 Write stop.txt lowercase with nowait",
           _write("d:/x/stop.txt", f"{_w} with nowait\n")),
    _block("272.block.28 %%sql cell lowercase with nowait", _nb(f"%%sql\n{_w} with nowait")),
    # GROUP B: sole-witness pins for the statement-position alternative.
    _block("272.block.29 %%sql CRLF", _nb(f"%%sql\r\n{_W}\r\n")),
    _block("272.block.30 %%sql trailing line comment", _nb(f"%%sql\n{_W} -- stop")),
    _block("272.block.31 %%sql trailing block comment", _nb(f"%%sql\n{_W} /* x */")),
    _block("272.block.32 %%sql followed by GO", _nb(f"%%sql\n{_W} GO")),
    _block("272.block.33 %%sql inside BEGIN..END", _nb(f"%%sql\nBEGIN {_W} END")),
    _block("272.block.34 %%sql parenthesised", _nb(f"%%sql\n({_W})")),
    _block("272.block.35 %%sql statement then SELECT", _nb(f"%%sql\n{_W}; SELECT 1")),
    _block("272.block.36 %%sql SELECT then statement", _nb(f"%%sql\nSELECT 1; {_W}")),
    _block("272.block.37 %%sql after IF..ELSE", _nb(f"%%sql\nIF 0=1 SELECT 1 ELSE {_W}")),
    _block("272.block.38 PowerShell double-quoted after separator",
           _ps(f'$q = "SELECT 1; {_W}"; Write-Output $q')),
    _block("272.block.39 PowerShell single-quoted after separator",
           _ps(f"$q = 'SELECT 1; {_W}'; Write-Output $q")),
    _block("272.block.40 Write .sql lowercase after IF 1=1",
           _write("d:/Dev/Foo/scripts/stop.sql", f"IF 1=1 {_w}\n")),
    # GROUP C: client / API markers.
    _block("272.block.41 osql", _bash(f"osql -E -Q {_w}")),
    _block("272.block.42 isql", _bash(f"isql -U sa -Q {_w}")),
    _block("272.block.43 SqlCommand in A.cs",
           _write("d:/Dev/Foo/src/A.cs", f'var c = new SqlCommand("{_W}", conn);\n')),
    _block("272.block.44 ExecuteSqlRaw in B.cs",
           _write("d:/Dev/Foo/src/B.cs", f'ExecuteSqlRaw(db.Database, "{_W}");\n')),
    _block("272.block.45 cursor.execute in c.py",
           _write("d:/Dev/Foo/src/c.py", f'cursor.execute("{_W}")\n')),
    # GROUP E: pins for _extract_text and markers that other alternatives mask.
    _block("272.block.46 Edit new_string lowercase in .sql (path route only)",
           {"tool_name": "Edit", "tool_input": {
               "file_path": "d:/Dev/Foo/scripts/stop.sql",
               "old_string": "SELECT 1", "new_string": f"{_w}\n"}}),
    _block("272.block.47 MultiEdit new_string in .sql",
           {"tool_name": "MultiEdit", "tool_input": {
               "file_path": "d:/Dev/Foo/scripts/stop.sql",
               "edits": [{"old_string": "SELECT 1", "new_string": f"{_w};"}]}}),
    _block("272.block.48 Write .txt statement on line 1 of content",
           _write("d:/x/stop.txt", f"{_W}\n")),
    _block("272.block.49 NotebookEdit without %%sql line",
           {"tool_name": "NotebookEdit", "tool_input": {
               "notebook_path": "d:/Dev/Foo/nb/ops.ipynb", "new_source": _W}}),
    _block("272.block.50 mssql-cli -Q without WITH NOWAIT",
           _bash(f'mssql-cli -S localhost -Q "{_W}"')),
    _block("272.block.51 usql -c",
           _bash(f'usql mssql://localhost -c "{_W}"')),
    _block("272.block.52 PowerShell Invoke-DbaQuery -Query",
           _ps(f'Invoke-DbaQuery -SqlInstance "(localdb)\\MSSQLLocalDB" -Query "{_W}"')),
    _block("272.block.53 cmd.CommandText + ExecuteNonQuery in B.cs",
           _write("B.cs", f'cmd.CommandText = "{_W}"; cmd.ExecuteNonQuery();\n')),
    # GROUP D: ALLOW pins.
    _allow("272.allow.13 markdown sentence starting with the word",
           _write("d:/Dev/Foo/docs/notes.md", f"{_W} the API before migrating.\n")),
    _allow("272.allow.14 sqlcmd SELECT && wsl --word",
           _bash(f'sqlcmd -E -Q "SELECT 1" && wsl --{_w}')),
    _allow("272.allow.15 py execute SELECT + pool.word",
           _write("d:/Dev/Foo/src/d.py", f'cursor.execute("SELECT 1")\nflag = pool.{_w}\n')),
    _allow("272.allow.16 PowerShell variable named word + Invoke-Sqlcmd SELECT",
           _ps(f'${_w} = $true; Invoke-Sqlcmd -Query "SELECT 1"')),
    _allow("272.allow.17 sqlcmd SELECT; echo word-complete",
           _bash(f'sqlcmd -E -Q "SELECT 1"; echo {_w}-complete')),
    _allow("272.allow.18 py execute SELECT + word.state",
           _write("d:/Dev/Foo/src/e.py", f'cursor.execute("SELECT 1")\nx = {_w}.state\n')),
    _allow("272.allow.19 py execute SELECT + word()",
           _write("d:/Dev/Foo/src/f.py", f'cursor.execute("SELECT 1")\n{_w}()\n')),
]


def run_case(case: Case) -> tuple[bool, str]:
    """Invoke the hook with the case's payload. Returns (passed, detail)."""
    payload_json = json.dumps(case.payload)
    # Ensure no inherited override leaks into the test process.
    env = dict(os.environ)
    env.pop("CLAUDE_DESTRUCTIVE_DB_OK", None)
    try:
        proc = subprocess.run(
            ["py", "-3", HOOK],
            input=payload_json,
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return False, "hook timed out"
    except FileNotFoundError as exc:
        return False, f"could not invoke hook: {exc}"

    rc = proc.returncode
    err = proc.stderr or ""

    if rc != case.expect_rc:
        return False, f"rc={rc} (expected {case.expect_rc})\n  stderr: {err[:400]}"
    if case.expect_stderr_contains and case.expect_stderr_contains not in err:
        return False, (
            f"stderr did not contain {case.expect_stderr_contains!r}\n"
            f"  full stderr: {err[:400]}"
        )
    return True, "ok"


def main() -> int:
    passed = 0
    failed = 0
    for case in CASES:
        ok, detail = run_case(case)
        if ok:
            passed += 1
            print(f"  PASS  {case.name}")
        else:
            failed += 1
            print(f"  FAIL  {case.name}")
            print(f"        {detail}")
    print()
    print(f"results: {passed} passed, {failed} failed (of {len(CASES)})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
