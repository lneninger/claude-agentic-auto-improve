---
name: verify-before-done
description: "Run the verification gauntlet before claiming a task is complete. Executes build, tests, migration check, generated-model drift check, and HANDOFF completeness check. Blocks on any failure. Use when: an agent or the user is about to declare Status=complete, before committing, before opening a PR, or whenever the phrase 'done', 'complete', 'ready to ship', 'finished' is used. Mandatory final step in /tdd-first and recommended final step in /design-first."
user_invocable: true
---

# /verify-before-done — Pre-Completion Verification Gauntlet

When invoked, run every applicable check below. **Do not report completion to the user or to a calling agent until this skill has been executed and passed.** If any check fails, halt and report the specific failure with its output — never claim "verified" based on partial evidence.

## Context — why this skill exists

Implementer agents (and Claude sessions in general) sometimes close a task with `Status: complete` based on *reading* the code they wrote, not *running* it. The project has four automation layers that catch drift (`concept-gate.py`, `architecture-guard.py`, CI `angular-models-drift.yml`, pre-commit hook) — but those only fire on write or commit. This skill is the runtime counterpart: it proves the claim *before* the user or downstream agent accepts it.

## Step 0: Determine scope

Classify the change by files touched (read `git status` + `git diff --stat`):

Roots come from `.claude/project-profile.md`. Read it first; do not infer a path from a project name.

- **Backend only** — every changed file sits under `backend.roots` → Steps 1, 2, 4, 5.5, 6, 7
- **Frontend only** — every changed file sits under `frontend.roots` → Steps 3, 4, 5.5, 6, 7
- **Full-stack** (both) → all steps
- **Migration** — anything under `migration.root` → Steps 1, 2, 5, 5.5, 6, 7
- **Sidecar or auxiliary runtime** — a language runtime outside `backend.roots` and `frontend.roots` → Steps 8, 5.5, 6, 7
- **Docs only** (`.md`, `.claude/`) → Step 6, 7 only

**Step 5.5 (safety-critical review gate) fires on every non-docs-only scope** — it short-circuits to PASS when no safety-critical path is touched, so it is cheap. See Step 5.5 for the path-to-reviewer mapping.

## Step 1: Backend build

```bash
dotnet build --nologo --verbosity minimal
```

**Halt conditions:**
- Any error CSxxxx that is NOT "DLL is locked" (the locked-DLL failure is the VS-debugger-attached edge case — ask the user to stop the debugger, then retry).
- Any warning treated as error per project config.

## Step 2: Backend tests

Run the tests for the project(s) whose source changed. Don't run the full suite unless the change is cross-cutting (DI, Program.cs, base classes).

```bash
dotnet test <affected-test-project> --nologo --verbosity minimal --no-build
```

**Halt conditions:**
- Any failed test, including previously-passing ones (regression).
- Any skipped test that was active before the change, unless the user explicitly approved skipping it.

## Step 3: Frontend build + tests

```bash
# From the frontend workspace root (frontend.root-container in the project profile):
npm run build -- --configuration=production
npm run test -- --watch=false --browsers=ChromeHeadless
```

**Halt conditions:**
- Angular compile errors.
- Any spec failure in the projects that changed.
- TypeScript errors in the generated folder (`core/api/generated/`, `core/hub/generated/`) — these indicate model drift, handled by Step 4.

## Step 4: Generated-model drift check

If any `.cs` file in a sentinel path (see `.claude/hooks/sentinel-paths.json`) was edited, verify the generated TypeScript matches:

```bash
# Check drift without running the regenerator
git diff --stat <frontend.roots>/**/generated/
# If there are uncommitted changes here but no regen in flight, run it manually:
tools/regenerate-angular-models.cmd
git diff --stat <frontend.roots>/**/generated/  # should now be clean if auto-regen already ran
```

**Halt conditions:**
- Modified `.cs` file in sentinel path AND stale `.ts` generated file → run the regenerator and stage the diff.
- CI would reject the PR anyway (angular-models-drift.yml) — catch it locally.

## Step 5: Migration safety check

If any `Persistence/Migrations/*.cs` file was created or modified:

1. Open the generated migration in an editor (or `Read` the file) and eyeball it:
   - Does it match the entity change you intended?
   - Does it include a sensible `Down()` for rollback?
   - Are there any `DROP COLUMN` / `ALTER COLUMN` / `DROP INDEX` operations that need a data backfill first?
2. Run the migration against a local dev DB:
   ```bash
   dotnet ef database update --project <the project owning migration.root> --startup-project <the startup project>
   ```
