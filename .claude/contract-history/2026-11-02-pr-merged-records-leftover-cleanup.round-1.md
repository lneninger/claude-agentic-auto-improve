# Superseded critique round 1 — 2026-11-02-pr-merged-records-leftover-cleanup

Moved out of `.claude/concepts/2026-11-02-pr-merged-records-leftover-cleanup.md` on 2026-11-02 by `contract-critic` (round 2), per the budget rule in `.claude/templates/concept-contract.md`. The data-architect amended the contract body in response to these findings before round 2 ran.

## Critique

**Critic:** contract-critic
**Date:** 2026-11-02
**Verdict:** blockers-found

### Findings

- **[BLOCKER] I-8 adds a second evidence-merge rule whose precedence is the reverse of the existing one**
  - **What is wrong:** I-8 says "A local record always wins" over origin, while `merge_evidence` (`pr_merged.py:2898`, docstring "Origin's records win over the stored local ones; only a record written by THIS run overrides origin's") uses the opposite rule on the same records in the same `main()`. Extension Point 4 also keeps `stored_records` unchanged, so at `pr_merged.py:4731` an id filled from a records branch differs from `stored` and is treated as written by this run, which overrides `origin/<default>` in the layout warnings.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "One shared reader must own the filtering, not only the selection"; `pr_merged.py:2898` `merge_evidence`.
  - **Where in this contract:** `## Reused Mechanisms`: "I-8's rule (local wins, origin fills the gaps) is a sibling union, not a change to it"; `## Data Shapes → I-8`.
- **[BLOCKER] A `differs` leftover leaves the loop with no exit**
  - **What is wrong:** `differs` counts as Records Pending (I-6), so `/advance` "Never dispatch[es] while it is non-empty" (Ext. Point 8). The records step "halts on a `differs` entry" (Commands), and I-7 puts `/pr-merged --records` first in the Next Command again on every later run. No owner command clears the state, so the loop suggests the same halting command forever.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A rule that refuses must give already-delivered work a named way out" ("make the loop's next command name it, so the refused command is never suggested twice").
  - **Where in this contract:** `## Data Shapes → I-4, I-6, I-7`; `### Commands` row "Run the records step"; `## Extension Points` 8.
- **[BLOCKER] I-9's re-delivery after a failed record runs straight into the `differs` halt**
  - **What is wrong:** I-9 says "A failed record ... is re-recorded exactly as today, so a re-delivery after a failed record still works". The new local `completed` record then differs from origin's `failed` blob at the same path. That makes it `differs` (I-4: "the loop never pushes over it"), so it stays pending, and the records step halts on it. The old failed record becomes the input that blocks this rule's own exit.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A failed record written by a new rule must not be the input of an older guard that blocks the rule's own exit".
  - **Where in this contract:** `## Data Shapes → I-9` vs `I-4`; `## Lessons referenced` claims 2026-10-30 "named way out" is heeded by I-9.
- **[BLOCKER] The standalone records step (`/pr-merged --records <slug>`) has no defined input**
  - **What is wrong:** the records step "still copies exactly that union" of `written_files` (`## Reused Mechanisms`; `contract-completion.md` steps 5 and 7: "the union of `written_files` from every writing run in the session"). The new route, though, runs it in a later session or from `/advance` Step 1, where no writing run happened and `written_files` is empty. The contract does not say what that route pushes.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery, not only the one the author had in mind"; brief implementer note "the pending check must read git facts, not session memory".
  - **Where in this contract:** `## Reused Mechanisms`: "`written_files` ... the records step still copies exactly that union"; `### Commands`: "`/pr-merged --records <slug>` (skill) | the slug".
- **[WARN] I-8 widens completion evidence beyond the brief and was not raised as an Open Question**
  - **What is wrong:** with I-8, a record on any `origin/docs/<slug>-records*` head now releases dependents and feeds the Completion Verdict, even when that head belongs to an unmerged or closed-unmerged records pull request. That changes what counts as evidence for a completion, and the change is decided in prose instead of being put to the user.
  - **Prior artifact ignored:** brief `## Out of scope` and acceptance criteria (no criterion asks for it); `VOCABULARY.md` **Delivery cleanup** ("every sub-task has a GitHub-verified completion record there", meaning at `origin/<default>`).
  - **Where in this contract:** `## Business Concept`: "Invariants I-8 and I-9 close that"; `## Data Shapes → I-8`.
- **[WARN] I-8 names `is_delivered`, which Delivery cleanup shares**
  - **What is wrong:** I-8 says "When `advance()`, `compute_released` and `is_delivered` read records". `cleanup_delivered.py:270` calls `pr_merged.is_delivered`, and its gate must read records only at `origin/<default>`. Only Extension Point 4 (`main()`) narrows the change. The Adjacent Areas row for Delivery cleanup says it is unchanged without naming this shared function.
  - **Prior artifact ignored:** `MECHANISMS.md` line 75 (Delivery cleanup reads records AT `origin/<default>`); `JOURNAL.md` 2026-11-01 "A shared reader reused by a stricter consumer must be re-checked".
  - **Where in this contract:** `## Data Shapes → I-8`; `## Adjacent Areas` row "Delivery cleanup".
