# Follow-up — The merge-base version row (INV-O1) fails every parent-branch sub-task

**Parent contract:** `.claude/concepts/2026-11-04-domain-split-registries.md`
**Derived from:** Amendment 6 critique (WARN 2), noticed by the critic, not by the scanner; area `version-rule` (not in `.claude/area-mapping.json`; the map is empty), score `n/a`
**Date:** 2026-11-07
**Status:** stub
**Estimated scope:** small
**Issue:** #240 (added as a checklist item to the contract's existing follow-up issue)

## What was noticed

The default branch's `test_plugin_manifests.py` holds the INV-O1 row (`:1331-1389`). It prints "the version obeys the merge-base rule: tree differs from the merge base (<version>), so all five declarations exceed it". The row requires any tree that differs from its merge base with `origin/master` to carry a higher version in all five declarations. The project's Parent Branch Delivery Rule (project `CLAUDE.md`, and `check_version_bump.py` parent mode at `:133-182`) requires a `task/<slug>/<id>` head into a parent branch to keep the version, because the landing raises it once. A parent-branch sub-task that changes anything therefore fails INV-O1 by construction. This is true for every future parent-branch contract in this repository, not only for sub-tasks 12 to 14 of the parent contract. The parent contract records only its own case, as an owner-accepted exception (Amendment 6 record, item 3).

Evidence: on sub-task 12's head (`task/2026-11-04-domain-split-registries/t12-merge-the-default-branch-into-the-parent-branch`, after the merge of `origin/master` `28f0b18`, version 0.16.3), `test_plugin_manifests.py` printed 191 passes and 1 failure, and the failure was this row. No configured gate runs the suite. `/verify-before-done` classifies `.claude/` and `.md` changes as docs-only (`skills/verify-before-done/SKILL.md:26`). The landing's verification steps (`.claude/work-item-conventions.json` `contractLanding.verification.steps`, about lines 88-124) are `version-bump`, `test_pr_merged.py`, `test_check_hook_registrations.py` and the `.claude/hooks/tests` folder, and none of them is `test_plugin_manifests.py`. So the row is red, and nothing reads it. After a landing merges the parent into the default branch, the merge base is the head itself and the row passes trivially, so it never proves the landing's raise either.

## Why it was deferred

Changing the version rule's test is outside the parent contract's scope (domain-split registries), and the owner accepted the one red row for that contract only (2026-11-07).

## Suggested next step

Run `/design-first` on this stub and choose one option. Recommendation: (a).

- **(a) Make the row parent-aware (recommended).** When `HEAD`'s branch, or the `GITHUB_HEAD_REF` the CI passes, matches `task/<slug>/<id>`, apply the parent-mode rule `check_version_bump.py` already implements: the version equals the base's version, or the version at the merge base with the default branch. Reuse `check_version_bump.py`'s parent-mode function rather than a second copy of the rule (one shared reader). If the branch cannot be read, the row still FAILS and names the cause, as today; it never skips.
- **(b) Exempt `task/` heads.** Smaller, but the row then checks nothing on a parent-branch sub-task, and a skipped check looks exactly like a passed one (the row's own comment at `:1334-1335`).
- **(c) Drop the row.** `check_version_bump.py` and the `version-bump` CI check already enforce the rule on every pull request. This loses the local test-suite signal on the default branch.

Whichever is chosen, add one fixture row for a `task/` head whose version equals its base's version, and one for a default-branch head that changes files but keeps the version, which must still fail.

## Pre-derived context

- **Adjacent area:** `version-rule` (no entry in `.claude/area-mapping.json`)
- **Files implicated:**
  - `.claude/scripts/tests/test_plugin_manifests.py` (INV-O1, `:1331-1397`)
  - `.claude/scripts/check_version_bump.py` (parent mode, `:133-182`)
  - `.claude/work-item-conventions.json` (`contractLanding.verification.steps`, if the suite should become a landing step)
- **Mechanisms touched:**
  - the Parent Branch Delivery Rule (project `CLAUDE.md`)
- **Journal entries to re-read when promoting:**
  - `2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have`
  - `2026-11-06 — A sub-task that flips the state an earlier sub-task's test pins must re-run that suite`

---

> **Lifecycle:**
> - Created by `data-architect` at Step 4.5 when an Adjacent Areas row is decided as `follow-up handle`.
> - Tracked by one GitHub issue per contract, opened by the main session at `/design-first` Step 3.4; the stub is the detail and the issue is what the user sees. A stub whose `Issue:` is still `pending` after approval is a defect.
> - Discovered by `/list-contracts` under the "Stubs / follow-ups" section.
> - Auto-archived to `<slug>.followup.archived.md` by `.claude/scripts/archive_stale_stubs.py` if older than 30 days and never promoted.
> - Promoted by running `/design-first` against the stub's `## What was noticed` paragraph — the resulting full contract should `superseded` this stub (rename the stub to `.followup.superseded.md` and add a `Superseded by:` line at the top).
> - `concept-gate.py` does NOT honor `Status: stub` as approved — you cannot write code authorized only by a stub.
