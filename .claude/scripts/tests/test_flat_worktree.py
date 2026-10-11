#!/usr/bin/env python3
"""
test_flat_worktree.py -- RED suite for the flat worktree helper ``.claude/scripts/flat_worktree.py``.

Contract: .claude/concepts/2026-10-07-worktree-isolation-by-default.md (sub-task 3, issue #474)
Invariants pinned here: I-4 (no switch or checkout in an existing tree; the main checkout's HEAD,
index and files are byte-identical), I-5 (a flat path, names of at most 60 characters cut at a hyphen,
``-2`` to ``-9``, ``reused``, ``branch-in-main-checkout``, ``nested``), and the acceptance criteria
AC1 (``--describe`` names the tree kind) and AC7 (from inside a worktree the result still lands flat).

Run:
    py -3 .claude/scripts/tests/test_flat_worktree.py

THE COMMAND LINE THIS SUITE PINS (the contract names the flags' roles, not their spelling):

    flat_worktree.py --describe
        stdout: one JSON object with ``current_tree`` ("main-checkout" | "linked-worktree" | ...)
        and ``main_root`` (the main checkout's absolute path).
    flat_worktree.py --create --action A --slug S [--date YYYYMMDD]
                     ( --base BRANCH --branch NEW | --existing --branch B | --detached REF )
        stdout: one JSON object, the Flat worktree plan: ``main_root``, ``name``, ``path``, ``branch``
        (or null), ``source``, ``current_tree`` and ``outcome``. ``outcome`` is ``created``, ``reused``,
        or a refusal whose text holds one of ``nested``, ``branch-in-main-checkout``, ``path-taken``,
        ``fetch-failed``, ``git-failed``. The folder is ``<date>-<action>-<slug>`` under
        ``<main root>/.claude/worktrees/``; ``--date`` defaults to today.
    The helper is always run from the folder it is called in (the process folder).

This file also holds the SHARED SUPPORT the other two script suites import (real temp git
repositories with a bare origin, a fake ``gh`` and a logging ``git`` that are real executables on
PATH, the byte-identity snapshot, the clean child environment). Importing it defines no test class
of its own besides the ones below, and no collection-time import of a module that may not exist.

RED today: ``flat_worktree.py`` does not exist, so every launch exits with Python's "can't open file"
text and no JSON; every test therefore fails on an ASSERTION that names the missing plan.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent.parent
HOOKS_DIR = REPO_ROOT / ".claude" / "hooks"
FLAT_WORKTREE = SCRIPTS_DIR / "flat_worktree.py"

#: Captured at import time, before test_pr_merged.py's setUpModule replaces subprocess.run with its
#: guard that refuses ``git push`` and ``gh pr create``. Every fixture command here uses these two.
REAL_RUN = subprocess.run
REAL_GIT = shutil.which("git") or "git"

_STRIPPED_EXACT = ("CLAUDE_PROJECT_DIR", "GH_REPO", "GH_HOST", "CLAUDE_CONCEPT_GATE", "CLAUDE_BASH_GATE",
                   "CLAUDE_ACTIVE_CONTRACT")
DATE = "20261007"


# ---------------------------------------------------------------------------
# Environment, processes
# ---------------------------------------------------------------------------
def clean_env(extra: dict | None = None, *, tools: "Tools | None" = None) -> dict:
    """The one builder of every child environment: no CLAUDE_PROJECT_DIR, GH_REPO, GH_HOST, no GIT_*
    variable and no off switch. ``tools`` puts its fake-executable folder FIRST on PATH."""
    env = {k: v for k, v in os.environ.items() if k not in _STRIPPED_EXACT and not k.startswith("GIT_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if tools is not None:
        env["PATH"] = tools.bin_dir_text + os.pathsep + env.get("PATH", "")
    if extra:
        env.update(extra)
    return env


class Proc:
    def __init__(self, rc: int, out: str, err: str):
        self.rc, self.out, self.err = rc, out, err

    def describe(self) -> str:
        return f"exit={self.rc} stdout={self.out.strip()[:500]!r} stderr={self.err.strip()[:500]!r}"

    def json(self):
        try:
            return json.loads(self.out)
        except (ValueError, TypeError):
            return None


def run(cmd: list, *, cwd, env: dict | None = None, stdin: bytes | None = None, timeout: int = 180) -> Proc:
    p = REAL_RUN(cmd, cwd=str(cwd), env=env if env is not None else clean_env(), input=stdin,
                 capture_output=True, timeout=timeout)
    return Proc(p.returncode, p.stdout.decode("utf-8", errors="replace"), p.stderr.decode("utf-8", errors="replace"))


def run_py(script, *args, cwd, env: dict | None = None, stdin: bytes | None = None, timeout: int = 180) -> Proc:
    return run([sys.executable, "-B", str(script), *[str(a) for a in args]], cwd=cwd, env=env, stdin=stdin,
               timeout=timeout)


def git(repo, *args: str, check: bool = True, env: dict | None = None) -> str:
    """Real git, never through PATH, with a fixed identity. Returns stripped stdout."""
    p = run([REAL_GIT, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
             "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args], cwd=repo, env=env)
    if check and p.rc != 0:
        raise RuntimeError(f"fixture git {' '.join(args)} failed in {repo}: {p.err.strip()}")
    return p.out.strip() if check else p.out.strip() + ("\n" + p.err.strip() if p.err.strip() else "")


def git_rc(repo, *args: str) -> Proc:
    return run([REAL_GIT, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
                "-c", "commit.gpgsign=false", *args], cwd=repo)


def posix(path) -> str:
    return str(path).replace("\\", "/")


def real(path) -> str:
    return os.path.normcase(os.path.realpath(str(path)))


def rmtree_force(path: Path) -> None:
    def _onerror(func, p, exc):
        try:
            os.chmod(p, 0o700)
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, onerror=_onerror)


# ---------------------------------------------------------------------------
# Real executables on PATH: a fake gh (config driven), a logging git, a fake git that echoes.
# ---------------------------------------------------------------------------
FAKE_GH_CODE = r'''
import json, os, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(sys.argv[0]))
args = sys.argv[1:]
cfg = json.load(open(os.path.join(HERE, "gh_config.json"), encoding="utf-8"))
with open(os.path.join(HERE, "gh_calls.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"args": args, "cwd": os.getcwd(), "gh_repo": os.environ.get("GH_REPO"),
                         "gh_host": os.environ.get("GH_HOST")}) + "\n")

def out(obj, code=0):
    print(json.dumps(obj)); sys.exit(code)

def fail(msg="fake gh: failing on purpose"):
    sys.stderr.write(msg + "\n"); sys.exit(1)

def opt(*names):
    for i, a in enumerate(args):
        for n in names:
            if a == n and i + 1 < len(args):
                return args[i + 1]
            if a.startswith(n + "=") and n.startswith("--"):
                return a.split("=", 1)[1]
    return None

def norm(p):
    return os.path.normcase(os.path.realpath(p))

if cfg.get("fail_all"):
    fail()
for prefix in cfg.get("fail_commands", []):
    if " ".join(args).startswith(prefix):
        fail("fake gh: %s fails on purpose" % prefix)
sub = args[:2]
if sub == ["repo", "view"]:
    rv = cfg.get("repo_view", {})
    positional, skip = [], False
    for a in args[2:]:
        if skip:
            skip = False
        elif a == "--json":
            skip = True
        elif not a.startswith("-"):
            positional.append(a)
    name = positional[0] if positional else os.environ.get("GH_REPO")
    answer = None
    if name:
        key = name.lower()
        if key.startswith("github.com/"):
            key = key[len("github.com/"):]
        answer = rv.get("by_name", {}).get(key)
    else:
        here, best = norm(os.getcwd()), -1
        for path, ans in rv.get("by_cwd", {}).items():
            p = norm(path)
            if (here == p or here.startswith(p + os.sep)) and len(p) > best:
                answer, best = ans, len(p)
        if answer is None:
            answer = rv.get("default")
    if answer is None or answer.get("fail"):
        fail("fake gh: repo view unreadable")
    out(answer)
if sub == ["pr", "list"]:
    base, head = opt("--base", "-B"), opt("--head", "-H")
    out([p for p in cfg.get("open_prs", [])
         if (not base or p.get("baseRefName") == base) and (not head or p.get("headRefName") == head)])
if sub == ["pr", "view"]:
    number = next((a for a in args[2:] if re.fullmatch(r"\d+", a)), None)
    pr = cfg.get("pr_view", {}).get(str(number))
    if pr is None:
        fail("fake gh: no such pull request")
    out(pr)
if sub == ["issue", "view"]:
    number = next((a for a in args[2:] if re.fullmatch(r"\d+", a)), None)
    fields = opt("--json") or ""
    if "subIssues" in fields:
        out({"subIssues": cfg.get("sub_issues", {}).get(str(number), [])})
    if "state" in fields:
        out({"state": cfg.get("issue_state", {}).get(str(number), "OPEN")})
    fail()
if args and args[0] == "api":
    m = re.search(r"issues/(\d+)/sub_issues", " ".join(args))
    if m:
        print(json.dumps([{"number": s["number"], "state": s["state"]}
                          for s in cfg.get("sub_issues", {}).get(m.group(1), [])]))
        sys.exit(0)
    fail()
if sub == ["issue", "develop"]:
    if cfg.get("develop_fail"):
        fail()
    name, base = opt("--name", "-n"), opt("--base", "-b")
    r = subprocess.run([cfg["real_git"], "push", "origin", "refs/remotes/origin/%s:refs/heads/%s" % (base, name)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        fail(r.stderr)
    print("https://github.com/acme/app/tree/" + name)
    sys.exit(0)
fail("fake gh: unexpected command %r" % (args,))
'''

FAKE_GIT_LOGGER_CODE = r'''
import json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(sys.argv[0]))
real = open(os.path.join(HERE, "real_git.txt"), encoding="utf-8").read().strip()
with open(os.path.join(HERE, "git_calls.jsonl"), "a", encoding="utf-8") as fh:
    fh.write(json.dumps({"args": sys.argv[1:], "cwd": os.getcwd()}) + "\n")
sys.exit(subprocess.call([real] + sys.argv[1:]))
'''

FAKE_GIT_ECHO_CODE = r'''
import json, os, sys
print(json.dumps({"cwd": os.getcwd(), "gh_repo": os.environ.get("GH_REPO"), "args": sys.argv[1:]}))
'''


def write_exe(directory: Path, name: str, code: str) -> Path:
    """A REAL executable called ``name`` (``name.exe`` on Windows) that runs ``code`` with this Python.

    On Windows ``subprocess`` finds only ``.exe`` files, so the launcher distlib ships with pip is
    used: launcher bytes + a shebang line + a zip holding ``__main__.py``, the way pip writes its own
    ``pip.exe``. Elsewhere it is a shebang script.
    """
    directory.mkdir(parents=True, exist_ok=True)
    body = code.encode("utf-8")
    if os.name == "nt":
        from pip._vendor.distlib.scripts import ScriptMaker  # type: ignore
        launcher = ScriptMaker(None, str(directory))._get_launcher("t")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("__main__.py", body)
        target = directory / (name + ".exe")
        target.write_bytes(launcher + b"#!" + sys.executable.encode("utf-8") + b"\r\n" + buf.getvalue())
    else:
        target = directory / name
        target.write_bytes(b"#!" + sys.executable.encode("utf-8") + b"\n" + body)
        target.chmod(0o755)
    return target


class Tools:
    """A folder of fake executables, placed FIRST on a child's PATH by ``clean_env(tools=...)``."""

    def __init__(self, root: Path):
        self.bin = Path(root) / "fakebin"
        self.bin.mkdir(parents=True, exist_ok=True)
        self.bin_dir_text = str(self.bin)

    # -- gh -------------------------------------------------------------------------------------
    def install_gh(self, config: dict | None = None) -> None:
        write_exe(self.bin, "gh", FAKE_GH_CODE)
        cfg = {"real_git": REAL_GIT}
        cfg.update(config or {})
        (self.bin / "gh_config.json").write_text(json.dumps(cfg), encoding="utf-8")

    def gh_config(self) -> dict:
        return json.loads((self.bin / "gh_config.json").read_text(encoding="utf-8"))

    def set_gh(self, **changes) -> None:
        cfg = self.gh_config()
        cfg.update(changes)
        (self.bin / "gh_config.json").write_text(json.dumps(cfg), encoding="utf-8")

    def gh_calls(self) -> list:
        f = self.bin / "gh_calls.jsonl"
        return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()] if f.exists() else []

    # -- a git that logs every argument vector and then runs the real git ---------------------------
    def install_git_logger(self) -> None:
        write_exe(self.bin, "git", FAKE_GIT_LOGGER_CODE)
        (self.bin / "real_git.txt").write_text(REAL_GIT, encoding="utf-8")

    def git_calls(self) -> list:
        f = self.bin / "git_calls.jsonl"
        return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()] if f.exists() else []

    def clear_git_calls(self) -> None:
        (self.bin / "git_calls.jsonl").unlink(missing_ok=True)

    # -- a git that only prints its folder and GH_REPO ----------------------------------------------
    def install_git_echo(self) -> None:
        write_exe(self.bin, "git", FAKE_GIT_ECHO_CODE)


