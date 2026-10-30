#!/usr/bin/env python3
"""
Text tests for the Parent Branch Delivery Rule (issue 113).

Contract: .claude/concepts/2026-10-30-parent-branch-delivery-rule.md, "Extension Points -> Text, each change
asserted in test_parent_branch_rule_text.py", the Registry text paragraph and the plugin version raise.

WHAT IS PINNED DOWN
-------------------
The rule is carried by prose as well as by scripts: a contract whose handoff has two or more mergeable blocks
(an implementation block plus a review block counts) is always delivered through a parent branch, the version
is raised once at landing, a Jira or Azure DevOps item can only have a single block, and the owner alone runs
`--accept-single-branch`. Each place that states the rule has one or more checks here:

    template (header line, rule paragraph, the implementation-plus-review sentence)
    agents/data-architect.md, agents/contract-critic.md (a BLOCKER item)
    skills/design-first (the approval gate with layout_defects, the mandatory header, the `contract:` write,
        Step 4 routing for two or more blocks)
    skills/flow (Step 2.7, the "no parent branch" sentence)
    skills/advance (exit 7 with two refusals, needs-issue before the cut, R-9)
    skills/pr-merged/references (contract-completion.md: R-7 and R-9; undeliverable-sub-task.md: R-8)
    skills/task (Step 4 one-liner for trackers without a GitHub parent issue)
    skills/task/references/parent-aware-mode.md, CLAUDE.md, VOCABULARY.md, the five version entries

How the checks read: each file is read whole, its whitespace is squashed to single spaces (the skills wrap
lines), and the check is a phrase or a short regular expression built from identifiers the contract names
(`layout_defects`, `needs-issue`, `--accept-single-branch`, `single-branch-delivery`, ...). A file that is
missing fails the check with a message, never with an exception. Tests named positive_control pass today by
design: they pin text that must stay.

Run: py -3 -B .claude/scripts/tests/test_parent_branch_rule_text.py
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text)


class TextCase(unittest.TestCase):

    def read(self, rel: str) -> str:
        path = PLUGIN_ROOT / rel
        self.assertTrue(path.is_file(), "%s does not exist" % rel)
        return path.read_text(encoding="utf-8", errors="replace")

    def flat(self, rel: str) -> str:
        return squash(self.read(rel))

    def section(self, rel: str, start: str, end: str) -> str:
        """The text from the heading ``start`` up to the heading ``end`` (squashed). Fails when ``start`` is absent."""
        text = self.read(rel)
        i = text.find(start)
        self.assertGreaterEqual(i, 0, "%s has no heading %r" % (rel, start))
        j = text.find(end, i + len(start))
        return squash(text[i:j if j >= 0 else len(text)])

    # A whole file is the container in most checks: never dump it into a failure message.
    def assertIn(self, member, container, msg=None):
        if isinstance(container, str) and len(container) > 300:
            self.assertTrue(member in container, msg or "text does not contain %r" % (member,))
        else:
            super().assertIn(member, container, msg)

    def assertNotIn(self, member, container, msg=None):
        if isinstance(container, str) and len(container) > 300:
            self.assertFalse(member in container, msg or "text must not contain %r" % (member,))
        else:
            super().assertNotIn(member, container, msg)

    def assertMatches(self, pattern: str, text: str, message: str, flags: int = re.I) -> None:
        self.assertIsNotNone(re.search(pattern, text, flags), message)

    def paragraphs(self, rel: str) -> list[str]:
        return [squash(p) for p in re.split(r"\n\s*\n", self.read(rel)) if p.strip()]


# ---------------------------------------------------------------------------
# The template and the two agents
# ---------------------------------------------------------------------------
class TemplateTextTests(TextCase):
    REL = ".claude/templates/concept-contract.md"

    def test_the_header_line_is_no_longer_merely_optional(self):
        line = next((ln for ln in self.read(self.REL).splitlines() if ln.startswith("**Work Item Brief:**")), None)
        self.assertIsNotNone(line, "the template keeps its **Work Item Brief:** header line")
        self.assertMatches(r"two or more|mandatory|required", line,
                           "the header line must say it is required for a contract with two or more mergeable "
                           "blocks; it still reads: %s" % line[:200])

    def test_the_template_states_the_rule(self):
        flat = self.flat(self.REL)
        self.assertIn("Parent Branch Delivery Rule", flat, "the template names the rule")
        self.assertMatches(r"parent branch[^.]{0,200}(sub-task|mergeable)|(sub-task|mergeable)[^.]{0,200}parent branch",
                           flat, "and says a multi-sub-task contract is delivered through a parent branch")

    def test_the_implementation_plus_review_sentence(self):
        flat = self.flat(self.REL)
        self.assertMatches(
            r"implementation block[^.]{0,30}(plus|and|\+)[^.]{0,20}review block[^.]{0,120}"
            r"(multi-sub-task|two or more|parent branch)", flat,
            "the template says one implementation block plus one review block is a multi-sub-task contract")


class DataArchitectTextTests(TextCase):
    REL = "agents/data-architect.md"

    def test_the_architect_states_the_rule(self):
        self.assertIn("Parent Branch Delivery Rule", self.flat(self.REL))

    def test_the_architect_always_writes_the_work_item_brief_header(self):
        flat = self.flat(self.REL)
        self.assertMatches(r"Work Item Brief[^.]{0,200}(always|every contract|mandatory)|"
                           r"(always|mandatory)[^.]{0,200}Work Item Brief", flat,
                           "data-architect always writes the **Work Item Brief:** header (the gate needs it "
                           "for two or more mergeable blocks)")

    def test_a_tracker_without_a_github_parent_issue_gets_a_single_block_and_no_review_block(self):
        flat = self.flat(self.REL)
        self.assertMatches(r"(Jira|Azure DevOps|ADO)[^.]{0,300}(single block|one block|no review block)", flat,
                           "a Jira or Azure DevOps item can carry neither a second implementation block nor a "
                           "review block; its review runs through /flow's reviewer step")


class ContractCriticTextTests(TextCase):
    REL = "agents/contract-critic.md"

    def test_a_blocker_item_covers_the_rule(self):
        lines = [ln for ln in self.read(self.REL).splitlines()
                 if "BLOCKER" in ln and "Parent Branch Delivery Rule" in ln]
        self.assertTrue(lines, "contract-critic needs a checklist item that is a BLOCKER when a contract breaks "
                               "the Parent Branch Delivery Rule")
        self.assertMatches(r"sub-task[^.]{0,200}(raise|bump)[^.]{0,80}version|version[^.]{0,120}(each|per) sub-task|"
                           r"sub-task-raises-version|default branch", squash(" ".join(lines)),
                           "and the item names what breaks it (a version raise per sub-task, or a sub-task pull "
                           "request to the default branch)")


# ---------------------------------------------------------------------------
# /design-first
# ---------------------------------------------------------------------------
class DesignFirstTextTests(TextCase):
    REL = "skills/design-first/SKILL.md"

    def test_the_approval_gate_refuses_the_flip_on_any_layout_defect(self):
        step3 = self.section(self.REL, "## Step 3: Present the contract", "## Step 3.4")
        self.assertIn("layout_defects", step3, "the gate reads layout_defects from pr_merged.py --status --json")
        self.assertIn("--status", step3)
        self.assertMatches(r"layout_defects[^.]{0,500}(not|never|refus)[^.]{0,200}approved|"
                           r"(not|never|refus)[^.]{0,200}approved[^.]{0,500}layout_defects", step3,
                           "and Status is not flipped to approved while a layout defect stands")

    def test_the_gate_runs_the_status_through_the_standard_script_lookup_block(self):
        flat = self.flat(self.REL)
        self.assertIn("agentic-auto-improve/*/", flat,
                      "the gate carries the standard script lookup block (the plugin-cache search line), so "
                      "test_skill_script_lookup.py exercises it")
        self.assertMatches(r'py -3 "\$\{?PRM\}?" --contract [^\n]{0,80}--status', flat,
                           'and runs py -3 "$PRM" --contract <slug> --status --json')

    def test_the_header_is_mandatory_for_two_or_more_mergeable_blocks(self):
        flat = self.flat(self.REL)
        self.assertMatches(
            r"(two or more|more than one)[^.]{0,250}Work Item Brief[^.]{0,200}(mandatory|required|must|always)|"
            r"Work Item Brief[^.]{0,250}(mandatory|required|must)[^.]{0,250}(two or more|more than one)",
            flat, "the **Work Item Brief:** header is mandatory when the handoff has two or more mergeable blocks")

    def test_the_approval_step_writes_contract_into_the_linked_brief_when_it_is_unset(self):
        hit = [p for p in self.paragraphs(self.REL)
               if "contract:" in p and "unset" in p and "brief" in p.lower() and "approv" in p.lower()]
        self.assertTrue(hit, "one paragraph says the approval step writes `contract:` into the existing linked "
                             "brief when it is unset, and that this creates nothing")

    def test_step_4_hands_blocks_to_implementers_only_for_a_single_block_and_routes_the_rest_to_flow(self):
        step4 = self.section(self.REL, "## Step 4: Hand off to implementer agents", "## Step 5")
        self.assertIn("/flow", step4, "two or more blocks route to /flow (Step 2.7), never to one-session implementers")
        self.assertMatches(r"two or more|more than one", step4, "Step 4 says what happens for two or more blocks")
        self.assertMatches(r"(single|one|exactly one) (implementation |mergeable )?block", step4,
                           "and that the direct hand-off is for a single block only")

    def test_positive_control_step_3_6_stays_after_the_approval_step(self):
        text = self.read(self.REL)
        self.assertLess(text.index("## Step 3:"), text.index("## Step 3.6"),
                        "Step 3.6 was not moved before approval (it writes a brief and opens an issue)")


# ---------------------------------------------------------------------------
# /flow
# ---------------------------------------------------------------------------
class FlowTextTests(TextCase):
    REL = "skills/flow/SKILL.md"

    def test_step_2_7_states_the_rule_and_is_the_remedy_of_needs_issue(self):
        step = self.section(self.REL, "## Step 2.7: Open the sub-tasks", "\n## Step 3")
        self.assertIn("Parent Branch Delivery Rule", step, "Step 2.7 names the rule")
        self.assertIn("needs-issue", step, "dispatch refuses needs-issue with remedy /flow Step 2.7: say so here")
        self.assertMatches(r"two or more[^.]{0,300}(parent (issue|branch)|sub-issue)", step,
                           "two or more mergeable blocks always get a parent issue, sub-issues and a landing")

    def test_a_contract_with_no_parent_branch_is_only_a_single_block_contract(self):
        flat = self.flat(self.REL)
        for sentence in re.split(r"(?<=[.!?])\s+", flat):
            if re.search(r"no parent branch", sentence, re.I):
                self.assertMatches(r"single|one mergeable|one implementation|exactly one", sentence,
                                   "a sentence about a contract with no parent branch must say it is a "
                                   "single-block contract: %s" % sentence[:200])


# ---------------------------------------------------------------------------
# /advance
# ---------------------------------------------------------------------------
class AdvanceTextTests(TextCase):
    REL = "skills/advance/SKILL.md"

    def test_exit_code_7_carries_two_refusals_told_apart_by_error(self):
        flat = self.flat(self.REL)
        self.assertMatches(r"(exit code 7|exit 7)[^.]{0,400}needs-issue|needs-issue[^.]{0,400}(exit code 7|exit 7)", flat,
                           "exit 7 now carries needs-issue as well as base-not-declared")
        self.assertIn("base-not-declared", flat)
        self.assertMatches(r"needs-issue[^.]{0,500}--dry-run|--dry-run[^.]{0,500}needs-issue", flat,
                           "both refusals hold under --dry-run, so a preview matches the real run")

    def test_needs_issue_is_a_refusal_before_the_branch_is_cut(self):
        flat = self.flat(self.REL)
        self.assertNotIn("has already cut the branch", flat,
                         "the old paragraph (the branch is cut before needs_issue is read) is rewritten: "
                         "needs_issue is computed before the cut")
        self.assertMatches(r"needs-issue[^.]{0,300}(before|no branch|nothing is cut|cuts no branch)", flat,
                           "needs-issue cuts nothing")

    def test_layout_defects_block_dispatch(self):
        flat = self.flat(self.REL)
        self.assertIn("layout_defects", flat, "/advance reads layout_defects from the status report")
        self.assertMatches(r"contract-defect[^.]{0,300}layout|layout[^.]{0,300}contract-defect", flat,
                           "a layout defect makes the move contract-defect in place of dispatch")

    def test_the_accept_command_is_shown_to_the_owner_and_never_run(self):
        paras = [p for p in self.paragraphs(self.REL) if "--accept-single-branch" in p]
        self.assertTrue(paras, "/advance names --accept-single-branch (R-9)")
        self.assertMatches(r"never run|does not run|do not run|shows? it to the owner|show it to the owner|owner runs",
                           " ".join(paras), "and says the skill shows it to the owner and never runs it itself")


# ---------------------------------------------------------------------------
# /pr-merged references
# ---------------------------------------------------------------------------
class PrMergedReferenceTextTests(TextCase):

    def test_contract_completion_states_guard_g7_and_the_two_remedies(self):
        flat = self.flat("skills/pr-merged/references/contract-completion.md")
        self.assertIn("G-7", flat, "the guard list gains G-7")
        self.assertIn("single-branch-delivery", flat)
        self.assertIn("--accept-single-branch", flat, "the remedy for work already merged on the default branch")
        self.assertMatches(r"/flow[^.]{0,200}/advance|Step 2\.7", flat,
                           "and the remedy for work not yet merged: /flow (Step 2.7), then /advance")

    def test_contract_completion_makes_the_accept_flag_human_only(self):
        paras = [p for p in self.paragraphs("skills/pr-merged/references/contract-completion.md")
                 if "--accept-single-branch" in p]
        self.assertTrue(paras, "the reference documents --accept-single-branch")
        self.assertMatches(r"owner|human|person", " ".join(paras), "who runs it: the owner")
        self.assertMatches(r"never (runs?|run) it|does not run it|never runs", " ".join(paras),
                           "the skill never runs it itself")

    def test_contract_completion_documents_the_delivery_record_marker(self):
        self.assertIn("single-branch-accepted", self.flat("skills/pr-merged/references/contract-completion.md"),
                      "the delivery record marks an accepted single-branch delivery: layout: single-branch-accepted")

    def test_undeliverable_sub_task_documents_the_web_merge_into_the_default_branch(self):
        flat = self.flat("skills/pr-merged/references/undeliverable-sub-task.md")
        self.assertIn("single-branch-delivery", flat, "R-8: a sub-task pull request merged into the default branch")
        self.assertMatches(r"failure:?\s*`?single-branch-delivery", flat, "is recorded as a failed record with that failure")
        self.assertIn("escalate", flat, "and the existing escalate move names it")


# ---------------------------------------------------------------------------
# /task and the parent-aware reference
# ---------------------------------------------------------------------------
class TaskTextTests(TextCase):

    def test_step_4_tells_a_jira_or_ado_item_its_contract_must_be_a_single_block(self):
        step4 = self.section("skills/task/SKILL.md", "## Step 4: Size and route", "\n## Step 5")
        self.assertIn("This item has no GitHub issue, so its contract must be a single block.", step4,
                      "row 4: the one-line refusal at intake")

    def test_parent_aware_mode_says_a_multi_sub_task_contracts_base_is_never_the_default_branch(self):
        flat = self.flat("skills/task/references/parent-aware-mode.md")
        self.assertIn("Parent Branch Delivery Rule", flat, "the reference names the rule")
        self.assertMatches(r"never the (repository )?default branch", flat,
                           "a sub-task's base: of a multi-sub-task contract is the parent branch, never the default branch")


# ---------------------------------------------------------------------------
# CLAUDE.md, the vocabulary registry and the version raise
# ---------------------------------------------------------------------------
class ProjectRulesTextTests(TextCase):

    def test_claude_md_says_the_version_is_raised_once_at_landing_and_always_by_a_minor(self):
        flat = self.flat("CLAUDE.md")
        self.assertMatches(r"landing[^.]{0,250}(always|only)[^.]{0,60}minor|minor[^.]{0,150}landing", flat,
                           "R-1: a landing raise is always minor")
        self.assertMatches(r"sub-task pull request[^.]{0,200}(never|not|does not)[^.]{0,60}rais", flat,
                           "a sub-task pull request into a parent branch does not raise the version")

    def test_claude_md_or_advance_documents_the_manual_landing_commands(self):
        both = self.flat("CLAUDE.md") + " " + self.flat("skills/advance/SKILL.md")
        self.assertIn("--raise", both, "R-4: under landing: manual the operator runs --raise")
        self.assertIn("--exact", both, "and --exact; CI enforces only 'raised'")


class VocabularyTextTests(TextCase):
    REL = ".claude/registries/VOCABULARY.md"

    def test_contract_delivery_is_amended(self):
        line = next((ln for ln in self.read(self.REL).splitlines() if ln.startswith("- **Contract Delivery**")), None)
        self.assertIsNotNone(line, "fixture sanity: the Contract Delivery entry exists")
        flat = squash(line)
        self.assertIn("single-branch-accepted", flat, "the amendment names the delivery record marker")
        self.assertMatches(r"two or more[^.]{0,100}blocks[^.]{0,200}parent branch", flat,
                           "for a contract with two or more mergeable blocks only the parent branch's landing "
                           "pull request, or an owner-accepted single-branch delivery, is a Contract Delivery")

    def test_the_four_new_terms_are_defined(self):
        text = self.read(self.REL)
        for term in ("Parent Branch Delivery Rule", "Layout defect", "Landing version raise",
                     "Accepted single-branch delivery"):
            with self.subTest(term=term):
                self.assertTrue(re.search(r"^- \*\*%s\*\*" % re.escape(term), text, re.M),
                                "VOCABULARY.md needs an entry for %r" % term)


class PluginVersionTextTests(TextCase):

    def versions(self):
        found = []
        for rel in ("plugin.json", ".claude-plugin/plugin.json", ".cursor-plugin/plugin.json",
                    ".claude-plugin/marketplace.json"):
            data = json.loads(self.read(rel))
            if "version" in data:
                found.append(data["version"])
            found.extend(entry["version"] for entry in data.get("plugins", []) if "version" in entry)
        return found

    def test_the_five_entries_agree_and_carry_the_minor_raise(self):
        found = self.versions()
        self.assertEqual(len(found), 5, "fixture sanity: five version entries, got %r" % found)
        self.assertEqual(len(set(found)), 1, "the five entries agree: %r" % found)
        parts = tuple(int(p) for p in found[0].split("."))
        self.assertGreaterEqual(parts[:2], (0, 11), "this pull request raises the version by a minor (was 0.10.0): "
                                                    "found %s" % found[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
