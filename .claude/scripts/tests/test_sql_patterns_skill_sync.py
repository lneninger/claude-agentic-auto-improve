#!/usr/bin/env python3
"""
test_sql_patterns_skill_sync.py -- keep /sql-server-patterns honest about the
reference it routes to and the guard it defers to.

House style: plain runnable script, NO pytest.

    py -3 .claude/scripts/tests/test_sql_patterns_skill_sync.py

--------------------------------------------------------------------------
WHAT THIS PINS DOWN
--------------------------------------------------------------------------
The skill is deliberately a ROUTER. tsql-patterns.md states in its own first
paragraph that callers consult it "rather than inlining examples", so the
skill carries an index of that file's sections and none of its SQL.

An index is a second copy of a closed set, and it rots in the direction that
is hardest to notice: a section renamed or added in the template leaves the
skill pointing at a heading that no longer exists, and the agent's most likely
recovery is to answer from memory -- which for this subject means inventing a
partitioning threshold. That is worse than no answer, and the skill says so.

The disposable-database suffixes are the same problem with teeth. The skill
tells an agent which suffix makes a migration-verification database legal;
db-destructive-guard.py decides whether it actually is. If those two lists
disagree, the skill instructs an agent into an operation the guard blocks --
or, far worse, names a suffix the guard does NOT recognise while implying it
is safe.

THE INVARIANTS

  INV-Q1  Every section heading in tsql-patterns.md is indexed by the skill.
  INV-Q2  The skill indexes no section the template does not have.
  INV-Q3  The skill inlines no T-SQL. It routes; it does not restate.
  INV-Q4  Every disposable-database suffix the skill names is one the guard
          actually recognises.
  INV-Q5  The skill names the two guards that bind it, and forbids setting the
          user-only override.
  INV-Q6  The skill states the boundary against the two SQL reviewers, both of
          which name it as the owner of the question they decline.
"""

from __future__ import annotations

import io
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills" / "sql-server-patterns" / "SKILL.md"
TEMPLATE = ROOT / ".claude" / "templates" / "tsql-patterns.md"
GUARD = ROOT / ".claude" / "hooks" / "db-destructive-guard.py"
REVIEWERS = [
    ROOT / "agents" / "migration-safety-reviewer.md",
    ROOT / "agents" / "sql-performance-reviewer.md",
]

_failures: list[str] = []
_passes = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _passes
    if cond:
        _passes += 1
        print("  PASS  %s" % name)
    else:
        _failures.append(name)
        print("  FAIL  %s%s" % (name, ("  -- " + detail) if detail else ""))


def read(path: pathlib.Path) -> str:
    return io.open(path, encoding="utf-8", errors="ignore").read()


print("\nsource files are present")
for path in [SKILL, TEMPLATE, GUARD] + REVIEWERS:
    check("%s exists" % path.relative_to(ROOT).as_posix(), path.is_file())
if _failures:
    print("\nabort: cannot compare against files that are not there")
    print("\n%s\n %d passed, %d failed\n%s" % ("-" * 60, _passes, len(_failures), "-" * 60))
    sys.exit(1)

skill = read(SKILL)
template = read(TEMPLATE)
guard = read(GUARD)

# Headings of the reference, minus its title.
sections = [h.strip() for h in re.findall(r"^##\s+(.+)$", template, re.M)]

print("\nINV-Q1  every template section is indexed by the skill")
check("template exposes sections", len(sections) >= 5, str(sections))
for heading in sections:
    # Compare on the distinctive leading words -- an index row may shorten a
    # heading ("Hierarchical data - 4 options" -> "Hierarchical data"), but it
    # may not point at something absent.
    stem = re.split(r"\s+[-—(]\s*", heading)[0].strip()
    check("skill indexes '%s'" % heading, stem.lower() in skill.lower(), "stem=%r" % stem)

print("\nINV-Q2  the skill indexes nothing the template lacks")
# Rows of the Step 1 index table, first cell, bolded.
indexed = [m.strip() for m in re.findall(r"^\|\s*\*\*(.+?)\*\*\s*\|", skill, re.M)]
check("the index table was found", bool(indexed), str(indexed))
for row in indexed:
    stem = re.split(r"\s+[-—(]\s*", row)[0].strip()
    check("'%s' exists in the template" % row, stem.lower() in template.lower())

print("\nINV-Q3  the skill routes and does not restate")
fences = re.findall(r"```(\w*)\n", skill)
check("the skill contains no ```sql fence",
      not any(f.lower() == "sql" for f in fences), str(fences))
for keyword in ("CREATE PARTITION FUNCTION", "SYSTEM_VERSIONING", "DATA_COMPRESSION",
                "PERIOD FOR SYSTEM_TIME", "CREATE PARTITION SCHEME"):
    check("no inlined T-SQL: %s" % keyword, keyword not in skill)
check("the skill cites the template by path",
      ".claude/templates/tsql-patterns.md" in skill)
check("the skill forbids reconstructing patterns from memory",
      bool(re.search(r"[Dd]o not reconstruct|from memory", skill)))

print("\nINV-Q4  every disposable suffix named is one the guard recognises")
named = set(re.findall(r"`(_[A-Za-z][A-Za-z0-9_<>-]*)`", skill))
suffixes = {s for s in named if s.lower().startswith("_")
            and s not in {"_comment", "_extension_seam"}}
check("the skill names disposable suffixes", bool(suffixes), str(sorted(suffixes)))
for suffix in sorted(suffixes):
    stem = suffix.split("<")[0].rstrip("_") or suffix
    check("guard recognises %s" % suffix,
          stem.lower() in guard.lower() or suffix.lower() in guard.lower())

print("\nINV-Q5  the skill names the guards that bind it")
for hook in ("db-destructive-guard.py", "db-research-readonly-guard.py"):
    check("skill names %s" % hook, hook in skill)
check("skill forbids setting CLAUDE_DESTRUCTIVE_DB_OK",
      bool(re.search(r"Never set `?CLAUDE_DESTRUCTIVE_DB_OK", skill)))
check("skill states the guards fail closed", "fail closed" in skill.lower())
check("skill forbids executing DDL itself",
      bool(re.search(r"issues no `?CREATE|never to them|does not execute", skill)))

print("\nINV-Q6  the boundary against the two reviewers is stated on both sides")
for path in REVIEWERS:
    text = read(path)
    check("%s still defers to this skill" % path.name,
          "sql-server-patterns" in text)
    check("  ...and the skill names %s back" % path.stem,
          path.stem in skill)

print("\n%s\n %d passed, %d failed\n%s"
      % ("-" * 60, _passes, len(_failures), "-" * 60))
sys.exit(1 if _failures else 0)
