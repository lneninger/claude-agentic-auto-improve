# Follow-up — The doctor's conventions scaffold has no parentLink block

**Parent contract:** `.claude/concepts/2026-10-15-subissue-title-parent-ref.md`
**Derived from:** Adjacent Areas, noticed by the architect (no area map is populated; the scanner has no area to surface)
**Date:** 2026-10-15
**Status:** stub
**Estimated scope:** trivial
**Issue:** #51

## What was noticed

`.claude/scripts/plugin_doctor.py` scaffolds `.claude/work-item-conventions.json` for a new project (the `SCAFFOLDS` dictionary). That scaffold carries `issueTitle`, `prTitle` and `issueLink`, but no `issueLink.parentLink` block. `verify_parent_link.py` returns `unverifiable` with cause `conventions-missing` when that block is absent, so a project set up by the doctor cannot complete Parent-aware mode's link check. The parent contract adds only its own `issueTitle.subIssue` block to the scaffold.

## Why it was deferred

It is a defect that existed before this work, in a block the parent contract does not own. Fixing it here would widen the parent beyond its acceptance criteria.

## Suggested next step

Add the `parentLink` block, copied from the plugin's conventions template, to the doctor's scaffold, and add a doctor test that the scaffold holds every block a shipped script reads.

## Pre-derived context

- **Adjacent area:** `uncategorized` (from `.claude/area-mapping.json`, which declares no areas)
- **Files implicated:**
  - `.claude/scripts/plugin_doctor.py`
  - `.claude/scripts/tests/test_plugin_doctor.py`
- **Mechanisms touched:**
  - Plugin registry ownership model (the conventions file is project-authored and scaffolded once)
- **Journal entries to re-read when promoting:**
  - `2026-10-04 — Detect an install mode by what the sync actually delivers`

## Added after the implementation review (2026-10-16)

The same scaffold ships `issueTitle.effortTypes` as an empty list. The new sub-issue title helper checks the effort tag against that list, so a project built by the doctor refuses every sub-issue title as `pattern-mismatch` until the nine effort tags are filled in. Fix it together with the missing `parentLink` block: seed the scaffold with the nine tags from `.claude/work-item-conventions.json`, and add a test that runs the helper against the scaffold's own output.
