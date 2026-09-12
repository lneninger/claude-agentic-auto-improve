---
name: north-star
description: |
  Capture an aspirational direction-setting thought as a north-star file at
  .claude/north-stars/<YYYY-MM-DD>-<slug>.md. North-stars are the
  WHAT-WE-WANT register; distinct from JOURNAL.md (lessons from what already
  happened) and contracts (concrete tasks). Read by data-architect Step 0.5
  on every /design-first and reviewed via /north-star-review to emit ranked
  suggestions of contracts that would move the codebase toward the aspiration.

  Use when: the user types `/north-star "<aspiration>"`, or says "capture
  this as a goal", "record this direction", "I want the system to eventually X",
  or describes a future-state intent that should influence design decisions
  beyond the current task.
user_invocable: true
---

# /north-star — Capture an aspirational direction

When invoked, create one new north-star file from the user's thought. The thought is the artifact — preserve the user's words; don't paraphrase.

## Step 0: Read the template

Read `.claude/templates/north-star.md` to confirm the exact section structure. The file has 7 required sections: Aspiration, Why this matters, Anti-patterns, Current gap (Claude-maintained), Suggested next steps (Claude-maintained), Related, Lifecycle footer.

## Step 1: Detect the project

From CWD, derive the project name (last path component of repo root). Default to `StockToolScalpingMachine` when in that working tree. Stop and ask the user via `AskUserQuestion` if the project is ambiguous.

Create the project subfolder under `.claude/north-stars/` if it doesn't exist.

## Step 2: Gather the thought

The user typed `/north-star "<aspiration>"` or pasted a longer paragraph after the slash command. Use that as the **Aspiration** section verbatim — do NOT compress or rephrase. The user's framing is the artifact.

If the user only gave a short phrase (< 15 words), ask one follow-up via `AskUserQuestion`:

> "Expand on the aspiration: a sentence or two on what it would look like when achieved, and why it matters."

Don't ask more — north-stars are low-friction by design.

## Step 3: Derive the title and slug

- **Title**: scannable one-liner derived from the aspiration. Examples: `Testing/eval/deploy pipeline is dynamic, user-friendly, production-ready`, `No local filesystem reliance`. Land it as the `# ` heading.
- **Slug**: kebab-case, ≤ 40 chars. Examples: `testing-model-production-ready`, `no-local-filesystem`. Must match the filename suffix.
- **Filename**: `<YYYY-MM-DD>-<slug>.md` at `.claude/north-stars/`.

## Step 4: Author the Anti-patterns section

This is the load-bearing section — `contract-critic` checklist item 13 reads it to decide whether a future contract is in DIRECT CONTRADICTION with the aspiration.

Propose 3–6 anti-patterns based on the aspiration. Each anti-pattern MUST contain at least one **backticked snippet** (a code identifier, file path fragment, class name, or class-attribute string) that `north_star_review.py` can grep against the codebase. Examples:

- `New code that calls \`System.IO.File.WriteAllText\` against a path under the project repo`
- `A new feature that requires the operator user to author conditions in \`ClientApp/projects/scalping-machine/\``
- `Hardcoding \`var(--mat-sys-primary)\` inside a \`style="..."\` attribute (already caught by architecture-guard, listed here for completeness)`

Anti-patterns without backticked snippets degrade to manual review only — they are still valid but don't surface gap signals.

Present the draft anti-patterns via `AskUserQuestion` and let the user refine.

## Step 5: Populate the Why this matters + Related sections

- **Why this matters**: one or two sentences. Concrete business value or UX improvement. NOT motivational filler.
- **Related**:
  - **Mechanisms**: cite slugs from `MECHANISMS.md` (project section) that this aspiration would extend or replace.
  - **Areas**: cite slugs from `.claude/area-mapping.json` that are implicated.
  - **Adjacent north-stars**: other thoughts in the same project that cluster with this one (siblings, the WHAT/HOW split, the precondition relationship).
  - **Lessons**: JOURNAL.md entries whose `Apply when:` pattern matches this aspiration's anti-patterns.

## Step 6: Leave the Claude-maintained sections empty

The two Claude-maintained sections must be initialized as:

```
_Last updated: not yet reviewed_

- (to be populated by `/north-star-review`)
```

Do NOT pre-fill them. They are computed by `north_star_review.py` from the live codebase grep + cross-references.

## Step 7: Write the file and confirm

Use `Write` to create the file. Then run a single read-back to confirm the structure is intact. Tell the user:

> "Created `<filename>`. Active and discoverable. Run `/north-star-review` to populate the gap signal and concrete next-step suggestions. The aspiration will be read by data-architect on every `/design-first` from now on."

## What this skill does NOT do

- Does NOT populate Current gap / Suggested next steps — that's `north_star_review.py`'s job.
- Does NOT cross-reference against existing contracts — that's `north_star_review.py`'s job.
- Does NOT generate the first suggestions — same reason.
- Does NOT modify any other file. North-stars are append-only entries; new aspirations get new files.

## Hard refusals

If the user provides an "aspiration" that is actually a concrete task (e.g. "Add a new endpoint that returns active strategies"), refuse:

> "That sounds like a concrete task, not an aspiration. Run `/design-first '<task>'` instead — north-stars are the long-horizon WHAT-WE-WANT register, not the short-horizon backlog."

If the user provides an "aspiration" that contradicts an already-active north-star:

> "There's an active north-star `<slug>` at `<path>` that says `<aspiration excerpt>`. Your new thought contradicts it. Choose: (a) refine the existing one in place, (b) supersede it (rename to `.superseded.md`, cite the new one as `Supersedes:`), or (c) clarify how both can be active simultaneously."
