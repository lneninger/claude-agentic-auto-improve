#!/usr/bin/env python3
"""Tests for the registry readers that serve the memory adapter: entry_blocks and journal_entries (adapters over
_registry_layout.parse_text, re-exported by generate_registry_digest) and accuracy_update.parse_journal_entries.

Contracts: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md, "Candidate reading", and
.claude/concepts/2026-11-04-domain-split-registries.md, block 12 (Q21 (a)).

  * entry_blocks / journal_entries take TEXT; sub-bullets attach to their parent; an entry ends at the next
    top-level match or a heading; tier comes from the text's own headings; an entry before any tier heading is
    Project; per_domain=True makes everything Project. EntryBlocksTests and JournalEntriesTests are the adapters'
    acceptance tests and were not changed by the move to the one grammar.
  * AdapterDifferenceTests pins each place where the adapters, which read through parse_text, differ on purpose from
    the default branch's old functions (D1-D5 for entry_blocks, J1-J5 for journal_entries).
  * TierSplitIsByteIdentical is gone: it pinned the pre-contract digest byte for byte, and the contract's Digest
    generator replaces that digest (test_registry_layout.py's digest tests cover the new one).
  * AccuracyParserTests: the hook's journal parser lives in accuracy_update.parse_journal_entries. It keeps the old
    regex output's sig, date, title and trigger on the frozen copy of the journal, and differs only in the source forms.
    The missing-reader row moved to block 13; test (d) of test_journal_post_approval_tracker.py covers it until then.

Run: py -3 .claude/scripts/tests/test_registry_entries.py
"""
from __future__ import annotations

import hashlib
import re
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent.parent
FROZEN_JOURNAL = REPO_ROOT / ".claude" / "hooks" / "tests" / "fixtures" / "journal-signatures-2026-11-06.md"
sys.path.insert(0, str(SCRIPTS_DIR))
import accuracy_update as au  # noqa: E402
import generate_registry_digest as grd  # noqa: E402


# --- the pre-change parser, copied verbatim, as the oracle ------------------------------------------------------
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

    def test_own_text_ends_at_a_blank_line_followed_by_a_non_indented_line(self):
        text = ("## Universal\n\n- **Last** bullet\n  wrapped line\n\nNote: see .claude/concepts/x.md\n\n"
                "  indented after the note\n- **Next** bullet\n\n  indented after a blank line\n")
        blocks = {b["title"]: b for b in grd.entry_blocks(text, grd.BULLET)}
        self.assertIn("wrapped line", blocks["Last"]["text"])
        self.assertNotIn("Note:", blocks["Last"]["text"])
        self.assertNotIn("indented after the note", blocks["Last"]["text"])
        self.assertIn("indented after a blank line", blocks["Next"]["text"],
                      "a blank line followed by an indented line does not end the entry")

    def test_a_note_paragraph_does_not_end_the_entry_before_it_when_a_top_level_match_follows(self):
        text = "## Universal\n\n- **A** one\n\n- **B** two\n"
        self.assertEqual([(b["title"], b["line"]) for b in grd.entry_blocks(text, grd.BULLET)], [("A", 3), ("B", 5)])

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