def tree_switching_calls(calls: list) -> list:
    """Logged git argument vectors that hold ``switch`` or ``checkout`` as a word of their own."""
    return [c["args"] for c in calls if {"switch", "checkout"} & set(c["args"])]


# ---------------------------------------------------------------------------
# Real repositories: a bare origin and the main checkout cloned from it.
# ---------------------------------------------------------------------------
def write_files(repo, files: dict) -> None:
    for rel, text in files.items():
        p = Path(repo) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")


def commit(repo, files: dict, message: str = "fixture") -> str:
    write_files(repo, files)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


class World(SimpleNamespace):
    """root, origin (bare), main (the main checkout), default (branch name)."""


def make_world(root: Path, *, default: str = "master", files: dict | None = None) -> World:
    root = Path(root)
    origin, main = root / "origin.git", root / "main_checkout"
    origin.mkdir(parents=True)
    git(origin, "init", "-q", "--bare", "-b", default)
    main.mkdir()
    git(main, "init", "-q", "-b", default)
    base_files = {"README.md": "fixture\n", "src/keep.txt": "x\n"}
    conv = REPO_ROOT / ".claude" / "work-item-conventions.json"
    if conv.is_file():
        base_files[".claude/work-item-conventions.json"] = conv.read_text(encoding="utf-8")
    base_files.update(files or {})
    commit(main, base_files, "initial")
    git(main, "remote", "add", "origin", str(origin))
    git(main, "push", "-q", "-u", "origin", default)
    git(main, "symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/origin/{default}")
    return World(root=root, origin=origin, main=main, default=default)


