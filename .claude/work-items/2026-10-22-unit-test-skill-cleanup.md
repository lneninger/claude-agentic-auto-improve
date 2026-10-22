---
id: none
issue_offer: pending
title: Move the unit-tester agent's responsibilities into a skill with guaranteed temp-resource cleanup
type: IMPROVEMENT
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/unit-test-skill-cleanup
worktree: .claude/worktrees/20261022-improvement-unit-tester-skill-cleanup
north_stars: none
contract: none
pr: none
status: clarified
created: 2026-10-22
---

# Move the unit-tester agent's responsibilities into a skill with guaranteed temp-resource cleanup

## Problem statement
The `senior-test-engineer` agent carries all test-writing conventions inline and says nothing about
resources a test run creates (disposable databases, temp folders, processes). Leftovers can survive a failed run.
The user wants the responsibilities in a skill, every created resource dropped after the run (pass or fail),
and a detailed report of the results rather than a list of the temporary resources.

## Acceptance criteria
- [ ] A skill `unit-testing` exists and holds the conventions, the RED workflow, the cleanup rule and the report format.
- [ ] The agent defers to that skill and keeps only its role boundary (tests only, never production code).
- [ ] The skill requires every resource created for a run to be removed in all outcomes (success, failure, abort), and to run the removal before reporting.
- [ ] The skill never lets the report list temp resources; it requires a detailed result report (tests, outcomes, failure output, reason RED).
- [ ] Plugin version bumped in all five places; version check passes.

## Out of scope
- Changing `tdd-first`, other agents, hooks or scripts.

## Open questions from intake
- "unit tester agent" means `senior-test-engineer` (the only test-writing agent) → **Answer:** assumed.
- Cleanup scope covers only resources the run itself created, never pre-existing ones → **Answer:** assumed (safety: matches the destructive-DB doctrine).

## Size
S — two markdown files plus version bump, no data shape.

## Routing
trivial → direct implementer (markdown only; gate allowlist)
