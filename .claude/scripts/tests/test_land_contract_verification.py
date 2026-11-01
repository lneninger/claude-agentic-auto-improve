#!/usr/bin/env python3
"""
RED-phase tests for contract 2026-10-07-landing-and-loop-hardening, block 3: W4, W8, W9 and I10.

  W4  the unit of a unittest-text result is the dotted class in BOTH Python line formats, so a new
      failure in an already-failing class still counts as new; the python-* step command prints one
      line per test.
  W8  the Verification Record lists every configured step with applicable / ran, the baseline is
      {path, measured_at_commit} or the text "absent", baseline_commit is gone, the repeat rule reads
      the new key (fallback: the old one), and the two readers (no step applies, "<ran> of <configured>").
  W9  applicable_steps expands sentinel: tokens, and the landing's real call site (_p8_verify) selects
      the generated-drift step from a sentinel-path diff.
  I10 P12 halts "unverifiable" when the children read fails.

Reuse: the process guard, the guarded import of land_contract, and the Kit / Stage fixtures are those of
test_land_contract.py, imported once (``tlc``) rather than copied, so the guard that refuses a real push,
a real merge and any git run inside this checkout is the very same one. The module is imported BEFORE
anything else touches land_contract, so the guard is installed first. ``land_contract`` is None when the
module is absent, and every symbol is looked up with getattr, so a missing symbol is an AssertionError.

Tests that pass today by design are named ``test_positive_control_*`` or say so in their docstring.

Run: py -3 -B .claude/scripts/tests/test_land_contract_verification.py
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_land_contract as tlc  # noqa: E402  (installs the process guard, then imports land_contract)

land_contract = tlc.land_contract
REPO_ROOT = tlc.REPO_ROOT
sha40 = tlc.sha40
git = tlc.git
write_files = tlc.write_files

setUpModule = tlc.setUpModule
tearDownModule = tlc.tearDownModule

RECORD_SLUG = tlc.SLUG
NEW_FAILURE = "scripts::tests.U::test_x"      # what UNIT_FAIL reports as new against a clean baseline
NO_CONFIG_REASON = "no contractLanding in this project's conventions (parent contract L-12)"


class VerCase(unittest.TestCase):
    """Asserts the module and each symbol exist before anything else (the _fn pattern)."""

    def mod(self):
        self.assertIsNotNone(land_contract, "land_contract.py does not exist yet")
        return land_contract

    def fn(self, name):
        f = getattr(self.mod(), name, None)
        self.assertIsNotNone(f, "land_contract.%s does not exist yet" % name)
        return f


# ===========================================================================
# W4: the unit of a unittest-text result
# ===========================================================================
FORMAT_WITH_METHOD = "test_x (pkg.Mod.TestA.test_x) ... ok\n"      # Python 3.11 and later
FORMAT_CLASS_ONLY = "test_x (pkg.Mod.TestA) ... ok\n"              # Python 3.10 and earlier


class TestParseUnittestTextUnit(VerCase):

    def units(self, text):
        got = self.fn("parse_unittest_text")(text)
        self.assertIsNotNone(got, "a verbose line must parse")
        return [(r["unit"], r["name"]) for r in got]

    def test_positive_control_the_line_that_ends_in_the_test_name_gives_the_class(self):
        self.assertEqual(self.units(FORMAT_WITH_METHOD), [("pkg.Mod.TestA", "test_x")],
                         "'test_x (pkg.Mod.TestA.test_x)': strip the test name, keep the class")

    def test_the_line_that_names_only_the_class_gives_the_class(self):
        self.assertEqual(self.units(FORMAT_CLASS_ONLY), [("pkg.Mod.TestA", "test_x")],
                         "'test_x (pkg.Mod.TestA)': the dotted name IS the class, nothing is stripped")

    def test_both_formats_in_one_output_give_the_same_unit(self):
        got = self.units(FORMAT_WITH_METHOD + "test_y (pkg.Mod.TestA) ... FAIL\n")
        self.assertEqual({u for u, _ in got}, {"pkg.Mod.TestA"}, "one class, whatever the line format")


class TestReadStepNewFailureInAKnownFailingClass(VerCase):
    STEP = {"id": "python-scripts", "suite": "python-scripts", "results": {"format": "unittest-text"}}
    BASELINE = {"python-scripts": {"known_failing": {"python-scripts::test_widget.TestW": ["test_old"]},
                                   "known_flaky": []}}
    NEW_ID = "python-scripts::test_widget.TestW::test_new"

    def read(self, text):
        run = {"launched": True, "exit_code": 1, "timed_out": False, "log_text": "", "results_text": text}
        return self.fn("read_step")(self.STEP, run, self.BASELINE)

    def test_positive_control_class_in_the_method_suffix_format(self):
        got = self.read("test_old (test_widget.TestW.test_old) ... FAIL\n"
                        "test_new (test_widget.TestW.test_new) ... FAIL\n"
                        "test_ok (test_widget.TestW.test_ok) ... ok\n")
        self.assertEqual(got["new_failures"], [self.NEW_ID], "only test_new is new; test_old is baselined")

    def test_a_new_failure_in_a_known_failing_class_is_new_in_the_class_only_format(self):
        got = self.read("test_old (test_widget.TestW) ... FAIL\n"
                        "test_new (test_widget.TestW) ... FAIL\n"
                        "test_ok (test_widget.TestW) ... ok\n")
        self.assertEqual(got["new_failures"], [self.NEW_ID],
                         "the class-only format must map to the same unit as the baseline records, so "
                         "test_old stays known and ONLY test_new is new (the t6 W4 probe, inverted)")
        self.assertEqual(got["reading"], "regression", "a new failure is a regression")


# ===========================================================================
# W8: the Verification Record, on _p8_verify in a temporary repository
# ===========================================================================
def _ok_step(step_id, when_paths=None):
    step = {"id": step_id, "suite": step_id, "command": [sys.executable, "-c", "pass"],
            "results": {"format": "exit-code"}, "timeout_minutes": 1, "environment_signatures": []}
    if when_paths is not None:
        step["when_paths"] = when_paths
    return step


class RepoCase(VerCase):
    """A temporary repository with a sentinel-paths file, a conventions file and one tracked file."""

    SENTINEL = {"rest": ["src/Api/*.cs"], "hub": ["src/Hubs/*.cs"], "graphql": ["src/Gql/*.cs"]}

    def setUp(self):
        self.mod()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.repo = base / "repo"
        self.repo.mkdir()
        self.logs = base / "logs"
        self.contract_dir = base / "contract"
        git(self.repo, "init", "--initial-branch=master")
        git(self.repo, "config", "user.name", "t")
        git(self.repo, "config", "user.email", "t@example.test")
        git(self.repo, "config", "core.autocrlf", "false")
        git(self.repo, "config", "commit.gpgsign", "false")
        write_files(self.repo, {
            ".claude/hooks/sentinel-paths.json": json.dumps(self.SENTINEL),
            ".claude/work-item-conventions.json": json.dumps({"contractLanding": {"verification": {"steps": []}}}),
            "src/Api/gen.txt": "generated\n", "README.md": "demo\n"})
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "initial")
        head = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "update-ref", "refs/remotes/origin/master", head)   # the default ref the landing reads
        self.head = head

    def verify(self, steps, contract_diff, merge_diff=(), baseline_note="absent", fingerprint=None,
               emulators=(), baseline=None):
        config = {"verification": {"steps": steps}, "emulators": list(emulators),
                  "reviewCoverage": [], "forbiddenPaths": []}
        return self.fn("_p8_verify")(
            self.repo, self.head, config, baseline or {}, baseline_note, fingerprint,
            list(contract_diff), list(merge_diff), [], {}, [], self.logs, self.contract_dir,
            "run-1", "origin/master")

    @staticmethod
    def entry(summary, step_id):
        found = [s for s in summary["steps"] if s.get("id") == step_id]
        return found[0] if found else None


class TestVerificationRecordShape(RepoCase):
    STEPS = [_ok_step("docs-only", ["docs/**"]), _ok_step("src-only", ["src/**"]), _ok_step("always")]

    def test_the_record_lists_every_configured_step(self):
        got = self.verify(self.STEPS, ["src/x.py"])
        self.assertEqual([s["id"] for s in got["steps"]], ["docs-only", "src-only", "always"],
                         "every configured step is in the record, in configured order, applicable or not")

    def test_a_step_that_does_not_apply_reads_not_applicable(self):
        entry = self.entry(self.verify(self.STEPS, ["src/x.py"]), "docs-only")
        self.assertIsNotNone(entry, "the non-applicable step must still be listed")
        self.assertIs(entry.get("applicable"), False, "applicable is false")
        self.assertIs(entry.get("ran"), False, "applicable false implies ran false")
        self.assertEqual(entry.get("reading"), "not-applicable", "and the reading is not-applicable")

    def test_a_step_that_ran_says_so(self):
        entry = self.entry(self.verify(self.STEPS, ["src/x.py"]), "src-only")
        self.assertIs(entry.get("applicable"), True, "the step applies")
        self.assertIs(entry.get("ran"), True, "and it ran")
        self.assertEqual(entry.get("reading"), "ok", "and read ok")

    def test_a_step_stopped_by_an_emulator_preflight_applies_but_did_not_run(self):
        steps = [dict(_ok_step("gated", ["src/**"]))]
        emulator = {"id": "emu", "host": "127.0.0.1", "port": 9, "gates_steps": ["gated"], "start_hint": "start it"}
        with mock.patch.object(self.mod(), "tcp_probe", return_value=False):
            entry = self.entry(self.verify(steps, ["src/x.py"], emulators=[emulator]), "gated")
        self.assertIsNotNone(entry, "the gated step is listed")
        self.assertIs(entry.get("applicable"), True, "it applies")
        self.assertIs(entry.get("ran"), False, "but the pre-flight stopped it before it ran")
        self.assertEqual(entry.get("reading"), "environment", "an environment reading")

    def test_the_baseline_is_a_path_and_a_measured_commit(self):
        got = self.verify(self.STEPS, ["src/x.py"], baseline_note=".claude/test-baseline.json",
                          fingerprint=sha40("0"))
        self.assertEqual(got["baseline"], {"path": ".claude/test-baseline.json",
                                           "measured_at_commit": sha40("0")},
                         "baseline is {path, measured_at_commit}")

    def test_positive_control_an_absent_baseline_is_the_text_absent(self):
        got = self.verify(self.STEPS, ["src/x.py"], baseline_note="absent", fingerprint=None)
        self.assertEqual(got["baseline"], "absent", "no baseline file reads as the text 'absent'")

    def test_the_record_no_longer_carries_baseline_commit(self):
        got = self.verify(self.STEPS, ["src/x.py"], baseline_note=".claude/test-baseline.json",
                          fingerprint=sha40("0"))
        self.assertNotIn("baseline_commit", got, "baseline_commit is replaced by baseline.measured_at_commit")


class TestVerificationRecordReaders(RepoCase):

    def test_positive_control_configured_but_no_step_applies_reads_ready_with_the_reason(self):
        steps = [_ok_step("docs-only", ["docs/**"]), _ok_step("src-only", ["src/**"])]
        got = self.verify(steps, ["README.md"])
        self.assertEqual(got["verdict"], "READY", "nothing applies, so nothing can fail")
        self.assertIn("configured, but no step applies", got["reasons"],
                      "the reading fires when no entry has applicable true, even though every step is listed")

    def test_the_pull_request_body_counts_the_steps_that_ran(self):
        summary = {"verdict": "READY", "head": "h" * 40, "new_failures": [], "baseline": "absent",
                   "steps": [{"id": "a", "applicable": True, "ran": True},
                             {"id": "b", "applicable": False, "ran": False},
                             {"id": "c", "applicable": False, "ran": False}]}
        body = self.fn("_pr_body")("394", "demo", "feature/p", "master", summary, [])
        self.assertIn("1 of 3 step(s) ran", body,
                      "three configured, one ran: the body says '1 of 3 step(s) ran'")


# ===========================================================================
# W8: the repeat rule, through run_landing with a previous report on disk
# ===========================================================================
class TestRepeatRuleReadsTheNewBaselineKey(tlc.StageCase):
    BASELINE_PATH = ".claude/test-baseline.json"

    def halted_next_command(self, previous_baseline):
        """Seed a previous verification-not-ready report, run a landing whose step fails the same test
        against a baseline measured at sha40('0'), and return the new report's next_command."""
        kit = tlc.Kit(Path(self._tmp.name), parent_files=self.src_change())
        verification = {"new_failures": [NEW_FAILURE]}
        verification.update(previous_baseline)
        seed = kit.landing_dir() / RECORD_SLUG
        seed.mkdir(parents=True, exist_ok=True)
        (seed / "report.json").write_text(json.dumps({
            "run_id": "run-0", "contract": RECORD_SLUG, "outcome": "verification-not-ready",
            "gate": "P8", "verification": verification}), encoding="utf-8")
        st = tlc.Stage(self, kit)
        st.step_outputs["py-unit"] = tlc.UNIT_FAIL
        report = st.run()
        self.assertOutcome(report, "verification-not-ready", "the step fails a test the baseline does not know")
        return report["next_command"]

    def test_the_same_measured_commit_as_last_time_is_not_a_repeat(self):
        nc = self.halted_next_command({"baseline": {"path": self.BASELINE_PATH,
                                                    "measured_at_commit": sha40("0")}})
        self.assertFalse(nc.get("repeat_after_rerecord"),
                         "baseline.measured_at_commit is unchanged, so nobody re-recorded in between")

    def test_a_moved_measured_commit_with_the_same_failure_is_a_repeat(self):
        """Passes today by accident (the old key is simply missing); kept to pin the new key's meaning."""
        nc = self.halted_next_command({"baseline": {"path": self.BASELINE_PATH,
                                                    "measured_at_commit": sha40("1")}})
        self.assertTrue(nc.get("repeat_after_rerecord"), "the baseline moved and the failure came back")
        self.assertEqual(nc["commands"], ["/design-first %s" % RECORD_SLUG], "a repeat routes to /design-first")

    def test_positive_control_a_report_written_before_the_change_falls_back_to_baseline_commit(self):
        nc = self.halted_next_command({"baseline": self.BASELINE_PATH, "baseline_commit": sha40("1")})
        self.assertTrue(nc.get("repeat_after_rerecord"), "the old key, moved, still reads as a repeat")

    def test_positive_control_the_old_key_unchanged_is_not_a_repeat(self):
        nc = self.halted_next_command({"baseline": self.BASELINE_PATH, "baseline_commit": sha40("0")})
        self.assertFalse(nc.get("repeat_after_rerecord"), "the old key, unchanged, is not a repeat")

    def test_neither_key_present_is_not_a_repeat(self):
        nc = self.halted_next_command({"baseline": "absent"})
        self.assertFalse(nc.get("repeat_after_rerecord"),
                         "unknown is never a repeat: the previous baseline could not be compared")


