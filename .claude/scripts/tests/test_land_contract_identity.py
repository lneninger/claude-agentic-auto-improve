#!/usr/bin/env python3
"""
Tests for the identity and process hardening of land_contract.py (contract
2026-10-07-landing-and-loop-hardening, sub-task 1, issue 482): W3 (L-14'), W6 (L-17), W11 (L-15').

RED-phase file. ``land_contract`` is loaded through the same guarded import as test_land_contract.py
and every symbol is looked up with ``self.fn``, so an absent module or symbol is an AssertionError
naming it, never an ImportError. The module guard, the temporary-repository kit and the launcher
harness below are copied from test_land_contract.py so this file stands alone (it is mirrored to the
plugin). Git runs in temporary repositories only. Every conventions file the tests need is built in
the temporary repository with neutral paths; this project's real conventions file is never read.

  W3   a verification step, a setup entry and a regenerator launched by the stage see
       CLAUDE_PROJECT_DIR equal to the landing checkout; the stage's own state and logs stay under the
       main root.
  W6   a dead lock holder with a live stage of the same run is a live run: read_status says "live",
       lock_acquire refuses, the relaunch halts landing-in-progress without any worktree_reset. The
       stage writes stage_pid and stage_started_at and releases its own run's lock after report.json.
  W11  a checkout re-created by hand at a recorded landing path is never reset (environment-failure,
       remedy "remove the landing worktree <path> with git worktree remove, then rerun"); a created
       checkout gets a landing-owner marker; P15 writes phase.json worktree null after a removal.

Tests that pass today by design are named test_positive_control_*.

Run: py -3 -B .claude/scripts/tests/test_land_contract_identity.py
"""

import contextlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent.parent
THIS_FILE = Path(__file__).resolve()
sys.path.insert(0, str(SCRIPTS_DIR))


def norm(path):
    return os.path.normcase(os.path.realpath(str(path)))


def _is_under(path, root):
    p, r = norm(path), norm(root)
    return p == r or p.startswith(r + os.sep)


# ---------------------------------------------------------------------------
# Structural guard (extends test_pr_merged.py:70-96). No test here may reach a real GitHub
# mutation or a real push, however the command is spelled, and no test may run git inside
# the checkout this file lives in. The launchers are patched at MODULE TOP, before the guarded
# import of land_contract below, so a ``from subprocess import Popen`` inside land_contract
# captures the guarded class, never the real one.
# ---------------------------------------------------------------------------
_REAL_SUBPROCESS_RUN = subprocess.run
_REAL_POPEN = subprocess.Popen
_REAL_OS_SYSTEM = os.system
_REAL_OS_POPEN = os.popen
_TEMP_ROOT = tempfile.gettempdir()

