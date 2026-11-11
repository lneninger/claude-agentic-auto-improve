---
id: 358
issue_offer: pending
title: Debug routing to shipped agents
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/358
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-11-audit-followups-165/t4-debug-routing-to-shipped-agents
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

# Debug routing to shipped agents

## Problem statement
One task of the approved contract `.claude/concepts/2026-11-11-audit-followups-165.md` (parent issue #165). The block below is the contract's own handoff, copied verbatim.

## Acceptance criteria
### 4. Debug routing to shipped agents (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `skills/debug/SKILL.md`
- `.claude/scripts/tests/test_agent_skill_preloads.py`

**Pre-written TASK block:**
```
TASK: Route ingestion jobs to "`dotnet-backend-architect`, or the project's own ingestion agent if it declares one".
  Route the LLM pipeline and Python sidecar to `python-ai-developer`, "or the project's own model-training agent if it
  declares one". Pin beside test_debug_routes_container_bugs_to_cloud_engineer, reusing plugin_agent_names() and
  TestTheRealPluginTree.NOT_SHIPPED (import, never copy): every backticked agent-shaped name in "Choose the agent by
  area" is shipped. The control plants "`llm-training-engineer`".
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V5)
FILES: the two above
CONSTRAINTS:
  - Run: test_agent_skill_preloads.py, test_plugin_text_scans.py, test_plugin_doctor.py (root set, zero skips)
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
