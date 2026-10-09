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
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass, field
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
#
# PLUGIN PORT (contract 2026-09-28-hook-server-modes, amendment 2026-10-09, INV-O7, sub-task 23).
# This suite is this repository's current one. The ONLY change for the plugin: the project's rules do
# not sit beside the hook (the plugin ships a fictional template there). A FIXTURE PROJECT supplies this
# project's database names instead: every case runs with CLAUDE_PROJECT_DIR naming a temporary folder
# whose .claude/hooks/db-destructive-guard.rules.json is the text below (INV-O3: the guard reads the
# project's file, never the plugin's template). The text copies this project's rules and names
# ScalpingMachine and ScalpingMachine_Testing, as the contract requires.
_RULES = {
    "protected_databases": ["ScalpingMachine", "ScalpingMachine_Testing"],
    "production_path_allowlist": [
        "src/scalpingmachine.api/",
        "src/scalpingmachine.persistence/",
        "tools/db-protection/",
        ".claude/",
        "/.claude/",
        "docs/",
    ],
    "human_only_commands": [
        {"script": "tools/db-protection/update-dev-database.cmd"},
        {"script": "tools/db-protection/restore-latest.cmd", "flag": "--recover-missing-dev-db"},
    ],
}
_RULES_PATH = Path("<fixture project>/.claude/hooks/db-destructive-guard.rules.json")

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
    # --- Fields used by the dev-DB-protection hardening cases (contract 2026-10-04) -----------------
    # Run with CLAUDE_PROJECT_DIR pointed at a throwaway directory, so the guard's audit record lands
    # in a log this run owns instead of the project's real one.
    isolate: bool = False
    # When set, the payload carries this (unique) session id, and the case reads the guard's OWN audit
    # record for it. A guard that crashes before deciding exits 0 with no record, so a crash cannot
    # pass an ALLOW case that demands a record (contract Failure Modes, critic blocker 4).
    session_id: str = ""
    expect_audit_decision: str = ""      # "ALLOW" or "BLOCK"
    expect_audit_reason: str = ""
    expect_targets: bool = False         # the record must carry a non-empty destructive_targets list
    env_extra: dict = field(default_factory=dict)
    # Run a copy of the hook that has NO rules file beside it (the fail-closed path, INV-9).
    rules_missing: bool = False
    # Run a copy of the hook whose rules file is the REAL one with these keys replaced (round 2: a value
    # of the wrong type must fail closed). The real rules file is never edited.
    rules_override: dict = field(default_factory=dict)


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


# ===========================================================================
# Dev-DB protection hardening (contract 2026-10-04-dev-db-protection-hardening.md)
#
# One or more cases per class of the Destructive Target binding table, on both
# sides (BLOCK and ALLOW), each tripping ONE clause. Four rules govern this block:
#
#   1. Every destructive verb and command is assembled from parts below, so this
#      file never contains the literal text the guard (or its successor) screens for.
#   2. EVERY ALLOW case for a destructive input carries a unique session id and
#      demands the guard's OWN audit record for it (decision ALLOW, with a
#      non-empty destructive_targets list). The guard fails open on an uncaught
#      error, exiting 0 with no record, so a bare "rc == 0" cannot tell a real
#      allow from a crash.
#   3. A disposable marker that sits ANYWHERE except on the operation's own
#      target (a comment, an echo, a second statement) must NOT exempt it. The
#      "marker in a comment" cases pin that for each class.
#   4. No case sets or reads the human override variable. Agents never set it.
# ===========================================================================
_DROP_TBL = f"{_D} {_T}"
_DROP_SCHEMA = f"{_D} SCH" + "EMA"
_TRUNC_TBL = "TRUN" + f"CATE {_T}"
_ALTER_DB = "AL" + f"TER {_DB}"
_RESTORE_DB = "REST" + f"ORE {_DB}"
_EF_DROP = "dotnet ef database " + "dr" + "op"
_EF_UPD = "dotnet ef database " + "up" + "date"
_EF_MIG_RM = "dotnet ef migrations " + "re" + "move"
_LDB_DEL = "sqllocaldb " + "de" + "lete"
_PG_DROP = "dr" + "opdb"
_MY_DROP = "dr" + "op"
_MONGO_DROP_DB = "db.dr" + "opDatabase()"
_ENSURE_DEL = "Ensure" + "Deleted"
_FLUSH_ALL = "FLUSH" + "ALL"
_FLUSH_DB = "FLUSH" + "DB"
_COSMOS_DEL = ".delete" + "Database("
_MDF = ".md" + "f"
_LDF = ".ld" + "f"
_RM, _DEL, _RD, _RMITEM = "r" + "m", "de" + "l", "r" + "d", "Remove" + "-Item"
_LDB_DIR = "Microsoft\\Microsoft SQL Server Local" + " DB\\Instances"
_SQLPKG_OFF = "/p:Block" + "OnPossibleDataLoss=Fa" + "lse"

# Disposable markers placed OFF the target (inside a comment or an echo).
_MARK = "Foo_Test_0a1b2c3d4e5f"
_DISP = "Foo_Test_0a1b2c3d4e5f"          # an on-target disposable name
_DISP_MV = "App_MigrationVerify_abc"
_UPD_CMD = "tools/db-protection/update-dev-database.cmd"
_RESTORE_CMD = "tools/db-protection/restore-latest.cmd"
_RECOVER_FLAG = "--recover-missing-dev-db"
_BANNER_INTERNAL = "[db-destructive-guard] BLOCKED: internal error while reading the target of"
_BANNER_INTERNAL_TAIL = "failing closed."


def _sid() -> str:
    return f"dbp-{uuid.uuid4().hex}"


def _blk(name: str, payload: dict, frag: str = "") -> Case:
    """A BLOCK case. Isolated so its audit record never reaches the project log."""
    return Case(name=f"{name} -> BLOCK", payload=payload, expect_rc=2,
                expect_stderr_contains=frag, isolate=True)


def _ok(name: str, payload: dict) -> Case:
    """An ALLOW case for an input that is NOT a destructive operation (a control)."""
    return Case(name=f"{name} -> ALLOW", payload=payload, expect_rc=0, isolate=True)


def _ok_audited(name: str, payload: dict) -> Case:
    """An ALLOW case for a DESTRUCTIVE input: the guard's own audit record must say ALLOW."""
    return Case(name=f"{name} -> ALLOW (audited)", payload=payload, expect_rc=0, isolate=True,
                session_id=_sid(), expect_audit_decision="ALLOW", expect_targets=True)


def _edit(path: str, new: str) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": path, "old_string": "x", "new_string": new}}


_HASH_MARK = f"# cleanup of {_MARK}"