# ===========================================================================
# W9: applicable_steps with expand, and the landing's real call site
# ===========================================================================
class TestApplicableStepsExpand(VerCase):
    TOKEN_STEP = {"id": "drift", "when_paths": ["sentinel:rest"]}

    def call(self, steps, contract_diff, merge_diff=(), **kw):
        try:
            return self.fn("applicable_steps")(steps, contract_diff, merge_diff, **kw)
        except TypeError as exc:
            self.fail("applicable_steps does not accept the expand argument: %s" % exc)

    def test_positive_control_three_arguments_match_literally_as_today(self):
        got = self.fn("applicable_steps")([self.TOKEN_STEP, {"id": "lit", "when_paths": ["src/**"]}],
                                          ["src/Api/X.cs"], [])
        self.assertEqual(got, ["lit"], "without expand a token is just a glob that matches no path")

    def test_expand_none_is_the_literal_match(self):
        got = self.call([self.TOKEN_STEP, {"id": "lit", "when_paths": ["src/**"]}], ["src/Api/X.cs"], expand=None)
        self.assertEqual(got, ["lit"], "expand=None keeps today's literal match")

    def test_a_token_entry_is_matched_through_expand(self):
        got = self.call([self.TOKEN_STEP], ["src/Api/X.cs"], expand=lambda entries: ["src/Api/*.cs"])
        self.assertEqual(got, ["drift"], "the expanded glob matches the changed file")

    def test_expand_receives_one_steps_when_paths_list(self):
        seen = []
        self.call([self.TOKEN_STEP], ["src/Api/X.cs"], expand=lambda e: (seen.append(list(e)), ["src/Api/*.cs"])[1])
        self.assertEqual(seen, [["sentinel:rest"]], "the callable is handed that step's when_paths list")

    def test_a_step_whose_entries_expand_to_nothing_is_not_applicable(self):
        got = self.call([self.TOKEN_STEP], ["src/Api/X.cs"], expand=lambda entries: [])
        self.assertEqual(got, [], "an empty expansion matches nothing, so the step does not apply")

    def test_a_step_with_no_when_paths_still_applies(self):
        got = self.call([{"id": "always"}], ["README.md"], expand=lambda entries: [])
        self.assertEqual(got, ["always"], "no when_paths means every diff")

    def test_positive_control_literal_when_paths_select_through_an_identity_expand(self):
        got = self.call([{"id": "lit", "when_paths": ["src/**"]}], ["src/a.py"], expand=lambda entries: list(entries))
        self.assertEqual(got, ["lit"], "an identity expand selects exactly as the literal match does")


