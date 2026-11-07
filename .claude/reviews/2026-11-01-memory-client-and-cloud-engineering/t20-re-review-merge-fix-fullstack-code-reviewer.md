# t20 re-review merge fix — fullstack-code-reviewer

**Verdict:** pass-with-findings

## Scope and range

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t20-re-review-merge-fix (issue #228, parent #161)
- **Contract:** `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md` (Revision 9, block 19; Revision 8, block 17)
- **Supersedes:** t18-review-merge-and-text-fixes-fullstack-code-reviewer.md
- **Reviewed on:** 2026-11-03. Cold context, in the t20 worktree at `27451d4`. Its tree (`0c56a32`) is the same as block 19's head tree.
- **Commit range reviewed (blocks 17 and 19 together):** `fdd7640..1388443`.
  - `fdd7640` is the parent tip before block 17's merge (the Revision 8 briefs commit).
  - `1388443` is block 19's head. `27451d4` (#230) merged it into the parent branch, and `git diff 1388443 27451d4` is empty (same tree).
- **Block 19's own range:** `664cb49..1388443`. `664cb49` is the parent tip block 19 was cut from. The range holds two commits:
  - `c4b192d`: the fix, four files.
  - `1388443`: the t19 brief's front matter only.
- **Block 17's own range** (from the t18 record, re-derived here): `fdd7640..4707150`, merged by `6099982` (#223). It holds three commits:
  - `3a5b1fa`: the merge of `274bf1e`.
  - `36ecfad`: the text fixes and J1-J11.
  - `4707150`: brief bookkeeping.
- **The `master` commit block 17 merged:** `274bf1e`, version 0.14.2. The merge base with `fdd7640` is `6d1ca0c`.
- **Method.** Every "identical" claim is judged by git blob ids, `git show` and `git diff`, never by bytes on disk (journal 2026-10-17). My own checks were written in the system temp folder and are not committed. They are: a blob-id diff against git's own merge tree; a line-set check for base text kept beside its rewrite; registry heading counts; an `ast` duplicate-name walk; and a per-suite runner.
- **Order of work.** I formed every finding below before opening the t18 artefact. I then read it only to confirm that B1 and W1 are cleared, and for format.

## What was checked

**Block 17, re-checked on the current tree.**
- **Conflict list.** Met. `git merge-tree --write-tree --name-only fdd7640 274bf1e` exits 1. It reports tree `fe7aff0` and conflicts in exactly the five files block 17 lists. It auto-merges `pr_merged.py`, `test_pr_merged.py`, `skills/flow/SKILL.md` and `skills/pr-merged/SKILL.md`.
- **Files outside block 17's Files to touch carry no hand edit.** Met.
  - `git diff --name-status fe7aff0 1388443` (git's own merge tree against block 19's head) lists four groups of files:
    - the seven files of block 17's Files to touch;
    - the one file block 19 adds, `.claude/scripts/tests/test_parent_branch_rule_text.py`;
    - the contract and the new follow-up stub;
    - the t18 artefact pair and four Work Item Briefs.
  - Every other path changed since `fdd7640` has the blob id git's merge gives it. That includes the four manifests, the four auto-merged files and every file only `master` changed. None of these carries a hand edit.
- **No name defined twice.** Met. An `ast` walk of `pr_merged.py`, `test_pr_merged.py` and `test_parent_branch_rule_text.py` at `1388443` finds no function or class defined twice in any scope.
- **Conflict markers.** Met. `git grep -E "^(<<<<<<<|=======|>>>>>>>)( |$)" 1388443` finds nothing (exit 1).
- **Registries.** Met for all three.
  - Every entry heading of `git show 274bf1e:<path>` and of `git show fdd7640:<path>` appears exactly once at `1388443`, with no heading repeated:
    - JOURNAL.md: `### ` headings;
    - MECHANISMS.md: `- **` bullets;
    - VOCABULARY.md: both forms.
  - Every non-blank line of either side is present in the head file.
  - In all three files, master's new entries come before this contract's: JOURNAL 5 and 5 (by line), MECHANISMS 3 and 1, VOCABULARY 11 and 16.
  - JOURNAL.md's last twelve headings are J1-J11 and then J12, each in the Step 3 shape. J1-J10 carry `pre-approval critic`, and J11 and J12 carry `post-impl divergence`. All twelve carry this contract as Source contract.
  - MECHANISMS.md and VOCABULARY.md are byte-identical by git between `664cb49` and `1388443`, so block 19 did not change them.
- **Text fixes (block 17).** Met; each still reads as block 17 states on the head tree.
  - W1: `CONTRIBUTING.md` says "It is not yet run in CI."
  - I1/I2: exactly one `**Correction (2026-11-03):**` sub-bullet in MECHANISMS.md, with the text block 17 gives.
  - I3: the new sentence is present once in both `README.md` and `skills/auto-improve-finish-install/SKILL.md`, and the old one is in neither.
  - I5: the README sentence is present.

**B1 (block 19): cleared.**
- **Step order.** Met. `records_step_labels` at `1388443` returns `['1', '2', '3', '4', '5', '5a', '6', '7', '8', '9']`. At `664cb49` it returns the same list with `'6', '7', '8', '9'` a second time (Evidence).
- **Steps 6-9 equal master's, by git's view.** Met. `git diff 274bf1e 1388443 -- skills/pr-merged/references/contract-completion.md` has no added or removed line starting `6. **`, `7. **`, `8. **` or `9. **`. Every line it does show is this contract's side:
  - the capture sentence in the order paragraph;
  - step 5a, its lookup code block and its six indented sub-steps;
  - the `/flow` capture sentence in the "Under `/flow`" paragraph.
- **Step 5a unchanged.** Met. `git diff 664cb49 1388443 -- <path>` is one hunk that removes exactly the four old step lines (`6. **Cut the branch in a flat worktree.**`, `7. **Copy exactly that union of`, the first `8. **Open a draft pull request**`, `9. **Remove the records worktree.** Then name the copies left`) and adds none.
- **The old phrase is gone.** Met. `git grep "Cut the branch in a flat worktree" 1388443` matches only in the contract and the t18, t19 and t20 briefs and artefact. It does not match in any shipped file.
- **The two auto-merged skill files, read end to end.** No base text is kept beside its rewrite.
  - I read `skills/flow/SKILL.md` (663 lines) and `skills/pr-merged/SKILL.md` (725 lines) in full.
  - A mechanical check backs the reading. For every shipped file changed since `274bf1e`, I listed each head line that is in the merge base `6d1ca0c` but that `274bf1e` removed, or that `fdd7640` removed. The check found zero such lines in all 41 files, both skill files included.
  - The same check, run on `664cb49`'s `contract-completion.md`, reports exactly B1's four lines, so it does detect this defect class.
  - Two things I noticed are not merge damage:
    - `skills/flow/SKILL.md:158` and `:165` run the same `--status --json` line twice. This is identical at `274bf1e` and at `6d1ca0c`.
    - `skills/pr-merged/SKILL.md:115,121` (and `skills/advance/SKILL.md:100-101`) say 760 `test_pr_merged.py` cases, which is master's text. See I2.

**W1 (block 19): cleared.** The four counts are measured on the `1388443` tree with block 19's counting rules:

| Tree line | README now says | Tree has |
|---|---|---|
| `hooks/tests/` | 23 hook test suites | 23 `test_*.py` files |
| `scripts/` | 23 workflow scripts, 3 shared helper modules | 23 `.py` files not starting `_`; 3 starting `_` (`_claude_paths.py`, `_contract_files.py`, `_contract_index.py`) |
| `scripts/tests/` | 36 suites, including the path-resolution suite | 36 `test_*.py` files |
| `references/` | 3 reference documents | 3 files |

- `git diff 664cb49 1388443 -- README.md` changes exactly these four lines and nothing else.
- The tree's other counts are true except one ambiguous count, which is information for the follow-up stub (I1):
  - 33 skills, 15 agents and 7 agreements;
  - 3 add-ons and 6 templates;
  - in `hooks/`: 13 hooks, a gate launcher and 7 helper modules.

**Test (block 19).** Met.
- The step 5a test now ends its section at `"6. **Put the stable branch"`. The diff changes only that one line of the test, so its assertions are unchanged.
- `records_step_labels(text)` meets every requirement in block 19:
  - It is module-level and takes a string.
  - It normalises `\r\n`, splits into raw lines and never calls `squash`, `flat` or `section`.
  - It counts only lines matching `^(\d+a?)\. \*\*` in column 0, between `### The records pull request` and the next `### ` line, and it skips fenced blocks.
- The step-order test and the control are added, and both pass on head: `test_parent_branch_rule_text.py` runs 41 tests, OK. The control checks three things:
  - a planted second `6. **` makes the list unequal;
  - an indented `   1. **` sub-step is not counted;
  - a fenced `1. **` is not counted.
- The comment explaining why the function takes text is present.

**J12.** Met. Block 19 adds seven lines to JOURNAL.md (six entry lines and a blank) and removes none.
- The entry sits after J11 and before the closing `---` and comment.
- Its six lines are identical, by a programmatic comparison, to block 19's text with the four-space task-block indent removed.
- No other registry line changed.

**Scope (block 19).** Met, with one note.
- `c4b192d` touches exactly the four files of block 19's Files to touch.
- `1388443` changes only the t19 brief's front matter (`pr:`, `issue_link:`, `status:`). That is the usual Work Item Brief bookkeeping, not a shipped file, as t18 recorded for `4707150`.
- `git diff bf8b20a 1388443 -- .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/` is empty, so the t18 artefact and its `.gate.json` are unchanged since #224.

**Version.** Met.
- No manifest changed in block 19.
- The parent-mode check exits 0: "sub-task pull request keeps version 0.14.2; the landing raises it".

**Second merge (the landing).**
- `origin/master` is now `e6918fc` (0.14.5).
- `git merge-tree --write-tree --name-only 1388443 origin/master` exits 0 and prints only the tree `ae9bf53`. **No file conflicts.**
- Master changed two files on block 19's stop list after `274bf1e`: `README.md` and `skills/auto-improve-finish-install/SKILL.md` (W2 has the detail). Git auto-merges both, and in `ae9bf53`:
  - the four tree counts, the I3 sentence and master's 0.14.4 and 0.14.5 changelog paragraphs are each present once, and the old I3 sentence is gone;
  - the registries, `contract-completion.md`, `CONTRIBUTING.md` and the test file have the same blob ids as at `1388443`;
  - the four counts measured on the merged tree are still 23; 23 and 3; 36; 3.
- The landing's raise reads `origin/master` 0.14.5, so it writes **0.15.0**.

## Findings

### W1 (warning) — the approved amendment block 19 ran under is not on the parent branch's remote. `c964787` (local `feature/memory-client-and-cloud-engineering` only)

Pull request #230's description says the first t19 run stopped at the pre-check because `master` had changed `README.md`, which is on block 19's stop list. By then `origin/master` was `1ad653e`, and `git diff --name-only 274bf1e 1ad653e` lists `README.md`. The owner approved a contract amendment, commit `c964787` ("clear README.md from block 19's pre-check stop list", parent `664cb49`). It adds seven lines to block 19's pre-check.

`git branch -a --contains c964787` lists only the local `feature/memory-client-and-cloud-engineering`, checked out in another worktree. It is on no remote branch. So the contract at `1388443` and on `origin/feature/memory-client-and-cloud-engineering` (`27451d4`) does not carry the amendment. The local parent branch has also diverged from its remote: it lacks #230.

This is not a defect in block 19's four files. The implementer followed the approved amendment, and its condition held: master's README hunks at that time were only the 0.14.4 paragraph. But the contract is the record of what each block was told, and it currently omits the instruction block 19 ran under.

**Fix (main session, outside this gate):**
1. In the parent worktree, merge `origin/feature/memory-client-and-cloud-engineering` into the local branch (or rebase `c964787` onto it).
2. Push, so the amendment is on the parent branch before the landing.

If it is never pushed, delete the local commit on purpose and say so in the parent brief. Do not leave it to vanish when the landing worktree is cut.

### W2 (warning) — a falsified assumption with no journal entry. The contract's Revision 9 `ASSUMED` line, and JOURNAL.md

Revision 9 assumed that `origin/master` was `0061212` and that master's commits after `274bf1e` touch no `README.md` and no file block 17 text-fixed. Both parts proved false:
- by block 19's run, `9dc5df1` (0.14.4, #226) had changed `README.md`, and the pre-check stopped;
- since then, `95c2107` and `e6918fc` (0.14.5, #229) changed `README.md` in three more hunks and `skills/auto-improve-finish-install/SKILL.md`, both stop-list files.

The mitigation worked, so this does not block. The pre-check stopped, the user amended, and the landing's merge is clean (above). But an `ASSUMED` that flipped to falsified and made the implementation route around it is a journal case (reviewer janitor rule). No entry exists, and this gate does not append. Proposed entry (`post-impl divergence`), to batch with the landing's raise or the next change that raises the version:

```
### 2026-11-03 — A stop list checked against a moving default branch needs a rule for changes outside the edited lines
- **Trigger:** post-impl divergence
- **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
- **Lesson:** When a block stops on "master changed a file on the stop list", say in the block which kind of change still allows it to go on (for example a hunk outside the lines the block edits, proven by a quoted git diff and a clean git merge-tree), so a busy default branch does not force a contract amendment for every changelog paragraph.
- **Apply when:** a fix or merge block's pre-check compares origin/<default> against a stop list of shared, often-edited files such as README.md
- **Tags:** pre-check, stop-list, moving-base, merge-tree, amendment
```

### I1 (info) — "6 generic data files" in the `hooks/` tree line depends on a counting rule. `README.md:765`

`.claude/hooks/` holds six `.json` files at `1388443`:
- `architecture-guard.exceptions.json`
- `architecture-guard.rules.json`
- `db-destructive-guard.rules.json`
- `hooks.json`
- `integration-check.rules.json`
- `working-agreements.rules.json`

`hooks.json` has its own tree line. So the count is 6 if `hooks.json` counts as a data file and 5 if it does not. This is not a finding against block 19, which was told not to touch it. It belongs to `.claude/concepts/followups/2026-11-03-readme-tree-counts-and-step-pins.followup.md`.

### I2 (info) — skill text says 760 `test_pr_merged.py` cases; the README and the suite say 761. `skills/pr-merged/SKILL.md:115,121`, `skills/advance/SKILL.md:100-101`

The two skill files hold master's text. Git auto-merged `skills/pr-merged/SKILL.md`, and `skills/advance/SKILL.md` is master-only. Neither file is in block 17's or block 19's Files to touch, so neither block could edit them. `README.md:935,1231` says 761, which matches the suite's own output (Evidence). Point this at the same follow-up stub, or at a block that owns these files.

### I3 (info) — the Revision 9 PowerShell command ran in Git Bash.

The worktree sandbox refused every `powershell.exe` invocation that names git, so the `git show … | py -3 -I -c …` command ran in Git Bash. The text is unchanged and needs no shell-specific quoting, so the result does not depend on the shell. I quote both outputs under Evidence.

### I4 (info) — five finish-install failures come from master's own text at `274bf1e`, and the landing's merge clears them. `.claude/scripts/tests/test_auto_improve_finish_install.py`

On head the suite runs 344 with 5 failures (`TestLauncherFallbackNote` 1, `TestLauncherSurfaceMissingRefusal` 4), the same five t18 reported. The suite and the code it tests have the same blob ids at `1388443` as at `274bf1e`, so neither block touched them. The same five fail on a `git archive` of `274bf1e`.

They no longer fail on `origin/master`. Master's 0.14.4 notes call them "red until the writer refusal merges", and that change merged as #229 (`e6918fc`, 0.14.5). On `git archive origin/master` the suite passes, Ran 344, OK. It also passes on `git archive ae9bf53`, the landing's trial merge tree.

So this is not "pre-existing on `origin/master`" in the strict sense of this gate's CONSTRAINTS. It is inherited from the merged master commit and fixed upstream since. It is not a defect of block 17 or 19, and the landing's second merge resolves it.

## What was NOT checked

- **Pull request #223's description.** Not checked, by decision: no gate reads it and it does not ship.
- **Running the step-labels command in PowerShell itself** (I3).
- **A run of the suites on the landing's merged tree `ae9bf53`.** Only `git merge-tree` and blob and count checks were run against it. The landing's own verification step runs the suites there.
- **The End-User View audit.** No Angular UI surface. Adjacent Areas: not applicable to a merge-fix block.
- **The contract's other `## Critique (Revision 9)` items.** I checked only those that blocks 19 and 20 carry.

## Evidence

Every command ran from this worktree's root on 2026-11-03, on the tree `0c56a32` (= `1388443`).

| Command | Exit | Result |
|---|---|---|
| `git log --format="%h %p %s" -n 12` | 0 | `27451d4` = merge of `664cb49` and `1388443`; `1388443` parent `c4b192d`; `c4b192d` parent `664cb49`; `3a5b1fa` = merge of `fdd7640` and `274bf1e` |
| `git diff --name-status 664cb49 1388443` | 0 | JOURNAL.md, `test_parent_branch_rule_text.py`, the t19 brief, README.md, `contract-completion.md` |
| `git diff --name-status c4b192d 1388443` | 0 | the t19 brief only (`pr:`, `issue_link:`, `status:`) |
| `git diff --stat bf8b20a 1388443 -- .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/` | 0 | empty |
| `git merge-base fdd7640 274bf1e` | 0 | `6d1ca0c` |
| `git merge-tree --write-tree --name-only fdd7640 274bf1e` | 1 | tree `fe7aff0`; conflicts: JOURNAL.md, MECHANISMS.md, VOCABULARY.md, README.md, contract-completion.md |
| `git diff --name-status fe7aff0 1388443` | 0 | only Files to touch of 17 and 19, the contract, the stub, the t18 pair and four briefs |
| `git grep -n -E "^(<<<<<<<\|=======\|>>>>>>>)( \|$)" 1388443` | 1 | no match |
| `ast` duplicate-name walk of `pr_merged.py`, `test_pr_merged.py`, `test_parent_branch_rule_text.py` | 0 | none |
| registry heading counts at `1388443` against `274bf1e` and `fdd7640` | 0 | every heading once; no repeat; master's new entries first in all three |
| J12 programmatic comparison with block 19's text | 0 | `verbatim: True`; 7 lines changed by block 19 |
| `git diff 664cb49 c4b192d -- skills/pr-merged/references/contract-completion.md` | 0 | one hunk: four lines removed, none added |
| `git diff 274bf1e 1388443 -- skills/pr-merged/references/contract-completion.md` | 0 | no `6. **`-`9. **` line; only the 5a block, its sub-steps and code, and two capture sentences |
| `git grep -n "Cut the branch in a flat worktree" 1388443` | 0 | only the contract, the t18 artefact and the t19 and t20 briefs; no shipped file |
| `git show 664cb49:skills/pr-merged/references/contract-completion.md \| py -3 -I -c "import sys; sys.path.insert(0, '.claude/scripts/tests'); import test_parent_branch_rule_text as t; print(t.records_step_labels(sys.stdin.read()))"` | 0 | `['1', '2', '3', '4', '5', '5a', '6', '7', '8', '9', '6', '7', '8', '9']`; the step-order equality fails here |
| same, `1388443:` | 0 | `['1', '2', '3', '4', '5', '5a', '6', '7', '8', '9']` |
| same, `274bf1e:` (control) | 0 | `['1', '2', '3', '4', '5', '6', '7', '8', '9']` |
| base-text-kept check over 41 shipped files changed since `274bf1e` | 0 | 0 lines in every file; on `664cb49`'s contract-completion.md it reports B1's four lines |
| tree counts at `1388443` (`git ls-tree`) | 0 | hooks/tests 23; scripts 23 + 3; scripts/tests 36; references 3; skills 33; agents 15; agreements 7; templates 6; add-ons 3 |
| `git fetch origin`; `git rev-parse --short origin/master` | 0 | `e6918fc` (0.14.5) |
| `git merge-tree --write-tree --name-only 1388443 origin/master` | 0 | `ae9bf53fad0e3b610fd4c34e8e7f7fb1b0d111ed`; no conflicted file |
| `git diff --name-only 274bf1e origin/master` | 0 | manifests, two t17/t18 result records, `_claude_paths.py`, `auto_improve_finish_install.py`, `plugin_doctor.py`, four tests, `work-item-conventions.json`, a brief, README.md, `skills/auto-improve-finish-install/SKILL.md` |
| `git diff --name-only 274bf1e 1ad653e` (master when block 19 ran) | 0 | includes README.md (the pre-check stop) |
| `git branch -a --contains c964787` | 0 | `+ feature/memory-client-and-cloud-engineering` only (W1) |
| `py -3 .claude/scripts/check_version_bump.py --base origin/feature/memory-client-and-cloud-engineering --default-branch master --head-ref task/2026-11-01-memory-client-and-cloud-engineering/t20-re-review-merge-fix` | 0 | "VERSION BUMP: sub-task pull request keeps version 0.14.2; the landing raises it" |
| `test_pr_merged.py` (alone, after every other suite finished) | 0 | Ran 761, OK. Matches `README.md:935,1231`; the skill files' "760" is I2 |
| `py -3 .claude/hooks/tests/test_addons.py` | 0 | Ran 17, OK |
| `py -3 .claude/hooks/tests/test_angular_rule_coverage.py` | 0 | Ran 17, OK |
| `py -3 .claude/hooks/tests/test_architecture_guard_messages.py` | 0 | Ran 24, OK |
| `py -3 .claude/hooks/tests/test_architecture_guard_paths.py` | 0 | Ran 56, OK |
| `py -3 .claude/hooks/tests/test_architecture_guard_precision.py` | 0 | Ran 44, OK |
| `py -3 .claude/hooks/tests/test_architecture_guard_scss.py` | 0 | Ran 32, OK |
| `py -3 .claude/hooks/tests/test_changed_file_check.py` | 0 | Ran 50, OK |
| `py -3 .claude/hooks/tests/test_codegraph_first_guard.py` | 0 | 28 passed, 0 failed, 28 total |
| `py -3 .claude/hooks/tests/test_concept_gate_outside_project.py` | 0 | Ran 10, OK |
| `py -3 .claude/hooks/tests/test_contract_index.py` | 0 | 197 passed, 0 failed (of 197) |
| `py -3 .claude/hooks/tests/test_db_destructive_guard.py` | 0 | 590 passed, 0 failed (of 590) |
| `py -3 .claude/hooks/tests/test_guard_deference.py` | 0 | Ran 118, OK |
| `py -3 .claude/hooks/tests/test_hook_data_files_project_first.py` | 0 | 29 PASS lines, 0 FAIL |
| `py -3 .claude/hooks/tests/test_main_checkout_guard.py` | 0 | Ran 55, OK |
| `py -3 .claude/hooks/tests/test_memory_common.py` | 0 | 26 PASS lines, 0 FAIL |
| `py -3 .claude/hooks/tests/test_post_edit_dispatcher.py` | 0 | 24 PASS lines, 0 FAIL |
| `py -3 .claude/hooks/tests/test_project_hook_launch.py` | 0 | Ran 21, OK |
| `py -3 .claude/hooks/tests/test_readonly_guard_disposable_exemption.py` | 0 | PASSED 16 of 16 (5 must-allow, 11 must-block) |
| `py -3 .claude/hooks/tests/test_shell_write_targets.py` | 0 | Ran 19, OK |
| `py -3 .claude/hooks/tests/test_stop_dispatcher.py` | 0 | Ran 20, OK |
| `py -3 .claude/hooks/tests/test_working_agreements.py` | 0 | 133 cases: 133 passed, 0 failed, 0 errored |
| `py -3 .claude/hooks/tests/test_worktree_path_guards.py` | 0 | 170 passed, 0 failed (of 170) |
| `test_plugin_text_scans.py` | 0 | Ran 13, OK |
| `test_registry_entries.py` | 0 | Ran 26, OK |
| `test_repo_consistency.py` | 0 | Ran 22, OK |
| `test_memory_boundary.py` | 0 | Ran 111, OK |
| `test_memory_off_parity.py` | 0 | Ran 28, OK |
| `py -3 .claude/scripts/tests/test_plugin_manifests.py` | 1 | 173 passed, 1 failed: "the version obeys the merge-base rule" (0.14.2 = merge base). By design on a parent branch, as block 19's CONSTRAINTS and the t10 and t18 reviews record; the landing's raise clears it |
| `test_auto_improve_finish_install.py` | 1 | Ran 344, FAILED (failures=5): `TestLauncherFallbackNote` 1, `TestLauncherSurfaceMissingRefusal` 4. See I4 |
| same suite on `git archive 274bf1e` (the master commit block 17 merged) | 1 | Ran 344, FAILED (failures=5), the same five |
| same suite on `git archive origin/master` (`e6918fc`) | 0 | Ran 344, OK |
| same suite on `git archive ae9bf53` (the landing's trial merge tree) | 0 | Ran 344, OK |
| `test_check_version_bump.py` | 0 | Ran 46, OK |
| `test_parent_branch_rule_text.py` | 0 | Ran 41, OK (39 before block 19, plus the step-order test and the control) |
| `test_skill_script_lookup.py` | 0 | Ran 29, OK |
| `test_cleanup_delivered.py` | 0 | Ran 126, OK (skipped=1) |

Rows with a bare file name ran as `py -3 -m unittest discover -s .claude/scripts/tests -t .claude/scripts/tests -p <file>`. Each hook suite and `test_plugin_manifests.py` ran directly as `py -3 <file>`, because several of them are plain scripts that `unittest discover` reports as "no tests ran". Every suite ran in its own process.

## Disposition

Pass with findings. B1 and W1 of the t18 review are cleared. Block 17's merge is exact on the current tree, and block 19 touched only its four files and the brief. The landing's second merge does not conflict.

1. **W1:** the main session pushes `c964787` to the parent branch (after merging `origin/feature/memory-client-and-cloud-engineering` into the local branch) before the landing, or discards it on record.
2. **W2:** append the proposed journal entry, batched with a change that raises the version (the landing's raise commit carries only the manifests, so the main session's next registry-carrying change, or the follow-up stub's block).
3. **I1, I2:** add to `.claude/concepts/followups/2026-11-03-readme-tree-counts-and-step-pins.followup.md`. **I3:** none. **I4:** none; the landing's second merge brings master's fix, and the suite passes on the trial merge tree.
4. **Reviewer-verdict line** for `~/.claude/logs/reviewer-verdicts.jsonl`, outside this gate's write scope:

   ```json
   {"ts":"2026-11-03T00:00:00Z","contract_path":"D:/Dev/HIPALANET/claude-agentic-auto-improve/.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md","divergence":true,"drift_summary":"block 19 ran under an approved pre-check amendment (c964787) that is not on the parent branch's remote; Revision 9's ASSUMED about master's later commits was falsified","critical_count":0,"warn_count":2}
   ```

5. **Registries:** block 19 adds no mechanism or term, so no MECHANISMS.md or VOCABULARY.md append is owed. The one owed JOURNAL.md entry is W2.
