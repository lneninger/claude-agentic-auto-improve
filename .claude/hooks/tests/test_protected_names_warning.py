#!/usr/bin/env python3
"""test_protected_names_warning.py -- RED suite for the turn-end warning of the Protected-name check.

PLUGIN-ONLY. This file pins files that exist only in the plugin repository (the warning hook, hooks.json,
stop-dispatcher.py, the plugin's verify-before-done skill), so it is never vendored into a consuming
repository. The check's own logic is pinned in test_protected_names.py, which is vendored.

Contract: .claude/concepts/2026-10-13-database-guard-names-in-rules-file.md in the consuming repository
(parent issue #623, sub-task 1 of 13): Data Shapes (Events, Commands, "What the check does in each
setting"), Extension Points (the Stop registration) and the plugin's verify-before-done Step.

THE FORM PINNED (the contract's first step, recorded in the pull request)
-----------------------------------------------------------------------
Form (B). The Claude Code hooks documentation was not reachable from this run and the plugin's only
asynchronous Stop row (memory-pager.py) never speaks, so the documentation is silent for this purpose.
The TASK says to pin form (B) in that case: the hook is a member of ``stop-dispatcher.py``'s ``CHECKS``
list (no new process start), ``hooks.json`` gains NO entry, and the hook has a no-change fast path: no git
call runs when neither tree's rules file (size and modification time) nor the default-branch ref changed
since its last run in the session.

WHAT IS PINNED
--------------
  (e) protected-names-warning.py: exit 0 on every path, its own exception included; one systemMessage
      for a removal, none the second time in the same session for the same set, one again when the set
      changes; silent with no origin; one noted line per session when origin exists but its ref cannot
      be read; checks both the cwd tree and the CLAUDE_PROJECT_DIR tree; never runs ``git fetch`` (proven
      with a trace of every git process the run starts); no git call at all when nothing changed.
  (f) the registration of form (B): stop-dispatcher.py's CHECKS names the hook and hooks.json holds no
      entry for it. The real dispatcher then delivers the hook's systemMessage.
  (g) skills/verify-before-done/SKILL.md has a "Protected database names" step that runs the INSTALLED
      plugin's protected_names_check.py with --fetch (never a project path) and prints the "changes the
      check's own code" note.

Each of (e), (f) and (g) fails when the thing it pins is removed: the controls at the end of each group
run the same judgement on a copy with the thing taken out.

RECORDING GIT. The TASK asks for a recording git shim first on PATH. A shim has to be an .exe on Windows
(a process started as "git" is never resolved to a .cmd), so every git process is recorded with
GIT_TRACE2_EVENT instead: it lists the argument list of every git process the run starts, including the
ones the hook starts through a helper. That records strictly more than a shim on PATH does.

Run:
    py -3 .claude/hooks/tests/test_protected_names_warning.py
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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_protected_names import (RULES_REL, _GIT_ENV, _rm_tree, git, make_git_shim, make_world,  # noqa: E402
                                  read_shim_log, rules_bytes)

CLAUDE_DIR = HERE.parents[1]
PLUGIN_ROOT = CLAUDE_DIR.parent
HOOKS_DIR = CLAUDE_DIR / "hooks"
HOOK_NAME = "protected-names-warning.py"
HOOK = HOOKS_DIR / HOOK_NAME
DISPATCHER = HOOKS_DIR / "stop-dispatcher.py"
HOOKS_JSON = HOOKS_DIR / "hooks.json"
SKILL = PLUGIN_ROOT / "skills" / "verify-before-done" / "SKILL.md"

A = ["Alpha_One", "Alpha_Two"]
B = ["Beta_One", "Beta_Two"]


class WarningCase(unittest.TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="pnwarn-test-")).resolve()
        self.addCleanup(_rm_tree, self.root)
        self.state = self.root / "state"       # TEMP, TMP, HOME: every file the hook keeps lands here
        self.state.mkdir()
        self.trace = self.root / "git-trace.json"
        self.neutral = self.root / "neutral"   # the process working folder: neither tree
        self.neutral.mkdir()

    # -- fixtures --------------------------------------------------------------------------------------
    def tree(self, name, default_names, working_names, **kw):
        folder = self.root / name
        folder.mkdir()
        working = {RULES_REL: rules_bytes(working_names)} if working_names is not None else {}
        return make_world(folder, {RULES_REL: rules_bytes(default_names)}, working, **kw)

    def narrowed(self, name="tree-alpha", default=None, working=None):
        default = default or A
        return self.tree(name, default, working if working is not None else default[:1])

    # -- running ---------------------------------------------------------------------------------------
    def env(self, project=None, extra=None):
        env = dict(_GIT_ENV)
        for key in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE"):
            env[key] = str(self.state)
        env["CLAUDE_CONFIG_DIR"] = str(self.state)
        env["GIT_TRACE2_EVENT"] = str(self.trace)
        if getattr(self, "shim_on", False):
            env["PATH"] = str(self.shim_dir) + os.pathsep + os.environ.get("PATH", "")
        env.pop("CLAUDE_PROJECT_DIR", None)
        if project is not None:
            env["CLAUDE_PROJECT_DIR"] = str(project)
        env.update(extra or {})
        return env

    def run_script(self, script, payload, project=None, extra=None, raw=None):
        data = raw if raw is not None else json.dumps(payload).encode("utf-8")
        proc = subprocess.run(["py", "-3", str(script)], input=data, capture_output=True,
                              cwd=str(self.neutral), env=self.env(project, extra), timeout=60)
        out = proc.stdout.decode("utf-8", errors="replace")
        err = proc.stderr.decode("utf-8", errors="replace")
        obj = None
        if out.strip():
            try:
                parsed = json.loads(out)
                obj = parsed if isinstance(parsed, dict) else None
            except ValueError:
                pass
        return proc.returncode, obj, out, err

    def stop(self, session, cwd, project=None, extra=None):
        """One Stop event of the hook alone."""
        return self.run_script(HOOK, {"session_id": session, "cwd": str(cwd), "hook_event_name": "Stop"},
                               project=project, extra=extra)

    def use_shim(self):
        """NAMED EDIT (#623 t14): recorder moved off GIT_TRACE2_EVENT because remedy invariant C2 removes that
        variable from every git call. A rule that calls this records through a recording git shim instead."""
        self.shim_dir, self.shim_log = self.root / "shim-bin", self.root / "git-shim.log"
        make_git_shim(self.shim_dir, self.shim_log)
        self.shim_on = True

    def git_calls(self):
        """The argument lists of every git process recorded since the last ``reset_trace``."""
        if getattr(self, "shim_on", False):
            return [["git"] + r["args"] for r in read_shim_log(self.shim_log)]
        if not self.trace.exists():
            return []
        calls = []
        for line in self.trace.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("event") == "start" and rec.get("argv"):
                calls.append([str(a) for a in rec["argv"]])
        return calls

    def reset_trace(self):
        if getattr(self, "shim_on", False):
            if self.shim_log.exists():
                self.shim_log.unlink()
            return
        if self.trace.exists():
            self.trace.unlink()

    def say(self, session, cwd, project=None):
        """Run one Stop event and return the systemMessage text ('' when silent). Exit must be 0."""
        rc, obj, out, err = self.stop(session, cwd, project)
        self.assertEqual(rc, 0, "the hook exits 0 on every path. stdout=%r stderr=%r" % (out[:200], err[:400]))
        if obj is None:
            self.assertEqual(out.strip(), "", "output that is not a JSON object must be empty. got %r" % out[:200])
            return ""
        return str(obj.get("systemMessage") or "")


# =====================================================================================================
# (e) the hook
# =====================================================================================================
class HookBehaviourTests(WarningCase):

    def test_the_hook_exists(self):
        self.assertTrue(HOOK.is_file(), "%s must exist" % HOOK)

    def test_a_removal_gives_one_system_message_naming_the_tree_and_the_missing_name(self):
        tree = self.narrowed()
        sid = "s" + uuid.uuid4().hex
        rc, obj, out, err = self.stop(sid, tree, project=tree)
        self.assertEqual(rc, 0, "exit 0. stderr=%r" % err[:400])
        self.assertIsNotNone(obj, "one JSON object with a systemMessage. stdout=%r" % out[:200])
        message = str(obj.get("systemMessage") or "")
        self.assertIn(A[1], message, "the message names the missing string")
        self.assertIn("tree-alpha", message, "and the tree it was found in")
        self.assertEqual(out.strip().count("\n"), 0, "exactly one object on one line, not several")

    def test_the_same_set_in_the_same_session_is_silent_the_second_time(self):
        tree = self.narrowed()
        sid = "s" + uuid.uuid4().hex
        self.assertIn(A[1], self.say(sid, tree, tree), "control: the first run speaks")
        self.assertEqual(self.say(sid, tree, tree), "", "the second run, same session, same set: nothing")

    def test_a_changed_set_speaks_again_in_the_same_session(self):
        tree = self.narrowed(default=A + ["Alpha_Three"], working=A[:1])
        sid = "s" + uuid.uuid4().hex
        first = self.say(sid, tree, tree)
        self.assertIn(A[1], first, "control: the first run speaks")
        (tree / RULES_REL).write_bytes(rules_bytes(["Unrelated_Only"]))
        second = self.say(sid, tree, tree)
        self.assertNotIn(A[0], first, "control: the first set did not hold the first name")
        self.assertIn(A[0], second, "a different missing set is a new set: the hook speaks again")

    def test_a_new_session_speaks_again_for_the_same_set(self):
        tree = self.narrowed()
        self.assertIn(A[1], self.say("s" + uuid.uuid4().hex, tree, tree))
        self.assertIn(A[1], self.say("s" + uuid.uuid4().hex, tree, tree), "the quiet is per session")

    def test_a_kept_tree_is_silent(self):
        tree = self.tree("tree-kept", A, A)
        self.assertEqual(self.say("s" + uuid.uuid4().hex, tree, tree), "")

    def test_no_origin_is_silent_on_every_run(self):
        tree = self.tree("tree-local", A, A[:1], origin=False)
        sid = "s" + uuid.uuid4().hex
        for _ in range(2):
            rc, obj, out, err = self.stop(sid, tree, project=tree)
            self.assertEqual((rc, out.strip(), err.strip()), (0, "", ""), "no origin: nothing to say")

    def test_an_origin_whose_ref_cannot_be_read_is_noted_once_per_session(self):
        tree = self.tree("tree-noref", A, A[:1], ref=None)
        sid = "s" + uuid.uuid4().hex
        rc, obj, out, err = self.stop(sid, tree, project=tree)
        self.assertEqual(rc, 0)
        noted = (out + err).strip()
        self.assertNotEqual(noted, "", "origin exists but its ref cannot be read: one noted line")
        self.assertLessEqual(len(noted.splitlines()), 3, "a line, not a report. got %r" % noted[:400])
        rc2, obj2, out2, err2 = self.stop(sid, tree, project=tree)
        self.assertEqual((rc2, (out2 + err2).strip()), (0, ""), "the second run in the session is silent")
        rc3, obj3, out3, err3 = self.stop("s" + uuid.uuid4().hex, tree, project=tree)
        self.assertNotEqual((out3 + err3).strip(), "", "a new session is noted again")

    def test_it_checks_the_cwd_tree_and_the_project_dir_tree_each_once(self):
        cwd_tree = self.tree("tree-cwd", A, A[:1])
        proj_tree = self.tree("tree-proj", B, B[:1])
        message = self.say("s" + uuid.uuid4().hex, cwd_tree, proj_tree)
        self.assertIn(A[1], message, "the cwd tree's removal is reported")
        self.assertIn(B[1], message, "the CLAUDE_PROJECT_DIR tree's removal is reported")
        self.assertEqual(message.count(A[1]), 1, "each tree once")
        self.assertEqual(message.count(B[1]), 1, "each tree once")

    def test_only_the_cwd_tree_removed_names_only_it(self):
        cwd_tree = self.tree("tree-cwd", A, A[:1])
        proj_tree = self.tree("tree-proj", B, B)
        message = self.say("s" + uuid.uuid4().hex, cwd_tree, proj_tree)
        self.assertIn(A[1], message)
        self.assertNotIn(B[1], message)

    def test_only_the_project_dir_tree_removed_names_only_it(self):
        cwd_tree = self.tree("tree-cwd", A, A)
        proj_tree = self.tree("tree-proj", B, B[:1])
        message = self.say("s" + uuid.uuid4().hex, cwd_tree, proj_tree)
        self.assertIn(B[1], message)
        self.assertNotIn(A[1], message)

    def test_the_same_tree_as_cwd_and_project_dir_is_reported_once(self):
        tree = self.narrowed()
        message = self.say("s" + uuid.uuid4().hex, tree, tree)
        self.assertEqual(message.count(A[1]), 1, "one tree reached by two routes is one report")

    def test_it_never_runs_git_fetch(self):
        self.use_shim()  # recorder moved off GIT_TRACE2_EVENT because remedy invariant C2 removes that variable from every git call (#623 t14)
        tree = self.narrowed()
        self.reset_trace()
        self.say("s" + uuid.uuid4().hex, tree, tree)
        calls = self.git_calls()
        self.assertTrue(calls, "control: the hook reads the tree with git, so git processes were recorded")
        self.assertEqual([c for c in calls if "fetch" in c[1:]], [], "a Stop hook never touches the network")

    def test_it_never_runs_git_fetch_when_the_ref_cannot_be_read(self):
        self.use_shim()  # recorder moved off GIT_TRACE2_EVENT because remedy invariant C2 removes that variable from every git call (#623 t14)
        tree = self.tree("tree-noref", A, A[:1], ref=None)
        self.reset_trace()
        rc, obj, out, err = self.stop("s" + uuid.uuid4().hex, tree, project=tree)
        self.assertEqual(rc, 0, "control: the hook ran and exited 0. stderr=%r" % err[:300])
        self.assertTrue(self.git_calls(), "control: the hook looked at the repository with git")
        self.assertEqual([c for c in self.git_calls() if "fetch" in c[1:]], [], "not even to look for the ref")

    # -- exit 0 on every path ---------------------------------------------------------------------------
    def test_exit_zero_on_input_that_is_not_json(self):
        rc, obj, out, err = self.run_script(HOOK, None, raw=b"this is not json")
        self.assertEqual(rc, 0, "a Stop hook never holds a session. stderr=%r" % err[:300])

    def test_exit_zero_on_empty_input(self):
        rc, obj, out, err = self.run_script(HOOK, None, raw=b"")
        self.assertEqual(rc, 0, "stderr=%r" % err[:300])

    def test_exit_zero_when_the_payload_holds_the_wrong_types(self):
        rc, obj, out, err = self.run_script(HOOK, {"session_id": {"a": 1}, "cwd": 5})
        self.assertEqual(rc, 0, "stderr=%r" % err[:300])

    def test_exit_zero_when_the_cwd_does_not_exist(self):
        rc, obj, out, err = self.stop("s" + uuid.uuid4().hex, self.root / "no-such-folder")
        self.assertEqual(rc, 0, "stderr=%r" % err[:300])

    def test_exit_zero_when_the_rules_file_cannot_be_read(self):
        tree = self.narrowed()
        (tree / RULES_REL).unlink()
        (tree / RULES_REL).mkdir()  # a folder where the file should be: reading it raises
        rc, obj, out, err = self.stop("s" + uuid.uuid4().hex, tree, project=tree)
        self.assertEqual(rc, 0, "its own exception is caught. stderr=%r" % err[:300])

    def test_exit_zero_when_git_itself_cannot_run(self):
        tree = self.narrowed()
        rc, obj, out, err = self.stop("s" + uuid.uuid4().hex, tree, project=tree,
                                      extra={"PATH": str(self.neutral)})
        self.assertEqual(rc, 0, "no git on PATH is a 'could not check', never a held session. stderr=%r" % err[:300])

    def test_exit_zero_when_the_git_folder_is_damaged(self):
        tree = self.narrowed()
        (tree / ".git" / "HEAD").write_text("garbage\n", encoding="utf-8")
        rc, obj, out, err = self.stop("s" + uuid.uuid4().hex, tree, project=tree)
        self.assertEqual(rc, 0, "stderr=%r" % err[:300])

    # -- form (B): no git call when nothing changed ------------------------------------------------------
    def test_no_git_call_runs_when_nothing_changed_since_its_last_run_in_the_session(self):
        self.use_shim()  # recorder moved off GIT_TRACE2_EVENT because remedy invariant C2 removes that variable from every git call (#623 t14)
        tree = self.narrowed()
        sid = "s" + uuid.uuid4().hex
        self.reset_trace()
        self.say(sid, tree, tree)
        self.assertTrue(self.git_calls(), "control: the first run in the session reads the tree with git")
        self.reset_trace()
        self.say(sid, tree, tree)
        self.assertEqual(self.git_calls(), [], "form (B) fast path: nothing changed, so not one git process")

    def test_a_changed_rules_file_ends_the_fast_path(self):
        self.use_shim()  # recorder moved off GIT_TRACE2_EVENT because remedy invariant C2 removes that variable from every git call (#623 t14)
        tree = self.narrowed(default=A + ["Alpha_Three"], working=A[:1])
        sid = "s" + uuid.uuid4().hex
        self.say(sid, tree, tree)
        (tree / RULES_REL).write_bytes(rules_bytes(["X"]))
        self.reset_trace()
        self.say(sid, tree, tree)
        self.assertTrue(self.git_calls(), "the file's size changed, so the hook looks again")

    def test_a_moved_default_branch_ref_ends_the_fast_path(self):
        self.use_shim()  # recorder moved off GIT_TRACE2_EVENT because remedy invariant C2 removes that variable from every git call (#623 t14)
        tree = self.narrowed()
        sid = "s" + uuid.uuid4().hex
        self.say(sid, tree, tree)
        # Move origin/master to a new commit built with git plumbing, so the working file on disk is
        # untouched (same size, same modification time): only the default-branch ref changes.
        scratch_file = self.root / "moved-rules.json"
        scratch_file.write_bytes(rules_bytes(A + ["Alpha_Three"]))
        blob = git(tree, "hash-object", "-w", str(scratch_file))
        git(tree, "update-index", "--add", "--cacheinfo", "100644,%s,%s" % (blob, RULES_REL))
        new_tree = git(tree, "write-tree")
        commit = git(tree, "commit-tree", new_tree, "-p", "HEAD", "-m", "moved default branch")
        git(tree, "update-ref", "refs/remotes/origin/master", commit)
        self.reset_trace()
        self.say(sid, tree, tree)
        self.assertTrue(self.git_calls(), "the ref moved, so the hook looks again")


# =====================================================================================================
# (f) the registration of form (B), and the real dispatcher delivering the message
# =====================================================================================================
def dispatcher_members(source: str):
    """The CHECKS literal of a dispatcher source, read statically; None when it declares none."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "CHECKS" for t in node.targets):
            try:
                return [m for m in ast.literal_eval(node.value) if isinstance(m, str)]
            except ValueError:
                return None
    return None


def hooks_json_entries_naming(cfg: dict, name: str):
    found = []
    for event, groups in (cfg.get("hooks") or {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                if any(name in str(a) for a in (hook.get("args") or [])) or name in str(hook.get("command", "")):
                    found.append(event)
    return found


def form_b_problems(dispatcher_source: str, cfg: dict):
    """What is wrong with the registration of form (B). An empty list means it is right."""
    problems = []
    members = dispatcher_members(dispatcher_source)
    if members is None or HOOK_NAME not in members:
        problems.append("stop-dispatcher.py's CHECKS does not name %s (it names %s)" % (HOOK_NAME, members))
    named = hooks_json_entries_naming(cfg, HOOK_NAME)
    if named:
        problems.append("hooks.json registers %s itself under %s; form (B) adds no entry" % (HOOK_NAME, named))
    return problems


class RegistrationTests(WarningCase):

    def test_the_dispatcher_names_the_hook_and_hooks_json_holds_no_entry_for_it(self):
        self.assertTrue(DISPATCHER.is_file() and HOOKS_JSON.is_file(), "both files exist")
        problems = form_b_problems(DISPATCHER.read_text(encoding="utf-8"), json.loads(HOOKS_JSON.read_text(encoding="utf-8")))
        self.assertEqual(problems, [], "form (B): " + "; ".join(problems))

    def test_hooks_json_still_registers_thirteen_entries(self):
        cfg = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        count = sum(len(g.get("hooks", [])) for groups in cfg["hooks"].values() for g in groups)
        self.assertEqual(count, 13, "form (B) adds no hooks.json entry, so the count the manifest suite pins stays 13")

    def test_the_hook_file_is_run_by_the_dispatcher_not_registered_twice(self):
        cfg = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        self.assertEqual(hooks_json_entries_naming(cfg, HOOK_NAME), [], "a second registration would run it twice")

    # -- controls: the judgement fails when the thing it pins is removed ---------------------------------
    def test_control_a_dispatcher_without_the_member_is_reported(self):
        self.assertTrue(form_b_problems('CHECKS = ["../scripts/concept_changed_check.py"]\n', {"hooks": {}}),
                        "removing the member must make the registration check fail")

    def test_control_a_dispatcher_with_the_member_and_a_clean_hooks_json_is_accepted(self):
        src = 'CHECKS = ["../scripts/concept_changed_check.py", "%s"]\n' % HOOK_NAME
        self.assertEqual(form_b_problems(src, {"hooks": {}}), [])

    def test_control_a_second_registration_in_hooks_json_is_reported(self):
        src = 'CHECKS = ["%s"]\n' % HOOK_NAME
        cfg = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "py",
                                              "args": ["-3", "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/" + HOOK_NAME]}]}]}}
        self.assertTrue(form_b_problems(src, cfg), "a hook that the dispatcher runs must not also be registered")

    # -- the real dispatcher delivers the message ---------------------------------------------------------
    def test_the_real_stop_dispatcher_delivers_the_hooks_system_message(self):
        tree = self.narrowed()
        sid = "s" + uuid.uuid4().hex
        rc, obj, out, err = self.run_script(DISPATCHER, {"session_id": sid, "cwd": str(tree), "hook_event_name": "Stop"},
                                            project=tree)
        self.assertEqual(rc, 0, "the dispatcher exits 0 when no member stops the turn. stderr=%r" % err[:400])
        self.assertIn(A[1], out, "the missing name reaches the session through the dispatcher's output. out=%r err=%r"
                      % (out[:300], err[:300]))
        self.assertIsNotNone(obj, "merged into one JSON object")
        self.assertIn(A[1], str(obj.get("systemMessage")))