DRIFT_STANDIN = (
    "import subprocess, sys\n"
    "if sys.argv[1] == 'change':\n"
    "    open('src/Api/gen.txt', 'a').write('regenerated\\n')\n"
    "out = subprocess.run(['git', 'status', '--porcelain'], capture_output=True, text=True).stdout\n"
    "print(out)\n"
    "sys.exit(1 if out.strip() else 0)\n")


class TestGeneratedDriftIsSelectedByTheLandingCallSite(RepoCase):

    def drift_step(self, mode):
        step = _ok_step("generated-drift", ["sentinel:rest"])
        step["command"] = [sys.executable, "-c", DRIFT_STANDIN, mode]
        return step

    def test_a_contract_diff_touching_a_sentinel_path_selects_and_runs_the_step(self):
        entry = self.entry(self.verify([self.drift_step("nothing")], ["src/Api/X.cs"]), "generated-drift")
        self.assertIsNotNone(entry, "the step is in the record")
        self.assertIs(entry.get("applicable"), True, "sentinel:rest expands to src/Api/*.cs, which X.cs matches")
        self.assertIs(entry.get("ran"), True, "so the landing runs it")
        self.assertEqual(entry.get("reading"), "ok", "a regenerator that changes nothing reads ok")

    def test_a_diff_touching_only_the_readme_leaves_the_step_unselected(self):
        entry = self.entry(self.verify([self.drift_step("nothing")], ["README.md"]), "generated-drift")
        self.assertIsNotNone(entry, "the step is listed even when it does not apply")
        self.assertIs(entry.get("applicable"), False, "README.md matches no sentinel path")
        self.assertIs(entry.get("ran"), False, "and it did not run")

    def test_a_regenerator_that_changes_a_tracked_file_reads_regression(self):
        entry = self.entry(self.verify([self.drift_step("change")], ["src/Api/X.cs"]), "generated-drift")
        self.assertIsNotNone(entry, "the step is in the record")
        self.assertEqual(entry.get("reading"), "regression",
                         "the regenerator changed a tracked file, so the committed output was stale")

    def test_the_merge_diff_alone_also_selects_the_step(self):
        entry = self.entry(self.verify([self.drift_step("nothing")], ["README.md"], merge_diff=["src/Api/Y.cs"]),
                           "generated-drift")
        self.assertIs((entry or {}).get("applicable"), True, "applicability reads the contract diff UNION the merge diff")

    def test_positive_control_the_stand_in_itself_reads_regression_when_it_changes_a_tracked_file(self):
        """Proves the fixture: with literal when_paths the stand-in runs today and its change is seen."""
        step = self.drift_step("change")
        step["id"], step["when_paths"] = "lit-drift", ["src/**"]
        changed = self.entry(self.verify([step], ["src/Api/X.cs"]), "lit-drift")
        self.assertEqual((changed or {}).get("reading"), "regression", "a changed tracked file exits 1")

    def test_positive_control_a_step_with_literal_when_paths_selects_as_today(self):
        entry = self.entry(self.verify([_ok_step("lit", ["src/**"])], ["src/Api/X.cs"]), "lit")
        self.assertIsNotNone(entry, "the literal step is in the record")
        self.assertEqual(entry.get("reading"), "ok", "a literal when_paths step still runs on a matching diff")


