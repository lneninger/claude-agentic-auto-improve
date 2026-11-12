---
id: 1459
issue_offer: opened
title: Plugin second remedy fixes
type: IMPROVEMENT
source: github
repo: lneninger/StockToolScalpingMachine
url: https://github.com/lneninger/StockToolScalpingMachine/issues/1459
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-13-database-guard-names-in-rules-file/t19-plugin-second-remedy-fixes
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

# Plugin second remedy fixes

## Problem statement
Sub-task 19 (GREEN) of the approved contract `2026-10-13-database-guard-names-in-rules-file` in lneninger/StockToolScalpingMachine (parent issue 623, sub-issue 1459). It fixes the findings of the two blocked reviews of the first remedy (block 15) and makes the failing tests of sub-task 18 (plugin pull request 384) pass. The issue and the contract live in that repository, so this pull request references the issue and cannot close it.

## Acceptance criteria
- Every finding pinned by block 18's rows is fixed with the names and shapes in the contract's Revisions 5 and 6.
- Every row of sub-task 18 passes; existing rows keep passing.
- The plugin version is raised above the plugin's default branch because the plugin's CI forces a bump for shipped files.

## Out of scope
Anything the contract's Non-Goals excludes. The repository-only reclaim guard hunks are a declared difference and are not ported.