# =====================================================================================================
# (g) the plugin's skill
# =====================================================================================================
STEP_HEADING = re.compile(r"(?m)^##\s+Step\s+(5\.\d+):\s*Protected database names\s*$")
ANY_STEP_HEADING = re.compile(r"(?m)^##\s+Step\s+([0-9]+(?:\.[0-9]+)?):")


def skill_section(text: str):
    """The text of the 'Protected database names' step, or None when the step is absent."""
    match = STEP_HEADING.search(text)
    if not match:
        return None
    rest = text[match.end():]
    following = re.search(r"(?m)^##\s", rest)
    return rest[:following.start()] if following else rest


def skill_problems(text: str):
    problems = []
    section = skill_section(text)
    if section is None:
        return ["there is no 'Step 5.<n>: Protected database names' heading"]
    numbers = ANY_STEP_HEADING.findall(text)
    duplicated = sorted({n for n in numbers if numbers.count(n) > 1})
    if duplicated:
        problems.append("step numbers used twice: %s (5.6 is already the registry structure lint)" % duplicated)
    if "protected_names_check.py" not in section:
        problems.append("the step never names protected_names_check.py")
    invocations = [l for l in section.splitlines() if re.search(r"\bpy\s+-3\b.*protected_names_check\.py|\"\$PNC\"", l)]
    if not any("--fetch" in l for l in invocations):
        problems.append("no invocation line carries --fetch")
    if re.search(r'(?m)^\s*(if|elif)\s+\[\s+-f\s+"\$S"\s+\]', section):
        problems.append("the lookup tests the project's own copy first; the installed plugin's copy must be the only one")
    if re.search(r"py\s+-3\s+[\"']?\.{0,2}/?\.claude/scripts/protected_names_check\.py", section):
        problems.append("an invocation names a project path")
    for needle in ("CLAUDE_PLUGIN_ROOT", "installed_plugins.json", "plugins/cache"):
        if needle not in section:
            problems.append("the lookup never reads %s" % needle)
    if "changes the check's own code" not in section:
        problems.append("the note \"changes the check's own code\" is not printed")
    for code in ("10", "11", "12"):
        if not re.search(r"(?<!\d)%s(?!\d)" % code, section):
            problems.append("exit code %s is not handled" % code)
    return problems


