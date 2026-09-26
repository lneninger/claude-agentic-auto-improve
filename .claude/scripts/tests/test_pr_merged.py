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
import subprocess
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


# ---------------------------------------------------------------------------
# Structural guard: no test in this suite may reach a real GitHub mutation.
#
# Six tests correctly intercept pr_merged._run today, by four different
# hand-written fixture shapes. That protection belongs to nothing but each
# test author's own discipline -- the next test added inherits none of it,
# and its failure mode is not a red test, it is a closed issue or a merged
# pull request on a live tracker. This wraps the real subprocess.run for the
# whole module: any test that fails to intercept pr_merged._run before a
# mutating gh command reaches a real process gets a loud RuntimeError instead
# of a live mutation. It patches subprocess.run itself, never pr_merged._run,
# so it does not interfere with the tests above that patch _run directly --
# those never reach subprocess.run at all. Read-only and local git commands
# (gh issue view, git fetch, git switch, git rev-parse, ...) pass straight
# through, so it cannot mask a genuine failure in logic that never mutates
# anything.
# ---------------------------------------------------------------------------
_REAL_SUBPROCESS_RUN = subprocess.run
_FORBIDDEN_GH_MUTATIONS = (
    ("gh", "issue", "close"),
    ("gh", "issue", "develop"),
    ("gh", "pr", "merge"),
)


def _guarded_subprocess_run(cmd, *args, **kwargs):
    if isinstance(cmd, (list, tuple)):
        head = tuple(str(c) for c in cmd[:3])
        for forbidden in _FORBIDDEN_GH_MUTATIONS:
            if head[:len(forbidden)] == forbidden:
                raise RuntimeError(
                    "test suite attempted a real %r -- a test fixture failed to intercept "
                    "pr_merged._run before this command reached subprocess.run. Never patch "
                    "this guard away; patch pr_merged._run in the failing test instead."
                    % (cmd,))
    return _REAL_SUBPROCESS_RUN(cmd, *args, **kwargs)


def setUpModule():
    subprocess.run = _guarded_subprocess_run


def tearDownModule():
    subprocess.run = _REAL_SUBPROCESS_RUN


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
             mock.patch.object(pr_merged, "ensure_commit_local", return_value=True, create=True), \
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
            "returning None, the shape a missing file produces -- is "
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


# --------------------------------------------------------------------------
# Sub-task 1 (issue #163): "Loop state and the merge recorder"
#
# Two independently measured defects, both inside main():
#   (1) classify_pr(pr, base) is passed only the repository default branch,
#       so a task pull request merged into its own parent branch is reported
#       merged-elsewhere and no completion record is ever written. Under this
#       contract's topology EVERY task pull request merges into a parent
#       branch, so this alone would release nothing, ever. Measured
#       2026-09-19 against PR #173:
#         py -3 .claude/scripts/pr_merged.py --contract ... --pr 173 --json
#         -> {"skipped": [{"pr": 173, "verdict": "merged-elsewhere"}]}
#   (2) main() unconditionally passes default_branch() as create_branch's
#       second argument (pr_merged.py:859, :947), so a dispatched sub-task
#       branch is always cut from the default branch regardless of what its
#       own state entry declares -- the acceptance criterion this whole
#       feature exists to satisfy ("Each sub-task branch is cut from the
#       parent branch, not from master") is silently unmet.
#
# Every main()-level case below drives pr_merged.main() itself against a
# throwaway contract written to a temp file, with load_state, default_branch,
# gh_pr, git_combined_diff, write_state, write_record and create_branch all
# stubbed, so nothing reaches git, GitHub or this project's own orchestrator
# directories.
# --------------------------------------------------------------------------
CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK = """
## Implementation Handoff

### 1. Backend (`acme-dev`)

**Depends on:** none

**Files to touch:**
- src/Foo.cs
"""


class TestClassifyPrAcceptsADeclaredBaseSet(unittest.TestCase):
    """classify_pr(pr, default_branch="master", accepted_bases=None) --
    Extension Points, pr_merged.py. I-9: with accepted_bases=None the
    function must behave exactly as it does today; with a set, merged holds
    for any base inside it and merged-elsewhere stays reachable for every
    base outside it.
    """

    def test_classify_pr_accepts_an_accepted_bases_parameter(self):
        sig = inspect.signature(classify_pr)
        self.assertIn(
            "accepted_bases", sig.parameters,
            "classify_pr must accept a third accepted_bases parameter -- Extension Points: "
            "classify_pr(pr, default_branch='master', accepted_bases=None). Without it there "
            "is no way to recognise a merge into a sub-task's own declared parent branch"
        )

    def test_merged_into_a_declared_non_default_base_is_recognised_as_merged(self):
        pr = {"state": "MERGED", "mergedAt": "t", "mergeCommit": {"oid": "a"},
              "baseRefName": "feature/160-parent"}
        self.assertEqual(
            classify_pr(pr, default_branch="master",
                       accepted_bases={"master", "feature/160-parent"}),
            "merged",
            "a pull request merged into a base the caller declared must be recognised as "
            "merged even though it is not the repository default branch -- this is the "
            "measured PR #173 defect: every task pull request in this contract's design "
            "merges into a parent branch, and without a declared accepted_bases set "
            "classify_pr falls back to treating only the repository default branch as "
            "merged (I-9's unchanged default)"
        )

    def test_merged_into_a_branch_outside_the_declared_set_is_still_merged_elsewhere(self):
        # Positive control: without this the fix could degenerate into accepting
        # any base at all, rather than only the ones the caller declared.
        pr = {"state": "MERGED", "mergedAt": "t", "mergeCommit": {"oid": "a"},
              "baseRefName": "some-other-branch"}
        self.assertEqual(
            classify_pr(pr, default_branch="master",
                       accepted_bases={"master", "feature/160-parent"}),
            "merged-elsewhere",
            "a pull request merged into a branch that is in neither the default branch nor "
            "the declared set must still be reported merged-elsewhere -- accepting a "
            "declared parent branch must not accept every branch"
        )

    # I-9 ("called without a declared set it reports exactly what it reports
    # today") is not re-tested here as a standalone case: classify_pr(pr,
    # default_branch="master") with no accepted_bases argument is exactly the
    # call TestClassifyPullRequest.test_merged_into_a_non_default_branch_is_flagged
    # already makes, and it already passes -- an assertion that could only ever
    # be green cannot itself be a RED test. That existing, unmodified test is
    # what enforces I-9 once accepted_bases gains a default of None.


class TestNewStateAcceptsABaseParameter(unittest.TestCase):
    """new_state(contract_slug, tasks, base=None) -- Extension Points. Each
    fresh entry gains issue: None, base: <base or default>, brief: None.
    """

    def test_new_state_accepts_a_base_parameter(self):
        sig = inspect.signature(new_state)
        self.assertIn(
            "base", sig.parameters,
            "new_state must accept an optional base parameter -- Extension Points: "
            "new_state(contract_slug, tasks, base=None) -- so a fresh sub-task entry can be "
            "seeded with a declared parent branch instead of always the default branch"
        )

    def test_a_given_base_is_stamped_into_every_fresh_entry(self):
        st = new_state("c-slug", _tasks(), base="feature/160-parent")
        for tid, entry in st["sub_tasks"].items():
            self.assertEqual(
                entry.get("base"), "feature/160-parent",
                "every fresh sub-task entry must be seeded with the base new_state was "
                "given; sub-task %r was not" % tid
            )

    def test_every_fresh_entry_also_carries_issue_and_brief_as_none(self):
        st = new_state("c-slug", _tasks(), base="feature/160-parent")
        for tid, entry in st["sub_tasks"].items():
            self.assertIn(
                "issue", entry,
                "sub-task %r must carry an issue key from the moment its entry is created, "
                "even before any sub-issue exists for it" % tid
            )
            self.assertIsNone(
                entry.get("issue"),
                "a freshly created entry has no sub-issue yet, so issue must be None -- "
                "sub-task %r read %r" % (tid, entry.get("issue"))
            )
            self.assertIn("brief", entry, "sub-task %r must carry a brief key" % tid)
            self.assertIsNone(entry.get("brief"))


class TestRecordSubTaskIdentity(unittest.TestCase):
    """record_sub_task_identity(state, subtask_id, issue, base, brief) --
    Extension Points: a new pure writer, the sibling of mark_dispatched,
    called by /flow Step 2.7 through --record-subtask.
    """

    def _get(self):
        fn = _fn("record_sub_task_identity")
        if fn is None:
            self.fail(
                "pr_merged.record_sub_task_identity must exist -- Extension Points names it "
                "the sibling of mark_dispatched that stamps a sub-task's issue, base and "
                "brief into the state store"
            )
        return fn

    def test_it_writes_issue_base_and_brief_for_the_named_subtask(self):
        record_sub_task_identity = self._get()
        st = record_sub_task_identity(new_state("c", _tasks()), "t1-a", 163,
                                      "feature/160-parent", ".claude/work-items/x.md")
        entry = st["sub_tasks"]["t1-a"]
        self.assertEqual(entry.get("issue"), 163,
                         "the sub-issue number given must be stamped into the named entry")
        self.assertEqual(entry.get("base"), "feature/160-parent",
                         "the declared base given must be stamped into the named entry")
        self.assertEqual(entry.get("brief"), ".claude/work-items/x.md",
                         "the brief path given must be stamped into the named entry")

    def test_it_does_not_mutate_the_state_it_was_given(self):
        # A naive in-place writer would still pass the test above; this is the
        # test that would catch it -- mark_dispatched already sets this precedent
        # via copy.deepcopy.
        record_sub_task_identity = self._get()
        original = new_state("c", _tasks())
        before = json.dumps(original, sort_keys=True, default=str)
        record_sub_task_identity(original, "t1-a", 163, "feature/160-parent",
                                 ".claude/work-items/x.md")
        after = json.dumps(original, sort_keys=True, default=str)
        self.assertEqual(
            before, after,
            "record_sub_task_identity must return a new state rather than mutating the one "
            "it was given, exactly as mark_dispatched already does"
        )

    def test_it_leaves_every_other_subtask_untouched(self):
        record_sub_task_identity = self._get()
        st = record_sub_task_identity(new_state("c", _tasks()), "t1-a", 163,
                                      "feature/160-parent", ".claude/work-items/x.md")
        for tid in ("t2-b", "t3-c"):
            self.assertIsNone(
                st["sub_tasks"][tid].get("issue"),
                "recording t1-a's identity must not stamp an issue onto %r" % tid
            )


class TestStateRoundTripsIssueBaseAndBriefThroughDisk(unittest.TestCase):
    def test_write_then_load_preserves_issue_base_and_brief(self):
        record_sub_task_identity = _fn("record_sub_task_identity")
        self.assertIsNotNone(
            record_sub_task_identity,
            "pr_merged.record_sub_task_identity must exist before a round trip through disk "
            "can even be attempted"
        )
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(pr_merged, "STATE_DIR", Path(d)):
                st = new_state("c-slug", _tasks())
                st = record_sub_task_identity(st, "t1-a", 163, "feature/160-parent",
                                              ".claude/work-items/2026-09-19-163-t1-a.md")
                pr_merged.write_state("c-slug", st)
                reloaded = pr_merged.load_state("c-slug")

        self.assertIsNotNone(reloaded, "a state written to disk must be readable back")
        entry = reloaded["sub_tasks"]["t1-a"]
        self.assertEqual(entry.get("issue"), 163,
                         "the sub-issue number must survive a write-then-read round trip")
        self.assertEqual(entry.get("base"), "feature/160-parent",
                         "the declared base must survive a write-then-read round trip")
        self.assertEqual(entry.get("brief"), ".claude/work-items/2026-09-19-163-t1-a.md",
                         "the brief path must survive a write-then-read round trip")


class TestDispatchPacketCarriesIssueBaseAndBrief(unittest.TestCase):
    """build_dispatch(...) gains issue, base, brief and needs_issue --
    Extension Points, pr_merged.py.
    """

    def test_the_packet_carries_issue_base_and_brief_when_given(self):
        task = SubTask(id="t2-backend", ordinal=2, name="Backend",
                       agent="dotnet-backend-architect", depends_on=[1], files=["src/Foo/Bar.cs"])
        d = build_dispatch(task, "c-slug", ".claude/concepts/c-slug.md", BLOCK_WITH_TASK,
                           issue=163, base="feature/160-parent",
                           brief=".claude/work-items/2026-09-19-163-t2-backend.md")
        self.assertEqual(
            d.get("issue"), 163,
            "the dispatch packet must carry the sub-task's own sub-issue number"
        )
        self.assertEqual(
            d.get("base"), "feature/160-parent",
            "the dispatch packet must carry the sub-task's declared base, so whatever ships "
            "on its behalf knows which branch to target"
        )
        self.assertEqual(
            d.get("brief"), ".claude/work-items/2026-09-19-163-t2-backend.md",
            "the dispatch packet must carry the sub-task's brief path"
        )

    def test_needs_issue_is_true_when_flagged_by_the_caller(self):
        task = SubTask(id="t1-a", ordinal=1, name="A", agent="x", depends_on=[], files=["a"])
        d = build_dispatch(task, "c", ".claude/concepts/c.md", "**Files to touch:**\n- a\n",
                           issue=None, needs_issue=True)
        self.assertIn(
            "needs_issue", d,
            "build_dispatch must report needs_issue so a caller never dispatches a sub-task "
            "that still has no sub-issue created for it"
        )
        self.assertTrue(d["needs_issue"])

    def test_needs_issue_positive_control_is_false_when_an_issue_is_present(self):
        # Positive control mirroring needs_agent's own (test_pr_merged.py:769):
        # a hard-coded True must not pass both this case and the one above.
        task = SubTask(id="t1-a", ordinal=1, name="A", agent="x", depends_on=[], files=["a"])
        d = build_dispatch(task, "c", ".claude/concepts/c.md", "**Files to touch:**\n- a\n",
                           issue=163, needs_issue=False)
        self.assertIn("needs_issue", d)
        self.assertFalse(
            d["needs_issue"],
            "needs_issue must be false once a sub-issue has been recorded -- a hard-coded "
            "True would pass the case above but not this one"
        )


class TestCreateBranchIssueAwareCutover(unittest.TestCase):
    """create_branch(branch, base, issue=None) -- Extension Points. Without an
    issue the function must behave exactly as it does today: plain git only,
    no gh call. With an issue and a working gh, it registers the branch
    against its sub-issue through gh issue develop before falling back.
    """

    def test_an_issue_switches_the_cutover_from_plain_git_to_gh_issue_develop(self):
        """(a) with an issue and a working gh: RED today -- create_branch(branch,
        base) accepts no issue argument at all, so no gh call can ever happen.
        (b) without an issue: unchanged -- plain git only, no gh call. Verified
        together so the no-issue regression travels inside a test that is
        genuinely RED for reason (a); asserting (b) alone would already pass
        against today's create_branch(branch, base) and could not itself be RED.
        """
        with_issue_calls = []

        def fake_run_with_issue(cmd):
            with_issue_calls.append(cmd)
            if cmd[:2] == ["gh", "issue"] and "develop" in cmd:
                return 0, "https://github.com/acme/repo/tree/task/c/t1-a"
            if cmd[:2] == ["git", "fetch"]:
                return 0, ""
            if cmd[0] == "git" and len(cmd) > 1 and cmd[1] in ("switch", "checkout"):
                return 0, "switched"
            return 0, ""

        with mock.patch.object(pr_merged, "_run", side_effect=fake_run_with_issue):
            ok_with, _detail_with = pr_merged.create_branch(
                "task/c/t1-a", "feature/160-parent", issue=163)

        self.assertTrue(ok_with, "the gh-issue-develop path must report success when gh succeeds")
        gh_develop_calls = [c for c in with_issue_calls
                            if c[:2] == ["gh", "issue"] and "develop" in c]
        self.assertTrue(
            gh_develop_calls,
            "create_branch given an issue must call gh issue develop to register the branch "
            "against its sub-issue -- the whole reason the parameter exists. Today "
            "create_branch(branch, base) accepts no issue at all"
        )
        call = gh_develop_calls[0]
        self.assertIn("163", call, "the sub-issue number must be passed to gh issue develop")
        self.assertIn("feature/160-parent", call,
                      "the declared base must be passed as gh issue develop's --base")

        without_issue_calls = []

        def fake_run_without_issue(cmd):
            without_issue_calls.append(cmd)
            if cmd[:3] == ["git", "rev-parse", "--verify"]:
                return 1, ""  # branch does not exist yet
            if cmd[:2] == ["git", "fetch"]:
                return 0, ""
            if cmd[:3] == ["git", "switch", "-c"]:
                return 0, "created it"
            return 1, "unexpected command: %r" % (cmd,)

        with mock.patch.object(pr_merged, "_run", side_effect=fake_run_without_issue):
            ok_without, _detail_without = pr_merged.create_branch(
                "task/c/t1-a", "feature/160-parent")

        self.assertTrue(ok_without, "the plain git path must still succeed when no issue is given")
        self.assertFalse(
            any(c and c[0] == "gh" for c in without_issue_calls),
            "create_branch(branch, base) with no issue must run no gh command at all -- "
            "today's behaviour for every state entry written before this change"
        )


class TestMainDispatchCutsFromTheSubtasksDeclaredBase(unittest.TestCase):
    """Extension Points, main(): 'the first amendment's list had four and
    omitted [reading the sub-task's base], which would have shipped the
    sub-issue with today's branch topology bolted on.' I-1 -- the acceptance
    criterion this whole feature exists to satisfy: 'Each sub-task branch is
    cut from the parent branch, not from master.'
    """

    def _drive_dispatch(self, state_sub_task_entry, filename="acme-dispatch-fixture.md"):
        create_branch_mock = mock.MagicMock(return_value=(True, "created it"))
        with tempfile.TemporaryDirectory() as d:
            contract_path = Path(d) / filename
            contract_path.write_text(CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, encoding="utf-8")
            slug = contract_path.stem
            branch = f"task/{slug}/t1-backend"
            state = {
                "contract": slug,
                "started_at": "2026-09-19T00:00:00+00:00",
                "sub_tasks": {"t1-backend": dict(state_sub_task_entry)},
            }
            out = io.StringIO()
            argv = ["pr_merged.py", "--contract", str(contract_path),
                    "--dispatch", "t1-backend", "--json"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value={}), \
                 mock.patch.object(pr_merged, "load_state", return_value=state), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", return_value=None), \
                 mock.patch.object(pr_merged, "create_branch", create_branch_mock), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 contextlib.redirect_stdout(out):
                pr_merged.main()
            printed = out.getvalue()
        packet = json.loads(printed) if printed.strip().startswith("{") else None
        return branch, create_branch_mock, packet

    def test_dispatch_cuts_the_branch_from_the_subtasks_declared_base_not_the_default(self):
        branch, create_branch_mock, packet = self._drive_dispatch(
            {"status": "pending", "branch": None, "pull_request": None,
             "issue": 163, "base": "feature/160-parent", "brief": None})
        self.assertTrue(create_branch_mock.called,
                        "fixture sanity: dispatching a released sub-task must cut its branch")
        args, kwargs = create_branch_mock.call_args
        self.assertEqual(args[0], branch)
        self.assertEqual(
            args[1], "feature/160-parent",
            "main() must read the sub-task's own base out of its state entry and pass it as "
            "create_branch's second argument -- today it unconditionally passes "
            "default_branch(), which leaves the feature's headline acceptance criterion "
            "silently unmet"
        )
        self.assertIsNotNone(packet, "fixture sanity: --json dispatch must print a packet")
        self.assertEqual(
            packet.get("base"), "feature/160-parent",
            "the dispatch packet main() prints must also carry the sub-task's declared base"
        )
        self.assertEqual(
            packet.get("issue"), 163,
            "the dispatch packet main() prints must also carry the sub-task's sub-issue"
        )

    def test_dispatch_passes_the_subtasks_issue_to_create_branch(self):
        _, create_branch_mock, _ = self._drive_dispatch(
            {"status": "pending", "branch": None, "pull_request": None,
             "issue": 163, "base": "feature/160-parent", "brief": None})
        args, kwargs = create_branch_mock.call_args
        self.assertEqual(
            kwargs.get("issue"), 163,
            "main() must pass the sub-task's own sub-issue number into create_branch, so the "
            "branch it cuts is registered against that sub-issue -- today create_branch is "
            "called with no issue argument at all"
        )

    def test_a_declared_base_produces_a_different_branch_source_than_no_declared_base(self):
        # The discriminating control: today main() passes the SAME default_branch()
        # value to create_branch regardless of the state entry, so a sub-task that
        # declares its own base and one that declares none currently receive an
        # IDENTICAL base argument.
        _, mock_with, _ = self._drive_dispatch(
            {"status": "pending", "branch": None, "pull_request": None,
             "issue": 163, "base": "feature/160-parent", "brief": None})
        base_with = mock_with.call_args[0][1]

        _, mock_without, _ = self._drive_dispatch(
            {"status": "pending", "branch": None, "pull_request": None})
        base_without = mock_without.call_args[0][1]

        self.assertEqual(
            base_without, "master",
            "a state entry with no base key at all -- every entry written before this "
            "change -- must fall back to the repository default branch (I-8)"
        )
        self.assertNotEqual(
            base_with, base_without,
            "a sub-task that declares its own base must be cut from that base, not from "
            "whatever a sub-task with no declared base falls back to -- today main() passes "
            "the identical default_branch() value in both cases"
        )


class TestMainAcceptsAMergeIntoTheSubtasksDeclaredBase(unittest.TestCase):
    """The measured PR #173 defect. classify_pr(pr, base) is passed only the
    repository default branch, so a task pull request merged into its own
    parent branch is reported merged-elsewhere and no completion record is
    ever written. Under this contract's design EVERY task pull request
    merges into a parent branch, so this defect alone would release nothing,
    ever:

        py -3 .claude/scripts/pr_merged.py --contract ... --pr 173 --json
        -> {"skipped": [{"pr": 173, "verdict": "merged-elsewhere"}]}
    """

    def _drive(self, base_ref_name, declared_base, filename="acme-merge-fixture.md"):
        with tempfile.TemporaryDirectory() as d:
            contract_path = Path(d) / filename
            contract_path.write_text(CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, encoding="utf-8")
            slug = contract_path.stem
            branch = f"task/{slug}/t1-backend"
            pr = {
                "number": 173,
                "state": "MERGED",
                "mergedAt": "2026-09-19T00:00:00Z",
                "mergeCommit": {"oid": "cafef00d"},
                "headRefName": branch,
                "baseRefName": base_ref_name,
                "url": "https://example.invalid/pull/173",
                "commits": [{"oid": "cafef00d"}],
                "statusCheckRollup": None,
            }
            state = {
                "contract": slug,
                "started_at": "2026-09-19T00:00:00+00:00",
                # 4343 is not a real issue (this repository's numbers stood near 206 on
                # 2026-09-25) -- amended 2026-09-25, fourth pass, from 163, which is t1's
                # REAL sub-issue (state.yaml:8). No assertion in this test reads the issue
                # number, so the change alters no outcome; it only stops this fixture from
                # naming a live tracker issue.
                "sub_tasks": {"t1-backend": {"status": "pending", "branch": branch,
                                             "pull_request": None, "issue": 4343,
                                             "base": declared_base, "brief": None}},
            }
            write_record_mock = mock.MagicMock(return_value=None)
            close_sub_issue_mock = mock.MagicMock(return_value=None)
            out = io.StringIO()
            argv = ["pr_merged.py", "--contract", str(contract_path), "--pr", "173", "--json"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value={}), \
                 mock.patch.object(pr_merged, "load_state", return_value=state), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", return_value=None), \
                 mock.patch.object(pr_merged, "write_record", write_record_mock), \
                 mock.patch.object(pr_merged, "gh_pr", side_effect=lambda n: pr if n == 173 else None), \
                 mock.patch.object(pr_merged, "git_combined_diff", return_value=([], 1)), \
                 mock.patch.object(pr_merged, "close_sub_issue", close_sub_issue_mock, create=True), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 contextlib.redirect_stdout(out):
                pr_merged.main()
            report = json.loads(out.getvalue())
        return report, write_record_mock, close_sub_issue_mock

    def test_a_merge_into_the_declared_base_is_accepted_while_others_are_still_rejected(self):
        """(a) accepted -- RED today: classify_pr(pr, base) never sees the
        declared base. (b) rejected -- the positive control, so accepting the
        parent branch cannot degenerate into accepting any base. (c) default
        branch -- unchanged; bundled here rather than as its own test because
        it already passes today and cannot itself be RED, so it is verified
        inside a test that is genuinely RED for reason (a).
        """
        accepted_report, accepted_writes, _accepted_close = self._drive(
            "feature/160-parent", "feature/160-parent")
        rejected_report, rejected_writes, rejected_close = self._drive(
            "some-other-branch", "feature/160-parent")
        default_report, _default_writes, _default_close = self._drive(
            "master", "feature/160-parent")

        self.assertTrue(
            accepted_report.get("closed"),
            "a pull request merged into the sub-task's own declared base must close it -- "
            "today classify_pr(pr, base) compares only against the repository default "
            "branch, so this list stays empty and the sub-issue never releases (measured "
            "PR #173 defect)"
        )
        self.assertTrue(
            accepted_writes.called,
            "a completion record must actually be written for a pull request merged into "
            "the declared base, not merely reported in memory"
        )

        self.assertEqual(
            rejected_report.get("closed", []), [],
            "a pull request merged into a branch that is neither the default branch nor the "
            "sub-task's declared base must never produce a completion record"
        )
        self.assertEqual(
            [s.get("verdict") for s in rejected_report.get("skipped", [])],
            ["merged-elsewhere"],
            "a pull request merged into an undeclared branch must still be reported "
            "merged-elsewhere -- accepting the parent branch must not accept anything"
        )
        self.assertFalse(rejected_writes.called)
        self.assertFalse(
            rejected_close.called,
            "B3-a: a pull request merged into a branch that is neither the default branch "
            "nor the sub-task's declared base must never close its sub-issue either -- "
            "close_sub_issue's only guard is the verdict == 'merged' term at the one call "
            "site (pr_merged.py:1474)"
        )

        self.assertTrue(
            default_report.get("closed"),
            "a pull request merged into the repository default branch must still close its "
            "sub-task exactly as it does today, regardless of what base the sub-task itself "
            "declares"
        )

    def test_a_closed_unmerged_pull_request_never_closes_its_subissue(self):
        """B3-b: closed-unmerged must not close the sub-issue either.

        classify_pr returns closed-unmerged for a PR that is CLOSED with no
        mergedAt/mergeCommit (pr_merged.py:433). That state is NOT in
        main()'s early-continue skip tuple ("not-found", "not-merged",
        "merged-elsewhere", pr_merged.py:1411), so this input reaches the
        close gate at :1474 -- unlike B3-a's rejected-merge case, which
        classify_pr reports merged-elsewhere and main() skips before the
        gate is ever reached (probe P10b's whole reason for existing). Only
        the verdict == "merged" term at the gate stops this one from
        closing. This case cannot go through _drive: _drive hard-codes a
        merged pull request (state MERGED, a mergedAt and a mergeCommit),
        and the edit rule for that helper allows only its two named changes.
        The state entry's issue is 4242 (not a real issue), matching the
        read-only-flags tests' own convention. Run without --dry-run,
        --status or --resume: any one of those would keep the close gate
        shut regardless of the probe and make this assertion inert.
        """
        close_sub_issue_mock = mock.MagicMock(return_value=None)
        with tempfile.TemporaryDirectory() as d:
            contract_path = Path(d) / "acme-closed-unmerged-fixture.md"
            contract_path.write_text(CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, encoding="utf-8")
            slug = contract_path.stem
            branch = f"task/{slug}/t1-backend"
            pr = {
                "number": 173, "state": "CLOSED", "mergedAt": None, "mergeCommit": None,
                "headRefName": branch, "baseRefName": "feature/160-parent",
                "url": "https://example.invalid/pull/173",
                "commits": [{"oid": "cafef00d"}], "statusCheckRollup": None,
            }
            state = {
                "contract": slug, "started_at": "2026-09-19T00:00:00+00:00",
                "sub_tasks": {"t1-backend": {"status": "pending", "branch": branch,
                                             "pull_request": None, "issue": 4242,
                                             "base": "feature/160-parent", "brief": None}},
            }
            out = io.StringIO()
            argv = ["pr_merged.py", "--contract", str(contract_path), "--pr", "173", "--json"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value={}), \
                 mock.patch.object(pr_merged, "load_state", return_value=state), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", return_value=None), \
                 mock.patch.object(pr_merged, "write_record", return_value=None), \
                 mock.patch.object(pr_merged, "gh_pr", side_effect=lambda n: pr if n == 173 else None), \
                 mock.patch.object(pr_merged, "git_combined_diff", return_value=([], 1)), \
                 mock.patch.object(pr_merged, "close_sub_issue", close_sub_issue_mock, create=True), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 contextlib.redirect_stdout(out):
                pr_merged.main()
            report = json.loads(out.getvalue())

        self.assertEqual(
            [c.get("verdict") for c in report.get("skipped", [])], [],
            "fixture sanity: closed-unmerged must NOT be skipped at the early continue -- it "
            "must reach the close gate for this assertion to mean anything"
        )
        self.assertFalse(
            close_sub_issue_mock.called,
            "B3-b: a closed-but-unmerged pull request must never close its sub-issue -- only "
            "the verdict == 'merged' term at the close gate (pr_merged.py:1474) stops it"
        )


class TestMainAttemptsSubIssueClosureAfterAConfirmedMerge(unittest.TestCase):
    """main() point 5, Extension Points: after a confirmed merge, attempt the
    sub-issue closure and stamp the outcome into the completion record as
    sub_issue_closed -- I-8's omit-rather-than-stamp-null treatment, the same
    one review_verdict already has.
    """

    def test_a_confirmed_merge_into_the_declared_base_closes_its_subissue_and_records_it(self):
        close_sub_issue_mock = mock.MagicMock(return_value="closed")
        with tempfile.TemporaryDirectory() as d:
            contract_path = Path(d) / "acme-close-fixture.md"
            contract_path.write_text(CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, encoding="utf-8")
            slug = contract_path.stem
            branch = f"task/{slug}/t1-backend"
            pr = {
                "number": 173, "state": "MERGED", "mergedAt": "2026-09-19T00:00:00Z",
                "mergeCommit": {"oid": "cafef00d"}, "headRefName": branch,
                "baseRefName": "feature/160-parent",
                "url": "https://example.invalid/pull/173",
                "commits": [{"oid": "cafef00d"}], "statusCheckRollup": None,
            }
            state = {
                "contract": slug, "started_at": "2026-09-19T00:00:00+00:00",
                "sub_tasks": {"t1-backend": {"status": "pending", "branch": branch,
                                             "pull_request": None, "issue": 163,
                                             "base": "feature/160-parent", "brief": None}},
            }
            out = io.StringIO()
            argv = ["pr_merged.py", "--contract", str(contract_path), "--pr", "173", "--json"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value={}), \
                 mock.patch.object(pr_merged, "load_state", return_value=state), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", return_value=None), \
                 mock.patch.object(pr_merged, "write_record", return_value=None), \
                 mock.patch.object(pr_merged, "gh_pr", side_effect=lambda n: pr if n == 173 else None), \
                 mock.patch.object(pr_merged, "git_combined_diff", return_value=([], 1)), \
                 mock.patch.object(pr_merged, "close_sub_issue", close_sub_issue_mock, create=True), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 contextlib.redirect_stdout(out):
                pr_merged.main()
            report = json.loads(out.getvalue())

        self.assertTrue(
            close_sub_issue_mock.called,
            "main() must attempt the sub-issue closure once a merge into the declared base "
            "is confirmed -- Extension Points main() point 5. Today main() never calls "
            "close_sub_issue at all, whether or not the function exists"
        )
        close_sub_issue_mock.assert_called_with(163, pr["url"])
        closed = report.get("closed", [])
        self.assertTrue(closed, "fixture sanity: the merge must close t1-backend")
        self.assertEqual(
            closed[0]["record"].get("sub_issue_closed"), "closed",
            "the completion record must carry the closure outcome under sub_issue_closed"
        )


