#!/usr/bin/env python3
"""
test_hook_registration_check.py -- RED suite for hook-registration-check.py (INV-P2, INV-P3).

Contract: .claude/concepts/2026-09-28-hook-server-modes.md (ScalpingMachine repository),
INV-P2, INV-P3, sub-task 1 and critique round five WARN 4 and WARN 5.

hook-registration-check.py is the plugin's one SessionStart hook. At every session start it
makes sure a project that installed the plugin has the plugin's 17 hook entries registered,
by writing the missing ones into the project's .claude/settings.local.json. This suite runs
the script as a subprocess, the way Claude Code starts it, against fixtures that live only in
temporary folders. It never reads or writes this machine's ~/.claude, a real settings file,
or a real plugin cache: HOME, USERPROFILE and CLAUDE_CONFIG_DIR point at temporary folders.

Run:
    py -3 .claude/hooks/tests/test_hook_registration_check.py

Exit code: 0 when every test passed, non-zero otherwise.

----------------------------------------------------------------------------------------
SHAPE ASSUMPTIONS (the contract names behaviour, not byte shapes; sub-task 2 satisfies these)
----------------------------------------------------------------------------------------
* The check lives at <plugin root>/.claude/hooks/hook-registration-check.py and the closed
  list in <plugin root>/.claude/hooks/hook-registration-entries.json.
* It learns the project from CLAUDE_PROJECT_DIR (the tests also set cwd and the stdin
  payload's "cwd" to the same folder) and the running plugin root from CLAUDE_PLUGIN_ROOT
  (the tests run the script from inside that same root, so either source gives one answer).
* An entry it writes is in exec form (INV-R1): "command" "py" (or "python3" off Windows),
  "args" starting with "-3" on Windows, then the absolute path
  <running root>/.claude/hooks/<script> and any extra argument; "async": true for the
  entries the contract names. The matcher is the one the plugin's hooks.json carries today.
* A script counts as registered by the project when settings.json holds that script
  basename under the same event, whatever its form.
* Its output on a change is ONE JSON object on stdout:
  {"systemMessage": <str>, "hookSpecificOutput": {"hookEventName": "SessionStart",
   "additionalContext": <str>}}. On no change it prints nothing at all. It writes nothing to
  stderr and always exits 0.
* One log line per change in <project>/.claude/logs/hook-registration.log; each line names
  the event and the script it changed.
* THE LOCK PROTOCOL (pinned here because the contract names only the file): the lock is the
  existence of <project>/.claude/.settings-local.lock, taken by creating it exclusively
  (O_CREAT|O_EXCL, the repository's .regen-lock convention) and released by deleting it. A
  writer that finds it held WAITS (the tests hold it for about a second) and then does its
  read-modify-write; the final write is an atomic os.replace of a temporary sibling.

----------------------------------------------------------------------------------------
POSITIVE CONTROLS
----------------------------------------------------------------------------------------
* "Each test fails against a check that only reports and never writes": the writing tests are
  scenario methods (scn_*). TestCheck runs each against the real check. TestReportOnlyControl
  runs the SAME scenario against a stand-in check that prints a plausible report and writes
  nothing, and asserts the scenario fails. A scenario that cannot tell a writer from a
  reporter would pass there and be reported.
* "A writer without the lock loses entries in the same harness": TestLockHarness proves, with
  test-supplied writers only, that the harness loses an entry for a lockless writer and keeps
  both for a locking one. It passes today.
* The tests that pass today are the harness controls above and the data-file-free helper
  checks in TestHarnessSanity. Every test that needs the check or its data file fails today
  because those files do not exist yet (the failure names the missing file).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REAL_HOOKS = HERE.parent
REAL_ROOT = REAL_HOOKS.parent.parent
CHECK_NAME = "hook-registration-check.py"
DATA_NAME = "hook-registration-entries.json"
PLUGIN_NAME = "agentic-auto-improve"
RUN_TIMEOUT = 60

# (event, matcher, script, extra args, async) -- the 17 entries of the 0.3.1 cache's hooks.json.
# Matchers and extra arguments are the ones the plugin's hooks.json carries today.
CONTRACT_ENTRIES = [
    ("PreToolUse", "Edit|Write|MultiEdit", "concept-gate.py", (), False),
    ("PreToolUse", "Edit|Write|MultiEdit", "architecture-guard.py", (), False),
    ("PreToolUse", "Bash", "bash-gate.py", (), False),
    ("PreToolUse", "Bash|Edit|Write|MultiEdit", "db-destructive-guard.py", (), False),
    ("PreToolUse", "Bash|Edit|Write|MultiEdit", "db-research-readonly-guard.py", (), False),
    ("PreToolUse", "Read|Grep|Glob", "codegraph-first-guard.py", (), False),
    ("PostToolUse", "Edit|Write|MultiEdit", "contract-status-watcher.py", (), True),
    ("PostToolUse", "Edit|Write|MultiEdit", "critic-verdict-tracker.py", (), True),
    ("PostToolUse", "Edit|Write|MultiEdit", "journal-post-approval-tracker.py", (), True),
    ("PostToolUse", "Edit|Write|MultiEdit", "integration-check.py", (), True),
    ("PostToolUse", "mcp__codegraph__.*", "codegraph-turn-tracker.py", (), False),
    ("UserPromptSubmit", None, "codegraph-turn-reset.py", (), False),
    ("UserPromptSubmit", None, "architecture-advisor.py", (), False),
    ("UserPromptSubmit", None, "plan-question-advisor.py", (), False),
    ("UserPromptSubmit", None, "plain-language-guard.py", ("--carry-forward",), False),
    ("Stop", None, "plain-language-guard.py", (), False),
    ("Stop", None, "memory-pager.py", (), True),
]
assert len(CONTRACT_ENTRIES) == 17

# ASSUMPTION pending t3 review (recorded by the main session, fact 3): plugin master's
# hooks.json gained an 18th entry after the contract was written, and the closed list is
# assumed to carry it too, because INV-P1 leaves hooks.json with one hook.
WORKING_AGREEMENTS = ("SessionStart", None, "working-agreements.py", (), False)

ASYNC_SCRIPTS = {"contract-status-watcher.py", "critic-verdict-tracker.py",
                 "journal-post-approval-tracker.py", "integration-check.py", "memory-pager.py"}

# A stand-in for "a check that only reports and never writes".
REPORT_ONLY_CHECK = textwrap.dedent('''\
    import json, sys
    names = "concept-gate.py, bash-gate.py, memory-pager.py"
    print(json.dumps({
        "systemMessage": "hook registration: would add " + names + " (report only). "
                         "A call refused with can't open file means restart the session.",
        "hookSpecificOutput": {"hookEventName": "SessionStart",
            "additionalContext": "Missing hook entries: " + names + ". "
                         "A refusal saying can't open file means restart the session."}}))
    sys.exit(0)
''')


# ------------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------------

def norm_path(text: str) -> str:
    return os.path.normcase(os.path.normpath(str(text).strip('"'))).replace("\\", "/")


def write_json(path: Path, obj) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(obj, indent=2) + "\n").encode("utf-8")
    path.write_bytes(data)
    return data


def read_json(path: Path):
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def drain(proc: subprocess.Popen) -> str:
    """Read what is left of a finished process's pipes, close them, return its stderr text."""
    err = ""
    for name in ("stdout", "stderr"):
        stream = getattr(proc, name, None)
        if stream is not None:
            data = stream.read()
            stream.close()
            if name == "stderr":
                err = data.decode("utf-8", "replace")
    return err