CASES += [
    # -----------------------------------------------------------------------------------------
    # Class A -- database-level statements. Target = the name after the database keyword.
    # -----------------------------------------------------------------------------------------
    _blk("dbp.A.1 database drop, protected target, no marker  [passes today]",
         _bash(f'sqlcmd -E -Q "{_DROP_DB} [{_DB_PROT}]"')),
    _blk("dbp.A.2 database drop of an unprotected name, marker only in a trailing SQL comment",
         _bash(f'sqlcmd -E -Q "{_DROP_DB} [SomeDb] -- cleanup of {_MARK}"')),
    _blk("dbp.A.3 database drop of an unprotected name, marker only in an echo before it",
         _bash(f'echo {_MARK}; sqlcmd -E -Q "{_DROP_DB} [SomeDb]"')),
    _blk("dbp.A.4 two drops: first unprotected+undisposable, second disposable (every target must be disposable)",
         _bash(f'sqlcmd -E -Q "{_DROP_DB} [SomeDb]; {_DROP_DB} [{_DISP}]"')),
    _blk("dbp.A.5 two drops: protected then disposable (the existing veto)  [passes today]",
         _bash(f'sqlcmd -E -Q "{_DROP_DB} [{_DB_PROT}]; {_DROP_DB} [{_DISP}]"')),
    _ok_audited("dbp.A.6 database drop, disposable target",
                _bash(f'sqlcmd -E -Q "{_DROP_DB} [{_DISP_MV}]"')),
    _ok_audited("dbp.A.7 two drops, both disposable",
                _bash(f'sqlcmd -E -Q "{_DROP_DB} [{_DISP}]; {_DROP_DB} [Bar_Test_1a2b3c4d5e6f]"')),
    _blk("dbp.A.8 alter to offline, protected target",
         _bash(f'sqlcmd -E -Q "{_ALTER_DB} [{_DB_PROT}] SET OFFLINE"')),
    _blk("dbp.A.9 alter to single-user, unprotected name, marker only in a trailing comment",
         _bash(f'sqlcmd -E -Q "{_ALTER_DB} [SomeDb] SET SINGLE_USER -- {_MARK}"')),
    _blk("dbp.A.10 alter to emergency, protected target",
         _bash(f'sqlcmd -E -Q "{_ALTER_DB} [{_DB_PROT}] SET EMERGENCY"')),
    _ok_audited("dbp.A.11 alter to single-user, disposable target",
                _bash(f'sqlcmd -E -Q "{_ALTER_DB} [{_DISP}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"')),
    _blk("dbp.A.12 restore with replace, protected target, marker only in a trailing shell comment",
         _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DB_PROT}] FROM DISK = N'x.bak' WITH REPLACE\" {_HASH_MARK}")),
    _blk("dbp.A.13 restore with replace, protected target, no marker  [passes today]",
         _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DB_PROT}] FROM DISK = N'x.bak' WITH REPLACE\"")),
    _ok_audited("dbp.A.14 restore with replace, disposable target",
                _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DISP}] FROM DISK = N'x.bak' WITH REPLACE\"")),

    # -----------------------------------------------------------------------------------------
    # Class A' -- predicate sweep. Target = the LIKE predicate.
    # -----------------------------------------------------------------------------------------
    _ok_audited("dbp.A'.1 sweep whose predicate is the disposable LIKE form",
                _bash("sqlcmd -E -Q \"DECLARE @s nvarchar(max)=''; "
                      f"SELECT @s += '{_DROP_DB} [' + name + '];' FROM sys.databases "
                      "WHERE name LIKE '%[_]Test[_]%'; EXEC(@s)\"")),
    _blk("dbp.A'.2 sweep with the disposable LIKE form that ALSO names a protected database",
         _bash("sqlcmd -E -Q \"DECLARE @s nvarchar(max)=''; "
               f"SELECT @s += '{_DROP_DB} [' + name + '];' FROM sys.databases "
               f"WHERE name LIKE '%[_]Test[_]%' OR name = '{_DB_PROT}'; EXEC(@s)\"")),
    _blk("dbp.A'.3 sweep with a non-disposable predicate  [passes today]",
         _bash("sqlcmd -E -Q \"DECLARE @s nvarchar(max)=''; "
               f"SELECT @s += '{_DROP_DB} [' + name + '];' FROM sys.databases "
               "WHERE name LIKE 'Scalping%'; EXEC(@s)\"")),
    _blk("dbp.A'.4 sweep with a non-disposable predicate, disposable LIKE form only in a comment",
         _bash("sqlcmd -E -Q \"DECLARE @s nvarchar(max)=''; "
               f"SELECT @s += '{_DROP_DB} [' + name + '];' FROM sys.databases "
               "WHERE name LIKE 'Scalping%'; EXEC(@s) -- was '%[_]Test[_]%'\"")),

    # -----------------------------------------------------------------------------------------
    # Class B -- table-level statements. Target = the session database.
    # -----------------------------------------------------------------------------------------
    _blk("dbp.B.1 table drop, no session database, no marker  [passes today]",
         _bash(f'sqlcmd -E -Q "{_DROP_TBL} dbo.Users"')),
    _blk("dbp.B.2 table drop, session database protected (-d)  [passes today]",
         _bash(f'sqlcmd -E -d {_DB_PROT} -Q "{_DROP_TBL} dbo.Users"')),
    _blk("dbp.B.3 table drop, NO session database named, marker only in a trailing comment (unresolved)",
         _bash(f'sqlcmd -E -Q "{_DROP_TBL} dbo.Users" {_HASH_MARK}')),
    _blk("dbp.B.4 table drop, session database unprotected and not disposable, marker in a comment",
         _bash(f'sqlcmd -E -d SomeDb -Q "{_DROP_TBL} dbo.Users" {_HASH_MARK}')),
    _blk("dbp.B.5 truncate, no session database, marker only in a trailing comment",
         _bash(f'sqlcmd -E -Q "{_TRUNC_TBL} dbo.Users" {_HASH_MARK}')),
    _blk("dbp.B.6 schema drop, no session database, marker only in a trailing comment",
         _bash(f'sqlcmd -E -Q "{_DROP_SCHEMA} Staging" {_HASH_MARK}')),
    _ok_audited("dbp.B.7 table drop, session database disposable (-d)",
                _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} dbo.Users"')),
    _ok_audited("dbp.B.8 table drop, session database disposable (USE)",
                _bash(f'sqlcmd -E -Q "USE [{_DISP}]; {_DROP_TBL} dbo.Users"')),
    _ok_audited("dbp.B.9 truncate, session database disposable (Initial Catalog)",
                _ps(f'Invoke-Sqlcmd -ConnectionString "Server=(localdb)\\m;Initial Catalog={_DISP}" '
                    f'-Query "{_TRUNC_TBL} dbo.Users"')),

    # -----------------------------------------------------------------------------------------
    # Class C -- EF commands. Target = Database=/Initial Catalog= inside --connection, before `--`.
    # -----------------------------------------------------------------------------------------
    _blk("dbp.C.1 ef database removal, marker only in a trailing shell comment",
         _bash(f"{_EF_DROP} --force --project src/X.Persistence {_HASH_MARK}")),
    _blk("dbp.C.2 ef database removal bound to a protected Initial Catalog, marker in an echo",
         _bash(f'{_EF_DROP} --force --connection "Server=(localdb)\\m;Initial Catalog={_DB_PROT}"; echo {_MARK}')),
    _blk("dbp.C.3 rollback to zero (positional target), no connection",
         _bash(f"{_EF_UPD} 0 --project src/X.Persistence")),
    _blk("dbp.C.4 update to a named migration (positional target), no connection",
         _bash(f"{_EF_UPD} 20260101000000_Init --project src/X.Persistence")),
    _blk("dbp.C.5 rollback with the disposable connection placed AFTER `--` (argv-position)",
         _bash(f'{_EF_UPD} 0 --project src/X.Persistence -- --connection "Server=(localdb)\\m;Database={_DISP_MV}"')),
    _ok_audited("dbp.C.6 rollback bound to a disposable --connection before `--`",
                _bash(f'{_EF_UPD} 0 --connection "Server=(localdb)\\m;Database={_DISP_MV}" --project src/X.Persistence')),
    _blk("dbp.C.7 migrations removal, no connection",
         _bash(f"{_EF_MIG_RM} --project src/X.Persistence")),
    _blk("dbp.C.8 migrations removal bound to a protected database, marker in an echo",
         _bash(f'{_EF_MIG_RM} --connection "Server=(localdb)\\m;Database={_DB_PROT}"; echo {_MARK}')),
    _ok_audited("dbp.C.9 migrations removal bound to a disposable --connection",
                _bash(f'{_EF_MIG_RM} --connection "Server=(localdb)\\m;Database={_DISP_MV}" --project src/X.Persistence')),
    _ok_audited("dbp.C.10 ef database removal bound to a disposable --connection (audited twin of 3a.2)",
                _bash(f'{_EF_DROP} --force --connection "Server=(localdb)\\m;Database={_DISP_MV}" --project src/X.Persistence')),

    # -----------------------------------------------------------------------------------------
    # Class D -- LocalDB instance deletion. Target = the instance name.
    # -----------------------------------------------------------------------------------------
    _blk("dbp.D.1 instance deletion, long verb, default instance",
         _bash(f"{_LDB_DEL} mssqllocaldb")),
    _blk("dbp.D.2 instance deletion, short verb",
         _bash("sqllocaldb d MSSQLLocalDB")),
    _blk("dbp.D.3 instance deletion through the full executable path",
         _bash(f'"C:\\Program Files\\Microsoft SQL Server\\160\\Tools\\Binn\\SqlLocalDB.exe" {"de" + "lete"} MSSQLLocalDB')),
    _blk("dbp.D.4 instance deletion through a .exe spelling in PowerShell",
         _ps("& 'sqllocaldb.exe' " + "de" + "lete MSSQLLocalDB")),
    _blk("dbp.D.5 instance deletion, marker only in a trailing comment",
         _bash(f"{_LDB_DEL} mssqllocaldb {_HASH_MARK}")),
    _ok_audited("dbp.D.6 instance deletion, disposable instance name",
                _bash(f"{_LDB_DEL} Scratch_Test_0a1b2c3d4e5f")),
    _ok("dbp.D.7 instance info / start are not deletions  [passes today]",
        _bash("sqllocaldb info mssqllocaldb && sqllocaldb start mssqllocaldb")),

    # -----------------------------------------------------------------------------------------
    # Class E -- data-file deletion. Named / wildcard / folder.
    # -----------------------------------------------------------------------------------------
    _blk("dbp.E.1 named data file, protected stem",
         _bash(f'{_RM} "C:/Users/dev/{_DB_PROT}{_MDF}"')),
    _blk("dbp.E.2 named log file, protected stem, backslash path",
         _bash(f"{_DEL} C:\\Users\\dev\\{_DB_PROT}_log{_LDF}")),
    _blk("dbp.E.3 named data file, protected stem, PowerShell",
         _ps(f'{_RMITEM} "C:\\Users\\dev\\{_DB_PROT}{_MDF}"')),
    _blk("dbp.E.4 named data file, protected stem, marker only in a trailing comment",
         _bash(f'{_RM} "C:/Users/dev/{_DB_PROT}{_MDF}" {_HASH_MARK}')),
    _ok_audited("dbp.E.5 named data file, disposable suffix after the protected name",
                _bash(f'{_RM} "C:/Users/dev/{_DB_PROT}_Test_0a1b2c3d4e5f{_MDF}"')),
    _ok_audited("dbp.E.6 named log file, disposable suffix after the protected name",
                _bash(f"{_DEL} C:\\Users\\dev\\{_DB_PROT}_Test_0a1b2c3d4e5f_log{_LDF}")),
    _blk("dbp.E.7 wildcard naming the data extension",
         _bash(f"{_RM} C:/Users/dev/*{_MDF}")),
    _blk("dbp.E.8 wildcard naming the data extension, marker INSIDE the wildcard (never passes by a marker)",
         _bash(f"{_RM} C:/Users/dev/*_Test_0a1b2c3d4e5f{_MDF}")),
    _blk("dbp.E.9 wildcard naming the log extension, PowerShell",
         _ps(f"{_RMITEM} C:\\Users\\dev\\*{_LDF}")),
    _blk("dbp.E.10 LocalDB instances folder, cmd spelling",
         _bash(f'{_RD} /s /q "%LOCALAPPDATA%\\{_LDB_DIR}\\MSSQLLocalDB"')),
    _blk("dbp.E.11 LocalDB instances folder, PowerShell recursive",
         _ps(f'{_RMITEM} -Recurse -Force "$env:LOCALAPPDATA\\{_LDB_DIR}"')),
    _blk("dbp.E.12 LocalDB instances folder, marker only in a trailing comment",
         _bash(f'{_RD} /s /q "%LOCALAPPDATA%\\{_LDB_DIR}\\MSSQLLocalDB" {_HASH_MARK}')),
    _ok("dbp.E.13 deleting a .bak backup is not a data-file deletion  [passes today]",
        _bash(f'{_RM} "D:/Backups/{_DB_PROT}/scalping-20261001.bak"')),
    _ok("dbp.E.14 deleting an unrelated file  [passes today]",
        _bash(f"{_RM} notes.txt && {_RM} -rf ./obj")),

    # -----------------------------------------------------------------------------------------
    # Class F -- server scope. Never exempted by a marker.
    # -----------------------------------------------------------------------------------------
    _blk("dbp.F.1 server-trigger removal with a disposable marker in the same text",
         _bash(f'sqlcmd -E -Q "{_DROP_TR} trg_protect_dev_databases ON ALL SERVER" {_HASH_MARK}')),
    _blk("dbp.F.2 server-trigger turn-off with a disposable marker in the same text",
         _bash(f'sqlcmd -E -Q "{_DISABLE_TR} trg_protect_dev_databases ON ALL SERVER" {_HASH_MARK}')),
    _blk("dbp.F.3 server stop with a disposable marker in the same text",
         _bash(f'sqlcmd -E -Q "{_SD}" {_HASH_MARK}'), "sql-shutdown"),

    # -----------------------------------------------------------------------------------------
    # Class G1 -- other engines whose target is readable. Bound exactly like class A.
    # -----------------------------------------------------------------------------------------
    _blk("dbp.G1.1 sqlpackage publish, protected /TargetDatabaseName, no marker  [passes today]",
         _bash(f"sqlpackage /Action:Publish /SourceFile:x.dacpac /TargetDatabaseName:{_DB_PROT} {_SQLPKG_OFF}")),
    _blk("dbp.G1.2 sqlpackage publish, protected /TargetDatabaseName, marker only in a trailing comment",
         _bash(f"sqlpackage /Action:Publish /SourceFile:x.dacpac /TargetDatabaseName:{_DB_PROT} {_SQLPKG_OFF} {_HASH_MARK}")),
    _blk("dbp.G1.3 sqlpackage publish, protected /tdn short form, marker only in a trailing comment",
         _bash(f"sqlpackage /Action:Publish /SourceFile:x.dacpac /tdn:{_DB_PROT} {_SQLPKG_OFF} {_HASH_MARK}")),
    _blk("dbp.G1.4 sqlpackage publish, protected Database= inside /TargetConnectionString, marker in a comment",
         _bash("sqlpackage /Action:Publish /SourceFile:x.dacpac "
               f'/TargetConnectionString:"Server=(localdb)\\m;Database={_DB_PROT}" {_SQLPKG_OFF} {_HASH_MARK}')),
    _ok_audited("dbp.G1.5 sqlpackage publish, disposable /TargetDatabaseName",
                _bash(f"sqlpackage /Action:Publish /SourceFile:x.dacpac /TargetDatabaseName:{_DISP} {_SQLPKG_OFF}")),
    _blk("dbp.G1.6 postgres removal tool, unprotected-looking positional name, no marker  [passes today]",
         _bash(f"{_PG_DROP} -U postgres scalping_prod")),
    _blk("dbp.G1.7 postgres removal tool, positional name not disposable, marker only in a trailing comment",
         _bash(f"{_PG_DROP} -U postgres scalping_prod {_HASH_MARK}")),
    _ok_audited("dbp.G1.8 postgres removal tool, disposable positional name",
                _bash(f"{_PG_DROP} -U postgres {_DISP}")),
    _blk("dbp.G1.9 mysql admin removal verb, no marker  [passes today]",
         _bash(f"mysqladmin -u root {_MY_DROP} scalping_prod")),
    _blk("dbp.G1.10 mysql admin removal verb, name not disposable, marker only in a trailing comment",
         _bash(f"mysqladmin -u root {_MY_DROP} scalping_prod {_HASH_MARK}")),
    _ok_audited("dbp.G1.11 mysql admin removal verb, disposable name",
                _bash(f"mysqladmin -u root {_MY_DROP} {_DISP}")),
    _blk("dbp.G1.12 mongo database removal after `use <name>`, no marker  [passes today]",
         _bash(f'mongosh --eval "use scalping; {_MONGO_DROP_DB}"')),
    _blk("dbp.G1.13 mongo database removal after `use <name>`, marker only in a trailing comment",
         _bash(f'mongosh --eval "use scalping; {_MONGO_DROP_DB}" {_HASH_MARK}')),
    _blk("dbp.G1.14 mongo database removal, database named in the URI path, marker in a comment",
         _bash(f'mongosh "mongodb://localhost/scalping" --eval "{_MONGO_DROP_DB}" {_HASH_MARK}')),
    _ok_audited("dbp.G1.15 mongo database removal after `use <disposable>`",
                _bash(f'mongosh --eval "use {_DISP}; {_MONGO_DROP_DB}"')),
    _blk("dbp.G1.16 runtime database removal beside a literal protected Database=, marker only in a comment",
         _write("d:/Dev/Foo/tests/SomeTest.cs",
                f"using var db = new Ctx();\ndb.Database.{_ENSURE_DEL}(); // see {_MARK}\n"
                f'var cs = "Server=(localdb)\\\\m;Database={_DB_PROT};";\n')),
    _ok_audited("dbp.G1.17 runtime database removal beside a literal DISPOSABLE Database=",
                _write("d:/Dev/Foo/tests/SomeTest.cs",
                       f"using var db = new Ctx();\ndb.Database.{_ENSURE_DEL}();\n"
                       f'var cs = "Server=(localdb)\\\\m;Database={_DISP};";\n')),

    # -----------------------------------------------------------------------------------------
    # Class G2 -- target not readable. A marker anywhere allows, UNLESS a protected name sits in a
    # database-name position of the same text (narrowed legacy rule; Open Question Q3, accepted).
    # -----------------------------------------------------------------------------------------
    _blk("dbp.G2.1 runtime removal, no marker, no literal  [passes today]",
         _write("d:/Dev/Foo/tests/SomeTest.cs", f"using var db = new Ctx();\ndb.Database.{_ENSURE_DEL}();\n")),
    _ok_audited("dbp.G2.2 runtime removal of a name built at run time, a disposable marker present",
                _write("d:/Dev/Foo/tests/SomeTest.cs",
                       f'const string Marker = "{_DISP}";\nusing var db = new Ctx();\ndb.Database.{_ENSURE_DEL}();\n')),
    _blk("dbp.G2.3 cache flush with a marker AND a protected name in a -d position",
         _bash(f'redis-cli {_FLUSH_ALL} ; sqlcmd -E -d {_DB_PROT} -Q "SELECT 1" {_HASH_MARK}')),
    _ok_audited("dbp.G2.4 cache flush with a disposable marker present",
                _bash(f"redis-cli -n 3 {_FLUSH_DB} {_HASH_MARK}")),
    _ok_audited("dbp.G2.5 cloud database deletion call with a disposable marker present",
                _write("d:/Dev/Foo/tests/CosmosTest.cs",
                       f'// {_MARK}\nawait client{_COSMOS_DEL}"x");\n')),
    _blk("dbp.G2.6 raw SQL inside a migration, no marker  [passes today]",
         _write("d:/Dev/Foo/src/Migrations/M1.cs", f'migrationBuilder.Sql("{_DROP_TBL} dbo.X");\n')),

    # -----------------------------------------------------------------------------------------
    # Class H -- human-only commands (shell tools only; Write/Edit are not class H).
    # -----------------------------------------------------------------------------------------
    _blk("dbp.H.1 forward ef update, no target",
         _bash(f"{_EF_UPD}")),
    _blk("dbp.H.2 forward ef update with project flags",
         _bash(f"{_EF_UPD} --project src/X.Persistence --startup-project src/X.API")),
    _blk("dbp.H.3 forward ef update bound to a protected --connection",
         _bash(f'{_EF_UPD} --connection "Server=(localdb)\\m;Database={_DB_PROT}"')),
    _blk("dbp.H.4 forward ef update, marker only in a trailing comment",
         _bash(f"{_EF_UPD} --project src/X.Persistence {_HASH_MARK}")),
    _blk("dbp.H.5 forward ef update with the disposable connection AFTER `--` (forwarded, not consumed)",
         _bash(f'{_EF_UPD} --project src/X.Persistence -- --connection "Server=(localdb)\\m;Database={_DISP_MV}"')),
    _ok("dbp.H.6 forward ef update bound to a disposable --connection (explicitly allowed)  [passes today]",
        _bash(f'{_EF_UPD} --connection "Server=(localdb)\\m;Database={_DISP_MV}" --project src/X.Persistence')),
    _ok("dbp.H.7 migrations script generation opens no database  [passes today]",
        _bash("dotnet ef migrations script --idempotent --project src/X.Persistence --startup-project src/X.API")),
    _ok("dbp.H.8 migrations add / list are not human-only  [passes today]",
        _bash("dotnet ef migrations add AddThing --project src/X.Persistence && dotnet ef migrations list")),
    _blk("dbp.H.9 update script by repository-relative path",
         _bash(_UPD_CMD)),
    _blk("dbp.H.10 update script by a backslash-led relative path",
         _bash(".\\tools\\db-protection\\update-dev-database.cmd")),
    _blk("dbp.H.11 update script by bare file name",
         _bash("cmd /c update-dev-database.cmd")),
    _blk("dbp.H.12 update script by a checkout-equivalent path inside a worktree",
         _bash("D:/Dev/X/.claude/worktrees/20261004-infra-thing/tools/db-protection/update-dev-database.cmd")),
    _blk("dbp.H.13 update script through the PowerShell tool",
         _ps("& .\\tools\\db-protection\\update-dev-database.cmd")),
    _blk("dbp.H.14 update script, marker only in a trailing comment",
         _bash(f"{_UPD_CMD} {_HASH_MARK}")),
    _blk("dbp.H.15 recovery mode of the restore script",
         _bash(f"{_RESTORE_CMD} {_RECOVER_FLAG}")),
    _blk("dbp.H.16 recovery mode through the bare file name",
         _bash(f"cmd /c restore-latest.cmd {_RECOVER_FLAG}")),
    _blk("dbp.H.17 recovery mode through PowerShell",
         _ps(f"& .\\tools\\db-protection\\restore-latest.cmd {_RECOVER_FLAG}")),
    _blk("dbp.H.18 recovery mode, marker only in a trailing comment",
         _bash(f"{_RESTORE_CMD} {_RECOVER_FLAG} {_HASH_MARK}")),
    _ok("dbp.H.19 restore script WITHOUT the recovery flag is not human-only  [passes today]",
        _bash(_RESTORE_CMD)),
    _ok("dbp.H.20 restore script to a disposable copy is not human-only  [passes today]",
        _bash(f"{_RESTORE_CMD} {_DISP}")),
    _ok("dbp.H.21 authoring the update script with the Write tool is not class H  [passes today]",
        _write("d:/Dev/Foo/tools/db-protection/update-dev-database.cmd",
               f"@echo off\nREM person-run\n{_EF_UPD} --project src/X.Persistence\n")),
    _ok("dbp.H.22 editing the restore script with the Edit tool is not class H  [passes today]",
        _edit("d:/Dev/Foo/tools/db-protection/restore-latest.cmd", f"REM mode {_RECOVER_FLAG}\n")),

    # -----------------------------------------------------------------------------------------
    # Fail-closed behaviour (INV-8, INV-9)
    # -----------------------------------------------------------------------------------------
    Case(name="dbp.FC.1 rules file missing: human-only update script still blocks -> BLOCK",
         payload=_bash(_UPD_CMD), expect_rc=2, rules_missing=True),
    Case(name="dbp.FC.2 rules file missing: recovery mode still blocks -> BLOCK",
         payload=_bash(f"{_RESTORE_CMD} {_RECOVER_FLAG}"), expect_rc=2, rules_missing=True),
    Case(name="dbp.FC.3 rules file missing: restore script without the flag is not human-only  [passes today] -> ALLOW",
         payload=_bash(_RESTORE_CMD), expect_rc=0, rules_missing=True),
    Case(name="dbp.FC.4 rules file missing: database drop of an arbitrary name  [passes today] -> BLOCK",
         payload=_bash(f'sqlcmd -E -Q "{_DROP_DB} [Whatever]"'), expect_rc=2, rules_missing=True),
    Case(name="dbp.FC.5 rules file missing: alter to offline of an arbitrary name -> BLOCK",
         payload=_bash(f'sqlcmd -E -Q "{_ALTER_DB} [Whatever] SET OFFLINE"'), expect_rc=2, rules_missing=True),
    Case(name="dbp.FC.6 rules file missing: marker only in a comment still does not exempt  [passes today: the any-name veto] -> BLOCK",
         payload=_bash(f'sqlcmd -E -Q "{_DROP_DB} [Whatever] -- {_MARK}"'), expect_rc=2, rules_missing=True),
    Case(name="dbp.FC.7 fault injected into the target reader on a destructive input -> BLOCK internal-error",
         payload=_bash(f'sqlcmd -E -Q "{_DROP_DB} [{_DISP}]"'), expect_rc=2, isolate=True,
         env_extra={"DB_GUARD_FAULT_INJECTION": "binder"}, session_id=_sid(),
         expect_audit_decision="BLOCK", expect_audit_reason="internal-error-after-match",
         expect_stderr_contains=_BANNER_INTERNAL),
    Case(name="dbp.FC.8 fault injected: the banner ends with the fail-closed tail -> BLOCK",
         payload=_bash(f'sqlcmd -E -Q "{_DROP_DB} [{_DISP}]"'), expect_rc=2, isolate=True,
         env_extra={"DB_GUARD_FAULT_INJECTION": "binder"}, expect_stderr_contains=_BANNER_INTERNAL_TAIL),
    Case(name="dbp.FC.9 fault injected on a non-destructive input changes nothing  [passes today] -> ALLOW",
         payload=_bash("dotnet build src/X.sln"), expect_rc=0, isolate=True,
         env_extra={"DB_GUARD_FAULT_INJECTION": "binder"}),
    Case(name="dbp.FC.10 fault injected on an input that already blocks still blocks  [passes today] -> BLOCK",
         payload=_bash(f'sqlcmd -E -Q "{_DROP_DB} [{_DB_PROT}]"'), expect_rc=2, isolate=True,
         env_extra={"DB_GUARD_FAULT_INJECTION": "binder"}),
]


