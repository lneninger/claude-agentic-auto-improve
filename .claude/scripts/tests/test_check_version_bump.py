import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import check_version_bump as cvb  # noqa: E402


class EvaluateTests(unittest.TestCase):
    def test_a_script_change_without_a_bump_fails(self):
        code, _ = cvb.evaluate([".claude/scripts/merge_direction.py"], ["0.8.6", "0.8.6"], ["0.8.6", "0.8.6"])
        self.assertEqual(code, 1)

    def test_a_script_change_with_a_higher_version_passes(self):
        code, _ = cvb.evaluate([".claude/scripts/merge_direction.py"], ["0.8.6"], ["0.8.7", "0.8.7"])
        self.assertEqual(code, 0)

    def test_disagreeing_manifests_fail(self):
        code, _ = cvb.evaluate(["skills/x/SKILL.md"], ["0.8.6"], ["0.8.7", "0.8.6"])
        self.assertEqual(code, 1)

    def test_a_lower_version_fails(self):
        code, _ = cvb.evaluate([".claude/hooks/a.py"], ["0.8.6"], ["0.8.5"])
        self.assertEqual(code, 1)

    def test_tests_briefs_and_docs_alone_need_no_bump(self):
        changed = [".claude/scripts/tests/test_a.py", ".claude/work-items/x.md", "CLAUDE.md", "README.md"]
        self.assertEqual(cvb.evaluate(changed, ["0.8.6"], ["0.8.6"])[0], 0)

    def test_an_unreadable_version_is_never_an_allow(self):
        self.assertEqual(cvb.evaluate([".claude/hooks/a.py"], ["bad"], ["0.8.6"])[0], 2)

    def test_numeric_not_textual_comparison(self):
        self.assertEqual(cvb.evaluate([".claude/hooks/a.py"], ["0.8.9"], ["0.8.10"])[0], 0)


if __name__ == "__main__":
    unittest.main()
