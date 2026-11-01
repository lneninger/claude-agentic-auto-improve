# Route trial: does a `.claude/rules/` file load, and when?

This is a record of one live trial of the `.claude/rules/` route (alternative E of the parent contract, `.claude/concepts/2026-10-30-angular-tailwind-followups.md`). It states only what was observed. It makes no claim beyond the three runs below.

## Terms used here

- **Rules file.** A Markdown file under `.claude/rules/` in a project. Claude Code reads it as standing instructions. Its optional front matter (a small `---` block at the top) can carry a `paths:` list of file patterns. A rules file with `paths:` is meant to load only when Claude works on a file that matches one of the patterns.
- **Sentinel line.** A line of text invented for the test, with a token no other file contains (`SENTINEL-RULES-T7-7f3a`). If Claude can quote it back, the rules file reached Claude. If Claude cannot, it did not.
- **Subagent.** A second Claude instance that the main session starts for a side task. It runs with its own context.
- **Exit code.** The number a command returns to the shell. 0 means the command finished without a command-level error.

## Record

| Field | Value |
|---|---|
| Date | 2026-10-31 |
| Host version | Claude Code 2.1.316 (`claude --version`) |
| Install mode | Headless runs (`claude -p`) from a plain folder outside every checkout. The user-level setup was active, so the auto-improve plugin 0.10.1 hooks and the user's global `CLAUDE.md` were also present in the session. The folder itself held no plugin files. |
| Model | claude-sonnet-5-5 |

### Front matter used

The trial rules file was `.claude/rules/angular.md`:

```markdown
---
paths:
  - "**/*.component.html"
---

SENTINEL-RULES-T7-7f3a: Angular template rule loaded.
```

The one matching file was `src/app/x.component.html`, holding `<div>hello</div>`.

### Outcomes

| Question | Answer |
|---|---|
| Loads in the main session (when the matching file is opened)? | **Yes** |
| Loads only on a matching path (not at session start)? | **Yes** (not present before the file was opened; see runs 1b and 2) |
| Reaches a subagent? | **Yes**, when the subagent itself opened the matching file. Not tested: a subagent that never opens a matching file. |

### Commands and results

All runs used the working folder `%TEMP%\rules-trial-t7` (here `C:\Users\lneni\AppData\Local\Temp\rules-trial-t7`). The runs went through the Bash tool, which on this machine is Git Bash, because the agent's PowerShell wrapper was refused by the worktree guard (the wrapper command was too complex for the guard to check). The `claude` arguments are identical in PowerShell. A PowerShell form of each run is shown. Exit codes were read from the shell after each run.

**Run 1a. No file opened, the prompt as the contract wrote it.**

```powershell
Set-Location "$env:TEMP\rules-trial-t7"
claude -p "Quote the sentinel line of any rule you were given" --output-format json
```

- Exit code: 0. `is_error: false`, `num_turns: 1`.
- Observed: **did not load.** The answer said no rule had a line labelled "sentinel line" and quoted instead the CodeGraph wording from the user's global `CLAUDE.md`, which also uses the word "sentinel". The test token never appeared.
- Caveat: the word "sentinel" collides with the global `CLAUDE.md`, so this prompt cannot tell "not loaded" from "loaded but not recognised". Run 1b removes the doubt.

**Run 1b. Control: no file opened, prompt names the token.**

```powershell
claude -p "Without opening any file, quote any line you were given that begins with SENTINEL-RULES-T7, or say none was given." --output-format json
```

- Exit code: 0. `is_error: false`, `num_turns: 1`.
- Observed: **did not load.** Answer: "None was given."

**Run 2. A prompt that opens the matching file.**

```powershell
claude -p "Open src/app/x.component.html and tell me what it contains. Then quote any line you were given that begins with SENTINEL-RULES-T7, or say none was given." --output-format json --allowedTools Read
```

- Exit code: 0. `is_error: false`, `num_turns: 2` (one file read).
- Observed: **loaded.** Answer quoted `SENTINEL-RULES-T7-7f3a: Angular template rule loaded.` and named `.claude/rules/angular.md` as its source.

**Run 3. A prompt that uses a subagent.**

```powershell
claude -p "Use the Agent tool to start a subagent. Tell the subagent to open src/app/x.component.html, then report any line it was given that begins with SENTINEL-RULES-T7, or say none was given. Relay its answer verbatim, and also say whether you yourself (not the subagent) were given such a line before you started it." --output-format json --allowedTools Read Agent
```

- Exit code: 0. `is_error: false`, `subagent_stats.spawned: 1`, `completed: 1`, `failed: 0`.
- Observed: **loaded in the subagent.** The subagent quoted the sentinel line and said it arrived in a system reminder after it opened the file. The main session said it had not been given the line before starting the subagent.

### When it loads, as observed

The rules file did not load at session start. It loaded after the session opened a file whose path matched `**/*.component.html`, and it loaded again, independently, inside a subagent that opened that file. The text arrived as a system reminder attached to the file read.

### Limits of this trial

- Three headless runs, one rules file, one matching file, one host version. Interactive sessions were not tried.
- The main session was only tested by reading the file. Editing or writing a matching file was not tested.
- A subagent that never touches a matching file was not tested, so "reaches a subagent" means "loads when the subagent opens a matching file", not "is handed down by the parent".
- Behaviour on other host versions is unknown.

## Follow-up

A follow-up issue is worth opening only if the team wants path-scoped Angular guidance: the route works as designed for load-on-match, but it gives no guidance before a matching file is read, so it cannot replace anything that must apply from the first prompt.

## Clean-up

The temporary folder `C:\Users\lneni\AppData\Local\Temp\rules-trial-t7` was removed after the runs.