class TestCloseSubIssueReadsBeforeClosing(unittest.TestCase):
    """close_sub_issue(issue, pr_url) -- Extension Points; enforces I-10: read
    gh issue view state FIRST, return already-closed without mutating when
    already closed; otherwise close and re-read to report closed/close-failed.
    """

    def _get(self):
        fn = _fn("close_sub_issue")
        if fn is None:
            self.fail(
                "pr_merged.close_sub_issue must exist -- Extension Points names it a new "
                "edge beside gh_pr, enforcing I-10's read-before-close ordering"
            )
        return fn

    def test_an_already_closed_issue_is_reported_closed_without_mutating(self):
        close_sub_issue = self._get()
        calls = []

        def fake_run(cmd):
            calls.append(cmd)
            if cmd[:2] == ["gh", "issue"] and "view" in cmd:
                return 0, json.dumps({"state": "CLOSED"})
            return 1, "close_sub_issue must not issue this command: %r" % (cmd,)

        with mock.patch.object(pr_merged, "_run", side_effect=fake_run):
            result = close_sub_issue(163, "https://example.invalid/pull/173")

        self.assertEqual(
            result, "already-closed",
            "an issue that is already closed must be reported already-closed, idempotently "
            "on a re-run -- I-10's read-before-close ordering"
        )
        self.assertFalse(
            any(c[:2] == ["gh", "issue"] and "close" in c for c in calls),
            "an already-closed issue must never receive a gh issue close call -- that is "
            "the mutation I-10 forbids on a re-run"
        )

    def test_an_open_issue_is_closed_and_reported_closed(self):
        close_sub_issue = self._get()
        calls = []

        def fake_run(cmd):
            calls.append(cmd)
            if cmd[:2] == ["gh", "issue"] and "view" in cmd:
                view_calls = [c for c in calls if c[:2] == ["gh", "issue"] and "view" in c]
                state = "OPEN" if len(view_calls) == 1 else "CLOSED"
                return 0, json.dumps({"state": state})
            if cmd[:2] == ["gh", "issue"] and "close" in cmd:
                return 0, ""
            return 1, "unexpected command: %r" % (cmd,)

        with mock.patch.object(pr_merged, "_run", side_effect=fake_run):
            result = close_sub_issue(163, "https://example.invalid/pull/173")

        close_calls = [c for c in calls if c[:2] == ["gh", "issue"] and "close" in c]
        self.assertTrue(
            close_calls,
            "an open sub-issue must be closed through gh issue close once its pull request "
            "has merged"
        )
        self.assertIn("163", close_calls[0],
                      "the sub-issue number must be passed to gh issue close")
        self.assertEqual(result, "closed")


# --------------------------------------------------------------------------
# The structural guard itself: proves it is live, not merely present.
# --------------------------------------------------------------------------
class TestSubprocessGuardBlocksLiveMutations(unittest.TestCase):
    """A test that forgets to intercept pr_merged._run must fail loudly, not
    reach a real gh mutation. Drives pr_merged._run directly -- no mock on
    _run itself -- so the only thing standing between this call and a real
    subprocess is the module-level guard installed by setUpModule above.
    """

    def test_an_unintercepted_close_call_raises_instead_of_running(self):
        with self.assertRaises(RuntimeError):
            pr_merged._run(["gh", "issue", "close", "163"])

    def test_an_unintercepted_develop_call_raises_instead_of_running(self):
        with self.assertRaises(RuntimeError):
            pr_merged._run(["gh", "issue", "develop", "163", "--name", "x"])

    def test_an_unintercepted_pr_merge_call_raises_instead_of_running(self):
        with self.assertRaises(RuntimeError):
            pr_merged._run(["gh", "pr", "merge", "42"])

    def test_a_read_only_gh_call_is_not_blocked(self):
        # Positive control: the guard must not mask a genuine failure by
        # blocking commands it was never meant to catch. W2: this used to run
        # a REAL `gh issue view 163` -- issue 163 is a real, live issue in
        # this repository's own tracker, and the assertion only ever proved
        # the guard did not raise, so the network result was irrelevant.
        # Swapped for a recorder, mirroring
        # test_verify_parent_link.py:997-1009's shape: the real subprocess
        # runner is replaced for the duration of this one call, so the
        # assertion is that the read reached the recorder, never a live
        # process.
        global _REAL_SUBPROCESS_RUN
        saved = _REAL_SUBPROCESS_RUN
        seen = []

        def fake_real(cmd, *args, **kwargs):
            seen.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, json.dumps({"state": "OPEN"}), "")

        _REAL_SUBPROCESS_RUN = fake_real
        try:
            code, out = pr_merged._run(["gh", "issue", "view", "163", "--json", "state"])
        except RuntimeError as exc:
            self.fail("the guard must not intercept a read-only gh command: %r" % exc)
        finally:
            _REAL_SUBPROCESS_RUN = saved

        self.assertEqual(
            seen, [["gh", "issue", "view", "163", "--json", "state"]],
            "the read-only call must reach the recorder -- after this change the suite must "
            "launch NO gh process at all"
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, json.dumps({"state": "OPEN"}))


# --------------------------------------------------------------------------
# CRITICAL 1: --record-subtask against an unknown id must refuse, not
# silently no-op while reporting success.
# --------------------------------------------------------------------------
class TestRecordSubtaskRefusesUnknownId(unittest.TestCase):
    """record_sub_task_identity only updates an entry that already exists in
    state["sub_tasks"], and main()'s --record-subtask handler wrote state,
    printed a success payload and returned 0 regardless. A typo'd or stale
    id therefore changed nothing and still reported success -- the state
    entry's issue field is I-5's ONLY witness that a sub-issue was created
    exactly once, so a confident success with no witness leaves the next run
    believing no issue exists and opening a second one for the same
    sub-task.
    """

    def _drive(self, subtask_id, extra_args=(), filename="acme-record-fixture.md"):
        write_state_mock = mock.MagicMock(return_value=None)
        with tempfile.TemporaryDirectory() as d:
            contract_path = Path(d) / filename
            contract_path.write_text(CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, encoding="utf-8")
            out = io.StringIO()
            argv = ["pr_merged.py", "--contract", str(contract_path),
                    "--record-subtask", subtask_id, "--issue", "163",
                    "--base", "feature/160-parent", "--brief", ".claude/work-items/x.md",
                    "--json", *extra_args]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value={}), \
                 mock.patch.object(pr_merged, "load_state", return_value=None), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", write_state_mock), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 contextlib.redirect_stdout(out):
                exit_code = pr_merged.main()
            printed = out.getvalue()
        payload = json.loads(printed) if printed.strip().startswith("{") else None
        return exit_code, payload, write_state_mock

    def test_an_unknown_id_refuses_with_a_non_zero_exit(self):
        exit_code, payload, write_state_mock = self._drive("t9-does-not-exist")
        self.assertNotEqual(
            exit_code, 0,
            "recording an id absent from the plan must not report success -- it is I-5's "
            "only witness, and a confident success with no witness lets a typo'd id open a "
            "second sub-issue on the next run"
        )
        self.assertIsNotNone(payload, "fixture sanity: the CLI must print a JSON payload")
        self.assertEqual(payload.get("error"), "unknown-sub-task")
        self.assertIn(
            "t1-backend", payload.get("known", []),
            "the refusal must name the known sub-task ids so the caller can see the typo"
        )
        self.assertFalse(
            write_state_mock.called,
            "an unknown id must never be written to the state store -- that write is the "
            "silent no-op this defect produced"
        )

    def test_a_known_id_still_succeeds(self):
        # Positive control: the refusal must not degenerate into rejecting every id.
        exit_code, payload, write_state_mock = self._drive("t1-backend")
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload.get("recorded"), "t1-backend")
        self.assertTrue(write_state_mock.called)


# --------------------------------------------------------------------------
# Warning 7: --record-subtask must honour --dry-run and --status exactly as
# the report path already does, rather than writing unconditionally.
# --------------------------------------------------------------------------
class TestRecordSubtaskHonoursDryRunAndStatus(unittest.TestCase):
    def _drive(self, extra_args, filename="acme-record-dryrun-fixture.md"):
        write_state_mock = mock.MagicMock(return_value=None)
        with tempfile.TemporaryDirectory() as d:
            contract_path = Path(d) / filename
            contract_path.write_text(CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, encoding="utf-8")
            out = io.StringIO()
            argv = ["pr_merged.py", "--contract", str(contract_path),
                    "--record-subtask", "t1-backend", "--issue", "163",
                    "--base", "feature/160-parent", "--brief", ".claude/work-items/x.md",
                    "--json", *extra_args]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value={}), \
                 mock.patch.object(pr_merged, "load_state", return_value=None), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", write_state_mock), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 contextlib.redirect_stdout(out):
                exit_code = pr_merged.main()
        return exit_code, write_state_mock

    def test_dry_run_computes_and_prints_but_never_writes(self):
        exit_code, write_state_mock = self._drive(["--dry-run"])
        self.assertEqual(exit_code, 0)
        self.assertFalse(
            write_state_mock.called,
            "--dry-run's own help text says compute everything and write nothing -- "
            "--record-subtask must not be the one path that ignores it"
        )

    def test_status_also_never_writes(self):
        exit_code, write_state_mock = self._drive(["--status"])
        self.assertEqual(exit_code, 0)
        self.assertFalse(write_state_mock.called)

    def test_without_either_flag_the_write_still_happens(self):
        # Positive control: gating the write must not silently disable it outright.
        exit_code, write_state_mock = self._drive([])
        self.assertEqual(exit_code, 0)
        self.assertTrue(write_state_mock.called)


# --------------------------------------------------------------------------
# Warning 3: close_sub_issue reads state as an allow list, not "not CLOSED".
# --------------------------------------------------------------------------
class TestCloseSubIssueReadsAsAnAllowList(unittest.TestCase):
    def _get(self):
        fn = _fn("close_sub_issue")
        self.assertIsNotNone(fn, "pr_merged.close_sub_issue must exist")
        return fn

    def test_a_payload_with_no_state_key_is_unverifiable_not_open(self):
        close_sub_issue = self._get()
        calls = []

        def fake_run(cmd):
            calls.append(cmd)
            if cmd[:2] == ["gh", "issue"] and "view" in cmd:
                return 0, json.dumps({})  # no "state" key at all
            return 1, "close_sub_issue must not issue this command: %r" % (cmd,)

        with mock.patch.object(pr_merged, "_run", side_effect=fake_run):
            result = close_sub_issue(163, "https://example.invalid/pull/173")

        self.assertEqual(
            result, "unverifiable",
            "a payload that parses but carries no state key must never be read as OPEN -- "
            "an empty string is not CLOSED, so a 'not CLOSED means close it' rule would fire "
            "the mutation having read nothing"
        )
        self.assertFalse(
            any(c[:2] == ["gh", "issue"] and "close" in c for c in calls),
            "an unverifiable read must never be followed by a close mutation"
        )

    def test_a_list_payload_is_unverifiable_not_a_crash(self):
        close_sub_issue = self._get()

        def fake_run(cmd):
            if cmd[:2] == ["gh", "issue"] and "view" in cmd:
                return 0, json.dumps([])  # json.loads returns a list, not a dict
            return 1, "close_sub_issue must not issue this command: %r" % (cmd,)

        with mock.patch.object(pr_merged, "_run", side_effect=fake_run):
            result = close_sub_issue(163, "https://example.invalid/pull/173")

        self.assertEqual(
            result, "unverifiable",
            "json.loads returning a list is not None, so 'or {}' does not catch it -- "
            "calling .get on a list must never reach an uncaught exception"
        )

    def test_an_unrecognised_state_value_is_unverifiable_not_open(self):
        close_sub_issue = self._get()
        calls = []

        def fake_run(cmd):
            calls.append(cmd)
            if cmd[:2] == ["gh", "issue"] and "view" in cmd:
                return 0, json.dumps({"state": "MERGED"})  # not a real issue state
            return 1, "close_sub_issue must not issue this command: %r" % (cmd,)

        with mock.patch.object(pr_merged, "_run", side_effect=fake_run):
            result = close_sub_issue(163, "https://example.invalid/pull/173")

        self.assertEqual(result, "unverifiable")
        self.assertFalse(any(c[:2] == ["gh", "issue"] and "close" in c for c in calls))


# --------------------------------------------------------------------------
# Warning 5: create_branch names which path it took, and never misreports a
# gh-registered branch's failed local checkout as "branch already exists".
# --------------------------------------------------------------------------
class TestCreateBranchNamesThePathDistinctly(unittest.TestCase):
    def test_gh_success_with_a_failed_local_checkout_is_named_on_its_own_terms(self):
        calls = []

        def fake_run(cmd):
            calls.append(cmd)
            if cmd[:2] == ["gh", "issue"] and "develop" in cmd:
                return 0, "https://github.com/acme/repo/tree/task/c/t1-a"
            if cmd[:2] == ["git", "fetch"]:
                return 0, ""
            if cmd[0] == "git" and len(cmd) > 1 and cmd[1] in ("switch", "checkout"):
                return 1, "local checkout blew up"
            return 1, "unexpected command: %r" % (cmd,)

        with mock.patch.object(pr_merged, "_run", side_effect=fake_run):
            ok, detail = pr_merged.create_branch("task/c/t1-a", "feature/160-parent", issue=163)

        self.assertFalse(ok, "a failed local checkout must not be reported as success")
        self.assertIn("163", detail, "the detail must name the sub-issue this path used")
        self.assertIn(
            "local checkout failed", detail,
            "the detail must say the checkout itself failed, not that gh issue develop was "
            "unavailable -- gh succeeded on this path"
        )
        self.assertNotIn(
            "already exists", detail,
            "a branch gh just correctly registered must never be reported as a fresh-dispatch "
            "collision -- the follow-on defect the reviewer found"
        )
        self.assertFalse(
            any(c[:3] == ["git", "rev-parse", "--verify"] for c in calls),
            "the plain-git 'does it already exist' check must never run once gh has already "
            "registered the branch -- that is the exact check that misreports outcome (2) as "
            "outcome (1)"
        )

    def test_gh_failure_outright_is_named_distinctly_from_a_failed_checkout(self):
        calls = []

        def fake_run(cmd):
            calls.append(cmd)
            if cmd[:2] == ["gh", "issue"] and "develop" in cmd:
                return 1, ""  # gh issue develop itself failed
            if cmd[:3] == ["git", "rev-parse", "--verify"]:
                return 1, ""
            if cmd[:2] == ["git", "fetch"]:
                return 0, ""
            if cmd[:3] == ["git", "switch", "-c"]:
                return 0, "created it"
            return 1, "unexpected command: %r" % (cmd,)

        with mock.patch.object(pr_merged, "_run", side_effect=fake_run):
            ok, detail = pr_merged.create_branch("task/c/t1-a", "feature/160-parent", issue=163)

        self.assertTrue(ok, "the plain-git fallback must still succeed when gh fails outright")
        self.assertIn(
            "gh issue develop failed", detail,
            "gh failing outright must be named distinctly from a gh success whose local "
            "checkout failed -- the two must never share one conflated message"
        )


# --------------------------------------------------------------------------
# Warning 6: an unreadable recorded brief must refuse dispatch, not fail open.
# --------------------------------------------------------------------------
class TestMainRefusesDispatchOnAnUnreadableBrief(unittest.TestCase):
    def test_a_brief_path_that_no_longer_resolves_refuses_the_dispatch(self):
        with tempfile.TemporaryDirectory() as d:
            contract_path = Path(d) / "acme-brief-fixture.md"
            contract_path.write_text(CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, encoding="utf-8")
            slug = contract_path.stem
            state = {
                "contract": slug,
                "started_at": "2026-09-19T00:00:00+00:00",
                "sub_tasks": {"t1-backend": {
                    "status": "pending", "branch": None, "pull_request": None,
                    "issue": 163, "base": "feature/160-parent",
                    "brief": str(Path(d) / "vanished-brief.md"),  # never written
                }},
            }
            create_branch_mock = mock.MagicMock(return_value=(True, "created it"))
            out = io.StringIO()
            argv = ["pr_merged.py", "--contract", str(contract_path),
                    "--dispatch", "t1-backend", "--json"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value={}), \
                 mock.patch.object(pr_merged, "load_state", return_value=state), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", return_value=None), \
                 mock.patch.object(pr_merged, "create_branch", create_branch_mock), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 contextlib.redirect_stdout(out):
                exit_code = pr_merged.main()
            printed = out.getvalue()
        payload = json.loads(printed) if printed.strip().startswith("{") else None

        self.assertNotEqual(
            exit_code, 0,
            "a recorded brief path that no longer resolves is unverifiable, not 'nothing to "
            "compare' -- I-7 is a refusal rule, and dispatching anyway would skip the only "
            "check standing between a stale pointer and a mismatched identity"
        )
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("error"), "brief-unreadable")
        self.assertFalse(
            create_branch_mock.called,
            "the dispatch must never cut a branch once its own brief cannot be verified"
        )

    def test_a_missing_brief_key_is_not_treated_as_unreadable(self):
        # Positive control: no brief recorded YET is not itself a mismatch or a failure --
        # there is nothing to compare a state entry against before a brief exists.
        with tempfile.TemporaryDirectory() as d:
            contract_path = Path(d) / "acme-brief-fixture-none.md"
            contract_path.write_text(CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, encoding="utf-8")
            slug = contract_path.stem
            state = {
                "contract": slug,
                "started_at": "2026-09-19T00:00:00+00:00",
                "sub_tasks": {"t1-backend": {
                    "status": "pending", "branch": None, "pull_request": None,
                    "issue": 163, "base": "feature/160-parent", "brief": None,
                }},
            }
            create_branch_mock = mock.MagicMock(return_value=(True, "created it"))
            out = io.StringIO()
            argv = ["pr_merged.py", "--contract", str(contract_path),
                    "--dispatch", "t1-backend", "--json"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value={}), \
                 mock.patch.object(pr_merged, "load_state", return_value=state), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", return_value=None), \
                 mock.patch.object(pr_merged, "create_branch", create_branch_mock), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 contextlib.redirect_stdout(out):
                exit_code = pr_merged.main()

        self.assertEqual(
            exit_code, 0,
            "a sub-task with no brief recorded yet must still be dispatchable -- absence is "
            "not the same thing as an unreadable pointer"
        )
        self.assertTrue(create_branch_mock.called)


# ==========================================================================
# Contract: "Make the contract loop's next step survive a cleared session"
#   .claude/concepts/2026-09-22-loop-next-step-survives-clear.md  (approved)
#
# RED phase, sub-task 1. Every case below states one behaviour that contract
# ADDS, and none of it exists yet. Not-yet-built symbols are looked up through
# _fn() (line 98) so an absent function becomes an explicit assertion failure
# naming it, never an ImportError that would redden the whole file; not-yet-
# built PARAMETERS are checked through inspect.signature first, so a missing
# keyword becomes an assertion failure rather than a TypeError. Both shapes
# follow the precedent this suite already set for review_verdict.
#
# Each class names, in a comment, the one-line mutation that turns its
# assertions red -- the positive control. Where an assertion is already green
# today (it pins behaviour the contract says must NOT change), the control is
# a mutation of a fixture the test owns, and it was run under `py -3 -B` so a
# stale bytecode cache cannot report a restored file's old answer.
# ==========================================================================


# --------------------------------------------------------------------------
# (a) The Hand-Resolved Summary -- three facts, never one list.
#
# Data Shapes, Hand-Resolved Summary: files (ordered, de-duplicated, possibly
# empty), merge_commits (inspected commits carrying two or more parents),
# commits_inspected (commits the pull request reported). The whole point of
# the shape is that merge_commits separates "nothing was conflicted" from
# "nothing was inspectable" -- a squash or rebase merge leaves no merge commit
# to read, and reporting that as clean is a claim nobody measured
# (Alternatives Considered, Option D).
# --------------------------------------------------------------------------
class TestSummariseHandResolved(unittest.TestCase):

    def _summarise(self):
        fn = _fn("summarise_hand_resolved")
        self.assertIsNotNone(
            fn,
            "pr_merged.summarise_hand_resolved must exist -- Extension Point 1 names it the "
            "pure function that performs the walk detect_resolved_files performs today and "
            "returns a Hand-Resolved Summary instead of a bare list"
        )
        return fn

    def test_a_merge_commit_reports_its_files_and_is_counted(self):
        # POSITIVE CONTROL (fixture-owned, run under `py -3 -B`): change this
        # fixture's parent count from 2 to 1 -- {"m1": (["a.md", "b.md"], 1)} --
        # and files reads [] with merge_commits 0, turning all three assertions
        # red. Measured: detect_resolved_files(["m1"], <1-parent fixture>) == [].
        summarise = self._summarise()

        def fake_git(sha):
            return {"m1": (["a.md", "b.md"], 2)}[sha]

        got = summarise(["m1"], fake_git)
        self.assertEqual(
            got["files"], ["a.md", "b.md"],
            "the summary's files must carry exactly what the combined diff reported, in the "
            "order it reported them -- this is the finding that is computed and thrown away today"
        )
        self.assertEqual(
            got["merge_commits"], 1,
            "a commit with two parents is an inspected merge commit and must be counted, so a "
            "reader can tell a measured clean merge from an unmeasurable one"
        )
        self.assertEqual(
            got["commits_inspected"], 1,
            "commits_inspected counts every commit the pull request reported, whatever its "
            "parent count"
        )

    def test_the_summary_carries_exactly_those_three_keys_and_no_verdict(self):
        # The KEY SET, not just the three values. Every other case in this
        # class passes with a fourth key present, and the fourth key a reader
        # reaches for first is a derived judgement -- "clean": not files --
        # which is precisely the overclaim Alternatives Considered rejected
        # Option D for: it re-collapses the four-state reading the shape exists
        # to hold open, and it does so under a name nobody can argue with.
        # POSITIVE CONTROL, measured against a throwaway stub
        # summarise_hand_resolved that also returns "clean": not files -- this
        # assertion goes red. Stated exactly, because the run was watched: two
        # other cases go red with it, the pair in
        # TestMainPassesTheSummaryIntoBuildRecord, which compare the whole
        # summary for equality at the call site. No case that reads only the
        # three values moves, which is the hole this fills.
        summarise = self._summarise()

        def fake_git(sha):
            return {"m1": (["a.md"], 2)}[sha]

        got = summarise(["m1"], fake_git)
        self.assertEqual(
            set(got), {"files", "merge_commits", "commits_inspected"},
            "the Hand-Resolved Summary is exactly three facts (Data Shapes, Value Objects). A "
            "fourth field carrying a judgement -- clean, safe, ok -- is a claim nobody "
            "measured; the four-state reading belongs to whoever reads the three facts, and "
            "the summary read %r" % (sorted(got),)
        )

    def test_files_are_de_duplicated_and_keep_first_seen_order(self):
        # POSITIVE CONTROL (fixture-owned): make m2 report ["c.md", "b.md"]
        # instead of ["b.md", "c.md"] and the expected order becomes
        # ["a.md", "b.md", "c.md"] no longer -- the assertion turns red.
        summarise = self._summarise()

        def fake_git(sha):
            return {"m1": (["a.md", "b.md"], 2), "m2": (["b.md", "c.md"], 2)}[sha]

        got = summarise(["m1", "m2"], fake_git)
        self.assertEqual(
            got["files"], ["a.md", "b.md", "c.md"],
            "the summary must de-duplicate exactly as detect_resolved_files does today, "
            "keeping first-seen order -- Extension Point 2 requires the projection to be "
            "indistinguishable from the function it replaces"
        )
        self.assertEqual(
            got["merge_commits"], 2,
            "both inspected commits carried two parents, so both are merge commits"
        )

    def test_a_commit_list_with_no_merge_commit_yields_zero_merges_and_no_files(self):
        # POSITIVE CONTROL (fixture-owned): raise this fixture's parent counts
        # to 2 and merge_commits must read 2 with files ["x", "y"] -- every
        # assertion below turns red.
        summarise = self._summarise()

        def fake_git(sha):
            return {"c1": (["x"], 1), "c2": (["y"], 1)}[sha]

        got = summarise(["c1", "c2"], fake_git)
        self.assertEqual(
            got["merge_commits"], 0,
            "no inspected commit carried two parents, so nothing was detectable -- this is the "
            "squash-or-rebase reading the summary exists to keep distinct from clean"
        )
        self.assertEqual(
            got["files"], [],
            "a commit with fewer than two parents has no combined diff to read, so it "
            "contributes no files"
        )
        self.assertEqual(
            got["commits_inspected"], 2,
            "both commits were inspected even though neither was a merge -- that is exactly "
            "what makes merge_commits zero readable as 'not detectable' rather than 'no commits'"
        )

    def test_an_empty_commit_list_yields_all_zeroes(self):
        # POSITIVE CONTROL (fixture-owned): pass ["m1"] with a two-parent fake
        # instead of [] and every one of these assertions turns red.
        summarise = self._summarise()
        calls = []

        def fake_git(sha):  # pragma: no cover -- must never be reached
            calls.append(sha)
            raise AssertionError("the walk must not ask git about a commit nobody reported")

        got = summarise([], fake_git)
        self.assertEqual(got["files"], [], "no commits means no files, never a guess")
        self.assertEqual(got["merge_commits"], 0, "no commits means no merge commits")
        self.assertEqual(
            got["commits_inspected"], 0,
            "a pull request nobody could inspect reads as all zeroes -- Uncertain Assumptions: "
            "'the walk simply iterates nothing and returns zeroes'"
        )
        self.assertEqual(calls, [], "an empty commit list must start no git read at all")


# --------------------------------------------------------------------------
# (b) detect_resolved_files is re-expressed as summarise_hand_resolved(...)
# ["files"] and must stay indistinguishable from what it is today.
#
# Extension Point 2: "Its signature, its ordering, its de-duplication and its
# skip-commits-with-fewer-than-two-parents rule are unchanged, so its existing
# tests and its recorded mutation probes stay valid."
# --------------------------------------------------------------------------
#: name -> (fake git table, commit shas, the list detect_resolved_files returns
#: today). The first three rows are exactly the fixtures TestResolvedFiles
#: already drives (test_pr_merged.py:322-337); the fourth adds the
#: de-duplication path those three never exercise.
_RESOLVED_FILE_FIXTURES = (
    ("a clean merge", {"m1": ([], 2)}, ["m1"], []),
    ("files differing from both parents", {"m1": (["a.md", "b.md"], 2)}, ["m1"], ["a.md", "b.md"]),
    ("a single-parent commit", {"c1": (["x"], 1)}, ["c1"], []),
    ("duplicates across two merges",
     {"m1": (["a.md", "b.md"], 2), "m2": (["b.md", "c.md"], 2)},
     ["m1", "m2"], ["a.md", "b.md", "c.md"]),
)


def _fake_git(table):
    def fake(sha):
        return table[sha]
    return fake


class TestDetectResolvedFilesIsTheSummarysFileProjection(unittest.TestCase):

    def test_detect_resolved_files_still_returns_exactly_the_same_list(self):
        # GREEN today and required to stay green: this pins the behaviour the
        # contract says must NOT change while the walk moves underneath it.
        # POSITIVE CONTROL (fixture-owned, run under `py -3 -B`): change the
        # "a single-parent commit" row's parent count from 1 to 2 and its
        # expected [] becomes ["x"] -- the assertion turns red. Measured.
        for name, table, shas, expected in _RESOLVED_FILE_FIXTURES:
            with self.subTest(fixture=name):
                self.assertEqual(
                    detect_resolved_files(shas, _fake_git(table)), expected,
                    "detect_resolved_files must return exactly the same list, in the same "
                    "order, with the same de-duplication, for %r -- Extension Point 2 keeps "
                    "the name and forbids changing its rule" % name
                )

    def test_detect_resolved_files_equals_the_summarys_files_for_every_fixture(self):
        # RED: summarise_hand_resolved does not exist. Once it does, this pins
        # that the two names AGREE on every fixture this suite drives -- the
        # ordering, the de-duplication and the skip-fewer-than-two-parents rule
        # Extension Point 2 keeps unchanged -- and that each name reads every
        # reported commit exactly ONCE per call.
        #
        # What this case does and does not claim, stated exactly, because two
        # earlier drafts disagreed with each other inside the same hunk. It
        # does NOT claim that detect_resolved_files delegates: a genuine second
        # implementation that iterates once and agrees on these four fixtures
        # passes here unharmed, and no assertion at this level can tell the two
        # apart. What Extension Point 2 actually forbids -- "the walk must not
        # happen twice" -- is pinned where it is observable, in
        # TestTheWalkHappensOnceForEachCommit below, which counts the reads one
        # main() run makes per commit identifier. The because-clauses here
        # claim agreement and one-read-per-commit, and nothing wider.
        # POSITIVE CONTROL (fixture-owned): drop the "duplicates across two
        # merges" row's second sha from ["m1", "m2"] to ["m1"] while leaving
        # its expected list at three entries, and the row turns red.
        summarise = _fn("summarise_hand_resolved")
        self.assertIsNotNone(
            summarise,
            "pr_merged.summarise_hand_resolved must exist before detect_resolved_files can be "
            "a projection of it"
        )
        for name, table, shas, expected in _RESOLVED_FILE_FIXTURES:
            with self.subTest(fixture=name):
                self.assertEqual(
                    detect_resolved_files(shas, _fake_git(table)),
                    summarise(shas, _fake_git(table))["files"],
                    "detect_resolved_files and the summary's files projection must AGREE for "
                    "%r -- same order, same de-duplication, same skip rule. Extension Point 2 "
                    "keeps the name and forbids changing its rule" % name
                )
                for reader_name, reader in (("detect_resolved_files", detect_resolved_files),
                                            ("summarise_hand_resolved", summarise)):
                    seen = []

                    def counting(sha, _table=table, _seen=seen):
                        _seen.append(sha)
                        return _table[sha]

                    reader(shas, counting)
                    self.assertEqual(
                        seen, list(shas),
                        "%s must read each reported commit exactly once, in the order the pull "
                        "request reported them, for %r -- a body that reads a commit twice is "
                        "asking git the same question twice and paying for it. It read %r"
                        % (reader_name, name, seen)
                    )


