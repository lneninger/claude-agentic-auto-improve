#!/usr/bin/env python3
"""
RED tests for the reuse entry points of land_contract.py (contract 2026-10-07, block 9).

Covers, in order: ``module_tag_reading`` and ``--module-tags``; ``--verify-here`` with its
run id and its read-only locator (``--run-id <id> --status``); the four new outcomes and the
closed set that holds them (``VERIFY_OUTCOMES``); lock contention between a verification run and
a landing; and L-18 (``landing: manual`` in the parent brief) together with the shared
``pr_merged.parent_brief_of``.

Structure. This file REUSES the harness of ``test_land_contract.py`` (its guarded import of
``land_contract``, the subprocess guard that refuses any real ``gh pr merge`` or ``git push``
and any git run inside this checkout, the ``Kit`` temporary repository, the ``Stage`` landing
harness and the ``LauncherCase`` launcher harness) by importing it as ``T``. Importing runs its
module-top guard installation, so the guard is in force before any test here runs. Nothing from
``T`` is bound at module level under a ``Test*`` name, so unittest collects only this file's
classes. A missing symbol or flag is an AssertionError naming it, never ImportError,
AttributeError or SystemExit: the harness catches ``SystemExit`` from argparse and reports the
unparsable output as a failure. ``pr_merged.parent_brief_of`` is patched with ``create=True`` so
its absence is an assertion on the call, not an AttributeError.

Tests that PASS TODAY BY DESIGN carry ``passes_today_by_design`` in their name. They are the
positive controls that prove a RED test can turn green.

Run: py -3 -B .claude/scripts/tests/test_land_contract_reuse.py
"""

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import test_land_contract as T  # noqa: E402  (installs the subprocess guard at import)

pr_merged = T.pr_merged
norm = T.norm
SLUG = T.SLUG
PARENT = T.PARENT

# ---------------------------------------------------------------------------
# Neutral fixtures (no project token). Mirrored to the plugin.
# ---------------------------------------------------------------------------
PR_TITLE = {
    "map": [
        {"tag": "CORE", "globs": ["core/**"]},
        {"tag": "WEB", "globs": ["web/**"]},
        {"tag": "CHECKS", "globs": ["checks/**"], "coveredBy": ["CORE"]},
        {"tag": "OPS", "globs": ["ops/**"]},
    ],
    "shared": [{"files": ["web/package.json"], "emits": ["WEB", "APP2"]}],
    "ignore": {"globs": ["*.png"]},
    "order": ["CORE", "WEB", "APP2", "CHECKS", "OPS"],
}
RUN_ID = "verify-20261008T120000Z-abc123"
INVALID_ID_REASON = "pass a fresh run id of letters, digits, dot, dash or underscore"
NO_BASELINE_REMEDY = "master holds no failing-test baseline, so this runner ran no step and decides nothing"
BASE_REMEDY = "fetch origin and pass a --base ref that exists"
NEW_MEMBERS = {"verified", "module-tags-read", "base-unreadable", "no-baseline"}
FORBIDDEN_GIT = {"reset", "clean", "push", "merge", "commit", "stash", "checkout", "restore"}

STEP_DRIFT = {"id": "generated-drift", "suite": "drift", "when_paths": ["**"],
              "command": ["py", "-3", "-c", "drift-marker"], "results": {"format": "exit-code"},
              "timeout_minutes": 5, "environment_signatures": []}
STEPS = [T.STEP_BUILD, T.STEP_UNIT, STEP_DRIFT]
WORK_FILES = {"src/feature.py": "x = 1\n"}


def setUpModule():
    T._install_guards()
    global _SAVED
    _SAVED = {"cwd": os.getcwd(), "dir": tempfile.mkdtemp(prefix="reusetest-cwd-"),
              "gh": tempfile.mkdtemp(prefix="reusetest-ghcfg-"),
              "env": {k: os.environ.get(k) for k in T._GH_ENV_KEYS + ("GH_CONFIG_DIR",)}}
    os.chdir(_SAVED["dir"])  # an inherited working directory is never this checkout
    os.environ["GH_CONFIG_DIR"] = _SAVED["gh"]
    for key in T._GH_ENV_KEYS:
        os.environ.pop(key, None)


def tearDownModule():
    for key, value in _SAVED["env"].items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    os.chdir(_SAVED["cwd"])
    import shutil
    for key in ("dir", "gh"):
        shutil.rmtree(_SAVED[key], ignore_errors=True)


