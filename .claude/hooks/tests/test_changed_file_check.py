#!/usr/bin/env python3
"""test_changed_file_check.py -- RED suite for ``concept_changed_check.py`` (the Changed-file check).

Contract: .claude/concepts/2026-10-12-dedupe-claude-config.md in the consuming repository, Revision 3
(Data Shapes: Changed-file baseline; Commands: Check changed files) and Revision 4 (round-four findings 7
and 8), block 16.

WHAT THE CHECK IS
-----------------
The default enforcement of the concept rule for shell commands. Instead of reading each command before it
runs, it asks git, once per turn (inside the Stop dispatcher) and once per commit (``--staged``), which
files changed, and judges each one through ``concept-gate.py``'s own ``resolve_target``. Its result is one
Guard Outcome: clean, noted or stopped.

  * stopped  exit 2, the file list on stderr after one fixed paragraph, plus the concept gate's next steps;
  * noted    exit 0 and one ``systemMessage`` on stdout naming the files;
  * clean    exit 0 and nothing said.

HOW THE ROWS ARE BUILT
----------------------
Every row builds its own temporary git repository from one template (a copy of the real hooks and scripts
committed with a clean tree), runs the REAL check as a subprocess with a Stop payload on stdin, and reads
the exit code, stdout and stderr. The system temporary folder (where the baseline and the "already stopped
for" memory live) is redirected per row, so no row sees another row's session. The baseline round trip uses
the REAL ``working-agreements.py`` SessionStart path and the REAL check; no row writes a baseline by hand
except the one that corrupts it on purpose.

EACH ROW CAN FAIL. A "clean" row also holds an uncovered file that must still stop (so an always-clean check
fails it); a "stopped" row names a covered or trivial sibling that must NOT be listed (so an always-stop check
fails it).

Narrow readings this file takes (the contract leaves them open):
  * a noted outcome is a JSON object with a ``systemMessage`` string on stdout, exit 0;
  * the baseline is a file in the system temporary folder whose name starts with
    ``auto-improve-changed-baseline-`` and contains the session id (decision 2 of the block 2 review);
  * "lists only the new files" means the stop text on stderr names the new file and does not name an
    earlier one;
  * the check logs to ``<project>/.claude/logs/errors.jsonl`` with hook name ``concept-changed-check``.

RED TODAY: ``concept_changed_check.py`` does not exist yet (block 17 adds it), so every row fails with a
message that says so. Nothing is imported from it.

Run:
    py -3 .claude/hooks/tests/test_changed_file_check.py
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
import zipfile
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = HOOKS_DIR.parent / "scripts"
CHECK = "concept_changed_check.py"
IS_WINDOWS = os.name == "nt"

BASELINE_PREFIX = "auto-improve-changed-baseline-"
FIXED_PARAGRAPH = (
    "These files changed in this working tree during this session and no approved contract covers them. "
    "A person editing in another program, or another session in the same tree, may have written some of "
    "them. If you did not write a file, tell the user which ones and do not edit or revert them; for the "
    "files you wrote, run /design-first or pin the contract that covers them."
)


def squash(text: str) -> str:
    """Whitespace folded, so a wrapped paragraph still compares equal."""
    return " ".join(text.split())


def token() -> str:
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Git helpers (a temporary repository per row; nothing touches a real repository).
# ---------------------------------------------------------------------------
def clean_env(extra: dict | None = None) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and not k.startswith("CLAUDE_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if extra:
        env.update(extra)
    return env


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
        cwd=str(cwd), env=clean_env(), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and proc.returncode != 0:
        raise RuntimeError("fixture git %s failed in %s: %s" % (" ".join(args), cwd, proc.stderr.strip()))
    return proc


def write_contract(path: Path, files: list[str], status: str = "approved") -> Path:
    """A contract the gate's own parser reads: the bold 'Files to touch:' marker, not a heading."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join("- `%s`" % f for f in files)
    path.write_text(
        "# Concept Contract - fixture\n\n**Status:** %s\n\n## Implementation Handoff\n\n"
        "**Files to touch:**\n%s\n\n## Next section\n\nprose\n" % (status, body), encoding="utf-8")
    return path


def assert_fixture_outside_claude_folder(test: unittest.TestCase, root: Path) -> None:
    """FAIL (never skip) when any part of the fixture's root path is named .claude.

    The concept gate treats every path holding a .claude segment as trivial, so a probe placed under such a
    folder reads clean by construction. The project's own .claude folder (below the root) is the only one
    allowed, so only the root and the folders above it are looked at.
    """
    parts = Path(os.path.realpath(str(root))).parts
    test.assertNotIn(".claude", [part.lower() for part in parts],
                     msg="fixture root %s sits under a .claude folder; a probe there is clean by construction "
                         "(point TEMP somewhere else)" % root)


class Template:
    root: Path | None = None
    project: Path | None = None


TEMPLATE = Template()


