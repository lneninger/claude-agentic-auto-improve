#!/usr/bin/env python3
"""test_db_guard_path_allowlist.py -- RED suite for the Folder-name match of the database guard's allow-list.

Contract: .claude/concepts/2026-10-13-database-guard-names-in-rules-file.md in the consuming repository
(parent issue #623, sub-task 1 of 13): Data Shapes, "Folder-name match", and Revision 3.

WHAT LAYER 3c AND ITS ALLOW-LIST ARE FOR
----------------------------------------
Layer 3c blocks an edit whose text both names a protected database in a connection form and holds a write
keyword. ``production_path_allowlist`` in the project's rules file exempts only the places where such text
is legitimate source. Today an entry matches when it is a SUBSTRING of the file path, so the entry
``.cs`` exempts every C# file anywhere, and ``src/`` exempts ``tools/src/x.cs``. The contract replaces the
substring with a whole-folder match anchored at the project root.

THE MATCH RULE UNDER TEST
-------------------------
An entry of k folder names matches a file when they equal the first k folder names of the file's path,
counted from the project root (``CLAUDE_PROJECT_DIR``, reduced to its main checkout) after every leading
worktree segment is removed; compared whole and without letter case. Never a substring.

  * a path outside the project root, on another drive, or under another folder is never exempt;
  * a ``..`` folder anywhere makes the path not exempt;
  * a malformed entry (a drive letter, a ``..`` folder, or nothing left) is skipped, and the key
    ``production_path_allowlist`` is named in the block banner;
  * with ``CLAUDE_PROJECT_DIR`` unset nothing is allow-listed;
  * a worktree path equals the main checkout's path for an allow-listed folder; worktree source that is
    not allow-listed is not exempt; ``CLAUDE_PROJECT_DIR`` may be the worktree and gives the same verdicts;
  * a worktree segment that is not LEADING in the relative path (``src/.claude./worktrees/w/...``) is not
    removed.

THREE HELPER STATES, EVERY ROW IN EACH
--------------------------------------
``normal``    ``_project_paths.py`` beside the guard (the real one);
``fallback``  no ``_project_paths.py`` (the guard's inline stand-in);
``stale``     a ``_project_paths.py`` that imports but lacks ``checkout_equivalent_path``; the verdicts must
              equal fallback mode.

FIXTURE
-------
A project folder in a temporary directory is ``CLAUDE_PROJECT_DIR``. A copy of the guard plus helpers sits
under ``<fixture>/.claude/hooks`` with a fixture rules file protecting only the fictional name ``AcmeApp``
(the project's own names are never used). HOME and USERPROFILE point inside the fixture so no real log is
written. Everything is removed afterwards.

Run:
    py -3 .claude/hooks/tests/test_db_guard_path_allowlist.py
"""
from __future__ import annotations

import json
import os
import posixpath
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent
GUARD = HOOKS / "db-destructive-guard.py"
RULES_NAME = "db-destructive-guard.rules.json"

# Built from pieces, as the neighbouring suites do, so this source holds no literal the guard screens for.
_INSERT = "INS" + "ERT INTO"
PROTECTED = "AcmeApp"

_STALE_PROJECT_PATHS_SOURCE = '''"""Stale _project_paths.py: imports cleanly, lacks the checkout-equivalent function."""
from __future__ import annotations
import os
from pathlib import Path

HOME = Path.home()
SELF_ROOT = Path(__file__).resolve().parent.parent


def project_dir():
    raw = os.environ.get("CLAUDE_PROJECT_DIR")
    if not raw:
        return None
    try:
        return Path(raw).resolve()
    except OSError:
        return Path(raw)


def claude_roots():
    roots = []
    proj = project_dir()
    if proj is not None:
        roots.append(proj / ".claude")
    roots.append(SELF_ROOT)
    roots.append(HOME / ".claude")
    return roots


def concepts_roots():
    return [r / "concepts" for r in claude_roots()]


def logs_dir():
    proj = project_dir()
    if proj is not None:
        return proj / ".claude" / "logs"
    return HOME / ".claude" / "logs"
'''

