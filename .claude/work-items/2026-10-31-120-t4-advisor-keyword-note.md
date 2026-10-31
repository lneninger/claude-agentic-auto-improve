---
id: 120
issue_offer: opened
title: Advisor keyword note
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/120
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-30-angular-tailwind-followups/t4-advisor-keyword-note
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

# Advisor keyword note

## Problem statement
Sub-task 4 of the approved contract `.claude/concepts/2026-10-30-angular-tailwind-followups.md` (parent issue #86). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 4. Advisor keyword note (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/addons/angular-tailwind/DISABLED.md`
- `.claude/hooks/tests/test_addons.py`

**Pre-written TASK block:**
```
TASK: Keep the "ui" limit documented. Add the advisor's home-folder fallback (line 43) as a second defect to fix
before turning the hook back on. Replace the kill-switch step.
CONTEXT: concept contract (criterion 3, G-3, K-1).
FILES: as listed.
CONSTRAINTS:
  - "How to turn it back on":
    * fix the keyword pattern, or drop "ui";
    * read the rules file through _project_paths;
    * add the new hash to released_sha256.
    Step 2 becomes "add-ons declare no kill switch".
  - A test asserts that DISABLED.md names both defects. Do not edit the advisor script.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-30-angular-tailwind-followups.md — dispatched by /advance
