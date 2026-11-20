---
id: 462
issue_offer: opened
title: Security review fixes, round three
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/462
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t13-security-review-fixes-round-three
worktree: none
north_stars: inherited from .claude/work-items/2026-11-16-file-based-switches.md
parent_issue: 419
base: feature/file-based-switches
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/464
issue_link: deferred
status: shipped
created: 2026-11-20
---

# Security review fixes, round three

## Problem statement
Sub-task 13 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 13. Security review fixes, round three (`python-ai-developer`)

**Depends on:** 11 — it fixes the findings of the third security review (block 12), but does not name block 12, because the loop never releases a block whose dependency reads `blocked` (the same convention as blocks 8 and 11, which name neither 4 nor 10).

**Files to touch:**
- `.claude/hooks/db-destructive-guard.py`
- `.claude/hooks/db-research-readonly-guard.py`
- `.claude/hooks/tests/test_database_override.py`
- `.claude/hooks/tests/test_db_destructive_guard.py`

`db-research-readonly-guard.py` is listed for I2 only (user answer 2026-11-20: I2 extended to both guards): its `_audit` appends to `<project>/.claude/logs/db-research.log` with a plain open on its block path, the same class as the destructive guard's `db-guard.log`. Its decision code is not changed (L1 accepted; it has no human-only class). Its I2 rows go in `test_database_override.py`, which already runs both guards as separate processes and holds block 11's pipe-link rows for both; `test_readonly_guard_disposable_exemption.py` runs unchanged. `_switches.py` is not listed: the Audit-log rule needs no helper entry point, and the classifier lives in the destructive guard. `test_db_destructive_guard.py` is listed only so a row that pins one of t12's B1, P1 or P2 shapes as allowed can be retired by name (see the constraints); no other change to it is allowed.

**What the rows prove, plainly.** As in block 11, the destructive guard is the deciding guard for B1, P1 and P2, and only its rows expect a block. This contract does not claim that the read-only guard blocks any of these shapes. Per t12, armed: on N2a and K1 to K6 (K1 to K3 apply because P2 is in this block) it asks and claims the arm (L1, accepted), and whether the host then shows a prompt rests on the ASSUMED "a block beats an ask"; on N1b and N1a it allows and keeps the arm. For I2 both guards have rows, because each writes its own audit log.

