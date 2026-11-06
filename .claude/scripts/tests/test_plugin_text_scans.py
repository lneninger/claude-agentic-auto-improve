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


TEMPLATES = PLUGIN_ROOT / ".claude" / "templates"
REGISTRY_NAMES = ("MECHANISMS", "VOCABULARY", "JOURNAL")

#: Contract .claude/concepts/2026-11-04-domain-split-registries.md, sub-task 7 (issue 247). The three sentences
#: every registry writer states, in these words.
FALLBACK_SENTENCE = ("on a project not yet on registry layout 2 it appends to a domain file and prints an "
                     "advisory line; that is success")
EXIT2_SENTENCE = "Exit 2: fix the entry file and re-run."
EXIT3_SENTENCE = "Exit 3: stop and show the message to the user."
RECEIVER_SECTION = "Run the data-architect's registry appends"
#: The §2.2-B writers: every one appends through registry_append.py.
WRITERS = ("agents/fullstack-code-reviewer.md", "agents/data-architect.md", "skills/journal-add/SKILL.md",
           "skills/design-first/SKILL.md")
#: Readers that name the general.md files of the three registries.
GENERAL_READERS = ("agents/data-architect.md", "agents/contract-critic.md")
#: Readers that search the journal and must reach the domain files too.
JOURNAL_SEARCHERS = ("agents/ui-ux-designer.md", "skills/application-design/SKILL.md",
                     "skills/website-design/SKILL.md", "skills/promote-ui-rule/SKILL.md")

_PROJECT_SECTION_RE = re.compile(r"project\s+sections?\b|under\s+<project>", re.I)
_EDIT_RE = re.compile(r"`Edit`|\bdirect Edit\b|\bby Edit\b|\bvia Edit\b")


