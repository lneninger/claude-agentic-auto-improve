---
id: 363
issue_offer: pending
title: README counts and count pins
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/363
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-11-audit-followups-165/t9-readme-counts-and-count-pins
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

# README counts and count pins

## Problem statement
One task of the approved contract `.claude/concepts/2026-11-11-audit-followups-165.md` (parent issue #165). The block below is the contract's own handoff, copied verbatim.

## Acceptance criteria
### 9. README counts and count pins (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `README.md`
- `.claude/scripts/tests/test_repo_consistency.py`

**Pre-written TASK block:**
```
TASK: Remove the numbers from the hooks/tests, scripts and scripts/tests tree lines. Correct the hooks line to
  "5 generic data files" and references to 4. Pin every remaining tree and provider-table count against its
  Count-claim oracle, with skill, agent and subagent measures. Helpers return violation lists, with broken-fixture
  controls; one control is a manifest-shaped description string. No assertion runs on the real manifests (I-2).
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V9, Q1, Q2)
FILES: the two above
CONSTRAINTS:
  - first run: git diff of README.md between the parent branch and origin/master. A hunk inside the tree or the
    provider table halts the block. Other hunks are fine when git merge-tree is clean (paste both).
  - each new real assertion fails on today's README (paste)
  - Run: test_repo_consistency.py, test_check_version_bump.py
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