class SkillTests(WarningCase):

    def test_the_skill_step_runs_the_installed_plugins_check_with_fetch(self):
        self.assertTrue(SKILL.is_file(), "%s must exist" % SKILL)
        problems = skill_problems(SKILL.read_text(encoding="utf-8"))
        self.assertEqual(problems, [], "; ".join(problems))

    def test_control_a_skill_without_the_step_is_reported(self):
        self.assertTrue(skill_problems("## Step 5.5: Safety-critical review gate\n\ntext\n"))

    def test_control_a_step_that_runs_the_projects_copy_is_reported(self):
        text = ("## Step 5.7: Protected database names\n\n```bash\n"
                'S=.claude/scripts/protected_names_check.py\nif [ -f "$S" ]; then PNC=$S\nfi\n'
                'py -3 "$PNC" --fetch --project .\n```\nexit 10 11 12 CLAUDE_PLUGIN_ROOT installed_plugins.json '
                "plugins/cache changes the check's own code\n")
        self.assertTrue(any("project" in p for p in skill_problems(text)),
                        "a step that looks in the project first must be reported")

    def test_control_a_step_that_is_complete_is_accepted(self):
        text = ("## Step 5.7: Protected database names\n\n```bash\n"
                'S=.claude/scripts/protected_names_check.py\n'
                'if [ -n "$CLAUDE_PLUGIN_ROOT" ] && [ -f "$CLAUDE_PLUGIN_ROOT/$S" ]; then PNC=$CLAUDE_PLUGIN_ROOT/$S\nelse\n'
                '  REC=$(cat "$CFG/plugins/installed_plugins.json"); ls "$CFG"/plugins/cache/*/agentic-auto-improve/*/\nfi\n'
                'py -3 "$PNC" --fetch --project "$CLAUDE_PROJECT_DIR"\n```\n'
                "Exit 0 passes; 10 and 11 are NOT-READY; 12 is a disclosed item. "
                "If this branch changes the check's own code, say so.\n")
        self.assertEqual(skill_problems(text), [], "the control's own text must pass: " + "; ".join(skill_problems(text)))