# ===========================================================================
# Pure: module_tag_reading and module_tags
# ===========================================================================
class TestModuleTagReading(T.LandCase):

    def reading(self, paths):
        return self.fn("module_tag_reading")(paths, PR_TITLE)

    def test_a_tag_covered_by_a_present_tag_is_dropped(self):
        got = self.reading(["core/a.py", "checks/test_a.py"])
        self.assertEqual(got["tags"], ["CORE"],
                         msg="coveredBy drops CHECKS when CORE is also in the diff")

    def test_a_tag_is_kept_when_no_covering_tag_is_present(self):
        got = self.reading(["ops/x.sh", "checks/test_a.py"])
        self.assertEqual(got["tags"], ["CHECKS", "OPS"],
                         msg="CHECKS stays (no CORE present) and the order is the configured one")

    def test_a_checks_only_diff_keeps_checks(self):
        self.assertEqual(self.reading(["checks/test_a.py"])["tags"], ["CHECKS"],
                         msg="nothing covers it")

    def test_a_shared_file_emits_both_its_tags_in_order(self):
        got = self.reading(["web/package.json"])
        self.assertEqual(got["tags"], ["WEB", "APP2"], msg="the shared entry emits WEB and APP2")
        self.assertEqual(got["prefix"], "[WEB][APP2]", msg="the prefix is the tags in brackets")

    def test_an_ignored_path_contributes_nothing_and_is_not_unmapped(self):
        got = self.reading(["x.png"])
        self.assertEqual((got["tags"], got["unmapped"]), ([], []), msg="*.png is ignored")

    def test_a_path_no_entry_maps_is_unmapped(self):
        got = self.reading(["core/a.py", "misc/y.txt"])
        self.assertEqual(got["unmapped"], ["misc/y.txt"], msg="it needs the ask-then-add rule")
        self.assertEqual(got["tags"], ["CORE"], msg="the mapped path still tags")

    def test_the_reading_carries_its_outcome_and_prefix(self):
        got = self.reading(["core/a.py", "checks/test_a.py"])
        self.assertEqual(got["outcome"], "module-tags-read", msg="the reading's outcome")
        self.assertEqual(got["prefix"], "[CORE]", msg="the title prefix")

    def test_module_tags_returns_the_same_tags_as_the_reading(self):
        lc = self.mod()
        for paths in (["core/a.py", "checks/test_a.py"], ["ops/x.sh", "checks/test_a.py"],
                      ["web/package.json"], ["x.png"]):
            self.assertEqual(lc.module_tags(paths, PR_TITLE), self.reading(paths)["tags"],
                             msg="module_tags delegates to module_tag_reading: %r" % paths)

    def test_passes_today_by_design_module_tags_exists_and_orders(self):
        self.assertEqual(self.mod().module_tags(["ops/x.sh", "core/a.py"], PR_TITLE), ["CORE", "OPS"],
                         msg="positive control: the existing function orders by the config")


# ===========================================================================
# Harness for the command line entry points
# ===========================================================================
class VerifyCase(T.LauncherCase):
    """Runs ``main(argv)`` in a checkout with every edge recorded."""

    def make_kit(self, *, baseline=T.BASELINE_CLEAN, steps=None, conventions=None, sub="k"):
        root = Path(self._tmp.name) / sub
        root.mkdir(parents=True, exist_ok=True)
        cfg = T.landing_config(steps=steps if steps is not None else STEPS)
        text = conventions if conventions is not None else json.dumps(
            {"contractLanding": cfg, "prTitle": PR_TITLE})
        return T.Kit(root, config=cfg, baseline=baseline, base_files={T.CONVENTIONS: text})

    def work_checkout(self, kit, files=None, name="20261008-verify-here"):
        path = kit.add_worktree(name, ref="origin/master")
        T.write_files(path, files or WORK_FILES)
        T.git(path, "add", "-A")
        T.git(path, "commit", "-m", "work")
        return path

    def logs(self, kit):
        with T.operator_shell(kit.main):
            return Path(self.mod().resolve_roots(kit.main)["logs_dir"])

    def run_main(self, kit, argv, cwd=None, unit_text=T.UNIT_PASS, build_rc=0):
        lc = self.mod()
        rec = SimpleNamespace(long=[], env=[], run=[], forbidden=[], acquired=[], released=[],
                              at_release=[], out="", err="", code=None)
        orig_run = lc._run
        logs_dir = self.logs(kit)

        def fake_long(cmd, *a, **k):
            rec.long.append([str(c) for c in cmd])
            rec.env.append(os.environ.get("CLAUDE_PROJECT_DIR"))
            outs = [str(c) for c in cmd if str(c).endswith("out.txt")]
            rc = build_rc
            if outs:
                Path(outs[0]).parent.mkdir(parents=True, exist_ok=True)
                Path(outs[0]).write_text(unit_text, encoding="utf-8")
                rc = 1 if "FAIL" in unit_text else 0
            return (rc, False)

        def fake_run(cmd, *a, **k):
            rec.run.append([str(c) for c in cmd])
            return orig_run(cmd, *a, **k)

        def forbid(name):
            def edge(*a, **k):
                rec.forbidden.append(name)
                return (0, "")
            return edge

        orig_acquire, orig_release = lc.lock_acquire, lc.lock_release

        def acquire(landing_dir, info):
            rec.acquired.append(dict(info))
            return orig_acquire(landing_dir, info)

        def release(landing_dir, run_id):
            rec.released.append(run_id)
            rec.at_release.append((logs_dir / "verify" / run_id / "report.json").exists())
            return orig_release(landing_dir, run_id)

        out, err = io.StringIO(), io.StringIO()
        with T.operator_shell(cwd or kit.main), contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(lc, "_run_long", side_effect=fake_long))
            stack.enter_context(mock.patch.object(lc, "_run", side_effect=fake_run))
            stack.enter_context(mock.patch.object(lc, "gh_auth_status", return_value=True))
            stack.enter_context(mock.patch.object(lc, "lock_acquire", side_effect=acquire))
            stack.enter_context(mock.patch.object(lc, "lock_release", side_effect=release))
            for name in ("exec_stage", "worktree_reset", "worktree_remove", "git_push", "git_merge",
                         "git_commit", "gh_pr_create", "gh_pr_merge"):
                stack.enter_context(mock.patch.object(lc, name, side_effect=forbid(name)))
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            try:
                rec.code = lc.main(argv)
            except SystemExit as exc:  # argparse refusing an unknown flag: reported as a failure below
                rec.code = exc.code
        rec.out, rec.err = out.getvalue(), err.getvalue()
        return rec

    def parsed(self, rec):
        try:
            return json.loads(rec.out)
        except ValueError:
            self.fail("stdout was not one JSON object (exit %r). stdout=%r stderr=%r"
                      % (rec.code, rec.out[:300], rec.err[-300:]))

    def git_subcommands(self, rec):
        found = []
        for argv in rec.run:
            if not argv or os.path.basename(argv[0]).lower().replace(".exe", "") != "git":
                continue
            i = 1
            while i < len(argv) and argv[i].startswith("-"):
                i += 2 if argv[i] in ("-c", "-C") else 1
            if i < len(argv):
                found.append(argv[i])
        return found

    def assert_no_mutation(self, rec):
        self.assertEqual(rec.forbidden, [], "no landing edge (reset, remove, push, merge, commit, "
                         "pull request, stage launch) is called by a verification or tag reading")
        self.assertEqual(sorted(set(self.git_subcommands(rec)) & FORBIDDEN_GIT), [],
                         "no reset, clean, push, merge, commit, stash or checkout command is launched")
        self.assertFalse(any("drift-marker" in " ".join(c) for c in rec.long),
                         "the generated-drift step (a regenerator) never runs")

    def verify(self, kit, extra=None, cwd=None, run_id=RUN_ID, **kw):
        argv = ["--verify-here"] + (["--run-id", run_id] if run_id else []) + (extra or []) + ["--json"]
        rec = self.run_main(kit, argv, cwd=cwd, **kw)
        report = self.parsed(rec)
        nc = report.get("next_command") or {}
        for line in nc.get("commands") or []:
            self.assertFalse(line.startswith("/advance") or line.startswith("/design-first"),
                             "no --verify-here outcome returns /advance or /design-first: %r" % line)
        return rec, report

    def listing(self, kit):
        out = []
        for sub in ("state", "logs"):
            root = kit.main / ".claude" / sub
            if root.exists():
                out += sorted(p.relative_to(kit.main).as_posix() for p in root.rglob("*"))
        return out


