---
id: none
issue_offer: pending
title: Declare each agent's CodeGraph tools with one server wildcard instead of repeating the tool names
type: REFACTOR
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/mcp-server-wildcard-tools
worktree: .claude/worktrees/20261022-improvement-mcp-server-wildcard-tools
north_stars: none
contract: none
pr: none
status: implementing
created: 2026-10-22
---

# Declare each agent's CodeGraph tools with one server wildcard instead of repeating the tool names

## Problem statement
All 14 agents repeat the same seven CodeGraph tool names in their `tools:` line. The user asked whether the
references can be centralized per Model Context Protocol server. The documentation has no central file for this,
but a `tools:` entry accepts a whole-server wildcard.

## Acceptance criteria
- [x] Every agent's `tools:` line carries `mcp__codegraph__*` in place of the individual CodeGraph names.
- [x] No other tool in any `tools:` line changes.
- [ ] Plugin version raised in all five places; the version check passes.

## Out of scope
- A central allowlist file (the documentation has none).
- CodeGraph mentions in prose.

## Open questions from intake
- The wildcard also grants `codegraph_explore` and `codegraph_context` to every agent, which the global rule reserves for the Explore subagent. → **Answer:** accepted as a trade-off, flagged in the pull request. Not launch-tested: the edited agents load only after the plugin is reinstalled.

## Size
S — one-line frontmatter edit per agent, no data shape.

## Routing
trivial → direct edit (markdown only)
