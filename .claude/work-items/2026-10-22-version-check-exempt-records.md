---
id: none
issue_offer: declined
title: Exempt record and review folders from the version-bump check
type: BUG
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: fix/version-check-exempt-records
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261022-bug-version-check-exempt-records
north_stars: none
contract: none
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/75
issue_link: none
status: shipped
created: 2026-10-22
---

# Exempt record and review folders from the version-bump check

Raw invocation: `Fix the version-bump check so records-only pull requests pass. .claude/scripts/check_version_bump.py keeps EXEMPT_PREFIXES ... lacks .claude/orchestrator/results/ and .claude/reviews/ ... Pull request 73 fails CI "version-bump" ... Add both prefixes to the exempt list and add test rows ... The plugin version must be raised by one patch because the check script itself is a shipped file (read master's version first). Do not change anything else.`

## Problem statement
The version-bump check decides which changed files are "shipped plugin files" that need a version raise. Its exempt list names folders that never ship (work items, concepts, registries, tests). It does not name `.claude/orchestrator/results/` (completion records written after a merge) or `.claude/reviews/` (review reports and their gate files). A records-only pull request therefore fails the check and demands a version raise for a change with no plugin code. Pull request 73 (records for the web-design skills contract) fails CI for exactly this reason.

## Acceptance criteria
- [ ] `EXEMPT_PREFIXES` in `.claude/scripts/check_version_bump.py` contains `.claude/orchestrator/results/` and `.claude/reviews/`; nothing else in that file changes.
- [ ] A test proves a diff touching only a file under `.claude/orchestrator/results/` needs no bump (exit 0).
- [ ] A test proves a diff touching only a file under `.claude/reviews/` needs no bump (exit 0).
- [ ] A test proves a diff touching a shipped file (for example `skills/x/SKILL.md`) still fails without a bump, even when it also touches the two exempt folders.
- [ ] `py -3 .claude/scripts/tests/test_check_version_bump.py` ends OK, exit 0.
- [ ] The plugin version is raised by one patch above master's (master reads 0.9.16, so 0.9.17) in all five manifest entries, and `check_version_bump.py --base origin/master` passes after the commit.
- [ ] Failure path: an unreadable version still exits 2 (existing test stays green).

## Out of scope
- The README hooks count drift.
- Any other exempt-list change.
- Opening any GitHub issue.

## Known context
- Parent / epic: none
- Related items: pull request 73 (the failing records pull request), pull request 74 (also raises the version to 0.9.17)
- Version collision: pull request 74 already sets 0.9.17. Whichever of the two merges second must be moved to 0.9.18 before it merges; say so in this pull request's notes.
- Affected areas (best guess): `.claude/scripts/check_version_bump.py`, `.claude/scripts/tests/test_check_version_bump.py`, the four manifests

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- Separate pull request from the web-design work? → **Answer:** yes, the user said "yes, do the separate small fix".
- Contract needed? → **Answer (assumption):** no. It is a two-entry data change in an existing list with test rows and no new data shape or mechanism. If the contract gate blocks the edit, the run escalates to /design-first.

## Size
S — one list gets two entries, plus test rows; no new data shape.

## Routing
S → /tdd-first (no contract unless the gate demands one)
