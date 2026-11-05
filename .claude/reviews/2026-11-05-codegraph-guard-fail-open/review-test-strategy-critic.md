## Test Strategy Review: issue #259, the codegraph guard fails open (contract 2026-11-05-codegraph-guard-fail-open)

**Reviewer:** test-strategy-critic
**Date:** 2026-11-05
**Tree:** worktree `20261105-bug-259-codegraph-guard-fail-open`, branch `fix/259-codegraph-guard-fail-open`, nothing committed
**Verdict:** NEEDS FIXES (1 blocker, 5 warnings, 8 nits)

### What I ran (one suite at a time, exit codes read)

| Suite | Result | Wall time |
|---|---|---|
| `py -3 .claude/hooks/tests/test_codegraph_first_guard.py` | 258 passed, 0 failed, 0 skipped, exit 0 | 55 s |
| `py -3 .claude/hooks/tests/test_worktree_path_guards.py` | 188 passed, 0 failed, exit 0 (C-pre, C11, C12, C12 twin, C13 present) | 59 s |
| `py -3 .claude/hooks/tests/test_addons.py` | 27 OK, no skip (the baseline commit 643b667 was available) | 13 s |
| `py -3 -m unittest` on the 7 new installer classes only | 26 OK | 8 s |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 19 OK | 2 s |
| `py -3 .claude/scripts/tests/test_plugin_manifests.py` | 190 passed | 5 s |

Leak check, done by hand. Before and after the guard suite I listed the real temp folder (`C:\Users\lneni\AppData\Local\Temp`). The run added no `auto-improve-codegraph-*`, `cg*-` or `addon-*` entry. The two new entries were from other processes (`rv259-*`, `prm_wt_*`). `~/.claude/logs` was unchanged (newest file dated 2026-11-04). The thirteen `wtguard-*` folders in the real temp folder date from 2026-09-28. They are older than this change and are not caused by it.

I did not run full `unittest discover`, as instructed, so `test_skill_script_lookup.py` (the `/verify-before-done` lookup block) was not run by me. I did not execute any mutation. Every mutation verdict below comes from reading the guard, the reset hook and the tests.

---

### Critical (BLOCKER)

- **B1. The privilege-free pruner swap tests (X-2, X-3, X-4) still pass when the whole per-file re-check is deleted. Only X-6 catches that mutation, and X-6 is the row that skips on machines without the symlink privilege.** `.claude/hooks/tests/test_codegraph_first_guard.py:941-980` (X-4), `:910-926` (X-2), `:928-939` (X-3); production `codegraph-turn-reset.py:170-202`.
  **Gap:** `_remove_folder` iterates `os.listdir` order. On NTFS that order is sorted, so the first file is `availability.json`. The seam fires before that first file.
  - **X-4** swaps the folder for a junction to `x4-target`, which holds only `turn.json` and `precious.txt` (`:945`). Delete the re-check block (`:180-190`) and `os.remove(<link>/availability.json)` raises `FileNotFoundError`. "Any failure keeps the rest" then returns before `turn.json` is reached. The target survives and X-4 passes.
  - **X-2** (a known file swapped for a same-named folder) passes without the re-check because `os.remove` refuses a directory.
  - **X-3** (a known file renamed) passes because the removal hits `FileNotFoundError`.
  - Only **X-6** (a file symlink) fails under the mutation: the symlink is unlinked, the remaining files go, the folder is removed, and `folder.is_dir()` fails. X-6 is exactly the row the contract lets skip with `file symlink refused by the OS`.

  The contract added X-4 because it "needs no privilege, so it runs even where `os.symlink` on a file is refused" (FM, pruner bullets). As built, it does not test the clause it exists for.
  **Why it matters:** I-5's per-file re-check is the only defence against deleting through a swapped junction in a shared temp folder. On a Windows machine without Developer Mode (a common case), the suite stays green with that defence removed. On this workstation X-6 ran (0 skipped), so the mutation is caught here only.
  **Fix:**
  - In X-4, fill the link target with every name in `KNOWN`, as X-5 already does at `:986-988`, so the first removal would hit a real file. Assert that every one of them survives.
  - Alternatively, make the seam swap only when `Path(p).name == "turn.json"`, and plant `turn.json` in the target.
  - For X-2 and X-3, either accept them as OS-guarded defence in depth and say so in the row name, or have the seam act on the last file in `sorted(KNOWN)`. Then a missing re-check would already have deleted the earlier files and dropped the folder, and the row would fail.

