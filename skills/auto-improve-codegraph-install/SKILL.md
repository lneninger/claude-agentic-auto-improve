---
name: auto-improve-codegraph-install
description: "Install the codegraph add-on of the agentic-auto-improve plugin in this project: three hooks that block a source Read, Grep or Glob until a CodeGraph tool has run in the same turn. Needs the CodeGraph MCP server; stops and says so plainly when it is not configured. Previews the files and the settings.json change, asks for one confirmation, then writes. The name carries the plugin name because you may have several plugins installed. Use when: user says /auto-improve-codegraph-install, 'install the codegraph add-on', 'turn on the code-search-first guard', or 'make CodeGraph come first'. Never overwrites a file that differs and never removes a row."
user_invocable: true
---

# /auto-improve-codegraph-install — install the codegraph add-on

The `codegraph` add-on makes a CodeGraph call come first. Once it is installed, the agent cannot read a source file until it has asked CodeGraph a question in the same turn. Nothing registers it by default.

This skill proposes first. It writes only after one yes, and it reads and touches only
`agentic-auto-improve`.

## The rule that shapes everything here

**The skill carries the conversation. The script carries every rule.**

Which files are copied, which rows are written, what is already there, and what is refused all
live in `auto_improve_finish_install.py addon`, which has its own test suite. Read its answer.
Do not work any of it out yourself, and never edit `settings.json` by hand to install this
add-on: a typing mistake there can switch every check off, or block every action.

The script never removes a row or a file. It never overwrites a file that differs from the
plugin's copy. It copies a helper file only when the project lacks it.

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

Every command below is `$PY "$FI" addon --name codegraph --project . ...`.

## What this add-on does

Three hooks work together:

- `codegraph-first-guard.py` runs before `Read`, `Grep` and `Glob`. It blocks a call on a source-code path while no CodeGraph tool has run in this turn. Markdown, JSON, YAML and a few other file kinds are always allowed.
- `codegraph-turn-tracker.py` runs after any `mcp__codegraph__*` tool. It writes the marker file `.claude/.codegraph-used-this-turn`, which opens the gate.
- `codegraph-turn-reset.py` runs at each new prompt and deletes the marker, so every turn starts closed.

It needs two helpers, `.claude/hooks/_project_paths.py` and `.claude/hooks/_error_log.py`, which the install copies only if the project lacks them.

## If the CodeGraph MCP server is not configured

**Stop, and say so plainly.** When the preview comes back refused as `codegraph-mcp-not-configured`
(exit `2`), tell the user in these words or close to them:

> The CodeGraph server is not configured in this project, so I did not install the add-on. With
> the gate installed and no server, every source Read, Grep and Glob would be blocked and the
> agent would have no way to satisfy it. Nothing was written. Configure the CodeGraph MCP server
> first, then run this again.

Do not install the add-on anyway. Do not edit `.mcp.json` yourself. Do not offer a way around
the check. The server's setup is the user's decision.

The script only checks that the server is configured, not that it is running. A server that is
configured but not running still blocks every source read at run time, so remind the user that
the server must be running.

## Step 1: Preview (writes nothing)

```bash
$PY "$FI" addon --name codegraph --project . --json
```

The answer carries `files` (each file with its action: `copy`, `present` or `keep-existing`),
`to-add` (the settings rows it would write), `already-present`, `unified-diff` (the exact change
to `.claude/settings.json`), `notes`, `kill-switches`, `target`, `plugin-root` and `plan-sha256`.
**Keep `plan-sha256`.** The apply needs it as `--expect-sha256`. It covers the settings bytes, the
text the write would produce and every file the install would copy, so anything that moves
between the preview and the write is refused as `changed-since-preview`.

**The preview checks for the CodeGraph MCP server first.** The script looks for a server named `codegraph` in the project's `.mcp.json`, in the user's Claude configuration file (`.claude.json`), and in that file's entry for this project. If it finds none, it refuses as `codegraph-mcp-not-configured`. Follow the section above.

## Step 2: Show the plan and ask once

