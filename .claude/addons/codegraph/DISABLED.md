# The codegraph tracker and reset hooks are disabled

Two scripts, `hooks/codegraph-turn-tracker.py` and `hooks/codegraph-turn-reset.py`, still ship in this folder. No install copies them and no install writes their rows. This is the cut-over of issue #262: the guard now decides from the session transcript, so the two hooks have nothing left to do. This note says what each hook did, where each duty went, what is saved, how to turn them back on, and how a project that still has them gets rid of them.

A few terms first:

- **The guard** is `hooks/codegraph-first-guard.py`. It blocks `Read`, `Grep` and `Glob` on source files until CodeGraph has been used in the current turn.
- **The turn** is the span after the last human prompt.
- **The transcript** is the log file that Claude Code writes for each session. The hook payload names it in `transcript_path`.
- **The turn marker** is the file `turn.json`, in the guard's per-session folder. The tracker wrote it and the reset hook deleted it.
- **A row** is one hook entry in `.claude/settings.json`.

## What they did

- **The tracker** ran after every CodeGraph tool call (`PostToolUse` on `mcp__codegraph__.*`) and after a Bash command that started with `codegraph ` (`PostToolUse` on `Bash`, argument `cli`, with `if` set to `Bash(codegraph *)`). It wrote the turn marker. It also wrote the one `cli-fallback` log record per session, when the command line opened a turn and no MCP call had been seen.
- **The reset hook** ran on every prompt (`UserPromptSubmit`, no matcher). It deleted the turn marker and the retry tickets. It created the session folder and, once per session, deleted old session folders. It printed the Connection notice, the one message that tells the user to run `/mcp` when the CodeGraph MCP connection has dropped.

## Where each duty went

| Duty | Now done by |
|---|---|
| Opening the turn after a CodeGraph MCP call | The guard reads the transcript and finds the `mcp__codegraph__*` tool use. |
| Opening the turn after a Counted `codegraph` command in Bash | The guard finds the Bash tool use in the transcript. The test is the tracker's strict test, moved into the guard. A failed attempt counts too. |
| Opening the turn after a subagent dispatch | The guard finds the `Agent` (or older `Task`) tool use in the transcript. This is new: the marker was shared with subagents, the transcript is not. |
| Closing the turn at a prompt | A human prompt in the transcript ends the turn. A background task notification does not. No file is deleted. |
| Expiring the retry ticket at a prompt | The ticket carries a `prompt_key`. It only matches inside the prompt that issued it. |
| The `cli-fallback` record | The guard writes it at the first guarded call of the turn. A turn with no guarded call writes none. |
| Creating the session folder, pruning old ones | The guard's prompt row: `codegraph-first-guard.py notice` on `UserPromptSubmit`. |
| The Connection notice | The same prompt row. |

## What it saves

Claude Code started one Python process for every prompt (the reset hook) and one for every CodeGraph call (the tracker). The parent contract's timing run (t3, one Windows workstation) measured about 104.7 ms for the reset hook and about 101.4 ms for the tracker at the median. The prompt row keeps the per-prompt start, because the notice has to run on every prompt. The tracker's start per CodeGraph call is gone, and so is the reset hook's load of the guard by path.

## What the cut-over added to the risk

The guard now trusts the transcript. A transcript line that is not understood never closes the gate: every read that is not a clear open or closed answer allows the call, with a logged reason, `fail-open:transcript-<cause>`. The measurement log, `.claude/logs/codegraph-shadow.jsonl`, records one line per guarded call, up to a 10 MB cap. It cannot tell a wrong block from a right one. The rollback rule below depends on the user's reports for that.

## How to turn them back on

There are two routes.

- **One project, at once:** run `/auto-improve-codegraph-uninstall`, then start a new session. The gate is off for that project until the install is run again.
- **The whole plugin, by a revert release.** This is a change to the plugin, not to a project:
  1. In `addon.json`, move both hooks out of `disabled` and into `hooks`. Put their four rows back into `registrations`: `UserPromptSubmit` for the reset hook, and the two `PostToolUse` rows of the tracker (the second with `args` set to `["cli"]` and its `if`). Keep the guard's `PreToolUse` row.
  2. Put the guard's previous copy back in `hooks/`. Add the cut-over guard's folded hash to the guard's `released_sha256`, so that the update action takes the copy back instead of treating it as edited.
  3. Move each hook's `released_sha256` list back to the top-level `released_sha256`, under the hook's name.
  4. Raise the plugin version in the five places the project rule names, and run `py -3 .claude/scripts/check_version_bump.py`.
  5. Run the manifest and install suites.

  Projects then run `/auto-improve-codegraph-install` again, and start a new session. The install updates the guard, restores both files and writes the missing rows. A project that already had the guard's `notice` row keeps it. The reverted guard exits 0 for a payload with no `tool_name`, so that leftover row does nothing.

## How to remove them from a project that has them

Run `/auto-improve-codegraph-install` again. The install retires the two hooks in two steps, so that a session that is already open never finds a missing script:

1. **Step A** removes the two hooks' rows from `.claude/settings.json` and leaves the files where they are. It also updates the guard and adds its prompt row. Start a new session afterwards.
2. **Step B** is the next run of the install. It deletes the two files when they are unedited released copies. An edited copy is kept and listed.

The install refuses (`disabled-hook-present`, nothing written) when a row for one of the two hooks is in `.claude/settings.local.json`, or when step A finds an edited copy of a hook whose row it would remove. Run `/auto-improve-codegraph-uninstall` in those cases.

Until step B has run, `plugin_doctor.py --drift` reports the leftover files as `disabled-hook-installed`. They do nothing.
