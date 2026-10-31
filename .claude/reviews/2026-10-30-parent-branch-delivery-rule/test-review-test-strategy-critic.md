# Test Strategy Review: Parent Branch Delivery Rule (issue 113)

Reviewer: test-strategy-critic. Date: 2026-10-30. Branch: `feature/113-parent-branch-delivery-rule` vs `origin/master`.
Contract: `.claude/concepts/2026-10-30-parent-branch-delivery-rule.md` (approved).

**Counts: BLOCKER 2, WARN 8, NIT 8.** Verdict: **NEEDS FIXES**.

## How this was checked

- I read every test hunk on the branch, plus the production code each new test reaches (`pr_merged.py`
  `delivery_layout`, `landing_evidence_holds`, G-7 and accept, R-8, `effective_base`;
  `land_contract.py` P0, P1, P7, P7b; `check_version_bump.py`).
- **Mutations were EXECUTED, not just reasoned about.** Each one was applied in memory with
  `mock.patch.object` on the module function, the targeted test classes were run with `unittest`, and
  the result was recorded. No file was edited.
- I ran these suites: `test_check_version_bump`, `test_parent_branch_rule_text`, `test_skill_script_lookup` and
  `test_land_contract_conflicts`. That is 103 tests, all passing, in 351 s. Afterwards no `vbump-*` or `landtest-p7v-*`
  folder was left in `%TEMP%`.
- As instructed, I did not run `test_land_contract.py` or `test_cleanup_delivered.py`.
- I could not test a clean git environment. The worktree guard refuses `GIT_CONFIG_GLOBAL`. So W-5 below is
  reasoned from the code, NOT executed.

## Mutation results (item c)

| # | Mutation (production code) | Caught? | By |
|---|---|---|---|
| M1 | `landing_evidence_holds` drops the `base_is_default is not True` clause | **NO** (0 of 58 failed) | nothing |
| M2 | `landing_evidence_holds` drops `head_ref == layout.parent_branch` | **NO** (0 of 58 failed) | nothing |
| M3 | `--accept-single-branch` ignores sub-tasks still `awaiting-merge` | yes | `test_a_sub_task_awaiting_merge_is_refused` |
| M4 | G-7 always passes (`landing_evidence_holds` returns True) | yes (9 failed) | the `TestRecordDeliveryJudgesByEvidence` refusals, the legacy loop |
| M5 | a layout disagreement: header brief `branch: feature/p` but every Sub-Task brief has `base: feature/q` (this is not a code mutation; it is a fixture no test builds) | **NO**: `delivery_layout` reports no defect, `effective_base` cuts from `feature/q`, and the later landing of `feature/p` is refused by G-7 | nothing |
| M6 | `effective_base` ignores the layout, so it falls back to `default` for a judged contract | yes (1 new failure) | `test_status_reports_no_default_branch_base_...`: an unresolved block reports `base_source: None` (refused), and the mutant makes it `default` |
| M7 | `delivery_layout` drops the `no-parent-issue` defect | yes (5 new failures) | the `id` subtests, and the never-in-completion test |
| M8 | `delivery_layout` drops the `ambiguous` defect | yes (1 new failure) | `test_briefs_that_disagree_on_the_parent_branch_are_the_reused_ambiguous_defect` |

M6 to M8 ran over 206 tests (all new layout, dispatch and parent classes in `test_pr_merged.py`, plus
every class in `test_pr_merged_dispatch.py`). The baseline already had 2 failures, which W-8 covers.

## BLOCKER

### B-1. R-7's two evidence clauses are unpinned: M1 and M2 survive
- **Where:** `test_pr_merged.py`, `TestRecordDeliveryJudgesByEvidence`.
- **Gap:** `test_a_sub_task_merged_into_the_default_branch_is_not_a_landing` sets BOTH
  `base_is_default: True` AND `base_ref: master`.
  - The `base_ref == head_ref` clause alone refuses this fixture, so deleting the `base_is_default`
    clause changes nothing (M1).
  - No fixture has a pull request whose head is not the layout's parent branch while every record's
    `base_ref` equals that head. So deleting the "headRefName must equal the parent branch" clause also
    changes nothing (M2).
