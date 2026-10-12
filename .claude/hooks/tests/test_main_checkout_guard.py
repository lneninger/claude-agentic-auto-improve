#!/usr/bin/env python3
"""test_main_checkout_guard.py -- RED suite for the gate launcher and the main-checkout guard.

Contract: .claude/concepts/2026-10-07-worktree-isolation-by-default.md (block 1, sub-issue #472)
Invariants pinned here: I-1, I-2, I-3, I-6, Shell reading, Resolved path, Git command class,
gh command class, Write target, Acting directory.

Run:
    py -3 .claude/hooks/tests/test_main_checkout_guard.py

HOW THE TESTS DRIVE THE CODE
----------------------------
Every row launches ``gate-launch.py <gate path>`` as a SUBPROCESS (never by import), feeding
one hook payload on stdin, exactly as Claude Code registers it. The child environment comes
from one helper that strips CLAUDE_PROJECT_DIR, GH_REPO, GH_HOST and every GIT_* variable
(control: ``HelperEnvironmentControlTests``). Fixtures are real ``git init`` and
``git worktree add`` folders in a temp folder outside any ``.claude`` path: a main checkout, a
flat worktree of it, a second repository and a plain folder.

COUNTING RULE
-------------
* BLOCK counts only with exit code 2 AND the marker ``MAIN CHECKOUT`` in stderr, so a gate that
  blocks for its own reason, or a launcher that is missing (Python exits 2 for a missing file),
  never counts as a guard block.
* ALLOW counts only with a same-run BLOCK sibling: ``_expect_allow`` fails unless a BLOCK row of
  the same test method has already been confirmed. Allow targets are .md files.

RED TODAY: gate-launch.py does not exist yet, so every launch exits 2 with Python's "can't open
file" text and no ``MAIN CHECKOUT``; every row therefore fails on an ASSERTION (never an
import), reporting what the launcher should have said.
"""
from __future__ import annotations

import ast
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = HOOKS_DIR.parent / "scripts"
LAUNCHER = HOOKS_DIR / "gate-launch.py"
LAUNCHER_BODY = HOOKS_DIR / "_gate_launch.py"
GUARD = HOOKS_DIR / "_main_checkout_guard.py"
CONCEPT_GATE = HOOKS_DIR / "concept-gate.py"
BASH_GATE = HOOKS_DIR / "bash-gate.py"
# Plugin copy (contract 2026-10-07-worktree-isolation-by-default, round-7 amendment): the plugin ships and
# registers no bash-gate.py, so a case that launches it cannot run here. Only those cases are skipped.
BASH_GATE_SKIP_REASON = ("the plugin does not register bash-gate (cut by 2026-09-28-hook-server-modes, "
                         "INV-O1)")


def needs_missing_bash_gate(gate) -> bool:
    return Path(gate) == BASH_GATE and not BASH_GATE.is_file()

MARKER = "MAIN CHECKOUT"
IS_WINDOWS = os.name == "nt"
SKIP_REAL_PATHS = ("the main-checkout guard refuses real-path writes from a main checkout; run from a "
                   "linked worktree (contract 2026-10-07-worktree-isolation-by-default)")

#: Variables the child must never see (control: HelperEnvironmentControlTests).
_STRIPPED_EXACT = ("CLAUDE_PROJECT_DIR", "GH_REPO", "GH_HOST", "CLAUDE_CONCEPT_GATE",
                   "CLAUDE_BASH_GATE", "CLAUDE_ACTIVE_CONTRACT")


def clean_env(extra: dict | None = None) -> dict:
    """The one helper that builds every child environment (no project dir, no gh repo or host,
    no GIT_* variable, no off switch)."""
    env = {k: v for k, v in os.environ.items()
           if k not in _STRIPPED_EXACT and not k.startswith("GIT_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if extra:
        env.update(extra)
    return env


def posix(path) -> str:
    return str(path).replace("\\", "/")


# ---------------------------------------------------------------------------
# Fixtures: real git repositories in a temp folder outside any .claude path.
# ---------------------------------------------------------------------------
class Fixture:
    root: Path
    main: Path
    wt: Path
    second: Path
    plain: Path
    junction: Path | None
    junction_skip_reason: str | None
    short_main: str | None
    short_skip_reason: str | None
    copy_counter = 0


FX = Fixture()


def _git(cwd: Path, *args: str) -> None:
    proc = subprocess.run(
        ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(cwd), env=clean_env(), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"fixture git {' '.join(args)} failed in {cwd}: {proc.stderr.strip()}")


def _make_repo(path: Path) -> None:
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    _git(path, "symbolic-ref", "HEAD", "refs/heads/master")
    (path / "src").mkdir()
    (path / "src" / ".gitkeep").write_text("", encoding="utf-8")
    (path / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "fixture")


def setUpModule() -> None:
    FX.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="mcg_fixture_")))
    FX.main = FX.root / "main_checkout_fixture"
    _make_repo(FX.main)
    FX.wt = FX.main / ".claude" / "worktrees" / "20261007-test-fixture"
    _git(FX.main, "worktree", "add", "-q", "-b", "fixture-branch", str(FX.wt))
    FX.second = FX.root / "second_repository"
    _make_repo(FX.second)
    FX.plain = FX.root / "plain_folder"
    FX.plain.mkdir()
    (FX.main / ".claude" / "logs").mkdir(parents=True, exist_ok=True)

    FX.junction, FX.junction_skip_reason = None, None
    if IS_WINDOWS:
        link = FX.root / "junction_to_main"
        proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(FX.main)],
                              capture_output=True, text=True)
        if proc.returncode == 0 and link.exists():
            FX.junction = link
        else:
            FX.junction_skip_reason = f"this machine refused to create a junction: {proc.stdout.strip()} {proc.stderr.strip()}"
    else:
        FX.junction_skip_reason = "junction rows are Windows-only"

    FX.short_main, FX.short_skip_reason = None, None
    if IS_WINDOWS:
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.windll.kernel32.GetShortPathNameW(str(FX.main), buf, 1024)
        if n and "~" in buf.value:
            FX.short_main = buf.value
        else:
            FX.short_skip_reason = "this machine has 8.3 short names disabled for the temp folder"
    else:
        FX.short_skip_reason = "8.3 rows are Windows-only"


def tearDownModule() -> None:
    if FX.junction is not None:
        try:
            os.rmdir(FX.junction)
        except OSError:
            pass
    for extra in FX.root.rglob("junction_inside"):
        try:
            os.rmdir(extra)
        except OSError:
            pass

    def _onerror(func, path, exc):
        try:
            os.chmod(path, 0o700)
            func(path)
        except OSError:
            pass
    shutil.rmtree(FX.root, onerror=_onerror)


# ---------------------------------------------------------------------------
# Launching.
# ---------------------------------------------------------------------------
class Result:
    def __init__(self, rc: int, out: bytes, err: bytes):
        self.rc, self.out, self.err_bytes = rc, out, err
        self.err = err.decode("utf-8", errors="replace")

    def describe(self) -> str:
        return f"exit={self.rc} stderr={self.err.strip()[:400]!r} stdout={self.out.decode('utf-8', 'replace').strip()[:200]!r}"


