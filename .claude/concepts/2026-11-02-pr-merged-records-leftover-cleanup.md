# Concept Contract — /pr-merged removes the completion-record copies it leaves in the starting tree

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-02
**Requested by:** user
**Status:** approved
**Work Item Brief:** .claude/work-items/2026-11-02-178-records-leftover-cleanup.md
**Tracking issue:** #178
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. Implementer agents refuse to run unless `Status: approved` or `Status: implemented`. The `concept-gate.py` hook reads `Files to touch` to decide whether Edit/Write/MultiEdit is allowed.
>
> **Budget note (fifth amendment, final):** the body is about 15,000 tokens, over the 12,000 budget. The overrun is the evidence and way-out rules (I-3 to I-7). The user chose to delete copies right after the push (criterion 1 as written, Option E rejected), and those rules are what keep that choice safe. The five critique rounds' findings could not be closed in fewer words. Q3 is answered, so only Q1 and Q2 remain open.

---

## Business Concept

- **What is this thing, in domain language?**
  After a merge, `/pr-merged` writes a completion record into the tree it runs from (the **starting tree**). The records step then copies the record onto a **Records pull request** branch from a flat worktree and pushes it. The starting-tree copy is never removed: it stays untracked, grows by one file per sub-task, can block a later merge of `master`, and leaves every session dirty.

  This contract makes the loop finish what it starts. Once a record is safely on origin, its identical starting-tree copy is deleted. A copy that differs is kept and named, with an owner exit. Nothing is deleted when the push failed or a read failed. The script learns from git alone when records still wait to be pushed, puts the records step first in its Next Command, and `/advance` does not dispatch on top of them. Both skills end with one line per tree they touched.

  Deleting the copy has a consequence the issue did not name. Today the untracked copy is what lets a later `/advance` in that tree see the completion. After the sweep, the loop must read that record from origin through one shared evidence rule (I-6, I-7). If it cannot read it, the loop must hold rather than re-dispatch.

- **Existing VOCABULARY.md terms that apply:** **Records pull request**, **Landed untracked file**, **Completion Verdict**, **Contract Delivery**, **Flat worktree**, **Delivery cleanup**, **Owned set**, **Main checkout**, **Tree kind** (Universal tier). "Next Command" and "completion record" are used as the script already uses them.

- **New terms proposed for VOCABULARY.md** (Universal tier, appended by the implementing pull request):
  - **Records leftover** — an untracked file under `.claude/orchestrator/results/<contract-slug>/` in a swept tree. Against the **Compared refs** it is:
    - `proven` — git would store it as exactly a compared blob at that path. Against `origin/<default>` it uses the same identity test as a **Landed untracked file**, but it is not that term (it applies to any swept tree, at any time, not to an owned worktree after delivery). Against the records branch tip it is a weaker proof, accepted only while that branch's pull request is open. The two are deliberately one state with two proofs, and the entry's `ref` says which;
    - `update` — it is a `completed` record, and every compared copy of that path is a `failed` record. This is the only replacement the loop pushes;
    - `differs` — a compared copy exists, but the file is neither of the above. This includes a local `failed` copy over a compared `completed` one, and a `completed` record for a different pull request over a `completed` one. Neither is pushed or swept; a person decides (I-8);
    - `unpushed` — no compared copy exists;
    - `unsafe` — it is a link, or sits under a linked folder.

    Only `proven` is deleted automatically.
  - **Compared refs** — what a leftover is judged against:
    - always `origin/<default>`;
    - the tip of the one stable branch `origin/docs/<slug>-records` (exact name, never a prefix), only while an open pull request has that branch as its head.

    Without an open pull request, the tip is never proof. Content already on `origin/<default>` is judged there.

    **Ancestry (second post-implementation amendment).** When `git merge-base --is-ancestor origin/docs/<slug>-records origin/<default>` succeeds, the tip is already merged. It contributes nothing to `stranded` or `unpushed`, and a later change to a path on `origin/<default>` through another route never makes it stale. If the check itself fails (any exit other than 0 or 1), the reading is `unverifiable`.
  - **Records stranded** — records-folder paths on the stable branch's tip that are not identical on `origin/<default>`, while no open pull request has that branch as its head and the tip is not an ancestor of `origin/<default>` (see Compared refs, Ancestry). Examples: a records pull request closed unmerged, or a push made after the last pull request merged. They stay readable as long as the branch exists, because the loop never re-cuts it. A branch a person deletes is covered in I-4. The **Records step** re-opens a draft pull request from the same branch.
  - **Records reading** — `ok` or `unverifiable`: whether the reads behind the Compared refs and the classification succeeded. The separate key `records_action: skipped-by-owner` reports the owner flag `--local-evidence-only` (I-3), which never changes the reading.
  - **Records unpushed** — the leftovers in `unpushed` or `update`. It is the **Records step**'s input, and it is not the Completion Verdict's `pending`.
  - **Records step** — the one procedure (`skills/pr-merged/references/contract-completion.md`, "The records pull request") that pushes Records unpushed to the stable branch, opens a draft pull request when none is open (which also clears Records stranded), and then sweeps every tree it touched. It is invoked as `/pr-merged --records <slug>` (Q2).
  - **Tree-clean line** — one line per tree given to the sweep: `tree <root>: clean`, `tree <root>: <n> entries left — <reasons>`, or `tree <root>: gone` for a tree passed with `--removed` that no longer exists.

---

## End-User View

Not applicable. Reason: `Files to touch` names no Angular component, template, stylesheet, state service, route file or shared layout. The change is a workflow script plus skill text, read by the operator in a terminal.

---

## Data Shapes

### Entities

Not applicable. Reason: no persisted entity is added. Completion records keep their shape (`build_record` is unchanged), and the state store gains no field.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Records report keys | `records_reading` (`ok` \| `unverifiable`); `records_reading_cause` (only when `unverifiable`: the failing ref, and for a record, the exact `<ref>:<path>`); `records_failure` (`transient` \| `persistent`, only when `unverifiable`); `records_action` (`normal` \| `skipped-by-owner`); `records_untracked` (every untracked results-folder path in the working tree, always listed); `records_unpushed`, `records_differing` and `records_stranded` (lists, meaningful only when the reading is `ok`) | Carried by the general report (`--status`, `--resume`, `--dry-run`, plain, `--pr` and `--record-delivery` runs) and by `--sweep-records`. **Exempt** (they print their own JSON and return early): `--record-subtask`, `--preconditions`, `--locate-parent`, the `--dispatch` packet and every JSON refusal. A skill branches on `records_reading` first |
| `next_move.held` | `records-unverifiable` or `records-stranded` (absent otherwise) | I-7's hold, declared here |
| Leftover Entry | `path`; `state` (`proven`/`update`/`differs`/`unpushed`/`unsafe`); `ref` (the matching or differing ref); `local_blob`, `ref_blob` (set for `differs`); `action` (`deleted`/`would-delete`/`kept`/`discarded`); `reason` (when kept); `remedy` (for `differs`: `/pr-merged --records <slug> --discard-differing <path>`) | `records_leftover.entries`, one per classified file |
| Already-recorded entry | `sub_task`, `ref`, `pull_request` | `report["already_recorded"]` (I-8) |
| Tree-clean line | `tree`, `clean`, `line` | `report["tree_lines"]`, printed last by `--sweep-records` |

### Invariants

- **I-1 (which trees).**
  - **Which flags.** `--from <tree>` (repeatable, default the working tree) must exist. If it does not, the run is refused with `tree-not-found`, exit 2, so a mistyped starting tree is never silently skipped. `--removed <tree>` (repeatable) names a tree the skill itself removed. It prints `gone` when absent, and `gone-partial` when the folder still exists without a `.git` entry (a half-removed worktree; not swept, never a refusal). When the tree is fully present, it is swept like `--from`.
  - **Never the main checkout.** A tree whose `tree_kind` is `main-checkout` is never swept. Its line reads `tree <root>: main checkout — not swept (<n> leftovers kept)`, and nothing there is deleted, which keeps the `os.remove` calls consistent with the main-checkout guard, which the guard itself cannot see inside a script. Under worktree isolation the starting tree is a linked worktree, so criterion 1 is met there.
  - **Tree root only.** A present tree must be the root of a worktree: the path itself carries a `.git` entry, read the way `tree_kind` reads it. A subfolder is refused with `not-a-tree-root`, exit 2, because `git -C <subfolder> status -- <folder>` would match nothing and print `clean`.
  - **Same repository.** A present tree must be a worktree of this repository. That is decided only with the re-exported tree classifier (`MECHANISMS.md` line 43): `tree_kind(tree)` is `main-checkout` or `linked-worktree`, and `main_checkout_root(tree)` equals `main_checkout_root(<working directory>)`. Otherwise the run is refused with `not-this-repository`, exit 2, before any delete. No `git rev-parse --git-common-dir` is run.
  - **Which files.** In each tree only `??` entries under the contract's results folder are touched, listed by `git -C <tree> status --porcelain -z --untracked-files=all -- <folder>`. The flip's modified contract and brief are reported, never touched.