# ===========================================================================
# --module-tags
# ===========================================================================
class TestModuleTagsCommand(VerifyCase):

    def tags(self, kit, checkout, base="origin/master"):
        rec = self.run_main(kit, ["--module-tags", "--base", base, "--json"], cwd=checkout)
        return rec, self.parsed(rec)

    def test_it_prints_the_tags_unmapped_and_prefix_and_exits_zero(self):
        kit = self.make_kit()
        wt = self.work_checkout(kit, {"core/a.py": "1\n", "checks/test_a.py": "2\n"})
        rec, got = self.tags(kit, wt)
        self.assertEqual(rec.code, 0, msg="module-tags-read is a success")
        self.assertEqual(got.get("outcome"), "module-tags-read", msg="the outcome")
        self.assertEqual(got.get("tags"), ["CORE"], msg="coveredBy applied to the real diff")
        self.assertEqual(got.get("unmapped"), [], msg="every path mapped")
        self.assertEqual(got.get("prefix"), "[CORE]", msg="the prefix")
        self.assertEqual(got["next_command"]["commands"], [], msg="no follow-up command")
        self.assert_no_mutation(rec)

    def test_an_unmapped_path_is_listed(self):
        kit = self.make_kit()
        wt = self.work_checkout(kit, {"core/a.py": "1\n", "misc/y.txt": "2\n"})
        rec, got = self.tags(kit, wt)
        self.assertEqual(got.get("unmapped"), ["misc/y.txt"], msg="the ask-then-add rule needs it")

    def test_an_absent_prtitle_reports_every_path_unmapped_and_still_reads(self):
        kit = self.make_kit(conventions=json.dumps({"contractLanding": T.landing_config()}))
        wt = self.work_checkout(kit, {"core/a.py": "1\n"})
        rec, got = self.tags(kit, wt)
        self.assertEqual((rec.code, got.get("outcome")), (0, "module-tags-read"),
                         msg="no prTitle is still a reading")
        self.assertEqual((got.get("tags"), got.get("unmapped")), ([], ["core/a.py"]),
                         msg="every path unmapped")

    def test_a_base_ref_that_does_not_exist_is_base_unreadable(self):
        kit = self.make_kit()
        wt = self.work_checkout(kit)
        rec, got = self.tags(kit, wt, base="origin/does-not-exist")
        self.assertEqual(rec.code, 9, msg="base-unreadable is a halt")
        self.assertEqual(got.get("outcome"), "base-unreadable", msg="the outcome")
        self.assertEqual(got["next_command"]["commands"], [], msg="nothing to run")
        self.assertIn(BASE_REMEDY, got["next_command"]["reason"], "the reason is the remedy")


