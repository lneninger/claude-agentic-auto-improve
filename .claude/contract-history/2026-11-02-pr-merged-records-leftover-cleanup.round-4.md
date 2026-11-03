# Superseded critique round 4 — 2026-11-02-pr-merged-records-leftover-cleanup

Moved out of `.claude/concepts/2026-11-02-pr-merged-records-leftover-cleanup.md` on 2026-11-02 by `contract-critic` (round 5), per the budget rule in `.claude/templates/concept-contract.md`. The data-architect amended the contract body (fourth amendment) in response to these findings before round 5 ran.

## Critique

**Critic:** contract-critic (round 4; rounds 1 to 3 moved to `.claude/contract-history/2026-11-02-pr-merged-records-leftover-cleanup.round-1.md`, `.round-2.md` and `.round-3.md`)
**Date:** 2026-11-02
**Verdict:** blockers-found

Round 3's three BLOCKERs are closed in the body. I-1 now uses `tree_kind` / `main_checkout_root`. An unreadable head makes the reading `unverifiable`. Merged heads are judged by `origin/<default>` only. The findings below are about the third amendment as it reads now. Option E is not raised again.

### Findings

- **[BLOCKER] I-4's fresh `-2`/`-3` cut drops the single records branch that the landing and `/flow` Step 8 depend on, and the swept copy was the only other place the record lived**
  - **What is wrong:** I-4 commits to a records head only while its pull request is open. Otherwise it cuts `docs/<slug>-records-2`, `-3` and so on. Once the first records pull request has merged and its branch still exists, every later push therefore goes to a suffixed head.
    - The landing reads records from exactly three refs: the parent branch, `origin/docs/<slug>-records` and `origin/<default>` (`land_contract.py:1995`, again at `:3089-3093`). A record on `-2` is invisible to it.
    - This includes the completion hand-off push made just before `/advance` launches the landing (`skills/pr-merged/SKILL.md:341`). The landing then halts `not-complete`.
    - Its remedy tells the operator to "commit the record to docs/<slug>-records and push it" (`land_contract.py:111`, `:2027`), and I-4 forbids exactly that.
    - Meanwhile the sweep has already deleted the starting-tree copy.
    - `/flow` Step 8 still requires "the one stable `docs/<contract-slug>-records` … never re-cut it while it exists. The landing reads records from that branch, so a second records branch for the same contract would hide records from it" (`skills/flow/SKILL.md:516`). The SKILL.md anti-pattern "Re-cutting `docs/<contract-slug>-records` while it exists on origin … Cut it from `origin/master` only when it is absent" (`skills/pr-merged/SKILL.md:617-618`) says the same.
    - Neither `skills/flow/SKILL.md` nor `land_contract.py` is in Files to touch. Extension Point 5 names lines ~597/~601, which are about failed and overwritten records, not ~617.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-01 "After merging a base that changes the row shape a feature reads, re-check every coverage claim and round-trip test against the merged writer" (Apply when: "a feature reads data another change's writer produces"); `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery, not only the one the author had in mind"; `skills/flow/SKILL.md:516`; `land_contract.py:1995`.
  - **Where in this contract:** `I-4`: "Otherwise it cuts a fresh branch from `origin/<default>` under the first free name of `docs/<slug>-records`, `-2`, `-3`, … This rule replaces the conflicting texts in `SKILL.md` Step 3"; `## Adjacent Areas` rows "Contract landing (`land_contract.py`) | not applicable" and "`/flow` Step 8 | not applicable"; `## Non-Goals`: "changing where `land_contract.py` reads records".
- **[WARN] The Records leftover state `landed` reuses the name of **Landed untracked file**, but it is judged against open, unmerged heads**
  - **What is wrong:** the registry term means a file that git would store as exactly the blob that `origin/<default>` holds. Delivery cleanup "removes nothing whose commits are not already in `origin/<default>`". The new `landed` state also matches the tip of an open records head that may never merge. Its definition says "(as for a **Landed untracked file**)", which is true only for the `origin/<default>` member of Compared refs.
  - **Prior artifact ignored:** `VOCABULARY.md` line 61 **Landed untracked file**; line 58 **Delivery cleanup**; `JOURNAL.md` 2026-10-28 "A new term's definition must be true against every existing member".
  - **Where in this contract:** `## Business Concept` → Records leftover: "`landed` — git would store it as exactly a compared blob at that path (as for a **Landed untracked file**)".