- **I-2 (deletion).** A `proven` file is deleted only on a reading that is `ok` and with `records_action: normal`, one file at a time. When the proof is the branch tip, the open pull request is re-read immediately before the first delete of that run, and if none is open, nothing proven by the tip is deleted. Immediately before each delete:
  - it is re-checked for links on the file and every parent folder (`_plain_file_inside`);
  - it is re-hashed with `git hash-object`, filters on.

  It is then removed with `os.remove`. There is no recursive delete, no `git clean`, and no switch, checkout, reset or stash; the only git writes are fetches into `refs/remotes/origin/*`. `--dry-run` reports `would-delete` and deletes nothing. The skills run the sweep only after a successful push, and an unpushed file is never `proven`, so a failed or declined push deletes nothing.
- **I-3 (failed reads are seen).** The reading is built only from readers that tell "failed" apart from "empty":
  - `ls-remote` of the exact stable branch name;
  - `open_records_pull_requests` (none on failure). It is the ONE reader of "is a records pull request open", used by the sweep, the records step, the flip check (~3805) and G-6 (~4283) alike. It is **extended by** an optional `head` argument. The sweep and the records step pass `head="docs/<slug>-records"`, which runs `gh pr list --head docs/<slug>-records --state open`, so the repository-wide `--limit 200` cap can never hide the stable branch's pull request. Existing callers are unchanged;
  - `fetch_default_branch`, once per ref;
  - `origin_records` with its fetch turned off after that single fetch (none on failure);
  - the strict `_tree_blobs_at` (`ls-tree -r --full-tree -z`, none on failure);
  - `_hash_files` (none on failure), compared against `_tree_blobs_at`'s blob ids. `compare_untracked` is not called (second amendment).

  Any failure sets `records_reading: unverifiable`. The cause names the exact failing ref, or the exact `<ref>:<path>` of a record that does not parse. Then no entry is classified, nothing is deleted in any tree, and I-7 holds the loop. `_tree_names_at` and `load_records_at`, which turn failure into emptiness, are never used here.

  **Transient or persistent.** `records_failure` classifies the cause:
  - `transient`: a failed fetch, `ls-remote` or `gh` call;
  - `persistent`: a record that does not parse, or `gh` missing or unauthenticated.

  A persistent failure keeps `--dispatch` refused (I-9) for as long as it lasts, with the cause named. The owner's way out is to fix that cause: repair the malformed record through a records pull request, or install or authenticate `gh`.

  **`--local-evidence-only`** (owner flag, passed through by both skills) only makes the sweep and the records step skip deleting and pushing for that run (`records_action: skipped-by-owner`). It exists so the owner can carry on with work that is not a dispatch. It never changes `evidence`, `advance()`, `delivery_candidates` or the Completion Verdict, and it never lifts I-7's hold or I-9's refusal.

  **Cost per run that carries the keys:**
  - one fetch of `origin/<default>` — new for a single-block `--status`, which fetched nothing before;
  - one `ls-remote`;
  - one `gh pr list --head docs/<slug>-records --state open`;
  - when the stable branch exists, one fetch of it.

  Each ref is fetched once.
- **I-4 (differs, update, and where a push goes).**
  - **Differs.** A `differs` copy is kept and reported with both blob ids and the `remedy`. `--discard-differing <path>` is the owner exit, never run by a skill on its own: it re-classifies the file, refuses (`not-differing`, exit 2) unless it still differs, prints both blob ids, then deletes the copy under I-2 (origin wins).
  - **Update.** An `update` copy (a completed re-delivery over a failed record) is pushable, like `unpushed`.
  - **Where a push goes: the single stable branch, exactly as today.** That is `SKILL.md` Step 3, the anti-pattern at ~617–618, `/flow` Step 8 (`skills/flow/SKILL.md:516`), and the three refs the landing reads (`land_contract.py:1995`, `:3089-3093`).
    - Fetch `origin/docs/<slug>-records` first.
    - If it exists, check it out, commit on top and push without force. It is never re-cut while it exists.
    - Only when it is absent, cut it from `origin/<default>`.
  - **New in the records step.** It commits only when the copied files change the branch. "No new content to commit" (for example, a local copy identical to a stranded tip, which reads `unpushed` because a tip without an open pull request is not compared) is success, not an empty commit, and the step goes on. Then, if no open pull request has the branch as its head (its previous one merged or closed), it opens a new draft pull request from the same branch. That is also the way back after a closed-unmerged records pull request (Records stranded).
  - **A deleted stable branch.** If the pull request was closed and the branch deleted, the record exists nowhere the loop reads. It is neither evidence nor stranded. The sweep never deleted the local copy unless an open pull request held the tip at that moment (I-2), but a later branch delete still leaves this residual risk. The ways back, in order:
    1. re-record from GitHub with `/pr-merged <sub-task pr>`; I-8 does not skip, because `evidence` lacks the record;
    2. or recover the file with `git fetch origin refs/pull/<n>/head` from the closed records pull request and push it through the records step.

    Until then, `/advance`'s existing backstop (a sub-task whose branch or pull request already exists → stop) guards against re-dispatch.
  - **Suffixes.** `contract-completion.md` step 6's `-2`/`-3` suffix is reworded to apply to the records **worktree folder** name only, as the Flat worktree helper already names taken folders. It never applies to the branch name. No suffixed branch is created or read.
  - **Never.** The loop never pushes over a completed record, and it pushes nothing while the reading is `unverifiable`.
- **I-5 (git-derived sets and the Next Command).** The report keys are computed on every run from git and GitHub facts, never from the state store, `written_files` or session memory. After `next_command_for(move, slug)` (`ADVANCE_ACTIONS` unchanged):
  - `records_reading: unverifiable`, `transient` → `commands: []` and `reason: "records could not be read (<cause>); retry once git and GitHub answer"`;
  - `records_reading: unverifiable`, `persistent` → `commands: []` and `reason: "records cannot be read: <cause>; fix it (repair <ref>:<path> through a records pull request, or install or authenticate gh); dispatch stays refused until then"`. Neither reason suggests `--local-evidence-only`;
  - `records_unpushed` or `records_stranded` not empty → `commands = ["/pr-merged --records <slug>"] + base commands`, alone when the move is `blocked`, with `reason` prefixed `records not on their way to origin (<n> files); `;
  - `records_differing` not empty → `commands` are unchanged, and `reason` names each `remedy`, because a differing copy never blocks;
  - otherwise the result is byte-identical to today.
- **I-6 (one evidence rule).** `evidence = merge_evidence(origin_default, records, stored_records, branch_heads=<records on the stable branch tip>)`, which extends the existing function. The tip's records count as evidence whether its pull request is open or not: the landing reads that same branch (`land_contract.py:1995`), and the branch is never re-cut. Sweep proof (I-2) still requires an open pull request. For each sub-task:
  1. a record written by **this run** wins outright (today's rule), so a `failed` record this run writes still escalates;
  2. among the other sources (`origin/<default>`, the stable branch tip, the stored local copy), `completed` beats `failed`;
  3. on equal status, `origin/<default>` beats the tip, which beats the stored local copy.

  Rule 2 deliberately changes one of today's answers: a stored `completed` record now beats an origin `failed` one, which is the re-delivery case, and it is tested. `records` and `stored_records` are never mutated.
- **I-7 (every decision reads `evidence`; an unreadable reading holds).**
  - **Who reads `evidence`.** Every reader in `main()` that decides from records reads `evidence`:
    - both `advance()` calls;
    - `delivery_candidates` (~4483, and the `--record-delivery` call at ~4250);
    - the `is_delivered` check (~4505);
    - `--record-delivery`'s G-3 failed check (~4265) and its already-recorded test (~4301);
    - G-7 `records-not-local` (~4244);
    - `reconcile_state` (~4491);
    - `evaluate_completion`;
    - the layout block (~4731).

    Added after review (I-12): `load_delivery`, `is_delivered`'s `delivery` argument, G-5 and `write_delivery`'s precondition. Added at the second review: the brief-link gate, and every other decision in `main()` that reads `stored_records` or the local `records`. Only the report-only fields listed as accepted limitations stay local.

    Write paths read `records`. G-7's purpose (never overwrite `origin`'s records from a stale checkout) is now carried by I-8, which never rewrites a sub-task that `evidence` holds as completed. On `evidence`, G-7 therefore fires only when a record cannot be read, and that case is already `unverifiable`. So `--record-delivery` in a swept tree after the merge proceeds and writes only what is missing.
  - **The flip.** A swept sub-task therefore reads as recorded, and no verdict names `/pr-merged <pr>`, which I-8 would skip.
    - A record held on the tip with an open pull request leaves the flip `pending` through the existing "records-pull-request-open: merge <url>" check (~3805).
    - With Records stranded, the flip is held (`next_move.held: records-stranded`, verdict `pending`, remedy `/pr-merged --records <slug>`, which re-opens the pull request).

    So the flip happens only with the record on `origin/<default>`.
  - **When the reading is `unverifiable`.** Nothing is released on missing evidence. The report empties `released` and builds no `dispatch` packets, `next_move.held` is `records-unverifiable`, and the Completion Verdict is `unverifiable` with I-5's remedy. `--local-evidence-only` changes none of this.
  - **Delivery cleanup is unchanged.** `cleanup_delivered.py` keeps `load_records_at(origin/<default>)` and `is_delivered`.
