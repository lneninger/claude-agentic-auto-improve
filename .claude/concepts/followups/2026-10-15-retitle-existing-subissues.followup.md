# Follow-up — Retitle the sub-issues that already exist without a parent reference

**Parent contract:** `.claude/concepts/2026-10-15-subissue-title-parent-ref.md`
**Derived from:** Adjacent Areas, noticed by the architect (no area map is populated; the scanner has no area to surface)
**Date:** 2026-10-15
**Status:** stub
**Estimated scope:** small
**Issue:** #51

## What was noticed

The parent contract changes how new sub-issue titles are built (`[TYPE] #<parent> - <bare title>`), read from the Sub-issue title format in `.claude/work-item-conventions.json`. The 37 open sub-issues of #638 in lneninger/StockToolScalpingMachine keep their old titles, so the flat issue list stays mixed until they are retitled.

## Why it was deferred

The Work Item Brief puts it out of scope: it edits shared issues in another repository, which is a separate operator decision to make after the parent ships.

## Suggested next step

After the parent ships, list the parent's children with the conventions file's `parentLink.parentListCommand`, preview each new title with `compose_subissue_title.py`, show the operator the full before/after list, and run `gh issue edit <n> --title` only on approval.

## Pre-derived context

- **Adjacent area:** `uncategorized` (from `.claude/area-mapping.json`, which declares no areas)
- **Files implicated:**
  - none in this repository; the edits are tracker mutations in another repository
- **Mechanisms touched:**
  - Sub-issue title format (introduced by the parent contract)
- **Journal entries to re-read when promoting:**
  - none
