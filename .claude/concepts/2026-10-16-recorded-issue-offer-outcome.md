# Concept Contract — Recorded outcome of the issue offer

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-16
**Requested by:** user
**Work Item Brief:** .claude/work-items/2026-10-16-plugin-own-repo-issue-closing.md
**Status:** approved
**Supersedes:** none
**Tracking issue:** #57

> **Protocol:** filled in by `data-architect`. Implementers refuse to run unless `Status: approved`. The `concept-gate.py` hook reads `Files to touch`.

---

## Business Concept

- **What is this thing, in domain language?**
  When work starts without a tracker issue, the chain offers to open one. That offer appears at two places today: intake (`/task` Step 2.5 point 6) and shipping (`/ship` Step 3.5). The run that starts at `/design-first` without `/task` never makes it (Step 3.6). Today the brief keeps only `id: none` (the Work Item Brief's issue number field, with "none" meaning no issue). So the brief cannot tell apart three different stories: the user said no, the offer could not be made, or nobody asked. An agent that keeps working on an assumption writes the same `id: none` as a user who declined. The link checker (`verify_issue_link.py`, the script `/ship` runs after opening the pull request to ask GitHub whether the closing link resolved) then reports `not-applicable`, a success. Nothing in the chain ever stops. That is the root cause confirmed in `.claude/debug-notes-own-repo-issue-closing.md`.
  This contract adds one recorded fact to the brief: the **Issue offer outcome**, meaning what happened when the chain offered to open an issue. All three call sites write it. It also adds a per-repository switch that makes the link checker halt when a brief has no issue and no recorded user decision. This repository turns the switch on. Every other project keeps today's behaviour unless it opts in, either by building its conventions file with the doctor (which writes the switch as `false`) or by following the README upgrade note (which says to leave it `false` when copying the block). In short, every project records the outcome, and only a project that opts in halts on a missing one.

- **Existing VOCABULARY.md terms that apply:**
  - Work Item Brief (used throughout, defined in the brief template in `skills/task/SKILL.md` Step 2). It has no registry entry of its own.
  - **Tracking Issue** (Universal). This is a different thing: the issue that tracks a contract's follow-ups. It is not touched here.
  - **Contract Delivery** and **Records pull request**. Not touched; named here so the reader does not confuse them.
  - From the `issueLink` block of `.claude/work-item-conventions.json` (the conventions file, the single source of truth for issue and pull-request keyword data): **Brief Id Reading** kinds `absent` / `unresolved` / `number` / `malformed`, the `absentIdTokens` list, `linkStates`, `verdicts`.

- **New terms proposed for VOCABULARY.md (Universal, after approval):**
  - **Issue offer outcome**: the recorded answer to "should this work get a tracker issue?", kept in the brief beside `id:` as `issue_offer`. Its values come from a closed set: `pending`, `opened`, `declined`, `unavailable`. It records what happened, not what someone intended. An assumed answer is recorded as `pending` and never as a decline.
  - **Recorded-offer requirement**: the per-repository switch `requireRecordedOffer` in the conventions file. When it is on, a brief with no issue must carry a recorded user decline, or a recorded reason the offer could not be made that still holds at ship time, before its pull request counts as shipped. When it is off, or missing, today's behaviour holds.

---

## End-User View

Not applicable. Reason: no Angular or other UI surface is in `Files to touch`. The change is to skill text, one Python script, a JSON conventions file and tests. The only person who notices it is the operator running the chain: a pull request whose brief records no issue decision stops with a named reason instead of passing silently.

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership (aggregate) |
|------|--------|------------|-----------------------|
| Work Item Brief (extended) | existing fields, plus `issue_offer` (enum, the Issue offer outcome) and `issue_offer_reason` (enum, present only with `unavailable`) | **I-1** The outcome is read only when the Brief Id Reading is `absent`. When `id:` is a number, the outcome is ignored, because the id wins. **I-2** An absent id with outcome `opened` contradicts itself, and is treated as unrecorded. **I-3** "No reason" means the `issue_offer_reason` key is absent. An empty value is read the same as absent. `unavailable` requires a reason from the closed reason set. `declined` with a reason still counts as recorded, and the reason is ignored. **I-4** An agent never writes `declined` unless the user answered the offer question in this run. An assumed answer writes `pending`. **I-5** Values are colon-free single tokens, because the brief parser reads any line with a colon as a new key. **I-6** The brief template writes `issue_offer: pending` and no reason key. A value that is still a template placeholder is an unknown value, and is treated as unrecorded. | The brief is its own aggregate. Writers: `/task` Step 2 and Step 2.5 point 6, `/design-first` Step 3.6, `/ship` Step 3.5. Reader: `verify_issue_link.py`. |

**Closed sets** (accepted at Open Question 1):
- `issue_offer`: `pending` (not yet asked, or asked and assumed) | `opened` (issue created; `id:`, `url:` and `repo:` written back) | `declined` (the user said no) | `unavailable` (the offer could not be made).
- `issue_offer_reason`: `gh-missing` | `gh-unauthenticated` | `create-failed` | `no-problem-statement`. The first two reuse the script's existing `UNVERIFIABLE_CAUSES` spellings. `no-problem-statement` names today's "Invent nothing" rule.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Recorded-offer requirement (conventions `issueLink` keys) | `requireRecordedOffer` (boolean, missing means false), `offerOutcomeField` ("issue_offer"), `offerOutcomes` (the closed set above), `offerReasonField` ("issue_offer_reason"), `offerReasons` (the closed reason set) | Read by the link checker. The skills cite the keys by name and never restate the values (same rule as `absentIdTokens`, INV-8). |
| Brief Id Reading (unchanged) | kind, raw | Still decides first. The offer outcome adds a sub-partition of `absent` only. |

**Where the switch and its value lists are read (accepted at Open Question 2):**
- **One file.** The switch, the four offer keys and the `verdicts` list used for the offer check are all read from the same file: the conventions file in the brief's own `.claude` folder (`<brief>/../../work-item-conventions.json`). None of them is read through the shared multi-root locator. The other `issueLink` keys (keywords, id tokens, repair budget) keep today's reading.
- **Off.** A missing file, a missing switch key or any switch value other than `true` means off.
- **On, incomplete.** If the switch is on and any of `offerOutcomeField`, `offerOutcomes`, `offerReasonField`, `offerReasons` or `verdicts` is missing or empty in that same file, the verdict is `unverifiable` with cause `conventions-missing`, exit 2, and the reason names the missing keys. It never borrows the lists from another root.
- **The brief path must exist as given.** The switch is read only when the brief was found at the path the caller passed. The verifier keeps its existing fallback that finds a relative brief through `work_items_dir()`, so a brief with a number id still verifies as today. But when the brief was found only through that fallback and its id reading is `absent`, the verifier cannot tell which project's switch applies. It then halts `unverifiable` with a new cause, `brief-path-unresolved` (remediation: "pass the brief path as it exists from the current directory"). It never falls through to the locator. This is the one change that can reach a project with the switch off, and only on that path. A brief that exists nowhere keeps today's fail-open `not-applicable` (INV-9, case 21).
- **Implementation note (divergence from "Off", recorded at green round 3).** The "Off" rule above says a missing file means off, and the paragraph above says `brief-path-unresolved` is the one change that reaches a project with the switch off. In the implementation a second path exists: a conventions file beside the brief that EXISTS but is not valid JSON (a byte-order-mark counts) halts `unverifiable` / `conventions-missing` for an absent id even when the switch would be off, because the switch cannot be read. A MISSING file still means off. The reason text says the file is not valid JSON and does not claim the requirement is on. Pinned by test cases 48 and 52; also stated in the conventions `$offerComment` and the README upgrade note.

### Events

| Name (past tense) | Emitter | Listeners | Payload |
|-------------------|---------|-----------|---------|
| Not applicable | Not applicable. Reason: the plugin has no event bus. State is passed through brief fields and script verdicts. | — | — |

### Commands (if any)

| Name (imperative) | Handler | Payload | Possible rejections |
|-------------------|---------|---------|---------------------|
| Verify the closing link (existing CLI, extended) | `verify_issue_link.py --brief --pr` | brief path, pull-request number | New halting verdict `offer-unrecorded`; `unverifiable` with cause `conventions-missing` (switch on, lists incomplete) or the new cause `brief-path-unresolved`. The existing rejections are unchanged. |

**Verdict changes.** The `verdicts` / `VERDICTS` closed set grows from 16 to 19. The new values are appended, and they are evaluated in the slot of today's rule 4 (the `absent` kind), so every later rule keeps its order. `UNVERIFIABLE_CAUSES` gains `brief-path-unresolved`.

By the time the verifier reaches the `absent` rule it has already run `gh --version` successfully (`verify_issue_link.py:730-737`), so `gh` is known to be present. A recorded `unavailable` with reason `gh-missing` or `gh-unauthenticated` is therefore stale at ship time and does not count.

| Condition (id reading `absent`, brief found at the given path) | Switch off | Switch on |
|---|---|---|
| any outcome, or none | `not-applicable`, `issue_link: none` (unchanged) | — |
| `declined` (with or without a reason) | — | `offer-declined`, success, `issue_link: none` |
| `unavailable` with reason `create-failed` or `no-problem-statement` | — | `offer-unavailable`, success, `issue_link: none`, reason echoed in the result |
| `unavailable` with reason `gh-missing` or `gh-unauthenticated` | — | `offer-unrecorded`, **halting**: "recorded reason is stale; gh is present now" |
| `pending`, key missing, unknown or placeholder value, `opened`, or `unavailable` with no or an unknown reason | — | `offer-unrecorded`, **halting**, exit 2, writes no `issue_link`, reason names which case it was |

The result's reason must name the case, so `/ship` can print it verbatim.

---

## Reused Mechanisms

- **`issueLink` closed sets in `.claude/work-item-conventions.json`** (`absentIdTokens` / `linkStates` / `verdicts`, with `partialField` / `linkStateField` as the precedent for naming a brief field in conventions). **Extended by** five keys and three verdicts. There is no parallel file and no parallel token list.
- **`verify_issue_link.py` ordered decision procedure** (`VERDICTS`, `ISSUE_LINK_WRITES`, `HALTING`, `UNVERIFIABLE_CAUSES`, `evaluate` rules first-match-wins). **Extended**: rule 4 gains a sub-partition, and the cause set gains `brief-path-unresolved`. INV-10 (no mutation) and INV-9 (missing data fails open, missing resolver fails loud) are unchanged. **INV-12 is amended**: today it reads "Every path resolves through `_claude_paths`". It becomes: every path resolves through `_claude_paths`, with one named exception, the conventions file beside the brief, read by exact path for the Recorded-offer requirement. The reason is that a project-owned switch must never come from another root (journal 2026-10-15 and 2026-10-16).
- **One mechanism, several call sites** (the shared wording between `/task` Step 2.5 point 6 and `/ship` Step 3.5). **Extended to a third call site**, `/design-first` Step 3.6. All three use one shared wording, including `gh issue create ... --body-file <path>`. None passes the body inline.
- **`test_ship_skill_sync.py`** (INV-S1 to INV-S6: the skill's prose tested against the script's closed sets). **Extended** with an offer-outcome check (INV-S7) and the verdict count 16 → 19.
- **`plugin_doctor.py` conventions scaffold**, the repository's second copy of the conventions shape. **Extended** with the same offer keys and the `verdicts` list, with the switch explicitly `false`. A scaffold-equals-shipped test pins them, following `test_compose_subissue_title.py:576-595`.
- **Version bump** (`check_version_bump.py`, five manifest entries). Consumed as-is: 0.9.3 → 0.9.4.
- **Direct project-file read** (journal 2026-10-15 / 2026-10-16: a project-owned file is read from an exact path, never from the multi-root locator). Consumed as the rule for where the switch and its lists are read.

---

## New Mechanisms (if any)

None. Every change extends the `issueLink` closed sets and the verifier's ordered rules.

---

## Extension Points

1. `.claude/work-item-conventions.json` → `issueLink`: add `requireRecordedOffer: true` (this repository only), `offerOutcomeField`, `offerOutcomes`, `offerReasonField`, `offerReasons`. Append the three verdicts to `verdicts`. Add a `$comment` that says where the switch is read, that missing means off, that switch-on with incomplete lists halts, and that a project copying this block should set the switch to `false` unless it wants the halt.
2. `verify_issue_link.py`:
   - Append the three verdicts to `VERDICTS`.
   - Add `offer-declined` / `offer-unavailable` → `none` to `ISSUE_LINK_WRITES`, and add `offer-unrecorded` to `HALTING`.
   - Add `brief-path-unresolved` to `UNVERIFIABLE_CAUSES` and `REMEDIATION`.
   - Add a pure brief reader for the outcome and the reason.
   - Read the switch and the offer lists from the brief's own `.claude` folder, and only when the brief path exists as given.
   - Split rule 4.
   - Amend the INV-12 text, and update the docstring's rule count.
3. `skills/task/SKILL.md`:
   - The brief template gains `issue_offer: pending`, and documents `issue_offer_reason:` as written only with `unavailable`. The template shows no reason key by default.
   - Step 2.5 point 6 always writes the outcome. When the gate fails because `gh` is missing or signed out, it writes `unavailable` plus the reason instead of saying nothing. When the problem statement is empty, it writes `unavailable` / `no-problem-statement`. On decline it writes `declined`. On accept it writes `opened`. An assumed answer writes `pending`.
   - The create command uses `--body-file`.
4. `skills/ship/SKILL.md`:
   - Step 0 reads the outcome.
   - Step 3.5's gate fires when the outcome is anything other than `declined` or `unavailable` / `no-problem-statement`. That covers `pending`, a missing key, `unavailable` with a `gh-*` reason, and `unavailable` / `create-failed`. The step records the answer. The create command uses `--body-file`.
   - Step 3 Notes gets one line when the brief has no issue: "No issue: declined by the user", or "No issue: could not be opened (<reason>)".
   - The Step 4d table gains the three rows, plus `brief-path-unresolved` in the halting group.
   - Step 5 is unchanged except for the new verdicts' `issue_link` values.
5. `skills/design-first/SKILL.md` Step 3.6: the minimal brief carries `issue_offer`. The step makes the shared offer with the same wording as the other two sites, using `--body-file`, and records the outcome. The paragraph "Do not ask a question for this" is narrowed: it still holds for the facts the step records, and the offer is the one question the step asks.
6. `.claude/scripts/plugin_doctor.py`: the scaffold gains the five offer keys with `requireRecordedOffer: false`, plus the `verdicts` list.
7. `README.md`: in the upgrade note near line 565 ("copy ... from this repository's copy into yours"), say that this repository's `requireRecordedOffer` is `true`, that copiers should leave it `false` unless they want the halt, and that turning it on needs the offer keys and the `verdicts` list in their own file.

---

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| `/task`, `/design-first`, `/ship` (writers) | Work Item Brief | frontmatter field | `issue_offer`, `issue_offer_reason` | skill → file |
| Work Item Brief + brief-side conventions file | `verify_issue_link.py` | file read | outcome + switch + offer lists | file → script |
| `verify_issue_link.py` | `/ship` Step 4d / Step 5 | JSON verdict | three new verdicts, one new cause | script → skill |

**Changes to existing integration surfaces:** there is no API, SignalR or DTO. The one contract shape that moves is the verdict closed set, and both sides change in the same sub-task (`verify_issue_link.py` and `skills/ship/SKILL.md`), pinned by `test_ship_skill_sync.py`.

---

## Adjacent Areas

The main session ran the cross-area scanner (`cross_area_scan.py`) on 2026-10-16. It reported `primary: (none)` and "no adjacent areas above threshold". Its code-graph signal was skipped because the code-graph tool's `impact` command failed, so the scan rests on the other two signals only. The rows below were found by reading, and they stand.

| Area | Decision | Implication / Reason | Handle |
|------|----------|----------------------|--------|
| Plugin doctor conventions scaffold | in-scope | It is the second copy of the conventions shape, and was updated in lockstep by `2026-10-15-subissue-title-parent-ref` (Reused Mechanisms entry). | `.claude/scripts/plugin_doctor.py` in Files to touch |
| Parent-aware sub-issues (`/flow`, `references/parent-aware-mode.md`) | not applicable | Point 6 "does not fire in Parent-aware mode" (`skills/task/SKILL.md` Step 2.5), and `/ship` Step 3.5 skips any brief with a resolved `parent_issue:`. Those briefs always carry a number id, so I-1 ignores the outcome. | — |
| Vendored copies in consuming projects | not applicable | Out of scope per the brief. Consumers keep `not-applicable` because the switch is missing or `false` on their side (the Recorded-offer requirement value object, and the README upgrade note). | — |

---

## UI Implications

Not applicable. Reason: no frontend consumer in Integration Surfaces. The repository has no frontend roots.

---

## Chat Tool Impact

**2. No — this contract adds no REST endpoint and no SignalR event.** Justification: it changes skill text, one local verification script and a JSON conventions file. There is no endpoint or event for a chat tool to wrap.

---

## Non-Goals

- Closing issues 51 and 21. Back-filling issues for pull requests 5 to 55. Changing other projects' repositories or vendored copies. (All three are out of scope per the brief.)
- Proving that a human, not an agent, answered the offer. A brief field is agent-written, so I-4 is a rule in the skill text, not something a machine can check. The halt catches the "never asked" case and a stale "could not offer", not a forged "declined".
- Changing what happens when an id is a number (acceptance criterion 2 already holds through `linked` / `absent-repairable`). This contract only adds a regression check.
- Sub-tasks of larger contracts (pull requests 41 to 46), which link to a parent.

---

## Confidence

Confidence: Medium-High. High on the root cause and the verifier change: both were read in code, the debug notes replayed the defect, and every critic finding now has a stated rule and a test. Medium on the brief-path fallback rule: it is a narrow behaviour change, and the replay in Uncertain Assumptions must confirm which path `/ship` actually passes.

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** a brief field plus a conventions switch plus new verifier verdicts. Why: the halt lives in the one script that already decides "shipped", and every closed set stays in the conventions file.
- **Option B (rejected):** reuse `id:` with new tokens (`declined`, `unavailable`) added to `absentIdTokens`. Why rejected: that list's meaning is "deliberately no issue, success", so folding "never asked" into it rebuilds the exact undifferentiated state (the `$tokenComment` warns against this). It also cannot carry a reason.
- **Option C (rejected):** enforce in skill prose only ("`/ship` must ask"). Why rejected: the root cause is that the ask is prose with no script check. Pull request 55's brief shows prose being skipped.
- **Option D (rejected):** turn the switch on for every project. Why rejected: it would halt consumers whose chains never wrote the field, and the brief scopes changes to this repository.
- **Option E (rejected):** keep the switch `false` in this repository's file and turn it on some other way. Why rejected: the switch's whole purpose is that this repository halts. The copy risk is handled by the doctor scaffold (`false`) and the README upgrade note instead.

---

## Uncertain Assumptions

- `VERIFIED via .claude/scripts/verify_issue_link.py:461-463`: an absent id returns `not-applicable` with no halt, and `:737` returns before any `gh repo view`.
- `VERIFIED via .claude/scripts/verify_issue_link.py:730-737`: `gh --version` runs before the id is read, so `gh` is present whenever the `absent` rule runs.
- `VERIFIED via .claude/scripts/verify_issue_link.py:186`: conventions are read through `work_item_conventions_path()`, the multi-root locator (`_project_paths.py:234`). That is why the switch and its lists must not be read through it.
- `VERIFIED via .claude/scripts/verify_issue_link.py:721-726`: a relative brief that does not exist from the current directory is replaced by `work_items_dir() / name`, and a brief found nowhere fails open to `not-applicable`. Case 21 pins both.
- `VERIFIED via .claude/scripts/verify_issue_link.py:46`: INV-12 reads "Every path resolves through `_claude_paths`".
- `VERIFIED via .claude/scripts/tests/test_ship_skill_sync.py:105,116-132`: the suite pins the verdict count at 16. INV-S2 flags any backticked hyphenated token in the ship skill that is absent from the script, so `create-failed`, `no-problem-statement` and `brief-path-unresolved` must appear in the script text or in that test's vocabulary set.
- `VERIFIED via .claude/scripts/tests/test_verify_issue_link.py:977-1018,1154`: cases 15, 19 and 20 require `VERDICTS` to equal both a hard-coded list and the real conventions `verdicts` array, in order.
- `VERIFIED via .claude/scripts/plugin_doctor.py:97-121`: the scaffold's `issueLink` has no offer keys and no `verdicts` list today.
- `ASSUMED`: `/ship` Step 4d passes a brief path that exists from its current directory, so the brief-path rule does not fire on the normal path. Verification path: the implementer replays `/ship` Step 4d from this worktree and records the path passed and which `.claude` folder the switch was read from.
- `ASSUMED`: no other script reads the brief's frontmatter with a closed key list that would reject `issue_offer`. Verification path: grep `parse_frontmatter` callers in `.claude/scripts/` (for example `pr_merged.py`).

---

## Failure Modes & Mitigations

- **FM:** A consumer under a plugin install inherits this repository's switch through the locator.
  - **Mitigation:** the switch is read only from the brief's own `.claude` folder, and a missing key means off. The test plants a decoy file with the switch on in each other place the locator or a fallback could reach: the `CLAUDE_PROJECT_DIR` root, the resolver's own root, the current directory and the home folder. Every decoy run must give `not-applicable`.
- **FM:** A project copies this repository's `issueLink` block and turns the halt on without meaning to.
  - **Mitigation:** the README upgrade note and the conventions `$comment` both say to leave the switch `false` unless the halt is wanted. The doctor scaffold writes `false`.
- **FM:** The switch is on but the offer lists or the `verdicts` list are missing or empty, and values are borrowed from another root.
  - **Mitigation:** all offer keys are read from the same file as the switch. Missing or empty lists halt `unverifiable` / `conventions-missing`, naming the keys. This is tested.
- **FM:** The brief was found through the `work_items_dir()` fallback, so its folder was chosen by the locator.
  - **Mitigation:** for an absent id, halt `unverifiable` / `brief-path-unresolved`. Never read a switch from a locator-chosen folder. This is tested, and case 21 stays green.
- **FM:** An `unavailable` / `gh-missing` recorded at intake passes at ship time after the second ask was skipped (the pull request 55 pattern).
  - **Mitigation:** the verifier treats a `gh-*` reason as stale and halts `offer-unrecorded`, because it has already proven `gh` is present.
- **FM:** An agent assumes "no" and writes `declined` (the pull request 55 pattern, in a new spelling).
  - **Mitigation:** I-4 in all three skills states that an assumed answer writes `pending`. This is not machine-provable (Non-Goals). The reviewer checks the wording.
- **FM:** The halt fires at Step 4d, after the pull request is open.
  - **Mitigation:** under the switch, Step 3.5 is the primary path and asks before the pull request is created. Step 4d is only the safety net. A halt leaves the draft open and `status:` unchanged, the same honest partial delivery as today's halts.
- **FM:** The verdict set drifts between the script, the conventions file, the scaffold and the ship table.
  - **Mitigation:** existing cases 15, 19 and 20, INV-S1 to INV-S3, the new INV-S7, and the new scaffold-equals-shipped test.
- **FM:** The free-text issue body is corrupted under Git Bash.
  - **Mitigation:** all three call sites use `gh issue create ... --body-file <path>` in one shared wording (journal 2026-10-16, Git Bash free text).

---

## Open Questions for User

- [x] **Q1 — Field name and values.** Recommendation: field `issue_offer` with `pending | opened | declined | unavailable`, plus `issue_offer_reason` with `gh-missing | gh-unauthenticated | create-failed | no-problem-statement`, used only with `unavailable`. These are short, colon-free, and the two `gh-*` reasons reuse spellings the verifier already has. User: accepted the recommendation (2026-10-16)
- [x] **Q2 — Is the switch per repository, in the conventions file, read beside the brief?** Recommendation: yes. `issueLink.requireRecordedOffer`, `true` in this repository, `false` in the doctor scaffold, and copiers told by the README to leave it `false`. It is read only from the brief's own `.claude/work-item-conventions.json`, never through the shared locator. No environment variable. User: accepted the recommendation (2026-10-16)
- [x] **Q3 — Halt or warn when a brief has `id: none` and no recorded outcome?** Recommendation: **halt** (`offer-unrecorded`, exit 2) when the switch is on. A warning is exactly the green "success" the debug notes caught. User: accepted the recommendation (2026-10-16)
- [x] **Q4 — Should `/design-first` Step 3.6 ask, or defer?** Recommendation: **ask**, with the same wording as the other two sites. The only reason is that the issue then exists sooner, at design time instead of at ship time. Today's "do not ask a question" rule stays true for the facts the step records; the offer is the one real question. User: accepted the recommendation (2026-10-16)
- [x] **Q5 — Is a recorded intake decline final?** Recommendation: **yes, final**. `/ship` asks again only when the outcome is `pending`, missing, `unavailable` with a `gh-*` reason, or `unavailable` / `create-failed`. It does not ask after `declined`, or after `unavailable` / `no-problem-statement`, where there is still nothing honest to put in the issue body. A `gh-*` reason is not trusted at ship time: the Step 3.5 gate needs `gh` to be available, and the verifier has already shown it is, so a recorded `gh-*` reason left in place halts `offer-unrecorded`. User: accepted the recommendation (2026-10-16)
- [x] **Q6 — How should existing briefs be treated?** Recommendation: **no grandfathering**. A brief with `id: none` and no `issue_offer` reads as unrecorded. Already-shipped briefs are never re-verified, so nothing shipped is affected. An in-flight brief simply gets the one real ask at `/ship` Step 3.5. User: accepted the recommendation (2026-10-16)

---

## Critique

**Critic:** contract-critic
**Date:** 2026-10-16
**Verdict:** warnings-only

### Findings

- **[WARN] The switch is turned on in the file other projects copy as their template**
  - **What is wrong:** This repository's `.claude/work-item-conventions.json` is also the template the plugin ships (README line 391: "TEMPLATE - schema intact, empty content set"), and README line 565 tells upgrading projects to copy blocks "from this repository's copy into yours". Setting `requireRecordedOffer: true` there means any project that copies the `issueLink` block turns the halt on without choosing to. That contradicts "Every other project keeps today's behaviour unless it opts in" and quietly does what Option D rejects. Only projects built by the doctor (scaffold `false`) are protected.
  - **Prior artifact ignored:** `MECHANISMS.md` line 44 (Plugin registry ownership model: a misclassified generic file "lands in every consuming project"); `.claude/concepts/2026-10-15-subissue-title-parent-ref.md` (the source of the README "copy this block from this repository's copy" upgrade note).
  - **Where in this contract:** `## Extension Points` item 1, "add `requireRecordedOffer: true` (this repository)"; `## Business Concept`, "Every other project keeps today's behaviour unless it opts in."
  - -> Addressed by: the switch stays `true` in this repository's file. The doctor scaffold writes `false`. The README upgrade note near line 565 and the conventions `$comment` tell copiers to leave it `false` unless they want the halt (Extension Points 1, 6, 7; Business Concept; Failure Modes; Option E). `README.md` is in Files to touch.
- **[WARN] A stale "could not offer" from intake still passes at ship time, which brings the root cause back**
  - **What is wrong:** The verifier checks `gh --version` before it reads the id (`verify_issue_link.py:730-737`). So whenever it reaches the `absent` rule, it has just shown that `gh` is present. Even so, the table accepts `unavailable` / `gh-missing` recorded at intake as `offer-unavailable`, a success. If `/ship` Step 3.5's second ask is skipped (it is still prose), the brief ships green with no issue. That is exactly the pull request 55 pattern this contract exists to stop. Open Question 5's reason, "because `gh` necessarily works at ship time", is stated as fact. It is not: the Step 3.5 gate itself requires `gh` to be available (`skills/ship/SKILL.md:228-230`).
  - **Prior artifact ignored:** `.claude/debug-notes-own-repo-issue-closing.md` Phase 2, pull request 55: "Both asks are prose only"; the contract's own Option C rejection ("the ask is prose with no script check").
  - **Where in this contract:** `## Commands` verdict table, the "`unavailable` with a valid reason → `offer-unavailable`, success" row; `## Open Questions for User` Q5.
  - -> Addressed by: the verdict table now sends `unavailable` with `gh-missing` or `gh-unauthenticated` to `offer-unrecorded`. Only `create-failed` and `no-problem-statement` count as `offer-unavailable`. Q5's wording is corrected, and a matching Failure Mode and test were added.
- **[WARN] The switch and the values it checks against are read from two different files**
  - **What is wrong:** The switch is read only from the conventions file beside the brief. But `offerOutcomeField` / `offerOutcomes` / `offerReasons` and the `verdicts` list are "the other `issueLink` keys", which keep their reading through the shared locator (`verify_issue_link.py:186`). Under a plugin install, a consumer that has turned the switch on but lacks the value lists gets value lists from whichever root the locator picks. The contract never says what happens when the switch is on and the value lists are missing or empty. Failure Modes does not cover it.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-15, "A script that reads a project-owned file must be told which project, not search for one".
  - **Where in this contract:** `## Data Shapes` → "Where the switch is read": "The other `issueLink` keys keep their current reading."; `## Value Objects` row "Recorded-offer requirement".
  - -> Addressed by: the switch, the four offer keys and the `verdicts` list are all read from the one file beside the brief. Switch on with any of them missing or empty halts `unverifiable` / `conventions-missing`, naming the keys (Data Shapes "Where the switch and its value lists are read", Failure Modes, test list).
- **[WARN] The verifier's existing brief fallback can make the "beside the brief" folder a folder the locator chose**
  - **What is wrong:** When a relative `--brief` path does not exist from the current directory, `verify()` replaces it with `work_items_dir() / path.name` (`verify_issue_link.py:722-723`), and `work_items_dir()` goes through the multi-root locator. In that case `<brief>/../../work-item-conventions.json` is a locator-chosen file, which breaks the "never through the shared locator" rule. The contract's ASSUMED entry on brief paths does not mention this code path.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-16, "A 'missing project file' refusal must cover both the unset root and the set-but-absent file" ("never fall through to a multi-root locator").
  - **Where in this contract:** `## Uncertain Assumptions`, the first `ASSUMED` entry; `## Extension Points` item 2, "read the switch from the brief's own `.claude` folder".
  - -> Addressed by: the switch is read only when the brief exists at the path as given. A brief found only through the fallback, with an absent id, halts `unverifiable` with the new cause `brief-path-unresolved`. It never falls through to the locator (Data Shapes, Failure Modes, test list; case 21 stays green).
- **[WARN] The direct read conflicts with the verifier's own INV-12, and the contract does not say so**
  - **What is wrong:** `verify_issue_link.py:46` states "INV-12 Every path resolves through `_claude_paths`." The new exact-path read goes around `_claude_paths` on purpose. The contract lists INV-9 and INV-10 as unchanged but says nothing about INV-12, so the implementer is left to decide whether to break, amend or work around a stated invariant.
  - **Prior artifact ignored:** `MECHANISMS.md` line 42 (Two-layer Claude path resolution).
  - **Where in this contract:** `## Reused Mechanisms`, "INV-10 (no mutation) and INV-9 (missing data fails open, missing resolver fails loud) are unchanged."
  - -> Addressed by: Reused Mechanisms names the one exception and gives the amended INV-12 wording. The handoff requires the verifier's invariant text to be changed in the same pull request.
- **[WARN] What the reason field holds when there is no reason is not declared**
  - **What is wrong:** I-3 says only `unavailable` carries a reason and "Any other value carries no reason". It does not say how "no reason" is written (key absent, empty, `none`), what the brief template writes by default, or whether `declined` plus a non-empty reason counts as recorded or unrecorded. The template default for `issue_offer:` itself is not stated either. This matters because the handoff expects "a template placeholder → offer-unrecorded".
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04, "A VERIFIED parser claim must be tested on the unfilled and the missing case".
  - **Where in this contract:** `## Data Shapes → Entities`, Invariants cell, "**I-3** ... Any other value carries no reason."
  - -> Addressed by: I-3 now says no reason means the key is absent (an empty value reads the same), and `declined` plus a reason counts as recorded with the reason ignored. New I-6 says the template writes `issue_offer: pending` and no reason key, and a leftover placeholder is unrecorded. Tests cover each case.
- **[WARN] `--body-file` only at the new call site breaks the shared wording of the offer**
  - **What is wrong:** Open Question 4 recommends "the same wording as the other two sites", and Reused Mechanisms extends "one mechanism, several call sites". But only `/design-first` is required to use `--body-file`. `/task` (`skills/task/SKILL.md:273`) and `/ship` (`skills/ship/SKILL.md:246`) keep an inline `--body "<problem statement ...>"`. That leaves the wording split three ways, and the Git Bash risk stays open at the two sites that make the offer most often. Both files are already in Files to touch.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-16, "Never let free text start an argument handed to a native program from Git Bash".
  - **Where in this contract:** `## Failure Modes & Mitigations`, "use `--body-file`, never an inline body"; `## Open Questions for User` Q4.
  - -> Addressed by: all three sites (`/task`, `/ship`, `/design-first`) use `gh issue create ... --body-file <path>` in one shared wording (Reused Mechanisms, Extension Points 3-5, Failure Modes, handoff, INV-S7).
- **[WARN] Open Question 4 treats the work item's issue as the contract's Tracking Issue**
  - **What is wrong:** Q4 justifies asking early because "the contract's `**Tracking issue:**` header" can reference the new issue. The registry defines Tracking Issue as the issue that tracks a contract's follow-ups and disclosures. The contract's own Business Concept says it is "a different thing ... not touched here". The question mixes the two meanings in the one place where the user decides.
  - **Prior artifact ignored:** `VOCABULARY.md` line 52, **Tracking Issue**.
  - **Where in this contract:** `## Open Questions for User` Q4, "An early issue lets the branch and the contract's `**Tracking issue:**` header reference it."
  - -> Addressed by: Q4 no longer mentions the Tracking Issue header or the branch. Its only reason is that the issue exists sooner.
- **[NIT] Q4's other reason does not hold** — `/design-first` Step 3.6 runs after approval and requires already being on the delivery branch (`skills/design-first/SKILL.md:249,256`), so the branch name cannot reference an issue created there.
  - -> Addressed by: the branch claim was removed from Q4.
- **[NIT] The decoy test covers one other location, not each one** — the 2026-10-05 journal entry ("A documented 'missing file means the default' must read one named location only") asks for a decoy in each other place: project directory variable, the resolver's own root, the current directory, home. The handoff plants one.
  - -> Addressed by: the test list now plants one decoy per other location (the `CLAUDE_PROJECT_DIR` root, the resolver's own root, the current directory, home), each run separately.
- **[NIT] No test checks that the scaffold matches the shipped keys** — the 2026-10-15 sub-issue contract added scaffold-equals-shipped checks (`test_compose_subissue_title.py:576-595`). This contract mirrors five keys into `plugin_doctor.py` with no matching check, so the two copies can drift.
  - -> Addressed by: a scaffold-equals-shipped test is added. The offer keys, value lists and `verdicts` must match the shipped file, except the switch, which must be `false` in the scaffold.
- **[NIT] Chat Tool Impact uses non-standard wording** — "2. **No.**" is not one of the three sanctioned answers (`No — UI/admin-only with justification`). No boundary is crossed, so this is about the format only.
  - -> Addressed by: Chat Tool Impact now uses the sanctioned "No —" answer with a one-line justification.

### Applicable journal entries

- **2026-10-15 — A script that reads a project-owned file must be told which project, not search for one** — heeded for the switch (Q2, Data Shapes); the value lists still go through the locator, see WARN above.
- **2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file** — heeded by "missing file means off", but the existing brief fallback falls through to the locator, see WARN above.
- **2026-10-05 — A documented "missing file means the default" must read one named location only** — heeded by the exact-path read and the decoy test; one decoy instead of one per location (NIT).
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by the handoff test list (missing field, placeholder, unknown value); the representation of "no reason" is undeclared (WARN).
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by the switch-off backward-compatibility tests backing the README note.
- **2026-10-16 — Never let free text start an argument handed to a native program from Git Bash** — heeded at the new `/design-first` site only; the two existing sites keep inline bodies (WARN).
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by `test_skill_script_lookup.py` in the run list.
- **2026-10-15 — Reuse the existing brief-linkage reader; a second one misses edge cases** — heeded by leaving Step 3.6's `find_linked_brief` lookup unchanged.
- **2026-10-05 — Neutralise every field echoed from untrusted input, not only the body** — not addressed. Not needed, because the reason echoed into pull request notes comes from a closed set and unknown values become `offer-unrecorded`.

### What the critic did not check

- `INTEGRATION.md` and `.claude/.scout-cache/registry-digest.md` do not exist in this worktree; the three registries were read whole. None of them has a project tier, so only Universal entries were checked.
- Adjacent Areas: whether the cross-area scan was run is not checked, because the caller said the main session is adding the scan output itself.
- North-star alignment: `.claude/north-stars/` does not exist, so item 13 produced no findings.
- This critique fills the empty `## Critique` placeholder where the template puts it, rather than adding a second heading at the end of the file.

---

## Lessons referenced

- **2026-10-15 — A script that reads a project-owned file must be told which project, not search for one** — heeded by reading the switch and all offer lists from the one file beside the brief, never through the locator (Data Shapes, Q2).
- **2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file** — heeded by "missing file means off", by switch-on-with-incomplete-lists halting, and by `brief-path-unresolved` instead of a locator fallthrough.
- **2026-10-05 — A documented "missing file means the default" must read one named location only** — heeded by one decoy per other location in the test list.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by I-3 / I-6 and the test list: field missing, placeholder value, empty reason, unknown value.
- **2026-10-16 — Never let free text start an argument handed to a native program from Git Bash** — heeded by `--body-file` at all three call sites.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by putting `test_skill_script_lookup.py` in the handoff run list as a precaution.
- **2026-10-15 — Reuse the existing brief-linkage reader** — heeded by leaving Step 3.6's `find_linked_brief` lookup unchanged.
- Orthogonal to north-stars: none (the register holds no active thought).

---

## Implementation Handoff

### 1. Recorded issue offer outcome, verifier verdicts, skills and version (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/verify_issue_link.py`
- `.claude/scripts/tests/test_verify_issue_link.py`
- `.claude/scripts/tests/test_ship_skill_sync.py`
- `.claude/work-item-conventions.json`
- `.claude/scripts/plugin_doctor.py`
- `skills/task/SKILL.md`
- `skills/ship/SKILL.md`
- `skills/design-first/SKILL.md`
- `README.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`

**Pre-written TASK block:**
```
TASK: Record the outcome of the issue offer in the brief at all three call sites, and make
      verify_issue_link.py halt on an absent id with no recorded outcome when the brief's own
      conventions file turns the switch on.
CONTEXT: concept contract at .claude/concepts/2026-10-16-recorded-issue-offer-outcome.md
FILES: the Files to touch list above
CONSTRAINTS:
  - TDD-first. RED before GREEN in test_verify_issue_link.py (house style: plain script, check()
    accumulator, fixture conventions under a temp dir). Minimum new cases, switch read from the
    conventions file beside the fixture brief:
    switch on + id none + no issue_offer -> offer-unrecorded, halt, exit 2 (this is the test that
      fails before the fix: today it returns not-applicable);
    replay of the pull request 55 brief shape (id none, no field) with the switch on ->
      offer-unrecorded;
    switch on + declined -> offer-declined, issue_link none; declined + a reason -> offer-declined;
    switch on + unavailable + create-failed / no-problem-statement -> offer-unavailable, reason
      echoed;
    switch on + unavailable + gh-missing / gh-unauthenticated -> offer-unrecorded (stale reason);
    switch on + unavailable with no reason key, an empty reason, or an unknown reason ->
      offer-unrecorded;
    switch on + pending / opened / unknown value / a template placeholder -> offer-unrecorded;
    switch on + any one of offerOutcomeField, offerOutcomes, offerReasonField, offerReasons,
      verdicts missing or empty in the beside-brief file -> unverifiable, cause
      conventions-missing, reason names the key (one check per key);
    brief found only through the work_items_dir() fallback + absent id -> unverifiable, cause
      brief-path-unresolved; the same fallback with a number id -> unchanged; a brief found
      nowhere -> not-applicable (case 21 stays green);
    switch off, switch key missing, or no beside-brief file -> not-applicable for every outcome
      (backward compatibility);
    id is a number + any outcome -> unchanged verdicts (I-1);
    decoys: switch on in a file at each other location, run separately (the CLAUDE_PROJECT_DIR
      root, the resolver's own root, the current directory, home), none beside the brief ->
      not-applicable each time;
    scaffold-equals-shipped: plugin_doctor.py's scaffold issueLink has the same offer keys, value
      lists and verdicts as the shipped conventions file, and requireRecordedOffer false (pattern
      of test_compose_subissue_title.py:576-595).
    Update cases 9, 14, 15, 19, 20 for 19 verdicts and the new cause; keep the ordering guard green.
  - Verifier: append the three verdicts after "still-absent"; evaluate them in rule 4's slot only.
    Read the switch, the four offer keys and the verdicts list only from
    <brief path as given>/../../work-item-conventions.json (exact path, no locator), and only when
    the brief exists at the path as given. A missing file, key or non-true switch means off.
    Add brief-path-unresolved to UNVERIFIABLE_CAUSES and REMEDIATION. Keep INV-9 and INV-10.
    Amend the INV-12 text to name the one exception (the beside-brief conventions read for the
    Recorded-offer requirement) and why. The reason names the unrecorded case.
  - Conventions: add requireRecordedOffer true, offerOutcomeField, offerOutcomes, offerReasonField,
    offerReasons and a $comment (where it is read, missing means off, incomplete lists halt,
    copiers set it false unless they want the halt); append the verdicts. Mirror the offer keys
    and the verdicts list into plugin_doctor.py's scaffold with requireRecordedOffer false.
  - Skills: the three call sites write issue_offer per the contract's Extension Points 3-5. The
    brief template writes issue_offer: pending and no reason key. An assumed answer writes
    pending, never declined (I-4). All three use one shared wording with
    gh issue create ... --body-file <path>, never an inline body. /design-first Step 3.6 asks
    (Q4). /ship Step 3.5 asks unless the outcome is declined or unavailable/no-problem-statement
    (Q5). /ship Step 4d table gains the three rows and brief-path-unresolved in the halting
    group; Step 3 Notes line for declined/unavailable. Cite conventions keys by name, never
    restate the value lists.
  - test_ship_skill_sync.py: verdict count 19; add INV-S7 (every offerOutcomes value and the
    field name appear in skills/ship/SKILL.md; skills/task and skills/design-first name the field;
    all three skills use --body-file for gh issue create). Make sure create-failed,
    no-problem-statement and brief-path-unresolved do not trip INV-S2.
  - README.md: in the upgrade note near line 565, say this repository's requireRecordedOffer is
    true, copiers should leave it false unless they want the halt, and turning it on needs the
    offer keys and the verdicts list in their own file.
  - Bump the version 0.9.3 -> 0.9.4 in all five manifest entries.
  - Run test_verify_issue_link.py, test_ship_skill_sync.py, test_plugin_doctor.py,
    test_check_version_bump.py, test_skill_script_lookup.py; all green. Replay /ship Step 4d from
    this worktree and record the brief path passed (Uncertain Assumptions).
  - Do not edit existing briefs. Do not invent new data shapes; the contract is authoritative.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-16-recorded-issue-offer-outcome.md
  contract_status: approved
```

### 2. Scope note on review

There is no separate review sub-task. The change is one mergeable sub-task, and the ordinary `/ship` review applies. The reviewer checks:
- I-1 to I-6.
- The switch and its lists are read from one file beside the brief, with a decoy test per location.
- The `brief-path-unresolved` rule, and the amended INV-12 text.
- The I-4 wording and `--body-file` at all three call sites.
- The README copier note.
- `/ship` on this very brief (id 57) reaches `linked`.

After merge, the reviewer promotes the two vocabulary terms and extends the `issueLink` mention in `MECHANISMS.md` if one is added.

---

## Review checklist (filled in after implementation)

`pr_merged.py` fills this list when the contract's work is merged and nothing is pending. Do not tick lines by hand.

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both backend and frontend sides
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
- [ ] `Status` flipped to `implemented`
