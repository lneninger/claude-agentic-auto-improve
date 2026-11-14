#!/usr/bin/env python3
"""test_protected_names.py -- RED suite for the Protected-name check and its command line.

Contract: .claude/concepts/2026-10-13-database-guard-names-in-rules-file.md in the consuming
repository (parent issue #623, sub-task 1 of 13). Sections: Data Shapes (Names reading, Protected-name
verdict), Commands ("Check protected names"), Revisions 3 and 4.

WHAT IS PINNED
--------------
The check compares the parsed ``protected_databases`` strings of a working copy of a database-guard
rules file with the same file at the tip of the default branch. The verdict is one of a closed set:
``kept`` and ``first-install`` pass; ``names-removed``, ``working-malformed``, ``reference-malformed``
and ``unverifiable`` do not. This suite pins, through the command line only (never an import, so a
missing file is an assertion and never an ImportError):

  (a) each verdict, in the contract's decision order, with the rows the TASK names;
  (b) the TIP, not the merge base, is the reference;
  (c) a worktree of the fixture reads its own file against the shared ref;
  (d) protected_names_check.py: exit codes 0, 10, 11, 12, each with exactly ONE JSON object on standard
      output whose verdict matches the code; ``--fetch`` falls back to the local ref with ``fetched``
      false; ``--fetch`` with ``--default-ref`` is refused; ``--working-ref`` and ``--default-ref`` read
      BOTH sides with git and never the disk; an unknown ref is ``unverifiable``; and the two files are
      self-contained (standard library only, runnable alone in an empty folder, under ``py -3 -I -B``).

This file is vendored into the consuming repository (block 7), so it reads only files that exist
there: ``.claude/hooks/_protected_names.py`` and ``.claude/scripts/protected_names_check.py``. The warning
hook, hooks.json, stop-dispatcher.py and the skill are plugin-only and are pinned in
test_protected_names_warning.py.

FIXTURES
--------
Every repository is built in a temporary folder this run owns and removes afterwards (pass or fail). Git
is run with the global and system configuration switched off. Nothing here touches this checkout, a real
remote or any database.

Run:
    py -3 .claude/hooks/tests/test_protected_names.py
"""
from __future__ import annotations

import ast
import importlib.util
import io
import json
import os
import platform
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

CLAUDE_DIR = Path(__file__).resolve().parents[2]
HELPER = CLAUDE_DIR / "hooks" / "_protected_names.py"
CHECK = CLAUDE_DIR / "scripts" / "protected_names_check.py"
RULES_REL = ".claude/hooks/db-destructive-guard.rules.json"

VERDICT_CODES = {
    "kept": 0, "first-install": 0,
    "names-removed": 10,
    "working-malformed": 11, "reference-malformed": 11,
    "unverifiable": 12,
}
JSON_KEYS = {"verdict", "missing", "working_ref", "default_ref", "fetched", "reason"}

NAMES = ["ScalpingMachine", "ScalpingMachine_Testing"]

_GIT_ENV = dict(os.environ,
                GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0",
                GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.test",
                GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.test")
for _k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_TRACE", "GIT_TRACE2_EVENT"):
    _GIT_ENV.pop(_k, None)


def git(cwd, *args, check=True):
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, env=_GIT_ENV)
    if check and proc.returncode != 0:
        raise AssertionError("fixture git %s failed: %s" % (list(args), proc.stderr))
    return proc.stdout.strip()


