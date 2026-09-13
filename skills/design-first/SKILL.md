---
name: design-first
description: "Kick off the Data-First Engineering Protocol for any non-trivial task. Classifies the task, invokes the data-architect to produce a concept contract at .claude/concepts/, resolves Open Questions with the user, and hands off to implementer agents with the contract as their authoritative input. Use when: user says /design-first, 'design this feature', 'start a new feature', or is about to request any non-trivial implementation. The concept-gate.py hook will block Edit/Write without an approved contract, so this skill is the entry point."
user_invocable: true
---

# /design-first — Data-First Engineering Protocol

When this skill is invoked, execute the following steps. This is the ONLY correct entry point for non-trivial tasks when the `concept-gate.py` hook is active.

## Step 0: Read the protocol

Before anything else, remember:

1. **Business concept first, code last.** Data shapes and mechanism reuse are decided before any file is edited.
2. **Reuse is the default, creation is the exception.** The data-architect MUST extend existing mechanisms from `.claude/registries/MECHANISMS.md` unless an explicit justification is written.
3. **Communication gate.** The contract is presented to the user and Open Questions resolved BEFORE implementer agents are invoked.
4. **Hard block.** `~/.claude/hooks/concept-gate.py` blocks Edit/Write on non-trivial files without an approved contract.

## Step 1: Classify the task

Decide whether the task is **trivial** or **non-trivial**.

**Trivial tasks (bypass the protocol — go straight to the implementer agent or edit directly):**

- Single-line or single-file typo, formatting, or comment fix
- Adding a log line or null-check to existing code
- Adding an XML doc or JSDoc comment
- Config bump (`appsettings.json`, `package.json`, `.env`)
- Pure rename of a symbol without semantic change
- Editing files under `.claude/` or `~/.claude/` themselves
- Bug fix limited to one branch of a conditional in one function

**Non-trivial tasks (proceed with the protocol — ALL of the rest):**

- Any new feature, no matter how small
- Any new entity, service, component, controller, or endpoint
- Any new data shape, field, or migration
- Any refactor that touches more than one file structurally
- Any change that introduces or modifies a reusable mechanism

If you are unsure — treat it as non-trivial. The cost of writing a short contract is far lower than the cost of inventing a parallel data shape.

**If trivial:** announce the classification, invoke the relevant implementer agent with a plain TASK block (no contract), let the hook's trivial-file allowlist handle it.

**If non-trivial:** continue to Step 2.

## Step 2: Invoke the data-architect

Launch the `data-architect` agent via the Agent tool with this TASK block:

```
TASK: <the user's request, verbatim>
CONTEXT: <any additional context from the session>
CWD: <current working directory — used to detect project>
FILES: <files the user mentioned, if any>
PRIOR_AGENT: none
PRIOR_FINDINGS:
  registry_digest: .claude/.scout-cache/registry-digest.md
  mechanisms_registry: .claude/registries/MECHANISMS.md
  vocabulary_registry: .claude/registries/VOCABULARY.md
  contract_template: .claude/templates/concept-contract.md
```

The data-architect will read the registry-scout digest first (< 15K tokens) for a high-level overview, then selectively drill down into domain-specific registry files as needed. The architect will read relevant code (read-only) and produce a concept contract file at `.claude/concepts/<YYYY-MM-DD>-<slug>.md` with `Status: draft`. The `## Critique` section is left empty for Step 2.5; the `## Lessons referenced` section is filled by the architect if any JOURNAL.md entries applied.

## Step 2.5: Critique the draft

### Step 2.5a — Skip-eligibility check (accuracy system)

Before spawning the critic, consult the accuracy-skip state. Areas that have demonstrated a perfect track record (clean_streak >= 5) MAY skip the critic; everything else MUST run it.

Run the bucket derivation:

```bash
py -3 .claude/scripts/derive_area.py "<contract-path-from-step-2>"
```

The output is one bucket per line. Three outcomes:

