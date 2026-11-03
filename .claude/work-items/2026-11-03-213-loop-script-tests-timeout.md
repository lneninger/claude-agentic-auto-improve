---
id: 213
issue_offer: pending
title: Landing step loop-script-tests times out: test_pr_merged.py takes about 20 minutes, limit is 15
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/213
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/213-loop-script-tests-timeout
worktree: D:/Dev/HIPALANET/claude-agentic-auto-improve/.claude/worktrees/20261103-infra-213-loop-script-tests-timeout
north_stars: none
contract: none
pr: none
issue_link: unknown
status: clarified
created: 2026-11-03
---

# Landing step loop-script-tests times out: test_pr_merged.py takes about 20 minutes, limit is 15

## Problem statement
The contract landing's `loop-script-tests` verification step runs `.claude/scripts/tests/test_pr_merged.py` with `timeout_minutes: 15` (`.claude/work-item-conventions.json`, `contractLanding.verification.steps`). A full run now takes about 20.5 minutes on the reference Windows workstation (`Ran 744 tests in 1230 s`). The landing merges nothing unless every step exits 0, so a landing would time out on this step even when every test passes.

## Acceptance criteria
- [ ] A full run of every configured verification step finishes inside its own `timeout_minutes` on the reference workstation, with the measured duration recorded.
- [ ] `test_land_contract_verification.py` fails if a step's timeout is below the recorded duration.

## Out of scope
- Making the individual tests faster (a separate effort).
- Adding `test_cleanup_delivered.py` (about an hour) as a landing step.
- Fixing the low-memory kills seen on the workstation (unconfirmed, and not caused by this configuration).

## Known context
- Parent / epic: none
- Related items: #178 (where the duration was measured), pull request #208
- Affected areas: `.claude/work-item-conventions.json`, `.claude/scripts/tests/test_land_contract_verification.py`

## North-star alignment
- none: the register holds no active thought

## Open questions from intake
- Raise the timeout, or split `test_pr_merged.py` into shorter files? → **Answer (assumption, stated not asked):** raise the timeout to a measured value with headroom and pin it in the test. Splitting is a larger change and the issue's acceptance criteria are met without it.
- Where is "the recorded duration" kept so a test can read it? → **Answer (assumption):** a `measured_minutes` field on each step, which the test compares to `timeout_minutes`. The step's `$comment` also names the measurement.

## Size
S — one configuration value, one recorded field, and one pinning test; no new data shape or mechanism.

## Routing
non-trivial → direct to `/tdd-first` (small; no contract needed).
