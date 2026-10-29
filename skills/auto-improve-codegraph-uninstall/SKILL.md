---
name: auto-improve-codegraph-uninstall
description: "Remove the codegraph add-on of the agentic-auto-improve plugin from this project: the three settings.json rows of the code-search-first guard, then its three hook files. Previews every row and file, asks for one confirmation, then writes: rows first with a backup, then the files. Keeps any hook file you edited, and keeps the shared helpers. Leaves the CLAUDE_SKIP_CG kill switch as it is. The name carries the plugin name because you may have several plugins installed. Use when: user says /auto-improve-codegraph-uninstall, 'remove the codegraph add-on', 'turn off the code-search-first guard', or 'uninstall the CodeGraph gate'. Never deletes a helper."
user_invocable: true
---

# /auto-improve-codegraph-uninstall — remove the codegraph add-on

This skill takes the `codegraph` add-on out of a project: the three rows in `.claude/settings.json` (`PreToolUse` on `Read|Grep|Glob`, `UserPromptSubmit`, and `PostToolUse` on the CodeGraph tools) and the three hook files `codegraph-first-guard.py`, `codegraph-turn-reset.py` and `codegraph-turn-tracker.py` in `.claude/hooks/`.

This skill proposes first. It writes only after one yes, and it reads and touches only `agentic-auto-improve`.

## The rule that shapes everything here

**The skill carries the conversation. The script carries every rule.**

Which rows match, which files are deleted, which are kept and in which order everything is written all live in `auto_improve_finish_install.py addon-remove`, which has its own test suite. Read its answer. Do not work any of it out yourself, and never delete a hook file or edit `settings.json` by hand to remove this add-on: a hook row that points at a missing script exits 2 and blocks every prompt (and here, every source read). The script writes `settings.json` first, with a backup, and deletes a file last.

What the script will not do:

- It deletes a hook file only when it is identical to the plugin's copy (line endings and a leading byte order mark are ignored). A file you edited is kept and reported as `kept-differs`; its row is still removed.
- It keeps a hook file that a `settings.local.json` or user settings row still names (`kept-referenced`).
- It never deletes a helper. `_project_paths.py` and `_error_log.py` stay: other hooks use them.
- It does not touch the `CLAUDE_SKIP_CG` kill switch, and it does not delete `.claude/.codegraph-used-this-turn`. That sentinel is a leftover of a turn; the user may delete it.

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

Every command below is `$PY "$FI" addon-remove --name codegraph --project . ...`.

## Step 1: Preview (writes nothing)

```bash
$PY "$FI" addon-remove --name codegraph --project . --json
```

The answer carries:

- `rows`: every `settings.json` row it would remove, with its `event`, `matcher`, `file` and the `command` as written. A row matches by the hook file name, under any event and in any form.
- `files`: each hook file with its action: `delete`, `kept-differs`, `kept-referenced` or `absent`.
- `kept`: what it leaves, each with the reason: the two helpers, and every file it kept.
- `kill-switches`: `CLAUDE_SKIP_CG`. It is named only; the script never changes it.
- `profile` (`null` for this add-on), `uninstall-skill`, `target`, `plugin-root` and `plan-sha256`.

**Keep `plan-sha256`.** The apply needs it as `--expect-sha256`. It covers the `settings.json` bytes and the project's bytes of every file to delete, so anything that moves between the preview and the write is refused as `changed-since-preview`.

If `rows` is empty and every file is `absent`, the add-on is not installed. Say so and stop.

## Step 2: Show the plan and ask once

Show the user, in plain words:

- the rows it would remove from `.claude/settings.json`, and that a backup is taken first.
- the files it would delete, and the files it would keep with the reason.
- what it leaves: the helpers, and the `CLAUDE_SKIP_CG` switch.
- that after the removal a source `Read`, `Grep` or `Glob` is no longer held back until a CodeGraph tool has run.

State your recommendation first, in one or two sentences. Then ask **once**: remove this add-on?

Declining writes nothing.

## Step 3: Apply

On a yes, apply with the `plan-sha256` from the preview:

```bash
$PY "$FI" addon-remove --name codegraph --project . --apply --expect-sha256 <plan-sha256 from the preview>
```

The answer lists `removed-rows`, `deleted`, `kept` and the `backup` path. Tell the user to **start a new session**: Claude Code reads the hook rows once, when a session starts, so this session still runs the guard until then.

If the answer says `nothing-to-do`, the add-on was not installed. Nothing was written. Running the skill again after a removal changes nothing.

### Refusals

Exit `2` is a refusal you can correct. Exit `3` is an environment problem. On either, read `code` and `message`, tell the user the reason in one plain sentence, and stop. A refusal always means nothing was changed. The ones you may see:

- `changed-since-preview`: something moved after the preview. Go back to the preview, show the new plan, and ask again. Never reuse the old hash.
- `malformed-settings` or `unexpected-settings-shape`: `settings.json` is not plain enough to edit safely. Nothing was written. Name the file and the reason, and tell the user to remove the three rows by hand, then run this skill again.
- `write-failed`: for example `.claude/settings.json` is a symbolic link, or `.claude` or `.claude/hooks` is a link (a junction on Windows) to another folder. Nothing was written, or the message says what was done before the failure. Tell the user to edit the file the link points to by hand.
- `plugin-source-checkout`: this folder is the plugin's own checkout. Run it in a project that uses the plugin.
- `addon-unknown`: the name matches no add-on folder in the plugin.

## Closing

End with a short summary: which rows were removed, which files were deleted, which were kept and why, and the backup path. Then repeat the new-session note. Say that the helpers were left on purpose, and that the install skill, `/auto-improve-codegraph-install`, puts the add-on back.

## Anti-patterns

- **Deleting a hook file yourself before its row is gone.** A row that points at a missing script blocks every prompt. The script removes the rows first.
- **Hand-editing `settings.json` instead of using the script.**
- **Writing without the preview's `plan-sha256`**, or with an old one. The hash is what proves the user saw the change as it is now.
- **Unsetting `CLAUDE_SKIP_CG` or setting it for the user.** The script leaves it as it is.
- **Deleting a kept file because the script kept it.** A `kept-differs` file may hold the team's edits.
- **Skipping the new-session note.** The user will otherwise test in this session and conclude the guard is still on.

## When NOT to use

- To install the add-on. That is `/auto-improve-codegraph-install`.
- To pause the guard for one turn. That is the user's own `CLAUDE_SKIP_CG`, which this skill never sets.
- Inside the plugin's own checkout. The script refuses it as `plugin-source-checkout`.
- On Cursor or Codex. Hooks are Claude-only in this release.
