import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))
import check_version_bump as cvb  # noqa: E402
import plugin_doctor  # noqa: E402


class EvaluateTests(unittest.TestCase):
    def test_a_script_change_without_a_bump_fails(self):
        code, _ = cvb.evaluate([".claude/scripts/merge_direction.py"], ["0.8.6", "0.8.6"], ["0.8.6", "0.8.6"])
        self.assertEqual(code, 1)

    def test_a_script_change_with_a_higher_version_passes(self):
        code, _ = cvb.evaluate([".claude/scripts/merge_direction.py"], ["0.8.6"], ["0.8.7", "0.8.7"])
        self.assertEqual(code, 0)

    def test_disagreeing_manifests_fail(self):
        code, _ = cvb.evaluate(["skills/x/SKILL.md"], ["0.8.6"], ["0.8.7", "0.8.6"])
        self.assertEqual(code, 1)

    def test_a_lower_version_fails(self):
        code, _ = cvb.evaluate([".claude/hooks/a.py"], ["0.8.6"], ["0.8.5"])
        self.assertEqual(code, 1)

    def test_tests_briefs_and_docs_alone_need_no_bump(self):
        changed = [".claude/scripts/tests/test_a.py", ".claude/work-items/x.md", "CLAUDE.md", "README.md"]
        self.assertEqual(cvb.evaluate(changed, ["0.8.6"], ["0.8.6"])[0], 0)

    def test_orchestrator_result_records_alone_need_no_bump(self):
        changed = [".claude/orchestrator/results/2026-10-22-x/t1.yaml"]
        code, _ = cvb.evaluate(changed, ["0.8.6"], ["0.8.6"])
        self.assertEqual(code, 0)

    def test_review_records_and_gate_files_alone_need_no_bump(self):
        changed = [
            ".claude/reviews/2026-10-22-x/t2-review-fullstack-code-reviewer.md",
            ".claude/reviews/2026-10-22-x/t2-review-fullstack-code-reviewer.gate.json",
        ]
        code, _ = cvb.evaluate(changed, ["0.8.6"], ["0.8.6"])
        self.assertEqual(code, 0)

    def test_exempt_records_do_not_hide_a_shipped_change_without_a_bump(self):
        changed = [
            ".claude/orchestrator/results/2026-10-22-x/t1.yaml",
            ".claude/reviews/2026-10-22-x/t2-review-fullstack-code-reviewer.md",
            ".claude/reviews/2026-10-22-x/t2-review-fullstack-code-reviewer.gate.json",
            "skills/x/SKILL.md",
        ]
        self.assertEqual(cvb.evaluate(changed, ["0.8.6"], ["0.8.6"])[0], 1)

    def test_exempt_records_alongside_a_shipped_change_pass_when_raised(self):
        changed = [
            ".claude/orchestrator/results/2026-10-22-x/t1.yaml",
            ".claude/reviews/2026-10-22-x/t2-review-fullstack-code-reviewer.md",
            "skills/x/SKILL.md",
        ]
        self.assertEqual(cvb.evaluate(changed, ["0.8.6"], ["0.8.7"])[0], 0)

    def test_is_shipped_excludes_records_but_not_state_or_skills(self):
        self.assertFalse(cvb.is_shipped(".claude/orchestrator/results/2026-10-22-x/t1.yaml"))
        self.assertFalse(cvb.is_shipped(".claude/reviews/2026-10-22-x/t2-review-fullstack-code-reviewer.md"))
        self.assertTrue(cvb.is_shipped("skills/x/SKILL.md"))
        self.assertTrue(cvb.is_shipped(".claude/orchestrator/state/x.yaml"))
        # same-stem near-misses pin the trailing slash of each new prefix
        self.assertTrue(cvb.is_shipped(".claude/reviews-old/x.md"))
        self.assertTrue(cvb.is_shipped(".claude/orchestrator/results-archive/x.yaml"))

    def test_every_file_plugin_doctor_copies_into_projects_counts_as_shipped(self):
        sources = [r.source for r in plugin_doctor.REQUIREMENTS if r.source]
        not_shipped = [s for s in sources if not cvb.is_shipped(s)]
        self.assertEqual(not_shipped, [], f"plugin_doctor copies these into user projects but they are not shipped: {not_shipped}")
        # guard against a vacuous pass
        for expected in (
            ".claude/templates/concept-contract.md",
            ".claude/registries/MECHANISMS.md",
            ".claude/registries/VOCABULARY.md",
            ".claude/registries/JOURNAL.md",
            ".claude/project-profile.md",
        ):
            self.assertIn(expected, sources)

    def test_a_registry_change_needs_a_bump(self):
        changed = [".claude/registries/JOURNAL.md"]
        self.assertEqual(cvb.evaluate(changed, ["0.9.17"], ["0.9.17"])[0], 1)
        self.assertEqual(cvb.evaluate(changed, ["0.9.17"], ["0.9.18"])[0], 0)

    def test_files_under_exempt_folders_are_not_shipped_but_orchestrator_state_is(self):
        for exempt in (
            ".claude/concepts/x.md",
            ".claude/work-items/x.md",
            ".claude/north-stars/x.md",
            ".claude/orchestrator/results/x/y.yaml",
            ".claude/reviews/x/y.md",
        ):
            self.assertFalse(cvb.is_shipped(exempt), exempt)
        self.assertFalse(cvb.is_shipped(".github/workflows/x.yml"))
        self.assertTrue(cvb.is_shipped(".claude/orchestrator/state/x.yaml"))
        # same-stem near-misses pin the trailing slash of each exempt folder
        for near_miss in (
            ".claude/concepts-old/x.md",
            ".claude/work-items-old/x.md",
            ".claude/north-stars-old/x.md",
        ):
            self.assertTrue(cvb.is_shipped(near_miss), near_miss)

    def test_an_unreadable_version_is_never_an_allow(self):
        self.assertEqual(cvb.evaluate([".claude/hooks/a.py"], ["bad"], ["0.8.6"])[0], 2)

    def test_numeric_not_textual_comparison(self):
        self.assertEqual(cvb.evaluate([".claude/hooks/a.py"], ["0.8.9"], ["0.8.10"])[0], 0)


# ===========================================================================
# Parent Branch Delivery Rule (issue 113): the three version check modes.
#
#   default  today's check
#   parent   only for a task/<slug>/<id> head into a NON-default base: the head version must equal the
#            base's version, or the version at merge-base(origin/<default>, HEAD)
#   exact    minor + 1, patch 0, relative to origin/<default>; all entries agree
#   --raise  rewrites every MANIFESTS entry to minor + 1 / patch 0 of origin/<default>, idempotently
#
# Every case below runs the script as a PROCESS inside a throwaway git repository (a bare "origin" and a
# clone), so a missing flag or mode is an assertion about the exit code, never an ImportError. The repository
# this file lives in is never touched.
# ===========================================================================
SCRIPT = SCRIPTS_DIR / "check_version_bump.py"
# The fixtures must never reach THIS repository, even when the suite runs under a git hook (which exports
# GIT_DIR and friends): those variables are removed, and git's upward search is capped above the temp root.
_REPO_POINTING_KEYS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR")
_GIT_ENV = {k: v for k, v in os.environ.items() if k not in _REPO_POINTING_KEYS}
_GIT_ENV.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.test",
                GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.test", GIT_CONFIG_NOSYSTEM="1",
                GIT_CEILING_DIRECTORIES=str(Path(tempfile.gettempdir()).resolve().parent))


def _git(cwd, *args, check=True):
    proc = subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *args],
                          cwd=str(cwd), capture_output=True, text=True, env=_GIT_ENV)
    if check and proc.returncode != 0:
        raise AssertionError("fixture git %r failed: %s" % (args, proc.stderr))
    return proc.stdout.strip()


