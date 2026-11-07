# Follow-up — Pin the README folder-tree counts in the repository consistency suite

**Parent contract:** `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`
**Derived from:** review finding, not an Adjacent Areas scan: the t18 review's W1 and the reviewer's F2 (Revision 9, Open Question 30)
**Date:** 2026-11-03
**Status:** stub
**Estimated scope:** small
**Issue:** #165

## What was noticed

The t18 review (`.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t18-review-merge-and-text-fixes-fullstack-code-reviewer.md`, W1) found four folder-tree counts in `README.md` false against the tree: `hooks/tests/` (9, tree 23), `scripts/` (15 + 3, tree 23 + 3), `scripts/tests/` (11, tree 36) and `references/` (2, tree 3). They were already false at the merge base, on both sides of the merge. `test_repo_consistency.py` pins only the hook-file and registration counts, so nothing caught them. Block 19 of the parent contract corrects the four numbers; nothing keeps them correct afterwards.

The same review's B1 (base steps 6-9 of `skills/pr-merged/references/contract-completion.md` restored beside master's rewrite) passed every suite because no test pins the records procedure's step order. The user answered the parent's Open Question 31 "yes" on 2026-11-03, so block 19 delivers that step-order pin in `test_parent_branch_rule_text.py`. It is not part of this stub. The file name's "step-pins" refers to it as history only.

Two more items joined this stub in Revision 9:
- **The counting rule for "6 generic data files"** in the `.claude/hooks/` tree line. The folder holds six `.json` files, but `hooks.json` has its own tree line, which leaves five. Decide the rule, then correct the number and pin it with the other tree counts.
- **The manifest descriptions** (t18 I1). The descriptions in `plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json` and `.claude-plugin/marketplace.json` say "28 skills" (and 14 agents), while the tree has 33 skills and 15 agents. The landing does not correct them: `raise_manifests` rewrites only the `"version"` fields. The parent's Open Question 33 recommends one pull request to `master` after the landing, which corrects the descriptions from the tree's counts and takes a patch raise.

One more item joined this stub from the t20 re-review (its I2):
- **The `test_pr_merged.py` case count in two skill files.** `skills/pr-merged/SKILL.md` (lines 115 and 121) and `skills/advance/SKILL.md` (lines 100 and 101) say 760 cases, while the suite and `README.md` say 761. Neither file was in the Files to touch of blocks 17 or 19, so neither block could correct it. Decide whether the skill text should carry a count at all, or point at the suite, then correct both files together.

## Why it was deferred

The pin is a new check with design choices of its own (which tree lines it reads, how a helper module is told from a workflow script, and whether every pull request that adds a test must also edit the README), and it fixes nothing the t18 review blocked on.

## Suggested next step

Run `/design-first` on this stub. Decide first whether the tree should carry counts at all, or name the folders without numbers, before extending `test_repo_consistency.py` with a counter per tree line and a planted-wrong-count control.

## Pre-derived context

- **Adjacent area:** not applicable (`.claude/area-mapping.json` is empty in this repository)
- **Files implicated:**
  - `README.md` (the folder tree under the plugin layout section)
  - `.claude/scripts/tests/test_repo_consistency.py` (`readme_counts`, `stale_counts`, the hook-count tests)
  - `plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, `.claude-plugin/marketplace.json` (description strings only; Open Question 33 of the parent)
- **Mechanisms touched:**
  - none registered; the existing README hook-count pin in `test_repo_consistency.py` is the pattern to extend
- **Journal entries to re-read when promoting:**
  - `2026-11-01 — After merging a base that changes the row shape a feature reads, re-check every coverage claim and round-trip test against the merged writer`
  - `2026-11-02 — A rule titled 'every' must list every line it covers`

---

> **Lifecycle:**
> - Created by `data-architect` at Step 4.5 when an Adjacent Areas row is decided as `follow-up handle`.
> - Tracked by one GitHub issue per contract, opened by the main session at `/design-first` Step 3.4; the stub is the detail and the issue is what the user sees. A stub whose `Issue:` is still `pending` after approval is a defect.
> - Discovered by `/list-contracts` under the "Stubs / follow-ups" section.
> - Auto-archived to `<slug>.followup.archived.md` by `.claude/scripts/archive_stale_stubs.py` if older than 30 days and never promoted.
> - Promoted by running `/design-first` against the stub's `## What was noticed` paragraph — the resulting full contract should `superseded` this stub (rename the stub to `.followup.superseded.md` and add a `Superseded by:` line at the top).
> - `concept-gate.py` does NOT honor `Status: stub` as approved — you cannot write code authorized only by a stub.
