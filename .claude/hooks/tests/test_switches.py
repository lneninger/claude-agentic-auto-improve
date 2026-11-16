#!/usr/bin/env python3
"""
test_switches.py -- the switch helper (.claude/hooks/_switches.py) and its file rules.

Contract: .claude/concepts/2026-11-16-file-based-switches.md (Data Shapes: "Switch rules"; Commands:
Read switch, Read every switch, Claim database override, Name test; sub-task 1, "RED tests").

HOW IT RUNS
-----------
Every row runs the helper in its OWN python process, from a temporary copy of the hooks folder, with a
temporary project, a temporary home folder and an environment stripped of every CLAUDE* variable. A
fresh process per call matters: the helper must read the files at call time and must never remember a
path from import (Two-layer path resolution), and the error log path is fixed when _error_log is
imported. Nothing here touches this repository's own .claude folder or the real home folder.

Linked worktrees are made with real git, inside the temporary folder.

AT BASE the helper does not exist, so every row fails. The whole class is marked
unittest.expectedFailure through one decorator (RED). Sub-task 2 (the helper block) removes it.

WHAT THE ROWS ASSUME WHERE THE CONTRACT IS SILENT (the stricter reading is taken; see the hand-off)
  * switch(key, project=None) answers the value in force: the text "on" or "off" for an on/off key,
    "" or the path text for pinned_contract, "on", "off" or "trace" for contract_index. A boolean is
    read as "on"/"off" here, so the row does not pin the type.
  * A switch reading may be a plain value or an object or mapping with a "value" field.
  * The error log is <project>/.claude/logs/errors.jsonl and exists before the helper runs (the log
    helper never creates the folder). The state folder is <project>/.claude/state.

Run: py -3 .claude/hooks/tests/test_switches.py
"""
from __future__ import annotations

import codecs
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HOOKS_SRC = Path(__file__).resolve().parents[1]
PROCESS_TIMEOUT = 60

ON_OFF_KEYS = (
    "concept_gate", "architecture_guard", "accuracy_tracker", "integration_check",
    "memory_pager", "working_agreements", "plan_question_advisor",
)
ALL_KEYS = ON_OFF_KEYS + ("pinned_contract", "contract_index")

OFF_VALUES = [False, "off", "0", "false", "no", "OFF", " Off ", "No", "FALSE"]
ON_VALUES = [True, "on", "1", "true", "yes", "ON", " Yes ", "True"]

_RUNNER = r'''
import json, sys
hooks, op, args = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
sys.path.insert(0, hooks)
import _switches as s

def plain(r):
    if isinstance(r, bool):
        return "on" if r else "off"
    return r

def reading(r):
    if isinstance(r, dict):
        d = r
    elif hasattr(r, "_asdict"):
        d = r._asdict()
    elif hasattr(r, "__dict__") and not isinstance(r, str):
        d = dict(vars(r))
    else:
        return {"value": plain(r), "source": ""}
    if "value" not in d:
        return {"value": plain(r), "source": ""}
    return {"value": plain(d.get("value")), "source": str(d.get("source", ""))}

def outcome(o):
    return str(getattr(o, "value", o)).lower().replace("_", "-").split(".")[-1]

try:
    if op == "switch":
        key, project = args
        r = s.switch(key) if project is None else s.switch(key, project=project)
        out = reading(r)
    elif op == "all":
        project = args[0]
        r = s.effective_switches() if project is None else s.effective_switches(project=project)
        if isinstance(r, dict):
            out = {k: reading(v) for k, v in r.items()}
        else:
            out = {}
            for x in r:
                k = x["key"] if isinstance(x, dict) else x.key
                out[k] = reading(x)
    elif op == "claim":
        project, tool_call_id = args
        out = outcome(s.claim_database_override(project, tool_call_id))
    elif op == "names":
        out = bool(s.names_override_file(args[0]))
    else:
        raise SystemExit("unknown op")
    print(json.dumps({"ok": out}))
except SystemExit:
    raise
except BaseException as exc:
    print(json.dumps({"error": type(exc).__name__ + ": " + str(exc)}))
'''