def manifest_files(version, description="d"):
    """The four manifest files (five version entries) at ``version``."""
    plugin = json.dumps({"name": "x", "version": version, "description": description}, indent=2) + "\n"
    market = json.dumps({"name": "m", "version": version,
                         "plugins": [{"name": "x", "version": version}]}, indent=2) + "\n"
    return {"plugin.json": plugin, ".claude-plugin/plugin.json": plugin,
            ".cursor-plugin/plugin.json": plugin, ".claude-plugin/marketplace.json": market}


def versions_on_disk(root):
    out = []
    for name in cvb.MANIFESTS:
        data = json.loads((Path(root) / name).read_text(encoding="utf-8"))
        if "version" in data:
            out.append(data["version"])
        for entry in data.get("plugins", []):
            out.append(entry["version"])
    return out


def force_rmtree(path):
    """Remove a folder holding a git repository. Git object files are read-only on Windows, so a plain
    rmtree(ignore_errors=True) silently leaves the folder behind; clear the flag and retry instead."""
    def retry(func, target, _error):
        os.chmod(target, stat.S_IWRITE)
        func(target)
    if sys.version_info >= (3, 12):
        shutil.rmtree(str(path), onexc=retry)
    else:
        shutil.rmtree(str(path), onerror=retry)


class VersionRepo:
    """A bare origin plus one working clone, both under one temporary folder that is removed on cleanup."""

    def __init__(self, case, master_version="0.10.0"):
        self.tmp = Path(tempfile.mkdtemp(prefix="vbump-"))
        case.addCleanup(force_rmtree, self.tmp)
        self.origin = self.tmp / "origin.git"
        self.work = self.tmp / "work"
        _git(self.tmp, "init", "--bare", "--initial-branch=master", str(self.origin))
        _git(self.tmp, "clone", str(self.origin), str(self.work))
        self.write(manifest_files(master_version))
        self.write({"skills/a/SKILL.md": "a\n"})
        self.commit("initial")
        self.push("master")

    def write(self, files):
        for rel, text in files.items():
            path = self.work / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")

    def commit(self, message="work"):
        _git(self.work, "add", "-A")
        _git(self.work, "commit", "-q", "-m", message)

    def push(self, branch):
        _git(self.work, "push", "-q", "origin", "HEAD:refs/heads/%s" % branch)

    def branch(self, name, start="master"):
        _git(self.work, "checkout", "-q", "-B", name, start)

    def advance_master(self, version):
        """Move origin/master to ``version`` through a commit made on master, then come back."""
        current = _git(self.work, "rev-parse", "--abbrev-ref", "HEAD")
        _git(self.work, "checkout", "-q", "master")
        _git(self.work, "pull", "-q", "origin", "master")
        self.write(manifest_files(version))
        self.commit("master moves to %s" % version)
        self.push("master")
        _git(self.work, "checkout", "-q", current)
        _git(self.work, "fetch", "-q", "origin")

    def ship_change(self, version=None, name="skills/a/SKILL.md", text="changed\n"):
        self.write({name: text})
        if version is not None:
            self.write(manifest_files(version))
        self.commit("shipped change")

    def env(self):
        """The environment the script under test is spawned with (test review W-5): a git identity, signing
        off, and an EMPTY global config, so `--raise` (which runs `git commit`) behaves the same on a
        developer machine, a fresh CI runner and a consumer, whatever their own git settings are."""
        empty = self.tmp / "empty-gitconfig"
        empty.write_text("", encoding="utf-8")
        env = dict(_GIT_ENV)
        env.update(GIT_CONFIG_GLOBAL=str(empty), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_COUNT="1",
                   GIT_CONFIG_KEY_0="commit.gpgsign", GIT_CONFIG_VALUE_0="false")
        return env

    def run(self, *args):
        proc = subprocess.run([sys.executable, "-B", str(SCRIPT), *args], cwd=str(self.work),
                              capture_output=True, text=True, timeout=120, env=self.env())
        return proc.returncode, (proc.stdout + proc.stderr).strip()


class ParentModeTests(unittest.TestCase):
    """Row 11: a sub-task pull request into the parent branch never raises the version."""

    TASK = "task/2026-10-30-demo/t1-a"

    def parent_world(self):
        """master 0.10.0 -> parent branch feature/p (pushed) -> master moves on to 0.11.0."""
        repo = VersionRepo(self)
        repo.branch("feature/p")
        repo.ship_change(name="skills/p/SKILL.md", text="parent work\n")
        repo.push("feature/p")
        repo.advance_master("0.11.0")
        repo.branch(self.TASK, "feature/p")
        return repo

    def check(self, repo, head_ref=None, base="origin/feature/p"):
        return repo.run("--base", base, "--default-branch", "master", "--head-ref", head_ref or self.TASK)

    def test_a_sub_task_that_raises_the_version_is_refused_in_parent_mode(self):
        repo = self.parent_world()
        repo.ship_change("0.10.1")  # 0.10.0 -> 0.10.1 while the default branch is at 0.11.0
        code, out = self.check(repo)
        self.assertEqual(code, 1, "a task/* head into a parent branch must keep the base's version (or the "
                                  "version at merge-base(origin/master, HEAD)); 0.10.1 is neither. got: %s" % out)

    def test_a_sub_task_that_keeps_the_parents_version_passes_with_shipped_files_changed(self):
        repo = self.parent_world()
        repo.ship_change()  # shipped file changed, version untouched at 0.10.0
        code, out = self.check(repo)
        self.assertEqual(code, 0, "parent mode: equal to the base's version is the required state, no raise. "
                                  "got: %s" % out)

    def test_a_stale_merge_of_the_default_branch_is_allowed_after_the_default_branch_moves_again(self):
        repo = self.parent_world()
        _git(repo.work, "merge", "-q", "--no-edit", "origin/master")  # head now carries 0.11.0
        repo.ship_change()
        repo.advance_master("0.12.0")  # the default branch moved after the merge
        self.assertEqual(versions_on_disk(repo.work), ["0.11.0"] * 5, "fixture sanity: the head holds 0.11.0")
        code, out = self.check(repo)
        self.assertEqual(code, 0, "the head equals the version at merge-base(origin/master, HEAD) = 0.11.0, "
                                  "so a stale merge of the default branch is allowed. got: %s" % out)

    def test_a_head_that_is_not_a_task_branch_into_a_non_default_base_is_not_checked_at_all(self):
        # Code review W1 (issue 113). Before this rule the workflow ran only for pull requests into the
        # default branch, so a stacked single-block pull request and a hand-named branch into a parent
        # branch were never checked. The contract says they are "unaffected": the CI mode must exit 0 for
        # them, with or without a raise.
        for head in ("feature/stacked", "fix/remedy-for-the-review", "docs/some-note"):
            with self.subTest(head=head):
                repo = self.parent_world()
                repo.branch(head, "feature/p")
                repo.ship_change()  # shipped change, no raise
                code, out = self.check(repo, head_ref=head)
                self.assertEqual(code, 0, "%s is not task/*, and its base is not the default branch: no "
                                          "check, exit 0. got: %s" % (head, out))
                repo.ship_change("0.10.1", text="more\n")
                code, out = self.check(repo, head_ref=head)
                self.assertEqual(code, 0, "and a raise there is not an error either. got: %s" % out)

    def test_a_head_that_is_not_a_task_branch_into_the_default_branch_keeps_the_default_rules(self):
        # Positive control for W1: the default mode is only skipped for a NON-default base.
        repo = VersionRepo(self)
        repo.branch("feature/x")
        repo.ship_change()
        code, out = repo.run("--base", "origin/master", "--default-branch", "master", "--head-ref", "feature/x")
        self.assertEqual(code, 1, "into the default branch the raise is still required. got: %s" % out)

    def test_a_task_head_into_the_default_branch_is_not_parent_mode(self):
        repo = self.parent_world()
        repo.branch(self.TASK, "master")
        repo.ship_change()  # no raise, base is the default branch
        code, out = repo.run("--base", "origin/master", "--default-branch", "master", "--head-ref", self.TASK)
        self.assertEqual(code, 1, "parent mode is only for a NON-default base; into master the raise is "
                                  "required. got: %s" % out)

    def test_positive_control_the_default_mode_without_the_new_flags_is_unchanged(self):
        repo = VersionRepo(self)
        repo.branch("feature/x")
        repo.ship_change()
        self.assertEqual(repo.run("--base", "origin/master")[0], 1, "shipped change, no raise: fails today")
        repo.ship_change("0.10.1", text="more\n")
        self.assertEqual(repo.run("--base", "origin/master")[0], 0, "raised: passes today")


