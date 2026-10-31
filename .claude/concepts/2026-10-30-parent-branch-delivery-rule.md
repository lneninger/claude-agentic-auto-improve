# Concept Contract — A multi-sub-task contract is always delivered through a parent branch, and the version is raised once at landing

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-30
**Requested by:** user
**Status:** approved
**Amended:** Amended 2026-10-30 by user approval: W7 (R-10; the implementation notes record final-review B1, W1 and W2). Amended 2026-10-30 by user approval ("fix cycle with option (a)"): R-10 limited to merges before `adoptedAt`; narrowed landing evidence and `accepted_blocks`; last-review B-1, W-1, W-2, W-3, N-1, N-3 and N-4.
**Work Item Brief:** .claude/work-items/2026-10-30-113-parent-branch-delivery-rule.md
**Tracking issue:** #113
**Budget:** 12,000 tokens

---

## Business Concept

- **What is this thing, in domain language?**
  The **Parent Branch Delivery Rule**. A contract whose handoff has two or more mergeable sub-tasks is always delivered through a parent branch: the `branch:` of the contract's own Work Item Brief.
  - Every sub-task branch is cut from it, and every sub-task pull request targets it.
  - One landing pull request moves it to the default branch.
  - Nobody chooses this layout.
  - The plugin version is never raised in a sub-task pull request. It is raised once, during the landing, after the default branch has been merged into the parent branch.

  **What counts:** the script counts mergeable blocks, and a review gate is a mergeable block. So **one implementation block plus one review block is a multi-sub-task contract**, as contract 84 was. That shape now needs a parent issue, sub-issues and a landing. A Jira or Azure DevOps item cannot have a GitHub parent issue, so its contract can carry neither a second implementation block nor a review block; its review runs through `/flow`'s reviewer step. A contract with exactly one mergeable block is unchanged.

- **Existing VOCABULARY.md terms that apply:** **Contract Delivery** (amended, see Registry text), **Merge direction**, **Records pull request**, **Tracking Issue**.

- **New terms proposed for VOCABULARY.md (Universal):**
  - **Parent Branch Delivery Rule**: the rule above.
  - **Layout defect**: a contract-level reason, from a closed set, why a multi-sub-task contract cannot be dispatched, approved or recorded under the rule.
  - **Landing version raise**: the single raise the landing commits on the parent branch after merging the default branch: minor + 1, patch reset to 0, relative to the default branch's version. Under `landing: manual` the operator makes it (R-4).
  - **Accepted single-branch delivery**: a one-branch delivery of a multi-sub-task contract that had already merged, recorded by the owner through `--accept-single-branch`. The delivery record marks it with `layout: single-branch-accepted`.

---

## End-User View

