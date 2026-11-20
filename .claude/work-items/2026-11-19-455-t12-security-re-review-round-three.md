---
id: 455
issue_offer: opened
title: Security re-review, round three
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/455
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t12-security-re-review-round-three
worktree: none
north_stars: inherited from .claude/work-items/2026-11-16-file-based-switches.md
parent_issue: 419
base: feature/file-based-switches
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/459
issue_link: deferred
status: shipped
created: 2026-11-19
---

# Security re-review, round three

## Problem statement
Sub-task 12 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 12. Security re-review, round three (`security-auditor`)

**Depends on:** 11 — it re-reviews the findings of blocks 4 and 10, but names neither, because both records read `blocked`.

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t12-security-re-review-round-three-security-auditor.md`

**Gate Output, written beside the artefact by the same agent and deliberately not listed above:** `.claude/reviews/2026-11-16-file-based-switches/t12-security-re-review-round-three-security-auditor.gate.json`, for the same reason as blocks 9 and 10. It is the file whose `supersedes` list retires the t4 and t10 reports.

**Pre-written TASK block:**
```
TASK: Re-review the database override and the switch reader after the second fixes block, and
  write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md; the blocked
  reports .claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md
  and t10-security-re-review-security-auditor.md; the second run sheet
  t9-live-prompt-trial-second-round-senior-test-engineer.md.
FILES: .claude/reviews/2026-11-16-file-based-switches/t12-security-re-review-round-three-security-auditor.md
CONSTRAINTS:
  - Name the commit range reviewed, base..head: the second fixes block's (11) merge into the
    parent branch. Say whether the reviewed guard and helper files differ between that merge and
    your head. Work in scratch copies under %TEMP% (git archive or a clone), not in a worktree
    under the checkout.
  - Re-run every t4 and t10 probe that failed, in its ORIGINAL clause order, with the folder
    path of the script, in the bash form and the PowerShell form where the probe exists in both
    (O13e, H3 and the Write-Host form exist in PowerShell only): O13, O13e, H1, H3, H4, H5, H6,
    H7, the t10 Disposition's cd and Write-Host forms, and t4's O10, O12, O14, R3, R4 and S5.
    The destructive guard must block each; report the read-only guard's outcome beside it (L1
    is accepted: armed, it asks on the shapes with a database write), and state what evidence
    there is for "a hook block beats a hook ask". Also run the quoted-launcher rows
    (bash -c "cd x; <script>", cmd /c, powershell -Command): they must block. Then re-run the whole override
    decision set (O0 to O20), the whole route table, the shared-claim and fallback probes (P1 to
    P9), and the control rows (script mentioned inside quotes stays allowed). Report each with
    its result at head.
  - Check W4 by a real attempt on this Windows host: a symbolic link at switches.local.json to
    a listening named pipe, in the \\.\ and \\?\ spellings; the helper must finish at once with
    every default. Check I1 the same way at the rules file, for both database guards, with the
    helper present, deleted and stale. If a link cannot be created, say so; that is not a pass.
  - Check the contract's Residual risk paragraph (W3 (a) and (b) as amended, the t9 limits, the
    Windows pipe-link route) and the Failure Modes dispositions (W4, B1, P1, I1, L1 accepted,
    t9 steps 7 to 9 residual, W5, N2, N3). As information, list other hooks that read a rules
    file with a plain open (same class as I1, out of this contract's scope).
  - Run the guard suites verbatim and record each exit code: test_switches.py,
    test_database_override.py, test_db_destructive_guard.py, test_db_guard_path_allowlist.py,
    test_readonly_guard_disposable_exemption.py, test_worktree_path_guards.py,
    test_shell_write_targets.py, test_switch_env_scan.py.
  - Write the artefact in the template's six-section shape; the file does NOT exist yet. End the
    header with one verdict line, alone on its line: "**Verdict:** pass",
    "**Verdict:** pass-with-findings" or "**Verdict:** blocked".
  - Write the Gate Output t12-security-re-review-round-three-security-auditor.gate.json beside
    it, as the template says. On pass or pass-with-findings its supersedes list is exactly
    ["t4-security-review-security-auditor.md", "t10-security-re-review-security-auditor.md"].
    On blocked it is [] (a report that failed to clear a blocker must not retire one).
  - A blocked verdict holds blocks 6 and 7. It leads to an architect amendment of this
    contract that adds a further fix block and a further review block, as this round did; no
    block is added without that amendment.
  - Edit no other report. Do not touch any plugin version file.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

---

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md - dispatched by /advance