class ExactModeTests(unittest.TestCase):
    """--exact: minor + 1, patch 0, relative to origin/<default>, all five entries agree."""

    def world(self, master="0.11.3"):
        repo = VersionRepo(self, master)
        repo.branch("feature/p")
        return repo

    def exact(self, repo):
        return repo.run("--exact", "--default-branch", "master")

    def test_minor_plus_one_with_patch_reset_passes(self):
        repo = self.world("0.11.3")
        repo.ship_change("0.12.0")
        code, out = self.exact(repo)
        self.assertEqual(code, 0, "0.11.3 on the default branch means exactly 0.12.0. got: %s" % out)

    def test_a_patch_raise_is_refused(self):
        repo = self.world("0.11.3")
        repo.ship_change("0.11.4")
        code, out = self.exact(repo)
        self.assertEqual(code, 1, "a landing raise is always minor (R-1); 0.11.4 is refused. got: %s" % out)

    def test_a_major_or_double_minor_raise_is_refused(self):
        for wrong in ("0.13.0", "1.0.0", "0.12.1"):
            with self.subTest(version=wrong):
                repo = self.world("0.11.3")
                repo.ship_change(wrong)
                code, out = self.exact(repo)
                self.assertEqual(code, 1, "only 0.12.0 is exact; %s is refused. got: %s" % (wrong, out))

    def test_no_raise_at_all_is_refused(self):
        repo = self.world("0.11.3")
        repo.ship_change()
        code, out = self.exact(repo)
        self.assertEqual(code, 1, "the version equals the default branch's, so it was never raised. got: %s" % out)

    def test_disagreeing_entries_are_refused_even_when_one_is_exact(self):
        repo = self.world("0.11.3")
        files = manifest_files("0.12.0")
        files[".claude-plugin/marketplace.json"] = manifest_files("0.11.3")[".claude-plugin/marketplace.json"]
        repo.write(files)
        repo.commit("one entry left behind")
        code, out = self.exact(repo)
        self.assertEqual(code, 1, "all five entries must agree. got: %s" % out)

    def test_an_unreadable_default_branch_is_never_an_allow(self):
        repo = self.world("0.11.3")
        repo.ship_change("0.12.0")
        code, out = repo.run("--exact", "--default-branch", "no-such-branch")
        self.assertEqual(code, 2, "the check could not run: exit 2, never an allow. got: %s" % out)
        self.assertTrue("VERSION BUMP" in out and "unrecognized arguments" not in out,
                        "exit 2 must come from the check reporting it could not read the default branch, "
                        "not from an unknown flag. got: %s" % out)


