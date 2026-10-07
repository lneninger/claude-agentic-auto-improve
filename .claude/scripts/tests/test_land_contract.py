#!/usr/bin/env python3
"""
Tests for land_contract.py -- the Contract Landing script (contract 2026-10-05, issue 394).

RED-phase file written BEFORE the script exists. ``land_contract`` is loaded through a
guarded import that yields ``None`` when the module is absent, and every test asserts the
module is present first and then looks each symbol up with ``getattr`` (the ``_fn`` pattern
of test_pr_merged.py). A missing module or symbol is therefore an AssertionError naming it,
never an ImportError, a NameError or an AttributeError.

The contract leaves function signatures open. THIS FILE PINS THE SIGNATURES the
implementer must meet; each pinned shape is stated where it is first used and
collected here:

  Pure functions
    parse_trx(text), parse_vitest_json(text), parse_unittest_text(text)
        -> list of {"unit", "name", "outcome": passed|failed|skipped, "message"}, or None
           when the text is empty or unparseable
    read_step(step, run, baseline, emulators=()) -> dict
        run = {"launched", "exit_code", "timed_out", "log_text", "results_text"}
        result keys: reading (ok|environment|regression), new_failures, failed_tests,
        baseline_now_passing, executed_count, environment_reason. Test ids are
        "<suite>::<class or spec file>::<test name>"; unit ids are "<suite>::<class or file>".
    merge_recording(runs) -> {"known_failing": {unit: [names]}, "known_flaky": [units]}
    classify_conflict(path, config) -> union | regenerate | halt
    merge_union(base, ours, theirs, entry_key) -> {"ok", "text", "reason"}
    evaluate_children(child_ids, read) -> {"outcome": None | children-still-open | unverifiable}
    evaluate_gates(facts) -> first halt outcome string, or None.  SCOPE: P3 to P14 only. The
        halts of P0 to P2 are decided where their facts arise (launcher, identify, environment)
        and are tested at launcher and stage level. Facts are booleans keyed "p<N>_<outcome with
        underscores>" (phase-specific, because environment-failure, unverifiable and
        children-still-open occur in several phases), plus "p8_verification_verdict" =
        READY | NOT-READY | ENVIRONMENT. See GATE_FACTS below for the full ordered list.
    roll_up_verdict(step_readings) -> READY | NOT-READY | ENVIRONMENT
        step_readings = the dicts read_step returns for the applicable steps. Any regression ->
        NOT-READY (environment steps listed too); else any environment -> ENVIRONMENT; else (or no
        step at all) READY.
    run_step(step, emulators, baseline, results_dir, cwd) -> the read_step dict
    run_recording(config, cwd, results_dir, out_path, commit) -> {"outcome": ...}
    applicable_steps(steps, contract_diff, merge_diff) -> [step ids]
    required_coverage(rows, contract_diff, resolved_paths) -> [reviewer names]
    check_configuration(config, worktree, results_dir) -> None | {"outcome": landing-not-configured}
    build_delivery_set(listings, slug) -> {"records", "briefs", "problem"}
    plan_worktree(worktree_paths, parent_issue, main_root, today) -> {"path", "create"} or
        {"outcome": "environment-failure", "detail"}
    next_command_for_outcome(outcome, slug, **facts) -> {"commands", "reason", ...}
    scan_text(text) -> patterns found; scan_tree(root) -> [(relative path, pattern)],
        ValueError when zero files were scanned. scan_tree WALKS THE FILE SYSTEM (it must not
        shell out to git: the subprocess guard below refuses any git run inside this checkout).
        Pinned pattern names: "gh-pr-merge" (pattern one, admitted for the exact path
        .claude/scripts/land_contract.py only, never by basename) and "git-push-protected";
        the others (gh api pulls/../merge, argv lists) are only pinned by "found or not".
    resolve_roots(path) -> {"main_root", "landing_root", "logs_dir", "state_dir"}
    LANDING_OUTCOMES (closed set)
  Edges (tests patch ONLY these names)
    _run(cmd, cwd=None) -> (rc, out)               _run_long(cmd, timeout, log_path, cwd) -> (rc, timed_out)
    tcp_probe(host, port, timeout) -> bool          exec_stage(argv, cwd=None) -> int
    git_show(ref, path, cwd=None) -> str | None     git_ls_remote(ref, cwd=None) -> sha | None
    git_push(parent, cwd, default_branch, protected) -> (rc, out)
    gh_pr_create(base, head, title, body, cwd=None) -> (rc, url)
    gh_pr_ready(number, cwd=None) -> (rc, out)      gh_pr_merge(number, head_sha, cwd=None) -> (rc, out)
    gh_pr_edit_body(number, body, cwd=None) -> (rc, out)
    gh_pr_find(head, base=None, cwd=None) -> dict | None
    gh_auth_status(cwd=None) -> bool   (P2: unauthenticated gh -> halt "unverifiable")
    probe_stage(path) -> bool          (P0: True when the script at path accepts "--stage land";
        a SEPARATE edge, so exec_stage is called exactly once per launch, for the landing itself,
        and no test needs a source-text grep)
    git_merge(...), git_commit(...)    (real git in the tests; wrapped by the stage tests to count)
    gh_pr_view(number, cwd=None) -> dict            gh_issue_state(number, cwd=None) -> str
    read_children(parent_issue, cwd=None) -> {"nodes", "totalCount"} | None
    verify_closing_link(brief_path, pr_number, cwd=None) -> verdict string
    write_bookkeeping(checkout, parent_brief, pr, report) -> None
    worktree_remove(path) -> None (raises on failure)   worktree_reset(path, main_root, slug)
  Orchestration
    run_landing(args) -> Landing Report dict, args = {"contract", "parent", "project_root",
        "checkout", "run_id", "worktree", "dry_run"}
    main(argv) -> int   (the launcher; P0). The launcher's "operator checkout" is the git
        toplevel of its working directory; the launcher tests chdir into the temporary operator
        checkout, so that is what they exercise.
    main(["--contract", slug, "--status", "--json"]) prints ONE JSON object whose "state" is
        live | interrupted (stale lock, no report) | report (last report, key "report") | none.
        It mutates nothing. main([... "--dry-run"]) forwards "--dry-run" to the landing stage,
        which stops after P5 (no setup, merge, step, push, pull request).

Git behaviour is exercised in temporary repositories this file builds; nothing here touches
the checkout it lives in. The module guard (setUpModule) enforces that structurally: it
wraps subprocess.Popen (so run, call and check_output are covered), os.system and os.popen,
and (1) refuses gh pr merge/create/edit/ready and git push anywhere in an argv after global
options (git -C x / -c k=v, gh -R o/r), through shell strings and cmd /c, sh -c wrappers; a git
push passes only when its effective directory is under the temporary root and (2) refuses ANY git
run whose explicit or inherited working directory resolves inside this checkout. The module's
working directory is a temporary sandbox for the same reason. The guard identifies git and gh by
the BASENAME of each word (full Windows paths, any case of .EXE, quoted or not), reads
``--git-dir`` / ``--work-tree`` (``--opt v`` and ``--opt=v``) as directories git acts in, also
refuses ``gh issue close`` and ``gh api -X PUT .../pulls/<n>/merge``, and is installed at module
top BEFORE ``import land_contract`` (so a ``from subprocess import Popen`` keeps the guarded
class). setUpModule also points GH_CONFIG_DIR at an empty temporary directory and removes
GH_TOKEN, GITHUB_TOKEN, GH_ENTERPRISE_TOKEN and GH_REPO, so any real gh call is unauthenticated.

COMPLETE LIST of what the tests require of land_contract (sub-task 2's one authoritative list;
signatures above are repeated here only where a return shape needs more than one line)
  Constants
    LANDING_OUTCOMES   a closed collection (set/tuple/frozenset) of outcome strings; every outcome
                       any function below returns, writes to a report or maps to a Next Command is a
                       member (TestLandingOutcomeSet)
    GATE_FACTS         NOT exported: it is a test-side tuple that mirrors the facts evaluate_gates
                       reads. The module reads exactly those keys, in that order (see the tuple)
  Pure functions (no edge, no clock)
    parse_trx(text) / parse_vitest_json(text) / parse_unittest_text(text) -> [result dicts] | None
    read_step(step, run, baseline, emulators=()) -> {"reading", "new_failures", "failed_tests",
        "baseline_now_passing", "executed_count", "environment_reason"}
    merge_recording(runs) -> {"known_failing", "known_flaky"}
    classify_conflict(path, config) -> "union" | "regenerate" | "halt"
    merge_union(base, ours, theirs, entry_key) -> {"ok", "text", "reason"}
    evaluate_children(child_ids, read) -> {"outcome": None | "children-still-open" | "unverifiable"}
    evaluate_gates(facts) -> first halt outcome (P3-P14) | None
    roll_up_verdict(step_readings) -> "READY" | "NOT-READY" | "ENVIRONMENT"
    applicable_steps(steps, contract_diff, merge_diff) -> [step ids]
    required_coverage(rows, contract_diff, resolved_paths) -> [reviewer names]
    check_configuration(config, worktree, results_dir) -> None | {"outcome": "landing-not-configured"}
    build_delivery_set(listings, slug) -> {"records", "briefs", "problem"}
    plan_worktree(worktree_paths, parent_issue, main_root, today) -> {"path", "create"} | halt dict
    next_command_for_outcome(outcome, slug, **facts) -> {"commands", "reason", ...}
    scan_text(text) -> [pattern names]; scan_tree(root) -> [(relative path, pattern)] (walks the
        file system, ValueError when it scanned zero files)
    resolve_roots(path) -> {"main_root", "landing_root", "logs_dir", "state_dir"}
  Steps that call edges (run with every edge patched)
    run_step(step, emulators, baseline, results_dir, cwd) -> the read_step dict
    run_recording(config, cwd, results_dir, out_path, commit) -> {"outcome": ...}
    worktree_reset(path, main_root, slug) (refusal cases)
  Orchestration
    run_landing(args) -> Landing Report dict (keys run_id, contract, outcome, gate, detail, remedy,
        next_command, plus "notes" list); main(argv) -> int (launcher P0, exit 8 for a set GH_REPO)
  Edges (the only names tests patch on the module; each must exist and be called by these names)
    _run, _run_long, tcp_probe, exec_stage, probe_stage, git_show, git_ls_remote, git_push,
    git_merge, git_commit, gh_pr_create, gh_pr_ready, gh_pr_merge, gh_pr_edit_body, gh_pr_find,
    gh_pr_view, gh_issue_state, gh_auth_status, read_children, verify_closing_link,
    write_bookkeeping, worktree_remove -- signatures in the Edges block above;
    gh_pr_view(number, cwd=None) -> {"number", "state", "isDraft", "baseRefName", "headRefName",
    "headRefOid", "mergeCommit": {"oid"}}; gh_pr_find returns the same shape or None
  Other modules
    pr_merged.declared_topology(contract_id, briefs, default_branch, protected): NEW in pr_merged,
        not tested here; run_landing and the launcher call it on the briefs (L-13) and the stage
        tests assert only its effect (ambiguous-parent, parent-is-default, topology mismatch).
    pr_merged.IMPLEMENTER_AGENTS and REVIEW_GATES: patched by the launcher tests; read, not changed.

Run: py -3 .claude/scripts/tests/test_land_contract.py
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


# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Result-file fixtures (literal formats the parsers must read)
# ---------------------------------------------------------------------------
def make_trx(results):
    """results: [(class, test name, outcome, message)] -> a TRX document."""
    res, defs = [], []
    for i, (cls, name, outcome, message) in enumerate(results):
        tid = "id-%d" % i
        body = ""
        if message:
            body = "<Output><ErrorInfo><Message>%s</Message></ErrorInfo></Output>" % message
        res.append('<UnitTestResult testId="%s" testName="%s" outcome="%s">%s</UnitTestResult>'
                   % (tid, name, outcome, body))
        defs.append('<UnitTest name="%s" id="%s"><TestMethod className="%s" name="%s" />'
                    "</UnitTest>" % (name, tid, cls, name))
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<TestRun id="r" xmlns="http://microsoft.com/schemas/VisualStudio/TeamTest/2010">'
            "<Results>%s</Results><TestDefinitions>%s</TestDefinitions></TestRun>"
            % ("".join(res), "".join(defs)))


def make_vitest(files):
    """files: {spec file: [(test name, status, message)]} -> vitest JSON reporter output."""
    return json.dumps({"testResults": [
        {"name": spec, "assertionResults": [
            {"fullName": n, "status": s, "failureMessages": [m] if m else []}
            for (n, s, m) in tests]}
        for spec, tests in files.items()]})


def make_unittest(lines):
    """lines: [(test, 'module.Class.test', result)] -> unittest -v output."""
    out = ["%s (%s) ... %s" % (t, dotted, r) for (t, dotted, r) in lines]
    out.append("")
    out.append("=" * 70)
    for (t, dotted, r) in lines:
        if r in ("FAIL", "ERROR"):
            out += ["%s: %s (%s)" % (r, t, dotted), "-" * 70,
                    "Traceback (most recent call last):", "AssertionError: nope", ""]
    out.append("Ran %d tests" % len(lines))
    return "\n".join(out) + "\n"


SUITE = "services"


def unit_id(cls):
    return "%s::%s" % (SUITE, cls)


def tail(test_id):
    return test_id.rsplit("::", 1)[-1]


def tails(ids):
    return sorted(tail(i) for i in ids)


EMU_AZURITE = {"id": "azurite", "host": "127.0.0.1", "port": 10000,
               "gates_steps": ["dotnet-unit"],
               "signatures": ["Could not reach an Azurite blob emulator"],
               "start_hint": "start the azurite container"}
EMU_GCS = {"id": "fake-gcs", "host": "127.0.0.1", "port": 4443,
           "gates_steps": ["dotnet-unit"],
           "signatures": ["Could not reach a fake-gcs-server emulator at"],
           "start_hint": "start the fake-gcs container"}
AZ_MSG = "Could not reach an Azurite blob emulator at 127.0.0.1:10000"
GCS_MSG = "Could not reach a fake-gcs-server emulator at 'http://localhost:4443/storage/v1/'"


def dotnet_step(**over):
    step = {"id": "dotnet-unit", "suite": SUITE, "when_paths": ["**"],
            "command": ["dotnet", "test", "--logger", "trx;LogFileName={results_dir}/r.trx"],
            "results": {"format": "trx", "path": "{results_dir}/r.trx"},
            "timeout_minutes": 5, "environment_signatures": []}
    step.update(over)
    return step


def run_ok(results_text, exit_code=0, **over):
    run = {"launched": True, "exit_code": exit_code, "timed_out": False,
           "log_text": "", "results_text": results_text}
    run.update(over)
    return run


def baseline_for(known_failing=None, known_flaky=None):
    return {SUITE: {"measured_on": "master", "measured_at_commit": sha40("0"), "runs": 2,
                    "known_failing": known_failing or {}, "known_flaky": known_flaky or [],
                    "note": "fixture"}}


# ===========================================================================
# (d) Parsers
# ===========================================================================
class TestParsers(LandCase):

    def test_trx_yields_class_name_outcome_and_message(self):
        parse = self.fn("parse_trx")
        got = parse(make_trx([("Acme.AlphaTests", "Passes", "Passed", ""),
                              ("Acme.BetaTests", "Fails", "Failed", "boom"),
                              ("Acme.BetaTests", "Skips", "NotExecuted", "")]))
        self.assertIsNotNone(got, "a well-formed TRX must parse")
        rows = {(r["unit"], r["name"], r["outcome"]) for r in got}
        self.assertEqual(
            rows,
            {("Acme.AlphaTests", "Passes", "passed"), ("Acme.BetaTests", "Fails", "failed"),
             ("Acme.BetaTests", "Skips", "skipped")},
            "each result carries its class (from TestDefinitions), its name and a normalised "
            "outcome; NotExecuted reads as skipped")
        failed = [r for r in got if r["outcome"] == "failed"][0]
        self.assertIn("boom", failed["message"], "the failure message is kept for signature matching")

    def test_trx_empty_or_broken_text_is_none_never_zero_failures(self):
        parse = self.fn("parse_trx")
        self.assertIsNone(parse(""), "an empty result file is unparseable, not 'no failures'")
        self.assertIsNone(parse("<TestRun"), "broken XML is unparseable, not 'no failures'")

    def test_vitest_json_yields_spec_file_name_outcome_and_message(self):
        parse = self.fn("parse_vitest_json")
        got = parse(make_vitest({"src/a.spec.ts": [("adds", "passed", ""),
                                                   ("breaks", "failed", "expected 1")],
                                 "src/b.spec.ts": [("pends", "pending", "")]}))
        self.assertIsNotNone(got, "a well-formed vitest JSON report must parse")
        rows = {(r["unit"], r["name"], r["outcome"]) for r in got}
        self.assertEqual(
            rows,
            {("src/a.spec.ts", "adds", "passed"), ("src/a.spec.ts", "breaks", "failed"),
             ("src/b.spec.ts", "pends", "skipped")},
            "the unit of a vitest result is its spec file; pending reads as skipped")
        self.assertIn("expected 1", [r for r in got if r["name"] == "breaks"][0]["message"],
                      "failure messages are kept")

    def test_vitest_json_empty_or_broken_text_is_none(self):
        parse = self.fn("parse_vitest_json")
        self.assertIsNone(parse(""), "empty report is unparseable")
        self.assertIsNone(parse("{not json"), "broken JSON is unparseable")

    def test_unittest_text_yields_class_name_and_outcome(self):
        parse = self.fn("parse_unittest_text")
        got = parse(make_unittest([("test_ok", "tests.Foo.test_ok", "ok"),
                                   ("test_bad", "tests.Foo.test_bad", "FAIL"),
                                   ("test_err", "tests.Bar.test_err", "ERROR"),
                                   ("test_skip", "tests.Bar.test_skip", "skipped 'why'")]))
        self.assertIsNotNone(got, "verbose unittest output must parse")
        rows = {(r["unit"], r["name"], r["outcome"]) for r in got}
        self.assertEqual(
            rows,
            {("tests.Foo", "test_ok", "passed"), ("tests.Foo", "test_bad", "failed"),
             ("tests.Bar", "test_err", "failed"), ("tests.Bar", "test_skip", "skipped")},
            "ERROR counts as failed; the unit is the dotted class")

    def test_unittest_text_with_no_test_lines_is_none(self):
        parse = self.fn("parse_unittest_text")
        self.assertIsNone(parse(""), "empty output is unparseable")


# ===========================================================================
# (d) Environment versus regression readings
# ===========================================================================
class TestReadStepEnvironmentReadings(LandCase):

    def read(self, run, step=None, baseline=None, emulators=()):
        return self.fn("read_step")(step or dotnet_step(), run, baseline or {}, emulators)

    def test_positive_control_clean_results_read_ok(self):
        r = self.read(run_ok(make_trx([("Acme.AlphaTests", "Passes", "Passed", "")])))
        self.assertEqual(r["reading"], "ok", "every test passed and exit was zero")
        self.assertGreater(r["executed_count"], 0, "the executed count is reported")

    def test_missing_result_file_is_environment(self):
        r = self.read(run_ok(None, exit_code=1))
        self.assertEqual(r["reading"], "environment",
                         "a missing result file is an environment reading, never zero failures")

    def test_empty_result_file_is_environment(self):
        r = self.read(run_ok("", exit_code=1))
        self.assertEqual(r["reading"], "environment", "an unparseable result file is environment")

    def test_executed_count_zero_is_environment(self):
        r = self.read(run_ok(make_trx([("Acme.AlphaTests", "Skips", "NotExecuted", "")])))
        self.assertEqual(r["reading"], "environment",
                         "a test step that executed nothing must not read as passing")

    def test_non_zero_exit_with_zero_parsed_failures_is_environment(self):
        r = self.read(run_ok(make_trx([("Acme.AlphaTests", "Passes", "Passed", "")]), exit_code=1))
        self.assertEqual(r["reading"], "environment",
                         "exit non-zero that parsed failures cannot account for is environment")

    def test_timeout_is_environment_even_with_a_valid_passing_result_file(self):
        passing = make_trx([("Acme.AlphaTests", "Passes", "Passed", "")])
        r = self.read(run_ok(passing, exit_code=0, timed_out=True))
        self.assertEqual(r["reading"], "environment",
                         "timed_out is the only abnormal fact (the results parse and pass), so a "
                         "timed-out step reads environment because it timed out")
        control = self.read(run_ok(passing, exit_code=0))
        self.assertEqual(control["reading"], "ok",
                         "positive control: the same results without the timeout read ok")

    def test_log_matching_an_environment_signature_is_environment(self):
        step = dotnet_step(environment_signatures=["MSB3027"])
        passing = make_trx([("Acme.AlphaTests", "Passes", "Passed", "")])
        r = self.read(run_ok(passing, exit_code=0,
                             log_text="error MSB3027: could not copy, file is locked"), step=step)
        self.assertEqual(r["reading"], "environment",
                         "exit 0 and passing results, so the log signature is the only abnormal "
                         "fact: a log line matching environment_signatures is environment")
        control = self.read(run_ok(passing, exit_code=0, log_text="all quiet"), step=step)
        self.assertEqual(control["reading"], "ok", "positive control: no signature in the log reads ok")

    def test_exit_code_step_failure_with_a_signature_is_environment(self):
        step = {"id": "compile", "suite": "build", "results": {"format": "exit-code"},
                "environment_signatures": ["MSB3027"]}
        r = self.read(run_ok(None, exit_code=1, log_text="MSB3027 locked"), step=step)
        self.assertEqual(r["reading"], "environment",
                         "a build failure whose log carries an environment signature is environment")


class TestReadStepRegressionReadings(LandCase):

    def read(self, run, step=None, baseline=None, emulators=()):
        return self.fn("read_step")(step or dotnet_step(), run, baseline or {}, emulators)

    def test_positive_control_a_recorded_failing_test_still_failing_is_tolerated(self):
        base = baseline_for(known_failing={unit_id("Acme.AlphaTests"): ["OldFail"]})
        r = self.read(run_ok(make_trx([("Acme.AlphaTests", "OldFail", "Failed", "x"),
                                       ("Acme.AlphaTests", "Fine", "Passed", "")]), exit_code=1),
                      baseline=base)
        self.assertEqual(r["reading"], "ok", "a failure recorded in known_failing is tolerated")
        self.assertEqual(r["new_failures"], [], "and it is not new")

    def test_a_new_test_name_inside_a_known_failing_unit_is_new(self):
        base = baseline_for(known_failing={unit_id("Acme.AlphaTests"): ["OldFail"]})
        r = self.read(run_ok(make_trx([("Acme.AlphaTests", "OldFail", "Failed", "x"),
                                       ("Acme.AlphaTests", "NewFail", "Failed", "y")]), exit_code=1),
                      baseline=base)
        self.assertEqual(r["reading"], "regression",
                         "L-8: known-failing tolerates the NAMES recorded, so a new name is new")
        self.assertEqual(tails(r["new_failures"]), ["NewFail"], "only the new name is reported")

    def test_a_unit_in_neither_list_is_new(self):
        base = baseline_for(known_failing={unit_id("Acme.AlphaTests"): ["OldFail"]},
                            known_flaky=[unit_id("Acme.FlakyTests")])
        r = self.read(run_ok(make_trx([("Acme.OtherTests", "Boom", "Failed", "z")]), exit_code=1),
                      baseline=base)
        self.assertEqual(r["reading"], "regression", "a unit in neither list is a regression")
        self.assertEqual(tails(r["new_failures"]), ["Boom"], "the failure is named")

    def test_a_build_failure_with_no_signature_is_regression(self):
        step = {"id": "compile", "suite": "build", "results": {"format": "exit-code"},
                "environment_signatures": ["MSB3027"]}
        r = self.read(run_ok(None, exit_code=1, log_text="error CS1002: ; expected"), step=step)
        self.assertEqual(r["reading"], "regression",
                         "a build or exit-code failure with no environment signature is regression")

    def test_positive_control_an_exit_code_step_that_exits_zero_is_ok(self):
        step = {"id": "compile", "suite": "build", "results": {"format": "exit-code"},
                "environment_signatures": []}
        r = self.read(run_ok(None, exit_code=0), step=step)
        self.assertEqual(r["reading"], "ok", "a clean exit-code step reads ok")

    def test_a_known_flaky_unit_is_tolerated_whole(self):
        base = baseline_for(known_flaky=[unit_id("Acme.FlakyTests")])
        r = self.read(run_ok(make_trx([("Acme.FlakyTests", "AnyName", "Failed", "x"),
                                       ("Acme.FlakyTests", "Another", "Failed", "x")]), exit_code=1),
                      baseline=base)
        self.assertEqual(r["reading"], "ok", "a known-flaky unit is tolerated whole")
        self.assertEqual(r["new_failures"], [], "no failure inside it is new")

    def test_a_baseline_test_that_now_passes_is_reported_not_acted_on(self):
        base = baseline_for(known_failing={unit_id("Acme.AlphaTests"): ["OldFail"]})
        r = self.read(run_ok(make_trx([("Acme.AlphaTests", "OldFail", "Passed", "")])), baseline=base)
        self.assertEqual(r["reading"], "ok", "a now-passing baseline test never blocks")
        self.assertEqual(tails(r["baseline_now_passing"]), ["OldFail"], "but it is reported")


class TestReadStepEmulatorSignatures(LandCase):
    """L-7b: a failure that carries an emulator signature is environment, never new."""

    def read(self, results, baseline=None):
        return self.fn("read_step")(dotnet_step(), run_ok(make_trx(results), exit_code=1),
                                    baseline or {}, [EMU_AZURITE, EMU_GCS])

    def test_an_azurite_signature_failure_is_environment_even_with_an_empty_baseline(self):
        r = self.read([("Acme.StorageTests", "Uploads", "Failed", AZ_MSG)])
        self.assertEqual(r["reading"], "environment",
                         "a failure whose message holds the Azurite signature is environment")
        self.assertEqual(r["new_failures"], [], "and it is not a new failure")

    def test_a_fake_gcs_signature_failure_is_environment_even_with_an_empty_baseline(self):
        r = self.read([("Acme.StorageTests", "Downloads", "Failed", GCS_MSG)])
        self.assertEqual(r["reading"], "environment",
                         "a failure whose message holds the fake-gcs signature is environment")
        self.assertEqual(r["new_failures"], [], "and it is not a new failure")

    def test_a_signature_failure_is_environment_whatever_the_baseline_says(self):
        base = baseline_for(known_failing={unit_id("Acme.StorageTests"): ["Uploads"]})
        r = self.read([("Acme.StorageTests", "Uploads", "Failed", AZ_MSG)], baseline=base)
        self.assertEqual(r["reading"], "environment",
                         "a baseline can never turn an emulator outage into 'known failing'")

    def test_a_mixed_step_one_signature_one_unrelated_is_regression(self):
        r = self.read([("Acme.StorageTests", "Uploads", "Failed", AZ_MSG),
                       ("Acme.OrderTests", "Totals", "Failed", "expected 3 but was 4")])
        self.assertEqual(r["reading"], "regression",
                         "an unrelated new failure survives the signature filter")
        self.assertEqual(tails(r["new_failures"]), ["Totals"],
                         "only the unrelated failure is new; the signature one is removed")

    def test_positive_control_the_same_unrelated_failure_alone_is_regression(self):
        r = self.read([("Acme.OrderTests", "Totals", "Failed", "expected 3 but was 4")])
        self.assertEqual(r["reading"], "regression", "the unrelated failure alone is a regression")
        self.assertEqual(tails(r["new_failures"]), ["Totals"], "and it is named")


class TestRunStepEmulatorPreflight(LandCase):
    """The pre-flight probe decides before anything launches."""

    def run_step(self, probe_result, trx_text=None, results_dir=None):
        lc = self.mod()
        calls = []

        def fake_long(cmd, timeout=None, log_path=None, cwd=None, *a, **k):
            calls.append([str(c) for c in cmd])
            for c in cmd:
                if str(c).endswith(".trx") and trx_text is not None:
                    p = Path(str(c).split("=")[-1])
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(trx_text, encoding="utf-8")
            return (0, False)

        with tempfile.TemporaryDirectory() as d:
            rdir = Path(results_dir or d)
            with mock.patch.object(lc, "tcp_probe", return_value=probe_result) as probe, \
                 mock.patch.object(lc, "_run_long", side_effect=fake_long) as long_:
                result = self.fn("run_step")(dotnet_step(), emulators=[EMU_AZURITE],
                                             baseline={}, results_dir=rdir, cwd=d)
            return result, long_, probe, calls, rdir

    def test_an_unreachable_emulator_means_the_step_never_launches(self):
        self.mod()
        self.fn("tcp_probe")
        result, long_, probe, _, _ = self.run_step(False)
        long_.assert_not_called()
        self.assertEqual(result["reading"], "environment",
                         "an unreachable emulator reads environment (L-7b)")
        reason = str(result.get("environment_reason", "")).lower()
        self.assertIn("emulator-unreachable", reason, "the reason names the pre-flight failure")
        self.assertIn("azurite", reason, "and the emulator that was unreachable")
        self.assertTrue(probe.called, "the emulator was probed")

    def test_positive_control_a_reachable_emulator_lets_the_step_launch(self):
        self.fn("tcp_probe")
        trx = make_trx([("Acme.AlphaTests", "Passes", "Passed", "")])
        result, long_, _, _, _ = self.run_step(True, trx_text=trx)
        self.assertEqual(long_.call_count, 1, "a reachable emulator must not block the launch")
        self.assertEqual(result["reading"], "ok", "and the clean results read ok")

    def test_results_dir_is_substituted_into_the_command_and_the_results_path(self):
        self.fn("tcp_probe")
        trx = make_trx([("Acme.AlphaTests", "Passes", "Passed", "")])
        result, _, _, calls, rdir = self.run_step(True, trx_text=trx)
        joined = " ".join(calls[0])
        self.assertNotIn("{results_dir}", joined, "the placeholder must be substituted in the command")
        self.assertIn(str(rdir), joined, "the command points into the results directory")
        self.assertEqual(result["reading"], "ok",
                         "the result file read back is the one under the substituted path")


# ===========================================================================
# (d) Two-run recording
# ===========================================================================
class TestMergeRecording(LandCase):

    def test_a_test_failing_in_both_runs_is_known_failing_with_its_name(self):
        out = self.fn("merge_recording")([[{"unit": "svc::A", "name": "t1"}],
                                          [{"unit": "svc::A", "name": "t1"}]])
        self.assertEqual(out["known_failing"], {"svc::A": ["t1"]},
                         "both runs failing: known_failing keeps the unit and the test name")
        self.assertEqual(out["known_flaky"], [], "nothing flaked")

    def test_a_test_failing_in_one_run_makes_its_unit_known_flaky(self):
        out = self.fn("merge_recording")([[{"unit": "svc::B", "name": "t2"}], []])
        self.assertEqual(out["known_flaky"], ["svc::B"], "one run only: the unit is known_flaky")
        self.assertNotIn("svc::B", out["known_failing"], "and it is not known_failing")

    def test_an_environment_run_writes_nothing(self):
        out = self.fn("merge_recording")([None, [{"unit": "svc::A", "name": "t1"}]])
        self.assertIsNone(out, "a run that read environment makes the whole recording None")


class TestRunRecording(LandCase):

    def config(self):
        return {"verification": {"steps": [dotnet_step()]}, "emulators": [EMU_AZURITE]}

    def record(self, trx_by_run, probe=True, timed_out=False):
        lc = self.mod()
        counter = {"n": 0}

        def fake_long(cmd, timeout=None, log_path=None, cwd=None, *a, **k):
            counter["n"] += 1
            text = trx_by_run[min(counter["n"] - 1, len(trx_by_run) - 1)]
            for c in cmd:
                if str(c).endswith(".trx") and text is not None:
                    p = Path(str(c).split("=")[-1])
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(text, encoding="utf-8")
            # timed out: exit 0 and a valid passing result, so the timeout is the ONLY abnormal fact
            return (0 if timed_out else 1, timed_out)

        with tempfile.TemporaryDirectory() as d:
            out_path = Path(d) / "test-baseline.json"
            with mock.patch.object(lc, "tcp_probe", return_value=probe), \
                 mock.patch.object(lc, "_run_long", side_effect=fake_long) as long_:
                result = self.fn("run_recording")(self.config(), cwd=d, results_dir=Path(d) / "res",
                                                  out_path=out_path, commit=sha40("c"))
            written = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else None
            return result, written, long_

    def test_both_runs_failing_and_one_run_failing_fill_the_two_lists(self):
        run1 = make_trx([("Acme.AlphaTests", "Fails", "Failed", "x"),
                         ("Acme.BetaTests", "Flaky", "Failed", "x"),
                         ("Acme.AlphaTests", "Fine", "Passed", "")])
        run2 = make_trx([("Acme.AlphaTests", "Fails", "Failed", "x"),
                         ("Acme.BetaTests", "Flaky", "Passed", ""),
                         ("Acme.AlphaTests", "Fine", "Passed", "")])
        result, written, long_ = self.record([run1, run2])
        self.assertEqual(result["outcome"], "baseline-recorded", "a clean recording succeeds")
        self.assertEqual(long_.call_count, 2, "every step runs twice (L-8)")
        entry = written[SUITE]
        self.assertEqual(entry["known_failing"], {unit_id("Acme.AlphaTests"): ["Fails"]},
                         "the test failing in both runs is known_failing, by name")
        self.assertIn(unit_id("Acme.BetaTests"), entry["known_flaky"],
                      "the unit with a one-run failure is known_flaky")
        self.assertEqual(entry["runs"], 2, "the entry records two runs")
        self.assertEqual(entry["measured_at_commit"], sha40("c"), "and the commit it measured")

    def test_an_unreachable_emulator_writes_nothing_and_runs_nothing(self):
        result, written, long_ = self.record([make_trx([("A", "t", "Passed", "")])], probe=False)
        self.assertEqual(result["outcome"], "environment-failure",
                         "a recording with an unreachable emulator is an environment halt")
        self.assertIsNone(written, "nothing is written")
        long_.assert_not_called()

    def test_a_timed_out_step_writes_nothing(self):
        passing = make_trx([("Acme.AlphaTests", "Passes", "Passed", "")])
        result, written, long_ = self.record([passing], timed_out=True)
        self.assertGreater(long_.call_count, 0, "fixture sanity: the step did launch, then timed out")
        self.assertEqual(result["outcome"], "environment-failure",
                         "a valid passing result file with timed_out is still an environment step")
        self.assertIsNone(written, "an environment reading writes nothing")

    def test_a_signature_matched_failure_never_enters_known_failing(self):
        both = make_trx([("Acme.StorageTests", "SigTest", "Failed", AZ_MSG),
                         ("Acme.OrderTests", "Totals", "Failed", "expected 3")])
        result, written, _ = self.record([both, both])
        self.assertEqual(result["outcome"], "baseline-recorded",
                         "an unrelated failure in both runs is recordable")
        text = json.dumps(written)
        self.assertNotIn("SigTest", text, "an emulator-signature failure is never recorded")
        self.assertIn("Totals", text, "the unrelated failure is recorded as known_failing")


# ===========================================================================
# (c) Conflict policy
# ===========================================================================
UNION_CONFIG = {
    "unionPaths": [{"glob": ".claude/JOURNAL.md", "entryKey": "heading"},
                   {"glob": ".claude/memory/MEMORY.md", "entryKey": "index-link"}],
    "regenerators": [{"id": "docs", "paths": ["docs/generated/**"], "triggers": [],
                      "command": [["echo", "regen"]]}],
}


class TestConflictClasses(LandCase):

    def test_union_regenerate_and_halt_classes(self):
        classify = self.fn("classify_conflict")
        self.assertEqual(classify(".claude/JOURNAL.md", UNION_CONFIG), "union", "listed union path")
        self.assertEqual(classify("docs/generated/openapi.json", UNION_CONFIG), "regenerate",
                         "a regenerator path takes the default branch's side then regenerates")
        self.assertEqual(classify("src/code.py", UNION_CONFIG), "halt",
                         "an unlisted path halts: the policy is closed")


class TestUnionMerge(LandCase):

    def merge(self, base, ours, theirs, key="heading"):
        return self.fn("merge_union")(base, ours, theirs, key)

    def test_insert_only_hunks_on_both_sides_union(self):
        base = "# T\n\n## A\n- a\n"
        r = self.merge(base, "# T\n\n## A\n- a\n## B\n- b\n", "# T\n\n## A\n- a\n## C\n- c\n")
        self.assertTrue(r["ok"], "two insert-only hunks are admissible: %s" % r.get("reason"))
        lines = r["text"].splitlines()
        for needle in ("## A", "## B", "## C"):
            self.assertEqual(lines.count(needle), 1, "%s must appear once in the union" % needle)
        self.assertLess(lines.index("## A"), lines.index("## B"), "base order is preserved")

    def test_a_hunk_editing_a_base_line_halts(self):
        base = "## A\n- a\n- b\n"
        r = self.merge(base, "## A\n- a\n- B-edited\n", "## A\n- a\n- b\n## C\n")
        self.assertFalse(r["ok"], "an edited base line is not an insert-only hunk")

    def test_a_hunk_deleting_a_base_line_halts(self):
        base = "## A\n- a\n- b\n"
        r = self.merge(base, "## A\n- a\n", "## A\n- a\n- b\n## C\n")
        self.assertFalse(r["ok"], "a deleted base line is not an insert-only hunk")

    def test_repeated_field_lines_are_never_keys(self):
        base = "## A\n- **Trigger:** x\n"
        r = self.merge(base, base + "## B\n- **Trigger:** x\n", base + "## C\n- **Trigger:** x\n")
        self.assertTrue(r["ok"], "field lines such as '- **Trigger:**' are not entry keys: %s"
                        % r.get("reason"))

    def test_a_base_with_two_identical_headings_untouched_passes(self):
        base = "## Dup\n- 1\n## Dup\n- 2\n"
        r = self.merge(base, "## New\n- n\n" + base, base + "- tail\n")
        self.assertTrue(r["ok"], "repeats already in the base are not inserted and never fire: %s"
                        % r.get("reason"))

    def test_the_same_heading_inserted_on_both_sides_halts(self):
        base = "## A\n- a\n"
        r = self.merge(base, base + "## Same\n- o\n", base + "## Same\n- t\n")
        self.assertFalse(r["ok"], "one heading inserted by both sides is a duplicate")

    def test_a_heading_inserted_that_already_exists_once_in_base_halts(self):
        base = "## A\n- a\n"
        r = self.merge(base, base + "## A\n- again\n", base)
        self.assertFalse(r["ok"], "count 2 exceeds max(base count 1, 1)")

    def test_two_index_lines_with_one_link_target_halt(self):
        base = "- [One](one.md) - x\n"
        r = self.merge(base, base + "- [Dup A](dup.md) - a\n", base + "- [Dup B](dup.md) - b\n",
                       key="index-link")
        self.assertFalse(r["ok"], "two inserted index lines with one link target are a duplicate")

    def test_positive_control_two_index_lines_with_different_targets_union(self):
        base = "- [One](one.md) - x\n"
        r = self.merge(base, base + "- [A](a.md) - a\n", base + "- [B](b.md) - b\n",
                       key="index-link")
        self.assertTrue(r["ok"], "different targets are not duplicates: %s" % r.get("reason"))


# ===========================================================================
# (l) Children
# ===========================================================================
def children(nodes, total=None):
    return {"nodes": [{"number": n, "state": s} for n, s in nodes],
            "totalCount": len(nodes) if total is None else total}


class TestEvaluateChildren(LandCase):

    def ev(self, read, ids=(401, 402)):
        return self.fn("evaluate_children")(list(ids), read)["outcome"]

    def test_positive_control_all_listed_and_closed_is_none(self):
        self.assertIsNone(self.ev(children([(401, "CLOSED"), (402, "CLOSED")])),
                          "every child present and CLOSED is the only passing reading")

    def test_an_open_child_is_children_still_open(self):
        self.assertEqual(self.ev(children([(401, "CLOSED"), (402, "OPEN")])), "children-still-open",
                         "an open child blocks the landing")

    def test_an_empty_list_while_work_items_exist_is_unverifiable(self):
        self.assertEqual(self.ev(children([])), "unverifiable",
                         "an empty list with work items is never 'all closed'")

    def test_a_missing_id_is_unverifiable(self):
        self.assertEqual(self.ev(children([(401, "CLOSED")])), "unverifiable",
                         "a work item id absent from the parent issue's children is unverifiable")

    def test_a_total_above_the_returned_count_is_unverifiable(self):
        self.assertEqual(self.ev(children([(401, "CLOSED"), (402, "CLOSED")], total=5)),
                         "unverifiable", "a truncated read cannot prove every child closed")

    def test_an_unreadable_read_is_unverifiable(self):
        self.assertEqual(self.ev(None), "unverifiable", "an unreadable read is never 'all closed'")


# ===========================================================================
# (b) Landing outcomes: one halt per test with ONLY its condition true
# ===========================================================================
SUCCESS_OUTCOMES = ("landed", "already-landed", "not-applicable")
HALT_OUTCOMES = (
    "landing-in-progress", "not-complete", "ambiguous-parent", "parent-unresolved",
    "parent-is-default", "gh-repo-set", "landing-not-configured", "baseline-unreadable",
    "unverifiable", "parent-diverged", "blocked-verdict", "children-still-open",
    "environment-failure", "unresolvable-conflict", "regeneration-failed",
    "verification-not-ready", "push-rejected", "pr-mismatch", "pr-not-ready",
    "link-not-verified", "master-moved", "head-moved", "not-mergeable", "merge-refused",
    "merge-unconfirmed",
)


def fact_key(outcome):
    return outcome.replace("-", "_")


# evaluate_gates covers P3 to P14. Facts are phase-specific booleans ("p<N>_<outcome>"), listed
# here in gate order, because environment-failure, unverifiable and children-still-open each
# occur in more than one phase. P8 is the verdict fact "p8_verification_verdict". The halts of
# P0 to P2 (landing-in-progress, not-complete, ambiguous-parent, parent-unresolved,
# parent-is-default, gh-repo-set, landing-not-configured, baseline-unreadable, parent-diverged,
# and the P0/P2 unverifiable and environment-failure) are decided where their facts arise and
# are tested at launcher and stage level below.
GATE_FACTS = (
    ("p3_blocked_verdict", "blocked-verdict"),
    ("p4_children_still_open", "children-still-open"),
    ("p4_unverifiable", "unverifiable"),
    ("p6_environment_failure", "environment-failure"),
    ("p7_unresolvable_conflict", "unresolvable-conflict"),
    ("p7_environment_failure", "environment-failure"),
    ("p7_regeneration_failed", "regeneration-failed"),
    ("p9_push_rejected", "push-rejected"),
    ("p10_pr_mismatch", "pr-mismatch"),
    ("p10_pr_not_ready", "pr-not-ready"),
    ("p11_link_not_verified", "link-not-verified"),
    ("p12_children_still_open", "children-still-open"),
    ("p12_master_moved", "master-moved"),
    ("p12_head_moved", "head-moved"),
    ("p12_not_mergeable", "not-mergeable"),
    ("p13_merge_refused", "merge-refused"),
    ("p14_merge_unconfirmed", "merge-unconfirmed"),
)


def good_facts():
    facts = {key: False for key, _ in GATE_FACTS}
    facts["p8_verification_verdict"] = "READY"
    return facts


class TestLandingOutcomeSet(LandCase):

    def test_the_outcome_set_is_closed_and_complete(self):
        outcomes = self.mod().__dict__.get("LANDING_OUTCOMES")
        self.assertIsNotNone(outcomes, "land_contract.LANDING_OUTCOMES (the closed set) must exist")
        self.assertEqual(set(outcomes), set(SUCCESS_OUTCOMES) | set(HALT_OUTCOMES),
                         "the closed set holds exactly 3 successes and 25 halts")


class TestEvaluateGates(LandCase):
    """P3 to P14. Stage-level tests keep the four required ordering pairs on real edges."""

    def test_positive_control_all_conditions_false_halts_nothing(self):
        self.assertIsNone(self.fn("evaluate_gates")(good_facts()),
                          "with no condition true there is no halt")

    def test_a_verification_verdict_of_environment_is_environment_failure(self):
        facts = good_facts()
        facts["p8_verification_verdict"] = "ENVIRONMENT"
        self.assertEqual(self.fn("evaluate_gates")(facts), "environment-failure",
                         "an ENVIRONMENT verdict is an environment halt, never a regression")

    def test_blocked_verdict_comes_before_children_still_open(self):
        facts = good_facts()
        facts.update(p3_blocked_verdict=True, p4_children_still_open=True)
        self.assertEqual(self.fn("evaluate_gates")(facts), "blocked-verdict",
                         "gate 3 (P3) is evaluated before gate 2 (P4)")

    def test_children_still_open_comes_before_a_setup_environment_failure(self):
        facts = good_facts()
        facts.update(p4_children_still_open=True, p6_environment_failure=True)
        self.assertEqual(self.fn("evaluate_gates")(facts), "children-still-open",
                         "the children check precedes setup and merge (P4 before P6)")

    def test_verification_comes_before_a_push_rejection(self):
        facts = good_facts()
        facts.update(p9_push_rejected=True, p8_verification_verdict="NOT-READY")
        self.assertEqual(self.fn("evaluate_gates")(facts), "verification-not-ready",
                         "verification (P8) precedes the push (P9)")

    def test_link_not_verified_comes_before_merge_refused(self):
        facts = good_facts()
        facts.update(p11_link_not_verified=True, p13_merge_refused=True)
        self.assertEqual(self.fn("evaluate_gates")(facts), "link-not-verified",
                         "the closing-link check (P11) precedes the merge (P13)")


def _make_halt_test(key, outcome):
    def test(self):
        facts = good_facts()
        facts[key] = True
        self.assertEqual(
            self.fn("evaluate_gates")(facts), outcome,
            "with ONLY %s true the halt must be %r verbatim" % (key, outcome))
    return test


def _make_verdict_test(verdict, outcome):
    def test(self):
        facts = good_facts()
        facts["p8_verification_verdict"] = verdict
        self.assertEqual(
            self.fn("evaluate_gates")(facts), outcome,
            "with ONLY a %s verdict the halt must be %r verbatim" % (verdict, outcome))
    return test


for _key, _o in GATE_FACTS:
    setattr(TestEvaluateGates, "test_halt_%s_when_only_its_condition_is_true" % _key,
            _make_halt_test(_key, _o))
setattr(TestEvaluateGates, "test_halt_p8_verification_not_ready_when_only_its_verdict_is_set",
        _make_verdict_test("NOT-READY", "verification-not-ready"))


class TestRollUpVerdict(LandCase):
    """The cross-step roll-up (L-7b): regression wins over environment; neither reads as zero."""

    def reading(self, name):
        return {"reading": name, "id": name}

    def roll(self, *names):
        return self.fn("roll_up_verdict")([self.reading(n) for n in names])

    def test_an_environment_step_and_a_regression_step_roll_up_to_not_ready(self):
        self.assertEqual(self.roll("environment", "regression"), "NOT-READY",
                         "any regression gives verification-not-ready, environment steps listed too")

    def test_the_order_of_the_steps_does_not_change_the_roll_up(self):
        self.assertEqual(self.roll("regression", "environment", "ok"), "NOT-READY",
                         "regression wins whatever the step order")

    def test_environment_steps_only_roll_up_to_environment(self):
        self.assertEqual(self.roll("ok", "environment", "environment"), "ENVIRONMENT",
                         "with no regression, any environment step gives environment-failure")

    def test_positive_control_all_ok_is_ready(self):
        self.assertEqual(self.roll("ok", "ok"), "READY", "every step ok reads READY")

    def test_no_applicable_step_is_ready(self):
        self.assertEqual(self.fn("roll_up_verdict")([]), "READY",
                         "configured but no step applies reads READY")

    def test_the_roll_up_verdicts_map_to_the_two_halts(self):
        facts = good_facts()
        facts["p8_verification_verdict"] = self.roll("environment", "regression")
        self.assertEqual(self.fn("evaluate_gates")(facts), "verification-not-ready",
                         "environment plus regression halts verification-not-ready end to end")
        facts["p8_verification_verdict"] = self.roll("environment")
        self.assertEqual(self.fn("evaluate_gates")(facts), "environment-failure",
                         "environment only halts environment-failure end to end")


# ===========================================================================
# (j) Next command per outcome
# ===========================================================================
class TestNextCommandPerOutcome(LandCase):

    def nc(self, outcome, **facts):
        return self.fn("next_command_for_outcome")(outcome, "demo-slug", **facts)

    def test_environment_failure_is_advance(self):
        self.assertEqual(self.nc("environment-failure")["commands"], ["/advance demo-slug"],
                         "the operator fixes the environment and reruns /advance")

    def test_landed_and_already_landed_have_no_next_command(self):
        for o in ("landed", "already-landed"):
            self.assertEqual(self.nc(o)["commands"], [], "%s ends the loop" % o)
            self.assertTrue(self.nc(o)["reason"], "an empty list travels with a reason")

    def test_not_applicable_is_the_verification_line(self):
        self.assertEqual(self.nc("not-applicable")["commands"], ["/verify-before-done"],
                         "no parent branch: today's ending")

    def test_children_still_open_and_landing_in_progress_have_none(self):
        for o in ("children-still-open", "landing-in-progress"):
            self.assertEqual(self.nc(o)["commands"], [], "%s has nothing to run" % o)

    def test_design_first_routes(self):
        for o in ("blocked-verdict", "unresolvable-conflict", "regeneration-failed"):
            self.assertEqual(self.nc(o)["commands"], ["/design-first demo-slug"],
                             "%s needs a remedy sub-task" % o)

    def test_other_halts_default_to_advance(self):
        for o in ("push-rejected", "master-moved", "parent-diverged"):
            self.assertEqual(self.nc(o)["commands"], ["/advance demo-slug"],
                             "%s reruns after the remedy" % o)

    def test_verification_not_ready_first_time_routes_to_a_baseline_rerecording(self):
        nc = self.nc("verification-not-ready", suite_ids=["services", "scripts"],
                     new_failures=["services::A::t1"], previous_new_failures=[],
                     baseline_commit_now=sha40("a"), baseline_commit_previous=None)
        self.assertEqual(len(nc["commands"]), 2, "re-record, then /advance")
        self.assertTrue(nc["commands"][0].startswith("/task Re-record the failing-test baseline for "),
                        "first command is the /task re-record line")
        self.assertIn("services", nc["commands"][0], "it names the suite ids")
        self.assertEqual(nc["commands"][1], "/advance demo-slug", "then /advance")
        self.assertFalse(nc.get("repeat_after_rerecord"), "first time is not a repeat")

    def test_the_same_failures_after_the_baseline_commit_changed_is_a_repeat(self):
        nc = self.nc("verification-not-ready", suite_ids=["services"],
                     new_failures=["services::A::t1"], previous_new_failures=["services::A::t1"],
                     baseline_commit_now=sha40("b"), baseline_commit_previous=sha40("a"))
        self.assertTrue(nc.get("repeat_after_rerecord"), "it is not a missed flake")
        self.assertEqual(nc["commands"], ["/design-first demo-slug"], "a repeat routes to /design-first")

    def test_the_same_failures_with_the_baseline_unchanged_is_still_the_rerecord_route(self):
        nc = self.nc("verification-not-ready", suite_ids=["services"],
                     new_failures=["services::A::t1"], previous_new_failures=["services::A::t1"],
                     baseline_commit_now=sha40("a"), baseline_commit_previous=sha40("a"))
        self.assertFalse(nc.get("repeat_after_rerecord"),
                         "nobody re-recorded in between, so this is not a repeat after re-recording")
        self.assertTrue(nc["commands"][0].startswith("/task Re-record"),
                        "the re-record route stands until the baseline moves")

    def test_different_new_failures_with_the_baseline_moved_is_the_rerecord_route(self):
        nc = self.nc("verification-not-ready", suite_ids=["services"],
                     new_failures=["services::B::t2"], previous_new_failures=["services::A::t1"],
                     baseline_commit_now=sha40("b"), baseline_commit_previous=sha40("a"))
        self.assertFalse(nc.get("repeat_after_rerecord"),
                         "the baseline moved, but these are NOT the failures reported last time, "
                         "so this is not a repeat: the recording did not miss a flake, it met a new one")
        self.assertTrue(nc["commands"][0].startswith("/task Re-record"),
                        "different failures route to the re-record line, not /design-first")
        self.assertEqual(nc["commands"][-1], "/advance demo-slug", "then /advance")

    def test_only_some_failures_repeating_with_the_baseline_moved_is_the_rerecord_route(self):
        nc = self.nc("verification-not-ready", suite_ids=["services"],
                     new_failures=["services::A::t1", "services::B::t2"],
                     previous_new_failures=["services::A::t1"],
                     baseline_commit_now=sha40("b"), baseline_commit_previous=sha40("a"))
        self.assertFalse(nc.get("repeat_after_rerecord"),
                         "a repeat needs EVERY new failure to have been new last time")
        self.assertTrue(nc["commands"][0].startswith("/task Re-record"), "so it re-records")


# ===========================================================================
# (e) Edge argv tests, patching ONLY land_contract._run / _run_long
# ===========================================================================
class TestEdgeArgv(LandCase):

    def patched(self, rc=0, out=""):
        lc = self.mod()
        self.fn("_run")
        self.fn("_run_long")
        return (mock.patch.object(lc, "_run", return_value=(rc, out)),
                mock.patch.object(lc, "_run_long", return_value=(rc, False)))

    @staticmethod
    def argvs(*mocks):
        out = []
        for m in mocks:
            for call in m.call_args_list:
                cmd = call[0][0] if call[0] else call[1].get("cmd")
                out.append([str(c) for c in cmd])
        return out

    def refused(self, func, *a):
        """True when the edge refused: raised ValueError or returned a non-zero rc."""
        try:
            res = func(*a)
        except ValueError:
            return True
        return isinstance(res, tuple) and res and res[0] != 0

    def test_merge_argv_is_merge_commit_pinned_to_forty_hex(self):
        merge = self.fn("gh_pr_merge")
        p_run, p_long = self.patched()
        with p_run as run, p_long as long_:
            merge(7, sha40("a"))
        argv = self.argvs(run, long_)[0]
        self.assertEqual(argv[:3], ["gh", "pr", "merge"], "the merge edge runs gh pr merge")
        self.assertIn("--merge", argv, "the merge method is --merge")
        self.assertIn("--match-head-commit", argv, "the head is pinned")
        self.assertEqual(argv[argv.index("--match-head-commit") + 1], sha40("a"),
                         "pinned to the exact 40-hex commit")

    def test_an_abbreviated_commit_is_refused_before_the_call(self):
        merge = self.fn("gh_pr_merge")
        p_run, p_long = self.patched()
        with p_run as run, p_long as long_:
            refused = self.refused(merge, 7, sha40("a")[:7])
        self.assertTrue(refused, "an abbreviated sha must be refused")
        self.assertEqual(self.argvs(run, long_), [], "and refused BEFORE any process is started")

    def test_create_argv_has_base_and_head_and_is_not_a_draft(self):
        create = self.fn("gh_pr_create")
        p_run, p_long = self.patched(out="https://example.test/o/r/pull/7")
        with p_run as run, p_long as long_:
            create("master", "feature/p", "title", "Closes #394")
        argv = self.argvs(run, long_)[0]
        self.assertEqual(argv[:3], ["gh", "pr", "create"], "the create edge runs gh pr create")
        self.assertEqual(argv[argv.index("--base") + 1], "master", "the base is the default branch")
        self.assertEqual(argv[argv.index("--head") + 1], "feature/p", "the head is the parent branch")
        self.assertNotIn("--draft", argv, "the parent pull request is opened ready, never as a draft")

    def test_ready_argv(self):
        ready = self.fn("gh_pr_ready")
        p_run, p_long = self.patched()
        with p_run as run, p_long as long_:
            ready(7)
        argv = self.argvs(run, long_)[0]
        self.assertEqual(argv[:3], ["gh", "pr", "ready"], "the ready edge runs gh pr ready")
        self.assertIn("7", argv, "for the named pull request")

    def test_push_argv_is_head_to_the_parent_branch_without_force(self):
        push = self.fn("git_push")
        p_run, p_long = self.patched()
        with p_run as run, p_long as long_:
            push("feature/p", ".", "master", ["master", "main"])
        argv = self.argvs(run, long_)[0]
        self.assertEqual(argv[:2], ["git", "push"], "the push edge runs git push")
        self.assertIn("HEAD:refs/heads/feature/p", argv, "the destination is the parent branch")
        self.assertFalse([a for a in argv if a in ("-f", "--force", "--force-with-lease")
                          or a.startswith("--force") or a.startswith("+")],
                         "a push is never forced")

    def test_a_protected_destination_is_refused_before_the_call(self):
        push = self.fn("git_push")
        for parent in ("master", "main", "release"):
            p_run, p_long = self.patched()
            with p_run as run, p_long as long_:
                refused = self.refused(push, parent, ".", "master", ["master", "main", "release"])
            self.assertTrue(refused, "pushing to %r must be refused" % parent)
            self.assertEqual(self.argvs(run, long_), [],
                             "%r is refused BEFORE any process is started" % parent)

    def test_children_read_uses_the_parent_list_command_argv(self):
        read = self.fn("read_children")
        payload = json.dumps({"subIssues": {"nodes": [{"number": 401, "state": "CLOSED"}],
                                            "totalCount": 1}})
        p_run, p_long = self.patched(out=payload)
        with p_run as run, p_long as long_:
            got = read(394)
        argv = self.argvs(run, long_)[0]
        self.assertEqual(argv[:6], ["gh", "issue", "view", "394", "--json", "subIssues"],
                         "the read is the conventions file's parentListCommand")
        self.assertEqual(got["totalCount"], 1, "the total count is returned")
        self.assertEqual(got["nodes"][0]["number"], 401, "the nodes are returned")

    def test_an_unreadable_children_read_is_none(self):
        read = self.fn("read_children")
        p_run, p_long = self.patched(rc=1, out="boom")
        with p_run, p_long:
            self.assertIsNone(read(394), "a failed read is None, never an empty list")


class TestWorktreeResetRefusals(LandCase):
    """L-15: destructive git only inside a recorded, listed landing worktree."""

    def setUp(self):
        self.mod()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.kit = Kit(self._tmp.name)
        # The passthrough runs real git with an INHERITED working directory: make it the
        # temporary operator checkout, never this checkout (the module guard enforces that).
        saved_cwd = os.getcwd()
        os.chdir(str(self.kit.main))
        self.addCleanup(os.chdir, saved_cwd)

    def passthrough(self):
        lc = self.mod()
        orig = lc._run
        return mock.patch.object(lc, "_run", side_effect=lambda cmd, *a, **k: orig(cmd, *a, **k))

    def record_phase(self, wt):
        write_files(self.kit.main, {".claude/state/landing/%s/phase.json" % SLUG:
                                    json.dumps({"run_id": "r", "phase": "p1", "worktree": str(wt)})})

    @staticmethod
    def destructive(run):
        return [c[0][0] for c in run.call_args_list
                if any(str(x) in ("reset", "clean") for x in c[0][0])]

    def test_a_path_not_in_git_worktree_list_is_refused(self):
        reset = self.fn("worktree_reset")
        stray = Path(self._tmp.name) / "stray"
        stray.mkdir()
        self.record_phase(stray)
        with self.passthrough() as run:
            with self.assertRaises(ValueError, msg="a path git does not list must be refused"):
                reset(stray, self.kit.main, SLUG)
        self.assertEqual(self.destructive(run), [], "no reset or clean ran")

    def test_a_listed_path_not_recorded_in_phase_json_is_refused(self):
        reset = self.fn("worktree_reset")
        wt = self.kit.add_worktree("20260101-land-394")
        with self.passthrough() as run:
            with self.assertRaises(ValueError, msg="a listed path with no phase.json must be refused"):
                reset(wt, self.kit.main, SLUG)
        self.assertEqual(self.destructive(run), [], "no reset or clean ran")

    def test_a_recorded_and_listed_path_is_reset_and_cleaned_keeping_ignored_files(self):
        reset = self.fn("worktree_reset")
        wt = self.kit.add_worktree("20260101-land-394")
        self.record_phase(wt)
        write_files(wt, {"stray.txt": "x", "node_modules/keep.txt": "y"})
        with self.passthrough() as run:
            reset(wt, self.kit.main, SLUG)
        argvs = [[str(x) for x in c[0][0]] for c in run.call_args_list]
        self.assertTrue(any("reset" in a and "--hard" in a for a in argvs), "git reset --hard ran")
        self.assertTrue(any("clean" in a for a in argvs), "git clean ran")
        self.assertFalse(any(re.fullmatch(r"-[a-zA-Z]*x[a-zA-Z]*", x) for a in argvs for x in a),
                         "git clean must never use -x: ignored files survive")
        self.assertFalse((wt / "stray.txt").exists(), "an untracked file is cleaned")
        self.assertTrue((wt / "node_modules" / "keep.txt").exists(),
                        "an ignored file survives between runs (installed packages)")


# ===========================================================================
# (h) L-11 containment scanner
# ===========================================================================
class TestContainmentScanner(LandCase):

    def found_in_fixture(self, rel, text):
        scan_tree = self.fn("scan_tree")
        with tempfile.TemporaryDirectory() as d:
            write_files(d, {rel: text, ".claude/scripts/benign.py": "x = 1\n"})
            return [(Path(p).as_posix(), pat) for p, pat in scan_tree(Path(d))]

    def assert_found(self, rel, text, spelling):
        found = self.found_in_fixture(rel, text)
        self.assertTrue(any(p == rel for p, _ in found),
                        "the scanner must find the %s spelling in %s; found %r" % (spelling, rel, found))

    def test_1_shell_gh_pr_merge(self):
        self.assert_found(".claude/scripts/f1.sh", "gh pr merge 12 --merge\n", "gh pr merge 12")

    def test_2_argv_list_gh_pr_merge_across_three_lines(self):
        self.assert_found(".claude/scripts/f2.py", 'CMD = (\n    "gh",\n    "pr",\n    "merge")\n',
                          '("gh",/"pr",/"merge")')

    def test_3_gh_api_pulls_merge(self):
        self.assert_found(".claude/skills/x/f3.md", "gh api repos/o/r/pulls/12/merge -X PUT\n",
                          "gh api .../pulls/12/merge")

    def test_4_git_push_origin_master(self):
        self.assert_found(".claude/hooks/f4.sh", "git push origin master\n", "git push origin master")

    def test_5_git_push_origin_head_colon_master(self):
        self.assert_found("tools/f5.cmd", "git push origin HEAD:master\n", "git push origin HEAD:master")

    def test_6_git_push_origin_head_colon_refs_heads_main(self):
        self.assert_found(".claude/agents/f6.md", "git push origin HEAD:refs/heads/main\n",
                          "git push origin HEAD:refs/heads/main")

    def test_7_argv_list_git_push_origin_main(self):
        self.assert_found(".claude/scripts/f7.py", 'RUN = ("git", "push", "origin", "main")\n',
                          '("git", "push", "origin", "main")')

    def test_a_push_to_a_non_protected_branch_is_not_found(self):
        found = self.found_in_fixture(".claude/scripts/f8.sh", "git push origin HEAD:refs/heads/feature/p\n")
        self.assertEqual(found, [], "a push to a non-protected branch is not a finding")

    def test_a_fixture_under_a_tests_folder_is_excluded(self):
        found = self.found_in_fixture(".claude/scripts/tests/f9.py", "gh pr merge 12\n")
        self.assertEqual(found, [], "test guards hold the forbidden tuples on purpose (L-11)")

    def test_land_contract_is_admitted_for_pattern_one_only(self):
        merge_only = self.found_in_fixture(".claude/scripts/land_contract.py", "gh pr merge 12\n")
        self.assertEqual(merge_only, [], "land_contract.py may spell gh pr merge")
        push = self.found_in_fixture(".claude/scripts/land_contract.py", "git push origin master\n")
        self.assertTrue(push, "but land_contract.py may never push to a protected branch")

    def test_the_exemption_is_the_exact_path_not_the_basename(self):
        self.assert_found("tools/land_contract.py", "gh pr merge 12\n", "gh pr merge in tools/land_contract.py")
        self.assert_found(".claude/hooks/land_contract.py", "gh pr merge 12\n",
                          "gh pr merge in a same-named file elsewhere")
        self.assert_found(".claude/scripts/sub/land_contract.py", "gh pr merge 12\n",
                          "gh pr merge in a nested same-named file")
        exempt = self.found_in_fixture(".claude/scripts/land_contract.py", "gh pr merge 12\n")
        self.assertEqual(exempt, [], "positive control: the exact path is the one exempt file")

    def test_land_contract_itself_is_found_by_pattern_one(self):
        scan_text = self.fn("scan_text")
        mod = self.mod()
        patterns = scan_text(Path(mod.__file__).read_text(encoding="utf-8"))
        self.assertIn("gh-pr-merge", set(patterns),
                      "the real script must spell the merge in a form the scanner recognises")

    def test_land_contract_own_push_to_the_parent_branch_is_not_found(self):
        scan_text = self.fn("scan_text")
        mod = self.mod()
        patterns = scan_text(Path(mod.__file__).read_text(encoding="utf-8"))
        self.assertNotIn("git-push-protected", set(patterns),
                         "its push to HEAD:refs/heads/<parent> is a non-protected destination")

    def test_a_scan_of_zero_files_fails(self):
        scan_tree = self.fn("scan_tree")
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError, msg="zero files scanned must fail, never pass vacuously"):
                scan_tree(Path(d))

    def test_the_real_tree_holds_no_merge_outside_land_contract(self):
        scan_tree = self.fn("scan_tree")
        findings = [(Path(p).as_posix(), pat) for p, pat in scan_tree(REPO_ROOT)]
        self.assertEqual(findings, [],
                         "only land_contract.py merges a pull request, and nothing pushes a "
                         "protected branch (L-11)")


# ===========================================================================
# (i) L-12 token test
# ===========================================================================
def token_hits(text, tokens, allowed):
    """The matcher the L-12 test uses: tokens found in text once allowed strings are removed."""
    for a in allowed:
        text = text.replace(a, "")
    low = text.lower()
    return [tok for tok in tokens if tok.lower() in low]


class TestTokenMatcher(unittest.TestCase):
    """Positive controls for the matcher itself. Needs no land_contract, so it passes today."""

    def test_a_token_in_the_text_is_found_case_insensitively(self):
        self.assertEqual(token_hits("see the AcmeCorp tree", ["acmecorp"], []), ["acmecorp"],
                         "a present token must be reported, or the L-12 scan could never fail")

    def test_an_allowed_string_hides_its_token_and_nothing_else(self):
        self.assertEqual(token_hits("AcmeCorp/allowed-path", ["acmecorp"], ["AcmeCorp/allowed-path"]), [],
                         "an allowed string is removed before matching")
        self.assertEqual(
            token_hits("AcmeCorp/allowed-path and AcmeCorp elsewhere", ["acmecorp"],
                       ["AcmeCorp/allowed-path"]), ["acmecorp"],
            "a token outside the allowed string is still found")

    def test_a_clean_text_has_no_hits(self):
        self.assertEqual(token_hits("nothing here", ["acmecorp"], []), [], "no token, no hit")


class TestNoProjectTokens(LandCase):

    def test_land_contract_and_its_tests_carry_no_project_token(self):
        mod = self.mod()
        cfg_path = REPO_ROOT / ".claude" / ".project-tokens.json"
        if not cfg_path.exists():
            self.skipTest("no .claude/.project-tokens.json in this tree, so there is no token list "
                          "to scan against")
        cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
        tokens = [t for t in cfg.get("tokens", []) if t]
        if not tokens:
            self.skipTest("the token list in .project-tokens.json is empty (the plugin template), "
                          "so the scan has nothing to match")
        allowed = [a.get("string", "") for a in cfg.get("allowed", []) if a.get("string")]
        problems = []
        for label, path in (("land_contract.py", Path(mod.__file__)), ("this test file", THIS_FILE)):
            for tok in token_hits(path.read_text(encoding="utf-8"), tokens, allowed):
                problems.append("%s contains the project token %r" % (label, tok))
        self.assertEqual(problems, [], "L-12: no project token in the script or its tests")


# ===========================================================================
# (n) Applicability and coverage over the right diffs
# ===========================================================================
class TestApplicabilityAndCoverage(LandCase):
    STEPS = [{"id": "docs-check", "when_paths": ["docs/**"]},
             {"id": "py-unit", "when_paths": ["src/**"]}]
    ROWS = [{"reviewer": "doc-reviewer", "paths": ["docs/**"]}]

    def test_a_step_is_applicable_when_only_the_merge_diff_touches_its_paths(self):
        got = self.fn("applicable_steps")(self.STEPS, ["src/a.py"], ["docs/x.md"])
        self.assertEqual(sorted(got), ["docs-check", "py-unit"],
                         "applicability is decided over contract_diff UNION merge_diff")

    def test_positive_control_a_step_matching_neither_diff_is_not_applicable(self):
        got = self.fn("applicable_steps")(self.STEPS, ["src/a.py"], ["other/y.md"])
        self.assertEqual(got, ["py-unit"], "docs-check matches no changed path")

    def test_coverage_is_not_required_by_a_merge_only_path(self):
        got = self.fn("required_coverage")(self.ROWS, ["src/a.py"], [])
        self.assertEqual(got, [], "coverage reads contract_diff and resolved_paths, not merge_diff")

    def test_coverage_is_required_by_a_resolved_path(self):
        got = self.fn("required_coverage")(self.ROWS, ["src/a.py"], ["docs/x.md"])
        self.assertEqual(got, ["doc-reviewer"],
                         "a path the landing hand-resolved (the Hand-Resolved Summary) needs its reviewer")

    def test_coverage_is_required_by_a_contract_diff_path(self):
        got = self.fn("required_coverage")(self.ROWS, ["docs/z.md"], [])
        self.assertEqual(got, ["doc-reviewer"], "a path in the contract's own diff needs its reviewer")


# ===========================================================================
# (r) Results outside the tree
# ===========================================================================
class TestCheckConfiguration(LandCase):

    def cfg(self, **step_over):
        step = dotnet_step()
        step.update(step_over)
        return {"verification": {"steps": [step]}}

    def check(self, config, d):
        return self.fn("check_configuration")(config, Path(d) / "wt", Path(d) / "logs" / "res")

    def test_positive_control_a_results_path_under_results_dir_is_configured(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(self.check(self.cfg(), d), "a placeholder results path is fine")

    def test_a_results_path_inside_the_worktree_is_not_configured(self):
        with tempfile.TemporaryDirectory() as d:
            got = self.check(self.cfg(results={"format": "trx", "path": "TestResults/r.trx"}), d)
            self.assertIsNotNone(got, "a results path resolving inside the worktree must be refused")
            self.assertEqual(got["outcome"], "landing-not-configured",
                             "results must never land in the tree under test")

    def test_an_absent_block_is_not_configured(self):
        with tempfile.TemporaryDirectory() as d:
            got = self.check(None, d)
            self.assertEqual((got or {}).get("outcome"), "landing-not-configured",
                             "no contractLanding block halts landing-not-configured")

    def test_empty_verification_steps_is_not_configured(self):
        with tempfile.TemporaryDirectory() as d:
            got = self.check({"verification": {"steps": []}}, d)
            self.assertEqual((got or {}).get("outcome"), "landing-not-configured",
                             "empty verification.steps halts landing-not-configured")


# ===========================================================================
# (p) Delivery record set, pure form
# ===========================================================================
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


class TestBuildDeliverySet(LandCase):

    def build(self, listings):
        return self.fn("build_delivery_set")(listings, SLUG)

    def test_records_only_on_the_stable_records_branch_are_seen(self):
        got = self.build({"origin/docs/%s-records" % SLUG: {REC_DIR + "t1-backend.yaml": record_yaml()}})
        self.assertIn("t1-backend", got["records"], "the stable records branch is a source of records")
        self.assertIsNone(got["problem"], "nothing disagrees")

    def test_byte_identical_copies_on_two_refs_collapse(self):
        text = record_yaml()
        got = self.build({"origin/%s" % PARENT: {REC_DIR + "t1-backend.yaml": text},
                          "origin/master": {REC_DIR + "t1-backend.yaml": text}})
        self.assertEqual(list(got["records"]), ["t1-backend"], "one record, not two")
        self.assertIsNone(got["problem"], "identical copies are not a disagreement")

    def test_two_different_records_for_one_sub_task_are_unverifiable(self):
        got = self.build({"origin/%s" % PARENT: {REC_DIR + "t1-backend.yaml": record_yaml()},
                          "origin/master": {REC_DIR + "t1-backend.yaml": record_yaml(pull_request="other")}})
        self.assertEqual((got["problem"] or {}).get("outcome"), "unverifiable",
                         "two different records for one sub-task cannot be reconciled")

    def test_briefs_disagreeing_on_base_are_ambiguous_parent(self):
        path = BRIEF_DIR + "2026-10-05-401-t1.md"
        got = self.build({"origin/%s" % PARENT: {path: brief_md(401, base=PARENT)},
                          "origin/master": {path: brief_md(401, base="feature/other")}})
        self.assertEqual((got["problem"] or {}).get("outcome"), "ambiguous-parent",
                         "copies of one brief disagreeing on base: cannot name a parent")


# ===========================================================================
# (s) Worktree location, (q) roots
# ===========================================================================
class TestPlanWorktree(LandCase):
    MAIN = "D:/repo"

    def plan(self, paths):
        return self.fn("plan_worktree")(paths, 394, self.MAIN, "20261005")

    def test_an_existing_worktree_from_an_earlier_date_is_reused(self):
        old = self.MAIN + "/.claude/worktrees/20250101-land-394"
        got = self.plan([self.MAIN, old])
        self.assertEqual(got["path"], old, "a rerun asks git, not the calendar")
        self.assertFalse(got["create"], "and creates nothing")

    def test_two_matches_are_an_environment_failure_naming_both(self):
        a = self.MAIN + "/.claude/worktrees/20250101-land-394"
        b = self.MAIN + "/.claude/worktrees/20250102-land-394"
        got = self.plan([self.MAIN, a, b])
        self.assertEqual(got["outcome"], "environment-failure", "two matches are ambiguous")
        self.assertTrue("20250101-land-394" in got["detail"] and "20250102-land-394" in got["detail"],
                        "the detail names both paths")

    def test_a_worktree_whose_issue_number_merely_starts_with_ours_is_not_a_match(self):
        other = self.MAIN + "/.claude/worktrees/20250101-land-3940"
        got = self.plan([self.MAIN, other])
        self.assertTrue(got["create"], "-land-3940 is issue 3940, not 394: none matches, so one is created")
        self.assertNotEqual(got["path"].replace("\\", "/"), other,
                            "the 3940 worktree must never be adopted for issue 394")

    def test_positive_control_the_exact_suffix_matches_among_look_alikes(self):
        wanted = self.MAIN + "/.claude/worktrees/20250101-land-394"
        got = self.plan([self.MAIN, self.MAIN + "/.claude/worktrees/20250101-land-3940",
                         self.MAIN + "/.claude/worktrees/20250101-land-1394", wanted])
        self.assertEqual(got["path"], wanted, "only the path ending exactly -land-394 matches")
        self.assertFalse(got["create"], "and it is reused")

    def test_no_match_creates_one_with_todays_date(self):
        other = self.MAIN + "/.claude/worktrees/20250101-land-1394"
        got = self.plan([self.MAIN, other])
        self.assertTrue(got["create"], "none exists, so one is created")
        self.assertTrue(got["path"].replace("\\", "/").endswith(".claude/worktrees/20261005-land-394"),
                        "flat, under the main root, today's date; got %r. (-land-1394 is a different "
                        "issue and must not match)" % got["path"])


class TestResolveRoots(LandCase):

    def test_roots_come_from_the_git_common_dir_not_the_environment_or_cwd(self):
        resolve = self.fn("resolve_roots")
        with tempfile.TemporaryDirectory() as d:
            kit = Kit(d)
            second = kit.add_worktree("20260101-land-394")
            elsewhere = Path(d) / "elsewhere"
            elsewhere.mkdir()
            old_env = os.environ.pop("CLAUDE_PROJECT_DIR", None)
            old_cwd = os.getcwd()
            os.chdir(str(elsewhere))
            try:
                from_main = resolve(kit.main)
                from_second = resolve(second)
                env_after = os.environ.get("CLAUDE_PROJECT_DIR")
            finally:
                os.chdir(old_cwd)
                if old_env is None:
                    os.environ.pop("CLAUDE_PROJECT_DIR", None)
                else:
                    os.environ["CLAUDE_PROJECT_DIR"] = old_env
            self.assertEqual(norm(from_main["main_root"]), norm(kit.main),
                             "main root is the parent of the git common dir")
            self.assertEqual(norm(from_second["main_root"]), norm(kit.main),
                             "a second worktree gets the SAME main root")
            home = norm(Path.home())
            for key in ("landing_root", "logs_dir", "state_dir"):
                self.assertTrue(norm(from_main[key]).startswith(norm(kit.main)),
                                "%s must resolve under the main root, got %s" % (key, from_main[key]))
                self.assertFalse(norm(from_main[key]).startswith(home) and
                                 not norm(from_main[key]).startswith(norm(kit.main)),
                                 "%s must never fall back to the home directory" % key)
            self.assertTrue(norm(from_main["landing_root"]).endswith(
                os.path.normcase(os.path.join(".claude", "state", "landing"))),
                "the runtime root is <main root>/.claude/state/landing")
            self.assertEqual(norm(env_after or ""), norm(kit.main),
                             "the script sets CLAUDE_PROJECT_DIR to the main root for itself and its children")


# ===========================================================================
# Temporary repository kit: a bare origin, the operator checkout (main root), and a scratch
# clone that makes commits only the remote has.
# ===========================================================================
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


# ===========================================================================
# Launcher (P0)
# ===========================================================================
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


class TestLauncherHandsOverToTheLandingWorktreeCopy(LauncherCase):

    def script_arg(self, argv, kit):
        for a in argv:
            if norm(a).endswith(os.path.normcase(os.path.join(".claude", "scripts", "land_contract.py"))):
                return a
        return None

    def test_the_launcher_runs_the_worktree_copy_with_the_stage_flags(self):
        kit = Kit(self._tmp.name)
        code, execm, report = self.launch(kit)
        self.assertEqual(execm.call_count, 1, "the launcher execs the landing stage exactly once")
        argv = [str(a) for a in (execm.call_args[0][0] if execm.call_args[0]
                                 else execm.call_args[1]["argv"])]
        script = self.script_arg(argv, kit)
        self.assertIsNotNone(script, "the argv names the landing worktree's land_contract.py: %r" % argv)
        self.assertTrue(norm(script).startswith(norm(kit.main / ".claude" / "worktrees")),
                        "that script lives in the landing worktree, not the operator checkout: %s" % script)
        self.assertLessEqual(argv.index(script), 3, "the script path starts the argv (after the interpreter)")
        flags = {argv[i]: argv[i + 1] for i in range(len(argv) - 1) if argv[i].startswith("--")}
        self.assertEqual(flags.get("--stage"), "land", "stage land")
        self.assertEqual(flags.get("--parent"), PARENT, "the parent branch")
        self.assertEqual(flags.get("--contract"), SLUG, "the contract slug")
        self.assertEqual(norm(flags.get("--project-root", "")), norm(kit.main), "the main root")
        self.assertEqual(norm(flags.get("--checkout", "")), norm(kit.main), "the launching checkout")
        self.assertTrue(flags.get("--run-id"), "a run id")
        probed = self.probe_mock.call_args[0][0]
        self.assertEqual(norm(probed), norm(script),
                         "the --stage land probe examines the very script the launcher then runs")

    def test_a_dry_run_is_forwarded_to_the_landing_stage(self):
        kit = Kit(self._tmp.name)
        _, execm, _ = self.launch(kit, argv=["--contract", SLUG, "--dry-run", "--json"])
        argv = [str(a) for a in execm.call_args[0][0]]
        self.assertIn("--dry-run", argv, "the landing stage is told to stop after P5")
        plain = Path(self._tmp.name) / "plain"
        plain.mkdir()
        _, execm2, _ = self.launch(Kit(plain))
        self.assertNotIn("--dry-run", [str(a) for a in execm2.call_args[0][0]],
                         "positive control: an ordinary launch does not forward --dry-run")

    def test_a_child_that_leaves_no_report_gets_an_environment_failure_report(self):
        kit = Kit(self._tmp.name)
        _, _, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "environment-failure",
                         "the launcher writes environment-failure when the child left no report")

    def test_a_report_the_child_wrote_for_this_run_is_left_alone(self):
        kit = Kit(self._tmp.name)

        def child(argv, cwd=None):
            run_id = argv[[str(a) for a in argv].index("--run-id") + 1]
            write_files(kit.landing_dir() / SLUG, {"report.json": json.dumps(
                {"run_id": run_id, "outcome": "landed", "contract": SLUG})})
            return 0

        _, _, report = self.launch(kit, exec_side_effect=child)
        self.assertEqual(self.outcome(report), "landed", "the child's own report stands")

    def test_a_worktree_copy_that_rejects_stage_land_is_an_environment_failure(self):
        kit = Kit(self._tmp.name, script_text="# an older copy\n")
        code, execm, report = self.launch(kit, stage_ok=False)
        self.assertTrue(self.probe_mock.called, "the launcher asked whether the copy accepts --stage land")
        self.assertEqual(self.outcome(report), "environment-failure",
                         "never a landing by the launcher's own code (L-16)")
        execm.assert_not_called()

    def test_landing_code_absent_at_origin_parent_is_an_environment_failure(self):
        kit = Kit(self._tmp.name, script_text=None)
        code, execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "environment-failure",
                         "no .claude/scripts/land_contract.py at origin/<parent>: nothing to run (L-16)")
        execm.assert_not_called()


class TestLauncherP0Halts(LauncherCase):

    def test_gh_repo_set_exits_eight_and_halts(self):
        kit = Kit(self._tmp.name)
        code, execm, report = self.launch(kit, env={"GH_REPO": "o/other"})
        self.assertEqual(code, 8, "a set GH_REPO exits 8")
        self.assertEqual(self.outcome(report), "gh-repo-set", "the halt is gh-repo-set")
        execm.assert_not_called()

    def test_all_default_topology_is_not_applicable_with_the_verification_line(self):
        kit = Kit(self._tmp.name, brief_base="master")
        _, execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "not-applicable", "no parent branch: today's ending")
        self.assertEqual(report["next_command"]["commands"], ["/verify-before-done"],
                         "not-applicable hands to /verify-before-done")
        execm.assert_not_called()

    def test_briefs_declaring_two_bases_are_ambiguous_parent(self):
        kit = Kit(self._tmp.name)
        write_files(kit.main, {BRIEF_DIR + "2026-10-05-402-t2-frontend.md":
                               brief_md(402, base="feature/other")})
        _, execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "ambiguous-parent", "disagreeing bases halt")
        execm.assert_not_called()

    def test_a_brief_only_on_the_operators_disk_is_not_complete_naming_its_path(self):
        kit = Kit(self._tmp.name)
        write_files(kit.main, {BRIEF_DIR + "2026-10-05-403-t3-extra.md": brief_md(403, base=PARENT)})
        _, execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "not-complete",
                         "a work item on no fetched ref is invisible to the landing")
        self.assertIn("2026-10-05-403-t3-extra.md", report["remedy"],
                      "the remedy names the brief's path (commit and push it)")
        execm.assert_not_called()

    def test_positive_control_a_brief_pushed_to_the_records_branch_proceeds(self):
        kit = Kit(self._tmp.name)
        extra = {BRIEF_DIR + "2026-10-05-403-t3-extra.md": brief_md(403, base=PARENT)}
        write_files(kit.main, extra)
        kit.commit_remote("docs/%s-records" % SLUG, extra)
        _, execm, report = self.launch(kit)
        self.assertEqual(execm.call_count, 1, "a brief on one of the three fetched refs is enough")

    def test_a_local_parent_ahead_of_origin_is_parent_diverged(self):
        kit = Kit(self._tmp.name)
        kit.local_parent_ahead()
        _, execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "parent-diverged", "local ahead of origin halts")
        execm.assert_not_called()

    def test_a_local_parent_behind_origin_proceeds(self):
        kit = Kit(self._tmp.name)
        kit.commit_remote(PARENT, {"remote-only.txt": "x"})
        git(kit.main, "update-ref", "refs/heads/%s" % PARENT, "origin/%s~1" % PARENT)
        _, execm, report = self.launch(kit)
        self.assertEqual(execm.call_count, 1, "behind is the normal case after a GitHub merge")


class TestLauncherLock(LauncherCase):

    def write_lock(self, kit, pid, contract="other-contract", kind="land"):
        write_files(kit.landing_dir(), {"lock": json.dumps(
            {"pid": pid, "run_id": "old", "kind": kind, "contract": contract,
             "started_at": "2026-10-05T00:00:00Z"})})

    def test_a_live_landing_of_another_contract_halts_this_one(self):
        kit = Kit(self._tmp.name)
        self.write_lock(kit, self.live_pid())
        _, execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "landing-in-progress",
                         "ONE lock serves every landing, whatever the contract")
        execm.assert_not_called()

    def test_a_live_landing_halts_a_record_baseline_too(self):
        kit = Kit(self._tmp.name)
        self.write_lock(kit, self.live_pid())
        self.launch(kit, argv=["--record-baseline", "--json"])
        report = json.loads((kit.landing_dir() / "_baseline" / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["outcome"], "landing-in-progress",
                         "a recording cannot overlap a landing's test run")

    def test_a_dead_pid_is_reclaimed_and_noted(self):
        kit = Kit(self._tmp.name)
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        self.write_lock(kit, dead.pid)
        _, execm, report = self.launch(kit)
        self.assertEqual(execm.call_count, 1, "a lock whose process is gone is reclaimed")
        self.assertIn("reclaim", json.dumps(report.get("notes", [])).lower(),
                      "the report notes the reclaimed lock")

    def test_one_lock_file_exists_during_the_landing_and_is_released_after(self):
        kit = Kit(self._tmp.name)
        seen = {}

        def child(argv, cwd=None):
            seen["entries"] = sorted(p.name for p in kit.landing_dir().iterdir()
                                     if p.name.startswith("lock"))
            seen["lock"] = json.loads((kit.landing_dir() / "lock").read_text(encoding="utf-8"))
            return 0

        self.launch(kit, exec_side_effect=child)
        self.assertEqual(seen.get("entries"), ["lock"], "exactly ONE lock file under the runtime root")
        self.assertEqual(seen["lock"]["pid"], os.getpid(), "the lock holds the launcher's pid")
        self.assertEqual(seen["lock"]["contract"], SLUG, "and the contract")
        self.assertEqual(seen["lock"]["kind"], "land", "and the kind")
        self.assertFalse((kit.landing_dir() / "lock").exists(), "the lock is released on exit")

    def test_the_report_is_written_on_a_halt(self):
        kit = Kit(self._tmp.name)
        self.write_lock(kit, self.live_pid())
        _, _, report = self.launch(kit)
        self.assertIsNotNone(report, "report.json is written on every exit")
        for key in ("run_id", "contract", "outcome", "gate", "detail", "remedy", "next_command"):
            self.assertIn(key, report, "the Landing Report carries %s" % key)


class TestLauncherStatus(LauncherCase):
    """--status reads the runtime root and reports; it mutates nothing."""

    ARGV = ["--contract", SLUG, "--status", "--json"]

    def write_lock(self, kit, pid):
        write_files(kit.landing_dir(), {"lock": json.dumps(
            {"pid": pid, "run_id": "old", "kind": "land", "contract": SLUG,
             "started_at": "2026-10-05T00:00:00Z"})})

    def dead_pid(self):
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait()
        return dead.pid

    def snapshot(self, kit):
        files = {}
        root = kit.landing_dir()
        if root.exists():
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    files[p.relative_to(root).as_posix()] = p.read_bytes()
        return files, git(kit.main, "worktree", "list", "--porcelain"), git(kit.main, "branch", "-a")

    def status(self, kit):
        before = self.snapshot(kit)
        code, execm, _ = self.launch(kit, argv=self.ARGV)
        execm.assert_not_called()
        self.assertEqual(self.snapshot(kit), before,
                         "--status mutates nothing: no lock, report, worktree or branch changed")
        return json.loads(self.stdout)

    def test_a_stale_lock_with_no_report_is_an_interrupted_run(self):
        kit = Kit(self._tmp.name)
        self.write_lock(kit, self.dead_pid())
        got = self.status(kit)
        self.assertEqual(got["state"], "interrupted",
                         "a lock whose process is gone and no report: the run was interrupted")

    def test_a_live_lock_is_a_live_run(self):
        kit = Kit(self._tmp.name)
        self.write_lock(kit, self.live_pid())
        self.assertEqual(self.status(kit)["state"], "live", "a lock held by a live process is live")

    def test_a_last_report_is_returned_when_nothing_is_running(self):
        kit = Kit(self._tmp.name)
        write_files(kit.landing_dir() / SLUG, {"report.json": json.dumps(
            {"run_id": "r9", "outcome": "children-still-open", "contract": SLUG})})
        got = self.status(kit)
        self.assertEqual(got["state"], "report", "no lock and a report: the last report")
        self.assertEqual(got["report"]["outcome"], "children-still-open", "the report is returned verbatim")

    def test_positive_control_nothing_recorded_is_none(self):
        kit = Kit(self._tmp.name)
        self.assertEqual(self.status(kit)["state"], "none", "no lock and no report: nothing to say")


class TestLauncherWorktreeLocation(LauncherCase):

    def landing_worktrees(self, kit):
        listing = git(kit.main, "worktree", "list", "--porcelain")
        return [l.split(" ", 1)[1].replace("\\", "/") for l in listing.splitlines()
                if l.startswith("worktree ") and l.rstrip().endswith("-land-394")]

    def phase(self, kit, path):
        write_files(kit.landing_dir() / SLUG,
                    {"phase.json": json.dumps({"run_id": "old", "phase": "p8", "worktree": str(path)})})

    def test_none_existing_creates_one_with_a_date_prefix(self):
        kit = Kit(self._tmp.name)
        self.launch(kit)
        found = self.landing_worktrees(kit)
        self.assertEqual(len(found), 1, "one landing worktree is created")
        self.assertRegex(found[0], r"/\d{8}-land-394$", "named <YYYYMMDD>-land-<parent issue>")

    def test_an_earlier_dates_worktree_is_reused_not_duplicated(self):
        kit = Kit(self._tmp.name)
        old = kit.add_worktree("20250101-land-394")
        self.phase(kit, old)
        self.launch(kit)
        found = self.landing_worktrees(kit)
        self.assertEqual(len(found), 1, "no second worktree is created")
        self.assertTrue(found[0].endswith("20250101-land-394"), "the earlier one is reused")

    def test_two_matching_worktrees_are_an_environment_failure(self):
        kit = Kit(self._tmp.name)
        kit.add_worktree("20250101-land-394")
        kit.add_worktree("20250102-land-394")
        _, execm, report = self.launch(kit)
        self.assertEqual(self.outcome(report), "environment-failure", "two matches halt")
        self.assertTrue("20250101-land-394" in report["detail"] and "20250102-land-394" in report["detail"],
                        "naming both")
        execm.assert_not_called()


# ===========================================================================
# Landing stage (P1 to P15), driven in a temporary repository
# ===========================================================================
UNIT_PASS = "test_ok (tests.U.test_ok) ... ok\n"
UNIT_FAIL = "test_x (tests.U.test_x) ... FAIL\ntest_ok (tests.U.test_ok) ... ok\n"


class Stage:
    """Real git in a temporary repo; every network, push and process edge is a recording fake."""

    EDGES = ("git_ls_remote", "tcp_probe", "_run_long", "git_push", "gh_pr_find", "gh_pr_create",
             "gh_pr_ready", "gh_pr_view", "gh_pr_merge", "gh_pr_edit_body", "verify_closing_link",
             "read_children", "gh_issue_state", "write_bookkeeping", "worktree_remove",
             "gh_auth_status")

    def __init__(self, case, kit, *, worktree_name="20260101-land-394"):
        self.case, self.kit = case, kit
        self.lc = case.mod()
        for name in self.EDGES + ("run_landing", "git_show", "git_merge", "git_commit"):
            case.fn(name)
        self.worktree = kit.add_worktree(worktree_name)
        self.calls = []
        self.argv_seen = []
        self.env_seen = []
        self.show_calls = []
        self.long_calls = []
        self.args_seen = {}
        self.pr = None
        self.children = children([(401, "CLOSED"), (402, "CLOSED")])
        self.link_verdict = "linked"
        self.remote_master = None
        self.pr_head = None
        self.view_lies_open = False
        self.mergeable = "MERGEABLE"
        self.push_result = (0, "")
        self.merge_result = (0, "")
        self.step_outputs = {"py-unit": UNIT_PASS}
        self.step_mutator = None
        self.remove_raises = None
        self.run_id = "run-1"
        self.auth_ok = True          # gh_auth_status
        self.probe_ok = True         # tcp_probe: every emulator reachable
        self.long_rc = {}            # marker in a _run_long command -> exit code to return
        self.ready_rc = (0, "")      # gh_pr_ready result

    # -- fakes ---------------------------------------------------------------
    def head(self):
        return git(self.worktree, "rev-parse", "HEAD")

    def _record(self, name, *a, **k):
        self.calls.append(name)
        self.args_seen.setdefault(name, []).append((a, k))

    def _dict(self):
        if self.pr is None:
            return None
        pr = dict(self.pr)
        if pr.get("headRefOid") is None:
            pr["headRefOid"] = self.head()
        return pr

    def install(self, stack):
        lc = self.lc
        orig_run, orig_show = lc._run, lc.git_show
        orig_merge, orig_commit = lc.git_merge, lc.git_commit
        stage = self

        def fake_run(cmd, *a, **k):
            stage.argv_seen.append([str(c) for c in cmd])
            if cmd and str(cmd[0]) == "gh":
                raise AssertionError("an unpatched gh edge reached _run: %r" % (cmd,))
            if len(cmd) > 1 and str(cmd[0]) == "git" and str(cmd[1]) == "push":
                raise AssertionError("a git push reached _run: %r" % (cmd,))
            return orig_run(cmd, *a, **k)

        def fake_show(ref, path, *a, **k):
            stage.show_calls.append((str(ref), str(path)))
            return orig_show(ref, path, *a, **k)

        def fake_long(cmd, *a, **k):
            stage._record("_run_long", cmd)
            stage.argv_seen.append([str(c) for c in cmd])
            stage.long_calls.append([str(c) for c in cmd])
            stage.env_seen.append(os.environ.get("CLAUDE_PROJECT_DIR"))
            joined = " ".join(str(c) for c in cmd)
            for marker, rc_forced in stage.long_rc.items():
                if marker in joined:
                    return (rc_forced, False)
            if stage.step_mutator:
                stage.step_mutator(stage.worktree)
            outs = [str(c) for c in cmd if str(c).endswith("out.txt")]
            rc = 0
            if outs:
                text = stage.step_outputs["py-unit"]
                Path(outs[0]).parent.mkdir(parents=True, exist_ok=True)
                Path(outs[0]).write_text(text, encoding="utf-8")
                rc = 1 if "FAIL" in text else 0
            return (rc, False)

        def fake_ls_remote(ref, *a, **k):
            stage._record("git_ls_remote", ref)
            if "master" in str(ref):
                return stage.remote_master or git(stage.kit.main, "rev-parse", "refs/remotes/origin/master")
            return git(stage.kit.main, "rev-parse", "refs/remotes/origin/%s" % PARENT)

        def fake_push(*a, **k):
            stage._record("git_push", *a, **k)
            return stage.push_result

        def fake_find(*a, **k):
            stage._record("gh_pr_find", *a, **k)
            return stage._dict()

        def fake_create(*a, **k):
            stage._record("gh_pr_create", *a, **k)
            stage.pr = {"number": 7, "state": "OPEN", "isDraft": False, "baseRefName": "master",
                        "headRefName": PARENT, "headRefOid": None,
                        "url": "https://example.test/o/r/pull/7"}
            return (0, stage.pr["url"])

        def fake_ready(*a, **k):
            stage._record("gh_pr_ready", *a, **k)
            if stage.pr and stage.ready_rc[0] == 0:
                stage.pr["isDraft"] = False
            return stage.ready_rc

        def fake_view(*a, **k):
            stage._record("gh_pr_view", *a, **k)
            pr = stage._dict() or {}
            if stage.pr_head:
                pr["headRefOid"] = stage.pr_head
            pr["mergeable"] = stage.mergeable
            if stage.view_lies_open and pr.get("state") == "MERGED":
                pr["state"] = "OPEN"
                pr.pop("mergeCommit", None)
            return pr

        def fake_merge(*a, **k):
            stage._record("gh_pr_merge", *a, **k)
            if stage.merge_result[0] == 0 and stage.pr:
                stage.pr["state"] = "MERGED"
                stage.pr["mergeCommit"] = {"oid": sha40("d")}
            return stage.merge_result

        def fake_remove(*a, **k):
            stage._record("worktree_remove", *a, **k)
            if stage.remove_raises:
                raise stage.remove_raises

        fakes = {
            "git_ls_remote": fake_ls_remote,
            "tcp_probe": lambda *a, **k: (stage._record("tcp_probe", *a, **k), stage.probe_ok)[1],
            "gh_auth_status": lambda *a, **k: (stage._record("gh_auth_status", *a, **k),
                                               stage.auth_ok)[1],
            "_run_long": fake_long, "git_push": fake_push, "gh_pr_find": fake_find,
            "gh_pr_create": fake_create, "gh_pr_ready": fake_ready, "gh_pr_view": fake_view,
            "gh_pr_merge": fake_merge,
            "gh_pr_edit_body": lambda *a, **k: (stage._record("gh_pr_edit_body", *a, **k), (0, ""))[1],
            "verify_closing_link": lambda *a, **k: (stage._record("verify_closing_link", *a, **k),
                                                    stage.link_verdict)[1],
            "read_children": lambda *a, **k: (stage._record("read_children", *a, **k), stage.children)[1],
            "gh_issue_state": lambda *a, **k: (stage._record("gh_issue_state", *a, **k), "CLOSED")[1],
            "write_bookkeeping": lambda *a, **k: stage._record("write_bookkeeping", *a, **k),
            "worktree_remove": fake_remove,
            "_run": fake_run, "git_show": fake_show,
            "git_merge": lambda *a, **k: (stage._record("git_merge", *a, **k), orig_merge(*a, **k))[1],
            "git_commit": lambda *a, **k: (stage._record("git_commit", *a, **k), orig_commit(*a, **k))[1],
        }
        for name, f in fakes.items():
            stack.enter_context(mock.patch.object(lc, name, side_effect=f))
        stack.enter_context(mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)))
        stack.enter_context(mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)))

    # -- run -----------------------------------------------------------------
    def run(self, **over):
        args = {"contract": SLUG, "parent": PARENT, "project_root": str(self.kit.main),
                "checkout": str(self.kit.main), "run_id": self.run_id,
                "worktree": str(self.worktree), "dry_run": False}
        args.update(over)
        saved_cwd = os.getcwd()
        saved_env = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        # An inherited working directory is the temporary folder, never this checkout (the
        # module guard refuses any git run that would resolve inside it).
        os.chdir(str(self.kit.tmp))
        try:
            with contextlib.ExitStack() as stack:
                self.install(stack)
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


class StageCase(LandCase):

    def setUp(self):
        self.mod()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def stage(self, subdir="", **kit_kwargs):
        root = Path(self._tmp.name) / subdir if subdir else Path(self._tmp.name)
        root.mkdir(parents=True, exist_ok=True)
        kit = Kit(root, **kit_kwargs)
        return Stage(self, kit)

    def src_change(self, kit=None):
        return {"src/feature.py": "x = 1\n"}

    def assertOutcome(self, report, outcome, why):
        self.assertEqual(report["outcome"], outcome, "%s. Report: %s %s" % (
            why, report.get("outcome"), report.get("detail")))


class TestStageHappyPathAndGates(StageCase):

    def test_positive_control_a_clean_world_lands_in_order(self):
        st = self.stage(parent_files=self.src_change())
        report = st.run()
        self.assertOutcome(report, "landed", "a clean world must land")
        order = [c for c in st.calls if c in ("git_push", "gh_pr_create", "verify_closing_link",
                                              "gh_pr_merge")]
        self.assertEqual(order, ["git_push", "gh_pr_create", "verify_closing_link", "gh_pr_merge"],
                         "push, open, verify the link, then merge (P9 to P13)")
        merge_args, merge_kw = st.args_seen["gh_pr_merge"][0]
        self.assertIn(st.head(), list(merge_args) + list(merge_kw.values()),
                      "the merge is pinned to the verified head commit H")
        self.assertEqual(report["verification"]["verdict"], "READY", "the verdict that allowed it")
        self.assertEqual(report["parent_issue_state_after"], "CLOSED", "P14 reads the parent issue")
        create_args, create_kw = st.args_seen["gh_pr_create"][0]
        self.assertTrue(any("Closes #394" in str(v) for v in list(create_args) + list(create_kw.values())),
                        "the parent pull request body carries the Closing Link")

    def test_blocked_verdict_comes_before_children_still_open(self):
        st = self.stage(verdicts={"t1-backend": "blocked"}, parent_files=self.src_change())
        st.children = children([(401, "OPEN"), (402, "OPEN")])
        self.assertOutcome(st.run(), "blocked-verdict", "gate 3 is read before gate 2")

    SETUP_CFG = {"id": "pkgs", "when_missing": "node_modules",
                 "command": ["py", "-3", "-c", "pass", "setup-marker"], "cwd": "."}

    def moved_master_stage(self, **kw):
        """A stage where master has a commit origin/<parent> lacks, so P7 HAS a merge to do.
        (In the default kit origin/<parent> already contains master's tip and P7 is skipped,
        which would make every 'git_merge never ran' assertion vacuous.)"""
        st = self.stage(**kw)
        st.kit.commit_remote("master", {"master-note.txt": "master moved on\n"})
        return st

    def test_children_still_open_stops_before_setup_and_merge(self):
        st = self.moved_master_stage(config=landing_config(setup=[self.SETUP_CFG]),
                                     parent_files=self.src_change())
        st.children = children([(401, "OPEN"), (402, "CLOSED")])
        report = st.run()
        self.assertOutcome(report, "children-still-open", "an open child halts")
        self.assertEqual(st.count("git_merge"), 0, "git_merge never ran, though master had moved")
        self.assertFalse(any("setup-marker" in " ".join(a) for a in st.argv_seen),
                         "no setup command ran")

    def test_positive_control_with_children_closed_setup_and_merge_do_run(self):
        st = self.moved_master_stage(config=landing_config(setup=[self.SETUP_CFG]),
                                     parent_files=self.src_change())
        self.assertOutcome(st.run(), "landed", "the same world with every child closed lands")
        self.assertTrue(any("setup-marker" in " ".join(a) for a in st.argv_seen),
                        "the setup entry runs once the gates before it pass")
        self.assertGreaterEqual(st.count("git_merge"), 1,
                                "and the merge runs: this is what the paired negative would have stopped")

    def test_a_setup_command_that_fails_is_an_environment_failure_before_the_merge(self):
        cfg = landing_config(setup=[dict(self.SETUP_CFG, command=[
            "py", "-3", "-c", "raise SystemExit(3)", "setup-marker"])])
        st = self.moved_master_stage(config=cfg, parent_files=self.src_change())
        st.long_rc = {"setup-marker": 3}
        report = st.run()
        self.assertOutcome(report, "environment-failure", "a failed setup entry (P6) is environment")
        self.assertEqual(st.count("git_merge"), 0, "P7 never ran after the setup failure")
        self.assertEqual(st.count("git_push"), 0, "and nothing was pushed")

    def test_an_unreachable_emulator_during_the_landing_is_an_environment_failure(self):
        cfg = landing_config(emulators=[dict(EMU_AZURITE, gates_steps=["py-unit"])])
        st = self.stage(config=cfg, parent_files=self.src_change())
        st.probe_ok = False
        report = st.run()
        self.assertOutcome(report, "environment-failure", "P8: an unreachable emulator is environment")
        self.assertEqual(report["verification"]["verdict"], "ENVIRONMENT", "never a regression verdict")
        self.assertFalse(any("run_unit" in " ".join(c) for c in st.long_calls),
                         "the gated step never launched")
        self.assertEqual(st.count("git_push"), 0, "nothing is pushed")

    def test_positive_control_a_reachable_emulator_lets_the_landing_run_its_steps(self):
        cfg = landing_config(emulators=[dict(EMU_AZURITE, gates_steps=["py-unit"])])
        st = self.stage(config=cfg, parent_files=self.src_change())
        self.assertOutcome(st.run(), "landed", "with the emulator reachable the world lands")
        self.assertIn("tcp_probe", st.calls, "fixture sanity: the emulator was probed")

    def test_a_failing_regenerator_is_regeneration_failed_and_pushes_nothing(self):
        regen = {"id": "gen", "paths": ["generated/**"], "triggers": ["src/**"],
                 "command": [["py", "-3", "-c", "raise SystemExit(5)", "regen-marker"]]}
        st = self.moved_master_stage(config=landing_config(regenerators=[regen]),
                                     parent_files=self.src_change())
        st.long_rc = {"regen-marker": 5}
        self.assertOutcome(st.run(), "regeneration-failed", "a regenerator that exits non-zero halts")
        self.assertEqual(st.count("git_push"), 0, "a halt never pushes")
        self.assertEqual(st.count("gh_pr_merge"), 0, "and never merges")

    def test_positive_control_the_same_regenerator_succeeding_lands(self):
        regen = {"id": "gen", "paths": ["generated/**"], "triggers": ["src/**"],
                 "command": [["py", "-3", "-c", "pass", "regen-marker"]]}
        st = self.moved_master_stage(config=landing_config(regenerators=[regen]),
                                     parent_files=self.src_change())
        self.assertOutcome(st.run(), "landed", "a regenerator that succeeds does not halt")

    def test_an_unauthenticated_gh_is_unverifiable_before_any_step_or_push(self):
        st = self.stage(parent_files=self.src_change())
        st.auth_ok = False
        report = st.run()
        self.assertOutcome(report, "unverifiable", "P2: gh must be authenticated, or nothing can be read")
        self.assertEqual(st.long_calls, [], "no verification step ran")
        self.assertEqual(st.count("git_push"), 0, "nothing is pushed")

    def test_gh_authentication_is_checked_before_the_push(self):
        st = self.stage(parent_files=self.src_change())
        self.assertOutcome(st.run(), "landed", "fixture sanity: the clean world lands")
        self.assertIn("gh_auth_status", st.calls, "P2 asks gh_auth_status")
        self.assertLess(st.calls.index("gh_auth_status"), st.calls.index("git_push"),
                        "authentication is checked at P2, before the P9 push")

    def test_a_missing_parent_brief_is_parent_unresolved(self):
        st = self.stage(with_parent_brief=False, parent_files=self.src_change())
        self.assertOutcome(st.run(), "parent-unresolved",
                           "no brief whose branch: is the parent branch (P1)")
        self.assertEqual(st.count("git_push"), 0, "nothing is pushed")

    def test_positive_control_the_parent_brief_present_resolves(self):
        st = self.stage(with_parent_brief=True, parent_files=self.src_change())
        self.assertNotEqual(st.run()["outcome"], "parent-unresolved",
                            "with the parent brief present the parent resolves")

    def test_verification_not_ready_stops_before_the_push(self):
        st = self.stage(parent_files=self.src_change())
        st.step_outputs["py-unit"] = UNIT_FAIL
        report = st.run()
        self.assertOutcome(report, "verification-not-ready", "a new failure is not READY")
        self.assertEqual(st.count("git_push"), 0, "nothing is pushed before READY (L-2)")
        self.assertEqual(st.count("gh_pr_create"), 0, "and no pull request is opened")

    def test_link_not_verified_stops_before_the_merge(self):
        st = self.stage(parent_files=self.src_change())
        st.link_verdict = "absent"
        self.assertOutcome(st.run(), "link-not-verified", "an unverified Closing Link halts")
        self.assertEqual(st.count("gh_pr_merge"), 0, "nothing is merged before P11 and P12 (L-2)")

    def test_a_record_missing_for_a_sub_task_is_not_complete(self):
        st = self.stage(parent_records=("t1-backend",), parent_files=self.src_change())
        self.assertOutcome(st.run(), "not-complete", "a sub-task without a record is not complete")
        self.assertEqual(st.count("git_push"), 0, "nothing is pushed")

    def test_an_unreadable_children_read_is_unverifiable(self):
        st = self.stage(parent_files=self.src_change())
        st.children = None
        self.assertOutcome(st.run(), "unverifiable", "an unreadable read is never 'all closed'")

    def test_a_landing_stage_parent_that_differs_from_the_briefs_is_ambiguous_parent(self):
        st = self.stage(parent_files=self.src_change())
        self.assertOutcome(st.run(parent="feature/other"), "ambiguous-parent",
                           "the landing's topology differing from --parent halts")

    def test_a_declared_parent_in_protected_branches_is_parent_is_default(self):
        cfg = landing_config(protectedBranches=["master", "main", PARENT])
        st = self.stage(config=cfg, parent_files=self.src_change())
        self.assertOutcome(st.run(), "parent-is-default", "a protected parent is refused (L-13)")

    def test_a_master_without_the_contract_landing_block_is_not_configured(self):
        st = self.stage(config=None, conventions_on_master=False, parent_files=self.src_change())
        self.assertOutcome(st.run(), "landing-not-configured",
                           "an absent block on master halts, even if the parent branch had one")

    def test_a_malformed_baseline_on_master_is_unreadable(self):
        st = self.stage(baseline="{not json", parent_files=self.src_change())
        self.assertOutcome(st.run(), "baseline-unreadable", "a malformed baseline halts")

    def test_a_push_refusal_is_push_rejected(self):
        st = self.stage(parent_files=self.src_change())
        st.push_result = (1, "rejected: non-fast-forward")
        self.assertOutcome(st.run(), "push-rejected", "a refused push halts")
        self.assertEqual(st.count("gh_pr_create"), 0, "no pull request after a refused push")

    def test_an_open_pull_request_with_another_base_is_pr_mismatch(self):
        st = self.stage(parent_files=self.src_change())
        st.pr = {"number": 7, "state": "OPEN", "isDraft": False, "baseRefName": "develop",
                 "headRefName": PARENT, "headRefOid": None}
        self.assertOutcome(st.run(), "pr-mismatch", "an adopted pull request must target the default branch")
        self.assertEqual(st.count("gh_pr_merge"), 0, "and nothing is merged")

    def test_a_conflicting_pull_request_is_not_mergeable(self):
        st = self.stage(parent_files=self.src_change())
        st.mergeable = "CONFLICTING"
        self.assertOutcome(st.run(), "not-mergeable", "P12 re-checks mergeability")
        self.assertEqual(st.count("gh_pr_merge"), 0, "and nothing is merged")

    def test_a_refused_merge_is_merge_refused(self):
        st = self.stage(parent_files=self.src_change())
        st.merge_result = (1, "head commit mismatch")
        self.assertOutcome(st.run(), "merge-refused", "a refused merge halts")

    def test_an_unconflictable_edit_on_both_sides_is_unresolvable_conflict(self):
        st = self.stage(base_files={"shared.txt": "line1\nline2\n"},
                        parent_files={"shared.txt": "parent\nline2\n", "src/feature.py": "x\n"})
        st.kit.commit_remote("master", {"shared.txt": "master\nline2\n"})
        report = st.run()
        self.assertOutcome(report, "unresolvable-conflict", "an unlisted conflicted path halts (L-6)")
        self.assertEqual(st.count("git_push"), 0, "a halt never pushes")
        self.assertEqual(st.count("gh_pr_merge"), 0, "and never merges into master")


class TestStageDryRun(StageCase):
    """--dry-run stops the landing stage after P5: P6 onward never runs."""

    MUTATING = ("git_merge", "git_commit", "git_push", "gh_pr_create", "gh_pr_ready",
                "gh_pr_edit_body", "gh_pr_merge", "write_bookkeeping", "worktree_remove", "_run_long")

    def test_a_dry_run_runs_no_setup_merge_step_push_or_pull_request(self):
        cfg = landing_config(setup=[TestStageHappyPathAndGates.SETUP_CFG])
        st = self.stage(config=cfg, parent_files=self.src_change())
        st.kit.commit_remote("master", {"master-note.txt": "master moved on\n"})
        report = st.run(dry_run=True)
        for edge in self.MUTATING:
            self.assertEqual(st.count(edge), 0, "a dry run must not call %s" % edge)
        self.assertFalse(any("setup-marker" in " ".join(a) for a in st.argv_seen), "no setup command ran")
        self.assertNotIn(report["outcome"], ("landed", "already-landed"), "a dry run never reports a landing")

    def test_positive_control_the_same_world_without_dry_run_lands(self):
        cfg = landing_config(setup=[TestStageHappyPathAndGates.SETUP_CFG])
        st = self.stage(config=cfg, parent_files=self.src_change())
        st.kit.commit_remote("master", {"master-note.txt": "master moved on\n"})
        self.assertOutcome(st.run(dry_run=False), "landed", "the identical world lands")
        self.assertGreaterEqual(st.count("git_merge"), 1, "so the dry run really did skip the merge")

    def test_a_dry_run_still_halts_on_a_gate_before_p6(self):
        st = self.stage(verdicts={"t1-backend": "blocked"}, parent_files=self.src_change())
        self.assertOutcome(st.run(dry_run=True), "blocked-verdict", "P3 is inside the dry-run range")


class TestStageResume(StageCase):
    """(f) L-10: resume asks the facts first."""

    MERGED = {"number": 5, "state": "MERGED", "isDraft": False, "baseRefName": "master",
              "headRefName": PARENT, "headRefOid": None, "mergeCommit": {"oid": sha40("d")}}

    def test_a_merged_pull_request_is_already_landed_with_bookkeeping_and_no_mutation(self):
        st = self.stage(parent_files=self.src_change())
        st.pr = dict(self.MERGED)
        report = st.run()
        self.assertOutcome(report, "already-landed", "a MERGED parent pull request is already landed")
        self.assertEqual(st.count("write_bookkeeping"), 1, "P15 bookkeeping is written")
        for edge in ("gh_pr_create", "gh_pr_ready", "gh_pr_merge", "gh_pr_edit_body", "git_push",
                     "git_merge"):
            self.assertEqual(st.count(edge), 0, "%s must not run on an already-landed contract" % edge)
        self.assertEqual(st.count("worktree_remove"), 1, "the landing worktree is removed")

    def test_a_rerun_after_merge_unconfirmed_writes_the_bookkeeping(self):
        st = self.stage(parent_files=self.src_change())
        st.view_lies_open = True
        self.assertOutcome(st.run(), "merge-unconfirmed",
                           "P14 cannot confirm a merge that gh reports OPEN")
        st.view_lies_open = False
        report = st.run()
        self.assertOutcome(report, "already-landed", "the rerun finds the merged pull request")
        self.assertEqual(st.count("write_bookkeeping"), 1,
                         "the rerun writes the bookkeeping the first run never reached")

    def test_a_ready_record_for_h_is_reused_while_the_worktree_is_clean(self):
        """MECHANISM THIS TEST RELIES ON: the rerun happens in the SAME landing worktree, which
        still stands at H (the P7 merge commit) after the push was rejected. P7 then merges
        master into H again; an M already contained in H is a no-op that keeps head H, so the
        head is unchanged and the READY record for H is reused. NOTE FOR A POSSIBLE CONTRACT L-10
        CLARIFICATION (reported, the contract is not changed here): the launcher's P0 detaches
        the worktree at origin/<parent> and resets it (L-15), which would DISCARD the local merge
        commit H after a P7 merge that was never pushed; through the real launcher, record reuse
        is therefore unreachable after a P7 merge unless H was pushed. This test drives the stage
        directly (run_landing in the same worktree) and does not cover that launcher interplay."""
        st = self.stage(parent_files=self.src_change())
        # master has a commit origin/<parent> lacks, so P7 really merges and H is a NEW merge
        # commit (in the default kit origin/<parent> already holds master's tip, P7 is skipped,
        # and H would be origin/<parent> itself).
        st.kit.commit_remote("master", {"master-note.txt": "master moved on\n"})
        st.push_result = (1, "rejected")
        self.assertOutcome(st.run(), "push-rejected", "first run verifies, then the push is refused")
        self.assertGreaterEqual(st.count("git_merge"), 1, "fixture sanity: P7 merged master (H is a merge)")
        first = len(st.long_calls)
        self.assertGreater(first, 0, "fixture sanity: the first run ran the verification steps")
        head_before = st.head()
        st.push_result = (0, "")
        self.assertOutcome(st.run(), "landed", "the rerun completes")
        self.assertEqual(st.head(), head_before, "the rerun landed the same head H")
        self.assertEqual(len(st.long_calls), first,
                         "a READY record for the same head with a clean worktree is reused: no step reruns")

    def test_positive_control_a_changed_head_does_not_reuse_the_record(self):
        st = self.stage(parent_files=self.src_change())
        st.kit.commit_remote("master", {"master-note.txt": "master moved on\n"})
        st.push_result = (1, "rejected")
        st.run()
        first = len(st.long_calls)
        first_head = st.head()
        self.assertGreater(first, 0, "fixture sanity: the first run ran the verification steps")
        # master moves again, and the worktree is put back at origin/<parent>: P7 now merges a
        # DIFFERENT master tip, so H differs without any clock dependence.
        git(st.worktree, "reset", "--hard", "origin/%s" % PARENT)
        st.kit.commit_remote("master", {"master-note-2.txt": "master moved again\n"})
        st.push_result = (0, "")
        st.run()
        self.assertNotEqual(st.head(), first_head, "fixture sanity: the second run produced another head")
        self.assertGreater(len(st.long_calls), first, "a different head is verified afresh")

    def test_a_draft_that_cannot_be_readied_is_pr_not_ready(self):
        st = self.stage(parent_files=self.src_change())
        st.pr = {"number": 7, "state": "OPEN", "isDraft": True, "baseRefName": "master",
                 "headRefName": PARENT, "headRefOid": None}
        st.ready_rc = (1, "GraphQL: not permitted")
        self.assertOutcome(st.run(), "pr-not-ready", "an adopted draft that gh cannot ready halts")
        self.assertEqual(st.count("gh_pr_ready"), 1, "fixture sanity: readying was attempted")
        self.assertEqual(st.count("gh_pr_merge"), 0, "and nothing is merged")

    def test_an_open_ready_pull_request_is_adopted_not_duplicated(self):
        st = self.stage(parent_files=self.src_change())
        st.pr = {"number": 7, "state": "OPEN", "isDraft": False, "baseRefName": "master",
                 "headRefName": PARENT, "headRefOid": None}
        self.assertOutcome(st.run(), "landed", "an adopted pull request lands")
        self.assertEqual(st.count("gh_pr_create"), 0, "no second pull request is created")
        self.assertEqual(st.count("gh_pr_ready"), 0, "a ready one is not readied again")

    def test_an_open_draft_pull_request_is_readied_once(self):
        st = self.stage(parent_files=self.src_change())
        st.pr = {"number": 7, "state": "OPEN", "isDraft": True, "baseRefName": "master",
                 "headRefName": PARENT, "headRefOid": None}
        self.assertOutcome(st.run(), "landed", "an adopted draft lands once readied")
        self.assertEqual(st.count("gh_pr_create"), 0, "no second pull request")
        self.assertEqual(st.count("gh_pr_ready"), 1, "the draft is marked ready exactly once")


class TestStageMasterAndHeadMoved(StageCase):
    """(g) L-9: the master tip is read fresh at P12, never from the P0 remote-tracking ref."""

    def test_master_moved_is_fed_by_a_fresh_ls_remote_even_when_the_tracking_ref_is_unchanged(self):
        st = self.stage(parent_files=self.src_change())
        st.remote_master = sha40("9")
        report = st.run()
        self.assertOutcome(report, "master-moved",
                           "the remote tip differs from M although origin/master still equals M locally")
        self.assertEqual(st.count("gh_pr_merge"), 0, "nothing is merged")
        self.assertEqual(
            git(st.kit.main, "rev-parse", "refs/remotes/origin/master"),
            git(st.kit.main, "rev-parse", "origin/master"),
            "fixture sanity: the remote-tracking ref was never moved")

    def test_p12_calls_git_ls_remote_after_the_push(self):
        st = self.stage(parent_files=self.src_change())
        st.run()
        self.assertIn("git_ls_remote", st.calls, "P12 must read the master tip with git_ls_remote")
        last_ls = max(i for i, c in enumerate(st.calls) if c == "git_ls_remote")
        self.assertGreater(last_ls, st.calls.index("git_push"),
                           "the read happens in P12, after P9's push, not at P0")

    def test_head_moved_when_the_pull_request_head_is_not_h(self):
        st = self.stage(parent_files=self.src_change())
        st.pr_head = sha40("f")
        report = st.run()
        self.assertOutcome(report, "head-moved", "headRefOid differs from the verified H")
        self.assertEqual(st.count("gh_pr_merge"), 0, "nothing is merged")


class TestStageDeliveryRecordSet(StageCase):
    """(p) Records are read from three fetched refs, never from any checkout's disk."""

    def rec(self, tid):
        return {REC_DIR + tid + ".yaml": record_yaml()}

    def test_records_spread_across_the_stable_branch_in_two_commits_are_all_found(self):
        st = self.stage(parent_records=(), parent_files=self.src_change())
        branch = "docs/%s-records" % SLUG
        st.kit.commit_remote(branch, self.rec("t1-backend"), "t1 record")
        st.kit.commit_remote(branch, self.rec("t2-frontend"), "t2 record on top")
        ahead = git(st.kit.main, "rev-list", "--count", "origin/master..origin/%s" % branch)
        self.assertEqual(ahead, "2", "fixture sanity: the second record was added on top, not re-cut")
        self.assertOutcome(st.run(), "landed", "both records are on the stable branch: complete")

    def test_positive_control_dropping_the_second_commit_is_not_complete(self):
        st = self.stage(parent_records=(), parent_files=self.src_change())
        st.kit.commit_remote("docs/%s-records" % SLUG, self.rec("t1-backend"), "t1 record")
        self.assertOutcome(st.run(), "not-complete", "without t2's commit the contract is not complete")

    def test_records_split_between_the_stable_branch_and_the_parent_are_found(self):
        st = self.stage(parent_records=("t1-backend",), parent_files=self.src_change())
        st.kit.commit_remote("docs/%s-records" % SLUG, self.rec("t2-frontend"), "t2 record")
        self.assertOutcome(st.run(), "landed", "t1 on the parent and t2 on the records branch")

    def test_a_record_only_on_the_operators_disk_is_not_seen(self):
        st = self.stage(parent_records=("t1-backend",), parent_files=self.src_change())
        write_files(st.kit.main, self.rec("t2-frontend"))
        self.assertOutcome(st.run(), "not-complete",
                           "the landing never reads records from any checkout's disk")