3. Step 5.5 will enforce that `migration-safety-reviewer` was invoked on the current diff — do not bypass it for schema modifications.

**Halt conditions:**
- Migration fails to apply (syntax, FK, constraint violation).
- Migration drops a column or table without a data migration plan.
- Migration modifies a table with > 1M rows without a plan for online reindex / locking.

## Step 5.5: Safety-critical review gate (hard gate)

This step encodes the **session-context-isolation principle**: code review done inline by the same session that generated the code is biased by the generator's reasoning. For safety-critical paths, an independent reviewer instance (spawned via the `Agent` tool with a cold context) MUST have audited the current diff before verification can PASS.

### Path-to-reviewer mapping

Read `git diff --name-only` (uncommitted + staged) and classify each file:

**Resolve every row against `.claude/project-profile.md` before matching.** The rows name profile
slots, not literal paths. Open the profile, read the slot, and match the diff against the roots it
names. If the profile is missing, say so and halt — do not guess a path from a project name.

> **Why this indirection exists, in one incident.** Until 2026-09-12 the first row read
> `src/ScalpingMachine.Strategy/Execution/**`. That path has never existed in this repository's
> history; the execution engine is under `Services/`. The row had been wrong since the day it was
> written on 2026-08-22, and no run ever failed because of it — a prose rule whose pattern matches
> nothing simply stays quiet, and quiet is indistinguishable from "nothing to review". A hardcoded
> path in a shared skill is a fact nobody owns. A slot has one owner and one place to be wrong.

| Diff touches the roots named by | Required reviewer agent | Rationale |
|---|---|---|
| `safety-critical.roots` — the live-order-flow and broker entries | `trading-safety-reviewer` | Live order flow, broker integration |
| `auth.roots` | `security-auditor` | Credentials, tokens, encryption |
| `migration.root` | `migration-safety-reviewer` | Online schema change risk |
| Any repository class or database query change under `backend.roots` | `sql-performance-reviewer` | Plan / index / N+1 risk |
| Any controller or data-transfer-object change under `backend.roots` | `api-contract-reviewer` | Frontend deserialization drift |
| Any hand edit to generated client code under `frontend.roots` | `api-contract-reviewer` + halt | Generated files must not be hand-edited; investigate before allowing |
| Any file the profile's `review.documents` flags as pipeline-critical | `llm-contract-reviewer` | Tool / schema / training-data alignment |

A slot may name several roots, and a single diff can require multiple reviewers — list them all.

### Gate procedure

1. Compute the required-reviewer set from the diff using the table above.
2. If the set is **empty** → emit `Step 5.5: PASS (no safety-critical paths in diff)` and proceed to Step 6.
3. If the set is **non-empty**, for each required reviewer in the set:
   - Check session history: was this reviewer spawned via the `Agent` tool AFTER the last modification to the files it owns? An inline review in the main session does **NOT** count and never satisfies this gate.
   - If yes → record `<reviewer>: SATISFIED (HANDOFF at <message ref>)`.
   - If no → record `<reviewer>: MISSING`.
4. If any reviewer in the set is `MISSING`:
   - **HALT verification.** Do NOT proceed to Step 6.
   - Emit the list of missing reviewers and the file groups they cover.
   - Tell the caller: *"Spawn the listed reviewer(s) via the `Agent` tool now. After each reviewer returns its HANDOFF, re-invoke `/verify-before-done`. Do NOT review the code inline — the isolation requirement is structural, not stylistic."*
   - Do not auto-spawn the reviewers — the caller (main session) must do it, because the spawn site is part of what makes the review isolated.
5. If every required reviewer is `SATISFIED`, emit `Step 5.5: PASS (<n> reviewers verified)` and proceed.

### What counts as "spawned via Agent tool"

- `Agent` tool call with `subagent_type: <reviewer-name>` returning a fresh HANDOFF block whose `Files reviewed` list overlaps the current diff
- Re-invocation of the same reviewer after a code change is a **new** spawn — do not credit the previous run if any in-scope file changed since
- `SendMessage` to a prior reviewer instance does **NOT** count — that instance still has the generator's context priming its judgment

### What does NOT count

- Inline review prose written by the main session ("I read the diff and it looks fine")
- Build / test PASS (those are Steps 1–3, not review)
- The implementer agent's own self-critique inside its HANDOFF
- A reviewer agent that was spawned but reviewed an earlier diff (the in-scope files changed since)

### Why this is a hard gate (not a recommendation)

