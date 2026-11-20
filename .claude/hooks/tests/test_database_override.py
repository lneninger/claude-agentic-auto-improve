#!/usr/bin/env python3
"""
test_database_override.py -- the Database override arm in both database guards.

Contract: .claude/concepts/2026-11-16-file-based-switches.md (Data Shapes: "Override rules"; Extension
Points: db-destructive-guard.py and the ask output; sub-task 1, "RED tests").

WHAT IS PINNED DOWN
-------------------
The arm is the file <project>/.claude/database-override.once. It allows nothing by itself: an armed,
fresh, regular file turns the NEXT blocked command into a permission prompt (the PreToolUse "ask"
answer on standard output, exit 0) and is used up, whatever the answer. Rows:

  * Arm-write refusal (both guards, Bash and PowerShell; the destructive guard also for Write, Edit,
    MultiEdit and NotebookEdit): a call that would write the arm is refused (exit 2) even when armed,
    even when the guard defers, and with the helper removed (the guard keeps an inline copy of the name
    test). A commit message, a pull request body and a search pattern that only MENTION the name are
    allowed.
  * Ask: armed + a mode where Claude Code asks (default, acceptEdits, plan) gives the ask JSON, exit 0,
    and the arm is gone. bypassPermissions, dontAsk, an unknown mode and a missing mode block, and the
    block text tells the person to run the command in their own terminal.
  * Stale (older than 15 minutes), folder and link arms block.
  * The human-only class and an injected guard fault block even when armed.
  * CLAUDE_DESTRUCTIVE_DB_OK=1 no longer allows (the variable is retired).
  * A call that matches no rule leaves the arm alone and usable.
  * Two guards on one tool_use_id both ask; with no identifier the second blocks.
  * A crafted target holding comment markers appears neutralised in the reason.

Each guard runs as its OWN python process, in place, with a temporary project (rules file, logs folder),
a temporary home folder and an environment stripped of every CLAUDE* variable. The only variables set
for a row are set inside that child process (CLAUDE_DESTRUCTIVE_DB_OK=1 and DB_GUARD_FAULT_INJECTION to
prove they no longer allow). Payloads are built from parts, so this file holds no literal destructive
phrase and an agent can edit it without tripping the guard.

GREEN. The guards carry the arm since sub-task 2 (the helper block), so the RED marks of sub-task 1 are
removed. Rows that mutate an armed state start with a CONTROL that the armed command asks, so a row cannot
pass by accident.

Run: py -3 .claude/hooks/tests/test_database_override.py
"""
from __future__ import annotations

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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_guard_deference import World as DeferenceWorld  # noqa: E402  (the existing fixture builder)
from test_guard_deference import DESTRUCTIVE as DEFERENCE_DESTRUCTIVE, READONLY as DEFERENCE_READONLY  # noqa: E402
from test_guard_deference import SESSION_ID as DEFERENCE_SESSION  # noqa: E402
from test_switches import SKIP_NO_SYMLINK, SKIP_POSIX_PIPES, PipeServer, make_pipe_link  # noqa: E402  (pipe server, link maker)

HOOK_TIMEOUT = 60

DESTRUCTIVE_HOOK = HOOKS_SRC / "db-destructive-guard.py"
READONLY_HOOK = HOOKS_SRC / "db-research-readonly-guard.py"

# Built from parts: no literal destructive phrase in this file.
_V = "DR" + "OP DATA" + "BASE"
PROTECTED = "ScalpingMachine"
#: Blocked by BOTH guards: a protected database named as the target of a database-level statement.
BLOCKED_COMMAND = 'sqlcmd -S "(localdb)\\m" -E -Q "' + _V + " " + PROTECTED + '"'
HUMAN_ONLY_SCRIPT = "tools/db-protection/update-dev-database.cmd"
_EF_UPDATE = "dotnet ef database " + "up" + "date"
_ROW_DELETE = "DE" + "LETE"

RULES = {
    "protected_databases": [PROTECTED, PROTECTED + "_Testing"],
    "production_path_allowlist": ["src/scalpingmachine.api/", "tools/db-protection/", ".claude/", "docs/"],
    "human_only_commands": [{"script": HUMAN_ONLY_SCRIPT}],
}

PROMPT_WORDING = ("One-shot destructive database override. A person armed it. "
                  "Approve only if you mean to run this exact command.")
ASK_MODES = ("default", "acceptEdits", "plan")
NO_PROMPT_MODES = ("bypassPermissions", "dontAsk", "someFutureMode", None)
FRESH_SECONDS = 15 * 60


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


class Run:
    """The result of one guard process."""

    def __init__(self, proc: subprocess.CompletedProcess):
        self.rc = proc.returncode
        self.out = proc.stdout.decode("utf-8", "replace")
        self.err = proc.stderr.decode("utf-8", "replace")

    @property
    def ask(self) -> dict | None:
        try:
            data = json.loads(self.out)
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    def __str__(self) -> str:
        return "rc=%s stdout=%r stderr=%r" % (self.rc, self.out[:300], self.err[:300])


class OverrideTestCase(unittest.TestCase):
    """One temporary project per test, removed in a cleanup that runs whether the test passes or fails."""

    GUARD = DESTRUCTIVE_HOOK

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="db-override-")).resolve()
        self.addCleanup(_rmtree, self.tmp)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.project = self.tmp / "project"
        (self.project / ".claude" / "hooks").mkdir(parents=True)
        (self.project / ".claude" / "logs").mkdir()
        (self.project / ".claude" / "hooks" / "db-destructive-guard.rules.json").write_text(
            json.dumps(RULES), encoding="utf-8")
        self._tool_ids = 0

    # ---------------------------------------------------------------- arm
    @property
    def arm_path(self) -> Path:
        return self.project / ".claude" / "database-override.once"

    def arm(self, *, age_seconds: float = 0.0, kind: str = "file") -> Path:
        path = self.arm_path
        if kind == "file":
            path.write_bytes(b"")
            stamp = time.time() - age_seconds
            os.utime(path, (stamp, stamp))
        elif kind == "folder":
            path.mkdir()
        elif kind == "link":
            target = self.project / "arm-target.txt"
            target.write_bytes(b"")
            try:
                os.symlink(target, path)
            except (OSError, NotImplementedError) as exc:
                self.skipTest("this machine cannot create a symbolic link: %s" % exc)
        return path

    def claim_files(self) -> list[Path]:
        return sorted((self.project / ".claude").glob("database-override.claimed-*"))

    # ---------------------------------------------------------------- run
    def env(self, extra: dict | None = None) -> dict:
        env = {k: v for k, v in os.environ.items()
               if not k.upper().startswith("CLAUDE") and k != "DB_GUARD_FAULT_INJECTION"}
        env.update({"HOME": str(self.home), "USERPROFILE": str(self.home), "TEMP": str(self.home),
                    "TMP": str(self.home), "TMPDIR": str(self.home), "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONIOENCODING": "utf-8", "CLAUDE_PROJECT_DIR": str(self.project)})
        env.update(extra or {})
        return env

    def payload(self, tool: str = "Bash", tool_input: dict | None = None, *, mode="default",
                tool_use_id: str | None = "toolu_default") -> dict:
        data = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input or {},
                "cwd": str(self.project), "session_id": "sess-override"}
        if mode is not None:
            data["permission_mode"] = mode
        if tool_use_id is not None:
            data["tool_use_id"] = tool_use_id
        return data

    def shell(self, command: str, tool: str = "Bash", **kw) -> dict:
        return self.payload(tool, {"command": command}, **kw)

    def run_guard(self, payload: dict, *, guard: Path | None = None, env: dict | None = None,
                  timeout: float = HOOK_TIMEOUT) -> Run:
        try:
            proc = subprocess.run([sys.executable, "-B", str(guard or self.GUARD)],
                                  input=json.dumps(payload).encode("utf-8"), capture_output=True,
                                  env=self.env(env), cwd=str(self.tmp), timeout=timeout)
        except subprocess.TimeoutExpired:
            self.fail("the guard did not finish within %s seconds (it hung)" % timeout)
        return Run(proc)

    # ---------------------------------------------------------------- asserts
    def assert_asks(self, run: Run, why: str) -> dict:
        self.assertEqual(run.rc, 0, "%s: an armed command must end in a prompt (exit 0). %s" % (why, run))
        data = run.ask
        self.assertIsNotNone(data, "%s: standard output must be the ask JSON. %s" % (why, run))
        self.assertEqual(set(data), {"hookSpecificOutput"}, why + ": the only top-level field is hookSpecificOutput")
        inner = data["hookSpecificOutput"]
        self.assertEqual(inner.get("hookEventName"), "PreToolUse", why)
        self.assertEqual(inner.get("permissionDecision"), "ask", why + ": the answer is ask, never allow")
        self.assertIsInstance(inner.get("permissionDecisionReason"), str, why)
        self.assertEqual(set(inner), {"hookEventName", "permissionDecision", "permissionDecisionReason"}, why)
        return inner

    def assert_blocks(self, run: Run, why: str) -> None:
        self.assertEqual(run.rc, 2, "%s: must block (exit 2). %s" % (why, run))
        self.assertNotIn("permissionDecision", run.out, why + ": a block must not also offer a prompt")

    def control_asks(self, why: str = "CONTROL") -> dict:
        """The armed blocked command asks. Used to make a 'must block' row red for the right reason."""
        self.arm()
        run = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()))
        inner = self.assert_asks(run, why + " (an armed, fresh arm in a default mode)")
        self.assertFalse(self.arm_path.exists(), why + ": the arm is used up")
        return inner

    def next_id(self) -> str:
        self._tool_ids += 1
        return "toolu_%d" % self._tool_ids


