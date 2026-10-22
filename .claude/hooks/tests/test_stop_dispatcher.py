#!/usr/bin/env python3
"""test_stop_dispatcher.py -- RED suite for ``stop-dispatcher.py`` (Revision 3 of the dedupe contract).

Contract: .claude/concepts/2026-10-12-dedupe-claude-config.md in the consuming repository, Reused
Mechanisms ("The in-process dispatcher") and block 16.

WHAT THE DISPATCHER IS
----------------------
One Stop hook in place of two. It follows ``post-edit-dispatcher.py`` (one process, the members run one
after another through ``_inprocess_hook.run_script``, in the order of its ``CHECKS`` list), with two
differences forced by the Stop event: it is not asynchronous, and it exits 2 when any member exits 2,
writing every member's error text in member order. Any other member code is ignored (fail open), and its
own failure exits 0. Its one member: ``../scripts/concept_changed_check.py`` (the Changed-file check).

WHAT IS PINNED
--------------
  * the members run in the order of CHECKS, in ONE process (the dispatcher's own);
  * any member exiting 2 gives exit 2, with EVERY member's error text in member order; a member that
    exits 2 never stops the next member from running;
  * a member exiting 1, and a member that raises, are ignored (exit 0) and the next member still runs;
  * a member's exit code, standard output and error text are BYTE-IDENTICAL to running it alone (a stub
    that writes fixed bytes, including a non-ASCII character, and exits 2);
  * a member's ``systemMessage`` reaches the dispatcher's output (the Changed-file check's "noted" outcome
    is a systemMessage; a dispatcher that swallowed it would turn "noted" into silence);
  * the dispatcher's own failure (it cannot load the in-process runner; empty input) exits 0;
  * (Revision 8, I.5) a MISSING member fails open: exit 0 with no traceback, one error-log line (hook
    ``stop-dispatcher``, event ``member-missing``), one notice per session naming the member (a
    ``systemMessage`` on exit 0; one trailing stderr line after the members' own text on exit 2), and the
    other members still run.

HOW IT IS TESTED
----------------
Order, exit rules and failure handling run against STUB members: a temporary hooks folder holds a copy of
the real ``stop-dispatcher.py`` and ``_inprocess_hook.py`` and stub files named like the members.
A stub records its name and process id in a trace file and then behaves as an environment variable tells it
(exit code, error text, output text, or a raised exception).

The real dispatcher has ONE member, so the rows about SEVERAL members (order, error texts in order, exit 2
not stopping the next, exit 1, raise, a missing first or second member) run on a TEST COPY of the
dispatcher whose ``CHECKS`` literal is rewritten to ``["first-stub.py", CONCEPT]``. The Workspace asserts
that the rewrite happened, so a renamed constant fails loudly instead of silently testing one member. The
one-member rows (``OneMemberTests``) and the identity row run on the dispatcher UNCHANGED.

Run:
    py -3 .claude/hooks/tests/test_stop_dispatcher.py
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
DISPATCHER = HOOKS_DIR / "stop-dispatcher.py"
CONCEPT = "../scripts/concept_changed_check.py"
FIRST = "first-stub.py"  # the stand-in first member of the test copy (the real list has one member)
MEMBERS = [FIRST, CONCEPT]  # the members of the TEST COPY

STUB_SOURCE = '''\
import json, os, sys

NAME = os.path.relpath(__file__, os.environ["STUB_HOOKS"]).replace(os.sep, "/")
DATA = sys.stdin.read()
CONFIG = json.loads(os.environ.get("STUB_CONFIG", "{}")).get(NAME, {})
with open(os.environ["STUB_TRACE"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"member": NAME, "pid": os.getpid(), "stdin": DATA}) + "\\n")
if CONFIG.get("out"):
    sys.stdout.write(CONFIG["out"])
if CONFIG.get("err"):
    sys.stderr.write(CONFIG["err"])
if CONFIG.get("raise"):
    raise RuntimeError("stub member " + NAME + " raised on purpose")
sys.exit(CONFIG.get("code", 0))
'''


def require_dispatcher() -> None:
    if not DISPATCHER.is_file():
        raise AssertionError("%s does not exist yet (block 17 adds the Stop dispatcher)" % DISPATCHER)


class Workspace:
    """A temporary hooks folder holding a dispatcher, the real runner and stub members.

    ``multi=True`` (the default) installs a TEST COPY of the dispatcher whose CHECKS literal is rewritten to
    ``MEMBERS``; ``multi=False`` installs the real dispatcher byte for byte and stubs its real members."""

    def __init__(self, *, with_runner: bool = True, multi: bool = True):
        self.root = Path(tempfile.mkdtemp(prefix="stopdisp_"))
        self.hooks = self.root / "hooks"
        self.hooks.mkdir()
        self.trace = self.root / "trace.jsonl"
        require_dispatcher()
        if multi:
            source = DISPATCHER.read_text(encoding="utf-8")
            rewritten, hits = re.subn(r"^CHECKS = \[.*?\]", "CHECKS = %s" % json.dumps(MEMBERS), source,
                                      count=1, flags=re.DOTALL | re.MULTILINE)
            if hits != 1 or rewritten == source:
                raise AssertionError("the CHECKS literal of stop-dispatcher.py could not be rewritten for the "
                                     "several-member rows (was the constant renamed?)")
            (self.hooks / "stop-dispatcher.py").write_text(rewritten, encoding="utf-8")
            self.members = list(MEMBERS)
        else:
            shutil.copyfile(DISPATCHER, self.hooks / "stop-dispatcher.py")
            self.members = [CONCEPT]
        if with_runner:
            shutil.copyfile(HOOKS_DIR / "_inprocess_hook.py", self.hooks / "_inprocess_hook.py")
        # Revision 8, I.5 (the one sanctioned fixture change): the error-log helper and its path helper sit
        # beside the dispatcher; HOME and USERPROFILE name a throwaway home whose .claude/logs exists, so a
        # log line never reaches the developer's real home log; TEMP and TMP are fresh per Workspace and the
        # session id is unique per Workspace, so the once-per-session marker never leaks between rows or reruns.
        for helper in ("_error_log.py", "_project_paths.py"):
            shutil.copyfile(HOOKS_DIR / helper, self.hooks / helper)
        self.home = self.root / "home"
        (self.home / ".claude" / "logs").mkdir(parents=True)
        self.temp = self.root / "temp"
        self.temp.mkdir()
        self.session_id = "s-stop-" + uuid.uuid4().hex
        (self.root / "scripts").mkdir()  # the second member lives in the scripts folder beside hooks
        for name in self.members:
            (self.hooks / name).write_text(STUB_SOURCE, encoding="utf-8")

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def run(self, config: dict | None = None, data: bytes | None = None):
        payload = data if data is not None else json.dumps(
            {"session_id": self.session_id, "cwd": str(self.root), "stop_hook_active": False}).encode("utf-8")
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_")}
        env.update({"STUB_TRACE": str(self.trace), "STUB_HOOKS": str(self.hooks), "STUB_CONFIG": json.dumps(config or {}),
                    "HOME": str(self.home), "USERPROFILE": str(self.home),
                    "TEMP": str(self.temp), "TMP": str(self.temp), "TMPDIR": str(self.temp),
                    "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})
        proc = subprocess.Popen([sys.executable, "-B", str(self.hooks / "stop-dispatcher.py")],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        out, err = proc.communicate(payload, timeout=60)
        return proc.pid, proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    def trace_rows(self) -> list[dict]:
        if not self.trace.is_file():
            return []
        return [json.loads(line) for line in self.trace.read_text(encoding="utf-8").splitlines() if line.strip()]

    def error_log_rows(self) -> list[dict]:
        """Every line the run wrote to the throwaway home's error log."""
        log = self.home / ".claude" / "logs" / "errors.jsonl"
        if not log.is_file():
            return []
        return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


class StopDispatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ws = Workspace()
        self.addCleanup(self.ws.close)

    def test_the_checks_list_names_the_one_member(self):
        tree = ast.parse(DISPATCHER.read_text(encoding="utf-8"))
        checks = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "CHECKS" for t in node.targets):
                checks = ast.literal_eval(node.value)
        self.assertEqual(checks, [CONCEPT],
                         msg="CHECKS (read as a literal, as the drift check reads it) must hold exactly one "
                             "member, ../scripts/concept_changed_check.py")

    def test_the_test_copy_really_has_several_members(self):
        text = (self.ws.hooks / "stop-dispatcher.py").read_text(encoding="utf-8")
        self.assertIn("CHECKS = %s" % json.dumps(MEMBERS), text,
                      msg="the several-member rows must run on a copy whose CHECKS literal was rewritten")

    def test_members_run_in_order_in_the_dispatchers_own_process(self):
        pid, code, _out, err = self.ws.run()
        rows = self.ws.trace_rows()
        self.assertEqual([r["member"] for r in rows], MEMBERS,
                         msg="both members of the test copy must run, in CHECKS order: " + err[:300])
        self.assertEqual({r["pid"] for r in rows}, {pid},
                         msg="the members run in ONE process (the dispatcher's own), not one program start each")
        self.assertEqual(code, 0, msg="two silent members give exit 0: " + err[:300])
        self.assertIn('"session_id": "%s"' % self.ws.session_id, rows[0]["stdin"],
                      msg="each member gets the same input bytes it would have been given on its own")
        self.assertEqual(rows[0]["stdin"], rows[1]["stdin"], msg="both members get the same input")

    def test_any_member_exit_2_gives_exit_2_with_every_members_error_text_in_order(self):
        _pid, code, _out, err = self.ws.run({FIRST: {"code": 2, "err": "FIRST-STOP-TEXT\n"},
                                             CONCEPT: {"code": 2, "err": "CONCEPT-STOP-TEXT\n"}})
        self.assertEqual(code, 2, msg="a member exit 2 must give exit 2: " + err[:300])
        self.assertIn("FIRST-STOP-TEXT", err, msg="the first member's error text must be written")
        self.assertIn("CONCEPT-STOP-TEXT", err, msg="the second member's error text must be written")
        self.assertLess(err.index("FIRST-STOP-TEXT"), err.index("CONCEPT-STOP-TEXT"),
                        msg="error texts come in member order")
        self.assertEqual([r["member"] for r in self.ws.trace_rows()], MEMBERS,
                         msg="a member that exits 2 must not stop the next member from running")

    def test_the_second_member_alone_exiting_2_gives_exit_2(self):
        _pid, code, _out, err = self.ws.run({CONCEPT: {"code": 2, "err": "CONCEPT-STOP-TEXT\n"}})
        self.assertEqual(code, 2, msg="the Changed-file check stopping the turn must stop the turn: " + err[:300])
        self.assertIn("CONCEPT-STOP-TEXT", err, msg="its text must reach the error stream")

    def test_the_first_member_alone_exiting_2_gives_exit_2_and_the_second_still_runs(self):
        _pid, code, _out, err = self.ws.run({FIRST: {"code": 2, "err": "FIRST-STOP-TEXT\n"}})
        self.assertEqual(code, 2, msg="the first member stopping the turn must stop the turn: " + err[:300])
        self.assertEqual([r["member"] for r in self.ws.trace_rows()], MEMBERS,
                         msg="the second member still runs after the first exits 2")

    def test_a_member_exit_1_is_ignored_and_the_next_member_still_runs(self):
        _pid, code, _out, err = self.ws.run({FIRST: {"code": 1, "err": "plain crashed\n"}})
        self.assertEqual(code, 0, msg="exit 1 is ignored (fail open): " + err[:300])
        self.assertEqual([r["member"] for r in self.ws.trace_rows()], MEMBERS,
                         msg="the member after an exit-1 member still runs")
        # Control: the same harness reports exit 2, so the exit-0 above is the dispatcher's rule.
        ws2 = Workspace()
        self.addCleanup(ws2.close)
        _pid, code2, _out, _err = ws2.run({FIRST: {"code": 1}, CONCEPT: {"code": 2, "err": "X\n"}})
        self.assertEqual(code2, 2, msg="control: an exit-1 member does not hide a later member's exit 2")

    def test_a_member_that_raises_is_ignored_and_the_next_member_still_runs(self):
        _pid, code, _out, err = self.ws.run({FIRST: {"raise": True}})
        self.assertEqual(code, 0, msg="a raised member is ignored (fail open): " + err[:300])
        self.assertEqual([r["member"] for r in self.ws.trace_rows()], MEMBERS,
                         msg="the member after a raised member still runs")

    def test_a_member_system_message_reaches_the_dispatchers_output(self):
        message = json.dumps({"systemMessage": "NOTED-FILES-TEXT"})
        _pid, code, out, err = self.ws.run({CONCEPT: {"code": 0, "out": message}})
        self.assertEqual(code, 0, msg="a noted outcome does not stop the turn: " + err[:300])
        self.assertIn("NOTED-FILES-TEXT", out,
                      msg="the Changed-file check's noted outcome is a systemMessage on its output; "
                          "the dispatcher must pass it on, or noted becomes silence")

    def test_the_dispatchers_own_failure_exits_0(self):
        ws = Workspace(with_runner=False)
        self.addCleanup(ws.close)
        _pid, code, _out, err = ws.run({FIRST: {"code": 2, "err": "WOULD-STOP\n"}})
        self.assertEqual(code, 0,
                         msg="with no in-process runner the dispatcher cannot run its members, and a "
                             "dispatcher that cannot work must exit 0, never hold a session: " + err[:300])

    def test_empty_input_exits_0(self):
        _pid, code, _out, err = self.ws.run(data=b"")
        self.assertEqual(code, 0, msg="empty input is not a failure: " + err[:300])


