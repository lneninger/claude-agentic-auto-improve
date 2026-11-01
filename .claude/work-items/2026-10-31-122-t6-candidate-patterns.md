---
id: 122
issue_offer: opened
title: Candidate patterns
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/122
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-30-angular-tailwind-followups/t6-candidate-patterns
worktree: none
north_stars: inherited from .claude/work-items/2026-10-30-86-angular-tailwind-followups.md
parent_issue: 86
base: feature/86-angular-tailwind-followups
contract: .claude/concepts/2026-10-30-angular-tailwind-followups.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/137
issue_link: deferred
status: shipped
created: 2026-10-31
---

# Candidate patterns

## Problem statement
Sub-task 6 of the approved contract `.claude/concepts/2026-10-30-angular-tailwind-followups.md` (parent issue #86). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 6. Candidate patterns (`ui-ux-designer`)

**Depends on:** none

**Files to touch:**
- `.claude/addons/angular-tailwind/documents/UI-UX-PATTERNS.md`

**Pre-written TASK block:**
```
TASK: Ship P-002 "Table column alignment" and record the three rejected patterns (Q2).
CONTEXT: concept contract (Pattern decision, Q2). Rule entry shape and precedence paragraph as in the parent.
FILES: as listed.
CONSTRAINTS:
  - P-002: numeric columns and their headers right-aligned, text columns left-aligned, each header aligned with
    its column. Enforced by: not enforced. One short example using token utilities and placeholders. First check
    that no catalogue rule in the four documents already states it.
  - Update the boundary paragraph. Add "## Patterns this plugin does not ship", one line each:
    * status badge: its states and colours are product data, and the application-design skill has an
      advisory one;
    * card surface: product look and feel;
    * constrained-panel: a project class name; T-014 and the scroll container already bound height.
  - Run .claude/hooks/tests/test_angular_rule_coverage.py.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-30-angular-tailwind-followups.md — dispatched by /advance