_FORBIDDEN_SEQUENCES = (
    ("gh", ("pr", "merge")),
    ("gh", ("pr", "create")),
    ("gh", ("pr", "edit")),
    ("gh", ("pr", "ready")),
    ("gh", ("issue", "close")),
    ("git", ("push",)),
)
_OPTIONS_WITH_VALUE = {
    "git": {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"},
    "gh": {"-R", "--repo"},
}
_DIR_OPTIONS = ("-C", "--git-dir", "--work-tree")
_GH_ENV_KEYS = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GH_REPO")


def _program(token):
    name = os.path.basename(token.replace("\\", "/")).lower()
    for ext in (".exe", ".cmd", ".bat"):
        if name.endswith(ext):
            name = name[:-len(ext)]
    return name


def _strip_quotes(word):
    word = word.strip()
    while len(word) >= 2 and word[0] == word[-1] and word[0] in "\"'":
        word = word[1:-1].strip()
    return word


def _expand(item, depth=0):
    """One argv item or shell word -> words. An item that is itself ONE executable path
    (``C:\\Program Files\\Git\\cmd\\git.EXE``, spaces and all) stays whole, found by the basename;
    any other item with spaces is split again WITHOUT posix escaping (posix splitting eats the
    backslashes of a Windows path), so ``cmd /c "gh pr merge 5"`` exposes its inner words."""
    if depth > 4 or not re.search(r"\s", item) or _program(item) in ("git", "gh"):
        return [item]
    # cmd's own rule: /c "<command line>" drops the OUTER quote pair (the inner path keeps its own)
    item = re.sub(r'(?i)(/[ck])\s+"(.*)"\s*$', r"\1 \2", item)
    try:
        words = shlex.split(item, posix=False)
    except ValueError:
        words = item.split()
    out = []
    for word in words:
        out.extend(_expand(_strip_quotes(word), depth + 1))
    return out


def _tokens(cmd):
    """Flatten an argv or a shell string into words (see _expand)."""
    if isinstance(cmd, (bytes, os.PathLike)):
        cmd = os.fsdecode(cmd)
    items = [cmd] if isinstance(cmd, str) else [os.fsdecode(c) if not isinstance(c, str) else c
                                                 for c in cmd]
    out = []
    for item in items:
        out.extend(_expand(_strip_quotes(str(item))))
    return out


def _skip_options(tokens, j, program):
    """Skip option words at tokens[j:] (``--opt v`` and ``--opt=v`` forms); return the new index
    and the (option, value) pairs that name a directory (-C, --git-dir, --work-tree)."""
    with_value, dirs = _OPTIONS_WITH_VALUE[program], []
    while j < len(tokens) and tokens[j].startswith("-"):
        name, eq, value = tokens[j].partition("=")
        if tokens[j] in with_value and j + 1 < len(tokens):
            if tokens[j] in _DIR_OPTIONS:
                dirs.append((tokens[j], tokens[j + 1]))
            j += 2
        elif eq and name in with_value:
            if name in _DIR_OPTIONS:
                dirs.append((name, value))
            j += 1
        else:
            j += 1
    return j, dirs


def _effective_dirs(base_cwd, dirs):
    """The directory git acts in (cwd moved by every -C) plus any --git-dir / --work-tree."""
    cwd = base_cwd
    for option, value in dirs:
        if option == "-C":
            cwd = os.path.join(cwd, value)
    return [cwd] + [os.path.join(cwd, v) for o, v in dirs if o in ("--git-dir", "--work-tree")]


def _is_api_merge(rest):
    """``gh api -X PUT .../pulls/<n>/merge`` in any spelling of the method option."""
    put = False
    for idx, word in enumerate(rest):
        low = word.lower()
        nxt = rest[idx + 1].upper() if idx + 1 < len(rest) else ""
        if (low in ("-x", "--method") and nxt == "PUT") or low in ("-xput", "--method=put"):
            put = True
    return put and any(re.search(r"pulls/[^/\s]+/merge", w) for w in rest)


def _is_url(text):
    return "://" in text or bool(re.match(r"^[\w.-]+@[\w.-]+:", text))


def _push_target_is_temporary(rest, where):
    """True only when the push remote positively resolves to a filesystem path under the
    temporary root: a path given directly, or a named remote (default origin) that
    ``git remote get-url --push`` resolves to one. A URL, an unknown remote or a directory that
    is not a repository is NOT temporary (the reading git call is a harmless read)."""
    remote = next((w for w in rest if not w.startswith("-")), "origin")
    if _is_url(remote):
        return False
    target = None
    try:
        proc = _REAL_POPEN(["git", "-C", where, "remote", "get-url", "--push", remote],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, _ = proc.communicate(timeout=30)
        if proc.returncode == 0 and out.strip():
            target = out.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    if target is None and os.path.isabs(remote):
        target = remote  # an explicit absolute path given as the remote
    if target is None or _is_url(target):
        return False
    return _is_under(os.path.join(where, target), _TEMP_ROOT)


def _guard_verdict(cmd, cwd=None):
    """None when the command may run, else the reason it must not (pure, so it is testable)."""
    tokens = _tokens(cmd)
    base_cwd = str(cwd) if cwd else os.getcwd()
    for i, tok in enumerate(tokens):
        program = _program(tok)
        if program not in ("git", "gh"):
            continue
        j, dirs = _skip_options(tokens, i + 1, program)
        effective = _effective_dirs(base_cwd, dirs) if program == "git" else [base_cwd]
        if program == "git":
            for where in effective:
                if _is_under(where, REPO_ROOT):
                    return ("git run inside the checkout this test file lives in (%s): tests "
                            "may only touch temporary repositories" % where)
        if program == "gh" and j < len(tokens) and tokens[j].lower() == "api" \
                and _is_api_merge(tokens[j + 1:]):
            return "real gh api PUT pulls/<n>/merge"
        for want_program, tail in _FORBIDDEN_SEQUENCES:
            if want_program != program:
                continue
            k, ok = j, True
            for word in tail:
                k, _ = _skip_options(tokens, k, program)
                if k < len(tokens) and tokens[k].lower() == word:
                    k += 1
                else:
                    ok = False
                    break
            if not ok:
                continue
            if program == "git" and all(_is_under(w, _TEMP_ROOT) for w in effective):
                if _push_target_is_temporary(tokens[k:], effective[0]):
                    continue  # the fixture pushing a temporary clone to a temporary bare origin
                return "git push whose remote is not a temporary bare repository"
            return "real %s %s" % (program, " ".join(tail))
    return None


def _refuse(cmd, cwd):
    reason = _guard_verdict(cmd, cwd)
    if reason:
        raise RuntimeError(
            "test suite attempted %s via %r -- a test failed to intercept the edge before it "
            "reached a process launcher. Never patch this guard away; patch the land_contract "
            "edge in the failing test instead." % (reason, cmd))


class _GuardedPopen(_REAL_POPEN):
    """subprocess.run, call and check_output all construct a Popen, so this covers them."""

    def __init__(self, args, *a, **kw):
        cwd = kw.get("cwd") or (a[8] if len(a) > 8 else None)
        _refuse(args, cwd)
        super().__init__(args, *a, **kw)


def _guarded_os_system(command):
    _refuse(command, None)
    return _REAL_OS_SYSTEM(command)


def _guarded_os_popen(cmd, *a, **kw):
    _refuse(cmd, None)
    return _REAL_OS_POPEN(cmd, *a, **kw)


def _install_guards():
    subprocess.Popen = _GuardedPopen
    os.system = _guarded_os_system
    os.popen = _guarded_os_popen


_install_guards()  # BEFORE the guarded import below
_INSTALLED_BEFORE_IMPORT = (subprocess.Popen is _GuardedPopen and os.system is _guarded_os_system
                            and os.popen is _guarded_os_popen)

try:  # the guarded import: absent module is None, never an ImportError
    import land_contract
except ImportError:  # pragma: no cover - the RED state
    land_contract = None

if land_contract is not None:  # belt and braces: rebind any real launcher the module kept by name
    for _name, _value in list(vars(land_contract).items()):
        if _value is _REAL_POPEN:
            setattr(land_contract, _name, _GuardedPopen)
        elif _value is _REAL_OS_SYSTEM:
            setattr(land_contract, _name, _guarded_os_system)
        elif _value is _REAL_OS_POPEN:
            setattr(land_contract, _name, _guarded_os_popen)

import pr_merged  # noqa: E402

_SANDBOX = {"dir": None, "cwd": None, "gh_config": None, "env": {}}


def setUpModule():
    _install_guards()  # idempotent: another module's tearDown may have restored the real ones
    _SANDBOX["cwd"] = os.getcwd()
    _SANDBOX["dir"] = tempfile.mkdtemp(prefix="landtest-cwd-")
    os.chdir(_SANDBOX["dir"])  # an inherited working directory is never this checkout
    # Any real gh call is unauthenticated, however it is spelled: an empty config directory and
    # no token or repository variable in the environment.
    _SANDBOX["env"] = {k: os.environ.get(k) for k in _GH_ENV_KEYS + ("GH_CONFIG_DIR",)}
    _SANDBOX["gh_config"] = tempfile.mkdtemp(prefix="landtest-ghcfg-")
    os.environ["GH_CONFIG_DIR"] = _SANDBOX["gh_config"]
    for key in _GH_ENV_KEYS:
        os.environ.pop(key, None)


def tearDownModule():
    subprocess.Popen = _REAL_POPEN
    os.system = _REAL_OS_SYSTEM
    os.popen = _REAL_OS_POPEN
    for key, value in _SANDBOX["env"].items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    if _SANDBOX["cwd"]:
        os.chdir(_SANDBOX["cwd"])
    for key in ("dir", "gh_config"):
        if _SANDBOX[key]:
            shutil.rmtree(_SANDBOX[key], ignore_errors=True)


class LandCase(unittest.TestCase):
    """Base class: asserts the module and each symbol exist before anything else."""

    def mod(self):
        self.assertIsNotNone(
            land_contract,
            "land_contract.py does not exist yet (.claude/scripts/land_contract.py); "
            "sub-task 2 creates it")
        return land_contract

    def fn(self, name):
        m = self.mod()
        f = getattr(m, name, None)
        self.assertIsNotNone(f, "land_contract.%s does not exist yet" % name)
        return f


# Real-git helpers. Used only on temporary repositories built by a test. The guard above
# lets a git push through only when its effective directory is under the temporary root, so
# the helper pushes only from a temporary clone toward a temporary bare repository.
# ---------------------------------------------------------------------------
_GIT_ENV = dict(os.environ,
                GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.test",
                GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.test")


def git(cwd, *args, check=True):
    proc = _REAL_SUBPROCESS_RUN(
        ["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false"] + list(args),
        cwd=str(cwd), capture_output=True, text=True, env=_GIT_ENV)
    if check and proc.returncode != 0:
        raise AssertionError("fixture git %r failed: %s" % (args, proc.stderr))
    return proc.stdout.strip()


def write_files(root, files):
    for rel, text in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")


def sha40(ch):
    return ch * 40


def children(nodes, total=None):
    return {"nodes": [{"number": n, "state": s} for n, s in nodes],
            "totalCount": len(nodes) if total is None else total}


def record_yaml(**over):
    import yaml
    rec = {"status": "completed", "verified": "github", "pull_request": "u", "review_verdict": "pass"}
    rec.update(over)
    return yaml.dump(rec, default_flow_style=False)


def brief_md(bid, base=None, branch=None, parent_issue=394, slug=None):
    lines = ["---", "id: %s" % bid, "title: t"]
    if parent_issue is not None:
        lines.append("parent_issue: %s" % parent_issue)
    if base:
        lines.append("base: %s" % base)
    if branch:
        lines.append("branch: %s" % branch)
    lines += ["contract: .claude/concepts/%s.md" % (slug or SLUG), "status: implementing", "---", "", "# t", ""]
    return "\n".join(lines)


SLUG = "2026-10-05-demo"
PARENT = "feature/p"
REC_DIR = ".claude/orchestrator/results/%s/" % SLUG
BRIEF_DIR = ".claude/work-items/"


CONTRACT_TEXT = """# Demo contract

## Implementation Handoff

### 1. Backend (`acme-dev`)

**Depends on:** none

**Files to touch:**
- src/Foo.cs

### 2. Frontend (`acme-dev`)

**Depends on:** none

**Files to touch:**
- src/Bar.cs
"""

STEP_UNIT = {"id": "py-unit", "suite": "scripts", "when_paths": ["src/**"],
             "command": ["py", "-3", "run_unit.py", "{results_dir}/out.txt"],
             "results": {"format": "unittest-text", "path": "{results_dir}/out.txt"},
             "timeout_minutes": 5, "environment_signatures": []}
STEP_BUILD = {"id": "compile", "suite": "build", "when_paths": ["**"],
              "command": ["py", "-3", "-c", "pass"], "results": {"format": "exit-code"},
              "timeout_minutes": 5, "environment_signatures": []}


def landing_config(steps=None, **over):
    cfg = {"mergeMethod": "merge", "protectedBranches": ["master", "main"], "unionPaths": [],
           "regenerators": [], "setup": [], "emulators": [],
           "verification": {"steps": steps if steps is not None else [STEP_UNIT, STEP_BUILD]},
           "reviewCoverage": [], "forbiddenPaths": []}
    cfg.update(over)
    return cfg


def conventions_text(cfg):
    return json.dumps({"contractLanding": cfg} if cfg is not None else {}, indent=2)


BASELINE_CLEAN = {"scripts": {"measured_on": "master", "measured_at_commit": sha40("0"), "runs": 2,
                              "known_failing": {}, "known_flaky": [], "note": "fixture"}}
BASELINE_WIDENED = {"scripts": {"measured_on": "master", "measured_at_commit": sha40("0"), "runs": 2,
                                "known_failing": {"scripts::tests.U": ["test_x"]},
                                "known_flaky": [], "note": "fixture"}}
CONVENTIONS = ".claude/work-item-conventions.json"
BASELINE_FILE = ".claude/test-baseline.json"


class Kit:
    """origin.git (bare) + main (operator checkout, on master) + scratch (remote-only commits)."""

    def __init__(self, tmp, *, parent_records=("t1-backend", "t2-frontend"), config=None,
                 baseline=BASELINE_CLEAN, base_files=None, parent_files=None, brief_base=PARENT,
                 verdicts=None, script_text="# the landing script\n", conventions_on_master=True,
                 with_parent_brief=True):
        self.tmp = Path(tmp)
        self.origin = self.tmp / "origin.git"
        self.main = self.tmp / "main"
        self.scratch = self.tmp / "scratch"
        git(self.tmp, "init", "--bare", "--initial-branch=master", str(self.origin))
        git(self.tmp, "clone", str(self.origin), str(self.main))
        self._configure(self.main)
        cfg = config if config is not None else landing_config()
        files = {"README.txt": "demo\n", ".gitignore":
                 ".claude/state/\n.claude/logs/\n.claude/worktrees/\nnode_modules/\n",
                 ".claude/concepts/%s.md" % SLUG: CONTRACT_TEXT}
        if conventions_on_master:
            files[CONVENTIONS] = conventions_text(cfg)
        if baseline is not None:
            files[BASELINE_FILE] = baseline if isinstance(baseline, str) else json.dumps(baseline)
        files.update(base_files or {})
        write_files(self.main, files)
        git(self.main, "add", "-A")
        git(self.main, "commit", "-m", "initial")
        self._push(self.main, "master")
        git(self.main, "checkout", "-b", PARENT)
        self.brief_files = self._brief_files(brief_base)
        if not with_parent_brief:
            self.brief_files.pop(BRIEF_DIR + "2026-10-05-394-demo.md")
        # script_text None: the landing code is absent at origin/<parent> (a P0 halt).
        pfiles = {".claude/scripts/land_contract.py": script_text} if script_text is not None else {}
        pfiles.update(self.brief_files)
        verdicts = verdicts or {}
        for tid in parent_records:
            pfiles[REC_DIR + tid + ".yaml"] = record_yaml(**({"review_verdict": verdicts[tid]}
                                                             if tid in verdicts else {}))
        pfiles.update(parent_files or {})
        write_files(self.main, pfiles)
        git(self.main, "add", "-A")
        git(self.main, "commit", "-m", "parent work")
        self._push(self.main, PARENT)
        git(self.main, "checkout", "master")
        # The operator's disk holds the briefs as /task wrote them (untracked on master).
        for rel in self.brief_files:
            target = self.main / rel
            if target.exists():
                target.unlink()
        write_files(self.main, self.brief_files)
        git(self.tmp, "clone", str(self.origin), str(self.scratch))
        self._configure(self.scratch)
        self.fetch()

    @staticmethod
    def _push(repo, branch):
        """Push a temporary clone to the temporary bare origin, never to a real remote."""
        proc = _REAL_SUBPROCESS_RUN(["git", "push", "origin", "HEAD:refs/heads/%s" % branch],
                                    cwd=str(repo), capture_output=True, text=True, env=_GIT_ENV)
        if proc.returncode != 0:
            raise AssertionError("fixture push failed: %s" % proc.stderr)

    @staticmethod
    def _configure(repo):
        for k, v in (("user.name", "t"), ("user.email", "t@example.test"),
                     ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
            git(repo, "config", k, v)

    @staticmethod
    def _brief_files(base):
        return {
            BRIEF_DIR + "2026-10-05-394-demo.md": brief_md(394, branch=PARENT, parent_issue=None),
            BRIEF_DIR + "2026-10-05-401-t1-backend.md": brief_md(401, base=base),
            BRIEF_DIR + "2026-10-05-402-t2-frontend.md": brief_md(402, base=base),
        }

    def fetch(self):
        git(self.main, "fetch", "origin")

    def commit_remote(self, branch, files, message="remote work"):
        git(self.scratch, "fetch", "origin")
        exists = _REAL_SUBPROCESS_RUN(
            ["git", "rev-parse", "--verify", "--quiet", "origin/%s" % branch],
            cwd=str(self.scratch), capture_output=True, env=_GIT_ENV).returncode == 0
        git(self.scratch, "checkout", "-B", branch, "origin/%s" % (branch if exists else "master"))
        write_files(self.scratch, files)
        git(self.scratch, "add", "-A")
        git(self.scratch, "commit", "-m", message)
        self._push(self.scratch, branch)
        self.fetch()

    def add_worktree(self, name, ref="origin/%s" % PARENT):
        path = self.main / ".claude" / "worktrees" / name
        git(self.main, "worktree", "add", "--detach", str(path), ref)
        return path

    def local_parent_ahead(self):
        tip = git(self.main, "rev-parse", "refs/heads/%s" % PARENT)
        commit = git(self.main, "commit-tree", tip + "^{tree}", "-p", tip, "-m", "local only")
        git(self.main, "update-ref", "refs/heads/%s" % PARENT, commit)

    def landing_dir(self):
        return self.main / ".claude" / "state" / "landing"

    def report(self, slug=SLUG):
        p = self.landing_dir() / slug / "report.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@contextlib.contextmanager
def operator_shell(cwd, env=None):
    """cwd = the operator checkout; GH_REPO and CLAUDE_PROJECT_DIR unset unless given."""
    saved_cwd = os.getcwd()
    saved = {k: os.environ.get(k) for k in ("GH_REPO", "CLAUDE_PROJECT_DIR")}
    os.environ.pop("GH_REPO", None)
    os.environ.pop("CLAUDE_PROJECT_DIR", None)
    os.environ.update(env or {})
    os.chdir(str(cwd))
    try:
        yield
    finally:
        os.chdir(saved_cwd)
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class LauncherCase(LandCase):

    def setUp(self):
        self.mod()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def live_pid(self):
        """A process this test owns and stops by handle. Never os.getppid(): an implementation
        probing liveness with os.kill(pid, 0) would TERMINATE a live process on Windows."""
        sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
        self.sleeper = sleeper  # launch() asserts it is STILL running after the launcher ran

        def stop():
            sleeper.kill()
            sleeper.wait()
        self.addCleanup(stop)
        return sleeper.pid

    def launch(self, kit, argv=None, exec_rc=0, exec_side_effect=None, env=None, stage_ok=True):
        """Run the launcher in the operator checkout. exec_stage (the landing itself) and
        probe_stage (does the worktree copy accept --stage land) are separate edges, so
        exec_stage.call_count is 1 for a landing that started and 0 otherwise."""
        lc = self.mod()
        self.fn("exec_stage")
        self.fn("probe_stage")
        exec_mock = mock.MagicMock(return_value=exec_rc, side_effect=exec_side_effect)
        self.probe_mock = mock.MagicMock(return_value=stage_ok)
        out = io.StringIO()
        with operator_shell(kit.main, env), \
             mock.patch.object(lc, "exec_stage", exec_mock), \
             mock.patch.object(lc, "probe_stage", self.probe_mock), \
             mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
             mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
             contextlib.redirect_stdout(out):
            code = lc.main(argv or ["--contract", SLUG, "--json"])
        self.stdout = out.getvalue()
        sleeper = getattr(self, "sleeper", None)
        if sleeper is not None:
            self.assertIsNone(sleeper.poll(),
                              "the live lock holder must still be running after the launcher "
                              "ran: a liveness probe with os.kill(pid, 0) TERMINATES a live "
                              "process on Windows")
        return code, exec_mock, kit.report()

    def outcome(self, report):
        self.assertIsNotNone(report, "report.json must be written on every exit, halts included")
        return report["outcome"]


# ===========================================================================
# The landing stage, driven in a temporary repository. Every network, push and gh edge is a
# recording fake; git is real. _run_long is real only when a test asks for it (real_long), so a
# child process can print what it was launched with.
# ===========================================================================
ENV_PRINT = "import os; print('CPD=' + os.environ.get('CLAUDE_PROJECT_DIR', ''))"
STEP_CLEAN = {"id": "compile", "suite": "build", "when_paths": ["**"],
              "command": ["py", "-3", "-c", "pass"], "results": {"format": "exit-code"},
              "timeout_minutes": 5, "environment_signatures": []}
SRC_CHANGE = {"src/feature.py": "x = 1\n"}


class Stage:
    """Real git in a temporary repo; every network and push edge is a recording fake."""

    def __init__(self, case, kit, *, worktree_name="20260101-land-394", real_long=False):
        self.case, self.kit = case, kit
        self.lc = case.mod()
        for name in ("run_landing", "git_show", "git_merge", "git_commit", "_run_long", "git_push",
                     "worktree_remove", "write_phase", "write_report"):
            case.fn(name)
        self.worktree = kit.add_worktree(worktree_name)
        self.calls = []
        self.pr = None
        self.children = children([(401, "CLOSED"), (402, "CLOSED")])
        self.push_result = (0, "")
        self.remove_raises = None
        self.run_id = "run-1"
        self.real_long = real_long

    def head(self):
        return git(self.worktree, "rev-parse", "HEAD")

    def _dict(self):
        if self.pr is None:
            return None
        pr = dict(self.pr)
        if pr.get("headRefOid") is None:
            pr["headRefOid"] = self.head()
        return pr

    def install(self, stack):
        lc, stage, kit = self.lc, self, self.kit

        def rec(name, value=None):
            def fake(*a, **k):
                stage.calls.append(name)
                return value
            return fake

        def ls_remote(ref, *a, **k):
            stage.calls.append("git_ls_remote")
            if "master" in str(ref):
                return git(kit.main, "rev-parse", "refs/remotes/origin/master")
            return git(kit.main, "rev-parse", "refs/remotes/origin/%s" % PARENT)

        def push(*a, **k):
            stage.calls.append("git_push")
            return stage.push_result

        def find(*a, **k):
            stage.calls.append("gh_pr_find")
            return stage._dict()

        def create(*a, **k):
            stage.calls.append("gh_pr_create")
            stage.pr = {"number": 7, "state": "OPEN", "isDraft": False, "baseRefName": "master",
                        "headRefName": PARENT, "headRefOid": None, "url": "https://example.test/o/r/pull/7"}
            return (0, stage.pr["url"])

        def view(*a, **k):
            stage.calls.append("gh_pr_view")
            pr = stage._dict() or {}
            pr["mergeable"] = "MERGEABLE"
            return pr

        def merge(*a, **k):
            stage.calls.append("gh_pr_merge")
            if stage.pr:
                stage.pr["state"] = "MERGED"
                stage.pr["mergeCommit"] = {"oid": sha40("d")}
            return (0, "")

        def remove(*a, **k):
            stage.calls.append("worktree_remove")
            if stage.remove_raises:
                raise stage.remove_raises

        fakes = {
            "git_ls_remote": ls_remote, "tcp_probe": lambda *a, **k: True,
            "gh_auth_status": lambda *a, **k: True, "git_push": push, "gh_pr_find": find,
            "gh_pr_create": create, "gh_pr_ready": rec("gh_pr_ready", (0, "")), "gh_pr_view": view,
            "gh_pr_merge": merge, "gh_pr_edit_body": rec("gh_pr_edit_body", (0, "")),
            "verify_closing_link": lambda *a, **k: "linked",
            "read_children": lambda *a, **k: stage.children,
            "gh_issue_state": lambda *a, **k: "CLOSED",
            "write_bookkeeping": rec("write_bookkeeping"), "worktree_remove": remove,
        }
        if not self.real_long:
            fakes["_run_long"] = lambda *a, **k: (0, False)
        for name, f in fakes.items():
            stack.enter_context(mock.patch.object(lc, name, side_effect=f))
        stack.enter_context(mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)))
        stack.enter_context(mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)))

    def run(self, extra_patches=(), **over):
        args = {"contract": SLUG, "parent": PARENT, "project_root": str(self.kit.main),
                "checkout": str(self.kit.main), "run_id": self.run_id,
                "worktree": str(self.worktree), "dry_run": False}
        args.update(over)
        saved_cwd = os.getcwd()
        saved_env = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        os.chdir(str(self.kit.tmp))  # never this checkout: the module guard refuses git there
        try:
            with contextlib.ExitStack() as stack:
                self.install(stack)
                for patch in extra_patches:
                    stack.enter_context(patch)
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                return self.lc.run_landing(args)
        finally:
            os.chdir(saved_cwd)
            if saved_env is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = saved_env

    def count(self, name):
        return self.calls.count(name)

    def phase(self):
        return json.loads((self.kit.landing_dir() / SLUG / "phase.json").read_text(encoding="utf-8"))