# ===========================================================================
# Round 2 (contract Revision 3, Amendment 2026-10-05, block 11).
#
# Every case below trips ONE clause of a rev. 3 rule. "[passes today]" marks a control that is green by
# design (it pins a behaviour the guard already has, or the allow side of a rule); every other case is
# RED until block 12 lands. Destructive verbs are composed from parts, as above. BLOCK cases carry a
# session id and demand the guard's OWN audit record, so a crash that exits 0 or 1 cannot pass as a
# decision. Expected audit reasons are asserted only where the contract names them.
# ===========================================================================
_UPDV = "up" + "date"                       # the EF forward verb, composed
_EF_SPELLINGS = ("dotnet ef", "dotnet-ef", "dotnet-ef.exe", "dotnet.exe ef", "dotnet tool run dotnet-ef")
_MODNAME = "MODI" + "FY NAME"
_RESTORE = "REST" + "ORE"
_REASON_UNRESOLVED = "unresolved-target"
_DISP_B = "Bar_Test_1a2b3c4d5e6f"


def _blk_a(name: str, payload: dict, reason: str = "", frag: str = "", env: dict | None = None) -> Case:
    """A BLOCK case that must also be backed by the guard's own audit record (decision BLOCK)."""
    return Case(name=f"{name} -> BLOCK (audited)", payload=payload, expect_rc=2,
                expect_stderr_contains=frag, isolate=True, session_id=_sid(),
                expect_audit_decision="BLOCK", expect_audit_reason=reason, env_extra=env or {})


