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
  INV-S7  The recorded issue-offer outcome (issue #57, contract
          2026-10-16-recorded-issue-offer-outcome.md): the conventions file
          declares the offer keys, /ship names the field and every outcome,
          /task and /design-first name the field, and all three call sites
          create the issue with --body-file, never an inline body.
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
check("VERDICTS parsed (expected 19)", len(VERDICTS) == 19, str(len(VERDICTS)))
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

print("\nINV-S7  the recorded issue-offer outcome is declared and named by all three call sites")
link_block = conventions.get("issueLink", {})
FIELD = "issue_offer"
OUTCOMES = ["pending", "opened", "declined", "unavailable"]
check("conventions declares offerOutcomeField == %r" % FIELD,
      link_block.get("offerOutcomeField") == FIELD, str(link_block.get("offerOutcomeField")))
check("conventions declares offerOutcomes == %s" % OUTCOMES,
      link_block.get("offerOutcomes") == OUTCOMES, str(link_block.get("offerOutcomes")))
check("conventions declares offerReasonField == 'issue_offer_reason'",
      link_block.get("offerReasonField") == "issue_offer_reason",
      str(link_block.get("offerReasonField")))
check("conventions declares the four offerReasons",
      link_block.get("offerReasons") == ["gh-missing", "gh-unauthenticated",
                                         "create-failed", "no-problem-statement"],
      str(link_block.get("offerReasons")))
check("conventions turns requireRecordedOffer on (this repository)",
      link_block.get("requireRecordedOffer") is True,
      str(link_block.get("requireRecordedOffer", "<absent>")))
field = link_block.get("offerOutcomeField") or FIELD
outcomes = link_block.get("offerOutcomes") or OUTCOMES
def names_field(text: str) -> bool:
    """The field as a whole word: 'issue_offer' must not match 'issue_offer_reason'."""
    return re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(field), text) is not None


check("word-boundary matcher: 'issue_offer_reason' alone does NOT name the field",
      not names_field("only `issue_offer_reason: gh-missing` here") and
      names_field("writes `issue_offer: pending`"))
check("SKILL.md (ship) names the field '%s'" % field, names_field(skill_text))
for outcome in outcomes:
    check("SKILL.md (ship) names the outcome '%s'" % outcome,
          re.search(r"(?<![A-Za-z-])%s(?![A-Za-z-])" % re.escape(outcome), skill_text)
          is not None)
for reason in ("create-failed", "no-problem-statement"):
    check("SKILL.md (ship) names the reason '%s' (the Step 3.5 gate rule)" % reason,
          reason in skill_text)
check("SKILL.md (ship) names the halting cause 'brief-path-unresolved'",
      "brief-path-unresolved" in skill_text)

SKILLS = {
    "ship": SKILL,
    "task": ROOT / "skills" / "task" / "SKILL.md",
    "design-first": ROOT / "skills" / "design-first" / "SKILL.md",
}
def fenced_commands(text: str) -> list[str]:
    """Every logical command inside a fenced block, backslash continuations joined."""
    commands: list[str] = []
    in_fence = False
    pending = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            if pending:
                commands.append(pending)
                pending = ""
            continue
        if not in_fence:
            continue
        if stripped.endswith("\\"):
            pending += stripped[:-1].rstrip() + " "
            continue
        commands.append(pending + stripped)
        pending = ""
    return commands


check("fenced_commands joins a backslash-continued inline --body into one command",
      fenced_commands("```bash\ngh issue create --title t \\\n  --body \"x\"\n```")
      == ['gh issue create --title t --body "x"'])

ASSUMED = re.compile(
    r"assum.{0,300}?pending.{0,300}?(never|not).{0,60}?declined"
    r"|assum.{0,300}?(never|not).{0,60}?declined.{0,200}?pending", re.S | re.I)

for label, path in SKILLS.items():
    text = read(path) if path.is_file() else ""
    if label != "ship":
        check("skills/%s/SKILL.md names the field '%s'" % (label, field), names_field(text))
    check("skills/%s/SKILL.md: an assumed answer writes pending and never declined (I-4)" % label,
          bool(ASSUMED.search(text)))
    create_cmds = [c for c in fenced_commands(text)
                   if "gh issue create" in c and "--parent" not in c]
    check("skills/%s/SKILL.md shows a 'gh issue create' command" % label,
          len(create_cmds) >= 1, "found %d" % len(create_cmds))
    check("skills/%s/SKILL.md: every 'gh issue create' uses --body-file" % label,
          bool(create_cmds) and all("--body-file" in c for c in create_cmds),
          str(create_cmds))
    check("skills/%s/SKILL.md: no 'gh issue create' passes an inline --body" % label,
          not any(re.search(r"--body(?!-file)", c) for c in create_cmds),
          str(create_cmds))

