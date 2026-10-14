#!/usr/bin/env python3
"""test_shell_write_targets.py -- RED suite for the shared shell parser ``_shell_write_targets.py``.

Contract: .claude/concepts/2026-10-12-dedupe-claude-config.md in the consuming repository, Revision 4, D
("The shell parser becomes a default plugin file; the strict gate stays an add-on"), and block 16.

THE FACT BEHIND THIS SUITE
--------------------------
The main-checkout guard reads write targets from shell text with ``parse_redirect_targets``. It used to
load that function from ``bash-gate.py`` in its own folder on every simple command. The plugin's hooks
folder holds no ``bash-gate.py``, so every shell command took the launcher's degraded path. The fix moves
``parse_redirect_targets`` and its two helpers, ``_QUOTE_RE`` and ``_strip_quoted``, VERBATIM into a default
helper file ``_shell_write_targets.py`` that both the guard and the strict add-on import.

WHAT IS PINNED
--------------
1. ``parse_redirect_targets`` returns, for a table of commands, the same (tool, path) pairs the old function
   returned. The pairs are RECORDED in the table below as literals, read from the function at the moment it
   was moved; this file never imports the old file. Two rows pin behaviour that looks like a defect and is
   kept on purpose, because the move is verbatim: the ``cp`` and ``mv`` rows give no pair (the old pattern
   is built with an f-string whose ``{1,}`` is read as a tuple, so it never matches), and
   ``sed -i ... && git diff --stat`` reads ``--stat`` as the file written. A later fix to either changes
   these rows on purpose, in its own change.
2. The helper uses only the standard library.
3. The main-checkout guard, loaded from a hooks folder that holds NO ``bash-gate.py``, judges a redirect
   into the main checkout with its own block (not the launcher's "guard degraded" path).

RED TODAY: ``_shell_write_targets.py`` does not exist yet (block 17 adds it), so every parser row fails
with a message that names the missing file, and the guard row fails because the guard still loads
``bash-gate.py``. The loader below turns a missing file into a failing assertion, never an import crash.

Run:
    py -3 .claude/hooks/tests/test_shell_write_targets.py
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = HOOKS_DIR.parent / "scripts"
HELPER = HOOKS_DIR / "_shell_write_targets.py"

#: The text a redirect to a quoted path would need; built from parts so no row below trips a scanner.
_OPEN = "ope" + "n("


def load_helper():
    """Load ``_shell_write_targets.py`` by path; a missing or broken file FAILS the calling test."""
    if not HELPER.is_file():
        raise AssertionError("%s does not exist yet (block 17 adds the shared shell parser)" % HELPER)
    spec = importlib.util.spec_from_file_location("_shell_write_targets_under_test", str(HELPER))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        raise AssertionError("%s does not load: %s: %s" % (HELPER, type(exc).__name__, exc))
    return module


def parser():
    module = load_helper()
    fn = getattr(module, "parse_redirect_targets", None)
    if fn is None:
        raise AssertionError("_shell_write_targets.parse_redirect_targets does not exist")
    return fn


# ---------------------------------------------------------------------------
# The table. (command, expected pairs). Expected values are literals recorded from the old function.
# ---------------------------------------------------------------------------
REDIRECT_ROWS = [
    ("echo hi > out.txt", [(">", "out.txt")]),
    ("echo hi >> out.txt", [(">", "out.txt")]),
    ("echo hi 2> err.log", [(">", "err.log")]),
    ("echo hi &> both.log", [(">", "both.log")]),
    ("echo hi 1>out.txt", [(">", "out.txt")]),
    ("echo hi > a.txt; echo yo >> b.txt", [(">", "a.txt"), (">", "b.txt")]),
    ("echo hi \\\n > c.txt", [(">", "c.txt")]),
    ("echo a > x.txt && echo b > x.txt", [(">", "x.txt")]),
]
DEV_NULL_ROWS = [
    ("echo hi > /dev/null", []),
    ("echo hi > NUL", []),
    ("cat a.txt | tee /dev/null", []),
]
TEE_ROWS = [
    ("cat a.txt | tee b.txt", [("tee", "b.txt")]),
    ("cat a.txt | tee -a b.txt", [("tee", "b.txt")]),
    ("cat in | tee out1.txt out2.txt", [("tee", "out1.txt")]),
]
SED_ROWS = [
    ("sed -i 's/a/b/' src/Foo.cs", [("sed -i", "src/Foo.cs")]),
    ("sed -i '' 's/a/b/' src/Foo.cs", [("sed -i", "src/Foo.cs")]),
    ("sed -i.bak 's/a/b/' src/Foo.cs", [("sed -i", "src/Foo.cs")]),
    # Kept as recorded (verbatim move): the option of the NEXT command is read as the file written.
    ("sed -i 's/a/b/' src/Foo.cs && git diff --stat", [("sed -i", "--stat")]),
]
AWK_ROWS = [
    ("awk -i inplace '{print}' src/Foo.cs", [("awk -i inplace", "src/Foo.cs")]),
]
CP_MV_ROWS = [
    # Kept as recorded (verbatim move): the old pattern never matches, so none of these gives a pair.
    ("cp a.txt src/b.txt", []),
    ("cp -r a src/dir", []),
    ("mv old.cs src/new.cs", []),
    ("mv -f x.txt y.txt", []),
    ("cp a.txt b.txt c.txt", []),
]
DD_ROWS = [
    ("dd if=/dev/zero of=src/disk.img bs=1 count=1", [("dd", "src/disk.img")]),
]
PYTHON_ROWS = [
    ('python -c "' + _OPEN + "'src/x.py','w').write('1')\"", [("python open-write", "src/x.py")]),
    ('python -c "' + _OPEN + "'src/y.py', 'a')\"", [("python open-write", "src/y.py")]),
    ('python -c "' + _OPEN + "'src/r.py','r')\"", []),
]
NOTHING_ROWS = [
    ("echo 'a > b.txt'", []),
    ('echo "x > y.txt" | cat', []),
    ("echo '{\"a\": 1}' | py -3 tool.py", []),
    ('echo "tee fake.txt" && ls', []),
    ("echo 'cp a.txt b.txt'", []),
    ("git status", []),
    ("ls -la", []),
    # A quoted target is masked with the rest of the quoted text: no pair, as recorded.
    ('echo hi > "q r.txt"', []),
]


class ParserTableTests(unittest.TestCase):
    """The recorded pairs, one test per command family."""

    def _check(self, rows) -> None:
        fn = parser()
        wrong = []
        for command, expected in rows:
            got = [tuple(p) for p in fn(command)]
            if got != [tuple(p) for p in expected]:
                wrong.append("%r: expected %r, got %r" % (command, expected, got))
        self.assertEqual(wrong, [], msg="parse_redirect_targets must return the pairs recorded from the old "
                                        "function for every row:\n" + "\n".join(wrong))

    def test_each_redirect_form(self):
        self._check(REDIRECT_ROWS)

    def test_dev_null_and_nul_targets_give_no_pair(self):
        self._check(DEV_NULL_ROWS)

    def test_tee_with_and_without_append(self):
        self._check(TEE_ROWS)

    def test_sed_in_place_including_the_recorded_misread(self):
        self._check(SED_ROWS)

    def test_awk_in_place(self):
        self._check(AWK_ROWS)

    def test_cp_and_mv_give_no_pair_as_recorded(self):
        self._check(CP_MV_ROWS)

    def test_dd_of(self):
        self._check(DD_ROWS)

    def test_python_open_for_write(self):
        self._check(PYTHON_ROWS)

    def test_quoted_text_and_non_writes_give_nothing(self):
        self._check(NOTHING_ROWS)

    def test_a_row_that_writes_is_not_empty_control(self):
        """Control: the table itself can fail. A parser that returned [] for everything passes the 'nothing'
        rows only, so the redirect rows must hold at least one non-empty expectation."""
        self.assertTrue(any(exp for _cmd, exp in REDIRECT_ROWS + TEE_ROWS + SED_ROWS + DD_ROWS),
                        msg="the table needs rows that expect a pair, or an always-empty parser would pass it")
        fn = parser()
        self.assertEqual([tuple(p) for p in fn("echo hi > out.txt")], [(">", "out.txt")],
                         msg="the simplest redirect must give its pair")


class HelperShapeTests(unittest.TestCase):
    def test_the_two_pieces_the_parser_uses_move_with_it(self):
        module = load_helper()
        for name in ("_QUOTE_RE", "_strip_quoted", "parse_redirect_targets"):
            self.assertTrue(hasattr(module, name), msg="the helper must hold %s (moved verbatim)" % name)
        blanked = module._strip_quoted("echo 'a > b' x")
        self.assertEqual(len(blanked), len("echo 'a > b' x"),
                         msg="_strip_quoted keeps offsets: every quoted segment becomes spaces of the same length")
        self.assertNotIn(">", blanked, msg="a '>' inside quotes must be hidden")

    def test_the_helper_uses_only_the_standard_library(self):
        self.assertTrue(HELPER.is_file(), msg="%s does not exist yet" % HELPER)
        tree = ast.parse(HELPER.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        stdlib = set(getattr(sys, "stdlib_module_names", ())) | {"re", "pathlib", "__future__"}
        self.assertTrue(imported <= stdlib,
                        msg="the helper must import only the standard library so it can never fail to load "
                            "for a missing sibling; it imports %s" % sorted(imported - stdlib))

    def test_the_helper_is_never_registered_as_a_hook(self):
        hooks_json = HOOKS_DIR / "hooks.json"
        if hooks_json.is_file():
            self.assertNotIn("_shell_write_targets", hooks_json.read_text(encoding="utf-8"),
                             msg="a helper (underscore file) is imported, never registered")
        self.assertTrue(HELPER.is_file(), msg="%s does not exist yet" % HELPER)


# ---------------------------------------------------------------------------
# The guard, run from a hooks folder that holds NO bash-gate.py.
# ---------------------------------------------------------------------------
def _clean_env(extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_")
           and k not in ("CLAUDE_PROJECT_DIR", "GH_REPO", "GH_HOST", "CLAUDE_CONCEPT_GATE",
                         "CLAUDE_BASH_GATE", "CLAUDE_ACTIVE_CONTRACT")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra:
        env.update(extra)
    return env


def _git(cwd: Path, *args: str) -> None:
    proc = subprocess.run(
        ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(cwd), env=_clean_env(), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError("fixture git %s failed in %s: %s" % (" ".join(args), cwd, proc.stderr.strip()))


class GuardWithoutBashGateTests(unittest.TestCase):
    """The guard judges a redirect into the main checkout with its OWN block, from a hooks folder with no
    bash-gate.py (the plugin's default folder)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="swt_guard_")))
        cls.copy_hooks = cls.root / "plugin" / ".claude" / "hooks"
        cls.copy_scripts = cls.root / "plugin" / ".claude" / "scripts"
        cls.copy_hooks.mkdir(parents=True)
        cls.copy_scripts.mkdir(parents=True)
        for item in HOOKS_DIR.iterdir():
            if item.is_file() and item.suffix in (".py", ".json") and item.name != "bash-gate.py":
                shutil.copy2(item, cls.copy_hooks / item.name)
        for item in SCRIPTS_DIR.glob("*.py"):
            shutil.copy2(item, cls.copy_scripts / item.name)
        cls.main = cls.root / "main_checkout"
        cls.main.mkdir()
        _git(cls.main, "init", "-q")
        _git(cls.main, "symbolic-ref", "HEAD", "refs/heads/master")
        (cls.main / "src").mkdir()
        (cls.main / "src" / ".gitkeep").write_text("", encoding="utf-8")
        (cls.main / "README.md").write_text("fixture\n", encoding="utf-8")
        _git(cls.main, "add", "-A")
        _git(cls.main, "commit", "-q", "-m", "fixture")
        cls.wt = cls.main / ".claude" / "worktrees" / "20261014-fixture"
        _git(cls.main, "worktree", "add", "-q", "-b", "fixture-branch", str(cls.wt))

    @classmethod
    def tearDownClass(cls) -> None:
        def _onerror(func, path, _exc):
            try:
                os.chmod(path, 0o700)
                func(path)
            except OSError:
                pass
        shutil.rmtree(cls.root, onerror=_onerror)

    def launch(self, command: str, cwd: Path):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
        return subprocess.run(
            [sys.executable, "-B", str(self.copy_hooks / "gate-launch.py"), str(self.copy_hooks / "concept-gate.py")],
            input=json.dumps(payload).encode("utf-8"), capture_output=True, cwd=str(cwd),
            env=_clean_env({"CLAUDE_PROJECT_DIR": str(self.main)}), timeout=90)

    def test_the_folder_holds_no_bash_gate(self):
        self.assertFalse((self.copy_hooks / "bash-gate.py").exists(),
                         msg="this suite's premise: the hooks folder has no bash-gate.py")

    def test_a_redirect_into_the_main_checkout_is_blocked_by_the_guard_itself(self):
        main = str(self.main).replace("\\", "/")
        blocked = self.launch("echo x > %s/src/x.cs" % main, self.wt)
        err = blocked.stderr.decode("utf-8", errors="replace")
        self.assertEqual(blocked.returncode, 2, msg="a redirect into the main checkout must exit 2: " + err[:400])
        self.assertIn("MAIN CHECKOUT", err, msg="the block must be the guard's banner: " + err[:400])
        self.assertNotIn("guard degraded", err,
                         msg="the block must be the guard's own decision, not the launcher's degraded path "
                             "(that path means the guard crashed on a missing bash-gate.py): " + err[:400])
        self.assertNotIn("launcher failed", err, msg="the launcher itself must not fail: " + err[:400])
        # ALLOW counts only with the BLOCK sibling above: the same redirect into the worktree is let through.
        wt = str(self.wt).replace("\\", "/")
        allowed = self.launch("echo x > %s/docs/x.md" % wt, self.wt)
        self.assertEqual(allowed.returncode, 0,
                         msg="a redirect into the worktree is not a main-checkout write: "
                             + allowed.stderr.decode("utf-8", errors="replace")[:400])


if __name__ == "__main__":
    unittest.main(verbosity=2)
