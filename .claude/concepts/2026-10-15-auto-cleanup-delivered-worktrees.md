# Concept Contract — Clean up worktrees and merged branches automatically once a work item is delivered

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-15
**Requested by:** user
**Status:** implemented
**Implemented:** 2026-10-16, automatically, by pr_merged.py after https://github.com/lneninger/claude-agentic-auto-improve/pull/52; 3 checklist items from review reports, 0 with no structured evidence; not performed (disclosed on #50): Implementation matches Data Shapes exactly; owner confirmed resolved: none
**Work Item Brief:** .claude/work-items/2026-10-15-50.md
**Tracking issue:** #50

> **Protocol:** filled in by `data-architect`. Implementer agents refuse to run unless `Status: approved` or `Status: implemented`. The `concept-gate.py` hook reads `Files to touch` to decide whether Edit/Write/MultiEdit is allowed.

**Revision 2 (2026-10-15):** applies the four user decisions (run timing, script location, brief lookup, remote switch) and answers each critic finding. The answers are in `## Critique`, marked `→ Addressed by:`.

**Revision 3 (2026-10-16):** after the first implementation review the user approved these amendments: removal limited to `.claude/worktrees/` (new reason `outside-worktrees-folder`); advance-worktree names match by prefix only when cut at the 60-character limit; the remote delete uses one `--force-with-lease` form; the two test files added to Files to touch; the review is folded into the one implementation block (no separate review sub-task); INV-9 has a single halt rule; the skills' `cd` runs in a subshell. Status stays `approved`.

---

## Business Concept

- **What is this thing, in domain language?**
  Once a contract is **implemented on the default branch**, its work item is finished. Its worktrees and merged branches are left over and are only clutter. **Delivery cleanup** removes them with no manual step. It removes only what belongs to that work item. It removes only what is provably already in `origin/<default>`. It removes nothing a person or another session may still be using. Today `/pr-merged` Step 6 only *offers* three manual git lines. The delivery of StockToolScalpingMachine#469 showed three ways those lines go wrong as written:
  - the session stands inside the tree it is removing;
  - a `node_modules` junction can take its real target down with the worktree;
  - `git branch -d` refuses a merged branch unless the current branch is the one it merged into.

  This contract replaces the offer with one tested script, `cleanup_delivered.py`. **Every** call of `/pr-merged` and `/advance` runs it. It is idempotent. Until the records pull request has merged it says "not delivered yet" and removes nothing. The first call after that merge removes everything it safely can. It prints a single line saying what it removed and what it kept, with the reason for each item it kept. Remote branches are deleted only when the caller passes `remove-remote`.

- **Existing VOCABULARY.md terms that apply:** **Contract Delivery**, **Completion Verdict**, **Records pull request**, **Main checkout**, **Flat worktree**, **Worktree segment**, **Tracking Issue** (all Universal tier).

- **New terms proposed for VOCABULARY.md (Universal tier):**
  - **Delivery cleanup** — the automatic removal of the worktrees and local branches that belong to a work item. Remote branches are removed too only with `remove-remote`. It acts only once the contract reads `Status: implemented` at `origin/<default>` and every sub-task has a GitHub-verified completion record there. It removes nothing whose commits are not already in `origin/<default>`. It runs on every `/pr-merged` and `/advance` call, and reads "not delivered yet" until then. Performed by `.claude/scripts/cleanup_delivered.py`.
  - **Owned set** — the branches and worktrees that belong to one work item, and nothing else.
    - **Branches:** the linked brief's `branch:`, `task/<slug>/<id>` for each sub-task in the handoff, and `docs/<slug>-records`. The linked brief is found by rule I-17, `find_linked_brief`, or else by the `branch:` fallback in INV-2.
    - **Worktrees:** a linked worktree with an owned branch checked out; or the one at the linked brief's `worktree:` path; or a detached advance worktree whose name matches this slug and no other.

    Anything outside the set is never examined beyond the worktree listing.
  - **Standing tree** — a worktree that the running session, its shell or any other process currently holds, whether by standing in it or by keeping a file open in it. A standing tree is *deferred*: it is left entirely untouched, and the next call from somewhere else removes it.

---

## End-User View

Not applicable. Reason: `Files to touch` names no Angular UI surface. This is a plugin workflow script plus skill text. Its only user surface is the one-line cleanup report inside `/pr-merged` and `/advance`, specified under Data Shapes.

---

## Data Shapes

### Entities

Not applicable. Reason: the script keeps no persistent state. Every run re-derives the Delivery Reading and the Owned set from git and GitHub. It writes no tracked file and no state store.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| **Delivery Reading** | contract slug; default branch; contract status at `origin/<default>` (string or none); sub-task ids (from the handoff at `origin/<default>`); delivered (bool, from `pr_merged.is_delivered` over records read at `origin/<default>`); open records pull request (url or none, from `pr_merged.open_records_pull_requests`); verdict: `delivered` \| `not-delivered` \| `unverifiable`; reasons (list of text, the first is shown) | Gate of every run. Anything except `delivered` ends the run before any mutation |
| **Owned Branch** | name; source: `brief-branch` \| `sub-task` \| `records` | Member of the Owned set |
| **Owned Worktree** | absolute path; checked-out branch or none; head sha; source: `owned-branch` \| `brief-worktree` \| `advance-name`; locked (bool) | Member of the Owned set |
| **Directory Link** | path inside the worktree; target path; kind: `junction` \| `symlink`; removed (bool); target survived (bool) | One per untracked link found in an owned worktree |
| **Cleanup Item** | kind: `worktree` \| `local-branch` \| `remote-branch`; name or path; action: `removed` \| `left` \| `deferred` \| `already-gone`; reason (closed set below; required when `left` or `deferred`); files (list of path; required for `uncommitted-changes`, `unpushed-commits`, `nested-worktree`); detail (commits, git message); links (list of Directory Link, worktrees only) | One per member of the Owned set. A branch yields up to two items: local and remote |
| **Cleanup Report** | contract slug; main root; remove_remote (bool); outcome: `cleaned` \| `partial` \| `nothing-owned` \| `not-delivered` \| `unverifiable`; delivery (Delivery Reading); items (list of Cleanup Item); line (the one-line summary); finish_command (one line, present only when an item is `deferred`); dry_run (bool) | The script's whole output under `--json`, and `line` alone otherwise |

**Reason closed set.** A Cleanup Item that is `left` or `deferred` carries exactly one:

- `uncommitted-changes` — files named.
- `unpushed-commits` — HEAD is not an ancestor of `origin/<default>`; the changed files are named.
- `nested-worktree` — an ignored folder inside the tree is itself a git worktree; its path is named.
- `not-in-default` — the branch tip is not an ancestor of `origin/<default>`.
- `checked-out` — the branch is held by the main checkout or by a kept worktree.
- `locked`
- `holds-foreign-branch` — a brief-named worktree now holds a branch outside the Owned set.
- `ambiguous-name` — an advance-style name matches two or more contract slugs.
- `standing-tree` — deferred.
- `in-use` — deferred.
- `link-not-removed`
- `remove-failed`
- `delete-failed`
- `open-pull-request`
- `protected-name`
- `remote-kept` — `remove-remote` was not given.
- `outside-worktrees-folder` — a registered worktree that is not a direct child of `<main root>/.claude/worktrees/` (`flat_worktree.is_flat` is false) holds an owned branch; it is kept, never removed.
- `unverifiable`

