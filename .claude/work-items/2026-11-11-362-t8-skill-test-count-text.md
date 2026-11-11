---
id: 362
issue_offer: pending
title: Skill test-count text
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/362
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-11-audit-followups-165/t8-skill-test-count-text
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

# Skill test-count text

## Problem statement
One task of the approved contract `.claude/concepts/2026-11-11-audit-followups-165.md` (parent issue #165). The block below is the contract's own handoff, copied verbatim.

## Acceptance criteria
### 8. Skill test-count text (`python-ai-developer`)

**Depends on:** 3 — both edit `test_plugin_text_scans.py`

**Files to touch:**
- `skills/pr-merged/SKILL.md`
- `skills/advance/SKILL.md`
- `.claude/scripts/tests/test_plugin_text_scans.py`

**Pre-written TASK block:**
```
TASK: Replace "760 cases" and "Ran 760 tests" with the suite path, its run command and "its unittest summary line
  must end OK". Pin: neither file states a digit count of tests or cases for test_pr_merged.py. The control plants
  "Ran 760 tests".
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V10, Q3)
FILES: the three above
CONSTRAINTS:
  - Run: test_plugin_text_scans.py, test_parent_branch_rule_text.py, test_pr_merged.py
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