def setUpModule() -> None:
    TEMPLATE.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="cfc_template_")))
    TEMPLATE.project = TEMPLATE.root / "project"
    hooks = TEMPLATE.project / ".claude" / "hooks"
    scripts = TEMPLATE.project / ".claude" / "scripts"
    hooks.mkdir(parents=True)
    scripts.mkdir(parents=True)
    for item in HOOKS_DIR.iterdir():
        if item.is_file() and item.suffix in (".py", ".json") and item.name != "bash-gate.py":
            shutil.copyfile(item, hooks / item.name)
    for item in SCRIPTS_DIR.glob("*.py"):
        shutil.copyfile(item, scripts / item.name)
    (TEMPLATE.project / ".claude" / "concepts").mkdir()
    (TEMPLATE.project / ".claude" / "concepts" / ".gitkeep").write_text("", encoding="utf-8")
    (TEMPLATE.project / "src").mkdir()
    (TEMPLATE.project / "src" / ".gitkeep").write_text("", encoding="utf-8")
    (TEMPLATE.project / "README.md").write_text("fixture\n", encoding="utf-8")
    (TEMPLATE.project / ".gitignore").write_text(".claude/worktrees/\n.claude/cache/\n.claude/logs/\n",
                                                 encoding="utf-8")
    (TEMPLATE.project / ".gitattributes").write_text("src/gen/** linguist-generated\n", encoding="utf-8")
    git(TEMPLATE.project, "init", "-q")
    git(TEMPLATE.project, "symbolic-ref", "HEAD", "refs/heads/master")
    git(TEMPLATE.project, "add", "-A")
    git(TEMPLATE.project, "commit", "-q", "-m", "fixture")


def tearDownModule() -> None:
    def _onerror(func, path, _exc):
        try:
            os.chmod(path, 0o700)
            func(path)
        except OSError:
            pass
    if TEMPLATE.root is not None:
        shutil.rmtree(TEMPLATE.root, onerror=_onerror)


class Result:
    def __init__(self, rc: int, out: str, err: str):
        self.rc, self.out, self.err = rc, out, err

    def describe(self) -> str:
        return "exit=%s stdout=%r stderr=%r" % (self.rc, self.out[:400], self.err[:600])

    def message(self) -> str:
        """The systemMessage on stdout, or '' when there is none."""
        text = self.out.strip()
        if not text:
            return ""
        try:
            data = json.loads(text)
        except ValueError:
            return ""
        return data.get("systemMessage", "") if isinstance(data, dict) and isinstance(
            data.get("systemMessage", ""), str) else ""


class Project:
    """One temporary copy of the template repository, with its own home, temp folder and bin folder."""

    def __init__(self, test: unittest.TestCase):
        if TEMPLATE.project is None:
            raise AssertionError("template missing")
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="cfc_row_")))
        test.addCleanup(self._remove)
        assert_fixture_outside_claude_folder(test, self.root)
        self.project = self.root / "project"
        shutil.copytree(TEMPLATE.project, self.project)
        # The hook error log writes only when the project's logs folder exists (it never creates it).
        (self.project / ".claude" / "logs").mkdir(parents=True, exist_ok=True)
        self.temp = self.root / "temp"
        self.home = self.root / "home"
        self.temp.mkdir()
        self.home.mkdir()
        self.session = "sess-" + token()
        self.hooks = self.project / ".claude" / "hooks"

    def _remove(self) -> None:
        def _onerror(func, path, _exc):
            try:
                os.chmod(path, 0o700)
                func(path)
            except OSError:
                pass
        shutil.rmtree(self.root, onerror=_onerror)

    # -- files -------------------------------------------------------------
    def write(self, rel: str, text: str = "content\n", base: Path | None = None) -> Path:
        path = (base or self.project) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit_file(self, rel: str, text: str = "committed\n") -> Path:
        path = self.write(rel, text)
        git(self.project, "add", "--", rel)
        git(self.project, "commit", "-q", "-m", "add " + rel)
        return path

    def contract(self, files: list[str], name: str | None = None, status: str = "approved",
                 base: Path | None = None) -> Path:
        return write_contract((base or self.project) / ".claude" / "concepts" / (name or "c-%s.md" % token()),
                              files, status)

    # -- running -----------------------------------------------------------
    def env(self, extra: dict | None = None, project_dir: Path | None = None) -> dict:
        env = clean_env({
            "CLAUDE_PROJECT_DIR": str(project_dir or self.project),
            "HOME": str(self.home), "USERPROFILE": str(self.home),
            "TEMP": str(self.temp), "TMP": str(self.temp), "TMPDIR": str(self.temp),
        })
        if extra:
            for key, value in extra.items():
                if value is None:
                    env.pop(key, None)
                else:
                    env[key] = value
        return env

    def check_path(self) -> Path:
        path = self.project / ".claude" / "scripts" / CHECK
        if not path.is_file():
            raise AssertionError("%s does not exist yet (block 17 adds the Changed-file check)" % path)
        return path

    def run_check(self, *, session: str | None = None, cwd: Path | None = None, stop_hook_active: bool = False,
                  args: tuple = (), env: dict | None = None, project_dir: Path | None = None,
                  payload: dict | None = None, stdin: bytes | None = None, timeout: int = 60) -> Result:
        script = self.check_path()
        body = payload if payload is not None else {
            "session_id": session or self.session, "cwd": str(cwd or self.project),
            "stop_hook_active": stop_hook_active, "hook_event_name": "Stop"}
        data = stdin if stdin is not None else (b"" if args else json.dumps(body).encode("utf-8"))
        proc = subprocess.run([sys.executable, "-B", str(script), *args], input=data, capture_output=True,
                              cwd=str(cwd or self.project), env=self.env(env, project_dir), timeout=timeout)
        return Result(proc.returncode, proc.stdout.decode("utf-8", "replace"),
                      proc.stderr.decode("utf-8", "replace"))

    def start_session(self, source: str | None, *, session: str | None = None, cwd: Path | None = None):
        """The REAL SessionStart hook, from this project's copy of the hooks."""
        body = {"session_id": session or self.session, "cwd": str(cwd or self.project),
                "hook_event_name": "SessionStart"}
        if source is not None:
            body["source"] = source
        proc = subprocess.run([sys.executable, "-B", str(self.hooks / "working-agreements.py")],
                              input=json.dumps(body).encode("utf-8"), capture_output=True,
                              cwd=str(cwd or self.project), env=self.env(), timeout=60)
        return proc

    def run_gate(self, target: Path) -> int:
        """The concept gate as a PreToolUse Write payload; returns its exit code."""
        body = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": "x"},
                "cwd": str(self.project)}
        proc = subprocess.run([sys.executable, "-B", str(self.hooks / "concept-gate.py")],
                              input=json.dumps(body).encode("utf-8"), capture_output=True,
                              cwd=str(self.project), env=self.env(), timeout=60)
        return proc.returncode

    def gate_stderr(self, target: Path) -> str:
        body = {"tool_name": "Write", "tool_input": {"file_path": str(target), "content": "x"},
                "cwd": str(self.project)}
        proc = subprocess.run([sys.executable, "-B", str(self.hooks / "concept-gate.py")],
                              input=json.dumps(body).encode("utf-8"), capture_output=True,
                              cwd=str(self.project), env=self.env(), timeout=60)
        return proc.stderr.decode("utf-8", "replace")

    # -- observations ------------------------------------------------------
    def baseline_files(self, session: str | None = None) -> list[Path]:
        sid = session or self.session
        return sorted(p for p in self.temp.iterdir()
                      if p.name.startswith(BASELINE_PREFIX) and sid in p.name)

    def error_lines(self) -> list[dict]:
        log = self.project / ".claude" / "logs" / "errors.jsonl"
        if not log.is_file():
            return []
        rows = []
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("hook") == "concept-changed-check":
                rows.append(row)
        return rows


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.p = Project(self)

    def assertStopped(self, res: Result, *named: str, absent: tuple = ()) -> None:
        self.assertEqual(res.rc, 2, msg="must STOP the turn (exit 2): " + res.describe())
        for name in named:
            self.assertIn(name, res.err, msg="the stop must name %s: %s" % (name, res.describe()))
        for name in absent:
            self.assertNotIn(name, res.err, msg="the stop must NOT name %s: %s" % (name, res.describe()))

    def assertClean(self, res: Result) -> None:
        self.assertEqual(res.rc, 0, msg="must be clean (exit 0): " + res.describe())
        self.assertNotIn(FIXED_PARAGRAPH[:40], squash(res.err), msg="clean does not stop: " + res.describe())
        self.assertEqual(res.out.strip(), "", msg="clean says nothing on stdout: " + res.describe())

    def assertNoted(self, res: Result, *named: str) -> None:
        self.assertEqual(res.rc, 0, msg="noted exits 0: " + res.describe())
        message = res.message()
        self.assertTrue(message, msg="noted is one systemMessage on stdout: " + res.describe())
        for name in named:
            self.assertIn(name, message, msg="the note must name %s: %s" % (name, res.describe()))


