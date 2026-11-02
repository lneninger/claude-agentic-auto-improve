#!/usr/bin/env python3
"""Tests for the shared registry reader: entry_blocks, journal_entries, tier_split, and the hook caller.

Contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md, "Candidate reading".

  * entry_blocks / journal_entries take TEXT; sub-bullets attach to their parent; an entry ends at the next
    top-level match or a heading; tier comes from the text's own headings; an entry before any tier heading is
    Project; per_domain=True makes everything Project.
  * tier_split keeps its (title, line) output byte for byte: the pre-change function is copied verbatim below and
    main() is run once with it and once with the new one, on a temporary copy of the registries. No golden file.
  * The hook's parse_entries is a thin caller of journal_entries and differs from the old regex output only for the
    listed Source contract forms.

Run: py -3 .claude/scripts/tests/test_registry_entries.py
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent.parent
HOOK_PATH = REPO_ROOT / ".claude" / "hooks" / "journal-post-approval-tracker.py"
sys.path.insert(0, str(SCRIPTS_DIR))
import generate_registry_digest as grd  # noqa: E402


# --- the pre-change code, copied verbatim, as the oracle -------------------------------------------------------
def old_tier_split(path, pattern):
    """Split a two-tier registry into (universal, project) entry lists."""
    uni, proj, tier = [], [], None
    for i, ln in enumerate(grd.read(path), 1):
        if ln.startswith('## Universal'):
            tier = 'U'
            continue
        if ln.startswith('## Project:'):
            tier = 'P'
            continue
        m = pattern.match(ln)
        if m:
            (uni if tier == 'U' else proj).append((m.group(1).strip(), i))
    return uni, proj


OLD_ENTRY_HEADER = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2})\s+(?:—|--|-)\s+(.+?)\s*$", re.MULTILINE)
OLD_TRIGGER_LINE = re.compile(r"^\s*-\s*\*\*Trigger:\*\*\s*(.+?)\s*$", re.MULTILINE)
OLD_SOURCE_LINE = re.compile(r"^\s*-\s*\*\*Source contract:\*\*\s*`?([^\s`]+)`?", re.MULTILINE)


def old_parse_entries(text):
    headers = list(OLD_ENTRY_HEADER.finditer(text))
    entries = []
    for i, h in enumerate(headers):
        start = h.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        tail = text[h.end():end]
        ss_break = re.search(r"(?m)^##\s", tail)
        if ss_break:
            end = h.end() + ss_break.start()
        body = text[start:end]
        date = h.group(1)
        title = h.group(2).strip()
        sig = hashlib.sha1(f"{date}|{title}".encode("utf-8", errors="ignore")).hexdigest()
        trig_m = OLD_TRIGGER_LINE.search(body)
        src_m = OLD_SOURCE_LINE.search(body)
        entries.append({
            "sig": sig, "date": date, "title": title,
            "trigger": (trig_m.group(1).strip().lower() if trig_m else ""),
            "source_contract": (src_m.group(1).strip() if src_m else ""),
            "body": body,
        })
    return entries


def load_hook():
    spec = importlib.util.spec_from_file_location("journal_post_approval_tracker_under_test", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BULLETS = """\
- **Early** before any tier heading
  - **Correction (2026-01-01, `.claude/concepts/early.md`):** fixed early.

## Universal Patterns (cross-project)

- **Alpha** first line
  continuation of alpha
  - **Correction (2026-02-02, `.claude/concepts/alpha-c.md`):** alpha fix one
    wrapped line of the fix
  - plain sub bullet
- **Beta** second

## Project: demo

- **Gamma** third
- **Delta** fourth
"""

JOURNAL = """\
# Journal

## Entry shape

### YYYY-MM-DD — template, not an entry

## Universal lessons (apply to every project)

### 2026-10-04 — First lesson
- **Trigger:** Pre-Approval Critic
- **Source contract:** `.claude/concepts/2026-10-04-a.md`

### 2026-10-05 — Second lesson
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-10-05-b.md

## Project: demo

