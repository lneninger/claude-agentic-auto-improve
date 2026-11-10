#!/usr/bin/env python3
"""
Tests for the default (no-flag) mode of validate_registries.py on a layout-2 project (issue 292, t9 review W4).

The default mode lists dead file references. Before this fix it read only the two root files, so on a layout-2
project every reference in a domain file went unchecked. Each test builds a temporary project and runs the script as
a subprocess with HOME, USERPROFILE and CLAUDE_PROJECT_DIR pointing into that temporary folder: no real registry is
read.

Run: py -3 .claude/scripts/tests/test_validate_registries_default.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
SCRIPT = SCRIPTS_DIR / "validate_registries.py"
sys.path.insert(0, str(SCRIPTS_DIR))

import _registry_layout as rl  # noqa: E402

MARK = rl.MARKER
ALIVE = "src/alive/file.cs"
DEAD = "src/dead/gone.cs"
LEFTOVER_DEAD = "src/leftover/never-existed.cs"


def mech_entry(title: str, ref: str) -> str:
    return f"- **{title}** *(2026-11-01)* — see `{ref}` for the code.\n"


def pointer(stem: str) -> str:
    # A short pointer without a path-shaped span: the generic pointer names `<STEM>/<domain>.md`, which the default
    # mode's unchanged regex reads as a dead reference (a pre-existing property of that mode, not what is tested here).
    return "## Project tier\n\nThis file holds only the Universal tier.\n"


class Project:
    def __init__(self, test: unittest.TestCase):
        self._tmp = tempfile.TemporaryDirectory(prefix="valreg-")
        test.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.project = self.base / "proj"
        self.home = self.base / "home"
        self.home.mkdir()
        (self.project / "src" / "alive").mkdir(parents=True)
        (self.project / ALIVE).write_text("// alive\n", encoding="utf-8")
        self.regs = self.project / ".claude" / "registries"
        self.regs.mkdir(parents=True)

    def write(self, rel: str, text: str) -> Path:
        path = self.regs / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
        return path

    def flat(self, mech_ref: str = DEAD) -> None:
        self.write("MECHANISMS.md", "# Mechanisms\n\n" + mech_entry("Flat Mech", mech_ref)
                   + mech_entry("Flat Alive", ALIVE))
        self.write("VOCABULARY.md", "# Vocabulary\n\n" + mech_entry("Flat Term", ALIVE))
        self.write("JOURNAL.md", "# Journal\n")

    def split(self, backend_ref: str | None = DEAD, general_text: str = "") -> None:
        for stem, title in (("MECHANISMS", "Mechanisms"), ("VOCABULARY", "Vocabulary")):
            self.write(f"{stem}.md", f"{MARK}\n\n# {title}\n\n## Universal\n\n"
                       + mech_entry("Root " + title, ALIVE) + "\n" + pointer(stem))
            self.write(f"{stem}/general.md", f"# {title} - general\n\n" + general_text)
        if backend_ref is not None:
            self.write("MECHANISMS/backend.md", "# Mechanisms - backend\n\n" + mech_entry("Backend Mech", backend_ref))
        self.write("JOURNAL.md", f"{MARK}\n# Journal\n")

    def run(self, *args: str, cwd: Path | None = None):
        env = dict(os.environ)
        env.update({"CLAUDE_PROJECT_DIR": str(self.project), "HOME": str(self.home), "USERPROFILE": str(self.home),
                    "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, env=env,
                              cwd=str(cwd or self.project), timeout=180)


def text(done) -> str:
    return done.stdout.decode("utf-8", "replace") + done.stderr.decode("utf-8", "replace")


def block(out: str, label: str) -> str:
    """The lines of one file's report block: from its status line to the line before the next status line."""
    lines = out.splitlines()
    start = next(i for i, ln in enumerate(lines) if f"] {label}:" in ln)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith(("[OK]", "[FAIL]", "[SKIP]"))
                or lines[i].startswith("=" * 10)), len(lines))
    return "\n".join(lines[start:end])