class StageCase(LandCase):

    def setUp(self):
        self.mod()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)


def dead_pid():
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


# ===========================================================================
# W3 (L-14'): a child sees the landing checkout as CLAUDE_PROJECT_DIR, the stage keeps the main root
# ===========================================================================
class TestChildrenSeeTheLandingCheckout(StageCase):
    """A verification step, a setup entry and a regenerator each print CLAUDE_PROJECT_DIR."""

    def landed_world(self):
        step = {"id": "env-step", "suite": "build", "when_paths": ["**"],
                "command": [sys.executable, "-c", ENV_PRINT], "results": {"format": "exit-code"},
                "timeout_minutes": 5, "environment_signatures": []}
        setup = [{"id": "env-setup", "when_missing": "absent-marker", "cwd": ".",
                  "command": [sys.executable, "-c", ENV_PRINT]}]
        regen = [{"id": "env-regen", "paths": ["generated/**"], "triggers": ["src/**"],
                  "command": [[sys.executable, "-c", ENV_PRINT]]}]
        kit = Kit(Path(self._tmp.name), config=landing_config(steps=[step], setup=setup, regenerators=regen),
                  parent_files=SRC_CHANGE)
        # master moves on, so P7 has a merge to do and the regenerator's trigger applies.
        kit.commit_remote("master", {"master-note.txt": "master moved on\n"})
        st = Stage(self, kit, real_long=True)
        st.push_result = (1, "stop here")  # the run ends at P9, after P6, P7 and P8 have run the children
        st.run()
        return st

    def seen(self, st, dirname):
        for log in (st.kit.main / ".claude").rglob("output.log"):
            if "worktrees" in log.parts or log.parent.name != dirname:
                continue
            found = re.search(r"CPD=(.*)", log.read_text(encoding="utf-8", errors="replace"))
            if found:
                return log, found.group(1).strip()
        return None, None

    def assert_sees_checkout(self, st, dirname, what):
        log, value = self.seen(st, dirname)
        self.assertIsNotNone(log, "fixture sanity: the %s ran and printed CPD= (looked for %s/output.log)"
                             % (what, dirname))
        self.assertEqual(norm(value), norm(st.worktree),
                         "L-14': the %s runs with CLAUDE_PROJECT_DIR equal to the landing checkout %s, "
                         "not the main root; it saw %s" % (what, st.worktree, value))

    def test_a_verification_step_sees_the_landing_checkout(self):
        self.assert_sees_checkout(self.landed_world(), "env-step", "verification step")

    def test_a_setup_entry_sees_the_landing_checkout(self):
        self.assert_sees_checkout(self.landed_world(), "setup-env-setup-0", "setup entry")

    def test_a_regenerator_sees_the_landing_checkout(self):
        self.assert_sees_checkout(self.landed_world(), "regen-env-regen-0", "regenerator")

    def test_positive_control_the_stage_itself_still_keeps_its_state_and_logs_under_the_main_root(self):
        st = self.landed_world()
        log, _ = self.seen(st, "env-step")
        self.assertIsNotNone(log, "fixture sanity: the verification step ran")
        self.assertTrue(norm(log).startswith(norm(st.kit.main / ".claude")),
                        "logs_dir() resolves under the main root, never the landing checkout: %s" % log)
        self.assertTrue((st.kit.landing_dir() / SLUG / "phase.json").is_file(),
                        "state_dir() resolves under the main root: phase.json lives in the runtime root")
        self.assertFalse((st.worktree / ".claude" / "state" / "landing").exists(),
                         "and nothing of the stage's state was written inside the landing checkout")