- **[WARN] I-8 says "the records branch" (singular), but the Compared refs are several heads**
  - **What is wrong:** the Compared refs include the `-2` and `-3` heads. I-8 has no rule for which head wins when two records branches hold different records for one sub-task.
  - **Prior artifact ignored:** `contract-completion.md` step 6 (the suffixes `-2` and `-3`); `VOCABULARY.md` **Records pull request**.
  - **Where in this contract:** `## Data Shapes → I-8`: "`origin/<default>` first, then the records branch".
- **[WARN] `--sweep-records` sweeps "the tree it stands in" but takes no starting-tree argument**
  - **What is wrong:** the sweep runs after step 6 and step 7 (creating, committing in and pushing from the records worktree), then after the worktree is removed. The contract does not say the shell is back in the starting tree. Delivery cleanup takes `--from <start>` for exactly this reason.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-16 "A skill step that moves the shell must come after every later step that reads the working tree"; `MECHANISMS.md` line 75 (`--from <start>`).
  - **Where in this contract:** `### Commands`: "No local contract file is needed"; `## Extension Points` 7.
- **[WARN] The acceptance criterion "a tree-clean line per tree touched" is mapped to one tree only**
  - **What is wrong:** the brief asks for a line per tree touched, and the vocabulary term says "one line per tree a run touched". I-1 and I-12 make `--sweep-records` judge and print only its own tree. The trees `/advance` touches when dispatching are not covered, and no test is named for this criterion.
  - **Prior artifact ignored:** brief acceptance criterion 6; `JOURNAL.md` 2026-10-28 "A new term's definition must be true against every existing member".
  - **Where in this contract:** `## Business Concept` → **Tree-clean line**; `## Data Shapes → I-1, I-12`.
- **[WARN] Failure mode 2's mitigation does not cover a re-run while the local copy is present**
  - **What is wrong:** I-9 applies only when the local record is absent ("A local record present → today's behaviour", an unconditional rewrite at `pr_merged.py:4443`). A re-run before the sweep, for example after an exit-2 "sweep unavailable", rewrites a record that then reads `differs` forever. That is the exact failure the failure mode names.
  - **Prior artifact ignored:** brief acceptance criterion 8 ("does not duplicate or delete a record").
  - **Where in this contract:** `## Failure Modes & Mitigations`: "I-9 skips the write when the same completed pull request is already recorded on origin".
- **[NIT] I-9 sits "before `write_record`", after the re-run has already closed the sub-issue and written the state entry** — `close_sub_issue` runs at `pr_merged.py:4431` and `record_merge_in_state` at line 4451. The contract does not say what `records[task.id]` holds when the write is skipped.
- **[NIT] Exit 2 means two things** — the skills read exit 2 as "sweep unavailable: sync the vendored copy", while the same exit 2 is the usage refusal for flag combinations (`### Commands`).
- **[NIT] "Records pending" reuses the word `pending`** — `pending` is already a **Completion Verdict** value with a different meaning (`VOCABULARY.md` line 50).
- **[NIT] The proposed VOCABULARY.md appends need this pull request's version raise** — CLAUDE.md line 20 counts the registries as shipped files, and `.claude/registries/VOCABULARY.md` is not in `Files to touch`.
- **[NIT] Two passages are out of date** — `## Adjacent Areas` says the scanner "was NOT run", and the third `ASSUMED` entry is still open. The caller ran the scan, and it found no adjacent area above the threshold.
- **[NIT] `/advance` acceptance criterion 5 has no test** — the TASK block's test list has no case for "does not dispatch on top of pending records". Only the skill text covers it.

### Applicable journal entries

- **2026-10-17 — Judge "identical to master" by git's view** — heeded by I-2.
- **2026-10-17 — Git for Windows lists files beneath an untracked junction** — heeded by I-2.
- **2026-10-15 — A cleanup wired to run before its own trigger event has fired never runs** — heeded by the idempotent sweep on every call.
- **2026-10-16 — An unset ownership field is not proof of ownership** — heeded by I-1.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by the TASK run list.
- **2026-10-15 — Locate a script from the plugin root** — heeded by "call the already-resolved $PRM".
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded by `## New Mechanisms`: None.
- **2026-11-01 — A shared reader reused by a stricter consumer** — heeded for `compare_untracked` (`_tree_names_at` splits `differs` from `unpushed`), not addressed for `is_delivered` (see WARN).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the body** — heeded: Q1 and Q2 name the body text they change.
- **2026-10-30 — One shared reader must own the filtering** — violated, see BLOCKER 1.
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — violated, see BLOCKER 2.
- **2026-10-30 — A failed record ... must not be the input of an older guard** — violated, see BLOCKER 3.
- **2026-10-30 — A delivery rule must name every route into delivery** — violated, see BLOCKER 4.
- **2026-10-16 — A skill step that moves the shell** — not addressed, see WARN.
- **2026-10-28 — A new term's definition must be true against every existing member** — not addressed, see the Tree-clean line WARN.

### What the critic did not check

- Checklist item 14: `pr_merged.py --contract <slug> --status --json` was not run (no shell). This is a single block, the `**Work Item Brief:**` header is present, and the version raise belongs to that block, so no layout defect follows from the text.
- `.claude/registries/INTEGRATION.md` does not exist in this repository, so item 7 was judged from `## Integration Surfaces` alone.
- `.claude/north-stars/` does not exist, so item 13 produces no findings.
- The version files were checked against CLAUDE.md lines 7–12 and the `check_version_bump.py` `MANIFESTS`: four files, five places, currently 0.12.4. They match. The minor raise to 0.13.0 matches "a minor bump for a new capability".
