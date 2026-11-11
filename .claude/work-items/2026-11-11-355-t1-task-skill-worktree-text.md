---
id: 355
issue_offer: pending
title: Task skill worktree text
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/355
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-11-audit-followups-165/t1-task-skill-worktree-text
worktree: none
north_stars: inherited from .claude/work-items/2026-11-11-165-audit-followups.md
parent_issue: 165
base: feature/165-audit-followups
contract: .claude/concepts/2026-11-11-audit-followups-165.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-11
---

# Task skill worktree text

## Problem statement
One task of the approved contract `.claude/concepts/2026-11-11-audit-followups-165.md` (parent issue #165). The block below is the contract's own handoff, copied verbatim.

## Acceptance criteria
### 1. Task skill worktree text (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `skills/task/SKILL.md`
- `.claude/scripts/tests/test_flat_worktree.py`

**Pre-written TASK block:**
```
TASK: Delete the second Step 1.5 (lines 120-134). In 5c, delete the "Create it" gh / git worktree add blocks and
  the "Enter it only if" paragraph. Rule 2 becomes "created by flat_worktree.py (Step 1.5), never by EnterWorktree's
  name: form". Line 498 becomes "the worktree checkout already placed a correct copy". Keep the naming, rules 1 and
  3-5, the base proof (on the plan's path), the gitignore check, the VS Code window and the lifecycle. Line 444
  points a new item at Step 1.5's flat_worktree.py command. Delete the line-559 paragraph. Pin in
  test_flat_worktree.py, with planted controls: exactly one Step 1.5 heading, and no "git worktree add" command
  line in 5c.
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V1, V2)
FILES: the two above
CONSTRAINTS:
  - Run: test_flat_worktree.py, test_parent_branch_rule_text.py, test_ship_skill_sync.py, test_memory_off_parity.py
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