def red(cls):
    """RED at base: every row of the class fails until the helper exists (sub-task 2 removes this)."""
    for name in dir(cls):
        if name.startswith("test_"):
            setattr(cls, name, unittest.expectedFailure(getattr(cls, name)))
    return cls


def _rmtree(path: Path) -> None:
    def fix(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    for _ in range(2):
        if not path.exists():
            return
        try:
            shutil.rmtree(path, onexc=fix)  # Python 3.12 and later
        except TypeError:
            shutil.rmtree(path, onerror=fix)
        except OSError:
            pass
    if path.exists():
        raise AssertionError("cleanup failed: could not remove " + str(path))


def base_env(home: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith("CLAUDE") and k != "DB_GUARD_FAULT_INJECTION"}
    env.update({"HOME": str(home), "USERPROFILE": str(home), "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONIOENCODING": "utf-8"})
    return env


def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", *args],
        cwd=str(cwd), capture_output=True, text=True, timeout=PROCESS_TIMEOUT)
    if proc.returncode != 0:
        raise AssertionError("fixture git failed: %s\n%s" % (args, proc.stderr[-300:]))
    return proc.stdout


class SwitchTestCase(unittest.TestCase):
    """One temporary root per test, removed in a cleanup that runs whether the test passes or fails."""

    hooks_dir: Path          # the hooks folder the helper is loaded from (a temporary copy)
    plugin_copy: Path        # the temporary plugin the copy lives in

    @classmethod
    def setUpClass(cls):
        cls._class_tmp = Path(tempfile.mkdtemp(prefix="switches-plugin-")).resolve()
        cls.plugin_copy = cls._class_tmp / "plugin"
        cls.hooks_dir = cls.plugin_copy / ".claude" / "hooks"
        cls.hooks_dir.mkdir(parents=True)
        for src in HOOKS_SRC.iterdir():
            if src.is_file() and src.suffix in (".py", ".json"):
                shutil.copy2(src, cls.hooks_dir / src.name)
        cls.addClassCleanup(_rmtree, cls._class_tmp)

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="switches-test-")).resolve()
        self.addCleanup(_rmtree, self.tmp)
        self.home = self.tmp / "home"
        self.home.mkdir()

    # ------------------------------------------------------------------ fixtures
    def project(self, name: str = "project", *, logs: bool = True, state: bool = True, git_init: bool = False) -> Path:
        root = self.tmp / name
        (root / ".claude").mkdir(parents=True)
        if logs:
            (root / ".claude" / "logs").mkdir()
        if state:
            (root / ".claude" / "state").mkdir()
        if git_init:
            git(root, "init", "-q")
            git(root, "commit", "-q", "--allow-empty", "-m", "base")
        return root

    @staticmethod
    def put(project: Path, name: str, content) -> Path:
        path = project / ".claude" / name
        if isinstance(content, (dict, list)) or content is None:
            data = json.dumps(content).encode("utf-8")
        elif isinstance(content, str):
            data = content.encode("utf-8")
        else:
            data = content
        path.write_bytes(data)
        return path

    def committed(self, project: Path, content) -> Path:
        return self.put(project, "switches.json", content)

    def local(self, project: Path, content) -> Path:
        return self.put(project, "switches.local.json", content)

    def worktree(self, main: Path, name: str = "wt") -> Path:
        wt = self.tmp / name
        git(main, "worktree", "add", "-q", "-b", name + "-branch", str(wt))
        (wt / ".claude").mkdir(exist_ok=True)
        (wt / ".claude" / "logs").mkdir(exist_ok=True)
        (wt / ".claude" / "state").mkdir(exist_ok=True)
        return wt

    # ------------------------------------------------------------------ running
    def call(self, op: str, args: list, *, env_project: Path | None = None, cwd: Path | None = None,
             extra_env: dict | None = None, hooks: Path | None = None):
        env = base_env(self.home)
        if env_project is not None:
            env["CLAUDE_PROJECT_DIR"] = str(env_project)
        env.update(extra_env or {})
        proc = subprocess.run(
            [sys.executable, "-I", "-B", "-c", _RUNNER, str(hooks or self.hooks_dir), op, json.dumps(args)],
            capture_output=True, env=env, cwd=str(cwd or self.tmp), timeout=PROCESS_TIMEOUT)
        err = proc.stderr.decode("utf-8", "replace")
        out = proc.stdout.decode("utf-8", "replace").strip()
        self.assertEqual(proc.returncode, 0, "the helper process failed: " + err[-400:])
        self.assertTrue(out, "the helper printed nothing: " + err[-400:])
        data = json.loads(out.splitlines()[-1])
        if "error" in data:
            raise AssertionError("the helper raised: " + data["error"] + " " + err[-300:])
        return data["ok"]

    def values(self, project: Path | None, **kw) -> dict:
        """Every key's value in force, reading through the explicit project argument."""
        data = self.call("all", [str(project) if project is not None else None], **kw)
        return {k: v["value"] for k, v in data.items()}

    def value(self, key: str, project: Path | None = None, **kw):
        return self.call("switch", [key, str(project) if project is not None else None], **kw)["value"]

    def assert_all_default(self, vals: dict, why: str):
        for key in ON_OFF_KEYS:
            self.assertEqual(vals.get(key), "on", "%s: %s must be at its default 'on'" % (why, key))
        self.assertEqual(vals.get("contract_index"), "on", why + ": contract_index must be at its default 'on'")
        self.assertIn(vals.get("pinned_contract"), ("", None), why + ": pinned_contract must be at its default (empty)")

    def log_lines(self, project: Path) -> list[str]:
        log = project / ".claude" / "logs" / "errors.jsonl"
        if not log.is_file():
            return []
        return [ln for ln in log.read_text(encoding="utf-8", errors="replace").splitlines()
                if "switches" in ln.lower()]

    def state_files(self, project: Path) -> list[Path]:
        folder = project / ".claude" / "state"
        return [p for p in folder.rglob("*") if p.is_file()] if folder.is_dir() else []


