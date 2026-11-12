---
name: auto-improve-finish-install
description: "Finish installing the agentic-auto-improve plugin in this project: fill in the project profile (Quick start step 4), propose the area map, the pull request module tags and the project-name tokens (Quick start step 3), and check or register the hooks (Quick start step 5). Looks at the repository, shows each proposed value with its evidence, asks for one confirmation, and writes only slots and files that are still as scaffolded. For the hooks it first works out how the plugin reached this project, then reports readiness (plugin install) or shows the exact settings.json change and writes it only after a yes (vendored copy). The name carries the plugin name because you may have several plugins installed. Use when: user says /auto-improve-finish-install, 'finish installing the auto-improve plugin', 'finish the agentic-auto-improve install', 'set up the project profile', 'fill in the project profile', 'fill in the area map', 'propose the project tokens', 'register the hooks', or 'are the auto-improve hooks on'. Never guesses a value and never overwrites an authored slot or file."
user_invocable: true
---

# /auto-improve-finish-install — finish the Quick start steps the plugin cannot copy

The plugin cannot copy three things for you. One is the project profile, which describes
**your** repository. Another is the three per-project files built from it: the area map, the
pull request module tags and the project-name tokens. The last is the hook registration, which
switches enforcement on.

This skill walks you through all three. It proposes, you confirm, and only then does it write.

```
/auto-improve-finish-install
   Stage 1  project profile   propose -> one confirmation -> write the placeholder slots
   Stage 2  step-3 files      area map, PR module tags, project-name tokens:
                              propose -> one confirmation -> write the files still as scaffolded
   Stage 3  hooks             plugin install:  report readiness, write nothing
                              vendored copy:   show the diff -> ask -> write, with a backup
```

The name says which plugin it finishes. You may have several plugins installed, and a bare
"finish install" could mean any of them. This skill reads and touches only
`agentic-auto-improve`. It never reads or changes another plugin's entries.

## The rule that shapes everything here

**The skill carries the conversation. The script carries every rule.**

Which slot is a placeholder, which agent name is real, how an install mode is decided, how
`settings.json` is merged: all of it lives in `auto_improve_finish_install.py`, which has its
own test suite. Read its answer. Do not work any of it out yourself. If you re-derive a rule,
there are two versions of it, and they will disagree.

## Step 0: Find the script

The script sits at a different path under a vendored copy and under a plugin install. Test
the places **in this order** and keep the first hit. Do not use `ls` on all three paths:
`ls` sorts its operands, so the order you meant is lost.

```bash
FI=
S=.claude/scripts/auto_improve_finish_install.py
if [ -f "$S" ]; then FI=$S
elif [ -n "$CLAUDE_PLUGIN_ROOT" ] && [ -f "$CLAUDE_PLUGIN_ROOT/$S" ]; then FI=$CLAUDE_PLUGIN_ROOT/$S
else
  # What Claude Code recorded for this plugin (this project's entry, then the user entry), then the newest cache folder by version number.
  CFG=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
  ME=$(printf %s "$CLAUDE_PROJECT_DIR" | tr 'A-Z\134' 'a-z/' | tr -s /)
  REC=$(tr -d '\r\n' 2>/dev/null < "$CFG/plugins/installed_plugins.json" | grep -o '"agentic-auto-improve@[^"]*" *: *\[[^]]*]' | grep -o '{[^{}]*}' | tr '\134' / | tr -s /)
  MINE=$(printf '%s\n' "$REC" | grep '"scope" *: *"project"' | while IFS= read -r O; do
    P=$(printf %s "$O" | sed -n 's/.*"projectPath" *: *"\([^"]*\)".*/\1/p' | tr 'A-Z' 'a-z' | tr -s /)
    [ -n "$ME" ] && [ "${P%/}" = "${ME%/}" ] && printf '%s\n' "$O"
  done)
  NEWEST=$(ls -d "$CFG"/plugins/cache/*/agentic-auto-improve/*/ 2>/dev/null | sed -n 's|^\(.*/\([0-9][0-9.]*\)/\)$|\2 \1|p' | sort -rV | cut -d' ' -f2-)
  FI=$({ printf '%s\n' "$MINE"; printf '%s\n' "$REC" | grep '"scope" *: *"user"'; } | sed -n 's/.*"installPath" *: *"\([^"]*\)".*/\1/p' | { cat; printf '%s\n' "$NEWEST"; } | while IFS= read -r D; do
    [ -n "$D" ] && [ -f "${D%/}/$S" ] && { printf '%s\n' "${D%/}/$S"; break; }
  done)
fi
py -3 "$FI" --help   # macOS and Linux: python3 "$FI" --help
```

