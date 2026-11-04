---
id: 173
issue_offer: opened
title: Review cloud capability
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/173
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t8-review-cloud-capability
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/188
issue_link: deferred
status: shipped
created: 2026-11-02
---

# Review cloud capability

## Problem statement
Sub-task 8 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 8. Review cloud capability (`fullstack-code-reviewer`)

**Depends on:** 6, 7

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t8-review-cloud-capability-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 6-7 and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t8-review-cloud-capability-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check: capability off while cloud.providers is unset; only selected references load; the cloud scope
    rule is stated in both the skill and the agent; no shipped cloud text instructs a mutating command
    (test_cloud_text_scans.py, control fails when planted); no settings file, permission row, hook or
    finish-install change was added (Decision note, Revision 5); database guards untouched;
    the Cloud coverage table in Appendix A.6 is now true.
  - Six fixed sections, base..head named, verdict line exactly "**Verdict:** pass",
    "**Verdict:** pass-with-findings" or "**Verdict:** blocked"; write the Gate Output beside it.
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