@red
class CatalogAndValueTests(SwitchTestCase):

    def test_the_catalog_holds_exactly_the_nine_keys_each_at_its_default(self):
        p = self.project()
        vals = self.values(p, env_project=p)
        self.assertEqual(set(vals), set(ALL_KEYS), "the catalog must hold exactly the nine keys of the Inventory")
        self.assert_all_default(vals, "no switch file")

    def test_an_unknown_key_to_the_read_switch_command_raises(self):
        p = self.project()
        with self.assertRaises(AssertionError) as ctx:
            self.value("not_a_switch", p, env_project=p)
        self.assertIn("raised", str(ctx.exception), "an unknown key is a programming error and must raise")

    def test_every_off_spelling_turns_each_on_off_key_off(self):
        for spelling in OFF_VALUES:
            with self.subTest(value=spelling):
                p = self.project("off-%d" % abs(hash(repr(spelling))))
                self.local(p, {k: spelling for k in ON_OFF_KEYS})
                vals = self.values(p, env_project=p)
                for key in ON_OFF_KEYS:
                    self.assertEqual(vals[key], "off", "%r must read as off for %s" % (spelling, key))

    def test_every_on_spelling_in_the_personal_file_beats_a_committed_off(self):
        for spelling in ON_VALUES:
            with self.subTest(value=spelling):
                p = self.project("on-%d" % abs(hash(repr(spelling))))
                self.committed(p, {k: "off" for k in ON_OFF_KEYS})
                self.local(p, {k: spelling for k in ON_OFF_KEYS})
                vals = self.values(p, env_project=p)
                for key in ON_OFF_KEYS:
                    self.assertEqual(vals[key], "on", "%r must read as on for %s" % (spelling, key))

    def test_a_value_outside_the_set_leaves_that_key_at_its_default_and_not_the_others(self):
        p = self.project()
        self.local(p, {"concept_gate": "maybe", "architecture_guard": "off", "memory_pager": 7,
                       "integration_check": None, "working_agreements": ["off"]})
        vals = self.values(p, env_project=p)
        self.assertEqual(vals["concept_gate"], "on", "a bad value leaves the key at its default")
        self.assertEqual(vals["memory_pager"], "on", "a number is outside the set")
        self.assertEqual(vals["integration_check"], "on", "null is outside the set")
        self.assertEqual(vals["working_agreements"], "on", "a list is outside the set")
        self.assertEqual(vals["architecture_guard"], "off", "a good value beside bad ones still counts")

    def test_an_unknown_key_is_ignored(self):
        p = self.project()
        self.local(p, {"bogus_switch": "off", "concept_gate": "off", "$comment": "ignored note"})
        vals = self.values(p, env_project=p)
        self.assertNotIn("bogus_switch", vals, "an unknown key must not become a switch")
        self.assertEqual(vals["concept_gate"], "off", "the known key still counts")

    def test_contract_index_takes_on_off_trace_and_reads_an_unknown_value_as_off(self):
        for text, want in (("on", "on"), ("off", "off"), ("trace", "trace"), ("banana", "off")):
            with self.subTest(value=text):
                p = self.project("ci-" + text)
                self.local(p, {"contract_index": text})
                self.assertEqual(self.value("contract_index", p, env_project=p), want)

    def test_a_pinned_contract_in_the_personal_file_is_read_and_in_the_committed_file_is_ignored(self):
        p = self.project()
        self.committed(p, {"pinned_contract": ".claude/concepts/committed-pin.md"})
        self.assertIn(self.value("pinned_contract", p, env_project=p), ("", None),
                      "a pinned_contract in the Switch file is misplaced and must be ignored")
        self.local(p, {"pinned_contract": ".claude/concepts/personal-pin.md"})
        self.assertEqual(self.value("pinned_contract", p, env_project=p), ".claude/concepts/personal-pin.md",
                         "a pinned_contract in the Local switch file is the pin")

    def test_the_personal_file_wins_key_by_key_over_the_committed_file(self):
        p = self.project()
        self.committed(p, {"concept_gate": "off", "architecture_guard": "off"})
        self.local(p, {"concept_gate": "on", "memory_pager": "off"})
        vals = self.values(p, env_project=p)
        self.assertEqual(vals["concept_gate"], "on", "the personal file wins for a key it sets")
        self.assertEqual(vals["architecture_guard"], "off", "a key the personal file leaves out comes from the committed file")
        self.assertEqual(vals["memory_pager"], "off", "a key only the personal file sets is honoured")
        self.assertEqual(vals["working_agreements"], "on", "a key nobody sets stays at its default")

    def test_a_reading_names_its_source_file_when_it_carries_one(self):
        p = self.project()
        self.committed(p, {"architecture_guard": "off"})
        self.local(p, {"concept_gate": "off"})
        data = self.call("all", [str(p)], env_project=p)
        for key, want in (("concept_gate", "switches.local.json"), ("architecture_guard", "switches.json"),
                          ("memory_pager", "default")):
            source = data[key]["source"]
            if source:  # a plain value carries no source: the row does not force the shape
                self.assertIn(want, source, "the source of %s must name %s" % (key, want))