# =====================================================================================================
# Rows run once per guard.
# =====================================================================================================
class OverrideRows:
    """Shared rows (a mixin, so the loader never collects it alone). A subclass sets GUARD and its name."""

    GUARD: Path

    # -- controls that hold at base ---------------------------------------------------------------
    def test_control_the_blocked_command_blocks_without_an_arm(self):
        run = self.run_guard(self.shell(BLOCKED_COMMAND))
        self.assert_blocks(run, "no arm")

    def test_control_a_mention_of_the_name_in_prose_is_allowed(self):
        self.arm()
        for command in (
            'git commit -m "Explain the database-override.once file in the README"',
            'gh pr create --title "Docs" --body "The arm file database-override.once is made by a person."',
            'grep -rn "database-override" .claude/hooks',
            'echo "a person creates database-override.once in their own terminal"',
        ):
            for tool in ("Bash", "PowerShell"):
                with self.subTest(command=command[:40], tool=tool):
                    run = self.run_guard(self.shell(command, tool))
                    self.assertEqual(run.rc, 0, "a mention is not a write: %s" % run)
                    self.assertTrue(self.arm_path.exists(), "a mention must leave the arm alone")

    # -- the ask ----------------------------------------------------------------------------------
    def test_armed_with_a_mode_that_asks_gives_the_ask_json_and_uses_up_the_arm(self):
        for mode in ASK_MODES:
            with self.subTest(mode=mode):
                self.arm()
                run = self.run_guard(self.shell(BLOCKED_COMMAND, mode=mode, tool_use_id=self.next_id()))
                inner = self.assert_asks(run, "mode " + mode)
                self.assertTrue(inner["permissionDecisionReason"].startswith(PROMPT_WORDING),
                                "the prompt reason starts with the fixed wording: %r" % inner["permissionDecisionReason"])
                self.assertFalse(self.arm_path.exists(), "the arm is claimed (renamed) before the prompt")

    def test_the_ask_also_holds_for_a_powershell_call(self):
        self.arm()
        run = self.run_guard(self.shell(BLOCKED_COMMAND, "PowerShell", tool_use_id=self.next_id()))
        self.assert_asks(run, "PowerShell")

    def test_one_arm_serves_one_tool_call_whatever_the_answer(self):
        self.control_asks("first call")
        again = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()))
        self.assert_blocks(again, "the second call finds no arm")

    def test_a_mode_where_nobody_is_asked_blocks_and_tells_the_person_to_use_their_own_terminal(self):
        self.control_asks("CONTROL")
        for mode in NO_PROMPT_MODES:
            with self.subTest(mode=mode):
                self.arm()
                run = self.run_guard(self.shell(BLOCKED_COMMAND, mode=mode, tool_use_id=self.next_id()))
                self.assert_blocks(run, "mode %r" % (mode,))
                self.assertIn("own terminal", run.err,
                              "Person-present rule: the block text tells the person to run the command in their own terminal")

    def test_a_stale_arm_blocks_and_is_removed(self):
        self.control_asks("CONTROL")
        self.arm(age_seconds=FRESH_SECONDS + 60)
        run = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()))
        self.assert_blocks(run, "an arm older than 15 minutes")
        self.assertFalse(self.arm_path.exists(), "Fresh-arm rule: a stale arm is removed")

    # -- N1: an arm dated in the future is not fresh --------------------------------------------------
    def test_an_arm_dated_one_day_ahead_blocks_and_is_removed(self):
        self.control_asks("CONTROL")
        self.arm(age_seconds=-24 * 3600)
        run = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()))
        self.assert_blocks(run, "Fresh-arm rule: an arm more than 60 seconds in the future")
        self.assertFalse(self.arm_path.exists(), "Fresh-arm rule: the future-dated arm is removed")

    def test_an_arm_thirty_seconds_ahead_still_asks(self):
        self.arm(age_seconds=-30)
        run = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()))
        self.assert_asks(run, "a small clock skew (30 seconds ahead) is tolerated")

    def test_an_arm_just_inside_fifteen_minutes_still_asks(self):
        self.arm(age_seconds=FRESH_SECONDS - 120)
        run = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()))
        self.assert_asks(run, "an arm 13 minutes old")

    def test_a_folder_at_the_arm_path_blocks(self):
        self.control_asks("CONTROL")
        self.arm(kind="folder")
        run = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()))
        self.assert_blocks(run, "a folder is not an arm")

    def test_a_link_at_the_arm_path_blocks(self):
        self.control_asks("CONTROL")
        self.arm(kind="link")
        run = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()))
        self.assert_blocks(run, "a link is not an arm")

    def test_the_retired_variable_no_longer_allows(self):
        run = self.run_guard(self.shell(BLOCKED_COMMAND), env={"CLAUDE_DESTRUCTIVE_DB_OK": "1"})
        self.assert_blocks(run, "CLAUDE_DESTRUCTIVE_DB_OK=1 with no arm (Variable-retired rule)")

    def test_the_retired_variable_does_not_replace_the_prompt_when_armed(self):
        self.arm()
        run = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()),
                             env={"CLAUDE_DESTRUCTIVE_DB_OK": "1"})
        self.assert_asks(run, "with the variable set and the arm present the answer is still a prompt, never a silent allow")

    def test_a_call_that_matches_no_rule_leaves_the_arm_alone_and_usable(self):
        self.arm()
        for command in ("echo hello", "dir", "git status"):
            run = self.run_guard(self.shell(command))
            self.assertEqual(run.rc, 0, "a harmless command is allowed: %s" % run)
            self.assertTrue(self.arm_path.exists(), "Untouched rule: %r must not use up the arm" % command)
        run = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()))
        self.assert_asks(run, "the arm is still usable after harmless calls")

    # -- the arm-write refusal --------------------------------------------------------------------
    def _arm_write_commands(self) -> list[str]:
        slash = str(self.arm_path).replace("\\", "/")
        back = str(self.arm_path).replace("/", "\\")
        return [
            "New-Item -ItemType File -Force '%s'" % back,
            'New-Item -Path "%s" -ItemType File' % slash.replace("database-override.once", "Database-Override.ONCE"),
            "touch %s" % slash,
            "touch '.claude/database-override.once'",
            "echo > .claude/database-override.once",
            ": > '.claude\\Database-Override.Once'",
            "Set-Content -Path \".claude\\database-override.once\" -Value ''",
            "'' | Out-File '.claude/database-override.once'",
            'cp /dev/null ".claude/DATABASE-override.once"',
        ]

    def test_a_shell_call_that_writes_the_arm_is_refused_with_and_without_an_arm(self):
        for command in self._arm_write_commands():
            for tool in ("Bash", "PowerShell"):
                for armed in (False, True):
                    with self.subTest(command=command[:50], tool=tool, armed=armed):
                        if armed:
                            self.arm()
                        elif self.arm_path.exists():
                            self.arm_path.unlink()
                        run = self.run_guard(self.shell(command, tool, tool_use_id=self.next_id()))
                        self.assert_blocks(run, "Arm-write rule: %r" % command)
                        self.assertIn("database-override", run.err.lower(),
                                      "the refusal names the arm file so the person can see why")

    def test_the_refusal_comes_before_every_other_rule_even_when_the_same_command_also_asks(self):
        self.control_asks("CONTROL")
        self.arm()
        command = "touch .claude/database-override.once; " + BLOCKED_COMMAND
        run = self.run_guard(self.shell(command, tool_use_id=self.next_id()))
        self.assert_blocks(run, "a command that writes the arm AND is blocked must be refused, not offered as a prompt")

    def test_a_quoted_path_argument_is_a_write_but_a_search_for_the_name_is_not(self):
        self.control_asks("CONTROL")
        quoted = self.run_guard(self.shell("New-Item -ItemType File '.claude\\database-override.once'", "PowerShell"))
        self.assert_blocks(quoted, "a quoted path argument names the arm as a target")
        self.arm()
        search = self.run_guard(self.shell('rg "database-override.once" README.md', "PowerShell"))
        self.assertEqual(search.rc, 0, "a search pattern only mentions the name: %s" % search)

    # -- W2: a git segment with a real redirection to a named file is not prose ---------------------------
    def test_a_git_command_redirected_to_the_arm_is_refused(self):
        slash = str(self.arm_path).replace("\\", "/")
        for command in (
            'git commit -m "x" > "%s"' % slash,
            'git commit -m "x" >> "%s"' % slash,
            'git tag -m "x" v1 > "%s"' % slash,
            'git notes add -m "x" > "%s"' % slash,
            'git commit -m "x" 2> "%s"' % slash,
            'git commit -m "x" 2>> \'%s\'' % slash,
            'git commit -m "x" >"%s"' % slash,
        ):
            for tool in ("Bash", "PowerShell"):
                for armed in (False, True):
                    with self.subTest(command=command[:34], tool=tool, armed=armed):
                        if armed:
                            self.arm()
                        elif self.arm_path.exists():
                            self.arm_path.unlink()
                        run = self.run_guard(self.shell(command, tool, tool_use_id=self.next_id()))
                        self.assert_blocks(run, "Arm-write rule: %r" % command)
                        self.assertIn("database-override", run.err.lower())

    def test_control_a_git_message_naming_the_arm_with_a_stream_duplication_or_a_pipe_is_allowed(self):
        self.arm()
        for command in (
            'git commit -m "Explain database-override.once in the README" 2>&1 | tail -n 5',
            'git commit -m "Explain database-override.once" 2>&1',
            'git tag -m "database-override.once docs" v1 | cat',
        ):
            for tool in ("Bash", "PowerShell"):
                with self.subTest(command=command[:50], tool=tool):
                    run = self.run_guard(self.shell(command, tool))
                    self.assertEqual(run.rc, 0, "a message that only names the arm is prose: %s" % run)
                    self.assertTrue(self.arm_path.exists(), "a mention must leave the arm alone")


