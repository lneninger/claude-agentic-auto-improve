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
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

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
    does); ``fetch-silent`` (``git fetch`` succeeds and writes nothing). Skips the test where no
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
        self.install_shim()
        work = self.world(NAMES, NAMES[:1])
        execdir = self.root / "exec-path"
        execdir.mkdir()
        logs = {}
        for name in ("git-ls-tree", "git-cat-file"):
            logs[name] = self.root / (name + ".log")
            (execdir / name).write_text("#!/bin/sh\necho ran >> \"%s\"\nexit 1\n" % str(logs[name]).replace("\\", "/"),
                                        encoding="utf-8", newline="\n")
        ssh_prog, ssh_log = self._recorder("ssh-recorder")
        trace2, trace = self.root / "trace2.json", self.root / "trace.txt"
        env = self.shim_env({"GIT_EXEC_PATH": str(execdir), "GIT_TRACE2_EVENT": str(trace2), "GIT_TRACE": str(trace),
                             "GIT_SSH_COMMAND": ssh_prog, "GIT_ZZ_CANARY": "1", "PYTHONSTARTUP": str(self.root / "startup.py")})
        self.expect(work, "names-removed", env=env, why="the fixture's verdict")
        for name, log in list(logs.items()) + [("ssh", ssh_log)]:
            self.assertFalse(log.exists(), "the recording %s program never ran" % name)
        self.assertFalse(trace2.exists(), "GIT_TRACE2_EVENT is not passed on: no trace file was written")
        self.assertFalse(trace.exists(), "GIT_TRACE is not passed on: no trace file was written")
        self.assert_isolated(read_shim_log(self.shim_log), "R5-B2-8 variables C2 never names")

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
    def _each_alias(self, shapes, side):
        for label, alias in shapes.items():
            with self.subTest(alias=label, side=side):
                if side == "working":
                    working = self.good({alias: rules_bytes(NAMES[:1])})
                    self.verdict_of(working, self.good(), "working-malformed", "working side: " + label)
                else:
                    default = self.good({alias: rules_bytes(NAMES)})
                    self.verdict_of(self.good(), default, "reference-malformed", "default side: " + label)

    def test_R5_B3_2_every_alias_of_the_rules_path_is_working_malformed(self):
        self._each_alias(ALIAS_SHAPES, "working")

    def test_R5_B3_3_the_same_aliases_on_the_default_side_are_reference_malformed(self):
        self._each_alias(ALIAS_SHAPES, "default")

    def test_R5_B3_5_non_ascii_folding_of_the_file_and_the_folder_is_malformed_on_both_sides(self):
        shapes = {k: v for k, v in UNICODE_SHAPES.items() if k.startswith(("U+0131", "U+017F"))}
        self._each_alias(shapes, "working")
        self._each_alias(shapes, "default")

    def test_R5_B3_6_the_lowercase_half_and_the_explicit_family_are_malformed_on_both_sides(self):
        shapes = {k: v for k, v in UNICODE_SHAPES.items() if k.startswith(("U+212A", "U+0130"))}
        self._each_alias(shapes, "working")
        self._each_alias(shapes, "default")

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


if __name__ == "__main__":
    unittest.main(verbosity=1)
