#!/usr/bin/env python3
"""
Tests for pr_merged.py — the closing phase of one sub-task.

Every test here exercises pure logic. GitHub and git are injected, so nothing
reaches the network or a working tree.

Run: py -3 .claude/scripts/tests/test_pr_merged.py
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pr_merged import (  # noqa: E402
    new_state,
    mark_dispatched,
    reconcile_state,
    awaiting_merge,
    extract_task_block,
    build_dispatch,
    advance,
    derive_subtask_id,
    parse_handoff,
    branch_for,
    map_pr_to_subtask,
    classify_pr,
    build_record,
    compute_released,
    detect_resolved_files,
    SubTask,
)


# --------------------------------------------------------------------------
# Sub-task identity
# --------------------------------------------------------------------------
class TestSubTaskIdentity(unittest.TestCase):
    def test_id_is_ordinal_plus_slug(self):
        self.assertEqual(derive_subtask_id(2, "Backend (`dotnet-backend-architect`)"), "t2-backend")

    def test_id_drops_the_agent_and_parenthetical(self):
        self.assertEqual(
            derive_subtask_id(3, "Data pipeline (`ingestion-data-architect`) — if applicable"),
            "t3-data-pipeline",
        )

    def test_id_strips_trailing_prose_after_a_dash(self):
        self.assertEqual(
            derive_subtask_id(6, "LLM training (`llm-training-engineer`) — after chat-tool changes land"),
            "t6-llm-training",
        )

    def test_branch_name_is_built_from_the_identity(self):
        self.assertEqual(branch_for("2026-09-13-force-entry", "t2-backend"),
                         "task/2026-09-13-force-entry/t2-backend")


# --------------------------------------------------------------------------
# Parsing the handoff section into sub-tasks
# --------------------------------------------------------------------------
CONTRACT = """
## Data Shapes
irrelevant

## Implementation Handoff

### 1. Test author (`senior-test-engineer`)

**Depends on:** none

**Files to touch:**
- tests/Foo.Tests/BarTests.cs

### 2. Backend (`dotnet-backend-architect`)

**Depends on:** 1

**Files to touch:**
- src/Foo/Bar.cs

### 3. Migration review (`migration-safety-reviewer`)

**Depends on:** 2

### No frontend, no migration, no sentinel files.

This is a pure backend refactor.

## Review checklist