# =====================================================================================================
# The destructive guard's own rows (it alone has the edit tools, the human-only class and fault injection).
# =====================================================================================================
class DestructiveGuardTests(OverrideTestCase, OverrideRows):
    GUARD = DESTRUCTIVE_HOOK

    def _edit_payloads(self, path_text: str, content: str = "x") -> dict[str, dict]:
        return {
            "Write": self.payload("Write", {"file_path": path_text, "content": content}),
            "Edit": self.payload("Edit", {"file_path": path_text, "old_string": "a", "new_string": content or "b"}),
            "MultiEdit": self.payload("MultiEdit", {"file_path": path_text,
                                                    "edits": [{"old_string": "a", "new_string": content or "b"}]}),
            "NotebookEdit": self.payload("NotebookEdit", {"notebook_path": path_text, "new_source": content or "b"}),
        }

    def test_control_a_normal_edit_is_allowed(self):
        self.arm()
        for tool, payload in self._edit_payloads(str(self.project / ".claude" / "switches.json")).items():
            with self.subTest(tool=tool):
                run = self.run_guard(payload)
                self.assertEqual(run.rc, 0, "an edit of another file is allowed: %s" % run)
        near = str(self.project / "docs" / "database-override-notes.md")
        for tool, payload in self._edit_payloads(near).items():
            with self.subTest(tool=tool, near=True):
                self.assertEqual(self.run_guard(payload).rc, 0,
                                 "a name that only resembles the arm (no dot after override) is allowed")

    def test_every_edit_tool_targeting_the_arm_is_refused_in_any_spelling(self):
        spellings = [
            str(self.arm_path),
            str(self.arm_path).replace("\\", "/"),
            str(self.arm_path).replace("/", "\\"),
            str(self.project / ".claude" / "Database-Override.ONCE"),
            ".claude/database-override.once",
            str(self.project / ".claude" / "database-override.claimed-toolu_1"),
            str(self.project / ".claude" / "database-override.once.bak"),
        ]
        for spelling in spellings:
            for tool, payload in self._edit_payloads(spelling).items():
                for armed in (False, True):
                    with self.subTest(path=spelling[-40:], tool=tool, armed=armed):
                        if armed:
                            self.arm()
                        elif self.arm_path.exists():
                            self.arm_path.unlink()
                        self.assert_blocks(self.run_guard(payload), "Arm-write rule, %s" % tool)

    def test_an_edit_tool_writing_empty_content_to_the_arm_is_still_refused(self):
        for tool, payload in self._edit_payloads(str(self.arm_path), content="").items():
            with self.subTest(tool=tool):
                self.assert_blocks(self.run_guard(payload), "an empty write still creates the arm (%s)" % tool)

    def test_the_human_only_class_blocks_even_when_armed(self):
        self.control_asks("CONTROL")
        self.arm()
        run = self.run_guard(self.shell(HUMAN_ONLY_SCRIPT, tool_use_id=self.next_id()))
        self.assert_blocks(run, "No-prompt classes rule: a human-only command never offers the prompt")
        self.assertIn("own terminal", run.err, "a person runs it by hand in their own terminal")

    # -- B1: the no-prompt class is decided from EVERY matched target, not from the chosen block reason --
    def _human_only_combinations(self) -> dict[str, str]:
        disposable = '"Server=(localdb)\\m;Database=App_MigrationVerify_abc"'
        rollback_after_separator = (_EF_UPDATE + " 0 --project src/X.Persistence -- --connection " + disposable)
        return {
            # O12: human-only script + the EF argument-position check
            "O12 human-only script plus the EF argument-position check":
                HUMAN_ONLY_SCRIPT + " && " + rollback_after_separator,
            # O13: human-only script + a row-deleting statement on a protected database
            "O13 human-only script plus a row-deleting statement on a protected database":
                HUMAN_ONLY_SCRIPT + ' && sqlcmd -S "(localdb)\\m" -E -d ' + PROTECTED + ' -Q "' + _ROW_DELETE + ' FROM dbo.T"',
            # O14: an EF forward update + the EF argument-position check
            "O14 EF forward update plus the EF argument-position check":
                _EF_UPDATE + " --project src/X.Persistence && " + rollback_after_separator,
        }

    def test_a_human_only_target_beside_another_blocked_operation_never_offers_the_prompt(self):
        self.control_asks("CONTROL")
        for leftover in self.claim_files():  # the control used its arm up; its claim is not this row's
            leftover.unlink()
        for label, command in self._human_only_combinations().items():
            for tool in ("Bash", "PowerShell"):
                with self.subTest(row=label, tool=tool):
                    self.arm()
                    run = self.run_guard(self.shell(command, tool, mode="default", tool_use_id=self.next_id()))
                    self.assert_blocks(run, "No-prompt classes rule: " + label)
                    self.assertIsNone(run.ask, label + ": no ask JSON")
                    self.assertTrue(self.arm_path.exists(), label + ": the arm is still in place (never claimed)")
                    self.assertEqual(self.claim_files(), [], label + ": no claim file was made")
                    self.assertIn("own terminal", run.err, label + ": the human-only instruction is printed")
                    self.arm_path.unlink()

    def test_the_human_only_class_alone_still_blocks_with_the_arm_in_place(self):
        """O11, kept: a human-only command alone blocks and leaves the arm."""
        self.arm()
        run = self.run_guard(self.shell(HUMAN_ONLY_SCRIPT, tool_use_id=self.next_id()))
        self.assert_blocks(run, "O11 human-only alone")
        self.assertTrue(self.arm_path.exists(), "the arm is still in place")

    # -- W1: the edit tools' target path is normalised before the last-part name test --------------------
    def test_an_edit_tool_target_that_reaches_the_arm_by_dot_parts_is_refused(self):
        forward = str(self.arm_path).replace("\\", "/")
        back = str(self.arm_path).replace("/", "\\")
        spellings = [forward + "/.", forward + "/x/..", back + "\\.", back + "\\x\\..",
                     forward + "/./", back + "\\x\\..\\", forward + "/x/y/../..",
                     forward + ".", forward + " ", forward + "/. "]
        for spelling in spellings:
            for tool, payload in self._edit_payloads(spelling).items():
                for armed in (False, True):
                    with self.subTest(path=spelling[-24:], tool=tool, armed=armed):
                        if armed:
                            self.arm()
                        elif self.arm_path.exists():
                            self.arm_path.unlink()
                        self.assert_blocks(self.run_guard(payload), "Arm-write rule, normalised path, %s" % tool)

    def test_control_an_edit_that_climbs_out_of_the_arm_to_another_file_is_allowed(self):
        """The normalised last part of <p>/.claude/database-override.once/../notes.md is notes.md."""
        base = str(self.project / ".claude")
        for spelling in (base.replace("\\", "/") + "/database-override.once/../notes.md",
                         base.replace("/", "\\") + "\\database-override.once\\..\\notes.md"):
            for tool, payload in self._edit_payloads(spelling).items():
                with self.subTest(path=spelling[-40:], tool=tool):
                    run = self.run_guard(payload)
                    self.assertEqual(run.rc, 0, "its normalised last part is notes.md: %s" % run)

    def test_an_injected_guard_fault_blocks_even_when_armed(self):
        self.control_asks("CONTROL")
        self.arm()
        run = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()),
                             env={"DB_GUARD_FAULT_INJECTION": "binder"})
        self.assert_blocks(run, "No-prompt classes rule: the internal-error path never offers the prompt")
        self.assertNotIn("CLAUDE_DESTRUCTIVE_DB_OK", run.err,
                         "the block text must not name the retired variable as a way out")

    def test_the_block_text_no_longer_names_the_retired_variable_and_prints_the_arm_commands(self):
        run = self.run_guard(self.shell(BLOCKED_COMMAND))
        self.assertEqual(run.rc, 2)
        self.assertNotIn("CLAUDE_DESTRUCTIVE_DB_OK", run.err, "Variable-retired rule: no variable is named as a way out")
        self.assertIn("database-override.once", run.err, "the block text says how a person arms the next command")
        self.assertIn("New-Item", run.err, "a PowerShell command for the person's own terminal")
        self.assertIn("touch", run.err, "a POSIX command for the person's own terminal")

    def test_a_crafted_target_with_comment_markers_is_neutralised_in_the_reason(self):
        self.control_asks("CONTROL")
        crafted = "x /* disposable test copy */ -- safe # ok " + "A" * 120 + "\x07 tail"
        command = 'sqlcmd -S "(localdb)\\m" -E -Q "' + _V + " [" + crafted + ']"'
        self.arm()
        run = self.run_guard(self.shell(command, tool_use_id=self.next_id()))
        inner = self.assert_asks(run, "a crafted target")
        reason = inner["permissionDecisionReason"]
        self.assertTrue(reason.startswith(PROMPT_WORDING), "fixed wording first: %r" % reason)
        for marker in ("/*", "*/", "--", "#"):
            self.assertNotIn(marker, reason, "Plain-reason rule: the comment marker %r must be removed from any target" % marker)
        self.assertFalse([c for c in reason if ord(c) < 32 and c not in "\n"], "control characters are removed")
        self.assertNotIn("A" * 61, reason, "each target is cut to 60 characters")
        if "AAAA" in reason:
            self.assertIn("as written in the command", reason, "a target shown in the reason is labelled")


