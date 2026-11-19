---
id: 454
issue_offer: opened
title: Security review fixes, round two
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/454
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t11-security-review-fixes-round-two
worktree: none
north_stars: inherited from .claude/work-items/2026-11-16-file-based-switches.md
parent_issue: 419
base: feature/file-based-switches
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/457
issue_link: deferred
status: shipped
created: 2026-11-19
---

# Security review fixes, round two

## Problem statement
Sub-task 11 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 11. Security review fixes, round two (`python-ai-developer`)

**Depends on:** 8 — it fixes the findings of the re-review (block 10), but does not name block 10, because the loop never releases a block whose dependency reads `blocked` (the same convention as block 8 and block 4).

**Files to touch:**
- `.claude/hooks/db-destructive-guard.py`
- `.claude/hooks/db-research-readonly-guard.py`
- `.claude/hooks/_switches.py`
- `.claude/hooks/tests/test_database_override.py`
- `.claude/hooks/tests/test_switches.py`
- `.claude/hooks/tests/test_db_destructive_guard.py`

`db-research-readonly-guard.py` is listed only for I1 (it reads the same rules file with a plain open, `:207`; user answer 2026-11-19: include I1). L1 is accepted, so its decision code is not changed. `test_db_destructive_guard.py` is listed only so a row that pins one of the P1 shapes as allowed can be retired by name (see the constraints); no other change to it is allowed. The rules-file reader is the switch helper's regular-file check, exposed under a public name, so no new helper file is added.

**What the rows prove, plainly (user answer 2026-11-19, "Test the destructive guard alone").** The destructive guard is the deciding guard for B1 and P1, and only its rows expect a block. The read-only guard has no human-only class and is not changed: its rows pin today's accepted behaviour (L1), which is that armed, on a shape that holds a database write, it asks and claims the arm, and on a shape with no database statement it allows, armed or not. This contract does **not** claim that both guards block these shapes. In a live session both guards run on one call, so an armed O13 or H7 spends the person's arm on the read-only guard's ask while the destructive guard blocks; whether the host then shows a prompt rests on the ASSUMED "a block beats an ask" (Uncertain Assumptions).