def clone_of(world: World, name: str = "other_clone") -> Path:
    dest = world.root / name
    git(world.root, "clone", "-q", str(world.origin), str(dest))
    return dest


def add_worktree(repo, path: Path, *args: str) -> Path:
    """``git worktree add`` through the real git (fixture only; the code under test never uses this)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    git(repo, "worktree", "add", "-q", *_wt_args(path, args))
    return path


def _wt_args(path: Path, args: tuple) -> list:
    # args like ("-b", "name", "origin/master") or ("--detach", "ref") or ("branch",): path goes first
    # after the options, before the commit-ish.
    opts, rest = [], list(args)
    while rest and rest[0] in ("-b", "--detach", "-B"):
        flag = rest.pop(0)
        opts.append(flag)
        if flag in ("-b", "-B"):
            opts.append(rest.pop(0))
    return [*opts, str(path), *rest]


def snapshot(main) -> dict:
    """What I-4 calls byte-identical: HEAD, the index, and every working file outside .git and
    .claude/worktrees (content hashes, so a rewritten file with the same text is the same)."""
    main = Path(main)
    gd = main / ".git"
    snap = {"HEAD": (gd / "HEAD").read_bytes(),
            "HEAD_sha": git(main, "rev-parse", "HEAD"),
            "index": (gd / "index").read_bytes() if (gd / "index").exists() else b""}
    files = {}
    for p in sorted(main.rglob("*")):
        rel = p.relative_to(main).as_posix()
        if rel == ".git" or rel.startswith(".git/") or rel == ".claude/worktrees" or rel.startswith(".claude/worktrees/"):
            continue
        if p.is_file():
            files[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    snap["files"] = files
    return snap


def worktree_paths(repo) -> list:
    out = git(repo, "worktree", "list", "--porcelain")
    return [real(l[len("worktree "):]) for l in out.splitlines() if l.startswith("worktree ")]


class TempWorldCase(unittest.TestCase):
    """A fresh temp folder (outside any .claude path), a world in it, fake tools in it."""

    world_files: dict | None = None

    def setUp(self) -> None:
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="flatwt_")))
        self.addCleanup(rmtree_force, self.tmp)
        self.world = make_world(self.tmp, files=self.world_files)
        self.main = self.world.main
        self.tools = Tools(self.tmp)

    def env(self, extra: dict | None = None) -> dict:
        return clean_env(extra, tools=self.tools)


# ===========================================================================
# The tests
# ===========================================================================
class HelperEnvironmentControlTests(unittest.TestCase):
    """Control: the child environment really is stripped, and the strip can be seen working."""

    def test_clean_env_removes_project_dir_gh_vars_and_every_git_variable(self):
        poisoned = {"CLAUDE_PROJECT_DIR": "x", "GH_REPO": "o/r", "GH_HOST": "h", "GIT_DIR": "d", "GIT_WORK_TREE": "w",
                    "GIT_INDEX_FILE": "i"}
        saved = {k: os.environ.get(k) for k in poisoned}
        try:
            os.environ.update(poisoned)
            env = clean_env()
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        for name in poisoned:
            self.assertNotIn(name, env, msg=f"{name} must never reach a child process under test")
        self.assertIn("PATH", env, msg="the strip must keep everything else, or no child could start")

    def test_the_control_can_fail_a_variable_that_is_not_stripped_is_seen(self):
        saved = os.environ.get("HARMLESS_FIXTURE_VARIABLE")
        try:
            os.environ["HARMLESS_FIXTURE_VARIABLE"] = "kept"
            env = clean_env()
        finally:
            if saved is None:
                os.environ.pop("HARMLESS_FIXTURE_VARIABLE", None)
            else:
                os.environ["HARMLESS_FIXTURE_VARIABLE"] = saved
        self.assertEqual(env.get("HARMLESS_FIXTURE_VARIABLE"), "kept",
                         msg="positive control: an unrelated variable survives, so the previous test is not vacuous")


class FlatWorktreeCase(TempWorldCase):
    def flat(self, *args, cwd=None, tools_logging: bool = False) -> tuple:
        """Run the helper; return (Proc, plan dict or None)."""
        if tools_logging:
            self.tools.install_git_logger()
        proc = run_py(FLAT_WORKTREE, *args, cwd=cwd or self.main, env=self.env())
        return proc, proc.json()

    def create(self, *args, slug="demo", action="task", date=DATE, cwd=None, tools_logging=False) -> tuple:
        return self.flat("--create", "--action", action, "--slug", slug, "--date", date, *args, cwd=cwd,
                         tools_logging=tools_logging)

    def need_plan(self, proc: Proc, plan, what: str) -> dict:
        self.assertIsInstance(plan, dict, msg=f"{what}: flat_worktree.py must print one JSON plan object, got "
                                              f"{proc.describe()}")
        return plan

    def worktrees_dir(self) -> Path:
        return self.main / ".claude" / "worktrees"

    def expected_name(self, slug="demo", action="task", date=DATE) -> str:
        full = f"{date}-{action}-{slug}"
        return full if len(full) <= 60 else full[:60].rsplit("-", 1)[0]

    def branch_of(self, path) -> str:
        return git(path, "rev-parse", "--abbrev-ref", "HEAD")


class DescribeTests(FlatWorktreeCase):
    def test_describe_reports_main_checkout_in_the_main_checkout(self):
        proc, plan = self.flat("--describe", cwd=self.main)
        plan = self.need_plan(proc, plan, "--describe in the main checkout")
        self.assertEqual(plan.get("current_tree"), "main-checkout",
                         msg="AC1: /task refuses 'current checkout' on this answer, so the main checkout must "
                             f"describe itself as main-checkout, got {plan}")

    def test_describe_reports_linked_worktree_in_a_worktree(self):
        wt = add_worktree(self.main, self.worktrees_dir() / "20261007-x-existing", "-b", "side", "HEAD")
        proc, plan = self.flat("--describe", cwd=wt)
        plan = self.need_plan(proc, plan, "--describe in a linked worktree")
        self.assertEqual(plan.get("current_tree"), "linked-worktree",
                         msg=f"AC1: a linked worktree must describe itself as linked-worktree, got {plan}")
        self.assertEqual(real(plan.get("main_root", "")), real(self.main),
                         msg="from inside a worktree the main root must still be the MAIN checkout, never the worktree")


class CreateTests(FlatWorktreeCase):
    def test_new_from_base_fetches_the_base_and_cuts_a_new_branch_in_a_flat_worktree(self):
        other = clone_of(self.world)
        newer = commit(other, {"src/newer.txt": "n\n"}, "origin moves on")
        git(other, "push", "-q", "origin", self.world.default)
        proc, plan = self.create("--base", self.world.default, "--branch", "task/demo/t1-a")
        plan = self.need_plan(proc, plan, "new-from-base")
        self.assertEqual(plan.get("outcome"), "created", msg=f"expected created, got {plan} / {proc.describe()}")
        path = Path(plan.get("path", ""))
        self.assertEqual(real(path), real(self.worktrees_dir() / self.expected_name()),
                         msg="the folder must be <main>/.claude/worktrees/<date>-<action>-<slug>")
        self.assertTrue((path / ".git").exists(), msg="the folder must be a real linked worktree")
        self.assertEqual(self.branch_of(path), "task/demo/t1-a", msg="the new branch must be checked out there")
        self.assertEqual(git(path, "rev-parse", "HEAD"), newer,
                         msg="new-from-base must FETCH the base first: the worktree starts at origin's current tip, "
                             "not at the stale local copy")
        self.assertIn("new-from-base", json.dumps(plan.get("source")), msg="the plan must say how the tree was cut")

    def test_existing_branch_is_checked_out_in_the_new_worktree(self):
        git(self.main, "branch", "feature/existing")
        proc, plan = self.create("--existing", "--branch", "feature/existing")
        plan = self.need_plan(proc, plan, "existing-branch")
        self.assertEqual(plan.get("outcome"), "created", msg=f"got {plan} / {proc.describe()}")
        self.assertEqual(self.branch_of(plan.get("path", "")), "feature/existing")
        self.assertIn("existing-branch", json.dumps(plan.get("source")))

    def test_existing_branch_known_only_on_origin_is_checked_out_too(self):
        other = clone_of(self.world)
        git(other, "switch", "-q", "-c", "feature/remote-only")
        commit(other, {"src/r.txt": "r\n"}, "remote only")
        git(other, "push", "-q", "origin", "feature/remote-only")
        proc, plan = self.create("--existing", "--branch", "feature/remote-only")
        plan = self.need_plan(proc, plan, "existing-branch, remote only")
        self.assertEqual(plan.get("outcome"), "created", msg=f"got {plan} / {proc.describe()}")
        self.assertEqual(self.branch_of(plan.get("path", "")), "feature/remote-only",
                         msg="a branch that only origin has must be fetched and checked out")

    def test_detached_at_a_commit_leaves_the_head_detached_at_that_commit(self):
        sha = git(self.main, "rev-parse", "HEAD")
        commit(self.main, {"src/more.txt": "m\n"}, "later")
        proc, plan = self.create("--detached", sha)
        plan = self.need_plan(proc, plan, "detached-at a commit")
        self.assertEqual(plan.get("outcome"), "created", msg=f"got {plan} / {proc.describe()}")
        path = Path(plan.get("path", ""))
        self.assertEqual(self.branch_of(path), "HEAD", msg="detached-at must leave a detached HEAD (no branch)")
        self.assertEqual(git(path, "rev-parse", "HEAD"), sha)
        self.assertIsNone(plan.get("branch"), msg="a detached plan has no branch")
        self.assertIn("detached-at", json.dumps(plan.get("source")))

    def test_detached_at_origin_default_lands_on_the_fetched_tip(self):
        tip = git(self.main, "rev-parse", f"origin/{self.world.default}")
        proc, plan = self.create("--detached", f"origin/{self.world.default}")
        plan = self.need_plan(proc, plan, "detached-at origin/<default>")
        self.assertEqual(git(plan.get("path", ""), "rev-parse", "HEAD"), tip)

    def test_a_branch_registered_to_a_worktree_is_reused_there_not_duplicated(self):
        proc, first = self.create("--base", self.world.default, "--branch", "task/demo/t1-a")
        first = self.need_plan(proc, first, "first create")
        self.assertEqual(first.get("outcome"), "created", msg=f"{first} / {proc.describe()}")
        before = worktree_paths(self.main)
        proc, second = self.create("--existing", "--branch", "task/demo/t1-a", slug="other-slug")
        second = self.need_plan(proc, second, "second call for the same branch")
        self.assertEqual(second.get("outcome"), "reused",
                         msg=f"I-5: a branch registered to a worktree is reused there, got {second}")
        self.assertEqual(real(second.get("path", "")), real(first.get("path", "")),
                         msg="reuse must answer the EXISTING worktree's path, whatever name was asked for")
        self.assertEqual(worktree_paths(self.main), before, msg="reuse must create no further worktree")


class RefusalTests(FlatWorktreeCase):
    def test_a_name_that_climbs_or_nests_is_refused_nested_and_creates_nothing(self):
        for slug in ("inner/deep", "../escape", "back\\slash"):
            with self.subTest(slug=slug):
                before = worktree_paths(self.main)
                proc, plan = self.create("--base", self.world.default, "--branch", "task/demo/t9", slug=slug)
                plan = self.need_plan(proc, plan, f"slug {slug!r}")
                self.assertIn("nested", str(plan.get("outcome")),
                              msg=f"I-5: a planned path whose parent is not exactly <main>/.claude/worktrees is "
                                  f"nested, got {plan}")
                self.assertEqual(worktree_paths(self.main), before, msg="a refusal must create nothing")
                self.assertFalse(Path(self.tmp, "escape").exists(), msg="nothing may be written outside the folder")

    def test_a_branch_held_by_the_main_checkout_is_refused_but_detached_at_it_is_planned(self):
        held = self.world.default  # the main checkout is on it
        before = worktree_paths(self.main)
        proc, plan = self.create("--existing", "--branch", held)
        plan = self.need_plan(proc, plan, "branch held by the main checkout")
        self.assertIn("branch-in-main-checkout", str(plan.get("outcome")),
                      msg=f"I-5: a branch the main checkout holds must be refused, got {plan}")
        self.assertEqual(worktree_paths(self.main), before)
        proc, detached = self.create("--detached", held)
        detached = self.need_plan(proc, detached, "detached-at the held branch")
        self.assertEqual(detached.get("outcome"), "created",
                         msg=f"I-5: only detached-at may then plan a tree, got {detached} / {proc.describe()}")
        self.assertEqual(self.branch_of(detached.get("path", "")), "HEAD")

    def test_taken_names_get_suffixes_2_to_9_then_path_taken(self):
        base_name = self.expected_name()
        seen = []
        for i in range(1, 10):
            proc, plan = self.create("--base", self.world.default, "--branch", f"task/demo/t{i}")
            plan = self.need_plan(proc, plan, f"create number {i}")
            self.assertEqual(plan.get("outcome"), "created", msg=f"number {i}: {plan} / {proc.describe()}")
            seen.append(Path(plan.get("path", "")).name)
        self.assertEqual(seen, [base_name] + [f"{base_name}-{n}" for n in range(2, 10)],
                         msg="I-5: a taken name gets -2 to -9 in order")
        proc, tenth = self.create("--base", self.world.default, "--branch", "task/demo/t10")
        tenth = self.need_plan(proc, tenth, "the tenth create")
        self.assertIn("path-taken", str(tenth.get("outcome")),
                      msg=f"I-5: after -9 the answer is path-taken, got {tenth}")
        self.assertEqual(len(worktree_paths(self.main)), 1 + 9, msg="the refusal must create nothing")

    def test_a_plain_folder_of_the_same_name_counts_as_taken(self):
        (self.worktrees_dir() / self.expected_name()).mkdir(parents=True)
        proc, plan = self.create("--base", self.world.default, "--branch", "task/demo/t1")
        plan = self.need_plan(proc, plan, "folder already there")
        self.assertEqual(plan.get("outcome"), "created", msg=f"{plan} / {proc.describe()}")
        self.assertEqual(Path(plan.get("path", "")).name, self.expected_name() + "-2",
                         msg="a leftover folder is a taken name, whether or not it is a worktree")

    def test_an_unreachable_origin_is_refused_fetch_failed_and_creates_nothing(self):
        git(self.main, "remote", "set-url", "origin", str(self.tmp / "no-such-origin.git"))
        before = worktree_paths(self.main)
        proc, plan = self.create("--base", self.world.default, "--branch", "task/demo/t1")
        plan = self.need_plan(proc, plan, "unreachable origin")
        self.assertIn("fetch-failed", str(plan.get("outcome")), msg=f"got {plan}")
        self.assertEqual(worktree_paths(self.main), before)


class NameLengthTests(FlatWorktreeCase):
    HEAD4 = "abcdefgh-abcdefgh-abcdefgh-abcdefgh"  # 35 characters; "20261007-task-" in front is 14

    def test_names_of_59_60_and_61_characters(self):
        cases = {59: self.HEAD4 + "-abcdefghi", 60: self.HEAD4 + "-abcdefghij", 61: self.HEAD4 + "-abcdefghijk"}
        for length, slug in cases.items():
            full = f"{DATE}-task-{slug}"
            self.assertEqual(len(full), length, msg="fixture sanity: the slug builds a name of the stated length")
        for length, slug in cases.items():
            with self.subTest(length=length):
                proc, plan = self.create("--base", self.world.default, "--branch", f"task/len/{length}", slug=slug)
                plan = self.need_plan(proc, plan, f"{length} characters")
                self.assertEqual(plan.get("outcome"), "created", msg=f"{plan} / {proc.describe()}")
                name = Path(plan.get("path", "")).name
                full = f"{DATE}-task-{slug}"
                if length <= 60:
                    self.assertEqual(name, full, msg=f"{length} characters fit, so the name stays whole")
                else:
                    self.assertEqual(name, f"{DATE}-task-{self.HEAD4}",
                                     msg="61 characters: the name is cut at a hyphen to at most 60, never mid-word")
                self.assertLessEqual(len(name), 60)


class FlatFromInsideAWorktreeTests(FlatWorktreeCase):
    def test_from_inside_a_worktree_the_new_one_still_lands_flat(self):
        inner = add_worktree(self.main, self.worktrees_dir() / "20261007-start-here", "-b", "start-here", "HEAD")
        proc, plan = self.create("--base", self.world.default, "--branch", "task/demo/t1", cwd=inner)
        plan = self.need_plan(proc, plan, "created from inside a worktree")
        self.assertEqual(plan.get("outcome"), "created", msg=f"{plan} / {proc.describe()}")
        path = Path(plan.get("path", ""))
        self.assertEqual(real(path.parent), real(self.worktrees_dir()),
                         msg="AC7: the parent folder must be <main>/.claude/worktrees, not a folder inside the "
                             "worktree the helper was run from")
        self.assertEqual(posix(real(path)).count("/.claude/worktrees/"), 1,
                         msg="AC7: the path holds exactly ONE Worktree segment (a nested one broke SqlClient's SNI.dll)")
        self.assertFalse((inner / ".claude" / "worktrees").exists(), msg="nothing may be created inside the starting worktree")
        self.assertEqual(plan.get("current_tree"), "linked-worktree")


class MainCheckoutUntouchedTests(FlatWorktreeCase):
    """I-4: the helper never runs switch or checkout in an existing tree, and the main checkout's
    HEAD, index and working files are byte-identical before and after any helper call."""

    def _dirty_main(self) -> None:
        (self.main / "src" / "uncommitted.txt").write_text("dirty\n", encoding="utf-8")
        (self.main / "README.md").write_text("fixture changed but not staged\n", encoding="utf-8")

    def test_every_outcome_leaves_head_index_and_files_byte_identical(self):
        self._dirty_main()
        git(self.main, "branch", "feature/existing")
        before = snapshot(self.main)
        self.tools.install_git_logger()
        steps = [
            ("describe", ("--describe",)),
            ("new-from-base", ("--create", "--action", "task", "--slug", "a", "--date", DATE, "--base",
                               self.world.default, "--branch", "task/a/t1")),
            ("reuse", ("--create", "--action", "task", "--slug", "a", "--date", DATE, "--existing", "--branch",
                       "task/a/t1")),
            ("existing-branch", ("--create", "--action", "task", "--slug", "b", "--date", DATE, "--existing",
                                 "--branch", "feature/existing")),
            ("detached-at", ("--create", "--action", "task", "--slug", "c", "--date", DATE, "--detached",
                             self.world.default)),
            ("refused branch-in-main-checkout", ("--create", "--action", "task", "--slug", "d", "--date", DATE,
                                                 "--existing", "--branch", self.world.default)),
            ("refused nested", ("--create", "--action", "task", "--slug", "x/y", "--date", DATE, "--base",
                                self.world.default, "--branch", "task/x/y")),
        ]
        outcomes = {}
        for label, args in steps:
            proc, plan = self.flat(*args)
            self.need_plan(proc, plan, label)
            outcomes[label] = plan
            self.assertEqual(snapshot(self.main), before,
                             msg=f"I-4: after '{label}' the main checkout's HEAD, index or a working file changed")
        self.assertEqual(outcomes["new-from-base"].get("outcome"), "created",
                         msg="fixture sanity: the byte-identity claim is only worth anything if the helper really ran")
        self.assertEqual(tree_switching_calls(self.tools.git_calls()), [],
                         msg="I-4: the helper must never run `git switch` or `git checkout` in any tree")
        self.assertTrue(self.tools.git_calls(), msg="positive control: the logging git saw the helper's calls")

    def test_positive_control_a_deliberate_checkout_in_the_main_checkout_does_change_head(self):
        self._dirty_main()
        before = snapshot(self.main)
        git(self.main, "branch", "feature/other")
        git(self.main, "checkout", "-q", "feature/other")
        after = snapshot(self.main)
        self.assertNotEqual(after["HEAD"], before["HEAD"],
                            msg="positive control: the snapshot must see a real checkout, or the tests above prove nothing")
        git(self.main, "checkout", "-q", self.world.default)
        self.assertEqual(snapshot(self.main), before, msg="control: going back restores the identical snapshot")


if __name__ == "__main__":
    unittest.main(verbosity=2)
