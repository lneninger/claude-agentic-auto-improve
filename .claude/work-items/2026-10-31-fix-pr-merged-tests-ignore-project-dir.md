---
id: none
issue_offer: pending
title: Make the pr_merged tests ignore CLAUDE_PROJECT_DIR
type: BUG
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: fix/pr-merged-tests-ignore-project-dir
worktree: D:/Dev/HIPALANET/claude-agentic-auto-improve/.claude/worktrees/20261031-infra-record-loop-script-tests-baseline
north_stars: none
base: none
contract: none
pr: none
issue_link: unknown
status: implementing
created: 2026-10-31
---

# Make the pr_merged tests ignore CLAUDE_PROJECT_DIR

## Problem statement
The contract landing halts at its verification gate (P8) because the `loop-script-tests` suite (`.claude/scripts/tests/test_pr_merged.py`) fails 33 of 651 tests when the landing runs it. The landing exports `CLAUDE_PROJECT_DIR`, pointing at its own checkout, for every verification step. The tests assume a clean environment, so `pr_merged.py` reads that checkout's work-item briefs instead of the fixture's. The same tests fail on an untouched `master` under that setting and pass without it.

The first plan was to record a failing-test baseline. That cannot work: the suite uses the `exit-code` result format, so the recorder refuses to baseline a failing run and the gate treats any non-zero exit as a regression.

## Acceptance criteria
- [x] `test_pr_merged.py` removes `CLAUDE_PROJECT_DIR` from the environment before the code under test is used.
- [x] The full suite passes (exit 0) when run with `CLAUDE_PROJECT_DIR` set to the checkout, as the landing runs it.
- [ ] After this merges, a fresh landing of the angular-tailwind follow-ups contract (parent issue 86) passes the P8 gate.
- [x] No shipped plugin file changes, so no version raise.

## Out of scope
- Recording a failing-test baseline (not possible for an exit-code suite).
- Other suites, and any change to `pr_merged.py` or `land_contract.py`.

## Known context
- Parent / epic: none
- Related items: contract 2026-10-30-angular-tailwind-followups; landing reports 20261031T223827Z-7518a2 and 20261031T230319Z-2556e9
- Affected areas: `.claude/scripts/tests/test_pr_merged.py`

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- Whether to open a tracker issue for this item → **Answer:** not asked at intake; `/ship` Step 3.5 decides.

## Size
XS — one line plus a comment in a test file.

## Routing
trivial → direct; no contract.
