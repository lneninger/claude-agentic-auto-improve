---
id: 155
issue_offer: pending
title: Failure attribution in the landing report
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/155
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-31-plugin-owns-hook-mechanism-tests/t3-failure-attribution-in-the-landing-report
worktree: none
north_stars: inherited from .claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md
parent_issue: 148
base: feature/148-plugin-owns-hook-mechanism-tests
contract: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-01
---

# Failure attribution in the landing report

Raw argument: sub-task 3 of the contract `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md`, opened by `/flow` Step 2.7 under parent issue #148.

## Problem statement
Task 3 of the approved contract `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md`. The contract is authoritative; see the parent brief `.claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md` for the work item as a whole.

## Acceptance criteria
The contract's own approved handoff block, copied verbatim:

### 3. Failure attribution in the landing report (`python-ai-developer`)

**Depends on:** 1 (its test reads the conventions file, whose step list block 1 extends)

**Files to touch:**
- `.claude/scripts/land_contract.py`
- `.claude/scripts/tests/test_land_contract_verification.py`
- `.claude/scripts/tests/test_land_contract.py`

**Pre-written TASK block:**
```
TASK: Build failure units, attribute each (FA-1..FA-5), record them in the Verification Record, split the
verification-not-ready detail, and carry the Q1 advice into report.json's next_command.
CONTEXT: concept contract (Data Shapes: Failure units, The empty list, Files a unit names, Attribution sides,
  FA rules, The advice facts; Extension Points: The next_command seam; Q1).
FILES: as listed.
CONSTRAINTS:
  - failure_units and attribute_failure are pure. Pass the three sides separately (never a union): contract
    diff; the P7 merge diff captured before P7b reassigns merge_diff, minus hand-resolved paths; landing's own
    paths = diff(HEAD captured before P7b, HEAD after P7b) (empty when P7b commits nothing) plus hand-resolved
    paths plus the MANIFESTS version files. Step applicability keeps using the post-P7b merge_diff.
  - A regression step with no named failures yields exactly one unit "step <id>". On a non-NOT-READY verdict the
    list is [] and there is no note. unittest-text names a file by whole-segment path suffix, unique match only.
  - Only named files decide in-diff/outside-diff; a when_paths match only feeds an FA-5 reason.
  - Add all_outside_diff and step_failures_only (The advice facts) to the P8 halt's keywords AND to make_report's
    fact allow-list. next_command: repeat branch first, unchanged; then step_failures_only -> [advance_line] and
    the "check whether the default branch fails the same step" reason, no re-record line; otherwise the existing
    branch, returning outside_diff and prefixing the Q1 advice when all_outside_diff is true.
  - Verdict, gate order, exit codes, baseline format and the --verify-here record are unchanged. New keys are
    additive. TestVerificationRecordShape and the existing tests stay green unchanged.
  - Tests (unit): one per rule FA-1..FA-5, each with a control; a file in both diffs is undetermined; a file
    changed only by the version-raise commit, or a version file when P7b committed nothing, is undetermined.
    Load this repository's .claude/work-item-conventions.json steps and fail each as exit-code, deriving every
    expectation from the loaded steps (no hard-coded step id or count): every step gets one entry with a
    non-empty reason and the note is written; for each step whose command names a file (rule in Files a unit
    names), that file in the contract diff gives in-diff and in the default-branch diff only gives outside-diff;
    each step naming no file stays undetermined with the "names no file" reason. Assert at least one step of
    each kind exists, so the test cannot pass vacuously.
  - Tests (issue #148 case): a step shaped like the README step (py -3 -B check_hook_registrations.py --settings
    .claude/settings.json --hook-registration-profile .claude/hook-registration-profile.json, no when_paths)
    with .claude/settings.json in the default-branch diff only gives outside-diff, step_failures_only true,
    all_outside_diff false.
  - Tests (empty list): a NOT-READY from reasons only (forbidden path, every step ok) gives [], the
    "no step regressed" note naming the reason, both facts false and no advice.
  - Tests (real report path, in test_land_contract.py, using its end-to-end landing fixture), both branches:
    (a) a named test regression attributed outside-diff halts verification-not-ready and report.json's
    next_command carries outside_diff true, the Q1 advice and the re-record command; (b) an exit-code step
    failing outside-diff carries outside_diff false, the "default branch fails the same step" reason and no
    re-record command; a control with an in-diff failure carries neither advice. The repeat-after-re-record
    branch keeps precedence and shows no advice.
  - Run: py -3 .claude/scripts/tests/test_land_contract_verification.py and
    py -3 .claude/scripts/tests/test_land_contract.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
  contract_status: approved
```

## Out of scope
- Anything outside this block's "Files to touch". See the parent brief for the item's out-of-scope list.

## Known context
- Parent / epic: #148
- Related items: the other sub-tasks of the same contract
- Affected areas: the files listed in the block above

## North-star alignment
- inherited from .claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md

## Open questions from intake
- none (intake is skipped for a task of an approved contract)

## Size
Task of an approved contract.

## Routing
task of .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md - dispatched by /advance
