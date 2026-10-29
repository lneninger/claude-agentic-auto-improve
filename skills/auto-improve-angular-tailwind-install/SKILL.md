---
name: auto-improve-angular-tailwind-install
description: "Install the angular-tailwind add-on of the agentic-auto-improve plugin in this project: four rule documents (Angular code, Angular Material, Tailwind styling, UI patterns) copied into .claude/references/angular-tailwind/ and listed in the project profile's review.documents slot. Installs no hook and writes no settings.json row. Previews the files and the profile change, asks for one confirmation, then writes. The name carries the plugin name because you may have several plugins installed. Use when: user says /auto-improve-angular-tailwind-install, 'install the angular tailwind add-on', 'add the Angular and Tailwind rule documents', or 'turn on the UI rules'. Never overwrites a file that differs and never removes a row."
user_invocable: true
---

# /auto-improve-angular-tailwind-install — install the angular-tailwind add-on

The `angular-tailwind` add-on gives a project the Angular and Tailwind rule documents. It copies four markdown files into `.claude/references/angular-tailwind/` and lists them in the project profile's `review.documents` slot, so the agents that read that slot find them. It is for projects built with Angular and Tailwind. Nothing registers it by default.

It starts no program on any prompt. The old prompt hook of this add-on is **disabled**: its script still ships, but this install never copies it and never writes its row. The edit-time guard `architecture-guard.py` stays the enforcement.

This skill proposes first. It writes only after one yes, and it reads and touches only
`agentic-auto-improve`.

## The rule that shapes everything here

**The skill carries the conversation. The script carries every rule.**

Which files are copied, which rows are written, what is already there, and what is refused all
live in `auto_improve_finish_install.py addon`, which has its own test suite. Read its answer.
Do not work any of it out yourself, and never edit `settings.json` by hand to install this
add-on: a typing mistake there can switch every check off, or block every action.

The script never removes a row or a file. It never overwrites a file that differs from the
plugin's copy. It copies a helper file only when the project lacks it. In the project profile it
writes exactly one thing: it appends its own document paths to the `review.documents` slot. It
changes no other slot and no other entry in that slot.

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

Every command below is `$PY "$FI" addon --name angular-tailwind --project . ...`.

## What this add-on does

Four rule documents, each one a short list of rules with a stable Rule ID (`A-nnn` Angular code, `M-nnn` Material, `T-nnn` Tailwind and styling, `P-nnn` patterns):

- `ANGULAR_CODE_RULES.md`
- `ANGULAR_MATERIAL_RULES.md`
- `TAILWINDCSS_RULES.md`
- `UI-UX-PATTERNS.md`

The install copies them verbatim into `.claude/references/angular-tailwind/`. The project never edits them. Project facts in them are placeholders that point at profile slots or at the project's own documents. The install then lists the four paths in the profile's `review.documents` slot, so a reviewer or an implementer reads them with the rest of that list. The guard's block and warn lines name the Rule ID, and name the document when it is installed here.

The install writes **no hook file and no `settings.json` row**, and the add-on declares **no kill switch**. Nothing starts on a prompt. The old prompt hook (`angular-tailwind-advisor.py`, once `architecture-advisor.py`) is a disabled hook of this add-on: see `DISABLED.md` in the add-on folder for what it did, what it cost and how to turn it back on.

It needs one helper, `.claude/hooks/_project_paths.py`, which the install copies only if the project lacks it.

## Step 1: Preview (writes nothing)

```bash
$PY "$FI" addon --name angular-tailwind --project . --json
```

The answer carries `files` (each file with its kind, `document` or `helper`, and its action: `copy`, `present` or `keep-existing`),
`profile` (the `review.documents` slot: `adds` the paths it would append, `already-listed` the paths it skips, `before` and `after`
the slot text, and a `unified-diff`), `to-add` (settings rows; empty for this add-on), `notes`, `kill-switches` (empty),
`disabled-hooks`, `target`, `plugin-root` and `plan-sha256`.
**Keep `plan-sha256`.** The apply needs it as `--expect-sha256`. It covers the settings bytes, the profile bytes before and
after, and every file the install would copy, so anything that moves between the preview and the write is refused as
`changed-since-preview`.

