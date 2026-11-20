---
id: 463
issue_offer: opened
title: Security re-review, round four
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/463
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t14-security-re-review-round-four
worktree: none
north_stars: inherited from .claude/work-items/2026-11-16-file-based-switches.md
parent_issue: 419
base: feature/file-based-switches
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-20
---

# Security re-review, round four

## Problem statement
Sub-task 14 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 14. Security re-review, round four (`security-auditor`)

**Depends on:** 13 — it re-reviews the findings of blocks 4, 10 and 12, but names none of them, because all three records read `blocked`.

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t14-security-re-review-round-four-security-auditor.md`

**Gate Output, written beside the artefact by the same agent and deliberately not listed above:** `.claude/reviews/2026-11-16-file-based-switches/t14-security-re-review-round-four-security-auditor.gate.json`, for the same reason as blocks 9, 10 and 12. It is the file whose `supersedes` list retires the t4, t10 and t12 reports.

**Pre-written TASK block:**
```
TASK: Re-review the database override, the human-only classifier and both database guards'
  audit writes after the third fixes block, and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (amendment 3:
  the No-prompt classes rule, the Audit-log rule, Failure Modes, the residual-risk paragraph,
  and the user's answers to the amendment 3 Open Questions); the blocked reports
  .claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md,
  t10-security-re-review-security-auditor.md and
  t12-security-re-review-round-three-security-auditor.md; the second run sheet
  t9-live-prompt-trial-second-round-senior-test-engineer.md. Naming: keep the t12 report's
  naming. "P1 to P9" are t4's shared-claim and fallback probes; "finding P1" and "finding P2"
  are t12's findings; t12's findings N5 and N6 are not its probe shapes N5 and N6. Say which
  one you mean each time.
FILES: .claude/reviews/2026-11-16-file-based-switches/t14-security-re-review-round-four-security-auditor.md
CONSTRAINTS:
  - Name the commit range reviewed, base..head: the third fixes block's (13) merge into the
    parent branch. Say whether the reviewed guard and helper files differ between that merge
    and your head. Work in scratch copies under %TEMP% (git archive or a clone), not in a
    worktree under the checkout.
  - Re-run every probe that failed in t4, t10 and t12, in its ORIGINAL clause order and spelling,
    in each shell the probe exists in, armed and unarmed as the report ran it: t4's O10, O12,
    O14, R3, R4, S5; t10's O13, O13e, H1, H3 to H7 and the Disposition's cd and Write-Host
    forms; t12's B1 and P1 shapes N1, N1a, N1b, N1c, N2, N2a, N2b, N3 to N6, N15 and K4 to K6;
    t12's P2 shapes N7 to N13 and K1 to K3, and block 13's per-word and valued-option rows.
    The destructive guard must block each; command -v and command -V <script> must stay
    allowed. Report the read-only guard's outcome beside each (L1 is accepted: armed, it asks
    on the shapes with a database write), and state what evidence there is for "a hook block
    beats a hook ask" (block 12's instruction, kept). Also run each new
    shape in a real bash and a real PowerShell with a harmless probe script, as t12 did, and
    report any shape where the real shell runs the script and the guard does not block.
  - Try further spellings of the same rule in both shells (other escapes, nested quotes, here
    strings, line continuations) and report what you find. Also try mentions that one shell
    would not run (a backtick-wrapped name in PowerShell, an escaped name in a commit message)
    and report each new false block; the union reading's false block is accepted in Failure
    Modes, but a mention row from MENTION_ROWS that now blocks is a finding.
  - Re-run the quoted-launcher rows (bash -c, sh -c, cmd /c, cmd /k, powershell -Command,
    pwsh -c, iex, Invoke-Expression): they must block. Re-run the mention controls: they must
    stay allowed. Then re-run the whole override decision set (O0 to O20), the whole route
    table, and t4's shared-claim and fallback probes P1 to P9. Report each with its result at
    head.
  - Real pipe-link attempts on this Windows host, each with a listening named pipe, in the \\.\
    and \\?\ spellings, links made by os.symlink and by cmd /c mklink: W4 at switches.local.json
    (the helper finishes at once with every default); I1 at the rules file, for both database
    guards, with the helper present, deleted and stale; I2 at <project>/.claude/logs/db-guard.log
    (destructive guard) AND at <project>/.claude/logs/db-research.log (read-only guard), each
    with a pipe that accepts and never reads: each guard finishes within a short timeout with
    its normal decision on its block path. Also, for each guard: a directory link at
    .claude/logs (into the pipe namespace and to another local folder), and a linked log over
    the size limit (rotation must neither rename nor remove the link target). If a link cannot
    be created, say so; that is not a pass.
  - Check the contract's Residual risk paragraph (it must close B1, P1, P2 and I2 (both guards)
    or name what stays open, carry the corrected L1 sentence, the t9 limits, W3 (a) and (b)) and
    the Failure Modes dispositions (W4, B1, P1, P2, I2, the union reading's false block, the
    skipped audit record, I1 and its neighbours, L1, t9 steps 7 to 9, N6, W5, N2, N3).
  - Run the guard suites verbatim and record each exit code: test_switches.py,
    test_database_override.py, test_db_destructive_guard.py, test_db_guard_path_allowlist.py,
    test_readonly_guard_disposable_exemption.py, test_worktree_path_guards.py,
    test_shell_write_targets.py, test_switch_env_scan.py.
  - Name destructive statements in words, never as literal command text. Write the artefact in
    the template's six-section shape; the file does NOT exist yet. End the header with one
    verdict line, alone on its line: "**Verdict:** pass", "**Verdict:** pass-with-findings" or
    "**Verdict:** blocked".
  - Write the Gate Output t14-security-re-review-round-four-security-auditor.gate.json beside
    it, as the template says. On pass or pass-with-findings its supersedes list is exactly
    ["t4-security-review-security-auditor.md", "t10-security-re-review-security-auditor.md",
    "t12-security-re-review-round-three-security-auditor.md"]. On blocked it is [] (a report
    that failed to clear a blocker must not retire one).
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
