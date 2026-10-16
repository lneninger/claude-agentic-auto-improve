## Test Strategy Review: Delivery cleanup (issue #50)

**Verdict:** pass-with-findings

**Scope.** I reviewed `test_cleanup_delivered.py` (66 tests), `test_cleanup_delivered_trials.py` (T1-T4), `TestAtRefRecordReadersAndAdvanceAlias` in `test_pr_merged.py`, `WorktreeEntriesLockedKeyTests` in `test_flat_worktree.py`, and the `PLUGIN_FIRST_VARS` carve-out in `test_skill_script_lookup.py`. I read them against `cleanup_delivered.py`, the shared fakes in `test_flat_worktree.py`, the `pr_merged.py` readers and both skill blocks.

**What I ran.** Only single classes:
- `test_cleanup_delivered.GateTests`: 5 tests, OK, 44 s, about 9 s per test.
- `test_cleanup_delivered_trials.T1HeldWorktreeRemovalTests`: OK. It recorded `returncode 255, folder_still_exists True, tracked_file_survived False, other_file_survived False, git_still_lists_it False`.

**What I could not run.** A mutation harness on a scratch copy outside the repository was blocked by `concept-gate.py`, which rejects writing any `.py` file. I did not route around the gate. Each "killed / survives" verdict below comes from reading each assertion against the code path. None of them was executed.

### Q1: the nine acceptance criteria, checked by mutation-style reading

