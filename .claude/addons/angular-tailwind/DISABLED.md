# The angular-tailwind advisor hook is disabled

The script `hooks/angular-tailwind-advisor.py` still ships in this folder, but no install copies it and no install writes its row. The add-on now installs rule documents (see `addon.json`, key `documents`) and registers them in the project profile. This note says what the hook did, what it cost, why it is off, and how to turn it back on.

## What it did

It was registered on `UserPromptSubmit` with no matcher. When the user's prompt held a UI word (component, template, style, layout, theme, scss, css, html, material, tailwind, angular, dashboard, dialog, card, panel, sidebar, button, widget and a few more), it added a reminder of about 400 words to what the agent saw: the CSS and Tailwind rules, the project's reference documents from `architecture-guard.rules.json`, the `.app-rules.json` appendix of any app the prompt named, and, for a layout prompt, a hint to read the two plugin design skills. It never blocked anything. The edit-time guard `architecture-guard.py` was, and still is, the enforcement.

Before the 0.7.0 release the same script was called `architecture-advisor.py`. Projects that installed it under that name carry a row naming that file. `addon.json` lists the old name under `former_names`, so the install and the removal recognise both.

## What it cost

- **A Python start on EVERY prompt.** The row had no matcher, so Claude Code started the script for every prompt, whether or not it was about UI. Only the printing depended on the keywords. Measured once, on one Windows workstation, for issue #84: a median of 123 ms per start against 50 ms for a bare Python start (the median of seven runs). That figure was not measured again.
- **About 400 words of context** added to the prompt each time a keyword matched.
- The text went into the prompt of the main session. That it ever reached a subagent that wrote the code was never verified.

## Why it is off

The rules now live where they cost nothing until they are needed: four rule documents copied into the project and listed in `review.documents`, a plugin skill (`angular-ui-rules`) that the Angular developer agent preloads, and a Rule ID on every line the guard prints. No program starts on any prompt for Angular rules.

## Two defects for anyone who turns it back on

1. The keyword `"ui"` can never match. The script finds words with the pattern `[a-zA-Z][a-zA-Z-]{2,}`, which needs at least three characters, and `ui` has two. A prompt that says only "ui" gets no reminder.
2. When `_project_paths` cannot be imported, the script falls back (line 43) to `architecture-guard.rules.json` in the user's home folder (`~/.claude/hooks/`). It then reads a file outside the project, which can name another project's documents. It should read the rules file through `_project_paths` only.

The script also no longer reads `CLAUDE_ARCH_ADVISOR`: the add-on declares no kill switch.

## How to turn it back on

This is a change to the plugin, not to a project:

1. In `addon.json`, move `angular-tailwind-advisor.py` from `disabled` into `hooks`, and add its row (`{"event": "UserPromptSubmit", "hook": "angular-tailwind-advisor.py", "args": []}`) to `registrations`. Keep `architecture-advisor.py` somewhere the checks still see it, because projects that installed the old file still carry it.
2. Add-ons declare no kill switch. Do not add a `kill_switches` key or an environment check to the script.
3. Fix both defects above: fix the keyword pattern, or drop `"ui"` from the keywords; and read the rules file through `_project_paths`, with no home-folder fallback. Then add the new hash of the script to `released_sha256`.
4. Raise the plugin version in the five places the project rule names, and run `py -3 .claude/scripts/check_version_bump.py`.
5. Run the manifest and install suites: `.claude/scripts/tests/test_plugin_manifests.py` and `.claude/scripts/tests/test_auto_improve_finish_install.py`.

Projects that want it then run the install skill again; they start a new session for the row to take effect.

## To remove it from a project that has it

Run `/auto-improve-angular-tailwind-uninstall`. Until it has run, the install refuses with `disabled-hook-present`.