class ReadonlyGuardTests(OverrideTestCase, OverrideRows):
    GUARD = READONLY_HOOK


# =====================================================================================================
# Two guards, one tool call.
# =====================================================================================================
class SharedClaimTests(OverrideTestCase):

    def both(self, command: str, tool_use_id: str | None, *, first: Path, second: Path) -> tuple[Run, Run]:
        payload = self.shell(command, tool_use_id=tool_use_id)
        return self.run_guard(payload, guard=first), self.run_guard(payload, guard=second)

    def test_two_guards_on_one_tool_use_id_both_ask_in_either_order(self):
        for first, second in ((DESTRUCTIVE_HOOK, READONLY_HOOK), (READONLY_HOOK, DESTRUCTIVE_HOOK)):
            with self.subTest(first=first.name):
                self.arm()
                a, b = self.both(BLOCKED_COMMAND, "toolu_shared", first=first, second=second)
                self.assert_asks(a, "the first guard (" + first.name + ")")
                self.assert_asks(b, "the second guard (" + second.name + ") accepts the first guard's claim")
                self.assertFalse(self.arm_path.exists())
                self.assertEqual([p.name for p in self.claim_files()], ["database-override.claimed-toolu_shared"],
                                 "Arm claim: the arm was renamed to the claim carrying the tool call identifier")
                for p in self.claim_files():
                    p.unlink()

    def test_a_claim_for_another_tool_call_does_not_serve_this_one(self):
        self.arm()
        self.assert_asks(self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id="toolu_one"), guard=DESTRUCTIVE_HOOK),
                         "the first call")
        other = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id="toolu_two"), guard=READONLY_HOOK)
        self.assert_blocks(other, "a different tool call finds neither an arm nor its own claim")

    def test_with_no_tool_use_id_the_second_guard_blocks(self):
        self.control_asks("CONTROL")
        self.arm()
        _, second = self.both(BLOCKED_COMMAND, None, first=DESTRUCTIVE_HOOK, second=READONLY_HOOK)
        self.assert_blocks(second, "Shared-claim rule: with no identifier in the payload the second guard blocks")


# =====================================================================================================
# The refusal when the guard defers, and with the helper removed.
# =====================================================================================================
class DeferenceTests(unittest.TestCase):

    def world(self, spec) -> DeferenceWorld:
        w = DeferenceWorld(spec)
        self.addCleanup(w.cleanup)
        w.register()
        started = w.start_session("startup")
        self.assertEqual(started.returncode, 0, "the session-start hook must exit 0")
        return w

    def arm(self, w: DeferenceWorld) -> Path:
        path = w.project / ".claude" / "database-override.once"
        path.write_bytes(b"")
        return path

    def write_payload(self, w: DeferenceWorld, command: str, tool="Bash") -> dict:
        return {"tool_name": tool, "tool_input": {"command": command}, "cwd": str(w.project),
                "session_id": DEFERENCE_SESSION, "permission_mode": "default", "tool_use_id": "toolu_defer"}

    def _rows(self, spec):
        w = self.world(spec)
        control = w.run_guard()
        self.assertEqual(control.returncode, 0, "CONTROL: the registered project copy makes the plugin copy defer")
        self.assertEqual(len(w.deferred_records()), 1, "CONTROL: one deferred record")
        w.clear_log()
        arm = self.arm(w)
        touch = "touch '%s'" % str(arm).replace("\\", "/")
        proc = w.run_guard(self.write_payload(w, touch))
        return w, arm, proc

    def test_the_destructive_guard_refuses_an_arm_write_even_when_it_defers(self):
        w, arm, proc = self._rows(DEFERENCE_DESTRUCTIVE)
        self.assertEqual(proc.returncode, 2,
                         "Arm-write rule runs before Guard deference. stderr: %s" % proc.stderr.decode("utf-8", "replace")[:300])
        self.assertEqual(w.deferred_records(), [], "a refusal is not a deferral")

    def test_the_readonly_guard_refuses_an_arm_write_even_when_it_defers(self):
        w, arm, proc = self._rows(DEFERENCE_READONLY)
        self.assertEqual(proc.returncode, 2,
                         "Arm-write rule runs before Guard deference. stderr: %s" % proc.stderr.decode("utf-8", "replace")[:300])
        self.assertEqual(w.deferred_records(), [], "a refusal is not a deferral")

    def test_the_destructive_guard_refuses_an_edit_tool_write_of_the_arm_when_it_defers(self):
        w = self.world(DEFERENCE_DESTRUCTIVE)
        arm = self.arm(w)
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(arm), "content": "x"},
                   "cwd": str(w.project), "session_id": DEFERENCE_SESSION}
        proc = w.run_guard(payload)
        self.assertEqual(proc.returncode, 2, "Write of the arm is refused even by a deferring guard")

    def test_control_a_deferring_guard_leaves_a_fresh_arm_untouched(self):
        for spec in (DEFERENCE_DESTRUCTIVE, DEFERENCE_READONLY):
            with self.subTest(guard=spec.hook_name):
                w = self.world(spec)
                arm = self.arm(w)
                proc = w.run_guard()
                self.assertEqual(proc.returncode, 0, "the plugin copy defers")
                self.assertEqual(len(w.deferred_records()), 1, "and records the deferral")
                self.assertTrue(arm.exists(), "a guard honours the arm only when it does not defer")


class InlineNameTestCopyTests(OverrideTestCase):
    """The guards keep an inline copy of the name test; with the helper removed it must still refuse."""

    def setUp(self):
        super().setUp()
        self.plugin = self.tmp / "plugin-without-helper"
        hooks = self.plugin / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        for src in HOOKS_SRC.iterdir():
            if src.is_file() and src.suffix in (".py", ".json") and src.name != "_switches.py":
                shutil.copy2(src, hooks / src.name)
        self.assertFalse((hooks / "_switches.py").exists(), "the helper is removed from this copy")
        self.hooks = hooks

    def test_both_guards_refuse_a_shell_write_of_the_arm_with_the_helper_removed(self):
        command = "touch .claude/database-override.once"
        for name in ("db-destructive-guard.py", "db-research-readonly-guard.py"):
            for tool in ("Bash", "PowerShell"):
                with self.subTest(guard=name, tool=tool):
                    self.assert_blocks(self.run_guard(self.shell(command, tool), guard=self.hooks / name),
                                       "inline name-test copy in " + name)

    def test_the_destructive_guard_refuses_an_edit_tool_write_of_the_arm_with_the_helper_removed(self):
        for tool, tool_input in (("Write", {"file_path": str(self.arm_path), "content": "x"}),
                                 ("Edit", {"file_path": str(self.arm_path), "old_string": "a", "new_string": "b"}),
                                 ("NotebookEdit", {"notebook_path": str(self.arm_path), "new_source": "b"})):
            with self.subTest(tool=tool):
                self.assert_blocks(self.run_guard(self.payload(tool, tool_input), guard=self.hooks / "db-destructive-guard.py"),
                                   "inline name-test copy, tool " + tool)

    def test_the_destructive_guard_refuses_a_dot_part_edit_path_with_the_helper_removed(self):
        """W1 fallback row: the guard's inline copy of the name test normalises the path itself."""
        forward = str(self.arm_path).replace("\\", "/")
        back = str(self.arm_path).replace("/", "\\")
        for spelling in (forward + "/.", forward + "/x/..", back + "\\.", back + "\\x\\.."):
            for tool, tool_input in (("Write", {"file_path": spelling, "content": "x"}),
                                     ("NotebookEdit", {"notebook_path": spelling, "new_source": "b"})):
                with self.subTest(path=spelling[-20:], tool=tool):
                    self.assert_blocks(self.run_guard(self.payload(tool, tool_input),
                                                      guard=self.hooks / "db-destructive-guard.py"),
                                       "inline normalising copy, tool " + tool)
        control = self.run_guard(self.payload("Write", {"file_path": forward + "/../notes.md", "content": "x"}),
                                 guard=self.hooks / "db-destructive-guard.py")
        self.assertEqual(control.rc, 0, "CONTROL: the normalised last part is notes.md: %s" % control)

    def test_with_the_helper_removed_an_armed_command_gets_no_override_and_an_arm_write_is_still_refused(self):
        self.arm()
        run = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()),
                             guard=self.hooks / "db-destructive-guard.py")
        self.assert_blocks(run, "Guard fallback mode: a missing claim binding means no override")
        refused = self.run_guard(self.shell("touch .claude/database-override.once"),
                                 guard=self.hooks / "db-destructive-guard.py")
        self.assert_blocks(refused, "and the inline name test still refuses the write")