# =====================================================================================================
# REVISION 5 REMEDY (block 14, RED): R5-B2-5 (the hook under a replace ref) and R5-W3-1, R5-W3-2 (what
# Step 5.7 of the skill runs, and on which tree). Gate 3's finding B2 and warning W3; invariant C4.
#
# The Step 5.7 rows RUN the skill's own bash block, not a text pattern: the block is read from the skill,
# executed by a bash, and the ``py`` it ends in is a recording shell script first on PATH, so what the
# block would have started is what the row reads. Every folder is test-owned and removed afterwards.
# =====================================================================================================
def git_bash():
    """A bash that can run the skill's block: Git's own on Windows (never the WSL launcher in System32)."""
    found = shutil.which("git")
    if found:
        for parent in Path(found).resolve().parents:
            candidate = parent / "bin" / "bash.exe"
            if candidate.is_file():
                return str(candidate)
    return shutil.which("bash") if os.name != "nt" else None


def step_bash_block():
    """The first bash block of Step 5.7 (the lookup and the call), or None."""
    section = skill_section(SKILL.read_text(encoding="utf-8")) if SKILL.is_file() else None
    match = re.search(r"```bash\n(.*?)```", section or "", re.S)
    return match.group(1) if match else None


def posix_norm(path):
    text = str(path).replace("\\", "/").rstrip("/").lower()
    return re.sub(r"^/([a-z])/", r"\1:/", text)


