# Superseded critique round 3 — 2026-11-02-pr-merged-records-leftover-cleanup

Moved out of `.claude/concepts/2026-11-02-pr-merged-records-leftover-cleanup.md` on 2026-11-02 by `contract-critic` (round 4), per the budget rule in `.claude/templates/concept-contract.md`. The data-architect amended the contract body (third amendment) in response to these findings before round 4 ran.

## Critique

**Critic:** contract-critic (round 3; round 1 moved to `.claude/contract-history/2026-11-02-pr-merged-records-leftover-cleanup.round-1.md`, round 2 to `.claude/contract-history/2026-11-02-pr-merged-records-leftover-cleanup.round-2.md`)
**Date:** 2026-11-02
**Verdict:** blockers-found

### Findings

- **[BLOCKER] I-1 writes its own repository check with `git rev-parse --git-common-dir`, but a tested tree classifier already exists for this script**
  - **What is wrong:** the "path present but not this repository" check compares `rev-parse --path-format=absolute --git-common-dir` output after `realpath` and case folding. That is a second tree classifier. `tree_kind(path)` and `main_checkout_root(path)` already answer this question from `.git` entries, and they are re-exported to `pr_merged.py` for exactly this purpose. The registry also says no script runs that git command.
  - **Prior artifact ignored:** `MECHANISMS.md` line 43, **Two-layer Claude path resolution**, "Tree classification": "They are re-exported through `_claude_paths.py`, because `flat_worktree.py`, `pr_merged.py` and `merge_direction.py` need them. No script runs `git rev-parse --git-common-dir`."
  - **Where in this contract:** `I-1`, check 2: "'This repository' is decided by comparing `git -C <tree> rev-parse --path-format=absolute --git-common-dir` with the same command run for the repository of the process's working directory"; TASK block test "common-dir comparison holds from a linked worktree and from the main checkout".
- **[BLOCKER] When a head cannot be read, the evidence silently drops it, and in a swept tree that brings back the re-dispatch this contract exists to prevent**
  - **What is wrong:** I-8 says "An unreadable ref adds nothing". I-6 says that with no untracked leftovers, `records_unpushed` is `[]` "even when a ref could not be read". Under Q3 (a), take a swept tree whose records sit only on an open records head. If `gh` or `ls-remote` fails, `evidence` lacks those records and `advance()` releases the sub-task again. I-14 does not refuse, because the list is empty and not `null`. The move never becomes `unverifiable`. The only thing left to stop it is the prose backstop in `/advance`. That is the contract's own first failure mode, reopened through a failed read.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-01 "A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for". `merge_evidence`'s only caller today is the layout-warning block (`pr_merged.py:4731`), where a missing ref only costs a warning. In this contract it decides dispatch.
  - **Where in this contract:** `I-8`: "An unreadable ref adds nothing, and the reading names it"; `I-6`: "With no untracked leftovers at all, both are empty lists even when a ref could not be read, because nothing local can be lost"; `## Failure Modes`, first FM.
