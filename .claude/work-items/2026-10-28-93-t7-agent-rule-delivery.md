---
id: 93
issue_offer: opened
title: Agent rule delivery
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/93
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-28-angular-tailwind-rule-documents/t7-agent-rule-delivery
worktree: none
north_stars: inherited from .claude/work-items/2026-10-28-84-angular-tailwind-rule-documents.md
parent_issue: 84
base: feature/84-angular-tailwind-rule-documents
contract: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/105
issue_link: deferred
status: shipped
created: 2026-10-28
---

# Agent rule delivery

## Problem statement
Sub-task 7 of the approved contract `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md` (parent issue #84). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 7. Agent rule delivery (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `skills/angular-ui-rules/SKILL.md`
- `agents/angular-senior-dev.md`
- `agents/ui-ux-designer.md`
- `.claude/scripts/tests/test_angular_rule_delivery.py`

**Pre-written TASK block:**
```
TASK: Ship the angular-ui-rules skill and preload it in both Angular agents. Prove delivery with a live trial.
CONTEXT: concept contract (Rule skill, Q4, Q5, Q14, C5, ASSUMED preload).
FILES: as listed.
CONSTRAINTS:
  - The skill content is exactly as the Rule skill section states.
  - angular-senior-dev: replace the inline rule list with the preload. Remove the project facts (isSuccess,
    /api/screeners/symbols) and the undeclared frontend.root-container slot (cite frontend.roots).
  - The test asserts: both agents' skills entries resolve to the plugin skill; the skill holds the sentinel, the
    precedence clause and the absence clause.
  - Trial (PowerShell): claude -p "Use the angular-senior-dev subagent; have it quote the first line of its preloaded
    skill" --output-format json. Bash: the same command. Try bare, then namespaced. Paste the output in the pull
    request. If both fail, stop and ask for a contract amendment for the SubagentStart fallback.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md — dispatched by /advance
