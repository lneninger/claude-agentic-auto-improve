# Follow-up — Token efficiency and stale references found by the memory and cloud audit

**Superseded by:** `.claude/concepts/2026-11-11-audit-followups-165.md`
**Parent contract:** `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`
**Derived from:** the parent contract's Appendix A (audit) and Appendix B (token efficiency). This stub did not come from an Adjacent Areas scan; the area map holds no areas.
**Date:** 2026-11-01
**Status:** stub
**Estimated scope:** medium
**Issue:** #165

## What was noticed

The read-only audit found defects that cost tokens or correctness but have nothing to do with memory or cloud work. The parent contract keeps them out because the brief rules out unrelated refactoring:

- `skills/task/SKILL.md` holds "Step 1.5: Enter a worktree" twice, word for word (lines 104-118 and 120-134).
- Its Step 5c (lines 446-521) still describes a worktree recipe that, by its own words, "is not run for a fresh item".
- `skills/flow/SKILL.md` Step 2.7 (lines 114-334, about 220 lines) loads on every `/flow` run, including single-block contracts. It could move to `references/` under the existing "read this file only when the case applies" rule that `/task` and `/pr-merged` already use.
- The concept-contract template carries a "Chat Tool Impact" section that names one consuming project's files and history (`ChatToolDefinitions.cs`, `SystemPromptBuilder.cs`, "Phase A2 Strategy Learner"). That is a genericity defect in a shipped file.
- `skills/debug/SKILL.md` lines 198-201 route work to agents this plugin does not ship (`docker-master-goat`, `llm-training-engineer`, `ingestion-data-architect`).
- The manifest descriptions and the README say "28 skills". `skills/` holds 32. A prior review (`t9-review-fullstack-code-reviewer.md`, finding F2) already reported this.
- `memory-pager.py` runs at every Stop, but the plugin ships no `memory-blocks.json`. A project without that file gets one `config-load-failed` log line per turn.
- The data-architect is told to read `.claude/.scout-cache/registry-digest.md`, `.claude/registries/INTEGRATION.md` and per-domain registry files. None of them exists in this repository, and nothing generates the digest automatically.

## Why it was deferred

The brief puts unrelated refactoring of existing skills, agents and hooks out of scope.

## Suggested next step

Run `/design-first` on this stub. Group the items into one contract with one block per skill file, so each block can be reviewed on its own.

## Pre-derived context

- **Adjacent area:** none. `.claude/area-mapping.json` holds no areas.
- **Files implicated:**
  - `skills/task/SKILL.md`
  - `skills/flow/SKILL.md`
  - `skills/debug/SKILL.md`
  - `.claude/templates/concept-contract.md`
  - `.claude/hooks/memory-pager.py`
  - `agents/data-architect.md`
  - `README.md`, `plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- **Mechanisms touched:**
  - `Two-tier registry with a generated complete index`
  - `Session-start context delivery` (no change, used only to compare size rules)
- **Journal entries to re-read when promoting:**
  - `2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test`
  - `2026-10-28 — State the real trigger of a hook, not the printing condition`

---

> **Lifecycle:**
> - Created by `data-architect` for the parent contract's audit findings.
> - Tracked by one GitHub issue per contract, opened by the main session at `/design-first` Step 3.4.
> - Discovered by `/list-contracts` under the "Stubs / follow-ups" section.
> - Auto-archived by `.claude/scripts/archive_stale_stubs.py` if older than 30 days and never promoted.
> - `concept-gate.py` does NOT treat `Status: stub` as approved.
