# Pass-2 review: Delivery cleanup (issue #50), fullstack-code-reviewer

**State reviewed:** the uncommitted working tree on `feature/50-auto-cleanup-delivered-worktrees`, on top of origin/master 0c4cdec. This was a cold-context pass. I formed my own findings first and only then read the pass-1 report (W1-W11, I1-I10).
**Contract:** `.claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md` (approved, revision 2)
**Verdict:** pass-with-findings

No CRITICAL findings. I found no path that deletes uncommitted or unpushed tracked work:
- Every worktree removal is a non-forced `git worktree remove`.
- It runs only on a registered entry that passes `is_flat`, is clean, and has its HEAD in `origin/<default>`.
- Every branch delete comes after `merge-base --is-ancestor`.
- The remote delete carries the one allowed lease form.

Two WARNs still let a run act on another work item or report the wrong state. Fix them before merge:
- **F2** (residual of W1) is ownership.
- **F1** is new. The W4 fix introduced it.

Tests were not run, as instructed. `check_version_bump.py` was not re-run either.

---

## WARN

**F1: In `/advance`, the cleanup's `cd` to the main root now runs before Step 3's final `pr_merged.py --status` call (new, introduced by the W4 fix).** `skills/advance/SKILL.md:450` (the `cd`) vs `:471` (`py -3 "$PRM" --contract <slug> --status --json`); `$PRM` is the relative path `.claude/scripts/pr_merged.py` in vendored mode (`:46-47`).

The session shell keeps its working directory between calls. After Step 2.5 it stands in the main checkout, so Step 3 goes wrong in two ways:
- **In vendored mode** it re-resolves `$PRM` to the main checkout's copy, which is stale or missing. The lesson was "never the main checkout's copy", and this repeats that defect.
- **In every mode** `pr_merged.py` reads `.claude/concepts` and `.claude/orchestrator/results` relative to that working directory (`pr_merged.py:42-43`, `load_records` at `:3283`). So the final Completion and Next-command lines come from the main checkout's out-of-date working tree.

The rest of the session also stays in the main checkout, which goes against "work happens in a worktree".

The `cd` also protects nothing. `--from "$START"` already puts the starting tree in the standing set, so that tree is deferred whatever the shell's folder is.

Fix: run the two lines in a subshell, `( cd "$(py -3 "$CLN" --print-main-root)" && py -3 "$CLN" --contract <slug> --from "$START" ... --json )`, in both skills. Or put Step 2.5 after Step 3's status call and before the report is printed. Add a skill-text test that no step after the cleanup block uses a relative script path, or that the block is a subshell.

**F2: The brief fallback still adopts a sibling item's brief whose `contract:` is unset (W1, partly fixed).** `.claude/scripts/cleanup_delivered.py:310-324`

The W1 fix rejects a fallback brief only when `contract:` is set and names another slug (`:320-322`). A brief that reads `contract: none` passes. That is the common unset value: this item's own brief carries it. The fallback reaches the starting tree's branch when all three hold:
- the contract has no `**Work Item Brief:**` header, or the header path is missing on disk under `--from` (see F6);
- no recorded pull-request head gives a brief, because `gh_pr` failed or the records lack `pull_request`;
- the session stands in item Y's tree.

In that case Y's brief, branch and `worktree:` join this contract's Owned set. The test at `test_cleanup_delivered.py:1665` says so outright: "no contract check can reject [it], so only the ORDER keeps the run on this item's own brief". There is no test for the case where the order does not save it.

What happens to Y today:
- Y's tree is the start tree, so it is deferred.
- Y's local branch reads `checked-out`.
- Y's **remote** branch is deleted under `remove-remote` when its tip is in `origin/<default>` and it has no open pull request, for example a freshly pushed branch with no commits yet. No commit is lost, but INV-2 ("only members of the Owned set") is broken.
- The deferred tree also gets a `finish:` line for a tree that is not this item's.

Fix: take the starting branch's brief only when its `contract:` positively names the slug. A brief reached through a recorded, GitHub-verified head may stay "unset or this slug". Add a test: the sibling brief reads `contract: none`, there is no recorded head, the session starts in the sibling's tree, and `--remove-remote` is given. Assert that nothing of the sibling appears in the report.

**F3: A cut advance-worktree name can still claim an in-flight sibling's advance worktree (W2 residual).** `cleanup_delivered.py:545-552` and `other_slugs` `:340-344`

The W2 fix (exact `flat_name` equality) is correct for names that were not cut. When this slug is longer than 43 characters, `flat_worktree._cut` cuts the name at a hyphen (`flat_worktree.py:56-63`). The cut can equal the full name of a shorter sibling slug.

Example:
- This slug is `2026-10-15-auto-cleanup-delivered-worktrees-v2`, so its name is cut to `YYYYMMDD-advance-2026-10-15-auto-cleanup-delivered-worktrees`.
- That is exactly the name of sibling slug `2026-10-15-auto-cleanup-delivered-worktrees`.

