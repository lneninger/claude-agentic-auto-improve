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
