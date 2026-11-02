---
id: 192
issue_offer: opened
title: Re-review cloud capability
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/192
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t13-re-review-cloud-capability
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/196
issue_link: deferred
status: shipped
created: 2026-11-02
---

# Re-review cloud capability

## Problem statement
Sub-task 13 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 13. Re-review cloud capability (`fullstack-code-reviewer`)

**Depends on:** 6, 7, 12

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t13-re-review-cloud-capability-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 6, 7 and 12 afresh and write the review artefact. This review supersedes the block 8 review.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md (Revision 6)
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t13-re-review-cloud-capability-fullstack-code-reviewer.md
CONSTRAINTS:
  - Start from a cold context. Do not read the block 8 review before forming your own findings; read it
    afterwards only to confirm that B1 and W3 are cleared.
  - Check the same list as block 8: capability off while cloud.providers is unset; only selected references load,
    on both the skill path and the agent path; the cloud scope rule is stated in both the skill and the agent;
    no shipped cloud text instructs a mutating command (test_cloud_text_scans.py, control fails when planted);
    no settings file, permission row, hook or finish-install change was added; database guards untouched;
    the Cloud coverage table in Appendix A.6 is true.
  - Six fixed sections, base..head named, verdict line exactly "**Verdict:** pass",
    "**Verdict:** pass-with-findings" or "**Verdict:** blocked". Write the Gate Output beside it, and set its
    supersedes field to the block 8 review artefact.
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
