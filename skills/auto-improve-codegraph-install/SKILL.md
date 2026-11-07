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
plugin's copy, with one exception: a hook that is an unedited copy of an older release is backed up
and replaced (the upgrade, below). It copies a helper file only when the project lacks it.

## Step 0: Find the script

Find the script through the plugin install **only**. A copy under the project's own `.claude/scripts/` is never used here: a vendored installer can be older than the hooks it manages, so it
would hide a stale hook, or write a stale row (one without its `if`). Without a separate plugin install the install, the removal and the check already refuse, so nothing is lost. Test the places **in this order** and keep the first hit. Do not use
`ls` on all the paths: `ls` sorts its operands, so the order you meant is lost.

```bash
FIP=
S=.claude/scripts/auto_improve_finish_install.py
if [ -n "$CLAUDE_PLUGIN_ROOT" ] && [ -f "$CLAUDE_PLUGIN_ROOT/$S" ]; then FIP=$CLAUDE_PLUGIN_ROOT/$S
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
  FIP=$({ printf '%s\n' "$MINE"; printf '%s\n' "$REC" | grep '"scope" *: *"user"'; } | sed -n 's/.*"installPath" *: *"\([^"]*\)".*/\1/p' | { cat; printf '%s\n' "$NEWEST"; } | while IFS= read -r D; do
    [ -n "$D" ] && [ -f "${D%/}/$S" ] && { printf '%s\n' "${D%/}/$S"; break; }
  done)
fi
py -3 "$FIP" --help   # macOS and Linux: python3 "$FIP" --help
```

**If `FIP` is empty, stop and say so.** Say that the script was not found in
`$CLAUDE_PLUGIN_ROOT` or in the plugin cache. Then stop. Without the script there is nothing
to run, and a skill that guesses is worse than one that stops.

Pick the launcher once and reuse it. On Windows use `py -3`. On macOS and Linux use
`python3`. The rest of this file writes it as `PY`.

```bash
PY="py -3"        # Windows
PY="python3"      # macOS and Linux
```

Every command below is `$PY "$FIP" addon --name codegraph --project . ...`.

## What this add-on does

Three hooks, with four rows, work together:

- `codegraph-first-guard.py` runs before `Read`, `Grep` and `Glob`. It blocks a call on a source-code path while no CodeGraph tool has run in this turn. Markdown, JSON, YAML and a few other file kinds are always allowed.
- `codegraph-turn-tracker.py` runs after any successful `mcp__codegraph__*` tool, and after a successful `codegraph query|explore|context|node|callers|callees|impact|files ...` command in the Bash tool (the command-line route; a second row, `PostToolUse` on `Bash` with `if: "Bash(codegraph *)"` and the argument `cli`). It writes the marker `turn.json` in the session's folder under the system temp folder (`auto-improve-codegraph-<session id>/`), which opens the gate. The marker belongs to the session, so a `cd` or `EnterWorktree` does not close the gate again. A failed call never opens the gate.
- `codegraph-turn-reset.py` runs at each new prompt and deletes the marker and any retry ticket, so every turn starts closed. Once per session it also prunes old session folders in the temp folder. It also runs the **connection notice**: when the server is configured and the index exists but no `codegraph serve --mcp` process belongs to this session, it tells the user and the model that the MCP connection is likely gone (`/mcp` can reconnect it) and that a command such as `codegraph explore "SymbolName"` in the Bash tool opens the gate meanwhile. It is silent on a healthy session, never blocks, and yields to a project instruction or a skill's gate that forbids shell commands.

**The command-line route.** When the MCP tools are gone but the `codegraph` program works, the block message names a copyable command, `codegraph explore "<term>"`. Run it on its own: no pipe, no `&&`, no `cd`, no variable prefix, nothing after an optional `2>&1`. A command that is not in that plain form, or that fails, opens nothing. In a worktree the command line reads the main checkout's index unless one was built there. The first time such a call opens the gate in a session with no successful MCP call, the tracker logs one `cli-fallback` record (`reason: mcp-unavailable`).

**The notice can be wrong on the first prompt.** A server that is still starting may not be visible yet, so on the first prompt of a session the notice can appear although the server is fine. That is accepted: it is one message, it never blocks, and `/mcp` shows the real state. On an install of Claude Code the notice does not know (another host program), it stays silent.

