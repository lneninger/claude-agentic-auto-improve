---
id: none
issue_offer: pending
title: Stop documenting a CodeGraph mark-dirty hook the plugin does not have
type: DOCS
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: docs/codegraph-no-mark-dirty
worktree: .claude/worktrees/20261104-docs-codegraph-no-mark-dirty
north_stars: none
contract: none
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/239
issue_link: none
status: shipped
created: 2026-11-04
---

# Stop documenting a CodeGraph mark-dirty hook the plugin does not have

## Problem statement
The request was: "conduct a full analyze and change the plugin to avoid the mark-dirty use from
codegraph use". The analysis found that the plugin never runs `codegraph mark-dirty`. No hook file,
no hook registry row and no add-on manifest calls it. The only mentions are two documentation
lines that claim lifecycle hooks (`sync-if-dirty` on session start and stop, `mark-dirty` after
edits) which nothing implements. This was checked on `origin/master` at version 0.15.0.

## Acceptance criteria
- [x] No file the plugin ships mentions `codegraph mark-dirty` or `codegraph sync-if-dirty` as something the plugin runs.
- [x] The two passages now say the plugin registers no index-refresh hook, that the CodeGraph MCP server's file watcher keeps the index fresh, and that a stale index is fixed with `codegraph sync` or `codegraph init -i`.
- [x] The plugin version is raised in all five places, so an installed copy receives the fix.
- [x] The manifest test suite passes.

## Out of scope
- The user's private global `CLAUDE.md` (outside this repository) also says a hook runs `codegraph mark-dirty` after edits. The plugin cannot change that file. The user should delete that line there.
- Any hook change. There was no hook to remove.

## Known context
- Affected files: `.claude/references/codegraph-decision-table.md`, `.claude/registries/MECHANISMS.md`, and the five version declarations.

## North-star alignment
- none — the register holds no active thought for this item.

## Size
XS — documentation wording and a version bump, no new data shape.

## Routing
trivial → direct edit (Markdown files are on the concept gate's trivial list).
