---
name: journal-add
description: "Append a lesson-learned entry to .claude/registries/JOURNAL.md. Use when: the user says /journal-add, 'log a lesson', 'add to the journal', 'record this for next time', or after a production incident / debugging session / contract review surfaces a non-obvious insight that future contracts should heed. The journal is read by data-architect (Step 1) and contract-critic on every run."
user_invocable: true
---

# /journal-add — Append Lesson to the Adaptive Engineering Journal

When this skill is invoked, append one entry to `.claude/registries/JOURNAL.md` under the matching project section (or Universal tier if no project context applies).

The journal is the only feedback loop that carries lessons forward between concept contracts. `data-architect` reads it before drafting and `contract-critic` matches every entry's `Apply when:` pattern against new drafts. A well-written entry prevents the same defect from recurring.

## Step 0: Read the file before editing

Always `Read` `.claude/registries/JOURNAL.md` first. You need:
1. The two-tier structure (Universal vs `## Project: <name>` sections).
2. Confirmation that the project section exists under the matching name. If not, create it.
3. The exact entry shape documented in the header.

## Step 1: Gather the entry fields

Use `AskUserQuestion` to collect each field unless the user already provided it in the slash-command argument.

The five required fields (template entry shape):

1. **Title** — short, scannable, action-oriented. Examples: `Reuse MarketElements + IFieldResolver for symbol characteristics`, `Don't hand-author EF migrations on tables > 10M rows`. Avoid generic titles like `Bug fix lesson`.

2. **Trigger** — one of:
   - `pre-approval critic` — surfaced during /design-first Step 5 from a contract-critic finding the user confirmed.
   - `post-approval` — the contract had already been approved (or implemented) when the issue surfaced. Pick this when a flaw in an approved design was uncovered by anything other than `fullstack-code-reviewer` (production incident, a follow-on contract revealing a flaw upstream, manual audit). Fires the accuracy-skip "post-approval" signal — the source contract's areas lose their clean streak.
   - `post-impl divergence` — surfaced by fullstack-code-reviewer when the contract turned out to be wrong vs the shipped code. Also fires the accuracy-skip signal (same `post-*` family).
   - `manual` — surfaced outside the protocol AND not tied to a specific approved contract (debugging unrelated to a contract, generic process insight). Does NOT fire the accuracy-skip signal.

   **Trigger selection rule:** if `Source contract:` points at a contract whose Status is `approved` or `implemented`, pick `post-approval` or `post-impl divergence` — NOT `manual`. The contract-critic accuracy system relies on this signal to reset the area's clean streak; mis-tagging it as `manual` silently swallows the failure signal.

3. **Source contract** — full path to `.claude/concepts/<slug>.md` if the lesson came from a contract review, or `N/A` for manual entries.

4. **Lesson** — one line, ACTIONABLE. Format as `Do X` or `Avoid Y when Z` or `When in <pattern>, reach for <mechanism>`. NOT `Be careful with X` (not actionable) and NOT a paragraph (too long).

5. **Apply when** — concrete signal a FUTURE contract should heed this. Phrase as a pattern the contract-critic checklist can match against. Examples: `contract adds a new symbol characteristic field`, `contract proposes a new background ingestion job`, `contract introduces a value object that already has a MECHANISMS.md analog`.

6. **Tags** — comma-separated keywords for grep. 2–5 tags. Examples: `reuse, MarketElements, field-resolver` or `ef-migration, large-table, online-index`.

If the user passed the title as the slash-command argument (e.g. `/journal-add Reuse MarketElements`), use it as `Title` and ask only the remaining four questions.

## Step 1.5: UI-lesson check

After gathering the basics, ask one focused yes/no question via `AskUserQuestion`:

> **Is this a UI lesson?** (Will the `ui-ux-designer` agent benefit from re-reading this on every invocation?)

If yes:

- **Enforce `ui-evolution` in the Tags line.** If the user's Step-1 Tags list does not include it, prepend `ui-evolution` automatically.
- **Ask the optional app scope** via a second `AskUserQuestion`: "Which app does this apply to?" — one option per application named by the `frontend.roots` slot of `.claude/project-profile.md`, spelled `app:<name> only`, plus an `all apps (no sub-tag)` option. If an `app:*` option is picked, append the chosen sub-tag to the Tags line.
- **Recurring-mistake check.** If the user described this as a repeat occurrence (e.g. "the third time we hit this"), also append `recurring-mistake` to the Tags line. This is the signal `/promote-ui-rule` reads when gating automated guard-rule promotion.

