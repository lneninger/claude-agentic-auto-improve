---
id: 390
issue_offer: pending
title: Keep rule for an unavailable outcome
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/390
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-11-audit-followups-165/t13-keep-rule-for-an-unavailable-outcome
worktree: none
north_stars: inherited from .claude/work-items/2026-11-11-165-audit-followups.md
parent_issue: 165
base: feature/165-audit-followups
contract: .claude/concepts/2026-11-11-audit-followups-165.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/394
issue_link: deferred
status: shipped
created: 2026-11-12
---

# Keep rule for an unavailable outcome

## Problem statement
One task of the approved contract `.claude/concepts/2026-11-11-audit-followups-165.md` (parent issue #165), added by its Revision 4 amendment after the t10 review returned blocked. The block below is the contract's own handoff, copied verbatim.

## Acceptance criteria
### 13. Keep rule for an unavailable outcome (`python-ai-developer`)

**Depends on:** 12 — test_memory_off_parity.py, in this block's Run list, is red on the parent tip until block 12 merges

**Files to touch:**
- `.claude/scripts/memory_boundary.py`
- `.claude/scripts/tests/test_memory_boundary.py`
- `skills/design-first/references/central-memory.md`

**Pre-written TASK block:**
```
TASK: Extend the keep rule in cmd_record to an unavailable outcome (Q8 answered yes, t10 F3). TDD: first turn the
  block-7 test test_an_unavailable_outcome_does_not_keep_earlier_items into one that pins the keep (rename it to
  say so) and paste its red run. Then remove the `outcome.get("state") != "unavailable"` condition at
  memory_boundary.py:791 and update the comment at :792-794. Change nothing else in cmd_record. Pins:
  - enabled with items, then unavailable (timeout) with empty lists: first line
    "Memory: unavailable (timeout) | <date>", the earlier Retrieved: and Reported: lines kept in order, then
    Captured: and Not sent:
  - extend the existing round trip with an unavailable step (empty lists) between the kept steps and the final
    replace
  - an unavailable outcome that carries items: those items are written in place of the earlier lines, exactly
    as for enabled (Data Shapes). This pin states the behaviour the code keeps; it is not a new rule.
  Reference: in central-memory.md section 6, add one sentence after the line table. It says that when the new
  outcome carries no item (an unconfigured profile, an empty retrieval, or an unavailable outcome), record keeps
  the earlier Retrieved: and Reported: lines in order. Leave line 43's empty-retrieval sentence as it is.
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (Data Shapes keep rule, V22, Q8)
FILES: the three above
CONSTRAINTS:
  - I-6: the three I-M0 disabled tests are not edited. Name every test you change in the pull request.
  - No new subcommand, refusal, state or reason (Memory adapter shape unchanged).
  - A sub-task pull request into the parent branch does not raise the plugin version (Parent Branch Delivery
    Rule). Touch no check_version_bump.MANIFESTS file.
  - Write nothing under .claude/reviews/.
  - A red suite in the Run list stops the block; report it.
  - Run, each with py -3 -B, and paste every summary line: test_memory_boundary.py, test_memory_off_parity.py
    (it reads the keep rule and pins central-memory.md), test_parent_branch_rule_text.py (it pins
    central-memory.md), test_plugin_text_scans.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

## Out of scope
- Every other block of the contract. A new subcommand, refusal, state or reason (the memory adapter shape is unchanged).

## Known context
- Parent / epic: #165
- Related items: the blocked review `.claude/reviews/2026-11-11-audit-followups-165/t10-review-fullstack-code-reviewer.md`

## North-star alignment
- none: inherited from the parent brief, whose register holds no active thought.

## Open questions from intake
- none

## Size
Not sized: a task of an approved contract.

## Routing
task of .claude/concepts/2026-11-11-audit-followups-165.md dispatched by /advance
