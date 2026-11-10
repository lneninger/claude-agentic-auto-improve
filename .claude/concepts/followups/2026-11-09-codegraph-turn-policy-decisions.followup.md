# Follow-up — Decide the CodeGraph gate's policy questions (ideas 2, 3, 4 and the `if` narrowing) on post-cut-over data

**Parent contract:** `.claude/concepts/2026-11-09-codegraph-hooks-cutover.md`
**Derived from:** the parent's Non-Goals (the user's intake answer of 2026-11-09: cut-over only), not an Adjacent Areas row
**Date:** 2026-11-09
**Status:** stub
**Estimated scope:** small
**Issue:** #262

## What was noticed

The cut-over contract enforces the transcript-based turn decision but keeps today's blocking policy. Four decisions that the stub `2026-11-05-codegraph-hooks-cutover.followup.md` owned were deferred by the user at intake because no shadow data existed: idea 2 (gate once per session instead of once per turn), idea 3 (never block a Read of one named source file; parent Q5 set the rule: enforce when more than 50% of Read-of-source blocks are followed by an identical retry in the same turn), idea 4 (allow the first call with a visible hint before blocking), and the `if` narrowing of the guard's `PreToolUse` row. After the cut-over the shadow comparison no longer exists, but the guard keeps writing one Measurement record per guarded call with `outcome: enforced`, and those records carry what each decision needs: blocks per `tool`, blocks followed by an identical retry (`session`, `fp`, `prompt_key`), and `session_seen`.

## Why it was deferred

Each is a change to what the guard blocks, which the user put out of scope of the cut-over until real data exists.

## Suggested next step

After the cut-over has run for at least 7 days in two projects, run `py -3 .claude/scripts/codegraph_shadow_report.py --project <dir>` on each, attach the "enforced" section, then run `/design-first` on this stub.

## Pre-derived context

- **Adjacent area:** none (`.claude/area-mapping.json` has an empty `areas` object)
- **Files implicated:**
  - `.claude/addons/codegraph/hooks/codegraph-first-guard.py`
  - `.claude/addons/codegraph/addon.json` (the `if` narrowing)
  - `.claude/scripts/codegraph_shadow_report.py`
- **Mechanisms touched:**
  - Add-on layout (row `if`)
  - Shadow decision log (now read in enforced mode)
- **Journal entries to re-read when promoting:**
  - 2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures
  - 2026-11-07 — A failed tool call is a different hook event, and a row's `if` matches each sub-command

---

> **Lifecycle:**
> - Created by `data-architect` when a contract defers work.
> - Tracked by issue #262, which stays open for these decisions after the cut-over merges.
> - Discovered by `/list-contracts` under the "Stubs / follow-ups" section.
> - Auto-archived to `<slug>.followup.archived.md` by `.claude/scripts/archive_stale_stubs.py` if older than 30 days and never promoted.
> - Promoted by running `/design-first` against the stub's `## What was noticed` paragraph.
> - `concept-gate.py` does NOT honor `Status: stub` as approved.
