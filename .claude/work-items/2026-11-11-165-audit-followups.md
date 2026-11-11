---
id: 165
issue_offer: pending
title: Follow-ups from Memory-system client boundary and cloud engineering capability (2026-11-01-memory-client-and-cloud-engineering)
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/165
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/165-audit-followups
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261111-infra-165-audit-followups
north_stars: none
contract: .claude/concepts/2026-11-11-audit-followups-165.md
pr: UNKNOWN
issue_link: unknown
status: designing
created: 2026-11-11
---

# Follow-ups from Memory-system client boundary and cloud engineering capability

## Problem statement
The audit and reviews of the parent contract `2026-11-01-memory-client-and-cloud-engineering` (parent issue #161) found defects that cost tokens or correctness but were out of that work's scope. Issue 165 collects them. Detail files: `.claude/concepts/followups/2026-11-01-token-efficiency-and-audit-defects.followup.md`, `2026-11-03-readme-tree-counts-and-step-pins.followup.md`, `2026-11-03-memory-boundary-review-leftovers.followup.md`.

## Scope assumption (stated, not asked)
The issue is a bundle. This run takes every item that is a concrete defect. Items that are questions about intended behaviour or design are NOT guessed here: they go to the contract as Open Questions for the owner. If the owner wants a narrower slice, they say so at the contract gate.

## Acceptance criteria
- [ ] `skills/task/SKILL.md` contains "Step 1.5: Enter a worktree" exactly once, and its Step 5c no longer describes a recipe the skill does not run for a fresh item (the proof that still applies is kept).
- [ ] `skills/flow/SKILL.md` Step 2.7 body lives under `skills/flow/references/` and SKILL.md points at it with the "read in full when the case applies" rule; behaviour is unchanged and the existing text pins still pass.
- [ ] The concept-contract template's "Chat Tool Impact" section names no file or phase of any consuming project.
- [ ] `skills/debug/SKILL.md` routes only to agents this plugin ships, or to a project-supplied agent by a generic phrase.
- [ ] Manifest descriptions and README state the real skill and agent counts, and a test in `test_repo_consistency.py` fails when they drift (planted-wrong-count control included).
- [ ] `memory-pager.py` writes no `config-load-failed` line when a project has no `memory-blocks.json`; it still logs a real load failure (a malformed file).
- [ ] The data-architect agent file no longer tells the agent to read registry files that do not exist in this repository, or says to read them only when present.
- [ ] `finish-install` Stage 1a asks before running the doctor's `--fix` (t16 W1).
- [ ] The wording and test-strength leftovers t16 I1, I2, I3 and t10 I6 are corrected; the `test_memory_off_parity.py` assertion in I3 can fail (planted control).
- [ ] The `test_pr_merged.py` case count in `skills/pr-merged/SKILL.md` and `skills/advance/SKILL.md` agrees with the suite, or both point at the suite instead of carrying a number.
- [ ] Failure path: each new pin has a planted-wrong control that is shown to fail before the fix.

## Out of scope
- Anything in the plugin that the three stubs do not name (unrelated refactoring).
- Behaviour changes to the memory exchange beyond the Open Questions below, until the owner answers them.
- The post-landing manifest patch version raise: the stub says it follows the parent landing as its own pull request. The count text fix is in scope; the version bump is flagged for the contract.

## Known context
- Parent / epic: issue #161, contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`
- Related items: #161
- Affected areas: `skills/task`, `skills/flow`, `skills/debug`, `skills/auto-improve-finish-install`, `skills/pr-merged`, `skills/advance`, `skills/design-first/references/central-memory.md`, `agents/data-architect.md`, `.claude/templates/concept-contract.md`, `.claude/hooks/memory-pager.py`, `.claude/project-profile.md`, `README.md`, four manifests, `.claude/scripts/tests/test_repo_consistency.py`, `test_memory_off_parity.py`
- Shipped-plugin mirror: confirm whether `skills/` and `.claude/` copies must stay in step (the repo carries both); the contract decides.

## North-star alignment
- none: the register holds no active thought (`.claude/north-stars/` does not exist).

## Open questions from intake
- Should the README folder tree carry counts at all, or name folders without numbers? → **Answer:** pending, owner decides at the contract gate.
- Counting rule for "6 generic data files" in the `.claude/hooks/` tree line (six `.json` files, `hooks.json` has its own line). → **Answer:** pending.
- Should skill text carry a test case count, or point at the suite? → **Answer:** pending (recommend point at the suite).
- t16 I4: on `enabled`, an empty retrieval prints nothing and records nothing, but the Data Shapes row says otherwise. Fix the code or the row? → **Answer:** pending.
- t16 I5: rewriting the section under `unconfigured` drops earlier `Retrieved:` lines. Intended? → **Answer:** pending.
- Is the manifest patch version raise part of this pull request or the separate post-landing one? → **Answer:** pending (recommend separate, per the stub).

## Size
L: more than ten files across skills, an agent, a template, a hook, four manifests and two test files; it touches a hook with code behaviour and test pins.

## Routing
non-trivial → /design-first (one block per skill file, per the stub's suggestion)