# =====================================================================================================
# B1 and P1 (t10 re-review): where a human-only script stands in the command.
#
# A human-only script that is INVOKED, after quoted text or not, is the no-prompt class: never a prompt,
# and with no arm never an allow. Every destructive statement below is built from parts, and every row
# uses the script spelled WITH its folder (the defect needs a separator before the name): forward slashes
# in the Bash rows, backslashes in the PowerShell rows. Each row runs in its own fresh project, with its
# own arm (never both guards on one arm).
# =====================================================================================================
SCRIPT_FWD = HUMAN_ONLY_SCRIPT
SCRIPT_BACK = HUMAN_ONLY_SCRIPT.replace("/", "\\")
RESTORE_FWD = "tools/db-protection/restore-latest.cmd"
RESTORE_BACK = RESTORE_FWD.replace("/", "\\")
RECOVER_FLAG = "--recover-missing-dev-db"
#: A row delete on a protected database (t4 probe O13).
PROTECTED_ROW_DELETE = 'sqlcmd -S "(localdb)\\m" -E -d ' + PROTECTED + ' -Q "' + _ROW_DELETE + ' FROM dbo.T"'
#: The removal of a NON-disposable database through sqlcmd -Q (t10 probe H7).
OTHER_DATABASE_REMOVAL = 'sqlcmd -S localhost -Q "' + _V + ' Orders"'
#: A write the read-only guard exempts today: a disposable-named database, no protected target.
DISPOSABLE_NAME = PROTECTED + "_ForceAction_Test_f4dd1c3cebce4c44922ce4876cff18d3"
DISPOSABLE_WRITE = ('sqlcmd -S "(localdb)\\m" -E -d ' + DISPOSABLE_NAME
                    + ' -Q "INSERT INTO StrategyRuns (Id) VALUES (NEWID())"')
DISPOSABLE_REMOVAL = 'sqlcmd -S "(localdb)\\m" -E -Q "' + _V + " [" + DISPOSABLE_NAME + ']"'

#: (row id, tool, command built from the project folder). A shape that exists in one shell only is
#: written once, in that shell.
ARMED_ROWS = [
    ("O13", "Bash", lambda p: PROTECTED_ROW_DELETE + " ; " + SCRIPT_FWD),
    ("O13e", "PowerShell", lambda p: PROTECTED_ROW_DELETE + "; " + SCRIPT_BACK),
    ("H7", "Bash", lambda p: OTHER_DATABASE_REMOVAL + " ; " + SCRIPT_FWD),
    ("H7", "PowerShell", lambda p: OTHER_DATABASE_REMOVAL + "; " + SCRIPT_BACK),
    ("H6", "Bash", lambda p: 'echo "a" ; ' + SCRIPT_FWD),
    ("H6", "PowerShell", lambda p: 'echo "a" ; ' + SCRIPT_BACK),
    ("cd", "Bash", lambda p: 'cd "' + p + '" && ' + SCRIPT_FWD),
    ("cd", "PowerShell", lambda p: 'cd "' + p + '" && ' + SCRIPT_BACK),
    ("write-host", "PowerShell", lambda p: "Write-Host 'x'; " + SCRIPT_BACK),
]
#: The rows of ARMED_ROWS whose own destructive statement makes the read-only guard ask.
ASKING_IDS = {"O13", "O13e", "H7"}
UNARMED_ROWS = [
    ("H1", "Bash", lambda p: 'echo "start" ; ' + SCRIPT_FWD),
    ("H1", "PowerShell", lambda p: 'echo "start" ; ' + SCRIPT_BACK),
    ("H3", "PowerShell", lambda p: "Write-Host 'x'; " + SCRIPT_BACK),
    ("H4", "Bash", lambda p: 'cd "' + p + '" && ' + SCRIPT_FWD),
    ("H4", "PowerShell", lambda p: 'cd "' + p + '" && ' + SCRIPT_BACK),
    ("H5", "Bash", lambda p: 'echo "a" && ' + RESTORE_FWD + " " + RECOVER_FLAG),
    ("H5", "PowerShell", lambda p: 'echo "a" && ' + RESTORE_BACK + " " + RECOVER_FLAG),
]
#: Controls that block at the parent tip already: a human-only script that is first, or that stands
#: inside the quoted argument of a known launcher.
LAUNCHER_ROWS = [
    ("bash-c", "Bash", lambda p: 'bash -c "cd x; ' + SCRIPT_FWD + '"'),
    ("cmd-c", "Bash", lambda p: 'cmd /c "echo a & ' + SCRIPT_FWD + '"'),
    ("cmd-c", "PowerShell", lambda p: 'cmd /c "echo a & ' + SCRIPT_BACK + '"'),
    ("powershell-command", "Bash", lambda p: 'powershell -Command "Write-Host x; ' + SCRIPT_FWD + '"'),
    ("powershell-command", "PowerShell", lambda p: 'powershell -Command "Write-Host x; ' + SCRIPT_BACK + '"'),
]
#: Must stay allowed: the script named inside quotes, or as an argument of another command.
MENTION_ROWS = [
    ("commit-message", "Bash", lambda p: 'git commit -m "docs: ' + SCRIPT_FWD + ' is run by a person"'),
    ("commit-message", "PowerShell", lambda p: 'git commit -m "docs: ' + SCRIPT_BACK + ' is run by a person"'),
    ("echo-text", "Bash", lambda p: 'echo "run ' + SCRIPT_FWD + ' in your own terminal"'),
    ("echo-text", "PowerShell", lambda p: 'echo "run ' + SCRIPT_BACK + ' in your own terminal"'),
    ("grep-pattern", "Bash", lambda p: 'grep -rn "' + SCRIPT_FWD + '" docs'),
    ("grep-pattern", "PowerShell", lambda p: 'Select-String -Pattern "' + SCRIPT_BACK + '" docs'),
    ("pr-body", "Bash", lambda p: 'gh pr create --title "Docs" --body "Run ' + SCRIPT_FWD + ' by hand; then go on."'),
    ("pr-body", "PowerShell", lambda p: 'gh pr create --title "Docs" --body "Run ' + SCRIPT_BACK + ' by hand; then go on."'),
    ("argument-git-add", "Bash", lambda p: "git add " + SCRIPT_FWD),
    ("argument-cat", "Bash", lambda p: "cat " + SCRIPT_FWD),
    ("argument-type", "PowerShell", lambda p: "Get-Content " + SCRIPT_BACK),
    ("argument-after-quote", "Bash", lambda p: 'echo "a" ; echo ' + SCRIPT_FWD),
    ("argument-after-quote", "PowerShell", lambda p: 'echo "a" ; Get-Content ' + SCRIPT_BACK),
    ("argument-after-flag", "Bash", lambda p: 'git commit -m "x" -- ' + SCRIPT_FWD),
]


def _add_rows(cls, prefix: str, rows, body) -> None:
    """One test method per row (so one row = one fresh project and one arm)."""
    for rid, tool, factory in rows:
        def make(rid=rid, tool=tool, factory=factory):
            def test(self):
                body(self, rid, tool, factory(str(self.project)))
            return test
        name = "test_%s_%s_%s" % (prefix, rid.lower().replace("-", "_"), tool.lower())
        setattr(cls, name, make())