It needs two helpers, `.claude/hooks/_project_paths.py` and `.claude/hooks/_error_log.py`, which the install copies only if the project lacks them.

**The guard is a nudge, never a wall.** It lets a read through, prints one `allowed (fail-open:<reason>)` line and logs it, when CodeGraph is provably unavailable. There are five reasons: `no-index` (no `.codegraph/codegraph.db` in the project, its parents or the main checkout; a `.codegraph` folder without `codegraph.db` is not an index), `index-other-tree` (a linked worktree with no index of its own, whose only index belongs to the main checkout), `server-not-configured`, `server-disabled`, and `subagent`. In any other session with no CodeGraph tool, **repeat the identical blocked call once**: it is allowed and logged as a retry escape, and the next prompt clears it.

**Shadow mode.** The guard also measures itself. On every call it reads the session transcript, works out what it would have decided from the transcript alone, and appends one record to `<project>/.claude/logs/codegraph-shadow.jsonl` (the project is `CLAUDE_PROJECT_DIR`; with that variable unset nothing is written). The record holds classes, booleans and hash prefixes only, never a path or prompt text. The shadow enforces nothing and anything it raises is swallowed, so the live outcome never changes. It rides on the guard's own `PreToolUse` row: **no new row, hook or manifest key is installed for it**, and every install age gets it by taking the new guard file. Read the log with the read-only report, which writes nothing:

```bash
$PY .claude/scripts/codegraph_shadow_report.py [--project <dir>] [--json]
```

It exits `2` when the log is missing or unreadable (never an empty "agree"). Every count is a lower bound, because the guard appends without a lock. The log is not removed by the uninstall.

**The permission entry.** The install also adds `mcp__codegraph__*` to the project's `permissions.allow`, inside the same preview and plan hash (the preview's `permissions-allow` field and its `unified-diff` show it). It never adds a single tool's name. The uninstall keeps the entry.

## If the CodeGraph MCP server is not configured

**Stop, and say so plainly.** When the preview comes back refused as `codegraph-mcp-not-configured`
(exit `2`), tell the user in these words or close to them:

> The CodeGraph server is not configured in this project, so I did not install the add-on. With
> no server the guard would have nothing to ask first, and an installed guard that can never be
> satisfied only adds a blocked round trip. Nothing was written. Configure the CodeGraph MCP
> server first, then run this again.

Do not install the add-on anyway. Do not edit `.mcp.json` yourself. Do not offer a way around
the check. The server's setup is the user's decision.

The script checks that the server is configured as a real entry (a non-empty `command` or `url`)
and that no settings layer lists it in `disabledMcpjsonServers`. It does not check that the
server is running. A server that is configured but not running leaves the guard asking for a
tool that is not there (the retry escape lets the read through), so remind the user that the server must be running. The refusal message names which
condition failed: no entry, an entry that starts no server, or a server listed as disabled.

When the server is defined only in the project's `.mcp.json` and no setting approves it
(`enabledMcpjsonServers` or `enableAllProjectMcpServers`), the preview does not refuse. It
carries one note saying so. Pass that note on to the user: Claude Code asks for approval when a
session starts, and until the server is approved the guard would ask for a tool that is not there.

## Step 1: Preview (writes nothing)

```bash
$PY "$FIP" addon --name codegraph --project . --json
```

The answer carries `files` (each file with its action: `copy`, `present`, `update` or `keep-existing`),
`to-add` (the settings rows it would write), `already-present`, `unified-diff` (the exact change
to `.claude/settings.json`), `notes`, `kill-switches`, `target`, `plugin-root` and `plan-sha256`.
**Keep `plan-sha256`.** The apply needs it as `--expect-sha256`. It covers the settings bytes, the
text the write would produce and every file the install would copy, so anything that moves
between the preview and the write is refused as `changed-since-preview`.

**The preview checks for the CodeGraph MCP server first.** The script looks for a server named `codegraph` in the project's `.mcp.json`, in the user's Claude configuration file (`.claude.json`), and in that file's entry for this project. It refuses as `codegraph-mcp-not-configured` when it finds none, when the entry has no `command` and no `url`, or when a settings layer lists the server in `disabledMcpjsonServers`. Follow the section above.

