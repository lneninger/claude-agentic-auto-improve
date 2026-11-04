#!/usr/bin/env python3
"""
Tests for registry_append.py, the single write path of the registries (contract 2026-11-04-domain-split-registries,
Command "Append registry entry").

Every test runs the script as a subprocess against a temporary project; HOME and USERPROFILE point at a temporary
folder so the machine-wide journal seen cache of the real machine is never touched.

Run: py -3 .claude/scripts/tests/test_registry_append.py
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
sys.path.insert(0, str(SCRIPTS_DIR))

import _registry_layout as rl  # noqa: E402

APPEND = SCRIPTS_DIR / "registry_append.py"
MARK = rl.MARKER
REG_FILES = {"mechanisms": "MECHANISMS", "vocabulary": "VOCABULARY", "journal": "JOURNAL"}


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def jentry(title: str, *, date: str = "2026-11-04", trigger: str = "manual", source: str = "N/A",
           apply_when: str = "a thing happens") -> str:
    return (f"### {date} — {title}\n- **Trigger:** {trigger}\n- **Source contract:** {source}\n"
            f"- **Lesson:** do the thing\n- **Apply when:** {apply_when}\n- **Tags:** t1, t2\n")


def mentry(title: str, body: str = "what it is and why it matters") -> str:
    return f"- **{title}** *(2026-11-04)* — {body}\n"


def root_text(registry: str, *, marked: bool, pointer: bool, universal: str = "", tail: str = "") -> str:
    head = (MARK + "\n") if marked else ""
    title = {"MECHANISMS": "Mechanisms", "VOCABULARY": "Vocabulary", "JOURNAL": "Journal"}[registry]
    text = head + f"# {title}\n\n> header prose\n\n## Universal\n\n{universal}"
    if pointer:
        text += "\n" + rl.pointer_section(registry)
    return text + tail


def universal_for(registry: str) -> str:
    return jentry("Existing universal lesson") if registry == "JOURNAL" else mentry("Existing universal")


class Fixture:
    """A temporary project plus a temporary home."""

    def __init__(self, test: unittest.TestCase):
        self._tmp = tempfile.TemporaryDirectory(prefix="regappend-")
        test.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.project = self.base / "proj"
        self.home = self.base / "home"
        self.home.mkdir()
        self.project.mkdir()
        self.regs = self.project / ".claude" / "registries"

    def env(self) -> dict:
        e = dict(os.environ)
        e.pop("CLAUDE_PROJECT_DIR", None)
        e.update({"HOME": str(self.home), "USERPROFILE": str(self.home), "PYTHONIOENCODING": "utf-8",
                  "PYTHONDONTWRITEBYTECODE": "1"})
        return e

    def make(self, state: str, *, domains: tuple = ("general", "frontend"), leftovers: bool = False) -> None:
        """Build the three registries in one layout state: current | pending | stale-sync."""
        write(self.project / ".claude" / "contract-accuracy.json", '{"schema_version": 1, "areas": {}}')
        write(self.project / ".claude" / "area-mapping.json",
              json.dumps({"areas": {"frontend": {"patterns": ["web/"]}}}))
        for registry in rl.REGISTRIES:
            uni = universal_for(registry)
            if state == "current":
                text = root_text(registry, marked=True, pointer=True, universal=uni)
            elif state == "pending":
                text = root_text(registry, marked=False, pointer=False, universal=uni,
                                 tail="\nSee domain-specific files in the project registry folder.\n")
            elif state == "stale-sync":
                project_entry = jentry("Project lesson in root") if registry == "JOURNAL" else mentry("Project in root")
                text = root_text(registry, marked=True, pointer=True, universal=uni,
                                 tail=f"\n## Project: demo\n\n{project_entry}")
            else:
                raise ValueError(state)
            write(self.regs / f"{registry}.md", text)
            if state == "current":
                for slug in domains:
                    body = f"# {registry} - {slug}\n\n> header\n\n"
                    if slug == "general" and leftovers:
                        body += (rl.LEFTOVERS_HEADING + "\n\n<!-- leftover from x.md:1-2, project-prose -->\n"
                                 "```\nleftover prose\n```\n")
                    write(self.regs / registry / f"{slug}.md", body)
            elif state == "pending" and "frontend" in domains:
                write(self.regs / registry / "frontend.md", f"# {registry} - frontend\n\n> header\n\n")

    def root_bytes(self) -> dict:
        return {r: (self.regs / f"{r}.md").read_bytes() for r in rl.REGISTRIES}

    def read(self, rel: str) -> str:
        return (self.regs / rel).read_bytes().decode("utf-8")

    def run(self, registry: str, entry: str | None, *extra: str, project: str | None = "default",
            stdin: str | None = None) -> subprocess.CompletedProcess:
        args = [sys.executable, str(APPEND)]
        if project == "default":
            project = str(self.project)
        if project is not None:
            args += ["--project", project]
        args += ["--registry", registry]
        data = None
        if entry is not None:
            if stdin is not None:
                args += ["--from-file", "-"]
                data = stdin
            else:
                src = self.base / "entry.md"
                src.write_bytes(entry.encode("utf-8"))
                args += ["--from-file", str(src)]
        args += list(extra)
        return subprocess.run(args, input=(data.encode("utf-8") if data is not None else None),
                              capture_output=True, env=self.env(), cwd=str(self.base), timeout=120)


def out(done: subprocess.CompletedProcess) -> str:
    return done.stdout.decode("utf-8", "replace") + done.stderr.decode("utf-8", "replace")


class RejectionTests(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture(self)
        self.fx.make("current")

    def assertRejected(self, done, code: str, exit_code: int):
        self.assertEqual(done.returncode, exit_code, out(done))
        self.assertIn(code, out(done))

    def test_bodiless_input(self):
        done = self.fx.run("journal", jentry("No body here", apply_when=""))
        self.assertRejected(done, "bodiless-input", 2)
        done = self.fx.run("mechanisms", "- **Empty body** *(2026-11-04)* —\n")
        self.assertRejected(done, "bodiless-input", 2)

    def test_duplicate_entry_in_domain_file_and_in_root(self):
        self.assertEqual(self.fx.run("journal", jentry("Same title"), "--domain", "frontend").returncode, 0)
        self.assertRejected(self.fx.run("journal", jentry("same   TITLE", date="2026-11-05")), "duplicate-entry", 2)
        self.assertRejected(self.fx.run("journal", jentry("Existing universal lesson")), "duplicate-entry", 2)

    def test_malformed_input(self):
        self.assertRejected(self.fx.run("mechanisms", "- **No separator** just words\n"), "malformed-input", 2)
        self.assertRejected(self.fx.run("journal", "not an entry at all\n"), "malformed-input", 2)
        self.assertRejected(self.fx.run("journal", ""), "malformed-input", 2)
        two = jentry("First of two") + "\n" + jentry("Second of two")
        self.assertRejected(self.fx.run("journal", two), "malformed-input", 2)
        bad_trigger = jentry("Bad trigger", trigger="sometime")
        self.assertRejected(self.fx.run("journal", bad_trigger), "malformed-input", 2)

    def test_unknown_domain_on_current(self):
        self.assertRejected(self.fx.run("journal", jentry("Nowhere"), "--domain", "nope"), "unknown-domain", 2)

    def test_no_universal_tier(self):
        write(self.fx.regs / "JOURNAL.md", MARK + "\n" + rl.pointer_section("JOURNAL"))
        self.assertRejected(self.fx.run("journal", jentry("Cannot go up"), "--universal"), "no-universal-tier", 2)

    def test_correction_and_archive_targets(self):
        self.assertRejected(self.fx.run("journal", "Superseded by a later finding.\n", "--correction-of", "Missing"),
                            "correction-target-missing", 2)
        self.assertRejected(self.fx.run("journal", None, "--archive-title-only", "Missing"),
                            "archive-target-missing", 2)
        self.assertRejected(self.fx.run("journal", None, "--archive-title-only", "Existing universal lesson"),
                            "archive-target-has-body", 2)

    def test_layout_unknown(self):
        write(self.fx.regs / "JOURNAL.md", root_text("JOURNAL", marked=False, pointer=False))
        done = self.fx.run("journal", jentry("Blocked"))
        self.assertRejected(done, "layout-unknown", 3)

    def test_registries_absent(self):
        empty = self.fx.base / "empty"
        empty.mkdir()
        self.assertRejected(self.fx.run("journal", jentry("Nowhere"), project=str(empty)), "registries-absent", 3)

    def test_project_undetermined_unset_and_absent(self):
        done = self.fx.run("journal", jentry("No project"), project=None)
        self.assertRejected(done, "project-undetermined", 3)
        done = self.fx.run("journal", jentry("No project"), project=str(self.fx.base / "does-not-exist"))
        self.assertRejected(done, "project-undetermined", 3)

    def test_write_failed(self):
        fx = Fixture(self)
        fx.make("pending", domains=())
        # JOURNAL is a regular file where the domain folder has to be, so general.md cannot be created.
        write(fx.regs / "JOURNAL", "not a folder")
        done = fx.run("journal", jentry("Cannot be written"))
        self.assertEqual(done.returncode, 3, out(done))
        self.assertIn("write-failed", out(done))


class CurrentTests(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture(self)
        self.fx.make("current")

    def parse(self, rel: str, registry: str):
        return rl.parse_file(self.fx.regs / rel, registry)

    def test_universal_lands_before_the_pointer(self):
        done = self.fx.run("journal", jentry("A new universal lesson"), "--universal")
        self.assertEqual(done.returncode, 0, out(done))
        text = self.fx.read("JOURNAL.md")
        self.assertLess(text.index("A new universal lesson"), text.index(rl.POINTER_HEADING))
        self.assertTrue(text.rstrip().endswith(rl.pointer_section("JOURNAL").rstrip()))
        self.assertIn("JOURNAL.md:", done.stdout.decode("utf-8"))
        pf = self.parse("JOURNAL.md", "JOURNAL")
        titles = [(e.title, e.tier) for e in pf.entries]
        self.assertIn(("A new universal lesson", "universal"), titles)
        self.assertEqual(rl.layout_state(self.fx.regs).state, "current")

    def test_domain_option_picks_the_existing_domain_file(self):
        done = self.fx.run("mechanisms", mentry("Frontend mechanism"), "--domain", "frontend")
        self.assertEqual(done.returncode, 0, out(done))
        self.assertIn("Frontend mechanism", self.fx.read("MECHANISMS/frontend.md"))
        self.assertNotIn("Frontend mechanism", self.fx.read("MECHANISMS/general.md"))
        self.assertNotIn("Frontend mechanism", self.fx.read("MECHANISMS.md"))
        self.assertIn("frontend", out(done))  # the choice is printed

    def test_area_default_from_the_source_contract(self):
        contract = self.fx.project / ".claude" / "concepts" / "2026-11-04-area.md"
        write(contract, "# C\n\n**Status:** approved\n\n**Files to touch:**\n\n- `web/app/thing.ts`\n")
        entry = jentry("Area routed lesson", source="`.claude/concepts/2026-11-04-area.md`")
        done = self.fx.run("journal", entry)
        self.assertEqual(done.returncode, 0, out(done))
        self.assertIn("Area routed lesson", self.fx.read("JOURNAL/frontend.md"))
        self.assertNotIn("Area routed lesson", self.fx.read("JOURNAL/general.md"))

    def test_general_fallback(self):
        done = self.fx.run("vocabulary", mentry("Plain term"))
        self.assertEqual(done.returncode, 0, out(done))
        self.assertIn("Plain term", self.fx.read("VOCABULARY/general.md"))
        self.assertIn("general", out(done))

    def test_create_domain_makes_the_file(self):
        done = self.fx.run("mechanisms", mentry("Backend mechanism"), "--domain", "backend", "--create-domain")
        self.assertEqual(done.returncode, 0, out(done))
        self.assertIn("Backend mechanism", self.fx.read("MECHANISMS/backend.md"))
        self.assertEqual(rl.layout_state(self.fx.regs).state, "current")

    def test_append_lands_above_the_leftovers_heading(self):
        fx = Fixture(self)
        fx.make("current", leftovers=True)
        done = fx.run("mechanisms", mentry("Above the leftovers"))
        self.assertEqual(done.returncode, 0, out(done))
        text = fx.read("MECHANISMS/general.md")
        self.assertLess(text.index("Above the leftovers"), text.index(rl.LEFTOVERS_HEADING))
        self.assertTrue(text.rstrip().endswith("```"))
        pf = rl.parse_file(fx.regs / "MECHANISMS" / "general.md", "MECHANISMS")
        self.assertEqual([e.title for e in pf.entries], ["Above the leftovers"])

    def test_crlf_file_stays_crlf(self):
        path = self.fx.regs / "MECHANISMS" / "general.md"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        done = self.fx.run("mechanisms", mentry("Crlf entry"))
        self.assertEqual(done.returncode, 0, out(done))
        data = path.read_bytes()
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        self.assertIn(b"Crlf entry", data)

    def test_entry_from_stdin(self):
        done = self.fx.run("mechanisms", "x", stdin=mentry("From standard input"))
        self.assertEqual(done.returncode, 0, out(done))
        self.assertIn("From standard input", self.fx.read("MECHANISMS/general.md"))


class PendingTests(unittest.TestCase):
    """The reference client's state: roots without a `## Project:` section, ending in a pointer-to-files line."""

    def setUp(self):
        self.fx = Fixture(self)
        self.fx.make("pending")

    def test_non_universal_entry_lands_in_the_existing_domain_file(self):
        before = self.fx.root_bytes()
        done = self.fx.run("journal", jentry("Pending frontend lesson"), "--domain", "frontend")
        self.assertEqual(done.returncode, 0, out(done))
        self.assertIn("Pending frontend lesson", self.fx.read("JOURNAL/frontend.md"))
        self.assertEqual(self.fx.root_bytes(), before)
        self.assertIn("advisory: registry layout pending", out(done))
        self.assertIn("run registry_migrate.py --dry-run", out(done))
        self.assertFalse((self.fx.regs / "JOURNAL" / "general.md").exists())

    def test_default_creates_general_from_the_skeleton(self):
        before = self.fx.root_bytes()
        done = self.fx.run("mechanisms", mentry("Pending general mechanism"))
        self.assertEqual(done.returncode, 0, out(done))
        general = self.fx.read("MECHANISMS/general.md")
        self.assertIn("# Mechanisms - general", general)  # the skeleton header
        self.assertIn("Pending general mechanism", general)
        self.assertEqual(self.fx.root_bytes(), before)
        self.assertIn("advisory: registry layout pending", out(done))

    def test_unknown_domain_falls_back_to_general_and_is_named(self):
        before = self.fx.root_bytes()
        done = self.fx.run("vocabulary", mentry("Pending unknown domain"), "--domain", "nope")
        self.assertEqual(done.returncode, 0, out(done))
        self.assertIn("Pending unknown domain", self.fx.read("VOCABULARY/general.md"))
        self.assertFalse((self.fx.regs / "VOCABULARY" / "nope.md").exists())
        self.assertIn("nope", out(done))
        self.assertEqual(self.fx.root_bytes(), before)

    def test_universal_lands_at_the_roots_universal_end(self):
        done = self.fx.run("journal", jentry("Pending universal lesson"), "--universal")
        self.assertEqual(done.returncode, 0, out(done))
        text = self.fx.read("JOURNAL.md")
        self.assertTrue(text.rstrip().endswith(jentry("Pending universal lesson").rstrip()))
        self.assertIn("advisory: registry layout pending", out(done))
        entries = rl.parse_file(self.fx.regs / "JOURNAL.md", "JOURNAL").entries
        self.assertIn(("Pending universal lesson", "universal"), [(e.title, e.tier) for e in entries])
        self.assertFalse((self.fx.regs / "JOURNAL" / "general.md").exists())