@red
class NoFileAndBrokenFileTests(SwitchTestCase):

    def test_a_missing_empty_or_whitespace_file_means_no_settings_and_reports_nothing(self):
        for label, content in (("empty", b""), ("blank", b"  \r\n\t \n"), ("missing", None)):
            with self.subTest(file=label):
                p = self.project("nofile-" + label)
                if content is not None:
                    self.local(p, content)
                    self.committed(p, content)
                self.assert_all_default(self.values(p, env_project=p), label + " file")
                self.assertEqual(self.log_lines(p), [], "no-file is not a problem and must write no report")

    def test_a_broken_personal_file_makes_every_switch_file_ignored_so_a_committed_off_does_not_stay(self):
        cases = {
            "invalid-json": b"{ not json",
            "array": b"[1, 2]",
            "string": b'"off"',
            "null": b"null",
            "undecodable": b"\x80\x81\x82{}",
            "utf16-without-mark": '{"concept_gate": "off"}'.encode("utf-16-le"),
        }
        for label, content in cases.items():
            with self.subTest(broken=label):
                p = self.project("broken-" + label)
                self.committed(p, {"concept_gate": "off", "architecture_guard": "off"})
                self.local(p, content)
                self.assert_all_default(self.values(p, env_project=p), "broken personal file (%s)" % label)

    def test_a_broken_committed_file_makes_the_personal_file_ignored_too(self):
        p = self.project()
        self.committed(p, b"[]")
        self.local(p, {"concept_gate": "off"})
        self.assert_all_default(self.values(p, env_project=p), "broken committed file")

    def test_a_folder_at_the_file_path_is_unreadable_and_everything_is_default(self):
        p = self.project()
        self.committed(p, {"concept_gate": "off"})
        (p / ".claude" / "switches.local.json").mkdir()
        self.assert_all_default(self.values(p, env_project=p), "folder at the personal file path")

    def test_each_broken_file_is_reported_once_per_file_state_across_processes(self):
        cases = {"invalid-json": b"{ nope", "not-an-object": b"[1]"}
        for label, content in cases.items():
            with self.subTest(broken=label):
                p = self.project("report-" + label)
                self.local(p, content)
                self.values(p, env_project=p)
                first = self.log_lines(p)
                self.assertEqual(len(first), 1, "a broken file is reported once on its first read: %r" % first)
                self.values(p, env_project=p)
                self.value("concept_gate", p, env_project=p)
                self.assertEqual(self.log_lines(p), first, "the same file state must not be reported again")
                self.local(p, content + b" ")  # a different file state
                self.values(p, env_project=p)
                self.assertEqual(len(self.log_lines(p)), 2, "a changed file state is a new report")

    def test_an_unreadable_folder_is_reported_once(self):
        p = self.project()
        (p / ".claude" / "switches.local.json").mkdir()
        self.values(p, env_project=p)
        first = self.log_lines(p)
        self.assertEqual(len(first), 1, "an unreadable file is a reported problem: %r" % first)
        self.values(p, env_project=p)
        self.assertEqual(self.log_lines(p), first, "an unreadable file is reported once per path, kind and time")

    def test_an_unknown_key_a_bad_value_and_a_misplaced_pin_are_each_reported_once(self):
        p = self.project()
        self.committed(p, {"bogus_switch": "off", "concept_gate": "maybe", "pinned_contract": "x.md"})
        self.values(p, env_project=p)
        first = self.log_lines(p)
        text = "\n".join(first)
        for key in ("bogus_switch", "concept_gate", "pinned_contract"):
            self.assertIn(key, text, "the report must name the offending key %s" % key)
        self.values(p, env_project=p)
        self.assertEqual(self.log_lines(p), first, "the same problems must not be reported again")

    def test_a_clean_file_writes_no_report_and_no_marker(self):
        p = self.project()
        self.committed(p, {"$comment": "note", "concept_gate": "on"})
        self.values(p, env_project=p)
        self.assertEqual(self.log_lines(p), [], "a clean file reports nothing")
        self.assertEqual(self.state_files(p), [], "a clean file leaves no marker")

    def test_the_marker_is_not_written_when_the_log_write_fails_and_the_problem_is_reported_later(self):
        p = self.project("nolog", logs=False)          # the log helper writes nothing without its folder
        self.local(p, b"{ broken")
        self.values(p, env_project=p)
        self.assertEqual(self.state_files(p), [],
                         "the marker must follow a successful log write, never precede it (Journal 2026-11-07)")
        (p / ".claude" / "logs").mkdir()
        self.values(p, env_project=p)
        self.assertEqual(len(self.log_lines(p)), 1, "the problem must be reported once the log can be written")
        self.assertTrue(self.state_files(p), "the marker is written after the log write succeeds")
        self.values(p, env_project=p)
        self.assertEqual(len(self.log_lines(p)), 1, "and not reported again")


