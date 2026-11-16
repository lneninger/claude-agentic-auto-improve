---
id: 422
issue_offer: opened
title: Live prompt trial
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/422
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t3-live-prompt-trial
worktree: none
north_stars: inherited from .claude/work-items/2026-11-16-file-based-switches.md
parent_issue: 419
base: feature/file-based-switches
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-16
---

# Live prompt trial

## Problem statement
Sub-task 3 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 3. Live prompt trial (`senior-test-engineer`)

**Depends on:** 2

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t3-live-prompt-trial-senior-test-engineer.md`

**Pre-written TASK block:**
```
TASK: Write the run sheet for a person-run trial of the prompt route. Do not run it; a person
  runs it in a real Claude Code session and sets the verdict before this pull request merges.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (Person-present
  rule, Visible-off rule, Uncertain Assumptions).
FILES: the run sheet only. It does NOT exist yet; you create it.
CONSTRAINTS:
  - Header line, alone on its line: "**Verdict:** blocked", plus the line "Results pending: a
    person runs the steps below". Merged unchanged, it holds every block that depends on it.
  - Steps, each with a PowerShell command and an expected and an observed line: (1) arm and run
    a destructive command on a disposable-looking but non-disposable name in default mode; a
    prompt appears, and declining leaves no arm; (2) the same in bypass-permissions mode blocks;
    (3) a headless run (claude -p) with no permission tool blocks; (4) switching concept_gate off
    shows the person a message once in the session; (5) record the Claude Code version.
  - The six fixed sections. "## Evidence" holds the person's observations. Write the Gate Output
    beside it with supersedes [] and checklist [].
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md — dispatched by /advance
