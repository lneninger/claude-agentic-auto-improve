---
id: 71
issue_offer: pending
title: Scan every hook's user-facing text for machine-specific text, and make the Stop member-missing notice accurate
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/71
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/71-hook-text-genericity-and-notice
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261111-infra-71-hook-text-genericity-and-notice
north_stars: none
contract: none
pr: none
issue_link: unknown
status: verifying
created: 2026-11-11
---

# Scan every hook's user-facing text for machine-specific text, and make the Stop member-missing notice accurate

(Issue title: "[CHORE] Follow-ups from Remove the plain-language guard hook (2026-10-18-remove-plain-language-hook)". Raw argument: https://github.com/lneninger/claude-agentic-auto-improve/issues/71)

## Problem statement
Issue 71 has two follow-ups left open (the first was delivered by pull request 151).
The genericity test in `test_working_agreements.py` scans only the shipped agreement files, so a hook that prints a person, project or machine path into every consuming project is not caught. Separately, `stop-dispatcher.py` prints "Files a shell command wrote were not checked against a contract" whenever any member is missing, although that is only true when the changed-file check itself is the missing member.

## Acceptance criteria
- [ ] A test scans the user-facing string text of every hook source in `.claude/hooks/*.py` with the existing structural patterns and the plugin manifest's author and owner names, and fails when a hit appears; each leg has a made-up positive control.
- [ ] The real hook sources pass that scan on master (any genuine hit found is fixed in the hook text, not exempted).
- [ ] The missing-member notice names only what was not checked: the shell-write sentence appears only when the changed-file check is missing, and a missing names warning gets its own accurate sentence.
- [ ] A test pins both notice variants, and the once-per-session marker and exit-code behaviour of `stop-dispatcher.py` are unchanged.
- [ ] The existing suites for those files still pass.

## Out of scope
- Editing any consuming project's old vendored `stop-dispatcher.py` (cannot be reached from here).
- The 19 failing tests in `test_auto_improve_finish_install.py` (separate item named in the issue comment).
- The first follow-up (dangling hook rows), already delivered.

## Known context
- Parent / epic: contract `.claude/concepts/2026-10-18-remove-plain-language-hook.md`
- Related items: pull request 151; followup `.claude/concepts/followups/2026-10-18-warn-on-rows-naming-unshipped-hooks.followup.md`
- Affected areas: `.claude/hooks/stop-dispatcher.py`, `.claude/hooks/tests/test_stop_dispatcher.py`, `.claude/hooks/tests/test_working_agreements.py` (or a new hook-text test file)

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- "Decide whether to reword" is a decision, not a criterion → **Answer (assumed, user prefers assumptions):** yes, reword; the current shipped dispatcher has the same defect, so fixing it there is the only reachable remedy.
- What counts as "user-facing text"? → **Answer (assumed):** string constants in the hook sources that are not docstrings or comments, extracted with `ast`.

## Size
S — one test addition and one small text change in one hook, no new data shape.

## Routing
trivial → no contract; run `/tdd-first` directly (status of the item: task of a chore, not a bug, so no `/debug`).