**Pre-written TASK block:**
```
TASK: Fix findings B1, P1 (round three), P2 and I2 (I2 in both database guards) of the third
  security review, each with test rows, and nothing else.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (the No-prompt
  classes rule's readings and command-start words, the Audit-log rule, Failure Modes, the
  amendment 3 Open Questions, answered 2026-11-20); the review
  .claude/reviews/2026-11-16-file-based-switches/t12-security-re-review-round-three-security-auditor.md
  (findings B1, P1, P2, I2; the Evidence table "B1 and P1 shapes not covered by block 11";
  the Disposition). Read it in full. Its row ids, clause order, script paths, quotes and escape
  characters are exact; its destructive statements are named in words by the report's own
  rule, so rebuild each one from those words by string joining, as the existing rows do. Name
  clash: t12's findings P1 and P2 are not t4's shared-claim probes P1 to P9, and t12's findings
  N5 and N6 are not its probe shapes N5 and N6; use the t12 row ids for rows.
FILES: as listed.
CONSTRAINTS:
  - RED before GREEN, in this one block (the block 8 and block 11 convention): commit the new
    rows first, run them at the parent tip, and list in the pull request body each new row with
    its outcome at the tip and at your head. Every row copied from t12 (the "Copied rows" lists
    below) and every hang row MUST fail (or time out) at the tip. A copied row that passes at
    the tip has been mistranscribed (a lost backslash or backtick, the script first, a bare
    script name with no folder): fix it until it fails at the tip; never relabel it a control.
    The only rows allowed to pass at the tip are the ones this TASK names as controls. The fix
    commit comes after.
  - B1 and P1: fix the classifier only (_starts_a_command, _in_command_position and only what
    _human_only_script_hits needs from them). Implement all four readings of the No-prompt
    classes rule and class the script as invoked when ANY of them says so: (1) the readings in
    force at the tip; (2) a bash reading: a backslash escapes the next character outside quotes
    and inside double quotes, nothing is escaped inside single quotes, $'...' takes backslash
    escapes, and a backtick outside single quotes opens a command segment (substitution), as
    $( does; (3) a PowerShell reading: a backtick escapes the next character inside and outside
    double quotes and never opens a segment, "" and '' are doubled quotes, a backslash is a
    plain character; (4) a quote-blind reading: strip the folder-prefix token and an optional
    quote before it; invoked when the nearest preceding non-space character is ; & | ( { or a
    newline (never a backtick). The backtick rule lives in the bash reading only, so it cannot
    conflict with the PowerShell reading: each reading is computed on its own and the results
    are joined by "any". All four readings are part of the Data Shapes rule; none is optional.
    Every shape the tip classes as invoked stays invoked. Do not change the human_only flag in
    _decide, the prose masker or _shell_write_targets.py.
  - Script spelling: tools/db-protection/update-dev-database.cmd (forward slashes) in bash rows,
    tools\db-protection\update-dev-database.cmd in PowerShell rows, exactly as t12 writes each
    row. A row that exists in one shell only is written once, in that shell.
  - Copied rows, the destructive guard alone, each row in its own fresh temporary project with
    its own arm (never both guards on one arm):
      armed, default mode, expect exit 2, no ask JSON, the arm still in place, the human-only
      instruction in the block text: N1a, N1b, N2a, K4, K5, K6.
      no arm, expect exit 2 (blocked, not allowed): N1, N1c, N15, N5, N6 (PowerShell) and N2,
      N2b, N3, N4 (bash).
  - P2 (user answer 2026-11-20: included): implement the command-start words of the No-prompt
    classes rule. A word that itself starts a command segment and is then, do, else, elif, !,
    time, env, nohup, exec, command, builtin, nice, timeout, xargs or sudo passes the start on
    to the next word, after skipping NAME=value assignments and that word's options. An option
    is a word starting with -; an option that takes a value also skips the next word: nice -n;
    sudo -u, -g, -h, -p, -C, -D, -r, -t, -U; env -u, -C; timeout -s, -k; xargs -I, -n, -P, -L,
    -d, -a, -E, -s; exec -a; time has no valued option. After its options, timeout also skips
    its duration. A leading NAME=value is skipped the same way. Exception: command -v and
    command -V (a lookup, not a run) keep the next word a mention. Copied rows: no arm, expect
    exit 2: N7 to N13; armed, as above: K1, K2, K3. Constructed rows, no arm, expect exit 2,
    one per remaining word (else, elif, exec, command, builtin, nice, timeout, xargs, sudo, a
    leading NAME=value) and one per valued option: nice -n 10 <script>, sudo -u root <script>,
    env -u NAME <script>, timeout -s KILL 5 <script>. A constructed row that already blocks at
    the tip is named a control. Controls that must stay allowed: command -v <script> and
    command -V <script> (named mentions, not false blocks); the same words as plain arguments
    (echo then <script>, grep -n time <script>); a script name after one of them inside a
    commit message.
  - I2 (user answer 2026-11-20: included, in BOTH database guards): implement the Audit-log
    rule in each guard's _audit (db-destructive-guard.py, db-guard.log; db-research-readonly-
    guard.py, db-research.log). Every step of the path is checked, not only the append:
      (a) the folders: walk from the folder that holds .claude (the project, or the home
          folder on the guard's no-project fallback) to the log folder (.claude, then
          .claude/logs) with lstat, never following links; each part must be a real folder,
          not a link or, on Windows, any reparse point (junction included); a missing part is
          created with a single-level mkdir and checked with lstat again; mkdir(parents=True)
          and exists() are not used;
      (b) the log: lstat it; missing goes to (d); a link, reparse point or anything but a
          regular file skips the record;
      (c) rotation: only when (b) found a regular file over the size limit; lstat the rotated
          name (.1): when it exists it must be a regular file, otherwise the record is skipped
          and nothing is renamed or removed; then remove it and rename the log; no stat() or
          exists() that follows a link;
      (d) the open: os.open with O_WRONLY | O_APPEND | O_CREAT, plus O_BINARY, O_NONBLOCK and
          O_NOFOLLOW where they exist; os.fstat the descriptor and require S_ISREG before any
          byte is written;
    on any failure close the descriptor unwritten, skip the record, write one line to standard
    error, and write no other file. The decision is never changed. Rows, per guard, the guard
    run as a separate process under a short timeout, each finishing within it with its normal
    decision (the destructive guard blocks a removal of a non-disposable database; the
    read-only guard, with no arm, blocks a write on a protected database, its block path), the record
    skipped and the link target untouched: (Windows only, skipped with the stated reason
    "symbolic link creation not permitted on this host" when os.symlink raises a privilege
    error) a link at the log to a listening named pipe that accepts and never reads, in the
    \\.\ and the \\?\ spelling; a link at the log to a \\server\share path; a directory link
    at .claude/logs into the pipe namespace; a directory link at .claude/logs to a
    \\server\share path; a
    directory link at .claude/logs to another local folder (nothing is written there);
    rotation on a linked log (a link at the log to a regular file larger than the size limit,
    made sparse: the target is neither renamed nor removed); rotation with a link at the .1
    name (its target is not removed). (POSIX only, skipped elsewhere) a named pipe at the log,
    the same. Controls, per guard: a regular log is appended as before; a missing log and a
    missing logs folder are created; a regular log over the limit rotates as before.
  - Controls that must stay green, unchanged: MENTION_ROWS and LAUNCHER_ROWS in
    test_database_override.py, every block 11 row, and O11, O12, O13b, O14. If any of them, or
    any row of the existing suites below other than a named P1/P2-pinning row, changes outcome,
    stop and report an AMENDMENT. Do not drop or weaken a reading to make a row pass.
  - Existing guard suites unchanged and green: test_switches.py, test_db_destructive_guard.py,
    test_db_guard_path_allowlist.py, test_readonly_guard_disposable_exemption.py,
    test_worktree_path_guards.py, test_shell_write_targets.py, test_switch_env_scan.py, and the
    db-protection fixture suite. If a row there expects ALLOW for one of t12's B1, P1 or P2
    shapes (a human-only script invoked after a misread quote, a keyword or prefix command, or a
    backtick), it pins the defect: retire it by name in test_db_destructive_guard.py, replace it
    with the blocking row, and name both in the pull request body. Any other row that changes
    outcome: stop and report an AMENDMENT; do not edit it.
  - Do not fix L1, N6 or the other hooks' plain opens. In the read-only guard change _audit
    only; do not touch its decision code.
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
