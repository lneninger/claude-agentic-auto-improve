---
id: 57
title: Work shipped from this repo has no issue, so nothing is closed
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/57
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: fix/57-own-repo-issue-closing
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261016-bug-plugin-not-closing-own-repo-issues
north_stars: none
contract: .claude/concepts/2026-10-16-recorded-issue-offer-outcome.md
pr: UNKNOWN
issue_link: unknown
status: verifying
created: 2026-10-16
---

# Work shipped from this repo has no issue, so nothing is closed

## Problem statement
The plugin's own repository (`lneninger/claude-agentic-auto-improve`) is delivered with the plugin's own chain, yet most merged pull requests close no issue. Of the pull requests inspected (41 to 55), only 48 and 52 carry a closing link (to issues 47 and 50). The older briefs (`2026-09-13`, `2026-09-14`, `2026-10-04`, `2026-10-05`) all record `id: none`. The only open issues are two follow-up chores (51 and 21). The tracker therefore never learns that the work happened. The user confirmed this reading ("work ships with no issue").

## Acceptance criteria
- [ ] ASSUMPTION, to be confirmed by the design: a free-text `/task` run in this repo, with `gh` signed in, ends with a real issue opened (or an explicit, recorded decline), never a silent `id: none`.
- [ ] A pull request shipped from a brief that has an issue id carries exactly one closing line, and `verify_issue_link.py` reports `closes` for it.
- [ ] Failure path: when an issue cannot be opened (no `gh`, not signed in), the brief records why and `/ship` says so in the pull request notes instead of omitting the link silently.
- [ ] The root cause is named from evidence: which step let each of pull requests 53, 54 and 55 ship with no issue (declined offer, run that began without `/task`, or an offer that never fired).
- [ ] A test fails before the fix and passes after it, for the cause found.

## Out of scope
- Closing the two existing follow-up chores (issues 51 and 21).
- Back-filling issues for pull requests 5 to 55 that already merged.
- Any change to other projects' repositories or their vendored copies.

## Known context
- Parent / epic: none
- Related items: issues 47 and 50 (closed correctly), 51 and 21 (open follow-up chores); pull request 54 (made `/design-first` create a linking brief when the run began without `/task`).
- Affected areas (best guess, to be confirmed by the contract): `skills/task/SKILL.md` (Step 2.5 point 6), `skills/ship/SKILL.md` (Step 3.5), `.claude/scripts/verify_issue_link.py`, `.claude/work-item-conventions.json`.

## North-star alignment
- none - the register holds no active thought

## Open questions from intake
- Which symptom did the user see? -> **Answer:** work ships with no issue (user's choice, recommended option).
- Why did the three newest pull requests ship with no issue? -> **Answer:** UNKNOWN on purpose. It is the first thing `/debug` must establish from the briefs and run logs, not something to guess here.

## Size
M - re-sized from S after `/debug`. The root cause (see `.claude/debug-notes-own-repo-issue-closing.md`, verdict CONFIRMED) is that "no issue" is one undifferentiated state; the fix adds a recorded offer outcome to the brief, a conventions switch and a verifier verdict. That is a new data shape.

## Run log
- 2026-10-16: intake, debug (root cause confirmed), contract approved by the user with all open questions answered, tests written first (red), implementation (green).
- Review stage used its retry budget: three fresh review passes each found real defects. Passes one and two were fixed test-first (bare-filename path read, stale verdicts list, non-list and non-text keys, an implicit success fall-through, a corrupt beside-brief file). The third pass left two warnings OPEN:
  - W1: `offer-unavailable` is reached by any extra reason a project adds to `offerReasons`; the contract allows only `create-failed` and `no-problem-statement`. Fix: an explicit allow-list in `_evaluate_absent` (`.claude/scripts/verify_issue_link.py` near line 546), plus a test.
  - W2: after `offer-unrecorded` with `issue_offer: opened` and no id, `/ship` Step 4d tells the agent to re-offer, which can create a duplicate issue. Fix: look up the already-created issue by exact title and write its id back first (`skills/ship/SKILL.md`, Step 3.5 gate and the Step 4d row).
  - Smaller notes N1 to N7 are in the review: byte-order mark in a brief, stale `--brief` help text, nested brief layout, wording gaps in the ship skill, and the changed agent-memory file.
- Suites at the last full run: issue-link verifier 535 of 535 checks pass; ship-skill consistency 102 of 102 pass; version-bump, script-lookup and sub-issue-title suites pass. Known failures that also fail without this change: `test_pr_merged.py` (1), `test_plugin_doctor.py` (11), `test_plugin_manifests.py` (14); all need hook or add-on files that are not tracked. (State at the first stop; superseded by the next entry.)
- 2026-10-16 (resumed on the user's "continue"): W1 and W2 fixed test-first (explicit allow-list of the two reasons that still hold at ship time; `/ship` looks up an already-created issue before re-offering). Verified on the final tree: issue-link verifier 542 checks pass, ship-skill consistency 104 pass, version-bump, script-lookup and sub-issue-title suites pass, version check "raised to 0.9.4". No review pass was run on this last small fix (the three earlier passes were); that is disclosed in the pull request. Not fixed, by choice: N1 (brief with a byte-order mark), N3 (brief nested deeper than `work-items`), N4 and N5 and N6 wording notes.

## Routing
non-trivial -> `/design-first` (contract), then `/tdd-first`. Debug notes: `.claude/debug-notes-own-repo-issue-closing.md`.
