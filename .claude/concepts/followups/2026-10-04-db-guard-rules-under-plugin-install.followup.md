# Follow-up — The database guard cannot be configured under a plugin install

**Parent contract:** `.claude/concepts/2026-10-04-auto-improve-finish-install-skill.md`
**Derived from:** design investigation for the parent (not a scanner result; the cross-area scan could not be run, see the parent's Adjacent Areas)
**Date:** 2026-10-04
**Status:** stub
**Issue:** #21
**Estimated scope:** medium

## What was noticed

`db-destructive-guard.py` reads its rules from `db-destructive-guard.rules.json` beside itself (`_RULES_PATH = Path(__file__).resolve().parent / ...`, around line 312). Under a plugin install that file is the plugin's own template in the provider cache, and it names two fictional databases (`AcmeApp`, `AcmeApp_Testing`). Because that list is non-empty, `RULES_LOADED` is true, so the guard is **not** in its fail-closed "every database is protected" mode. Its per-name write layer protects only the two fictional names. The generic destructive-command bank still blocks drops and truncates of any non-disposable name. A plugin-installed project has no supported place to put its own rules file: an edit inside the cache is lost at the next update. The README's "the database guards fail closed" line is true only when the rules file is absent or empty.

## Why it was deferred

The parent's brief rules out "any change to what an individual hook does". The parent only reports this state truthfully. It does not change it.

## Suggested next step

Run `/design-first` on this stub. The likely shape is to read the rules file from the project's `.claude/hooks/` first and fall back to the file beside the hook, with a fail-closed test that has the project file renamed away. Correct the README sentence in the same change.

## Pre-derived context

- **Adjacent area:** none mapped (the plugin's `.claude/area-mapping.json` has an empty `areas` set)
- **Files implicated:**
  - `.claude/hooks/db-destructive-guard.py`
  - `.claude/hooks/db-destructive-guard.rules.json`
  - `.claude/hooks/db-research-readonly-guard.py` (check whether it has the same shape)
  - `README.md` ("Installing the hooks turns on enforcement")
- **Mechanisms touched:**
  - `Guard rules file`
  - `Two-layer Claude path resolution`
- **Journal entries to re-read when promoting:**
  - none at draft time (the Universal journal is empty)

---

> **Lifecycle:** see `.claude/templates/followup-stub.md`.