## Step 2: Show the plan and ask once

Show the user, in plain words:

- the files it would copy into `.claude/hooks/` (and any helper into `.claude/hooks/` or
  `.claude/scripts/`), with the action for each. A file marked `present` is already identical
  and is not touched. A file marked `update` is an unedited older release: say it will be saved as
  `<hook>.bak-<UTC stamp>` and replaced. A helper marked `keep-existing` is kept as it is.
- the exact `unified-diff` for `.claude/settings.json`, and how many rows it adds.
- that the add-on has no kill switch (`kill-switches` is an empty list): the way out is `/auto-improve-codegraph-uninstall`.
- the permission entry: `permissions-allow` lists `mcp__codegraph__*` under `add` (or `already-listed`).
- any `notes`. **Relay the index note** if there is one: "no index: the guard lets every read through until one exists" or "the index at <main>/.codegraph belongs to the main checkout, so the guard lets reads through in this worktree" (a `.codegraph` folder with no `codegraph.db` is "not an index"). When the note says there is no index, or that the index belongs to the main checkout, **offer once** to run `codegraph init -i` in this working tree, and run it only on a yes. An index of its own brings the gate back here. Say that a new session is needed for the guard to see the new index.

State your recommendation first, in one or two sentences. Then ask **once**: install this
add-on?

Say plainly: **the new rows take effect only in a NEW session.** Claude Code reads the hook rows
once, when a session starts, so this session keeps running without them.

Declining writes nothing.

## Step 3: Apply

On a yes, apply with the `plan-sha256` from the preview:

```bash
$PY "$FIP" addon --name codegraph --project . --apply --expect-sha256 <plan-sha256 from the preview>
```

The script copies the hook files first and writes the rows last, so a row never points at a file
that is not there. It takes a timestamped backup of `.claude/settings.json` before it replaces
it. Print the `backup` path and the `rollback` line (one copy command that puts the old file
back). Tell the user to add `.claude/settings.json.bak-*` to `.gitignore`.

If the answer says `nothing-to-do`, the add-on was already installed. Nothing was written.

The guard has no bypass variable. In a session with no `mcp__codegraph__*` tool, repeat the blocked call once (the retry escape) and it is allowed and logged; `/auto-improve-codegraph-uninstall` followed by a new session takes the guard out.

**Upgrading an older install: re-run this skill.** No uninstall and no hand edit is needed. A hook file in the project whose line-ending-folded hash is listed in the add-on's `released_sha256` is an unedited copy of an older release. The preview marks it `update` (not `addon-file-differs`) and adds a note naming it; the apply saves it as `<hook>.bak-<UTC stamp>` beside it, then replaces it with the plugin's copy. The `update` sits inside the same `plan-sha256`: a file that changed between the preview and the apply is refused as `changed-since-preview`. A link is never replaced. A hook you edited is still refused as `addon-file-differs`, and the message names the file and the route: run `/auto-improve-codegraph-uninstall` (it keeps an edited file), rename or remove the file by hand, then run this skill again. After an update tell the user the backups are in `.claude/hooks/` (`*.bak-*` may be deleted once the new guard is trusted), and to start a new session. `addon --name codegraph --check` then confirms the permission entry. The answer of the apply lists `updated` and `file-backups`.

What an install of each age holds, so the preview is read correctly:

- **0.9.9 to 0.15.1:** three rows (`PreToolUse` on `Read|Grep|Glob`, `UserPromptSubmit`, `PostToolUse` on `mcp__codegraph__.*`), the older hook files, and no `mcp__codegraph__*` entry in `permissions.allow`. The earliest of these releases declared a kill switch (`CLAUDE_SKIP_CG`); none exists now. The re-run shows those three rows as `already-present`, the hook files as `update`, the permission entry under `permissions-allow.add`, and the Bash row (`cli`) under `to-add`.
- **0.15.2 to 0.16.1:** the same three rows and the permission entry. The re-run updates the hook files and adds exactly one row, the tracker's Bash row (`PostToolUse` on `Bash`, argument `cli`, `if: "Bash(codegraph *)"`). The 0.16.1 row of this list is the one most installs are at.
- **Current (0.16.2):** four rows; every file `present`; the re-run writes nothing.

