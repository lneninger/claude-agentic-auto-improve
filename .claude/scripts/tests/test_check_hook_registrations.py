"""Tests for check_hook_registrations.py (the Hook registration check).

Run: py -3 .claude/scripts/tests/test_check_hook_registrations.py

The five classes named after the consuming project's tests are their plugin-owned equivalents:
HookGatingTests.test_hook_gating (HR-3), RegistrationRowsUnchangedTests (HR-2 and HR-1),
ProfileSetupTests.test_profile_setup, RegistrationCoverageTests (HR-4 on the shipped hooks.json).
"""
import contextlib
import copy
import hashlib
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

HERE = Path(__file__).resolve().parent
SCRIPTS_DIR = HERE.parent
REPO_ROOT = SCRIPTS_DIR.parent.parent
FIXTURES = HERE / "fixtures" / "hook-registrations"
CHECKER = SCRIPTS_DIR / "check_hook_registrations.py"
FIVE_FILES = (
    "check_hook_registrations.py",
    "auto_improve_finish_install.py",
    "pr_merged.py",
    "plugin_doctor.py",
    "check_version_bump.py",
)

sys.path.insert(0, str(SCRIPTS_DIR))
import check_hook_registrations as chk  # noqa: E402

# A checkout may give a text fixture CRLF line endings (core.autocrlf); the recorder always writes LF.
SETTINGS_BYTES = (FIXTURES / "settings.json").read_bytes().replace(b"\r\n", b"\n")
PROFILE_BYTES = (FIXTURES / "hook-registration-profile.json").read_bytes().replace(b"\r\n", b"\n")

RULES = (
    "row-count-unchanged",
    "rows-unchanged-apart-from-if",
    "if-keys-unchanged",
    "every-registration-profiled-or-excluded",
    "every-exclusion-matches-a-row",
)
R1, R2, R3, R4, R5 = RULES

EDIT_GATE = "PreToolUse|edit-gate.py"
LAUNCH = "PreToolUse|launch.py|shared-gate.py"
SESSION = "SessionStart|session-start.py"
ECHO = "command:echo checking"
STOP_SUMMARY = "Stop|stop-summary.py"
PROMPT = 'prompt:{"prompt":"Summarise the session","type":"prompt"}'


def settings_dict():
    return json.loads(SETTINGS_BYTES.decode("utf-8"))


def profile_dict():
    return json.loads(PROFILE_BYTES.decode("utf-8"))


def as_bytes(value):
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return (json.dumps(value, indent=2) + "\n").encode("utf-8")