class TestStageGateSelfEdit(StageCase):
    """(t) L-16: the contract under test cannot edit the gate that tests it."""

    S_AND_BUILD = landing_config()
    BUILD_ONLY = landing_config(steps=[STEP_BUILD])

    def widened_parent_files(self):
        return {CONVENTIONS: conventions_text(self.BUILD_ONLY),
                BASELINE_FILE: json.dumps(BASELINE_WIDENED), "src/feature.py": "x = 1\n"}

    def reverted_parent_files(self):
        return {"src/feature.py": "x = 1\n"}

    def run_world(self, subdir="", **kit_kwargs):
        st = self.stage(subdir=subdir, **kit_kwargs)
        st.step_outputs["py-unit"] = UNIT_FAIL
        st.kit.commit_remote("master", {"master-note.txt": "master moved on\n"})
        return st, st.run()

    def test_a_contract_that_widens_the_baseline_and_removes_the_step_still_fails_its_own_landing(self):
        st, report = self.run_world(config=self.S_AND_BUILD, baseline=BASELINE_CLEAN,
                                    parent_files=self.widened_parent_files())
        self.assertOutcome(report, "verification-not-ready",
                           "master's step still runs and master's baseline still lacks the unit")
        self.assertTrue(any("py-unit" in " ".join(c) or "run_unit" in " ".join(c) for c in st.long_calls),
                        "the step the contract removed was still run (configuration read from master)")
        self.assertTrue(any("test_x" in f for f in report["verification"]["new_failures"]),
                        "U's failing test is a NEW failure under master's baseline")
        self.assertEqual(st.count("git_push"), 0, "so nothing is pushed")

    def test_the_verdict_equals_the_one_with_the_contracts_two_edits_reverted(self):
        _, with_edits = self.run_world(config=self.S_AND_BUILD, baseline=BASELINE_CLEAN,
                                       parent_files=self.widened_parent_files())
        _, reverted = self.run_world(subdir="reverted", config=self.S_AND_BUILD, baseline=BASELINE_CLEAN,
                                     parent_files=self.reverted_parent_files())
        self.assertEqual(with_edits["outcome"], reverted["outcome"],
                         "the two edits change nothing for their own landing")
        self.assertEqual(sorted(with_edits["verification"]["new_failures"]),
                         sorted(reverted["verification"]["new_failures"]),
                         "and the same failures read as new")

    def test_positive_control_the_same_edits_on_master_are_ready(self):
        st, report = self.run_world(config=self.BUILD_ONLY, baseline=BASELINE_WIDENED,
                                    parent_files=self.reverted_parent_files())
        self.assertOutcome(report, "landed", "placed on master, the widened gate is in force")
        self.assertEqual(report["verification"]["verdict"], "READY", "and the verdict is READY")

    def test_configuration_and_baseline_are_read_with_git_show_on_origin_master(self):
        st, _ = self.run_world(config=self.S_AND_BUILD, baseline=BASELINE_CLEAN,
                               parent_files=self.widened_parent_files())
        for path in (CONVENTIONS, BASELINE_FILE):
            reads = [ref for ref, p in st.show_calls if p == path]
            self.assertIn("origin/master", reads, "%s is read from origin/master" % path)
            self.assertEqual(sorted(set(reads) - {"origin/master"}), [],
                             "%s is never read from H, origin/<parent> or a checkout: read from %r"
                             % (path, reads))

    def test_a_different_block_and_baseline_written_to_the_operators_disk_are_ignored(self):
        disk_block = landing_config(steps=[STEP_UNIT, STEP_BUILD, dict(
            STEP_BUILD, id="disk-only", command=["py", "-3", "-c", "pass", "DISK-ONLY-MARKER"])])
        st = self.stage(config=self.S_AND_BUILD, baseline=BASELINE_CLEAN,
                        parent_files=self.reverted_parent_files())
        st.step_outputs["py-unit"] = UNIT_FAIL
        # Uncommitted edits in the operator checkout (the --checkout tree): a different block and
        # a baseline that would tolerate U. Neither is on origin/master.
        write_files(st.kit.main, {CONVENTIONS: conventions_text(disk_block),
                                  BASELINE_FILE: json.dumps(BASELINE_WIDENED)})
        dirty = git(st.kit.main, "status", "--porcelain", "--untracked-files=no")
        self.assertTrue(CONVENTIONS in dirty and BASELINE_FILE in dirty,
                        "fixture sanity: both disk edits are uncommitted modifications: %r" % dirty)
        report = st.run()
        self.assertOutcome(report, "verification-not-ready",
                           "the disk baseline is ignored, so U's failure is new under master's baseline")
        self.assertFalse(any("DISK-ONLY-MARKER" in " ".join(c) for c in st.long_calls + st.argv_seen),
                         "a step that exists only in the operator checkout's block never runs")
        self.assertEqual(sorted(set(r for r, p in st.show_calls if p in (CONVENTIONS, BASELINE_FILE))),
                         ["origin/master"], "both gate files were read from origin/master only")

    def test_positive_control_the_same_disk_baseline_committed_to_master_is_honoured(self):
        st = self.stage(config=self.S_AND_BUILD, baseline=BASELINE_WIDENED,
                        parent_files=self.reverted_parent_files())
        st.step_outputs["py-unit"] = UNIT_FAIL
        self.assertOutcome(st.run(), "landed",
                           "placed on master the widened baseline tolerates U (so the disk case above "
                           "fails only because the disk copy is ignored)")

    def test_a_value_only_on_the_parent_branch_is_not_used(self):
        only_parent = landing_config(steps=[STEP_UNIT, STEP_BUILD, dict(
            STEP_BUILD, id="parent-only", command=["py", "-3", "-c", "pass", "PARENT-ONLY-MARKER"])])
        st = self.stage(parent_files={CONVENTIONS: conventions_text(only_parent),
                                      "src/feature.py": "x = 1\n"})
        st.run()
        self.assertFalse(any("PARENT-ONLY-MARKER" in " ".join(c) for c in st.long_calls + st.argv_seen),
                         "a contractLanding value present only at origin/<parent> is NOT used")
        self.assertTrue(any("run_unit" in " ".join(c) for c in st.long_calls),
                        "the value at origin/master is")