# ===========================================================================
# 1. The basic judgement
# ===========================================================================
class JudgementTests(Base):
    def test_an_uncovered_non_trivial_file_stops_with_the_file_and_the_gates_next_steps(self):
        name = "Uncovered_%s.cs" % token()
        self.p.write("src/" + name)
        res = self.p.run_check()
        self.assertStopped(res, name)
        for text in ("Next steps:", "/design-first"):
            self.assertIn(text, res.err, msg="the stop carries the concept gate's next-steps text (%r): %s"
                                             % (text, res.describe()))
        # Sanity: those markers are the gate's own, so the check's text is the gate's text.
        gate_text = self.p.gate_stderr(self.p.project / "src" / name)
        for text in ("Next steps:", "/design-first"):
            self.assertIn(text, gate_text, msg="control: the gate itself says %r" % text)

    def test_the_stop_text_begins_with_the_fixed_paragraph_about_files_the_session_may_not_have_written(self):
        self.p.write("src/Opening_%s.cs" % token())
        res = self.p.run_check()
        self.assertEqual(res.rc, 2, msg=res.describe())
        self.assertTrue(squash(res.err).startswith(squash(FIXED_PARAGRAPH)),
                        msg="the stop text must OPEN with the fixed paragraph. Got: " + squash(res.err)[:500])

    def test_a_covered_file_is_clean_and_an_uncovered_sibling_still_stops(self):
        tag = token()
        covered, other = "Covered_%s.cs" % tag, "Other_%s.cs" % tag
        self.p.contract(["src/" + covered])
        self.p.write("src/" + covered)
        only_covered = self.p.run_check()
        self.assertClean(only_covered)
        self.p.write("src/" + other)
        both = self.p.run_check(session="second-" + tag)
        self.assertStopped(both, other, absent=(covered,))

    def test_a_trivial_file_is_clean_and_an_uncovered_sibling_still_stops(self):
        tag = token()
        for rel in ("docs/notes_%s.md" % tag, "config_%s.json" % tag, "README_%s.txt" % tag):
            self.p.write(rel)
        self.assertClean(self.p.run_check())
        other = "Other_%s.cs" % tag
        self.p.write("src/" + other)
        res = self.p.run_check(session="second-" + tag)
        self.assertStopped(res, other, absent=("notes_%s.md" % tag, "config_%s.json" % tag))

    def test_a_dot_claude_file_is_clean_and_an_uncovered_sibling_still_stops(self):
        tag = token()
        self.p.write(".claude/hooks/x_%s.py" % tag)
        self.p.write(".claude/notes_%s.txt" % tag)
        self.assertClean(self.p.run_check())
        other = "Other_%s.cs" % tag
        self.p.write("src/" + other)
        res = self.p.run_check(session="second-" + tag)
        self.assertStopped(res, other, absent=("x_%s.py" % tag,))

    def test_a_deleted_file_is_never_judged(self):
        tag = token()
        gone = "Gone_%s.cs" % tag
        path = self.p.commit_file("src/" + gone)
        path.unlink()
        self.assertClean(self.p.run_check())
        other = "Other_%s.cs" % tag
        self.p.write("src/" + other)
        res = self.p.run_check(session="second-" + tag)
        self.assertStopped(res, other, absent=(gone,))

    def test_a_modified_tracked_file_is_judged(self):
        name = "Tracked_%s.cs" % token()
        path = self.p.commit_file("src/" + name, "one\n")
        path.write_text("two\n", encoding="utf-8")
        self.assertStopped(self.p.run_check(), name)

    def test_a_linguist_generated_file_is_noted_never_stopped(self):
        tag = token()
        generated = "Client_%s.cs" % tag
        self.p.write("src/gen/" + generated)
        res = self.p.run_check()
        self.assertNoted(res, generated)
        # Control: with an ordinary uncovered file beside it, the turn stops for that file only.
        other = "Other_%s.cs" % tag
        self.p.write("src/" + other)
        res2 = self.p.run_check(session="second-" + tag)
        self.assertStopped(res2, other, absent=(generated,))

    def test_concept_gate_off_turns_the_check_off(self):
        name = "Off_%s.cs" % token()
        self.p.write("src/" + name)
        self.assertEqual(self.p.run_check(session="control-" + token()).rc, 2,
                         msg="control: without the switch the same tree stops")
        res = self.p.run_check(env={"CLAUDE_CONCEPT_GATE": "off"})
        self.assertEqual(res.rc, 0, msg="CLAUDE_CONCEPT_GATE=off must turn the check off: " + res.describe())
        self.assertNotIn(name, res.err, msg="and it names nothing: " + res.describe())

    def test_a_pinned_contract_covers_the_file_and_without_the_pin_it_stops(self):
        tag = token()
        name = "Pinned_%s.cs" % tag
        self.p.write("src/" + name)
        pinned = write_contract(self.p.root / "elsewhere" / ("pin-%s.md" % tag), ["src/" + name])
        self.assertStopped(self.p.run_check(session="control-" + tag), name)
        res = self.p.run_check(env={"CLAUDE_ACTIVE_CONTRACT": str(pinned)})
        self.assertClean(res)

    def test_a_worktrees_own_approved_contract_covers_its_files(self):
        tag = token()
        wt = self.p.project / ".claude" / "worktrees" / ("wt-%s" % tag)
        git(self.p.project, "worktree", "add", "-q", "-b", "branch-%s" % tag, str(wt))
        covered, other = "WtCovered_%s.cs" % tag, "WtOther_%s.cs" % tag
        self.p.contract(["src/" + covered], base=wt)
        self.p.write("src/" + covered, base=wt)
        res = self.p.run_check(cwd=wt)
        self.assertClean(res)
        self.p.write("src/" + other, base=wt)
        res2 = self.p.run_check(cwd=wt, session="second-" + tag)
        self.assertStopped(res2, other, absent=(covered,))


