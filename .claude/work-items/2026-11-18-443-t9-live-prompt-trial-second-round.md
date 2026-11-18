---
id: 443
issue_offer: opened
title: Live prompt trial, second round
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/443
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t9-live-prompt-trial-second-round
worktree: none
north_stars: inherited from .claude/work-items/2026-11-16-file-based-switches.md
parent_issue: 419
base: feature/file-based-switches
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/448
issue_link: deferred
status: shipped
created: 2026-11-18
---

# Live prompt trial, second round

## Problem statement
Sub-task 9 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 9. Live prompt trial, second round (`senior-test-engineer`)

**Depends on:** 2

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t9-live-prompt-trial-second-round-senior-test-engineer.md`

**Gate Output, written beside the artefact by the same agent and deliberately not listed above:** `.claude/reviews/2026-11-16-file-based-switches/t9-live-prompt-trial-second-round-senior-test-engineer.gate.json`. It is not declared because the landing's blocked-report check names a task's reports from its declared review files, and a `.gate.json` is never a report, so declaring it would make a blocked record of this block impossible to supersede.

**Pre-written TASK block:**
```
TASK: Write the run sheet for a second person-run trial of the prompt route, covering what the
  first trial and the security review left unproven. Do not run it; a person runs it in a real
  Claude Code session and sets the verdict before this pull request merges.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (Person-present
  rule, Uncertain Assumptions, the Residual risk paragraph); the first run sheet
  t3-live-prompt-trial-senior-test-engineer.md and finding W3 of the t4 security review.
FILES: the run sheet only. It does NOT exist yet; you create it.
CONSTRAINTS:
  - Header line, alone on its line: "**Verdict:** blocked", plus the line "Results pending: a
    person runs the steps below". Merged unchanged, it holds the re-review.
  - Every destructive command in the steps targets a database name that does not exist on the
    local server, so a command the host wrongly allows fails harmlessly. Name destructive
    statements in words, never as literal command text (the guard refuses such files).
  - Steps 6 to 10, numbered after the first trial's five, each with a PowerShell command, an
    Expected line and an Observed line. Before step 6, record the commit the trial runs against
    (git rev-parse HEAD in the parent-branch checkout the session starts from) in the header.
    (6) With every Claude Code session closed, add by hand, in an editor, to
    .claude/settings.local.json an allow rule matching sqlcmd for the shell tool the session
    uses (record the exact rule text). Save it, record the file's save time
    ((Get-Item .claude\settings.local.json).LastWriteTime), then start a NEW session, because
    permission rules may be read only at session start, and record that session's start time.
    The Observed line must show the session started after the save; otherwise the step is void
    and is run again. Arm from the person's own terminal, and in default mode ask Claude to run
    the statement through sqlcmd -Q. Expected: the prompt still appears;
    decline; then remove the rule. If no prompt appears, the person sets the verdict to
    blocked. (7) acceptEdits mode (claude --permission-mode acceptEdits): a prompt; declining
    leaves no arm. (8) plan mode: record whether a prompt appears or the host refuses to run
    the command; either way nothing runs unprompted. (9) dontAsk mode: blocked, arm kept; then
    remove the arm by hand. (10) Record the Claude Code version, and state that a missing
    permission mode cannot be produced from a normal session and rests on the unit rows.
  - The six fixed sections. "## Evidence" holds the person's observations. Write the Gate Output
    t9-live-prompt-trial-second-round-senior-test-engineer.gate.json beside it with
    supersedes [] and checklist []; it supersedes nothing, because the first trial's report
    stays in force.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md - dispatched by /advance