**Invariants**

- **INV-1 (delivered only, every call).** Nothing is mutated unless the Delivery Reading is `delivered`. That needs all three:
  - `git fetch origin <default>` succeeded;
  - the contract file at `origin/<default>` reads `Status: implemented`;
  - `is_delivered` holds over the completion and delivery records read **at `origin/<default>`**, never from the working tree.

  Before that point only a fetch, git reads, `ls-remote` and `gh pr list` run. The script runs on every `/pr-merged` and `/advance` call. While the records pull request is still open it reads `not-delivered`, and its first reason is `records pull request <url> not merged yet`. Its `line` ends with the rerun hint `runs again on the next /pr-merged or /advance`. The exit code is 5, which the skills treat as normal, never as a failure.

- **INV-2 (owned only).** Only members of the Owned set are examined or changed. Never the main checkout. Never a landing worktree (`land_contract.is_landing_worktree`). Never the default branch, `master` or `main`. Ownership is decided by checked-out branch or by exact brief path, never by folder name alone. Sub-task worktrees are named `<date>-task-<task id>` with no slug, so a sibling contract's `t1-backend` folder looks identical. The one rule that goes by name, the advance worktree, needs the name to match this slug and no other contract slug at `origin/<default>`.

  **Brief lookup:**
  1. Call `pr_merged.find_linked_brief(<contract text at origin/<default>>, slug)`, rule I-17: the `**Work Item Brief:**` header first, then the one brief whose `contract:` names the slug. The working directory is the starting tree's root, given by `--from`.
  2. If that finds nothing, fall back to `pr_merged.brief_for_branch(<head>, origin/<default>)`. `<head>` is the head branch of each recorded pull request, from the delivery record and the sub-task records, read with `gh pr view --json headRefName`, plus the starting tree's current branch. This fallback matches the brief's own `branch:` field, so a brief carrying `contract: none` is still found.
  3. The chosen brief's frontmatter is read at `origin/<default>`, or from disk when the file is absent there.

- **INV-3 (nothing tracked lost).** A worktree is removed only when all of these hold:
  - `git status --porcelain` is empty;
  - its HEAD is an ancestor of `origin/<default>`;
  - it is not locked;
  - it is not a standing tree;
  - no ignored folder inside it contains a `.git` entry. A nested worktree under the ignored `.claude/worktrees/` reads `nested-worktree`.

  Other ignored content is deleted with the tree. That covers `.venv/`, build output and logs. Ignored means regenerable, and this is accepted and stated. A local or remote branch is deleted only after `git merge-base --is-ancestor <tip> origin/<default>` passes. `git branch -D` is used only after that check, never otherwise.

- **INV-4 (link first, alone, last-moment).** Untracked links are removed only after every INV-3 check and the INV-6 probe have passed for that worktree, immediately before `git worktree remove`.
  - **Removal:** every untracked junction or symlink anywhere in the tree is removed as the link entry itself. A directory link uses `os.rmdir`, a file link `os.unlink`. Its target's existence is re-checked afterwards.
  - **Detection works on every supported Python, including versions before 3.12** (no `os.path.isjunction` there). The walk uses `os.scandir` and tests each entry with `os.lstat`. On Windows an entry whose `st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT` is set is a link; elsewhere `stat.S_ISLNK`. A link is never descended into. Before 3.12 `DirEntry.is_dir(follow_symlinks=False)` reports a junction as a directory, so that test is never used.
  - **Failures:** a link that cannot be removed leaves the worktree `link-not-removed`. If `git worktree remove` then fails, the item is `remove-failed`, and `detail` lists each removed link with its target so it can be recreated.

- **INV-5 (never force, never global).** None of these, anywhere:
  - `git worktree remove --force`;
  - `git worktree prune`, which would also remove other items' stale entries;
  - `rm -rf` or `shutil.rmtree` on a worktree;
  - `switch` or `checkout` in any tree.

  One force form is allowed, and only that one: the remote delete's lease, `git push --force-with-lease=refs/heads/<b>:<sha> origin --delete <b>`, where `<sha>` is the tip the ancestor check used (INV-7). A bare `--force`, `-f` or `--force-with-lease` stays forbidden.

- **INV-6 (standing tree deferred, one line).** A worktree is `deferred` and left untouched in two cases. It reads `standing-tree` when it holds the script's own working directory or `CLAUDE_PROJECT_DIR`, on every platform. On Windows it reads `in-use` when it fails the probe, which renames the folder to a sibling name and back at once. On POSIX a rename always succeeds, so the probe is skipped there and only the standing-tree rule applies.

  Both cases print the same `finish_command`: `py -3 '<script>' --contract '<slug>' --from '<main root>'`.
  - `<script>` is the absolute path of the running copy. That copy was found **from the plugin root first, then the current worktree's copy, never the main checkout's copy**.
  - Every path is single-quoted, so nothing in it is expanded. A `'` inside a path is written `'\''`.
  - All modules are imported before any removal.
  - The line works once no process stands in the tree: after the session has left it, or from any terminal outside it.
  - The next `/pr-merged` or `/advance` call from a session that does not stand in the tree also clears it, because every call reruns the cleanup. The line is a fallback, not the only path.
  - **Trial T3 finding (recorded 2026-10-15):** the rename probe is blind to the session's own Git Bash. Git for Windows' msys bash opens its working directory with share-delete, so a bash process that stays in a tree does not block the probe rename. A Python or `cmd` process in the folder does. So the probe cannot see the session's own shell, and the standing-tree rules above (the script's working directory, `CLAUDE_PROJECT_DIR`, and the `--from` starting tree) are the layer that covers it.

- **INV-7 (remote only when asked, only when still there).** Without `--remove-remote`, remote branches are never changed. Each owned branch that `ls-remote` still lists is reported `left` with `remote-kept`. With `--remove-remote`, a remote branch is touched only under all of these:
  - a fresh `git ls-remote --heads origin <b>` lists it. A branch GitHub has already deleted reads `already-gone`.
  - its tip passes INV-3's ancestor check. Otherwise it reads `not-in-default`.
  - `gh pr list --head <b> --state open` reports none. Otherwise it reads `open-pull-request`.
  - `gh` answered. If `gh` is unavailable the branch reads `unverifiable`.

  Only then does `git push origin --delete <b>` run.

- **INV-8 (one bounded line).** The report's `line` is one line, never longer than 600 characters:
  - **Delivered:** `CLEANUP <slug>: removed <n> (<names>); left <m> (<name>: <reason>[ [<file>, <file>, <file>, +k more]]; ...)`. Each list names at most 8 items and then adds `+k more`. Each item names at most 3 files. Names have control characters removed.
  - **Something deferred:** the line also carries `; finish: <finish_command>`.
  - **Not delivered:** `CLEANUP <slug>: not delivered yet (<first reason>); nothing removed; runs again on the next /pr-merged or /advance`.

  The full lists stay in the JSON. No tracked file is written.

