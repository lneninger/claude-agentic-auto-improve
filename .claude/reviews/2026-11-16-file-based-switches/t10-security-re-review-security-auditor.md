# t10 security re-review — security-auditor

- **Gate agent:** security-auditor
- **Sub-task:** t10-security-re-review (issue #444, parent #419)
- **Contract:** `.claude/concepts/2026-11-16-file-based-switches.md` (approved)
- **Re-reviews:** `t4-security-review-security-auditor.md` (blocked)
- **Reviewed on:** 2026-11-18
- **Commit range reviewed:** `4a5c638..7d97bc1`, the fixes block's merge into `feature/file-based-switches` (pull request #446, fix commit `0015895`). The five files it changes are `_switches.py`, `db-destructive-guard.py`, `db-research-readonly-guard.py`, `tests/test_database_override.py` and `tests/test_switches.py`.
- **Commit the t9 run sheet ran against:** `3a23bccd0603d9d9729a5ae162760f20881d5ef4`. This worktree's head is `eccbf9c`. `git diff --stat 3a23bcc eccbf9c` lists only the t9 run sheet, and `git diff --stat 7d97bc1 eccbf9c -- .claude/hooks` is empty. So the reviewed guard files are byte-identical at the commit the person tested, at the fixes merge, and at my head.

**Verdict:** blocked

There is one blocker. B1 is not cleared: a human-only command combined with another blocked operation still gets a permission prompt when the human-only script comes after any quoted text in the call. The t4 probe O13 still asks, unchanged. The fix decides the no-prompt class from every target as the review asked, but the human-only target is never produced in that position, so the new check never fires. The same root cause is older than this contract and is worse: with no arm, a human-only script placed after a quoted span is allowed with no prompt at all (P1). The t9 step 6 observation is met (an allow rule did not skip the prompt), so the override is not withdrawn. The block comes from the fixes, not from step 6. W1, W2 and N1 are cleared. W4 is cleared on POSIX but not on Windows. Destructive statements are named in words in this report, never as command text (the same deviation as t3, t4 and t9).

## What was checked

- **No-prompt classes rule (B1):** **not met.** The fix at `db-destructive-guard.py:2229` (`human_only = any(... for t in targets)`) is correct. Its input is wrong. `_in_command_position` (`:1187-1197`) strips the text before the script name with a pattern whose first branch, `\"[^\"\n]*[\\/]$`, matches from the *closing* quote of any earlier quoted span through to the slash before the script name. The text before the script then ends in a word, not a separator, so the script does not count as invoked, `_human_only_script_hits` returns `[]`, and no `human-only` target exists. O13 as written in t4 (row delete on a protected database, then `;`, then the script) gives ASK and the arm is gone. So does H7 (a removal of a non-disposable database through `sqlcmd -Q`, then the script), and so does the PowerShell form. The fixes block's rows all put the script first (`test_database_override.py:488-496`), which is the one order that works, so the suite is green. O12 and O14 now block with the arm kept. O11 still blocks.
- **Prompt-only rule:** met. No allow path was added. No probe turned a blocked command into an allow through the arm.
- **Use-once rule:** met (O1 to O3, armLeft=False).
- **Fresh-arm rule (N1):** met. O10 (arm dated one day ahead) now blocks and the arm is removed. `_is_fresh_age` gives the window `-60 <= age <= 900` and is used by both the claim and the sweep.
- **Person-present rule:** met in code. Offline, `acceptEdits` and `plan` ask (O2, O3). `bypassPermissions`, `dontAsk`, `auto`, a missing mode and `Default` block with the arm kept (O4 to O8, O20). Live, it is only partly proven. `default` asks (t3, t9 step 6), and `bypassPermissions` and headless `auto` block (t3, t9 item 2). `acceptEdits`, `plan` and `dontAsk` were never run live (t9 steps 7 to 9 not run, by the owner's decision). They rest on the unit rows and my offline probes. The contract keeps them `ASSUMED`, which is correct. That is not a blocker, because each one fails closed in code except the two prompt modes, and a prompt in those modes is the designed outcome.
- **t9 step 6 (allow rule vs hook `ask`):** met. Rule `PowerShell(sqlcmd:*)` in `.claude\settings.local.json`, saved at 4:53:22 PM. The session was started later, with mode `default` and the branch's hooks loaded through `--plugin-dir`. The prompt appeared, and the log shows ASK `claimed-by-sibling` with `permission_mode` `default`. The arm was consumed. **No allow rule skipped the prompt, so the withdrawal direction (user answer 2026-11-18) is not triggered.** Two limits: the session start time was inferred from a differing session id, not recorded, and only one rule in one settings layer was tested (not user-level or managed settings, not the `Bash(...)` form).
- **Arm-write rule, edit tools (W1):** met. R3 and R4 now block. So do `\x\..`, `/x/..\.`, a `\\?\` prefix, a trailing `. .`, and Edit on `/x/..`. The control `<arm>/../notes.md` is allowed. `/x/.. ` and `/x/...` are allowed, and that is correct: `GetFullPathNameW` and a real `open()` on this host resolve them to `…\database-override.once\x\` and fail with FileNotFoundError, and Node's `path.resolve` keeps them literal. Neither creates the arm.
- **Arm-write rule, shell tools (W2):** met in both guards. S5 now blocks, and so do `>>`, `2>`, `>|`, `&>`, `>&`, `1>'…'`, `>"…"` with no space, `2>&1 >`, a redirection placed before `git`, `$'…'`, `git tag`, `git notes`, PowerShell `*>` and `| Out-File`. The controls stay allowed: a commit message, a pull request body, a grep pattern and `git commit -m "<names the arm>" 2>&1 | tail -n 5`. `git commit -F "<arm>"` is allowed, which is correct because it reads.
- **The whole route table:** re-run, 42 rows. Every SEEN row from t4 is still SEEN, and R3, R4 and S5 moved from MISSED to SEEN. The residual MISSED rows are unchanged (R11, S10 to S18, S25, S26) and covered by the residual-risk paragraph.
- **Arm-write rule runs before Guard deference, in both guards:** met (unchanged). With the helper removed it falls back to the inline copy (P8, P8b: BLOCK).
- **Broken-file rule (W4):** met on POSIX, **not met on Windows.** POSIX: the two named-pipe rows of `test_switches.py` pass on a POSIX container (Python 3.13, `--network none`, a read-only copy of the head hooks), and the code opens with `O_NONBLOCK` and checks `fstat`. Windows: a symbolic link at `switches.local.json` whose target is `\\.\pipe\<name>`, with a pipe server that accepts and never writes, **hangs the helper** (no result within 15 s, for both `\\.\` and `\\?\` spellings). `_network_link_reason` strips `\\?\`, reads `pipe\<name>` as a relative path on the local drive (type 3), and then `open()` plus `read()` block. The contract's sentence "Windows has no named pipes at a file path" is false for a link. Symbolic links can be created without elevation on this host. Finding W4.
- **Shared-claim rule:** met (P1 to P4 unchanged).
- **Plain-reason rule:** unchanged. N2 is still reproducible (P5) and is dispositioned.
- **Variable-retired rule:** met (P7). **No-environment rule:** `test_switch_env_scan.py` gives 14 OK with 2 expected failures, which belong to the documents block.
- **Residual-risk paragraph:** partly met. It now names W3(a) (the arm is not bound to a command, and the target shows as "unresolved" for `sqlcmd -Q`) and W3(b) (the allow-rule question, with the withdrawal direction). But the W3(b) sentence is stale: it says "not yet proven" although t9 step 6 has since been met. It does not state the limits of that proof (one rule, one layer). It omits the Windows pipe-link class of W4. Finding W3.
- **W5, N2 and N3 dispositioned in Failure Modes:** met (`## Failure Modes & Mitigations`, the bullet "Security review W5, N2 and N3, not fixed here", user answer 2026-11-18). W5 and N2 go to a follow-up, and N3 is accepted.
- **Existing guard suites unchanged and green:** met (see Evidence).

## Findings

- **B1 (blocker, not cleared) — a human-only script after any quoted span is not classed human-only, so combined with another blocked operation it prompts.** Location: `.claude/hooks/db-destructive-guard.py:1187-1197` (`_in_command_position`, the strip pattern at `:1190-1192`), which feeds `_human_only_script_hits` (`:1200-1211`), `_dynamic_labels` (`:1268`), `_bind_targets` (`:1521`) and so the `human_only` flag (`:2229`).
  **Exploit scenario:** a person arms for one ordinary blocked command. The agent sends `sqlcmd -S localhost -Q "<removal of a non-disposable database>" ; tools/db-protection/update-dev-database.cmd`. The closing quote of the `-Q` argument makes the strip pattern eat everything up to `tools/db-protection/`. The script is judged "mentioned, not invoked" and gets no target. `human_only` is False, `_try_override` claims the arm, and the person sees one prompt that covers both the removal and the human-only script. O13 in its t4 order reproduces it exactly.
  **Impact:** the user-decided invariant "never prompt for them; the person runs them by hand" is still broken for the most natural combined form. The fixes block's rows cannot catch it because they only use script-first order.
  **Fix:** strip a quoted prefix only when that quote *opens* the token that holds the script name, that is, when the quote character occurs an odd number of times in `pre`. Simpler and safer: split the text into segments on unquoted `; & | && || ( newline` and test only whether the script is the first word of a segment (after a launcher word). Add armed rows in the t4 order and in PowerShell: `<protected row delete> ; <script>`, `<sqlcmd -Q removal> ; <script>`, `cd "<p>" && <script>`, and `Write-Host 'x'; <script with backslashes>`. Each expects exit 2, no ask JSON and the arm kept. Add unarmed rows for P1.
- **P1 (critical, existing before this contract, same root cause as B1) — with no arm, a human-only script after a quoted span runs with no prompt.** Location: as B1. Present at `cd8eb51` (before the contract) and at head.
  **Scenario:** `echo "start" ; tools/db-protection/update-dev-database.cmd`, or `cd "<project>" && tools/db-protection/update-dev-database.cmd`, or the PowerShell form `Write-Host 'x'; tools\db-protection\update-dev-database.cmd`, or `echo "a" && tools/db-protection/restore-latest.cmd --recover-missing-dev-db`. Each gives exit 0 (ALLOW) with no arm. Only the script alone blocks (H2).
  **Impact:** the class the guard documents as "never by an agent" runs from an agent with nobody answering anything. It changes the development database, which is the 2026-05-06 incident class.
  **Fix:** the B1 fix closes it. It is listed apart because it is not caused by this contract and needs its own rows and its own change note.
- **W4 (warning, not cleared on Windows) — a symbolic link at a switch-file path to a named pipe hangs every switch read.** Location: `.claude/hooks/_switches.py`, `_read_regular_file_bytes` (the `if non_block:` branch is POSIX only) and `_network_link_reason` (a `\\?\pipe\…` target becomes a relative path on a local drive).
  **Scenario:** in one tool call the agent starts a background pipe server that accepts and never writes, and runs `New-Item -ItemType SymbolicLink -Path .claude\switches.local.json -Target \\.\pipe\x`. From then on the concept gate, the architecture guard and every hook that reads a switch block in `read()` until the host's hook timeout, and a timed-out hook is not a block. There is no Visible-off notice. The database guards do not read switch files, so the override itself is unaffected.
  **Fix:** on every platform, open with `os.open(path, O_RDONLY | O_BINARY)` (adding `O_NONBLOCK` where it exists), then `os.fstat(fd)`, then require `S_ISREG` before any read. Verified on this host: opening a pipe through a link returns at once, and `fstat` reports `S_ISFIFO`, not `S_ISREG`. Keep the network-drive check before the open. Correct the contract's sentence "Windows has no named pipes at a file path". Add a Windows-only row: a link to a listening pipe gives every default and one report within the short timeout.
- **W3 (warning, contract text) — the residual-risk paragraph is stale and incomplete.** Location: contract, `## Failure Modes & Mitigations`, "Residual risk of the database override, in one place", and `## Uncertain Assumptions` (the allow-rule bullet is still `ASSUMED`).
  (a) "Whether a `permissions.allow` rule … can turn the guard's `ask` into an allow is not yet proven" should now read as verified by t9 step 6, limited to `PowerShell(sqlcmd:*)` in the project's `settings.local.json`, in `default` mode, on Claude Code 2.1.327. A user-level or managed rule and a `Bash(...)` rule are untested, and a later host version may change the precedence.
  (b) Name the Windows pipe-link route of W4 until it is fixed.
  (c) t9 item 1: the trial proves the branch's guard only when the installed plugin is disabled. That is not a bypass (the older guard blocks), but the README should say that an installed older copy blocks the override.
- **L1 (low) — the read-only guard can spend an arm on a call the destructive guard blocks as human-only.** Location: `db-research-readonly-guard.py` (no human-only class). The command is `<script> && sqlcmd -d Orders -Q "<row delete>"`. Armed, the read-only guard claims the arm and asks (X1), and the destructive guard blocks (X2). It fails closed if a block beats an ask (still `ASSUMED`), but the person's arm is used up by a call that could never run. **Fix:** either let the read-only guard skip the claim when the destructive guard's human-only test matches (import it the way `_mask_inert_prose` is imported), or accept and document it.
- **I1 (informational, existing before this contract, outside the reviewed range) — a link to a named pipe at the database guard's rules file hangs the destructive guard itself.** Location: `db-destructive-guard.py:439-448` (`_load_guard_rules`, plain `open()` at import). With a link at `<project>/.claude/hooks/db-destructive-guard.rules.json` to a listening pipe, the guard did not finish within 20 s on a removal of a non-disposable database, at `cd8eb51` and at head. If the host treats a hook timeout as non-blocking (t4 assumed so, and it was not verified live), that destructive command runs with no prompt and no arm. This corrects the t4 line "No path allows a destructive command without a prompt: met", which held only for routes that reach `_decide`. It is not this contract's change, so it does not count toward this verdict on its own. It is the same fix as W4 (read through the regular-file reader), and it should be tracked.
- **N2, N3, W5:** unchanged and dispositioned by the user (follow-up and accepted). Not re-raised.

## What was NOT checked

- No live Claude Code session. Host behaviour (ask shown, block beats ask, timeout treated as non-blocking) rests on t3, t9 step 6 and the documentation quoted in pull request 432.
- `acceptEdits`, `plan` and `dontAsk` live (t9 steps 7 to 9 not run).
- Allow rules in user-level or managed settings, and the `Bash(sqlcmd:*)` form.
- Whether the host's hook timeout actually lets the tool call proceed, for W4 and I1. I showed only that the hook does not finish.
- W4's network-drive branch against a real mapped network drive or share (none on this host). Only the pipe-link route was run. The Windows link rows in the suite passed.
- The ordinary switches block, the documents block and the README (out of the reviewed range).
- MCP tools that write files (a contract Non-Goal).

## Evidence

Every probe ran a guard as a separate process, in a fresh temporary project with `CLAUDE_PROJECT_DIR` pointing at it, the `CLAUDE_*` variables stripped, and the payload on standard input. The harness scripts are outside the repository: `%TEMP%\t4h\harness.py` (reused from t4), `%TEMP%\t4h\gen_override.py`, `routes.json`, `probe2.py`, plus new `%TEMP%\t10h\gen_o13.py`, `gen_h.py`, `gen_w.py`, `gen_rg.py`, `dbg.py`, `win_open.py`, `pipe_link.py`, `pipe_fstat.py` and `pipe_rules.py`. Destructive statements in them are built by string joining. Older trees for comparison were extracted with `git archive` (`cd8eb51`, `4a5c638`, `HEAD`) into `%TEMP%\t10h\{base,prefix,head}` and run by absolute path. An early run that passed a relative hooks path failed with "can't open file", was discarded and was re-run.

| Command | Exit |
|---|---|
| `git log --oneline --first-parent` (fixes merge `7d97bc1` = `4a5c638` + `bec0b34`) | 0 |
| `git diff 4a5c638 7d97bc1 -- <the three guard and helper files>` (read in full) | 0 |
| `git diff --stat 3a23bcc eccbf9c` (only the t9 run sheet) | 0 |
| `git diff --stat 7d97bc1 eccbf9c -- .claude/hooks` (empty) | 0 |
| `py -3 -I harness.py <head hooks> x override.json` (O0 to O20) | 0 |
| `py -3 -I harness.py <head hooks> x routes.json` (whole route table) | 0 |
| `py -3 -I probe2.py <head hooks>` (P1 to P9) | 0 |
| `py -3 -I harness.py <hooks> x o13.json`, `h.json` at `cd8eb51`, `4a5c638`, head | 0 |
| `py -3 -I harness.py <head hooks> x w.json` and `w_rg.json` (W1, W2 variants, both guards) | 0 |
| `py -3 -I dbg.py <hooks>` (`_human_only_script_hits` gives `[]` after a quoted span, at `4a5c638` and head) | 0 |
| `py -3 -I win_open.py` (`GetFullPathNameW` and a real open for `/x/.. `, `/x/...`, …: never the arm) | 0 |
| `py -3 -I pipe_link.py <head hooks>` (helper HUNG over 15 s, both spellings) | 0 |
| `py -3 -I -u pipe_fstat.py` (open returns in 0.00 s; `S_ISREG=False`, `S_ISFIFO=True`) | 0 |
| `py -3 -I pipe_rules.py <hooks>` at `cd8eb51` and head (destructive guard HUNG over 20 s) | 0 |
| `docker run --rm --network none … python3 -B .claude/hooks/tests/test_switches.py ReaderFileKindTests -v` (POSIX: both named-pipe rows ok) | 0 |
| `py -3 .claude/hooks/tests/test_switches.py` (58, OK, 3 POSIX skips) | 0 |
| `py -3 .claude/hooks/tests/test_database_override.py` (62 OK) | 0 |
| `py -3 .claude/scripts/tests/test_switch_env_scan.py` (14 OK, 2 expected failures) | 0 |
| `py -3 .claude/hooks/tests/test_db_destructive_guard.py` (605 of 605) | 0 |
| `py -3 .claude/hooks/tests/test_db_guard_path_allowlist.py` (93 OK) | 0 |
| `py -3 .claude/hooks/tests/test_readonly_guard_disposable_exemption.py` (16 of 16) | 0 |
| `py -3 .claude/hooks/tests/test_worktree_path_guards.py` (190 of 190) | 0 |
| `py -3 .claude/hooks/tests/test_shell_write_targets.py` (19 OK) | 0 |

**Re-run of the t4 failures.** O10: BLOCK, arm removed (was ASK). O12: BLOCK, arm kept (was ASK). **O13: ASK, arm gone (was ASK; not cleared).** O14: BLOCK, arm kept (was ASK). R3, R4: SEEN (were MISSED). S5: SEEN (was MISSED).

**Override decisions at head** (armed unless noted; a removal of a non-disposable database through `sqlcmd -Q`). O0 not armed: BLOCK. O1 `default`, O2 `acceptEdits`, O3 `plan`: ASK, arm gone. O4 `bypassPermissions`, O5 `dontAsk`, O6 `auto`, O7 mode missing, O8 `Default`: BLOCK, arm kept. O9 stale: BLOCK, removed. O10: BLOCK, removed. O11: BLOCK, kept. O15 `git status`: ALLOW, kept. O16, O17: ASK, target `unresolved` (W5). O18 no id: ASK. O19 rg: ASK. O20 rg bypass: BLOCK.

**Human-only placement** (H = `tools/db-protection/update-dev-database.cmd`). The same result at `cd8eb51`, `4a5c638` and head, except H7:

| Row | Command shape | Armed | Result |
|---|---|---|---|
| H1 | `echo "start" ; H` | no | ALLOW (P1) |
| H2 | `H` | no | BLOCK |
| H3 | PowerShell `Write-Host 'x'; H` with backslashes | no | ALLOW (P1) |
| H4 | `cd "<p>" && H` | no | ALLOW (P1) |
| H5 | `echo "a" && <restore-latest.cmd --recover-missing-dev-db>` | no | ALLOW (P1) |
| H6 | `echo "a" ; H` | yes | ALLOW, arm kept |
| H7 | `sqlcmd -Q "<removal, non-disposable>" ; H` | yes | ASK at `4a5c638` and head (B1); BLOCK at `cd8eb51` (no override then) |
| O13 | `sqlcmd -d <protected> -Q "<row delete>" ; H` | yes | ASK (B1) |
| O13b | `H ; sqlcmd -d <protected> -Q "<row delete>"` | yes | BLOCK, kept |
| O13e | PowerShell, O13 order | yes | ASK (B1) |

**Arm-write routes at head.** R1, R2, R3, R4, R5, R8, R9, R10, S1 to S5, S9, S19 to S24, S27, S28 and P8, P8b, P9: SEEN. R6, R7: MISSED, harmless (different file). R11, S10 to S18, S25, S26: MISSED, residual. S6 to S8, S29: allowed, correct.

**Files read:** the fixes diff of `_switches.py`, `db-destructive-guard.py` and `db-research-readonly-guard.py` (whole); `db-destructive-guard.py:420-455`, `:1036-1070`, `:1150-1272`, `:1487-1546`, `:2144-2233`; `test_database_override.py:484-519`; `test_switches.py` skip markers `:715-785`; the contract's Entities, Override rules, Non-Goals, Uncertain Assumptions, Failure Modes, Open Questions and blocks 8 to 10; the t4 report and the t9 run sheet.

## Disposition

**Blocked.** This holds blocks 6 and 7. The block comes from B1 in the fixes, not from t9 step 6. Step 6 was met, so the override is **not** withdrawn. Per the TASK constraint, this leads to an architect amendment of the contract that adds a further fix block and a further re-review block. No block is added without that amendment.

The further fix block (`python-ai-developer`, a sub-task pull request into `feature/file-based-switches`, no version raise) should:

1. Fix B1 at its root, `_in_command_position`, with the armed rows in the t4 order, in PowerShell, and after a quoted `cd`. The same change clears P1, which needs its unarmed rows.
2. Fix W4 on Windows (`fstat` and `S_ISREG` on the open descriptor on every platform) with a Windows pipe-link row. Recommended in the same block: read the destructive guard's rules file through the same regular-file check (I1). That is a user decision, because it predates the contract.
3. Optionally fix L1, or have the architect accept it in Failure Modes.

The architect also updates the residual-risk paragraph and the allow-rule assumption (W3 (a) to (c)) and corrects the Broken-file rule's sentence about Windows pipes. The next re-review supersedes both `t4-security-review-security-auditor.md` and this report. This report's Gate Output supersedes nothing.