class HumanOnlyPlacementTests(OverrideTestCase):
    """The destructive guard alone (B1 and P1)."""

    GUARD = DESTRUCTIVE_HOOK

    def _armed_blocks(self, rid: str, tool: str, command: str) -> None:
        self.arm()
        run = self.run_guard(self.shell(command, tool, mode="default", tool_use_id=self.next_id()))
        why = "%s (%s): a human-only script that is invoked is the no-prompt class" % (rid, tool)
        self.assert_blocks(run, "No-prompt classes rule, " + why)
        self.assertIsNone(run.ask, why + ": no ask JSON")
        self.assertTrue(self.arm_path.exists(), why + ": the arm is still in place (never claimed)")
        self.assertEqual(self.claim_files(), [], why + ": no claim file was made")
        self.assertIn("own terminal", run.err, why + ": the human-only instruction is printed")

    def _unarmed_blocks(self, rid: str, tool: str, command: str) -> None:
        run = self.run_guard(self.shell(command, tool, mode="default", tool_use_id=self.next_id()))
        why = "%s (%s), no arm" % (rid, tool)
        self.assert_blocks(run, "a human-only script that is invoked is never run by an agent: " + why)
        self.assertIn("own terminal", run.err, why + ": the human-only instruction is printed")

    def _control_blocks(self, rid: str, tool: str, command: str) -> None:
        run = self.run_guard(self.shell(command, tool, mode="default", tool_use_id=self.next_id()))
        self.assert_blocks(run, "invoked inside a launcher argument, %s (%s)" % (rid, tool))

    def _control_allowed(self, rid: str, tool: str, command: str) -> None:
        run = self.run_guard(self.shell(command, tool, mode="default", tool_use_id=self.next_id()))
        self.assertEqual(run.rc, 0, "a mention is not an invocation, %s (%s): %s" % (rid, tool, run))

    def test_control_o11_the_script_alone_blocks_armed_and_unarmed(self):
        for tool, script in (("Bash", SCRIPT_FWD), ("PowerShell", SCRIPT_BACK)):
            for armed in (False, True):
                with self.subTest(tool=tool, armed=armed):
                    if armed:
                        self.arm()
                    run = self.run_guard(self.shell(script, tool, tool_use_id=self.next_id()))
                    self.assert_blocks(run, "O11")
                    self.assertEqual(self.arm_path.exists(), armed)
                    if armed:
                        self.arm_path.unlink()

    def test_control_o13b_the_script_first_blocks_with_the_arm_kept(self):
        for tool, script, sep in (("Bash", SCRIPT_FWD, " ; "), ("PowerShell", SCRIPT_BACK, "; ")):
            with self.subTest(tool=tool):
                self.arm()
                run = self.run_guard(self.shell(script + sep + PROTECTED_ROW_DELETE, tool, tool_use_id=self.next_id()))
                self.assert_blocks(run, "O13b")
                self.assertIsNone(run.ask)
                self.assertTrue(self.arm_path.exists(), "O13b: the arm is kept")
                self.arm_path.unlink()


_add_rows(HumanOnlyPlacementTests, "armed", ARMED_ROWS, HumanOnlyPlacementTests._armed_blocks)
_add_rows(HumanOnlyPlacementTests, "unarmed", UNARMED_ROWS, HumanOnlyPlacementTests._unarmed_blocks)
_add_rows(HumanOnlyPlacementTests, "control_launcher", LAUNCHER_ROWS, HumanOnlyPlacementTests._control_blocks)
_add_rows(HumanOnlyPlacementTests, "control_mention", MENTION_ROWS, HumanOnlyPlacementTests._control_allowed)


# =====================================================================================================
# Block 13 (t12 round-three review): findings B1, P1 and P2.
#
# B1 and P1: the quote scanner used ONE escape model for both shells. Each row below is a spelling where a
# human-only script is invoked after a quote that the shell closes differently from the scanner (a
# trailing backslash before the closing quote, an escaped quote outside quotes, a backtick escape, an
# ANSI-C quoted string). P2: the script follows a keyword or prefix command (then, do, else, elif, !, time,
# env, nohup, exec, command, builtin, nice, timeout, xargs, sudo, a NAME=value assignment) or a backtick.
# Row ids are the t12 ids (t12's P1 and P2 are not t4's shared-claim probes P1 to P9). Destructive
# statements are the ones above, built from parts.
# =====================================================================================================
B1_ARMED_ROWS = [
    ("N1a", "PowerShell", lambda p: 'Set-Location "C:\\work\\"; ' + SCRIPT_BACK),
    ("N1b", "PowerShell", lambda p: PROTECTED_ROW_DELETE + '; cd "C:\\w\\"; ' + SCRIPT_BACK),
    ("N2a", "Bash", lambda p: OTHER_DATABASE_REMOVAL + ' ; cd "C:\\\\w\\\\" && ' + SCRIPT_FWD),
    ("K4", "Bash", lambda p: OTHER_DATABASE_REMOVAL + ' ; echo \\" ; ' + SCRIPT_FWD),
    ("K5", "PowerShell", lambda p: OTHER_DATABASE_REMOVAL + '; Write-Host `" ; ' + SCRIPT_BACK),
    ("K6", "PowerShell", lambda p: OTHER_DATABASE_REMOVAL + '; cd "' + p + '\\"; ' + SCRIPT_BACK),
]
B1_UNARMED_ROWS = [
    ("N1", "PowerShell", lambda p: 'Set-Location "C:\\work\\"; ' + SCRIPT_BACK),
    ("N1c", "PowerShell", lambda p: 'Write-Host "C:\\work\\"; ' + SCRIPT_BACK),
    ("N15", "PowerShell", lambda p: 'cd "' + p + '\\"; ' + SCRIPT_BACK),
    ("N5", "PowerShell", lambda p: 'Write-Host `" ; ' + SCRIPT_BACK),
    ("N6", "PowerShell", lambda p: 'Write-Host "a``"; ' + SCRIPT_BACK),
    ("N2", "Bash", lambda p: 'cd "C:\\\\work\\\\" && ' + SCRIPT_FWD),
    ("N2b", "Bash", lambda p: 'echo "a\\\\" ; ' + SCRIPT_FWD),
    ("N3", "Bash", lambda p: 'echo \\" ; ' + SCRIPT_FWD),
    ("N4", "Bash", lambda p: "echo $'a\\'b' ; " + SCRIPT_FWD),
]
#: P2, copied from t12: keyword, prefix-command and backtick positions.
P2_ARMED_ROWS = [
    ("K1", "Bash", lambda p: OTHER_DATABASE_REMOVAL + " ; time " + SCRIPT_FWD),
    ("K2", "Bash", lambda p: OTHER_DATABASE_REMOVAL + " ; if true; then " + SCRIPT_FWD + "; fi"),
    ("K3", "Bash", lambda p: OTHER_DATABASE_REMOVAL + " ; echo `" + SCRIPT_FWD + "`"),
]
P2_UNARMED_ROWS = [
    ("N7", "Bash", lambda p: "echo `" + SCRIPT_FWD + "`"),
    ("N8", "Bash", lambda p: "if true; then " + SCRIPT_FWD + "; fi"),
    ("N9", "Bash", lambda p: "time " + SCRIPT_FWD),
    ("N10", "Bash", lambda p: "env " + SCRIPT_FWD),
    ("N11", "Bash", lambda p: "nohup " + SCRIPT_FWD),
    ("N12", "Bash", lambda p: "for i in 1; do " + SCRIPT_FWD + "; done"),
    ("N13", "Bash", lambda p: "! " + SCRIPT_FWD),
    # Constructed: one per remaining word, and one per valued option.
    ("else", "Bash", lambda p: "if false; then :; else " + SCRIPT_FWD + "; fi"),
    ("elif", "Bash", lambda p: "if false; then :; elif " + SCRIPT_FWD + "; then :; fi"),
    ("command", "Bash", lambda p: "command " + SCRIPT_FWD),
    ("builtin", "Bash", lambda p: "builtin " + SCRIPT_FWD),
    ("nice", "Bash", lambda p: "nice " + SCRIPT_FWD),
    ("timeout", "Bash", lambda p: "timeout 5 " + SCRIPT_FWD),
    ("xargs", "Bash", lambda p: "echo x | xargs " + SCRIPT_FWD),
    ("sudo", "Bash", lambda p: "sudo " + SCRIPT_FWD),
    ("assignment", "Bash", lambda p: "FOO=bar " + SCRIPT_FWD),
    ("nice-n", "Bash", lambda p: "nice -n 10 " + SCRIPT_FWD),
    ("sudo-u", "Bash", lambda p: "sudo -u root " + SCRIPT_FWD),
    ("env-u", "Bash", lambda p: "env -u NAME " + SCRIPT_FWD),
    ("timeout-s", "Bash", lambda p: "timeout -s KILL 5 " + SCRIPT_FWD),
]
#: Named controls: block at the parent tip already (exec is an invoking word today).
P2_BLOCKING_CONTROLS = [
    ("exec", "Bash", lambda p: "exec " + SCRIPT_FWD),
]
#: Must stay allowed: a lookup, the same words as plain arguments, a name after one of them in a message.
P2_MENTION_CONTROLS = [
    ("command-v", "Bash", lambda p: "command -v " + SCRIPT_FWD),
    ("command-upper-v", "Bash", lambda p: "command -V " + SCRIPT_FWD),
    ("echo-then", "Bash", lambda p: "echo then " + SCRIPT_FWD),
    ("grep-time", "Bash", lambda p: "grep -n time " + SCRIPT_FWD),
    ("message-after-time", "Bash", lambda p: 'git commit -m "docs: time ' + SCRIPT_FWD + ' by hand"'),
    ("message-after-then", "Bash", lambda p: 'git commit -m "docs: if x; then ' + SCRIPT_FWD + '; fi"'),
    ("message-after-sudo", "Bash", lambda p: 'git commit -m "sudo ' + SCRIPT_FWD + '"'),
]