# ===========================================================================
# 2. The baseline: only what changed during the session counts
# ===========================================================================
class BaselineTests(Base):
    def test_a_file_unchanged_since_the_baseline_is_clean_and_the_same_file_changed_after_it_stops(self):
        name = "Before_%s.cs" % token()
        path = self.p.write("src/" + name, "version one\n")
        start = self.p.start_session("startup")
        self.assertEqual(start.returncode, 0, msg="the real SessionStart hook must exit 0")
        self.assertTrue(self.p.baseline_files(),
                        msg="a SessionStart with source startup must write the baseline into the system "
                            "temporary folder (a file starting %r and naming the session)" % BASELINE_PREFIX)
        self.assertClean(self.p.run_check())
        path.write_text("version two\n", encoding="utf-8")
        self.assertStopped(self.p.run_check(session=self.p.session), name)

    def test_a_file_created_after_the_baseline_stops_while_one_uncommitted_before_it_does_not(self):
        tag = token()
        old, new = "Old_%s.cs" % tag, "New_%s.cs" % tag
        self.p.write("src/" + old)
        self.p.start_session("startup")
        self.p.write("src/" + new)
        self.assertStopped(self.p.run_check(), new, absent=(old,))

    def test_a_tree_with_no_baseline_counts_every_uncommitted_file(self):
        name = "NoBaseline_%s.cs" % token()
        self.p.write("src/" + name)
        self.assertEqual(self.p.baseline_files(), [], msg="fixture: no baseline was written")
        self.assertStopped(self.p.run_check(), name)

    def test_a_tree_the_session_entered_later_counts_every_uncommitted_file(self):
        tag = token()
        self.p.start_session("startup")
        other_tree = self.p.root / "other_tree"
        other_tree.mkdir()
        git(other_tree, "init", "-q")
        (other_tree / "README.md").write_text("x\n", encoding="utf-8")
        git(other_tree, "add", "-A")
        git(other_tree, "commit", "-q", "-m", "x")
        name = "Later_%s.cs" % tag
        self.p.write("src/" + name, base=other_tree)
        res = self.p.run_check(cwd=other_tree)
        self.assertStopped(res, name)

    def test_a_missing_or_unreadable_baseline_counts_every_uncommitted_file(self):
        name = "Corrupt_%s.cs" % token()
        self.p.write("src/" + name)
        self.p.start_session("startup")
        files = self.p.baseline_files()
        self.assertTrue(files, msg="fixture: the startup start must have written a baseline")
        for f in files:
            f.write_bytes(b"\x00 this is not a baseline \xff")
        self.assertStopped(self.p.run_check(), name)

    def test_a_startup_start_writes_the_baseline(self):
        self.assertEqual(self.p.baseline_files(), [], msg="fixture: nothing yet")
        self.p.start_session("startup")
        self.assertEqual(len(self.p.baseline_files()), 1,
                         msg="exactly one baseline file for the session, named with the session id")

    def test_resume_clear_compact_and_no_source_write_no_baseline(self):
        for source in ("resume", "clear", "compact", None):
            with self.subTest(source=source):
                p = Project(self)
                p.write("src/Pending_%s.cs" % token())
                proc = p.start_session(source)
                self.assertEqual(proc.returncode, 0, msg="the hook must exit 0")
                self.assertEqual(p.baseline_files(), [],
                                 msg="source %r must write no baseline" % (source,))
        # Control: startup does write one, so the empty result above is the rule and not a broken probe.
        p = Project(self)
        p.start_session("startup")
        self.assertTrue(p.baseline_files(), msg="control: startup writes the baseline")

    def test_resume_clear_compact_and_no_source_leave_an_existing_baseline_unchanged(self):
        for source in ("resume", "clear", "compact", None):
            with self.subTest(source=source):
                p = Project(self)
                p.write("src/First_%s.cs" % token())
                p.start_session("startup")
                files = p.baseline_files()
                self.assertTrue(files, msg="fixture: a baseline exists")
                before = {f.name: f.read_bytes() for f in files}
                p.write("src/Second_%s.cs" % token())
                p.start_session(source)
                after = {f.name: f.read_bytes() for f in p.baseline_files()}
                self.assertEqual(after, before,
                                 msg="a %r start must leave the baseline exactly as it was" % (source,))

    def test_a_file_changed_before_a_compact_start_is_still_judged_after_it(self):
        name = "BeforeCompact_%s.cs" % token()
        self.p.start_session("startup")
        self.p.write("src/" + name)
        self.p.start_session("compact")
        self.assertStopped(self.p.run_check(), name)


