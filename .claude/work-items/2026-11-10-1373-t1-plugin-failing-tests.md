---
id: 1373
issue_offer: opened
title: Plugin failing tests
type: IMPROVEMENT
source: github
repo: lneninger/StockToolScalpingMachine
url: https://github.com/lneninger/StockToolScalpingMachine/issues/1373
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-13-database-guard-names-in-rules-file/t1-plugin-failing-tests
worktree: none
north_stars: inherited from the parent work item in lneninger/StockToolScalpingMachine
parent_issue: 623
base: master
contract: none (the contract lives in lneninger/StockToolScalpingMachine at .claude/concepts/2026-10-13-database-guard-names-in-rules-file.md)
pr: none
issue_link: none
status: implementing
created: 2026-11-10
---

# Plugin failing tests

## Problem statement
Sub-task 1 (RED) of the approved contract `2026-10-13-database-guard-names-in-rules-file` in lneninger/StockToolScalpingMachine (parent issue 623, sub-issue 1373). The plugin half of the tests only. The issue and the contract live in that repository, so this pull request references the issue and cannot close it.

## Acceptance criteria
- Failing tests for the Protected-name check, its plugin run points, the Folder-name match, the guard error path and the protect-databases subcommand.
- No production code and no version bump.

## Out of scope
Anything the contract's Non-Goals excludes.
