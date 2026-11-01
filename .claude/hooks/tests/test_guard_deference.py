#!/usr/bin/env python3
"""
test_guard_deference.py -- Guard deference: the plugin's copy of a database guard stands down when
the PROJECT registers its own copy of the same guard for the same event and tool.

Contract: .claude/concepts/2026-10-12-dedupe-claude-config.md in the consuming repository, Value
Objects ("Project guard registration", conditions (a) to (h), invariants I-D1 to I-D3), and the
sub-task 2 rows D1 to D19. The vocabulary term is "Guard deference": the plugin copy exits without
acting because the project registers its own copy. It is never a guard that turns itself off.

WHAT IS PINNED DOWN
-------------------
Each of the two guards (db-destructive-guard.py, db-research-readonly-guard.py) has its OWN set of
rows below. Every row follows one pattern, so no row can pass by accident:

  1. A CONTROL: the world is built so that the guard MUST defer (exit 0 and a "deferred" decision
     in the project's db-guard.log). A guard with no deference code fails here, which is why every
     "acts" row is RED today and not vacuously green.
  2. ONE MUTATION: exactly one condition is broken.
  3. The guard must ACT: exit 2 on the same blocked payload, and no "deferred" record is written.

I-D3 says every failure resolves toward acting, so the worst wrong answer is a guard that runs
twice, never a call that no guard checks.

HOW THE FIXTURES WORK (no real machine state is read or written)
----------------------------------------------------------------
* A throwaway PLUGIN folder holds copies of the real hook files (the code under test), a generated
  hooks.json (so a row can set the plugin's own timeout) and the plugin manifest.
* A throwaway PROJECT folder holds the project's settings.json, the stub file the settings row
  launches, and the guard's rules file.
* HOME, USERPROFILE, TEMP, TMP and TMPDIR all point at a fixture folder, so the session-start
  marker (condition (h)) lands in the fixture and the real home is never touched.
* The session-start marker is written by the REAL writer (working-agreements.py), never invented by
  the test. Its name is settled by decision 2 of the block 2 review: `auto-improve-session-start-<session_id>`
  in the system temporary folder, holding the time as a number. Block 17's baseline file uses another
  prefix (`auto-improve-changed-baseline-<session_id>`), so the two never collide; a row plants such a
  baseline file with a misleading value and the guard must still read only the marker. Rows that need a
  different marker select it by that prefix and rewrite its contents in the format the writer used.
* Rows that need a broken helper edit the fixture copy of _project_paths.py. They find the deference
  functions by the substring "defer" in a top-level function name (case-insensitive). If the helper
  names its function something else, those rows fail with a message that says so; name it with
  "defer" in it. (The contract names the term "Guard deference" and calls it "the deference helper".)

Payloads are built from parts; this file never holds a literal destructive phrase.

Run: py -3 .claude/hooks/tests/test_guard_deference.py
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HOOKS_SRC = Path(__file__).resolve().parents[1]
PLUGIN_SRC = HOOKS_SRC.parent.parent
HOOK_TIMEOUT = 90

#: Built from parts so no destructive phrase appears in this file.
_EF_REMOVE = "dotnet ef database " + "dr" + "op" + " --force"
_SQL_WRITE = 'sqlcmd -S "(localdb)\\fixture" -E -Q "' + "INS" + "ERT INTO Orders (Id) VALUES (1)" + '"'

SESSION_ID = "sess-0001-fixture"
#: Decision 2 (block 2 review): the session-start marker and block 17's baseline never share a name.
MARKER_PREFIX = "auto-improve-session-start-"
BASELINE_PREFIX = "auto-improve-changed-baseline-"


#: Where the launcher source lives and what it is called (contract Revision 9, section L): the constant is
#: read from the helper beside this tests folder, never from a fixture copy.
LAUNCHER_CONSTANT = "PROJECT_HOOK_LAUNCHER_SOURCE"


#: Used ONLY while the constant does not exist yet, so that every launcher row below fails today for
#: its stated reason (the plugin copy did not defer) instead of all failing at one lookup. One row,
#: test_r9_the_launcher_source_constant_exists, fails for the missing constant itself.
_STAND_IN_LAUNCHER_TEXT = ("# agentic-auto-improve project-hook-launch v1\nimport os, sys\n"
                           "# stand-in text: the real constant does not exist yet\n")


def _load_launcher_constant():
    """The launcher source constant of the real ``_project_paths.py``, or ``None`` when it is absent."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_t28_deference_project_paths", str(HOOKS_SRC / "_project_paths.py"))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception:
        return None
    value = getattr(module, LAUNCHER_CONSTANT, None)
    return value if isinstance(value, str) and value.strip() else None


def launcher_source_or_fail(case: unittest.TestCase) -> str:
    """The launcher source constant, or the stand-in text while the constant is absent."""
    value = _load_launcher_constant()
    return value if value is not None else _STAND_IN_LAUNCHER_TEXT


def _rmtree(path: Path) -> None:
    def _onerror(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, onerror=_onerror)


class GuardSpec:
    """What differs between the two guards."""

    def __init__(self, file_name: str, hook_name: str, command: str):
        self.file_name = file_name
        self.hook_name = hook_name
        self.command = command

    def payload(self, tool: str = "Bash", cwd: str = "", session: str | None = SESSION_ID) -> dict:
        data = {"tool_name": tool, "tool_input": {"command": self.command}, "cwd": cwd}
        if session is not None:
            data["session_id"] = session
        return data


