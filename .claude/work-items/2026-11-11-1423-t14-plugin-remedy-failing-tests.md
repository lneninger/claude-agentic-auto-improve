---
id: 1423
issue_offer: opened
title: Plugin remedy failing tests
type: IMPROVEMENT
source: github
repo: lneninger/StockToolScalpingMachine
url: https://github.com/lneninger/StockToolScalpingMachine/issues/1423
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-13-database-guard-names-in-rules-file/t14-plugin-remedy-failing-tests
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

# Plugin remedy failing tests

## Problem statement
Sub-task 14 (RED) of the approved contract `2026-10-13-database-guard-names-in-rules-file` in lneninger/StockToolScalpingMachine (parent issue 623, sub-issue 1423). The security review of block 2 (verdict blocked) found three ways to get a protected database name past the landing gate. This pull request adds one failing test per probe. The issue and the contract live in that repository, so this pull request references the issue and cannot close it.

## Acceptance criteria
- A failing test for each probe of the blocked review and each new row of Revision 5.
- Existing rows keep passing, except where a named edit moves a recorder off the trace variable that remedy invariant C2 removes.
- The plugin version is raised to 0.18.5 because the plugin's CI forces a bump for shipped test files.

## Out of scope
Anything the contract's Non-Goals excludes. No production code.
