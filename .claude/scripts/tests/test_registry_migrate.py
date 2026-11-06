#!/usr/bin/env python3
"""
Tests for registry_migrate.py: the layout gate (--check), the dry-run / apply runner and migration 0001
(contract 2026-11-04-domain-split-registries, "Migration 0001", I-9..I-13, Commands "Preview / apply migration").

The fixtures are under fixtures/registry-migration/: ``client`` (the reference client's state), ``stale-sync``,
``conflict`` and ``plugin`` (a fake installed plugin root with its manifest). Every test works on a temporary copy
that is a git repository. No fixture names a real project.

Run: py -3 .claude/scripts/tests/test_registry_migrate.py
"""

from __future__ import annotations

import collections
import contextlib
import io
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
REPO_ROOT = SCRIPTS_DIR.parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "registry-migration"
sys.path.insert(0, str(SCRIPTS_DIR))

import _preview_apply  # noqa: E402
import _registry_layout as rl  # noqa: E402

RUNNER = SCRIPTS_DIR / "registry_migrate.py"
PLUGIN_FIXTURE = FIXTURES / "plugin"
REGS = Path(".claude") / "registries"

GIT = ["git", "-c", "user.name=tester", "-c", "user.email=tester@example.invalid", "-c", "commit.gpgsign=false",
       "-c", "core.autocrlf=false"]


def git(project: Path, *args: str) -> None:
    subprocess.run(GIT + list(args), cwd=str(project), check=True, capture_output=True)


def snapshot(root: Path, sub: Path = REGS) -> dict:
    base = Path(root) / sub
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file()}


def nonblank(data: bytes) -> collections.Counter:
    text = rl.normalise_bytes(data).decode("utf-8")
    return collections.Counter(ln.rstrip() for ln in text.split("\n") if ln.strip())


def tree_lines(tree: dict) -> collections.Counter:
    total: collections.Counter = collections.Counter()
    for data in tree.values():
        total += nonblank(data)
    return total


