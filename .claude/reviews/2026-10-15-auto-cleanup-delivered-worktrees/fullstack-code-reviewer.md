# Review: Delivery cleanup (issue #50) — fullstack-code-reviewer

**State reviewed:** the uncommitted working tree on top of origin/master 0c4cdec (branch `feature/50-auto-cleanup-delivered-worktrees`). Nothing was committed, so there is no commit range.
**Contract:** `.claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md` (approved, revision 2)
**Verdict:** pass-with-findings

No CRITICAL findings. Every deletion goes through a non-forced `git worktree remove` on an entry that git has registered, or through `git branch -D` / `git push --delete` after an ancestor check against `origin/<default>`. None of these appear anywhere: `--force`, `git worktree prune`, `rmtree`, `switch` or `checkout`. Every git and gh failure I traced fails closed: the item is kept, read as `unverifiable`, or read as `not-in-default`. The eleven WARNs are cases where the code is looser than the brief's safety rules. Three of them (W1, W2, W11) let a run take in an item that belongs to another work item or to the user. Fix those before merge.

Tests were not run (instructions: long suites excluded). `check_version_bump.py` exits 0 only because nothing is committed yet. It must be re-run after the commit.

---

## WARN

**W1 — The brief fallback adopts another work item's brief through the starting tree's branch.** `.claude/scripts/cleanup_delivered.py:300-319`
`find_brief` adds the `--from` tree's current branch to `heads`, then accepts whatever `brief_for_branch(head, ref)` returns. It never checks that the brief belongs to this contract. Suppose `/pr-merged` for contract Y is run from item X's tree, and Y has no header and no brief whose `contract:` names it. Then X's `branch:` and `worktree:` join Y's Owned set. Today the standing-tree rule and the `checked-out` rule hide most of the damage, because X's tree is the start tree. But X's brief `worktree:` (when detached), and X's merged branch once X's tree is gone, can be removed by Y's run. That breaks the brief rule "never touch another work item's worktree or branch". No test covers the negative case: test 1173 only proves the positive.
Fix: reject a fallback brief whose `contract:` is set and does not name the slug (`pr_merged._names_contract`). Try the start branch only after the record heads. Add a test where the start tree belongs to a sibling item, whose brief reads `contract: <other-slug>`, and assert that nothing of the sibling is in the report. The contract's INV-2 step 2 caused this, so a JOURNAL entry was added.

**W2 — The advance-name ownership is a prefix match, checked for ambiguity only against slugs on `origin/<default>`.** `cleanup_delivered.py:334-338, 517-521`; `pr_merged.py:882-891`
`_is_advance_worktree(".../20261015-advance-foo", "foo-bar")` is True, because `"foo-bar".startswith("foo-")`. The `ambiguous-name` guard lists only the contracts committed at `origin/<default>`. If contract `foo` exists so far only on its own feature branch, a cleanup for `foo-bar` claims foo's detached advance worktree and removes it when that tree is clean and merged. Its ignored content goes with it.
Fix: accept the prefix form only when the folder name was really cut, meaning its length is at `flat_worktree`'s 60-character cap. Otherwise require `rest == slug` (or `rest` with `-2..-9` removed).