@red
class EncodingTests(SwitchTestCase):

    TEXT = '{"concept_gate": "off", "architecture_guard": false}'

    def _assert_off(self, project: Path, why: str):
        vals = self.values(project, env_project=project)
        self.assertEqual(vals["concept_gate"], "off", why)
        self.assertEqual(vals["architecture_guard"], "off", why)
        self.assertEqual(self.log_lines(project), [], why + ": a readable file reports nothing")

    def test_a_utf8_byte_order_mark_is_dropped(self):
        p = self.project()
        self.local(p, codecs.BOM_UTF8 + self.TEXT.encode("utf-8"))
        self._assert_off(p, "UTF-8 with a byte order mark")

    def test_a_utf16_little_endian_file_with_a_mark_is_read(self):
        p = self.project()
        self.local(p, codecs.BOM_UTF16_LE + self.TEXT.encode("utf-16-le"))
        self._assert_off(p, "UTF-16 little-endian, what Windows PowerShell 5.1 writes")

    def test_a_utf16_big_endian_file_with_a_mark_is_read(self):
        p = self.project()
        self.local(p, codecs.BOM_UTF16_BE + self.TEXT.encode("utf-16-be"))
        self._assert_off(p, "UTF-16 big-endian")

    def test_a_committed_utf16_file_is_read_the_same_way(self):
        p = self.project()
        self.committed(p, codecs.BOM_UTF16_LE + self.TEXT.encode("utf-16-le"))
        self._assert_off(p, "committed UTF-16 file")


