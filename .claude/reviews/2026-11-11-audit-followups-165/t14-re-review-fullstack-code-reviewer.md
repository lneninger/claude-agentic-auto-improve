# Re-review: audit follow-ups 165, blocks 1-9, 12 and 13, and the default-branch intake (t14)

- **Gate agent:** `fullstack-code-reviewer`
- **Sub-task:** t14-re-review
- **Contract:** `.claude/concepts/2026-11-11-audit-followups-165.md` (Revision 4)
- **Reviewed on:** 2026-11-12
- **Commit range reviewed:** `d538e8a..2b9ad3c` (the merge base with `origin/master` before the intake .. the tip of `feature/165-audit-followups`, which is also this branch's HEAD). Blocks 1-9 merged as #365, #367, #369, #371, #374, #377, #379, #381, #383; block 12 as #392 (`894d999`); block 13 as #394 (`481db27`). The intake merge `2b9ad3c` takes in `origin/master` at `d0d0d5b`. Between the t10 tip `a0f4d4a` and this tip, the contract's shipped files changed only through blocks 12 and 13. Every other shipped change in `a0f4d4a..2b9ad3c` came from master (Evidence).
- **Supersedes:** the blocked t10 report, `t10-review-fullstack-code-reviewer.md`. This report judges every item t10 judged.

**Verdict:** pass-with-findings

## What was checked

### Default-branch check and stop list

| # | Item | Outcome |
|---|---|---|
| D1 | The recorded `origin/master` commit `d0d0d5b` is an ancestor of the parent tip | met. `git merge-base --is-ancestor d0d0d5b HEAD` exits 0, and `git merge-base origin/master HEAD` before the fetch is `d0d0d5b`. The intake ran |
| D2 | Current `origin/master` tip after a fetch | `a5f7a83` (#395). `d0d0d5b..origin/master` holds `1d7955a` and its merge `a5f7a83`. Together they add one file, `.claude/orchestrator/results/2026-11-11-audit-followups-165/t13-keep-rule-for-an-unavailable-outcome.yaml`, which no block lists in Files to touch. Nothing joins the stop list |
| D3 | Formal stop list: commits in `d538e8a..origin/master` that touch a file in the Files to touch of blocks 1-13 | empty. I ran `git log` over all 29 listed paths and it printed nothing. This matches the intake record |
| D4 | Intake merge `2b9ad3c` reviewed with `git show --remerge-diff` | met. The remerge diff is empty, so the merge resolved nothing by hand and is exactly the automatic merge of `481db27` and `d0d0d5b` |
| D5 | The four manifests after the intake | met. `git diff origin/master HEAD -- <four manifests>` is empty (byte-identical, version 0.19.2). The manifests also moved over `d538e8a..HEAD`. Only master commits moved them: `git log --no-merges origin/master..HEAD -- <four manifests>` is empty |

Rating of each master commit that the intake brought in and that touches a shipped file, a pinned file, or a record. The rule is the block 14 severity rule.

| Commit | What it changes | Shipped or pinned? | Suites re-run | Rating |
|---|---|---|---|---|
| `e7f4355` (0.19.1, RED tests) | `test_protected_names.py`, `test_protected_names_warning.py` (block 5 Run list), `test_land_contract.py`, the four manifests (master's own raise), a work-item brief | yes. Tests ship, and the warning suite is in block 5's Run list | `test_protected_names_warning.py` 49 OK; `test_protected_names.py` 119 OK (2 platform skips) | **Note.** It also adds `test_8`-`test_10` of `TestContainmentScanner`, which made the scanner read `agents/` and `skills/`. See F7 |
| `8c8525c` (0.19.2, fixes) | `_protected_names.py`, `land_contract.py`, `skills/verify-before-done/SKILL.md` (read by the lookup pins), the four manifests, a work-item brief | yes | `test_skill_script_lookup.py` 35 OK; `test_protected_names_warning.py` 49 OK; `test_plugin_doctor.py` 224 OK | **Note.** No I-1..I-7 text moved. Its widened scanner, together with an unchanged line of `skills/ship/SKILL.md`, turns `test_land_contract.py` red on master and on this tip alike (F7). That suite is in no block's Run list, so under the rule this is not Breaking |
| `8c8c9e7` (t12 record) | one orchestrator results file | no | — | **Note.** State-store record only |
| `db9920f` (t10 record) | one orchestrator results file | no | — | **Note.** State-store record only |
| `547e187` (t9 record) | one orchestrator results file | no | — | **Note.** State-store record only |
| `1d7955a` (t13 record, after the intake, not yet in the parent) | one orchestrator results file | no | — | **Note.** The landing's default-branch merge takes it in. It conflicts with nothing |

The intake record says `8c8525c` touched `test_protected_names*.py` and `test_land_contract.py`. In fact `e7f4355` touched those three tests, and `8c8525c` touched the code they test. The rating is the same either way.

### t10's items, judged again on the tip

| # | Item | Outcome |
|---|---|---|
| C1 | Brief criterion 1: `/task` holds "Step 1.5" once; 5c runs no recipe it does not describe | met. `skills/task/SKILL.md` did not change after `a0f4d4a`. `test_flat_worktree.py` 26 OK |
| C2 | Brief criterion 2: `/flow` Step 2.7 body in `skills/flow/references/`, read-in-full rule, behaviour unchanged | met. Neither file changed after `a0f4d4a`. `test_parent_branch_rule_text.py` 44 OK, `test_compose_subissue_title.py` exit 0, `test_skill_script_lookup.py` 35 OK |
| C3 | Brief criterion 3: the template's Chat Tool Impact section names no consuming project's file or phase | met, and the whole template is now clean too (F1 fixed). `TestChatToolImpactSectionIsGeneric` and `TestTemplateNamesOnlyShippedAgents` green |
| C4 | Brief criterion 4: `/debug` routes only to shipped agents | met. `test_agent_skill_preloads.py` 11 OK |
| C5 | Brief criterion 5: README half plus the manifest follow-up stub | met. `ReadmeCountPinTests` green, and `.claude/concepts/followups/2026-11-11-manifest-description-counts.followup.md` is present |
| C6 | Brief criterion 6: `memory-pager.py` is silent when absent and logs a malformed file | met. `test_memory_pager.py` 4 OK |
| C7 | Brief criterion 7: the digest and INTEGRATION.md are read only when present | met. None of the six files changed after `a0f4d4a`. `test_plugin_text_scans.py` 53 OK |
| C8 | Brief criterion 8: finish-install Stage 1a asks before `--fix` | met. The Stage 1a text is unchanged. The run as a whole now keeps I-5 (C16) |
| C9 | Brief criterion 9: t16 I1, I2, I3 and t10 I6 corrected; the I3 assertion can fail | met. `FixAskPinTests.test_the_real_file_has_every_fix_line_covered` and `ProjectHistoryRecordTextTests.test_the_doctor_runs_in_report_mode_and_fix_waits_for_a_yes` are green. `ASK_WORD` was not widened (block 12's diff does not touch it) |
| C10 | Brief criterion 10: no test count in skill text | met. `TestSkillsStateNoTestCountForThePrMergedSuite` green after the F4 rename |
| C11 | Brief criterion 11: every new pin has a planted-wrong control shown to fail | met for blocks 1-9 (t10's probe; those files did not change). For blocks 12 and 13, see P1-P4 |
| C12 | I-1: README counts equal their oracles; three tree lines carry no number | met. `README.md` did not change after `a0f4d4a`. `test_repo_consistency.py` 31 OK |
| C13 | I-2: no block lists or touches a `check_version_bump.MANIFESTS` file | met. No Files to touch list names one. No non-master commit in the range touches one. `check_version_bump.py` in parent mode reports "sub-task pull request keeps version 0.19.2; the landing raises it" |
| C14 | I-3: the `/flow` move leaves behaviour unchanged | met (C2) |
| C15 | I-4: pager silent when absent, finds any rank, logs other failures, exits 0 | met (C6) |
| C16 | I-5: finish-install asks about `--fix` at most once per run, in all four runs | met. The Stage 2 `scaffold-missing` bullet (`SKILL.md:241-244`) now says Stage 2 asks nothing about `--fix` and names the run's one ask. Every other `--fix` line is in Stage 1a (107-117), the history record check (452-459) or Anti-patterns (506). In run (a) the history check alone asks. In (b) the basis does not appear. In (c) and (d) Stage 2 asks nothing. The bullet promises no re-preview this run |
| C17 | I-6: the three I-M0 disabled tests are not edited | met. Block 13's diff of `test_memory_boundary.py` touches only the round trip and the unavailable tests (#394 names every test it changed) |
| C18 | I-7: the template keeps `## Chat Tool Impact` and the three answers | met. Heading at `concept-contract.md:216`, answers at 222, 230 and 232. Block 12 changed only lines 12 and 455 |
| C19 | Re-run every named suite, `test_skill_script_lookup.py`, `test_check_version_bump.py`, and the doctor with the root set (zero skips) | met. Every suite is green. The doctor ran 224 tests, OK, with no skip (Evidence) |
| C20 | Data Shapes keep rule (Memory used section) | met. `cmd_record` (`memory_boundary.py:791-794`) keeps the earlier `Retrieved:` and `Reported:` lines for any enabled-branch outcome with empty lists, `unavailable` included. The `unconfigured` branch (770-775) keeps them too. An outcome that carries items replaces them. That is the Revision 4 text exactly |
| C21 | Reused mechanisms: imports, not copies | met. Block 12's `TestTemplateNamesOnlyShippedAgents` imports `TestTheRealPluginTree.NOT_SHIPPED` and uses `plugin_agent_names()`. The Protocol-line pin imports `pr_merged.DEFAULT_IMPLEMENTERS`. The Stage 2 pin reuses `section()` and `fix_lines_without_ask` |
| C22 | Superseded stubs and the brief's `contract:` field | met (unchanged since t10). The F5/F6 stub `.claude/concepts/followups/2026-11-12-t10-review-nits-f5-f6.followup.md` exists |
| C23 | Off-area drift | met. `.claude/area-mapping.json` has no areas. Every shipped file that blocks 12 and 13 changed is in their Files to touch (#392 and #394 file lists). The other shipped changes in the range are master's |

### t10's findings

| # | t10 finding | Outcome |
|---|---|---|
| F1 | The template names `ingestion-data-architect` (lines 12, 455) | fixed by block 12. Line 12 lists exactly `pr_merged.DEFAULT_IMPLEMENTERS`, and line 455 reads "### 3. Data pipeline (`dotnet-backend-architect`, or the project's own ingestion agent if it declares one)". The doctor guard is green with the root set and zero skips |
| F2 | Stage 2 `scaffold-missing` bullet adds a second `--fix` ask | fixed by block 12. The bullet is reworded, and `ASK_WORD` and `fix_lines_without_ask` are unchanged. A new Stage 2 pin guards it |
| F3 | `unavailable` sits outside the keep rule | answered (Q8: yes) and done by block 13. The exclusion is removed, the block-7 test was renamed and inverted, the round trip gains an unavailable step, and a carries-items pin was added. `central-memory.md` section 6 states the rule in one sentence (line 89). Line 43 is untouched |
| F4 | `test_count_claims` helper has a `test_` name | fixed by block 12 (`count_claims_in`, with its callers) |
| F5, F6 | `/task` two names for one path; repeated import setup | known nits, not new findings. Tracked in `.claude/concepts/followups/2026-11-12-t10-review-nits-f5-f6.followup.md`. F5 is still present (`skills/task/SKILL.md:456` against `:467,482`), as Q9 decided |

### New pins of blocks 12 and 13

| # | Pin | Outcome |
|---|---|---|
| P1 | Block 12 F1 pin (`TestTemplateNamesOnlyShippedAgents`): runs without `AGENTIC_PLUGIN_ROOT`; the control fails on its fixture | met. The control asserts that the helper flags a planted `` `ingestion-data-architect` `` line, a planted heading with that name, and a made-up `` `frob-reviewer` `` heading, and does not flag a shipped one. My probe applied the helper to the `efab7e0` template and got `['ingestion-data-architect', 'ingestion-data-architect']`. On the tip it returns `[]`. The Protocol-line pin compares against `DEFAULT_IMPLEMENTERS` in order |
| P2 | Block 12 F2 pin (`Stage2FixIsNeverAskedTests`): the three controls fail (master's bullet, "ask the user whether", the conditional ask), and the reworded bullet passes | met. My probe found one violation for each of the three controls. The conditional control is caught on "ask once". The reworded bullet gives `[]`. A fourth control, a re-preview promise in its own sentence, also fails. On `efab7e0` the real file gives 1 violation. On the tip it gives 0 |
| P3 | Block 13 pins: unavailable with empty lists keeps earlier lines in order, then receipts; the round trip gets an unavailable step; carries-items replaces | met. #394 records the red run before the fix (120 tests, 2 failures). By reading the code: under the removed `!= "unavailable"` condition, `carried` stays empty and the earlier lines drop, so both keep assertions would fail. The carries-items pin states existing behaviour and passed before the fix, as the contract says |
| P4 | Block 12's red runs before the fix | met. #392 records `test_memory_off_parity.py` red (3 failures) and `test_plugin_text_scans.py` red (2 failures) before the fix. My `efab7e0` probe agrees |

## Findings

**F7 — warning — `skills/ship/SKILL.md:358` against master's widened containment scanner (`e7f4355` test, `8c8525c` scanner), owned by master, not by this contract.** `test_land_contract.py::TestContainmentScanner::test_the_real_tree_holds_no_merge_outside_land_contract` fails on this tip with `[('skills/ship/SKILL.md', 'gh-pr-merge')]`. Line 358 is prose: "routes on `api.github.com` named in the 403 text instead of `gh pr ready` / `gh pr merge --auto`". The 0.19.2 scanner now reads `skills/`, and it counts this prose mention as a merge command. `skills/ship/SKILL.md`, `land_contract.py` and `test_land_contract.py` are byte-identical to `origin/master` (`git diff origin/master HEAD` on the three is empty). No commit of this contract touches `skills/ship/SKILL.md` (`git log origin/master..HEAD -- skills/ship/SKILL.md` is empty; the file last changed on master in `6abbcc0`, 0.9.17). So master is red in the same way, and master itself has no `.claude/test-baseline.json` to record it. Under the severity rule this is not Breaking: the commit changes a shipped file, but none of the suites block 14 re-runs goes red, and I-1..I-7 hold. It is a defect the landing will carry in unchanged, and CI does not run that suite (`version-bump.yml` runs only `test_check_version_bump.py` and `test_repo_consistency.py`). Fix it on master in contract 623's line of work, not here: reword line 358 so it does not spell the merge command, or have the scanner skip prose. A file under `.claude/concepts/followups/` or an issue against 623 should carry it.

**F8 — nit — `.claude/scripts/tests/test_memory_off_parity.py`, `FIX_ASK_FORBIDDEN`.** The Stage 2 pin forbids the words "offer", "ask the user / once / whether / if", "preview again" and "run the preview". A bullet sentence that asks with another verb, and does not name `--fix`, passes. My probe planted "Prompt the user to create it now, then continue." and "Suggest running the doctor's fix now and wait for the answer." Both returned `[]`. The real text is correct today, so this is a gap in the guard, not a defect. Widening the list, with a control for each new word, would close it. Mind that the real bullet's "proposes its content" must still pass.

## What was NOT checked

- The `/flow` reference read through a plugin-cache install (Failure Mode 2). No installed cache carries this change. Not checked, as in t10.
- The full `unittest discover` of `.claude/scripts/tests/` and `.claude/hooks/tests/` beyond the named suites. Two unnamed suites were run, because the intake brought their files in: `test_protected_names.py` and `test_land_contract.py`.
- The cross-area script (`cross_area_scan.py`): not run, because the area map is empty (contract `ASSUMED`).
- Block 13's red run, repeated by me. I relied on #394's record, plus a reading of the removed condition.
- Why `test_one_subtask_contract_no_issue_needs_issue_false` failed once when it ran alongside other suites (Evidence). It is green alone and in its class, and the code is master's, unchanged by this contract. I did not find the root cause.
- Whether master's owner already tracks F7. I found no baseline file, but I did not search the issue tracker.

## Evidence

Every suite was run from the worktree root on `2b9ad3c` with `py -3 -B <suite>`, with `AGENTIC_PLUGIN_ROOT` set to the worktree root (runner `C:\Temp\t14-165\run_suites.py`).

| Command | Exit | Result |
|---|---|---|
| `git merge-base --is-ancestor d0d0d5b1e08042828dbac28a0515a2c718f6c4e7 HEAD` | 0 | ancestor (D1) |
| `git fetch origin`; `git rev-parse origin/master` | 0 | `a5f7a83589803631e6a984988098effc2f76b2d3` |
| `git log --oneline d0d0d5b..origin/master` | 0 | `a5f7a83`, `1d7955a`. `git show --stat` shows one results `.yaml` (D2) |
| `git log --oneline d538e8a..origin/master -- <the 29 Files to touch paths of blocks 1-13>` | 0 | empty (D3) |
| `git show --remerge-diff --format= 2b9ad3c \| wc -l` | 0 | `0` (D4) |
| `git diff --stat origin/master HEAD -- plugin.json .claude-plugin/plugin.json .cursor-plugin/plugin.json .claude-plugin/marketplace.json` | 0 | empty (D5) |
| `git log --oneline --no-merges origin/master..HEAD -- <the four manifests>` | 0 | empty (C13) |
| `git show --stat 8c8525c e7f4355 8c8c9e7 db9920f 547e187` | 0 | file lists as rated above |
| `git diff --stat a0f4d4a HEAD` | 0 | 30 files. The contract's shipped changes are only block 12's and block 13's. The rest are master's 0.19.1/0.19.2, records and briefs |
| `git diff efab7e0 894d999 -- <block 12 files>`; `git diff 894d999 481db27 -- <block 13 files>` | 0 | read in full (C16, C20, P1-P3) |
| `py -3 .claude/scripts/check_version_bump.py --base origin/feature/165-audit-followups --head-ref task/2026-11-11-audit-followups-165/t14-re-review --default-branch master` | 0 | "sub-task pull request keeps version 0.19.2; the landing raises it" |
| `py -3 -B .claude/scripts/tests/test_flat_worktree.py` | 0 | Ran 26 tests, OK |
| `py -3 -B .claude/scripts/tests/test_parent_branch_rule_text.py` | 0 | Ran 44 tests, OK |
| `py -3 -B .claude/scripts/tests/test_ship_skill_sync.py` | 0 | 104 passed, 0 failed |
| `py -3 -B .claude/scripts/tests/test_memory_off_parity.py` | 0 | Ran 54 tests, OK |
| `py -3 -B .claude/scripts/tests/test_compose_subissue_title.py` | 0 | exit 0 (custom runner; no failure line) |
| `py -3 -B .claude/scripts/tests/test_plugin_text_scans.py` | 0 | Ran 53 tests, OK |
| `AGENTIC_PLUGIN_ROOT=<worktree> py -3 -B .claude/scripts/tests/test_plugin_doctor.py` | 0 | Ran 224 tests, OK. No skip; the summary line is a bare `OK` |
| `py -3 -B .claude/scripts/tests/test_agent_skill_preloads.py` | 0 | Ran 11 tests, OK |
| `py -3 -B .claude/scripts/tests/test_memory_boundary.py` | 0 | Ran 120 tests, OK |
| `py -3 -B .claude/scripts/tests/test_repo_consistency.py` | 0 | Ran 31 tests, OK |
| `py -3 -B .claude/scripts/tests/test_check_version_bump.py` | 0 | Ran 53 tests, OK |
| `py -3 -B .claude/scripts/tests/test_skill_script_lookup.py` | 0 | Ran 35 tests, OK (250 s) |
| `py -3 -B .claude/scripts/tests/test_pr_merged.py` (run alone) | 0 | Ran 761 tests, OK (997 s) |
| the same suite, first run, concurrent with `test_land_contract.py` and the other suites | 1 | Ran 761 tests, FAILED (failures=1): `TestNeedsIssueAtTheReportCallSite.test_one_subtask_contract_no_issue_needs_issue_false`, "fixture sanity: 't1-backend' must appear in report['dispatch'] -- got None". `py -3 -B -m unittest test_pr_merged.TestNeedsIssueAtTheReportCallSite` then ran 3 tests, OK, both with and without `AGENTIC_PLUGIN_ROOT`, and the solo full run above is green. `pr_merged.py` and `test_pr_merged.py` are byte-identical to `origin/master` |
| `py -3 -B .claude/hooks/tests/test_memory_pager.py` | 0 | Ran 4 tests, OK |
| `py -3 -B .claude/hooks/tests/test_memory_common.py` | 0 | 26 passed, 0 failed |
| `py -3 -B .claude/hooks/tests/test_protected_names_warning.py` | 0 | Ran 49 tests, OK |
| `py -3 -B .claude/hooks/tests/test_hook_data_files_project_first.py` | 0 | 29 passed, 0 failed |
| `py -3 -B -m unittest -v test_protected_names` (from `.claude/hooks/tests`) | 0 | Ran 119 tests, OK (skipped=2). Both skips depend on the platform and are expected. `test_R5_B3_4_…case_variant…` is skipped because "this file system folds letter case within a folder", which is the default on NTFS. `test_R5_B2_10_…longer_than_260_characters…` is skipped because the fixture cannot be created ("WinError 267"), as long paths are not enabled |
| `py -3 -B -m unittest -v test_land_contract.TestContainmentScanner` (from `.claude/scripts/tests`) | 1 | Ran 19 tests, FAILED (failures=1): `test_the_real_tree_holds_no_merge_outside_land_contract`, `[('skills/ship/SKILL.md', 'gh-pr-merge')]` (F7) |
| `py -3 -B -m unittest -v test_land_contract` (from `.claude/scripts/tests`) | 1 | Ran 360 tests, FAILED (failures=1, skipped=1). The one failure is F7's. The skip is `TestNoProjectTokens.test_land_contract_and_its_tests_carry_no_project_token`, "the token list in .project-tokens.json is empty (the plugin template), so the scan has nothing to match". That skip is expected in the plugin's own repository |
| `git diff --stat origin/master HEAD -- skills/ship/SKILL.md .claude/scripts/land_contract.py .claude/scripts/tests/test_land_contract.py` | 0 | empty: byte-identical to master (F7) |
| `git log --oneline origin/master..HEAD -- skills/ship/SKILL.md` | 0 | empty: no block touched it (F7) |
| `git cat-file -e origin/master:.claude/test-baseline.json` | 128 | master holds no failing-test baseline (F7) |
| Probe `C:\Temp\t14-165\pins_on_old_tree.py` (block 12 helpers on `efab7e0`, `HEAD` and `origin/master`, plus the controls) | 0 | `efab7e0`: 1 Stage 2 violation, 1 uncovered `--fix` line, 2 unshipped template names. `HEAD`: 0, 0, `[]`. Controls: master's bullet, ask-whether and the conditional each give one violation, and the reworded bullet gives `[]`. The synonym plants "Prompt the user …" and "Suggest running …" give `[]` (F8) |
| `gh pr view 392` / `gh pr view 394 --json body,baseRefName,files` | 0 | both based on `feature/165-audit-followups`. File lists match blocks 12 and 13 plus each one's own brief. The red-before-green runs are recorded (P3, P4) |
| Files read: the contract (Revision 4); the t14 brief; the t10 report and gate file; `memory_boundary.py:745-804`; `test_land_contract.py:1594-1698`; `skills/auto-improve-finish-install/SKILL.md` `--fix` lines; template lines 216-232, 371-406 | — | as cited |

## Disposition

Nothing. This gate releases its dependents. The Gate Output lists the blocked t10 report in `supersedes`, so the landing's P3 check reads this report in its place. Before or at the landing:

1. F7 belongs to master. Open a follow-up for contract 623's line of work: the containment scanner flags the prose at `skills/ship/SKILL.md:358`. The landing takes this red in unchanged, and nothing in this contract should edit `skills/ship/SKILL.md` to hide it.
2. F8 is optional hardening of block 12's Stage 2 pin. It can join the F5/F6 follow-up stub.
3. The landing's default-branch merge takes in `1d7955a`/`a5f7a83`, a results record only.