# ===========================================================================
# I10: P12 halts unverifiable when the children read fails
# ===========================================================================
class ChildrenReadFailsAtP12Stage(tlc.Stage):
    """read_children answers the first read (P4) and returns None for every later one (P12)."""

    CLOSED = tlc.children([(401, "CLOSED"), (402, "CLOSED")])

    @property
    def children(self):
        return self.CLOSED if len(self.args_seen.get("read_children", [])) <= 1 else None

    @children.setter
    def children(self, value):
        pass


class TestStageP12ChildrenReadFails(tlc.StageCase):

    def test_positive_control_an_unreadable_children_list_at_p12_halts_unverifiable(self):
        """Passes today by design: it pins the I10 row (unverifiable is a P12 halt)."""
        kit = tlc.Kit(Path(self._tmp.name), parent_files=self.src_change())
        st = ChildrenReadFailsAtP12Stage(self, kit)
        report = st.run()
        self.assertOutcome(report, "unverifiable", "P12 cannot re-verify the children")
        self.assertEqual(report["gate"], "P12", "the halt is the P12 re-check")
        self.assertEqual(st.count("gh_pr_merge"), 0, "nothing is merged")


# ===========================================================================
# This project's real conventions: ONE class, skipped when the block is absent
# ===========================================================================
def _real_landing_block():
    path = REPO_ROOT / ".claude" / "work-item-conventions.json"
    try:
        return (json.loads(path.read_text(encoding="utf-8")) or {}).get("contractLanding")
    except (OSError, ValueError):
        return None


