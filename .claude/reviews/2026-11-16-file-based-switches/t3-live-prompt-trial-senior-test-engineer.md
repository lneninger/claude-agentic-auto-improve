# t3 live prompt trial — senior-test-engineer

- **Gate agent:** senior-test-engineer
- **Sub-task:** t3-live-prompt-trial (issue #422, parent #419)
- **Contract:** `.claude/concepts/2026-11-16-file-based-switches.md` (approved)
- **Reviewed on:** 2026-11-18 (run by the repository owner, in live sessions, with this worktree loaded as a session-only plugin through `--plugin-dir`)
- **Commit range reviewed:** `feature/file-based-switches..task/2026-11-16-file-based-switches/t3-live-prompt-trial` (the base holds the helper and the database override arm from t2, merge `adb70aa`, which is the code under trial)

**Verdict:** pass-with-findings

All five steps were run by a person. Every Uncertain Assumption held. The findings below are warnings and nits, none a blocker. The "Observed" lines below were written by an agent from the owner's pasted output and the guard log, and the owner confirmed them.

The person sets the verdict to `pass` or `pass-with-findings` in this same pull request, only after every "Observed" line below is filled in and matches its "Expected" line. Merged unchanged, `blocked` holds every block that depends on this one. No agent runs these steps: the contract's Person-present rule is about a real person in a real Claude Code session, and an agent cannot stand in for one.

**Deviation from the brief, approved by the user:** the brief asks for a PowerShell command in every step. In steps 1 to 3 the PowerShell blocks cover only the arm file, the permission mode, the log and the version. The destructive statement itself is described in words and is never written in this sheet, because the plugin's destructive-database guard blocks any file that holds it. The person types that statement themselves, in the session.

## What was checked

Each step has one outcome (`met`, `not-met`, or `not-run`).

- Step 1, default mode, arm plus a destructive command on a disposable-looking, non-disposable name: a prompt appears; declining leaves no arm. Outcome: met (with warning W1).
- Step 2, bypass-permissions mode, same command: the guard blocks, no prompt. Outcome: met (the hook's own block text was not captured in full, see N2).
- Step 3, headless `claude -p` with no permission-prompt tool: the guard blocks. Outcome: met on the guard's log line (reply text and exit code were not captured, see N3).
- Step 4, `concept_gate` switched off: the person sees one message in the session, once. Outcome: met.
- Step 5, Claude Code version recorded. Outcome: met.

## Findings

No blocker. No observation contradicted an Uncertain Assumption of the contract: the payload carried `permission_mode` (default, auto, bypassPermissions all logged); `permissionDecision: "ask"` showed a prompt; a block held in modes that cannot prompt; the off notice reached the person inside the session.

- **W1 (warning, step 1):** the permission prompt names the target as `"unresolved"`, not the database name. The guard could not read the database name from the command-line form used here, so the person approving sees no name. The log shows the same: `destructive_targets` name `unresolved`, `block_reason` `unresolved-target`. The prompt, the claim and the log all worked, so this weakens the "approve only if you mean this exact command" promise without breaking the design. Recommend a follow-up to resolve the target for this command form.
- **N1 (nit, startup):** Claude Code prints `hooks.json: unknown key "$comment" ignored` twice at the start of every session. Harmless. `.claude/hooks/hooks.json` belongs to sub-task 6.
- **N2 (nit, step 2):** the hook's own block text was not captured in full; only Claude's paraphrase was seen. The log line is complete.
- **N3 (nit, step 3):** the reply text and exit code were not captured. A first attempt, with the prompt passed as an argument, reached Claude with its inner quotes stripped by Windows PowerShell 5.1, so Claude ran an incomplete command and the guard logged nothing. The retry, with the prompt sent through standard input, logged a block. This is a trial-sheet defect: the sheet's `claude -p "<your prompt>"` form is unsafe in Windows PowerShell 5.1 when the prompt holds double quotes.
- **N4 (nit, step 3):** the headless run reported permission mode `auto`, not a missing mode, so the "mode missing" case was not exercised.
- **N5 (info):** the guard fired for both the Bash and PowerShell tools.

## What was NOT checked

- No step was run by an agent. A person ran every step; an agent only wrote the Observed lines from the person's pasted output and the guard log.
- The "permission mode missing" case was not exercised (N4).
- The hook's own block text for steps 2 and 3, the reply text and the exit code for step 3 were not captured (N2, N3).
- Not covered by any step, and stated as residual risk in the contract: a prompt answered by code the person configured (a permission-prompt tool, an SDK permission callback, a `PermissionRequest` hook). Step 3 proves only the case with none configured.
- `acceptEdits` and `plan` modes are not tried; the person may add them as extra steps.
- A hook row edited inside a session acts only from the next session.

## Evidence

The person's observations. Run from the root of a scratch project that has the plugin's hooks registered and the t2 code, never against a database the project's configuration points at. No step touches a real database: the name `Orders_Throwaway_Live` does not exist, and the point of the trial is that the command is refused or prompted before it runs. Decline every prompt. Start a fresh Claude Code session for each step so no once-per-session marker or arm leaks across steps.

Replace `<project>` with the scratch project root.

**The statement for steps 1 to 3 (typed by the person):** a SQL Server command-line statement (through `sqlcmd`, against `localhost`) that drops the database named `Orders_Throwaway_Live`. Ask Claude to run exactly that, and nothing else. The name looks disposable because it holds the word `Throwaway`, but it does not end in an allow-listed disposable suffix, so the guard must treat it as non-disposable.

### Step 1: default mode, arm present, destructive command on a non-disposable name

```powershell
Set-Location '<project>'
New-Item -ItemType File -Path '.claude\database-override.once' -Force | Out-Null
Test-Path '.claude\database-override.once'          # expect True before the session
claude                                              # default permission mode: the footer shows no bypass, accept-edits or plan label
# In the session, type the statement described above and ask Claude to run it.
# When the permission prompt appears, choose No (decline). Then exit the session.
Test-Path '.claude\database-override.once'          # expect False after declining
Get-Content '.claude\logs\db-guard.log' -Tail 5
```

- **Expected:** a permission prompt appears, and its reason names `Orders_Throwaway_Live`. After declining, the command did not run, the second `Test-Path` prints `False` (the arm is used up whatever the answer), and the last `db-guard.log` line shows the override claimed with permission mode `default`.
- **Observed:** A permission prompt appeared in default mode. Its reason read: "One-shot destructive database override. A person armed it. Approve only if you mean to run this exact command. Target: "unresolved" as written in the command." It did not name the database (W1). The person chose No and the command did not run. The second `Test-Path` printed `False`; the arm was claimed by rename to `database-override.claimed-<tool_use_id>`. Log line, 2026-11-18T13:42:02Z, tool Bash: decision ASK, reason claimed, block_reason unresolved-target, permission_mode default, with the tool_use_id. Two earlier attempts in `auto` mode (13:32 and 13:37) logged BLOCK with reason no-prompt-available and left the arm unconsumed; they are extra evidence, not part of this step. A first attempt before `--plugin-dir` was used ran the installed 0.16.5 plugin and is not counted.

### Step 2: bypass-permissions mode, same statement

```powershell
Set-Location '<project>'
New-Item -ItemType File -Path '.claude\database-override.once' -Force | Out-Null
claude --permission-mode bypassPermissions
# In the session, type the same statement and ask Claude to run it.
# Exit the session.
Test-Path '.claude\database-override.once'
Get-Content '.claude\logs\db-guard.log' -Tail 5
Remove-Item '.claude\database-override.once' -ErrorAction SilentlyContinue   # tidy up the arm if it is still there
```

- **Expected:** no prompt. The guard blocks the command, and the block text tells the person to run the command themselves, in their own terminal. The log records a block with permission mode `bypassPermissions`. The command did not run.
- **Observed:** No prompt. The command was refused ("Not run, permission denied", reason "PreToolUse:PowerShell hook error: [db-destructive-guard] BLOCKED"). Claude's summary said the arm file existed and the mode was bypassPermissions, which shows no prompt, so the command stayed blocked. The hook's full block text was not captured (N2). Log line, 2026-11-18T13:52:33Z, tool PowerShell: decision BLOCK, reason no-prompt-available, block_reason unresolved-target, permission_mode bypassPermissions. The arm file was still present afterwards, as expected for a block, and was removed by the person.

### Step 3: headless run with no permission-prompt tool

```powershell
Set-Location '<project>'
New-Item -ItemType File -Path '.claude\database-override.once' -Force | Out-Null
# Run claude -p with a prompt you write yourself: ask it to run the same statement.
#   claude -p "<your prompt>" --output-format text
$LASTEXITCODE
Get-Content '.claude\logs\db-guard.log' -Tail 5
Remove-Item '.claude\database-override.once' -ErrorAction SilentlyContinue
```

Do not pass `--permission-prompt-tool`, `--dangerously-skip-permissions` or `--permission-mode`. Make sure no `PermissionRequest` hook is configured in the scratch project or your user settings.

- **Expected:** the guard blocks, whatever permission mode the headless run reports (a missing or unknown mode blocks), and the reply carries the block text or says the command was refused. The command did not run.
- **Observed:** Attempt 1 (prompt passed as an argument) did not test the guard: the inner double quotes were stripped by Windows PowerShell 5.1, Claude ran an incomplete command, SQL Server rejected it with a syntax error near the first keyword, nothing was dropped and the guard logged nothing (N3). Attempt 2 (prompt sent through standard input) logged, 2026-11-18T14:01:33Z, tool Bash: decision BLOCK, reason no-prompt-available, block_reason unresolved-target, permission_mode auto (N4). The arm file was left unconsumed. Reply text and exit code were not captured (N3).

### Step 4: switching `concept_gate` off shows the person a message once

```powershell
Set-Location '<project>'
Copy-Item '.claude\switches.json' '.claude\switches.json.bak' -ErrorAction SilentlyContinue
# Edit .claude\switches.json by hand so it holds  { "concept_gate": "off" }  (keep any other keys).
Get-Content '.claude\switches.json'
claude
# In the session, ask Claude to make two separate edits to a source file that no approved contract covers (for example, add a comment line to a .py file, then add a second one).
# Note every place the message appears. Exit the session.
# Restore the file:
if (Test-Path '.claude\switches.json.bak') { Move-Item '.claude\switches.json.bak' '.claude\switches.json' -Force } else { Remove-Item '.claude\switches.json' }
```

- **Expected:** the person sees one message in the session, in Claude Code's own display and not only in a log, saying the concept gate is off, naming the key `concept_gate`, the value `off` and the file. It appears on the first edit and not again on the second. A new session shows it once more.
- **Observed:** With `concept_gate` set to `off` in `.claude/switches.json`, the message "Guard switched off: concept_gate is off (set in switches.json). The concept-gate guard is not enforcing. Set it back to on in the switch file to turn it on again." showed inside the Claude window, labelled `PreToolUse:Bash says`, on the first edit. It did not show on the second edit. A new session showed it once on its first edit. It names the key, the value and the file.

### Step 5: record the Claude Code version

```powershell
claude --version
```

- **Expected:** one version string, copied here exactly.
- **Observed:** 2.1.327 (Claude Code), 2026-11-18, Windows 11.

## Disposition

Released as `pass-with-findings`: a person ran steps 1 to 5 and every Observed line matches its Expected line, apart from the prompt's reason text in step 1 (W1), which does not name the database.

- If every Observed line matches its Expected line, the person changes the verdict line to `**Verdict:** pass`, fills in the "Reviewed on" date, and sets each "What was checked" outcome. This gate then releases its dependents.
- If a step differs, the person records it under "Findings". A harmless difference gives `**Verdict:** pass-with-findings`. A difference that breaks an Uncertain Assumption (no `permission_mode` in the payload, no prompt shown, a prompt shown in bypass mode, or an invisible off notice) leaves `**Verdict:** blocked` and goes back to the architect, because the override design depends on that behaviour.
