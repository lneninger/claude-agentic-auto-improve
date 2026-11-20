# t12 security re-review, round three — security-auditor

- **Gate agent:** security-auditor
- **Sub-task:** t12-security-re-review-round-three (parent #419)
- **Contract:** `.claude/concepts/2026-11-16-file-based-switches.md` (approved)
- **Re-reviews:** `t4-security-review-security-auditor.md` (blocked) and `t10-security-re-review-security-auditor.md` (blocked)
- **Reviewed on:** 2026-11-19
- **Commit range reviewed:** `d11572c..d43a285`. This is the second fixes block's (11) merge into `feature/file-based-switches` (pull request #457; RED commit `a40e9d3`, fix commit `4852a08`). It changes `_switches.py`, `db-destructive-guard.py`, `db-research-readonly-guard.py`, `tests/test_database_override.py` and `tests/test_switches.py`, plus the t11 brief.
- **Head:** this worktree's head is `d43a285` itself, so the reviewed guard and helper files do not differ between the merge and my head. Every probe ran against scratch trees made with `git archive` under `%TEMP%\t12h\` (`head` = `d43a285`, `base` = `d11572c`), plus the pre-contract tree `%TEMP%\t10h\base` (`cd8eb51`).

**Verdict:** blocked

There is one blocker. B1 is not cleared, for a third round. Every reported probe now blocks in the destructive guard, in its original clause order and in both shells, and so do the quoted-launcher rows. But the new quote scanner (`_starts_a_command`) reads quotes with one escape model for both shells, and that model is wrong for each of them. The commonest Windows spelling, PowerShell `cd "<folder>\"; <script>` (a trailing backslash before the closing quote), reads as "inside a quote". So does bash `cd "C:\\w\\" && <script>`, and so do escaped quotes outside quotes in both shells. Armed, such a call after a database write gives ASK from both guards. Unarmed, it runs the human-only script with no prompt (P1). I checked every shape in a real shell with a harmless probe script, and the trailing command runs in each one. W4 and I1 are cleared by a real attempt with a listening pipe. Destructive statements are named in words in this report, never as command text (the same deviation as t3, t4, t9 and t10).

## What was checked

- **No-prompt classes rule (B1), the reported probes:** met. O13, O13e (both the t10 forward-slash spelling and the backslash spelling), H6, H7 (bash and PowerShell), and the t10 Disposition's `cd "<p>" && <script>` and `Write-Host 'x'; <script>` forms were each run armed in `default` mode, each in its own fresh project. The destructive guard gives exit 2, no ask JSON, the arm kept, no claim file, and the human-only line "It never becomes a prompt." O12 and O14 block with the arm kept. O11 and O13b (script first) still block.
- **No-prompt classes rule (B1), other spellings of the same rule:** **not met.** The contract's sentence (`Data Shapes`, Override rules) splits segments "on separators outside quotes" and says "Quoted text in an earlier segment never decides it". In the shapes below, quoted text in an earlier segment still decides it, because the scanner disagrees with the shell about where the quote ends. See finding B1.
- **P1 (no arm), the reported probes:** met. H1 (bash and PowerShell), H3, H4 (bash and PowerShell) and H5 (bash and PowerShell, with the recover flag) each block with the human-only line. H2 (the script alone) blocks.
- **P1, other spellings:** **not met.** Nine shapes are allowed with no arm, exit 0, and each one runs the trailing script in the real shell (finding P1).
- **Quoted launchers:** met. `bash -c "cd x; <script>"`, `cmd /c "echo a & <script>"` (Bash and PowerShell tools) and `powershell -Command "Write-Host x; <script>"` block, armed and unarmed. So do `sh -c '…'`, `pwsh -c "…"`, `cmd /k "…"`, `iex "…"`, `Invoke-Expression '…'`, `bash -lc "cd \"<p>\" && …"` and `powershell -NoProfile -Command "…"`.
- **Mention controls:** met. A commit message, an `echo` text, a grep pattern, a pull request body, `Write-Host '…'` naming the script, `cat <script>`, and an armed `echo "<script>" ; git status` all give exit 0. The armed control keeps its arm.
- **Classifier monotonicity ("may only move a form from mentioned to invoked"):** met by reading. `_in_command_position` keeps the old reading and ORs the new one in (`db-destructive-guard.py:1335-1351`).
- **The read-only guard beside each probe (L1 accepted):** as the contract pins it. Armed, it asks and renames the arm to the claim on H7 (both shells) and on O13 and O13e in the suite's spelling (`sqlcmd -S "(localdb)\m" -E -d <protected> …`). On t4's literal O13 and O13e (no `-S`), it gives exit 0 and keeps the arm, which is a closed outcome because the destructive guard blocks. It gives exit 0 on H6, on the cd and Write-Host forms, on O12, O14, the launchers and every unarmed H row. It never blocks a human-only shape, as designed.
- **Evidence for "a hook block beats a hook ask":** documentation only. Pull request 432 quotes the hooks documentation: "deny > defer > ask > allow; exit 2 routes as deny". No live session has observed a block and an ask answering one call. t9 step 6 logged `claimed-by-sibling`, which is ASK from both guards, not a block beside an ask. The contract keeps it `ASSUMED`, which is correct. For B1's new shapes the question does not arise: there both guards ask, so no block exists to win.
- **Prompt-only, use-once, fresh-arm (N1) and person-present rules:** met. O0 to O20 are unchanged from t10 (see Evidence). O10 (arm dated one day ahead) blocks and the arm is removed.
- **Arm-write rule (W1, W2), the whole route table:** met, unchanged from t10. R3, R4 and S5 are SEEN. The residual MISSED rows are the same as before (R11, S10 to S18, S25, S26).
- **Shared-claim rule and Guard fallback mode:** met. P1 to P4 are unchanged. P8 and P8b (helper removed, parser removed) refuse the arm writes, and P9 (non-ASCII payload) refuses in both guards. P7 (retired variable set) blocks in both guards.
- **Broken-file rule (W4), real attempt on Windows:** **met.** I ran a pipe server on `\\.\pipe\<unique>` that accepts and never writes, and put a link at `switches.local.json`, with the committed `switches.json` saying `concept_gate` and `architecture_guard` `off`. The links were made with `os.symlink` and with `cmd /c mklink`, in the `\\.\` and `\\?\` spellings. Each read finishes in 0.10 to 0.14 s with every key at its default (the committed `off` is ignored). Each logs exactly one `switches` report in `.claude/logs/errors.jsonl`, and a second read does not repeat it. The helper classes the link `broken` / `unreadable` ("the link points into the device namespace"). A directory link at `.claude` itself to the pipe namespace also finishes at once with every default. Links were created without elevation by `os.symlink` and `mklink`. PowerShell `New-Item -ItemType SymbolicLink` refused with "Administrator privilege required" (finding N5).
- **I1, rules file, real attempt:** **met for both guards.** I put a link at `<project>/.claude/hooks/db-destructive-guard.rules.json` to a listening pipe, in both spellings, plus a link to a `\\server\share` path and a directory link at `.claude/hooks` into the pipe namespace. I ran this with the helper present, deleted, and stale (the `d11572c` `_switches.py`, which lacks `read_regular_file_bytes`). The destructive guard blocks a removal of a non-disposable database within 0.18 s in every case. The read-only guard blocks a write on a disposable-named database in every link case: the exemption is withdrawn, which is the accepted false block. With a regular rules file it allows that write, so the exemption still loads.
- **Residual-risk paragraph:** partly met. W3(a) (the arm is not bound to a command; "unresolved" for `sqlcmd -Q`) is named. W3(b) with the t9 limits (one rule, one layer, `default`, 2.1.327, plugin disabled, start time inferred, void by block 9's own rule) is named. The Windows pipe-link route is named. But the paragraph says these classes hold "until block 11 merges". That is now false for B1 and P1, it does not name the shapes in finding P2, and it does not name the audit-log route (finding I2). Finding W6.
- **Failure Modes dispositions:** present for W4 (POSIX and Windows), B1 (both entries), P1, I1 and the I1 false block, L1 (accepted, "fails closed only if a block beats an ask"), t9 steps 7 to 9 (named residual), and W5, N2 and N3. The B1 and P1 mitigations ("block 11 fixes the classifier") are not achieved for the shapes below.
- **Guard suites:** all eight exit 0 (see Evidence).

## Findings

- **B1 (blocker, not cleared, round three): the quote scanner uses one escape model for both shells, so a human-only script after a quoted span still claims the arm in common spellings.** Location: `.claude/hooks/db-destructive-guard.py:1297-1332` (`_starts_a_command`), reached from `_in_command_position` (`:1335-1351`) and `_human_only_script_hits` (`:1354-1365`). Inside double quotes it treats `\"` and `` `" `` as escapes for both shells (`:1311-1314`). That is wrong for PowerShell, where `\` is a plain character, and wrong for bash `\\"` and PowerShell ``` ``" ```, where the escape character is itself escaped and the quote closes. Outside quotes it treats nothing as an escape. That is wrong for bash `\"` and `\'` and for PowerShell `` `" ``. It does not know bash ANSI-C `$'…\'…'`. The prose masker leaves the script name visible in every shape below (`mask_probe.py`), so the defect is in the classifier alone.
  **Exploit scenario:** a person arms for one ordinary blocked command. The agent sends, in PowerShell, `sqlcmd -d <protected> -Q "<row delete>"; cd "C:\w\"; tools\db-protection\update-dev-database.cmd`, or the natural `cd "<project>\"; <script>` after a removal of a non-disposable database. The scanner reads `\"` as an escaped quote, so the script sits "inside" a quote and gets no human-only target. `human_only` is False, the arm is claimed, and both guards ask. Reproduced armed: N1b (PowerShell, row delete on a protected database, then `cd "C:\w\"; <script>`): destructive guard ASK. N2a (bash, removal through `sqlcmd -Q`, then `; cd "C:\\w\\" && <script>`): ASK from both guards. K4 (bash `echo \" ; <script>`), K5 (PowerShell `` Write-Host `" ; <script> ``) and K6 (PowerShell `cd "<p>\"; <script>`), each after a removal: ASK from both guards. Each one is ASK at `d11572c` too, so block 11 did not reach these spellings.
  **Impact:** the user-decided invariant "never prompt for them; the person runs them by hand" still breaks. The trailing backslash form is the one a Windows agent writes when it changes into a folder. The suite stays green because every copied row uses balanced, escape-free quotes.
  **Fix:** stop guessing one shell's quoting. Class the script as invoked when ANY of these readings says so, which can only move a mention to an invocation: (1) the existing two readings; (2) a bash reading (backslash escapes outside quotes and inside double quotes, no escapes inside single quotes, `$'…'` with backslash escapes); (3) a PowerShell reading (backtick escapes in and outside double quotes, `""` and `''` doubling, no backslash escapes); (4) a quote-blind reading: strip the folder-prefix token and an optional quote before it, and test whether the nearest preceding character is a separator (`; & | ( { newline`). The prose masker has already blanked commit messages, echo text, grep patterns and pull request bodies (`main`, `:2230`), so the mention rows stay allowed. Add armed rows (destructive guard alone, its own arm each, expect exit 2, no ask JSON, arm kept) in t12's exact spelling: N1a, N1b, N2a, K4, K5, K6. Add unarmed rows (expect exit 2) for P1's nine shapes. Re-run MENTION_ROWS unchanged.
- **P1 (critical, existing before this contract, same root cause): with no arm, nine shapes run a human-only script with no prompt.** Location: as B1. Each one is ALLOW at `cd8eb51`, at `d11572c` and at `d43a285`, and each runs the trailing command in the real shell (verified with `tools\probe\ran.cmd`, which prints `RAN`, in Windows PowerShell 5.1, and with `tools/probe/ran.sh` in Git Bash):
  N1 PowerShell `Set-Location "C:\work\"; <script>`; N1c PowerShell `Write-Host "C:\work\"; <script>`; N15 PowerShell `cd "<project>\"; <script>`; N5 PowerShell `` Write-Host `" ; <script> ``; N6 PowerShell ``` Write-Host "a``"; <script> ```; N2 bash `cd "C:\\work\\" && <script>`; N2b bash `echo "a\\" ; <script>`; N3 bash `echo \" ; <script>`; N4 bash `echo $'a\'b' ; <script>`.
  **Impact:** the 2026-05-06 incident class. An agent changes the development database with nobody answering anything.
  **Fix:** the B1 fix. These need their own unarmed rows and a line in the P1 change note.
- **P2 (high, existing before this contract, outside the contract's literal definition): a script after a shell keyword, a prefix command or inside backtick substitution counts as mentioned.** Location: `_INVOKING_WORDS` (`:1269-1271`) and `_COMMAND_SEPARATORS` (`:1273`). With no arm these all give ALLOW at head, at `d11572c` and at `cd8eb51`, and all run the script in Git Bash: N7 `` echo `<script>` ``, N8 `if true; then <script>; fi`, N9 `time <script>`, N10 `env <script>`, N11 `nohup <script>`, N12 `for i in 1; do <script>; done`, N13 `! <script>`. Armed after a removal, K1 (`time`), K2 (`then`) and K3 (backticks) give ASK from both guards. The contract defines "invoked" as the first word of a segment split on `; & | && || ( newline`, after a known launcher word. These shapes fall outside that list, so this is a gap in the rule, not a divergence from it.
  **Fix:** the architect extends the rule: the words `then`, `do`, `else`, `elif`, `!`, `time`, `env`, `nohup`, `exec`, `command`, `builtin`, `nice`, `timeout`, `xargs` and `sudo` (any `NAME=value` assignments skipped) start a command, and a backtick opens a segment. Add the rows in the same fix block, because the change is in the same function.
- **I2 (high, existing before this contract, same class as I1, outside this contract's scope): a link at the destructive guard's audit log to a pipe that never reads hangs the guard on its block path.** Location: `db-destructive-guard.py:782-797` (`_audit`, a plain `AUDIT_LOG.open("a")` on `<project>/.claude/logs/db-guard.log`), called before the block returns (`:2390-2394`). I created a link there to a pipe with zero buffers that accepts and never reads. A removal of a non-disposable database then gave no result within 20 s, at `cd8eb51` and at head (`pipe_audit.py`). The read-only guard finished in 0.13 s, because it does not write its audit to the project path. The I1 mitigation reads "a file that fails the check takes the existing fail-closed path", and that is true for the rules file. The same "guard times out before it answers" route stays open through the audit write. Whether the host then lets the call proceed is not verified live (see What was NOT checked).
  **Fix:** before the append, refuse a log that is a link or not a regular file (`lstat`, then the helper's link-target check), and open with `O_WRONLY | O_APPEND | O_CREAT` plus `O_NONBLOCK` where it exists. Then `fstat` the descriptor and require `S_ISREG` before any write, and on failure skip the audit (the decision is already made). This predates the contract, so as with I1 it is a user decision whether it joins the next fix block.
- **W6 (warning, contract text): the residual-risk paragraph is out of date after block 11.** Location: contract, `## Failure Modes & Mitigations`, "Residual risk of the database override, in one place", the sentences "Until block 11 merges: …" and "After block 11, …". (a) B1 and P1 are not closed for the B1 and P1 shapes above. (b) P2 is not named. (c) I2 (audit-log pipe link) is not named, while the paragraph implies the guard-timeout route is closed. (d) In the L1 entry, "The same holds for the reported orders O13, O13e and H7: block 11's read-only guard rows pin that it asks" holds only for the suite's spelling with `-S`. With t4's literal O13 the read-only guard allows and keeps the arm. That is a closed outcome, but the sentence overstates it.
- **N5 (informational): how links are created on this host.** `os.symlink` and `cmd /c mklink` create a file link without elevation. PowerShell `New-Item -ItemType SymbolicLink` refuses ("Administrator privilege required"), so t10's route through `New-Item` needs another tool on this host. Both spellings are stored as `\\?\pipe\<name>` (`os.readlink`), so the `\\.` branch of the link check is not reached by these creation routes. The open-then-`fstat` check behind it covers that case. The contract's "Symbolic links need no elevation on the auditor's host" should name the tool.
- **N6 (informational, existing before this contract): the restore script's recover flag is matched as text after the script name.** With `F=--recover-missing-dev-db; tools/db-protection/restore-latest.cmd $F` the guard gives ALLOW (N14), because the flag text comes before the name. This is the same text-guard limit as the arm-write residual rows S10 to S14. It is listed for the W5 follow-up, not as a finding against block 11.
- **Information, as the task asks: other hooks that read a rules or data file with a plain open (the same class as I1, out of this contract's scope).** `architecture-guard.py:118` and `:147` (`architecture-guard.rules.json` through `_pp.hook_file`), `:297` (`<project>/.app-rules.json`) and `:457` (`architecture-guard.exceptions.json`); `integration-check.py:72-73` (`integration-check.rules.json` through `_pp.hook_file`); `working-agreements.py:187` and `:201` (`working-agreements.rules.json` beside the hook itself, the plugin folder); `protected-names-warning.py:106` (`_read_small`, `open(path, "rb")`). `_protected_names.py:325-327` checks `is_file()` before reading, so a pipe fails the check instead of hanging. I did not run a pipe link against these.

## What was NOT checked

- No live Claude Code session. Whether a hook block beats a hook ask, and whether a timed-out hook lets the call proceed (W4, I1, I2), rest on the documentation quoted in pull request 432 and on t3 and t9.
- `acceptEdits`, `plan` and `dontAsk` live (t9 steps 7 to 9 not run; a named residual).
- Allow rules in user-level or managed settings, and the `Bash(sqlcmd:*)` form.
- PowerShell 7 (`pwsh` is not installed on this host). The PowerShell shapes were run in Windows PowerShell 5.1 only. PowerShell 7 has the same quoting rules for `\` and the backtick.
- The B1 and P1 shapes through the Bash tool as Claude Code actually runs it (Git Bash). I ran the shapes in Git Bash and Windows PowerShell directly, with a harmless probe script in place of the human-only script.
- A pipe link against the other hooks listed under Information.
- POSIX: the POSIX named-pipe rows were not re-run in a container this round. `test_switches.py` skips its 3 POSIX rows here, and the POSIX branch is unchanged in shape (now shared with Windows).
- MCP tools that write files (a contract Non-Goal). The ordinary switches block and the documents block (out of the reviewed range).

## Evidence

Every probe ran a guard as a separate process, in a fresh temporary project with `CLAUDE_PROJECT_DIR` pointing at it, the `CLAUDE_*` variables stripped, and the payload on standard input. Destructive statements in the harness files are built by string joining. Harness files (outside the repository, under `C:\Users\lneni\AppData\Local\Temp\`): `t12h\harness12.py` (reports the arm, the claim file and the human-only line), `t12h\gen_fail.py`, `t12h\gen_cand2.py`, `t12h\mask_probe.py`, `t12h\pipe12.py`, `t12h\pipe12b.py`, `t12h\pipe12c.py`, `t12h\pipe_audit.py`, `t12h\shell\ps_shapes.ps1`, `t12h\shell\bash_shapes.sh` (with `tools\probe\ran.cmd` and `ran.sh`, which only print `RAN`), and the reused t4 files `t4h\harness.py`, `t4h\gen_override.py`, `t4h\routes.json` and `t4h\probe2.py`.

| Command | Exit |
|---|---|
| `git log --first-parent --oneline -5` (merge `d43a285` = `d11572c` + `070e71e`) | 0 |
| `git show --stat d43a285` (the five hook files and the brief) | 0 |
| `git rev-parse HEAD` (`d43a285…`: head is the merge) | 0 |
| `git diff d11572c d43a285 -- <the three guard and helper files>` (read in full) | 0 |
| `git archive` of `d43a285` and `d11572c`, extracted to `%TEMP%\t12h\head` and `base` | 0 |
| `py -3 -I harness12.py <head hooks> s_fail.json dg,rg` (failing probes, both guards) | 0 |
| `py -3 -I harness12.py <head hooks> s_launch.json dg,rg` and `s_ctrl.json` | 0 |
| `py -3 -I harness12.py <hooks> s_cand.json dg[,rg]` at head, `d11572c` and `cd8eb51` | 0 |
| `py -3 -I harness12.py <head hooks> s_cand2.json dg,rg` (armed K1 to K6) | 0 |
| `powershell -NoProfile -ExecutionPolicy Bypass -File ps_shapes.ps1` (`RAN` after each of N1, N1c, N5, N6, N15) | 0 |
| `bash bash_shapes.sh` (`RAN` after each of N2, N2b, N3, N4, N7 to N13; the last line, `! ran.sh`, sets 1) | 1 |
| `py -3 -I mask_probe.py <head hooks>` (the name stays visible after masking; no hit on raw or masked text) | 0 |
| `py -3 -I harness.py <head hooks> x override.json` (O0 to O20) | 0 |
| `py -3 -I harness.py <head hooks> x routes.json` (whole route table) | 0 |
| `py -3 -I probe2.py <head hooks>` (P1 to P9) | 0 |
| `py -3 -I pipe12.py <head hooks> <d11572c _switches.py>` (W4 and I1, helper present, deleted, stale) | 0 |
| `py -3 -I pipe12c.py <head hooks>` (W4, links by `os.symlink` and `mklink`, committed `off`, one report) | 0 |
| `py -3 -I pipe_audit.py <hooks>` at head and `cd8eb51` (destructive guard HUNG over 20 s with a linked audit log) | 0 |
| `gh pr view 432 --json body` ("deny > defer > ask > allow; exit 2 routes as deny") | 0 |
| `py -3 .claude/hooks/tests/test_switches.py` (63 tests, OK, 3 POSIX skips) | 0 |
| `py -3 .claude/hooks/tests/test_database_override.py` (145 tests, OK) | 0 |
| `py -3 .claude/hooks/tests/test_db_destructive_guard.py` (605 of 605) | 0 |
| `py -3 .claude/hooks/tests/test_db_guard_path_allowlist.py` (93 tests, OK) | 0 |
| `py -3 .claude/hooks/tests/test_readonly_guard_disposable_exemption.py` (16 of 16) | 0 |
| `py -3 .claude/hooks/tests/test_worktree_path_guards.py` (190 of 190) | 0 |
| `py -3 .claude/hooks/tests/test_shell_write_targets.py` (19 tests, OK) | 0 |
| `py -3 .claude/scripts/tests/test_switch_env_scan.py` (14 tests, OK, 2 expected failures owned by the documents block) | 0 |

**Re-run of the t4 and t10 failures at head** (H = `tools/db-protection/update-dev-database.cmd`, HB = the backslash spelling; dg = destructive guard, rg = read-only guard; each guard in its own project with its own arm):

| Probe | Shell | Armed | dg | rg |
|---|---|---|---|---|
| O13 `sqlcmd -d <protected> -Q "<row delete>" ; H` (t4 literal) | Bash | yes | BLOCK, arm kept, human-only line | ALLOW, arm kept |
| O13 suite spelling (`-S "(localdb)\m" -E -d <protected>`) | Bash | yes | BLOCK, arm kept | ASK, claimed |
| O13e t10 spelling (forward slashes) | PowerShell | yes | BLOCK, arm kept | ALLOW, arm kept |
| O13e backslashes, t4 literal / suite spelling | PowerShell | yes | BLOCK, arm kept / BLOCK, arm kept | ALLOW / ASK, claimed |
| H1 `echo "start" ; H` | Bash, PowerShell | no | BLOCK, BLOCK | ALLOW, ALLOW |
| H3 `Write-Host 'x'; HB` | PowerShell | no | BLOCK | ALLOW |
| H4 `cd "<p>" && H` | Bash, PowerShell | no | BLOCK, BLOCK | ALLOW, ALLOW |
| H5 `echo "a" && <restore script> --recover-missing-dev-db` | Bash, PowerShell | no | BLOCK, BLOCK | ALLOW, ALLOW |
| H6 `echo "a" ; H` | Bash, PowerShell | yes | BLOCK, arm kept (both) | ALLOW, arm kept |
| H7 `sqlcmd -S localhost -Q "<removal, non-disposable>" ; H` | Bash, PowerShell | yes | BLOCK, arm kept (both) | ASK, claimed (both) |
| Disposition cd form `cd "<p>" && H` | Bash, PowerShell | yes | BLOCK, arm kept (both) | ALLOW, arm kept |
| Disposition `Write-Host 'x'; HB` | PowerShell | yes | BLOCK, arm kept | ALLOW, arm kept |
| O12 EF removal with the argument-position bug ; H | Bash | yes | BLOCK, arm kept | ALLOW, arm kept |
| O14 EF forward update ; EF removal with the argument-position bug | Bash | yes | BLOCK, arm kept | ALLOW, arm kept |
| O10 arm dated one day ahead | Bash | yes | BLOCK, arm removed | BLOCK, arm removed |
| R3 Write `<arm>/.`, R4 Write `<arm>/x/..`, S5 `git commit -m "x" > "<arm>"` | — | — | SEEN (exit 2) | — |

**Quoted launchers at head** (dg; rg gives exit 0 on each): `bash -c "cd x; H"`, `cmd /c "echo a & HB"`, `powershell -Command "Write-Host x; HB"` (unarmed and armed, arm kept), `sh -c '…'`, `pwsh -c "…"`, `cmd /k "…"`, `iex "…"`, `Invoke-Expression '…'`, `bash -lc "cd \"<p>\" && H"`, `powershell -NoProfile -Command "…"`: every one is BLOCK.

**Controls at head** (both guards exit 0): the commit message, `echo "H"`, the grep pattern, the pull request body, `cat H`, `Write-Host 'run HB'`, and armed `echo "H" ; git status` (arm kept). O11 armed, O13b armed and H2 give dg BLOCK, arm kept.

**B1 and P1 shapes not covered by block 11** (dg; the same at `d11572c`; at `cd8eb51` the armed rows block because the override did not exist yet):

| Row | Shape | Armed | dg | rg |
|---|---|---|---|---|
| N1 / N1a | PowerShell `Set-Location "C:\work\"; HB` | no / yes | ALLOW / ALLOW, arm kept | ALLOW |
| N1b | PowerShell row delete on a protected database `; cd "C:\w\"; HB` | yes | **ASK, claimed** | ALLOW, arm kept |
| N1c | PowerShell `Write-Host "C:\work\"; HB` | no | **ALLOW** | ALLOW |
| N15 | PowerShell `cd "<p>\"; HB` | no | **ALLOW** | ALLOW |
| N5 | PowerShell `` Write-Host `" ; HB `` | no | **ALLOW** | ALLOW |
| N6 | PowerShell ``` Write-Host "a``"; HB ``` | no | **ALLOW** | ALLOW |
| N2 | Bash `cd "C:\\work\\" && H` | no | **ALLOW** | ALLOW |
| N2a | Bash removal `; cd "C:\\w\\" && H` | yes | **ASK, claimed** | ASK, claimed |
| N2b | Bash `echo "a\\" ; H` | no | **ALLOW** | ALLOW |
| N3 | Bash `echo \" ; H` | no | **ALLOW** | ALLOW |
| N4 | Bash `echo $'a\'b' ; H` | no | **ALLOW** | ALLOW |
| K4, K5, K6 | removal, then N3 / N5 / N15 | yes | **ASK, claimed** | ASK, claimed |
| N7 to N13 (P2) | backticks, `then`, `time`, `env`, `nohup`, `do`, `!` | no | ALLOW | ALLOW |
| K1, K2, K3 (P2) | removal, then `time H` / `then H` / backticks | yes | ASK, claimed | ASK, claimed |
| N14 (N6) | `F=--recover-missing-dev-db; <restore script> $F` | no | ALLOW | ALLOW |

**Override decisions at head** (armed unless noted; a removal of a non-disposable database through `sqlcmd -Q`). O0 not armed: BLOCK. O1 `default`, O2 `acceptEdits`, O3 `plan`: ASK, arm gone. O4 `bypassPermissions`, O5 `dontAsk`, O6 `auto`, O7 mode missing, O8 `Default`: BLOCK, arm kept. O9 stale: BLOCK, removed. O10 future: BLOCK, removed. O11, O12, O13, O14: BLOCK, kept. O15 `git status`: ALLOW, kept. O16, O17: ASK (target `unresolved`, W5). O18 no id: ASK. O19 rg: ASK. O20 rg bypass: BLOCK, kept.

**Arm-write routes at head.** R1 to R5, R8 to R10, S1 to S5, S9, S19 to S24, S27, S28: SEEN. R6, R7: MISSED, harmless (a different file). R11, S10 to S18, S25, S26: MISSED, residual. S6 to S8, S29: allowed, correct.

**Shared claim and fallback at head.** P1 dg then rg: ASK, ASK. P2 rg then dg: ASK, ASK. P3 no id: ASK, BLOCK. P4 different id: ASK, BLOCK. P5: the quote-forged name survives (N2, dispositioned). P6, P6b: ASK with neutralised targets. P7: BLOCK, BLOCK. P8 helper removed: BLOCK on the destructive command, the Write to the arm and rg `touch`. P8b helper and parser removed: BLOCK. P9 non-ASCII payload: BLOCK in both guards.

**W4 and I1 real attempts at head.** W4, link at `switches.local.json` to a listening pipe: `os.symlink` `\\.\` 0.10 s, `mklink` `\\.\` 0.14 s, `os.symlink` `\\?\` 0.13 s, `mklink` `\\?\` 0.12 s. Each gives every default with the committed `off` ignored, and 1 report that is not repeated. `New-Item` refused (elevation). A directory link at `.claude` into the pipe namespace: 0.10 s, every default. I1, link at `.claude/hooks/db-destructive-guard.rules.json`, helper present / deleted / stale, each case: regular file: dg BLOCK, rg ALLOW (exemption loads). `\\.\` pipe, `\\?\` pipe, `\\server\share`, and a directory link at `.claude/hooks`: dg BLOCK, rg BLOCK. All in 0.12 to 0.18 s.

**Files read:** the block-11 diff of `_switches.py`, `db-destructive-guard.py` and `db-research-readonly-guard.py` (whole); `db-destructive-guard.py:782-797`, `:1110-1160`, `:1266-1425`, `:1672-1676`, `:2375-2468`; `test_database_override.py:60-90` and `:755-919`; `test_switches.py` (pipe and log helpers, `:139-210`, `:284-345`, `:820-890`); the plain-open sites under Information. The contract's Entities, Override rules, Uncertain Assumptions, Failure Modes, the residual-risk paragraph, and blocks 11 and 12. The t4 and t10 reports.

## Disposition

**Blocked.** This holds blocks 6 and 7. The block comes from B1 (round three) and P1: the No-prompt classes rule's own sentence ("segments are split on separators outside quotes … Quoted text in an earlier segment never decides it") is not met for the trailing-backslash and escaped-quote spellings, in either shell. W4 and I1 are cleared, and this report records that. Per the TASK constraint, this leads to an architect amendment of the contract that adds a further fix block and a further review block. No block is added without that amendment.

The further fix block (`python-ai-developer`, a sub-task pull request into `feature/file-based-switches`, no version raise) should:

1. Fix B1 and P1 in `_starts_a_command` / `_in_command_position` with the union of readings described under B1. Each one can only move a mention to an invocation. Add the armed rows N1a, N1b, N2a, K4, K5 and K6, and the unarmed rows N1, N1c, N2, N2b, N3, N4, N5, N6 and N15, in this report's exact spelling. Each copied row must fail at the parent tip (the block 8 and block 11 convention). Keep MENTION_ROWS and LAUNCHER_ROWS unchanged and green.
2. If the architect extends the rule (P2): treat keyword, prefix-command and backtick positions as command starts, with rows N7 to N13 and K1 to K3.
3. If the user includes it (I2, as with I1): read-only checks before the audit append, with a Windows pipe-link row at `.claude/logs/db-guard.log` that must finish within the short timeout and still block.

The architect also updates the residual-risk paragraph and the L1 entry (W6 (a) to (d)) and the elevation sentence (N5). The next re-review supersedes `t4-security-review-security-auditor.md`, `t10-security-re-review-security-auditor.md` and this report. This report's Gate Output supersedes nothing.
