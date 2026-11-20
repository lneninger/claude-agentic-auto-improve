# t14 security re-review, round four — security-auditor

- **Gate agent:** security-auditor
- **Sub-task:** t14-security-re-review-round-four (parent #419)
- **Contract:** `.claude/concepts/2026-11-16-file-based-switches.md` (approved, amendment 3)
- **Re-reviews:** `t4-security-review-security-auditor.md`, `t10-security-re-review-security-auditor.md` and `t12-security-re-review-round-three-security-auditor.md` (all three blocked)
- **Reviewed on:** 2026-11-20
- **Commit range reviewed:** `4a67d1a..4a817cb`. This is the third fixes block's (13) merge into `feature/file-based-switches` (pull request #464; RED commit `7ef8609`, fix commit `3505346`). It changes `db-destructive-guard.py`, `db-research-readonly-guard.py`, `tests/test_database_override.py` and the t13 brief. `test_db_destructive_guard.py` and `_switches.py` are not changed. `MENTION_ROWS` and `LAUNCHER_ROWS` are unchanged (`git diff` shows no `-` or `+` line naming them).
- **Head:** this worktree's head is `4a817cb` itself, so the reviewed guard and helper files do not differ between the merge and my head. Every probe ran against scratch trees made with `git archive` under `%TEMP%\t14h\` (`head` = `4a817cb`, `base` = `4a67d1a`), plus the pre-contract tree `%TEMP%\t10h\base` (`cd8eb51`) and the stale helper `%TEMP%\t12h\base` (`d11572c`).
- **Naming:** "t4 probes P1 to P9" are t4's shared-claim and fallback probes. "Finding P1" and "finding P2" are this report's findings and keep t12's meaning. t12's findings N5 and N6 are not its probe shapes N5 and N6. Row ids W, V, X, A, D, CV, CW and M are this report's own (harness files under Evidence).

**Verdict:** blocked

There is one blocker. B1 is not cleared, for a fourth round. Every probe that t4, t10 and t12 reported now blocks in the destructive guard. That covers its original clause order, both shells, the quoted launchers, and block 13's per-word and short valued-option rows. I2 is cleared in both guards by a real pipe-link attempt, and W4 and I1 still hold. But two new spelling classes inside the No-prompt classes rule's own definition still read as "mentioned": a quote that opens mid-word right before the script name (`tools/db-protection/"<script>"`), and an apostrophe in a `#` comment on an `echo`, `Write-Host`, `git commit` or `grep` line. Armed, both guards ask. With no arm, the script runs, and I saw it run in a real Git Bash and a real Windows PowerShell. The comment-apostrophe defect sits in the shared prose masker and predates this contract. It also hides any destructive statement on later lines from the destructive guard: an EF removal sent this way is allowed by both guards with no arm and no prompt (finding Q1, critical). Destructive statements are named in words in this report, never as command text.

## What was checked

- **No-prompt classes rule (B1), every reported probe in its original clause order and shell, armed as reported:** met. t4's O12, O13, O14 and t10's O13e (forward slashes and backslashes), H6, H7 and the Disposition's `cd` and `Write-Host` forms block. Each gives exit 2, no ask JSON, the arm kept, no claim, and the human-only line. t12's armed N1a, N1b, N2a, K1 to K6 block the same way. O11 and O13b block.
- **P1 (no arm), every reported probe:** met. t10's H1 (both shells), H3, H4 (both), H5 (both) and t12's N1, N1c, N2, N2b, N3 to N6, N15 block.
- **P2 rows and block 13's per-word and valued-option rows:** met. N7 to N13, `else`, `elif`, `exec`, `command`, `builtin`, `nice`, `timeout 5`, `xargs`, `sudo` and a leading `FOO=1` (W1 to W10) block, along with `nice -n 10`, `sudo -u root`, `env -u NAME`, `timeout -s KILL 5`, `exec -a name` and `xargs -I {}` (V1 to V6). Armed V7 blocks with the arm kept. `command -v <script>` and `command -V <script>` stay allowed (CV1, CV2), and so does armed `command -v <script> ; git status` (arm kept). `echo then <script>`, `grep -n time <script>` and a commit message holding `then <script>` stay allowed.
- **No-prompt classes rule, further spellings of the same rule:** **not met.** Two classes inside the rule's literal definition ("the word that holds it, quoted or not, is the first word of a command segment") are read as mentioned (finding B1). A third set of command starts lies outside the rule's word list (finding P3). The rule's own sentence on valued options is not met for long options with a separate value (finding P2).
- **Quoted launchers:** met. `bash -c`, `sh -c`, `cmd /c`, `cmd /k`, `powershell -Command`, `powershell -NoProfile -Command`, `pwsh -c`, `iex`, `Invoke-Expression` and `bash -lc "cd \"<p>\" && …"` block, armed (arm kept) and unarmed. Git Bash `cmd //c "echo a & <script>"` blocks (X12). Unquoted `cmd //c <script>` does not (finding P3).
- **Mention controls:** met. The t12 controls (commit message, `echo "<script>"`, grep pattern, pull request body, `cat <script>`, `Write-Host 'run <script>'`, armed `echo "<script>" ; git status` with the arm kept) give exit 0. `test_database_override.py`, which carries `MENTION_ROWS`, exits 0. No `MENTION_ROWS` row now blocks. New false blocks, all of the class Failure Modes accepts, are listed under finding F1.
- **The read-only guard beside each probe (L1 accepted):** as the contract pins it. Armed, it asks and claims on H7, N2a, K1 to K6, the suite-spelling O13 and O13e, and every armed new shape that holds a removal. It allows and keeps the arm on t4's literal O13 and O13e, N1a, N1b, H6, the `cd` and `Write-Host` forms, O12, O14 and the launchers. It allows every unarmed human-only shape. It never blocks a human-only shape, as designed.
- **Evidence for "a hook block beats a hook ask" (block 12's instruction, kept):** documentation only, unchanged. Pull request 432 quotes the hooks documentation: "deny > defer > ask > allow; exit 2 routes as deny". No live session has observed a block and an ask answering one call, and the contract correctly keeps it `ASSUMED`. On B1's new shapes the question does not arise, because the destructive guard asks too, or allows (X1e), so no block exists to win.
- **Prompt-only, use-once, fresh-arm (N1) and person-present rules (O0 to O20):** met, unchanged from t12 (see Evidence). O10 (arm dated one day ahead) blocks and removes the arm.
- **Arm-write rule (W1, W2), the whole route table:** met, unchanged. R3, R4 and S5 are SEEN. The residual MISSED rows are the same as before (R11, S10 to S18, S25, S26).
- **Shared-claim rule and Guard fallback mode (t4 probes P1 to P9):** met, unchanged. P3 and P4 give ASK then BLOCK. P7 blocks in both guards. P8 and P8b refuse with the helper (and parser) removed. P9 refuses a non-ASCII payload in both guards.
- **Broken-file rule (W4), real attempt:** met. A link at `switches.local.json` to a listening pipe, made by `os.symlink` and by `cmd /c mklink`, in the `\\.\` and `\\?\` spellings, gives every key at its default in 0.09 to 0.12 s. The committed `off` is ignored, and exactly one `switches` report is logged and not repeated. A directory link at `.claude` into the pipe namespace finishes in 0.12 s with every default. PowerShell `New-Item -ItemType SymbolicLink` still refuses ("Administrator privilege required"), so that route was not created.
- **I1, rules file, real attempt:** met for both guards. Links were made by `os.symlink` and `mklink`, in both spellings, plus a `\\server\share` link and a directory link at `.claude/hooks`, with the helper present, deleted and stale (`d11572c`, which has no public `read_regular_file_bytes`). The destructive guard blocks a removal of a non-disposable database in 0.13 to 0.20 s in every case. The read-only guard withdraws the disposable exemption, which is the accepted false block. With a regular rules file the exemption loads.
- **Audit-log rule (I2), real attempt, both guards:** **met.** Each pipe accepts and never reads (zero buffers). In every case the guard gives its normal block within the 10 s timeout, writes the "audit record skipped" line, and leaves the link target untouched. The cases: a link at `<project>/.claude/logs/db-guard.log` (destructive guard) and at `<project>/.claude/logs/db-research.log` (read-only guard) to the pipe, made by `os.symlink` and `mklink` in both spellings; a link to `\\server\share`; a directory link at `.claude/logs` into the pipe namespace (`os.symlink` and `mklink /D`), to another local folder (symbolic link and junction; nothing written there) and to `\\server\share`; a directory link at `.claude` into the pipe namespace; rotation on a log linked to a regular file over the limit (target neither renamed nor removed); rotation with a link at `.1` (its target not removed). Times were 0.11 to 0.17 s. Controls: a regular log is appended, a missing logs folder is created, and a regular log over the limit rotates. **Live control:** at `4a67d1a` the four pipe-link cases make both guards give no result within 10 s, so the probe detects the hang. A hard link at the log still receives the record (finding L2).
- **Residual-risk paragraph:** partly met. The corrected L1 sentence is present ("for t4's O13 and O13e only in the spelling with `-S`"). So are the t9 limits (one rule, one layer, `default`, 2.1.327, plugin disabled, start time inferred, void by block 9's own rule), W3 (a) (the arm is not bound to a command; "unresolved" for `sqlcmd -Q`) and W3 (b) (an allow rule did not win, narrowly proven). I2 for both guards and its remaining Windows race are named. But the paragraph frames B1, P1 and P2 as holding "Until block 13 merges", and block 13 has merged. It names none of the shapes in findings B1, P1, P2, P3, T1 or Q1. Finding W7.
- **Failure Modes dispositions:** present for W4 (POSIX and Windows), B1 (all entries), P1, P2, I2 (both guards), the union reading's false block, the skipped audit record, I1 and its neighbours, L1, t9 steps 7 to 9, N6 (Information entry), and W5, N2 and N3. The B1, P1 and P2 mitigations are achieved for every row block 13 copied, and not for the shapes below. The union-false-block disposition says commit-message mentions "are blanked by the prose masker before the classifier runs". That is not true for a PowerShell commit message with a backtick-wrapped name (F1).
- **Guard suites:** all eight exit 0 (see Evidence).

## Findings

- **B1 (blocker, not cleared, round four): a human-only script after a misread quote still claims the arm, in two spelling classes inside the rule's definition.**
  - **(a) A quote opened mid-word right before the name.** Location: `.claude/hooks/db-destructive-guard.py:1554-1563` (`_starts_a_command`: when `pre` ends inside a quote, only a launcher argument can be "invoked") and `:1566-1570` (`_quote_blind_starts_a_command`: the pattern strips an optional quote *before* the folder prefix, never one *after* it). In `tools/db-protection/"<script>"` every reading ends inside the quote, so the word that holds the name (the segment's first word) is never judged. Backslash paths escape this in the bash reading, so the PowerShell form needs forward slashes, which PowerShell accepts.
  - **(b) An apostrophe in a `#` comment.** Location: `_mask_inert_prose` (`:2085-2143`) and `_skip_quoted` (`:1996-2001`). The masker has no idea of comments in either shell. In `echo "start"   # we don't need this` the comment's apostrophe opens a single-quoted "span" that `_skip_quoted` carries across newlines to the next apostrophe anywhere later in the call. The span belongs to the `echo` segment, so it is blanked as echo prose, and every line inside it disappears before the classifier runs. The rule exempts only "commit messages, `echo` text, search patterns, pull request bodies". This blanks command lines.
  - **Exploit scenario:** a person arms for one ordinary blocked command. The agent sends, in bash, a removal of a non-disposable database through `sqlcmd -Q`, then `echo "start"   # we don't need this`, then `tools/db-protection/update-dev-database.cmd`, then `echo "done, it's ok"` on separate lines. Both guards ask (A1). In PowerShell the same shape asks from both guards (A1p). In X1e (PowerShell: `Write-Host "go"  # don't`, the script, the removal, then `Write-Host 'x'`), the destructive guard allows and keeps the arm, because the masked span also hid the removal, while the read-only guard asks and claims. In bash, a removal followed by `tools/db-protection/"update-dev-database.cmd"` asks from both guards (X3a), and so does the PowerShell forward-slash form (X3h). Each is ASK, or ALLOW, at `4a67d1a` too, so block 13 did not reach these spellings.
  - **Impact:** the user-decided invariant "never prompt for them; the person runs them by hand" still breaks. An apostrophe in a comment ("don't", "it's") on a multi-line agent command is ordinary text, not an evasion.
  - **Fix:** (a) in each quote reading, when `pre` ends inside a quote that opened inside the current word (the quote is not a launcher argument), judge the word's position as the `not quote` branch does: `seg.words` before the word, plus the start-passing words. In the quote-blind pattern, allow an optional quote after the folder prefix as well as before it, and quotes inside the prefix (`["']?(?:[^\s;&|()]|["'])*[\\/]["']?$`). (b) Make the masker comment-aware for both shells. A `#` at the start of a word outside quotes ends the segment at the newline, and its text is never scanned for quotes. PowerShell `<# … #>` is skipped as a whole. Add armed rows (destructive guard alone, its own arm each, exit 2, no ask JSON, arm kept) in this report's exact spelling: A1, A1p, X1e, X3a, X3h. Add unarmed rows as under P1. Each must fail at the parent tip.
- **P1 (critical, existing before this contract, same root cause as B1): with no arm, the same shapes run a human-only script with no prompt.** Each is ALLOW at `cd8eb51`, `4a67d1a` and `4a817cb`, and each ran the trailing command in the real shell (`tools/probe/ran.sh` in Git Bash, `tools\probe\ran.cmd` in Windows PowerShell 5.1; both only print `RAN` and append a marker line). X1 is bash `echo "start"   # we don't need this` / script / `echo "done, it's ok"`; X1p is the PowerShell `Write-Host` form. X1c is the bash `git commit -m "wip"  # don't push yet` / script / `git log -1 --format='%s'`, and X1d is the bash `grep -n "x" a.txt   # it's here` / script / `echo 'ok'`. X3 is bash `tools/db-protection/"<script>"` and X3b is bash `echo a; tools/db-protection/'<script>'`. X3f is PowerShell `tools/db-protection/"<script>"` and X3g is PowerShell `cd x; tools/db-protection/'<script>'`. X3i is bash `"$PWD"/tools/db-protection/"<script>"`.
  **Impact:** the 2026-05-06 incident class: an agent changes the development database and nobody answers anything.
  **Fix:** the B1 fix, with these as unarmed rows (expect exit 2) and a line in the P1 change note.
- **Q1 (critical, existing before this contract, outside its scope: the shared prose masker): an apostrophe in a `#` comment hides every destructive statement up to the next apostrophe from the destructive guard.** Location: as B1 (b). This is the 2026-11-05 shared-classifier lesson in the other direction: the masker blanks what destructive-command detection must read. Same results at `cd8eb51`, `4a67d1a` and `4a817cb`:
  - D1 and D3: `echo "go"  # don't` (bash) or `Write-Host "go"  # don't` (PowerShell), then a removal of a non-disposable database through `sqlcmd -S localhost -Q`, then `echo 'x'`. The destructive guard allows. The read-only guard blocks, but only because it sees a database write without the read-only intent.
  - D2, D4 and D5: the same with an EF removal, including after `git commit -m "wip"  # it's fine`. **Both guards allow**, with no arm and no prompt. The read-only guard does not match EF commands (control D0e: EF removal alone is BLOCK from the destructive guard and ALLOW from the read-only guard).
  - D6: an empty-table statement on a protected database through `sqlcmd -d`. Both guards allow.
  - D8, armed, EF removal: both guards allow and the arm is kept.

  **Exploit scenario:** an agent writes a three-line command whose first line carries a remark such as "# don't skip the cleanup", whose second line is the EF removal of the configured database, and whose third line echoes something in single quotes. Nothing blocks it.
  **Impact:** the exact command of the reference incident (an EF removal of the configured development database) passes the guard built to stop it. This bypass is not a crafted evasion: it is a comment containing a contraction.
  **Fix:** the masker change under B1 (b). Then a guard-suite row per shell for D1 to D6 (destructive guard, expect exit 2) and controls for a commit message, an `echo` and a pull request body that hold `#` and apostrophes inside quotes (expect them still masked). The masker is shared with destructive-command detection, so this predates the contract and the user decides whether it joins the next fix block, as with I1 and I2. I recommend yes, at critical severity.
- **P2 (high, not cleared for long options): an option that takes a value is skipped only when it is one of the short options block 13 lists.** Location: `_VALUED_OPTIONS` (`:1374-1382`) and `_words_pass_the_start` (`:1385-1420`). The rule's sentence is "an option that takes a value also skips its value". With a separate value, a long option's value is read as the command word, so the name is a mention. With no arm these give ALLOW at head, base and `cd8eb51`, and run in Git Bash: X41 `timeout --signal KILL 5 <script>`, X43 `env --unset NAME <script>`, X44 `nice --adjustment 10 <script>`, X45 `echo x | xargs --max-args 1 <script>`. X42 `sudo --user root <script>` is also ALLOW (not run, because `sudo` on this host is Windows sudo). Armed after a removal, A41 gives ASK from both guards. The `=` form (`--signal=KILL`) blocks.
  **Fix:** add the long spellings of every listed valued option (`--signal`, `--kill-after`, `--user`, `--group`, `--host`, `--prompt`, `--close-from`, `--chdir`, `--role`, `--type`, `--other-user`, `--unset`, `--adjustment`, `--replace`, `--max-args`, `--max-procs`, `--max-lines`, `--delimiter`, `--arg-file`, `--eof`, `--max-chars`), with one row per word.
- **P3 (high, existing before this contract, outside the rule's literal word and launcher lists): other command starts read as mentions.** Location: `_INVOKING_WORDS` (`:1340-1342`), `_START_PASSING_WORDS` (`:1370-1373`), `_takes_command_string` (`:1350-1365`). With no arm, each gives ALLOW at head, base and `cd8eb51`.
  - Ran in the real shell, Git Bash: X4 `if <script>; then :; fi`, X5 `while <script>; do break; done`, X6 `until …`, X7 `eval <script>`, X8 `eval "<script>"`, X9 `find . -maxdepth 0 -exec <script> \;`, X10 `2>/dev/null <script>` (a leading redirection), X11 `cmd //c tools\\db-protection\\<script>` (the Git Bash spelling of `cmd /c`), X16 `stdbuf -oL <script>`, X18 `case x in x) <script>;; esac`, X19 `coproc <script>`, X20 `trap '<script>' EXIT`.
  - Ran in the real shell, Windows PowerShell: X13 `Start-Process -FilePath <script> -Wait -NoNewWindow`, X14 `Start-Process -Wait -NoNewWindow <script>`, X87b `start -Wait -WindowStyle Hidden <script>`, X86 `& (Get-Item <script>)`, X53 `cmd /c --% <script>`, X88b `cmd /c start /wait /b <script>`, X89b `cmd /c start "" /b <script>`.
  - Not run: X15 `winpty` needs a console. X17 `setsid` and X80 to X84 (`doas`, `unbuffer`, `watch -n 1`, `flock`, `ionice`) are not on this host.

  Armed after a removal, A4 (`if`), A7 (`eval`), A10 (leading redirection), A11 (`cmd //c`), A13 (`Start-Process -FilePath`) and A53 (`cmd /c --%`) give ASK from both guards. `if`, `while` and `until` are the same kind of word as `then`, `do` and `elif`, which block 13 added. Git Bash `cmd //c` is what an agent on this host types.
  **Fix:** this is for the architect, because it extends the rule as P2 did. Three rounds of adding invocation contexts have each left more. I recommend inverting the test: a human-only name that survives masking counts as **invoked**, except in a short allowlist of mention positions (an argument of `echo`, `printf`, `Write-Host`, `Write-Output`, `cat`, `type`, `Get-Content`, `less`, `head`, `tail`, `grep`, `rg`, `Select-String`, `ls`, `dir`, `Get-Item`/`Test-Path` outside `&`, `git add`/`diff`/`log`/`show`, `command -v`/`-V`, `which`, `Get-Command`). Each mention is then a named row, and an unknown form fails closed with a block naming the script, which is the outcome the user chose for this class. If the architect keeps the enumeration instead, add at least `if`, `while`, `until`, `eval` (and its quoted argument as command text), `coproc`, a `)` that closes a `case` pattern, `trap`'s quoted argument, a leading redirection, `find -exec`/`-execdir`/`-ok`, `stdbuf`, `setsid`, `winpty`, `doas`, `watch`, `flock`, `ionice`, `unbuffer`, `//c` and `//k`, `--%`, PowerShell `Start-Process`/`start`/`saps` with any options, cmd `start` with options and a title, and `&` before a parenthesised expression.
- **T1 (high, existing before this contract): the human-only name is matched as literal text, so a call the shell resolves to the script without that text is not seen.** Location: `_human_only_script_hits` (`:1595-1606`). With no arm, each gives ALLOW at head, base and `cd8eb51`, and each ran in the real shell:
  - X21: PowerShell `tools\db-protection\update-dev-database`, with no extension. PowerShell and cmd find the `.cmd` through `PATHEXT`. This is a natural spelling, not an evasion.
  - X21b: Git Bash `cmd //c tools\\db-protection\\update-dev-database`.
  - X23: a bash `\`-newline continuation inside the name.
  - X24: a bash `''` splice inside the name.
  - X25: PowerShell `& ('tools\db-protection\' + '<script>')`.
  - X22 and X22p: the restore script with its recover flag on the next line after a bash `\` or PowerShell backtick continuation. The flag check reads only the rest of the first line (`split("\n", 1)[0]`), and the line-continuation probe printed the flag.

  Armed, A21 gives ASK from both guards. The splice and concatenation forms are the same text-guard limit as the arm-write residual rows S10 to S17 and t12's N6. The extension-less call and the continued flag are not.
  **Fix:** match the stem with an optional `.cmd`/`.bat` and trailing dots or spaces (`update-dev-database(?:\.(?:cmd|bat))?[. ]*`). Before matching and before the flag check, join bash `\`-newline and PowerShell backtick-newline continuations and remove empty quote pairs. Name the rest (concatenation, variables, `-EncodedCommand`) in the residual-risk paragraph as the text-guard limit for the human-only class.
- **W7 (warning, contract text): the residual-risk paragraph and one Failure Modes sentence are out of date after block 13.** Location: `## Failure Modes & Mitigations`, "Residual risk of the database override, in one place", the sentence beginning "Until block 13 merges:"; and the union-false-block disposition, "Mentions inside commit messages … are blanked by the prose masker before the classifier runs". (a) Block 13 merged as `4a817cb`, and B1, P1 and P2 hold for the shapes above. (b) Q1, P3 and T1 are not named. (c) The hard-link case (L2) is not named. (d) A PowerShell commit message with a backtick-wrapped name is not blanked (F1).
- **L2 (low, existing before this contract): a hard link at the audit log receives the record.** Location: `db-destructive-guard.py:811-866` and `db-research-readonly-guard.py:379-434` (`_audit`). A hard link is a regular file to `lstat` and `fstat`, so the append lands in whatever file the link shares. In both guards a user file grew from 11 bytes to 739 and 335 bytes. The Audit-log rule's reason ("a write through one reaches a file the guard did not choose") applies. **Fix:** require `st_nlink == 1` on the `fstat` result before writing, and skip the record otherwise.
- **F1 (informational, accepted false blocks, union reading):** in PowerShell, `Write-Host "run `<script>` by hand"` (M1) and `git commit -m "docs: run `<script>` by hand"` (M1b) block, because the bash reading takes the backticks as a substitution and the masker does not blank a double-quoted span with a backtick. In bash, the same commit message in single quotes stays allowed (M1c). `cat <<'EOF'` with the script on its own line blocks (M4). `command -pv <script>` blocks (X49). These are the class the Failure Modes entry accepts. None is a `MENTION_ROWS` row, and the M1b case is the one W7 (d) names.
- **Information, as the task asks: further spellings that block correctly.** Here strings and heredocs that run text (X27 `iex @"…"@`, X28 `bash <<'EOF'`), `"$(<script>)"` in `echo`, `git commit -m` and `Write-Host` (X30 to X32), `{ <script>; }`, `if ($true) { <script> }`, `Invoke-Command -ScriptBlock { … }`, `time -p`, `sudo -E`, `sudo --`, `env A=1 B=2`, `env --`, `nohup nice -n 5`, `timeout --signal=KILL 5`, `timeout -k 5 -s KILL 5`, `nice -n10`, `sudo -uroot`, `time time`, `command -p`, `cmd --% /c <script>`, PowerShell `cmd /c "echo "a" & <script>"`, bash `echo $'\'' ; <script> ; echo $'\''` (X2), and the PowerShell `& tools\db-protection\"<script>"` and `.\tools\db-protection\'<script>'` forms (backslash before the quote). Escaped names in commit messages stay allowed in both shells (M2, M2p). So do PowerShell here-string mentions (M3, M3b), a `#` comment that names the script, multi-line commit message and pull request bodies, and a commit message holding both an apostrophe and the name.

## What was NOT checked

- No live Claude Code session. Whether a hook block beats a hook ask, and whether a timed-out hook lets the call proceed (W4, I1, I2), rest on the documentation quoted in pull request 432 and on t3 and t9.
- `acceptEdits`, `plan` and `dontAsk` live (t9 steps 7 to 9 not run; a named residual).
- Allow rules in user-level or managed settings, and the `Bash(sqlcmd:*)` form.
- PowerShell 7 (`pwsh` is not installed on this host). The PowerShell shapes ran in Windows PowerShell 5.1 only.
- The new shapes through Claude Code's own Bash and PowerShell tools. I ran them in Git Bash (as a script file and through `bash -c`) and Windows PowerShell 5.1 directly, with harmless probe scripts in place of the human-only script.
- `winpty`, `setsid`, `doas`, `unbuffer`, `watch`, `flock` and `ionice` in a real shell (no console, or not installed). Unix `sudo --user` (only Windows sudo is on this host).
- The Windows race the skipped-audit disposition names: a link swapped in between the check and the open, to a target that stalls in the open. No attempt was made to win it.
- POSIX: no container run. `test_switches.py` skips its 3 POSIX rows and `test_database_override.py` skips 2 here.
- A pipe link against the other hooks t12 listed (accepted neighbours of I1).
- MCP tools that write files (a contract Non-Goal). The ordinary switches block and the documents block (out of the reviewed range).

## Evidence

Every probe ran a guard as a separate process, in a fresh temporary project with `CLAUDE_PROJECT_DIR` pointing at it, the `CLAUDE_*` variables stripped, and the payload on standard input. Destructive statements in the harness files are built by string joining. One exception: t4's `probe2.py` row P7 sets the retired variable `CLAUDE_DESTRUCTIVE_DB_OK=1` in the environment of its two child guard processes, in a throwaway project, to prove the guards ignore it (both block). I set it nowhere else: not in my shell or session, and no guard runs a command. No database was contacted.

Harness files are outside the repository, under `C:\Users\lneni\AppData\Local\Temp\`:

- this round: `t14h\gen14.py`, `gen14b.py`, `gen14c.py`, `gen14d.py` (and their `s14_*.json`), `t14h\pipe14_audit.py` and `t14h\pipe14_i1.py`; `t14h\shell\bash_shapes14.sh`, `ps_shapes14.ps1` and `exact14.sh`, with `tools\probe\ran.cmd` and `ran.sh`, which only print `RAN` and append to `ran.log`;
- reused from t12: `t12h\harness12.py`, its `s_fail`, `s_launch`, `s_ctrl`, `s_cand` and `s_cand2` sets, `pipe12.py` and `pipe12c.py`;
- reused from t4: `t4h\harness.py`, `override.json`, `routes.json` and `probe2.py`.

| Command | Exit |
|---|---|
| `git rev-parse HEAD` (`4a817cb…`: head is the merge) | 0 |
| `git log --first-parent --oneline -6`; `git show --stat 4a817cb` (parents `4a67d1a`, `9359ae0`; four files) | 0 |
| `git diff 4a67d1a 4a817cb -- db-destructive-guard.py db-research-readonly-guard.py` (read in full) | 0 |
| `git diff 4a67d1a 4a817cb -- test_database_override.py \| grep MENTION_ROWS\|LAUNCHER_ROWS` (no changed line) | 1 |
| `git diff --stat 4a67d1a 4a817cb -- test_db_destructive_guard.py` (empty) | 0 |
| `git archive 4a817cb` and `4a67d1a`, extracted to `%TEMP%\t14h\head` and `base` | 0 |
| `py -3 -I harness12.py <head hooks> s_fail.json dg,rg` (t4, t10 failures, both guards) | 0 |
| `py -3 -I harness12.py <head hooks> s_launch.json dg,rg`, `s_ctrl.json`, `s_cand.json`, `s_cand2.json` | 0 |
| `py -3 -I harness12.py <head hooks> s14_words.json dg`, `s14_ctrl.json` (block 13 per-word, valued, controls) | 0 |
| `py -3 -I harness12.py <hooks> s14_new.json dg` at head, `4a67d1a` and `cd8eb51` | 0 |
| `py -3 -I harness12.py <hooks> s14_armed.json dg[,rg]` at head, `4a67d1a`, `cd8eb51` | 0 |
| `py -3 -I harness12.py <head hooks> s14_extra.json dg,rg`; `s14_mention.json dg` | 0 |
| `py -3 -I harness12.py <hooks> s14_d.json dg,rg` at head, `4a67d1a`, `cd8eb51` (Q1) | 0 |
| `bash bash_shapes14.sh` (`RAN` for every shape except X15 `winpty`) | 0 |
| `powershell -NoProfile -ExecutionPolicy Bypass -File ps_shapes14.ps1` (`RAN` for every shape) | 0 |
| `bash exact14.sh` (X1 and X1d through `bash -c`; X3f, X3g in PowerShell: `RAN` each) | 0 |
| `py -3 -I harness.py <head hooks> x override.json` (O0 to O20) | 0 |
| `py -3 -I harness.py <head hooks> x routes.json` (whole route table) | 0 |
| `py -3 -I probe2.py <head hooks>` (t4 probes P1 to P9) | 0 |
| `py -3 -I pipe12.py <head hooks> <d11572c _switches.py>` (W4, I1 by `os.symlink`; helper present, deleted, stale) | 0 |
| `py -3 -I pipe12c.py <head hooks>` (W4 by `os.symlink` and `mklink`, committed `off`, one report) | 0 |
| `py -3 -I pipe14_i1.py <head hooks> <d11572c _switches.py>` (I1 by `mklink`, both spellings, three helper states) | 0 |
| `py -3 -I pipe14_audit.py <head hooks>` (I2, both guards, 17 cases each) | 0 |
| `py -3 -I pipe14_audit.py <4a67d1a hooks>` (live control: the four pipe-link cases give no result within 10 s in both guards) | 0 |
| `gh pr view 432 --json body` ("deny > defer > ask > allow; exit 2 routes as deny") | 0 |
| `py -3 .claude/hooks/tests/test_switches.py` (63 tests, OK, 3 POSIX skips) | 0 |
| `py -3 .claude/hooks/tests/test_database_override.py` (219 tests, OK, 2 skips) | 0 |
| `py -3 .claude/hooks/tests/test_db_destructive_guard.py` (605 of 605) | 0 |
| `py -3 .claude/hooks/tests/test_db_guard_path_allowlist.py` (93 tests, OK) | 0 |
| `py -3 .claude/hooks/tests/test_readonly_guard_disposable_exemption.py` (16 of 16) | 0 |
| `py -3 .claude/hooks/tests/test_worktree_path_guards.py` (190 of 190) | 0 |
| `py -3 .claude/hooks/tests/test_shell_write_targets.py` (19 tests, OK) | 0 |
| `py -3 .claude/scripts/tests/test_switch_env_scan.py` (14 tests, OK, 2 expected failures owned by the documents block) | 0 |

**Re-run of the t4, t10 and t12 failures at head** (H = `tools/db-protection/update-dev-database.cmd`, HB = the backslash spelling; dg = destructive guard, rg = read-only guard; each guard in its own project with its own arm; "arm kept" means no claim file):

| Probe | Shell | Armed | dg | rg |
|---|---|---|---|---|
| O13 t4 literal / suite spelling | Bash | yes | BLOCK, arm kept / BLOCK, arm kept | ALLOW, arm kept / ASK, claimed |
| O13e forward slashes / backslashes / suite spelling | PowerShell | yes | BLOCK, arm kept (each) | ALLOW / ALLOW / ASK, claimed |
| H1, H4, H5 | Bash, PowerShell | no | BLOCK (each) | ALLOW (each) |
| H3 | PowerShell | no | BLOCK | ALLOW |
| H6 | Bash, PowerShell | yes | BLOCK, arm kept | ALLOW, arm kept |
| H7 | Bash, PowerShell | yes | BLOCK, arm kept | ASK, claimed |
| Disposition `cd "<p>" && H` / `Write-Host 'x'; HB` | Bash, PowerShell / PowerShell | yes | BLOCK, arm kept | ALLOW, arm kept |
| O12, O14 | Bash | yes | BLOCK, arm kept | ALLOW, arm kept |
| O10 arm dated one day ahead | Bash | yes | BLOCK, arm removed | BLOCK, arm removed |
| O11, O13b, H2 | Bash | yes, yes, no | BLOCK (arm kept where armed) | ALLOW |
| t12 N1, N1c, N5, N6, N15 | PowerShell | no | BLOCK | ALLOW |
| t12 N2, N2b, N3, N4, N7 to N13 | Bash | no | BLOCK | ALLOW |
| t12 N1a, N1b | PowerShell | yes | BLOCK, arm kept | ALLOW, arm kept |
| t12 N2a, K1 to K4 / K5, K6 | Bash / PowerShell | yes | BLOCK, arm kept | ASK, claimed |
| t12 N14 (finding N6) | Bash | no | ALLOW (accepted) | ALLOW |
| R3, R4, S5 | — | — | SEEN (exit 2) | — |

**Quoted launchers at head** (dg; rg gives exit 0 on each): L1 to L10 of t12, unarmed and armed (arm kept): every one is BLOCK. Git Bash `cmd //c "echo a & HB"` (X12): BLOCK.

**Block 13 rows at head** (dg, no arm unless noted): W1 to W10 and V1 to V6 BLOCK; V7 armed BLOCK, arm kept. Controls CV1 `command -v`, CV2 `command -V`, CW1 to CW4 ALLOW; CW5 armed `command -v H ; git status` ALLOW, arm kept.

**New shapes at head** (dg / rg; every row is the same at `4a67d1a`, and the unarmed rows are the same at `cd8eb51`; "ran" = the real shell ran the probe script):

| Row | Shape | Armed | dg | rg | Real shell |
|---|---|---|---|---|---|
| X1, X1c, X1d | bash comment apostrophe after `echo` / `git commit` / `grep` | no | **ALLOW** | ALLOW | ran |
| X1p | PowerShell comment apostrophe after `Write-Host` | no | **ALLOW** | ALLOW | ran |
| A1 / A1p | removal, then X1 / X1p | yes | **ASK, claimed** | ASK, claimed | — |
| X1e | PowerShell `Write-Host "go"  # don't`, HB, removal, `Write-Host 'x'` | yes | **ALLOW, arm kept** | ASK, claimed | — |
| X3, X3b, X3i | bash `tools/db-protection/"<name>"`, `echo a; …/'<name>'`, `"$PWD"/…/"<name>"` | no | **ALLOW** | ALLOW | ran (X3, X3b) |
| X3f, X3g | PowerShell forward-slash mid-word quote | no | **ALLOW** | ALLOW | ran |
| X3a / X3h | removal, then X3 / X3f | yes | **ASK, claimed** | ASK, claimed | — |
| X41, X43, X44, X45, X42 | long valued option with a separate value | no | **ALLOW** | — | ran (not X42) |
| A41 | removal, then X41 | yes | **ASK, claimed** | ASK, claimed | — |
| X4 to X11, X16, X18 to X20 | `if`, `while`, `until`, `eval`, `eval "…"`, `find -exec`, leading redirection, `cmd //c`, `stdbuf`, `case`, `coproc`, `trap` | no | **ALLOW** | — | ran |
| X13, X14, X87b, X86, X53, X88b, X89b | `Start-Process` with options, `start -Wait`, `& (Get-Item …)`, `cmd /c --%`, `cmd /c start /wait /b`, `start "" /b` | no | **ALLOW** | ALLOW | ran |
| X15, X17, X80 to X84 | `winpty`, `setsid`, `doas`, `unbuffer`, `watch`, `flock`, `ionice` | no | ALLOW | — | not run |
| A4, A7, A10, A11, A13, A53 | removal, then `if` / `eval` / redirection / `cmd //c` / `Start-Process` / `--%` | yes | **ASK, claimed** | ASK, claimed | — |
| X21, X21b, X23, X24, X25, X22, X22p | no extension, continuation or splice in the name, concatenation, flag after a continuation | no | **ALLOW** | — | ran |
| A21 | removal, then X21 | yes | **ASK, claimed** | ASK, claimed | — |

**Q1 at head, `4a67d1a` and `cd8eb51`** (identical; no arm unless noted): D0 removal through `sqlcmd` alone: dg BLOCK, rg BLOCK. D0e EF removal alone: dg BLOCK, rg ALLOW. D1, D3 (comment apostrophe, then the `sqlcmd` removal): dg **ALLOW**, rg BLOCK. D2, D4, D5 (comment apostrophe, then the EF removal): dg **ALLOW**, rg **ALLOW**. D6 (comment apostrophe, then the empty-table statement on a protected database): dg **ALLOW**, rg **ALLOW**. D7 (`$'\''` pairing, then the EF removal): dg BLOCK. D8 armed (comment apostrophe, then the EF removal): dg ALLOW, rg ALLOW, arm kept.

**Override decisions at head** (a removal of a non-disposable database through `sqlcmd -Q`; armed unless noted).

| Probes | Outcome |
|---|---|
| O0 (not armed) | BLOCK |
| O1 `default`, O2 `acceptEdits`, O3 `plan` | ASK, arm gone |
| O4 `bypassPermissions`, O5 `dontAsk`, O6 `auto`, O7 mode missing, O8 `Default` | BLOCK, arm kept |
| O9 (stale arm) and O10 (arm dated in the future) | BLOCK, arm removed |
| O11 to O14 | BLOCK, arm kept |
| O15 `git status` | ALLOW, arm kept |
| O16 and O17 | ASK; the target is `unresolved` (W5) |
| O18 (no tool call id) | ASK |
| O19 (read-only guard) | ASK |
| O20 (read-only guard, bypass mode) | BLOCK, arm kept |

**Arm-write routes at head.**

| Routes | Outcome |
|---|---|
| R1 to R5, R8 to R10, S1 to S5, S9, S19 to S24, S27, S28 | SEEN |
| R6, R7 | MISSED, harmless (they write a different file) |
| R11, S10 to S18, S25, S26 | MISSED, residual |
| S6 to S8, S29 | allowed, correctly |

**Shared claim and fallback at head (t4 probes P1 to P9).** P1 dg then rg: ASK, ASK. P2 rg then dg: ASK, ASK. P3 (no id): ASK, BLOCK. P4 (different id): ASK, BLOCK. P5: the quote-forged name survives (N2, accepted). P6 and P6b: ASK with neutralised targets. P7: BLOCK, BLOCK. P8 (helper removed): BLOCK for the destructive command, the Write to the arm and the read-only guard's `touch`. P8b (helper and parser removed): BLOCK. P9 (non-ASCII payload): BLOCK in both guards.

**W4, I1 and I2 real attempts at head.**

- **W4:** `os.symlink` `\\.\` 0.10 s and `\\?\` 0.11 to 0.12 s; `mklink` `\\.\` 0.11 s and `\\?\` 0.11 s. Each link is stored as `\\?\pipe\<name>`. Every key comes back at its default, the committed `off` is ignored, and there is 1 report, not repeated. A directory link at `.claude` gives every default in 0.12 s. `New-Item` was refused (elevation).
- **I1:** with the helper present, deleted or stale, a regular rules file gives dg BLOCK and rg ALLOW. A link to a pipe (`os.symlink` and `mklink`, both spellings), to `\\server\share`, or a directory link at `.claude/hooks` gives dg BLOCK and rg BLOCK, in 0.10 to 0.20 s.
- **I2:** see the table below.

| Case | dg (`db-guard.log`) | rg (`db-research.log`) |
|---|---|---|
| regular log; missing logs folder; regular log over the limit | BLOCK, appended / created / rotated | BLOCK, appended / created / rotated |
| link to the pipe, `os.symlink` and `mklink`, `\\.\` and `\\?\` | BLOCK 0.14 to 0.17 s, skipped | BLOCK 0.11 s, skipped |
| link to `\\server\share` | BLOCK, skipped | BLOCK, skipped |
| `.claude/logs` linked into the pipe namespace (`os.symlink`, `mklink /D`) | BLOCK, skipped | BLOCK, skipped |
| `.claude/logs` linked to a local folder (symbolic link, junction), to `\\server\share` | BLOCK, skipped, nothing written there | BLOCK, skipped, nothing written there |
| `.claude` linked into the pipe namespace | BLOCK, skipped | BLOCK, skipped |
| log linked to a regular file over the limit | BLOCK, skipped, target unchanged and not renamed | same |
| link at `.1`, regular log over the limit | BLOCK, skipped, `.1` target kept | same |
| hard link at the log | BLOCK, **record written into the other file** (L2) | same |
| at `4a67d1a`: the four pipe-link cases | no result within 10 s | no result within 10 s |

**Files read:**

- the whole block-13 diff of both guards;
- `db-destructive-guard.py`: `:100-117` and `:1185-1365` (the human-only entries, `_command_tokens`, `_INVOKING_WORDS`, `_takes_command_string`), `:1566-1606` and `:1996-2143` (`_skip_quoted`, `_span_is_inert`, `_segment_is_prose`, `_mask_inert_prose`);
- `db-research-readonly-guard.py:88-99`;
- `_project_paths.py:51-59` and `:197-207`;
- the contract's Override rules (No-prompt classes and Audit-log rules), Uncertain Assumptions, Failure Modes, the residual-risk paragraph, the amendment 3 Open Questions, blocks 13 and 14, and the Review checklist;
- the t12 report and Gate Output, and the t12 and t4 harness files.

## Disposition

**Blocked.** This holds blocks 6 and 7. The block comes from B1 (round four) and P1: the No-prompt classes rule's sentence ("the word that holds it, quoted or not, is the first word of a command segment") is not met for a quote opened mid-word before the name. The masker also blanks command lines that follow an apostrophe in a comment, which the rule's exemption for commit messages, `echo` text, search patterns and pull request bodies does not cover. Both hold in both shells. I2 is cleared in both guards and W4 and I1 still hold, and this report records that. Per the TASK constraint, this leads to an architect amendment of the contract that adds a further fix block and a further review block. No block is added without that amendment.

The further fix block (`python-ai-developer`, a sub-task pull request into `feature/file-based-switches`, no version raise) should:

1. Fix B1 and P1: (a) the mid-word quote in every quote reading and in the quote-blind pattern; (b) a comment-aware prose masker for both shells (`#` at a word start, PowerShell `<# … #>`). Add the armed rows A1, A1p, X1e, X3a, X3h and the unarmed rows X1, X1c, X1d, X1p, X3, X3b, X3f, X3g, X3i, in this report's exact spelling and shell. Each must fail at the parent tip. Keep `MENTION_ROWS` and `LAUNCHER_ROWS` unchanged and green, and add masker controls with `#` and apostrophes inside quoted commit messages, `echo` text and pull request bodies.
2. If the user includes it (Q1, the same masker change; existing before this contract, critical): guard-suite rows D1 to D6 in both shells that expect a block.
3. P2: the long spellings of the valued options, with rows X41 to X45 and A41.
4. The architect decides P3 and T1. My recommendation is to invert the human-only test (every unmasked occurrence of the name is invoked, except a named allowlist of mention positions) rather than extend the lists a fourth time. Then match the stem with or without its extension after joining continuations and removing empty quote pairs, and read the recover flag across continuation lines. Rows: X4 to X11, X13, X14, X16, X18 to X20, X53, X86, X87b, X88b, X89b, X21, X21b, X22, X22p, X23, X24 and A4, A7, A10, A11, A13, A21, A53. Each named mention position needs an allowed row.
5. Optionally, L2: require `st_nlink == 1` on the open descriptor in both guards' `_audit`.

The architect also updates the residual-risk paragraph and the union-false-block disposition (W7 (a) to (d)). The next re-review supersedes `t4-security-review-security-auditor.md`, `t10-security-re-review-security-auditor.md`, `t12-security-re-review-round-three-security-auditor.md` and this report. This report's Gate Output supersedes nothing.
