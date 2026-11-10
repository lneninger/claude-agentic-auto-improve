# Follow-up — Sync tool halts on a pending registry-layout migration

**Parent contract:** `.claude/concepts/2026-11-04-domain-split-registries.md`
**Derived from:** Adjacent Areas (noticed by the architect, not by the scanner), area `sync-tool` (not in `.claude/area-mapping.json`; the map is empty), score `n/a`
**Date:** 2026-11-04
**Status:** stub
**Estimated scope:** medium
**Issue:** #240

## What was noticed

Issue #235 section 4 asks the sync tool (`tools/sync-plugin.ps1`, configured by `.claude/.sync-config.json`) to stop with a pending-migration exit code when a client's registries are still on layout 1, and to sync normally after the migration. Neither file is in this plugin repository (verified 2026-11-04 by the intake brief and again by the parent contract). The parent contract ships the cross-platform Python gate `py -3 .claude/scripts/registry_migrate.py --check --project <root>` (exit 0 current or absent, 6 pending or stale-sync, 2 unknown or could not check; the Registry layout state is printed as JSON on stdout, and `absent` means no root registry file exists at all) and documents the hand-off in `.claude/references/registry-layout.md` § "For the sync tool".

## Why it was deferred

The sync tool lives in another repository, so this contract cannot edit or test it.

## Suggested next step

In the repository that owns `tools/sync-plugin.ps1` (issue #235 §4.2, §4.3, §5 AC 7 and AC 9):

1. **plugin-to-repo gate.** Before the registries tree is compared, run `registry_migrate.py --check --project <consumer>`. On exit 6 (`pending` or `stale-sync`) print the plan and stop that tree with a new sync exit code 6 ("pending registry migration") naming `registry_migrate.py --dry-run`; never auto-apply. On exit 2 stop with exit 4 (bad environment). Do not trust the marker alone: `stale-sync` (marker delivered by an older sync above `## Project:` sections) is pending too.
2. **repo-to-plugin refusal.** Refuse to publish registry files whose layout differs from the plugin's (`--check` not exit 0), with a distinct exit code and a message naming the migration.
3. **Layout configuration and state.** Add `"registry_layout": 2` (the plugin's current layout) to `.claude/.sync-config.json`, and record the consumer's **applied** layout in `.claude/.sync-state/` (absent = 1). Write it only when `--check` reports the state `current` in its JSON output, not on every exit 0, because exit 0 also covers `absent`. The gate compares applied against current.
4. **Tree semantics under layout 2.** The root registry files are whole-file Universal content (marker + Universal tier + generic `## Project tier` pointer); the `MECHANISMS/`, `VOCABULARY/`, `JOURNAL/` folders are project-owned and never synced, per `.claude/references/registry-layout.md` § "For the sync tool".
5. **Docs.** Add the §4.3 client procedure to `tools/SYNC.md` (sync dry-run sees "layout migration pending"; migration dry-run and report; apply; `--check-structure`; regenerate digest; commit; re-run sync; recover or mark orphans), and the new exit codes to its exit-code table.
6. **The plugin-owned token loop (parent contract, round-2 finding P2-W1).** The plugin's own Universal tier names client paths and names, e.g. `MECHANISMS.md:18` "lneninger", `:35` `python/scalping_llm/`, `:36` `python/scalping_strategy_rl/…`. If a client moved such an entry into a domain file, the next plugin-to-repo sync would put it back in the root, giving a duplicate (R2) and a permanent R3 hit. The parent contract breaks the loop on its side: 0001 never moves an entry whose key is in the plugin's Universal tier, and R3 reports such hits as advisory `R3 plugin-owned`. On the sync side: the repo-to-plugin project-name check already refuses new contamination. Clearing the existing plugin-side tokens needs its own contract, because I-7 forbids rewriting those entries in place.
7. **Files arrays.** Add the new generic scripts to the sync config's `files` arrays (issue §4.1): `.claude/scripts/_registry_layout.py`, `_preview_apply.py`, `_plugin_root.py`, `registry_append.py`, `registry_migrate.py`, `registry_migrations/`, plus `.claude/references/registry-layout.md` and `.claude/templates/registries/`. Import chain (parent contract, "Import chain"): `auto_improve_finish_install.py` hard-imports `_preview_apply.py` and `_plugin_root.py`, so a consumer that vendors it without them fails at import; `plugin_doctor.py` and `validate_registries.py --check-structure` import `_registry_layout.py` lazily and report it missing by name. Until this lands, copied-script clients copy the files by hand, as listed in the README change note "Domain-split registries (issue #235)".
8. **Tests.** The sync's own tests: a layout-1 fixture and a stale-sync fixture halt with exit 6; a migrated fixture syncs; repo-to-plugin refuses a layout mismatch.

## Pre-derived context

- **Adjacent area:** `sync-tool` (no entry in `.claude/area-mapping.json`)
- **Files implicated** (in the other repository, unverified here):
  - `tools/sync-plugin.ps1`
  - `.claude/.sync-config.json`
  - `.claude/.sync-state/` (applied registry layout)
  - `tools/SYNC.md`
  - the sync tool's own tests
- **Mechanisms touched** (intersection of parent's `## Reused Mechanisms` and this area's files):
  - `Bidirectional sync with manual conflict resolution`
  - `Section-scoped registry sync`
- **Journal entries to re-read when promoting** (entries with `Apply when:` patterns matching this area):
  - `2026-10-04 — Detect an install mode by what the sync actually delivers`
  - `2026-10-30 — A rule that refuses must give already-delivered work a named way out`

---

> **Lifecycle:**
> - Created by `data-architect` at Step 4.5 when an Adjacent Areas row is decided as `follow-up handle`.
> - Tracked by one GitHub issue per contract, opened by the main session at `/design-first` Step 3.4; the stub is the detail and the issue is what the user sees. A stub whose `Issue:` is still `pending` after approval is a defect.
> - Discovered by `/list-contracts` under the "Stubs / follow-ups" section.
> - Auto-archived to `<slug>.followup.archived.md` by `.claude/scripts/archive_stale_stubs.py` if older than 30 days and never promoted.
> - Promoted by running `/design-first` against the stub's `## What was noticed` paragraph — the resulting full contract should `superseded` this stub (rename the stub to `.followup.superseded.md` and add a `Superseded by:` line at the top).
> - `concept-gate.py` does NOT honor `Status: stub` as approved — you cannot write code authorized only by a stub.
