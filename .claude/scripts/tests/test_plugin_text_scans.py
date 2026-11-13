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

import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(PLUGIN_ROOT / ".claude" / "scripts"))
import check_version_bump  # noqa: E402
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


# --- (4) only the memory adapter names the memory tools ---------------------------------------------------------
# Contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md, Extension Points. The file set is
# built by walking the named shipped folders from this checkout's own root (never the current directory, never a
# walk from the repo root), dropping every path with a `.claude/worktrees/` segment, then keeping what
# check_version_bump.is_shipped() calls shipped. The registries, .claude/hooks/tests/ and .claude/agent-memory/ are
# shipped and get no exemption.
SHIPPED_FOLDERS = ("agents", "skills", ".claude/hooks", ".claude/scripts", ".claude/templates", ".claude/references",
                   ".claude/registries", ".claude/agreements", ".claude/addons", ".claude/agent-memory")
ROOT_MANIFESTS = ("plugin.json", ".claude-plugin/plugin.json", ".cursor-plugin/plugin.json",
                  ".claude-plugin/marketplace.json")
MEMORY_TOOL_NAMES = ("memory_" + "retrieve", "memory_" + "capture")
MEMORY_ADAPTER = ".claude/scripts/memory_boundary.py"


def shipped_files(root: Path) -> list[str]:
    """Root-relative posix paths of the shipped files under the named folders of ``root``."""
    found = []
    for folder in SHIPPED_FOLDERS:
        for dirpath, dirnames, filenames in os.walk(root / folder):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                found.append((Path(dirpath) / name).relative_to(root).as_posix())
    found += [m for m in ROOT_MANIFESTS if (root / m).is_file()]
    return sorted(rel for rel in set(found)
                  if "/.claude/worktrees/" not in "/" + rel and check_version_bump.is_shipped(rel))


def memory_name_files(root: Path) -> list[str]:
    """Shipped files under ``root`` that contain either memory tool name."""
    hits = []
    for rel in shipped_files(root):
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(name in text for name in MEMORY_TOOL_NAMES):
            hits.append(rel)
    return hits


class TestOnlyTheMemoryAdapterNamesTheMemoryTools(unittest.TestCase):
    def plant(self, root: Path, rel: str) -> None:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("call " + MEMORY_TOOL_NAMES[0] + " here\n", encoding="utf-8")

    def test_control_a_planted_made_up_shipped_path_is_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.plant(root, "skills/zz-made-up/SKILL.md")
            self.plant(root, ".claude/registries/ZZ.md")
            self.assertEqual(memory_name_files(root), [".claude/registries/ZZ.md", "skills/zz-made-up/SKILL.md"])

    def test_control_a_copy_under_a_worktrees_segment_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.plant(root, "skills/zz-copy/.claude/worktrees/x/SKILL.md")
            self.plant(root, ".claude/scripts/.claude/worktrees/x/copy.py")
            self.assertEqual(memory_name_files(root), [])

    def test_control_unshipped_and_cached_files_are_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.plant(root, ".claude/scripts/tests/test_x.py")
            self.plant(root, ".claude/scripts/__pycache__/x.pyc")
            self.plant(root, "README.md")
            self.plant(root, "docs/notes.md")
            self.assertEqual(memory_name_files(root), [])

    def test_the_walk_starts_from_this_checkout_not_the_current_directory(self):
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                files = shipped_files(PLUGIN_ROOT)
            finally:
                os.chdir(cwd)
        self.assertGreater(len(files), 0)
        self.assertIn(MEMORY_ADAPTER, files)

    def test_only_the_adapter_contains_the_tool_names(self):
        self.assertIn(MEMORY_ADAPTER, shipped_files(PLUGIN_ROOT), "the scan must reach the adapter")
        self.assertEqual(memory_name_files(PLUGIN_ROOT), [MEMORY_ADAPTER],
                         "only %s may name the memory tools; every other shipped file says 'the configured "
                         "retrieve tool' and 'the configured capture tool'" % MEMORY_ADAPTER)


# --- (5) only the wildcard names CodeGraph tools -------------------------------------------------------------------
# Issue #259 (concept contract 2026-11-05-codegraph-guard-fail-open, "Scan"). The CodeGraph server now offers only the
# explore tool, so a shipped file that names an individual tool names something that may not exist, and every such
# name is a second place to keep in step. The rule: no shipped file contains the prefixed form
# `mcp__codegraph__codegraph_<x>` and none contains a bare legacy name (`codegraph_search` and the rest); a file says
# `mcp__codegraph__*` or "a CodeGraph tool". The file set is the one scan (4) uses (shipped_files). The only
# exemption is the two test files that PROVE the wildcard covers the legacy names. README is not shipped
# (check_version_bump.EXEMPT_NAMES), so it is edited but not scanned. The names are built from parts here, so this
# file (not shipped: .claude/scripts/tests) never needs to be an exception.
CG_PREFIX = "mcp__codegraph__" + "codegraph_"
CG_LEGACY_RE = re.compile(r"\bcodegraph_(?:search|node|callers|callees|impact|files|status|context)\b")
CG_WILDCARD = "mcp__codegraph__*"
CG_EXEMPT = (".claude/hooks/tests/test_addons.py", ".claude/hooks/tests/test_codegraph_first_guard.py")
# Issue #261 (concept contract 2026-11-05-codegraph-hooks-redesign). The shadow decision reads the real session
# transcript, and a recorded transcript names the tools exactly as the host wrote them, so the captured fixtures cannot
# be reworded without ceasing to be recordings. The shadow test replays them. Two narrow additions: the one fixtures
# folder (a trailing slash makes it a folder prefix, never a file-name prefix) and the one replaying test file.
CG_EXEMPT_RECORDED = (".claude/hooks/tests/test_codegraph_shadow.py",)
CG_EXEMPT_RECORDED_DIRS = (".claude/hooks/tests/fixtures/codegraph-transcripts/",)