@red
class ProjectFolderRuleTests(SwitchTestCase):

    OFF = {k: "off" for k in ON_OFF_KEYS}

    def test_with_no_project_known_every_key_is_default_even_with_decoys_in_the_working_directory(self):
        cwd = self.project("cwd")
        self.committed(cwd, self.OFF)
        self.local(cwd, self.OFF)
        self.assert_all_default(self.values(None, cwd=cwd), "no project argument, no CLAUDE_PROJECT_DIR")

    def test_a_decoy_in_the_working_directory_is_never_read_when_a_project_is_named(self):
        project = self.project("project")
        cwd = self.project("cwd")
        self.committed(cwd, self.OFF)
        self.local(cwd, self.OFF)
        self.assert_all_default(self.values(project, env_project=project, cwd=cwd), "explicit project, decoy cwd")
        self.assert_all_default(self.values(None, env_project=project, cwd=cwd), "env project, decoy cwd")

    def test_a_decoy_in_the_plugins_own_claude_folder_is_never_read(self):
        plugin = self.tmp / "decoy-plugin"
        hooks = plugin / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        for src in self.hooks_dir.iterdir():
            if src.is_file():
                shutil.copy2(src, hooks / src.name)
        for name in ("switches.json", "switches.local.json"):
            (plugin / ".claude" / name).write_text(json.dumps(self.OFF), encoding="utf-8")
        project = self.project("project")
        self.assert_all_default(self.values(project, env_project=project, hooks=hooks), "plugin decoy, project named")
        self.assert_all_default(self.values(None, hooks=hooks), "plugin decoy, no project known")

    def test_a_decoy_around_a_main_checkout_is_never_read(self):
        main = self.project("main", git_init=True)
        # the parent folder and a sibling checkout hold decoys; the project itself has no personal file
        (self.tmp / ".claude").mkdir(exist_ok=True)
        (self.tmp / ".claude" / "switches.local.json").write_text(json.dumps(self.OFF), encoding="utf-8")
        sibling = self.project("sibling", git_init=True)
        self.local(sibling, self.OFF)
        self.committed(sibling, self.OFF)
        self.assert_all_default(self.values(main, env_project=main), "a main checkout reads only its own .claude")

    def test_an_explicit_project_argument_wins_over_claude_project_dir(self):
        a = self.project("a")
        b = self.project("b")
        self.local(a, {"concept_gate": "off"})
        self.assertEqual(self.value("concept_gate", b, env_project=a), "on",
                         "the explicit project (clean) wins over the environment project (off)")
        self.assertEqual(self.value("concept_gate", a, env_project=b), "off",
                         "the explicit project (off) wins over the environment project (clean)")
        self.assertEqual(self.value("concept_gate", None, env_project=a), "off",
                         "with no argument the project comes from CLAUDE_PROJECT_DIR")

    def test_an_environment_variable_named_like_a_switch_changes_nothing(self):
        p = self.project()
        env = {"CLAUDE_CONCEPT_GATE": "off", "concept_gate": "off", "CLAUDE_ARCH_GUARD": "off",
               "CLAUDE_CONTRACT_INDEX": "trace", "CLAUDE_ACTIVE_CONTRACT": "x.md"}
        self.assert_all_default(self.values(p, env_project=p, extra_env=env), "old variables set, no file")
        self.local(p, {"concept_gate": "off"})
        self.assertEqual(self.value("concept_gate", p, env_project=p,
                                    extra_env={"CLAUDE_CONCEPT_GATE": "on", "concept_gate": "on"}), "off",
                         "a variable must not override the file either")

    def test_the_helper_reads_the_files_at_call_time_not_at_import(self):
        p = self.project()
        self.assertEqual(self.value("concept_gate", p, env_project=p), "on")
        self.local(p, {"concept_gate": "off"})
        self.assertEqual(self.value("concept_gate", p, env_project=p), "off",
                         "a second process sees the edit: nothing may be cached on disk or at import")


