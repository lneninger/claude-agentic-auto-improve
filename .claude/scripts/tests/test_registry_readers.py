#!/usr/bin/env python3
"""
Tests that cross_area_scan.py and north_star_review.py read the journal and the mechanisms registry
through ``registry_files`` (the root file plus its domain files), not through one flat file.

Run: py -3 .claude/scripts/tests/test_registry_readers.py

Each fixture is a throwaway project (``CLAUDE_PROJECT_DIR``) with its own ``.claude/registries``
folder, so the resolver picks the fixture's root file and never this repository's registries.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))

import cross_area_scan  # noqa: E402
import north_star_review  # noqa: E402

MAPPING = {"billing": ["src/billing/"], "web": ["src/web/"], "api": ["src/api/"], "legacyland": ["src/legacy/"]}

CONTRACT = "# C\n\n## Reused Mechanisms\n\n- `WidgetFactory` -- builds widgets\n\n## Files to touch\n\n- src/x\n"


def journal_entry(date: str, title: str, areas: str, tags: str = "billing") -> str:
    return (
        f"### {date} — {title}\n"
        "- **Trigger:** manual\n"
        "- **Source contract:** `n/a`\n"
        f"- **Areas:** {areas}\n"
        "- **Lesson:** something\n"
        "- **Apply when:** always\n"
        f"- **Tags:** {tags}\n\n"
    )


class Fixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.proj = Path(self._tmp.name).resolve()
        self.reg = self.proj / ".claude" / "registries"
        self.reg.mkdir(parents=True)
        self._old = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.proj)
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        if self._old is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = self._old

    def put(self, rel: str, text: str) -> Path:
        path = self.reg / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class JournalSignalTests(Fixture):
    def areas(self) -> set[str]:
        return {a for a, _w, _l in cross_area_scan.journal_signal({"billing"}, MAPPING)}

    def test_flat_layout_one_unchanged(self) -> None:
        self.put("JOURNAL.md", "# Journal\n\n" + journal_entry("2026-11-01", "flat billing", "api"))
        self.assertEqual(cross_area_scan.journal_signal({"billing"}, MAPPING), [("api", 2, "journal")])

    def test_domain_file_entry_is_seen(self) -> None:
        self.put("JOURNAL.md", "<!-- registry-layout: 2 -->\n# Journal\n")
        self.put("JOURNAL/general.md", "# General\n")
        self.put("JOURNAL/frontend.md", "# Frontend\n\n" + journal_entry("2026-11-01", "web billing", "web"))
        self.assertEqual(self.areas(), {"web"})

    def test_legacy_entry_is_seen(self) -> None:
        legacy = ("## 2026-10-01 — legacy billing note\n"
                  "- **Source contract:** `n/a`\n- **Areas:** legacyland\n")
        self.put("JOURNAL.md", "# Journal\n\n" + legacy)
        self.assertEqual(self.areas(), {"legacyland"})

    def test_root_and_domain_entries_both_counted(self) -> None:
        self.put("JOURNAL.md", "# Journal\n\n" + journal_entry("2026-11-01", "root billing", "api"))
        self.put("JOURNAL/frontend.md", journal_entry("2026-11-02", "web billing", "web"))
        self.assertEqual(self.areas(), {"api", "web"})

    def test_repo_root_anchors_on_root_file(self) -> None:
        self.put("JOURNAL.md", "# Journal\n")
        self.put("JOURNAL/frontend.md", "# F\n")
        self.assertEqual(cross_area_scan.journal_repo_root(), self.proj)
        self.assertEqual(cross_area_scan.journal_path(), self.reg / "JOURNAL.md")


class MechanismsSignalTests(Fixture):
    def signal(self) -> list:
        return cross_area_scan.mechanisms_signal(CONTRACT, set(), MAPPING)

    def test_flat_layout_one_unchanged(self) -> None:
        self.put("MECHANISMS.md", "# M\n\n- **WidgetFactory** — lives in src/api/widget.py\n")
        self.assertEqual(self.signal(), [("api", 1, "mechanism:WidgetFactory")])

    def test_domain_file_entry_is_seen(self) -> None:
        self.put("MECHANISMS.md", "<!-- registry-layout: 2 -->\n# M\n")
        self.put("MECHANISMS/backend.md", "# B\n\n- **WidgetFactory** — lives in src/api/widget.py\n")
        self.assertEqual(self.signal(), [("api", 1, "mechanism:WidgetFactory")])

    def test_legacy_dated_heading_entry_is_seen(self) -> None:
        self.put("MECHANISMS.md",
                 "# M\n\n## 2026-10-01 — WidgetFactory\n\nWidgetFactory lives in src/legacy/widget.py\n")
        self.assertEqual({a for a, _w, _l in self.signal()}, {"legacyland"})

    def test_window_does_not_span_files(self) -> None:
        self.put("MECHANISMS.md", "# M\n\n- **WidgetFactory** — root text\n")
        self.put("MECHANISMS/backend.md", "src/api/other.py is elsewhere\n")
        self.assertEqual(self.signal(), [])


class NorthStarReaderTests(Fixture):
    def names(self, files: list) -> list:
        return [Path(p).name for p in files]

    def test_journal_files_include_domain_files(self) -> None:
        self.put("JOURNAL.md", "# J\n")
        self.put("JOURNAL/frontend.md", "# F\n")
        self.assertEqual(self.names(north_star_review.journal_files()), ["JOURNAL.md", "frontend.md"])

    def test_mechanisms_files_include_domain_files(self) -> None:
        self.put("MECHANISMS.md", "# M\n")
        self.put("MECHANISMS/backend.md", "# B\n")
        self.assertEqual(self.names(north_star_review.mechanisms_files()), ["MECHANISMS.md", "backend.md"])

    def test_registry_text_joins_every_file(self) -> None:
        self.put("MECHANISMS.md", "root-marker\n")
        self.put("MECHANISMS/backend.md", "domain-marker\n")
        text = north_star_review.registry_text(north_star_review.mechanisms_files())
        self.assertIn("root-marker", text)
        self.assertIn("domain-marker", text)

    def test_flat_layout_one_unchanged(self) -> None:
        self.put("JOURNAL.md", "flat-journal\n")
        self.assertEqual(self.names(north_star_review.journal_files()), ["JOURNAL.md"])
        self.assertEqual(north_star_review.registry_text(north_star_review.journal_files()), "flat-journal\n")
        self.assertEqual(north_star_review.journal_path(), self.reg / "JOURNAL.md")


if __name__ == "__main__":
    unittest.main(verbosity=2)