# ===========================================================================
# W6 (L-17): a live stage keeps the run alive when the launcher that holds the lock is dead
# ===========================================================================
class TestLiveStageKeepsTheRunAlive(LauncherCase):

    def plant(self, kit, *, stage_pid, lock_run="old", phase_run="old", holder_pid=None):
        write_files(kit.landing_dir(), {"lock": json.dumps(
            {"pid": holder_pid if holder_pid is not None else dead_pid(), "run_id": lock_run,
             "kind": "land", "contract": SLUG, "started_at": "2026-10-05T00:00:00Z"})})
        write_files(kit.landing_dir() / SLUG, {"phase.json": json.dumps(
            {"run_id": phase_run, "phase": "p8", "started_at": "2026-10-05T00:00:00Z",
             "heartbeat_at": "2026-10-05T00:01:00Z", "worktree": None, "merge_commit": None,
             "stage_pid": stage_pid, "stage_started_at": "2026-10-05T00:00:05Z"})})

    def status(self, kit):
        self.launch(kit, argv=["--contract", SLUG, "--status", "--json"])
        return json.loads(self.stdout)["state"]

    def acquire(self, kit):
        return self.fn("lock_acquire")(kit.landing_dir(), {
            "pid": os.getpid(), "run_id": "new", "kind": "land", "contract": SLUG,
            "started_at": "2026-10-07T00:00:00Z"})

    # -- the W6 cases ---------------------------------------------------------
    def test_status_reads_live_when_the_holder_is_dead_but_its_stage_is_alive(self):
        kit = Kit(self._tmp.name)
        self.plant(kit, stage_pid=self.live_pid())
        self.assertEqual(self.status(kit), "live",
                         "L-17: the lock's run_id equals phase.json's and its stage_pid is alive, so the "
                         "run is live although the launcher that wrote the lock is gone")

    def test_lock_acquire_is_refused_while_the_stage_is_alive(self):
        kit = Kit(self._tmp.name)
        self.plant(kit, stage_pid=self.live_pid())
        taken = self.acquire(kit)
        self.assertFalse(taken["acquired"],
                         "L-17: a second run must not take the lock from a run whose stage still works")
        held = json.loads((kit.landing_dir() / "lock").read_text(encoding="utf-8"))
        self.assertEqual(held["run_id"], "old", "and the lock file still names the live run")

    def test_a_relaunch_does_not_reset_the_worktree_and_halts_landing_in_progress(self):
        kit = Kit(self._tmp.name)
        self.plant(kit, stage_pid=self.live_pid())
        lc = self.mod()
        self.fn("worktree_reset")
        before = git(kit.main, "worktree", "list", "--porcelain")
        with mock.patch.object(lc, "worktree_reset") as reset:
            _, execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "landing-in-progress",
                         "L-17: the relaunch finds the run live and halts at P0")
        reset.assert_not_called()
        execm.assert_not_called()
        self.assertEqual(git(kit.main, "worktree", "list", "--porcelain"), before,
                         "and no landing checkout was created or touched")

    # -- positive controls (all pass today by design) -------------------------------
    def test_positive_control_a_dead_stage_with_no_report_is_interrupted(self):
        kit = Kit(self._tmp.name)
        self.plant(kit, stage_pid=dead_pid())
        self.assertEqual(self.status(kit), "interrupted",
                         "holder dead and stage dead and no report: the run was interrupted")

    def test_positive_control_a_dead_stage_lets_the_lock_be_reclaimed(self):
        kit = Kit(self._tmp.name)
        self.plant(kit, stage_pid=dead_pid())
        self.assertTrue(self.acquire(kit)["acquired"], "nothing alive holds the run, so the lock is reclaimed")

    def test_positive_control_a_phase_of_another_run_does_not_make_the_run_live(self):
        kit = Kit(self._tmp.name)
        self.plant(kit, stage_pid=self.live_pid(), phase_run="someone-else")
        self.assertEqual(self.status(kit), "interrupted",
                         "the live stage_pid belongs to a different run_id, so it proves nothing for this lock")

    def test_positive_control_a_phase_of_another_run_lets_the_lock_be_reclaimed(self):
        kit = Kit(self._tmp.name)
        self.plant(kit, stage_pid=self.live_pid(), phase_run="someone-else")
        self.assertTrue(self.acquire(kit)["acquired"], "run_id mismatch: not live, so reclaimable")

    def test_positive_control_a_live_lock_holder_still_means_live(self):
        kit = Kit(self._tmp.name)
        self.plant(kit, stage_pid=dead_pid(), holder_pid=self.live_pid())
        self.assertEqual(self.status(kit), "live", "the launcher itself being alive is live, as before")