class RealProjectConfigTests(VerCase):

    def setUp(self):
        self.block = _real_landing_block()
        if not self.block:
            self.skipTest(NO_CONFIG_REASON)

    def steps(self):
        return list((self.block.get("verification") or {}).get("steps") or [])

    def test_generated_drift_is_the_last_step_and_lists_the_three_sentinel_keys(self):
        steps = self.steps()
        self.assertTrue(steps, "the block configures verification steps")
        last = steps[-1]
        self.assertEqual(last.get("id"), "generated-drift", "generated-drift runs last")
        self.assertEqual(last.get("when_paths"), ["sentinel:rest", "sentinel:hub", "sentinel:graphql"],
                         "it is selected by the rest, hub and graphql sentinel lists")

    def test_the_python_scripts_command_prints_per_test_lines_and_a_per_file_line_only_for_a_crash(self):
        step = next((s for s in self.steps() if s.get("id") == "python-scripts"), None)
        self.assertIsNotNone(step, "python-scripts is configured")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            write_files(folder, {
                "test_good.py": "import unittest\nclass TestGood(unittest.TestCase):\n"
                                "    def test_a(self):\n        pass\n"
                                "if __name__ == '__main__':\n    unittest.main()\n",
                "test_bad.py": "import unittest\nclass TestBad(unittest.TestCase):\n"
                               "    def test_b(self):\n        self.fail('boom')\n"
                               "if __name__ == '__main__':\n    unittest.main()\n",
                "test_crash.py": "import module_that_does_not_exist\n"})
            command = [c.replace("{results_dir}", tmp) for c in step["command"]]
            command[-2:] = [str(folder), "scripts"]      # the folder and label arguments
            proc = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=300)
        out = proc.stdout + "\n" + proc.stderr
        self.assertRegex(out, r"test_a \(test_good\.TestGood(\.test_a)?\) \.\.\. ok",
                         "the passing file prints its own per-test line")
        self.assertRegex(out, r"test_b \(test_bad\.TestBad(\.test_b)?\) \.\.\. FAIL",
                         "the failing file prints its own per-test line")
        self.assertNotIn("test_good (scripts.test_good.test_good)", out,
                         "no synthetic per-file line for a file that ran a test")
        self.assertNotIn("test_bad (scripts.test_bad.test_bad)", out,
                         "no synthetic per-file line for a file that ran a test")
        self.assertIn("test_crash (scripts.test_crash.test_crash) ... FAIL", out,
                      "the per-file line appears for the file that crashed on import")


# ===========================================================================
# Failure attribution (contract 2026-10-31-plugin-owns-hook-mechanism-tests, block 3)
# ===========================================================================
def _step(step_id, command, fmt="exit-code", when_paths=None, suite=None):
    step = {"id": step_id, "suite": suite or step_id, "command": list(command),
            "results": {"format": fmt}, "timeout_minutes": 1, "environment_signatures": []}
    if when_paths is not None:
        step["when_paths"] = when_paths
    return step


def _regression(step_id, new_failures=()):
    return {"id": step_id, "suite": step_id, "reading": "regression", "new_failures": list(new_failures)}


class AttributionCase(VerCase):

    def sides(self, contract=(), default=(), landing=()):
        return self.fn("AttributionSides")(list(contract), list(default), list(landing))

    def attribute(self, unit, step, **sides):
        return self.fn("attribute_failure")(unit, step, self.sides(**sides), None)

    @staticmethod
    def step_unit(step_id):
        return {"unit": "step %s" % step_id, "unit_kind": "step", "step_id": step_id}

    @staticmethod
    def named_unit(failure_id, step_id):
        return {"unit": failure_id, "unit_kind": "test", "step_id": step_id}


FILE_STEP = _step("check", ["py", "-3", "scripts/check_x.py"])
INLINE_STEP = _step("inline", ["py", "-3", "-c", "import sys; sys.exit(1)"])
UT_STEP = _step("ut", ["py", "-3", "run_unit.py"], fmt="unittest-text", suite="scripts")
UT_ID = "scripts::tests.test_mod.TestA::test_x"
UT_FILE = "tests/test_mod.py"


class TestFailureUnits(AttributionCase):

    def test_a_named_failure_is_one_test_unit_each(self):
        units = self.fn("failure_units")([_regression("ut", [UT_ID, "scripts::tests.test_mod.TestA::test_y"])])
        self.assertEqual([(u["unit"], u["unit_kind"], u["step_id"]) for u in units],
                         [(UT_ID, "test", "ut"), ("scripts::tests.test_mod.TestA::test_y", "test", "ut")])

    def test_a_regression_with_no_named_failures_is_exactly_one_step_unit(self):
        units = self.fn("failure_units")([_regression("check")])
        self.assertEqual([(u["unit"], u["unit_kind"]) for u in units], [("step check", "step")])

    def test_control_a_reading_that_is_not_a_regression_yields_nothing(self):
        readings = [{"id": "a", "reading": "ok", "new_failures": []},
                    {"id": "b", "reading": "environment", "new_failures": []}]
        self.assertEqual(self.fn("failure_units")(readings), [])


