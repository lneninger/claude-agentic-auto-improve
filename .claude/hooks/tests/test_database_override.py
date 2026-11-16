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

HOOK_TIMEOUT = 60

DESTRUCTIVE_HOOK = HOOKS_SRC / "db-destructive-guard.py"
READONLY_HOOK = HOOKS_SRC / "db-research-readonly-guard.py"

# Built from parts: no literal destructive phrase in this file.
_V = "DR" + "OP DATA" + "BASE"
PROTECTED = "ScalpingMachine"
#: Blocked by BOTH guards: a protected database named as the target of a database-level statement.
BLOCKED_COMMAND = 'sqlcmd -S "(localdb)\\m" -E -Q "' + _V + " " + PROTECTED + '"'
HUMAN_ONLY_SCRIPT = "tools/db-protection/update-dev-database.cmd"

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

    def run_guard(self, payload: dict, *, guard: Path | None = None, env: dict | None = None) -> Run:
        proc = subprocess.run([sys.executable, "-B", str(guard or self.GUARD)],
                              input=json.dumps(payload).encode("utf-8"), capture_output=True,
                              env=self.env(env), cwd=str(self.tmp), timeout=HOOK_TIMEOUT)
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

    def test_with_the_helper_removed_an_armed_command_gets_no_override_and_an_arm_write_is_still_refused(self):
        self.arm()
        run = self.run_guard(self.shell(BLOCKED_COMMAND, tool_use_id=self.next_id()),
                             guard=self.hooks / "db-destructive-guard.py")
        self.assert_blocks(run, "Guard fallback mode: a missing claim binding means no override")
        refused = self.run_guard(self.shell("touch .claude/database-override.once"),
                                 guard=self.hooks / "db-destructive-guard.py")
        self.assert_blocks(refused, "and the inline name test still refuses the write")


if __name__ == "__main__":
    unittest.main(verbosity=2)
