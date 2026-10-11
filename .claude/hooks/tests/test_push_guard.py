#!/usr/bin/env python3
"""
test_push_guard.py -- RED suite for the plugin push guard (contract
2026-10-11-post-merge-push-follow-up-pr, P-8 and P-9, sub-task 4).

WHAT THIS PINS DOWN
-------------------
``.claude/hooks/push-guard.py`` (does not exist yet) is a PreToolUse hook on
the Bash and PowerShell tools. It blocks (exit 2, stderr starting
``[push-guard] BLOCKED`` and naming the helper ``push_branch.py``) any command
that invokes ``git push``, in every spelling P-8 lists, and allows everything
else. A push to a remote whose url host is not github.com is allowed with a
decision record on stderr (``[push-guard] allowed`` + the host). An unreadable
url is treated as GitHub and blocked. The kill switch is the hook's own
environment (``CLAUDE_PUSH_GUARD`` = off, 0, false, no); an inline prefix in
the command text does not lift it. P-9: when the parser raises, the guard
blocks raw text matching ``\\bgit(\\.exe)?\\b[^\\n]*\\bpush\\b``, allows other
text, and names the exception in its banner. Malformed stdin and other tool
names are allowed.

HOW IT RUNS
-----------
The real guard file is launched as a subprocess (never imported) with a JSON
payload on stdin, cwd a temporary git repository whose origin is a github.com
url unless a row says otherwise. A missing guard file is an assertion failure
(see ``guard_run``), not an error.

ASSUMPTION FOR THE IMPLEMENTER (flagged, not in the contract)
-------------------------------------------------------------
P-9 says "forcing the parser to raise" but names no seam. These tests use the
environment variable ``PUSH_GUARD_TEST_RAISE``: when set to a non-empty text,
the parser step must raise ``RuntimeError(<that text>)``. The fallback banner
must name ``RuntimeError`` and the text. If t5 picks another seam, change
``FORCE_RAISE_ENV`` here and nothing else.

CONTROLS THAT PASS TODAY (they prove the fixtures work, so a red row is red
for the guard's absence and not for a broken fixture)
-----------------------------------------------------
  * test_control_github_repo_fixture_reads_origin_url
  * test_control_other_host_repo_fixture_reads_origin_url
  * test_control_no_origin_repo_fixture_has_no_origin
Every other test fails today by assertion (the guard file is absent).

Run:
    py -3 -B .claude/hooks/tests/test_push_guard.py

Exit code: 0 all pass, 1 any failure or error.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD = HERE.parent / "push-guard.py"
FORCE_RAISE_ENV = "PUSH_GUARD_TEST_RAISE"
HELPER = "push_branch.py"
BLOCKED = "[push-guard] BLOCKED"
ALLOWED = "[push-guard] allowed"
TOOLS = ("Bash", "PowerShell")

_TMP_ROOT: Path | None = None
GH_REPO: Path
OTHER_REPO: Path
NO_ORIGIN_REPO: Path
NO_REPO: Path


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, timeout=30)


def _make_repo(name: str, origin: str | None) -> Path:
    path = _TMP_ROOT / name
    path.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], path)
    if origin is not None:
        _git(["remote", "add", "origin", origin], path)
    return path


def setUpModule():
    global _TMP_ROOT, GH_REPO, OTHER_REPO, NO_ORIGIN_REPO, NO_REPO
    _TMP_ROOT = Path(tempfile.mkdtemp(prefix="push-guard-red-"))
    GH_REPO = _make_repo("gh", "https://github.com/acme/widgets.git")
    OTHER_REPO = _make_repo("other", "https://gitlab.example.org/acme/widgets.git")
    NO_ORIGIN_REPO = _make_repo("noorigin", None)
    NO_REPO = _TMP_ROOT / "norepo"
    NO_REPO.mkdir()


def tearDownModule():
    if _TMP_ROOT:
        shutil.rmtree(_TMP_ROOT, ignore_errors=True)


def guard_run(tool, command, cwd=None, env_extra=None, raw_stdin=None):
    """Run the guard once; return (exit_code, stderr). Missing guard = failure."""
    if not GUARD.is_file():
        raise AssertionError(f"push guard does not exist yet: {GUARD}")
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PUSH_GUARD", FORCE_RAISE_ENV)}
    env["GIT_CEILING_DIRECTORIES"] = str(_TMP_ROOT.parent)
    env.update(env_extra or {})
    stdin = raw_stdin if raw_stdin is not None else json.dumps(
        {"tool_name": tool, "tool_input": {"command": command}})
    proc = subprocess.run([sys.executable, "-B", str(GUARD)], input=stdin,
                          capture_output=True, text=True, cwd=str(cwd or GH_REPO),
                          env=env, timeout=30)
    return proc.returncode, proc.stderr


class PushGuardBase(unittest.TestCase):
    def assert_blocked(self, tool, command, **kw):
        code, err = guard_run(tool, command, **kw)
        self.assertEqual(code, 2, msg=f"{tool}: {command!r} must exit 2; stderr={err!r}")
        self.assertIn(BLOCKED, err, msg=f"{tool}: {command!r} banner literal; stderr={err!r}")
        self.assertIn(HELPER, err, msg=f"{tool}: {command!r} banner must name the helper")

    def assert_allowed(self, tool, command, **kw):
        code, err = guard_run(tool, command, **kw)
        self.assertEqual(code, 0, msg=f"{tool}: {command!r} must exit 0; stderr={err!r}")
        self.assertNotIn(BLOCKED, err, msg=f"{tool}: {command!r} must not be blocked")


class FixtureControls(unittest.TestCase):
    def test_control_github_repo_fixture_reads_origin_url(self):
        r = _git(["remote", "get-url", "origin"], GH_REPO)
        self.assertIn("github.com", r.stdout, msg="fixture origin must be github.com")

    def test_control_other_host_repo_fixture_reads_origin_url(self):
        r = _git(["remote", "get-url", "origin"], OTHER_REPO)
        self.assertIn("gitlab.example.org", r.stdout, msg="fixture origin must be another host")

    def test_control_no_origin_repo_fixture_has_no_origin(self):
        r = _git(["remote", "get-url", "origin"], NO_ORIGIN_REPO)
        self.assertNotEqual(r.returncode, 0, msg="fixture must have no origin")


class BlockedSpellings(PushGuardBase):
    def _each(self, commands):
        for tool in TOOLS:
            for cmd in commands:
                with self.subTest(tool=tool, cmd=cmd):
                    self.assert_blocked(tool, cmd)

    def test_plain_push_blocked(self):
        self._each(["git push", "git push origin main", "git push -u origin feature/x"])

    def test_dash_c_dir_push_blocked(self):
        self._each([f"git -C {GH_REPO.as_posix()} push", "git -c user.name=x push origin main",
                    "git --no-pager push", "git --git-dir=.git push"])

    def test_quoted_program_path_blocked(self):
        self._each(['"/usr/bin/git" push', "'C:/Program Files/Git/cmd/git.exe' push origin main"])

    def test_git_exe_blocked(self):
        self._each(["git.exe push", "C:/Git/cmd/git.exe push origin main"])

    def test_env_and_var_prefixes_blocked(self):
        self._each(["env git push", "command git push", "FOO=bar git push",
                    "env FOO=bar BAZ=1 git push origin main"])

    def test_chained_segments_blocked(self):
        self._each(["echo hi && git push", "git status; git push", "false || git push",
                    "git fetch | git push", "echo a\ngit push"])

    def test_nested_shell_wrappers_blocked(self):
        self._each(['bash -c "git push"', "sh -c 'git push origin main'",
                    'powershell -Command "git push"', 'pwsh -Command "git push"',
                    'pwsh -c "git push"', "cmd /c git push", "cmd /k git push"])

    def test_tag_push_and_branch_deletion_blocked(self):
        self._each(["git push origin v1.0.0", "git push --tags", "git push origin --delete old",
                    "git push origin :old"])

    def test_inline_kill_switch_prefix_does_not_lift_guard(self):
        self._each(["CLAUDE_PUSH_GUARD=off git push", "env CLAUDE_PUSH_GUARD=0 git push"])

    def test_github_url_forms_blocked(self):
        self._each(["git push https://github.com/acme/widgets.git main",
                    "git push git@github.com:acme/widgets.git main",
                    "git push ssh://git@github.com/acme/widgets.git main"])

    def test_github_origin_in_each_form_blocked(self):
        for form in ("https://github.com/a/b.git", "git@github.com:a/b.git",
                     "ssh://git@github.com/a/b.git"):
            repo = _make_repo("form-" + uuid.uuid4().hex[:6], form)
            for tool in TOOLS:
                with self.subTest(tool=tool, origin=form):
                    self.assert_blocked(tool, "git push", cwd=repo)

    def test_unreadable_url_blocked(self):
        for tool in TOOLS:
            with self.subTest(tool=tool, case="no origin"):
                self.assert_blocked(tool, "git push", cwd=NO_ORIGIN_REPO)
            with self.subTest(tool=tool, case="no repository"):
                self.assert_blocked(tool, "git push", cwd=NO_REPO)
            with self.subTest(tool=tool, case="no such remote"):
                self.assert_blocked(tool, "git push upstream main", cwd=GH_REPO)


class AllowedSpellings(PushGuardBase):
    def test_non_push_commands_allowed(self):
        for tool in TOOLS:
            for cmd in ["git stash push", "git stash push -m wip", "git status",
                        'git commit -m "docs: mention git push in the notes"',
                        "echo 'run git push later'",
                        "py -3 .claude/scripts/push_branch.py --branch x"]:
                with self.subTest(tool=tool, cmd=cmd):
                    self.assert_allowed(tool, cmd)

    def test_env_kill_switch_values_allowed(self):
        for tool in TOOLS:
            for val in ("off", "0", "false", "no"):
                with self.subTest(tool=tool, value=val):
                    self.assert_allowed(tool, "git push", env_extra={"CLAUDE_PUSH_GUARD": val})

    def test_malformed_stdin_allowed(self):
        for raw in ("", "not json", "{", "[1,2]"):
            with self.subTest(raw=raw):
                self.assert_allowed("Bash", "", raw_stdin=raw)

    def test_other_tool_name_allowed(self):
        for tool in ("Read", "Edit", "Write", "Grep"):
            with self.subTest(tool=tool):
                self.assert_allowed(tool, "git push")


class NonGitHubRemote(PushGuardBase):
    def _assert_allowed_record(self, tool, command, host, **kw):
        code, err = guard_run(tool, command, **kw)
        self.assertEqual(code, 0, msg=f"{tool}: {command!r} must exit 0; stderr={err!r}")
        self.assertTrue(err.startswith(ALLOWED),
                        msg=f"{tool}: stderr must start {ALLOWED!r}; got {err!r}")
        self.assertIn(host, err, msg="decision record must name the host")

    def test_origin_on_other_host_allowed_with_record(self):
        for tool in TOOLS:
            for cmd in ("git push", "git push origin main"):
                with self.subTest(tool=tool, cmd=cmd):
                    self._assert_allowed_record(tool, cmd, "gitlab.example.org", cwd=OTHER_REPO)

    def test_dash_c_dir_on_other_host_allowed_with_record(self):
        for tool in TOOLS:
            with self.subTest(tool=tool):
                self._assert_allowed_record(tool, f"git -C {OTHER_REPO.as_posix()} push",
                                            "gitlab.example.org", cwd=GH_REPO)

    def test_positional_url_on_other_host_allowed_with_record(self):
        for tool in TOOLS:
            for url in ("https://bitbucket.example.net/a/b.git", "git@bitbucket.example.net:a/b.git",
                        "ssh://git@bitbucket.example.net/a/b.git"):
                with self.subTest(tool=tool, url=url):
                    self._assert_allowed_record(tool, f"git push {url} main",
                                                "bitbucket.example.net", cwd=GH_REPO)


class ParserFailureFallback(PushGuardBase):
    def _raise_env(self):
        return {FORCE_RAISE_ENV: "boom-" + uuid.uuid4().hex[:8]}

    def test_parser_raise_blocks_push_text_and_names_exception(self):
        for tool in TOOLS:
            env = self._raise_env()
            with self.subTest(tool=tool):
                code, err = guard_run(tool, "git push origin main", env_extra=env)
                self.assertEqual(code, 2, msg=f"fallback must block push text; stderr={err!r}")
                self.assertIn(BLOCKED, err, msg="fallback banner literal")
                self.assertIn(HELPER, err, msg="fallback banner names the helper")
                self.assertIn("RuntimeError", err, msg="banner names the exception type")
                self.assertIn(env[FORCE_RAISE_ENV], err, msg="banner names the exception text")

    def test_parser_raise_blocks_git_exe_push_text(self):
        for tool in TOOLS:
            with self.subTest(tool=tool):
                code, err = guard_run(tool, "echo x && git.exe -C d push", env_extra=self._raise_env())
                self.assertEqual(code, 2, msg=f"fallback regex covers git.exe; stderr={err!r}")

    def test_parser_raise_allows_text_without_push(self):
        for tool in TOOLS:
            for cmd in ("git status", "ls -la", "echo hello"):
                with self.subTest(tool=tool, cmd=cmd):
                    code, err = guard_run(tool, cmd, env_extra=self._raise_env())
                    self.assertEqual(code, 0, msg=f"fallback must not lock the shell; stderr={err!r}")
                    self.assertNotIn(BLOCKED, err, msg="no block without push")


if __name__ == "__main__":
    unittest.main(verbosity=1)
