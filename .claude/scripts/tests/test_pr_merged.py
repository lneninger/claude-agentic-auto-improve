#!/usr/bin/env python3
"""
Tests for pr_merged.py — the closing phase of one sub-task.

Every test here exercises pure logic. GitHub and git are injected, so nothing
reaches the network or a working tree.

Run: py -3 .claude/scripts/tests/test_pr_merged.py
"""

import contextlib
import inspect
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pr_merged import (  # noqa: E402
    load_slot,
    load_review_gates,
    unknown_agents,
    DEFAULT_REVIEW_GATES,
    load_implementers,
    DEFAULT_IMPLEMENTERS,
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
import pr_merged  # noqa: E402  -- the module itself, for symbols this contract has not built yet


def _fn(name):
    """Look up a not-yet-built symbol on ``pr_merged`` without a collection-time crash.

    ``classify_handoff`` and ``parse_review_verdict`` do not exist until sub-task 2 lands. A
    bare ``from pr_merged import classify_handoff`` would raise ImportError for the whole file —
    every test in this suite, old and new, would fail to even load. That is a broken fixture,
    not a RED test. Routing the lookup through ``getattr`` instead lets each test turn the
    absence into its own explicit ``assertIsNotNone`` failure, naming exactly which symbol is
    missing, so a RED result here is always an assertion about behaviour, never a bare
    AttributeError.
    """
    return getattr(pr_merged, name, None)


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


# --------------------------------------------------------------------------
# Portability - the implementer list comes from the project profile
# --------------------------------------------------------------------------
PROFILE = """# Project Profile\n\n## Slots\n\n| Slot | Value |\n|---|---|\n| `project.name` | AcmeApp |\n| `backend.roots` | src/AcmeApp.Api/ |\n| `implementers` | `acme-backend-dev`, `acme-frontend-dev` |\n"""


class TestPortability(unittest.TestCase):
    def test_the_implementer_list_is_read_from_the_profile(self):
        self.assertEqual(load_implementers(PROFILE), ("acme-backend-dev", "acme-frontend-dev"))

    def test_no_profile_falls_back_to_the_agents_the_plugin_ships(self):
        self.assertEqual(load_implementers(None), DEFAULT_IMPLEMENTERS)

    def test_a_profile_without_the_slot_falls_back_too(self):
        self.assertEqual(load_implementers("# Project Profile\n\n| `project.name` | X |\n"),
                         DEFAULT_IMPLEMENTERS)

    def test_a_slot_reading_none_falls_back_rather_than_matching_nothing(self):
        prof = PROFILE.replace("`acme-backend-dev`, `acme-frontend-dev`", "none")
        self.assertEqual(load_implementers(prof), DEFAULT_IMPLEMENTERS,
                         "an empty implementer list would make every block a non-sub-task")

    def test_the_default_only_names_agents_the_plugin_actually_ships(self):
        for a in DEFAULT_IMPLEMENTERS:
            self.assertNotIn(a, ("ingestion-data-architect", "llm-training-engineer",
                                 "pinescript-developer"),
                             "project-specific agents belong in a profile, not the default")

    def test_a_contract_parses_against_a_projects_own_implementers(self):
        contract = """
## Implementation Handoff

### 1. Service (`acme-backend-dev`)

**Depends on:** none

**Files to touch:**
- src/AcmeApp.Api/Thing.cs
"""
        tasks = parse_handoff(contract, implementers=("acme-backend-dev",))
        self.assertEqual([t.id for t in tasks], ["t1-service"])

    def test_the_same_contract_yields_nothing_under_the_default_list(self):
        # REWRITTEN under Open Question 1 (answered A): the block DECLARES FILES, so under the
        # settled design it is mergeable whoever is assigned -- it can no longer be silently
        # excluded by an unrecognised agent name. What survives is that an unrecognised agent
        # is a reported CONTRACT DEFECT, never a sub-task. Asserting the defect's `reason`
        # (rather than only that `sub_tasks` stays empty) is the load-bearing part: today's
        # resolution is exact set membership (`pr_merged.py:232-233`, `a in named`), and this is
        # the protection the original case bought against a regression to substring matching --
        # under substring matching "acme-backend-dev" could resolve against a same-prefixed real
        # agent with `agent_role == "implementer"` and NO defect row, so an assertion on
        # `sub_tasks == []` alone would stay green through exactly that regression.
        contract = "## Implementation Handoff\n\n### 1. Service (`acme-backend-dev`)\n\n**Depends on:** none\n\n**Files to touch:**\n- a.cs\n"
        classify_handoff = _fn("classify_handoff")
        self.assertIsNotNone(classify_handoff,
                             "classify_handoff must exist to classify a block by what it declares")
        result = classify_handoff(contract, implementers=(), gates=())
        self.assertEqual(result.sub_tasks, [],
                         "an unrecognised agent name is not silently treated as a sub-task")
        self.assertEqual(len(result.defects), 1,
                         "a block that declares files but names no recognised agent is a "
                         "reported defect, not silence")
        self.assertEqual(result.defects[0].reason, "files-but-no-recognised-agent",
                         "the defect's reason, not mere tracking, is what a regression to "
                         "substring matching would falsify")


class TestProfilePlaceholders(unittest.TestCase):
    """The template ships with placeholder prose. It must never parse as agent names."""

    def test_placeholder_prose_is_not_read_as_agents(self):
        tmpl = ("| Slot | Value |\n"
                "| `implementers` | *(the agents that may own a contract sub-task, "
                "or `none` to accept the plugin's own)* |\n")
        self.assertEqual(load_implementers(tmpl), DEFAULT_IMPLEMENTERS,
                         "an unfilled template slot must fall back, not invent names")

    def test_only_backticked_values_count_as_names(self):
        filled = "| `implementers` | `acme-dev`, `acme-web` |\n"
        self.assertEqual(load_implementers(filled), ("acme-dev", "acme-web"))

    def test_a_slot_with_prose_around_real_names_takes_only_the_names(self):
        mixed = "| `implementers` | `acme-dev` and nothing else for now |\n"
        self.assertEqual(load_implementers(mixed), ("acme-dev",))


# --------------------------------------------------------------------------
# A general way to name what the flow needs
# --------------------------------------------------------------------------
SLOTS = """| Slot | Value |
|---|---|
| `project.name` | AcmeApp |
| `implementers` | `acme-dev` |
| `review-gates` | `acme-reviewer`, `acme-auditor` |
"""


class TestSlotReader(unittest.TestCase):
    def test_any_slot_can_be_read_by_name(self):
        self.assertEqual(load_slot(SLOTS, "project.name"), ("AcmeApp",))
        self.assertEqual(load_slot(SLOTS, "implementers"), ("acme-dev",))

    def test_an_absent_slot_reads_as_empty_not_as_an_error(self):
        self.assertEqual(load_slot(SLOTS, "nothing-declared-here"), ())

    def test_review_gates_come_from_their_own_slot(self):
        self.assertEqual(load_review_gates(SLOTS), ("acme-reviewer", "acme-auditor"))

    def test_no_profile_falls_back_to_the_gates_the_plugin_ships(self):
        self.assertEqual(load_review_gates(None), DEFAULT_REVIEW_GATES)


class TestUnknownAgents(unittest.TestCase):
    """A name that is neither an implementer nor a gate must be reported, never dropped."""

    CONTRACT = """
## Implementation Handoff

### 1. Tests (`senior-test-engineer`)

**Depends on:** none

**Files to touch:**
- tests/a.cs

### 2. Review (`fullstack-code-reviewer`)

**Depends on:** 1

### 3. Safety (`trading-safety`)

**Depends on:** 1
"""

    def test_a_declared_gate_is_not_reported_as_unknown(self):
        out = unknown_agents(self.CONTRACT,
                             implementers=("senior-test-engineer",),
                             gates=("fullstack-code-reviewer", "trading-safety-reviewer"))
        self.assertNotIn("fullstack-code-reviewer", out)

    def test_a_malformed_name_is_reported(self):
        out = unknown_agents(self.CONTRACT,
                             implementers=("senior-test-engineer",),
                             gates=("fullstack-code-reviewer", "trading-safety-reviewer"))
        self.assertIn("trading-safety", out,
                      "a block naming nothing recognised must surface, not vanish")

    def test_an_implementer_is_not_reported(self):
        out = unknown_agents(self.CONTRACT, implementers=("senior-test-engineer",), gates=())
        self.assertNotIn("senior-test-engineer", out)


class TestExactAgentMatching(unittest.TestCase):
    def test_a_suffixed_name_does_not_match_the_real_agent(self):
        # REWRITTEN under Open Question 1 (answered A), same reasoning as the sibling case in
        # TestPortability. The block DECLARES FILES, so it is mergeable under the settled design
        # -- the typo can no longer make it vanish. What the original case protected is now
        # expressed as the defect's `reason`, not as `sub_tasks == []`: `dotnet-backend-architects`
        # is one character away from the real agent, and today's resolution builds a `set` of
        # exact backticked names and asks `a in named` (`pr_merged.py:232-233`). Under a
        # regression to substring matching, "dotnet-backend-architects" would match
        # "dotnet-backend-architect" as a substring, resolve `agent_role == "implementer"`, and
        # produce NO defect row -- so asserting `sub_tasks == []` alone would stay green through
        # exactly that regression. Asserting `reason == "files-but-no-recognised-agent"` is what
        # actually catches it.
        contract = """
## Implementation Handoff

### 1. Backend (`dotnet-backend-architects`)

**Depends on:** none

**Files to touch:**
- src/a.cs
"""
        classify_handoff = _fn("classify_handoff")
        self.assertIsNotNone(classify_handoff,
                             "classify_handoff must exist to classify a block by what it declares")
        result = classify_handoff(contract, implementers=("dotnet-backend-architect",), gates=())
        self.assertEqual(result.sub_tasks, [],
                         "substring matching would silently accept a typo as the real agent")
        self.assertEqual(len(result.defects), 1,
                         "a typo'd agent name on a block that declares files is a reported "
                         "defect, not silence")
        self.assertEqual(result.defects[0].reason, "files-but-no-recognised-agent",
                         "the defect's reason, not mere tracking, is what a regression to "
                         "substring matching would falsify")

# --------------------------------------------------------------------------
# classify_handoff — a block is classified by what it declares, never by who
# is assigned to it. (a)-(d) plus the required positive control.
# --------------------------------------------------------------------------
CONTRACT_MERGEABLE_REVIEW_GATE = """
## Implementation Handoff

### 1. Review (`acme-reviewer`)

**Depends on:** none

**Files to touch:**
- .claude/reviews/c-slug/t1-review-acme-reviewer.md
"""

CONTRACT_NAMED_AGENT_NO_FILES = """
## Implementation Handoff

### 1. Review (`acme-reviewer`)

**Depends on:** none
"""

CONTRACT_SCOPE_NOTE_ONLY = """
## Implementation Handoff

### No frontend, no migration, no sentinel files.

This is a pure backend refactor.
"""

CONTRACT_ONE_OF_EACH_KIND = """
## Implementation Handoff

### 1. Backend (`acme-dev`)

**Depends on:** none

**Files to touch:**
- src/Foo.cs

### 2. Review (`acme-reviewer`)

**Depends on:** 1

### No frontend, no migration, no sentinel files.

Pure backend refactor.
"""


class TestClassifyHandoff(unittest.TestCase):
    """classify_handoff asks what a block DECLARES, never who is assigned to it."""

    def test_a_review_gate_that_declares_files_is_tracked_with_its_role_resolved(self):
        # (a) + REQUIRED POSITIVE CONTROL for review-gate resolution. Asserting agent_role,
        # rather than only that the block is tracked, is deliberate: a block that declares files
        # is tracked because of the file list alone, whichever list (or no list) resolves its
        # agent -- so a test that stopped at "is it in sub_tasks" would stay green even if
        # REVIEW_GATES were removed from resolution entirely. Only agent_role == "review-gate"
        # fails when that resolution is missing.
        classify_handoff = _fn("classify_handoff")
        self.assertIsNotNone(classify_handoff,
                             "classify_handoff must exist to classify a block by what it declares")
        result = classify_handoff(CONTRACT_MERGEABLE_REVIEW_GATE,
                                  implementers=("acme-dev",), gates=("acme-reviewer",))
        ids = [t.id for t in result.sub_tasks]
        self.assertEqual(ids, ["t1-review"],
                         "a block that declares files is mergeable whoever is assigned")
        self.assertEqual(result.sub_tasks[0].agent_role, "review-gate",
                         "the agent must resolve from the review-gates list, not merely be tracked")

    def test_a_block_naming_an_agent_with_no_files_is_a_defect_not_a_sub_task(self):
        # (b)
        classify_handoff = _fn("classify_handoff")
        self.assertIsNotNone(classify_handoff,
                             "classify_handoff must exist to classify a block by what it declares")
        result = classify_handoff(CONTRACT_NAMED_AGENT_NO_FILES,
                                  implementers=(), gates=("acme-reviewer",))
        self.assertEqual(result.sub_tasks, [],
                         "a block that declares no files can never merge, so it is not a sub-task")
        self.assertEqual(len(result.defects), 1,
                         "an agent named with no files is a reported defect, never a silent drop")
        self.assertEqual(result.defects[0].reason, "no-files-but-names-an-agent",
                         "the reason must name exactly what is wrong with the block")

    def test_a_block_naming_no_agent_and_no_files_is_a_scope_note(self):
        # (c)
        classify_handoff = _fn("classify_handoff")
        self.assertIsNotNone(classify_handoff,
                             "classify_handoff must exist to classify a block by what it declares")
        result = classify_handoff(CONTRACT_SCOPE_NOTE_ONLY, implementers=(), gates=())
        self.assertEqual(result.blocks[0].kind, "scope-note",
                         "a block declaring neither an agent nor files is a scope note")
        self.assertEqual(result.defects, [],
                         "a scope note is not deliverable, but it is not a defect either")

    def test_block_count_equals_the_number_of_headings_in_the_handoff_section(self):
        # (d) -- one fixture carrying one block of each kind: mergeable, malformed, scope-note.
        classify_handoff = _fn("classify_handoff")
        self.assertIsNotNone(classify_handoff,
                             "classify_handoff must exist to classify a block by what it declares")
        heading_count = len(re.findall(r"^### ", CONTRACT_ONE_OF_EACH_KIND, re.M))
        self.assertEqual(heading_count, 3,
                         "fixture sanity: one mergeable, one malformed, one scope-note block")
        result = classify_handoff(CONTRACT_ONE_OF_EACH_KIND,
                                  implementers=("acme-dev",), gates=("acme-reviewer",))
        self.assertEqual(len(result.blocks), heading_count,
                         "the accounting listing must never drop a block, whatever kind it is")


# --------------------------------------------------------------------------
# advance() must report a contract's own defects before asking anything else
# --------------------------------------------------------------------------
class TestAdvanceContractDefect(unittest.TestCase):
    def test_defects_take_priority_over_dispatching_ready_sub_tasks(self):
        # (e), case 1: defects alongside valid sub-tasks.
        sig = inspect.signature(advance)
        self.assertIn("defects", sig.parameters,
                      "advance() must accept a defects parameter so a contract defect is reported")
        out = advance(_tasks(), {}, defects=[{"id": "t9-x", "reason": "no-files-but-names-an-agent"}])
        self.assertEqual(out["action"], "contract-defect",
                         "a reported defect must halt dispatch, even while other sub-tasks are ready")

    def test_defects_are_reported_ahead_of_nothing_planned_on_an_all_malformed_contract(self):
        # (e), case 2: every block malformed -- tasks is empty, defects is not. Today's first
        # question ("nothing-planned") would wrongly describe a contract declaring nine
        # defective blocks as one declaring none.
        sig = inspect.signature(advance)
        self.assertIn("defects", sig.parameters,
                      "advance() must accept a defects parameter so a contract defect is reported")
        nine_defects = [{"id": f"t{n}-x", "reason": "no-files-but-names-an-agent"} for n in range(1, 10)]
        out = advance([], {}, defects=nine_defects)
        self.assertEqual(out["action"], "contract-defect",
                         "nine malformed blocks are not 'the contract declares no sub-tasks'")
        self.assertNotEqual(out["action"], "nothing-planned",
                            "an empty task list must not be read as an empty contract when defects exist")


# --------------------------------------------------------------------------
# Dispatch must refuse to name nothing as if it were an agent
# --------------------------------------------------------------------------
class TestDispatchNeedsAgent(unittest.TestCase):
    def test_a_dispatch_packet_flags_needs_agent_when_the_sub_task_has_none(self):
        # (f)
        task = SubTask(id="t1-a", ordinal=1, name="A", agent=None, depends_on=[], files=["a"])
        d = build_dispatch(task, "c", ".claude/concepts/c.md", "**Files to touch:**\n- a\n")
        self.assertIn("needs_agent", d,
                      "build_dispatch must report needs_agent so a caller never dispatches to "
                      "an empty name")
        self.assertTrue(d["needs_agent"],
                        "a None agent has no one to dispatch to")

    def test_a_dispatch_packet_does_not_flag_needs_agent_when_an_agent_is_present(self):
        # Positive control paired with the case above, so a hard-coded True cannot pass both.
        task = SubTask(id="t2-backend", ordinal=2, name="Backend",
                       agent="dotnet-backend-architect", depends_on=[1], files=["src/Foo/Bar.cs"])
        d = build_dispatch(task, "c", ".claude/concepts/c.md", "**Files to touch:**\n- src/Foo/Bar.cs\n")
        self.assertIn("needs_agent", d,
                      "build_dispatch must report needs_agent so a caller never dispatches to "
                      "an empty name")
        self.assertFalse(d["needs_agent"],
                         "a resolved agent must not be flagged as needing one")


# --------------------------------------------------------------------------
# The one machine-read line in a review artefact
# --------------------------------------------------------------------------
class TestParseReviewVerdict(unittest.TestCase):
    def _parser(self):
        parser = _fn("parse_review_verdict")
        self.assertIsNotNone(parser,
                             "parse_review_verdict must exist to read a review artefact's verdict line")
        return parser

    def test_reads_pass(self):
        parser = self._parser()
        text = "# Review\n\n**Verdict:** pass\n\n## What was checked\n- x: ok\n"
        self.assertEqual(parser(text), "pass")

    def test_reads_pass_with_findings(self):
        parser = self._parser()
        text = "# Review\n\n**Verdict:** pass-with-findings\n\n## What was checked\n- x: ok\n"
        self.assertEqual(parser(text), "pass-with-findings")

    def test_reads_blocked(self):
        parser = self._parser()
        text = "# Review\n\n**Verdict:** blocked\n\n## What was checked\n- x: ok\n"
        self.assertEqual(parser(text), "blocked")

    def test_returns_none_for_a_missing_verdict_line(self):
        parser = self._parser()
        text = "# Review\n\n## What was checked\n- x: ok\n"
        self.assertIsNone(parser(text),
                          "no header line means no verdict can be read, never a guess")

    def test_returns_none_for_prose_that_is_not_the_fixed_header(self):
        parser = self._parser()
        text = "# Review\n\nVerdict: everything looks good\n\n## What was checked\n- x: ok\n"
        self.assertIsNone(parser(text),
                          "free prose is not the machine-read line, whatever it says")

    def test_returns_none_for_a_value_outside_the_closed_set(self):
        parser = self._parser()
        text = "# Review\n\n**Verdict:** looks-fine\n\n## What was checked\n- x: ok\n"
        self.assertIsNone(parser(text),
                          "a value outside pass / pass-with-findings / blocked is unreadable to the loop")


# --------------------------------------------------------------------------
# A review gate's verdict is read, not merely stamped -- releases must honour it
# --------------------------------------------------------------------------
class TestReleasesHonourReviewVerdict(unittest.TestCase):
    def test_a_blocked_verdict_withholds_the_dependent_and_names_the_reading(self):
        # (h), reading "blocked"
        recs = {"t1-a": {"status": "completed", "verified": "github", "review_verdict": "blocked"}}
        rel, blocked = compute_released(_tasks(), recs)
        self.assertNotIn("t2-b", [t.id for t in rel],
                         "a blocked review verdict must not release what depends on it")
        self.assertIn("t1-a (review verdict: blocked)", blocked["t2-b"],
                      "the blocked reason must name which dependency and which reading stopped it")

    def test_an_unreadable_verdict_withholds_the_dependent_and_names_the_reading(self):
        # (h), reading "unreadable"
        recs = {"t1-a": {"status": "completed", "verified": "github", "review_verdict": "unreadable"}}
        rel, blocked = compute_released(_tasks(), recs)
        self.assertNotIn("t2-b", [t.id for t in rel],
                         "an unreadable verdict is not evidence of a clean review")
        self.assertIn("t1-a (review verdict: unreadable)", blocked["t2-b"],
                      "the blocked reason must name which dependency and which reading stopped it")

    def test_pass_with_findings_still_releases_the_dependent(self):
        # (i), part 1
        recs = {"t1-a": {"status": "completed", "verified": "github", "review_verdict": "pass-with-findings"}}
        rel, _ = compute_released(_tasks(), recs)
        self.assertIn("t2-b", [t.id for t in rel],
                      "pass-with-findings is a releasing reading, not a blocking one")

    def test_a_record_with_no_review_verdict_key_behaves_exactly_as_before_this_change(self):
        # (i), part 2 -- protects every completion record written before this change.
        recs = {"t1-a": {"status": "completed", "verified": "github"}}
        rel, _ = compute_released(_tasks(), recs)
        self.assertIn("t2-b", [t.id for t in rel],
                      "a record written before this change carries no review_verdict key and "
                      "must release exactly as it did before")

    def test_second_positive_control_release_flips_on_the_verdict_reading_alone(self):
        # SECOND POSITIVE CONTROL, required: two records identical but for the verdict reading.
        # If the reading were only stamped and never consulted by compute_released, both would
        # release identically and this case would stay green even with both consumers deleted.
        recs_pass = {"t1-a": {"status": "completed", "verified": "github", "review_verdict": "pass"}}
        rel_pass, _ = compute_released(_tasks(), recs_pass)
        self.assertIn("t2-b", [t.id for t in rel_pass],
                      "a passing verdict must release its dependent")

        recs_blocked = {"t1-a": {"status": "completed", "verified": "github", "review_verdict": "blocked"}}
        rel_blocked, _ = compute_released(_tasks(), recs_blocked)
        self.assertNotIn("t2-b", [t.id for t in rel_blocked],
                         "a blocked verdict on the SAME dependency must withhold the SAME dependent")


# --------------------------------------------------------------------------
# Reachability from the command line.
#
# Every case above this point proves classify_handoff, advance(defects=...),
# build_dispatch and compute_released are CORRECT when called directly. None
# of them proves main() -- the one thing a person or the orchestrator loop
# actually runs -- ever calls them that way. Measured by hand against this
# checkout: main() builds `tasks` from parse_handoff (pr_merged.py:831),
# which discards classify_handoff's blocks and defects entirely; it calls
# advance(tasks, records, state) at both call sites (pr_merged.py:879 and
# :901) with no `defects` argument; and its report dict never gains "blocks",
# "defects" or "review_verdicts" keys. Every case below drives pr_merged.main()
# itself -- the real command-line entry point -- against a contract written
# to a throwaway temp file (never a real project file), with every edge that
# would otherwise touch git, GitHub or the orchestrator's real result/state
# directories stubbed out. A RED result here can only be turned green by
# wiring main() itself; calling classify_handoff or advance directly, the way
# every earlier case in this file does, cannot make any of these pass.
# --------------------------------------------------------------------------
def _drive_main_report(contract_text, filename="acme-red-fixture.md"):
    """Call pr_merged.main() exactly the way the command line does.

    The contract is a literal written to a throwaway temp file so main()'s
    own ``find_contract`` can read it as a real path, without ever reading a
    file that belongs to this project. Every edge main() would otherwise use
    to reach git, GitHub or the orchestrator's real result/state directories
    is stubbed so the call is fully hermetic and deterministic. Returns the
    parsed ``--json`` report.
    """
    with tempfile.TemporaryDirectory() as d:
        contract_path = Path(d) / filename
        contract_path.write_text(contract_text, encoding="utf-8")
        out = io.StringIO()
        argv = ["pr_merged.py", "--contract", str(contract_path), "--status", "--json"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pr_merged, "load_records", return_value={}), \
             mock.patch.object(pr_merged, "load_state", return_value=None), \
             mock.patch.object(pr_merged, "default_branch", return_value="master"), \
             mock.patch.object(pr_merged, "write_state", return_value=None), \
             mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
             mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
             contextlib.redirect_stdout(out):
            pr_merged.main()
        return json.loads(out.getvalue())


CONTRACT_CLI_HAS_MALFORMED_BLOCK = """
## Implementation Handoff

### 1. Backend (`acme-dev`)

**Depends on:** none

**Files to touch:**
- src/Foo.cs

### 2. Review (`acme-reviewer`)

**Depends on:** 1
"""

CONTRACT_CLI_ALL_MALFORMED = """
## Implementation Handoff

### 1. Review (`acme-reviewer`)

**Depends on:** none

### 2. Another review (`acme-reviewer`)

**Depends on:** 1
"""

CONTRACT_CLI_ONE_OF_EACH_KIND = """
## Implementation Handoff

### 1. Backend (`acme-dev`)

**Depends on:** none

**Files to touch:**
- src/Foo.cs

### 2. Review (`acme-reviewer`)

**Depends on:** 1

### No frontend, no migration, no sentinel files.

Pure backend refactor.
"""


class TestMainSurfacesDefects(unittest.TestCase):
    """(a) The command-line path must surface defects, not just sub-tasks.

    Calling classify_handoff(CONTRACT_CLI_HAS_MALFORMED_BLOCK) directly
    already returns the defect -- TestClassifyHandoff proves that. This case
    is red for a different reason: main() never asks classify_handoff at
    all, so its report has no way to carry that defect out to a person or to
    the orchestrator loop.
    """

    def test_the_report_dict_names_the_malformed_block_in_its_defects_entry(self):
        report = _drive_main_report(CONTRACT_CLI_HAS_MALFORMED_BLOCK)
        self.assertIn(
            "defects", report,
            "main()'s report must carry a defects key -- today it builds \"sub_tasks\" from "
            "parse_handoff alone (pr_merged.py:831), which discards everything "
            "classify_handoff would have reported as a defect"
        )
        self.assertTrue(
            any(d.get("id") == "t2-review" for d in report["defects"]),
            "the malformed block (`acme-reviewer`, no Files to touch) must be named in the "
            "report's defects entry by its id, not merely tracked somewhere classify_handoff "
            "returns when called directly"
        )


class TestMainReachesContractDefect(unittest.TestCase):
    """(b) main() must reach the contract-defect action, not merely accept it.

    advance() already accepts a defects parameter and already returns
    "contract-defect" when given one -- TestAdvanceContractDefect proves
    that by calling advance(defects=...) directly. That case passes today
    and proves nothing about reachability. This case never calls advance()
    itself: it drives main() end to end, against a contract whose blocks are
    ALL malformed, so parse_handoff's projection is empty and today's
    unwired call site (pr_merged.py:901, advance(tasks, records, state) with
    no defects argument) answers "nothing-planned" about a contract that
    declares two defective blocks.
    """

    def test_an_all_malformed_contract_resolves_to_contract_defect_not_nothing_planned(self):
        report = _drive_main_report(CONTRACT_CLI_ALL_MALFORMED)
        action = report.get("next_move", {}).get("action")
        self.assertEqual(
            action, "contract-defect",
            "main() must pass classify_handoff's defects into advance() so a contract whose "
            "blocks are all malformed is reported as a contract defect -- today main() calls "
            "advance(tasks, records, state) with no defects argument at either call site"
        )
        self.assertNotEqual(
            action, "nothing-planned",
            "an empty task list built from two malformed blocks must never be read as a "
            "contract declaring no sub-tasks"
        )


class TestMainReportsBlockListing(unittest.TestCase):
    def test_the_report_blocks_entry_accounts_for_every_heading_with_its_kind(self):
        # (f)
        heading_count = len(re.findall(r"^### ", CONTRACT_CLI_ONE_OF_EACH_KIND, re.M))
        self.assertEqual(heading_count, 3,
                         "fixture sanity: one mergeable, one malformed, one scope-note block")
        report = _drive_main_report(CONTRACT_CLI_ONE_OF_EACH_KIND)
        self.assertIn(
            "blocks", report,
            "main()'s report must carry a blocks key -- the accounting listing built through "
            "classify_handoff, not the sub_tasks projection alone. TestClassifyHandoff already "
            "proves len(blocks) == heading_count for classify_handoff called directly; this "
            "asks the same question through the real reporting path"
        )
        self.assertEqual(
            len(report["blocks"]), heading_count,
            "len(blocks) must equal the number of ### headings in the handoff section through "
            "the report main() actually prints, not merely through classify_handoff in isolation"
        )
        self.assertEqual(
            sorted(b.get("kind") for b in report["blocks"]),
            ["malformed", "mergeable", "scope-note"],
            "every block in the report must carry its kind marker, so an operator reading the "
            "report -- not the classifier's return value -- can see what each block declared"
        )


class TestBuildRecordCarriesReviewVerdict(unittest.TestCase):
    """(c) + (d): build_record gains a review_verdict parameter and stamps it,
    with an explicit None omitting the key rather than stamping it null --
    the positive control that protects every completion record written
    before this change.
    """

    def test_build_record_accepts_and_stamps_a_review_verdict(self):
        # (c)
        sig = inspect.signature(build_record)
        self.assertIn(
            "review_verdict", sig.parameters,
            "build_record must accept a review_verdict parameter so a gate's reading can be "
            "stamped into the completion record it returns -- today it takes only verdict, "
            "commit, pr_url, merged_at and checks"
        )
        rec = build_record("merged", commit="abc123", pr_url="u", merged_at="t", checks=None,
                           review_verdict="pass-with-findings")
        self.assertEqual(
            rec.get("review_verdict"), "pass-with-findings",
            "the review verdict passed to build_record must be stamped into the record it "
            "returns, not merely accepted and dropped"
        )

    def test_a_record_built_without_a_verdict_omits_the_key(self):
        # (d) -- positive control for (c). A non-verdict-bearing sub-task passes None
        # explicitly, and the key must be OMITTED rather than stamped as null, so a
        # naive implementation that always writes "review_verdict": None cannot pass.
        sig = inspect.signature(build_record)
        self.assertIn(
            "review_verdict", sig.parameters,
            "build_record must accept a review_verdict parameter so a gate's reading can be "
            "stamped into the completion record it returns -- today it takes only verdict, "
            "commit, pr_url, merged_at and checks"
        )
        rec = build_record("merged", commit="abc123", pr_url="u", merged_at="t", checks=None,
                           review_verdict=None)
        self.assertNotIn(
            "review_verdict", rec,
            "a non-verdict-bearing sub-task passes None and the key must be OMITTED, not "
            "stamped as null, so every completion record written before this change keeps its "
            "exact meaning"
        )


CONTRACT_CLI_VERDICT_BEARING = """
## Implementation Handoff

### 1. Review (`acme-reviewer`)

**Depends on:** none

**Files to touch:**
- .claude/reviews/acme-red-fixture/t1-review-acme-reviewer.md
"""


class TestMainComposesFileAtCommitForAVerdictBearingSubtask(unittest.TestCase):
    """(e) The edge that reads a review artefact at the merge commit must be
    reachable from a merged pull request, not merely exist as a free
    function nobody calls. No real git process is ever started: the edge is
    injected as a fake, the same way TestResolvedFiles already fakes
    git_combined_diff, and the assertion is on the call shape -- that
    main() calls it at all, with the merge commit and the declared artefact
    path -- and on what its reading does to the completion record main()
    writes.
    """

    def test_file_at_commit_is_called_for_the_declared_artefact_at_the_merge_commit(self):
        artefact_text = "**Verdict:** pass-with-findings\n\n## What was checked\n- x: ok\n"
        fake_file_at_commit = mock.MagicMock(return_value=artefact_text)

        with tempfile.TemporaryDirectory() as d:
            contract_path = Path(d) / "acme-red-fixture.md"
            contract_path.write_text(CONTRACT_CLI_VERDICT_BEARING, encoding="utf-8")
            slug = contract_path.stem
            branch = f"task/{slug}/t1-review"
            pr = {
                "number": 42,
                "state": "MERGED",
                "mergedAt": "2026-01-01T00:00:00Z",
                "mergeCommit": {"oid": "deadbeef"},
                "headRefName": branch,
                "baseRefName": "master",
                "url": "https://example.invalid/pull/42",
                "commits": [{"oid": "deadbeef"}],
                "statusCheckRollup": None,
            }
            out = io.StringIO()
            argv = ["pr_merged.py", "--contract", str(contract_path),
                    "--pr", "42", "--dry-run", "--json"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value={}), \
                 mock.patch.object(pr_merged, "load_state", return_value=None), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", return_value=None), \
                 mock.patch.object(pr_merged, "write_record", return_value=None), \
                 mock.patch.object(pr_merged, "gh_pr", side_effect=lambda n: pr if n == 42 else None), \
                 mock.patch.object(pr_merged, "git_combined_diff", return_value=([], 1)), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 mock.patch.object(pr_merged, "file_at_commit", fake_file_at_commit, create=True), \
                 contextlib.redirect_stdout(out):
                pr_merged.main()
            report = json.loads(out.getvalue())

        self.assertTrue(
            fake_file_at_commit.called,
            "main() must read the declared review artefact at the merge commit through "
            "file_at_commit for a verdict-bearing sub-task -- today nothing in main() composes "
            "file_at_commit with parse_review_verdict at all, so a merged review gate's verdict "
            "is never read, whether or not file_at_commit itself exists"
        )
        fake_file_at_commit.assert_called_with(
            "deadbeef", ".claude/reviews/acme-red-fixture/t1-review-acme-reviewer.md"
        )
        closed = report.get("closed", [])
        self.assertTrue(closed, "fixture sanity: the merged pull request must close t1-review")
        self.assertEqual(
            closed[0]["record"].get("review_verdict"), "pass-with-findings",
            "the reading file_at_commit + parse_review_verdict produced must be stamped into "
            "the completion record main() writes for the merged pull request"
        )


# --------------------------------------------------------------------------
# The producer side of ReviewVerdictReading's fourth member, "unreadable".
#
# TestParseReviewVerdict already proves parse_review_verdict returns None for
# a missing line, a prose line and an out-of-set value -- that half of the
# contract is built and green. TestReleasesHonourReviewVerdict already proves
# compute_released withholds a release when a record's review_verdict reads
# "unreadable" -- but it hand-feeds that literal string; no code path in this
# repository produces it. The gap is main()'s own composition of the two:
# measured by hand against this checkout, main() (pr_merged.py:891-896) only
# assigns review_verdict when parse_review_verdict returned something, so
# every one of the three failures parse_review_verdict already reports as
# None leaves review_verdict at its initial None and the key is OMITTED from
# the record build_record returns -- never stamped "unreadable". A record
# with no review_verdict key is then judged by compute_released
# (pr_merged.py:525-527) exactly as a non-verdict-bearing record, and
# releases the dependent. Every case below drives pr_merged.main() itself,
# against a two-sub-task contract -- a verdict-bearing review gate and an
# ordinary dependent that names it in Depends on -- with every edge to git
# and GitHub stubbed, the same way TestMainComposesFileAtCommitFor... above
# does. A RED result here can only be turned green by main() itself naming
# its own "unreadable" reading; calling parse_review_verdict or
# compute_released directly, as the two suites above do, cannot make any of
# these pass.
# --------------------------------------------------------------------------
CONTRACT_CLI_VERDICT_BEARING_WITH_DEPENDENT = """
## Implementation Handoff

### 1. Review (`acme-reviewer`)

**Depends on:** none

**Files to touch:**
- .claude/reviews/acme-red-fixture/t1-review-acme-reviewer.md

### 2. Backend (`acme-dev`)

**Depends on:** 1

**Files to touch:**
- src/Foo.cs
"""


def _drive_main_pr_report_for_verdict_bearing_dependent(artefact_text, filename="acme-red-fixture.md"):
    """Drive pr_merged.main() end to end for a verdict-bearing gate plus its dependent.

    ``t1-review`` declares a file under ``.claude/reviews/`` and is verdict-bearing;
    ``t2-backend`` is an ordinary sub-task that names it in ``Depends on``. PR #42 closes
    only ``t1-review`` -- ``t2-backend`` never gets a pull request of its own in this test --
    so whether ``t2-backend`` appears in ``report["released"]`` is decided entirely by how the
    loop reads ``t1-review``'s verdict. Mirrors
    ``TestMainComposesFileAtCommitForAVerdictBearingSubtask``'s own mocking exactly; the only
    thing that varies between callers is what ``file_at_commit`` returns for the merge commit --
    a real artefact, prose, an out-of-set value, or nothing at all. Returns the parsed
    ``--json`` report.
    """
    with tempfile.TemporaryDirectory() as d:
        contract_path = Path(d) / filename
        contract_path.write_text(CONTRACT_CLI_VERDICT_BEARING_WITH_DEPENDENT, encoding="utf-8")
        slug = contract_path.stem
        branch = f"task/{slug}/t1-review"
        pr = {
            "number": 42,
            "state": "MERGED",
            "mergedAt": "2026-01-01T00:00:00Z",
            "mergeCommit": {"oid": "deadbeef"},
            "headRefName": branch,
            "baseRefName": "master",
            "url": "https://example.invalid/pull/42",
            "commits": [{"oid": "deadbeef"}],
            "statusCheckRollup": None,
        }
        fake_file_at_commit = mock.MagicMock(return_value=artefact_text)
        out = io.StringIO()
        argv = ["pr_merged.py", "--contract", str(contract_path),
                "--pr", "42", "--dry-run", "--json"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pr_merged, "load_records", return_value={}), \
             mock.patch.object(pr_merged, "load_state", return_value=None), \
             mock.patch.object(pr_merged, "default_branch", return_value="master"), \
             mock.patch.object(pr_merged, "write_state", return_value=None), \
             mock.patch.object(pr_merged, "write_record", return_value=None), \
             mock.patch.object(pr_merged, "gh_pr", side_effect=lambda n: pr if n == 42 else None), \
             mock.patch.object(pr_merged, "git_combined_diff", return_value=([], 1)), \
             mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
             mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
             mock.patch.object(pr_merged, "file_at_commit", fake_file_at_commit, create=True), \
             contextlib.redirect_stdout(out):
            pr_merged.main()
        return json.loads(out.getvalue())


class TestMainNamesAnUnreadableVerdictAndWithholdsRelease(unittest.TestCase):
    def test_an_out_of_set_verdict_is_named_unreadable_and_withholds_the_dependent(self):
        # (a) -- correct shape, wrong case: "Blocked" is not "blocked".
        artefact_text = "**Verdict:** Blocked\n\n## What was checked\n- x: ok\n"
        report = _drive_main_pr_report_for_verdict_bearing_dependent(artefact_text)
        closed = report.get("closed", [])
        self.assertTrue(closed, "fixture sanity: the merged pull request must close t1-review")
        self.assertEqual(
            closed[0]["record"].get("review_verdict"), "unreadable",
            "a **Verdict:** line whose value is outside the closed set -- here, wrong case -- "
            "is the loop's own ReviewVerdictReading of \"unreadable\" (contract Data Shapes, "
            "ReviewVerdictReading row), not a value main() leaves unset. Today main() only "
            "assigns review_verdict when parse_review_verdict returns something "
            "(pr_merged.py:891-896), so a parser failure leaves the key out of the record "
            "entirely rather than naming the loop's own reading"
        )
        self.assertNotIn(
            "t2-backend", report.get("released", []),
            "a record with no review_verdict key is judged exactly as before this field "
            "existed (compute_released, pr_merged.py:525-527) -- so an out-of-set verdict that "
            "main() fails to name releases its dependent exactly as a clean pass would, which "
            "is the release the contract's third Failure Mode says must not happen"
        )

    def test_a_prose_verdict_is_named_unreadable_and_withholds_the_dependent(self):
        # (b) -- not the fixed "**Verdict:** <value>" header at all.
        artefact_text = "Verdict: everything looks good\n\n## What was checked\n- x: ok\n"
        report = _drive_main_pr_report_for_verdict_bearing_dependent(artefact_text)
        closed = report.get("closed", [])
        self.assertTrue(closed, "fixture sanity: the merged pull request must close t1-review")
        self.assertEqual(
            closed[0]["record"].get("review_verdict"), "unreadable",
            "free prose in place of the fixed \"**Verdict:** <value>\" header is the loop's own "
            "ReviewVerdictReading of \"unreadable\" -- the contract's own Failure Modes name "
            "this exact shape (\"A gate writes its verdict as prose\"). Today main() leaves the "
            "key out of the record instead of naming it"
        )
        self.assertNotIn(
            "t2-backend", report.get("released", []),
            "an unreadable review verdict must not release what depends on it -- today it does, "
            "because the omitted key is judged exactly as a non-verdict-bearing record"
        )

    def test_an_absent_artefact_is_named_unreadable_and_withholds_the_dependent(self):
        # (c) -- the artefact reader returns nothing for the merge commit.
        report = _drive_main_pr_report_for_verdict_bearing_dependent(None)
        closed = report.get("closed", [])
        self.assertTrue(closed, "fixture sanity: the merged pull request must close t1-review")
        self.assertEqual(
            closed[0]["record"].get("review_verdict"), "unreadable",
            "a declared review artefact absent from the merge commit -- file_at_commit "
            "returning None, the shape a missing file or an unfetched commit produces -- is "
            "the loop's own ReviewVerdictReading of \"unreadable\" (ReviewVerdictReading row: "
            "\"the declared artefact is absent from that commit\"). Today main() only reads "
            "artefact_text when it is not None (pr_merged.py:895), so an absent artefact never "
            "even reaches parse_review_verdict and the key is omitted from the record"
        )
        self.assertNotIn(
            "t2-backend", report.get("released", []),
            "an absent review artefact must not release what depends on it -- today it does, "
            "because the omitted key is judged exactly as a non-verdict-bearing record"
        )

    def test_positive_control_a_correctly_spelled_pass_still_releases_the_dependent(self):
        # (e) -- must stay green throughout, so a fix that blocks everything cannot pass.
        artefact_text = "**Verdict:** pass\n\n## What was checked\n- x: ok\n"
        report = _drive_main_pr_report_for_verdict_bearing_dependent(artefact_text)
        closed = report.get("closed", [])
        self.assertTrue(closed, "fixture sanity: the merged pull request must close t1-review")
        self.assertEqual(
            closed[0]["record"].get("review_verdict"), "pass",
            "fixture sanity: a correctly spelled pass must still be read as pass"
        )
        self.assertIn(
            "t2-backend", report.get("released", []),
            "a correctly spelled passing verdict must still release its dependent -- this "
            "positive control must stay green throughout a fix, so a change that withholds "
            "every release regardless of the verdict's content cannot pass"
        )


class TestTheFetcherAsksForEveryFieldItsConsumersRead(unittest.TestCase):
    """A field the fetcher never requests arrives empty, and its reader dies quietly.

    ``map_pr_to_subtask`` falls back to the pull request title when the head
    branch is not a task branch. That is mapping rule two, documented in both
    loop skills. But ``gh_pr`` never asked GitHub for ``title``, so the fallback
    received the empty string on every call and could never fire. Pull request
    152 came back unmapped with all four of its sub-task identities sitting in
    its title, and no completion record was written for work that had merged.

    This is the same shape as the four other defects this contract removed: a
    consumer with no producer. Here the missing producer is the field list.
    """

    def _requested_fields(self):
        source = inspect.getsource(pr_merged.gh_pr)
        match = re.search(r'"--json",\s*\n?\s*"([^"]+)"', source)
        self.assertIsNotNone(
            match,
            "gh_pr must pass an explicit --json field list; without one this "
            "invariant cannot be checked at all")
        return set(match.group(1).split(","))

    def test_the_title_is_requested_because_the_mapper_reads_it(self):
        self.assertIn(
            "title", self._requested_fields(),
            "map_pr_to_subtask matches a sub-task identity against the pull "
            "request title, so gh_pr must request title. Without it the title "
            "is always empty, and a pull request on any branch that is not "
            "task/<contract>/<id> can never be mapped")

    def test_every_field_the_caller_reads_is_requested(self):
        """Positive control: pins the whole contract, not the one field."""
        requested = self._requested_fields()
        for field in ("state", "mergedAt", "mergeCommit", "headRefName",
                      "baseRefName", "url", "commits"):
            self.assertIn(
                field, requested,
                "main() reads pr.get(%r); a field the fetcher does not request "
                "arrives empty and its reader fails silently" % field)


if __name__ == "__main__":
    unittest.main(verbosity=2)
