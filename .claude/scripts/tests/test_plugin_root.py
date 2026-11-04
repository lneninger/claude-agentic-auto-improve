#!/usr/bin/env python3
"""
Tests for _plugin_root.py: the guarded plugin-root lookup shared by finish-install and the registry tools.

Run: py -3 .claude/scripts/tests/test_plugin_root.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import _plugin_root  # noqa: E402

MOVED = ("_same_dir", "_norm", "_manifest_names_plugin", "_load_json_lenient", "_claude_home",
         "_version_key", "_cache_roots", "PLUGIN_NAME")


def _make_plugin(root: Path, name: str = "agentic-auto-improve") -> Path:
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    return root


class ExtractionTests(unittest.TestCase):
    def test_finish_install_names_are_the_moved_objects(self):
        import auto_improve_finish_install as fi
        for name in MOVED:
            self.assertIs(getattr(fi, name), getattr(_plugin_root, name), name)
        self.assertIs(fi._separate_plugin_root, _plugin_root._separate_plugin_root)
        self.assertIs(_plugin_root.separate_plugin_root, _plugin_root._separate_plugin_root)

    def test_clean_process_import_changes_no_sys_state(self):
        code = (
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "before = (sys.dont_write_bytecode, list(sys.path))\n"
            "import _plugin_root\n"
            "assert (sys.dont_write_bytecode, list(sys.path)) == before, 'sys state changed'\n"
            "assert 'plugin_doctor' not in sys.modules, 'plugin_doctor imported at module level'\n"
            % str(SCRIPTS_DIR))
        done = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class SeparatePluginRootTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        # Keep ambient configuration out of the lookup.
        env = mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.home)})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CLAUDE_PLUGIN_ROOT", None)

    def _vendored_project(self) -> Path:
        project = self.base / "project"
        (project / ".claude" / "templates").mkdir(parents=True)
        (project / ".claude" / "templates" / "project-profile.md").write_text("t", encoding="utf-8")
        (project / ".claude" / "scripts").mkdir(parents=True)
        (project / ".claude" / "scripts" / "x.py").write_text("", encoding="utf-8")
        _make_plugin(project)
        return project

    def test_the_projects_own_tree_is_rejected(self):
        project = self._vendored_project()
        # The module's own-copy candidate is the real checkout; point it at the project instead.
        with mock.patch.object(_plugin_root, "_SCRIPTS_DIR", str(project / ".claude" / "scripts")):
            self.assertIsNone(_plugin_root.separate_plugin_root(project, None, self.home))

    def test_a_cache_copy_with_the_manifest_is_returned(self):
        project = self._vendored_project()
        cache = _make_plugin(self.home / "plugins" / "cache" / "mkt" / "agentic-auto-improve" / "1.2.3")
        with mock.patch.object(_plugin_root, "_SCRIPTS_DIR", str(project / ".claude" / "scripts")):
            found = _plugin_root.separate_plugin_root(project, None, self.home)
        self.assertIsNotNone(found)
        self.assertTrue(_plugin_root._same_dir(found, cache))

    def test_an_override_equal_to_the_project_is_none(self):
        project = self._vendored_project()
        self.assertIsNone(_plugin_root.separate_plugin_root(project, project, self.home))

    def test_an_override_naming_another_plugin_is_none(self):
        project = self._vendored_project()
        other = _make_plugin(self.base / "other", name="not-this-plugin")
        self.assertIsNone(_plugin_root.separate_plugin_root(project, other, self.home))

    def test_an_override_naming_this_plugin_is_returned(self):
        project = self._vendored_project()
        other = _make_plugin(self.base / "elsewhere")
        found = _plugin_root.separate_plugin_root(project, other, self.home)
        self.assertTrue(_plugin_root._same_dir(found, other))

    def test_newest_cache_version_wins(self):
        names = [Path("1.2.10"), Path("1.2.9")]
        self.assertEqual(sorted(names, key=_plugin_root._version_key, reverse=True)[0], Path("1.2.10"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