# ===========================================================================
# 3. Stopping, noting and never stopping twice for the same files
# ===========================================================================
class OutcomeTests(Base):
    def test_stop_hook_active_gives_noted_with_exit_0(self):
        name = "Active_%s.cs" % token()
        self.p.write("src/" + name)
        self.assertEqual(self.p.run_check(session="control-" + token()).rc, 2, msg="control: it stops without it")
        res = self.p.run_check(stop_hook_active=True)
        self.assertNoted(res, name)

    def test_the_same_set_twice_in_one_session_gives_noted_the_second_time(self):
        name = "Twice_%s.cs" % token()
        self.p.write("src/" + name)
        first = self.p.run_check()
        self.assertStopped(first, name)
        second = self.p.run_check()
        self.assertNoted(second, name)

    def test_a_set_that_adds_one_new_file_stops_again_and_lists_only_the_new_file(self):
        tag = token()
        a, b = "Alpha_%s.cs" % tag, "Bravo_%s.cs" % tag
        self.p.write("src/" + a)
        self.assertStopped(self.p.run_check(), a)
        self.p.write("src/" + b)
        res = self.p.run_check()
        # OPEN CONTRACT QUESTION (flagged for the architect): the contract says the earlier files go "in one
        # noted line". This row asserts the earlier file is NEVER named on stderr, on the narrowest reading of
        # "lists only the new file": a stop is exit 2, and Claude Code ignores stdout JSON (the systemMessage
        # channel) on exit 2, so stderr is the only channel and the noted line cannot ride on stdout. If the
        # architect decides the noted line belongs on stderr, this assertion changes; it is not loosened here.
        self.assertStopped(res, b, absent=(a,))

    def test_a_set_made_only_of_files_already_stopped_for_is_noted(self):
        tag = token()
        a, b = "Alpha_%s.cs" % tag, "Bravo_%s.cs" % tag
        path_a = self.p.write("src/" + a)
        self.p.write("src/" + b)
        self.assertStopped(self.p.run_check(), a, b)
        path_a.unlink()
        res = self.p.run_check()
        self.assertNoted(res, b)

    def test_another_session_is_stopped_for_the_same_file_because_the_memory_is_per_session(self):
        name = "PerSession_%s.cs" % token()
        self.p.write("src/" + name)
        self.assertStopped(self.p.run_check(session="one-" + token()), name)
        self.assertStopped(self.p.run_check(session="two-" + token()), name)


# ===========================================================================
# 4. Failing open
# ===========================================================================
def write_fake_git(directory: Path, seconds: int) -> Path:
    """A real executable called git that sleeps (git.exe on Windows, built from the launcher pip ships)."""
    directory.mkdir(parents=True, exist_ok=True)
    body = ("import time\ntime.sleep(%d)\n" % seconds).encode("utf-8")
    if IS_WINDOWS:
        from pip._vendor.distlib.scripts import ScriptMaker  # type: ignore
        launcher = ScriptMaker(None, str(directory))._get_launcher("t")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("__main__.py", body)
        target = directory / "git.exe"
        target.write_bytes(launcher + b"#!" + sys.executable.encode("utf-8") + b"\r\n" + buf.getvalue())
    else:
        target = directory / "git"
        target.write_bytes(b"#!" + sys.executable.encode("utf-8") + b"\n" + body)
        target.chmod(0o755)
    return target


