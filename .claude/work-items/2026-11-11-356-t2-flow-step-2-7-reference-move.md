---
id: 356
issue_offer: pending
title: Flow Step 2.7 reference move
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/356
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-11-audit-followups-165/t2-flow-step-2-7-reference-move
worktree: none
north_stars: inherited from .claude/work-items/2026-11-11-165-audit-followups.md
parent_issue: 165
base: feature/165-audit-followups
contract: .claude/concepts/2026-11-11-audit-followups-165.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/367
issue_link: deferred
status: shipped
created: 2026-11-11
---

# Flow Step 2.7 reference move

## Problem statement
One task of the approved contract `.claude/concepts/2026-11-11-audit-followups-165.md` (parent issue #165). The block below is the contract's own handoff, copied verbatim.

## Acceptance criteria
### 2. Flow Step 2.7 reference move (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `skills/flow/SKILL.md`
- `skills/flow/references/open-sub-tasks.md`
- `.claude/scripts/tests/test_parent_branch_rule_text.py`
- `.claude/scripts/tests/test_compose_subissue_title.py`

**Pre-written TASK block:**
```
TASK: Move Step 2.7 point 3 onward verbatim into skills/flow/references/open-sub-tasks.md: the gh check, the
  per-sub-task decision with both verify_parent_link.py lookup blocks, the /task call, the partial-failure rule,
  point 4, "Finding sub-issues" and "No new status:". Replace it with the Extension Points line. Keep the guard, the
  Parent Branch Delivery Rule paragraph, the PRM lookup and status call, and points 1 and 2. Retarget the
  no:parent-issue check to SKILL.md plus the reference. Add FlowTextTests, with planted controls: Step 2.7 names the
  reference and the read-in-full and stop rule; the reference holds --record-subtask, verify_parent_link.py and
  no:parent-issue.
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V3, I-3)
FILES: the four above
CONSTRAINTS:
  - Run: test_parent_branch_rule_text.py, test_compose_subissue_title.py, test_skill_script_lookup.py (slow),
    test_memory_off_parity.py, test_pr_merged.py
  - report SKILL.md line counts before and after
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

## Out of scope
- Every other block of the contract.

## Known context
- Parent / epic: #165
- Related items: none

## North-star alignment
- none: inherited from the parent brief, whose register holds no active thought.

## Open questions from intake
- none

## Size
Not sized: a task of an approved contract.

## Routing
task of .claude/concepts/2026-11-11-audit-followups-165.md dispatched by /advance