### CRITICAL 1 — something that is not a sub-task
"""


class TestParseHandoff(unittest.TestCase):
    def setUp(self):
        self.tasks = parse_handoff(CONTRACT)
        self.by_id = {t.id: t for t in self.tasks}

    def test_only_blocks_with_an_agent_and_files_are_sub_tasks(self):
        self.assertEqual([t.id for t in self.tasks], ["t1-test-author", "t2-backend"])

    def test_a_scope_note_is_not_a_sub_task(self):
        self.assertNotIn("t4-no-frontend-no-migration-no-sentinel-files", self.by_id)

    def test_a_review_gate_is_not_a_merge_gated_sub_task(self):
        # It has an agent but no Files to touch, so nothing waits on it to merge.
        self.assertNotIn("t3-migration-review", self.by_id)

    def test_headings_after_the_section_are_not_read(self):
        self.assertFalse(any("critical" in t.id for t in self.tasks))

    def test_declared_dependencies_are_read_as_ordinals(self):
        self.assertEqual(self.by_id["t1-test-author"].depends_on, [])
        self.assertEqual(self.by_id["t2-backend"].depends_on, [1])

    def test_missing_depends_on_line_is_a_defect_not_an_implied_none(self):
        broken = CONTRACT.replace("**Depends on:** 1\n\n", "", 1)
        tasks = parse_handoff(broken)
        backend = [t for t in tasks if t.id == "t2-backend"][0]
        self.assertIsNone(backend.depends_on, "absent Depends on must be None, never []")


# --------------------------------------------------------------------------
# Classifying what GitHub says about a pull request
# --------------------------------------------------------------------------
class TestClassifyPullRequest(unittest.TestCase):
    def test_merged_with_a_commit_is_merged(self):
        self.assertEqual(classify_pr({"state": "MERGED", "mergedAt": "2026-09-13T00:00:00Z",
                                      "mergeCommit": {"oid": "abc"}, "baseRefName": "master"},
                                     default_branch="master"), "merged")

    def test_open_is_not_merged(self):
        self.assertEqual(classify_pr({"state": "OPEN", "baseRefName": "master"},
                                     default_branch="master"), "not-merged")

    def test_closed_without_a_merge_is_a_failed_sub_task(self):
        self.assertEqual(classify_pr({"state": "CLOSED", "mergedAt": None, "baseRefName": "master"},
                                     default_branch="master"), "closed-unmerged")

    def test_merged_into_a_non_default_branch_is_flagged(self):
        self.assertEqual(classify_pr({"state": "MERGED", "mergedAt": "x", "mergeCommit": {"oid": "a"},
                                      "baseRefName": "develop"}, default_branch="master"),
                         "merged-elsewhere")

    def test_missing_pull_request_is_not_found(self):
        self.assertEqual(classify_pr(None, default_branch="master"), "not-found")


# --------------------------------------------------------------------------
# Mapping a pull request onto a sub-task
# --------------------------------------------------------------------------
class TestMapping(unittest.TestCase):
    def setUp(self):
        self.tasks = parse_handoff(CONTRACT)

    def test_branch_match_is_exact(self):
        t = map_pr_to_subtask("task/c-slug/t2-backend", "anything", self.tasks, "c-slug")
        self.assertEqual(t.id, "t2-backend")

    def test_title_naming_the_identity_also_matches(self):
        t = map_pr_to_subtask("some/other/branch", "[BACKEND] t1-test-author bits", self.tasks, "c-slug")
        self.assertEqual(t.id, "t1-test-author")

    def test_no_match_returns_none_rather_than_guessing(self):
        self.assertIsNone(map_pr_to_subtask("feature/unrelated", "nothing", self.tasks, "c-slug"))


# --------------------------------------------------------------------------
# The record written for a sub-task
# --------------------------------------------------------------------------
class TestRecord(unittest.TestCase):
    def test_completion_never_claims_tests_passed_without_evidence(self):
        rec = build_record("merged", commit="abc123", pr_url="u", merged_at="t", checks=None)
        self.assertEqual(rec["tests_passed"], "unknown")
        self.assertEqual(rec["tests_verified_by"], "none")

    def test_a_green_status_check_is_recorded_as_evidence(self):
        rec = build_record("merged", commit="abc", pr_url="u", merged_at="t", checks="SUCCESS")
        self.assertTrue(rec["tests_passed"])
        self.assertEqual(rec["tests_verified_by"], "ci")

    def test_completion_is_stamped_as_verified_by_github(self):
        rec = build_record("merged", commit="abc", pr_url="u", merged_at="t", checks=None)
        self.assertEqual(rec["verified"], "github")
        self.assertEqual(rec["status"], "completed")
        self.assertFalse(rec["contract_impact"]["requires_architect"])

    def test_a_closed_pull_request_produces_a_failure_that_escalates(self):
        rec = build_record("closed-unmerged", commit=None, pr_url="u", merged_at=None, checks=None)
        self.assertEqual(rec["status"], "failed")
        self.assertTrue(rec["contract_impact"]["requires_architect"])


# --------------------------------------------------------------------------
# Computing what a completion releases
# --------------------------------------------------------------------------
def _tasks():
    return [
        SubTask(id="t1-a", ordinal=1, name="A", agent="x", depends_on=[], files=["a"]),
        SubTask(id="t2-b", ordinal=2, name="B", agent="x", depends_on=[1], files=["b"]),
        SubTask(id="t3-c", ordinal=3, name="C", agent="x", depends_on=[1, 2], files=["c"]),
    ]


class TestReleases(unittest.TestCase):
    def test_a_sub_task_is_released_when_every_dependency_has_a_record(self):
        rel, blocked = compute_released(_tasks(), {"t1-a": {"status": "completed", "verified": "github"}})
        self.assertEqual([t.id for t in rel], ["t2-b"])

    def test_a_sub_task_stays_blocked_and_names_what_holds_it(self):
        _, blocked = compute_released(_tasks(), {"t1-a": {"status": "completed", "verified": "github"}})
        self.assertEqual(blocked["t3-c"], ["t2-b"])

    def test_a_failed_dependency_releases_nothing(self):
        recs = {"t1-a": {"status": "failed", "verified": "github"}}
        rel, blocked = compute_released(_tasks(), recs)
        self.assertEqual(rel, [])
        self.assertEqual(blocked["t2-b"], ["t1-a"])

    def test_a_record_without_github_verification_does_not_release(self):
        recs = {"t1-a": {"status": "completed", "verified": "asserted"}}
        rel, _ = compute_released(_tasks(), recs)
        self.assertEqual(rel, [], "only a verified record may release dependents")

    def test_an_undeclared_dependency_list_blocks_rather_than_releases(self):
        tasks = _tasks()
        tasks[1].depends_on = None  # contract defect
        rel, blocked = compute_released(tasks, {"t1-a": {"status": "completed", "verified": "github"}})
        self.assertNotIn("t2-b", [t.id for t in rel])
        self.assertIn("t2-b", blocked)

    def test_a_dependency_on_a_sub_task_that_does_not_exist_blocks(self):
        tasks = _tasks()
        tasks[1].depends_on = [99]
        rel, blocked = compute_released(tasks, {"t1-a": {"status": "completed", "verified": "github"}})
        self.assertNotIn("t2-b", [t.id for t in rel])
        self.assertIn("t2-b", blocked)


# --------------------------------------------------------------------------
# Hand-resolved files in the pull request's history
# --------------------------------------------------------------------------
class TestResolvedFiles(unittest.TestCase):
    def test_a_clean_merge_reports_nothing(self):
        def fake_git(sha):
            return {"m1": ([], 2)}[sha]
        self.assertEqual(detect_resolved_files(["m1"], fake_git), [])

    def test_files_differing_from_both_parents_are_reported(self):
        def fake_git(sha):
            return {"m1": (["a.md", "b.md"], 2)}[sha]
        self.assertEqual(detect_resolved_files(["m1"], fake_git), ["a.md", "b.md"])

    def test_single_parent_commits_are_skipped(self):
        def fake_git(sha):
            return {"c1": (["x"], 1)}[sha]
        self.assertEqual(detect_resolved_files(["c1"], fake_git), [],
                         "a non-merge commit has no combined diff to read")



# --------------------------------------------------------------------------
# Dispatch — extracted from the contract, never invented
# --------------------------------------------------------------------------
BLOCK_WITH_TASK = """
**Depends on:** none

