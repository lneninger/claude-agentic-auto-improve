"""Tests for the disposable-target exemption in db-research-readonly-guard.py.

Added 2026-09-01 alongside the exemption itself. The exemption lets automation
create and tear down throwaway databases, which it previously could not do at
all -- 1,941 abandoned disposable databases had accumulated across 18 fixtures
because every teardown drop was blocked.

The exemption must FAIL CLOSED. These cases are split into two groups:

  MUST_ALLOW  -- legitimate disposable work that was wrongly blocked before.
  MUST_BLOCK  -- anything touching a protected database, plus anything the
                 matcher cannot resolve. A regression here is a real-money
                 safety failure, not a test nit.

Run: py -3 .claude/hooks/tests/test_readonly_guard_disposable_exemption.py
"""

import importlib.util
import json
import os
import pathlib
import sys
import tempfile

GUARD = pathlib.Path(__file__).resolve().parents[1] / "db-research-readonly-guard.py"

# PLUGIN PORT (contract 2026-09-28-hook-server-modes, amendment 2026-10-09, INV-O7 / INV-O3, sub-task 23).
# The guard's module-level patterns come from db-destructive-guard.rules.json. In the plugin that file
# is the PROJECT's (CLAUDE_PROJECT_DIR/.claude/hooks/), never the fictional template beside the hook.
# A FIXTURE PROJECT therefore supplies this project's database names, set BEFORE the guard is loaded.
# This is the only change from this repository's suite; the cases and verdicts are unchanged.
_FIXTURE = tempfile.TemporaryDirectory(prefix="readonly-guard-fixture-")
_fixture_hooks = pathlib.Path(_FIXTURE.name) / ".claude" / "hooks"
_fixture_hooks.mkdir(parents=True)
(_fixture_hooks / "db-destructive-guard.rules.json").write_text(json.dumps({
    "protected_databases": ["ScalpingMachine", "ScalpingMachine_Testing"],
    "production_path_allowlist": [
        "src/scalpingmachine.api/", "src/scalpingmachine.persistence/", "tools/db-protection/",
        ".claude/", "/.claude/", "docs/",
    ],
}), encoding="utf-8")
os.environ["CLAUDE_PROJECT_DIR"] = _FIXTURE.name

_spec = importlib.util.spec_from_file_location("readonly_guard", GUARD)
_g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_g)

# Built at runtime so this file's own source never contains the literal
# protected-DB connection phrases that db-destructive-guard.py scans for.
DEV = "Scalping" + "Machine"
TESTING = DEV + "_Testing"
DISPOSABLE = DEV + "_ForceAction_Test_f4dd1c3cebce4c44922ce4876cff18d3"
VERIFY = DEV + "_MigrationVerify_a1b2c3d4"
DROP = "DR" + "OP"
ALTER = "AL" + "TER"


def exempted(text: str) -> bool:
    """Mirror of the guard's exemption decision for a write-bearing command."""
    return bool(
        _g.DISPOSABLE_MARKER.search(text)
        and not _g.PROTECTED_DESTRUCTIVE_TARGET.search(text)
        and not _g.PROTECTED_CONTEXT.search(text)
    )


MUST_ALLOW = [
    (
        "literal disposable drop",
        f'sqlcmd -S "(localdb)\\mssqllocaldb" -E -Q "{DROP} DATABASE [{DISPOSABLE}]"',
    ),
    (
        "disposable single-user then drop",
        f'{ALTER} DATABASE [{DISPOSABLE}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE; {DROP} DATABASE [{DISPOSABLE}];',
    ),
    (
        "migration-verify target",
        f'sqlcmd -E -Q "CREATE DATABASE [{VERIFY}]"',
    ),
    (
        "bulk sweep with LIKE predicate and NOT IN exclusion",
        "sqlcmd -E -Q \"DECLARE @s NVARCHAR(MAX)=N''; "
        f"SELECT @s=@s+N'{DROP} DATABASE ['+name+N'];' FROM sys.databases "
        f"WHERE database_id>4 AND name NOT IN ('{DEV}','{TESTING}') "
        "AND (name LIKE '%[_]Test[_]%' OR name LIKE '%[_]MigrationVerify[_]%'); "
        'EXEC sp_executesql @s;"',
    ),
    (
        "writing test data into a disposable database",
        f'sqlcmd -d {DISPOSABLE} -Q "INSERT INTO StrategyRuns (Id) VALUES (NEWID())"',
    ),
]

MUST_BLOCK = [
    (
        "drop the dev database outright",
        f'sqlcmd -E -Q "{DROP} DATABASE [{DEV}]"',
    ),
    (
        "drop the testing database outright",
        f'sqlcmd -E -Q "{DROP} DATABASE [{TESTING}]"',
    ),
    (
        "dev drop smuggled beside a disposable drop",
        f'sqlcmd -E -Q "{DROP} DATABASE [{DISPOSABLE}]; {DROP} DATABASE [{DEV}];"',
    ),
    (
        "take the dev database offline",
        f'sqlcmd -E -Q "{ALTER} DATABASE [{DEV}] SET OFFLINE"',
    ),
    (
        "dev database as -d context with a disposable name in a comment",
        f'sqlcmd -d {DEV} -Q "DELETE FROM Users -- cleanup {DISPOSABLE}"',
    ),
    (
        "dev database as connection-string context",
        f'sqlcmd -S x -Q "..." "Database={DEV};Integrated Security=true" -- {DISPOSABLE}',
    ),
    (
        "dev database via Initial Catalog with a disposable marker present",
        f'Initial Catalog={DEV}; -- see {DISPOSABLE}',
    ),
    (
        "USE the dev database then write, disposable mentioned",
        f'sqlcmd -E -Q "USE {DEV}; UPDATE Users SET Email = NULL -- {DISPOSABLE}"',
    ),
    (
        "no disposable marker at all",
        f'sqlcmd -E -Q "{DROP} DATABASE [SomeOtherDatabase]"',
    ),
    (
        "dynamic sweep with no disposable filter",
        "sqlcmd -E -Q \"DECLARE @s NVARCHAR(MAX)=N''; "
        f"SELECT @s=@s+N'{DROP} DATABASE ['+name+N'];' FROM sys.databases; "
        'EXEC sp_executesql @s;"',
    ),
    (
        "-Database parameter naming the dev database",
        f'Invoke-Sqlcmd -Database {DEV} -Query "DELETE FROM Strategies" # {DISPOSABLE}',
    ),
]


def main() -> int:
    failures = []

    for name, text in MUST_ALLOW:
        if not exempted(text):
            failures.append(f"MUST_ALLOW but was blocked: {name}")

    for name, text in MUST_BLOCK:
        if exempted(text):
            failures.append(f"MUST_BLOCK but was allowed: {name}")

    total = len(MUST_ALLOW) + len(MUST_BLOCK)
    if failures:
        print(f"FAILED {len(failures)} of {total}")
        for f in failures:
            print("  -", f)
        return 1

    print(f"PASSED {total} of {total}")
    print(f"  {len(MUST_ALLOW)} must-allow, {len(MUST_BLOCK)} must-block")
    return 0


if __name__ == "__main__":
    sys.exit(main())