class TestAttributionRules(AttributionCase):

    def test_fa1_a_named_file_the_landing_itself_changes_is_undetermined(self):
        got = self.attribute(self.step_unit("check"), FILE_STEP, contract=["scripts/check_x.py"],
                             landing=["scripts/check_x.py"])
        self.assertEqual(got["attribution"], "undetermined")
        self.assertIn("the landing itself changes scripts/check_x.py", got["reason"])

    def test_fa1_control_without_the_landing_term_the_same_file_is_in_diff(self):
        got = self.attribute(self.step_unit("check"), FILE_STEP, contract=["scripts/check_x.py"])
        self.assertEqual(got["attribution"], "in-diff")

    def test_fa1_a_file_changed_only_by_the_version_raise_commit_is_undetermined(self):
        step = _step("v", ["py", "-3", "plugin.json"])
        got = self.attribute(self.step_unit("v"), step, default=["plugin.json"], landing=["plugin.json"])
        self.assertEqual(got["attribution"], "undetermined")

    def test_fa1_a_version_file_when_p7b_committed_nothing_is_undetermined(self):
        # the landing side still holds every MANIFESTS path, whether or not this run committed one
        step = _step("v", ["py", "-3", ".claude-plugin/plugin.json"])
        got = self.attribute(self.step_unit("v"), step, contract=[".claude-plugin/plugin.json"],
                             landing=list(self.mod().MANIFESTS))
        self.assertEqual(got["attribution"], "undetermined")

    def test_fa2_a_file_in_both_diffs_is_undetermined(self):
        got = self.attribute(self.step_unit("check"), FILE_STEP, contract=["scripts/check_x.py"],
                             default=["scripts/check_x.py"])
        self.assertEqual(got["attribution"], "undetermined")
        self.assertIn("both the contract's diff and the default branch's diff", got["reason"])
        self.assertIn("scripts/check_x.py", got["reason"])

    def test_fa2_different_named_files_in_each_diff_are_undetermined(self):
        step = _step("two", ["py", "-3", "a/one.py", "b/two.py"])
        got = self.attribute(self.step_unit("two"), step, contract=["a/one.py"], default=["b/two.py"])
        self.assertEqual(got["attribution"], "undetermined")
        self.assertIn("both the contract's diff and the default branch's diff", got["reason"])

    def test_fa3_a_named_file_only_in_the_contract_diff_is_in_diff(self):
        got = self.attribute(self.step_unit("check"), FILE_STEP, contract=["scripts/check_x.py"],
                             default=["other.txt"])
        self.assertEqual(got["attribution"], "in-diff")
        self.assertIn("only the contract's diff changes scripts/check_x.py", got["reason"])

    def test_fa4_a_named_file_only_in_the_default_branch_diff_is_outside_diff(self):
        got = self.attribute(self.step_unit("check"), FILE_STEP, contract=["other.txt"],
                             default=["scripts/check_x.py"])
        self.assertEqual(got["attribution"], "outside-diff")
        self.assertIn("only the default branch's diff changes scripts/check_x.py", got["reason"])

    def test_fa5_a_step_naming_no_file_is_undetermined_with_that_reason(self):
        got = self.attribute(self.step_unit("inline"), INLINE_STEP, contract=["src/a.py"], default=["b.py"])
        self.assertEqual(got["attribution"], "undetermined")
        self.assertIn("the step names no file, so a failure cannot be traced to a diff", got["reason"])

    def test_fa5_a_when_paths_match_never_decides_a_side(self):
        step = _step("inline", ["py", "-3", "-c", "pass"], when_paths=["src/**"])
        got = self.attribute(self.step_unit("inline"), step, contract=["src/a.py"])
        self.assertEqual(got["attribution"], "undetermined", "a path match shows why the step ran, not what failed")

    def test_fa5_a_file_naming_step_with_a_when_paths_match_gives_the_when_paths_reason(self):
        step = _step("check", ["py", "-3", "scripts/check_x.py"], when_paths=["src/**"])
        got = self.attribute(self.step_unit("check"), step, contract=["src/a.py"], default=["src/b.py"])
        self.assertEqual(got["attribution"], "undetermined")
        self.assertIn("when_paths match the contract's diff and the default branch's diff", got["reason"])
        self.assertIn("which shows only why the step ran, not what failed", got["reason"])

    def test_fa5_otherwise_no_file_the_failure_names_is_in_either_diff(self):
        got = self.attribute(self.step_unit("check"), FILE_STEP, contract=["src/a.py"], default=["b.py"])
        self.assertEqual(got["attribution"], "undetermined")
        self.assertIn("no file the failure names is in either diff", got["reason"])

    def test_fa5_control_a_when_paths_that_matches_nothing_gives_the_last_reason(self):
        step = _step("check", ["py", "-3", "scripts/check_x.py"], when_paths=["docs/**"])
        got = self.attribute(self.step_unit("check"), step, contract=["src/a.py"])
        self.assertIn("no file the failure names is in either diff", got["reason"])

    def test_a_backslash_argument_equals_the_diff_path(self):
        step = _step("check", ["py", "-3", "scripts\\check_x.py"])
        got = self.attribute(self.step_unit("check"), step, default=["scripts/check_x.py"])
        self.assertEqual(got["attribution"], "outside-diff")

    def test_an_option_argument_never_names_a_file(self):
        step = _step("opt", ["py", "-3", "--settings", "-x.py"])
        got = self.attribute(self.step_unit("opt"), step, default=["-x.py"])
        self.assertEqual(got["attribution"], "undetermined")

    def test_the_file_a_unittest_unit_names_is_its_module_path_suffix(self):
        got = self.attribute(self.named_unit(UT_ID, "ut"), UT_STEP, default=["pkg/" + UT_FILE])
        self.assertEqual(got["attribution"], "outside-diff", "whole-segment suffix, unique match")
        self.assertEqual(got["unit_kind"], "test")

    def test_a_unittest_module_matching_two_diff_paths_names_no_file(self):
        got = self.attribute(self.named_unit(UT_ID, "ut"), UT_STEP, contract=["a/" + UT_FILE],
                             default=["b/" + UT_FILE])
        self.assertEqual(got["attribution"], "undetermined")
        self.assertIn("no file the failure names", got["reason"])

    def test_a_partial_segment_is_not_a_suffix_match(self):
        got = self.attribute(self.named_unit(UT_ID, "ut"), UT_STEP, default=["xtests/test_mod.py"])
        self.assertEqual(got["attribution"], "undetermined")

    def test_a_main_module_names_no_file(self):
        unit = self.named_unit("scripts::__main__.TestA::test_x", "ut")
        got = self.attribute(unit, UT_STEP, default=["__main__.py"])
        self.assertEqual(got["attribution"], "undetermined")

    def test_a_vitest_unit_names_its_path(self):
        step = _step("ui", ["npx", "vitest"], fmt="vitest-json", suite="ui")
        unit = self.named_unit("ui::src/app/a.spec.ts::does x", "ui")
        self.assertEqual(self.attribute(unit, step, contract=["src/app/a.spec.ts"])["attribution"], "in-diff")
        self.assertEqual(self.attribute(unit, step, default=["src/app/a.spec.ts"])["attribution"], "outside-diff")

    def test_a_trx_unit_names_no_file(self):
        step = _step("dn", ["dotnet", "test"], fmt="trx", suite="dn")
        unit = self.named_unit("dn::Ns.Cls::T", "dn")
        got = self.attribute(unit, step, contract=["Ns/Cls.cs"], default=["Ns.Cls.cs"])
        self.assertEqual(got["attribution"], "undetermined")


