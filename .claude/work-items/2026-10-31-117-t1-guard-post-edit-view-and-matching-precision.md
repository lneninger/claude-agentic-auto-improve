---
id: 117
issue_offer: opened
title: Guard post-edit view and matching precision
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/117
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-30-angular-tailwind-followups/t1-guard-post-edit-view-and-matching-precision
worktree: none
north_stars: inherited from .claude/work-items/2026-10-30-86-angular-tailwind-followups.md
parent_issue: 86
base: feature/86-angular-tailwind-followups
contract: .claude/concepts/2026-10-30-angular-tailwind-followups.md
pr: none
issue_link: unknown
status: implementing
created: 2026-10-31
---

# Guard post-edit view and matching precision

## Problem statement
Sub-task 1 of the approved contract `.claude/concepts/2026-10-30-angular-tailwind-followups.md` (parent issue #86). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 1. Guard post-edit view and matching precision (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/hooks/architecture-guard.py`
- `.claude/hooks/tests/test_architecture_guard_precision.py`
- `.claude/addons/angular-tailwind/documents/TAILWINDCSS_RULES.md`

**Pre-written TASK block:**
```
TASK: Implement G-4 and G-5 with V-2 for the builder, the per-call pass, the view-versus-disk comparison,
de-duplication and G-5. Fix W4, W6a and W7. Pin W5, W6b, W8 and W11.
CONTEXT: concept contract at .claude/concepts/2026-10-30-angular-tailwind-followups.md
FILES: as listed.
CONSTRAINTS:
  - View tests: a missing file; an ambiguous old_string; replace_all; a three-edit MultiEdit that reports each
    violation once; non-UTF-8 bytes; a CRLF file.
  - One forced-raise test per V-2 step above. Each expects exit 2 on new text that blocks today.
  - Inline template: an Edit that adds "template:" inside an existing decorator blocks. An Edit elsewhere in a
    file that already has one gives today's result.
  - Height chain: a fragment inside a file whose root carries h-full gives no warning.
  - Every G-5 row. The docstring "Known limits" block.
  - TAILWINDCSS_RULES.md: correct only the "Enforced by" lines at :61, :109 and :148. Run
    test_angular_rule_coverage.py.
  - Run test_architecture_guard_scss.py, test_architecture_guard_messages.py and
    test_hook_data_files_project_first.py unchanged.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-30-angular-tailwind-followups.md — dispatched by /advance