def launch(stdin, *, gate: str | Path = CONCEPT_GATE, hooks_dir: Path = HOOKS_DIR, gate_arg: str | None = None,
           project: Path | str | None = None, extra_env: dict | None = None) -> Result:
    """Run ``gate-launch.py <gate>`` as a subprocess with ``stdin`` (dict -> JSON UTF-8, bytes as is)."""
    if isinstance(stdin, dict):
        stdin = json.dumps(stdin).encode("utf-8")
    env = clean_env(extra_env)
    if project is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project)
    arg = gate_arg if gate_arg is not None else str(Path(hooks_dir) / Path(gate).name)
    proc = subprocess.run([sys.executable, str(Path(hooks_dir) / "gate-launch.py"), arg], input=stdin,
                          capture_output=True, env=env, timeout=90)
    return Result(proc.returncode, proc.stdout, proc.stderr)


FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def file_payload(tool: str, path: str, cwd: Path | str) -> dict:
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    tool_input = {key: path}
    if tool == "Edit":
        tool_input.update(old_string="a", new_string="b")
    elif tool == "Write":
        tool_input["content"] = "x"
    elif tool == "MultiEdit":
        tool_input["edits"] = [{"old_string": "a", "new_string": "b"}]
    return {"tool_name": tool, "tool_input": tool_input, "cwd": str(cwd)}


def shell_payload(tool: str, command: str, cwd: Path | str) -> dict:
    return {"tool_name": tool, "tool_input": {"command": command}, "cwd": str(cwd)}


class Case:
    def __init__(self, name, payload, expect, *, project=None, extra_env=None, contains=(), hooks_dir=None,
                 gate=None):
        self.name, self.payload, self.expect = name, payload, expect
        self.project, self.extra_env, self.contains = project, extra_env, tuple(contains)
        self.hooks_dir = hooks_dir or HOOKS_DIR
        if gate is None:
            tool = payload.get("tool_name") if isinstance(payload, dict) else None
            gate = BASH_GATE if tool in ("Bash", "PowerShell") else CONCEPT_GATE
        self.gate = gate


def f(name, tool, path, cwd, project, expect, **kw) -> Case:
    return Case(name, file_payload(tool, str(path), cwd), expect, project=project, **kw)


def sh(name, tool, command, cwd, project, expect, **kw) -> Case:
    return Case(name, shell_payload(tool, command, cwd), expect, project=project, **kw)


class GuardTestCase(unittest.TestCase):
    """Base class: the BLOCK / ALLOW counting rule."""

    def setUp(self) -> None:
        self._block_ok = False

    @staticmethod
    def is_block(res: Result) -> bool:
        return res.rc == 2 and MARKER in res.err

    def _expect_block(self, res: Result, contains=()) -> None:
        self.assertTrue(self.is_block(res),
                        msg=f"must BLOCK with exit 2 AND '{MARKER}' in stderr (a gate-only block or a missing "
                            f"launcher does not count): {res.describe()}")
        for text in contains:
            self.assertIn(text, res.err, msg=f"the block banner must say {text!r}")
        self._block_ok = True

    def _expect_allow(self, res: Result) -> None:
        self.assertTrue(self._block_ok,
                        msg="ALLOW counts only with a same-run BLOCK sibling confirmed first: no BLOCK row of this "
                            "test method has passed, so this allow proves nothing")
        self.assertEqual(res.rc, 0, msg=f"must ALLOW (exit 0): {res.describe()}")
        self.assertNotIn(MARKER, res.err, msg="an allowed call must not carry the guard banner")

    def run_cases(self, cases: list[Case]) -> None:
        for case in cases:
            if needs_missing_bash_gate(case.gate):
                with self.subTest(case.name):
                    self.skipTest(BASH_GATE_SKIP_REASON)
        cases = [c for c in cases if not needs_missing_bash_gate(c.gate)]
        ordered = sorted(cases, key=lambda c: 0 if c.expect == "block" else 1)

        def one(case: Case) -> Result:
            return launch(case.payload, gate=case.gate, hooks_dir=case.hooks_dir, project=case.project,
                          extra_env=case.extra_env)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(one, ordered))
        for case, res in zip(ordered, results):
            with self.subTest(case.name):
                if case.expect == "block":
                    self._expect_block(res, case.contains)
                else:
                    self._expect_allow(res)


# ---------------------------------------------------------------------------
# Hooks-folder copies (degraded rows, launcher edges, gate pass-through).
# ---------------------------------------------------------------------------
def make_hooks_copy(label: str, *, overwrite: dict | None = None, delete: tuple = ()) -> Path:
    """A copy of the hooks folder (files only) beside a scripts folder holding the shared helpers."""
    FX.copy_counter += 1
    base = FX.root / "copies" / f"{label}_{FX.copy_counter}"
    dest = base / "hooks"
    dest.mkdir(parents=True)
    for item in HOOKS_DIR.iterdir():
        if item.is_file():
            shutil.copy2(item, dest / item.name)
    scripts_dest = base / "scripts"
    scripts_dest.mkdir()
    for item in SCRIPTS_DIR.glob("_*.py"):
        shutil.copy2(item, scripts_dest / item.name)
    for name, text in (overwrite or {}).items():
        (dest / name).write_text(text, encoding="utf-8")
    for name in delete:
        target = dest / name
        if target.exists():
            target.unlink()
    return dest


GATE_MARKER_BODY = (
    "import pathlib, sys\n"
    "pathlib.Path(__file__).with_name('gate_ran.marker').write_text('1')\n"
)


def error_log_lines() -> int:
    total = 0
    for p in (FX.main / ".claude" / "logs" / "errors.jsonl",):
        if p.exists():
            total += len(p.read_text(encoding="utf-8", errors="replace").splitlines())
    return total


# ===========================================================================
# Control: the child environment.
# ===========================================================================
class HelperEnvironmentControlTests(unittest.TestCase):
    def test_child_environment_never_holds_the_stripped_variables(self):
        poison = {"CLAUDE_PROJECT_DIR": "x", "GH_REPO": "o/r", "GH_HOST": "h", "GIT_DIR": "x",
                  "GIT_WORK_TREE": "x", "GIT_INDEX_FILE": "x", "CLAUDE_CONCEPT_GATE": "off"}
        saved = {k: os.environ.get(k) for k in poison}
        os.environ.update(poison)
        try:
            proc = subprocess.run(
                [sys.executable, "-c",
                 "import os, json; print(json.dumps(sorted(k for k in os.environ if k in "
                 "('CLAUDE_PROJECT_DIR','GH_REPO','GH_HOST','CLAUDE_CONCEPT_GATE','CLAUDE_BASH_GATE') "
                 "or k.startswith('GIT_'))))"],
                env=clean_env(), capture_output=True, text=True)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.assertEqual(json.loads(proc.stdout), [],
                         msg="control: the one environment helper must strip CLAUDE_PROJECT_DIR, GH_REPO, GH_HOST "
                             "and every GIT_* variable even when the parent sets them")

    def test_fixtures_are_real_git_trees_outside_any_claude_path(self):
        self.assertTrue((FX.main / ".git").is_dir(), msg="the main checkout fixture has a .git DIRECTORY")
        self.assertTrue((FX.wt / ".git").is_file(), msg="the worktree fixture has a .git FILE")
        self.assertTrue((FX.second / ".git").is_dir(), msg="the second repository is a real repository")
        self.assertNotIn("/.claude/", posix(FX.root) + "/", msg="fixtures live outside any .claude path")
        self.assertIn("/.claude/worktrees/", posix(FX.wt), msg="the worktree fixture is a FLAT worktree of the main one")