def codegraph_exempt(rel: str) -> bool:
    """True for a proof file, the shadow replay test, or a file inside the recorded-transcript fixtures folder."""
    return rel in CG_EXEMPT or rel in CG_EXEMPT_RECORDED or rel.startswith(CG_EXEMPT_RECORDED_DIRS)


def codegraph_name_files(root: Path) -> list[str]:
    """Shipped files under ``root`` (the exempt files excepted) that name an individual CodeGraph tool."""
    hits = []
    for rel in shipped_files(root):
        if codegraph_exempt(rel):
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if CG_PREFIX in text or CG_LEGACY_RE.search(text):
            hits.append(rel)
    return hits


def tools_line(text: str) -> str | None:
    """The `tools:` line of an agent's front matter, or None."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        if line.startswith("tools:"):
            return line
    return None


def codegraph_grant_problems(root: Path) -> tuple[int, list[str]]:
    """(agents read, problems): every agent whose tools: line grants any CodeGraph tool must grant exactly the wildcard."""
    problems, read = [], 0
    for path in sorted((root / "agents").glob("*.md")):
        read += 1
        line = tools_line(path.read_text(encoding="utf-8", errors="replace"))
        if line is None:
            continue
        tokens = [tok.strip() for tok in line[len("tools:"):].split(",") if tok.strip()]
        granted = [tok for tok in tokens if "codegraph" in tok.lower()]
        if granted and granted != [CG_WILDCARD]:
            problems.append("agents/%s grants %r; the only CodeGraph grant is exactly %s" % (path.name, granted, CG_WILDCARD))
    return read, problems


class TestOnlyTheWildcardNamesCodeGraphTools(unittest.TestCase):
    def plant(self, root: Path, rel: str, text: str) -> None:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def test_control_a_prefixed_name_and_a_bare_legacy_name_are_caught_in_a_hook_test_a_registry_and_an_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.plant(root, ".claude/hooks/tests/test_other.py", "x = '" + CG_PREFIX + "search'\n")
            self.plant(root, ".claude/registries/ZZ.md", "ask codegraph_" + "callers first\n")
            self.plant(root, "agents/zz.md", "---\ntools: Read\n---\nuse codegraph_" + "explore? no: codegraph_" + "node\n")
            self.assertEqual(codegraph_name_files(root),
                             [".claude/hooks/tests/test_other.py", ".claude/registries/ZZ.md", "agents/zz.md"])

    def test_control_the_two_proof_files_are_exempt_and_the_wildcard_and_python_names_are_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in CG_EXEMPT:
                self.plant(root, rel, CG_PREFIX + "search and codegraph_" + "node\n")
            self.plant(root, ".claude/registries/OK.md", "say " + CG_WILDCARD + " or 'a CodeGraph tool'\n")
            self.plant(root, ".claude/scripts/ok.py", "def codegraph_impact_files(): pass\ncodegraph_signal = 1\n")
            self.assertEqual(codegraph_name_files(root), [])

    def test_control_the_recorded_transcript_exemption_is_narrow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            named = CG_PREFIX + "search and codegraph_" + "node\n"
            fixtures = ".claude/hooks/tests/fixtures/codegraph-transcripts/"
            for rel in (fixtures + "sequential-turns.jsonl", fixtures + "README.md", ".claude/hooks/tests/test_codegraph_shadow.py"):
                self.plant(root, rel, named)
            self.assertEqual(codegraph_name_files(root), [])
            # a neighbouring file, a sibling folder and a look-alike folder name are all still caught
            for rel in (".claude/hooks/tests/test_codegraph_shadow_extra.py",
                        ".claude/hooks/tests/fixtures/other/x.jsonl",
                        ".claude/hooks/tests/fixtures/codegraph-transcripts-copy/x.jsonl"):
                self.plant(root, rel, named)
            self.assertEqual(codegraph_name_files(root),
                             [".claude/hooks/tests/fixtures/codegraph-transcripts-copy/x.jsonl",
                              ".claude/hooks/tests/fixtures/other/x.jsonl",
                              ".claude/hooks/tests/test_codegraph_shadow_extra.py"])

    def test_control_a_copy_under_a_worktrees_segment_and_an_unshipped_test_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.plant(root, "agents/.claude/worktrees/x/zz.md", CG_PREFIX + "search\n")
            self.plant(root, ".claude/scripts/tests/test_x.py", CG_PREFIX + "search\n")
            self.assertEqual(codegraph_name_files(root), [])

    def test_no_shipped_file_names_an_individual_codegraph_tool(self):
        files = shipped_files(PLUGIN_ROOT)
        self.assertGreater(len(files), 0, "the scan must have read shipped files")
        for rel in CG_EXEMPT:
            self.assertIn(rel, files, "the scan must reach the exempt proof file %s" % rel)
        self.assertEqual(codegraph_name_files(PLUGIN_ROOT), [],
                         "no shipped file may name `mcp__codegraph__codegraph_<tool>` or a bare legacy tool name "
                         "(search, node, callers, callees, impact, files, status, context); say `%s` or 'a CodeGraph "
                         "tool'. Only %s may, because they prove the wildcard covers the legacy names; and %s, "
                         "which hold recorded transcripts and the test that replays them"
                         % (CG_WILDCARD, " and ".join(CG_EXEMPT),
                            " and ".join(CG_EXEMPT_RECORDED + CG_EXEMPT_RECORDED_DIRS)))

    def test_control_the_grant_check_catches_a_per_tool_grant_and_accepts_the_wildcard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.plant(root, "agents/good.md", "---\nname: good\ntools: Read, Grep, " + CG_WILDCARD + "\n---\nbody\n")
            self.plant(root, "agents/none.md", "---\nname: none\ntools: Read\n---\nbody\n")
            self.assertEqual(codegraph_grant_problems(root), (2, []))
            self.plant(root, "agents/bad.md", "---\nname: bad\ntools: Read, " + CG_PREFIX + "search\n---\nbody\n")
            self.plant(root, "agents/both.md", "---\nname: both\ntools: " + CG_WILDCARD + ", " + CG_PREFIX + "node\n---\n")
            read, problems = codegraph_grant_problems(root)
            self.assertEqual(read, 4)
            self.assertEqual(len(problems), 2, problems)

    def test_every_agent_that_grants_codegraph_grants_exactly_the_wildcard(self):
        read, problems = codegraph_grant_problems(PLUGIN_ROOT)
        self.assertGreater(read, 0, "the scan must have read the agent files")
        self.assertEqual(problems, [], "an agent's tools: line grants CodeGraph through `%s` and nothing narrower" % CG_WILDCARD)
        granting = [p.name for p in (PLUGIN_ROOT / "agents").glob("*.md")
                    if CG_WILDCARD in (tools_line(p.read_text(encoding="utf-8", errors="replace")) or "")]
        self.assertGreater(len(granting), 0, "at least one agent must grant the wildcard (the scan is not vacuous)")


# Issue #295 (concept contract 2026-11-07-295-codegraph-gate-dropped-mcp): the texts that tell an agent about the hook
# freshness check, the command-line route and the profile re-record. Each scan reads a real section and asserts it found it.
def _section(text: str, start: str, stop: str) -> str:
    begin = text.find(start)
    if begin < 0:
        return ""
    end = text.find(stop, begin + len(start))
    return text[begin:end if end > 0 else len(text)]


class TestCodegraphFreshnessTexts(unittest.TestCase):
    VBD = SKILLS / "verify-before-done" / "SKILL.md"
    INSTALL = SKILLS / "auto-improve-codegraph-install" / "SKILL.md"
    UNINSTALL = SKILLS / "auto-improve-codegraph-uninstall" / "SKILL.md"

    def step_58(self) -> str:
        return _section(self.VBD.read_text(encoding="utf-8"), "## Step 5.8", "## Step 6")

    def test_step_5_8_is_found(self):
        self.assertTrue(self.step_58().strip(), "the scan must read Step 5.8 of /verify-before-done (it found nothing)")

    def test_step_5_8_names_the_four_finding_codes_the_note_and_the_freshness_rule(self):
        text = self.step_58()
        for code in ("addon-hook-outdated", "addon-hook-missing", "addon-row-missing", "addon-row-outdated", "addon-hook-unrecognised"):
            self.assertIn(code, text, "Step 5.8 must name the finding %s" % code)
        self.assertIn("freshness", text, "Step 5.8 must name the freshness field")
        self.assertRegex(text, r"(?is)freshness.{0,300}could not check|could not check.{0,300}freshness",
                         "a result without `freshness` reads 'could not check' and is NOT READY (an older installer)")
        line = next((ln for ln in text.splitlines() if "addon-hook-unrecognised" in ln), "")
        self.assertRegex(line, r"(?i)\bnote\b", "the unrecognised-copy code is described as a note (it never makes the step NOT READY)")

    def test_step_5_8_finds_the_installer_through_the_plugin_only(self):
        text = self.step_58()
        self.assertIn("FIP", text, "Step 5.8 looks the installer up into FIP (plugin-only)")
        self.assertIsNone(re.search(r'\[ -f "\$S" \]\s*;\s*then\s+FI[P]?=\$S', text), "and never takes the project's own copy")

    def test_the_install_skill_tells_the_profile_re_record_the_age_row_and_the_first_prompt_notice(self):
        text = self.INSTALL.read_text(encoding="utf-8")
        self.assertIn("record-registrations", text, "a project with a Hook registration profile re-records it after the install")
        self.assertIn("0.16.1", text, "the upgrade-age row for 0.16.1 (one new row to add)")
        self.assertRegex(text, r"(?i)first prompt", "the install skill states the possible false notice on the first prompt")
        self.assertRegex(text, r"codegraph explore", "and shows the command-line route")

    def test_the_uninstall_skill_finds_the_installer_through_the_plugin_only(self):
        text = self.UNINSTALL.read_text(encoding="utf-8")
        self.assertIn("FIP", text)

    def test_the_readme_records_the_change_and_the_profile_note(self):
        text = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("Changed in 0.16.5", text)
        section = _section(text, "Changed in 0.16.5", "**Changed in 0.")
        self.assertIn("record-registrations", section, "the note for a project with a Hook registration profile")

    def test_the_decision_table_teaches_the_command_line_route(self):
        text = (PLUGIN_ROOT / ".claude" / "references" / "codegraph-decision-table.md").read_text(encoding="utf-8")
        self.assertIn("codegraph explore", text, "the decision table names the bare command-line form")


# --- (6) the template's "Chat Tool Impact" section names no consuming project's artefact -------------------------
# Contract .claude/concepts/2026-11-11-audit-followups-165.md (V4, V19, invariant I-7). The section used to name one
# project's files, phase, adapter id, agents, slash command, route, contract slug and memory note. Seven rules pin it;
# each has a made-up control proving it fires.
CHAT_TOOL_HEADING = "## Chat Tool Impact"
_SOURCE_FILE_RE = re.compile(r"\b[\w.\-]+\.(?:cs|ts|py|java)\b")
_PHASE_LABEL_RE = re.compile(r"\bPhase\s+[A-Za-z]\d\b")
_HEX_ID_RE = re.compile(r"\b(?=[0-9a-f]*\d)[0-9a-f]{6,}\b")
_BACKTICK_NAME_RE = re.compile(r"`([a-z][a-z0-9]*(?:-[a-z0-9]+)+)`")
_SLASH_COMMAND_RE = re.compile(r"(?<![\w/.\-<>])/([a-z][a-z0-9\-]*)(?![\w/\-])")
_HTTP_ROUTE_RE = re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE)\s+/api/")
_DATED_SLUG_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}-[a-z0-9][a-z0-9\-]*")
_FEEDBACK_NOTE_RE = re.compile(r"\bfeedback_[\w\-]*\.md\b")


def chat_tool_section(text: str) -> str:
    """The text from the `## Chat Tool Impact` heading to the next `---` rule or `## ` heading ('' if absent)."""
    m = re.search(r"(?m)^## Chat Tool Impact\b.*$", text)
    if not m:
        return ""
    rest = text[m.end():]
    stop = re.search(r"(?m)^(?:---\s*|## .*)$", rest)
    return text[m.start():m.end() + (stop.start() if stop else len(rest))]


def skill_names() -> set[str]:
    return {p.name for p in SKILLS.iterdir() if p.is_dir()}


def chat_tool_violations(section: str, agents: set[str], skills: set[str]) -> dict[int, list[str]]:
    """Rule number -> offending matches in ``section`` (only rules that fire appear)."""
    found: dict[int, list[str]] = {}

    def add(rule: int, items: list[str]) -> None:
        if items:
            found.setdefault(rule, []).extend(items)

    add(1, [m.group(0) for m in _SOURCE_FILE_RE.finditer(section)])
    add(2, [m.group(0) for m in _PHASE_LABEL_RE.finditer(section)])
    add(3, [m.group(0) for m in _HEX_ID_RE.finditer(section)])
    add(4, [m.group(1) for m in _BACKTICK_NAME_RE.finditer(section) if m.group(1) not in agents])
    add(5, ["/" + m.group(1) for m in _SLASH_COMMAND_RE.finditer(section) if m.group(1) not in skills])
    add(6, [m.group(0) for m in _HTTP_ROUTE_RE.finditer(section)])
    add(7, [m.group(0) for m in _DATED_SLUG_RE.finditer(section)] + [m.group(0) for m in _FEEDBACK_NOTE_RE.finditer(section)])
    add(8, folder_paths(section))
    return found


# Rule 8 (contract 2026-11-13-audit-followups-165-chores): no folder path outside `.claude/`. A segment is one or more
# word characters, `.` or `-`. A path starts where the previous character is not a segment character or `/` and ends
# where the next one is not either (a sentence-ending `.` is not part of it). It fires with a final `/`, or with three
# or more segments and no final `/`. A two-segment form with no final `/` (`frob/data`) does not fire: it cannot be told
# from prose such as `and/or` (stated residual).
_FOLDER_PATH_RE = re.compile(r"(?<![\w.\-/])(?:[\w.\-]+/)+[\w.\-]*(?![\w.\-/])")


def folder_paths(section: str) -> list[str]:
    found = []
    for m in _FOLDER_PATH_RE.finditer(section):
        path = m.group(0).rstrip(".")
        segments = [s for s in path.split("/") if s]
        if not segments or segments[0] == ".claude":
            continue
        if path.endswith("/") or len(segments) >= 3:
            found.append(path)
    return found


class TestChatToolImpactSectionIsGeneric(unittest.TestCase):
    AGENTS_SET = {"contract-critic", "data-architect"}
    SKILLS_SET = {"design-first", "flow"}

    def fires(self, text: str) -> set[int]:
        return set(chat_tool_violations(text, self.AGENTS_SET, self.SKILLS_SET))

    def test_control_rule_1_a_source_file_name_fires(self):
        for name in ("FooTools.cs", "foo.ts", "frob_runner.py", "FrobService.java"):
            self.assertIn(1, self.fires("declare it in " + name), name)
        self.assertNotIn(1, self.fires("the project's chat-tool definition file"))

    def test_control_rule_2_a_phase_label_fires(self):
        self.assertIn(2, self.fires("Phase Z9 Frob Learner added a route"))
        self.assertNotIn(2, self.fires("a later phase of the project"))

    def test_control_rule_3_a_hex_id_fires(self):
        self.assertIn(3, self.fires("adapter 1a2b3c4d was archived"))
        self.assertNotIn(3, self.fires("a decade of facade work"))

    def test_control_rule_4_an_agent_shaped_name_outside_the_plugin_fires(self):
        self.assertIn(4, self.fires("the `frob-reviewer` audited it"))
        self.assertNotIn(4, self.fires("the `contract-critic` checks it"))
        self.assertNotIn(4, self.fires("the project's model-training agent"))

    def test_control_rule_5_a_slash_command_that_is_not_a_skill_fires(self):
        self.assertIn(5, self.fires("the next /retrain-frob cycle"))
        self.assertNotIn(5, self.fires("the next /design-first cycle"))
        self.assertNotIn(5, self.fires("UI-only/admin-only and the rest/docs lists in .claude/hooks/x.json"))

    def test_control_rule_6_an_http_verb_and_api_route_fires(self):
        self.assertIn(6, self.fires("POST /api/frobs/{id}/start"))
        self.assertIn(6, self.fires("DELETE /api/x"))
        self.assertNotIn(6, self.fires("a REST endpoint or SignalR event"))

    def test_control_rule_7_a_dated_contract_slug_and_a_feedback_note_fire(self):
        self.assertIn(7, self.fires("a mini-phase (2026-01-02-frob-chat-tools)"))
        self.assertIn(7, self.fires("see feedback_frob_rule.md for the rules"))
        self.assertNotIn(7, self.fires("name the follow-up contract; dated YYYY-MM-DD-slug"))

    def test_control_section_extraction_stops_at_the_next_rule_or_heading(self):
        text = "## Chat Tool Impact (x)\nbody FooTools.cs\n\n---\n\n## Next\nBar.cs\n"
        self.assertIn("FooTools.cs", chat_tool_section(text))
        self.assertNotIn("Bar.cs", chat_tool_section(text))
        self.assertEqual(chat_tool_section("no heading"), "")

    def test_the_template_section_names_no_consuming_projects_artefact(self):
        template = (TEMPLATES / "concept-contract.md").read_text(encoding="utf-8")
        section = chat_tool_section(template)
        self.assertTrue(section.strip(), "the scan must read the Chat Tool Impact section of the template")
        agents, skills = plugin_agent_names(), skill_names()
        self.assertGreater(len(agents), 0)
        self.assertGreater(len(skills), 0)
        self.assertEqual(chat_tool_violations(section, agents, skills), {},
                         "the section must name no source file, Phase label, hex id, non-plugin agent, non-skill "
                         "slash command, HTTP /api/ route, dated contract slug or feedback note")

    def test_the_template_section_keeps_the_heading_and_the_three_sanctioned_answers(self):
        section = chat_tool_section((TEMPLATES / "concept-contract.md").read_text(encoding="utf-8"))
        self.assertTrue(section.startswith(CHAT_TOOL_HEADING))
        self.assertIn("Yes —", section)
        self.assertIn("No —", section)
        self.assertIn("Deferred", section)

    def test_control_rule_8_a_folder_path_outside_dot_claude_fires(self):
        for text in ("frob/train-data/synthetic/", "put it in `frob/data/`.", "the .frob/zed/ folder",
                     "see frob/train-data/synthetic for the rest", "in frob/data/."):
            self.assertIn(8, self.fires(text), text)

    def test_control_rule_8_prose_slashes_and_dot_claude_paths_do_not_fire(self):
        for text in ("UI/admin-only", "endpoint/event", "the `rest`/`docs` lists", "and/or", "frob/data",
                     "under .claude/frob/", "in .claude/hooks/sentinel-paths.json", "the /design-first skill"):
            self.assertNotIn(8, self.fires(text), text)


def agent_item_7(text: str) -> str:
    """Critic item 7: from the line that starts `7. **Integration surface omission` up to the next numbered item
    (`8. **...`) or the next heading, whichever comes first ('' if absent)."""
    m = re.search(r"(?m)^7\. \*\*Integration surface omission", text)
    if not m:
        return ""
    rest = text[m.start():]
    stop = re.search(r"(?m)^(?:\d+\. \*\*|#{1,6} )", rest[1:])
    return rest[:stop.start() + 1] if stop else rest


def reviewer_training_section(text: str) -> str:
    return _section(text, "## LLM Training Data Maintenance", "\n## ")


_TRAINING_PHRASE_RE = re.compile(r"(model-training agent or skill, if it has one)")
_OPENING_PHRASE = "whatever the contract's `## Chat Tool Impact` answer is, or if the answer is missing"


def template_training_phrase(template: str) -> str:
    """The template's wording for the model-training agent ('' if absent), read when the test runs."""
    m = _TRAINING_PHRASE_RE.search(template)
    return m.group(1) if m else ""