**If `FI` is empty, stop and say so.** Say that the script was not found in the project, in
`$CLAUDE_PLUGIN_ROOT` or in the plugin cache. Then stop. Without the script there is nothing
to run, and a skill that guesses is worse than one that stops.

Pick the launcher once and reuse it. On Windows use `py -3`. On macOS and Linux use
`python3`. The rest of this file writes it as `PY`.

```bash
PY="py -3"        # Windows
PY="python3"      # macOS and Linux
```

Every command below is `$PY "$FI" <profile|project-files|hooks> --project . ...`.

**Exit codes.** `0` means a plan, an apply or nothing to do. `2` means a refusal you can
correct. `3` means an environment problem, such as a missing template. On `2` or `3`, read
the `code` and `message` fields, tell the user the reason in one plain sentence, and stop.
A refusal always means nothing was changed.

### Which provider is this?

Hooks are Claude-only in this release. On **Cursor** and **Codex**, run Stages 1 and 2 in full, then
run `hooks --provider cursor` (or `codex`). It returns `provider-has-no-hooks`. Say that hooks
are Claude-only here, that nothing was written, and stop. The profile and the three step-3 files are
the same on all three providers.

## Stage 1: the project profile (Quick start step 4)

### 1a. Is there a profile yet?

If `.claude/project-profile.md` does not exist, run the doctor first. It scaffolds the file
with its placeholders intact. It never overwrites a file that exists:

```bash
$PY "<dir of FI>/plugin_doctor.py" --fix
```

Resolve `plugin_doctor.py` from the same folder as `FI`. If a profile already exists, skip
this step.

### 1b. Preview

```bash
$PY "$FI" profile --project . --json
```

The answer carries `proposals`, `rows-to-fill`, `rows-to-add`, `unified-diff`,
`local-agents`, `plugin-root`, `source-sha256` and `plan-sha256`. **Keep `plan-sha256`.** Both
writes need it as `--expect-sha256`. It covers the profile bytes and the text the write would
produce, so a template that moves between the preview and the write is refused. `source-sha256`
alone is refused as `changed-since-preview`.

Show the user the `plugin-root` the template came from, so a wrong pick is visible. It is the
copy of the plugin the script read, found in the Claude home that was named (or `~/.claude`
when none was). A tree that is not this plugin is skipped.

### 1c. Show one table

Show every slot in **one** table. Give each row the slot name, the proposed value, the basis
and the evidence.

| Slot | Value | Basis | Evidence |
|---|---|---|---|

The four bases mean:

- `inferred`: the script found a marker in the repository. The evidence column names it.
- `needs-answer`: the script will not guess. You must ask.
- `kept-authored`: the team already wrote this slot. It will not change.
- `none-found`: nothing in the repository points to a value. The slot becomes `none`.

If an authored slot differs from what the script would propose, show both and ask. Do not
change it. The script refuses to.

### 1d. Ask once

State your recommendation first, in one or two sentences. Then ask for **one** confirmation
or correction of the whole set.

Ask only about `needs-answer` slots. They are:

- **Theme polarity**, per frontend root: light, dark or both.
- **Safety-critical roots**: the folders where a mistake is expensive.
- **Auth candidates**: the folders the script listed by name. A folder name is a guess, so
  the user decides which are real.
- **Local agents' roles**: for each agent in `local-agents`, is it an implementer, a review
  gate, or neither?

A role slot that is filled **replaces** the plugin defaults. It does not add to them. So when
the user assigns a local agent to a role, the value is the plugin's default agents for that
role plus the local agent.

### 1e. Write

```bash
$PY "$FI" profile --project . --apply --expect-sha256 <plan-sha256 from the preview> \
    --set backend.roots=src/Api,src/Worker --set safety-critical.roots=none ...
```

Rules for the `--set` list:

- Pass one `--set slot=value` for every placeholder slot.
- For a slot that is never inferred and that the user left unanswered, pass `none`
  **explicitly**. Leaving it out is refused as `slot-unanswered`.
- Write a list as plain entries separated by commas, or the word `none`. A value holds no
  backtick, newline or pipe: the script adds the backticks itself when it writes the row, and
  a value with any of the three is refused as `invalid-slot-value`.
