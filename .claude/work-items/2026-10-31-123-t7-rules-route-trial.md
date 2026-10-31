---
id: 123
issue_offer: opened
title: Rules route trial
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/123
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-30-angular-tailwind-followups/t7-rules-route-trial
worktree: none
north_stars: inherited from .claude/work-items/2026-10-30-86-angular-tailwind-followups.md
parent_issue: 86
base: feature/86-angular-tailwind-followups
contract: .claude/concepts/2026-10-30-angular-tailwind-followups.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/138
issue_link: deferred
status: shipped
created: 2026-10-31
---

# Rules route trial

## Problem statement
Sub-task 7 of the approved contract `.claude/concepts/2026-10-30-angular-tailwind-followups.md` (parent issue #86). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 7. Rules route trial (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/references/claude-rules-route-trial.md`

**Pre-written TASK block:**
```
TASK: Try the .claude/rules/ route live and record the outcome as a Route trial record.
CONTEXT: concept contract (Route trial record; alternative E of the parent).
FILES: as listed.
CONSTRAINTS:
  - Work in a new temporary folder outside every checkout. It holds .claude/rules/angular.md (paths:
    "**/*.component.html", plus a sentinel line) and one matching file.
  - PowerShell:  claude -p "Quote the sentinel line of any rule you were given" --output-format json
    Then a prompt that opens the matching file, then one that uses a subagent. Bash: the same commands.
    Record each output and exit code.
  - Record what was observed, including "did not load". Add one line on whether a follow-up issue is worth
    opening.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-30-angular-tailwind-followups.md — dispatched by /advance
