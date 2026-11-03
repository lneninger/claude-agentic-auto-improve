# t5 review — fullstack-code-reviewer

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t5-review (issue #157, parent issue #148)
- **Contract:** `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md` (approved)
- **Reviewed on:** 2026-11-01
- **Commit range reviewed:** `3b89bea..c1eda3c` (parent branch `feature/148-plugin-owns-hook-mechanism-tests`, from the commit that opened the contract and the sub-task briefs to the merge of pull request #162, t4)
- **Sub-task merges in the range (first parent):** t1 `9149eb5` (#158), t2 `3f12b05` (#159), t3 `7e5ff77` (#160), t4 `c1eda3c` (#162)

**Verdict:** pass-with-findings

## What was checked

| Item | Outcome |
|---|---|
| HR-1..HR-5 each with a test | **Met.** One pure function per rule in `RULES` (`check_hook_registrations.py:442-448`); each rule broken alone gives exit 1 naming only that rule (`assert_only_fails`, `HookGatingTests`, `RegistrationRowsUnchangedTests`, `RuleFailureTests`); a fixture breaking all five gives five FAIL lines; all five are always evaluated in order. |
| RP-1..RP-8 each with a test | **Met.** RP-1/RP-2: `BuildProfileTests` (two builds give identical bytes, no BOM, two-space indent, key order, one newline, no time/hash/host/absolute path); RP-3: `test_row_count_includes_excluded_rows...`; RP-4..RP-7: `test_hook_registration_profile_unreadable_for_each_breach`; RP-8: `ProfileSetupTests.test_profile_setup` (stale Exclusion kept) and the recorder's `test_existing_exclusions_are_kept_verbatim_and_stale_ones_are_listed`. |
| Settings shape, one test per malformed level | **Met.** `SHAPE_CASES` covers hooks, event value, group, matcher, group `hooks` absent and not a list, handler, type, command, args, each arg; duplicate key at top and handler level; UTF-16; invalid JSON; not-object; BOM accepted; no `hooks` key gives zero rows. |
| The seven refusal codes, each with a test, all exit 2 | **Met.** `RefusalTests` covers `paths-not-given` (and no cwd/environment fallback), `settings-missing` (root set, root absent, explicit paths), `settings-unreadable` (every kind, folder), `hook-registration-profile-missing` (remedy names `record-registrations`), `hook-registration-profile-unreadable`, `checker-internal-error` (one line, exit 2), `checker-dependency-missing` (in process and as a copy alone in a temporary folder). |
| Profile bytes hold no volatile value; preview then apply succeeds | **Met.** No time argument exists; `test_the_preview_writes_nothing_and_the_apply_writes_a_profile_the_check_accepts`, `test_an_unchanged_rerecord_reports_nothing_to_write_and_keeps_the_bytes`, changed-since-preview after a settings change and after a profile change. |
| The five equivalent tests exist and run | **Met.** `HookGatingTests.test_hook_gating`, `RegistrationRowsUnchangedTests.test_hooks_block_equals_base_apart_from_if_keys`, `RegistrationRowsUnchangedTests.test_row_count_is_unchanged`, `ProfileSetupTests.test_profile_setup`, `RegistrationCoverageTests.test_real_settings_every_registration_is_profiled_or_excluded` (records from the shipped `hooks.json`, checks clean, one unrecorded row gives HR-4). All pass. |
| The checker is the only place the rules live | **Met.** The rule names appear only in the checker, its suite, `VOCABULARY.md` and the contract. The recorder calls `checker.build_hook_registration_profile`, `serialise`, `read_rows`, `_matches`; it has no rule code of its own. |
| Every exit-code step gets a step unit with a reason | **Met.** `failure_units` (`land_contract.py:1363-1375`); `TestAttributionOnThisRepositorysSteps.test_every_step_gets_one_entry_with_a_reason_and_the_note_is_written`. |
| FA-1..FA-5 advisory (verdict, exit codes unchanged) | **Met.** Attribution is computed after `verdict` is fixed in `_p8_verify` (`:2754-2762`) and writes only two new record keys; `evaluate_gates` and the halt's outcome are untouched. One unit test per rule with a control (`TestAttributionRules`). |
| Only named files decide a side | **Met.** `_named_files` (`:1394-1411`) feeds FA-1..FA-4; `when_paths` only feeds an FA-5 reason (`test_fa5_a_when_paths_match_never_decides_a_side`). |
| A reasons-only NOT-READY gives `[]` and no advice | **Met.** `TestEmptyListAndRecord.test_a_not_ready_from_reasons_only...` through `_p8_verify` in a temporary repository: `[]`, the "no step regressed" note naming the reason, both facts false. |
| `all_outside_diff` needs a named test unit | **Met.** `advice_facts` (`:1487-1495`); `test_outside_diff_steps_without_a_test_unit_are_not_all_outside_diff`. |
| `step_failures_only` drops the re-record command and names the default-branch check | **Met.** `next_command_for_outcome` (`:1655-1661`) returns `[advance_line]` and the "check whether the default branch fails the same step (<ids>)" reason; the ids are the failing steps (`_land`, `:2370-2371`). |
| Both facts in `make_report`'s allow-list and reach `report.json` through real landing tests, one per branch | **Met.** Allow-list at `:1900-1903`; `TestStageFailureAttributionReachesTheReport` drives the end-to-end landing fixture: (a) named test outside-diff gives `outside_diff` true, the Q1 advice and the re-record command; (b) exit-code step outside-diff gives `outside_diff` false, the same-step reason and no re-record; in-diff controls for both; the repeat branch keeps precedence. |
| Landing's own paths use HEAD captured before P7b and include the version files | **Met in code; integration test thin (N5).** `head_before_p7b` is captured after `gate_check("P7")` and before P7b (`:2330`); `landing_paths` = diff(head_before_p7b, head) when they differ, plus hand-resolved paths, plus `MANIFESTS` (`:2351-2352`). The default-branch diff is captured before P7b reassigns `merge_diff` (`:2329`). |
| Checker sets `dont_write_bytecode` before its import; tree-unchanged test runs a copy outside this repository | **Met.** Statement after `import sys` (`check_hook_registrations.py:23`), before the guarded import (`:49-52`); `test_the_bytecode_flag_is_the_first_statement_before_the_guarded_import`; `assert_tree_unchanged` copies the five files into a `tempfile` folder, strips `PYTHONDONTWRITEBYTECODE`/`PYTHONPYCACHEPREFIX`, runs with and without `-B`, snapshots every path and hash. |
| `record-registrations` tested run as a script | **Met.** `test_the_subcommand_runs_as_a_script_with_a_second_installer_copy` (preview then apply, `py -3 -B auto_improve_finish_install.py ...`). |
| One Settings shape validator serves check and recorder and refuses a hooks-less group; `_parse_settings` unchanged | **Met.** The recorder reads through `checker.load_settings` and maps `shape` to `unexpected-settings-shape`, the rest to `malformed-settings`; `group with no hooks key` is refused in both; the diff does not touch `_parse_settings`, and `test_parse_settings_still_accepts_what_the_recorder_refuses` pins it. |
| Block 3's conventions test hard-codes no step id or count; the conventions `$comment` names it | **Met.** `TestAttributionOnThisRepositorysSteps` derives everything from the loaded steps and asserts at least one step of each kind; the `$comment` names `.claude/scripts/tests/test_land_contract_verification.py`. |
| Q1 answer (as narrowed) in the code and the README | **Met, README wording slightly narrower than the code (N3).** |
| README: five-file vendored set, `py -3 -B` explicit-argument step, no plugin-root alternative, undetermined limit for this repository's step, no version number | **Met.** All four present; the new README text carries no version number ("326 cases" is a test count). |
| No bare "profile" names the new concept | **Partly met (W1).** Two operator-visible strings and four identifiers in the checker use bare "profile". |
| No module-level circular import | **Met.** The installer imports the checker inside `_plan_hook_registration_profile` only; `test_each_module_imports_first_in_a_fresh_process` asserts it is absent from `sys.modules` after importing the installer. |
| No sub-task pull request changes a version file | **Met.** No `MANIFESTS` path in `git diff --stat 3b89bea c1eda3c`; `check_version_bump.py` in parent mode passes. |
| Registry appends verbatim and Universal-tier | **Partly met (N2).** All appends are at the end of the only (Universal) section of each file and edit no existing entry; three of the four VOCABULARY definitions are lightly reworded from the contract. |
| Contract alignment: Files to touch | **Met.** The 17 changed files are exactly the four blocks' lists plus their four work-item briefs. Adjacent Areas: not applicable per the contract (no area mapping), so no off-area drift. |

## Findings

**W1 — warning — naming rule: bare "profile" in operator text and identifiers.** `check_hook_registrations.py:586` (the `--project` help: "project root holding .claude/settings.json and the profile") and `:337` (the RP-6 refusal message: "excludes a row the profile expects"). Both reach the operator. The contract's naming rule also covers identifiers that name the concept: `ProfileError` (`:90`, public, and referenced by the installer as `checker.ProfileError`), `PROFILE_FORMAT` (`:60`), `PROFILE_FILE_NAME` (`:62`) and `_validate_profile` (`:303`). Fix: "and the hook registration profile", "a row the hook registration profile expects"; rename to `HookRegistrationProfileError`, `HOOK_REGISTRATION_PROFILE_FORMAT`, `_validate_hook_registration_profile` (and the installer's one reference). No test changes needed beyond the rename.

**N1 — nit — dead constant.** `check_hook_registrations.py:62` `PROFILE_FILE_NAME` is never read; `_run` rebuilds the path inline (`:533-534`). Use it or drop it.

**N2 — nit — registry appends are not word-for-word.** `.claude/registries/VOCABULARY.md:93-96` against the contract's "New terms": Registration row ("Identity text:" became "The identity text is"), Hook registration profile (adds "(an Ownership tier of local)"), Failure attribution ("one new P8 failure unit" became "one new verification failure"). The meaning is unchanged and the MECHANISMS entry and correction line are faithful; recorded so the carry-forward is a deliberate choice.

**N3 — nit — README states the Q1 condition more narrowly than the code.** `README.md` (Hook registration checks note): "only when every new failure is an `outside-diff` named test regression". `advice_facts` (`land_contract.py:1492-1494`) also sets `all_outside_diff` when step units are present beside at least one test unit, all `outside-diff`, which is the contract's definition. Suggested wording: "only when every new failure is `outside-diff` and at least one is a named test regression".

**N4 — nit — the recorder's checker import is unguarded.** `auto_improve_finish_install.py:3078` (`_plan_hook_registration_profile`): `import check_hook_registrations as checker`. A project that vendored the installer but not the checker gets a traceback and exit 1 from `record-registrations`. The contract's recorder refusals do not cover this case, so it is not a divergence; a named refusal (exit class 2) naming the five-file set would match how the checker handles the same gap.

**N5 — nit — the P7b wiring has no end-to-end pin.** FA-1 is unit-tested through `AttributionSides` only. No stage test asserts that a file the P7b commit changes reads `undetermined` in a real landing, and because `MANIFESTS` is always in the landing side, a broken `head_before_p7b` capture would not fail any test today. Low risk (the version raise only touches `MANIFESTS` paths), but the capture is currently untested.

**N6 — nit — `if` type not validated in the profile.** `_validate_profile` (`check_hook_registrations.py:314-325`) accepts a Profiled row whose `if` is not a string; the contract's Profiled row says "string, or absent". HR-3 still compares canonically, so the effect is only that a hand-edited malformed value is read rather than refused.

**Observation (not from this range).** `test_land_contract_verification.py` has two failing tests in `RealProjectConfigTests` (`generated-drift` must be the last step; a `python-scripts` step must exist). They assert a consuming project's configuration, the asserting lines are not touched by this range, and the base configuration's last step was already `hook-tests`. The file is not a landing step here, so this does not affect the landing, but "the existing tests stay green" cannot be read for that file. Likewise `test_land_contract.py` has one failing test, `TestContainmentScanner.test_the_real_tree_holds_no_merge_outside_land_contract`, which flags `skills/ship/SKILL.md` for `gh-pr-merge`; that file is not in this range. Neither file is a landing step in this repository. Worth a follow-up item for all three.

## What was NOT checked

- The landing itself (P7b raising 0.12.1 to 0.13.0) and the `hook-registration-tests` step running inside a real landing: they happen after this gate.
- A consuming project (`StockToolScalpingMachine`) adopting the check: out of scope per the contract's Non-Goals.
- Import-time behaviour of `pr_merged.py` and `plugin_doctor.py` was not traced line by line; it rests on the passing copy-outside-the-repository test, as the contract's Confidence section states.
- The `hooks` and `addon` subcommands were not exercised beyond their existing tests in the finish-install suite (which passed).
- Linux/macOS behaviour (the suites ran on Windows only); the symbolic-link test ran rather than skipping here.
- `~/.claude/logs/reviewer-verdicts.jsonl` was not appended: the caller limited writes to this artefact and its Gate Output.

## Evidence

| Command (run from the worktree) | Exit code | Result |
|---|---|---|
| `git log --oneline --first-parent -15` | 0 | range `3b89bea..c1eda3c`, four sub-task merges |
| `git diff --stat 3b89bea c1eda3c` | 0 | 17 files, 2915 insertions, 24 deletions; no version file |
| `py -3 .claude/scripts/check_version_bump.py --base 3b89bea --default-branch master --head-ref task/2026-10-31-plugin-owns-hook-mechanism-tests/t5-review` | 0 | "sub-task pull request keeps version 0.12.1; the landing raises it" |
| `py -3 -B .claude/scripts/tests/test_check_hook_registrations.py` | 0 | 72 tests, OK |
| `py -3 -B .claude/scripts/tests/test_auto_improve_finish_install.py` | 0 | 326 tests, OK |
| `py -3 -B .claude/scripts/tests/test_auto_improve_finish_install.py TestRecordRegistrations -v` | 0 | 22 tests, OK; the symbolic-link test ran (not skipped) |
| `py -3 -B .claude/scripts/tests/test_land_contract_verification.py` | 1 | 74 tests, 2 failures, both in `RealProjectConfigTests` (pre-existing, see Observation); every new attribution test passes |
| `py -3 -B .claude/scripts/tests/test_land_contract.py` | 1 | 310 tests, 1 failure, 1 skipped. The failure is `TestContainmentScanner.test_the_real_tree_holds_no_merge_outside_land_contract` on `skills/ship/SKILL.md` (`gh-pr-merge`), a file this range does not touch (last changed in `6abbcc0`); pre-existing, see Observation |
| `py -3 -B .claude/scripts/tests/test_land_contract.py TestStageFailureAttributionReachesTheReport` | 0 | 5 tests, OK (both report branches, both controls, repeat precedence) |
| `git log --oneline -2 -- .claude/skills/ship/SKILL.md skills/ship/SKILL.md` and `git diff --name-only 3b89bea c1eda3c` | 0 | the failing scanner's file is outside the range |
| `git status --short` (after the suites) | 0 | only this review folder is new: the suites leave the tree unchanged |
| Grep for the five rule names across the repository | 0 | only the checker, its suite, `VOCABULARY.md`, the contract |
| Grep for bare "profile" in the checker and in the diff's added lines | 0 | the hits listed under W1; none in the installer's new text, `land_contract.py`, README or registries |

Files read: the contract (whole); `check_hook_registrations.py` (whole); the diffs of `auto_improve_finish_install.py`, `land_contract.py`, `work-item-conventions.json`, `README.md`, `MECHANISMS.md`, `VOCABULARY.md` and the three test files; `land_contract.py:1602-1672` and `:2300-2390`; `auto_improve_finish_install.py:1040-1105` (`_hook_key`, `_Registration.key`, `_iter_hooks`) and `:143-150` (`EXIT_CLASS`).

## Disposition

Nothing. This gate releases its dependents. W1 should be fixed before the landing if convenient (two strings and four renames, no behaviour change); the nits and the three pre-existing test failures (two in `RealProjectConfigTests`, one in `TestContainmentScanner`) can go to a follow-up item.