_add_rows(HumanOnlyPlacementTests, "b1_armed", B1_ARMED_ROWS, HumanOnlyPlacementTests._armed_blocks)
_add_rows(HumanOnlyPlacementTests, "b1_unarmed", B1_UNARMED_ROWS, HumanOnlyPlacementTests._unarmed_blocks)
_add_rows(HumanOnlyPlacementTests, "p2_armed", P2_ARMED_ROWS, HumanOnlyPlacementTests._armed_blocks)
_add_rows(HumanOnlyPlacementTests, "p2_unarmed", P2_UNARMED_ROWS, HumanOnlyPlacementTests._unarmed_blocks)
_add_rows(HumanOnlyPlacementTests, "p2_control_blocking", P2_BLOCKING_CONTROLS, HumanOnlyPlacementTests._control_blocks)
_add_rows(HumanOnlyPlacementTests, "p2_control_mention", P2_MENTION_CONTROLS, HumanOnlyPlacementTests._control_allowed)


class HumanOnlyPlacementReadonlyPinTests(OverrideTestCase):
    """L1 (accepted): the read-only guard has no human-only class and is not changed by this block.
    These rows PIN today's behaviour, so they are expected to pass at the parent tip and at the head."""

    GUARD = READONLY_HOOK

    def _armed(self, rid: str, tool: str, command: str) -> None:
        self.arm()
        run = self.run_guard(self.shell(command, tool, mode="default", tool_use_id="toolu_pin"))
        if rid in ASKING_IDS:
            self.assert_asks(run, "pin %s (%s): the read-only guard asks on its own statement" % (rid, tool))
            self.assertFalse(self.arm_path.exists(), "pin: the arm was renamed to the claim")
            self.assertEqual([p.name for p in self.claim_files()], ["database-override.claimed-toolu_pin"])
        else:
            self.assertEqual(run.rc, 0, "pin %s (%s): nothing for the read-only guard to block: %s" % (rid, tool, run))
            self.assertIsNone(run.ask)
            self.assertTrue(self.arm_path.exists(), "pin: the arm is kept")

    def _unarmed(self, rid: str, tool: str, command: str) -> None:
        run = self.run_guard(self.shell(command, tool, mode="default", tool_use_id="toolu_pin"))
        self.assertEqual(run.rc, 0, "pin %s (%s), no arm: %s" % (rid, tool, run))


_add_rows(HumanOnlyPlacementReadonlyPinTests, "pin_armed", ARMED_ROWS, HumanOnlyPlacementReadonlyPinTests._armed)
_add_rows(HumanOnlyPlacementReadonlyPinTests, "pin_unarmed", UNARMED_ROWS, HumanOnlyPlacementReadonlyPinTests._unarmed)


# =====================================================================================================
# I1: both database guards read db-destructive-guard.rules.json through the regular-file check.
# =====================================================================================================
SHORT_TIMEOUT = 15
SHARE_TARGET = "\\\\192.0.2.1\\share\\db-destructive-guard.rules.json"  # TEST-NET-1: nothing answers


class _RulesFileRows:
    """Rows run once per guard and once per way the guard reaches the check (the helper, a deleted
    helper, a stale helper). A subclass sets GUARD_NAME, STRICT (a command the strict default blocks that
    the loaded rules also block or allow), LOADED (a command only a loaded rules file lets through)."""

    GUARD_NAME: str
    STRICT_COMMAND: str       # blocked with the rules file unreadable
    LOADED_COMMAND: str       # allowed with the regular rules file in place, blocked without it

    @property
    def rules_path(self) -> Path:
        return self.project / ".claude" / "hooks" / "db-destructive-guard.rules.json"

    def guard_path(self) -> Path:
        return HOOKS_SRC / self.GUARD_NAME

    def _run(self, command: str) -> Run:
        return self.run_guard(self.shell(command, tool_use_id=self.next_id()), guard=self.guard_path(),
                              timeout=SHORT_TIMEOUT)

    def _strict(self, why: str) -> None:
        run = self._run(self.STRICT_COMMAND)
        self.assert_blocks(run, "strict default, " + why)

    def test_a_regular_rules_file_still_loads(self):
        run = self._run(self.LOADED_COMMAND)
        self.assertEqual(run.rc, 0, "the regular rules file loads as before: %s" % run)

    def test_without_a_rules_file_the_strict_default_blocks_the_loaded_command(self):
        """CONTROL for the row above: with no rules file the same command is blocked."""
        self.rules_path.unlink()
        self.assert_blocks(self._run(self.LOADED_COMMAND), "strict default: the exemption is withdrawn")

    @unittest.skipUnless(sys.platform == "win32", SKIP_POSIX_PIPES)
    def test_a_link_to_a_listening_pipe_in_the_dot_spelling_takes_the_strict_default(self):
        self.rules_path.unlink()
        make_pipe_link(self, self.rules_path, "dot")
        self._strict("pipe link, dot spelling")
        self.assert_blocks(self._run(self.LOADED_COMMAND), "the exemption is withdrawn too")

    @unittest.skipUnless(sys.platform == "win32", SKIP_POSIX_PIPES)
    def test_a_link_to_a_listening_pipe_in_the_question_mark_spelling_takes_the_strict_default(self):
        self.rules_path.unlink()
        make_pipe_link(self, self.rules_path, "question-mark")
        self._strict("pipe link, question-mark spelling")
        self.assert_blocks(self._run(self.LOADED_COMMAND), "the exemption is withdrawn too")

    @unittest.skipUnless(sys.platform == "win32", SKIP_POSIX_PIPES)
    def test_a_link_to_a_server_share_takes_the_strict_default(self):
        self.rules_path.unlink()
        try:
            os.symlink(SHARE_TARGET, self.rules_path)
        except (OSError, NotImplementedError):
            self.skipTest(SKIP_NO_SYMLINK)
        self._strict("link to a server share (accepted fail-closed behaviour, Failure Modes I1)")
        self.assert_blocks(self._run(self.LOADED_COMMAND), "the exemption is withdrawn too")


class _PluginCopyMixin:
    """The guard runs from a copy of the hooks folder whose helper is deleted or stale."""

    HELPER: str   # "deleted" or "stale"

    def setUp(self):
        super().setUp()
        hooks = self.tmp / "plugin-copy" / ".claude" / "hooks"
        hooks.mkdir(parents=True)
        for src in HOOKS_SRC.iterdir():
            if not (src.is_file() and src.suffix in (".py", ".json")):
                continue
            if src.name == "_switches.py":
                if self.HELPER == "deleted":
                    continue
                # A stale helper: it imports and still has the claim function, but predates the reader.
                text = src.read_text(encoding="utf-8")
                (hooks / src.name).write_text(
                    text + "\n\nglobals().pop('read_regular_file_bytes', None)\n", encoding="utf-8")
                continue
            shutil.copy2(src, hooks / src.name)
        self.copy_hooks = hooks

    def guard_path(self) -> Path:
        return self.copy_hooks / self.GUARD_NAME


class DestructiveGuardRulesFileTests(_RulesFileRows, OverrideTestCase):
    GUARD = DESTRUCTIVE_HOOK
    GUARD_NAME = "db-destructive-guard.py"
    STRICT_COMMAND = OTHER_DATABASE_REMOVAL
    LOADED_COMMAND = DISPOSABLE_REMOVAL


class ReadonlyGuardRulesFileTests(_RulesFileRows, OverrideTestCase):
    GUARD = READONLY_HOOK
    GUARD_NAME = "db-research-readonly-guard.py"
    STRICT_COMMAND = DISPOSABLE_WRITE
    LOADED_COMMAND = DISPOSABLE_WRITE


class DestructiveGuardRulesFallbackDeletedHelperTests(_PluginCopyMixin, _RulesFileRows, OverrideTestCase):
    HELPER = "deleted"
    GUARD = DESTRUCTIVE_HOOK
    GUARD_NAME = "db-destructive-guard.py"
    STRICT_COMMAND = OTHER_DATABASE_REMOVAL
    LOADED_COMMAND = DISPOSABLE_REMOVAL


class DestructiveGuardRulesFallbackStaleHelperTests(_PluginCopyMixin, _RulesFileRows, OverrideTestCase):
    HELPER = "stale"
    GUARD = DESTRUCTIVE_HOOK
    GUARD_NAME = "db-destructive-guard.py"
    STRICT_COMMAND = OTHER_DATABASE_REMOVAL
    LOADED_COMMAND = DISPOSABLE_REMOVAL


class ReadonlyGuardRulesFallbackDeletedHelperTests(_PluginCopyMixin, _RulesFileRows, OverrideTestCase):
    HELPER = "deleted"
    GUARD = READONLY_HOOK
    GUARD_NAME = "db-research-readonly-guard.py"
    STRICT_COMMAND = DISPOSABLE_WRITE
    LOADED_COMMAND = DISPOSABLE_WRITE