CASES += [
    # -----------------------------------------------------------------------------------------
    # Class B -- three-part table names (rev. 3): the database part is a target
    # -----------------------------------------------------------------------------------------
    *[_blk_a(f"r2.B.1 three-part table name, database part {p}, session database disposable (-d)",
             _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} {p}.dbo.Users"')) for p in _PROTECTED_DBS],
    _blk_a("r2.B.2 three-part table name, bracketed protected database part, USE disposable",
           _bash(f'sqlcmd -E -Q "USE [{_DISP}]; {_DROP_TBL} [{_DB_PROT}].[dbo].[Users]"')),
    _blk_a("r2.B.3 three-part table name with the empty schema form (<db>..<table>), session disposable",
           _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} {_DB_PROT}..Users"')),
    _blk_a("r2.B.4 truncate of a three-part protected name, Initial Catalog disposable (PowerShell)",
           _ps(f'Invoke-Sqlcmd -ConnectionString "Server=(localdb)\\m;Initial Catalog={_DISP}" '
               f'-Query "{_TRUNC_TBL} {_DB_PROT}.dbo.Users"')),
    _blk_a("r2.B.5 three-part table name whose database part is neither protected nor disposable, session disposable",
           _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} SomeDb.dbo.Users"')),
    _ok_audited("r2.B.6 three-part table name whose database part is disposable, session disposable  [passes today]",
                _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} [{_DISP_B}].dbo.Users"')),
    _ok_audited("r2.B.7 three-part table name whose database part is disposable, NO session database named",
                _bash(f'sqlcmd -E -Q "{_DROP_TBL} [{_DISP}].dbo.Users"')),

    # -----------------------------------------------------------------------------------------
    # Class C -- every executable spelling of the EF tool, four operations each
    # -----------------------------------------------------------------------------------------
    *[_blk_a(f"r2.C.{i}.{opname} via `{sp}`", _bash(f"{sp} {opargs} --project src/X.Persistence"))
      for i, sp in enumerate(_EF_SPELLINGS)
      for opname, opargs in (
          ("rollback-to-zero", f"database {_UPDV} 0"),
          ("forward-update", f"database {_UPDV}"),
          ("database-removal", "database " + "dr" + "op --force"),
          ("migrations-removal", "migrations " + "re" + "move"),
      )],
    *[_blk_a(f"r2.C.{i}.removal-marker-in-comment via `{sp}`",
             _bash(f"{sp} database " + "dr" + f"op --force --project src/X.Persistence {_HASH_MARK}"))
      for i, sp in enumerate(_EF_SPELLINGS)],
    *[_ok_audited(f"r2.C.{i}.rollback bound to a disposable --connection via `{sp}`",
                  _bash(f'{sp} database {_UPDV} 0 --connection "Server=(localdb)\\m;Database={_DISP_MV}" '
                        "--project src/X.Persistence"))
      for i, sp in enumerate(_EF_SPELLINGS) if i > 0],
    *[_ok(f"r2.C.{i}.read-only verbs via `{sp}` are not destructive  [passes today]",
          _bash(f"{sp} migrations list && {sp} migrations add AddThing"))
      for i, sp in enumerate(_EF_SPELLINGS)],
    _blk_a("r2.C.v.1 verb position holds a variable (shell variable), marker only in a trailing comment",
           _bash(f"dotnet ef database $EF_VERB --project src/X.Persistence {_HASH_MARK}"), _REASON_UNRESOLVED),
    _blk_a("r2.C.v.2 noun AND verb are variables",
           _bash("dotnet ef $EF_NOUN $EF_VERB --project src/X.Persistence"), _REASON_UNRESOLVED),
    _blk_a("r2.C.v.3 verb position holds a cmd variable through the hyphenated spelling",
           _bash("dotnet-ef database %EF_VERB% --project src/X.Persistence"), _REASON_UNRESOLVED),
    _blk_a("r2.C.v.4 verb position holds a delayed-expansion variable (PowerShell tool)",
           _ps("& dotnet.exe ef database !EF_VERB! --project src/X.Persistence"), _REASON_UNRESOLVED),

    # -----------------------------------------------------------------------------------------
    # Connection string naming its database more than once: every occurrence must be disposable
    # -----------------------------------------------------------------------------------------
    _blk_a("r2.CS.1 removal: disposable Database= then protected Initial Catalog=",
           _bash(f'{_EF_DROP} --force --connection "Server=(localdb)\\m;Database={_DISP_MV};Initial Catalog={_DB_PROT}"')),
    _blk_a("r2.CS.2 removal: protected Database= then disposable Initial Catalog=",
           _bash(f'{_EF_DROP} --force --connection "Server=(localdb)\\m;Database={_DB_PROT};Initial Catalog={_DISP_MV}"')),
    _blk_a("r2.CS.3 migrations removal: disposable Database= then an undisposable Database=",
           _bash(f'{_EF_MIG_RM} --connection "Server=(localdb)\\m;Database={_DISP_MV};Database=SomeDb"')),
    _blk_a("r2.CS.4 removal: disposable Database= then an unreadable Database= (variable)",
           _bash(f'{_EF_DROP} --force --connection "Server=(localdb)\\m;Database={_DISP_MV};Database=%DB%"'),
           _REASON_UNRESOLVED),
    _ok_audited("r2.CS.5 removal: two occurrences, BOTH disposable",
                _bash(f'{_EF_DROP} --force --connection "Server=(localdb)\\m;Database={_DISP_MV};Initial Catalog={_DISP}"')),
    _ok_audited("r2.CS.6 removal: one disposable occurrence, repeated verbatim",
                _bash(f'{_EF_DROP} --force --connection "Server=(localdb)\\m;Database={_DISP_MV};Database={_DISP_MV}"')),

    # -----------------------------------------------------------------------------------------
    # Class E -- wildcard deletes over the user-profile root and over the LocalDB instances folder
    # -----------------------------------------------------------------------------------------
    _blk_a("r2.E.1 wildcard over the user-profile root (forward slashes)",
           _bash(f"{_RM} -rf C:/Users/dev/*")),
    _blk_a("r2.E.2 wildcard over the user-profile root (backslashes, *.*)",
           _bash(f"{_DEL} /q C:\\Users\\dev\\*.*")),
    _blk_a("r2.E.3 wildcard over the user-profile root through ~",
           _bash(f"{_RM} -rf ~/*")),
    _blk_a("r2.E.4 wildcard over the user-profile root through $HOME",
           _bash(f'{_RM} -rf "$HOME/*"')),
    _blk_a("r2.E.5 wildcard over the user-profile root through %USERPROFILE%",
           _bash(f"{_DEL} /q /s %USERPROFILE%\\*")),
    _blk_a("r2.E.6 wildcard over the user-profile root (PowerShell $env:USERPROFILE)",
           _ps(f'{_RMITEM} -Recurse -Force "$env:USERPROFILE\\*"')),
    _blk_a("r2.E.7 wildcard over the user-profile root, marker only in a trailing comment",
           _bash(f"{_RM} -rf C:/Users/dev/* {_HASH_MARK}")),
    _blk_a("r2.E.8 wildcard over one instance folder, extension *.*",
           _bash(f'{_DEL} /q "%LOCALAPPDATA%\\{_LDB_DIR}\\MSSQLLocalDB\\*.*"')),
    _blk_a("r2.E.9 wildcard over one instance folder, a non-database extension",
           _bash(f'{_RM} -f "$LOCALAPPDATA/' + _LDB_DIR.replace("\\", "/") + '/MSSQLLocalDB/*.dat"')),
    _blk_a("r2.E.10 wildcard over the whole instances folder (PowerShell)",
           _ps(f'{_RMITEM} -Force "$env:LOCALAPPDATA\\{_LDB_DIR}\\*"')),
    _blk_a("r2.E.11 wildcard over an instance folder, disposable marker inside the wildcard (never a marker)",
           _bash(f'{_RM} -rf "$LOCALAPPDATA/Microsoft/Microsoft SQL Server Local DB/Instances/*_Test_0a1b2c3d4e5f"')),
    _ok("r2.E.12 a wildcard under a project sub-folder is not the profile root  [passes today]",
        _bash(f"{_RM} -rf C:/Users/dev/project/obj/*")),
    _ok("r2.E.13 one named non-database file in the profile root is not a wildcard  [passes today]",
        _bash(f"{_RM} C:/Users/dev/notes.txt")),

    # -----------------------------------------------------------------------------------------
    # Class A-rename -- renaming a protected database; no marker exemption
    # -----------------------------------------------------------------------------------------
    *[_blk_a(f"r2.RN.1 rename of protected {p} to a name carrying a disposable marker",
             _bash(f'sqlcmd -E -Q "{_ALTER_DB} [{p}] {_MODNAME} = [{_DISP}]"')) for p in _PROTECTED_DBS],
    *[_blk_a(f"r2.RN.2 rename of protected {p} to an ordinary name",
             _bash(f'sqlcmd -E -Q "{_ALTER_DB} [{p}] {_MODNAME} = [SomeDb]"')) for p in _PROTECTED_DBS],
    _blk_a("r2.RN.3 rename of a protected database, marker only in a trailing shell comment",
           _bash(f'sqlcmd -E -Q "{_ALTER_DB} [{_DB_PROT}] {_MODNAME} = [SomeDb]" {_HASH_MARK}')),
    _blk_a("r2.RN.4 rename of a protected database through PowerShell, unbracketed names",
           _ps(f'Invoke-Sqlcmd -Query "{_ALTER_DB} {_DB_PROT} {_MODNAME} = {_DISP}"')),

    # -----------------------------------------------------------------------------------------
    # Class A -- every restore onto a database, with or without the replace option (Amendment A)
    # -----------------------------------------------------------------------------------------
    *[_blk_a(f"r2.RS.1 restore onto protected {p}, NO replace option",
             _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{p}] FROM DISK = N'x.bak'\"")) for p in _PROTECTED_DBS],
    _blk_a("r2.RS.2 restore onto a protected name with file moves and stats, no replace option",
           _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DB_PROT}] FROM DISK = N'x.bak' WITH MOVE N'a' TO N'b.mdf', STATS = 10\"")),
    _blk_a("r2.RS.3 restore onto a protected name, marker only in a trailing shell comment",
           _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DB_PROT}] FROM DISK = N'x.bak'\" {_HASH_MARK}")),
    _blk_a("r2.RS.4 restore onto a protected name through PowerShell",
           _ps(f"Invoke-Sqlcmd -Query \"{_RESTORE_DB} {_DB_PROT} FROM DISK = N'x.bak'\"")),
    _blk_a("r2.RS.5 restore onto an undisposable, unprotected name, marker only in a trailing comment",
           _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [SomeDb] FROM DISK = N'x.bak'\" {_HASH_MARK}")),
    _blk_a("r2.RS.6 two restores: a disposable target then a protected one (every target must be disposable)",
           _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DISP}] FROM DISK = N'x.bak'; {_RESTORE_DB} [{_DB_PROT}] FROM DISK = N'x.bak'\"")),
    _blk_a("r2.RS.7 restore onto an unreadable (variable) target, marker only in a trailing comment",
           _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [$(TARGET)] FROM DISK = N'x.bak'\" {_HASH_MARK}"), _REASON_UNRESOLVED),
    _ok_audited("r2.RS.8 restore onto a disposable name, no replace option",
                _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DISP}] FROM DISK = N'x.bak'\"")),
    _ok_audited("r2.RS.9 restore onto a disposable name with file moves and stats",
                _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DISP_MV}] FROM DISK = N'x.bak' WITH MOVE N'a' TO N'b.mdf', STATS = 10\"")),
    _ok("r2.RS.10 reading a backup's file list restores nothing  [passes today]",
        _bash(f"sqlcmd -E -Q \"{_RESTORE} FILELISTONLY FROM DISK = N'x.bak'\"")),
    _ok("r2.RS.11 verifying or reading a backup's header restores nothing  [passes today]",
        _bash(f"sqlcmd -E -Q \"{_RESTORE} VERIFYONLY FROM DISK = N'x.bak'; {_RESTORE} HEADERONLY FROM DISK = N'x.bak'\"")),

    # -----------------------------------------------------------------------------------------
    # Unreadable targets with a marker elsewhere, classes A, C and D (and a G1 twin): audit reason
    # unresolved-target (review finding B1; these are the witness payload shapes)
    # -----------------------------------------------------------------------------------------
    _blk_a("r2.U.A.1 database removal, variable target, marker only in a trailing comment  [passes today]",
           _bash(f'sqlcmd -E -Q "{_DROP_DB} [$(TARGET_DB)]" {_HASH_MARK}'), _REASON_UNRESOLVED),
    _blk_a("r2.U.A.2 database removal, cmd variable target, marker only in a trailing comment  [passes today]",
           _bash(f'sqlcmd -E -Q "{_DROP_DB} [%TARGET_DB%]" {_HASH_MARK}'), _REASON_UNRESOLVED),
    _blk_a("r2.U.A.3 alter to single-user, variable target, marker only in a comment  [passes today]",
           _bash(f'sqlcmd -E -Q "{_ALTER_DB} [$(TARGET_DB)] SET SINGLE_USER" {_HASH_MARK}'), _REASON_UNRESOLVED),
    _blk_a("r2.U.C.1 ef removal, --connection is a variable, marker only in a trailing comment  [passes today]",
           _bash(f'{_EF_DROP} --force --connection "%CS%" {_HASH_MARK}'), _REASON_UNRESOLVED),
    _blk_a("r2.U.C.2 ef removal, Database= inside the connection is a variable  [passes today]",
           _bash(f'{_EF_DROP} --force --connection "Server=(localdb)\\m;Database=%DB%" {_HASH_MARK}'), _REASON_UNRESOLVED),
    _blk_a("r2.U.C.3 ef migrations removal, --connection is a variable  [passes today]",
           _bash(f'{_EF_MIG_RM} --connection "$CONN" {_HASH_MARK}'), _REASON_UNRESOLVED),
    _blk_a("r2.U.D.1 instance deletion, cmd variable instance, marker only in a trailing comment  [passes today]",
           _bash(f"{_LDB_DEL} %INST% {_HASH_MARK}"), _REASON_UNRESOLVED),
    _blk_a("r2.U.D.2 instance deletion, shell variable instance, marker only in a trailing comment  [passes today]",
           _bash(f'{_LDB_DEL} "$INSTANCE" {_HASH_MARK}'), _REASON_UNRESOLVED),
    _blk_a("r2.U.G1.1 sqlpackage publish, variable /TargetDatabaseName, marker only in a comment  [passes today]",
           _bash(f"sqlpackage /Action:Publish /SourceFile:x.dacpac /TargetDatabaseName:$(DB) {_SQLPKG_OFF} {_HASH_MARK}"),
           _REASON_UNRESOLVED),
    _blk_a("r2.U.G1.2 postgres removal tool, variable database, marker only in a comment  [passes today]",
           _bash(f"{_PG_DROP} -U postgres $DB {_HASH_MARK}"), _REASON_UNRESOLVED),

    # -----------------------------------------------------------------------------------------
    # Fault injection: every step inside the fail-closed section (rev. 3)
    # -----------------------------------------------------------------------------------------
    *[Case(name=f"r2.FI.{step} fault injected into the {step} step on a destructive input -> BLOCK internal-error",
           payload=_bash(f'sqlcmd -E -Q "{_DROP_DB} [{_DISP}]"'), expect_rc=2, isolate=True,
           env_extra={"DB_GUARD_FAULT_INJECTION": step}, session_id=_sid(),
           expect_audit_decision="BLOCK", expect_audit_reason="internal-error-after-match",
           expect_stderr_contains=_BANNER_INTERNAL)
      for step in ("dynamic", "writes")],
    *[Case(name=f"r2.FI.{step}.2 fault injected into the {step} step: banner ends with the fail-closed tail -> BLOCK",
           payload=_bash(f'sqlcmd -E -Q "{_DROP_DB} [{_DISP}]"'), expect_rc=2, isolate=True,
           env_extra={"DB_GUARD_FAULT_INJECTION": step}, expect_stderr_contains=_BANNER_INTERNAL_TAIL)
      for step in ("dynamic", "writes")],
    *[Case(name=f"r2.FI.{step}.3 fault injected into the {step} step on a non-destructive input changes nothing  [passes today] -> ALLOW",
           payload=_bash("dotnet build src/X.sln"), expect_rc=0, isolate=True,
           env_extra={"DB_GUARD_FAULT_INJECTION": step})
      for step in ("dynamic", "writes")],
    *[Case(name=f"r2.FI.{step}.4 fault injected into the {step} step on an input that already blocks still blocks  [passes today] -> BLOCK",
           payload=_bash(f'sqlcmd -E -Q "{_DROP_DB} [{_DB_PROT}]"'), expect_rc=2, isolate=True,
           env_extra={"DB_GUARD_FAULT_INJECTION": step})
      for step in ("dynamic", "writes")],

    # -----------------------------------------------------------------------------------------
    # Rules-file value types: a wrong type fails closed and never widens or disables (rev. 3)
    # -----------------------------------------------------------------------------------------
    Case(name="r2.RF.1 protected_databases is a string: protected-database write still blocks, banner names the key -> BLOCK",
         payload=_bash(f"sqlcmd -S \"(localdb)\\m\" -E -Q \"Database={_DB_PROT}; {_INSERT} Users VALUES (1, 'x')\""),
         expect_rc=2, isolate=True, rules_override={"protected_databases": _DB_PROT},
         expect_stderr_contains="protected_databases"),
    Case(name="r2.RF.2 protected_databases holds a non-string entry: fails closed (every database protected) -> BLOCK",
         payload=_bash(f"sqlcmd -S \"(localdb)\\m\" -E -Q \"Database=Whatever; {_INSERT} Users VALUES (1, 'x')\""),
         expect_rc=2, isolate=True, rules_override={"protected_databases": [_DB_PROT, 7]},
         expect_stderr_contains="protected_databases"),
    Case(name="r2.RF.3 protected_databases is a number: the guard still decides (exit 2, not a crash) -> BLOCK",
         payload=_bash(f"sqlcmd -S \"(localdb)\\m\" -E -Q \"Database={_DB_PROT}; {_INSERT} Users VALUES (1, 'x')\""),
         expect_rc=2, isolate=True, rules_override={"protected_databases": 5},
         expect_stderr_contains="protected_databases"),
    Case(name="r2.RF.4 production_path_allowlist is a string: it must not allow-list a test file -> BLOCK",
         payload=_write("d:/Dev/Foo/tests/SomeTest.cs",
                        f'const string cs = "Server=(localdb)\\m;Database={_DB_PROT};Trusted_Connection=True;";\n'
                        f'await conn.ExecuteAsync("{_INSERT} Users (Id, Name) VALUES (1, \'x\')");'),
         expect_rc=2, isolate=True, rules_override={"production_path_allowlist": "src/scalpingmachine.api/"},
         expect_stderr_contains="production_path_allowlist"),
    Case(name="r2.RF.5 production_path_allowlist is an object: it must not allow-list a test file -> BLOCK",
         payload=_write("d:/Dev/Foo/tests/SomeTest.cs",
                        f'const string cs = "Server=(localdb)\\m;Database={_DB_PROT};Trusted_Connection=True;";\n'
                        f'await conn.ExecuteAsync("{_INSERT} Users (Id, Name) VALUES (1, \'x\')");'),
         expect_rc=2, isolate=True, rules_override={"production_path_allowlist": {"a": 1}},
         expect_stderr_contains="production_path_allowlist"),
    Case(name="r2.RF.6 production_path_allowlist holds a non-string entry: narrows to the defaults, so a production path no longer passes -> BLOCK",
         payload=_write(f"d:/Dev/Foo/{_SRC_ALLOWED}appsettings.json",
                        '"ConnectionStrings": { "AppDb": '
                        f'"Server=(localdb)\\m;Database={_DB_PROT};Trusted_Connection=True;" }}'),
         expect_rc=2, isolate=True, rules_override={"production_path_allowlist": [_SRC_ALLOWED, 5]},
         expect_stderr_contains="production_path_allowlist"),
    *[Case(name=f"r2.RF.7.{i} human_only_commands is {desc}: the built-in entries still block the update script  [passes today] -> BLOCK",
           payload=_bash(_UPD_CMD), expect_rc=2, isolate=True, rules_override={"human_only_commands": val})
      for i, (desc, val) in enumerate((("a string", "none"), ("an object without script", [{"flag": "--x"}]),
                                       ("a list of numbers", [5, 6])))],
    *[Case(name=f"r2.RF.8.{i} human_only_commands is {desc}: the block banner names the key -> BLOCK",
           payload=_bash(_UPD_CMD), expect_rc=2, isolate=True, rules_override={"human_only_commands": val},
           expect_stderr_contains="human_only_commands")
      for i, (desc, val) in enumerate((("a string", "none"), ("an object without script", [{"flag": "--x"}]),
                                       ("a list of numbers", [5, 6])))],
]