class TestStageRecordsItsProcessAndReleasesItsLock(StageCase):

    def halted_stage(self):
        kit = Kit(Path(self._tmp.name), parent_files=SRC_CHANGE)
        st = Stage(self, kit)
        st.children = children([(401, "OPEN"), (402, "CLOSED")])  # halts at P4: cheap and deterministic
        return st

    def plant_lock(self, st, run_id):
        write_files(st.kit.landing_dir(), {"lock": json.dumps(
            {"pid": dead_pid(), "run_id": run_id, "kind": "land", "contract": SLUG,
             "started_at": "2026-10-05T00:00:00Z"})})

    def test_the_stage_writes_its_pid_and_start_time_into_phase_json(self):
        st = self.halted_stage()
        report = st.run()
        self.assertEqual(report["outcome"], "children-still-open", "fixture sanity: the run reached P4")
        phase = st.phase()
        self.assertEqual(phase.get("stage_pid"), os.getpid(),
                         "L-17: phase.json carries the stage's own process id (this test is the stage)")
        self.assertTrue(phase.get("stage_started_at"), "and the instant the stage started")

    def test_the_stage_releases_the_lock_of_its_own_run_after_writing_report_json(self):
        st = self.halted_stage()
        self.plant_lock(st, st.run_id)
        lock = st.kit.landing_dir() / "lock"
        state = {}
        original = self.mod().write_report

        def watching(contract_dir, report):
            state["lock_present_at_report"] = lock.exists()
            original(contract_dir, report)
            state["report_written"] = (Path(contract_dir) / "report.json").is_file()

        st.run(extra_patches=[mock.patch.object(self.mod(), "write_report", side_effect=watching)])
        self.assertTrue(state.get("report_written"), "fixture sanity: the stage wrote report.json")
        self.assertTrue(state.get("lock_present_at_report"),
                        "the lock is still held while report.json is written: a report for a run whose "
                        "lock is already free could be read as a finished run")
        self.assertFalse(lock.exists(), "L-17: the stage releases the lock for its own run_id when it is done")

    def test_positive_control_the_stage_leaves_the_lock_of_another_run_alone(self):
        st = self.halted_stage()
        self.plant_lock(st, "someone-else")
        st.run()
        self.assertTrue((st.kit.landing_dir() / "lock").exists(),
                        "a lock that names another run is not the stage's to release")


# ===========================================================================
# W11 (L-15'): a landing checkout is reset only when a landing made it
# ===========================================================================
def owner_marker(wt):
    return Path(git(wt, "rev-parse", "--absolute-git-dir")) / "landing-owner"


class TestLandingCheckoutOwnership(LauncherCase):

    REMEDY = re.compile(r"remove the landing worktree (.+) with git worktree remove, then rerun")

    def record_phase(self, kit, wt):
        write_files(kit.landing_dir() / SLUG, {"phase.json": json.dumps(
            {"run_id": "old", "phase": "p15", "worktree": str(wt)})})

    def write_marker(self, wt, path=None, run_id="old"):
        owner_marker(wt).write_text(json.dumps(
            {"run_id": run_id, "path": str(path or wt), "created_at": "2026-10-05T00:00:00Z"}), encoding="utf-8")

    def hand_made(self, kit, name="20250101-land-394"):
        """An operator re-creates a checkout at a removed landing path: a branch, an edit, an untracked file."""
        path = kit.main / ".claude" / "worktrees" / name
        git(kit.main, "worktree", "add", "-b", "operator/land-394", str(path), "origin/%s" % PARENT)
        write_files(path, {"README.txt": "operator edit\n", "notes.txt": "unsaved work\n"})
        return path

    def assert_untouched(self, wt):
        self.assertEqual((wt / "README.txt").read_text(encoding="utf-8"), "operator edit\n", "the edit survives")
        self.assertEqual((wt / "notes.txt").read_text(encoding="utf-8"), "unsaved work\n",
                         "the untracked file survives")
        self.assertEqual(git(wt, "symbolic-ref", "-q", "HEAD"), "refs/heads/operator/land-394",
                         "the branch is not detached")

    def assert_refused_with_remedy(self, report, wt):
        self.assertEqual(self.outcome(report), "environment-failure", "P0 halts")
        found = self.REMEDY.fullmatch(report.get("remedy") or "")
        self.assertIsNotNone(found, "the remedy is 'remove the landing worktree <path> with git worktree "
                                    "remove, then rerun'; got %r" % report.get("remedy"))
        self.assertEqual(norm(found.group(1)), norm(wt), "and it names the checkout")

    def test_probe_c_a_recreated_checkout_at_a_recorded_landing_path_is_never_reset(self):
        kit = Kit(self._tmp.name)
        wt = self.hand_made(kit)
        self.record_phase(kit, wt)  # a finished run left this path in phase.json
        _, execm, report = self.launch(kit)
        self.assert_untouched(wt)
        execm.assert_not_called()
        self.assert_refused_with_remedy(report, wt)

    def test_a_marker_that_names_another_path_is_not_accepted(self):
        kit = Kit(self._tmp.name)
        wt = self.hand_made(kit)
        self.record_phase(kit, wt)
        self.write_marker(wt, path=kit.main / ".claude" / "worktrees" / "20240101-land-394")
        _, execm, report = self.launch(kit)
        self.assert_untouched(wt)
        execm.assert_not_called()
        self.assert_refused_with_remedy(report, wt)

    def test_a_created_checkout_gets_an_owner_marker_naming_the_run_and_the_path(self):
        kit = Kit(self._tmp.name)
        _, execm, _ = self.launch(kit)
        listing = git(kit.main, "worktree", "list", "--porcelain")
        created = [Path(l.split(" ", 1)[1]) for l in listing.splitlines()
                   if l.startswith("worktree ") and l.rstrip().endswith("-land-394")]
        self.assertEqual(len(created), 1, "fixture sanity: the launcher created one landing checkout")
        marker = owner_marker(created[0])
        self.assertTrue(marker.is_file(), "L-15': the run that created the checkout writes %s" % marker)
        data = json.loads(marker.read_text(encoding="utf-8"))
        argv = [str(a) for a in execm.call_args[0][0]]
        self.assertEqual(data.get("run_id"), argv[argv.index("--run-id") + 1], "the marker names the creating run")
        self.assertEqual(norm(data.get("path", "")), norm(created[0]), "and the checkout's own path")
        self.assertTrue(data.get("created_at"), "and when it was made")

    # -- positive controls (pass today by design) --------------------------------------
    def test_positive_control_a_reused_checkout_whose_marker_names_its_path_is_reset(self):
        kit = Kit(self._tmp.name)
        wt = kit.add_worktree("20250101-land-394")
        self.record_phase(kit, wt)
        self.write_marker(wt)
        before = owner_marker(wt).read_bytes()
        write_files(wt, {"notes.txt": "stray\n"})
        _, execm, _ = self.launch(kit)
        self.assertEqual(execm.call_count, 1, "a checkout a landing made is accepted and the stage starts")
        self.assertFalse((wt / "notes.txt").exists(), "and it was cleaned")
        self.assertEqual(owner_marker(wt).read_bytes(), before,
                         "a marker is never written on reuse and survives git clean")


