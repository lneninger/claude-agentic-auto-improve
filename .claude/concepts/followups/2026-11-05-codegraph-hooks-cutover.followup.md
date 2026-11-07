# Follow-up — Cut the codegraph add-on over to the one-hook design and retire the tracker and reset hooks

**Parent contract:** `.claude/concepts/2026-11-05-codegraph-hooks-redesign.md`
**Derived from:** Non-Goals of the parent (the cut-over is deliberately a later step, acceptance criterion 2 of issue #261), not an Adjacent Areas row
**Date:** 2026-11-05
**Status:** stub
**Estimated scope:** medium
**Issue:** #262

## What was noticed

The parent contract ships the transcript-derived turn decision (issue idea 1) only in shadow mode: the old hooks still decide, and the guard writes a Shadow record per call to `<CLAUDE_PROJECT_DIR>/.claude/logs/codegraph-shadow.jsonl`. The brief requires that the old hooks are removed only after that log shows the two designs agree across real sessions. That removal is this follow-up: the guard decides from the Transcript turn state, `codegraph-turn-tracker.py` and `codegraph-turn-reset.py` move to the `disabled` list of `addon.json` with their released hashes (Disabled add-on hook mechanism), the reset hook's once-per-session pruning moves into the guard, and the three existing test files change to match.

## Why it was deferred

It may start only when `codegraph_shadow_report.py` meets the parent's Q2 criterion (answered 2026-11-05: at least 20 real main sessions over at least 7 days in at least 2 projects, zero unexplained `shadow-more-closed` outcomes, transcript-path p95 within the old per-turn cost; the report's counts are lower bounds), and it necessarily changes the three test files the parent must leave unchanged.

## Suggested next step

Run `codegraph_shadow_report.py` on the projects that ran the shadow, attach its output, then run `/design-first` on this stub.

## Pre-derived context

- **Adjacent area:** none (`.claude/area-mapping.json` has an empty `areas` object)
- **Files implicated:**
  - `.claude/addons/codegraph/addon.json`
  - `.claude/addons/codegraph/hooks/codegraph-first-guard.py`
  - `.claude/addons/codegraph/hooks/codegraph-turn-tracker.py`
  - `.claude/addons/codegraph/hooks/codegraph-turn-reset.py`
  - `.claude/hooks/tests/test_codegraph_first_guard.py`, `test_worktree_path_guards.py`, `test_addons.py`
- **Mechanisms touched:**
  - Disabled add-on hook
  - Add-on layout
  - Preview-hash apply
- **Decisions this follow-up owns, on the shadow data** (parent's Alternatives, issue numbering):
  - Idea 2 (once-per-session gate): owner of the decision; evidence is the report's `session_seen` count.
  - Idea 3 (never block a Read of one named file): enforce (parent's Q5, answered yes on 2026-11-05) only if, over the Q2 sample, more than 50% of Read-of-source blocks are followed by an identical retry within the same turn (same `session`, `fp` and `prompt_key`); evidence is blocks and retries per `tool`.
  - Idea 4 (nudge before blocking): owner of the decision; evidence is blocks followed by a retry.
  - Hot-path order for the transcript check (transcript before or after classification): set by the parent's block 3 bench.
  - The `if` narrowing of the guard's registration row (an "other option" in the parent).
- **Journal entries to re-read when promoting:**
  - 2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures
  - 2026-10-22 — Describe a broken install by the rows each install age really has
  - 2026-11-02 — Name the tests a fix may change by the state they guard, after reading them
