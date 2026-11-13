# Critique round 1 of 2026-11-13-audit-followups-165-chores (superseded)

Moved out of the contract by the budget rule. Round 1 found 1 BLOCKER, 5 WARN, 3 NIT. The owner (2026-11-13) answered Q1 (keep real counts) and asked for a revision addressing the BLOCKER and all WARNs; the data-architect's revision addressed each, and the second pass (kept in the contract) re-judged them.

**Critic:** contract-critic
**Date:** 2026-11-13
**Verdict:** blockers-found

### Findings

- **[BLOCKER] I-5 sends the reviewer to two profile slots that do not carry the fact it needs**
  - **What is wrong:** `implementers` is "the agents that may own a contract sub-task, or `none` to accept the plugin's own" (`.claude/project-profile.md:35`), and `review.documents` is "the primary documents a reviewer must read" (`:34`; its only amendment lets add-ons append their documents, `VOCABULARY.md:89`). Neither slot says which agent is the model-training one or where training examples live, so the shipped reviewer text would read a fact out of slots that do not hold it. Option E's rejection depends on the claim that they "cover this one".
  - **Prior artifact ignored:** `MECHANISMS.md:69` (Project profile): "an agent needing a fact no slot covers is a defect in the template, and the fix is to add the slot to the template in the plugin, in the same change".
  - **Where in this contract:** `## Data Shapes → Invariants` I-5: "named in the `implementers` slot of `.claude/project-profile.md`" / "where its `review.documents` place them"; `## Alternatives Considered` Option E: "`implementers` and `review.documents` cover this one".
- **[WARN] As defined, rule 8 fires on the sanctioned answer that I-3 must keep word for word**
  - **What is wrong:** rule 8 counts "a path of one or more `/`-separated segments ending in `/`" as a folder path, and `UI/` in `UI/admin-only` is exactly that. I-3 requires critic item 7 to keep `No — UI/admin-only with justification` word for word, and I-4 requires the same passage to pass rule 8. The contract declares `UI/admin-only` a must-not-fire fixture but gives no boundary rule that would make it pass, so I-3 and I-4 contradict each other unless the implementer adds an undeclared exception.
  - **Prior artifact ignored:** `.claude/scripts/tests/test_plugin_text_scans.py:673` (rule 5 handles the same text with a word-character lookbehind) and `:739` (its must-not-fire control); `JOURNAL.md` 2026-10-05 "Never hide a forbidden name by hashing it when the test needs a positive control" (controls must reflect the real rule).
  - **Where in this contract:** `## Data Shapes` "**Rule 8 (new):** ... a path of one or more `/`-separated segments ending in `/` ... `UI/admin-only` ... do not fire."
- **[WARN] Confidence is High, but three Uncertain Assumptions are ASSUMED**
  - **What is wrong:** the verdict leaves out the three ASSUMED entries: `master` still at `0.20.1`, the hook oracle still 14, and `cross_area_scan.py` printing nothing (not run).
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md:246-252` (Confidence must be an honest breakdown of strong and weak areas).
  - **Where in this contract:** `## Confidence` "Confidence: High. Every claim re-read at the cited lines"; `## Uncertain Assumptions` three `ASSUMED` bullets.
- **[WARN] The new `<plan path>` definition misstates the folder name the helper produces**
  - **What is wrong:** the line-442 rewrite says the last segment of the plan's path "is the `<YYYYMMDD>-<action>-<slug>` folder". The helper cuts that name at a hyphen to at most 60 characters and gives a taken name a `-2` to `-9` suffix. That makes F5's "one path, one name" fix wrong in a new way.
  - **Prior artifact ignored:** `MECHANISMS.md:82` (Flat worktree helper: "cut at a hyphen to at most 60 characters, and gives a taken name `-2` to `-9`"); `VOCABULARY.md:61` (Flat worktree: "at most 60 characters").
  - **Where in this contract:** `## Implementation Handoff` TASK (3): "whose last segment is the <YYYYMMDD>-<action>-<slug> folder (I-6)".