# ===========================================================================
# W11 (P15): a removed landing checkout is not remembered
# ===========================================================================
class TestP15ForgetsTheRemovedCheckout(StageCase):

    def landed(self, remove_raises=None):
        kit = Kit(Path(self._tmp.name), config=landing_config(steps=[STEP_CLEAN]), parent_files=SRC_CHANGE)
        st = Stage(self, kit)
        st.remove_raises = remove_raises
        return st, st.run()

    def test_p15_writes_worktree_null_after_a_successful_removal(self):
        st, report = self.landed()
        self.assertEqual(report["outcome"], "landed", "fixture sanity: %s %s" % (report["outcome"], report["detail"]))
        self.assertEqual(st.count("worktree_remove"), 1, "fixture sanity: the removal ran and succeeded")
        phase = st.phase()
        self.assertIn("worktree", phase, "the key stays in phase.json")
        self.assertIsNone(phase["worktree"],
                          "L-15': once the checkout is removed phase.json must stop naming it (still names %r)"
                          % phase.get("worktree"))

    def test_a_later_write_phase_does_not_bring_the_removed_checkout_back(self):
        st, report = self.landed()
        self.assertEqual(report["outcome"], "landed", "fixture sanity")
        self.fn("write_phase")(st.kit.landing_dir() / SLUG, "run-2", "p0")
        self.assertIsNone(st.phase().get("worktree"),
                          "a later phase write with no worktree must not carry the removed path forward")

    def test_positive_control_a_failed_removal_keeps_the_record_so_the_next_run_can_retry(self):
        st, report = self.landed(remove_raises=RuntimeError("file in use"))
        self.assertEqual(report["outcome"], "landed", "the outcome stands")
        self.assertEqual(norm(st.phase().get("worktree") or ""), norm(st.worktree),
                         "the checkout still exists, so phase.json still names it")

    def test_positive_control_write_phase_records_a_worktree_it_is_given(self):
        kit = Kit(Path(self._tmp.name))
        path = kit.main / ".claude" / "worktrees" / "20260101-land-394"
        self.fn("write_phase")(kit.landing_dir() / SLUG, "run-3", "p0", worktree=path)
        phase = json.loads((kit.landing_dir() / SLUG / "phase.json").read_text(encoding="utf-8"))
        self.assertEqual(norm(phase["worktree"]), norm(path), "an explicit worktree is recorded")
        self.fn("write_phase")(kit.landing_dir() / SLUG, "run-3", "p1")
        phase = json.loads((kit.landing_dir() / SLUG / "phase.json").read_text(encoding="utf-8"))
        self.assertEqual(norm(phase["worktree"]), norm(path), "and carried forward while it still exists")


# ===========================================================================
# Issue 113: P7b, the Landing version raise (R-1, R-2, R-5), and the landing readers' feeders.
#
# P7b runs after P7 (the default branch merged into the parent branch) and before the verification:
# `check_version_bump.py --raise`, then `--exact`, committed on the parent branch. It reads its switch,
# contractLanding.versionRaise, from the conventions file at origin/<default>. It runs whether or not P7
# merged anything, and is idempotent. A raise that cannot be made halts `version-raise-failed`.
#
# The fixture puts the real check_version_bump.py and four manifest files into the repository, so the
# assertions hold wherever the implementation finds the script. Real git, fake network edges (Stage).
# ===========================================================================
_VBUMP_SCRIPT = Path(__file__).resolve().parent.parent / "check_version_bump.py"
_MANIFEST_NAMES = ("plugin.json", ".claude-plugin/plugin.json", ".cursor-plugin/plugin.json",
                   ".claude-plugin/marketplace.json")


def manifests_at(version):
    plugin = json.dumps({"name": "x", "version": version, "description": "d"}, indent=2) + "\n"
    market = json.dumps({"name": "m", "version": version,
                         "plugins": [{"name": "x", "version": version}]}, indent=2) + "\n"
    return {"plugin.json": plugin, ".claude-plugin/plugin.json": plugin,
            ".cursor-plugin/plugin.json": plugin, ".claude-plugin/marketplace.json": market}


def versions_in_tree(root):
    found = []
    for name in _MANIFEST_NAMES:
        data = json.loads((Path(root) / name).read_text(encoding="utf-8"))
        if "version" in data:
            found.append(data["version"])
        found.extend(entry["version"] for entry in data.get("plugins", []))
    return found