1. **Empty output** (no `Files to touch` section parsed) → run the critic. Log reason `no-files-to-touch-section`.
2. **Output contains `uncategorized`** → run the critic. Log reason `uncategorized-area`. (Add a pattern to `.claude/area-mapping.json` if this contract represents a recurring kind of work.)
3. **One or more named buckets** → for each bucket, run `py -3 .claude/scripts/accuracy_update.py query <bucket>` and inspect the `skip_eligible` field. **Skip is offered only when ALL buckets return `skip_eligible: true`.** Any cold or recently-failed bucket forces the critic to run.

If the env var `CLAUDE_CONTRACT_SKIP=off` is set, skip the entire skip-eligibility check and run the critic unconditionally. This is the user's escape hatch.

If skip is **not** eligible, print the reason (each bucket's `clean_streak: N/5` and `last_verdict`) one line each, then proceed to Step 2.5b unconditionally. The transparency matters — the user must see why they're paying the critic cost so they can decide whether to ramp accuracy by writing more contracts in that area.

If skip **is** eligible, present this `AskUserQuestion`:

> *"All buckets demonstrate a perfect streak (≥5 clean critic verdicts). Skip contract-critic for this draft? [buckets: bucket-a 7/5, bucket-b 5/5]"*  
> Options: **Skip** (default) · **Run anyway**

**If the user picks Run anyway:** proceed to Step 2.5b as if not eligible. The verdict-tracker hook will record the resulting verdict normally.

**If the user picks Skip (or defaults):**

1. Append a `## Critique` stub to the contract via `Edit`:
   ```markdown

   ---

   ## Critique

   **Critic:** skipped-by-accuracy-system
   **Date:** <today YYYY-MM-DD>
   **Verdict:** skipped
   **Buckets:** <bucket-a 7/5>, <bucket-b 5/5>, ...
   **Override:** set CLAUDE_CONTRACT_SKIP=off or run /critique-now <contract-path>

   ### Findings
   - (skipped — buckets demonstrated N>=5 clean streak)
   ```

2. **Do NOT call `accuracy_update.py record-clean`.** Skips are non-counting — counting them would let a single clean run perpetually re-skip itself (bootstrap-gaming the threshold). Streak progress requires evidence from the actual critic. The verdict-tracker hook recognizes `Verdict: skipped` and is a no-op.

3. Skip ahead to **Step 3** — the contract is ready for user review with no findings beyond the stub.

### Step 2.5b — Spawn contract-critic

(Reached when skip is ineligible OR the user picked "Run anyway".)

Launch the `contract-critic` agent via the Agent tool with this TASK block:

```
TASK: critique the draft contract
CONTEXT: invoked by /design-first Step 2.5 after data-architect wrote the draft
CWD: <current working directory>
PRIOR_AGENT: data-architect
PRIOR_FINDINGS:
  contract_path: <full path returned by data-architect in Step 2>
  contract_status: draft
```

The critic reads the contract plus MECHANISMS.md / VOCABULARY.md / INTEGRATION.md / JOURNAL.md (both tiers), applies its adversarial checklist (reuse drift, vocabulary drift, hidden Open Questions, integration-surface omissions, journal-lesson applicability, End-User View completeness, etc.) and **appends a `## Critique` section to the contract file** with BLOCKER / WARN / NIT findings.

The critic is **advisory** — it does NOT flip `Status` and does NOT block the workflow. Its only output is the appended `## Critique` section plus a HANDOFF summary. Do NOT proceed to Step 3 until the critic returns.

If the critic reports `verdict: blockers-found`, surface that prominently when presenting the contract in Step 3. The user may either address the BLOCKERs (recommended) or explicitly acknowledge them and proceed anyway. Either choice is valid — the journal append in Step 3 captures the outcome.

### Why the failure-reset rule exists

The accuracy-skip system (Step 2.5a) trusts only **evidence** — a chain of clean critic verdicts in the same sentinel-path bucket. The 2026-05-17 AI-Workshop-Eval-Runs contract was drafted with `verdict: confident` and the critic still produced 5 WARN findings (vocabulary drift, conditional file lists, an unresolved Open Question masquerading as a decision, an INTEGRATION.md target section that did not exist, and a precedent violation). The data-architect's own confidence rating is **not** evidence the draft is clean.

That incident is why ANY post-approval failure signal — user rejection, `fullstack-code-reviewer` divergence, a `/critique-now` BLOCKER, or a JOURNAL.md entry with `Trigger: post-approval` / `post-impl divergence` — instantly resets the bucket's `clean_streak` to 0 and re-mandates the critic for the next contract in that area. The system rewards proven areas, not first contracts, and it discards trust the moment evidence contradicts it.

**Session-context-isolation principle:** the data-architect's reasoning primes its own self-review. Only a fresh agent instance, spawned via the `Agent` tool with a cold context, performs independent critique. Inline critique by the main orchestrator session does **not** satisfy this step.

## Step 3: Present the contract and resolve Open Questions

Read the contract file. Show the user:

1. The one-paragraph summary from the data-architect's HANDOFF
2. The Business Concept section
3. The Data Shapes section (tables)
4. The list of Reused Mechanisms
5. The list of New Mechanisms, if any (with justifications)
6. The `## Critique` section findings (BLOCKER / WARN / NIT) with severity counts up front
7. The `## Lessons referenced` section (which JOURNAL.md entries the architect heeded)
8. The Open Questions — each with a recommendation from the data-architect

Use the `AskUserQuestion` tool to resolve each Open Question AND to walk the user through every BLOCKER and WARN from the `## Critique` section. Phrase critique questions as: *"The critic flagged this as `<BLOCKER|WARN>`: `<summary>`. Address it (how?), defer it (note your reasoning), or reject the finding (why)?"* Do NOT guess answers. Do NOT flip `Status` to `approved` until every Open Question has a documented answer AND every BLOCKER has an explicit user response.

For each critic finding the user **agrees with and addresses** (or agrees with and defers with justification), append a corresponding entry to `.claude/registries/JOURNAL.md` under the matching project section using this shape:

```markdown
### YYYY-MM-DD — <Finding summary distilled into one-line title>
- **Trigger:** pre-approval critic
- **Source contract:** <full contract path>
- **Lesson:** <one-line actionable — `Do X` / `Avoid Y when Z`>
- **Apply when:** <pattern future critic should match against — copy from the finding's "Prior artifact ignored" or derive from "What is wrong">
- **Tags:** <2-5 grep-friendly keywords>
```

Findings the user **rejects** are NOT logged — the user's rejection is recorded inline in the contract (under the relevant Open Question or as a one-line note appended to the relevant `## Critique` finding bullet) so future readers see the decision trail. The `/journal-add` skill is the manual escape hatch if the user later changes their mind.

### Contract-level rejection (accuracy-skip bad-plan signal)

If, during Step 3, the user expresses **contract-level** rejection — not a single-finding disagreement, but rejection of the design as a whole — treat it as a bad-plan signal. Rejection-phrase keywords to watch for (case-insensitive, whole-message scan):

- "reject this plan" / "reject the plan" / "reject this contract" / "reject the contract"
- "this contract is wrong" / "this plan is wrong" / "this design is wrong"
- "redesign this" / "redesign the contract" / "redo this"
- "start over" / "scrap this" / "discard this contract"

On match (or any clearly equivalent intent):

1. Confirm once via `AskUserQuestion`: *"Treat this as a full rejection of the contract? (Status will be flipped to `rejected`, accuracy-skip clean_streak resets for every bucket this contract touched.)"* — Yes / No / Address-specific-finding-instead.
2. On confirmed Yes: `Edit` the contract to flip `Status: draft` (or `approved`, if it had been flipped already in this session) → `Status: rejected`. The `contract-status-watcher.py` PostToolUse hook detects the transition and calls `accuracy_update.py record-failure` for every derived area with source `rejection`.
3. Stop the workflow. Do NOT proceed to Step 4. Suggest the user start a new `/design-first` cycle with the lessons they learned from this draft.

Do NOT auto-trigger on isolated words ("wrong", "bad", "no") — false positives are worse than misses here. The keyword scan only fires on the full phrases above.

Once all Open Questions are answered AND all critique findings have explicit user responses (addressed / deferred / rejected), edit the contract file to:
- Append the user's answers under each Open Question
- Append `→ Addressed by: <one line>` / `→ Deferred: <reason>` / `→ Rejected: <reason>` directly under each `[BLOCKER]` and `[WARN]` finding in the `## Critique` section
- Flip `Status: draft` → `Status: approved`

## Step 3.5: Offer orchestration for autonomous execution

> ### GATE — do not offer Option A. The orchestrator does not work.
>
> Its two load-bearing pieces are unimplemented stubs, and it reports success anyway.
> Skip the choice entirely and go straight to Step 4. Say in one line that an autonomous
> path exists but is gated as unimplemented. Do not put a choice to the user when only one
> option is available.
> Verified 2026-09-13 by reading the code and running the suite.
>
> - `.claude/scripts/orchestrator_task_planner.py` — `_load_contract` returns a hardcoded
>   dictionary holding an empty task list, instead of parsing the contract markdown.
>   `plan_tasks` returns nothing. A contract therefore yields zero tasks.
> - `.claude/scripts/task_executor_launcher.py` — `_spawn_claude_session` has its real call
>   commented out. It touches a marker file and returns true. `_collect_result` then finds no
>   result file, falls through to a fallback, and reports the task completed with tests
>   passed. The commit it cites is whatever the worktree was already sitting on.
>
> Nothing is planned, nothing is executed, and the run still reports a passing final review.
> This is silent success, which is worse than a crash: every gate reports green.
>
> The suite at `.claude/orchestrator/tests/test_orchestration_system.py` does not catch it.
> It assigns `orchestrator.task_map` directly and never calls `plan_tasks`, so the planner
> stub is never exercised. Thirteen tests pass in about a fifth of a second.
>
> **Lift this gate only when both stubs are real, and a test proves a task's work actually
> landed** — a commit the orchestrator did not invent. A positive control is required here:
> a task that fails must make the run fail. Until then, everything below is a design record,
> not a runnable path.
>
> Five further defects, found 2026-09-13 in the consuming project and recorded here so the
> gate carries the whole picture. Any one of them would break a run on its own:
>
> - `task_executor_launcher.py` passes three arguments, in a different order, to the
>   `TaskExecutionPacketGenerator` constructor, which declares four. Every task would raise
>   a type error before doing anything.
> - `_wait_for_architect` in `orchestrator_loop.py` blocks on Python's `input`, and the
>   agent dispatch beside it is commented out. An unattended run cannot answer it.
> - `_merge_to_master` checks out the default branch and merges with no working directory
>   set, so it acts on whichever tree the orchestrator was started from — including a
>   developer's primary checkout.
> - `_start_execution` shells out to the GitHub client to create one issue for the contract
>   and one per task, **before** any work happens. A curious run leaves real issues behind.
> - `OrchestratorLoop._find_contract` returns the first markdown file containing the text
>   `Status: approved`, which need not be the contract that was asked for.
>
> The working alternative is `/flow`, which composes `/task`, `/design-first`, `/tdd-first`,
> the reviewer agents, `/verify-before-done`, `/git-commit` and `/ship`, and pauses only
> where a person has to decide. Route there instead of offering a choice.
>
> Note for a consuming project: the plugin ships these seven scripts but neither the
> roadmap under `.claude/orchestrator/` nor the tests, so nothing in a fresh checkout
> records that they are stubs. This gate is that record.

With the contract now approved, offer the user an orchestration option for autonomous, loop-driven task execution:

**Present this choice:**

> **Contract approved.** Choose how to proceed:
> 
> **Option A — UNAVAILABLE, see the gate above. Do not present this option.** The Contract Orchestrator — manages task planning, execution, Architect re-entry, and final review autonomously. Returns when complete.
> 
> **Option B:** Traditional workflow — hand off to implementer agents (`/tdd-first` flow) and conduct reviews manually.

**If the user chooses Option A (Orchestrator) — unreachable while the gate above stands:**

1. Extract the contract ID from the filename: `<YYYY-MM-DD>-<slug>.md` → slug becomes `CTR-<slug>` (e.g., `2026-09-09-add-trailing-stops.md` → `CTR-add-trailing-stops`)
2. Run the orchestrator entry point:
   ```bash
   python3 .claude/scripts/execute_contract.py <CONTRACT-ID>
   ```
3. Wait for orchestrator completion (will handle task planning, execution, architect re-entry, and final review autonomously)
4. Orchestrator will report completion status and any failures
5. **STOP here.** Do NOT proceed to Steps 4, 5, or 6. The orchestrator subsumes all post-approval workflow steps.

**If the user chooses Option B (Traditional workflow):**

Proceed to Step 4 (implementer handoff) as normal. The orchestrator is not invoked.

**Rationale:** The orchestrator is designed for contracts with clear, decomposable work — explicit task lists and minimal discovery. Traditional workflow suits contracts where extensive review, feedback loops, or deep user involvement is expected. The user chooses which tool fits their contract's risk profile and complexity.

## Step 4: Hand off to implementer agents

Read the `Implementation Handoff` section of the approved contract. For each handoff block, launch the named agent (`dotnet-backend-architect`, `angular-senior-dev`, `ingestion-data-architect`) with the pre-written TASK block from the contract.

The implementer agents are configured to refuse if `PRIOR_FINDINGS.contract_path` is missing or the contract's `Status` is not `approved`. Always pass these fields.

When multiple implementer handoffs are present (e.g. backend + frontend), launch them in parallel where their file sets do not overlap. Launch sequentially if they do.

## Step 5: Post-implementation review

After all implementers return `Status: complete`, launch `fullstack-code-reviewer` **via the `Agent` tool**. This is non-negotiable — the main orchestrator session does NOT review its own implementers' output inline. Inline review prose ("I read the diff and it looks fine") does not satisfy this step. The reviewer must be a fresh agent instance with a cold context.

```
TASK: Review the implementation of <contract slug>
CONTEXT: concept contract at <path>, status approved
FILES: <union of all files changed across implementers>
PRIOR_AGENT: <implementer agents>
PRIOR_FINDINGS:
  contract_path: <path>
  contract_status: approved
  extra_checklist:
    - Did the implementation diverge from the concept contract's Data Shapes? If so, is the divergence justified?
    - Did this introduce a new reusable mechanism that belongs in .claude/registries/MECHANISMS.md? If yes, append it.
    - Did this introduce new domain vocabulary that belongs in .claude/registries/VOCABULARY.md? If yes, append it.
    - Did the implementation reveal a CONTRACT DEFECT (justified divergence = the contract was wrong)? If yes, the reviewer's janitor duty appends an entry to .claude/registries/JOURNAL.md with Trigger: post-impl divergence.
```

### Multi-pass review: always spawn fresh, never `SendMessage`

If the reviewer flags issues, the implementer fixes them, and you need a second review pass — **spawn a NEW `fullstack-code-reviewer` instance via the `Agent` tool**. Do NOT `SendMessage` to the prior reviewer instance. The prior instance carries forward its own earlier findings and the implementer's reasoning from the first round, both of which prime the second pass with biased context.

A clean re-review requires a clean context. The cost of one extra agent spawn is far lower than the cost of a missed regression.

### Mapping to the safety-critical review gate

This Step 5 invocation produces the HANDOFF that `/verify-before-done` Step 5.5 looks for when the diff includes safety-critical paths. If the diff additionally touches a root named by the `safety-critical.roots`, `auth.roots` or `migration.root` slots of `.claude/project-profile.md`, also spawn the matching domain reviewer (the project's live-action safety reviewer, `security-auditor`, `migration-safety-reviewer`) — each is an independent agent invocation, not a replacement for `fullstack-code-reviewer`.

## Step 6: Flip contract status to implemented

After review passes, edit the contract file and change `Status: approved` → `Status: implemented`. Fill in the Review Checklist at the bottom of the contract.

## Escape hatches

- **User asks for trivial change and gets wrongly classified as non-trivial:** user can override by re-stating as trivial. You must respect the override.
- **User wants to bypass the hook entirely:** document that they can set `CLAUDE_CONCEPT_GATE=off` in their environment for the session. Use sparingly.
- **Contract promotion:** if a contract's implementation introduces something genuinely reusable, the review step (Step 5) appends it to `MECHANISMS.md`. This is how the registry grows.

## What this skill does NOT do

- Does not write production code itself — delegates to data-architect (design) and implementer agents (code).
- Does not skip the communication gate — Open Questions MUST be answered by the user, never guessed.
- Does not run without reading `MECHANISMS.md` first (the data-architect enforces this).