- **INV-9 (order, isolation).** Worktrees come first, then local branches, then remote branches. One item's failure is recorded and the run goes on to the next item. There is ONE halt rule: the run stops all further mutation when it can no longer be sure what it has changed. That happens in two cases only: a probe could not rename the folder back (reported with the repair line `git worktree repair '<path>'`), and a link that this run is about to remove has lost its target (reported as `remove-failed` with the target named, W6). Nothing else halts. A dangling link inside an ignored folder such as `.venv/` or a real `node_modules/`, a failed git read, or a failed removal is recorded for that one item and the run goes on. A read that fails (`ls-files`, the tree's own HEAD, the other contracts' slugs) never turns a safety check off: the item is kept as `unverifiable`.

### Events

Not applicable. Reason: the script is a synchronous command with no listeners. Its Cleanup Report goes back to the calling skill, which prints `line`. No domain event is persisted.

### Commands (if any)

| Name (imperative) | Handler | Payload | Possible rejections |
|-------------------|---------|---------|---------------------|
| Clean up delivered work item | `.claude/scripts/cleanup_delivered.py` | `--contract <slug>` `--from <starting dir>` [`--remove-remote`] [`--dry-run`] [`--json`]; also `--print-main-root` (prints `flat_worktree.describe()["main_root"]` and exits) | `not-delivered` (exit 5, nothing touched, normal); `unverifiable` (exit 10, nothing touched); usage (exit 2). Exit 0 = `cleaned` or `nothing-owned`; exit 3 = `partial` |

---

## Reused Mechanisms

- **Flat worktree helper** (`flat_worktree.py`): **extended**. `worktree_entries` also records `locked` from the porcelain listing. `describe()` is the single source of `main_root`, used by the script and, through `--print-main-root`, by the skills. Ownership relies on the helper's naming, `<date>-<action>-<slug>` with `-2…-9`.
- **`pr_merged.py` readers**: **extended, consumed by import**, following the precedent of `auto_improve_finish_install.py` importing `pr_merged.load_slot`.
  - Consumed as-is: `find_linked_brief` (I-17), `brief_for_branch`, `read_contract_status`, `parse_handoff`, `is_delivered`, `file_at_commit`, `default_branch_or_none`, `branch_for`, `records_branch_prefix`, `open_records_pull_requests`, `parse_brief_frontmatter`, `gh_pr` and `DELIVERY_RECORD_NAME`.
  - Extended by two readers that work at a ref, `load_records_at(ref, slug)` and `load_delivery_at(ref, slug)`. They use the same YAML parse as `load_records` and `load_delivery`.
  - Extended by one public alias, `is_advance_worktree = _is_advance_worktree`.
  - No new brief reader exists. **Enum check:** the Completion Verdict set is unchanged.
- **Two-layer Claude path resolution**: consumed as-is. `main_checkout_root` and `tree_kind` come through `_claude_paths.py` by way of `flat_worktree.describe`. No script or skill line runs `--git-common-dir`.
- **Plugin script lookup in skills** (the `$PRM` block in `skills/pr-merged/SKILL.md`): **extended in order**. `$CLN` tries `$CLAUDE_PLUGIN_ROOT/.claude/scripts/cleanup_delivered.py` first, then the installed-plugin records and the newest cache folder, then the current worktree's `.claude/scripts/cleanup_delivered.py`. That path is made absolute before any `cd`. It never tries the main checkout's copy.
- Not registered in `MECHANISMS.md` but reused as code: `land_contract.is_landing_worktree`, plus its habit of moving out of a tree before removal and re-checking just before. Also the CLAUDE.md version-bump rule (`check_version_bump.py`): a minor bump, 0.8.7 → 0.9.0, in all five entries.

---

## New Mechanisms (if any)

- **Name:** Delivery cleanup (`cleanup_delivered.py`)
- **Purpose:** the plan, check and act sequence of INV-1 to INV-9 for one contract, idempotent across calls.
- **Why an existing mechanism was not sufficient:**
  - `land_contract.worktree_remove` refuses everything that is not a landing worktree, by design (C1). Loosening it would weaken the landing's guard.
  - `flat_worktree.py` only plans and creates, and its suite pins that it never mutates an existing tree.
  - `pr_merged.py` runs its verdict inside a tree that may be one of those to remove, and before the records pull request has merged.
- **Proposed location:** `.claude/scripts/cleanup_delivered.py`, beside `flat_worktree.py`.
- **Extension seam:** a new owned-branch source is one more entry in the Owned set builder. A new reason is one more value in the closed set. `/ship` and `/task` can call the same script.
- **Will this be promoted to `MECHANISMS.md` after implementation?** yes

---

## Extension Points