class ReplaceRefHookTests(WarningCase):

    def test_R5_B2_5_the_hook_under_a_replace_ref_on_the_default_branchs_rules_blob_still_emits_its_one_system_message(self):
        tree = self.narrowed()
        control = self.say("s" + uuid.uuid4().hex, tree, tree)
        self.assertIn(A[1], control, "control: before the replace ref the hook speaks")
        default_blob = git(tree, "rev-parse", "refs/remotes/origin/master:" + RULES_REL)
        narrowed_blob = git(tree, "hash-object", "-w", str(tree / RULES_REL))
        self.assertNotEqual(default_blob, narrowed_blob, "control: the two blobs differ")
        git(tree, "replace", default_blob, narrowed_blob)
        rc, obj, out, err = self.stop("s" + uuid.uuid4().hex, tree, project=tree)
        self.assertEqual(rc, 0, "exit 0 on every path. stderr=%r" % err[:300])
        self.assertIsNotNone(obj, "a replace ref must not silence the warning: one JSON object with a systemMessage. "
                                  "stdout=%r stderr=%r" % (out[:200], err[:300]))
        self.assertIn(A[1], str(obj.get("systemMessage")), "the message still names the missing string")
        self.assertEqual(out.strip().count("\n"), 0, "and it is one message, not several")


