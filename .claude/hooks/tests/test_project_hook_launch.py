#!/usr/bin/env python3
"""
test_project_hook_launch.py -- the Project hook launcher (contract
2026-10-12-dedupe-claude-config, Revision 9, sections K to O, block 28 cases (a) to (i)).

WHAT THE LAUNCHER IS
--------------------
A project's settings row runs ``py -3 -c <launcher source> <class> <script> [extra arguments]``. The
source is one small standard-library program kept as ONE constant in this folder's ``_project_paths.py``
(the row writer writes it, the deference reader compares to it). It finds ``<script>`` in the project's
``.claude/hooks`` folder, falls back to the main checkout when that folder was removed, and runs the
script inside its own interpreter with ``runpy``. A missing script exits 2 for class ``block`` and 1 for
class ``warn``, never CPython's own "can't open file" exit 2 on an event that must not block.

HOW THIS FILE FINDS THE CODE UNDER TEST
---------------------------------------
The launcher source is read from ``_project_paths.py`` in the hooks folder beside this tests folder, by
loading that file under a private module name. The constant is expected under the name
``PROJECT_HOOK_LAUNCHER_SOURCE`` (the row builder ``project_hook_launcher_row`` is used by one case).
Every case first asserts that the constant exists, so a missing constant is an ASSERTION failure with a
named reason, never an import error. The file reads nothing else outside its own fixtures, so it can be
vendored unchanged into a repository that holds the same ``_project_paths.py``.

THE PROBE HOOK
--------------
Each case builds a throwaway ``.claude/hooks`` folder holding a probe. The probe writes a JSON record
(its arguments after its own name, a hash of the stdin bytes, the working folder, ``sys.path[0]``,
``__file__``, ``CLAUDE_PROJECT_DIR``, the ``sys.modules`` names present at start, ``sys.orig_argv`` and the
``__main__`` module's file), prints known stdout and stderr text, and exits with the code its payload
chooses (``exit=N`` on the payload's first line; ``exit=raise`` raises an exception after the record).

ENVIRONMENT
-----------
Every child starts from a copy of the runner's environment with ``CLAUDE_PROJECT_DIR`` and every other
``CLAUDE_*`` variable removed, then sets only what the case names (journal 2026-09-29).

CASE (h), WHY THERE IS NO ROW
-----------------------------
Step 7 is the launcher's own failure in steps 1 to 5. Those steps only split arguments, test files with
``os.path.isfile`` (which swallows every OS error) and build strings, so no input a test can set from
outside (an argument, an environment variable, a file) makes them raise. Reaching step 7 would need the
source edited, which this file must not do. The behaviour is covered by the source-text row (g) and by
parity case (a) for the target's own exceptions (step 6).

Run: py -3 .claude/hooks/tests/test_project_hook_launch.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
PROJECT_PATHS = HOOKS_DIR / "_project_paths.py"
CONSTANT = "PROJECT_HOOK_LAUNCHER_SOURCE"
BUILDER = "project_hook_launcher_row"
MARKER_LINE = "# agentic-auto-improve project-hook-launch v1"
RUN_TIMEOUT = 90

#: Module names a project's hooks folder holds. The launcher must never have imported one of them.
COLLIDING = ("_project_paths", "_memory_common", "_error_log", "_gate_launch", "_main_checkout_guard")
_DRIVE_LETTER_RE = re.compile(r"[A-Za-z]:[\\/]")  # this repository's decoded-string scan rule (INV-X1)

PROBE = r'''
import sys
_modules_at_start = sorted(sys.modules)
_path0 = sys.path[0] if sys.path else None
import hashlib, json, os
_raw = sys.stdin.buffer.read()
_first = _raw.split(b"\n", 1)[0].decode("ascii", "replace")
try:
    import _project_paths as _fixture
    _marker = getattr(_fixture, "FIXTURE_MARKER", "imported-without-marker")
except Exception as _exc:
    _marker = "no-import: " + type(_exc).__name__
_main = sys.modules.get("__main__")
_record = {
    "argv0": sys.argv[0],
    "argv": sys.argv[1:],
    "stdin_sha256": hashlib.sha256(_raw).hexdigest(),
    "stdin_length": len(_raw),
    "cwd": os.getcwd(),
    "path0": _path0,
    "file": globals().get("__file__"),
    "name": __name__,
    "project_dir": os.environ.get("CLAUDE_PROJECT_DIR"),
    "modules": _modules_at_start,
    "orig_argv": list(getattr(sys, "orig_argv", [])),
    "main_file": getattr(_main, "__file__", None),
    "fixture_marker": _marker,
}
with open(os.environ["PROBE_RECORD"], "w", encoding="utf-8") as _fh:
    json.dump(_record, _fh, sort_keys=True)
sys.stdout.write("probe-stdout-line\n")
sys.stdout.flush()
sys.stderr.write("probe-stderr-line\n")
sys.stderr.flush()
if _first == "exit=raise":
    raise RuntimeError("boom-from-probe")
sys.exit(int(_first.split("=", 1)[1]))
'''

#: Fields that legitimately differ between a launcher run and a direct run (the exceptions to L8).
_EXEMPT_FIELDS = ("modules", "orig_argv")
_PATH_FIELDS = ("argv0", "cwd", "path0", "file", "project_dir", "main_file")


def _rmtree(path: Path) -> None:
    def _onerror(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, onerror=_onerror)


def _interpreter() -> list:
    """``py -3`` where the Windows launcher exists, ``python3`` elsewhere."""
    py = shutil.which("py")
    if py:
        return [py, "-3"]
    return [shutil.which("python3") or sys.executable]


def _clean_env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("CLAUDE_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update({k: v for k, v in extra.items() if v is not None})
    return env


def _load_constants() -> tuple:
    """(module or None, why not). Loads _project_paths.py under a private name; never raises."""
    if not PROJECT_PATHS.is_file():
        return None, "%s does not exist" % PROJECT_PATHS
    try:
        spec = importlib.util.spec_from_file_location("_t28_project_paths_under_test", str(PROJECT_PATHS))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
    except Exception as exc:  # the helper being unreadable is a finding, reported as one
        return None, "_project_paths.py could not be loaded: %s: %s" % (type(exc).__name__, exc)
    return module, ""


def _norm(text) -> str:
    return os.path.normcase(os.path.normpath(text)) if isinstance(text, str) else text


def _decoded_strings(value):
    """Every string inside a decoded JSON value (the rule block 34 gives this repository's scan)."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _decoded_strings(k)
            yield from _decoded_strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _decoded_strings(v)


def decoded_drive_letter_scan(json_text: str) -> list:
    """Drive-letter paths and 'Users' found after decoding each string of a JSON document."""
    hits = []
    for s in _decoded_strings(json.loads(json_text)):
        hits += _DRIVE_LETTER_RE.findall(s)
        if "Users" in s:
            hits.append("Users")
    return hits


class Result:
    def __init__(self, proc: subprocess.CompletedProcess, record_path: Path):
        self.returncode = proc.returncode
        self.stdout = proc.stdout
        self.stderr = proc.stderr
        self.record_path = record_path

    @property
    def record(self):
        if not self.record_path.is_file():
            return None
        return json.loads(self.record_path.read_text(encoding="utf-8"))

    def stderr_text(self) -> str:
        return self.stderr.decode("utf-8", "replace")

    def last_traceback_line(self) -> str:
        lines = [ln for ln in self.stderr_text().splitlines() if ln.strip()]
        return lines[-1] if lines else ""


class LauncherCase(unittest.TestCase):
    """Shared plumbing. Each test builds its own fixtures under one throwaway root."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="hook-launch-")).resolve()
        self.addCleanup(_rmtree, self.root)
        self._count = 0

    # ----------------------------------------------------------------- the code under test
    def source(self) -> str:
        module, why = _load_constants()
        if module is None:
            self.fail("the launcher source cannot be read: " + why)
        value = getattr(module, CONSTANT, None)
        self.assertIsInstance(
            value, str,
            "_project_paths.py must define the launcher source as a string constant named %s "
            "(contract Revision 9, L3); it defines none today" % CONSTANT)
        self.assertTrue(value.strip(), "%s must not be empty" % CONSTANT)
        return value

    # ---------------------------------------------------------------------- fixtures
    def new_dir(self, *parts) -> Path:
        path = self.root.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def checkout(self, name: str = "checkout", script: str = "probe.py", extra_files=None) -> Path:
        """A temporary main checkout whose .claude/hooks holds the probe under ``script``."""
        main = self.new_dir(name)
        hooks = main / ".claude" / "hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        (hooks / script).write_text(PROBE, encoding="utf-8")
        for rel, text in (extra_files or {}).items():
            (hooks / rel).write_text(text, encoding="utf-8")
        return main

    def record_file(self) -> Path:
        self._count += 1
        return self.root / ("record-%d.json" % self._count)

    @staticmethod
    def payload(code="0", body: str = "hello\n", raw_body: bytes = None) -> bytes:
        head = ("exit=%s\n" % code).encode("ascii")
        return head + (raw_body if raw_body is not None else body.encode("utf-8"))

    def launch(self, hook_class: str, script: str, *extras, cwd: Path, project_dir=None, stdin: bytes = None,
               source: str = None) -> Result:
        record = self.record_file()
        env = _clean_env(PROBE_RECORD=str(record), CLAUDE_PROJECT_DIR=project_dir)
        argv = _interpreter() + ["-c", source if source is not None else self.source(), hook_class, script,
                                 *extras]
        proc = subprocess.run(argv, input=stdin if stdin is not None else self.payload(), capture_output=True,
                              env=env, cwd=str(cwd), timeout=RUN_TIMEOUT)
        return Result(proc, record)

    def direct(self, target: Path, *extras, cwd: Path, project_dir=None, stdin: bytes = None) -> Result:
        record = self.record_file()
        env = _clean_env(PROBE_RECORD=str(record), CLAUDE_PROJECT_DIR=project_dir)
        argv = _interpreter() + [str(target), *extras]
        proc = subprocess.run(argv, input=stdin if stdin is not None else self.payload(), capture_output=True,
                              env=env, cwd=str(cwd), timeout=RUN_TIMEOUT)
        return Result(proc, record)

    # --------------------------------------------------------------------- assertions
    def assert_same_run(self, launched: Result, direct: Result, why: str, normalize_paths: bool = True):
        self.assertEqual(launched.returncode, direct.returncode, why + ": exit codes differ")
        self.assertEqual(launched.stdout, direct.stdout, why + ": stdout differs")
        self.assertEqual(launched.stderr, direct.stderr, why + ": stderr differs")
        got, want = launched.record, direct.record
        self.assertIsNotNone(want, why + ": fixture fault, the direct run wrote no record")
        self.assertIsNotNone(got, why + ": the launcher run wrote no record (the hook did not run)")
        for field in sorted(set(got) | set(want)):
            if field in _EXEMPT_FIELDS:
                continue
            a, b = got.get(field), want.get(field)
            if normalize_paths and field in _PATH_FIELDS:
                a, b = _norm(a), _norm(b)
            self.assertEqual(a, b, "%s: record field %r differs between the launcher run and a direct run"
                             % (why, field))


class ParityTests(LauncherCase):
    """(a) L8: what the hook sees and produces is what a direct run of the same file sees and produces."""

    def _project(self) -> Path:
        project = self.checkout("project")
        (project / "sub" / "deeper").mkdir(parents=True)
        return project

    def test_a_exit_codes_0_2_3_match_a_direct_run_from_root_and_subfolder_for_three_payload_kinds(self):
        project = self._project()
        target = project / ".claude" / "hooks" / "probe.py"
        kinds = {
            "ascii": lambda code: self.payload(code, "hello\n"),
            "non-ASCII UTF-8": lambda code: self.payload(code, "h\u00e9llo \u2014 \u65e5\u672c\u8a9e \u2713\n"),
            "bytes that are not UTF-8": lambda code: self.payload(code, raw_body=b"\xff\xfe\x80 bad \xc3\x28\n"),
        }
        for code in ("0", "2", "3"):
            for label, make in kinds.items():
                for where, cwd in (("project root", project), ("subfolder", project / "sub" / "deeper")):
                    with self.subTest(exit_code=code, payload=label, cwd=where):
                        stdin = make(code)
                        launched = self.launch("warn", "probe.py", cwd=cwd, project_dir=str(project), stdin=stdin)
                        direct = self.direct(target, cwd=cwd, project_dir=str(project), stdin=stdin)
                        self.assertEqual(direct.returncode, int(code), "fixture fault: the direct run's exit code")
                        self.assert_same_run(launched, direct, "exit %s, %s payload, from the %s" % (code, label, where))
                        self.assertEqual(launched.record["stdin_sha256"], hashlib.sha256(stdin).hexdigest(),
                                         "the hook must read the original stdin bytes unchanged")

    def test_a_an_uncaught_exception_exits_1_with_equal_stdout_and_last_traceback_line(self):
        project = self._project()
        target = project / ".claude" / "hooks" / "probe.py"
        for where, cwd in (("project root", project), ("subfolder", project / "sub" / "deeper")):
            with self.subTest(cwd=where):
                stdin = self.payload("raise")
                launched = self.launch("block", "probe.py", cwd=cwd, project_dir=str(project), stdin=stdin)
                direct = self.direct(target, cwd=cwd, project_dir=str(project), stdin=stdin)
                self.assertEqual(direct.returncode, 1, "fixture fault: a direct run of a raising hook exits 1")
                self.assertEqual(launched.returncode, 1, "an exception from the hook must exit 1 (as a direct run), "
                                 "not the class's missing-script code; stderr: " + launched.stderr_text()[-400:])
                self.assertEqual(launched.stdout, direct.stdout, "stdout must be equal")
                self.assertEqual(launched.last_traceback_line(), direct.last_traceback_line(),
                                 "the exception type and message on the traceback's last line must be equal")
                self.assertEqual(launched.last_traceback_line(), "RuntimeError: boom-from-probe",
                                 "fixture sanity: the last line is the probe's exception")

    def test_a2_project_dir_unset_gives_the_class_exit_code_and_says_the_variable_is_unset(self):
        project = self._project()
        for hook_class, code in (("block", 2), ("warn", 1)):
            with self.subTest(hook_class=hook_class):
                result = self.launch(hook_class, "probe.py", cwd=project, project_dir=None)
                self.assertEqual(result.returncode, code, "no candidate exists, so the class rule applies")
                self.assertIsNone(result.record, "no hook can have run")
                self.assertEqual(result.stdout, b"", "nothing goes to stdout")
                text = result.stderr_text()
                self.assertIn("CLAUDE_PROJECT_DIR", text, "the message names the variable")
                self.assertRegex(text, r"(?i)unset|not set", "and says it is unset")

    def test_a3_a_runpy_or_traceback_in_the_working_folder_never_runs(self):
        project = self._project()
        shadow = self.new_dir("shadow")
        markers = {name: self.root / ("marker-%s.txt" % name) for name in ("runpy", "traceback")}
        for name, marker in markers.items():
            (shadow / (name + ".py")).write_text(
                "open(%r, 'w').write('the working-folder %s ran')\nraise ImportError('shadow')\n" % (str(marker), name),
                encoding="utf-8")
        for label, code, want in (("a passing hook", "0", 0), ("an uncaught exception", "raise", 1)):
            with self.subTest(case=label):
                result = self.launch("warn", "probe.py", cwd=shadow, project_dir=str(project),
                                     stdin=self.payload(code))
                self.assertEqual(result.returncode, want, "the hook's own exit code; stderr: "
                                 + result.stderr_text()[-400:])
                self.assertIsNotNone(result.record, "the hook's own record must be written")
                for name, marker in markers.items():
                    self.assertFalse(marker.exists(), "the working folder's %s.py ran inside the hook (step 0 "
                                                      "must remove the working-folder entry before any import)" % name)


class RemovedFolderTests(LauncherCase):
    """(b) the session's project folder was removed: the main checkout's hook runs instead."""

    def _removed(self, main: Path, tail: str) -> str:
        """A project-folder TEXT under the main checkout that is created and then removed."""
        text = str(main) + "/" + tail
        path = Path(text.replace("\\", "/"))
        path.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(path)
        self.assertFalse(path.exists(), "fixture: the project folder must be gone")
        return text

    def _second_worktree_shaped_folder(self) -> Path:
        return self.new_dir("other-main", ".claude", "worktrees", "second")

    def test_b_the_main_checkouts_hook_runs_and_the_record_equals_a_direct_run(self):
        main = self.checkout("main")
        target = main / ".claude" / "hooks" / "probe.py"
        cwd = self._second_worktree_shaped_folder()
        variants = {
            "one worktree segment": ".claude/worktrees/feature-a",
            "nested worktree segments": ".claude/worktrees/outer/.claude/worktrees/inner",
            "upper-case .Claude/Worktrees": ".Claude/Worktrees/feature-a",
            "backslash separators": ".claude\\worktrees\\feature-a",
        }
        for label, tail in variants.items():
            with self.subTest(variant=label):
                project_dir = self._removed(main, tail) if "\\" not in tail else str(main) + "/" + tail
                launched = self.launch("block", "probe.py", cwd=cwd, project_dir=project_dir)
                direct = self.direct(target, cwd=cwd, project_dir=project_dir)
                self.assertEqual(direct.returncode, 0, "fixture fault: the direct run of the main checkout's probe")
                self.assert_same_run(launched, direct, "fallback to the main checkout (%s)" % label,
                                     normalize_paths=True)
                self.assertEqual(launched.record["project_dir"], project_dir,
                                 "CLAUDE_PROJECT_DIR must keep naming the removed folder (Open Question 8)")
                self.assertEqual(_norm(launched.record["file"]), _norm(str(target)),
                                 "the hook that ran is the main checkout's file")

    def test_b_the_fallback_works_for_the_warn_class_too(self):
        main = self.checkout("main")
        project_dir = self._removed(main, ".claude/worktrees/feature-b")
        result = self.launch("warn", "probe.py", cwd=self._second_worktree_shaped_folder(), project_dir=project_dir)
        self.assertEqual(result.returncode, 0, "the main checkout's probe ran and exited 0")
        self.assertIsNotNone(result.record, "the fallback must run the probe")

    def test_b_a_project_folder_with_no_worktree_segment_has_no_fallback(self):
        main = self.checkout("main")
        project_dir = str(main / "plain-project-folder-that-is-gone")  # no worktree segment, never created
        for hook_class, code in (("block", 2), ("warn", 1)):
            with self.subTest(hook_class=hook_class):
                result = self.launch(hook_class, "probe.py", cwd=main, project_dir=project_dir)
                self.assertEqual(result.returncode, code, "no candidate B exists, so the class rule applies")
                self.assertIsNone(result.record,
                                  "the launcher must not walk up to the parent's hooks folder (limit R3)")
                self.assertIn("probe.py", result.stderr_text(), "the message names the script")

    def test_b_the_project_folders_own_hook_wins_when_it_exists(self):
        main = self.checkout("main")
        project = self.new_dir("main", ".claude", "worktrees", "alive")
        (project / ".claude" / "hooks").mkdir(parents=True)
        (project / ".claude" / "hooks" / "probe.py").write_text(PROBE, encoding="utf-8")
        result = self.launch("block", "probe.py", cwd=project, project_dir=str(project))
        self.assertEqual(result.returncode, 0, "candidate A exists and runs")
        self.assertEqual(_norm(result.record["file"]), _norm(str(project / ".claude" / "hooks" / "probe.py")),
                         "candidate A is preferred over the main checkout's copy")
        self.assertTrue((main / ".claude" / "hooks" / "probe.py").is_file(), "fixture sanity")


class MissingEverywhereTests(LauncherCase):
    """(c) the script exists nowhere: the class decides the exit code and the launcher says why."""

    FIXED_PHRASE = "restart Claude Code from an existing checkout"

    def test_c_block_exits_2_and_warn_exits_1_naming_the_class_the_script_and_every_path_tried(self):
        main = self.new_dir("main")
        (main / ".claude" / "hooks").mkdir(parents=True)  # the folder exists, the script does not
        project_dir = str(main) + "/.claude/worktrees/gone"
        path_a = (project_dir + "/.claude/hooks/ghost-hook.py")
        path_b = (str(main) + "/.claude/hooks/ghost-hook.py")
        for hook_class, code in (("block", 2), ("warn", 1)):
            with self.subTest(hook_class=hook_class):
                result = self.launch(hook_class, "ghost-hook.py", cwd=main, project_dir=project_dir)
                text = result.stderr_text()
                flat = text.replace("\\", "/").casefold()
                self.assertEqual(result.returncode, code, "stderr: " + text[-400:])
                self.assertEqual(result.stdout, b"", "nothing goes to stdout")
                self.assertIn(hook_class, text, "the message names the class")
                self.assertIn("ghost-hook.py", text, "the message names the script")
                self.assertIn(path_a.replace("\\", "/").casefold(), flat, "the message names candidate A")
                self.assertIn(path_b.replace("\\", "/").casefold(), flat, "the message names candidate B")
                # positive control: the launcher's own message, never CPython's failure to open a file
                self.assertIn(self.FIXED_PHRASE.casefold(), flat,
                              "the launcher's fixed recovery phrase must be present")
                self.assertNotIn("can't open file", text, "CPython's own message means the launcher never ran")


class ModuleNameTests(LauncherCase):
    """(d) the launcher imports no module a project's hooks folder also holds."""

    def test_d_the_hook_gets_the_fixtures_project_paths_and_none_of_the_names_were_loaded_at_start(self):
        main = self.checkout("main", extra_files={"_project_paths.py": "FIXTURE_MARKER = 'fixture-copy'\n"})
        result = self.launch("block", "probe.py", cwd=main, project_dir=str(main))
        self.assertEqual(result.returncode, 0, "stderr: " + result.stderr_text()[-400:])
        record = result.record
        self.assertIsNotNone(record, "the hook must run")
        self.assertEqual(record["fixture_marker"], "fixture-copy",
                         "an import of _project_paths made by the hook must find the FIXTURE's copy")
        present = [n for n in COLLIDING if n in record["modules"]]
        self.assertEqual(present, [], "the launcher must not have imported these before the hook started")
        self.assertEqual(_norm(record["path0"]), _norm(str(main / ".claude" / "hooks")),
                         "the target's folder is first on sys.path")


class ArgumentTests(LauncherCase):
    """(e) extra arguments."""

    def test_e_carry_forward_and_ordinary_arguments_arrive_unchanged(self):
        main = self.checkout("main")
        extras = ["--carry-forward", "--on-prompt", "plain value", "sub/other.py", "x.py"]
        result = self.launch("warn", "probe.py", *extras, cwd=main, project_dir=str(main))
        self.assertEqual(result.returncode, 0, "stderr: " + result.stderr_text()[-400:])
        self.assertEqual(result.record["argv"], extras,
                         "for any script but gate-launch.py every argument passes unchanged, a bare .py name included")

    def test_e_for_gate_launch_a_bare_py_argument_becomes_the_target_folders_path(self):
        main = self.checkout("main", script="gate-launch.py")
        hooks = main / ".claude" / "hooks"
        extras = ["concept-gate.py", "--flag", "sub/other.py", "value"]
        result = self.launch("block", "gate-launch.py", *extras, cwd=main, project_dir=str(main))
        self.assertEqual(result.returncode, 0, "stderr: " + result.stderr_text()[-400:])
        argv = result.record["argv"]
        self.assertEqual(len(argv), len(extras), "no argument is added or dropped")
        self.assertEqual(_norm(argv[0]), _norm(str(hooks / "concept-gate.py")),
                         "a bare .py name becomes <target folder>/<name> so the gate's same-folder check holds")
        self.assertEqual(argv[1:], extras[1:], "every other argument is unchanged, a .py path with a folder included")


class UnknownClassTests(LauncherCase):
    """(f) an unknown class or a script with a separator."""

    def test_f_an_unknown_class_exits_1_with_a_message_and_runs_nothing(self):
        main = self.checkout("main")
        for bad in ("Block", " block", "block ", "BLOCK", "", "warning", "2"):
            with self.subTest(hook_class=bad):
                result = self.launch(bad, "probe.py", cwd=main, project_dir=str(main))
                self.assertEqual(result.returncode, 1,
                                 "the launcher cannot know the event, and exit 2 outside PreToolUse is the wedge; "
                                 "stderr: " + result.stderr_text()[-300:])
                self.assertIsNone(result.record, "an unknown class runs no hook")
                self.assertEqual(result.stdout, b"", "nothing goes to stdout")
                self.assertTrue(result.stderr_text().strip(), "one message on stderr")

    def test_f_a_script_that_is_not_a_bare_py_name_exits_by_its_class(self):
        main = self.checkout("main")
        (main / "sub").mkdir()
        (main / "sub" / "probe.py").write_text(PROBE, encoding="utf-8")
        for script in ("sub/probe.py", "sub\\probe.py", "../probe.py", str(main / "sub" / "probe.py"), "probe"):
            for hook_class, code in (("block", 2), ("warn", 1)):
                with self.subTest(script=script, hook_class=hook_class):
                    result = self.launch(hook_class, script, cwd=main, project_dir=str(main))
                    self.assertEqual(result.returncode, code, "stderr: " + result.stderr_text()[-300:])
                    self.assertIsNone(result.record, "such a script must never run")
                    self.assertTrue(result.stderr_text().strip(), "with a message")


class SourceTextTests(LauncherCase):
    """(g) the launcher source (L5, L6)."""

    def test_g_it_compiles_stays_within_40_lines_and_starts_with_the_marker_comment(self):
        src = self.source()
        compile(src, "<launcher>", "exec")
        self.assertLessEqual(len(src.splitlines()), 40, "at most 40 lines (L5)")
        self.assertEqual(src.splitlines()[0], MARKER_LINE, "the first line is the version marker (L5, L7)")

    def test_g_it_imports_only_os_sys_runpy_and_traceback_and_the_last_two_only_after_the_path_entry_goes(self):
        import ast
        src = self.source()
        tree = ast.parse(src)
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names += [(a.name.split(".")[0], node.lineno) for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names.append(((node.module or "").split(".")[0], node.lineno))
        self.assertTrue({n for n, _ in names} <= {"os", "sys", "runpy", "traceback"},
                        "standard library only, and only these four: %r" % sorted({n for n, _ in names}))
        lines = src.splitlines()
        first_path_use = next((i + 1 for i, ln in enumerate(lines) if "sys.path" in ln), None)
        self.assertIsNotNone(first_path_use, "step 0 must change sys.path (remove the working-folder entry)")
        for name, lineno in names:
            if name in ("runpy", "traceback"):
                self.assertGreater(lineno, first_path_use,
                                   "%s is imported on line %d, before the working-folder entry is removed on "
                                   "line %d (step 0)" % (name, lineno, first_path_use))

    def test_g_it_holds_no_character_a_layer_could_rewrite(self):
        src = self.source()
        for bad, label in (("$", "dollar"), ("%", "percent"), ('"', "double quote"), ("\\", "backslash")):
            self.assertNotIn(bad, src, "L6: the source must hold no %s" % label)

    def test_g_the_decoded_text_holds_no_drive_letter_path_and_no_users_and_does_not_end_in_py(self):
        src = self.source()
        self.assertIsNone(_DRIVE_LETTER_RE.search(src), "no drive-letter path in the decoded text")
        self.assertNotIn("Users", src, "no user-profile path in the decoded text")
        self.assertFalse(src.rstrip().endswith(".py"),
                         "it must not end in .py, because profile_setup and the latency tool take the first "
                         "argument ending .py as the hook's name")

    def test_g_a_row_built_by_the_builder_passes_this_repositorys_decoded_string_scan(self):
        module, why = _load_constants()
        self.assertIsNotNone(module, why)
        builder = getattr(module, BUILDER, None)
        self.assertTrue(callable(builder), "_project_paths.py must define the row builder %s() (contract "
                                           "Revision 9, section N)" % BUILDER)
        row = builder("probe.py", "warn")
        text = json.dumps(row)
        self.assertEqual(decoded_drive_letter_scan(text), [],
                         "the decoded strings of a launcher row hold no drive letter and no Users")
        self.assertIn(self.source(), row.get("args", []), "the builder writes the constant byte for byte")

    def test_g_positive_control_the_scan_fails_a_planted_drive_letter_path(self):
        self.assertEqual(decoded_drive_letter_scan(json.dumps({"args": ["-c", "C:/x"]})), ["C:/"],
                         "POSITIVE CONTROL: a planted C:/x must be seen by the scan")
        self.assertEqual(decoded_drive_letter_scan(json.dumps({"args": ["a\nb"]})), [],
                         "and a stored newline must not read as a drive letter after decoding")


class OneInterpreterTests(LauncherCase):
    """(i) the hook runs inside the launcher's own interpreter."""

    def test_i_the_probe_ran_in_the_dash_c_process_with_the_target_as_its_main_module(self):
        self.assertTrue(hasattr(sys, "orig_argv"),
                        "HALT: sys.orig_argv is missing, so the installed Python (%s) is older than 3.10 and "
                        "case (i) cannot be written; report the version" % sys.version.split()[0])
        main = self.checkout("main")
        src = self.source()
        result = self.launch("block", "probe.py", cwd=main, project_dir=str(main), source=src)
        self.assertEqual(result.returncode, 0, "stderr: " + result.stderr_text()[-400:])
        record = result.record
        self.assertIsNotNone(record, "the hook must run")
        orig = record["orig_argv"]
        self.assertIn("-c", orig, "the interpreter that ran the hook was started with -c")
        after = orig[orig.index("-c") + 1]
        self.assertEqual(after.replace("\r\n", "\n"), src,
                         "and its program text is the launcher source, so no second Python was started from it")
        self.assertEqual(_norm(record["main_file"]), _norm(str(main / ".claude" / "hooks" / "probe.py")),
                         "the __main__ module the hook saw is the target file")
        self.assertEqual(record["name"], "__main__", "the hook ran as __main__")


if __name__ == "__main__":
    unittest.main(verbosity=2)