def system_messages(stdout: str) -> list[str]:
    """Every ``systemMessage`` value on the dispatcher's standard output (one JSON object per line)."""
    found = []
    for line in stdout.splitlines():
        if line.strip():
            payload = json.loads(line)
            if isinstance(payload, dict) and isinstance(payload.get("systemMessage"), str):
                found.append(payload["systemMessage"])
    return found


class MissingMemberTests(unittest.TestCase):
    """Revision 8, I.5: a member whose file is missing is "could not check", never a crash (contract G).

    Every row builds its own Workspace, so each has a fresh home, a fresh temporary folder and its own session
    id. "The second member" and "the first member" are MEMBERS[1] and MEMBERS[0]: the rows never name a
    member file themselves, so block 17's path-only repair of the member constant leaves them unchanged."""

    def setUp(self) -> None:
        self.ws = Workspace()
        self.addCleanup(self.ws.close)
        self.first, self.second = MEMBERS[0], MEMBERS[1]

    def _remove_second(self) -> None:
        (self.ws.hooks / self.second).unlink()

    def test_a_missing_second_member_exits_0_with_no_traceback(self):
        self._remove_second()
        _pid, code, _out, err = self.ws.run()
        self.assertEqual(code, 0, msg="a missing member is 'could not check', never exit 1 or 2: " + err[:300])
        self.assertNotIn("Traceback", err,
                         msg="the runner's missing-file traceback (_inprocess_hook.run_script) must not reach stderr")
        self.assertEqual([r["member"] for r in self.ws.trace_rows()], [self.first],
                         msg="the members that exist still run; only the missing one is skipped")

    def test_a_missing_second_member_writes_exactly_one_member_missing_log_line(self):
        self._remove_second()
        self.ws.run()
        rows = self.ws.error_log_rows()
        self.assertEqual(len(rows), 1, msg="exactly one error-log line per missing member, in the throwaway "
                                           "home's log: " + repr(rows))
        self.assertEqual((rows[0].get("hook"), rows[0].get("event")), ("stop-dispatcher", "member-missing"),
                         msg="the line names the hook stop-dispatcher and the event member-missing")
        self.assertIn(self.second, json.dumps(rows[0], ensure_ascii=False),
                      msg="the line carries the member string as written in CHECKS")

    def test_on_exit_0_one_system_message_names_the_member_and_a_second_run_in_the_session_prints_none(self):
        self._remove_second()
        _pid, code, out, err = self.ws.run()
        self.assertEqual(code, 0, msg=err[:300])
        notices = system_messages(out)
        self.assertEqual(len(notices), 1, msg="exactly one systemMessage on the first run: " + repr(out))
        self.assertIn(self.second, notices[0], msg="the notice names the member that did not run")
        _pid, code2, out2, err2 = self.ws.run()
        self.assertEqual(code2, 0, msg=err2[:300])
        self.assertEqual(system_messages(out2), [],
                         msg="at most one notice per session: the second run in the same session prints none")
        self.assertNotIn(self.second, out2, msg="and nothing else on stdout names the member either")

    def test_on_exit_2_the_notice_follows_the_first_members_unchanged_text_and_is_not_repeated(self):
        self._remove_second()
        text = "FIRST-STOP-TEXT\n"
        _pid, code, out, err = self.ws.run({self.first: {"code": 2, "err": text}})
        self.assertEqual(code, 2, msg="the first member's exit 2 still stops the turn: " + err[:300])
        # The stub runs inside the dispatcher through a text wrapper (_inprocess_hook.run_script) whose newline
        # setting turns "\n" into "\r\n" on Windows, and Workspace.run decodes without translating. Compare on
        # normalised newlines: the member's text still comes first and unchanged, whichever line ending it got.
        err_n = err.replace("\r\n", "\n")
        self.assertTrue(err_n.startswith(text),
                        msg="the member's own bytes come first and are unchanged: " + repr(err[:200]))
        trailing = err_n[len(text):].strip()
        self.assertIn(self.second, trailing, msg="the notice naming the missing member follows that text")
        self.assertEqual(len(trailing.splitlines()), 1, msg="exactly one notice line trails the member text")
        self.assertEqual(system_messages(out), [], msg="on exit 2 the notice goes to stderr, not stdout")
        _pid, code2, out2, err2 = self.ws.run()
        self.assertEqual(code2, 0, msg="a later clean run in the same session exits 0: " + err2[:300])
        self.assertNotIn(self.second, out2 + err2,
                         msg="the marker was spent when the notice was written: no second notice")

    def test_with_the_first_member_missing_the_second_still_runs_and_its_exit_2_still_stops_the_turn(self):
        # Paired control, not a broken-rule target (round nine): it goes red if the check stops the loop at a
        # missing member, but not when the check is removed.
        (self.ws.hooks / self.first).unlink()
        _pid, code, _out, err = self.ws.run({self.second: {"code": 2, "err": "CONCEPT-STOP-TEXT\n"}})
        self.assertEqual([r["member"] for r in self.ws.trace_rows()], [self.second],
                         msg="a missing first member must not stop the later member from running: " + err[:300])
        self.assertEqual(code, 2, msg="the second member's exit 2 still stops the turn: " + err[:300])
        self.assertIn("CONCEPT-STOP-TEXT", err, msg="its error text reaches stderr")