class Proj:
    """A temporary copy of one fixture, committed to a fresh git repository."""

    def __init__(self, test: unittest.TestCase, kind: str = "client", *, use_git: bool = True):
        self.test = test
        self._tmp = tempfile.TemporaryDirectory(prefix="regmig-")
        test.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.project = self.base / "proj"
        self.home = self.base / "home"
        (self.home / ".claude").mkdir(parents=True)
        shutil.copytree(FIXTURES / kind, self.project)
        self.regs = self.project / REGS
        if use_git:
            git(self.project, "init", "-q")
            self.commit()

    def commit(self) -> None:
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "state", "--allow-empty")

    def env(self) -> dict:
        e = dict(os.environ)
        for name in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR"):
            e.pop(name, None)
        e.update({"HOME": str(self.home), "USERPROFILE": str(self.home), "CLAUDE_CONFIG_DIR": str(self.home / ".claude"),
                  "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
        return e

    def run(self, *args: str, plugin: bool = True, runner: Path = RUNNER, project: str | None = "default"):
        argv = [sys.executable, str(runner)]
        if project == "default":
            project = str(self.project)
        if project is not None:
            argv += ["--project", project]
        if plugin:
            argv += ["--plugin-root", str(PLUGIN_FIXTURE)]
        argv += list(args)
        done = subprocess.run(argv, capture_output=True, env=self.env(), cwd=str(self.base), timeout=300)
        return done

    def report(self, done) -> dict:
        return json.loads(done.stdout.decode("utf-8"))

    def dry(self, **kw) -> dict:
        done = self.run("--dry-run", **kw)
        self.test.assertEqual(done.returncode, 0, out(done))
        return self.report(done)

    def apply(self, expect: str | None = None, **kw):
        if expect is None:
            expect = self.dry(**kw)["plan_hash"]
        return self.run("--apply", "--expect-sha256", expect, **kw)

    def state(self) -> str:
        return rl.layout_state(self.regs).state


def out(done) -> str:
    return done.stdout.decode("utf-8", "replace") + done.stderr.decode("utf-8", "replace")


def read(proj: Proj, rel: str) -> str:
    return (proj.regs / rel).read_bytes().decode("utf-8").replace("\r\n", "\n")


def lines_of(report: dict, registry: str, key: str) -> list:
    return report["registries"][registry][key]


# ---------------------------------------------------------------------------
class GateTests(unittest.TestCase):
    def test_check_exits_6_before_and_0_after(self):
        p = Proj(self)
        done = p.run("--check")
        self.assertEqual(done.returncode, 6, out(done))
        self.assertEqual(json.loads(done.stdout.decode())["state"], "pending")
        self.assertEqual(p.apply().returncode, 0)
        done = p.run("--check")
        self.assertEqual(done.returncode, 0, out(done))
        self.assertEqual(json.loads(done.stdout.decode())["state"], "current")

    def test_check_stale_sync_exits_6(self):
        p = Proj(self, "stale-sync")
        done = p.run("--check")
        self.assertEqual(done.returncode, 6, out(done))
        self.assertEqual(json.loads(done.stdout.decode())["state"], "stale-sync")

    def test_check_absent_exits_0_and_unknown_exits_2(self):
        p = Proj(self)
        shutil.rmtree(p.regs)
        done = p.run("--check")
        self.assertEqual(done.returncode, 0, out(done))
        self.assertEqual(json.loads(done.stdout.decode())["state"], "absent")
        q = Proj(self)
        (q.regs / "JOURNAL.md").write_bytes(rl.MARKER.encode() + b"\n" + (q.regs / "JOURNAL.md").read_bytes())
        done = q.run("--check")
        self.assertEqual(done.returncode, 2, out(done))
        self.assertEqual(json.loads(done.stdout.decode())["state"], "unknown")

    def test_unknown_layout_refuses_a_migration(self):
        p = Proj(self)
        (p.regs / "JOURNAL.md").write_bytes(rl.MARKER.encode() + b"\n" + (p.regs / "JOURNAL.md").read_bytes())
        p.commit()
        before = snapshot(p.project)
        done = p.run("--dry-run")
        self.assertEqual(done.returncode, 3, out(done))
        self.assertEqual(p.report(done)["refusal_code"], "unknown-layout")
        self.assertEqual(snapshot(p.project), before)

    def test_project_undetermined_unset_and_absent(self):
        p = Proj(self)
        for project in (None, str(p.base / "no-such-project")):
            for mode in ("--check", "--dry-run"):
                done = p.run(mode, project=project)
                self.assertEqual(done.returncode, 3, out(done))
                self.assertIn("project-undetermined", out(done))

    def test_apply_needs_the_expected_hash(self):
        p = Proj(self)
        done = p.run("--apply")
        self.assertEqual(done.returncode, 2, out(done))

    def test_the_runner_never_imports_finish_install(self):
        for path in (RUNNER, SCRIPTS_DIR / "registry_migrations" / "m0001_domain_split.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("import auto_improve_finish_install", text, path.name)
            self.assertNotIn("from auto_improve_finish_install", text, path.name)


# ---------------------------------------------------------------------------
class DryRunApplyTests(unittest.TestCase):
    def test_dry_run_writes_nothing_under_registries(self):
        p = Proj(self)
        before = snapshot(p.project)
        rep = p.dry()
        self.assertEqual(snapshot(p.project), before)
        self.assertEqual(rep["mode"], "dry-run")
        self.assertEqual(rep["number"], "0001")
        self.assertEqual(len(rep["plan_hash"]), 64)
        self.assertEqual(rep["refusal_code"], "")
        self.assertTrue((Path(rep["report_dir"]) / "report.json").is_file())
        self.assertTrue((Path(rep["report_dir"]) / "registry-migration-report.md").is_file())
        self.assertTrue(rep["files"])

    def test_apply_with_the_dry_run_hash_makes_both_fixtures_current(self):
        for kind in ("client", "stale-sync"):
            with self.subTest(kind):
                p = Proj(self, kind)
                done = p.apply()
                self.assertEqual(done.returncode, 0, out(done))
                self.assertEqual(p.report(done)["mode"], "apply")
                self.assertEqual(p.state(), "current", rl.layout_state(p.regs).reasons)
                self.assertEqual(p.run("--check").returncode, 0)

    def test_second_apply_is_an_empty_plan_with_equal_bytes_before_any_git_check(self):
        p = Proj(self)
        self.assertEqual(p.apply().returncode, 0)
        after = snapshot(p.project)
        done = p.run("--apply", "--expect-sha256", "0" * 64)  # the tree is uncommitted; the state check comes first
        self.assertEqual(done.returncode, 0, out(done))
        rep = p.report(done)
        self.assertEqual(rep["files"], [])
        self.assertEqual(snapshot(p.project), after)
        done = p.run("--dry-run")
        self.assertEqual(done.returncode, 0, out(done))
        self.assertEqual(p.report(done)["files"], [])

    def test_plan_hash_is_plan_digest_over_the_stated_parts(self):
        p = Proj(self)
        before = snapshot(p.project, Path(".claude"))
        rep = p.dry()
        self.assertEqual(p.apply(rep["plan_hash"]).returncode, 0)
        after = snapshot(p.project, Path(".claude"))
        parts = [b"registry-migration", b"0001"]
        for rel in sorted(rep["files"]):
            parts += [rel.encode("utf-8"), before.get(rel, b"absent"), after[rel]]
        self.assertEqual(rep["plan_hash"], _preview_apply._plan_digest(*parts))
        self.assertEqual(rep["files"], sorted(rep["files"]))
        changed = sorted(r for r in after if before.get(r) != after[r] and r.startswith(".claude/registries/"))
        self.assertEqual(changed, rep["files"])

    def test_backups_live_only_under_the_report_folder(self):
        p = Proj(self)
        before = snapshot(p.project)
        rep = p.dry()
        done = p.apply(rep["plan_hash"])
        self.assertEqual(done.returncode, 0)
        after = snapshot(p.project)
        new_under_registries = sorted(set(after) - set(before))
        self.assertTrue(all(r.endswith("general.md") for r in new_under_registries), new_under_registries)
        backups = [q for q in (Path(p.report(done)["report_dir"]) / "backup").rglob("*") if q.is_file()]
        self.assertTrue(backups)
        names = {q.name for q in backups}
        self.assertIn("JOURNAL.md", names)

    def test_crlf_registries_migrate_and_keep_their_line_endings(self):
        p = Proj(self)
        path = p.regs / "JOURNAL.md"
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        p.commit()
        self.assertEqual(p.apply().returncode, 0)
        data = path.read_bytes()
        self.assertIn(b"\r\n", data)
        self.assertNotIn(b"\n", data.replace(b"\r\n", b""))
        self.assertEqual(p.state(), "current")


# ---------------------------------------------------------------------------
class ContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="regmig-cls-")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def migrate(self, kind: str = "client"):
        p = Proj(self, kind)
        self.before = snapshot(p.project)
        rep = p.dry()
        done = p.apply(rep["plan_hash"])
        self.assertEqual(done.returncode, 0, out(done))
        self.after = snapshot(p.project)
        return p, rep

    def test_i12_every_lost_line_is_a_listed_removed_line_and_every_new_line_is_structural(self):
        p, rep = self.migrate()
        src = tree_lines({k: v for k, v in self.before.items() if k.startswith(".claude/registries/")})
        dst = tree_lines({k: v for k, v in self.after.items() if k.startswith(".claude/registries/")})
        removed: collections.Counter = collections.Counter()
        for reg in rep["registries"].values():
            for item in reg["removed_lines"]:
                removed[item["text"].rstrip()] += 1
        lost = src - dst
        self.assertEqual(lost - removed, collections.Counter(), "a line was lost without being listed")
        skeleton_lines = set()
        for stem in rl.REGISTRIES:
            skeleton_lines |= {ln.rstrip() for ln in
                               (REPO_ROOT / ".claude" / "templates" / "registries" / stem / "general.md")
                               .read_text(encoding="utf-8").split("\n") if ln.strip()}
        pointer_lines = set()
        for stem in rl.REGISTRIES:
            pointer_lines |= {ln.rstrip() for ln in rl.pointer_section(stem).split("\n") if ln.strip()}

        def structural(line: str) -> bool:
            return (line == rl.MARKER or line in pointer_lines or line in skeleton_lines
                    or line == rl.LEFTOVERS_HEADING or line.startswith("<!-- leftover from ")
                    or set(line) <= {"`"})
        for line in dst - src:
            self.assertTrue(structural(line), "unexpected new line: %r" % line)

    def test_i12_entry_keys_and_counts(self):
        p, rep = self.migrate()
        keys_before = {e.key for e in rl.collect_entries(FIXTURES / "client" / REGS)}
        keys_after = {e.key for e in rl.collect_entries(p.regs)}
        self.assertEqual(keys_before, keys_after)
        for name, reg in rep["registries"].items():
            counts = reg["counts"]
            self.assertEqual(counts["in"], counts["out"] + counts["merged_away"], name)
            self.assertEqual(counts["out"], counts["kept"] + counts["moved"], name)
        self.assertEqual(sum(1 for e in rl.collect_entries(p.regs)), sum(r["counts"]["out"] for r in rep["registries"].values()))

    def test_leftovers_are_verbatim_and_the_last_section_of_general(self):
        p, rep = self.migrate()
        voc = read(p, "VOCABULARY/general.md")
        self.assertIn(rl.LEFTOVERS_HEADING, voc)
        head = voc.index(rl.LEFTOVERS_HEADING)
        self.assertNotIn("\n## ", voc[head + 3:], "the leftovers section is not the last section")
        tail = voc[head:]
        for line in ("Project prose paragraph that is not an entry.", "### Project sub heading", "| col | col |",
                     "|-----|-----|", "| a   | b   |"):
            self.assertIn(line + "\n", tail)
        self.assertIn("<!-- leftover from .claude/registries/VOCABULARY.md:", tail)
        self.assertIn("project-prose -->", tail)
        self.assertIn("non-entry-heading -->", tail)
        reasons = {b["reason"] for b in lines_of(rep, "VOCABULARY", "leftovers")}
        self.assertEqual(reasons, {"project-prose", "non-entry-heading"})
        # the leftover section is inert: it parses as no entry
        pf = rl.parse_file(p.regs / "VOCABULARY" / "general.md", "VOCABULARY")
        self.assertTrue(all(e.line < head_line(voc, head) for e in pf.entries))
        # the journal's prose, sub-heading and bullets
        jou = read(p, "JOURNAL/general.md")
        jtail = jou[jou.index(rl.LEFTOVERS_HEADING):]
        self.assertIn("Project prose line.\n", jtail)
        self.assertIn("### Tag conventions\n", jtail)
        self.assertIn("- `x` — a project prose bullet, not an entry.\n", jtail)

    def test_legacy_entries_move_verbatim_and_not_into_leftovers(self):
        p, rep = self.migrate()
        jou = read(p, "JOURNAL/general.md")
        head = jou.index(rl.LEFTOVERS_HEADING)
        for text in ("- 2026-10-06 — Dated bullet legacy lesson\n  continuation of the dated bullet.\n",
                     "## 2026-10-05 — Legacy dated heading lesson\nLegacy text line one.\nLegacy text line two.\n"):
            self.assertIn(text, jou)
            self.assertLess(jou.index(text), head, "a legacy entry sits in the leftovers section")
        legacy = {item["key"] for item in lines_of(rep, "JOURNAL", "legacy_entries")}
        self.assertEqual(legacy, {"dated bullet legacy lesson", "legacy dated heading lesson"})
        for blk in lines_of(rep, "JOURNAL", "leftovers"):
            self.assertFalse(any("Legacy text line" in ln or "Dated bullet legacy" in ln for ln in blk["lines"]))
        # the bullet is still an entry in its new file (it did not get swallowed by a heading entry)
        keys = {e.key for e in rl.parse_file(p.regs / "JOURNAL" / "general.md", "JOURNAL").entries}
        self.assertIn("dated bullet legacy lesson", keys)

    def test_removed_lines_are_listed_by_reason(self):
        p, rep = self.migrate()
        for name in rl.REGISTRIES:
            reasons = {i["reason"] for i in lines_of(rep, name, "removed_lines")}
            self.assertTrue(reasons <= {"project-heading", "replaced-sync-section", "merged-duplicate"}, reasons)
        heads = [i for i in lines_of(rep, "JOURNAL", "removed_lines") if i["reason"] == "project-heading"]
        self.assertEqual([h["text"] for h in heads], ["## Project: acme-app"])
        self.assertTrue(heads[0]["file"].endswith("JOURNAL.md") and heads[0]["line"] > 1)
        merged = [i for i in lines_of(rep, "JOURNAL", "removed_lines") if i["reason"] == "merged-duplicate"]
        self.assertEqual([m["text"] for m in merged], ["### 2026-10-12 — Dup lesson key"])

    def test_section_4_2_order_tags_then_area_then_general(self):
        p, rep = self.migrate()
        moved = {m["key"]: m for m in lines_of(rep, "JOURNAL", "moved")}
        self.assertEqual((moved["tagged backend lesson"]["to"], moved["tagged backend lesson"]["reason"]),
                         ("JOURNAL/backend.md", "tags"))
        self.assertEqual((moved["area routed lesson"]["to"], moved["area routed lesson"]["reason"]),
                         ("JOURNAL/frontend.md", "source-contract-area"))
        self.assertEqual(moved["unclassified lesson"]["to"], "JOURNAL/general.md")
        self.assertIn("unclassified lesson", lines_of(rep, "JOURNAL", "unclassified"))
        self.assertIn("### 2026-10-07 — Tagged backend lesson", read(p, "JOURNAL/backend.md"))
        self.assertIn("### 2026-10-08 — Area routed lesson", read(p, "JOURNAL/frontend.md"))
        self.assertNotIn("Tagged backend lesson", read(p, "JOURNAL/general.md"))

    def test_token_entries_universal_candidates_and_token_lines(self):
        p, rep = self.migrate()
        root = read(p, "MECHANISMS.md")
        general = read(p, "MECHANISMS/general.md")
        self.assertIn("**Client Widgetco Mech**", general)
        self.assertIn("  A continuation line.\n", general)
        self.assertNotIn("Client Widgetco Mech", root)
        self.assertIn("**Plugin Widgetco Mech**", root)
        self.assertIn("**Client Generic Mech**", root)
        m = rep["registries"]["MECHANISMS"]
        self.assertEqual(m["token_entries_moved"], ["client widgetco mech"])
        self.assertEqual(m["plugin_owned_token_entries"], ["plugin widgetco mech"])
        self.assertEqual(m["universal_candidates"], ["client generic mech"])
        self.assertEqual(m["unverified_token_entries"], [])
        self.assertEqual([t["text"] for t in m["unmovable_token_lines"]], ["> Widgetco mechanisms for the acme team."])
        self.assertIn("See domain-specific files in the registry folder.", root)
        self.assertIn("```text\n- **Fenced Sample** *(2026-01-01)* — inside a fence, never an entry.\n```", root)
        self.assertEqual(root.splitlines()[0], rl.MARKER)
        self.assertTrue(root.rstrip().endswith(rl.pointer_section("MECHANISMS").rstrip()))
        j = rep["registries"]["JOURNAL"]
        self.assertEqual(j["token_entries_moved"], ["client widgetco lesson"])
        self.assertEqual(j["plugin_owned_token_entries"], ["plugin widgetco lesson"])
        self.assertIn("### 2026-10-20 — Client widgetco lesson", read(p, "JOURNAL/general.md"))
        self.assertIn("### Tag conventions", read(p, "JOURNAL.md"))  # the universal prose section stays

    def test_the_lesson_only_copy_is_appended_under_the_kept_entry(self):
        p, rep = self.migrate()
        front = read(p, "JOURNAL/frontend.md")
        self.assertEqual(front.count("— Dup lesson key"), 1)
        lesson = "- **Lesson:** Extra lesson line from the lesson-only copy."
        self.assertEqual(front.count(lesson), 1)
        header = front.index("— Dup lesson key")
        self.assertGreater(front.index(lesson), header)
        self.assertNotIn("Dup lesson key", read(p, "JOURNAL/general.md"))
        appended = lines_of(rep, "JOURNAL", "appended_merge_lines")
        self.assertEqual([a["key"] for a in appended], ["dup lesson key"])
        self.assertEqual(appended[0]["lines"], [lesson])
        merged = lines_of(rep, "JOURNAL", "merged_duplicates")
        self.assertEqual([m["key"] for m in merged], ["dup lesson key"])
        self.assertEqual(len([e for e in rl.collect_entries(p.regs, registries=["JOURNAL"]) if e.key == "dup lesson key"]), 1)

    def test_the_same_bodiless_entry_in_flat_and_split_is_one_copy(self):
        p, rep = self.migrate()
        voc = read(p, "VOCABULARY/backend.md")
        self.assertEqual(voc.count("**Bodiless In Both**"), 1)
        self.assertNotIn("Bodiless In Both", read(p, "VOCABULARY/general.md"))
        self.assertEqual([m["key"] for m in lines_of(rep, "VOCABULARY", "merged_duplicates")], ["bodiless in both"])

    def test_orphans_are_listed_with_a_command_and_never_marked(self):
        p, rep = self.migrate()
        found = {name: {o["key"] for o in lines_of(rep, name, "bodiless_orphans")} for name in rl.REGISTRIES}
        self.assertEqual(found["MECHANISMS"], {"title only split mech"})
        self.assertEqual(found["VOCABULARY"], {"bodiless in both", "orphan under project"})
        self.assertEqual(found["JOURNAL"], {"orphan journal lesson"})
        orphan = lines_of(rep, "JOURNAL", "bodiless_orphans")[0]
        self.assertIn("recover the body from your own backups, or mark it", orphan["hint"])
        self.assertIn("registry_append.py", orphan["command"])
        self.assertIn("--registry journal", orphan["command"])
        self.assertIn("--archive-title-only 'Orphan journal lesson'", orphan["command"])
        for rel, data in self.after.items():
            self.assertNotIn(b"archived-title-only", data, rel)

    def test_unchanged_domain_files_are_not_rewritten(self):
        p, rep = self.migrate()
        self.assertNotIn(".claude/registries/MECHANISMS/backend.md", rep["files"])  # nothing joined it
        self.assertEqual(self.before[".claude/registries/MECHANISMS/backend.md"],
                         self.after[".claude/registries/MECHANISMS/backend.md"])

    def test_stale_sync_removes_the_marker_and_pointer_lines_it_replaces(self):
        p, rep = self.migrate("stale-sync")
        removed = lines_of(rep, "MECHANISMS", "removed_lines")
        by_reason = collections.defaultdict(list)
        for item in removed:
            by_reason[item["reason"]].append(item["text"])
        self.assertIn(rl.MARKER, by_reason["replaced-sync-section"])
        self.assertIn("## Project tier", by_reason["replaced-sync-section"])
        self.assertEqual(by_reason["project-heading"], ["## Project: acme-app"])
        root = read(p, "MECHANISMS.md")
        self.assertEqual(root.count(rl.MARKER), 1)
        self.assertEqual(root.count("## Project tier"), 1)
        general = read(p, "MECHANISMS/general.md")
        self.assertIn("**Below Pointer Mech**", general)
        self.assertIn("**Stale Project Mech**", general)
        self.assertIn("Stale project prose.", general[general.index(rl.LEFTOVERS_HEADING):])
        jou = read(p, "JOURNAL/general.md")
        self.assertTrue(jou.startswith("# Journal - general\n\n> existing general header\n"))
        self.assertIn("### 2026-10-31 — Stale project lesson", jou)
        self.assertEqual(rep["layout_state"]["state"], "stale-sync")

    def test_lines_that_a_forced_plan_drops_are_content_loss(self):
        import registry_migrate as rm
        from registry_migrations import m0001_domain_split as m0001
        p = Proj(self)
        before = snapshot(p.project)
        original = m0001.render_leftover_block

        def dropping(*args, **kwargs):
            block, added = original(*args, **kwargs)
            block = list(block)
            del block[2]  # the first verbatim line, between the opening fence and the rest
            return block, added
        env = {"CLAUDE_CONFIG_DIR": str(p.home / ".claude"), "HOME": str(p.home), "USERPROFILE": str(p.home)}
        with mock.patch.object(m0001, "render_leftover_block", dropping):
            code, stdout, stderr = run_inproc(rm, ["--project", str(p.project), "--plugin-root", str(PLUGIN_FIXTURE),
                                                   "--apply", "--expect-sha256", "0" * 64], env)
        self.assertEqual(code, 3, stderr)
        rep = json.loads(stdout)
        self.assertEqual(rep["refusal_code"], "content-loss-detected")
        self.assertEqual(snapshot(p.project), before)
        self.assertIn("content-loss-detected", stderr)


def head_line(text: str, offset: int) -> int:
    return text[:offset].count("\n") + 1


def run_inproc(module, argv: list, env: dict | None = None):
    buf, err = io.StringIO(), io.StringIO()
    clean = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR")}
    clean.update(env or {})
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err), mock.patch.dict(os.environ, clean, clear=True):
        code = module.main(argv)
    return code, buf.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
class RefusalTests(unittest.TestCase):
    def assert_refused(self, p: Proj, done, code: str, before: dict) -> dict:
        self.assertEqual(done.returncode, 3, out(done))
        rep = p.report(done)
        self.assertEqual(rep["mode"], "refused")
        self.assertEqual(rep["refusal_code"], code)
        self.assertIn(code, done.stderr.decode("utf-8", "replace"))
        self.assertEqual(snapshot(p.project), before, "a refusal changed a registry file (I-13)")
        self.assertTrue((Path(rep["report_dir"]) / "report.json").is_file(), "a refusal must still write the report")
        self.assertTrue((Path(rep["report_dir"]) / "registry-migration-report.md").is_file())
        return rep

    def test_conflicting_entry_refuses_and_names_every_location_and_field(self):
        p = Proj(self, "conflict")
        before = snapshot(p.project)
        done = p.run("--dry-run")
        rep = self.assert_refused(p, done, "conflicting-entry", before)
        conflicts = rep["registries"]["VOCABULARY"]["conflicts"]
        self.assertEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c["key"], "conflict term")
        self.assertEqual(sorted(loc.split(":")[0] for loc in c["locations"]),
                         [".claude/registries/VOCABULARY.md", ".claude/registries/VOCABULARY/backend.md"])
        self.assertEqual(c["field"], "body")
        self.assertEqual(len(c["versions"]), 2)
        self.assertTrue(any("version one body" in v for v in c["versions"]))
        self.assertTrue(any("version two" in v for v in c["versions"]))
        self.assertTrue(rep["plan_hash"])  # present in every mode
        done = p.run("--apply", "--expect-sha256", "1" * 64)
        self.assert_refused(p, done, "conflicting-entry", before)

    def test_uncommitted_registry_changes_refuse(self):
        p = Proj(self)
        path = p.regs / "VOCABULARY.md"
        path.write_bytes(path.read_bytes() + b"\nA hand edit nobody committed.\n")
        before = snapshot(p.project)
        done = p.run("--dry-run")
        rep = self.assert_refused(p, done, "uncommitted-registry-changes", before)
        self.assertTrue(rep["plan_hash"])
        done = p.run("--apply", "--expect-sha256", rep["plan_hash"])
        self.assert_refused(p, done, "uncommitted-registry-changes", before)

    def test_not_a_git_tree_refuses(self):
        p = Proj(self, use_git=False)
        before = snapshot(p.project)
        self.assert_refused(p, p.run("--dry-run"), "not-a-git-tree", before)

    def test_changed_since_preview_refuses(self):
        p = Proj(self)
        stale = p.dry()["plan_hash"]
        path = p.regs / "VOCABULARY.md"
        path.write_bytes(path.read_bytes() + b"\nCommitted after the preview.\n")
        p.commit()
        before = snapshot(p.project)
        self.assert_refused(p, p.run("--apply", "--expect-sha256", stale), "changed-since-preview", before)

    def test_a_forced_replace_failure_restores_every_file(self):
        import registry_migrate as rm
        p = Proj(self)
        before = snapshot(p.project)
        rep = p.dry()
        real_replace = os.replace
        calls = {"stage": 0}

        def flaky(src, dst, *a, **kw):
            if ".stage-" in os.path.basename(str(src)):
                calls["stage"] += 1
                if calls["stage"] == 3:
                    raise OSError("simulated replace failure")
            return real_replace(src, dst, *a, **kw)
        env = {"CLAUDE_CONFIG_DIR": str(p.home / ".claude"), "HOME": str(p.home), "USERPROFILE": str(p.home)}
        with mock.patch("_preview_apply.os.replace", flaky):
            code, stdout, stderr = run_inproc(rm, ["--project", str(p.project), "--plugin-root", str(PLUGIN_FIXTURE),
                                                   "--apply", "--expect-sha256", rep["plan_hash"]], env)
        self.assertEqual(code, 3, stderr)
        self.assertEqual(json.loads(stdout)["refusal_code"], "write-failed")
        self.assertGreaterEqual(calls["stage"], 3)
        after = snapshot(p.project)
        self.assertEqual(after, before)  # every original byte-identical, no new or stage file under .claude/registries/
        self.assertEqual(sorted(after), sorted(before))

    def test_a_symlinked_target_refuses(self):
        p = Proj(self)
        target = p.regs / "JOURNAL" / "backend.md"
        elsewhere = p.base / "elsewhere.md"
        elsewhere.write_bytes(target.read_bytes())
        target.unlink()
        try:
            os.symlink(str(elsewhere), str(target))
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are not available here")
        p.commit()
        done = p.run("--dry-run")
        self.assertEqual(done.returncode, 3, out(done))
        self.assertEqual(p.report(done)["refusal_code"], "symlink-target")