class FailOpenTests(Base):
    """git missing, a folder outside git and a git call past its time limit each exit 0, log one error line
    and say so once per session."""

    def _assert_failed_open(self, first: Result, lines_after_first: list, second: Result) -> None:
        self.assertEqual(first.rc, 0, msg="a check that cannot work exits 0: " + first.describe())
        self.assertNotIn("Traceback", first.err, msg="and does not crash: " + first.describe())
        message = first.message().lower()
        self.assertTrue(message, msg="the first run says once that shell writes were not checked: "
                                     + first.describe())
        for word in ("shell", "not", "check"):
            self.assertIn(word, message, msg="the note must say shell writes were not checked: " + message)
        self.assertEqual(len(lines_after_first), 1,
                         msg="exactly one error-log line (hook concept-changed-check) for the first run: %r"
                             % lines_after_first)
        self.assertEqual(second.rc, 0, msg="the second run also exits 0: " + second.describe())
        self.assertEqual(second.message(), "",
                         msg="and says nothing again: at most one systemMessage per session: " + second.describe())

    def _twice(self, **kw):
        first = self.p.run_check(**kw)
        lines = self.p.error_lines()
        second = self.p.run_check(**kw)
        return first, lines, second

    def test_git_missing(self):
        empty = self.p.root / "empty_bin"
        empty.mkdir()
        self.p.write("src/Missing_%s.cs" % token())
        self._assert_failed_open(*self._twice(env={"PATH": str(empty)}))

    def test_a_folder_outside_git(self):
        outside = self.p.root / "not_a_repo"
        outside.mkdir()
        (outside / "Loose.cs").write_text("x\n", encoding="utf-8")
        self._assert_failed_open(*self._twice(cwd=outside))

    def test_a_git_call_past_its_time_limit(self):
        fake = self.p.root / "slow_bin"
        write_fake_git(fake, 25)
        self.p.write("src/Slow_%s.cs" % token())
        path_env = {"PATH": str(fake) + os.pathsep + os.environ.get("PATH", "")}
        started = time.time()
        first = self.p.run_check(env=path_env, timeout=50)
        elapsed = time.time() - started
        lines = self.p.error_lines()
        second = self.p.run_check(env=path_env, timeout=50)
        self._assert_failed_open(first, lines, second)
        self.assertLess(elapsed, 22, msg="a git call over 5 seconds must be given up on, not waited for")

    def test_its_own_exception_exits_0(self):
        self.p.write("src/Boom_%s.cs" % token())
        self.p.check_path()
        (self.p.hooks / "concept-gate.py").unlink()  # the check loads the gate by path; this makes it raise
        res = self.p.run_check()
        self.assertEqual(res.rc, 0, msg="its own exception must exit 0, never hold a session: " + res.describe())
        self.assertNotIn("Traceback", res.err, msg="and must not print a traceback: " + res.describe())
        self.assertEqual(len(self.p.error_lines()), 1,
                         msg="and logs exactly one error line (hook concept-changed-check): %r" % self.p.error_lines())

    def test_garbage_input_exits_0(self):
        res = self.p.run_check(stdin=b"{ this is not json")
        self.assertEqual(res.rc, 0, msg="unreadable input is not a reason to hold a session: " + res.describe())
        self.assertNotIn("Traceback", res.err, msg="and must not print a traceback: " + res.describe())


# ===========================================================================
# 5. Commit time: --staged
# ===========================================================================
class StagedTests(Base):
    def _stage(self, rel: str, text: str = "staged\n") -> Path:
        path = self.p.write(rel, text)
        git(self.p.project, "add", "--", rel)
        return path

    def test_a_staged_uncovered_file_exits_2_and_names_it(self):
        tag = token()
        staged = "Staged_%s.cs" % tag
        self._stage("src/" + staged)
        self.p.write("src/Unstaged_%s.cs" % tag)
        res = self.p.run_check(args=("--staged",))
        self.assertEqual(res.rc, 2, msg="a staged file no contract covers: exit 2: " + res.describe())
        self.assertIn(staged, res.err, msg="it names the staged file: " + res.describe())
        self.assertNotIn("Unstaged_%s.cs" % tag, res.err,
                         msg="it does not judge a file that is not staged: " + res.describe())

    def test_covered_trivial_and_dot_claude_staged_files_exit_0(self):
        tag = token()
        covered = "StagedCovered_%s.cs" % tag
        self.p.contract(["src/" + covered])
        self._stage("src/" + covered)
        self._stage("docs/staged_%s.md" % tag)
        self._stage(".claude/hooks/staged_%s.py" % tag)
        res = self.p.run_check(args=("--staged",))
        self.assertEqual(res.rc, 0, msg="covered, trivial and .claude/ files are clean: " + res.describe())
        # Control: add an uncovered staged file and the same command exits 2.
        other = "StagedOther_%s.cs" % tag
        self._stage("src/" + other)
        res2 = self.p.run_check(args=("--staged",))
        self.assertEqual(res2.rc, 2, msg="control: an uncovered staged file stops the commit: " + res2.describe())
        self.assertIn(other, res2.err, msg=res2.describe())
        self.assertNotIn(covered, res2.err, msg="and the covered one is not listed: " + res2.describe())

    def test_nothing_staged_exits_0(self):
        self.p.write("src/OnlyUnstaged_%s.cs" % token())
        res = self.p.run_check(args=("--staged",))
        self.assertEqual(res.rc, 0, msg="an empty staged set is clean: " + res.describe())

    def test_a_staged_deletion_is_not_judged(self):
        gone = "StagedGone_%s.cs" % token()
        self.p.commit_file("src/" + gone)
        git(self.p.project, "rm", "-q", "--", "src/" + gone)
        res = self.p.run_check(args=("--staged",))
        self.assertEqual(res.rc, 0, msg="deletions are never judged: " + res.describe())

    def test_a_folder_outside_git_exits_3(self):
        outside = self.p.root / "not_a_repo"
        outside.mkdir()
        res = self.p.run_check(args=("--staged",), cwd=outside)
        self.assertEqual(res.rc, 3, msg="could not check: exit 3: " + res.describe())

    def test_concept_gate_off_exits_0(self):
        self._stage("src/StagedOff_%s.cs" % token())
        self.assertEqual(self.p.run_check(args=("--staged",)).rc, 2, msg="control: it stops without the switch")
        res = self.p.run_check(args=("--staged",), env={"CLAUDE_CONCEPT_GATE": "off"})
        self.assertEqual(res.rc, 0, msg="the switch turns the commit check off too: " + res.describe())