class TestStageResultsAndHygiene(StageCase):
    """(r) Results live outside the tree; the tree must be unchanged by the steps."""

    def test_a_results_path_inside_the_worktree_is_not_configured(self):
        cfg = landing_config(steps=[dict(STEP_UNIT, results={"format": "unittest-text",
                                                             "path": "TestResults/out.txt"})])
        st = self.stage(config=cfg, parent_files=self.src_change())
        self.assertOutcome(st.run(), "landing-not-configured",
                           "results resolving inside the worktree are refused")
        self.assertEqual(st.long_calls, [], "and no step ran")

    def test_results_dir_is_outside_the_worktree_under_the_runtime_logs(self):
        st = self.stage(parent_files=self.src_change())
        st.run()
        outs = [a for call in st.long_calls for a in call if a.endswith("out.txt")]
        self.assertTrue(outs, "fixture sanity: the unit step ran")
        for out in outs:
            self.assertNotIn("{results_dir}", out, "the placeholder is substituted")
            self.assertFalse(norm(out).startswith(norm(st.worktree)),
                             "results never land inside the worktree: %s" % out)
            parts = Path(out).parts
            self.assertTrue(SLUG in parts and st.run_id in parts and "py-unit" in parts,
                            "results_dir is logs/landing/<contract>/<run_id>/<step id>: %s" % out)

    def test_an_untracked_file_appearing_during_a_step_is_not_ready(self):
        st = self.stage(parent_files=self.src_change())
        st.step_mutator = lambda wt: (Path(wt) / "stray.txt").write_text("x", encoding="utf-8")
        report = st.run()
        self.assertOutcome(report, "verification-not-ready",
                           "a step that dirties the tree (hygiene) is not READY")
        self.assertEqual(st.count("git_push"), 0, "nothing is pushed")

    def test_the_script_sets_claude_project_dir_to_the_main_root_for_its_children(self):
        st = self.stage(parent_files=self.src_change())
        st.run()
        self.assertTrue(st.env_seen, "fixture sanity: a step ran")
        for seen in st.env_seen:
            self.assertEqual(norm(seen or ""), norm(st.kit.main),
                             "L-14: CLAUDE_PROJECT_DIR is the explicit main root, never unset")


