# Follow-up — Point the angular-tailwind advisor's layout nudge at the new design skills

**Parent contract:** `.claude/concepts/2026-10-22-webdesign-plugin-skills.md`
**Derived from:** Adjacent Areas row noticed by the architect (not in the area map; the scan had no areas to score), area `angular-tailwind add-on`, score `n/a`
**Date:** 2026-10-22
**Status:** stub
**Estimated scope:** small
**Issue:** pending

## What was noticed

The opt-in angular-tailwind add-on's advisor hook (`.claude/addons/angular-tailwind/hooks/angular-tailwind-advisor.py`, lines 136-157) still nudges layout requests toward `~/.claude/references/ui-ux-pro-max/product-patterns.md` and `ux-guidelines.md`. The `ui-ux-designer` agent records that this directory never existed (agent lines 79-83, confirmed 2026-08-18 and 2026-08-25), and the parent contract moves that note into the website-design foundation. After the parent lands, the nudge's natural target is the `agentic-auto-improve:application-design` skill, not a phantom catalogue.

## Why it was deferred

The parent contract moves knowledge between markdown assets only; changing a hook's printed text is Python, needs its own test, and touches an opt-in add-on with its own install path.

## Suggested next step

Run `/design-first` on this stub: replace the phantom-path nudge with a pointer to the two design skills, and add a test row proving the nudge never names a path that does not exist.

## Pre-derived context

- **Adjacent area:** `angular-tailwind add-on` (not declared in `.claude/area-mapping.json`, whose `areas` object is empty in this repository)
- **Files implicated:**
  - `.claude/addons/angular-tailwind/hooks/angular-tailwind-advisor.py`
  - `.claude/addons/angular-tailwind/addon.json`
- **Mechanisms touched:**
  - `Project profile` (the nudge should cite `review.documents`, as the skills do)
- **Journal entries to re-read when promoting:**
  - `2026-10-04 — Check a documented guard behaviour against the guard's code`

---

> **Lifecycle:**
> - Created by `data-architect` at Step 4.5 when an Adjacent Areas row is decided as `follow-up handle`.
> - Tracked by one GitHub issue per contract, opened by the main session at `/design-first` Step 3.4; the stub is the detail and the issue is what the user sees. A stub whose `Issue:` is still `pending` after approval is a defect.
> - Discovered by `/list-contracts` under the "Stubs / follow-ups" section.
> - Auto-archived to `<slug>.followup.archived.md` by `.claude/scripts/archive_stale_stubs.py` if older than 30 days and never promoted.
> - Promoted by running `/design-first` against the stub's `## What was noticed` paragraph — the resulting full contract should `superseded` this stub (rename the stub to `.followup.superseded.md` and add a `Superseded by:` line at the top).
> - `concept-gate.py` does NOT honor `Status: stub` as approved — you cannot write code authorized only by a stub.