# ===========================================================================
# 6. The one-matcher rule: the check and the gate agree on every target
# ===========================================================================
class ParityTests(Base):
    def test_the_check_and_the_concept_gate_allow_and_block_the_same_targets(self):
        tag = token()
        covered = "src/ParityCovered_%s.cs" % tag
        self.p.contract([covered])
        targets = [
            covered,
            "src/ParityUncoveredA_%s.cs" % tag,
            "src/ParityUncoveredB_%s.py" % tag,
            "lib/ParityUncoveredC_%s.ts" % tag,
            "docs/ParityNotes_%s.md" % tag,
            "ParityConfig_%s.json" % tag,
            "ParityText_%s.txt" % tag,
            ".claude/hooks/ParityHook_%s.py" % tag,
            ".claude/concepts/ParityDraft_%s.md" % tag,
            "bin/ParityBinary_%s.cs" % tag,
            "node_modules/pkg/ParityModule_%s.js" % tag,
            "src/ParityLock_%s.lock" % tag,
            "Makefile_%s" % tag,
            "settings_%s.env" % tag,
        ]
        paths = [self.p.write(rel) for rel in targets]
        # The gate judges each target as a PreToolUse Write payload.
        gate_blocks = {rel for rel, path in zip(targets, paths) if self.p.run_gate(path) == 2}
        res = self.p.run_check()
        names = {rel: Path(rel).name for rel in targets}
        check_blocks = {rel for rel in targets if names[rel] in res.err}
        self.assertTrue(gate_blocks, msg="control: the gate blocks at least one target, or this row proves nothing")
        self.assertTrue(set(targets) - gate_blocks, msg="control: the gate allows at least one target")
        self.assertEqual(res.rc, 2, msg="at least one target is blocked, so the check stops: " + res.describe())
        self.assertEqual(check_blocks, gate_blocks,
                         msg="the check must block exactly the targets the concept gate blocks.\n"
                             "gate only: %s\ncheck only: %s\n%s"
                             % (sorted(gate_blocks - check_blocks), sorted(check_blocks - gate_blocks),
                                res.describe()))