# --------------------------------------------------------------------------
# (c) build_record writes hand_resolved whenever a summary is supplied,
# INCLUDING when the file list is empty (invariant I-1), and omits the key
# only when None is supplied (invariant I-3, which protects every record
# written before this change).
# --------------------------------------------------------------------------
class TestBuildRecordCarriesHandResolved(unittest.TestCase):

    def _require_parameter(self):
        sig = inspect.signature(build_record)
        self.assertIn(
            "hand_resolved", sig.parameters,
            "build_record must accept a hand_resolved keyword -- Extension Point 3. Today it "
            "takes verdict, commit, pr_url, merged_at, checks, review_verdict and "
            "sub_issue_closed, so the finding main() computes at pr_merged.py:1160 is printed "
            "and then discarded"
        )

    def test_a_supplied_summary_is_stamped_into_the_record(self):
        # POSITIVE CONTROL (fixture-owned): change the expected merge_commits
        # in this fixture from 1 to 2 and the equality assertion turns red.
        self._require_parameter()
        summary = {"files": ["src/Hand.cs"], "merge_commits": 1, "commits_inspected": 4}
        rec = build_record("merged", commit="abc123", pr_url="u", merged_at="t", checks=None,
                           hand_resolved=summary)
        self.assertEqual(
            rec.get("hand_resolved"), summary,
            "the summary passed to build_record must be stamped into the record it returns, "
            "whole -- all three fields, not just the file list"
        )

    def test_an_empty_file_list_is_still_written_never_omitted(self):
        # I-1: "written on EVERY record produced for a pull request that mapped
        # to a sub-task, including when no files were found. It is never
        # omitted to mean empty."
        # POSITIVE CONTROL, measured against a throwaway stub build_record
        # that writes the key only when the file list is non-empty (the exact
        # "omit it to mean empty" defect I-1 forbids). RE-MEASURED at subtest
        # granularity: TWO cases go red, not one. This case, and
        # test_a_pull_request_with_nothing_inspectable_still_hands_over_the
        # _summary, which reaches the same defect through the record main()
        # actually writes. The earlier "nothing else does" was written before
        # that second case existed and went stale the moment it was added.
        # Paired with test_only_none_omits_the_key below,
        # which goes red against a stub that always stamps the key -- so no
        # implementation can satisfy both by always writing or always omitting.
        self._require_parameter()
        summary = {"files": [], "merge_commits": 2, "commits_inspected": 5}
        rec = build_record("merged", commit="abc123", pr_url="u", merged_at="t", checks=None,
                           hand_resolved=summary)
        self.assertIn(
            "hand_resolved", rec,
            "a summary whose file list is empty is a MEASUREMENT (two merge commits were "
            "inspected and neither was conflicted) and must be recorded; omitting it would "
            "make it indistinguishable from a record written before this change"
        )
        self.assertEqual(
            rec["hand_resolved"], summary,
            "the empty file list must be recorded as empty, with its two counts intact"
        )

    def test_only_none_omits_the_key(self):
        # POSITIVE CONTROL, measured against a throwaway stub build_record
        # that stamps rec["hand_resolved"] = hand_resolved unconditionally:
        # this case goes red and nothing else does, because a null under the
        # key is exactly the value I-2 must be able to distinguish from an
        # absent key.
        self._require_parameter()
        rec = build_record("merged", commit="abc123", pr_url="u", merged_at="t", checks=None,
                           hand_resolved=None)
        self.assertNotIn(
            "hand_resolved", rec,
            "None means no summary was supplied, and the key must be OMITTED rather than "
            "stamped null -- I-2 reads an absent key as not-recorded, so a null would launder "
            "'nobody measured' into a stored value"
        )


# --------------------------------------------------------------------------
# (d) + (i) The report side: a read-only run reports the summaries already on
# disk (Extension Point 5), and a record written before this change is
# reported as not-recorded rather than as clean (invariant I-2).
# --------------------------------------------------------------------------
def _drive_main_with_flags(contract_text, flags, records=None, filename="acme-red-fixture.md"):
    """Call pr_merged.main() the way the command line does, with chosen flags.

    Mirrors _drive_main_report (test_pr_merged.py:943) exactly, except that the
    flag list and the stored completion records are the caller's to choose, and
    write_state / write_record are MagicMocks so a test can ask whether a run
    wrote anything. The contract is a literal written to a throwaway temp file;
    nothing reaches git, GitHub or this project's own orchestrator directories.

    Returns (raw stdout, write_state mock, write_record mock).
    """
    write_state_mock = mock.MagicMock(return_value=None)
    write_record_mock = mock.MagicMock(return_value=None)
    with tempfile.TemporaryDirectory() as d:
        contract_path = Path(d) / filename
        contract_path.write_text(contract_text, encoding="utf-8")
        out = io.StringIO()
        argv = ["pr_merged.py", "--contract", str(contract_path)] + list(flags)
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pr_merged, "load_records", return_value=dict(records or {})), \
             mock.patch.object(pr_merged, "load_state", return_value=None), \
             mock.patch.object(pr_merged, "default_branch", return_value="master"), \
             mock.patch.object(pr_merged, "write_state", write_state_mock), \
             mock.patch.object(pr_merged, "write_record", write_record_mock), \
             mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
             mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
             contextlib.redirect_stdout(out):
            pr_merged.main()
        return out.getvalue(), write_state_mock, write_record_mock


#: The record a post-change run writes: a summary that measured something.
_RECORD_WITH_SUMMARY = {
    "status": "completed", "verified": "github", "pull_request": "u",
    "hand_resolved": {"files": ["src/Hand.cs"], "merge_commits": 1, "commits_inspected": 3},
}

#: The record every run written before this change left behind: no key at all.
_RECORD_WITHOUT_SUMMARY = {"status": "completed", "verified": "github", "pull_request": "u"}


#: Both read-only front doors, driven by every case in the class below.
#: The criterion names --status AND --resume, and a seeding step that runs
#: under --status alone satisfies a --status-only case. Measured against a
#: throwaway stub whose seeding loop is skipped whenever args.resume is set:
#: the --resume row of each case below goes red and the --status row of each
#: stays green -- and --status was the only flag set this class drove before
#: it was parametrised.
_READ_ONLY_FLAG_SETS = (["--status", "--json"], ["--resume", "--json"])


class TestReportSeedsHandResolvedFromStoredRecords(unittest.TestCase):
    """The cases below are the only ones in this block whose control cannot be
    RUN before the implementation lands: both drive main(), and main()'s
    seeding step does not exist to be mutated. What was measured instead is
    that their assertion predicates FLIP between the two entry shapes they pin
    -- the seeded shape satisfies the (i) assertions and fails the
    not-recorded one; the absent shape does the reverse. Neither case is
    vacuous, and an implementation that stamps every entry "not-recorded"
    fails the first while one that seeds only real summaries fails the second.
    """

    def _entry_for(self, report, sub_task):
        self.assertIn(
            "hand_resolved", report,
            "the report must carry a hand_resolved entry list -- it does today, but only ever "
            "filled from the pull-request loop"
        )
        return next((e for e in report["hand_resolved"] if e.get("sub_task") == sub_task), None)

    def test_a_read_only_run_reports_a_stored_summary_without_processing_a_pull_request(self):
        # (i) -- Extension Point 5. RED today: report["hand_resolved"] is
        # seeded nowhere but inside the pull-request loop, so a read-only run
        # with no --pr always reports an empty list. Driven over BOTH read-only
        # front doors, because the criterion names both and seeding placed
        # under the --status branch alone satisfies neither half of it.
        # POSITIVE CONTROL (fixture-owned): key the stored record under
        # "t9-ghost" instead of "t1-backend" and the entry lookup finds
        # nothing, turning the first assertion red.
        for flags in _READ_ONLY_FLAG_SETS:
            with self.subTest(flags=" ".join(flags)):
                text, _, _ = _drive_main_with_flags(
                    CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, flags,
                    records={"t1-backend": _RECORD_WITH_SUMMARY})
                report = json.loads(text)
                entry = self._entry_for(report, "t1-backend")
                self.assertIsNotNone(
                    entry,
                    "a session that never saw the merge must still be able to report what was "
                    "resolved by hand under %r -- the summary is already on disk in the "
                    "completion record, and Extension Point 5 seeds the report from it before "
                    "the pull-request loop" % " ".join(flags)
                )
                self.assertEqual(
                    entry.get("files"), ["src/Hand.cs"],
                    "the stored file list must be reported verbatim, not recomputed -- nothing "
                    "in a cleared session can walk a branch history that was merged days ago"
                )
                self.assertEqual(
                    entry.get("merge_commits"), 1,
                    "the stored merge-commit count must travel with the file list; without it "
                    "the reader cannot tell a measured reading from an unmeasurable one"
                )
                self.assertEqual(
                    entry.get("commits_inspected"), 3,
                    "the stored inspected-commit count must travel with the file list for the "
                    "same reason"
                )

    def test_a_record_with_no_hand_resolved_key_is_reported_as_not_recorded(self):
        # (d) -- invariant I-2 and the second Failure Mode: "A completion
        # record written before this change is read as 'no files were resolved
        # by hand', silently clearing a risk nobody measured." Driven over both
        # read-only front doors for the reason above.
        # POSITIVE CONTROL (fixture-owned): swap _RECORD_WITHOUT_SUMMARY for
        # _RECORD_WITH_SUMMARY here and "not-recorded" must no longer appear
        # in the entry, turning the assertion red -- so an implementation that
        # simply stamps every entry "not-recorded" cannot pass both this case
        # and the one above.
        for flags in _READ_ONLY_FLAG_SETS:
            with self.subTest(flags=" ".join(flags)):
                text, _, _ = _drive_main_with_flags(
                    CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, flags,
                    records={"t1-backend": _RECORD_WITHOUT_SUMMARY})
                report = json.loads(text)
                entry = self._entry_for(report, "t1-backend")
                self.assertIsNotNone(
                    entry,
                    "a record with no hand_resolved key must still be ACCOUNTED FOR in the "
                    "report under %r -- silence is what makes an unmeasured risk read as a "
                    "clean one" % " ".join(flags)
                )
                flat = json.dumps(entry, sort_keys=True, default=str)
                self.assertIn(
                    "not-recorded", flat,
                    "I-2: a record with no hand_resolved key was written before this change, "
                    "and the report must name that reading. The entry read %r" % flat
                )
                self.assertNotIn(
                    "clean", flat,
                    "nobody measured this pull request, so the report must never describe it "
                    "as clean"
                )
                self.assertNotEqual(
                    entry.get("files"), [],
                    "an absent summary must not be rendered as an empty file list -- an empty "
                    "list is the one reading that means 'inspected and nothing was conflicted', "
                    "and handing it to a renderer is exactly how not-measured becomes clean"
                )


# --------------------------------------------------------------------------
# (c2) The CALL SITE: main() passes the summary into build_record.
#
# Extension Point 4. build_record's parameter is pinned above in isolation,
# which says nothing about whether anything ever passes it. Two implementations
# satisfy every other assertion in this file: one that passes
# hand_resolved=None, and one that passes the summary only when the file list
# is non-empty -- the exact "omit it to mean empty" defect I-1 forbids, reached
# through the one path that writes a record to disk.
# --------------------------------------------------------------------------
def _drive_main_over_a_pull_request(contract_text, commits, diff_table,
                                    filename="acme-red-fixture.md"):
    """Call pr_merged.main() with --pr so the pull-request loop actually runs.

    Every edge the loop has to the outside is replaced before main() is
    entered: ``gh_pr`` returns the literal pull request built below,
    ``git_combined_diff`` answers out of ``diff_table``, ``file_at_commit``
    returns nothing, ``write_state`` and ``write_record`` are mocks, and
    ``pr_merged._run`` itself raises -- so no subprocess can start even down a
    path this fixture did not anticipate. The module's subprocess guard near
    line 69 is left exactly as it is and is never reached.

    ``build_record`` is WRAPPED rather than replaced. The wrapper records the
    keyword arguments main() actually passed, then calls the real function with
    the keywords its current signature accepts -- so the record that reaches
    ``write_record`` is the real one, and the call site stays observable before
    the parameter exists. Without the filter an absent parameter would raise
    TypeError, which is a broken fixture rather than a red test.

    Returns (the keyword arguments main() passed to build_record,
    the write_record mock, the parsed --json report).
    """
    recorded = {}
    real_build_record = pr_merged.build_record
    accepted = set(inspect.signature(real_build_record).parameters)

    def recording_build_record(*a, **kw):
        recorded.clear()
        recorded.update(kw)
        return real_build_record(*a, **{k: v for k, v in kw.items() if k in accepted})

    def no_subprocess(cmd):  # pragma: no cover -- must never be reached
        raise AssertionError(
            "this fixture must reach no process at all; %r was attempted" % (cmd,))

    pull_request = {
        "state": "MERGED", "mergedAt": "2026-09-22T00:00:00Z",
        "mergeCommit": {"oid": "merge-sha"}, "baseRefName": "master",
        "headRefName": "task/acme-red-fixture/t1-backend", "title": "t1-backend",
        "url": "https://example.invalid/pr/7",
        "commits": [{"oid": sha} for sha in commits], "statusCheckRollup": None,
    }
    write_record_mock = mock.MagicMock(return_value=None)
    with tempfile.TemporaryDirectory() as d:
        contract_path = Path(d) / filename
        contract_path.write_text(contract_text, encoding="utf-8")
        out = io.StringIO()
        argv = ["pr_merged.py", "--contract", str(contract_path), "--pr", "7", "--json"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pr_merged, "load_records", return_value={}), \
             mock.patch.object(pr_merged, "load_state", return_value=None), \
             mock.patch.object(pr_merged, "default_branch", return_value="master"), \
             mock.patch.object(pr_merged, "write_state", mock.MagicMock(return_value=None)), \
             mock.patch.object(pr_merged, "write_record", write_record_mock), \
             mock.patch.object(pr_merged, "build_record", recording_build_record), \
             mock.patch.object(pr_merged, "gh_pr", lambda number: pull_request), \
             mock.patch.object(pr_merged, "git_combined_diff", lambda sha: diff_table[sha]), \
             mock.patch.object(pr_merged, "file_at_commit", lambda sha, path: None), \
             mock.patch.object(pr_merged, "_run", no_subprocess), \
             mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
             mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
             contextlib.redirect_stdout(out):
            pr_merged.main()
        return recorded, write_record_mock, json.loads(out.getvalue())


#: (commit shas the pull request reports, the git table, the summary the walk
#: must produce from them). The first found a file; the second inspected two
#: commits and neither was a merge, which is a MEASUREMENT and not an absence.
_PR_THAT_FOUND_A_FILE = (
    ["c1", "m1"], {"c1": ([], 1), "m1": (["src/Hand.cs"], 2)},
    {"files": ["src/Hand.cs"], "merge_commits": 1, "commits_inspected": 2},
)
_PR_WITH_NOTHING_INSPECTABLE = (
    ["c1", "c2"], {"c1": ([], 1), "c2": ([], 1)},
    {"files": [], "merge_commits": 0, "commits_inspected": 2},
)


class TestMainPassesTheSummaryIntoBuildRecord(unittest.TestCase):

    def _drive(self, case):
        commits, table, expected = case
        recorded, write_record_mock, _report = _drive_main_over_a_pull_request(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, commits, table)
        self.assertTrue(
            write_record_mock.called,
            "fixture sanity: this run must reach the pull-request loop and write one record. "
            "If it does not, every assertion below is measuring a loop that never ran"
        )
        return recorded, write_record_mock, expected

    def test_a_pull_request_that_found_files_hands_the_whole_summary_to_build_record(self):
        # POSITIVE CONTROL, measured against a throwaway stub main() that
        # computes the summary and passes build_record nothing -- today's
        # shape, kept after the parameter exists: this case and the one below
        # both go red naming the keywords that were passed.
        recorded, write_record_mock, expected = self._drive(_PR_THAT_FOUND_A_FILE)
        self.assertIn(
            "hand_resolved", recorded,
            "main() must PASS the summary into build_record (Extension Point 4). It computes "
            "the finding at the top of the loop, prints it and discards it, handing build_record "
            "only review_verdict and sub_issue_closed. The keywords it passed were %r"
            % (sorted(recorded),)
        )
        self.assertEqual(
            recorded["hand_resolved"], expected,
            "the three facts must arrive whole at the call site -- a bare file list here is the "
            "shape the Hand-Resolved Summary exists to replace"
        )
        written = write_record_mock.call_args[0][2]
        self.assertEqual(
            written.get("hand_resolved"), expected,
            "and the record that reaches write_record must carry it, which is the only reason "
            "passing it matters: the record on disk is what a cleared session reads back"
        )

    def test_a_pull_request_with_nothing_inspectable_still_hands_over_the_summary(self):
        # I-1 at the only call site that produces a real record: "written on
        # EVERY record produced for a pull request that mapped to a sub-task,
        # including when no files were found. It is never omitted to mean
        # empty."
        # POSITIVE CONTROL, measured against a throwaway stub main() that
        # passes hand_resolved only when the summary's file list is non-empty:
        # this case goes red and the case above stays green. Against a stub
        # passing hand_resolved=None, both go red, and the None assertion
        # below is the one that names which defect it was.
        recorded, write_record_mock, expected = self._drive(_PR_WITH_NOTHING_INSPECTABLE)
        self.assertIn(
            "hand_resolved", recorded,
            "a walk that inspected two commits and found no merge commit MEASURED something, "
            "and I-1 forbids omitting the key to mean empty -- an absent key is how a record "
            "written before this change is recognised (I-2), so omitting it here would launder "
            "a real reading into 'nobody looked'. The keywords passed were %r" % (sorted(recorded),)
        )
        self.assertIsNotNone(
            recorded.get("hand_resolved"),
            "None is how build_record is told no summary was supplied, and a mapped pull "
            "request always has one -- passing None reaches I-2's not-recorded reading by a "
            "different road"
        )
        self.assertEqual(
            recorded["hand_resolved"], expected,
            "an empty file list travels with its two counts; they are what make it readable as "
            "'nothing was detectable' rather than 'nothing was conflicted'"
        )
        written = write_record_mock.call_args[0][2]
        self.assertEqual(
            written.get("hand_resolved"), expected,
            "and the written record carries the same three facts, empty file list included"
        )


# --------------------------------------------------------------------------
# (e) ADVANCE_ACTIONS -- the closed set of moves advance() can return.
#
# The third Failure Mode: "A new move is added to advance later and ships with
# no printed next step, so the loop silently regains the defect this contract
# removes." The mitigation is this constant plus a test that drives advance()
# into each of the seven REAL scenarios.
# --------------------------------------------------------------------------
#: Extension Point 6, verbatim.
_CONTRACT_ADVANCE_ACTIONS = (
    "contract-defect", "nothing-planned", "escalate", "awaiting-merge",
    "complete", "dispatch", "blocked",
)


def _seven_real_moves():
    """Drive advance() into each of its seven real scenarios.

    Nothing here hand-writes a move mapping: every value is what advance()
    itself returns, so a move that changed shape or stopped being reachable
    shows up here rather than in prose.
    """
    blocked_tasks = _tasks()
    blocked_tasks[0].depends_on = [99]  # an ordinal the plan does not contain
    dispatched = mark_dispatched(new_state("c-slug", _tasks()), "t1-a", "task/c-slug/t1-a")
    completed = {t.id: {"status": "completed", "verified": "github"} for t in _tasks()}
    return {
        "contract-defect": advance(_tasks(), {},
                                   defects=[{"id": "t9-x",
                                             "reason": "no-files-but-names-an-agent"}]),
        "nothing-planned": advance([], {}),
        "escalate": advance(_tasks(), {"t1-a": {"status": "failed", "verified": "github"}}),
        "awaiting-merge": advance(_tasks(), {}, state=dispatched),
        "complete": advance(_tasks(), completed),
        "dispatch": advance(_tasks(), {}),
        "blocked": advance(blocked_tasks, {}),
    }


class TestAdvanceActionsIsTheClosedSet(unittest.TestCase):

    def _actions(self):
        actions = _fn("ADVANCE_ACTIONS")
        self.assertIsNotNone(
            actions,
            "pr_merged.ADVANCE_ACTIONS must exist -- Extension Point 6 names it the module "
            "constant holding the seven moves advance() can return, and the New Mechanisms "
            "section makes it the seam a new move must pass through"
        )
        return actions

    def test_the_constant_holds_exactly_the_seven_moves_the_contract_lists(self):
        # POSITIVE CONTROL (fixture-owned): drop "contract-defect" from
        # _CONTRACT_ADVANCE_ACTIONS and both assertions turn red -- the set
        # comparison and the length. Open Question one answered that all seven
        # are covered, contract-defect included.
        actions = self._actions()
        self.assertEqual(
            set(actions), set(_CONTRACT_ADVANCE_ACTIONS),
            "ADVANCE_ACTIONS must hold exactly the seven moves Extension Point 6 lists -- no "
            "more, so a member with no arm cannot hide; no fewer, so a move advance() can "
            "return cannot ship with no printed next step"
        )
        self.assertEqual(
            len(actions), 7,
            "seven moves, not six: advance() checks contract-defect BEFORE every other move, "
            "so it is the one an operator meets when a contract is malformed"
        )

    def test_each_of_the_seven_real_scenarios_returns_a_member_of_the_set(self):
        # This is the totality test the third Failure Mode names. It never
        # hand-writes an action string: every one comes out of advance().
        # POSITIVE CONTROL (fixture-owned): change the "blocked" scenario's
        # depends_on from [99] to [] and advance() answers "dispatch", so the
        # observed set loses "blocked" and the last assertion turns red.
        actions = self._actions()
        moves = _seven_real_moves()
        observed = set()
        for scenario, move in moves.items():
            with self.subTest(scenario=scenario):
                self.assertEqual(
                    move["action"], scenario,
                    "fixture sanity: the %r scenario must actually drive advance() into the "
                    "%r move" % (scenario, scenario)
                )
                self.assertIn(
                    move["action"], actions,
                    "advance() returned %r, which is not in ADVANCE_ACTIONS -- a move outside "
                    "the closed set has no arm in next_command_for and would ship with no "
                    "printed next step" % move["action"]
                )
            observed.add(move["action"])
        self.assertEqual(
            observed, set(actions),
            "every member of ADVANCE_ACTIONS must be reachable from a real scenario; a member "
            "no scenario produces is a claim nobody measured"
        )


# --------------------------------------------------------------------------
# (f) next_command_for -- the Next Command mechanism.
#
# New Mechanisms: "a human-facing next step is data the owner returns, never
# prose a caller composes." One arm per member of ADVANCE_ACTIONS, plus a
# fail-closed fallback. I-5: an empty command list is a valid, meaningful
# value and always travels with a non-empty reason.
#
# `move` is advance()'s own return mapping, not a bare action string: the
# blocked arm's reason has to name what holds each sub-task (brief acceptance
# criterion four), and only the mapping carries that.
# --------------------------------------------------------------------------
class TestNextCommandFor(unittest.TestCase):

    def setUp(self):
        self.next_command_for = _fn("next_command_for")
        self.assertIsNotNone(
            self.next_command_for,
            "pr_merged.next_command_for must exist -- Extension Point 7 names it the pure "
            "function returning a Next Command, with one arm per member of ADVANCE_ACTIONS"
        )
        self.moves = _seven_real_moves()

    def _command_for(self, scenario):
        nc = self.next_command_for(self.moves[scenario], "c-slug")
        self.assertIn("commands", nc, "a Next Command must carry a commands list")
        self.assertIn("reason", nc, "a Next Command must carry a reason")
        self.assertIsInstance(nc["commands"], list, "commands is an ordered list of lines")
        self.assertIsInstance(nc["reason"], str, "reason is one plain line")
        return nc

    def test_dispatch_gives_the_clear_line_then_the_advance_line(self):
        # POSITIVE CONTROL (fixture-owned): ask for self.moves["complete"]
        # instead of self.moves["dispatch"] and the clear line is gone,
        # turning the ordering assertions red.
        nc = self._command_for("dispatch")
        self.assertEqual(
            len(nc["commands"]), 2,
            "dispatch is the one move whose next step is two lines: clear the session, then "
            "advance. Isolation that depends on the operator remembering to clear is the third "
            "gap this contract closes"
        )
        self.assertIn(
            "/clear", nc["commands"][0],
            "the clear line comes FIRST -- advancing before clearing inherits the previous "
            "sub-task's transcript, which is the isolation failure this exists to remove"
        )
        self.assertIn(
            "/advance", nc["commands"][1],
            "the advance line comes second, after the clear"
        )
        self.assertIn(
            "c-slug", nc["commands"][1],
            "the advance line must name the contract it advances -- a cleared session has no "
            "memory of which contract it was working on, which is the whole premise"
        )

    def test_awaiting_merge_gives_the_pr_merged_line(self):
        # POSITIVE CONTROL (fixture-owned): ask for self.moves["dispatch"]
        # instead and the command names /advance, not /pr-merged -- red.
        nc = self._command_for("awaiting-merge")
        self.assertEqual(
            len(nc["commands"]), 1,
            "a sub-task out for merge has exactly one next step and it is not a clear"
        )
        self.assertIn(
            "/pr-merged", nc["commands"][0],
            "the loop suspends across an unbounded human wait; /pr-merged is what wakes it"
        )

    def test_the_awaiting_merge_reason_names_the_sub_task_and_its_branch(self):
        # The fifth Failure Mode's mitigation, which had no witness: "the
        # reason line names the awaiting sub-task and its branch, so the
        # number is one command away, and the placeholder is written in angle
        # brackets so it reads as a slot rather than a value." The blocked
        # arm's symmetric obligation is pinned above; this arm's was not, so a
        # reason reading "waiting on a sub-task to merge" passed.
        # POSITIVE CONTROLS, both measured against a throwaway stub: a
        # next_command_for whose awaiting arm returns the fixed reason "waiting
        # on a sub-task to merge" reddens the first assertion and the second;
        # a stub that names the sub-task but drops branch_for(...) from the
        # reason reddens only the second. Nothing else in the file moves for
        # either, which is what made this a hole.
        nc = self._command_for("awaiting-merge")
        waiting = list(self.moves["awaiting-merge"].get("awaiting", []))
        self.assertTrue(waiting, "fixture sanity: the awaiting-merge move must name a sub-task")
        for tid in waiting:
            self.assertIn(
                tid, nc["reason"],
                "the reason must name the awaiting sub-task %r -- an operator holding a "
                "generic 'a sub-task is out for merge' cannot tell which pull request number "
                "to paste into the command's slot. The reason read %r" % (tid, nc["reason"])
            )
            self.assertIn(
                branch_for("c-slug", tid), nc["reason"],
                "and it must name that sub-task's branch %r, which is what makes the pull "
                "request number one command away rather than a search. The reason read %r"
                % (branch_for("c-slug", tid), nc["reason"])
            )
        self.assertIn(
            "<", nc["commands"][0],
            "the pull request number is a SLOT, not a value: the mitigation writes it in angle "
            "brackets precisely so an operator cannot paste a placeholder and have it look like "
            "a number. The command read %r" % (nc["commands"][0],)
        )

    def test_escalate_nothing_planned_and_contract_defect_all_give_the_design_line(self):
        # Open Question one, answered: contract-defect gets the SAME design
        # line as escalate and nothing-planned, because the remedy for all
        # three is amending the contract.
        # POSITIVE CONTROL (fixture-owned): substitute "complete" into this
        # tuple and the /design-first assertion turns red for that member.
        for scenario in ("escalate", "nothing-planned", "contract-defect"):
            with self.subTest(scenario=scenario):
                nc = self._command_for(scenario)
                self.assertTrue(
                    nc["commands"],
                    "%r has a real next step and must never carry an empty command list -- "
                    "blocked is the only move that does" % scenario
                )
                self.assertTrue(
                    any("/design-first" in c for c in nc["commands"]),
                    "the remedy for %r is amending the contract, so its next command is the "
                    "design line. Read %r" % (scenario, nc["commands"])
                )

    def test_complete_gives_the_verification_line(self):
        # POSITIVE CONTROL (fixture-owned): ask for self.moves["escalate"]
        # instead and the command names /design-first, turning this red.
        nc = self._command_for("complete")
        self.assertTrue(nc["commands"], "a complete contract has a next step: verification")
        self.assertTrue(
            any("/verify-before-done" in c for c in nc["commands"]),
            "a contract whose every sub-task has a completion record is handed to verification. "
            "Read %r" % (nc["commands"],)
        )

    def test_blocked_gives_an_empty_command_list_and_a_non_empty_reason(self):
        # I-5 -- the one arm whose commands are empty, and the reason is what
        # makes that empty list meaningful rather than missing.
        # POSITIVE CONTROL (fixture-owned): ask for self.moves["dispatch"]
        # instead and commands is two lines long, turning the emptiness
        # assertion red.
        nc = self._command_for("blocked")
        self.assertEqual(
            nc["commands"], [],
            "nothing is runnable while every sub-task is held by a dependency that has not "
            "landed; inventing a command here would send an operator to do work that cannot "
            "start"
        )
        self.assertTrue(
            nc["reason"].strip(),
            "I-5: an empty command list is valid and meaningful only because it always travels "
            "with a non-empty reason -- an empty list with no reason is indistinguishable from "
            "a missing field"
        )
        blocked_ids = list(self.moves["blocked"].get("blocked", {}))
        self.assertTrue(blocked_ids, "fixture sanity: the blocked move must name blocked sub-tasks")
        self.assertTrue(
            any(tid in nc["reason"] for tid in blocked_ids),
            "the blocked reason must name what holds the sub-tasks (brief acceptance criterion "
            "four: 'blocked gives no command, plus what holds each sub-task'). Blocked ids were "
            "%r and the reason read %r" % (blocked_ids, nc["reason"])
        )

    def test_every_member_of_advance_actions_has_an_arm_and_a_real_scenario(self):
        # The totality test the New Mechanisms section names as the extension
        # seam's guard: "a new move added to advance adds one member to
        # ADVANCE_ACTIONS and one arm to the mapping, in the same change. The
        # totality test goes red if only one of the two is done."
        # POSITIVE CONTROL (fixture-owned): delete the "complete" entry from
        # _seven_real_moves()'s returned mapping and the first assertion names
        # it as a member with no scenario -- red.
        actions = _fn("ADVANCE_ACTIONS")
        self.assertIsNotNone(actions, "ADVANCE_ACTIONS must exist for the totality test to run")
        for action in actions:
            with self.subTest(action=action):
                self.assertIn(
                    action, self.moves,
                    "ADVANCE_ACTIONS names %r but no scenario in this suite drives advance() "
                    "into it -- a member nobody can reach is untested by construction" % action
                )
                nc = self.next_command_for(self.moves[action], "c-slug")
                self.assertIsInstance(
                    nc.get("commands"), list,
                    "next_command_for must return a commands list for %r -- a move with no arm "
                    "ships with no printed next step, which is the third Failure Mode" % action
                )
                self.assertTrue(
                    str(nc.get("reason", "")).strip(),
                    "every arm carries a reason, including the ones that carry commands"
                )
                if action != "blocked":
                    self.assertTrue(
                        nc["commands"],
                        "blocked is the only move that carries an empty command list (Open "
                        "Question one, answered); %r must carry at least one runnable line"
                        % action
                    )

    def test_an_unrecognised_action_fails_closed(self):
        # Extension Point 7: "plus a fail-closed fallback for an unrecognised
        # action that returns empty commands and a reason naming the
        # disagreement."
        # POSITIVE CONTROL (fixture-owned): pass {"action": "dispatch"} here
        # instead of the unrecognised action and the empty-commands assertion
        # turns red.
        nc = self.next_command_for({"action": "no-such-move-exists"}, "c-slug")
        self.assertEqual(
            nc.get("commands"), [],
            "an action outside the closed set is a disagreement between advance() and this "
            "mapping; guessing a command from it would be the same overclaim the loop exists "
            "to avoid"
        )
        self.assertTrue(
            str(nc.get("reason", "")).strip(),
            "the fallback's reason must name the disagreement rather than leaving an operator "
            "with an empty field and no explanation"
        )