def squash(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def flat_registry_lines(text: str) -> list[str]:
    """Lines naming a flat registry path (`registries/<NAME>.md`) without the domain form (`<NAME>/`).

    The registry seeds under templates/registries/ are the registries themselves and are not references.
    """
    hits = []
    for line in text.splitlines():
        for name in REGISTRY_NAMES:
            m = re.search(r"(?<!templates/)registries/%s\.md" % name, line)
            if m and (name + "/") not in line:
                hits.append(line.strip())
                break
    return hits


def project_section_lines(text: str) -> list[str]:
    return [l.strip() for l in text.splitlines() if _PROJECT_SECTION_RE.search(l)]


def edit_append_lines(text: str) -> list[str]:
    """Lines that tell a reader to write a registry by the Edit tool: a registry named, and `Edit` used as the way."""
    hits = []
    for line in text.splitlines():
        names = any(("registries/%s" % n) in line or ("%s.md" % n) in line for n in REGISTRY_NAMES)
        if names and _EDIT_RE.search(line):
            hits.append(line.strip())
    return hits


def shipped_instruction_files() -> list[tuple[Path, str]]:
    files = read_all(AGENTS) + read_all(SKILLS) + [
        (p, p.read_text(encoding="utf-8", errors="replace")) for p in sorted(TEMPLATES.glob("*.md"))]
    return files


def read_rel(rel: str) -> str:
    path = PLUGIN_ROOT / rel
    assert path.is_file(), "%s must exist in the plugin" % rel
    return path.read_text(encoding="utf-8", errors="replace")


class TestRegistryLayout2Instructions(unittest.TestCase):
    """Sub-task 7 of the domain-split registries contract: every writer goes through registry_append.py, every
    reader reaches the domain files, and no shipped text names a flat registry path alone."""

    def test_matcher_controls(self):
        self.assertTrue(flat_registry_lines("read `.claude/registries/JOURNAL.md` first"),
                        "control: a flat path alone is reported")
        self.assertFalse(flat_registry_lines("read `.claude/registries/JOURNAL.md` and `JOURNAL/*.md`"),
                         "control: the domain form beside it is accepted")
        self.assertFalse(flat_registry_lines("copy `.claude/templates/registries/JOURNAL.md`"),
                         "control: a seed under templates/registries/ is not a registry reference")
        self.assertTrue(project_section_lines("under the matching project section"), "control: project section")
        self.assertTrue(project_section_lines("Add it under <project>."), "control: under <project>")
        self.assertFalse(project_section_lines("the project profile names the roots"), "control: other prose")
        self.assertTrue(edit_append_lines("append the entry to JOURNAL.md using `Edit`"), "control: Edit append")
        self.assertTrue(edit_append_lines("update `.claude/registries/MECHANISMS.md` (a direct Edit)"),
                        "control: direct Edit")
        self.assertFalse(edit_append_lines("Edit MECHANISMS.md is not yours to do"),
                         "control: the plain verb in a prohibition is not an instruction")
        self.assertFalse(edit_append_lines("run registry_append.py to append to JOURNAL.md"),
                         "control: the script is the sanctioned way")

    def test_writers_append_through_registry_append_py(self):
        for rel in WRITERS:
            text = squash(read_rel(rel))
            with self.subTest(file=rel):
                self.assertIn("registry_append.py", text, "%s must name registry_append.py" % rel)
                self.assertIn('--project "$CLAUDE_PROJECT_DIR"', text,
                              "%s must pass --project \"$CLAUDE_PROJECT_DIR\"" % rel)
                self.assertIn(FALLBACK_SENTENCE, text, "%s must state the layout-2 fallback sentence" % rel)
                self.assertIn(EXIT2_SENTENCE, text, "%s must state the exit 2 rule" % rel)
                self.assertIn(EXIT3_SENTENCE, text, "%s must state the exit 3 rule" % rel)

    def test_data_architect_and_contract_critic_name_the_general_files_and_drop_the_fixed_domain_list(self):
        for rel in GENERAL_READERS:
            text = read_rel(rel)
            with self.subTest(file=rel):
                for name in REGISTRY_NAMES:
                    self.assertIn("%s/general.md" % name, text, "%s must name %s/general.md" % (rel, name))
                self.assertNotIn("{backend,frontend,data,trading}", text,
                                 "%s must not fix the domain list: the set is the files on disk" % rel)

    def test_data_architect_names_the_receiver_section_and_design_first_contains_it(self):
        self.assertIn(RECEIVER_SECTION, read_rel("agents/data-architect.md"))
        self.assertIn("Registry appends:", read_rel("agents/data-architect.md"))
        design_first = read_rel("skills/design-first/SKILL.md")
        self.assertRegex(design_first, r"(?m)^#{2,4} .*" + re.escape(RECEIVER_SECTION),
                         "design-first must carry the receiver as a section heading")
        self.assertIn("Registry appends:", design_first)

    def test_journal_searchers_reach_the_domain_files(self):
        for rel in JOURNAL_SEARCHERS:
            with self.subTest(file=rel):
                self.assertIn("JOURNAL/", read_rel(rel), "%s must search JOURNAL/*.md as well as JOURNAL.md" % rel)

    def test_verify_before_done_runs_the_structure_lint_and_validate_registries_describes_it(self):
        text = squash(read_rel("skills/verify-before-done/SKILL.md"))
        self.assertIn("validate_registries.py", text)
        self.assertIn("--check-structure", text)
        self.assertIn("NOT-READY", text)
        text = read_rel("skills/validate-registries/SKILL.md")
        for needle in ("--check-structure", "--strict", "R4", "registry_append.py", "--correction-of"):
            self.assertIn(needle, text, "validate-registries must describe %s" % needle)

    def test_registry_scout_describes_the_full_index(self):
        text = squash(read_rel("agents/registry-scout.md"))
        self.assertIn("legacy", text.lower())
        self.assertIn("R1", text)
        self.assertIn("R2", text)

    def test_no_shipped_text_names_a_flat_registry_path_alone(self):
        files = shipped_instruction_files()
        self.assertGreater(len(files), 0, "the scan must have read at least one file")
        offenders = ["%s: %s" % (p.relative_to(PLUGIN_ROOT).as_posix(), l)
                     for p, t in files for l in flat_registry_lines(t)]
        self.assertEqual(offenders, [], "name the root file together with its domain form (<NAME>/...)")

    def test_no_shipped_text_says_project_section(self):
        offenders = ["%s: %s" % (p.relative_to(PLUGIN_ROOT).as_posix(), l)
                     for p, t in shipped_instruction_files() for l in project_section_lines(t)]
        self.assertEqual(offenders, [], "layout 2 has Universal root files and domain files, no project section")

    def test_no_shipped_text_appends_to_a_registry_by_edit(self):
        offenders = ["%s: %s" % (p.relative_to(PLUGIN_ROOT).as_posix(), l)
                     for p, t in shipped_instruction_files() for l in edit_append_lines(t)]
        self.assertEqual(offenders, [], "registry entries are written by registry_append.py, never by Edit")


if __name__ == "__main__":
    unittest.main(verbosity=2)
