---
id: 172
issue_offer: opened
title: Cloud agent and review coverage
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/172
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t7-cloud-agent-and-review-coverage
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

# Cloud agent and review coverage

## Problem statement
Sub-task 7 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 7. Cloud agent and review coverage (`python-ai-developer`)

**Depends on:** 6

**Files to touch:**
- `agents/cloud-engineer.md`
- `agents/security-auditor.md`
- `skills/debug/SKILL.md`
- `.claude/scripts/pr_merged.py`
- `.claude/scripts/tests/test_pr_merged.py`
- `.claude/scripts/tests/test_agent_skill_preloads.py`

**Pre-written TASK block:**
```
TASK: Add the cloud-engineer implementer agent (tools: Read, Edit, Write, Grep, Glob, Bash,
  mcp__codegraph__*; refuses without an approved contract and when cloud.providers is unset; writes
  only under cloud.roots; does design, review, validation with non-mutating commands only, and
  troubleshooting; never runs a deploy, apply, create, update or destroy command against a live
  environment, and writes it out for the user to run instead; the user's normal permission prompts and
  the existing destructive-operation guards apply unchanged).
  Add an infrastructure-as-code checklist section to security-auditor, active when cloud.providers is set.
  Route container and infrastructure bugs in /debug to cloud-engineer. Add cloud-engineer to
  DEFAULT_IMPLEMENTERS.
CONTEXT: concept contract (Extension Points, Failure Modes).
FILES: the six listed.
CONSTRAINTS:
  - Follow the subagent_type literal rule in test_plugin_text_scans.py.
  - Only the docker-master-goat line changes in /debug; the other unshipped names stay (follow-up stub).
  - The agent text must pass test_cloud_text_scans.py (block 6), which covers agents/cloud-engineer.md.
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
