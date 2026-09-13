# Follow-up — <one-line title>

**Parent contract:** `.claude/concepts/<parent-slug>.md`
**Derived from:** Adjacent Areas scan, area `<area-slug>`, score `<N>`
**Date:** YYYY-MM-DD
**Status:** stub
**Estimated scope:** trivial | small | medium | large

## What was noticed

<One paragraph — describe the cross-area signal that triggered this stub. Cite the parent contract's section that referenced the related work (e.g., "Parent's `## Integration Surfaces` row for `ProviderCallLogged` event implies a frontend consumer that the parent declared out-of-scope.").>

## Why it was deferred

<One sentence — why this is NOT in the parent contract's scope. Common reasons: scope cap, requires its own data design, owner of the area is on a separate roadmap, blocked by unresolved Open Question elsewhere.>

## Suggested next step

<One sentence — concrete action that would close this stub. Examples:
- "Run `/design-first` on this stub to produce a full draft contract."
- "Append to `.claude/registries/MECHANISMS.md` under <project>."
- "Audit the existing area for drift against the new shape introduced in the parent."
- "Open a backlog ticket and re-evaluate after phase X ships.">

## Pre-derived context

- **Adjacent area:** `<area-slug>` (from `.claude/area-mapping.json`)
- **Files implicated** (from `cross_area_scan.py` output for the parent):
  - `path/to/file1`
  - `path/to/file2`
- **Mechanisms touched** (intersection of parent's `## Reused Mechanisms` and this area's files):
  - `<mechanism-name>`
- **Journal entries to re-read when promoting** (entries with `Apply when:` patterns matching this area):
  - `<YYYY-MM-DD — entry title>` (if any)

---

> **Lifecycle:**
> - Created by `data-architect` at Step 4.5 when an Adjacent Areas row is decided as `follow-up handle`.
> - Discovered by `/list-contracts` under the "Stubs / follow-ups" section.
> - Auto-archived to `<slug>.followup.archived.md` by `.claude/scripts/archive_stale_stubs.py` if older than 30 days and never promoted.
> - Promoted by running `/design-first` against the stub's `## What was noticed` paragraph — the resulting full contract should `superseded` this stub (rename the stub to `.followup.superseded.md` and add a `Superseded by:` line at the top).
> - `concept-gate.py` does NOT honor `Status: stub` as approved — you cannot write code authorized only by a stub.
