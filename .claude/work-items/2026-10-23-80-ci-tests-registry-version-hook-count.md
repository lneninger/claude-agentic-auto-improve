---
id: 80
issue_offer: pending
title: Follow-ups from the registries version-gap fix: run tests in CI, document the version raise in registry flows, fix the README hook count
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/80
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/80-ci-tests-registry-version-hook-count
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261023-infra-80-ci-tests-registry-version-hook-count
north_stars: none
contract: none
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/115
issue_link: closes
status: shipped
created: 2026-10-23
---

# Follow-ups from the registries version-gap fix

Raw invocation: `https://github.com/lneninger/claude-agentic-auto-improve/issues/80`

## Problem statement
Three small gaps were left after the registries version-gap fix (issue 77, pull request 78). (1) Nothing runs the unit tests on GitHub, so the guard test added in pull request 78 only bites when someone runs the suite by hand. (2) Three flows append to the registry files without saying that such an append needs a plugin version raise. (3) The README says "12 hooks" but the plugin declares more.

## Acceptance criteria
- [ ] A CI step runs the chosen tests, and the guard test from pull request 78 is among them.
- [ ] Each of the three flows (`agents/fullstack-code-reviewer.md` registry janitor duties, `skills/journal-add/SKILL.md`, the journal entries in `skills/design-first/SKILL.md`) names the version-raise rule in one sentence, with identical wording.
- [ ] The README hook count matches the hooks `.claude/hooks/hooks.json` really declares, and a test keeps it from drifting again.
- [ ] The plugin version is raised once for the whole change, in all five manifest places.

## Out of scope
- Changing the version-bump rule itself (settled in pull request 78).
- `.claude/orchestrator/state/`, which stays non-exempt by design.
- Reworking `test_skill_script_lookup.py` to run faster.

## Known context
- Parent / epic: none
- Related items: issue 77, pull request 78 (guard test), pull request 75 (exempt record folders)
- Verified at intake: `hooks.json` holds 14 command entries (SessionStart 1, PreToolUse 8, PostToolUse 1, UserPromptSubmit 2, Stop 2). README line 113 already says "fourteen hooks"; line 356 (the provider table) says "12 hooks" and is the stale one. CORRECTED during review: both Claude manifest descriptions said "17 enforcement hooks" (fixed to 14), and README line 424 said "12 generic hooks" (fixed). The README counts two measures that are both 14 today: hook files (non-underscore .py in .claude/hooks minus gate-launch.py) and registrations (hooks.json command entries); the test checks each separately. Agent count (14) and skill count (28) match the README.
- Master is at version 0.9.18; no open pull requests, so no version collision. Target 0.9.19 (patch).
- Affected areas (best guess): `.github/workflows/`, `agents/fullstack-code-reviewer.md`, `skills/journal-add/SKILL.md`, `skills/design-first/SKILL.md`, `README.md`, `.claude/scripts/tests/`, five manifest places.

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- Which tests run in CI? → **Answer (assumption):** a fast, named subset that includes the pull request 78 guard test and the version-bump tests, not the full suite, because `test_skill_script_lookup.py` alone takes three to four minutes. The implementer measures run time and records the choice in the workflow.
- Contract needed? → **Answer (assumption):** no. No new data shape or mechanism: a workflow step, one sentence in three docs, one number in the README, one drift test. Same sizing as the earlier version-check chore. If the contract gate blocks an edit, the run escalates to /design-first.
- Version bump size? → **Answer (assumption):** one patch, 0.9.19. Shipped skills and agents change, but no new capability.

## Size
S — small edits across several files, no new data shape.

## Routing
S → /tdd-first (no contract unless the gate demands one)