class TestAttributionOnThisRepositorysSteps(AttributionCase):
    """Every expectation is derived from the loaded steps: no step id and no count is written here."""

    def setUp(self):
        block = _real_landing_block()
        if not block:
            self.skipTest(NO_CONFIG_REASON)
        self.steps = list((block.get("verification") or {}).get("steps") or [])
        self.assertTrue(self.steps, "the block configures verification steps")

    @staticmethod
    def named_file(step):
        """The independent reading of the rule: a non-option argument (not inline code) that is a file here."""
        args = list(step["command"])[1:]
        found, skip = [], False
        for arg in args:
            if skip:
                skip = False
                continue
            if arg == "-c":
                skip = True
                continue
            if not arg.startswith("-") and (REPO_ROOT / arg.replace("\\", "/")).is_file():
                found.append(arg.replace("\\", "/"))
        return found[0] if found else None

    def build(self, **sides):
        readings = [_regression(s["id"]) for s in self.steps]
        return self.fn("build_attribution")(readings, self.steps, self.sides(**sides), [], None)

    def test_every_step_gets_one_entry_with_a_reason_and_the_note_is_written(self):
        attributed, note = self.build(contract=["unrelated/none.txt"])
        self.assertEqual([a["unit"] for a in attributed], ["step %s" % s["id"] for s in self.steps])
        for entry in attributed:
            self.assertTrue(entry["reason"], "a non-empty reason for %s" % entry["unit"])
        self.assertTrue(note, "no entry is in-diff or outside-diff, so the note is written")

    def test_a_step_that_names_a_file_is_in_diff_or_outside_diff_by_where_the_file_changed(self):
        naming = [s for s in self.steps if self.named_file(s)]
        self.assertTrue(naming, "at least one step names a file, so the test cannot pass vacuously")
        for step in naming:
            file = self.named_file(step)
            for side, expected in (("contract", "in-diff"), ("default", "outside-diff")):
                with self.subTest(step=step["id"], side=side):
                    readings = [_regression(step["id"])]
                    attributed, _ = self.fn("build_attribution")(
                        readings, [step], self.sides(**{side: [file]}), [], None)
                    self.assertEqual(attributed[0]["attribution"], expected)

    def test_a_step_naming_no_file_stays_undetermined_with_the_names_no_file_reason(self):
        silent = [s for s in self.steps if not self.named_file(s)]
        self.assertTrue(silent, "at least one step names no file, so the test cannot pass vacuously")
        for step in silent:
            with self.subTest(step=step["id"]):
                attributed, _ = self.fn("build_attribution")(
                    [_regression(step["id"])], [step],
                    self.sides(contract=["a/x.py"], default=["a/x.py"]), [], None)
                self.assertEqual(attributed[0]["attribution"], "undetermined")
                self.assertIn("names no file", attributed[0]["reason"])