The 2026-05-17 eval-runs consolidation contract showed 5 WARN findings from `contract-critic` in a draft the data-architect had marked `verdict: confident`. The generator could not see what an independent reviewer could see. That pattern recurs in code review: the generator's confidence is not evidence of correctness. The gate makes the structural isolation mandatory for the paths where the cost of a missed bug is highest (live money, credentials, schema, query plans, API contracts).

### Escape hatch

For a one-shot human-approved exception, the **user** (not an agent) sets `CLAUDE_VERIFY_REVIEW_GATE=off` in the environment for the session. Agents MUST NOT set or unset this. Document any use in the commit message.

## Step 6: HANDOFF completeness check

If the caller is an agent producing a `### HANDOFF` block (see `.claude/HANDOFF_SCHEMA.md`), verify:

- [ ] `Status` is populated (complete / needs-review / blocked)
- [ ] `Files changed` lists absolute paths with one-line description each
- [ ] `Key decisions` explains any non-obvious choice (never "N/A" unless truly nothing notable)
- [ ] `Warnings` lists known-but-unaddressed issues (empty is allowed)
- [ ] `Context for next agent` is populated if `Recommended next` is not `none`
- [ ] `Recommended next` names a specific agent or explicitly says `none`
- [ ] `Suggested input for next agent` is pre-written if `Recommended next` ≠ `none`

A HANDOFF block missing any mandatory field is not a completed task — the implementer gets a second chance to fill it in.

## Step 7: Commit hygiene sanity check

```bash
git status
git diff --stat --cached
```

Check for:

- [ ] No unintended files staged (`.env`, credentials, `*.key`, `*.pem`, connection strings).
- [ ] No generated-client drift under `frontend.roots` (either committed cleanly or regenerated in Step 4).
- [ ] No `.claude/.models-dirty-*` or `.claude/.regen-lock` files accidentally staged.
- [ ] No `bin/`, `obj/`, or build output staged.
- [ ] No `debug-notes*.md` or `.claude/tdd-scratch-*.md` staged (those are local scratch files).

**Halt conditions:**
- Any sensitive file (secrets, keys, connection strings) staged — ask the user to unstage and confirm before proceeding.

## Step 8: Python sidecar smoke check

If any file under `python/scalping_llm/**` changed:

```bash
# Syntax / import check
cd python && py -3 -c "import scalping_llm" && cd ..

# If the sidecar is already running, hit /health
curl -sS http://localhost:8091/health || echo "sidecar not running (acceptable if not required for this change)"

# Run any sidecar tests that exist
cd python && py -3 -m pytest tests/ -q && cd ..
```

**Halt conditions:**
- Import error on the package.
- Any sidecar test fails.

## Step 9: Report verified state

Once all applicable steps pass, emit:

```
### VERIFICATION REPORT
- Scope: <backend|frontend|full-stack|migration|python|docs>
- Steps executed: <list>
- Build: PASS
- Tests: PASS (<n> tests)
- Generated drift: CLEAN
- Migration applied: <yes/no/NA>
- Safety-critical review gate: PASS (<n> isolated reviewers verified | NO SAFETY-CRITICAL PATHS)
- HANDOFF fields: COMPLETE
- Commit hygiene: CLEAN
- VERDICT: READY
```

Only then may the caller set `Status: complete` in their HANDOFF.

## Step 10: Post-verification commit protocol (auto-fires on VERDICT: READY)

After Step 9 returns `VERDICT: READY`, auto-stage + auto-draft + ASK ONCE before committing. Do **not** commit silently. Do **not** skip this step unless one of the explicit skip conditions below applies.

### Trigger gate

Run this step IFF all of the following are true:
- Step 9 verdict is `READY` (not `BLOCKED`, not partial)
- Working tree has at least 1 modified or untracked file (otherwise nothing to commit — silently skip)
- The user did not say "don't commit", "wait", "hold off", "no commit", or any equivalent phrase since the verification started
- The project's recent commit history is non-empty (this is a `git init`-with-commits repo, not a fresh init)

### Action sequence

1. **Identify scope.** Run `git status --short` and parse the file list. Exclude any of:
   - Sensitive: `.env`, `.env.*`, `*.key`, `*.pem`, `*.pfx`, `appsettings*.json` (with credentials), `secrets*.json`, `credentials.json`
   - Build output: `bin/`, `obj/`, `dist/`, `node_modules/`
   - Local scratch: `.claude/.models-dirty-*`, `.claude/.regen-lock`, `.claude/hooks/*.log*`, `debug-notes-*.md`, `.claude/tdd-scratch-*.md`
   - Generated drift: generated client code under `frontend.roots` only if Step 4 reported drift that was NOT yet regenerated (a CLEAN regen is committable)
   If any excluded file is in the working copy, list it explicitly to the user and ask whether to include it before staging anything else.

