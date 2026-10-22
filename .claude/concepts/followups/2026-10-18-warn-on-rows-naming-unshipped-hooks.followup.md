# Follow-up — Warn about project hook rows that name a hook file the plugin no longer ships

**Parent contract:** `.claude/concepts/2026-10-18-remove-plain-language-hook.md`
**Derived from:** design investigation for the parent (not a scanner result; the cross-area scan was not run, see the parent's Adjacent Areas)
**Date:** 2026-10-18
**Status:** stub
**Estimated scope:** small
**Issue:** #71

## What was noticed

The parent removes the plain-language guard from the plugin. A vendored install that the finish-install script set up from version 0.9.8 on has ONE row of its own in `.claude/settings.json` that launches `${CLAUDE_PROJECT_DIR}/.claude/hooks/plain-language-guard.py`, on prompt submit. At Stop the guard ran only through the project's own `stop-dispatcher.py`. An install registered before 0.9.8 also has a direct Stop row. The finish-install script only ever adds rows, so it never takes these away. While the project keeps its copy of the file, nothing breaks. If the operator deletes the file and forgets the rows, the Python launcher fails to open the script and exits with code 2 (checked by a real call). On prompt submit, code 2 blocks every prompt. A direct Stop row, where it exists, holds the end of every turn. The dispatcher's missing-member path exits 0 instead, but an old vendored dispatcher then prints a misleading notice ("Files a shell command wrote were not checked") although the Changed-file check did run. The parent only documents the safe order (rows first, then the file). Nothing detects the bad state.

Also carried here from the superseded 2026-10-05 follow-up: extend the genericity scan so it covers the user-facing text of every hook, not only the guard's stop message.

## Why it was deferred

The parent is a removal with a fixed scope. Adding a new check to the install tooling is a feature with its own tests, and it would apply to every hook the plugin removes, not only this one.

## Suggested next step

Run `/design-first` on this stub: extend the finish-install readiness report or `plugin_doctor.py` to list every project-layer hook row whose launched file does not exist, naming the event and the row, as a finding and never an automatic edit.

## Pre-derived context

- **Adjacent area:** none mapped (the plugin's `.claude/area-mapping.json` has an empty `areas` set)
- **Files implicated:**
  - `.claude/scripts/auto_improve_finish_install.py` (readiness report already lists `unresolved-commands`, but only for the plugin's own `hooks.json`)
  - `.claude/scripts/plugin_doctor.py`
  - their test suites
- **Mechanisms touched:**
  - `Preview-hash apply`
- **Journal entries to re-read when promoting:**
  - `2026-10-04 — Check a documented guard behaviour against the guard's code`

---

> **Lifecycle:** see `.claude/templates/followup-stub.md`.
