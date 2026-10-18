#!/usr/bin/env python3
"""
test_concept_gate_outside_project.py -- RED tests for the concept gate's "outside every project" allowance.

Contract: .claude/concepts/2026-10-17-worktree-removal-untracked-identical.md, Data Shapes CG-1 to CG-6
(cases G1 to G6 of the Implementation Handoff).

The gate protects project code. A Write or Edit is allowed when the gate can PROVE the target has no project
marker (.git, CLAUDE.md, package.json, pyproject.toml, *.sln) anywhere on its path, both as written (links NOT
followed, ``..`` folded) and as resolved, and both scans were complete. Inside a project nothing changes.

Cases:
  G1  a .cmd and a .py target in a fresh temp folder with no marker on its path -> exit 0, nothing printed.
  G2  control: the same names inside a temp project (CLAUDE.md marker; and a .git folder variant) -> exit 2.
  G3  a relative target "x.py", cwd = <temp project>/sub (sub has no marker) -> exit 2.
  G4  in-process: the LISTING of one existing ancestor raises PermissionError -> not allowed.
  G4b in-process: the EXISTENCE CHECK of one existing ancestor raises PermissionError -> not allowed, no raise.
  G5  two targets (one outside every project, one uncovered in a project) -> exit 2 naming the in-project one only.
  G6  a link from a project to a marker-less folder, and a link from a marker-less folder into a project -> exit 2.

G3, G4, G4b and G6 each carry a control that the allowance exists (the same kind of target outside every project
is allowed). Without it they would pass today for the wrong reason: today nothing is ever allowed outside a
contract, so "not allowed" proves nothing.

Run:  py -3 .claude/hooks/tests/test_concept_gate_outside_project.py
      (or: cd .claude/hooks/tests && py -3 -m unittest test_concept_gate_outside_project)
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HOOKS_DIR = Path(__file__).resolve().parent.parent
GATE = HOOKS_DIR / "concept-gate.py"
IS_WINDOWS = os.name == "nt"

MARKER_NAMES = (".git", "CLAUDE.md", "package.json", "pyproject.toml")
BLOCKED_BANNER = "[concept-gate] BLOCKED"
NO_CONTRACT_REASON = "no approved contract's 'Files to touch' list references this file"


def rmtree_force(path: Path) -> None:
    def _onerror(func, p, _exc):
        try:
            os.chmod(p, 0o700)
            func(p)
        except OSError:
            pass
    shutil.rmtree(str(path), onerror=_onerror)


def markers_on_path(path) -> list:
    """Every project marker on ``path`` or any ancestor, for the path as written AND as resolved. The test's OWN
    walk (it never calls the gate), used as the precondition of the allowance tests."""
    found = []
    seen = set()
    for start in (os.path.abspath(str(path)), os.path.realpath(str(path))):
        cur = start
        while True:
            if cur not in seen:
                seen.add(cur)
                try:
                    names = os.listdir(cur) if os.path.isdir(cur) else []
                except OSError as exc:
                    found.append(f"{cur}: cannot be listed ({exc})")
                    names = []
                for name in names:
                    if name in MARKER_NAMES or name.endswith(".sln"):
                        found.append(os.path.join(cur, name))
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    return found


def make_directory_link(link: Path, target: Path) -> str:
    """A directory link at ``link`` pointing to ``target``: a junction on Windows, a symlink elsewhere."""
    if IS_WINDOWS:
        import _winapi  # type: ignore
        _winapi.CreateJunction(str(target), str(link))
        return "junction"
    os.symlink(str(target), str(link), target_is_directory=True)
    return "symlink"


class GateCase(unittest.TestCase):
    def setUp(self) -> None:
        self.base = Path(os.path.realpath(tempfile.mkdtemp(prefix="cg_outside_")))
        self.addCleanup(rmtree_force, self.base)
        self.home = self.base / "home"
        self.home.mkdir()

    # -- layout ----------------------------------------------------------------------------------
    def fresh_dir(self, name: str) -> Path:
        d = self.base / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def project(self, name: str = "proj", *, marker: str = "CLAUDE.md") -> Path:
        d = self.fresh_dir(name)
        if marker == ".git":
            (d / ".git").mkdir()
        else:
            (d / marker).write_text("# project\n", encoding="utf-8")
        return d

    def assert_no_marker(self, path: Path, what: str) -> None:
        found = markers_on_path(path)
        if found:  # never a skip: a host that cannot show the allowance must say so loudly
            self.fail(f"precondition for {what}: the temp area must be outside every project, but a marker sits on the "
                      f"path of {path}: {found}")

    # -- running the hook ------------------------------------------------------------------------
    def env(self) -> dict:
        env = {k: v for k, v in os.environ.items()
               if k not in ("CLAUDE_CONCEPT_GATE", "CLAUDE_ACTIVE_CONTRACT", "CLAUDE_PROJECT_DIR",
                            "CLAUDE_CONTRACT_INDEX", "PYTHONPATH")}
        env["HOME"] = str(self.home)
        env["USERPROFILE"] = str(self.home)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def run_gate(self, targets, *, cwd: Path | None = None, tool: str = "Write") -> subprocess.CompletedProcess:
        if isinstance(targets, str):
            targets = [targets]
        if len(targets) == 1 and tool == "Write":
            tool_input = {"file_path": targets[0], "content": "x\n"}
        else:
            tool = "MultiEdit"
            tool_input = {"edits": [{"file_path": t, "old_string": "a", "new_string": "b"} for t in targets]}
        payload = json.dumps({"tool_name": tool, "tool_input": tool_input}).encode("utf-8")
        done = subprocess.run([sys.executable, str(GATE)], input=payload, capture_output=True,
                              cwd=str(cwd or self.base), env=self.env(), timeout=120)
        return done

    @staticmethod
    def err(done) -> str:
        return (done.stderr or b"").decode("utf-8", "replace")

    def describe(self, done) -> str:
        return f"exit {done.returncode}, stderr: {self.err(done)[:600]!r}"

    def assert_allowed(self, done, why: str) -> None:
        self.assertEqual(done.returncode, 0, msg=f"{why}; got {self.describe(done)}")
        self.assertNotIn(BLOCKED_BANNER, self.err(done), msg=f"{why}: no block banner")

    def assert_blocked(self, done, why: str) -> None:
        self.assertEqual(done.returncode, 2, msg=f"{why}; got {self.describe(done)}")
        self.assertIn(BLOCKED_BANNER, self.err(done), msg=f"{why}: the block banner is printed")

    # -- the gate loaded in-process --------------------------------------------------------------
    def load_gate(self):
        if str(HOOKS_DIR) not in sys.path:
            sys.path.insert(0, str(HOOKS_DIR))
        spec = importlib.util.spec_from_file_location("concept_gate_under_test", str(GATE))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def resolve(self, module, target: Path):
        with mock.patch.dict(os.environ, self.env(), clear=True):
            return module.resolve_target(target, None)


def same(a, b) -> bool:
    return os.path.normcase(os.path.abspath(str(a))) == os.path.normcase(os.path.abspath(str(b)))


# ===========================================================================
# G1 and G2: the allowance and its control
# ===========================================================================
class OutsideEveryProjectTests(GateCase):
    def test_g1_a_cmd_and_a_py_target_outside_every_project_are_allowed_and_nothing_is_printed(self):
        area = self.fresh_dir("scratch")
        self.assert_no_marker(area, "G1")
        for name in ("run.cmd", "tool.py"):
            target = area / name

            done = self.run_gate(str(target))

            self.assert_allowed(done, f"CG-1: {name} has no project marker on its path as written or resolved")
            self.assertEqual(self.err(done).strip(), "",
                             msg="CG-3: the allowance prints nothing, like every other allow")

    def test_g2_control_the_same_names_inside_a_claude_md_project_are_still_blocked(self):
        project = self.project("proj_md", marker="CLAUDE.md")
        for name in ("run.cmd", "tool.py"):
            done = self.run_gate(str(project / name))

            self.assert_blocked(done, f"CG-3: {name} inside a CLAUDE.md project is gated as today")
            self.assertIn(NO_CONTRACT_REASON, self.err(done),
                          msg="CG-3: the reason is the unchanged 'no approved contract' text")

    def test_g2_control_the_same_names_inside_a_git_folder_project_are_still_blocked(self):
        project = self.project("proj_git", marker=".git")
        for name in ("run.cmd", "tool.py"):
            done = self.run_gate(str(project / name))

            self.assert_blocked(done, f"CG-3: {name} inside a .git project is gated as today")
            self.assertIn(NO_CONTRACT_REASON, self.err(done),
                          msg="CG-3: the reason is the unchanged 'no approved contract' text")

    def test_g3_a_relative_target_whose_project_sits_above_the_working_folder_is_blocked(self):
        project = self.project("proj_rel")
        sub = project / "sub"
        sub.mkdir()
        free = self.fresh_dir("rel_scratch")
        self.assert_no_marker(free, "G3 control")

        control = self.run_gate("x.py", cwd=free)
        done = self.run_gate("x.py", cwd=sub)

        self.assert_allowed(control, "control: a relative target in a marker-less working folder is outside every project")
        self.assert_blocked(done, "CG-1: the relative target is made absolute against the hook's cwd, and the project "
                                  "above it (CLAUDE.md) is found, though `sub` itself has no marker")


# ===========================================================================
# G4 and G4b: cannot prove means gated (in-process)
# ===========================================================================
class CannotProveTests(GateCase):
    def setUp(self) -> None:
        super().setUp()
        self.area = self.fresh_dir("proof_scratch")
        self.assert_no_marker(self.area, "G4")
        self.target = self.area / "deep" / "tool.py"  # `deep` does not exist: a new file in a new folder
        self.ancestor = self.area.parent  # an existing ancestor above the target (the temp folder this test made)

    def test_control_unpatched_the_target_is_outside_every_project_and_is_allowed(self):
        module = self.load_gate()

        allowed, reason, _contract = self.resolve(module, self.target)

        self.assertTrue(allowed, msg=f"control: with every ancestor readable, the target is outside every project and "
                                     f"allowed; got blocked with {reason!r}")

    def test_g4_an_ancestor_whose_listing_raises_permission_error_means_not_allowed(self):
        module = self.load_gate()
        allowed_before, reason_before, _c = self.resolve(module, self.target)
        self.assertTrue(allowed_before, msg=f"control: unpatched, the target is allowed (got {reason_before!r}); without "
                                            "this the test would pass today for the wrong reason")
        real_listdir, real_scandir, real_iterdir = os.listdir, os.scandir, Path.iterdir

        def deny(path) -> bool:
            return same(path, self.ancestor)

        def listdir(path=".", *a, **k):
            if deny(path):
                raise PermissionError(13, "listing refused on purpose", str(path))
            return real_listdir(path, *a, **k)

        def scandir(path=".", *a, **k):
            if deny(path):
                raise PermissionError(13, "listing refused on purpose", str(path))
            return real_scandir(path, *a, **k)

        def iterdir(self_path):
            if deny(self_path):
                raise PermissionError(13, "listing refused on purpose", str(self_path))
            return real_iterdir(self_path)

        with mock.patch("os.listdir", listdir), mock.patch("os.scandir", scandir), mock.patch.object(Path, "iterdir", iterdir):
            allowed, reason, _contract = self.resolve(module, self.target)

        self.assertFalse(allowed, msg="CG-2: an existing ancestor that cannot be listed leaves the scan incomplete; a "
                                      "target the gate cannot prove is outside every project stays gated")

    def test_g4b_an_ancestor_whose_existence_check_raises_permission_error_means_not_allowed_and_no_raise(self):
        module = self.load_gate()
        allowed_before, reason_before, _c = self.resolve(module, self.target)
        self.assertTrue(allowed_before, msg=f"control: unpatched, the target is allowed (got {reason_before!r}); without "
                                            "this the test would pass today for the wrong reason")
        real_stat, real_isdir, real_exists = os.stat, os.path.isdir, os.path.exists
        real_p_stat, real_p_is_dir, real_p_exists = Path.stat, Path.is_dir, Path.exists

        def deny(path) -> bool:
            return same(path, self.ancestor)

        def raising(path):
            raise PermissionError(13, "existence check refused on purpose", str(path))

        def stat(path, *a, **k):
            if not isinstance(path, int) and deny(path):
                raising(path)
            return real_stat(path, *a, **k)

        def isdir(path):
            if not isinstance(path, int) and deny(path):
                raising(path)
            return real_isdir(path)

        def exists(path):
            if not isinstance(path, int) and deny(path):
                raising(path)
            return real_exists(path)

        def p_stat(self_path, *a, **k):
            if deny(self_path):
                raising(self_path)
            return real_p_stat(self_path, *a, **k)

        def p_is_dir(self_path, *a, **k):
            if deny(self_path):
                raising(self_path)
            return real_p_is_dir(self_path, *a, **k)

        def p_exists(self_path, *a, **k):
            if deny(self_path):
                raising(self_path)
            return real_p_exists(self_path, *a, **k)

        outcome = {}
        with contextlib.ExitStack() as stack:
            for target, fn in (("os.stat", stat), ("os.path.isdir", isdir), ("os.path.exists", exists)):
                stack.enter_context(mock.patch(target, fn))
            for attr, fn in (("stat", p_stat), ("is_dir", p_is_dir), ("exists", p_exists)):
                stack.enter_context(mock.patch.object(Path, attr, fn))
            try:
                outcome["result"] = self.resolve(module, self.target)
            except Exception as exc:  # noqa: BLE001 - the point of the test
                outcome["raised"] = exc

        self.assertNotIn("raised", outcome,
                         msg=f"CG-2: resolve_target must not raise when an existence check fails (the hook would then "
                             f"fail open); it raised {outcome.get('raised')!r}")
        self.assertFalse(outcome["result"][0],
                         msg="CG-2: an ancestor whose existence check fails (not 'not found') leaves the scan "
                             "incomplete, so the target stays gated")


# ===========================================================================
# G5: several targets in one call
# ===========================================================================
class MultiTargetTests(GateCase):
    def test_g5_one_target_outside_and_one_uncovered_in_a_project_blocks_and_names_only_the_project_one(self):
        free = self.fresh_dir("multi_free")
        self.assert_no_marker(free, "G5")
        project = self.project("proj_multi")
        outside = str(Path(free / "outside.py"))
        inside = str(Path(project / "inside.py"))

        done = self.run_gate([outside, inside])

        self.assert_blocked(done, "CG-5: the uncovered in-project target blocks the whole call")
        err = self.err(done)
        self.assertIn(f"Target:  {inside}", err, msg="CG-5: the banner's Target line is the in-project file")
        self.assertIn(f"- BLOCKED: {inside}", err, msg="CG-5: the in-project target is listed as blocked")
        self.assertNotIn(f"- BLOCKED: {outside}", err,
                         msg="CG-5: the target outside every project is judged separately and is not listed as blocked")


# ===========================================================================
# G6: links
# ===========================================================================
class LinkTests(GateCase):
    def test_g6_a_link_inside_a_project_to_a_marker_less_folder_stays_gated(self):
        free = self.fresh_dir("link_free")
        self.assert_no_marker(free, "G6")
        project = self.project("proj_link_in")
        (project / "src").mkdir()
        try:
            make_directory_link(project / "src" / "shared", free)
        except (OSError, NotImplementedError, ImportError) as exc:
            self.skipTest(f"this host refuses to create a directory link: {exc}")
        control = self.run_gate(str(free / "x.py"))

        done = self.run_gate(str(project / "src" / "shared" / "x.py"))

        self.assert_allowed(control, "control: the marker-less folder itself is outside every project")
        self.assert_blocked(done, "CG-1: the written path lies inside the project, so the written scan finds it "
                                  "though the resolved path does not")

    def test_g6_reverse_a_link_in_a_marker_less_folder_into_a_project_stays_gated(self):
        free = self.fresh_dir("link_free_rev")
        self.assert_no_marker(free, "G6 reverse")
        project = self.project("proj_link_out")
        try:
            make_directory_link(free / "into", project)
        except (OSError, NotImplementedError, ImportError) as exc:
            self.skipTest(f"this host refuses to create a directory link: {exc}")
        control = self.run_gate(str(free / "x.py"))

        done = self.run_gate(str(free / "into" / "x.py"))

        self.assert_allowed(control, "control: a file directly in the marker-less folder is outside every project")
        self.assert_blocked(done, "CG-1: the resolved path lies inside the project, so the resolved scan finds it "
                                  "though the written path does not")


if __name__ == "__main__":
    unittest.main(verbosity=2)
