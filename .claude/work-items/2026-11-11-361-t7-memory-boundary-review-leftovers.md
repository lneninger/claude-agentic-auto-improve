---
id: 361
issue_offer: pending
title: Memory boundary review leftovers
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/361
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-11-audit-followups-165/t7-memory-boundary-review-leftovers
worktree: none
north_stars: inherited from .claude/work-items/2026-11-11-165-audit-followups.md
parent_issue: 165
base: feature/165-audit-followups
contract: .claude/concepts/2026-11-11-audit-followups-165.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/379
issue_link: deferred
status: shipped
created: 2026-11-11
---

# Memory boundary review leftovers

## Problem statement
One task of the approved contract `.claude/concepts/2026-11-11-audit-followups-165.md` (parent issue #165). The block below is the contract's own handoff, copied verbatim.

## Acceptance criteria
### 7. Memory boundary review leftovers (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `skills/auto-improve-finish-install/SKILL.md`
- `skills/design-first/references/central-memory.md`
- `skills/pr-merged/references/contract-completion.md`
- `.claude/project-profile.md`
- `.claude/scripts/memory_boundary.py`
- `.claude/scripts/tests/test_memory_boundary.py`
- `.claude/scripts/tests/test_memory_off_parity.py`

**Pre-written TASK block:**
```
TASK: The changes:
  - W1: Stage 1a runs plugin_doctor.py --project ., shows the missing list as what --fix would create, asks once,
    and runs --fix only on yes. The four runs of I-5 apply.
  - I1: the line-18 example carries the suffix.
  - I2: 5a.1 names default-branch-unknown, and the one re-run uses --default-branch with a name read from
    "git symbolic-ref refs/remotes/origin/HEAD" or from the user, never a guessed one.
  - I3: word-bounded ask pattern, looking back only within the paragraph, extended to every --fix line in the file.
  - Q4: section 3 records the empty outcome and prints one line with the suffix.
  - Q5 and Q4: the keep rule in cmd_record (Data Shapes).
  - I6: the retrieve-tool and shape rows say `none` with a server set reports unconfigured.
  Pins with controls:
  - I1: every backticked "Memory: unavailable" example ends with the suffix
  - I2
  - I-5's four runs
  - W1: a planted bare Stage 1a --fix fails
  - the round trip: enabled with items, then enabled empty (kept), then unconfigured (kept), then enabled with new
    items (replaced)
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V11-V17, I-5, I-6)
FILES: the seven above
CONSTRAINTS:
  - I-6; contract-completion.md step labels unchanged (records_step_labels)
  - Run: test_memory_off_parity.py, test_memory_boundary.py, test_parent_branch_rule_text.py,
    test_plugin_text_scans.py, test_plugin_doctor.py (root set, zero skips)
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