- A theme polarity is one entry per root, in the form `<root>=<polarity>`.
- Use only real agent names. A name that is not a real agent is refused as `unknown-agent`.
- Never `--set` a slot that is already authored. It is refused as `slot-already-authored`.

If the apply says `changed-since-preview`, the file changed after you showed it. Go back to
1b, preview again, show the new table, and ask again. Never reuse the old hash.

Declining writes nothing.

## Stage 2: the three per-project files (Quick start step 3)

This stage reads the profile that Stage 1 just filled, so it runs after Stage 1 and before the
hooks. It proposes content for three files the doctor scaffolds: the area map
(`.claude/area-mapping.json`), the pull request module tags (`prTitle.map` and `prTitle.order` in
`.claude/work-item-conventions.json`) and the project-name token list (`.claude/.project-tokens.json`).
One plan covers all three, one confirmation releases it, and one plan hash binds the write.

### 2a. Preview

```bash
$PY "$FI" project-files --project . --json
```

The answer carries `files` (one entry per file), `modules`, `token-proposals`, `exclusions`,
`source-notes`, `not-inferred`, `narrows`, `narrows-if-tokens`, `narrowing-statement`, `profile-note`,
`plugin-text-check`, `backup-dir`, `gitignore-hint` and `plan-sha256`. This first preview has no
`--token` and no `--skip-file`, so it is for showing the table. **Its `plan-sha256` is not the one to
apply with:** the hash covers every file's old and planned bytes, the `--token` list and the
`--skip-file` list, so the hash of the final preview in 2d is the only one that is accepted.

If the answer is refused as `plugin-source-checkout`, `project-unreadable` or `token-invalid`, say
the reason in one plain sentence and stop. A problem with one file is never a refusal: it is that
file's `basis`, and the other two files go on.

### 2b. Show one table

Show one row per file with its `basis` and its `unified-diff`, one row per entry in `modules`
(the area, its patterns and the profile slot that named its root), and one row per token proposal
(the text, the source, the evidence, and whether it is `already-listed`) or exclusion (the text and
the reason). Show every `source-notes` entry too. A source note means a token source was skipped
and why; the other sources and files went on.

The file bases mean:

- `inferred`: the file is still as scaffolded and the script has content for it. The diff shows it.
- `none-found`: nothing to propose. The file stays as scaffolded, and the note says why.
- `kept-authored`: the team already wrote this file. It is never changed. What would have been
  proposed is shown as `advice`.
- `scaffold-missing`: the file is absent. This command never creates it. Offer to run
  `plugin_doctor.py --fix` (see "The project history record" for the ask-first rule), then run the preview again.
- `unrecognised`: the file is not strict JSON, has a duplicate key or a byte order mark, or lacks
  the expected member. It is never written. Tell the user the note's reason.
- `skipped`: the user named it with `--skip-file`.
- `nothing-confirmed`: tokens were proposed but no `--token` was given. The file stays as it is.

If `profile-note` is present, the profile is the reason: `profile-missing` or
`profile-has-placeholders` means "fill the profile first (Stage 1)"; `roots-authored-none` means the
profile says this project has no such roots. Say which, and do not propose anything yourself.

Say what the script does **not** infer (`not-inferred`): vendor and broker names, and the project's
own handbook file names. The user adds those by hand. If `plugin-text-check` is `unverifiable`,
say that no plugin copy could be read, so the check that a token does not occur in the plugin's
own files could not run.

### 2c. Ask once

State your recommendation first, in one or two sentences. Then ask for **one** answer that holds:

- **The tokens to keep.** Only a token the user names is ever written. Pass each one with
  `--token`. A name the user gives that no source found is allowed. Never propose or type a token
  the script did not list or the user did not name.
- **Any file to skip**, with `--skip-file area-map|conventions|tokens`.
- **A yes or no to the narrowing statement**, whenever `narrows-if-tokens` is true (the token file
  is still empty and not skipped; the first preview already says so, before any token is chosen).
  Print the `narrowing-statement` in plain words: today the empty list keeps every memory item
  private to the project; after the change an item stays global unless it contains a listed name, so
  a name missing from the list can leave in a global item. Ask it here, with the other answers, so
  that one reply holds everything. Without a yes, do not pass `--confirm-narrowing`.

  What a **no** does: drop every `--token`, or pass `--skip-file tokens`, preview again (2d), and
  apply the other two files. The token file then stays as scaffolded and no confirmation is needed.

### 2d. Preview again with the confirmed flags, then write