# ===========================================================================
# File tools: Edit, Write, MultiEdit, NotebookEdit.
# ===========================================================================
class FileToolLaunchInputTests(GuardTestCase):
    """I-1, I-2: project dir, cwd, target matrix, for every covered file tool."""

    def _matrix(self, tool: str) -> list[Case]:
        main, wt = FX.main, FX.wt
        cases = [
            f(f"{tool} (main, main, main-file) blocks", tool, main / "src" / "x.cs", main, main, "block"),
            f(f"{tool} (wt, wt, main-file) blocks", tool, main / "src" / "x.cs", wt, wt, "block"),
            f(f"{tool} (main, main, relative) blocks", tool, "src/x.cs", main, main, "block"),
            f(f"{tool} (main, wt/src, wt-file) allows", tool, wt / "docs" / "x.md", wt / "src", main, "allow"),
            f(f"{tool} (wt, wt, relative) allows", tool, "docs/x.md", wt, wt, "allow"),
            f(f"{tool} (main, wt, relative) allows", tool, "docs/x.md", wt, main, "allow"),
            f(f"{tool} outside the repository allows", tool, FX.plain / "x.md", wt, main, "allow"),
            f(f"{tool} second repository main allows", tool, FX.second / "docs" / "x.md", wt, main, "allow"),
        ]
        return cases

    def test_edit_launch_inputs(self):
        self.run_cases(self._matrix("Edit"))

    def test_write_launch_inputs(self):
        self.run_cases(self._matrix("Write"))

    def test_multiedit_launch_inputs(self):
        self.run_cases(self._matrix("MultiEdit"))

    def test_notebookedit_launch_inputs(self):
        self.run_cases(self._matrix("NotebookEdit"))

    def test_second_repository_session_is_guarded_for_its_own_main_only(self):
        second = FX.second
        self.run_cases([
            f("session in the second repository blocks its own main", "Edit", second / "src" / "x.cs", second, second, "block"),
            f("session in the second repository allows the first main", "Edit", FX.main / "docs" / "x.md", second, second, "allow"),
        ])


class FileToolSpellingTests(GuardTestCase):
    """Resolved path: every spelling of a main target blocks (I-1)."""

    def _spellings(self) -> list[tuple[str, str]]:
        main, wt = posix(FX.main), posix(FX.wt)
        drive = main[0].lower()
        rows = [
            ("msys drive spelling", f"/{drive}/{main[3:]}/src/x.cs"),
            ("backslashes", str(FX.main / "src" / "x.cs")),
            ("mixed case", (main[:3] + main[3:].swapcase()) + "/src/x.cs"),
            ("worktree dot-dot to main", f"{wt}/../../../src/x.cs"),
            ("trailing dot component", f"{main}/src./x.cs"),
            ("alternate stream", f"{main}/src/x.cs:stream"),
            ("extended-length prefix", "\\\\?\\" + str(FX.main / "src" / "x.cs")),
            ("device prefix", "\\\\.\\" + str(FX.main / "src" / "x.cs")),
            ("driveless rooted forward", main[2:] + "/src/x.cs"),
            ("driveless rooted backslash", main[2:].replace("/", "\\") + "\\src\\x.cs"),
        ]
        if FX.junction is not None:
            rows.append(("junction into main", posix(FX.junction) + "/src/x.cs"))
        else:
            print(f"SKIP junction row: {FX.junction_skip_reason}", file=sys.stderr)
        if FX.short_main:
            rows.append(("8.3 short name", FX.short_main.replace("\\", "/") + "/src/x.cs"))
        else:
            print(f"SKIP 8.3 row: {FX.short_skip_reason}", file=sys.stderr)
        return rows

    @unittest.skipUnless(IS_WINDOWS, "Windows path spellings")
    def test_edit_blocks_every_spelling_of_a_main_target(self):
        cases = [f(f"Edit {n}", "Edit", p, FX.wt, FX.main, "block") for n, p in self._spellings()]
        cases.append(f("Edit worktree file allows", "Edit", FX.wt / "docs" / "x.md", FX.wt, FX.main, "allow"))
        self.run_cases(cases)

    @unittest.skipUnless(IS_WINDOWS, "Windows path spellings")
    def test_edit_lower_case_drive_spelling_blocks_main_and_allows_worktree_md(self):
        main, wt = posix(FX.main), posix(FX.wt)
        drive = main[0].lower()
        self.run_cases([
            f("lower-case drive main", "Edit", f"/{drive}/{main[3:]}/src/x.cs", FX.wt, FX.main, "block"),
            f("lower-case drive worktree md", "Edit", f"/{drive}/{wt[3:]}/docs/x.md", FX.wt, FX.main, "allow"),
        ])

    @unittest.skipUnless(IS_WINDOWS, "Windows path spellings")
    def test_edit_driveless_rooted_path_blocks_instead_of_failing_open(self):
        main = posix(FX.main)
        self.run_cases([
            f("rooted forward slashes", "Edit", main[2:] + "/src/x.cs", FX.main, FX.main, "block"),
            f("rooted backslashes", "Edit", main[2:].replace("/", "\\") + "\\src\\x.cs", FX.wt, FX.main, "block"),
            f("worktree file allows", "Edit", FX.wt / "docs" / "x.md", FX.wt, FX.main, "allow"),
        ])

    def test_non_ascii_main_target_blocks(self):
        self.run_cases([
            f("Edit main e-acute file", "Edit", FX.main / "src" / "é.cs", FX.main, FX.main, "block"),
            f("Edit worktree e-acute md allows", "Edit", FX.wt / "docs" / "é.md", FX.wt, FX.main, "allow"),
        ])


