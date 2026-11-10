# t2 fail-open review — fullstack-code-reviewer

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t2-fail-open-review (issue #326)
- **Contract:** `.claude/concepts/2026-11-09-codegraph-hooks-cutover.md` (approved)
- **Reviewed on:** 2026-11-09
- **Commit range reviewed:** `fb89001..81ee03d`. `fb89001` is the merge base of `origin/master` and the parent branch `feature/262-codegraph-hooks-cutover`; `81ee03d` is the parent head, the merge of pull request #331 (block 1). The local `master` ref is stale (`c02d475`), so the merge base was taken against `origin/master`.
- **Commits in the range:** `c8dfd33` (contract and briefs), `b254c21` (guard), `672bb03` (installer retire op), `06c846a` (report), `8be6430` (docs), `2bbf95e` (brief), `81ee03d` (merge of #331).
- **Scope:** Python hooks, installer, report script, manifests, tests and docs. There is no C# or Angular code, so those checklists do not apply. End-User View: not applicable (no UI surface). Adjacent Areas: not applicable (`.claude/area-mapping.json` has no areas, so every file derives `uncategorized`). Every changed file is in block 1's Files to touch, or is a contract, brief, follow-up or state record under `.claude/`.

**Verdict:** pass-with-findings

## What was checked

1. **Every unknown transcript cause allows with a logged reason, and nothing in the read can block on a guess:** met. `read_transcript` (guard:1717-1853) gives `unknown:<cause>` for each of these: a subagent, a missing path, a missing file, a non-regular file, unreadable, time exceeded (before and during the read), rewritten, window exceeded (a hit limit, or no boundary in a mid-file cold window), and parse error. `_read_turn` (:1147-1158) maps any exception to `unknown:error`. Step 3a (:1203-1204) allows every cause as `fail-open:transcript-<cause>`, and `announce_record` / `announce_line` give one log record per session per reason and the stderr line. A closed state comes only from a positively identified human prompt or a cold scan from byte 0. One theoretical residue is noted as N1.
2. **C-1 order, including the unusable-folder rule (Q3 as answered) and no fail-open line on an allowlisted target:** met. `_plan` (:1168-1237) runs 0, 1, 2, 3, 3a, 4-5, 6, 7. An unusable folder skips the read and gives `closed` (:1150-1151), so it reaches step 7 as `session-state-unusable` (row CO-11). Step 3a comes after classification, so a `README.md` read with an unknown state prints nothing (row CO-9, and smoke S4 re-run here).
3. **C-2: no effect after the ticket can change exit code or stderr:** met. In `main()` (:2447-2461), `apply_state` (availability, then the ticket) comes first. The cursor, the cli-fallback record, the fail-open record and the Measurement record each run under `_quiet`, which swallows `BaseException`. Only then come `announce_line` or `block()`. Row CO-17 forces each late effect to raise, and both the exit code and stderr stay the same.
4. **The block rows of the three named suites keep their assertions and gained a closed transcript (diffed):** met. In `test_worktree_path_guards.py`, `read_payload` and `grep_path_payload` now carry `CLOSED_TRANSCRIPT`, and no block expectation changed (0 removed block assertions). In `test_addons.py`, 0 block assertions were removed. In `test_codegraph_first_guard.py`, 13 block assertions were removed with no identical re-add. Each one was traced:
   - **Rewritten on a closed transcript with the same outcome:** E-6, T-1 control and fresh, T-3 other session, T-4, T-5, T-7 control, AC2 stranger.
   - **Flipped to allow by the contract's own Q1:** CLI-3 and RT-3. A failed call now counts (Alternative F was rejected). RT-3 became a sidechain row that still blocks.
   - **Dropped because their subject retired:** E-6b (the reset hook deleting tickets) and F3 (a marker write).
   - **One control dropped:** the T-7 "another session is still BLOCKED" control, see N2.
   
   CLI-2 (non-counted forms) and CLI-4 (background run) still assert a block.
5. **The Bash route uses the strict Counted test, not the row's if:** met. `entry_facts` (:1631-1632) calls `counted_subcommand` (:1581-1604). That function is the tracker's (`codegraph-turn-tracker.py:310-329`) line for line, plus a dict type guard. A compound command stays closed (smoke S2 compound, re-run here).
6. **Tickets keyed to the prompt; an old ticket reads as absent:** met. `_prompt_key` (:1138-1144) takes 12 hex of the SHA-256 of `prompt_id`, or `none` (Q6). `_ticket_matches` (:1161-1165) needs a plain file, parseable JSON and an equal `prompt_key`. Rows: E-6 and CO-12 (another prompt, and no key, both BLOCKED with the ticket overwritten).
7. **The prompt row always exits 0, prunes once, keeps the notice outcomes:** met. `notice_main` (:2386-2417) wraps everything in `BaseException` and then calls `sys.exit(0)`. Pruning is guarded by the `pruned` flag (`_first_prompt_of_session`, `_prune_once`). The notice is `notice_section`, carried verbatim, with the closed outcome set and the 100 ms budget. An unusable folder prints the reset hook's line without "the gate stays shut". Rows: PRW-1..6, NT-6, NM-1..5. Re-run here: S6 and S6b exit 0, and no `__pycache__` appeared.
8. **Retire runs in two steps (C-8):** met. `_plan_retire` (installer :2353-2398) and `_delete_retired` (:3256-3265):
   - **No run deletes a file whose row it removes.** Step A returns no file ops at all.
   - **Step B** deletes only files whose folded hash is in the entry's released hashes (or matches the plugin's copy), and lists an edited copy under `kept` with `kept-differs`.
   - **Refusals:** a `settings.local.json` row is refused, and so is an edited copy at step A when a row names that hook.
   - **Dangling rows** are removed by step A whether or not the file exists.
   - **angular-tailwind** is covered: `TestRetireInTwoSteps` runs both names and both row forms, and its skill and `DISABLED.md` were updated.
   - **The revert-manifest test passes:** `test_a_revert_manifest_restores_both_hooks_and_rows_and_the_leftover_notice_row_exits_0`.
   
   The step-B hash is bound into the plan hash, so a file that changes after the preview gives `changed-since-preview`. The Q7 question is in both install skills.
9. **(8a) C-7: a dispatch in the current turn reads open; the disagreement smoke cases ran with the expected outcomes:** met in code, partly-met in the record. `entry_facts` classifies an `Agent` or `Task` tool use as `subagent-dispatch`, and `read_transcript` opens the turn on it (rows T-7, CLI-5, RT-1/2). Pull request #331 records all five non-interactive disagreement cases as allowed. Re-run here at hook level: "Agent dispatch then Read" was allowed, and "mcp, then a task notification, then Read" was allowed. The interactive terminal case was not run, see W2.
10. **(9) Released hashes:** met. Every `origin/master` first-parent commit's copy of the guard, the tracker and the reset hook was folded:
    - tracker: 4 distinct hashes;
    - reset hook: 5;
    - guard: 6.
    
    Every hash is listed in `addon.json`, the 0.16.5 copies included. The head guard folds to `3109eed2…9b64`, which is listed and labelled `0.17.0`. That is the version the landing's minor raise produces from 0.16.5. The tracker and the reset hook at the head are byte-identical to `origin/master`, so they are frozen.
11. **(10) The live smoke was run and recorded; re-run any step you can:** partly-met. Pull request #331 records Claude Code 2.1.319 and CodeGraph 1.6.2, and steps A and B on a real 0.16.5 install, five agreeing cases and five disagreeing cases. The interactive case is recorded as not run (W2). I re-ran a hook-level smoke: real subprocesses of the merged guard against real transcript files, with an isolated home, an index and a configured server. All 14 cases gave the contract's outcomes (Evidence E4). I did not re-run `claude -p` sessions (What was NOT checked).
12. **(11) The report's enforced section and shadow sections are separate:** met. `codegraph_shadow_report.py` splits `all_records` into shadow-era `records` and `enforced`, and only the shadow sections read the former. `_enforced_section` counts records, reasons split main and agent, the fail-open share, blocks and retries, blocks per tool, states, routes and cost. The cap line comes from the first `log-full`. The denominator of the Q4 share is skewed, see W3.
13. **(12) Every entry in "Registry amendments at review" is appended (VOCABULARY, MECHANISMS), each checked against its cited line:** not-met. None of the 11 entries is in `.claude/registries/VOCABULARY.md` or `MECHANISMS.md` at the head: a grep for `#262`, `cut-over` and `2026-11-09` finds nothing. Pull request #331 says they are "applied at review", but this gate's write scope is the artefact and its Gate Output alone. Each cited line was checked, and each names the entry the contract says it does (W1). The drafted text is in the Disposition.

## Findings

### W1 (warning) — The contract's registry amendments are not appended. `.claude/registries/VOCABULARY.md:16,82,125,126,130,132-138,141`; `.claude/registries/MECHANISMS.md:45,89-93,107,109,111`

At the cut-over these entries now describe behaviour the code no longer has. Examples:
- V125: "written by the tracker … deleted by the reset hook".
- V126: "cleared by the next prompt".
- V130: "It still opens the gate".
- V133: "`main()` applies them after the shadow".
- V137: "reaches the tracker as a `PostToolUse` event".
- V138: "An exit 0 is counted".
- V141: "the `codegraph` reset hook's per-prompt message".
- M111: "The tracker owns it".
- M109: "`_remote_host` and `_own_spellings` have six" copies.

The cited lines are all correct. `data-architect` and `contract-critic` read these registries on every run, so a future contract built on them would design against retired hooks. The contract makes block 2's check (12) audit the whole list, and the list is not appended. The fix is in the Disposition.

### W2 (warning) — The one interactive smoke case was not run. Contract safeguard 3 and block 1's live smoke; pull request #331, "Live smoke"

Safeguard 3 says "the main session runs the one interactive case". The case is blocked, then allowed after CodeGraph, then blocked after the next typed prompt. It is the only case on the `typed` / `suggestion_accepted` prompt sources. The Uncertain Assumptions verified those sources from a transcript on disk, not from a live hook run. Pull request #331 records it as not run, with the commands to run it. That satisfies "recorded as not run" in the letter, but the safeguard names an owner (the main session), and the waiver leans on this safeguard. A misread typed prompt would turn the guard off for interactive sessions (it fails open, not closed). The 7-day report would show that only as a low block count, never as an error.

### W3 (warning) — The fail-open share (the Q4 rollback number) counts open-turn non-source reads in its denominator. `codegraph_shadow_report.py` `_enforced_section`; guard `_plan` :1184-1185, `measurement_record` :1928

Step 1 returns `transcript-open` before step 2 classifies targets, so an open-turn record keeps `target_class: "not-computed"`. The report's `gated_calls` excludes only `no-target` and `non-source-target`. So:
- in an open turn, every Read, Grep and Glob, markdown and JSON included, counts as gated;
- in an unknown state, a markdown read is `non-source-target` and is not counted.

The numerator (`fail-open:transcript-*`) is source-only, while the denominator is inflated by open-turn non-source reads. The share therefore reads low, and could stay under the 10% rollback trigger when the true share is above it.

**Fix (no decision change):** classify the targets inside the wrapped `_apply_measurement` effect, after the ticket, so it can neither block nor change output, and write the real `target_class`. Then have the report count as gated only records whose `target_class` is not `allowed`.

**Cheaper alternative:** state in the report line and in the 7-day follow-up stub that the share is a lower bound.

### N1 (nit) — A skipped line of more than 2 MB can leave the state `closed`. guard :1826-1830

If the skipped line were the assistant entry that opened the turn, the call would block on a guess. In practice a `mcp__codegraph__*`, `Bash` or `Agent` tool-use entry is small, and a 2 MB assistant entry is beyond the model's output size. The parent contract accepted the skip. A one-line hardening, if wanted: when `skipped` is non-zero in this read and the result is `closed`, answer `unknown:window-exceeded`.

### N2 (nit) — The T-7 cross-session control row was dropped. `test_codegraph_first_guard.py` around :715-725

The old T-7 asserted that "another session is still BLOCKED". The new T-7 tests the dispatch rule without that control. Cross-session isolation is still pinned by T-1 fresh, T-3 and the AC2 stranger, so the loss is small.

### N3 (nit) — The installer flag `--keep-retired-files` is not named in the contract. installer :3936-3938; both install skills

It implements Q7's "on no, apply the rest without the deletion". It gets its own plan hash, and it is tested by `test_keep_retired_files_applies_the_rest_and_leaves_step_b_out`. This is a justified divergence, and it does not need a JOURNAL entry, because the contract's Q7 text describes exactly this behaviour without naming a mechanism. It should be mentioned when the contract is closed.

## What was NOT checked

- **Real `claude -p` sessions were not re-run.** The ten non-interactive cases, and steps A and B on a real 0.16.5 install, rest on the implementer's record in pull request #331. Claude Code 2.1.322 and CodeGraph 1.6.2 are on this workstation, but a nested model session per case was outside this gate's budget. The hook-level re-run (E4) exercises the same code paths with real transcript files, though not the host's own transcript writer or its timing.
- **The interactive terminal case** (W2) was not run. A subagent cannot type prompts.
- **The reviewer-verdict log** (`~/.claude/logs/reviewer-verdicts.jsonl`) and the registry appends were not written, because the caller limited this gate's writes to the artefact and its Gate Output. The JSONL line for the caller to append: `{"ts":"2026-11-09T00:00:00Z","contract_path":"D:\\Dev\\HIPALANET\\claude-agentic-auto-improve\\.claude\\concepts\\2026-11-09-codegraph-hooks-cutover.md","divergence":false,"drift_summary":"none (the --keep-retired-files flag implements Q7 as written)","critical_count":0,"warn_count":3}`.
- **`cross_area_scan.py` / `derive_area.py`** were not run. The area mapping has no areas, so every file derives `uncategorized`.
- **The other 23 hook test files and `test_pr_merged.py`** were not run. Pull request #331 reports them as exit 0.
- **macOS and Linux** were not checked. Every run here was on Windows (`win32`), so the POSIX branches (`getuid`, `/proc`, `ps`) were read only.

## Evidence

- **E1. Range.** `git merge-base origin/master 81ee03d`, exit 0: `fb89001…`. `git log --oneline fb89001..81ee03d`, exit 0: 7 commits. `git diff --stat fb89001..81ee03d`, exit 0: 29 files, +4214/−1484.
- **E2. Suites,** run from this worktree with `PYTHONIOENCODING=utf-8 py -3 -B <file>`. The suites are plain scripts, not pytest.

  | Suite | Exit | Result |
  |---|---|---|
  | `test_codegraph_first_guard.py` | 0 | 1331 passed, 0 failed, 3 skipped |
  | `test_worktree_path_guards.py` | 0 | 190 passed of 190 |
  | `test_addons.py` | 0 | 38 tests, OK |
  | `test_codegraph_shadow.py` | 0 | 150 passed |
  | `test_auto_improve_finish_install.py` | 0 | 436 tests, OK |
  | `test_plugin_manifests.py` | 1 | 222 passed, 1 failed (see below) |
  | `test_plugin_doctor.py` (unedited) | 0 | OK, 1 skipped |
  | `test_plugin_text_scans.py` | 0 | OK |
  | `test_codegraph_shadow_report.py` | 0 | OK |

  The one failure in `test_plugin_manifests.py` is "the version obeys the merge-base rule … merge-base version 0.16.5". It is expected under the Parent Branch Delivery Rule, and the landing's raise clears it.
- **E3. Version check.** `py -3 -B .claude/scripts/check_version_bump.py --base origin/feature/262-codegraph-hooks-cutover --default-branch master --head-ref task/2026-11-09-codegraph-hooks-cutover/t2-fail-open-review`, exit 0: "sub-task pull request keeps version 0.16.5; the landing raises it". The same call with `--default-branch origin/master` exits 2 (`origin/origin/master`), because the script adds the remote prefix itself.
- **E4. Hook-level smoke re-run.** A scratch script in `%TEMP%\t2rev-scratch\smoke.py` ran the merged guard as a subprocess with an isolated HOME, LOCALAPPDATA and XDG_CACHE_HOME, a project holding `.codegraph/codegraph.db`, `.git/` and `.mcp.json` with a `codegraph` command server, and a real JSONL transcript appended between calls. Script exit 0. Each case's exit code:

  | Case | Exit | Outcome |
  |---|---|---|
  | closed Read | 2 | banner |
  | identical retry | 0 | `retry-escape-used` |
  | MCP use, then Read | 0 | silent |
  | next human prompt | 2 | blocked |
  | counted Bash | 0 | silent |
  | compound Bash | 2 | blocked |
  | Agent dispatch | 0 | silent |
  | MCP, task notification, Read | 0 | silent |
  | no `transcript_path` | 0 | `fail-open:transcript-no-transcript` |
  | malformed line | 0 | `fail-open:transcript-parse-error` |
  | README, no transcript | 0 | nothing printed |
  | subagent | 0 | `fail-open:subagent` |
  | notice row | 0 | one JSON object, 1274 bytes |
  | notice row, garbage stdin | 0 | — |

  No `.pyc` files appeared beside the guard. A first pass without `codegraph.db` gave `fail-open:no-index` on every gated call, as step 4 requires.
- **E5. Released hashes.** `%TEMP%\t2rev-scratch\hashes.py` folds each file with the installer's own `_fold_text_bytes` / `_sha256` at every `origin/master` first-parent commit. Exit 0. Every hash is `LISTED`, with no `MISSING`. The head guard folds to `3109eed2098a81b0fe39c8ae07e0af79268a3e5d4d8f0af7cd5e3c49c85d9b64`, which is listed and labelled `0.17.0`. The tracker and reset hook at the head are identical to `origin/master`.
- **E6. Block-row diff.** `%TEMP%\t2rev-scratch\blockrows.py` reads `git diff -U0 fb89001 81ee03d` of the three suites and lists removed block assertions with no identical re-add. Exit 0. It found 13 in the guard suite, 0 in the worktree suite and 0 in the add-on suite. Each of the 13 was traced by grep in the head file (check 4).
- **E7. Registries.** `grep -nE "#262|cut-over|cutover|2026-11-09"` over VOCABULARY.md and MECHANISMS.md, exit 1 (no match). Each cited line was read with `sed -n`, and each names the entry the contract cites.
- **E8. Files read:**
  - the guard: `_plan`, `apply_state`, `read_transcript`, `entry_facts`, `counted_subcommand`, the apply effects, `notice_main`, `main`;
  - the retired reset hook's `main`;
  - the installer diff (`_plan_retire`, `_retire_file_ops`, `_plan_settings_edit`'s retire splice, `_delete_retired`, the validator);
  - the report diff;
  - `addon.json`;
  - the install skills (the codegraph step-B question and the age table; angular-tailwind) and `angular-tailwind/DISABLED.md`;
  - the test diffs of `_addon_fixture.py` and `test_worktree_path_guards.py`;
  - the new installer test rows.
- **E9. Pull request.** `gh pr view 331 --json title,body,state,mergedAt,baseRefName`, exit 0: MERGED into `feature/262-codegraph-hooks-cutover` at 2026-11-10T02:20:35Z. The body holds the live-smoke record quoted above.

## Disposition

Before the landing, these steps are needed. None of them changes block 1's code:

1. **W1: append the registry amendments.** Do it on this sub-task's branch. The registry files count as shipped, and the landing's single raise covers them under the Parent Branch Delivery Rule. Each is a dated entry appended under `## Universal …`, and no earlier text is edited:
   - **VOCABULARY, Investigation Turn (amendment)** *(2026-11-09, issue #262)*: supersedes `:16`, `:125` and `:136`. A turn is the span between two human prompts in the session transcript (`human-prompt` entries). A background task notification fires the prompt event but does not end a turn. Three things open it, each counted when the main session issues the call, whether or not it succeeds: a `mcp__codegraph__*` tool use, a Counted command in the Bash tool, or an `Agent` / `Task` tool use (a subagent dispatch). This replaces the shared-folder rule of `:125`.
   - **VOCABULARY, Transcript turn state (amendment)** *(2026-11-09, #262)*: `:132` is now enforced. `codegraph-use` also covers a Bash Counted command, the class `subagent-dispatch` opens the turn, and there is a new cause, `unknown:error`.
   - **VOCABULARY, Turn marker, Shadow decision (`:134`) and Foreign marker (`:130`), retired** *(2026-11-09, #262)*: `turn.json` is neither read nor written, and the foreign-marker check is removed.
   - **VOCABULARY, Live plan (amendment)** *(2026-11-09, #262)*: `:133`. `main()` applies the effects in the C-2 order (availability, ticket, cursor, cli-fallback, notice flags and `log_event`, one Measurement record, then stderr and the exit code). There is no shadow step.
   - **VOCABULARY, Shadow record (amendment)** *(2026-11-09, #262)*: `:135`. After the cut-over it is a **Measurement record** with `outcome: enforced`, `shadow_*` equal to `live_*`, `turn_marker` null and `turn_route` set. It holds no paired decision.
   - **VOCABULARY, Retry escape (amendment)** *(2026-11-09, #262)*: `:126`. A ticket is valid only within the prompt that issued it, identified by `prompt_key` (12 hex of the SHA-256 of `prompt_id`, or `none`). No hook clears tickets at a prompt. A prompt can be shorter than a turn, so a ticket expires at a task notification.
   - **VOCABULARY, Command-line route and Counted command (amendment)** *(2026-11-09, #262)*: `:137` and `:138`. They are counted by the guard from the transcript, with the same strict test, not by a tracker `PostToolUse`. A failed attempt counts too, and the exit-0 rule is retired.
   - **VOCABULARY, Connection notice (amendment)** *(2026-11-09, #262)*: `:141`. It is printed by the guard file on its prompt row (`args: ["notice"]`), not by the reset hook.
   - **VOCABULARY, Disabled add-on hook (amendment)** *(2026-11-09, #262)*: `:82`. An install retires one in two steps (C-8) instead of refusing.
   - **MECHANISMS, CodeGraph (amendment)** *(2026-11-09, #262)*: supersedes the three-hook text of `:107` and `:111`. One hook file has two rows (`PreToolUse` on `Read|Grep|Glob`, and `UserPromptSubmit` with `notice`). The guard owns the command-line route, the cli-fallback record, the pruning and the notice. The tracker and the reset hook are Disabled add-on hooks.
   - **MECHANISMS, inline-copy parity (correction)** *(2026-11-09, #262)*: `:45` and `:109`. The disabled tracker and reset copies leave the parity set and stay frozen at their 0.16.5 bytes. `_remote_host` and `_own_spellings` now have four active copies (helper, guard, bridge, installer), `_hop_allowed` keeps four, and the Per-user session parent code has one active copy, in the guard.
   - **MECHANISMS, Disabled add-on hook (amendment)** *(2026-11-09, #262)*: `:89-93`.
     - "Enforced by" gains the install's two-step `retire` op: step A removes the rows and keeps the files; step B deletes unedited released copies and keeps edited ones.
     - The refusal `disabled-hook-present` now covers only a `settings.local.json` row and an edited copy at step A.
     - `registration` may be one row or a list.
     - The released hashes live in each entry.
     - `--keep-retired-files` leaves step B out.
2. **W2:** the main session runs the interactive terminal case (`cd $env:TEMP\cg-smoke-262\proj; claude`, then the three prompts), and records the outcome in the landing pull request. Any outcome other than blocked, allowed, blocked goes back to the user.
3. **W3:** fix the denominator as described, or state in the report line and in `.claude/concepts/followups/2026-11-09-codegraph-cutover-7-day-check.followup.md` that the share is a lower bound. Do this before the 7-day check reads the number.

When those are done, this gate releases the landing. N1, N2 and N3 are optional.
