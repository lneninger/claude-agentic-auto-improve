---
id: 442
issue_offer: opened
title: Security review fixes
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/442
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t8-security-review-fixes
worktree: none
north_stars: inherited from .claude/work-items/2026-11-16-file-based-switches.md
parent_issue: 419
base: feature/file-based-switches
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/446
issue_link: deferred
status: shipped
created: 2026-11-18
---

# Security review fixes

## Problem statement
Sub-task 8 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 8. Security review fixes (`python-ai-developer`)

**Depends on:** 2 — it fixes the findings of block 4, but does not name block 4, because the loop never releases a block whose dependency reads `blocked`.

**Files to touch:**
- `.claude/hooks/db-destructive-guard.py`
- `.claude/hooks/db-research-readonly-guard.py`
- `.claude/hooks/_switches.py`
- `.claude/hooks/tests/test_database_override.py`
- `.claude/hooks/tests/test_switches.py`

**Pre-written TASK block:**
```
TASK: Fix findings B1, W1, W2, W4 and N1 of the security review, each with test rows, and
  nothing else.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (the amended
  No-prompt classes, Arm-write, Fresh-arm and Broken-file rules) and the review at
  .claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md
  (findings, probes O10 to O14, routes R3, R4 and S5).
FILES: as listed. db-research-readonly-guard.py changes only where it carries the same code
  (its inline name test and its own prose masking), so the two guards stay in step.
CONSTRAINTS:
  - Write each new row first and see it fail at the parent tip, then fix.
  - B1: decide the no-prompt class from every matched target (any target classed human-only),
    not from the chosen block reason. When true, do not claim the arm, block, and print the
    human-only instruction. Rows, armed, default mode: human-only plus the EF argument-position
    check (O12), human-only plus a row-deleting statement on a protected database (O13), an EF
    forward update plus the argument-position check (O14). Each expects exit 2, no ask JSON and
    the arm still in place. Keep the human-only-alone row (O11).
  - W1: normalise the edit tools' target path before the last-part name test (slashes folded,
    "." and ".." resolved, trailing dots and spaces dropped from each part), in the helper's name
    test and in each guard's inline copy. Rows: Write to <arm>/. and <arm>/x/.. with forward
    slashes and with backslashes, all refused. Control: a Write to
    <p>/.claude/database-override.once/../notes.md is allowed (its normalised last part is
    notes.md). One fallback row with the helper removed.
  - W2: for the Arm-write rule only, a git segment with a real output redirection to a named
    file (> or >>, with or without a stream number, followed by a path) is not prose. A stream
    duplication such as 2>&1 and a plain pipe do not count. Do not change the masking used for
    destructive-command detection, and do not change _shell_write_targets.py. Rows refused:
    git commit -m "x" > "<arm>", the same after git tag and git notes, and
    git commit -m "x" 2> "<arm>". Controls allowed: git commit -m "<names the arm>" 2>&1 | tail -n 5;
    a commit message, a pull request body and a search pattern that only mention the name.
  - W4: in the switch reader, where os.O_NONBLOCK exists (POSIX), open the file read-only and
    non-blocking, check its kind on the open descriptor (fstat), and close it unread unless it
    is a regular file; anything else is unreadable under the Broken-file rule. On Windows (no
    O_NONBLOCK, no named pipes at a file path), when the switch file is a link, judge the link
    target's drive from the local drive table with no network access first; a network drive or
    a \\server\share target is unreadable and never opened. Rows: (POSIX only, skipped
    elsewhere) a named pipe at switches.local.json gives every default and one report, and the
    hook process finishes within a short timeout, so a regression fails instead of hanging.
    (Windows only, skipped when a link cannot be created) a link at switches.local.json to a
    \\server\share path gives every default and one report, within the same timeout.
  - N1: an arm older than 15 minutes or more than 60 seconds in the future is stale: removed,
    blocked. Rows: an arm dated one day ahead blocks and is removed; an arm 30 seconds ahead
    still asks; a claim dated one day ahead is removed by the sweep.
  - Run the existing guard suites unchanged and record them green: test_db_destructive_guard.py,
    test_db_guard_path_allowlist.py, test_readonly_guard_disposable_exemption.py,
    test_worktree_path_guards.py, test_shell_write_targets.py, test_switch_env_scan.py. If any of
    their rows changes outcome, stop and report an AMENDMENT; do not edit them.
  - Plugin version (project CLAUDE.md, Parent Branch Delivery Rule): this sub-task pull request
    goes into feature/file-based-switches and does NOT raise the version. Do not touch
    plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json or
    .claude-plugin/marketplace.json. check_version_bump.py runs in parent mode on this pull
    request and requires the head's version to equal the base's. The landing raises it once.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md - dispatched by /advance