### 2026-10-06 — Third lesson
- **Trigger:** manual
- **Source contract:** N/A
"""


class EntryBlocksTests(unittest.TestCase):
    def setUp(self):
        self.blocks = grd.entry_blocks(BULLETS, grd.BULLET)
        self.by_title = {b["title"]: b for b in self.blocks}

    def test_every_top_level_match_is_an_entry_with_a_one_based_line(self):
        self.assertEqual([(b["title"], b["line"]) for b in self.blocks],
                         [("Early", 1), ("Alpha", 6), ("Beta", 11), ("Gamma", 15), ("Delta", 16)])

    def test_correction_subbullets_attach_to_their_parent_with_their_own_line(self):
        alpha = self.by_title["Alpha"]
        self.assertEqual([s["line"] for s in alpha["subs"]], [8, 10])
        self.assertIn("alpha fix one", alpha["subs"][0]["text"])
        self.assertIn("wrapped line of the fix", alpha["subs"][0]["text"],
                      "a deeper continuation line belongs to its sub-bullet")
        self.assertIn("plain sub bullet", alpha["subs"][1]["text"])
        self.assertEqual(self.by_title["Early"]["subs"][0]["line"], 2)

    def test_own_text_stops_before_the_first_subbullet(self):
        alpha = self.by_title["Alpha"]
        self.assertIn("first line", alpha["text"])
        self.assertIn("continuation of alpha", alpha["text"])
        self.assertNotIn("Correction", alpha["text"])
        self.assertNotIn("plain sub bullet", alpha["text"])

    def test_a_bullet_ends_at_the_next_top_level_match_or_heading(self):
        beta = self.by_title["Beta"]
        self.assertNotIn("Project: demo", beta["text"])
        self.assertNotIn("Gamma", beta["text"])
        self.assertEqual(beta["subs"], [])
        self.assertNotIn("Delta", self.by_title["Gamma"]["text"])

    def test_tier_follows_the_text_headings_and_a_pre_heading_entry_is_project(self):
        tiers = {b["title"]: b["tier"] for b in self.blocks}
        self.assertEqual(tiers, {"Early": "Project", "Alpha": "Universal", "Beta": "Universal",
                                 "Gamma": "Project", "Delta": "Project"})

    def test_per_domain_makes_every_entry_project_even_under_a_universal_heading(self):
        blocks = grd.entry_blocks(BULLETS, grd.BULLET, per_domain=True)
        self.assertEqual({b["tier"] for b in blocks}, {"Project"})
        self.assertEqual(len(blocks), 5)

    def test_it_takes_text_not_a_path(self):
        self.assertEqual(grd.entry_blocks("", grd.BULLET), [])
        self.assertEqual(grd.entry_blocks("no entries here\n", grd.BULLET), [])


class JournalEntriesTests(unittest.TestCase):
    def entries(self, text=JOURNAL, **kw):
        return {e["title"]: e for e in grd.journal_entries(text, **kw)}

    def test_sig_is_sha1_of_date_and_title_and_fields_are_read(self):
        e = self.entries()["First lesson"]
        self.assertEqual(e["sig"], hashlib.sha1(b"2026-10-04|First lesson").hexdigest())
        self.assertEqual((e["date"], e["line"]), ("2026-10-04", 9))
        self.assertEqual(e["trigger"], "pre-approval critic")
        self.assertEqual(e["source"], ".claude/concepts/2026-10-04-a.md")
        self.assertIn("**Trigger:**", e["text"])

    def test_the_template_heading_is_not_an_entry(self):
        self.assertNotIn("template, not an entry", self.entries())
        self.assertEqual(len(self.entries()), 3)

    def test_tier_comes_from_universal_and_project_headings(self):
        got = self.entries()
        self.assertEqual(got["First lesson"]["tier"], "Universal")
        self.assertEqual(got["Second lesson"]["tier"], "Universal")
        self.assertEqual(got["Third lesson"]["tier"], "Project")

    def test_an_entry_before_any_tier_heading_is_project(self):
        text = "### 2026-01-01 — Loose\n- **Trigger:** manual\n\n## Universal lessons\n\n### 2026-01-02 — Tiered\n"
        got = self.entries(text)
        self.assertEqual(got["Loose"]["tier"], "Project")
        self.assertEqual(got["Tiered"]["tier"], "Universal")

    def test_per_domain_makes_every_entry_project(self):
        self.assertEqual({e["tier"] for e in self.entries(per_domain=True).values()}, {"Project"})

    def test_an_entry_ends_at_the_next_entry_or_a_second_level_heading(self):
        got = self.entries()
        self.assertNotIn("Second lesson", got["First lesson"]["text"])
        self.assertNotIn("Project: demo", got["Second lesson"]["text"])

    def source(self, value):
        text = "### 2026-01-01 — T\n- **Trigger:** manual\n- **Source contract:**%s\n" % value
        return grd.journal_entries(text)[0]["source"]

    def test_source_with_spaces_is_captured_to_the_end_of_the_line_trimmed(self):
        self.assertEqual(self.source(" `.claude/concepts/my folder/x y.md`  "), ".claude/concepts/my folder/x y.md")
        self.assertEqual(self.source(" .claude/concepts/a b.md"), ".claude/concepts/a b.md")

    def test_unset_forms_read_as_empty(self):
        for value in (" N/A", " n/a", " none", " None", "", "   ", " `N/A`", " <path to the contract>",
                      " `<slug>`"):
            self.assertEqual(self.source(value), "", "form %r must read as unset" % value)

    def test_a_missing_source_line_reads_as_empty(self):
        self.assertEqual(grd.journal_entries("### 2026-01-01 — T\n- **Trigger:** manual\n")[0]["source"], "")

    def test_an_absolute_windows_path_is_captured_whole(self):
        path = r"D:\Dev\X\.claude\worktrees\w\.claude\concepts\2026-10-31-warn.md"
        self.assertEqual(self.source(" " + path), path)
        self.assertEqual(self.source(" `%s`" % path), path)


class FixtureRegistries:
    """A temporary project tree holding a copy of a registries folder."""

    def __init__(self, source=None, files=None):
        self.tmp = Path(tempfile.mkdtemp(prefix="registry-entries-"))
        reg = self.tmp / ".claude" / "registries"
        if source is not None:
            shutil.copytree(source, reg)
        else:
            reg.mkdir(parents=True)
        for rel, text in (files or {}).items():
            target = reg / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def run_main(tmp: Path, tier_split_fn):
    cwd = os.getcwd()
    original = grd.tier_split
    os.chdir(tmp)
    grd.tier_split = tier_split_fn
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = grd.main()
        return code, buf.getvalue(), (tmp / grd.OUT).read_bytes()
    finally:
        grd.tier_split = original
        os.chdir(cwd)


class TierSplitIsByteIdentical(unittest.TestCase):
    def compare(self, source=None, files=None):
        new = grd.tier_split
        fx = FixtureRegistries(source=source, files=files)
        try:
            old_run = run_main(fx.tmp, old_tier_split)
            new_run = run_main(fx.tmp, new)
        finally:
            fx.close()
        self.assertEqual(old_run[0], new_run[0], "exit code must match")
        self.assertEqual(old_run[1], new_run[1], "printed summary must match")
        self.assertEqual(old_run[2], new_run[2], "the generated digest must match byte for byte")
        self.assertGreater(len(new_run[2]), 200)

    def test_current_registries(self):
        self.compare(source=REPO_ROOT / ".claude" / "registries")

    def test_fixtures_with_a_pre_heading_entry_and_correction_subbullets(self):
        self.compare(files={
            "MECHANISMS.md": BULLETS,
            "VOCABULARY.md": BULLETS.replace("Alpha", "Vocab"),
            "JOURNAL.md": JOURNAL,
            "MECHANISMS/backend.md": "- **Dom A** x\n  - **Correction (d, `c`):** y\n",
            "JOURNAL/data.md": "### 2026-02-02 — Domain lesson\n- **Trigger:** manual\n",
        })

    def test_new_tier_split_keeps_its_signature_and_shape(self):
        fx = FixtureRegistries(files={"MECHANISMS.md": BULLETS})
        try:
            path = str(fx.tmp / ".claude" / "registries" / "MECHANISMS.md")
            self.assertEqual(grd.tier_split(path, grd.BULLET), old_tier_split(path, grd.BULLET))
            self.assertEqual(grd.tier_split(path + ".missing", grd.BULLET), ([], []))
        finally:
            fx.close()


class HookCallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hook = load_hook()
        cls.journal_text = (REPO_ROOT / ".claude" / "registries" / "JOURNAL.md").read_text(encoding="utf-8")

    def test_parse_entries_keeps_its_signature_and_keys(self):
        entries = self.hook.parse_entries(JOURNAL)
        self.assertEqual(len(entries), 3)
        self.assertEqual(set(entries[0]), {"sig", "date", "title", "trigger", "source_contract", "body"})

    def test_sig_trigger_and_source_equal_the_old_output_on_the_current_journal(self):
        new = self.hook.parse_entries(self.journal_text)
        old = old_parse_entries(self.journal_text)
        self.assertGreater(len(old), 20)
        self.assertEqual(len(new), len(old))
        for n, o in zip(new, old):
            self.assertEqual((n["sig"], n["date"], n["title"], n["trigger"], n["source_contract"]),
                             (o["sig"], o["date"], o["title"], o["trigger"], o["source_contract"]))

    def test_only_the_listed_source_forms_differ_from_the_old_output(self):
        text = ("### 2026-01-01 — Spaces\n- **Trigger:** manual\n- **Source contract:** `a b/c d.md`\n\n"
                "### 2026-01-02 — NotApplicable\n- **Trigger:** manual\n- **Source contract:** N/A\n")
        new = {e["title"]: e for e in self.hook.parse_entries(text)}
        old = {e["title"]: e for e in old_parse_entries(text)}
        self.assertEqual(old["Spaces"]["source_contract"], "a")
        self.assertEqual(new["Spaces"]["source_contract"], "a b/c d.md")
        self.assertEqual(old["NotApplicable"]["source_contract"], "N/A")
        self.assertEqual(new["NotApplicable"]["source_contract"], "",
                         "an N/A source no longer feeds derive_areas a non-path")
        for key in ("sig", "date", "title", "trigger"):
            self.assertEqual(new["Spaces"][key], old["Spaces"][key])

    def test_a_missing_reader_makes_the_hook_skip_and_log(self):
        events = []
        original = (self.hook._journal_entries, self.hook.log_event)
        self.hook._journal_entries = None
        self.hook.log_event = lambda *a, **k: events.append(k.get("event"))
        try:
            self.assertEqual(self.hook.main(), 0)
            self.assertEqual(self.hook.parse_entries(JOURNAL), [])
        finally:
            self.hook._journal_entries, self.hook.log_event = original
        self.assertIn("journal-tracker-reader-missing", events)


if __name__ == "__main__":
    unittest.main(verbosity=2)