# ===========================================================================
# Final fix round (contract Revision 4, "Amendment 2026-10-05 (final fix round)", block 19).
#
# Every case below trips ONE clause of guard items 1-8 or one regression allow of item 7 / 16. "[passes today]"
# marks a control that is green by design (it pins the allow side of a rule, or a behaviour the guard already
# has); every other case is RED until block 20 lands. Destructive verbs are composed from parts, as above. BLOCK
# and audited-ALLOW cases carry a session id and demand the guard's OWN audit record.
#
# NEW FAULT-INJECTION SWITCH (item 8): DB_GUARD_FAULT_INJECTION=parser. It must raise inside the argument-list parser
# step (the step that finds the dynamic-only classes: EF rollback target and unreadable verb, data-file delete,
# human-only script) WHATEVER the input, even when no static pattern matched. The guard must then fail CLOSED
# (exit 2, audit reason internal-error-after-match, the existing internal-error banner) whenever the text holds the EF
# tool, a delete verb or a human-only script name, and keep the fail-open contract (exit 0) for every other text.
# ===========================================================================
# PLUGIN PORT: the real artifacts (this project's tools/db-protection files) are vendored byte for byte
# under tests/fixtures/ because the plugin has no such tools folder.
_REPO_ROOT = Path(__file__).resolve().parent / "fixtures"
_DBP_DIR = _REPO_ROOT / "db-protection"


def _real_text(*parts: str) -> str:
    """The real artifact, read at import time. Missing means a vacuous suite, so it fails loud (like the rules loader)."""
    path = _REPO_ROOT.joinpath(*parts[1:])  # PLUGIN PORT: parts[0] is "tools"; the fixtures folder has no such level
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover - configuration error, not a test failure
        raise SystemExit(f"cannot read the real artifact {path}: {exc}")


def _bashd(cmd: str, desc: str) -> dict:
    """A Bash call with a human-written description, as Claude Code sends it."""
    return {"tool_name": "Bash", "tool_input": {"command": cmd, "description": desc}}


def _blk_rules(name: str, payload: dict, override: dict, reason: str = "") -> Case:
    """A BLOCK case run against a copy of the hook whose rules file is the real one with these keys replaced."""
    return Case(name=f"{name} -> BLOCK (audited)", payload=payload, expect_rc=2, isolate=True,
                session_id=_sid(), expect_audit_decision="BLOCK", expect_audit_reason=reason,
                rules_override=override)


def _blk_parser_fault(name: str, payload: dict) -> Case:
    """Item 8: the parser step raises; a text holding the EF tool, a delete verb or a human-only script name blocks."""
    return Case(name=f"{name} -> BLOCK internal-error (audited)", payload=payload, expect_rc=2, isolate=True,
                env_extra={"DB_GUARD_FAULT_INJECTION": "parser"}, session_id=_sid(),
                expect_audit_decision="BLOCK", expect_audit_reason="internal-error-after-match",
                expect_stderr_contains=_BANNER_INTERNAL)


_EF_HOST_SPELLINGS = ("dotnet ef", "dotnet-ef")
_EF_LEADING_OPTIONS = (("--project src/X.Persistence", "--project"), ("-p src/X.Persistence", "-p"), ("-v", "-v"),
                       ("--no-color", "--no-color"), ("--startup-project src/X.API", "--startup-project"))
_EF_OPS = (
    ("rollback-to-zero", f"database {_UPDV} 0"),
    ("forward-update", f"database {_UPDV}"),
    ("database-removal", "database " + "dr" + "op --force"),
    ("migrations-removal", "migrations " + "re" + "move"),
)
_PS_DOTNET_Q = '& "C:\\Program Files\\dotnet\\dotnet.exe"'
_PS_DOTNET_SQ = "& 'C:\\Program Files\\dotnet\\dotnet.exe'"
_PS_EFTOOL_Q = '& "C:\\Users\\dev\\.dotnet\\tools\\dotnet-ef.exe"'
_RESTORE_PS_SQL = "Restore" + "-SqlDatabase"      # the SqlServer module's restore cmdlet, composed
_RESTORE_PS_DBA = "Restore" + "-DbaDatabase"      # the dbatools restore cmdlet, composed
_DEV_SCRIPTS = ("update-dev-database.cmd", "restore-latest.cmd", "verify-migration.cmd", "check-protection-status.cmd")
_BAK = "D:/Backups/ScalpingMachine/scalping-20260901-020000.bak"

