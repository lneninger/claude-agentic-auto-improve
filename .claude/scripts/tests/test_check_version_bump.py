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
_GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.test",
                GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.test", GIT_CONFIG_NOSYSTEM="1")


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

    def run(self, *args):
        proc = subprocess.run([sys.executable, "-B", str(SCRIPT), *args], cwd=str(self.work),
                              capture_output=True, text=True, timeout=120)
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

    def test_a_head_that_is_not_a_task_branch_keeps_the_default_rules_even_into_a_parent_base(self):
        repo = self.parent_world()
        repo.branch("feature/stacked", "feature/p")
        repo.ship_change()  # shipped change, no raise
        code, out = self.check(repo, head_ref="feature/stacked")
        self.assertEqual(code, 1, "a stacked pull request of single-block work is not a task/* head, so it "
                                  "still needs its raise. got: %s" % out)
        repo.ship_change("0.10.1", text="more\n")
        code, out = self.check(repo, head_ref="feature/stacked")
        self.assertEqual(code, 0, "and passes once it raises, exactly as today. got: %s" % out)

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
        self.assertTrue("--base origin/${{ github.base_ref }}" in text,
                        "the base is still the pull request's base")


if __name__ == "__main__":
    unittest.main()
