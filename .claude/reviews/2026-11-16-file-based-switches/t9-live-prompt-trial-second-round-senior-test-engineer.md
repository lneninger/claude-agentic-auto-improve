# t9 live prompt trial, second round — senior-test-engineer

- **Gate agent:** senior-test-engineer
- **Sub-task:** t9-live-prompt-trial-second-round (issue #443, parent #419)
- **Contract:** `.claude/concepts/2026-11-16-file-based-switches.md` (approved)
- **Reviewed on:** 2026-11-18
- **Follows:** `t3-live-prompt-trial-senior-test-engineer.md` (steps 1 to 5, report stays in force) and finding W3 of `t4-security-review-security-auditor.md`
- **Commit the trial runs against:** `3a23bccd0603d9d9729a5ae162760f20881d5ef4` (`git rev-parse HEAD` in the parent-branch checkout the session started from)

**Verdict:** pass-with-findings

Step 6 was run by a person and met. Steps 7 to 10 were not run: the owner closed the trial after step 6 on 2026-11-18. See "Findings" and "What was NOT checked".

No agent ran these steps: the contract's Person-present rule is about a real person in a real Claude Code session. The person ran step 6 and set the verdict.

**Why a second round:** the first trial proved the prompt route in default, bypass-permissions and headless modes. It left open what the t4 security review named in finding W3(b) (does a `permissions.allow` rule in `settings.local.json` override a PreToolUse `ask`?) and the modes `acceptEdits`, `plan` and `dontAsk`, which the review probed offline only. Steps 6 to 10 continue the numbering of the first sheet.

## What was checked

Each step has one outcome (`met`, `not-met`, or `not-run`). All start as `not-run`.

- Step 6, default mode with an allow rule for `sqlcmd` in `settings.local.json`, session started after the rule was saved: the prompt still appears. Outcome: met.
- Step 7, `acceptEdits` mode: a prompt appears; declining leaves no arm. Outcome: not-run.
- Step 8, `plan` mode: a prompt or a host refusal; nothing runs unprompted. Outcome: not-run.
- Step 9, `dontAsk` mode: the guard blocks, the arm is kept, then removed by hand. Outcome: not-run.
- Step 10, Claude Code version recorded; the missing-mode case stated as resting on the unit rows. Outcome: not-run (the version was read afterwards, see its Observed line).

## Findings

1. **The trial only tests the branch's code if the session loads the branch's hooks.** The installed plugin (0.21.0 at `C:\Users\lneni\.claude\plugins\cache\...`) has the old guard and does not know the arm file. Attempts 1 and 3 were blocked by that guard with no prompt (`unresolved-target`, no `permission_mode` field in the log) and are void. The valid run used `claude --permission-mode default --plugin-dir <parent-branch worktree>` with the installed plugin disabled for the trial (`claude plugin disable agentic-auto-improve@auto-improve`, then enabled again). Whether the branch's guard still wins when both copies are active was not tested.
2. **In `auto` mode the guard blocked and kept the arm.** One attempt ran in `auto` mode: log reason `no-prompt-available`, `permission_mode = "auto"`, no prompt, arm file kept. That is the intended behaviour for a mode with no prompt.
3. **The model may refuse before any hook runs.** The first attempt in the session was refused by Claude itself under the person's global rule against `DROP` statements, so no tool call was made. An explicit authorizing message from the person was needed for the command to reach the tool.
4. **Log reason `claimed-by-sibling`, not `claimed`.** The two database guards share one arm through a claim file named after the tool call id; the one that claimed it second logs `claimed-by-sibling`. Both asked. Harmless and by design; "claimed" in step 6's Expected line means either outcome.
5. **The decline answer was not recorded separately.** The arm file was consumed (`Test-Path` printed `False`) and the person closed the trial after the prompt; the sheet has no separate line saying "No" was chosen.
6. **Steps 7 to 10 were not run.** The owner closed the trial after step 6. That is why the verdict is `pass-with-findings`, not `pass`.

- If step 6 shows no prompt, a `permissions.allow` rule overrides the hook's `ask`, an agent can write that file, and the override design is broken. The person leaves `**Verdict:** blocked` and the item goes back to the architect.
- A harmless difference gives `**Verdict:** pass-with-findings`.
- A prompt that names the target as `"unresolved"` is already known (first trial W1, review W5) and is not a new finding.

## What was NOT checked

- No step is run by an agent.
- Steps 7, 8 and 9 (`acceptEdits`, `plan`, `dontAsk`) and the live part of step 10 were not run. The owner closed the trial after step 6.
- Whether the branch's guard still decides first when the installed plugin is also active (Findings item 1).
- A missing permission mode cannot be produced from a normal Claude Code session. That case rests on the unit rows, not on this trial (step 10 states it).
- A prompt answered by code the person configured (a permission-prompt tool, an SDK permission callback, a `PermissionRequest` hook) stays the contract's stated residual risk; no step here covers it.
- The arm is not bound to one command: the agent picks which blocked command uses it up (review W3(a)). This trial does not test that; it is named in the residual-risk paragraph.
- The FIFO route of review finding W4 (POSIX only).
- Permission rules other than the one rule text recorded in step 6 (for example a user-level or managed settings rule).

## Evidence

The person's observations. Run from the parent-branch checkout, with the plugin's hooks registered and the t2 code, never against a database the project's configuration points at. Every destructive statement in this trial targets the name `Orders_T9_Nonexistent_Live`, which does not exist on the local server, so a command the host wrongly allows fails harmlessly with an unknown-database error. Decline every prompt. Replace `<project>` with the checkout root.

**The statement (typed by the person):** a SQL Server command-line statement, through `sqlcmd -S localhost -Q`, that drops the database named `Orders_T9_Nonexistent_Live`. This sheet never holds that statement as command text, because the plugin's destructive-database guard refuses any file that holds it. Ask Claude to run exactly that statement through `sqlcmd -Q`, and nothing else. The name does not end in an allow-listed disposable suffix, so the guard treats it as non-disposable.

Before you start, confirm the name is absent (this is a read-only check):

```powershell
sqlcmd -S localhost -E -Q "SELECT COUNT(*) FROM sys.databases WHERE name = 'Orders_T9_Nonexistent_Live'"   # expect 0
```

### Step 6: an allow rule for sqlcmd in settings.local.json does not remove the prompt

Close every Claude Code session first. Then:

```powershell
Set-Location '<project>'
# 1. In an editor (not through Claude), add to .claude\settings.local.json, under permissions.allow, one rule matching sqlcmd
#    for the shell tool the session uses: Bash(sqlcmd:*) for the Bash tool, or PowerShell(sqlcmd:*) for the PowerShell tool.
#    Record the exact rule text you saved:
#    RULE TEXT: <paste exact text>
Get-Content '.claude\settings.local.json'
# 2. Save, then record the save time:
(Get-Item '.claude\settings.local.json').LastWriteTime
# 3. Only now start a NEW session (permission rules may be read only at session start). Record its start time:
Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
# 4. Arm from your own terminal, before starting the session or from a second terminal:
New-Item -ItemType File -Path '.claude\database-override.once' -Force | Out-Null
Test-Path '.claude\database-override.once'          # expect True
claude                                              # default permission mode: no bypass, accept-edits or plan label in the footer
# 5. In the session, ask Claude to run the statement through sqlcmd -Q. When any prompt appears, choose No (decline). Exit the session.
Test-Path '.claude\database-override.once'
Get-Content '.claude\logs\db-guard.log' -Tail 5
# 6. Remove the rule by hand, in an editor, and confirm it is gone:
Get-Content '.claude\settings.local.json'
Remove-Item '.claude\database-override.once' -ErrorAction SilentlyContinue
```

- **Expected:** the permission prompt still appears although the allow rule matches the command. After declining, the command did not run, the second `Test-Path` prints `False`, and the last `db-guard.log` line shows the override claimed with permission mode `default`. The Observed line shows the session start time later than the file's save time; otherwise the step is void and is run again from the top. If no prompt appears, the person sets the verdict to `blocked`.
- **Observed:** Rule text: `PowerShell(sqlcmd:*)`, in `.claude\settings.local.json` (a new file). Save time: Wednesday, November 18, 2026 4:53:22 PM. The session was a new one started after the 5:21 PM attempt (its log session id differs from that attempt's), so after the save; the exact start time was not recorded. Mode `default`, session started with `--permission-mode default --plugin-dir <parent-branch worktree>` and the installed plugin disabled. A prompt appeared: "One-shot destructive database override. A person armed it. Approve only if you mean to run this exact command." Log line at 2026-11-18T22:27:31Z: tool `PowerShell`, `decision` ASK, `reason` `claimed-by-sibling` (see Findings item 4), `permission_mode` `default`. The arm file was gone afterwards (`Test-Path` printed `False`). The rule was still in the file when this was written and is to be removed by the person; the installed plugin is to be enabled again.

### Step 7: acceptEdits mode

```powershell
Set-Location '<project>'
New-Item -ItemType File -Path '.claude\database-override.once' -Force | Out-Null
claude --permission-mode acceptEdits
# In the session, ask Claude to run the same statement through sqlcmd -Q. When the prompt appears, choose No. Exit the session.
Test-Path '.claude\database-override.once'
Get-Content '.claude\logs\db-guard.log' -Tail 5
Remove-Item '.claude\database-override.once' -ErrorAction SilentlyContinue
```

- **Expected:** a permission prompt appears. After declining, the command did not run, `Test-Path` prints `False` (no arm is left), and the log shows the override claimed with permission mode `acceptEdits`.
- **Observed:** Not run. The owner closed the trial after step 6 on 2026-11-18.

### Step 8: plan mode

```powershell
Set-Location '<project>'
New-Item -ItemType File -Path '.claude\database-override.once' -Force | Out-Null
claude --permission-mode plan
# In the session, ask Claude to run the same statement through sqlcmd -Q. Note whether a prompt appears or the host refuses to run the command. Decline any prompt. Exit the session.
Test-Path '.claude\database-override.once'
Get-Content '.claude\logs\db-guard.log' -Tail 5
Remove-Item '.claude\database-override.once' -ErrorAction SilentlyContinue
```

- **Expected:** either a prompt appears or the host refuses to run the command. Either way nothing runs unprompted. Record which one happened, whether the arm survived, and the log line (if the guard ran, its permission mode).
- **Observed:** Not run. The owner closed the trial after step 6 on 2026-11-18.

### Step 9: dontAsk mode

```powershell
Set-Location '<project>'
New-Item -ItemType File -Path '.claude\database-override.once' -Force | Out-Null
claude --permission-mode dontAsk
# In the session, ask Claude to run the same statement through sqlcmd -Q. Exit the session.
Test-Path '.claude\database-override.once'          # expect True: a block keeps the arm
Get-Content '.claude\logs\db-guard.log' -Tail 5
Remove-Item '.claude\database-override.once' -ErrorAction SilentlyContinue   # remove the arm by hand
Test-Path '.claude\database-override.once'          # expect False
```

- **Expected:** no prompt. The command is blocked, the arm file is still present afterwards (a block does not consume it), and the log records a block with permission mode `dontAsk`. After the manual removal the last `Test-Path` prints `False`.
- **Observed:** Not run. The owner closed the trial after step 6 on 2026-11-18. The only evidence for a mode with no prompt is the `auto` attempt in Findings item 2 (blocked, arm kept, reason `no-prompt-available`); `dontAsk` itself was not tried.

### Step 10: record the Claude Code version

```powershell
claude --version
```

- **Expected:** one version string, copied here exactly. The person also writes this sentence into the Observed line: "A missing permission mode cannot be produced from a normal session; that case rests on the unit rows."
- **Observed:** Claude Code `2.1.327`, read with `claude --version` after the trial. A missing permission mode cannot be produced from a normal session; that case rests on the unit rows. Steps 7 to 9 were not run, so the version was not read at the time of a trial session.

## Disposition

Closed as `pass-with-findings` on 2026-11-18: step 6 was run by a person and met; steps 7 to 10 were not run, by the owner's decision. The re-review (sub-task 10) should treat the `acceptEdits`, `plan` and `dontAsk` modes as unproven by a live trial and resting on the unit rows, and should read Findings items 1 and 6.

- If every Observed line matches its Expected line, the person changes the verdict line to `**Verdict:** pass`, removes the line "Results pending: a person runs the steps below", fills in "Reviewed on", and sets each "What was checked" outcome. This gate then releases the re-review.
- If a step differs harmlessly, the person records it under "Findings" and sets `**Verdict:** pass-with-findings`.
- If step 6 shows no prompt, or any step shows a destructive command running unprompted, the verdict stays `blocked` and goes back to the architect, because the override design depends on that behaviour.
- This report supersedes nothing: the first trial's report stays in force.