# ===========================================================================
# Outcome sets, exit codes, remedies and next commands (pure)
# ===========================================================================
class TestVerifyOutcomeSets(T.LandCase):

    def test_verify_outcomes_holds_exactly_the_four_new_members(self):
        got = getattr(self.mod(), "VERIFY_OUTCOMES", None)
        self.assertIsNotNone(got, "land_contract.VERIFY_OUTCOMES does not exist yet")
        self.assertEqual(set(got), NEW_MEMBERS, msg="exactly the four new members")

    def test_passes_today_by_design_landing_outcomes_is_unchanged(self):
        lc = self.mod()
        self.assertEqual(len(lc.LANDING_OUTCOMES), 29, msg="3 successes and 26 halts (issue 113 adds "
                                                           "version-raise-failed)")
        self.assertEqual(set(lc.LANDING_OUTCOMES) & NEW_MEMBERS, set(), msg="none of the new four")

    def test_verified_and_module_tags_read_are_successes_with_exit_zero(self):
        lc = self.mod()
        for outcome in ("verified", "module-tags-read"):
            self.assertIn(outcome, lc.SUCCESS_EXIT, "%s joins SUCCESS_EXIT" % outcome)
            self.assertEqual(lc.exit_code_for(outcome), 0, msg="%s exits 0" % outcome)
        for outcome in ("no-baseline", "base-unreadable"):
            self.assertEqual(lc.exit_code_for(outcome), 9, msg="%s is a halt" % outcome)

    def test_the_two_new_halts_have_their_remedies(self):
        remedies = self.mod().REMEDIES
        self.assertEqual(remedies.get("base-unreadable"), BASE_REMEDY, msg="base-unreadable remedy")
        self.assertEqual(remedies.get("no-baseline"), NO_BASELINE_REMEDY, msg="no-baseline remedy")

    def test_the_verify_next_commands(self):
        nc = self.fn("next_command_for_outcome")
        got = nc("verified", "", verify_here=True)
        self.assertEqual(got["commands"], [], msg="verified suggests no command")
        self.assertIn("Step 5", got["reason"], "the reason names /verify-before-done Step 5")
        got = nc("module-tags-read", "")
        self.assertEqual(got["commands"], [], msg="no command")
        self.assertIn("ask-then-add", got["reason"], "the reason keeps the ask-then-add rule")
        got = nc("no-baseline", "", verify_here=True)
        self.assertEqual((got["commands"], got.get("fallback")), ([], "prose-steps"),
                         msg="no-baseline falls back to the prose steps")
        self.assertEqual(got["reason"], NO_BASELINE_REMEDY, msg="the reason is the remedy")
        got = nc("base-unreadable", "")
        self.assertEqual(got["commands"], [], msg="no command")
        self.assertIn(BASE_REMEDY, got["reason"], "the reason is the remedy")

    def test_a_not_ready_verification_here_names_failures_and_has_no_fallback(self):
        got = self.fn("next_command_for_outcome")("verification-not-ready", "", verify_here=True,
                                                    new_failures=["scripts::tests.U::test_x"])
        self.assertEqual(got["commands"], [], msg="no landing command: nothing is being landed")
        self.assertNotIn("fallback", got, "a baseline exists, so the reading is trusted")
        self.assertIn("scripts::tests.U::test_x", got["reason"], "the new failure ids are named")

    def test_every_prose_arm_under_verify_here_falls_back(self):
        nc = self.fn("next_command_for_outcome")
        for outcome in ("environment-failure", "landing-not-configured", "baseline-unreadable",
                        "landing-in-progress", "base-unreadable"):
            got = nc(outcome, "", verify_here=True)
            self.assertEqual((got["commands"], got.get("fallback")), ([], "prose-steps"),
                             msg="%s under verify_here" % outcome)
            self.assertTrue(got.get("reason"), "%s carries the remedy as its reason" % outcome)

    def test_a_landing_that_finds_a_verify_lock_is_told_to_retry(self):
        got = self.fn("next_command_for_outcome")("landing-in-progress", "demo", live_kind="verify",
                                                    live="x")
        self.assertEqual(got["commands"], ["/advance demo"], msg="rerun after the self-check ends")

    def test_manual_landing_is_a_not_applicable_with_no_command(self):
        got = self.fn("next_command_for_outcome")("not-applicable", "demo", manual_landing=True)
        self.assertEqual(got["commands"], [], msg="the operator merges by hand")
        self.assertIn("landing: manual", got["reason"], "the reason names the field")

    def test_passes_today_by_design_the_ordinary_not_applicable_keeps_its_command(self):
        got = self.fn("next_command_for_outcome")("not-applicable", "demo")
        self.assertEqual(got["commands"], ["/verify-before-done"], msg="today's ending")


# ===========================================================================
# --verify-here
# ===========================================================================
class TestVerifyHereNoBaseline(VerifyCase):

    def test_no_baseline_runs_no_step_takes_no_lock_and_writes_a_report(self):
        kit = self.make_kit(baseline=None)
        wt = self.work_checkout(kit)
        rec, report = self.verify(kit, cwd=wt)
        self.assertEqual(rec.code, 9, msg="no-baseline is a halt")
        self.assertEqual(report.get("outcome"), "no-baseline", msg="the outcome")
        self.assertEqual(report["next_command"].get("fallback"), "prose-steps", msg="prose decides")
        self.assertEqual(rec.long, [], msg="no step command is launched")
        self.assertEqual(rec.acquired, [], msg="no lock is taken (V-1 a0)")
        self.assertFalse((kit.landing_dir() / "lock").exists(), "no lock file exists")
        path = self.logs(kit) / "verify" / RUN_ID / "report.json"
        self.assertTrue(path.is_file(), "report.json is written under logs_dir()/verify/<run_id>/")
        written = json.loads(path.read_text(encoding="utf-8"))
        steps = {s["id"]: s for s in written["steps"]}
        for sid in ("compile", "py-unit"):
            self.assertEqual((steps[sid]["ran"], steps[sid]["reading"]), (False, "not-run"),
                             msg="applicable step %s did not run" % sid)
        self.assert_no_mutation(rec)

    def test_a_baseline_only_on_the_operators_disk_is_still_no_baseline(self):
        kit = self.make_kit(baseline=None)
        wt = self.work_checkout(kit)
        T.write_files(wt, {T.BASELINE_FILE: json.dumps(T.BASELINE_CLEAN)})
        rec, report = self.verify(kit, cwd=wt)
        self.assertEqual(report.get("outcome"), "no-baseline",
                         msg="the baseline is read from origin/<default>, never from the disk")
        self.assertEqual(rec.long, [], msg="and nothing ran")