- **[WARN] I-7 says "every reader … that decides from records" reads `evidence`, but G-7 and the `--record-delivery` candidate read are not on the list**
  - **What is wrong:** two readers in `main()` still decide from `records` and are not listed:
    - G-7 `records-not-local` (`pr_merged.py:4244-4248`) refuses `--record-delivery` whenever `origin/<default>` holds a record that `records` lacks.
    - The `--record-delivery` route also calls `delivery_candidates([cand], tasks, records)` (`pr_merged.py:4250`), and that call is not on the list either.

    After the sweep, a starting tree whose records pull request has merged lacks every swept record. `--record-delivery` there therefore always refuses G-7, and the contract neither names this nor says whether G-7 moves to `evidence`. If G-7 did move to `evidence`, it could never fire.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "One shared reader must own the filtering, not only the selection"; 2026-10-30 "A delivery rule must name every route into delivery".
  - **Where in this contract:** `I-7`: "Every reader in `main()` that decides from records reads `evidence`: both `advance()` calls, `delivery_candidates` (~4483), … `reconcile_state` (~4491), `evaluate_completion` and the layout block (~4731)".
- **[WARN] A records pull request closed without merging, after the sweep, leaves the record nowhere the loop counts, and no way out is named**
  - **What is wrong:** the sweep deletes the copy as soon as an open head holds it. If a person then closes that pull request unmerged, or deletes the head (which closes it), Compared refs drop the head ("closed-unmerged … never counts"). `evidence` then lacks the record, and `compute_released` treats a sub-task with no record as open work (`pr_merged.py:604-606`). The Failure Modes and I-7 do not trace this route. Nothing in the script holds it, and no Next Command names how to restore the record (for example by re-recording with `/pr-merged <pr>`). Only the prose backstop at `skills/advance/SKILL.md:113` stands between this and a re-dispatch.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A rule that refuses must give already-delivered work a named way out"; 2026-10-30 "A delivery rule must name every route into delivery".
  - **Where in this contract:** **Compared refs**: "A head that is closed-unmerged, or has no pull request, never counts"; `## Failure Modes`, first FM: "a swept tree re-dispatches finished work" (mitigated only for failed reads).
- **[WARN] A permanent read failure holds the whole loop behind a "run again" remedy that can never clear it**
  - **What is wrong:** `origin_records` returns none when any record blob on the ref fails to parse or is not a mapping (`pr_merged.py:2885-2893`). Its only caller today is a warning (`pr_merged.py:4727`). Under I-3 and I-7, that same none now does all of the following:
    - empties `released` and builds no dispatch packets;
    - makes the Completion Verdict `unverifiable`;
    - refuses every writing run with exit 10 and every `--dispatch` with exit 12.

    This holds for every run of the contract, including a tree with no leftovers at all. The only remedy given is "run the same command again when git and GitHub answer". That cannot clear a malformed record on `origin/<default>` or on an open head, a missing `gh`, or an offline clone (`ls-remote` always runs).
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-01 "A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for"; 2026-10-30 "A rule that refuses must give already-delivered work a named way out".
  - **Where in this contract:** `I-3`: "Any failure sets `records_reading: unverifiable` … and I-7 holds the loop"; `I-5`: "`reason: \"records could not be read (<cause>); run the same command again when git and GitHub answer\"`".
- **[WARN] I-1 accepts any existing folder inside a worktree, not only the worktree root, so a `--from` subfolder can print `clean` over real leftovers**
  - **What is wrong:** `tree_kind` and `main_checkout_root` walk up from the nearest existing ancestor (`MECHANISMS.md` line 43), so a subfolder of a worktree passes the same-repository check. But the listing is `git -C <tree> status … -- <folder>`, and that pathspec is resolved relative to `<tree>`. From a subfolder it matches nothing, and the Tree-clean line reads `clean`. The script already records this exact trap for `ls-tree` (`pr_merged.py:2874-2875`: "a path relative to a subfolder matches nothing and would read as 'no records'").
  - **Prior artifact ignored:** `MECHANISMS.md` line 43 (Tree classification reads from the nearest existing ancestor); `JOURNAL.md` 2026-11-01 "A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for".
  - **Where in this contract:** `I-1` "Same repository" and "Which files"; `I-10`.
- **[WARN] "Every `--json` report carries the keys" is not defined for the script's early-return JSON outputs, yet I-11 reads a missing key as "older script"**
  - **What is wrong:** several modes print their own JSON and return before line ~4748, where I-5 and I-7 apply:
    - `--record-subtask` (`pr_merged.py:4031-4035`);
    - `--preconditions` (`pr_merged.py:4674-4704`);
    - the `--dispatch` packet (`pr_merged.py:4661`);
    - every JSON refusal.

    `/advance`'s dispatch path decides from `--preconditions` (`skills/advance/SKILL.md:156`). That reading gets neither the I-7 hold nor the I-5 prefix. If it lacks `records_reading`, I-11 halts with a false "predates 0.13.0" message.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-28 "A new term's definition must be true against every existing member"; 2026-10-04 "Detect an install mode by what the sync actually delivers".
  - **Where in this contract:** `### Value Objects` → Records report keys: "present in every `--json` report"; `I-11`: "the report has no `records_reading` key"; `## Extension Points` 2.
