#!/usr/bin/env python3
"""
Tests for the journal post-approval tracker (hook journal-post-approval-tracker.py, logic in
accuracy_update.process_journal_change), contract 2026-11-04-domain-split-registries, Event "Journal entry
appended" and invariant I-14.

Every test runs the hook (or registry_append.py) as a subprocess against a temporary project. HOME and USERPROFILE
point at a temporary folder, so the machine-wide seen cache of the real machine is never read or written. A "fire" is
a row with source `post-approval-journal` in the project's own contract-accuracy.json.

Run: py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py
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

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / ".claude" / "hooks" / "journal-post-approval-tracker.py"
APPEND = ROOT / ".claude" / "scripts" / "registry_append.py"
MARK = "<!-- registry-layout: 2 -->"

CONTRACT = "# C\n\n**Status:** approved\n\n**Files to touch:**\n\n- `web/app/thing.ts`\n"
ROOT_JOURNAL = (MARK + "\n# Journal\n\n> header\n\n## Universal\n\n"
                "### 2026-01-01 — An old universal lesson\n- **Trigger:** manual\n- **Source contract:** N/A\n"
                "- **Lesson:** l\n- **Apply when:** a\n- **Tags:** t\n\n"
                "## Project tier\n\nThis file holds only the Universal tier.\n")


def entry(title: str, trigger: str, contract: Path | None, date: str = "2026-11-04") -> str:
    source = f"`{contract.as_posix()}`" if contract else "N/A"
    return (f"### {date} — {title}\n- **Trigger:** {trigger}\n- **Source contract:** {source}\n"
            f"- **Lesson:** l\n- **Apply when:** a thing happens\n- **Tags:** t\n")


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def append_text(path: Path, text: str) -> None:
    path.write_bytes(path.read_bytes() + b"\n" + text.encode("utf-8"))


class Project:
    """One checkout (the main one, or a worktree of it) with its registries, ledger and area map."""

    def __init__(self, base: Path, home: Path):
        self.base = base
        self.home = home
        self.regs = base / ".claude" / "registries"
        self.contract = base / ".claude" / "concepts" / "2026-11-04-probe.md"
        write(self.contract, CONTRACT)
        write(base / ".claude" / "contract-accuracy.json", '{"schema_version": 1, "areas": {}}')
        write(base / ".claude" / "area-mapping.json", json.dumps({"areas": {"frontend": {"patterns": ["web/"]}}}))
        write(self.regs / "JOURNAL.md", ROOT_JOURNAL)
        for name in ("MECHANISMS", "VOCABULARY"):
            write(self.regs / f"{name}.md", f"{MARK}\n# {name.title()}\n\n## Universal\n\n"
                  + "## Project tier\n\nThis file holds only the Universal tier.\n")
            write(self.regs / name / "general.md", f"# {name} - general\n\n")
        write(self.regs / "JOURNAL" / "general.md", "# Journal - general\n\n> header\n")
        write(self.regs / "JOURNAL" / "frontend.md", "# Journal - frontend\n\n> header\n")

    def env(self) -> dict:
        e = dict(os.environ)
        e.pop("CLAUDE_ACCURACY_TRACKER", None)
        e.update({"CLAUDE_PROJECT_DIR": str(self.base), "HOME": str(self.home), "USERPROFILE": str(self.home),
                  "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
        return e

    def hook(self, path: Path, tool: str = "Edit", extra_env: dict | None = None, hook: Path = HOOK):
        payload = json.dumps({"tool_name": tool, "tool_input": {"file_path": str(path)}}).encode("utf-8")
        env = self.env()
        env.update(extra_env or {})
        return subprocess.run([sys.executable, str(hook)], input=payload, capture_output=True, env=env,
                              cwd=str(self.base), timeout=120)

    def append(self, registry: str, text: str, *extra: str) -> subprocess.CompletedProcess:
        src = self.base.parent / "entry-input.md"
        src.write_bytes(text.encode("utf-8"))
        return subprocess.run([sys.executable, str(APPEND), "--project", str(self.base), "--registry", registry,
                               "--from-file", str(src), *extra], capture_output=True, env=self.env(),
                              cwd=str(self.base), timeout=120)

    def fires(self) -> int:
        data = json.loads((self.base / ".claude" / "contract-accuracy.json").read_text(encoding="utf-8"))
        return sum(1 for area in data["areas"].values() for row in area["history"]
                   if row.get("source") == "post-approval-journal")

    def cache(self) -> dict:
        path = self.home / ".claude" / "state" / "journal-entries-seen.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


class TrackerCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="tracker-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.home = self.tmp / "home"
        self.home.mkdir()
        (self.tmp / "p").mkdir()
        self.p = Project(self.tmp / "p" / "main", self.home)
        self.general = self.p.regs / "JOURNAL" / "general.md"
        self.frontend = self.p.regs / "JOURNAL" / "frontend.md"

    def seed(self) -> None:
        """Run the hook once on a journal file with no post entries: seeds every journal file, fires nothing."""
        done = self.p.hook(self.general)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.p.fires(), 0)


class ScriptAndHandEditTests(TrackerCase):
    def test_post_impl_divergence_by_script_fires_once_and_a_later_hand_edit_does_not_refire(self):
        done = self.p.append("journal", entry("Divergence by script", "post-impl divergence", self.p.contract),
                             "--domain", "frontend")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.p.fires(), 1)
        # a later hand edit of the same file: a new manual entry, then a rewrite of the existing one
        append_text(self.frontend, entry("A manual note", "manual", None))
        self.assertEqual(self.p.hook(self.frontend).returncode, 0)
        self.assertEqual(self.p.fires(), 1)
        self.frontend.write_bytes(self.frontend.read_bytes().replace(b"a thing happens", b"a thing happened"))
        self.assertEqual(self.p.hook(self.frontend, tool="Write").returncode, 0)
        self.assertEqual(self.p.fires(), 1)

    def test_hand_edit_to_a_seeded_general_file_fires(self):
        self.seed()
        append_text(self.general, entry("Hand written post-approval", "post-approval", self.p.contract))
        self.assertEqual(self.p.hook(self.general).returncode, 0)
        self.assertEqual(self.p.fires(), 1)
        self.assertEqual(self.p.hook(self.general).returncode, 0)  # the same edit again: nothing more
        self.assertEqual(self.p.fires(), 1)

    def test_hand_edit_of_the_root_file_fires_after_seeding(self):
        self.seed()
        root = self.p.regs / "JOURNAL.md"
        root.write_bytes(root.read_bytes().replace(
            b"## Project tier", entry("Root hand entry", "post-approval", self.p.contract).encode("utf-8")
            + b"\n## Project tier"))
        self.assertEqual(self.p.hook(root).returncode, 0)
        self.assertEqual(self.p.fires(), 1)

    def test_script_entry_in_a_new_domain_file_fires_because_it_is_fresh(self):
        self.seed()
        done = self.p.append("journal", entry("Fresh in a new file", "post-impl divergence", self.p.contract),
                             "--domain", "backend", "--create-domain")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue((self.p.regs / "JOURNAL" / "backend.md").exists())
        self.assertEqual(self.p.fires(), 1)

    def test_non_post_trigger_by_script_does_not_fire(self):
        done = self.p.append("journal", entry("Just a note", "manual", self.p.contract), "--domain", "frontend")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.p.fires(), 0)

    def test_hook_ignores_files_that_are_not_journal_files(self):
        other = write(self.p.base / "notes.md", entry("Not a journal", "post-approval", self.p.contract))
        self.assertEqual(self.p.hook(other).returncode, 0)
        self.assertEqual(self.p.fires(), 0)
        self.assertEqual(self.p.cache(), {})
        self.assertEqual(self.p.hook(self.general, tool="Read").returncode, 0)
        self.assertEqual(self.p.cache(), {})


class SeedingTests(TrackerCase):
    def test_unseeded_domain_file_with_post_entries_is_seeded_with_zero_fires(self):
        append_text(self.frontend, entry("Historic post entry", "post-approval", self.p.contract))
        self.assertEqual(self.p.hook(self.general).returncode, 0)
        self.assertEqual(self.p.fires(), 0)
        cache = self.p.cache()
        keys = list(cache["seeded_files"])
        self.assertTrue(any(k.endswith("JOURNAL/frontend.md") or k.lower().endswith("journal/frontend.md")
                            for k in keys), keys)
        # once seeded, a new entry in that file fires
        append_text(self.frontend, entry("Later post entry", "post-approval", self.p.contract, date="2026-11-05"))
        self.assertEqual(self.p.hook(self.frontend).returncode, 0)
        self.assertEqual(self.p.fires(), 1)

    def test_old_cache_seeds_domain_files_without_firing_and_keeps_the_root_seeded(self):
        append_text(self.frontend, entry("Historic post entry", "post-approval", self.p.contract))
        state = self.home / ".claude" / "state"
        state.mkdir(parents=True)
        (state / "journal-entries-seen.json").write_text(
            json.dumps({"_initialized": True, "sigs": {"0" * 40: True}}), encoding="utf-8")
        self.assertEqual(self.p.hook(self.general).returncode, 0)
        self.assertEqual(self.p.fires(), 0)
        cache = self.p.cache()
        self.assertTrue(cache["_initialized"])
        self.assertGreaterEqual(len(cache["seeded_files"]), 3)  # root + general + frontend
        # the root key counted as seeded by the old cache: a new root entry fires
        root = self.p.regs / "JOURNAL.md"
        root.write_bytes(root.read_bytes().replace(
            b"## Project tier", entry("Root entry after upgrade", "post-approval", self.p.contract).encode("utf-8")
            + b"\n## Project tier"))
        self.assertEqual(self.p.hook(root).returncode, 0)
        self.assertEqual(self.p.fires(), 1)

    def test_accepted_guard_limit_hand_entry_in_a_never_seen_file_does_not_fire(self):
        """Q17, pinned: a hand-written post-* entry in a journal file the machine never saw is seeded, not fired."""
        self.seed()
        backend = write(self.p.regs / "JOURNAL" / "backend.md",
                        "# Journal - backend\n\n" + entry("Hand entry in a new file", "post-approval", self.p.contract))
        self.assertEqual(self.p.hook(backend).returncode, 0)
        self.assertEqual(self.p.fires(), 0)
        # the script path for a file in the same position does fire
        done = self.p.append("journal", entry("Script entry in a newer file", "post-impl divergence", self.p.contract),
                             "--domain", "ops", "--create-domain")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.p.fires(), 1)


class WorktreeTests(TrackerCase):
    def test_same_journal_file_from_two_worktrees_seeds_once_and_fires_once(self):
        a = Project(self.p.base / ".claude" / "worktrees" / "a", self.home)
        b = Project(self.p.base / ".claude" / "worktrees" / "b", self.home)
        a_general = a.regs / "JOURNAL" / "general.md"
        b_general = b.regs / "JOURNAL" / "general.md"
        self.assertEqual(a.hook(a_general).returncode, 0)
        seeded_after_a = dict(a.cache()["seeded_files"])
        self.assertTrue(seeded_after_a)
        self.assertFalse(any("worktrees" in k for k in seeded_after_a), seeded_after_a)
        self.assertEqual(b.hook(b_general).returncode, 0)
        self.assertEqual(b.cache()["seeded_files"], seeded_after_a)  # seeded once, shared by both checkouts
        # a new hand entry in worktree b fires once ...
        new = entry("Hand entry from b", "post-approval", b.contract)
        append_text(b_general, new)
        self.assertEqual(b.hook(b_general).returncode, 0)
        self.assertEqual(b.fires(), 1)
        # ... and the same entry arriving through worktree a does not fire again
        append_text(a_general, entry("Hand entry from b", "post-approval", a.contract))
        self.assertEqual(a.hook(a_general).returncode, 0)
        self.assertEqual(a.fires() + b.fires(), 1)


class HookContractTests(TrackerCase):
    def test_off_switch_does_nothing(self):
        append_text(self.general, entry("Switched off", "post-approval", self.p.contract))
        done = self.p.hook(self.general, extra_env={"CLAUDE_ACCURACY_TRACKER": "off"})
        self.assertEqual(done.returncode, 0)
        self.assertEqual(self.p.cache(), {})

    def test_missing_entry_point_exits_zero_with_one_stderr_line(self):
        lone = self.tmp / "lone" / ".claude" / "hooks"
        lone.mkdir(parents=True)
        shutil.copy2(HOOK, lone / HOOK.name)
        done = self.p.hook(self.general, hook=lone / HOOK.name)
        self.assertEqual(done.returncode, 0, done.stderr)
        lines = [ln for ln in done.stderr.decode("utf-8", "replace").splitlines() if ln.strip()]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("process_journal_change", lines[0])

    def test_garbage_input_exits_zero(self):
        done = subprocess.run([sys.executable, str(HOOK)], input=b"not json", capture_output=True,
                              env=self.p.env(), cwd=str(self.p.base), timeout=120)
        self.assertEqual(done.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