DESTRUCTIVE = GuardSpec("db-destructive-guard.py", "db-destructive-guard", _EF_REMOVE)
READONLY = GuardSpec("db-research-readonly-guard.py", "db-research-readonly-guard", _SQL_WRITE)


class World:
    """One plugin folder, one project folder and one fixture machine, all temporary."""

    def __init__(self, spec: GuardSpec, plugin_timeout: "int | list | None" = None):
        """plugin_timeout: one timeout for a single registration group, or a list of (matcher, timeout)
        pairs, one group each (the real hooks.json registers the destructive guard in three groups)."""
        self.spec = spec
        self.tmp = Path(tempfile.mkdtemp(prefix="guard-deference-"))
        self.machine = self.tmp / "machine"
        self.temp_dir = self.machine / "temp"
        self.home = self.machine / "home"
        for d in (self.temp_dir, self.home):
            d.mkdir(parents=True)
        self.plugin = self.tmp / "plugin"
        self.plugin_hooks = self.plugin / ".claude" / "hooks"
        self.project = self.tmp / "project"
        self.project_hooks = self.project / ".claude" / "hooks"
        self.settings_path = self.project / ".claude" / "settings.json"
        self.local_settings_path = self.project / ".claude" / "settings.local.json"
        self.log_path = self.project / ".claude" / "logs" / "db-guard.log"
        self._build_plugin(plugin_timeout)
        self._build_project()
        self.registered_path = "${CLAUDE_PROJECT_DIR}/.claude/hooks/" + spec.file_name

    # ----------------------------------------------------------------- build
    def _build_plugin(self, plugin_timeout) -> None:
        self.plugin_hooks.mkdir(parents=True)
        for src in HOOKS_SRC.iterdir():
            if src.is_file() and src.name != "hooks.json" and src.suffix in (".py", ".json"):
                shutil.copy2(src, self.plugin_hooks / src.name)
        (self.plugin / ".claude-plugin").mkdir()
        (self.plugin / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "agentic-auto-improve", "version": "0.0.0"}), encoding="utf-8")
        agreements = PLUGIN_SRC / ".claude" / "agreements"
        if agreements.is_dir():
            shutil.copytree(agreements, self.plugin / ".claude" / "agreements")
        if isinstance(plugin_timeout, list):
            groups = plugin_timeout
        else:
            groups = [("Edit|Write|MultiEdit|NotebookEdit|Bash|PowerShell", plugin_timeout)]
        built = []
        for matcher, timeout in groups:
            entry = {"type": "command", "command": "py",
                     "args": ["-3", "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/" + self.spec.file_name]}
            if timeout is not None:
                entry["timeout"] = timeout
            built.append({"matcher": matcher, "hooks": [entry]})
        hooks_json = {"hooks": {"PreToolUse": built}}
        (self.plugin_hooks / "hooks.json").write_text(json.dumps(hooks_json, indent=2), encoding="utf-8")

    def _build_project(self) -> None:
        self.project_hooks.mkdir(parents=True)
        (self.project_hooks / self.spec.file_name).write_text("# the project's registered copy\n", encoding="utf-8")
        (self.project_hooks / "db-destructive-guard.rules.json").write_text(json.dumps({
            "protected_databases": ["FixtureDb"], "production_path_allowlist": ["src/"]}), encoding="utf-8")

    # ------------------------------------------------------------- settings
    def entry(self, launched: str | None = None, *, form: str = "exec", timeout=None, async_=None) -> dict:
        launched = launched if launched is not None else self.registered_path
        if form == "exec":
            entry = {"type": "command", "command": "py", "args": ["-3", launched]}
        else:
            entry = {"type": "command", "command": 'py -3 "' + launched + '"'}
        if timeout is not None:
            entry["timeout"] = timeout
        if async_ is not None:
            entry["async"] = async_
        return entry

    def settings_body(self, entry: dict | None = None, *, matcher: str = "Bash|PowerShell",
                      event: str = "PreToolUse", extra: dict | None = None) -> dict:
        entry = entry if entry is not None else self.entry()
        body: dict = {"hooks": {event: [{"matcher": matcher, "hooks": [entry]}]}}
        if extra:
            body.update(extra)
        return body

    def write_settings(self, body: dict | str, path: Path | None = None, *, age: float = 3600.0) -> Path:
        path = path or self.settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body if isinstance(body, str) else json.dumps(body, indent=2), encoding="utf-8")
        self.set_age(path, age)
        return path

    @staticmethod
    def set_age(path: Path, seconds_ago: float) -> None:
        stamp = time.time() - seconds_ago
        os.utime(path, (stamp, stamp))

    def register(self, **kwargs) -> None:
        """The baseline: a correct exec-form registration, older than the session start."""
        self.write_settings(self.settings_body(self.entry(**{k: v for k, v in kwargs.items()
                                                               if k in ("launched", "form", "timeout", "async_")}),
                                               matcher=kwargs.get("matcher", "Bash|PowerShell")))

    # --------------------------------------------------------------- running
    def env(self, *, project: bool = True) -> dict:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("CLAUDE") and k not in ("DB_GUARD_FAULT_INJECTION",)}
        env.update({
            "HOME": str(self.home), "USERPROFILE": str(self.home),
            "TEMP": str(self.temp_dir), "TMP": str(self.temp_dir), "TMPDIR": str(self.temp_dir),
            "CLAUDE_PLUGIN_ROOT": str(self.plugin),
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
        })
        if project:
            env["CLAUDE_PROJECT_DIR"] = str(self.project)
        return env

    def run_hook(self, script: Path, payload: dict, *, project: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-B", str(script)], input=json.dumps(payload).encode("utf-8"),
                              capture_output=True, env=self.env(project=project), timeout=HOOK_TIMEOUT,
                              cwd=str(self.tmp))

    def run_guard(self, payload: dict | None = None, *, project: bool = True, script: Path | None = None):
        payload = payload or self.spec.payload(cwd=str(self.project))
        return self.run_hook(script or (self.plugin_hooks / self.spec.file_name), payload, project=project)

    def start_session(self, source: str = "startup", session: str = SESSION_ID):
        """Run the real session-start hook of the fixture plugin; it writes the marker for startup/resume."""
        payload = {"hook_event_name": "SessionStart", "session_id": session, "source": source,
                   "cwd": str(self.project)}
        return self.run_hook(self.plugin_hooks / "working-agreements.py", payload)

    # ---------------------------------------------------------------- log
    def log_records(self) -> list[dict]:
        if not self.log_path.is_file():
            return []
        records = []
        for line in self.log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
        return records

    def deferred_records(self) -> list[dict]:
        return [r for r in self.log_records()
                if r.get("decision") == "deferred" and r.get("hook") == self.spec.hook_name]

    def clear_log(self) -> None:
        if self.log_path.is_file():
            self.log_path.unlink()

    # -------------------------------------------------------------- marker
    def marker_files(self, session: str = SESSION_ID) -> list[Path]:
        """The session-start marker: selected by its prefix and the session id (decision 2). A file that
        merely contains the session id (block 17's baseline) is not a marker."""
        return [p for p in self.temp_dir.iterdir() if p.is_file() and p.name == MARKER_PREFIX + session]

    def marker_value(self) -> float:
        files = self.marker_files()
        assert len(files) == 1, "expected exactly one session-start marker, found %r" % [f.name for f in files]
        text = files[0].read_text(encoding="utf-8").strip()
        assert re.fullmatch(r"\d+(\.\d+)?", text), "the marker must hold the time as a number, found %r" % text
        return float(text)

    def rewrite_marker(self, value: float | str) -> None:
        files = self.marker_files()
        assert len(files) == 1, "expected exactly one session-start marker, found %r" % [f.name for f in files]
        original = files[0].read_text(encoding="utf-8").strip()
        if isinstance(value, str):
            files[0].write_text(value, encoding="utf-8")
        elif "." in original:
            files[0].write_text("%.6f" % value, encoding="utf-8")
        else:
            files[0].write_text(str(int(value)), encoding="utf-8")

    # -------------------------------------------------------------- helper
    def helper_path(self) -> Path:
        return self.plugin_hooks / "_project_paths.py"

    def deference_function_names(self) -> list[str]:
        tree = ast.parse(self.helper_path().read_text(encoding="utf-8"))
        return [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and "defer" in n.name.lower()]

    def cleanup(self) -> None:
        _rmtree(self.tmp)