class StepBlockCase(WarningCase):
    """Runs Step 5.7's bash block with a recording ``py`` and returns the arguments that ``py`` received."""

    def setUp(self):
        super().setUp()
        self.bash = git_bash()
        if self.bash is None:
            self.skipTest("no bash that can run the skill's block (Git's bash.exe) was found")
        self.block = step_bash_block()
        self.assertIsNotNone(self.block, "Step 5.7 must hold a bash block (the lookup and the call)")
        self.shim = self.root / "py-shim"
        self.shim.mkdir()
        self.rec = self.root / "py-args.txt"
        (self.shim / "py").write_text("#!/bin/sh\nfor a in \"$@\"; do printf '%s\\n' \"$a\"; done >> \"$REC_LOG\"\nexit 0\n",
                                      encoding="utf-8", newline="\n")
        self.cfg = self.root / "claude-config"
        self.cfg.mkdir()
        self.launch = self.root / "launch-tree"
        self.launch.mkdir()

    def plugin_with_checker(self, folder):
        script = Path(folder) / ".claude" / "scripts" / "protected_names_check.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# a checker\n", encoding="utf-8")
        return script

    def run_block(self, cwd, plugin_root=None, project_dir=None):
        env = {"PATH": str(self.shim) + os.pathsep + os.environ.get("PATH", ""), "REC_LOG": str(self.rec),
               "HOME": str(self.state), "TEMP": str(self.state), "TMP": str(self.state),
               "CLAUDE_CONFIG_DIR": str(self.cfg)}
        for key in ("SYSTEMROOT", "WINDIR", "COMSPEC"):
            if key in os.environ:
                env[key] = os.environ[key]
        if plugin_root is not None:
            env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
        if project_dir is not None:
            env["CLAUDE_PROJECT_DIR"] = str(project_dir)
        proc = subprocess.run([self.bash, "-c", self.block], cwd=str(cwd), env=env, capture_output=True, text=True, timeout=120)
        args = self.rec.read_text(encoding="utf-8").splitlines() if self.rec.exists() else []
        return args, proc

    def project_arg(self, args, proc):
        self.assertIn("--project", args, "the step starts the checker with --project. args=%r stderr=%r" % (args, proc.stderr[-300:]))
        return args[args.index("--project") + 1]

    def script_arg(self, args):
        self.assertIn("-3", args, "the step runs py -3 <checker>. args=%r" % args)
        return args[args.index("-3") + 1]