Show the user, in plain words:

- the files it would copy into `.claude/hooks/` (and any helper into `.claude/hooks/` or
  `.claude/scripts/`), with the action for each. A file marked `present` is already identical
  and is not touched. A helper marked `keep-existing` is kept as it is.
- the exact `unified-diff` for `.claude/settings.json`, and how many rows it adds.
- the kill switches from `kill-switches`. They are set by the user and never by an agent.
- any `notes`.

State your recommendation first, in one or two sentences. Then ask **once**: install this
add-on?

Say plainly: **the new rows take effect only in a NEW session.** Claude Code reads the hook rows
once, when a session starts, so this session keeps running without them.

Declining writes nothing.

## Step 3: Apply

On a yes, apply with the `plan-sha256` from the preview:

```bash
$PY "$FI" addon --name codegraph --project . --apply --expect-sha256 <plan-sha256 from the preview>
```

The script copies the hook files first and writes the rows last, so a row never points at a file
that is not there. It takes a timestamped backup of `.claude/settings.json` before it replaces
it. Print the `backup` path and the `rollback` line (one copy command that puts the old file
back). Tell the user to add `.claude/settings.json.bak-*` to `.gitignore`.

If the answer says `nothing-to-do`, the add-on was already installed. Nothing was written.

To bypass the guard for one session, the user sets `CLAUDE_SKIP_CG=1`. The agent never sets it.

A project with a CodeGraph index builds it with the `codegraph` command line tool (`codegraph init -i`). This skill does not build the index.

### Refusals

Exit `2` is a refusal you can correct. Exit `3` is an environment problem, such as an add-on
folder with no `addon.json`. On either, read `code` and `message`, tell the user the reason in
one plain sentence, and stop. A refusal always means nothing was changed. The ones you may see:

- `addon-file-differs`: a hook file of this add-on already exists in the project and is not the
  plugin's copy. Name the file. The script will not overwrite it. The user compares it with the
  plugin's copy and renames or removes it by hand, then runs this skill again.
- `changed-since-preview`: something moved after the preview. Go back to the preview, show the
  new plan, and ask again. Never reuse the old hash.
- `write-failed`: for example `.claude/settings.json` is a symbolic link. Nothing was written.
  Tell the user to edit the file the link points to by hand.
- `plugin-source-checkout`: this folder is the plugin's own checkout. Install an add-on in a
  project that uses the plugin instead.
- `addon-unknown`: the name matches no add-on folder in the plugin.

## How to remove it

The script never removes anything, so removal is by hand:

1. Open `.claude/settings.json` and delete the three entries whose `args` name `codegraph-first-guard.py`, `codegraph-turn-tracker.py` and `codegraph-turn-reset.py`.
2. Delete those three files from `.claude/hooks/`, and `.claude/.codegraph-used-this-turn` if it exists.
3. Leave `_project_paths.py` and `_error_log.py`: other hooks use them.

## Closing

End with a short summary: what was copied, which rows were added, the backup path, and what was
**not** written and why. Then repeat the new-session warning. Say that running this skill again
changes nothing: identical files are left alone and a row that is already there is not written
twice.

## Anti-patterns

- **Installing without the server.** The script refuses. Do not look for a way around it.
- **Setting `CLAUDE_SKIP_CG` for the user.** It is the user's escape hatch, never an agent's.

- **Writing `settings.json` without the preview's `plan-sha256`**, or with an old one. The hash
  is what proves the user saw the change as it is now.
- **Hand-editing `settings.json` instead of using the script.**
- **Overwriting a hook file that differs.** The script refuses; do not copy over it yourself.
- **Skipping the new-session warning.** The user will otherwise test in this session and
  conclude the add-on does nothing.

## When NOT to use

- To index the code. That is `codegraph init -i`, run by the user.
- To bypass the guard for a turn. That is `CLAUDE_SKIP_CG`, set by the user.
- Inside the plugin's own checkout. The script refuses it as `plugin-source-checkout`.
- On Cursor or Codex. Hooks are Claude-only in this release.