class DeferenceRows:
    """Shared rows (a mixin, so the unittest loader never collects it alone). A subclass sets SPEC."""

    SPEC: GuardSpec

    def setUp(self):
        self.worlds: list[World] = []

    def tearDown(self):
        for w in self.worlds:
            w.cleanup()

    def world(self, plugin_timeout: int | None = None) -> World:
        w = World(self.SPEC, plugin_timeout)
        self.worlds.append(w)
        return w

    # ------------------------------------------------------------ asserts
    def assert_defers(self, w: World, why: str, payload: dict | None = None, **kw) -> None:
        proc = w.run_guard(payload, **kw)
        err = proc.stderr.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 0,
                         "CONTROL (%s): the plugin copy must defer to the registered project copy and exit 0, "
                         "but it exited %d. stderr: %s" % (why, proc.returncode, err[:300]))
        self.assertEqual(len(w.deferred_records()), 1,
                         "CONTROL (%s): a deferral must write ONE 'deferred' decision to the project's "
                         "db-guard.log (I-D2); a clean exit with no log line is never read as a deferral. "
                         "Records seen: %r" % (why, w.log_records()))

    def assert_acts(self, w: World, why: str, payload: dict | None = None, **kw) -> None:
        proc = w.run_guard(payload, **kw)
        err = proc.stderr.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 2,
                         "%s: with this condition broken the guard must ACT as it does today (exit 2 on the "
                         "blocked payload), never defer (I-D3). It exited %d. stderr: %s"
                         % (why, proc.returncode, err[:300]))
        self.assertEqual(w.deferred_records(), [],
                         "%s: an acting guard must not write a 'deferred' decision (I-D2)" % why)

    def baseline(self, **world_kwargs) -> World:
        """A world whose guard must defer: correct registration, marker well after the settings file's."""
        w = self.world(**world_kwargs)
        w.register()
        started = w.start_session("startup")
        self.assertEqual(started.returncode, 0, "the session-start hook must exit 0")
        return w

    def mutate_and_expect_act(self, why: str, mutate, **world_kwargs) -> World:
        """Control (defers), clear the log, apply ONE mutation, then the guard must act."""
        w = self.baseline(**world_kwargs)
        self.assert_defers(w, why)
        w.clear_log()
        mutate(w)
        self.assert_acts(w, why)
        return w

    # ===================================================================
    # D1 / D2 -- the registrations that DO defer
    # ===================================================================
    def test_d1_exec_form_registration_defers_and_the_same_payload_without_it_is_blocked(self):
        w = self.baseline()
        self.assert_defers(w, "exec-form registration")
        w.clear_log()
        w.write_settings({"hooks": {}})            # the registration removed, same session, same payload
        self.assert_acts(w, "D1 same run, registration removed")

    def test_d1_a_positive_control_an_unregistered_project_is_blocked(self):
        # PASSES TODAY BY DESIGN: it is the blocked payload's own control. If this ever returns 0 the
        # payload used by every row in this file no longer proves anything.
        w = self.world()
        w.start_session("startup")
        self.assert_acts(w, "unregistered project")

    def test_d2_shell_form_with_braces_defers(self):
        w = self.baseline()
        w.write_settings(w.settings_body(w.entry(form="shell")))
        self.assert_defers(w, "shell form ${CLAUDE_PROJECT_DIR}")

    def test_d2_shell_form_without_braces_defers(self):
        w = self.baseline()
        w.write_settings(w.settings_body(w.entry("$CLAUDE_PROJECT_DIR/.claude/hooks/" + self.SPEC.file_name,
                                                 form="shell")))
        self.assert_defers(w, "shell form $CLAUDE_PROJECT_DIR")

    def test_d2_an_absolute_path_with_other_slashes_and_letter_case_defers(self):
        w = self.baseline()
        absolute = str(w.project_hooks / self.SPEC.file_name)
        folded = absolute.replace("/", "\\").upper() if os.name == "nt" else absolute
        w.write_settings(w.settings_body(w.entry(folded)))
        self.assert_defers(w, "absolute path, slashes and case folded")

    def test_matcher_forms_that_cover_the_tool_defer(self):
        for matcher in ("Bash", "Bash|PowerShell", "", "*", ".*"):
            with self.subTest(matcher=matcher):
                w = self.baseline()
                w.write_settings(w.settings_body(matcher=matcher))
                self.assert_defers(w, "matcher %r" % matcher, payload=self.SPEC.payload("Bash", str(w.project)))

    # ===================================================================
    # D3 .. D6, D10 .. D12 -- registrations that do NOT count
    # ===================================================================
    def test_d3_a_bash_only_registration_with_a_powershell_payload_acts(self):
        def mutate(w):
            w.write_settings(w.settings_body(matcher="Bash"))
        w = self.baseline()
        self.assert_defers(w, "Bash row, Bash payload")
        w.clear_log()
        mutate(w)
        self.assert_acts(w, "D3 PowerShell payload against a Bash-only row",
                         payload=self.SPEC.payload("PowerShell", str(w.project)))

    def test_d4_a_registration_of_a_missing_file_acts(self):
        self.mutate_and_expect_act("D4 registered file missing",
                                   lambda w: (w.project_hooks / self.SPEC.file_name).unlink())

    def test_d5_settings_absent_acts(self):
        self.mutate_and_expect_act("D5 settings.json absent", lambda w: w.settings_path.unlink())

    def test_d5_settings_unparseable_acts(self):
        self.mutate_and_expect_act("D5 settings.json unparseable",
                                   lambda w: w.write_settings("{ this is : not json"))

    def test_d6_no_project_dir_acts(self):
        w = self.baseline()
        self.assert_defers(w, "project dir set")
        w.clear_log()
        proc = w.run_guard(project=False)
        self.assertEqual(proc.returncode, 2, "D6: with CLAUDE_PROJECT_DIR unset there is no project registration "
                         "to defer to, so the guard acts. stderr: " + proc.stderr.decode("utf-8", "replace")[:300])
        self.assertEqual(w.deferred_records(), [], "D6: an acting guard writes no deferral")

    def test_d10_a_matcher_that_does_not_cover_the_tool_acts(self):
        for matcher in ("Edit|Write", "Read"):
            with self.subTest(matcher=matcher):
                self.mutate_and_expect_act("D10 matcher %r" % matcher,
                                           lambda w, m=matcher: w.write_settings(w.settings_body(matcher=m)))

    def test_d10_a_partial_matcher_acts_because_the_match_is_on_the_whole_tool_name(self):
        self.mutate_and_expect_act("D10 partial matcher 'Bas'",
                                   lambda w: w.write_settings(w.settings_body(matcher="Bas")))

    def test_d11_a_posttooluse_only_registration_acts(self):
        self.mutate_and_expect_act("D11 PostToolUse-only registration",
                                   lambda w: w.write_settings(w.settings_body(event="PostToolUse")))

    def test_d12_disable_all_hooks_in_settings_acts(self):
        self.mutate_and_expect_act(
            "D12 disableAllHooks in settings.json",
            lambda w: w.write_settings(w.settings_body(extra={"disableAllHooks": True})))

    def test_d12_disable_all_hooks_in_local_settings_acts(self):
        self.mutate_and_expect_act(
            "D12 disableAllHooks in settings.local.json",
            lambda w: w.write_settings({"disableAllHooks": True}, w.local_settings_path))

    # ===================================================================
    # D7 -- the project's own copy
    # ===================================================================
    def test_d7_the_projects_own_copy_acts_and_never_defers_to_itself(self):
        w = self.baseline()
        self.assert_defers(w, "plugin copy")
        w.clear_log()
        for src in w.plugin_hooks.iterdir():       # make the project's registered file a full working copy
            if src.is_file() and src.name != "hooks.json":
                shutil.copy2(src, w.project_hooks / src.name)
        self.assert_acts(w, "D7 the project's own copy (I-D1)", script=w.project_hooks / self.SPEC.file_name)

    # ===================================================================
    # D8 / D9 -- the helper is missing, stale or raises
    # ===================================================================
    def test_d8_a_missing_helper_acts(self):
        self.mutate_and_expect_act("D8 _project_paths.py missing", lambda w: w.helper_path().unlink())

    def test_d8_a_stale_helper_without_the_deference_function_acts(self):
        def mutate(w):
            names = w.deference_function_names()
            self.assertTrue(names, "the helper must define a top-level function whose name contains 'defer' "
                                   "(the deference helper); none found, so the stale-helper row cannot be built")
            with w.helper_path().open("a", encoding="utf-8") as fh:
                fh.write("\n" + "".join("del %s\n" % n for n in names))
        self.mutate_and_expect_act("D8 stale helper", mutate)

    def test_d9_a_helper_that_raises_acts(self):
        def mutate(w):
            names = w.deference_function_names()
            self.assertTrue(names, "the helper must define a top-level function whose name contains 'defer' "
                                   "(the deference helper); none found, so the raising-helper row cannot be built")
            with w.helper_path().open("a", encoding="utf-8") as fh:
                fh.write("\n\ndef _fixture_raises(*a, **k):\n    raise RuntimeError('fixture: the helper raised')\n")
                fh.write("".join("%s = _fixture_raises\n" % n for n in names))
        self.mutate_and_expect_act("D9 helper raises", mutate)

    # ===================================================================
    # D13, D14, D19 -- a row that cannot block
    # ===================================================================
    def test_d13_an_async_registration_acts(self):
        self.mutate_and_expect_act("D13 async true",
                                   lambda w: w.write_settings(w.settings_body(w.entry(async_=True))))

    def test_d13_async_false_still_defers(self):
        w = self.baseline()
        w.write_settings(w.settings_body(w.entry(async_=False)))
        self.assert_defers(w, "async false")

    def test_d14_a_project_timeout_below_the_plugins_acts(self):
        w = self.baseline(plugin_timeout=60)
        w.write_settings(w.settings_body(w.entry(timeout=60)))
        self.assert_defers(w, "equal timeouts")
        w.clear_log()
        w.write_settings(w.settings_body(w.entry(timeout=120)))
        self.assert_defers(w, "project timeout above the plugin's")
        w.clear_log()
        w.write_settings(w.settings_body(w.entry(timeout=10)))
        self.assert_acts(w, "D14 project timeout 10 below the plugin's 60")

    def test_d14_a_tiny_project_timeout_against_an_unset_plugin_timeout_acts(self):
        # An unset plugin timeout is read as Claude Code's default hook timeout, which is far above 1.
        self.mutate_and_expect_act("D14 project timeout 1, plugin unset",
                                   lambda w: w.write_settings(w.settings_body(w.entry(timeout=1))))

    def test_d19_a_project_timeout_left_unset_while_the_plugins_is_above_the_default_acts(self):
        w = self.baseline(plugin_timeout=100000)
        w.write_settings(w.settings_body(w.entry(timeout=100000)))
        self.assert_defers(w, "both set to the same large value")
        w.clear_log()
        w.write_settings(w.settings_body(w.entry()))      # project timeout unset
        self.assert_acts(w, "D19 project unset, plugin 100000 above the default")

    def test_d19_the_plugin_timeout_is_the_largest_among_the_groups_whose_matcher_covers_the_tool(self):
        # Decision 3. The real hooks.json registers db-destructive-guard.py in three groups. The rule: take
        # the registrations whose matcher covers the payload's tool, then the largest timeout among them.
        groups = [("Edit|Write|MultiEdit", 900), ("Bash", 30), ("Bash|PowerShell", 100), ("PowerShell", 200)]
        w = self.baseline(plugin_timeout=groups)       # a Bash payload: covering groups carry 30 and 100
        w.write_settings(w.settings_body(w.entry(timeout=100)))
        self.assert_defers(w, "project timeout equals the largest covering plugin timeout (100)")
        w.clear_log()
        w.write_settings(w.settings_body(w.entry(timeout=60)))
        self.assert_acts(w, "D19 project timeout 60 is above the smallest covering plugin timeout (30) "
                            "but below the largest (100)")

    def test_d19_a_group_that_does_not_cover_the_tool_adds_nothing_to_the_plugin_timeout(self):
        groups = [("Bash", 30), ("PowerShell", 500)]
        w = self.baseline(plugin_timeout=groups)       # a Bash payload: only the 30 counts
        w.write_settings(w.settings_body(w.entry(timeout=40)))
        self.assert_defers(w, "project timeout 40 covers the only covering plugin group (30); the 500 is PowerShell's")

    def test_d19_a_covering_group_with_no_timeout_counts_as_the_default_of_sixty(self):
        groups = [("Bash", None), ("Bash|PowerShell", 30)]
        w = self.baseline(plugin_timeout=groups)       # unset reads as 60, so 60 is the largest
        w.write_settings(w.settings_body(w.entry(timeout=60)))
        self.assert_defers(w, "project timeout 60 equals the unset group's default")
        w.clear_log()
        w.write_settings(w.settings_body(w.entry(timeout=45)))
        self.assert_acts(w, "D19 project timeout 45 is below the unset group's default of 60")

    # ===================================================================
    # D15 -- a launched path that only contains or ends with the guard path
    # ===================================================================
    def test_d15_a_path_that_only_resembles_the_guard_path_acts(self):
        name = self.SPEC.file_name
        lookalikes = {
            "backup suffix": "${CLAUDE_PROJECT_DIR}/.claude/hooks/%s.bak" % name,
            "another folder ending in the same relative path": "${CLAUDE_PROJECT_DIR}/other/.claude/hooks/%s" % name,
            "same folder, longer file name": "${CLAUDE_PROJECT_DIR}/.claude/hooks/old-%s" % name,
        }
        for label, launched in lookalikes.items():
            with self.subTest(label=label):
                def mutate(w, launched=launched):
                    target = Path(launched.replace("${CLAUDE_PROJECT_DIR}", str(w.project)))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("# a look-alike that exists on disk\n", encoding="utf-8")
                    w.write_settings(w.settings_body(w.entry(launched)))
                self.mutate_and_expect_act("D15 " + label, mutate)

    # ===================================================================
    # D16 -- a git worktree whose own settings lack the row
    # ===================================================================
    def _git_worktree(self, w: World, with_row: bool) -> Path:
        tree = w.tmp / "wt"
        (tree / "sub").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(tree)], check=True, capture_output=True, timeout=60)
        body = w.settings_body() if with_row else {"hooks": {}}
        w.write_settings(body, tree / ".claude" / "settings.json")
        return tree

    def test_d16_a_payload_cwd_in_a_worktree_whose_settings_lack_the_row_acts(self):
        w = self.baseline()
        tree = self._git_worktree(w, with_row=True)
        payload = self.SPEC.payload(cwd=str(tree / "sub"))
        self.assert_defers(w, "worktree settings carry the row too", payload=payload)
        w.clear_log()
        w.write_settings({"hooks": {}}, tree / ".claude" / "settings.json")
        self.assert_acts(w, "D16 worktree settings lack the row while the project dir's has it", payload=payload)

    # ===================================================================
    # D17 -- the session-start marker, condition (h)
    # ===================================================================
    def test_d17_a_settings_file_modified_after_the_markers_time_acts(self):
        w = self.baseline()
        self.assert_defers(w, "settings older than the marker")
        w.clear_log()
        marker = w.marker_value()
        os.utime(w.settings_path, (marker + 60, marker + 60))
        self.assert_acts(w, "D17 settings modified after the session started")

    def test_d17_a_settings_file_modified_less_than_two_seconds_before_the_marker_acts(self):
        w = self.baseline()
        marker = w.marker_value()
        os.utime(w.settings_path, (marker - 2.5, marker - 2.5))
        self.assert_defers(w, "settings 2.5 seconds before the marker (boundary control)")
        w.clear_log()
        os.utime(w.settings_path, (marker - 1.0, marker - 1.0))
        self.assert_acts(w, "D17 settings modified 1 second before the session started")

    def test_d17_no_marker_for_the_payloads_session_id_acts(self):
        def mutate(w):
            for f in w.marker_files():
                f.unlink()
        self.mutate_and_expect_act("D17 no marker file", mutate)

    def test_d17_a_payload_without_a_session_id_acts(self):
        w = self.baseline()
        self.assert_defers(w, "session id present")
        w.clear_log()
        self.assert_acts(w, "D17 payload with no session_id",
                         payload=self.SPEC.payload(cwd=str(w.project), session=None))

    def test_d17_a_marker_for_another_session_does_not_count(self):
        w = self.baseline()
        self.assert_defers(w, "own session marker")
        w.clear_log()
        self.assert_acts(w, "D17 payload from a different session",
                         payload=self.SPEC.payload(cwd=str(w.project), session="sess-9999-other"))

    def test_d17_a_non_numeric_marker_acts(self):
        self.mutate_and_expect_act("D17 non-numeric marker", lambda w: w.rewrite_marker("not-a-number"))

    def test_d17_an_empty_marker_acts(self):
        self.mutate_and_expect_act("D17 empty marker", lambda w: w.rewrite_marker(""))

    # ===================================================================
    # D18 -- the marker writer, through both real modules
    # ===================================================================
    def test_d18_startup_writes_the_marker_and_the_reader_accepts_it(self):
        self._round_trip("startup")

    def test_d18_resume_writes_the_marker_and_the_reader_accepts_it(self):
        self._round_trip("resume")

    def _round_trip(self, source: str) -> None:
        w = self.world()
        w.register()
        self.assertEqual(w.marker_files(), [], "fixture: no marker before the session starts")
        proc = w.start_session(source)
        self.assertEqual(proc.returncode, 0, "the session-start hook exits 0")
        self.assertEqual(len(w.marker_files()), 1,
                         "D18: SessionStart with source=%s must write ONE marker file named %s<session_id> in "
                         "the system temporary folder (decision 2). Files there: %r"
                         % (source, MARKER_PREFIX, [p.name for p in w.temp_dir.iterdir()]))
        self.assertAlmostEqual(w.marker_value(), time.time(), delta=60,
                               msg="the marker holds the current time as a number")
        self.assert_defers(w, "round trip after source=%s" % source)

    def test_d18_a_baseline_file_for_the_same_session_is_never_read_as_the_marker(self):
        # Block 17's baseline is named by the same session id under another prefix (decision 2). Plant one
        # holding a number far in the past: a guard that picked it up as the marker would see the settings
        # file as modified after the session started and would act instead of deferring.
        w = self.baseline()
        (w.temp_dir / (BASELINE_PREFIX + SESSION_ID)).write_text("1", encoding="utf-8")
        self.assertEqual(len(w.marker_files()), 1, "fixture: the real marker is still the only marker")
        self.assert_defers(w, "a decoy baseline file named by the same session id sits beside the marker")

    def test_d18_a_baseline_file_alone_is_not_a_marker_so_the_guard_acts(self):
        w = self.world()
        w.register()
        (w.temp_dir / (BASELINE_PREFIX + SESSION_ID)).write_text(str(int(time.time())), encoding="utf-8")
        self.assert_acts(w, "D18 only a baseline file exists for the session, no session-start marker")

    def test_d18_clear_and_compact_write_no_marker_so_the_guard_acts(self):
        for source in ("clear", "compact", ""):
            with self.subTest(source=source):
                w = self.world()
                w.register()
                w.start_session("startup")                   # a marker exists from the earlier start ...
                self.assert_defers(w, "after a startup")
                for f in w.marker_files():
                    f.unlink()
                w.clear_log()
                proc = w.start_session(source)               # ... then this start must NOT write one
                self.assertEqual(proc.returncode, 0)
                self.assertEqual(w.marker_files(), [],
                                 "D18: a session started by %r writes no marker" % source)
                self.assert_acts(w, "D18 session started by %r" % source)

    def test_d18_the_writer_adds_no_output_beyond_the_agreements_envelope(self):
        # The marker write must not change what working-agreements.py prints. Compare a startup run with
        # a clear run: the printed envelope is identical, so the marker adds no output.
        w = self.world()
        w.register()
        started = w.start_session("startup")
        for f in w.marker_files():
            f.unlink()
        cleared = w.start_session("clear")
        self.assertEqual(started.stdout, cleared.stdout,
                         "the marker write adds no output: stdout is the same with and without it")


    # ===================================================================
    # Review round one -- a row that names the guard file but may not run, or cannot block
    # ===================================================================
    def test_a_row_with_a_key_outside_the_known_set_acts(self):
        # A per-row `if` condition (or any key this code does not know) means the row may not run on every call.
        def mutate(w):
            row = w.entry()
            row["if"] = "Bash(sqlcmd *)"
            w.write_settings(w.settings_body(row))
        self.mutate_and_expect_act("review: the row carries an `if` key", mutate)

    def test_the_known_row_keys_still_defer(self):
        w = self.baseline()
        row = w.entry(timeout=120, async_=False)
        row["statusMessage"] = "checking"
        row["shell"] = "bash"
        w.write_settings(w.settings_body(row))
        self.assert_defers(w, "type, command, args, timeout, async, statusMessage and shell are all known keys")

    def test_a_shell_form_row_holding_a_shell_operator_acts(self):
        for label, tail in (("or-true", " || true"), ("exit zero", " ; exit 0"), ("pipe", " | cat"),
                            ("redirect out", " > out.txt"), ("redirect in", " < in.txt"),
                            ("background", " &"), ("backtick", " `true`")):
            with self.subTest(operator=label):
                def mutate(w, tail=tail):
                    row = {"type": "command", "command": 'py -3 "%s"%s' % (w.registered_path, tail)}
                    w.write_settings(w.settings_body(row))
                self.mutate_and_expect_act("review: shell form with %s" % label, mutate)

    def test_an_exec_form_row_whose_command_is_not_a_python_launcher_acts(self):
        def mutate(w):
            row = {"type": "command", "command": "echo", "args": [w.registered_path]}
            w.write_settings(w.settings_body(row))
        self.mutate_and_expect_act("review: exec form launched by echo", mutate)

    def test_known_python_launchers_still_defer(self):
        for launcher in ("py", "py.exe", "python", "python3", "python3.exe", "PY"):
            with self.subTest(launcher=launcher):
                w = self.baseline()
                row = {"type": "command", "command": launcher, "args": ["-3", w.registered_path]}
                w.write_settings(w.settings_body(row))
                self.assert_defers(w, "launcher %s" % launcher)

    # ===================================================================
    # Revision 9 (block 28, section N) -- a Project hook launcher row
    #
    # A row `py -3 -c <launcher source> <class> <script>` runs the project's guard through the launcher.
    # Condition (d) counts it as the project's registration ONLY when all three hold: the program text is
    # byte-equal to the installed reader's own launcher constant, the class is exactly 'block', and the
    # script is a bare .py name equal to the guard file. Anything else fails (d), so the plugin copy acts:
    # the failure direction is always "the guard runs twice", never "no guard runs" (I-D3).
    # Every row below is a control-then-mutation pair, like the rows above, so each is RED today for the
    # control's reason: today the launched script of such a row is the program text, never the guard file.
    # ===================================================================
    def launcher_text(self) -> str:
        return launcher_source_or_fail(self)

    def launcher_entry(self, w: World, *, hook_class: str = "block", script: str | None = None,
                       text: str | None = None, command: str = "py") -> dict:
        args = ["-c", text if text is not None else self.launcher_text(), hook_class,
                script if script is not None else self.SPEC.file_name]
        if command.lower().startswith("py"):
            args.insert(0, "-3")
        return {"type": "command", "command": command, "args": args}

    def launcher_world(self, **entry_kwargs) -> World:
        w = self.world()
        w.write_settings(w.settings_body(self.launcher_entry(w, **entry_kwargs)))
        started = w.start_session("startup")
        self.assertEqual(started.returncode, 0, "the session-start hook must exit 0")
        return w

    def launcher_mutation(self, why: str, mutate, **entry_kwargs) -> World:
        w = self.launcher_world(**entry_kwargs)
        self.assert_defers(w, "CONTROL for %s: a block-class launcher row with the constant's text" % why)
        w.clear_log()
        mutate(w)
        self.assert_acts(w, why)
        return w

    def test_r9_the_launcher_source_constant_exists(self):
        self.assertIsNotNone(_load_launcher_constant(),
                             "_project_paths.py must define the launcher source as a non-empty string constant named "
                             "%s (Revision 9, L3); it defines none today" % LAUNCHER_CONSTANT)

    def test_r9_a_block_class_launcher_row_defers_for_each_tool_the_guard_is_registered_for(self):
        for tool in ("Bash", "PowerShell"):
            with self.subTest(tool=tool):
                w = self.launcher_world()
                self.assert_defers(w, "launcher row, %s payload" % tool, payload=self.SPEC.payload(tool, str(w.project)))

    def test_r9_a_python3_launcher_row_without_the_dash_3_defers(self):
        w = self.launcher_world(command="python3")
        self.assert_defers(w, "python3 launcher row")

    def test_r9_a_launcher_row_whose_class_is_warn_acts(self):
        # A warn row would not block on a missing script, so it cannot stand for the project's guard.
        self.launcher_mutation("r9 class warn", lambda w: w.write_settings(
            w.settings_body(self.launcher_entry(w, hook_class="warn"))))

    def test_r9_a_launcher_row_whose_class_is_spelled_block_with_other_case_or_spaces_acts(self):
        for spelling in ("Block", " block", "block ", "BLOCK"):
            with self.subTest(spelling=repr(spelling)):
                self.launcher_mutation("r9 class %r" % spelling, lambda w, s=spelling: w.write_settings(
                    w.settings_body(self.launcher_entry(w, hook_class=s))))

    def test_r9_a_launcher_row_that_names_the_other_guard_acts(self):
        other = READONLY if self.SPEC is DESTRUCTIVE else DESTRUCTIVE

        def mutate(w):
            (w.project_hooks / other.file_name).write_text("# the other guard exists on disk\n", encoding="utf-8")
            w.write_settings(w.settings_body(self.launcher_entry(w, script=other.file_name)))
        self.launcher_mutation("r9 the row launches the other guard", mutate)

    def test_r9_a_launcher_row_whose_text_differs_from_the_constant_by_one_byte_acts(self):
        text = self.launcher_text()
        changed = text[:-1] + chr(ord(text[-1]) ^ 1)
        self.assertNotEqual(changed, text, "fixture: one byte changed")
        self.launcher_mutation("r9 text differs by one byte", lambda w: w.write_settings(
            w.settings_body(self.launcher_entry(w, text=changed))))

    def test_r9_a_launcher_row_with_an_earlier_or_later_marker_version_acts(self):
        text = self.launcher_text()
        self.assertIn("project-hook-launch v1", text.splitlines()[0], "fixture: the constant carries marker v1")
        for version in ("v0", "v2"):
            with self.subTest(marker=version):
                other = text.replace("project-hook-launch v1", "project-hook-launch " + version, 1)
                self.assertNotEqual(other, text, "fixture: the marker changed")
                self.launcher_mutation("r9 marker %s" % version, lambda w, t=other: w.write_settings(
                    w.settings_body(self.launcher_entry(w, text=t))))

    def test_r9_with_the_project_file_missing_condition_e_fails_and_the_copy_acts(self):
        self.launcher_mutation("r9 the launched project file is missing",
                               lambda w: (w.project_hooks / self.SPEC.file_name).unlink())

    def test_r9_a_launcher_row_with_a_script_that_only_resembles_the_guard_acts(self):
        for label, script in (("backup suffix", self.SPEC.file_name + ".bak"),
                              ("longer name", "old-" + self.SPEC.file_name),
                              ("folder separator", "sub/" + self.SPEC.file_name)):
            with self.subTest(label=label):
                def mutate(w, script=script):
                    target = w.project_hooks / script
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text("# a look-alike that exists on disk\n", encoding="utf-8")
                    w.write_settings(w.settings_body(self.launcher_entry(w, script=script)))
                self.launcher_mutation("r9 look-alike script %s" % label, mutate)

    def _launcher_worktree(self, w: World, with_row: bool) -> Path:
        tree = w.tmp / "wt"
        (tree / "sub").mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(tree)], check=True, capture_output=True, timeout=60)
        body = w.settings_body(self.launcher_entry(w)) if with_row else {"hooks": {}}
        w.write_settings(body, tree / ".claude" / "settings.json")
        return tree

    def test_r9_a_launcher_row_in_a_worktree_settings_file_follows_condition_c(self):
        w = self.launcher_world()
        tree = self._launcher_worktree(w, with_row=True)
        payload = self.SPEC.payload(cwd=str(tree / "sub"))
        self.assert_defers(w, "r9 the worktree's settings carry the launcher row too", payload=payload)
        w.clear_log()
        w.write_settings({"hooks": {}}, tree / ".claude" / "settings.json")
        self.assert_acts(w, "r9 the worktree's settings lack the row while the project dir's has it", payload=payload)


class DestructiveGuardDeferenceTests(DeferenceRows, unittest.TestCase):
    """The rows for db-destructive-guard.py."""
    SPEC = DESTRUCTIVE


class ReadonlyGuardDeferenceTests(DeferenceRows, unittest.TestCase):
    """The rows for db-research-readonly-guard.py. It only handles Bash and PowerShell."""
    SPEC = READONLY


if __name__ == "__main__":
    unittest.main(verbosity=2)
