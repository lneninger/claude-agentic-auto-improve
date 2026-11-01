"""Every skill an agent preloads through its `skills:` front matter must ship as skills/<name>/SKILL.md.

A preload that names a skill the plugin does not ship is silently dead. The entries are read the way
test_angular_rule_delivery.py reads them.
"""
import re
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


if __name__ == "__main__":
    unittest.main()