If no, skip this step. (The architecture-advisor hook and ui-ux-designer agent's Step 0 grep would still pick up the entry on a tag match, but you avoid the noise of marking generic lessons as UI-tagged.)

**Optional Areas line.** For any entry (UI or not) whose `Source contract:` is `N/A` (manual entries), offer to append an `Areas:` line so the cross-area scanner can attribute the lesson to specific buckets. Use `AskUserQuestion` with the options drawn from `.claude/area-mapping.json` keys + `(universal — no Areas line)`. The user picks any subset; the Areas line gets the comma-separated slugs. Skip the prompt for non-manual triggers — those derive their area from the Source contract automatically.

## Step 2: Detect the project section

Determine the project from CWD:

- If CWD is inside the repository, the section is `## Project: <project.name>`, taking `project.name` from the `.claude/project-profile.md` slot of that repository.
- If the profile is absent, fall back to the last path component of the repo root.
- If CWD is `~/.claude` or unrelated → use the `## Universal lessons` section instead.

If the matching `## Project: <name>` section does not exist in JOURNAL.md, create it immediately above the closing of the file with this exact heading and a single-line placeholder comment matching the existing project sections.

## Step 3: Append the entry

Use `Edit` with `old_string` = the placeholder comment for the target section (e.g. `<!-- empty on day 1 — populated as lessons are discovered -->` if it's still there) OR the trailing whitespace after the last existing entry in that section, and `new_string` = the placeholder/whitespace PLUS the newly-formatted entry below it. NEVER reorder existing entries. NEVER rewrite them.

The exact entry shape (already documented in the JOURNAL.md header):

```markdown
### YYYY-MM-DD — <Title from Step 1>
- **Trigger:** <Trigger from Step 1>
- **Source contract:** <Source contract path or N/A>
- **Lesson:** <Lesson from Step 1>
- **Apply when:** <Apply-when pattern from Step 1>
- **Tags:** <comma-separated tags from Step 1; with `ui-evolution` and optional `app:*` / `recurring-mistake` from Step 1.5>
- **Areas:** <optional, only when supplied in Step 1.5 for manual entries>
```

The date is today's date in `YYYY-MM-DD` format. If you don't know today's date from session context, use `Bash` with `date +%Y-%m-%d` (POSIX) or PowerShell `Get-Date -Format yyyy-MM-dd`.

## Step 4: Confirm the append to the user

Show the appended entry verbatim and the destination section (Universal vs `Project: <name>`). One short sentence — no celebration prose.

If this was triggered from `/design-first` Step 5 (the orchestrator confirming a contract-critic finding), the orchestrator already knows what to do next. Otherwise, mention that future `data-architect` and `contract-critic` runs will now read this entry on every invocation — no additional setup is required.

## Step 5: If the user mis-tagged the trigger, ask

If the user said `manual` but the lesson clearly came from a contract review (e.g. they passed a contract path as Source contract), prompt once: `Trigger was set to 'manual' but the source is a contract. Re-tag as 'pre-approval critic', 'post-approval', or 'post-impl divergence'?` Use `AskUserQuestion`. Don't auto-correct.

If the user picked `post-approval` or `post-impl divergence` but Source contract is `N/A` or unresolvable, prompt once: `Trigger '<value>' requires a Source contract path so the accuracy-skip system can reset the area's clean streak. Provide the contract path or change Trigger to 'manual'.` Use `AskUserQuestion`. Don't auto-correct.

## What this skill does NOT do

- Does NOT write to any file other than `.claude/registries/JOURNAL.md`.
- Does NOT modify or reorder existing journal entries — append-only.
- Does NOT validate the lesson content for quality — that's the human's call.
- Does NOT trigger any agent or downstream workflow. The next time `data-architect` or `contract-critic` runs, they read the journal naturally.

## Hard refusals

If the user provides a Lesson that is just a paragraph or a multi-sentence explanation:

> "Journal entries are one-line actionable lessons. What you wrote is closer to a postmortem section. Compress to one line of `Do X` / `Avoid Y when Z` form, and I'll append it. The longer context belongs in the source contract or a separate handbook entry."

If the user tries to log something that contradicts an existing journal entry without referencing it:

> "There's an existing entry `<date — title>` that says `<existing lesson>`. Your new entry contradicts it. Either reference the old entry explicitly in the Lesson body (`Refines <YYYY-MM-DD — title>: ...`) or pick one to supersede."

The append-only invariant matters: contradictory entries side by side without cross-reference would teach the critic to flag false positives.