Run the preview **again** with every confirmed `--token` and `--skip-file`, and take the
`plan-sha256` of THAT answer. Check that its diffs are the ones the user confirmed:

```bash
$PY "$FI" project-files --project . [--token <text>]... [--skip-file <file>]... --json
```

Then apply with that hash and the SAME `--token` and `--skip-file` flags. Always pass `--json`, so
the answer is one JSON object to read (`status`, `written`, `backup-dir`, `rollback`, or `code` and
`message`):

```bash
$PY "$FI" project-files --project . [--token <text>]... [--skip-file <file>]... --json --apply \
    --expect-sha256 <plan-sha256 of the second preview> [--confirm-narrowing]
```

Pass `--confirm-narrowing` on this apply only after the user said yes to the narrowing statement
(it is needed only when the 2d preview says `narrows` is true). The re-preview and the apply need no
further question, so the user confirms once.

- `changed-since-preview`: a file, the `--token` set or the `--skip-file` set changed after the
  preview. Run the preview of this step again with the same flags and take its new hash. If its
  diffs are the ones the user confirmed, apply with the new hash; if they differ, show what changed
  and ask again. Never reuse an old hash.
- `narrowing-unconfirmed`: the first tokens were not confirmed. Nothing was written. Ask again.
- `token-invalid`: the message names the rule (empty, too long, a control character, `too-short`,
  `generic-word`, `system-database` or `in-plugin-text`). Ask the user for another token.
- `write-failed`: nothing was written; every file replaced before the failure was restored.
  A `.claude` folder that is a link is refused the same way.

The files are written all together or not at all, and each changed file is first copied under
`backup-dir`. Print the `backup-dir` and the `rollback` line. If the project's `.gitignore` does not
cover `.claude/cache/` (the `gitignore-hint`), tell the user to add it.

Declining writes nothing. If no file is `inferred`, the script answers `nothing-to-do` and writes
nothing. Running the stage again changes nothing: the files it wrote are now authored.

## Stage 3: the hooks (Quick start step 5)

Registering hooks turns enforcement on. That is the user's decision, so this stage reports
first and writes only after a yes.

### 3a. Plan

```bash
$PY "$FI" hooks --project . --json
```

The script works out the **install mode** from files on disk. Branch on the answer's `mode`
field: a readiness report carries `mode: plugin`, and a settings plan carries
`install-mode: vendored`. A plugin that is installed but not enabled, next to a vendored
copy, is `vendored`: only the vendored hooks run. Managed settings and a settings file passed
on Claude Code's own command line are not read, and the answer's message says so.

### 3b. `mode` is `plugin`: report, write nothing

The plugin's own `hooks.json` registers the hooks, so a plugin install needs no registration
and the project's `settings.json` registers none of them (a hook registered in both places
runs twice). The answer is a readiness report. Tell the user, in plain words:

- **Ready to load is not live.** The report says what it checked and what it could not. Say
  both. Never say "the hooks are live".
- **Which gates are on.** Name the files in `gates`. The ones that block are the concept
  gate, the architecture guard and the two database guards. The strict shell gate and the
  code-search-first guard are add-ons: they are off unless the project installed them (see
  "Add-ons" below).
- **The environment variables.** Print the list in `kill-switches`. Most are kill switches,
  set by the user and never by an agent. Two are different: `CLAUDE_ACTIVE_CONTRACT` pins one
  approved contract, and `CLAUDE_DESTRUCTIVE_DB_OK` is a one-shot approval for one destructive
  database operation.
- **The database guards read the project's rules file.** Report `database-guard-rules` as it
  reads, but know that it describes the template shipped inside the plugin, which names the
  made-up databases `AcmeApp` and `AcmeApp_Testing`. The guards themselves never read that
  template: they read the project's own `.claude/hooks/db-destructive-guard.rules.json`. A
  project that has no such file (or an empty list) has every database protected, which is
  strict on purpose. The project names its real databases in that file.
- **The code-search-first note.** Print `code-search-first-note`. In short: the guard that
  makes a CodeGraph call come first is the `codegraph` add-on. It is off by default, so the
  plugin does not block source reads. `/auto-improve-codegraph-install` turns it on. Once on,
  the guard lets reads through when CodeGraph is unavailable, unless its session folder cannot be
  used, when it blocks and says why, and allows the identical retry of a blocked call once.
- **The add-ons.** Print the `add-ons` list from the report: each add-on's name and its
  install skill. Say they are opt-in and that this skill installs none of them.