class TestIssue148Case(AttributionCase):
    README_STEP = _step("hook-registration-check", [
        "py", "-3", "-B", ".claude/scripts/check_hook_registrations.py",
        "--settings", ".claude/settings.json",
        "--hook-registration-profile", ".claude/hook-registration-profile.json"])

    def test_the_default_branch_changing_settings_reads_outside_diff_and_steers_to_the_default_branch(self):
        sides = self.sides(contract=["src/a.py"], default=[".claude/settings.json"])
        attributed, _ = self.fn("build_attribution")([_regression("hook-registration-check")],
                                                     [self.README_STEP], sides, [], None)
        self.assertEqual(attributed[0]["attribution"], "outside-diff")
        facts = self.fn("advice_facts")([], attributed)
        self.assertEqual(facts, {"all_outside_diff": False, "step_failures_only": True})

    def test_control_the_contract_changing_settings_reads_in_diff(self):
        sides = self.sides(contract=[".claude/settings.json"])
        attributed, _ = self.fn("build_attribution")([_regression("hook-registration-check")],
                                                     [self.README_STEP], sides, [], None)
        self.assertEqual(attributed[0]["attribution"], "in-diff")


class TestAdviceFacts(AttributionCase):

    @staticmethod
    def entry(kind, attribution):
        return {"unit": "u", "unit_kind": kind, "attribution": attribution, "reason": "r"}

    def facts(self, reasons, *entries):
        return self.fn("advice_facts")(list(reasons), list(entries))

    def test_every_unit_outside_diff_with_a_test_unit_is_all_outside_diff(self):
        got = self.facts([], self.entry("test", "outside-diff"), self.entry("step", "outside-diff"))
        self.assertEqual(got, {"all_outside_diff": True, "step_failures_only": False})

    def test_control_one_in_diff_unit_clears_it(self):
        got = self.facts([], self.entry("test", "outside-diff"), self.entry("test", "in-diff"))
        self.assertEqual(got, {"all_outside_diff": False, "step_failures_only": False})

    def test_steps_only_is_step_failures_only_whatever_the_attribution(self):
        got = self.facts([], self.entry("step", "in-diff"), self.entry("step", "outside-diff"))
        self.assertEqual(got, {"all_outside_diff": False, "step_failures_only": True})

    def test_outside_diff_steps_without_a_test_unit_are_not_all_outside_diff(self):
        got = self.facts([], self.entry("step", "outside-diff"))
        self.assertFalse(got["all_outside_diff"])

    def test_reasons_or_no_unit_make_both_false_never_vacuously_true(self):
        none = {"all_outside_diff": False, "step_failures_only": False}
        self.assertEqual(self.facts(["forbidden paths"], self.entry("test", "outside-diff")), none)
        self.assertEqual(self.facts([]), none)


class TestEmptyListAndRecord(RepoCase):
    """The Verification Record keys, through _p8_verify in a temporary repository."""

    def call(self, steps, contract_diff, forbidden=(), **kw):
        config = {"verification": {"steps": steps}, "emulators": [], "reviewCoverage": [],
                  "forbiddenPaths": list(forbidden)}
        return self.fn("_p8_verify")(self.repo, self.head, config, {}, "absent", None, list(contract_diff),
                                     kw.pop("merge_diff", []), [], {}, [], self.logs, self.contract_dir,
                                     "run-1", "origin/master", **kw)

    FAIL_ARGV = [sys.executable, "-c", "import sys; sys.exit(1)"]

    def test_a_not_ready_from_reasons_only_has_an_empty_list_and_the_no_step_regressed_note(self):
        got = self.call([_ok_step("always")], ["secrets/key.pem"], forbidden=["secrets/*"])
        self.assertEqual(got["verdict"], "NOT-READY")
        self.assertEqual(got["new_failures_attributed"], [])
        self.assertIn("no step regressed, so there is nothing to attribute; the verdict comes from:",
                      got["attribution_note"])
        self.assertIn("forbidden paths in the contract diff", got["attribution_note"])
        self.assertEqual(self.fn("advice_facts")(got["reasons"], got["new_failures_attributed"]),
                         {"all_outside_diff": False, "step_failures_only": False})

    def test_a_ready_verdict_has_an_empty_list_and_no_note(self):
        got = self.call([_ok_step("always")], ["README.md"])
        self.assertEqual(got["verdict"], "READY")
        self.assertEqual(got["new_failures_attributed"], [])
        self.assertNotIn("attribution_note", got)

    def test_a_failing_step_is_one_step_unit_attributed_from_the_three_sides(self):
        step = {"id": "check", "suite": "check", "command": self.FAIL_ARGV + ["scripts/check_x.py"],
                "results": {"format": "exit-code"}, "timeout_minutes": 1, "environment_signatures": []}
        got = self.call([step], ["src/a.py"], merge_diff=["scripts/check_x.py"],
                        default_branch_diff=["scripts/check_x.py"], landing_paths=[])
        self.assertEqual(got["verdict"], "NOT-READY")
        self.assertEqual([(a["unit"], a["unit_kind"], a["attribution"]) for a in got["new_failures_attributed"]],
                         [("step check", "step", "outside-diff")])
        self.assertNotIn("attribution_note", got, "an outside-diff entry exists and there are no reasons")

    def test_no_decided_entry_writes_the_note_with_the_distinct_reasons(self):
        step = {"id": "inline", "suite": "inline", "command": self.FAIL_ARGV,
                "results": {"format": "exit-code"}, "timeout_minutes": 1, "environment_signatures": []}
        got = self.call([step], ["src/a.py"])
        self.assertEqual(got["new_failures_attributed"][0]["attribution"], "undetermined")
        self.assertIn("the step names no file", got["attribution_note"])

    def test_the_defaults_keep_existing_callers_working(self):
        got = self.verify([_ok_step("always")], ["README.md"])
        self.assertEqual(got["new_failures_attributed"], [])


if __name__ == "__main__":
    unittest.main()
