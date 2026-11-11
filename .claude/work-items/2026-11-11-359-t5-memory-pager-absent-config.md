---
id: 359
issue_offer: pending
title: Memory pager absent config
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/359
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-11-audit-followups-165/t5-memory-pager-absent-config
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

# Memory pager absent config

## Problem statement
One task of the approved contract `.claude/concepts/2026-11-11-audit-followups-165.md` (parent issue #165). The block below is the contract's own handoff, copied verbatim.

## Acceptance criteria
### 5. Memory pager absent config (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/hooks/memory-pager.py`
- `.claude/hooks/tests/test_memory_pager.py`

**Pre-written TASK block:**
```
TASK: When the resolved config path is not a file at any claude_roots() rank (FileNotFoundError), memory-pager.py
  writes no log record and exits 0. Every other failure keeps config-load-failed (I-4). Suite test_memory_pager.py
  copies the hook and its helpers into a temporary <tmp>/.claude/hooks/, so SELF_ROOT is temporary. It runs the hook
  by subprocess with CLAUDE_PROJECT_DIR, cwd, HOME and USERPROFILE all temporary, and an existing log folder.
  Rows:
  - absent at all four ranks: no config-load-failed, exit 0 (must fail on today's code; paste it)
  - a malformed decoy at each rank in turn (project, SELF_ROOT, cwd, home): config-load-failed each time
  - a folder in the file's place: logs
  - CLAUDE_MEMORY_PAGER=off: nothing
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V7, I-4, Option E)
FILES: the two above
CONSTRAINTS:
  - do not edit _memory_common.py or _project_paths.py
  - Run: test_memory_pager.py, test_memory_common.py, test_protected_names_warning.py, test_hook_data_files_project_first.py
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