# ===========================================================================
# Bash and PowerShell: spellings, rooted paths, write targets.
# ===========================================================================
class ShellSpellingTests(GuardTestCase):

    @unittest.skipUnless(IS_WINDOWS, "Windows path spellings")
    def test_bash_redirect_blocks_every_spelling_of_a_main_target(self):
        main, wt = posix(FX.main), posix(FX.wt)
        drive = main[0].lower()
        rows = [
            ("msys drive", f"/{drive}/{main[3:]}/src/x.cs"),
            ("mixed case", (main[:3] + main[3:].swapcase()) + "/src/x.cs"),
            ("worktree dot-dot to main", f"{wt}/../../../src/x.cs"),
            ("trailing dot", f"{main}/src./x.cs"),
            ("alternate stream", f"{main}/src/x.cs:stream"),
            ("plain forward", f"{main}/src/x.cs"),
        ]
        if FX.junction is not None:
            rows.append(("junction", posix(FX.junction) + "/src/x.cs"))
        if FX.short_main:
            rows.append(("8.3 short name", FX.short_main.replace("\\", "/") + "/src/x.cs"))
        cases = [sh(f"bash redirect {n}", "Bash", f"echo x > {p}", FX.wt, FX.main, "block") for n, p in rows]
        cases.append(sh("bash redirect worktree md", "Bash", f"echo x > {wt}/docs/x.md", FX.wt, FX.main, "allow"))
        self.run_cases(cases)

    @unittest.skipUnless(IS_WINDOWS, "Windows path spellings")
    def test_powershell_write_blocks_windows_spellings_of_a_main_target(self):
        main = FX.main
        rows = [
            ("backslashes", str(main / "src" / "x.cs")),
            ("mixed case", str(main).swapcase() + "\\src\\x.cs"),
            ("extended-length", "\\\\?\\" + str(main / "src" / "x.cs")),
            ("trailing dot", str(main) + "\\src.\\x.cs"),
            ("alternate stream", str(main / "src" / "x.cs") + ":stream"),
        ]
        cases = [sh(f"powershell Set-Content {n}", "PowerShell", f"Set-Content {p} x", FX.wt, FX.main, "block")
                 for n, p in rows]
        cases.append(sh("powershell Set-Content worktree md", "PowerShell",
                        f"Set-Content {FX.wt / 'docs' / 'x.md'} x", FX.wt, FX.main, "allow"))
        self.run_cases(cases)

    @unittest.skipUnless(IS_WINDOWS, "Windows path spellings")
    def test_driveless_rooted_targets_block_in_both_shells(self):
        main = posix(FX.main)[2:]
        self.run_cases([
            sh("PowerShell Set-Content driveless rooted", "PowerShell", f"Set-Content {main}/src/x.cs x", FX.main, FX.main, "block"),
            sh("Bash redirect driveless rooted", "Bash", f"echo x > {main}/x", FX.wt, FX.main, "block",
               contains=["write the path out in full"]),
            sh("Bash redirect /tmp allows", "Bash", "echo x > /tmp/x.md", FX.wt, FX.main, "allow"),
            sh("Bash redirect /dev/null allows", "Bash", "echo x > /dev/null", FX.wt, FX.main, "allow"),
            sh("PowerShell redirect to $null allows", "PowerShell", "Get-Date > $null", FX.wt, FX.main, "allow"),
        ])

    def test_unresolvable_targets_block_with_the_write_it_out_hint(self):
        self.run_cases([
            sh("Bash redirect to unset variable", "Bash", "echo x > $UNSET_ZZ_VARIABLE/x.md", FX.wt, FX.main, "block",
               contains=["write the path out in full"]),
            sh("Bash redirect to command substitution", "Bash", "echo x > $(pwd)/x.md", FX.wt, FX.main, "block",
               contains=["write the path out in full"]),
            sh("Bash redirect to a literal worktree md allows", "Bash", f"echo x > {posix(FX.wt)}/docs/x.md", FX.wt, FX.main, "allow"),
        ])


class WriteTargetKindTests(GuardTestCase):
    """Write target: each kind into main blocks, into a worktree allows."""

    def _bash_rows(self, base: str) -> list[tuple[str, str]]:
        return [
            ("redirect", f"echo x > {base}/n.md"),
            ("append", f"echo x >> {base}/n.md"),
            ("rm", f"rm {base}/n.md"),
            ("rmdir", f"rmdir {base}/newdir"),
            ("mkdir", f"mkdir {base}/newdir"),
            ("touch", f"touch {base}/n.md"),
            ("ln", f"ln -s a {base}/n.md"),
        ]

    def _ps_rows(self, base: str) -> list[tuple[str, str]]:
        return [
            ("redirect", f"Get-Date > {base}/n.md"),
            ("append", f"Get-Date >> {base}/n.md"),
            ("Set-Content", f"Set-Content {base}/n.md x"),
            ("Add-Content", f"Add-Content {base}/n.md x"),
            ("Clear-Content", f"Clear-Content {base}/n.md"),
            ("Out-File", f"Get-Date | Out-File {base}/n.md"),
            ("New-Item", f"New-Item {base}/n.md"),
            ("Remove-Item", f"Remove-Item {base}/n.md"),
            ("Copy-Item", f"Copy-Item a.md {base}/n.md"),
            ("Move-Item", f"Move-Item a.md {base}/n.md"),
            ("Rename-Item", f"Rename-Item {base}/o.md n.md"),
        ]

    def test_bash_write_targets_into_main_block_and_into_worktree_allow(self):
        cases = [sh(f"bash {n} into main", "Bash", c, FX.wt, FX.main, "block")
                 for n, c in self._bash_rows(posix(FX.main) + "/src")]
        cases += [sh(f"bash {n} into worktree", "Bash", c, FX.wt, FX.main, "allow")
                  for n, c in self._bash_rows(posix(FX.wt) + "/docs")]
        self.run_cases(cases)

    def test_powershell_write_targets_into_main_block_and_into_worktree_allow(self):
        cases = [sh(f"powershell {n} into main", "PowerShell", c, FX.wt, FX.main, "block")
                 for n, c in self._ps_rows(posix(FX.main) + "/src")]
        cases += [sh(f"powershell {n} into worktree", "PowerShell", c, FX.wt, FX.main, "allow")
                  for n, c in self._ps_rows(posix(FX.wt) + "/docs")]
        self.run_cases(cases)

    def test_git_worktree_add_allows_only_a_flat_path(self):
        main, wt = posix(FX.main), posix(FX.wt)
        flat = f"{main}/.claude/worktrees/20261008-flat-new"
        self.run_cases([
            sh("worktree add into src", "Bash", f"git worktree add {main}/src/x -b b1", FX.main, FX.main, "block"),
            sh("worktree add quoted variable", "Bash", 'git worktree add "$WT" -b b2', FX.main, FX.main, "block",
               contains=["write the path out in full"]),
            sh("worktree add nested in a worktree", "Bash", f"git worktree add {wt}/.claude/worktrees/inner -b b3",
               FX.main, FX.main, "block"),
            sh("worktree add flat path", "Bash", f"git worktree add {flat} -b b4", FX.main, FX.main, "allow"),
            sh("PowerShell worktree add flat path", "PowerShell", f"git worktree add {flat} -b b5", FX.main, FX.main, "allow"),
        ])