**Files to touch:**
- src/Foo/Bar.cs

**Pre-written TASK block:**
```
TASK: Do the backend thing.
CONTEXT: concept contract at .claude/concepts/x.md
```
"""


class TestDispatch(unittest.TestCase):
    def test_the_task_block_is_extracted_from_the_contract(self):
        got = extract_task_block(BLOCK_WITH_TASK)
        self.assertIn("TASK: Do the backend thing.", got)

    def test_a_block_without_one_returns_none_rather_than_a_guess(self):
        self.assertIsNone(extract_task_block("**Files to touch:**\n- a.cs\n"))

    def test_a_dispatch_packet_names_branch_agent_scope_and_task(self):
        task = SubTask(id="t2-backend", ordinal=2, name="Backend",
                       agent="dotnet-backend-architect", depends_on=[1], files=["src/Foo/Bar.cs"])
        d = build_dispatch(task, "c-slug", ".claude/concepts/c-slug.md", BLOCK_WITH_TASK)
        self.assertEqual(d["branch"], "task/c-slug/t2-backend")
        self.assertEqual(d["agent"], "dotnet-backend-architect")
        self.assertEqual(d["files"], ["src/Foo/Bar.cs"])
        self.assertIn("TASK: Do the backend thing.", d["task_block"])
        self.assertEqual(d["contract"], ".claude/concepts/c-slug.md")

    def test_a_dispatch_without_a_task_block_is_flagged_not_fabricated(self):
        task = SubTask(id="t1-a", ordinal=1, name="A", agent="x", depends_on=[], files=["a"])
        d = build_dispatch(task, "c", ".claude/concepts/c.md", "**Files to touch:**\n- a\n")
        self.assertIsNone(d["task_block"])
        self.assertTrue(d["needs_authoring"])


# --------------------------------------------------------------------------
# advance — one move, then stop. It never iterates.
# --------------------------------------------------------------------------
class TestAdvance(unittest.TestCase):
    def test_an_empty_plan_is_never_reported_as_complete(self):
        out = advance([], {})
        self.assertEqual(out["action"], "nothing-planned")
        self.assertNotEqual(out["action"], "complete")

    def test_ready_sub_tasks_are_returned_for_dispatch(self):
        out = advance(_tasks(), {})
        self.assertEqual(out["action"], "dispatch")
        self.assertEqual(out["sub_tasks"], ["t1-a"])

    def test_completion_is_positive_every_sub_task_has_a_record(self):
        recs = {t.id: {"status": "completed", "verified": "github"} for t in _tasks()}
        self.assertEqual(advance(_tasks(), recs)["action"], "complete")

    def test_a_failure_escalates_rather_than_dispatching(self):
        recs = {"t1-a": {"status": "failed", "verified": "github",
                         "contract_impact": {"requires_architect": True}}}
        out = advance(_tasks(), recs)
        self.assertEqual(out["action"], "escalate")
        self.assertIn("t1-a", out["failed"])

    def test_nothing_ready_and_nothing_failed_is_blocked_not_complete(self):
        tasks = _tasks()
        tasks[0].depends_on = [99]
        out = advance(tasks, {})
        self.assertEqual(out["action"], "blocked")
        self.assertNotEqual(out["action"], "complete")

    def test_advance_returns_one_move_and_does_not_iterate(self):
        out = advance(_tasks(), {})
        self.assertEqual(len(out["sub_tasks"]), 1,
                         "only the currently ready set; the caller decides what happens next")


# --------------------------------------------------------------------------
# The state store — what makes suspend and resume real
# --------------------------------------------------------------------------
class TestState(unittest.TestCase):
    def test_a_new_state_lists_every_sub_task_as_pending(self):
        st = new_state("c-slug", _tasks())
        self.assertEqual(st["contract"], "c-slug")
        self.assertEqual({k: v["status"] for k, v in st["sub_tasks"].items()},
                         {"t1-a": "pending", "t2-b": "pending", "t3-c": "pending"})

    def test_dispatching_records_the_branch_and_the_awaiting_merge_state(self):
        st = mark_dispatched(new_state("c", _tasks()), "t1-a", "task/c/t1-a")
        self.assertEqual(st["sub_tasks"]["t1-a"]["status"], "awaiting-merge")
        self.assertEqual(st["sub_tasks"]["t1-a"]["branch"], "task/c/t1-a")

    def test_awaiting_merge_is_distinct_from_blocked(self):
        st = mark_dispatched(new_state("c", _tasks()), "t1-a", "task/c/t1-a")
        self.assertEqual(awaiting_merge(st), ["t1-a"],
                         "a dispatched sub-task is suspended, not stuck")

    def test_a_completion_record_moves_the_sub_task_out_of_awaiting_merge(self):
        st = mark_dispatched(new_state("c", _tasks()), "t1-a", "task/c/t1-a")
        st = reconcile_state(st, {"t1-a": {"status": "completed", "verified": "github"}})
        self.assertEqual(st["sub_tasks"]["t1-a"]["status"], "completed")
        self.assertEqual(awaiting_merge(st), [])

    def test_a_failure_record_is_reflected_in_state(self):
        st = reconcile_state(new_state("c", _tasks()),
                             {"t1-a": {"status": "failed", "verified": "github"}})
        self.assertEqual(st["sub_tasks"]["t1-a"]["status"], "failed")

    def test_reconcile_never_invents_a_status_for_an_unknown_sub_task(self):
        st = reconcile_state(new_state("c", _tasks()), {"t99-ghost": {"status": "completed"}})
        self.assertNotIn("t99-ghost", st["sub_tasks"])

    def test_resuming_from_state_knows_what_it_is_waiting_for(self):
        st = mark_dispatched(new_state("c", _tasks()), "t1-a", "task/c/t1-a")
        st["sub_tasks"]["t1-a"]["pull_request"] = 42
        self.assertEqual(st["sub_tasks"]["t1-a"]["pull_request"], 42)
        self.assertEqual(awaiting_merge(st), ["t1-a"])


class TestAdvanceWithState(unittest.TestCase):
    def test_a_dispatched_sub_task_is_not_offered_for_dispatch_again(self):
        st = mark_dispatched(new_state("c", _tasks()), "t1-a", "task/c/t1-a")
        out = advance(_tasks(), {}, state=st)
        self.assertEqual(out["action"], "awaiting-merge")
        self.assertEqual(out["awaiting"], ["t1-a"])

    def test_without_state_behaviour_is_unchanged(self):
        self.assertEqual(advance(_tasks(), {})["action"], "dispatch")

if __name__ == "__main__":
    unittest.main(verbosity=2)