# --------------------------------------------------------------------------
# (f2) next_command's complete arm, driven end-to-end through main(): the
# approved concept contract (.claude/concepts/2026-09-22-loop-next-step-
# survives-clear.md, Extension Point 7 and criterion (f)) states that the
# complete move gives the verification line, /verify-before-done, whatever
# the mergeable sub-task count is (``report["sub_tasks"]``, the mergeable
# subset classify_handoff resolved). No children-still-open gate exists yet
# -- not in /flow, not anywhere else in this script -- so nothing here
# should claim one does or route a multi-sub-task completion around
# /verify-before-done to reach it.
#
# Both cases go through main() rather than calling next_command_for
# directly: the older TestNextCommandFor.test_complete_gives_the_
# verification_line test calls next_command_for with a bare move mapping
# and so never exercises main(). These tests drive main() end to end and
# pin the exact output.
# --------------------------------------------------------------------------
CONTRACT_CLI_TWO_MERGEABLE_INDEPENDENT_TASKS = """
## Implementation Handoff

### 1. Backend (`acme-dev`)

**Depends on:** none

**Files to touch:**
- src/Foo.cs

### 2. Frontend (`acme-dev`)

**Depends on:** none

**Files to touch:**
- src/Bar.cs
"""


class TestNextCommandCompleteIsTheVerificationLineWhateverTheSubTaskCount(unittest.TestCase):

    def _report_for(self, contract_text, records):
        raw, _, _ = _drive_main_with_flags(contract_text, ["--status", "--json"], records=records)
        return json.loads(raw)

    def test_two_or_more_mergeable_subtasks_complete_still_gives_verify_before_done(self):
        report = self._report_for(
            CONTRACT_CLI_TWO_MERGEABLE_INDEPENDENT_TASKS,
            records={
                "t1-backend": {"status": "completed", "verified": "github", "pull_request": "u1"},
                "t2-frontend": {"status": "completed", "verified": "github", "pull_request": "u2"},
            },
        )
        self.assertEqual(
            len(report["sub_tasks"]), 2,
            "fixture sanity: this contract must declare two mergeable sub-tasks -- the whole "
            "point of this case is proving the ending holds even once that count reaches two "
            "or more"
        )
        self.assertTrue(
            report["complete"],
            "fixture sanity: both sub-tasks carry a github-verified completion record, so "
            "advance() must report the contract complete -- otherwise this case never reaches "
            "the complete arm at all"
        )
        nc = report["next_command"]
        commands = nc["commands"]
        self.assertEqual(
            commands, ["/verify-before-done"],
            "criterion (f): the complete move gives the verification line, "
            "/verify-before-done, whatever the mergeable sub-task count is -- and no command "
            "here may name /flow, since no children-still-open gate exists to hand a "
            "two-or-more-mergeable completion off to it. Read %r"
            % (commands,)
        )

    def test_positive_control_exactly_one_mergeable_subtask_complete_keeps_verify_before_done(self):
        # Probably green today: a single-sub-task contract is exactly the
        # shape TestNextCommandFor.test_complete_gives_the_verification_line
        # already covers via a bare move mapping -- criterion (f): the
        # complete move gives /verify-before-done whatever the mergeable
        # sub-task count is.
        report = self._report_for(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK,
            records={"t1-backend": {"status": "completed", "verified": "github", "pull_request": "u"}},
        )
        self.assertEqual(
            len(report["sub_tasks"]), 1,
            "fixture sanity: this contract must declare exactly one mergeable sub-task"
        )
        self.assertTrue(
            report["complete"],
            "fixture sanity: the sole sub-task carries a github-verified completion record"
        )
        nc = report["next_command"]
        self.assertEqual(
            nc["commands"], ["/verify-before-done"],
            "a contract with exactly one mergeable sub-task keeps today's ending -- "
            "criterion (f): the complete move gives /verify-before-done whatever the "
            "mergeable sub-task count is. Read %r"
            % (nc["commands"],)
        )


# --------------------------------------------------------------------------
# (g) The human-readable output prints the next command as its FINAL line.
#
# Extension Point 9: "prints the next command as its FINAL line, after the
# dispatch listing".
# --------------------------------------------------------------------------
class TestHumanReadableOutputEndsWithTheNextCommand(unittest.TestCase):

    def test_the_next_command_is_the_last_line_printed_after_the_dispatch_listing(self):
        # POSITIVE CONTROL (fixture-owned): pass ["--status", "--json"]
        # instead, and the output is a JSON document whose last line is "}" --
        # the startswith assertion turns red, which proves the assertion reads
        # the real final line rather than searching the whole output.
        text, _, _ = _drive_main_with_flags(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, ["--status"])
        lines = [ln for ln in text.splitlines() if ln.strip()]
        self.assertTrue(lines, "fixture sanity: the human-readable report must print something")
        dispatch_lines = [i for i, ln in enumerate(lines) if "dispatch t1-backend" in ln]
        self.assertTrue(
            dispatch_lines,
            "fixture sanity: this contract's one sub-task is ready, so the report must list a "
            "dispatch line"
        )
        self.assertTrue(
            lines[-1].strip().startswith("next command:"),
            "the next command must be the FINAL line of the human-readable report -- a skill "
            "that renders an ending of its own is the second implementation of a rule the "
            "script owns. The last line read %r" % lines[-1]
        )
        self.assertGreater(
            len(lines) - 1, dispatch_lines[-1],
            "the next command comes AFTER the dispatch listing, not before it"
        )
        self.assertIn(
            "/clear", lines[-1],
            "this contract's move is dispatch, so the printed line must carry the clear step -- "
            "the printed reminder is the only thing that makes isolation not depend on the "
            "operator remembering"
        )
        # EVERY command, not just the first. POSITIVE CONTROL, measured against
        # a throwaway stub main() that prints commands[0] alone: the two
        # assertions below go red and nothing else in the file moves, because
        # the assertion above is satisfied by the clear line on its own. A
        # printed step that stops after the clear leaves the operator in a
        # cleared session with nothing to run, which is worse than no reminder.
        self.assertIn(
            "/advance", lines[-1],
            "the printed line must carry BOTH halves of the dispatch step. Extension Point 9 "
            "prints the next command as one line joining every command; printing only the "
            "first strands the operator in a freshly cleared session with no line to run. The "
            "last line read %r" % lines[-1]
        )
        self.assertLess(
            lines[-1].index("/clear"), lines[-1].index("/advance"),
            "and they must be printed in the order the Next Command lists them -- advancing "
            "before clearing inherits the previous sub-task's transcript. The last line read %r"
            % lines[-1]
        )


#: name -> (contract literal, the move main() reaches with it, a fragment the
#: stamped command list must carry). Two DIFFERENT moves on purpose: dispatch
#: is the one move whose command the human-readable case above already reads,
#: so a report stamping next_command for dispatch alone passes a one-move case.
_NEXT_COMMAND_REPORT_CASES = (
    ("the dispatch move", CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, "dispatch", "/clear"),
    ("the contract-defect move", CONTRACT_CLI_ALL_MALFORMED, "contract-defect", "/design-first"),
)


class TestTheJsonReportStampsTheNextCommand(unittest.TestCase):
    """Extension Point 8: main stamps ``report["next_command"]``.

    The case above reads the PRINTED line. The advance skill reads the JSON --
    Integration Surfaces names the script's JSON report as the mechanism
    carrying Next Command to both skills, and Extension Point 13 has the skill
    print the script's next command verbatim from a read-only call. Until this
    case, no assertion in this file touched the field, so two implementations
    passed everything: one computing the line inside the human-readable branch
    and never stamping it, and one stamping it for the dispatch move alone.
    """

    def test_the_report_carries_a_next_command_for_each_move_it_reaches(self):
        # POSITIVE CONTROL, measured against a throwaway stub main() that
        # stamps report["next_command"] only when the move is dispatch: the
        # contract-defect row goes red naming the absent key while the dispatch
        # row stays green. That stub also reddens
        # TestHumanReadableOutputRendersStoredSummaries, whose run raises
        # KeyError: 'next_command' reaching for the same field -- noted because
        # it was watched, not predicted. Against a second stub that composes
        # the line inside the human-readable branch and stamps no field at all,
        # this case is the ONLY one that goes red in the whole file: the
        # printed-line case above passes it untouched, which is the gap.
        for name, contract_text, expected_action, fragment in _NEXT_COMMAND_REPORT_CASES:
            with self.subTest(case=name):
                text, _, _ = _drive_main_with_flags(contract_text, ["--status", "--json"])
                report = json.loads(text)
                self.assertEqual(
                    report.get("next_move", {}).get("action"), expected_action,
                    "fixture sanity: %s must drive main() into the %r move" % (name, expected_action)
                )
                self.assertIn(
                    "next_command", report,
                    "the JSON report must carry next_command for the %r move -- a line composed "
                    "inside the human-readable branch reaches no skill at all, and a skill that "
                    "renders its own ending is the second implementation this contract removes"
                    % expected_action
                )
                nc = report["next_command"]
                self.assertIsInstance(
                    nc.get("commands"), list,
                    "a Next Command carries an ordered commands list (Data Shapes, Next "
                    "Command); for %r it read %r" % (expected_action, nc)
                )
                self.assertTrue(
                    str(nc.get("reason", "")).strip(),
                    "I-5: a Next Command always carries a non-empty reason, including when the "
                    "command list is empty -- the reason is what makes an empty list meaningful "
                    "rather than missing"
                )
                self.assertTrue(
                    any(fragment in c for c in nc["commands"]),
                    "the %r move's stamped command must carry %r, so the field is computed from "
                    "the move rather than filled with one move's answer. It read %r"
                    % (expected_action, fragment, nc["commands"])
                )


#: name -> (the stored completion record, the fragment the rendered line must
#: carry). A seeded entry has no "pr" key and a not-recorded entry has no
#: "files" key, and today's renderer reads both unguarded.
_HAND_RESOLVED_RENDER_CASES = (
    ("a stored summary that found a file", _RECORD_WITH_SUMMARY, "src/Hand.cs"),
    ("a record written before this change", _RECORD_WITHOUT_SUMMARY, "not-recorded"),
)


class TestHumanReadableOutputRendersStoredSummaries(unittest.TestCase):
    """The human-readable branch, driven with records already on disk.

    ``pr_merged.py`` prints ``hand-resolved in #{h['pr']}: {h['files']}`` with
    no guard on either key, and the only case in this file that drives that
    branch supplies no records, so the loop body never executes. Once
    Extension Point 5 seeds the list from stored records, that line raises
    KeyError on every run that has any -- and the suite as it stood would stay
    silent, because the branch it exercises is the empty one.
    """

    def test_a_read_only_run_renders_each_stored_reading_without_raising(self):
        # POSITIVE CONTROL, measured against a throwaway stub main() that seeds
        # the report and leaves the renderer exactly as it is today: both rows
        # go red, and the message reads "it raised KeyError: 'pr'" -- the
        # failure this case exists to make visible, on the seeded entry that
        # has no pull-request number. Against a stub that seeds and guards both
        # keys, both rows pass.
        for name, record, fragment in _HAND_RESOLVED_RENDER_CASES:
            with self.subTest(case=name):
                try:
                    text, _, _ = _drive_main_with_flags(
                        CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, ["--status"],
                        records={"t1-backend": record})
                except Exception as exc:  # noqa: BLE001 -- the raise IS the finding
                    self.fail(
                        "the human-readable report must render %s and finish; it raised %s: %s. "
                        "An operator meets this as a stack trace instead of a report, on every "
                        "run that has stored records" % (name, type(exc).__name__, exc))
                self.assertIn(
                    fragment, text,
                    "the human-readable report must NAME the reading for %s -- %r was nowhere "
                    "in it, and a reading nobody prints is indistinguishable from a clean "
                    "merge. The report read:\n%s" % (name, fragment, text)
                )
                naming = [ln for ln in text.splitlines() if fragment in ln]
                self.assertTrue(
                    any("t1-backend" in ln for ln in naming),
                    "the line carrying the reading must name the sub-task it belongs to: a "
                    "seeded entry has no pull-request number to identify it by, and an "
                    "unattributed reading tells an operator nothing about where to look. The "
                    "matching lines were %r" % (naming,)
                )


# --------------------------------------------------------------------------
# (h) --resume is a read-only report.
#
# Measured defect (Data Shapes, Commands): --resume is declared at
# pr_merged.py:1074 and its value is never read in main(), so a run carrying
# it falls through to the default report path -- which WRITES the state store,
# because every non-writing branch is gated on --dry-run and --status only.
# --------------------------------------------------------------------------
class TestResumeIsAReadOnlyReport(unittest.TestCase):

    def test_resume_writes_neither_the_state_store_nor_any_record(self):
        # WHICH MOCK THE LIVE CONTROL COVERS -- corrected, because the earlier
        # version of this comment said "this case is its own live positive
        # control" without naming a mock, and that is true of one of the two
        # and false of the other.
        #
        # write_state: a genuine live control. Its current output reads
        # "write_state was called 1 time(s)" -- the mock is watching main()
        # perform a real write today, on the very flag the contract says must
        # write nothing, so the count in the message IS the observation. The
        # paired case test_positive_control_a_default_run_does_write_the_state
        # _store keeps that true after the implementation lands.
        #
        # write_record: NOT a live control here, and the assertion below is
        # kept only as the shape statement it really is. _drive_main_with_flags
        # supplies no --pr, so main()'s pull-request loop never runs and
        # write_record is unreachable on every flag set this fixture can drive.
        # Measured call counts, all three flag sets, against the throwaway
        # stub: --resume --json -> write_state 0, write_record 0; --status
        # --json -> 0 and 0; --json -> write_state 1, write_record 0. The
        # write_record row never moves, so assertFalse on it cannot fail here.
        # The REACHABLE witness is
        # TestResumeIsReadOnlyAtEveryWritingBranch.test_resume_writes_no
        # _completion_record_for_a_merged_pull_request, which drives the same
        # flag through the --pr fixture and has its own live control beside it.
        _text, write_state_mock, write_record_mock = _drive_main_with_flags(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, ["--resume", "--json"])
        self.assertFalse(
            write_state_mock.called,
            "--resume must join --status in every branch currently gated on 'not args.dry_run "
            "and not args.status' (Extension Point 10). Reporting the stored position must "
            "never move it -- write_state was called %d time(s)"
            % write_state_mock.call_count
        )
        self.assertFalse(
            write_record_mock.called,
            "a --resume run given no --pr has no pull request to record, so it must reach "
            "write_record zero times. This path cannot distinguish a guarded writer from an "
            "unreachable one; the case that can is named in the comment above"
        )

    def test_the_resume_report_leads_with_the_stored_position(self):
        # Open Question four, answered: "--resume becomes a read-only report:
        # it writes neither the state store nor any completion record, and its
        # report leads with THE STORED POSITION and what that position is
        # waiting for." Until this case nothing asserted the position half, so
        # an implementation reaching read-only by dropping report["state"]
        # passed -- and dropping it is the shortest way to make a writer stop
        # mattering.
        # What the name calls "leads with" is pinned here as PRESENCE, which is
        # its testable half: the report is a JSON object, and key order in one
        # is not a contract, so the two assertions below ask that
        # report["state"] exists as a dict and names this contract's sub-task
        # and nothing about where it sits.
        # POSITIVE CONTROL, measured against a throwaway stub main() that
        # stamps report["state"] = None whenever args.resume is set: both
        # assertions below go red and nothing else in the file moves.
        text, _, _ = _drive_main_with_flags(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, ["--resume", "--json"])
        report = json.loads(text)
        self.assertIsInstance(
            report.get("state"), dict,
            "a --resume report must still CARRY the stored position -- reaching read-only by "
            "omitting the position answers the flag's own help text with silence. It read %r"
            % (report.get("state"),)
        )
        self.assertIn(
            "t1-backend", report["state"].get("sub_tasks", {}),
            "and the position must name this contract's sub-task, which is the thing a cleared "
            "session has no other way to learn. The position read %r" % (report["state"],)
        )

    def test_resume_still_produces_a_report(self):
        # The other half of Extension Point 10: --resume becomes a read-only
        # REPORT, not an error and not a silent no-op.
        # POSITIVE CONTROL, measured: run the same flags against a contract
        # slug that resolves to nothing --
        #   py -3 -B .claude/scripts/pr_merged.py --contract zz-no-such-contract-probe
        #     --resume --json
        # -- and main() prints {"error": "contract-not-found", "contract":
        # "zz-no-such-contract-probe"} with exit code 2, so the equality
        # against "acme-red-fixture" and the assertIn("next_move") both turn
        # red.
        text, _, _ = _drive_main_with_flags(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, ["--resume", "--json"])
        report = json.loads(text)
        self.assertEqual(
            report.get("contract"), "acme-red-fixture",
            "a --resume run must still report the contract it was asked about"
        )
        self.assertIn(
            "next_move", report,
            "a --resume run reports the stored position and what it waits for, which is the "
            "move -- the flag's own help text says exactly that"
        )

    def test_positive_control_a_default_run_does_write_the_state_store(self):
        # POSITIVE CONTROL for the read-only case above. Must stay green
        # throughout: it proves this fixture's write_state mock observes a
        # real write, so assertFalse(write_state_mock.called) is a measurement
        # and not a mock that was never wired. Mutation that turns it red: add
        # "--status" to this flag list.
        _text, write_state_mock, _ = _drive_main_with_flags(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, ["--json"])
        self.assertTrue(
            write_state_mock.called,
            "a plain run with neither --dry-run, --status nor --resume writes the state store "
            "-- if this ever goes red the read-only assertions above are measuring nothing"
        )


# --------------------------------------------------------------------------
# (j) The Sub-Task Cycle -- decided by what the block DECLARES, never by who
# is assigned.
#
# Extension Point 12, four arms, first match wins. I-6: the list is always
# exactly ONE stage. I-7: no-declared-phase always travels with exactly one
# unphased stage, never with a red stage the contract did not ask for. There
# is no RED_STAGE_AGENT constant and no case below assumes one: every stage's
# agent is the block's own.
# --------------------------------------------------------------------------
BLOCK_DECLARING_PHASE_RED = """
**Depends on:** none

**Files to touch:**
- .claude/scripts/tests/test_thing.py

**Pre-written TASK block:**
```
TASK: Write the failing tests for the thing.
CONTEXT: concept contract at .claude/concepts/c-slug.md
PRIOR_FINDINGS:
  contract_path: .claude/concepts/c-slug.md
  contract_status: approved
  phase: RED
```
"""

BLOCK_DECLARING_PHASE_GREEN = """
**Depends on:** 1

**Files to touch:**
- .claude/scripts/thing.py

**Pre-written TASK block:**
```
TASK: Make the failing tests pass.
CONTEXT: concept contract at .claude/concepts/c-slug.md
PRIOR_FINDINGS:
  contract_path: .claude/concepts/c-slug.md
  contract_status: approved
  phase: GREEN
```
"""

BLOCK_DECLARING_NO_PHASE = """
**Depends on:** none

**Files to touch:**
- src/Foo.cs

**Pre-written TASK block:**
```
TASK: Do the thing.
CONTEXT: concept contract at .claude/concepts/c-slug.md
PRIOR_FINDINGS:
  contract_path: .claude/concepts/c-slug.md
  contract_status: approved
```
"""

BLOCK_WITH_NO_TASK_BLOCK_AT_ALL = """
**Depends on:** none

**Files to touch:**
- src/Foo.cs
"""

#: Extension Point 11 defines declared_phase as reading the phase "out of the
#: block's own TASK block", so the shape that can fool a careless reader is a
#: `phase:` line at column zero OUTSIDE any fenced TASK block. This repository
#: already writes that shape: the briefs under .claude/work-items/ carry a
#: column-zero `phase:` line. Those files never reach build_dispatch -- it is
#: handed a contract handoff block body, and a brief travels through main() as
#: a PATH in the state entry, never as content -- so the claim here is about
#: the shape alone, which handoff prose is equally free to take.
#: Every other fixture in this file puts its phase line inside a fenced TASK
#: block: grep '^phase:' over this file finds exactly the one below. So none
#: of them can tell a reader that honours the TASK block from one that scans
#: the whole body. Measured against a throwaway stub build_dispatch, swapping
#: the TASK-block-scoped search for the same regular expression over
#: block_body turns exactly two subtests red and nothing green -- this
#: fixture's _CYCLE_CASES row and
#: test_a_phase_line_in_prose_outside_the_task_block_is_not_a_declaration.
#: This block declares NO phase; the phase-shaped line below it is a sentence
#: about the sub-task that came before, and reading it as a declaration hands
#: this block a red stage the contract never asked for.
BLOCK_WITH_A_PHASE_LINE_IN_PROSE_ONLY = """
**Depends on:** none

**Files to touch:**
- src/Foo.cs

The brief this block replaces recorded its own metadata in wrapped prose, and one of the lines it
wrapped onto a column-zero line of its own was
phase: RED
which belonged to the sub-task that came before this one and never to this block.

**Pre-written TASK block:**
```
TASK: Do the thing.
CONTEXT: concept contract at .claude/concepts/c-slug.md
PRIOR_FINDINGS:
  contract_path: .claude/concepts/c-slug.md
  contract_status: approved
```
"""

#: A review gate that DECLARES a review artefact path -- verdict-bearing.
_ARTEFACT_DECLARING_TASK = SubTask(
    id="t4-script-review", ordinal=4, name="Script review", agent="acme-reviewer",
    depends_on=[2], files=[".claude/reviews/c-slug/t4-script-review-acme-reviewer.md"],
    agent_role="review-gate")

#: The case that proves the rule (Extension Point 12, sub-task 6 of this very
#: contract): its agent IS a review gate, but it declares ordinary files and
#: no artefact, so it correctly gets NO review stage.
_REVIEW_AGENT_ORDINARY_FILES_TASK = SubTask(
    id="t6-code-review", ordinal=6, name="Code review", agent="fullstack-code-reviewer",
    depends_on=[2], files=["src/Foo.cs", "src/Bar.cs"], agent_role="review-gate")

_RED_PHASE_TASK = SubTask(
    id="t1-failing-tests", ordinal=1, name="Failing tests", agent="senior-test-engineer",
    depends_on=[], files=[".claude/scripts/tests/test_thing.py"], agent_role="implementer")

_GREEN_PHASE_TASK = SubTask(
    id="t2-script", ordinal=2, name="Script", agent="python-ai-developer",
    depends_on=[1], files=[".claude/scripts/thing.py"], agent_role="implementer")

#: The two rows that de-confound the red arm from the agent's NAME.
#: _RED_PHASE_TASK above is owned by senior-test-engineer, so on its own it
#: cannot tell an arm reading the DECLARED phase from an arm reading "is this
#: a test engineer" -- the RED_STAGE_AGENT shape Non-Goals forbids. Measured:
#: that mutation survived every case in this class. These cross the two facts
#: over, the way _REVIEW_AGENT_ORDINARY_FILES_TASK crosses the review arm
#: against agent_role.
_RED_PHASE_TASK_OWNED_BY_A_SCRIPT_AUTHOR = SubTask(
    id="t7-red-by-a-script-author", ordinal=7, name="Failing tests",
    agent="python-ai-developer", depends_on=[],
    files=[".claude/scripts/tests/test_other.py"], agent_role="implementer")

_GREEN_PHASE_TASK_OWNED_BY_A_TEST_ENGINEER = SubTask(
    id="t8-green-by-a-test-engineer", ordinal=8, name="Script",
    agent="senior-test-engineer", depends_on=[1],
    files=[".claude/scripts/other.py"], agent_role="implementer")

#: name -> (sub-task, block body, the one stage expected, the expected basis)
_CYCLE_CASES = (
    ("a declared review artefact",
     _ARTEFACT_DECLARING_TASK, BLOCK_DECLARING_NO_PHASE, "review", "verdict-bearing"),
    ("a declared review artefact alongside a declared phase",
     _ARTEFACT_DECLARING_TASK, BLOCK_DECLARING_PHASE_RED, "review", "verdict-bearing"),
    ("a review-gate agent whose files are ordinary",
     _REVIEW_AGENT_ORDINARY_FILES_TASK, BLOCK_DECLARING_NO_PHASE, "unphased", "no-declared-phase"),
    ("a task block declaring phase RED",
     _RED_PHASE_TASK, BLOCK_DECLARING_PHASE_RED, "red", "declared-phase"),
    ("a task block declaring phase GREEN",
     _GREEN_PHASE_TASK, BLOCK_DECLARING_PHASE_GREEN, "green", "declared-phase"),
    ("a block declaring no phase",
     _GREEN_PHASE_TASK, BLOCK_DECLARING_NO_PHASE, "unphased", "no-declared-phase"),
    ("a block with no task block at all",
     _GREEN_PHASE_TASK, BLOCK_WITH_NO_TASK_BLOCK_AT_ALL, "unphased", "no-declared-phase"),
    ("a declared RED phase whose agent is not a test engineer",
     _RED_PHASE_TASK_OWNED_BY_A_SCRIPT_AUTHOR, BLOCK_DECLARING_PHASE_RED, "red", "declared-phase"),
    ("a test engineer owning a declared GREEN phase",
     _GREEN_PHASE_TASK_OWNED_BY_A_TEST_ENGINEER, BLOCK_DECLARING_PHASE_GREEN,
     "green", "declared-phase"),
    ("a phase line in prose outside the task block",
     _GREEN_PHASE_TASK, BLOCK_WITH_A_PHASE_LINE_IN_PROSE_ONLY, "unphased", "no-declared-phase"),
)