class AdapterDifferenceTests(unittest.TestCase):
    """One fixture row per intended difference from the default branch's old functions (block 12, Q21 (a)).

    The adapters read through _registry_layout.parse_text, the one grammar. Each row names what the old function did
    so a reader sees why the result moved.
    """

    def blocks(self, text, **kw):
        return grd.entry_blocks(text, grd.BULLET, **kw)

    def titles(self, text, **kw):
        return [b["title"] for b in self.blocks(text, **kw)]

    # --- D1-D5: entry_blocks -------------------------------------------------------------------------------------
    def test_d1_a_bullet_inside_a_fence_is_not_an_entry_and_a_column_zero_fence_ends_the_open_entry(self):
        text = ("## Universal Patterns\n\n- **Real** — body\n```markdown\n- **Fake** — in a fence\n```\n"
                "- **After** — b\n")
        blocks = {b["title"]: b for b in self.blocks(text)}
        self.assertEqual(list(blocks), ["Real", "After"], "old: Fake was an entry")
        self.assertEqual(blocks["Real"]["text"], "- **Real** — body", "old: the fence lines folded into the text")

    def test_d2_bullets_under_a_non_tier_heading_are_prose_to_the_next_heading(self):
        text = ("## Universal Patterns\n\n- **Real** — body\n\n## Notes\n\n- **Prose** — not an entry\n\n"
                "## Project: demo\n\n- **Proj** — x\n")
        self.assertEqual(self.titles(text), ["Real", "Proj"], "old: Prose was an entry")

    def test_d3_a_dated_second_level_heading_is_a_legacy_entry(self):
        text = ("## Universal Patterns\n\n- **Real** — body\n\n## 2026-09-01 — Old way\nFree text.\n- plain bullet\n\n"
                "## Project: demo\n\n- **Proj** — x\n")
        blocks = {b["title"]: b for b in self.blocks(text)}
        self.assertEqual(list(blocks), ["Real", "Old way", "Proj"], "old: the heading only ended the previous entry")
        legacy = blocks["Old way"]
        self.assertEqual(legacy["line"], 5)
        self.assertEqual(legacy["text"], "## 2026-09-01 — Old way\nFree text.\n- plain bullet")
        self.assertEqual(legacy["subs"], [])
        self.assertEqual(blocks["Real"]["text"], "- **Real** — body")

    def test_d4_an_entry_continues_only_on_blank_and_indented_lines(self):
        text = "## Universal Patterns\n\n- **Alpha** — first\n  continued\nplain column-0 line\n- **Beta** — b\n"
        alpha = self.blocks(text)[0]
        self.assertEqual(alpha["text"], "- **Alpha** — first\n  continued", "old: the column-0 line continued it")
        text = "## Universal Patterns\n\n- **Gamma** — g\n one-space line\n- **Delta** — d\n"
        self.assertEqual(self.blocks(text)[0]["text"], "- **Gamma** — g", "old: the one-space line continued it")

    def test_d5_an_entry_below_the_pointer_is_project(self):
        text = "## Universal Patterns\n\n- **Up** — u\n\n## Project tier\n\n- **Below** — b\n"
        tiers = {b["title"]: b["tier"] for b in self.blocks(text)}
        self.assertEqual(tiers, {"Up": "Universal", "Below": "Project"}, "old: Below stayed Universal")

    def test_entry_blocks_returns_legacy_entries_to_readers_with_the_keys_of_an_entry(self):
        text = "## Universal Patterns\n\n## 2026-09-02 -- Legacy term\nDefined here.\n"
        (legacy,) = self.blocks(text)
        self.assertEqual(set(legacy), {"title", "line", "tier", "text", "subs"})
        self.assertEqual((legacy["title"], legacy["line"], legacy["tier"]), ("Legacy term", 3, "Universal"))
        self.assertIn("Defined here.", legacy["text"])

    # --- J1-J5: journal_entries ----------------------------------------------------------------------------------
    def entries(self, text, **kw):
        return grd.journal_entries(text, **kw)

    def test_j1_a_dated_heading_inside_a_fence_is_not_an_entry(self):
        text = ("## Universal lessons\n\n### 2026-01-01 — Real\n- **Trigger:** manual\n```text\n"
                "### 2026-02-02 — Fake in fence\n```\n- **Source contract:** .claude/concepts/x.md\n")
        (real,) = self.entries(text)
        self.assertEqual(real["title"], "Real", "old: Fake in fence was a second entry")
        self.assertIn("### 2026-02-02 — Fake in fence", real["text"])
        self.assertEqual(real["source"], ".claude/concepts/x.md")

    def test_j2_entries_under_a_non_tier_heading_are_prose(self):
        text = ("## Universal lessons\n\n### 2026-01-01 — Real\n- **Trigger:** manual\n\n## Notes\n\n"
                "### 2026-02-02 — In notes\n- **Trigger:** manual\n")
        self.assertEqual([e["title"] for e in self.entries(text)], ["Real"], "old: In notes was an entry")

    def test_j3_the_text_ends_at_the_next_heading_of_any_level(self):
        text = ("## Universal lessons\n\n### 2026-01-01 — Real\n- **Trigger:** manual\n- **Lesson:** l\n\n"
                "### Tag conventions\n\n- **`x`** — prose\n")
        (real,) = self.entries(text)
        self.assertEqual(real["text"], "### 2026-01-01 — Real\n- **Trigger:** manual\n- **Lesson:** l",
                         "old: the Tag conventions heading and its bullets folded into the entry")
        text = "## Universal lessons\n\n### 2026-01-01 — Real\n- **Trigger:** manual\n#### Sub\nmore\n"
        self.assertEqual(self.entries(text)[0]["text"], "### 2026-01-01 — Real\n- **Trigger:** manual")

    def test_j4_a_heading_with_no_separator_or_an_en_dash_is_a_malformed_entry(self):
        text = "## Universal lessons\n\n### 2026-01-01\n- **Trigger:** manual\n\n### 2026-01-02 – En dash title\n- **Trigger:** manual\n"
        got = self.entries(text)
        self.assertEqual([(e["date"], e["title"]) for e in got], [("2026-01-01", ""), ("2026-01-02", "En dash title")],
                         "old: neither was an entry, and both folded into the previous one")
        self.assertNotIn("En dash", got[0]["text"])

    def test_j5_the_last_field_line_wins_and_indented_lines_fold_into_the_value(self):
        text = ("## Universal lessons\n\n### 2026-01-01 — T\n- **Trigger:** manual\n- **Trigger:** Pre-Approval Critic\n"
                "- **Source contract:** .claude/concepts/a.md\n  continued-b\n")
        (entry,) = self.entries(text)
        self.assertEqual(entry["trigger"], "pre-approval critic", "old: the first Trigger line won")
        self.assertEqual(entry["source"], ".claude/concepts/a.md continued-b", "old: its own line only")

    def test_journal_entries_returns_entries_only_never_legacy_ones(self):
        text = ("## Universal lessons\n\n## 2026-09-01 — Old heading\nFree text.\n\n- 2026-09-02 — Old bullet\n\n"
                "### 2026-10-01 — Real\n- **Trigger:** manual\n")
        self.assertEqual([e["title"] for e in self.entries(text)], ["Real"])

    def test_the_returned_keys_are_the_default_branch_keys(self):
        (entry,) = self.entries("## Universal lessons\n\n### 2026-10-01 — Real\n- **Trigger:** manual\n")
        self.assertEqual(set(entry), {"sig", "date", "title", "line", "tier", "trigger", "source", "text"})
        (block,) = self.blocks("- **Alpha** — a\n")
        self.assertEqual(set(block), {"title", "line", "tier", "text", "subs"})