The `ambiguous-name` guard only sees contracts committed at `origin/<default>`, so an in-flight sibling, whose contract lives only on its own branch, is claimed. The docstring's "which the exact form covers" is not true for that collision. Removal still needs the tree to be detached, clean, merged and not standing. On POSIX there is no probe, so a live sibling session's tree can go.

`other_slugs` also returns `[]` when `git ls-tree` fails, which turns the ambiguity check off. That is a quiet fail-open.

Fix: never claim a name of 60 characters, or 60 with its `-N` suffix. Read it as `ambiguous-name`. A detached advance tree loses nothing by staying. Make an `other_slugs` failure keep every advance-name item.

**F4: A dangling link anywhere in an owned tree halts the whole run, on every call, under a misleading reason.** `cleanup_delivered.py:468-474`

This is the W6 fix. Any untracked link whose target does not exist sets `run.halted`, and halting skips all later trees and all branches. That includes links inside an ignored real `node_modules`, where dangling links are ordinary. A link that was always dangling is not evidence that a removal took its target. Also, because every call re-runs, a single dangling link blocks the work item's cleanup forever, and the line reports it as `remove-failed`, as if a removal had been tried.

INV-9 says the probe's rename-back is the single halt. This second halt is not in the contract.

Fix: two options.
- Keep the halt only for a target that was removed during this run. Compare against `run.removed_paths` and the links removed earlier.
- Otherwise leave that one tree as `link-not-removed`, the closest closed-set reason, and continue.

Either way, amend INV-9 in the contract.

**F5: Several git reads fail open and turn a safety check off.** `cleanup_delivered.py`
- `_ignored_dirs` (`:402-404`) returns `[]` when `git ls-files` fails, so `find_nested` sees nothing and a nested worktree is removed together with its tree. That is exactly the loss INV-3 forbids. Fix: return `None` and leave the item `unverifiable`.
- `_tracked` (`:407-409`) returns an empty set on failure. Every tracked link is then treated as untracked and removed before `git worktree remove`, which then refuses a now-dirty tree and leaves it modified. Fix: same as above.
- `item["head"] or "HEAD"` (`:446`, pass-1 I2, **not fixed**) tests the main checkout's HEAD, because the working directory is the main root. Use `git -C <path> rev-parse HEAD`, or read the item `unverifiable`.
- `other_slugs` failing gives `[]` (see F3).

**F6: The brief header path is tested only on disk, relative to `--from` as given rather than the tree's root.** `cleanup_delivered.py:296-302`, `pr_merged.find_linked_brief` `:2367-2370`

`find_linked_brief` returns None as soon as the header path is missing on disk, so it does not fall through to the frontmatter scan. Three cases reach that:
- the finish command runs with `--from '<main root>'`, whose working tree is never updated (INV-5);
- the session's `$PWD` is a sub-folder of its tree;
- the brief exists only at the ref.

In each case the lookup falls to the gh-dependent fallback. If that finds nothing, the brief branch and its worktree are silently left out of the Owned set. They are not listed in `items`, and the run can still read `cleaned`. The contract says "the starting tree's root" (INV-2 step 1).

This fails safe, since nothing is deleted, but the cleanup silently skips its own feature worktree and its report says nothing about it. Fix:
- read the header path with `file_at_commit(ref, path)` first;
- resolve `--from` to `git rev-parse --show-toplevel`;
- add an item, or a reason in `delivery`, whenever no brief was found.

**F7: `orphan_folders` can crash after mutations, and it tells the reader to delete an unverified folder by hand.** `cleanup_delivered.py:565, 570-572`

`_is_link(path)` and `os.listdir(path)` are not guarded. A `PermissionError` or a vanished folder raises after worktrees were removed. Local and remote branches are then skipped, and the skill gets a traceback with exit 1 instead of a line. This was not checked against any exit code the skills handle.

The `detail` text "remove it by hand" also tells the model, through `--json`, to delete a folder on which git never ran its clean, ancestor or nested checks. The folder may hold the only copy of uncommitted work.

It never deletes. Answer to (d): confirmed, it only reports. Fix: wrap it in `try/except OSError`, and say "inspect it; it was never checked" instead.

---

## INFO