2. **Scope-creep check.** If the staged file list exceeds **30 files** OR touches more than **3 top-level project directories**, escalate to the user with the full list before drafting the message. Large commits hide intent; ask the user to confirm or split.

3. **Stage explicitly.** Use `git add <file1> <file2> ...` with the explicit file list. Never `git add -A` / `git add .` / `git add -u`.

4. **Draft the commit message** matching the project's recent commit style (read the last 3 commit subjects via `git log -3 --format="%s"` to mirror length + tone):
   - **Subject:** ≤ 70 chars, focuses on the *why* (or the named phase/scope), present tense, no trailing period
   - **Body** (only if scope is multi-component or non-obvious): 2–4 sentences explaining the *why* and naming any side-effects, blank line before
   - **Trailer:** `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (always, on its own line at the very end)

5. **Show + ask.** Surface to the user:
   - The staged file count + first ~10 file paths (the rest as `... and N more`)
   - The drafted subject line + first 2–3 lines of the body
   - One question: `Commit? (yes / edit / cancel)`

6. **On user response:**
   - `yes` (or any clear go-ahead like "ship", "commit", "go", "do it"): commit via HEREDOC immediately, then run `git status --short` + `git log -1 --oneline` and report the new HEAD hash
   - `edit`: show the full message and accept the user's revision (apply their text verbatim into the HEREDOC), then commit
   - `cancel` / `no` / `wait`: leave the staged file list as-is and tell the user `git reset` will unstage if they want to abandon

7. **Never:**
   - Skip hooks (`--no-verify`) unless the user explicitly asks
   - Amend (`--amend`) unless the user explicitly asks
   - Push (`git push`) unless the user explicitly asks
   - Force-push (`git push --force`) under any circumstance — escalate
   - Commit if the pre-commit hook fails — investigate the hook output and fix the underlying issue (per project rule: failed pre-commit hook means the commit did NOT happen, so `--amend` would corrupt the prior commit)

### Skip conditions (do NOT auto-commit)

- User said any "don't commit" phrase since verification started
- The change is purely a HANDOFF field fix or a stale-cache invalidation that the user would likely want to fold into the next feature commit
- The verification was invoked mid-flight specifically to check state (not to ship) — detect by reading the most recent user message: if it says "check" / "see if" / "what does it look like" / "status" / "smoke", treat as a state-check and skip the commit ask
- The repo is in detached HEAD state, on `main` / `master` directly (not a feature branch), or in mid-rebase (`git status` reports rebase / merge in progress)

### Why this exists

Without this step, every shippable change requires the user to type "commit" twice (once to ask, once to confirm). With this step, the path is one tap (`yes`) once the verification has already proven the change is safe. The ASK-before-commit caveat preserves human review of scope creep — the protocol's purpose is to remove typing, not human judgment.

## Anti-patterns (halt immediately)

- **"All green" without running the commands** — the skill requires actual command output, not a summary of what the output would have been.
- **Skipping Step 4 because "I didn't touch generated files"** — if a sentinel `.cs` file changed, the `.ts` drift check is mandatory.
- **Partial verification** — don't run 3 of 8 applicable steps and call it verified. Run them all or report which ones were skipped and why.
- **Claiming "verified" based on the previous CI run** — CI ran before this change. Verify this change's state.
- **Reviewing the diff inline in the main session to satisfy Step 5.5** — the gate exists *because* same-session review is biased. Inline prose never counts; spawn the reviewer via the `Agent` tool.
- **`SendMessage`-ing a prior reviewer instance after a code change to satisfy Step 5.5** — that instance carries the generator's context. Spawn a fresh instance.

## Integration

The canonical places to invoke this skill:

1. **End of `/tdd-first`** — Step 7 already references this skill.
2. **Before any `Status: complete` HANDOFF** — implementer agents should invoke this automatically via the `Skill` tool if the project has the skill available.
3. **Before `git commit`** — either manually, or as part of a pre-commit workflow.
4. **Before `gh pr create`** — PR readiness check.

## When to NOT use this skill

- **Mid-flight exploration** — if you're still iterating, verify-before-done is overkill.
- **Read-only tasks** — research, code review, architecture analysis. Nothing to verify.
- **Documentation-only changes** — Step 6 (HANDOFF) + Step 7 (commit hygiene) are enough.