def reviewer_body(section: str) -> str:
    """The section below its heading line; a heading-only section has an empty body."""
    return section.split("\n", 1)[1] if "\n" in section else ""


def reviewer_training_problems(section: str, phrase: str) -> list[str]:
    """I-5 positive content: clauses (a), (b), (c), WARNING-only findings and the template's agent wording, all in the body."""
    body = reviewer_body(section)
    if not body.strip():
        return ["the section has no body below its heading"]
    out = [f"clause {c} is missing" for c in ("(a)", "(b)", "(c)") if c not in body]
    if "WARNING" not in body:
        out.append("the findings are not named WARNING")
    if "never blocking" not in body:
        out.append("the section does not say the findings are never blocking")
    if "BLOCKER" in body:
        out.append("the section names a BLOCKER; the findings are WARNING-only")
    if not phrase:
        out.append("the template's model-training agent wording was not found")
    elif phrase not in body:
        out.append(f"the template's wording {phrase!r} is missing")
    return out


def reviewer_opening_problems(section: str) -> list[str]:
    """The limit phrase sits in the opening sentence, not in clause (c); (c) reads 'Otherwise raise nothing'."""
    body = reviewer_body(section)
    lines = [ln for ln in body.splitlines() if ln.strip()]
    opening = lines[0] if lines else ""
    clause_c = next((ln for ln in lines if ln.startswith("- **(c)")), "")
    out = []
    if _OPENING_PHRASE not in opening:
        out.append("the opening sentence lacks the 'whatever the contract's ... answer is, or if the answer is missing' phrase")
    if not clause_c:
        out.append("clause (c) was not found")
    else:
        if _OPENING_PHRASE in clause_c:
            out.append("clause (c) still carries the 'whatever ... answer is missing' phrase")
        if not clause_c.startswith("- **(c) Otherwise raise nothing"):
            out.append("clause (c) does not start 'Otherwise raise nothing'")
        if "This also holds when no contract is under review." not in clause_c:
            out.append("clause (c) lacks 'This also holds when no contract is under review.'")
    return out