### High (WARN)

- **W1. T-1 and the add-on tracker test pass through the retry escape, not the marker.** `test_codegraph_first_guard.py:552-571`; `test_addons.py:321-334`.
  **Gap:** Both tests make a blocked call (which issues a ticket for that exact fingerprint), run the tracker, then repeat the identical Read in the same session and assert only `allowed(after)` / `rc == 0`. If the guard ignored `turn.json` entirely (step 2 deleted), the repeat is allowed by step 6 (`retry-escape-used`) and both tests stay green. The tracker half is still proven by the `turn.json` body check. The "the guard then allows the Read" half is not.
  **Why it matters:** These rows are the stated proof of acceptance criterion 8 ("explore, a legacy name and a future name all create the marker" that opens the gate). Today step 2 is covered elsewhere (T-3, C5, C6, C11, `test_the_marker_survives_a_directory_change`, the first control in `test_the_reset_removes_the_marker…`), so this is a misleading assertion rather than an open hole.
  **Fix:** Use a fresh session for the "before" control, or assert that `after.stderr` has no `allowed (` line (turn-marker-present prints nothing, while retry-escape-used does).

- **W2. T-6, "a subagent shares the parent's marker", passes because of `agent_id`, not because of the marker.** `test_codegraph_first_guard.py:614-621`.
  **Gap:** The payload carries `agent_id`, so step 3 allows it whatever the marker state, and `allowed(sub)` checks no reason. Delete the marker write, or key the subagent's folder on `agent_id`, and T-6 still passes. The verified live fact this row claims to pin (a subagent carries the parent's `session_id`, so the folder is shared) has no discriminating test. Nothing runs the tracker with a subagent payload (agent_id plus the parent's session_id) and then the parent's Read either. That is the direction where sharing matters, because the parent has no step-3 escape.
  **Fix:**
  - In T-6, assert that the stderr does NOT contain `fail-open:subagent`. Step 2 runs before step 3, so the shared marker must win.
  - Add T-7: the tracker with `{session_id: parent, agent_id, agent_type}`, then the parent's Read with no `agent_id`, gives an allow with no `allowed (` line.

- **W3. The guard's inline copy of the walk, and the bridge's inline copy, are not pinned to the helper. The contract requires that parity test.** `test_codegraph_first_guard.py:819-828` runs `af.own_root_cases` against `_project_paths.worktree_own_root` only. `codegraph-first-guard.py:351-379` (`_inline_own_root`) and `_claude_paths.py:114-144` (`_inline_worktree_own_root`) are third and second copies with no unit rows.
  **Gap:** The contract says "the guard uses an inline copy of the same walk, pinned to the helper by a parity test". The TASK block lists "the guard's inline walk vs `_project_paths.worktree_own_root`" as a required parity test. The fallback-mode O-1 and C13 rows exercise the inline walk only through end-to-end verdicts, on the happy layouts. The `(None, None)` for unreadable, the `(F, None)` for no `gitdir:` line, and the nearest-existing-ancestor rows never reach either copy.
  **Why it matters:** The three copies are byte-identical today. The first edit to one of them drifts silently, and the drift surfaces only under Guard fallback mode or beside an older helper, which are exactly the configurations nobody runs by hand.
  **Fix:** Load the installed guard with `importlib` and run `af.own_root_cases(guard._inline_own_root, …)`. Do the same for `_claude_paths._inline_worktree_own_root`. Also compare all three on the same inputs. This is three lines; the case generator already exists.

- **W4. I-4 ("an internal error allows, exit 0") is tested only on the explicit JSON-decode branch, never on the catch-all.** `test_codegraph_first_guard.py:485-487`.
  **Gap:** `raw="{not json"` is handled by `main()`'s own `except json.JSONDecodeError` (`codegraph-first-guard.py:895-897`). Deleting the top-level `except Exception` (`:923-925`) keeps I-4 green. An exception inside `evaluate` (for example in `availability`, or in `_server_state_at` on a hostile settings file) would then exit 1 with a traceback. Nothing tests that path, nor step 7's `fail-open:state-unwritable` when the ticket write fails.
  **Fix:** Add an in-process row that patches `guard.availability` to raise and runs `guard.main()` with a stdin stub, or a subprocess row whose payload makes a helper raise. Assert exit 0 and the `internal error (failing open)` line.

- **W5. No assertion that the real temp folder is untouched. The isolation holds by construction only.** All three suites.
  **Gap:** The contract's FM 1 moved the guard's state into the system temp folder, and the round-5 NIT showed an in-process row already leaked a ticket once. Task G snapshots the real home logs. Nothing snapshots `tempfile.gettempdir()` (the process's real one) for `auto-improve-codegraph-*` before and after. I checked it by hand for one run and found it clean, but a future row that forgets `isolated_env` / `codegraph_env`, or calls `guard.decide` before `tempfile.tempdir` is set, would leak silently.
  **Fix:** In the `run()` finally of `test_codegraph_first_guard.py` and in `test_worktree_path_guards.main`, snapshot the real temp folder's `auto-improve-codegraph-*` names at start and end, and fail on any new entry. This mirrors task G.

### Medium / Low (NIT)

- **N1.** E-3 (`:503-504`) and `test_addons.py:424` match `"retry" in stderr`. The `fail-open:state-unwritable` notice also contains "retry" ("cannot record a retry"), so a wrong-reason allow would match. E-3b's log-event count rescues the guard suite, but the add-on test has no rescue. Match `retry-escape-used`.
- **N2.** I-2 (`:279-286`) checks `cat\s` and "through the shell". The contract also names `sed`. Add it to the needle list.
- **N3.** P-1 server parity (`:725-728`) compares one boolean. `disabled` and `not-configured` collapse, so a guard that swaps the two reasons passes parity. Compare the guard's reason against the installer's state string.
- **N4.** `load_hook` (`:95`) patches `mod.sentinel_exists`, which no longer exists. It is dead, implementation-coupled residue that suggests the in-process rows are stubbed when they are not. Delete it.
- **N5.** `find_prune` / `call_prune` (`:841-857`) pick the pruner by reflection: the first callable with "prune" in its name, with the parameters matched by regex. A future `_prune_helper` sorts first and is called instead. The contract named the seam, so call `mod.prune_session_folders(tmp, before_remove=…)` directly and fail loudly if it is missing.
- **N6.** The availability cache is keyed per distinct cwd, but no row changes cwd from a no-index tree to an indexed one inside a session and expects a block. A "cache the index verdict once per session" regression would pass every row. This is low risk because it fails toward reading, but the cache is an explicit Data Shape.
- **N7.** `test_addons.py` `test_the_manifest_lists_the_released_hash…` calls `skipTest` when `git show 643b667:…` fails (a shallow clone), so on a shallow CI checkout the only check of the released-hash content silently disappears. It also checks only the latest release, not "every committed version since the add-on was created". Say in the skip reason that it needs full history, or pin the hashes as literals.
- **N8.** Duplication of coverage: `test_addons.py` `CodegraphAddonTests` re-tests no-index, no server, disabled, subagent, retry and reset, which the guard suite already covers on the full Read/Grep/Glob x .cs/.ts matrix. Keep the add-on suite to what only it proves (the installed hook works with its manifest's helpers, with no fallback banner) plus one fail-open and one block. That would save about 6 s and one place to update per wording change.

### Answers to the caller's specific questions

1. **Positive controls really block.** They do. I-1 (non-git, undecidable, main), the R-1 twins, R-1c with the decoy plus the db, O-1 own-index (bound mode), O-3 in all three helper modes, O-4 (server only under main, both layouts, all modes), and C1/C2/C7/C9/C12-twin/C13 all block. The sandboxes sit in `C:\Users\lneni\AppData\Local\Temp`, inside the home folder, whose `C:\Users\lneni\.codegraph` has no `codegraph.db` (I checked). So the live decoy is exercised on this machine, and R-1c covers it synthetically elsewhere. `clean_above` / C-pre fail loudly if a real index sits above a fixture.
2. **Payload shapes.** The main-session payloads carry neither `agent_id` nor `agent_type`. The subagent rows (R-4) carry both, and an empty `agent_id` is a blocked control. The parent-`session_id` sharing has no discriminating test (W2). The payloads omit `transcript_path`, `tool_use_id` and `permission_mode`. The guard reads none of them, and the fingerprint uses `tool_input` only, so the omission is harmless.
3. **Mutations** (by reading, not executed):

   | Mutation | Caught by |
   |---|---|
   | allow everything | K-4 control, R-1/R-1c twins, R-3b, R-4 controls, I-1, E-1/E-2/E-4/E-5, T-1 control, T-3 control, O-1/O-3/O-4, P-1, C1/C2/C7/C8/C9/C12-twin/C13, the add-on blocks |
   | block everything | every `allowed(proc, reason)` row (R-1..R-4, step 0, O-1 index-other-tree, O-2), E-3, T-3, C3/C4/C5/C6/C10/C11/C12 |
   | ignore the ticket | E-3 / E-3b, the add-on retry test |
   | never consume the ticket | E-4 |
   | key the ticket on cwd or the project | E-5 |
   | ignore the marker | T-3, C5, C6, C11, the add-on directory-change and reset tests. NOT T-1, NOT T-6, NOT the add-on tracker test (W1, W2) |
   | key the marker on cwd | T-3, C11, the add-on directory-change test |
   | key the marker on CLAUDE_PROJECT_DIR | T-3's "another session is BLOCKED" control |
   | delete the pruner's per-file re-check | X-6 only, which skips without the privilege (B1) |
   | delete the top-level fail-open catch | nothing (W4) |
   | any `.codegraph` counts as an index | R-1c, the add-on decoy test, P-2 decoy |
   | drop the main-checkout server candidate | O-4 |
   | inline walk drifts from the helper | only end-to-end, on happy layouts (W3) |
4. **Task G and the other guards' rows.** `base_env` is unchanged. `run_hook` switches to `codegraph_env` only for `codegraph-*` file names. The task G snapshot code is untouched in the diff. The concept-gate, bash-gate and db-destructive-guard rows still run with the real home. The 188/188 run includes their positive controls. Not weakened.
5. **Isolation and cleanup.**
   - Sandboxes are removed with links unlinked first, and the run's final check fails on any leftover.
   - `isolated_env` strips `CLAUDE_*` / `GIT_*` and sets HOME, USERPROFILE, CLAUDE_CONFIG_DIR, TMP, TEMP and TMPDIR.
   - The in-process #612 rows set `tempfile.tempdir` (addendum 3 met).
   - The junction and symlink rows call `skip(...)` with a reason when the OS refuses. The X-6 message matches the contract text.
   - The real-temp check exists only by hand (W5).
6. **Flakiness.**
   - No sleeps.
   - Session ids are `uuid4` and the sandbox names come from `mkdtemp`.
   - Ages are fixed offsets (1, 10 and 30 days against 7), so no clock races.
   - Every row builds its own fixture or session, so nothing depends on order. C12 mutates the shared `repo` index and restores it in a `finally`.
   - X-4 depends on `listdir` order: it behaves differently on POSIX, where the order is not sorted (part of B1).
7. **Gaps against the contract and the brief.**
   - Criteria 1, 3, 4, 5, 6, 7, 8 and 9 have behaviour tests.
   - Criterion 2's Edit half rests on the `Read|Grep|Glob` matcher pins in `test_plugin_manifests.py:805` and `test_auto_improve_finish_install.py:221`, which is acceptable.
   - Criterion 10's `/verify-before-done` half is skill text plus the lookup test, which I did not run.
   - Criterion 12 (docs) has no test, which is acceptable.
   - Contract items missing: the inline-walk parity test (W3), and a discriminating subagent-shares-the-parent's-folder test (W2).
   - Step 0's "owned by another POSIX user" and "not writable" branches have no rows. Both are platform-bound and low value.
8. **Size and run time.** The guard suite takes 55 s and the path-guards suite 59 s. Each subprocess launch is about 0.2 s, and the O-1 matrix (12 fixtures x 3 modes) plus P-2 accounts for about 60 launches. That is acceptable for a script tier, but it is the integration tier: none of it is a sub-second unit tier. No single row exceeds the 60 s subprocess timeout.

### Recommended test-suite shape

- Keep the subprocess matrix in `test_codegraph_first_guard.py` as the integration tier. It is valuable and the controls are real.
- Fix B1 with one change to the X-4 target, and W1/W2 with assertion changes of 2 to 3 lines each.
- Add one in-process unit block of about 15 rows:
  - the three walk copies against `own_root_cases` (W3);
  - the catch-all fail-open (W4);
  - the cwd-keyed cache (N6).
- Add a real-temp snapshot at the end of the guard suite and the path-guards suite (W5).
- Trim `CodegraphAddonTests` to install-specific rows (N8).

### Verdict

NEEDS FIXES. The positive controls are real and most mutations are caught. The pruner's privilege-free swap test does not bite (B1). Three "allowed" assertions pass for the wrong reason, or test a contract item that has no discriminating test (W1, W2, W3).