def isolated_git_env(folder):
    """The environment a spawned git sees: an identity, signing off, an empty global config, no system config."""
    empty = Path(folder) / "empty-gitconfig"
    empty.write_text("", encoding="utf-8")
    env = {k: _GIT_ENV[k] for k in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")}
    env.update(GIT_CONFIG_GLOBAL=str(empty), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_COUNT="1",
               GIT_CONFIG_KEY_0="commit.gpgsign", GIT_CONFIG_VALUE_0="false")
    return env


class TestP7bVersionRaise(StageCase):

    def landing(self, *, master="0.11.3", parent="0.10.0", versionRaise=True, parent_extra=None,
                move_master=True, subdir="k"):
        """The parent branch holds ``parent``; origin/master holds ``master``; one source change on the parent."""
        folder = Path(self._tmp.name) / subdir
        folder.mkdir()
        base_files = dict(manifests_at(parent))
        base_files[".claude/scripts/check_version_bump.py"] = _VBUMP_SCRIPT.read_text(encoding="utf-8")
        cfg = landing_config(steps=[STEP_CLEAN])
        if versionRaise is not None:
            cfg["versionRaise"] = versionRaise
        parent_files = dict(SRC_CHANGE)
        parent_files.update(parent_extra or {})
        kit = Kit(folder, config=cfg, base_files=base_files, parent_files=parent_files)
        if move_master:
            kit.commit_remote("master", manifests_at(master), "master moves")
        st = Stage(self, kit)
        self.isolated = isolated_git_env(folder)
        # Test review W-5: the raise commit is made by a spawned `git commit` that inherits the environment,
        # so the landing runs under a pinned one (identity, signing off, empty global config).
        with mock.patch.dict(os.environ, self.isolated):
            return st, st.run()

    def exact(self, st):
        proc = _REAL_SUBPROCESS_RUN(
            [sys.executable, "-B", str(_VBUMP_SCRIPT), "--exact", "--default-branch", "master"],
            cwd=str(st.worktree), capture_output=True, text=True, env=dict(os.environ, **self.isolated))
        return proc.returncode, (proc.stdout + proc.stderr).strip()

    def test_the_landing_environment_is_isolated_from_the_developers_git_settings(self):
        self.landing(subdir="env-pin")
        env = self.isolated
        self.assertEqual(Path(env["GIT_CONFIG_GLOBAL"]).read_text(encoding="utf-8"), "", "an empty global config")
        self.assertEqual((env["GIT_CONFIG_KEY_0"], env["GIT_CONFIG_VALUE_0"]), ("commit.gpgsign", "false"))
        self.assertTrue(env.get("GIT_AUTHOR_EMAIL") and env.get("GIT_COMMITTER_EMAIL"), "an identity")

    def test_the_landing_commits_one_minor_raise_against_the_default_branch_after_merging_it(self):
        st, report = self.landing()
        self.assertEqual(report["outcome"], "landed", "fixture sanity: %s %s" % (report["outcome"], report["detail"]))
        self.assertEqual(versions_in_tree(st.worktree), ["0.12.0"] * 5,
                         "R-1: the default branch is at 0.11.3, so the landing head carries 0.12.0 (minor + 1, patch 0)")
        code, out = self.exact(st)
        self.assertEqual(code, 0, "and --exact accepts the committed head. got: %s" % out)
        self.assertEqual(git(st.worktree, "status", "--porcelain"), "", "the raise is committed, not left in the tree")

    def test_p7b_runs_even_when_p7_had_nothing_to_merge(self):
        # The parent branch was cut from a master that is already at 0.11.3: M is an ancestor of the head.
        st, report = self.landing(master="0.11.3", parent="0.11.3", move_master=False)
        self.assertEqual(report["outcome"], "landed", "fixture sanity: %s %s" % (report["outcome"], report["detail"]))
        self.assertEqual(versions_in_tree(st.worktree), ["0.12.0"] * 5, "R-2: P7b does not depend on P7 merging")

    def test_positive_control_p7b_is_idempotent_when_the_head_already_carries_the_raise(self):
        st, report = self.landing(master="0.11.3", parent="0.11.3", move_master=False,
                                  parent_extra=manifests_at("0.12.0"))
        self.assertEqual(report["outcome"], "landed", "fixture sanity: %s %s" % (report["outcome"], report["detail"]))
        self.assertEqual(versions_in_tree(st.worktree), ["0.12.0"] * 5, "R-2: never 0.13.0 on a second pass")

    def test_a_raise_that_cannot_be_made_halts_version_raise_failed_and_pushes_nothing(self):
        st, report = self.landing(master="0.11.3", parent="0.11.3", move_master=False,
                                  parent_extra={"plugin.json": "{ this is not json"})
        self.assertEqual(report["outcome"], "version-raise-failed",
                         "an unreadable manifest cannot be raised: %s %s" % (report["outcome"], report["detail"]))
        self.assertEqual(st.count("git_push"), 0, "nothing is pushed after a halt")
        self.assertEqual(st.count("gh_pr_merge"), 0)

    def test_positive_control_without_the_switch_the_manifests_are_not_touched(self):
        for label, value in (("switch absent", None), ("switch off", False)):
            with self.subTest(case=label):
                st, report = self.landing(versionRaise=value, subdir="switch-" + label.replace(" ", "-"))
                self.assertEqual(report["outcome"], "landed", "%s %s" % (report["outcome"], report["detail"]))
                self.assertEqual(versions_in_tree(st.worktree), ["0.11.3"] * 5,
                                 "contractLanding.versionRaise is off: the landing leaves the version alone")


class TestFeedersPassUnfilteredBriefs(StageCase):
    """L-3: the landing's P1 reads the parent brief through the one selector, whatever its contract: field holds."""

    def test_a_parent_brief_whose_contract_field_is_none_does_not_stop_the_landing_at_parent_unresolved(self):
        brief_rel = BRIEF_DIR + "2026-10-05-394-demo.md"
        parent_brief = brief_md(394, branch=PARENT, parent_issue=None).replace(
            "contract: .claude/concepts/%s.md" % SLUG, "contract: none")
        self.assertIn("contract: none", parent_brief, "fixture sanity")
        contract = ("# Demo contract\n\n**Status:** approved\n**Work Item Brief:** %s\n" % brief_rel
                    + CONTRACT_TEXT.split("\n", 1)[1])
        kit = Kit(Path(self._tmp.name), config=landing_config(steps=[STEP_CLEAN]),
                  base_files={".claude/concepts/%s.md" % SLUG: contract},
                  parent_files=dict(SRC_CHANGE, **{brief_rel: parent_brief}))
        report = Stage(self, kit).run()
        self.assertEqual(report["outcome"], "landed",
                         "the contract's header names the parent brief; contract: none is unset, not another "
                         "contract's. got %s: %s" % (report["outcome"], report["detail"]))


# ===========================================================================
# Code review W3 + test review B-2 (mutant M5), landing side: the header brief's branch: is PARENT, and every
# Sub-Task brief says base: feature/q. Neither P0 nor P1 may choose a side in silence.
# ===========================================================================
_DISAGREE_BRIEF = BRIEF_DIR + "2026-10-05-394-demo.md"


def disagreeing_kit(tmp, status="approved", header_branch=None, header_contract=None, brief_base="feature/q",
                    config=None, parent_extra=None):
    """Two mergeable blocks; the header brief is on PARENT (or ``header_branch``) while the Sub-Task briefs
    say ``base: brief_base``. ``header_contract`` rewrites the header brief's contract: value."""
    contract = ("# Demo contract\n\n**Status:** %s\n**Work Item Brief:** %s\n" % (status, _DISAGREE_BRIEF)
                + CONTRACT_TEXT.split("\n", 1)[1])
    kit = Kit(tmp, config=config or landing_config(steps=[STEP_CLEAN]), brief_base=brief_base,
              base_files={".claude/concepts/%s.md" % SLUG: contract},
              parent_files={**SRC_CHANGE, **(parent_extra or {})})
    if header_branch is not None or header_contract is not None:
        text = brief_md(394, branch=header_branch or PARENT, parent_issue=None)
        if header_contract is not None:
            text = text.replace("contract: .claude/concepts/%s.md" % SLUG, "contract: %s" % header_contract)
        write_files(kit.main, {_DISAGREE_BRIEF: text})  # the operator's disk is what P0 reads
    return kit


class TestLauncherHeaderBriefDisagreement(LauncherCase):

    def test_p0_halts_ambiguous_parent_and_starts_no_landing(self):
        kit = disagreeing_kit(self._tmp.name)
        _, execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "ambiguous-parent",
                         "the header brief says %s, the sub-task briefs say feature/q: P0 must name the "
                         "disagreement, not launch a landing of one of them (got %s: %s)"
                         % (PARENT, report.get("outcome"), report.get("detail")))
        execm.assert_not_called()