# ===========================================================================
# Git and gh command classes.
# ===========================================================================
class GitCommandClassTests(GuardTestCase):

    def _allow_list(self) -> list[str]:
        main, wt = posix(FX.main), posix(FX.wt)
        return [
            "git status", "git log --oneline -5", "git diff HEAD", "git show HEAD", "git fetch origin",
            "git push origin HEAD:refs/heads/x", "git branch -a", "git tag -l", "git rev-parse HEAD",
            "git rev-list HEAD", "git ls-files", "git ls-remote origin", "git ls-tree HEAD", "git cat-file -p HEAD",
            "git describe --always", "git shortlog -s", "git blame README.md", "git grep foo",
            "git merge-base HEAD HEAD", "git for-each-ref", "git name-rev HEAD", "git check-ignore x",
            "git remote -v", "git remote show origin", "git remote get-url origin", "git config --get user.name",
            "git config --get-all user.name", "git config --list", "git config -l", "git reflog show",
            "git stash list", "git stash show", "git worktree list", "git worktree prune",
            f"git worktree remove {wt}-gone", f"git -C {wt} commit -m x", "git --no-pager log",
            f"git worktree add {main}/.claude/worktrees/20261008-allow-list -b allowlist",
        ]

    def _block_list(self) -> list[str]:
        main = posix(FX.main)
        return [
            "git commit -m x", "git switch master", "git checkout master", "git stash push", "git stash",
            "git pull", "git merge origin/master", "git update-ref HEAD x", "git read-tree HEAD", "git branch -m a b",
            "git add .", "git reset --hard", "git co master", "git ci -m x",
            "git -c x=y status", f"git --git-dir={main}/.git status", "GIT_DIR=x git status",
            "git diff --output=x", "git log -o x", "git fetch --update-head-ok", "git fetch -u", "git grep -O foo",
        ]

    def test_bash_allow_list_allows_and_every_mutating_form_blocks(self):
        cases = [sh(f"bash block: {c}", "Bash", c, FX.main, FX.main, "block") for c in self._block_list()]
        cases += [sh(f"bash allow: {c}", "Bash", c, FX.main, FX.main, "allow") for c in self._allow_list()]
        self.run_cases(cases)

    def test_powershell_allow_list_allows_and_every_mutating_form_blocks(self):
        cases = [sh(f"powershell block: {c}", "PowerShell", c, FX.main, FX.main, "block") for c in self._block_list()]
        cases += [sh(f"powershell allow: {c}", "PowerShell", c, FX.main, FX.main, "allow") for c in self._allow_list()]
        self.run_cases(cases)

    def test_acting_directory_changes_into_main_block_a_commit(self):
        main, wt = posix(FX.main), posix(FX.wt)
        self.run_cases([
            sh("cd main then commit", "Bash", f"cd {main} && git commit -m x", FX.wt, FX.main, "block"),
            sh("pushd main then commit", "Bash", f"pushd {main} && git commit -m x", FX.wt, FX.main, "block"),
            sh("Set-Location main then commit", "PowerShell", f"Set-Location {main}; git commit -m x", FX.wt, FX.main, "block"),
            sh("popd then commit", "Bash", "popd && git commit -m x", FX.wt, FX.main, "block"),
            sh("bash -c nested from a main directory", "Bash", f'cd {main} && bash -c "git commit -m x"', FX.wt, FX.main, "block"),
            sh("eval git commit", "Bash", 'eval "git commit -m x"', FX.wt, FX.main, "block"),
            sh("git -C main commit", "Bash", f"git -C {main} commit -m x", FX.wt, FX.main, "block"),
            sh("commit in the worktree cwd allows", "Bash", "git commit -m x", FX.wt, FX.main, "allow"),
            sh("cd worktree then commit allows", "Bash", f"cd {wt} && git commit -m x", FX.main, FX.main, "allow"),
        ])


class FastForwardTests(GuardTestCase):
    """Open Question 5: exactly two fast-forward shapes pass in the main checkout."""

    def _rows(self) -> list[tuple[str, str]]:
        main = posix(FX.main)
        rows = [
            ("block", "git merge origin/master"), ("block", "git pull"),
            ("allow", "git merge --ff-only origin/master"), ("allow", "git pull --ff-only"),
            ("allow", "git pull --ff-only origin"), ("allow", "git pull --ff-only origin master"),
        ]
        for extra in ("--no-ff", "--rebase", "--squash", "--autostash"):
            rows.append(("block", f"git merge --ff-only origin/master {extra}"))
            rows.append(("block", f"git pull --ff-only origin master {extra}"))
        rows += [
            ("block", "git -c x=y merge --ff-only origin/master"), ("block", "git -c x=y pull --ff-only"),
            ("block", f"git -C {main} merge --ff-only origin/master"), ("block", f"git -C {main} pull --ff-only"),
            ("block", "git merge --ff-only origin/master other"), ("block", "git pull --ff-only origin master other"),
        ]
        return rows

    def test_bash_only_the_two_ff_only_shapes_pass(self):
        self.run_cases([sh(f"bash {e}: {c}", "Bash", c, FX.main, FX.main, e) for e, c in self._rows()])

    def test_powershell_only_the_two_ff_only_shapes_pass(self):
        self.run_cases([sh(f"powershell {e}: {c}", "PowerShell", c, FX.main, FX.main, e) for e, c in self._rows()])


class KeywordAndGrouperTests(GuardTestCase):
    """Git invocation: keywords, groupers, `&`, unparseable segments (fail closed)."""

    def test_bash_keywords_and_groupers_cannot_hide_a_commit(self):
        m = FX.main
        rows = [
            ("block", "if ! git diff --quiet; then git commit -am x; fi"), ("block", "{ git commit; }"),
            ("block", "( git commit )"), ("block", "for f in a; do git add $f; done"),
            ("block", "while true; do git commit; done"), ("block", "until false; do git commit; done"),
            ("block", "true && ! git commit"), ("block", "time git commit"), ("block", "sleep 1 & git commit"),
            ("block", "case x in *) git commit;; esac"), ("block", "{ git commit"), ("block", "f() { git commit; }"),
            ("allow", "if git diff --quiet; then git status; fi"),
        ]
        self.run_cases([sh(f"bash {e}: {c}", "Bash", c, m, m, e) for e, c in rows])

    def test_powershell_keywords_and_groupers_cannot_hide_a_commit(self):
        m = FX.main
        rows = [
            ("block", "if ($x) { git commit }"), ("block", "if (git diff --quiet) { } else { git commit }"),
            ("block", "foreach ($f in $a) { git add $f }"), ("block", "while ($true) { git commit }"),
            ("block", "{ git commit }"), ("block", "& git commit"), ("block", "& 'git' commit"),
            ("block", ".\\git commit"), ("allow", "git status"),
        ]
        self.run_cases([sh(f"powershell {e}: {c}", "PowerShell", c, m, m, e) for e, c in rows])


