---
id: 178
issue_offer: pending
title: /pr-merged leaves completion-record copies untracked in the starting tree
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/178
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/178-records-leftover-cleanup
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261102-infra-178-records-leftover-cleanup
north_stars: none
contract: .claude/concepts/2026-11-02-pr-merged-records-leftover-cleanup.md
pr: UNKNOWN
issue_link: unknown
status: designing
created: 2026-11-02
---

# /pr-merged leaves completion-record copies untracked in the starting tree

## Problem statement
After `/pr-merged` records a finished sub-task, the completion record file stays behind as an
untracked file in the working copy the command ran from (the starting tree). The same file has
already reached `master` through the records pull request, so the leftover is clutter. It grows by
one file per merged sub-task and nothing removes it. A later merge of `master` into the starting
tree can be blocked, because git refuses to overwrite an untracked file of the same name. Every
session also starts with a dirty tree, which breaks the rule that no task file is left uncommitted.
The script's `next_command` does not know a records push is pending, so it points at `/clear` then
`/advance` while a record is still untracked.

## Acceptance criteria
- [ ] After a normal `/pr-merged` run that pushes the records branch, `git status --short` in the starting tree shows no untracked file under the records results folder.
- [ ] A starting-tree record that differs from the pushed one is not deleted. The report names it and says why.
- [ ] If the records push fails or is declined, no starting-tree file is deleted.
- [ ] When records are pending, the `next_command` printed by `pr_merged.py` starts with the records step. When none are pending, it is unchanged.
- [ ] `/advance` runs the records step before dispatching, and does not dispatch on top of pending records.
- [ ] `/advance` and `/pr-merged` end with a tree-clean line per tree touched.
- [ ] A test covers each case: identical copy removed, differing copy kept, failed push keeps files, records pending changes `next_command`, nothing pending leaves it unchanged (`.claude/scripts/tests/test_pr_merged.py`).
- [ ] A test proves a re-run of `/pr-merged` for an already recorded sub-task does not duplicate or delete a record.
- [ ] The skill text in `skills/pr-merged/SKILL.md` (Step 3), `skills/pr-merged/references/contract-completion.md` (Step 9) and `skills/advance/SKILL.md` matches the new behaviour, and the vendored copies in consuming projects are told to sync.

## Out of scope
- Moving records to the parent branch or changing where the landing script reads records from.
- Changing how a sub-task is mapped to its pull request.
- Merging records pull requests. That stays with the person.

## Known context
- Parent / epic: none
- Related items: pull request 1054 (consuming project), journal entry of 2026-08-29 (stale-base reason for cutting the records branch fresh from `master`)
- Affected areas (best guess, to be confirmed by the contract): `.claude/scripts/pr_merged.py`, `.claude/scripts/tests/test_pr_merged.py`, `skills/pr-merged/SKILL.md`, `skills/pr-merged/references/contract-completion.md`, `skills/advance/SKILL.md`, release notes and a plugin version bump
- Implementer notes from the issue: compare by blob hash after normalising line endings (Windows `autocrlf`); delete only in the starting tree; the pending check must read git facts, not session memory.

## North-star alignment
- none — the register holds no active thought (`.claude/north-stars/` does not exist)

## Open questions from intake
- The issue's proposed fix point 4 asks the maintainer whether every records push should skip its confirmation, like the existing completion hand-off push. → **Answer:** carried to the `/design-first` gate as an Open Question with a recommendation (adopt it: documentation-only files, fixed branch, no force push, merging stays with the person). Not decided at intake.

## Size
M — changes a script, its tests and three skill documents, and needs a release bump.

## Routing
non-trivial → /design-first
