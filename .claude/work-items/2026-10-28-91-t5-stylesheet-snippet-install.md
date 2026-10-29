---
id: 91
issue_offer: opened
title: Stylesheet snippet install
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/91
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-28-angular-tailwind-rule-documents/t5-stylesheet-snippet-install
worktree: none
north_stars: inherited from .claude/work-items/2026-10-28-84-angular-tailwind-rule-documents.md
parent_issue: 84
base: feature/84-angular-tailwind-rule-documents
contract: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/103
issue_link: deferred
status: shipped
created: 2026-10-28
---

# Stylesheet snippet install

## Problem statement
Sub-task 5 of the approved contract `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md` (parent issue #84). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 5. Stylesheet snippet install (`python-ai-developer`)

**Depends on:** 4

**Files to touch:**
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `skills/auto-improve-angular-tailwind-install/SKILL.md`

**Pre-written TASK block:**
```
TASK: Add the --stylesheet step that appends the scroll-edge snippet when the classes are missing.
CONTEXT: concept contract (Stylesheet snippet, I-9, Q7, Q12).
FILES: as listed.
CONSTRAINTS:
  - With no --stylesheet, the plan lists candidates (<each frontend.roots entry>/src/styles.scss or .css that exists)
    and writes nothing.
  - All three classes defined: present. None defined: append at the end, inside the markers. Some defined:
    stylesheet-partial-snippet.
  - Tests: all three definitions exist after the install; a second install changes nothing (byte-identical);
    a pre-existing project definition is reported as present.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md — dispatched by /advance