- **I-a**: Both skill blocks use two lines with no `&&` (`skills/pr-merged/SKILL.md` and `skills/advance/SKILL.md:450-451`), while the contract specifies `cd ... && py -3 ...`. A failed `cd` still runs the script. That is harmless, because the script itself runs `chdir(main_root)` and `START` is standing anyway. The F1 subshell form fixes this too.
- **I-b** (pass-1 I1, partly fixed): "If `CLN` comes back empty, stop" is prose after the block, not a shell guard. A model that runs the block verbatim executes `py -3 ""` twice. Harmless, but `if [ -n "$CLN" ]; then ...; else echo "CLEANUP: script not found"; fi` is cheap.
- **I-c** (W5, fixed): the `repair:` tail (`:691`) names only `git worktree repair '<path>'`. The folder is still at `<path>.probe`, and the rename step is only in `detail` (`:482`). Repair will not work until that rename is done, so put the rename into the line as well.
- **I-d**: the dry run (`:462`) reports `removed` before the vanished-target check and the in-use probe run, so a dry run can promise removals that a real run defers.
- **I-e** (pass-1 I6, open): when the run halts, the remaining planned worktrees are dropped from `items` (`:753`). The report under-counts what was left.
- **I-f** (pass-1 I4, open): `build_line` returns more than 600 characters when the `finish` or `repair` tail alone exceeds the budget (`:705`). This takes very long paths.
- **I-g**: `pr_merged.is_advance_worktree` (`pr_merged.py:895`) is no longer used by the cleanup since the W2 fix. It is dead public surface that the contract lists as consumed. Either drop it or note it in the contract.
- **I-h** (W10, open, accepted by the contract): there is no probe on POSIX, and T3 shows the Windows probe cannot see Git Bash. A parallel session in a clean, merged, owned tree can still lose that tree's ignored content. T4 is still a `skip` stub (`test_cleanup_delivered_trials.py:316-317`). Record it in the pull request.
- **I-i**: `_real_target` maps a `\\?\UNC\...` junction target to a relative `UNC\...` path. That makes it read as vanished and triggers F4's halt.

---

## Pass-1 findings, checked

| Pass-1 | State now | Evidence |
|---|---|---|
| W1 sibling brief via starting branch | **partly fixed**: an unset `contract:` still passes | F2, `:320-322`; test `:1665` docstring |
| W2 advance prefix match | fixed for names that were not cut; **cut-name collision remains** | F3 |
| W3 main checkout's copy in the `$CLN` fallback | fixed (`[ -f "$PWD/.git" ]`, a test at `:907`) | — |
| W4 cleanup after the report | fixed, but **introduced F1** | `advance/SKILL.md:416` vs `:465-471` |
| W5 repair not in the line | fixed (`:690-691`); rename step missing | I-c |
| W6 target survival, relative targets | fixed (`:115-116`, pre-removal check); **new liveness defect** | F4 |
| W7 protected names at the worktree stage | fixed (`:537-538`, tests `:1416-1441`) | — |
| W8 remote check-then-act | fixed (`:654-655`, allowed lease form) | — |
| W9 files outside Files to touch | fixed (contract lines 461-462) | — |
| W10 other live sessions / T4 | open, accepted | I-h |
| W11 removal outside `.claude/worktrees` | fixed (`is_flat` → `outside-worktrees-folder`, `:539-540`; reason added to the contract) | — |
| I2 `head or "HEAD"` | **not fixed** | F5 |
| I3 brief read relative to the main root | not fixed | F6 |

## Answers to the focus questions

- **(a)** I found no path that removes a worktree outside `<main root>/.claude/worktrees/<one segment>`. Every planned item goes through `is_flat`, and the main checkout and landing worktrees are skipped first. Items outside the true Owned set can still enter it through F2 (fallback brief) and F3 (cut-name collision).
- **(b)** These fail open: F5 (`_ignored_dirs`, `_tracked`, `HEAD` fallback, `other_slugs`) and F7 (crash after mutation). Everything else fails closed: fetch, status, merge-base with a code other than 0 or 1, ls-remote, gh, for-each-ref. A failure of `worktree_entries` during the branch stage is covered by git's own refusal to delete a checked-out branch.
- **(c)** The order is right: clean, ancestor, nested, standing, dry-run, vanished-check, probe, links, remove. Links are found with `lstat` and are never entered. The vanished-target halt is over-broad (F4) and is not in the contract.
- **(d)** The orphan report never deletes. It can crash (F7).
- **(e)** A name that was not cut cannot claim a sibling. A cut name can (F3).
- **(f)**
  - The quoting is fine.
  - The `$PWD/.git`-is-a-file rule is correct. A sub-folder `$PWD` just yields an empty `CLN`.
  - `--from "$START"` is captured before the `cd`, which is correct and tested by running the block.
  - An empty `CLN` is guarded by prose only (I-b).
  - The `cd` ordering is wrong in `/advance` (F1).
- **(g)** Gaps between the contract and the code:
  - INV-9 names a single halt, but the code has a second one (F4).
  - INV-2 step 1 says "the starting tree's root", but the code uses `--from` as given (F6).
  - The contract's `cd ... &&` form is not used (I-a).
  - `is_advance_worktree` is listed as consumed but is unused (I-g).
  - INV-8's 600-character cap can be exceeded by the tail (I-f).

## Janitor

- `JOURNAL.md`: appended two entries under the trigger `post-impl divergence`:
  - "An unset ownership field is not proof of ownership" (F2). It corrects the pass-1 entry's "unset or this slug" clause.
  - "A skill step that moves the shell must come after every later step that reads the working tree" (F1).
- `MECHANISMS.md` and `VOCABULARY.md`: already janitored in pass 1. Nothing new.
- `INTEGRATION.md`: not present in this repository.
- Gate Output: `fullstack-code-reviewer-pass2.gate.json`. It supersedes `fullstack-code-reviewer.md`.
