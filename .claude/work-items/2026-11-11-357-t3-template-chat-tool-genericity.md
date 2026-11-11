---
id: 357
issue_offer: pending
title: Template chat-tool genericity
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/357
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-11-audit-followups-165/t3-template-chat-tool-genericity
worktree: none
north_stars: inherited from .claude/work-items/2026-11-11-165-audit-followups.md
parent_issue: 165
base: feature/165-audit-followups
contract: .claude/concepts/2026-11-11-audit-followups-165.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/369
issue_link: deferred
status: shipped
created: 2026-11-11
---

# Template chat-tool genericity

## Problem statement
One task of the approved contract `.claude/concepts/2026-11-11-audit-followups-165.md` (parent issue #165). The block below is the contract's own handoff, copied verbatim.

## Acceptance criteria
### 3. Template chat-tool genericity (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/templates/concept-contract.md`
- `.claude/scripts/tests/test_plugin_text_scans.py`

**Pre-written TASK block:**
```
TASK: Rewrite "## Chat Tool Impact" so it names no consuming project's file, tool, endpoint, adapter, phase,
  contract, memory note or agent. Cite "the project's chat-tool definition, executor and system-prompt files (the
  rest/docs lists in .claude/hooks/sentinel-paths.json, where the project keeps one)" and "the project's
  model-training agent or skill, if it has one". Replace the history paragraph with one generic sentence. Keep I-7.
  Pin the section with seven rules, each with a made-up control (for example "FooTools.cs", "frob-reviewer",
  "/retrain-frob"):
  (1) no file name with a source extension (.cs .ts .py .java)
  (2) no "Phase <letter><digit>" label
  (3) no hex id of six or more characters
  (4) no backticked agent-shaped name outside plugin_agent_names()
  (5) no slash command that is not a skills/ folder
  (6) no "<HTTP verb> /api/" route
  (7) no dated contract slug and no "feedback_*.md" note
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V4, V19)
FILES: the two above
CONSTRAINTS:
  - Run: test_plugin_text_scans.py, test_plugin_doctor.py (AGENTIC_PLUGIN_ROOT set, zero skips),
    test_parent_branch_rule_text.py, test_memory_off_parity.py
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