def _rm_tree(path):
    def onerror(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    shutil.rmtree(str(path), onerror=onerror)


def rules_bytes(names, **extra) -> bytes:
    body = {"protected_databases": names, "production_path_allowlist": [".claude/"], "human_only_commands": []}
    body.update(extra)
    return json.dumps(body, indent=2).encode("utf-8")


def make_world(root: Path, default_files, working_files=None, *, origin=True, ref="master",
               head_symref=True) -> Path:
    """A repository ``<root>/work`` whose ``origin/<ref>`` is its first commit, with no network.

    ``default_files`` is {relative path: bytes} committed first (a README is always added so the commit is
    never empty). ``working_files`` is applied afterwards on disk only: bytes writes, None deletes.
    ``ref`` None leaves ``origin`` declared but with no remote-tracking ref at all (no default branch).
    """
    work = root / "work"
    work.mkdir(parents=True)
    git(work, "init", "-q", "-b", "master")
    files = {"README.txt": b"fixture\n"}
    files.update(default_files or {})
    for rel, data in files.items():
        target = work / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "default")
    if origin:
        git(work, "remote", "add", "origin", str(root / "no-such-origin.git"))
        if ref:
            git(work, "update-ref", "refs/remotes/origin/%s" % ref, "HEAD")
            if head_symref:
                git(work, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/%s" % ref)
    for rel, data in (working_files or {}).items():
        target = work / rel
        if data is None:
            if target.exists():
                target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return work


def make_origin_world(root: Path, names):
    """A real bare origin, a ``work`` clone and a second clone ``other`` (to move the default branch)."""
    origin = root / "origin.git"
    git(root, "init", "-q", "--bare", "-b", "master", str(origin))
    seed = root / "seed"
    git(root, "clone", "-q", str(origin), str(seed))
    (seed / ".claude" / "hooks").mkdir(parents=True)
    (seed / RULES_REL).write_bytes(rules_bytes(names))
    git(seed, "add", "-A")
    git(seed, "commit", "-q", "-m", "seed")
    git(seed, "push", "-q", "origin", "HEAD:refs/heads/master")
    work = root / "work"
    git(root, "clone", "-q", str(origin), str(work))
    return origin, seed, work


class CheckCase(unittest.TestCase):
    """Base: a temporary root per test, removed afterwards whether the test passes or fails."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="pnames-test-")).resolve()
        self.addCleanup(_rm_tree, self.root)

    # -- running the command line -------------------------------------------------------------------
    def run_check(self, project, *args, env=None, script=None, timeout=60):
        """(returncode, parsed JSON or None, stdout, stderr). ``script`` defaults to the real one."""
        run_env = dict(_GIT_ENV)
        run_env.update(env or {})
        proc = subprocess.run(
            ["py", "-3", "-I", "-B", str(script or CHECK), "--project", str(project), *args],
            capture_output=True, text=True, env=run_env, timeout=timeout)
        obj = None
        try:
            parsed = json.loads(proc.stdout)
            obj = parsed if isinstance(parsed, dict) else None
        except ValueError:
            pass
        return proc.returncode, obj, proc.stdout, proc.stderr

    def verdict(self, project, expected, *args, missing=None, env=None):
        rc, obj, out, err = self.run_check(project, *args, env=env)
        self.assertIsNotNone(
            obj, "the command line must print exactly one JSON object on standard output "
                 "(exit %s). stdout=%r stderr=%r" % (rc, out[:200], err[:300]))
        self.assertEqual(obj.get("verdict"), expected,
                         "expected verdict %r. Result: %r stderr=%r" % (expected, obj, err[:300]))
        self.assertEqual(rc, VERDICT_CODES[expected],
                         "the exit code for %r must be %d, not a Python crash code" % (expected, VERDICT_CODES[expected]))
        if missing is not None:
            self.assertEqual(obj.get("missing"), missing, "the strings the working copy lacks, in order")
        return obj

    def world(self, default_names, working_names="same", **kw):
        working = {}
        if working_names != "same":
            working[RULES_REL] = rules_bytes(working_names) if working_names is not None else None
        return make_world(self.root, {RULES_REL: rules_bytes(default_names)}, working, **kw)


# =====================================================================================================
# (a) each verdict, in the contract's decision order
# =====================================================================================================
class VerdictTests(CheckCase):

    def test_kept_when_the_working_copy_equals_the_default_branch(self):
        self.verdict(self.world(NAMES), "kept", missing=[])

    def test_an_append_is_kept(self):
        self.verdict(self.world(NAMES, NAMES + ["Extra_Db"]), "kept")

    def test_a_reorder_is_kept(self):
        self.verdict(self.world(NAMES, list(reversed(NAMES))), "kept")

    def test_a_removed_name_is_names_removed(self):
        self.verdict(self.world(NAMES, NAMES[:1]), "names-removed", missing=[NAMES[1]])

    def test_an_added_trailing_space_is_names_removed(self):
        self.verdict(self.world(NAMES, [NAMES[0] + " ", NAMES[1]]), "names-removed", missing=[NAMES[0]])

    def test_a_letter_case_change_is_names_removed(self):
        self.verdict(self.world(NAMES, [NAMES[0].lower(), NAMES[1]]), "names-removed", missing=[NAMES[0]])

    def test_a_blank_string_is_a_name_like_any_other_and_is_never_skipped(self):
        self.verdict(self.world(NAMES + [""], NAMES), "names-removed", missing=[""])

    def test_an_absent_key_on_the_default_branch_counts_as_an_empty_list(self):
        work = make_world(self.root, {RULES_REL: b"{}"}, {RULES_REL: rules_bytes(["Only"])})
        self.verdict(work, "kept")

    def test_an_empty_default_branch_list_keeps_a_deleted_working_file(self):
        work = self.world([], None)
        self.verdict(work, "kept")

    # -- malformed readings ---------------------------------------------------------------------------
    def test_a_duplicate_key_in_the_working_copy_is_working_malformed(self):
        text = b'{"protected_databases": ["A"], "protected_databases": ["A", "B"]}'
        work = make_world(self.root, {RULES_REL: rules_bytes(["A"])}, {RULES_REL: text})
        self.verdict(work, "working-malformed")

    def test_a_duplicate_key_anywhere_nested_is_malformed_too(self):
        text = b'{"protected_databases": ["A"], "note": {"k": 1, "k": 2}}'
        work = make_world(self.root, {RULES_REL: rules_bytes(["A"])}, {RULES_REL: text})
        self.verdict(work, "working-malformed")

    def test_a_byte_order_mark_in_the_working_copy_is_working_malformed(self):
        work = make_world(self.root, {RULES_REL: rules_bytes(NAMES)}, {RULES_REL: b"\xef\xbb\xbf" + rules_bytes(NAMES)})
        self.verdict(work, "working-malformed")

    def test_a_non_string_entry_is_working_malformed(self):
        text = json.dumps({"protected_databases": [NAMES[0], 5]}).encode()
        work = make_world(self.root, {RULES_REL: rules_bytes(NAMES)}, {RULES_REL: text})
        self.verdict(work, "working-malformed")

    def test_a_list_that_is_not_an_object_is_working_malformed(self):
        work = make_world(self.root, {RULES_REL: rules_bytes(NAMES)}, {RULES_REL: b'["A"]'})
        self.verdict(work, "working-malformed")

    def test_a_protected_databases_value_that_is_not_a_list_is_working_malformed(self):
        work = make_world(self.root, {RULES_REL: rules_bytes(NAMES)}, {RULES_REL: b'{"protected_databases": "A"}'})
        self.verdict(work, "working-malformed")

    def test_bytes_that_are_not_utf8_are_working_malformed(self):
        work = make_world(self.root, {RULES_REL: rules_bytes(NAMES)}, {RULES_REL: b'{"protected_databases": ["\xff"]}'})
        self.verdict(work, "working-malformed")

    def test_a_deleted_working_file_with_a_non_empty_default_list_is_working_malformed(self):
        self.verdict(self.world(NAMES, None), "working-malformed")

    def test_a_malformed_default_branch_file_is_reference_malformed(self):
        work = make_world(self.root, {RULES_REL: b"\xef\xbb\xbf" + rules_bytes(NAMES)}, {RULES_REL: rules_bytes(NAMES)})
        self.verdict(work, "reference-malformed")

    def test_a_duplicate_key_on_the_default_branch_is_reference_malformed(self):
        text = b'{"protected_databases": ["A"], "protected_databases": ["A"]}'
        work = make_world(self.root, {RULES_REL: text}, {RULES_REL: rules_bytes(["A"])})
        self.verdict(work, "reference-malformed")

    def test_reference_malformed_is_decided_before_working_malformed(self):
        work = make_world(self.root, {RULES_REL: b"{ not json"}, {RULES_REL: b"{ also not json"})
        self.verdict(work, "reference-malformed")

    # -- first install and the git failures ---------------------------------------------------------
    def test_no_file_at_the_default_branch_tip_is_first_install_when_the_working_file_parses(self):
        work = make_world(self.root, {}, {RULES_REL: rules_bytes(NAMES)})
        self.verdict(work, "first-install")

    def test_no_file_at_the_tip_and_none_on_disk_is_first_install(self):
        self.verdict(make_world(self.root, {}), "first-install")

    def test_no_file_at_the_tip_and_a_malformed_working_file_is_working_malformed(self):
        work = make_world(self.root, {}, {RULES_REL: b"{ nope"})
        self.verdict(work, "working-malformed")

    def test_no_origin_is_unverifiable(self):
        self.verdict(self.world(NAMES, origin=False), "unverifiable")

    def test_origin_declared_but_no_default_branch_ref_is_unverifiable(self):
        self.verdict(self.world(NAMES, ref=None), "unverifiable")

    def test_an_origin_main_ref_with_no_origin_head_is_a_default_branch(self):
        self.verdict(self.world(NAMES, ref="main", head_symref=False), "kept")

    def test_a_listing_of_the_default_branch_commit_that_fails_is_unverifiable(self):
        work = self.world(NAMES)
        (work / ".git" / "refs" / "remotes" / "origin" / "master").write_text("a" * 40 + "\n", encoding="ascii")
        self.verdict(work, "unverifiable")

    def test_a_folder_that_is_not_a_repository_is_unverifiable(self):
        empty = self.root / "plain"
        empty.mkdir()
        self.verdict(empty, "unverifiable")

    # -- Revision 3 attack rows -----------------------------------------------------------------------
    def test_a_branch_that_adds_the_plugin_manifest_and_drops_a_name_is_names_removed(self):
        work = self.world(NAMES, NAMES[:1])
        manifest = work / ".claude-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": "agentic-auto-improve"}), encoding="utf-8")
        self.verdict(work, "names-removed", missing=[NAMES[1]])

    def test_a_plugin_shaped_tree_whose_template_names_are_unchanged_is_kept(self):
        template = ["AcmeApp", "AcmeApp_Testing"]
        work = make_world(self.root, {RULES_REL: rules_bytes(template),
                                      ".claude-plugin/plugin.json": json.dumps({"name": "agentic-auto-improve"}).encode()})
        self.verdict(work, "kept")

    def test_no_verdict_named_template_checkout_exists(self):
        self.assertTrue(HELPER.is_file(), "%s must exist" % HELPER)
        self.assertNotIn("template-checkout", HELPER.read_text(encoding="utf-8"),
                         "Revision 3 removed the plugin-checkout exemption: no such verdict exists")
        self.assertTrue(CHECK.is_file(), "%s must exist" % CHECK)
        self.assertNotIn("template-checkout", CHECK.read_text(encoding="utf-8"))

    # -- (b) the tip, not the merge base ----------------------------------------------------------------
    def test_a_branch_cut_before_a_name_was_added_is_names_removed_against_the_tip(self):
        origin, seed, work = make_origin_world(self.root, NAMES)
        (seed / RULES_REL).write_bytes(rules_bytes(NAMES + ["Added_Later"]))
        git(seed, "commit", "-q", "-am", "add a name")
        git(seed, "push", "-q", "origin", "HEAD:refs/heads/master")
        git(work, "fetch", "-q", "origin")
        self.assertEqual((work / RULES_REL).read_bytes(), rules_bytes(NAMES),
                         "control: the work branch was cut before the name was added")
        self.verdict(work, "names-removed", missing=["Added_Later"])


# =====================================================================================================
# (c) a worktree of the fixture reads its own file against the shared ref
# =====================================================================================================
class WorktreeTests(CheckCase):

    def test_a_worktree_reads_its_own_working_file_against_the_shared_ref(self):
        work = self.world(NAMES)
        wt = self.root / "wt"
        git(work, "worktree", "add", "-q", "-b", "wtbranch", str(wt))
        (wt / RULES_REL).write_bytes(rules_bytes(NAMES[:1]))
        self.verdict(wt, "names-removed", missing=[NAMES[1]])
        self.verdict(work, "kept")  # control: the main tree's own file is untouched

    def test_a_worktree_sees_a_ref_the_main_tree_moved(self):
        work = self.world(NAMES)
        wt = self.root / "wt"
        git(work, "worktree", "add", "-q", "-b", "wtbranch", str(wt))
        (work / RULES_REL).write_bytes(rules_bytes(NAMES + ["Moved"]))
        git(work, "commit", "-q", "-am", "moved")
        git(work, "update-ref", "refs/remotes/origin/master", "HEAD")
        self.verdict(wt, "names-removed", missing=["Moved"])


# =====================================================================================================
# (d) the command line
# =====================================================================================================
class CommandLineTests(CheckCase):

    def test_each_exit_code_comes_with_exactly_one_json_object_whose_verdict_matches(self):
        rows = [
            ("kept", self.world(NAMES)),
        ]
        for sub, (verdict, builder) in enumerate((
                ("names-removed", lambda r: make_world(r, {RULES_REL: rules_bytes(NAMES)}, {RULES_REL: rules_bytes(NAMES[:1])})),
                ("working-malformed", lambda r: make_world(r, {RULES_REL: rules_bytes(NAMES)}, {RULES_REL: b"{ x"})),
                ("unverifiable", lambda r: make_world(r, {RULES_REL: rules_bytes(NAMES)}, origin=False)),
        )):
            folder = self.root / ("row%d" % sub)
            folder.mkdir()
            rows.append((verdict, builder(folder)))
        for verdict, project in rows:
            rc, obj, out, err = self.run_check(project)
            self.assertIsNotNone(obj, "%s: standard output must be one JSON object, got %r (stderr %r)"
                                 % (verdict, out[:200], err[:200]))
            self.assertEqual(obj.get("verdict"), verdict, "the JSON verdict")
            self.assertEqual(rc, VERDICT_CODES[verdict], "the exit code agrees with the JSON verdict")
            self.assertTrue(JSON_KEYS <= set(obj), "the JSON carries %s, got %s" % (sorted(JSON_KEYS), sorted(obj)))
            self.assertNotIn(rc, (1, 2), "never a code that Python itself uses for a crash or a usage error")

    def test_names_removed_says_on_standard_error_what_to_do(self):
        work = self.world(NAMES, NAMES[:1])
        rc, obj, out, err = self.run_check(work)
        self.assertEqual(rc, 10, "names-removed exits 10. stderr=%r" % err[:300])
        self.assertIn(NAMES[1], err, "the message names the missing string")
        self.assertIn("only a person removes a protected database name", err)
        self.assertIn("change only the rules file in its own pull request and merge it by hand", err)

    def test_the_human_readable_text_never_goes_to_standard_output(self):
        work = self.world(NAMES, NAMES[:1])
        rc, obj, out, err = self.run_check(work)
        self.assertIsNotNone(obj, "standard output must parse as one JSON object (exit %s)" % rc)
        self.assertNotIn("only a person removes", out, "prose belongs on standard error")

    # -- --fetch ------------------------------------------------------------------------------------------
    def test_fetch_updates_the_default_branch_before_comparing(self):
        origin, seed, work = make_origin_world(self.root, NAMES)
        (seed / RULES_REL).write_bytes(rules_bytes(NAMES + ["Added_Later"]))
        git(seed, "commit", "-q", "-am", "add a name")
        git(seed, "push", "-q", "origin", "HEAD:refs/heads/master")
        self.verdict(work, "kept")  # control: the local ref is stale, so without --fetch nothing is missing
        obj = self.verdict(work, "names-removed", "--fetch", missing=["Added_Later"])
        self.assertIs(obj.get("fetched"), True, "the fetch ran, so fetched is true")

    def test_a_failed_fetch_falls_back_to_the_local_ref_and_says_so(self):
        work = self.world(NAMES, NAMES[:1])
        obj = self.verdict(work, "names-removed", "--fetch")
        self.assertIs(obj.get("fetched"), False, "origin does not exist, so the fetch failed: fetched is false")

    def test_a_failed_fetch_with_no_local_ref_is_unverifiable(self):
        work = self.world(NAMES, ref=None)
        self.verdict(work, "unverifiable", "--fetch")

    def test_fetch_together_with_default_ref_is_refused(self):
        work = self.world(NAMES)
        head = git(work, "rev-parse", "HEAD")
        rc, obj, out, err = self.run_check(work, "--fetch", "--default-ref", head)
        self.assertNotIn(rc, (0, 10, 11, 12), "a refused combination is a usage refusal, not a verdict. stdout=%r" % out[:200])
        self.assertIn("--default-ref", err, "the refusal names the flag it refuses. stderr=%r" % err[:300])

    # -- Revision 4: both sides read with git --------------------------------------------------------------
    def _two_commits(self):
        """origin/master = C1 (A and B); the work branch commits C2 (A only). Returns (work, C1, C2)."""
        work = self.world(NAMES)
        c1 = git(work, "rev-parse", "HEAD")
        (work / RULES_REL).write_bytes(rules_bytes(NAMES[:1]))
        git(work, "commit", "-q", "-am", "narrow")
        c2 = git(work, "rev-parse", "HEAD")
        return work, c1, c2

    def test_working_ref_reads_the_commit_and_never_the_disk_narrowed_disk_with_a_kept_commit_is_kept(self):
        work, c1, c2 = self._two_commits()
        self.assertEqual((work / RULES_REL).read_bytes(), rules_bytes(NAMES[:1]), "control: the disk file is narrowed")
        self.verdict(work, "kept", "--working-ref", c1)

    def test_working_ref_reads_the_commit_and_never_the_disk_kept_disk_with_a_narrowed_commit_is_names_removed(self):
        work, c1, c2 = self._two_commits()
        (work / RULES_REL).write_bytes(rules_bytes(NAMES))
        self.verdict(work, "names-removed", "--working-ref", c2, missing=[NAMES[1]])

    def test_default_ref_names_the_commit_for_the_default_side(self):
        work, c1, c2 = self._two_commits()
        self.verdict(work, "names-removed", "--working-ref", c2, "--default-ref", c1)
        self.verdict(work, "kept", "--working-ref", c1, "--default-ref", c2)

    def test_default_ref_wins_over_the_detected_origin_branch(self):
        work, c1, c2 = self._two_commits()
        # origin/master is C1 (A and B). Against C2 (A only) the same working commit is kept.
        self.verdict(work, "kept", "--working-ref", c2, "--default-ref", c2)

    def test_an_unknown_working_ref_is_unverifiable(self):
        self.verdict(self.world(NAMES), "unverifiable", "--working-ref", "f" * 40)

    def test_an_unknown_default_ref_is_unverifiable(self):
        self.verdict(self.world(NAMES), "unverifiable", "--default-ref", "f" * 40)

    def test_the_json_names_the_commit_ids_it_compared(self):
        work, c1, c2 = self._two_commits()
        obj = self.verdict(work, "names-removed", "--working-ref", c2, "--default-ref", c1)
        self.assertIn(c1, json.dumps(obj), "default_ref carries the commit id it was read at")
        self.assertIn(c2, json.dumps(obj), "working_ref carries the commit id it was read at")

    def test_an_explicit_ref_makes_no_fetch(self):
        work, c1, c2 = self._two_commits()
        # NAMED EDIT (#623 t14): recorder moved off GIT_TRACE2_EVENT because remedy invariant C2 removes that
        # variable from every git call. A recording git shim, first on PATH, records every call instead.
        shim_dir, shim_log = self.root / "shim-bin", self.root / "shim.log"
        make_git_shim(shim_dir, shim_log)
        self.verdict(work, "names-removed", "--working-ref", c2, "--default-ref", c1,
                     env={"PATH": str(shim_dir) + os.pathsep + os.environ.get("PATH", "")})
        recs = read_shim_log(shim_log)
        self.assertTrue(recs, "control: git ran and was recorded")
        self.assertFalse([r for r in recs if shim_subcommand(r["args"]) == "fetch"],
                         "reading two commits runs no git fetch")


# =====================================================================================================
# Revision 4: both files are self-contained
# =====================================================================================================
def _imported_top_modules(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level > 0:
            found.add("." * node.level)
    return found


class SelfContainmentTests(CheckCase):

    def test_both_files_exist(self):
        self.assertTrue(HELPER.is_file(), "%s must exist" % HELPER)
        self.assertTrue(CHECK.is_file(), "%s must exist" % CHECK)

    def test_both_files_import_only_the_standard_library_and_each_other(self):
        for path in (HELPER, CHECK):
            self.assertTrue(path.is_file(), "%s must exist" % path)
            allowed = set(sys.stdlib_module_names) | {"_protected_names"}
            foreign = sorted(m for m in _imported_top_modules(path) if m not in allowed)
            self.assertEqual(foreign, [], "%s imports something that is not standard library: %s" % (path.name, foreign))

    def test_neither_file_names_the_two_path_bridges(self):
        for path in (HELPER, CHECK):
            self.assertTrue(path.is_file(), "%s must exist" % path)
            text = path.read_text(encoding="utf-8")
            for bridge in ("_claude_paths", "_project_paths"):
                self.assertNotIn(bridge, text, "%s must not use %s (the landing gate's folder has neither)" % (path.name, bridge))

    def _copy_and_run(self, layout):
        self.assertTrue(HELPER.is_file() and CHECK.is_file(), "both files must exist")
        folder = self.root / ("copy-" + layout)
        if layout == "single":
            (folder).mkdir()
            script_dir = helper_dir = folder
        else:
            script_dir, helper_dir = folder / "scripts", folder / "hooks"
            script_dir.mkdir(parents=True)
            helper_dir.mkdir(parents=True)
        shutil.copy2(str(CHECK), str(script_dir / CHECK.name))
        shutil.copy2(str(HELPER), str(helper_dir / HELPER.name))
        listing = sorted(p.name for p in folder.rglob("*") if p.is_file())
        self.assertNotIn("_claude_paths.py", listing, "control: no path bridge beside the copies")
        self.assertNotIn("_project_paths.py", listing, "control: no path bridge beside the copies")
        project = self.root / ("proj-" + layout)
        project.mkdir()
        work = make_world(project, {RULES_REL: rules_bytes(NAMES)})
        return self.run_check(work, script=script_dir / CHECK.name)

    def test_the_two_files_copied_alone_into_an_empty_folder_print_a_valid_verdict(self):
        rc, obj, out, err = self._copy_and_run("single")
        self.assertIsNotNone(obj, "a self-contained script prints one JSON object. stdout=%r stderr=%r" % (out[:200], err[:300]))
        self.assertEqual(obj.get("verdict"), "kept", "the fixture keeps every name. stderr=%r" % err[:300])
        self.assertEqual(rc, 0)

    def test_the_two_files_in_this_repositorys_layout_print_a_valid_verdict(self):
        rc, obj, out, err = self._copy_and_run("layout")
        self.assertIsNotNone(obj, "script in scripts/, helper in hooks/. stdout=%r stderr=%r" % (out[:200], err[:300]))
        self.assertEqual(obj.get("verdict"), "kept", "stderr=%r" % err[:300])
        self.assertEqual(rc, 0)


# =====================================================================================================
# REVISION 5 REMEDY (block 14, RED). Gate 3's probes and invariants C1 (import order), C2 (git isolation)
# and C3 (rules-path aliases) of the contract 2026-10-13-database-guard-names-in-rules-file.
#
# Every row name carries its contract row id (R5-B1-3, R5-B2-3, R5-B2-4, R5-B2-8, R5-B2-9, R5-B2-10,
# R5-W4-1, R5-W4-2, R5-B3-2 to R5-B3-6). Like the rows above, these go through the command line only.
#
# THE RECORDING GIT SHIM. The TASK asks for a recording git first on PATH. A shim must be an .exe on
# Windows (a process started as git is never resolved to a .cmd), so make_git_shim() builds one from the
# console launcher pip vendors (pip/_vendor/distlib/t64.exe) with a zipped __main__.py appended; on other
# systems it is a script with a shebang. The shim logs argv, cwd and the WHOLE environment of every call
# to a test-owned file, then runs the real git (its absolute path is baked in, so it needs nothing from
# the environment it is given). It never writes outside test-owned folders.
#
# Every fixture lives in self.root, which the base class removes whether the test passes or fails.
# =====================================================================================================
#: The environment C2 names, exactly (Commands, Git isolation). The first four are copied from the caller.
NAMED_ENV = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "PATH", "TEMP", "TMP", "TMPDIR", "HOME",
             "USERPROFILE", "GIT_NO_REPLACE_OBJECTS", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL",
             "GIT_TERMINAL_PROMPT", "GIT_OPTIONAL_LOCKS")
COPIED_ENV = ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT")
#: The variables C2 says are absent by construction (plus every GIT_CONFIG_KEY_<n>, GIT_CONFIG_VALUE_<n>, PYTHON*).
EXCLUDED_ENV = ("GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
                "GIT_CONFIG_SYSTEM", "GIT_NAMESPACE", "XDG_CONFIG_HOME")
#: The command-line settings C2 puts on every call (safe.directory is checked separately: its value varies).
C2_SETTINGS = ("core.fsmonitor=false", "core.untrackedCache=false", "index.sparse=false",
               "core.quotePath=false", "core.longpaths=true")
NULL_DEVICES = (os.devnull.lower(), "nul", "/dev/null")

_SHIM_MAIN = r'''
import json, os, subprocess, sys
LOG, REAL, MODE, KEEP = __LOG__, __REAL__, __MODE__, __KEEP__
args = sys.argv[1:]
with open(LOG, "a", encoding="utf-8") as fh:
    # Only the variables C2 names keep their value: the caller's other variables may hold secrets, and a
    # key set is all a row needs to know about them.
    fh.write(json.dumps({"argv0": sys.argv[0], "args": args, "cwd": os.getcwd(),
                         "env": {k: (v if k in KEEP else "*") for k, v in os.environ.items()},
                         "temp_is_dir": os.path.isdir(os.environ.get("TEMP", ""))}) + "\n")
if MODE == "planted":
    sys.exit(0)


def subcommand(items):
    i = 0
    while i < len(items):
        if items[i] in ("-c", "-C"):
            i += 2
        elif items[i].startswith("-"):
            i += 1
        else:
            return items[i]
    return ""


if MODE == "hostile-gate" and args[:1] == ["--no-replace-objects"] and subcommand(args) == "ls-tree":
    sys.exit(0)  # a hostile git: it answers the isolated listing of a tree with nothing and exit 0
if MODE.startswith("fail-cat:") and subcommand(args) == "cat-file" and any(o and o in args for o in MODE[9:].split(",")):
    sys.stderr.write("fatal: unable to read blob (simulated failure of one named read)\n")
    sys.exit(128)
if MODE.startswith("toplevel:") and subcommand(args) == "rev-parse" and "--show-toplevel" in args:
    sys.stdout.write(MODE[9:] + "\n")  # a planted git that answers `rev-parse --show-toplevel` with a decoy
    sys.exit(0)
if MODE.startswith("fail-ls:") and subcommand(args) == "ls-tree" and "--full-tree" in args and any(c and c in args for c in MODE[8:].split(",")):
    sys.stderr.write("fatal: unable to list the tree (simulated failure of the whole-tree listing of one named commit)\n")
    sys.exit(128)
if MODE == "ownership" and not any(a.startswith("safe.directory=") for a in args):
    sys.stderr.write("fatal: detected dubious ownership in repository (simulated: no safe.directory given)\n")
    sys.exit(128)
if MODE == "fetch-silent" and subcommand(args) == "fetch":
    sys.exit(0)
sys.exit(subprocess.run([REAL] + args, env=os.environ).returncode)
'''


def _distlib_launcher():
    try:
        import pip  # noqa: WPS433 -- only to find the vendored console launcher
    except ImportError:
        return None
    machine = platform.machine().lower()
    name = "t64-arm.exe" if "arm" in machine else ("t64.exe" if sys.maxsize > 2 ** 32 else "t32.exe")
    path = Path(pip.__file__).resolve().parent / "_vendor" / "distlib" / name
    return path.read_bytes() if path.is_file() else None


def shim_name():
    return "git.exe" if os.name == "nt" else "git"


def make_git_shim(folder, log, mode="record"):
    """Create ``<folder>/git(.exe)``, a git that logs every call to ``log`` and then runs the real git.

    ``mode``: ``record`` (log, then run git); ``planted`` (log, then exit 0 doing nothing: a program that
    must NEVER run); ``ownership`` (a call without ``-c safe.directory=`` fails as git's ownership check
    does); ``fetch-silent`` (``git fetch`` succeeds and writes nothing). Block 18 adds three modes, each
    a pass-through recorder except for the one call it names: ``hostile-gate`` (an isolated
    ``--no-replace-objects ... ls-tree`` answers nothing with exit 0, as gate 16's probe did);
    ``fail-cat:<oid>[,<oid>]`` (a ``cat-file`` naming one of those object ids exits 128);
    ``toplevel:<path>`` (``rev-parse --show-toplevel`` answers ``<path>``). Block 25 adds ``fail-ls:<commit>[,<commit>]``
    (a ``ls-tree ... --full-tree`` naming one of those commits exits 128, as a failed whole-tree listing does). Skips the test where no
    executable can be built."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    real = shutil.which("git")
    if not real:
        raise unittest.SkipTest("no git on PATH to delegate to")
    main = (_SHIM_MAIN.replace("__LOG__", repr(str(log))).replace("__REAL__", repr(str(real)))
            .replace("__MODE__", repr(mode)).replace("__KEEP__", repr(NAMED_ENV)))
    target = folder / shim_name()
    if os.name == "nt":
        launcher = _distlib_launcher()
        if launcher is None:
            raise unittest.SkipTest("cannot build a recording git.exe: pip's vendored console launcher is missing")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("__main__.py", main)
        target.write_bytes(launcher + b"#!" + os.fsencode(sys.executable) + b"\n" + buf.getvalue())
    else:
        target.write_text("#!%s\n%s" % (sys.executable, main), encoding="utf-8")
        target.chmod(0o755)
    return target


def read_shim_log(log):
    path = Path(log)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def shim_subcommand(args):
    i = 0
    while i < len(args):
        if args[i] in ("-c", "-C"):
            i += 2
        elif args[i].startswith("-"):
            i += 1
        else:
            return args[i]
    return ""


def _norm(path):
    return os.path.normcase(os.path.realpath(str(path)))


def expected_env_keys():
    return sorted(key for key in NAMED_ENV if key not in COPIED_ENV or key in os.environ)


def git_in(cwd, *args, input=None, env=None):
    """A fixture git call that may take standard input (bytes) and extra environment."""
    run_env = dict(_GIT_ENV)
    run_env.update(env or {})
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, input=input, env=run_env)
    if proc.returncode != 0:
        raise AssertionError("fixture git %s failed: %s" % (list(args), proc.stderr.decode("utf-8", "replace")))
    return proc.stdout.decode("utf-8", errors="replace").strip()


def hash_blob(repo, data):
    return git_in(repo, "hash-object", "-w", "--stdin", input=data)


def plumbing_commit(repo, files):
    """A parentless commit whose tree holds ``{path: bytes}``, built with hash-object, mktree and
    commit-tree only: no path ever touches the disk, so a name Windows would fold or refuse is fine."""
    root = {}
    for path, data in files.items():
        parts = path.split("/")
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = data

    def write(node):
        lines = []
        for name, value in node.items():
            if isinstance(value, dict):
                lines.append(b"040000 tree " + write(value).encode("ascii") + b"\t" + name.encode("utf-8"))
            else:
                lines.append(b"100644 blob " + hash_blob(repo, value).encode("ascii") + b"\t" + name.encode("utf-8"))
        return git_in(repo, "mktree", "-z", input=b"\0".join(lines) + b"\0")

    return git_in(repo, "commit-tree", write(root), "-m", "fixture")


class RemedyCase(CheckCase):
    """CheckCase plus the recording shim and a runner that never goes through the ``py`` launcher (a row
    that sets PATH must not depend on PATH to start the checker)."""

    def setUp(self):
        super().setUp()
        self.shim_dir = self.root / "shim-bin"
        self.shim_log = self.root / "shim.log"

    def install_shim(self, mode="record"):
        return make_git_shim(self.shim_dir, self.shim_log, mode)

    def shim_env(self, extra=None):
        env = {"PATH": str(self.shim_dir) + os.pathsep + os.environ.get("PATH", "")}
        env.update(extra or {})
        return env

    def run_checker(self, project, *args, env=None, cwd=None, timeout=120):
        run_env = dict(_GIT_ENV)
        run_env.update(env or {})
        proc = subprocess.run([sys.executable, "-I", "-B", str(CHECK), "--project", str(project), *args],
                              capture_output=True, text=True, env=run_env,
                              cwd=str(cwd if cwd else self.root), timeout=timeout)
        obj = None
        try:
            parsed = json.loads(proc.stdout)
            obj = parsed if isinstance(parsed, dict) else None
        except ValueError:
            pass
        return proc.returncode, obj, proc.stdout, proc.stderr

    def expect(self, project, verdict, *args, env=None, cwd=None, why=""):
        rc, obj, out, err = self.run_checker(project, *args, env=env, cwd=cwd)
        self.assertIsNotNone(obj, "%s: one JSON object on standard output (exit %s). stdout=%r stderr=%r"
                             % (why, rc, out[:200], err[:300]))
        self.assertEqual(obj.get("verdict"), verdict, "%s: expected %r. Result %r stderr=%r"
                         % (why, verdict, obj, err[:300]))
        self.assertEqual(rc, VERDICT_CODES[verdict], "%s: the exit code for %r" % (why, verdict))
        return obj

    def assert_isolated(self, records, why, skip=("fetch", "ls-remote")):
        """Every call the shim logged carries C2's isolation (the network calls named in ``skip`` are the one
        stated exception: they run with the caller's environment)."""
        self.assertTrue(records, "%s: control: the recording git saw at least one call (git ran through it)" % why)
        for rec in records:
            if shim_subcommand(rec["args"]) in skip:
                continue
            label = "%s: git %s" % (why, " ".join(rec["args"][:12]))
            self.assertEqual(rec["args"][:1], ["--no-replace-objects"], label + " must begin with --no-replace-objects")
            given = [rec["args"][i + 1] for i, a in enumerate(rec["args"][:-1]) if a == "-c"]
            for setting in C2_SETTINGS:
                self.assertIn(setting, given, label + " must pass -c " + setting)
            safe = [s for s in given if s.startswith("safe.directory=")]
            self.assertEqual(len(safe), 1, label + " must pass exactly one -c safe.directory=<path>")
            self.assertNotEqual(safe[0], "safe.directory=*", label + ": never a wildcard")
            value = safe[0].split("=", 1)[1]
            self.assertTrue(os.path.isabs(value), label + ": safe.directory is an absolute path, got %r" % value)
            reads = [rec["cwd"]] + [rec["args"][i + 1] for i, a in enumerate(rec["args"][:-1]) if a == "-C"]
            self.assertIn(_norm(value), [_norm(p) for p in reads],
                          label + ": safe.directory is the exact path of the repository the call reads (%r)" % reads)
            env = rec["env"]
            self.assertEqual(sorted(env), expected_env_keys(),
                             label + ": the environment holds exactly C2's named list and nothing else")
            self.assertEqual(env.get("GIT_NO_REPLACE_OBJECTS"), "1", label)
            self.assertEqual(env.get("GIT_CONFIG_NOSYSTEM"), "1", label)
            self.assertIn(str(env.get("GIT_CONFIG_GLOBAL")).lower(), NULL_DEVICES, label + ": GIT_CONFIG_GLOBAL at the null device")
            self.assertEqual(env.get("GIT_TERMINAL_PROMPT"), "0", label)
            self.assertEqual(env.get("GIT_OPTIONAL_LOCKS"), "0", label)
            private = {env.get(k) for k in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE")}
            self.assertEqual(len(private), 1, label + ": TEMP, TMP, TMPDIR, HOME and USERPROFILE are one private folder")
            self.assertTrue(rec["temp_is_dir"], label + ": and that folder exists")
            self.assertEqual(_norm(env["PATH"].split(os.pathsep)[0]), _norm(self.shim_dir),
                             label + ": PATH begins with the folder of the resolved git program")


# -----------------------------------------------------------------------------------------------------
# C1: import order (R5-B1-3)
# -----------------------------------------------------------------------------------------------------
class ImportOrderTests(RemedyCase):
    """The script imports the standard library before it edits sys.path, and ../hooks is a fallback only."""

    def _layout(self, with_own_helper):
        base = self.root / "layout"
        scripts, hooks = base / "scripts", base / "hooks"
        scripts.mkdir(parents=True)
        hooks.mkdir()
        self.assertTrue(CHECK.is_file(), "%s must exist" % CHECK)
        shutil.copy2(str(CHECK), str(scripts / CHECK.name))
        marker = self.root / "markers.txt"

        def helper(tag):
            return ("open(%r, 'a').write(%r)\nEXIT_CODES = {'kept': 0}\n\n\ndef check(project, working_ref=None, "
                    "default_ref=None, fetch=False):\n    return {'verdict': 'kept', 'missing': [], 'working_ref': '', "
                    "'default_ref': '', 'fetched': None, 'reason': ''}\n" % (str(marker), tag + "\n"))
        if with_own_helper:
            (scripts / "_protected_names.py").write_text(helper("A"), encoding="utf-8")
        (hooks / "_protected_names.py").write_text(helper("B"), encoding="utf-8")
        (hooks / "json.py").write_text("open(%r, 'a').write('J\\n')\n" % str(marker), encoding="utf-8")
        return scripts / CHECK.name, marker

    def _run(self, script):
        proc = subprocess.run([sys.executable, "-I", "-B", str(script), "--project", str(self.root)],
                              capture_output=True, text=True, cwd=str(self.root), timeout=60)
        return proc

    def test_R5_B1_3_the_helper_beside_the_script_runs_and_neither_the_sibling_hooks_helper_nor_its_json_does(self):
        script, marker = self._layout(with_own_helper=True)
        proc = self._run(script)
        seen = marker.read_text(encoding="utf-8").split() if marker.exists() else []
        self.assertEqual(seen, ["A"],
                         "only helper A (beside the script) may run; B (../hooks) is a fallback and json.py there is "
                         "never a standard-library stand-in. Markers seen: %r. exit %s stderr=%r"
                         % (seen, proc.returncode, proc.stderr[-300:]))
        self.assertEqual(proc.returncode, 0, "and the run still gives its verdict. stderr=%r" % proc.stderr[-300:])

    def test_R5_B1_3_with_no_helper_beside_the_script_the_sibling_hooks_helper_is_the_fallback_and_json_still_never_runs(self):
        script, marker = self._layout(with_own_helper=False)
        proc = self._run(script)
        seen = marker.read_text(encoding="utf-8").split() if marker.exists() else []
        self.assertEqual(seen, ["B"],
                         "helper B (the fallback) runs and the planted json.py never does. Markers seen: %r. exit %s "
                         "stderr=%r" % (seen, proc.returncode, proc.stderr[-300:]))
        self.assertEqual(proc.returncode, 0, "stderr=%r" % proc.stderr[-300:])

    def test_R5_B1_3_control_the_two_stubs_and_the_planted_json_are_wired_to_the_same_marker_file(self):
        """A marker file that nothing could write would make the rows above pass for the wrong reason."""
        script, marker = self._layout(with_own_helper=True)
        self.assertTrue((script.parent.parent / "hooks" / "json.py").is_file(), "control: the planted json.py exists")
        probe = subprocess.run([sys.executable, "-B", str(script.parent.parent / "hooks" / "json.py")],
                               capture_output=True, text=True, cwd=str(self.root), timeout=30)
        self.assertEqual(probe.returncode, 0, "control: the planted json.py runs when run directly")
        self.assertEqual(marker.read_text(encoding="utf-8").split(), ["J"], "control: its marker reaches the file")


# -----------------------------------------------------------------------------------------------------
# C2: git isolation (R5-B2-3, R5-B2-4, R5-B2-8, R5-B2-9, R5-B2-10)
# -----------------------------------------------------------------------------------------------------
class ReplaceRefDiskModeTests(RemedyCase):

    def test_R5_B2_3_a_replace_ref_on_the_default_branchs_rules_blob_still_gives_names_removed(self):
        work = self.world(NAMES, NAMES[:1])
        default_blob = git(work, "rev-parse", "refs/remotes/origin/master:" + RULES_REL)
        narrowed_blob = hash_blob(work, rules_bytes(NAMES[:1]))
        self.assertNotEqual(default_blob, narrowed_blob, "control: the two blobs differ")
        self.expect(work, "names-removed", why="control, before the replace ref")
        git(work, "replace", default_blob, narrowed_blob)
        shown = subprocess.run(["git", "cat-file", "-p", default_blob], cwd=str(work), capture_output=True, env=_GIT_ENV).stdout
        self.assertEqual(shown, rules_bytes(NAMES[:1]), "control: git reads the REPLACEMENT bytes under that blob id")
        self.expect(work, "names-removed", why="a replace ref must not change the bytes the check compares")


class EnvironmentIsolationTests(RemedyCase):

    # -- R5-B2-4: a hostile caller environment ---------------------------------------------------------
    def _recorder(self, name):
        """A shell script that records its own run, and the log it writes to (forward slashes for git)."""
        log = (self.root / (name + ".log"))
        prog = self.root / (name + ".sh")
        prog.write_text("#!/bin/sh\necho ran >> \"%s\"\nexit 0\n" % str(log).replace("\\", "/"), encoding="utf-8", newline="\n")
        return str(prog).replace("\\", "/"), log

    def test_R5_B2_4_control_the_recording_program_does_run_when_git_reads_the_index_unprotected(self):
        work = self.world(NAMES, NAMES[:1])
        prog, log = self._recorder("fsmonitor")
        git(work, "config", "core.fsmonitor", prog)
        git(work, "ls-files", "-z", "--full-name")
        self.assertTrue(log.exists(), "control: a plain git that reads the index runs the core.fsmonitor program; "
                                      "without this the 'never runs' rows below would prove nothing")

    def test_R5_B2_4_inherited_git_variables_and_config_files_decide_nothing(self):
        self.install_shim()
        work = self.world(NAMES, NAMES[:1])
        decoy_root = self.root / "decoyroot"
        decoy_root.mkdir()
        decoy = make_world(decoy_root, {RULES_REL: rules_bytes(NAMES[:1])})  # its default branch keeps only the first name
        decoy_index = self.root / "decoy-index"
        shutil.copy2(str(decoy / ".git" / "index"), str(decoy_index))
        prog, log = self._recorder("fsmonitor")
        cfg = self.root / "hostile.gitconfig"
        cfg.write_text("[core]\n\tfsmonitor = %s\n" % prog, encoding="utf-8")
        hostile = {
            "GIT_DIR": str(decoy / ".git"), "GIT_COMMON_DIR": str(decoy / ".git"), "GIT_WORK_TREE": str(decoy),
            "GIT_INDEX_FILE": str(decoy_index), "GIT_OBJECT_DIRECTORY": str(decoy / ".git" / "objects"),
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(decoy / ".git" / "objects"),
            "GIT_CONFIG_PARAMETERS": "'core.fsmonitor'='%s'" % prog,
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.fsmonitor", "GIT_CONFIG_VALUE_0": prog,
            "GIT_CONFIG_GLOBAL": str(cfg), "GIT_CONFIG_SYSTEM": str(cfg),
        }
        self.expect(work, "names-removed", env=self.shim_env(hostile), why="the real fixture's own verdict, not the decoy's")
        self.assertFalse(log.exists(), "the core.fsmonitor program the hostile environment names never ran")
        self.assert_isolated(read_shim_log(self.shim_log), "R5-B2-4 hostile environment")

    def test_R5_B2_4_a_fixtures_own_core_fsmonitor_setting_never_runs_its_program(self):
        self.install_shim()
        work = self.world(NAMES, NAMES[:1])
        prog, log = self._recorder("fsmonitor-own")
        git(work, "config", "core.fsmonitor", prog)
        self.expect(work, "names-removed", env=self.shim_env(), why="a fixture with an fsmonitor program in .git/config")
        self.assertFalse(log.exists(), "the repository's own core.fsmonitor program never ran (-c core.fsmonitor=false)")
        self.assert_isolated(read_shim_log(self.shim_log), "R5-B2-4 own fsmonitor setting")

    def test_R5_B2_4_every_call_is_isolated_even_in_working_ref_mode(self):
        self.install_shim()
        work = self.world(NAMES)
        head = git(work, "rev-parse", "HEAD")
        self.expect(work, "kept", "--working-ref", head, "--default-ref", head, env=self.shim_env(), why="two commits")
        self.assert_isolated(read_shim_log(self.shim_log), "R5-B2-4 commit mode")

    # -- R5-B2-8: variables C2 never names ---------------------------------------------------------------
    def test_R5_B2_8_variables_the_contract_never_names_are_absent_not_removed(self):
        # NAMED EDIT (#623 t18, F8): the GIT_EXEC_PATH and GIT_SSH_COMMAND recorder halves are deleted. On a
        # local fixture git never starts a non-builtin git program (the listing and the blob read are
        # builtins) and never starts ssh, so no recorder could ever have run: those halves could not fail.
        # What stays is what CAN fail: the key set of the environment every git call receives (a copy that
        # only REMOVES the contract's excluded names keeps GIT_EXEC_PATH, GIT_SSH_COMMAND, GIT_TRACE... and
        # fails assert_isolated) and the two trace files (a trace variable that is passed on writes one).
        self.install_shim()
        work = self.world(NAMES, NAMES[:1])
        execdir = self.root / "exec-path"
        execdir.mkdir()
        trace2, trace = self.root / "trace2.json", self.root / "trace.txt"
        env = self.shim_env({"GIT_EXEC_PATH": str(execdir), "GIT_TRACE2_EVENT": str(trace2), "GIT_TRACE": str(trace),
                             "GIT_SSH_COMMAND": "no-such-ssh-program", "GIT_ZZ_CANARY": "1",
                             "PYTHONSTARTUP": str(self.root / "startup.py")})
        self.expect(work, "names-removed", env=env, why="the fixture's verdict")
        self.assertFalse(trace2.exists(), "GIT_TRACE2_EVENT is not passed on: no trace file was written (a passed-on "
                                          "trace variable makes git write the file)")
        self.assertFalse(trace.exists(), "GIT_TRACE is not passed on: no trace file was written (a passed-on trace "
                                         "variable makes git write the file)")
        self.assert_isolated(read_shim_log(self.shim_log),
                             "R5-B2-8 variables C2 never names (the key set of every git call's environment is exactly "
                             "C2's named list, so GIT_EXEC_PATH, GIT_SSH_COMMAND, GIT_ZZ_CANARY and PYTHONSTARTUP are absent)")

    # -- R5-B2-9: the PATH walk -------------------------------------------------------------------------
    def _planted_world(self):
        work = self.world(NAMES, NAMES[:1])
        second = self.root / "second-tree"
        git(work, "worktree", "add", "-q", "-b", "second-branch", str(second))
        cwd = self.root / "cwd"
        (cwd / "bin").mkdir(parents=True)
        self.planted_log = self.root / "planted.log"
        for folder in (cwd, cwd / "bin", work / "tools", second / "tools"):
            make_git_shim(folder, self.planted_log, mode="planted")
        return work, second, cwd

    def test_R5_B2_9_a_git_found_in_an_empty_dot_relative_or_checked_tree_entry_is_never_run(self):
        work, second, cwd = self._planted_world()
        self.install_shim()
        path = os.pathsep.join(["", ".", "bin", str(work / "tools"), str(second / "tools"), str(self.shim_dir)])
        rc, obj, out, err = self.run_checker(work, env={"PATH": path}, cwd=cwd)
        planted = read_shim_log(self.planted_log)
        self.assertEqual([r["args"][:3] for r in planted], [],
                         "no git planted in the working folder, '.', 'bin', the project root or a second tree under "
                         "check may run")
        self.assertEqual((obj or {}).get("verdict"), "names-removed",
                         "the real git, last on PATH, reaches the fixture's verdict. Result %r stderr=%r" % (obj, err[:200]))
        recorded = read_shim_log(self.shim_log)
        self.assertTrue(recorded, "control: the real git (the last entry) ran")
        for rec in recorded:
            self.assertEqual(_norm(rec["argv0"]), _norm(self.shim_dir / shim_name()),
                             "every call used the real git's absolute path")

    def test_R5_B2_9_with_only_planted_entries_on_path_the_verdict_is_unverifiable(self):
        work, second, cwd = self._planted_world()
        path = os.pathsep.join(["", ".", "bin", str(work / "tools"), str(second / "tools")])
        rc, obj, out, err = self.run_checker(work, env={"PATH": path}, cwd=cwd)
        self.assertEqual([r["args"][:3] for r in read_shim_log(self.planted_log)], [],
                         "no planted git may run, even when nothing else is left")
        self.assertIsNotNone(obj, "one JSON object. stdout=%r stderr=%r" % (out[:200], err[:300]))
        self.assertEqual((obj.get("verdict"), rc), ("unverifiable", 12), "no usable git: unverifiable, never a pass. %r" % obj)

    # -- R5-B2-10: safe.directory and core.longpaths -----------------------------------------------------
    def test_R5_B2_10_every_call_carries_core_longpaths_and_the_exact_path_safe_directory(self):
        self.install_shim()
        work = self.world(NAMES, NAMES[:1])
        self.expect(work, "names-removed", env=self.shim_env(), why="disk mode")
        recs = read_shim_log(self.shim_log)
        self.assert_isolated(recs, "R5-B2-10")
        for rec in recs:
            given = [rec["args"][i + 1] for i, a in enumerate(rec["args"][:-1]) if a == "-c"]
            self.assertIn("core.longpaths=true", given, "git %s" % rec["args"][:6])
            safe = [g.split("=", 1)[1] for g in given if g.startswith("safe.directory=")]
            self.assertEqual([_norm(s) for s in safe], [_norm(work)],
                             "git %s: safe.directory is the one repository path, never *" % rec["args"][:6])

    def test_R5_B2_10_a_repository_whose_owner_check_fails_without_the_flag_still_reaches_its_verdict(self):
        self.install_shim("ownership")
        work = self.world(NAMES, NAMES[:1])
        self.expect(work, "names-removed", env=self.shim_env(), why="the shim fails every call that lacks safe.directory")

    def test_R5_B2_10_a_fixture_under_a_path_longer_than_260_characters_reaches_its_verdict(self):
        deep = self.root
        while len(str(deep)) < 290:
            deep = deep / ("long-folder-" + "x" * 28)
        try:
            work = make_world(deep, {RULES_REL: rules_bytes(NAMES)}, {RULES_REL: rules_bytes(NAMES[:1])})
        except (OSError, AssertionError) as exc:
            self.skipTest("this file system cannot hold a fixture repository under a path longer than 260 "
                          "characters (%s: %s)" % (type(exc).__name__, str(exc)[:120]))
        self.assertGreater(len(str(work)), 260, "control: the fixture path is longer than 260 characters")
        self.expect(work, "names-removed", why="a deep fixture")


# -----------------------------------------------------------------------------------------------------
# R5-W4-1, R5-W4-2: --fetch names its destination and trusts only a ref that equals the remote's tip
# -----------------------------------------------------------------------------------------------------
class FetchDestinationTests(RemedyCase):

    def _moved_world(self):
        """origin/master in ``work`` is C0 (first name only); the remote's tip is C1 (both names). The working
        file drops the second name, exactly as C0 does, so only a fresh ref shows the removal."""
        origin = self.root / "origin.git"
        git(self.root, "init", "-q", "--bare", "-b", "master", str(origin))
        seed = self.root / "seed"
        git(self.root, "clone", "-q", str(origin), str(seed))
        (seed / ".claude" / "hooks").mkdir(parents=True)
        (seed / RULES_REL).write_bytes(rules_bytes(NAMES[:1]))
        git(seed, "add", "-A")
        git(seed, "commit", "-q", "-m", "older commit, first name only")
        git(seed, "push", "-q", "origin", "HEAD:refs/heads/master")
        c0 = git(seed, "rev-parse", "HEAD")
        work = self.root / "work"
        git(self.root, "clone", "-q", str(origin), str(work))
        (seed / RULES_REL).write_bytes(rules_bytes(NAMES))
        git(seed, "commit", "-q", "-am", "tip, both names")
        git(seed, "push", "-q", "origin", "HEAD:refs/heads/master")
        c1 = git(seed, "rev-parse", "HEAD")
        self.assertEqual(git(work, "rev-parse", "refs/remotes/origin/master"), c0, "control: the local ref is the older commit")
        self.assertNotEqual(c0, c1, "control: the remote moved on")
        return work, c0, c1

    def _fetch_rec(self):
        fetches = [r for r in read_shim_log(self.shim_log) if shim_subcommand(r["args"]) == "fetch"]
        self.assertTrue(fetches, "control: the check ran a git fetch through the recording git")
        return fetches[0]["args"]

    def _assert_explicit_fetch(self, work, c1):
        obj = self.expect(work, "names-removed", "--fetch", env=self.shim_env(), why="--fetch against a moved remote")
        self.assertIs(obj.get("fetched"), True, "the ref now equals the remote's tip, so fetched is true")
        self.assertEqual(git(work, "rev-parse", "refs/remotes/origin/master"), c1, "the ref was moved to the remote's tip")
        args = self._fetch_rec()
        self.assertIn("+refs/heads/master:refs/remotes/origin/master", args, "the destination is named explicitly: %r" % args)
        self.assertIn("--no-tags", args, "no tags are fetched: %r" % args)
        self.assertIn("--no-write-fetch-head", args, "FETCH_HEAD is not written: %r" % args)

    def test_R5_W4_1_a_fixture_with_no_remote_fetch_refspec_still_updates_the_default_branch_ref(self):
        self.install_shim()
        work, c0, c1 = self._moved_world()
        git(work, "config", "--unset-all", "remote.origin.fetch")
        self.assertEqual(git(work, "config", "--get-all", "remote.origin.fetch", check=False), "", "control: no refspec")
        self._assert_explicit_fetch(work, c1)

    def test_R5_W4_1_a_refspec_that_maps_the_default_branch_elsewhere_decides_nothing(self):
        self.install_shim()
        work, c0, c1 = self._moved_world()
        git(work, "config", "--replace-all", "remote.origin.fetch", "+refs/heads/master:refs/remotes/elsewhere/master")
        self._assert_explicit_fetch(work, c1)

    def test_R5_W4_2_a_fetch_that_succeeds_without_writing_the_ref_is_not_fetched(self):
        self.install_shim("fetch-silent")
        work, c0, c1 = self._moved_world()
        c0_date = git(work, "show", "-s", "--format=%cI", c0)
        rc, obj, out, err = self.run_checker(work, "--fetch", env=self.shim_env())
        self.assertIsNotNone(obj, "one JSON object. stdout=%r stderr=%r" % (out[:200], err[:300]))
        self.assertEqual(git(work, "rev-parse", "refs/remotes/origin/master"), c0, "control: the shim wrote nothing")
        self.assertIs(obj.get("fetched"), False,
                      "ls-remote advertises %s but the ref still says %s: never fetched:true. Result %r" % (c1[:8], c0[:8], obj))
        text = json.dumps(obj) + err
        self.assertIn("ref-not-updated", text, "the reason is named. stderr=%r result=%r" % (err[:300], obj))
        self.assertIn(c0_date, text + out, "the compared ref's commit date is disclosed. stderr=%r" % err[:300])
        self.assertEqual((obj.get("verdict"), rc), ("kept", 0), "the stale ref is compared, as an offline run is. %r" % obj)

    def test_R5_W4_2_control_an_honest_fetch_through_the_same_shim_is_fetched_true(self):
        self.install_shim("record")
        work, c0, c1 = self._moved_world()
        obj = self.expect(work, "names-removed", "--fetch", env=self.shim_env(), why="an honest fetch")
        self.assertIs(obj.get("fetched"), True, "control: the shim in record mode lets the fetch write the ref")


# -----------------------------------------------------------------------------------------------------
# C3: rules-path aliases (R5-B3-2 to R5-B3-6)
# -----------------------------------------------------------------------------------------------------
ALIAS_SHAPES = {
    "the file name in another letter case": ".claude/hooks/DB-destructive-guard.rules.json",
    "the hooks folder in another letter case": ".claude/Hooks/db-destructive-guard.rules.json",
    "a top-level .Claude beside .claude": ".Claude/hooks/db-destructive-guard.rules.json",
    "a trailing dot on the file": ".claude/hooks/db-destructive-guard.rules.json.",
    "a trailing dot on the folder": ".claude./hooks/db-destructive-guard.rules.json",
    "a trailing space on the file": ".claude/hooks/db-destructive-guard.rules.json ",
    "a ::$DATA stream suffix": ".claude/hooks/db-destructive-guard.rules.json::$DATA",
    "an 8.3 shape on the file": ".claude/hooks/DB-DES~1.JSO",
    "an 8.3 shape on the folder": "CLAUDE~1/hooks/db-destructive-guard.rules.json",
}
#: R5-B3-5 and R5-B3-6: letters that only a wider fold equates with the ASCII ones.
UNICODE_SHAPES = {
    "U+0131 for the i of destructive": ".claude/hooks/db-destructıve-guard.rules.json",
    "U+017F for the s of hooks": ".claude/hookſ/db-destructive-guard.rules.json",
    "U+212A (Kelvin sign) for the k of hooks": ".claude/hooKs/db-destructive-guard.rules.json",
    "U+0130 for the i of destructive": ".claude/hooks/db-destructİve-guard.rules.json",
}


class AliasTests(RemedyCase):

    def setUp(self):
        super().setUp()
        self.repo = make_world(self.root, {RULES_REL: rules_bytes(NAMES)})

    def good(self, extra=None):
        files = {RULES_REL: rules_bytes(NAMES)}
        files.update(extra or {})
        return plumbing_commit(self.repo, files)

    def verdict_of(self, working, default, expected, why):
        self.expect(self.repo, expected, "--working-ref", working, "--default-ref", default, why=why)

    # -- the working side ---------------------------------------------------------------------------------
    def _each_alias(self, shapes, side, note=""):
        for label, alias in shapes.items():
            with self.subTest(alias=label, side=side):
                if side == "working":
                    working = self.good({alias: rules_bytes(NAMES[:1])})
                    self.verdict_of(working, self.good(), "working-malformed", "working side: " + label + note)
                else:
                    default = self.good({alias: rules_bytes(NAMES)})
                    self.verdict_of(self.good(), default, "reference-malformed", "default side: " + label + note)

    def test_R5_B3_2_every_alias_of_the_rules_path_is_working_malformed(self):
        self._each_alias(ALIAS_SHAPES, "working")

    def test_R5_B3_3_the_same_aliases_on_the_default_side_are_reference_malformed(self):
        self._each_alias(ALIAS_SHAPES, "default")

    def test_R5_B3_5_non_ascii_folding_of_the_file_and_the_folder_is_malformed_on_both_sides(self):
        shapes = {k: v for k, v in UNICODE_SHAPES.items() if k.startswith(("U+0131", "U+017F"))}
        self._each_alias(shapes, "working")
        self._each_alias(shapes, "default")

    def test_R5_B3_6_the_lowercase_half_and_the_explicit_family_are_malformed_on_both_sides(self):
        """NAMED EDIT (#623 t18, F9): the U+212A (Kelvin sign) case is caught by THREE independent routes:
        ``casefold()`` (the sign folds to a plain k), ``lower()`` (so does its lowercase) and the explicit
        family (it is listed there by hand). It therefore fails ONLY when all three are gone: an upper-only
        fold with the Kelvin sign also dropped from the family. An upper-only fold on its own does not fail
        this row (Revision 5 said it did; Revision 6, F9, corrects that). U+0130 is the other member: it
        needs ``lower()`` or the family. No assertion changed; only this text."""
        shapes = {k: v for k, v in UNICODE_SHAPES.items() if k.startswith(("U+212A", "U+0130"))}
        note = (" (U+212A is caught by casefold(), by lower() and by the explicit family; this fails only when all "
                "three are gone, an upper-only fold with the Kelvin sign also dropped from the family)")
        self._each_alias(shapes, "working", note)
        self._each_alias(shapes, "default", note)

    def test_R5_B3_3_a_default_commit_holding_only_an_alias_is_reference_malformed_never_first_install(self):
        for label, alias in ALIAS_SHAPES.items():
            with self.subTest(alias=label):
                default = plumbing_commit(self.repo, {alias: rules_bytes(NAMES)})
                self.verdict_of(self.good(), default, "reference-malformed", "only the alias on the default branch: " + label)

    # -- controls: the rows above cannot be satisfied by calling everything malformed -----------------------
    def test_R5_B3_control_a_commit_with_unrelated_paths_beside_the_exact_file_is_kept(self):
        extra = {"README.txt": b"x\n", "src/hooks/db-destructive-guard.rules.json": b"{}",
                 "db-destructive-guard.rules.json": b"{}", ".claude/hooks/other.json": b"{}"}
        self.verdict_of(self.good(extra), self.good(extra), "kept", "no alias among these paths")

    def test_R5_B3_6_a_name_one_character_longer_than_an_alias_is_not_an_alias(self):
        for label, path in {"hookss": ".claude/hookss/db-destructive-guard.rules.json",
                            "file name plus s": ".claude/hooks/db-destructive-guard.rules.jsons",
                            "dotclaude plus x": ".claudex/hooks/db-destructive-guard.rules.json"}.items():
            with self.subTest(path=label):
                self.verdict_of(self.good({path: rules_bytes(NAMES[:1])}), self.good(), "kept",
                                "%s is a different name, not an alias" % label)

    def test_R5_B3_control_a_default_commit_with_no_rules_file_and_no_alias_is_still_first_install(self):
        default = plumbing_commit(self.repo, {"README.txt": b"x\n"})
        self.verdict_of(self.good(), default, "first-install", "nothing on the default branch")

    # -- R5-B3-4: disk mode ---------------------------------------------------------------------------------
    def test_R5_B3_4_an_alias_in_the_index_is_working_malformed_at_the_file_and_at_the_top_level_folder(self):
        for label, alias in {"the file": ".claude/hooks/DB-destructive-guard.rules.json",
                             "the top-level folder": ".Claude/hooks/db-destructive-guard.rules.json"}.items():
            with self.subTest(index_alias=label):
                world_root = self.root / ("idx-" + label.replace(" ", "-"))
                world_root.mkdir()
                work = make_world(world_root, {RULES_REL: rules_bytes(NAMES)})
                git(work, "config", "core.ignorecase", "false")
                blob = hash_blob(work, rules_bytes(NAMES[:1]))
                git(work, "update-index", "--add", "--cacheinfo", "100644,%s,%s" % (blob, alias))
                listed = git(work, "ls-files", "-z", "--full-name").split("\0")
                self.assertIn(alias, listed, "control: the alias is in the index beside the exact path")
                self.assertIn(RULES_REL, listed, "control: and so is the exact path")
                self.expect(work, "working-malformed", env=None, why="disk mode, alias in the index: " + label)

    def test_R5_B3_4_control_an_index_without_an_alias_is_kept_in_disk_mode(self):
        self.expect(self.repo, "kept", why="disk mode, the index and the disk hold the one exact path")

    def test_R5_B3_4_a_case_variant_second_file_in_a_directory_listing_is_working_malformed(self):
        hooks = self.repo / ".claude" / "hooks"
        variant = hooks / "DB-destructive-guard.rules.json"
        variant.write_bytes(rules_bytes(NAMES[:1]))
        listing = sorted(os.listdir(str(hooks)))
        if len([n for n in listing if n.lower() == "db-destructive-guard.rules.json"]) < 2:
            self.skipTest("this file system folds letter case within a folder (listing: %r), so a second "
                          "case-variant file cannot exist on disk here" % listing)
        self.expect(self.repo, "working-malformed", why="a second file differing only in letter case")


# =====================================================================================================
# REVISION 6 REMEDY (block 18, RED). The blocked reviews of gates 4 and 16, findings T1, T3, T4 and the
# guard rows F3-1 and F3-2, with invariants C6 (duplicate entries), C7 (excluded roots) and C8 (one rule for
# path spellings). Contract 2026-10-13-database-guard-names-in-rules-file, Revision 6.
#
# NAMES THIS SUITE PINS (Revision 6, "Names and shapes pinned for block 18's tests"), each in BOTH
# .claude/hooks/_protected_names.py and .claude/scripts/land_contract.py (loaded here by path; the landing keeps
# a local copy and never imports the helper):
#   linked_worktrees(root) -> list[str]   C7's set minus the call's working folder: the main checkout, every
#       linked worktree and the common git folder (and so the project root itself), read with no git process.
#       An unreadable or unparseable .git, commondir or gitdir file RAISES (any exception: this suite only
#       needs a raise; the check then reads it as unverifiable); a missing worktrees folder is no error.
#   comparable_path(path) -> str          C8's resolved spelling (steps 1 to 5).
#   written_path(path) -> str             C8's written spelling (steps 1, 2 and 5, abspath for realpath).
#   resolve_git(path_value, excluded_roots) -> str | None   (existing) skips an entry when either spelling
#       of the entry lies inside either spelling of a root.
# A row that needs one of these asks for it through ``need``, so its absence is an ASSERTION failure that
# names the missing function, never an ImportError.
#
# SAFETY. Every fixture lives in self.root (removed whether the row passes or fails). Planted programs are
# recorders in test-owned folders. A junction, a case-sensitive folder and a ``.claude.`` folder made with the
# \\?\ prefix are removed by their own cleanup (the dot-ending folder through the \\?\ prefix) before the
# case's root is. Nothing is planted in the real system temporary folder or on the real PATH: a row that
# changes PATH hands the changed value only to the process it starts.
# =====================================================================================================
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
LAND = SCRIPTS_DIR / "land_contract.py"
_LOADED_COPIES = {}


def load_copy(label):
    """One of the two copies of the path rules, loaded by path (never by import name): ``_protected_names``
    or ``land_contract``."""
    if label not in _LOADED_COPIES:
        path = HELPER if label == "_protected_names" else LAND
        if not path.is_file():
            raise unittest.SkipTest("%s is not present in this checkout, so its copy of the rule cannot be compared"
                                    % path.name)
        if label == "land_contract" and str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        spec = importlib.util.spec_from_file_location("_t18_" + label, str(path))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LOADED_COPIES[label] = module
    return _LOADED_COPIES[label]


def both_copies():
    return [(label, load_copy(label)) for label in ("_protected_names", "land_contract")]


def real_git_exe():
    found = shutil.which("git")
    if not found:
        raise unittest.SkipTest("no git on PATH")
    return found


def raw_tree(repo, entries):
    """A tree object whose entries are written IN THE ORDER GIVEN, duplicates included (``git mktree`` would
    sort them; ``--literally`` skips the checks). ``entries`` is a list of (mode, name, object id)."""
    body = b"".join(mode.encode("ascii") + b" " + name.encode("utf-8") + b"\0" + bytes.fromhex(oid)
                    for mode, name, oid in entries)
    return git_in(repo, "hash-object", "-t", "tree", "-w", "--literally", "--stdin", input=body)


RULES_NAME = "db-destructive-guard.rules.json"


def duplicate_commit(repo, shape, kept_first):
    """A parentless commit holding TWO entries where the rules path has one: ``file`` (the file entry
    doubled), ``hooks-folder`` (the hooks folder entry doubled) or ``claude-folder`` (the .claude folder entry
    doubled). The first listed copy keeps both names when ``kept_first``, else the narrowed one comes first."""
    kept = hash_blob(repo, rules_bytes(NAMES))
    narrowed = hash_blob(repo, rules_bytes(NAMES[:1]))
    readme = hash_blob(repo, b"x\n")
    first, second = (kept, narrowed) if kept_first else (narrowed, kept)

    def hooks(blobs):
        return raw_tree(repo, [("100644", RULES_NAME, blob) for blob in blobs])

    if shape == "file":
        claude = raw_tree(repo, [("40000", "hooks", hooks([first, second]))])
        root = raw_tree(repo, [("100644", "README.txt", readme), ("40000", ".claude", claude)])
    elif shape == "hooks-folder":
        claude = raw_tree(repo, [("40000", "hooks", hooks([first])), ("40000", "hooks", hooks([second]))])
        root = raw_tree(repo, [("100644", "README.txt", readme), ("40000", ".claude", claude)])
    else:
        one = raw_tree(repo, [("40000", "hooks", hooks([first]))])
        two = raw_tree(repo, [("40000", "hooks", hooks([second]))])
        root = raw_tree(repo, [("100644", "README.txt", readme), ("40000", ".claude", one), ("40000", ".claude", two)])
    return git_in(repo, "commit-tree", root, "-m", "duplicate entries (%s)" % shape)


class SecondRemedyCase(RemedyCase):

    def need(self, module, label, name):
        fn = getattr(module, name, None)
        if fn is None:
            self.fail("%s.%s does not exist yet: Revision 6 (Names and shapes pinned for block 18's tests) adds it, "
                      "so this row cannot say anything until block 19" % (label, name))
        return fn

    def plant(self, folder):
        """A file named like git in ``folder`` (a recorder stands in: resolve_git only asks whether it is a file)."""
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / shim_name()
        target.write_bytes(b"MZ planted\n")
        if os.name != "nt":
            target.chmod(0o755)
        return target

    def linked_world(self):
        """A main checkout ``work`` with an origin whose default branch keeps both names, and two linked
        worktrees ``wt1`` and ``wt2`` of it."""
        work = self.world(NAMES)
        wt1, wt2 = self.root / "wt1", self.root / "wt2"
        git(work, "worktree", "add", "-q", "-b", "wt1-branch", str(wt1))
        git(work, "worktree", "add", "-q", "-b", "wt2-branch", str(wt2))
        return work, wt1, wt2


# -----------------------------------------------------------------------------------------------------
# C6 / T1: two entries of the rules path
# -----------------------------------------------------------------------------------------------------
class DuplicateEntryTests(SecondRemedyCase):

    def setUp(self):
        super().setUp()
        self.repo = make_world(self.root, {RULES_REL: rules_bytes(NAMES)})
        self.good = plumbing_commit(self.repo, {RULES_REL: rules_bytes(NAMES)})

    def _each(self, side):
        for shape in ("file", "hooks-folder", "claude-folder"):
            for kept_first in (True, False):
                label = "%s doubled, %s copy first" % (shape, "kept" if kept_first else "narrowed")
                with self.subTest(shape=shape, kept_first=kept_first, side=side):
                    dup = duplicate_commit(self.repo, shape, kept_first)
                    working, default = (dup, self.good) if side == "working" else (self.good, dup)
                    verdict = "working-malformed" if side == "working" else "reference-malformed"
                    obj = self.expect(self.repo, verdict, "--working-ref", working, "--default-ref", default,
                                      why="R6-T1-1 %s side, %s: git checkout writes the LAST entry, while a read by "
                                          "<commit>:<path> takes the FIRST (older git) or is refused with exit 128 "
                                          "(newer git, which reads as unverifiable). The rules path listed twice is "
                                          "malformed with reason duplicate-entry, never kept, never first-install, "
                                          "never unverifiable" % (side, label))
                    self.assertIn("duplicate-entry", str(obj.get("reason")),
                                  "R6-T1-1 %s side, %s: the malformed reason is duplicate-entry. Result %r" % (side, label, obj))

    def test_R6_T1_1_a_duplicate_rules_path_on_the_working_side_is_working_malformed_with_reason_duplicate_entry(self):
        self._each("working")

    def test_R6_T1_1_a_duplicate_rules_path_on_the_default_side_is_reference_malformed_with_reason_duplicate_entry(self):
        self._each("default")

    def test_R6_T1_1_control_the_fixture_trees_hold_the_rules_path_twice_and_a_clean_tree_is_kept(self):
        """Without this a row above could pass because the fixture never held a duplicate (or fail on a fixture bug)."""
        for shape in ("file", "hooks-folder", "claude-folder"):
            dup = duplicate_commit(self.repo, shape, True)
            listing = git_in(self.repo, "ls-tree", "-r", "--name-only", dup).splitlines()
            self.assertEqual(listing.count(RULES_REL), 2, "control: %s leaves the exact path listed twice (%r)" % (shape, listing))
        self.expect(self.repo, "kept", "--working-ref", self.good, "--default-ref", self.good,
                    why="control: a tree with the exact path once is kept")


# -----------------------------------------------------------------------------------------------------
# C7 / T3: linked_worktrees from a linked worktree, and the PATH walk it feeds
# -----------------------------------------------------------------------------------------------------
class LinkedWorktreesTests(SecondRemedyCase):

    def _norm_set(self, paths):
        return {_norm(p) for p in paths}

    def test_R6_T3_1_from_main_and_from_a_linked_worktree_the_set_is_the_same_and_holds_the_main_checkout(self):
        work, wt1, wt2 = self.linked_world()
        want = self._norm_set([work, wt1, wt2, work / ".git"])
        for label, module in both_copies():
            fn = self.need(module, label, "linked_worktrees")
            from_main, from_linked = self._norm_set(fn(str(work))), self._norm_set(fn(str(wt1)))
            self.assertIn(_norm(work), from_linked,
                          "%s: from a linked worktree the main checkout is in the set (its commondir, ../.., is resolved "
                          "relative to the git folder). Got %r" % (label, sorted(from_linked)))
            self.assertEqual(from_main, from_linked, "%s: the same set from the main checkout and from a linked worktree" % label)
            self.assertEqual(from_linked, want, "%s: the main checkout, both linked worktrees and the common folder" % label)

    def test_R6_T3_1_a_git_file_whose_gitdir_cannot_be_read_gives_unverifiable(self):
        for label, module in both_copies():
            fn = self.need(module, label, "linked_worktrees")
            for what, text in (("a gitdir line that names a folder that does not exist", "gitdir: %s\n" % (self.root / "no-such-git-dir")),
                               ("a .git file with no gitdir line", "this is not a gitdir pointer\n")):
                with self.subTest(copy=label, shape=what):
                    folder = self.root / ("broken-%s-%s" % (label, abs(hash(what))))
                    folder.mkdir()
                    (folder / ".git").write_text(text, encoding="utf-8")
                    with self.assertRaises(Exception, msg="%s: %s must raise (unverifiable), not return an empty list" % (label, what)):
                        fn(str(folder))
        work = self.world(NAMES)
        broken = self.root / "broken-for-check"
        broken.mkdir()
        (broken / ".git").write_text("gitdir: %s\n" % (self.root / "no-such-git-dir"), encoding="utf-8")
        self.expect(broken, "unverifiable", why="check() on a project whose .git file points nowhere")

    def test_R6_T3_1_a_commondir_that_exists_but_cannot_be_read_or_holds_no_path_gives_unverifiable(self):
        work, wt1, wt2 = self.linked_world()
        pointer = work / ".git" / "worktrees" / "wt1" / "commondir"
        self.assertTrue(pointer.is_file(), "control: a linked worktree's git folder holds a commondir file")
        original = pointer.read_bytes()
        for label, module in both_copies():
            fn = self.need(module, label, "linked_worktrees")
            for what in ("holds no path", "is a folder, not a readable file"):
                with self.subTest(copy=label, commondir=what):
                    if pointer.is_dir():
                        pointer.rmdir()
                    if what == "holds no path":
                        pointer.write_bytes(b"\n")
                    else:
                        if pointer.exists():
                            pointer.unlink()
                        pointer.mkdir()
                    with self.assertRaises(Exception, msg="%s: a commondir that %s must raise (unverifiable)" % (label, what)):
                        fn(str(wt1))
        if pointer.is_dir():
            pointer.rmdir()
        pointer.write_bytes(original)
        self.expect(wt1, "kept", why="control: with commondir restored the linked worktree reaches its normal verdict")

    def test_R6_T3_1_a_gitdir_file_under_the_worktrees_folder_that_cannot_be_read_gives_unverifiable(self):
        work, wt1, wt2 = self.linked_world()
        pointer = work / ".git" / "worktrees" / "wt1" / "gitdir"
        self.assertTrue(pointer.is_file(), "control: the worktrees folder holds one gitdir file per linked worktree")
        self.expect(work, "kept", why="control: before the file is damaged the main checkout is kept")
        pointer.unlink()
        pointer.mkdir()  # exists, cannot be read as a file; git itself never reads it for the calls the check makes
        for label, module in both_copies():
            fn = self.need(module, label, "linked_worktrees")
            with self.assertRaises(Exception, msg="%s: a gitdir entry that exists but cannot be read must raise" % label):
                fn(str(work))
        self.expect(work, "unverifiable", why="the check cannot tell which folders are linked worktrees, so it says so")

    def test_R6_T3_1_a_common_folder_with_no_worktrees_folder_gives_the_main_checkout_and_the_common_folder_only(self):
        work = self.world(NAMES)
        self.assertFalse((work / ".git" / "worktrees").exists(), "control: no linked worktree was ever made")
        for label, module in both_copies():
            fn = self.need(module, label, "linked_worktrees")
            self.assertEqual(self._norm_set(fn(str(work))), self._norm_set([work, work / ".git"]),
                             "%s: a missing worktrees folder is an empty list, not an error; the set is the main checkout and "
                             "the common folder only" % label)
        self.expect(work, "kept", why="and the check reaches its normal verdict")


class EqualCopiesTests(SecondRemedyCase):

    def test_R6_EQ_the_two_copies_return_equal_results_for_the_same_inputs(self):
        """Extends R5-B2-6 (the environment rule and the git resolution): the path rules exist twice."""
        work, wt1, wt2 = self.linked_world()
        copies = both_copies()
        helper, landing = copies[0][1], copies[1][1]
        fns = {name: [self.need(module, label, name) for label, module in copies]
               for name in ("linked_worktrees", "comparable_path", "written_path")}
        for project in (work, wt1, wt2):
            a, b = (sorted(_norm(p) for p in fn(str(project))) for fn in fns["linked_worktrees"])
            self.assertEqual(a, b, "linked_worktrees(%s) is equal in the two copies" % project.name)
        inputs = [str(work), str(work) + "\\x\\..\\y", str(work).upper(), str(work) + "\\", "relative\\folder"]
        if os.name == "nt":
            drive, tail = os.path.splitdrive(str(work))
            inputs += ["\\\\?\\" + str(work), "\\\\.\\" + str(work), "\\\\localhost\\%s$\\%s" % (drive[:1], tail.strip("\\")),
                       "\\\\?\\UNC\\127.0.0.1\\%s$\\%s" % (drive[:1], tail.strip("\\"))]
        for name in ("comparable_path", "written_path"):
            for text in inputs:
                a, b = (fn(text) for fn in fns[name])
                self.assertEqual(a, b, "%s(%r) is equal in the two copies" % (name, text))
        # NAMED EDIT (#623 t25, L1; Revision 7 asked to "extend R6-EQ" and Revision 8 names the edit): is_device_path (C12) is
        # compared in both copies over R7-N3-1's inputs, the device spellings and the spellings that are not device paths,
        # so a one-copy change (MN3-isdev-l) and a change on the pipe form alone (MN3-isdev-l-pipe) turn THIS row red too.
        is_device = [self.need(module, label, "is_device_path") for label, module in copies]
        for text in DEVICE_SPELLINGS + NOT_DEVICE_SPELLINGS:
            a, b = (fn(text) for fn in is_device)
            self.assertEqual(a, b, "is_device_path(%r) is equal in the two copies (_protected_names gave %r, land_contract gave %r)"
                             % (text, a, b))


    def test_R6_EQ_J_the_two_copies_resolve_a_junction_to_a_long_named_folder_to_equal_results(self):
        """W2 (Revision 9): R6-EQ's inputs hold no link, so removing ``realpath`` from ONE copy (MT4-s2-h or MT4-s2-l) turned no row
        red in the comparison. A junction ``O\\j`` -> the long-named ``O\\long-target`` (``O`` outside every root) makes the two
        copies differ the moment one stops following links. The junction is a fixture: it is never skipped."""
        if os.name != "nt":
            self.skipTest("a junction exists only on Windows")
        owned = self.root / "o-outside-every-root"
        real_sub = owned / "a-rather-long-target-folder-name" / "sub"
        real_sub.mkdir(parents=True)
        link = _junction_or_fail(self, owned / "a-rather-long-target-folder-name", owned / "j")
        copies = both_copies()
        fns = [self.need(module, label, "comparable_path") for label, module in copies]
        self.assertTrue(_local_spelling(link).endswith("a-rather-long-target-folder-name"),
                        "control: the junction %s really leads to the long-named folder" % link)
        for text in (str(link), str(link / "sub")):
            a, b = (fn(text) for fn in fns)
            self.assertEqual(a, b, "comparable_path(%r) is equal in the two copies (_protected_names gave %r, land_contract gave %r)"
                             % (text, a, b))


# -----------------------------------------------------------------------------------------------------
# C7 / T3: the PATH walk from a linked worktree (the checker child, disk mode and --working-ref mode)
# -----------------------------------------------------------------------------------------------------
class LinkedWorktreePathWalkTests(SecondRemedyCase):

    def _planted(self, work):
        folder = work / "tools-planted"
        log = self.root / "planted-main.log"
        make_git_shim(folder, log, mode="planted")
        return folder, log

    def _path(self, folder):
        return os.pathsep.join([str(folder), os.path.dirname(real_git_exe())])

    def test_R6_T3_2_disk_mode_from_a_linked_worktree_never_runs_a_git_planted_in_the_main_checkout(self):
        work, wt1, wt2 = self.linked_world()
        (wt1 / RULES_REL).write_bytes(rules_bytes(NAMES[:1]))
        folder, log = self._planted(work)
        rc, obj, out, err = self.run_checker(wt1, env={"PATH": self._path(folder)})
        self.assertEqual([r["args"][:3] for r in read_shim_log(log)], [],
                         "a git planted in the MAIN checkout (a .venv\\Scripts or node_modules\\.bin folder) is inside a tree "
                         "under check and must never run, even when the project is a linked worktree")
        self.assertEqual((obj or {}).get("verdict"), "names-removed",
                         "the real git, after the planted entry, reaches the fixture's verdict (a hostile git here answers "
                         "nothing, which reads as unverifiable or first-install). Result %r stderr=%r" % (obj, err[:200]))
        self.assertEqual(rc, 10)

    def test_R6_T3_2_working_ref_mode_from_a_linked_worktree_never_runs_a_git_planted_in_the_main_checkout(self):
        work, wt1, wt2 = self.linked_world()
        (wt1 / RULES_REL).write_bytes(rules_bytes(NAMES[:1]))
        git(wt1, "commit", "-q", "-am", "narrow the list")
        folder, log = self._planted(work)
        rc, obj, out, err = self.run_checker(wt1, "--working-ref", "HEAD", env={"PATH": self._path(folder)})
        self.assertEqual([r["args"][:3] for r in read_shim_log(log)], [],
                         "no git planted in the main checkout may run in --working-ref mode either")
        self.assertEqual((obj or {}).get("verdict"), "names-removed", "Result %r stderr=%r" % (obj, err[:200]))
        self.assertEqual(rc, 10)

    def test_R6_T3_2_control_the_same_planted_git_is_the_one_that_runs_when_it_is_first_and_outside_every_tree(self):
        """Without this the rows above could pass because the recorder never starts at all."""
        work, wt1, wt2 = self.linked_world()
        elsewhere = self.root / "elsewhere-bin"
        log = self.root / "planted-elsewhere.log"
        make_git_shim(elsewhere, log, mode="planted")
        rc, obj, out, err = self.run_checker(wt1, env={"PATH": self._path(elsewhere)})
        self.assertTrue(read_shim_log(log), "control: a planted git in a folder outside every tree IS chosen (this is the "
                                            "documented residual) and its calls are recorded")


# -----------------------------------------------------------------------------------------------------
# C8 / T4: one rule for path spellings
# -----------------------------------------------------------------------------------------------------
UNC_KINDS = ("long-unc-localhost", "unc-localhost", "unc-127-0-0-1", "unc-own-name")
SPELLING_KINDS = ("long-prefix", "device-prefix") + UNC_KINDS + ("letter-case",)


def spelled_folder(root, kind, leaf="x"):
    """``<root>\\<leaf>`` written in one of the spellings of C8's threat model (covered list)."""
    root = str(root)
    drive, tail = os.path.splitdrive(root)
    letter, tail = drive[:1], tail.strip("\\")
    host = {"long-unc-localhost": "localhost", "unc-localhost": "localhost", "unc-127-0-0-1": "127.0.0.1",
            "unc-own-name": socket.gethostname()}.get(kind)
    if kind == "long-prefix":
        return "\\\\?\\" + root + "\\" + leaf
    if kind == "device-prefix":
        return "\\\\.\\" + root + "\\" + leaf
    if kind == "long-unc-localhost":
        return "\\\\?\\UNC\\%s\\%s$\\%s\\%s" % (host, letter, tail, leaf)
    if kind in UNC_KINDS:
        return "\\\\%s\\%s$\\%s\\%s" % (host, letter, tail, leaf)
    return root.swapcase() + "\\" + leaf  # letter-case


class PathSpellingCase(SecondRemedyCase):

    def setUp(self):
        super().setUp()
        if os.name != "nt":
            self.skipTest("these spellings (\\\\?\\, \\\\.\\, UNC administrative shares) exist only on Windows")
        self.excluded = self.root / "root"
        self.excluded.mkdir()
        self.plant(self.excluded / "x")
        self.git_exe = real_git_exe()

    def assert_real_git(self, path_value, roots, why):
        for label, module in both_copies():
            resolve = self.need(module, label, "resolve_git")
            got = resolve(path_value, roots)
            self.assertTrue(got, "%s: %s: a git was found (the real one, last on PATH)" % (label, why))
            self.assertEqual(_norm(got), _norm(self.git_exe),
                             "%s: %s: the planted git in the excluded root must be skipped and the real git returned, not %r"
                             % (label, why, got))


class PathSpellingRowTests(PathSpellingCase):
    pass


def _spelling_rows():
    def string_half(kind):
        def test(self):
            expected_tail = os.sep + "x"
            for label, module in both_copies():
                comparable = self.need(module, label, "comparable_path")
                spelled = spelled_folder(self.excluded, kind)
                self.assertEqual(comparable(spelled), comparable(str(self.excluded)) + expected_tail,
                                 "%s: R6-T4-1 string half, %s: comparable_path of %r equals the root's comparable path plus "
                                 "\\x"
                                 % (label, kind, spelled))
        return test

    def end_to_end_half(kind):
        def test(self):
            spelled = spelled_folder(self.excluded, kind)
            if kind in UNC_KINDS and not os.path.isfile(os.path.join(spelled, shim_name())):
                self.skipTest("the administrative share %r cannot be reached from this account, so the planted git in the "
                              "excluded root is not reachable through that spelling and the row would prove nothing (the "
                              "string half of this spelling ran and never skips)" % spelled)
            self.assertTrue(os.path.isfile(os.path.join(spelled, shim_name())),
                            "control: the planted git is reachable through the spelling %r" % spelled)
            path_value = os.pathsep.join([spelled, os.path.dirname(self.git_exe)])
            self.assert_real_git(path_value, [str(self.excluded)], "R6-T4-1 end to end, %s" % kind)
        return test

    for kind in SPELLING_KINDS:
        slug = kind.replace("-", "_")
        setattr(PathSpellingRowTests, "test_R6_T4_1_string_half_%s" % slug, string_half(kind))
        setattr(PathSpellingRowTests, "test_R6_T4_1_end_to_end_half_%s" % slug, end_to_end_half(kind))


_spelling_rows()


class PathSpellingRootsTests(PathSpellingCase):

    def _root_spellings(self):
        drive, tail = os.path.splitdrive(str(self.excluded))
        return {"long-prefix": "\\\\?\\" + str(self.excluded),
                "unc-localhost": "\\\\localhost\\%s$\\%s" % (drive[:1], tail.strip("\\"))}

    def test_R6_T4_3_string_half_a_root_spelled_with_the_long_prefix_has_the_plain_roots_comparable_path(self):
        spelled = self._root_spellings()["long-prefix"]
        for label, module in both_copies():
            comparable = self.need(module, label, "comparable_path")
            self.assertEqual(comparable(spelled), comparable(str(self.excluded)),
                             "%s: the root %r and the plain root are one folder once C8 is applied to the roots too" % (label, spelled))

    def test_R6_T4_3_string_half_a_root_spelled_as_a_unc_path_has_the_plain_roots_comparable_path(self):
        spelled = self._root_spellings()["unc-localhost"]
        for label, module in both_copies():
            comparable = self.need(module, label, "comparable_path")
            self.assertEqual(comparable(spelled), comparable(str(self.excluded)),
                             "%s: the root %r (rewritten to its drive form before realpath, so no share is touched) equals the "
                             "plain root" % (label, spelled))

    def test_R6_T4_3_end_to_end_with_the_root_given_with_the_long_prefix_and_path_holding_the_plain_spelling(self):
        path_value = os.pathsep.join([str(self.excluded / "x"), os.path.dirname(self.git_exe)])
        self.assert_real_git(path_value, [self._root_spellings()["long-prefix"]],
                             "R6-T4-3: an implementation that applies C8 to the PATH entries but not to the roots fails here")

    def test_R6_T4_3_end_to_end_with_the_root_given_as_a_unc_path_and_path_holding_the_plain_spelling(self):
        path_value = os.pathsep.join([str(self.excluded / "x"), os.path.dirname(self.git_exe)])
        self.assert_real_git(path_value, [self._root_spellings()["unc-localhost"]],
                             "R6-T4-3: the root as \\\\localhost\\<letter>$\\... (no share is read: the root is only a string "
                             "that C8 rewrites)")


class JunctionTests(PathSpellingCase):
    """R6-T4-J and R6-T4-J2: a junction written INSIDE a tree that leads OUT of every root."""

    def _entry(self, root):
        return os.path.join(str(root), "ClientApp", "node_modules", ".bin")

    def test_R6_T4_J2_the_pure_half_the_written_spelling_of_the_bin_folder_lies_inside_the_written_spelling_of_the_root(self):
        for label, module in both_copies():
            written = self.need(module, label, "written_path")
            inner, outer = written(self._entry(self.excluded)), written(str(self.excluded))
            self.assertTrue(inner.startswith(outer.rstrip("\\/") + os.sep),
                            "%s: written_path of <root>\\ClientApp\\node_modules\\.bin (%r) lies inside written_path of the "
                            "root (%r) with no link on disk: C8 compares the spelling before any link is followed" % (label, inner, outer))

    def _make_junction(self, project_root):
        outside = self.root / "outside-every-root"
        (outside / ".bin").mkdir(parents=True)
        log = self.root / "junction-planted.log"
        make_git_shim(outside / ".bin", log, mode="planted")
        parent = Path(project_root) / "ClientApp"
        parent.mkdir(exist_ok=True)
        link = parent / "node_modules"
        try:
            import _winapi  # noqa: WPS433 -- Windows only, as the row
            _winapi.CreateJunction(str(outside), str(link))
        except (ImportError, AttributeError, OSError) as exc:
            self.skipTest("a junction cannot be created here (%s: %s); R6-T4-J2 still guards the rule" % (type(exc).__name__, exc))
        self.addCleanup(lambda: os.rmdir(str(link)) if os.path.lexists(str(link)) else None)  # the link only, never its target
        return log

    def test_R6_T4_J_a_bin_folder_reached_through_a_junction_that_leaves_the_tree_is_still_excluded(self):
        self._make_junction(self.excluded)
        entry = self._entry(self.excluded)
        self.assertTrue(os.path.isfile(os.path.join(entry, shim_name())),
                        "control: the recorder is reachable through the junction")
        self.assertNotEqual(_norm(entry), _norm(self.excluded) + os.sep + "clientapp" + os.sep + "node_modules" + os.sep + ".bin",
                            "control: the junction really leads out of the tree (the resolved folder is elsewhere)")
        path_value = os.pathsep.join([entry, os.path.dirname(self.git_exe)])
        self.assert_real_git(path_value, [str(self.excluded)], "R6-T4-J: written inside the root, resolved outside it")

    def test_R6_T4_J_a_check_with_such_a_folder_first_on_path_reaches_names_removed_and_never_runs_the_recorder(self):
        work = self.world(NAMES, NAMES[:1])
        log = self._make_junction(work)
        path_value = os.pathsep.join([self._entry(work), os.path.dirname(self.git_exe)])
        rc, obj, out, err = self.run_checker(work, env={"PATH": path_value})
        self.assertEqual([r["args"][:3] for r in read_shim_log(log)], [],
                         "the recorder behind <project>\\ClientApp\\node_modules\\.bin never runs: the entry is written inside the tree")
        self.assertEqual((obj or {}).get("verdict"), "names-removed",
                         "the real git, after the junction entry, reaches the fixture's verdict. Result %r stderr=%r" % (obj, err[:200]))
        self.assertEqual(rc, 10)


def short_path_name(path):
    """The 8.3 short spelling of an existing ``path`` (GetShortPathNameW, which only READS), or ``None`` when this is not
    Windows or the call fails. The volume setting that creates short names is never changed here."""
    if os.name != "nt":
        return None
    import ctypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    buf = ctypes.create_unicode_buffer(1024)
    size = kernel.GetShortPathNameW(str(path), buf, 1024)
    return buf.value if 0 < size < 1024 else None


class RealpathRouteTests(PathSpellingCase):
    """R8-G4-1 and R8-G4-2 (Revision 8, gate 21's finding G4, invariant C8): the two routes that ONLY ``realpath`` closes, in
    both copies. A junction made OUTSIDE every root that leads INTO a root, and an 8.3 short name of a root. The written
    spelling of such an entry lies outside the root, so only the resolved spelling can skip it. Removing ``realpath`` from
    ``comparable_path`` in ONE copy turns R6-EQ red; removing it from BOTH copies at once (mutation MT4-s2-both) turned no
    row red before these two. ``subst`` stays out of scope (the command is forbidden here)."""

    def _junction(self, target, link):
        """A junction ``link`` -> ``target``, both test-owned. Its cleanup removes the LINK only, before any target or root."""
        try:
            import _winapi  # noqa: WPS433 -- Windows only, as the row
            _winapi.CreateJunction(str(target), str(link))
        except (ImportError, AttributeError, OSError) as exc:
            self.skipTest("a junction cannot be created here (%s: %s); R8-G4-1 cannot say anything" % (type(exc).__name__, exc))
        self.addCleanup(lambda: os.rmdir(str(link)) if os.path.lexists(str(link)) else None)  # the link only, never its target
        return link

    def _outside(self, name):
        folder = self.root / name
        folder.mkdir()
        return folder

    def test_R8_G4_1_a_junction_made_outside_every_root_that_leads_into_a_root_is_skipped_in_both_copies(self):
        owned = self._outside("o-outside-every-root")
        link = self._junction(self.excluded / "x", owned / "J")
        self.assertTrue(os.path.isfile(os.path.join(str(link), shim_name())),
                        "control: the recorder inside the root is reachable through the junction %s" % link)
        path_value = os.pathsep.join([str(link), os.path.dirname(self.git_exe)])
        self.assert_real_git(path_value, [str(self.excluded)],
                             "R8-G4-1: written outside the root (%s), resolved INSIDE it: only realpath sees it" % link)

    def test_R8_G4_1_control_a_junction_made_outside_every_root_that_leads_to_a_folder_outside_every_root_is_returned(self):
        """Without this the row above could pass because a junction is never followed at all."""
        owned = self._outside("o-outside-every-root")
        target = self._outside("recorder-outside-every-root")
        planted = self.plant(target)
        link = self._junction(target, owned / "J2")
        path_value = os.pathsep.join([str(link), os.path.dirname(self.git_exe)])
        for label, module in both_copies():
            got = self.need(module, label, "resolve_git")(path_value, [str(self.excluded)])
            self.assertTrue(got, "%s: control: a git was found" % label)
            self.assertEqual(_norm(got), _norm(planted),
                             "%s: control: the recorder reached through a junction that leads outside every root IS the git "
                             "returned (the documented residual), so the row above proves realpath and not a broken fixture. "
                             "Got %r" % (label, got))

    def test_R8_G4_2_an_entry_spelled_through_the_roots_8_3_short_name_is_skipped_in_both_copies(self):
        short = short_path_name(self.excluded)
        if short is None:
            import ctypes  # noqa: WPS433 -- Windows only: short_path_name returns None here only on Windows
            self.skipTest("the short-name call failed: %s" % ctypes.get_last_error())
        if os.path.normcase(short) == os.path.normcase(str(self.excluded)):
            self.skipTest("no component of %s has a short name on this volume (8.3 names are off here), so there is no 8.3 "
                          "spelling of the root to test; R8-G4-1 alone carries MT4-s2-both. The volume setting is never changed."
                          % self.excluded)
        spelled = short + os.sep + "x"
        self.assertTrue(os.path.isfile(os.path.join(spelled, shim_name())),
                        "control: the recorder inside the root is reachable through the short spelling %s" % spelled)
        self.assertNotEqual(os.path.normcase(spelled), os.path.normcase(str(self.excluded / "x")),
                            "control: the spelling really differs from the long one")
        path_value = os.pathsep.join([spelled, os.path.dirname(self.git_exe)])
        self.assert_real_git(path_value, [str(self.excluded)],
                             "R8-G4-2: %s is the root's x folder through its 8.3 short name: only realpath expands it" % spelled)


class StatedResidualTests(PathSpellingCase):

    def test_R6_T4_R_a_unc_spelling_through_another_address_of_this_computer_is_NOT_recognised(self):
        """PINS A STATED LIMIT, not a goal: Revision 6, "Threat model for path spellings", lists "a UNC spelling
        through another address of this computer (its network address, an IPv6 literal, a DNS alias)" under
        "It does not cover". comparable_path of \\\\192.0.2.10\\<letter>$\\<root tail>\\x therefore does NOT lie
        inside the root's comparable path. A rule that later covers it changes THIS ROW DELIBERATELY (and the
        paragraph); an accidental change must fail here. The row passes whenever the function exists. The
        address is 192.0.2.10 (TEST-NET-1, RFC 5737: never routed), so no real share is meant; realpath may
        wait for a network answer that never comes."""
        drive, tail = os.path.splitdrive(str(self.excluded))
        spelled = "\\\\192.0.2.10\\%s$\\%s\\x" % (drive[:1], tail.strip("\\"))
        for label, module in both_copies():
            comparable = self.need(module, label, "comparable_path")
            inner, outer = comparable(spelled), comparable(str(self.excluded))
            self.assertFalse(inner == outer or inner.startswith(outer.rstrip("\\/") + os.sep),
                             "%s: R6-T4-R pins the stated residual of the Revision 6 threat model (another address of this "
                             "computer is not recognised). If a rule now covers it, change this row on purpose and say so in "
                             "that paragraph. comparable_path gave %r against the root %r" % (label, inner, outer))


# -----------------------------------------------------------------------------------------------------
# Block 27 (Revision 9, gate 26's findings G5, G6, W2): the link and spelling rows. Each row is TWO methods, -h (the helper,
# _protected_names.py) and -l (land_contract.py), so a one-copy mutation names its copy.
# -----------------------------------------------------------------------------------------------------
def _local_spelling(path):
    """The local drive spelling of ``path`` for comparing a returned program (Revision 9, decision 6). ``_norm`` keeps a
    ``\\\\?\\`` prefix and spells a share link as ``\\\\localhost\\C$\\...``, so it cannot be used here. This has its own
    regular expressions and never imports or calls either copy, so a mutation of a copy cannot change it."""
    text = os.path.realpath(str(path))
    text = re.sub(r"^\\\\\?\\UNC\\", r"\\\\", text, flags=re.IGNORECASE)
    text = re.sub(r"^\\\\[?.]\\(?=[A-Za-z]:)", "", text)
    hosts = "|".join(re.escape(h) for h in ("localhost", "127.0.0.1", socket.gethostname()))
    text = re.sub(r"^\\\\(?:%s)\\([A-Za-z])\$(?=\\|$)" % hosts, r"\1:", text, flags=re.IGNORECASE)
    return os.path.normcase(text)


def _drive_and_tail(path):
    """(``C:``, ``C``, the folder tail without its leading and trailing backslash) of an absolute local path."""
    drive, tail = os.path.splitdrive(str(path))
    return drive, drive[:1], tail.strip("\\")


def _junction_or_fail(case, target, link):
    """A junction ``link`` -> ``target``, both test-owned. A junction that cannot be made is a fixture failure, never a skip: a
    skip would leave the row's mutation guarded by nothing. The cleanup removes the LINK only, before any target or root."""
    try:
        import _winapi  # noqa: WPS433 -- Windows only, as the row
        _winapi.CreateJunction(str(target), str(link))
    except (ImportError, AttributeError, OSError) as exc:
        case.fail("fixture failure: a junction %s -> %s cannot be created here (%s: %s)"
                  % (link, target, type(exc).__name__, exc))
    case.addCleanup(lambda: os.rmdir(str(link)) if os.path.lexists(str(link)) else None)  # the link only, never its target
    return link


class LinkSpellingTests(PathSpellingCase):
    """R9-G5-* (C8, step 3 of ``comparable_path``) and R9-G6-* (C8, the written spelling), each in BOTH copies. Mutations
    MT4-s3-h/-l/-both turn the G5 rows' -h/-l/both methods red and MRV-wp-h/-l/-both do the same for the G6 rows. Each control
    is green at M4 and under the same mutation: the spelling under test reaches the planted program when no root contains it."""

    def setUp(self):
        super().setUp()
        self.owned = self.root / "o-outside-every-root"
        self.owned.mkdir()
        self.planted_log = self.root / "planted-recorder.log"

    def _plant_recorder(self, folder):
        """The suite's planted git (``make_git_shim``, mode ``planted``) in ``folder``; the local path it was made at."""
        return make_git_shim(folder, self.planted_log, mode="planted")

    def _path_value(self, entry):
        return os.pathsep.join([str(entry), os.path.dirname(self.git_exe)])

    def _assert_returns_real_git(self, label, got, why):
        self.assertIsNotNone(got, "%s: %s: a git was found (the real one, last on PATH)" % (label, why))
        self.assertEqual(_local_spelling(got), _local_spelling(self.git_exe),
                         "%s: %s: the entry lies inside the root once C8 is applied, so it is skipped and the real git is "
                         "returned, not %r" % (label, why, got))

    def _assert_returns_planted(self, label, got, planted, why):
        self.assertIsNotNone(got, "%s: control: %s: a git was found" % (label, why))
        self.assertEqual(_local_spelling(got), _local_spelling(planted),
                         "%s: control: %s: the spelling under test reaches the planted program when no root contains it. "
                         "Got %r" % (label, why, got))

    def _fake_realpath(self, spelled_link, answer):
        """A realpath that answers ``answer`` for ``spelled_link`` and calls the real function for every other input."""
        real = os.path.realpath
        calls = []
        wanted = os.path.normcase(os.path.abspath(str(spelled_link)))

        def fake(path, *args, **kwargs):
            text = os.fspath(path)
            calls.append(text)
            if os.path.normcase(os.path.abspath(text)) == wanted:
                return answer
            return real(path, *args, **kwargs)
        return fake, calls

    def _symlink_or_skip(self, target, link):
        try:
            os.symlink(str(target), str(link), target_is_directory=True)
        except (OSError, NotImplementedError, AttributeError) as exc:
            self.skipTest("no symbolic-link privilege (%s: %s)" % (type(exc).__name__, exc))
        self.addCleanup(lambda: os.rmdir(str(link)) if os.path.lexists(str(link)) else None)  # the link only, never its target

    # -- G5: step 3 of comparable_path ------------------------------------------------------------------
    def _g5_1(self, label):
        module = dict(both_copies())[label]
        resolved_root = os.path.realpath(str(self.excluded))
        _, letter, tail = _drive_and_tail(resolved_root)
        link = self.owned / "L"
        self._plant_recorder(link)
        answer = "\\\\localhost\\%s$\\%s\\x" % (letter, tail)
        fake, calls = self._fake_realpath(link, answer)
        with mock.patch("os.path.realpath", fake):
            comparable = self.need(module, label, "comparable_path")(str(link))
            got = self.need(module, label, "resolve_git")(self._path_value(link), [resolved_root])
        self.assertTrue(any(os.path.normcase(os.path.abspath(c)) == os.path.normcase(str(link)) for c in calls),
                        "%s: R9-G5-1: control: the patched realpath was called with %s (it is not bypassed)" % (label, link))
        self.assertEqual(comparable, os.path.normcase(resolved_root + "\\x"),
                         "%s: R9-G5-1: realpath answered %s for %s; step 3 of comparable_path strips the prefix, so the "
                         "root's x folder through the admin share has the root's drive spelling" % (label, answer, link))
        self._assert_returns_real_git(label, got, "R9-G5-1: the link resolves to the root's x folder through the admin share")

    def _g5_1c(self, label):
        module = dict(both_copies())[label]
        resolved_root = os.path.realpath(str(self.excluded))
        _, letter, tail = _drive_and_tail(os.path.realpath(str(self.owned)))
        link = self.owned / "L"
        planted = self._plant_recorder(link)
        fake, calls = self._fake_realpath(link, "\\\\localhost\\%s$\\%s\\y" % (letter, tail))
        with mock.patch("os.path.realpath", fake):
            got = self.need(module, label, "resolve_git")(self._path_value(link), [resolved_root])
        self._assert_returns_planted(label, got, planted, "R9-G5-1C: the link resolves outside every root through the share")

    def _g5_2(self, label):
        module = dict(both_copies())[label]
        _, letter, tail = _drive_and_tail(os.path.realpath(str(self.excluded)))
        self._plant_recorder(self.excluded / "x")
        link = self.owned / "L"
        self._symlink_or_skip("\\\\localhost\\%s$\\%s\\x" % (letter, tail), link)
        if not os.path.isfile(os.path.join(str(link), shim_name())):
            self.skipTest("admin share not reachable through a link")
        got = self.need(module, label, "resolve_git")(self._path_value(link), [str(self.excluded)])
        self._assert_returns_real_git(label, got, "R9-G5-2: a symbolic link to the root's x folder through the admin share")

    def _g5_2c(self, label):
        module = dict(both_copies())[label]
        _, letter, tail = _drive_and_tail(os.path.realpath(str(self.owned)))
        planted = self._plant_recorder(self.owned / "y")
        link = self.owned / "L2"
        self._symlink_or_skip("\\\\localhost\\%s$\\%s\\y" % (letter, tail), link)
        if not os.path.isfile(os.path.join(str(link), shim_name())):
            self.skipTest("admin share not reachable through a link")
        got = self.need(module, label, "resolve_git")(self._path_value(link), [str(self.excluded)])
        self._assert_returns_planted(label, got, planted, "R9-G5-2C: a symbolic link to a folder outside every root through the share")

    # -- G6: the written spelling ---------------------------------------------------------------------
    def _g6_fixture(self):
        out = self.owned / "out"
        planted = self._plant_recorder(out)
        _junction_or_fail(self, out, self.excluded / "nm")
        return planted

    def _g6_1(self, label):
        module = dict(both_copies())[label]
        self._g6_fixture()
        drive, _, tail = _drive_and_tail(self.excluded)
        entry = "\\\\?\\%s\\%s\\nm" % (drive, tail)
        got = self.need(module, label, "resolve_git")(self._path_value(entry), [str(self.excluded)])
        self._assert_returns_real_git(label, got, "R9-G6-1: the junction %s\\nm leads out, but the entry is WRITTEN inside the root "
                                                   "with a long prefix, so only the written spelling skips it" % self.excluded)

    def _g6_1c(self, label):
        module = dict(both_copies())[label]
        planted = self._g6_fixture()
        drive, _, tail = _drive_and_tail(self.owned)
        entry = "\\\\?\\%s\\%s\\out" % (drive, tail)
        got = self.need(module, label, "resolve_git")(self._path_value(entry), [str(self.excluded)])
        self._assert_returns_planted(label, got, planted, "R9-G6-1C: the long-prefix entry names the folder outside every root")

    def _g6_2(self, label):
        module = dict(both_copies())[label]
        self._g6_fixture()
        _, letter, tail = _drive_and_tail(self.excluded)
        entry = "\\\\localhost\\%s$\\%s\\nm" % (letter, tail)
        if not os.path.isfile(os.path.join(entry, shim_name())):
            self.skipTest("admin share not reachable")
        got = self.need(module, label, "resolve_git")(self._path_value(entry), [str(self.excluded)])
        self._assert_returns_real_git(label, got, "R9-G6-2: the junction reached through the admin share, written inside the root")

    def _g6_2c(self, label):
        module = dict(both_copies())[label]
        planted = self._g6_fixture()
        _, letter, tail = _drive_and_tail(self.owned)
        entry = "\\\\localhost\\%s$\\%s\\out" % (letter, tail)
        if not os.path.isfile(os.path.join(entry, shim_name())):
            self.skipTest("admin share not reachable")
        got = self.need(module, label, "resolve_git")(self._path_value(entry), [str(self.excluded)])
        self._assert_returns_planted(label, got, planted, "R9-G6-2C: the share entry names the folder outside every root")

    def test_R9_G5_1_a_link_resolving_to_the_root_through_a_share_is_skipped_h(self):
        self._g5_1("_protected_names")

    def test_R9_G5_1_a_link_resolving_to_the_root_through_a_share_is_skipped_l(self):
        self._g5_1("land_contract")

    def test_R9_G5_1_control_a_link_resolving_outside_every_root_through_a_share_is_returned_h(self):
        self._g5_1c("_protected_names")

    def test_R9_G5_1_control_a_link_resolving_outside_every_root_through_a_share_is_returned_l(self):
        self._g5_1c("land_contract")

    def test_R9_G5_2_a_symbolic_link_to_the_root_through_the_admin_share_is_skipped_h(self):
        self._g5_2("_protected_names")

    def test_R9_G5_2_a_symbolic_link_to_the_root_through_the_admin_share_is_skipped_l(self):
        self._g5_2("land_contract")

    def test_R9_G5_2_control_a_symbolic_link_outside_every_root_through_the_admin_share_is_returned_h(self):
        self._g5_2c("_protected_names")

    def test_R9_G5_2_control_a_symbolic_link_outside_every_root_through_the_admin_share_is_returned_l(self):
        self._g5_2c("land_contract")

    def test_R9_G6_1_a_long_prefix_entry_written_inside_the_root_over_a_junction_is_skipped_h(self):
        self._g6_1("_protected_names")

    def test_R9_G6_1_a_long_prefix_entry_written_inside_the_root_over_a_junction_is_skipped_l(self):
        self._g6_1("land_contract")

    def test_R9_G6_1_control_a_long_prefix_entry_outside_every_root_is_returned_h(self):
        self._g6_1c("_protected_names")

    def test_R9_G6_1_control_a_long_prefix_entry_outside_every_root_is_returned_l(self):
        self._g6_1c("land_contract")

    def test_R9_G6_2_a_share_entry_written_inside_the_root_over_a_junction_is_skipped_h(self):
        self._g6_2("_protected_names")

    def test_R9_G6_2_a_share_entry_written_inside_the_root_over_a_junction_is_skipped_l(self):
        self._g6_2("land_contract")

    def test_R9_G6_2_control_a_share_entry_outside_every_root_is_returned_h(self):
        self._g6_2c("_protected_names")

    def test_R9_G6_2_control_a_share_entry_outside_every_root_is_returned_l(self):
        self._g6_2c("land_contract")


# -----------------------------------------------------------------------------------------------------
# Guard rows F3-1 and F3-2: the disk-mode directory listing (they PASS at M; the mutation MB3g-h turns them red)
# -----------------------------------------------------------------------------------------------------
class DiskDirectoryListingGuardTests(RemedyCase):

    def setUp(self):
        super().setUp()
        if os.name != "nt":
            self.skipTest("both rows build their second spelling with Windows folder semantics")

    def test_R6_F3_1_a_case_variant_second_file_in_a_case_sensitive_folder_is_working_malformed(self):
        cs = self.root / "case-sensitive"
        cs.mkdir()
        proc = subprocess.run(["fsutil", "file", "setCaseSensitiveInfo", str(cs), "enable"], capture_output=True, text=True)
        if proc.returncode != 0:
            self.skipTest("fsutil file setCaseSensitiveInfo failed here (exit %d: %s%s)" % (
                proc.returncode, proc.stdout.strip()[:160], proc.stderr.strip()[:160]))
        work = make_world(cs, {RULES_REL: rules_bytes(NAMES)})
        hooks = work / ".claude" / "hooks"
        self.expect(work, "kept", why="control: before the second file the disk holds the one exact file")
        (hooks / "DB-destructive-guard.rules.json").write_bytes(rules_bytes(NAMES[:1]))
        listing = [n for n in os.listdir(str(hooks)) if n.lower() == RULES_NAME]
        if len(listing) < 2:
            self.skipTest("the folder did not stay case-sensitive for the new .claude\\hooks (listing %r)" % listing)
        rc, obj, out, err = self.run_checker(work)
        self.assertEqual((rc, (obj or {}).get("verdict")), (11, "working-malformed"),
                         "R6-F3-1: both %s and DB-%s on disk (a directory listing sees both; the index does not hold the "
                         "variant). Result %r stderr=%r" % (RULES_NAME, RULES_NAME[3:], obj, err[:200]))

    def test_R6_F3_2_a_literal_dot_claude_dot_folder_made_with_the_long_prefix_is_working_malformed(self):
        work = make_world(self.root, {RULES_REL: rules_bytes(NAMES)})
        self.expect(work, "kept", why="control: before the second folder the disk holds the one exact file")
        extended = "\\\\?\\" + str(work / ".claude.")
        self.addCleanup(lambda: self.assertFalse(os.path.exists(extended), "the .claude. folder was removed"))
        self.addCleanup(lambda: _rm_tree(extended) if os.path.exists(extended) else None)
        os.makedirs(extended + "\\hooks")
        with open(extended + "\\hooks\\" + RULES_NAME, "wb") as handle:
            handle.write(rules_bytes(NAMES[:1]))
        self.assertTrue(os.path.exists(extended + "\\hooks\\" + RULES_NAME), "control: the folder with the trailing dot exists")
        rc, obj, out, err = self.run_checker(work)
        self.assertEqual((rc, (obj or {}).get("verdict")), (11, "working-malformed"),
                         "R6-F3-2: a folder literally named '.claude.' beside '.claude' holding a narrowed rules file is an "
                         "alias that Windows folds onto the exact path. Result %r stderr=%r" % (obj, err[:200]))


# =====================================================================================================
# REVISION 7 REMEDY (block 22, RED). Gate 20's blocked report (t20), findings N3 and N4 (fixed: invariants C12
# and C11), and one documenting row per STATED RESIDUAL of Revision 6, "Threat model for path spellings",
# "Trust boundary" (N1, N2, I1, the working-folder residual, N5). Contract
# 2026-10-13-database-guard-names-in-rules-file, Revision 7.
#
# NAMES THIS SUITE PINS (Revision 7, "Names and shapes for block 22's tests"), each in BOTH
# .claude/hooks/_protected_names.py and .claude/scripts/land_contract.py:
#   is_device_path(path) -> bool   new. True for a path that is a device path after C8 step 1 (``\\.\Volume{GUID}\``,
#       ``\\?\Volume{GUID}\``, ``\\.\GLOBALROOT\Device\...``, ``\\.\pipe\``), whichever separator is used in its first
#       four characters; False for a drive form (``\\?\C:\``), a long UNC form (``\\?\UNC\``, any letter case) and
#       a plain path. A row that needs it asks for it through ``need``, so its absence is an ASSERTION failure.
#   comparable_path / written_path of a device path return os.path.normcase of the text (no realpath, no abspath).
#   resolve_git skips a device-path PATH entry, and returns None when an excluded root is a device path.
#   A malformed reading for C11 carries a JSON ``reason`` containing ``backslash-in-path``.
#
# SAFETY. As block 18. Every fixture, recorder and compiled file lives in a test-owned folder that the case removes
# whether the row passes or fails. The only calls into the volume manager are the two READING calls
# GetVolumeNameForVolumeMountPointW and QueryDosDeviceW; nothing here runs net use, subst, fsutil 8dot3name or
# mountvol, and no mount is changed. A row that changes the working folder restores it before the case's root goes.
# =====================================================================================================
BACKSLASH_RULES = ".claude\\hooks\\db-destructive-guard.rules.json"
FAKE_GUID = "{11111111-2222-3333-4444-555555555555}"
TRUST_BOUNDARY = "Revision 6, Threat model for path spellings, Trust boundary"


def volume_identity(path):
    """(volume name, device name) of the drive that holds ``path``: ``\\\\?\\Volume{GUID}\\`` from
    GetVolumeNameForVolumeMountPointW and ``\\Device\\HarddiskVolumeN`` from QueryDosDeviceW. Both only READ.
    Raises RuntimeError naming the failing call and its error."""
    if os.name != "nt":
        raise RuntimeError("volume names exist only on Windows")
    import ctypes
    drive = os.path.splitdrive(os.path.abspath(str(path)))[0]
    if len(drive) != 2 or drive[1] != ":":
        raise RuntimeError("%r has no drive letter" % str(path))
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    volume = ctypes.create_unicode_buffer(260)
    if not kernel.GetVolumeNameForVolumeMountPointW(drive + "\\", volume, 260):
        raise RuntimeError("GetVolumeNameForVolumeMountPointW(%s\\) failed with error %d" % (drive, ctypes.get_last_error()))
    device = ctypes.create_unicode_buffer(260)
    if not kernel.QueryDosDeviceW(drive, device, 260):
        raise RuntimeError("QueryDosDeviceW(%s) failed with error %d" % (drive, ctypes.get_last_error()))
    return volume.value, device.value


def device_forms(folder):
    """The four device spellings of ``folder`` that Windows itself resolves (read from this drive's own GUID and
    device number): ``\\\\.\\Volume{GUID}\\<tail>``, ``\\\\?\\Volume{GUID}\\<tail>``, and the two GLOBALROOT forms."""
    volume, device = volume_identity(folder)
    tail = os.path.splitdrive(os.path.abspath(str(folder)))[1].lstrip("\\")
    return {"dot-volume": "\\\\.\\" + volume[4:] + tail,
            "question-volume": volume + tail,
            "dot-globalroot": "\\\\.\\GLOBALROOT" + device + "\\" + tail,
            "question-globalroot": "\\\\?\\GLOBALROOT" + device + "\\" + tail}


class Revision7Case(SecondRemedyCase):

    def need(self, module, label, name):
        fn = getattr(module, name, None)
        if fn is None:
            self.fail("%s.%s does not exist yet: Revision 7 (Names and shapes for block 22's tests) adds it, so this row "
                      "cannot say anything until block 23" % (label, name))
        return fn

    def chdir_to(self, name):
        """Make the working folder a test-owned folder (outside every fixture tree); restored before the root goes."""
        folder = self.root / name
        folder.mkdir(parents=True, exist_ok=True)
        saved = os.getcwd()
        os.chdir(str(folder))
        self.addCleanup(os.chdir, saved)
        return folder

    def real_git_dir(self):
        return os.path.dirname(real_git_exe())

    def roots_of(self, module, label, project):
        """The fixture's excluded roots as the landing computes them: the project and ``linked_worktrees(project)``."""
        fn = self.need(module, label, "linked_worktrees")
        return [str(project)] + list(fn(str(project)))


# -----------------------------------------------------------------------------------------------------
# R7-N4-1 (C11, finding N4): a backslash anywhere in a listing makes that side malformed
# -----------------------------------------------------------------------------------------------------
class BackslashListingTests(RemedyCase):

    def setUp(self):
        super().setUp()
        self.repo = make_world(self.root, {RULES_REL: rules_bytes(NAMES)})
        self.kept = rules_bytes(NAMES)
        self.narrowed = rules_bytes(NAMES[:1])

    def tree_with(self, extra, with_exact=True):
        files = {RULES_REL: self.kept} if with_exact else {"README.txt": b"x\n"}
        files.update(extra)
        return plumbing_commit(self.repo, files)

    def listed(self, commit):
        return git_in(self.repo, "ls-tree", "-r", "-z", "--full-tree", commit).split("\0")

    def malformed(self, obj, why):
        self.assertIn("backslash-in-path", str(obj.get("reason")),
                      "%s: the malformed reason names backslash-in-path (Revision 7, C11). Result %r" % (why, obj))

    def test_R7_N4_1_i_a_root_entry_with_backslash_separators_beside_the_kept_file_is_working_malformed(self):
        """Gate 20 N4: a checkout with core.protectNTFS=false writes the root entry named
        ``.claude\\hooks\\db-destructive-guard.rules.json`` over the guard's file, while the exact kept file beside it
        made the check read ``kept``."""
        working = self.tree_with({BACKSLASH_RULES: self.narrowed})
        good = self.tree_with({})
        self.assertIn(BACKSLASH_RULES, [e.partition("\t")[2] for e in self.listed(working)],
                      "control: the working tree lists the backslash-named root entry beside the exact file")
        obj = self.expect(self.repo, "working-malformed", "--working-ref", working, "--default-ref", good,
                          why="R7-N4-1 (i) working side: any path holding a backslash makes the side malformed")
        self.malformed(obj, "R7-N4-1 (i) working side")

    def test_R7_N4_1_i_the_same_root_entry_on_the_default_side_is_reference_malformed(self):
        default = self.tree_with({BACKSLASH_RULES: self.narrowed})
        good = self.tree_with({})
        obj = self.expect(self.repo, "reference-malformed", "--working-ref", good, "--default-ref", default,
                          why="R7-N4-1 (i) default side: the same entry on the default branch")
        self.malformed(obj, "R7-N4-1 (i) default side")

    def test_R7_N4_1_ii_an_unrelated_backslash_path_beside_the_kept_file_is_malformed_on_each_side(self):
        """Pins the whole-listing rule (C11): the path is ``docs\\a.md``, nothing like the rules path."""
        stray = {"docs\\a.md": b"x\n"}
        with_stray, good = self.tree_with(stray), self.tree_with({})
        obj = self.expect(self.repo, "working-malformed", "--working-ref", with_stray, "--default-ref", good,
                          why="R7-N4-1 (ii) working side: an unrelated backslash path")
        self.malformed(obj, "R7-N4-1 (ii) working side")
        obj = self.expect(self.repo, "reference-malformed", "--working-ref", good, "--default-ref", with_stray,
                          why="R7-N4-1 (ii) default side: an unrelated backslash path")
        self.malformed(obj, "R7-N4-1 (ii) default side")

    def test_R7_N4_1_iii_disk_mode_an_index_entry_holding_a_backslash_is_working_malformed(self):
        for label, name in (("the rules path spelled with backslashes", BACKSLASH_RULES), ("an unrelated path", "docs\\a.md")):
            with self.subTest(index_entry=label):
                world_root = self.root / ("idx-" + label.split()[1])
                world_root.mkdir()
                work = make_world(world_root, {RULES_REL: self.kept})
                blob = hash_blob(work, self.narrowed)
                proc = subprocess.run(["git", "-c", "core.protectNTFS=false", "update-index", "--add", "--cacheinfo",
                                       "100644,%s,%s" % (blob, name)], cwd=str(work), capture_output=True, text=True, env=_GIT_ENV)
                if proc.returncode != 0:
                    self.skipTest("git refused to put %r in the index (exit %d): %s; R7-N4-1 (i) and (ii) still guard the "
                                  "rule" % (name, proc.returncode, proc.stderr.strip()[:200]))
                listed = git(work, "ls-files", "-z", "--full-name").split("\0")
                self.assertIn(name, listed, "control: the index holds the backslash entry beside the exact path")
                self.assertIn(RULES_REL, listed, "control: and the exact path")
                rc, obj, out, err = self.run_checker(work)
                self.assertEqual((rc, (obj or {}).get("verdict")), (11, "working-malformed"),
                                 "R7-N4-1 (iii) disk mode, %s in the index. Result %r stderr=%r" % (label, obj, err[:200]))
                self.malformed(obj or {}, "R7-N4-1 (iii) disk mode, " + label)

    def test_R7_N4_1_iv_control_the_same_trees_without_the_backslash_entry_are_kept(self):
        """PASSES today: without this a row above could pass because the fixture trees are broken."""
        good = self.tree_with({})
        self.expect(self.repo, "kept", "--working-ref", good, "--default-ref", good, why="control: working-ref mode, no backslash entry")
        self.expect(self.repo, "kept", why="control: disk mode, no backslash entry")
        beside = self.tree_with({"docs/a.md": b"x\n"})
        self.expect(self.repo, "kept", "--working-ref", beside, "--default-ref", good,
                    why="control: an unrelated path with a forward slash is no backslash path")

    def test_R7_N4_1_v_a_default_side_with_no_rules_file_and_an_unrelated_backslash_path_is_reference_malformed_never_first_install(self):
        """Verdict step (2): such a listing is never ``first-install``, which would let any working list pass."""
        default = self.tree_with({"docs\\a.md": b"x\n"}, with_exact=False)
        self.assertNotIn(RULES_REL, [e.partition("\t")[2] for e in self.listed(default)],
                         "control: the default tree holds no rules file")
        good = self.tree_with({})
        obj = self.expect(self.repo, "reference-malformed", "--working-ref", good, "--default-ref", default,
                          why="R7-N4-1 (v): no rules file and a backslash path on the default side is reference-malformed, "
                              "never first-install")
        self.malformed(obj, "R7-N4-1 (v)")


# -----------------------------------------------------------------------------------------------------
# R7-N3-1 (C12, finding N3): the string halves, in both copies, never skipped
# -----------------------------------------------------------------------------------------------------
DEVICE_SPELLINGS = ("\\\\.\\Volume" + FAKE_GUID + "\\x", "\\\\?\\Volume" + FAKE_GUID + "\\x",
                    "\\\\.\\GLOBALROOT\\Device\\HarddiskVolume1\\x", "\\\\?\\GLOBALROOT\\Device\\HarddiskVolume1\\x",
                    "//./Volume" + FAKE_GUID + "/x", "\\\\.\\pipe\\x")
NOT_DEVICE_SPELLINGS = ("\\\\?\\C:\\x", "\\\\.\\C:\\x", "//?/C:/x", "\\\\?\\UNC\\localhost\\C$\\x",
                        "\\\\.\\UNC\\localhost\\C$\\x", "\\\\?\\unc\\localhost\\C$\\x", "C:\\x")
DRIVE_FORMS = ("\\\\?\\C:\\x", "\\\\.\\C:\\x", "//?/C:/x")


class DevicePathStringTests(Revision7Case):

    def test_R7_N3_1_is_device_path_is_true_for_every_device_spelling(self):
        for label, module in both_copies():
            with self.subTest(copy=label):
                fn = self.need(module, label, "is_device_path")
                for text in DEVICE_SPELLINGS:
                    self.assertIs(fn(text), True, "%s: is_device_path(%r) is True: a device-namespace spelling that is not a "
                                                  "drive form or a UNC form (Revision 7, C12)" % (label, text))

    def test_R7_N3_1_is_device_path_is_false_for_a_drive_form_a_unc_form_and_a_plain_path(self):
        for label, module in both_copies():
            with self.subTest(copy=label):
                fn = self.need(module, label, "is_device_path")
                for text in NOT_DEVICE_SPELLINGS:
                    self.assertIs(fn(text), False, "%s: is_device_path(%r) is False (a drive form, a long UNC form with the letter "
                                                   "case of UNC ignored, or a plain path)" % (label, text))

    def test_R7_N3_1_comparable_and_written_path_of_a_device_path_keep_the_prefix_and_never_start_with_the_working_folder(self):
        here = self.chdir_to("working-folder-outside-every-tree")
        folder = os.path.normcase(str(here))
        for label, module in both_copies():
            with self.subTest(copy=label):
                comparable = self.need(module, label, "comparable_path")
                written = self.need(module, label, "written_path")
                for text in DEVICE_SPELLINGS:
                    for name, fn in (("comparable_path", comparable), ("written_path", written)):
                        got = fn(text)
                        self.assertFalse(got.startswith(folder),
                                         "%s: %s(%r) = %r must never begin with the working folder %r: a device path is never "
                                         "given to realpath or abspath and never joined to the working folder (N3)"
                                         % (label, name, text, got, folder))
                        self.assertEqual(got, os.path.normcase(text),
                                         "%s: %s(%r) keeps the device prefix: os.path.normcase of the text" % (label, name, text))

    def test_R7_N3_1_each_drive_form_has_the_comparable_path_of_the_plain_drive_path(self):
        """PASSES today: the drive forms were already stripped and are not touched by C12."""
        if os.name != "nt":
            self.skipTest("a drive letter and the \\\\?\\ prefix are Windows spellings")
        self.chdir_to("working-folder-outside-every-tree")
        for label, module in both_copies():
            with self.subTest(copy=label):
                comparable = self.need(module, label, "comparable_path")
                for text in DRIVE_FORMS:
                    self.assertEqual(comparable(text), comparable("C:\\x"),
                                     "%s: comparable_path(%r) equals comparable_path('C:\\\\x'): C12 still strips a prefix that "
                                     "is followed by a drive letter and a colon" % (label, text))

    def test_R7_N3_1_a_device_path_as_an_excluded_root_makes_resolve_git_return_none(self):
        """A device root cannot be compared with any entry, so the program search is unverifiable (a landing halt)."""
        self.chdir_to("working-folder-outside-every-tree")
        path_value = self.real_git_dir()
        for label, module in both_copies():
            with self.subTest(copy=label):
                resolve = self.need(module, label, "resolve_git")
                self.assertTrue(resolve(path_value, [str(self.root)]),
                                "%s: control: with an ordinary root and PATH holding only the real git's folder, git is found" % label)
                for root in DEVICE_SPELLINGS[:4]:
                    self.assertIsNone(resolve(path_value, [root]),
                                      "%s: an excluded root %r is a device path, so resolve_git returns None (unverifiable) "
                                      "instead of a git that was never compared with it (Revision 7, C12)" % (label, root))


# -----------------------------------------------------------------------------------------------------
# R7-N3-2 (C12): end to end, a tree folder spelled as a device path is never the program search's git
# -----------------------------------------------------------------------------------------------------
class DevicePathEndToEndTests(Revision7Case):

    def setUp(self):
        super().setUp()
        if os.name != "nt":
            self.skipTest("device paths (\\\\.\\Volume{GUID}\\, \\\\.\\GLOBALROOT\\) exist only on Windows; "
                          "R7-N3-1 still guards the rule")
        self.work, self.wt1, self.wt2 = self.linked_world()
        self.git_exe = real_git_exe()
        self.chdir_to("working-folder-outside-every-tree")

    def forms_of(self, folder):
        try:
            return device_forms(folder)
        except RuntimeError as exc:
            self.skipTest("the volume of the fixture cannot be read (%s); R7-N3-1 still guards the rule" % exc)

    def test_R7_N3_2_a_recorder_in_the_linked_worktree_reached_through_a_device_path_is_never_the_git_returned(self):
        planted = self.wt1 / "tools-planted"
        self.plant(planted)
        for form, spelled in self.forms_of(planted).items():
            self.assertTrue(os.path.isfile(os.path.join(spelled, shim_name())),
                            "control: the recorder in the tree is reachable through %s: %r" % (form, spelled))
            path_value = os.pathsep.join([spelled, self.real_git_dir()])
            for label, module in both_copies():
                with self.subTest(copy=label):
                    resolve = self.need(module, label, "resolve_git")
                    got = resolve(path_value, self.roots_of(module, label, self.wt1))
                    self.assertTrue(got, "%s: %s: a git was found (the real one, second on PATH)" % (label, form))
                    self.assertEqual(_norm(got), _norm(self.git_exe),
                                     "%s: %s: a folder of the tree spelled as a device path must be skipped and the real git returned, "
                                     "not %r (N3: the prefix was stripped and the rest joined to the working folder, so the entry "
                                     "looked like an unrelated relative folder)" % (label, form, got))

    def test_R7_N3_2_control_the_same_recorder_outside_every_tree_listed_by_its_plain_spelling_is_returned(self):
        """PASSES today: a row above cannot pass because the recorder is invisible to the program search."""
        for form in ("dot-volume", "question-volume", "dot-globalroot", "question-globalroot"):
            outside = self.root / ("outside-bin-" + form)
            recorder = self.plant(outside)
            spelled = self.forms_of(outside)[form]
            self.assertTrue(os.path.isfile(os.path.join(spelled, shim_name())),
                            "control: the recorder is reachable through %s: %r" % (form, spelled))
            path_value = os.pathsep.join([str(outside), self.real_git_dir()])
            for label, module in both_copies():
                with self.subTest(copy=label):
                    resolve = self.need(module, label, "resolve_git")
                    got = resolve(path_value, self.roots_of(module, label, self.wt1))
                    self.assertTrue(got and _norm(got) == _norm(recorder),
                                    "%s: %s: the recorder outside every tree, listed by its plain drive spelling first, IS the git "
                                    "returned (the documented residual). Got %r" % (label, form, got))


# -----------------------------------------------------------------------------------------------------
# The stated residuals of the Trust boundary (Revision 7). Each row PASSES today and pins the limit.
# -----------------------------------------------------------------------------------------------------
class StatedResidualRevision7Tests(Revision7Case):

    def residual_note(self, what):
        return ("R7 residual %s: this row PINS A STATED LIMIT, not a goal (%s). A fix that covers it changes THIS ROW "
                "DELIBERATELY, with the paragraph; an accidental change must fail here." % (what, TRUST_BOUNDARY))

    def folders(self, module, label, project):
        return {_norm(p) for p in self.need(module, label, "linked_worktrees")(str(project))}

    def two_worktrees(self):
        work = self.world(NAMES)
        a, b = self.root / "a", self.root / "b"
        git(work, "worktree", "add", "-q", "-b", "a-branch", str(a))
        git(work, "worktree", "add", "-q", "-b", "b-branch", str(b))
        return work, a, b

    def test_R7_N1_R_a_deleted_or_redirected_gitdir_file_drops_that_worktree_from_the_set(self):
        """N1. ``<common>/worktrees/b/gitdir`` names where linked worktree b lives. Deleted, or rewritten to name a
        file elsewhere, b leaves the set that linked_worktrees(a) returns: a process that can edit git's internal
        files can also edit the rules file, so the boundary lies there. BOUND: the main checkout and worktree a stay
        in the set, so a widening of what is dropped turns this row red too."""
        work, a, b = self.two_worktrees()
        pointer = work / ".git" / "worktrees" / "b" / "gitdir"
        self.assertTrue(pointer.is_file(), "control: git wrote the gitdir pointer of worktree b")
        outside = Path(tempfile.mkdtemp(prefix="pnames-outside-")).resolve()
        self.addCleanup(_rm_tree, outside)
        (outside / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
        for label, module in both_copies():
            self.assertIn(_norm(b), self.folders(module, label, a), "control: %s: before the pointer is changed b is in the set" % label)
        pointer.unlink()
        for step, edit in (("deleted", lambda: None), ("redirected to a file outside the fixture",
                                                       lambda: pointer.write_text(str(outside / ".git"), encoding="utf-8"))):
            edit()
            for label, module in both_copies():
                got = self.folders(module, label, a)
                self.assertNotIn(_norm(b), got, "%s: gitdir %s: %s" % (label, step, self.residual_note("N1")))
                self.assertIn(_norm(work), got, "%s: gitdir %s: BOUND: the main checkout stays in the set" % (label, step))
                self.assertIn(_norm(a), got, "%s: gitdir %s: BOUND: worktree a stays in the set" % (label, step))

    def test_R7_N2_R_a_common_folder_not_named_dot_git_leaves_the_main_checkout_out_of_the_set(self):
        """N2. ``git init --separate-git-dir`` puts the common folder at <owned>/repo.git; the main checkout is found
        only as the parent of a common folder named ``.git``, so linked_worktrees(<linked worktree>) omits it. It
        needs a main-checkout folder on PATH, which C8's person rule already forbids. BOUND: the linked worktree and
        the common folder stay in the set."""
        owned = self.root / "separate"
        owned.mkdir()
        main, common, linked = owned / "main", owned / "repo.git", owned / "linked"
        git(owned, "init", "-q", "-b", "master", "--separate-git-dir", str(common), str(main))
        (main / "README.txt").write_text("fixture\n", encoding="utf-8")
        git(main, "add", "-A")
        git(main, "commit", "-q", "-m", "first")
        git(main, "worktree", "add", "-q", "-b", "linked-branch", str(linked))
        self.assertTrue((main / ".git").is_file(), "control: the main checkout holds a .git FILE (the git folder is elsewhere)")
        for label, module in both_copies():
            got = self.folders(module, label, linked)
            self.assertNotIn(_norm(main), got, "%s: %s" % (label, self.residual_note("N2")))
            self.assertIn(_norm(linked), got, "%s: BOUND: the linked worktree stays in the set" % label)
            self.assertIn(_norm(common), got, "%s: BOUND: the common folder (repo.git) stays in the set" % label)

    def test_R7_I1_R_a_submodules_superproject_is_not_in_the_set(self):
        """I1 (informational, not provided). linked_worktrees(<super>/sub) has no way to name the superproject.
        BOUND: sub and <super>/.git/modules/sub stay in the set."""
        source = self.root / "subsource"
        source.mkdir()
        git(source, "init", "-q", "-b", "master")
        (source / "lib.txt").write_text("library\n", encoding="utf-8")
        git(source, "add", "-A")
        git(source, "commit", "-q", "-m", "library")
        sup = self.root / "super"
        sup.mkdir()
        git(sup, "init", "-q", "-b", "master")
        (sup / "README.txt").write_text("super\n", encoding="utf-8")
        git(sup, "add", "-A")
        git(sup, "commit", "-q", "-m", "super")
        proc = subprocess.run(["git", "-c", "protocol.file.allow=always", "submodule", "add", str(source), "sub"],
                              cwd=str(sup), capture_output=True, text=True, env=_GIT_ENV)
        if proc.returncode != 0:
            self.skipTest("git refused to add the submodule (exit %d): %s" % (proc.returncode, proc.stderr.strip()[:300]))
        sub, modules = sup / "sub", sup / ".git" / "modules" / "sub"
        self.assertTrue((sub / ".git").is_file() and modules.is_dir(), "control: a submodule checkout with its git folder under the superproject")
        for label, module in both_copies():
            got = self.folders(module, label, sub)
            self.assertNotIn(_norm(sup), got, "%s: %s" % (label, self.residual_note("I1")))
            self.assertIn(_norm(sub), got, "%s: BOUND: the submodule stays in the set" % label)
            self.assertIn(_norm(modules), got, "%s: BOUND: its git folder .git/modules/sub stays in the set" % label)

    def test_R7_C7_R_a_folder_under_the_working_folder_is_not_excluded_but_the_working_folder_itself_is(self):
        """The working-folder residual (C7, Revision 7). The working folder is skipped by EQUALITY only. With the
        working folder F a test-owned folder that is not a tree, a recorder at F\\tools\\git.exe IS returned; one in F
        itself, listed first, is skipped. BOUND: a recorder in a fixture tree folder, listed after a folder of F that
        holds no git, is still skipped, so a widening to 'F is a root' or a loosening of the tree rule turns this red."""
        work, wt1, wt2 = self.linked_world()
        folder = self.chdir_to("F")
        recorder = self.plant(folder / "tools")
        self.plant(folder)
        self.plant(work / "tools-planted")
        (folder / "bare").mkdir()
        real = self.real_git_dir()
        for label, module in both_copies():
            resolve = self.need(module, label, "resolve_git")
            roots = self.roots_of(module, label, wt1)
            got = resolve(os.pathsep.join([str(folder / "tools"), real]), roots)
            self.assertTrue(got and _norm(got) == _norm(recorder),
                            "%s: a recorder in a folder UNDER the working folder is returned: %s Got %r"
                            % (label, self.residual_note("working-folder"), got))
            got = resolve(os.pathsep.join([str(folder), real]), roots)
            self.assertEqual(_norm(got), _norm(self.git_exe_of(real)),
                             "%s: a recorder in the working folder itself, listed first, is skipped by equality" % label)
            got = resolve(os.pathsep.join([str(folder / "bare"), str(work / "tools-planted"), real]), roots)
            self.assertEqual(_norm(got), _norm(self.git_exe_of(real)),
                             "%s: BOUND: a recorder in a fixture tree folder (the main checkout), listed after a folder of F "
                             "that holds no git, is still skipped" % label)

    def git_exe_of(self, folder):
        return os.path.join(folder, shim_name())

    def test_R7_N5_R_a_compiled_helper_planted_in_the_installed_folder_decides_the_verdict_under_dash_I_dash_B(self):
        """N5. ``-B`` stops Python WRITING bytecode, not reading it: an UNCHECKED_HASH .pyc planted at
        <installed>/.claude/hooks/__pycache__/ is imported instead of the helper's source. That needs a process that
        can write into the plugin's installed folder, which can edit the checker itself. BOUND: the same two files in
        a fresh private folder with no __pycache__ (as the landing gate writes mark_m's copy) report names-removed and
        run no stub, so the residual stays confined to the installed folder."""
        import py_compile
        marker = self.root / "stub-ran.txt"
        stub = self.root / "stub-source" / "_protected_names.py"
        stub.parent.mkdir()
        stub.write_text("open(%r, 'a').write('stub\\n')\nEXIT_CODES = {'kept': 0}\n\n\ndef check(project, working_ref=None, "
                        "default_ref=None, fetch=False):\n    return {'verdict': 'kept', 'missing': [], 'working_ref': '', "
                        "'default_ref': '', 'fetched': None, 'reason': ''}\n" % str(marker), encoding="utf-8")
        work = self.world(NAMES, NAMES[:1])

        def layout(name):
            base = self.root / name
            (base / ".claude" / "scripts").mkdir(parents=True)
            (base / ".claude" / "hooks").mkdir(parents=True)
            shutil.copy2(str(CHECK), str(base / ".claude" / "scripts" / CHECK.name))
            shutil.copy2(str(HELPER), str(base / ".claude" / "hooks" / HELPER.name))
            return base

        def run(base):
            return subprocess.run([sys.executable, "-I", "-B", str(base / ".claude" / "scripts" / CHECK.name), "--project", str(work)],
                                  capture_output=True, text=True, env=dict(_GIT_ENV), cwd=str(self.root), timeout=120)

        installed = layout("installed")
        pyc = installed / ".claude" / "hooks" / "__pycache__" / ("_protected_names.%s.pyc" % sys.implementation.cache_tag)
        pyc.parent.mkdir()
        py_compile.compile(str(stub), cfile=str(pyc), doraise=True, invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
        proc = run(installed)
        self.assertTrue(marker.exists() and proc.returncode == 0,
                        "the planted .pyc in the installed folder is imported although the helper's source drops no stub: the "
                        "stub ran and printed kept on a fixture that drops a name (exit %s, stdout=%r, stderr=%r). %s"
                        % (proc.returncode, proc.stdout[:200], proc.stderr[-200:], self.residual_note("N5")))
        marker.unlink()
        fresh = layout("fresh-private-folder")
        self.assertFalse((fresh / ".claude" / "hooks" / "__pycache__").exists(), "control: the fresh folder has no __pycache__")
        proc = run(fresh)
        self.assertEqual((proc.returncode, marker.exists()), (10, False),
                         "BOUND: the same two files with no __pycache__ give names-removed (exit 10) and run no stub: the "
                         "residual is confined to the installed folder. stdout=%r stderr=%r" % (proc.stdout[:200], proc.stderr[-200:]))


if __name__ == "__main__":
    unittest.main(verbosity=1)