class TestVerifyHereWithBaseline(VerifyCase):

    def test_a_passing_run_is_verified_and_names_step_five(self):
        kit = self.make_kit()
        wt = self.work_checkout(kit)
        rec, report = self.verify(kit, cwd=wt)
        self.assertEqual(rec.code, 0, msg="verified exits 0")
        self.assertEqual(report.get("outcome"), "verified", msg="the outcome")
        self.assertIn("Step 5", report["next_command"]["reason"], "the reason names Step 5")
        self.assertEqual(report["next_command"]["commands"], [], msg="no command")
        self.assertTrue(any("-c" in c and "pass" in c for c in rec.long), "the exit-code step ran")
        self.assert_no_mutation(rec)

    def test_a_failing_run_is_not_ready_naming_the_new_failures_without_a_fallback(self):
        kit = self.make_kit()
        wt = self.work_checkout(kit)
        rec, report = self.verify(kit, cwd=wt, unit_text=T.UNIT_FAIL)
        self.assertEqual(rec.code, 9, msg="verification-not-ready is a halt")
        self.assertEqual(report.get("outcome"), "verification-not-ready", msg="the outcome")
        nc = report["next_command"]
        self.assertNotIn("fallback", nc, "a baseline exists, so the reading is trusted")
        self.assertIn("test_x", nc["reason"], "the new failure id is in the reason")

    def test_the_baseline_comes_from_origin_not_the_disk(self):
        kit = self.make_kit()
        wt = self.work_checkout(kit)
        (wt / T.BASELINE_FILE).unlink()
        rec, report = self.verify(kit, cwd=wt)
        self.assertEqual(report.get("outcome"), "verified",
                         msg="the baseline file is on origin/master, so deleting the disk copy changes nothing")

    def test_the_configuration_comes_from_the_disk(self):
        kit = self.make_kit()
        wt = self.work_checkout(kit)
        cfg = T.landing_config(steps=STEPS + [
            {"id": "disk-only", "suite": "extra", "when_paths": ["**"],
             "command": ["py", "-3", "-c", "disk-only-marker"], "results": {"format": "exit-code"},
             "timeout_minutes": 5, "environment_signatures": []}])
        T.write_files(wt, {T.CONVENTIONS: json.dumps({"contractLanding": cfg, "prTitle": PR_TITLE})})
        rec, report = self.verify(kit, cwd=wt)
        self.assertTrue(any("disk-only-marker" in " ".join(c) for c in rec.long),
                        "a step that exists only in the checkout's own file runs (a sub-task may add one)")

    def test_a_generated_drift_step_is_not_applicable_and_never_runs(self):
        kit = self.make_kit()
        wt = self.work_checkout(kit)
        rec, report = self.verify(kit, cwd=wt)
        written = json.loads((self.logs(kit) / "verify" / RUN_ID / "report.json").read_text("utf-8"))
        step = {s["id"]: s for s in written["steps"]}["generated-drift"]
        self.assertEqual((step["applicable"], step["reading"]), (False, "not-applicable"),
                         msg="Step 4 regenerates in the operator tree, so the runner leaves it")
        self.assertFalse(any("drift-marker" in " ".join(c) for c in rec.long), "and never launches it")

    def test_children_see_the_checkout_as_the_project_dir(self):
        kit = self.make_kit()
        wt = self.work_checkout(kit)
        rec, _ = self.verify(kit, cwd=wt)
        self.assertTrue(rec.env, "at least one step ran")
        for value in rec.env:
            self.assertEqual(norm(value or ""), norm(wt), msg="L-14': the current checkout, not the main root")

    def test_the_report_is_in_the_main_roots_logs_and_written_before_the_lock_is_released(self):
        kit = self.make_kit()
        wt = self.work_checkout(kit)
        rec, report = self.verify(kit, cwd=wt)
        expected = self.logs(kit) / "verify" / RUN_ID / "report.json"
        self.assertEqual(norm(report.get("report_path", "")), norm(expected),
                         msg="report_path is absolute and under logs_dir()/verify/<run_id>/")
        self.assertTrue(Path(report["report_path"]).is_absolute(), "absolute")
        self.assertEqual(report.get("run_id"), RUN_ID, msg="the report carries the run id")
        self.assertEqual([a.get("kind") for a in rec.acquired], ["verify"], msg="a verify lock")
        self.assertEqual([a.get("run_id") for a in rec.acquired], [RUN_ID],
                         msg="the lock's run_id is the verification run id, so its scope is verify/<run_id>")
        self.assertEqual(rec.released, [rec.acquired[0]["run_id"]] if rec.acquired else [],
                         msg="released once, by its own run id")
        self.assertEqual(rec.at_release, [True], msg="report.json existed when the lock was released")

    def test_a_landing_lock_halts_it_without_running_a_step(self):
        kit = self.make_kit()
        wt = self.work_checkout(kit)
        T.write_files(kit.landing_dir(), {"lock": json.dumps(
            {"pid": self.live_pid(), "run_id": "old", "kind": "land", "contract": SLUG,
             "started_at": "2026-10-05T00:00:00Z"})})
        rec, report = self.verify(kit, cwd=wt)
        self.assertEqual((rec.code, report.get("outcome")), (9, "landing-in-progress"),
                         msg="neither side waits on the other")
        self.assertEqual(report["next_command"].get("fallback"), "prose-steps", msg="prose decides")
        self.assertEqual(rec.long, [], msg="no step ran")

    def test_a_missing_contract_landing_block_is_landing_not_configured(self):
        kit = self.make_kit(conventions="{}")
        wt = self.work_checkout(kit)
        rec, report = self.verify(kit, cwd=wt)
        self.assertEqual((rec.code, report.get("outcome")), (9, "landing-not-configured"),
                         msg="no contractLanding block")
        self.assertEqual(report["next_command"].get("fallback"), "prose-steps", msg="prose decides")

    def test_an_unreadable_baseline_is_baseline_unreadable(self):
        kit = self.make_kit(baseline="[1, 2]")
        wt = self.work_checkout(kit)
        rec, report = self.verify(kit, cwd=wt)
        self.assertEqual((rec.code, report.get("outcome")), (9, "baseline-unreadable"),
                         msg="a baseline that is not an object")
        self.assertEqual(report["next_command"].get("fallback"), "prose-steps", msg="prose decides")

    def test_a_base_ref_that_does_not_exist_is_base_unreadable(self):
        kit = self.make_kit()
        wt = self.work_checkout(kit)
        rec, report = self.verify(kit, extra=["--base", "origin/does-not-exist"], cwd=wt)
        self.assertEqual((rec.code, report.get("outcome")), (9, "base-unreadable"), msg="no such ref")
        self.assertEqual(report["next_command"].get("fallback"), "prose-steps", msg="prose decides")


