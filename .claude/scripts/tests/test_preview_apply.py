#!/usr/bin/env python3
"""
Tests for _preview_apply.py: the preview-hash apply helpers shared by finish-install and registry_migrate.

Run: py -3 .claude/scripts/tests/test_preview_apply.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

import _preview_apply  # noqa: E402


def _tree(root: Path) -> dict:
    return {str(p.relative_to(root)).replace("\\", "/"): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file()}


class ExtractionTests(unittest.TestCase):
    def test_finish_install_names_are_the_moved_objects(self):
        import auto_improve_finish_install as fi
        self.assertIs(fi._plan_digest, _preview_apply._plan_digest)
        self.assertIs(fi._atomic_write, _preview_apply._atomic_write)

    def test_clean_process_import_changes_no_sys_state(self):
        code = (
            "import sys\n"
            "before = (sys.dont_write_bytecode, list(sys.path))\n"
            "sys.path.insert(0, %r); before = (sys.dont_write_bytecode, list(sys.path))\n"
            "import _preview_apply\n"
            "assert (sys.dont_write_bytecode, list(sys.path)) == before, 'sys state changed'\n"
            % str(SCRIPTS_DIR))
        done = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_plan_digest_is_length_prefixed(self):
        self.assertNotEqual(_preview_apply._plan_digest(b"ab", b"c"), _preview_apply._plan_digest(b"a", b"bc"))
        self.assertEqual(len(_preview_apply._plan_digest(b"x")), 64)

    def test_atomic_write_creates_and_replaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a" / "f.txt"
            self.assertIsNone(_preview_apply._atomic_write(target, b"one"))
            self.assertIsNone(_preview_apply._atomic_write(target, b"two"))
            self.assertEqual(target.read_bytes(), b"two")
            self.assertEqual([p.name for p in target.parent.iterdir()], ["f.txt"])


class _StageCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir()
        self.backup = Path(self._tmp.name) / "report" / "backup"
        self.t1 = self.root / "reg" / "one.md"
        self.t2 = self.root / "reg" / "two.md"
        self.t3 = self.root / "reg" / "new.md"  # does not exist yet
        self.t1.parent.mkdir()
        self.t1.write_bytes(b"old one")
        self.t2.write_bytes(b"old two")
        self.writes = [(self.t1, b"new one"), (self.t2, b"new two"), (self.t3, b"new three")]


class StageAndReplaceTests(_StageCase):
    def test_success_replaces_all_and_backs_up_existing(self):
        result = _preview_apply.stage_and_replace(self.writes, self.backup)
        self.assertNotEqual(result.get("status"), "refused", result)
        self.assertEqual(self.t1.read_bytes(), b"new one")
        self.assertEqual(self.t2.read_bytes(), b"new two")
        self.assertEqual(self.t3.read_bytes(), b"new three")
        backed = [p for p in self.backup.rglob("*") if p.is_file()]
        self.assertEqual(sorted(p.read_bytes() for p in backed), [b"old one", b"old two"])
        self.assertEqual([p for p in self.root.rglob("*") if ".stage-" in p.name], [])

    def test_backups_land_only_in_backup_dir(self):
        before = set(_tree(self.root))
        _preview_apply.stage_and_replace(self.writes, self.backup)
        after = set(_tree(self.root))
        self.assertEqual(after - before, {"reg/new.md"})
        self.assertFalse([n for n in after if "backup" in n or ".bak" in n])

    def test_staging_failure_touches_no_target(self):
        before = _tree(self.root)
        real_open = open
        calls = {"n": 0}

        def flaky(path, *a, **k):
            if ".stage-" in os.path.basename(str(path)):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise OSError("disk full")
            return real_open(path, *a, **k)

        with mock.patch("builtins.open", flaky):
            result = _preview_apply.stage_and_replace(self.writes, self.backup)
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["code"], "write-failed")
        self.assertEqual(_tree(self.root), before)
        self.assertFalse(self.backup.exists() and [p for p in self.backup.rglob("*") if p.is_file()])

    def test_replace_failure_on_second_restores_first_and_deletes_created(self):
        # Order the created file first so it is "already replaced" when the 2nd replace fails.
        writes = [(self.t3, b"new three"), (self.t1, b"new one"), (self.t2, b"new two")]
        before = _tree(self.root)
        real_replace = os.replace
        calls = {"n": 0}

        def flaky(src, dst):
            if ".stage-" in os.path.basename(str(src)):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise OSError("locked")
            return real_replace(src, dst)

        with mock.patch("os.replace", flaky):
            result = _preview_apply.stage_and_replace(writes, self.backup)
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["code"], "write-failed")
        self.assertEqual(_tree(self.root), before)

    def test_replace_failure_on_second_of_three_restores_first(self):
        before = _tree(self.root)
        real_replace = os.replace
        calls = {"n": 0}

        def flaky(src, dst):
            if ".stage-" in os.path.basename(str(src)):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise OSError("locked")
            return real_replace(src, dst)

        with mock.patch("os.replace", flaky):
            result = _preview_apply.stage_and_replace(self.writes, self.backup)
        self.assertEqual(result["code"], "write-failed")
        self.assertEqual(_tree(self.root), before)
        self.assertEqual(self.t1.read_bytes(), b"old one")


class BackupLayoutTests(_StageCase):
    """W2: backups land under backup_dir / target.relative_to(base); N3: folders the run created are removed again."""

    def test_backup_path_is_backup_dir_joined_with_the_path_relative_to_base(self):
        result = _preview_apply.stage_and_replace(self.writes, self.backup, base=self.root)
        self.assertNotEqual(result.get("status"), "refused", result)
        self.assertEqual((self.backup / "reg" / "one.md").read_bytes(), b"old one")
        self.assertEqual((self.backup / "reg" / "two.md").read_bytes(), b"old two")
        self.assertEqual(sorted(str(p.relative_to(self.backup)).replace("\\", "/")
                                for p in self.backup.rglob("*") if p.is_file()), ["reg/one.md", "reg/two.md"])

    def test_base_defaults_to_the_common_parent_folder_of_the_targets(self):
        result = _preview_apply.stage_and_replace(self.writes, self.backup)
        self.assertNotEqual(result.get("status"), "refused", result)
        self.assertEqual(sorted(p.name for p in self.backup.rglob("*") if p.is_file()), ["one.md", "two.md"])
        self.assertTrue((self.backup / "one.md").is_file())

    def test_a_deep_checkout_stays_under_max_path_with_the_relative_layout(self):
        deep_root = self.root / ("d" * 40) / ("e" * 40)
        backup = deep_root / ".claude" / "cache" / "registry-migrations" / "20261106T000000Z" / "backup"
        target = deep_root / ".claude" / "registries" / "VOCABULARY" / "general.md"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"old")
        old_rule = backup / Path(*Path(os.path.abspath(str(target))).parts[1:])
        self.assertGreater(len(str(old_rule)), 260)
        result = _preview_apply.stage_and_replace([(target, b"new")], backup, base=deep_root)
        self.assertNotEqual(result.get("status"), "refused", result)
        copy = backup / ".claude" / "registries" / "VOCABULARY" / "general.md"
        self.assertLess(len(str(copy)), 260)
        self.assertEqual(copy.read_bytes(), b"old")

    def test_a_target_outside_base_is_write_failed_before_any_stage_file(self):
        outside = Path(self._tmp.name) / "elsewhere" / "x.md"
        outside.parent.mkdir()
        outside.write_bytes(b"outside")
        before = _tree(Path(self._tmp.name))
        result = _preview_apply.stage_and_replace([(self.t1, b"new one"), (outside, b"new")], self.backup,
                                                  base=self.root)
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["code"], "write-failed")
        self.assertEqual(_tree(Path(self._tmp.name)), before)

    def test_a_folder_made_by_a_failed_run_is_removed_and_an_existing_one_stays(self):
        new_dir = self.root / "NEWREG"
        writes = [(new_dir / "general.md", b"new"), (self.t1, b"new one"), (self.t2, b"new two")]
        real_replace = os.replace
        calls = {"n": 0}

        def flaky(src, dst):
            if ".stage-" in os.path.basename(str(src)):
                calls["n"] += 1
                if calls["n"] == 2:
                    raise OSError("locked")
            return real_replace(src, dst)

        with mock.patch("os.replace", flaky):
            result = _preview_apply.stage_and_replace(writes, self.backup, base=self.root)
        self.assertEqual(result["code"], "write-failed")
        self.assertFalse(new_dir.exists())
        self.assertTrue(self.t1.parent.is_dir())

    def test_a_folder_made_before_a_staging_failure_is_removed(self):
        new_dir = self.root / "NEWREG"
        writes = [(new_dir / "general.md", b"new"), (self.t1, b"new one")]
        real_open = open

        def flaky(path, *a, **k):
            if ".stage-" in os.path.basename(str(path)) and os.path.basename(str(path)).startswith(".one"):
                raise OSError("disk full")
            return real_open(path, *a, **k)

        with mock.patch("builtins.open", flaky):
            result = _preview_apply.stage_and_replace(writes, self.backup, base=self.root)
        self.assertEqual(result["code"], "write-failed")
        self.assertFalse(new_dir.exists())
        self.assertTrue(self.t1.parent.is_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)