class TestDispatchPacketCarriesTheSubTaskCycle(unittest.TestCase):

    def _packet(self, case_name):
        for name, task, body, _stage, _basis in _CYCLE_CASES:
            if name == case_name:
                d = build_dispatch(task, "c-slug", ".claude/concepts/c-slug.md", body)
                self.assertIn(
                    "cycle", d,
                    "build_dispatch must carry a cycle key -- Extension Point 12. Today the "
                    "packet names branch, agent, files, contract and task block, and nothing "
                    "about the stages the sub-task runs through"
                )
                self.assertIn(
                    "cycle_basis", d,
                    "build_dispatch must carry a cycle_basis key beside cycle, naming WHICH "
                    "declaration produced the stage, so a reader can tell a stage the contract "
                    "asked for from one the loop fell back to"
                )
                return d, task
        raise AssertionError("no cycle case named %r" % case_name)

    def test_a_declared_review_artefact_yields_one_review_stage(self):
        # POSITIVE CONTROL (fixture-owned): change
        # _ARTEFACT_DECLARING_TASK.files to ["src/Foo.cs"] and the arm can no
        # longer fire, so stage reads "unphased" and basis "no-declared-phase"
        # -- both assertions turn red. That is the same mutation the
        # ordinary-files case below makes permanent.
        d, task = self._packet("a declared review artefact")
        self.assertEqual(
            len(d["cycle"]), 1,
            "I-6: the cycle is always exactly one stage; the loop never composes two"
        )
        self.assertEqual(
            d["cycle"][0]["stage"], "review",
            "a sub-task declaring a path under .claude/reviews/ is verdict-bearing, and that is "
            "read from the DECLARED PATH -- the rule stated at MECHANISMS.md:149, "
            "VOCABULARY.md:40 and project-profile.md:60, and already applied by main() when it "
            "picks the verdict file"
        )
        self.assertEqual(
            d["cycle_basis"], "verdict-bearing",
            "the basis names which declaration produced the stage"
        )
        self.assertEqual(
            d["cycle"][0]["agent"], task.agent,
            "every stage carries the block's OWN agent; the script never chooses one"
        )
        self.assertEqual(
            d["cycle"][0]["isolation"], "fresh-subagent",
            "isolation is the constant fresh-subagent -- that is the capability this cycle "
            "exists to make explicit instead of leaving it to an operator's memory"
        )

    def test_the_review_arm_wins_over_a_declared_phase(self):
        # The ordering test MECHANISMS.md:115 requires of a first-match-wins
        # procedure: the same block declares BOTH a review artefact and
        # phase: RED, and review must win.
        # POSITIVE CONTROL (fixture-owned): swap this case's sub-task for
        # _RED_PHASE_TASK -- same block body, ordinary files -- and the stage
        # reads "red" with basis "declared-phase", turning both assertions red.
        d, _task = self._packet("a declared review artefact alongside a declared phase")
        self.assertEqual(
            d["cycle"][0]["stage"], "review",
            "the review arm is first and first match wins; a block declaring both must not be "
            "read as a red stage"
        )
        self.assertEqual(d["cycle_basis"], "verdict-bearing",
                         "the basis must name the declaration that actually decided the stage")

    def test_a_review_gate_agent_whose_files_are_ordinary_gets_no_review_stage(self):
        # The case that proves the rule. Extension Point 12 names it: this
        # contract's own sub-task 6 is owned by fullstack-code-reviewer, writes
        # five ordinary files and no artefact, and correctly gets no review
        # stage. agent_role is deliberately set to "review-gate" on this
        # fixture, so an implementation that keys on agent_role instead of on
        # the declared path fails here and only here.
        # POSITIVE CONTROL, measured against a throwaway stub build_dispatch
        # that keys the review arm on `task.agent_role == "review-gate"`
        # instead of on the declared path: this case and the
        # no-declared-phase row of test_no_case_invents_a_red_stage... are the
        # only two that go red, which is what makes it the case that proves
        # the rule.
        d, task = self._packet("a review-gate agent whose files are ordinary")
        self.assertEqual(
            task.agent_role, "review-gate",
            "fixture sanity: this sub-task's agent IS resolved as a review gate, which is the "
            "whole point of the case"
        )
        self.assertNotEqual(
            d["cycle"][0]["stage"], "review",
            "the cycle is keyed on what the block DECLARES and never on agent_role -- a review "
            "gate that writes ordinary files has no verdict to bear"
        )
        self.assertEqual(
            d["cycle"][0]["stage"], "unphased",
            "no artefact and no declared phase leaves exactly one unphased stage"
        )
        self.assertEqual(d["cycle_basis"], "no-declared-phase",
                         "the basis must say the phase was ABSENT, not inferred")

    def test_a_declared_red_phase_yields_one_red_stage(self):
        # POSITIVE CONTROL (fixture-owned): change this block's
        # "phase: RED" line to "phase: GREEN" and the stage reads "green",
        # turning the assertion red.
        d, task = self._packet("a task block declaring phase RED")
        self.assertEqual(len(d["cycle"]), 1, "I-6: exactly one stage")
        self.assertEqual(
            d["cycle"][0]["stage"], "red",
            "a task block declaring phase: RED is the contract SAYING which half of the "
            "test-first cycle this block is"
        )
        self.assertEqual(d["cycle_basis"], "declared-phase",
                         "the basis names the phase line as the declaration that decided it")
        self.assertEqual(
            d["cycle"][0]["agent"], task.agent,
            "the red stage carries the block's own agent -- there is no RED_STAGE_AGENT "
            "constant and the script never guesses who writes a failing test"
        )

    def test_the_stage_is_keyed_on_the_declared_phase_and_never_on_the_agents_name(self):
        # The de-confounding case, and the sibling of the ordinary-files case
        # above. _RED_PHASE_TASK is owned by senior-test-engineer, so the red
        # arm on its own is indistinguishable from an arm that asks "is this a
        # test engineer" -- measured: that mutation survived every other case
        # in this class. These two rows cross the two facts over: a RED
        # declaration owned by a script author, and a GREEN declaration owned
        # by a test engineer.
        # POSITIVE CONTROL, measured against a throwaway stub build_dispatch
        # whose red arm reads `task.agent == "senior-test-engineer"` instead of
        # declared_phase(...): this case goes red, and so do exactly the two
        # rows added with it in test_no_case_invents_a_red_stage_the_block_did
        # _not_declare. Nothing else in the file moves -- every row that
        # existed before those two passes the mutation, which is the confound.
        d, task = self._packet("a declared RED phase whose agent is not a test engineer")
        self.assertNotEqual(
            task.agent, "senior-test-engineer",
            "fixture sanity: this row exists precisely because its agent is not a test engineer"
        )
        self.assertEqual(
            d["cycle"][0]["stage"], "red",
            "a block declaring phase: RED yields a red stage whoever owns it -- the declaration "
            "decides the stage, and Non-Goals rules out the script ever reading a name to "
            "decide it"
        )
        mirror, mirror_task = self._packet("a test engineer owning a declared GREEN phase")
        self.assertEqual(
            mirror_task.agent, "senior-test-engineer",
            "fixture sanity: this row exists precisely because a test engineer owns it"
        )
        self.assertEqual(
            mirror["cycle"][0]["stage"], "green",
            "a block declaring phase: GREEN yields a green stage even when a test engineer owns "
            "it: the agent who wrote the failing tests is often the obvious owner of the block "
            "that follows, and a loop reading the name would hand that block a second red stage"
        )

    def test_a_declared_green_phase_yields_one_green_stage(self):
        # POSITIVE CONTROL (fixture-owned): change this block's
        # "phase: GREEN" line to "phase: RED" and the stage reads "red".
        d, task = self._packet("a task block declaring phase GREEN")
        self.assertEqual(len(d["cycle"]), 1, "I-6: exactly one stage")
        self.assertEqual(d["cycle"][0]["stage"], "green",
                         "a task block declaring phase: GREEN yields one green stage")
        self.assertEqual(d["cycle_basis"], "declared-phase",
                         "the basis names the phase line as the declaration that decided it")
        self.assertEqual(d["cycle"][0]["agent"], task.agent,
                         "the green stage carries the block's own agent")

    def test_a_block_declaring_no_phase_yields_one_unphased_stage(self):
        # POSITIVE CONTROL (fixture-owned): add a "  phase: RED" line to
        # BLOCK_DECLARING_NO_PHASE's task block and both assertions turn red.
        d, _task = self._packet("a block declaring no phase")
        self.assertEqual(d["cycle"][0]["stage"], "unphased",
                         "a block that declares no phase gets ONE stage carrying its own agent")
        self.assertEqual(
            d["cycle_basis"], "no-declared-phase",
            "I-7: the basis must make an absent declaration visible, so an operator can tell a "
            "fallback from a stage the contract asked for"
        )

    def test_a_block_with_no_task_block_at_all_yields_one_unphased_stage(self):
        # Extension Point 11: a block with no TASK block and a block that
        # declares no phase are the SAME answer on purpose -- in both cases
        # the contract did not say.
        # POSITIVE CONTROL (fixture-owned): swap this case's body for
        # BLOCK_DECLARING_PHASE_RED and the stage reads "red".
        d, _task = self._packet("a block with no task block at all")
        self.assertTrue(
            d["needs_authoring"],
            "fixture sanity: this block genuinely has no pre-written TASK block"
        )
        self.assertEqual(d["cycle"][0]["stage"], "unphased",
                         "no TASK block means the contract did not say, which is unphased")
        self.assertEqual(d["cycle_basis"], "no-declared-phase",
                         "the basis must name the absence rather than hiding it")

    def test_a_phase_line_in_prose_outside_the_task_block_is_not_a_declaration(self):
        # Extension Point 11 reads the phase out of the BLOCK'S OWN TASK BLOCK.
        # Every other fixture here puts the phase line only inside one, so none
        # of them can tell those two readers apart.
        # POSITIVE CONTROL, measured against a throwaway stub build_dispatch
        # that searches block_body with the same regular expression instead of
        # calling declared_phase(extract_task_block(...)): exactly two subtests
        # go red -- this case, and the 'a phase line in prose outside the task
        # block' row of test_no_case_invents_a_red_stage_the_block_did_not
        # _declare. Nothing else in the file moves, before or after this
        # fixture was added, which is what made this a hole: every other
        # fixture puts its phase line where it belongs.
        d, _task = self._packet("a phase line in prose outside the task block")
        self.assertIn(
            "\nphase: RED\n", BLOCK_WITH_A_PHASE_LINE_IN_PROSE_ONLY,
            "fixture sanity: the hazard is real only if the body genuinely carries a "
            "column-zero phase line outside the fenced TASK block"
        )
        self.assertNotIn(
            "phase: RED", extract_task_block(BLOCK_WITH_A_PHASE_LINE_IN_PROSE_ONLY) or "",
            "fixture sanity: and that line must be OUTSIDE what extract_task_block returns, or "
            "this case is measuring an ordinary declared-phase block"
        )
        self.assertEqual(
            d["cycle"][0]["stage"], "unphased",
            "prose is not a declaration. A block whose TASK block declares no phase is unphased "
            "however many phase-shaped sentences surround it, and promoting one of them hands "
            "this block a red stage the contract never asked for"
        )
        self.assertEqual(
            d["cycle_basis"], "no-declared-phase",
            "and the basis must say the phase was ABSENT from the TASK block, not read from "
            "somewhere else in the body"
        )

    def test_no_case_yields_two_stages(self):
        # I-6 across every arm at once. POSITIVE CONTROL, measured against a
        # throwaway stub build_dispatch that returns a red stage COMPOSED IN
        # FRONT of the stage it decided: all TEN rows of this case go red, and
        # 27 failing subtests across 11 methods in total, because a red stage
        # in front also makes cycle[0] read "red" everywhere. That is the
        # defect this case exists to catch -- a two-stage cycle collapses the
        # two authors the design keeps apart.
        # The count is stated per ROW and re-measured whenever _CYCLE_CASES
        # changes: the earlier "all seven rows" was correct when it was
        # written and went stale twice, once when two de-confounding rows were
        # added and once when the prose-phase row was. Read the tuple's length
        # before writing a number here.
        for name, task, body, _stage, _basis in _CYCLE_CASES:
            with self.subTest(case=name):
                d = build_dispatch(task, "c-slug", ".claude/concepts/c-slug.md", body)
                self.assertIn("cycle", d, "build_dispatch must carry a cycle key")
                self.assertEqual(
                    len(d["cycle"]), 1,
                    "I-6: %r must yield exactly one stage. Two stages would collapse the two "
                    "authors this design exists to keep apart, since a single dispatch would "
                    "carry both the failing test and the code that satisfies it" % name
                )

    def test_no_case_invents_a_red_stage_the_block_did_not_declare(self):
        # I-7, stated explicitly because a silent default is the defect the
        # unphased arm exists to avoid.
        # POSITIVE CONTROL, measured against a throwaway stub build_dispatch
        # that promotes every no-declared-phase stage to "red": exactly the
        # FOUR no-declared-phase rows of this case go red, plus the FOUR
        # single-case tests that pin the same rows -- the review-gate-with-
        # ordinary-files case, the no-phase case, the no-task-block case and
        # the phase-in-prose case. Eight failing subtests across five methods.
        # A stub that leaves them unphased passes. Re-measure both numbers
        # whenever a no-declared-phase row is added to _CYCLE_CASES; the
        # earlier "three rows plus two single-case tests" was true of an
        # earlier tuple and of an earlier set of single-case tests.
        for name, task, body, expected_stage, expected_basis in _CYCLE_CASES:
            with self.subTest(case=name):
                d = build_dispatch(task, "c-slug", ".claude/concepts/c-slug.md", body)
                self.assertIn("cycle", d, "build_dispatch must carry a cycle key")
                self.assertEqual(
                    d["cycle"][0]["stage"], expected_stage,
                    "%r must yield a %r stage" % (name, expected_stage)
                )
                self.assertEqual(
                    d["cycle_basis"], expected_basis,
                    "%r must be stamped with basis %r" % (name, expected_basis)
                )
                if expected_basis == "no-declared-phase":
                    self.assertNotEqual(
                        d["cycle"][0]["stage"], "red",
                        "I-7: no-declared-phase must never travel with a red stage -- %r "
                        "declared no phase, so the loop must not ask for a failing test the "
                        "contract never requested" % name
                    )

    def test_every_stage_names_the_blocks_own_agent(self):
        # There is no arm in which the script chooses an agent the contract
        # did not name, which is why RED_STAGE_AGENT is NOT added (Non-Goals).
        # POSITIVE CONTROL, measured against a throwaway stub build_dispatch
        # that names "senior-test-engineer" on every stage instead of the
        # block's own agent: EIGHT rows of this case go red -- every row whose
        # agent is not senior-test-engineer, which is eight of the ten in
        # _CYCLE_CASES. That is exactly the RED_STAGE_AGENT shape Non-Goals
        # forbids, and only this case and the two single-case agent assertions
        # catch it: ten failing subtests across three methods. The earlier
        # "six rows" counted a seven-row tuple and was stale before the
        # de-confounding rows landed beside it.
        for name, task, body, _stage, _basis in _CYCLE_CASES:
            with self.subTest(case=name):
                d = build_dispatch(task, "c-slug", ".claude/concepts/c-slug.md", body)
                self.assertIn("cycle", d, "build_dispatch must carry a cycle key")
                for stage in d["cycle"]:
                    self.assertEqual(
                        stage.get("agent"), task.agent,
                        "%r: every stage's agent is the block's own (%r), never a name the "
                        "script chose" % (name, task.agent)
                    )
                    self.assertEqual(
                        stage.get("isolation"), "fresh-subagent",
                        "%r: every stage runs in a fresh subagent -- that constant IS the "
                        "isolation the operator currently has to produce by remembering to "
                        "clear" % name
                    )


# --------------------------------------------------------------------------
# (k) declared_phase -- reads the phase line out of a block's own TASK block.
#
# Extension Point 11: returns RED, GREEN or None. None for a block that
# declares no phase AND for a block with no TASK block at all, and the two are
# the same answer on purpose: in both cases the contract did not say.
# --------------------------------------------------------------------------
class TestDeclaredPhase(unittest.TestCase):

    def _declared_phase(self):
        fn = _fn("declared_phase")
        self.assertIsNotNone(
            fn,
            "pr_merged.declared_phase must exist -- Extension Point 11 names it the pure "
            "function that reads the phase line out of a block's own TASK block"
        )
        return fn

    def test_a_task_block_declaring_red_reads_red(self):
        # POSITIVE CONTROL (fixture-owned): read the phase out of
        # BLOCK_DECLARING_PHASE_GREEN instead and this assertion turns red.
        declared_phase = self._declared_phase()
        self.assertEqual(
            declared_phase(extract_task_block(BLOCK_DECLARING_PHASE_RED)), "RED",
            "the phase line is the contract's own declaration of which half of the test-first "
            "cycle a block is, and it is read verbatim"
        )

    def test_a_task_block_declaring_green_reads_green(self):
        # POSITIVE CONTROL (fixture-owned): read the phase out of
        # BLOCK_DECLARING_PHASE_RED instead and this assertion turns red.
        declared_phase = self._declared_phase()
        self.assertEqual(
            declared_phase(extract_task_block(BLOCK_DECLARING_PHASE_GREEN)), "GREEN",
            "GREEN is read exactly as RED is; neither is inferred from the agent"
        )

    def test_a_task_block_with_no_phase_line_reads_none(self):
        # POSITIVE CONTROL (fixture-owned): add a "  phase: RED" line to
        # BLOCK_DECLARING_NO_PHASE's task block and this assertion turns red.
        declared_phase = self._declared_phase()
        self.assertIsNone(
            declared_phase(extract_task_block(BLOCK_DECLARING_NO_PHASE)),
            "a block that declares no phase must read None -- the contract did not say, and a "
            "guess here would invent a stage nobody asked for"
        )

    def test_an_absent_task_block_reads_none(self):
        # extract_task_block returns None for a block with no TASK block, and
        # declared_phase must answer None for it rather than raising --
        # build_dispatch hands it exactly that value for a needs_authoring
        # block.
        # POSITIVE CONTROL (fixture-owned): pass
        # extract_task_block(BLOCK_DECLARING_PHASE_RED) instead of the absent
        # one and this assertion turns red.
        declared_phase = self._declared_phase()
        self.assertIsNone(
            extract_task_block(BLOCK_WITH_NO_TASK_BLOCK_AT_ALL),
            "fixture sanity: this block genuinely has no TASK block"
        )
        self.assertIsNone(
            declared_phase(extract_task_block(BLOCK_WITH_NO_TASK_BLOCK_AT_ALL)),
            "no TASK block at all is the SAME answer as no phase line, on purpose: in both "
            "cases the contract did not say (Extension Point 11)"
        )

    def test_a_phase_value_outside_the_closed_set_reads_none(self):
        # Four probes, not one. AMBER alone begins with a letter neither member
        # claims, so it is passed by an implementation returning RED for
        # anything beginning with R, and by one that upper-cases before
        # comparing -- measured, both survived. REVIEW catches the first,
        # because the word an operator most plausibly mistypes into a phase
        # line is the name of the other kind of block this loop knows about.
        # Lowercase "red" catches the second.
        #
        # REFACTOR is the fourth, and it is the one a real author here is most
        # likely to write. A repository-wide census of `phase:` values found
        # exactly three in use -- RED, GREEN and REFACTOR, the last documented
        # in the test-first skill -- while lowercase "red" appears nowhere. So
        # REFACTOR is the near-miss with a live author behind it and "red" is
        # the near-miss with a live implementation defect behind it; both rows
        # are one line each, and both are kept.
        # POSITIVE CONTROL (fixture-owned): add "RED" to this tuple and that
        # row turns red.
        declared_phase = self._declared_phase()
        for value in ("AMBER", "REVIEW", "red", "REFACTOR"):
            with self.subTest(phase=value):
                block = BLOCK_DECLARING_PHASE_RED.replace("phase: RED", "phase: %s" % value)
                self.assertIsNone(
                    declared_phase(extract_task_block(block)),
                    "RED and GREEN are the closed set and the phase line is read VERBATIM, so "
                    "%r is unreadable to the loop and must never be passed through as a stage "
                    "name. A contract that means RED writes RED: normalising the value here "
                    "lets 'phase: REVIEW' or 'phase: red' decide a stage the contract never "
                    "declared in the form Extension Point 11 names, which is the same silent "
                    "default the unphased arm exists to avoid" % value
                )


# --------------------------------------------------------------------------
# (h2) --resume is read-only at EVERY branch, including the two that reach
# outside this process.
#
# Extension Point 10 says --resume joins --status in every branch currently
# written as `not args.dry_run and not args.status`. Measured in
# .claude/scripts/pr_merged.py, that phrase appears exactly four times: the
# --record-subtask state write, the sub-issue closure, the completion-record
# write, and the default report's state write. The suite's --resume cases
# witnessed the LAST one only, and the case above cannot reach the middle two
# at all, because its fixture supplies no --pr and the pull-request loop
# therefore never runs.
#
# The branch that matters most is the second. It reads
#   if verdict == "merged" and task_issue is not None and not args.dry_run
#       and not args.status:
#       sub_issue_closed = close_sub_issue(task_issue, pr.get("url", ""))
# and close_sub_issue runs `gh issue close` -- a real mutation on a live
# tracker. A flag whose entire promise is "report, write nothing" that can
# still close a GitHub issue is not a missing feature; it is the feature
# inverted. The measurement that made this a hole: removing --resume from that
# one branch left the whole suite green.
# --------------------------------------------------------------------------
#: A stored position whose one sub-task already carries a sub-issue. Without an
#: issue on the entry, main() short-circuits before close_sub_issue is ever
#: considered and the case below would be green for want of an observation.
_STATE_WITH_A_SUB_ISSUE = {
    "contract": "acme-red-fixture",
    "started_at": "2026-09-22T00:00:00Z",
    "sub_tasks": {
        "t1-backend": {"status": "awaiting-merge",
                       "branch": "task/acme-red-fixture/t1-backend",
                       "pull_request": None, "issue": 4242,
                       "base": "master", "brief": None},
    },
}


def _drive_main_over_a_pull_request_with(contract_text, commits, diff_table, flags,
                                         state=None, filename="acme-red-fixture.md"):
    """_drive_main_over_a_pull_request, with the flags and the stored position chosen.

    Extends that fixture (test_pr_merged.py:2974) rather than replacing it, and
    keeps every one of its edges stubbed: ``gh_pr`` returns the literal pull
    request, ``git_combined_diff`` answers out of ``diff_table``,
    ``file_at_commit`` returns nothing, ``write_state`` and ``write_record``
    are mocks, and ``pr_merged._run`` raises so no subprocess can start down a
    path this fixture did not anticipate. The module's subprocess guard near
    line 69 is left exactly as it is and is never reached.

    Two edges are added. ``close_sub_issue`` is a mock, so the branch in main()
    that runs ``gh issue close`` against a live GitHub tracker is observable
    instead of merely unreached. It is not main()'s only mutating branch --
    the dispatch path reaches ``create_branch``, which runs ``gh issue
    develop`` -- so this fixture stubs ``_run`` as well rather than relying on
    one mock. Patching close_sub_issue is also what keeps a --resume
    regression from becoming a closed issue on a real repository. And
    ``git_combined_diff``
    counts the identifiers it was asked about, so a run that walks the same
    commit twice is visible.

    Returns a dict rather than a tuple: this fixture has seven observations --
    text, exit_code, recorded, reads, write_record, write_state and
    close_sub_issue -- and positional unpacking of seven is how a later reader
    gets two of them the wrong way round.
    """
    recorded = {}
    reads = []
    real_build_record = pr_merged.build_record
    accepted = set(inspect.signature(real_build_record).parameters)

    def recording_build_record(*a, **kw):
        recorded.clear()
        recorded.update(kw)
        return real_build_record(*a, **{k: v for k, v in kw.items() if k in accepted})

    def counting_git_combined_diff(sha):
        reads.append(sha)
        return diff_table[sha]

    def no_subprocess(cmd):  # pragma: no cover -- must never be reached
        raise AssertionError(
            "this fixture must reach no process at all; %r was attempted" % (cmd,))

    pull_request = {
        "state": "MERGED", "mergedAt": "2026-09-22T00:00:00Z",
        "mergeCommit": {"oid": "merge-sha"}, "baseRefName": "master",
        "headRefName": "task/acme-red-fixture/t1-backend", "title": "t1-backend",
        "url": "https://example.invalid/pr/7",
        "commits": [{"oid": sha} for sha in commits], "statusCheckRollup": None,
    }
    write_record_mock = mock.MagicMock(return_value=None)
    write_state_mock = mock.MagicMock(return_value=None)
    close_sub_issue_mock = mock.MagicMock(return_value="closed")
    with tempfile.TemporaryDirectory() as d:
        contract_path = Path(d) / filename
        contract_path.write_text(contract_text, encoding="utf-8")
        out = io.StringIO()
        argv = ["pr_merged.py", "--contract", str(contract_path), "--pr", "7"] + list(flags)
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pr_merged, "load_records", return_value={}), \
             mock.patch.object(pr_merged, "load_state",
                               return_value=(json.loads(json.dumps(state))
                                             if state is not None else None)), \
             mock.patch.object(pr_merged, "default_branch", return_value="master"), \
             mock.patch.object(pr_merged, "write_state", write_state_mock), \
             mock.patch.object(pr_merged, "write_record", write_record_mock), \
             mock.patch.object(pr_merged, "close_sub_issue", close_sub_issue_mock), \
             mock.patch.object(pr_merged, "build_record", recording_build_record), \
             mock.patch.object(pr_merged, "gh_pr", lambda number: pull_request), \
             mock.patch.object(pr_merged, "git_combined_diff", counting_git_combined_diff), \
             mock.patch.object(pr_merged, "file_at_commit", lambda sha, path: None), \
             mock.patch.object(pr_merged, "_run", no_subprocess), \
             mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
             mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
             contextlib.redirect_stdout(out):
            exit_code = pr_merged.main()
    return {"text": out.getvalue(), "exit_code": exit_code, "recorded": recorded,
            "reads": reads, "write_record": write_record_mock,
            "write_state": write_state_mock, "close_sub_issue": close_sub_issue_mock}


class TestResumeIsReadOnlyAtEveryWritingBranch(unittest.TestCase):

    def test_resume_never_closes_a_sub_issue(self):
        # The hole this class exists for. RED today: main() never reads
        # args.resume, so this run reaches `gh issue close` through
        # close_sub_issue with a real issue number.
        # POSITIVE CONTROL, and a live one: its paired case
        # test_positive_control_the_same_run_without_resume_closes_and_writes
        # drives the identical fixture with --resume removed and asserts the
        # mock WAS called, so a green assertion here can never mean the mock
        # was wired to nothing. Measured separately against the throwaway stub
        # by removing `and not args.resume` from that one branch: this case
        # goes red alone, which is the mutation the shipped suite survived.
        run = _drive_main_over_a_pull_request_with(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, *_PR_THAT_FOUND_A_FILE[:2],
            flags=["--resume", "--json"], state=_STATE_WITH_A_SUB_ISSUE)
        self.assertFalse(
            run["close_sub_issue"].called,
            "--resume must join --status in the sub-issue branch as well (Extension Point 10). "
            "close_sub_issue runs `gh issue close` on a live tracker, so a read-only flag that "
            "reaches it does not merely write when it promised not to -- it mutates a system "
            "outside this process. It was called %d time(s) with %r"
            % (run["close_sub_issue"].call_count, run["close_sub_issue"].call_args_list)
        )

    def test_resume_writes_no_completion_record_for_a_merged_pull_request(self):
        # The reachable witness for the write_record half. The --resume case in
        # TestResumeIsAReadOnlyReport asserts the same thing over a fixture
        # that supplies no --pr, where write_record is unreachable and the
        # assertion cannot fail; this one drives the loop that writes.
        # POSITIVE CONTROL: the paired case below, same fixture without
        # --resume, asserts write_record WAS called. Measured against the stub
        # by removing `and not args.resume` from the write_record branch alone:
        # this case goes red alone.
        run = _drive_main_over_a_pull_request_with(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, *_PR_THAT_FOUND_A_FILE[:2],
            flags=["--resume", "--json"], state=_STATE_WITH_A_SUB_ISSUE)
        self.assertFalse(
            run["write_record"].called,
            "a --resume run that processes a pull request must write no completion record: a "
            "read-only report that writes is not read-only. write_record was called %d time(s)"
            % run["write_record"].call_count
        )
        self.assertFalse(
            run["write_state"].called,
            "and it must not move the stored position either, on the path that has a pull "
            "request to reconcile. write_state was called %d time(s)"
            % run["write_state"].call_count
        )

    def test_positive_control_the_same_run_without_resume_closes_and_writes(self):
        # Must stay green throughout. It proves all three mocks above observe
        # real calls, so the three assertFalse results are measurements rather
        # than mocks nobody wired. Mutation that turns it red: add "--resume"
        # to this flag list.
        run = _drive_main_over_a_pull_request_with(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, *_PR_THAT_FOUND_A_FILE[:2],
            flags=["--json"], state=_STATE_WITH_A_SUB_ISSUE)
        self.assertTrue(
            run["close_sub_issue"].called,
            "a plain run with a confirmed merge and a recorded sub-issue closes it -- if this "
            "ever goes red the read-only assertions above are measuring nothing"
        )
        self.assertEqual(
            run["close_sub_issue"].call_args[0][0], 4242,
            "and it closes THIS sub-task's issue, read out of the stored position"
        )
        self.assertTrue(
            run["write_record"].called,
            "the same plain run writes the completion record, which is what makes the "
            "write_record assertion above falsifiable"
        )

    def test_resume_never_writes_the_state_store_on_a_record_subtask_run(self):
        # The fourth branch: --record-subtask's own write, at the top of
        # main(). It is gated on --dry-run and --status today, and its two
        # existing cases (TestRecordSubtaskHonoursDryRunAndStatus) drive
        # exactly those two flags. Extension Point 10 says every branch, and
        # this is one.
        # POSITIVE CONTROL: the paired case below. Measured against the stub by
        # removing `and not args.resume` from this branch alone: this case goes
        # red alone.
        _text, write_state_mock, _ = _drive_main_with_flags(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK,
            ["--record-subtask", "t1-backend", "--issue", "7", "--base", "master",
             "--brief", ".claude/work-items/probe.md", "--resume", "--json"])
        self.assertFalse(
            write_state_mock.called,
            "--resume must join --status in the --record-subtask write as well: stamping an "
            "identity into the stored position is exactly the kind of move a flag promising a "
            "read-only report must not make. write_state was called %d time(s)"
            % write_state_mock.call_count
        )

    def test_positive_control_a_record_subtask_run_without_resume_writes(self):
        # Must stay green throughout, for the same reason as the control above.
        # Mutation that turns it red: add "--resume" to this flag list.
        _text, write_state_mock, _ = _drive_main_with_flags(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK,
            ["--record-subtask", "t1-backend", "--issue", "7", "--base", "master",
             "--brief", ".claude/work-items/probe.md", "--json"])
        self.assertTrue(
            write_state_mock.called,
            "a --record-subtask run with no read-only flag writes the stored position -- if "
            "this ever goes red the assertion above is measuring nothing"
        )


# --------------------------------------------------------------------------
# (c3) The PROCESSED report entry: Extension Point 4's other half.
#
# "main, the pull-request loop -- passes the summary into build_record, AND
# STAMPS THE REPORT ENTRY WITH THE SUB-TASK IDENTITY AND THE SOURCE OF THE
# READING." Integration Surfaces lists `sub_task` and `source` on both sides
# of the pr-merged skill's surface.
#
# TestMainPassesTheSummaryIntoBuildRecord reads the build_record call and the
# written record and never looks at report["hand_resolved"], so the entry the
# skill actually renders had no assertion at all: reducing it to {"pr": number}
# left the suite green, and so did dropping just the two counts. The SEEDED
# entry's counts are pinned by
# TestReportSeedsHandResolvedFromStoredRecords; the processed entry's were not.
# The consequence is the failure the contract rejected Option D for: the skill
# renders its four readings off this entry, so a freshly processed pull request
# would arrive as a bare file list with no merge_commits, and "not detectable"
# would be indistinguishable from "clean".
# --------------------------------------------------------------------------
class TestTheProcessedReportEntryNamesItsSubTaskAndItsSource(unittest.TestCase):

    def _entry(self, case):
        commits, table, expected = case
        _recorded, _mock, report = _drive_main_over_a_pull_request(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, commits, table)
        entries = [e for e in report.get("hand_resolved", []) if e.get("pr") == 7]
        self.assertEqual(
            len(entries), 1,
            "fixture sanity: this run processes exactly one pull request, so the report must "
            "carry exactly one entry for it. It carried %r" % (report.get("hand_resolved"),)
        )
        return entries[0], expected

    def test_a_processed_entry_carries_its_sub_task_its_source_and_all_three_facts(self):
        # POSITIVE CONTROL, measured against a throwaway stub main() that
        # appends {"pr": number} alone -- the reduction the shipped suite
        # survived: this case goes red, and so does the zero-merge-count case
        # below. Two failing cases, both in this class, nothing else in the
        # file. Measured a second time against a stub that stamps sub_task and
        # source but copies only summary["files"]: the same two cases go red
        # and every other assertion in this class's first case stays green, so
        # the counts are pinned by their own assertions rather than by the
        # identity ones.
        entry, expected = self._entry(_PR_THAT_FOUND_A_FILE)
        self.assertEqual(
            entry.get("sub_task"), "t1-backend",
            "Extension Point 4: the entry is stamped with the SUB-TASK IDENTITY. A pull request "
            "number identifies the request; only the sub-task id says which piece of the plan "
            "the finding belongs to, and the seeded entries beside it have no number at all. "
            "The entry read %r" % (entry,)
        )
        self.assertTrue(
            str(entry.get("source", "")).strip(),
            "and with the SOURCE OF THE READING, so a reader can tell a reading this run "
            "measured from one read back off a completion record. The entry read %r" % (entry,)
        )
        self.assertEqual(
            entry.get("files"), expected["files"],
            "the file list must reach the report, because the skill renders it"
        )
        self.assertEqual(
            entry.get("merge_commits"), expected["merge_commits"],
            "and merge_commits with it: the skill distinguishes four readings off this entry, "
            "and three of the four are decided by this count. Without it a freshly processed "
            "pull request renders as a bare file list"
        )
        self.assertEqual(
            entry.get("commits_inspected"), expected["commits_inspected"],
            "and commits_inspected, which is what makes merge_commits zero readable as "
            "'nothing was detectable' rather than 'no commits were reported'"
        )

    def test_a_pull_request_with_nothing_inspectable_reports_its_zero_merge_count(self):
        # The reading that cannot be inferred from the file list. Both cases
        # carry files == [], so an entry that reports files alone renders them
        # identically -- one was inspected and clean, the other could not be
        # measured at all. This is the exact collapse Alternatives Considered
        # rejected Option D for.
        # POSITIVE CONTROL (fixture-owned): drive _PR_THAT_FOUND_A_FILE here
        # instead and merge_commits reads 1, turning the assertion red.
        entry, expected = self._entry(_PR_WITH_NOTHING_INSPECTABLE)
        self.assertEqual(entry.get("files"), [],
                         "fixture sanity: this pull request found no files")
        self.assertEqual(
            entry.get("merge_commits"), 0,
            "zero inspected merge commits is a MEASUREMENT and must reach the report, or a "
            "squashed pull request is rendered as clean -- the first Failure Mode. The entry "
            "read %r" % (entry,)
        )
        self.assertEqual(entry.get("commits_inspected"), expected["commits_inspected"],
                         "with the count of commits that were inspected to reach it")

    def test_a_processed_reading_and_a_stored_reading_do_not_share_one_source(self):
        # `source` is only worth stamping if it discriminates. The contract
        # does not fix the vocabulary -- it says "the source of the reading" --
        # so this case pins the property rather than the words: the entry a run
        # walked and the entry it read back off disk must not answer the same.
        # POSITIVE CONTROL, measured against a throwaway stub main() that
        # stamps the same constant on both shapes: this case goes red alone,
        # while every presence assertion in this file stays green.
        processed, _expected = self._entry(_PR_THAT_FOUND_A_FILE)
        text, _, _ = _drive_main_with_flags(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, ["--status", "--json"],
            records={"t1-backend": _RECORD_WITH_SUMMARY})
        seeded_entries = [e for e in json.loads(text).get("hand_resolved", [])
                          if e.get("sub_task") == "t1-backend"]
        # Looked up as a list and asserted, never with next() over a generator:
        # a StopIteration escaping a test is a broken fixture, and this file's
        # rule is that an absent behaviour arrives as an assertion naming it.
        self.assertEqual(
            len(seeded_entries), 1,
            "the seeded half of this comparison needs exactly one entry for t1-backend -- "
            "Extension Point 5 seeds the report from the stored completion record. The report's "
            "hand_resolved list read %r" % (json.loads(text).get("hand_resolved"),)
        )
        seeded = seeded_entries[0]
        self.assertNotEqual(
            processed.get("source"), seeded.get("source"),
            "a reading this run walked and a reading recovered from a completion record are "
            "different claims about the same field: the first was measured now against the "
            "commits GitHub reported, the second was measured by a run nobody in this session "
            "watched. A source that answers the same for both carries no reading at all. "
            "Processed read %r, seeded read %r"
            % (processed.get("source"), seeded.get("source"))
        )