**W3 — The `$CLN` fallback picks the main checkout's copy when the session stands in the main checkout.** `skills/pr-merged/SKILL.md:446`, `skills/advance/SKILL.md:484`
`if [ -z "$CLN" ] && [ -f "$PWD/$S" ]; then CLN=$PWD/$S; fi` — when `/pr-merged` runs from the main checkout (common) and no plugin install is found, this is exactly the stale copy that decision 2 and INV-6 forbid. The new lookup test only exercises a project folder.
Fix: take `$PWD/$S` only for a linked worktree, for example `[ -f "$PWD/.git" ]` (a linked worktree's `.git` is a file). Add a test for the case where the start folder is the main checkout.

**W4 — In `/advance` the cleanup step comes after the report that prints its line.** `skills/advance/SKILL.md:443` vs `:452`
Step 3 (Report) carries `- Cleanup: <Step 4's ... line>`, but Step 4 runs after Step 3. A model following the order will report before it cleans up, or leave the cleanup out. Move the cleanup before the report, or make it the last action of Step 2.

**W5 — The INV-9 repair instruction never reaches the printed line.** `cleanup_delivered.py:466-470, 718-722`, `build_line` `:636-648`
When a probe cannot rename back, the instruction "rename `<sibling>` back, then `git worktree repair`" sits only in `detail` and `report["repair"]`. The skills print `line` alone, so the trader sees `<name>: remove-failed`. The worktree is then sitting at `<path>.probe` and git's metadata is broken. Append `; repair: <rename + git worktree repair '<path>'>` to the line, the way `finish:` is appended, and keep it outside the cap.

**W6 — "Confirm the target survives" is computed but never acted on, and is wrong for relative symlinks.** `cleanup_delivered.py:220-232, 476-485`
`target_survived` is recorded and ignored. A link whose target vanished still lets the run go on to `git worktree remove`, and the line says nothing. `os.path.exists(target)` resolves a relative symlink target against the process cwd (the main root), not against the link's folder.
Fix: resolve relative targets with `os.path.join(os.path.dirname(link), target)`. On `target_survived is False`, stop all further mutation (as for `Halt`) and report it in the line.

**W7 — Protected names are filtered only at the branch stage, not at the worktree stage.** `cleanup_delivered.py:322-331, 510-511`
If a brief names `master`, `main` or the default branch, `owned_branches` puts it in the set. `plan_worktrees` then plans any linked worktree holding it (`branch in owned`) and removes it when clean. INV-2 says never the default branch. Fix: drop `PROTECTED` and `default` in `owned_branches`, or mark such worktrees `protected-name`.

**W8 — The remote deletion has a check-then-act window.** `cleanup_delivered.py:569-608`
The tip comes from `ls-remote`, followed by the ancestor check, `gh pr list`, and then `git push origin --delete <b>`, which has no lease. A push to the branch in between is deleted without its new commits having been checked. It is off by default, but the deletion is outward-facing. Fix: `git push --force-with-lease=refs/heads/<b>:<tip> origin --delete <b>`. Allow exactly that form in `forbidden_hits`, which today matches any `--force`.

**W9 — Two test files were touched that the contract's `Files to touch` does not list.** `.claude/scripts/tests/test_skill_script_lookup.py` was modified: the CLN carve-out changes an existing test's expectation for CLN. `.claude/scripts/tests/test_cleanup_delivered_trials.py` is new. Both are justified: decision 2 and trials T1 to T4. They sit in the same area (`uncategorized`), so this is not off-area drift. The contract's file list still needs both added. The carve-out does not weaken the PRM guard, which a new test re-pins.

**W10 — Another live session can still lose a clean, merged tree; T4 is not recorded.** `cleanup_delivered.py:452-474`; `tests/test_cleanup_delivered_trials.py:278`
There is no probe on POSIX, and on Windows the probe cannot see a Git Bash shell (T3). Only this session's own folders count as standing. So a parallel Claude session working in an owned tree gets that tree removed when it is clean and merged. Tracked work is safe, but ignored content is lost and the session is left in a missing folder. The contract accepts this, but the brief says "never touch another session's worktree". T4 (the manual trial) is still a skip stub. Record it in the PR before merge, and state this residual risk in the PR description.

**W11 — A removal can reach outside `.claude/worktrees/` and delete ignored files that cannot be regenerated.** `cleanup_delivered.py:498-522`
Any registered linked worktree, anywhere on disk, that holds an owned branch is removed. So is any worktree sitting at the brief's `worktree:` path. `git worktree remove` deletes ignored files: `.env`, local databases, caches. `skills/ship/SKILL.md` says "Do not remove a worktree the user entered by path for their own purposes". The contract does not limit where an owned worktree may sit.
Suggest: remove a worktree only when `flat_worktree.is_flat(main_root, path)` holds. Keep the others as `left` with a new reason, which needs a contract amendment, or `holds-foreign-branch`-style wording. Question for the user.

## INFO

- **I1** — The skill blocks (`skills/pr-merged/SKILL.md:448-449`, `skills/advance/SKILL.md:486-487`) do not stop when `CLN` is empty. They run `cd "$(py -3 "" ...)"` and `py -3 "" ...`. Wrap them in `if [ -n "$CLN" ]; then ...; else echo "CLEANUP: script not found"; fi`.
- **I2** — The fallback `item["head"] or "HEAD"` (`cleanup_delivered.py:440, 445`) reads the main checkout's HEAD, because the cwd is the main root. Use `git -C <path> rev-parse HEAD`, or keep the tree as `unverifiable`.
- **I3** — When a brief is absent at the ref, `find_brief` reads it relative to the main root, not to `--from` (`cleanup_delivered.py:296-299`, after `_in_dir` exits). It fails safe, because the brief's branch is not owned.
- **I4** — `build_line` returns more than 600 characters when `finish` is present (`:648`). `_quote` is POSIX-only: PowerShell does not accept `'\''`, and the session shell here is PowerShell. `py -3` does not exist on POSIX hosts (the Cursor manifest).
- **I5** — `forbidden_hits` does not scan for `switch` or `checkout` (INV-5).
- **I6** — On `Halt`, the worktrees still planned are dropped from `items` (`:695-697`), so the report under-counts what was left.
- **I7** — `_is_link` treats every reparse point as a link: OneDrive placeholders, dedup files, AppExecLinks. Directories fail safe (`rmdir` on a non-empty folder fails). Prefer `st_reparse_tag in (IO_REPARSE_TAG_SYMLINK, IO_REPARSE_TAG_MOUNT_POINT)`.
- **I8** — When PyYAML is missing, `load_records_at` silently skips every record (`pr_merged.py`, the new reader), and the reason reads "has no completion record". It fails closed but misleads.
- **I9** — Small departures from Data Shapes. A dry-run Directory Link lacks `kind` and `target_survived`. Worktree items merge in the Owned Worktree fields (`source`, `head`, `locked`). The Reading key is `records_pull_request`. All acceptable.
- **I10** — `find_nested` walks every ignored folder in full. A real (non-junction) `node_modules` makes that slow. Correctness is not affected.

## Checked and clean

- INV-1: a fetch failure gives `unverifiable`, exit 10. The status, records and delivery are all read at `origin/<default>`. Nothing is mutated before the verdict.
- INV-3: the order is status, then ancestor, then nested, then standing, then dry-run, then probe, then links, then a non-forced removal. Branches are deleted only after `merge-base --is-ancestor`. A missing remote object reads `not-in-default`, which is the correct closed answer.
- INV-4: links are found with `os.lstat` plus `FILE_ATTRIBUTE_REPARSE_POINT` or `S_ISLNK`, and are never descended into. Directory links on Windows use `rmdir`.
- INV-5: no forbidden tokens. The forbidden-token scan has a positive and a negative control.
- INV-6: the rename probe and the rename back, with `Halt` on a failed rename back. The finish command is single-quoted with the apostrophe escape. Every module is imported before any removal.
- INV-7: remote deletion is off by default. A gh failure gives `unverifiable`. An open pull request keeps the branch.
- `flat_worktree.locked`, `load_records_at`, `load_delivery_at` and the `is_advance_worktree` alias match the contract's Extension Points.
- The version is 0.9.0 in all five entries.
- `ship` and `task` no longer tell anyone to prune.

## Janitor

- `MECHANISMS.md`: added **Delivery cleanup** (Universal).
- `VOCABULARY.md`: added **Delivery cleanup**, **Owned set** and **Standing tree**.
- `JOURNAL.md`: added "A fallback that finds the brief by the caller's own branch must prove the brief belongs to this contract", with Trigger post-impl divergence (W1/W2).
- `INTEGRATION.md`: not present in this repository, so nothing to update.
