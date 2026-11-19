---
id: 444
issue_offer: opened
title: Security re-review
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/444
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t10-security-re-review
worktree: none
north_stars: inherited from .claude/work-items/2026-11-16-file-based-switches.md
parent_issue: 419
base: feature/file-based-switches
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: none
issue_link: deferred
status: implementing
created: 2026-11-18
---

# Security re-review

## Problem statement
Sub-task 10 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 10. Security re-review (`security-auditor`)

**Depends on:** 8, 9

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t10-security-re-review-security-auditor.md`

**Gate Output, written beside the artefact by the same agent and deliberately not listed above:** `.claude/reviews/2026-11-16-file-based-switches/t10-security-re-review-security-auditor.gate.json`, for the same reason as block 9. It is the file whose `supersedes` list retires the t4 report.

**Pre-written TASK block:**
```
TASK: Re-review the database override after the fixes block and the second live trial, and
  write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md; the blocked
  report .claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md;
  the second run sheet t9-live-prompt-trial-second-round-senior-test-engineer.md.
FILES: .claude/reviews/2026-11-16-file-based-switches/t10-security-re-review-security-auditor.md
CONSTRAINTS:
  - Name the commit range reviewed, base..head: the fixes block's merge into the parent branch.
    Record the commit the t9 run sheet says it ran against, and say whether the reviewed guard
    files differ between that commit and your head.
  - Re-run the t4 probes that failed (O10, O12, O13, O14, R3, R4, S5) and the whole route table;
    check W4 by reading, and by running the named-pipe row if a POSIX host is available.
  - Read the t9 observations. If step 6 shows that an allow rule skipped the prompt, the
    verdict is blocked. Check that acceptEdits, plan and dontAsk behave as the Person-present
    rule says.
  - Check that the contract's Residual risk paragraph now names every class you know of,
    including W3(a) and W3(b), and that W5, N2 and N3 are dispositioned in Failure Modes.
  - Write the artefact in the template's six-section shape; the file does NOT exist yet. End the
    header with one verdict line, alone on its line: "**Verdict:** pass",
    "**Verdict:** pass-with-findings" or "**Verdict:** blocked".
  - Write the Gate Output t10-security-re-review-security-auditor.gate.json beside it, as the
    template says. On pass or pass-with-findings its supersedes list is exactly
    ["t4-security-review-security-auditor.md"]. On blocked it is [] (a report that failed to
    clear a blocker must not retire it); the next re-review then supersedes both blocked reports.
  - A blocked verdict holds blocks 6 and 7. It leads to an architect amendment of this
    contract that adds a further fix block and a further re-review block, as this round did;
    no block is added without that amendment. If the block comes from step 6 of t9 (an allow
    rule skipped the prompt), the amendment withdraws the override instead (user answer
    2026-11-18).
  - Edit no other report. Do not touch any plugin version file.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

---

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md - dispatched by /advance