# --------------------------------------------------------------------------
# (b2) The walk happens ONCE.
#
# Extension Point 2 keeps detect_resolved_files "rather than deleting it
# because it is a public name AND THE WALK MUST NOT HAPPEN TWICE." That is the
# one claim the unit-level pairing above cannot make, and it is stated there
# rather than implied. Here it is observable: the fixture injects
# git_combined_diff, so counting the identifiers one main() run asks about
# catches a loop that computes the summary and then calls detect_resolved_files
# beside it -- the most likely way the two names drift back apart.
# --------------------------------------------------------------------------
class TestTheWalkHappensOnceForEachCommit(unittest.TestCase):

    def test_one_run_reads_each_reported_commit_exactly_once(self):
        # POSITIVE CONTROL, measured against a throwaway stub main() that keeps
        # the summary and adds `summary["files"] = detect_resolved_files(shas,
        # git_combined_diff)` beside it -- a second walk that agrees on every
        # value and costs one extra git read per commit: this case goes red
        # naming the doubled reads, and nothing else in the file moves. That
        # is what makes it the witness for a claim the value comparisons
        # cannot make.
        commits, table, _expected = _PR_THAT_FOUND_A_FILE
        run = _drive_main_over_a_pull_request_with(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, commits, table,
            flags=["--json"], state=_STATE_WITH_A_SUB_ISSUE)
        self.assertTrue(
            run["write_record"].called,
            "fixture sanity: this run must reach the pull-request loop, or the read count "
            "below is counting a loop that never ran"
        )
        self.assertEqual(
            run["reads"], list(commits),
            "one run must ask git about each reported commit exactly once, in the order the "
            "pull request reported them. A second walk beside the first doubles every read "
            "against a real repository and is how the projection quietly becomes two "
            "implementations that agree until one of them changes. It read %r" % (run["reads"],)
        )


# --------------------------------------------------------------------------
# (g2) The printed next-command line when there IS no command.
#
# Extension Point 9 names two forms, `next command: <lines joined by ", then
# ">` and `next command: none - <reason>`. Only the first was driven, so a
# printed line that stops after the prefix survived, and so did an arm that
# invents a runnable line for the one move that has none -- the defect
# test_blocked_gives_an_empty_command_list_and_a_non_empty_reason names in its
# own because-clause, pinned there on the function and nowhere on the output an
# operator actually reads.
# --------------------------------------------------------------------------
#: One sub-task, declaring a dependency on an ordinal the plan does not
#: contain, which is what drives main() into the blocked move.
CONTRACT_CLI_ONE_BLOCKED_TASK = """
## Implementation Handoff

### 1. Backend (`acme-dev`)

**Depends on:** 9

**Files to touch:**
- src/Foo.cs
"""

#: The loop commands that must never appear on a blocked line: the move's
#: whole content is that there is nothing to run. /flow stays in the tuple
#: as a guard against the reverted arm coming back.
_LOOP_COMMAND_TOKENS = ("/clear", "/advance", "/pr-merged", "/design-first", "/verify-before-done", "/flow")


class TestTheHumanReadableLineForAMoveWithNoCommand(unittest.TestCase):

    def test_a_blocked_move_prints_none_and_the_reason_rather_than_a_bare_prefix(self):
        # POSITIVE CONTROLS, both measured against throwaway stubs. A main()
        # whose empty-command branch prints "next command:" and stops: the
        # reason assertions go red and nothing else in the file moves. A
        # next_command_for whose blocked arm returns ["/advance <slug>"]
        # instead of []: the last assertion goes red here, alongside the
        # function-level case that already pins the empty list -- which is the
        # point, because until this case the printed output had no witness at
        # all.
        text, _, _ = _drive_main_with_flags(CONTRACT_CLI_ONE_BLOCKED_TASK, ["--status"])
        lines = [ln for ln in text.splitlines() if ln.strip()]
        self.assertTrue(lines, "fixture sanity: the human-readable report must print something")
        self.assertIn(
            "blocked:", text,
            "fixture sanity: this contract's one sub-task depends on an ordinal the plan does "
            "not contain, so the report must reach the blocked move. It read:\n%s" % text
        )
        last = lines[-1].strip()
        self.assertTrue(
            last.startswith("next command: none"),
            "a move with no runnable line still prints a next-command line, and it says NONE "
            "rather than trailing off after the prefix -- an operator who reads a bare 'next "
            "command:' cannot tell an empty answer from a truncated one. The last line read %r"
            % last
        )
        self.assertTrue(
            last[len("next command: none"):].strip(" -–—\t"),
            "I-5: the empty command list is meaningful only because a non-empty reason travels "
            "with it. Printing the word none alone is the missing field it exists to prevent. "
            "The last line read %r" % last
        )
        self.assertIn(
            "t1-backend", last,
            "and the reason names what is held, exactly as the blocked arm's own case requires "
            "of the function -- an operator reading the printed line is the only reader who "
            "ever sees it. The last line read %r" % last
        )
        for token in _LOOP_COMMAND_TOKENS:
            self.assertNotIn(
                token, last,
                "nothing is runnable while every sub-task is held, so the printed line must "
                "carry no runnable command -- %r appeared in %r. Inventing one here sends an "
                "operator to do work that cannot start" % (token, last)
            )


### --------------------------------------------------------------------------
# RED (t2-script-and-skills): W1 -- read-only flags must not reach a mutating
# callee through --dispatch.
#
# Extension Point 10 says --resume joins --status "in every branch currently
# written as `not args.dry_run and not args.status`". Measured against
# .claude/scripts/pr_merged.py, the dispatch section's two writes (create_branch
# at line 1493, write_state at line 1499) are gated on `args.dry_run` alone --
# neither `--status` nor `--resume` is read there at all, so a run carrying
# either flag alongside --dispatch still cuts a real branch (gh issue develop /
# git switch -c) and stamps the sub-task as dispatched in the state store.
# --------------------------------------------------------------------------
def _drive_dispatch_with_flags(extra_flags, filename="acme-dispatch-readonly-fixture.md"):
    """Drive --dispatch through main() with a chosen extra flag set.

    Mirrors TestMainDispatchCutsFromTheSubtasksDeclaredBase._drive_dispatch
    (test_pr_merged.py:1780), except write_state is a MagicMock rather than a
    bare return_value=None, so a case can ask whether main() wrote the state
    store as well as whether it cut a branch. The state entry is fixed --
    pending, with an issue and a declared base -- so advance() reports
    t1-backend ready to dispatch regardless of which extra flags are given;
    the only thing that varies between cases is the flag list.

    Returns (create_branch mock, write_state mock).
    """
    create_branch_mock = mock.MagicMock(return_value=(True, "created it"))
    write_state_mock = mock.MagicMock(return_value=None)
    with tempfile.TemporaryDirectory() as d:
        contract_path = Path(d) / filename
        contract_path.write_text(CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, encoding="utf-8")
        slug = contract_path.stem
        state = {
            "contract": slug,
            "started_at": "2026-09-19T00:00:00+00:00",
            "sub_tasks": {"t1-backend": {"status": "pending", "branch": None,
                                          "pull_request": None, "issue": 163,
                                          "base": "feature/160-parent", "brief": None}},
        }
        out = io.StringIO()
        argv = (["pr_merged.py", "--contract", str(contract_path),
                 "--dispatch", "t1-backend"] + list(extra_flags))
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pr_merged, "load_records", return_value={}), \
             mock.patch.object(pr_merged, "load_state", return_value=state), \
             mock.patch.object(pr_merged, "default_branch", return_value="master"), \
             mock.patch.object(pr_merged, "write_state", write_state_mock), \
             mock.patch.object(pr_merged, "create_branch", create_branch_mock), \
             mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
             mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
             contextlib.redirect_stdout(out):
            pr_merged.main()
    return create_branch_mock, write_state_mock


class TestReadOnlyFlagsNeverReachDispatchMutationsThroughDispatch(unittest.TestCase):
    """Extension Point 10 extended to --dispatch: --resume and --status must
    each keep create_branch and write_state unreached even when --dispatch
    names a sub-task advance() reports ready. Before this fix, main()'s
    read-only guard in the --dispatch branch (`read_only_dispatch`) was
    `args.dry_run` alone.
    """

    def test_resume_with_dispatch_never_calls_create_branch(self):
        # Was RED before the fix: measured directly against pr_merged.main()
        # -- this exact flag combination called create_branch with a real
        # branch name and a real issue number, which is what create_branch's
        # own docstring calls "a real mutation on a live tracker" one
        # function further down.
        create_branch_mock, _write_state_mock = _drive_dispatch_with_flags(
            ["--resume", "--json"])
        self.assertFalse(
            create_branch_mock.called,
            "--resume --dispatch <id> must not cut a branch -- --resume promises a read-only "
            "report (Extension Point 10), and create_branch runs `gh issue develop` / `git "
            "switch -c`, both real mutations against a live tracker and a real working tree. "
            "It was called %d time(s) with %r"
            % (create_branch_mock.call_count, create_branch_mock.call_args_list)
        )

    def test_resume_with_dispatch_never_calls_write_state(self):
        # Was RED before the fix, same call: main() stamps the sub-task as
        # dispatched in the state store immediately after cutting the
        # branch, gated on the same `args.dry_run`-only condition.
        _create_branch_mock, write_state_mock = _drive_dispatch_with_flags(
            ["--resume", "--json"])
        self.assertFalse(
            write_state_mock.called,
            "--resume --dispatch <id> must not stamp the sub-task as dispatched in the state "
            "store -- a read-only report must never move the stored position. write_state was "
            "called %d time(s)" % write_state_mock.call_count
        )

    def test_status_with_dispatch_never_calls_create_branch(self):
        # Was RED before the fix: --status carries the identical read-only
        # promise as --resume, and the gate at the time read neither.
        create_branch_mock, _write_state_mock = _drive_dispatch_with_flags(
            ["--status", "--json"])
        self.assertFalse(
            create_branch_mock.called,
            "--status --dispatch <id> must not cut a branch either -- --status is the other "
            "read-only front door Extension Point 10 names. It was called %d time(s) with %r"
            % (create_branch_mock.call_count, create_branch_mock.call_args_list)
        )

    def test_status_with_dispatch_never_calls_write_state(self):
        _create_branch_mock, write_state_mock = _drive_dispatch_with_flags(
            ["--status", "--json"])
        self.assertFalse(
            write_state_mock.called,
            "--status --dispatch <id> must not stamp the state store. write_state was called "
            "%d time(s)" % write_state_mock.call_count
        )

    def test_positive_control_the_same_dispatch_without_a_read_only_flag_mutates_both(self):
        # Must stay green throughout. Proves the two mocks above observe real
        # calls, so the four assertFalse results above are measurements, never
        # mocks wired to nothing. Mutation that turns it red: add "--resume"
        # (or "--status") to this flag list -- measured directly, both mutate
        # this exact assertion.
        create_branch_mock, write_state_mock = _drive_dispatch_with_flags(["--json"])
        self.assertTrue(
            create_branch_mock.called,
            "fixture sanity: a plain --dispatch run on a released sub-task cuts its branch -- "
            "if this ever goes red the assertFalse results above are measuring nothing"
        )
        self.assertTrue(
            write_state_mock.called,
            "fixture sanity: and it stamps the state store, for the same reason"
        )


# --------------------------------------------------------------------------
# RED (t2-script-and-skills): W2 -- one hand-resolved entry per sub-task.
#
# main()'s seeding loop (the `for tid, rec in records.items():` loop) runs
# BEFORE the pull-request loop and appends one entry per stored completion
# record, unconditionally. The pull-request loop (`for number in args.pr:`)
# appends its own entry for whatever sub-task the measured pull request maps
# to. Nothing removes the
# seeded entry once the measured one exists, so a sub-task that is BOTH stored
# AND measured this run carries two entries in report["hand_resolved"] -- one
# stale, one fresh, with two different "source" readings for the same
# identity. Data Shapes' invariant on this field (I-1/I-2) never claims two
# entries are acceptable; the pr-merged skill renders one line per sub-task,
# so a second entry is either silently dropped by the renderer or silently
# doubles the printed line, and neither is a report the skill promised.
# --------------------------------------------------------------------------
def _no_subprocess_reached(cmd):  # pragma: no cover -- must never be reached
    raise AssertionError(
        "this fixture must reach no process at all; %r was attempted" % (cmd,))


def _drive_main_over_a_pull_request_with_stored_records(contract_text, commits, diff_table,
                                                         records, filename="acme-red-fixture.md"):
    """Like _drive_main_over_a_pull_request (test_pr_merged.py:2974), except
    load_records returns the caller's own stored records instead of {} -- so
    the pull request measured this run can map to a sub-task that ALREADY
    carries a seeded hand_resolved entry from a previous run's completion
    record. Every edge to the outside world is stubbed exactly as that
    fixture stubs it: gh_pr returns the literal pull request built below,
    git_combined_diff answers out of diff_table, file_at_commit returns
    nothing, write_state and write_record are mocks, and pr_merged._run
    raises so no subprocess can start.

    Returns the parsed --json report.
    """
    pull_request = {
        "state": "MERGED", "mergedAt": "2026-09-22T00:00:00Z",
        "mergeCommit": {"oid": "merge-sha"}, "baseRefName": "master",
        "headRefName": "task/acme-red-fixture/t1-backend", "title": "t1-backend",
        "url": "https://example.invalid/pr/7",
        "commits": [{"oid": sha} for sha in commits], "statusCheckRollup": None,
    }
    with tempfile.TemporaryDirectory() as d:
        contract_path = Path(d) / filename
        contract_path.write_text(contract_text, encoding="utf-8")
        out = io.StringIO()
        argv = ["pr_merged.py", "--contract", str(contract_path), "--pr", "7", "--json"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pr_merged, "load_records", return_value=dict(records)), \
             mock.patch.object(pr_merged, "load_state", return_value=None), \
             mock.patch.object(pr_merged, "default_branch", return_value="master"), \
             mock.patch.object(pr_merged, "write_state", mock.MagicMock(return_value=None)), \
             mock.patch.object(pr_merged, "write_record", mock.MagicMock(return_value=None)), \
             mock.patch.object(pr_merged, "gh_pr", lambda number: pull_request), \
             mock.patch.object(pr_merged, "git_combined_diff", lambda sha: diff_table[sha]), \
             mock.patch.object(pr_merged, "file_at_commit", lambda sha, path: None), \
             mock.patch.object(pr_merged, "_run", _no_subprocess_reached), \
             mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
             mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
             contextlib.redirect_stdout(out):
            pr_merged.main()
        return json.loads(out.getvalue())


#: A stale reading left on disk by a previous run, for the same sub-task this
#: run's pull request maps to.
_STORED_HAND_RESOLVED_FOR_T1 = {
    "status": "completed", "verified": "github", "pull_request": "u",
    "hand_resolved": {"files": ["stale.txt"], "merge_commits": 1, "commits_inspected": 1},
}
#: A stored reading for a sub-task this run's pull request does NOT touch --
#: the positive control that proves the fix removes a duplicate rather than
#: every seeded entry.
_STORED_HAND_RESOLVED_FOR_OTHER = {
    "status": "completed", "verified": "github", "pull_request": "u",
    "hand_resolved": {"files": ["other.txt"], "merge_commits": 2, "commits_inspected": 2},
}


def _drive_main_over_two_pull_requests_mapping_to_the_same_subtask(
        contract_text, commits, diff_table, records, filename="acme-red-fixture.md"):
    """Like _drive_main_over_a_pull_request_with_stored_records (test_pr_merged.py:4960),
    except TWO pull requests (#7 and #8) are processed in ONE run, and BOTH map to the
    same sub-task -- gh_pr answers with the identical headRefName whatever number it is
    asked about, so map_pr_to_subtask resolves both to t1-backend. Every edge to the
    outside world is stubbed exactly the same way: git_combined_diff answers out of
    diff_table, file_at_commit returns nothing, write_state and write_record are mocks,
    and pr_merged._run raises so no subprocess can start.

    Returns the parsed --json report.
    """
    def pull_request_for(number):
        return {
            "state": "MERGED", "mergedAt": "2026-09-22T00:00:00Z",
            "mergeCommit": {"oid": "merge-sha-%d" % number}, "baseRefName": "master",
            "headRefName": "task/acme-red-fixture/t1-backend", "title": "t1-backend",
            "url": "https://example.invalid/pr/%d" % number,
            "commits": [{"oid": sha} for sha in commits], "statusCheckRollup": None,
        }
    with tempfile.TemporaryDirectory() as d:
        contract_path = Path(d) / filename
        contract_path.write_text(contract_text, encoding="utf-8")
        out = io.StringIO()
        argv = ["pr_merged.py", "--contract", str(contract_path),
                "--pr", "7", "--pr", "8", "--json"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pr_merged, "load_records", return_value=dict(records)), \
             mock.patch.object(pr_merged, "load_state", return_value=None), \
             mock.patch.object(pr_merged, "default_branch", return_value="master"), \
             mock.patch.object(pr_merged, "write_state", mock.MagicMock(return_value=None)), \
             mock.patch.object(pr_merged, "write_record", mock.MagicMock(return_value=None)), \
             mock.patch.object(pr_merged, "gh_pr", pull_request_for), \
             mock.patch.object(pr_merged, "git_combined_diff", lambda sha: diff_table[sha]), \
             mock.patch.object(pr_merged, "file_at_commit", lambda sha, path: None), \
             mock.patch.object(pr_merged, "_run", _no_subprocess_reached), \
             mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
             mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
             contextlib.redirect_stdout(out):
            pr_merged.main()
        return json.loads(out.getvalue())


class TestHandResolvedReportsExactlyOneEntryPerSubTask(unittest.TestCase):

    def _entries_for(self, report, sub_task):
        return [e for e in report.get("hand_resolved", []) if e.get("sub_task") == sub_task]

    def test_a_measured_subtask_keeps_only_its_measured_entry(self):
        # Was RED before the fix: measured directly against pr_merged.main()
        # -- t1-backend carried two entries, one seeded with source
        # "stored-record" and one appended with source "measured-this-run".
        report = _drive_main_over_a_pull_request_with_stored_records(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, *_PR_THAT_FOUND_A_FILE[:2],
            records={"t1-backend": _STORED_HAND_RESOLVED_FOR_T1})
        entries = self._entries_for(report, "t1-backend")
        self.assertEqual(
            len(entries), 1,
            "a sub-task both stored AND measured this run must carry exactly one hand_resolved "
            "entry -- the seeded entry from the stored record and the freshly measured entry "
            "must not both survive into the report. Found %r" % (entries,)
        )
        self.assertEqual(
            entries[0].get("source"), "measured-this-run",
            "the surviving entry must be the one this run measured, not the stale one read "
            "back off disk -- a session that just watched the merge knows more than a "
            "completion record written before it ever ran. The surviving entry read %r"
            % (entries[0],)
        )
        self.assertEqual(
            entries[0].get("files"), _PR_THAT_FOUND_A_FILE[2]["files"],
            "and it must carry the freshly measured file list, not the stale one from the "
            "stored record. The surviving entry read %r" % (entries[0],)
        )

    def test_a_stored_subtask_not_measured_this_run_keeps_its_seeded_entry(self):
        # POSITIVE CONTROL: a different sub-task, not mapped by this run's
        # pull request, must be unaffected by whatever dedup rule fixes the
        # case above -- proving the fix removes the DUPLICATE for the
        # colliding identity rather than discarding seeded entries altogether.
        # Measured against a throwaway stub that drops every seeded entry
        # unconditionally: this case goes red while the one above stays green.
        report = _drive_main_over_a_pull_request_with_stored_records(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, *_PR_THAT_FOUND_A_FILE[:2],
            records={"t1-backend": _STORED_HAND_RESOLVED_FOR_T1,
                     "t2-other": _STORED_HAND_RESOLVED_FOR_OTHER})
        entries = self._entries_for(report, "t2-other")
        self.assertEqual(
            len(entries), 1,
            "a sub-task this run never measured must keep exactly its one seeded entry -- a "
            "dedup rule that discards every seeded entry regardless of whether it collides "
            "with a measured one would pass the case above and fail this one. Found %r"
            % (entries,)
        )
        self.assertEqual(
            entries[0].get("source"), "stored-record",
            "and that entry must still read as a stored reading, since nothing measured "
            "t2-other this run. The entry read %r" % (entries[0],)
        )
        self.assertEqual(
            entries[0].get("files"), ["other.txt"],
            "and it must still carry the stored file list, unchanged by the dedup rule"
        )

    def test_two_pull_requests_mapping_to_the_same_subtask_both_keep_their_measured_entries(self):
        # W-3b (t2-script-and-skills). This may already pass: main()'s dedup filter
        # (the `report["hand_resolved"] = [...]` comprehension inside the pull-request
        # loop) keeps every entry whose source IS "measured-this-run"
        # and drops only entries that are NOT, so a second measured pull request landing
        # on the same sub-task this run should already survive beside the first, and the
        # stale stored entry should already be gone by the time the second iteration
        # runs. Pinned here as a mutation probe: a dedup rule mutated to "keep only the
        # LAST measured-this-run entry for a sub-task" would still pass every other case
        # in this class and go red only here.
        report = _drive_main_over_two_pull_requests_mapping_to_the_same_subtask(
            CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, *_PR_THAT_FOUND_A_FILE[:2],
            records={"t1-backend": _STORED_HAND_RESOLVED_FOR_T1})
        entries = self._entries_for(report, "t1-backend")
        prs = sorted(e.get("pr") for e in entries)
        self.assertEqual(
            prs, [7, 8],
            "both pull requests mapped to t1-backend this run, and both must keep their own "
            "measured entry -- one per pull request, never a single winner. Found %r" % (entries,)
        )
        for entry in entries:
            self.assertEqual(
                entry.get("source"), "measured-this-run",
                "every surviving entry for a sub-task measured this run must read as measured, "
                "never as the stale stored reading left on disk. Entry read %r" % (entry,)
            )
        self.assertEqual(
            len(entries), 2,
            "no stored entry may survive alongside the two measured ones for this sub-task -- "
            "found %r" % (entries,)
        )


# --------------------------------------------------------------------------
# RED (t2-script-and-skills): W3 -- _render_hand_resolved_reading fails
# closed on a malformed stored count.
#
# Measured directly against pr_merged._render_hand_resolved_reading
# (pr_merged.py:1242): the only special case is the LITERAL value 0
# (`if entry.get("merge_commits") == 0:`). An absent key, an explicit None, a
# string, or a negative value all fail that comparison and fall through to
# the files check, which reads "clean" whenever files is also empty -- the
# exact overclaim the Hand-Resolved Summary's four-state reading exists to
# prevent (Failure Modes, first entry).
# --------------------------------------------------------------------------
class TestRenderHandResolvedReadingFailsClosedOnAMalformedCount(unittest.TestCase):

    def _reading(self, entry):
        fn = _fn("_render_hand_resolved_reading")
        self.assertIsNotNone(
            fn, "pr_merged._render_hand_resolved_reading must exist -- Data Shapes names it "
                "the renderer of the Hand-Resolved Summary's four readings"
        )
        return fn(entry)

    def _not_detectable_prefix(self):
        # Read the function's OWN wording for the literal-0 case, once, so
        # every malformed-count case below compares against words the
        # function already uses rather than a copy that could drift from it.
        return self._reading(
            {"source": "measured-this-run", "files": [], "merge_commits": 0,
             "commits_inspected": 2}).split(" (")[0]

    def test_positive_control_zero_merge_commits_with_no_files_reads_not_detectable(self):
        reading = self._reading({"source": "measured-this-run", "files": [],
                                 "merge_commits": 0, "commits_inspected": 2})
        self.assertTrue(
            reading.startswith("not detectable"),
            "fixture sanity: zero merge commits inspected must already read as not detectable "
            "-- if this is not true nothing below is measuring the right function. Read %r"
            % reading
        )

    def test_positive_control_two_merge_commits_with_no_files_reads_clean(self):
        reading = self._reading({"source": "measured-this-run", "files": [],
                                 "merge_commits": 2, "commits_inspected": 2})
        self.assertEqual(
            reading, "clean",
            "fixture sanity: a genuinely measured, genuinely clean merge must still read "
            "clean -- otherwise the fail-closed cases below could not be told apart from a "
            "function that just always refuses to say clean"
        )

    def test_positive_control_two_merge_commits_with_files_lists_them(self):
        reading = self._reading({"source": "measured-this-run",
                                 "files": ["src/Hand.cs"], "merge_commits": 2,
                                 "commits_inspected": 2})
        self.assertEqual(
            reading, "src/Hand.cs",
            "fixture sanity: a measured merge that found a file names it, unaffected by "
            "whatever fail-closed rule the malformed-count cases below require"
        )

    def test_an_absent_merge_commits_key_never_reads_clean(self):
        # RED today: measured directly -- entry.get("merge_commits") is None,
        # None == 0 is False, files is empty, so this reads "clean".
        prefix = self._not_detectable_prefix()
        reading = self._reading({"source": "measured-this-run", "files": []})
        self.assertNotEqual(
            reading, "clean",
            "a stored hand_resolved summary with no merge_commits key at all must never read "
            "as clean -- 'clean' claims a merge was inspected and found nothing, and nothing "
            "was inspected here. Read %r" % reading
        )
        self.assertTrue(
            reading.startswith(prefix),
            "and it should read with the function's own not-detectable wording, the same "
            "words it already uses for a literal 0, since a caller cannot trust a count that "
            "is not there. Read %r" % reading
        )

    def test_a_none_merge_commits_value_never_reads_clean(self):
        # RED today: same failure, this time with the key present and holding
        # an explicit None -- which a hand-edited or partially-migrated record
        # could carry.
        prefix = self._not_detectable_prefix()
        reading = self._reading({"source": "measured-this-run", "files": [],
                                 "merge_commits": None})
        self.assertNotEqual(
            reading, "clean",
            "an explicit None must never read as clean either. Read %r" % reading
        )
        self.assertTrue(
            reading.startswith(prefix),
            "and it should carry the same not-detectable wording. Read %r" % reading
        )

    def test_a_string_merge_commits_value_never_reads_clean(self):
        # RED today: a merge_commits value that survived a YAML round trip as
        # text rather than a number is not a count the reader can trust, and
        # "2" == 0 is False just as surely as None == 0 is.
        prefix = self._not_detectable_prefix()
        reading = self._reading({"source": "measured-this-run", "files": [],
                                 "merge_commits": "2"})
        self.assertNotEqual(
            reading, "clean",
            "a merge_commits value that arrived as a string is not a count the reader can "
            "trust -- a hand-corrupted completion record can carry exactly this shape. "
            "Read %r" % reading
        )
        self.assertTrue(
            reading.startswith(prefix),
            "and it should carry the same not-detectable wording. Read %r" % reading
        )

    def test_a_negative_merge_commits_value_never_reads_clean(self):
        # RED today: -1 == 0 is False, so a nonsensical negative count is
        # treated exactly like a genuinely inspected, genuinely clean merge.
        prefix = self._not_detectable_prefix()
        reading = self._reading({"source": "measured-this-run", "files": [],
                                 "merge_commits": -1})
        self.assertNotEqual(
            reading, "clean",
            "a negative merge_commits count is nonsensical and must never be read as a clean "
            "measurement -- today only the literal value 0 is special-cased. Read %r" % reading
        )
        self.assertTrue(
            reading.startswith(prefix),
            "and it should carry the same not-detectable wording. Read %r" % reading
        )

    def test_a_scalar_hand_resolved_value_does_not_crash_main(self):
        # RED today, and for a different reason than the six cases above: a
        # stored record's hand_resolved should always be a mapping, but a
        # hand-edited or corrupted YAML file could carry a bare scalar.
        # main()'s seeding loop does `dict(_stored)` unconditionally
        # (pr_merged.py:1356), and dict("x") raises ValueError -- measured
        # directly against pr_merged.main(). A malformed record on disk must
        # never crash an otherwise read-only report; wrapped in try/except so
        # an uncaught exception here is reported as THIS assertion failing,
        # never as an unrelated test-runner error.
        try:
            text, _, _ = _drive_main_with_flags(
                CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, ["--status", "--json"],
                records={"t1-backend": {"status": "completed", "hand_resolved": "x"}})
        except Exception as exc:
            self.fail(
                "a scalar hand_resolved value on a stored record must not crash main() -- it "
                "raised %s: %s. The seeding loop must treat an unreadable shape the same way "
                "it treats a missing key, never let it propagate out of a read-only report"
                % (type(exc).__name__, exc)
            )
        report = json.loads(text)
        entries = [e for e in report.get("hand_resolved", [])
                  if e.get("sub_task") == "t1-backend"]
        self.assertEqual(
            len(entries), 1,
            "the malformed record must still be accounted for as one entry, not silently "
            "dropped nor allowed to crash the run. Found %r" % (entries,)
        )

    def test_a_bool_true_merge_commits_value_never_reads_clean(self):
        # W-3a (t2-script-and-skills). Already fails closed today: the guard reads
        # `isinstance(merge_commits, bool)` explicitly, so a literal True short-circuits
        # before `merge_commits <= 0` is ever evaluated. Pinned here as a regression
        # guard against a future refactor of that isinstance check, not as a new RED.
        prefix = self._not_detectable_prefix()
        reading = self._reading({"source": "measured-this-run", "files": [],
                                 "merge_commits": True})
        self.assertNotEqual(
            reading, "clean",
            "a bool True is not a genuine merge-commit count and must never read as clean. "
            "Read %r" % reading
        )
        self.assertTrue(
            reading.startswith(prefix),
            "and it should carry the same not-detectable wording as every other malformed "
            "count. Read %r" % reading
        )

    def test_a_bool_false_merge_commits_value_never_reads_clean(self):
        # W-3a (t2-script-and-skills). Same guard, the other bool value.
        prefix = self._not_detectable_prefix()
        reading = self._reading({"source": "measured-this-run", "files": [],
                                 "merge_commits": False})
        self.assertNotEqual(
            reading, "clean",
            "a bool False is not a genuine merge-commit count and must never read as clean. "
            "Read %r" % reading
        )
        self.assertTrue(
            reading.startswith(prefix),
            "and it should carry the same not-detectable wording. Read %r" % reading
        )

    def _reading_no_raise(self, entry):
        """Like _reading, except an exception from the function under test is converted
        into self.fail -- so a malformed `files` field that crashes
        _render_hand_resolved_reading registers as THIS test's own assertion failure,
        never as an unrelated test-runner error.
        """
        fn = _fn("_render_hand_resolved_reading")
        self.assertIsNotNone(
            fn, "pr_merged._render_hand_resolved_reading must exist -- Data Shapes names it "
                "the renderer of the Hand-Resolved Summary's four readings"
        )
        try:
            return fn(entry)
        except Exception as exc:
            self.fail(
                "_render_hand_resolved_reading must never raise on a malformed files field -- "
                "it raised %s: %s for entry %r" % (type(exc).__name__, exc, entry)
            )

    def test_an_absent_files_key_never_reads_clean(self):
        # W-1 (t2-script-and-skills). RED today: entry.get("files") returns None,
        # `None or []` collapses to [], and `if files:` reads False -- the exact same
        # path a genuinely inspected, genuinely clean merge takes. An absent files
        # field is a different claim: the shape could not be read at all, and reading
        # it as clean is the overclaim this reading exists to prevent.
        reading = self._reading_no_raise({"source": "measured-this-run", "merge_commits": 2})
        self.assertNotEqual(
            reading, "clean",
            "an absent files field must not read the same as an inspected-and-clean merge. "
            "Read %r" % reading
        )

    def test_a_none_files_value_never_reads_clean(self):
        # W-1 (t2-script-and-skills). RED today: same collapse as the absent case, this
        # time with the key present and holding an explicit None.
        reading = self._reading_no_raise(
            {"source": "measured-this-run", "merge_commits": 2, "files": None})
        self.assertNotEqual(
            reading, "clean",
            "an explicit None files value must not read as clean either. Read %r" % reading
        )

    def test_an_empty_dict_files_value_never_reads_clean(self):
        # W-1 (t2-script-and-skills). RED today: `{} or []` is falsy-collapsed to [] the
        # same way, so a files field that is not even the right SHAPE -- a mapping,
        # never a list -- is read as though it were an inspected, empty list.
        reading = self._reading_no_raise(
            {"source": "measured-this-run", "merge_commits": 2, "files": {}})
        self.assertNotEqual(
            reading, "clean",
            "a files field holding a mapping is not a file list and must not read as clean. "
            "Read %r" % reading
        )

    def test_a_zero_files_value_never_reads_clean(self):
        # W-1 (t2-script-and-skills). RED today: `0 or []` is falsy-collapsed the same way.
        reading = self._reading_no_raise(
            {"source": "measured-this-run", "merge_commits": 2, "files": 0})
        self.assertNotEqual(
            reading, "clean",
            "a files field holding the integer 0 is not a file list and must not read as "
            "clean. Read %r" % reading
        )

    def test_a_string_files_value_is_not_rendered_character_by_character(self):
        # W-1 (t2-script-and-skills). RED today: a non-empty string is truthy, so
        # `", ".join(files)` runs -- and join() over a string iterates its CHARACTERS,
        # not a one-element file list. A hand-edited or partially-migrated record
        # carrying a bare path string here must not silently explode into its letters.
        reading = self._reading_no_raise(
            {"source": "measured-this-run", "merge_commits": 2, "files": "src/a.cs"})
        char_joined = ", ".join("src/a.cs")
        self.assertNotEqual(
            reading, "clean",
            "fixture sanity: a truthy files value must not fall through to clean either. "
            "Read %r" % reading
        )
        self.assertNotEqual(
            reading, char_joined,
            "a bare string files value must never be rendered character by character -- "
            "join() iterating a string's letters is the overclaim this test pins shut. "
            "Read %r" % reading
        )

    def test_a_list_with_a_non_string_element_does_not_crash(self):
        # W-1 (t2-script-and-skills). RED today: `", ".join(["a", None])` raises
        # TypeError -- str.join demands every element be a string, and a hand-edited
        # or partially-migrated completion record can carry exactly this shape. Failing
        # closed means reporting something readable, never crashing an otherwise
        # read-only render.
        reading = self._reading_no_raise(
            {"source": "measured-this-run", "merge_commits": 2, "files": ["a", None]})
        self.assertNotEqual(
            reading, "clean",
            "a file list carrying a non-string element is not a genuinely clean measurement "
            "and must not read as one. Read %r" % reading
        )

    def test_main_does_not_crash_on_a_stored_record_with_a_malformed_files_list(self):
        # W-1 (t2-script-and-skills). RED today: main()'s human-readable branch calls
        # _render_hand_resolved_reading(h) directly for every seeded entry
        # (pr_merged.py:1592) -- a stored record with files=['a', None] crashes that
        # call with the same TypeError the unit-level case above pins, this time
        # reached through main() itself rather than the function in isolation.
        try:
            text, _, _ = _drive_main_with_flags(
                CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, ["--status"],
                records={"t1-backend": {"status": "completed", "verified": "github",
                                        "pull_request": "u",
                                        "hand_resolved": {"merge_commits": 2,
                                                          "files": ["a", None]}}})
        except Exception as exc:
            self.fail(
                "a stored record with a malformed files list must not crash main() -- it "
                "raised %s: %s. A malformed shape on disk must be reported as unreadable, "
                "never allowed to propagate out of a read-only report"
                % (type(exc).__name__, exc)
            )
        self.assertIn(
            "hand-resolved", text,
            "fixture sanity: the human-readable report must reach the hand-resolved line "
            "rather than crashing before it. It read:\n%s" % text
        )


