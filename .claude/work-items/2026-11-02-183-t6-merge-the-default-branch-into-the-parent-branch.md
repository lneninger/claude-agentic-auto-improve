---
id: 183
issue_offer: pending
title: Merge the default branch into the parent branch
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/183
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-31-plugin-owns-hook-mechanism-tests/t6-merge-the-default-branch-into-the-parent-branch
worktree: none
north_stars: inherited from .claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md
parent_issue: 148
base: feature/148-plugin-owns-hook-mechanism-tests
contract: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-02
---

# Merge the default branch into the parent branch

Raw argument: sub-task 6 of the contract `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md`, opened by `/flow` Step 2.7 under parent issue #148.

## Problem statement
Task 6 of the approved contract `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md`. The contract is authoritative; see the parent brief `.claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md` for the work item as a whole. This is a remedy sub-task: the landing run `20261102T133845Z-5f35db` halted at gate P7 (`unresolvable-conflict`) because `master` moved on after the parent branch was cut.

## Acceptance criteria
The contract's own approved handoff block, copied verbatim:

### 6. Merge the default branch into the parent branch (`python-ai-developer`)

*Amendment of 2026-11-02, a remedy sub-task.* The landing run `20261102T133845Z-5f35db` halted at gate P7 (`unresolvable-conflict`): `master` moved on after the parent branch was cut and three files now conflict. This block clears them by hand, so the landing's own merge of `master` is clean. It adds no data shape and no mechanism.

**Depends on:** 5

**Files to touch:**
- `.claude/registries/VOCABULARY.md`
- `README.md`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`

**Pre-written TASK block:** see block 6 of the contract at .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md (merge origin/master into the sub-task branch; keep both sides of VOCABULARY.md and of the new test classes; write the real test-case count into README.md; no version file edit).

## Out of scope
- Anything outside this block's "Files to touch", other than files that arrive unchanged from `master` through the merge. See the parent brief for the item's out-of-scope list.

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
