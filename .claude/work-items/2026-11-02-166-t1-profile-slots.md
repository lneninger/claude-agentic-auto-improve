---
id: 166
issue_offer: opened
title: Profile slots
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/166
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t1-profile-slots
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: UNKNOWN
issue_link: unknown
status: implementing
created: 2026-11-02
---

# Profile slots

## Problem statement
Sub-task 1 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 1. Profile slots (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/project-profile.md`

**Pre-written TASK block:**
```
TASK: Add nine slot rows to the Slots table of the profile template: memory.server, memory.retrieve-tool,
  memory.capture-tool, memory.shape, memory.project-key, cloud.providers, cloud.iac, cloud.roots,
  cloud.mcp-server. Each value is the template's italic placeholder prose saying what to write and that
  `none` turns it off. Add one short note under the table: memory and cloud are optional and are off
  while their slots are unset.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md (Data Shapes,
  value objects "Memory adapter configuration" and "Cloud profile").
FILES: .claude/project-profile.md
CONSTRAINTS:
  - Placeholder form "*( ... )*" so pr_merged.load_slot reads every new slot as unset.
  - Do not change existing rows. Do not touch any version file.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```


## Out of scope
- Everything outside this sub-task's handoff block; see the other sub-tasks of the contract.

## Known context
- Parent / epic: #161 (https://github.com/lneninger/claude-agentic-auto-improve/issues/161)
- Related items: the other sub-tasks of `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`
- Affected areas: the files named in the handoff block

## North-star alignment
- inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md

## Open questions from intake
- none; the sub-task's criteria were approved at the contract gate.

## Size
Task of .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md.

## Routing
task of .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md - dispatched by /advance