- **I-8 (re-run guard, both routes).**
  - **Skip.** Before `--pr` or `--record-delivery` writes a record, if `evidence` (excluding this run) holds a `completed` record for that sub-task with the same `pull_request` link, the run writes nothing for it: no record, no sub-issue close, no state write. It is listed in `already_recorded`, `records[task.id]` is left as loaded, and nothing is deleted.
  - **Refuse.** A `--pr` or `--record-delivery` writing run (not `--dry-run`) whose reading is `unverifiable` writes nothing and exits 10, the script's existing unverifiable exit, with the cause. `--dispatch` is not covered here; it has I-9's exit 12 only, so `skills/advance/SKILL.md:210` ("`--dispatch` never exits 10") stays true.
  - **Re-delivery.** A `failed` record, or a different pull request, is re-recorded as today.
    - Over a `failed` record, the new `completed` copy is `update` and is pushed.
    - Over a `completed` record for another pull request, it is `differs`, as the code behaves (second post-implementation amendment). It is not pushed and not swept. The Next Command reason names the resolution: `--discard-differing <path>` keeps origin's record; otherwise the owner keeps the local one by committing it to the stable branch by hand.
- **I-9 (dispatch refuses).** Right after the `unknown-sub-task` check and before `advance()` (~4519), `--dispatch` (including `--dry-run`) prints one JSON refusal, as its others do, and exits **12**: `records-unpushed` (non-empty `records_unpushed` or `records_stranded`, remedy `/pr-merged --records <slug>`) or `records-unverifiable` (the cause, and I-5's remedy). `--local-evidence-only` never lifts either refusal. The script's `--dispatch` uses exits 2–7, and nothing in it uses 12. A `differs` copy never refuses. `/advance` reads exit 12 together with the `error` key.
- **I-10 (tree-clean lines).** `--sweep-records` re-reads each tree's status after deleting and prints one Tree-clean line per `--from`/`--removed` tree as its final lines. The skills pass every tree they touched — the starting tree, the records worktree (`--removed`) and, under `/advance`, the `--dispatch` worktree — and print the lines verbatim.
- **I-11 (an older vendored script).** The skills halt the records step and dispatch with "this `pr_merged.py` predates 0.13.0: sync the vendored copy (`tools/sync-plugin.cmd`)" when either:
  - a `--status --json` or `--sweep-records` report has no `records_reading` key. This applies only to the modes documented to carry the keys; the exempt modes in Value Objects are never judged this way;
  - any call exits 2 with `unrecognized arguments:` naming `--sweep-records`, `--from`, `--removed`, `--discard-differing` or `--local-evidence-only`.

  Any other exit 2 without a JSON `error` is printed verbatim and halts. An absent key never reads as "nothing pending".

> **Post-implementation amendment (2026-11-02; Status stays `approved`).** Recorded after code review, as a contract defect fix plus declared divergences. I-1 to I-11 keep their numbers.

- **I-12 (the Contract Delivery Record is evidence too; review defect B1).** The sweep deletes `contract-delivery.yaml` once it is `proven`. Never sweeping it was rejected, because it would leave an untracked file and break criterion 1.
  - **How it is read.** The delivery record is therefore read as evidence exactly like completion records: the local copy, else the stable-branch tip, else `origin/<base>`, under the same failure-aware reading. Any failed read makes the reading `unverifiable` (I-3).
  - **Readers added to I-7's list:** `load_delivery`; the `delivery` argument of `is_delivered`; G-5; and `write_delivery`'s precondition.
  - **Rule.** A delivery record read from evidence never causes a new local delivery write. `--record-delivery` treats it as already recorded, G-5 compares against it, and a contract delivered through the parent-branch layout reads delivered in a swept tree.
- **I-13 (the scope gate; declared divergence).** The implementation runs the records reading only where it can work. This gate exists for in-process drivers written before 0.13.0 (tests and callers that call `main()` from a folder with no repository metadata).
  - **What it may test.** Only whether the working directory is a git tree carrying the repository metadata the reading needs. It runs `git remote get-url origin`:
    - **Exit 2** means no `origin` remote. The gate is off, and the run behaves as before 0.13.0.
    - **Any other failure** while a `.git` entry exists makes the reading `unverifiable`, never "no reading".
  - **What it must not test.** Where the contract file sits. A path-form `--contract` that points at another tree's concepts folder still carries the keys and still gets exit 12 on `--dispatch`.
  - **Required.** A test pins this. `skills/pr-merged/SKILL.md` names the gate and what it is for.
- **I-14 (smaller rules made explicit at review):**
  - **Mode check.** The identity test requires the blob mode to be 100644 or 100755. A 120000 (symlink) blob is never `proven`.
  - **gh logged out.** `gh` present but not authenticated is `persistent` (I-3).
  - **Same repository only.** The sweep applies the G-1 `GH_REPO` refusal. It counts only same-repository pull requests (`isCrossRepository` false) as the stable branch's open pull request.
  - **Slug check.** The sweep checks its slug against an existing contract or results folder. It refuses a partial, empty or glob-shaped slug (`sweep-usage`, exit 2).
  - **Combined flags.** `--locate-parent` together with `--sweep-records` is a `sweep-usage` refusal.
  - **Re-runs.** A `--record-delivery` re-run that writes nothing also writes no state store.
  - **No confirmation (Q1).** `/flow` Step 8 and `contract-completion.md` do not ask for a confirmation before the stable-branch records push.
  - **Skill test counts.** They are taken from the suite's own `Ran N tests ... OK` line, never from a grep of test methods.
- **Second reader `_records_at` (declared divergence).** The contract planned a `fetch` argument on `origin_records`. The implementation added a separate reader, `_records_at`. It must be folded into `origin_records(fetch=False)`. If that is impossible, both must call one shared parser and one shared filter (the delivery-record exclusion and the mapping check), and a parity test must feed both the same tree, so they cannot drift. Second amendment: the parity test must include a 120000 (symlink) `.yaml`, a nested file and `contract-delivery.yaml` whenever the recursive, mode-filtered listing cannot itself be shared.

- **Second post-implementation amendment (2026-11-02), accepted limitations:**
  - `--discard-differing <path>` acts in every swept tree where that path differs, not in one chosen tree.
  - `--status` with `GH_REPO` set can misread another repository's pull requests. The sweep itself refuses `GH_REPO` (I-14).
  - `run_sweep_records` falls back to `master` through `default_branch()` when the default branch cannot be read.
  - A path with trailing whitespace at the end of a `-z` listing fails closed (it reads `unverifiable`).
  - Report-only fields seeded from local records (`review_verdicts`, the hand-resolved seed) still read local records. They change no decision, and are known local-only NITs.

### Events

Not applicable. Reason: the loop has no event bus; its outputs are the JSON report and the printed lines.

### Commands

| Name (imperative) | Handler | Payload | Possible rejections |
|-------------------|---------|---------|---------------------|
| Sweep records leftovers | `pr_merged.py --contract <slug> --sweep-records [--from <tree>]... [--removed <tree>]... [--discard-differing <path>]... [--dry-run] [--json]` | slug, trees, owner discards. It runs before the `contract-not-found` refusal (~3961), so no local contract is needed | exit 2 with a JSON `error` (`sweep-usage` when combined with `--pr`/`--record-delivery`/`--dispatch`/`--status`; `tree-not-found`; `not-a-tree-root`; `not-this-repository`; `not-differing`); exit 10 when `unverifiable`; exit 0 otherwise, with kept files and `gone` included |
| Run the records step | `/pr-merged --records <slug> [--discard-differing <path>]` (skill) | slug | Input is `records_unpushed` from `--status --json` in the starting tree. On the same-session path it also carries a flip's `written_files` outside the results folder (contract, brief). It pushes to the stable branch (I-4) and opens a draft pull request when none is open, which also covers `records_stranded`. It halts on `unverifiable` (naming the cause per I-5) and on I-11. Under `--local-evidence-only` it pushes nothing. "Nothing to do" applies only when the reading is `ok` and both lists are empty |
| Skip records actions for one run | `--local-evidence-only` on any `pr_merged.py` mode that carries the keys; passed through by both skills | owner's word | none. The report shows `records_action: skipped-by-owner`: no delete and no push. Evidence, holds and the dispatch refusal are unchanged |
| Dispatch | `pr_merged.py --dispatch <id>` (existing) | unchanged | `records-unpushed` / `records-unverifiable`, exit 12 (I-9) |

---

## Reused Mechanisms

- **Records pull request**, the single stable branch `docs/<slug>-records`, and the existing push procedure — consumed as-is. The sweep reads that exact branch name. `records_branch_prefix` (`pr_merged.py:2922`) is unchanged for its existing callers.
- `fetch_default_branch` (`pr_merged.py:2843`) — consumed as-is, once per ref. Its refspec works for any branch name.
- `origin_records` (`pr_merged.py:2861`) — **extended by** an optional `fetch` argument (default on, as today). The sweep turns it off after its single fetch. It returns none on any failure (I-3). *Divergence:* the implementation added `_records_at`; it is to be folded in, or made to share one parser and one filter (amendment after I-14).
- `_tree_names_at` (`pr_merged.py:2589`) — **extended by** a strict sibling, `_tree_blobs_at` (`-r`, none on failure, `{name: blob}`). The original and its callers are unchanged.
- `open_records_pull_requests` (`pr_merged.py:2823`) — **extended by** an optional `head` argument (`gh pr list --head <branch> --state open`). It stays the one reader of "is a records pull request open". The sweep and the records step use the head form for `docs/<slug>-records`, and existing callers are unchanged.
- `merge_evidence` (`pr_merged.py:2898`) — **extended by** `branch_heads` and I-6 rule 2, inside the same function; rule 1 is today's rule.
- `is_delivered`, `next_command_for`, `ADVANCE_ACTIONS` — consumed as-is (I-5, I-7).
- `tree_kind` / `main_checkout_root` (`.claude/hooks/_project_paths.py`, re-exported by `_claude_paths.py`; `MECHANISMS.md` line 43) — consumed as-is for I-1, imported lazily the way `pr_merged.py:2501` imports `project_dir`.
- **Delivery cleanup → Landed untracked files** (`MECHANISMS.md` line 75): `_hash_files` and `_plain_file_inside` — consumed as-is through a lazy import inside the sweep. `compare_untracked` is **not** called: the sweep does its own failure-aware, mode-filtered listing (`_tree_blobs_at`), because it needs the differing blob and the absent/differing split. `cleanup_delivered` imports `pr_merged` at its top, which is why the import is lazy.
- `written_files` — consumed as-is, only for the flip's contract and brief on the same-session path.
- **Flat worktree helper** — consumed as-is by the records step.

## New Mechanisms (if any)

None. Everything is an extension:
- one script mode with its flags, plus the owner flag `--local-evidence-only`;
- new report keys;
- `merge_evidence`'s new argument and rule;
- `origin_records`' `fetch` argument;
- a strict sibling of `_tree_names_at`;
- a wrapper around the Next Command;
- one guard in two write routes;
- one dispatch refusal;
- the records step re-opening a pull request from the stable branch.

**Registry candidate (requested by the reviewer).** The **Records leftover sweep** (`--sweep-records`, which reuses Delivery cleanup's `_hash_files` and `_plain_file_inside`, not `compare_untracked`) and the **Records reading** (failure-aware evidence for completion and delivery records, with `records_reading`, holds and exit 12) form a reusable pattern. A `MECHANISMS.md` Universal-tier entry for them is appended with the implementation, extend-by included. It sits beside the **Delivery cleanup** entry, not inside it.

---

## Extension Points

1. `pr_merged.py` argparse (~3897): add `--sweep-records`, `--from`, `--removed`, `--discard-differing` and `--local-evidence-only`, with the refusals in Commands. `--sweep-records` is handled before the `contract-not-found` refusal (~3961).
2. `pr_merged.py`: add the reading (I-1–I-3) and `_tree_blobs_at` beside `origin_records`, plus `origin_records`' `fetch` argument. The reading is called once per run, in the modes that carry the keys.
3. `main()`: build `evidence` (I-6) before the `--pr` / `--record-delivery` loops, then refresh it with this run's writes. Route every reader I-7 lists through it. Apply I-7's hold and I-8's guard and refusal.
4. `main()` after line ~4755: I-5. `--dispatch`: I-9.
5. `skills/pr-merged/SKILL.md`:
   - Step 3: keep the stable-branch push rule and the anti-pattern at ~617–618 as they are. Add: open a new draft pull request when none is open (I-4), and sweep after a successful push (`--from <start> --removed <records worktree>`). Replace "Never leave the records uncommitted" with the sweep rule.
   - Document `--local-evidence-only` as "skip deleting and pushing for this run". It never unblocks dispatch; a persistent read failure is cleared by fixing its named cause.
   - Add `--records <slug> [--discard-differing <path>]`.
   - Apply Q1's confirmation rule.
   - Report: add `- Records left in starting tree:` and `- Trees:`.
   - Apply I-11.
   - Reword ~323–326 (append-only: a completed record replaces a failed one only through `update`; a differing completed record is never overwritten, the owner decides) and the anti-patterns ~597/~601 to match.
   - Update the test count at ~77–82, and the Q1 anti-pattern bullet.
6. `skills/pr-merged/references/contract-completion.md`, "The records pull request":
   - step 6: the branch is always the stable `docs/<slug>-records`, fetched first and committed on top when it exists, cut from `origin/<default>` only when absent. The `-2`/`-3` suffix is reworded to name the worktree folder only;
   - step 8: open a draft pull request when none is open from the stable branch;
   - step 7 copies `records_unpushed` plus the flip's `written_files`;
   - step 9 runs the sweep with `--removed`;
   - the "fresh worktree" remedy text is reworded.
7. `skills/advance/SKILL.md`:
   - Step 1 branches on `records_reading`:
     - `unverifiable` → halt with I-5's reason (retry for `transient`, fix the named cause for `persistent`), and dispatch nothing;
     - a non-empty `records_unpushed` or `records_stranded` → run the records step and re-read (exit 12 → the same);
     - `records_differing` → show the remedies and continue;
     - I-11 applies.

     `--local-evidence-only` is passed through on the owner's word. It only skips deleting and pushing.
   - Line ~113: records on the stable branch tip count as evidence, and the backstop stays.
   - Step 2.5: sweep with every touched tree, the `--dispatch` worktree included.
   - Step 3: add `- Trees:`.
   - Update the test count.
7a. `skills/flow/SKILL.md` Step 8 (lines ~514–521), a minimal edit:
   - For orchestrator result records of a contract, the follow-up branch is always the stable `docs/<contract-slug>-records`, single-sub-task contracts included, under the same rule as line 516. A kept copy is then judged against that branch and is not pushed twice.
   - After Step 8's push, run `--sweep-records --from <starting tree>` (plus `--removed` for any tree it removed) and print its Tree-clean lines verbatim.
   - The sweep is the deleter for result records. Step 8's own "prove before deleting" rule still covers every other file.
8. `README.md`: a "Changed in 0.13.0 (issue #178)" note. A project that vendors `pr_merged.py` must sync it, or the skills halt per I-11.
9. `.claude/registries/VOCABULARY.md`: append the seven terms. It is a shipped registry, so it rides this raise.
10. Version 0.12.4 → 0.13.0 in all five manifest places.

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| `.claude/scripts/pr_merged.py` | `skills/pr-merged/SKILL.md`, `skills/pr-merged/references/contract-completion.md`, `skills/advance/SKILL.md`, `skills/flow/SKILL.md` | `--json` report, printed lines, exit codes | the report keys, `already_recorded`, `tree_lines`, `next_command`, refusals with exit 12 | script → skill |
| `.claude/scripts/pr_merged.py` | `.claude/scripts/cleanup_delivered.py` | lazy import of three helpers | Untracked Comparison (unchanged) | script → script |
| `.claude/scripts/pr_merged.py` | `.claude/hooks/_project_paths.py` via `_claude_paths.py` | `tree_kind`, `main_checkout_root` | Tree kind (unchanged) | script → helper |
| `.claude/scripts/pr_merged.py` | GitHub | `open_records_pull_requests` (existing) | open records pull requests | read |

- [ ] The producer (`pr_merged.py`) and its three skill consumers change in the same pull request. `cleanup_delivered.py` and `_project_paths.py` do not change.

## Adjacent Areas

The cross-area scan (run by the main session) reported primary area none and no adjacent area above the threshold. The architect noticed these areas:

| Area | Decision | Implication / Reason | Handle |
|------|----------|----------------------|--------|
| Delivery cleanup (`cleanup_delivered.py`) | not applicable | I-7 keeps its `load_records_at(origin/<default>)` → `is_delivered` gate (`cleanup_delivered.py:268-270`) unchanged; its helpers are only imported (`MECHANISMS.md` line 75). | — |
| Contract landing (`land_contract.py` record reading, `:1995`, `:3089-3093`, remedies `:111`, `:2027`) | not applicable | Unchanged, because the single stable branch `docs/<slug>-records` is kept (I-4). Every record the loop pushes stays where the landing reads it, and the brief's out-of-scope list excludes changing that reading. | — |
| `/flow` Step 8 (`skills/flow/SKILL.md:514-521`) | in-scope | Under `/flow`, the records push is Step 8's (`skills/pr-merged/SKILL.md:339`), so Step 8 gains the sweep and its Tree-clean lines. Single-sub-task contracts also use the stable branch, so a kept copy is judged against it and never pushed twice (Extension Point 7a). The multi-sub-task stable-branch rule at line 516 is unchanged. | `skills/flow/SKILL.md` in Files to touch |

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

## Chat Tool Impact

2. No — this endpoint/event is UI-only or admin-only: in substance there is no endpoint or event at all; the contract changes a local workflow script, so no chat tool can wrap it.

## Non-Goals

- Moving records to the parent branch, changing where `land_contract.py` reads records (brief, out of scope), or changing the single stable records branch rule.
- Changing how a sub-task maps to its pull request.
- Merging records pull requests (that stays with the person).
- Touching the flip's modified contract and brief in the starting tree, or recovering them in a later session.
- Changing Delivery cleanup, `build_record` or the state store. `/flow` Step 8 changes only as Extension Point 7a says.

## Confidence

Confidence: Medium. High on the deletion and failure rules: Delivery cleanup's tested identity check, failure-aware readers, and the tested tree classifier. High on the push path, which is the shipped stable-branch rule plus a pull-request re-open, now traced on the `/flow` route too. High that `--local-evidence-only` cannot reopen re-dispatch, because it only skips deleting and pushing. Medium on I-6 and I-7: every existing `advance()`, candidate, G-7 and completion scenario in the 530+ test suite must stay green with `evidence` routed through them. Medium on the lazy cross-import, which is assumed. After review: Medium on I-12, because the delivery-record evidence was missed at design time, and the swept-tree delivery and G-5 tests are what close it. Medium on I-13 until its test pins a contract path outside the working tree.

## Alternatives Considered & Why Rejected

- **Option A (chosen):** delete each identical copy right after the push. Judge copies against `origin/<default>` and against the stable records branch tip while its pull request is open. Read one shared evidence everywhere. Hold the loop when a read fails, with an owner way out.
  - Why: criterion 1 holds right after the push, as the user requires. Every decision reads one fact, and the landing's single branch is untouched.
- **Option A4 (rejected, round 4):** cut a fresh `-2`/`-3` records branch whenever the stable branch's pull request is not open.
  - Why rejected: the landing (`land_contract.py:1995`), its remedies, `/flow` Step 8 and the SKILL.md anti-pattern all require the one stable branch, so a suffixed branch hides records from the landing.
- **Option E (rejected by the user at the gate, 2026-11-02):** delete only copies already on `origin/<default>`.
  - Why rejected: it is simpler, but criterion 1 must hold right after the push, not after the records pull request merges.
- **Option A2 (rejected):** local-wins evidence beside `merge_evidence`.
  - Why rejected: it is a second, reversed rule (journal 2026-10-30, one shared reader).
- **Option A3 (rejected):** discard a `differs` copy automatically.
  - Why rejected: it silently loses a record the owner may need.
- **Option B (rejected):** extend `cleanup_delivered.py`.
  - Why rejected: its gate fires only after the flip, which is the wrong moment.
- **Option C (rejected):** judge copies by `written_files`.
  - Why rejected: that is session memory, which cannot see a failed push.
- **Option D (rejected):** a ninth `ADVANCE_ACTIONS` move.
  - Why rejected: unpushed records are orthogonal to the plan position, and a move would hide the real move.

## Uncertain Assumptions

- `VERIFIED via pr_merged.py:2589-2617`: `_tree_names_at` and `load_records_at` swallow failures (so they are not used here).
- `VERIFIED via pr_merged.py:2861-2895`: `origin_records` returns none on failure.
- `VERIFIED via pr_merged.py:2826-2840`: `open_records_pull_requests` lists only open pull requests (`--limit 200` of open ones), with a prefix match, and returns none on failure. It is the one reader of open-ness; the sweep matches the exact head name.
- `VERIFIED via the round-4 critique's citations`: the landing reads the parent branch, `origin/docs/<slug>-records` and `origin/<default>` (`land_contract.py:1995`, `:3089-3093`); `/flow` Step 8 (`skills/flow/SKILL.md:516`) requires the single stable branch.
- `VERIFIED via pr_merged.py:4513-4639`: `--dispatch` refusals are inline JSON with exits 2–7; 12 is free.
- `VERIFIED via pr_merged.py:2885-2893`: `origin_records` returns none when any blob fails to parse, which is why I-3's cause names the `<ref>:<path>` and classifies it `persistent`.
- `VERIFIED via skills/flow/SKILL.md:514-521`: Step 8 pushes result records itself, and names the stable branch only for multi-sub-task contracts (hence Extension Point 7a).
- `VERIFIED via pr_merged.py:3805-3811`: the flip already reads `pending` while a records pull request is open.
- `VERIFIED via MECHANISMS.md line 43`: `tree_kind` and `main_checkout_root` are re-exported for `pr_merged.py`. `pr_merged.py` does not call them yet; it imports from `_claude_paths` lazily elsewhere (~2501).
- `VERIFIED via cleanup_delivered.py:472-505`: `compare_untracked` folds absent into differing, and gives no blob for a differing file (hence `_tree_blobs_at`).
- `VERIFIED via cleanup_delivered.py:268-270`: Delivery cleanup's gate reads `origin/<default>` only.
- `VERIFIED via the main session's scan`: no adjacent area above the threshold.
- `ASSUMED`: the lazy `import cleanup_delivered` works when `pr_merged.py` runs as `__main__`. If not, the implementer moves the three helpers to a shared module and amends this contract.
- `ASSUMED`: a minor raise (0.13.0) is right, because a new script mode is a new capability.

## Failure Modes & Mitigations

- **FM (second review):** a merged-and-kept records branch goes stale when `origin/<default>` changes a path through another route. It then reads stranded forever, holds the flip, makes `--dispatch` exit 12, and its remedy opens a pull request that reverts origin's newer record.
  - **Mitigation:** the ancestry check (Compared refs). A tip that is an ancestor of `origin/<default>` is never stranded or unpushed, and a failed check is `unverifiable`.
- **FM (second review):** a re-delivery by a different pull request over a completed record is silently pushed or swept.
  - **Mitigation:** it is `differs`. A person decides through `--discard-differing` or by hand (I-8).
- **FM (found at review):** after the sweep deletes `contract-delivery.yaml`, a parent-branch contract reads undelivered in that tree for good, G-5 is bypassed, and a fresh local delivery record is written.
  - **Mitigation:** I-12. The delivery record is read from evidence and never rewritten from it.
- **FM (found at review):** the scope gate keys on the contract file's location, so a path-form `--contract` silently loses the keys and the exit 12.
  - **Mitigation:** I-13. The gate keys only on the working directory's git metadata.
- **FM:** a swept tree re-dispatches finished work.
  - **Mitigation:** I-6 and I-7 (one evidence for every decision), and an `unverifiable` reading holds the loop.
- **FM:** a failed read turns `differs` into `unpushed`, or empties the evidence.
  - **Mitigation:** I-3's failure-aware readers and `records_reading`.
- **FM:** a copy is deleted against a branch that is not on its way to `origin/<default>`.
  - **Mitigation:** the tip counts as proof only while an open pull request has the stable branch as its head.
- **FM:** the records pull request is closed unmerged after the sweep.
  - **Mitigation:** while the branch exists, the record stays on it, because the loop never re-cuts it. It still counts as evidence (I-6), so nothing is re-dispatched. It reads as Records stranded: the flip is held and the Next Command names `/pr-merged --records <slug>`, which re-opens a draft pull request from the same branch.
  - **Residual risk:** if a person also deletes the branch, the record exists nowhere the loop reads. The ways back are `/pr-merged <sub-task pr>` (re-records from GitHub) or `git fetch origin refs/pull/<n>/head` from the closed records pull request (I-4). Until then, `/advance`'s backstop stops a re-dispatch.
- **FM:** a read fails permanently (a malformed record, no `gh`, offline).
  - **Mitigation:** the cause names the exact ref or `<ref>:<path>`, classified `persistent`. Dispatch stays refused until the owner fixes it. `--local-evidence-only` only skips deleting and pushing for non-dispatch work, and never unblocks dispatch.
- **FM:** a `--from` subfolder prints `clean` over real leftovers.
  - **Mitigation:** `not-a-tree-root` (I-1).
- **FM:** the landing cannot see a pushed record.
  - **Mitigation:** the single stable branch is kept (I-4).
- **FM:** a re-run duplicates records or closes a sub-issue again.
  - **Mitigation:** I-8 on both routes, plus exit 10 on an `unverifiable` writing run.
- **FM:** a re-delivery is stuck behind a failed record.
  - **Mitigation:** `update` plus I-6 rule 2. A failed record written this run still escalates (rule 1).
- **FM:** CRLF copies of LF blobs never match.
  - **Mitigation:** `hash-object` with filters on.
- **FM:** a junction redirects a delete outside the tree.
  - **Mitigation:** `_plain_file_inside`, checked right before each delete.
- **FM:** a mistyped `--from` silently sweeps nothing.
  - **Mitigation:** `tree-not-found`. Only `--removed` may be gone.
- **FM:** an older vendored script reads as "nothing pending".
  - **Mitigation:** I-11.

## Open Questions for User

- [x] **Q1 — Should every records push skip its confirmation, as the completion hand-off push already does?** **Recommendation: yes, for the push itself.** It carries only docs files, goes to the one stable records branch, never force-pushes, and merging stays with the person. The step-3 evidence confirmation before a flipping run (skipped checks, owner-resolved reports, disclosures) stays. If yes, the SKILL.md anti-pattern "Moving the completion hand-off push's no-prompt rule to other pushes" is rewritten to match.
  → **Answered 2026-11-02 (user): yes.** Every records push to the stable branch runs without asking; the pre-flip evidence confirmation (contract-completion.md step 3) stays. The SKILL.md anti-pattern bullet is rewritten to match.
- [x] **Q2 — How is the records step spelled in the Next Command?** **Recommendation: `/pr-merged --records <contract-slug>`.** It is runnable, and it lives in the skill that owns the procedure.
  → **Answered 2026-11-02 (user): `/pr-merged --records <contract-slug>`.**
- [x] **Q3 — May a record on the stable records branch count as evidence, and, while its pull request is open, as proof for the sweep?** Answered 2026-11-02: (a). The user rejected the alternative (Option E) at the gate, so the body applies (a).

---

## Critique

**Critic:** contract-critic (round 5; rounds 1 to 4 moved to `.claude/contract-history/2026-11-02-pr-merged-records-leftover-cleanup.round-1.md` to `.round-4.md`)
**Date:** 2026-11-02
**Verdict:** blockers-found

The fourth amendment fixes round 4's BLOCKER: one stable branch, no `-2` branch, and the landing and `/flow` Step 8 unchanged for multi-block contracts. It also fixes round 4's WARNs on G-7, `not-a-tree-root`, exempt modes, the exit 10/12 split and `contract-not-found`. Option E is not raised again. The findings below are about the body as it reads now. Most are new routes opened by `--local-evidence-only`, the open-PR condition and Records stranded.

### Findings

- **[BLOCKER] `--local-evidence-only` brings back re-dispatch of finished work in any swept tree, and the contract calls it "exactly the pre-0.13.0 behaviour"**
  - **What is wrong:** with the flag on, `evidence` is "today's (local records, plus `origin/<default>` where the existing code already reads it)".
    - Today `advance()` and `delivery_candidates` read only local `records` (`pr_merged.py:4483`, `:4520`). `origin/<default>` is read only by G-7 (`:4237`) and the layout block (`:4727`).
    - `compute_released` treats a sub-task with no record as open work (`pr_merged.py:604-606`).
    - So in a tree an earlier 0.13.0 run has already swept, every swept sub-task reads as open again. That holds both before and after its records pull request merges.
    - I-9 lifts the dispatch refusal under the flag ("neither refusal applies"), and I-8's re-run guard also reads that local-only `evidence`.
    - Before 0.13.0 the same tree still held the untracked copy, so the behaviour is not the pre-0.13.0 one.
    - I-5's `unverifiable` reason names `/advance <slug> --local-evidence-only` for every failure, transient ones included. The TASK block pins "holds nothing and refuses nothing" as the tested behaviour.
    - The owner's way out therefore leads straight into Failure Mode 1, and only the prose backstop at `skills/advance/SKILL.md:113` stands in front of it.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A rule that refuses must give already-delivered work a named way out" (the exit must not lead the loop to redo delivered work); `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery, not only the one the author had in mind".
  - **Where in this contract:** `I-3`: "That is exactly the pre-0.13.0 behaviour, and the report says so"; `I-9`: "Under `--local-evidence-only` neither refusal applies"; `## Failure Modes`: "a swept tree re-dispatches finished work", whose mitigation does not name this flag.
- **[WARN] Records stranded and I-4's "open a draft pull request when none is open" depend on a reader that cannot see past 200 open pull requests**
  - **What is wrong:** `open_records_pull_requests` runs `gh pr list --state open --limit 200` with no `--head`, then filters by prefix (`pr_merged.py:2826-2838`).
    - When a repository has more than 200 open pull requests and the records pull request is not among them, the reader returns an empty list instead of failing.
    - Before this contract, that only meant a missed G-6 refusal.
    - Now the same empty list does three things. The tip stops counting as proof. A records-folder path that is only on the tip reads as Records stranded, so the flip is held and `--dispatch` exits 12. And the records step tries to open a second pull request for a head that already has one, which `gh pr create` refuses.
    - The loop then has no exit. I-3 says every reader it uses tells "failed" from "empty", and this one does not.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-01 "A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for".
  - **Where in this contract:** `I-3`: "`open_records_pull_requests` (none on failure). It is the ONE reader of 'is a records pull request open'"; `## Uncertain Assumptions`: "lists only open pull requests (`--limit 200` of open ones)".
- **[WARN] Without an open pull request the tip is not compared, so a copy that is already on the stranded tip, or that conflicts with it, reads `unpushed` and is pushed on top**
  - **What is wrong:** a stable branch with no open pull request is not a Compared ref.
    - A starting-tree copy that is identical to the stranded tip therefore reads `unpushed` ("no compared copy exists"). It lands in both `records_unpushed` and `records_stranded`.
    - The records step then copies it and commits, but the commit is empty. The contract does not say whether an empty commit counts as a "successful push", which decides whether the pull request is re-opened and the sweep runs.
    - A local `failed` copy whose path holds a `completed` record on the stranded tip also reads `unpushed`, not `differs`. The records step would then commit the failed record over the completed one. That breaks I-4's "Never. The loop never pushes over a completed record".
    - Example: a second tree whose failed copy was kept as `differs` while the pull request was open, and the pull request was then closed unmerged.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-28 "A new term's definition must be true against every existing member" (`unpushed` and Records stranded overlap); `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery".
  - **Where in this contract:** **Compared refs**: "Without an open pull request, the tip is never proof"; **Records leftover**: "`unpushed` — no compared copy exists"; `I-4` "Never".
- **[WARN] A records branch deleted after its pull request closed unmerged still loses the swept record, but the Failure Modes say the record "stays on the stable branch"**
  - **What is wrong:** round 4 named both closing the pull request and deleting its head. The amendment answers only the close.
    - A person who closes a records pull request often deletes its branch too, from the GitHub button.
    - After that, `ls-remote` finds no stable branch, so the tip is gone from I-6's `evidence` and Records stranded is empty.
    - The starting-tree copy was already deleted while the pull request was open.
    - The sub-task now has no record anywhere the loop reads. Nothing holds the loop, and no Next Command names a way back, such as re-recording with `/pr-merged <pr>`.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A rule that refuses must give already-delivered work a named way out"; round 4 WARN "A records pull request closed without merging … or deletes the head" (`.claude/contract-history/2026-11-02-pr-merged-records-leftover-cleanup.round-4.md`).
  - **Where in this contract:** `## Failure Modes`: "the record stays on the stable branch, which is never re-cut"; **Records stranded**: "They are not lost, because the stable branch is never re-cut".
- **[WARN] The `/flow` route is not traced: under `/flow` the records push is `/flow` Step 8's, so the new sweep, Tree-clean lines and pull-request re-open never run there**
  - **What is wrong:** `skills/pr-merged/SKILL.md:339` says that when `/flow` runs this phase, the files go to `/flow` Step 8 "instead of committing here".
    - Extension Point 5 adds the sweep "after a successful push" in Step 3, but under `/flow` Step 3 makes no push.
    - `/flow` Step 8 (`skills/flow/SKILL.md:514-520`) deletes copies by its own rule ("compare it with the committed or master copy, ignoring line endings"). That rule is separate from the I-2 deleter.
    - For a single-sub-task contract, Step 8 pushes to "a small follow-up branch from freshly fetched `origin/master`" with no required name. Only multi-sub-task contracts must use `docs/<contract-slug>-records`. A record pushed there is never a Compared ref, so a kept copy reads `unpushed` and the records step pushes it a second time.
    - The Adjacent Areas row says Step 8's rule "is exactly I-4's" and that `/flow` "leaves no untracked leftover". Both are true only for the multi-sub-task half of line 516.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery, not only the one the author had in mind"; `skills/flow/SKILL.md:516`, `:519`.
  - **Where in this contract:** `## Adjacent Areas` → "`/flow` Step 8 … | not applicable | Unchanged, because the single stable branch is kept: its 'one stable branch, never re-cut' rule is exactly I-4's"; `## Extension Points` 5.
- **[NIT] `proven` is said to be "exactly a Landed untracked file" against `origin/<default>`, but that term is defined for "an untracked file in an owned worktree"** — the starting tree may be the main checkout or a tree outside the Owned set (`VOCABULARY.md` line 61, line 59; `JOURNAL.md` 2026-10-28 "A new term's definition must be true against every existing member").
- **[NIT] I-1 accepts `main-checkout`, so the sweep's `os.remove` writes in the main checkout, and the contract does not say why this fits the main-checkout guard** — the guard refuses "file writes … aimed at the session's main checkout" (`MECHANISMS.md` line 67). A delete done by a script is invisible to it.
- **[NIT] A `--removed` tree that Windows only partly removed (folder left, `.git` gone) is refused `not-a-tree-root` with exit 2, and that refusal stops the sweep of the starting tree too** — Delivery cleanup carries a rename probe exactly because Windows removals partly fail (`MECHANISMS.md` line 75).
- **[NIT] I-11 detects an older script only through a missing `records_reading` or `unrecognized arguments: --sweep-records`** — an older script given `--local-evidence-only` exits 2 with `unrecognized arguments: --local-evidence-only`. That falls to the verbatim halt with no "sync the vendored copy" message (`JOURNAL.md` 2026-10-04 "Detect an install mode by what the sync actually delivers").
- **[NIT] Q3 option (b) is Option E, which the user already rejected, so Q3 is answered and still takes up an Open Question** — the template's budget rule shrinks resolved questions to one line (`.claude/templates/concept-contract.md` line 22; `JOURNAL.md` 2026-10-22 "An accepted critic WARN or answered Open Question must amend the contract body before approval").
- **[NIT] The body is about 14,000 tokens against a 12,000 budget** — the header note discloses the overrun, which has grown by about 1,000 tokens since round 4 (`.claude/templates/concept-contract.md` line 22).

### Applicable journal entries

- **2026-10-17 — Judge "identical to master" by git's view** — heeded by `I-2` (`hash-object`, filters on).
- **2026-10-17 — Git for Windows lists files beneath an untracked junction** — heeded by `I-2` (`_plain_file_inside` immediately before each delete).
- **2026-10-15 — A cleanup wired before its trigger never runs** — heeded: the sweep is idempotent and runs on every call.
- **2026-10-15 — A fallback that finds "the brief" by the caller's own branch** / **2026-10-16 — An unset ownership field is not proof** — heeded by `I-1` (exact results folder, exact branch name, tree classifier).
- **2026-10-16 — A skill step that moves the shell** — heeded by `--from` / `--removed` with `git -C`.
- **2026-10-15 — A skill that edits a lookup block must name the test** — heeded by the TASK run list (`test_skill_script_lookup.py`).
- **2026-10-28 — Do not promote an extension seam** — heeded: New Mechanisms is None, and `tree_kind` / `main_checkout_root` / `merge_evidence` are extended or reused.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by `records_reading` plus `records_untracked`, and by `tree-not-found` versus `gone`.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded: exit 12 is free in `pr_merged.py`, and `skills/advance/SKILL.md:210` stays true.
- **2026-10-04 — Detect an install mode by what the sync actually delivers** — heeded by I-11 for the keyed modes; partly not for the new flag, see NIT.
- **2026-10-28 — State the real trigger** — heeded: I-3 states the new `origin/<default>` fetch and the per-run reads.
- **2026-10-30 — A failed record written by a new rule must not feed an older guard** — heeded by I-6 rules 1 and 2.
- **2026-10-30 — One shared reader must own the filtering** — heeded: I-7 lists G-7, G-3, the already-recorded test and the `--record-delivery` candidate read.
- **2026-10-22 — Amend the body before approval** — heeded for Q1 and Q2; Q3 left open although it is answered, see NIT.
- **2026-11-01 — After merging a base that changes the row shape a feature reads** — heeded: the single stable branch keeps every reader in `land_contract.py` and `/flow` Step 8 (multi-sub-task) unchanged.
- **2026-10-30 — A delivery rule must name every route** — violated: the `/flow` Step 8 single-sub-task route and the `--local-evidence-only` route, see BLOCKER and WARN.
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — violated: the owner exit re-dispatches swept work, and a deleted stranded branch has no way back, see BLOCKER and WARN.
- **2026-11-01 — A shared reader reused by a stricter consumer** — heeded for `_tree_blobs_at` and `origin_records`; violated for `open_records_pull_requests`' 200-item truncation, see WARN.
- **2026-10-28 — A new term's definition must be true against every existing member** — violated by `unpushed` overlapping Records stranded, and by `proven` = **Landed untracked file**, see WARN and NIT.
- **2026-10-15 — Locate a script from the plugin root** — not addressed: the contract adds no new script lookup.

### What the critic did not check

- No CodeGraph tool was available to this critic. Code claims were checked with Grep and Read on `pr_merged.py`, `land_contract.py` and the three skill files (`pr-merged`, `advance`, `flow`).
- Checklist item 14 was not run, because this critic has no shell. By reading: there is one mergeable block, the brief header is present, and the block raises the version itself.
- `.claude/registries/INTEGRATION.md`, `.claude/north-stars/` and `.claude/.scout-cache/registry-digest.md` do not exist, so items 7, 12 and 13 produce no findings. The cross-area scan reported no primary area, so item 11.a does not apply.
- Not tried: the token count (estimated at about four characters per token), the lazy `cleanup_delivered` import (ASSUMED), and whether `git worktree remove` on Windows leaves a folder without `.git`.

---

### Critique responses (user, 2026-11-02)

- Rounds 1 to 5: every BLOCKER and WARN was either **addressed** in the body by the architect's amendments or, for the round-5 findings, by the final targeted pass (which received no further critic review, by the user's choice). The simpler Option E was **rejected** by the user at the gate (criterion 1 must hold right after the push).
- Round-5 NITs not applied and the body exceeding the 12,000-token budget (about 15,000, explained in the header) are **deferred** with the user's approval.
- The implementation review (fullstack-code-reviewer, test-strategy-critic) is the next line of defence.

---

## Lessons referenced

- **2026-10-17 — Judge "identical to master" by git's view; untracked junction parent-link check** — I-2.
- **2026-10-15 — A cleanup wired before its trigger never runs** — the sweep runs after every push and at the end of every `/pr-merged` and `/advance` call. It is idempotent.
- **2026-10-16 — An unset ownership field is not proof of ownership** — I-1: the contract's own results folder, in trees proven by the tree classifier.
- **2026-10-16 — A skill step that moves the shell** — `--from` / `--removed` with `git -C`. The shell's position never matters.
- **2026-10-28 — Do not promote an extension seam** — no New Mechanism. I-1 reuses `tree_kind` / `main_checkout_root` and does not reimplement them.
- **2026-10-28 — A new term's definition must be true against every member** — the Tree-clean line names the exact flags, and the skills pass every tree they touched.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and missing case** — `records_reading` plus `records_untracked` remove the null-versus-empty ambiguity. `tree-not-found` versus `gone` is explicit.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — I-9 cites the real inline refusals (exits 2–7) and the free exit 12.
- **2026-10-04 — Detect an install mode by what the sync delivers** — I-11.
- **2026-10-30 — A rule that refuses must give a named way out** — every hold names its remedy:
  - `--discard-differing`;
  - "retry" for a transient failure; for a persistent failure, the exact bad ref or path to fix (dispatch stays refused; `--local-evidence-only` only skips deleting and pushing);
  - for a deleted records branch, `/pr-merged <sub-task pr>` or `git fetch origin refs/pull/<n>/head`;
  - re-opening a pull request for Records stranded;
  - `/pr-merged --records <slug>`;
  - "merge <url>".

  No verdict names a command that I-8 skips.
- **2026-10-30 — One shared reader must own the filtering** — `merge_evidence` owns every precedence rule, and I-7 lists every decision reader in `main()`, including G-3, the already-recorded test and `reconcile_state`.
- **2026-10-30 — A delivery rule must name every route** — I-8 covers `--pr` and `--record-delivery`, and I-7 covers G-7 and the `--record-delivery` candidate read. I-4 keeps the one stable branch, so the landing, `/flow` Step 8 and the records step all see the same records. The `/flow` route gains the sweep and the stable branch for single-sub-task contracts (Extension Point 7a). The closed-unmerged route has its way back (Records stranded), and the deleted-branch route names its recovery. `--local-evidence-only` is traced and cannot reach dispatch.
- **2026-11-01 — After merging a base that changes the row shape a feature reads, re-check every reader** — I-4 was checked against every reader of the records branch (`land_contract.py`, `/flow` Step 8, the SKILL.md anti-pattern), and no reader changes.
- **2026-10-30 — A failed record must not feed an older guard** — traced in both directions:
  - rule 2 lets a completed re-delivery beat an older failed record;
  - rule 1 keeps a failed record written this run escalating.
- **2026-11-01 — A shared reader reused by a stricter consumer** — I-3 uses only failure-aware readers, and an `unverifiable` reading holds dispatch, release and the flip (I-7, I-9). A permanent failure names its exact ref and path for the owner to fix, and it keeps dispatch refused. The stable branch's open pull request is read per head, so the `--limit 200` cap cannot hide it. A subfolder `--from` is refused, because the tree helper walks up and would accept it.
- **2026-10-28 — A new term's definition must be true against every member** — the `proven` state is defined with its two proofs, and the registry's **Landed untracked file** is left meaning `origin/<default>` only. The report keys name the modes that carry them, and I-11 judges only those modes.
- **2026-10-28 — State the real trigger** — I-3 states the real per-run cost, including the new `origin/<default>` fetch.
- **2026-10-15 — A skill that edits a lookup block must name the test** — no lookup block moves, and `test_skill_script_lookup.py` is on the run list.
- **2026-10-22 — Amend the body before approval** — the Q1 and Q3 effects, and the SKILL.md lines ~323/597/601, are named in Extension Point 5.
- **2026-08-29 (stale-base reason for a fresh cut)** — unchanged: the stable branch is cut fresh from `origin/<default>` when it is absent, and never re-cut while it exists.
- Orthogonal to north-stars: none active.

---

## Implementation Handoff

**One mergeable block, on purpose.** The work is one script, its tests, four skill documents, the README, the vocabulary appends and the version. A second block or a review gate would trigger the Parent Branch Delivery Rule (a parent branch, a parent issue, sub-issues and a landing) for a change one pull request reviews comfortably. Review runs as `/flow`'s reviewer step, and the block raises the version itself.

### 1. Records leftover sweep (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/pr_merged.py`
- `.claude/scripts/tests/test_pr_merged.py`
- `skills/pr-merged/SKILL.md`
- `skills/pr-merged/references/contract-completion.md`
- `skills/advance/SKILL.md`
- `skills/flow/SKILL.md`
- `README.md`
- `.claude/registries/VOCABULARY.md`
- `.claude/registries/MECHANISMS.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**Pre-written TASK block:**
```
TASK: Implement the records leftover sweep and its evidence, re-run and dispatch rules (I-1 to I-11);
update the four skill documents (pr-merged, contract-completion, advance, flow Step 8), the README note, the VOCABULARY.md appends and the version (0.13.0,
all five places).
CONTEXT: concept contract at .claude/concepts/2026-11-02-pr-merged-records-leftover-cleanup.md
FILES: the Files to touch list above
CONSTRAINTS:
  - Invariants I-1 to I-14 (I-12 to I-14 and the _records_at note were added after review) are
    authoritative; no extra keys, states, moves or exit codes.
  - I-1 uses tree_kind / main_checkout_root (lazy import from _claude_paths); never git rev-parse
    --git-common-dir. I-3 uses only failure-aware readers; never _tree_names_at / load_records_at.
  - merge_evidence keeps "this run wins"; status-first applies only among the other sources (I-6).
  - Lazy-import _hash_files / _plain_file_inside (not compare_untracked); if that fails from the CLI, stop
    and emit an AMENDMENT.
  - Tests in test_pr_merged.py (temp git repos with a bare origin, gh stubbed), one per case:
    sweep: identical copy deleted; differing kept with both blob ids and remedy; --discard-differing
    deletes only a still-differing path; unpushed kept (failed push); update for completed-over-failed;
    nested file under the results folder classified (ls-tree -r); CRLF copy of LF blob is proven;
    dry run deletes nothing.
    stable branch: tip with an open PR is proof; tip without an open PR is never proof; a commit
    pushed after the last PR merged reads as stranded; a closed-unmerged PR after the sweep leaves the
    record as evidence, holds the flip (held: records-stranded) and names /pr-merged --records; the
    records step pushes on top of the existing branch (never re-cut, never a -2 branch) and opens a
    new draft PR when none is open; a local copy identical to a stranded tip makes no empty commit and
    the step still opens the PR; a local failed copy over a completed tip record is differs and is
    never pushed; the open-PR lookup for the stable branch uses --head and still finds it when the
    repository has more than 200 open PRs; no open PR at the moment of deletion -> nothing proven by
    the tip is deleted; a prefix-similar branch of another contract is ignored.
    unverifiable: failed ls-remote, gh, fetch, ls-tree or blob read -> records_reading unverifiable,
    cause names the exact ref or <ref>:<path>, records_failure transient or persistent (a record that
    does not parse is persistent), nothing deleted, released empty, no dispatch packet, Completion
    Verdict unverifiable, --pr/--record-delivery writing run exits 10, --dispatch exits 12 (never 10),
    also with zero leftovers; --local-evidence-only gives records_action skipped-by-owner, deletes
    nothing, pushes nothing, still refuses dispatch, and leaves evidence, released and the verdict
    unchanged.
    next command: unpushed or stranded prefixes (precedes /clear under dispatch; alone when blocked);
    transient unverifiable says retry, persistent names the cause, neither names
    --local-evidence-only; differing only names the remedy; nothing left is byte-identical.
    dispatch: exit 12 records-unpushed under --dispatch and --dry-run; differs-only does not refuse;
    --status never refuses.
    evidence: completed on the branch tip beats failed on origin/<default> (no escalate); a failed
    record written this run still escalates; equal status origin beats tip beats stored; a swept tree
    releases its dependents; the verdict never names /pr-merged <pr> for a recorded sub-task;
    --record-delivery in a swept tree after the merge does not refuse G-7 and writes only what is
    missing.
    re-run: --pr and --record-delivery re-runs write, close and record nothing, with or without the
    local copy.
    trees: one line per --from/--removed; missing --removed prints gone; missing --from refuses
    tree-not-found; a subfolder refuses not-a-tree-root; a tree of another repository refuses
    not-this-repository; a half-removed --removed tree prints gone-partial and the other trees are
    still swept; the main checkout is never swept (line names its kept leftovers); --sweep-records
    works without a local contract file.
    modes: the exempt modes (--record-subtask, --preconditions, --locate-parent, the dispatch packet,
    refusals) carry no keys and are never judged by I-11; unrecognized --local-evidence-only (older
    script) gives the "sync the vendored copy" halt.
    flow: a text check that skills/flow/SKILL.md Step 8 names docs/<contract-slug>-records for result
    records of single-sub-task contracts and runs --sweep-records.
    post-review (I-12 to I-14): after contract-delivery.yaml is swept, the tree still reads delivered
    from the tip or origin/<base>; --record-delivery then writes no new delivery record and no state;
    G-5 compares against the evidence delivery record; a failed delivery read -> unverifiable; a
    path-form --contract into another tree's concepts folder still carries the keys and --dispatch
    exits 12; the scope gate skips only a working directory without repository metadata; a 120000 blob
    is never proven; gh unauthenticated -> persistent; GH_REPO -> G-1 refusal; a cross-repository PR
    on the stable branch name is not counted; partial, empty or glob slug -> sweep-usage;
    --locate-parent with --sweep-records -> sweep-usage; _records_at and origin_records(fetch=False)
    return identical results on one tree (or _records_at is removed), including a 120000 .yaml, a
    nested file and contract-delivery.yaml.
    second review: a merged-and-kept stable branch whose path origin/<default> later changes is not
    stranded, does not hold the flip and does not make --dispatch exit 12; a failed merge-base
    --is-ancestor -> unverifiable; a completed record for a different PR over a completed one is
    differs (not pushed, not swept) and the reason names --discard-differing; no origin remote (get-url
    exit 2) -> gate off; any other get-url failure with a .git entry -> unverifiable; the brief-link
    gate reads evidence in a swept tree.
  - Run: test_pr_merged.py, test_cleanup_delivered.py, test_skill_script_lookup.py,
    test_plugin_text_scans.py, check_version_bump.py. Update the test counts in both SKILL.md files
    from each suite's own "Ran N tests ... OK" line. Mention the I-13 scope gate in
    skills/pr-merged/SKILL.md. Append the MECHANISMS.md registry entry named in New Mechanisms.
  - Skill text: no new lookup block; use $PRM; keep the single stable branch rule (SKILL.md Step 3,
    ~617-618); in contract-completion.md step 6 the -2/-3 suffix names the worktree folder only; add
    the PR re-open (I-4); apply the Q1-Q3 answers recorded in the approved contract.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-02-pr-merged-records-leftover-cleanup.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both backend and frontend sides
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
- [ ] `Status` flipped to `implemented`
