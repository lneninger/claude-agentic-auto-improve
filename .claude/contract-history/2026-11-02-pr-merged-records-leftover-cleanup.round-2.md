# Superseded critique round 2 — 2026-11-02-pr-merged-records-leftover-cleanup

Moved out of `.claude/concepts/2026-11-02-pr-merged-records-leftover-cleanup.md` on 2026-11-02 by `contract-critic` (round 3), per the budget rule in `.claude/templates/concept-contract.md`. The data-architect amended the contract body in response to these findings before round 3 ran.

## Critique

**Critic:** contract-critic (round 2; round 1 moved to `.claude/contract-history/2026-11-02-pr-merged-records-leftover-cleanup.round-1.md`)
**Date:** 2026-11-02
**Verdict:** blockers-found

### Findings

- **[BLOCKER] The reused readers cannot report a failed read, so I-3 cannot be enforced and a real `differs` reads as `unpushed`**
  - **What is wrong:** `_tree_names_at` returns `[]` "when git cannot list it" (`pr_merged.py:2589-2596`), and `load_records_at` drops unreadable records without a sign (`pr_merged.py:2599-2617`). A failed `ls-tree` therefore reads as "no ref holds the path". That is `unpushed`, not `unverifiable`. The records step then pushes the file over a completed record on the branch, which I-4 forbids. `origin_records` (`pr_merged.py:2861-2895`) already tells `None` apart from `{}`, but the contract does not use it.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-01 "A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for"
  - **Where in this contract:** `## Reused Mechanisms`: "`_tree_names_at` ... consumed as-is to tell `differs` ... from `unpushed`" and "`origin_records` / `load_records_at` ... consumed as-is"; `I-3`.
- **[BLOCKER] In a swept tree, the Completion Verdict's remedy leads back to the same verdict**
  - **What is wrong:** I-13 keeps `evaluate_completion` on `records`, and `records` holds only the local files (`pr_merged.py:3972`, `4788-4792`). The flip's condition one (`pr_merged.py:3651`) then reads "<id> has no completion record — record its merged pull request with /pr-merged <pr>" for every swept sub-task. Running that command hits I-9, which skips the write and leaves "`records[task.id]` ... exactly as loaded", so the same verdict comes back. At the same time, `advance()` reads `evidence` and reports `complete`. So until the records pull request merges, a declined or deferred flip cannot be finished from that tree.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A rule that refuses must give already-delivered work a named way out"; `pr_merged.py:3152` `is_delivered` docstring: "the move and the verdict never read the same fact two ways"
  - **Where in this contract:** `I-13`: "keep their record inputs exactly as today"; `I-9`; `## Failure Modes` covers only "records-branch evidence flips a contract", not the reverse.
- **[BLOCKER] A re-delivery after a failed record that has already merged escalates once its copy is swept**
  - **What is wrong:** take a `failed` record that reached `origin/<default>` and a re-delivered `completed` record that I-4's `update` pushed to a records head. The sweep then deletes the local copy as `landed`. On the next run, `records` and `stored` are both empty, so `merge_evidence` takes origin's `failed` record. I-8's "`origin/<default>` wins over every records-branch head" outranks the head's `completed` record, and `advance()` returns `escalate` on any failed record (`pr_merged.py:1793-1796`). The `update` exception claims "the old failed record never blocks the re-delivery", but here it does, until a person merges the records pull request.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A failed record written by a new rule must not be the input of an older guard that blocks the rule's own exit"
  - **Where in this contract:** `I-8` (the third bullet) vs `I-4` Exception and `I-9`; the `## Lessons referenced` entry claiming that lesson is heeded.
- **[WARN] A missing `--from` both refuses (I-1) and prints `gone` (I-12)**
  - **What is wrong:** I-1 refuses a `--from` that fails the `rev-parse --git-common-dir` check, with "exit 2, and nothing is swept". A removed folder fails that check. Extension Point 7 always passes the removed records worktree, so if I-1 is checked first, the starting tree is never swept.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case"
  - **Where in this contract:** `I-1`; `I-12`: "A `--from` path that no longer exists prints `tree <path>: gone`"; `## Extension Points` 7.
- **[WARN] An older vendored script has no `records_unpushed` key, and the skills read that as empty**
  - **What is wrong:** the skills find a vendored copy first (`skills/pr-merged/SKILL.md:51`). With an older copy, the records step finds "nothing to push" and `/advance` dispatches, so records are never pushed where today they are. The failure mode covers only the case where `--sweep-records` is rejected.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "Detect an install mode by what the sync actually delivers"; 2026-10-22 "Describe a broken install by the rows each install age really has"
  - **Where in this contract:** `## Extension Points` 7: "Its input is the Records Unpushed set read by `--status --json`"; the last failure mode.
- **[WARN] A copy found only on an unmerged records head is deleted as `landed`**
  - **What is wrong:** the definition of `landed` accepts any Compared ref, including a head whose records pull request was closed without merging. After the delete, the record sits only on that branch. Q3 decides evidence only; under its recommendation (a), the deletion rule is unconditional.
  - **Prior artifact ignored:** `VOCABULARY.md` **Landed untracked file** (judged against `origin/<default>`); `VOCABULARY.md` **Delivery cleanup**: "removes nothing whose commits are not already in `origin/<default>`"
  - **Where in this contract:** **Records leftover**, item 1; `Q3`.
- **[WARN] If the comparison is `unverifiable`, the records step pushes copies that may differ**
  - **What is wrong:** I-6 counts "every non-`unsafe` leftover as unpushed" when the comparison is `unverifiable`, and the records step pushes that set. A copy that really differs then lands on top of origin's record, which breaks I-4's "The loop never pushes over a completed record". Delivery cleanup does nothing at all when a read is unverifiable.
  - **Prior artifact ignored:** `MECHANISMS.md` line 75: "a failed `ls-tree`/`hash-object` reads `unverifiable`" and keeps the tree
  - **Where in this contract:** `I-6` vs `I-4`; `### Commands` row "Run the records step".