- **[NIT] The cost statement is too low** — `origin/<default>` is always a Compared ref, so every run also fetches it. Today a single-block `--status` fetches nothing: `_origin()` is called only at `pr_merged.py:4237` and `:4727`. Also, `origin_records` fetches each head again after I-3's `fetch_default_branch` already did (`JOURNAL.md` 2026-10-28 "State the real trigger of a hook, not the printing condition").
- **[NIT] Two exit codes for `--dispatch` on an unreadable reading** — I-8's "a writing run (not `--dry-run`, not `--status`) … exits 10" also covers `--dispatch`, which I-9 gives exit 12. Meanwhile `skills/advance/SKILL.md:210` says "`--dispatch` never exits 10".
- **[NIT] `next_move` gains `held: records-unverifiable`** — this key is not among the Value Objects, and the TASK block says "no extra keys".
- **[NIT] `--sweep-records` needs "no local contract", but `main()` refuses `contract-not-found` first** — that refusal is at `pr_merged.py:3961-3964`, and no Extension Point moves the sweep ahead of it.
- **[NIT] Two readers answer "is a records pull request open"** — Compared refs use the per-head `gh pr list --head`. The flip's check (`pr_merged.py:3805`) and G-6 (`:4283`) still use `open_records_pull_requests` (`:2823`), so the two can disagree.
- **[NIT] Suffixed heads are outside the Owned set** — `VOCABULARY.md` line 59 names only `docs/<slug>-records`, so Delivery cleanup never removes `-2`/`-3`. Separately, the `ls-remote` prefix also matches another contract whose slug begins `<slug>-records`, and an unreadable head there would make this contract `unverifiable`.
- **[NIT] The body is about 13,000 tokens against a 12,000 budget** — the header note discloses the overrun, but it does not bring the body within budget (`.claude/templates/concept-contract.md` line 22).

### Applicable journal entries

- **2026-10-17 — Judge "identical to master" by git's view** — heeded by `I-2` (`hash-object`, filters on).
- **2026-10-17 — Git for Windows lists files beneath an untracked junction** — heeded by `I-2` (`_plain_file_inside` immediately before each delete).
- **2026-10-15 — A cleanup wired before its trigger never runs** — heeded: the sweep runs on every call and can be repeated safely.
- **2026-10-16 — An unset ownership field is not proof of ownership** — heeded by `I-1` (only this contract's results folder).
- **2026-10-16 — A skill step that moves the shell** — heeded by `--from` / `--removed` with `git -C`.
- **2026-10-15 — A skill that edits a lookup block must name the test** — heeded by the TASK run list.
- **2026-10-28 — Do not promote an extension seam** — heeded: `I-1` now reuses `tree_kind` / `main_checkout_root`, and New Mechanisms is None.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by `records_reading` plus `records_untracked`, and by `tree-not-found` versus `gone`.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded for I-9 (exits 2–7, and 12 is free). The I-8/I-9 overlap is a NIT.
- **2026-10-04 — Detect an install mode by what the sync actually delivers** — partly heeded by I-11; violated for the early-return outputs, see WARN.
- **2026-10-30 — A failed record written by a new rule must not feed an older guard** — heeded in both directions (I-6 rules 1 and 2).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body** — heeded: the Q1–Q3 effects are named in Extension Point 5.
- **2026-10-30 — One shared reader must own the filtering** — violated: G-7 and the `--record-delivery` candidate read are missing from I-7, see WARN.
- **2026-10-30 — A delivery rule must name every route** — violated: the landing, `/flow` Step 8 and closed-unmerged heads, see BLOCKER and WARN.
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — violated: persistent `unverifiable` and closed-unmerged heads, see WARNs.
- **2026-11-01 — A shared reader reused by a stricter consumer** — heeded for the I-3 reader choice; violated for `origin_records`' parse failure and for `tree_kind`'s ancestor walk, see WARNs.
- **2026-11-01 — After merging a base that changes the row shape a feature reads** — violated: the landing and `/flow` Step 8 still read only the unsuffixed branch, see BLOCKER.
- **2026-10-28 — A new term's definition must be true against every existing member** — violated by `landed` and by "every `--json` report", see WARNs.
- **2026-10-28 — State the real trigger of a hook, not the printing condition** — cost statement, see NIT.
- **2026-10-15 — Locate a script from the plugin root** — not addressed: the contract adds no new script lookup, and the skills keep `$PRM`.

### What the critic did not check

- No CodeGraph tool was available to this critic, so code claims were checked with Grep and Read on `pr_merged.py`, `cleanup_delivered.py`, `land_contract.py`, `_claude_paths.py` and the three skill files.
- Checklist item 14 (`pr_merged.py --status --json`) was not run, because this critic has no shell. By reading: the contract has one mergeable block, carries the brief header, and that block raises the version.
- `.claude/registries/INTEGRATION.md`, `.claude/north-stars/` and `.claude/.scout-cache/registry-digest.md` do not exist. Items 7, 12 and 13 produce no findings.
- The token count is estimated, not measured. The lazy `cleanup_delivered` import (ASSUMED) and git's porcelain path form from a subfolder were not tried.