task_text = read(SKILLS["task"]) if SKILLS["task"].is_file() else ""
check("/task template writes 'issue_offer: pending'",
      re.search(r"^\s*issue_offer:\s*pending\b", task_text, re.M) is not None)
check("/task template has NO 'issue_offer_reason:' line (I-6)",
      re.search(r"^\s*issue_offer_reason:", task_text, re.M) is None)

unrecorded_rows = [ln for ln in skill_text.splitlines()
                   if ln.lstrip().startswith("|") and "offer-unrecorded" in ln]
check("ship's Step 4d table has an 'offer-unrecorded' row", len(unrecorded_rows) >= 1,
      "found %d" % len(unrecorded_rows))
row = " ".join(unrecorded_rows)
check("the 'offer-unrecorded' row says to re-run Step 4d",
      re.search(r"re-?run[^|]{0,60}4d|4d[^|]{0,60}re-?run", row, re.I) is not None, row)
check("the 'offer-unrecorded' row says not to create the pull request again",
      re.search(r"(do not|don't|never|not)[^|]{0,40}(create|open)[^|]{0,40}"
                r"(pull request|PR)[^|]{0,20}again", row, re.I) is not None, row)

def section(text: str, start: str, end: str) -> str:
    a = text.find(start)
    b = text.find(end, a + len(start)) if a >= 0 else -1
    return text[a:b] if a >= 0 and b >= 0 else ""


def chunks(text: str) -> list[str]:
    """Paragraphs and list items, so one bullet is judged on its own words."""
    out: list[str] = []
    cur: list[str] = []
    for ln in text.splitlines():
        if not ln.strip() or ln.lstrip().startswith("- "):
            if cur:
                out.append(" ".join(cur))
            cur = [ln.strip()] if ln.strip() else []
        else:
            cur.append(ln.strip())
    if cur:
        out.append(" ".join(cur))
    return out


step35 = section(skill_text, "## Step 3.5", "## Step 4:")
check("found the Step 3.5 section", bool(step35))
gh_gone = [c for c in chunks(step35)
           if re.search(r"`gh` is not available|gh is not available|gh-missing|gh-unauthenticated", c)
           and "offer-unrecorded" in c
           and not re.search(r"stale", c)]
check("Step 3.5 does not name offer-unrecorded as the verdict for 'gh not available' "
      "(that case halts earlier, unverifiable / gh-missing)", bool(step35) and not gh_gone,
      str(gh_gone))

notes = section(skill_text, "## Notes", "Closes #<id>")
check("found the Step 3 Notes template", bool(notes))
check("the Notes line lists the still-valid reasons create-failed and no-problem-statement",
      "create-failed" in notes and "no-problem-statement" in notes, notes[-300:])
check("the Notes line does not list the stale reasons gh-missing / gh-unauthenticated",
      "gh-missing" not in notes and "gh-unauthenticated" not in notes, notes[-300:])

def says_find_existing_issue_first(text: str) -> list[str]:
    """Meaningful words, not a whole sentence. Returns the list of missing ideas."""
    missing = []
    if not re.search(r"look(ing)? (for|up)|search|find|found", text, re.I):
        missing.append("look for / search / find")
    if not re.search(r"exact title", text, re.I):
        missing.append("by its exact title")
    if not re.search(r"already (been )?(created|exists?|opened|made)|already-created", text, re.I):
        missing.append("the issue already created")
    if not re.search(r"write[^.|]{0,60}\bid\b|\bid\b[^.|]{0,40}back", text, re.I):
        missing.append("write its id back")
    if not (re.search(r"\bonly\b", text, re.I)
            and re.search(r"\bnone\b|not found|no (such |matching )?issue|nothing", text, re.I)
            and re.search(r"create", text, re.I)):
        missing.append("only offer to create when none is found")
    return missing


opened_chunks = " ".join(c for c in chunks(step35) if "opened" in c)
miss_gate = says_find_existing_issue_first(opened_chunks)
check("Step 3.5 says, for 'opened' with an absent id, to find the issue already created "
      "by its exact title, write its id back, and offer to create only if none is found",
      bool(opened_chunks) and not miss_gate,
      "missing ideas: %s" % miss_gate if opened_chunks else "no Step 3.5 text names 'opened'")
miss_row = says_find_existing_issue_first(" ".join(unrecorded_rows))
check("the 'offer-unrecorded' row says the same (find by exact title, write the id back, "
      "create only if none is found)", not miss_row, "missing ideas: %s" % miss_row)

print("\nhalting verdicts are presented as halting")
for verdict in sorted(HALTING):
    if verdict == "still-absent":
        continue  # given its own row in the table
    check("%s appears in the halting group" % verdict, verdict in skill_text)

print("\n%s\n %d passed, %d failed\n%s"
      % ("-" * 60, _passes, len(_failures), "-" * 60))
sys.exit(1 if _failures else 0)
