#!/usr/bin/env python3
"""
Tests for the registry layout reader (_registry_layout.py), the structure lint
(validate_registries.py --check-structure), the strict digest
(generate_registry_digest.py) and the three general.md skeletons.

Run: py -3 .claude/scripts/tests/test_registry_layout.py
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

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "registry-layout"
sys.path.insert(0, str(SCRIPTS_DIR))

import _registry_layout as rl  # noqa: E402

VALIDATE = SCRIPTS_DIR / "validate_registries.py"
DIGEST = SCRIPTS_DIR / "generate_registry_digest.py"
TEMPLATES = REPO_ROOT / ".claude" / "templates" / "registries"
NO_PLUGIN = "__no_such_plugin_root__"

MARK = "<!-- registry-layout: 2 -->"


def write(root: Path, rel: str, text: str | bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_bytes(text.encode("utf-8"))
    return path


def reg(root: Path) -> Path:
    return root / ".claude" / "registries"


def mv_root(registry: str, body: str, *, marked: bool, pointer: bool = False, tail: str = "") -> str:
    head = (MARK + "\n") if marked else ""
    text = head + f"# {registry} registry\n\n> header prose\n\n## Universal Patterns\n\n{body}\n"
    if pointer:
        text += "\n" + rl.pointer_section(registry)
    return text + tail


def journal_root(body: str, *, marked: bool, pointer: bool = False, tail: str = "") -> str:
    head = (MARK + "\n") if marked else ""
    text = head + f"# Journal\n\n> header prose\n\n## Universal lessons\n\n{body}\n"
    if pointer:
        text += "\n" + rl.pointer_section("JOURNAL")
    return text + tail


M_BODY = "- **Alpha** *(2026-01-01)* — the alpha body.\n  continuation line.\n- **Beta** — the beta body."
V_BODY = "- **Term One** — defined here.\n- **Term Two** -- defined too."


def jentry(date: str, title: str, *, apply_when: str = "when X happens", trigger: str = "manual",
           tags: str = "`a, b`") -> str:
    return (f"### {date} — {title}\n- **Trigger:** {trigger}\n- **Source contract:** N/A\n"
            f"- **Lesson:** do the thing.\n- **Apply when:** {apply_when}\n- **Tags:** {tags}\n")


J_BODY = jentry("2026-10-01", "First lesson") + "\n" + jentry("2026-10-02", "Second lesson")


def make_layout1(root: Path, m: str = M_BODY, v: str = V_BODY, j: str = J_BODY) -> Path:
    write(root, ".claude/registries/MECHANISMS.md", mv_root("MECHANISMS", m, marked=False))
    write(root, ".claude/registries/VOCABULARY.md", mv_root("VOCABULARY", v, marked=False))
    write(root, ".claude/registries/JOURNAL.md", journal_root(j, marked=False))
    return reg(root)


def make_layout2(root: Path, m: str = M_BODY, v: str = V_BODY, j: str = J_BODY,
                 with_general: bool = True) -> Path:
    write(root, ".claude/registries/MECHANISMS.md", mv_root("MECHANISMS", m, marked=True, pointer=True))
    write(root, ".claude/registries/VOCABULARY.md", mv_root("VOCABULARY", v, marked=True, pointer=True))
    write(root, ".claude/registries/JOURNAL.md", journal_root(j, marked=True, pointer=True))
    if with_general:
        write(root, ".claude/registries/MECHANISMS/general.md", "# Mechanisms - general\n")
        write(root, ".claude/registries/VOCABULARY/general.md", "# Vocabulary - general\n")
        write(root, ".claude/registries/JOURNAL/general.md", "# Journal - general\n")
    return reg(root)


class TmpCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        self.home = Path(self._tmp.name) / "home"
        self.home.mkdir()

    def run_cli(self, script: Path, *args: str, root: Path | None = None,
                env_extra: dict | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.pop("CLAUDE_PROJECT_DIR", None)
        env.update(env_extra or {})
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        env["CLAUDE_CONFIG_DIR"] = str(self.home)
        env["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                              encoding="utf-8", env=env, cwd=str(root or self.root))

    def lint(self, *extra: str, root: Path | None = None) -> subprocess.CompletedProcess:
        return self.run_cli(VALIDATE, "--check-structure", "--project", str(root or self.root),
                            "--plugin-root", str(self.root / NO_PLUGIN), *extra, root=root)

    def findings(self, rule: str | None = None, **kw):
        report = rl.check_structure(reg(self.root), project_root=self.root, **kw)
        found = report.findings
        return [f for f in found if rule is None or f.rule == rule]


def parse(text: str, registry: str = "MECHANISMS", kind: str = "root", slug: str | None = None):
    return rl.parse_text(text, registry, kind=kind, slug=slug, file="x.md")


# ---------------------------------------------------------------------------
class KeyAndGrammarTests(unittest.TestCase):
    def test_entry_key_normalises(self):
        self.assertEqual(rl.entry_key("  Foo   BAR\tbaz "), "foo bar baz")
        self.assertEqual(rl.entry_key("Foo *(2026-01-01)*"), "foo")

    def test_mv_separators_and_date_tag(self):
        text = ("## Universal Patterns\n- **One** *(2026-01-01)* — em body\n- **Two** -- dash body\n"
                "- **Three** - hyphen body\n- **Four** — body\n")
        entries = parse(text).entries
        self.assertEqual([e.title for e in entries], ["One", "Two", "Three", "Four"])
        self.assertEqual([e.key for e in entries], ["one", "two", "three", "four"])
        self.assertEqual(entries[0].text.strip().startswith("em body"), True)
        self.assertEqual(entries[1].text.strip(), "dash body")
        self.assertTrue(all(e.has_body for e in entries))
        self.assertEqual(entries[0].tier, "universal")

    def test_mv_continuation_and_status_and_correction(self):
        text = ("## Universal Patterns\n- **One** — first line\n  second line\n  - **Correction (2026-02-01, src):** fix\n"
                "- **Gone** —\n  - **Status:** archived-title-only\n- **Empty** —\n\n")
        entries = {e.title: e for e in parse(text).entries}
        self.assertIn("second line", entries["One"].text)
        self.assertIn("Correction", entries["One"].text)
        self.assertEqual(entries["Gone"].status, "archived-title-only")
        self.assertFalse(entries["Gone"].has_body)
        self.assertFalse(entries["Empty"].has_body)
        self.assertEqual(entries["Empty"].status, "active")

    def test_crlf_and_bom_read_like_lf(self):
        text = "﻿## Universal Patterns\r\n" + M_BODY.replace("\n", "\r\n") + "\r\n"
        entries = parse(text).entries
        self.assertEqual([e.title for e in entries], ["Alpha", "Beta"])
        self.assertNotIn("\r", entries[0].text)

    def test_fenced_sample_is_never_parsed(self):
        text = ("## Universal Patterns\n```markdown\n- **Fake** — in a fence\n```\n- **Real** — outside\n"
                "````\n```\n- **Fake2** — inner\n```\n````\n")
        self.assertEqual([e.title for e in parse(text).entries], ["Real"])

    def test_journal_entry_grammar(self):
        text = "## Universal lessons\n\n" + jentry("2026-10-01", "A lesson") + jentry("2026-10-02", "B lesson")
        entries = parse(text, "JOURNAL").entries
        self.assertEqual([e.title for e in entries], ["A lesson", "B lesson"])
        self.assertEqual(entries[0].date, "2026-10-01")
        self.assertEqual(entries[0].fields["trigger"], "manual")
        self.assertTrue(entries[0].has_body)
        self.assertEqual(entries[0].kind, "entry")

    def test_journal_separators(self):
        text = "### 2026-10-01 -- Dash\n- **Apply when:** x\n### 2026-10-02 - Hyphen\n- **Apply when:** y\n"
        self.assertEqual([e.title for e in parse(text, "JOURNAL").entries], ["Dash", "Hyphen"])

    def test_tag_conventions_section_is_prose(self):
        text = ("## Entry shape\n\n### Tag conventions\n\n- **`ui-evolution`** — set on lessons\n- **`app:<name>`** — optional\n\n"
                "## Universal lessons\n\n" + jentry("2026-10-01", "Real"))
        parsed = parse(text, "JOURNAL")
        self.assertEqual([e.title for e in parsed.entries], ["Real"])

    def test_notes_section_bullets_are_prose(self):
        text = ("## Universal Patterns\n- **Real** — body\n\n## Notes\n\n- **Not an entry** — prose\n- **Also not** — prose\n")
        parsed = parse(text)
        self.assertEqual([e.title for e in parsed.entries], ["Real"])

    def test_prose_section_ends_at_same_or_higher_heading(self):
        text = "## Notes\n- **Prose** — a\n### Deeper\n- **Still prose** — b\n## Universal Patterns\n- **Real** — c\n"
        self.assertEqual([e.title for e in parse(text).entries], ["Real"])

    def test_legacy_dated_heading_is_a_keyed_legacy_entry(self):
        text = "## Universal lessons\n\n## 2026-09-01 — Old way\nFree text lesson.\n\n### Not shape\n"
        entries = parse(text, "JOURNAL").entries
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].kind, "legacy")
        self.assertEqual(entries[0].status, "legacy")
        self.assertEqual(entries[0].key, "old way")
        self.assertIn("Free text", entries[0].text)

    def test_legacy_dated_bullet_in_a_journal(self):
        text = "## Universal lessons\n\n- 2026-09-02 — Bullet lesson\n  more text\n- **not dated** — x\n"
        entries = parse(text, "JOURNAL").entries
        self.assertEqual([(e.kind, e.key) for e in entries], [("legacy", "bullet lesson")])

    def test_tier_tracking_on_layout1(self):
        text = "## Universal Patterns\n- **U** — a\n## Project: Acme\n- **P** — b\n"
        entries = parse(text).entries
        self.assertEqual([e.tier for e in entries], ["universal", "project:Acme"])

    def test_domain_file_tier(self):
        entries = parse("- **D** — a\n", kind="domain", slug="backend").entries
        self.assertEqual(entries[0].tier, "domain:backend")


class PathReferenceTests(unittest.TestCase):
    def test_rejections(self):
        for span in ("?? d/f.txt", '"$CLAUDE_PROJECT_DIR"/.claude/hooks/x.py', "../a/b.md",
                     "JOURNAL/frontend.md:33", "./a/b.md", "/abs/x.md", "noslash.md", "dir/noext",
                     "<project>/.claude/x.json", "a/b.toolongext12"):
            self.assertEqual(rl.path_references(f"see `{span}` here"), [], span)

    def test_acceptances(self):
        self.assertEqual(rl.path_references("a `.claude/concepts/x.md` b"), [".claude/concepts/x.md"])
        self.assertEqual(rl.path_references("`src\\app\\x.cs` and `a/b-c_d.py`"), ["src\\app\\x.cs", "a/b-c_d.py"])


# ---------------------------------------------------------------------------
class LayoutStateTests(TmpCase):
    def state(self) -> rl.LayoutState:
        return rl.layout_state(reg(self.root))

    def test_absent(self):
        reg(self.root).mkdir(parents=True)
        s = self.state()
        self.assertEqual(s.state, "absent")
        self.assertEqual(s.marker, "none")
        self.assertIn("plugin_doctor.py --fix", s.remedy)

    def test_absent_when_folder_missing(self):
        self.assertEqual(self.state().state, "absent")

    def test_unknown_one_or_two_roots_missing(self):
        make_layout1(self.root)
        (reg(self.root) / "VOCABULARY.md").unlink()
        s = self.state()
        self.assertEqual(s.state, "unknown")
        self.assertIn("registry-missing:VOCABULARY", s.reasons)
        self.assertIn("plugin_doctor.py --fix", s.remedy)
        (reg(self.root) / "JOURNAL.md").unlink()
        s = self.state()
        self.assertEqual(s.state, "unknown")
        self.assertEqual(sorted(r for r in s.reasons if r.startswith("registry-missing:")),
                         ["registry-missing:JOURNAL", "registry-missing:VOCABULARY"])

    def test_unknown_other_marker_value(self):
        make_layout1(self.root)
        p = reg(self.root) / "JOURNAL.md"
        p.write_bytes(b"<!-- registry-layout: 3 -->\n" + p.read_bytes())
        s = self.state()
        self.assertEqual(s.state, "unknown")
        self.assertEqual(s.marker, "3")
        self.assertIn("make the root markers agree", s.remedy)

    def test_unknown_mixed_markers(self):
        make_layout2(self.root)
        p = reg(self.root) / "VOCABULARY.md"
        p.write_bytes(p.read_bytes().replace((MARK + "\n").encode(), b""))
        self.assertEqual(self.state().state, "unknown")

    def test_pending(self):
        make_layout1(self.root)
        s = self.state()
        self.assertEqual(s.state, "pending")
        self.assertEqual(s.marker, "none")
        self.assertIn("registry_migrate.py --dry-run", s.remedy)

    def test_marker_not_on_line_one_does_not_count(self):
        make_layout1(self.root)
        p = reg(self.root) / "MECHANISMS.md"
        p.write_bytes(b"# t\n" + MARK.encode() + b"\n" + p.read_bytes())
        self.assertEqual(self.state().state, "pending")

    def test_current(self):
        make_layout2(self.root)
        s = self.state()
        self.assertEqual(s.state, "current")
        self.assertEqual(s.marker, "2")
        self.assertEqual(s.layout_current, 2)
        self.assertEqual(s.reasons, [])
        as_dict = s.as_dict()
        self.assertEqual(as_dict["state"], "current")
        self.assertEqual(as_dict["layout_current"], 2)

    def test_stale_sync_project_heading_in_root(self):
        make_layout2(self.root)
        p = reg(self.root) / "MECHANISMS.md"
        p.write_bytes(p.read_bytes().replace(b"## Universal Patterns", b"## Project: Acme\n\n## Universal Patterns"))
        s = self.state()
        self.assertEqual(s.state, "stale-sync")
        self.assertTrue(s.reasons)
        self.assertIn("registry_migrate.py --dry-run", s.remedy)

    def test_stale_sync_entry_below_pointer(self):
        make_layout2(self.root)
        p = reg(self.root) / "JOURNAL.md"
        p.write_bytes(p.read_bytes() + jentry("2026-10-09", "Below").encode())
        self.assertEqual(self.state().state, "stale-sync")

    def test_stale_sync_leftover_below_pointer(self):
        make_layout2(self.root)
        p = reg(self.root) / "VOCABULARY.md"
        p.write_bytes(p.read_bytes() + (rl.LEFTOVERS_HEADING + "\n").encode())
        self.assertEqual(self.state().state, "stale-sync")

    def test_stale_sync_general_missing(self):
        make_layout2(self.root, with_general=False)
        write(self.root, ".claude/registries/MECHANISMS/general.md", "# g\n")
        write(self.root, ".claude/registries/VOCABULARY/general.md", "# g\n")
        s = self.state()
        self.assertEqual(s.state, "stale-sync")
        self.assertTrue(any("JOURNAL" in r for r in s.reasons))

    def test_pointer_text_is_generic(self):
        for name in rl.REGISTRIES:
            text = rl.pointer_section(name)
            self.assertTrue(text.startswith("## Project tier"))
            self.assertIn(f"{name}/<domain>.md", text)
            self.assertIn("general.md", text)
            self.assertNotIn("backend", text)


# ---------------------------------------------------------------------------
class RuleTests(TmpCase):
    def test_clean_current_layout_has_no_findings(self):
        make_layout2(self.root)
        self.assertEqual(self.findings(), [])

    def test_r1_journal_bodiless_fails_and_passes(self):
        make_layout2(self.root, j=jentry("2026-10-01", "Bodiless", apply_when=""))
        hits = self.findings("R1")
        self.assertEqual([h.key for h in hits], ["bodiless"])
        self.assertEqual(hits[0].severity, "finding")
        make_layout2(self.root)
        self.assertEqual(self.findings("R1"), [])

    def test_r1_mv_empty_body(self):
        make_layout2(self.root, m="- **Hollow** —\n- **Full** — body")
        self.assertEqual([h.key for h in self.findings("R1")], ["hollow"])

    def test_r1_exempt_archived_legacy_and_prose(self):
        j = ("### 2026-10-01 — Archived\n- **Status:** archived-title-only\n\n" +
             "## 2026-09-01 — Legacy\nno fields at all\n\n## Notes\n\n### 2026-10-05 — prose heading in a notes section\n")
        make_layout2(self.root, m="- **Gone** —\n  - **Status:** archived-title-only", j=j)
        self.assertEqual(self.findings("R1"), [])
        self.assertEqual(self.findings("A1"), [])

    def test_r2_duplicate_across_root_and_domain(self):
        make_layout2(self.root)
        write(self.root, ".claude/registries/MECHANISMS/backend.md", "- **ALPHA** — again\n")
        hits = self.findings("R2")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].key, "alpha")
        self.assertIn("MECHANISMS.md", hits[0].message)
        self.assertIn("backend.md", hits[0].message)

    def test_r2_applies_to_legacy_entries(self):
        j = jentry("2026-10-01", "Twin") + "\n## 2026-09-01 — Twin\nlegacy copy\n"
        make_layout2(self.root, j=j)
        self.assertEqual([h.key for h in self.findings("R2")], ["twin"])

    def test_r2_unique_passes(self):
        make_layout2(self.root)
        write(self.root, ".claude/registries/MECHANISMS/backend.md", "- **Gamma** — distinct\n")
        self.assertEqual(self.findings("R2"), [])

    def test_r3_project_heading_in_root(self):
        make_layout2(self.root)
        p = reg(self.root) / "MECHANISMS.md"
        p.write_bytes(p.read_bytes().replace(b"## Universal Patterns", b"## Project: Acme\n\n## Universal Patterns"))
        self.assertEqual([h.rule for h in self.findings("R3")], ["R3"])

    def test_r3_entry_below_pointer(self):
        make_layout2(self.root)
        p = reg(self.root) / "VOCABULARY.md"
        p.write_bytes(p.read_bytes() + b"\n- **Stray** - below the pointer\n")
        hits = self.findings("R3")
        self.assertEqual([h.key for h in hits], ["stray"])
        # An entry below the pointer makes the tree stale-sync, and a tree that is not current is advisory.
        self.assertEqual(hits[0].severity, "advisory")
        self.assertEqual(rl.layout_state(reg(self.root)).state, "stale-sync")

    def test_r3_token_client_authored_is_a_finding(self):
        make_layout2(self.root, m="- **Alpha** — mentions AcmeCorp inside\n- **Beta** — clean")
        hits = self.findings("R3", tokens=("acmecorp",), plugin_keys={"MECHANISMS": frozenset({"beta"})})
        self.assertEqual([(h.key, h.severity, h.variant) for h in hits], [("alpha", "finding", "")])

    def test_r3_token_plugin_owned_is_advisory(self):
        make_layout2(self.root, m="- **Alpha** — mentions AcmeCorp inside")
        hits = self.findings("R3", tokens=("acmecorp",), plugin_keys={"MECHANISMS": frozenset({"alpha"})})
        self.assertEqual([(h.key, h.severity, h.variant) for h in hits], [("alpha", "advisory", "plugin-owned")])

    def test_r3_token_unverified_without_plugin_root(self):
        make_layout2(self.root, m="- **Alpha** — mentions AcmeCorp inside")
        hits = self.findings("R3", tokens=("acmecorp",), plugin_keys=None)
        self.assertEqual([(h.severity, h.variant) for h in hits], [("advisory", "unverified")])

    def test_r3_allowed_string_is_honoured(self):
        make_layout2(self.root, m="- **Alpha** — see AcmeCorp-Public docs")
        hits = self.findings("R3", tokens=("acmecorp",), allowed=("AcmeCorp-Public",),
                             plugin_keys={"MECHANISMS": frozenset({"alpha"})})
        self.assertEqual(hits, [])

    def test_r3_universal_candidate(self):
        make_layout2(self.root, m="- **Alpha** — x\n- **Beta** — y")
        hits = self.findings("R3", plugin_keys={"MECHANISMS": frozenset({"beta"}), "VOCABULARY": frozenset({"term one", "term two"}),
                                                "JOURNAL": frozenset({"first lesson", "second lesson"})})
        self.assertEqual([(h.key, h.severity, h.variant) for h in hits], [("alpha", "advisory", "universal-candidate")])
        self.assertEqual(self.findings("R3", plugin_keys=None), [])

    def test_r4_dead_reference_is_advisory(self):
        make_layout2(self.root, m="- **Alpha** — see `docs/gone.md` and `docs/here.md`")
        write(self.root, "docs/here.md", "x")
        hits = self.findings("R4")
        self.assertEqual([(h.message, h.severity) for h in hits], [("docs/gone.md", "advisory")])
        self.assertGreater(hits[0].line, 0)

    def test_r4_fences_and_leftovers_are_skipped(self):
        make_layout2(self.root)
        write(self.root, ".claude/registries/MECHANISMS/general.md",
              "# g\n- **Mine** — fine\n```\n`docs/fenced.md`\n```\n\n" + rl.LEFTOVERS_HEADING +
              "\n\n<!-- leftover from MECHANISMS.md:3-4, project-prose -->\n```\nsee `docs/leftover.md`\n```\n")
        self.assertEqual(self.findings("R4"), [])

    def test_r4_excluded_prefix_is_skipped(self):
        refs = " ".join(f"`{p}x.json`" for p in rl.R4_EXCLUDED_PREFIXES if p.endswith("/")) + \
            " `.claude/settings.json` `.claude/settings.local.json` `.claude/.sync-config.json` `.claude/hook-registration-profile.json`"
        make_layout2(self.root, m=f"- **Alpha** — {refs}")
        self.assertEqual(self.findings("R4"), [])

    def test_r4_path_only_under_plugin_root_resolves(self):
        make_layout2(self.root, m="- **Alpha** — see `agents/thing.md`")
        plugin = self.root.parent / "plug"
        write(plugin, "agents/thing.md", "x")
        self.assertEqual(len(self.findings("R4")), 1)
        self.assertEqual(self.findings("R4", plugin_root=plugin), [])

    def test_r4_strict_makes_exit_one_on_current(self):
        make_layout2(self.root, m="- **Alpha** — see `docs/gone.md`")
        report = rl.check_structure(reg(self.root), project_root=self.root)
        self.assertEqual(report.exit_code(strict=False), 0)
        self.assertEqual(report.exit_code(strict=True), 1)

    def test_r5_general_missing_and_bad_names(self):
        make_layout2(self.root, with_general=False)
        write(self.root, ".claude/registries/MECHANISMS/Bad_Name.md", "x\n")
        (reg(self.root) / "VOCABULARY" / "nested").mkdir(parents=True)
        (reg(self.root) / "INTEGRATION").mkdir(parents=True)
        files = {Path(h.file).as_posix() for h in self.findings("R5")}
        self.assertTrue(any(f.endswith("MECHANISMS/general.md") for f in files), files)
        self.assertTrue(any(f.endswith("MECHANISMS/Bad_Name.md") for f in files), files)
        self.assertTrue(any(f.endswith("VOCABULARY/nested") for f in files), files)
        self.assertTrue(any(f.endswith("INTEGRATION") for f in files), files)

    def test_r5_passes_with_valid_domains_and_skips_pending_without_folder(self):
        make_layout2(self.root)
        write(self.root, ".claude/registries/MECHANISMS/back-end2.md", "x\n")
        self.assertEqual(self.findings("R5"), [])
        shutil.rmtree(self.root)
        self.root.mkdir()
        make_layout1(self.root)
        self.assertEqual(self.findings("R5"), [])

    def test_r6_digest_states(self):
        make_layout2(self.root)
        digest = self.root / ".claude" / ".scout-cache" / "registry-digest.md"
        report = rl.check_structure(reg(self.root), project_root=self.root, digest_path=digest)
        self.assertEqual(report.digest, "absent")
        self.assertEqual([f for f in report.findings if f.rule == "R6"], [])
        self.assertIn("digest: absent", report.lines())
        # Missing hash line.
        write(self.root, ".claude/.scout-cache/registry-digest.md", "# Registry Digest\n- Alpha [x:1]\n")
        self.assertEqual(len(self.findings("R6", digest_path=digest)), 1)
        # Matching hash and every key present.
        entries = rl.collect_entries(reg(self.root))
        lines = ["# Registry Digest", f"<!-- registry-sources-sha256: {rl.sources_sha256(reg(self.root))} -->"]
        lines += [f"- {rl.digest_title(e)} [x:{e.line}]" for e in entries]
        digest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertEqual(self.findings("R6", digest_path=digest), [])
        # A registry key absent from the digest.
        digest.write_text("\n".join(lines[:3]) + "\n", encoding="utf-8")
        self.assertEqual(len(self.findings("R6", digest_path=digest)), 1)
        # A changed source.
        digest.write_text("\n".join(lines) + "\n", encoding="utf-8")
        write(self.root, ".claude/registries/MECHANISMS/general.md", "- **New** — body\n")
        self.assertEqual(len(self.findings("R6", digest_path=digest)), 1)

    def test_a1_journal_malformed(self):
        j = ("### 2026-13-45 — Bad date\n- **Trigger:** manual\n- **Source contract:** N/A\n- **Lesson:** l\n- **Apply when:** w\n- **Tags:** t\n\n"
             "### 2026-10-02 No separator\n- **Trigger:** manual\n- **Source contract:** N/A\n- **Lesson:** l\n- **Apply when:** w\n- **Tags:** t\n\n"
             "### 2026-10-03 — Missing lesson\n- **Trigger:** manual\n- **Source contract:** N/A\n- **Apply when:** w\n- **Tags:** t\n\n" +
             jentry("2026-10-04", "Bad trigger", trigger="whenever"))
        make_layout2(self.root, j=j)
        hits = self.findings("A1")
        self.assertEqual(len(hits), 4, [h.message for h in hits])
        self.assertTrue(all(h.severity == "finding" for h in hits))

    def test_a1_mv_missing_separator_and_pass(self):
        make_layout2(self.root, m="- **NoSep** just text\n- **Fine** — ok")
        self.assertEqual([h.key for h in self.findings("A1")], ["nosep"])
        make_layout2(self.root)
        self.assertEqual(self.findings("A1"), [])

    def test_legacy_and_leftover_are_notices_not_findings(self):
        j = jentry("2026-10-01", "Real") + "\n## 2026-09-01 — Old\nlegacy\n"
        make_layout2(self.root, j=j)
        write(self.root, ".claude/registries/JOURNAL/general.md",
              "# g\n\n" + rl.LEFTOVERS_HEADING + "\n\n<!-- leftover from JOURNAL.md:3-4, project-prose -->\n```\nprose\n```\n")
        report = rl.check_structure(reg(self.root), project_root=self.root)
        self.assertEqual(report.findings, [])
        text = "\n".join(report.lines())
        self.assertIn("advisory: legacy .claude/registries/JOURNAL.md:", text)
        self.assertIn("advisory: leftover .claude/registries/JOURNAL/general.md:", text)
        self.assertEqual(report.exit_code(strict=True), 0)


# ---------------------------------------------------------------------------
class ModeAndCliTests(TmpCase):
    def test_not_current_is_advisory_with_layout_line_exit_zero(self):
        make_layout1(self.root, m="- **Hollow** —\n- **Dup** — a\n- **Dup** — b")
        done = self.lint()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("advisory: registry layout pending", done.stdout)
        self.assertIn("registry_migrate.py --dry-run", done.stdout)
        self.assertIn("advisory: R1", done.stdout)
        self.assertIn("advisory: R2", done.stdout)
        self.assertNotIn("finding:", done.stdout)
        self.assertEqual(self.lint("--strict").returncode, 0)

    def test_current_exits_one_on_a_finding(self):
        make_layout2(self.root, m="- **Hollow** —")
        done = self.lint()
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("finding: R1", done.stdout)

    def test_current_clean_exits_zero_and_strict_catches_r4(self):
        make_layout2(self.root, m="- **Alpha** — see `docs/gone.md`")
        done = self.lint()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("advisory: R4", done.stdout)
        self.assertIn("docs/gone.md", done.stdout)
        strict = self.lint("--strict")
        self.assertEqual(strict.returncode, 1, strict.stdout)

    def test_absent_and_unknown_are_advisory(self):
        reg(self.root).mkdir(parents=True)
        done = self.lint()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("advisory: registry layout absent", done.stdout)
        make_layout1(self.root)
        (reg(self.root) / "JOURNAL.md").unlink()
        done = self.lint()
        self.assertEqual(done.returncode, 0)
        self.assertIn("advisory: registry layout unknown", done.stdout)

    def test_default_mode_keeps_its_exit_code(self):
        make_layout2(self.root, m="- **Alpha** — see `docs/gone.md`")
        done = self.run_cli(VALIDATE, root=self.root, env_extra={"CLAUDE_PROJECT_DIR": str(self.root)})
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("Registry Validation Report", done.stdout)

    def test_cli_reads_tokens_file_and_plugin_root(self):
        make_layout2(self.root, m="- **Alpha** — mentions AcmeCorp")
        write(self.root, ".claude/.project-tokens.json", json.dumps({"tokens": ["acmecorp"], "allowed": []}))
        done = self.lint()
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("R3 unverified", done.stdout)
        plugin = self.root.parent / "plug"
        write(plugin, ".claude-plugin/plugin.json", json.dumps({"name": "agentic-auto-improve"}))
        write(plugin, ".claude/registries/MECHANISMS.md", "## Universal Patterns\n- **Other** — x\n")
        write(plugin, ".claude/registries/VOCABULARY.md", "## Universal Vocabulary\n- **Other** — x\n")
        write(plugin, ".claude/registries/JOURNAL.md", "## Universal lessons\n")
        done = self.run_cli(VALIDATE, "--check-structure", "--project", str(self.root), "--plugin-root", str(plugin))
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("finding: R3", done.stdout)

    def test_exit_two_when_the_project_has_no_claude_folder(self):
        done = self.run_cli(VALIDATE, "--check-structure", "--project", str(self.root / "nowhere"))
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)

    def test_missing_module_is_named_with_exit_two(self):
        # Run the lint from a copy of the scripts folder that lacks the new module.
        copy = Path(self._tmp.name) / "scripts_copy"
        shutil.copytree(SCRIPTS_DIR.parent, copy.parent / "claude_copy", ignore=shutil.ignore_patterns("tests", "__pycache__"))
        scripts = copy.parent / "claude_copy" / "scripts"
        (scripts / "_registry_layout.py").unlink()
        make_layout2(self.root)
        env = dict(os.environ)
        env.pop("CLAUDE_PROJECT_DIR", None)
        done = subprocess.run([sys.executable, str(scripts / "validate_registries.py"), "--check-structure",
                               "--project", str(self.root)], capture_output=True, text=True, encoding="utf-8", env=env)
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn("_registry_layout", done.stderr)


SKIP_PREFIX = "advisory: R3 universal-candidate skipped"


class PluginOwnManifestSkipTests(TmpCase):
    """W5 (Q19 a): a project that holds the plugin's own manifest gets no R3 universal-candidate advisories."""

    def plugin(self, *, same_entries: bool) -> Path:
        plugin = self.root.parent / "plug"
        write(plugin, ".claude-plugin/plugin.json", json.dumps({"name": "agentic-auto-improve"}))
        if same_entries:
            make_layout1(plugin)
        else:
            write(plugin, ".claude/registries/MECHANISMS.md", "## Universal Patterns\n- **Other** — x\n")
            write(plugin, ".claude/registries/VOCABULARY.md", "## Universal Vocabulary\n- **Other** — x\n")
            write(plugin, ".claude/registries/JOURNAL.md", "## Universal lessons\n")
        return plugin

    def structure(self, plugin: Path, *, manifest: bool, tokens: bool = False, m: str = M_BODY):
        make_layout2(self.root, m=m)
        if manifest:
            write(self.root, ".claude-plugin/plugin.json", json.dumps({"name": "agentic-auto-improve"}))
        if tokens:
            write(self.root, ".claude/.project-tokens.json", json.dumps({"tokens": ["acmecorp"], "allowed": []}))
        return self.run_cli(VALIDATE, "--check-structure", "--project", str(self.root), "--plugin-root", str(plugin))

    @staticmethod
    def candidate_lines(done) -> list:
        return [ln for ln in done.stdout.splitlines()
                if ln.startswith("advisory: R3 universal-candidate") and not ln.startswith(SKIP_PREFIX)]

    def test_manifest_and_candidates_gives_the_skip_line_and_no_candidate_lines(self):
        plugin = self.plugin(same_entries=False)
        without = self.structure(plugin, manifest=False)
        listed = self.candidate_lines(without)
        self.assertEqual(len(listed), 6, without.stdout)
        shutil.rmtree(self.root)
        self.root.mkdir()
        done = self.structure(plugin, manifest=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.candidate_lines(done), [])
        skips = [ln for ln in done.stdout.splitlines() if ln.startswith(SKIP_PREFIX)]
        self.assertEqual(skips, ["advisory: R3 universal-candidate skipped: 6 entries; "
                                 "this project holds the plugin's own manifest"])
        self.assertTrue(skips[0].isascii())

    def test_manifest_and_no_candidates_gives_no_skip_line(self):
        done = self.structure(self.plugin(same_entries=True), manifest=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotIn("universal-candidate", done.stdout)

    def test_the_same_project_without_the_manifest_still_lists_the_candidates(self):
        done = self.structure(self.plugin(same_entries=False), manifest=False)
        self.assertEqual(len(self.candidate_lines(done)), 6, done.stdout)
        self.assertNotIn(SKIP_PREFIX, done.stdout)

    def test_a_token_bearing_client_entry_stays_a_finding_with_the_manifest_present(self):
        done = self.structure(self.plugin(same_entries=False), manifest=True, tokens=True,
                              m=M_BODY + "\n- **Gamma** — mentions AcmeCorp")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("finding: R3 ", done.stdout)
        self.assertIn("'Gamma'", done.stdout)
        self.assertEqual(self.candidate_lines(done), [])


class DigestTests(TmpCase):
    def digest_text(self) -> str:
        return (self.root / ".claude" / ".scout-cache" / "registry-digest.md").read_text(encoding="utf-8")

    def gen(self) -> subprocess.CompletedProcess:
        return self.run_cli(DIGEST, "--project", str(self.root))

    def test_domains_are_discovered_labelled_and_hashed(self):
        make_layout2(self.root)
        write(self.root, ".claude/registries/MECHANISMS/ops.md", "- **Ops thing** — body\n")
        write(self.root, ".claude/registries/JOURNAL/ops.md", jentry("2026-10-05", "Ops lesson"))
        write(self.root, ".claude/registries/INTEGRATION.md", "# Integration\n\n## Surface A\n\n### Sub B\n")
        done = self.gen()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        text = self.digest_text()
        self.assertIn("Ops thing", text)
        self.assertIn("Ops lesson", text)
        self.assertIn("domain:ops", text)
        self.assertIn("Universal", text)
        self.assertIn("Surface A", text)
        self.assertIn(f"<!-- registry-sources-sha256: {rl.sources_sha256(reg(self.root))} -->", text)
        # Round trip: a fresh digest is not stale.
        self.assertEqual(self.findings("R6", digest_path=self.root / ".claude" / ".scout-cache" / "registry-digest.md"), [])

    def test_project_tier_label_and_legacy_entries_are_indexed(self):
        j = "- 2026-09-02 — Bullet legacy\n\n" + jentry("2026-10-01", "Real") + "\n## 2026-09-01 — Old legacy\nbody\n"
        make_layout1(self.root, m="- **U** — u\n\n## Project: Acme\n\n- **P** — p", j=j)
        self.assertEqual(self.gen().returncode, 0)
        text = self.digest_text()
        self.assertIn("project:Acme", text)
        self.assertIn("Old legacy", text)
        self.assertIn("Bullet legacy", text)
        self.assertIn("Real", text)

    def test_exit_one_on_r1_and_r2_but_index_still_written(self):
        make_layout2(self.root, m="- **Hollow** —\n- **Twin** — a\n- **Twin** — b")
        done = self.gen()
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("R1", done.stdout)
        self.assertIn("R2", done.stdout)
        text = self.digest_text()
        self.assertEqual(text.count("Twin"), 2)
        self.assertIn("Hollow", text)

    def test_digest_has_no_hardcoded_domain_list(self):
        self.assertNotIn("DOMAINS", DIGEST.read_text(encoding="utf-8"))


class SkeletonTests(TmpCase):
    def test_skeletons_exist_and_pass_the_lint(self):
        make_layout2(self.root)
        for name in rl.REGISTRIES:
            skel = TEMPLATES / name / "general.md"
            self.assertTrue(skel.is_file(), skel)
            write(self.root, f".claude/registries/{name}/general.md", skel.read_bytes())
        self.assertEqual(rl.layout_state(reg(self.root)).state, "current")
        report = rl.check_structure(reg(self.root), project_root=self.root)
        self.assertEqual(report.findings, [])
        self.assertEqual(report.exit_code(strict=True), 0)

    def test_skeleton_with_crlf_still_passes(self):
        make_layout2(self.root)
        for name in rl.REGISTRIES:
            skel = TEMPLATES / name / "general.md"
            write(self.root, f".claude/registries/{name}/general.md", skel.read_bytes().replace(b"\n", b"\r\n"))
        self.assertEqual(rl.check_structure(reg(self.root), project_root=self.root).findings, [])


class StaticFixtureTests(unittest.TestCase):
    def test_client_shape_fixture(self):
        registries = FIXTURES / "client-shape" / ".claude" / "registries"
        self.assertEqual(rl.layout_state(registries).state, "pending")
        entries = rl.collect_entries(registries)
        got = {(e.registry, e.key): (e.tier, e.kind) for e in entries}
        self.assertEqual(got[("MECHANISMS", "universal one")], ("universal", "entry"))
        self.assertEqual(got[("MECHANISMS", "project one")], ("project:Fixture", "entry"))
        self.assertNotIn(("MECHANISMS", "not an entry"), got)
        self.assertNotIn(("MECHANISMS", "fenced sample"), got)
        self.assertNotIn(("JOURNAL", "ui-evolution"), got)
        self.assertEqual(got[("JOURNAL", "a dated bullet lesson")][1], "legacy")
        self.assertEqual(got[("JOURNAL", "old dated heading")], ("project:Fixture", "legacy"))
        self.assertEqual(got[("JOURNAL", "project lesson")], ("project:Fixture", "entry"))
        report = rl.check_structure(registries, project_root=FIXTURES / "client-shape")
        self.assertEqual(report.exit_code(strict=True), 0)
        # R1 on the bodiless entry; R3 once per `## Project:` heading in a root (advisory on layout 1).
        self.assertEqual(sorted({f.rule for f in report.findings}), ["R1", "R3"])
        self.assertEqual([f.key for f in report.findings if f.rule == "R1"], ["project bodiless"])
        self.assertTrue(all(f.severity == "advisory" for f in report.findings))


class DomainFilesTests(TmpCase):
    def test_files_in_orders_root_general_then_alphabetical(self):
        make_layout2(self.root)
        write(self.root, ".claude/registries/MECHANISMS/zeta.md", "x\n")
        write(self.root, ".claude/registries/MECHANISMS/alpha.md", "x\n")
        names = [p.name for p in rl.registry_files_in(reg(self.root), "MECHANISMS.md")]
        self.assertEqual(names, ["MECHANISMS.md", "general.md", "alpha.md", "zeta.md"])
        kept = [p.name for p in rl.registry_files_in(reg(self.root), "MECHANISMS.md", domains=["zeta"])]
        self.assertEqual(kept, ["MECHANISMS.md", "general.md", "zeta.md"])


class ImportChainTests(unittest.TestCase):
    def test_reader_imports_no_cli_script_and_no_plugin_doctor(self):
        code = ("import sys\nsys.path.insert(0, %r)\nimport _registry_layout\n"
                "bad = [m for m in ('plugin_doctor', 'validate_registries', 'generate_registry_digest',\n"
                "                   'auto_improve_finish_install', 'registry_migrate') if m in sys.modules]\n"
                "assert not bad, bad\n" % str(SCRIPTS_DIR))
        done = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)


