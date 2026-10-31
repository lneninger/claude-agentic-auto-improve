# t10 review — fullstack-code-reviewer

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t10-review (issue #86)
- **Contract:** `.claude/concepts/2026-10-30-angular-tailwind-followups.md` (approved)
- **Reviewed on:** 2026-10-31
- **Commit range reviewed:** `0cae694..238d15c` (parent branch `feature/86-angular-tailwind-followups`, from the commit that opened the sub-task briefs to the merge of pull request #140, t9)
- **Sub-task merges in the range (first parent):** t1 `640c729` (#127), t2 `e024be6` (#129), t3 `1536a71` (#131), t4 `1076f32` (#133), t5 `672c74d` (#135), t6 `7bdfad3` (#137), t7 `f8eb9c2` (#138), t8 `9340920` (#139), t9 `238d15c` (#140)

**Verdict:** pass-with-findings

## What was checked

- **G-0 (ledger).** Met. Every weak spot W1 to W11 (W6 split into W6a and W6b) has one disposition. The accepted ones (W5, W6b, W8, W11) are in the guard docstring's "Known limits" block. Each is pinned by `test_w5_*`, `test_w6b_*`, `test_w8_*` or `test_w11_*` in `test_architecture_guard_precision.py`. W2 is pinned by `test_no_clientapp_and_no_features_folder_in_the_guard`. W10 is pinned by `test_design_document_paths.py`. One accepted limit that is not in the ledger was added; see finding N2.
- **G-1.** Met. `load_app_rules` walks `app_root_segments()`, which holds one entry per segment of `frontend_projects_root`. The literal `"projects"` comparison is gone. Each control has a test: the rules file renamed away, `"apps"`, and a two-segment root. Backslash, padding and doubled slashes also have tests.
- **G-2.** Met. The predicates use `@Component\s*\(`. A suffix-less `.html`, `.scss` or `.css` file counts only through its `<stem>.ts` sibling on disk. A `.ts` file counts through its post-edit view. `.spec.ts` and `.d.ts` are rejected by name, before the file is read. `classify_sibling_component` now removes the actual suffix and reads `<stem>.component.ts` before `<stem>.ts`. Every listed negative has a test (`index.html`, `main.ts`, `x.spec.ts`, `x.d.ts`, and `app.html` beside an undecorated `app.ts`), and so do the `.css` case and the `@Component ({` spelling. The accepted limit is pinned.
- **G-3.** Met. The guard calls neither `Path.home` nor `HOME`. The fallback is `HOOK_DIR`, the hook's own folder. Only the `hook_file`-order sentence in the docstring names `~/.claude`. The `ast` and string tests exist, and so do the `promote-ui-rule` lookup-block tests for steps 3 and 4.
- **G-4.** Met. `build_post_edit_view` reads strict UTF-8, folds CRLF to LF in the disk text and in both strings, and enforces the uniqueness of `old_string` unless `replace_all` is set. It applies MultiEdit edits in order and is built once per file per call (`post_edit_snapshot`). Its reasons match the contract's list. The line rules judge each fragment. The whole-file rules run once per file in `scan_whole_file_rules`. Inline-rule findings are reported once per rule, and `dedupe_violations` drops a repeat with the same rule, line and text. Tests cover a three-edit MultiEdit, CRLF, non-UTF-8 input, a missing file, an ambiguous `old_string`, `replace_all`, the inline-template add and the height-chain fragment.
- **G-5.** Met. `is_template_reference_variable` checks all four conditions. Every allowed and blocked row in the contract has a test, and the `  #fff` limit is pinned. `RX_HEX_COLOR` matches only 3- or 6-character runs, so the stated limit is exact.
- **V-1.** Met. `PostEditView.reason` is set exactly when `text` is `None`. A Write has `reason=""`, and a builder fault gives `builder-error`.
- **V-2.** Met. All seven fallbacks are present. Each has a forced-raise test that expects exit 2: the view builder, the root walk, the G-2 checks (three tests), the G-5 reference test, the whole-file pass (with its height-chain fallback), the view-against-disk comparison, and de-duplication. No new step can raise into the outer catch.
- **K-1.** Met. Neither `codegraph/addon.json` nor `strict-shell-gate/addon.json` has a `kill_switches` key, and a grep for the key under `.claude/addons/` finds only prose in `DISABLED.md`. The install suite expects an empty `kill-switches` list; see Evidence.
- **K-2.** Met. A grep for the three names under `.claude/addons/` exits 1 (no match). `test_plugin_manifests` passes both the text check and the `env_vars_read_by` check, and their planted-variable controls.
- **K-3.** Met. `concept-gate.py` is unchanged and still reads `CLAUDE_CONCEPT_GATE` (`:242`), and a test checks that. `bash-gate.py` no longer reads it. README (`:209`, `:268-269`, `:328`), both strict-shell-gate skills and the release note say so.
- **K-4.** Met. The codegraph block message is self-contained. It says to call a CodeGraph tool, to read through the shell, to uninstall and start a new session, and to run `codegraph sync` / `init -i`, and it names the install skill. It names no `references/` path and no `CLAUDE_SKIP_CG`. README has the "Ways out when a hook cannot run" table with all five rows. The uninstall skills carry the new wording. The `test_shell_write_targets` reachability tests and the import-failure message test exist. The environment strip lists are unchanged.
- **D-1.** Met. `FINDING_KINDS` gains only `disabled-hook-installed`.
- **D-2.** Met. `add()` keys findings by `(kind, path)` through `setdefault`.
- **D-3.** Partly met. The detection is right: every add-on is checked, names are compared case-insensitively, and `_effective_hooks` runs once per layer, with the reported finding paths. The parity fixtures and the gate-launch and non-object divergences have tests. However, the contract's first divergence, that the install refuses a user-layer row, is false. Finding W1 covers it.
- **D-4.** Met. Documents are compared when the sync config lists the add-on, or when any of its documents exists in the project. Line endings are folded. `content-differs` and `one-sided` are owned by `plugin`. `test_the_destination_constant_equals_the_installs` tests the `ADDON_DOCUMENTS_REL` equality.
- **D-5.** Met. `test_a_run_with_disabled_hooks_and_documents_changes_no_file` and `test_a_run_that_compares_nothing_still_exits_4` cover it.
- **"Enforced by" corrections, and only those.** Met. A `-U0` diff shows exactly `TAILWINDCSS_RULES.md:29,54,61,109,148` and `ANGULAR_CODE_RULES.md:37`. The verbatim old-hook lines (`TAILWINDCSS_RULES.md:27`, `ANGULAR_CODE_RULES.md:35`) are unchanged, and no other rule entry changed.
- **P-002 and the rejections.** Met. P-002 right-aligns numeric columns and their headers, left-aligns text columns, and aligns each header with its column. It says "Enforced by: not enforced." and has one short example. The boundary paragraph names P-002. "Patterns this plugin does not ship" lists the status badge, the card surface and the constrained panel, with the contract's reasons. The cited `tabular-nums` rule, `T-014` and the `application-design` skill all exist. No catalogue rule already states column alignment.
- **Registry appends verbatim, merged after t1, t3 and t5.** Met. A scripted comparison of the added lines against the contract's `## Registry appends` matched every line: 13 in VOCABULARY and 11 in MECHANISMS, with 0 lines removed. The text sits at the end of the Universal tier, and the CodeGraph entry at MECHANISMS.md:15 is untouched. t8 (`9340920`) merged after t1 (`640c729`), t3 (`1536a71`) and t5 (`672c74d`).
- **The trial record's commands and exit codes.** Partly met. Each run has its command, exit code and observed outcome, plus the three yes/no answers, the date, the host version, the install mode and the front matter. However, only Git Bash was run. Finding W2 covers it.
- **No sub-task pull request changes a version file (Rule V).** Met. `git log 0cae694..HEAD` on the four manifest files lists no commit. All five declarations read 0.11.0, equal to `origin/master`. `check_version_bump.py` in parent mode exits 0.
- **The guard suites ran unchanged.** Met. `test_architecture_guard_scss.py`, `test_architecture_guard_messages.py`, `test_hook_data_files_project_first.py` and `test_skill_script_lookup.py` show no diff in the range, and all pass.
- **Off-list files (data-first audit).** One source file outside the list: `test_angular_rule_coverage.py`. Finding N1 covers it. `concept-gate.py`, `concept_changed_check.py`, the advisor script and the strip-list tests are unchanged, as the Non-Goals require.

## Findings

### W1 (warning) — The D-3 user-layer divergence is false, and the release note repeats it. `README.md:350-351`; contract D-3

The contract pins "a user-layer row: the install refuses and the doctor is silent". The install does not refuse it. `_disabled_hook_refusal` keeps only the `project` and `local` layers (`auto_improve_finish_install.py:2097`). t5 found this and pinned the real behaviour in `test_a_user_layer_row_is_silent_in_both_readers_contrary_to_the_contract` (`test_plugin_doctor.py:1350-1360`). No contract amendment, journal entry or pull request text records the divergence. The t9 release note still ships the false claim: "a disabled hook row there is refused by the install but not reported by the doctor". A user who reads it believes a user-layer row is caught at install time, and it is not.

Fix: change the release-note sentence to "Neither the doctor nor the install reads the user-level settings layer, so a disabled hook row there is reported by neither." Also append a `post-impl divergence` entry to JOURNAL.md; the proposed text is under Disposition. If the install should refuse a user-layer row, that is a follow-up contract, not part of this one.

### W2 (warning) — The trial ran in one shell, and the PowerShell commands were written up, not run. `.claude/references/claude-rules-route-trial.md:46-84`

The t7 constraint asked for the PowerShell commands, then the same commands in Bash, with each output and exit code recorded. The record says every run went through Git Bash, because the worktree guard refused the PowerShell wrapper. The ```powershell blocks are therefore after-the-fact restatements, not the commands that ran. The Bash command lines that did produce the exit codes are not shown, and the outputs are paraphrased, not quoted. The record says all of this openly, and the outcome does not depend on the shell, so this does not block. Even so, the record does not show the commands that produced its exit codes.

Fix: label the blocks "PowerShell form (not run)", and add the Bash command line that actually ran for each of runs 1a, 1b, 2 and 3. Or run the PowerShell form once and record its exit code.

### W3 (warning) — `test_plugin_manifests.py` exits 1 on the parent branch (INV-O1), and no record mentions it. `.claude/scripts/tests/test_plugin_manifests.py`, INV-O1

173 checks pass and 1 fails: "the version obeys the merge-base rule … tree differs from the merge base (0.11.0)". Under Rule V this is expected until the landing raise. INV-O1 has no parent mode, so it fails on every sub-task branch of every parent-branch contract. t3 ran this suite, but neither its record nor the t1 or t2 reviews mention the failure. The suite should be green once the landing raises 0.11.0 to 0.12.0. The landing must re-run it and expect exit 0. Making INV-O1 aware of parent mode is outside this contract.

### N1 (nit) — t6 changed a file outside its list: `test_angular_rule_coverage.py`. `.claude/hooks/tests/test_angular_rule_coverage.py:84-88`

That test keeps a verbatim copy of the boundary paragraph, which t6 had to update, so the edit follows from the brief. Commit `92b4983` states it, and the file is in the same add-on area. Acceptable, but the block-6 file list should have named it.

### N2 (nit) — The ledger does not list one accepted guard limit. `architecture-guard.py` docstring, G-5 entry

After the t1 review (W-2 there), an apostrophe inside a double-quoted attribute (`aria-label="Don't save" #add`) makes the quote count odd. The reference variable is then read as a colour, and the edit is blocked: a false block, not a miss. The limit is documented and pinned (`test_g5_apostrophe_*`), but the contract's G-5 lists one accepted limit and the ledger is unchanged. `TAILWINDCSS_RULES.md:61` does not mention it either.

### N3 (nit) — Two counts in the release note and the trial record are off. `README.md:303`, `:364-365`; `claude-rules-route-trial.md:3`

"It has eight parts" sits above a ten-bullet list. "Three headless runs" and "the three runs below" describe four invocations (1a, 1b, 2, 3).

### N4 (nit) — A shipped reference file holds a local user path. `claude-rules-route-trial.md:46,103`

`C:\Users\lneni\AppData\Local\Temp\rules-trial-t7` ships to every project. `%TEMP%\rules-trial-t7` alone is enough.

### N5 (nit) — De-duplication uses line numbers that count from the start of each edit. `architecture-guard.py`, `dedupe_violations`

The key is `(rule, line_no, line_text)`. Line rules count each edit's lines from 1, so two edits of one MultiEdit that add the same line text at the same position in their edits are reported once. The call still exits 2, so nothing is let through; only the count shown is lower. This is consistent with "reported once" in G-4.

## What was NOT checked

- The interactive (non-headless) behaviour of the `.claude/rules/` route. The t7 runs were not reproduced; only the record was read.
- Real Windows PowerShell runs of any command in the record.
- The landing itself: the `--raise` / `--exact` result, and that 0.12.0 is the version produced. `origin/master` reads 0.11.0 today, so minor + 1 gives 0.12.0, which matches the release note, but nothing has raised it yet.
- The full test tree. Only the suites the contract names and the suites of touched files were run (see Evidence).
- The contents of the user's global `~/.claude/CLAUDE.md`, beyond confirming that the README lists the three lines.
- The reviewer-verdict JSONL log and the JOURNAL.md append. This gate may write only the two artefact files, so both are proposed in Disposition, not written.

## Evidence

Every command ran from the t10 worktree root on 2026-10-31.

| Command | Exit | Result |
|---|---|---|
| `git log --oneline --first-parent feature/86-angular-tailwind-followups -30` | 0 | sub-task merges t1 to t8; HEAD `238d15c` adds t9 (= `origin/feature/86-angular-tailwind-followups`) |
| `git diff --stat 0cae694 HEAD` | 0 | 47 files; no manifest file |
| `git log --first-parent --format=%h 0cae694..HEAD -- plugin.json .claude-plugin/plugin.json .cursor-plugin/plugin.json .claude-plugin/marketplace.json` | 0 | empty |
| `git log --format='%h %s' 0cae694..HEAD -- <same four files>` | 0 | empty |
| `grep -h '"version"' plugin.json .claude-plugin/plugin.json .cursor-plugin/plugin.json .claude-plugin/marketplace.json` | 0 | 0.11.0 ×5 |
| `git show origin/master:plugin.json` (version) | 0 | 0.11.0 |
| `py -3 .claude/scripts/check_version_bump.py --base origin/feature/86-angular-tailwind-followups --default-branch master --head-ref task/2026-10-30-angular-tailwind-followups/t10-review` | 0 | "sub-task pull request keeps version 0.11.0; the landing raises it" |
| `git diff --name-only 0cae694 HEAD -- test_architecture_guard_scss.py test_architecture_guard_messages.py test_hook_data_files_project_first.py test_skill_script_lookup.py` | 0 | empty (unchanged) |
| `git diff --stat 0cae694 HEAD -- concept-gate.py concept_changed_check.py addons/angular-tailwind/hooks/ test_flat_worktree.py test_worktree_path_guards.py` | 0 | empty (unchanged) |
| `git diff -U0 0cae694 HEAD -- TAILWINDCSS_RULES.md ANGULAR_CODE_RULES.md` | 0 | hunks only at T:29, 54, 61, 109, 148 and A:37 |
| `git grep -n kill_switches -- .claude/addons/` | 0 | one prose hit in `DISABLED.md:33` only |
| `git grep -n "CLAUDE_SKIP_CG\|CLAUDE_BASH_GATE\|CLAUDE_CONCEPT_GATE" -- .claude/addons/` | 1 | no match |
| `py -3 -I -c <registry verbatim comparison against the contract's ## Registry appends>` | 0 | VOCABULARY verbatim 13/13, MECHANISMS verbatim 11/11, 0 lines removed |
| `grep -n -A25 "def _disabled_hook_refusal" .claude/scripts/auto_improve_finish_install.py` | 0 | `:2097` filters `row["layer"] in ("project", "local")` (W1) |
| `py -3 .claude/hooks/tests/test_architecture_guard_scss.py` | 0 | Ran 32, OK |
| `py -3 .claude/hooks/tests/test_architecture_guard_messages.py` | 0 | Ran 24, OK |
| `py -3 .claude/hooks/tests/test_hook_data_files_project_first.py` | 0 | 29 passed, 0 failed |
| `py -3 .claude/hooks/tests/test_architecture_guard_precision.py` | 0 | Ran 44, OK |
| `py -3 .claude/hooks/tests/test_architecture_guard_paths.py` | 0 | Ran 56, OK |
| `py -3 .claude/hooks/tests/test_angular_rule_coverage.py` | 0 | Ran 17, OK |
| `py -3 .claude/scripts/tests/test_skill_script_lookup.py` | 0 | Ran 23, OK |
| `py -3 .claude/scripts/tests/test_design_document_paths.py` | 0 | Ran 5, OK |
| `py -3 .claude/hooks/tests/test_addons.py` | 0 | Ran 17, OK |
| `py -3 .claude/hooks/tests/test_codegraph_first_guard.py` | 0 | 28 passed, 0 failed |
| `py -3 .claude/hooks/tests/test_shell_write_targets.py` | 0 | Ran 19, OK |
| `py -3 .claude/scripts/tests/test_agent_skill_preloads.py` | 0 | Ran 4, OK |
| `py -3 .claude/scripts/tests/test_plugin_manifests.py` | 1 | 173 passed, 1 failed: INV-O1 merge-base version rule (W3; expected before the landing raise) |
| `py -3 .claude/scripts/tests/test_plugin_doctor.py` | 0 | Ran 114, OK (skipped=1) |
| `py -3 .claude/hooks/tests/test_contract_index.py` | 0 | 197 passed, 0 failed (section (f): neither switch has any effect on bash-gate) |
| `py -3 .claude/hooks/tests/test_main_checkout_guard.py` | 0 | Ran 55, OK |
| `py -3 .claude/scripts/tests/test_auto_improve_finish_install.py` | 0 | Ran 304, OK (the plan's `kill-switches` is `[]`; the env-var set is `{CLAUDE_CONCEPT_GATE, CLAUDE_ARCH_GUARD}`) |

Files read: the contract; the diffs of `architecture-guard.py`, `plugin_doctor.py`, `codegraph-first-guard.py`, `bash-gate.py`, `DISABLED.md`, `UI-UX-PATTERNS.md`, the rule documents, the registries and `agents/python-ai-developer.md`; `claude-rules-route-trial.md`; README `:300-370` and the K-4 table; the four add-on skills (grep); `test_plugin_doctor.py:1350-1380`; the t1 and t2 review artefacts.

## Disposition

The contract can continue to the landing. Nothing here is a blocker. Before or at the landing:

1. **W1:** correct the README sentence (`README.md:350-351`) as given above, in the landing pull request or a follow-up sub-task. Append this JOURNAL.md entry under the project section (this gate may not write it):

   ```markdown
   ### 2026-10-31 — A pinned divergence between two readers must be verified against both readers' code
   - **Trigger:** post-impl divergence
   - **Source contract:** .claude/concepts/2026-10-30-angular-tailwind-followups.md
   - **Lesson:** Before a contract pins "reader A does X and reader B does not", cite the line in each reader that does or skips X; t5 found the install never reads the user layer, so the pinned divergence was false.
   - **Apply when:** a contract's Data Shapes lists expected divergences or parity between two code paths (install vs doctor, hook vs checker).
   - **Tags:** parity, divergence, plugin-doctor, install, settings-layer
   ```

2. **W3:** after `check_version_bump.py --raise` and `--exact`, the landing re-runs `test_plugin_manifests.py` and expects exit 0.
3. **W2, N1 to N5:** optional fixes. W2 and N3 to N4 are a few lines in `claude-rules-route-trial.md` and `README.md`. N2 is a one-line contract or ledger note.
4. Append the reviewer-verdict line to `~/.claude/logs/reviewer-verdicts.jsonl` (outside this gate's write scope): `{"ts":"2026-10-31T00:00:00Z","contract_path":"D:/Dev/HIPALANET/claude-agentic-auto-improve/.claude/concepts/2026-10-30-angular-tailwind-followups.md","divergence":true,"drift_summary":"D-3 user-layer divergence false: install skips the user layer; README repeats the false claim","critical_count":0,"warn_count":3}`.

This gate releases its dependents.
