"""Every skill an agent preloads through its `skills:` front matter must ship as skills/<name>/SKILL.md.

A preload that names a skill the plugin does not ship is silently dead. The entries are read the way
test_angular_rule_delivery.py reads them.
"""
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _front_matter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\r?\n(.*?)\r?\n---", text, re.S)
    assert match, f"{path} has no front matter"
    return match.group(1)


def _skills_entries(path: Path) -> list[str]:
    entries: list[str] = []
    in_block = False
    for line in _front_matter(path).splitlines():
        if re.match(r"^skills:\s*$", line):
            in_block = True
        elif in_block and re.match(r"^\s+-\s+", line):
            entries.append(re.sub(r"^\s+-\s+", "", line).strip().strip("'\""))
        elif in_block:
            break
    return entries


def unresolved_preloads(root: Path) -> list[str]:
    """`<agent>: <skill>` for every skills: entry with no skills/<skill>/SKILL.md under `root`."""
    missing: list[str] = []
    for agent in sorted((root / "agents").glob("*.md")):
        for name in _skills_entries(agent):
            if not (root / "skills" / name / "SKILL.md").is_file():
                missing.append(f"{agent.name}: {name}")
    return missing


class AgentSkillPreloadTests(unittest.TestCase):
    def test_every_preloaded_skill_ships(self):
        self.assertEqual(unresolved_preloads(ROOT), [])

    def test_python_ai_developer_preloads_nothing(self):
        self.assertEqual(_skills_entries(ROOT / "agents" / "python-ai-developer.md"), [])

    def test_cloud_engineer_ships_with_its_tools_and_scope_rule(self):
        path = ROOT / "agents" / "cloud-engineer.md"
        self.assertTrue(path.is_file())
        front = _front_matter(path)
        self.assertIn("tools: Read, Edit, Write, Grep, Glob, Bash, Skill, mcp__codegraph__*", front)
        text = path.read_text(encoding="utf-8")
        for needle in ("cloud.providers", "cloud.roots", "for the user to run", "never run a deploy",
                       "No concept contract provided", "permission prompts"):
            self.assertIn(needle, text)
        self.assertTrue((ROOT / "skills" / "cloud-engineering" / "SKILL.md").is_file())

    def test_cloud_engineer_stops_when_its_skill_cannot_load(self):
        text = (ROOT / "agents" / "cloud-engineer.md").read_text(encoding="utf-8")
        self.assertIn("If the skill cannot be loaded, stop and say so", text)

    def test_every_agent_that_invokes_a_skill_can_load_it(self):
        offenders: list[str] = []
        for agent in sorted((ROOT / "agents").glob("*.md")):
            text = agent.read_text(encoding="utf-8")
            body = text[len(re.match(r"---\r?\n.*?\r?\n---", text, re.S).group(0)):]
            if "with the Skill tool" not in body:
                continue
            tools_line = next((ln for ln in _front_matter(agent).splitlines() if ln.startswith("tools:")), "")
            tools = [t.strip() for t in tools_line[len("tools:"):].split(",")]
            if "Skill" not in tools and not _skills_entries(agent):
                offenders.append(agent.name)
        self.assertEqual(offenders, [])

    def test_security_auditor_has_the_infrastructure_checklist(self):
        text = (ROOT / "agents" / "security-auditor.md").read_text(encoding="utf-8")
        self.assertIn("### Infrastructure as code (active when `cloud.providers` is set)", text)

    def test_debug_routes_container_bugs_to_cloud_engineer(self):
        text = (ROOT / "skills" / "debug" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`cloud-engineer`", text)
        self.assertNotIn("docker-master-goat", text)

    def test_the_angular_agents_still_preload_their_skill(self):
        for name in ("angular-senior-dev", "ui-ux-designer"):
            self.assertIn("angular-ui-rules", _skills_entries(ROOT / "agents" / f"{name}.md"))

    def test_a_planted_missing_name_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)
            (fake / "agents").mkdir()
            (fake / "skills" / "real").mkdir(parents=True)
            (fake / "skills" / "real" / "SKILL.md").write_text("# real\n", encoding="utf-8")
            (fake / "agents" / "ok.md").write_text("---\nname: ok\nskills:\n  - real\n---\nbody\n", encoding="utf-8")
            self.assertEqual(unresolved_preloads(fake), [])
            (fake / "agents" / "bad.md").write_text("---\nname: bad\nskills:\n  - ghost\n---\nbody\n",
                                                    encoding="utf-8")
            self.assertEqual(unresolved_preloads(fake), ["bad.md: ghost"])


class DebugAreaRoutingTests(unittest.TestCase):
    """The /debug area routing names only shipped agents; the sys.path setup and the two imports run once."""

    @classmethod
    def setUpClass(cls):
        tests_dir = str(Path(__file__).resolve().parent)
        scripts_dir = str(Path(__file__).resolve().parent.parent)
        for p in (tests_dir, scripts_dir):
            if p not in sys.path:
                sys.path.append(p)
        from test_plugin_text_scans import plugin_agent_names
        from test_plugin_doctor import TestTheRealPluginTree
        cls.shipped_agent_names = staticmethod(plugin_agent_names)
        cls.not_shipped = TestTheRealPluginTree.NOT_SHIPPED

    @staticmethod
    def _unshipped_area_names(text: str, shipped: set[str], not_shipped: tuple[str, ...]) -> list[str]:
        """Agent-shaped backticked names in "Choose the agent by area" that the plugin does not ship."""
        start = text.index("Choose the agent by area")
        end = text.index("###", start)
        names = re.findall(r"`([a-z][a-z0-9]*(?:-[a-z0-9]+)+)`", text[start:end])
        # A skill (`/sql-server-patterns`) is not an agent: only names without a leading slash count.
        section = text[start:end]
        names = [n for n in names if f"`/{n}`" not in section and f"/{n}`" not in section]
        return sorted({n for n in names if n not in shipped or n in not_shipped})

    def test_debug_area_routing_names_only_shipped_agents(self):
        shipped = self.shipped_agent_names()
        text = (ROOT / "skills" / "debug" / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(self._unshipped_area_names(text, shipped, self.not_shipped), [])
        self.assertIn("`python-ai-developer`, or the project's own model-training agent if it declares one", text)
        self.assertIn("`dotnet-backend-architect`, or the project's own ingestion agent if it declares one", text)

    def test_debug_area_routing_control_catches_an_unshipped_name(self):
        planted = "Choose the agent by area:\n\n- LLM pipeline → `llm-training-engineer`\n\n### next\n"
        self.assertEqual(
            self._unshipped_area_names(planted, self.shipped_agent_names(), self.not_shipped),
            ["llm-training-engineer"])


if __name__ == "__main__":
    unittest.main()