Not applicable. Reason: no Angular UI surface is touched.

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership |
|------|--------|------------|-----------|
| Delivery Layout (derived, never stored) | sub-task count; parent branch; parent issue; layout defects | **L-1** Computed only for two or more mergeable blocks and a Status of `draft` or `approved`. **L-2** The parent brief comes from ONE pure `select_linked_brief(contract_text, slug, briefs)` over brief mappings that each carry `_path`. If the `**Work Item Brief:**` header names a brief, that brief is used, unless the matcher says its `contract:` names a different contract. A header naming a brief not in the list gives no brief and no fallback. With no header, the one brief the matcher accepts is used. **L-3** ONE matcher, `brief_names_contract(brief, slug)`, decides "names this contract". It owns ALL the filtering: it treats `contract:` values of `none`, `none - <text>`, `UNKNOWN`, empty and `<…` placeholders as unset, and otherwise matches when the stem equals the slug, case-insensitively. Feeders pass unfiltered brief lists: `_briefs_on_disk` (`land_contract.py:2583`), `build_delivery_set` (`:1398`) and the disk reader under `find_linked_brief`. `_names_contract` and `_brief_names_contract` stay as thin wrappers over it, so `cleanup_delivered.py:331`, rehydration (`pr_merged.py:857`), `locate_parent` (`:934`) and the stub reader (`:2792`) keep working: one matcher, thin wrappers. **L-4** Parent branch = the brief's `branch:`, never the default or a protected branch. Parent issue = its `id:`, a positive integer. **L-5** Sub-Task Work Items agree, checked by `declared_topology` with its reused readings `ambiguous` and `parent-is-default`. | `pr_merged.py`. **Four parent readers** go through `select_linked_brief`: the disk path (`--status`, `--dispatch`, `--record-delivery`), `locate_parent`, landing P0 (`_launch_land`) and landing P1. |

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Header value | the text after `**Work Item Brief:**` | Absent when empty, `none`, or starting with `<`. `data-architect` always writes it. The gate requires it only for two or more mergeable blocks. |
| Layout defect reason (closed) | `no-parent-branch`; `parent-is-default`, `ambiguous` (reused); `no-parent-issue`; `sub-task-raises-version` (a block's `Files to touch` lists a path equal, after slash normalisation, to an entry of `check_version_bump.MANIFESTS`, while `versionRaise` is on); `single-branch-delivery` (R-7) | `layout_defects` in `--status --json`, each with a `remedy`. They block dispatch (`advance()` returns `contract-defect` in place of `dispatch`) and approval (the gate). They never enter `is_delivered`, G-2 or the completion evaluation. |
| Version raise switch | `contractLanding.versionRaise: true` in the conventions file at `origin/<default>` | Turns on P7b and `sub-task-raises-version`. The paths come only from `check_version_bump.MANIFESTS`, imported by both scripts. |
| Version check mode | `default` (today's check); `parent` (only for a `task/<slug>/<id>` head into a non-default base: the head version must equal the base's version or the version at `merge-base(origin/<default>, HEAD)`); `exact` (minor + 1, patch 0, relative to `origin/<default>`, all entries agree) | `check_version_bump.py`. Stacked pull requests of single-block work are not `task/*` heads, so they are unaffected. |

### Commands

| Name | Handler | Possible rejections |
|------|---------|---------------------|
| Raise version at landing (P7b) | `land_contract.py` runs `check_version_bump.py --raise`, then `--exact` | `version-raise-failed` (a new halt; 26 halts) |
| Record delivery, multi-sub-task | `pr_merged.py --record-delivery` | G-7 `single-branch-delivery` (R-7) |
| Accept single-branch delivery (human-only) | `pr_merged.py --record-delivery <pr> --accept-single-branch` | the pull request is not verified merged by GitHub; any sub-task is `awaiting-merge`; any `failed` record other than the R-10 kind, or an R-8 record merged on or after `adoptedAt` (G-3, `merged-after-rule`); a delivery already recorded (G-5); GitHub or origin is unreadable (`unverifiable`, exit 10) |

### Rules

- **R-1** A landing raise is always minor. `CLAUDE.md` states this.
- **R-2** P7b runs whether or not P7 merged anything, and is idempotent.
- **R-3** `classify_conflict` returns a new class, `version-fields`, for a `MANIFESTS` path. Inside `_p7_merge`'s per-path branch, every region from `conflict_regions` must differ only in lines carrying `"version"`. If so, the default branch's side is taken and P7b rewrites those lines. Otherwise the merge halts `unresolvable-conflict`.
- **R-4 `landing: manual`.** P7b does not run. The operator merges the default branch into the parent branch, then runs `--raise` and `--exact`. CI enforces only "raised".
- **R-5** If the default branch moves, P12 halts `master-moved`. The rerun merges again (R-3) and recomputes (R-2).
- **R-6 Grandfathering.** Status decides who is judged: `draft` and `approved` are judged, everything else is exempt. Stored records are never re-judged, and new refusals apply only to new recordings. `is_delivered` is unchanged.
- **R-7 Delivery by evidence.** For a multi-sub-task contract, a pull request from the parent branch into the default branch is a landing only when every sub-task has a stored completion record with `verified: github`, `base_ref` equal to that pull request's `headRefName` (which must equal the layout's parent branch), and `base_is_default` not `true`. A missing `base_is_default` reads as "not the default", exactly as `candidate_kind` reads it, because `base_ref` is the deciding fact. The landing pull request is never matched to a sub-task by a title substring, only by these records. Otherwise:
  - `--record-delivery` refuses G-7 and writes nothing. The remedy depends on the situation:
    - **The work is not yet merged:** `/flow` (Step 2.7), then `/advance`.
    - **The work is already merged on the default branch:** `--accept-single-branch`, because the work is delivered and must not be re-dispatched.
  - The live `--status` reports `single-branch-delivery` only for a Delivery Candidate that is `known` and of kind `single-branch`, and only while no Records pull request of the contract is open. While one is open, the records are still on the records branch and the existing `delivery-unrecorded` arm names that pull request. A GitHub read that fails is reported as `unverifiable`, never as a layout defect.