CASES += [
    # -----------------------------------------------------------------------------------------
    # Item 1 -- EF option tokens BEFORE the noun and verb are skipped when the verb is read
    # -----------------------------------------------------------------------------------------
    *[_blk_a(f"r4.1.{sp.replace(' ', '_')}.{optname}.{opname} option before the noun and verb",
             _bash(f"{sp} {opt} {opargs}"))
      for sp in _EF_HOST_SPELLINGS
      for opt, optname in _EF_LEADING_OPTIONS
      for opname, opargs in _EF_OPS],
    *[_blk_a(f"r4.1.{sp.replace(' ', '_')}.two-options-before.{opname}",
             _bash(f"{sp} --project src/X.Persistence -v --no-color {opargs}"))
      for sp in _EF_HOST_SPELLINGS for opname, opargs in _EF_OPS],
    *[_ok_audited(f"r4.1.{sp.replace(' ', '_')}.rollback bound to a disposable --connection, option before the noun",
                  _bash(f'{sp} --project src/X.Persistence database {_UPDV} 0 --connection '
                        f'"Server=(localdb)\\m;Database={_DISP_MV}"'))
      for sp in _EF_HOST_SPELLINGS],
    *[_ok(f"r4.1.{sp.replace(' ', '_')}.read-only verbs with options before the noun are not destructive  [passes today]",
          _bash(f"{sp} --project src/X.Persistence -v migrations list && {sp} -p src/X.Persistence dbcontext info "
                f"&& {sp} --no-color migrations script --idempotent -o out.sql"))
      for sp in _EF_HOST_SPELLINGS],

    # -----------------------------------------------------------------------------------------
    # Item 4 -- quoted host paths, a quoted dotnet-ef.exe, and a first token that starts with @
    # -----------------------------------------------------------------------------------------
    *[_blk_a(f"r4.4.quoted-host.{opname} via a double-quoted dotnet.exe path (PowerShell call operator)",
             _ps(f"{_PS_DOTNET_Q} ef {opargs} --project src/X.Persistence")) for opname, opargs in _EF_OPS],
    *[_blk_a(f"r4.4.single-quoted-host.{opname} via a single-quoted dotnet.exe path",
             _ps(f"{_PS_DOTNET_SQ} ef {opargs} --project src/X.Persistence")) for opname, opargs in _EF_OPS],
    *[_blk_a(f"r4.4.quoted-host-bash.{opname} via a double-quoted dotnet.exe path (Bash)",
             _bash(f'"C:\\Program Files\\dotnet\\dotnet.exe" ef {opargs} --project src/X.Persistence'))
      for opname, opargs in _EF_OPS],
    *[_blk_a(f"r4.4.quoted-dotnet-ef-exe.{opname} via a double-quoted dotnet-ef.exe path",
             _ps(f"{_PS_EFTOOL_Q} {opargs} --project src/X.Persistence")) for opname, opargs in _EF_OPS],
    _ok_audited("r4.4.quoted-host rollback bound to a disposable --connection",
                _ps(f'{_PS_DOTNET_Q} ef database {_UPDV} 0 --connection "Server=(localdb)\\m;Database={_DISP_MV}"')),
    _ok("r4.4.quoted-host read-only verb is not destructive  [passes today]",
        _ps(f"{_PS_DOTNET_Q} ef migrations list --project src/X.Persistence")),
    _blk_a("r4.4.at-1 first token starts with @ (PowerShell splatting) after the host, shell tool",
           _ps("dotnet ef @efargs"), _REASON_UNRESOLVED),
    _blk_a("r4.4.at-2 first token starts with @ after the hyphenated spelling",
           _ps("dotnet-ef @efargs --project src/X.Persistence"), _REASON_UNRESOLVED),
    _blk_a("r4.4.at-3 first token starts with @ after a quoted host path",
           _ps(f"{_PS_DOTNET_Q} ef @efargs"), _REASON_UNRESOLVED),
    _ok("r4.4.at-4 authoring a script that splats the EF arguments (Write) is not a shell call  [passes today]",
        _write("d:/Dev/Foo/tools/x/run-ef.ps1", "param($efargs)\ndotnet ef @efargs\n")),

    # -----------------------------------------------------------------------------------------
    # Item 2 -- class A restore: FILE = and FILEGROUP = ... WITH PARTIAL clauses, and a comment after the name
    # -----------------------------------------------------------------------------------------
    *[_blk_a(f"r4.2.file-clause restore onto protected {p}",
             _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{p}] FILE = N'a' FROM DISK = N'x.bak'\"")) for p in _PROTECTED_DBS],
    *[_blk_a(f"r4.2.filegroup-partial restore onto protected {p}",
             _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{p}] FILEGROUP = N'PRIMARY' FROM DISK = N'x.bak' WITH PARTIAL\""))
      for p in _PROTECTED_DBS],
    *[_blk_a(f"r4.2.page restore onto protected {p}",
             _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{p}] PAGE = '1:57' FROM DISK = N'x.bak'\"")) for p in _PROTECTED_DBS],
    *[_blk_a(f"r4.2.read-write-filegroups restore onto protected {p}",
             _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{p}] READ_WRITE_FILEGROUPS FROM DISK = N'x.bak' WITH PARTIAL\""))
      for p in _PROTECTED_DBS],
    _blk_a("r4.2.file-clause restore onto a protected name through PowerShell, unbracketed",
           _ps(f"Invoke-Sqlcmd -Query \"{_RESTORE_DB} {_DB_PROT} FILE = N'a' FROM DISK = N'x.bak'\"")),
    _blk_a("r4.2.file-clause restore onto an unprotected undisposable name, marker only in a trailing comment",
           _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [SomeDb] FILE = N'a' FROM DISK = N'x.bak'\" {_HASH_MARK}")),
    _blk_a("r4.2.file-clause restore onto an unreadable (variable) target, marker only in a trailing comment",
           _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [$(TARGET)] FILE = N'a' FROM DISK = N'x.bak'\" {_HASH_MARK}"),
           _REASON_UNRESOLVED),
    _blk_a("r4.2.two restores: a disposable file-clause restore then a protected filegroup restore",
           _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DISP}] FILE = N'a' FROM DISK = N'x.bak'; "
                 f"{_RESTORE_DB} [{_DB_PROT}] FILEGROUP = N'PRIMARY' FROM DISK = N'x.bak' WITH PARTIAL\"")),
    _ok_audited("r4.2.file-clause restore onto a disposable name",
                _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DISP}] FILE = N'a' FROM DISK = N'x.bak'\"")),
    _ok_audited("r4.2.filegroup-partial restore onto a disposable name",
                _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DISP}] FILEGROUP = N'PRIMARY' FROM DISK = N'x.bak' WITH PARTIAL\"")),
    *[_blk_a(f"r4.2.block-comment after the name of protected {p}",
             _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{p}] /* keep */ FROM DISK = N'x.bak'\"")) for p in _PROTECTED_DBS],
    *[_blk_a(f"r4.2.line-comment after the name of protected {p}",
             _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{p}] -- keep\nFROM DISK = N'x.bak'\"")) for p in _PROTECTED_DBS],
    _blk_a("r4.2.block-comment after an unbracketed protected name",
           _ps(f"Invoke-Sqlcmd -Query \"{_RESTORE_DB} {_DB_PROT}/* keep */ FROM DISK = N'x.bak'\"")),
    _blk_a("r4.2.block-comment after an unprotected undisposable name, marker only in a trailing shell comment",
           _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [SomeDb] /* keep */ FROM DISK = N'x.bak'\" {_HASH_MARK}")),
    _ok_audited("r4.2.block-comment after a disposable name",
                _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DISP}] /* keep */ FROM DISK = N'x.bak'\"")),
    _ok_audited("r4.2.line-comment after a disposable name",
                _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [{_DISP}] -- keep\nFROM DISK = N'x.bak'\"")),

    # -----------------------------------------------------------------------------------------
    # Item 2 (cmdlets) -- the SqlServer and dbatools PowerShell restore cmdlets, target read from -Database
    # -----------------------------------------------------------------------------------------
    *[_blk_a(f"r4.2.cmdlet {cmd} onto protected {p} (-Database)",
             _ps(f'{cmd} -ServerInstance "(localdb)\\m" -Database {p} -BackupFile "x.bak"'))
      for cmd in (_RESTORE_PS_SQL, _RESTORE_PS_DBA) for p in _PROTECTED_DBS],
    _blk_a("r4.2.cmdlet with a double-quoted protected -Database value",
           _ps(f'{_RESTORE_PS_SQL} -ServerInstance x -Database "{_DB_PROT}" -BackupFile x.bak')),
    _blk_a("r4.2.cmdlet with a single-quoted bracketed protected -Database value",
           _ps(f"{_RESTORE_PS_SQL} -ServerInstance x -Database '[{_DB_PROT}]' -BackupFile x.bak")),
    _blk_a("r4.2.cmdlet reached through a Bash pwsh call",
           _bash(f'pwsh -NoProfile -Command "{_RESTORE_PS_SQL} -ServerInstance x -Database {_DB_PROT} -BackupFile x.bak"')),
    _blk_a("r4.2.cmdlet onto an unprotected undisposable name, marker only in a trailing comment",
           _ps(f"{_RESTORE_PS_SQL} -ServerInstance x -Database SomeDb -BackupFile x.bak {_HASH_MARK}")),
    _blk_a("r4.2.cmdlet with no -Database value at all is unreadable",
           _ps(f"{_RESTORE_PS_SQL} -ServerInstance x -BackupFile x.bak {_HASH_MARK}"), _REASON_UNRESOLVED),
    _blk_a("r4.2.cmdlet with a variable -Database value is unreadable",
           _ps(f"{_RESTORE_PS_SQL} -ServerInstance x -Database $db -BackupFile x.bak {_HASH_MARK}"), _REASON_UNRESOLVED),
    _blk_a("r4.2.two cmdlet calls: disposable first, protected second",
           _ps(f"{_RESTORE_PS_SQL} -ServerInstance x -Database {_DISP} -BackupFile x.bak; "
               f"{_RESTORE_PS_SQL} -ServerInstance x -Database {_DB_PROT} -BackupFile x.bak")),
    _blk_a("r4.2.dbatools cmdlet with -DatabaseName onto a protected name",
           _ps(f"{_RESTORE_PS_DBA} -SqlInstance x -Path x.bak -DatabaseName {_DB_PROT}")),
    _ok_audited("r4.2.SqlServer cmdlet onto a disposable name",
                _ps(f"{_RESTORE_PS_SQL} -ServerInstance x -Database {_DISP} -BackupFile x.bak")),
    _ok_audited("r4.2.dbatools cmdlet onto a disposable name",
                _ps(f"{_RESTORE_PS_DBA} -SqlInstance x -Path x.bak -Database {_DISP}")),

    # -----------------------------------------------------------------------------------------
    # Item 3 -- a protected-target veto hit alone is a match (read literally: any ALTER on a protected name)
    # -----------------------------------------------------------------------------------------
    *[_blk_a(f"r4.3.veto-alone: a database ALTER on protected {p} that no label lists (recovery model)",
             _bash(f'sqlcmd -E -Q "{_ALTER_DB} [{p}] SET RECOVERY SIMPLE"')) for p in _PROTECTED_DBS],
    _ok("r4.3.veto-alone near miss: the same ALTER on a disposable name is not a protected target  [passes today]",
        _bash(f'sqlcmd -E -Q "{_ALTER_DB} [{_DISP}] SET RECOVERY SIMPLE"')),

    # -----------------------------------------------------------------------------------------
    # Item 5 -- quoted values in connection strings are read; an unpaired quote is unresolved
    # -----------------------------------------------------------------------------------------
    _blk_a("r4.5.1 removal: bare disposable Database= then a single-quoted protected Database=",
           _bash(f"{_EF_DROP} --force --connection \"Server=(localdb)\\m;Database={_DISP_MV};Database='{_DB_PROT}'\"")),
    _blk_a("r4.5.2 removal: bare disposable Database= then a double-quoted protected Initial Catalog= (PowerShell)",
           _ps(f"{_EF_DROP} --force --connection 'Server=(localdb)\\m;Database={_DISP_MV};Initial Catalog=\"{_DB_PROT}\"'")),
    _blk_a("r4.5.3 migrations removal: bare disposable then single-quoted undisposable Database=",
           _bash(f"{_EF_MIG_RM} --connection \"Server=(localdb)\\m;Database={_DISP_MV};Database='SomeDb'\"")),
    _blk_a("r4.5.4 rollback: single-quoted disposable then double-quoted protected (both quoted)  [passes today]",
           _ps(f"dotnet ef database {_UPDV} 0 --connection 'Server=(localdb)\\m;Database=\"{_DISP_MV}\";Database=\"{_DB_PROT}\"'")),
    _blk_a("r4.5.5 removal: a quoted protected value LAST, a quoted disposable first  [passes today]",
           _bash(f"{_EF_DROP} --force --connection \"Server=(localdb)\\m;Database='{_DISP_MV}';Initial Catalog='{_DB_PROT}'\"")),
    _blk_a("r4.5.6 removal: unpaired single quote on the last value",
           _bash(f"{_EF_DROP} --force --connection \"Server=(localdb)\\m;Database={_DISP_MV};Database='{_DB_PROT}\"")),
    _blk_a("r4.5.7 removal: unpaired double quote on the last value (PowerShell)",
           _ps(f"{_EF_DROP} --force --connection 'Server=(localdb)\\m;Database={_DISP_MV};Initial Catalog=\"{_DB_PROT}'")),
    _blk_a("r4.5.8 table removal: bare disposable then double-quoted protected session database (PowerShell connection string)",
           _ps(f"Invoke-Sqlcmd -ConnectionString 'Server=(localdb)\\m;Database={_DISP};Database=\"{_DB_PROT}\"' "
               f"-Query \"{_DROP_TBL} dbo.Users\"")),
    _ok_audited("r4.5.9 removal: both values single-quoted disposable names",
                _bash(f"{_EF_DROP} --force --connection \"Server=(localdb)\\m;Database='{_DISP_MV}';Initial Catalog='{_DISP}'\"")),
    _ok_audited("r4.5.10 removal: both values double-quoted disposable names (PowerShell)",
                _ps(f"{_EF_DROP} --force --connection 'Server=(localdb)\\m;Database=\"{_DISP_MV}\";Database=\"{_DISP}\"'")),
    _ok_audited("r4.5.11 table removal: one quoted disposable session database, nothing else",
                _ps(f"Invoke-Sqlcmd -ConnectionString 'Server=(localdb)\\m;Database=\"{_DISP}\"' -Query \"{_DROP_TBL} dbo.Users\"")),

    # -----------------------------------------------------------------------------------------
    # Item 6 -- three-part table names with whitespace around the dots or a comment before them
    # -----------------------------------------------------------------------------------------
    *[_blk_a(f"r4.6.1 three-part name with spaces around the dots, protected {p}, session disposable",
             _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} {p} . dbo . Users"')) for p in _PROTECTED_DBS],
    _blk_a("r4.6.2 three-part name, bracketed parts with spaces around the dots, session disposable",
           _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} [{_DB_PROT}] . [dbo] . [Users]"')),
    _blk_a("r4.6.3 three-part name with a block comment before the first dot",
           _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} {_DB_PROT} /* c */ . dbo . Users"')),
    _blk_a("r4.6.4 three-part name with a block comment before the second dot",
           _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} {_DB_PROT} . dbo /* c */ . Users"')),
    _blk_a("r4.6.5 truncate of a three-part name with spaces, Initial Catalog disposable (PowerShell)",
           _ps(f'Invoke-Sqlcmd -ConnectionString "Server=(localdb)\\m;Initial Catalog={_DISP}" '
               f'-Query "{_TRUNC_TBL} {_DB_PROT} . dbo . Users"')),
    _blk_a("r4.6.6 three-part name with spaces, database part neither protected nor disposable, session disposable",
           _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} SomeDb . dbo . Users"')),
    _blk_a("r4.6.7 three-part name with spaces only before the second dot",
           _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} {_DB_PROT}.dbo . Users"')),
    _blk_a("r4.6.8 comment glued to the database part (<db>/*c*/.dbo.Users)  [passes today]",
           _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} {_DB_PROT}/*c*/.dbo.Users"')),
    _ok_audited("r4.6.9 three-part name with spaces, disposable database part, disposable session  [passes today]",
                _bash(f'sqlcmd -E -d {_DISP} -Q "{_DROP_TBL} [{_DISP_B}] . dbo . Users"')),
    _ok_audited("r4.6.10 three-part name with spaces, disposable database part, NO session database named",
                _bash(f'sqlcmd -E -Q "{_DROP_TBL} [{_DISP}] . dbo . Users"')),

    # -----------------------------------------------------------------------------------------
    # Item 7c -- the protected names are built in; the rules file can only ADD names
    # -----------------------------------------------------------------------------------------
    *[_blk_rules(f"r4.7c.1 rules file omits {p}: a test file writing to it still blocks",
                 _write("d:/Dev/Foo/tests/SomeTest.cs",
                        f'const string cs = "Server=(localdb)\\m;Database={p};Trusted_Connection=True;";\n'
                        f'await conn.ExecuteAsync("{_INSERT} Users (Id, Name) VALUES (1, \'x\')");'),
                 {"protected_databases": ["Unrelated_Prod_Db"]}, "protected-db-write-from-non-production-path")
      for p in _PROTECTED_DBS],
    *[_blk_rules(f"r4.7c.2 rules file omits {p}: a sqlcmd session write still blocks",
                 _bash(f'sqlcmd -S "(localdb)\\m" -E -d {p} -Q "UPDATE Users SET Name = \'x\' WHERE Id = 1"'),
                 {"protected_databases": ["Unrelated_Prod_Db"]}, "protected-db-write-from-non-production-path")
      for p in _PROTECTED_DBS],
    _blk_rules("r4.7c.3 rules file omits the dev name: USE <dev>; DELETE still blocks",
               _bash(f'sqlcmd -S "(localdb)\\m" -E -Q "USE {_DB_PROT}; DELETE FROM Users WHERE Id = 1"'),
               {"protected_databases": ["Unrelated_Prod_Db"]}, "protected-db-write-from-non-production-path"),
    _blk_rules("r4.7c.4 rules file omits the dev name: a connection-string write from a PowerShell tool still blocks",
               _ps(f"Invoke-Sqlcmd -ConnectionString 'Server=(localdb)\\m;Initial Catalog={_DB_PROT}' "
                   f"-Query \"{_INSERT} Users VALUES (1, 'x')\""),
               {"protected_databases": ["Unrelated_Prod_Db"]}, "protected-db-write-from-non-production-path"),
    _blk_rules("r4.7c.5 a name the rules file ADDS is honoured as well  [passes today]",
               _bash(f"sqlcmd -S \"(localdb)\\m\" -E -Q \"Database=Extra_Prod_Db; {_INSERT} Users VALUES (1, 'x')\""),
               {"protected_databases": ["Extra_Prod_Db"] + _PROTECTED_DBS}, "protected-db-write-from-non-production-path"),

    # -----------------------------------------------------------------------------------------
    # Item 8 -- pattern-less classes fail CLOSED on a parser exception (DB_GUARD_FAULT_INJECTION=parser)
    # -----------------------------------------------------------------------------------------
    _blk_parser_fault("r4.8.1 parser fault, EF rollback target (no static pattern)",
                      _bash(f"dotnet ef database {_UPDV} 0 --project src/X.Persistence")),
    _blk_parser_fault("r4.8.2 parser fault, EF forward update (no static pattern)",
                      _bash(f"dotnet ef database {_UPDV} --project src/X.Persistence")),
    _blk_parser_fault("r4.8.3 parser fault, an EF read-only verb (the text holds the EF tool)",
                      _bash("dotnet ef migrations list --project src/X.Persistence")),
    _blk_parser_fault("r4.8.4 parser fault, the hyphenated EF spelling",
                      _bash("dotnet-ef --version")),
    _blk_parser_fault("r4.8.5 parser fault, a delete verb on an ordinary file",
                      _bash(f"{_RM} -f build.log")),
    _blk_parser_fault("r4.8.6 parser fault, a data-file delete",
                      _bash(f"{_RM} -f C:/data/Foo{_MDF}")),
    _blk_parser_fault("r4.8.7 parser fault, a cmd delete verb",
                      _bash(f"{_DEL} /q x.tmp")),
    _blk_parser_fault("r4.8.8 parser fault, the update script invoked",
                      _bash(_UPD_CMD)),
    _blk_parser_fault("r4.8.9 parser fault, the recovery mode invoked",
                      _bash(f"{_RESTORE_CMD} {_RECOVER_FLAG}")),
    _blk_parser_fault("r4.8.10 parser fault, a human-only script name merely mentioned (the text holds it)",
                      _bash(f"cat {_UPD_CMD}")),
    Case(name="r4.8.11 parser fault on text that holds none of the three triggers fails open  [passes today] -> ALLOW",
         payload=_bash("dotnet build src/X.sln"), expect_rc=0, isolate=True,
         env_extra={"DB_GUARD_FAULT_INJECTION": "parser"}),
    Case(name="r4.8.12 parser fault on a plain git command fails open  [passes today] -> ALLOW",
         payload=_bash("git status --short"), expect_rc=0, isolate=True,
         env_extra={"DB_GUARD_FAULT_INJECTION": "parser"}),
    Case(name="r4.8.13 parser fault on the harness run fails open  [passes today] -> ALLOW",
         payload=_bash("py -3 tools/db-protection/tests/test_db_protection_scripts.py"), expect_rc=0, isolate=True,
         env_extra={"DB_GUARD_FAULT_INJECTION": "parser"}),

    # -----------------------------------------------------------------------------------------
    # Item 7a / 16 -- prose that only MENTIONS a guarded command must not block (descriptions, commit
    # messages, PR bodies, heredocs, a ';' inside a quoted string)
    # -----------------------------------------------------------------------------------------
    _ok("r4.7a.1 description mentions the update script after a semicolon",
        _bashd("py -3 tools/db-protection/tests/test_db_protection_scripts.py",
               f"Run the harness; {_UPD_CMD} stays a person-only step")),
    _ok("r4.7a.2 description mentions the recovery mode on a line of its own",
        _bashd("git status --short",
               f"Check the tree\n{_RESTORE_CMD} {_RECOVER_FLAG} is people only, then the update script")),
    _ok("r4.7a.3 description mentions the forward EF update",
        _bashd("git status --short", f"Note that {_EF_UPD} is run by a person, never by Claude")),
    _ok("r4.7a.4 description mentions a restore of the dev database",
        _bashd("git status --short", f"Check that {_RESTORE_DB} {_DB_PROT} FROM DISK is refused for agents")),
    _ok("r4.7a.5 description names the recovery script and its flag in prose",
        _bashd("git diff --stat", f"Review the recover-missing-dev-db change; {_RESTORE_CMD} {_RECOVER_FLAG}")),
    _ok("r4.7a.6 git commit -m naming the forward update and the update script",
        _bash(f'git commit -m "docs: run {_EF_UPD} through {_UPD_CMD}"')),
    _ok("r4.7a.7 git commit -m with a semicolon before the recovery script (path form)  [passes today]",
        _bash(f'git commit -m "fix(recovery): refuse when a database exists; {_RESTORE_CMD} {_RECOVER_FLAG} needs a person"')),
    _ok("r4.7a.8 git commit -m with a restore statement named in the message",
        _bash(f'git commit -m "test: a {_RESTORE_DB} {_DB_PROT} FROM DISK without the replace option can overwrite"')),
    _ok("r4.7a.9 heredoc commit message, lines that start with the script names",
        _bash("git commit -m \"$(cat <<'EOF'\n"
              "fix(db-protection): refuse a missing dev database\n\n"
              "The route is: copy a .bak into the backup folder, run\n"
              f"{_RESTORE_CMD} {_RECOVER_FLAG}, then\n"
              f"{_UPD_CMD}. A plain {_EF_UPD} is never run by the script.\n"
              "EOF\n)\"")),
    _ok("r4.7a.10 gh pr create --body naming the commands",
        _bash(f'gh pr create --title "dev db protection" --body "Run {_UPD_CMD} after a pull; '
              f'a {_RESTORE_DB} {_DB_PROT} FROM DISK is blocked; never {_EF_UPD} against the dev database"')),
    _ok("r4.7a.11 gh pr create heredoc body with bullet lines  [passes today]",
        _bash("gh pr create --title \"t\" --body \"$(cat <<'EOF'\n## Summary\n"
              f"- {_UPD_CMD} refuses a missing database\n"
              f"- {_RESTORE_CMD} {_RECOVER_FLAG} restores it\n"
              "EOF\n)\"")),
    _ok("r4.7a.12 a semicolon inside a double-quoted echo before the update script path  [passes today]",
        _bash(f'echo "step one; {_UPD_CMD} is human-only"')),
    _ok("r4.7a.12b a semicolon inside a double-quoted echo before the bare update script name",
        _bash('echo "step one; update-dev-database.cmd is human-only"')),
    _ok("r4.7a.7b git commit -m with a semicolon before the bare recovery script name",
        _bash(f'git commit -m "fix(recovery): refuse when a database exists; restore-latest.cmd {_RECOVER_FLAG} needs a person"')),
    _ok("r4.7a.13 a semicolon inside a single-quoted grep pattern before the recovery flag",
        _bash(f"grep -n 'a; restore-latest.cmd {_RECOVER_FLAG}' README.md")),
    _blk_a("r4.7a.14 the update script invoked plainly still blocks  [passes today]",
           _bash(_UPD_CMD), "human-only-command"),
    _blk_a("r4.7a.15 the update script invoked through a quoted backslash path still blocks  [passes today]",
           _bash('"tools\\db-protection\\update-dev-database.cmd"'), "human-only-command"),
    _blk_a("r4.7a.16 the update script run through cmd /c still blocks  [passes today]",
           _bash("cmd.exe /c tools\\db-protection\\update-dev-database.cmd"), "human-only-command"),
    _blk_a("r4.7a.17 the recovery mode after a semicolon still blocks  [passes today]",
           _bash(f"git status; {_RESTORE_CMD} {_RECOVER_FLAG}"), "human-only-command"),
    _blk_a("r4.7a.18 the forward EF update at the start of a command still blocks  [passes today]",
           _bash(f"{_EF_UPD} --project src/X.Persistence"), "human-only-command"),

    # -----------------------------------------------------------------------------------------
    # Item 16 -- read-only and housekeeping commands over the four scripts
    # -----------------------------------------------------------------------------------------
    _ok("r4.16.1 git add of the two human-only scripts  [passes today]",
        _bash(f"git add tools/db-protection/{_DEV_SCRIPTS[0]} tools/db-protection/{_DEV_SCRIPTS[1]}")),
    _ok("r4.16.2 git add of the harness test file  [passes today]",
        _bash("git add tools/db-protection/tests/test_db_protection_scripts.py")),
    _ok("r4.16.3 git diff of the restore script  [passes today]",
        _bash(f"git diff -- tools/db-protection/{_DEV_SCRIPTS[1]}")),
    _ok("r4.16.4 git log of the update script  [passes today]",
        _bash(f"git log --oneline -- tools/db-protection/{_DEV_SCRIPTS[0]}")),
    _ok("r4.16.5 git show of the restore script at HEAD  [passes today]",
        _bash(f"git show HEAD:tools/db-protection/{_DEV_SCRIPTS[1]}")),
    *[_ok(f"r4.16.6 cat of {s}  [passes today]", _bash(f"cat tools/db-protection/{s}")) for s in _DEV_SCRIPTS],
    *[_ok(f"r4.16.7 sed -n of {s}  [passes today]", _bash(f"sed -n '1,60p' tools/db-protection/{s}")) for s in _DEV_SCRIPTS],
    *[_ok(f"r4.16.8 grep of {s} for the recovery flag  [passes today]",
          _bash(f"grep -n -- {_RECOVER_FLAG} tools/db-protection/{s}")) for s in _DEV_SCRIPTS],
    *[_ok(f"r4.16.9 Get-Content of {s}  [passes today]", _ps(f"Get-Content tools\\db-protection\\{s}")) for s in _DEV_SCRIPTS],
    _ok("r4.16.10 running the script harness  [passes today]",
        _bash("py -3 tools/db-protection/tests/test_db_protection_scripts.py")),
    _ok("r4.16.11 migrations script  [passes today]",
        _bash("dotnet ef migrations script --idempotent -o out.sql --project src/ScalpingMachine.Persistence "
              "--startup-project src/ScalpingMachine.API")),
    _ok("r4.16.12 dbcontext info and the EF version preflight  [passes today]",
        _bash("dotnet ef dbcontext info --project src/ScalpingMachine.Persistence && dotnet ef --version")),
    _ok("r4.16.13 deleting a .bak with rm  [passes today]", _bash(f'{_RM} "{_BAK}"')),
    _ok("r4.16.14 deleting a .bak with del  [passes today]", _bash(f'{_DEL} "{_BAK.replace("/", chr(92))}"')),
    _ok("r4.16.15 deleting a .bak with Remove-Item  [passes today]",
        _ps(f'{_RMITEM} "{_BAK.replace("/", chr(92))}"')),

    # -----------------------------------------------------------------------------------------
    # Item 7b -- an agent may Write or Edit WHOLE files under tools/db-protection/ and the harness test file;
    # a restore with a variable target inside them is authoring, not an executed restore
    # -----------------------------------------------------------------------------------------
    _ok("r4.7b.1 Write of the whole real restore-latest.cmd",
        _write("d:/Dev/Foo/tools/db-protection/restore-latest.cmd", _real_text("tools", "db-protection", "restore-latest.cmd"))),
    _ok("r4.7b.2 Write of the whole real verify-migration.cmd",
        _write("d:/Dev/Foo/tools/db-protection/verify-migration.cmd", _real_text("tools", "db-protection", "verify-migration.cmd"))),
    _ok("r4.7b.3 Write of the whole real harness test file  [passes today]",
        _write("d:/Dev/Foo/tools/db-protection/tests/test_db_protection_scripts.py",
               _real_text("tools", "db-protection", "tests", "test_db_protection_scripts.py"))),
    _ok("r4.7b.4 Write of the whole real update-dev-database.cmd  [passes today]",
        _write("d:/Dev/Foo/tools/db-protection/update-dev-database.cmd", _real_text("tools", "db-protection", "update-dev-database.cmd"))),
    _ok("r4.7b.5 Write of the whole real check-protection-status.cmd  [passes today]",
        _write("d:/Dev/Foo/tools/db-protection/check-protection-status.cmd", _real_text("tools", "db-protection", "check-protection-status.cmd"))),
    _ok("r4.7b.6 Write of the whole real restore-latest.cmd through a worktree path",
        _write("d:/Dev/Foo/.claude/worktrees/20261004-infra-x/tools/db-protection/restore-latest.cmd",
               _real_text("tools", "db-protection", "restore-latest.cmd"))),
    _ok("r4.7b.7 Edit inserting the real restore line(s) into restore-latest.cmd",
        _edit("d:/Dev/Foo/tools/db-protection/restore-latest.cmd",
              "\n".join(l for l in _real_text("tools", "db-protection", "restore-latest.cmd").splitlines()
                        if _RESTORE_DB in l.upper() and "FROM DISK" in l.upper()) or "REM no restore line found")),
    _ok("r4.7b.8 Edit inserting the real database-removal line into verify-migration.cmd",
        _edit("d:/Dev/Foo/tools/db-protection/verify-migration.cmd",
              "\n".join(l for l in _real_text("tools", "db-protection", "verify-migration.cmd").splitlines()
                        if _DROP_DB in l.upper()) or "REM no removal line found")),
    # The relaxation is narrow: the same variable-target restore anywhere else still blocks, and so does a protected-
    # database write from a path outside the authoring paths.
    _blk_a("r4.7b.9 the real restore-latest.cmd text written to a test helper path still blocks  [passes today]",
           _write("d:/Dev/Foo/tests/helpers/Restore.ps1", _real_text("tools", "db-protection", "restore-latest.cmd"))),
    _blk_a("r4.7b.10 the real verify-migration.cmd text written under src/ still blocks  [passes today]",
           _write("d:/Dev/Foo/src/X/Evil.cs", _real_text("tools", "db-protection", "verify-migration.cmd"))),
    _blk_a("r4.7b.11 a protected-database write from a tools folder that is not the authoring path still blocks  [passes today]",
           _write("d:/Dev/Foo/tools/other/fix.cmd",
                  f'sqlcmd -S "(localdb)\\m" -E -d {_DB_PROT} -Q "UPDATE Users SET Name = \'x\' WHERE Id = 1"'),
           "protected-db-write-from-non-production-path"),
    _blk_a("r4.7b.12 a restore with a variable target run through a shell tool still blocks  [passes today]",
           _bash(f"sqlcmd -E -Q \"{_RESTORE_DB} [$(TARGET)] FROM DISK = N'x.bak'\""), _REASON_UNRESOLVED),
]


