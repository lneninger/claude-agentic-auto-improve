---
id: 88
issue_offer: opened
title: Coverage test
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/88
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-28-angular-tailwind-rule-documents/t2-coverage-test
worktree: none
north_stars: inherited from .claude/work-items/2026-10-28-84-angular-tailwind-rule-documents.md
parent_issue: 84
base: feature/84-angular-tailwind-rule-documents
contract: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/99
issue_link: deferred
status: shipped
created: 2026-10-28
---

# Coverage test

## Problem statement
Sub-task 2 of the approved contract `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md` (parent issue #84). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 2. Coverage test (`senior-test-engineer`)

**Depends on:** 1

**Files to touch:**
- `.claude/hooks/tests/test_angular_rule_coverage.py`

**Pre-written TASK block:**
```
TASK: Write the drift test proving that every rule the old hook printed is in the shipped documents.
CONTEXT: concept contract (Coverage row, Rule document set, Rule ID).
FILES: as listed.
CONSTRAINTS:
  - Read REMINDER and DESIGN_NUDGE from the kept advisor script with ast (never import it).
  - The coverage rows are companion 2's map, verbatim, as data. Each row asserts its IDs and literal fragments.
  - Also assert: every catalogue ID appears once across the set; P IDs are unique; every document has the boundary
    paragraph and the precedence paragraph word for word; no document carries a planted project token (the positive
    control uses a made-up name).
  - A positive control deletes one rule from a temporary copy and expects the failure to name it. No row is skipped.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md — dispatched by /advance
