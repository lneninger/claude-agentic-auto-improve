---
id: 191
issue_offer: opened
title: Cloud agent skill-load fix
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/191
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t12-cloud-agent-skill-load-fix
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/194
issue_link: deferred
status: shipped
created: 2026-11-02
---

# Cloud agent skill-load fix

## Problem statement
Sub-task 12 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 12. Cloud agent skill-load fix (`python-ai-developer`)

**Depends on:** 7

**Files to touch:**
- `agents/cloud-engineer.md`
- `skills/debug/SKILL.md`
- `.claude/scripts/tests/test_agent_skill_preloads.py`

**Pre-written TASK block:**
```
TASK: Fix review findings B1 and W3 of the block 8 review.
  B1: add Skill to the tool line of agents/cloud-engineer.md, so the line reads
  "Read, Edit, Write, Grep, Glob, Bash, Skill, mcp__codegraph__*". Add the instruction that if the
  cloud-engineering skill cannot be loaded the agent stops and says so, as agents/senior-test-engineer.md
  does. Update the test in test_agent_skill_preloads.py that pins the old tool line, and add a test that
  every agent whose body says to invoke a skill with the Skill tool lists Skill on its tool line or
  preloads it with a skills: entry (cover all files under agents/).
  W3: in skills/debug/SKILL.md, make the hand-off to cloud-engineer carry a contract_path when one exists,
  and when none exists say that a contract is required first (run /design-first) instead of invoking the
  agent. Change nothing else in /debug.
CONTEXT: concept contract (Revision 6); the block 8 review at
  .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t8-review-cloud-capability-fullstack-code-reviewer.md
  (findings B1 and W3).
FILES: the three listed.
CONSTRAINTS:
  - No new agent, skill or flow. Do not bump the plugin version (Parent Branch Delivery Rule).
  - Follow the subagent_type literal rule in test_plugin_text_scans.py.
  - Keep agents/cloud-engineer.md passing test_cloud_text_scans.py.
  - Run test_agent_skill_preloads.py, test_cloud_text_scans.py and test_plugin_text_scans.py and quote the results.
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