class StepFiveSevenProjectTests(StepBlockCase):

    def test_R5_W3_1_the_project_is_the_tree_git_reports_not_the_launch_tree(self):
        tree = self.tree("tree-w3", A, A)
        cwd = tree / "sub" / "deeper"
        cwd.mkdir(parents=True)
        plugin = self.root / "plugin"
        self.plugin_with_checker(plugin)
        args, proc = self.run_block(cwd, plugin_root=plugin, project_dir=self.launch)
        self.assertEqual(posix_norm(self.script_arg(args)), posix_norm(plugin / ".claude" / "scripts" / "protected_names_check.py"),
                         "control: the checker is the one in CLAUDE_PLUGIN_ROOT")
        want = git(cwd, "rev-parse", "--show-toplevel")
        self.assertEqual(posix_norm(self.project_arg(args, proc)), posix_norm(want),
                         "--project is `git rev-parse --show-toplevel` of the current folder (%s), never "
                         "$CLAUDE_PROJECT_DIR (%s) while git can answer" % (want, self.launch))

    def test_R5_W3_1_when_git_cannot_answer_claude_project_dir_is_the_fallback(self):
        plugin = self.root / "plugin"
        self.plugin_with_checker(plugin)
        args, proc = self.run_block(self.neutral, plugin_root=plugin, project_dir=self.launch)
        self.assertEqual(posix_norm(self.project_arg(args, proc)), posix_norm(self.launch),
                         "git cannot answer in a folder that is no repository: $CLAUDE_PROJECT_DIR is used")

    def test_R5_W3_1_control_the_recording_py_sees_the_flags_the_block_passes(self):
        plugin = self.root / "plugin"
        self.plugin_with_checker(plugin)
        args, proc = self.run_block(self.neutral, plugin_root=plugin, project_dir=self.launch)
        self.assertIn("--fetch", args, "control: the shim recorded the real invocation (%r)" % args)