class OneMemberTests(unittest.TestCase):
    """The REAL dispatcher, unchanged, with its one member stubbed: the Changed-file check."""

    def setUp(self) -> None:
        self.ws = Workspace(multi=False)
        self.addCleanup(self.ws.close)

    def test_a_silent_member_gives_exit_0_and_says_nothing(self):
        _pid, code, out, err = self.ws.run()
        self.assertEqual([r["member"] for r in self.ws.trace_rows()], [CONCEPT],
                         msg="the one member must run: " + err[:300])
        self.assertEqual(code, 0, msg="a silent member gives exit 0: " + err[:300])
        self.assertEqual(out, "",
                         msg="nothing on standard output: the real CHECKS list must name no other member "
                             "(a member file that is absent from the folder would print a missing notice): "
                             + out[:300])
        self.assertEqual(err, "", msg="nothing on standard error when the one member is silent")
        self.assertEqual(self.ws.error_log_rows(), [],
                         msg="no member-missing line: the real CHECKS list names only files that exist")

    def test_the_member_exit_2_stops_the_turn(self):
        _pid, code, _out, err = self.ws.run({CONCEPT: {"code": 2, "err": "CONCEPT-STOP-TEXT\n"}})
        self.assertEqual(code, 2, msg="the Changed-file check stopping the turn must stop the turn: " + err[:300])
        self.assertIn("CONCEPT-STOP-TEXT", err, msg="its text must reach the error stream")
        self.assertNotIn("not run", err, msg="no missing-member notice trails the text: the list has one member")

    def test_the_member_system_message_passes_through(self):
        message = json.dumps({"systemMessage": "NOTED-FILES-TEXT"})
        _pid, code, out, err = self.ws.run({CONCEPT: {"code": 0, "out": message}})
        self.assertEqual(code, 0, msg="a noted outcome does not stop the turn: " + err[:300])
        self.assertEqual(system_messages(out), ["NOTED-FILES-TEXT"],
                         msg="the member's systemMessage is the only message on the output")