class ReadonlyGuardRulesFallbackStaleHelperTests(_PluginCopyMixin, _RulesFileRows, OverrideTestCase):
    HELPER = "stale"
    GUARD = READONLY_HOOK
    GUARD_NAME = "db-research-readonly-guard.py"
    STRICT_COMMAND = DISPOSABLE_WRITE
    LOADED_COMMAND = DISPOSABLE_WRITE


# =====================================================================================================
# I2 (t12 round-three review): the audit log of BOTH database guards is written without following a link.
#
# A link at the log (or at .claude/logs) to a pipe that never reads used to hang the guard on its block
# path. Every step is now checked with lstat, and the open is non-following and non-blocking. Each row
# runs the guard as a separate process under a short timeout and expects its normal decision (blocked),
# the record skipped (one line on standard error) and the link target untouched.
# =====================================================================================================
AUDIT_OVER_LIMIT = 10 * 1024 * 1024 + 1   # over both guards' rotation limits (10 MB and 5 MB)
AUDIT_SKIP_LINE = "audit record skipped"
SHARE_LOG_TARGET = "\\\\192.0.2.1\\share\\audit.log"   # TEST-NET-1: nothing answers
SHARE_DIR_TARGET = "\\\\192.0.2.1\\share\\logs"


def _symlink(case: unittest.TestCase, target: str | Path, link: Path, *, directory: bool = False) -> None:
    try:
        os.symlink(target, link, target_is_directory=directory)
    except NotImplementedError:
        case.skipTest(SKIP_NO_SYMLINK)
    except OSError as exc:
        if isinstance(exc, PermissionError) or getattr(exc, "winerror", 0) == 1314:
            case.skipTest(SKIP_NO_SYMLINK)
        raise


def _big_file(path: Path, size: int = AUDIT_OVER_LIMIT) -> None:
    with open(path, "wb") as handle:
        handle.truncate(size)   # sparse where the file system allows it


class _AuditLogRows:
    """Rows run once per guard. A subclass sets GUARD, LOG_NAME and a command its guard blocks with no arm."""

    LOG_NAME: str
    COMMAND = BLOCKED_COMMAND

    @property
    def logs(self) -> Path:
        return self.project / ".claude" / "logs"

    @property
    def log(self) -> Path:
        return self.logs / self.LOG_NAME

    @property
    def rotated(self) -> Path:
        return self.logs / (self.LOG_NAME + ".1")

    def blocked_run(self) -> Run:
        run = self.run_guard(self.shell(self.COMMAND, tool_use_id=self.next_id()), timeout=SHORT_TIMEOUT)
        self.assert_blocks(run, "the guard keeps its normal decision whatever stands at its audit log")
        return run

    def skipped_run(self) -> Run:
        run = self.blocked_run()
        self.assertIn(AUDIT_SKIP_LINE, run.err, "the skipped record is named on standard error: %s" % run)
        return run

    def _json_lines(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # ---------------------------------------------------------------- controls (pass before and after)
    def test_control_a_regular_log_is_appended_as_before(self):
        self.log.write_text('{"old": 1}\n', encoding="utf-8")
        self.blocked_run()
        lines = self._json_lines(self.log)
        self.assertEqual(lines[0], {"old": 1})
        self.assertGreaterEqual(len(lines), 2, "one record was appended")
        self.assertEqual(lines[-1].get("decision"), "BLOCK")

    def test_control_a_missing_log_is_created(self):
        self.assertFalse(os.path.lexists(self.log))
        self.blocked_run()
        self.assertEqual(self._json_lines(self.log)[-1].get("decision"), "BLOCK")

    def test_control_a_missing_logs_folder_is_created(self):
        os.rmdir(self.logs)
        self.blocked_run()
        self.assertTrue(self.logs.is_dir() and not self.logs.is_symlink())
        self.assertEqual(self._json_lines(self.log)[-1].get("decision"), "BLOCK")

    def test_control_a_regular_log_over_the_limit_rotates_as_before(self):
        _big_file(self.log)
        self.blocked_run()
        self.assertEqual(self.rotated.stat().st_size, AUDIT_OVER_LIMIT, "the old log became the .1 file")
        self.assertLess(self.log.stat().st_size, 1024 * 1024, "a new, small log was started")
        self.assertEqual(self._json_lines(self.log)[-1].get("decision"), "BLOCK")

    # ---------------------------------------------------------------- Windows: links to device and share paths
    @unittest.skipUnless(sys.platform == "win32", SKIP_POSIX_PIPES)
    def test_a_link_at_the_log_to_a_listening_pipe_in_the_dot_spelling_skips_the_record(self):
        make_pipe_link(self, self.log, "dot")
        self.skipped_run()

    @unittest.skipUnless(sys.platform == "win32", SKIP_POSIX_PIPES)
    def test_a_link_at_the_log_to_a_listening_pipe_in_the_question_mark_spelling_skips_the_record(self):
        make_pipe_link(self, self.log, "question-mark")
        self.skipped_run()

    @unittest.skipUnless(sys.platform == "win32", SKIP_POSIX_PIPES)
    def test_a_link_at_the_log_to_a_server_share_skips_the_record(self):
        _symlink(self, SHARE_LOG_TARGET, self.log)
        self.skipped_run()

    @unittest.skipUnless(sys.platform == "win32", SKIP_POSIX_PIPES)
    def test_a_directory_link_at_the_logs_folder_into_the_pipe_namespace_skips_the_record(self):
        server = PipeServer()
        self.addCleanup(server.close)
        os.rmdir(self.logs)
        _symlink(self, "\\\\.\\pipe\\" + server.leaf, self.logs, directory=True)
        self.skipped_run()

    @unittest.skipUnless(sys.platform == "win32", SKIP_POSIX_PIPES)
    def test_a_directory_link_at_the_logs_folder_to_a_server_share_skips_the_record(self):
        os.rmdir(self.logs)
        _symlink(self, SHARE_DIR_TARGET, self.logs, directory=True)
        self.skipped_run()

    @unittest.skipUnless(sys.platform == "win32", SKIP_POSIX_PIPES)
    def test_a_directory_link_at_the_logs_folder_to_another_local_folder_writes_nothing_there(self):
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        os.rmdir(self.logs)
        _symlink(self, elsewhere, self.logs, directory=True)
        self.skipped_run()
        self.assertEqual(os.listdir(elsewhere), [], "nothing was written through the directory link")

    @unittest.skipUnless(sys.platform == "win32", SKIP_POSIX_PIPES)
    def test_a_junction_at_the_logs_folder_writes_nothing_there(self):
        elsewhere = self.tmp / "elsewhere-junction"
        elsewhere.mkdir()
        os.rmdir(self.logs)
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.logs), str(elsewhere)],
                              capture_output=True, timeout=SHORT_TIMEOUT)
        if made.returncode != 0:
            self.skipTest("a junction could not be created on this host")
        self.skipped_run()
        self.assertEqual(os.listdir(elsewhere), [], "nothing was written through the junction")

    # ---------------------------------------------------------------- rotation never follows a link
    @unittest.skipUnless(sys.platform == "win32", SKIP_POSIX_PIPES)
    def test_rotation_on_a_linked_log_renames_and_removes_nothing(self):
        target = self.tmp / "big-target.log"
        _big_file(target)
        _symlink(self, target, self.log)
        self.skipped_run()
        self.assertTrue(self.log.is_symlink(), "the link is still the log")
        self.assertFalse(os.path.lexists(self.rotated), "nothing was renamed to the .1 name")
        self.assertEqual(target.stat().st_size, AUDIT_OVER_LIMIT, "the target is untouched")

    @unittest.skipUnless(sys.platform == "win32", SKIP_POSIX_PIPES)
    def test_rotation_with_a_link_at_the_dot_one_name_removes_and_renames_nothing(self):
        _big_file(self.log)
        keep = self.tmp / "keep-me.txt"
        keep.write_text("keep", encoding="utf-8")
        _symlink(self, keep, self.rotated)
        self.skipped_run()
        self.assertTrue(self.rotated.is_symlink(), "the link at the .1 name is still there")
        self.assertEqual(keep.read_text(encoding="utf-8"), "keep", "its target is not removed")
        self.assertEqual(self.log.stat().st_size, AUDIT_OVER_LIMIT, "the log was neither renamed nor appended to")

    # ---------------------------------------------------------------- POSIX: a named pipe at the log
    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"), "POSIX only: needs a named pipe")
    def test_a_named_pipe_at_the_log_skips_the_record(self):
        os.mkfifo(self.log)
        self.skipped_run()


class DestructiveGuardAuditLogTests(_AuditLogRows, OverrideTestCase):
    GUARD = DESTRUCTIVE_HOOK
    LOG_NAME = "db-guard.log"


class ReadonlyGuardAuditLogTests(_AuditLogRows, OverrideTestCase):
    GUARD = READONLY_HOOK
    LOG_NAME = "db-research.log"


if __name__ == "__main__":
    unittest.main(verbosity=2)
