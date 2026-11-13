---
id: 360
issue_offer: pending
title: Registry reads in agents and design-first
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/360
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-11-audit-followups-165/t6-registry-reads-in-agents-and-design-first
worktree: none
north_stars: inherited from .claude/work-items/2026-11-11-165-audit-followups.md
parent_issue: 165
base: feature/165-audit-followups
contract: .claude/concepts/2026-11-11-audit-followups-165.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/377
issue_link: deferred
status: shipped
created: 2026-11-11
---

# Registry reads in agents and design-first

## Problem statement
One task of the approved contract `.claude/concepts/2026-11-11-audit-followups-165.md` (parent issue #165). The block below is the contract's own handoff, copied verbatim.

## Acceptance criteria
### 6. Registry reads in agents and design-first (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `agents/data-architect.md`
- `agents/contract-critic.md`
- `agents/registry-scout.md`
- `agents/fullstack-code-reviewer.md`
- `agents/api-contract-reviewer.md`
- `skills/design-first/SKILL.md`

**Pre-written TASK block:**
```
TASK: At every read line listed in V8, the digest is read "when it exists (made by py -3
  .claude/scripts/generate_registry_digest.py); otherwise read the registries directly". Every INTEGRATION.md
  read becomes "where the project keeps one", and without it the agent works from the code it investigated.
  registry-scout reports the digest as absent and names the generator. design-first SKILL.md:96 passes
  registry_digest only when the file exists. Write and update instructions are unchanged.
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V8)
FILES: the six above
CONSTRAINTS:
  - leave the focus rule, memory rule 9, critic item 7 and the Parent Branch lines untouched
  - Run: test_plugin_text_scans.py, test_memory_off_parity.py, test_parent_branch_rule_text.py,
    test_repo_consistency.py, test_skill_script_lookup.py (slow)
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