class TestStageWorktreeRemoval(StageCase):
    """(s) P15: a failing removal never changes the outcome."""

    def test_a_failing_worktree_remove_after_landed_keeps_landed_and_adds_the_note(self):
        st = self.stage(parent_files=self.src_change())
        st.remove_raises = RuntimeError("file in use")
        report = st.run()
        self.assertOutcome(report, "landed", "master is already merged, so the outcome stands")
        notes = [str(n).replace("\\", "/") for n in report["notes"]]
        expected = "worktree-not-removed: %s" % str(st.worktree).replace("\\", "/")
        self.assertIn(expected, notes, "the notes carry worktree-not-removed: <path>")

    def test_a_failing_worktree_remove_after_already_landed_keeps_already_landed(self):
        st = self.stage(parent_files=self.src_change())
        st.pr = dict(TestStageResume.MERGED)
        st.remove_raises = RuntimeError("file in use")
        report = st.run()
        self.assertOutcome(report, "already-landed", "a removal failure never changes the outcome")
        self.assertTrue(any(str(n).startswith("worktree-not-removed:") for n in report["notes"]),
                        "and the next run's P5 path can retry it: the note says so")


# ===========================================================================
# Self-checks that need no land_contract. They PASS TODAY by design: they prove the harness
# (the subprocess guard and the temporary-repository kit) works before any implementation
# exists, so a RED elsewhere is never a broken fixture.
# ===========================================================================
class TestSubprocessGuard(unittest.TestCase):

    def temp_clone(self):
        """A temporary clone whose origin is a temporary bare repository (the fixture shape)."""
        root = tempfile.mkdtemp(prefix="guardtest-")
        self.addCleanup(shutil.rmtree, root, True)
        bare, clone = Path(root) / "origin.git", Path(root) / "clone"
        git(root, "init", "--bare", str(bare))
        git(root, "clone", str(bare), str(clone))
        return clone

    def test_a_push_from_a_temporary_clone_to_a_remote_that_is_a_url_is_refused(self):
        clone = self.temp_clone()
        git(clone, "remote", "set-url", "origin", "https://github.com/o/r.git")
        self.assertTrue(self.refused(["git", "push", "origin", "HEAD:master"], cwd=clone),
                        "a named remote that resolves to a URL is a real remote, whatever the cwd")
        self.assertTrue(self.refused('"C:\\Program Files\\Git\\cmd\\git.exe" push origin master', cwd=clone),
                        "the quoted full-path spelling of the same push")

    def refused(self, cmd, cwd=None):
        return _guard_verdict(cmd, cwd or _SANDBOX["dir"]) is not None

    def test_the_four_gh_mutations_are_refused(self):
        for sub in ("merge", "create", "edit", "ready"):
            self.assertTrue(self.refused(["gh", "pr", sub, "5"]), "gh pr %s must be refused" % sub)

    def test_positive_control_gh_reads_and_a_harmless_git_are_allowed(self):
        self.assertFalse(self.refused(["gh", "pr", "view", "5"]), "gh pr view is a read")
        self.assertFalse(self.refused(["gh", "issue", "view", "394"]), "gh issue view is a read")
        self.assertFalse(self.refused(["git", "--version"]), "git in the sandbox is allowed")
        self.assertFalse(self.refused(["py", "-3", "-c", "pass"]), "an unrelated process is allowed")

    def test_the_sequence_is_found_after_global_options(self):
        self.assertTrue(self.refused(["gh", "-R", "o/r", "pr", "merge", "5"]), "gh -R o/r pr merge")
        self.assertTrue(self.refused(["gh", "--repo", "o/r", "pr", "create"]), "gh --repo o/r pr create")
        self.assertTrue(self.refused(["gh", "pr", "-R", "o/r", "merge", "5"]), "an option between pr and merge")
        self.assertFalse(self.refused(["git", "-C", str(self.temp_clone()), "push", "origin", "x"]),
                         "control: git -C <temporary clone> push is a fixture push into a temporary repo")
        self.assertTrue(self.refused(["git", "-c", "k=v", "-C", str(REPO_ROOT), "push"]),
                        "git -c k=v -C <this checkout> push")

    def test_the_sequence_is_found_anywhere_in_the_argv(self):
        self.assertTrue(self.refused(["py", "-3", "run.py", "gh", "pr", "merge", "5"]),
                        "a wrapper that passes the command through")
        self.assertTrue(self.refused(["env", "X=1", "gh", "pr", "merge"]), "env prefix")

    def test_strings_and_shell_wrappers_are_split_and_refused(self):
        self.assertTrue(self.refused("gh pr merge 5 --merge"), "a shell string")
        self.assertTrue(self.refused(["cmd", "/c", "gh pr merge 5"]), "cmd /c wrapper")
        self.assertTrue(self.refused("cmd.exe /c gh.exe pr ready 5"), "cmd.exe /c with gh.exe")
        self.assertTrue(self.refused(["bash", "-c", "gh pr edit 5 --body x"]), "bash -c wrapper")
        self.assertTrue(self.refused(["sh", "-c", "git -C . push origin HEAD:master"], cwd=REPO_ROOT),
                        "sh -c git push from this checkout")

    def test_a_git_push_passes_only_from_the_temporary_root(self):
        self.assertFalse(self.refused(["git", "push", "origin", "HEAD:refs/heads/x"], cwd=self.temp_clone()),
                         "the fixture's own push from a temporary clone passes")
        self.assertTrue(self.refused(["git", "push", "origin", "HEAD:refs/heads/x"], cwd=_SANDBOX["dir"]),
                        "from a temporary directory whose origin does not resolve to a temporary "
                        "path (not even a repository) it is refused: the remote is unverified")
        self.assertTrue(self.refused(["git", "push", "origin", "HEAD:refs/heads/x"], cwd=REPO_ROOT),
                        "the same push from this checkout is refused")

    GIT_FULL = r"C:\Program Files\Git\mingw64\bin\git.EXE"
    GH_FULL = r"C:\Program Files\GitHub CLI\gh.exe"

    def test_full_path_executables_in_list_form_are_identified_by_basename(self):
        git_exe = shutil.which("git") or self.GIT_FULL
        gh_exe = shutil.which("gh") or self.GH_FULL
        for exe in (git_exe, self.GIT_FULL):
            self.assertTrue(self.refused([exe, "status"], cwd=REPO_ROOT),
                            "%s is git: a run inside this checkout is refused" % exe)
        for exe in (gh_exe, self.GH_FULL):
            for sub in ("merge", "create", "edit", "ready"):
                self.assertTrue(self.refused([exe, "pr", sub, "5"]), "%s pr %s is refused" % (exe, sub))
            self.assertTrue(self.refused([exe, "issue", "close", "5"]), "%s issue close is refused" % exe)
        self.assertFalse(self.refused([git_exe, "--version"]), "control: a harmless full-path git runs")
        self.assertFalse(self.refused([gh_exe, "pr", "view", "5"]), "control: a full-path gh read runs")

    def test_a_single_string_with_a_quoted_windows_path_is_identified(self):
        self.assertTrue(self.refused('"C:\\Program Files\\Git\\cmd\\git.exe" status', cwd=REPO_ROOT),
                        "a quoted full-path git inside this checkout (posix splitting would eat the "
                        "backslashes)")
        self.assertTrue(self.refused('"C:\\Program Files\\Git\\cmd\\git.exe" push origin master',
                                     cwd=REPO_ROOT), "the quoted full-path git push")
        self.assertTrue(self.refused('"C:\\Program Files\\GitHub CLI\\gh.exe" pr merge 5'),
                        "a quoted full-path gh pr merge")
        self.assertTrue(self.refused('cmd /c ""C:\\Program Files\\GitHub CLI\\gh.exe" pr ready 5"'),
                        "a quoted full path inside a cmd /c wrapper")
        self.assertFalse(self.refused('"C:\\Program Files\\Git\\cmd\\git.exe" --version'),
                         "control: the same quoted path running something harmless")

    def test_git_dir_and_work_tree_feed_the_in_checkout_check(self):
        git_dir, tree = str(REPO_ROOT / ".git"), str(REPO_ROOT)
        forms = {
            "--git-dir v": ["git", "--git-dir", git_dir, "status"],
            "--git-dir=v": ["git", "--git-dir=" + git_dir, "status"],
            "--work-tree v": ["git", "--work-tree", tree, "status"],
            "--work-tree=v": ["git", "--work-tree=" + tree, "status"],
            "both, = form": ["git", "--git-dir=" + git_dir, "--work-tree=" + tree, "clean", "-fdx"],
            "both, split form": ["git", "--git-dir", git_dir, "--work-tree", tree, "clean", "-fdx"],
            "a push through --git-dir": ["git", "--git-dir=" + git_dir, "push", "origin", "HEAD:master"],
        }
        for label, argv in forms.items():
            self.assertTrue(self.refused(argv), "%s inside this checkout must be refused" % label)
        sandbox_tree = _SANDBOX["dir"]
        self.assertFalse(self.refused(["git", "--git-dir=" + os.path.join(sandbox_tree, ".git"),
                                       "--work-tree=" + sandbox_tree, "status"]),
                         "control: the same options pointing at the temporary sandbox are fine")

    def test_a_git_push_to_a_url_is_refused_even_from_the_temporary_root(self):
        for target in ("https://github.com/o/r.git", "git@github.com:o/r.git", "ssh://git@h/o/r.git"):
            self.assertTrue(self.refused(["git", "push", target, "HEAD:master"]),
                            "push to %s is a real remote, whatever the cwd" % target)
        self.assertFalse(self.refused(["git", "push", os.path.join(_SANDBOX["dir"], "origin.git"),
                                       "HEAD:refs/heads/x"]),
                         "control: a push to a temporary bare repository path passes")

    def test_gh_api_put_pulls_merge_is_refused_in_every_method_spelling(self):
        endpoint = "repos/o/r/pulls/5/merge"
        for method in (["-X", "PUT"], ["--method", "PUT"], ["-XPUT"], ["--method=PUT"], ["-X", "put"]):
            self.assertTrue(self.refused(["gh", "api"] + method + [endpoint]),
                            "gh api %s %s must be refused" % (" ".join(method), endpoint))
            self.assertTrue(self.refused(["gh", "api", endpoint] + method),
                            "the method after the endpoint too: %s" % " ".join(method))
        self.assertTrue(self.refused(["gh", "-R", "o/r", "api", "-X", "PUT", "/repos/o/r/pulls/5/merge"]),
                        "after a global option, with a leading slash")
        self.assertFalse(self.refused(["gh", "api", "repos/o/r/pulls/5"]), "control: a GET of a pull request")
        self.assertFalse(self.refused(["gh", "api", "-X", "PUT", "repos/o/r/issues/5/labels"]),
                         "control: a PUT that is not a merge")

    def test_gh_issue_close_is_refused_and_a_read_is_not(self):
        self.assertTrue(self.refused(["gh", "issue", "close", "394"]), "gh issue close mutates GitHub")
        self.assertTrue(self.refused(["gh", "-R", "o/r", "issue", "close", "394", "--reason", "completed"]),
                        "after a global option")
        self.assertFalse(self.refused(["gh", "issue", "view", "394"]), "control: gh issue view is a read")

    def test_the_launchers_were_patched_before_land_contract_was_imported(self):
        self.assertTrue(_INSTALLED_BEFORE_IMPORT,
                        "subprocess.Popen, os.system and os.popen are replaced at module top, BEFORE "
                        "the guarded import, so a from-import inside land_contract keeps the guard")
        self.assertIs(subprocess.Popen, _GuardedPopen, "and they are installed now")

    def test_any_real_gh_call_is_unauthenticated_in_this_environment(self):
        for key in _GH_ENV_KEYS:
            self.assertNotIn(key, os.environ, "%s is removed for the module run" % key)
        config = os.environ.get("GH_CONFIG_DIR")
        self.assertTrue(config, "GH_CONFIG_DIR points somewhere")
        self.assertTrue(_is_under(config, _TEMP_ROOT), "inside the temporary root, never ~/.config/gh")
        self.assertTrue(os.path.isdir(config), "and the directory exists")
        self.assertEqual(os.listdir(config), [], "and is EMPTY: no hosts.yml, so gh holds no login")

    def test_any_git_run_inside_this_checkout_is_refused_explicit_or_inherited(self):
        self.assertTrue(self.refused(["git", "status"], cwd=REPO_ROOT), "explicit cwd inside the checkout")
        self.assertTrue(self.refused(["git", "status"], cwd=REPO_ROOT / ".claude" / "scripts"),
                        "a subfolder of the checkout")
        saved = os.getcwd()
        os.chdir(str(REPO_ROOT))
        try:
            self.assertTrue(_guard_verdict(["git", "status"]) is not None,
                            "an INHERITED cwd inside the checkout is refused too")
        finally:
            os.chdir(saved)
        self.assertFalse(self.refused(["git", "status"]), "control: the sandbox cwd is fine")

    def test_the_real_launchers_are_guarded_not_only_subprocess_run(self):
        calls = (
            lambda: subprocess.run(["gh", "pr", "merge", "5"]),
            lambda: subprocess.run("gh pr merge 5", shell=True),
            lambda: subprocess.Popen(["gh", "pr", "create"]),
            lambda: subprocess.check_output(["gh", "pr", "ready", "5"]),
            lambda: subprocess.call(["git", "push", "origin", "x"], cwd=str(REPO_ROOT)),
            lambda: subprocess.run(["git", "status"], cwd=str(REPO_ROOT)),
            lambda: os.system("gh pr merge 5"),
        )
        for call in calls:
            with self.assertRaises(RuntimeError, msg="the launcher must refuse before any process starts"):
                call()

    def test_positive_control_a_harmless_command_still_runs_through_the_guard(self):
        proc = subprocess.run([sys.executable, "-c", "print('ok')"], capture_output=True, text=True)
        self.assertEqual(proc.stdout.strip(), "ok", "the guard must not block ordinary processes")


