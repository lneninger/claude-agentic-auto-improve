#!/usr/bin/env python3
"""
Plugin-side text scans over the plugin's own agents/ and skills/.

Contract: .claude/concepts/2026-10-12-dedupe-claude-config.md in the consuming repository, Files to touch
and TASK block of sub-task 2. Once agents and skills leave the consuming repository (Claude Code loads them
from the installed plugin alone) the repository's own suites can no longer read them. Three checks that
used to read the repository's copies move here, where the one copy lives:

  (1) No line tells Claude to run an EF database-removal form. This is the generic check of the repository's
      test_hook_gating.py (W1) applied to the plugin's agents/ and skills/. The wording must hand the command
      to a person ("by hand"). Claude Code refuses these forms, so an instruction to run one only wastes a turn.
  (2) agents/data-architect.md and agents/contract-critic.md each have exactly ONE line naming both
      templates/concept-contract.md and "budget". It was the repository's test_contract_budget.py:92-97
      (test_agent_pointers). The contract-size rule lives in the template; each agent points at it once.
  (3) Every subagent_type literal that names a plugin agent follows the dispatch rule: a plugin agent is
      dispatched as `agentic-auto-improve:<name>`, unless the project carries `.claude/agents/<name>.md`
      (in which case the line says so). A bare name in a literal addresses nothing once the project's copy
      is gone. The literal is read in the plain form (`subagent_type: x`) and the JSON-quoted form
      (`"subagent_type": "x"`). A line that carries a bare name is exempt only when the namespaced form of
      the same agent is also on it; naming `.claude/agents/<name>.md` alone does not exempt it.

Every scan asserts that it read at least one file, and every scan has a POSITIVE CONTROL that proves it can
fail. Phrases that look destructive are built from parts; this file never holds one literally.

PASSES TODAY BY DESIGN (regression guards, once the reconciliation merge has put both agents in the plugin):
scans (1) and (2) and all positive controls. Scan (3) is RED today: skills/critique-now/SKILL.md names
`contract-critic` bare in its subagent_type literal.

Run: py -3 .claude/scripts/tests/test_plugin_text_scans.py
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
AGENTS = PLUGIN_ROOT / "agents"
SKILLS = PLUGIN_ROOT / "skills"
NAMESPACE = "agentic-auto-improve"

# --- parts, so this file never holds a destructive phrase -------------------------------------------------
_d = "dr" + "op"
_u = "up" + "date"
_EF = "dotnet " + "ef"
EF_BASES = (_EF + " database ", "dotnet-ef database ", "dotnet tool run dotnet-ef database ")
_EF_INVOKE_RE = re.compile(r"(?:dotnet\s+tool\s+run\s+dotnet-ef|dotnet-ef|dotnet\s+ef)\b(.*)", re.I)
_EF_FORM_RE = re.compile(r"database\s+" + _d, re.I)


def ef_drop(base: str = EF_BASES[0]) -> str:
    return base + _d


def ef_instructions(text: str) -> list[str]:
    """Lines that tell a reader to run an EF database-removal form, in any spelling.

    A line counts when it holds an EF invocation whose remainder names the removal verb, or an elided form
    carrying `--connection` or `--force`. A line that hands the command to a person ("by hand") is the
    sanctioned wording and is not counted.
    """
    hits = []
    for line in text.splitlines():
        m = _EF_INVOKE_RE.search(line)
        if not m:
            continue
        rest = m.group(1)
        if _EF_FORM_RE.search(rest) or "--connection" in rest or "--force" in rest:
            if "by hand" not in line.lower():
                hits.append(line.strip())
    return hits


def pointer_lines(text: str) -> list[str]:
    """Lines naming both the template path and the word 'budget' (case-insensitive)."""
    return [l for l in text.split("\n") if "templates/concept-contract.md" in l and "budget" in l.lower()]


#: `subagent_type: x`, `subagent_type="x"`, and the JSON-quoted `"subagent_type": "x"` (the key is quoted too).
_SUBAGENT_RE = re.compile(r"""subagent_type["'`]?\s*[:=]\s*["'`]?([A-Za-z0-9_][A-Za-z0-9_.:\-]*)""")


def dispatch_violations(text: str, plugin_agents: set[str]) -> list[str]:
    """Lines whose subagent_type literal names a plugin agent by its bare name.

    A line is exempt only when the namespaced form `agentic-auto-improve:<name>` of that SAME agent is also
    present on it: the line then names the default dispatch and the bare name is the stated alternative.
    Merely mentioning `.claude/agents/` does not exempt a line.
    """
    bad = []
    for line in text.splitlines():
        for m in _SUBAGENT_RE.finditer(line):
            value = m.group(1)
            if value in plugin_agents and (NAMESPACE + ":" + value) not in line:
                bad.append(line.strip())
    return bad


def read_all(folder: Path, pattern: str = "*.md") -> list[tuple[Path, str]]:
    return [(p, p.read_text(encoding="utf-8", errors="replace")) for p in sorted(folder.rglob(pattern)) if p.is_file()]


def plugin_agent_names() -> set[str]:
    return {p.stem for p in AGENTS.glob("*.md")}


class TestEfRemovalFormIsNeverAnInstruction(unittest.TestCase):
    def test_matcher_control_catches_every_spelling_and_spares_other_verbs(self):
        for base in EF_BASES:
            self.assertTrue(ef_instructions("Run `%s --force` now" % ef_drop(base)),
                            "control: spelling %r must be reported" % base)
        self.assertTrue(ef_instructions('  %s ... --connection "<x>" --force' % _EF),
                        "control: the elided form must be reported")
        self.assertFalse(ef_instructions("run `%s database %s --project p`" % (_EF, _u)),
                         "control: the other database verb is not a removal")
        self.assertFalse(ef_instructions("the EF form is run by hand: " + ef_drop()),
                         "control: wording that hands the command to a person is sanctioned")

    def test_no_agent_or_skill_tells_claude_to_run_the_form(self):
        files = read_all(AGENTS) + read_all(SKILLS)
        self.assertGreater(len(files), 0, "the scan must have read at least one agent or skill file")
        offenders = []
        for path, text in files:
            for line in ef_instructions(text):
                offenders.append("%s: %s" % (path.relative_to(PLUGIN_ROOT).as_posix(), line))
        self.assertEqual(offenders, [],
                         "Claude Code refuses every EF database-removal form, so no agent or skill may tell Claude "
                         "to run one; the wording must say the form is run by hand")


class TestAgentsPointAtTheBudgetRuleOnce(unittest.TestCase):
    def test_matcher_control_counts_zero_one_and_two(self):
        self.assertEqual(len(pointer_lines("no pointer here")), 0)
        self.assertEqual(len(pointer_lines("See templates/concept-contract.md for the Budget rule")), 1)
        self.assertEqual(len(pointer_lines(
            "templates/concept-contract.md budget\nagain templates/concept-contract.md BUDGET")), 2)
        self.assertEqual(len(pointer_lines("templates/concept-contract.md only")), 0,
                         "control: the template path alone is not a pointer to the budget rule")

    def test_data_architect_and_contract_critic_each_have_exactly_one_pointer_line(self):
        read = 0
        for agent in ("data-architect", "contract-critic"):
            path = AGENTS / (agent + ".md")
            self.assertTrue(path.is_file(), "agents/%s.md must exist in the plugin" % agent)
            text = path.read_text(encoding="utf-8", errors="replace")
            read += 1
            hits = pointer_lines(text)
            self.assertEqual(len(hits), 1,
                             "%s: exactly one line must name both templates/concept-contract.md and 'budget'; "
                             "found %d" % (agent, len(hits)))
        self.assertEqual(read, 2, "the scan must have read both agent files")


class TestSubagentTypeLiteralsFollowTheDispatchRule(unittest.TestCase):
    AGENTS_SET = {"contract-critic", "data-architect"}

    def test_matcher_control(self):
        self.assertTrue(dispatch_violations("(`subagent_type: contract-critic`)", self.AGENTS_SET),
                        "control: a bare plugin agent name in a literal is a violation")
        self.assertTrue(dispatch_violations('subagent_type="data-architect"', self.AGENTS_SET),
                        "control: the quoted form is read too")
        self.assertFalse(dispatch_violations("subagent_type: %s:contract-critic" % NAMESPACE, self.AGENTS_SET),
                         "control: the namespaced name follows the rule")
        self.assertFalse(dispatch_violations("subagent_type: <reviewer-name>", self.AGENTS_SET),
                         "control: a placeholder names no agent")
        self.assertFalse(dispatch_violations("subagent_type: ibkr-api-architect", self.AGENTS_SET),
                         "control: an agent the plugin does not ship is not the plugin's to namespace")

    def test_matcher_control_json_quoted_form(self):
        self.assertTrue(dispatch_violations('{"subagent_type": "contract-critic", "prompt": "x"}', self.AGENTS_SET),
                        "control: the JSON-quoted form with a bare plugin agent name is a violation")
        self.assertTrue(dispatch_violations("\"subagent_type\": 'data-architect'", self.AGENTS_SET),
                        "control: the quoted key with a single-quoted value is read too")
        self.assertFalse(dispatch_violations('{"subagent_type": "%s:contract-critic"}' % NAMESPACE, self.AGENTS_SET),
                         "control: the JSON-quoted namespaced form follows the rule")

    def test_matcher_control_exemption_needs_the_namespaced_form_of_the_same_agent_on_the_line(self):
        both = ("subagent_type: %s:contract-critic (or `subagent_type: contract-critic` when the project carries "
                ".claude/agents/contract-critic.md)" % NAMESPACE)
        self.assertFalse(dispatch_violations(both, self.AGENTS_SET),
                         "control: the namespaced form beside the stated bare alternative follows the rule")
        self.assertTrue(dispatch_violations(
            "subagent_type: contract-critic (the project's .claude/agents/contract-critic.md when it has one)",
            self.AGENTS_SET), "control: naming the project path alone does not exempt a bare literal")
        self.assertTrue(dispatch_violations(
            "subagent_type: contract-critic, not %s:data-architect" % NAMESPACE, self.AGENTS_SET),
            "control: the namespaced form of ANOTHER agent does not exempt this one")

    def test_every_literal_naming_a_plugin_agent_is_namespaced_or_states_the_project_exception(self):
        agents = plugin_agent_names()
        self.assertGreater(len(agents), 0, "the plugin ships agents/*.md")
        files = read_all(SKILLS) + read_all(AGENTS)
        self.assertGreater(len(files), 0, "the scan must have read at least one file")
        offenders = []
        for path, text in files:
            for line in dispatch_violations(text, agents):
                offenders.append("%s: %s" % (path.relative_to(PLUGIN_ROOT).as_posix(), line))
        self.assertEqual(offenders, [],
                         "a plugin agent is dispatched as '%s:<name>' unless the project carries "
                         ".claude/agents/<name>.md; a bare name addresses nothing once the project's copy is gone"
                         % NAMESPACE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
