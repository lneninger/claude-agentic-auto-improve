---
id: 92
issue_offer: opened
title: Guard messages
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/92
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-28-angular-tailwind-rule-documents/t6-guard-messages
worktree: none
north_stars: inherited from .claude/work-items/2026-10-28-84-angular-tailwind-rule-documents.md
parent_issue: 84
base: feature/84-angular-tailwind-rule-documents
contract: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
pr: none
issue_link: unknown
status: implementing
created: 2026-10-28
---

# Guard messages

## Problem statement
Sub-task 6 of the approved contract `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md` (parent issue #84). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 6. Guard messages (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/hooks/architecture-guard.py`
- `.claude/hooks/tests/test_architecture_guard_messages.py`

**Pre-written TASK block:**
```
TASK: Make every guard block and warn line name its Rule ID, with a document footer that degrades when the document
is absent, and honour C1(b) and the sticky rule.
CONTEXT: concept contract (Guard rule map, Guard violation, C1, C4, Q11, Q13).
FILES: as listed.
CONSTRAINTS:
  - Match exact names and prefixes exactly as the Guard rule map states.
  - The footer names <project>/.claude/references/angular-tailwind/<doc> only when that file exists. Otherwise it
    prints the "not installed" line. Test both.
  - C1(b) tests: <svg> with fill blocks; <g> and <text> with left:0 are allowed; <div> with left:0 blocks; a split
    <rect tag blocks. Sticky: "sticky top-4" in a class attribute blocks; the word sticky in text does not.
  - Every mapped ID exists as a heading in the shipped documents. The inline-style suggestion stops citing w-[200px].
  - Run test_architecture_guard_scss.py and test_hook_data_files_project_first.py unchanged.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md — dispatched by /advance