class TestVerifyHereRunIdAndLocator(VerifyCase):

    def locate(self, kit, run_id=RUN_ID, cwd=None, with_id=True):
        argv = ["--verify-here"] + (["--run-id", run_id] if with_id else []) + ["--status", "--json"]
        rec = self.run_main(kit, argv, cwd=cwd)
        return rec, self.parsed(rec)

    def test_a_run_writes_a_report_carrying_the_given_run_id(self):
        kit = self.make_kit(baseline=None)
        rec, report = self.verify(kit)
        path = Path(report.get("report_path", ""))
        self.assertTrue(path.is_absolute(), "report_path is absolute")
        self.assertEqual(norm(path), norm(self.logs(kit) / "verify" / RUN_ID / "report.json"),
                         msg="under logs_dir()/verify/<that id>/")
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")).get("run_id"), RUN_ID,
                         msg="the file carries the id")

    def test_the_locator_returns_the_report_and_changes_nothing(self):
        kit = self.make_kit(baseline=None)
        self.verify(kit)
        before = self.listing(kit)
        rec, got = self.locate(kit)
        self.assertEqual(rec.code, 0, msg="the locator always exits 0")
        self.assertEqual(got.get("state"), "report", msg="a report of this run exists")
        self.assertEqual(got.get("run_id"), RUN_ID, msg="the id")
        self.assertEqual(norm(got.get("report_path", "")),
                         norm(self.logs(kit) / "verify" / RUN_ID / "report.json"), msg="same path")
        self.assertEqual((got.get("report") or {}).get("outcome"), "no-baseline",
                         msg="the parsed report is returned")
        self.assertEqual(self.listing(kit), before, "no lock and no file is created")
        self.assertEqual(rec.acquired, [], msg="no lock is taken")

    def test_an_id_with_no_trace_is_none(self):
        kit = self.make_kit(baseline=None)
        rec, got = self.locate(kit, run_id="verify-20261008T130000Z-000000")
        self.assertEqual((rec.code, got.get("state"), got.get("report")), (0, "none", None),
                         msg="no folder, no lock")

    def test_a_report_of_another_run_is_interrupted_with_no_report(self):
        kit = self.make_kit(baseline=None)
        folder = self.logs(kit) / "verify" / RUN_ID
        T.write_files(folder, {"report.json": json.dumps({"run_id": "someone-else", "outcome": "verified"})})
        rec, got = self.locate(kit)
        self.assertEqual((got.get("state"), got.get("report")), ("interrupted", None),
                         msg="a report of another run_id is not this run's report")

    def test_an_unparseable_report_is_interrupted(self):
        kit = self.make_kit(baseline=None)
        T.write_files(self.logs(kit) / "verify" / RUN_ID, {"report.json": "{not json"})
        rec, got = self.locate(kit)
        self.assertEqual((got.get("state"), got.get("report")), ("interrupted", None),
                         msg="an unparseable file")

    def test_a_live_verify_lock_for_the_id_is_live(self):
        kit = self.make_kit(baseline=None)
        T.write_files(kit.landing_dir(), {"lock": json.dumps(
            {"pid": self.live_pid(), "run_id": RUN_ID, "kind": "verify", "contract": None,
             "started_at": "2026-10-08T12:00:00Z"})})
        rec, got = self.locate(kit)
        self.assertEqual(got.get("state"), "live", msg="L-17: the launcher process is alive")

    def test_a_dead_verify_lock_with_no_report_is_interrupted(self):
        kit = self.make_kit(baseline=None)
        dead = T.subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        T.write_files(kit.landing_dir(), {"lock": json.dumps(
            {"pid": dead.pid, "run_id": RUN_ID, "kind": "verify", "contract": None,
             "started_at": "2026-10-08T12:00:00Z"})})
        rec, got = self.locate(kit)
        self.assertEqual((got.get("state"), got.get("report")), ("interrupted", None),
                         msg="nothing live and no report")

    def refusal(self, kit, argv, before):
        rec = self.run_main(kit, argv)
        got = self.parsed(rec)
        self.assertEqual(rec.code, 2, msg="a refused run id exits 2")
        self.assertEqual(got.get("error"), "run-id-invalid", msg="the error")
        nc = got.get("next_command") or {}
        self.assertEqual((nc.get("commands"), nc.get("fallback")), ([], "prose-steps"),
                         msg="prose takes over")
        self.assertEqual(nc.get("reason"), INVALID_ID_REASON, msg="the fixed reason")
        self.assertEqual(rec.long, [], msg="nothing ran")
        self.assertEqual(self.listing(kit), before, "nothing was written")

    def test_a_path_like_run_id_is_refused_on_a_run_and_on_a_status(self):
        kit = self.make_kit(baseline=None)
        before = self.listing(kit)
        self.refusal(kit, ["--verify-here", "--run-id", "../x", "--json"], before)
        self.refusal(kit, ["--verify-here", "--run-id", "../x", "--status", "--json"], before)

    def test_status_without_a_run_id_is_refused(self):
        kit = self.make_kit(baseline=None)
        self.refusal(kit, ["--verify-here", "--status", "--json"], self.listing(kit))

    def test_a_run_id_whose_folder_already_exists_is_refused_on_a_run(self):
        kit = self.make_kit(baseline=None)
        (self.logs(kit) / "verify" / RUN_ID).mkdir(parents=True)
        self.refusal(kit, ["--verify-here", "--run-id", RUN_ID, "--json"], self.listing(kit))

    def test_positive_control_a_run_without_an_id_makes_its_own(self):
        kit = self.make_kit(baseline=None)
        rec, report = self.verify(kit, run_id=None)
        self.assertRegex(report.get("run_id", ""), r"^\d{8}T\d{6}Z-[0-9a-f]{6}$",
                         "a manual run gets new_run_id()'s shape")
        self.assertTrue(Path(report["report_path"]).is_file(), "and its report is written")

    def test_help_lists_the_new_flags(self):
        kit = self.make_kit(baseline=None)
        rec = self.run_main(kit, ["--help"])
        for flag in ("--verify-here", "--module-tags", "--run-id", "--base"):
            self.assertIn(flag, rec.out, "--help lists %s" % flag)