- **R-8** `merge_direction.py` cannot stop a sub-task pull request into the default branch that is merged on the web. Only after the merge does `pr_merged.py` record it, as a `failed` completion record with `failure: single-branch-delivery`. The existing `escalate` move names it, and R-10 is its exit.
- **R-9 No endless loop.** When the move is `delivery-unrecorded`, the candidate is merged and G-7 would refuse, `next_command_for` names `/pr-merged <pr> --record-delivery --accept-single-branch`, never the refused command. `/advance` and `/pr-merged` show that command to the owner and never run it themselves. Once it has been recorded, the delivery exists, `is_delivered` holds, and the move is `complete`.
- **R-10 Accepting an R-8 failure (amended 2026-10-30, W7, option a).** The accept exit also clears a failed record caused by the new rule, **limited to pull requests that merged BEFORE the upgrade.** The human-only `--record-delivery <pr> --accept-single-branch` clears an R-8 failed record (`failure: single-branch-delivery`, `pull_request` = `<pr>`), and nothing else. It does so only when GitHub confirms `<pr>` merged, with a `mergedAt` strictly before the contract's `adoptedAt`.
  - **Adoption time, `adoptedAt`:**
    - **Where it lives:** the file `.claude/orchestrator/results/<slug>/rule-adoption.yaml`, in the git-tracked results folder that already holds the contract's completion and delivery records. It travels in the same Records pull request. `load_records` skips this file, the same way it skips the delivery record.
    - **When it is written:** exactly once, as the UTC instant of the first recording run of this code that writes an R-8 failed record for the contract, in the same write as that record. It is never rewritten.
    - **A contract that already holds an R-8 failed record from before this amendment shipped, with no `adoptedAt`:** the first recording run of the amended code for that contract writes `adoptedAt` as that run's instant. Read-only modes (`--status`, `--dry-run`, `--resume`) use "now" and write nothing. Those existing failures (merged earlier) can therefore be accepted.
    - **Accepted limit:** a web merge made after the upgrade but before the first R-8 run is read as before the rule.
  - **What it writes:** the failed record is replaced by a `completed` record for the same sub-task with:
    - `verified: github`, with `base_ref` and `base_is_default` as GitHub reports them
    - `layout: single-branch-accepted`
    - `replaces: {failure: single-branch-delivery, pull_request, merged_at, recorded_at}`, the structured copy of the record it replaced (W-3)
    - `note: "replaces failed record (failure: single-branch-delivery)"`
  - **The sub-issue:** the accept closes the sub-task's sub-issue the way a normal completion does, and stamps `sub_issue_closed` (B-1).
  - **No delivery record** is written unless the R-7 accept conditions also hold for `<pr>`.
  - **Sticky (B-1):** a later plain `/pr-merged <pr>` run for the same pull request URL never rewrites an accepted record into an R-8 failed record. `web_merged` is false when the existing record is an accepted one for that URL, and the rewrite keeps `layout`, `replaces` and `note`.
  - **Landing evidence (narrowed):** R-7 counts an accepted record only when it is `status: completed`, `verified: github`, `layout: single-branch-accepted`, `base_is_default: true`, and carries `replaces.failure: single-branch-delivery`. The later landing's Contract Delivery Record stamps `accepted_blocks: [<sub-task ids>]` whenever any of its evidence records is accepted, so the bypass stays visible.
  - **What it refuses (G-3):**
    - `merged-after-rule`: `mergedAt` is on or after `adoptedAt`.
    - Any other failed record: `only a single-branch-delivery failure can be accepted; <sub-task> failed with <failure>`.
    - `not-merged`: GitHub does not report `<pr>` merged.
    - `github-unverifiable`, exit 10: GitHub or origin cannot be read.
  - **What `next_command_for` prints (R-9, N-1):** the `escalate` move prints `/pr-merged <pr> --record-delivery --accept-single-branch` only when all of these hold:
    - every failed record is R-8 with `merged_at` before `adoptedAt`
    - no delivery is recorded (so G-5 cannot refuse it)
    - the pull request reference parses as a number

    An R-8 record merged on or after `adoptedAt`, or any other failure, prints `/design-first`, because the work must be re-scoped. A printed command is never one a guard refuses. Skills show it to the owner and never run it.

