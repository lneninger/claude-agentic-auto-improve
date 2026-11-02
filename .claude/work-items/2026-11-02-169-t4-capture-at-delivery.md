---
id: 169
issue_offer: opened
title: Capture at delivery
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/169
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t4-capture-at-delivery
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

# Capture at delivery

## Problem statement
Sub-task 4 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 4. Capture at delivery (`python-ai-developer`)

**Depends on:** 3

**Files to touch:**
- `skills/pr-merged/references/contract-completion.md`
- `skills/pr-merged/SKILL.md`
- `skills/flow/SKILL.md`
- `.claude/scripts/tests/test_skill_script_lookup.py`
- `.claude/scripts/tests/test_parent_branch_rule_text.py`

**Pre-written TASK block:**
```
TASK: Add step 5a "Capture" to references/contract-completion.md exactly as Extension Points describes. It
  runs only when capture is enabled and only AFTER a live writing run returned "flipped" for this contract,
  whatever the dry run said. Step 3's confirmation is unchanged. Run capture-candidates --run-report
  <the report> (the JSON of the writing run that flipped); on not-flipped or brief-not-carried print one
  line and go on, sending nothing. Otherwise ask the separate capture question (candidates, provenance,
  scope, lowerings), send confirmed candidates in order with the stop rule, then record --receipts
  --run-report <the report> into the linked brief before step 7's copy. In contract-completion.md, amend
  the sentence "the confirmation always comes before any writing run" and the /flow sentence (line 59)
  so they also say: "when memory capture is enabled and candidates exist, one separate capture question
  follows the writing run that flipped". In skills/flow/SKILL.md, amend the closing paragraph (line 591,
  "Step 8's confirmation as the one confirmation") and Step 8 with the same sentence: Step 8's
  confirmation stays BEFORE the writing run and is unchanged; the capture question comes after that run
  flips, and Step 8 commits the brief only after receipts are recorded. Add the capture question to
  "Always the operator's call". pr-merged reads ../design-first/references/central-memory.md.
CONTEXT: concept contract (Provenance mapping, Candidate reading, Duplicate protection, Capture receipt,
  route table).
FILES: the five listed.
CONSTRAINTS:
  - Capture is never built from a dry run and never folded into the records confirmation, on either route.
    Exactly one capture question, only when there are candidates. Never capture without the owner's
    answer in this run.
  - Stop rule: at the first send failure or timeout, stop sending, write the rest as "Not sent: (stopped
    after <reason>)", continue delivery. No outcome of capture blocks the records pull request.
  - Keep every sentence test_parent_branch_rule_text.py pins in flow, pr-merged and contract-completion.md;
    where an amended sentence is pinned, update the pin in the same block and say why.
  - skills/journal-add/SKILL.md is NOT touched.
  - flow is a repository-owned skill: keep any sync test over it passing.
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
