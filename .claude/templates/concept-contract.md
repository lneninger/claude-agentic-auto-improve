# Concept Contract — <TASK NAME>

**Project:** <detected from CWD>
**Date:** <YYYY-MM-DD>
**Requested by:** user
**Status:** draft
**Supersedes:** <optional — path to a prior contract this replaces>

> **Protocol:** filled in by `data-architect`. Implementer agents (`dotnet-backend-architect`, `angular-senior-dev`, `ingestion-data-architect`, `senior-test-engineer`, `ui-ux-designer`) refuse to run unless `Status: approved` or `Status: implemented`. The `concept-gate.py` hook reads `Files to touch` to decide whether Edit/Write/MultiEdit is allowed.
>
> **Lifecycle:**
> - `draft` — data-architect has drafted; user still has Open Questions to resolve. Hook BLOCKS.
> - `approved` — all Open Questions answered; implementer agents can run. Hook ALLOWS matching files.
> - `implemented` — code is live, reviewer has audited. Hook still ALLOWS (kept as historical record).
> - `archived` — obsolete or deprioritized. Hook SKIPS this contract entirely.
> - `superseded` — replaced by another contract (add `Supersedes:` pointing to replacement). Hook SKIPS.
> - `rejected` — user declined after reviewing the draft. Hook SKIPS.
>
> **Management commands:**
> - `/list-contracts` — show all contracts and their statuses
> - `/validate-registries` — check that MECHANISMS.md and VOCABULARY.md references still resolve

---

## Business Concept

- **What is this thing, in domain language?**
  One paragraph. Describe the concept in the user's vocabulary, not implementation terms.

- **Existing VOCABULARY.md terms that apply:**
  List every term from `.claude/registries/VOCABULARY.md` (Universal or Project sections) that is relevant. Link the section header so the reader can jump to the definition.

- **New terms proposed for VOCABULARY.md:**
  For each: the term, the proposed one-paragraph definition, and which tier it belongs in (Universal or Project). If the term is ambiguous, DO NOT guess — move it to Open Questions.

---

## End-User View

> **REQUIRED for any contract whose `Files to touch` includes an Angular UI surface** (component, template, stylesheet, state service, route file, or shared layout). Optional but encouraged otherwise. The data-architect MUST fill this section before flipping `Status` to `approved`. The fullstack-code-reviewer checklist verifies it.
>
> **Tone and structure rules:** read `.claude/references/end-user-view-standard.md`. The short version: plain operator-readable business English; no variable names, no enum identifiers, no route URLs, no code-style conditions, no implementation jargon. Refer to people as the trader, the operator, the team. Refer to screens by their human name. Translate every code-level state, field and flag into the plain-English meaning it represents.
>
> **Category metadata:** the first line of this section MUST be `**Category:** <human group name>` (e.g. `**Category:** AI Workshop`, `**Category:** Strategy Authoring`). The handbook aggregator uses this to place the extracted page in the right group inside the docs portal's User navigation tree.

**Category:** <human group name>

### What the end user sees
One short paragraph. What changes for the trader inside the platform. If the feature is internal-only and the trader never sees it directly, say so explicitly and explain what they will eventually notice as a downstream effect.

### What it does for the end user
One to three short paragraphs. The value the feature provides, expressed in trader terms. A description of the benefit, not of the implementation.

### Connections to the rest of the system
Which other screens, flows, or features this one interacts with — named by their human, user-facing names. How work or data enters this feature and where it leaves.

### Implications
Trade-offs the operator and team inherit as a side effect of how this feature works. Latency, cost, availability windows, requires-network behaviours, manual-step requirements. What this feature implicitly assumes about the rest of the system.

### Measures
Safeguards built into the feature, described in trader-readable terms. Observable signals, guarantees the feature enforces, what it does to protect the trader from foreseeable failure modes.

### How it could be improved
Known follow-ups written so a product manager can prioritise them without reading the engineering plan. A set of acknowledged future improvements that today are accepted limitations — not a roadmap commitment.

---

## Data Shapes

Declare every shape this feature introduces or modifies. No implementation code — just the shape and its meaning.

### Entities

| Name | Fields | Invariants | Ownership (aggregate) |
|------|--------|------------|-----------------------|
|      |        |            |                       |

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
|      |        |         |

### Events

| Name (past tense) | Emitter | Listeners | Payload |
|-------------------|---------|-----------|---------|
|                   |         |           |         |

