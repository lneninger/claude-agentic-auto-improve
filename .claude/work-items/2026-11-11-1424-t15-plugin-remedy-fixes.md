---
id: 1424
issue_offer: opened
title: Plugin remedy fixes
type: IMPROVEMENT
source: github
repo: lneninger/StockToolScalpingMachine
url: https://github.com/lneninger/StockToolScalpingMachine/issues/1424
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-13-database-guard-names-in-rules-file/t15-plugin-remedy-fixes
worktree: none
north_stars: inherited from the parent work item in lneninger/StockToolScalpingMachine
parent_issue: 623
base: master
contract: none (the contract lives in lneninger/StockToolScalpingMachine at .claude/concepts/2026-10-13-database-guard-names-in-rules-file.md)
pr: none
issue_link: none
status: implementing
created: 2026-11-11
---

# Plugin remedy fixes

## Problem statement
Sub-task 15 (GREEN) of the approved contract `2026-10-13-database-guard-names-in-rules-file` in lneninger/StockToolScalpingMachine (parent issue 623, sub-issue 1424). It fixes the three landing-gate bypasses found by the blocked security review of block 2, and makes the failing tests of sub-task 14 (plugin pull request 349) pass. The issue and the contract live in that repository, so this pull request references the issue and cannot close it.

## Acceptance criteria
- The planted-helper takeover, the git replace and environment override bypass, and the case-variant rules file bypass are fixed, with the names and shapes pinned in the contract's Revision 5.
- Step 5.7 resolves the project from the tree being verified.
- Every row of sub-task 14 passes; existing rows keep passing.
- The plugin version is raised above the plugin's default branch (0.18.7) because the plugin's CI forces a bump for shipped files.

## Out of scope
Anything the contract's Non-Goals excludes. The repository-only reclaim guard hunks are a declared difference and are not ported.