- **[BLOCKER] "A merged head's records are on `origin/<default>`" is false for a records branch that gets new commits after its merge, so a copy can be deleted and the contract can flip with the record on a dead branch**
  - **What is wrong:** a head counts as a Compared ref when it has an open or merged pull request. I-4's exception commits "on top of the records branch", so new commits can land on a branch whose earlier pull request already merged. Until a new pull request is opened, and for good if opening it fails, that head counts as "merged". The sweep then deletes the local copy as `landed` against it. `evidence` counts the record. The flip's only remaining guard is "no open records pull request" (`pr_merged.py:3804-3813`), and it passes. The record is then on neither `origin/<default>` nor an open pull request. Separately, `open_records_pull_requests` lists with `--limit 200` (`pr_merged.py:2826-2827`). With `--state all`, that window covers the 200 newest pull requests of the whole repository, so on a busy repository an older merged head silently counts as having no pull request.
  - **Prior artifact ignored:** `VOCABULARY.md` **Delivery cleanup** / **Landed untracked file** (proof is against `origin/<default>`, "removes nothing whose commits are not already in `origin/<default>`"); `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery, not only the one the author had in mind".
  - **Where in this contract:** **Compared refs**: "every `origin/docs/<contract-slug>-records*` head that has an **open or merged** pull request"; `I-13`: "a merged head's records are on `origin/<default>`. So the flip itself still happens only once the records are on `origin/<default>`"; `I-4` Exception: "the records step commits it on top of the records branch".
- **[WARN] The I-13 list of decision readers is incomplete, and the re-run guard covers only the `--pr` route**
  - **What is wrong:** three readers in `main()` still read `records` and miss the list:
    - `--record-delivery`'s G-3 (`failed_ids` from `records`, `pr_merged.py:4265`);
    - its "already recorded" test `if task.id in records` (`pr_merged.py:4301`);
    - `reconcile_state(state, records)` (`pr_merged.py:4491`).

    In a swept tree, `--record-delivery` therefore writes a fresh record for every sub-task that is already on origin. I-9 does not stop it, because I-9 guards only the `--pr` loop. That breaks acceptance criterion 8 ("does not duplicate") on the delivery route. Also, I-9's "refs unreadable, no local copy → written as today" closes the sub-issue again and rewrites state on a re-run.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "One shared reader must own the filtering, not only the selection"; 2026-10-30 "A delivery rule must name every route into delivery".
  - **Where in this contract:** `I-13`: "Every reader in `main()` that decides something from records reads `evidence` … Those readers are:" (five listed); `I-9`: "In the `--pr` path".
- **[WARN] I-8 rule 1 changes more of today's behaviour than the contract admits**
  - **What is wrong:** "Status first, across every source" also outranks a `failed` record written by THIS run whenever any source holds a `completed` one. Today, `advance()` escalates on that record (`pr_merged.py:1793-1796`), and `merge_evidence`'s own rule is "only a record written by THIS run overrides origin's" (`pr_merged.py:2900`). Under rule 1, the escalation goes away without a word. The local `failed` copy is then neither `landed` nor `update`, so it sits as `differs` until the owner discards it. The contract names only "a stored `completed` record against an origin `failed` one" as the deliberate change.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A failed record written by a new rule must not be the input of an older guard that blocks the rule's own exit" (trace every guard that reads failed records, in both directions).
  - **Where in this contract:** `I-8`: "Rule 1 does change today's result for a stored `completed` record against an origin `failed` one; that change is deliberate and tested."
- **[WARN] The `null` and empty-list rules contradict each other, and "`null` with leftovers present" cannot be read from the report**
  - **What is wrong:** I-3 says a failed read makes "the whole reading `unverifiable` … `records_unpushed` and `records_differing` are `null`". I-6 says both are empty lists when there are no leftovers, "even when a ref could not be read". The verdict enum has no value for "no leftovers, ref unreadable". Also, I-7, I-14 and Extension Point 10 all branch on "`null` with leftovers present". But when the reading is unverifiable, "No entry is classified", and the Leftover Reading defines no field that lists the unclassified paths. A skill therefore cannot tell those two cases apart.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case".
  - **Where in this contract:** `I-3`; `I-6`; `### Value Objects` → Records Leftover Reading (`entries`, `verdict`); `## Extension Points` 10: "or `null` with leftovers present".
- **[WARN] The `update` exception changes how the records branch is cut, while the contract says the cutting rule is unchanged**
  - **What is wrong:** I-4 commits "on top of the records branch (cut from `origin/<default>` when the branch is absent)". The shipped procedure cuts the branch fresh from `origin/<default>` every time, and uses a `-2`/`-3` suffix when the name is taken (`skills/pr-merged/references/contract-completion.md:54`). The fresh cut exists because of the stale-base reason the brief cites. Neither Extension Point 8 nor Extension Point 9 rewords step 6.
  - **Prior artifact ignored:** `skills/pr-merged/references/contract-completion.md:54`; the brief's "Related items: … journal entry of 2026-08-29 (stale-base reason for cutting the records branch fresh from `master`)".
  - **Where in this contract:** `I-4` Exception; `## Lessons referenced`: "The cutting rule is unchanged (Non-Goals)".
- **[WARN] The contract is about twice its token budget**
  - **What is wrong:** the body without the critique is roughly 23,000 tokens, against `**Budget:** 12,000 tokens`. Most of the growth is mechanism that the acceptance criteria do not ask for (see the next finding).
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md` line 22, budget rule.
  - **Where in this contract:** header `**Budget:** 12,000 tokens`; `## Data Shapes → Invariants` I-1 to I-15.
- **[WARN] The contract is out of proportion with an M-sized IMPROVEMENT. Option E would meet the brief at much lower risk, apart from when acceptance criterion 1 is met**
  - **What is wrong:** the brief asks for nine criteria on "a script, its tests and three skill documents". The contract now has:
    - 15 invariants;
    - a new exit code;
    - an owner flag;
    - a fifth leftover state (`update`);
    - a reordering of `merge_evidence` that every decision reader in `main()` now depends on;
    - a GitHub `--state all` read and per-head fetches on every `--json` run;
    - a version-skew detector.

    Every BLOCKER above, and the "open or merged head" reasoning behind them, exists only because Q3 (a) deletes a copy before its records reach `origin/<default>`. **Option E** keeps what the brief needs:
    - the sweep, against `origin/<default>` alone (the existing **Landed untracked file** rule);
    - `merge_evidence` unchanged, with no `branch_heads` and no status-first rule;
    - I-9 against `origin/<default>`;
    - the I-7 prefix and the I-14 refusal.

    It drops `open_records_pull_requests(state)`, the head classes, rule 1 and all three BLOCKERs. Its cost is the one the contract already states: criterion 1 ("after a normal `/pr-merged` run that pushes the records branch") holds only from the first call after the records pull request merges. The brief's own problem statement assumes that state ("The same file has already reached `master` through the records pull request"). The every-call sweep is exactly what the 2026-10-15 trigger-timing lesson prescribes. Under E, criterion 1 needs a one-line rewording by the user; nothing else in the brief changes.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-15 "A cleanup wired to run before its own trigger event has fired never runs" ("make the step safe to repeat and run it on every call, so the first call after the event does the work"); `VOCABULARY.md` **Landed untracked file**; the brief, `## Size`: "M".
  - **Where in this contract:** `Q3` recommendation "(a)"; `## Alternatives Considered` → Option E; `## Confidence`: "Medium on feeding `evidence` into every decision reader, and on the status-first rule".