class TestVerifyOutcomesAreTotal(VerifyCase):

    def test_every_outcome_either_command_returns_is_in_one_of_the_two_sets(self):
        lc = self.mod()
        known = set(lc.LANDING_OUTCOMES) | set(getattr(lc, "VERIFY_OUTCOMES", ()))
        seen = {}
        base = self.make_kit(sub="a", baseline=None)
        wt = self.work_checkout(base, {"core/a.py": "1\n"})
        seen["tags"] = self.run_main(base, ["--module-tags", "--base", "origin/master", "--json"], cwd=wt)
        seen["tags-bad"] = self.run_main(base, ["--module-tags", "--base", "origin/nope", "--json"], cwd=wt)
        seen["no-baseline"] = self.run_main(base, ["--verify-here", "--run-id", RUN_ID, "--json"], cwd=wt)
        ok = self.make_kit(sub="b")
        wt2 = self.work_checkout(ok)
        seen["verified"] = self.run_main(ok, ["--verify-here", "--run-id", RUN_ID, "--json"], cwd=wt2)
        seen["not-ready"] = self.run_main(ok, ["--verify-here", "--run-id", "verify-2", "--json"], cwd=wt2,
                                          unit_text=T.UNIT_FAIL)
        seen["bad-base"] = self.run_main(ok, ["--verify-here", "--run-id", "verify-3", "--base",
                                              "origin/nope", "--json"], cwd=wt2)
        bare = self.make_kit(sub="c", conventions="{}")
        wt3 = self.work_checkout(bare)
        seen["not-configured"] = self.run_main(bare, ["--verify-here", "--run-id", RUN_ID, "--json"], cwd=wt3)
        outcomes = {name: self.parsed(rec).get("outcome") for name, rec in seen.items()}
        for name, outcome in outcomes.items():
            self.assertIn(outcome, known, "%s returned %r, which is in neither closed set" % (name, outcome))
        self.assertEqual(set(outcomes.values()) & NEW_MEMBERS, NEW_MEMBERS,
                         "the scenarios reach all four new outcomes")