class GhCommandClassTests(GuardTestCase):

    def _mutating(self) -> list[str]:
        return ["gh pr checkout 5", "gh pr merge 5 -d", "gh pr merge 5 --delete-branch", "gh issue develop 5 -c",
                "gh issue develop 5 --checkout", "gh repo sync", "gh repo clone o/r", "gh release download v1",
                "gh run download 1", "gh gist clone abc"]

    def test_each_mutating_gh_member_blocks_in_both_shells(self):
        m = FX.main
        cases = [sh(f"bash {c}", "Bash", c, m, m, "block") for c in self._mutating()]
        cases += [sh(f"powershell {c}", "PowerShell", c, m, m, "block") for c in self._mutating()]
        cases += [sh(f"bash allow {c}", "Bash", c, m, m, "allow") for c in ("gh pr view 5", "gh issue list", "gh run list")]
        self.run_cases(cases)

    def test_gh_member_blocks_after_each_keyword_and_grouper(self):
        m = FX.main
        rows = [
            ("Bash", "if true; then gh pr checkout 5; fi"), ("Bash", "{ gh pr checkout 5; }"),
            ("Bash", "for f in a; do gh pr checkout 5; done"), ("Bash", "! gh pr checkout 5"),
            ("PowerShell", "if ($true) { gh pr checkout 5 }"),
        ]
        cases = [sh(f"{t}: {c}", t, c, m, m, "block") for t, c in rows]
        cases.append(sh("Bash: if true; then gh pr view 5; fi", "Bash", "if true; then gh pr view 5; fi", m, m, "allow"))
        self.run_cases(cases)


class DirectoryLeftBehindTests(GuardTestCase):

    def test_changing_into_main_blocks_even_when_every_segment_is_a_read(self):
        main = posix(FX.main)
        self.run_cases([
            sh("cd main alone", "Bash", f"cd {main}", FX.wt, FX.main, "block", contains=["git -C"]),
            sh("cd main then git status", "Bash", f"cd {main} && git status", FX.wt, FX.main, "block"),
            sh("PowerShell Set-Location main alone", "PowerShell", f"Set-Location {main}", FX.wt, FX.main, "block"),
            sh("subshell cd main then git status", "Bash", f"(cd {main} && git status)", FX.wt, FX.main, "allow"),
            sh("git -C main status", "Bash", f"git -C {main} status", FX.wt, FX.main, "allow"),
        ])


class OffSwitchTests(GuardTestCase):
    """The existing off switches run after the guard: they never switch the guard off."""

    def test_concept_gate_off_still_blocks_a_main_edit(self):
        env = {"CLAUDE_CONCEPT_GATE": "off"}
        self.run_cases([
            f("Edit main with CLAUDE_CONCEPT_GATE=off", "Edit", FX.main / "src" / "x.cs", FX.main, FX.main, "block", extra_env=env),
            f("Edit worktree md with CLAUDE_CONCEPT_GATE=off", "Edit", FX.wt / "docs" / "x.md", FX.wt, FX.main, "allow", extra_env=env),
        ])

    def test_bash_gate_off_still_blocks_a_main_commit(self):
        env = {"CLAUDE_BASH_GATE": "off"}
        self.run_cases([
            sh("git commit in main with CLAUDE_BASH_GATE=off", "Bash", "git commit -m x", FX.main, FX.main, "block", extra_env=env),
            sh("git status in main with CLAUDE_BASH_GATE=off", "Bash", "git status", FX.main, FX.main, "allow", extra_env=env),
        ])

    def test_both_switches_together_still_block(self):
        env = {"CLAUDE_BASH_GATE": "off", "CLAUDE_CONCEPT_GATE": "off"}
        self.run_cases([
            f("Edit main with both off", "Edit", FX.main / "src" / "x.cs", FX.main, FX.main, "block", extra_env=env),
            sh("Bash write main with both off", "Bash", f"echo x > {posix(FX.main)}/src/x.cs", FX.wt, FX.main, "block", extra_env=env),
            f("Edit worktree md with both off", "Edit", FX.wt / "docs" / "x.md", FX.wt, FX.main, "allow", extra_env=env),
        ])


class BlockBannerTests(GuardTestCase):
    """I-6: every banner holds both remedy lines and 'BLOCKED: main checkout'."""

    def test_every_banner_names_both_remedies(self):
        main = posix(FX.main)
        cases = [
            f("Edit main", "Edit", FX.main / "src" / "x.cs", FX.main, FX.main, "block"),
            sh("Bash redirect main", "Bash", f"echo x > {main}/src/x.cs", FX.wt, FX.main, "block"),
            sh("git commit in main", "Bash", "git commit -m x", FX.main, FX.main, "block"),
            sh("gh pr checkout in main", "Bash", "gh pr checkout 5", FX.main, FX.main, "block"),
            sh("unresolvable target", "Bash", "echo x > $UNSET_ZZ_VARIABLE/x.md", FX.wt, FX.main, "block"),
        ]
        if any(needs_missing_bash_gate(c.gate) for c in cases):
            self.skipTest(BASH_GATE_SKIP_REASON)
        results = [launch(c.payload, gate=c.gate, project=c.project) for c in cases]
        for case, res in zip(cases, results):
            with self.subTest(case.name):
                self._expect_block(res)
                for text in ("/task", "EnterWorktree", "do not retry", "BLOCKED: main checkout"):
                    self.assertIn(text, res.err, msg=f"I-6: every banner must hold {text!r} (session remedy, then "
                                                      "subagent remedy line)")


# ===========================================================================
# Launcher edges (I-2, I-3).
# ===========================================================================
class LauncherInputEdgeTests(GuardTestCase):

    def test_invalid_input_and_unknown_gate_exit_2(self):
        good = file_payload("Edit", str(FX.wt / "docs" / "x.md"), FX.wt)
        results = {
            "payload is not JSON": launch(b"this is not json{", project=FX.main),
            "payload is a JSON list": launch(json.dumps([1, 2]).encode(), project=FX.main),
            "stdin is not valid UTF-8": launch(b"\xff\xfe{\"tool_name\":\"Edit\"}", project=FX.main),
            "unknown gate argument": launch(good, gate=HOOKS_DIR / "architecture-guard.py", project=FX.main),
            "gate argument that is no gate": launch(good, gate_arg=str(HOOKS_DIR / "not-a-gate.py"), project=FX.main),
        }
        for name, res in results.items():
            with self.subTest(name):
                self._expect_block(res)
        self._expect_allow(launch(good, project=FX.main))

    def test_non_ascii_payload_reaches_the_gate_byte_identically(self):
        main_block = launch(file_payload("Edit", str(FX.main / "src" / "é.cs"), FX.main), project=FX.main)
        self._expect_block(main_block)
        payload = json.dumps(file_payload("Edit", str(FX.wt / "docs" / "é.md"), FX.wt), ensure_ascii=False).encode("utf-8")
        via = launch(payload, project=FX.main)
        direct_env = clean_env({"PYTHONIOENCODING": "utf-8", "CLAUDE_PROJECT_DIR": str(FX.main)})
        direct = subprocess.run([sys.executable, str(CONCEPT_GATE)], input=payload, capture_output=True, env=direct_env, timeout=90)
        self._expect_allow(via)
        self.assertEqual((via.rc, via.out, via.err_bytes), (direct.returncode, direct.stdout, direct.stderr),
                         msg="I-2: an allowing payload holding a non-ASCII character must give the SAME exit, stdout "
                             "and stderr bytes through the launcher and directly with PYTHONIOENCODING=utf-8")


