---
id: 71
issue_offer: pending
title: Warn about project hook rows that name a hook file the plugin no longer ships
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/71
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/71-warn-on-unshipped-hook-rows
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261031-infra-71-warn-on-unshipped-hook-rows
north_stars: none
contract: .claude/concepts/2026-10-31-warn-on-unshipped-hook-rows.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/151
partial: true
issue_link: unresolved
status: verifying
created: 2026-10-31
---

# Warn about project hook rows that name a hook file the plugin no longer ships

(Issue title: "[CHORE] Follow-ups from Remove the plain-language guard hook (2026-10-18-remove-plain-language-hook)".)

## Problem statement
The plain-language guard hook was removed from the plugin. A vendored install keeps its own rows in `.claude/settings.json` that launch `.claude/hooks/plain-language-guard.py`. If the operator deletes that file and forgets the rows, the launcher exits with code 2. On prompt submit that blocks every prompt. Nothing detects this state today. The finish-install script only adds rows and never removes them.

## Acceptance criteria
- [ ] The finish-install readiness report or `plugin_doctor.py` lists every project-layer hook row whose launched file does not exist.
- [ ] Each finding names the event and the row.
- [ ] The check reports a finding only and never edits `settings.json`.
- [ ] A project whose rows all launch existing files reports no such finding.
- [ ] Tests cover both the finding and the clean case, in the existing test suites for both scripts.

## Out of scope
- Issue #71 follow-up 2: extending the genericity scan to the user-facing text of every hook. Vague as written; stays open on the issue.
- Issue #71 follow-up 3: the misleading "Files a shell command wrote were not checked" notice from an old vendored `stop-dispatcher.py`. It is a decision ("decide whether to reword"), not work. Stays open on the issue.
- Any automatic removal of rows.

## Known context
- Parent / epic: contract `.claude/concepts/2026-10-18-remove-plain-language-hook.md`
- Detail file: `.claude/concepts/followups/2026-10-18-warn-on-rows-naming-unshipped-hooks.followup.md`
- Affected areas: `.claude/scripts/auto_improve_finish_install.py`, `.claude/scripts/plugin_doctor.py`, their tests
- Mechanism touched: Preview-hash apply

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- Issue #71 bundles three follow-ups; which does this run cover? → **Answer (assumption, not user-confirmed):** follow-up 1 only. It is the only concrete one with a detail file. The other two stay open. `partial: true` makes `/ship` use `Refs #71`, not a closing keyword.

## Size
M — new check in install tooling with its own tests, touching two scripts.

## Routing
non-trivial → /design-first

## Run log
- 2026-11-01 /flow halted at Step 4 (review): retry budget spent. Three review passes each found a real false-positive defect in `dangling_hook_rows`. The finding's remedy says "remove the row", so a false positive could invite removing a WORKING hook.
  - Pass 1 fixed: a quoted variable joined to a path (`"$CLAUDE_PROJECT_DIR"/x.py`), the variable-name boundary, and `OSError` escaping before `run_drift`'s try block.
  - Pass 2 fixed: an apostrophe inside a quoted path, a backslash-escaped space, a Git Bash `/c/...` path, and an unused `shlex` import.
  - Pass 3 OPEN (critical): a shell-form row that changes folder before launching (`cd X && python g.py`, `cd .claude/hooks; python g.py`, `pushd ...`) is reported as dangling.
  - Pass 3 OPEN (warn): nested-shell rows such as `bash -c '...'` and `cmd /c "..."`.
  - Reviewer's suggested fix, not applied: in `dangling_hook_rows` only, treat a shell-form row as unresolvable when a separator (`&&`, `||`, `;`, `|`, `&`) precedes the launched word, when the first word is `cd`, `pushd` or `Set-Location`, or when the word before the launched word is `-c`, `/c`, `/k` or `-Command`. Do not change `_launched_raw_tokens`. Tests: the four working rows give no finding, and `cd ... && python missing.py` is skipped too (accepted cost).
  - Tests: 518 pass (exit 0), including the new ones. The open defect has no failing test yet.
  - Intake assumption still stands: this run covers issue #71 follow-up 1 only (`partial: true`).
- 2026-11-01 /flow resumed after "Continue". The open defect was closed by switching to a whitelist for both row forms (reviews 4 to 6; review 6 was clean). Master moved to 0.12.3 (Project hook launcher rows, pull request #150), so the branch merged master and is now 0.12.4. Launcher rows are skipped by the check. The read-back tests were rewritten for that.
- 2026-11-01 /ship: draft pull request #151 opened. `verify_issue_link.py` returned `unexpected-closing-ref` (halt): GitHub reports a closing link to #71 although the body says `Refs #71` and the brief says `partial: true`. Cause: the branch was cut with `gh issue develop` at intake, so GitHub treats it as linked to the issue. A merge would close #71 while follow-ups 2 and 3 are still open. No repair was attempted. `issue_link: unresolved`. Needs a human: unlink the branch from the issue (issue #71 sidebar, Development section), or reopen #71 after the merge.
- 19 failures in `test_auto_improve_finish_install.py` are master's own (identical on a clean `origin/master` checkout) and are not part of this work.
