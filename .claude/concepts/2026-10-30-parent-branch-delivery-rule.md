# Concept Contract — A multi-sub-task contract is always delivered through a parent branch, and the version is raised once at landing

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-30
**Requested by:** user
**Status:** approved
**Amended:** Amended 2026-10-30 by user approval: W7 (R-10; the implementation notes record final-review B1, W1 and W2). Amended 2026-10-30 by user approval ("fix cycle with option (a)"): R-10 limited to merges before `adoptedAt`; narrowed landing evidence and `accepted_blocks`; last-review B-1, W-1, W-2, W-3, N-1, N-3 and N-4. Amended 2026-10-30 on the user's design direction, "the record cannot have that kind of rule. Its only responsibility is to close the already done work.": the old R-7 to R-10 are replaced by R-7 (Records are plain) and R-8 (Layout warning). The failed R-8 record, G-7, `--accept-single-branch`, `adoptedAt` and everything built only on them are removed. Amended 2026-10-30 by user approval ("approve option 1 with W3 freshness refusal and N2 clearing"): new rule R-10, the freshness refusal G-7 `records-not-local` (stale data, every contract); the R-8 warning clears on completion; fixed `layout_warnings` forms (absent, `[]`, `held`, `unverifiable`); origin always read when judged; plain-records review W1, W2, W4, W5, W6 and N1.
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
  - **Layout defect**: a contract-level reason, from a closed set, why a multi-sub-task contract cannot be dispatched or approved under the rule.
  - **Layout warning**: a contract-level report that work already merged outside the parent branch while sub-tasks remain. It blocks nothing, it is never written into a record, and it clears once the contract is complete.
  - **Landing version raise**: the single raise the landing commits on the parent branch after merging the default branch: minor + 1, patch reset to 0, relative to the default branch's version. Under `landing: manual` the operator makes it (R-4).

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
| Layout defect reason (closed) | `no-parent-branch`; `parent-is-default`, `ambiguous` (reused); `no-parent-issue`; `sub-task-raises-version` (a block's `Files to touch` lists a path equal, after slash normalisation, to an entry of `check_version_bump.MANIFESTS`, while `versionRaise` is on) | `layout_defects` in `--status --json`, each with a `remedy`. They block dispatch (`advance()` returns `contract-defect` in place of `dispatch`) and approval (the gate). They never enter `is_delivered`, G-2, recording or the completion evaluation. |
| Layout warning reason (closed) | `single-branch-delivery`; `held` (a Records pull request is open); `unverifiable` (an input read failed) | `layout_warnings` in `--status --json` and in the Landing Report, each with a `remedy`. Blocks nothing. The key is absent for an unjudged contract (R-8). |
| Version raise switch | `contractLanding.versionRaise: true` in the conventions file at `origin/<default>` | Turns on P7b and `sub-task-raises-version`. The paths come only from `check_version_bump.MANIFESTS`, imported by both scripts. |
| Version check mode | `default` (today's check); `parent` (only for a `task/<slug>/<id>` head into a non-default base: the head version must equal the base's version or the version at `merge-base(origin/<default>, HEAD)`); `exact` (minor + 1, patch 0, relative to `origin/<default>`, all entries agree) | `check_version_bump.py`. Stacked pull requests of single-block work are not `task/*` heads, so they are unaffected. |

### Commands

| Name | Handler | Possible rejections |
|------|---------|---------------------|
| Raise version at landing (P7b) | `land_contract.py` runs `check_version_bump.py --raise`, then `--exact` | `version-raise-failed` (a new halt; 26 halts) |
| Record delivery / delivery-filled records (every contract) | `pr_merged.py --record-delivery`, and the per-PR recording | G-7 `records-not-local` (R-10, stale data); `github-unverifiable`, exit 10 |

### Rules

- **R-1** A landing raise is always minor. `CLAUDE.md` states this.
- **R-2** P7b runs whether or not P7 merged anything, and is idempotent.
- **R-3** `classify_conflict` returns a new class, `version-fields`, for a `MANIFESTS` path. Inside `_p7_merge`'s per-path branch, every region from `conflict_regions` must differ only in lines carrying `"version"`. If so, the default branch's side is taken and P7b rewrites those lines. Otherwise the merge halts `unresolvable-conflict`.
- **R-4 `landing: manual`.** P7b does not run. The operator merges the default branch into the parent branch, then runs `--raise` and `--exact`. CI enforces only "raised".
- **R-5** If the default branch moves, P12 halts `master-moved`. The rerun merges again (R-3) and recomputes (R-2).
- **R-6 Grandfathering.** Status decides who is judged: `draft` and `approved` are judged, everything else is exempt. `is_delivered` is unchanged.
- **R-7 Records are plain (user, 2026-10-30).** A completion record, and a Contract Delivery Record, only record that work is done, as GitHub reports it: `status: completed`, `verified: github`, and `base_ref` and `base_is_default` as GitHub reports them. A record never judges the delivery layout, never carries a layout verdict or marker, and no layout check refuses or fails a recording. A sub-task pull request merged into the default branch is recorded like any other completion, and it closes its sub-issue like any other completion. `--record-delivery` records a merged one-branch delivery like any other delivery. `merge_direction.py` and the dispatch and approval gates are where the layout is prevented. Records are where done work is closed.
- **R-8 Layout warnings (`layout_warnings`).** They are advisory and block nothing: not recording, not completion, not dispatch. They are derived from facts, never from a stored verdict. The key's presence and value are fixed:
  - **The key is absent** for an unjudged contract (exempt Status, or a single mergeable block). It is never `[]`.
  - **The key is `[]`** only when the contract is judged and every input read succeeded with nothing to report. That includes a contract that is complete, meaning no sub-task remains to deliver: the warning clears then (N2).
  - **`held`**, with the detail `records pull request open: <url>`: a Records pull request of the contract is open, so the warning is held back. It is never read as clean.
  - **`unverifiable`**, with a re-read remedy: an input read failed. That is a failed open-Records-pull-request lookup (None), or an unreadable `origin/<default>` (B1).
  - **`single-branch-delivery`**: only while sub-tasks remain to deliver, and only when the parent branch is resolved. With no parent branch, the layout defect already explains it (N1). It fires when a completion record has `base_is_default: true` or a `base_ref` other than the parent branch, or when a `known` Delivery Candidate is of kind `single-branch`. The records are always the local ones merged with `origin/<default>`'s. Origin is read whenever the contract is judged and no Records pull request is open, not only when a candidate exists (W2). Remedy: "This work is already on the default branch and is recorded as done; nothing needs undoing. Deliver the remaining sub-tasks through the parent branch (`/flow` Step 2.7, then `/advance`)."
- **R-10 Freshness refusal G-7 `records-not-local` (stale data, not layout).** This applies to every contract, single-block included. `--record-delivery`, and the per-pull-request recording that writes records filled in from a delivery, refuse with G-7 `records-not-local` when `origin/<default>` holds records for the contract that the local results folder does not, because writing from a stale checkout would overwrite the real records. The refusal writes nothing. Remedy (G-6 wording): "run again in a flat worktree cut fresh from origin/<base>". An unreadable origin exits 10 with `github-unverifiable` (B1).
- **R-9 The landing's own safety.** The landing never reads a record's verdict, because there is none. It relies on its own checks: the parent from `select_linked_brief` and `declared_topology` (P0 and P1), the completion move (P1), the merge of the default branch and P8's verification of the merged head on the parent branch, and the children-closed and review gates. A sub-task whose record shows it merged into the default branch is already in the default branch, so P7 brings it into the parent branch and P8 verifies it with the rest. The Landing Report repeats R-8's `layout_warnings`, using the same absent, `[]`, `held` and `unverifiable` forms. A failed listing gives `unverifiable`. The landing does not halt on any of them.
- **Removed:** the delivery-by-evidence refusal (the old G-7 `single-branch-delivery`; G-7 now names only R-10's `records-not-local`), the `--accept-single-branch` exit, the failed `single-branch-delivery` record, adoption time (`adoptedAt`, `rule-adoption.yaml`), `merged-after-rule`, sticky accepted records, `accepted_blocks`, `replaces`, accepted-record landing evidence, and the `escalate` arm that printed the accept. **The legacy-shape exit is no longer needed:** the legacy one-branch deliveries (PR #58, PR #82) record with the plain `/pr-merged <pr> --record-delivery`, because nothing refuses them, and R-8 reports the warning.


---

## Bypass flows

Choke point: `pr_merged.py`. Second enforcement point: the `/design-first` approval gate, which runs `--status` through the standard script lookup block and refuses the flip on any layout defect.

| # | Flow | Enforcement | Test |
|---|------|-------------|------|
| 1 | `/design-first` with no brief | A missing header gives `no-parent-branch`, with the remedy "run `/task`, then put the brief path in the header". Nothing is created before approval. | Missing header and placeholder header both read as absent |
| 2 | `/task` → `/design-first`, with or without `/flow` | `data-architect` writes the header. The approval step writes `contract:` into the existing linked brief when it is unset; this creates nothing. | Parity: all four readers return the same brief for one fixture set that includes a header-linked brief with `contract:` set to `none`, to `none - <text>`, to the placeholder, and missing |
| 3 | Issue offer declined, or free text | `no-parent-issue`. Remedy: open the issue and write its number into `id:`. | `id: none` |
| 4 | Jira or Azure DevOps item | `/task` Step 4 says in one line: "This item has no GitHub issue, so its contract must be a single block." `data-architect` writes no review block for it. | `id: PROJ-12`; text test |
| 5 | `/design-first` Step 4 with one-session implementers, then `/ship` | Step 4 hands blocks over only for a single block, and otherwise routes to `/flow`. If the delivery happens anyway: R-7 records it and R-8 warns. | Two legacy fixtures shaped like 2026-10-16 (PR #58) and 2026-10-18 (PR #82): the plain `--record-delivery` records them, the move reaches `complete`, no record carries a layout field, and the warning clears once complete (N2). R-10: a stale checkout is refused with `records-not-local` and writes nothing, for a single-block contract too |
| 6 | A sub-task pull request merged into the default branch on the web | `merge_direction.py` cannot stop it before it merges. After the merge, R-7 records it and R-8 warns. | With a real parent issue and an OPEN sub-issue: the record is `completed`, carries no `failure` and no layout field, and closes the sub-issue. `--status` lists the warning with its remedy and blocks nothing. The warning shows from a parent-branch checkout with no candidate (W2), and the later landing's report repeats it (R-9). Warning forms are covered: absent for an unjudged contract; `held` while a Records pull request is open; `unverifiable` for a failed lookup, origin read or landing listing; no warning with an unresolved parent (N1); `/advance` prints `layout_warnings` on every move (W4) |
| 7 | `/advance` or `/pr-merged` typed by hand, with no Step 2.7 | Layout defects block dispatch. `effective_base` never returns `default` here. `needs_issue` is computed before the branch cut. | No issue: nothing is cut |
| 8 | One block amended to several | Recomputed on every call, so row 7 applies | 2 blocks, 1 state entry |
| 9 | A consumer upgrades mid-flight | R-6. Named defects block only dispatch and approval (rows 3 and 7). Work already merged elsewhere records normally and gets the R-8 warning. Nothing is skipped silently. | Approved legacy fixture |
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

- **`pr_merged.py`:** `select_linked_brief`; `brief_names_contract` plus the wrappers; `delivery_layout`; `layout_defects`; the dispatch gating in `advance()`; `needs_issue` before the cut; `layout_warnings` (R-8).
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
  - `/advance` (lines 171-190 and 272-290, exit 7; one preamble line that prints `layout_warnings` on every move, W4)
  - `/pr-merged` SKILL.md (R-8 forms, R-10)
  - `/pr-merged` references: `contract-completion.md` and `undeliverable-sub-task.md` (R-7 and R-8; the accept, G-7 and failed-record text removed)
  - `/task` Step 4
  - `parent-aware-mode.md:299`
  - `CLAUDE.md`

**Registry text:** amend `VOCABULARY.md:47` **Contract Delivery** to add: "For a contract with two or more mergeable blocks, the delivery is the parent branch's landing pull request. A delivery made any other way is still recorded as it is, and `--status` reports the layout warning `single-branch-delivery`." Then append the four new terms.

---

## Integration Surfaces

| Source | Target | Mechanism | Data Shape |
|--------|--------|-----------|------------|
| `pr_merged.py --json` | `/design-first`, `/flow`, `/advance`, `/pr-merged` | JSON | `layout_defects`; `base_source: work-item-brief`; `needs-issue`; `layout_warnings` |
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

- **Chosen:** derive the layout from the header-linked brief through one selector and one matcher; prevent violations at dispatch and approval; keep records plain and report violations as warnings; raise the version in P7b.
- **Rejected:** a `**Delivery:**` header, because the user ruled the layout is not a choice.
- **Rejected:** moving Step 3.6 before approval, because it writes a brief and opens an issue before approval.
- **Rejected:** doing the raise as a regenerator, because regenerators run only on a merge.
- **Rejected:** a date constant, because it ties the rule to this repository's landing and not to when a consumer adopts it.
- **Rejected:** having a record judge the layout (refusing a delivery, writing a failed record, or using an accept exit with an adoption time), because the user ruled on 2026-10-30 that a record's only responsibility is to close the already-done work.

## Uncertain Assumptions

- `VERIFIED via version-bump.yml:3-5`: the check runs only on pull requests into `master`.
- `VERIFIED via pr_merged.py:1541-1544, 4319-4326`: the silent fallback to `default`; `needs_issue` is computed after the cut.
- `VERIFIED via pr_merged.py:2825-2837, 3996-4031, 4059-4061`: `candidate_kind`; `--record-delivery` writes `base_is_default: true`; `merged-elsewhere` writes nothing.
- `VERIFIED via land_contract.py:2951-2958, 1984-2009`: P0 and P1 use `declared_topology`; `landing: manual` ends at P1.
- `ASSUMED`: `--status` parses a draft contract's handoff. Verification path: one test.

## Failure Modes & Mitigations

- **FM:** A single-block contract is affected. **Mitigation:** L-1, plus byte-identical tests.
- **FM:** The readers disagree. **Mitigation:** one matcher that owns the filtering, one selector, and the row 2 parity test.
- **FM:** A false warning during an outage or while records are unmerged. **Mitigation:** R-8's `known` and open-Records-pull-request conditions, and B1.
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
- [BLOCKER] No way out for an already-merged one-branch delivery. → Addressed by: R-7 (nothing refuses it; it records plainly) and R-8 (warning). The accept exit was removed by the 2026-10-30 records-are-plain amendment.
- [WARN] Keep `_names_contract`. → Addressed by: L-3 wrappers and `cleanup_delivered.py`.
- [WARN] `locate_parent`. → Addressed by: the four readers.
- [WARN] Filtering inside the matcher. → Addressed by: L-3 and the row 2 fixtures.
- [WARN] Records-branch window and outages. → Addressed by: R-8 and B1.
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
3. Dispatch, and R-7 to R-9 (layout warnings).
4. `land_contract.py`.
5. Text and the registry.
6. The version raise.

**Implementation notes (final review, 2026-10-30; the code must match these):**
- **B1:** an unreadable origin (a fetch failure, a missing ref, or a failed listing or blob read) is `unverifiable` wherever origin's records are read (R-8). The live report offers a re-read (`git fetch origin <base>`, then rerun). It never reports the warning, and never its absence, on a failed read.
- **W1 (amended by last-review W-1):** the origin listing runs `git ls-tree --full-tree --name-only -z <ref> -- <folder>/`, splits on NUL, and returns None on any failure. That form works from any subfolder. A test pins the argv, and another runs it from a subfolder. None means unreadable (B1), never "no records".
- **W2:** the fetch uses the explicit refspec `+refs/heads/<base>:refs/remotes/origin/<base>` and sets `GIT_TERMINAL_PROMPT=0`.
- **N-3:** documented in the docstring and in `/pr-merged`: every judged `--status` reads origin (R-8, W2), and the read-only modes (`--status`, `--dry-run`, `--resume`) also run that fetch. They refresh the shared `refs/remotes/origin/<base>`, which every worktree sees, and they write `FETCH_HEAD`.
- **Last-review W-2:** while a Records pull request is open, the warning is `held`, and the move keeps the pointer to that pull request. Any origin-read failure names origin, not GitHub: "origin/<default> could not be read; run git fetch origin <default> and rerun". The candidate list is never rewritten to unknown.
- **N-4:** a contract file missing at landing P0 halts `unverifiable` with the remedy "restore .claude/concepts/<slug>.md on the parent branch, then rerun".

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
- `skills/pr-merged/SKILL.md`
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
Implementation notes declare.
CONTEXT: concept contract at .claude/concepts/2026-10-30-parent-branch-delivery-rule.md
FILES: <the Files to touch list above>
CONSTRAINTS:
  - ONE brief_names_contract owns all "names this contract" filtering; feeders pass unfiltered
    lists; _names_contract/_brief_names_contract stay as thin wrappers. Four readers use
    select_linked_brief. Parity fixtures per row 2.
  - Layout defects block dispatch and approval only. Records are plain (R-7): no layout
    field, no layout failure, no layout refusal of any recording.
  - R-8 layout_warnings: absent when unjudged, [] only when every read succeeded, held while
    a Records PR is open, unverifiable on any failed read; clears on completion; none when the
    parent is unresolved; origin read whenever judged. Legacy #58/#82 shapes record plainly.
  - R-10 G-7 records-not-local for EVERY contract (stale data, not layout); writes nothing.
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
