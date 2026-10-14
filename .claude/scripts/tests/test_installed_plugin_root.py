#!/usr/bin/env python3
"""
Tests for installed_plugin_root() -- the one locator for "the plugin version this project runs".

Contract: .claude/concepts/2026-10-12-dedupe-claude-config.md in the consuming repository, Business
Concept ("Installed plugin root") and Reused Mechanisms ("Two-layer Claude path resolution").

The order, fixed:
  1. the folder named by CLAUDE_PLUGIN_ROOT;
  2. the installPath that installed_plugins.json records: an entry scoped to THIS project first
     (the project path compared with case and slashes folded), then the user-scope entry;
  3. the newest version folder in the plugin cache, compared as numbers (never alphabetically).
A recorded path that no longer exists falls through to the next step. A folder whose name is not a
version is ignored. CLAUDE_CONFIG_DIR is honoured, otherwise the home .claude is read. Nothing found
gives None.

The function lives in .claude/hooks/_project_paths.py and is re-exported by
.claude/scripts/_claude_paths.py (the scripts-side bridge).

Every test builds its own throwaway "Claude config directory" and never reads the real one.
A symbol that does not exist yet fails the test with a message that names it (RED for a missing
symbol is a failing test, not an import crash that hides the rest of the file).

Run: py -3 .claude/scripts/tests/test_installed_plugin_root.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
HOOKS_DIR = SCRIPTS_DIR.parent / "hooks"
PLUGIN_NAME = "agentic-auto-improve"
KEY = PLUGIN_NAME + "@auto-improve"

for _p in (str(HOOKS_DIR), str(SCRIPTS_DIR)):
    if _p not in sys.path:
        sys.path.append(_p)

import _project_paths  # noqa: E402


def _norm(path) -> str:
    return os.path.normcase(os.path.realpath(str(path)))


def _resolver(module=_project_paths):
    fn = getattr(module, "installed_plugin_root", None)
    if fn is None:
        raise AssertionError("%s.installed_plugin_root does not exist yet (missing symbol)" % module.__name__)
    return fn


class RootCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="plugin-root-"))
        self.config = self.tmp / "claude-config"
        self.project = self.tmp / "work" / "My Project"
        self.project.mkdir(parents=True)
        self.config.mkdir()
        self.plugin_env = None
        self._patch = None

    def tearDown(self):
        if self._patch:
            self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------- builders
    def version_dir(self, name: str, market: str = "auto-improve") -> Path:
        """A cache version folder that looks like a real plugin install."""
        d = self.config / "plugins" / "cache" / market / PLUGIN_NAME / name
        (d / ".claude-plugin").mkdir(parents=True, exist_ok=True)
        (d / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": PLUGIN_NAME}), encoding="utf-8")
        (d / ".claude" / "templates").mkdir(parents=True, exist_ok=True)
        (d / ".claude" / "templates" / "concept-contract.md").write_text("# contract\n", encoding="utf-8")
        return d

    def record(self, entries: dict) -> None:
        plugins = self.config / "plugins"
        plugins.mkdir(parents=True, exist_ok=True)
        (plugins / "installed_plugins.json").write_text(
            json.dumps({"version": 2, "plugins": entries}, indent=2), encoding="utf-8")

    @staticmethod
    def entry(scope: str, install: Path | str, project: str | None = None, version: str = "x") -> dict:
        e = {"scope": scope, "installPath": str(install), "version": version}
        if project is not None:
            e["projectPath"] = project
        return e

    def env(self, **extra):
        base = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
        base["CLAUDE_CONFIG_DIR"] = str(self.config)
        base["CLAUDE_PROJECT_DIR"] = str(self.project)
        base.update(extra)
        return base

    def resolve(self, **extra):
        env = self.env(**extra)
        env = {k: v for k, v in env.items() if v is not None}
        with mock.patch.dict(os.environ, env, clear=True):
            return _resolver()()

    def assertRoot(self, got, expected: Path, msg: str):
        self.assertIsNotNone(got, msg + " (got None)")
        self.assertEqual(_norm(got), _norm(expected), msg)


class TestResolutionOrder(RootCase):
    def test_the_plugin_root_environment_variable_wins_over_everything(self):
        mine = self.version_dir("0.1.0", market="elsewhere")
        newest = self.version_dir("9.9.9")
        self.record({KEY: [self.entry("user", newest, version="9.9.9")]})
        self.assertRoot(self.resolve(CLAUDE_PLUGIN_ROOT=str(mine)), mine,
                        "CLAUDE_PLUGIN_ROOT names the running version and beats the record and the cache")

    def test_the_project_scope_entry_for_this_project_beats_the_user_scope_entry(self):
        user, scoped = self.version_dir("0.8.1"), self.version_dir("0.7.1")
        self.record({KEY: [self.entry("user", user), self.entry("project", scoped, str(self.project))]})
        self.assertRoot(self.resolve(), scoped, "an entry scoped to THIS project is the first recorded choice")

    def test_the_project_path_is_compared_with_case_and_slashes_folded(self):
        user, scoped = self.version_dir("0.8.1"), self.version_dir("0.7.1")
        spelled = str(self.project).replace("/", "\\").upper()
        self.record({KEY: [self.entry("user", user), self.entry("project", scoped, spelled)]})
        self.assertRoot(self.resolve(CLAUDE_PROJECT_DIR=str(self.project).replace("\\", "/").lower()), scoped,
                        "a project path spelled with other slashes and other letter case is still this project")

    def test_a_project_scope_entry_for_another_project_is_ignored(self):
        user, other = self.version_dir("0.8.1"), self.version_dir("0.7.1")
        self.record({KEY: [self.entry("project", other, str(self.tmp / "work" / "Another")),
                           self.entry("user", user)]})
        self.assertRoot(self.resolve(), user, "an entry scoped to a different project must not be used")

    def test_a_project_scope_entry_of_another_plugin_is_ignored(self):
        user, foreign = self.version_dir("0.8.1"), self.version_dir("0.7.1", market="other")
        self.record({"superpowers@other": [self.entry("project", foreign, str(self.project))],
                     KEY: [self.entry("user", user)]})
        self.assertRoot(self.resolve(), user, "only this plugin's entries are read")

    def test_the_user_scope_entry_is_used_when_no_project_entry_matches(self):
        user, newest = self.version_dir("0.8.1"), self.version_dir("0.10.0")
        self.record({KEY: [self.entry("user", user)]})
        self.assertRoot(self.resolve(), user,
                        "the recorded installPath is the plugin Claude Code runs, even when a newer folder sits in the cache")

    def test_a_recorded_path_that_is_missing_falls_through_to_the_next_entry(self):
        user = self.version_dir("0.8.1")
        self.record({KEY: [self.entry("project", self.config / "gone" / "0.7.1", str(self.project)),
                           self.entry("user", user)]})
        self.assertRoot(self.resolve(), user, "a project entry whose folder was deleted falls through to the user entry")

    def test_every_recorded_path_missing_falls_through_to_the_newest_cache_folder(self):
        newest = self.version_dir("0.9.0")
        self.version_dir("0.2.0")
        self.record({KEY: [self.entry("user", self.config / "gone" / "0.8.1")]})
        self.assertRoot(self.resolve(), newest, "with no usable record the cache decides")

    def test_a_malformed_record_file_falls_through_to_the_cache(self):
        newest = self.version_dir("0.9.0")
        (self.config / "plugins").mkdir(parents=True, exist_ok=True)
        (self.config / "plugins" / "installed_plugins.json").write_text("{ not json", encoding="utf-8")
        self.assertRoot(self.resolve(), newest, "an unreadable record must not stop the lookup")


class TestCacheOrder(RootCase):
    def test_versions_compare_as_numbers_so_0_10_0_beats_0_8_1_and_0_3_1(self):
        for v in ("0.3.1", "0.8.1", "0.10.0"):
            self.version_dir(v)
        self.assertRoot(self.resolve(), self.config / "plugins" / "cache" / "auto-improve" / PLUGIN_NAME / "0.10.0",
                        "0.10.0 is the newest; an alphabetical sort would pick 0.8.1 or 0.3.1")

    def test_a_folder_whose_name_is_not_a_version_is_ignored(self):
        self.version_dir("0.8.1")
        self.version_dir("latest")
        self.version_dir("backup")
        self.assertRoot(self.resolve(), self.config / "plugins" / "cache" / "auto-improve" / PLUGIN_NAME / "0.8.1",
                        "'latest' and 'backup' sort after digits alphabetically but are not versions")

    def test_nothing_found_gives_none(self):
        (self.config / "plugins").mkdir(parents=True, exist_ok=True)
        self.assertIsNone(self.resolve(), "with no variable, no record and no cache folder there is no installed root")


class TestConfigDirectory(RootCase):
    def test_claude_config_dir_is_honoured_over_the_home_directory(self):
        home = self.tmp / "home"
        decoy = home / ".claude" / "plugins" / "cache" / "auto-improve" / PLUGIN_NAME / "9.0.0"
        decoy.mkdir(parents=True)
        mine = self.version_dir("0.8.1")
        env = {k: v for k, v in self.env(HOME=str(home), USERPROFILE=str(home)).items() if v is not None}
        code = ("import sys; sys.path.append(%r); import _project_paths as p; r = p.installed_plugin_root(); "
                "print('' if r is None else r)" % str(HOOKS_DIR))
        out = subprocess.run([sys.executable, "-B", "-c", code], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, "the call must not raise: " + out.stderr[-400:])
        self.assertEqual(_norm(out.stdout.strip()), _norm(mine),
                         "CLAUDE_CONFIG_DIR names the config directory; the home one is not read")

    def test_without_claude_config_dir_the_home_dot_claude_is_read(self):
        home = self.tmp / "home"
        newest = home / ".claude" / "plugins" / "cache" / "auto-improve" / PLUGIN_NAME / "0.4.0"
        (newest / ".claude-plugin").mkdir(parents=True)
        (newest / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": PLUGIN_NAME}), encoding="utf-8")
        env = {k: v for k, v in self.env(HOME=str(home), USERPROFILE=str(home)).items() if v is not None}
        env.pop("CLAUDE_CONFIG_DIR", None)
        code = ("import sys; sys.path.append(%r); import _project_paths as p; r = p.installed_plugin_root(); "
                "print('' if r is None else r)" % str(HOOKS_DIR))
        out = subprocess.run([sys.executable, "-B", "-c", code], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, "the call must not raise: " + out.stderr[-400:])
        self.assertEqual(_norm(out.stdout.strip()), _norm(newest),
                         "with no CLAUDE_CONFIG_DIR the home .claude is the config directory")


class TestScriptsSideBridge(RootCase):
    def test_claude_paths_re_exports_the_same_resolver(self):
        import _claude_paths
        newest = self.version_dir("0.9.0")
        env = self.env()
        with mock.patch.dict(os.environ, env, clear=True):
            via_bridge = _resolver(_claude_paths)()
        self.assertRoot(via_bridge, newest, "_claude_paths.installed_plugin_root answers like the hooks-side one")
        self.assertIn("installed_plugin_root", getattr(_claude_paths, "__all__", []),
                      "the bridge lists the new name in __all__ with its other re-exports")


if __name__ == "__main__":
    unittest.main(verbosity=2)
