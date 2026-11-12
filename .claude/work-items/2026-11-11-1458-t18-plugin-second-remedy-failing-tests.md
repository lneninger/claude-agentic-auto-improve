---
id: 1458
issue_offer: opened
title: Plugin second remedy failing tests
type: IMPROVEMENT
source: github
repo: lneninger/StockToolScalpingMachine
url: https://github.com/lneninger/StockToolScalpingMachine/issues/1458
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-13-database-guard-names-in-rules-file/t18-plugin-second-remedy-failing-tests
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

# Plugin second remedy failing tests

## Problem statement
Sub-task 18 (RED) of the approved contract `2026-10-13-database-guard-names-in-rules-file` in lneninger/StockToolScalpingMachine (parent issue 623, sub-issue 1458). The test review of block 15 and the security re-review of block 15 were both blocked. This pull request adds one failing test per open finding, plus guard rows for the test gaps. The issue and the contract live in that repository, so this pull request references the issue and cannot close it.

## Acceptance criteria
- A failing test for each finding of the two blocked reviews (T1 to T8, T10) and the guard rows for the test review's gaps F2, F3 and F4, each guard row mutation-checked.
- Named edits for F5, F6, F8, F9 and R5-W3-1; existing rows keep passing.
- The plugin version is raised above the plugin's default branch (0.19.1) because the plugin's CI forces a bump for shipped test files.

## Out of scope
Anything the contract's Non-Goals excludes. No production code.
