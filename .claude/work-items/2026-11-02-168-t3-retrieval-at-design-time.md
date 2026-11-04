---
id: 168
issue_offer: opened
title: Retrieval at design time
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/168
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t3-retrieval-at-design-time
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/198
issue_link: deferred
status: shipped
created: 2026-11-02
---

# Retrieval at design time

## Problem statement
Sub-task 3 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 3. Retrieval at design time (`python-ai-developer`)

**Depends on:** 2

**Preconditions:** one session with a stub MCP server confirms the tool id form mcp__server__tool, and a stub that never answers confirms the host timeout returns an error

**Files to touch:**
- `skills/design-first/SKILL.md`
- `skills/design-first/references/central-memory.md`
- `agents/data-architect.md`
- `.claude/templates/concept-contract.md`
- `.claude/scripts/tests/test_skill_script_lookup.py`
- `.claude/scripts/tests/test_repo_consistency.py`
- `.claude/scripts/tests/test_parent_branch_rule_text.py`
- `.claude/scripts/tests/test_memory_off_parity.py`
- `skills/flow/SKILL.md`

**Pre-written TASK block:**
```
TASK: Add /design-first Step 1.5 exactly as Extension Points describes. On "disabled" or an empty lookup it
  prints nothing and writes nothing. On ANY non-zero exit, crash, timeout or unreadable output of any
  adapter subcommand it prints one line, writes nothing more, treats memory as off and goes to Step 2.
  On "unconfigured" it records and prints one line. On "enabled" it
  reads references/central-memory.md. Write that reference: check the tool list; make ONE call (no retry,
  host timeout bounds it; any error or timeout means record "unavailable", print one line, go to Step 2);
  normalise; changed-items; ONE applicability question call (at most 8 items, up to two multi-select
  questions of four options); pass only applies items as
  PRIOR_FINDINGS memory_items; at Step 3 run check-contract, show not-cited/uncleared-item and change
  notices; write a follow-up stub (Parent contract = this contract) only on the user's yes. Document the
  "## Memory used" section in this reference (NOT in /task). Add the data-architect "Memory items" rule
  and the "Memory item <id>@<version>" line format to the template's Lessons referenced section. In
  skills/flow/SKILL.md, add the Step 1.5 applicability question to "Always the operator's call".
CONTEXT: concept contract (Extension Points, route table, Applicability decision, I-M0).
FILES: the nine listed.
CONSTRAINTS:
  - skills/task/SKILL.md is NOT touched.
  - Keep every sentence test_parent_branch_rule_text.py pins in design-first and flow passing.
  - No skill text names a memory tool; the tool id comes from the script's output.
  - Items are quoted data below registries and the user; applies/does-not-apply come only from the user.
  - Extend test_skill_script_lookup.py with the new lookup block (journal 2026-10-15). Keep every
    sentence test_repo_consistency.py SENTENCE_PLACEMENT pins in design-first; update the table only
    if a pinned sentence must move.
  - test_memory_off_parity.py: with memory off (profile absent, placeholder slots, and slots "none"),
    run the commands Step 1.5 runs against copies of every brief in .claude/work-items/ and two fixture
    briefs. Assert each is byte-identical to its original and that no new file appeared in the temp tree.
    Assert skills/task/SKILL.md contains no "Memory used" and no "memory_boundary" text (a content
    check, not a hash pin, so unrelated /task edits do not break it).
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