class LauncherSourceShapeTests(unittest.TestCase):
    """I-3: the stub is tiny and stdlib-only; the body is bounded; both compile."""

    def _imports(self, path: Path, *, top_only: bool = False) -> set[str]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        nodes = tree.body if top_only else list(ast.walk(tree))
        names: set[str] = set()
        for n in nodes:
            if isinstance(n, ast.Import):
                names.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module:
                names.add(n.module.split(".")[0])
        return names

    @staticmethod
    def _compile(path: Path) -> None:
        """Compile into a throwaway output file (os.devnull is refused on Windows); raises on a syntax error."""
        with tempfile.TemporaryDirectory() as tmp:
            py_compile.compile(str(path), cfile=os.path.join(tmp, "out.pyc"), doraise=True)

    def test_stub_exists_compiles_and_stays_small(self):
        self.assertTrue(LAUNCHER.is_file(), msg=f"{LAUNCHER} must exist (the registered launcher stub)")
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "broken.py"
            broken.write_text("def (:\n", encoding="utf-8")
            with self.assertRaises(py_compile.PyCompileError,
                                   msg="control: a file with a syntax error must make the compile step raise"):
                self._compile(broken)
        self._compile(LAUNCHER)
        lines = LAUNCHER.read_text(encoding="utf-8").splitlines()
        self.assertLess(len(lines), 15, msg="I-3: the stub is under 15 lines")
        self.assertLessEqual(self._imports(LAUNCHER, top_only=True), {"sys", "os"},
                             msg="I-3: the stub's module-level imports are sys and os only")
        tree = ast.parse(LAUNCHER.read_text(encoding="utf-8"))
        self.assertTrue(any(isinstance(n, ast.Try) for n in tree.body),
                        msg="I-2: the stub is one try that imports and runs the body, so any failure is exit 2")

    def test_body_exists_compiles_and_imports_only_the_allowed_modules(self):
        self.assertTrue(LAUNCHER_BODY.is_file(), msg=f"{LAUNCHER_BODY} must exist (the launcher body)")
        self._compile(LAUNCHER_BODY)
        lines = LAUNCHER_BODY.read_text(encoding="utf-8").splitlines()
        self.assertLess(len(lines), 120, msg="I-3: the body stays under 120 lines")
        allowed = {"sys", "os", "io", "json", "runpy", "traceback", "_main_checkout_guard"}
        self.assertLessEqual(self._imports(LAUNCHER_BODY), allowed,
                             msg="I-3: the body imports only sys, os, io, json, runpy, traceback (plus the guard "
                                 "module it calls); no subprocess")


class LauncherFailureTests(GuardTestCase):
    """I-3: any failure in the launcher's own code exits 2 and never runs the gate."""

    def _copy(self, label: str, **kw) -> Path:
        base = {"concept-gate.py": GATE_MARKER_BODY}
        base.update(kw.pop("overwrite", {}))
        return make_hooks_copy(label, overwrite=base, **kw)

    def _allow_payload(self) -> dict:
        return file_payload("Edit", str(FX.wt / "docs" / "x.md"), FX.wt)

    def test_guard_copy_that_calls_sys_exit_blocks_as_launcher_failed_and_skips_the_gate(self):
        for code in (0, 1):
            hooks = self._copy(f"guard_exit{code}", overwrite={
                "_main_checkout_guard.py": f"import sys\n\ndef decide(*a, **k):\n    sys.exit({code})\n"})
            marker = hooks / "gate_ran.marker"
            with self.subTest(f"decide calls sys.exit({code})"):
                res = launch(self._allow_payload(), hooks_dir=hooks, project=FX.main)
                self._expect_block(res, contains=["launcher failed"])
                self.assertFalse(marker.exists(), msg="the gate must not run after the launcher failed")

    def test_guard_that_returns_a_non_verdict_blocks(self):
        hooks = self._copy("guard_nonverdict", overwrite={
            "_main_checkout_guard.py": "def decide(*a, **k):\n    return 42\n"})
        res = launch(self._allow_payload(), hooks_dir=hooks, project=FX.main)
        self._expect_block(res)
        self.assertFalse((hooks / "gate_ran.marker").exists(), msg="a non-verdict must never reach the gate")

    def test_body_that_raises_before_its_decision_blocks(self):
        self.assertTrue(LAUNCHER_BODY.is_file(), msg=f"{LAUNCHER_BODY} must exist to be copied with an injected failure")
        text = LAUNCHER_BODY.read_text(encoding="utf-8")
        injected, count = re.subn(r"(def main\([^)]*\)[^:\n]*:\n)", r'\1    raise RuntimeError("injected")\n', text, count=1)
        self.assertEqual(count, 1, msg="the body must define main(), where the failure is injected")
        hooks = self._copy("body_raises", overwrite={"_gate_launch.py": injected})
        res = launch(self._allow_payload(), hooks_dir=hooks, project=FX.main)
        self._expect_block(res)
        self.assertFalse((hooks / "gate_ran.marker").exists(), msg="the gate must not run when the body raised")

    def test_body_deleted_or_with_a_syntax_error_blocks_through_the_stub_fallback(self):
        deleted = self._copy("body_deleted", delete=("_gate_launch.py",))
        broken = self._copy("body_syntax", overwrite={"_gate_launch.py": "def main(:\n    pass\n"})
        for name, hooks in (("_gate_launch.py deleted", deleted), ("_gate_launch.py syntax error", broken)):
            with self.subTest(name):
                res = launch(self._allow_payload(), hooks_dir=hooks, project=FX.main)
                self._expect_block(res)
                self.assertFalse((hooks / "gate_ran.marker").exists(), msg="the gate must not run")

    def test_named_gate_file_deleted_blocks(self):
        hooks = self._copy("gate_deleted", delete=("concept-gate.py",))
        res = launch(self._allow_payload(), hooks_dir=hooks, gate_arg=str(hooks / "concept-gate.py"), project=FX.main)
        self.assertEqual(res.rc, 2, msg=f"a missing gate file must exit 2 as a direct launch of a missing file does: {res.describe()}")
        self.assertTrue(LAUNCHER.is_file(), msg="the launcher itself must exist for this row to mean anything")