@red
class WorktreeRuleTests(SwitchTestCase):

    def test_a_linked_worktree_with_nothing_there_reads_the_main_checkouts_personal_file(self):
        main = self.project("main", git_init=True)
        self.local(main, {"concept_gate": "off", "pinned_contract": ".claude/concepts/main-pin.md"})
        wt = self.worktree(main)
        vals = self.values(wt, env_project=wt)
        self.assertEqual(vals["concept_gate"], "off", "no personal file in the worktree: the main checkout's counts")
        self.assertEqual(vals["pinned_contract"], ".claude/concepts/main-pin.md")

    def test_an_empty_own_file_stops_the_fallback(self):
        main = self.project("main", git_init=True)
        self.local(main, {"concept_gate": "off"})
        wt = self.worktree(main)
        self.local(wt, b"")
        self.assert_all_default(self.values(wt, env_project=wt), "empty own personal file")

    def test_a_blank_own_file_stops_the_fallback(self):
        main = self.project("main", git_init=True)
        self.local(main, {"concept_gate": "off"})
        wt = self.worktree(main)
        self.local(wt, b" \n ")
        self.assert_all_default(self.values(wt, env_project=wt), "whitespace-only own personal file")

    def test_a_broken_own_file_stops_the_fallback_and_every_file_is_ignored(self):
        main = self.project("main", git_init=True)
        self.local(main, {"concept_gate": "off"})
        wt = self.worktree(main)
        self.committed(wt, {"architecture_guard": "off"})
        self.local(wt, b"{ broken")
        self.assert_all_default(self.values(wt, env_project=wt), "broken own personal file")

    def test_a_folder_at_the_own_path_counts_as_something_there(self):
        main = self.project("main", git_init=True)
        self.local(main, {"concept_gate": "off"})
        wt = self.worktree(main)
        (wt / ".claude" / "switches.local.json").mkdir()
        self.assert_all_default(self.values(wt, env_project=wt), "anything at the own path stops the fallback")

    def test_a_valid_own_file_wins_and_the_main_checkouts_is_not_merged_in(self):
        main = self.project("main", git_init=True)
        self.local(main, {"concept_gate": "off", "memory_pager": "off"})
        wt = self.worktree(main)
        self.local(wt, {"architecture_guard": "off"})
        vals = self.values(wt, env_project=wt)
        self.assertEqual(vals["architecture_guard"], "off")
        self.assertEqual(vals["concept_gate"], "on", "the main checkout's file is not read once the worktree has its own")
        self.assertEqual(vals["memory_pager"], "on")

    def test_a_broken_main_checkout_file_read_through_the_fallback_counts_as_broken(self):
        main = self.project("main", git_init=True)
        self.local(main, b"[1, 2]")
        wt = self.worktree(main)
        self.committed(wt, {"architecture_guard": "off"})
        self.assert_all_default(self.values(wt, env_project=wt), "broken main-checkout file")

    def test_the_committed_file_always_comes_from_the_worktree_itself(self):
        main = self.project("main", git_init=True)
        self.committed(main, {"concept_gate": "off"})
        wt = self.worktree(main)
        self.assertEqual(self.value("concept_gate", wt, env_project=wt), "on",
                         "the main checkout's committed file must not be read for a worktree")
        self.committed(wt, {"concept_gate": "off"})
        self.assertEqual(self.value("concept_gate", wt, env_project=wt), "off", "the worktree's own committed file counts")

    def test_the_main_checkouts_committed_file_still_counts_in_the_main_checkout(self):
        main = self.project("main", git_init=True)
        self.committed(main, {"concept_gate": "off"})
        self.assertEqual(self.value("concept_gate", main, env_project=main), "off")

    def test_decoys_in_the_working_directory_and_the_plugin_are_not_used_by_the_fallback(self):
        main = self.project("main", git_init=True)
        wt = self.worktree(main)
        cwd = self.project("cwd")
        self.local(cwd, {"concept_gate": "off"})
        self.assert_all_default(self.values(wt, env_project=wt, cwd=cwd), "worktree with nothing, decoy in cwd")