class TestLandingP0JudgesOnlyJudgedContracts(LauncherCase):
    """Fix review F2. P0's header-brief check is the layout check of /pr-merged, applied to the same contracts:
    R-6 judges Status draft or approved with two or more mergeable blocks, and nobody else."""

    def test_an_exempt_contract_is_not_refused_at_p0_for_a_header_brief_that_differs(self):
        for status in ("implemented", "rejected", "superseded", "archived"):
            with self.subTest(status=status):
                folder = Path(self._tmp.name) / ("exempt-" + status)
                folder.mkdir()
                _, execm, report = self.launch(disagreeing_kit(folder, status=status))
                outcome = report["outcome"] if report else None
                self.assertNotIn(outcome, ("ambiguous-parent", "parent-is-default"),
                                 "R-6: a %s contract is not judged, so the header brief's branch is not compared "
                                 "with the children's base at P0 (got %s: %s)"
                                 % (status, outcome, (report or {}).get("detail")))

    def test_a_judged_contract_whose_header_brief_is_on_the_default_branch_reports_parent_is_default(self):
        folder = Path(self._tmp.name) / "default-header"
        folder.mkdir()
        _, execm, report = self.launch(disagreeing_kit(folder, header_branch="master"))
        self.assertEqual(self.outcome(report), "parent-is-default",
                         "delivery_layout calls this parent-is-default; P0 must use the same reason, not "
                         "ambiguous-parent (got %s: %s)" % (report.get("outcome"), report.get("detail")))
        execm.assert_not_called()

    def test_a_header_brief_whose_contract_field_is_a_placeholder_is_still_the_header_brief(self):
        # The matcher treats tbd / n/a as absent, so the header-linked brief (branch PARENT) still disagrees
        # with the children (feature/q): the landing halts exactly as with a filled-in contract: field.
        for value in ("tbd", "n/a"):
            with self.subTest(contract_field=value):
                folder = Path(self._tmp.name) / ("placeholder-" + value.replace("/", ""))
                folder.mkdir()
                _, execm, report = self.launch(disagreeing_kit(folder, header_contract=value))
                self.assertEqual(self.outcome(report), "ambiguous-parent", report.get("detail"))
                execm.assert_not_called()

    def test_a_parent_branch_landing_whose_contract_cannot_be_read_halts_unverifiable(self):
        # Final review N3: an unreadable contract must not make the header check vanish (zero blocks, no
        # layout, nothing to compare). Here every brief agrees, so only the missing contract can stop it.
        folder = Path(self._tmp.name) / "no-contract"
        folder.mkdir()
        kit = disagreeing_kit(folder, brief_base=PARENT)
        (kit.main / ".claude" / "concepts" / ("%s.md" % SLUG)).unlink()
        _, execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "unverifiable",
                         "P0 cannot judge the layout of a contract it cannot read (got %s: %s)"
                         % (report.get("outcome"), report.get("detail")))
        execm.assert_not_called()

    def test_the_remedy_for_a_missing_contract_is_to_restore_it_not_to_retry(self):
        # Final review N-4 / contract note: the default `unverifiable` remedy ("make the read succeed ... and
        # rerun") reads as a retry, and a retry cannot bring a missing file back.
        folder = Path(self._tmp.name) / "no-contract-remedy"
        folder.mkdir()
        kit = disagreeing_kit(folder, brief_base=PARENT)
        (kit.main / ".claude" / "concepts" / ("%s.md" % SLUG)).unlink()
        _, _execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "unverifiable", report.get("detail"))
        remedy = report.get("remedy") or ""
        self.assertTrue("restore" in remedy and (".claude/concepts/%s.md" % SLUG) in remedy
                        and "parent branch" in remedy,
                        "the remedy: restore .claude/concepts/<slug>.md on the parent branch, then rerun. got %r" % remedy)
        self.assertNotIn("network", remedy)

    def test_p0_delegates_the_check_to_the_one_layout_function(self):
        text = (Path(__file__).resolve().parent.parent / "land_contract.py").read_text(encoding="utf-8")
        start = text.index("def _launch_land(")
        end = text.index("\ndef ", start + 10)
        self.assertTrue("delivery_layout(" in text[start:end],
                        "P0 (_launch_land) asks pr_merged.delivery_layout, so the status gate, the reason "
                        "vocabulary and the placeholder rule exist once")

    def test_a_malformed_protected_branches_value_is_not_split_into_characters(self):
        # NIT 4: protectedBranches: "release" (a string) must read as the default only. Split into characters
        # it would make a branch called "e" protected. The contract has no Status, so only the topology check runs.
        folder = Path(self._tmp.name) / "malformed"
        folder.mkdir()
        kit = Kit(folder, config=landing_config(protectedBranches="release"), brief_base="e")
        _, execm, report = self.launch(kit)
        self.assertNotEqual(self.outcome(report), "parent-is-default",
                            "'e' is not a protected branch: the string is not a list of characters (got %s: %s)"
                            % (report.get("outcome"), report.get("detail")))


class TestLandingNeverReadsARecordVerdict(StageCase):
    """R-9 (amended 2026-10-30): the landing relies on its own checks and never on a record's verdict, because a
    record has none. It repeats R-8's layout warning in the Landing Report and does not halt on it."""

    WARNING = "single-branch-delivery"

    def land(self, name, **record):
        folder = Path(self._tmp.name) / name
        folder.mkdir()
        extra = {REC_DIR + "t1-backend.yaml": record_yaml(**record)} if record else None
        st = Stage(self, disagreeing_kit(folder, brief_base=PARENT, parent_extra=extra))
        return st.run()

    def reasons(self, report):
        return [w.get("reason") if isinstance(w, dict) else w for w in report.get("layout_warnings") or []]

    def test_a_record_merged_into_the_default_branch_is_landed_and_the_report_repeats_the_warning(self):
        report = self.land("on-default", base_ref="master", base_is_default=True)
        self.assertEqual(report["outcome"], "landed", "the landing does not halt on it: %s: %s"
                         % (report["outcome"], report["detail"]))
        self.assertIn(self.WARNING, self.reasons(report), "the Landing Report repeats the warning (R-9)")

    def test_records_on_the_parent_branch_give_an_empty_warning_list(self):
        report = self.land("on-parent", base_ref=PARENT, base_is_default=False)
        self.assertEqual(report["outcome"], "landed", report["detail"])
        self.assertEqual(report.get("layout_warnings"), [], "the key is present and empty")

    def test_a_hand_made_layout_or_failure_field_is_never_read(self):
        report = self.land("verdict-fields", base_ref=PARENT, base_is_default=False,
                           layout="single-branch-accepted", failure="single-branch-delivery")
        self.assertEqual(report["outcome"], "landed", "no record carries a verdict, so none is read: %s"
                         % report["detail"])

    def test_the_landing_script_reads_no_accepted_blocks_and_no_record_layout(self):
        text = (Path(__file__).resolve().parent.parent / "land_contract.py").read_text(encoding="utf-8")
        for token in ("accepted_blocks", "single-branch-accepted"):
            self.assertFalse(token in text, "land_contract.py must not mention %s" % token)
        self.assertIsNone(re.search(r"""\.get\(\s*["']layout["']|\[\s*["']layout["']\s*\]""", text),
                          "and reads no `layout` field of a record")


class TestLandingReportWarningForms(StageCase):
    """R-9 (amended): the Landing Report repeats layout_warnings in the same forms as --status: absent for an
    unjudged contract, [] when judged and every read succeeded, `unverifiable` when the listing failed. The
    landing never halts on a warning."""

    def run_landing(self, name, kit_factory, **run_kwargs):
        folder = Path(self._tmp.name) / name
        folder.mkdir()
        st = Stage(self, kit_factory(folder))
        return st, st.run(**run_kwargs)

    def test_the_key_is_absent_for_an_unjudged_contract(self):
        # The default Kit contract has no Status, so it is not judged (R-6).
        _st, report = self.run_landing(
            "unjudged", lambda folder: Kit(folder, config=landing_config(steps=[STEP_CLEAN]),
                                           parent_files=dict(SRC_CHANGE)))
        self.assertEqual(report["outcome"], "landed", report["detail"])
        self.assertNotIn("layout_warnings", report, "absent, never [] (W1)")

    def test_the_key_is_absent_for_an_implemented_contract(self):
        _st, report = self.run_landing("implemented",
                                       lambda folder: disagreeing_kit(folder, status="implemented", brief_base=PARENT))
        self.assertEqual(report["outcome"], "landed", report["detail"])
        self.assertNotIn("layout_warnings", report)

    def test_a_failed_origin_listing_is_unverifiable_and_the_landing_still_lands(self):
        import land_contract as lc_module
        real = lc_module._git

        def failing(cwd, *args, **kwargs):
            if args and args[0] == "ls-tree" and "origin/master" in args:
                return 128, "fatal: unable to read tree"
            return real(cwd, *args, **kwargs)

        _st, report = self.run_landing(
            "listing-fails", lambda folder: disagreeing_kit(folder, brief_base=PARENT),
            extra_patches=[mock.patch.object(lc_module, "_git", failing)])
        self.assertEqual(report["outcome"], "landed", "the landing does not halt on it: %s" % report["detail"])
        reasons = [w.get("reason") if isinstance(w, dict) else w for w in report.get("layout_warnings") or []]
        self.assertEqual(reasons, ["unverifiable"],
                         "a failed listing is unverifiable, not []. got %r" % (report.get("layout_warnings"),))


class TestStageHeaderBriefDisagreement(StageCase):

    def test_p1_never_lands_whichever_parent_the_launcher_passes(self):
        # P1 already halts today (topology versus the passed parent); this pins it as a regression guard.
        for parent in (PARENT, "feature/q"):
            with self.subTest(parent=parent):
                folder = Path(self._tmp.name) / ("p1-" + parent.replace("/", "-"))
                folder.mkdir()
                st = Stage(self, disagreeing_kit(folder))
                report = st.run(parent=parent)
                self.assertIn(report["outcome"], ("ambiguous-parent", "parent-unresolved"),
                              "no silent choice between %s and feature/q. got %s: %s"
                              % (PARENT, report["outcome"], report["detail"]))
                self.assertEqual(st.count("git_push"), 0, "nothing is pushed")
                self.assertEqual(st.count("gh_pr_merge"), 0, "and nothing is merged")


if __name__ == "__main__":
    unittest.main(verbosity=2)
