# t18 review — fullstack-code-reviewer

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t18-review (issue #328, parent issue #235)
- **Contract:** `.claude/concepts/2026-11-04-domain-split-registries.md` (approved, amendment 10)
- **Reviewed on:** 2026-11-09
- **Commit range reviewed:** `a4f7c65..5960ebc` (parent branch `fix/235-domain-split-registries`). `a4f7c65` is the parent tip t17 was cut from (it holds amendment 10 and the t17 and t18 briefs). `5960ebc` is the merge of pull request #329 (t17).
- **First-parent commits in the range:** **t17 `5960ebc` (#329)**, parents `a4f7c65` and `34a95f9`. There is no other first-parent commit.
- **The t17 branch inside #329:** code and tests `58271ee` → MECHANISMS.md Correction line `6f8dce9` → journal lesson `c980ded` → brief bookkeeping `34a95f9`. None of them is a merge.
- **Effective earlier report:** `t16-review-fullstack-code-reviewer.md` stays in force. This report does not replace it, and its W1 (Q27) is still open.

**Verdict:** pass-with-findings

## What was checked

Each item is on one line. The outcome comes first, then the evidence.

- **RED proof in #329.** Met, with N2. The PR shows the RED run (exit 1, `FAILED (failures=3)`) and the refusal text "cannot import the module '_preview_apply'" for the three tests. It then shows the tests-first run (`FAILED (failures=4)`, the fourth being the pin test). Both are excerpts cut with "...", not full raw output, and the RED block does not print the three test names.
- **`VENDORED_FILES` is exactly the seven names, in block 17's order.** Met. At `5960ebc`: `check_hook_registrations.py`, `auto_improve_finish_install.py`, `pr_merged.py`, `plugin_doctor.py`, `check_version_bump.py`, `_preview_apply.py`, `_plugin_root.py`. The pin test asserts that tuple.
- **The refusal message and remedy take the count from `len(VENDORED_FILES)`.** Met. `check_hook_registrations.py:515-518` use `%d` with `len(VENDORED_FILES)` in both strings. `git grep -n -w five` finds two hits: `:10` "The five Registration rules" and `:455` "Evaluate all five rules". Both count rules, not files.
- **The tests read `chk.VENDORED_FILES`.** Met. `FIVE_FILES` is gone (exit 1, no output). `VENDORED_FILES = chk.VENDORED_FILES` sits after the import. The pin test `test_the_vendored_file_list_is_exactly_the_seven_files_in_order` (`:710`) exists, and so does the renamed `test_dependency_import_failure_is_exit_2_naming_every_vendored_file` (`:700`). The old name is absent.
- **`VENDORED_FILES` readers.** Partly met (N1). The search prints four files, not the three block 18 expects: the checker (4), its test (6), MECHANISMS.md (1) and **JOURNAL.md (2)**. The extra file is the lesson block 17 had to append verbatim, which names `VENDORED_FILES` in its Lesson and Apply-when lines. The code is right and the contract mis-predicted. t17 reported this in #329.
- **The old count survives only where I-7 keeps it.** Met. The narrow pattern prints exactly `.claude/registries/MECHANISMS.md:1` (exit 0). That is line 112, the original "Hook registration check" entry, which is byte-equal to its `a4f7c65` copy.
- **My own closure check.** Met. Module-level imports outside the standard library, read from the top of each file:
  - `check_hook_registrations.py:53` (inside the guarded try): `auto_improve_finish_install`.
  - `auto_improve_finish_install.py:115-120`: `pr_merged`, `plugin_doctor`, `_preview_apply`, `_plugin_root`.
  - `pr_merged.py:44`: `check_version_bump`.
  - `plugin_doctor.py:25-37`, `check_version_bump.py:16-23`, `_preview_apply.py:12-18` and `_plugin_root.py:15-21`: standard library only.
  - Every one of them is in `VENDORED_FILES`, so the closure is the seven files.
  - Lazy imports: the check calls `_iter_hooks`, `_hook_key` and `_compare_extras`. `_hook_key` (`:989-1004`) calls `_launcher_api()`, which runs `import _claude_paths` (`:140`) and returns `None` on `ImportError` or `SystemExit`. So that lazy import is reachable on the check's path. It fails soft in a seven-file copy. See N4. The other lazy imports (`plugin_doctor.py:168, 208, 485`, `_plugin_root.py:87`, the many in `pr_merged.py`) are not reachable from those three functions.
- **README step 2.** Met. It says "Vendor seven files", lists the seven names in `VENDORED_FILES` order, and says "The checker imports the other six". `git diff a4f7c65 5960ebc -- README.md` has one hunk (4 insertions, 3 deletions), all inside step 2.
- **MECHANISMS.md.** Met. `6f8dce9` (one parent, `58271ee`) touches only MECHANISMS.md, with 1 insertion. The new line 113 sits directly under the entry's line 112. It is byte-equal to `"  - **Correction (2026-11-09, issue #235, amendment 10):** "` plus block 17's quoted text. `git log -S` names only `6f8dce9`. #329 pastes the `registry_append` result `.claude/registries/MECHANISMS.md:113`.
- **JOURNAL.md (Q28).** Met. The count prints `.claude/registries/JOURNAL.md:1` (exit 0). My script took the six-line quoted block from the end of the "Amendment 10 record" (with its two-space indent removed). It sits at JOURNAL.md lines 550-555 line for line, above `## Project tier` (line 557). `git log -S` names only `c980ded` (one parent, `6f8dce9`), which touches only JOURNAL.md (+7: the six lines and a blank line).
- **The defect is this contract's, not master's.** Met. `git cat-file -e origin/master:.claude/scripts/_preview_apply.py` exits 128 ("exists on disk, but not in 'origin/master'"), and so does `_plugin_root.py`. `git grep -n -F "_preview_apply" origin/master -- .claude/scripts/auto_improve_finish_install.py` exits 1. Master's finish-install imports only `pr_merged` and `plugin_doctor` from the scripts folder.
- **No version file edited by hand.** Met. `git log --no-merges a4f7c65..5960ebc -- plugin.json .claude-plugin .cursor-plugin` is empty, and so is the diff over the range.
- **origin/master's version.** `git show origin/master:plugin.json` shows `"version": "0.16.5"`, the same as the parent tip.
- **The older-test search outputs (four questions) are in #329.** Met, with N2. Questions 1, 2, 3, 4 and 5 each have a command and a result. Question 5 names six files, and t17 ran only two of them. I ran all six, and all are green.
- **Open questions.** Q28 and Q29 are ticked: "Owner answered 2026-11-09: accepted the recommendation: no extra guard, no stub." and "Owner answered 2026-11-09: accepted." **Q27 is still open** (`- [ ]`, amendment 9: fold or retitle the three duplicate titles). I did not decide it and did not ask the owner. That is t16's W1, carried forward.
- **The landing's verification steps match the conventions file.** Met. `contractLanding.verification.steps` holds exactly `version-bump` (`py -3 .claude/scripts/check_version_bump.py`), `loop-script-tests` (`py -3 .claude/scripts/tests/test_pr_merged.py`), `hook-registration-tests` (`py -3 .claude/scripts/tests/test_check_hook_registrations.py`) and `hook-tests` (the `-c` one-liner). Each is character-equal to block 18's copy. `land_contract.py:987, 2713, 3104` read that list, and `:3125-3128` end `no-baseline` at V1 when the baseline is absent.
- **(A) The four steps on the parent tip `5960ebc`.** Met.
  - The bare v1 exits 1 with "… but the plugin version is still 0.16.5; raise it in all manifests". That is the expected pre-raise case.
  - Parent-mode v1 exits 0 with "keeps version 0.16.5".
  - v2: the first run exited 1 (1 of 761 failed) while other suites ran beside it. Run alone it exited 0 (761 OK). See W1.
  - v3 exits 0 (73 tests OK). v4 exits 0.
- **(A) Block 17's Run list and the search-(5) files.** Met. Every suite exits 0 except two rows that are not findings against this change:
  - `test_plugin_manifests.py`: only the INV-O1 row fails, as expected.
  - `test_land_contract_verification.py`: 2 failures that belong to master (N3).
  - `registry_migrate --check` gives `current`. The structure lint prints 39 R4 lines, one R3-skip line and `digest: absent`, with no R1, R2, R3, R5 or A1 line.
- **(B) The four steps on a throwaway landing merge.** Met, with W2 (block 18's procedure cannot run as written).
  - I merged origin/master `686a61a` into `5960ebc` (merge `f5b63cd`, exit 0, three records files, no conflict).
  - `--raise` exits 0 and makes its own commit `c620de8`, raising 0.16.5 → 0.17.0. The block's `git commit -am` therefore exits 1 ("nothing added to commit").
  - `--exact` exits 0 ("version is exactly 0.17.0"). The bare v1 now exits 0 ("version raised to 0.17.0").
  - v2 exits 0 (761 OK), v3 exits 0 (73 OK) and v4 exits 0, each run alone.
  - I switched back to the task branch afterwards. Its ref is still `5960ebc`, and nothing was pushed.
- **Off-area drift.** Nothing to compare.
  - `derive_area.py` returns `uncategorized`.
  - The range touches the five files block 17 lists, plus the t17 brief (`34a95f9`, bookkeeping).
- **Last check: the landing merge is clean.** Met. `merge-tree` against origin/master `686a61a` exits 0 with no conflicting path and gives tree `d607497`. The parent is `5960ebc`, which holds t17's merge. origin/master moved past `efd8f83` by one records pull request only (#330, `06a8cd4`).

## Findings

### W1 (warning) — The loop-script-tests step failed once under load and passed alone. `.claude/scripts/tests/test_pr_merged.py:6279-6286`

During the first parent-tip run, `TestNeedsIssueAtTheReportCallSite.test_one_subtask_contract_no_issue_needs_issue_false` failed its fixture-sanity line: "'t1-backend' must appear in report['dispatch'] -- got None". Two other suite runners and some wait loops were running at the same time.

- Run alone, the class passes (3 tests OK).
- A full re-run alone passes (761 OK, exit 0), and so does the run on the throwaway landing merge.
- `_drive_report_needs_issue` (`:6160-6187`) mocks the state, the records and the default branch, but not every live call `main()` makes on the report path. I did not trace which unmocked call returned a report with no `dispatch` key.

The landing runs its steps one at a time, and t17 also saw 761 OK, so this does not block. But the step is judged by exit code with no baseline, so a recurrence halts P8 again with an `undetermined` attribution. Question for the owner: should a follow-up find the unmocked call? Fix, if wanted: mock it in `_drive_report_needs_issue`, outside this contract.

### W2 (warning) — Block 18's throwaway-merge procedure cannot run as written. Contract, block 18, "(B) Throwaway landing merge"

It fails in two places when run as written in a worktree-isolated session on this machine:

1. `git worktree add --detach .claude/worktrees/t18-landing-merge-scratch …`, run from this worktree, is refused by the main-checkout guard ("a worktree inside a worktree is nested; cut it flat under <main>/.claude/worktrees/"). A flat path under the main checkout's worktrees folder can be created (exit 0). But the worktree-isolation guard then refuses every git command aimed at it, whether by `Push-Location`/`cd` or by `git -C`. So I removed it at once (exit 0), and `git worktree list` no longer shows it.
2. `check_version_bump.py --raise` commits the raise itself (`check_version_bump.py:125`, `git commit -q --no-verify -m "chore: raise the plugin version to … at the landing"`). So the block's `git commit -am "scratch: landing raise (never pushed)"` exits 1 with "nothing added to commit".

I ran the same steps in this worktree on a detached HEAD at `origin/fix/235-domain-split-registries`. The task branch ref did not move (`5960ebc` before and after), and the scratch commits `f5b63cd` and `c620de8` are unreachable once the branch is checked out again. Nothing was pushed. Every step that proves P8 (merge, `--raise`, `--exact`, v1 to v4) exited 0 there.

Why this is not "blocked": block 18 says any non-zero step here blocks, "because the landing would halt at P8 again". The one non-zero step is the block's own redundant commit, which the landing does not run, because its P7b raise commits by itself. Fix: in a later amendment, drop the `git commit -am` line and run (B) on a detached HEAD in the reviewer's own worktree (or name a flat path and say that the session must be launched there).

### N1 (nit) — Block 18's `VENDORED_FILES` search expects three files; four are right. Contract, block 17 search (4) and block 18 "The tests read chk.VENDORED_FILES"

The amendment-10 critique fold scoped the search to `.claude/scripts README.md .claude/registries`, but it did not count the journal lesson that the same fold told block 17 to append. That lesson names `VENDORED_FILES` twice. So the correct output is the checker, its test, MECHANISMS.md and JOURNAL.md. t17 reported this in #329 ("Search (4) expectation"). The lesson the t16 report proposed (check a contract's command against the tree before approving the block) covers this class. Fix: none for the code. Correct the expectation at the next amendment.

### N2 (nit) — #329 summarises its RED output and skips four search-(5) suites. Record: pull request #329

- The RED and tests-first outputs are excerpts cut with "...", and the RED run's three test names are not printed. Block 17 asked for "the raw output".
- Search (5) named six files, and block 17 says "Run every file this search names". #329 says "Not run by the implementer: `test_registry_migrate`, `test_check_version_bump`, `test_design_document_paths`, `test_memory_boundary`".

I ran all four (40, 46, 5 and 117 tests, all OK), and I confirmed the RED state from the landing's failure text quoted in the "Amendment 10 record" and from the diff. So no check rests on an assertion. Journal entry `a74a52b` ("A merge block's pull request must paste …") already covers this class. Fix: none for this contract.

### N3 (nit) — `test_land_contract_verification.py` fails 2 rows, and both belong to master. `.claude/scripts/tests/test_land_contract_verification.py:498-508`

`test_generated_drift_is_the_last_step_and_lists_the_three_sentinel_keys` expects a last step `generated-drift`. `test_the_python_scripts_command_prints_per_test_lines_and_a_per_file_line_only_for_a_crash` expects a step `python-scripts`. The test just above them (`:491-494`) pins the configured steps as exactly the four landing steps, so these two contradict it on this repository's own config.

`git diff --stat origin/master HEAD` over the test, `land_contract.py` and `.claude/work-item-conventions.json` is empty, so master has the same two red rows. This suite is not a P8 step. Block 17 listed it as expected green, which was a contract mis-prediction. Fix: outside this contract, on master.

### N4 (nit, question) — The seven-file copy keys Project hook launcher rows differently from the plugin copy. `auto_improve_finish_install.py:123-143, 989-1004`

In a seven-file copy there is no `_claude_paths.py` (nor `.claude/hooks/_project_paths.py`), so `_launcher_api()` returns `None` and `_hook_key` falls back to the first `.py` token. A Project hook launcher row would then key on the launcher script, not on the hook script it runs. A profile recorded where `_claude_paths` is importable could fail to match on such a row.

The vendored-copy tests do not reach this. The fixture's six rows are plain exec rows, and its one `launch.py` row is the gate launcher with a `.py` argument. `_launcher_api` and its fail-soft branch are on master too (`origin/master:auto_improve_finish_install.py:119`), so this is not t17's or this contract's, and seven files is still the correct import closure. Question for the owner: should the vendored set or README step 2 say what happens to launcher rows? If so, file it as a follow-up.

## What was NOT checked

- I did not re-run the RED state on `a4f7c65`. I relied on the landing's failure text (quoted in the "Amendment 10 record") and on #329's excerpts (N2).
- I did not trace the unmocked call behind W1.
- I did not run a launcher-row case through a vendored copy (N4). I read the code path only.
- I did not run `test_gate_cost.py`. The hook-tests step excludes it, block 17's Run list does not name it, and t16 recorded it as environmental.
- I did not run the scripts-wide `unittest discover`. Only the suites the blocks name, and the search-(5) files, were run.
- I did not run the landing or ask the owner about Q27.
- Off the worktree diff, I appended one audit line to `~/.claude/logs/reviewer-verdicts.jsonl`, as my role requires. The worktree holds only this artefact and its Gate Output.

## Evidence

All commands were run from the worktree root on Windows (Git Bash, so `MSYS_NO_PATHCONV=1` was set for each `<rev>:<path>` argument), with `py -3` and `PYTHONIOENCODING=utf-8`. The long suites ran one at a time, except for the first (A) v2 run (W1). Scratch scripts lived under `C:\Temp\t18\`, outside the repository (`run_suites.py`, `checks.py`).

| Command | Exit | Result |
|---|---|---|
| `git fetch origin` ; `git rev-parse HEAD origin/fix/235-domain-split-registries origin/master` | 0 | `5960ebc`, `5960ebc`, `efd8f83` (at the start) |
| `git log --first-parent` and `git log --graph --format='%h %p \| %s'` over the parent branch | 0 | range `a4f7c65..5960ebc`: first-parent `5960ebc` only (parents `a4f7c65 34a95f9`); branch `58271ee` (parent `a4f7c65`) → `6f8dce9` → `c980ded` → `34a95f9`, none a merge |
| `git show --stat 58271ee 6f8dce9 c980ded 34a95f9` | 0 | checker +/−, test +/−, README 4/3; MECHANISMS.md +1; JOURNAL.md +7; the t17 brief 3/3 |
| `git diff --name-only a4f7c65 5960ebc` | 0 | JOURNAL.md, MECHANISMS.md, the checker, its test, the t17 brief, README.md |
| `py -3 -c "…json.load(… work-item-conventions.json)['contractLanding']['verification']"` | 0 | four steps, each command equal to block 18's copy |
| `git grep -n -w five -- .claude/scripts/check_hook_registrations.py` | 0 | `:10` "The five Registration rules", `:455` "Evaluate all five rules" (rules, not files) |
| `git grep -c -w FIVE_FILES -- .claude/scripts README.md .claude/registries` | 1 | no output |
| `git grep -c -w VENDORED_FILES -- .claude/scripts README.md .claude/registries` | 0 | `JOURNAL.md:2`, `MECHANISMS.md:1`, `check_hook_registrations.py:4`, `test_check_hook_registrations.py:6` (four files; N1) |
| `git grep -n -w VENDORED_FILES -- .claude/registries/JOURNAL.md` | 0 | `:553` (Lesson) and `:554` (Apply when) |
| `git grep -c -E "needs five files\|Vendor five files\|all five files\|the five files" -- .claude/scripts README.md .claude/registries` | 0 | `.claude/registries/MECHANISMS.md:1` only |
| `git grep -n -e "def test_the_vendored_file_list_is_exactly_the_seven_files_in_order" -e "def test_dependency_import_failure_is_exit_2_naming_every_vendored_file" -e "naming_the_five_files" -- …/test_check_hook_registrations.py` | 0 | `:700` and `:710`; the old name absent |
| Grep of `^\s*(import \|from \S+ import)` over the seven files | 0 | closure as listed in "What was checked"; one reachable lazy import, `auto_improve_finish_install.py:140` `_claude_paths` |
| `git grep -c -F "A change that adds a module-level import to a vendored script" -- .claude/registries/JOURNAL.md` | 0 | `.claude/registries/JOURNAL.md:1` |
| `git grep -n -F -e "<lesson title>" -e "## Project tier" -- .claude/registries/JOURNAL.md` | 0 | lesson `:550`, pointer `:557` |
| `py -3 -I C:\Temp\t18\checks.py <repo>` | 0 | journal: 6 quoted lines byte-equal at 550-555, heading once, pointer 557; MECHANISMS: Correction line equals block 17's text at 113, directly under entry 112; entry 112 unchanged since `a4f7c65` and still says "needs five files" |
| `git log --format='%h parents=%p' -S"<lesson title>" a4f7c65..5960ebc -- .claude/registries/JOURNAL.md` | 0 | `c980ded parents=6f8dce9` |
| `git log --format='%h parents=%p' -S"needs seven files in one folder, not five" a4f7c65..5960ebc -- .claude/registries/MECHANISMS.md` | 0 | `6f8dce9 parents=58271ee` |
| `git cat-file -e origin/master:.claude/scripts/_preview_apply.py` | 128 | "exists on disk, but not in 'origin/master'" (absent, as expected) |
| `git cat-file -e origin/master:.claude/scripts/_plugin_root.py` | 128 | absent |
| `git cat-file -e origin/master:.claude/scripts/check_hook_registrations.py` (control) | 0 | present |
| `git grep -n -F "_preview_apply" origin/master -- .claude/scripts/auto_improve_finish_install.py` | 1 | no output |
| `git grep -n -e "def _launcher_api" -e "api = _launcher_api()" origin/master -- …/auto_improve_finish_install.py` | 0 | `:119`, `:1093`, `:1401`, `:2764` (N4 is master's) |
| `git log --oneline --no-merges a4f7c65..5960ebc -- plugin.json .claude-plugin .cursor-plugin` | 0 | empty |
| `git diff --stat a4f7c65 5960ebc -- plugin.json .claude-plugin .cursor-plugin` | 0 | empty |
| `git show origin/master:plugin.json` | 0 | `"version": "0.16.5"` (HEAD the same) |
| `git diff --stat a4f7c65 5960ebc -- README.md` | 0 | 1 file, 4 insertions, 3 deletions, one hunk (step 2) |
| `gh pr view 329 --json state,mergeCommit,baseRefName,headRefName,body,comments` | 0 | MERGED into `fix/235-…` as `5960ebc`; body only (no comments); RED, tests-first, `registry_append` file:lines, searches 1-5, GREEN list (N1, N2) |
| `grep` of Q27, Q28, Q29 in the contract | 0 | Q27 `- [ ]`; Q28 and Q29 `- [x]`, "Owner answered 2026-11-09" |
| `git diff --stat origin/master HEAD -- .claude/work-item-conventions.json …/test_land_contract_verification.py .claude/scripts/land_contract.py` | 0 | empty (N3 is master's) |
| `py -3 .claude/scripts/derive_area.py .claude/concepts/2026-11-04-domain-split-registries.md` | 0 | `uncategorized` |
| **(A) parent tip `5960ebc`** | | |
| (v1) `py -3 .claude/scripts/check_version_bump.py` | 1 | first line: "VERSION BUMP: shipped files changed (…round-1.md, …round-2.md, …round-3.md) but the plugin version is still 0.16.5; raise it in all manifests" (expected before the raise) |
| (v1) `py -3 .claude/scripts/check_version_bump.py --base origin/fix/235-domain-split-registries --default-branch master --head-ref task/2026-11-04-domain-split-registries/t18-review` | 0 | "VERSION BUMP: sub-task pull request keeps version 0.16.5; the landing raises it" |
| (v2) `py -3 .claude/scripts/tests/test_pr_merged.py`, first run (concurrent with other suites) | 1 | 761 run, 1 failure: `TestNeedsIssueAtTheReportCallSite.test_one_subtask_contract_no_issue_needs_issue_false`, "'t1-backend' must appear in report['dispatch'] -- got None" (W1) |
| `py -3 .claude/scripts/tests/test_pr_merged.py TestNeedsIssueAtTheReportCallSite` | 0 | 3 tests OK |
| (v2) `py -3 .claude/scripts/tests/test_pr_merged.py`, re-run alone | 0 | 761 tests OK in 943 s |
| (v3) `py -3 .claude/scripts/tests/test_check_hook_registrations.py` | 0 | 73 tests OK |
| (v4) hook-tests one-liner, verbatim | 0 | every hook suite green; last line "results: 190 passed, 0 failed (of 190)" (`test_worktree_path_guards.py`, real-folder check PASS) |
| `py -3 .claude/scripts/tests/test_auto_improve_finish_install.py` | 0 | 421 tests OK |
| `py -3 .claude/scripts/tests/test_preview_apply.py` | 0 | 15 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_root.py` | 0 | 8 tests OK |
| `py -3 .claude/scripts/tests/test_land_contract_verification.py` | 1 | 79 run, failures=2: the two `RealProjectConfigTests` rows of N3 only |
| `py -3 .claude/scripts/tests/test_registry_append.py` | 0 | 29 tests OK |
| `py -3 .claude/scripts/tests/test_registry_layout.py` | 0 | 83 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 0 | 37 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_manifests.py` | 1 | 204 passed, 1 failed: only INV-O1 "the version obeys the merge-base rule: tree differs from the merge base (0.16.5), so all five declarations exceed it" |
| `py -3 .claude/scripts/tests/test_registry_migrate.py` (search 5) | 0 | 40 tests OK |
| `py -3 .claude/scripts/tests/test_check_version_bump.py` (search 5) | 0 | 46 tests OK |
| `py -3 .claude/scripts/tests/test_design_document_paths.py` (search 5) | 0 | 5 tests OK |
| `py -3 .claude/scripts/tests/test_memory_boundary.py` (search 5) | 0 | 117 tests OK |
| `py -3 .claude/scripts/tests/test_registry_entries.py` | 0 | 36 tests OK |
| `py -3 .claude/scripts/registry_migrate.py --check --project .` | 0 | `state: current`, `marker: 2`, `reasons: []` |
| `py -3 .claude/scripts/validate_registries.py --check-structure --project .` | 0 | 39 R4 lines, "advisory: R3 universal-candidate skipped: 19 entries; this project holds the plugin's own manifest", "digest: absent"; no R1, R2, R3, R5 or A1 line |
| **(B) throwaway landing merge** | | |
| `git worktree add --detach .claude/worktrees/t18-landing-merge-scratch origin/fix/235-domain-split-registries` | refused | main-checkout guard: "a worktree inside a worktree is nested" (W2) |
| `git worktree add --detach D:/…/claude-agentic-auto-improve/.claude/worktrees/t18-landing-merge-scratch origin/fix/235-domain-split-registries` | 0 | detached at `5960ebc` |
| `cd <scratch> && git merge …` ; `git -C <scratch> merge …` | refused | worktree-isolation guard (W2) |
| `git worktree remove D:/…/t18-landing-merge-scratch` ; `git worktree list` | 0 | removed; the list has no scratch entry (`grep -c` 0, exit 1) |
| `git fetch origin` ; `git rev-parse origin/master origin/fix/235-domain-split-registries task/…/t18-review` | 0 | `686a61a` (master moved by #330, records only: `06a8cd4`), `5960ebc`, `5960ebc` |
| `git checkout --detach origin/fix/235-domain-split-registries` (in this worktree) | 0 | HEAD `5960ebc`, detached |
| `git merge --no-ff --no-edit origin/master` | 0 | merge `f5b63cd` (parents `5960ebc 686a61a`); 3 files added under `.claude/orchestrator/results/…`; no conflict |
| `py -3 .claude/scripts/check_version_bump.py --raise --default-branch master` | 0 | "VERSION BUMP: manifests raised to 0.17.0"; it committed `c620de8` itself (4 manifests, 5 lines) |
| `git commit -am "scratch: landing raise (never pushed)"` | 1 | "nothing added to commit but untracked files present" (W2) |
| `py -3 .claude/scripts/check_version_bump.py --exact --default-branch master` | 0 | "VERSION BUMP: version is exactly 0.17.0" |
| (v1) `py -3 .claude/scripts/check_version_bump.py` | 0 | "VERSION BUMP: version raised to 0.17.0" |
| (v3) `py -3 .claude/scripts/tests/test_check_hook_registrations.py` | 0 | 73 tests OK |
| (v2) `py -3 .claude/scripts/tests/test_pr_merged.py` (alone) | 0 | 761 tests OK in 846 s |
| (v4) hook-tests one-liner, verbatim (alone) | 0 | every hook suite green; last line "results: 190 passed, 0 failed (of 190)" |
| `git checkout task/2026-11-04-domain-split-registries/t18-review` ; `git rev-parse HEAD` ; `git status --short` | 0 | back on the branch at `5960ebc` (unchanged); git names `c620de8` and `f5b63cd` as left behind, unconnected; status shows only this artefact and its Gate Output |
| **Last check**, run live after every other check: `git fetch origin ; git merge-tree --write-tree --name-only origin/master origin/fix/235-domain-split-registries` | 0 | origin/master `686a61aa65e2`, parent `5960ebc55d81` (the #329 merge, which holds t17), tree `d607497c9f34`, no conflicting path (2026-11-10T02:34:31Z) |

**Version proof at the landing.** The version proof is the landing's own `check_version_bump.py --raise`, then `--exact` (gate P7b), and its version-bump verification step. Each must exit 0, with the raised version equal to origin/master's version at landing time, minor + 1 and patch 0. At amendment time that was 0.16.5 → 0.17.0. I read origin/master at 0.16.5 today, so the figure holds, and my throwaway merge produced exactly 0.17.0 with all three steps exiting 0.

**Landing command for the operator (I did not run it).**

1. Answer Q27 first (t16 W1).
2. Immediately before launching, re-run the last check: `git fetch origin ; git merge-tree --write-tree --name-only origin/master origin/fix/235-domain-split-registries`. It must exit 0 with no conflicting path. A clean result is valid only for the origin/master commit it names (here `686a61a`).
3. Then, in Claude Code, run:

```
/advance 2026-11-04-domain-split-registries
```

## Disposition

- **Pass with findings.**
  - Sub-task 17 does what block 17 asks. `VENDORED_FILES` holds the seven files in order, the refusal message and remedy count from it, and the tests read it, with a pin test. README step 2 and one Correction line are right, and the Q28 lesson is in place once, byte-equal.
  - The import closure is exactly those seven files.
  - The defect is absent on master. No version file changed.
  - The landing's four steps pass on the parent tip and on a throwaway merge with origin/master and the 0.17.0 raise.
  - The landing merge is clean against origin/master `686a61a`.
- **t16's W1 (Q27) is still open.** The owner answers it before launching the landing.
- **W1** is a flake risk for P8: one failure under load, not reproduced alone. It does not block. A follow-up can mock the live call.
- **W2** is contract text only: block 18's (B) procedure cannot run as written. The landing is unaffected.
- **N1 to N4** are optional. N1 and W2 are contract-text corrections for a later amendment. N3 and N4 belong to master.
- **Registry janitor.**
  - No new mechanism or vocabulary term in `a4f7c65..5960ebc`. `VENDORED_FILES` is the existing list, extended, and the mechanism entry has its Correction line.
  - The amendment-10 lesson was the only journal append due, and it is in.
  - INTEGRATION.md does not apply: there is no REST, SignalR or DTO surface.
  - This task may write only this artefact and its Gate Output, so I am proposing one lesson, not appending it. Batch it with the landing's raise through `registry_append.py --registry journal --universal`, if wanted:

  ```markdown
  ### 2026-11-09 — Run a review block's scratch procedure against the guards and the scripts it calls before approving it
  - **Trigger:** post-impl divergence
  - **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
  - **Lesson:** Block 18 told the reviewer to build a throwaway landing merge in a nested scratch worktree and to commit the version raise by hand, but the main-checkout guard refuses nested worktrees, the worktree-isolation guard refuses git in any other worktree, and `check_version_bump.py --raise` already commits, so its worktree steps and its commit step failed as written. When a block prescribes a git procedure, check it against the session's guards and against what each called script does, and prefer a detached HEAD in the agent's own worktree for throwaway merges.
  - **Apply when:** an amendment adds a scratch merge, a second worktree or a manual commit to a review or merge block.
  - **Tags:** contract-text, worktree, guards, landing, review
  ```
