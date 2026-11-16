# t3 live prompt trial — senior-test-engineer

- **Gate agent:** senior-test-engineer
- **Sub-task:** t3-live-prompt-trial (issue #422, parent #419)
- **Contract:** `.claude/concepts/2026-11-16-file-based-switches.md` (approved)
- **Reviewed on:** pending, a person fills this in when they run the sheet
- **Commit range reviewed:** `feature/file-based-switches..task/2026-11-16-file-based-switches/t3-live-prompt-trial` (the base holds the helper and the database override arm from t2, merge `adb70aa`, which is the code under trial)

**Verdict:** blocked

Results pending: a person runs the steps below

The person sets the verdict to `pass` or `pass-with-findings` in this same pull request, only after every "Observed" line below is filled in and matches its "Expected" line. Merged unchanged, `blocked` holds every block that depends on this one. No agent runs these steps: the contract's Person-present rule is about a real person in a real Claude Code session, and an agent cannot stand in for one.

**Deviation from the brief, approved by the user:** the brief asks for a PowerShell command in every step. In steps 1 to 3 the PowerShell blocks cover only the arm file, the permission mode, the log and the version. The destructive statement itself is described in words and is never written in this sheet, because the plugin's destructive-database guard blocks any file that holds it. The person types that statement themselves, in the session.

## What was checked

Each step has one outcome, to be filled in by the person (`met`, `not-met`, or `not-run`). All five are `not-run` until the person runs them.

- Step 1, default mode, arm plus a destructive command on a disposable-looking, non-disposable name: a prompt appears; declining leaves no arm. Outcome: not-run.
- Step 2, bypass-permissions mode, same command: the guard blocks, no prompt. Outcome: not-run.
- Step 3, headless `claude -p` with no permission-prompt tool: the guard blocks. Outcome: not-run.
- Step 4, `concept_gate` switched off: the person sees one message in the session, once. Outcome: not-run.
- Step 5, Claude Code version recorded. Outcome: not-run.

## Findings

None yet. The person lists here every difference between an Expected and an Observed line, with a severity (`blocker`, `warning`, `nit`) and the step number. A step whose observation contradicts an Uncertain Assumption of the contract (the payload carries `permission_mode`; `permissionDecision: "ask"` shows a prompt; a block beats an ask; `systemMessage` is shown to the person) is a `blocker`.

## What was NOT checked

- No step was run by an agent. Every Observed line is empty.
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
- **Observed:** _(person fills in: did a prompt appear, its reason text, the second `Test-Path` value, the log line)_

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
- **Observed:** _(person fills in: was there a prompt, the block text, the log line, the `Test-Path` value)_

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
- **Observed:** _(person fills in: the reply text, `$LASTEXITCODE`, the log line with its permission mode)_

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
- **Observed:** _(person fills in: the message text, where it showed, how many times in the session, whether a new session showed it again)_

### Step 5: record the Claude Code version

```powershell
claude --version
```

- **Expected:** one version string, copied here exactly.
- **Observed:** _(person fills in: the version string, the date, the operating system)_

## Disposition

Blocked until a person runs steps 1 to 5 and writes their observations above.

- If every Observed line matches its Expected line, the person changes the verdict line to `**Verdict:** pass`, fills in the "Reviewed on" date, and sets each "What was checked" outcome. This gate then releases its dependents.
- If a step differs, the person records it under "Findings". A harmless difference gives `**Verdict:** pass-with-findings`. A difference that breaks an Uncertain Assumption (no `permission_mode` in the payload, no prompt shown, a prompt shown in bypass mode, or an invisible off notice) leaves `**Verdict:** blocked` and goes back to the architect, because the override design depends on that behaviour.
