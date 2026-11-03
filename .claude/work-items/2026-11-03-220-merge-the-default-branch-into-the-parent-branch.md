---
id: 220
issue_offer: opened
title: Merge the default branch into the parent branch
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/220
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t17-merge-the-default-branch-into-the-parent-branch
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: UNKNOWN
issue_link: unknown
status: implementing
created: 2026-11-03
---

# Merge the default branch into the parent branch

## Problem statement
Sub-task 17 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 17. Merge the default branch into the parent branch (`python-ai-developer`)

*Revision 8 (2026-11-03), a remedy sub-task.* The user answered Open Questions 24-28 and the Revision 8 critique on 2026-11-03, and the answers are written in below. The amendment awaits only the user's final approval at `/design-first` Step 3. `Status` stays `approved` in the header for the blocks already delivered. It adds no data shape, mechanism or term. Blocks 1-16 keep their identities and records, and 9 and 10 stay as delivered.

**Why.** Landing run `20261103T101941Z-58fe7b` (`.claude/state/landing/2026-11-01-memory-client-and-cloud-engineering/report.json`) halted at gate P7, `unresolvable-conflict`: "`.claude/registries/JOURNAL.md` conflicts and is neither a union path nor regenerated". Nothing reached `master`. `master` (8ea2dd4, version 0.14.x) gained the records-leftover-cleanup work (#178 and later) after the parent branch (0.12.4) was cut, while block 9 appended to the same registry tails. The t10 review (`pass-with-findings`) also left text fixes W1, W2, I1, I2, I3 and I5 owed before the landing's flip; entries appended after that flip are never offered for capture.

**Conflicting files (computed 2026-11-03, `master` at 8ea2dd4; Open Question 24).** The main session ran `git merge-tree --write-tree --name-only origin/feature/memory-client-and-cloud-engineering origin/master`. It reports conflicts in exactly five files:
- `.claude/registries/JOURNAL.md`, `.claude/registries/MECHANISMS.md` and `.claude/registries/VOCABULARY.md`. Both sides appended at the end of the Universal tier. In JOURNAL.md, master added "2026-11-02 — A sweep that deletes every proven file..." and this contract added the t5 entry, both after the 2026-11-01 "After merging a base..." entry.
- `README.md`.
- `skills/pr-merged/references/contract-completion.md`.

Four files that both sides changed are auto-merged by git with no conflict: `.claude/scripts/pr_merged.py`, `.claude/scripts/tests/test_pr_merged.py`, `skills/flow/SKILL.md` and `skills/pr-merged/SKILL.md`. No manifest conflicts. That conclusion rests on the `merge-tree` result alone. The P7 halt on JOURNAL.md proves nothing about the manifests, for two reasons. With `versionRaise: true`, a manifest conflict is a `version-fields` case, not `halt` (`land_contract.py:1038-1039`). And `plugin.json` and `.cursor-plugin/plugin.json` sort after JOURNAL.md. If `master` moves before block 17 runs, git's own conflict list governs. A conflict in a file not listed below stops the block with `git merge --abort`.

**Version (Open Question 28, accepted).** No conflict with the version rule. The parent side never changed a manifest, and `merge-tree` reports no manifest conflict. So git takes `master`'s 0.14.x into all five entries, and no version file is edited by hand. The sub-task pull request is checked in `parent` mode (`check_version_bump.py:166-174`). That mode allows the base's version (0.12.4) or the version at `merge-base(origin/master, HEAD)`. After the merge, that merge base is the merged `master` commit itself, so 0.14.x is allowed and the check exits 0. It still exits 0 if `master` moves on later. Block 18's pull request is cut from the merged parent, where base and head both hold 0.14.x. The landing then merges `master` again, which is clean or a no-op, and `--raise` writes minor + 1 with patch 0 of `origin/master` (`exact_version`, `:91-97`). That is **0.15.0** while `master` stays on 0.14, and `--exact` checks the same value. A `master` that reaches 0.15 first moves the landing to 0.16.0. The precedent is block 6 of `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md` (#183, pull request #187).

**Journal entries for t10 W2.** The user confirmed all eleven, J1-J11 (Open Questions 25 and 26). They take the `/design-first` Step 3 shape.

The t10 review placed these entries in the landing's version-raise commit. Block 17 moves them into its own sub-task commit, for two reasons. The landing halts at P7 before its raise commit exists. And entries appended after the landing's flip are never offered for capture. `raise_manifests` commits only the manifests, so nothing is lost by the move. Source contract for all: `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`. The Trigger is `pre-approval critic` for J1-J10 and `post-impl divergence` for J11. Each title starts `2026-11-02 — `.
- **J1** (WARN reach) "A rule every session needs goes in a shipped agreement, not a once-run step". Lesson: before putting a standing instruction in an onboarding skill or one design step, check Session-start context delivery and list the routes (direct edit, `/debug`, `/journal-add`, sessions that never design) that would never see it. Apply when: a contract adds a standing instruction to `/auto-improve-finish-install`, one skill step or any once-run path. Tags: agreements, session-start, standing-guidance, reach.
- **J2** (WARN term collision) "Search a proposed term against agent frontmatter and host docs before adding it". Lesson: if the words already name something else (`memory: project`, the host's "project memory"), rename the term instead of adding "it is not X" to its definition. Apply when: a contract proposes a VOCABULARY term that reuses a word the repository or host already uses. Tags: vocabulary, term-collision, naming, agent-memory.
- **J3** (WARN `--fix`) "Describe a fixer a skill runs by everything it writes, and keep the skill's confirm-first promise". Lesson: describe `plugin_doctor.py --fix` (or any list-driven fixer) from its own requirement list (`REQUIREMENTS`, `apply_fixes`), and run it only after the user confirms the listed set. Apply when: a contract triggers `--fix` or another fixer that creates every missing item. Tags: plugin-doctor, fix-scope, confirmation, side-effects.
- **J4** (WARN tests) "Name the tests a fix may change by the state they guard, after reading them". Lesson: before telling an implementer to change tests "around" given lines, read each one; a test that guards a neighbouring invariant (here `disabled`, I-M0) is named as unchangeable. Apply when: a fix block's CONSTRAINTS tell the implementer to change or relax tests by line number. Tags: tests, invariant, fix-scope, line-reference.
- **J5** (WARN brief on the unconfigured path) "A path that calls a command must say how it finds the command's input". Lesson: when a step calls a command that needs an input (`record --brief`), state on that same path how the input is found and what happens when it is absent; a rule that lives only on a sibling path turns a normal case into a reported failure. Apply when: one branch of a skill step (unconfigured, disabled, error) calls a command whose argument is resolved only on another branch. Tags: skill-steps, missing-input, brief-linkage, degradation.
- **J6** (WARN Failure Modes) "A revision that adds a path adds its failure modes". Lesson: for each new script call, fixer run or degraded path a revision adds, add a Failure Modes entry whose mitigation cites a mechanism. Apply when: a contract revision adds blocks or Extension Points and leaves `## Failure Modes & Mitigations` unchanged. Tags: failure-modes, amendment, revision, completeness.
- **J7** (NIT stale lines) "After amending a contract, update every summary of the block graph". Lesson: re-check the header Revision line, the Handoff intro's block count and graph, and the prioritised plan's Depends on against the new blocks. Apply when: a revision adds, removes or re-links handoff blocks. Tags: amendment, summary-drift, handoff-graph.
- **J8** (NIT scope note) "Edit a reversed sentence where it stands". Lesson: when an amendment reverses an earlier claim, edit that sentence; do not keep it and add a later bullet that contradicts it. Apply when: a revision changes a claim made earlier in the same section. Tags: amendment, self-contradiction, scope-note.
- **J9** (NIT block 14 scope) "Keep a review-fix block to the review's findings". Lesson: put text for a new requirement in the block that owns the requirement, so each block's review judges one thing. Apply when: one revision adds both review fixes and a new user requirement. Tags: block-scope, review-fix, separation.
- **J10** (NIT suffix) "A rule titled 'every' must list every line it covers". Lesson: a rule for "every state" or "every printed line" names each line, including failure and skipped lines, and a test pins each. Apply when: a contract adds text to every output line or state of a step. Tags: every-claim, printed-lines, coverage.
- **J11** (t10 Disposition 7, verbatim from the review artefact) "A 'fails the build' claim must name the workflow that runs the check".
- No new entry (Open Question 25) for five findings, which re-apply existing lessons or are deferred:
  - the BLOCKER (re-applies 2026-10-22);
  - the WARN on the term definition (2026-10-28);
  - the WARN on "append on every run" (2026-10-04);
  - the WARN on the I2 reader (2026-10-15);
  - the budget NIT (deferred, Open Question 14).
- Critique rounds 1-3 were not journaled. No entries are added for them.

**Deferred review leftovers (Open Question 27).** The t16 review's W1 and I1-I5, and the t10 review's I4 and I6, go into one follow-up stub: `.claude/concepts/followups/2026-11-03-memory-boundary-review-leftovers.followup.md`, `**Issue:** pending`. No block of this contract fixes them.

**Main-session actions, outside any block:**
- Append the t10 reviewer-verdict line (Disposition 8) to `~/.claude/logs/reviewer-verdicts.jsonl`.
- In the parent brief, record "no new entry" for the five findings above, and that critique rounds 1-3 were not journaled.
- Create the follow-up stub named above and open its issue (`/design-first` Step 3.4).

**Depends on:** 9, 10

**Files to touch:**
- `.claude/registries/JOURNAL.md`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `README.md`
- `skills/pr-merged/references/contract-completion.md`
- `CONTRIBUTING.md`
- `skills/auto-improve-finish-install/SKILL.md`

The first five files are the computed conflicts; the last two take text fixes. No test pins the replaced sentences, so the text fixes change no test file. The four auto-merged files are not listed: they keep git's automatic merge and are not edited by hand.

**Pre-written TASK block:**
```
TASK: On the sub-task branch (cut from origin/feature/memory-client-and-cloud-engineering), run
  git fetch origin, then git merge origin/master, and resolve every conflict by hand. Commit the merge on
  its own. Then, in a second commit, apply the t10 text fixes and the confirmed journal entries.
  Merge:
  - Before resolving, list the conflicts (git diff --name-only --diff-filter=U) and quote them. If any
    conflicting file is not in Files to touch, stop, abort the merge (git merge --abort) and report the
    list: the contract must be amended first.
  - JOURNAL.md, MECHANISMS.md, VOCABULARY.md: both sides append at the end of the Universal tier. Keep
    every entry of both sides, verbatim, once each; never edit, reorder or drop an existing entry. Master's
    entries go first, then this contract's (precedent: block 6 of
    .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md). Keep each file's closing lines once.
  - skills/pr-merged/references/contract-completion.md: keep both sides' changes, so that both behaviours
    stay (master's records-leftover steps and this contract's step 5a capture).
  - Do not edit the four auto-merged files (pr_merged.py, test_pr_merged.py, skills/flow/SKILL.md,
    skills/pr-merged/SKILL.md). Check only that no function, class or test name is defined twice in
    them and every import is present; if one is, stop and report it (the contract must be amended).
  - README.md: keep both sides' sections. Every count (skills, agents, agreements, hooks, test cases of
    any suite either side changed) is rewritten from the merged tree and from what each suite reports
    when run; never add the two sides' numbers.
  Text fixes (second commit). Line numbers are from the parent tip before the merge and will shift in
  README.md; locate each sentence by its text.
  - W1, CONTRIBUTING.md:162-163: "A scan in .claude/scripts/tests/test_plugin_text_scans.py enforces it:
    run it before committing a change to a shipped file. It is not yet run in CI."
  - I1 and I2: one append-only sub-bullet under the Memory adapter entry of MECHANISMS.md:
    "**Correction (2026-11-03):** a new bullet registry as a capture source is one pair in the tuple in
    select_candidates; any other source kind is a new branch there with its own key and provenance rule
    (there is no source-kind table). The call is bounded by the host's MCP timeout, and by a deadline
    argument where the shape supports one (v0 sends deadline_seconds: 20)."
  - I3, in both README.md (~903, "The contract-critic reads it and never appends.") and
    skills/auto-improve-finish-install/SKILL.md (~292, "The `contract-critic` reads it and never
    appends."): replace with "The contract-critic appends only its Critique section to the contract
    under review, and never writes a registry."
  - I5, README.md:885-886: "With both off, every brief, every Step 1.5 run and every capture step is what
    it was before they existed. The Project history record rule below applies whatever the switches say."
  - W2: append to JOURNAL.md, after the merged tail, all eleven entries J1-J11 of block 17, in that
    order, each in the /design-first Step 3 shape (title "### 2026-11-02 — <title>", then
    Trigger, Source contract, Lesson, Apply when, Tags lines), J11 verbatim from the t10 artefact's
    Disposition item 7.
CONTEXT: concept contract, block 17 (Revision 8 note, conflict list, Version, journal entries); landing
  report .claude/state/landing/2026-11-01-memory-client-and-cloud-engineering/report.json; the t10 review
  .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t10-review-documentation-fullstack-code-reviewer.md
  (W1, W2, I1, I2, I3, I5, Disposition 7).
FILES: as listed.
CONSTRAINTS:
  - A change to any file not listed comes only from master through the merge; resolve nothing else by
    choosing a side.
  - Never edit plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json or
    .claude-plugin/marketplace.json by hand. The merge brings master's version; the landing raises once.
  - Registry text names no memory tool literally ("the configured retrieve tool", "the configured
    capture tool").
  - No conflict marker may remain in any file (search for "<<<<<<<", "=======" at line start, ">>>>>>>").
  - Run, and report the exit code and case count of: test_pr_merged.py (on its own; it is large),
    every .claude/hooks/tests/test_*.py except test_gate_cost.py, test_plugin_text_scans.py,
    test_registry_entries.py, test_repo_consistency.py, test_memory_boundary.py, test_memory_off_parity.py,
    test_plugin_manifests.py, test_auto_improve_finish_install.py, test_check_version_bump.py,
    test_parent_branch_rule_text.py, test_skill_script_lookup.py and test_cleanup_delivered.py (the
    last three read the merged skills/pr-merged/references/contract-completion.md, skills/flow/SKILL.md
    and skills/pr-merged/SKILL.md, and pin sentences in them), and
    py -3 .claude/scripts/check_version_bump.py --base origin/feature/memory-client-and-cloud-engineering
    --default-branch master --head-ref <this branch>. A failure that also fails on origin/master is
    reported as such, with the origin/master run quoted, and is not fixed here.
  - Every command in a form that runs in PowerShell.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

---

## Out of scope
- Everything outside this sub-task's handoff block; see the other sub-tasks of the contract.

## Known context
- Parent / epic: #161 (https://github.com/lneninger/claude-agentic-auto-improve/issues/161)
- Related items: the other sub-tasks of `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`
- Affected areas: the files named in the handoff block

## North-star alignment
- inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md

## Open questions from intake
- none; the sub-task's criteria were approved at the contract gate.

## Size
Task of .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md.

## Routing
task of .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md - dispatched by /advance
