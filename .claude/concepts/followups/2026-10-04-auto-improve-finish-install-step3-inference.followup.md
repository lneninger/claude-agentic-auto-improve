# Follow-up — /auto-improve-finish-install proposes the other three per-project files (Quick start step 3)

**Parent contract:** `.claude/concepts/2026-10-04-auto-improve-finish-install-skill.md`
**Derived from:** the parent brief's out-of-scope list
**Date:** 2026-10-04
**Status:** stub
**Issue:** #21
**Estimated scope:** medium

## What was noticed

`/auto-improve-finish-install` fills `project-profile.md` from repository evidence and registers hooks. The other three per-project files from Quick start step 3 are still scaffolded empty by `plugin_doctor.py`: `area-mapping.json`, `work-item-conventions.json` and `.project-tokens.json`. An empty `.project-tokens.json` leaves the outbound sync unguarded. An empty area map makes every contract derive `uncategorized`.

## Why it was deferred

The brief excludes step 3. Inferring a token list or an area map is riskier than inferring source roots, because a wrong token silently weakens the project-name check.

## Suggested next step

Run `/design-first` on this stub. Reuse the parent's slot-proposal shape (a proposal, its evidence, and one confirmation) and the parent's preview-hash apply rule.

## Pre-derived context

- **Adjacent area:** none mapped
- **Files implicated:**
  - `.claude/scripts/auto_improve_finish_install.py` (created by the parent)
  - `.claude/scripts/plugin_doctor.py`
  - `skills/auto-improve-finish-install/SKILL.md`
- **Mechanisms touched:**
  - `Project-name check`
  - `Project profile`
- **Journal entries to re-read when promoting:**
  - none at draft time

---

> **Lifecycle:** see `.claude/templates/followup-stub.md`.