- **[WARN] I-14 cites a refusal helper and exit code that do not exist**
  - **What is wrong:** `--dispatch` prints each refusal inline, with exit codes 2, 3, 5 and 7 (`pr_merged.py:4517-4585`). There is no shared helper, so the suite has no exit code to pin. I-14 also does not say whether the refusal comes before or after `advance()`, or whether it applies under `--dry-run`.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "Check a documented guard behaviour against the guard's code"
  - **Where in this contract:** `I-14`: "through the same refusal helper and exit code as its other refusals".
- **[WARN] `update` replaces a failed record, but the skill text that forbids this is not amended**
  - **What is wrong:** `skills/pr-merged/SKILL.md` line 323 ("append-only ... Show both and ask") and the anti-patterns at lines 597 and 601 ("Deleting a failure record ...", "Overwriting an existing completion record silently") still stand. Extension Point 7 does not list them.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22 "An accepted critic WARN or answered Open Question must amend the contract body before approval"
  - **Where in this contract:** `I-4` Exception; `## Extension Points` 7.
- **[WARN] The other readers in `main()` still read the swept `records`**
  - **What is wrong:** `delivery_candidates(raw_candidates, tasks, records)` (`pr_merged.py:4483`) feeds `candidate_kind`, and on empty records that returns `single-branch` (`pr_merged.py:3099-3101`). So an `early` candidate turns into a blocking `delivery-unrecorded` move in a swept tree. `is_delivered(tasks, records, ...)` at line 4505 also diverges.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "One shared reader must own the filtering, not only the selection"
  - **Where in this contract:** `## Extension Points` 4: "pass it to `advance()` ... in place of `records`".
- **[WARN] The Tree-clean line does not reach every tree `/advance` touches**
  - **What is wrong:** the term says "the skills pass every tree they touched". Extension Point 9 passes only "the tree it stands in, and any records worktree it created", not the flat worktree `--dispatch` creates.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-28 "A new term's definition must be true against every existing member"; brief acceptance criterion 6
  - **Where in this contract:** **Tree-clean line**; `## Extension Points` 9.
- **[NIT] Any argparse error is read as "sync the vendored copy"** — a missing `--contract` also exits 2 with no JSON on stdout, and the skills key only on the missing JSON `error`.
- **[NIT] I-1's "the script's own" common directory is undefined under a plugin install** — the script sits outside the repository, and `--git-common-dir` prints a relative `.git` in the main checkout but an absolute path in a worktree.
- **[NIT] `skills/pr-merged/SKILL.md:77-82` also says "530 cases / Ran 530 tests"** — Extension Point 7 does not update it; only Extension Point 9 updates the copy in `advance`.
- **[NIT] I-9 does not say what happens when the Compared refs are unreadable** — the guard turns off without a sign, and the record is rewritten.
- **[NIT] Leftover Entry's `ref_blob` needs a read the contract does not name** — `compare_untracked` returns `blobs` only for identical files (`cleanup_delivered.py:496-499`).
- **[NIT] Chat Tool Impact reads "2. **No.**"** — not the sanctioned wording `No — UI/admin-only with justification`. No REST, SignalR or DTO surface changes, so item 7 does not fire.

### Applicable journal entries

- **2026-10-17 — Judge "identical" by git's view** — heeded by `I-2`.
- **2026-10-17 — Untracked junction; the parent-link check is load-bearing** — heeded by `I-2`.
- **2026-10-15 — A cleanup wired before its trigger never runs** — heeded by the sweep, which can be repeated safely and runs on every call.
- **2026-10-16 — An unset ownership field is not proof of ownership** — heeded by `I-1`.
- **2026-10-16 — A skill step that moves the shell** — heeded by `--from` / `git -C` (`I-1`, `I-11`).
- **2026-10-15 — Locate a script from the plugin root** / **lookup-block test** — heeded by `$PRM` and the TASK run list.
- **2026-10-28 — Do not promote an extension seam** — heeded by `## New Mechanisms`: None.
- **2026-10-22 — Amend the body before approval** — heeded for Q1–Q3; violated for the `update` skill text, see WARN.
- **2026-10-30 — A delivery rule must name every route** — heeded by `I-6` (git-derived input); the older-vendored-script route is open, see WARN.
- **2026-10-30 — One shared reader must own the filtering** — heeded by `merge_evidence` + `branch_heads`; violated by the other readers in `main()`, see WARN.
- **2026-10-30 — A rule that refuses must give a named way out** — heeded for `differs` (`--discard-differing`); violated by the flip remedy loop, see BLOCKER 2.
- **2026-10-30 — A failed record must not feed an older guard** — violated, see BLOCKER 3.
- **2026-11-01 — A shared reader reused by a stricter consumer** — violated, see BLOCKER 1.
- **2026-10-28 — A new term's definition must be true against every existing member** — violated by the Tree-clean line, see WARN.

### What the critic did not check

- Checklist item 14: `pr_merged.py --contract <slug> --status --json` was not run, at the caller's instruction (no contract-slug state exists yet). The contract has a single block and carries the `**Work Item Brief:**` header, and the version raise sits in that block.
- `.claude/registries/INTEGRATION.md` and `.claude/north-stars/` do not exist, so item 7 was judged from `## Integration Surfaces` and item 13 produces no findings.
- `.claude/.scout-cache/registry-digest.md` was not read; the three registries were read directly. CodeGraph tools were not available in this session, so the code claims were checked with Grep and Read.
- The cost of `ls-remote` plus a fetch per records head on every `--status` was not measured.
