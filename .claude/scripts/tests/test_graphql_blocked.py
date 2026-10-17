"""test_graphql_blocked.py -- gh's GraphQL commands fail with the cloud-session 403; REST still works.

Run: python3 .claude/scripts/tests/test_graphql_blocked.py
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pr_merged  # noqa: E402
import verify_issue_link  # noqa: E402

BLOCKED = ("HTTP 403: GitHub GraphQL is not available from Claude Code sessions; use the REST API "
           "(gh api repos/{owner}/{repo}/...). (https://api.github.com/graphql)")
REPO = {"full_name": "acme/app", "default_branch": "master"}
PULL = {"number": 7, "title": "t", "state": "closed", "merged_at": "2026-10-01T00:00:00Z",
        "merge_commit_sha": "abc", "html_url": "https://github.com/acme/app/pull/7",
        "head": {"ref": "feat", "sha": "h1"}, "base": {"ref": "master"}}


def fake_run(cmd, *, cwd=None, env=None):
    """gh GraphQL commands fail; gh api answers from canned REST JSON; git remote is a proxy URL."""
    if cmd[:2] == ["git", "remote"]:
        return 0, "http://local_proxy@127.0.0.1:41111/git/acme/app"
    if cmd[:2] in (["gh", "repo"], ["gh", "pr"], ["gh", "issue"]):
        return 1, ""
    path = cmd[-1]
    table = {"repos/acme/app": REPO, "repos/acme/app/pulls/7": PULL,
             "repos/acme/app/pulls/7/commits?per_page=100": [{"sha": "c1"}],
             "repos/acme/app/commits/h1/check-runs": {"check_runs": [{"conclusion": "success"}]},
             "repos/acme/app/issues/5": {"state": "open"}}
    return (0, json.dumps(table[path])) if path in table else (1, "")


class RestFallback(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(pr_merged, "_run", fake_run)
        p.start()
        self.addCleanup(p.stop)
        mock.patch.dict("os.environ", {}, clear=False).start()
        self.addCleanup(mock.patch.stopall)
        pr_merged.os.environ.pop("GH_REPO", None)

    def test_repo_view_keeps_its_shape(self):
        self.assertEqual(pr_merged.repo_view(), {"nameWithOwner": "acme/app", "defaultBranchRef": "master"})
        self.assertEqual(pr_merged.repo_view("acme/app"),
                         {"nameWithOwner": "acme/app", "defaultBranchRef": "master"})

    def test_graphql_path_still_wins_when_it_works(self):
        def run(cmd, **kw):
            if cmd[:3] == ["gh", "repo", "view"]:
                return 0, json.dumps({"nameWithOwner": "x/y", "defaultBranchRef": {"name": "main"}})
            return 1, ""
        with mock.patch.object(pr_merged, "_run", run):
            self.assertEqual(pr_merged.repo_view(), {"nameWithOwner": "x/y", "defaultBranchRef": "main"})

    def test_gh_pr_reads_through_rest(self):
        pr = pr_merged.gh_pr(7)
        self.assertEqual((pr["state"], pr["baseRefName"], pr["headRefName"]), ("MERGED", "master", "feat"))
        self.assertEqual(pr["mergeCommit"], {"oid": "abc"})
        self.assertEqual(pr["commits"], [{"oid": "c1"}])
        self.assertEqual(pr["statusCheckRollup"][0]["conclusion"], "SUCCESS")

    def test_issue_state_reads_through_rest(self):
        self.assertEqual(pr_merged._read_issue_state(5), "OPEN")

    def test_unreadable_everywhere_is_none(self):
        with mock.patch.object(pr_merged, "_run", lambda cmd, **kw: (1, "")):
            self.assertIsNone(pr_merged.repo_view())
            self.assertIsNone(pr_merged.gh_pr(7))


class VerifierNamesTheBlock(unittest.TestCase):
    def test_classifies_the_403(self):
        self.assertEqual(verify_issue_link._classify_gh_failure(BLOCKED), "graphql-unavailable")
        self.assertIn("graphql-unavailable", verify_issue_link.REMEDIATION)

    def test_blocked_graphql_is_unverifiable_never_a_body_match(self):
        def run_gh(args):
            if args == ["--version"]:
                return 0, "gh version 2.89.0", ""
            return 1, "", BLOCKED
        conv = Path(__file__).parent / "_graphql_conv.json"
        conv.write_text(json.dumps({"issueLink": {"closingKeyword": "Closes", "referenceKeyword": "Refs"}}))
        brief = Path(__file__).parent / "_graphql_brief.md"
        brief.write_text("---\nid: 5\n---\n")
        self.addCleanup(conv.unlink)
        self.addCleanup(brief.unlink)
        result = verify_issue_link.verify(str(brief), 7, "acme/app", conventions_path=str(conv), run_gh=run_gh)
        self.assertEqual(result["verdict"], "unverifiable")
        self.assertEqual(result["cause"], "graphql-unavailable")
        self.assertTrue(result["halt"])


if __name__ == "__main__":
    unittest.main()