A row is never rewritten by an upgrade; only files are replaced and a missing row is added. A Bash row that an older installer wrote without its `if` is reported by `addon --check` as `addon-row-outdated`: run `/auto-improve-codegraph-uninstall`, then this skill again.

**A project with a Hook registration profile** (one recorded with `record-registrations`) must re-record it after this install, because the profile counts the rows and the install added a fourth: `$PY "$FIP" record-registrations --project .` to preview, then the same command with `--apply --expect-sha256 <plan hash>`. Otherwise its row-count check fails.

A project with a CodeGraph index builds it with the `codegraph` command line tool (`codegraph init -i`). This skill does not build the index.

### Refusals

Exit `2` is a refusal you can correct. Exit `3` is an environment problem, such as an add-on
folder with no `addon.json`. On either, read `code` and `message`, tell the user the reason in
one plain sentence, and stop. A refusal always means nothing was changed. The ones you may see:

- `addon-file-differs`: a hook file of this add-on already exists in the project, is not the
  plugin's copy and is not an unedited released copy (those are updated, see above). Name the file. The script will not
  overwrite it. The user compares it with the plugin's copy, runs `/auto-improve-codegraph-uninstall`
  (which keeps an edited file), renames or removes the file by hand, then runs this skill again.
- `changed-since-preview`: something moved after the preview. Go back to the preview, show the
  new plan, and ask again. Never reuse the old hash.
- `write-failed`: for example `.claude/settings.json` is a symbolic link, or `.claude` or
  `.claude/hooks` is a link (a junction on Windows) to another folder. Nothing was written.
  Tell the user to edit the file the link points to by hand, or to replace the link with a real folder.
- `codegraph-tool-named` (exit `2`): a settings layer's `permissions.allow` names an individual CodeGraph tool. The message lists each entry and the file it is in. The user replaces it with `mcp__codegraph__*` by hand, then runs this again. Nothing was written.
- `plugin-source-checkout`: this folder is the plugin's own checkout. Install an add-on in a
  project that uses the plugin instead.
- `addon-unknown`: the name matches no add-on folder in the plugin.

## How to remove it

This install never removes anything. The removal is its own skill, `/auto-improve-codegraph-uninstall`. It previews, asks once, then removes the three `settings.json` rows (with a backup) and only then the three hook files. It keeps a hook file you edited, leaves `_project_paths.py` and `_error_log.py` because other hooks use them, and keeps the `mcp__codegraph__*` permission entry (listed under `kept`). The only leftover is the session folder in the system temp folder, which the reset hook prunes; an older `.claude/.codegraph-used-this-turn`, if it exists, is a leftover of a turn that the user may delete.

Do not delete the hook files or the rows by hand while the hooks can run: a row that points at a missing script blocks every prompt. Only when a hook cannot run (the README table, section "Ways out when a hook cannot run") does the user remove its row by hand.

## Closing

End with a short summary: what was copied, which rows were added, the backup path, and what was
**not** written and why. Then repeat the new-session warning. Say that running this skill again
changes nothing: identical files are left alone and a row that is already there is not written
twice.

## Anti-patterns

- **Installing without the server.** The script refuses. Do not look for a way around it.
- **Telling the user to set a bypass variable.** The guard has none; the way out is the uninstall skill.

- **Writing `settings.json` without the preview's `plan-sha256`**, or with an old one. The hash
  is what proves the user saw the change as it is now.
- **Hand-editing `settings.json` instead of using the script.**
- **Overwriting a hook file that differs.** The script refuses; do not copy over it yourself.
- **Skipping the new-session warning.** The user will otherwise test in this session and
  conclude the add-on does nothing.

## When NOT to use

- To index the code. That is `codegraph init -i`, run by the user.
- To bypass the guard for a turn. There is no bypass variable; call a CodeGraph tool, repeat the blocked call once (the retry escape), or remove the add-on with `/auto-improve-codegraph-uninstall`.
- Inside the plugin's own checkout. The script refuses it as `plugin-source-checkout`.
- On Cursor or Codex. Hooks are Claude-only in this release.