- **[WARN] In-flight parent branches get no named way out of the new red pin**
  - **What is wrong:** the Failure Modes cover a *later* multi-sub-task contract. They do not cover a parent branch already in flight whose merged sub-tasks added a skill or agent. When that branch takes `master` in through a sub-task (as JOURNAL 2026-11-07 requires), the new pin turns that sub-task red, and the contract's own Q1 says no route can correct a manifest. The contract also does not check whether any open parent branch is in this state today.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A rule that refuses must give already-delivered work a named way out"; `JOURNAL.md` 2026-11-07 "A parent branch that shares files with a moving default branch must take the default branch in through a sub-task before its landing".
  - **Where in this contract:** `## Failure Modes & Mitigations` "**FM:** a later multi-sub-task contract adds a skill or agent".
- **[WARN] The claimed heed of "Keep a review-fix block to the review's findings" does not match the lesson**
  - **What is wrong:** the lesson is to put text for a new requirement in its own block, so each block's review judges one thing. Block 1 puts the F5/F6 review fixes together with two non-review requirements (manifest counts, agent text). Option A argues the trade-off against the Parent Branch Delivery Rule, but the Lessons line reports compliance instead of an acknowledged departure.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 "Keep a review-fix block to the review's findings".
  - **Where in this contract:** `## Lessons referenced` "heeded by limiting F5 and F6 to what the review found"; `## Implementation Handoff` "### 1. Manifest counts, agent chat-tool text and review nits".
- **[NIT] The Adjacent Areas line reports a scan result for a scan that did not run** — "cross-area scan returned no signal ... the script was not run" puts a claimed result next to an admission that the script never ran. The empty `areas: {}` in `.claude/area-mapping.json` makes the outcome the same, but the wording is not the sanctioned single line (checklist 11.f).
- **[NIT] The F5 pin is worded for command arguments only** — "Step 5c's text holds no `.claude/worktrees/<wt>` command argument", but line 475 is prose that I-6 also covers (`JOURNAL.md` 2026-11-02 "A rule titled 'every' must list every line it covers": a test pins each line).
- **[NIT] New value-object names, but "New terms: none"** — "Count claim", "Genericity passage" and "Text pin" are named as reused or new shapes, yet none of them appears in `VOCABULARY.md`.

### Applicable journal entries

- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded by rule 8's made-up controls (but see the rule-8 WARN above).
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by the Run list (`test_skill_script_lookup.py`).
- **2026-10-30 — A delivery rule must name every route into delivery, not only the one the author had in mind** — heeded by Option A and by the follow-up stub.
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — not addressed, see the in-flight parent branch WARN above.
- **2026-11-02 — A rule titled 'every' must list every line it covers** — heeded by I-1 and the I-6 line list; the pin is partial (NIT above).
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them** — heeded by I-7 and I-8.
- **2026-11-02 — Keep a review-fix block to the review's findings** — claimed heed contradicted, see the WARN above.
- **2026-11-02 — A "fails the build" claim must name the workflow that runs the check** — heeded by the first Failure Mode (`version-bump.yml`, `tests` job).
- **2026-11-07 — A merge block's pull request must paste each required output, not tick a line that says it passed** — heeded by the TASK block's "Paste its failing run ... then the passing run" and the "Ran N tests" before and after.

### What the critic did not check

- `.claude/registries/INTEGRATION.md` is absent from this tree; checklist item 7 was judged on the contract alone (no endpoint, event or DTO).
- `pr_merged.py --contract ... --status --json` and `derive_area.py` were not run (no shell). Item 14 was judged from V9 and the single-block layout; item 11 from the empty `areas` map.
- `.claude/north-stars/` is absent, so item 13 produces no findings.
- The V1, V3, V6 and V8 line citations in the manifests and `test_repo_consistency.py` were not re-read; V5, V6 (rules 1-7), V7 and the profile slots were.