---

## Bypass flows

Choke point: `pr_merged.py`. Second enforcement point: the `/design-first` approval gate, which runs `--status` through the standard script lookup block and refuses the flip on any layout defect.

| # | Flow | Enforcement | Test |
|---|------|-------------|------|
| 1 | `/design-first` with no brief | A missing header gives `no-parent-branch`, with the remedy "run `/task`, then put the brief path in the header". Nothing is created before approval. | Missing header and placeholder header both read as absent |
| 2 | `/task` → `/design-first`, with or without `/flow` | `data-architect` writes the header. The approval step writes `contract:` into the existing linked brief when it is unset; this creates nothing. | Parity: all four readers return the same brief for one fixture set that includes a header-linked brief with `contract:` set to `none`, to `none - <text>`, to the placeholder, and missing |
| 3 | Issue offer declined, or free text | `no-parent-issue`. Remedy: open the issue and write its number into `id:`. | `id: none` |
| 4 | Jira or Azure DevOps item | `/task` Step 4 says in one line: "This item has no GitHub issue, so its contract must be a single block." `data-architect` writes no review block for it. | `id: PROJ-12`; text test |
| 5 | `/design-first` Step 4 with one-session implementers, then `/ship` | Step 4 hands blocks over only for a single block, and otherwise routes to `/flow`. If the delivery happens anyway: R-7 and R-9. | Two legacy fixtures shaped like 2026-10-16 (PR #58) and 2026-10-18 (PR #82), each with a merged one-branch delivery and no records. `next_command` names `--accept-single-branch`. Recording with it reaches `complete`, and repeated `advance()` calls never return to the refused command |
| 6 | A sub-task pull request merged into the default branch on the web | R-8, then R-10 (only for a merge before `adoptedAt`) | All with a real parent issue and an OPEN sub-issue: (a) the first R-8 writes `adoptedAt` once, and a second R-8 leaves it unchanged; (b) a merge before `adoptedAt`: `escalate` prints the accept, and the accept writes `replaces` and `layout` and closes the sub-issue; (c) re-recording the same pull request leaves the record accepted (sticky); (d) the later landing records with `accepted_blocks`, with no G-4 refusal; (e) running every remedy the next guard prints keeps the accept; (f) a merge on or after `adoptedAt`: G-3 `merged-after-rule`, and `next_command` is `/design-first`; (g) a pre-amendment failed record with no `adoptedAt` is acceptable, and read-only modes write nothing; (h) a different failure kind gives G-3; a pull request not merged is refused; unreadable GitHub or origin exits 10; a recorded delivery prints no accept (N-1); (i) a hand-made record with `layout: single-branch-accepted` but no `replaces` is not landing evidence; (j) text test: skills show the accept and never run it |
| 7 | `/advance` or `/pr-merged` typed by hand, with no Step 2.7 | Layout defects block dispatch. `effective_base` never returns `default` here. `needs_issue` is computed before the branch cut. | No issue: nothing is cut |
| 8 | One block amended to several | Recomputed on every call, so row 7 applies | 2 blocks, 1 state entry |
| 9 | A consumer upgrades mid-flight | R-6. Named defects come with remedies (rows 3, 5, 6, 7). Nothing is skipped silently. | Approved legacy fixture |
| 10 | Brief on the default branch | `parent-is-default` | `branch: master` |
| 11 | A sub-task raises the version | `contract-critic` BLOCKER; `sub-task-raises-version`; CI `parent` mode | 0.10.0 → 0.10.1 is refused with the default branch at 0.11.0; a stale merge of the default branch at 0.11.0 is allowed with the default branch at 0.12.0 |

**Exit 7 carries two refusals:** `base-not-declared` (remedy: `--record-subtask … --base`) and `needs-issue` (remedy: `/flow` Step 2.7). Each has its own `error` and `remedy`, and callers branch on `error`. Both refuse under `--dispatch` and `--dry-run` alike, so a preview matches the real run. Under `--status` and `--resume`, both are reported only.

---

## Reused Mechanisms

- **`find_linked_brief`, `_names_contract` and `_brief_names_contract` (now thin wrappers), `declared_topology`, `locate_parent`, `effective_base`, `advance()`, `next_command_for`, `needs_issue`, `candidate_kind`, `--record-delivery`, `build_record`, `open_records_pull_requests`**: extended as stated. A single-block contract's output is byte-identical.
- **Contract Landing**: extended with P7b, one halt and `version-fields`. L-16 is consumed as-is.
- **`check_version_bump.py`**: its `MANIFESTS` is the single path source. It gains `--raise`, `--exact`, `--default-branch` and `--head-ref`.
- **`merge_direction.py` R-1** and the **script lookup block**: consumed as-is.

## New Mechanisms (if any)

None.

---

## Extension Points

- **`pr_merged.py`:** `select_linked_brief`; `brief_names_contract` plus the wrappers; `delivery_layout`; `layout_defects`; the dispatch gating in `advance()`; `needs_issue` before the cut; G-7; `--accept-single-branch`; R-8; the R-9 arm in `next_command_for`.
- **`land_contract.py`:** P0 and P1 go through `select_linked_brief`; the feeders stop filtering; P7b; `version-raise-failed`; `version-fields`.
- **`cleanup_delivered.py`:** still calls `_names_contract`; a test pins that it is unchanged.
- **Conventions:** `contractLanding.versionRaise: true`.
- **`version-bump.yml`:** runs on all pull requests and passes `--default-branch` and `--head-ref`.
- **Text, each change asserted in `test_parent_branch_rule_text.py`:**
  - template (header line, rule paragraph, the implementation-plus-review sentence)
  - `data-architect`
  - `contract-critic` (a BLOCKER item)
  - `/design-first` (gate with the lookup block, the `contract:` write, Step 4 routing)
  - `/flow` (Step 2.7, line 342)
  - `/advance` (lines 171-190 and 272-290, exit 7, R-9)
  - `/pr-merged` references: `contract-completion.md` (R-7, R-9) and `undeliverable-sub-task.md` (R-8)
  - `/task` Step 4
  - `parent-aware-mode.md:299`
  - `CLAUDE.md`

**Registry text:** amend `VOCABULARY.md:47` **Contract Delivery** to add: "For a contract with two or more mergeable blocks, only the parent branch's landing pull request, or an owner-accepted single-branch delivery (`layout: single-branch-accepted`), is a Contract Delivery." Then append the four new terms.

---

## Integration Surfaces

| Source | Target | Mechanism | Data Shape |
|--------|--------|-----------|------------|
| `pr_merged.py --json` | `/design-first`, `/flow`, `/advance`, `/pr-merged` | JSON | `layout_defects`; `base_source: work-item-brief`; `needs-issue`; G-7 with both remedies; R-9 next command |
| `pr_merged.py` | `land_contract.py`, `cleanup_delivered.py` | import | `select_linked_brief`, `brief_names_contract`, wrappers |
| `land_contract.py`, `pr_merged.py`, CI | `check_version_bump.py` | import / subprocess | `MANIFESTS`, `--raise`, `--exact` |

No backend or frontend boundary is involved.

---

## Adjacent Areas

The cross-area scan found no signal above the threshold. The rows below were noticed by the architect.

| Area | Decision | Implication / Reason | Handle |
|------|----------|----------------------|--------|
| `/advance`, `/pr-merged`, `/task` text; `cleanup_delivered.py` | in-scope | In Files to touch | — |
| contract 86 | not applicable | Its Rule V is amended in its own work item (brief, Out of scope) | — |

## UI Implications

Not applicable. Reason: there is no frontend consumer.

## Chat Tool Impact

Not applicable. Reason: no endpoint or event is involved.

---

## Non-Goals

- Amending contract 86.
- Changing single-block contracts.
- Re-judging stored records.
- Non-GitHub parent issues (Q2).
- Consumer projects' own manifest lists.

## Confidence

Confidence: Medium.
- **High** on the current behaviour, read in code.
- **Medium** on R-3's region test, and on moving the filtering into one matcher, which callers outside `pr_merged.py` may sense.

## Alternatives Considered & Why Rejected

- **Chosen:** derive the layout from the header-linked brief through one selector and one matcher; decide delivery by stored evidence, with a human-only exit; raise the version in P7b.
- **Rejected:** a `**Delivery:**` header, because the user ruled the layout is not a choice.
- **Rejected:** moving Step 3.6 before approval, because it writes a brief and opens an issue before approval.
- **Rejected:** doing the raise as a regenerator, because regenerators run only on a merge.
- **Rejected:** a date constant, because it ties the rule to this repository's landing and not to when a consumer adopts it.
- **Rejected:** accepting a one-branch delivery automatically, because it would make the rule advisory. The exit is human-only.

## Uncertain Assumptions

- `VERIFIED via version-bump.yml:3-5`: the check runs only on pull requests into `master`.
- `VERIFIED via pr_merged.py:1541-1544, 4319-4326`: the silent fallback to `default`; `needs_issue` is computed after the cut.
- `VERIFIED via pr_merged.py:2825-2837, 3996-4031, 4059-4061`: `candidate_kind`; `--record-delivery` writes `base_is_default: true`; `merged-elsewhere` writes nothing.
- `VERIFIED via land_contract.py:2951-2958, 1984-2009`: P0 and P1 use `declared_topology`; `landing: manual` ends at P1.
- `ASSUMED`: `--status` parses a draft contract's handoff. Verification path: one test.

## Failure Modes & Mitigations

- **FM:** A single-block contract is affected. **Mitigation:** L-1, plus byte-identical tests.
- **FM:** The readers disagree. **Mitigation:** one matcher that owns the filtering, one selector, and the row 2 parity test.
- **FM:** An endless `delivery-unrecorded` loop. **Mitigation:** R-9, plus the legacy fixtures.
- **FM:** A false defect during an outage or while records are unmerged. **Mitigation:** R-7's `known` and open-Records-pull-request conditions.
- **FM:** A double raise, or dropped manifest edits. **Mitigation:** R-2, `--exact`, R-3.

---

## Open Questions for User

- [x] **Q1: How should "bumped after the merge against master" be read?** The landing merges the default branch into the parent branch, commits a raise of minor + 1 with patch reset to 0, relative to the default branch's version, verifies that head, and lands it. If the default branch moves, it reruns and recomputes. **Recommendation: confirm.** Answer: yes, confirmed by the user, 2026-10-30.
- [x] **Q2: Jira and Azure DevOps items.** They have no GitHub parent issue, so their contracts must be single blocks, with no second implementation block and no review block. **Recommendation: refuse at intake (`/task` Step 4) and at the gate with `no-parent-issue`.** Supporting them is a new contract. Answer: refuse, confirmed by the user, 2026-10-30.

---

## Critique

Condensed only. The full text of the earlier rounds was not kept.

**Round 1:**
- [BLOCKER] One-branch route. → Addressed by: R-7, R-8, R-9.
- [BLOCKER] Circular gate. → Addressed by: the header and the approval-time `contract:` write.
- [BLOCKER] The landing reader. → Addressed by: L-2 and L-3.
- [BLOCKER] Lookup block. → Addressed by: the gate text and `test_skill_script_lookup.py`.
- [WARN] Web merge into the default branch. → Addressed by: R-8.
- [WARN] Reach of the defects. → Addressed by: the Layout defect row.
- [WARN] `needs_issue`. → Addressed by: the exit-7 paragraph.
- [WARN] Manifest edits. → Addressed by: R-3.
- [WARN] `parent` mode. → Addressed by: the Version check mode row.
- [WARN] `versionRaise` location. → Addressed by: the switch row.
- [WARN] Issue opened before approval. → Addressed by: Step 3.6 not moved.
- [WARN] Late Q2. → Addressed by: row 4.
- [WARN] Consumer legacy. → Addressed by: R-6 and row 9.
- [WARN] `landing: manual` and the level. → Addressed by: R-4 and R-1.
- [WARN] Failure Mode 2. → Addressed by: L-2.
- [NIT] Stale text, two vocabularies, the manual alternative, the scan line. → Addressed by: Extension Points, L-5, Alternatives, Adjacent Areas.

**Round 2:**
- [BLOCKER] Single-branch delivery recorded via Contract Delivery. → Addressed by: R-7 and R-8.
- [BLOCKER] Feeders filter differently. → Addressed by: L-3 and the row 2 parity test.
- [WARN] P0 reader. → Addressed by: the four-reader list.
- [WARN] Date constant. → Addressed by: R-6.
- [WARN] Header. → Addressed by: the Header value row.
- [WARN] Exit 7. → Addressed by: the exit-7 paragraph.
- [WARN] Two manifest lists. → Addressed by: `MANIFESTS` as the single source.
- [NIT] R-3 location, stale default merge, minor step, read-only behaviour, review order. → Addressed by: R-3, row 11, the term definition, the exit-7 paragraph, the Review order note.

**Final coordinator pass:**
- [BLOCKER] No way out for an already-merged one-branch delivery. → Addressed by: `--accept-single-branch`, G-7's two remedies, R-9, and the legacy fixtures in row 5.
- [WARN] Keep `_names_contract`. → Addressed by: L-3 wrappers and `cleanup_delivered.py`.
- [WARN] `locate_parent`. → Addressed by: the four readers.
- [WARN] Filtering inside the matcher. → Addressed by: L-3 and the row 2 fixtures.
- [WARN] Records-branch window and outages. → Addressed by: R-7.
- [WARN] `--dry-run`. → Addressed by: the exit-7 paragraph.
- [WARN] Implementation plus review counts as multi-sub-task. → Addressed by: Business Concept.
- [WARN] `/pr-merged` references and VOCABULARY. → Addressed by: Registry text and Files to touch.

---

## Lessons referenced

- **2026-10-15 — Reuse the existing brief-linkage reader**: heeded by L-2 and L-3.
- **2026-10-15 — A cleanup wired to run before its own trigger event has fired never runs**: heeded (Step 3.6 not moved).
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test**: heeded.
- **2026-10-05 — One named location**: heeded (`MANIFESTS`; the switch at `origin/<default>`).
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case**: heeded (rows 1-2).
- **2026-10-22 — Describe a broken install by the rows each install age really has**: heeded (row 9, R-9).
- **2026-10-22 — An answered Open Question must amend the contract body**: Q1 and Q2 edit R-2, R-5 and row 4.
- Orthogonal to north-stars: none active.

---

## Implementation Handoff

**One block.** P7b reads its switch from `origin/<default>`, so a split delivery of this contract would land with no raise. This pull request raises the version (minor) itself.

**Review order** (one commit each):
1. `check_version_bump.py` and the workflow.
2. The selector, the matcher, the wrappers and the parity tests.
3. Dispatch, G-7, `--accept-single-branch`, R-8 and R-9.
4. `land_contract.py`.
5. Text and the registry.
6. The version raise.

**Implementation notes (final review, 2026-10-30; the code must match these):**
- **B1:** an unreadable origin (a fetch failure, a missing ref, or a failed listing or blob read) is `unverifiable`. G-7 exits 10 with `github-unverifiable` before any accept branch. The live report offers a re-read (`git fetch origin <base>`, then rerun), never `--record-delivery` and never the accept.
- **W1 (amended by last-review W-1):** the origin listing runs `git ls-tree --full-tree --name-only -z <ref> -- <folder>/`, splits on NUL, and returns None on any failure. That form works from any subfolder. A test pins the argv, and another runs it from a subfolder. None means unreadable (B1), never "no records".
- **W2:** the fetch uses the explicit refspec `+refs/heads/<base>:refs/remotes/origin/<base>` and sets `GIT_TERMINAL_PROMPT=0`.
- **N-3:** documented in the docstring and in `/pr-merged`: read-only modes (`--status`, `--dry-run`, `--resume`) also run that fetch. They refresh the shared `refs/remotes/origin/<base>`, which every worktree sees, and they write `FETCH_HEAD`.
- **Last-review W-2:** origin is read only when no Records pull request is open. When origin cannot be read while one is open, the report keeps the pointer to that pull request, and the reason names origin, not GitHub: "origin/<default> could not be read; run git fetch origin <default> and rerun". The candidate list is not rewritten to unknown.
- **N-4:** a contract file missing at landing P0 halts `unverifiable` with the remedy "restore .claude/concepts/<slug>.md on the parent branch, then rerun".
- **W7:** R-10 (option a), with the row 6 tests.

### 1. Parent branch delivery rule (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/pr_merged.py`
- `.claude/scripts/land_contract.py`
- `.claude/scripts/check_version_bump.py`
- `.claude/scripts/cleanup_delivered.py`
- `.claude/work-item-conventions.json`
- `.github/workflows/version-bump.yml`
- `.claude/scripts/tests/test_pr_merged.py`
- `.claude/scripts/tests/test_pr_merged_dispatch.py`
- `.claude/scripts/tests/test_land_contract.py`
- `.claude/scripts/tests/test_land_contract_identity.py`
- `.claude/scripts/tests/test_land_contract_conflicts.py`
- `.claude/scripts/tests/test_check_version_bump.py`
- `.claude/scripts/tests/test_cleanup_delivered.py`
- `.claude/scripts/tests/test_skill_script_lookup.py`
- `.claude/scripts/tests/test_parent_branch_rule_text.py`
- `.claude/templates/concept-contract.md`
- `.claude/registries/VOCABULARY.md`
- `agents/data-architect.md`
- `agents/contract-critic.md`
- `skills/design-first/SKILL.md`
- `skills/flow/SKILL.md`
- `skills/advance/SKILL.md`
- `skills/pr-merged/references/contract-completion.md`
- `skills/pr-merged/references/undeliverable-sub-task.md`
- `skills/task/SKILL.md`
- `skills/task/references/parent-aware-mode.md`
- `CLAUDE.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**Pre-written TASK block:**
```
TASK: Implement the Parent Branch Delivery Rule and the Landing version raise exactly as the
contract's Data Shapes, Rules R-1..R-10, Bypass flows, Extension Points, Registry text and the
Implementation notes (B1, W1, W2, W7) declare.
CONTEXT: concept contract at .claude/concepts/2026-10-30-parent-branch-delivery-rule.md
FILES: <the Files to touch list above>
CONSTRAINTS:
  - ONE brief_names_contract owns all "names this contract" filtering; feeders pass unfiltered
    lists; _names_contract/_brief_names_contract stay as thin wrappers. Four readers use
    select_linked_brief. Parity fixtures per row 2.
  - Layout defects block dispatch and approval only; stored records are never re-judged.
  - R-7 evidence fields exactly as stated; live report only for known candidates with no open
    Records pull request; GitHub failure = unverifiable.
  - --accept-single-branch is human-only: skills print it, never run it. R-9 next command.
    Legacy fixtures (#58, #82 shapes) reach complete with no loop.
  - Exit 7: distinct error/remedy; both refuse under --dry-run; report-only under --status/--resume.
  - check_version_bump.MANIFESTS is the only path list. P7b per R-1..R-5.
  - Single-block output byte-identical (test it). Follow the Review order.
  - Raise the plugin version (minor) in all five places in THIS pull request.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-parent-branch-delivery-rule.md
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