@red
class DatabaseOverrideHelperTests(SwitchTestCase):
    """The helper's two override commands (Commands: Claim database override and Name test)."""

    def arm(self, project: Path, age_seconds: float = 0.0) -> Path:
        path = project / ".claude" / "database-override.once"
        path.write_bytes(b"")
        stamp = time.time() - age_seconds
        os.utime(path, (stamp, stamp))
        return path

    def test_with_no_arm_the_outcome_is_absent(self):
        p = self.project()
        self.assertEqual(self.call("claim", [str(p), "tool-1"], env_project=p), "absent")

    def test_a_fresh_arm_is_claimed_by_rename_and_used_up(self):
        p = self.project()
        arm = self.arm(p)
        self.assertEqual(self.call("claim", [str(p), "tool-1"], env_project=p), "claimed")
        self.assertFalse(arm.exists(), "the arm is renamed away when claimed (Use-once rule)")
        self.assertTrue((p / ".claude" / "database-override.claimed-tool-1").exists(),
                        "the claim carries the tool call identifier")
        self.assertEqual(self.call("claim", [str(p), "tool-2"], env_project=p), "absent",
                         "one arm serves one tool call")

    def test_a_second_claim_for_the_same_tool_call_is_claimed_by_sibling(self):
        p = self.project()
        self.arm(p)
        self.assertEqual(self.call("claim", [str(p), "tool-9"], env_project=p), "claimed")
        self.assertEqual(self.call("claim", [str(p), "tool-9"], env_project=p), "claimed-by-sibling")

    def test_a_stale_arm_is_removed_and_reported_stale(self):
        p = self.project()
        arm = self.arm(p, age_seconds=16 * 60)
        self.assertEqual(self.call("claim", [str(p), "tool-1"], env_project=p), "stale")
        self.assertFalse(arm.exists(), "a stale arm is removed")

    def test_a_folder_or_a_link_at_the_arm_path_is_unusable(self):
        p = self.project("folder")
        (p / ".claude" / "database-override.once").mkdir()
        self.assertEqual(self.call("claim", [str(p), "tool-1"], env_project=p), "unusable")

    def test_a_link_arm_is_unusable(self):
        p = self.project("link")
        target = p / "elsewhere.txt"
        target.write_bytes(b"")
        try:
            os.symlink(target, p / ".claude" / "database-override.once")
        except (OSError, NotImplementedError) as exc:
            self.skipTest("this machine cannot create a symbolic link: %s" % exc)
        self.assertEqual(self.call("claim", [str(p), "tool-1"], env_project=p), "unusable")

    def test_the_name_test_matches_a_path_or_text_naming_the_arm_in_any_case_and_slash(self):
        for text in (".claude/database-override.once", r"C:\proj\.claude\Database-Override.ONCE",
                     "touch '.claude/database-override.x'", "database-override.claimed-abc"):
            with self.subTest(text=text):
                self.assertTrue(self.call("names", [text]), "must name the arm: " + text)

    def test_the_name_test_does_not_match_other_names(self):
        for text in (".claude/switches.json", "docs/override.md", "database_override", "notes.txt"):
            with self.subTest(text=text):
                self.assertFalse(self.call("names", [text]), "must not name the arm: " + text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