def template_answer_heads(template: str) -> list[str]:
    """The three answer heads of the template's Chat Tool Impact section, without the final period."""
    return re.findall(r"(?m)^\d\.\s+\*\*(.+?)\.\*\*", chat_tool_section(template))


def item_7_problems(item: str, heads: list[str]) -> list[str]:
    out = [f"answer head not in item 7: {h!r}" for h in heads if h not in item]
    for needed in ("BLOCKER", CHAT_TOOL_HEADING, "Why this section exists"):
        if needed not in item:
            out.append(f"item 7 lacks {needed!r}")
    return out


class TestAgentPassagesAreGeneric(unittest.TestCase):
    """Rules 1-8 on the two agent passages that used to carry one project's text (contract 2026-11-13, I-3..I-5)."""
    CRITIC = AGENTS / "contract-critic.md"
    REVIEWER = AGENTS / "fullstack-code-reviewer.md"

    def test_critic_item_7_is_found_and_names_no_consuming_projects_artefact(self):
        item = agent_item_7(self.CRITIC.read_text(encoding="utf-8"))
        self.assertTrue(item.strip(), "the scan must find critic item 7 (the line that starts `7. **Integration surface omission`)")
        self.assertEqual(chat_tool_violations(item, plugin_agent_names(), skill_names()), {},
                         "critic item 7 must name no source file, Phase label, hex id, non-plugin agent, non-skill slash "
                         "command, HTTP route, dated contract slug, feedback note or folder path")

    def test_reviewer_training_section_is_found_and_names_no_consuming_projects_artefact(self):
        section = reviewer_training_section(self.REVIEWER.read_text(encoding="utf-8"))
        self.assertTrue(reviewer_body(section).strip(),
                        "the scan must find a non-empty body below the reviewer's `## LLM Training Data Maintenance` heading")
        self.assertEqual(chat_tool_violations(section, plugin_agent_names(), skill_names()), {},
                         "the reviewer section must name no source file, Phase label, hex id, non-plugin agent, non-skill "
                         "slash command, HTTP route, dated contract slug, feedback note or folder path")

    def test_reviewer_training_section_names_no_profile_slot_and_no_sentinel_file(self):
        section = reviewer_training_section(self.REVIEWER.read_text(encoding="utf-8"))
        self.assertTrue(reviewer_body(section).strip(),
                        "the scan must find a non-empty body below the reviewer's `## LLM Training Data Maintenance` heading")
        for banned in ("project-profile", "sentinel-paths"):
            self.assertNotIn(banned, section, "I-5: the reviewer reads only the contract under review and the diff")

    def test_reviewer_training_section_keeps_clauses_a_b_c_as_warnings_and_the_templates_agent_wording(self):
        phrase = template_training_phrase((TEMPLATES / "concept-contract.md").read_text(encoding="utf-8"))
        section = reviewer_training_section(self.REVIEWER.read_text(encoding="utf-8"))
        self.assertEqual(reviewer_training_problems(section, phrase), [],
                         "I-5: the reviewer section must keep clauses (a), (b), (c), WARNING-only findings (never "
                         "BLOCKER) and the template's model-training agent wording")

    def test_control_a_heading_only_or_blocker_reviewer_section_fails(self):
        phrase = "frob-training agent or skill, if it has one"
        good = ("## LLM Training Data Maintenance\n\nOpening.\n\n- **(a) One.** x\n- **(b) Two.** y\n- **(c) Otherwise raise nothing.** z\n\n"
                "Both findings are WARNINGs, never blocking. Launch the project's " + phrase + ".\n")
        self.assertEqual(reviewer_training_problems(good, phrase), [])
        self.assertNotEqual(reviewer_training_problems("## LLM Training Data Maintenance\n", phrase), [])
        self.assertNotEqual(reviewer_training_problems("## LLM Training Data Maintenance", phrase), [])
        self.assertNotEqual(reviewer_training_problems(good.replace("never blocking", "a BLOCKER"), phrase), [])
        self.assertNotEqual(reviewer_training_problems(good.replace(phrase, "some agent"), phrase), [])

    def test_reviewer_limit_phrase_sits_in_the_opening_sentence_and_clause_c_is_otherwise_raise_nothing(self):
        section = reviewer_training_section(self.REVIEWER.read_text(encoding="utf-8"))
        self.assertEqual(reviewer_opening_problems(section), [],
                         "the 'whatever the contract's `## Chat Tool Impact` answer is, or if the answer is missing' "
                         "phrase belongs in the opening sentence; clause (c) reads 'Otherwise raise nothing. This "
                         "also holds when no contract is under review.'")

    def test_control_the_limit_phrase_inside_clause_c_fails(self):
        good = ("## LLM Training Data Maintenance\n\nTake facts from the contract, " + _OPENING_PHRASE + ", and the diff.\n\n"
                "- **(a) One.** x\n- **(c) Otherwise raise nothing.** This also holds when no contract is under review. Stated.\n")
        self.assertEqual(reviewer_opening_problems(good), [])
        bad = good.replace("contract, " + _OPENING_PHRASE + ", and", "contract and").replace(
            "under review.", "under review, " + _OPENING_PHRASE + ".")
        problems = reviewer_opening_problems(bad)
        self.assertTrue(any("opening sentence lacks" in p for p in problems), problems)
        self.assertTrue(any("clause (c) still carries" in p for p in problems), problems)
        old_c = good.replace("- **(c) Otherwise raise nothing.** This also holds", "- **(c) Raise nothing.** It holds")
        self.assertNotEqual(reviewer_opening_problems(old_c), [])

    def test_control_item_7_is_read_to_the_next_numbered_item(self):
        text = ("6. **Other.** a\n\n7. **Integration surface omission (BLOCKER if hit)** — first line.\n"
                "   Second line names frob/train-data/synthetic/ here.\n\n8. **Next.** frob/other/place/ stays out.\n")
        item = agent_item_7(text)
        self.assertIn("Second line", item)
        self.assertNotIn("Next.", item)
        self.assertIn(8, chat_tool_violations(item, set(), set()))
        self.assertEqual(agent_item_7("no such item"), "")

    def test_critic_item_7_keeps_the_templates_answer_heads_and_points_at_its_authority(self):
        heads = template_answer_heads((TEMPLATES / "concept-contract.md").read_text(encoding="utf-8"))
        self.assertEqual(len(heads), 3, "the scan must read the template's three answer heads, got %r" % heads)
        item = agent_item_7(self.CRITIC.read_text(encoding="utf-8"))
        self.assertTrue(item.strip(), "the scan must find critic item 7")
        self.assertEqual(item_7_problems(item, heads), [],
                         "critic item 7 must quote the template's answer heads word for word, keep BLOCKER and "
                         "`## Chat Tool Impact`, and cite the template's 'Why this section exists' as its precedent")

    def test_control_item_7_with_the_old_answers_or_without_the_pointer_fails(self):
        heads = ["Yes — this contract adds a chat tool", "No — this endpoint/event is UI-only or admin-only",
                 "Deferred to a follow-up mini-phase"]
        good = ("7. **Integration surface omission (BLOCKER if hit)** — `## Chat Tool Impact` is missing or not one of "
                "`" + "`, `".join(heads) + "`? See the template's section, Why this section exists.")
        self.assertEqual(item_7_problems(good, heads), [])
        old = good.replace(heads[0], "Yes — declares schema")
        self.assertNotEqual(item_7_problems(old, heads), [])
        self.assertNotEqual(item_7_problems(good.replace("BLOCKER", "WARNING"), heads), [])
        self.assertNotEqual(item_7_problems(good.replace("Why this section exists", "a precedent"), heads), [])

    def test_control_template_answer_heads_are_read_from_a_fixture(self):
        fixture = ("## Chat Tool Impact (x)\n\n1. **Yes — frob.** Declare.\n   - **Tool name** (a):\n"
                   "2. **No — zed.** One line.\n3. **Deferred to later.** Name it.\n\n---\n")
        self.assertEqual(template_answer_heads(fixture), ["Yes — frob", "No — zed", "Deferred to later"])


