# t18 review merge and text fixes — fullstack-code-reviewer

**Verdict:** blocked

## Scope and range

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t18-review-merge-and-text-fixes (issue #221, parent #161)
- **Contract:** `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md` (Revision 8, block 17)
- **Supersedes:** none
- **Reviewed on:** 2026-11-03, cold context, in the t18 worktree at `6099982`.
- **Commit range reviewed:** `fdd7640..4707150`.
  - `fdd7640` is the parent tip before the merge (the Revision 8 briefs commit).
  - `4707150` is block 17's head, merged into the parent branch by `6099982` (#223). `git diff 4707150 6099982` is empty.
  - The range holds three commits: `3a5b1fa` (the merge of `274bf1e` from `master`), `36ecfad` (the text fixes and J1-J11) and `4707150` (the t17 brief's `pr:` line only).
- **The `master` commit merged** is `274bf1e` (#219), version 0.14.2. The contract's ASSUMED line named `8ea2dd4`, which is an ancestor of `274bf1e`. `master` has since moved to `0061212` (0.14.3); see I2.
- **Method.** Every merge claim is judged by git blob ids and `git show`, not by bytes on disk (journal 2026-10-17). The registry checks compare whole-file line sequences of each side against the merged file. Scripts: `blobcheck.sh`, `regcheck.py`, `sidelines.py`, `dupcount.py`, `dupnames.py` (system temp folder, not committed).

## What was checked

**Conflict list.** Met. `git merge-tree --write-tree --name-only fdd7640 274bf1e` reports exactly the five files block 17 lists: JOURNAL.md, MECHANISMS.md, VOCABULARY.md, README.md and `skills/pr-merged/references/contract-completion.md`. It auto-merges the four files block 17 names. No manifest conflict.

**Files outside Files to touch carry no hand edit.** Met. The merge commit `3a5b1fa` changes 70 files against `fdd7640`.
- 61 files only `master` changed, the four manifests included. Each has the same blob id at `3a5b1fa` as at `274bf1e`.
- 4 files both sides changed (`pr_merged.py`, `test_pr_merged.py`, `skills/flow/SKILL.md`, `skills/pr-merged/SKILL.md`). Each has the same blob id as in the tree `fe7aff0` that `git merge-tree --write-tree fdd7640 274bf1e` prints. None equals `origin/master`, as expected.
- `git diff --name-only fe7aff0 3a5b1fa` lists only the five conflicted files. No other path differs from git's own merge.
- **No name defined twice.** An `ast` walk of `pr_merged.py` (163 top-level definitions, 15 imports) and `test_pr_merged.py` (289 top-level definitions, 20 imports) finds no function, class, method or module constant defined twice in any scope, and no duplicate import. Both suites import and run (Evidence).

**Registries.** Met for all three files.
- `origin/master`'s copy of each registry is identical to `274bf1e`'s, so the "master" side is the same whichever is used.
- In `3a5b1fa` and in `4707150`, the whole line sequence of `origin/master`'s file and of `fdd7640`'s file is each a subsequence of the merged file. So every entry of both sides is present and unedited.
- Every entry heading of both sides is present exactly once. JOURNAL.md has 42 `### ` entries at the merge base, 43 on each side, 44 after the merge and 55 at the head (44 + J1-J11). No `### ` heading repeats. MECHANISMS.md: 47 and 45 headings, none repeated. VOCABULARY.md: 85 and 90, none repeated.
- **Master's first.** The new entries of `master` (JOURNAL 1, MECHANISMS 3, VOCABULARY 11) all sit before the new entries of this contract (1, 1, 16).
- No line of the merged registries comes from neither side, and no line either side removed was brought back. Each file's closing lines appear once.

**Conflict markers.** Met. `git grep` at `3a5b1fa` and at `4707150` finds no `<<<<<<< ` or `>>>>>>> ` line in any file, and no bare `=======` line in the seven files of Files to touch.

**contract-completion.md.** Not met; this is B1. Master's records-step paragraph and this contract's step 5a are both kept. But the resolution also keeps the base's old steps 6-9, which `master` replaced, beside master's new steps 6-9.

**README.md resolution.** Met. Every line `master` added is present, every line the parent side added is present apart from the "313 cases" line that the count rewrite replaced, no line comes from neither side, and no removed line came back.

**Text fixes.** Met, each as block 17 states.
- W1, `CONTRIBUTING.md:162-163`: "A scan in `.claude/scripts/tests/test_plugin_text_scans.py` enforces it: run it before committing a change to a shipped file. It is not yet run in CI." The "fails the build" claim is gone.
- I1 and I2: one sub-bullet `**Correction (2026-11-03):**` appended under the Memory adapter entry of MECHANISMS.md, text as block 17 gives it. The entry itself is untouched (append-only). `select_candidates` (`memory_boundary.py:535`) and `deadline_seconds: 20` (`:72`, `:311`) exist.
- I3: the same replacement sentence in `README.md` (Who appends) and `skills/auto-improve-finish-install/SKILL.md:292`.
- I5: the Memory client paragraph of README.md now reads "With both off, every brief, every Step 1.5 run and every capture step is what it was before they existed. The Project history record rule below applies whatever the switches say."

**JOURNAL.md J1-J11.** Met. Eleven `### 2026-11-02 — ` entries follow the merged tail, in the order J1-J11, before the closing `---` and comment. Each has the Step 3 shape: Trigger, Source contract, Lesson, Apply when, Tags. J1-J10 carry `pre-approval critic`, J11 `post-impl divergence`. Each title, Lesson, Apply when and Tags matches block 17's text. J11 matches the t10 artefact's Disposition item 7 line for line.

**README counts.** Partly met.
- Counts block 17 names are true: 33 skills, 15 agents, 7 agreements (tree and provider table), "fifteen agents", 13 hooks (pinned by `test_repo_consistency.py`, which passes). `test_pr_merged.py` is "761 cases" and "761 tests" in its two places, and `test_auto_improve_finish_install.py` "344 cases"; both match the suites' own output (Evidence). Neither is a sum of the two sides (539/575 and 313/344).
- Four counts in the directory tree are false against the merged tree, though both sides and the merge base already had them: W1.

**Version.** Met. No version file was hand-edited (blob ids above). All five declarations are 0.14.2, from `274bf1e`. The parent-mode check exits 0 for this branch and for block 17's own pull request (base `fdd7640`).

**Scope.** Met, with one note. `36ecfad` touches only files in Files to touch. `4707150` touches the t17 Work Item Brief's front matter (`pr:`, `issue_link:`, `status:`), the usual brief bookkeeping and not a shipped file.

## Findings

### B1 (blocker) — contract-completion.md now has two sets of steps 6-9, and the first set is the procedure `master` replaced. `skills/pr-merged/references/contract-completion.md:89-96`

`git merge-tree` shows the conflict hunk. The parent side (`fdd7640`) holds step 5a and then the base's unchanged steps 6-9. The `master` side holds master's rewritten steps 6-9. The resolution kept both sides of the hunk whole, so the merged file reads:

```
89: 6. **Cut the branch in a flat worktree.** Fetch `origin/<default>`, then create a worktree ... cut from `origin/<default>`. If the name is taken, use the suffix `-2`, then `-3`. ...
90: 7. **Copy exactly that union of `written_files` there** ...
91: 8. **Open a draft pull request** ...
92: 9. **Remove the records worktree.** Then name the copies left in the starting tree ...
93: 6. **Put the stable branch in a flat worktree.** The branch is always the one stable `docs/<contract-slug>-records`. ... never re-cut the branch. ...
94: 7. **Copy exactly `records_unpushed` plus the flip's `written_files` there** ...
95: 8. **Open a draft pull request** ... when no open pull request has `docs/<contract-slug>-records` as its head ...
96: 9. **Remove the records worktree, then sweep.** Run `--sweep-records` ...
```

Why it blocks:
- The parent side never changed steps 6-9; it only inserted 5a above them. In a three-way merge, master's rewrite of those lines wins. The lines at 89-92 are base text that `master` deleted, and the resolution brought them back. My check found these four lines are the only lines in any conflicted file that one side removed and the merge restored.
- The two sets contradict each other. Line 89 cuts the records branch from `origin/<default>`. Line 93 and `skills/pr-merged/SKILL.md:376` ("One stable branch, added to and never re-cut") forbid re-cutting. Line 92 names leftover copies by hand, and line 96 says the sweep "replaces naming the leftover copies by hand". The records-step paragraph (line 47) says "It runs steps 6 to 9 below", which now names eight steps.
- A session following this shipped reference can re-cut the stable records branch, or run both procedures. That breaks `master`'s records-leftover behaviour (#178) after the landing ships it to `master`, so "both behaviours stay" in block 17's TASK is not met.
- No suite pins the step order or count, so all suites pass. The line-presence checks miss it too, because every master line is present.

Fix: delete lines 89-92, keeping step 5a and then master's steps 6-9 (lines 93-96). The result should equal the merge-tree hunk with the parent side's steps 6-9 dropped. This file is in block 17's Files to touch, so the fix is a text change to that file, made in a fix block of the contract (Revision 9) or a re-run of block 17, then a re-review.

### W1 (warning) — four directory-tree counts in README.md are false against the merged tree. `README.md:766-770`

| README line | Says | Merged tree |
|---|---|---|
| `hooks/tests/` | 9 hook test suites | 23 `test_*.py` files |
| `scripts/` | 15 workflow scripts, 3 shared helper modules | 26 `.py` files (23 + 3) |
| `scripts/tests/` | 11 suites | 36 `test_*.py` files |
| `references/` | 2 reference documents | 3 files |

These lines are the same at the merge base `6d1ca0c`, at `fdd7640` and at `274bf1e`, so the merge did not cause them and block 17's own count list (skills, agents, agreements, hooks, suite case counts) does not name them. The review's TASK says every README count must be true against the merged tree, so I report them. `test_repo_consistency.py` pins only the hooks count. Fix: either rewrite the four counts, or file a follow-up stub that also extends `test_repo_consistency.py` to pin them. Not a block, because none was introduced by block 17.

### I1 (info) — the manifest descriptions still say "28 skills". `plugin.json` and the other manifests

They come from `master` by the merge, and block 17 must not edit a version file. The tree has 33 skills and 15 agents. The landing corrects them (Open Question 15, as the t10 review recorded). Nothing to do here.

### I2 (info) — `master` moved past the merged commit.

`origin/master` is at `0061212` (0.14.3), two commits after `274bf1e`. Those commits change the four manifests, two test files, `.claude/work-item-conventions.json` and a brief. None touches a registry, README.md or a conflicted file. So the landing's second merge should be a `version-fields` case only, not a P7 halt (the Revision 8 failure mode "master appends to a registry tail again"). The landing raise would be 0.15.0.

### I3 (info) — the reviewer-verdict log line and a journal lesson for B1 are owed, and this gate does not write them.

This gate writes only its two artefact files. Both are proposed under Disposition.

## What was NOT checked

- The meaning of the auto-merged text in `skills/flow/SKILL.md` and `skills/pr-merged/SKILL.md`. I confirmed they equal git's merge, and spot-checked that both behaviours (sweep and step 5a) appear in each. I did not read them end to end for a contradiction like B1.
- The hook suites under `.claude/hooks/tests/`: see Evidence for what finished. The full set was slow on a loaded machine.
- Pull request #223's description.
- The End-User View audit: no Angular UI surface. Adjacent Areas: not applicable to a merge block.

## Evidence

Every command ran from this worktree's root on 2026-11-03.

| Command | Exit | Result |
|---|---|---|
| `git log --format='%H %P %s' -6` | 0 | `6099982` = merge of `fdd7640` and `4707150`; `3a5b1fa` = merge of `fdd7640` and `274bf1e` |
| `git merge-base fdd7640 274bf1e` | 0 | `6d1ca0c` |
| `git merge-tree --write-tree --name-only fdd7640 274bf1e` | 1 | tree `fe7aff0`; conflicts: JOURNAL.md, MECHANISMS.md, VOCABULARY.md, README.md, contract-completion.md |
| blob-id comparison over `git diff --name-only fdd7640 3a5b1fa` | 0 | 61 master-only files identical to `274bf1e`; 4 auto-merged files identical to `fe7aff0`; 0 mismatches |
| `git diff --name-only fe7aff0 3a5b1fa` | 0 | only the five conflicted files |
| `git grep` for conflict markers at `3a5b1fa` and `4707150` | 1 | no match |
| registry subsequence and heading counts (`regcheck.py`) | 0 | all True; no heading repeated; master's new entries first in all three |
| `git show fe7aff0:skills/pr-merged/references/contract-completion.md` | 0 | the hunk at 60-103: parent side = 5a + base steps 6-9; master side = new steps 6-9 (B1) |
| `ast` duplicate-name walk of `pr_merged.py`, `test_pr_merged.py` | 0 | none |
| `py -3 .claude/scripts/check_version_bump.py --base origin/feature/memory-client-and-cloud-engineering --default-branch master --head-ref task/2026-11-01-memory-client-and-cloud-engineering/t18-review-merge-and-text-fixes` | 0 | "sub-task pull request keeps version 0.14.2; the landing raises it" |
| same, `--base fdd7640 --head-ref task/…/t17-merge-the-default-branch-into-the-parent-branch` | 0 | same line |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 0 | Ran 13, OK |
| `py -3 .claude/scripts/tests/test_registry_entries.py` | 0 | Ran 26, OK |
| `py -3 .claude/scripts/tests/test_repo_consistency.py` | 0 | Ran 22, OK |
| `py -3 .claude/scripts/tests/test_memory_boundary.py` | 0 | Ran 111, OK |
| `py -3 .claude/scripts/tests/test_memory_off_parity.py` | 0 | Ran 28, OK |
| `py -3 .claude/scripts/tests/test_plugin_manifests.py` | 1 | 173 passed, 1 failed: "the version obeys the merge-base rule" (0.14.2 = merge base). Fails by design on a parent branch, where the landing raises; the t10 review recorded the same |
| `py -3 .claude/scripts/tests/test_check_version_bump.py` | 0 | Ran 46, OK |
| `py -3 .claude/scripts/tests/test_parent_branch_rule_text.py` | 0 | Ran 39, OK |
SUITES_PENDING

## Disposition

Blocked on B1 alone. The merge is otherwise exact: git's own result everywhere outside the five conflicted files, both sides' registry entries present once and unedited with master's first, no marker, and the text fixes and J1-J11 as block 17 states.

1. **B1:** amend the contract (Revision 9) with a fix block whose only change is deleting the four stale lines `skills/pr-merged/references/contract-completion.md:89-92`, then a re-review. Consider a test in `test_cleanup_delivered.py` or `test_skill_script_lookup.py` that pins each numbered step of that procedure exactly once.
2. **W1:** rewrite the four tree counts in the same fix block (README.md is in block 17's Files to touch), or file a follow-up stub.
3. **I1, I2:** none; the landing handles them.
4. **Journal entry owed for B1** (post-impl divergence; the main session appends it, batched with the fix):

   ```
   ### 2026-11-03 — When resolving a conflict hunk by keeping both sides, drop the base lines the other side rewrote
   - **Trigger:** post-impl divergence
   - **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
   - **Lesson:** Before keeping both sides of a conflict hunk, diff each side against the merge base; lines one side left unchanged and the other side rewrote belong to the rewrite only, or the merge restores deleted text beside its replacement.
   - **Apply when:** a merge resolves a prose or procedure conflict "keeping both behaviours", especially numbered steps
   - **Tags:** merge, conflict-resolution, base-text, duplicate-steps
   ```

5. **Reviewer-verdict line** for `~/.claude/logs/reviewer-verdicts.jsonl`, outside this gate's write scope:

   ```json
   {"ts":"2026-11-03T00:00:00Z","contract_path":"D:/Dev/HIPALANET/claude-agentic-auto-improve/.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md","divergence":true,"drift_summary":"block 17 merge restored base steps 6-9 of contract-completion.md beside master's rewrite (B1); four stale README tree counts (W1)","critical_count":1,"warn_count":1}
   ```

6. **Registries:** block 17 adds no mechanism or term, so no MECHANISMS.md or VOCABULARY.md append is owed.