# --------------------------------------------------------------------------
# RED (t2-script-and-skills): W2 -- every hand_resolved entry in --json output
# carries its own rendered reading.
#
# Data Shapes' Hand-Resolved Summary names four readings a person interprets
# from files/merge_commits/source -- today that rendering exists ONLY in
# main()'s human-readable branch (pr_merged.py:1592), one call to
# _render_hand_resolved_reading per printed line. A caller reading --json
# output -- the orchestrator loop, or a skill rendering the report itself --
# gets the raw files/merge_commits/commits_inspected/source fields and must
# reimplement the same four-state reading a second time, which is exactly the
# drift Alternatives Considered rejects for the printed line. Every entry
# report["hand_resolved"] carries, whatever produced it -- a seeded
# stored-record, a not-recorded placeholder, or a freshly measured entry --
# must carry its own "reading" field in --json output too.
# --------------------------------------------------------------------------
#: Three sub-tasks, so one run can carry all three sources at once: t1-backend
#: is the one this run's pull request measures, t2-other keeps a stored
#: completion record with a hand_resolved summary, and t3-third keeps a
#: completion record with no hand_resolved key at all.
CONTRACT_CLI_THREE_SUBTASKS_FOR_READING_FIELD = """
## Implementation Handoff

### 1. Backend (`acme-dev`)

**Depends on:** none

**Files to touch:**
- src/Foo.cs

### 2. Other (`acme-dev`)

**Depends on:** none

**Files to touch:**
- src/Bar.cs

### 3. Third (`acme-dev`)

**Depends on:** none

**Files to touch:**
- src/Baz.cs
"""


class TestEveryHandResolvedEntryCarriesItsOwnRenderedReadingInJson(unittest.TestCase):

    def test_a_seeded_stored_record_a_not_recorded_entry_and_a_measured_entry_all_carry_their_reading(self):
        # RED today: measured through main() with --json -- report["hand_resolved"]
        # entries carry files/merge_commits/commits_inspected/source and a sub_task,
        # but no "reading" key at all, on any of the three sources this run produces
        # in one pass.
        render = _fn("_render_hand_resolved_reading")
        self.assertIsNotNone(
            render, "pr_merged._render_hand_resolved_reading must exist -- Data Shapes "
                    "names it the renderer of the Hand-Resolved Summary's four readings"
        )
        report = _drive_main_over_a_pull_request_with_stored_records(
            CONTRACT_CLI_THREE_SUBTASKS_FOR_READING_FIELD, *_PR_THAT_FOUND_A_FILE[:2],
            records={
                "t2-other": _STORED_HAND_RESOLVED_FOR_OTHER,
                "t3-third": {"status": "completed", "verified": "github", "pull_request": "u"},
            })
        by_subtask = {e.get("sub_task"): e for e in report.get("hand_resolved", [])}
        for sub_task, expected_source in (
                ("t1-backend", "measured-this-run"),
                ("t2-other", "stored-record"),
                ("t3-third", "not-recorded")):
            with self.subTest(sub_task=sub_task):
                entry = by_subtask.get(sub_task)
                self.assertIsNotNone(
                    entry,
                    "fixture sanity: this run must produce exactly one entry for %r. The "
                    "report's hand_resolved list read %r"
                    % (sub_task, report.get("hand_resolved"))
                )
                self.assertEqual(
                    entry.get("source"), expected_source,
                    "fixture sanity: %r must carry the %r source, or this case is not "
                    "measuring the reading it claims to. Entry read %r"
                    % (sub_task, expected_source, entry)
                )
                self.assertIn(
                    "reading", entry,
                    "every hand_resolved entry in --json output must carry its own rendered "
                    "reading -- a caller reading --json must not reimplement the four-state "
                    "reading main()'s own human-readable branch already computes. Entry read "
                    "%r" % entry
                )
                self.assertEqual(
                    entry.get("reading"), render(entry),
                    "and the stamped reading must equal _render_hand_resolved_reading(entry) "
                    "for that same entry -- the JSON output and the printed line must never "
                    "disagree about what a reader is told this entry means. Entry read %r"
                    % entry
                )


# --------------------------------------------------------------------------
# RED (t2-script-and-skills): W6 -- declared_phase reads one line only.
#
# Measured directly against pr_merged.declared_phase (pr_merged.py:770): the
# regex `r"^\s*phase:\s*(\S+)\s*$"` uses re.M, but \s (unlike a literal space)
# matches a newline character too, so the `\s*` between the colon and the
# value can cross a line boundary. A phase line broken across two lines is
# read as if it were one line, and two CONFLICTING phase lines inside one
# TASK block resolve silently to whichever comes first, rather than reading
# as the ambiguous declaration it is.
# --------------------------------------------------------------------------
#: A TASK block whose PRIOR_FINDINGS carries the phase line TWICE, with
#: disagreeing values -- an author who edited the line and left the old one
#: behind, or a merge that combined two authors' TASK blocks. declared_phase
#: must read this as undeclared, the same as no phase line at all, never as
#: whichever value the regex happens to match first.
BLOCK_DECLARING_CONFLICTING_PHASES = """
**Depends on:** none

**Files to touch:**
- src/Foo.cs

**Pre-written TASK block:**
```
TASK: Do the thing.
CONTEXT: concept contract at .claude/concepts/c-slug.md
PRIOR_FINDINGS:
  contract_path: .claude/concepts/c-slug.md
  contract_status: approved
  phase: RED
  phase: GREEN
```
"""


class TestDeclaredPhaseReadsOneLineOnly(unittest.TestCase):

    def _declared_phase(self):
        fn = _fn("declared_phase")
        self.assertIsNotNone(
            fn, "pr_merged.declared_phase must exist -- Extension Point 11 names it the pure "
                "function that reads the phase line out of a block's own TASK block"
        )
        return fn

    def test_a_phase_value_split_across_two_lines_reads_none(self):
        # RED today: measured directly -- declared_phase("phase:\nGREEN")
        # returns "GREEN", because \s* between "phase:" and the value happily
        # consumes the newline. The value never sat on the phase line at all;
        # reading it anyway is the same silent-default failure the unphased
        # arm of build_dispatch exists to avoid, one level down.
        declared_phase = self._declared_phase()
        self.assertIsNone(
            declared_phase("phase:\nGREEN"),
            "a phase value that is not on the same line as the phase: label was never "
            "declared on that line -- declared_phase must read this as undeclared (None), "
            "never cross the newline to find a value sitting on the next line"
        )

    def test_two_conflicting_phase_lines_in_one_task_block_read_none(self):
        # RED today: measured directly against
        # declared_phase(extract_task_block(BLOCK_DECLARING_CONFLICTING_PHASES))
        # -- today's regex is a plain re.search, so it returns the FIRST
        # match ("RED") and never notices the second, contradicting line.
        declared_phase = self._declared_phase()
        task_block = extract_task_block(BLOCK_DECLARING_CONFLICTING_PHASES)
        self.assertIsNotNone(
            task_block, "fixture sanity: this block genuinely carries a TASK block"
        )
        self.assertIsNone(
            declared_phase(task_block),
            "a TASK block carrying two disagreeing phase: lines is an ambiguous declaration, "
            "not a declaration of whichever line the regex happens to match first -- "
            "declared_phase must read None here, the same undeclared answer it gives a block "
            "with no phase line at all, because in both cases which phase the contract means "
            "is not something this function may guess"
        )

    def test_positive_control_a_phase_value_padded_with_spaces_on_one_line_still_reads(self):
        # Must stay green throughout: the fix for the two RED cases above must
        # narrow \s* so it never crosses a newline, not so it stops matching
        # the ordinary padding a hand-typed phase line already carries.
        # Mutation that turns it red: any fix that requires the value to sit
        # immediately after the colon with no padding at all.
        declared_phase = self._declared_phase()
        self.assertEqual(
            declared_phase("  phase: GREEN  "),
            "GREEN",
            "fixture sanity: ordinary horizontal padding around a phase value that stays on "
            "one line must still be read -- if this is not true the two RED cases above could "
            "be satisfied by an implementation that refuses every phase line, real or not"
        )

    def test_positive_control_two_identical_phase_lines_are_not_ambiguous(self):
        # Probably green today: this is the mirror of
        # test_two_conflicting_phase_lines_in_one_task_block_read_none above.
        # That case reads None because "phase: RED" and "phase: GREEN"
        # disagree -- two identical "phase: GREEN" lines carry only one
        # value between them and must still read GREEN. A mutation that
        # turns declared_phase's ambiguity check into "more than one phase:
        # line at all reads None" -- rather than "more than one DISTINCT
        # value reads None" -- would answer None here too; this case exists
        # to keep that mutation caught.
        declared_phase = self._declared_phase()
        self.assertEqual(
            declared_phase("phase: GREEN\nphase: GREEN"),
            "GREEN",
            "two identical phase: lines are not a disagreement -- declared_phase must read the "
            "one value they agree on, not treat repetition itself as ambiguity"
        )


# --------------------------------------------------------------------------
# B2 -- needs_issue's real rule (I-6), driven through main() at BOTH copies:
# --dispatch (pr_merged.py:1567) and the report path's dispatch list
# (pr_merged.py:1605). TestDispatchPacketCarriesIssueBaseAndBrief's own
# needs_issue pair only drives build_dispatch, which merely ECHOES the
# argument it is handed -- it cannot fail on the real rule,
# len(tasks) >= 2 and issue is None, which lives in main() itself, in two
# copies.
# --------------------------------------------------------------------------
CONTRACT_CLI_TWO_MERGEABLE_TASKS = """
## Implementation Handoff

### 1. Backend (`acme-dev`)

**Depends on:** none

**Files to touch:**
- src/Foo.cs

### 2. Frontend (`acme-dev`)

**Depends on:** 1

**Files to touch:**
- src/Bar.cs
"""


def _drive_dispatch_needs_issue(sub_task_entries, dispatch_id="t1-backend",
                                contract_text=CONTRACT_CLI_TWO_MERGEABLE_TASKS,
                                filename="acme-needs-issue-dispatch-fixture.md"):
    """Drive main() through --dispatch and read the printed packet's needs_issue.

    Mirrors TestMainDispatchCutsFromTheSubtasksDeclaredBase._drive_dispatch,
    but accepts the WHOLE sub_tasks state mapping (not one entry) and the
    contract text, so a two-sub-task contract can be built without adding a
    second helper class. FIXTURE RULE: every sub_task_entries mapping this
    module passes here gives every entry the SAME base, or gives none of
    them a base key at all -- sub-task 13 later refuses to dispatch an entry
    with no base beside a sibling that declares a non-default base, and a
    mixed fixture here would change meaning once that lands.
    """
    create_branch_mock = mock.MagicMock(return_value=(True, "created it"))
    with tempfile.TemporaryDirectory() as d:
        contract_path = Path(d) / filename
        contract_path.write_text(contract_text, encoding="utf-8")
        slug = contract_path.stem
        state = {
            "contract": slug,
            "started_at": "2026-09-19T00:00:00+00:00",
            "sub_tasks": sub_task_entries,
        }
        out = io.StringIO()
        argv = ["pr_merged.py", "--contract", str(contract_path),
                "--dispatch", dispatch_id, "--json"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pr_merged, "load_records", return_value={}), \
             mock.patch.object(pr_merged, "load_state", return_value=state), \
             mock.patch.object(pr_merged, "default_branch", return_value="master"), \
             mock.patch.object(pr_merged, "write_state", return_value=None), \
             mock.patch.object(pr_merged, "create_branch", create_branch_mock), \
             mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
             mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
             contextlib.redirect_stdout(out):
            pr_merged.main()
        printed = out.getvalue()
    packet = json.loads(printed) if printed.strip().startswith("{") else None
    return packet


def _drive_report_needs_issue(sub_task_entries, contract_text=CONTRACT_CLI_TWO_MERGEABLE_TASKS,
                              filename="acme-needs-issue-report-fixture.md"):
    """Drive main() through the default report path (no --dispatch, no --pr)
    and read report["dispatch"]'s needs_issue for whichever sub-task the
    plan releases.
    """
    with tempfile.TemporaryDirectory() as d:
        contract_path = Path(d) / filename
        contract_path.write_text(contract_text, encoding="utf-8")
        slug = contract_path.stem
        state = {
            "contract": slug,
            "started_at": "2026-09-19T00:00:00+00:00",
            "sub_tasks": sub_task_entries,
        }
        out = io.StringIO()
        argv = ["pr_merged.py", "--contract", str(contract_path), "--json"]
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pr_merged, "load_records", return_value={}), \
             mock.patch.object(pr_merged, "load_state", return_value=state), \
             mock.patch.object(pr_merged, "default_branch", return_value="master"), \
             mock.patch.object(pr_merged, "write_state", return_value=None), \
             mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
             mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
             contextlib.redirect_stdout(out):
            pr_merged.main()
        report = json.loads(out.getvalue())
    return report


class TestNeedsIssueAtTheDispatchCallSite(unittest.TestCase):
    """B2, pr_merged.py:1567 -- the --dispatch copy of needs_issue."""

    def test_two_subtask_contract_no_issue_recorded_needs_issue_true(self):
        packet = _drive_dispatch_needs_issue({
            "t1-backend": {"status": "pending", "branch": None, "pull_request": None,
                          "issue": None, "brief": None},
            "t2-frontend": {"status": "pending", "branch": None, "pull_request": None,
                           "issue": None, "brief": None},
        })
        self.assertIsNotNone(packet, "fixture sanity: --json dispatch must print a packet")
        self.assertTrue(
            packet.get("needs_issue"),
            "a contract orchestrating two or more mergeable sub-tasks, dispatching one that "
            "carries no recorded issue, must flag needs_issue -- main()'s own copy at "
            "pr_merged.py:1567, not build_dispatch's echo of an argument"
        )

    def test_two_subtask_contract_with_issue_recorded_needs_issue_false(self):
        packet = _drive_dispatch_needs_issue({
            "t1-backend": {"status": "pending", "branch": None, "pull_request": None,
                          "issue": 163, "brief": None},
            "t2-frontend": {"status": "pending", "branch": None, "pull_request": None,
                           "issue": None, "brief": None},
        })
        self.assertIsNotNone(packet, "fixture sanity: --json dispatch must print a packet")
        self.assertFalse(
            packet.get("needs_issue"),
            "needs_issue must be false once the dispatched sub-task's own state entry "
            "already carries a recorded issue"
        )

    def test_one_subtask_contract_no_issue_needs_issue_false(self):
        # Positive control for the "two or more" term: a lone sub-task must
        # never be flagged, however its issue field reads.
        packet = _drive_dispatch_needs_issue(
            {"t1-backend": {"status": "pending", "branch": None, "pull_request": None,
                           "issue": None, "brief": None}},
            contract_text=CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK,
        )
        self.assertIsNotNone(packet, "fixture sanity: --json dispatch must print a packet")
        self.assertFalse(
            packet.get("needs_issue"),
            "a contract with only ONE mergeable sub-task must never flag needs_issue, even "
            "with no issue recorded -- this is the positive control for the "
            "len(tasks) >= 2 term"
        )


class TestNeedsIssueAtTheReportCallSite(unittest.TestCase):
    """B2, pr_merged.py:1605 -- the report path's dispatch-list copy of needs_issue."""

    def _dispatch_entry(self, report, sub_task_id="t1-backend"):
        entries = [d for d in report.get("dispatch", []) if d.get("sub_task") == sub_task_id]
        self.assertTrue(
            entries, "fixture sanity: %r must appear in report['dispatch'] -- got %r"
                     % (sub_task_id, report.get("dispatch"))
        )
        return entries[0]

    def test_two_subtask_contract_no_issue_recorded_needs_issue_true(self):
        report = _drive_report_needs_issue({
            "t1-backend": {"status": "pending", "branch": None, "pull_request": None,
                          "issue": None, "brief": None},
            "t2-frontend": {"status": "pending", "branch": None, "pull_request": None,
                           "issue": None, "brief": None},
        })
        entry = self._dispatch_entry(report)
        self.assertTrue(
            entry.get("needs_issue"),
            "a contract orchestrating two or more mergeable sub-tasks, releasing one that "
            "carries no recorded issue, must flag needs_issue -- main()'s own copy at "
            "pr_merged.py:1605, not build_dispatch's echo of an argument"
        )

    def test_two_subtask_contract_with_issue_recorded_needs_issue_false(self):
        report = _drive_report_needs_issue({
            "t1-backend": {"status": "pending", "branch": None, "pull_request": None,
                          "issue": 163, "brief": None},
            "t2-frontend": {"status": "pending", "branch": None, "pull_request": None,
                           "issue": None, "brief": None},
        })
        entry = self._dispatch_entry(report)
        self.assertFalse(
            entry.get("needs_issue"),
            "needs_issue must be false once the released sub-task's own state entry already "
            "carries a recorded issue"
        )

    def test_one_subtask_contract_no_issue_needs_issue_false(self):
        # Positive control for the "two or more" term.
        report = _drive_report_needs_issue(
            {"t1-backend": {"status": "pending", "branch": None, "pull_request": None,
                           "issue": None, "brief": None}},
            contract_text=CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK,
        )
        entry = self._dispatch_entry(report)
        self.assertFalse(
            entry.get("needs_issue"),
            "a contract with only ONE mergeable sub-task must never flag needs_issue, even "
            "with no issue recorded -- this is the positive control for the "
            "len(tasks) >= 2 term"
        )


# --------------------------------------------------------------------------
# B4 -- reconcile_subtask_identity (I-7) had no test at all before this
# sub-task, neither a unit test of the function nor a main() case driving
# the mismatch branch.
# --------------------------------------------------------------------------
class TestReconcileSubtaskIdentity(unittest.TestCase):
    """reconcile_subtask_identity(state_entry, brief_fields) -- I-7."""

    def _get(self):
        fn = _fn("reconcile_subtask_identity")
        self.assertIsNotNone(
            fn, "pr_merged.reconcile_subtask_identity must exist -- I-7's dispatch refusal "
                "compares a state entry against its own brief before every dispatch"
        )
        return fn

    def test_an_issue_mismatch_is_reported_naming_both_readings(self):
        fn = self._get()
        result = fn({"issue": 163}, {"id": "9999"})
        self.assertIsNotNone(result, "an issue mismatch must be reported, never silently ignored")
        self.assertIn("163", result)
        self.assertIn("9999", result)

    def test_a_base_mismatch_is_reported_naming_both_readings(self):
        fn = self._get()
        result = fn({"base": "feature/160-parent"}, {"base": "some-other-branch"})
        self.assertIsNotNone(result, "a base mismatch must be reported, never silently ignored")
        self.assertIn("feature/160-parent", result)
        self.assertIn("some-other-branch", result)

    def test_agreement_on_issue_and_base_is_not_a_mismatch(self):
        fn = self._get()
        result = fn({"issue": 163, "base": "feature/160-parent"},
                   {"id": "163", "base": "feature/160-parent"})
        self.assertIsNone(result, "matching readings must never be reported as a mismatch")

    def test_a_hash_prefixed_brief_id_agrees_with_a_bare_state_entry_number(self):
        # "#5" in the brief must agree with 5 in the state entry once the '#'
        # is stripped -- a literal string comparison would wrongly report a
        # mismatch.
        fn = self._get()
        result = fn({"issue": 5}, {"id": "#5"})
        self.assertIsNone(
            result, "'#5' in the brief must agree with 5 in the state entry once the '#' is "
                    "stripped before comparing"
        )

    def test_a_key_missing_on_the_state_entry_side_is_not_a_mismatch(self):
        fn = self._get()
        result = fn({}, {"id": "163", "base": "feature/160-parent"})
        self.assertIsNone(
            result, "there is nothing to compare a state entry against before it records an "
                    "issue or a base of its own -- a missing key is not a mismatch"
        )

    def test_a_key_missing_on_the_brief_side_is_not_a_mismatch(self):
        fn = self._get()
        result = fn({"issue": 163, "base": "feature/160-parent"}, {})
        self.assertIsNone(
            result, "a brief that has not yet recorded an id or a base has nothing to compare "
                    "against either -- not itself a mismatch"
        )


class TestMainRefusesDispatchOnIdentityMismatch(unittest.TestCase):
    """I-7, B4's main() case: a state entry whose brief disagrees with it
    must refuse the dispatch rather than proceed on the stale reading.
    """

    def test_a_readable_brief_disagreeing_with_the_state_entry_refuses_the_dispatch(self):
        create_branch_mock = mock.MagicMock(return_value=(True, "created it"))
        with tempfile.TemporaryDirectory() as d:
            brief_path = Path(d) / "acme-identity-mismatch-brief.md"
            brief_path.write_text(
                "---\nid: 9999\ntitle: Something else entirely\n---\n\n# Body\n",
                encoding="utf-8",
            )
            contract_path = Path(d) / "acme-identity-mismatch-fixture.md"
            contract_path.write_text(CONTRACT_CLI_ONE_MERGEABLE_BACKEND_TASK, encoding="utf-8")
            slug = contract_path.stem
            state = {
                "contract": slug,
                "started_at": "2026-09-19T00:00:00+00:00",
                "sub_tasks": {"t1-backend": {
                    "status": "pending", "branch": None, "pull_request": None,
                    "issue": 163, "base": "feature/160-parent",
                    "brief": str(brief_path),
                }},
            }
            out = io.StringIO()
            argv = ["pr_merged.py", "--contract", str(contract_path),
                    "--dispatch", "t1-backend", "--json"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value={}), \
                 mock.patch.object(pr_merged, "load_state", return_value=state), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", return_value=None), \
                 mock.patch.object(pr_merged, "create_branch", create_branch_mock), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 contextlib.redirect_stdout(out):
                exit_code = pr_merged.main()
            printed = out.getvalue()
        payload = json.loads(printed) if printed.strip().startswith("{") else None

        self.assertEqual(
            exit_code, 5,
            "an identity mismatch between a state entry and its own brief must refuse the "
            "dispatch with exit code 5 (I-7) -- without reconcile_subtask_identity wired in, "
            "a mismatch dispatches anyway"
        )
        self.assertIsNotNone(payload, "fixture sanity: the CLI must print a JSON payload")
        self.assertEqual(payload.get("error"), "identity-mismatch")
        self.assertEqual(payload.get("sub_task"), "t1-backend")
        detail = payload.get("detail", "")
        self.assertIn("163", detail, "the refusal must name the state entry's own reading")
        self.assertIn("9999", detail, "the refusal must name the brief's own reading")
        self.assertFalse(
            create_branch_mock.called,
            "a refused dispatch must never cut a branch -- create_branch must not be called "
            "when the identity check fails"
        )


# ==========================================================================
# Contract block 12: failing tests for the loop fix.
#
# Defect one: an unfetched merge commit reads as "unreadable". Today main()
# reads the declared review artefact once at the merge commit
# (pr_merged.py:1457-1465); a commit the local clone does not hold returns
# None, exactly as a missing file does, and the loop never distinguishes the
# two. ensure_commit_local(sha, ref) -> bool is the new edge: consulted only
# when the first read yields nothing, it fetches once if the commit is
# absent and reports whether it is present afterwards. "unreadable" is kept
# for a commit the clone genuinely holds but whose artefact still can't be
# parsed; "unfetched" is new, for a commit that stays absent after the one
# fetch attempt.
# ==========================================================================
CONTRACT_CLI_MARKDOWN_OUTSIDE_REVIEWS_WITH_DEPENDENT = """
## Implementation Handoff

### 1. Docs (`acme-dev`)

**Depends on:** none

**Files to touch:**
- docs/plan.md

### 2. Backend (`acme-dev`)

**Depends on:** 1

**Files to touch:**
- src/Foo.cs
"""


def _drive_main_pr_fetch_case(contract_text, head_task_id, file_at_commit_side_effect,
                              ensure_commit_local_return=True, base_ref_name="master",
                              extra_cli_flags=("--dry-run",),
                              filename="acme-fetch-fixture.md",
                              state_base_overrides=None):
    """Drive pr_merged.main() end to end for a merged pull request, with both
    ``file_at_commit`` and the not-yet-built ``ensure_commit_local`` injected.

    Mirrors ``_drive_main_pr_report_for_verdict_bearing_dependent``
    (test_pr_merged.py:1269) exactly, except the head sub-task id, the merged
    pull request's own ``baseRefName``, the CLI flags and ``file_at_commit``'s
    sequence of readings are all the caller's to choose -- Defect One's own
    cases vary every one of those. Returns
    ``(report, fake_file_at_commit, fake_ensure_commit_local)``.

    ``state_base_overrides``, when given, is a ``{sub_task_id: base}`` mapping
    used to build a stored state ``load_state`` returns instead of ``None``.
    Without it every entry's base is the default branch (``"master"``), so a
    pull request merged into a non-default ``baseRefName`` classifies as
    merged-elsewhere and is skipped before ``file_at_commit`` or
    ``ensure_commit_local`` is ever reached -- (e) needs a declared base that
    matches its own non-default ``baseRefName`` so the merge is accepted and
    the fetch edge is actually exercised.
    """
    with tempfile.TemporaryDirectory() as d:
        contract_path = Path(d) / filename
        contract_path.write_text(contract_text, encoding="utf-8")
        slug = contract_path.stem
        branch = f"task/{slug}/{head_task_id}"
        pr = {
            "number": 42,
            "state": "MERGED",
            "mergedAt": "2026-01-01T00:00:00Z",
            "mergeCommit": {"oid": "deadbeef"},
            "headRefName": branch,
            "baseRefName": base_ref_name,
            "url": "https://example.invalid/pull/42",
            "commits": [{"oid": "deadbeef"}],
            "statusCheckRollup": None,
        }
        stored_state = None
        if state_base_overrides:
            stored_state = {
                "contract": slug,
                "started_at": "2026-01-01T00:00:00+00:00",
                "sub_tasks": {
                    tid: {"status": "pending", "branch": None, "pull_request": None,
                         "issue": None, "base": base, "brief": None}
                    for tid, base in state_base_overrides.items()
                },
            }
        fake_file_at_commit = mock.MagicMock(side_effect=list(file_at_commit_side_effect))
        fake_ensure_commit_local = mock.MagicMock(return_value=ensure_commit_local_return)
        out = io.StringIO()
        argv = (["pr_merged.py", "--contract", str(contract_path),
                "--pr", "42", "--json"] + list(extra_cli_flags))
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(pr_merged, "load_records", return_value={}), \
             mock.patch.object(pr_merged, "load_state", return_value=stored_state), \
             mock.patch.object(pr_merged, "default_branch", return_value="master"), \
             mock.patch.object(pr_merged, "write_state", return_value=None), \
             mock.patch.object(pr_merged, "write_record", return_value=None), \
             mock.patch.object(pr_merged, "gh_pr", side_effect=lambda n: pr if n == 42 else None), \
             mock.patch.object(pr_merged, "git_combined_diff", return_value=([], 1)), \
             mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
             mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
             mock.patch.object(pr_merged, "file_at_commit", fake_file_at_commit, create=True), \
             mock.patch.object(pr_merged, "ensure_commit_local", fake_ensure_commit_local,
                               create=True), \
             contextlib.redirect_stdout(out):
            pr_merged.main()
        report = json.loads(out.getvalue())
    return report, fake_file_at_commit, fake_ensure_commit_local