# ===========================================================================
# Round 5 (final fix round, contract Revision 4, item 7a and 8). RED cases for two open blockers:
#   B6      (t23): the "piped or redirected echo is not prose" exclusion of _segment_is_prose is unpinned.
#   F1      (t25): _mask_inert_prose blanks quoted text that sits inside an EXECUTED sub-command.
#   WARN-F1 (t25): DB_GUARD_FAULT_INJECTION=parser must not turn a Pass B block into an allow.
# Every case says whether it is RED today or BY-DESIGN green today (a control or a mutation twin).
# Destructive verbs come from the composed fragments above; no database is ever opened.
# ===========================================================================
_R5_RESTORE = f"{_RESTORE_DB} [{_DB_PROT}] FROM DISK = N'x.bak'"      # a restore onto the PROTECTED dev name
_R5_RESTORE_D = f"{_RESTORE_DB} [{_DISP}] FROM DISK = N'x.bak'"       # the same shape onto a DISPOSABLE name
_R5_HEREDOC_EARLY = ("git commit -m \"$(cat <<'EOF'\nfix: a note\nEOF\n"
                     "sqlcmd -E -Q \"{sql}\"\nEOF\n)\"")


def _r5_heredoc_early(sql: str) -> str:
    """The tag line ends the heredoc at once; a command runs between it and the line the scanner takes as the end."""
    return _R5_HEREDOC_EARLY.replace("{sql}", sql)


