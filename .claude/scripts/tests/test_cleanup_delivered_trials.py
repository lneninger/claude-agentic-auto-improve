#!/usr/bin/env python3
"""
test_cleanup_delivered_trials.py -- the host trials T1 to T4 of the Delivery cleanup contract.

Contract: .claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md, section "Uncertain Assumptions"
(issue #50). These trials exercise the HOST (git, the operating system, Git Bash) and need no
implementation, so they run today: they pass, record, or skip. They are the first TDD commit, before any
test of ``cleanup_delivered.py`` is frozen (journal 2026-10-05: prove a host behaviour with a real trial
before the code depends on it).

  T1  (records its outcome)  On Windows, ``git worktree remove`` (never forced) on a throwaway worktree
      whose folder a subprocess holds as its working directory: does it delete content before it fails?
      The design does NOT depend on the answer (the rename probe always runs on Windows); the trial only
      documents why the probe is there. The observed outcome is printed on stderr as "TRIAL T1 RESULT"
      and kept in ``T1_OUTCOME``; copy it into the pull request description.
  T2  (can fail, has a control)  Removing a directory LINK as the link entry itself leaves its target and
      the target's file intact: ``os.rmdir`` on a junction made with ``_winapi.CreateJunction`` (Windows),
      ``os.unlink`` on a symlink (POSIX). Control: before the removal the file is visible THROUGH the link,
      so a link that never worked could not make the test pass; the link is detected by ``os.lstat``
      (``FILE_ATTRIBUTE_REPARSE_POINT`` on Windows, ``S_ISLNK`` elsewhere) while the real target is not.
  T3  (can fail, has a control)  Once a Git Bash process has changed directory OUT of a tree, it no longer
      blocks the probe rename of that tree. Control: a bash process that stays in the tree DOES block it.
      If T3 fails the design is unchanged: the starting tree simply reads ``in-use`` and a later call
      clears it.
  T4  (manual)  Whether the Claude Code process itself holds its working directory. It cannot be
      automated; the skip message below says how to run it and where to record the answer.

Every trial works in its own temporary folder. None touches the real repository, its worktrees, branches
or remote.

Run: py -3 .claude/scripts/tests/test_cleanup_delivered_trials.py
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_flat_worktree import REAL_GIT, git, rmtree_force  # noqa: E402

IS_WINDOWS = os.name == "nt"

#: Filled in by T1 so a reader (or the pull request description) can quote the observed behaviour.
T1_OUTCOME: dict = {}


def say(text: str) -> None:
    sys.stderr.write(text + "\n")
    sys.stderr.flush()


def make_directory_link(link: Path, target: Path) -> str:
    """A directory link at ``link`` pointing to ``target``: a junction on Windows, a symlink elsewhere."""
    if IS_WINDOWS:
        import _winapi  # type: ignore
        _winapi.CreateJunction(str(target), str(link))
        return "junction"
    os.symlink(str(target), str(link), target_is_directory=True)
    return "symlink"


def is_link_entry(path: Path) -> bool:
    """The detection INV-4 prescribes: ``os.lstat`` plus the reparse-point flag (Windows) or S_ISLNK."""
    st = os.lstat(str(path))
    if IS_WINDOWS:
        return bool(getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    return stat.S_ISLNK(st.st_mode)


def find_git_bash() -> str | None:
    """Git Bash next to the installed git (never the WSL launcher that PATH may name first)."""
    git_exe = shutil.which("git")
    if not git_exe:
        return None
    for root in Path(git_exe).resolve().parents[:4]:  # cmd\git.exe, ucrt64\bin\git.exe and the like
        for candidate in (root / "usr" / "bin" / "bash.exe", root / "bin" / "bash.exe"):
            if candidate.is_file():
                return str(candidate)
    return None


class TrialCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="cleanup_trial_")))
        self.addCleanup(rmtree_force, self.tmp)
        self.procs: list = []
        self.addCleanup(self._reap)

    def _reap(self) -> None:
        for p in self.procs:
            try:
                p.kill()
                p.wait(timeout=10)
            except Exception:
                pass

    def hold(self, argv: list, cwd: Path) -> subprocess.Popen:
        p = subprocess.Popen(argv, cwd=str(cwd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             stdin=subprocess.DEVNULL)
        self.procs.append(p)
        return p


@unittest.skipUnless(IS_WINDOWS, "T1: a process holding its working directory blocks removing that folder "
                                 "only on Windows; POSIX never blocks, so there is nothing to record")
class T1HeldWorktreeRemovalTests(TrialCase):
    def test_t1_records_what_git_worktree_remove_does_to_a_tree_a_process_holds(self):
        """T1. Records the outcome; it asserts only that the trial itself ran.

        Observed on the developer machine (Windows 11, Git for Windows) and printed on stderr as
        "TRIAL T1 RESULT" on every run: see ``T1_OUTCOME`` keys ``returncode``, ``stderr``,
        ``folder_still_exists``, ``tracked_file_survived``, ``git_still_lists_it``.
        """
        repo = self.tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "master")
        (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        (repo / "other.txt").write_text("other\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "initial")
        wt = self.tmp / "held_worktree"
        git(repo, "worktree", "add", "-q", "-b", "held", str(wt))

        holder = self.hold([sys.executable, "-c", "import time; time.sleep(60)"], wt)
        time.sleep(0.5)  # let the holder start and settle in the folder
        self.assertIsNone(holder.poll(), msg="the holder process must be running while the removal is tried")

        removal = subprocess.run([REAL_GIT, "worktree", "remove", str(wt)], cwd=str(repo), capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=120)
        listing = git(repo, "worktree", "list", "--porcelain")
        T1_OUTCOME.update({
            "returncode": removal.returncode,
            "stderr": removal.stderr.strip()[:300],
            "folder_still_exists": wt.exists(),
            "tracked_file_survived": (wt / "tracked.txt").exists(),
            "other_file_survived": (wt / "other.txt").exists(),
            "git_still_lists_it": os.path.normcase(str(wt)).replace("\\", "/") in
                                  os.path.normcase(listing).replace("\\", "/"),
        })
        say("TRIAL T1 RESULT: %r" % (T1_OUTCOME,))
        # The only assertion: the trial observed something definite. Either outcome is acceptable to the design.
        self.assertIn("returncode", T1_OUTCOME,
                      msg="T1 must have recorded the removal's exit code, the design keeps the probe either way")


class T2LinkRemovalLeavesTargetTests(TrialCase):
    def build(self) -> tuple:
        target = self.tmp / "real_node_modules"
        (target / "pkg").mkdir(parents=True)
        (target / "pkg" / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")
        tree = self.tmp / "tree"
        tree.mkdir()
        link = tree / "node_modules"
        kind = make_directory_link(link, target)
        return target, tree, link, kind

    def test_t2_control_the_link_works_and_is_detected_as_a_link_by_lstat(self):
        target, _tree, link, kind = self.build()
        self.assertTrue((link / "pkg" / "index.js").is_file(),
                        msg=f"control: the {kind} must expose the target's file, or the removal test proves nothing")
        self.assertTrue(is_link_entry(link),
                        msg=f"INV-4 detection: os.lstat must flag the {kind} as a link on this Python "
                            f"({sys.version.split()[0]}), including versions before 3.12")
        self.assertFalse(is_link_entry(target),
                         msg="control: the real target folder is not a link, so the lstat test can tell them apart")
        # Recorded for the pull request: how DirEntry sees the link (INV-4 forbids relying on it).
        with os.scandir(str(link.parent)) as it:
            entry = next(e for e in it if e.name == "node_modules")
            say("TRIAL T2 NOTE: DirEntry.is_dir(follow_symlinks=False)=%r is_symlink()=%r on this %s (Python %s)"
                % (entry.is_dir(follow_symlinks=False), entry.is_symlink(), kind, sys.version.split()[0]))

    def test_t2_removing_the_link_entry_alone_leaves_target_folder_and_file_intact(self):
        target, tree, link, kind = self.build()
        self.assertTrue((link / "pkg" / "index.js").is_file(), msg="precondition: the file is reachable via the link")

        if kind == "junction":
            os.rmdir(str(link))
        else:
            os.unlink(str(link))

        self.assertFalse(os.path.lexists(str(link)),
                         msg=f"the {kind} entry itself must be gone after os.{'rmdir' if kind == 'junction' else 'unlink'}")
        self.assertTrue(target.is_dir(), msg=f"T2: removing the {kind} must not take its target folder down")
        self.assertEqual((target / "pkg" / "index.js").read_text(encoding="utf-8"), "module.exports = 1;\n",
                         msg=f"T2: the target's file must survive the removal of the {kind}")
        self.assertTrue(tree.is_dir(), msg="the tree that held the link is untouched")


@unittest.skipUnless(IS_WINDOWS, "T3: the probe rename is Windows-only; on POSIX a rename always succeeds")
class T3CdReleasesFolderTests(TrialCase):
    def probe_rename(self, tree: Path) -> OSError | None:
        """The INV-6 probe: rename the folder to a sibling name and back at once. Returns the failure or None."""
        sibling = tree.with_name(tree.name + "-probe")
        try:
            os.rename(str(tree), str(sibling))
        except OSError as exc:
            return exc
        os.rename(str(sibling), str(tree))
        return None

    def start_bash(self, script: str, tree: Path) -> None:
        bash = find_git_bash()
        if bash is None:
            self.skipTest("T3 needs Git Bash next to git (bin/bash.exe); not found on this machine")
        self.hold([bash, "-c", script], tree)

    def wait_for(self, marker: Path, what: str) -> None:
        deadline = time.time() + 20
        while time.time() < deadline:
            if marker.exists():
                time.sleep(0.3)
                return
            time.sleep(0.1)
        self.fail(f"{what}: the bash process never wrote {marker.name}; the trial could not be set up")

    def test_t3_control_a_python_process_that_stays_in_the_tree_blocks_the_probe(self):
        """Control: the probe CAN fail. A non-bash process whose working directory is the tree blocks the rename."""
        tree = self.tmp / "tree_stay_py"
        tree.mkdir()
        holder = self.hold([sys.executable, "-c", "import time; time.sleep(30)"], tree)
        time.sleep(1.0)
        self.assertIsNone(holder.poll(), msg="the holder must be running while the probe is tried")

        failure = self.probe_rename(tree)

        self.assertIsNotNone(failure,
                             msg="T3 control: a process whose working directory is the tree must make the probe "
                                 "rename fail; if it does not, the probe cannot detect any holder at all")
        self.assertTrue(tree.is_dir(), msg="the failed probe leaves the folder where it was")

    def test_t3_records_whether_a_git_bash_that_stays_in_the_tree_blocks_the_probe(self):
        """RECORDED FINDING (not an assertion about the design).

        The first version of this trial asserted that a bash process staying in the tree BLOCKS the probe
        rename. Observed on the developer machine (Windows 11, Git for Windows, msys bash): it does NOT; the
        rename succeeds, because msys bash opens its working directory with share-delete. A python or cmd
        process in the same folder does block it (see the control above). So the rename probe is blind to a
        Git Bash that stays in the tree; the standing-tree rule (script cwd, CLAUDE_PROJECT_DIR, --from) is
        the layer that has to cover the session's own shell. The outcome is printed as "TRIAL T3 RESULT".
        """
        tree = self.tmp / "tree_stay_bash"
        tree.mkdir()
        marker = self.tmp / "ready_stay"
        self.start_bash(f"touch '{marker.as_posix()}' && sleep 30", tree)
        self.wait_for(marker, "bash stays")

        failure = self.probe_rename(tree)
        say("TRIAL T3 RESULT: git bash staying in the tree -> probe rename %s"
            % ("BLOCKED: %r" % (failure,) if failure else "NOT blocked (probe is blind to it)"))

        self.assertTrue(tree.is_dir(), msg="whatever the probe saw, the folder is back where it was")

    def test_t3_a_bash_process_that_cd_s_out_of_the_tree_releases_it(self):
        tree = self.tmp / "tree_left"
        tree.mkdir()
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        marker = self.tmp / "ready_left"
        self.start_bash(f"cd '{elsewhere.as_posix()}' && touch '{marker.as_posix()}' && sleep 30", tree)
        self.wait_for(marker, "cd out")

        failure = self.probe_rename(tree)

        self.assertIsNone(failure,
                          msg="T3: once bash has changed directory out of the tree the probe rename must succeed; "
                              f"got {failure!r}. If this fails the design is unchanged: the starting tree reads "
                              "in-use and a later call clears it")
        self.assertTrue(tree.is_dir(), msg="the probe renames back, so the folder is where it was")


T5_OUTCOME: dict = {}


class T5GitWorktreeRemoveVersusALinkTests(TrialCase):
    def test_t5_records_whether_git_worktree_remove_alone_takes_a_links_target_down(self):
        """T5 (reviewer F11). Records the outcome; it asserts only that the trial ran and that its control holds.

        If git's own `worktree remove` does NOT follow a junction, the targets survive even when the cleanup never
        removed the link first, and the survival assertions of the cleanup suite prove less than they seem to; the
        recursive link scan the wrapper `git` makes at remove time is then the real guard of 'links go first'.
        The outcome is printed on stderr as "TRIAL T5 RESULT" and kept in ``T5_OUTCOME``.
        """
        repo = self.tmp / "repo"
        repo.mkdir()
        git(repo, "init", "-q", "-b", "master")
        (repo / ".gitignore").write_text("node_modules\n", encoding="utf-8")
        (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "initial")
        wt = self.tmp / "wt"
        git(repo, "worktree", "add", "-q", "-b", "w", str(wt))
        target = self.tmp / "real_node_modules"
        (target / "pkg").mkdir(parents=True)
        (target / "pkg" / "index.js").write_text("module.exports = 1;\n", encoding="utf-8")
        kind = make_directory_link(wt / "node_modules", target)
        self.assertTrue((wt / "node_modules" / "pkg" / "index.js").is_file(), msg=f"control: the {kind} works before the removal")

        removal = subprocess.run([REAL_GIT, "worktree", "remove", str(wt)], cwd=str(repo), capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", timeout=120)

        T5_OUTCOME.update({"link_kind": kind, "returncode": removal.returncode, "stderr": removal.stderr.strip()[:300],
                           "worktree_folder_still_exists": wt.exists(),
                           "target_file_survived": (target / "pkg" / "index.js").exists(),
                           "target_folder_survived": target.is_dir()})
        say("TRIAL T5 RESULT: %r" % (T5_OUTCOME,))
        self.assertIn("returncode", T5_OUTCOME, msg="T5 recorded git's behaviour on a tree holding a link")


class T4ClaudeProcessHoldsItsWorkingDirectoryTests(unittest.TestCase):
    @unittest.skip("T4 is a MANUAL trial and cannot be automated. Procedure: start a Claude Code session in the "
                   "main checkout, enter a linked worktree, run `py -3 .claude/scripts/cleanup_delivered.py "
                   "--contract <slug> --from <worktree> --dry-run`, and note in the pull request whether that "
                   "worktree read `in-use` (the Claude process holds it) or not. Either answer is safe: a "
                   "held tree is deferred and a later call clears it.")
    def test_t4_manual_trial_whether_the_claude_process_holds_its_working_directory(self):
        pass


if __name__ == "__main__":
    unittest.main()
