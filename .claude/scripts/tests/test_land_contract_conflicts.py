#!/usr/bin/env python3
"""
Tests for W5 (L-6'): union admissibility judged per Conflict region, in land_contract.py
(contract 2026-10-07-landing-and-loop-hardening, block 5).

RED-phase file. Pinned shape: ``conflict_regions(base, ours, theirs)`` returns a list of
{"base": [lines], "ours": [lines], "theirs": [lines]}, one per conflict hunk in file order, and
equals the hunks parsed from ``git merge-file -p --diff3 ours base theirs`` over the same texts.
``merge_union(base, ours, theirs, entry_key)`` keeps its signature and {ok, text, reason} result.

Fixtures are built in the tests with neutral headings; no real registry is read (this file is
mirrored to the plugin). The module guard, guarded import and ``fn`` lookup are copied from
test_land_contract.py, so a missing function is an AssertionError, never an ImportError.
Run with ``py -3 -B``.

Tests that pass TODAY by design (they pin behaviour that must stay): every test whose name
contains ``passes_today_by_design``.
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
# Structural guard (copied from test_land_contract.py). No test here may reach a real GitHub
# mutation or a real push, and no test may run git inside the checkout this file lives in.
# The launchers are patched at MODULE TOP, before the guarded import of land_contract below.
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

_SANDBOX = {"dir": None, "cwd": None, "gh_config": None, "env": {}}


def setUpModule():
    _install_guards()  # idempotent: another module's tearDown may have restored the real ones
    _SANDBOX["cwd"] = os.getcwd()
    _SANDBOX["dir"] = tempfile.mkdtemp(prefix="landtest-cwd-")
    os.chdir(_SANDBOX["dir"])  # an inherited working directory is never this checkout
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
            "land_contract.py does not exist (.claude/scripts/land_contract.py)")
        return land_contract

    def fn(self, name):
        m = self.mod()
        f = getattr(m, name, None)
        self.assertIsNotNone(f, "land_contract.%s does not exist yet" % name)
        return f


_GIT_ENV = dict(os.environ,
                GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.test",
                GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.test")


def write_files(root, files):
    for rel, text in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")


def run_merge_file(base, ours, theirs):
    """Hunks of ``git merge-file -p --diff3 ours base theirs`` over three temporary files."""
    root = tempfile.mkdtemp(prefix="landtest-regions-")
    try:
        write_files(root, {"ours.txt": ours, "base.txt": base, "theirs.txt": theirs})
        proc = _REAL_SUBPROCESS_RUN(
            ["git", "-c", "core.autocrlf=false", "merge-file", "-p", "--diff3",
             "-L", "ours", "-L", "base", "-L", "theirs", "ours.txt", "base.txt", "theirs.txt"],
            cwd=root, capture_output=True, text=True, env=_GIT_ENV)
        if proc.returncode < 0 or proc.returncode > 127:
            raise AssertionError("fixture git merge-file failed: %s" % proc.stderr)
        return parse_hunks(proc.stdout)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def parse_hunks(text):
    hunks, current, section = [], None, None
    for line in text.splitlines():
        if line.startswith("<<<<<<< "):
            current, section = {"base": [], "ours": [], "theirs": []}, "ours"
        elif current is not None and line.startswith("||||||| "):
            section = "base"
        elif current is not None and line == "=======":
            section = "theirs"
        elif current is not None and line.startswith(">>>>>>> "):
            hunks.append(current)
            current, section = None, None
        elif current is not None:
            current[section].append(line)
    return hunks


# Registry text built here, neutral headings. A is the LAST entry, so appends touch its tail.
BASE = "# T\n\n## A\n- **Trigger:** x\n- a1\n- a2\n"


class TestMergeUnionPerRegion(LandCase):

    def merge(self, base, ours, theirs, key="heading"):
        return self.fn("merge_union")(base, ours, theirs, key)

    def test_a_line_rewritten_inside_an_entry_unites_with_appends_on_both_sides(self):
        # the t6 P1 probe, inverted: master edits a line inside A and appends M; the parent appends P
        master = BASE.replace("- a2\n", "- a2 edited by master\n") + "## M\n- m\n"
        parent = BASE + "## P\n- p\n"
        self.assertGreaterEqual(len(run_merge_file(BASE, master, parent)), 1,
                                "positive control: git itself reports a conflict for this fixture")
        r = self.merge(BASE, master, parent)
        self.assertTrue(r["ok"], "the edit and the appends are compatible: %s" % r.get("reason"))
        lines = r["text"].splitlines()
        self.assertIn("- a2 edited by master", lines,
                      "master's rewrite of a line inside entry A must survive in the union")
        self.assertNotIn("- a2", lines, "the rewritten line must not come back unedited")
        self.assertEqual(lines.count("## M"), 1, "master's appended heading appears exactly once")
        self.assertEqual(lines.count("## P"), 1, "the parent's appended heading appears exactly once")

    def test_an_edit_inside_a_conflict_region_still_halts_passes_today_by_design(self):
        master = BASE.replace("- a2\n", "- a2 master\n")
        parent = BASE.replace("- a2\n", "- a2 parent\n")
        self.assertEqual(len(run_merge_file(BASE, master, parent)), 1,
                         "positive control: both sides edit one line, git reports one conflict")
        r = self.merge(BASE, master, parent)
        self.assertFalse(r["ok"], "two different edits of one base line cannot be united")
        self.assertIn("only insert-only hunks can be united", r["reason"],
                      "the existing reason text is kept for a region that fails")

    def test_the_same_heading_inserted_on_both_sides_with_different_bodies_halts_passes_today_by_design(self):
        r = self.merge(BASE, BASE + "## X\n- from master\n", BASE + "## X\n- from parent\n")
        self.assertFalse(r["ok"], "one heading inserted twice with different bodies is a duplicate")
        self.assertIn("would appear 2 times", r["reason"], "the key check reports the count")

    def test_a_heading_inserted_that_is_already_in_base_once_halts_passes_today_by_design(self):
        r = self.merge(BASE, BASE + "## A\n- again\n", BASE + "## P\n- p\n")
        self.assertFalse(r["ok"], "A is in base once; inserting it again makes two")

    def test_repeated_field_lines_still_pass_passes_today_by_design(self):
        r = self.merge(BASE, BASE + "## M\n- **Trigger:** x\n", BASE + "## P\n- **Trigger:** x\n")
        self.assertTrue(r["ok"], "'- **Trigger:**' lines are not entry keys: %s" % r.get("reason"))

    def test_two_byte_identical_insertions_collapse_to_one_copy_passes_today_by_design(self):
        same = BASE + "## S\n- s\n"
        r = self.merge(BASE, same, same)
        self.assertTrue(r["ok"], "identical insertions on both sides are one insertion (I3): %s"
                        % r.get("reason"))
        self.assertEqual(r["text"].splitlines().count("## S"), 1, "exactly one copy remains")


class TestConflictRegions(LandCase):

    def regions(self, base, ours, theirs):
        return self.fn("conflict_regions")(base, ours, theirs)

    def test_regions_equal_the_hunks_git_merge_file_reports_for_the_p1_fixture(self):
        master = BASE.replace("- a2\n", "- a2 edited by master\n") + "## M\n- m\n"
        parent = BASE + "## P\n- p\n"
        expected = run_merge_file(BASE, master, parent)
        self.assertGreaterEqual(len(expected), 1, "positive control: the fixture does conflict")
        self.assertEqual(self.regions(BASE, master, parent), expected,
                         "conflict_regions must return git's own hunks, in file order")

    def test_regions_for_two_separate_conflicts_come_in_file_order(self):
        base = "## A\n- a1\n- keep1\n- keep2\n- keep3\n## B\n- b1\n"
        ours = "## A\n- a1 ours\n- keep1\n- keep2\n- keep3\n## B\n- b1 ours\n"
        theirs = "## A\n- a1 theirs\n- keep1\n- keep2\n- keep3\n## B\n- b1 theirs\n"
        expected = run_merge_file(base, ours, theirs)
        self.assertEqual(len(expected), 2, "positive control: two separate conflicts")
        got = self.regions(base, ours, theirs)
        self.assertEqual(got, expected, "one entry per hunk, in file order")
        self.assertEqual(got[0]["ours"], ["- a1 ours"], "the first hunk is the one in entry A")

    def test_a_clean_merge_has_no_regions(self):
        base = "## A\n- a\n"
        self.assertEqual(run_merge_file(base, base + "## B\n", base), [],
                         "positive control: git merges this without a conflict")
        self.assertEqual(self.regions(base, base + "## B\n", base), [],
                         "no conflict hunk, so an empty list")


# ===========================================================================
# Issue 113, R-3: P7's per-path branch for the new class ``version-fields``.
#
# Inside _p7_merge, a conflict on a check_version_bump.MANIFESTS path is judged region by region
# (conflict_regions). When every region differs only in lines carrying "version", the default branch's
# side is taken (and the later raise rewrites those lines); otherwise the merge halts unresolvable-conflict.
# Real git in a temporary repository; the repository is removed by addCleanup whatever the outcome.
# ===========================================================================
def _g(cwd, *args, check=True):
    proc = _REAL_SUBPROCESS_RUN(["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *args],
                                cwd=str(cwd), capture_output=True, text=True, env=_GIT_ENV)
    if check and proc.returncode != 0:
        raise AssertionError("fixture git %r failed: %s" % (args, proc.stderr))
    return proc.stdout.strip()


def force_rmtree(path):
    """Remove a folder holding a git repository. Git object files are read-only on Windows, so a plain
    rmtree(ignore_errors=True) silently leaves the folder behind; clear the flag and retry instead."""
    import stat

    def retry(func, target, _error):
        os.chmod(target, stat.S_IWRITE)
        func(target)
    if sys.version_info >= (3, 12):
        shutil.rmtree(str(path), onexc=retry)
    else:
        shutil.rmtree(str(path), onerror=retry)


PLUGIN_BASE = ('{\n  "name": "x",\n  "version": "0.10.0",\n  "description": "d",\n'
               '  "versionNote": "n",\n  "other": 1\n}\n')


class TestP7VersionFieldConflicts(LandCase):

    CONFIG = {"versionRaise": True, "unionPaths": [], "regenerators": []}

    def conflict(self, parent_text, default_text, path="plugin.json", base=PLUGIN_BASE):
        """A parent branch and a default branch that both changed ``path``; returns the P7 outcome."""
        tmp = Path(tempfile.mkdtemp(prefix="landtest-p7v-"))
        self.addCleanup(force_rmtree, tmp)
        repo = tmp / "repo"
        _g(tmp, "init", "-q", "--initial-branch=master", str(repo))
        for key, value in (("user.name", "t"), ("user.email", "t@example.test")):
            _g(repo, "config", key, value)
        write_files(repo, {path: base, "README.txt": "r\n"})
        _g(repo, "add", "-A")
        _g(repo, "commit", "-q", "-m", "base")
        _g(repo, "checkout", "-q", "-b", "parent")
        write_files(repo, {path: parent_text})
        _g(repo, "commit", "-q", "-am", "parent edits")
        _g(repo, "checkout", "-q", "master")
        write_files(repo, {path: default_text})
        _g(repo, "commit", "-q", "-am", "default edits")
        mark_m, mark_p = _g(repo, "rev-parse", "master"), _g(repo, "rev-parse", "parent")
        _g(repo, "checkout", "-q", "--detach", "parent")
        logs = tmp / "logs"
        logs.mkdir()
        facts, details, notes = {}, {}, []
        out = self.fn("_p7_merge")({}, repo, "master", mark_m, mark_p, dict(self.CONFIG), logs, "parent",
                                   "demo", facts, details, notes)
        return {"repo": repo, "facts": facts, "details": details, "resolved": out[2],
                "merging": _g(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False),
                "parents": _g(repo, "rev-list", "--parents", "-n", "1", "HEAD").split()}

    def test_regions_that_differ_only_in_version_lines_take_the_default_branchs_side(self):
        result = self.conflict(PLUGIN_BASE.replace('"0.10.0"', '"0.10.1"'), PLUGIN_BASE.replace('"0.10.0"', '"0.11.0"'))
        self.assertFalse(result["facts"].get("p7_unresolvable_conflict"),
                         "a stale parent bump against a moved default branch is a version-only region: %r"
                         % (result["details"],))
        self.assertIn("plugin.json", result["resolved"], "the file is listed among the resolved paths")
        text = (result["repo"] / "plugin.json").read_text(encoding="utf-8")
        self.assertIn('"version": "0.11.0"', text, "the default branch's side is taken")
        self.assertEqual(len(result["parents"]), 3, "and the merge is committed (two parents)")

    def test_a_region_that_also_differs_in_another_line_halts_unresolvable_conflict(self):
        result = self.conflict(
            PLUGIN_BASE.replace('"0.10.0",\n  "description": "d"', '"0.10.1",\n  "description": "parent words"'),
            PLUGIN_BASE.replace('"0.10.0",\n  "description": "d"', '"0.11.0",\n  "description": "default words"'))
        self.assertTrue(result["facts"].get("p7_unresolvable_conflict"),
                        "the description line differs in the same region, so nobody may pick a side blindly")
        self.assertIn("plugin.json", str(result["details"].get("unresolvable-conflict")), "the detail names the file")
        self.assertEqual(result["merging"], "", "and the merge was aborted, not left half done")

    def test_a_line_that_only_looks_like_version_is_not_a_version_line(self):
        result = self.conflict(PLUGIN_BASE.replace('"versionNote": "n"', '"versionNote": "parent"'),
                               PLUGIN_BASE.replace('"versionNote": "n"', '"versionNote": "default"'))
        self.assertTrue(result["facts"].get("p7_unresolvable_conflict"),
                        '"versionNote" does not carry "version": the merge halts')

    def test_two_separate_version_only_regions_are_both_resolved(self):
        base = ('{\n  "version": "0.10.0",\n  "name": "m",\n  "plugins": [\n    {\n      "name": "x",\n'
                '      "version": "0.10.0"\n    }\n  ]\n}\n')
        tmp_path = ".claude-plugin/marketplace.json"
        result = self.conflict(base.replace("0.10.0", "0.10.1"), base.replace("0.10.0", "0.11.0"), path=tmp_path,
                               base=base)
        self.assertFalse(result["facts"].get("p7_unresolvable_conflict"), repr(result["details"]))
        text = (result["repo"] / tmp_path).read_text(encoding="utf-8")
        self.assertEqual(text.count('"0.11.0"'), 2, "both entries come from the default branch")

    def test_positive_control_a_non_manifest_conflict_still_halts(self):
        result = self.conflict(PLUGIN_BASE.replace('"0.10.0"', '"0.10.1"'), PLUGIN_BASE.replace('"0.10.0"', '"0.11.0"'),
                               path="notes.json")
        self.assertTrue(result["facts"].get("p7_unresolvable_conflict"),
                        "only MANIFESTS paths get the version-fields rule")


if __name__ == "__main__":
    unittest.main()