### Commands (if any)

| Name (imperative) | Handler | Payload | Possible rejections |
|-------------------|---------|---------|---------------------|
|                   |         |         |                     |

---

## Reused Mechanisms

Every entry from `.claude/registries/MECHANISMS.md` this task leans on. No exceptions — if you are not reusing at least one mechanism, you have not looked hard enough.

For each: `<mechanism name>` — **extended by `<X>`** OR **consumed as-is**.

**Validation rule for "consumed as-is":** trace the data flow from this feature's entry point through the mechanism down to its persistence layer. Check:
1. **Identity boundary** — Does the actor identity in this feature (e.g. AdminUser) match what the mechanism's persistence layer assumes (e.g. FK to Users table)? If the mechanism was built for one identity type and this feature introduces a different one, that is NOT "consumed as-is" — it requires a schema change.
2. **FK constraints** — Read the `IEntityTypeConfiguration` for every entity the mechanism persists. Will the new feature's data satisfy all FK constraints?
3. **Enum coverage** — If the mechanism uses an enum (e.g. `AuditAction`, `DataCapability`), does it already have a value for this feature's operations, or does the enum need extending?

If any check fails, document the required change in Extension Points — do NOT mark the mechanism as "consumed as-is".

Example:
- `IConditionEvaluator + ContextResolver` — consumed as-is; new field resolver plugs in without changing the evaluator.
- `MarketElements` — extended by new field key `position.trailing_stop_peak`.
- `IAuditLog` — consumed as-is. **Persistence check:** `AuditLogEntity.UserId` has no FK constraint, so AdminUser actor IDs are accepted. `AuditAction` enum already has `Create`, `Update`, `Delete`, `ResetPassword` — all required values exist.

---

## New Mechanisms (if any)

**Default: none.** Creating a new mechanism is the exception, not the rule. For every entry here you MUST justify why an existing mechanism could not be extended.

For each:

- **Name:**
- **Purpose:**
- **Why an existing mechanism was not sufficient:** (REQUIRED — missing = contract rejected)
- **Proposed location:** (layer + folder)
- **Extension seam:** (how future features will plug into this new mechanism)
- **Will this be promoted to `MECHANISMS.md` after implementation?** yes / no / decide-at-review

---

## Extension Points

Where does this plug into existing pipelines? Be specific — DI registrations, job map entries, resolver lists, route table entries, SignalR hub methods, etc.

Example:
- Register `TrailingStopEvaluator` in `Program.cs` alongside existing evaluators.
- Add `TrailingStopResolver` to the resolver list consumed by `ContextResolver`.
- Add `position.trailing_stop_peak` to the `MarketElements` declaration.

---

## Integration Surfaces

Which existing modules does this feature communicate with across layer/project boundaries? Cross-reference `.claude/registries/INTEGRATION.md` for the full surface map and named integration flows.

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| (e.g. FlowManager) | (e.g. StrategyRunState) | SignalR FlowUpdate | StrategyFlow | backend → frontend |

