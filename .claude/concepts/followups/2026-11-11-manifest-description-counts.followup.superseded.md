# Follow-up — Manifest descriptions state the real skill and agent counts, pinned by a drift test

**Parent contract:** `.claude/concepts/2026-11-11-audit-followups-165.md`
**Derived from:** the parent's Q6 answer (2026-11-11) and its critic BLOCKER; not an Adjacent Areas scan (`.claude/area-mapping.json` holds no areas)
**Date:** 2026-11-11
**Status:** superseded
**Superseded by:** `.claude/concepts/2026-11-13-audit-followups-165-chores.md` (issue #354)
**Estimated scope:** small
**Issue:** #354

## What was noticed

The brief for issue 165 asks for manifest descriptions with the real counts, and for a test in `test_repo_consistency.py` that fails when they drift. All four manifests still say "28 skills" (and 14 agents or subagents), while the tree has 34 skills, 15 agents and 14 hooks. The files are `plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` and `.cursor-plugin/plugin.json`. They are in `check_version_bump.MANIFESTS`, and `contractLanding.versionRaise` is `true`, so no sub-task of the parent contract may list them: that is the Layout defect `sub-task-raises-version`. The parent's block 9 ships the count helper (with a manifest-shaped control) and the README pins only.

## Why it was deferred

The owner chose on 2026-11-11 to make it its own tracked work item after the parent lands, so that it gets its own design, review and version raise instead of an unreviewed second route into the default branch.

## Suggested next step

After the parent lands, run `/task` on this stub. That gives one work item with one single-block contract, which corrects the four descriptions and applies the parent's count helper to the real manifests, then is delivered and version-raised through that item's own flow.

## Pre-derived context

- **Adjacent area:** none (`.claude/area-mapping.json` is empty)
- **Files implicated:**
  - `plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json` (description strings only)
  - `.claude/scripts/tests/test_repo_consistency.py`
- **Mechanisms touched:**
  - `Plugin version check modes`
- **Journal entries to re-read when promoting:**
  - `2026-10-30 — A delivery rule must name every route into delivery, not only the one the author had in mind`

---

> **Lifecycle:**
> - Created by `data-architect` for an item the owner moved out of the parent contract.
> - Tracked by one GitHub issue per contract, opened by the main session at `/design-first` Step 3.4. A stub whose `Issue:` is still `pending` after approval is a defect.
> - Discovered by `/list-contracts` under the "Stubs / follow-ups" section.
> - Auto-archived by `.claude/scripts/archive_stale_stubs.py` if older than 30 days and never promoted.
> - `concept-gate.py` does NOT treat `Status: stub` as approved.