_HEADING_BACKTICK_RE = re.compile(r"`([^`]+)`")


def template_unshipped_names(text: str, agents: set[str], not_shipped: tuple[str, ...]) -> list[str]:
    """Names in `text` that the plugin does not ship.

    Two kinds: any NOT_SHIPPED name anywhere in the text, and any backticked name in a "###" heading that is
    not a plugin agent. Both lists come from the callers, never copied here.
    """
    found = [name for name in not_shipped if name in text]
    for line in text.splitlines():
        if line.startswith("###"):
            found += [n for n in _HEADING_BACKTICK_RE.findall(line) if n not in agents]
    return found


class TestTemplateNamesOnlyShippedAgents(unittest.TestCase):
    """The whole concept-contract template, not only its Chat Tool Impact section, names no unshipped agent."""

    @staticmethod
    def not_shipped() -> tuple[str, ...]:
        tests_dir = str(Path(__file__).resolve().parent)
        if tests_dir not in sys.path:
            sys.path.append(tests_dir)
        from test_plugin_doctor import TestTheRealPluginTree
        return TestTheRealPluginTree.NOT_SHIPPED

    def test_control_a_planted_unshipped_name_and_a_planted_heading_fail(self):
        agents, not_shipped = plugin_agent_names(), self.not_shipped()
        self.assertIn("ingestion-data-architect", not_shipped)
        self.assertTrue(template_unshipped_names("implementers: `ingestion-data-architect`", agents, not_shipped))
        self.assertTrue(template_unshipped_names("### 3. Data (`ingestion-data-architect`)", agents, not_shipped))
        self.assertTrue(template_unshipped_names("### 3. Data (`frob-reviewer`)", agents, not_shipped))
        self.assertEqual(template_unshipped_names("### 1. Backend (`dotnet-backend-architect`)", agents, not_shipped), [])

    def test_the_whole_template_names_no_unshipped_agent(self):
        text = (TEMPLATES / "concept-contract.md").read_text(encoding="utf-8")
        self.assertEqual(template_unshipped_names(text, plugin_agent_names(), self.not_shipped()), [])

    def test_the_protocol_line_names_exactly_the_default_implementers(self):
        import pr_merged
        text = (TEMPLATES / "concept-contract.md").read_text(encoding="utf-8")
        line = next(l for l in text.splitlines() if l.startswith("> **Protocol:**"))
        listed = re.search(r"Implementer agents \((.*?)\) refuse", line)
        self.assertIsNotNone(listed)
        self.assertEqual(tuple(re.findall(r"`([^`]+)`", listed.group(1))), tuple(pr_merged.DEFAULT_IMPLEMENTERS))


