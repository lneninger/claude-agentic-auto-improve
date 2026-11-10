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
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
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
        trace = self.root / "trace.json"
        self.verdict(work, "names-removed", "--working-ref", c2, "--default-ref", c1,
                     env={"GIT_TRACE2_EVENT": str(trace)})
        self.assertTrue(trace.exists(), "control: git ran and was traced")
        calls = [json.loads(l).get("argv") or [] for l in trace.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertFalse([a for a in calls if "fetch" in a[1:]], "reading two commits runs no git fetch")


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


if __name__ == "__main__":
    unittest.main(verbosity=1)