class GatePassThroughTests(GuardTestCase):
    """I-3: after ALLOW the gate's own exit code stands."""

    def _gate_copy(self, label: str, gate_text: str) -> Path:
        return make_hooks_copy(label, overwrite={"concept-gate.py": GATE_MARKER_BODY + gate_text})

    def test_gate_exit_codes_pass_through_after_allow(self):
        allow_payload = file_payload("Edit", str(FX.wt / "docs" / "x.md"), FX.wt)
        block_payload = file_payload("Edit", str(FX.main / "src" / "x.cs"), FX.main)
        rows = [
            ("gate exits 2", "import sys\nsys.stderr.write('GATE-OWN-BLOCK')\nsys.exit(2)\n", 2, "GATE-OWN-BLOCK"),
            ("gate exits 0", "import sys\nsys.exit(0)\n", 0, ""),
            ("gate exits 1", "import sys\nsys.exit(1)\n", 1, ""),
            ("gate has a syntax error", "def (:\n", 1, ""),
            ("gate raises", "raise RuntimeError('gate boom')\n", 1, "gate boom"),
        ]
        for name, text, want_rc, want_err in rows:
            hooks = self._gate_copy("passthrough", text)
            syntax_error = name == "gate has a syntax error"
            if syntax_error:  # nothing of a file that fails to compile runs, so no marker is written
                (hooks / "concept-gate.py").write_text(text, encoding="utf-8")
            with self.subTest(name):
                self._block_ok = False
                blocked = launch(block_payload, hooks_dir=hooks, project=FX.main)
                self._expect_block(blocked)
                self.assertFalse((hooks / "gate_ran.marker").exists(), msg="a guard block must precede the gate: it never ran")
                res = launch(allow_payload, hooks_dir=hooks, project=FX.main)
                self.assertTrue(self._block_ok, msg="same-run BLOCK sibling confirmed first")
                if not syntax_error:
                    self.assertTrue((hooks / "gate_ran.marker").exists(), msg="after allow the launcher must run the gate")
                self.assertIn(res.rc, (want_rc,), msg="exit code check precedes the stderr check")
                self.assertEqual(res.rc, want_rc, msg=f"{name}: the gate's own exit code stands: {res.describe()}")
                self.assertNotIn(MARKER, res.err, msg="an allowed call carries no guard banner")
                if want_err:
                    self.assertIn(want_err, res.err, msg="the gate's own stderr reaches the caller")


class MisregistrationTests(GuardTestCase):
    """I-3: a gate argument from another folder blocks loudly; the same folder through a junction runs."""

    def test_gate_from_a_second_folder_blocks_as_misregistered(self):
        other = FX.root / "other_hooks"
        other.mkdir(exist_ok=True)
        shutil.copy2(CONCEPT_GATE, other / "concept-gate.py")
        allow_payload = file_payload("Edit", str(FX.wt / "docs" / "x.md"), FX.wt)
        literal = "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/concept-gate.py"
        for name, arg, folder in (("identical copy outside the launcher folder", str(other / "concept-gate.py"), str(other)),
                                  ("unexpanded plugin root text", literal, "${CLAUDE_PLUGIN_ROOT}")):
            with self.subTest(name):
                res = launch(allow_payload, gate_arg=arg, project=FX.main)
                self._expect_block(res, contains=["launcher misregistered", "auto_improve_finish_install.py"])
                norm = res.err.replace("\\", "/").lower()
                self.assertIn(posix(HOOKS_DIR).lower(), norm, msg="the banner names the launcher's own folder")
                self.assertIn(folder.replace("\\", "/").lower(), norm, msg="the banner names the gate's folder")

    @unittest.skipUnless(IS_WINDOWS, "junction rows are Windows-only")
    def test_gate_reached_through_a_junction_to_its_own_folder_runs(self):
        link = FX.root / "junction_to_hooks"
        proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(HOOKS_DIR)], capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"SKIP junction-to-hooks row: this machine refused to create a junction: {proc.stdout.strip()}", file=sys.stderr)
            self.skipTest("this machine refused to create a junction")
        try:
            allow_payload = file_payload("Edit", str(FX.wt / "docs" / "x.md"), FX.wt)
            blocked = launch(allow_payload, gate_arg=str(FX.root / "other_hooks" / "concept-gate.py"), project=FX.main)
            self._expect_block(blocked, contains=["launcher misregistered"])
            res = launch(allow_payload, gate_arg=str(link / "concept-gate.py"), project=FX.main)
            self._expect_allow(res)
        finally:
            os.rmdir(link)


# ===========================================================================
# Degraded mode (guard missing, lacking decide, raising, syntax error).
# ===========================================================================
class DegradedGuardTests(GuardTestCase):
    VARIANTS = {
        "guard deleted": {"delete": ("_main_checkout_guard.py",)},
        "guard lacks decide": {"overwrite": {"_main_checkout_guard.py": "VALUE = 1\n"}},
        "guard raises on import": {"overwrite": {"_main_checkout_guard.py": "raise RuntimeError('boom')\n"}},
        "guard has a syntax error": {"overwrite": {"_main_checkout_guard.py": "def decide(:\n"}},
    }

    def _hooks(self, label: str, variant: dict) -> Path:
        return make_hooks_copy(label, **variant)

    def test_main_blocks_as_guard_degraded_worktree_file_allows_and_one_log_line_is_written(self):
        for name, variant in self.VARIANTS.items():
            hooks = self._hooks("degraded", variant)
            with self.subTest(name):
                self._block_ok = False
                before = error_log_lines()
                res = launch(file_payload("Edit", str(FX.main / "src" / "x.cs"), FX.main), hooks_dir=hooks, project=FX.main)
                self._expect_block(res, contains=["guard degraded"])
                self.assertEqual(error_log_lines() - before, 1,
                                 msg="a degraded block writes exactly one errors.jsonl line "
                                     "(<project>/.claude/logs/errors.jsonl, the project-local logs_dir())")
                self._expect_allow(launch(file_payload("Edit", str(FX.wt / "docs" / "x.md"), FX.wt), hooks_dir=hooks, project=FX.main))

    def test_degraded_spelling_rows(self):
        hooks = self._hooks("degraded_rows", self.VARIANTS["guard deleted"])
        main, wt = posix(FX.main), posix(FX.wt)
        extra: list[Case] = []
        link = FX.wt / "junction_inside"
        if IS_WINDOWS and not link.exists():
            proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(FX.main)], capture_output=True, text=True)
            if proc.returncode == 0:
                extra.append(f("degraded: junction from a worktree path into main", "Edit",
                               link / "src" / "a.cs", FX.wt, FX.main, "block", hooks_dir=hooks))
            else:
                print(f"SKIP degraded junction row: {proc.stdout.strip()}", file=sys.stderr)
        cases = [
            f("degraded: dot-dot out of the worktree into main", "Edit", f"{wt}/../../../src/a.cs", FX.wt, FX.main, "block", hooks_dir=hooks),
            sh("degraded: cd main then commit", "Bash", f"cd {main} && git commit -m x", FX.wt, FX.main, "block", hooks_dir=hooks),
            sh("degraded: git -C main commit", "Bash", f"git -C {main} commit -m x", FX.wt, FX.main, "block", hooks_dir=hooks),
            sh("degraded: worktree add into src", "Bash", f"git worktree add {main}/src/x", FX.wt, FX.main, "block", hooks_dir=hooks),
            sh("degraded: gh pr create from a worktree", "Bash", "gh pr create --title t --body b", FX.wt, FX.main, "block", hooks_dir=hooks),
            sh("degraded: flat worktree add", "Bash", f"git worktree add {main}/.claude/worktrees/20261008-degraded-flat -b degraded1",
               FX.wt, FX.main, "allow", hooks_dir=hooks),
            f("degraded: worktree md edit", "Edit", FX.wt / "docs" / "x.md", FX.wt, FX.main, "allow", hooks_dir=hooks),
        ] + extra
        self.run_cases(cases)


if __name__ == "__main__":
    unittest.main(verbosity=2)