class StaleSyncTests(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture(self)
        self.fx.make("stale-sync")

    def test_universal_goes_before_the_synced_pointer(self):
        done = self.fx.run("mechanisms", mentry("Stale universal"), "--universal")
        self.assertEqual(done.returncode, 0, out(done))
        text = self.fx.read("MECHANISMS.md")
        self.assertLess(text.index("Stale universal"), text.index(rl.POINTER_HEADING))
        self.assertIn("advisory: registry layout stale-sync", out(done))

    def test_project_entry_goes_to_a_domain_file_not_the_root(self):
        before = self.fx.root_bytes()
        done = self.fx.run("mechanisms", mentry("Stale project entry"))
        self.assertEqual(done.returncode, 0, out(done))
        self.assertIn("Stale project entry", self.fx.read("MECHANISMS/general.md"))
        self.assertEqual(self.fx.root_bytes(), before)
        self.assertIn("advisory: registry layout stale-sync", out(done))


class CorrectionAndArchiveTests(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture(self)
        self.fx.make("current")
        bodiless = ("### 2026-10-01 — Orphan lesson\n- **Trigger:** manual\n- **Source contract:** N/A\n"
                    "- **Lesson:** body lost\n- **Apply when:**\n- **Tags:** x\n")
        general = self.fx.regs / "JOURNAL" / "general.md"
        general.write_bytes(general.read_bytes() + (bodiless + "\n" + jentry("Bodied lesson")).encode("utf-8"))
        mech = self.fx.regs / "MECHANISMS" / "general.md"
        mech.write_bytes(mech.read_bytes() + b"- **Orphan mechanism** *(2026-10-01)* \xe2\x80\x94\n\n"
                         + mentry("Bodied mechanism").encode("utf-8"))

    def test_correction_of_adds_an_indented_line_under_the_entry(self):
        done = self.fx.run("mechanisms", "The rule no longer holds after the split.\n",
                           "--correction-of", "Bodied mechanism", "--date", "2026-11-05", "--source", "issue 244")
        self.assertEqual(done.returncode, 0, out(done))
        text = self.fx.read("MECHANISMS/general.md")
        self.assertIn("  - **Correction (2026-11-05, issue 244):** The rule no longer holds after the split.", text)
        self.assertLess(text.index("Bodied mechanism"), text.index("Correction (2026-11-05"))
        entries = rl.parse_file(self.fx.regs / "MECHANISMS" / "general.md", "MECHANISMS").entries
        self.assertEqual(len(entries), 2)

    def test_correction_of_a_journal_entry(self):
        done = self.fx.run("journal", "Refined later.\n", "--correction-of", "Bodied lesson", "--date", "2026-11-05")
        self.assertEqual(done.returncode, 0, out(done))
        text = self.fx.read("JOURNAL/general.md")
        self.assertIn("  - **Correction (2026-11-05, registry_append):** Refined later.", text)

    def test_archive_title_only_marks_a_bodiless_entry(self):
        done = self.fx.run("journal", None, "--archive-title-only", "Orphan lesson")
        self.assertEqual(done.returncode, 0, out(done))
        text = self.fx.read("JOURNAL/general.md")
        self.assertIn("  - **Status:** archived-title-only", text)
        self.assertLess(text.index("Orphan lesson"), text.index("archived-title-only"))
        self.assertLess(text.index("archived-title-only"), text.index("Bodied lesson"))
        entry = [e for e in rl.parse_file(self.fx.regs / "JOURNAL" / "general.md", "JOURNAL").entries
                 if e.title == "Orphan lesson"][0]
        self.assertEqual(entry.status, "archived-title-only")

    def test_archive_title_only_on_a_bodiless_mechanism(self):
        done = self.fx.run("mechanisms", None, "--archive-title-only", "Orphan mechanism")
        self.assertEqual(done.returncode, 0, out(done))
        self.assertIn("  - **Status:** archived-title-only", self.fx.read("MECHANISMS/general.md"))

    def test_archive_refused_on_a_bodied_entry_changes_nothing(self):
        before = self.fx.read("JOURNAL/general.md")
        done = self.fx.run("journal", None, "--archive-title-only", "Bodied lesson")
        self.assertEqual(done.returncode, 2, out(done))
        self.assertIn("archive-target-has-body", out(done))
        self.assertEqual(self.fx.read("JOURNAL/general.md"), before)


if __name__ == "__main__":
    unittest.main(verbosity=1)
