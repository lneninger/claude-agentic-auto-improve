#!/usr/bin/env python3
"""
Tests for plugin_doctor.py — create what a consuming project is missing.

Every test runs against a throwaway directory. Nothing touches a real project.

Run: py -3 .claude/scripts/tests/test_plugin_doctor.py
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plugin_doctor import (  # noqa: E402
    REQUIREMENTS,
    Requirement,
    check,
    apply_fixes,
    scaffold_for,
)


def _fake_plugin(root: Path) -> Path:
    """A plugin tree with the sources a project copies from."""
    p = root / "plugin"
    (p / ".claude/templates").mkdir(parents=True)
    (p / ".claude/templates/concept-contract.md").write_text("# Concept Contract\n", encoding="utf-8")
    (p / ".claude/registries").mkdir(parents=True)
    (p / ".claude/registries/MECHANISMS.md").write_text("# Mechanisms\n", encoding="utf-8")
    (p / ".claude/project-profile.md").write_text(
        "# Project Profile\n\n| Slot | Value |\n|---|---|\n"
        "| `project.name` | *(the repository name)* |\n", encoding="utf-8")
    return p


class DoctorCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = self.tmp / "proj"
        self.project.mkdir()
        self.plugin = _fake_plugin(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


# --------------------------------------------------------------------------
class TestCheck(DoctorCase):
    def test_a_bare_project_reports_everything_missing(self):
        missing = check(self.project)
        self.assertTrue(missing, "a project with no .claude should report requirements")
        self.assertTrue(all(isinstance(r, Requirement) for r in missing))

    def test_an_existing_file_is_not_reported_missing(self):
        (self.project / ".claude").mkdir()
        (self.project / ".claude/project-profile.md").write_text("mine", encoding="utf-8")
        missing = check(self.project)
        self.assertNotIn(".claude/project-profile.md", [r.path for r in missing])

    def test_every_requirement_declares_how_it_is_satisfied(self):
        for r in REQUIREMENTS:
            self.assertIn(r.kind, ("dir", "copy", "scaffold", "manual"),
                          f"{r.path} declares an unknown kind {r.kind}")


# --------------------------------------------------------------------------
class TestApply(DoctorCase):
    def test_directories_are_created(self):
        apply_fixes(self.project, check(self.project), self.plugin)
        self.assertTrue((self.project / ".claude/concepts").is_dir())
        self.assertTrue((self.project / ".claude/work-items").is_dir())

    def test_a_template_is_copied_from_the_plugin(self):
        apply_fixes(self.project, check(self.project), self.plugin)
        got = self.project / ".claude/templates/concept-contract.md"
        self.assertTrue(got.is_file())
        self.assertEqual(got.read_text(encoding="utf-8"), "# Concept Contract\n")

    def test_an_existing_file_is_never_overwritten(self):
        (self.project / ".claude/templates").mkdir(parents=True)
        mine = self.project / ".claude/templates/concept-contract.md"
        mine.write_text("MINE - DO NOT TOUCH", encoding="utf-8")
        # Pass the FULL requirement list, not check()'s filtered one. check() would
        # drop this file for already existing, so filtering it would test the filter
        # rather than the guard inside apply_fixes.
        apply_fixes(self.project, list(REQUIREMENTS), self.plugin)
        self.assertEqual(mine.read_text(encoding="utf-8"), "MINE - DO NOT TOUCH",
                         "apply_fixes must refuse an existing target even when handed one")

    def test_check_also_filters_an_existing_file(self):
        (self.project / ".claude/templates").mkdir(parents=True)
        (self.project / ".claude/templates/concept-contract.md").write_text("x", encoding="utf-8")
        self.assertNotIn(".claude/templates/concept-contract.md",
                         [r.path for r in check(self.project)])

    def test_a_scaffolded_json_file_is_valid_json(self):
        apply_fixes(self.project, check(self.project), self.plugin)
        for name in ("area-mapping.json", "work-item-conventions.json"):
            f = self.project / ".claude" / name
            if f.is_file():
                json.loads(f.read_text(encoding="utf-8"))

    def test_the_report_says_what_it_did_and_what_it_left(self):
        report = apply_fixes(self.project, check(self.project), self.plugin)
        self.assertIn("created", report)
        self.assertIn("needs_authoring", report)

    def test_nothing_is_created_when_the_plugin_source_is_absent(self):
        empty = self.tmp / "no-plugin"
        empty.mkdir()
        report = apply_fixes(self.project, check(self.project), empty)
        self.assertFalse((self.project / ".claude/templates/concept-contract.md").is_file())
        self.assertTrue(report["unresolved"],
                        "a copy whose source is missing must be reported, not silently skipped")


# --------------------------------------------------------------------------
class TestAuthoredFiles(DoctorCase):
    """A file describing the project must never be silently invented."""

    def test_the_profile_is_scaffolded_but_flagged_as_needing_authoring(self):
        report = apply_fixes(self.project, check(self.project), self.plugin)
        self.assertIn(".claude/project-profile.md", report["needs_authoring"])

    def test_the_scaffolded_profile_keeps_the_placeholders_visible(self):
        apply_fixes(self.project, check(self.project), self.plugin)
        text = (self.project / ".claude/project-profile.md").read_text(encoding="utf-8")
        self.assertIn("*(", text, "placeholders must survive so the loop reads the slot as unfilled")

    #: Names belonging to the originating project. None may appear in anything the
    #: doctor writes into a different repository.
    #:
    #: An agent the plugin actually ships is NOT a leak - naming one in a worked
    #: example is the point of a template. Only a name the plugin does not ship is,
    #: because a consuming project would inherit a handoff block addressed to an
    #: agent that does not exist for it.
    LEAKS = ("ScalpingMachine", "ClientApp", "scalping-machine", "admin-panel",
             "ingestion-data-architect", "llm-training-engineer", "pinescript-developer",
             "ibkr", "Alpaca")

    def test_no_file_the_doctor_writes_leaks_a_project_specific_value(self):
        report = apply_fixes(self.project, check(self.project), self.plugin)
        checked = 0
        for rel in report["created"]:
            f = self.project / rel
            if not f.is_file():
                continue
            checked += 1
            text = f.read_text(encoding="utf-8", errors="replace")
            for leaked in self.LEAKS:
                self.assertNotIn(leaked.lower(), text.lower(),
                                 f"{rel} carries '{leaked}' from the originating project")
        self.assertGreater(checked, 0, "the scan must actually have read some files")

    def test_the_scan_would_catch_a_leak_if_one_existed(self):
        # Positive control. Without this, the scan above could pass by reading nothing
        # useful, which is how a leak test quietly stops testing.
        planted = self.project / ".claude/planted.md"
        planted.parent.mkdir(parents=True, exist_ok=True)
        planted.write_text("built for ScalpingMachine", encoding="utf-8")
        text = planted.read_text(encoding="utf-8")
        self.assertTrue(any(l.lower() in text.lower() for l in self.LEAKS),
                        "the leak list must match a known leak")

    def test_settings_is_manual_and_never_written(self):
        kinds = {r.path: r.kind for r in REQUIREMENTS}
        self.assertEqual(kinds.get(".claude/settings.json"), "manual",
                         "registering hooks turns on enforcement; that is the operator's call")
        report = apply_fixes(self.project, list(REQUIREMENTS), self.plugin)
        self.assertFalse((self.project / ".claude/settings.json").exists())
        self.assertIn(".claude/settings.json", report["left_to_you"],
                      "a manual requirement must be reported, not silently dropped")

    def test_a_manual_requirement_is_never_created_even_with_a_source(self):
        # A positive control: give the manual entry everything a copy would need,
        # and it must still not be written.
        sneaky = Requirement(".claude/settings.json", "manual", "x",
                             source=".claude/templates/concept-contract.md")
        report = apply_fixes(self.project, [sneaky], self.plugin)
        self.assertFalse((self.project / ".claude/settings.json").exists())
        self.assertEqual(report["created"], [])


class TestScaffolds(DoctorCase):
    def test_every_scaffold_requirement_has_content_to_write(self):
        for r in REQUIREMENTS:
            if r.kind == "scaffold":
                self.assertIsNotNone(scaffold_for(r.path),
                                     f"{r.path} is scaffolded but has no content defined")



class TestTheRealPluginTree(unittest.TestCase):
    """The tests above prove the mechanism. This one proves the actual content.

    A fake plugin tree cannot catch a name leaking in the real template, because the
    fake one is clean by construction. Without this, the leak test passes while the
    thing it exists to protect is dirty.
    """

    #: Only a name the plugin does not ship counts. An agent it does ship is a
    #: legitimate worked example.
    NOT_SHIPPED = ("ingestion-data-architect", "llm-training-engineer",
                   "pinescript-developer", "ScalpingMachine", "ClientApp")

    def _plugin_root(self):
        """The plugin's own checkout, never a vendored copy.

        find_plugin_root deliberately prefers the vendored copy, because that is
        what a consuming project should use. Here we want the source of truth, so
        we look for a checkout that is the plugin rather than one that embeds it.
        """
        import os
        env = os.environ.get("AGENTIC_PLUGIN_ROOT")
        candidates = [Path(env)] if env else []
        here = Path(__file__).resolve()
        # The plugin is a SIBLING of this repository, so search the parent of the
        # repository root as well as the root itself.
        for level in (3, 4):
            if level < len(here.parents):
                candidates += list(here.parents[level].glob("claude-agentic-auto-improve"))
        for c in candidates:
            if (c / "plugin.json").is_file() and (c / ".claude/templates").is_dir():
                return c
        return None

    def test_the_files_a_project_copies_carry_no_unshipped_name(self):
        root = self._plugin_root()
        if root is None:
            self.skipTest("the plugin checkout is not beside this repository")
        from plugin_doctor import REQUIREMENTS
        checked = 0
        for r in REQUIREMENTS:
            if not r.source:
                continue
            f = root / r.source
            if not f.is_file():
                continue
            checked += 1
            text = f.read_text(encoding="utf-8", errors="replace")
            for name in self.NOT_SHIPPED:
                self.assertNotIn(name, text,
                                 f"{r.source} names '{name}', which the plugin does not ship; "
                                 f"every consuming project would inherit it")
        self.assertGreater(checked, 0, "the scan must have read at least one real source file")

if __name__ == "__main__":
    unittest.main(verbosity=2)