class StepFiveSevenCheckerLookupTests(StepBlockCase):

    def _install_record(self, install_path, scope="user"):
        record = {"version": 2, "plugins": {"agentic-auto-improve@auto-improve": [
            {"scope": scope, "installPath": str(install_path), "version": "0.16.5"}]}}
        (self.cfg / "plugins").mkdir(exist_ok=True)
        (self.cfg / "plugins" / "installed_plugins.json").write_text(json.dumps(record, indent=2), encoding="utf-8")

    def _caches(self):
        reviewed = self.cfg / "plugins" / "cache" / "auto-improve" / "agentic-auto-improve" / "0.16.5"
        newer = self.cfg / "plugins" / "cache" / "auto-improve" / "agentic-auto-improve" / "0.18.4"
        self.plugin_with_checker(reviewed)
        self.plugin_with_checker(newer)  # written last: the newest modification time as well as the highest version
        return reviewed, newer

    def test_R5_W3_2_without_claude_plugin_root_the_checker_is_the_installed_plugins_install_path(self):
        reviewed, newer = self._caches()
        self._install_record(reviewed)
        tree = self.tree("tree-w3", A, A)
        args, proc = self.run_block(tree, project_dir=tree)
        self.assertEqual(posix_norm(self.script_arg(args)), posix_norm(reviewed / ".claude" / "scripts" / "protected_names_check.py"),
                         "the installPath of the user-scope entry, never the higher-numbered or newer cache folder (%s)" % newer)

    def test_R5_W3_2_a_newer_unreviewed_cache_folder_is_never_a_fallback(self):
        reviewed, newer = self._caches()
        self._install_record(self.cfg / "plugins" / "cache" / "auto-improve" / "agentic-auto-improve" / "0.0.0-not-installed")
        tree = self.tree("tree-w3", A, A)
        args, proc = self.run_block(tree, project_dir=tree)
        text = "\n".join(posix_norm(a) for a in args)
        self.assertNotIn("0.18.4", text, "the unreviewed newest cache folder must not be run (args=%r)" % args)
        self.assertNotIn("0.16.5", text, "nor any cache folder the install record does not name (args=%r)" % args)


if __name__ == "__main__":
    unittest.main(verbosity=1)