# ---------------------------------------------------------------------------
class VendoredTests(unittest.TestCase):
    """(d) The project vendors the plugin's scripts: the only plugin tree is the project itself."""

    def vendored(self) -> Proj:
        p = Proj(self, use_git=False)
        shutil.copytree(SCRIPTS_DIR, p.project / ".claude" / "scripts",
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        shutil.copytree(REPO_ROOT / ".claude" / "hooks", p.project / ".claude" / "hooks",
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        shutil.copytree(REPO_ROOT / ".claude" / "templates" / "registries",
                        p.project / ".claude" / "templates" / "registries")
        shutil.copytree(PLUGIN_FIXTURE / ".claude-plugin", p.project / ".claude-plugin")
        git(p.project, "init", "-q")
        p.commit()
        return p

    def test_without_a_separate_plugin_root_every_token_entry_is_unverified_and_kept(self):
        p = self.vendored()
        runner = p.project / ".claude" / "scripts" / "registry_migrate.py"
        rep = p.report(self.ok(p.run("--dry-run", plugin=False, runner=runner)))
        self.assertEqual(rep["plugin_root"], "unverified")
        self.assertEqual(rep["plugin_root_reason"], "same-as-project")
        m = rep["registries"]["MECHANISMS"]
        self.assertEqual(sorted(m["unverified_token_entries"]), ["client widgetco mech", "plugin widgetco mech"])
        self.assertEqual(m["token_entries_moved"], [])
        self.assertEqual(m["universal_candidates"], [])
        j = rep["registries"]["JOURNAL"]
        self.assertEqual(sorted(j["unverified_token_entries"]), ["client widgetco lesson", "plugin widgetco lesson"])
        self.assertEqual(j["token_entries_moved"], [])
        done = p.run("--apply", "--expect-sha256", rep["plan_hash"], plugin=False, runner=runner)
        self.ok(done)
        self.assertIn("Client Widgetco Mech", read(p, "MECHANISMS.md"))
        self.assertIn("Client widgetco lesson", read(p, "JOURNAL.md"))
        self.assertIn("re-run with --plugin-root", json.dumps(rep))

    def ok(self, done):
        self.assertEqual(done.returncode, 0, out(done))
        return done


if __name__ == "__main__":
    unittest.main(verbosity=1)