**Changes to existing integration surfaces** (DTO shape changes, new SignalR events, new/changed API endpoints):
- [ ] List each change with the affected file on BOTH sides (C# + TypeScript)

If this feature does not cross module boundaries, write: `Not applicable. Reason: feature is contained within a single layer.`

---

## Acknowledged conflict with north-star (OPTIONAL — only when applicable)

> **Fill this section ONLY when the contract introduces an anti-pattern declared by an `active` north-star at `.claude/north-stars/`.**
> `data-architect` Step 0.5 surfaces the conflict; the user accepts the conflict by approving the contract with this section populated. `contract-critic` checklist item 13 BLOCKS the contract when the conflict exists but this section is missing.

| North-star slug | Anti-pattern triggered | Why we're accepting the conflict |
|-----------------|------------------------|----------------------------------|
| (e.g. no-local-filesystem) | (e.g. Writes a temp scratch file at `python/cache/`) | (e.g. Required as a CI-only debugging artifact; will be removed in follow-up `<slug>` before any production deploy.) |

If the contract does NOT conflict with any active north-star, OMIT this section entirely (do not write "Not applicable" — the section's presence is itself the BLOCKER trigger).

---

## Adjacent Areas

> **Filled by `data-architect` during Step 4.5 (cross-area scan). Verified by `contract-critic` checklist item 11.**
>
> List the top 3 adjacent areas (from `.claude/area-mapping.json`) that the cross-area scanner surfaced for this contract, plus any the architect noticed on their own. For each area, declare exactly one of:
>
> - **in-scope** — files in this area appear in `## Implementation Handoff → Files to touch`.
> - **follow-up handle** — out of scope for this contract; a deferred-improvement stub has been written at `.claude/concepts/followups/<date>-<slug>.followup.md`. Cite the stub path in the Handle column.
> - **not applicable** — the scanner flagged this area but it does not apply. One-sentence reason required, citing a MECHANISMS.md line or a JOURNAL.md entry (`Tags:` or title match). Bare "doesn't apply" is rejected by the critic as NIT.
>
> If the scanner returned zero adjacent areas above threshold, write the single line: `Not applicable. Reason: cross-area scan returned no signal above the threshold.`

| Area | Decision | Implication / Reason | Handle |
|------|----------|----------------------|--------|
| (e.g. signalr-hub) | follow-up handle | Ingestion job emits new event; admin dashboard should subscribe. | `.claude/concepts/followups/2026-XX-XX-admin-dashboard-subscribe.followup.md` |

---

## UI Implications

> **REQUIRED whenever `## Integration Surfaces` lists ANY entry with a frontend consumer (file under `ClientApp/projects/...` OR a DTO referenced in INTEGRATION.md's frontend section). Verified by `contract-critic` checklist item 12.**
>
> Either enumerate the UI changes OR explicitly mark UI work out of scope with a follow-up handle. Empty "no changes needed" prose is not acceptable.

**Enumeration form** (fill when UI work IS in scope):

| App | Surface affected | Change | Theme/density note |
|-----|------------------|--------|--------------------|
| (e.g. admin-panel) | RemediationStepButton | New `target` enum value rendered as a button | Dark theme — use `text-on-surface` not `text-neutral-700` |
| (e.g. scalping-machine) | StrategyCenterBlade | New status badge color | Light theme — use `text-primary` on `bg-primary/8` |

**Out-of-scope form** (fill when UI work is deferred):

`Out of scope. Follow-up handle: .claude/concepts/followups/<date>-<slug>.followup.md (Status: stub)`

If this contract has no frontend consumer in Integration Surfaces, write: `Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.`

---

## Chat Tool Impact (REQUIRED when this contract adds or changes a REST endpoint or SignalR event)

A REST endpoint / SignalR event does NOT automatically get a chat-tool wrapper — the LLM tool surface is a separate deliberate extension. This section forces the decision to be explicit so the next `/retrain-llm` cycle does not invent a tool shape to fill a silent gap.

**Answer one of the three:**

1. **Yes — this contract adds a chat tool.** Declare the tool schema here:
   - **Tool name** (snake_case, globally unique across `ChatToolDefinitions.cs`):
   - **Arguments** (each field must map 1:1 to the backend request DTO; `format: "uuid"` for GUIDs; enums as `enum: ["Live", "Shadow"]` PascalCase strings matching `JsonStringEnumConverter` on the wire):
   - **Tool-result JSON shape** (narrow — matching `create_strategy`/`update_strategy` precedent; NOT the full domain object):
   - **Executor dispatch target** (`IXxxService.YyyAsync` — prefer a service seam so controller + executor share one orchestration path; see `feedback_service_layer_cannot_leak_exception_message_to_chat.md` for error-handling rules):
   - **System-prompt announcement prose** (draft the paragraph that will land in `SystemPromptBuilder.cs`; include Live/Shadow defaults and any Phase-constrained semantics).
   - **Sentinel files to touch** (always these three for a new chat tool): `src/ScalpingMachine.Services/Chat/ChatToolDefinitions.cs`, `ChatToolExecutor.cs`, `SystemPromptBuilder.cs`. These trigger `/retrain-llm`.

2. **No — this endpoint/event is UI-only or admin-only.** One-line justification (e.g. "admin-only surface — chat would bypass row-level auth", "UI-only destructive mutation where a typed chat call would be unsafe").

3. **Deferred to a follow-up mini-phase.** Name the follow-up contract or todo item. The current contract MUST NOT ship synthetic training examples that invoke a non-existent tool — the `llm-training-engineer` is instructed to refuse data generation when this section is absent or set to "Deferred".

**Why this section exists:** Phase A2 Strategy Learner (2026-04-21) added `POST /api/strategy-runs/{strategyId}/start-pair` + `runPairUpdate` SignalR event but OMITTED this section. The subsequent `/retrain-llm` cycle filled the gap by inventing a tool shape, producing adapter `5d9acc15` that would confidently hallucinate a non-existent API contract (`create_strategy` with `action: "start_pair"`). The adapter was archived DO NOT DEPLOY after `llm-contract-reviewer` audit. A separate mini-phase (`2026-04-23-a2-chat-tools-start-run-pair`) had to be written to properly add the `start_run_pair` tool. This section makes that class of omission impossible for future contracts.

---

## Non-Goals

Explicit list of what this contract does NOT cover. Anything not listed here and not implied by the Data Shapes is out of scope. This protects against scope creep during implementation.

---

## Confidence

One line. The data-architect's honest self-assessment of this contract's solidity.

**Format:** `Confidence: <High|Medium|Low>. <one-line breakdown of where confidence is strong vs weak>`

**Example:** `Confidence: Medium. High on Data Shapes (verified against existing entities); Medium on Extension Points (assumed Quartz schedule tolerance < 1s but did not verify); Low on external provider quota impact (depends on live traffic patterns).`

If Confidence is Low, the Open Questions section must include a question that, when answered, would raise it to Medium or High.

---

## Alternatives Considered & Why Rejected

Forces externalizing the decision tree instead of defending a single path post-hoc. Minimum **one** rejected alternative with a concrete reason. Bare "I considered X but chose Y" is not enough — explain the tradeoff in one sentence.

- **Option A (chosen):** <1-line description of the selected approach>
  - Why: <1-line reason it wins>
- **Option B (rejected):** <1-line description>
  - Why rejected: <concrete tradeoff — performance, reuse, complexity, FK constraints, enum coverage, etc.>
- **Option C (rejected):** <1-line description>
  - Why rejected: <concrete tradeoff>

If the task has a genuinely narrow design space (e.g., a pure rename), state so explicitly: `Task scope forces exactly one approach because <reason>. Considered doing nothing — rejected because <reason>.` Zero alternatives is not acceptable.

---

## Uncertain Assumptions

Agent-internal uncertainty, **distinct from user-facing Open Questions**. This section captures what the data-architect guessed vs. what it verified. Reviewers and implementer agents target this section first, and any entry tagged `ASSUMED` is fair game for the implementer to flip to `VERIFIED` (or to emit an `AMENDMENT:` block on the contract if the assumption turns out to be wrong).

**Format:**

- `ASSUMED`: <statement>. <why it matters if wrong>. Verification path: <what would confirm it>.
- `VERIFIED via <source>`: <statement>. <file:line citation or MECHANISMS.md reference>.
- `VERIFIED via context7:<library>@<version>`: <statement>. <context7 query or doc section>.

**Example:**

- `ASSUMED`: Quartz job schedule tolerance is under 1s drift. Matters because scheduling accuracy > 1s would need dedicated retry logic. Verification path: read `QuartzConfig.cs` or run a timing test.
- `VERIFIED via src/Persistence/Configuration/AuditLogConfiguration.cs:34`: `IAuditLog.UserId` column is nullable.
- `VERIFIED via context7:@angular/material@21`: `MatSnackBar.open(message, action, config)` still accepts `duration` in `config`; signature unchanged from v20.

Empty is not acceptable — if you truly verified everything, list the primary verification sources as `VERIFIED`.

---

## Failure Modes & Mitigations

Pre-commit failure analysis, not postmortem. What could go wrong, and what prevents it. Each failure mode gets a one-line mitigation — **cite an existing mechanism from MECHANISMS.md where possible** (reuse > invention).

**Format:**

- **FM:** <1-line failure description>
  - **Mitigation:** <what prevents it — cite MECHANISMS.md entry if applicable>
- **FM:** <1-line failure description>
  - **Mitigation:** <what prevents it>

**Example:**

- **FM:** Peak resets on restart (ASSUMED in Uncertain Assumptions).
  - **Mitigation:** Persist in `StrategyRunState` snapshot — reuses the existing `Startup Task Runner` mechanism from MECHANISMS.md.
- **FM:** Stale peak when a symbol is renamed mid-run.
  - **Mitigation:** Key by `instrumentId`, not ticker symbol — ticker is a display field only.
- **FM:** Race between close-eval and peak-update.
  - **Mitigation:** Single-writer lock already in `OpenPositionLock` mechanism (MECHANISMS.md → Universal Patterns).

If no failure modes apply (e.g., pure doc change), state so explicitly: `No failure modes — change is <reason, e.g., documentation-only, no runtime impact>.`

---

## Open Questions for User

Must be resolved before `Status` flips to `approved`. Each question must be answerable without forcing the user to read code.

- [ ] Question 1 — context + options + a recommendation.
- [ ] Question 2 — ...

---

## Critique

> **Filled by `contract-critic` during `/design-first` Step 4.5, AFTER the data-architect drafts this contract and BEFORE the user reviews it.** The data-architect leaves this section empty. The critic reads MECHANISMS.md / VOCABULARY.md / INTEGRATION.md / JOURNAL.md and appends BLOCKER / WARN / NIT findings here so the user sees them alongside Open Questions.
>
> **The critic is advisory.** The user remains the approval gate — Status flips to `approved` only after the user reviews both Open Questions AND critique findings. User-confirmed findings become entries in `.claude/registries/JOURNAL.md` automatically (Trigger: `pre-approval critic`) so the same defect class is caught on future contracts.
>
> **Format produced by the critic** (do not pre-fill):
> ```
> **Critic:** contract-critic
> **Date:** YYYY-MM-DD
> **Verdict:** blockers-found | warnings-only | clean
>
> ### Findings
> - **[BLOCKER] <summary>** — What is wrong / Prior artifact ignored / Where in this contract
> - **[WARN] <summary>** — same shape
> - **[NIT] <summary>** — one-line context
>
> ### Applicable journal entries
> - **<YYYY-MM-DD — entry title>** — heeded by `<section>` | violated | not addressed
> ```

---

## Lessons referenced

> **Filled by `data-architect` during Step 4.** List every `.claude/registries/JOURNAL.md` entry (Universal or matching project) whose `Apply when:` pattern matched this contract and whose lesson influenced a design decision. Empty if no entries applied. This section is what makes the journal a living checklist — without it, lessons stay invisible.

- **<YYYY-MM-DD — journal entry title>** — heeded by `<section / decision in this contract>`. Cross-reference: `.claude/registries/JOURNAL.md` § `<Universal lessons | Project: <name>>`.

If no journal entries applied, write: `No applicable lessons in JOURNAL.md at draft time.`

---

## Implementation Handoff

Once `Status: approved`, the main session dispatches the following handoffs. The `Files to touch` list is authoritative — the `concept-gate.py` hook uses it to allow/block Edit and Write calls.

### Backend (`dotnet-backend-architect`)

**Files to touch:**
- `path/to/file1.cs`
- `path/to/file2.cs`

**Pre-written TASK block:**
```
TASK: <exact task description>
CONTEXT: concept contract at .claude/concepts/<this-file>.md
LAYER: <Domain | Strategy | Services | Persistence | API>
FILES: <list>
CONSTRAINTS:
  - follow reused mechanisms listed in the contract
  - do NOT invent new data shapes — the contract is authoritative
PRIOR_FINDINGS:
  contract_path: .claude/concepts/<this-file>.md
  contract_status: approved
```

### Frontend (`angular-senior-dev`)

**Files to touch:**
- `ClientApp/projects/<app>/src/app/...`

**Pre-written TASK block:**
```
TASK: <exact task description>
CONTEXT: concept contract at .claude/concepts/<this-file>.md
FILES: <list>
CONSTRAINTS:
  - reuse signal state pattern and existing state services
  - no *ngIf/*ngFor; use @if/@for with track
  - do NOT invent new models — match the Data Shapes section exactly
PRIOR_FINDINGS:
  contract_path: .claude/concepts/<this-file>.md
  contract_status: approved
```

### Data pipeline (`ingestion-data-architect`) — if applicable

**Files to touch:**
- `src/ScalpingMachine.Services/Ingestion/...`

**Pre-written TASK block:**
```
TASK: <exact task description>
CONTEXT: concept contract at .claude/concepts/<this-file>.md
FILES: <list>
CONSTRAINTS:
  - all external calls MUST route through IExternalDataDispatcher
  - add DataCapability enum value if the data type is new
PRIOR_FINDINGS:
  contract_path: .claude/concepts/<this-file>.md
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