# ===========================================================================
# Lock contention between a verification run and a landing
# ===========================================================================
class TestLockKinds(VerifyCase):

    def write_lock(self, kit, kind, run_id="old-run", contract=None):
        T.write_files(kit.landing_dir(), {"lock": json.dumps(
            {"pid": self.live_pid(), "run_id": run_id, "kind": kind, "contract": contract,
             "started_at": "2026-10-08T12:00:00Z"})})

    def test_a_landing_that_finds_a_verify_lock_halts_with_a_retry_command(self):
        kit = T.Kit(self._tmp.name)
        self.write_lock(kit, "verify")
        code, execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "landing-in-progress", msg="the lock is held")
        self.assertEqual(report["next_command"]["commands"], ["/advance %s" % SLUG],
                         msg="the landing retries after the self-check ends")
        execm.assert_not_called()

    def test_passes_today_by_design_a_landing_lock_gives_no_retry_command(self):
        kit = T.Kit(self._tmp.name)
        self.write_lock(kit, "land", contract="other-contract")
        code, execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "landing-in-progress", msg="the lock is held")
        self.assertEqual(report["next_command"]["commands"], [], msg="positive control: only a verify lock retries")

    def test_status_of_a_verify_lock_reads_the_verify_phase_not_the_baseline_phase(self):
        kit = T.Kit(self._tmp.name)
        self.write_lock(kit, "verify", run_id=RUN_ID)
        T.write_files(self.logs(kit) / "verify" / RUN_ID,
                      {"phase.json": json.dumps({"run_id": RUN_ID, "phase": "verify-marker"})})
        T.write_files(kit.landing_dir() / "_baseline", {"phase.json": json.dumps({"phase": "decoy"})})
        self.launch(kit, argv=["--contract", SLUG, "--status", "--json"])
        got = json.loads(self.stdout)
        self.assertEqual(got.get("state"), "live", msg="the holder is alive")
        self.assertEqual((got.get("phase") or {}).get("phase"), "verify-marker",
                         msg="verify/<run_id>/phase.json, never _baseline/phase.json")

    def test_passes_today_by_design_status_of_a_landing_lock_reads_its_contract_phase(self):
        kit = T.Kit(self._tmp.name)
        self.write_lock(kit, "land", run_id="r1", contract=SLUG)
        T.write_files(kit.landing_dir() / SLUG, {"phase.json": json.dumps({"phase": "p7-marker"})})
        self.launch(kit, argv=["--contract", SLUG, "--status", "--json"])
        self.assertEqual((json.loads(self.stdout).get("phase") or {}).get("phase"), "p7-marker",
                         msg="positive control: the landing's own phase file")


# ===========================================================================
# L-18 and the shared parent_brief_of
# ===========================================================================
BRIEF_PATH = T.BRIEF_DIR + "2026-10-05-394-demo.md"


def manual_brief():
    return T.brief_md(394, branch=PARENT, parent_issue=None).replace(
        "status: implementing", "status: implementing\nlanding: manual")


class TestManualLanding(T.StageCase):

    def fake_parent_brief_of(self, calls):
        def fake(*a, **k):
            calls.append((a, k))
            briefs = a[1] if len(a) > 1 else k.get("briefs")
            return next((b for b in briefs if b.get("branch") == PARENT and str(b.get("id")) == "394"), None)
        return fake

    def manual_stage(self, **extra):
        files = dict(self.src_change(), **{BRIEF_PATH: manual_brief()})
        files.update(extra)
        return self.stage(parent_files=files)

    def test_a_manual_parent_brief_ends_the_landing_at_p1_as_not_applicable(self):
        st = self.manual_stage()
        report = st.run()
        self.assertOutcome(report, "not-applicable", "landing: manual ends the landing at P1")
        self.assertEqual(self.mod().exit_code_for(report["outcome"]), 0, "exit 0")
        self.assertEqual(report["next_command"]["commands"], [], "the operator merges by hand")
        self.assertIn("landing: manual", report["next_command"]["reason"], "the reason names the field")
        for edge in ("git_merge", "git_commit", "git_push", "gh_pr_create", "gh_pr_ready", "gh_pr_merge",
                     "worktree_remove", "_run_long"):
            self.assertEqual(st.count(edge), 0, "a manual landing must not call %s" % edge)
        self.assertFalse(any(len(c) > 1 and c[0] == "git" and c[1] in ("reset", "clean", "push", "merge")
                             for c in st.argv_seen), "no reset, clean, push or merge command")

    def test_p1_finds_the_parent_brief_through_pr_merged_parent_brief_of(self):
        st = self.manual_stage()
        calls = []
        with mock.patch.object(pr_merged, "parent_brief_of", create=True,
                               side_effect=self.fake_parent_brief_of(calls)):
            report = st.run()
        self.assertGreaterEqual(len(calls), 1, "P1 calls pr_merged.parent_brief_of, not its own copy")
        first = calls[0][0][0] if calls[0][0] else calls[0][1].get("contract_id")
        self.assertEqual(first, T.SLUG, "with the contract id first")
        self.assertOutcome(report, "not-applicable", "the brief it returned is the one that carries the field")

    def test_a_dry_run_records_manual_landing_and_reaches_p5(self):
        st = self.manual_stage()
        report = st.run(dry_run=True)
        self.assertIs(report.get("manual_landing"), True, "a dry run records manual_landing: true")
        self.assertEqual(report.get("gate"), "P5", "and goes on through P5")
        self.assertEqual(report.get("outcome"), "landing-in-progress", "the dry-run ending")

    def test_passes_today_by_design_a_brief_without_the_field_proceeds_past_p1(self):
        st = self.stage(parent_files=self.src_change())
        self.assertOutcome(st.run(), "landed", "positive control: the same world without the field lands")

    def test_passes_today_by_design_a_dry_run_without_the_field_records_no_manual_landing(self):
        st = self.stage(parent_files=self.src_change())
        report = st.run(dry_run=True)
        self.assertFalse(report.get("manual_landing"), "positive control: only the field sets it")
        self.assertEqual(report.get("gate"), "P5", "and the dry run still reaches P5")


if __name__ == "__main__":
    unittest.main()