def snapshot(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None)
            for p in sorted(Path(root).rglob("*"))}


def hook_key(hook: dict):
    """(script basename, extra args, script path) of one registered hook, in exec or string form."""
    if hook.get("args") is not None:
        tokens = [str(hook.get("command", ""))] + [str(a) for a in hook["args"]]
    else:
        tokens = re.findall(r'"([^"]*)"|(\S+)', str(hook.get("command", "")))
        tokens = [a or b for a, b in tokens]
    for i, tok in enumerate(tokens):
        if tok.lower().endswith(".py"):
            path = tok.replace("\\", "/")
            return path.rsplit("/", 1)[-1], tuple(tokens[i + 1:]), path
    return None


def registrations(settings: dict):
    """[(event, matcher, script, extras, path, hook dict)] for every script hook in a settings dict."""
    out = []
    for event, groups in ((settings or {}).get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                key = hook_key(hook)
                if key:
                    out.append((event, group.get("matcher") or None, key[0], key[1], key[2], hook))
    return out


def settings_hook(script: str, args=()):
    return {"type": "command", "command": "py",
            "args": ["-3", "${CLAUDE_PROJECT_DIR}/.claude/hooks/" + script, *args]}


def settings_with(entries) -> dict:
    """A project settings.json registering the given (event, matcher, script, extras, async) entries."""
    hooks: dict = {}
    for event, matcher, script, extras, _async in entries:
        groups = hooks.setdefault(event, [])
        group = next((g for g in groups if g.get("matcher") == matcher), None)
        if group is None:
            group = {"hooks": []}
            if matcher is not None:
                group["matcher"] = matcher
            groups.append(group)
        group["hooks"].append(settings_hook(script, extras))
    return {"hooks": hooks}


class World:
    """One temporary home, project and plugin root (laid out like a plugin cache version folder)."""

    def __init__(self, base: Path, stub: bool):
        self.base = base
        self.home = base / "claudehome"
        self.fake_user = base / "fakeuser"
        self.project = base / "proj"
        self.root = (self.home / "plugins" / "cache" / "auto-improve" / PLUGIN_NAME / "0.9.9")
        for folder in (self.home, self.fake_user, self.project):
            folder.mkdir(parents=True, exist_ok=True)
        ignore = shutil.ignore_patterns("tests", "__pycache__", "*.pyc")
        shutil.copytree(REAL_ROOT / ".claude", self.root / ".claude", ignore=ignore)
        if (REAL_ROOT / ".claude-plugin").is_dir():
            shutil.copytree(REAL_ROOT / ".claude-plugin", self.root / ".claude-plugin")
        if stub:
            (self.root / ".claude" / "hooks" / CHECK_NAME).write_text(REPORT_ONLY_CHECK, encoding="utf-8")
            # The control must fail on the check's behaviour, not on a missing data file.
            if not (self.root / ".claude" / "hooks" / DATA_NAME).is_file():
                (self.root / ".claude" / "hooks" / DATA_NAME).write_text(
                    json.dumps({"stand-in": "concept-gate.py"}), encoding="utf-8")
        self.stale_root = self.home / "plugins" / "cache" / "auto-improve" / PLUGIN_NAME / "0.1.0"

    @property
    def check(self) -> Path:
        return self.root / ".claude" / "hooks" / CHECK_NAME

    @property
    def data_file(self) -> Path:
        return self.root / ".claude" / "hooks" / DATA_NAME

    @property
    def settings(self) -> Path:
        return self.project / ".claude" / "settings.json"

    @property
    def local(self) -> Path:
        return self.project / ".claude" / "settings.local.json"

    @property
    def log(self) -> Path:
        return self.project / ".claude" / "logs" / "hook-registration.log"

    @property
    def lock(self) -> Path:
        return self.project / ".claude" / ".settings-local.lock"

    def env(self) -> dict:
        env = dict(os.environ)
        for name in [n for n in env if n.startswith("CLAUDE_")]:
            del env[name]
        env.update({"HOME": str(self.fake_user), "USERPROFILE": str(self.fake_user),
                    "CLAUDE_CONFIG_DIR": str(self.home), "CLAUDE_PROJECT_DIR": str(self.project),
                    "CLAUDE_PLUGIN_ROOT": str(self.root), "PYTHONDONTWRITEBYTECODE": "1"})
        return env

    def payload(self) -> bytes:
        return json.dumps({"hook_event_name": "SessionStart", "source": "startup",
                           "session_id": "t", "cwd": str(self.project)}).encode("utf-8")

    def command(self):
        return ["py", "-3", str(self.check)] if sys.platform == "win32" else ["python3", str(self.check)]

    def popen(self) -> subprocess.Popen:
        return subprocess.Popen(self.command(), cwd=str(self.project), env=self.env(),
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def run(self):
        proc = self.popen()
        out, err = proc.communicate(self.payload(), timeout=RUN_TIMEOUT)
        return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")

    def local_regs(self):
        return registrations(read_json(self.local)) if self.local.is_file() else []

    def log_lines(self):
        if not self.log.is_file():
            return []
        return [l for l in self.log.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]


class Scenarios(unittest.TestCase):
    """The scenarios. No test_ methods here: TestCheck and TestReportOnlyControl call them."""

    stub = False

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hrc-")).resolve()
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.w = World(self.tmp, self.stub)

    # --- assertions -------------------------------------------------------------------
    def need_check(self):
        self.assertTrue(self.w.check.is_file(),
                        msg="%s does not exist yet (sub-task 2 creates it); nothing to run" % CHECK_NAME)

    def need_data_file(self):
        self.assertTrue(self.w.data_file.is_file(),
                        msg="%s does not exist yet (sub-task 2 creates the closed list there)" % DATA_NAME)

    def run_check(self):
        self.need_check()
        rc, out, err = self.w.run()
        self.assertEqual(rc, 0, msg="the check must exit 0 whatever it did; stderr=%r" % err)
        self.assertEqual(err.strip(), "", msg="the check writes nothing to stderr (fail open)")
        return out

    def closed_regs(self):
        """Closed-list registrations in settings.local.json, with the one allowed extra split off."""
        regs = self.w.local_regs()
        contract = {(e, s, x) for e, _m, s, x, _a in CONTRACT_ENTRIES}
        wa = (WORKING_AGREEMENTS[0], WORKING_AGREEMENTS[2], WORKING_AGREEMENTS[3])
        known = contract | {wa}
        return [r for r in regs if (r[0], r[2], r[3]) in known]

    def assert_entry_shape(self, reg, matcher, is_async, script):
        event, got_matcher, _script, extras, path, hook = reg
        self.assertEqual(got_matcher, matcher,
                         msg="%s on %s keeps the matcher the plugin's hooks.json carries" % (script, event))
        self.assertEqual(bool(hook.get("async")), is_async,
                         msg="%s async flag must be %s (INV-P2 names the after-edit trackers and memory-pager)"
                             % (script, is_async))
        self.assertIn(hook.get("command"), ("py", "python3"),
                      msg="%s is written in exec form: command is the launcher, not a command line" % script)
        self.assertIsInstance(hook.get("args"), list, msg="%s is written with an args list (INV-R1)" % script)
        if hook.get("command") == "py":
            self.assertEqual(hook["args"][0], "-3", msg="py entries start their args with -3 (INV-R1)")
        self.assertEqual(norm_path(path), norm_path(self.w.root / ".claude" / "hooks" / script),
                         msg="%s points at the RUNNING plugin root, not another version's folder" % script)

    # --- scenarios -------------------------------------------------------------------
    def scn_silent_when_everything_is_registered(self):
        entries = CONTRACT_ENTRIES + [WORKING_AGREEMENTS]
        self.w.settings.parent.mkdir(parents=True, exist_ok=True)
        write_json(self.w.settings, settings_with(entries))
        other_local = {"permissions": {"allow": ["Bash(ls:*)"]}}
        write_json(self.w.local, other_local)
        before = snapshot(self.w.project)
        out = self.run_check()
        self.assertEqual(out.strip(), "", msg="nothing changed, so nothing is said (no banner, no context)")
        self.assertEqual(snapshot(self.w.project), before,
                         msg="a project whose settings.json registers every script gets no file written, "
                             "no log line and no new file")

    def scn_writes_the_whole_list_when_no_local_entries(self):
        self.need_data_file()
        custom = {"type": "command", "command": "py",
                  "args": ["-3", "${CLAUDE_PROJECT_DIR}/.claude/hooks/custom-user-hook.py"]}
        other = {"permissions": {"allow": ["Bash(ls:*)"]}, "env": {"MY_FLAG": "1"},
                 "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [custom]}]}}
        write_json(self.w.local, other)
        self.assertFalse(self.w.settings.exists(), msg="fixture: this project has no settings.json at all")
        self.run_check()
        self.assertFalse(self.w.settings.exists(), msg="the check never creates or touches settings.json")
        local = read_json(self.w.local)
        for key in ("permissions", "env"):
            self.assertEqual(local.get(key), other[key], msg="the check keeps every other key (%s)" % key)
        regs = self.w.local_regs()
        self.assertTrue([r for r in regs if r[2] == "custom-user-hook.py" and r[5] == custom],
                        msg="the user's own hook entry survives unchanged")
        closed = self.closed_regs()
        for event, matcher, script, extras, is_async in CONTRACT_ENTRIES:
            found = [r for r in closed if (r[0], r[2], r[3]) == (event, script, extras)]
            self.assertEqual(len(found), 1,
                             msg="exactly one local entry for %s on %s; got %d" % (script, event, len(found)))
            self.assert_entry_shape(found[0], matcher, is_async, script)
        extra = [r for r in closed if (r[0], r[2], r[3]) not in {(e, s, x) for e, _m, s, x, _a in CONTRACT_ENTRIES}]
        for reg in extra:
            self.assertEqual((reg[0], reg[2]), (WORKING_AGREEMENTS[0], WORKING_AGREEMENTS[2]),
                             msg="the only entry allowed beyond the contract's 17 is working-agreements.py")
        lines = self.w.log_lines()
        self.assertEqual(len(lines), len(closed),
                         msg="one log line per change (%d entries written); got %d lines" % (len(closed), len(lines)))
        for reg in closed:
            self.assertTrue([l for l in lines if reg[2] in l and reg[0] in l],
                            msg="a log line names the event %s and the script %s" % (reg[0], reg[2]))

    def scn_writes_only_the_missing_entries(self):
        self.need_data_file()
        registered = [e for e in CONTRACT_ENTRIES if e[2] in (
            "concept-gate.py", "architecture-guard.py", "db-destructive-guard.py",
            "critic-verdict-tracker.py", "codegraph-turn-reset.py")]
        registered.append(("Stop", None, "plain-language-guard.py", (), False))  # Stop only
        registered.append(WORKING_AGREEMENTS)
        wrong_event = ("UserPromptSubmit", None, "memory-pager.py", (), True)  # memory-pager belongs on Stop
        write_json(self.w.settings, settings_with(registered + [wrong_event]))
        before_settings = self.w.settings.read_bytes()
        self.run_check()
        self.assertEqual(self.w.settings.read_bytes(), before_settings, msg="settings.json is never touched")
        have = {(e, s, x) for e, _m, s, x, _a, _as in self.closed_regs()}
        reg_keys = {(e, s, x) for e, _m, s, x, _a in registered}
        expected = {(e, s, x) for e, _m, s, x, _a in CONTRACT_ENTRIES} - reg_keys
        self.assertEqual(have, expected,
                         msg="local entries are exactly the closed-list entries the project does not register "
                             "on their event (memory-pager on the wrong event does not count, plain-language-guard "
                             "on Stop does not cover UserPromptSubmit)")
        self.assertEqual(len(self.closed_regs()), len(expected), msg="each missing entry is written once")
        self.assertEqual(len(self.w.log_lines()), len(expected), msg="one log line per entry written")

    def scn_rewrites_entries_of_another_version_and_is_idempotent(self):
        self.need_data_file()
        stale = [("PreToolUse", "Edit|Write|MultiEdit", "concept-gate.py", (), False),
                 ("PreToolUse", "Bash", "bash-gate.py", (), False),
                 ("UserPromptSubmit", None, "plain-language-guard.py", ("--carry-forward",), False),
                 ("Stop", None, "memory-pager.py", (), True)]
        groups: dict = {}
        for event, matcher, script, extras, is_async in stale:
            hook = {"type": "command", "command": "py",
                    "args": ["-3", str(self.w.stale_root / ".claude" / "hooks" / script), *extras]}
            if is_async:
                hook["async"] = True
            group = {"hooks": [hook]}
            if matcher is not None:
                group["matcher"] = matcher
            groups.setdefault(event, []).append(group)
        custom = {"type": "command", "command": "py",
                  "args": ["-3", "${CLAUDE_PROJECT_DIR}/.claude/hooks/custom-user-hook.py"]}
        groups.setdefault("Stop", []).append({"hooks": [custom]})
        self.assertFalse(self.w.stale_root.exists(), msg="fixture: the 0.1.0 folder was deleted")
        write_json(self.w.local, {"env": {"A": "1"}, "hooks": groups})
        write_json(self.w.settings, settings_with([WORKING_AGREEMENTS]))
        self.run_check()
        text = self.w.local.read_text(encoding="utf-8")
        self.assertNotIn("0.1.0", text, msg="no entry still points at the deleted 0.1.0 folder")
        self.assertEqual(read_json(self.w.local).get("env"), {"A": "1"}, msg="other keys are kept")
        closed = self.closed_regs()
        for event, matcher, script, extras, is_async in CONTRACT_ENTRIES:
            found = [r for r in closed if (r[0], r[2], r[3]) == (event, script, extras)]
            self.assertEqual(len(found), 1, msg="%s on %s appears exactly once (a rewrite is not an add)"
                                                % (script, event))
            self.assert_entry_shape(found[0], matcher, is_async, script)
        self.assertTrue([r for r in self.w.local_regs() if r[2] == "custom-user-hook.py" and r[5] == custom],
                        msg="a hook that is not on the closed list is left alone")
        # second run: nothing changes
        before = snapshot(self.w.project)
        out = self.run_check()
        self.assertEqual(out.strip(), "", msg="a second run says nothing")
        self.assertEqual(snapshot(self.w.project), before,
                         msg="a second run leaves settings.local.json byte-identical and logs nothing")

    def scn_messages_name_what_changed_and_never_ask_for_a_command(self):
        self.need_data_file()
        unchanged = ["architecture-guard.py", "journal-post-approval-tracker.py", "integration-check.py"]
        registered = [e for e in CONTRACT_ENTRIES if e[2] in unchanged] + [WORKING_AGREEMENTS]
        write_json(self.w.settings, settings_with(registered))
        stale = self.w.stale_root / ".claude" / "hooks" / "concept-gate.py"
        write_json(self.w.local, {"hooks": {"PreToolUse": [{"matcher": "Edit|Write|MultiEdit", "hooks": [
            {"type": "command", "command": "py", "args": ["-3", str(stale)]}]}]}})
        out = self.run_check()
        self.assertTrue(out.strip(), msg="a change was made, so the check says so on stdout")
        payload = json.loads(out)
        system_message = payload.get("systemMessage")
        context = (payload.get("hookSpecificOutput") or {}).get("additionalContext")
        self.assertTrue(isinstance(system_message, str) and system_message.strip(),
                        msg="INV-P3: a systemMessage banner for the operator")
        self.assertTrue(isinstance(context, str) and context.strip(),
                        msg="INV-P3: additionalContext for Claude under hookSpecificOutput")
        written = {reg[2] for reg in self.closed_regs()}
        changed = [s for s in written if s not in unchanged and s != "working-agreements.py"]
        expected_changed = {e[2] for e in CONTRACT_ENTRIES} - set(unchanged)
        self.assertEqual(set(changed), expected_changed,
                         msg="the changes the messages must name really happened: the stale entry was rewritten "
                             "and every unregistered entry was added")
        self.assertNotIn("0.1.0", self.w.local.read_text(encoding="utf-8"),
                         msg="the stale entry no longer points at the deleted folder")
        for label, text in (("systemMessage", system_message), ("additionalContext", context)):
            for script in changed:
                self.assertIn(script[:-3], text, msg="%s names the changed entry %s" % (label, script))
            for script in unchanged:
                self.assertNotIn(script[:-3], text,
                                 msg="%s does not name %s, which the project already registers" % (label, script))
            self.assertRegex(text, r"can[’']t open file",
                             msg="%s explains the \"can't open file\" refusal" % label)
            self.assertRegex(text, r"(?i)restart",
                             msg="%s says that refusal means restarting the session" % label)
            self.assertNotRegex(text, r"(?:^|[\s\"'(`])/[a-z][a-z-]+\b(?![/.\w])",
                                msg="%s never names a slash command or skill to run" % label)
            self.assertNotRegex(text, r"(?i)\b(run|execute|invoke)\b",
                                msg="%s never asks anyone to run or execute anything" % label)
            self.assertNotIn("finish-install", text, msg="%s never points at the finish-install skill" % label)

    def scn_closed_list_is_read_from_the_data_file(self):
        self.need_data_file()
        self.need_check()
        source = self.w.check.read_text(encoding="utf-8", errors="replace")
        quoted = [name for _e, _m, name, _x, _a in CONTRACT_ENTRIES + [WORKING_AGREEMENTS]
                  if re.search(r"""["']%s["']""" % re.escape(name), source)]
        self.assertEqual(quoted, [], msg="the check's own code holds no list of the plugin's scripts "
                                         "(round five WARN 5); it quotes: %s" % quoted)
        text = self.w.data_file.read_text(encoding="utf-8")
        self.assertIn("concept-gate.py", text, msg="fixture sanity: the data file names concept-gate.py")
        self.w.data_file.write_text(text.replace("concept-gate.py", "zz-sentinel-gate.py"), encoding="utf-8")
        self.run_check()
        scripts = {reg[2] for reg in self.w.local_regs()}
        self.assertIn("zz-sentinel-gate.py", scripts,
                      msg="an entry changed only in the data file is the entry the check writes")
        self.assertNotIn("concept-gate.py", scripts,
                         msg="an entry removed from the data file is not written (the list is not in the code)")

    def scn_two_checks_started_together_agree(self):
        self.need_data_file()
        self.need_check()
        procs = [self.w.popen(), self.w.popen()]
        for proc in procs:
            proc.stdin.write(self.w.payload())
            proc.stdin.close()
        codes = [proc.wait(timeout=RUN_TIMEOUT) for proc in procs]
        for proc in procs:
            drain(proc)
        self.assertEqual(codes, [0, 0], msg="both sessions' checks exit 0")
        closed = self.closed_regs()
        keys = [(r[0], r[2], r[3]) for r in closed]
        self.assertEqual(len(keys), len(set(keys)), msg="no entry is written twice by two sessions")
        for event, _m, script, extras, _a in CONTRACT_ENTRIES:
            self.assertIn((event, script, extras), keys, msg="%s on %s is present" % (script, event))
        self.assertEqual(len(self.w.log_lines()), len(closed),
                         msg="the second writer found the first one's entries (read-modify-write under the "
                             "lock), so each change is logged once")
        names = sorted(p.name for p in (self.w.project / ".claude").iterdir())
        self.assertEqual([n for n in names if n not in ("settings.local.json", "logs")], [],
                         msg="the lock is released and no temporary file is left behind; saw %s" % names)

    def scn_waits_for_the_lock_and_keeps_the_other_writers_entries(self):
        self.need_data_file()
        self.need_check()
        peer = self.tmp / "peer.py"
        peer.write_text(PEER_WRITER, encoding="utf-8")
        ready = self.tmp / "peer.ready"
        proc_peer = subprocess.Popen([sys.executable, str(peer), str(self.w.project), "lock", "1.5", str(ready)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.time() + 20
        while not ready.exists() and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(ready.exists(), msg="harness: the peer writer took the lock")
        proc_check = self.w.popen()
        proc_check.stdin.write(self.w.payload())
        proc_check.stdin.close()
        self.assertEqual(proc_check.wait(timeout=RUN_TIMEOUT), 0, msg="the check exits 0")
        drain(proc_check)
        peer_code = proc_peer.wait(timeout=RUN_TIMEOUT)
        peer_err = drain(proc_peer)
        self.assertEqual(peer_code, 0, msg="harness: the peer exits 0; stderr=%r" % peer_err)
        local = read_json(self.w.local)
        self.assertIn("peerMarker", local, msg="the other writer's key survived the check's write")
        self.assertTrue([r for r in registrations(local) if r[2] == "peer-entry.py"],
                        msg="the other writer's hook entry survived the check's write")
        have = {(r[0], r[2], r[3]) for r in self.closed_regs()}
        for event, _m, script, extras, _a in CONTRACT_ENTRIES:
            self.assertIn((event, script, extras), have,
                          msg="the check's entry %s on %s survived the peer's later write "
                              "(it took the shared lock before reading)" % (script, event))
        self.assertFalse(self.w.lock.exists(), msg="the lock is released when everyone is done")


PEER_WRITER = textwrap.dedent('''\
    import json, os, sys, time
    project, mode, hold, ready = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
    claude = os.path.join(project, ".claude")
    local = os.path.join(claude, "settings.local.json")
    lock = os.path.join(claude, ".settings-local.lock")
    os.makedirs(claude, exist_ok=True)
    if mode == "lock":
        deadline = time.time() + 30
        while True:
            try:
                os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                break
            except FileExistsError:
                if time.time() > deadline:
                    sys.exit(3)
                time.sleep(0.05)
    open(ready, "w").close()
    try:
        current = json.load(open(local, encoding="utf-8")) if os.path.exists(local) else {}
        time.sleep(hold)
        current["peerMarker"] = {"by": "peer"}
        current.setdefault("hooks", {}).setdefault("PostToolUse", []).append(
            {"matcher": "Write", "hooks": [{"type": "command", "command": "py",
                                            "args": ["-3", "C:/peer/peer-entry.py"]}]})
        tmp = local + ".peer-tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(current, handle)
        os.replace(tmp, local)
    finally:
        if mode == "lock":
            try:
                os.unlink(lock)
            except OSError:
                pass
''')

NAIVE_WRITER = textwrap.dedent('''\
    import json, os, sys, time
    project, mode, delay = sys.argv[1], sys.argv[2], float(sys.argv[3])
    claude = os.path.join(project, ".claude")
    local = os.path.join(claude, "settings.local.json")
    lock = os.path.join(claude, ".settings-local.lock")
    time.sleep(delay)
    if mode == "lock":
        deadline = time.time() + 30
        while True:
            try:
                os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                break
            except FileExistsError:
                if time.time() > deadline:
                    sys.exit(3)
                time.sleep(0.05)
    try:
        current = json.load(open(local, encoding="utf-8")) if os.path.exists(local) else {}
        current["naiveMarker"] = {"by": "naive"}
        tmp = local + ".naive-tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(current, handle)
        os.replace(tmp, local)
    finally:
        if mode == "lock":
            try:
                os.unlink(lock)
            except OSError:
                pass
''')


# ------------------------------------------------------------------------------------
# The tests
# ------------------------------------------------------------------------------------

class TestCheck(Scenarios):
    """INV-P2, INV-P3 and rounds five WARN 4 and WARN 5, against the real check."""

    def test_silent_and_writes_nothing_when_settings_json_registers_every_script(self):
        self.scn_silent_when_everything_is_registered()

    def test_with_no_local_entries_the_check_writes_the_whole_list_and_keeps_everything_else(self):
        self.scn_writes_the_whole_list_when_no_local_entries()

    def test_with_some_entries_registered_by_the_project_it_writes_only_the_missing_ones(self):
        self.scn_writes_only_the_missing_entries()

    def test_entries_pointing_at_another_version_are_rewritten_and_a_second_run_changes_nothing(self):
        self.scn_rewrites_entries_of_another_version_and_is_idempotent()

    def test_system_message_and_additional_context_name_what_changed_and_ask_for_no_command(self):
        self.scn_messages_name_what_changed_and_never_ask_for_a_command()

    def test_round_five_warn_5_the_closed_list_is_read_from_the_data_file_not_the_code(self):
        self.scn_closed_list_is_read_from_the_data_file()

    def test_round_five_warn_4_the_check_waits_for_the_shared_lock_and_loses_no_entries(self):
        self.scn_waits_for_the_lock_and_keeps_the_other_writers_entries()

    def test_round_five_warn_4_two_checks_started_together_write_each_entry_once(self):
        self.scn_two_checks_started_together_agree()

    def test_the_data_file_names_every_one_of_the_17_contract_scripts(self):
        self.need_data_file()
        data = json.loads(self.w.data_file.read_text(encoding="utf-8"))
        self.assertIsInstance(data, (dict, list), msg="the data file is valid JSON")
        text = self.w.data_file.read_text(encoding="utf-8")
        for event, _matcher, script, _extras, _async in CONTRACT_ENTRIES:
            expected = sum(1 for e in CONTRACT_ENTRIES if e[2] == script)
            self.assertEqual(len(re.findall(re.escape(script), text)), expected,
                             msg="%s is named once per event it is registered on (%d)" % (script, expected))

    def test_the_check_writes_the_four_after_edit_trackers_and_memory_pager_async(self):
        self.need_data_file()
        self.run_check()
        by_script = {}
        for reg in self.closed_regs():
            by_script.setdefault(reg[2], []).append(reg)
        for script in ASYNC_SCRIPTS:
            self.assertTrue(by_script.get(script), msg="%s is written" % script)
            for reg in by_script[script]:
                self.assertIs(reg[5].get("async"), True, msg="%s carries async true" % script)
        for script, regs in by_script.items():
            if script not in ASYNC_SCRIPTS:
                for reg in regs:
                    self.assertFalse(reg[5].get("async"), msg="%s is synchronous" % script)

    def test_assumption_pending_t3_review_working_agreements_is_in_the_closed_list(self):
        """ASSUMPTION pending t3 review.

        Plugin master's hooks.json registers working-agreements.py on SessionStart, an 18th entry
        added after the contract was written. INV-P1 leaves hooks.json with one hook, so dropping
        it from both places would silently stop a shipped hook. This test assumes the closed list
        therefore carries it (SessionStart, no matcher, synchronous). If the t3 review rules
        otherwise, delete this test; the 17 contract entries are asserted by name elsewhere.
        """
        self.need_data_file()
        self.run_check()
        found = [r for r in self.w.local_regs() if (r[0], r[2]) == ("SessionStart", "working-agreements.py")]
        self.assertEqual(len(found), 1, msg="working-agreements.py is written once, on SessionStart")
        self.assert_entry_shape(found[0], None, False, "working-agreements.py")


class TestReportOnlyControl(Scenarios):
    """Positive control: each writing scenario FAILS against a check that only reports."""

    stub = True

    def assert_scenario_fails(self, scenario):
        with self.assertRaises(AssertionError, msg="a report-only check must fail this scenario"):
            scenario()

    def test_control_whole_list(self):
        self.assert_scenario_fails(self.scn_writes_the_whole_list_when_no_local_entries)

    def test_control_only_missing(self):
        self.assert_scenario_fails(self.scn_writes_only_the_missing_entries)

    def test_control_rewrite_and_idempotence(self):
        self.assert_scenario_fails(self.scn_rewrites_entries_of_another_version_and_is_idempotent)

    def test_control_messages(self):
        self.assert_scenario_fails(self.scn_messages_name_what_changed_and_never_ask_for_a_command)

    def test_control_data_file_drives_the_list(self):
        self.assert_scenario_fails(self.scn_closed_list_is_read_from_the_data_file)

    def test_control_two_checks_together(self):
        self.assert_scenario_fails(self.scn_two_checks_started_together_agree)

    def test_control_lock_scenario(self):
        self.assert_scenario_fails(self.scn_waits_for_the_lock_and_keeps_the_other_writers_entries)


class TestLockHarness(unittest.TestCase):
    """Control for round five WARN 4: the harness itself, with test-supplied writers only."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hrc-lock-")).resolve()
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.project = self.tmp / "proj"
        (self.project / ".claude").mkdir(parents=True)
        (self.tmp / "peer.py").write_text(PEER_WRITER, encoding="utf-8")
        (self.tmp / "naive.py").write_text(NAIVE_WRITER, encoding="utf-8")

    def race(self, naive_mode):
        ready = self.tmp / "ready"
        peer = subprocess.Popen([sys.executable, str(self.tmp / "peer.py"), str(self.project), "lock", "1.2",
                                 str(ready)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.time() + 20
        while not ready.exists() and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(ready.exists(), msg="the peer took the lock")
        naive = subprocess.Popen([sys.executable, str(self.tmp / "naive.py"), str(self.project), naive_mode, "0.2"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        naive_code = naive.wait(timeout=60)
        peer_code = peer.wait(timeout=60)
        drain(naive)
        drain(peer)
        self.assertEqual(naive_code, 0, msg="the second writer finishes")
        self.assertEqual(peer_code, 0, msg="the peer finishes")
        return json.loads((self.project / ".claude" / "settings.local.json").read_text(encoding="utf-8"))

    def test_control_a_writer_without_the_lock_loses_its_entry_in_this_harness(self):
        final = self.race("nolock")
        self.assertIn("peerMarker", final, msg="the lock holder's entry is there")
        self.assertNotIn("naiveMarker", final,
                         msg="the lockless writer's entry was overwritten by the peer's stale read-modify-write: "
                             "the harness can see a lost update")

    def test_control_a_writer_that_takes_the_lock_keeps_both_entries_in_this_harness(self):
        final = self.race("lock")
        self.assertIn("peerMarker", final, msg="the lock holder's entry is there")
        self.assertIn("naiveMarker", final, msg="the locking writer waited, so neither entry was lost")
        self.assertFalse((self.project / ".claude" / ".settings-local.lock").exists(), msg="the lock was released")


class TestHarnessSanity(unittest.TestCase):
    """Pass today: the helpers the scenarios lean on agree with the shapes they claim."""

    def test_hook_key_reads_exec_and_string_forms(self):
        exec_form = {"command": "py", "args": ["-3", "C:\\x\\.claude\\hooks\\a.py", "--carry-forward"]}
        string_form = {"command": 'py -3 "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/b.py"'}
        self.assertEqual(hook_key(exec_form)[:2], ("a.py", ("--carry-forward",)))
        self.assertEqual(hook_key(string_form)[:2], ("b.py", ()))
        self.assertIsNone(hook_key({"command": "echo hi"}))

    def test_the_contract_table_has_17_entries_and_five_async(self):
        self.assertEqual(len(CONTRACT_ENTRIES), 17)
        self.assertEqual({e[2] for e in CONTRACT_ENTRIES if e[4]}, ASYNC_SCRIPTS)

    def test_the_report_only_stand_in_writes_nothing_and_prints_a_banner(self):
        tmp = Path(tempfile.mkdtemp(prefix="hrc-stub-")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        stub = tmp / "stub.py"
        stub.write_text(REPORT_ONLY_CHECK, encoding="utf-8")
        result = subprocess.run([sys.executable, str(stub)], cwd=str(tmp), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(json.loads(result.stdout)["systemMessage"])
        self.assertEqual([p.name for p in tmp.iterdir()], ["stub.py"], msg="it wrote no file")


if __name__ == "__main__":
    unittest.main(verbosity=1)