class TestMainFetchesAnAbsentMergeCommitBeforeNamingUnreadable(unittest.TestCase):
    """Contract block 12, Defect One. Every case except (f) drives main()
    through --pr for t1-review, a verdict-bearing sub-task, with t2-backend
    depending on it -- ``CONTRACT_CLI_VERDICT_BEARING_WITH_DEPENDENT``, the
    same fixture ``TestMainNamesAnUnreadableVerdictAndWithholdsRelease``
    already uses.
    """

    def test_a_commit_fetched_successfully_then_read_reports_the_retried_verdict(self):
        # (a) -- the 2026-09-25 case exactly.
        report, _fake_file_at_commit, _fake_ensure_commit_local = _drive_main_pr_fetch_case(
            CONTRACT_CLI_VERDICT_BEARING_WITH_DEPENDENT, "t1-review",
            [None, "**Verdict:** blocked\n\n## What was checked\n- x: ok\n"],
            ensure_commit_local_return=True,
        )
        closed = report.get("closed", [])
        self.assertTrue(closed, "fixture sanity: the merged pull request must close t1-review")
        self.assertEqual(
            closed[0]["record"].get("review_verdict"), "blocked",
            "an absent artefact read whose commit ensure_commit_local reports present after "
            "fetching must be RE-READ, and the retried read's verdict is what gets stamped -- "
            "today main() reads the artefact exactly once and stamps 'unreadable' on the "
            "first empty read, so a commit that never even needed a network fetch is "
            "misdiagnosed as an unreadable artefact"
        )

    def test_a_commit_still_absent_after_a_failed_fetch_is_named_unfetched(self):
        # (b)
        report, _fake_file_at_commit, _fake_ensure_commit_local = _drive_main_pr_fetch_case(
            CONTRACT_CLI_VERDICT_BEARING_WITH_DEPENDENT, "t1-review",
            [None],
            ensure_commit_local_return=False,
        )
        closed = report.get("closed", [])
        self.assertTrue(closed, "fixture sanity: the merged pull request must close t1-review")
        self.assertEqual(
            closed[0]["record"].get("review_verdict"), "unfetched",
            "a commit ensure_commit_local reports still absent after attempting a fetch must "
            "be named 'unfetched', a distinct ReviewVerdictReading from 'unreadable' -- today "
            "there is no such reading at all, and every empty read stamps 'unreadable' whether "
            "or not the commit could ever have been fetched"
        )
        self.assertNotIn(
            "t2-backend", report.get("released", []),
            "an unfetched review verdict must not release what depends on it, exactly like an "
            "unreadable one"
        )
        blocked = report.get("blocked", {})
        self.assertTrue(
            any("(review verdict: unfetched)" in reason
                for reason in blocked.get("t2-backend", [])),
            "the blocked reason must name the unfetched reading so an operator knows the "
            "remedy is a fetch, not a rewrite of the artefact -- got %r"
            % blocked.get("t2-backend")
        )

    def test_a_commit_present_but_still_empty_after_fetch_is_unreadable_not_unfetched(self):
        # (c) -- pairs with (b); also proves ensure_commit_local is consulted
        # exactly once, never once per retried read.
        report, _fake_file_at_commit, fake_ensure_commit_local = _drive_main_pr_fetch_case(
            CONTRACT_CLI_VERDICT_BEARING_WITH_DEPENDENT, "t1-review",
            [None, None],
            ensure_commit_local_return=True,
        )
        closed = report.get("closed", [])
        self.assertTrue(closed, "fixture sanity: the merged pull request must close t1-review")
        self.assertEqual(
            closed[0]["record"].get("review_verdict"), "unreadable",
            "a commit ensure_commit_local reports present, whose re-read still yields "
            "nothing, is 'unreadable' -- the artefact really is absent or malformed at a "
            "commit the clone holds -- and must never be confused with 'unfetched'"
        )
        self.assertEqual(
            fake_ensure_commit_local.call_count, 1,
            "ensure_commit_local must be consulted exactly once per empty read -- without "
            "this assertion this case passes on today's code, which already stamps "
            "'unreadable' for an empty read and never calls ensure_commit_local at all"
        )

    def test_positive_control_a_first_read_pass_never_consults_ensure_commit_local(self):
        # (d)
        report, _fake_file_at_commit, fake_ensure_commit_local = _drive_main_pr_fetch_case(
            CONTRACT_CLI_VERDICT_BEARING_WITH_DEPENDENT, "t1-review",
            ["**Verdict:** pass\n\n## What was checked\n- x: ok\n"],
        )
        closed = report.get("closed", [])
        self.assertTrue(closed, "fixture sanity: the merged pull request must close t1-review")
        self.assertEqual(closed[0]["record"].get("review_verdict"), "pass")
        self.assertIn("t2-backend", report.get("released", []))
        self.assertFalse(
            fake_ensure_commit_local.called,
            "a first read that already yields text must never consult ensure_commit_local -- "
            "a fix that fetches on every merge, not only an empty read, must fail this control"
        )

    def test_ensure_commit_local_receives_the_pull_requests_own_base_ref_not_the_default(self):
        # (e). The pull request merges into "feature/160-parent", a
        # non-default branch -- the stored state must declare that same
        # base for t1-review, or classify_pr reports merged-elsewhere and
        # the pull request is skipped before file_at_commit or
        # ensure_commit_local is ever reached.
        report, _fake_file_at_commit, fake_ensure_commit_local = _drive_main_pr_fetch_case(
            CONTRACT_CLI_VERDICT_BEARING_WITH_DEPENDENT, "t1-review",
            [None, "**Verdict:** pass\n"],
            ensure_commit_local_return=True,
            base_ref_name="feature/160-parent",
            state_base_overrides={"t1-review": "feature/160-parent"},
        )
        self.assertTrue(
            report.get("closed"),
            "fixture sanity: a pull request merged into the sub-task's own declared base "
            "must close it -- otherwise this case never reaches file_at_commit or "
            "ensure_commit_local at all, and the assertions below would be measuring nothing"
        )
        self.assertTrue(
            fake_ensure_commit_local.called,
            "an empty first read must consult ensure_commit_local"
        )
        fake_ensure_commit_local.assert_called_with("deadbeef", "feature/160-parent")

    def test_a_non_review_artefact_never_consults_ensure_commit_local(self):
        # (f) -- POSITIVE CONTROL. A declared markdown file OUTSIDE
        # .claude/reviews/, so this also fails a fix that widens the
        # verdict-bearing rule to any markdown file.
        report, fake_file_at_commit, fake_ensure_commit_local = _drive_main_pr_fetch_case(
            CONTRACT_CLI_MARKDOWN_OUTSIDE_REVIEWS_WITH_DEPENDENT, "t1-docs",
            [None],
            ensure_commit_local_return=True,
        )
        self.assertTrue(
            report.get("closed"), "fixture sanity: the merged pull request must close t1-docs"
        )
        self.assertFalse(
            fake_file_at_commit.called,
            "fixture sanity: t1-docs declares no path under .claude/reviews/, so nothing is "
            "verdict-bearing and file_at_commit must never be called for it"
        )
        self.assertFalse(
            fake_ensure_commit_local.called,
            "a merge whose sub-task declares no .claude/reviews/ artefact must never consult "
            "ensure_commit_local -- a declared markdown file outside .claude/reviews/ must "
            "not be enough to trigger it either"
        )

    def test_ensure_commit_local_is_consulted_under_dry_run(self):
        # (g), --dry-run half.
        _report, _fake_file_at_commit, fake_ensure_commit_local = _drive_main_pr_fetch_case(
            CONTRACT_CLI_VERDICT_BEARING_WITH_DEPENDENT, "t1-review",
            [None, "**Verdict:** pass\n"],
            ensure_commit_local_return=True,
            extra_cli_flags=("--dry-run",),
        )
        self.assertTrue(
            fake_ensure_commit_local.called,
            "Open Question 4 was answered yes on 2026-09-25: the fetch runs in every mode, "
            "including --dry-run, because a dry run must preview what the real run would do"
        )

    def test_ensure_commit_local_is_consulted_under_status(self):
        # (g), --status half.
        _report, _fake_file_at_commit, fake_ensure_commit_local = _drive_main_pr_fetch_case(
            CONTRACT_CLI_VERDICT_BEARING_WITH_DEPENDENT, "t1-review",
            [None, "**Verdict:** pass\n"],
            ensure_commit_local_return=True,
            extra_cli_flags=("--status",),
        )
        self.assertTrue(
            fake_ensure_commit_local.called,
            "the fetch must also run under --status -- a read-only report that silently "
            "skips the fetch would misreport what the real run reads"
        )


class TestEnsureCommitLocal(unittest.TestCase):
    """ensure_commit_local(sha, ref) -> bool -- Defect One's own edge, over a
    patched ``pr_merged._run``. No real git process is ever started.
    """

    def _get(self):
        fn = _fn("ensure_commit_local")
        self.assertIsNotNone(
            fn, "pr_merged.ensure_commit_local must exist -- Defect One's fetch-then-recheck "
                "edge that tells an unfetched merge commit apart from a genuinely unreadable "
                "artefact"
        )
        return fn

    def test_a_commit_already_present_runs_no_fetch(self):
        fn = self._get()
        commands = []

        def fake_run(cmd):
            commands.append(list(cmd))
            return (0, "deadbeef")

        with mock.patch.object(pr_merged, "_run", fake_run):
            result = fn("deadbeef", "master")

        self.assertTrue(result, "a commit already present locally must report True")
        self.assertFalse(
            any("fetch" in c for c in commands),
            "a commit already present must never trigger a fetch -- got %r" % commands
        )

    def test_an_absent_commit_runs_exactly_one_fetch_and_checks_again(self):
        # W2: the responses are keyed strictly by call ORDER (first call =
        # the presence check, second = the fetch, third = the re-check), so
        # the assertions below must pin the exact command SEQUENCE -- not
        # merely that a fetch happened and True came back. An implementation
        # that treats the fetch's own exit code as "the commit is now
        # present" and never re-checks would make only two calls and still
        # report True; asserting the full three-call shape is what catches
        # that shortcut.
        fn = self._get()
        commands = []
        responses = iter([(1, ""), (0, ""), (0, "deadbeef")])

        def fake_run(cmd):
            commands.append(list(cmd))
            return next(responses)

        with mock.patch.object(pr_merged, "_run", fake_run):
            result = fn("deadbeef", "master")

        self.assertTrue(
            result, "once the fetch succeeds and the commit checks present, "
                    "ensure_commit_local must report True"
        )
        self.assertEqual(
            len(commands), 3,
            "ensure_commit_local must run exactly three commands for an absent commit whose "
            "fetch succeeds: a presence check, the fetch, then a SECOND presence check -- an "
            "implementation that returns the fetch's own exit code instead of re-checking "
            "would stop at two commands and still report True. Got %r" % commands
        )
        self.assertNotIn(
            "fetch", commands[0],
            "the first command must be a presence check, not the fetch itself -- got %r"
            % commands[0]
        )
        self.assertEqual(
            commands[1], ["git", "fetch", "origin", "master"],
            "the second command must be exactly one 'git fetch origin <ref>' -- got %r"
            % commands
        )
        self.assertEqual(
            commands[2], commands[0],
            "the third command must be the SAME presence check re-run after the fetch, not a "
            "different query -- got %r" % commands
        )

    def test_a_successful_fetch_whose_recheck_still_reports_absent_returns_false(self):
        # New case, added after review: a fetch that itself succeeds is not
        # the same claim as the commit being present afterwards -- for
        # example a fetch of a tag or a shallow history that never actually
        # brought the merge commit down. Without this case, an
        # implementation that returns True on any fetch exit code 0, with no
        # real re-check, would still pass every other test here.
        fn = self._get()
        commands = []
        responses = iter([(1, ""), (0, ""), (1, "")])

        def fake_run(cmd):
            commands.append(list(cmd))
            return next(responses)

        with mock.patch.object(pr_merged, "_run", fake_run):
            result = fn("deadbeef", "master")

        self.assertFalse(
            result, "a fetch that succeeds but whose re-check still reports the commit "
                    "absent must report False -- a successful fetch is not itself proof the "
                    "commit is now present"
        )

    def test_a_failed_fetch_returns_false(self):
        # W1: the fake answers by COMMAND rather than by call count, so an
        # implementation that re-checks presence even after a failed fetch
        # (a defensible choice the TASK block does not forbid) gets a
        # consistent "still absent" / "fetch fails" answer for as many calls
        # as it makes, instead of raising StopIteration on a third call this
        # test did not originally anticipate.
        fn = self._get()
        commands = []

        def fake_run(cmd):
            commands.append(list(cmd))
            if "fetch" in cmd:
                return (1, "")  # the fetch itself fails
            return (1, "")  # every presence check reports the commit absent

        with mock.patch.object(pr_merged, "_run", fake_run):
            result = fn("deadbeef", "master")

        self.assertFalse(result, "a fetch that itself fails must report False, never True")
        fetch_calls = [c for c in commands if "fetch" in c]
        self.assertEqual(
            len(fetch_calls), 1,
            "a failed fetch must still have been attempted exactly once -- got %r" % commands
        )


# ==========================================================================
# Contract block 12, Defect Two: sub-tasks appended by an amendment cannot
# be recorded. main() loads the stored state and never adds a planned
# sub-task the stored state lacks, so --record-subtask refuses an id
# /flow's sub-issue step has already opened on GitHub.
# backfill_state(state, tasks) -> state is the new pure function: it adds a
# pending entry, in new_state's own shape, for every planned id the stored
# state lacks, with base explicitly None -- never the repository default
# branch. It never removes an entry and never rewrites an existing one.
# ==========================================================================
class TestBackfillStateAddsMissingPlannedEntries(unittest.TestCase):
    def _get(self):
        fn = _fn("backfill_state")
        self.assertIsNotNone(
            fn, "pr_merged.backfill_state must exist -- Defect Two: a sub-task appended to a "
                "contract whose state store already exists is never added, so "
                "--record-subtask refuses an id /flow's sub-issue step has already opened on "
                "GitHub"
        )
        return fn

    def test_a_missing_planned_id_is_added_as_a_pending_entry_with_base_none(self):
        fn = self._get()
        state = {
            "contract": "c-slug", "started_at": "2026-09-25T00:00:00+00:00",
            "sub_tasks": {
                "t1-a": {"status": "completed", "branch": "task/c-slug/t1-a",
                         "pull_request": "u1", "issue": 163, "base": "feature/x",
                         "brief": ".claude/work-items/x.md"},
                "t2-b": {"status": "pending", "branch": None, "pull_request": None},
            },
        }
        result = fn(state, _tasks())

        self.assertIn(
            "t3-c", result["sub_tasks"],
            "backfill_state must add an entry for every planned id the stored state lacks -- "
            "today nothing in main() ever adds one"
        )
        entry = result["sub_tasks"]["t3-c"]
        self.assertEqual(
            set(entry.keys()), {"status", "branch", "pull_request", "issue", "base", "brief"},
            "a backfilled entry must carry new_state's own six keys, no more and no fewer"
        )
        self.assertEqual(entry["status"], "pending")
        self.assertIsNone(entry["branch"])
        self.assertIsNone(entry["pull_request"])
        self.assertIsNone(entry["issue"])
        self.assertIn(
            "base", entry,
            "the backfilled entry must carry a base key explicitly, not merely omit one"
        )
        self.assertIsNone(
            entry["base"],
            "a backfilled entry's base must be null, never the repository default branch -- "
            "the only base main() holds at this point is default_branch(), and stamping it "
            "here would silently cut the sub-task from master even where every sibling in "
            "this same contract carries a declared parent branch"
        )
        self.assertIsNone(entry["brief"])

        self.assertEqual(
            result["sub_tasks"]["t1-a"], state["sub_tasks"]["t1-a"],
            "an existing completed entry -- issue, base and brief included -- must survive "
            "backfill_state byte-identical; it adds, it never rewrites"
        )
        self.assertEqual(
            result["sub_tasks"]["t2-b"], state["sub_tasks"]["t2-b"],
            "an existing entry with no base key at all must be left exactly as it was -- "
            "backfill_state must never invent a base for an entry that already exists"
        )
        self.assertNotIn(
            "base", result["sub_tasks"]["t2-b"],
            "backfill_state must never add a base key to an existing entry that never had one"
        )

    def test_an_entry_no_longer_planned_is_never_removed(self):
        fn = self._get()
        state = {
            "contract": "c-slug", "started_at": "2026-09-25T00:00:00+00:00",
            "sub_tasks": {
                "t1-a": {"status": "pending", "branch": None, "pull_request": None,
                         "issue": None, "base": "master", "brief": None},
                "t9-ghost": {"status": "pending", "branch": None, "pull_request": None,
                             "issue": None, "base": "master", "brief": None},
            },
        }
        result = fn(state, [_tasks()[0]])
        self.assertIn(
            "t9-ghost", result["sub_tasks"],
            "backfill_state must never remove an entry whose id the plan no longer contains "
            "-- it only ever adds"
        )


class TestMainRecordSubtaskAfterBackfill(unittest.TestCase):
    """Defect Two, main() case (k): a sub-task appended to the contract after
    its state store was first written is invisible to --record-subtask
    until backfill_state runs right after loading. (l) is the required
    positive control.
    """

    def _drive(self, subtask_id, filename="acme-backfill-record-fixture.md"):
        write_state_mock = mock.MagicMock(return_value=None)
        with tempfile.TemporaryDirectory() as d:
            contract_path = Path(d) / filename
            contract_path.write_text(CONTRACT_CLI_TWO_MERGEABLE_TASKS, encoding="utf-8")
            slug = contract_path.stem
            state = {
                "contract": slug,
                "started_at": "2026-09-25T00:00:00+00:00",
                # t2-frontend was appended by an amendment after this state store was
                # first written and is entirely absent -- the amendment scenario
                # Defect Two names.
                "sub_tasks": {"t1-backend": {"status": "pending", "branch": None,
                                             "pull_request": None, "issue": 100,
                                             "base": "master", "brief": None}},
            }
            out = io.StringIO()
            argv = ["pr_merged.py", "--contract", str(contract_path),
                    "--record-subtask", subtask_id, "--issue", "200",
                    "--base", "feature/x", "--brief", ".claude/work-items/t2.md", "--json"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value={}), \
                 mock.patch.object(pr_merged, "load_state", return_value=state), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", write_state_mock), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 contextlib.redirect_stdout(out):
                exit_code = pr_merged.main()
            printed = out.getvalue()
        payload = json.loads(printed) if printed.strip().startswith("{") else None
        return exit_code, payload, write_state_mock

    def test_a_planned_id_missing_from_stored_state_is_now_recorded(self):
        # (k)
        exit_code, payload, write_state_mock = self._drive("t2-frontend")
        self.assertEqual(
            exit_code, 0,
            "a sub-task the plan already declares, appended after the state store was first "
            "written, must be recordable through --record-subtask -- today main() never adds "
            "the missing entry, so this refuses unknown-sub-task even though /flow's "
            "sub-issue step already opened the sub-issue on GitHub"
        )
        self.assertIsNotNone(payload, "fixture sanity: the CLI must print a JSON payload")
        self.assertEqual(payload.get("recorded"), "t2-frontend")
        self.assertTrue(write_state_mock.called)

    def test_positive_control_an_id_outside_the_plan_is_still_refused(self):
        # (l)
        exit_code, payload, write_state_mock = self._drive("t9-does-not-exist")
        self.assertEqual(
            exit_code, 2,
            "backfilling every PLANNED id must never widen --record-subtask to accept an id "
            "the plan itself does not declare"
        )
        self.assertEqual(payload.get("error"), "unknown-sub-task")
        self.assertFalse(write_state_mock.called)


class TestMainStatusReportsABackfilledIdWithoutWritingIt(unittest.TestCase):
    """Defect Two, main() case (m). The in-memory backfill must appear in
    the report's own state object even though nothing is written to disk
    under --status.
    """

    def test_a_planned_id_missing_from_stored_state_appears_in_the_reports_state(self):
        write_state_mock = mock.MagicMock(return_value=None)
        with tempfile.TemporaryDirectory() as d:
            contract_path = Path(d) / "acme-backfill-status-fixture.md"
            contract_path.write_text(CONTRACT_CLI_TWO_MERGEABLE_TASKS, encoding="utf-8")
            slug = contract_path.stem
            state = {
                "contract": slug,
                "started_at": "2026-09-25T00:00:00+00:00",
                "sub_tasks": {"t1-backend": {"status": "pending", "branch": None,
                                             "pull_request": None, "issue": 100,
                                             "base": "master", "brief": None}},
            }
            out = io.StringIO()
            argv = ["pr_merged.py", "--contract", str(contract_path), "--status", "--json"]
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value={}), \
                 mock.patch.object(pr_merged, "load_state", return_value=state), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", write_state_mock), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 contextlib.redirect_stdout(out):
                pr_merged.main()
            report = json.loads(out.getvalue())

        self.assertIn(
            "t2-frontend", report.get("state", {}).get("sub_tasks", {}),
            "the report's own state object must list every PLANNED sub-task, not only the "
            "ones the stored state already had on disk -- this is the in-memory backfill "
            "main() must apply right after loading. Asserting only on report['sub_tasks'] "
            "(the plan list, always complete) would pass today and prove nothing"
        )
        self.assertFalse(
            write_state_mock.called,
            "--status must never write the backfilled state to disk -- the backfill is "
            "in-memory only, exactly like every other read-only path"
        )


# ==========================================================================
# Contract block 12, Defect Two, second half (added 2026-09-25, third pass):
# an entry with no base is cut from the default branch. backfill_state
# writes base: null for an entry it adds, and the same fallback reaches an
# entry that already exists with no base key -- sub-task 10's own position.
# base_not_declared(state, subtask_id, default_base) -> Optional[str] is the
# new --dispatch refusal: it fires only when the dispatched entry has no
# base AND at least one OTHER entry in the same state declares a non-default
# base -- I-8 stays intact for every state where no entry declares one.
# ==========================================================================
class TestMainDispatchRefusesWhenTheDispatchedEntryDeclaresNoBase(unittest.TestCase):
    """Every case drives --dispatch over CONTRACT_CLI_TWO_MERGEABLE_TASKS
    (t1-backend, depends on none; t2-frontend, depends on 1), with
    advance() releasing t2-frontend through a completed, github-verified
    t1-backend record.
    """

    def _drive(self, sub_task_entries, dispatch_id="t2-frontend", extra_flags=(),
              filename="acme-base-not-declared-fixture.md"):
        create_branch_mock = mock.MagicMock(return_value=(True, "created it"))
        write_state_mock = mock.MagicMock(return_value=None)
        with tempfile.TemporaryDirectory() as d:
            contract_path = Path(d) / filename
            contract_path.write_text(CONTRACT_CLI_TWO_MERGEABLE_TASKS, encoding="utf-8")
            slug = contract_path.stem
            state = {
                "contract": slug,
                "started_at": "2026-09-25T00:00:00+00:00",
                "sub_tasks": sub_task_entries,
            }
            records = {"t1-backend": {"status": "completed", "verified": "github",
                                      "pull_request": "u1"}}
            out = io.StringIO()
            argv = (["pr_merged.py", "--contract", str(contract_path),
                    "--dispatch", dispatch_id, "--json"] + list(extra_flags))
            with mock.patch.object(sys, "argv", argv), \
                 mock.patch.object(pr_merged, "load_records", return_value=records), \
                 mock.patch.object(pr_merged, "load_state", return_value=state), \
                 mock.patch.object(pr_merged, "default_branch", return_value="master"), \
                 mock.patch.object(pr_merged, "write_state", write_state_mock), \
                 mock.patch.object(pr_merged, "create_branch", create_branch_mock), \
                 mock.patch.object(pr_merged, "IMPLEMENTER_AGENTS", ("acme-dev",)), \
                 mock.patch.object(pr_merged, "REVIEW_GATES", ("acme-reviewer",)), \
                 contextlib.redirect_stdout(out):
                exit_code = pr_merged.main()
            printed = out.getvalue()
        payload = json.loads(printed) if printed.strip().startswith("{") else None
        return exit_code, payload, create_branch_mock, write_state_mock

    def test_a_backfilled_entry_with_no_base_beside_a_declared_parent_base_is_refused(self):
        # (n) -- the exact 2026-09-25 scenario: t2-frontend is entirely
        # absent from the stored state and only reaches --dispatch through
        # backfill_state's own base: null.
        exit_code, payload, create_branch_mock, write_state_mock = self._drive({
            "t1-backend": {"status": "completed", "branch": "task/x/t1-backend",
                          "pull_request": "u1", "issue": 163, "base": "feature/x",
                          "brief": None},
        })
        self.assertEqual(
            exit_code, 7,
            "dispatching a sub-task whose entry declares no base, beside another entry in "
            "the same state that declares a non-default base, must refuse with exit code 7 "
            "-- today this falls back to default_branch() and cuts from master silently"
        )
        self.assertIsNotNone(payload, "fixture sanity: the CLI must print a JSON payload")
        self.assertEqual(payload.get("error"), "base-not-declared")
        self.assertEqual(payload.get("sub_task"), "t2-frontend")
        self.assertIn(
            "feature/x", payload.get("detail", ""),
            "the refusal must name the other base already on record so the remedy is obvious"
        )
        self.assertFalse(create_branch_mock.called)
        self.assertFalse(write_state_mock.called)

    def test_an_existing_entry_with_no_base_key_beside_a_declared_parent_base_is_refused(self):
        # (o) -- sub-task 10's position today: the entry EXISTS but never
        # had a base key at all, rather than being added by backfill_state.
        exit_code, payload, create_branch_mock, write_state_mock = self._drive({
            "t1-backend": {"status": "completed", "branch": "task/x/t1-backend",
                          "pull_request": "u1", "issue": 163, "base": "feature/x",
                          "brief": None},
            "t2-frontend": {"status": "pending", "branch": None, "pull_request": None,
                           "issue": None, "brief": None},
        })
        self.assertEqual(exit_code, 7)
        self.assertEqual(payload.get("error"), "base-not-declared")
        self.assertEqual(payload.get("sub_task"), "t2-frontend")
        self.assertIn("feature/x", payload.get("detail", ""))
        self.assertFalse(create_branch_mock.called)
        self.assertFalse(write_state_mock.called)

    def test_positive_control_a_declared_base_dispatches_normally(self):
        # (p)
        exit_code, _payload, create_branch_mock, _write_state_mock = self._drive({
            "t1-backend": {"status": "completed", "branch": "task/x/t1-backend",
                          "pull_request": "u1", "issue": 163, "base": "feature/x",
                          "brief": None},
            "t2-frontend": {"status": "pending", "branch": None, "pull_request": None,
                           "issue": None, "base": "feature/x", "brief": None},
        })
        self.assertEqual(
            exit_code, 0,
            "a dispatched entry that DOES declare its own base must never be refused, "
            "whatever its siblings declare"
        )
        self.assertTrue(create_branch_mock.called)
        self.assertEqual(create_branch_mock.call_args[0][1], "feature/x")

    def test_positive_control_i8_neither_entry_declares_a_base(self):
        # (q) -- pinned 2026-09-25, fourth pass: neither entry carries a
        # base key at all, not "both with the default branch" -- that
        # variant cannot catch a refusal widened to fire on every missing
        # base.
        exit_code, _payload, create_branch_mock, _write_state_mock = self._drive({
            "t1-backend": {"status": "completed", "branch": "task/x/t1-backend",
                          "pull_request": "u1", "issue": 163, "brief": None},
            "t2-frontend": {"status": "pending", "branch": None, "pull_request": None,
                           "issue": None, "brief": None},
        })
        self.assertEqual(
            exit_code, 0,
            "I-8: a state where no entry declares a non-default base must dispatch exactly "
            "as today -- a refusal that fires on every missing base, not only one "
            "contradicted by a sibling, fails this control"
        )
        self.assertTrue(create_branch_mock.called)
        self.assertEqual(create_branch_mock.call_args[0][1], "master")

    def test_the_refusal_holds_under_dry_run(self):
        # (r)
        exit_code, payload, create_branch_mock, _write_state_mock = self._drive(
            {
                "t1-backend": {"status": "completed", "branch": "task/x/t1-backend",
                              "pull_request": "u1", "issue": 163, "base": "feature/x",
                              "brief": None},
                "t2-frontend": {"status": "pending", "branch": None, "pull_request": None,
                               "issue": None, "brief": None},
            },
            extra_flags=["--dry-run"],
        )
        self.assertEqual(
            exit_code, 7,
            "the refusal must hold under --dry-run too, before the identity check and before "
            "any branch is cut -- a dry run must preview the real run, not silently succeed"
        )
        self.assertEqual(payload.get("error"), "base-not-declared")
        self.assertFalse(create_branch_mock.called)


class TestBaseNotDeclared(unittest.TestCase):
    """base_not_declared(state, subtask_id, default_base) -> Optional[str],
    as a pure function -- every branch (s).
    """

    def _get(self):
        fn = _fn("base_not_declared")
        self.assertIsNotNone(
            fn, "pr_merged.base_not_declared must exist -- the --dispatch refusal that stops "
                "an entry with no declared base from being silently cut from the default "
                "branch beside a sibling that declares a real parent"
        )
        return fn

    def test_a_missing_base_key_on_the_subject_counts_as_no_base(self):
        fn = self._get()
        state = {"sub_tasks": {"t1-backend": {}, "t2-frontend": {"base": "feature/x"}}}
        self.assertIsNotNone(fn(state, "t1-backend", "master"))

    def test_a_null_base_on_the_subject_counts_as_no_base(self):
        fn = self._get()
        state = {"sub_tasks": {"t1-backend": {"base": None},
                               "t2-frontend": {"base": "feature/x"}}}
        self.assertIsNotNone(fn(state, "t1-backend", "master"))

    def test_an_other_entry_carrying_exactly_the_default_base_does_not_trigger(self):
        fn = self._get()
        state = {"sub_tasks": {"t1-backend": {}, "t2-frontend": {"base": "master"}}}
        self.assertIsNone(
            fn(state, "t1-backend", "master"),
            "an other entry whose base IS the default branch is not the contradiction this "
            "refusal exists for -- I-8 must stay intact"
        )

    def test_the_subjects_own_entry_is_never_counted_as_the_other(self):
        fn = self._get()
        state = {"sub_tasks": {"t1-backend": {}}}
        self.assertIsNone(
            fn(state, "t1-backend", "master"),
            "with no OTHER entry in the state, nothing can contradict the subject's own "
            "missing base, however that entry itself reads"
        )

    def test_an_id_absent_from_the_state_entirely_counts_as_no_base(self):
        fn = self._get()
        state = {"sub_tasks": {"t2-frontend": {"base": "feature/x"}}}
        self.assertIsNotNone(fn(state, "t1-backend", "master"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