STATES = ("normal", "fallback", "stale")


def _rm_tree(path):
    def onerror(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    shutil.rmtree(str(path), onerror=onerror)


class Fixture:
    """Three project folders (one per helper state) plus a worktree folder inside each."""

    def __init__(self):
        self.base = Path(tempfile.mkdtemp(prefix="pnallow-test-")).resolve()
        self.home = self.base / "home"
        self.home.mkdir()
        self.projects = {}
        for state in STATES:
            root = self.base / ("proj-" + state)
            hooks = root / ".claude" / "hooks"
            hooks.mkdir(parents=True)
            wt = root / ".claude" / "worktrees" / "w"
            (wt / ".claude" / "hooks").mkdir(parents=True)
            shutil.copy2(str(GUARD), str(hooks / GUARD.name))
            shutil.copy2(str(HOOKS / "_error_log.py"), str(hooks / "_error_log.py"))
            if state == "normal":
                shutil.copy2(str(HOOKS / "_project_paths.py"), str(hooks / "_project_paths.py"))
            elif state == "stale":
                (hooks / "_project_paths.py").write_text(_STALE_PROJECT_PATHS_SOURCE, encoding="utf-8")
            self.projects[state] = (root, wt)

    def close(self):
        _rm_tree(self.base)

    def write_rules(self, folder: Path, entries):
        rules = {"protected_databases": [PROTECTED], "production_path_allowlist": entries, "human_only_commands": []}
        path = folder / ".claude" / "hooks" / RULES_NAME
        path.write_text(json.dumps(rules), encoding="utf-8")

    def run(self, state, project_dir, path, entries, rules_folder=None, project_env=True):
        root, wt = self.projects[state]
        self.write_rules(root, entries)
        self.write_rules(wt, entries)
        env = dict(os.environ)
        env.pop("CLAUDE_DESTRUCTIVE_DB_OK", None)
        env.pop("DB_GUARD_FAULT_INJECTION", None)
        for key in ("HOME", "USERPROFILE"):
            env[key] = str(self.home)
        if project_env:
            env["CLAUDE_PROJECT_DIR"] = str(project_dir)
        else:
            env.pop("CLAUDE_PROJECT_DIR", None)
        content = ('const string cs = "Server=(localdb)\\\\m;Database=%s;Trusted_Connection=True;";\n'
                   'await conn.ExecuteAsync("%s Users (Id, Name) VALUES (1, \'x\')");' % (PROTECTED, _INSERT))
        payload = {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}
        guard = root / ".claude" / "hooks" / GUARD.name
        proc = subprocess.run(["py", "-3", str(guard)], input=json.dumps(payload), capture_output=True,
                              text=True, env=env, timeout=30)
        return proc.returncode, proc.stderr


_FIXTURE: Fixture | None = None


def setUpModule():
    global _FIXTURE
    _FIXTURE = Fixture()
    unittest.addModuleCleanup(_FIXTURE.close)


# -----------------------------------------------------------------------------------------------------
# The rows. Each: id, rules entries, how the path and the project dir are built, expectation.
# ``where`` is "main" (CLAUDE_PROJECT_DIR = the main checkout), "worktree" (= the worktree) or "unset".
# -----------------------------------------------------------------------------------------------------
A5 = [".cs", "src/", ".claude/", "/.claude/", "src/acmeapp.api/"]
API = ["src/acmeapp.api/"]
WT_RULES = ["src/acmeapp.api/", ".claude/"]


def _swap_drive(path: str, letter: str) -> str:
    return letter + path[1:]


def _other_letter(path: str, candidates="ZYX") -> str:
    own = path[0].upper()
    return next(c for c in candidates if c != own)


ROWS = [
    # id, entries, path builder(root, wt), where, exempt, banner fragment expected when blocked
    ("allowed folder under src/ and the narrower entry", A5, lambda r, w: r + "/src/acmeapp.api/Program.cs", "main", True, ""),
    ("src/ entry matches a nested file", A5, lambda r, w: r + "/src/a/b.cs", "main", True, ""),
    (".claude/ entry matches a file under the project's .claude", A5, lambda r, w: r + "/.claude/concepts/a.md", "main", True, ""),
    ("/.claude/ entry anchors at the root", ["/.claude/"], lambda r, w: r + "/.claude/concepts/a.md", "main", True, ""),
    (".cs entry is not a substring: an ordinary C# file is not exempt", [".cs"], lambda r, w: r + "/x/Program.cs", "main", False, ""),
    (".cs entry matches a top-level item named .cs", [".cs"], lambda r, w: r + "/.cs", "main", True, ""),
    ("a top-level file ending in .cs is not exempt by the .cs entry", [".cs"], lambda r, w: r + "/Program.cs", "main", False, ""),
    ("tools/src/x.cs is not under src/", ["src/"], lambda r, w: r + "/tools/src/x.cs", "main", False, ""),
    ("srcx/a.cs is not under src/", ["src/"], lambda r, w: r + "/srcx/a.cs", "main", False, ""),
    ("src/.claude/x.cs is not exempt by the .claude/ entry", [".claude/"], lambda r, w: r + "/src/.claude/x.cs", "main", False, ""),
    ("a .. folder makes the path not exempt", ["src/"], lambda r, w: r + "/src/../tools/a.cs", "main", False, ""),
    ("drive letter in upper case", API, lambda r, w: r[0].upper() + r[1:] + "/src/acmeapp.api/a.cs", "main", True, ""),
    ("drive letter in lower case", API, lambda r, w: r[0].lower() + r[1:] + "/src/acmeapp.api/a.cs", "main", True, ""),
    ("a path on another drive is not exempt", API, lambda r, w: _swap_drive(r, _other_letter(r)) + "/src/acmeapp.api/a.cs", "main", False, ""),
    ("a path in a sibling folder of the project is not exempt (anchored at the root)", API,
     lambda r, w: posixpath.dirname(r) + "/other-project/src/acmeapp.api/a.cs", "main", False, ""),
    ("a worktree path of an allow-listed folder equals main's", WT_RULES, lambda r, w: w + "/src/acmeapp.api/a.cs", "main", True, ""),
    ("worktree source that is not allow-listed is not exempt", WT_RULES, lambda r, w: w + "/src/other/b.cs", "main", False, ""),
    ("the worktree's own .claude/ file is exempt", WT_RULES, lambda r, w: w + "/.claude/concepts/a.md", "main", True, ""),
    ("CLAUDE_PROJECT_DIR = the worktree: an allow-listed file of the worktree is exempt", WT_RULES,
     lambda r, w: w + "/src/acmeapp.api/a.cs", "worktree", True, ""),
    ("CLAUDE_PROJECT_DIR = the worktree: other worktree source is not exempt", WT_RULES,
     lambda r, w: w + "/src/other/b.cs", "worktree", False, ""),
    ("CLAUDE_PROJECT_DIR = the worktree still exempts the main checkout's .claude/ file", [".claude/"],
     lambda r, w: r + "/.claude/concepts/a.md", "worktree", True, ""),
    ("CLAUDE_PROJECT_DIR = the worktree: a main-checkout path equals the worktree's", API,
     lambda r, w: r + "/src/acmeapp.api/a.cs", "worktree", True, ""),
    ("malformed entries are skipped and the valid one still applies", ["C:/x/", "../y/", "src/"],
     lambda r, w: r + "/src/a.cs", "main", True, ""),
    ("malformed entries are named in the banner of a block", ["C:/x/", "../y/", "src/"],
     lambda r, w: r + "/tools/a.cs", "main", False, "production_path_allowlist"),
    ("a malformed entry never matches as a substring", ["../y/"], lambda r, w: r + "/q/../y/a.cs", "main", False, ""),
    ("CLAUDE_PROJECT_DIR unset: nothing is allow-listed", [".claude/"],
     lambda r, w: r + "/.claude/concepts/a.md", "unset", False, ""),
    # Revision 3
    ("a worktree-shaped path under another folder and drive is not exempt", API,
     lambda r, w: "E:/x/.claude/worktrees/w/src/acmeapp.api/a.cs" if r[0].upper() != "E" else "Z:/x/.claude/worktrees/w/src/acmeapp.api/a.cs",
     "main", False, ""),
    ("a worktree-shaped path under a sibling folder is not exempt", API,
     lambda r, w: posixpath.dirname(r) + "/other/.claude/worktrees/w/src/acmeapp.api/a.cs", "main", False, ""),
    ("an interior worktree segment is not removed: src/.claude./worktrees/w/acmeapp.api/a.cs", API,
     lambda r, w: r + "/src/.claude./worktrees/w/acmeapp.api/a.cs", "main", False, ""),
    ("an interior worktree segment with the plain spelling is not removed either", API,
     lambda r, w: r + "/src/.claude/worktrees/w/acmeapp.api/a.cs", "main", False, ""),
]


class AllowlistCase(unittest.TestCase):
    pass


def _make_test(state, row):
    name, entries, build, where, exempt, banner = row

    def test(self):
        fx = _FIXTURE
        root, wt = fx.projects[state]
        r = root.as_posix()
        w = wt.as_posix()
        path = build(r, w)
        project_env = where != "unset"
        project_dir = wt if where == "worktree" else root
        rc, err = fx.run(state, project_dir, path, entries, project_env=project_env)
        if exempt:
            self.assertEqual(rc, 0, "[%s] %s: expected the write to be exempt (exit 0), got %d. path=%s stderr=%r"
                             % (state, name, rc, path, err[:300]))
        else:
            self.assertEqual(rc, 2, "[%s] %s: expected the write to be blocked (exit 2), got %d. path=%s stderr=%r"
                             % (state, name, rc, path, err[:300]))
            self.assertIn("PROTECTED", err, "the block is the Layer 3c block, not another one. stderr=%r" % err[:300])
            if banner:
                self.assertIn(banner, err, "[%s] %s: the banner must name %s. stderr=%r" % (state, name, banner, err[:500]))
    return test


for _state in STATES:
    for _index, _row in enumerate(ROWS):
        _slug = "".join(c if c.isalnum() else "_" for c in _row[0].lower())[:70]
        setattr(AllowlistCase, "test_%s_%02d_%s" % (_state, _index, _slug), _make_test(_state, _row))


class HelperStateControlTests(unittest.TestCase):
    """The three fixtures really are in the three helper states the rows claim."""

    def test_the_normal_fixture_has_the_real_helper_with_the_checkout_equivalent_function(self):
        root, _ = _FIXTURE.projects["normal"]
        text = (root / ".claude" / "hooks" / "_project_paths.py").read_text(encoding="utf-8")
        self.assertIn("def checkout_equivalent_path", text)

    def test_the_fallback_fixture_has_no_helper(self):
        root, _ = _FIXTURE.projects["fallback"]
        self.assertFalse((root / ".claude" / "hooks" / "_project_paths.py").exists())

    def test_the_stale_fixture_has_a_helper_without_the_checkout_equivalent_function(self):
        root, _ = _FIXTURE.projects["stale"]
        text = (root / ".claude" / "hooks" / "_project_paths.py").read_text(encoding="utf-8")
        self.assertNotIn("checkout_equivalent_path", text)
        self.assertIn("def logs_dir", text)


if __name__ == "__main__":
    unittest.main(verbosity=1)
