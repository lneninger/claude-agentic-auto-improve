---
name: auto-improve-finish-install
description: "Finish installing the agentic-auto-improve plugin in this project: fill in the project profile (Quick start step 4) and check or register the hooks (Quick start step 5). Looks at the repository, shows each proposed value with its evidence, asks for one confirmation, and writes only slots that are still placeholders. For the hooks it first works out how the plugin reached this project, then reports readiness (plugin install) or shows the exact settings.json change and writes it only after a yes (vendored copy). The name carries the plugin name because you may have several plugins installed. Use when: user says /auto-improve-finish-install, 'finish installing the auto-improve plugin', 'finish the agentic-auto-improve install', 'set up the project profile', 'fill in the project profile', 'register the hooks', or 'are the auto-improve hooks on'. Never guesses a value and never overwrites an authored slot."
user_invocable: true
---

# /auto-improve-finish-install — finish the last two Quick start steps

The plugin cannot copy two things for you. One is the project profile, which describes
**your** repository. The other is the hook registration, which switches enforcement on.

This skill walks you through both. It proposes, you confirm, and only then does it write.

```
/auto-improve-finish-install
   Stage 1  project profile   propose -> one confirmation -> write the placeholder slots
   Stage 2  hooks             plugin install:  report readiness, write nothing
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
if   [ -f ".claude/scripts/auto_improve_finish_install.py" ]; then
  FI=".claude/scripts/auto_improve_finish_install.py"
elif [ -n "$CLAUDE_PLUGIN_ROOT" ] && [ -f "$CLAUDE_PLUGIN_ROOT/.claude/scripts/auto_improve_finish_install.py" ]; then
  FI="$CLAUDE_PLUGIN_ROOT/.claude/scripts/auto_improve_finish_install.py"
else
  # The provider cache under the Claude home (CLAUDE_CONFIG_DIR when set, else ~/.claude).
  # Newest version first (a version sort, so 0.10.0 beats 0.9.0).
  for d in $(ls -d "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"/plugins/cache/*/agentic-auto-improve/*/ 2>/dev/null | sort -rV); do
    if [ -f "${d}.claude/scripts/auto_improve_finish_install.py" ]; then
      FI="${d}.claude/scripts/auto_improve_finish_install.py"
      break
    fi
  done
fi
echo "FI=$FI"
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

Every command below is `$PY "$FI" <profile|hooks> --project . ...`.

**Exit codes.** `0` means a plan, an apply or nothing to do. `2` means a refusal you can
correct. `3` means an environment problem, such as a missing template. On `2` or `3`, read
the `code` and `message` fields, tell the user the reason in one plain sentence, and stop.
A refusal always means nothing was changed.

### Which provider is this?

Hooks are Claude-only in this release. On **Cursor** and **Codex**, run Stage 1 in full, then
run `hooks --provider cursor` (or `codex`). It returns `provider-has-no-hooks`. Say that hooks
are Claude-only here, that nothing was written, and stop. The profile is the same on all
three providers.

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

## Stage 2: the hooks (Quick start step 5)

Registering hooks turns enforcement on. That is the user's decision, so this stage reports
first and writes only after a yes.

### 2a. Plan

```bash
$PY "$FI" hooks --project . --json
```

The script works out the **install mode** from files on disk. Branch on the answer's `mode`
field: a readiness report carries `mode: plugin`, and a settings plan carries
`install-mode: vendored`. A plugin that is installed but not enabled, next to a vendored
copy, is `vendored`: only the vendored hooks run. Managed settings and a settings file passed
on Claude Code's own command line are not read, and the answer's message says so.

### 2b. `mode` is `plugin`: report, write nothing

The plugin's own `hooks.json` registers the hooks, so a plugin install needs no registration
and the project's `settings.json` registers none of them (a hook registered in both places
runs twice). The answer is a readiness report. Tell the user, in plain words:

- **Ready to load is not live.** The report says what it checked and what it could not. Say
  both. Never say "the hooks are live".
- **Which gates are on.** Name the files in `gates`. The ones that block are the concept
  gate, the architecture guard and the two database guards. The bash gate and the
  code-search-first guard were retired in 0.7.0.
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
- **The code-search-first note.** Print `code-search-first-note`. In short: the check was
  retired in 0.7.0, the plugin no longer blocks source reads, and no CodeGraph tool has to run
  first, so there is nothing to bypass.
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

### 2c. `install-mode` is `vendored`: show the diff, ask, write

1. Show the user the `hooks-json` path the registrations come from and the `plugin-root`
   (empty when the project's own `hooks.json` is the source), so a wrong pick is visible.
   Show the exact `unified-diff`. Say how many registrations will be added and how many were
   already present. Report any `notes`, such as a registration under a different matcher or a
   database guard that matches no PowerShell tool.
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

### 2d. Any other mode: stop

`both`, `none`, `plugin-source`, `plugin-disabled` and `install-record-unreadable` each stop
with the script's named reason. Say the reason in plain words. Write nothing. For `both`,
every hook would run twice, so the user must remove one of the two registrations. That is
their decision, not this skill's.

## Closing

End with a short summary:

- what was written (the profile slots, the settings change and the backup path), and
- what was **not** written, and why.

Then give the **first-session check**. In a NEW session, ask for an edit to a source file
that has no approved contract. The concept gate should block it. If it does not, the hooks
are not loaded in that session.

Say that running this skill again changes nothing: authored slots stay as they are, and a
settings file that already has every registration is not rewritten.

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
- **Overwriting an authored slot.** Show the difference and ask. The script will refuse anyway.
- **Skipping the new-session warning.** The user will otherwise test in this session and
  conclude the hooks do nothing.

## When NOT to use

- To finish the other per-project files (the area map, the title conventions, the protected
  names list). This skill does not fill them. They are Quick start step 3.
- To set up the sync configuration. That is Quick start step 6.
- To change how a hook behaves, or to give the database guards the project's own database
  names under a plugin install.
- To register hooks for Cursor or Codex. Hooks are Claude-only in this release.
- Inside the plugin's own checkout. The script refuses it as `plugin-source-checkout`.