class RaiseTests(unittest.TestCase):
    """--raise writes minor + 1 / patch 0 of origin/<default> into every MANIFESTS entry."""

    def world(self, master="0.11.3", head="0.10.0"):
        repo = VersionRepo(self, master)
        repo.branch("feature/p")
        repo.write(manifest_files(head, description="kept"))
        repo.commit("parent branch carries an older version")
        return repo

    def test_raise_rewrites_all_five_entries_to_minor_plus_one_and_keeps_the_rest(self):
        repo = self.world()
        code, out = repo.run("--raise", "--default-branch", "master")
        self.assertEqual(code, 0, "--raise must be a known mode that succeeds. got: %s" % out)
        self.assertEqual(versions_on_disk(repo.work), ["0.12.0"] * 5,
                         "relative to the default branch's 0.11.3: minor + 1, patch 0, in every entry")
        plugin = json.loads((repo.work / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(plugin.get("description"), "kept", "only the version fields change")

    def test_raise_then_exact_agree(self):
        repo = self.world()
        self.assertEqual(repo.run("--raise", "--default-branch", "master")[0], 0, "fixture sanity")
        code, out = repo.run("--exact", "--default-branch", "master")
        self.assertEqual(code, 0, "the landing runs --raise and then --exact; they must agree. got: %s" % out)

    def test_raise_is_idempotent(self):
        repo = self.world()
        repo.run("--raise", "--default-branch", "master")
        first = {n: (repo.work / n).read_bytes() for n in cvb.MANIFESTS}
        code, out = repo.run("--raise", "--default-branch", "master")
        self.assertEqual(code, 0, "a second --raise is a no-op, not an error. got: %s" % out)
        self.assertEqual(versions_on_disk(repo.work), ["0.12.0"] * 5, "R-2: never 0.13.0 on the second run")
        self.assertEqual({n: (repo.work / n).read_bytes() for n in cvb.MANIFESTS}, first,
                         "and the files are byte-identical after the second run")

    def test_raise_follows_a_default_branch_that_moved(self):
        repo = self.world()
        repo.run("--raise", "--default-branch", "master")
        repo.advance_master("0.12.0")  # master moved while the landing verified
        code, out = repo.run("--raise", "--default-branch", "master")
        self.assertEqual(code, 0, out)
        self.assertEqual(versions_on_disk(repo.work), ["0.13.0"] * 5,
                         "R-5: the rerun recomputes against the new default branch")

    def test_an_unreadable_default_branch_changes_nothing(self):
        repo = self.world()
        before = {n: (repo.work / n).read_bytes() for n in cvb.MANIFESTS}
        code, out = repo.run("--raise", "--default-branch", "no-such-branch")
        self.assertEqual(code, 2, "could not run: exit 2. got: %s" % out)
        self.assertTrue("VERSION BUMP" in out and "unrecognized arguments" not in out,
                        "exit 2 must come from the check reporting it could not read the default branch, "
                        "not from an unknown flag. got: %s" % out)
        self.assertEqual({n: (repo.work / n).read_bytes() for n in cvb.MANIFESTS}, before,
                         "and no manifest was touched")


class EmptyDefaultBranchTests(unittest.TestCase):
    """Fix review N2: an empty --default-branch is exit 2 (the check could not run), never an allow. With
    default_ref "origin/" every base differs from it, so a non-task pull request INTO the default branch
    would otherwise skip the check and exit 0."""

    def test_the_ci_mode_with_an_empty_default_branch_exits_2(self):
        repo = VersionRepo(self)
        repo.branch("feature/x")
        repo.ship_change()  # shipped change, no raise, into master: the default rules say exit 1
        code, out = repo.run("--base", "origin/master", "--default-branch", "", "--head-ref", "feature/x")
        self.assertEqual(code, 2, "the default branch is unknown: never an allow. got: %s" % out)
        self.assertTrue("VERSION BUMP" in out and "unrecognized arguments" not in out,
                        "and the message comes from the check. got: %s" % out)

    def test_exact_and_raise_with_an_empty_default_branch_exit_2_too(self):
        repo = VersionRepo(self)
        repo.branch("feature/x")
        repo.ship_change("0.11.0")
        for mode in ("--exact", "--raise"):
            with self.subTest(mode=mode):
                code, out = repo.run(mode, "--default-branch", "")
                self.assertEqual(code, 2, "got: %s" % out)


class PaddedDefaultBranchTests(unittest.TestCase):
    """Final review N5: a padded --default-branch is stripped for the ref AND for the check."""

    def test_the_default_rules_still_apply_into_the_default_branch(self):
        repo = VersionRepo(self)
        repo.branch("feature/x")
        repo.ship_change()  # shipped change, no raise, into master: exit 1
        code, out = repo.run("--base", "origin/master", "--default-branch", " master", "--head-ref", "feature/x")
        self.assertEqual(code, 1, "' master' is master: the check must not be skipped (exit 0). got: %s" % out)

    def test_exact_reads_the_stripped_ref(self):
        repo = VersionRepo(self, "0.11.3")
        repo.branch("feature/p")
        repo.ship_change("0.12.0")
        code, out = repo.run("--exact", "--default-branch", " master ")
        self.assertEqual(code, 0, "origin/master, not 'origin/ master '. got: %s" % out)


class SpawnedScriptEnvironmentTests(unittest.TestCase):
    """Test review W-5: the script under test never reads the developer's own git configuration."""

    def git_in(self, repo, *args):
        proc = subprocess.run(["git", *args], cwd=str(repo.work), capture_output=True, text=True, env=repo.env())
        return proc.returncode, proc.stdout.strip()

    def test_the_spawned_environment_has_an_identity_no_signing_and_an_empty_global_config(self):
        repo = VersionRepo(self)
        self.assertEqual(self.git_in(repo, "config", "--global", "--list")[1], "",
                         "the global git configuration the script sees is empty")
        self.assertEqual(self.git_in(repo, "config", "--get", "commit.gpgsign")[1], "false", "signing is off")
        code, ident = self.git_in(repo, "var", "GIT_AUTHOR_IDENT")
        self.assertTrue(code == 0 and "t@example.test" in ident, "an author identity is provided: %r" % ident)

    def test_raise_commits_in_a_clone_that_has_no_identity_of_its_own(self):
        repo = VersionRepo(self, "0.11.3")
        repo.branch("feature/p")
        repo.write(manifest_files("0.10.0"))
        repo.commit("older version")
        self.assertEqual(self.git_in(repo, "config", "--local", "--get", "user.name")[0], 1,
                         "fixture sanity: the clone has no local identity")
        code, out = repo.run("--raise", "--default-branch", "master")
        self.assertEqual(code, 0, "the raise commit needs only the pinned environment. got: %s" % out)
        self.assertEqual(self.git_in(repo, "status", "--porcelain")[1], "", "and it is committed")


class ManifestsSingleSourceTests(unittest.TestCase):
    """check_version_bump.MANIFESTS is the only list of version files."""

    def test_the_four_files_are_listed_once_in_this_script(self):
        self.assertEqual(len(cvb.MANIFESTS), 4, "fixture sanity: four manifest files, five version entries")

    def test_land_contract_and_pr_merged_import_the_list_instead_of_spelling_it(self):
        for name in ("land_contract.py", "pr_merged.py"):
            with self.subTest(script=name):
                text = (SCRIPTS_DIR / name).read_text(encoding="utf-8")
                self.assertTrue("check_version_bump" in text,
                                "%s must import check_version_bump (MANIFESTS is the single path source)" % name)
                for manifest in cvb.MANIFESTS:
                    self.assertFalse('"%s"' % manifest in text,
                                     "%s spells %s itself; take it from check_version_bump.MANIFESTS" % (name, manifest))


class WorkflowTriggerTests(unittest.TestCase):
    """version-bump.yml runs on every pull request and tells the script the default branch and the head."""

    WORKFLOW = REPO_ROOT / ".github" / "workflows" / "version-bump.yml"

    def text(self):
        return self.WORKFLOW.read_text(encoding="utf-8")

    def test_the_workflow_is_not_limited_to_pull_requests_into_master(self):
        text = self.text()
        self.assertIsNone(re.search(r"(?m)^\s*branches:\s*\[\s*master\s*\]", text),
                          "the check must also run on a sub-task pull request into a parent branch "
                          "(version-bump.yml still limits pull_request to branches: [master])")
        self.assertIsNotNone(re.search(r"(?m)^\s*pull_request:", text), "it still runs on pull requests")

    def test_the_workflow_passes_the_default_branch_and_the_head_ref(self):
        text = self.text()
        self.assertTrue("--default-branch" in text, "parent and exact modes need the default branch")
        self.assertTrue("--head-ref" in text, "parent mode needs the head ref")
        self.assertTrue("github.head_ref" in text, "the head ref comes from the event")
        self.assertTrue("--base origin/${{ github.base_ref }}" in text or "$BASE_REF" in text
                        or "${BASE_REF}" in text, "the base is still the pull request's base")

    # Code review W2: a pull request's head ref is attacker-chosen text. GitHub substitutes ${{ }} BEFORE
    # the shell runs, and a git ref may hold ; | $ ( ) ` so it must travel through env: and be quoted.
    def steps(self):
        import yaml
        data = yaml.safe_load(self.text())
        found = []
        for job in (data.get("jobs") or {}).values():
            found.extend(job.get("steps") or [])
        return data, found

    def test_no_run_line_interpolates_a_pull_request_controlled_expression(self):
        _data, steps = self.steps()
        runs = [s for s in steps if s.get("run")]
        self.assertTrue(runs, "fixture sanity: the workflow has a run: step")
        for step in runs:
            script = step["run"]
            for expression in re.findall(r"\$\{\{(.*?)\}\}", script, re.S):
                self.assertIsNone(
                    re.search(r"head_ref|event\.pull_request|head\.ref|\.title|\.body", expression),
                    "run: must not interpolate %r; pass it through env: and quote it" % expression.strip())

    def test_the_refs_go_through_env_and_are_quoted_in_the_run_line(self):
        _data, steps = self.steps()
        step = next((s for s in steps if s.get("run")), {})
        env = step.get("env") or {}
        self.assertTrue(any("github.head_ref" in str(v) for v in env.values()),
                        "the head ref is handed to the step through env:. env was %r" % (env,))
        self.assertIsNotNone(re.search(r'--head-ref\s+"\$\{?[A-Za-z_]+\}?"', step.get("run", "")),
                             'the run line passes the head ref as a quoted variable: --head-ref "$HEAD_REF"')

    def test_the_workflow_declares_read_only_contents_permission(self):
        data, _steps = self.steps()
        job_permissions = [job.get("permissions") for job in (data.get("jobs") or {}).values()]
        permissions = data.get("permissions") or next((p for p in job_permissions if p), None)
        self.assertEqual(permissions, {"contents": "read"},
                         "the job gets no write access it does not use (permissions: contents: read)")


class ParentModeFunctionTests(unittest.TestCase):
    """Issue 240: the parent-mode predicate and the allowed-versions reader are shared functions (INV-O1 row
    and main() both call them). A missing function is an assertion failure naming it, never an AttributeError."""

    DEFAULT = "origin/master"
    TASK = "task/demo/t1"

    def need(self, name):
        self.assertTrue(hasattr(cvb, name),
                        "check_version_bump.%s does not exist yet: lift it out of main()'s inline parent branch" % name)
        return getattr(cvb, name)

    def test_a_task_head_into_a_non_default_base_is_parent_mode(self):
        is_parent_mode = self.need("is_parent_mode")
        self.assertIs(is_parent_mode(self.TASK, "origin/feature/p", self.DEFAULT), True,
                      "task/<slug>/<id> into a base that is not origin/master is parent mode")

    def test_a_task_head_into_the_default_base_is_not_parent_mode(self):
        is_parent_mode = self.need("is_parent_mode")
        self.assertIs(is_parent_mode(self.TASK, self.DEFAULT, self.DEFAULT), False,
                      "a task head whose base IS the default ref keeps the default rules")

    def test_a_task_head_with_an_absent_base_is_parent_mode(self):
        is_parent_mode = self.need("is_parent_mode")
        self.assertIs(is_parent_mode(self.TASK, None, self.DEFAULT), True,
                      "an absent base counts as not-the-default (a local task head targets its parent branch)")

    def test_a_non_task_head_is_never_parent_mode(self):
        is_parent_mode = self.need("is_parent_mode")
        for head in ("fix/demo", "task/demo"):
            for base in ("origin/feature/p", self.DEFAULT, None):
                with self.subTest(head=head, base=base):
                    self.assertIs(is_parent_mode(head, base, self.DEFAULT), False,
                                  "only a task/<slug>/<id> head can be in parent mode (head %r, base %r)" % (head, base))
        self.assertIs(is_parent_mode("", None, self.DEFAULT), False, "an empty head ref is not parent mode")

    def build_repo(self, tmp, parent_version=None):
        """A throwaway repo: master at 1.2.3 (also origin/master); optionally origin/parent at parent_version."""
        repo = Path(tmp) / "repo"
        repo.mkdir()
        _git(repo, "init", "-q")
        _git(repo, "checkout", "-q", "-b", "master")
        for name, text in manifest_files("1.2.3").items():
            target = repo / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "base")
        _git(repo, "update-ref", "refs/remotes/origin/master", "HEAD")
        if parent_version:
            _git(repo, "checkout", "-q", "-b", "feature/p")
            for name, text in manifest_files(parent_version).items():
                (repo / name).write_text(text, encoding="utf-8")
            _git(repo, "commit", "-q", "-am", "parent")
            _git(repo, "update-ref", "refs/remotes/origin/feature/p", "HEAD")
            _git(repo, "checkout", "-q", "-b", self.TASK)
        return repo

    def test_parent_allowed_versions_without_a_base_reads_only_the_merge_base_step(self):
        reader = self.need("parent_allowed_versions")
        tmp = tempfile.mkdtemp(prefix="pav-none-")
        try:
            repo = self.build_repo(tmp)
            self.assertEqual(reader(None, self.DEFAULT, cwd=str(repo)), ["1.2.3"] * 5,
                             "base None: only the five versions at merge-base(origin/master, HEAD), no base step")
        finally:
            force_rmtree(tmp)

    def test_parent_allowed_versions_with_a_base_lists_the_base_then_the_merge_base(self):
        reader = self.need("parent_allowed_versions")
        tmp = tempfile.mkdtemp(prefix="pav-base-")
        try:
            repo = self.build_repo(tmp, parent_version="1.3.0")
            self.assertEqual(reader("origin/feature/p", self.DEFAULT, cwd=str(repo)),
                             ["1.3.0"] * 5 + ["1.2.3"] * 5,
                             "the base's versions come first, then the merge-base's")
        finally:
            force_rmtree(tmp)

    def test_parent_allowed_versions_raises_when_git_fails(self):
        reader = self.need("parent_allowed_versions")
        tmp = tempfile.mkdtemp(prefix="pav-fail-")
        try:
            with self.assertRaises(subprocess.CalledProcessError,
                                   msg="a failed git call is raised, never returned as an empty list"):
                reader(None, self.DEFAULT, cwd=tmp)  # not a repository
        finally:
            force_rmtree(tmp)


# ===========================================================================
# Manifest counts (contract 2026-11-14-manifest-counts-landing-refresh).
#
# The count rule, the Count verdict, the Landing count refresh (--raise / --exact with --manifest-counts), the
# version-free --counts mode, and the Count deferral predicate. Process runs inside a throwaway repository, like
# the version modes above, so a missing flag is an assertion about an exit code, never an AttributeError.
# ===========================================================================
def counted_tree(skills, agents, hooks):
    """Tracked files that give exactly these counts (plus files the rules must NOT count)."""
    files = {}
    for i in range(skills):
        files["skills/s%d/SKILL.md" % i] = "s\n"
    for i in range(agents):
        files["agents/a%d.md" % i] = "a\n"
    for i in range(hooks):
        files[".claude/hooks/h%d.py" % i] = "h\n"
    files[".claude/hooks/_helper.py"] = "helper\n"
    files[".claude/hooks/gate-launch.py"] = "launcher\n"
    files[".claude/hooks/hooks.json"] = "{}\n"
    return files


def counted_manifests(version, skills, agents, hooks, overrides=None):
    """The four manifests with count claims. ``overrides`` maps a manifest name to a description, or to raw file
    text when the value starts with ``RAW:``."""
    overrides = overrides or {}
    descriptions = {
        "plugin.json": "Protocol: %d skills that put design first." % skills,
        ".claude-plugin/plugin.json": "Protocol: %d skills, %d agents and %d hooks that put design first."
                                      % (skills, agents, hooks),
        ".cursor-plugin/plugin.json": "Protocol: %d skills and %d subagents that put design first." % (skills, agents),
    }
    descriptions[".claude-plugin/marketplace.json"] = descriptions[".claude-plugin/plugin.json"]
    descriptions.update({k: v for k, v in overrides.items() if not v.startswith("RAW:")})

    def one(desc):
        return json.dumps({"name": "x", "version": version, "description": desc}, indent=2) + "\n"

    files = {name: one(descriptions[name]) for name in ("plugin.json", ".claude-plugin/plugin.json",
                                                         ".cursor-plugin/plugin.json")}
    files[".claude-plugin/marketplace.json"] = json.dumps(
        {"name": "m", "version": version, "description": "A marketplace.",
         "plugins": [{"name": "x", "version": version, "description": descriptions[".claude-plugin/marketplace.json"]}]},
        indent=2) + "\n"
    files.update({k: v[len("RAW:"):] for k, v in overrides.items() if v.startswith("RAW:")})
    return files


class CountsWorldMixin:
    """A parent branch feature/p whose tracked tree holds ``tree`` counts and whose manifests claim ``claims``."""

    def counts_world(self, tree=(4, 3, 3), claims=(3, 2, 2), master="0.11.3", head_version="0.10.0", overrides=None):
        repo = VersionRepo(self, master)
        repo.branch("feature/p")
        (repo.work / "skills" / "a" / "SKILL.md").unlink()
        repo.write(counted_tree(*tree))
        repo.write(counted_manifests(head_version, *claims, overrides=overrides))
        repo.commit("parent branch: counted tree and manifests")
        return repo

    def on_disk(self, repo):
        return {n: (repo.work / n).read_bytes() for n in cvb.MANIFESTS}

    def head(self, repo):
        return _git(repo.work, "rev-parse", "HEAD")

    def subject(self, repo):
        return _git(repo.work, "log", "-1", "--format=%s")

    def commits(self, repo):
        return int(_git(repo.work, "rev-list", "--count", "HEAD"))


class CountRuleTests(unittest.TestCase):
    """The three path rules over a path list: case-sensitive (D2), one segment, never disk or git."""

    def need(self, name):
        self.assertTrue(hasattr(cvb, name), "check_version_bump.%s does not exist yet" % name)
        return getattr(cvb, name)

    def test_d2_the_rule_is_case_sensitive(self):
        count = self.need("measure_count")
        self.assertEqual(count("skills", ["skills/a/skill.md"]), 0, "skill.md is not SKILL.md")
        self.assertEqual(count("skills", ["skills/a/SKILL.md"]), 1, "control: SKILL.md counts")
        self.assertEqual(count("hooks", [".claude/hooks/X.PY"]), 0, "X.PY is not a .py file")
        self.assertEqual(count("hooks", [".claude/hooks/x.py"]), 1, "control: x.py counts")
        self.assertEqual(count("agents", ["agents/a.MD"]), 0, "a.MD is not a .md file")
        self.assertEqual(count("agents", ["agents/a.md"]), 1, "control: a.md counts")

    def test_nested_misnamed_and_excluded_paths_do_not_count(self):
        count = self.need("measure_count")
        self.assertEqual(count("skills", ["skills/a/b/SKILL.md", "skills/SKILL.md", "skills//SKILL.md",
                                          "skills/a/README.md", "xskills/a/SKILL.md"]), 0)
        self.assertEqual(count("agents", ["agents/sub/a.md", "agents/a.txt", "xagents/a.md"]), 0)
        self.assertEqual(count("hooks", [".claude/hooks/_helper.py", ".claude/hooks/gate-launch.py",
                                         ".claude/hooks/tests/t.py", ".claude/hooks/hooks.json",
                                         ".claude/other/x.py"]), 0)

    def test_the_rule_counts_each_path_once_and_rejects_an_unknown_measure(self):
        count = self.need("measure_count")
        self.assertEqual(count("skills", ["skills/a/SKILL.md", "skills/a/SKILL.md", "skills/b/SKILL.md"]), 2)
        with self.assertRaises(ValueError):
            count("agreements", [])

    def test_the_measure_roots_are_one_shared_constant_each(self):
        self.assertEqual((self.need("SKILLS_ROOT"), self.need("AGENTS_ROOT"), self.need("HOOKS_ROOT")),
                         ("skills/", "agents/", ".claude/hooks/"))


class NonDefaultBaseTests(unittest.TestCase):
    """I-6: one base comparison, and the Count deferral built on the parent predicate."""

    DEFAULT = "master"
    TASK = "task/demo/t1"

    def need(self, name):
        self.assertTrue(hasattr(cvb, name), "check_version_bump.%s does not exist yet" % name)
        return getattr(cvb, name)

    def test_is_non_default_base(self):
        f = self.need("is_non_default_base")
        self.assertIs(f("feature/p", "master"), True)
        self.assertIs(f("master", "master"), False)
        self.assertIs(f(None, "master"), True, "an absent base is not the default")

    def test_is_parent_mode_is_unchanged_over_its_rows(self):
        for head, base, expected in ((self.TASK, "origin/feature/p", True), (self.TASK, "origin/master", False),
                                     (self.TASK, None, True), ("fix/demo", "origin/feature/p", False),
                                     ("task/demo", None, False), ("", None, False)):
            with self.subTest(head=head, base=base):
                self.assertIs(cvb.is_parent_mode(head, base, "origin/master"), expected)

    def test_the_deferral_rows(self):
        f = self.need("count_pin_deferred")
        rows = (
            (self.TASK, "feature/p", True, "a sub-task head into the parent"),
            (self.TASK, "master", False, "a task head into the default branch"),
            (self.TASK, None, True, "a task head with no base (a local run)"),
            ("feature/x", "feature/p", True, "a hand-named head into a non-default base"),
            ("feature/x", "master", False, "any head into the default branch"),
            ("feature/x", None, False, "a non-task head with no base"),
            ("fix/y", "master", False, "a single block into the default branch"),
        )
        for head, base, expected, why in rows:
            with self.subTest(why=why):
                self.assertIs(f(head, base, self.DEFAULT), expected, why)

    def test_an_unknown_default_branch_never_defers(self):
        f = self.need("count_pin_deferred")
        for default in ("", " ", "\t\n", None):
            for head in (self.TASK, "feature/x", ""):
                for base in (None, "feature/p", "master", ""):
                    with self.subTest(default=default, head=head, base=base):
                        self.assertIs(f(head, base, default), False,
                                      "I-6 guard: with no default branch known the pin is full, whatever the head and base")

    def test_the_predicate_spells_neither_the_task_pattern_nor_the_comparison(self):
        import ast
        import inspect
        import textwrap
        function = ast.parse(textwrap.dedent(inspect.getsource(self.need("count_pin_deferred")))).body[0]
        if ast.get_docstring(function) is not None:
            function.body = function.body[1:]  # the code, not its docstring
        code = ast.unparse(function)
        self.assertNotIn("TASK_HEAD", code)
        self.assertNotIn("!=", code)
        self.assertNotIn("==", code)
        self.assertIn("is_parent_mode", code)
        self.assertIn("is_non_default_base", code)


class ModifierGrammarTests(unittest.TestCase, CountsWorldMixin):
    """I-5: --manifest-counts rides on --raise or --exact only; --counts is its own mode."""

    def test_manifest_counts_is_refused_without_raise_or_exact(self):
        repo = self.counts_world()
        for args in (["--manifest-counts"], ["--manifest-counts", "--counts"],
                     ["--manifest-counts", "--default-branch", "master"]):
            with self.subTest(args=args):
                code, out = repo.run(*args)
                self.assertEqual(code, 2, "got: %s" % out)
                self.assertIn("--manifest-counts", out)
                self.assertNotIn("unrecognized arguments", out, "the refusal comes from the check, not argparse")

    def test_counts_is_mutually_exclusive_with_the_other_modes(self):
        repo = self.counts_world()
        for other in ("--raise", "--exact"):
            with self.subTest(other=other):
                code, out = repo.run("--counts", other, "--default-branch", "master")
                self.assertEqual(code, 2, "argparse refuses two modes: %s" % out)
                self.assertIn("not allowed with", out)


class LandingCountRefreshTests(unittest.TestCase, CountsWorldMixin):
    """--raise --manifest-counts: the version and the counts in one commit, numbers only, all or nothing."""

    RAISE = ("--raise", "--manifest-counts", "--default-branch", "master")

    def test_each_noun_is_rewritten_from_the_tree(self):
        repo = self.counts_world(tree=(4, 3, 3), claims=(3, 2, 2))
        code, out = repo.run(*self.RAISE)
        self.assertEqual(code, 0, "got: %s" % out)
        expected = counted_manifests("0.12.0", 4, 3, 3)
        for name in cvb.MANIFESTS:
            with self.subTest(manifest=name):
                self.assertEqual((repo.work / name).read_text(encoding="utf-8"), expected[name],
                                 "skills, agents, subagents and hooks claims follow the tree; the version is raised")
        self.assertEqual(versions_on_disk(repo.work), ["0.12.0"] * 5)

    def test_every_byte_outside_the_numbers_is_unchanged(self):
        # irregular layout: tabs, key order, escaped non-ASCII letters, a trailing space, no final newline; and a
        # second manifest that holds the same kind of letters raw (UTF-8), the other spelling the refresh can locate
        raw = ('{"version" :\t"0.10.0", "keywords": ["a" , "b"],\n'
               '  "description"  : "Caf\\u00e9 \\u2014 3 skills, 2 agents and 2 hooks that do things. \\u00fc",\n'
               '"x":   [1,2,3]}  ')
        raw_utf8 = '{"name":"x",\t"version" :"0.10.0",\n"description":"Caf\u00e9 \u2014 3 skills and 2 subagents \u00fc"}\n'
        repo = self.counts_world(overrides={".claude-plugin/plugin.json": "RAW:" + raw,
                                            ".cursor-plugin/plugin.json": "RAW:" + raw_utf8})
        before = self.on_disk(repo)
        code, out = repo.run(*self.RAISE)
        self.assertEqual(code, 0, "got: %s" % out)
        after = self.on_disk(repo)
        for name in cvb.MANIFESTS:
            with self.subTest(manifest=name):
                self.assertEqual(re.sub(rb"\d+", b"#", after[name]), re.sub(rb"\d+", b"#", before[name]),
                                 "only number characters differ, whatever the layout")
        changed = after[".claude-plugin/plugin.json"].decode("utf-8")
        self.assertIn("4 skills, 3 agents and 3 hooks", changed)
        self.assertIn('"x":   [1,2,3]}  ', changed, "the unrelated arrays keep their digits")
        self.assertTrue(changed.startswith('{"version" :\t"0.12.0", "keywords"'))
        self.assertIn("Caf\\u00e9 \\u2014 4 skills", changed, "the escapes stay escapes")
        cursor = after[".cursor-plugin/plugin.json"].decode("utf-8")
        self.assertIn("Café — 4 skills and 3 subagents ü", cursor, "and the raw letters stay raw")

    def test_a_spelled_count_is_written_as_the_word_for_the_new_value(self):
        repo = self.counts_world(tree=(4, 3, 3), claims=(3, 2, 2), overrides={
            "plugin.json": "Protocol: three skills that put design first.",
            ".claude-plugin/plugin.json": "Protocol: Three skills, TWO agents and two hooks that put design first.",
        })
        code, out = repo.run(*self.RAISE)
        self.assertEqual(code, 0, "got: %s" % out)
        self.assertIn("four skills", (repo.work / "plugin.json").read_text(encoding="utf-8"))
        text = (repo.work / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        self.assertIn("Four skills, THREE agents and three hooks", text, "the word keeps its case")

    def test_a_claim_that_is_already_true_is_left_alone(self):
        repo = self.counts_world(tree=(3, 2, 2), claims=(3, 2, 2))
        code, out = repo.run(*self.RAISE)
        self.assertEqual(code, 0, "got: %s" % out)
        expected = counted_manifests("0.12.0", 3, 2, 2)
        self.assertEqual({n: (repo.work / n).read_text(encoding="utf-8") for n in cvb.MANIFESTS}, expected)

    def test_the_three_commit_messages(self):
        # version and counts
        repo = self.counts_world(tree=(4, 3, 3), claims=(3, 2, 2))
        self.assertEqual(repo.run(*self.RAISE)[0], 0)
        self.assertEqual(self.subject(repo), "chore: raise the plugin version to 0.12.0 and refresh the manifest counts at the landing")
        # version only: no count changed
        repo = self.counts_world(tree=(3, 2, 2), claims=(3, 2, 2))
        self.assertEqual(repo.run(*self.RAISE)[0], 0)
        self.assertEqual(self.subject(repo), "chore: raise the plugin version to 0.12.0 at the landing")
        # counts only: the version is already raised
        repo = self.counts_world(tree=(4, 3, 3), claims=(3, 2, 2))
        self.assertEqual(repo.run("--raise", "--default-branch", "master")[0], 0, "plain raise first")
        self.assertEqual(versions_on_disk(repo.work), ["0.12.0"] * 5)
        before = self.commits(repo)
        code, out = repo.run(*self.RAISE)
        self.assertEqual(code, 0, "got: %s" % out)
        self.assertEqual(self.commits(repo), before + 1)
        self.assertEqual(self.subject(repo), "chore: refresh the manifest counts at the landing")

    def test_a_second_run_changes_nothing(self):
        repo = self.counts_world()
        self.assertEqual(repo.run(*self.RAISE)[0], 0)
        head, bytes_ = self.head(repo), self.on_disk(repo)
        code, out = repo.run(*self.RAISE)
        self.assertEqual(code, 0, "got: %s" % out)
        self.assertEqual((self.head(repo), self.on_disk(repo)), (head, bytes_), "no new commit, no new byte")
        self.assertEqual(repo.run("--exact", "--manifest-counts", "--default-branch", "master")[0], 0)

    def test_without_the_flag_the_counts_stay_stale(self):
        repo = self.counts_world(tree=(4, 3, 3), claims=(3, 2, 2))
        code, out = repo.run("--raise", "--default-branch", "master")
        self.assertEqual(code, 0, "got: %s" % out)
        self.assertEqual({n: (repo.work / n).read_text(encoding="utf-8") for n in cvb.MANIFESTS},
                         counted_manifests("0.12.0", 3, 2, 2), "today's raise writes the version fields only")
        self.assertEqual(self.subject(repo), "chore: raise the plugin version to 0.12.0 at the landing")


class CountRefusalTests(unittest.TestCase, CountsWorldMixin):
    """Each Count refusal: named in the output, exit 1 (description) or 2 (read), nothing written, nothing committed."""

    def refuse(self, reason, code_wanted, repo, args=("--raise", "--manifest-counts", "--default-branch", "master")):
        before, head = self.on_disk(repo), self.head(repo)
        code, out = repo.run(*args)
        self.assertEqual(code, code_wanted, "got: %s" % out)
        self.assertIn("count refresh refused (%s)" % reason if "--raise" in args else "(%s)" % reason, out)
        self.assertNotIn("unrecognized arguments", out)
        self.assertEqual(self.on_disk(repo), before, "no manifest was written")
        self.assertEqual(self.head(repo), head, "nothing was committed")
        return out

    def test_count_missing(self):
        repo = self.counts_world(overrides={".claude-plugin/plugin.json": "Protocol: 3 skills and some agents and 2 hooks."})
        out = self.refuse("count-missing", 1, repo)
        self.assertIn(".claude-plugin/plugin.json", out)
        self.assertIn("agents", out)

    def test_count_unrefreshable_noun(self):
        repo = self.counts_world(overrides={
            ".claude-plugin/plugin.json": "Protocol: 3 skills, 2 agents, 2 hooks and 3 add-ons."})
        out = self.refuse("count-unrefreshable-noun", 1, repo)
        self.assertIn("add-ons", out)

    def test_count_unwritable(self):
        repo = self.counts_world(tree=(21, 3, 3), claims=(20, 2, 2), overrides={
            "plugin.json": "Protocol: twenty skills that put design first."})
        out = self.refuse("count-unwritable", 1, repo)
        self.assertIn("plugin.json", out)

    def test_count_reader_disagreement(self):
        repo = self.counts_world(overrides={
            ".claude-plugin/plugin.json": "Protocol: 3 skills, 2 agents and 2 hooks; it retired 6 hooks."})
        self.refuse("count-reader-disagreement", 1, repo)

    def test_the_hook_files_noun_is_read_by_one_reader_only(self):
        repo = self.counts_world(overrides={
            ".claude-plugin/plugin.json": "Protocol: 3 skills, 2 agents and 2 hooks, 14 hook files."})
        self.refuse("count-reader-disagreement", 1, repo)

    def test_description_not_located(self):
        # an upper-case hex escape is neither of the two spellings json.dumps would write
        raw = ('{"name": "x", "version": "0.10.0",\n  "description": "Caf\\u00E9: 3 skills, 2 agents and 2 hooks."}\n')
        repo = self.counts_world(overrides={".claude-plugin/plugin.json": "RAW:" + raw})
        self.refuse("description-not-located", 1, repo)

    def test_oracle_empty(self):
        repo = self.counts_world(tree=(4, 3, 0), claims=(3, 2, 2))
        self.refuse("oracle-empty", 2, repo)

    def test_oracle_unreadable(self):
        import contextlib
        import io
        from unittest import mock
        repo = self.counts_world()
        before, head = self.on_disk(repo), self.head(repo)
        out = io.StringIO()
        cwd = os.getcwd()
        os.chdir(str(repo.work))
        self.addCleanup(os.chdir, cwd)
        error = subprocess.CalledProcessError(128, ["git", "ls-tree"], stderr="fatal")
        with mock.patch.object(cvb, "tree_paths", side_effect=error), contextlib.redirect_stdout(out):
            code = cvb.main(["--raise", "--manifest-counts", "--default-branch", "master"])
        self.assertEqual(code, 2, out.getvalue())
        self.assertIn("count refresh refused (oracle-unreadable)", out.getvalue())
        self.assertEqual((self.on_disk(repo), self.head(repo)), (before, head))

    def test_an_unreadable_manifest_exits_2_and_writes_nothing(self):
        repo = self.counts_world(overrides={".cursor-plugin/plugin.json": "RAW:{not json"})
        before, head = self.on_disk(repo), self.head(repo)
        code, out = repo.run("--raise", "--manifest-counts", "--default-branch", "master")
        self.assertEqual(code, 2, "got: %s" % out)
        self.assertIn("VERSION BUMP", out)
        self.assertNotIn("unrecognized arguments", out)
        self.assertEqual((self.on_disk(repo), self.head(repo)), (before, head))

    def test_one_refusal_blocks_the_other_manifests_too(self):
        # plugin.json is refreshable, the cursor manifest is not: all or nothing
        repo = self.counts_world(overrides={".cursor-plugin/plugin.json": "Protocol: 3 skills and some subagents."})
        self.refuse("count-missing", 1, repo)

    def test_the_same_refusals_stop_counts_and_exact_with_the_same_exit_codes(self):
        cases = (
            ("count-missing", 1, {".claude-plugin/plugin.json": "Protocol: 4 skills and some agents and 3 hooks."}, (4, 3, 3)),
            ("count-unrefreshable-noun", 1, {".claude-plugin/plugin.json": "Protocol: 4 skills, 3 agents, 3 hooks, 3 add-ons."}, (4, 3, 3)),
            ("oracle-empty", 2, {}, (4, 3, 0)),
        )
        for reason, code_wanted, overrides, tree in cases:
            for args in (("--counts",), ("--exact", "--manifest-counts", "--default-branch", "master")):
                with self.subTest(reason=reason, args=args):
                    repo = self.counts_world(tree=tree, claims=tree, head_version="0.12.0", overrides=overrides)
                    before, head = self.on_disk(repo), self.head(repo)
                    code, out = repo.run(*args)
                    self.assertEqual(code, code_wanted, "got: %s" % out)
                    self.assertIn(reason, out)
                    self.assertEqual((self.on_disk(repo), self.head(repo)), (before, head), "nothing is ever written")


class CountsModeTests(unittest.TestCase, CountsWorldMixin):
    """--counts: HEAD's manifests against HEAD's tree. No version, no base, no origin ref, no write."""

    def test_true_counts_exit_0_and_stale_counts_exit_1(self):
        repo = self.counts_world(tree=(3, 2, 2), claims=(3, 2, 2))
        code, out = repo.run("--counts")
        self.assertEqual(code, 0, "got: %s" % out)
        self.assertNotIn("unrecognized arguments", out)
        repo = self.counts_world(tree=(4, 2, 2), claims=(3, 2, 2))
        before = self.on_disk(repo)
        code, out = repo.run("--counts")
        self.assertEqual(code, 1, "one skill more than the description says: %s" % out)
        self.assertIn("3", out)
        self.assertIn("skills", out)
        self.assertEqual(self.on_disk(repo), before, "--counts writes nothing")

    def test_it_passes_on_a_default_branch_checkout_that_holds_true_counts(self):
        repo = VersionRepo(self, "0.11.3")  # master itself: no feature branch, no raise
        (repo.work / "skills" / "a" / "SKILL.md").unlink()
        repo.write(counted_tree(3, 2, 2))
        repo.write(counted_manifests("0.11.3", 3, 2, 2))
        repo.commit("true counts on the default branch")
        code, out = repo.run("--counts")
        self.assertEqual(code, 0, "baseline recording runs this step on master: %s" % out)

    def test_it_reads_no_version_no_base_and_no_origin_ref(self):
        repo = self.counts_world(tree=(3, 2, 2), claims=(3, 2, 2), head_version="not-a-version")
        _git(repo.work, "remote", "remove", "origin")
        code, out = repo.run("--counts", "--default-branch", "no-such-branch", "--base", "origin/none")
        self.assertEqual(code, 0, "got: %s" % out)

    def test_it_reads_the_committed_head_not_the_working_tree(self):
        repo = self.counts_world(tree=(3, 2, 2), claims=(3, 2, 2))
        repo.write(counted_manifests("0.10.0", 99, 99, 99))  # uncommitted edit
        code, out = repo.run("--counts")
        self.assertEqual(code, 0, "HEAD holds true counts: %s" % out)

    def test_a_tracked_deletion_not_yet_committed_does_not_change_the_listing(self):
        repo = self.counts_world(tree=(3, 2, 2), claims=(3, 2, 2))
        (repo.work / "skills" / "s0" / "SKILL.md").unlink()
        code, out = repo.run("--counts")
        self.assertEqual(code, 0, "the tree listing is HEAD's: %s" % out)


class ExactWithCountsTests(unittest.TestCase, CountsWorldMixin):
    """--exact --manifest-counts: the exit is the higher of the version exit and the count exit."""

    def pair(self, version_exit, count_exit):
        tree = (4, 3, 0) if count_exit == 2 else (4, 3, 3)
        claims = (3, 3, 3) if count_exit == 1 else (4, 3, 3)
        version = "0.12.0" if version_exit == 0 else "0.11.3"
        repo = self.counts_world(tree=tree, claims=claims, head_version=version)
        default = "no-such-branch" if version_exit == 2 else "master"
        return repo.run("--exact", "--manifest-counts", "--default-branch", default)

    def test_every_pair_gives_the_higher_code(self):
        for version_exit in (0, 1, 2):
            for count_exit in (0, 1, 2):
                with self.subTest(version=version_exit, counts=count_exit):
                    code, out = self.pair(version_exit, count_exit)
                    self.assertEqual(code, max(version_exit, count_exit), "got: %s" % out)
                    self.assertNotIn("unrecognized arguments", out)

    def test_both_verdicts_are_printed(self):
        code, out = self.pair(1, 1)
        self.assertEqual(code, 1)
        self.assertIn("landing version must be exactly 0.12.0", out)
        self.assertRegex(out, r"(?i)3 skills")


class LandingCountPlanTests(unittest.TestCase):
    """The pure planner behind --raise, --counts and --exact: one Count verdict (I-4)."""

    MANIFEST = json.dumps({"version": "1.0.0", "description": "Protocol: 3 skills, 2 agents and 2 hooks."}, indent=2)

    def need(self, name):
        self.assertTrue(hasattr(cvb, name), "check_version_bump.%s does not exist yet" % name)
        return getattr(cvb, name)

    def texts(self, description):
        text = json.dumps({"version": "1.0.0", "description": description}, indent=2)
        return {".claude-plugin/plugin.json": text}

    def test_a_true_description_gives_an_empty_plan(self):
        plan = self.need("plan_counts")(self.texts("Protocol: 3 skills, 2 agents and 2 hooks."),
                                        {"skills": 3, "agents": 2, "hooks": 2})
        self.assertEqual((plan.refusals, plan.mismatches, plan.rewrites), ([], [], []))

    def test_a_stale_description_is_rewritten_and_reported(self):
        plan = self.need("plan_counts")(self.texts("Protocol: 3 skills, 2 agents and 2 hooks."),
                                        {"skills": 5, "agents": 2, "hooks": 2})
        self.assertEqual(plan.refusals, [])
        self.assertEqual(len(plan.mismatches), 1)
        self.assertIn("5 skills, 2 agents and 2 hooks", plan.texts[".claude-plugin/plugin.json"])
        self.assertEqual(plan.rewrites, [(".claude-plugin/plugin.json", "skills", 3, 5)])

    def test_the_exit_code_of_a_plan(self):
        plan_counts, code = self.need("plan_counts"), self.need("count_exit_code")
        measures = {"skills": 3, "agents": 2, "hooks": 2}
        self.assertEqual(code(plan_counts(self.texts("3 skills, 2 agents and 2 hooks"), measures)), 0)
        self.assertEqual(code(plan_counts(self.texts("4 skills, 2 agents and 2 hooks"), measures)), 1, "equality failure")
        self.assertEqual(code(plan_counts(self.texts("3 skills and 2 hooks"), measures)), 1, "count-missing")
        self.assertEqual(code(plan_counts(self.texts("3 skills, 2 agents and 2 hooks"), dict(measures, hooks=0))), 2,
                         "oracle-empty is a read refusal")
        self.assertEqual(code(plan_counts(self.texts("3 skills, 2 agents and 2 hooks"), None, "no listing")), 2,
                         "oracle-unreadable is a read refusal")

    def test_a_plan_reports_every_refusal_it_finds(self):
        plan = self.need("plan_counts")(self.texts("Protocol: 3 skills, 2 agents, 3 add-ons and some hooks."),
                                        {"skills": 3, "agents": 2, "hooks": 2})
        self.assertEqual({r.reason for r in plan.refusals}, {"count-unrefreshable-noun", "count-missing"})
        self.assertEqual({r.kind for r in plan.refusals}, {"description"})


if __name__ == "__main__":
    unittest.main()