class TestGuardCoversWhatLandContractImports(LandCase):

    def test_land_contract_holds_no_real_process_launcher_under_any_name(self):
        lc = self.mod()
        real = {"subprocess.Popen": _REAL_POPEN, "os.system": _REAL_OS_SYSTEM, "os.popen": _REAL_OS_POPEN}
        for name, value in vars(lc).items():
            for label, original in real.items():
                self.assertIsNot(value, original,
                                 "land_contract.%s is the real %s: a from-import kept the unguarded "
                                 "launcher" % (name, label))


class TestKitFixtureShape(unittest.TestCase):
    """The Kit is the foundation of the launcher and stage tests: pin its shape."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.kit = Kit(self._tmp.name)

    def is_ancestor(self, ancestor, descendant):
        return _REAL_SUBPROCESS_RUN(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=str(self.kit.main), capture_output=True, env=_GIT_ENV).returncode == 0

    def test_the_briefs_are_untracked_files_on_the_operators_disk(self):
        tracked = git(self.kit.main, "ls-files").splitlines()
        status = git(self.kit.main, "status", "--porcelain", "--untracked-files=all")
        self.assertTrue(self.kit.brief_files, "fixture sanity: the kit has briefs")
        for rel in self.kit.brief_files:
            self.assertTrue((self.kit.main / rel).exists(), "%s is on the operator's disk" % rel)
            self.assertNotIn(rel, tracked, "%s is not tracked on master" % rel)
            self.assertIn("?? " + rel, status, "%s reads as untracked" % rel)

    def test_the_operator_checkout_is_on_master_with_a_clean_tracked_tree(self):
        self.assertEqual(git(self.kit.main, "rev-parse", "--abbrev-ref", "HEAD"), "master",
                         "the operator checkout stands on the default branch")
        self.assertEqual(git(self.kit.main, "status", "--porcelain", "--untracked-files=no"), "",
                         "no tracked modification (the disk-edit tests rely on this baseline)")

    def test_the_parent_branch_descends_from_master_and_holds_records_and_the_script(self):
        self.assertTrue(self.is_ancestor("origin/master", "origin/%s" % PARENT),
                        "by default origin/<parent> already contains master's tip, so P7 is skipped")
        listing = git(self.kit.main, "ls-tree", "-r", "--name-only", "origin/%s" % PARENT).splitlines()
        self.assertIn(".claude/scripts/land_contract.py", listing, "the landing code is at origin/<parent>")
        self.assertIn(REC_DIR + "t1-backend.yaml", listing, "t1's record is on the parent")
        self.assertIn(REC_DIR + "t2-frontend.yaml", listing, "t2's record is on the parent")
        self.assertNotIn(REC_DIR + "t1-backend.yaml",
                         git(self.kit.main, "ls-tree", "-r", "--name-only", "origin/master").splitlines(),
                         "and master holds none")

    def test_moving_master_makes_the_parent_lack_its_tip(self):
        self.kit.commit_remote("master", {"master-note.txt": "x\n"})
        self.assertFalse(self.is_ancestor("origin/master", "origin/%s" % PARENT),
                         "after a remote master commit, P7 has a real merge to do")
        self.assertEqual(git(self.kit.main, "rev-parse", "origin/master"),
                         git(self.kit.scratch, "rev-parse", "HEAD"),
                         "and the operator checkout fetched it")

    def test_remote_commits_to_one_branch_stack_instead_of_recutting_it(self):
        branch = "docs/%s-records" % SLUG
        self.kit.commit_remote(branch, {"one.txt": "1\n"}, "first")
        self.kit.commit_remote(branch, {"two.txt": "2\n"}, "second")
        self.assertEqual(git(self.kit.main, "rev-list", "--count", "origin/master..origin/%s" % branch),
                         "2", "the second commit sits on top of the first")
        listing = git(self.kit.main, "ls-tree", "-r", "--name-only", "origin/%s" % branch).splitlines()
        self.assertTrue("one.txt" in listing and "two.txt" in listing, "both files survive on the branch")

    def test_the_parent_brief_can_be_left_out(self):
        other = Path(self._tmp.name) / "no-parent-brief"
        other.mkdir()
        kit = Kit(other, with_parent_brief=False)
        self.assertFalse((kit.main / BRIEF_DIR / "2026-10-05-394-demo.md").exists(),
                         "with_parent_brief=False leaves the parent brief out of the kit")
        self.assertTrue((self.kit.main / BRIEF_DIR / "2026-10-05-394-demo.md").exists(),
                        "positive control: the default kit has it")


# ===========================================================================
# Review gate remedy (t7): clauses of the landing gate that no test could turn red
# ===========================================================================
REVIEWER = "acme-reviewer"
REVIEW_ARTEFACT = ".claude/reviews/demo/t1-backend-%s.md" % REVIEWER
COVERAGE_CFG = [{"reviewer": REVIEWER, "paths": ["src/**"]}]
CONTRACT_WITH_ARTEFACT = CONTRACT_TEXT.replace("- src/Foo.cs\n", "- src/Foo.cs\n- %s\n" % REVIEW_ARTEFACT)
NO_VERDICT_RECORD = "status: completed\nverified: github\npull_request: u\n"


class TestStageReviewCoverageOfTheVerdict(StageCase):
    """L-7 bullet four: a READY verdict needs a passing review artefact for every required reviewer."""

    def coverage_stage(self, contract=CONTRACT_TEXT, subdir="", **kw):
        base = {".claude/concepts/%s.md" % SLUG: contract}
        return self.stage(subdir=subdir, config=landing_config(reviewCoverage=COVERAGE_CFG), base_files=base,
                          parent_files=self.src_change(), **kw)

    def test_a_required_reviewer_with_no_artefact_in_any_task_file_list_is_not_ready(self):
        st = self.coverage_stage()
        report = st.run()
        self.assertOutcome(report, "verification-not-ready", "src/** needs acme-reviewer and no artefact names it")
        self.assertIn(REVIEWER, " ".join(report["verification"]["reasons"]),
                      "the reason must name the reviewer whose artefact is missing")
        self.assertEqual(st.count("git_push"), 0, "nothing is pushed before READY (L-2)")

    def test_positive_control_an_artefact_in_a_task_file_list_with_a_pass_record_lands(self):
        for verdict in ("pass", "pass-with-findings"):
            with self.subTest(verdict=verdict):
                st = self.coverage_stage(contract=CONTRACT_WITH_ARTEFACT, subdir=verdict,
                                         verdicts={"t1-backend": verdict})
                self.assertOutcome(st.run(), "landed",
                                   "the same world with the artefact and a passing record lands")

    def test_an_artefact_whose_record_carries_no_verdict_does_not_satisfy_the_reviewer(self):
        parent_files = dict(self.src_change(), **{REC_DIR + "t1-backend.yaml": NO_VERDICT_RECORD})
        st = self.stage(config=landing_config(reviewCoverage=COVERAGE_CFG), parent_files=parent_files,
                        base_files={".claude/concepts/%s.md" % SLUG: CONTRACT_WITH_ARTEFACT})
        report = st.run()
        self.assertOutcome(report, "verification-not-ready",
                           "the artefact is named but the record has no passing verdict (P3 lets a missing "
                           "key pass; coverage does not)")
        self.assertIn(REVIEWER, " ".join(report["verification"]["reasons"]), "the unsatisfied reviewer is named")

    def test_a_record_with_no_verdict_key_passes_p3_when_no_coverage_is_required(self):
        parent_files = dict(self.src_change(), **{REC_DIR + "t1-backend.yaml": NO_VERDICT_RECORD})
        st = self.stage(parent_files=parent_files)
        self.assertOutcome(st.run(), "landed",
                           "L-5: a record with no review_verdict key passes, as in compute_released")


class TestStageP3HaltsOnEveryNonPassVerdict(StageCase):
    """L-5: blocked, unreadable, unfetched and cross-repository halt alike."""

    def test_every_non_pass_verdict_is_a_blocked_verdict_halt(self):
        for verdict in ("blocked", "unreadable", "unfetched", "cross-repository"):
            with self.subTest(verdict=verdict):
                st = self.stage(subdir=verdict, verdicts={"t1-backend": verdict}, parent_files=self.src_change())
                report = st.run()
                self.assertOutcome(report, "blocked-verdict", "L-5: %s halts at P3" % verdict)
                self.assertEqual(st.count("git_push"), 0, "a halt never pushes")
                self.assertEqual(st.count("gh_pr_merge"), 0, "and never merges")


class TestStageAlreadyLandedNamesBaseAndHead(StageCase):

    def merged(self, **over):
        pr = dict(TestStageResume.MERGED)
        pr.update(over)
        return pr

    def test_a_pull_request_merged_into_another_base_is_not_already_landed(self):
        st = self.stage(parent_files=self.src_change())
        st.pr = self.merged(baseRefName="develop")
        report = st.run()
        self.assertNotEqual(report["outcome"], "already-landed", "a merge into develop never reached master")
        self.assertEqual(st.count("write_bookkeeping"), 0, "no bookkeeping is written for it")

    def test_a_merged_pull_request_from_another_head_is_not_already_landed(self):
        st = self.stage(parent_files=self.src_change())
        st.pr = self.merged(headRefName="feature/other")
        report = st.run()
        self.assertNotEqual(report["outcome"], "already-landed", "another head branch is another contract")
        self.assertEqual(st.count("write_bookkeeping"), 0, "no bookkeeping is written for it")


class TestStageMergePinAndConflicts(StageCase):

    def test_the_merge_is_pinned_to_h_not_to_the_parent_tip_when_master_moved(self):
        st = self.stage(parent_files=self.src_change())
        st.kit.commit_remote("master", {"master-note.txt": "master moved on\n"})
        parent_tip = git(st.kit.main, "rev-parse", "refs/remotes/origin/%s" % PARENT)
        report = st.run()
        self.assertOutcome(report, "landed", "fixture sanity: the moved-master world lands")
        merge_args, merge_kw = st.args_seen["gh_pr_merge"][0]
        seen = list(merge_args) + list(merge_kw.values())
        self.assertNotEqual(st.head(), parent_tip, "fixture sanity: H differs from the parent tip at P0")
        self.assertIn(st.head(), seen, "the merge is pinned to H, the verified merge commit")
        self.assertNotIn(parent_tip, seen, "and never to the parent tip read at P0")

    def test_a_registry_heading_added_on_both_sides_is_united_and_lands(self):
        cfg = landing_config(unionPaths=[{"glob": "reg.md", "entryKey": "heading"}])
        st = self.stage(config=cfg, base_files={"reg.md": "## A\n- a\n"},
                        parent_files={"reg.md": "## A\n- a\n## P\n- p\n", "src/feature.py": "x\n"})
        st.kit.commit_remote("master", {"reg.md": "## A\n- a\n## M\n- m\n"})
        report = st.run()
        self.assertOutcome(report, "landed", "a union path with insert-only hunks is united, never a halt")
        text = (st.worktree / "reg.md").read_text(encoding="utf-8")
        for heading in ("## A", "## P", "## M"):
            self.assertEqual(text.splitlines().count(heading), 1, "%s appears once in H" % heading)

    def test_a_regenerated_path_takes_the_default_branchs_side(self):
        regen = {"id": "gen", "paths": ["generated/**"], "triggers": ["nothing/**"],
                 "command": [["py", "-3", "-c", "pass", "regen-marker"]]}
        st = self.stage(config=landing_config(regenerators=[regen]), base_files={"generated/out.txt": "base\n"},
                        parent_files={"generated/out.txt": "parent\n", "src/feature.py": "x\n"})
        st.kit.commit_remote("master", {"generated/out.txt": "master\n"})
        report = st.run()
        self.assertOutcome(report, "landed", "a conflict under a regenerator's paths is resolved, not a halt")
        self.assertEqual((st.worktree / "generated" / "out.txt").read_text(encoding="utf-8").strip(), "master",
                         "H holds the default branch's version of a regenerated path")


class TestStageHygieneClauses(StageCase):

    def test_a_forbidden_path_in_the_contract_diff_is_not_ready(self):
        cfg = landing_config(forbiddenPaths=["*.pem"])
        st = self.stage(config=cfg, parent_files=dict(self.src_change(), **{"secrets.pem": "key\n"}))
        report = st.run()
        self.assertOutcome(report, "verification-not-ready", "forbiddenPaths names *.pem and the diff holds one")
        self.assertIn("secrets.pem", " ".join(report["verification"]["reasons"]), "the reason names the path")
        self.assertEqual(st.count("git_push"), 0, "nothing is pushed")

    def test_positive_control_forbidden_paths_set_but_no_match_lands(self):
        st = self.stage(config=landing_config(forbiddenPaths=["*.pem"]), parent_files=self.src_change())
        self.assertOutcome(st.run(), "landed", "the same configuration with no forbidden path lands")

    def test_a_step_that_moves_head_with_a_clean_status_is_not_ready(self):
        st = self.stage(parent_files=self.src_change())
        st.step_mutator = lambda wt: git(Path(wt), "commit", "--allow-empty", "-m", "step commit")
        report = st.run()
        self.assertOutcome(report, "verification-not-ready", "HEAD must still equal H after the steps")
        self.assertEqual(st.count("git_push"), 0, "nothing is pushed")


class PerReadChildrenStage(Stage):
    """A Stage whose read_children answers the first read with closed children and later reads with an open one."""

    OPEN = children([(401, "OPEN"), (402, "CLOSED")])
    CLOSED = children([(401, "CLOSED"), (402, "CLOSED")])

    @property
    def children(self):
        return self.CLOSED if len(self.args_seen.get("read_children", [])) <= 1 else self.OPEN

    @children.setter
    def children(self, value):
        pass


class TestStageP12RereadsTheChildren(StageCase):

    def test_a_child_reopened_between_p4_and_p12_stops_the_merge(self):
        kit = Kit(Path(self._tmp.name), parent_files=self.src_change())
        st = PerReadChildrenStage(self, kit)
        report = st.run()
        self.assertOutcome(report, "children-still-open",
                           "P12 reads the child issues again and sees the reopened one")
        self.assertGreaterEqual(st.count("read_children"), 2, "the children were read at P4 and again at P12")
        self.assertEqual(st.count("gh_pr_merge"), 0, "nothing is merged")


class TestContainmentScanExtensions(LandCase):

    def found_in_fixture(self, rel, text):
        return TestContainmentScanner.found_in_fixture(self, rel, text)

    def test_a_powershell_script_spelling_the_merge_is_found(self):
        found = self.found_in_fixture(".claude/scripts/f.ps1", "gh pr merge 12 --merge\n")
        self.assertTrue(any(p == ".claude/scripts/f.ps1" for p, _ in found), "a .ps1 file is scanned: %r" % found)

    def test_a_json_registration_spelling_the_merge_is_found(self):
        found = self.found_in_fixture(".claude/hooks/f.json", '{"command": "gh pr merge 12 --merge"}\n')
        self.assertTrue(any(p == ".claude/hooks/f.json" for p, _ in found), "a .json file is scanned: %r" % found)


if __name__ == "__main__":
    unittest.main(verbosity=2)
