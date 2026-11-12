# Review: audit follow-ups 165, blocks 1-9 (t10)

- **Gate agent:** `fullstack-code-reviewer`
- **Sub-task:** t10-review
- **Contract:** `.claude/concepts/2026-11-11-audit-followups-165.md`
- **Reviewed on:** 2026-11-12
- **Commit range reviewed:** `d538e8a..a0f4d4a` (merge base with `origin/master` .. tip of `feature/165-audit-followups`, which is also this branch's HEAD). Blocks 1-9 merged as #365, #367, #369, #371, #374, #377, #379, #381, #383. The two merges `212e3ce` and `189894d` bring in `origin/master` up to `d538e8a`.

**Verdict:** blocked

## What was checked

| # | Item | Outcome |
|---|---|---|
| C1 | Brief criterion 1: `/task` holds "Step 1.5: Enter a worktree" once, and 5c no longer describes a recipe it does not run | met. One heading; no `git worktree add` command line in 5c; base proof, gitignore check, VS Code window and lifecycle kept |
| C2 | Brief criterion 2: `/flow` Step 2.7 body lives in `skills/flow/references/`, with the read-in-full rule; behaviour unchanged; existing pins pass | met. A line-by-line comparison finds all 127 removed non-blank lines in `open-sub-tasks.md`. The only difference is the point-3 heading line, which stays in SKILL.md. The reference adds a title and a two-line preamble |
| C3 | Brief criterion 3: the template's "Chat Tool Impact" section names no consuming project's file or phase | met for the section. The rest of the same template still names an unshipped agent (F1) |
| C4 | Brief criterion 4: `/debug` routes only to shipped agents or to a generic project agent | met |
| C5 | Brief criterion 5, judged as the README half plus the follow-up stub | met. The README tree and provider table match their oracles and are pinned. `.claude/concepts/followups/2026-11-11-manifest-description-counts.followup.md` exists (issue #354) and names both the four description strings and applying the count helper to the real manifests (the drift test) |
| C6 | Brief criterion 6: `memory-pager.py` logs nothing when no rank holds `memory-blocks.json`, and still logs a malformed file | met |
| C7 | Brief criterion 7: data-architect reads the digest and INTEGRATION.md only when present | met. All V8 read lines in the six files are covered. `design-first/SKILL.md:220` and `registry-scout.md:3` are a story and a description, not reads |
| C8 | Brief criterion 8: finish-install Stage 1a asks before `--fix` | met in Stage 1a. On the tip, the run as a whole breaks I-5 (F2) |
| C9 | Brief criterion 9: t16 I1, I2, I3 and t10 I6 corrected; the I3 assertion can fail | partly-met. The text changes and the controls are in place. On the tip, the I3 real assertion fails (F2) |
| C10 | Brief criterion 10: the skill text points at `test_pr_merged.py` with no count | met |
| C11 | Brief criterion 11: every new pin has a planted-wrong control shown to fail | met. Every control test passes, and each control asserts that its rule fires on its planted fixture. I also applied each new real assertion's helper to the merge-base text: every one fails there except the provider-table pin, whose rows were already correct. The pager suite run against the old hook fails exactly its absent-row test |
| C12 | I-1: README counts equal their oracles; three tree lines carry no number | met (`ReadmeCountPinTests`, 9 tests green) |
| C13 | I-2: no block lists or touches a `check_version_bump.MANIFESTS` file | met. No manifest differs over the range. `212e3ce` is the only commit under `origin/master..HEAD` that touches one, and its manifests are byte-identical to `d538e8a` (master's own 0.19.0 raise, brought in by the merge) |
| C14 | I-3: the `/flow` move leaves behaviour unchanged | met (see C2). The guard, status call, `defects` stop and `<= 1` stop stay in SKILL.md |
| C15 | I-4: pager is silent when absent, finds a file at any rank, logs other failures, exits 0 | met. Only `FileNotFoundError` is caught. A folder in the file's place raises a different error and still logs, and the four-rank decoy rows pass |
| C16 | I-5: finish-install asks about `--fix` at most once per run, in all four runs | not-met on the tip (F2) |
| C17 | I-6: the three I-M0 disabled tests in `test_memory_boundary.py` are not edited | met. The diff of that file adds lines and removes none |
| C18 | I-7: the template keeps `## Chat Tool Impact` and the three answers | met |
| C19 | Re-run every suite named in blocks 1-9, plus `test_skill_script_lookup.py`, `test_check_version_bump.py` and `test_plugin_doctor.py` with `AGENTIC_PLUGIN_ROOT` set (zero skips) | not-met. Two suites are red (F1, F2). The doctor ran with zero skips and one failure. Every other suite is green (Evidence) |
| C20 | Data Shapes keep rule (Memory used section) | partly-met. The `unconfigured` and enabled-empty cases are implemented and round-trip tested. The `unavailable` case is pinned the other way (F3) |
| C21 | Reused mechanisms: block 4 imports `plugin_agent_names()` and `NOT_SHIPPED` instead of copying them; the pager keeps the resolver | met |
| C22 | Superseded stubs and the brief's `contract:` field (Extension Points) | met. The three stubs are renamed `.followup.superseded.md`, each with a `Superseded by:` line, and the parent brief's `contract:` is set |
| C23 | Off-area drift | met. `.claude/area-mapping.json` has no areas, and every changed shipped file is in some block's Files to touch |

## Findings

**F1 — blocker — `.claude/templates/concept-contract.md:12` and `:455`.** `TestTheRealPluginTree.test_the_files_a_project_copies_carry_no_unshipped_name` fails on the tip. It is the V19 guard, and the contract's Failure Modes rely on it to stop a leaked name from shipping. The template, which every consuming project copies, still names `ingestion-data-architect`: in the Protocol line's list of implementer agents, and in the `### 3. Data pipeline (\`ingestion-data-architect\`)` handoff example. Blocks 3, 4 and 7 each found this failure, said it was outside their files and passed it on (#369 notes; #371 Notes; #379 counted it as a skip). No block owns it, though block 3's Files to touch lists the template. Fix: in both places, name a shipped agent or "the project's own ingestion agent, if it declares one", and re-run the doctor suite with the root set. The fix belongs in a fix pull request against block 3's file.

**F2 — blocker — `skills/auto-improve-finish-install/SKILL.md:241-242` against block 7's I3 pin and I-5.** Master's #373 (`7c0afde`, feature 21, finish-install step-3 proposals) added a Stage 2 bullet: "`scaffold-missing` … Offer to run `plugin_doctor.py --fix` …, then run the preview again". The parent-branch merges `212e3ce`/`189894d` combined that bullet with block 7's whole-file I3 pin. The pin's ask words do not include "Offer", so `FixAskPinTests.test_the_real_file_has_every_fix_line_covered` and `ProjectHistoryRecordTextTests.test_the_doctor_runs_in_report_mode_and_fix_waits_for_a_yes` fail. The pin is also right on the substance. Stage 2 runs between Stage 1a and the history-record check, so this offer is a second `--fix` ask in run (a): the profile exists and Stage 1a is skipped, so this ask comes on top of the history check's ask. It is also a re-ask after a no in run (c). Both break I-5. Fix: reword the bullet to follow I-5, for example "if this run has not yet asked about `--fix`, ask once …; otherwise name the command to run later". Do not just add "offer" to `ASK_WORD`. Then re-run `test_memory_off_parity.py`. CI's `tests` job runs only `test_check_version_bump.py` and `test_repo_consistency.py`, so CI would not catch F1 or F2 at the landing.

**F3 — warning — `.claude/scripts/memory_boundary.py` (`cmd_record`, enabled branch) and `test_memory_boundary.py::test_an_unavailable_outcome_does_not_keep_earlier_items`.** The Data Shapes keep rule reads: "when the new outcome carries no retrieved item and no reported entry (an `unconfigured` profile, or an `enabled` empty retrieval)". An `unavailable` outcome also carries neither, but the code excludes it (`outcome.get("state") != "unavailable"`), and a new test pins that a re-run whose memory call timed out deletes the brief's earlier `Retrieved:` lines. That is the loss critic WARN 7 was raised to prevent. Either the parenthetical is a closed list and the drop is intended (then say so in the contract's Data Shapes), or the keep rule should cover `unavailable` too. This is a question for the owner and does not block. No pull request records a reason for the exclusion.

**F4 — nit — `.claude/scripts/tests/test_plugin_text_scans.py`, module-level `def test_count_claims(text)`.** It is a helper with a `test_` name. The `unittest` runner ignores it, but a pytest run would collect it and error on the missing `text` fixture. Rename it to `count_claims_in`.

**F5 — nit — `skills/task/SKILL.md:467,482`.** The base proof now says `<plan path>`, but the VS Code paragraph still writes `.claude/worktrees/<wt>`. The location is the same, but there are now two names for one path.

**F6 — nit — `.claude/scripts/tests/test_agent_skill_preloads.py`.** The two new tests repeat the same `sys.path` setup and import lines. A `setUpClass` would hold them once.

## What was NOT checked

- The `/flow` reference read through a plugin-cache install (FM 2). Every cached install here is at most 0.16.5, older than this change. As indirect evidence, the 0.16.5 cache does ship same-skill `references/` folders for `task` and `pr-merged`. Not checked.
- Block 7's round-trip test against the old `memory_boundary.py`. I relied on #379's statement ("1 in the boundary file" failed before the change). The test does fail on its own logic, which I read.
- The full `unittest discover` of `.claude/scripts/tests/` and `.claude/hooks/tests/` beyond the named suites.
- The cross-area script (`cross_area_scan.py`): not run, because the area map is empty (contract `ASSUMED`).
- Whether the main session's merges `212e3ce`/`189894d` were reviewed. Their only effect found here is F2.

## Evidence

Every suite was run from the worktree root on `a0f4d4a` with `py -3 -B <suite> -v`, with `AGENTIC_PLUGIN_ROOT` set to the worktree root.

| Command | Exit | Result |
|---|---|---|
| `py -3 -B .claude/scripts/tests/test_flat_worktree.py` | 0 | Ran 26 tests, OK |
| `py -3 -B .claude/scripts/tests/test_parent_branch_rule_text.py` | 0 | Ran 44 tests, OK |
| `py -3 -B .claude/scripts/tests/test_ship_skill_sync.py` | 0 | 104 passed, 0 failed |
| `py -3 -B .claude/scripts/tests/test_memory_off_parity.py` | 1 | Ran 48 tests, FAILED (failures=2): `FixAskPinTests.test_the_real_file_has_every_fix_line_covered`, `ProjectHistoryRecordTextTests.test_the_doctor_runs_in_report_mode_and_fix_waits_for_a_yes`. Both report `'command never creates it. Offer to run\n  \`plugin_doctor.py --fix'` (F2) |
| `py -3 -B .claude/scripts/tests/test_compose_subissue_title.py` | 0 | all checks passed |
| `py -3 -B .claude/scripts/tests/test_skill_script_lookup.py` | 0 | Ran 35 tests, OK (276 s) |
| `py -3 -B .claude/scripts/tests/test_pr_merged.py` | 0 | Ran 761 tests, OK (1223 s). A first background run through the batch runner exited with code 4 and wrote no result line, so this result comes from a direct foreground re-run |
| `py -3 -B .claude/scripts/tests/test_plugin_text_scans.py` | 0 | Ran 50 tests, OK |
| `AGENTIC_PLUGIN_ROOT=<worktree> py -3 -B .claude/scripts/tests/test_plugin_doctor.py` | 1 | Ran 224 tests, FAILED (failures=1), no skips: `test_the_files_a_project_copies_carry_no_unshipped_name`, `'ingestion-data-architect' unexpectedly found` in `concept-contract.md` (F1) |
| `py -3 -B .claude/scripts/tests/test_agent_skill_preloads.py` | 0 | Ran 11 tests, OK |
| `py -3 -B .claude/hooks/tests/test_memory_pager.py` | 0 | Ran 4 tests, OK |
| `py -3 -B .claude/hooks/tests/test_memory_common.py` | 0 | 26 passed, 0 failed |
| `py -3 -B .claude/hooks/tests/test_protected_names_warning.py` | 0 | Ran 41 tests, OK |
| `py -3 -B .claude/hooks/tests/test_hook_data_files_project_first.py` | 0 | 29 passed, 0 failed |
| `py -3 -B .claude/scripts/tests/test_memory_boundary.py` | 0 | Ran 119 tests, OK |
| `py -3 -B .claude/scripts/tests/test_repo_consistency.py` | 0 | Ran 31 tests, OK |
| `py -3 -B .claude/scripts/tests/test_check_version_bump.py` | 0 | Ran 53 tests, OK |
| `py -3 .claude/scripts/check_version_bump.py --base origin/feature/165-audit-followups --head-ref task/2026-11-11-audit-followups-165/t10-review --default-branch master` | 0 | "sub-task pull request keeps version 0.19.0; the landing raises it" |
| `git diff --name-only d538e8a a0f4d4a -- plugin.json .claude-plugin/plugin.json .cursor-plugin/plugin.json .claude-plugin/marketplace.json` | 0 | empty (I-2) |
| `git log --oneline origin/master..HEAD -- <the four manifests>` | 0 | `212e3ce` only; `git diff --stat d538e8a 212e3ce -- <the four manifests>` is empty, so the merge took master's files unchanged |
| `git branch -r --contains 65ed3e9` | 0 | only `origin/feature/165-audit-followups` and this branch, so no block reached `master` |
| `git show origin/master:skills/auto-improve-finish-install/SKILL.md` (lines 221-222) and `git log -- <that file>` | 0 | the `scaffold-missing … Offer to run plugin_doctor.py --fix` bullet comes from master's `7c0afde` (F2) |
| Probe `C:\Temp\t10-165\verbatim_flow.py`: removed Step 2.7 body vs `open-sub-tasks.md` | 0 | 127 removed lines, 1 not in the reference (the point-3 heading kept in SKILL.md), 3 reference-only lines (title, preamble) |
| Probe `C:\Temp\t10-165\pins_on_old_tree.py`: each new pin's helper on the `d538e8a` text, and the pager suite on the old hook | 0 | b1 (two headings; two `git worktree add` lines), b2 (no reference; `verify_parent_link.py` in Step 2.7), b3 (rules 1-7 fire: `ChatToolDefinitions.cs`, `Phase A2`, `5d9acc15`, `llm-training-engineer` …), b4 (`ingestion-data-architect`, `llm-training-engineer`), b7 (bare 1a `--fix`; I1 bare example), b8 (`760 cases`/`760 tests` in both skills), b9 (`6 generic data files`) all FAIL before and pass now, except b7's whole-file pin, which still fails now (F2). Provider-table pin passes before and now. Pager on the old hook: only `test_absent_at_all_four_ranks_logs_nothing` fails |
| `gh pr view 369 / 371 / 379 --json body` | 0 | each records the doctor unshipped-name failure or skip as outside its files (F1) |
| Files read: the contract; the parent and t10 briefs; the manifest follow-up stub; `git diff d538e8a a0f4d4a` for every shipped file of blocks 1-9; `_memory_common.load_config`; the I3 helper `fix_lines_without_ask` | — | as cited in the findings |

## Disposition

This gate releases nothing. Before the contract continues:

1. Fix F1 in `.claude/templates/concept-contract.md` (lines 12 and 455) so `test_plugin_doctor.py` passes with `AGENTIC_PLUGIN_ROOT` set and zero skips.
2. Fix F2 in `skills/auto-improve-finish-install/SKILL.md` (the Stage 2 `scaffold-missing` bullet) so it follows I-5's one ask, and so `test_memory_off_parity.py` passes without weakening `ASK_WORD`.
3. Answer F3 as the owner: keep the `unavailable` exclusion and amend Data Shapes, or extend the keep rule.
4. Re-run this gate on a new pull request after 1 and 2 merge into `feature/165-audit-followups`. The re-run's Gate Output lists this file in `supersedes`.