_TEST_COUNT_RE = re.compile(r"\b\d[\d,]*\s+(?:unit\s+)?(?:tests|cases)\b", re.I)
PR_MERGED_SUITE = ".claude/scripts/tests/test_pr_merged.py"


def count_claims_in(text: str) -> list[str]:
    """Digit counts of tests or cases ("760 cases", "Ran 760 tests"): they go stale on the next test added."""
    return [m.group(0) for m in _TEST_COUNT_RE.finditer(text)]


class TestSkillsStateNoTestCountForThePrMergedSuite(unittest.TestCase):
    FILES = ("pr-merged", "advance")

    def test_control_a_planted_ran_760_tests_is_flagged_and_prose_is_not(self):
        self.assertEqual(count_claims_in("reads `Ran 760 tests ... OK`"), ["760 tests"])
        self.assertEqual(count_claims_in("covered by 760 cases over identity"), ["760 cases"])
        self.assertEqual(count_claims_in("its unittest summary line must end OK"), [])
        self.assertEqual(count_claims_in("every test case and the tests"), [])

    def test_neither_skill_states_a_digit_count_of_tests_or_cases(self):
        for name in self.FILES:
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(count_claims_in(text), [], name)

    def test_each_skill_names_the_suite_its_run_command_and_the_ok_ending(self):
        for name in self.FILES:
            text = squash((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"))
            self.assertIn(PR_MERGED_SUITE, text, name)
            self.assertIn("py -3 " + PR_MERGED_SUITE, text, name)
            self.assertIn("its unittest summary line must end OK", text.replace("`", ""), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