**Pre-written TASK block:**
```
TASK: Fix findings B1, P1, W4 (Windows) and I1 of the security re-review, each with test rows,
  and nothing else.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (the No-prompt
  classes rule's invoked-or-mentioned sentence, the Broken-file rule, the Guard rules file entry
  under Reused Mechanisms, Failure Modes); the re-review
  .claude/reviews/2026-11-16-file-based-switches/t10-security-re-review-security-auditor.md
  (findings B1, P1, W4, I1; the "Human-only placement" table H1 to H7, O13, O13b, O13e; the
  Disposition) and the first review t4-security-review-security-auditor.md (B1, probes O11 to
  O14). Read both reports in full. Their clause order and script paths are exact; their
  destructive statements are named in words by the reports' own rule, so rebuild each one from
  those words by string joining, as the existing rows do.
FILES: as listed. db-research-readonly-guard.py changes only for I1.
CONSTRAINTS:
  - RED before GREEN, in this one block (the block 8 convention): commit the new rows first, run
    them at the parent tip, and list in the pull request body each new row with its outcome at
    the tip and at your head. Every destructive-guard row copied from a reported probe (the
    "Copied probes" list below) and every hang row MUST fail (or time out) at the tip. A copied
    probe that passes at the tip has been mistranscribed (script first, or a bare script name
    with no folder): fix the row until it fails at the tip; never relabel it a control. The only
    rows allowed to pass at the tip are the ones this TASK names as controls or pins. The fix
    commit comes after.
  - B1 and P1: fix the classifier, not the decision. Change _in_command_position (and only what
    _human_only_script_hits needs from it) so the No-prompt classes rule's sentence holds. The
    change may only turn a mention into an invocation; every shape the tip classes as invoked
    stays invoked. Text inside the quoted argument of a known launcher (bash -c, sh -c, cmd /c,
    cmd /k, powershell -Command, -c, iex, Invoke-Expression) is command text: split it into
    segments the same way, and a script that starts a segment there is invoked. Do not change
    the human_only flag in _decide, which block 8 got right.
  - Script spelling in every row: the folder path, never the bare name, because the defect needs
    a folder separator before the name: tools/db-protection/update-dev-database.cmd (forward
    slashes) in the bash rows, tools\db-protection\update-dev-database.cmd in the PowerShell
    rows. A probe that exists in one shell only (O13e, H3, Write-Host 'x'; <script>) is written
    once, in that shell. A row with && keeps it as written: the guard judges text, and Windows
    PowerShell 5.1 not running && does not change the guard's verdict.
  - Copied probes, the destructive guard alone, each row in its own fresh temporary project with
    its own arm (never both guards on one arm):
      armed, default mode, expect exit 2, no ask JSON, the arm still in place, the human-only
      instruction in the block text: O13 (row delete on a protected database, then ";", then
      the script), O13e (its PowerShell form), H7 (removal of a non-disposable database
      through sqlcmd -Q, then ";", then the script), H6 (echo "a" ; the script), and the t10
      Disposition's cd "<p>" && the script and Write-Host 'x'; the script.
      no arm, expect exit 2 (blocked, not allowed): H1 echo "start" ; the script; H3 PowerShell
      Write-Host 'x'; the script; H4 cd "<p>" && the script; H5 echo "a" && the restore script
      with its recover flag.
  - Read-only guard pins (L1, accepted; today's behaviour, expected the same at the tip and at
    head, and named as pins in the pull request body): armed, O13, O13e and H7 give the ask JSON
    and the arm renamed to the claim; armed, H6 and the cd and Write-Host forms give exit 0 and
    the arm kept; no arm, H1, H3, H4 and H5 give exit 0. No row expects the read-only guard to
    block these shapes.
  - Controls (destructive guard, pass at the tip and at head): O11 (the script alone), O12,
    O13b (script first) and O14 block; invoked inside a quoted launcher argument blocks, with no
    arm: bash -c "cd x; <script>", cmd /c "echo a & <script>",
    powershell -Command "Write-Host x; <script>". Must stay allowed: a commit message, an echo
    text, a grep pattern and a pull request body that name the script inside quotes; the script
    name as an argument of another command.
  - Existing guard suites unchanged and green: test_db_destructive_guard.py,
    test_db_guard_path_allowlist.py, test_readonly_guard_disposable_exemption.py,
    test_worktree_path_guards.py, test_shell_write_targets.py, test_switch_env_scan.py, and the
    db-protection fixture suite. If a row there expects ALLOW for one of the P1 shapes (a
    human-only script invoked after quoted text), it pins the defect: retire it by name in
    test_db_destructive_guard.py, replace it with the blocking row, and name both in the pull
    request body. Any other row that changes outcome: stop and report an AMENDMENT; do not edit
    it.
  - W4 (Windows): in _read_regular_file_bytes, on every platform open with os.open (O_RDONLY,
    plus O_BINARY and O_NONBLOCK where they exist), then os.fstat on the descriptor, and close it
    unread unless S_ISREG; anything else is unreadable under the Broken-file rule. Keep the
    link-target check before the open, and fix _network_link_reason so a device-namespace target
    (\\.\..., or \\?\... not followed by a drive letter) is unreadable and never opened, instead
    of being read as a relative local path. Rows, Windows only: a symbolic link at
    switches.local.json to a listening named pipe (for example a
    multiprocessing.connection.Listener on \\.\pipe\<unique name> that accepts and never
    writes), in the \\.\ and the \\?\ spelling, gives every default and one report, with the
    hook run as a separate process under a short timeout so the row fails instead of hanging.
    Skip with the stated reason "symbolic link creation not permitted on this host" when
    os.symlink raises a privilege error; skip on POSIX with the reason that the POSIX
    named-pipe rows cover it. Keep the POSIX named-pipe rows green.
  - Expose the reader under the public name read_regular_file_bytes (the Commands row "Read
    regular file"); keep the private name as an alias for the helper's own callers.
  - I1 (user answer 2026-11-19: yes): both database guards read db-destructive-guard.rules.json
    through the same check. Bind the helper's read_regular_file_bytes with getattr; keep an
    inline fallback copy in each guard (Guard fallback mode), because the rules load at import
    and must fail closed with the helper missing. Each inline copy keeps BOTH parts: the Windows
    link-target check (network drive, \\server\share, device namespace) and the
    open-then-fstat regular-file check. A file that fails the check takes the loader's existing
    fail-closed result: the destructive guard treats every database as protected, the read-only
    guard withdraws the disposable exemption. A regular file decodes exactly as today. Rows,
    per guard: a pipe link at the rules file (the same Windows skip rules) makes the guard
    finish within the short timeout with its strict-default outcome (the destructive guard
    blocks a removal of a non-disposable database; the read-only guard blocks a write on a
    disposable-named database it would exempt today); a rules file that is a link to a
    \\server\share path takes the same strict default (accepted fail-closed behaviour, Failure
    Modes I1); a regular rules file still loads as before.
  - Fallback rows (MECHANISMS.md line 64, part 4: one test per inline copy, per spelling, run
    against a stale helper as well as a deleted one): for EACH of the two guards' inline readers,
    with the helper deleted AND with a stale helper that lacks read_regular_file_bytes, a pipe
    link in the \\.\ spelling, a pipe link in the \\?\ spelling, and a \\server\share link each
    give the strict default within the timeout; a regular rules file loads.
  - Do not fix L1 and do not touch the read-only guard's decision code (L1 is accepted in
    Failure Modes). Do not change _shell_write_targets.py or the destructive-detection masking.
  - Plugin version (project CLAUDE.md, Parent Branch Delivery Rule): this sub-task pull request
    goes into feature/file-based-switches and does NOT raise the version. Do not touch
    plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json or
    .claude-plugin/marketplace.json. check_version_bump.py runs in parent mode on this pull
    request and requires the head's version to equal the base's. The landing raises it once.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

---

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md - dispatched by /advance
