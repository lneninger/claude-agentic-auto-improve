---
id: 170
issue_offer: opened
title: Review memory boundary
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/170
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t5-review-memory-boundary
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/203
issue_link: deferred
status: shipped
created: 2026-11-02
---

# Review memory boundary

## Problem statement
Sub-task 5 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 5. Review memory boundary (`fullstack-code-reviewer`)

**Depends on:** 2, 3, 4

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t5-review-memory-boundary-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 2-4 and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t5-review-memory-boundary-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check: one adapter point (scan over is_shipped paths, control fails when planted); memory off leaves
    briefs byte-identical (test_memory_off_parity.py) and /task and /journal-add untouched; unavailable
    and hung server give one line and continue; every server field neutralised (probe tests); no item
    reaches the architect before the user's applicability answer; provenance never stronger than the
    table; registry text is read only through the extended shared reader in generate_registry_digest.py
    (digest byte-identical, hook a thin normal-import caller, no importlib); candidates only from entries
    whose own line names the contract; capture only in step 5a after a live flipped run, refusing
    brief-not-carried before any send; capture is its own question after the flip on both /pr-merged
    and /flow, and the records confirmation (step 3 / Step 8) is unchanged and still before the writing
    run; the stop rule holds; receipts carried by the records pull request; the Step 1.5 and capture
    stops are listed in /flow; the scan walks named folders and excludes .claude/worktrees/; no frontmatter key, hook, store or
    background process added; each part names its existing mechanism as in Reused Mechanisms.
  - Six fixed sections; the file does not exist yet and you create it. Name base..head.
  - Verdict line alone, exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings",
    "**Verdict:** blocked". Write the Gate Output <artefact stem>.gate.json beside it.
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