class SpecTests(unittest.TestCase):
    def test_spec_carries_the_sync_tool_section_and_the_normative_lists(self):
        text = (REPO_ROOT / ".claude" / "references" / "registry-layout.md").read_text(encoding="utf-8")
        self.assertIn("## 12. For the sync tool", text)
        for needle in ("`stale-sync`", "exit", "plugin-owned", "project-owned", "registry_migrate.py --check",
                       rl.MARKER, "`R4_EXCLUDED_PREFIXES`"):
            self.assertIn(needle, text, needle)
        for prefix in rl.R4_EXCLUDED_PREFIXES:
            self.assertIn(prefix, text, prefix)
        for rule in ("R1", "R2", "R3", "R4", "R5", "R6", "A1", "I-8b", "I-8c"):
            self.assertIn(rule, text, rule)


class SourceValueAndAdapterTierTests(unittest.TestCase):
    """Block 12 (Q21): source_value and the tier rule of the two adapters that serve the memory readers."""

    def test_source_value_trims_backticks_and_padding_and_keeps_the_whole_value(self):
        self.assertEqual(rl.source_value("  `.claude/concepts/my folder/x y.md`  "), ".claude/concepts/my folder/x y.md")
        self.assertEqual(rl.source_value(" .claude/concepts/a b.md"), ".claude/concepts/a b.md")
        self.assertEqual(rl.source_value(r"D:\Dev\X\.claude\concepts\c.md"), r"D:\Dev\X\.claude\concepts\c.md")

    def test_source_value_reads_the_unset_forms_as_empty(self):
        for raw in ("", "   ", "none", "None", "N/A", "n/a", " `N/A` ", "na", "unknown", "TBD", "tbd",
                    "<path to the contract>", " `<slug>`"):
            self.assertEqual(rl.source_value(raw), "", "form %r must read as unset" % raw)

    def test_a_root_entry_under_a_universal_heading_is_universal_in_both_adapters(self):
        mv = "## Universal Patterns\n\n- **Alpha** — body\n"
        jr = "## Universal lessons\n\n### 2026-01-01 — Lesson\n- **Trigger:** manual\n"
        self.assertEqual([b["tier"] for b in rl.entry_blocks(mv)], ["Universal"])
        self.assertEqual([e["tier"] for e in rl.journal_entries(jr)], ["Universal"])

    def test_a_root_entry_before_any_heading_is_project_in_both_adapters(self):
        mv = "- **Alpha** — body\n"
        jr = "### 2026-01-01 — Lesson\n- **Trigger:** manual\n"
        self.assertEqual([b["tier"] for b in rl.entry_blocks(mv)], ["Project"])
        self.assertEqual([e["tier"] for e in rl.journal_entries(jr)], ["Project"])

    def test_a_domain_file_entry_is_project_even_under_a_universal_heading(self):
        mv = "## Universal Patterns\n\n- **Alpha** — body\n"
        jr = "## Universal lessons\n\n### 2026-01-01 — Lesson\n- **Trigger:** manual\n"
        self.assertEqual([b["tier"] for b in rl.entry_blocks(mv, per_domain=True)], ["Project"])
        self.assertEqual([e["tier"] for e in rl.journal_entries(jr, per_domain=True)], ["Project"])

    def test_the_adapters_take_text_and_return_lists(self):
        self.assertEqual(rl.entry_blocks(""), [])
        self.assertEqual(rl.journal_entries(""), [])


class ThisRepositoryTests(unittest.TestCase):
    def test_check_structure_exits_zero_with_only_layout_and_r4_output(self):
        env = dict(os.environ)
        env.pop("CLAUDE_PROJECT_DIR", None)
        env["PYTHONIOENCODING"] = "utf-8"
        done = subprocess.run([sys.executable, str(VALIDATE), "--check-structure", "--project", str(REPO_ROOT),
                               "--plugin-root", str(REPO_ROOT / NO_PLUGIN)], capture_output=True, text=True,
                              encoding="utf-8", env=env, cwd=str(REPO_ROOT))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        lines = [ln for ln in done.stdout.splitlines() if ln.strip()]
        # This repository is on layout 2 (state "current"), so no layout advisory line is printed:
        # only R4 and digest lines remain (and, when a plugin root resolves, the one R3 skip line).
        for ln in lines:
            self.assertFalse(ln.startswith("advisory: registry layout"), ln)
            self.assertTrue(ln.startswith("advisory: R4 ") or ln.startswith("digest: ")
                            or ln.startswith("advisory: R3 universal-candidate skipped"), ln)


if __name__ == "__main__":
    unittest.main(verbosity=1)
