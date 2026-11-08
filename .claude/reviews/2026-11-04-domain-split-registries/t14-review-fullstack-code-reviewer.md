# t14 review — fullstack-code-reviewer

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t14-review (issue #306, parent issue #235)
- **Contract:** `.claude/concepts/2026-11-04-domain-split-registries.md` (approved, amendments 5 and 6)
- **Supersedes:** .claude/reviews/2026-11-04-domain-split-registries/t11-review-fullstack-code-reviewer.md
- **Reviewed on:** 2026-11-07
- **Commit range reviewed:** `43e802c..eb9502d` (parent branch `fix/235-domain-split-registries`, from the merge of pull request #299 (t11) to the merge of pull request #312 (t13)).
- **First-parent commits in the range:** amendment 5 `ce961fb` (#302), the briefs for sub-tasks 12-14 `b863596` (a direct commit), amendment 6 `59d4800` (#308), **t12 `090f24d` (#309)** and **t13 `eb9502d` (#312)**.
- **Merges of origin/master inside t12, each read with `git show --remerge-diff`:**
  - `8558879`: parents `b863596` (the parent tip) and `28f0b18` (origin/master). Its base is `9a1b452a`. It hand-resolved 8 files.
  - `22cc333`: parents `8cfa2c0` and `88f4d32` (origin/master). Its base is `28f0b18`. Git merged it automatically, and its remerge-diff is empty.

**Verdict:** pass-with-findings

## What was checked

Each item is on one line. The outcome comes first, then the evidence.

- **The t12 merge commits have two parents, one from origin/master, and #309 was merged with a merge commit.** Met.
  - `8558879` has parents `b863596` and `28f0b18`. `22cc333` has parents `8cfa2c0` and `88f4d32`. `090f24d` (the #309 merge) has parents `59d4800` and `a77fa02`.
  - `git merge-base origin/master origin/fix/235-domain-split-registries` prints `88f4d32`, not `9a1b452a`.
  - Block 13's Run-first outputs are in #312's description: merge base `88f4d32`, three hashes for `090f24d`, and `--is-ancestor` exit 0.
- **Rule (0) held.** Met here, partly met in #309 (see W1).
  - I wrote my own Base-line check (a temporary script, outside the repository) and ran it per merge with that merge's own base and parent tip.
  - On `skills/design-first/SKILL.md` and `MECHANISMS.md`: 0 surviving base lines for `8558879` and 0 for `22cc333`.
  - On all seven united paths: 0 for each merge.
  - A reverse check (lines either side added that the merge lost) finds exactly one line: the default branch's 2026-11-05 "CodeGraph (amendment)" entry, which Q22 folds on purpose.
  - #309's description states "0 surviving" as a ticked line, but pastes no output.
- **D1-D5 and J1-J5 adapter rows exist and pass; memory_boundary binds `registry_files_in` through `_bind`.** Met.
  - `AdapterDifferenceTests` has one row each for D1-D5 and J1-J5, plus the legacy-kind row and the keys row. `test_registry_entries.py`: 36 tests OK.
  - `memory_boundary.py:62` reads `_RL = _bind("_registry_layout", "registry_files_in")`.
  - The hidden-module row and the amendment-6 stand-in row both pass (`test_memory_boundary.py`, 117 tests OK).
- **The 8 files follow block 12's per-file rules.** Met.
  - (1) The hook is the parent's thin wrapper. It has no regex and no `parse_entries`; the only addition is amendment 6's `is_journal` reader-missing branch.
  - (2) The digest is the parent's body plus three lines only: `entry_blocks`, `journal_entries` and `BULLET`, re-exported from `rl`. `DOMAINS`, `tier_split`, `read` and `entries` are absent.
  - (3) MECHANISMS.md is on layout 2. All five default-branch entries and Correction lines are byte-identical to `28f0b18` (Memory adapter, its 2026-11-03 Correction, both CodeGraph corrections, Add-on layout amendment, and the "Addendum 3 item 14" Correction under Two-layer resolution). They sit above `## Project tier` (line 124).
  - Q22 is exact: `MECHANISMS.md:107` equals `"  - **Correction (2026-11-05, issue #259):** "` followed by the default branch's text after the separator. It is the last indented line of the 2026-10-30 entry, and no top-level copy remains.
  - (4) VOCABULARY.md is on layout 2. The default branch's added lines lost: 0. The pointer is at line 152.
  - (5) Every JOURNAL.md entry is above the pointer (line 529).
  - (6) Both scan suites keep both sides' tests: lost lines 0, base lines surviving 0, `test_plugin_text_scans.py` 30 OK, `test_skill_script_lookup.py` 32 OK. The rule-(6) fix in `skills/auto-improve-finish-install/SKILL.md` (`20d1a80`) names the three `general.md` skeletons.
  - (7)/(8) The skills keep both sides. design-first has Step 1.5 "Consult the Central Memory System" (line 50) and "Run the data-architect's registry appends" (line 109). verify-before-done runs Steps 5.5, 5.6 and 5.8 in order.
- **Q21 (a): one grammar.** Met.
  - `git grep` for dated or bold-bullet regexes in production `.py` files outside `_registry_layout.py` finds only two hits. Both are in `memory_boundary.py` (`DATE_RE` at :97 and a Correction-date search at :565), and both came unchanged from the default branch (`28f0b18`). Neither parses a heading or an entry bullet.
  - `accuracy_update.parse_journal_entries` uses `rl.source_value`, and `_SOURCE_VALUE` is deleted. `journal_entries` uses `source_value`.
  - `memory_boundary._registry_files` lists files through `registry_files_in`. `JOURNAL/ops.md` is read (`test_a_domain_file_outside_the_old_domain_list_is_read`). `DOMAINS` and `DEFAULT_DOMAINS` are gone.
  - `EntryBlocksTests`, `JournalEntriesTests` and the `BULLETS`/`JOURNAL` fixtures are byte-identical to `28f0b18` (AST comparison).
  - The `TierSplitIsByteIdentical` deletion is justified in #309 under "Notes for the reviewer".
- **t11 W1 fixed.** Met.
  - `process_journal_change` checks the `_registry_layout` import before `_load_seen()`. When the import fails, it writes one stderr line, logs `journal-tracker-reader-missing` and returns `[]`.
  - The new test asserts (d2) no cache file, (d1) a byte-identical old-reader cache, the log event, and (d3) `{"reader": 2}` with zero fires. The (d3) zero-fires assertion is vacuous (N1), but (d1) and (d2) pin the regression.
- **t11 N2.** Met.
  - `README.md:1550-1552` has the contract's sentence word for word.
  - `MECHANISMS.md:116` holds `  - **Correction (2026-11-07, t11 review N2):** …`. That is the `registry_append.py --correction-of` shape, and the entry line itself is unchanged.
- **All five 2026-11-07 lessons appended.** Met.
  - `JOURNAL.md:494`, `:501`, `:508`, `:515` and `:522`, all Universal.
  - (1) and (2) have Trigger `post-impl divergence`; (3)-(5) have `pre-approval critic`. Every one names this contract as its source, and (1) is the t11 text verbatim.
- **No version file was edited by hand.** Met.
  - The four manifests changed in the range only through the `090f24d` merge. No non-merge commit in `88f4d32..eb9502d` touches them, and neither remerge-diff lists them.
  - `git diff 88f4d32 eb9502d` over the manifests is empty, and so is the diff against origin/master (0.16.3).
  - `check_version_bump.py` in parent mode exits 0 ("keeps version 0.16.3").
- **Every t11 "Met" item still holds.** Met.
  - Line 1 of all three roots is the layout-2 marker, and `--check` gives `current`.
  - The three skeletons are `cmp`-identical to the templates.
  - `skills/ship/SKILL.md` has an empty diff over the range.
  - All 14 t11 suites exit 0.
  - The lint gives R4 advisories, one R3 skip line (22 entries now, against 11 at t11: the merge brought the default branch's Universal entries) and `digest: absent`. There is no layout advisory line.
  - The doctor reports `current` and 0 body-less entries.
- **Amendment 6, rule (9) folds.** Met, exact.
  - `MECHANISMS.md:121` is the 2026-11-06 issue-271 text, prefixed exactly as the rule says. It is the last indented line of the 2026-11-05 "CodeGraph (correction)" entry, and no top-level copy remains.
  - `VOCABULARY.md:140` is the column-0 line with exactly two leading spaces added. It is the last indented line of "Investigation Turn (amendment)", and no column-0 copy remains.
  - I checked both against `88f4d32` with a script.
- **Amendment 6: stand-ins only for the closed list.** Met.
  - `_claude_paths.py:119-120` binds `getattr(...) or _missing_helper_function(name)` for `registry_files` and `registry_files_in` only.
  - `checkout_equivalent_path`, `PROJECT_HOOK_LAUNCHER_SOURCE`, `HOOK_CLASS_BLOCK` and `HOOK_CLASS_WARN` stay bare reads (:121, :232-236).
  - Both names are in `__all__`.
  - `def checkout_equivalent_path` is at line 486 of the helper in both `643b667` and `e4f392c`.
- **Amendment 6: frozen-helper, CLI, hook and Q-hop rows.** Met. All pass and none skipped (the commit is present).
  - Case 13 has 13 PASS rows (frozen helper ×6, CLI ×3, hook ×4).
  - `test_codegraph_first_guard.py` passes 1390, fails 0 and skips 3. The 3 skips are POSIX-only rows Q-3, Q-9 and T-M1, which are unrelated.
  - Both named Q-hop rows (`0.15.2 helper (e4f392c)`: binds; `older helper (643b667)`: "the bridge imports beside that helper" with TREE_HOP_REFUSAL False) pass. The file equals `88f4d32`'s copy.
  - The CLI row pins exit 2, not the contract's exit 1 (N2).
- **The tracker hook logs `journal-tracker-reader-missing`.** Met. The case 13 hook row counts exactly one event, and no cache file is written.
- **Every t12 merge of origin/master read with `--remerge-diff`, each with its own Base-line check.** Met here, partly met in #309 (W1).
  - `8558879` shows exactly the 8 conflicting files resolved per rule. `22cc333` shows nothing.
  - My Base-line output for each merge is in Evidence.
- **`test_plugin_manifests.py` fails exactly one row.** Met.
  - 191 passed and 1 failed. The failing row is "the version obeys the merge-base rule: tree differs from the merge base (0.16.3), so all five declarations exceed it".
  - That is the owner-accepted exception, not a finding. No gate runs this suite, and no other row is red.
- **Off-area drift.** Nothing to compare.
  - `derive_area.py` returns `uncategorized`, because the area map is empty.
  - Every file the t12/t13 non-merge commits touch is on block 12's or block 13's Files to touch. The one exception is the brief bookkeeping in `a77fa02`.
  - The merge resolutions touch only the 8 listed files.
- **Last check: the landing merge is clean.** Met. `merge-tree` against origin/master `a241f5c` exits 0, lists no conflicting path, and gives tree `ba683c3`. origin/master moved past `88f4d32` by three docs-only paths: two orchestrator result files and one work-item brief.

## Findings

### W1 (warning) — #309's description states the required outputs instead of pasting them. Record: pull request #309

Block 12 told the implementer to paste several raw outputs in the pull request. #309's description gives only ticked summary lines for these:

- the Base-line check output for each merge commit;
- the head-proof outputs;
- for each conflicting file, what each side added since `9a1b452a`;
- the three VOCABULARY rule-(4) comparisons;
- the rule-(9) lines, quoted;
- the `checkout_equivalent_path` re-check output;
- the `merge-tree --name-only` output;
- the default-branch test files with their exits;
- the `registry_append` printed file:line.

It also marks its older-test search "spot checks, not exhaustive", and question (5) (`ThisRepositoryTests`) has no grep at all. #309 has no comments that carry these.

The substance holds. I re-ran each check independently (Evidence: Base-line check on all seven paths per merge, the fold checks, the closed-list check, the manifest diffs, and all suites). Nothing in the code needs to change.

The risk is the record. A later reader of #309 cannot tell a verified check from an asserted one, and the next merge block, if any, will copy the summary style. Fix: none for this contract, because this report now holds the outputs. For future merge blocks, see the proposed rule in Disposition.

### N1 (nit) — The W1 test's (d3) "zero fires" assertion would pass even with the t11 bug. `.claude/hooks/tests/test_journal_post_approval_tracker.py:368-374`

`self.general` is `"# Journal - general\n\n> header\n"` (`Project.__init__`, :98). It holds no entry, so no historical `post-impl divergence` entry exists that a wrongly seeded cache could re-fire.

(d1) and (d2) still catch the t11 regression on their own: the buggy path writes the cache, so "no cache file" and "byte-identical" fail. But the contract's "the later healthy run fires zero" is not shown by (d3).

Fix: before the first degraded run, write one `entry("Historical", "post-impl divergence", self.p.contract, date="2026-01-01")` into `self.general`. Then (d3) reproduces t11's own probe, where the historical entry fired once.

### N2 (nit) — Two block-12 claims do not match the code, and no amendment has recorded that. Contract, block 12, "Bridge" and "Run"

1. **The CLI exit code.** Block 12 says that `validate_registries` beside an older helper stops "with an uncaught ImportError: traceback, exit 1". In fact, the script's `__main__` wrapper catches the error, prints `[validate-registries] error: _claude_paths: registry_files_in() …` (the remedy is named) and exits 2.
   - The case 13 CLI row pins exit 2. The pull request and a test comment both say so.
   - My probe confirmed that the contract's text does hold for `generate_registry_digest.py` and `cross_area_scan.py`: exit 1, the last line an ImportError that names the remedy, and no AttributeError.
2. **The "single definitions" grep cannot pass as worded.** `land_contract.py:578` and `memory_boundary.py:720` define `_atomic_write`, and both came from the default branch (`9a1b452a` and `28f0b18`).

#309 asked for "a later amendment or block 13" to fix these. Block 13 did not touch them. Neither is a code defect, but the contract text is now wrong, and `/pr-merged` and later contracts read it. Fix: a one-line clarification at the landing or in a later amendment. A journal lesson is proposed in Disposition.

### N3 (nit) — The hidden-module row never runs the `lister is None` branch. `.claude/scripts/tests/test_memory_boundary.py:1279-1298`

With `sys.modules['_registry_layout'] = None`, `generate_registry_digest` cannot import either, because it imports `_registry_layout as rl` at the top. So `_GRD`'s readers are None, and `select_candidates` refuses at `memory_boundary.py:550-551` before it calls `_registry_files`.

The `lister is None` branch (:503-505), which block 12 keeps "for a missing module", is never reached by a test. The refusal code is the same (`reader-unavailable`), so callers see no difference.

Fix, if wanted: one row that sets `mb._RL['registry_files_in'] = None` and leaves the module present. Alternatively, accept the branch as defensive dead code.

## What was NOT checked

- I did not run `registry_migrate.py --apply` or `--dry-run`, because the tree is `current` and the task did not ask for it.
- I ran the digest generator live (exit 0). It wrote `.claude/.scout-cache/registry-digest.md`, which is gitignored (`.gitignore:33`). I removed that folder afterwards, so the worktree holds only this artefact and its Gate Output.
- I did not probe `north_star_review.py` and `registry_append.py` beside the older helper. I probed only `generate_registry_digest.py`, `cross_area_scan.py` and `validate_registries.py`.
- I did not ask the owner whether the merge method of #309 was chosen deliberately. The two-parent `090f24d` and the moved merge base prove the outcome.
- `tools/sync-plugin.ps1` and `tools/SYNC.md` are out of scope by contract.
- I did not run the landing. Its command is below.

## Evidence

All commands were run from the worktree root on Windows (Git Bash), using `py -3` with `PYTHONIOENCODING=utf-8`. The suites ran one at a time, never concurrently. Scratch scripts lived under `C:\Temp\t14\`, outside the repository.

| Command | Exit | Result |
|---|---|---|
| `git log --first-parent --oneline 43e802c..HEAD` | 0 | `eb9502d` #312, `090f24d` #309, `59d4800` #308, `b863596`, `ce961fb` #302 |
| `git rev-list --parents -n 1` / `git log -1 --format='%H %P'` on `8558879`, `22cc333`, `090f24d`, `eb9502d` | 0 | `8558879 b863596 28f0b18`; `22cc333 8cfa2c0 88f4d32`; `090f24d 59d4800 a77fa02`; `eb9502d 090f24d 5b69bf1` |
| `git merge-base b863596 28f0b18`; `git merge-base 8cfa2c0 88f4d32` | 0 | `9a1b452a`; `28f0b18` (each merge's own base) |
| `git merge-base origin/master origin/fix/235-domain-split-registries` | 0 | `88f4d32` (not `9a1b452a`) |
| `git show --remerge-diff 8558879` | 0 | 8 files: the tracker hook, MECHANISMS, VOCABULARY, the digest, both scan tests, both skills |
| `git show --remerge-diff 22cc333` | 0 | empty (automatic merge) |
| `gh pr view 309` / `gh pr view 312` (`body`, `comments`) | 0 | both MERGED into `fix/235-…`; #309 line 1 holds the owner merge-method sentence; no comments on either |
| Base-line check `baseline_check.py <repo> 9a1b452a 28f0b18 b863596 8558879` on design-first and MECHANISMS | 0 | 0 and 0 surviving |
| Base-line check `baseline_check.py <repo> 28f0b18 88f4d32 8cfa2c0 22cc333` on design-first and MECHANISMS | 0 | 0 and 0 surviving |
| Base-line check, both merges, all seven united paths | 0 | TOTAL 0 for each merge |
| Lost-lines check (added by a side, missing after the merge), both merges | 0 | one line only: the Q22-folded 2026-11-05 "CodeGraph (amendment)" |
| `check_folds.py <repo> 88f4d32` (Q22 and rule (9)) | 0 | ALL OK (MECHANISMS:107 under the 2026-10-30 entry; :121 under the 2026-11-05 correction; VOCABULARY:140 under Investigation Turn (amendment)) |
| `class_cmp.py` / `const_cmp.py` against `28f0b18:test_registry_entries.py` | 0 | `EntryBlocksTests`, `JournalEntriesTests`, `BULLETS`, `JOURNAL` IDENTICAL |
| `git show 643b667:.claude/hooks/_project_paths.py` / `e4f392c:…` grep `def checkout_equivalent_path` | 0 | line 486 in both |
| `git grep -nF 'd{4}-'` and `'\*\*('` in `*.py`, excluding tests and `_registry_layout.py` | 0 | `memory_boundary.py:97,565` (from the default branch, not heading or bullet grammar); `pr_merged.py` brief fields (unrelated) |
| `git grep -n -e "def _atomic_write" -e "def _plan_digest" -e "def _separate_plugin_root" -- .claude/scripts` | 0 | `_preview_apply.py`, `_plugin_root.py`, plus `land_contract.py:578` and `memory_boundary.py:720` from the default branch (N2) |
| `py -3 .claude/scripts/tests/test_preview_apply.py` | 0 | 15 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_root.py` | 0 | 8 tests OK |
| `py -3 .claude/scripts/tests/test_registry_layout.py` | 0 | 83 tests OK |
| `py -3 .claude/scripts/tests/test_script_path_resolution.py` (×2) | 0 | 206 passed, 0 failed; case 13: 13 PASS, no SKIP |
| `py -3 .claude/scripts/tests/test_registry_append.py` | 0 | 29 tests OK |
| `py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py` | 0 | 18 tests OK |
| `py -3 .claude/scripts/tests/test_registry_readers.py` | 0 | 13 tests OK |
| `py -3 .claude/scripts/tests/test_registry_migrate.py` | 0 | 40 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_doctor.py` | 0 | 209 tests OK (1 skipped) |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 0 | 30 tests OK |
| `py -3 .claude/scripts/tests/test_skill_script_lookup.py` | 0 | 32 tests OK |
| `py -3 .claude/scripts/tests/test_auto_improve_finish_install.py` | 0 | 408 tests OK |
| `py -3 .claude/scripts/tests/test_check_version_bump.py` | 0 | 46 tests OK |
| `py -3 .claude/scripts/tests/test_validate_registries_default.py` | 0 | 7 tests OK |
| `py -3 .claude/scripts/tests/test_registry_entries.py` | 0 | 36 tests OK |
| `py -3 .claude/scripts/tests/test_memory_boundary.py` | 0 | 117 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_manifests.py` | 1 | 191 passed, 1 failed: only INV-O1 "the version obeys the merge-base rule: tree differs from the merge base (0.16.3), so all five declarations exceed it" (owner-accepted, amendment 6) |
| `py -3 .claude/hooks/tests/test_addons.py` | 0 | 33 tests OK |
| `py -3 .claude/hooks/tests/test_codegraph_first_guard.py` (×2) | 0 | 1390 passed, 0 failed, 3 skipped (POSIX-only Q-3, Q-9, T-M1); all 12 Q-hop rows PASS |
| `py -3 .claude/hooks/tests/test_codegraph_shadow.py` | 0 | 118 passed, 0 failed |
| `py -3 .claude/hooks/tests/test_main_checkout_guard.py` | 0 | 57 tests OK |
| `py -3 .claude/hooks/tests/test_working_agreements.py` | 0 | 133 passed |
| `py -3 .claude/hooks/tests/test_worktree_path_guards.py` | 0 | 190 passed |
| `py -3 .claude/scripts/tests/test_agent_skill_preloads.py` | 0 | 9 tests OK |
| `py -3 .claude/scripts/tests/test_cloud_text_scans.py` | 0 | 11 tests OK |
| `py -3 .claude/scripts/tests/test_codegraph_session_parent_docs.py` | 0 | 27 tests OK |
| `py -3 .claude/scripts/tests/test_codegraph_shadow_report.py` | 0 | 31 tests OK |
| `py -3 .claude/scripts/tests/test_installed_plugin_root.py` | 0 | 18 tests OK |
| `py -3 .claude/scripts/tests/test_memory_off_parity.py` | 0 | 28 tests OK |
| `py -3 .claude/scripts/tests/test_parent_branch_rule_text.py` | 0 | 41 tests OK |
| `py -3 .claude/scripts/tests/test_pr_merged.py` | 0 | 761 tests OK |
| `py -3 .claude/scripts/registry_migrate.py --check --project .` | 0 | `state: current`, `marker: 2`, `reasons: []` |
| `py -3 .claude/scripts/validate_registries.py --check-structure --project .` | 0 | 33 R4 advisories, `advisory: R3 universal-candidate skipped: 22 entries; …`, `digest: absent`; no R1, R2, R3, R5, A1 or layout line |
| `py -3 .claude/scripts/validate_registries.py --check-structure --strict --project .` | 1 | R4 counts under `--strict`, as specified |
| `py -3 .claude/scripts/generate_registry_digest.py` | 0 | 234 entries, 0 bad references, 0 R1/R2 (the output was removed afterwards) |
| `py -3 .claude/scripts/validate_registries.py --check-structure --project .` with the digest present | 0 | the `digest:` line is gone; only R4 and the R3 skip line remain |
| `py -3 .claude/scripts/plugin_doctor.py --project .` | 0 | `registry layout: current`, `body-less journal entries: 0` |
| `py -3 .claude/scripts/plugin_doctor.py --project . --json` | 0 | `registry_layout.state = current`, `bodyless_journal_entries = 0` |
| `py -3 .claude/scripts/check_version_bump.py --base origin/fix/235-domain-split-registries --default-branch master --head-ref task/2026-11-04-domain-split-registries/t14-review` | 0 | "sub-task pull request keeps version 0.16.3; the landing raises it" |
| `git diff 88f4d32 eb9502d -- plugin.json .claude-plugin .cursor-plugin`; same against `origin/master` | 0 | empty; empty (0.16.3 on both) |
| `git log --oneline --no-merges 88f4d32..eb9502d -- plugin.json .claude-plugin .cursor-plugin` | 0 | empty (no hand edit) |
| `git diff --stat 43e802c..eb9502d -- skills/ship/SKILL.md` | 0 | empty |
| `head -1` of the three roots; `cmp` of the three skeletons against the templates | 0 | the layout-2 marker on each; identical |
| `py -3 .claude/scripts/derive_area.py .claude/concepts/2026-11-04-domain-split-registries.md` | 0 | `uncategorized` |
| `older_probe.py` (scripts beside the `643b667` helper, sandbox outside the repository, deleted afterwards) | 0 | digest exit 1 and cross_area_scan exit 1, each with a last-line ImportError naming the remedy; validate_registries exit 2, wrapped message naming the remedy; no AttributeError |
| **Last check**, run live after every other check: `git fetch origin ; git merge-tree --write-tree --name-only origin/master origin/fix/235-domain-split-registries` | 0 | origin/master `a241f5c01c8a`, parent `eb9502d05c89`, tree `ba683c32d309`, no conflicting path (2026-11-07T20:18:38Z). origin/master moved past `88f4d32` by docs-only paths |

**Version proof at the landing.** The version proof is the landing's own `check_version_bump.py --raise`, then `--exact` (gate P7b), and its version-bump verification step. It is not a re-run of `test_plugin_manifests.py` after the landing: the merge base is then the head itself, so INV-O1 passes trivially. The operator reads the landing report's raise and exact outcomes. Each must exit 0, and the raised version must be origin/master's version with the minor raised by one and the patch reset to 0 (today 0.16.3 → 0.17.0).

**Landing command for the operator (I did not run it).** Just before launching, re-run the last check above (`git fetch origin ; git merge-tree --write-tree --name-only origin/master origin/fix/235-domain-split-registries`, exit 0, no conflicting path). Then, in Claude Code:

```
/advance 2026-11-04-domain-split-registries
```

It launches `py -3 .claude/scripts/land_contract.py --contract 2026-11-04-domain-split-registries --json` in the background.

## Disposition

- **Pass with findings.** Sub-task 12's two merges keep both sides with no surviving base line and no lost line. Q21 (a), Q22 and rule (9) are exact, and amendment 6's bridge, hook and memory-adapter changes behave as specified. Sub-task 13 closes t11 W1 and N2 and appends all five lessons. Every suite is green apart from the one owner-accepted row, and the landing merge is clean against origin/master `a241f5c`. Nothing blocks the landing.
- **W1** is about the record only. This report now carries the outputs that #309 asserted. No code change is needed.
- **N1, N2, N3** are optional. N1 and N3 are each a few lines in a test file. N2 is contract text. If any are taken, batch them with the landing's version raise or file them as follow-ups of issue #235.
- **Registry janitor.** No new mechanism or term in `43e802c..eb9502d`.
  - The adapters (`entry_blocks`, `journal_entries`, `source_value`) are recorded under "Memory adapter" (the Correction at `MECHANISMS.md:119`).
  - The bridge stand-in is internal to "Two-layer Claude path resolution".
  - INTEGRATION.md does not apply: there is no REST, SignalR or DTO surface.
  - This task may write only this artefact and its Gate Output, so the lesson below is proposed, not appended. If wanted, the landing appends it with `registry_append.py --registry journal --universal`, batched with the version raise:

  ```markdown
  ### 2026-11-07 — A merge block's pull request must paste each required output, not tick a line that says it passed
  - **Trigger:** post-impl divergence
  - **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
  - **Lesson:** When a contract block says "paste the output in the pull request" (Base-line checks, side-by-side comparisons, older-test greps), the description must carry the raw output per item; a ticked summary turns a verified check into an asserted one, and the reviewer must redo every check. Likewise, when the implementer finds that the contract mis-predicts the code (an exit code, a grep that cannot pass), the next block or an amendment must fix the text, not only the pull request note.
  - **Apply when:** a contract block lists evidence to paste in a pull request, or a pull request records "the contract's wording does not match the code".
  - **Tags:** evidence, pull-request, merge-block, contract-text, review
  ```
