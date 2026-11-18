---
id: 423
issue_offer: opened
title: Security review
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/423
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t4-security-review
worktree: none
north_stars: inherited from .claude/work-items/2026-11-16-file-based-switches.md
parent_issue: 419
base: feature/file-based-switches
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/440
issue_link: deferred
status: shipped
created: 2026-11-16
---

# Security review

## Problem statement
Sub-task 4 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 4. Security review (`security-auditor`)

**Depends on:** 2, 3

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md`

**Pre-written TASK block:**
```
TASK: Review the helper block as a safety-critical change, and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md.
FILES: .claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md
CONSTRAINTS:
  - Check each override rule against the code. Try to create the arm as an agent by every route
    you can think of (Write, Edit, shell redirection, encoded or joined paths, a script file).
    Name each route and whether the guard saw it.
  - Check that no path allows a destructive command without a prompt, that the stated residual
    risk is complete, that the prompt reason is neutralised, and that the live trial run sheet's
    observations support the Person-present rule.
  - Check the Broken-file and No-environment rules: no broken or missing file, and no missing
    helper, turns a guard off.
  - Write the artefact in the template's six-section shape. The file does NOT exist yet; you
    create it. Name the commit range reviewed, base..head. "## Evidence" lists the commands run
    with exit codes. End the header with one verdict line, alone on its line:
    "**Verdict:** pass", "**Verdict:** pass-with-findings" or "**Verdict:** blocked".
  - Also write the Gate Output <artefact stem>.gate.json beside it, as the template says.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md — dispatched by /advance