def run_main(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = chk.main(argv)
    return code, buf.getvalue()


def child_env():
    env = dict(os.environ)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    env.pop("PYTHONPYCACHEPREFIX", None)
    return env


def snapshot(root):
    """Every path under root with a content hash, so any written file or folder shows."""
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        out[rel] = None if p.is_dir() else hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def entry(profile, identity):
    return next(e for e in profile["registrations"] if e["identity"] == identity)


def drop_entry(profile, identity):
    profile["registrations"] = [e for e in profile["registrations"] if e["identity"] != identity]


def row_of(settings, identity_hint):
    """The handler dict of the first row whose command text contains the hint."""
    for groups in settings["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                if identity_hint in json.dumps(hook):
                    return hook
    raise KeyError(identity_hint)


class ProjectCase(unittest.TestCase):
    """A temporary project folder holding the fixture settings and Hook registration profile."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.settings_path = self.root / ".claude" / "settings.json"
        self.profile_path = self.root / ".claude" / "hook-registration-profile.json"
        self.settings_path.parent.mkdir(parents=True)

    def put(self, settings=SETTINGS_BYTES, profile=PROFILE_BYTES):
        if settings is not None:
            self.settings_path.write_bytes(as_bytes(settings))
        if profile is not None:
            self.profile_path.write_bytes(as_bytes(profile))

    def report(self, *extra):
        code, out = run_main(["--project", str(self.root), "--json", *extra])
        return code, json.loads(out)

    def text(self):
        return run_main(["--project", str(self.root)])

    @staticmethod
    def failed(report):
        return {r["rule"] for r in report["rules"] if r["status"] == "fail"}

    def assert_only_fails(self, rules, settings=SETTINGS_BYTES, profile=PROFILE_BYTES):
        self.put(settings, profile)
        code, rep = self.report()
        self.assertEqual(code, 1, rep)
        self.assertEqual(rep["status"], "fail")
        self.assertEqual(self.failed(rep), set(rules), rep)
        return rep

    def assert_refusal(self, code_name, settings=SETTINGS_BYTES, profile=PROFILE_BYTES):
        self.put(settings, profile)
        code, rep = self.report()
        self.assertEqual(code, 2, rep)
        self.assertEqual(rep["status"], "could-not-check")
        self.assertEqual(rep["refusal"]["code"], code_name, rep)
        self.assertEqual(rep["rules"], [])
        self.assertTrue(rep["refusal"]["message"])
        self.assertTrue(rep["remedy"])
        return rep


# ===========================================================================
# The fixture and the profile bytes
# ===========================================================================
class FixtureTests(unittest.TestCase):

    def test_fixture_is_generic_and_uses_the_project_dir_variable(self):
        both = (SETTINGS_BYTES + PROFILE_BYTES).decode("utf-8").lower()
        self.assertIn("${claude_project_dir}", both)
        for name in ("stocktool", "scalping", "hipalanet"):
            self.assertNotIn(name, both)

    def test_fixture_profile_is_exactly_what_the_recorder_writes(self):
        previous = chk.load_hook_registration_profile(PROFILE_BYTES)
        built = chk.build_hook_registration_profile(chk.load_settings(SETTINGS_BYTES), previous)
        self.assertEqual(chk.serialise(built), PROFILE_BYTES)

    def test_fixture_checks_clean(self):
        results = chk.check(chk.load_settings(SETTINGS_BYTES), chk.load_hook_registration_profile(PROFILE_BYTES))
        self.assertEqual([r.rule for r in results], list(RULES))
        self.assertEqual([r.status for r in results], ["pass"] * 5)


class IdentityTests(unittest.TestCase):

    def rows(self, settings=None):
        return chk.read_rows(chk.load_settings(as_bytes(settings if settings is not None else settings_dict())))

    def test_identities_of_the_fixture_rows(self):
        got = [(r.event, r.matcher, r.identity, r.occurrence) for r in self.rows()]
        self.assertEqual(got, [
            ("SessionStart", "", SESSION, 1),
            ("PreToolUse", "Edit|Write", EDIT_GATE, 1),
            ("PreToolUse", "Edit|Write", LAUNCH, 1),
            ("PreToolUse", "Bash", ECHO, 1),
            ("Stop", "", STOP_SUMMARY, 1),
            ("Stop", "", PROMPT, 1),
        ])

    def test_a_row_with_no_py_file_gets_the_command_identity(self):
        s = {"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": "echo", "args": ["a", "b"]},
            {"type": "command", "command": "run.exe /x"},
        ]}]}}
        self.assertEqual([r.identity for r in self.rows(s)], ["command:echo a b", "command:run.exe /x"])

    def test_duplicate_rows_count_their_occurrence_in_file_order(self):
        h = {"type": "command", "command": "py", "args": ["-3", "x/a.py"]}
        s = {"hooks": {"Stop": [{"hooks": [h, h]}, {"matcher": "m", "hooks": [h]}]}}
        got = [(r.matcher, r.occurrence) for r in self.rows(s)]
        self.assertEqual(got, [("", 1), ("", 2), ("m", 1)])

    def test_no_hooks_key_is_valid_and_has_zero_rows(self):
        self.assertEqual(self.rows({}), [])
        built = chk.build_hook_registration_profile(chk.load_settings(b"{}"), None)
        self.assertEqual(built["row_count"], 0)
        self.assertEqual(built["registrations"], [])
        self.assertEqual([r.status for r in chk.check(chk.load_settings(b"{}"), built)], ["pass"] * 5)


class BuildProfileTests(unittest.TestCase):

    def test_two_builds_from_the_same_input_give_identical_bytes(self):
        a = chk.serialise(chk.build_hook_registration_profile(chk.load_settings(SETTINGS_BYTES), None))
        b = chk.serialise(chk.build_hook_registration_profile(chk.load_settings(SETTINGS_BYTES), None))
        self.assertEqual(a, b)
        self.assertTrue(a)

    def test_serialisation_follows_rp2(self):
        data = chk.serialise(chk.build_hook_registration_profile(chk.load_settings(SETTINGS_BYTES), None))
        self.assertFalse(data.startswith(b"\xef\xbb\xbf"), "no byte-order mark")
        self.assertTrue(data.endswith(b"}\n") and not data.endswith(b"\n\n"), "one trailing newline")
        text = data.decode("utf-8")
        self.assertIn('\n  "format": 1,\n  "settings_path": ".claude/settings.json",\n  "row_count": ', text)
        self.assertEqual(list(json.loads(text)),
                         ["format", "settings_path", "row_count", "registrations", "excluded"])

    def test_the_profile_holds_no_time_hash_host_or_absolute_path(self):
        text = chk.serialise(chk.build_hook_registration_profile(chk.load_settings(SETTINGS_BYTES), None)).decode()
        for needle in ("timestamp", "recorded_at", "generated", "sha256", "hostname", "C:\\", "D:\\", ":/Users", "/home/"):
            self.assertNotIn(needle, text)

    def test_entry_keys_are_in_the_documented_order(self):
        built = chk.build_hook_registration_profile(chk.load_settings(SETTINGS_BYTES), None)
        first = built["registrations"][0]
        self.assertEqual(list(first), ["event", "matcher", "identity", "occurrence", "row"])
        gated = entry(built, EDIT_GATE)
        self.assertEqual(list(gated), ["event", "matcher", "identity", "occurrence", "row", "if"])
        self.assertNotIn("if", gated["row"])
        self.assertEqual(gated["if"], "Edit(src/**)")

    def test_row_count_includes_excluded_rows_and_excluded_rows_are_not_profiled(self):
        previous = chk.load_hook_registration_profile(PROFILE_BYTES)
        built = chk.build_hook_registration_profile(chk.load_settings(SETTINGS_BYTES), previous)
        self.assertEqual(built["row_count"], 6)
        self.assertEqual(len(built["registrations"]), 5)
        self.assertNotIn(PROMPT, [e["identity"] for e in built["registrations"]])

    def test_without_exclusions_every_row_is_profiled(self):
        built = chk.build_hook_registration_profile(chk.load_settings(SETTINGS_BYTES), None)
        self.assertEqual(len(built["registrations"]), 6)
        self.assertEqual(built["excluded"], [])


# ===========================================================================
# load_settings: the one Settings shape validator
# ===========================================================================
SHAPE_CASES = [
    ("hooks is a list", {"hooks": []}, "$.hooks"),
    ("hooks is a string", {"hooks": "x"}, "$.hooks"),
    ("event value is not a list", {"hooks": {"Stop": {}}}, "$.hooks.Stop"),
    ("group is not an object", {"hooks": {"Stop": ["x"]}}, "$.hooks.Stop[0]"),
    ("matcher is not a string", {"hooks": {"Stop": [{"matcher": 1, "hooks": []}]}}, "$.hooks.Stop[0].matcher"),
    ("group hooks key absent", {"hooks": {"Stop": [{"matcher": "x"}]}}, "$.hooks.Stop[0].hooks"),
    ("group hooks is not a list", {"hooks": {"Stop": [{"hooks": {}}]}}, "$.hooks.Stop[0].hooks"),
    ("handler is not an object", {"hooks": {"Stop": [{"hooks": ["x"]}]}}, "$.hooks.Stop[0].hooks[0]"),
    ("handler has no type", {"hooks": {"Stop": [{"hooks": [{}]}]}}, "$.hooks.Stop[0].hooks[0].type"),
    ("handler type is not a string", {"hooks": {"Stop": [{"hooks": [{"type": 3}]}]}},
     "$.hooks.Stop[0].hooks[0].type"),
    ("command handler has no command", {"hooks": {"Stop": [{"hooks": [{"type": "command"}]}]}},
     "$.hooks.Stop[0].hooks[0].command"),
    ("command is not a string", {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": 5}]}]}},
     "$.hooks.Stop[0].hooks[0].command"),
    ("args is not a list",
     {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "py", "args": "x"}]}]}},
     "$.hooks.Stop[0].hooks[0].args"),
    ("an arg is not a string",
     {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "py", "args": ["a", 1]}]}]}},
     "$.hooks.Stop[0].hooks[0].args[1]"),
]


class LoadSettingsTests(unittest.TestCase):

    def assert_error(self, data, kind, path=None):
        with self.assertRaises(chk.SettingsError) as ctx:
            chk.load_settings(data)
        self.assertEqual(ctx.exception.kind, kind)
        if path is not None:
            self.assertEqual(ctx.exception.path, path)
        return ctx.exception

    def test_the_fixture_loads(self):
        self.assertEqual(chk.load_settings(SETTINGS_BYTES), settings_dict())

    def test_a_byte_order_mark_is_accepted(self):
        self.assertEqual(chk.load_settings(b"\xef\xbb\xbf" + SETTINGS_BYTES), settings_dict())

    def test_utf16_is_an_encoding_error(self):
        self.assert_error(SETTINGS_BYTES.decode("utf-8").encode("utf-16"), "encoding")

    def test_invalid_json_is_a_json_error(self):
        self.assert_error(b'{"hooks": ', "json")

    def test_a_duplicate_key_at_the_top_level(self):
        self.assert_error(b'{"hooks": {}, "hooks": {}}', "duplicate-key", "$")

    def test_a_duplicate_key_at_handler_level(self):
        data = (b'{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "a", "command": "b"}]}]}}')
        self.assert_error(data, "duplicate-key", "$.hooks.Stop[0].hooks[0]")

    def test_a_document_that_is_not_an_object(self):
        for text in (b"[]", b'"x"', b"3", b"null"):
            self.assert_error(text, "not-object", "$")

    def test_each_malformed_level_is_a_shape_error_with_its_path(self):
        for label, settings, path in SHAPE_CASES:
            with self.subTest(label):
                self.assert_error(as_bytes(settings), "shape", path)

    def test_group_keys_other_than_matcher_and_hooks_are_not_judged(self):
        s = {"hooks": {"Stop": [{"hooks": [], "note": 5, "x": [1]}]}, "other": {"a": 1}}
        self.assertEqual(chk.load_settings(as_bytes(s)), s)

    def test_a_non_command_handler_needs_only_a_string_type(self):
        s = {"hooks": {"Stop": [{"hooks": [{"type": "prompt", "command": 5}]}]}}
        self.assertEqual(chk.load_settings(as_bytes(s)), s)


# ===========================================================================
# The five equivalents of the consuming project's tests
# ===========================================================================
class HookGatingTests(ProjectCase):

    def test_hook_gating(self):
        # HR-3: an if value changed, added or removed is the only finding.
        changed = settings_dict()
        row_of(changed, "edit-gate.py")["if"] = "Edit(**)"
        rep = self.assert_only_fails([R3], changed)
        finding = next(r for r in rep["rules"] if r["rule"] == R3)["findings"][0]
        self.assertIn(EDIT_GATE, json.dumps(finding))

        added = settings_dict()
        row_of(added, "session-start.py")["if"] = "Bash(*)"
        self.assert_only_fails([R3], added)

        removed = settings_dict()
        del row_of(removed, "edit-gate.py")["if"]
        self.assert_only_fails([R3], removed)

    def test_an_if_value_equal_on_both_sides_passes(self):
        self.put()
        code, rep = self.report()
        self.assertEqual((code, self.failed(rep)), (0, set()))


class RegistrationRowsUnchangedTests(ProjectCase):

    def test_hooks_block_equals_base_apart_from_if_keys(self):
        # HR-2: a content change other than `if` is the only finding; a change to `if` alone is not.
        s = settings_dict()
        row_of(s, "shared-gate.py")["timeout"] = 99
        rep = self.assert_only_fails([R2], s)
        text = json.dumps(next(r for r in rep["rules"] if r["rule"] == R2)["findings"])
        self.assertIn(LAUNCH, text)
        self.assertIn("timeout", text)

        only_if = settings_dict()
        row_of(only_if, "edit-gate.py")["if"] = "other"
        self.put(only_if)
        _code, rep2 = self.report()
        self.assertNotIn(R2, self.failed(rep2))

    def test_a_path_prefix_change_shows_as_a_content_change(self):
        s = settings_dict()
        row_of(s, "session-start.py")["args"] = ["-3", "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/session-start.py"]
        rep = self.assert_only_fails([R2], s)
        self.assertIn("args", json.dumps(next(r for r in rep["rules"] if r["rule"] == R2)["findings"]))

    def test_a_missing_row_is_reported_missing(self):
        s = settings_dict()
        s["hooks"]["SessionStart"][0]["hooks"][0]["args"] = ["-3", "x/renamed.py"]
        self.put(s)
        code, rep = self.report()
        self.assertEqual(code, 1)
        self.assertIn(R2, self.failed(rep))
        self.assertIn("missing", json.dumps(next(r for r in rep["rules"] if r["rule"] == R2)["findings"]))
        self.assertIn(R4, self.failed(rep), "the renamed row is unprofiled")

    def test_row_count_is_unchanged(self):
        # HR-1: the finding names both numbers.
        p = profile_dict()
        p["row_count"] = 9
        rep = self.assert_only_fails([R1], profile=p)
        text = json.dumps(next(r for r in rep["rules"] if r["rule"] == R1)["findings"])
        self.assertIn("9", text)
        self.assertIn("6", text)

    def test_row_count_counts_excluded_rows(self):
        # Removing the excluded row from the settings breaks HR-1 (and HR-5: the exclusion goes stale).
        s = settings_dict()
        s["hooks"]["Stop"][0]["hooks"].pop()
        self.put(s)
        code, rep = self.report()
        self.assertEqual(code, 1)
        self.assertEqual(self.failed(rep), {R1, R5})


class ProfileSetupTests(ProjectCase):

    def test_profile_setup(self):
        # Record, round-trip, check clean.
        settings = chk.load_settings(SETTINGS_BYTES)
        recorded = chk.serialise(chk.build_hook_registration_profile(settings, None))
        self.put(profile=recorded)
        code, rep = self.report()
        self.assertEqual((code, self.failed(rep)), (0, set()), rep)
        self.assertEqual(chk.serialise(chk.load_hook_registration_profile(recorded)), recorded)

        # A re-record keeps every Exclusion verbatim, a stale one included, and an unchanged
        # re-record produces identical bytes.
        previous = chk.load_hook_registration_profile(PROFILE_BYTES)
        previous["excluded"].append({"event": "Stop", "identity": "Stop|gone.py", "reason": "removed upstream"})
        again = chk.build_hook_registration_profile(settings, previous)
        self.assertEqual(again["excluded"], previous["excluded"])
        self.assertEqual(chk.serialise(chk.build_hook_registration_profile(settings, again)),
                         chk.serialise(again))
        stale = chk.serialise(again)
        self.put(profile=stale)
        code, rep = self.report()
        self.assertEqual(code, 1)
        self.assertEqual(self.failed(rep), {R5}, "the stale Exclusion is the only finding")
        self.assertIn("remove it from the hook registration profile", json.dumps(rep))

    def test_a_re_record_after_a_settings_change_profiles_the_new_row(self):
        s = settings_dict()
        s["hooks"]["Stop"][0]["hooks"].append({"type": "command", "command": "py", "args": ["-3", "x/new.py"]})
        previous = chk.load_hook_registration_profile(PROFILE_BYTES)
        built = chk.build_hook_registration_profile(chk.load_settings(as_bytes(s)), previous)
        self.assertEqual(built["row_count"], 7)
        self.assertIn("Stop|new.py", [e["identity"] for e in built["registrations"]])
        self.assertEqual(built["excluded"], previous["excluded"])


class RegistrationCoverageTests(unittest.TestCase):

    def test_real_settings_every_registration_is_profiled_or_excluded(self):
        hooks_json = (REPO_ROOT / ".claude" / "hooks" / "hooks.json").read_bytes()
        settings = chk.load_settings(hooks_json)
        self.assertTrue(chk.read_rows(settings), "the shipped hooks.json registers hooks")
        profile = chk.build_hook_registration_profile(settings, None)
        self.assertEqual([r.status for r in chk.check(settings, profile)], ["pass"] * 5)

        extra = copy.deepcopy(settings)
        extra["hooks"]["Stop"][0]["hooks"].append(
            {"type": "command", "command": "py", "args": ["-3", "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/unrecorded-new.py"]})
        results = {r.rule: r for r in chk.check(extra, profile)}
        self.assertEqual(results[R4].status, "fail")
        self.assertIn("unrecorded-new.py", json.dumps(results[R4].findings))
        self.assertEqual(results[R5].status, "pass")


# ===========================================================================
# Failure path: one rule at a time, then all five
# ===========================================================================
class RuleFailureTests(ProjectCase):

    def test_hr4_alone_an_unprofiled_row(self):
        p = profile_dict()
        drop_entry(p, SESSION)
        rep = self.assert_only_fails([R4], profile=p)
        self.assertIn(SESSION, json.dumps(next(r for r in rep["rules"] if r["rule"] == R4)["findings"]))

    def test_hr5_alone_a_stale_exclusion(self):
        p = profile_dict()
        p["excluded"].append({"event": "Stop", "identity": "Stop|gone.py", "reason": "gone"})
        rep = self.assert_only_fails([R5], profile=p)
        text = json.dumps(next(r for r in rep["rules"] if r["rule"] == R5)["findings"])
        self.assertIn("Stop|gone.py", text)
        self.assertIn("remove it from the hook registration profile", text)

    def test_hr5_a_matcher_specific_exclusion_that_matches_no_matcher_is_stale(self):
        p = profile_dict()
        p["excluded"][0]["matcher"] = "NoSuchMatcher"
        self.assert_only_fails([R4, R5], profile=p)

    def test_all_five_broken_give_five_fail_lines(self):
        s = settings_dict()
        row_of(s, "edit-gate.py")["if"] = "changed"          # HR-3
        row_of(s, "shared-gate.py")["timeout"] = 99          # HR-2
        p = profile_dict()
        p["row_count"] = 7                                   # HR-1
        drop_entry(p, ECHO)                                  # HR-4
        p["excluded"].append({"event": "Stop", "identity": "Stop|gone.py", "reason": "gone"})  # HR-5
        self.put(s, p)
        code, out = self.text()
        self.assertEqual(code, 1)
        fails = [ln for ln in out.splitlines() if ln.startswith("FAIL ")]
        self.assertEqual(len(fails), 5, out)
        for rule in RULES:
            self.assertEqual(sum(ln.startswith("FAIL " + rule + ":") for ln in fails), 1, out)
        self.assertFalse([ln for ln in out.splitlines() if ln.startswith("PASS ")])

    def test_all_rules_are_always_evaluated_in_order(self):
        s = settings_dict()
        row_of(s, "edit-gate.py")["if"] = "changed"
        self.put(s)
        _code, rep = self.report()
        self.assertEqual([r["rule"] for r in rep["rules"]], list(RULES))

    def test_one_exclusion_covering_two_duplicate_rows_passes(self):
        h = {"type": "command", "command": "py", "args": ["-3", "x/dup.py"]}
        s = {"hooks": {"Stop": [{"hooks": [h, copy.deepcopy(h)]}]}}
        p = {"format": 1, "settings_path": ".claude/settings.json", "row_count": 2,
             "registrations": [], "excluded": [{"event": "Stop", "identity": "Stop|dup.py", "reason": "twice on purpose"}]}
        self.put(s, p)
        code, rep = self.report()
        self.assertEqual((code, self.failed(rep)), (0, set()), rep)

    def test_a_matcher_less_exclusion_covers_every_matcher(self):
        h = {"type": "command", "command": "py", "args": ["-3", "x/dup.py"]}
        s = {"hooks": {"Stop": [{"matcher": "a", "hooks": [h]}, {"matcher": "b", "hooks": [h]}]}}
        p = {"format": 1, "settings_path": ".claude/settings.json", "row_count": 2,
             "registrations": [], "excluded": [{"event": "Stop", "identity": "Stop|dup.py", "reason": "all matchers"}]}
        self.put(s, p)
        code, rep = self.report()
        self.assertEqual((code, self.failed(rep)), (0, set()), rep)

    def test_an_excluded_row_is_exempt_from_hr2_hr3_and_hr4(self):
        # The excluded prompt row carries an `if` the profile never recorded: still a pass.
        s = settings_dict()
        s["hooks"]["Stop"][0]["hooks"][1]["if"] = "anything"
        self.put(s)
        code, rep = self.report()
        self.assertEqual((code, self.failed(rep)), (0, set()), rep)

    def test_a_changed_excluded_row_changes_identity_so_the_exclusion_goes_stale(self):
        s = settings_dict()
        s["hooks"]["Stop"][0]["hooks"][1]["prompt"] = "changed text"
        self.put(s)
        code, rep = self.report()
        self.assertEqual(code, 1)
        self.assertEqual(self.failed(rep), {R4, R5})


# ===========================================================================
# Could-not-check refusals
# ===========================================================================
class RefusalTests(ProjectCase):

    def test_paths_not_given(self):
        for argv in ([], ["--settings", "x.json"], ["--hook-registration-profile", "p.json"]):
            with self.subTest(argv=argv):
                code, out = run_main(argv + ["--json"])
                rep = json.loads(out)
                self.assertEqual(code, 2)
                self.assertEqual(rep["refusal"]["code"], "paths-not-given")
                self.assertEqual(rep["status"], "could-not-check")

    def test_paths_are_never_taken_from_the_working_directory_or_environment(self):
        self.put()
        old = os.getcwd()
        self.addCleanup(os.chdir, old)
        os.chdir(self.root)
        with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(self.root)}):
            code, out = run_main(["--json"])
        self.assertEqual((code, json.loads(out)["refusal"]["code"]), (2, "paths-not-given"))

    def test_settings_missing_with_the_root_set(self):
        self.put(settings=None)
        code, rep = self.report()
        self.assertEqual((code, rep["refusal"]["code"]), (2, "settings-missing"))
        self.assertTrue(rep["refusal"]["path"].endswith("settings.json"))

    def test_settings_missing_with_an_absent_root(self):
        code, out = run_main(["--project", str(self.root / "nope"), "--json"])
        self.assertEqual((code, json.loads(out)["refusal"]["code"]), (2, "settings-missing"))

    def test_settings_missing_with_explicit_paths(self):
        self.put(settings=None)
        code, out = run_main(["--settings", str(self.settings_path),
                              "--hook-registration-profile", str(self.profile_path), "--json"])
        self.assertEqual((code, json.loads(out)["refusal"]["code"]), (2, "settings-missing"))

    def test_settings_unreadable_for_every_error_kind(self):
        cases = {
            "utf16": SETTINGS_BYTES.decode().encode("utf-16"),
            "invalid json": b'{"hooks": ',
            "duplicate top-level key": b'{"hooks": {}, "hooks": {}}',
            "duplicate handler key":
                b'{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "a", "command": "b"}]}]}}',
            "not an object": b"[]",
        }
        for label, settings, _path in SHAPE_CASES:
            cases["shape: " + label] = as_bytes(settings)
        for label, data in cases.items():
            with self.subTest(label):
                rep = self.assert_refusal("settings-unreadable", settings=data)
                self.assertTrue(rep["refusal"]["path"].endswith("settings.json"))

    def test_the_shape_refusal_names_the_json_path(self):
        rep = self.assert_refusal("settings-unreadable", settings={"hooks": {"Stop": [{"hooks": [{"type": "command"}]}]}})
        self.assertIn("$.hooks.Stop[0].hooks[0].command", rep["refusal"]["message"])

    def test_a_settings_path_that_is_a_folder_is_unreadable_not_a_pass(self):
        self.put(settings=None)
        self.settings_path.mkdir()
        code, rep = self.report()
        self.assertEqual((code, rep["refusal"]["code"]), (2, "settings-unreadable"))

    def test_hook_registration_profile_missing_names_the_recorder(self):
        rep = self.assert_refusal("hook-registration-profile-missing", profile=None)
        self.assertIn("record-registrations", rep["remedy"])
        self.assertNotIn("profile-missing", rep["remedy"].replace("hook-registration-profile-missing", ""))

    def test_hook_registration_profile_unreadable_for_each_breach(self):
        dup = profile_dict()
        dup["registrations"].append(copy.deepcopy(dup["registrations"][0]))
        no_reason = profile_dict()
        del no_reason["excluded"][0]["reason"]
        blank_reason = profile_dict()
        blank_reason["excluded"][0]["reason"] = ""
        both = profile_dict()          # RP-6: a row both expected and excluded
        both["excluded"].append({"event": "SessionStart", "identity": SESSION, "reason": "also"})
        both_matcher = profile_dict()
        both_matcher["excluded"].append(
            {"event": "PreToolUse", "identity": EDIT_GATE, "matcher": "Edit|Write", "reason": "also"})
        twice = profile_dict()         # RP-7: identical exclusions
        twice["excluded"].append(copy.deepcopy(twice["excluded"][0]))
        overlap = profile_dict()       # RP-7: matcher-less beside matcher-specific
        overlap["excluded"].append(dict(overlap["excluded"][0], matcher="x"))
        overlap2 = profile_dict()
        overlap2["excluded"][0]["matcher"] = "x"
        overlap2["excluded"].append({k: v for k, v in overlap2["excluded"][0].items() if k != "matcher"})
        wrong_format = dict(profile_dict(), format=2)
        string_format = dict(profile_dict(), format="1")
        wrong_path = dict(profile_dict(), settings_path="settings.json")
        negative = dict(profile_dict(), row_count=-1)
        bool_count = dict(profile_dict(), row_count=True)
        cases = {
            "RP-4 duplicate identity": dup, "RP-5 reason absent": no_reason, "RP-5 reason empty": blank_reason,
            "RP-6 expected and excluded": both, "RP-6 with the matcher": both_matcher,
            "RP-7 identical exclusions": twice, "RP-7 matcher-less beside matcher": overlap,
            "RP-7 matcher beside matcher-less": overlap2,
            "unknown format": wrong_format, "format is a string": string_format, "wrong settings_path": wrong_path,
            "negative row_count": negative, "boolean row_count": bool_count,
            "utf-16": PROFILE_BYTES.decode().encode("utf-16"),
            "invalid json": b"{",
            "empty object": b"{}",
            "not an object": b"[]",
            "duplicate key": b'{"format": 1, "format": 1}',
        }
        for field in ("format", "settings_path", "row_count", "registrations", "excluded"):
            missing = profile_dict()
            del missing[field]
            cases["missing " + field] = missing
        for field in ("event", "matcher", "identity", "occurrence", "row"):
            broken = profile_dict()
            del broken["registrations"][0][field]
            cases["entry lacks " + field] = broken
        for field in ("event", "identity"):
            broken = profile_dict()
            del broken["excluded"][0][field]
            cases["exclusion lacks " + field] = broken
        for label, data in cases.items():
            with self.subTest(label):
                self.assert_refusal("hook-registration-profile-unreadable", profile=data)

    def test_two_exclusions_with_different_matchers_are_readable(self):
        p = profile_dict()
        p["excluded"][0]["matcher"] = ""
        p["excluded"].append(dict(p["excluded"][0], matcher="other"))
        self.put(profile=p)
        code, rep = self.report()
        self.assertEqual(code, 1, "readable: only the second exclusion is stale")
        self.assertEqual(self.failed(rep), {R5})

    def test_an_unreadable_profile_is_never_an_empty_one(self):
        self.put(profile=b"{}")
        code, rep = self.report()
        self.assertEqual(code, 2)
        self.assertEqual(rep["rules"], [])

    def test_checker_internal_error_is_one_line_exit_2(self):
        self.put()
        with mock.patch.object(chk, "check", side_effect=RuntimeError("boom")):
            code, out = run_main(["--project", str(self.root)])
        self.assertEqual(code, 2)
        self.assertIn("checker-internal-error", out)
        self.assertIn("RuntimeError", out)
        self.assertIn("boom", out)
        self.assertNotIn("Traceback", out)

    def test_dependency_import_failure_is_exit_2_naming_the_five_files(self):
        self.put()
        with mock.patch.object(chk, "_IMPORT_FAILURE", ImportError("No module named 'pr_merged'", name="pr_merged")):
            code, out = run_main(["--project", str(self.root), "--json"])
        rep = json.loads(out)
        self.assertEqual((code, rep["refusal"]["code"]), (2, "checker-dependency-missing"))
        self.assertIn("pr_merged", rep["refusal"]["message"])
        for name in FIVE_FILES:
            self.assertIn(name, rep["refusal"]["message"])

    def test_a_non_import_failure_while_importing_is_an_internal_error(self):
        self.put()
        with mock.patch.object(chk, "_IMPORT_FAILURE", SyntaxError("bad")):
            code, out = run_main(["--project", str(self.root), "--json"])
        self.assertEqual((code, json.loads(out)["refusal"]["code"]), (2, "checker-internal-error"))


# ===========================================================================
# Command line output
# ===========================================================================
class CommandLineTests(ProjectCase):

    def test_pass_prints_five_pass_lines_and_exits_0(self):
        self.put()
        code, out = self.text()
        self.assertEqual(code, 0, out)
        self.assertEqual([ln for ln in out.splitlines() if ln.startswith("PASS ")], ["PASS " + r for r in RULES])

    def test_explicit_paths_work_like_project(self):
        self.put()
        code, out = run_main(["--settings", str(self.settings_path),
                              "--hook-registration-profile", str(self.profile_path)])
        self.assertEqual(code, 0, out)

    def test_json_report_shape(self):
        self.put()
        code, rep = self.report()
        self.assertEqual(code, 0)
        self.assertEqual(rep["status"], "pass")
        self.assertEqual(Path(rep["settings"]), self.settings_path)
        self.assertEqual(Path(rep["hook_registration_profile"]), self.profile_path)
        self.assertEqual([r["rule"] for r in rep["rules"]], list(RULES))
        self.assertEqual({tuple(sorted(r)) for r in rep["rules"]}, {("findings", "rule", "status")})
        self.assertNotIn("refusal", rep)
        self.assertIsInstance(rep["remedy"], str)

    def test_a_failing_report_names_the_recorder_in_its_remedy(self):
        s = settings_dict()
        row_of(s, "edit-gate.py")["if"] = "changed"
        self.put(s)
        code, out = self.text()
        self.assertEqual(code, 1)
        self.assertIn("record-registrations", out)

    def test_finding_shape(self):
        s = settings_dict()
        row_of(s, "edit-gate.py")["if"] = "changed"
        self.put(s)
        _code, rep = self.report()
        finding = next(r for r in rep["rules"] if r["rule"] == R3)["findings"][0]
        self.assertEqual(sorted(finding), ["detail", "identity"])

    def test_the_check_writes_nothing(self):
        self.put()
        before = snapshot(self.root)
        self.report()
        self.text()
        self.assertEqual(snapshot(self.root), before)


# ===========================================================================
# Fresh-process behaviour: dependencies and bytecode
# ===========================================================================
class ProcessTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def stage(self, files, name="proj"):
        proj = self.tmp / name
        scripts = proj / ".claude" / "scripts"
        scripts.mkdir(parents=True)
        for f in files:
            shutil.copy2(SCRIPTS_DIR / f, scripts / f)
        (proj / ".claude" / "settings.json").write_bytes(SETTINGS_BYTES)
        (proj / ".claude" / "hook-registration-profile.json").write_bytes(PROFILE_BYTES)
        return proj

    def run_copy(self, proj, *flags, extra=()):
        cmd = [sys.executable, *flags, ".claude/scripts/check_hook_registrations.py",
               "--settings", ".claude/settings.json",
               "--hook-registration-profile", ".claude/hook-registration-profile.json", *extra]
        return subprocess.run(cmd, cwd=str(proj), env=child_env(), capture_output=True, text=True, timeout=120)

    def test_the_checker_copied_alone_is_checker_dependency_missing(self):
        proj = self.stage(["check_hook_registrations.py"])
        done = self.run_copy(proj, extra=["--json"])
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        rep = json.loads(done.stdout)
        self.assertEqual(rep["refusal"]["code"], "checker-dependency-missing")
        self.assertIn("auto_improve_finish_install", rep["refusal"]["message"])
        for name in FIVE_FILES:
            self.assertIn(name, rep["refusal"]["message"])
        self.assertNotIn("Traceback", done.stderr)

    def test_a_missing_second_level_dependency_names_that_module(self):
        proj = self.stage(["check_hook_registrations.py", "auto_improve_finish_install.py"])
        done = self.run_copy(proj, extra=["--json"])
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        rep = json.loads(done.stdout)
        self.assertEqual(rep["refusal"]["code"], "checker-dependency-missing")
        self.assertIn("pr_merged", rep["refusal"]["message"])

    def test_the_bytecode_flag_is_the_first_statement_before_the_guarded_import(self):
        source = CHECKER.read_text(encoding="utf-8")
        flag = source.index("sys.dont_write_bytecode = True")
        self.assertLess(source.index("import sys"), flag)
        self.assertLess(flag, source.index("from auto_improve_finish_install import"))
        before_flag = source[:flag]
        for other in ("import json", "import os", "from pathlib", "import hashlib", "import argparse"):
            self.assertNotIn(other, before_flag, "nothing but `import sys` runs before the flag")

    def assert_tree_unchanged(self, *flags):
        proj = self.stage(FIVE_FILES, name="proj" + "".join(flags))
        before = snapshot(proj)
        done = self.run_copy(proj, *flags)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        after = snapshot(proj)
        self.assertEqual(after, before, "the check must leave the whole tree byte-identical")
        self.assertFalse([p for p in after if "__pycache__" in p or p.endswith(".pyc")])

    def test_a_vendored_copy_leaves_the_tree_byte_identical_with_dash_B(self):
        self.assert_tree_unchanged("-B")

    def test_a_vendored_copy_leaves_the_tree_byte_identical_without_dash_B(self):
        self.assert_tree_unchanged()

    def test_the_vendored_copy_fails_the_same_way_as_the_repository_copy(self):
        proj = self.stage(FIVE_FILES)
        s = settings_dict()
        row_of(s, "edit-gate.py")["if"] = "changed"
        (proj / ".claude" / "settings.json").write_bytes(as_bytes(s))
        done = self.run_copy(proj, "-B")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("FAIL " + R3, done.stdout)


# ===========================================================================
# This repository's landing step
# ===========================================================================
class ConventionsTests(unittest.TestCase):

    def block(self):
        path = REPO_ROOT / ".claude" / "work-item-conventions.json"
        return json.loads(path.read_text(encoding="utf-8"))["contractLanding"]

    def test_the_step_follows_loop_script_tests(self):
        steps = self.block()["verification"]["steps"]
        ids = [s["id"] for s in steps]
        self.assertEqual(ids.count("hook-registration-tests"), 1)
        self.assertEqual(ids.index("hook-registration-tests"), ids.index("loop-script-tests") + 1)
        self.assertEqual(steps[ids.index("hook-registration-tests")], {
            "id": "hook-registration-tests",
            "command": ["py", "-3", ".claude/scripts/tests/test_check_hook_registrations.py"],
            "results": {"format": "exit-code"},
            "timeout_minutes": 5,
        })

    def test_the_comment_describes_the_step_and_names_the_test_that_reads_the_steps(self):
        comment = self.block()["$comment"]
        self.assertIn("hook-registration-tests", comment)
        self.assertIn(".claude/scripts/tests/test_land_contract_verification.py", comment)

    def test_the_step_points_at_a_real_file(self):
        self.assertTrue((REPO_ROOT / ".claude" / "scripts" / "tests" / "test_check_hook_registrations.py").is_file())


if __name__ == "__main__":
    unittest.main()
