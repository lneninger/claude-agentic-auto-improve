# End-User View — tone and structure standard

Authoritative rules for the `## End-User View` section of a concept contract.

**Why this section is special.** It is the only part of a concept contract that ships verbatim to
people who are not engineers. The handbook aggregator extracts it into the docs portal's **User**
group, and the in-screen help drawer renders it to the trader. Drift here propagates directly into
trader-facing documentation — which is why `fullstack-code-reviewer` grades a non-compliant section
`[CRITICAL]` and `contract-critic` grades a missing one `BLOCKER`.

> **Provenance.** Reconstructed on 2026-08-25 from the specification already carried by its
> consumers: `data-architect.md` §8 and Step-4 item 2, `contract-critic.md` check 9,
> `fullstack-code-reviewer.md` End-User View audit, and `.claude/templates/concept-contract.md`.
> This file documents the existing standard; it does not introduce new rules.

---

## When it is required

**REQUIRED** when the contract's `Implementation Handoff → Files to touch` includes **any** Angular
UI surface:

- a component (`*.component.ts`)
- a template (`*.component.html`)
- a stylesheet (`*.component.scss`)
- a signal state service (`core/state/*.state.ts`)
- a route file
- a shared layout

Optional but encouraged otherwise. `data-architect` must **refuse to flip `Status` to `approved`**
without it. A draft missing the section, or carrying placeholder text, returns to the user as
`draft` with an Open Question demanding the content.

If the feature is internal-only and the trader never sees it directly, the section is still
written — say so explicitly and explain what they will eventually notice as a downstream effect.

## Structure — fixed, in order

The section is titled `## End-User View` and sits **directly after Business Concept**.

The first non-heading line is the category metadata:

```
**Category:** <human group name>
```

Examples: `**Category:** AI Workshop`, `**Category:** Strategy Authoring`. The handbook aggregator
uses this to place the extracted page in the right group of the docs portal's User navigation tree.
A missing or non-human category misfiles the page.

Then **six sub-sections, all present, in this exact order**:

### 1. What the end user sees
One short paragraph. What changes for the trader inside the platform.

### 2. What it does for the end user
One to three short paragraphs. The value the feature provides, expressed in trader terms. A
description of the **benefit**, not of the implementation.

### 3. Connections to the rest of the system
Which other screens, flows or features this one interacts with — named by their human, user-facing
names. How work or data enters this feature and where it leaves.

### 4. Implications
Trade-offs the operator and team inherit as a side effect of how this feature works. Latency, cost,
availability windows, requires-network behaviours, manual-step requirements. What this feature
implicitly assumes about the rest of the system.

### 5. Measures
Safeguards built into the feature, described in trader-readable terms. Observable signals,
guarantees the feature enforces, what it does to protect the trader from foreseeable failure modes.

### 6. How it could be improved
Known follow-ups written so a product manager can prioritise them without reading the engineering
plan. Acknowledged future improvements that are accepted limitations today — **not** a roadmap
commitment.

## Tone rules

Plain operator-readable business English throughout.

**Refer to people as** the trader, the operator, the team.
**Never as** the user, the actor, the principal, the subject, the caller, the client.

**Refer to screens by their human name** — "the Shadow Mode screen", never `/ai/shadow` and never
`ModelTestingShadowComponent`.

**Translate every code-level state, field and flag into the plain-English meaning it represents.**
A status enum becomes what that status means to a trader. A boolean flag becomes the condition it
describes.

## Banned content

Any of these makes the section non-compliant:

| Banned | Examples |
|---|---|
| Variable / type / enum identifiers | `isAuthoritative`, `StrategyStatus.Paused`, `RecordingSegment` |
| Table and column names | `StockFundamentals`, `provider_call_log` |
| Property names in prose | camelCase, PascalCase or `snake_case` tokens that look like code |
| Route URLs | `/ai/shadow`, `/docs/api` |
| Component class names | `ModelTestingShadowComponent` |
| Code-style conditions | "when status equals X", "if isAuthoritative is true" |
| Implementation jargon | IDs, rows, foreign keys, transactions, optimistic updates, polling, push channels, debouncing, atomic swaps, soft-deletes, append-only stores, GUIDs, payloads, DTOs |

## Worked contrast

**Non-compliant** — identifiers, a route, a code-style condition, implementation jargon:

> When `RecordingSession.status` is `Capturing`, the user navigates to `/recordings` and the
> `RecordingListComponent` polls the hub every 2s, doing an optimistic update of the row before the
> DTO round-trips.

**Compliant** — same behaviour, trader-readable:

> While a capture is running, the trader can open the Recordings screen and watch it progress in
> near real time. The list updates itself without the trader refreshing, and a capture that has
> just started appears immediately rather than after a delay.

## Audit checklist

`fullstack-code-reviewer` runs this. A gap is `[CRITICAL]`; `contract-critic` treats it as a
`BLOCKER` pre-approval.

- [ ] Section present, titled `## End-User View`, directly after Business Concept
- [ ] First non-heading line is `**Category:** <human group name>`
- [ ] All six sub-sections present, in order
- [ ] No code identifiers — grep for camelCase, PascalCase, `snake_case`
- [ ] No route URLs, no component class names
- [ ] No code-style conditions
- [ ] No implementation jargon
- [ ] People referred to as the trader, the operator, the team
- [ ] **Implementation matches the section** — what shipped matches what the section promises. A
      divergence means either the section needs updating or the implementation needs correcting.