class AccuracyParserTests(unittest.TestCase):
    """accuracy_update.parse_journal_entries: the parser the journal tracker hook calls (block 12)."""

    @classmethod
    def setUpClass(cls):
        cls.frozen = FROZEN_JOURNAL.read_text(encoding="utf-8")

    def test_the_parser_keeps_its_signature_and_keys(self):
        entries = au.parse_journal_entries(JOURNAL)
        self.assertEqual(len(entries), 3)
        self.assertEqual(set(entries[0]), {"sig", "date", "title", "trigger", "source_contract", "body"})

    def test_sig_date_title_and_trigger_equal_the_old_output_on_the_frozen_journal(self):
        new = au.parse_journal_entries(self.frozen)
        old = old_parse_entries(self.frozen)
        self.assertGreater(len(old), 20)
        self.assertEqual(len(new), len(old))
        for n, o in zip(new, old):
            self.assertEqual((n["sig"], n["date"], n["title"], n["trigger"]),
                             (o["sig"], o["date"], o["title"], o["trigger"]))

    def test_only_the_listed_source_forms_differ_from_the_old_output(self):
        text = ("### 2026-01-01 — Spaces\n- **Trigger:** manual\n- **Source contract:** `a b/c d.md`\n\n"
                "### 2026-01-02 — NotApplicable\n- **Trigger:** manual\n- **Source contract:** N/A\n")
        new = {e["title"]: e for e in au.parse_journal_entries(text)}
        old = {e["title"]: e for e in old_parse_entries(text)}
        self.assertEqual(old["Spaces"]["source_contract"], "a")
        self.assertEqual(new["Spaces"]["source_contract"], "a b/c d.md")
        self.assertEqual(old["NotApplicable"]["source_contract"], "N/A")
        self.assertEqual(new["NotApplicable"]["source_contract"], "",
                         "an N/A source no longer feeds derive_areas a non-path")
        for key in ("sig", "date", "title", "trigger"):
            self.assertEqual(new["Spaces"][key], old["Spaces"][key])

    def test_the_source_rule_is_the_one_in_the_registry_layout_module(self):
        self.assertFalse(hasattr(au, "_SOURCE_VALUE"), "the source rule lives in _registry_layout.source_value")


if __name__ == "__main__":
    unittest.main(verbosity=2)
