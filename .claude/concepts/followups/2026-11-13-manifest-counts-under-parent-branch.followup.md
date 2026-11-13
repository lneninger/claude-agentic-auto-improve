# Follow-up — A multi-sub-task contract that adds a skill, agent or hook cannot keep the manifest counts true

**Parent contract:** `.claude/concepts/2026-11-13-audit-followups-165-chores.md`
**Derived from:** noticed by the data-architect while designing the manifest drift test; not an Adjacent Areas scan (`.claude/area-mapping.json` holds no areas)
**Date:** 2026-11-13
**Status:** stub
**Estimated scope:** small
**Issue:** #405

## What was noticed

The parent contract pins the skill and agent counts in the four manifest descriptions against the tree, the same way `HookCountTests` already pins the hook count (`test_repo_consistency.py:392-404`). CI runs that suite on every pull request (`.github/workflows/version-bump.yml`, `tests` job), including a sub-task pull request into a parent branch. A sub-task may not list a manifest (`sub-task-raises-version`, `pr_merged.py:1632-1638`), and the landing's `check_version_bump.py --raise` writes only the version fields. So a multi-sub-task contract that adds a skill, an agent or a hook turns the `tests` job red on the sub-task that adds it, and no reviewed route can correct the description: not a sub-task, and not the landing. The hook half of this gap already existed before the parent contract.

## Why it was deferred

It changes the landing (or the counting rule), which is delivery machinery with its own design; the parent contract is a small chore that only corrects today's text.

## Way out until this stub is delivered

A parent branch already in flight whose merged sub-tasks add or remove a skill or agent turns red on this pin from the sub-task that takes the default branch in (journal 2026-11-07) onward. The parent contract finds such a branch with a Run-first check that diffs each `origin` branch against `origin/master` for added or deleted `skills/*/SKILL.md` and `agents/*.md`. It names two owner-only exits (journal 2026-10-30), and the pin's failure message repeats them:

- **(i) Recommended:** hold the parent contract's pull request until that branch lands, then recount. No route turns red.
- **(ii) Otherwise, one exit per route:**
  - the sync sub-task, each later sub-task and the landing pull request merge with the `tests` job red on this pin alone, and each records a finding in its review artefact that cites this stub;
  - `master` after the landing is red until a single-block recount pull request merges. That pull request may list the manifests (a single block is not judged by the layout rule, `pr_merged.py:1585-1587`) and raises the version one patch step. It is the next pull request merged into `master`.

This stub's design must make both exits unnecessary, and say how a branch still in flight on the day it ships is handled.

## Suggested next step

Run `/design-first` on this stub. The owner chose real counts on 2026-11-13 (parent Q1, answer (a)), so the design is (a): the landing rewrites the description counts from `count_oracles` in the same commit as the version raise, with a `--exact`-style check. Number-free descriptions (b) were declined.

## Pre-derived context

- **Adjacent area:** none (`.claude/area-mapping.json` is empty)
- **Files implicated:**
  - `.claude/scripts/check_version_bump.py` (`--raise`)
  - `.claude/scripts/land_contract.py` (P7b)
  - `.claude/scripts/tests/test_repo_consistency.py`
  - `plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`
- **Mechanisms touched:**
  - `Plugin version check modes`
- **Journal entries to re-read when promoting:**
  - `2026-10-30 — A delivery rule must name every route into delivery, not only the one the author had in mind`
  - `2026-11-02 — A "fails the build" claim must name the workflow that runs the check`
  - `2026-10-30 — A rule that refuses must give already-delivered work a named way out`
  - `2026-11-07 — A parent branch that shares files with a moving default branch must take the default branch in through a sub-task before its landing`

---

> **Lifecycle:**
> - Created by `data-architect` for a gap noticed outside the parent's scope.
> - Tracked by one GitHub issue per contract, opened by the main session at `/design-first` Step 3.4. A stub whose `Issue:` is still `pending` after approval is a defect.
> - Discovered by `/list-contracts` under the "Stubs / follow-ups" section.
> - Auto-archived by `.claude/scripts/archive_stale_stubs.py` if older than 30 days and never promoted.
> - `concept-gate.py` does NOT treat `Status: stub` as approved.