- **Why it matters:** R-7 names exactly these two facts as part of "delivery by evidence". Today they are
  decoration. A refactor can drop either one and the suite stays green. Then a pull request from any
  branch whose records point at it is accepted as the landing.
- **Fix:** add two fixtures.
  1. Records with `base_ref` equal to the parent branch AND `base_is_default: true` must be refused.
  2. A pull request from `feature/other`, with records whose `base_ref` is `feature/other` and a layout
     parent of `feature/p`, must be refused G-7.
     - It is reachable through a brief whose `pr:` link names a pull request whose `headRefName` is not
       the brief's `branch:`. Both the status path and G-1 accept a candidate taken from the link.
     - If G-1 always refuses such a pull request first, pin THAT in a test instead, and record the clause
       as defence in depth. Either way, one test must fail when the clause is deleted, or the clause
       should go.

### B-2. The row 2 "parity" test does not exercise the landing readers it names, so it misses a real reader disagreement (M5)
- **Where:** `test_pr_merged.py`, `TestTheReadersReturnTheSameBrief.test_all_readers_agree_for_every_contract_field_variant`.
- **Gap:** the entries labelled "landing P0 feeder" and "landing P1 feeder" are not P0 or P1. The test
  calls `select_linked_brief` itself on the output of `_briefs_on_disk` and `build_delivery_set`.
  - That proves only that the feeders stop filtering, which is already the next test's job.
  - The real P0 (`_launch_land`, `land_contract.py:3034-3046`) and P1 (`:2023-2044`) still take the
    parent branch from `declared_topology` over the Sub-Task briefs. `select_linked_brief` is only a
    fallback for the parent brief record (P1) and a "must be pushed" list (P0).
  - `delivery_layout` also takes the parent from the selector. And `effective_base` puts the topology
    first (rule 3) and the layout second.
  - In every fixture the parity test builds, the two sources agree, so it cannot see this.
