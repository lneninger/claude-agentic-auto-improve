# t16 review — fullstack-code-reviewer

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t16-review (issue #320, parent issue #235)
- **Contract:** `.claude/concepts/2026-11-04-domain-split-registries.md` (approved, amendments 7, 8 and 9)
- **Supersedes:** .claude/reviews/2026-11-04-domain-split-registries/t14-review-fullstack-code-reviewer.md
- **Reviewed on:** 2026-11-09
- **Commit range reviewed:** `82bfe5e..ccd006f` (parent branch `fix/235-domain-split-registries`). `82bfe5e` is the parent tip t15 was cut from after its fast-forward first step (it holds amendment 8). `ccd006f` is the merge of pull request #321 (t15).
- **First-parent commits in the range:** amendment 9 `0dbf087` (a direct commit to the parent branch, a contract-only change like t14's `b863596`) and **t15 `ccd006f` (#321)**.
- **The t15 branch inside #321:** merge `6fdaf25` → journal appends `a74a52b` → rule (7') fold `02e581b` → brief bookkeeping `ad081c7`.
- **The one t15 merge of origin/master, read with `git show --remerge-diff`:**
  - `6fdaf25`: parents `82bfe5e` (the parent tip) and `67a4a14` (origin/master). Its own base is `88f4d32`. It hand-resolved 3 files.

**Verdict:** pass-with-findings

## What was checked

Each item is on one line. The outcome comes first, then the evidence.

- **The t15 merge commit has two parents, one from origin/master, and #321 was merged with a merge commit.** Met.
  - `6fdaf25` has parents `82bfe5e` and `67a4a14`. `ccd006f` (the #321 merge) has parents `0dbf087` and `ad081c7`.
  - `git merge-base origin/master origin/fix/235-domain-split-registries` prints `67a4a14` (the merged origin/master commit), not `88f4d32`.
  - #321's first line is the owner merge-method sentence.
- **The remerge-diff shows only MECHANISMS.md, VOCABULARY.md and skills/verify-before-done/SKILL.md resolved.** Met.
  - `git show --remerge-diff --stat 6fdaf25` lists exactly those three paths (9 insertions, 19 deletions). Each hunk only removes the conflict markers and orders the two sides; in the skill it also drops the parent's old Step 5.8 heading.
  - JOURNAL.md changed only through the auto-merge (the default branch's entries, all above the pointer, so no rule (5') commit was needed and none exists) and through the separate journal-append commit `a74a52b`.
  - MECHANISMS.md and VOCABULARY.md are changed once more, by the separate rule (7') fold commit `02e581b` (3 insertions, 3 deletions). That is not a resolution.
  - All three commits are listed in #321's "Commits" section.
- **The skill keeps both sides (rule (6')).** Met.
  - At `ccd006f`: `git grep -c -F "## Step 5.6: Registry structure lint"` prints 1, and `git grep -c -F "## Step 5.8: The codegraph add-on's settings and hook freshness check"` prints 1 (line 262).
  - The old heading as a whole line is absent. The contract's form `git grep -c -x -F …` cannot run: git 2.56 has no `-x` switch and exits 129 (N1). I used the anchored equivalent, `git grep -c -E "^## Step 5\.8: The codegraph add-on's settings check$"`, which exits 1 with no output.
  - The remerge-diff hunk shows nothing else changed: the parent's Step 5.6 section is kept verbatim, the old heading is removed, and master's renamed heading follows it.
- **Duplicate titles (rule (7'), amendment 9).** Met, exact.
  - The structure lint prints no R2 line.
  - MECHANISMS.md: the 2026-10-30 "CodeGraph (amendment)" entry ends with the 2026-11-05 (issue #259) Correction line and then the 2026-11-07 (issue #295) Correction line. The 2026-11-05 "Add-on layout (amendment)" entry ends with a 2026-11-07 (issue #295) Correction line.
  - VOCABULARY.md: the 2026-11-05 "Investigation Turn (amendment)" entry ends with a 2026-11-07 (issue #295) Correction line, after its 2026-11-06 Correction line.
  - My script built each expected line as `"  - **Correction (2026-11-07, issue #295):** "` plus the text after the ` — ` separator in `67a4a14`'s copy. All three match byte for byte.
  - No top-level entry with those three titles and the 2026-11-07 date remains.
  - The fold was applied provisionally. Q27 is still open for the owner (W1).
- **`test_gate_cost.py` is red only on its production-size check.** Met. It is environmental, not a finding. See the Evidence table for its one failing line.
- **Journal appends (Q25).** Met.
  - I extracted both lesson blocks from the contract's "Amendment 7 record". Each sits in JOURNAL.md at `ccd006f` with its heading and all five fields line-equal to the quoted text: "A clean landing check goes stale …" at line 536 and "A merge block's pull request must paste …" at line 543. Both are above `## Project tier` (line 550).
  - `git grep -c -F "<title>" ccd006f -- .claude/registries/JOURNAL.md` prints `:1` for each title.
  - `git log -S"<title>" 82bfe5e..ccd006f -- JOURNAL.md` names only `a74a52b` for each. That commit has one parent (`6fdaf25`), so it is not a merge. It reached the parent branch only through #321, not by a direct push.
- **Base-line check, re-run with my own script on the three resolved paths.** Met.
  - The merge's own base is `88f4d32`, its parent tip is `82bfe5e`, and its master side is `67a4a14`.
  - At `6fdaf25`: 0 surviving base lines, 0 lost side-added lines and 0 lost parent lines on each of MECHANISMS.md, VOCABULARY.md and the skill.
  - At `ccd006f`: the same result, 0 on every count, once the three rule (7') heading lines are excluded. Those three lines are exactly the heading lines #321 quotes as folded, and their text survives as the Correction lines.
  - The Q22 fold is intact. Its line occurs once, under the 2026-10-30 entry, and the 2026-11-05 top-level "CodeGraph (amendment)" is absent.
  - The MECHANISMS rule-(9) fold is intact. It occurs once, under the 2026-11-05 "CodeGraph (correction)" entry, and the top-level 2026-11-06 "CodeGraph (correction)" is absent.
  - The VOCABULARY rule-(9) fold is intact. The column-0 2026-11-06 line is absent, and its two-space-indented copy occurs once, under "Investigation Turn (amendment)".
  - Both sides' entries are kept. In MECHANISMS.md, 2 entries and Correction lines the default branch added since `88f4d32` are not folded ("Project hook launcher", and the Revision 9 Correction under "Guard fallback mode"). In VOCABULARY.md there are 8, and in JOURNAL.md 5. Each is byte-equal to `67a4a14`'s copy and above its file's pointer (MECHANISMS 128, VOCABULARY 161, JOURNAL 550). Each Correction line sits under the same entry as in `67a4a14`.
- **t15's pull request pastes the raw outputs block 15 names (t14 W1).** Mostly met (N2).
  - #321 has two comments (7,916 and 61,746 characters). Between them they carry: the merge-base and merge-tree lines, the `git log` list, the 18-file deleted-names list with its grep, the Base-line output before and after the fold, the two `registry_append` file:line results, both `git grep -c` counts, the head proof, the three skill counts, the version diff and check, the older-test search, the structure lint and the five definition lines.
  - The raw tail of every suite, with its exit code, is there too, including `test_gate_cost.py`'s FAIL line.
  - Three items are not raw: the `git diff --stat <base> origin/master` output, the two sides of the skill hunk (given in prose), and "what each side added" (given as title lists).
- **No version file was edited by hand.** Met.
  - `git log --no-merges 88f4d32..ccd006f --not 67a4a14` over the manifests is empty. The only manifest commits reachable through the merge are master's own (`c5bf9d4`, `d860663`).
  - `git diff 67a4a14 ccd006f` over the manifests is empty, and so is the diff against today's origin/master `fb89001`. Both are at 0.16.5.
  - `check_version_bump.py` in parent mode exits 0 ("keeps version 0.16.5").
- **Lint, `--check` and the doctor.** Met.
  - The lint prints only R4 lines (39), one line `advisory: R3 universal-candidate skipped: 18 entries; …` and `digest: absent`.
  - `--check` gives `current`.
  - The doctor reports `registry layout: current` and 0 body-less journal entries, in both its text and its JSON output.
- **`test_plugin_manifests.py` fails exactly one row.** Met.
  - 204 passed and 1 failed. The failing row is "the version obeys the merge-base rule: tree differs from the merge base (0.16.5), so all five declarations exceed it". That is the amendment-6 exception, now with the new merge base's version.
  - It is not a finding, and no other row is red.
- **Every t14 "Met" item still holds.** Met.
  - Over `5df3f3a..ccd006f`, the only `.py` files that changed are the default branch's 18 (codegraph hooks, installer, shadow report, their tests and the frozen fixtures). The contract's code is untouched.
  - `memory_boundary.py:62` still binds `registry_files_in` through `_bind`. `DOMAINS`, `DEFAULT_DOMAINS` and `_SOURCE_VALUE` are absent from production code; only negative test assertions name them.
  - Line 1 of all three roots is the layout-2 marker. The three `general.md` skeletons are `cmp`-identical to the templates.
  - `skills/ship/SKILL.md` has an empty diff over the range.
  - Every suite in t14's Evidence table exits 0, except the one owner-accepted row above. That includes case 13 of `test_script_path_resolution.py` (206 passed) and the Q-hop rows of `test_codegraph_first_guard.py` (1671 passed, 0 failed, 3 skipped).
  - The single-definitions grep, in block 15's whole-word form with the fixtures excluded, prints exactly the five lines.
- **Off-area drift.** Nothing to compare.
  - `derive_area.py` returns `uncategorized`, because the area map is empty.
  - The non-merge commits of t15 touch only Files to touch (JOURNAL.md, MECHANISMS.md and VOCABULARY.md), plus the brief bookkeeping in `ad081c7`. The resolution touches only the three listed paths.
- **Last check: the landing merge is clean.** Met.
  - `merge-tree` against origin/master `fb89001` exits 0, lists no conflicting path, and gives tree `e947889`.
  - The parent is `ccd006f`, the same commit my journal-appends line read, so it already holds both Q25 lessons.
  - origin/master moved past `67a4a14` by one records file only (`d23bc0d`, the t15 completion record, #322).

## Findings

### W1 (warning) — Q27 is still open, and the fold it decides is already on the parent branch. Contract, `## Open Questions for User`, Q27

The contract lists Q27 as `- [ ]`, and its own text says the fold "was applied provisionally … the owner was not asked … The owner confirms or redirects at that review" (the review of #321). #321 says the same in "Open for the owner". #321 was merged, but no line in the contract or the pull request records the owner's answer.

No script stops on this. `land_contract.py` and `pr_merged.py` do not read Open Questions; only `list_contracts.py` reports them. So the landing would ship a design decision the owner never made.

The fold itself is correct. It follows Q22 exactly, and every check above passes. If the owner chose "retitle" instead, the remedy is to revert `02e581b`, after which the lint reports the three R2 titles again, plus a new amendment.

Fix: before running `/advance`, the owner answers Q27 in the contract (tick it with "→ Owner answered …"). This review cannot do that.

### N1 (nit) — Block 15's and block 16's old-heading check names a git switch that does not exist. Contract, block 15 "Head proof"; block 16 "the skill keeps both sides"

`git grep -c -x -F "## Step 5.8: The codegraph add-on's settings check" …` exits 129 ("unknown switch `x'") on git 2.56. t15 reported this in #321 and used an anchored `-e "^…$"` form instead. The contract text was not corrected, so the next block that copies it fails the same way.

This is the second half of the lesson t15 itself appended ("when the implementer finds that the contract mis-predicts the code, the next block or an amendment must fix the text"). Fix: at the landing or in a later amendment, replace the `-x -F` form with `git grep -c -E "^## Step 5\.8: The codegraph add-on's settings check$"`.

### N2 (nit) — Three of block 15's required outputs are summarised, not pasted. Record: pull request #321

The `git diff --stat <base> origin/master` output is missing. The two sides of the skill hunk are given as prose (comment 1, line "Rule (6') hunk: …"), and "what each side added since <base>" is given as title lists.

Everything else is raw, and it is far better than #309 was (t14 W1). I re-derived all three items from `git show --remerge-diff 6fdaf25` and my own script, so no check rests on an assertion. Fix: none for this contract. The journal lesson `a74a52b` already covers this class.

## What was NOT checked

- I did not re-run block 15's deleted-names check. #321 pastes its 18-file list and the grep, and the `.py` files the default branch changed are all codegraph, installer and test files. My suites cover them.
- I did not re-run the older-test search (block 15's four questions). The suites it would point at are all in my run.
- The R3 skip count is 18, where t14 printed 22. I did not trace the difference entry by entry. `validate_registries.py:335-346` counts the local Universal entries that the resolved installed plugin copy lacks, so the number depends on which installed release resolves, not on the merge. Block 16 asks only for "at most one R3-skip line".
- I did not ask the owner about Q27 (W1).
- I ran the digest generator live (exit 0). It wrote `.claude/.scout-cache/registry-digest.md` (gitignored). I removed that folder afterwards, so the worktree holds only this artefact and its Gate Output.
- `.claude/hooks/tests/bench_codegraph_guard.py` changed on the default branch, but it is a benchmark, not a test: it has no `test_` prefix, its docstring says it asserts nothing, and it must be run from a Claude Code session. I did not run it. `_addon_fixture.py` is a helper module, and test_addons.py exercises it.
- I did not run the landing. Its command is below.

## Evidence

All commands were run from the worktree root on Windows (Git Bash), using `py -3` with `PYTHONIOENCODING=utf-8`. The suites ran one at a time, never concurrently, through a sequential runner. Scratch scripts lived under `C:\Temp\t16\`, outside the repository (`run_suites.py`, `checks.py`).

**Test files the default branch changed since `88f4d32`.** I listed them with `git diff --name-only 88f4d32..67a4a14 -- .claude/scripts/tests .claude/hooks/tests` (exit 0): `_addon_fixture.py`, `bench_codegraph_guard.py`, `test_addons.py`, `test_codegraph_first_guard.py` and `test_codegraph_shadow.py` under hooks/tests; the three `fixtures/codegraph-db61fd7/*.py` files, `test_auto_improve_finish_install.py`, `test_codegraph_shadow_report.py`, `test_plugin_manifests.py`, `test_plugin_text_scans.py` and `test_skill_script_lookup.py` under scripts/tests.

- Every `test_*` file on that list is run below.
- `_addon_fixture.py` and the fixtures are helper modules or data.
- `bench_codegraph_guard.py` is a benchmark (What was NOT checked).
- `test_gate_cost.py` (from the default branch, `58d476d`) is also run.

| Command | Exit | Result |
|---|---|---|
| `git fetch origin` ; `git rev-parse HEAD origin/fix/235-domain-split-registries origin/master` | 0 | `ccd006f`, `ccd006f`, `fb89001` |
| `git log --graph --format='%h %p \| %s' 5df3f3a..ccd006f` | 0 | first-parent `82bfe5e` → `0dbf087` (amendment 9) → `ccd006f` (#321); #321's branch `6fdaf25` → `a74a52b` → `02e581b` → `ad081c7` |
| `git rev-list --parents -n 1` on `6fdaf25`, `ccd006f`, `0dbf087` | 0 | `6fdaf25 82bfe5e 67a4a14`; `ccd006f 0dbf087 ad081c7`; `0dbf087 82bfe5e` |
| `git merge-base 82bfe5e 67a4a14` | 0 | `88f4d32` (the merge's own base) |
| `git merge-base origin/master origin/fix/235-domain-split-registries` | 0 | `67a4a14` (not `88f4d32`) |
| `git show --remerge-diff --stat 6fdaf25` | 0 | 3 files: MECHANISMS.md, VOCABULARY.md, skills/verify-before-done/SKILL.md |
| `git show --remerge-diff 6fdaf25` (full) | 0 | each hunk: conflict markers removed, sides ordered (registries: master's entries, then the pointer; skill: Step 5.6 section, then master's renamed heading, the old heading dropped) |
| `git show --stat` on `a74a52b`, `02e581b`, `ad081c7`, `0dbf087` | 0 | JOURNAL.md +14; MECHANISMS.md 2/2 and VOCABULARY.md 1/1; the t15 brief; the contract |
| `git show 02e581b` | 0 | the three folded heading lines removed, three `  - **Correction (2026-11-07, issue #295):**` lines added under the earlier entries |
| `git diff --name-only 6fdaf25 ccd006f` ; `git diff --name-only 5df3f3a 82bfe5e` | 0 | the contract, JOURNAL, MECHANISMS, VOCABULARY, the t15 brief; the contract, the orchestrator state, two briefs |
| `checks.py <repo>` (Base-line, lost-lines, parent-lines, folds, master-added entries, journal) | 0 | every row OK: at `6fdaf25` and at `ccd006f`, surviving 0, lost 0 and parent-lines-lost 0 on all three paths (the 3 folded headings excluded at `ccd006f`); rule (7') last lines byte-equal; Q22 and both rule-(9) folds once, no top-level copy; master-added MECHANISMS 2, VOCABULARY 8, JOURNAL 5, all byte-equal, above the pointers 128/161/550, under the same entry; journal lessons at 536 and 543, 5 fields each, introduced only by `a74a52b` (parent `6fdaf25`) |
| `git grep -c -F "## Step 5.6: Registry structure lint" ccd006f -- skills/verify-before-done/SKILL.md` | 0 | `:1` |
| `git grep -c -F "## Step 5.8: The codegraph add-on's settings and hook freshness check" ccd006f -- …` | 0 | `:1` (line 262) |
| `git grep -c -x -F "## Step 5.8: The codegraph add-on's settings check" ccd006f -- …` | 129 | `error: unknown switch 'x'` (N1) |
| `git grep -c -E "^## Step 5\.8: The codegraph add-on's settings check$" ccd006f -- …` | 1 | no output: the old heading is absent |
| `git grep -c -F "<title>" ccd006f -- .claude/registries/JOURNAL.md` (both Q25 titles, via `checks.py`) | 0 | `:1` and `:1` |
| `gh pr view 321 --json state,mergeCommit,baseRefName,headRefName,body,comments` | 0 | MERGED into `fix/235-…` as `ccd006f`; line 1 is the merge-method sentence; Q27 listed as open; 2 comments with raw outputs (N2 lists the gaps) |
| `git diff --stat 67a4a14 ccd006f -- plugin.json .claude-plugin .cursor-plugin`; same against `origin/master` | 0 | empty; empty (0.16.5 on both) |
| `git log --oneline --no-merges 88f4d32..ccd006f --not 67a4a14 -- plugin.json .claude-plugin .cursor-plugin` | 0 | empty (no hand edit; the only manifest commits reachable are master's `c5bf9d4` and `d860663`) |
| `py -3 .claude/scripts/check_version_bump.py --base origin/fix/235-domain-split-registries --default-branch master --head-ref task/2026-11-04-domain-split-registries/t16-review` | 0 | "VERSION BUMP: sub-task pull request keeps version 0.16.5; the landing raises it" |
| `git diff --name-only 5df3f3a ccd006f -- '*.py'` | 0 | the 18 files of the default branch only |
| `git grep` for `_RL = _bind(…)`, `DOMAINS`, `DEFAULT_DOMAINS`, `_SOURCE_VALUE` in `.claude/scripts/*.py` | 0 | `memory_boundary.py:62` binds; the other names occur only in negative test assertions |
| `git grep -n -w -e "def _atomic_write" -e "def _plan_digest" -e "def _separate_plugin_root" -- .claude/scripts ':(exclude).claude/scripts/tests/fixtures'` | 0 | exactly five: `_plugin_root.py:73`, `_preview_apply.py:21`, `_preview_apply.py:30`, `land_contract.py:578`, `memory_boundary.py:720` |
| `git diff --stat 5df3f3a ccd006f -- skills/ship/SKILL.md` | 0 | empty |
| `head -1` of the three roots; `cmp` of the three `general.md` against `.claude/templates/registries/*/general.md` | 0 | the layout-2 marker on each; identical (exit 0 ×3) |
| `py -3 .claude/scripts/derive_area.py .claude/concepts/2026-11-04-domain-split-registries.md` | 0 | `uncategorized` |
| `py -3 .claude/scripts/tests/test_preview_apply.py` | 0 | 15 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_root.py` | 0 | 8 tests OK |
| `py -3 .claude/scripts/tests/test_registry_layout.py` | 0 | 83 tests OK |
| `py -3 .claude/scripts/tests/test_script_path_resolution.py` | 0 | 206 passed, 0 failed |
| `py -3 .claude/scripts/tests/test_registry_append.py` | 0 | 29 tests OK |
| `py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py` | 0 | 18 tests OK |
| `py -3 .claude/scripts/tests/test_registry_readers.py` | 0 | 13 tests OK |
| `py -3 .claude/scripts/tests/test_registry_migrate.py` | 0 | 40 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_doctor.py` | 0 | 209 tests OK (1 skipped: the plugin checkout is not beside this repository) |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` (explicit) | 0 | 37 tests OK |
| `py -3 .claude/scripts/tests/test_skill_script_lookup.py` (explicit) | 0 | 35 tests OK |
| `py -3 .claude/scripts/tests/test_auto_improve_finish_install.py` | 0 | 421 tests OK |
| `py -3 .claude/scripts/tests/test_check_version_bump.py` | 0 | 46 tests OK |
| `py -3 .claude/scripts/tests/test_validate_registries_default.py` | 0 | 7 tests OK |
| `py -3 .claude/scripts/tests/test_registry_entries.py` | 0 | 36 tests OK |
| `py -3 .claude/scripts/tests/test_memory_boundary.py` | 0 | 117 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_manifests.py` | 1 | 204 passed, 1 failed: only INV-O1 "the version obeys the merge-base rule: tree differs from the merge base (0.16.5), so all five declarations exceed it" (owner-accepted, amendment 6) |
| `py -3 .claude/hooks/tests/test_addons.py` | 0 | 39 tests OK |
| `py -3 .claude/hooks/tests/test_codegraph_first_guard.py` | 0 | 1671 passed, 0 failed, 3 skipped (POSIX-only); BN-1 "db61fd7 is present" PASS |
| `py -3 .claude/hooks/tests/test_codegraph_shadow.py` | 0 | 124 passed, 0 failed |
| `py -3 .claude/hooks/tests/test_main_checkout_guard.py` | 0 | 57 tests OK |
| `py -3 .claude/hooks/tests/test_working_agreements.py` | 0 | 133 passed |
| `py -3 .claude/hooks/tests/test_worktree_path_guards.py` | 0 | 190 passed, 0 failed |
| `py -3 .claude/scripts/tests/test_agent_skill_preloads.py` | 0 | 9 tests OK |
| `py -3 .claude/scripts/tests/test_cloud_text_scans.py` | 0 | 11 tests OK |
| `py -3 .claude/scripts/tests/test_codegraph_session_parent_docs.py` | 0 | 27 tests OK |
| `py -3 .claude/scripts/tests/test_codegraph_shadow_report.py` | 0 | 35 tests OK |
| `py -3 .claude/scripts/tests/test_installed_plugin_root.py` | 0 | 18 tests OK |
| `py -3 .claude/scripts/tests/test_memory_off_parity.py` | 0 | 28 tests OK |
| `py -3 .claude/scripts/tests/test_parent_branch_rule_text.py` | 0 | 41 tests OK |
| `py -3 .claude/scripts/tests/test_pr_merged.py` | 0 | 761 tests OK |
| `py -3 .claude/hooks/tests/test_gate_cost.py` | 1 | 0 passed, 1 failed; the one failing check is "the measured concepts folder is production size (at least 100 contracts; from neither CLAUDE_GATE_COST_CONCEPTS nor CLAUDE_PROJECT_DIR is set)" (environmental, amendment 9) |
| `py -3 .claude/scripts/registry_migrate.py --check --project .` | 0 | `state: current`, `marker: 2`, `reasons: []` |
| `py -3 .claude/scripts/validate_registries.py --check-structure --project .` | 0 | 39 R4 lines, `advisory: R3 universal-candidate skipped: 18 entries; this project holds the plugin's own manifest`, `digest: absent`; no R1, R2, R3, R5, A1 or layout line |
| `py -3 .claude/scripts/validate_registries.py --check-structure --strict --project .` | 1 | R4 counts under `--strict`, as specified |
| `py -3 .claude/scripts/generate_registry_digest.py` | 0 | 244 entries, 0 bad references, 0 R1/R2 findings (the output folder was removed afterwards) |
| `py -3 .claude/scripts/validate_registries.py --check-structure --project .` with the digest present | 0 | the `digest:` line is gone; only R4 and the R3 skip line remain |
| `py -3 .claude/scripts/plugin_doctor.py --project .` | 0 | `registry layout: current`, `body-less journal entries: 0` |
| `py -3 .claude/scripts/plugin_doctor.py --project . --json` | 0 | `registry_layout.state = current`, `bodyless_journal_entries = 0` |
| **Last check**, run live after every other check: `git fetch origin ; git merge-tree --write-tree --name-only origin/master origin/fix/235-domain-split-registries` | 0 | origin/master `fb89001fdf7c`, parent `ccd006fa6022` (the commit the journal-appends line read), tree `e9478890a58a`, no conflicting path (2026-11-09T15:18:39Z). origin/master moved past `67a4a14` by one records file only (`d23bc0d`, #322) |

**Version proof at the landing.** The version proof is the landing's own `check_version_bump.py --raise`, then `--exact` (gate P7b), and its version-bump verification step. It is not a re-run of `test_plugin_manifests.py` after the landing. The operator reads the landing report's raise and exact outcomes. Each must exit 0, and the raised version must be origin/master's version at landing time with the minor raised by one and the patch reset to 0. At amendment time that was 0.16.4 → 0.17.0. Today origin/master is at 0.16.5, so the raise is 0.16.5 → 0.17.0.

**Landing command for the operator (I did not run it).**

1. Resolve W1 (Q27) first.
2. Immediately before launching, re-run the last check: `git fetch origin ; git merge-tree --write-tree --name-only origin/master origin/fix/235-domain-split-registries`. It must exit 0 with no conflicting path. A clean result is valid only for the origin/master commit it names (here `fb89001`).
3. Then, in Claude Code, run:

```
/advance 2026-11-04-domain-split-registries
```

It launches `py -3 .claude/scripts/land_contract.py --contract 2026-11-04-domain-split-registries --json` in the background.

## Disposition

- **Pass with findings.**
  - Sub-task 15's one merge (`6fdaf25`) keeps both sides on all three resolved paths, with no surviving base line and no lost line.
  - The rule (7') fold is exact. The Q22 and rule-(9) folds are intact.
  - Both Q25 lessons are in place once each, added by a non-merge commit through #321.
  - The version is untouched (0.16.5, equal to origin/master). Every suite is green apart from the owner-accepted INV-O1 row and the environmental `test_gate_cost.py` check.
  - The landing merge is clean against origin/master `fb89001`.
- **W1** is a decision for the owner, not a defect: answer Q27 before launching the landing. If the owner confirms the fold, nothing else changes. If the owner chooses retitle, revert `02e581b` and amend the contract.
- **N1 and N2** are optional.
  - N1 is one contract line: replace the `-x -F` form. Batch it with the landing's version raise or with a later amendment.
  - N2 needs no change. This report re-derived the three summarised items.
- **Registry janitor.** No new mechanism or term in `82bfe5e..ccd006f`.
  - The merge brought the default branch's own entries ("Project hook launcher" and the issue-295 terms). Their contracts own them.
  - The two Q25 lessons were the only journal appends due, and they are in.
  - INTEGRATION.md does not apply: there is no REST, SignalR or DTO surface.
  - This task may write only this artefact and its Gate Output, so I am proposing the one new lesson below, not appending it. Batch it with the landing's raise through `registry_append.py --registry journal --universal`, if wanted:

  ```markdown
  ### 2026-11-09 — Check that a contract's shell command runs before writing it into a block
  - **Trigger:** post-impl divergence
  - **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
  - **Lesson:** a block's command is copied verbatim by the implementer and the reviewer; a flag the tool does not have (here `git grep -x`, which only GNU grep has) fails with a usage error in both stages. Run each new command once against the tree before the block is approved, and when an implementer reports a command that cannot run, fix the block text in the same amendment cycle.
  - **Apply when:** an amendment adds a literal git or shell command to a block's Head proof, Run list or review checks.
  - **Tags:** contract-text, git-grep, command, head-proof, review
  ```
