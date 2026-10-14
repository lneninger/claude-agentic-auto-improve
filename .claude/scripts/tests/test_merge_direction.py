#!/usr/bin/env python3
"""
test_merge_direction.py -- RED suite for the merge-direction check ``.claude/scripts/merge_direction.py``
and its trigger in the main-checkout guard.

Contract: .claude/concepts/2026-10-07-worktree-isolation-by-default.md (sub-task 3, issue #474)
Invariants pinned here: I-9 (merge direction: R-0 cross-repository, R-1 a sub-task pull request targets
its declared base, R-2 a parent opens into the default branch only when no sub-issue and no pull
request into it is open, strict inputs, ``parse_repo_spec``) and Extension Point 2 (the guard runs the
check for ``gh pr create``, ``gh pr edit`` with a base option and ``gh pr merge``).

Run:
    py -3 .claude/scripts/tests/test_merge_direction.py

THE COMMAND LINE THIS SUITE PINS (the contract names the options, not their output):

    merge_direction.py --head H --base B --session-root R [--repo SPEC] [--pr N] [--cwd DIR]
        exit 0 allow, 11 refuse, 10 when an input cannot be read (repository-unreadable,
        default-branch-unreadable, unverifiable). The reason name appears in stdout or stderr.
        ``--pr N`` takes head and base from that pull request. ``GH_REPO`` in the check's own
        environment names the target repository when no ``--repo`` is given.

Everything is real except GitHub: real temp git repositories with a bare origin, a fake ``gh`` that is
a real executable first on PATH replaying canned JSON (see test_flat_worktree.py), the real hooks.

RED today: ``merge_direction.py`` does not exist, so every direct row exits with Python's "can't open
file" status; and the guard never runs a check, so every gate row that expects a MERGE DIRECTION block
is let through. Each therefore fails on an assertion.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_flat_worktree import (  # noqa: E402
    HOOKS_DIR, REPO_ROOT, SCRIPTS_DIR, REAL_GIT, Proc, Tools, add_worktree, clean_env, clone_of, commit, git,
    make_world, posix, real, rmtree_force, run, run_py, write_files,
)

import tempfile  # noqa: E402

MERGE_DIRECTION = SCRIPTS_DIR / "merge_direction.py"
LAUNCHER = HOOKS_DIR / "gate-launch.py"
CONCEPT_GATE = HOOKS_DIR / "concept-gate.py"
MARKER = "MERGE DIRECTION"

SLUG = "2026-10-07-acme-fixture"
CONTRACT = f".claude/concepts/{SLUG}.md"
PARENT = "feature/460-parent"
TASK = f"task/{SLUG}/t1-a"


def brief_text(*, id, branch, base=None, parent_issue=None, contract=CONTRACT) -> str:
    lines = ["---", f"id: {id}", f"title: Fixture {id}", "type: IMPROVEMENT", f"branch: {branch}"]
    if parent_issue is not None:
        lines.append(f"parent_issue: {parent_issue}")
    if base is not None:
        lines.append(f"base: {base}")
    lines += [f"contract: {contract}", "status: implementing", "---", "", f"# Brief {id}", ""]
    return "\n".join(lines)


def repo_answer(name_with_owner: str, default) -> dict:
    return {"nameWithOwner": name_with_owner, "defaultBranchRef": {"name": default} if default else None}


class MDWorld:
    """root, main, default, parent, task, task_wt, second (a second repository or None)."""


def build_md_world(root: Path, *, default: str = "master", with_second: bool = True) -> MDWorld:
    w = MDWorld()
    w.root, w.default, w.parent, w.task = Path(root), default, PARENT, TASK
    world = make_world(root, default=default, files={CONTRACT: "# contract\n"})
    w.world, w.main, w.origin = world, world.main, world.origin
    # the parent branch, with the parent's brief (id 460)
    git(w.main, "switch", "-q", "-c", PARENT)
    commit(w.main, {".claude/work-items/2026-10-07-460-parent.md":
                    brief_text(id=460, branch=PARENT, base=default)}, "parent brief")
    git(w.main, "push", "-q", "origin", PARENT)
    # the sub-task branch cut from the parent, with its brief (id 473, base = the parent)
    git(w.main, "switch", "-q", "-c", TASK)
    commit(w.main, {".claude/work-items/2026-10-07-473-t1.md":
                    brief_text(id=473, branch=TASK, base=PARENT, parent_issue=460)}, "task brief")
    git(w.main, "push", "-q", "origin", TASK)
    # a sub-task branch whose brief declares NO base, one with NO brief, and a plain branch
    git(w.main, "switch", "-q", "-c", f"task/{SLUG}/t8-nobase", PARENT)
    commit(w.main, {".claude/work-items/2026-10-07-478-t8.md":
                    brief_text(id=478, branch=f"task/{SLUG}/t8-nobase", parent_issue=460)}, "task brief without base")
    git(w.main, "branch", f"task/{SLUG}/t9-nobrief", PARENT)
    git(w.main, "branch", "docs/plain-notes", PARENT)
    git(w.main, "switch", "-q", default)
    # the sub-task's linked worktree: where a session would stand when it opens the pull request
    w.task_wt = add_worktree(w.main, w.main / ".claude" / "worktrees" / "20261007-task-t1", TASK)
    w.second = None
    if with_second:
        sec_root = w.root / "second_repository"
        sec_root.mkdir()
        sec = make_world(sec_root, default="trunk")
        git(sec.main, "branch", TASK)  # a sub-task-looking head with NO brief in that repository
        git(sec.main, "branch", "feature/x")
        w.second = sec
    return w


def gh_config(w: MDWorld, **extra) -> dict:
    """The default canned answers: the session repository is acme/app (default branch w.default),
    the second repository is other/second (default trunk), another HOST names acme/app too."""
    by_cwd = {str(w.main): repo_answer("acme/app", w.default)}
    by_name = {"other/second": repo_answer("other/second", "trunk"),
               "other.host/acme/app": repo_answer("acme/app", "master")}
    if w.second is not None:
        by_cwd[str(w.second.main)] = repo_answer("other/second", "trunk")
    cfg = {"repo_view": {"by_cwd": by_cwd, "by_name": by_name}, "open_prs": [], "sub_issues": {"460": []},
           "pr_view": {}}
    cfg.update(extra)
    return cfg


class MDCase(unittest.TestCase):
    """A world per class (read-only tests), a fake gh config per test."""

    default = "master"
    w: MDWorld
    tmp: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="mergedir_")))
        cls.w = build_md_world(cls.tmp, default=cls.default)
        cls.tools = Tools(cls.tmp)

    @classmethod
    def tearDownClass(cls) -> None:
        rmtree_force(cls.tmp)

    def setUp(self) -> None:
        self.tools.install_gh(gh_config(self.w))

    def env(self, extra: dict | None = None) -> dict:
        return clean_env(extra, tools=self.tools)

    def md(self, head, base, *extra, repo=None, pr=None, cwd=None, env_extra=None, session_root=None) -> Proc:
        cwd = cwd or self.w.task_wt
        args = ["--head", head, "--base", base, "--session-root", session_root or self.w.main, "--cwd", cwd]
        if repo is not None:
            args += [f"--repo={repo}"] if repo == "" or repo.startswith("-") else ["--repo", repo]
        if pr is not None:
            args += ["--pr", pr]
        return run_py(MERGE_DIRECTION, *args, *extra, cwd=cwd, env=self.env(env_extra))

    def assert_verdict(self, proc: Proc, rc: int, reason: str | None = None) -> None:
        self.assertEqual(proc.rc, rc, msg=f"expected exit {rc}: {proc.describe()}")
        if reason:
            self.assertIn(reason, proc.out + proc.err, msg=f"the verdict must name the reason {reason!r}: {proc.describe()}")


# ===========================================================================
# R-1 .. R-3: the plain topology rules
# ===========================================================================
class MergeDirectionRuleTests(MDCase):
    def test_sub_task_into_the_default_branch_while_its_base_names_the_parent_is_refused(self):
        self.assert_verdict(self.md(TASK, self.w.default), 11, "sub-task-targets-default")

    def test_sub_task_into_its_declared_base_is_allowed(self):
        self.assert_verdict(self.md(TASK, PARENT), 0)

    def test_sub_task_into_any_other_branch_is_refused(self):
        self.assert_verdict(self.md(TASK, "dev"), 11, "base-differs-from-declared")

    def test_sub_task_without_a_brief_is_refused_base_not_declared(self):
        self.assert_verdict(self.md(f"task/{SLUG}/t9-nobrief", PARENT), 11, "base-not-declared")

    def test_sub_task_whose_brief_declares_no_base_is_refused_base_not_declared(self):
        self.assert_verdict(self.md(f"task/{SLUG}/t8-nobase", PARENT), 11, "base-not-declared")

    def test_parent_into_default_with_an_open_sub_issue_is_refused(self):
        self.tools.set_gh(sub_issues={"460": [{"number": 473, "state": "OPEN"}]})
        self.assert_verdict(self.md(PARENT, self.w.default), 11, "parent-opened-early")

    def test_parent_into_default_with_an_open_pull_request_into_it_is_refused(self):
        self.tools.set_gh(open_prs=[{"number": 77, "headRefName": TASK, "baseRefName": PARENT, "url": "u"}])
        self.assert_verdict(self.md(PARENT, self.w.default), 11, "parent-opened-early")

    def test_parent_into_default_with_every_child_closed_and_nothing_open_is_allowed(self):
        # positive control for the two refusals above: the same call, nothing open
        self.tools.set_gh(sub_issues={"460": [{"number": 473, "state": "CLOSED"}]},
                          open_prs=[{"number": 5, "headRefName": "x", "baseRefName": "unrelated", "url": "u"}])
        self.assert_verdict(self.md(PARENT, self.w.default), 0)

    def test_a_plain_branch_is_allowed_into_the_default_branch(self):
        self.assert_verdict(self.md("docs/plain-notes", self.w.default), 0)

    def test_an_unreadable_github_is_exit_10_never_an_allow(self):
        self.tools.set_gh(fail_all=True)
        proc = self.md("docs/plain-notes", self.w.default)
        self.assertEqual(proc.rc, 10, msg=f"gh failing is exit 10 (the check could not verify): {proc.describe()}")

    def test_an_unreadable_child_query_is_unverifiable_exit_10(self):
        self.tools.set_gh(fail_commands=["issue view", "api", "pr list"])
        self.assert_verdict(self.md(PARENT, self.w.default), 10, "unverifiable")

    def test_pr_number_takes_head_and_base_from_the_pull_request(self):
        self.tools.set_gh(pr_view={"6": {"number": 6, "headRefName": TASK, "baseRefName": self.w.default,
                                         "state": "OPEN", "url": "u"},
                                   "7": {"number": 7, "headRefName": TASK, "baseRefName": PARENT,
                                         "state": "OPEN", "url": "u"}})
        proc = run_py(MERGE_DIRECTION, "--pr", "6", "--session-root", self.w.main, "--cwd", self.w.task_wt,
                      cwd=self.w.task_wt, env=self.env())
        self.assert_verdict(proc, 11, "sub-task-targets-default")
        proc = run_py(MERGE_DIRECTION, "--pr", "7", "--session-root", self.w.main, "--cwd", self.w.task_wt,
                      cwd=self.w.task_wt, env=self.env())
        self.assert_verdict(proc, 0)

    def test_the_check_writes_nothing(self):
        before = (git(self.w.main, "status", "--porcelain"), git(self.w.main, "rev-parse", "HEAD"),
                  git(self.w.task_wt, "rev-parse", "HEAD"), sorted(p.name for p in self.w.task_wt.iterdir()))
        allowed, refused = self.md(TASK, PARENT), self.md(TASK, self.w.default)
        self.assertEqual((allowed.rc, refused.rc), (0, 11),
                         msg=f"fixture sanity: the check must really have run, an allow and a refusal: "
                             f"{allowed.describe()} / {refused.describe()}")
        after = (git(self.w.main, "status", "--porcelain"), git(self.w.main, "rev-parse", "HEAD"),
                 git(self.w.task_wt, "rev-parse", "HEAD"), sorted(p.name for p in self.w.task_wt.iterdir()))
        self.assertEqual(after, before, msg="I-9: the check writes nothing")


# ===========================================================================
# R-0: cross-repository pull requests
# ===========================================================================
class CrossRepositoryTests(MDCase):
    def test_cross_repository_pr_from_acting_dir_to_its_default_is_allowed(self):
        # The acting directory is a checkout of ANOTHER repository (other/second, default trunk); no -R.
        # The head even looks like a sub-task: R-0 decides first, so R-1's "no brief" never applies.
        proc = self.md(TASK, "trunk", cwd=self.w.second.main)
        self.assert_verdict(proc, 0)

    def test_cross_repository_pr_named_by_the_repo_flag_to_its_default_is_allowed(self):
        self.assert_verdict(self.md(TASK, "trunk", repo="other/second"), 0)

    def test_cross_repository_pr_named_by_gh_repo_to_its_default_is_allowed(self):
        self.assert_verdict(self.md(TASK, "trunk", env_extra={"GH_REPO": "other/second"}), 0)

    def test_cross_repository_pr_to_another_branch_is_refused(self):
        self.assert_verdict(self.md(TASK, "dev", cwd=self.w.second.main), 11, "cross-repo-base-not-default")
        self.assert_verdict(self.md(TASK, "dev", repo="other/second"), 11, "cross-repo-base-not-default")
        self.assert_verdict(self.md(TASK, "dev", env_extra={"GH_REPO": "other/second"}), 11,
                            "cross-repo-base-not-default")

    def test_unreadable_acting_directory_identity_refuses_while_the_session_repository_reads(self):
        # t8 F9 [kill M14b]: the acting directory is a checkout of another repository whose `gh repo view`
        # fails, the session repository's succeeds, and there is no -R.
        self.assert_verdict(self.md(TASK, "trunk", cwd=self.w.second.main), 0)  # control: readable, so an allow
        view = gh_config(self.w)["repo_view"]
        view["by_cwd"][str(self.w.second.main)] = {"fail": True}
        self.tools.set_gh(repo_view=view)
        self.assert_verdict(self.md(TASK, "trunk", cwd=self.w.second.main), 10, "repository-unreadable")

    def test_the_other_repositorys_default_is_not_this_repositorys(self):
        # control: `trunk` is not the session repository's default, so the same call into the session
        # repository is judged by R-1 (the sub-task's base is the parent) and refused.
        self.assert_verdict(self.md(TASK, "trunk"), 11, "base-differs-from-declared")

    def test_a_repo_on_another_host_with_the_same_owner_and_name_is_another_repository(self):
        # R-0: `other.host/acme/app` is NOT acme/app on github.com, so it is cross-repository.
        self.assert_verdict(self.md(TASK, "master", repo="other.host/acme/app"), 0)
        self.assert_verdict(self.md(TASK, "dev", repo="other.host/acme/app"), 11, "cross-repo-base-not-default")


# ===========================================================================
# I-9: -R / GH_REPO spellings, parse_repo_spec
# ===========================================================================
class RepoSpellingTests(MDCase):
    def test_repo_flag_with_host_names_session_repository(self):
        self.assert_verdict(self.md(TASK, self.w.default, repo="github.com/acme/app"), 11, "sub-task-targets-default")

    def test_repo_flag_spellings_of_the_session_repository_are_the_same_repository_not_cross_repository(self):
        spellings = ["github.com/acme/app", "https://github.com/acme/app.git", "https://github.com/acme/app/",
                     "ACME/APP", "acme/app"]
        for spelling in spellings:
            with self.subTest(repo=spelling):
                self.assert_verdict(self.md(TASK, self.w.default, repo=spelling), 11, "sub-task-targets-default")

    def test_repo_equals_form_in_another_letter_case(self):
        proc = run_py(MERGE_DIRECTION, "--head", TASK, "--base", self.w.default, "--session-root", self.w.main,
                      "--cwd", self.w.task_wt, "--repo=ACME/APP", cwd=self.w.task_wt, env=self.env())
        self.assert_verdict(proc, 11, "sub-task-targets-default")

    def test_gh_repo_with_host_names_the_session_repository(self):
        proc = self.md(TASK, self.w.default, env_extra={"GH_REPO": "github.com/acme/app"})
        self.assert_verdict(proc, 11, "sub-task-targets-default")

    def test_repo_flag_unparseable_refuses(self):
        for bad in ("a/b/c/d", "", "$X", "has space/repo", "just-one-segment"):
            with self.subTest(repo=bad):
                self.assert_verdict(self.md(TASK, self.w.default, repo=bad), 10, "repository-unreadable")

    def test_gh_repo_unparseable_refuses(self):
        self.assert_verdict(self.md(TASK, self.w.default, env_extra={"GH_REPO": "a/b/c/d"}), 10,
                            "repository-unreadable")

    def test_parse_repo_spec_is_a_pure_text_parser_of_three_spellings(self):
        self.assertTrue(MERGE_DIRECTION.is_file(), msg="merge_direction.py must exist")
        spec = importlib.util.spec_from_file_location("merge_direction_under_test", MERGE_DIRECTION)
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path.remove(str(SCRIPTS_DIR))
        parse = getattr(mod, "parse_repo_spec", None)
        self.assertIsNotNone(parse, msg="merge_direction.py must define parse_repo_spec")

        def parts(text):
            r = parse(text)
            if isinstance(r, dict):
                r = tuple(r.get(k) for k in ("host", "owner", "name"))
            return tuple(str(x).lower() for x in r)
        self.assertEqual(parts("acme/app"), ("github.com", "acme", "app"), msg="an absent host means github.com")
        self.assertEqual(parts("other.host/acme/app"), ("other.host", "acme", "app"))
        self.assertEqual(parts("https://github.com/Acme/App.git"), ("github.com", "acme", "app"))
        self.assertEqual(parts("https://github.com/acme/app/"), ("github.com", "acme", "app"))
        for bad in ("", "a/b/c/d", "$X", "a b/c", "a"):
            try:
                result = parse(bad)
            except (ValueError, TypeError):
                continue
            self.assertIsNone(result, msg=f"{bad!r} is unparseable: raise ValueError or return None")


# ===========================================================================
# I-9: strict inputs
# ===========================================================================
class StrictInputTests(unittest.TestCase):
    """A world per test: these tests change origin/HEAD or the default branch."""

    def setUp(self) -> None:
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="mergedir_strict_")))
        self.addCleanup(rmtree_force, self.tmp)
        self.tools = Tools(self.tmp)

    def world(self, default: str, **gh_extra) -> MDWorld:
        w = build_md_world(self.tmp, default=default, with_second=True)
        self.tools.install_gh(gh_config(w, **gh_extra))
        return w

    def md(self, w, head, base, repo=None) -> Proc:
        args = ["--head", head, "--base", base, "--session-root", w.main, "--cwd", w.task_wt]
        if repo is not None:
            args += ["--repo", repo]
        return run_py(MERGE_DIRECTION, *args, cwd=w.task_wt, env=clean_env(tools=self.tools))

    def unset_origin_head(self, w) -> None:
        git(w.main, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")

    def assert_verdict(self, proc, rc, reason=None):
        self.assertEqual(proc.rc, rc, msg=f"expected exit {rc}: {proc.describe()}")
        if reason:
            self.assertIn(reason, proc.out + proc.err, msg=f"must name {reason!r}: {proc.describe()}")

    def test_parent_into_main_default_too_early_is_refused(self):
        # origin's default branch is `main` and origin/HEAD says so; an OPEN child exists.
        w = self.world("main", sub_issues={"460": [{"number": 473, "state": "OPEN"}]})
        self.assertEqual(git(w.main, "symbolic-ref", "refs/remotes/origin/HEAD"), "refs/remotes/origin/main",
                         msg="fixture sanity: origin/HEAD is set to main")
        self.assert_verdict(self.md(w, PARENT, "main"), 11, "parent-opened-early")

    def test_parent_into_main_with_nothing_open_is_allowed(self):
        w = self.world("main", sub_issues={"460": []})
        self.assert_verdict(self.md(w, PARENT, "main"), 0)

    def test_unreadable_origin_head_uses_gh_default(self):
        w = self.world("main", sub_issues={"460": [{"number": 473, "state": "OPEN"}]})
        self.unset_origin_head(w)
        proc = self.md(w, PARENT, "main")
        self.assert_verdict(proc, 11, "parent-opened-early")
        self.assertTrue(any(c["args"][:2] == ["repo", "view"] for c in self.tools.gh_calls()),
                        msg="with origin/HEAD unset the default branch must be READ from gh, not guessed as 'master'")

    def test_unreadable_default_branch_refuses_with_named_reason(self):
        w = self.world("main")
        self.unset_origin_head(w)
        by_cwd = {str(w.main): {"nameWithOwner": "acme/app", "defaultBranchRef": None}}
        self.tools.set_gh(repo_view={"by_cwd": by_cwd, "by_name": {}})
        self.assert_verdict(self.md(w, PARENT, "main"), 10, "default-branch-unreadable")

    def test_every_repo_view_failing_with_origin_head_unset_refuses_with_a_named_reason(self):
        w = self.world("main")
        self.unset_origin_head(w)
        self.tools.set_gh(fail_commands=["repo view"])
        proc = self.md(w, PARENT, "main")
        self.assertEqual(proc.rc, 10, msg=f"nothing readable is exit 10, never an allow: {proc.describe()}")
        text = proc.out + proc.err
        self.assertTrue("default-branch-unreadable" in text or "repository-unreadable" in text,
                        msg=f"the refusal must name why: {proc.describe()}")

    def test_unreadable_repository_identity_refuses(self):
        w = self.world("master")
        by_cwd = {str(w.main): {"fail": True}}  # the session repository cannot be read
        self.tools.set_gh(repo_view={"by_cwd": by_cwd, "by_name": {"other/second": repo_answer("other/second", "trunk")}})
        self.assert_verdict(self.md(w, TASK, "master"), 10, "repository-unreadable")
        self.assert_verdict(self.md(w, TASK, "master", repo="other/second"), 10, "repository-unreadable")

    def test_default_branch_is_still_master_with_origin_head_unset_for_old_callers(self):
        w = self.world("main")  # the real default is `main`
        code = ("import sys, json; sys.path.insert(0, %r); import pr_merged; "
                "print(json.dumps({'db': pr_merged.default_branch(), "
                "'none': getattr(pr_merged, 'default_branch_or_none', lambda: 'MISSING')()}))" % str(SCRIPTS_DIR))
        ctl = run([sys.executable, "-B", "-c", code], cwd=w.main, env=clean_env(tools=self.tools)).json()
        self.assertEqual(ctl, {"db": "main", "none": "main"},
                         msg="with origin/HEAD set both readers answer the real default branch")
        self.unset_origin_head(w)
        proc = run([sys.executable, "-B", "-c", code], cwd=w.main, env=clean_env(tools=self.tools))
        self.assertEqual(proc.json(), {"db": "master", "none": None},
                         msg="default_branch() keeps answering 'master' when origin/HEAD is unreadable, while the new "
                             f"default_branch_or_none() answers None: {proc.describe()}")


# ===========================================================================
# Through gate-launch.py: the guard runs the check for gh pr create / edit / merge
# ===========================================================================
def payload(tool: str, command: str, cwd) -> dict:
    return {"tool_name": tool, "tool_input": {"command": command}, "cwd": str(cwd)}


# The gate cases launch the default shell row, gate-launch.py concept-gate.py. The launcher accepts only a gate
# in its own folder; the plugin's hooks folder holds no bash-gate.py and no case pairs the launcher with it.
class GateCase(MDCase):
    hooks_dir = HOOKS_DIR

    def launch(self, tool: str, command: str, *, hooks_dir: Path | None = None, cwd=None) -> Proc:
        hooks = hooks_dir or self.hooks_dir
        data = json.dumps(payload(tool, command, cwd or self.w.task_wt)).encode("utf-8")
        return run([sys.executable, "-B", str(hooks / "gate-launch.py"), str(hooks / "concept-gate.py")],
                   cwd=self.w.task_wt, env=self.env(), stdin=data)

    def launch_all(self, rows: list) -> list:
        with ThreadPoolExecutor(max_workers=6) as pool:
            return list(pool.map(lambda r: self.launch(r[0], r[1], hooks_dir=r[2] if len(r) > 2 else None), rows))

    @staticmethod
    def blocked(proc: Proc) -> bool:
        return proc.rc == 2 and MARKER in proc.err

    def assert_blocked(self, proc: Proc, label: str, reason: str) -> None:
        """BLOCK means exit 2, the marker AND the reason word (t8 F7): a call refused for another reason, or a
        crash of the check, must not pass as the refusal under test."""
        self.assertTrue(self.blocked(proc),
                        msg=f"{label}: must BLOCK with exit 2 and '{MARKER}' on stderr: {proc.describe()}")
        self.assertIn(reason, proc.err, msg=f"{label}: the banner must name the reason {reason!r}: {proc.describe()}")
        self.assertNotIn("guard degraded", proc.err,
                         msg=f"{label}: the refusal must be the merge-direction check's own, not the launcher's "
                             f"degraded rule (the guard crashed and the rule blocked): {proc.describe()}")

    def assert_allowed(self, proc: Proc, label: str) -> None:
        self.assertEqual(proc.rc, 0, msg=f"{label}: must be let through (exit 0): {proc.describe()}")
        self.assertNotIn(MARKER, proc.err, msg=f"{label}: an allowed call carries no merge-direction banner")


class MergeDirectionGateTests(GateCase):
    def setUp(self) -> None:
        super().setUp()
        self.tools.set_gh(pr_view={
            "5": {"number": 5, "headRefName": TASK, "baseRefName": PARENT, "state": "OPEN", "url": "u"},
            "6": {"number": 6, "headRefName": TASK, "baseRefName": self.w.default, "state": "OPEN", "url": "u"},
            "7": {"number": 7, "headRefName": TASK, "baseRefName": PARENT, "state": "OPEN", "url": "u"}})

    #: (command, the reason word its banner must carry): every one targets the default branch for a sub-task.
    WRONG = [
        ("gh pr create --title t --body b", "sub-task-targets-default"),
        ("gh pr create --base master --title t --body b", "sub-task-targets-default"),
        ("gh pr create --base=master --title t --body b", "sub-task-targets-default"),
        ("gh pr create -B master --title t --body b", "sub-task-targets-default"),
        ("gh pr create -Bmaster --title t --body b", "sub-task-targets-default"),
        ("gh pr edit 5 -B master", "sub-task-targets-default"),
        ("gh pr edit 5 --base master", "sub-task-targets-default"),
        ("gh pr merge 6 --squash", "sub-task-targets-default"),
    ]
    RIGHT = "gh pr create --base feature/460-parent --title t --body b"

    def test_a_wrong_target_is_blocked_in_bash_and_powershell_and_a_correct_one_is_not(self):
        rows = [(tool, cmd, reason) for tool in ("Bash", "PowerShell") for cmd, reason in self.WRONG]
        results = self.launch_all([(tool, cmd) for tool, cmd, _reason in rows])
        for (tool, cmd, reason), proc in zip(rows, results):
            with self.subTest(tool=tool, command=cmd):
                self.assert_blocked(proc, f"{tool}: {cmd}", reason)
        # ALLOW counts only after a same-run BLOCK sibling: the correct create, in both tools.
        self.assertTrue(any(self.blocked(p) for p in results),
                        msg="no BLOCK row confirmed: an allow here would prove nothing")
        for tool in ("Bash", "PowerShell"):
            with self.subTest(tool=tool, command=self.RIGHT):
                self.assert_allowed(self.launch(tool, self.RIGHT), f"{tool}: {self.RIGHT}")

    def test_gh_pr_merge_of_a_pull_request_with_the_right_base_is_not_blocked(self):
        blocked = self.launch("Bash", "gh pr merge 6 --squash")
        self.assert_blocked(blocked, "gh pr merge 6 (base is the default branch)", "sub-task-targets-default")
        self.assert_allowed(self.launch("Bash", "gh pr merge 7 --squash"), "gh pr merge 7 (base is the parent)")

    def test_keyword_positions_in_bash(self):
        wrong = "gh pr create --base master --title t --body b"
        rows = [("Bash", c) for c in (
            f"if true; then {wrong}; fi",
            "{ " + wrong + "; }",
            f"for x in a; do {wrong}; done",
            f"! {wrong}",
            f"true && {wrong}",
        )]
        for (tool, cmd), proc in zip(rows, self.launch_all(rows)):
            with self.subTest(command=cmd):
                self.assert_blocked(proc, cmd, "sub-task-targets-default")

    def test_keyword_positions_in_powershell(self):
        wrong = "gh pr create --base master --title t --body b"
        rows = [("PowerShell", c) for c in (
            "if ($true) { " + wrong + " }",
            "& " + wrong,
            ".\\" + wrong,
        )]
        for (tool, cmd), proc in zip(rows, self.launch_all(rows)):
            with self.subTest(command=cmd):
                self.assert_blocked(proc, cmd, "sub-task-targets-default")

    def test_attached_base_spellings_on_create_are_read_like_the_separate_ones(self):
        # t8 F5 [kill M26, M27]: `--base=dev` and `-Bdev` must be READ as a base. The other repository's default
        # is `master` here, so an unread base (the default is filled in) would be let through as a default.
        view = gh_config(self.w)["repo_view"]
        view["by_name"]["other/second"] = repo_answer("other/second", "master")
        self.tools.set_gh(repo_view=view)
        blocks = [
            ("gh pr create --base=dev", "base-differs-from-declared"),
            ("gh pr create -Bdev", "base-differs-from-declared"),
            ("gh pr create --base=dev -R other/second", "cross-repo-base-not-default"),
            ("gh pr create -Bdev -R other/second", "cross-repo-base-not-default"),
        ]
        results = self.launch_all([("Bash", cmd) for cmd, _reason in blocks])
        for (cmd, reason), proc in zip(blocks, results):
            with self.subTest(command=cmd):
                self.assert_blocked(proc, cmd, reason)
        self.assertTrue(any(self.blocked(p) for p in results), msg="no BLOCK row confirmed: an allow proves nothing")
        for cmd in (f"gh pr create --base={PARENT}", f"gh pr create -B{PARENT}"):
            with self.subTest(command=cmd):
                self.assert_allowed(self.launch("Bash", cmd), cmd)

    def test_the_check_is_not_run_for_other_gh_commands(self):
        self.assert_blocked(self.launch("Bash", "gh pr create --base master --title t --body b"), "sibling block",
                            "sub-task-targets-default")
        self.assert_allowed(self.launch("Bash", "gh pr view 5"), "gh pr view is not a create, edit or merge")
        self.assert_allowed(self.launch("Bash", "gh pr list"), "gh pr list")
        self.assert_allowed(self.launch("Bash", "gh pr edit 5 --title new"), "gh pr edit without a base option")


class GhSpellingGateTests(GateCase):
    """Four gh spellings the guard misreads and must refuse (contract amendment notes, round 8). Each row is
    RED today: it is either let through, or blocked without the reason text the refusal must carry. The
    parent-branch folder has an OPEN child, so a parent opening into the default branch is refused anyway
    (the control row), which is why those rows can only be told apart by their reason text."""

    SEPARATELY = "write each option separately"
    TWICE = "given more than once"
    ACTION_FIRST = "write `gh pr <action>` first"

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.parent_wt = add_worktree(cls.w.main, cls.w.main / ".claude" / "worktrees" / "20261007-parent-460", PARENT)

    def setUp(self) -> None:
        super().setUp()
        self.tools.set_gh(
            sub_issues={"460": [{"number": 473, "state": "OPEN"}]},
            pr_view={"5": {"number": 5, "headRefName": PARENT, "baseRefName": self.w.default, "state": "OPEN", "url": "u"}})

    def cwd_of(self, key: str):
        return {"parent": self.parent_wt, "task": self.w.task_wt}[key]

    def run_rows(self, rows: list) -> None:
        """rows: (folder key, command, reason text). One BLOCK each, in Bash; the control row first proves the
        fixture refuses a parent opening early, so an allow below it counts."""
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda r: self.launch("Bash", r[1], cwd=self.cwd_of(r[0])), rows))
        for (key, cmd, text), proc in zip(rows, results):
            with self.subTest(folder=key, command=cmd):
                self.assert_blocked(proc, f"{key}: {cmd}", text)

    def control_refusal(self) -> None:
        self.assert_blocked(self.launch("Bash", "gh pr create --base master --title t", cwd=self.parent_wt),
                            "control: the parent opening into the default branch with an open child",
                            "parent-opened-early")

    def test_attached_equals_and_option_clusters_are_refused_with_the_write_separately_text(self):
        self.control_refusal()
        self.run_rows([
            ("parent", "gh pr create -B=master", self.SEPARATELY),
            ("parent", "gh pr create -dBmaster", self.SEPARATELY),
            ("parent", "gh pr create -dB master", self.SEPARATELY),
            ("task", f"gh pr create -H={TASK} --base master", self.SEPARATELY),
            ("task", "gh pr create -R other/second -dBdev", self.SEPARATELY),
            ("task", "gh pr edit 5 -B=master", self.SEPARATELY),
            ("task", "gh pr merge 5 -R=other/second", self.SEPARATELY),
            ("task", "gh pr merge 5 -dR other/second", self.SEPARATELY),
        ])

    def test_a_base_head_or_repository_given_twice_is_refused_with_the_more_than_once_text(self):
        self.control_refusal()
        self.run_rows([
            ("parent", "gh pr create --base dev -B master", self.TWICE),
            ("task", f"gh pr create --base {PARENT} -B master", self.TWICE),
            ("task", f"gh pr create -H {TASK} --head {PARENT}", self.TWICE),
            ("task", "gh pr edit 5 --base dev -B master", self.TWICE),
            ("task", "gh pr merge 5 --repo acme/app -R other/second", self.TWICE),
        ])

    def test_an_option_before_the_action_word_is_refused_with_the_action_first_text(self):
        self.control_refusal()
        self.run_rows([
            ("parent", "gh pr --base master create", self.ACTION_FIRST),
            ("parent", "gh --base master pr create", self.ACTION_FIRST),
            ("parent", "gh pr -R acme/app create", self.ACTION_FIRST),
            ("task", "gh -R other/second pr create --base dev", self.ACTION_FIRST),
            ("task", "gh pr --base master edit 5", self.ACTION_FIRST),
            ("task", "gh pr -d merge 5", self.ACTION_FIRST),
        ])

    def test_two_and_three_options_before_pr_are_refused_with_the_action_first_text(self):
        self.control_refusal()
        self.run_rows([
            ("parent", "gh --title t --base master pr create", self.ACTION_FIRST),
            ("parent", "gh --title t --body b --base master pr create", self.ACTION_FIRST),
            ("task", "gh -R other/second -B dev pr create", self.ACTION_FIRST),
            ("task", "gh -R other/second -d -B dev pr create", self.ACTION_FIRST),
            ("task", "gh --title t -B master pr edit 5", self.ACTION_FIRST),
            ("task", "gh -R acme/app --title t -B master pr edit 5", self.ACTION_FIRST),
            ("task", "gh -R other/second --subject s pr merge 5", self.ACTION_FIRST),
            ("task", "gh -R other/second --subject s --body b pr merge 5", self.ACTION_FIRST),
        ])

    def test_an_option_after_the_action_word_and_a_plain_delete_branch_stay_allowed(self):
        self.control_refusal()  # an allow below counts only after this confirmed refusal
        self.assert_allowed(self.launch("Bash", f"gh pr create -d -B {PARENT}", cwd=self.w.task_wt),
                            "gh pr create -d -B <parent> from the task folder")
        self.assert_allowed(self.launch("Bash", "gh pr view --json headRefName", cwd=self.parent_wt),
                            "an option after the action word stays allowed")
        self.tools.set_gh(pr_view={"5": {"number": 5, "headRefName": TASK, "baseRefName": PARENT, "state": "OPEN", "url": "u"}})
        self.assert_allowed(self.launch("Bash", "gh pr merge 5 -d", cwd=self.w.task_wt),
                            "gh pr merge 5 -d where pull request 5 is the task into its parent")


class MergeDirectionScriptMissingTests(GateCase):
    def _copy_layout(self, name: str, *, with_script: bool) -> Path:
        base = self.tmp / "copies" / name
        hooks, scripts = base / "hooks", base / "scripts"
        hooks.mkdir(parents=True)
        scripts.mkdir()
        for item in HOOKS_DIR.iterdir():
            if item.is_file():
                shutil.copy2(item, hooks / item.name)
        for item in SCRIPTS_DIR.glob("*.py"):
            if item.name == "merge_direction.py" and not with_script:
                continue
            shutil.copy2(item, scripts / item.name)
        return hooks

    def test_a_missing_merge_direction_script_blocks_even_a_correct_create(self):
        full = self._copy_layout("full", with_script=True)
        gone = self._copy_layout("renamed_away", with_script=False)
        wrong = "gh pr create --base master --title t --body b"
        right = "gh pr create --base feature/460-parent --title t --body b"
        # control: the copied layout works -- the wrong target is refused for its direction
        self.assert_blocked(self.launch("Bash", wrong, hooks_dir=full), "control: full copy, wrong target",
                            "sub-task-targets-default")
        self.assert_allowed(self.launch("Bash", right, hooks_dir=full), "control: full copy, correct target")
        # the check cannot run: a missing script is a refusal, never an allow
        self.assert_blocked(self.launch("Bash", right, hooks_dir=gone), "merge_direction.py renamed away", "is missing")
        self.assert_blocked(self.launch("PowerShell", right, hooks_dir=gone), "merge_direction.py renamed away (PowerShell)",
                            "is missing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