class DomainFileTests(unittest.TestCase):
    def test_a_dead_path_only_in_a_domain_file_is_reported_under_that_file_and_exits_1(self):
        p = Project(self)
        p.split(backend_ref=DEAD)
        done = p.run()
        out = text(done)
        self.assertEqual(done.returncode, 1, out)
        self.assertIn(DEAD, block(out, "MECHANISMS/backend.md"))
        self.assertIn("[FAIL] MECHANISMS/backend.md: 0/1 references resolve, 1 dead", out)
        self.assertIn("[OK] MECHANISMS.md: 1/1 references resolve, 0 dead", out)
        self.assertIn("[OK] MECHANISMS/general.md: 0/0 references resolve, 0 dead", out)
        self.assertNotIn(DEAD, block(out, "MECHANISMS.md"))
        self.assertNotIn(DEAD, block(out, "MECHANISMS/general.md"))

    def test_a_layout_2_project_with_no_dead_path_exits_0(self):
        p = Project(self)
        p.split(backend_ref=ALIVE)
        done = p.run()
        out = text(done)
        self.assertEqual(done.returncode, 0, out)
        self.assertNotIn("[FAIL]", out)
        self.assertIn("[OK] MECHANISMS/backend.md: 1/1 references resolve, 0 dead", out)
        self.assertIn("[OK] VOCABULARY/general.md: 0/0 references resolve, 0 dead", out)

    def test_json_aggregates_over_all_files_and_adds_one_files_key(self):
        p = Project(self)
        p.split(backend_ref=DEAD)
        done = p.run("--json")
        self.assertEqual(done.returncode, 1, text(done))
        data = json.loads(done.stdout.decode("utf-8"))
        self.assertEqual(set(data), {"roots", "mechanisms", "vocabulary", "files"})
        mech = data["mechanisms"]
        self.assertEqual((mech["total"], mech["alive"], mech["dead"]), (2, 1, 1))
        self.assertEqual([d["reference"] for d in mech["dead_entries"]], [DEAD])
        self.assertEqual(mech["file"], str(p.regs / "MECHANISMS.md"))
        self.assertEqual(data["vocabulary"]["total"], 1)
        self.assertEqual([Path(b["file"]).relative_to(p.regs).as_posix() for b in data["files"]],
                         ["MECHANISMS.md", "MECHANISMS/general.md", "MECHANISMS/backend.md",
                          "VOCABULARY.md", "VOCABULARY/general.md"])


class FlatLayoutTests(unittest.TestCase):
    def test_a_flat_layout_1_project_prints_the_same_blocks_and_json_as_before(self):
        p = Project(self)
        p.flat()
        done = p.run()
        out = text(done)
        self.assertEqual(done.returncode, 1, out)
        self.assertEqual(block(out, "MECHANISMS.md"),
                         f"  [FAIL] MECHANISMS.md: 1/2 references resolve, 1 dead\n"
                         f"         source: {p.regs / 'MECHANISMS.md'}\n\n"
                         f"    * line    3: {DEAD}\n"
                         f"      context: - **Flat Mech** *(2026-11-01)* — see `{DEAD}` for the code.\n")
        self.assertEqual(block(out, "VOCABULARY.md"),
                         f"  [OK] VOCABULARY.md: 1/1 references resolve, 0 dead\n"
                         f"         source: {p.regs / 'VOCABULARY.md'}")
        self.assertEqual(out.count("[OK]") + out.count("[FAIL]") + out.count("[SKIP]"), 2)
        data = json.loads(p.run("--json").stdout.decode("utf-8"))
        self.assertEqual(data["mechanisms"], {
            "file": str(p.regs / "MECHANISMS.md"), "total": 2, "alive": 1, "dead": 1,
            "dead_entries": [{"line": 3, "reference": DEAD,
                              "context": f"- **Flat Mech** *(2026-11-01)* — see `{DEAD}` for the code."}]})
        self.assertEqual(data["vocabulary"], {"file": str(p.regs / "VOCABULARY.md"), "total": 1, "alive": 1,
                                              "dead": 0, "dead_entries": []})
        self.assertEqual([Path(b["file"]).name for b in data["files"]], ["MECHANISMS.md", "VOCABULARY.md"])

    def test_a_flat_project_with_only_live_paths_exits_0(self):
        p = Project(self)
        p.flat(mech_ref=ALIVE)
        self.assertEqual(p.run().returncode, 0)


class LeftoversTests(unittest.TestCase):
    def leftovers(self) -> str:
        return (f"\n{rl.LEFTOVERS_HEADING}\n\n<!-- leftover from .claude/registries/MECHANISMS.md:40-44, project-prose -->\n"
                f"```\nsee `{LEFTOVER_DEAD}` in prose\n```\n"
                f"A stray three-backtick run:\n```\nand `{LEFTOVER_DEAD}` again, never closed\n")

    def test_the_leftovers_section_gives_no_finding_and_a_dead_path_above_it_still_does(self):
        self.assertEqual(rl.LEFTOVERS_HEADING, "## Migration 0001 leftovers (not parsed as entries)")
        p = Project(self)
        p.split(backend_ref=None, general_text=mech_entry("Above The Leftovers", DEAD) + self.leftovers())
        # the same text in the other registry too
        done = p.run()
        out = text(done)
        self.assertEqual(done.returncode, 1, out)
        self.assertIn(DEAD, block(out, "MECHANISMS/general.md"))
        self.assertNotIn(LEFTOVER_DEAD, out)
        self.assertIn("[FAIL] MECHANISMS/general.md: 0/1 references resolve, 1 dead", out)

    def test_a_leftovers_section_alone_exits_0(self):
        p = Project(self)
        p.split(backend_ref=None, general_text=mech_entry("Above The Leftovers", ALIVE) + self.leftovers())
        done = p.run()
        out = text(done)
        self.assertEqual(done.returncode, 0, out)
        self.assertNotIn(LEFTOVER_DEAD, out)
        self.assertIn("[OK] MECHANISMS/general.md: 1/1 references resolve, 0 dead", out)


if __name__ == "__main__":
    unittest.main(verbosity=1)
