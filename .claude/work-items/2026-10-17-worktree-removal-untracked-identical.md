---
id: none
issue_offer: pending
title: Delivery cleanup leaves a worktree behind over an untracked file that master already holds, and the concept gate blocks a script written outside any project
type: BUG
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: fix/worktree-removal-untracked-identical
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261017-bug-worktree-removal-blocked-untracked
north_stars: none
parent_issue: none
base: master
contract: .claude/concepts/2026-10-17-worktree-removal-untracked-identical.md
pr: UNKNOWN
issue_link: unknown
status: designing
created: 2026-10-17
---

# Delivery cleanup leaves a worktree behind over an untracked file that master already holds, and the concept gate blocks a script written outside any project

## Problem statement
Seen while removing the worktree of the "providers database migration" item (issue 394, pull request 449). Delivery cleanup (`cleanup_delivered.py`) would not remove its worktree, because that tree held one untracked file. The file was byte for byte the same as the version already on master from pull request 449, so removing the tree loses nothing. The agent therefore decided to hand the user a Windows script (`C:\Users\lneni\remove-394-worktree.cmd`) to run after the session ended. Writing that script was blocked by the concept gate (`concept-gate.py`, the hook that demands an approved design contract before a file is written). The gate reported `Project: <unknown project>`: the target sat in the user's home folder, outside every project. Two separate defects are therefore in play: cleanup treats a harmless untracked file as unsaved work, and the gate applies the design-contract rule to a file that belongs to no project.

Assumption: the worktree in the report was an ordinary delivered worktree whose only blocker was that one untracked file. The cleanup code path (`_status_files` then the `uncommitted-changes` outcome) matches the symptom exactly, but the original tree is not available to reproduce against.

## Acceptance criteria
- [ ] A delivered worktree whose only untracked files are byte-identical to the same paths in the landing reference (`origin/master`) is removed by delivery cleanup, and its branch is cleaned as for any clean tree. A test with a real git repository shows the tree and folder gone.
- [ ] A worktree with an untracked file that is NOT identical to the landing reference (different content, or a path master does not have) is still left in place, reported as `uncommitted-changes` with that file listed. A test proves it.
- [ ] A worktree with a modified tracked file, or a staged change, is still left in place exactly as today.
- [ ] The identical files are deleted only after every other check has passed, and removal still never uses `git worktree remove --force` (the existing no-force rule keeps its test).
- [ ] The cleanup report names the identical files it removed, so the run explains why the tree had been blocked.
- [ ] Failure path: if the landing reference cannot be read or a file cannot be compared, the tree is left in place with an `unverifiable` outcome. It is never treated as identical by default.
- [ ] The concept gate allows a Write or Edit whose target lies outside every project, meaning `detect_project_name` finds no marker (`.git`, `CLAUDE.md`, `package.json`, `pyproject.toml`, a solution file) on the path. Code inside a project is still gated exactly as before. A test covers both sides.
- [ ] The plugin version is bumped and the change reaches the plugin copy the way earlier fixes did (CONTRIBUTING rules for a plugin change).

## Out of scope
- Removing a worktree that holds the current session's own folder (the existing standing-tree deferral stays as it is).
- Treating a differing untracked file as safe, or ever forcing removal.
- Changing which files the gate trusts inside a project, or the contract format.
- The main-checkout guard, which has its own rules for the shared checkout.

## Known context
- Parent / epic: none
- Related items: pull request 449 and issue 394 (the providers database migration item, in another repository); reference journal `.claude/agent-memory/agentic-auto-improve-test-strategy-critic/concept-gate-blocks-scratch-harness.md`
- Affected areas (best guess, to be confirmed by the contract): `.claude/scripts/cleanup_delivered.py` and its tests `.claude/scripts/tests/test_cleanup_delivered.py`; `.claude/hooks/concept-gate.py` and its tests; `plugin.json`, `.claude-plugin/plugin.json` and `.cursor-plugin/plugin.json` for the version.

## North-star alignment
- none: the register holds no active thought

## Open questions from intake
- Should the fix delete identical untracked files itself, or only stop calling them changes? → **Answer (assumed):** it must delete them, because plain `git worktree remove` without force also refuses a tree that holds untracked files. Deletion happens last and only for files proven identical.
- Should the concept-gate change cover the whole "no project" case, or only the user's home folder? → **Answer (assumed):** the whole case, defined by "no project marker on the path", because the gate exists to protect project code and has nothing to protect outside one.
- Open an issue for this? → **Answer:** not asked. `issue_offer` stays `pending`, so `/ship` makes the offer later instead of this unattended run guessing.

## Size
M — changes a destructive deletion path and a safety hook, with new behaviour and tests in two areas.

## Routing
non-trivial → /design-first