# ===========================================================================
# 7. Where a "generated" mark may come from (Revision 11, finding F2)
# ===========================================================================
class GeneratedAttributeSourceTests(Base):
    """A file counts as generated only when the COMMITTED attribute files of HEAD mark it.

    Three other places can carry the mark and a session controls each: an untracked ``.gitattributes``, the
    repository-private ``.git/info/attributes`` and a user-wide attributes file. None of them may hide an
    uncovered file. A ``linguist-generated`` line in ``info/attributes`` turns the exemption off for every file
    in the run. At ``--staged`` a generated file is no longer silent: exit 0 and one stderr line naming it.

    Each row has its own project and so its own session id. Every fixture asserts, before use, that its root
    is not under a .claude folder (a probe there would be clean by construction) and FAILS otherwise.
    """

    def _stage(self, *rels: str) -> None:
        for rel in rels:
            git(self.p.project, "add", "--", rel)

    def _stops_at_turn_end(self, name: str, env: dict | None = None) -> None:
        self.assertStopped(self.p.run_check(env=env), name)

    def _stops_at_staged(self, name: str, *stage: str, env: dict | None = None) -> None:
        self._stage(*stage)
        staged = self.p.run_check(args=("--staged",), env=env)
        self.assertEqual(staged.rc, 2, msg="at --staged the same file must stop the commit: " + staged.describe())
        self.assertIn(name, staged.err, msg="and the stop must name it: " + staged.describe())

    def _info_attributes(self, text: str = "src/** linguist-generated\n") -> None:
        info = self.p.project / ".git" / "info"
        info.mkdir(parents=True, exist_ok=True)
        (info / "attributes").write_text(text, encoding="utf-8")

    def _user_wide_marking(self) -> dict:
        """The fixture's own global git config pointing at an attributes file that marks src/**."""
        attributes = self.p.root / "global-attributes"
        attributes.write_text("src/** linguist-generated\n", encoding="utf-8")
        config = self.p.root / "global-gitconfig"
        config.write_text("[core]\n\tattributesFile = %s\n" % attributes.as_posix(), encoding="utf-8")
        return {"GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_NOSYSTEM": "1"}

    def test_fixture_root_is_outside_any_claude_folder(self):
        parts = [part.lower() for part in Path(os.path.realpath(str(self.p.root))).parts]
        self.assertNotIn(".claude", parts, msg="the fixture must live under the system temporary folder")
        # Positive control for the guard itself: a root under a .claude folder is refused. Each call is outside
        # subTest and a SkipTest becomes a failure (a skip would pass assertRaises and be recorded as a skip).
        for bad in (self.p.root / ".claude" / "x", Path("C:/Users/someone/.claude/jobs/abc"),
                    Path("/home/u/.CLAUDE/t")):
            try:
                assert_fixture_outside_claude_folder(self, bad)
            except unittest.SkipTest:
                self.fail("the guard SKIPPED for %s; it must fail" % bad)
            except AssertionError:
                continue
            self.fail("the guard let %s pass; it must fail" % bad)

    def test_a_new_uncovered_file_with_no_attribute_stops_at_turn_end(self):
        # (a) positive control: passes today.
        name = "Plain_%s.cs" % token()
        self.p.write("src/" + name)
        self._stops_at_turn_end(name)

    def test_a_new_uncovered_file_with_no_attribute_stops_at_staged(self):
        # (a) positive control: passes today.
        name = "PlainStaged_%s.cs" % token()
        self.p.write("src/" + name)
        self._stops_at_staged(name, "src/" + name)

    def test_an_untracked_gitattributes_marking_everything_does_not_hide_the_file_at_turn_end(self):
        # (b) the untracked file covers itself and the file beside it.
        name = "UntrackedAttr_%s.cs" % token()
        self.p.write("src/.gitattributes", "* linguist-generated\n")
        self.p.write("src/" + name)
        self._stops_at_turn_end(name)

    def test_an_untracked_gitattributes_marking_everything_does_not_hide_the_file_at_staged(self):
        # (b) with both files staged; neither is in HEAD, so neither mark counts.
        name = "UntrackedAttrStaged_%s.cs" % token()
        self.p.write("src/.gitattributes", "* linguist-generated\n")
        self.p.write("src/" + name)
        self._stops_at_staged(name, "src/.gitattributes", "src/" + name)

    def test_a_mark_in_the_private_info_attributes_file_does_not_hide_the_file_at_turn_end(self):
        # (c) git status never shows .git/info/attributes.
        name = "InfoAttr_%s.cs" % token()
        self._info_attributes()
        self.p.write("src/" + name)
        self._stops_at_turn_end(name)

    def test_a_mark_in_the_private_info_attributes_file_does_not_hide_the_file_at_staged(self):
        name = "InfoAttrStaged_%s.cs" % token()
        self._info_attributes()
        self.p.write("src/" + name)
        self._stops_at_staged(name, "src/" + name)

    def test_a_mark_in_a_user_wide_attributes_file_does_not_hide_the_file(self):
        # (d) the fixture's own global git config; the developer's is never read.
        name = "GlobalAttr_%s.cs" % token()
        env = self._user_wide_marking()
        self.p.write("src/" + name)
        # Positive control: git itself, given that config, reports the mark, so the fixture is not inert.
        probe = subprocess.run(["git", "check-attr", "linguist-generated", "--", "src/" + name],
                               cwd=str(self.p.project), env=self.p.env(env), capture_output=True, text=True)
        self.assertIn("linguist-generated: set", probe.stdout,
                      msg="fixture: the user-wide file must mark the file: %r %r" % (probe.stdout, probe.stderr))
        self._stops_at_turn_end(name, env=env)

    def test_a_mark_in_a_user_wide_attributes_file_does_not_hide_the_file_at_staged(self):
        name = "GlobalAttrStaged_%s.cs" % token()
        env = self._user_wide_marking()
        self.p.write("src/" + name)
        self._stops_at_staged(name, "src/" + name, env=env)

    def test_a_committed_attribute_still_notes_the_file_at_turn_end(self):
        # (e, first half) the existing behaviour: a control that passes today.
        name = "Committed_%s.cs" % token()
        self.p.write("src/gen/" + name)
        self.assertNoted(self.p.run_check(), name)

    def test_a_committed_attribute_at_staged_exits_0_and_says_one_stderr_line_naming_the_file(self):
        # (e, second half) today it says nothing.
        name = "CommittedStaged_%s.cs" % token()
        self.p.write("src/gen/" + name)
        self._stage("src/gen/" + name)
        res = self.p.run_check(args=("--staged",))
        self.assertEqual(res.rc, 0, msg="a generated file alone does not stop the commit: " + res.describe())
        lines = [line for line in res.err.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, msg="exactly one standard-error line: " + res.describe())
        self.assertIn(name, lines[0], msg="and it names the generated file: " + res.describe())
        self.assertEqual(res.out.strip(), "", msg="nothing on stdout: " + res.describe())

    def test_a_committed_attribute_plus_an_info_attributes_mark_stops_at_turn_end(self):
        # (f) the committed attribute does not save the file once the private file also marks it.
        name = "Both_%s.cs" % token()
        self._info_attributes()
        self.p.write("src/gen/" + name)
        self._stops_at_turn_end(name)

    def test_a_committed_attribute_plus_an_info_attributes_mark_stops_at_staged(self):
        name = "BothStaged_%s.cs" % token()
        self._info_attributes()
        self.p.write("src/gen/" + name)
        self._stops_at_staged(name, "src/gen/" + name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