- **`pr_merged.py`:** add `load_records_at` and `load_delivery_at` next to `load_records`, plus the alias `is_advance_worktree`. No change to `evaluate_completion`, `advance` or `next_command_for`.
- **`flat_worktree.worktree_entries`:** gains a `locked` key, default false.
- **`skills/pr-merged/SKILL.md` Step 6** becomes "Clean up, automatically, on every call". After Steps 3 to 5 and any records pull request it runs `START="$PWD"; cd "$(py -3 "$CLN" --print-main-root)" && py -3 "$CLN" --contract <slug> --from "$START" [--remove-remote] --json`. It asks nothing, and exit 5 is normal.
  - **Subshell rule.** The `cd` runs inside a subshell, with no `&&` chaining outside it: `( cd "$(py -3 "$CLN" --print-main-root)" && py -3 "$CLN" --contract <slug> --from "$START" [--remove-remote] --json )`. The session shell keeps its own working directory, so a later step (`/advance` Step 3's `--status` call, which reads `.claude/concepts` and the records relative to the working directory) still sees the starting tree, and a failed `cd` cannot be followed by a script call from the wrong folder.
  - The skill accepts the parameter `remove-remote`, for example `/pr-merged 40 remove-remote`. It is off by default and passed straight through.
  - Step 7's `- Cleanup:` line is the script's `line`, verbatim.
  - The anti-patterns gain four entries: hand-running `git branch -d` or `-D`; running `git worktree prune`; composing the cleanup line as prose; deleting a remote branch without `remove-remote`.
- **`skills/advance/SKILL.md`:** the same command runs at the end of **every** `/advance` call, whatever the state, with the same `remove-remote` parameter.
- **`skills/ship/SKILL.md` Step 6 and `skills/task/SKILL.md` (lines about 495 and 563):** the manual `git worktree remove` + `git worktree prune` lines are removed. Delivered items are cleaned by delivery cleanup; an abandoned worktree uses `git worktree remove` alone, never prune.

---

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| `/pr-merged`, `/advance` skills | `cleanup_delivered.py` | subprocess, `--json` stdout, exit code | Cleanup Report | skill → script → skill |
| `cleanup_delivered.py` | `pr_merged.py`, `flat_worktree.py`, `land_contract.py`, `_claude_paths.py` | Python import, from the script's own folder | Delivery Reading inputs, worktree entries | script → modules |
| `cleanup_delivered.py` | git (local and `origin`); GitHub through `gh pr list --head` and `gh pr view` | subprocess | refs, porcelain, open-PR list, head branch | script → git / GitHub |

**Changes to existing integration surfaces:**
- [ ] `pr_merged.py` gains two at-ref readers and one public alias (tested in `test_pr_merged.py`).
- [ ] `flat_worktree.worktree_entries` gains the `locked` key (tested in `test_flat_worktree.py`).
- No C# or TypeScript side, and the repository has no `INTEGRATION.md`.

---

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold.

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

---

## Chat Tool Impact (REQUIRED when this contract adds or changes a REST endpoint or SignalR event)

Not applicable. Reason: no REST endpoint or SignalR event is added or changed. The plugin has no chat tool surface.

---

## Non-Goals

- Work items that are not delivered, meaning an open pull request, an unmerged branch, or a contract not yet `implemented` at `origin/<default>`. INV-1 reads them `not-delivered` and touches nothing.
- The landing worktrees' own lifecycle (`land_contract.py` P15).
- Syncing this change into other projects that carry a copy of the scripts. That is reported at the end, not done here. There is no in-repo mirror: scripts live once under `.claude/scripts/`, and skills once under `skills/`.
- Contracts flipped by hand before 2026-10-05, which have no records at `origin/<default>`. They read `not-delivered`.
- `/north-star`'s hand-written `git worktree add` line. It creates worktrees, not removes them, and no follow-up stub exists for it yet.
- Writing to the brief's run log, or to any tracked file.
- A background watcher for merges. The cleanup runs only when a skill is called.

---

## Confidence

Confidence: Medium.
- **High** on ownership, ordering, the ancestor rule and run timing, all verified against `pr_merged.py`, `flat_worktree.py` and `land_contract.py`.
- **Medium** on Windows holder behaviour. Trials T1 to T4 under Uncertain Assumptions settle it before the main tests are frozen.
- The design stays safe whichever way those trials come out. Every uncertain holder ends `deferred`, never partly removed.

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** a standalone `cleanup_delivered.py` that gates itself on the Delivery Reading. Every `/pr-merged` and `/advance` call runs it, from the main root. A standing tree is deferred, and the next call clears it.
  - Why: one tested script and both front doors. It is idempotent, it runs from outside the trees it removes, and it reuses the `pr_merged` readers, so there is no second verdict.
- **Option B (rejected):** clean up inside `pr_merged.py` at the `flipped` verdict.
  - Why rejected: at a flip the records pull request has not merged, so the contract is not `implemented` at `origin/<default>`.
- **Option C (rejected):** loosen `land_contract.worktree_remove`.
  - Why rejected: it weakens the landing's C1 guard.
- **Option D (rejected):** keep the offer and print better manual lines.
  - Why rejected: it fails acceptance criterion 1.
- **Option E (rejected):** delete remote branches by default.
  - Why rejected: the user chose off by default (decision 4), because a remote deletion is outward-facing.

---

## Uncertain Assumptions

- `VERIFIED via pr_merged.py:2915-2922, 3140`: the flip writes the contract in the starting tree, and a records pull request carries it. So `implemented` at `origin/<default>` appears only after that pull request merges. That is why the cleanup runs on every call.
- `VERIFIED via pr_merged.py:1032, 3827`: sub-task worktrees are named `<date>-task-<task id>`, with no slug.
- `VERIFIED via pr_merged.py:882-891`: `_is_advance_worktree` accepts a prefix match. That is why INV-2 requires the name to be unambiguous.
- `VERIFIED via pr_merged.py:2311-2330, 1964-1991`: `find_linked_brief` reads the header first, and `brief_for_branch` matches `branch:` exactly at a commit. This item's brief carries `contract: none`, and this contract's `**Work Item Brief:**` header is what finds it.
- `VERIFIED via check_version_bump.py:17-20` and `CLAUDE.md`: five version entries, and no mirror copy exists.
- **Trials run first, in the first TDD commit, before any other test is frozen.** Each one records its observed result in the test's docstring and in the pull request description:
  - `ASSUMED` T1: on Windows, `git worktree remove` on a throwaway worktree whose folder a subprocess holds as its working directory deletes contents before it fails. The design does not depend on the answer, because the probe always runs on Windows. The trial only documents why the probe is there. Verification: a real test that records the outcome.
  - `ASSUMED` T2: `os.rmdir` on a junction made with `_winapi.CreateJunction` (Windows), and `os.unlink` on a symlink (POSIX), leave the target and its file intact. Verification: a real test that can fail.
  - `ASSUMED` T3: once a Git Bash process changes directory with `cd` out of a tree, it no longer blocks the probe rename. Verification: a real test that starts `bash -c "cd <elsewhere> && sleep 5"` with its working directory in the tree and asserts the probe succeeds. A control in which bash stays in the tree asserts that the probe fails. If T3 fails, the design is unchanged: the starting tree simply reads `in-use` and is cleared by a later call. **Observed result (2026-10-15): the first form of this trial failed. A Git Bash process that STAYS in the tree does not block the probe rename (msys bash opens its working directory with share-delete), so the probe is blind to the session's own Git Bash. The `cd`-out half and the Python-holder control hold. INV-6's standing-tree rules (script cwd, `CLAUDE_PROJECT_DIR`, `--from`) are what cover the session's own shell.**
  - `ASSUMED` T4: whether the Claude Code process itself holds its working directory. This cannot be automated. The implementer runs one manual trial: a session that started in the main checkout and entered a worktree runs `cleanup_delivered.py --dry-run`, and the probe result is recorded in the pull request. Either answer is safe, because a held tree reads `in-use`.

---

## Failure Modes & Mitigations

- **FM:** A junction is followed and the real `node_modules` is deleted.
  - **Mitigation:** INV-4 detects reparse points through `lstat` and removes links alone, last thing before removal. Test T2 and the junction test cover it.
- **FM:** A sibling item's worktree with the same `t1-…` folder name is removed.
  - **Mitigation:** INV-2 decides ownership by branch.
- **FM:** Uncommitted, unpushed or nested-worktree work is lost.
  - **Mitigation:** INV-3: status clean, ancestor check, and a `.git` scan of ignored folders. Ignored regenerable content is deleted by design, as stated.
- **FM:** A cleanup run on a stale view deletes something.
  - **Mitigation:** INV-1 fetches first and reads only `origin/<default>`.
- **FM:** The cleanup never runs after the records pull request merges.
  - **Mitigation:** it runs on every `/pr-merged` and `/advance` call, and while not delivered its line carries the rerun hint.
- **FM:** The session's own tree is half-removed.
  - **Mitigation:** INV-6 defers it, and INV-4 runs only after the probe.
- **FM:** A new holder opens the folder between the probe and `git worktree remove`.
  - **Mitigation:** none closes that window. The tree is clean and its commits are already in `origin/<default>`, so nothing tracked is lost. The item reads `remove-failed`, and the report names the leftover folder.
- **FM:** A remote branch is deleted that should have stayed.
  - **Mitigation:** INV-7: remote branches are off by default; with `remove-remote` there is an ancestor check, an open pull request check, and `gh` unavailable keeps the branch.
- **FM:** The probe's rename-back fails.
  - **Mitigation:** INV-9 halts all further mutation and names `git worktree repair`.
- **FM:** The finish line is mis-expanded by the shell, or the report floods the context.
  - **Mitigation:** INV-6 single-quotes every path, and INV-8 bounds the line.

---

## Open Questions for User

None open. All four of the user's 2026-10-15 decisions are applied.

### Decisions recorded with the user (2026-10-15)

1. **Run timing.** The cleanup is idempotent and runs on every call of `/pr-merged` and `/advance`. Until the records pull request merges it reports "not delivered yet", removes nothing, and gives the rerun hint. The next call after the merge removes everything it safely can (INV-1).
2. **Script location.** Skills find `cleanup_delivered.py` from the plugin root first, then from the current worktree's copy, and never use the main checkout's copy. INV-6's finish line names that same copy.
3. **Brief lookup.** `pr_merged.find_linked_brief` (rule I-17), with a fallback through `brief_for_branch` on the recorded head branches. `briefs_naming_contract_at` is dropped (INV-2).
4. **Remote switch.** The skill parameter `remove-remote` maps to the script flag `--remove-remote` and is off by default. Without it, only local worktrees and branches are removed, and the remote branches still present are listed as `remote-kept`. With it, INV-7 applies. This replaces revision 1's Open Question about deleting without a prompt.

### Brief assumptions, resolved

1. **Trigger point** — decision 1 above.
2. **"Belongs to the work item"** — the Owned set (INV-2): the brief's two rules plus the records branch and the advance worktree, decided by branch.
3. **"Without a manual step"** — verified by `test_cleanup_delivered.py`. Its entry-point test runs on a real temporary repository with a bare `origin`, through three calls: first while the records pull request is open (`not-delivered`, nothing touched), then after it merges (cleaned), then again (a no-op). A text test checks that Step 6 and `/advance` run the script on every call and offer no manual lines.

---

## Critique

**Critic:** contract-critic
**Date:** 2026-10-15
**Verdict:** blockers-found

### Findings

- **[BLOCKER] The chosen trigger runs before the contract can read `implemented` at `origin/<default>`, so the run it is wired into always gets `not-delivered`**
  - **What is wrong:** `/pr-merged` Step 6 runs the script "after Steps 3 to 5 and any records pull request". That records pull request is a draft that a person merges later, so the flip reaches `origin/<default>` only after this run ends. INV-1 then refuses, and nothing in the contract re-runs the cleanup once the records pull request merges. Acceptance criterion 1 ("without a manual step") is therefore not met. The same applies to `/advance` step 5, which runs "after ... the records push". The question of which run first sees `delivered` is an Open Question presented as a settled decision.
  - **Prior artifact ignored:** `VOCABULARY.md:53` **Records pull request** ("the small docs-only **draft** pull request ... and on a flip the contract and the brief"); `skills/pr-merged/SKILL.md:335` ("push it and open a draft pull request"); this contract's own Option B rejection and `Uncertain Assumptions` line 1, which name this exact timing.
  - **Where in this contract:** `## Open Questions for User → Brief assumptions, resolved as decisions` item 1: "The closing step of `/pr-merged`, Step 6, runs on every run that names a contract ... The flip in `pr_merged.py` is *not* the trigger, because at that moment the records pull request is unmerged".
  - → Addressed by: user decision 1. INV-1 now runs on every `/pr-merged` and `/advance` call. The not-delivered reason names the open records pull request, and the line carries the rerun hint. `/advance` runs it on every call, not only after a landing. The entry-point test covers three calls: open, merged, no-op.

- **[BLOCKER] `$CLN` "resolved like `$PRM`", combined with `cd "<main root>" &&`, runs the main checkout's copy of the script, which may be stale or absent**
  - **What is wrong:** `$PRM` resolution tries the relative path `.claude/scripts/pr_merged.py` in the current tree first. After `cd "<main root>"`, that relative path points at the main checkout's copy. INV-5 forbids any `switch`/`checkout`, so nothing ever updates that checkout. In plugin-source mode, or in a vendored consumer, the cleanup and the `pr_merged` readers it imports then come from an old copy, or the file does not exist there at all. INV-6's finish line repeats the defect: it deliberately prefers "the main checkout's" copy over the running copy. The lesson is claimed as heeded by INV-6, but the Extension Point violates it.
  - **Prior artifact ignored:** `JOURNAL.md` **2026-10-04 — A root locator can return the consumer itself under vendoring**; `skills/advance/SKILL.md:46-47` (`S=.claude/scripts/pr_merged.py; if [ -f "$S" ]; then PRM=$S`).
  - **Where in this contract:** `## Extension Points`: "`cd "<main root>" && py -3 "$CLN" --contract <slug> --json` ... `$CLN` is resolved like `$PRM`". Also INV-6: "the main checkout's, then the running plugin copy".
  - → Addressed by: user decision 2. `$CLN` is resolved from the plugin root first, then the current worktree's copy, and made absolute before the `cd`. The main checkout's copy is never tried (Reused Mechanisms, the plugin script lookup). INV-6's finish line names the running copy, which was resolved the same way. The script imports `pr_merged` from its own folder, so the readers always match it.

- **[BLOCKER] The Owned set's brief linkage creates a parallel reader to `find_linked_brief`, and it would miss this work item's own brief**
  - **What is wrong:** The new `briefs_naming_contract_at(ref, slug)` reads "each linked brief" (plural) through the brief's `contract:` field. The existing linkage rule I-17 (`pr_merged.find_linked_brief`, `pr_merged.py:2311-2330`) reads the contract's `**Work Item Brief:**` header first, and otherwise takes exactly one brief whose `contract:` names the contract. That rule is not in the list of consumed readers. This work item's brief carries `contract: none` (`.claude/work-items/2026-10-15-50.md:14`), so a frontmatter-only scan would leave `feature/50-auto-cleanup-delivered-worktrees` and its worktree out of the Owned set.
  - **Prior artifact ignored:** `pr_merged.py:2311` `find_linked_brief` (I-17); `VOCABULARY.md:47` **Contract Delivery** ("the pull request the contract's own brief names", singular); the brief at `.claude/work-items/2026-10-15-50.md:14`.
  - **Where in this contract:** `## Reused Mechanisms`: "Extended by three reader functions ... `briefs_naming_contract_at(ref, slug)`". `## Business Concept → Owned set`: "Branches: the `branch:` of each linked brief".
  - → Addressed by: user decision 3. `briefs_naming_contract_at` is dropped. INV-2 calls `find_linked_brief` with the working directory at the `--from` tree root, then falls back to `brief_for_branch` on the recorded head branches and the starting branch. A required test covers a brief with `contract: none` that is found through the header, and one found through the `branch:` fallback.

- **[WARN] "Ignored files excepted" lets `git worktree remove` destroy ignored content, including a nested worktree, and Failure Modes does not list it**
  - **What is wrong:** INV-3 accepts a tree whose porcelain status is empty apart from ignored files. A non-forced `git worktree remove` deletes ignored files. `.gitignore:20` ignores `.claude/worktrees/`, so a legacy nested worktree inside an owned tree is invisible to the clean check and is deleted together with its own uncommitted work. `.venv/`, `*.log` and `.sync-state/` are deleted the same way. The phrase "nothing lost" overstates what INV-3 guarantees.
  - **Prior artifact ignored:** `VOCABULARY.md:55` **Flat worktree** ("A worktree inside another worktree is nested, never flat"); `MECHANISMS.md:63` (the `nested` refusal exists because nested trees were created before 2026-10-07).
  - **Where in this contract:** `## Data Shapes → Invariants` INV-3: "`git status --porcelain` is empty (ignored files excepted)". The gap is in `## Failure Modes & Mitigations`: "Unpushed or uncommitted work is lost."
  - → Addressed by: INV-3 is renamed "nothing tracked lost". A tree with any ignored folder containing a `.git` entry is left as `nested-worktree`, with its path named. The deletion of other ignored content is stated as accepted. A Failure Mode is added, and a required test covers a nested worktree.

- **[WARN] The printed report never names the files, although acceptance criterion 4 requires it**
  - **What is wrong:** Named files live only in `Cleanup Item.detail`. The INV-8 `line` format carries `<name>: <reason>` only, and the skills print `line` alone (Step 7's `- Cleanup:` is `line` verbatim). The person never sees which files kept a tree.
  - **Prior artifact ignored:** brief `.claude/work-items/2026-10-15-50.md:30` ("it is left alone, and the report names the files").
  - **Where in this contract:** INV-8: "`CLEANUP <slug>: removed <n> (<names>); left <m> (<name>: <reason>; ...)`". `## Extension Points`: "Step 7's `- Cleanup:` line becomes the script's `line`, verbatim".
  - → Addressed by: `Cleanup Item.files` is a required field. The INV-8 line carries up to three files per item plus `+k more`. A required test asserts that the file names appear in the printed line.

- **[WARN] Two of the three ASSUMED Windows behaviours have no verification that can fail before the tests are frozen**
  - **What is wrong:** Assumption 1, that `git worktree remove` deletes contents before it fails, is "verified" by a test of the rename probe. That test passes whether the assumption is true or false. The window between the probe's rename-back and `git worktree remove`, when a new holder can open the folder, appears nowhere in Failure Modes. Assumption 3 is deferred to a manual trial in the post-implementation review's Evidence, after the tests are written. The more important unknown, whether the Claude Code process itself holds the tree as its working directory, appears only in `## Confidence` and has no ASSUMED line or verification path. Assumption 2 (junction removal leaves the target) can be checked as written, using `_winapi.CreateJunction`.
  - **Prior artifact ignored:** `JOURNAL.md` **2026-10-05 — Count a host's size cap the way the host counts, and prove the cap with a real trial** ("put the trial result in the contract before freezing tests"); `JOURNAL.md` **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** ("prove it with one harmless invocation before the code depends on it").
  - **Where in this contract:** `## Uncertain Assumptions`: "Verification path: a test that holds a cwd from a subprocess ..." and "Verification path: a manual trial on Windows, recorded in the review's Evidence section". `## Confidence`: "or the Claude process itself, holds a handle on its working directory".
  - → Addressed by: trials T1 to T4 run in the first TDD commit, before any other test is frozen. T2 and T3 are real tests that can fail, and T3 has a control. T1 records its outcome, and the design is stated not to depend on it. T4, the Claude process, now has an ASSUMED line and a manual trial path, and either outcome is safe. The race window between the probe and the removal is now a Failure Mode. → Deferred: the trial results cannot go into this contract before approval, because this agent has no shell. They go into the test docstrings and the pull request description, before the dependent tests are written.

- **[WARN] The finish line can defer forever, and the contract never says where it must be run**
  - **What is wrong:** Under isolation by default, the session normally stands in the work item's own worktree. If the session process holds that tree, then rerunning `finish_command` from the same session hits `in-use` again. The contract does not say that the line works only after the session has left the tree, or from which shell it must be run. That is what decides whether acceptance criterion 9's "exactly one script line" actually finishes the cleanup.
  - **Prior artifact ignored:** `MECHANISMS.md:61` and `MECHANISMS.md:63` (the main-checkout guard and the flat worktree helper: sessions work inside a worktree); brief `.claude/work-items/2026-10-15-50.md:35`.
  - **Where in this contract:** INV-6: "Rerunning that line re-derives everything, and so is idempotent."
  - → Addressed by: INV-6 now says the line works once no process stands in the tree: after the session has left it, or from any terminal outside it. Because every `/pr-merged` and `/advance` call reruns the cleanup, the next call from a session that is not in the tree clears it with no line at all. The skill also moves its own shell out with `cd` before calling.

- **[WARN] The required test list leaves several destructive or safety paths untested, and the reviewer checks only the listed cases**
  - **What is wrong:** These paths have no required case: INV-7 open pull request kept, and `gh` unavailable giving `unverifiable` (the Open Question's "nothing can be lost" rests on both); INV-9 rename-back failure halting all mutation; `checked-out` (an owned branch held by the main checkout); `holds-foreign-branch`; `protected-name`; one item's failure not stopping the rest; a remote branch that is not in the default branch being kept; a standing tree detected through the script's starting directory (only `CLAUDE_PROJECT_DIR` is listed); `link-not-removed`; the INV-8 one-line shape with a reason for each item left (acceptance criterion 8). Criteria 1 to 7 and 9 each map to a listed case. Criterion 8 has none.
  - **Prior artifact ignored:** brief `.claude/work-items/2026-10-15-50.md:27-35` (acceptance criteria); `VOCABULARY.md:49` **Gate Output** (the reviewer's checklist is the TASK block's list, per `### 2. Review`: "each required test case in sub-task 1's TASK block").
  - **Where in this contract:** `## Implementation Handoff → 1. Cleanup → CONSTRAINTS`: "Required cases: delivered fixture cleaned; ... a source scan proving no "--force", no "worktree prune", no rmtree."
  - → Addressed by: every listed path is now a required case in sub-task 1's TASK block, mapped to its acceptance criterion. The added cases are: the open pull request; `gh` unavailable; rename-back failure; `checked-out`; `holds-foreign-branch`; `protected-name`; failure isolation; a remote branch not in the default branch; standing through the starting directory; `link-not-removed`; the one-line shape for criterion 8; `remove-remote` on and off; and `nested-worktree`.

- **[WARN] The order of link removal and the standing-tree checks is unstated, so a kept tree can be left partly changed**
  - **What is wrong:** INV-4 removes links "before `git worktree remove`". It does not say this happens after the clean, ancestor, lock, standing-tree and in-use checks. A tree that is then deferred, or that ends `remove-failed`, is left with its `node_modules` junction gone. That contradicts the proposed Standing tree rule, "deferred, never partly removed".
  - **Prior artifact ignored:** `land_contract.py:423-438` `worktree_remove` (check again "right before the removal"), which `## Reused Mechanisms` says is "kept".
  - **Where in this contract:** INV-4: "Before `git worktree remove`, every untracked junction or symlink anywhere in the tree is removed". INV-6: "A standing tree is *deferred*, never partly removed."
  - → Addressed by: INV-4 removes links only after every INV-3 check and the INV-6 probe have passed, immediately before removal. A deferred tree keeps its links, and a test asserts that. On `remove-failed`, `detail` lists each removed link with its target so it can be recreated.

- **[WARN] The forbidden-token source scan has no positive control**
  - **What is wrong:** The scan "proving no `--force`, no `worktree prune`, no rmtree" is required, but no case plants a token to prove that the scan catches it. A scan that matches nothing passes just as well.
  - **Prior artifact ignored:** `JOURNAL.md` **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** (Apply when: "any test that must prove a forbidden token is caught").
  - **Where in this contract:** `## Implementation Handoff → CONSTRAINTS`: "a source scan proving no "--force", no "worktree prune", no rmtree."
  - → Addressed by: a required positive control. The same scanner function runs on planted text that holds each forbidden token in plain form and must flag every one, then runs on the real source and must flag none.

- **[WARN] The skill derives the main root with `--git-common-dir` instead of the helper that already provides it**
  - **What is wrong:** `## Reused Mechanisms` says no script runs `--git-common-dir`. The new Step 6 text then derives `<main root>` with that same command, when `flat_worktree.py --describe` already prints `main_root` and `/ship` already uses it. That makes a second derivation of the same value.
  - **Prior artifact ignored:** `MECHANISMS.md:63` **Flat worktree helper** ("`--describe` prints `main_root`"); `MECHANISMS.md:42` (tree classification); `skills/ship/SKILL.md:268` ("`<main_root from flat_worktree.py --describe>`").
  - **Where in this contract:** `## Extension Points`: "`<main root>` is the parent of `git rev-parse --path-format=absolute --git-common-dir`".
  - → Addressed by: the skills use `cleanup_delivered.py --print-main-root`, which prints `flat_worktree.describe()["main_root"]`, so there is still one source. No line runs `--git-common-dir`.

- **[WARN] `/task` keeps instructing `git worktree prune`, and the deferral that would fix it has no stub on disk**
  - **What is wrong:** `skills/task/SKILL.md:563` (and `:495`) still tell the user to run `git worktree remove` and then `git worktree prune`. INV-5 forbids prune, and the new `/pr-merged` anti-patterns ban it, so the plugin would ship two contradictory instructions. The Non-Goal points to follow-up `2026-10-07-adopt-flat-worktree-helper`, but no such `.followup.md` exists under `.claude/concepts/followups/`.
  - **Prior artifact ignored:** `MECHANISMS.md:63` (which names the same follow-up); `.claude/concepts/followups/` (it holds only three stubs, none of them this one).
  - **Where in this contract:** `## Non-Goals`: "`/task` and `/north-star` hand-written worktree lines (follow-up `2026-10-07-adopt-flat-worktree-helper` already tracks the latter)."
  - → Addressed by: `skills/task/SKILL.md` is now in `Files to touch`, and its prune lines are removed. `/ship` line 371 is fixed in the same change. The Non-Goal no longer cites the missing stub, and it says plainly that `/north-star` is a creation line with no follow-up.

- **[NIT] Two "Reused Mechanisms" have no registry entry** — "Landing worktree safety pattern" and "Plugin version bump rule" do not appear in `MECHANISMS.md` (Universal tier, lines 15-65), so "consumed as-is" cites code rather than a registered mechanism.
  - → Addressed by: both are moved into a separate line, "Not registered in `MECHANISMS.md` but reused as code".
- **[NIT] Adjacent Areas carries a stale instruction** — the main session already ran `cross_area_scan.py`: no areas, and `derive_area` returns `uncategorized`. The section still says "should run ... to confirm" instead of the exact sanctioned single line.
  - → Addressed by: the section is now the single sanctioned line.
- **[NIT] How INV-4 detects a junction is not stated** — before Python 3.12, `DirEntry.is_symlink()` and `os.walk` do not treat a junction as a link (`os.path.isjunction` arrived in 3.12). "The walk never follows a link" depends on detecting the reparse point.
  - → Addressed by: INV-4 states the detection: `os.lstat` plus `FILE_ATTRIBUTE_REPARSE_POINT` on Windows and `S_ISLNK` elsewhere, with `DirEntry.is_dir(follow_symlinks=False)` never used. A required test runs the junction case whichever Python version is installed.
- **[NIT] The `line` and the `finish_command` are not bounded or neutralised** — the line lists every name with no limit (by analogy with `JOURNAL.md` 2026-10-05 size budget). The finish line puts `<main root>` inside Bash double quotes, where a `$` in the path is expanded (by analogy with `JOURNAL.md` 2026-10-05 "Neutralise every field echoed from untrusted input").
  - → Addressed by: INV-8 caps the line at 600 characters, with 8 items per list, 3 files per item and `+k more`. Control characters are stripped, and the cap includes the summary. INV-6 single-quotes every path.
- **[NIT] POSIX behaviour for a held tree is unstated** — the in-use probe is Windows-only. On Linux and macOS, a shell standing in a removed tree is left in a deleted folder, and the Cursor manifest ships the script there too.
  - → Addressed by: INV-6 now says the standing-tree rule applies on every platform and only the probe is Windows-only. On POSIX, the session's own tree and the `CLAUDE_PROJECT_DIR` tree are deferred too.

### Applicable journal entries

- **2026-10-04 — Check a documented guard behaviour against the guard's code**: heeded by `## Lessons referenced`. Confirmed: `.claude/hooks/hooks.json:64` registers only `concept-gate.py` behind the launcher.
- **2026-10-04 — A root locator can return the consumer itself under vendoring**: violated, see the second BLOCKER.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control**: not addressed, see the source-scan WARN.
- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work**: not addressed. "Apply when" does not match literally (no host-read configuration); the trial-first principle is raised in the ASSUMED WARN.
- **2026-10-05 — Count a host's size cap the way the host counts, and prove the cap with a real trial**: not addressed. No hook-delivered text; the trial-before-tests principle is raised in the ASSUMED WARN.
- **2026-10-05 — Neutralise every field echoed from untrusted input, not only the body**: not addressed. Partial match (the skill echoes the line into model context); see the NIT.
- **2026-10-05 — A size budget must bound the summary it adds, not only the items it keeps**: not addressed, because the contract declares no size limit; see the NIT.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case**: not addressed. No parser is claimed VERIFIED, but the brief's `contract: none` placeholder is exactly the unfilled case (see the third BLOCKER).

### What the critic did not check

- CodeGraph tools were not available in this run. Symbols were checked with Grep and Read on `pr_merged.py`, `flat_worktree.py`, `land_contract.py` and `check_version_bump.py`. Every cited reader and line range exists as claimed.
- `INTEGRATION.md`, the registry digest (`.claude/.scout-cache/`), the per-domain registry files and `.claude/north-stars/` do not exist. Only the Universal tier was checked, and checklist item 13 produced no findings.
- `derive_area.py` and `cross_area_scan.py` were not re-run. The main session's run (no areas) was relied on.

---

## Lessons referenced

- **2026-10-04 — A root locator can return the consumer itself under vendoring** — heeded by the `$CLN` lookup and INV-6. The plugin root comes first, then the current worktree, and the main checkout's copy is never used.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by INV-2 and the required brief-lookup tests. A `contract: none` brief is found through the header, and through the `branch:` fallback.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded by the source-scan positive control.
- **2026-10-05 — Count a host's size cap the way the host counts, and prove the cap with a real trial** and **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** — heeded in principle by trials T1 to T4, which run before the dependent tests are frozen.
- **2026-10-05 — A size budget must bound the summary it adds, not only the items it keeps** — heeded by INV-8. The 600-character cap includes the `+k more` summaries.
- **2026-10-05 — Neutralise every field echoed from untrusted input, not only the body** — heeded by INV-8, which strips control characters, and INV-6, which single-quotes paths.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded. The plugin registers only `concept-gate.py` behind the launcher, and a script subprocess is not a hooked Bash call, so no guard behaviour is claimed.
- Orthogonal to north-stars: none active (`.claude/north-stars/` does not exist; the brief's `north_stars: none` is confirmed).

---

## Implementation Handoff

### 1. Cleanup (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/cleanup_delivered.py`
- `.claude/scripts/tests/test_cleanup_delivered.py`
- `.claude/scripts/tests/test_cleanup_delivered_trials.py`
- `.claude/scripts/tests/test_skill_script_lookup.py`
- `.claude/scripts/pr_merged.py`
- `.claude/scripts/tests/test_pr_merged.py`
- `.claude/scripts/flat_worktree.py`
- `.claude/scripts/tests/test_flat_worktree.py`
- `skills/pr-merged/SKILL.md`
- `skills/advance/SKILL.md`
- `skills/ship/SKILL.md`
- `skills/task/SKILL.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**Pre-written TASK block:**
```
TASK: Implement Delivery cleanup per the contract: new cleanup_delivered.py (INV-1..INV-9,
  flags --contract --from --remove-remote --dry-run --json --print-main-root), the two at-ref
  readers and the is_advance_worktree alias in pr_merged.py, the locked key in
  flat_worktree.worktree_entries, the skill wiring (pr-merged Step 6/7 and advance on EVERY
  call, both accepting the remove-remote parameter; ship Step 6 and task prune lines removed),
  the $CLN lookup (plugin root first, then current worktree copy, never the main checkout),
  and the minor version bump 0.8.7 -> 0.9.0 in all five entries.
CONTEXT: concept contract at .claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md;
  brief .claude/work-items/2026-10-15-50.md
FILES: as listed in Files to touch
CONSTRAINTS:
  - /tdd-first is mandatory. FIRST commit: trials T1-T4 from Uncertain Assumptions (T2, T3 as
    real failing-capable tests with a control; T1 records its outcome; T4 a manual trial noted
    in the PR). Freeze the other tests only after.
  - Tests use real temporary git repos with a local bare origin; gh is injected as a fake.
    Required cases (criterion in brackets):
    [1] three calls: records PR open -> not-delivered, nothing touched, rerun hint in line;
        merged -> cleaned; again -> no-op. Skill text test: Step 6 and /advance run the
        script on every call, no manual lines.
    [2] remove-remote OFF: remote branches listed remote-kept, untouched. ON: present+ancestor
        -> deleted; already deleted by GitHub -> already-gone, no push; remote not in
        origin/master -> kept not-in-default; open PR -> kept open-pull-request; gh
        unavailable -> kept unverifiable.
    [3] junction (Windows, _winapi.CreateJunction) / symlink (POSIX) removed alone and
        last-moment, target and its file survive, on the installed Python whatever its
        version; link-not-removed leaves the tree; a deferred tree keeps its links.
    [4] dirty tree and unpushed commit left, and the file names appear in the printed line;
        nested worktree under an ignored folder -> nested-worktree.
    [5] branch not in origin/master kept with reason.
    [6] merged branch deleted with -D while the main checkout sits on another branch;
        an owned branch held by the main checkout -> checked-out; protected-name for master.
    [7] sibling item's worktree with the same task-id folder name survives; prefix-sharing
        advance worktree -> ambiguous-name; holds-foreign-branch; locked, main checkout and
        landing worktrees untouched.
    [8] the one-line report: exact shape, a reason for every item left, 600-char cap with
        "+k more", control characters stripped.
    [9] CLAUDE_PROJECT_DIR inside a target and the script's own cwd inside a target ->
        deferred standing-tree with exactly one single-quoted finish line; a held cwd
        (Windows) -> in-use, files intact; a later call from outside clears it.
    Also: brief lookup with contract: none via the header and via the branch: fallback;
    rename-back failure halts all further mutation with the repair line; one item's
    remove-failed does not stop the next; not-delivered and unverifiable touch nothing;
    dry-run touches nothing; source scan for "--force", "worktree prune", "rmtree" with a
    positive control on planted text, then zero hits on the real source.
  - Reuse pr_merged readers by import (find_linked_brief, brief_for_branch, is_delivered,
    open_records_pull_requests, ...); do NOT write a second record or brief parser.
  - Never switch/checkout; never prune; never force-remove; chdir to the main root first.
  - The line format and the reason closed set are authoritative; do not add values.
  - Run py -3 .claude/scripts/check_version_bump.py before committing; it must exit 0.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md
  contract_status: approved
```

**Review (not a separate deliverable).** Decision 2026-10-15 (user, at the delivery-shape question): the review is not its own sub-task. The one implementation block is reviewed in the same pull request by fresh `fullstack-code-reviewer` and `test-strategy-critic` agents (flow Step 4), with weight on INV-1 to INV-9, the nine required test cases, trials T1 to T4, the $CLN lookup order, the version bump and the skill wiring. The review reports are committed with the pull request.

---

## Review checklist (filled in after implementation)

`pr_merged.py` fills this list when the contract's work is merged and nothing is pending. Do not tick lines by hand.

- [ ] Implementation matches Data Shapes exactly — not performed (disclosed on #50)
- [x] Reused Mechanisms are actually reused (no parallel implementations introduced) — evidence: .claude/reviews/2026-10-15-auto-cleanup-delivered-worktrees/fullstack-code-reviewer-pass2.md
- [x] New Mechanisms (if any) promoted to `MECHANISMS.md` — evidence: .claude/reviews/2026-10-15-auto-cleanup-delivered-worktrees/fullstack-code-reviewer-pass2.md
- [x] New vocabulary terms promoted to `VOCABULARY.md` — evidence: .claude/reviews/2026-10-15-auto-cleanup-delivered-worktrees/fullstack-code-reviewer-pass2.md
- [ ] Integration surfaces reflected on both backend and frontend sides — not applicable (.claude/reviews/2026-10-15-auto-cleanup-delivered-worktrees/fullstack-code-reviewer-pass2.md)
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced — not applicable (.claude/reviews/2026-10-15-auto-cleanup-delivered-worktrees/fullstack-code-reviewer-pass2.md)
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface) — not applicable (.claude/reviews/2026-10-15-auto-cleanup-delivered-worktrees/fullstack-code-reviewer-pass2.md)
- [x] `Status` flipped to `implemented`