- **The platform note.** If the answer has `platform-note` (macOS and Linux), say plainly
  that this command cannot fix it under a plugin install. The cached `hooks.json` launches
  `py -3`. The two options are to copy the hooks into the project instead (vendor them), or to
  wait for a per-platform hooks format.
- **What cannot be verified.** Print the fixed `not-verifiable` list. It is: that the running
  session loaded the hooks, that a project trust prompt was accepted, and that a hook's imports
  of its sibling helpers succeed at run time.

If a check failed (an unresolved command, a hook that does not compile, `disableAllHooks`, a
version mismatch, a missing launcher, a duplicate registration), name it. Do not write.

`hooks --apply` when `mode` is `plugin` is refused as `plugin-install-needs-no-registration`.
Do not try it.

### 3c. `install-mode` is `vendored`: show the diff, ask, write

1. Show the user the `hooks-json` path the registrations come from and the `plugin-root`
   (empty when the project's own `hooks.json` is the source), so a wrong pick is visible.
   Show the exact `unified-diff`. Say how many registrations will be added and how many were
   already present. Report any `notes`, such as a registration under a different matcher or a
   database guard that matches no PowerShell tool. Tell the user that every row the diff adds
   carries a short launcher program inside it (`py -3 -c <program> <class> <hook file>`), so the
   hook is still found if this session's project folder is removed; the long program text in each
   row is expected, and the README section "Project hook launcher" explains it.
2. Say plainly: **registration turns enforcement on, and it takes effect only in a NEW
   session.** This session keeps running without it.
3. Ask **once**: apply this change? If the user wants to leave a hook out, add
   `--skip <hook file name>` for each, **at preview time too**: the hash covers the skip list,
   so re-run the preview with the same `--skip` flags before asking.
4. On a yes, apply with the `plan-sha256` from the preview (not `source-sha256`, which is only the hash
   of the input file), and the SAME `--skip` list. Any difference in the skip list, the
   settings files, the source `hooks.json` or the platform is refused as `changed-since-preview`:

   ```bash
   $PY "$FI" hooks --project . --apply --expect-sha256 <plan-sha256 from the preview> [--skip <hook>]
   ```

   A `.claude/settings.json` that is a symbolic link is refused on apply as `write-failed`
   (the message says "symbolic link"); nothing is written. Tell the user to edit the file the
   link points to by hand. A preview through a link still works.

5. Print the `backup` path and the `rollback` line (one copy command that puts the old file
   back). Tell the user to add `.claude/settings.json.bak-*` to `.gitignore`.

Declining writes nothing. If the plan says nothing is missing, the script writes nothing and
there is no backup.

If the preview or the apply is refused as `project-hook-launcher-missing` (exit 3), the hooks
folder beside the scripts has no usable `_project_paths.py` with the Project hook launcher, so no
row can be written, whatever the plan would add. Nothing was changed and no backup was made. Tell
the user the file the message names (`<project>/.claude/hooks/_project_paths.py`) and that the
project's hooks folder must be brought to the same release as the scripts (copy the hooks
folder from that release). Then run the preview again. Never write
a row by hand to get past it.

### 3d. Any other mode: stop

`both`, `none`, `plugin-source`, `plugin-disabled` and `install-record-unreadable` each stop
with the script's named reason. Say the reason in plain words. Write nothing. For `both`,
every hook would run twice, so the user must remove one of the two registrations. That is
their decision, not this skill's.

## The project history record

The project's record of its design history is its **Project history record**. It is made of:

- the three registries the doctor seeds: `.claude/registries/MECHANISMS.md`, `VOCABULARY.md` and `JOURNAL.md`, and their domain skeletons `.claude/registries/MECHANISMS/general.md`, `VOCABULARY/general.md` and `JOURNAL/general.md`;
- `INTEGRATION.md` in the same folder, where the project keeps one (no seed exists for it, so the doctor never creates it);
- the concept contracts and follow-up stubs under `.claude/concepts/`;
- the Work Item Briefs under `.claude/work-items/`.

Who uses it, exactly:

- `/design-first` and the `data-architect` read it on every design.
- `/task` writes the brief, and the `data-architect` writes the contract.
- `/design-first` appends to `JOURNAL.md` only the critic findings the user confirmed (Steps 3 and 5).
- `fullstack-code-reviewer` appends on a justified contract divergence and, as janitor, to `MECHANISMS.md` and `VOCABULARY.md`.
- `/journal-add` appends a manual lesson.
- The contract-critic appends only its Critique section to the contract under review, and never writes a registry.