IDENTITY_STUB = '''import sys
sys.stdin.read()
sys.stdout.write("OUT-FIXED \u00e9\u2014 caf\u00e9 done")
sys.stderr.write("ERR-FIXED \u2026 na\u00efve stop")
sys.exit(2)
'''


class StubIdentityTests(unittest.TestCase):
    """A stub member through the real dispatcher equals the same stub run alone, byte for byte."""

    def _folder(self, root: Path) -> Path:
        hooks = root / "hooks"
        hooks.mkdir()
        for name in ("_inprocess_hook.py", "_error_log.py", "_project_paths.py"):
            shutil.copyfile(HOOKS_DIR / name, hooks / name)
        (root / "scripts").mkdir(exist_ok=True)
        (hooks / CONCEPT).write_text(IDENTITY_STUB, encoding="utf-8")
        shutil.copyfile(DISPATCHER, hooks / "stop-dispatcher.py")
        return hooks

    def _run(self, script: Path, root: Path):
        temp = root / "temp"
        temp.mkdir(exist_ok=True)
        (root / "home" / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_")}
        env.update({"TEMP": str(temp), "TMP": str(temp), "HOME": str(root / "home"),
                    "USERPROFILE": str(root / "home"), "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONIOENCODING": "utf-8"})
        payload = {"session_id": "s-ident-" + uuid.uuid4().hex, "stop_hook_active": False}
        proc = subprocess.run([sys.executable, "-B", str(script)], input=json.dumps(payload).encode("utf-8"),
                              capture_output=True, env=env, timeout=60)
        return proc.returncode, proc.stdout, proc.stderr

    def test_exit_code_output_and_error_text_are_byte_identical(self):
        require_dispatcher()
        alone_root = Path(tempfile.mkdtemp(prefix="id_alone_"))
        disp_root = Path(tempfile.mkdtemp(prefix="id_disp_"))
        self.addCleanup(shutil.rmtree, alone_root, True)
        self.addCleanup(shutil.rmtree, disp_root, True)
        alone_hooks = self._folder(alone_root)
        disp_hooks = self._folder(disp_root)
        alone_code, alone_out, alone_err = self._run(alone_hooks / CONCEPT, alone_root)
        disp_code, disp_out, disp_err = self._run(disp_hooks / "stop-dispatcher.py", disp_root)
        self.assertEqual(alone_code, 2, msg="fixture sanity: the stub alone exits 2: %r" % alone_err[:300])
        self.assertIn("é".encode("utf-8"), alone_out, msg="fixture sanity: the stub writes a non-ASCII character")
        self.assertEqual(disp_code, alone_code, msg="the dispatcher's exit code must equal the member's")
        self.assertEqual(disp_out, alone_out, msg="the member's output must be byte-identical through the dispatcher")
        self.assertEqual(disp_err, alone_err, msg="the member's error text must be byte-identical through the "
                                                  "dispatcher (no trailing notice, no extra line)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
