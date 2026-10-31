---
id: 121
issue_offer: opened
title: Doctor drift and agent preload
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/121
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-30-angular-tailwind-followups/t5-doctor-drift-and-agent-preload
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

# Doctor drift and agent preload

## Problem statement
Sub-task 5 of the approved contract `.claude/concepts/2026-10-30-angular-tailwind-followups.md` (parent issue #86). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 5. Doctor drift and agent preload (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/plugin_doctor.py`
- `.claude/scripts/tests/test_plugin_doctor.py`
- `agents/python-ai-developer.md`
- `.claude/scripts/tests/test_agent_skill_preloads.py`

**Pre-written TASK block:**
```
TASK: Implement D-3 and D-4 in --drift, and remove the python-ai preload.
CONTEXT: concept contract (Doctor rules D-1 to D-5).
FILES: as listed.
CONSTRAINTS:
  - D-3 reuses _effective_hooks and _launched_and_first_argument, called per layer. Include the parity fixtures
    and the three pinned divergences, exactly as stated. Positive and negative controls.
  - D-4: the destination equality test. --drift never writes.
  - Remove the skills: block of python-ai-developer. New test: every skills: entry in agents/*.md resolves to a
    shipped skills/<name>/SKILL.md, resolved the way test_angular_rule_delivery.py does. A planted missing
    name fails.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-30-angular-tailwind-followups.md — dispatched by /advance