Tell the user to commit these files and never to delete, gitignore or bypass them. The Central Memory System, when a project switches it on through the `memory.*` profile slots, only supplements them: it never replaces or hides them, and a local entry wins a conflict until the user decides.

**The check: report first, then ask before the doctor writes anything.** Run the doctor in report mode, which writes nothing:

```bash
$PY "<dir of FI>/plugin_doctor.py" --project .
```

- If `plugin_doctor.py` prints `plugin:  NOT FOUND - pass --plugin`, say in one line that the registries cannot be seeded and ask for the plugin path. Offer `plugin_doctor.py --fix` only together with `--plugin <path>`.
- If `plugin_doctor.py` lists any `missing` entry, show the user that whole list as exactly what the fix would create. The fix creates every missing requirement in the doctor's list, not only the registries (for example `.claude/north-stars`, `.claude/orchestrator/results`, the contract template, `.claude/area-mapping.json`, `.claude/work-item-conventions.json` and `.claude/.project-tokens.json`). It never overwrites a file and leaves `.claude/settings.json` alone.
- Ask the user once whether to go ahead. Only after the user says yes, run:

  ```bash
  $PY "<dir of FI>/plugin_doctor.py" --fix
  ```

  Never run it on its own.
- If nothing is missing, say so and write nothing.

## Add-ons (opt-in, installed by their own skills)

Three optional add-ons ship with the plugin. None is registered by the plugin, and this skill
installs none of them. Each has its own skill, which previews first and writes only after a yes:

| Add-on | What it does | Its install skill |
|---|---|---|
| `angular-tailwind` | At each prompt, reminds the agent of the Angular and Tailwind CSS rules. | `/auto-improve-angular-tailwind-install` |
| `codegraph` | Blocks a source Read, Grep or Glob until a CodeGraph call has run in the turn, and lets reads through when CodeGraph is unavailable. Needs the CodeGraph MCP server. | `/auto-improve-codegraph-install` |
| `strict-shell-gate` | Reads each shell command before it runs and blocks a write into a source file that no approved contract covers. | `/auto-improve-strict-shell-gate-install` |

Only name them. Do not start one of them unless the user asks.

## Closing

End with a short summary:

- what was written (the profile slots, the step-3 files with their backup folder, the settings change and its backup path),
- what was **not** written, and why, and
- which Project history record files exist and which the doctor created, if the user agreed.

Then give the **first-session check**. In a NEW session, ask for an edit to a source file
that has no approved contract. The concept gate should block it. If it does not, the hooks
are not loaded in that session.

Say that running this skill again changes nothing: authored slots and authored step-3 files stay as
they are, and a settings file that already has every registration is not rewritten.

## Anti-patterns

- **Inferring or guessing a slot value yourself.** If the script did not propose it with
  evidence, ask the user or pass `none`.
- **Writing `settings.json` without the preview's `plan-sha256`**, or with an old one. The hash
  is what proves the user saw the change as it is now.
- **Treating "ready to load" as "live".** Only a running session shows that.
- **Reading or touching other plugins' entries.** Only `agentic-auto-improve` is in scope.
- **Hand-editing `settings.json` or the profile instead of using the script.** A typing
  mistake in `settings.json` can switch every check off, or block every action.
- **Asking one question per slot.** Show one table. Ask once.
- **Overwriting an authored slot or an authored step-3 file.** Show the difference and ask. The script will refuse anyway.
- **Proposing or typing a token the script did not list or the user did not name.** Only a `--token` the user named is ever written, and a wrong token can stop every outbound sync or change how shared memory behaves.
- **Treating the Central Memory System as the project's record, skipping the registries, or running the doctor's fix (`plugin_doctor.py --fix`) without asking.** The registries and the concept contracts are the record; the memory system only supplements them, and the doctor writes only after the user says yes.
- **Skipping the new-session warning.** The user will otherwise test in this session and
  conclude the hooks do nothing.

## When NOT to use

- To change a step-3 file the team already wrote, or to add tokens to a list that already has some.
  Stage 2 shows advice for such a file and leaves the edit to the team.
- To set the database guards' protected names. Use `/auto-improve-database-guard-install`.
- To set up the sync configuration. That is Quick start step 6.
- To change how a hook behaves. To give the database guards the project's own database
  names, use `/auto-improve-database-guard-install`.
- To register hooks for Cursor or Codex. Hooks are Claude-only in this release.
- Inside the plugin's own checkout. The script refuses it as `plugin-source-checkout`.
