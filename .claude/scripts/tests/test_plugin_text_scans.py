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
        self.assertIn("Changed in 0.16.4", text)
        section = _section(text, "Changed in 0.16.4", "**Changed in 0.")
        self.assertIn("record-registrations", section, "the note for a project with a Hook registration profile")

    def test_the_decision_table_teaches_the_command_line_route(self):
        text = (PLUGIN_ROOT / ".claude" / "references" / "codegraph-decision-table.md").read_text(encoding="utf-8")
        self.assertIn("codegraph explore", text, "the decision table names the bare command-line form")


if __name__ == "__main__":
    unittest.main(verbosity=2)