How the slot is written: a slot that still holds its placeholder, or `none`, becomes the list of the four paths. A slot the team
wrote keeps its text, and the missing paths are appended after it. A path that is already listed (with or without backticks,
with either slash) is skipped. When all four are listed, the profile is not written at all.

## Step 2: Show the plan and ask once

Show the user, in plain words:

- the documents it would copy into `.claude/references/angular-tailwind/`, and any helper into `.claude/hooks/`, with the
  action for each. A file marked `present` is already identical and is not touched. A helper marked `keep-existing` is kept as it is.
- the `profile` change: the slot before, the slot after, and the `unified-diff`.
- that no hook is installed and no row is written to `settings.json`.
- any `notes`.

State your recommendation first, in one or two sentences. Then ask **once**: install this
add-on?

No new session is needed for the documents to be found: they are files, read when an agent reads `review.documents`.

Declining writes nothing.

## Step 3: Apply

On a yes, apply with the `plan-sha256` from the preview:

```bash
$PY "$FI" addon --name angular-tailwind --project . --apply --expect-sha256 <plan-sha256 from the preview>
```

The script copies the documents first and updates the profile last, so the profile never lists a file that is not there.
`settings.json` is not touched, so there is no backup to print. The answer lists `copied` and `registered` (the paths appended to the slot).

If the answer says `nothing-to-do`, the add-on was already installed. Nothing was written.

### Refusals

Exit `2` is a refusal you can correct. Exit `3` is an environment problem, such as an add-on
folder with no `addon.json`. On either, read `code` and `message`, tell the user the reason in
one plain sentence, and stop. A refusal always means nothing was changed. The ones you may see:

- `profile-slot-missing`: the project has no `.claude/project-profile.md`, or the profile has no
  `review.documents` row. Nothing was written, not even the documents. Tell the user to run
  `/auto-improve-finish-install` first (it writes the profile), then run this skill again.
- `disabled-hook-present`: the project still carries the retired advisor hook, as the file
  `.claude/hooks/angular-tailwind-advisor.py` or `.claude/hooks/architecture-advisor.py`, or as a
  row in `.claude/settings.json` or `.claude/settings.local.json` that names either file. Name what the
  message names. Nothing was written. Tell the user to run `/auto-improve-angular-tailwind-uninstall`
  first, which removes the row and then the file, then run this skill again. Do not delete the row
  or the file yourself: a row left pointing at a missing script blocks every prompt.
- `addon-file-differs`: one of the four documents already exists in the project and is not the
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

This install never removes anything. The removal is its own skill, `/auto-improve-angular-tailwind-uninstall`.
It also cleans a project that installed the old advisor hook under either of its file names, which is
what `disabled-hook-present` asks for.

## Closing

End with a short summary: what was copied, which paths were registered in `review.documents`, and what was
**not** written and why (no hook, no row, no `settings.json`). Say that running this skill again
changes nothing: identical files are left alone and a path that is already listed is not listed twice.

## Anti-patterns

- **Telling the user the documents enforce anything.** They state the rules. The architecture guard enforces
  what it checks, and for those rules its verdict is final.
- **Offering a kill switch or an environment variable for this add-on.** It declares none, and it starts nothing.
- **Writing a hook row or a `settings.json` entry for this add-on.** Its hook is disabled; the script writes no row.
- **Writing the profile by hand to list the documents.** Use the script: it compares paths and skips the ones already listed.
- **Writing without the preview's `plan-sha256`**, or with an old one. The hash is what proves the user saw the
  change as it is now.
- **Hand-editing `settings.json` or deleting the old advisor row or file yourself.** Run the uninstall skill:
  it removes the row first, because a row that points at a missing script blocks every prompt.
- **Overwriting a document that differs.** The script refuses; do not copy over it yourself.

## When NOT to use

- To turn on the check that blocks a bad write. That is `architecture-guard.py`, already a default hook.
- To change the rules the documents state. They belong to the add-on's `documents/` folder in the plugin.
- To get the prompt reminder back. See `DISABLED.md` in the add-on folder.
- Inside the plugin's own checkout. The script refuses it as `plugin-source-checkout`.
- On Cursor or Codex. Hooks are Claude-only in this release.