- **Executed probe (M5):**
  - Header brief `branch: feature/p`, `id: 100`. Two child briefs, each `base: feature/q`.
  - Result: `delivery_layout` reports parent `feature/p` with **no defect**, while `effective_base`
    returns `feature/q` (`declared-topology`).
  - So dispatch cuts every sub-task from `feature/q`. Then the landing of `feature/p` fails R-7 (the
    records' `base_ref` is `feature/q`), and P1 is told a different parent than the briefs give.
- **Why it matters:** Failure Mode 2 ("the readers disagree") lists this test as its mitigation. The test
  passes on an implementation where the readers do disagree.
- **Fix:**
  1. Add a fixture where the header brief's `branch:` differs from the children's `base:`. Assert either
     that it is a layout defect (`ambiguous`), or that every reader (status layout, `effective_base`, P0,
     P1) names the same branch.
  2. Make the parity test drive `_launch_land`, P1 and `effective_base` through their real entry points
     (as `TestFeedersPassUnfilteredBriefs` does for P1), not through a hand-composed
     `select(feeder())`.
  3. The production gap goes to the implementer.

(An earlier draft had a B-3 here: "the row 7 test is vacuous". I withdrew it after the M6 run. A
`base_source` of `None` is `effective_base`'s refusal, and the mutant that returns `default` fails the
test. The remaining weakness is N-8.)

## WARN

### W-1. Item (a): the record-delivery write tests now pin only the `--accept-single-branch` path
- **Where:** `TestRecordDeliveryWritesTheStoreAndNothingElse`, `TestRecordDeliveryGuards.test_g4_passes...`,
  `TestFormatterChainReplay.test_run_4`, and the `M27` dry-run test.
- **Gap:**
  - Every write assertion (I-15, I-20 "the three tracked files", G-5 "second run is a no-op", "dry run
    writes nothing", "never overwrites") now runs only with `--accept-single-branch`.
  - The plain `--record-delivery` write path keeps only coarse positive controls: exit 0, and the record
    exists.
  - A mutation that differs only on the unflagged path (for example skipping `blocks_already_recorded`, or
    rewriting on a second run) survives.
- **Fix:** run the same class twice through a mixin.
  1. Its current two-block accept world.
  2. A single-block world (or an evidenced landing world) with the plain flags.

### W-2. Item (a), the L-4 change: the "no G-4 read for `id: none`" assertion was replaced, not moved
- **Gap:**
  - The old assertion `assertFalse(gh_open_sub_issues.called)` pinned that a brief with no parent issue
    costs no GitHub read.
  - It was rewritten into "exactly one read of 100", which is correct for the new world.
  - The original branch (`pr_merged.py:4163`, `parent_id.lower() not in ("", "none")`) now has no
    spy-level test.
  - It is protected only indirectly: `test_positive_control_one_mergeable_block_is_judged_as_before`
    would fail with exit 9 `brief-id-unreadable` if the guard went. So the outcome is covered, but the
    "no read" property is not.
- **Fix:** keep the old assertion on a single-block, `id: none` world.

### W-3. Item (a): the wrong-owner control no longer controls the tests it was written for
- **Where:** `TestWrongOwnerResolvedRefusesBeforeAnyWrite.test_control_the_right_name_still_lets_both_writing_runs_write`.
- **Gap:**
  - The comment still says "the same fixtures with the real blocked report named".
  - The two wrong-name tests still use `_last_block_world()` and `_delivery_world(self)`: `id: none`,
    the sub-task merged into `master`, no accept flag.
  - The control now builds a different world: a valid parent, a parent base and `--accept-single-branch`.
  - With the right name, the record-delivery world of the wrong-name test would now be refused by G-7 and
    write nothing. So its "writes nothing" assertion is vacuous.
  - Only the `error == owner-resolved-not-blocked` assertion still carries the test.
- **Fix:** give the two wrong-name tests the same new worlds as the control.

### W-4. The accept refusals assert the exit code but not the reason
- **Where:** `TestAcceptSingleBranchRefusals`.
- **Gap:**
  - `test_a_failed_record_is_refused` and `test_a_pull_request_that_is_not_merged_is_refused` assert only
    `exit_code == 9`.
  - The failed-record case is refused by the pre-existing G-3, not by anything new. So this test does not
    prove that the accept path checks failed records; it passes because G-3 runs first.
  - That is acceptable, but unstated. If G-3 is ever reordered after the accept branch, the test cannot
    tell which guard fired.
- **Fix:** assert `guard` and `reason` on each refusal: `G-3 failed-record`, `G-1 ...`, and
  `G-7 sub-task-awaiting-merge`.

### W-5. Item (d): the `--raise` tests depend on the developer's global git identity (reasoned, not executed)
- **Where:** `test_check_version_bump.py` `VersionRepo.run`, `RaiseTests`, `ExactModeTests` (via
  `--raise`), and `test_land_contract_identity.py` `TestP7bVersionRaise`.
- **Gap:**
  - The fixture's own git calls carry `_GIT_ENV` (identity, `GIT_CONFIG_NOSYSTEM`, and
    `commit.gpgsign=false` through `-c`).
  - But the script under test is spawned with the inherited environment. Its `raise_manifests` then runs
    `git commit` with no `-c commit.gpgsign=false` and no identity.
  - The clone has no local `user.name`. On a machine with no global identity (a fresh CI runner, a
    consumer), or with `commit.gpgsign=true`, `--raise` fails with exit 2, and those tests fail for
    reasons unrelated to the code.
  - Today no workflow runs the suites (only `version-bump.yml` exists), so this has not shown up.
- **Fix:** pass `env=_GIT_ENV` (plus `GIT_CONFIG_GLOBAL` pointing at an empty file) to `VersionRepo.run`,
  and in `TestP7bVersionRaise`; or set `user.name`, `user.email` and `commit.gpgsign` in the clone's
  local config.

### W-6. R-3's switch dependency in `classify_conflict` is unpinned
- **Where:** `test_land_contract.py` `TestVersionFieldsConflictClass` and `test_land_contract_conflicts.py`
  `TestP7VersionFieldConflicts`.
- **Gap:**
  - Every case uses `versionRaise: True`.
  - `classify_conflict` returns `version-fields` only when the switch is on (`land_contract.py:1038`).
    No test asserts that a MANIFESTS path with the switch off is still `halt`.
  - Removing `config.get("versionRaise") is True` would silently resolve version conflicts in every
    consumer project that never opted in.
- **Fix:** add one `classify_conflict(path, {"versionRaise": False, ...}) == "halt"` case for each
  manifest path.

### W-7. L-4's "or a protected branch" has no test, and the code does not implement it
- **Gap:**
  - `delivery_layout` refuses only `branch == default` (`pr_merged.py:1591`). Every test uses
    `branch: master`.
  - A brief whose `branch:` is a protected branch (for example `release`, listed in
    `contractLanding.protectedBranches`) yields no defect at status or at dispatch. P0 and P1 do check
    protected branches, so the landing would halt late.
- **Fix:** add a fixture with a protected-branch `branch:` and assert `parent-is-default`. This test will
  fail today and expose the gap; send the fix to the implementer.

### W-8. Two tests in `test_pr_merged_dispatch.py` fail on this branch, and their skip guard does not skip them
- **Where:** `DispatchIdentityAmbiguousTests` (`test_dispatch_refuses_identity_ambiguous_before_rule_one_is_read`
  and `test_status_reports_identity_ambiguous_without_refusing`). Run alone, both fail with
  `None != 'identity-ambiguous'`.
- **Gap:**
  - The class is guarded by `@unittest.skipUnless(hasattr(pr_merged, "brief_for_branch"))`. But
    `brief_for_branch` already exists on `origin/master`.
  - So the "contract 460 is not on this branch" skip never fires, and Rule 0 is still not built
    (`effective_base` docstring).
  - This branch did not touch that class or Rule 0, so the failures are most likely older than issue 113.
    I did NOT run them on `origin/master` to confirm.
- **Why it matters:** a red suite that everyone has learned to ignore hides new reds. Any "the suite
  passes" claim for this branch has to name these two failures.
- **Fix:** gate the class on the symbol Rule 0 actually adds, or mark the two tests as expected failures
  with the contract 460 reference. Either way, the dispatch suite then tells the truth.

## NIT

- **N-8.** `test_status_reports_no_default_branch_base_...` asserts `base_source != "default"`. That also
  passes if the report drops `base_source`, or if the base is wrongly taken from a state entry. Assert the
  refusal itself: `base_source is None` together with `base_problem == "base-not-declared"`, or whatever
  field the report carries.

- **N-1. Item (b): wording tests.** `test_parent_branch_rule_text.py` is a regex check over whole flattened
  files. About a third of its checks pin identifiers that the scripts emit or accept (`layout_defects`,
  `needs-issue`, `--accept-single-branch`, `single-branch-accepted`, `G-7`), and those are worth keeping.
  The rest pin prose:
  - the exact sentence `"This item has no GitHub issue, so its contract must be a single block."`;
  - `never run|does not run|...`;
  - `"has already cut the branch"`;
  - `(always|mandatory)` near "Work Item Brief".

  These break on a harmless edit, and many can be satisfied by an unrelated paragraph (`[^.]{0,500}`
  windows over a whole file).
  - **Fix:** derive the expected tokens from the scripts instead of from the authors' wording. For
    example: every `pr_merged.LAYOUT_DEFECT_REASONS` member appears in the `/design-first` gate section,
    and the literal command string that `next_command_for` builds for R-9 appears in `/advance` and in
    `contract-completion.md`.
- **N-2.** `FlowTextTests.test_a_contract_with_no_parent_branch_is_only_a_single_block_contract` loops over
  sentences that contain "no parent branch". If those sentences are deleted, it passes vacuously. Add
  `assertTrue(found)`.
- **N-3.** `PluginVersionTextTests` asserts `>= (0, 11)`. That pins this one PR and nothing after it. It
  overlaps with `test_plugin_manifests.py`'s agreement check. Delete it, or pin it against
  `exact_version(origin/master)`.
- **N-4. Redundancy.** `TestCleanupStillUsesTheWrapper` (`test_pr_merged.py`) and
  `ParentBranchRuleLeavesCleanupUnchangedTests.test_the_call_site_is_unchanged`
  (`test_cleanup_delivered.py`) are the same source-text grep. Keep one; the behavioural wrapper table is
  the one worth having. `ManifestsSingleSourceTests` is a source grep too: it catches `"plugin.json"`
  written in double quotes only.
- **N-5.** `TestDesignFirstApprovalGateLookup.test_the_gate_block_is_the_same_text_as_the_standard_one`
  compares only `gate[0]`. A second, divergent block in the skill would pass.
- **N-6. Process.** The implementation commit `2ce0bed` edited one RED test
  (`test_a_valid_layout_reports_an_empty_defect_list_and_still_dispatches`, a fixture changed to `pr: none`)
  and the 17 legacy tests in the same commit as the production change. Each edit carries its reason in a
  comment, and I judged the reasons sound, except W-3. In future, put fixture rewrites in a separate
  commit, so the change a reviewer sees in RED-to-GREEN is only production code.

- **N-7. Runtime.** Measured times:
  - `test_check_version_bump` runs 36 tests in 91 s, about 2.5 s each. Every parent, exact and raise case
    builds a bare origin and a clone.
  - `TestP7VersionFieldConflicts` runs 5 tests in 15.5 s.

  `evaluate_parent`, `exact_version` and `evaluate_exact` are pure functions. Test their table (the
  boundary cases: patch, major, double minor, disagreeing entries, unparsable versions, and default
  manifests that disagree, which `max()` hides today) in milliseconds. Keep only one or two process tests
  per mode, for the git wiring.

## Items (d) and (e) summary

- **(d) Real-git tests.**
  - **Isolation:** good. Every repository is a fresh `mkdtemp` or `TemporaryDirectory`. Bare origins are
    local, and the landing tests use the `Kit`/`Stage` fake network edges.
  - **Windows cleanup:** `force_rmtree` (chmod and retry, with `onexc` on 3.12) is correct, and no folder
    was left behind after the run. It is copied verbatim into two files; move it into one shared helper.
  - **Flakiness:** no sleeps and no clock use. The one real risk is the git identity and signing
    dependency (W-5).
  - **Runtime:** 103 tests in 351 s across the four suites I ran. N-7 gives the per-suite times of the new
    classes. That is slow for the unit tier, but within reason for real-git integration.
- **(e) Parity test.** See B-2: it pins that the feeders do not filter, not that the readers agree.

## Recommended test-suite shape

- Keep the file-backed `_World` CLI tests for R-6 to R-9. They assert observable outcomes (exit code,
  guard, snapshot unchanged, printed command), which is the right level.
- Add:
  1. two evidence fixtures for B-1, plus the guard and reason asserts of W-4;
  2. one disagreement fixture driven through `--status`, `--dispatch`, P0 and P1 (B-2);
  3. one protected-branch fixture (W-7);
  4. one switch-off `classify_conflict` case (W-6).
- Turn about half of the text tests into token-derived checks (N-1).
- Move the pure version logic to table tests (N-7).
- Pin the git environment of the spawned script (W-5).
- Fix the skip guard of the two failing identity tests (W-8).

## Verdict

**NEEDS FIXES.** The structure is good: real CLI drives, snapshot no-write checks, and real git where git
is the subject. But two of the protections named in the contract are weaker than claimed:
- two R-7 evidence clauses survive being deleted (M1, M2);
- the row 2 parity test cannot see a real reader disagreement (M5, which leaves the dispatch on the
  wrong parent branch with no defect reported).
