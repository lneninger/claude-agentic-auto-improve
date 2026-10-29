"""t7: the angular-ui-rules plugin skill ships and both Angular agents preload it."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills" / "angular-ui-rules" / "SKILL.md"
AGENTS = [ROOT / "agents" / "angular-senior-dev.md", ROOT / "agents" / "ui-ux-designer.md"]
SKILL_NAME = "angular-ui-rules"


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


class SkillContentTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SKILL.exists(), "skills/angular-ui-rules/SKILL.md is missing")
        self.text = SKILL.read_text(encoding="utf-8")

    def test_front_matter_names_the_skill(self):
        self.assertRegex(_front_matter(SKILL), rf"(?m)^name:\s*{SKILL_NAME}\s*$")

    def test_sentinel_is_the_first_body_line(self):
        body = re.sub(r"\A---\r?\n.*?\r?\n---\r?\n", "", self.text, count=1, flags=re.S)
        first = next(line for line in body.splitlines() if line.strip())
        self.assertEqual(first.strip(), "Rule set: angular-ui-rules")

    def test_precedence_clause_present(self):
        self.assertIn("The project's own instructions win over every rule document.", self.text)
        self.assertIn("the guard's verdict is final", self.text)

    def test_absence_clause_present(self):
        self.assertRegex(self.text, r"not installed")
        self.assertIn("review.documents", self.text)

    def test_per_app_and_layout_sentences(self):
        self.assertIn(".app-rules.json", self.text)
        self.assertIn("advisorRemindersAppendix", self.text)
        self.assertIn("agentic-auto-improve:application-design", self.text)
        self.assertIn("agentic-auto-improve:website-design", self.text)

    def test_no_project_facts_or_undeclared_slot(self):
        for token in ("isSuccess", "/api/screeners/symbols", "frontend.root-container"):
            self.assertNotIn(token, self.text)


class AgentPreloadTests(unittest.TestCase):
    def test_both_agents_preload_the_plugin_skill(self):
        for agent in AGENTS:
            entries = _skills_entries(agent)
            self.assertIn(SKILL_NAME, entries, f"{agent.name} skills: {entries}")
        self.assertTrue((ROOT / "skills" / SKILL_NAME / "SKILL.md").exists())

    def test_ui_ux_designer_no_longer_preloads_bare_angular(self):
        self.assertNotIn("angular", _skills_entries(AGENTS[1]))

    def test_senior_dev_has_no_inline_rules_or_project_facts(self):
        text = AGENTS[0].read_text(encoding="utf-8")
        for token in ("isSuccess", "/api/screeners/symbols", "frontend.root-container", "- **Components:**", "- **DI:**"):
            self.assertNotIn(token, text)
        self.assertIn("frontend.roots", text)


if __name__ == "__main__":
    unittest.main()
