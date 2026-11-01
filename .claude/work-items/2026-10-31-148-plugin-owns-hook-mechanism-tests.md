---
id: 148
issue_offer: pending
title: Own hook-mechanism tests in the plugin, not in consuming projects
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/148
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/148-plugin-owns-hook-mechanism-tests
worktree: D:/Dev/HIPALANET/claude-agentic-auto-improve/.claude/worktrees/20261031-feature-148-plugin-owns-hook-mechanism-tests
north_stars: none
contract: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
pr: none
issue_link: unknown
status: designing
created: 2026-10-31
---

# Own hook-mechanism tests in the plugin, not in consuming projects

Raw argument: `https://github.com/lneninger/claude-agentic-auto-improve/issues/148`

## Problem statement
The hook mechanism (hook gating, hook registration rows, setup profiling) is owned by this plugin. The tests that prove it works live in a consuming project repository, `lneninger/StockToolScalpingMachine`. A change to hook registrations on that project's default branch can therefore fail those tests inside an unrelated contract landing. The landing script (`land_contract.py`, gate P8) then offers no way past except re-recording the project's failing-test baseline, which can hide a real break. A finished 30-sub-task contract could not land because of tests about hook registration.

## Acceptance criteria
- [ ] The five named tests, or their equivalents, run from this repo's own suite: `test_hook_gating::test_hook_gating`, `RegistrationRowsUnchangedTests::test_hooks_block_equals_base_apart_from_if_keys`, `RegistrationRowsUnchangedTests::test_row_count_is_unchanged`, `test_profile_setup::test_profile_setup`, `RegistrationCoverageTests::test_real_settings_every_registration_is_profiled_or_excluded`.
- [ ] A project can run a plugin-owned checker against its own `.claude/settings.json` and gets a pass, or a named failure for each broken rule (row count unchanged, `if` keys unchanged, every registration profiled or excluded).
- [ ] After migration, a project no longer needs `python-hooks` or `python-scripts` hook-mechanism entries in its failing-test baseline. Verifiable here only by showing the checker is the single place the rules live and a project needs no copy of the tests.
- [ ] The P8 landing report separates "failures in the contract's diff" from "failures outside it", or states in the report why it cannot.
- [ ] The pull request answers the open question: does the "suggest checking the default branch before re-recording" advice belong in the landing script, or in the checker's output only?
- [ ] Failure path: the checker, given a `settings.json` that breaks each rule in turn, exits non-zero and names the rule. Given a missing or unreadable `settings.json`, it fails with a clear message and does not pass silently.

## Out of scope
- Any change to the project's landing-page contract or its code.
- Deciding whether to re-record the project's baseline; the project does that on its own branch.
- Editing files in the consuming project repository.

## Known context
- Parent / epic: none
- Related items: contract parent issue #864 in the project repository (`StockToolScalpingMachine`); landing run `20261101T021604Z-5bc0d3`.
- Affected areas (best guess, to be confirmed by the contract): `.claude/scripts/land_contract.py` and its tests, a new plugin-owned checker under `.claude/scripts/`, `.claude/hooks/hooks.json` and the registration rows it describes, `auto_improve_finish_install.py` (setup profiling), plugin version and release notes.
- Verified in this worktree (2026-10-31): no `test_hook_gating` or `test_profile_setup` file is tracked here, and `land_contract.py` carries gate `verification-not-ready` with the remedy text "fix the new failures named in the detail, or re-record the baseline".
- Not verified, per the issue: whether the five tests fail on the project's default branch alone or only on the merged head; that the named registration commits caused it.

## North-star alignment
- none — the register holds no active thought (the `.claude/north-stars/` directory does not exist).

## Open questions from intake
- The issue says the original tests live only in the consuming project, so their source is not in this repo. Are "equivalents" written fresh here against a generic fixture settings file acceptable? → **Answer (assumption, no blocker):** yes. The contract states the rules, the plugin implements and tests them, and the project's copy is not read or edited.
- Does the P8 advice belong in the landing script or only in the checker's output? → **Answer:** left open on purpose. The issue requires the pull request to answer it, so the contract carries it as an Open Question with a recommendation.
- Issue title carries no effort prefix. → **Answer (assumption):** type is IMPROVEMENT, because the tests exist and work but live in the wrong place and the landing report is inadequate. The title on GitHub was not edited, so the tracker title is out of sync with this brief.

## Size
L — a new plugin-owned checker, a migrated test set, a change to the landing report, and a version bump across more than one mergeable block.

## Routing
non-trivial → /design-first. A contract with two or more mergeable blocks is delivered through a parent branch and needs a GitHub parent issue (Parent Branch Delivery Rule).
