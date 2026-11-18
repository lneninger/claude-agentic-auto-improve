# Follow-up — The Database override prompt names the target "unresolved" for the common sqlcmd -Q form, and its reason text keeps two label characters

**Parent contract:** `.claude/concepts/2026-11-16-file-based-switches.md`
**Derived from:** the security review of the helper block (`.claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md`, findings W5 and N2) and the first live trial (`.claude/reviews/2026-11-16-file-based-switches/t3-live-prompt-trial-senior-test-engineer.md`, finding W1); decided by the user on 2026-11-18 as a follow-up, not a fix in the fixes block
**Date:** 2026-11-18
**Status:** stub
**Estimated scope:** small
**Issue:** #445

## What was noticed

When the override arm is used, the person is shown a permission prompt that should name what is about to run. For the very common `sqlcmd -Q "<statement>"` form, the guard cannot bind the target database, so the prompt shows the target only as "unresolved". The person then answers a prompt that does not say which database it will touch. The arm is also not tied to any one command, so an agent chooses which blocked command uses it up; a prompt that hides the target makes that choice harder to catch.

A second, smaller issue (N2): the function that cleans the reason text before it is shown keeps the double quote and the semicolon, so in principle text written by an agent could imitate the label structure of the prompt. No command form tried in the review delivered such a target.

## Why it was deferred

Neither finding lets a destructive command run without a prompt. The fixes block (blocks 8 to 10 of the parent contract) is kept to the findings that do, so its re-review can pass. This change reaches into how the guard binds targets for several tools, which has its own design and test rows.

## Way out until this stub is delivered

The residual-risk paragraph of the parent contract and the README text name this limit: the person must read the statement in the prompt itself and not rely on the target label. The prompt still appears for every use of the arm.

## Suggested next step

Run `/design-first` on this stub. Bind the target for `sqlcmd -Q` and the other forms the guard already parses, show "unresolved" only when binding truly fails, and drop the double quote and semicolon in the neutraliser or escape them, with a row for each.

## Pre-derived context

- **Adjacent area:** none (`.claude/area-mapping.json` is empty)
- **Files implicated:**
  - `.claude/hooks/db-destructive-guard.py` (`_bind_targets`, `_neutralise_target`)
  - `.claude/hooks/tests/test_database_override.py`
- **Mechanisms touched:**
  - `Switch file and switch helper` (the Database override arm)
- **Journal entries to re-read when promoting:**
  - `2026-10-05 — neutralise every field echoed from untrusted input`

---

> **Lifecycle:**
> - Created by `data-architect` for a gap noticed outside the parent's scope.
> - Tracked by one GitHub issue per contract, opened by the main session at `/design-first` Step 3.4. A stub whose `Issue:` is still `pending` after approval is a defect.
> - Discovered by `/list-contracts` under the "Stubs / follow-ups" section.
> - Auto-archived by `.claude/scripts/archive_stale_stubs.py` if older than 30 days and never promoted.
> - `concept-gate.py` does NOT treat `Status: stub` as approved.