CASES += [
    # ---- B6: a piped or redirected echo-family command is NOT inert prose (BY-DESIGN green today; mutation twins) ----
    _blk_a("r5.B6.1 echo of a restore onto the dev name piped into sqlcmd  [by-design green: mutation twin of 'and not piped']",
           _bash(f'echo "{_R5_RESTORE}" | sqlcmd -E')),
    _blk_a("r5.B6.2 printf of a restore onto the dev name piped into sqlcmd  [by-design green: mutation twin of 'and not piped']",
           _bash(f"printf '%s' \"{_R5_RESTORE}\" | sqlcmd -E")),
    _blk_a("r5.B6.3 echo of a restore onto the dev name redirected to a file, then run with -i  [by-design green: twin of 'and not redirected']",
           _bash(f'echo "{_R5_RESTORE}" > r.sql && sqlcmd -E -i r.sql')),
    _blk_a("r5.B6.4 PowerShell Write-Output of a restore onto the dev name piped into sqlcmd  [by-design green: twin of 'and not piped']",
           _ps(f'Write-Output "{_R5_RESTORE}" | sqlcmd -E')),
    _blk_a("r5.B6.5 PowerShell Write-Output redirected to a file, then run with -i  [by-design green: twin of 'and not redirected']",
           _ps(f'Write-Output "{_R5_RESTORE}" > r.sql; sqlcmd -E -i r.sql')),
    _ok_audited("r5.B6.6 echo of a restore onto a DISPOSABLE name piped into sqlcmd  [by-design green: audited allow twin]",
                _bash(f'echo "{_R5_RESTORE_D}" | sqlcmd -E')),
    _ok_audited("r5.B6.7 echo of a restore onto a DISPOSABLE name redirected, then run with -i  [by-design green: audited allow twin]",
                _bash(f'echo "{_R5_RESTORE_D}" > r.sql && sqlcmd -E -i r.sql')),

    # ---- Controls (BY-DESIGN green): plain prose that merely mentions a restore stays allowed ----
    _ok("r5.C.1 a plain unpiped echo naming a restore onto the dev name  [by-design green]",
        _bash(f'echo "{_R5_RESTORE}"')),
    _ok("r5.C.2 a plain Write-Output naming a restore onto the dev name  [by-design green]",
        _ps(f'Write-Output "{_R5_RESTORE}"')),
    _ok("r5.C.3 a grep pattern naming a restore onto the dev name  [by-design green]",
        _bash(f"grep -n '{_R5_RESTORE}' notes.md")),
    _ok("r5.C.4 a git commit -m naming a restore onto the dev name  [by-design green]",
        _bash(f'git commit -m "docs: {_R5_RESTORE} is refused for agents"')),
    _ok("r5.C.5 a gh pr create --body naming a restore onto the dev name  [by-design green]",
        _bash(f'gh pr create --title "t" --body "A {_R5_RESTORE} is refused for agents"')),
    _ok("r5.C.6 a heredoc commit message that names a restore onto the dev name, tag line directly before the paren  [by-design green]",
        _bash("git commit -m \"$(cat <<'EOF'\nfix: note\n" + _R5_RESTORE + "\nEOF\n)\"")),

    # ---- F1 route 1: an unquoted command substitution / backticks / group inside a prose command's arguments ----
    _blk_a("r5.F1.1 echo with an unquoted command substitution that runs sqlcmd with a restore onto the dev name  [RED today]",
           _bash(f'echo $(sqlcmd -E -Q "{_R5_RESTORE}")')),
    _blk_a("r5.F1.2 git commit -m with an unquoted command substitution that runs the restore  [RED today]",
           _bash(f'git commit -m $(sqlcmd -E -Q "{_R5_RESTORE}")')),
    _blk_a("r5.F1.3 grep with an unquoted command substitution that runs the restore  [RED today]",
           _bash(f'grep -r $(sqlcmd -E -Q "{_R5_RESTORE}") .')),
    _blk_a("r5.F1.4 gh issue comment with an unquoted command substitution that runs the restore  [RED today]",
           _bash(f'gh issue comment 1 --body $(sqlcmd -E -Q "{_R5_RESTORE}")')),
    _blk_a("r5.F1.5 echo with a pair of backticks that runs the restore  [RED today]",
           _bash(f'echo `sqlcmd -E -Q "{_R5_RESTORE}"`')),
    _blk_a("r5.F1.6 printf with a command substitution that runs the restore  [RED today]",
           _bash(f"printf '%s' $(sqlcmd -E -Q \"{_R5_RESTORE}\")")),
    _blk_a("r5.F1.7 PowerShell Write-Output wrapping a parenthesised Invoke-Sqlcmd restore  [RED today]",
           _ps(f'Write-Output (Invoke-Sqlcmd -Query "{_R5_RESTORE}")')),
    _blk_a("r5.F1.8 PowerShell Write-Host wrapping a $( ) subexpression that runs the restore  [RED today]",
           _ps(f'Write-Host $(Invoke-Sqlcmd -Query "{_R5_RESTORE}")')),
    _blk_a("r5.F1.9 echo wrapping a quoted-host EF rollback to zero inside a command substitution  [RED today]",
           _bash(f'echo $("C:\\Program Files\\dotnet\\dotnet.exe" ef database {_UPDV} 0 --project src/X.Persistence)')),
    _blk_a("r5.F1.10 PowerShell Write-Output wrapping a parenthesised quoted-host EF rollback to zero  [by-design green today: the call operator & splits the segment, so the host is not in the prose segment]",
           _ps(f'Write-Output ({_PS_DOTNET_Q} ef database {_UPDV} 0 --project src/X.Persistence)')),
    _ok_audited("r5.F1.11 echo with a command substitution that runs a restore onto a DISPOSABLE name  [RED today: no audit record; green once read]",
                _bash(f'echo $(sqlcmd -E -Q "{_R5_RESTORE_D}")')),
    _ok_audited("r5.F1.12 PowerShell Write-Output wrapping a parenthesised restore onto a DISPOSABLE name  [RED today: no audit record; green once read]",
                _ps(f'Write-Output (Invoke-Sqlcmd -Query "{_R5_RESTORE_D}")')),

    # ---- F1 route 2: quote desync. Bash: a backslash pair then a quote opens a real quote; the scanner reads the
    #      first quote as escaped. PowerShell: a backslash never escapes, so the same text pairs differently. ----
    _blk_a("r5.F1.13 bash: echo, an escaped-backslash pair, an empty string, then an executed restore in single quotes  [RED today]",
           _bash(f"echo x\\\\\"\" ; sqlcmd -E -Q '{_R5_RESTORE}' ; echo \"y\"")),
    _blk_a("r5.F1.14 PowerShell: Write-Output, a lone backslash, an empty string, then an executed restore in single quotes  [RED today]",
           _ps(f"Write-Output x\\\"\" ; Invoke-Sqlcmd -Query '{_R5_RESTORE}' ; Write-Output \"y\"")),
    _ok_audited("r5.F1.15 bash: the same desync shape onto a DISPOSABLE name  [RED today: no audit record; green once read]",
                _bash(f"echo x\\\\\"\" ; sqlcmd -E -Q '{_R5_RESTORE_D}' ; echo \"y\"")),

    # ---- F1 route 3: the heredoc tag line ends it early; a command runs before the line the scanner takes as the end ----
    _blk_a("r5.F1.16 commit-message heredoc: a restore runs between the first tag line and the closing paren  [RED today]",
           _bash(_r5_heredoc_early(_R5_RESTORE))),
    _ok_audited("r5.F1.17 the same early-tag heredoc shape with a restore onto a DISPOSABLE name  [RED today: no audit record; green once read]",
                _bash(_r5_heredoc_early(_R5_RESTORE_D))),

    # ---- F1 route 4: a search command or gh that is piped or fed stdin is not inert; gh alias set stores a command ----
    _blk_a("r5.F1.18 grep fed a here-string holding the restore, piped into sqlcmd  [RED today]",
           _bash(f'grep -h . <<< "{_R5_RESTORE}" | sqlcmd -E')),
    _blk_a("r5.F1.19 rg fed a here-string holding the restore, piped into sqlcmd  [RED today]",
           _bash(f'rg . <<< "{_R5_RESTORE}" | sqlcmd -E')),
    _blk_a("r5.F1.20 grep fed a here-string holding the restore, redirected to a file that sqlcmd then runs  [RED today]",
           _bash(f'grep -h . <<< "{_R5_RESTORE}" > r.sql && sqlcmd -E -i r.sql')),
    _blk_a("r5.F1.21 gh api fed a here-string holding the restore, piped into sqlcmd  [RED today]",
           _bash(f'gh api user <<< "{_R5_RESTORE}" | sqlcmd -E')),
    _blk_a("r5.F1.22 gh alias set storing a shell command that holds the restore  [RED today]",
           _bash(f"gh alias set rst --shell 'sqlcmd -E -Q \"{_R5_RESTORE}\"'")),
    _ok_audited("r5.F1.23 grep fed a here-string holding a restore onto a DISPOSABLE name, piped into sqlcmd  [RED today: no audit record; green once read]",
                _bash(f'grep -h . <<< "{_R5_RESTORE_D}" | sqlcmd -E')),
    _ok_audited("r5.F1.24 gh alias set storing a shell command with a restore onto a DISPOSABLE name  [RED today: no audit record; green once read]",
                _bash(f"gh alias set rst --shell 'sqlcmd -E -Q \"{_R5_RESTORE_D}\"'")),

    # ---- WARN-F1: DB_GUARD_FAULT_INJECTION=parser must not turn a protected-database-write block into an allow ----
    _blk_a("r5.W1.0 control: a protected-database write from a shell blocks without the switch  [by-design green]",
           _bash(f'sqlcmd -E -d {_DB_PROT} -Q "UPDATE Users SET Name = \'x\' WHERE Id = 1"'),
           "protected-db-write-from-non-production-path"),
    _blk_a("r5.W1.1 the same protected-database write still blocks with the parser fault switch set  [RED today: the switch allows it]",
           _bash(f'sqlcmd -E -d {_DB_PROT} -Q "UPDATE Users SET Name = \'x\' WHERE Id = 1"'),
           env={"DB_GUARD_FAULT_INJECTION": "parser"}),
    _blk_a("r5.W1.2 a protected-database write through a Write tool outside the production paths still blocks with the switch  [RED today]",
           _write("d:/Dev/Foo/tools/other/fix.cmd",
                  f'sqlcmd -S "(localdb)\\m" -E -d {_DB_PROT} -Q "UPDATE Users SET Name = \'x\' WHERE Id = 1"'),
           env={"DB_GUARD_FAULT_INJECTION": "parser"}),
    Case(name="r5.W1.3 control: with the switch set and no match at all the hook stays fail-open  [by-design green] -> ALLOW",
         payload=_bash("git status --short"), expect_rc=0, isolate=True,
         env_extra={"DB_GUARD_FAULT_INJECTION": "parser"}),
]


# Self-checks that are not hook payloads. Each returns (passed, detail).
def _check_isolation_overrides_an_inherited_project_dir() -> tuple[bool, str]:
    """Round 2 (W1): a legacy case, run with a DECOY inherited CLAUDE_PROJECT_DIR, must not write there.

    Falsifiable: against a runner that isolates only some cases, the decoy log gains the record.
    """
    decoy = tempfile.mkdtemp(prefix="dbguard-decoy-")
    marker = f"Iso_{uuid.uuid4().hex[:12]}"
    legacy = Case(name="isolation probe", payload=_bash(f'sqlcmd -E -Q "{_DROP_DB} [{marker}]"'), expect_rc=2)
    try:
        base = dict(os.environ)
        base["CLAUDE_PROJECT_DIR"] = decoy
        ok, detail = run_case(legacy, base_env=base)
        if not ok:
            return False, f"the probe case itself did not behave (rc mismatch): {detail}"
        decoy_log = Path(decoy) / ".claude" / "logs" / "db-guard.log"
        if decoy_log.exists() and marker in decoy_log.read_text(encoding="utf-8", errors="replace"):
            return False, (
                f"the guard wrote its audit record into the INHERITED project directory ({decoy_log}): "
                "run_case does not isolate a case that carries no isolate flag"
            )
        return True, "ok"
    finally:
        shutil.rmtree(decoy, ignore_errors=True)


SELF_CHECKS = [
    ("dbp.ISO.1 a case with no isolate flag still writes no record into an inherited project dir",
     _check_isolation_overrides_an_inherited_project_dir),
]


def run_case(case: Case, base_env: dict | None = None) -> tuple[bool, str]:
    """Invoke the hook with the case's payload. Returns (passed, detail).

    EVERY case runs with CLAUDE_PROJECT_DIR pointed at a fresh throwaway directory (round 2, review
    finding W1): before this, only a subset did, so the older cases appended synthetic BLOCK records
    naming the protected database to the project's real audit log, the same log reviewers read as proof
    that no verification step touched the dev database. ``base_env`` exists only so the isolation
    self-check can hand the runner a decoy inherited project directory and prove it is overridden.
    """
    payload = dict(case.payload)
    if case.session_id:
        payload["session_id"] = case.session_id
    payload_json = json.dumps(payload)

    # Ensure no inherited override or fault switch leaks into the test process. The human override
    # is only ever REMOVED here, never set: agents must not set it.
    env = dict(os.environ if base_env is None else base_env)
    env.pop("CLAUDE_DESTRUCTIVE_DB_OK", None)
    env.pop("DB_GUARD_FAULT_INJECTION", None)
    env.update(case.env_extra)

    hook = HOOK
    scratch = tempfile.mkdtemp(prefix="dbguard-test-")
    env["CLAUDE_PROJECT_DIR"] = scratch
    try:
        # PLUGIN PORT (INV-O7 / INV-O3): the hook runs IN PLACE, from the plugin; the fixture project's own
        # .claude/hooks/ folder carries the rules. Nothing is copied beside the hook.
        project_hooks = Path(scratch) / ".claude" / "hooks"
        project_hooks.mkdir(parents=True)
        if case.rules_missing:
            # NO rules file in the project: the fail-closed path (every database protected).
            assert not (project_hooks / "db-destructive-guard.rules.json").exists()
        else:
            # The fixture rules, with the named keys replaced by a value of the wrong type when asked.
            rules = dict(_RULES)
            rules.update(case.rules_override)
            (project_hooks / "db-destructive-guard.rules.json").write_text(
                json.dumps(rules), encoding="utf-8")

        try:
            proc = subprocess.run(
                ["py", "-3", hook],
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

        if case.expect_audit_decision:
            return _check_audit(case, scratch)
        return True, "ok"
    finally:
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)


def _check_audit(case: Case, scratch: str | None) -> tuple[bool, str]:
    """Find the guard's OWN audit record for this case's unique session id and check it."""
    log = Path(scratch or "") / ".claude" / "logs" / "db-guard.log"
    if not log.exists():
        return False, (
            f"no audit log at {log}: the guard wrote no decision record, so an exit code of "
            f"{case.expect_rc} cannot be told apart from a crash that failed open"
        )
    records = []
    for line in log.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("session") == case.session_id:
            records.append(rec)
    if not records:
        return False, f"no audit record for session {case.session_id}: the guard never reached a decision"
    rec = records[-1]
    if rec.get("decision") != case.expect_audit_decision:
        return False, f"audit decision {rec.get('decision')!r} (expected {case.expect_audit_decision!r})"
    if case.expect_audit_reason and rec.get("reason") != case.expect_audit_reason:
        return False, f"audit reason {rec.get('reason')!r} (expected {case.expect_audit_reason!r})"
    if case.expect_targets:
        targets = rec.get("destructive_targets")
        if not isinstance(targets, list) or not targets:
            return False, (
                "audit record carries no destructive_targets list: the guard did not read a target "
                f"for this input (record keys: {sorted(rec)})"
            )
    return True, "ok"


def main() -> int:
    # The audit assertions are only meaningful if every session id is unique.
    sessions = [c.session_id for c in CASES if c.session_id]
    if len(sessions) != len(set(sessions)):
        print("FAIL  test setup: session ids are not unique")
        return 1
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
    for name, check in SELF_CHECKS:
        ok, detail = check()
        if ok:
            passed += 1
            print(f"  PASS  {name}")
        else:
            failed += 1
            print(f"  FAIL  {name}")
            print(f"        {detail}")
    print()
    print(f"results: {passed} passed, {failed} failed (of {len(CASES) + len(SELF_CHECKS)})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