- **[NIT] Any absent `--from` reads `gone` and exits 0** — a mistyped starting-tree path sweeps nothing and reports no error, so criterion 1 fails without a sign.
- **[NIT] `_tree_blobs_at` is described without `-r`** — `status --untracked-files=all` lists files in nested folders, but a non-recursive `ls-tree` of `<folder>/` does not, so a nested file under the results folder would read `unpushed`.
- **[NIT] Every `--json` run, `--status` included, now makes a GitHub list call plus `ls-remote` and one fetch per head (Extension Point 2)** — the cost per `/advance` call is not stated.
- **[NIT] Uncertain Assumptions says `--dispatch` refuses with "exits 2, 3, 5 and 7"** — the same branch also returns 4 and 6 (`pr_merged.py:4609-4639`). Exit 12 is still free.
- **[NIT] Chat Tool Impact uses none of the three sanctioned phrasings** — no REST, SignalR or DTO surface changes, so item 7 does not fire.

### Applicable journal entries

- **2026-10-17 — Judge "identical to master" by git's view** — heeded by `I-2`.
- **2026-10-17 — Git for Windows lists files beneath an untracked junction** — heeded by `I-2` (`_plain_file_inside` re-checked before each delete).
- **2026-10-15 — A cleanup wired before its trigger never runs** — heeded by the every-call sweep. The lesson also argues for Option E, see WARN.
- **2026-10-16 — An unset ownership field is not proof of ownership** — heeded by `I-1` (contract's own results folder, `--from` trees).
- **2026-10-16 — A skill step that moves the shell** — heeded by `--from` / `git -C` (`I-1`, `I-11`).
- **2026-10-15 — A skill that edits a lookup block must name the test** — heeded by the TASK run list.
- **2026-10-28 — Do not promote an extension seam** — heeded by `## New Mechanisms`: None. But `I-1` duplicates the tree classifier, see BLOCKER 1.
- **2026-10-28 — A new term's definition must be true against every member** — heeded by Tree-clean line (Extension Point 10 now passes the `--dispatch` worktree).
- **2026-10-22 — Amend the body before approval** — heeded: the `update` skill text is now listed in Extension Point 8.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by `I-14` (inline refusal, exit 12, placed before `advance()`, under `--dry-run` too). There is a minor exit-list slip, see NIT.
- **2026-10-04 — Detect an install mode by what the sync delivers** — heeded by `I-15`.
- **2026-10-04 — A VERIFIED parser claim must be tested on the missing case** — heeded for `gone`; violated by the `null`/empty rules, see WARN.
- **2026-10-30 — A rule that refuses must give a named way out** — heeded by `--discard-differing`, the I-7 reason text and the I-13 flip remedy.
- **2026-10-30 — One shared reader must own the filtering** — partly heeded (`merge_evidence` owns precedence); violated by the readers missing from I-13, see WARN.
- **2026-10-30 — A delivery rule must name every route** — violated: the `--record-delivery` route and the reused merged records branch, see BLOCKER 3 and WARN.
- **2026-10-30 — A failed record must not feed an older guard** — heeded for the merged-failed plus head-completed case (rule 1). The reverse direction, a this-run `failed` record, is not traced, see WARN.
- **2026-11-01 — A shared reader reused by a stricter consumer** — heeded for the sweep's own readers (`_tree_blobs_at`, `origin_records`). Violated by `merge_evidence` feeding dispatch with an unreadable head treated as empty, see BLOCKER 2.

### What the critic did not check

- Checklist item 14: `pr_merged.py --contract <slug> --status --json` was not run, because the contract has no state yet. It has one mergeable block, carries the `**Work Item Brief:**` header, and that block raises the version.
- `.claude/registries/INTEGRATION.md`, `.claude/north-stars/` and `.claude/.scout-cache/registry-digest.md` do not exist or were not read. Item 7 was judged from `## Integration Surfaces`, and item 13 produces no findings.
- CodeGraph tools were not available to this critic. Code claims were checked with Grep and Read on `.claude/scripts/pr_merged.py` and `skills/pr-merged/references/contract-completion.md`.
- The lazy `cleanup_delivered` import (ASSUMED) was not run.