| AC | Mutation | Killed by | Verdict |
|----|----------|-----------|---------|
| 1 | drop `git fetch` | `test_three_calls_...` (the fixture keeps the main checkout's `origin/master` stale, so call 2 would read exit 5) | killed |
| 1 | gate ignores records (`implemented` alone is enough) | `GateTests.test_implemented_at_origin_without_a_completion_record...` | killed |
| 1 | read the contract and records from the working tree | `GateTests.test_a_flip_that_exists_only_in_the_working_tree...` | killed |
| 1 | the skill passes `--from` after the `cd`, so `$PWD` is the main root | nothing (only needle tests) | **survives**, see F4 |
| 2 | push `--delete` without a fresh `ls-remote` | `test_a_branch_github_already_deleted...` (no push names it) | killed; but the `already-gone` reading is optional, see F10 |
| 2 | ignore `remove-remote` | `test_off_by_default...` | killed |
| 2 | drop the open pull request check, or treat a `gh` failure as "none open" | `test_..._open_pull_request`, `test_gh_unavailable...` | killed |
| 2 | drop the remote ancestor check | `test_a_remote_branch_whose_tip_is_not_in_origin_master...` | killed |
| 3 | skip link removal | `children` snapshot of the wrapper at `worktree remove`, plus `len(links) >= 2` | killed; the target-survival assertion is probably not what kills it, see F11 |
| 3 | remove links before the checks | `test_a_dirty_worktree_is_left_with_its_links_in_place`, `test_a_deferred_standing_tree_keeps_its_links` | killed |
| 3 | junction-blind detection (`os.path.islink`) | top-level `children` check | killed on Windows 3.12 only; the code before 3.12 is never run, see F14 |
| 4 | drop the dirty check, or the untracked check | `UnsafeTreeTests` (asserts the reason) | killed. Real git also refuses, so this is defence in depth |
| 4 | drop the worktree HEAD ancestor check | `test_..._unpushed_commit...` (`assertKept`) | killed. Real `git worktree remove` would succeed here, so this test is load-bearing |
| 4 | drop the nested-worktree check | `test_an_ignored_folder_that_is_itself_a_git_worktree...` | killed |
| 4 | file names missing from the printed line | `assertIn("src/feature.txt", line)` | killed |
| 5 | drop the local ancestor check | `LocalBranchTests.test_a_branch_whose_tip_is_not_in_origin_master...` | killed. The ordering assertion in the `-D` test would **not** kill it, see F15 |
| 6 | `-d` instead of `-D` | `test_a_merged_branch_is_deleted_with_capital_d...` | killed |
| 6 | drop `checked-out` or `protected-name` | `test_an_owned_branch_held_by_the_main_checkout...`, `ProtectedNameTests` | killed |
| 7 | ownership by `-task-` folder name | `test_a_sibling_items_worktrees...` (`-2` sibling kept) | killed |
| 7 | drop the ambiguity check | `test_an_advance_worktree_whose_name_fits_two_contracts...` | killed |
| 7 | sibling whose slug is a **prefix** of ours, with its contract not yet at `origin/master` | nothing | **gap, and the code removes it**, see F2 |
| 7 | drop the landing exclusion or the lock check | `test_the_main_checkout_and_a_landing_worktree...`, `test_a_locked_worktree...` | killed |
| 8 | wrong shape, a reason missing, cap or `+k more` | `ReportLineTests` | killed. The cap is not tested together with a finish line, and control characters are not tested on Windows, see F8 and F9 |
| 9 | drop the standing check (`CLAUDE_PROJECT_DIR`, cwd, `--from`) | `StandingTreeTests` (4 entry points) | killed |
| 9 | ignore the halt | `test_a_probe_that_cannot_rename_back...` (a later `branch -D` appears) | killed (Windows) |

### Critical

None. No high-stakes invariant was found where the suite passes on a broken implementation and real git would not catch it either.

### High

- **F1: `remove-failed` is modelled as a clean failure, but the host fails destructively.** Wrapper `git` (`FAKE_GIT_CODE`) and the tests `test_when_git_worktree_remove_fails...` and `IsolationTests`.
  - **Gap:** the wrapper exits 1 *before* real git runs, so the tree stays whole and registered. T1, which I ran on this host, shows the real shape of a remove that fails: every file is deleted, the worktree is **deregistered**, and an empty held folder is left behind.
  - **Why it matters:** this is the documented race between the probe and the removal (contract Failure Modes: "the report names the leftover folder"). After a T1-shaped failure, the next call's `plan_worktrees` no longer sees the folder, so it is never reported again. The owned branch is no longer "held" and is deleted in the same run. None of this is pinned.
  - **Fix:** add a wrapper mode that runs the real removal while a holder process stands in the tree, or that empties and deregisters it and then exits 255. Assert:
    - the item is `remove-failed` and names the leftover path;
    - the branch outcome is what the contract intends;
    - what call 2 reports.

- **F2: no test covers an in-flight sibling whose slug is a prefix of ours.** `OwnershipTests`. Production code: `plan_worktrees`, `other_slugs`.
  - **Gap:** `_is_advance_worktree("…-advance-2026-10-15-demo", "2026-10-15-demo-feature")` is True, because the folder name may be a prefix of the slug. The ambiguity guard only knows the slugs **at `origin/master`**. A sibling contract `2026-10-15-demo` that is not yet on master has a full-name advance worktree. That worktree is detached, clean and at an ancestor of master, so it is planned as ours and removed.
  - **Why it matters:** this is AC7, "never touched". The rename probe cannot see a sibling session's Git Bash (T3), so the only protection left is that session's lock, if it has one.
  - **Fix:** add the negative test: the sibling contract exists only on its branch, and its advance worktree must survive. It fails today. The fix is a contract question: should a prefix-only match require exact equality, or should the slugs on every remote branch count as well? **Escalate to the user. Do not patch it silently.**

- **F3: the fallback through recorded pull request heads (INV-2 step 2) cannot be reached under the fake `gh`.** `BriefLookupTests` and `FAKE_GH_CODE`.
  - **Gap:** `gh_pr(url)` passes an `https://…/pull/41` URL. The fake's `pr view` only accepts an all-digit argument, so the fake always answers "no such pull request". The suite exercises only the starting branch. Replacing `pr = pr_merged.gh_pr(url)` with `pr = None` passes every test.
  - **Why it matters:** when the session starts from the main checkout and the contract has no header, this is the only path to the brief. A regression there leaves the brief's branch and worktree un-owned, so AC1 ("no worktree left") fails silently.
  - **Fix:** teach the fake `pr view` to accept a URL (`pull/(\d+)`), and seed `pr_view` with `headRefName`. Add a test that starts from the main checkout, with no header and a recorded head, and expects the feature worktree and branch to be owned. Add a positive control that the fake answered the URL form.

- **F4: the skill command that carries the standing-tree layer is never executed.** `SkillWiringTests`.
  - **Gap:** the tests only check that `--from`, `--contract` and `CLN` appear in Step 6 and in `/advance`.
  - **Why it matters:** the session's own tree is protected only if `START="$PWD"` is captured **before** `cd "$(… --print-main-root)"` and `--from "$START"` is passed. The probe cannot replace that layer, because T3 showed it is blind to Git Bash. A regression to `--from "$PWD"` after the `cd` passes every test and lets the session's own worktree be removed under it, which is the #469 failure.
  - **Fix:** extend the `test_skill_script_lookup` snippet runner to execute the full Step 6 and `/advance` blocks from inside a real linked worktree. `$CLN` should be a stub that records its argv and cwd. Assert that the `--print-main-root` call ran from the worktree, and that the cleanup call ran from the main root with `--from` equal to the worktree.

### Medium

- **F5: the fake `gh` silently swallows unexpected commands, and no test checks the `gh` call log.** `FAKE_GH_CODE`, where `fail("unexpected command")` exits 1.
  - **Gap:** a mutation that deletes a branch through `gh api -X DELETE …/git/refs/heads/<b>`, or that runs `gh pr close`, gets exit 1. The script records it as a failure, and every test still passes. The fake performs no write, so `remote_heads` is unchanged.
  - **Fix:** in `CleanupCase`, assert after every run that `tools.gh_calls()` holds only `pr list` and `pr view`. Make the fake exit with a distinctive code on unexpected commands.

- **F6: the INV-5 runtime check runs in only one happy-path test.** `test_a_full_run_never_prunes_forces_or_switches_a_tree`.
  - **Gap:** the failure paths (`remove-failed`, `link-not-removed`, halt, `delete-failed`) are exactly where a "retry with force" or "fall back to prune" would be added, and no test checks those runs for `prune`, `--force` or `switch`.
  - **Gap (source scan, Q4):** the scan is not the INV-5 list.
    - It has no `switch` or `checkout`, and no `rm -rf`.
    - It misses `getattr(shutil, "rmtree")`, because only the NAME token is flagged and the string is not.
    - It misses a hand-written `os.rmdir`/`os.remove` recursion.
    - It misses `"--for" + "ce"`.
    - It scans only `cleanup_delivered.py`, not the modules it calls.
  - **Fix:**
    - Run the "no prune, no force, no switch or checkout, no `-f`" check over `git_calls()` in a `CleanupCase` cleanup hook, so all ~55 world tests enforce it.
    - Add `switch`, `checkout` and `rm -rf` to the scan, and flag the string `"rmtree"`.
    - Treat the scan as a tripwire, not a proof. The runtime log is the proof for git commands, and `assertKept` after every failure path is the proof for Python-level deletion (F7).

- **F7: the `remove-failed` tests never assert that the folder and its files are intact.** `test_when_git_worktree_remove_fails...` and `IsolationTests` check only the reason and the detail.
  - **Gap:** a "fall back to a recursive delete" mutation passes both.
  - **Fix:** add `assertKept` and a file check to both, together with F1's real-shape variant.

- **F8: the 600-character cap is never tested together with a finish line, and the code diverges there.**
  - **Gap:** `build_line` returns `line if finish else line[:LINE_LIMIT]`, so a deferred run with long paths can exceed 600, which breaks INV-8's "never". `test_a_long_report_is_capped...` has no deferred item.
  - **Fix:** add an in-process unit of `build_line`: 12 left items, one deferred, a long main root. Flag the divergence to `fullstack-code-reviewer`.

- **F9: the control-character test is skipped on the only host that runs the suite.** `@skipIf(IS_WINDOWS)`.
  - **Gap:** `_clean` is pure, yet it is tested only through a POSIX file name.
  - **Fix:** add an in-process unit: `build_line` / `_left_entry` with a synthetic item whose name and files carry `\x1b`, `\x07` and `\n`. Keep the POSIX end-to-end test.

- **F10: the `already-gone` reading is optional.** `test_a_branch_github_already_deleted…` uses `pick(..., required=False)`.
  - **Gap:** INV-7 names the reading `already-gone`. An implementation that drops the item passes.
  - **Fix:** require the item, since the code emits it when the local branch existed. Add the case where the local branch is also gone, and pin whether an item is expected there.

- **F11: the "target survived" assertion may be vacuous on this host.** `DirectoryLinkTests`.
  - **Gap:** if Git for Windows' `git worktree remove` treats a junction as a link and does not recurse into it, the targets survive even when the junction is never removed first. In that case the top-level `children` snapshot is the only real guard of "link first". A deep link (`src/deep/node_modules`) is guarded only by the implementation's own `links[].removed` report.
  - **Fix:** add trial T5, which runs `git worktree remove` on a tree that holds a junction and records whether the target survives. Make the wrapper record a **recursive** lstat scan for links at remove time, and assert it is empty.

- **F12: the finish command is checked with the test's own parser and never run.** `assertDeferredWithOneFinishLine`.
  - **Gap:** `shell_words` mirrors the implementation's `'\''` rule, so a quoting bug the two share passes. "Exactly one finish line" is tested with one deferred item only.
  - **Fix:**
    - Run `finish_command` once through Git Bash, after the holder leaves, and assert the tree is removed. That is AC9's "one script line" proven end to end.
    - Add a run with two deferred trees and assert one `finish:`.

- **F14: the detection before 3.12 is pinned only by a grep of the source.** `LinkDetectionSourceTests`.
  - **Gap:** `assertIn("lstat", text)` and `assertIn("FILE_ATTRIBUTE_REPARSE_POINT", text)` read the raw text, comments included (line 129 already holds "os.lstat" in a comment). The host runs Python 3.12.10, so the code path before 3.12 never runs.
  - **Fix:** read `code_tokens`, not raw text. Add a behaviour test that hides `os.path.isjunction` and asserts `_is_link` still flags a junction. If CI exists, add a 3.11 leg.

### Low / Nit

- **F13 (Q3): the fetch-test fix is sound, but weaker than it needs to be.**
  - **What is sound:** reading `state()` before breaking origin, and comparing only `worktree_paths` afterwards, avoids the `ls-remote` crash.
  - **What it drops:** the local-branch map and the folder listings. `mutating_calls` still covers branch deletion through git, but not Python-level changes (link removal, a probe rename that is left behind). The test also never asserts *which* unverifiable path fired, so the `origin/HEAD`-unreadable reason would satisfy it too.
  - **Better:** `git remote set-url origin <real origin>` after the run, then the full `assertUntouched(before, main_before, …)`, plus `assertTrue(reasons[0].startswith("git fetch origin master failed"))`.
- **F15:** the ordering check in `test_a_merged_branch_is_deleted_with_capital_d…` accepts any earlier `merge-base … origin/master`, including the worktree checks, so it would not catch a missing branch check. Bind it to the branch's tip sha.
- **F16:** the skill text regexes are weak: `(?i)every` and `\b5\b` match "Step 5". After F4 they become redundant.
- **F17:** the in-use test uses `time.sleep(1.0)` and `sleep(0.5)` for synchronisation. A process holds its cwd from creation, so the first sleep is unnecessary. If a wait is needed, use a marker file, as T3 does.
- **F18:** these branches have no test: `ls-remote` failing (remote `unverifiable`), `merge-base` exit codes other than 0 or 1, a folder that is missing but still listed, local `delete-failed`, and `origin/HEAD` unreadable.
- **F19:** `CommandLineTests.test_no_arguments_is_a_usage_error_exit_2` builds a full world it never uses.
- **F20:** `test_skill_script_lookup`'s world is a plain folder. "Never the main checkout's copy" is therefore indistinguishable from "the current folder's copy". F4's real-worktree runner would cover it.
- **Not findings:**
  - `TestAtRefRecordReadersAndAdvanceAlias` is strong: negative tests against the working tree, parity with `load_records` / `load_delivery`, the unreadable case, and the prefix-alias case.
  - `WorktreeEntriesLockedKeyTests` has a real control (an unlocked sibling) and tests injection of a lock reason. No change needed.
  - T1 asserting only that it ran is what the contract asks for. It is a record, not protection, and its result should drive F1.

### Q2: what the fakes do not model

- **Wrapper `git`:**
  - It fails *before* real git runs, so there is never a partial delete or a deregistration (F1).
  - It snapshots only the top-level children (F11).
  - It adds a Python launcher process to every git call (runtime, Q5).
  - Real git runs underneath, so git's own refusals (dirty, locked, checked-out) are real. That is good.
- **Fake `gh`:**
  - `pr view` by URL always fails (F3).
  - Unexpected or writing commands exit 1 and are not flagged (F5).
  - `--state` is ignored (harmless here, because `gh pr list` defaults to open).
  - `--limit` and pagination are not modelled.
  - There is no failure on a single branch only: `gh` either fails for all branches or for none.
  - The repository being asked (`GH_REPO`, forks) is not modelled.

### Q5: a cheaper structure that loses nothing (about 7 min, about 9 s per world test)

1. **Snapshot-restore at a fixed path.** Build each world shape once per class into a template. Before each test, copy it back to the **same** absolute path (copy2 keeps mtimes), so the worktree `gitdir` links stay valid. Run `git update-index --refresh` on the main checkout so `snapshot()` index bytes are stable. Expected effect: world build drops from seconds to a few hundred ms. Fidelity is unchanged.
2. **Move the pure logic in-process**, with no world: `build_line` caps and `+k`, control characters (F9), the cap with a finish line (F8), `_quote` / `finish_command`, and the scanner. Keep one end-to-end shape test (`test_every_item_left_carries…`). `test_a_long_report_is_capped…`, the 12-task world and the heaviest fixture, becomes a unit test plus that one end-to-end assertion.
3. **Measure the wrapper overhead, then log calls through `GIT_TRACE2_EVENT`** (set explicitly; `clean_env` strips `GIT_*`). Keep the Python wrapper only for the roughly 4 tests that inject failures or need the `children` snapshot. Trace2 nests child processes, so filter on the top-level `start` events.
4. **Run the modules in parallel.** The worlds are independent temp roots.

Do not merge the four standing-tree entry points into dry runs. That would couple the tests to where `--dry-run` branches in the code.

### Recommended test-suite shape

- Keep the real-git, bare-origin world tests for the destructive paths (they are the right boundary).
- Add:
  - a T1-shaped failure injection (F1);
  - the in-flight sibling with a prefix slug (F2);
  - URL-capable `gh pr view` (F3);
  - one executed skill block per front door (F4).
- Make the git/`gh` call-log invariants per-test (F5, F6).
- Move about 6 line and quoting cases to in-process units (F8, F9).
- Restore worlds from snapshots (Q5) to cut runtime by several times with no loss of fidelity.

### HANDOFF
- **Status:** needs-fixes (pass-with-findings)
- **Files reviewed:** D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261015-feature-50-auto-cleanup-delivered-worktrees\.claude\scripts\tests\test_cleanup_delivered.py; …\tests\test_cleanup_delivered_trials.py; …\tests\test_pr_merged.py (TestAtRefRecordReadersAndAdvanceAlias); …\tests\test_flat_worktree.py (WorktreeEntriesLockedKeyTests, Tools, FAKE_GH_CODE); …\tests\test_skill_script_lookup.py; …\.claude\scripts\cleanup_delivered.py; skills\pr-merged\SKILL.md Step 6; skills\advance\SKILL.md
- **Critical findings:** none
- **Contract alignment:** aligned with the TASK-block cases [1]-[9]. Partial on INV-2 step 2 (F3) and INV-8's "never longer than 600" (F8). F2 is a contract-level gap to escalate.
- **Recommended suite shape:** as above.
- **Warnings:**
  - The fake `gh` hides writes and can never answer `pr view` by URL.
  - The `remove-failed` fault injection does not match the observed host behaviour.
  - The INV-5 runtime check runs only on the happy path.
  - The control-character test never runs on Windows.
  - The mutation verdicts are by reading only, because `concept-gate.py` blocked the scratch harness.
- **Context for next agent:** F1-F12 above. F2 needs a user decision before any test is frozen.
- **Recommended next:** senior-test-engineer, with F2 going to the user first.
- **Suggested input for next agent:**
  TASK: Add F1 (T1-shaped remove failure), F3 (URL `pr view` in the fake `gh` plus a recorded-head fallback test), F4 (execute the Step 6 and /advance blocks from a real worktree with a stub `$CLN`), F5/F6 (per-test git and `gh` call-log invariants), F7, F8, F9, F10, F11 (recursive link snapshot plus trial T5), F12. Write the F2 negative test as `expectedFailure`, pending the user's decision.
  FILES: .claude/scripts/tests/test_cleanup_delivered.py, test_cleanup_delivered_trials.py, test_flat_worktree.py (FAKE_GH_CODE), test_skill_script_lookup.py
  FOCUS: INV-2 (ownership, brief fallback), INV-3/INV-9 (the remove-failed shape), INV-5 (on every path), INV-6 (the skill-level `--from`), INV-8 (cap with finish).

```yaml
findings:
  - id: F1
    severity: Breaking
    file: .claude/scripts/tests/test_cleanup_delivered.py:98 (FAKE_GIT_CODE)
    description: The remove failure is injected before real git runs; the host (T1) empties and deregisters the tree instead.
    proposed_feedback_rule:
      name: feedback_fault_injection_matches_observed_host_failure.md
      body: |
        Inject a failure in the shape a host trial recorded, never as a clean failure before the command runs.
        **Why:** #50 T1 showed `git worktree remove` deletes every file and deregisters the tree before it fails; the wrapper's clean exit 1 hid that orphaning path.
        **How to apply:** when a trial records a host failure, add a fault mode that reproduces it and assert both the report and the next call's behaviour.
  - id: F2
    severity: Breaking
    file: .claude/scripts/cleanup_delivered.py:517 (plan_worktrees advance-name rule)
    description: A sibling whose slug is a prefix of ours, with its contract not at origin/master, has its advance worktree claimed and removed; no test covers it.
    proposed_feedback_rule:
      name: feedback_name_based_ownership_needs_inflight_negative_test.md
      body: |
        Any ownership rule that matches by name needs a negative test with an in-flight sibling, one whose records are not on the default branch yet.
        **Why:** #50's ambiguity guard reads only slugs at origin/master, so a prefix-slug sibling still on its branch is treated as ours.
        **How to apply:** for every by-name match, add a sibling that shares the prefix and exists only on its branch; assert it survives.
  - id: F3
    severity: Soft
    file: .claude/scripts/tests/test_flat_worktree.py:207 (fake gh pr view)
    description: The fake gh cannot answer pr view by URL, so the recorded-head brief fallback is unreachable and a mutation of it survives.
    proposed_feedback_rule:
      name: feedback_fake_must_reach_every_contract_path.md
      body: |
        A fake must be able to answer every call form the code under test makes, proven by a positive control.
        **Why:** #50's fake gh accepted only numeric pr view arguments, while gh_pr passes URLs, so INV-2 step 2 was never exercised.
        **How to apply:** for each contract-required path that depends on a fake, assert in one test that the fake returned a real answer, not its failure branch.
  - id: F4
    severity: Breaking
    file: .claude/scripts/tests/test_cleanup_delivered.py:637 (SkillWiringTests)
    description: The skill command that carries --from "$START" before the cd is checked only by needles, never executed.
    proposed_feedback_rule:
      name: feedback_execute_skill_command_blocks.md
      body: |
        A skill block whose argument order carries a safety property is executed in a test, not grepped.
        **Why:** #50's standing-tree layer depends on START being captured before cd; a needle test passes a regression that removes the session's own tree.
        **How to apply:** run the fenced block with a stub script that records its argv and cwd, from a real worktree; assert the values.
  - id: F5
    severity: Soft
    file: .claude/scripts/tests/test_flat_worktree.py:241
    description: The fake gh exits 1 on unexpected commands, and no test checks the gh call log, so writes through gh are invisible.
    proposed_feedback_rule:
      name: feedback_fakes_fail_loud_on_unexpected_commands.md
      body: |
        A fake executable records unexpected commands, and every test asserts that the allow list of calls held.
        **Why:** #50's fake gh swallowed unknown commands as a plain failure; a `gh api -X DELETE` would pass every test.
        **How to apply:** in the shared base case, assert after each run that gh_calls() holds only the read commands the contract allows.
  - id: F6
    severity: Soft
    file: .claude/scripts/tests/test_cleanup_delivered.py:596, 1499
    description: The INV-5 runtime check runs on one happy run only; the source scan covers a subset of INV-5 and can be evaded.
    proposed_feedback_rule:
      name: feedback_destructive_invariants_checked_in_every_test.md
      body: |
        A "never run X" invariant is asserted over the call log of every test in the suite, not one, and a source scan's token list equals the invariant's list.
        **Why:** #50's failure paths, where a force or prune fallback would be added, were never checked; the scan missed switch, checkout, rm -rf and string-form rmtree.
        **How to apply:** put the call-log assertion in the base case's cleanup; derive the scan tokens from the invariant text.
  - id: F7
    severity: Soft
    file: .claude/scripts/tests/test_cleanup_delivered.py:845, 1400
    description: The remove-failed tests do not assert that the folder and its files are kept.
    no_rule_needed:
      reason: Falls under F1's proposed rule (fault injection asserts the full post-failure state), and is fixed in the same change; there is no separate bug class.
  - id: F8
    severity: Soft
    file: .claude/scripts/cleanup_delivered.py:648
    description: The 600-character cap is skipped when a finish line is present, and no test combines cap and finish.
    no_rule_needed:
      reason: Already covered by journal lesson "A size budget must bound the summary it adds, not only the items it keeps"; the test simply did not apply it to the finish suffix.
      existing_rule: .claude/registries/JOURNAL.md (2026-10-05 size budget entry)
  - id: F9
    severity: Soft
    file: .claude/scripts/tests/test_cleanup_delivered.py:1242
    description: Control-character stripping is tested only on POSIX; the dev host is Windows.
    proposed_feedback_rule:
      name: feedback_pure_logic_tests_run_on_every_host.md
      body: |
        Pure text logic is tested in-process with synthetic input, so a platform skip never removes its only test.
        **Why:** #50's control-character test needs a file name Windows cannot hold, so it never ran where the suite runs.
        **How to apply:** when a test is platform-skipped only because of its fixture, add a unit of the pure function beside it.
  - id: F10
    severity: Soft
    file: .claude/scripts/tests/test_cleanup_delivered.py:746
    description: The already-gone reading is optional (required=False), although INV-7 names it.
    no_rule_needed:
      reason: A leniency left from the RED phase, when the item's presence was unknown; the implementation now settles it, so the fix is to make it required, and no recurring class remains.
  - id: F11
    severity: Soft
    file: .claude/scripts/tests/test_cleanup_delivered.py:811
    description: Target survival may hold even without junction-first ordering, if git does not recurse into junctions; a deep link is guarded only by the implementation's self-report.
    no_rule_needed:
      reason: Covered by the existing trial-first lesson; the fix is trial T5 recording git's junction behaviour.
      existing_rule: .claude/registries/JOURNAL.md (2026-10-05 "prove the cap with a real trial")
  - id: F12
    severity: Soft
    file: .claude/scripts/tests/test_cleanup_delivered.py:1265
    description: The finish command is parsed by a test-owned mirror of the quoting and never executed; there is no case with two deferred trees.
    no_rule_needed:
      reason: Covered by the journal lesson "Do not rely on a host expanding a variable in a form nobody has seen work"; the fix is one real Git Bash run.
      existing_rule: .claude/registries/JOURNAL.md (2026-10-04 host-expansion entry)
  - id: F13
    severity: Safe
    file: .claude/scripts/tests/test_cleanup_delivered.py:1452
    description: The fetch-failure test compares only worktree paths after breaking origin and never asserts which unverifiable reason fired.
    no_rule_needed:
      reason: A one-test repair after the test broke its own oracle (ls-remote against the URL it broke); restoring the URL before the full comparison fixes it, and the class is specific to tests that sabotage the remote they compare against.
  - id: F14
    severity: Soft
    file: .claude/scripts/tests/test_cleanup_delivered.py:896
    description: Junction detection before 3.12 is pinned by a raw-text grep that comments satisfy; it never runs behaviourally on the 3.12 host.
    no_rule_needed:
      reason: Covered by the existing journal lesson that a parser or VERIFIED claim needs a test that can fail; fix by scanning code tokens and hiding os.path.isjunction in a behaviour test.
      existing_rule: .claude/registries/JOURNAL.md (2026-10-04 "A VERIFIED parser claim must be tested")
  - id: F15-F20
    severity: Safe
    file: see report Low section
    description: A weak ordering bind, weak skill regexes, sleeps, untested minor branches, an unused world, a plain-folder lookup world.
    no_rule_needed:
      reason: Each is a local tightening of an existing test with no shared root cause; F4 and F6 above absorb the two that could recur.
```
