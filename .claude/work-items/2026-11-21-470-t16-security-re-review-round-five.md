---
id: 470
issue_offer: opened
title: Security re-review, round five
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/470
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t16-security-re-review-round-five
worktree: none
north_stars: inherited from .claude/work-items/2026-11-16-file-based-switches.md
parent_issue: 419
base: feature/file-based-switches
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-21
---

# Security re-review, round five

## Problem statement
Sub-task 16 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 16. Security re-review, round five (`security-auditor`)

**Depends on:** 15 — it re-reviews the findings of blocks 4, 10, 12 and 14, but names none of them, because all four records read `blocked`.

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t16-security-re-review-round-five-security-auditor.md`

**Gate Output, written beside the artefact by the same agent and deliberately not listed above:** `.claude/reviews/2026-11-16-file-based-switches/t16-security-re-review-round-five-security-auditor.gate.json`, for the same reason as blocks 9, 10, 12 and 14. It is the file whose `supersedes` list retires the t4, t10, t12 and t14 reports.

**Pre-written TASK block:**
```
TASK: Re-review the database override, the human-only classifier, the comment-aware prose
  masker and both database guards' audit writes after the fourth fixes block, and write the
  review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (amendment 4:
  the No-prompt classes rule, the Audit-log rule, Failure Modes, the residual-risk paragraph,
  Non-Goals, and the user's answers to the amendment-4 Open Questions); the blocked reports
  .claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md,
  t10-security-re-review-security-auditor.md,
  t12-security-re-review-round-three-security-auditor.md and
  t14-security-re-review-round-four-security-auditor.md; the second run sheet
  t9-live-prompt-trial-second-round-senior-test-engineer.md. Naming: keep the t14 report's
  naming. "P1 to P9" are t4's shared-claim and fallback probes; "finding P1", "finding P2"
  and "finding P3" are t14's findings; t12's findings N5 and N6 are not its probe shapes N5
  and N6. Say which one you mean each time.
FILES: .claude/reviews/2026-11-16-file-based-switches/t16-security-re-review-round-five-security-auditor.md
CONSTRAINTS:
  - Name the commit range reviewed, base..head: the fourth fixes block's (15) merge into the
    parent branch. Say whether the reviewed guard and helper files differ between that merge
    and your head. Work in scratch copies under %TEMP% (git archive or a clone), not in a
    worktree under the checkout.
  - Re-run every probe that failed in t4, t10, t12 and t14, in its ORIGINAL clause order and
    spelling, in each shell the probe exists in, armed and unarmed as the report ran it:
    t4's O10, O12, O14, R3, R4, S5; t10's O13, O13e, H1, H3 to H7 and the Disposition's cd and
    Write-Host forms; t12's N1 to N6, N1a to N1c, N2a, N2b, N15, K1 to K6 and N7 to N13; block
    13's per-word and valued-option rows; t14's A1, A1p, X1e, X3a, X3h, X1, X1c, X1d, X1p, X3,
    X3b, X3f, X3g, X3i, X41 to X45, A41, X4 to X11, X13, X14, X16, X18 to X20, X53, X86, X87b,
    X88b, X89b, A4, A7, A10, A11, A13, A53, X21, X21b, X22, X22p, X23, X24, A21, and D1 to D6
    and D8 (Q1 is in block 15 by the user's answer of 2026-11-21). The destructive guard must
    block each, except D8, which must give the normal armed ask with the arm claimed. Also
    re-run block 15's arm-write comment rows in BOTH guards (each must refuse the arm write),
    its escape and here-document rows, its cross-shell continuation rows, and its multi-hop
    pipe, substitution, argument-rule and Environment-rule rows. Report the
    read-only guard's outcome beside each (L1 is accepted: armed, it asks on the shapes with a
    database write), and state what evidence there is for "a hook block beats a hook ask"
    (block 12's instruction, kept). Also run each t14 shape and each new class row of block 15
    in a real bash and a real PowerShell with a harmless probe script, as t14 did, and report
    any shape where the real shell runs the script and the guard does not block.
  - Try further spellings of the two t14 classes (a # comment with an apostrophe before the
    target line; a quote opened mid-word before the name) in both shells, of the masker
    exclusions (every here-document and here-string spelling, --%, # inside a word,
    <# ... #>), and of a # that one shell reads inside a quote or a word because of an
    escape (escaped quotes, escaped spaces, $'…', doubled quotes), each in the destructive,
    human-only and arm-write forms. The classifier is inverted by the user's answer of
    2026-11-21: try mentions after read commands outside the list and report each false
    block; the inverted classifier's false block is accepted in Failure Modes, but a
    must-stay-allowed row that now blocks is a finding, and an occurrence the guard classes
    as a mention while a real shell runs the script is a finding. Try each listed mention
    word's own options for one that runs a program (as rg --pre and git grep -O do), longer
    pipelines and nested substitutions, and continuations read by the other shell.
  - Trust boundary: the residual-risk paragraph names a text-guard limit for the human-only
    class (a name built at run time: concatenation, a variable, -EncodedCommand, a copy under
    another name; a listed command turned into a launcher by configuration written outside
    the call's text; a shell other than bash and PowerShell). A shape inside that limit is
    reported as information, not a finding, unless it is wider than the paragraph states. A
    shape outside it is a finding. A listed mention word that runs a program from its own
    arguments or from an environment change in the same call is outside the limit, so it is
    a finding.
  - Re-run the quoted-launcher rows (bash -c, sh -c, cmd /c, cmd /k, powershell -Command,
    pwsh -c, iex, Invoke-Expression): they must block. Re-run the mention controls
    (MENTION_ROWS, t14's CV1, CV2, CW1 to CW5, M1c, M2, M2p, M3, M3b): they must stay allowed.
    Then re-run the whole override decision set (O0 to O20), the whole route table, and t4's
    shared-claim and fallback probes P1 to P9. Report each with its result at head.
  - Real link attempts on this Windows host: W4 at switches.local.json and I1 at the rules
    file, as t14 ran them (both spellings, os.symlink and cmd /c mklink, the helper present,
    deleted and stale); I2 at db-guard.log and db-research.log (pipe link, folder links,
    rotation on a linked log and a linked .1), as t14 ran them; and L2: a hard link at each
    log to a file outside .claude/logs, which must receive no record. If a link cannot be
    created, say so; that is not a pass.
  - Check the contract's Residual risk paragraph (it must close B1, P1, P2, P3, T1, L2, Q1
    and the arm-write comment route, or name what stays open; carry the text-guard limit,
    the corrected L1 sentence, the t9 limits, W3 (a) and (b)) and the Failure Modes
    dispositions (the t14 B1 and P1 entry, Q1, the comment-aware masker's loosening, the
    arm-write comment route, cross-shell continuation joining, P2, P3, the inverted
    classifier's false block, mention commands that can run a program, the pipeline beyond
    one hop, T1, L2, and every earlier entry t14 checked).
  - Run the guard suites verbatim and record each exit code: test_switches.py,
    test_database_override.py, test_db_destructive_guard.py, test_db_guard_path_allowlist.py,
    test_readonly_guard_disposable_exemption.py, test_worktree_path_guards.py,
    test_shell_write_targets.py, test_switch_env_scan.py.
  - Name destructive statements in words, never as literal command text. Write the artefact in
    the template's six-section shape; the file does NOT exist yet. End the header with one
    verdict line, alone on its line: "**Verdict:** pass", "**Verdict:** pass-with-findings" or
    "**Verdict:** blocked".
  - Write the Gate Output t16-security-re-review-round-five-security-auditor.gate.json beside
    it, as the template says. On pass or pass-with-findings its supersedes list is exactly
    ["t4-security-review-security-auditor.md", "t10-security-re-review-security-auditor.md",
    "t12-security-re-review-round-three-security-auditor.md",
    "t14-security-re-review-round-four-security-auditor.md"]. On blocked it is [] (a report
    that failed to clear a blocker must not retire one).
  - A blocked verdict holds blocks 6 and 7. It leads to an architect amendment of this
    contract, which either adds a further fix block and a further review block, as this round
    did, or records the remaining shapes as stated residuals with the user's agreement. No
    block is added without that amendment.
  - Edit no other report. Do not touch any plugin version file.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

---

---

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md - dispatched by /advance
