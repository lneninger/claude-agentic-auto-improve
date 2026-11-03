---
id: 206
issue_offer: opened
title: Re-review memory boundary
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/206
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t16-re-review-memory-boundary
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/215
issue_link: deferred
status: shipped
created: 2026-11-02
---

# Re-review memory boundary

## Problem statement
Sub-task 16 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 16. Re-review memory boundary (`fullstack-code-reviewer`)

**Depends on:** 2, 3, 4, 14, 15

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t16-re-review-memory-boundary-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 2, 3, 4, 14 and 15 afresh and write the review artefact. This review supersedes the block 5 review.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md (Revision 7)
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t16-re-review-memory-boundary-fullstack-code-reviewer.md
CONSTRAINTS:
  - Start from a cold context. Do not read the block 5 review before forming your own findings. Read it
    afterwards only to confirm that B1, W1, W2 and W3 are cleared and that I1 and I2 are handled.
  - Check the same list as block 5. Then check Revision 7: record writes the unconfigured line and
    refuses only disabled (and --receipts unless enabled); the skill no longer documents a refusal as
    expected; receipts carry <file>:<line> from the real capture-candidates output; changed-items gets
    the normalised file and applies the normalise rules; Triggers map only by exact canonical value; a
    trailing note paragraph is no entry's text; --default-branch is not hard-coded and, when unset, is
    read with default_branch_or_none(cwd=<project>) or refused as default-branch-unknown; the unconfigured
    path records into the brief whose branch: is the current branch and treats a missing brief as a
    skipped line, not a failure; the three I-M0 disabled tests are unchanged.
  - Check block 15: finish-install, /design-first Step 1.5 and its reference, and the new shipped
    agreement state that the Project history record is the project's record and that the Central Memory
    System only supplements it; the finish-install text says exactly who appends (no "on every run"
    claim); finish-install runs the doctor in report mode, shows what --fix would create, and runs --fix
    only on the user's yes; every Step 1.5 printed line carries the suffix; the disabled path still prints
    and writes nothing (I-M0, test_memory_off_parity.py); no change to plugin_doctor.py or
    memory_boundary.py from block 15; test_working_agreements.py names the new file and the set fits the
    limit; no store, seed, hook or frontmatter key added.
  - Six fixed sections; the file does not exist yet and you create it. Name base..head.
  - Verdict line alone, exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings",
    "**Verdict:** blocked". Write the Gate Output <artefact stem>.gate.json beside it, and set its
    supersedes field to the block 5 review artefact.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

---

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
