#!/usr/bin/env python3
"""test_memory_pager.py -- pins memory-pager.py's handling of a missing or broken memory-blocks.json.

Contract: .claude/concepts/2026-11-11-audit-followups-165.md (V7, I-4, Option E).

I-4: when no ``claude_roots()`` rank holds ``memory-blocks.json``, the pager writes no log record and
exits 0. A file at ANY rank is found and read. Any other load failure still logs ``config-load-failed``.

The suite copies the hook and its helpers into ``<tmp>/self/.claude/hooks/`` so that ``SELF_ROOT`` is
temporary, and runs the hook by subprocess with CLAUDE_PROJECT_DIR, cwd, HOME and USERPROFILE all
temporary and distinct, and an existing log folder. The four ranks are therefore:

    project  <tmp>/project/.claude
    self     <tmp>/self/.claude        (SELF_ROOT)
    cwd      <tmp>/cwd/.claude
    home     <tmp>/home/.claude

Run:
    py -3 .claude/hooks/tests/test_memory_pager.py
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

HERE = Path(__file__).resolve().parent
HOOKS_DIR = HERE.parent
HELPERS = ("memory-pager.py", "_memory_common.py", "_project_paths.py", "_error_log.py")
CONFIG_NAME = "memory-blocks.json"
RANKS = ("project", "self", "cwd", "home")
MALFORMED = "{ this is not json"


class PagerCase(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="mempager-test-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.dirs = {r: self.tmp / r for r in RANKS}
        for rank, base in self.dirs.items():
            (base / ".claude").mkdir(parents=True)
        hooks = self.dirs["self"] / ".claude" / "hooks"
        hooks.mkdir()
        for name in HELPERS:
            shutil.copy2(HOOKS_DIR / name, hooks / name)
        self.hook = hooks / "memory-pager.py"
        self.logs = self.dirs["project"] / ".claude" / "logs"
        self.logs.mkdir()

    def config_at(self, rank: str) -> Path:
        return self.dirs[rank] / ".claude" / CONFIG_NAME

    def run_hook(self, **extra_env: str) -> subprocess.CompletedProcess:
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_")}
        env.update(
            CLAUDE_PROJECT_DIR=str(self.dirs["project"]),
            HOME=str(self.dirs["home"]),
            USERPROFILE=str(self.dirs["home"]),
        )
        env.update(extra_env)
        return subprocess.run(
            [sys.executable, str(self.hook)],
            input="{}", text=True, capture_output=True, env=env,
            cwd=str(self.dirs["cwd"]), timeout=60,
        )

    def events(self) -> list[str]:
        log = self.logs / "errors.jsonl"
        if not log.exists():
            return []
        return [json.loads(line)["event"] for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_absent_at_all_four_ranks_logs_nothing(self) -> None:
        for rank in RANKS:
            self.assertFalse(self.config_at(rank).exists())
        proc = self.run_hook()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("config-load-failed", self.events())
        self.assertEqual(self.events(), [])

    def test_malformed_decoy_at_each_rank_logs(self) -> None:
        for rank in RANKS:
            with self.subTest(rank=rank):
                self.config_at(rank).write_text(MALFORMED, encoding="utf-8")
                try:
                    proc = self.run_hook()
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertIn("config-load-failed", self.events())
                finally:
                    self.config_at(rank).unlink()
                    shutil.rmtree(self.logs)
                    self.logs.mkdir()

    def test_folder_in_the_files_place_logs(self) -> None:
        self.config_at("project").mkdir()
        proc = self.run_hook()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("config-load-failed", self.events())

    def test_bypass_env_logs_nothing(self) -> None:
        self.config_at("self").write_text(MALFORMED, encoding="utf-8")
        proc = self.run_hook(CLAUDE_MEMORY_PAGER="off")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.events(), [])


if __name__ == "__main__":
    unittest.main()
