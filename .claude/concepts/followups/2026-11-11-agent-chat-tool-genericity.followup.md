# Follow-up — Consuming-project chat-tool text in two shipped agents

**Parent contract:** `.claude/concepts/2026-11-11-audit-followups-165.md`
**Derived from:** noticed by the data-architect while verifying the template's "Chat Tool Impact" defect; not an Adjacent Areas scan (`.claude/area-mapping.json` holds no areas)
**Date:** 2026-11-11
**Status:** stub
**Estimated scope:** small
**Issue:** #354

## What was noticed

The parent contract's block 3 makes the template's "Chat Tool Impact" section generic. Two shipped agents carry the same consuming-project text. `agents/contract-critic.md` checklist item 7 cites a consuming project's contract (`2026-04-21-strategy-learner-phase-a2-...`) as its precedent. `agents/fullstack-code-reviewer.md` lines 170-178 name `ChatToolDefinitions.cs`, `SystemPromptBuilder.cs`, `python/training-data/synthetic/` and the `llm-training-engineer` agent, which this plugin does not ship. Critic item 7 also depends on the template's heading and its three sanctioned answers, which block 3 keeps on purpose.

## Why it was deferred

The brief puts files that the three issue-165 stubs do not name out of scope.

## Suggested next step

Run `/design-first` on this stub. Make both agent passages cite the project-profile slots and `.claude/hooks/sentinel-paths.json` instead of literal file names, and extend block 3's template pin to the two agent files.

## Pre-derived context

- **Adjacent area:** none (`.claude/area-mapping.json` is empty)
- **Files implicated:**
  - `agents/contract-critic.md`
  - `agents/fullstack-code-reviewer.md`
- **Mechanisms touched:**
  - `Project profile`
- **Journal entries to re-read when promoting:**
  - `2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control`

---

> **Lifecycle:**
> - Created by `data-architect` for a defect noticed outside the parent's scope.
> - Tracked by one GitHub issue per contract, opened by the main session at `/design-first` Step 3.4. A stub whose `Issue:` is still `pending` after approval is a defect.
> - Discovered by `/list-contracts` under the "Stubs / follow-ups" section.
> - Auto-archived by `.claude/scripts/archive_stale_stubs.py` if older than 30 days and never promoted.
> - `concept-gate.py` does NOT treat `Status: stub` as approved.
