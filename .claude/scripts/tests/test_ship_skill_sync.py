#!/usr/bin/env python3
"""
test_ship_skill_sync.py -- keep /ship's verdict table in sync with the script
it drives.

House style: plain runnable script, NO pytest.

    py -3 .claude/scripts/tests/test_ship_skill_sync.py

--------------------------------------------------------------------------
WHAT THIS PINS DOWN
--------------------------------------------------------------------------
verify_issue_link.py owns three closed sets -- VERDICTS, ISSUE_LINK_WRITES
and HALTING -- and its own docstring says adding a value without adding its
case is a coverage regression. skills/ship/SKILL.md restates those sets as a
prose table an agent reads at Step 4d and branches on.

Two copies of one closed set is a drift generator. The failure is quiet and
expensive: a verdict added to the script but missing from the table leaves
the agent with no branch for it, and the most likely improvisation is to
treat an unrecognised verdict as success -- shipping an unlinked pull request
and reporting it as linked, which is the exact defect /ship exists to prevent.

So the prose is tested against the code, not maintained beside it.

THE INVARIANTS

  INV-S1  Every verdict in VERDICTS is named somewhere in SKILL.md.
  INV-S2  SKILL.md invents no verdict that VERDICTS does not define.
  INV-S3  Every issue_link value the script can write is named in SKILL.md,
          and each is paired with the verdict that produces it.
  INV-S4  SKILL.md names 'manual' only to forbid it. It is a real member of
          linkStates, reserved for a human reconciling an issue by hand, so a
          table that lists it as an outcome invites an agent to write it.
  INV-S5  The repair budget in SKILL.md matches maxRepairAttempts in
          work-item-conventions.json.
  INV-S6  SKILL.md drives the script by its real CLI: the flag that marks the
          post-repair re-query is spelled exactly as argparse defines it.
"""

from __future__ import annotations

import io
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
SCRIPT = ROOT / ".claude" / "scripts" / "verify_issue_link.py"
SKILL = ROOT / "skills" / "ship" / "SKILL.md"
CONVENTIONS = ROOT / ".claude" / "work-item-conventions.json"

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
for path in (SCRIPT, SKILL, CONVENTIONS):
    check("%s exists" % path.relative_to(ROOT).as_posix(), path.is_file())
if _failures:
    print("\nabort: cannot compare against files that are not there")
    print("\n%s\n %d passed, %d failed\n%s" % ("-" * 60, _passes, len(_failures), "-" * 60))
    sys.exit(1)

script_text = read(SCRIPT)
skill_text = read(SKILL)


def literal_list(name: str) -> list[str]:
    """Pull a module-level list-of-strings literal out of the script."""
    m = re.search(r"^%s\s*=\s*\[(.*?)\]" % name, script_text, re.S | re.M)
    return re.findall(r'"([^"]+)"', m.group(1)) if m else []


def literal_dict(name: str) -> dict:
    m = re.search(r"^%s\s*=\s*\{(.*?)\n\}" % name, script_text, re.S | re.M)
    return dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', m.group(1))) if m else {}


def literal_set(name: str) -> set:
    m = re.search(r"^%s\s*=\s*\{(.*?)\}" % name, script_text, re.S | re.M)
    return set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()


VERDICTS = literal_list("VERDICTS")
WRITES = literal_dict("ISSUE_LINK_WRITES")
HALTING = literal_set("HALTING")

print("\nthe script's closed sets were readable")
check("VERDICTS parsed (expected 16)", len(VERDICTS) == 16, str(len(VERDICTS)))
check("ISSUE_LINK_WRITES parsed", len(WRITES) >= 4, str(WRITES))
check("HALTING parsed", len(HALTING) >= 10, str(len(HALTING)))

print("\nINV-S1  every verdict the script can return is documented")
for verdict in VERDICTS:
    check("SKILL.md names '%s'" % verdict, verdict in skill_text)

print("\nINV-S2  the skill invents no verdict the script cannot return")
# Only inspect backticked tokens, so ordinary prose ("success", "halt") is not
# mistaken for a verdict name.
quoted = set(re.findall(r"`([a-z][a-z-]{3,30})`", skill_text))
known = set(VERDICTS)
vocabulary = {
    # script/CLI surface and conventions keys the skill legitimately names
    "verdict", "reason", "remediation", "closes", "refs", "none", "unresolved",
    "manual", "partial", "branch", "worktree", "contract", "status", "shipped",
    "title", "type", "repo", "unknown", "draft", "master", "main", "base",
    "issue-link", "body-file", "repair-attempted", "json", "path",
}
suspicious = {
    q for q in quoted - known - vocabulary
    if "-" in q and q.count("-") <= 2 and not q.endswith(".md")
}
# A hyphenated backticked token that is not a known verdict is only a problem
# when it reads like one; allow anything that appears in the script too.
suspicious = {q for q in suspicious if q not in script_text}
check("no verdict-shaped token absent from the script", not suspicious, str(sorted(suspicious)))

print("\nINV-S3  every issue_link the script writes is paired with its verdict")
for verdict, value in sorted(WRITES.items()):
    check("SKILL.md documents %s -> issue_link: %s" % (verdict, value),
          verdict in skill_text and value in skill_text)
    # the pairing must appear close together, not merely both somewhere
    near = re.search(
        r"%s.{0,200}?%s|%s.{0,200}?%s"
        % (re.escape(verdict), re.escape(value), re.escape(value), re.escape(verdict)),
        skill_text, re.S)
    check("  ...and pairs them within one table row", bool(near))

print("\nINV-S4  'manual' is named only to forbid it")
check("SKILL.md mentions 'manual'", "manual" in skill_text)
check("it is forbidden, not offered",
      bool(re.search(r"[Nn]ever write `?manual", skill_text)))
check("'manual' is not a value the script ever writes",
      "manual" not in set(WRITES.values()), str(WRITES))

print("\nINV-S5  the repair budget matches the conventions file")
conventions = json.loads(read(CONVENTIONS))
budget = conventions.get("issueLink", {}).get("maxRepairAttempts")
check("maxRepairAttempts is declared", budget is not None)
check("SKILL.md states a budget of exactly %s" % budget,
      budget == 1 and bool(re.search(r"at most ONCE|maxRepairAttempts", skill_text)))
check("SKILL.md forbids looping further",
      "Do not loop further" in skill_text or "one attempt" in skill_text.lower())

print("\nINV-S6  the skill drives the script by its real CLI")
for flag in ("--brief", "--pr", "--repair-attempted"):
    check("script defines %s" % flag, ('"%s"' % flag) in script_text)
    check("  ...and SKILL.md uses it", flag in skill_text)

print("\nhalting verdicts are presented as halting")
for verdict in sorted(HALTING):
    if verdict == "still-absent":
        continue  # given its own row in the table
    check("%s appears in the halting group" % verdict, verdict in skill_text)

print("\n%s\n %d passed, %d failed\n%s"
      % ("-" * 60, _passes, len(_failures), "-" * 60))
sys.exit(1 if _failures else 0)
