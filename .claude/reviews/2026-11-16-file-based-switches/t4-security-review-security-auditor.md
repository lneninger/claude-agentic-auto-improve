# t4 security review — security-auditor

- **Gate agent:** security-auditor
- **Sub-task:** t4-security-review (issue #423, parent #419)
- **Contract:** `.claude/concepts/2026-11-16-file-based-switches.md` (approved)
- **Reviewed on:** 2026-11-18
- **Commit range reviewed:** `e1dfa2d..adb70aa` (the helper block, pull request #432: `0bb73f9`, `3bab588`, `b05b7cb`). The four files under review (`_switches.py`, `db-destructive-guard.py`, `db-research-readonly-guard.py`, `_shell_write_targets.py`) are byte-identical at this worktree's head `f24c320` (`git diff --stat adb70aa f24c320` on them is empty), so every probe below ran against the reviewed code.

**Verdict:** blocked

One blocker: a human-only command becomes a permission prompt when it is combined in one tool call with another blocked operation. That breaks the No-prompt classes rule, which the user decided ("never prompt for them; the person runs them by hand"). No path allows a destructive command with no prompt at all. Five warnings and three nits follow.

This report names destructive statements in words, never as literal command text, because the plugin's destructive-database guard refuses any file that holds them (the same deviation as the t3 run sheet).

## What was checked

- **Prompt-only rule** (the arm allows nothing by itself): met. The only new outcome is `ask` with exit 0 (`_print_ask`). No allow path was added. The retired variable's two allow paths are gone. Probes O1 to O20 and P1 to P4 never produced an allow for a blocked command.
- **Use-once rule:** met. The arm is renamed to `database-override.claimed-<id>` before the ask is printed. It is gone after a prompt (O1 to O3, armLeft=False), whatever the answer. The trial's step 1 matches.
- **Fresh-arm rule:** partly met. A 16-minute-old arm is removed and the command is blocked (O9). A folder or link arm counts as `unusable` (lstat plus `S_ISREG`, covered by the suite). A future modification time counts as fresh (O10, nit N1).
- **Person-present rule:** met in code. `_PROMPT_MODES` is an allow-list (`default`, `acceptEdits`, `plan`). `bypassPermissions`, `dontAsk`, `auto`, a missing mode and `Default` in the wrong case all block and leave the arm in place (O4 to O8, O20).
- **Person-present rule against the trial run sheet:** partly met. The person's observations support it for `default` (prompt), `bypassPermissions` (block) and headless `auto` (block). `acceptEdits`, `plan`, `dontAsk` and a missing mode were never run live (run sheet N4 and "What was NOT checked"). They rest on the unit suite and on my offline probes only.
- **Arm-write rule, every route I tried:** partly met. The route table is under Evidence. The guard saw 19 routes and missed 21. Of the 21 misses, 2 are ones the contract says are refused (warnings W1 and W2). The other 19 are unseen routes the residual risk covers.
- **Arm-write rule runs before Guard deference, in both guards:** met (`main()` in both files calls `_arm_write_match` before `_defers_to_project_copy`).
- **Inline name-test copy with the helper removed (Guard fallback mode):** met (P8, P8b).
- **No-prompt classes rule:** **not met.** A human-only command alone blocks (O11). Combined with a protected-database write or with the EF argument-position bug, it prompts (O12, O13, O14). Blocker B1.
- **`_fail_closed` never prompts:** met by reading the code (no override call in `_fail_closed`), and by the suite's injected-fault rows.
- **Variable-retired rule:** met. With the retired variable set to 1, both guards still block (P7). The environment scan suite passes.
- **Untouched rule:** met. A non-destructive call keeps the arm (O15).
- **Shared-claim rule:** met. With one `tool_use_id`, both guards ask, in either order (P1, P2). With no id, the second guard blocks (P3). With a different id, the second guard blocks (P4).
- **Plain-reason rule:** met for the wording, control and format characters, comment markers, the 60-character cut and the label. The double quote and `;` survive, so the label structure can be forged (nit N2). No parser form I tried delivered such a target.
- **No path allows a destructive command without a prompt:** met. The destructive guard fails closed on an uncaught exception (exit 2 in `__main__`). The ask path's only output is the ask JSON.
- **The stated residual risk is complete:** **not met.** Two classes are missing (warning W3).
- **Broken-file rule:** partly met. Any broken file makes every file ignored (`_resolve`, `ignored=True`), and the suite passes. A FIFO at a switch-file path is not handled: on POSIX, `open()` blocks and the hook times out (warning W4, found by reading the code).
- **No-file rule and missing helper:** met. With `_switches` missing, `bypass_env` in `concept-gate.py` and `architecture-guard.py` returns False. The database guards bind `claim_database_override` with `getattr`, and a missing binding means `absent`, so they block.
- **No-environment rule:** met for this block. Neither database guard reads the retired variable. `test_switch_env_scan.py` passes, and its 2 expected failures belong to the documents block. `DB_GUARD_FAULT_INJECTION` stays test-only, and it can only turn an allow into a block.
- **`.gitignore`:** met. `.claude/database-override.*` and `.claude/switches.local.json` are ignored (`git check-ignore -v`).

## Findings

- **B1 (blocker) — a human-only command combined with another blocked operation gets a permission prompt.** Location: `.claude/hooks/db-destructive-guard.py:2161-2176` (`_decide`, the BLOCK-reason chain and `override_outcome = "absent" if reason == "human-only-command" else _try_override(payload)`), and the matching block-text branch at `:2251`.
  **Exploit scenario:** a person arms because they mean to approve one ordinary blocked command. The agent sends `tools/db-protection/update-dev-database.cmd` and appends, after `;`, the EF database-removal command with the disposable name placed after the `--` separator. The first clause is human-only; the second sets `argv_position_bug`. `argv_position_bug` (or `protected_db_violation`) is checked before the human-only branch, so `reason` is not `human-only-command`. The arm is claimed and the person sees an ask whose reason reads `"(configured database)"` / `"update-dev-da…"`. The same happens with a forward EF database update plus the argument-position-bug removal (O14), and with a row-deleting statement on a protected database plus the human-only script (O13).
  **Impact:** an agent can turn a command class the user ruled "never a prompt" into a promptable one by adding one clause. This diverges from an approved, user-decided invariant.
  **Fix:** decide the no-prompt class from the targets, not from the first reason. Use `human_only = any(t["classification"] == "human-only" for t in targets)` and skip `_try_override` when it is true, whatever `reason` is. Use the same flag for the stderr branch. Add rows to `test_database_override.py` for human-only plus protected-write, human-only plus argument-position bug, and EF forward update plus argument-position bug, each armed in `default` mode, each expecting a block with the arm still in place.
- **W1 (warning) — the Arm-write rule for the edit tools misses a path that ends in `/.` or `x/..`.** Location: `db-destructive-guard.py`, `_last_part_names_arm` (and its call in `_arm_write_match`). The read-only guard has the same helper, but it is not registered on the edit tools.
  **Scenario:** a Write with `file_path` `<project>/.claude/database-override.once/.` or `<project>/.claude/database-override.once/x/..` passes (R3, R4: ALLOW). On this host, Win32 collapses both and `open()` creates `database-override.once` (verified). Node's `path.resolve` gives the same result. The contract says the edit tools are refused on the last part of the target path, so this is a seen route that the code misses.
  **Fix:** normalise first (`ntpath.normpath` or `posixpath.normpath` of the slash-folded text, with trailing dots and spaces stripped from each part), then test every part, or simply run `_ARM_NAME_RE` over the whole path. Add rows for `/.`, `/x/..`, `\.` and `\x\..`.
- **W2 (warning) — a redirection after `git commit`, `git tag` or `git notes` to a quoted arm path is allowed.** Location: `db-destructive-guard.py:1652-1658` (`_segment_is_prose` returns True for git before the `piped or redirected` test) together with `_shell_write_targets.parse_redirect_targets`, which returns `[]` for a quoted target.
  **Scenario:** `git commit -m "x" > ".claude/database-override.once"` gives ALLOW (S5). The shell creates the file even when the commit fails. The parser does not see the quoted target, and the masker blanks it as commit prose. The contract lists "a redirection" and "a quoted path argument" as refused.
  **Fix:** in the Arm-write rule, unquote the redirect targets (or make `parse_redirect_targets` return quoted targets), and make `_segment_is_prose` return False for git when `redirected` is true. Add an S5-style row.
- **W3 (warning) — the residual-risk paragraph misses two classes.** Location: contract, Failure Modes and Mitigations, "Residual risk of the database override".
  (a) The arm is not bound to a command: the agent chooses which blocked command uses it up. A person who arms for command A can be shown command B. The guard's reason names the target as `"unresolved"` for the common `sqlcmd -Q` form (O1, O16, and run-sheet finding W1), so the only defence is the host's own display of the command.
  (b) The trial did not prove, and the helper pull request quotes nothing showing, that a PreToolUse `ask` is not overridden by a `permissions.allow` rule in `settings.json` or `settings.local.json`. An agent can write those files. The pull request quotes only hook-to-hook precedence ("deny > defer > ask > allow").
  **Fix:** name (a) in the residual paragraph and the README section (documents block). Add a live trial step: put an allow rule for `Bash(sqlcmd:*)` in `settings.local.json`, arm, and confirm the prompt still appears. If it does not, this becomes a blocker.
- **W4 (warning, POSIX only, found by reading the code, not reproduced) — a FIFO at a switch-file path hangs every switch read.** Location: `.claude/hooks/_switches.py:187-203` (`_read_file` rejects only `S_ISDIR`, then `open(path, "rb")`).
  **Scenario:** `mkfifo .claude/switches.local.json`. `open()` blocks until a writer appears, so the concept gate and the architecture guard time out. A hook timeout is not a block, so the edit goes through with no Visible-off notice. The user accepted that an agent may write `concept_gate: off`, but that route shows a `systemMessage`; this one is silent. The arm is not affected (`claim_database_override` checks `S_ISREG`).
  **Fix:** after `lstat`, follow the link with `os.stat`, require `S_ISREG`, and treat anything else as `unreadable` under the Broken-file rule. Alternatively, open with `O_NONBLOCK` and check `fstat`. Add a POSIX-only row.
- **W5 (warning, carried from run-sheet finding W1) — the prompt reason gives no target for the common command form.** Location: `db-destructive-guard.py`, `_plain_reason` fed by `_bind_targets`. For a database removal passed to `sqlcmd -S localhost -Q`, the target is `unresolved` (O1). This weakens W3(a). It is tracked as a follow-up, not a blocker.
- **N1 (nit) — an arm with a future modification time never goes stale.** Location: `_switches.py:512` (`time.time() - info.st_mtime > ARM_FRESH_SECONDS`) and `_fresh_regular_file`. O10: an arm dated 1 day ahead gives ASK. **Fix:** require `0 <= age <= ARM_FRESH_SECONDS` (allow a small negative skew). Apply the same to the claim sweep.
- **N2 (nit) — the neutraliser keeps `"` and `;`.** Location: `db-destructive-guard.py`, `_neutralise_target`. A direct call with the name `X" as written in the command. Disposable copy; "Y` yields a reason that seems to list two labelled targets (P5). No command form I tried delivered such a name (P6 resolved to `unresolved`). **Fix:** drop `"` and `;` as well, or render each target with `json.dumps` inside the label.
- **N3 (nit, existing behaviour) — the read-only guard fails open on an uncaught exception** (`db-research-readonly-guard.py:586-591`, exit 0). Its Arm-write refusal is therefore only as robust as the destructive guard beside it, which fails closed. P9 (non-ASCII payload) shows both still refuse.

## What was NOT checked

- No live Claude Code session was run. Host behaviour (`ask` shown, block beats ask, `systemMessage` shown) rests on the person-run trial and the helper pull request's documentation quotes.
- Whether the Write tool of Claude Code 2.1.327 accepts a `file_path` that ends in `/.` or `x/..` (W1). Only the guard's verdict and the operating system's open behaviour were checked.
- Whether a `permissions.allow` rule overrides a hook `ask` (W3(b)).
- The FIFO route (W4) on a POSIX host. This host is Windows.
- `acceptEdits`, `plan` and `dontAsk` live in a real session (offline probes only).
- The ordinary switches block (`e1dfa2d..adb70aa` excludes #436). I read only its `_switches` binding in `concept-gate.py` and `architecture-guard.py`, for the missing-helper rule.
- The documents block's README residual-risk text, which does not exist yet.
- MCP tools that write files. No guard sees them (a contract Non-Goal).

## Evidence

Each probe ran a guard as a separate process. Every run used a fresh temporary project with `CLAUDE_PROJECT_DIR` pointing at it, the `CLAUDE_*` variables stripped, and the payload on standard input as UTF-8. Harness scripts (outside the repository; the destructive statements in them are built by string joining so no file holds one literally): `%TEMP%\t4h\harness.py`, `%TEMP%\t4h\routes.json`, `%TEMP%\t4h\gen_override.py`, `%TEMP%\t4h\probe2.py`.

| Command | Exit |
|---|---|
| `git diff --stat e1dfa2d adb70aa` (11 files; the helper block) | 0 |
| `git diff --stat adb70aa f24c320 -- <the four reviewed files>` (empty) | 0 |
| `py -3 -I harness.py .claude/hooks x routes.json` (arm-write routes) | 0 |
| `py -3 -I gen_override.py override.json` then `py -3 -I harness.py .claude/hooks x override.json` (override decisions) | 0 |
| `py -3 -I probe2.py .claude/hooks` (shared claim, neutralising, helper removed, retired variable, non-ASCII payload) | 0 |
| inline `py -3 -I -` probe: Win32 open of `/.`, `x/..`, trailing dot and trailing space, plus the long-s and dotless-i look-alikes; `parse_redirect_targets` on quoted targets | 0 |
| `node -e "console.log(require('path').resolve('C:/p/.claude/database-override.once/x/..'))"` gives `C:\p\.claude\database-override.once` | 0 |
| `py -3 .claude/hooks/tests/test_switches.py` (48 OK) | 0 |
| `py -3 .claude/hooks/tests/test_database_override.py` (49 OK) | 0 |
| `py -3 .claude/scripts/tests/test_switch_env_scan.py` (14 OK, 2 expected failures: the retired-name text row and the README table row, both owned by the documents block) | 0 |
| `py -3 .claude/hooks/tests/test_db_destructive_guard.py` (605 of 605) | 0 |
| `py -3 .claude/hooks/tests/test_db_guard_path_allowlist.py` (OK) | 0 |
| `py -3 .claude/hooks/tests/test_readonly_guard_disposable_exemption.py` (16 of 16) | 0 |
| `py -3 .claude/hooks/tests/test_worktree_path_guards.py` (190 of 190) | 0 |
| `git check-ignore -v .claude/database-override.once .claude/switches.local.json .claude/database-override.claimed-x` | 0 |
| `gh pr view 432 --json body` (documentation quotes: "deny > defer > ask > allow"; `auto` mode treated as no-prompt) | 0 |

**Arm-write routes.** "dg" is the destructive guard and "rg" the read-only guard. SEEN means refused with exit 2. MISSED means exit 0.

| Route | Guard | Result |
|---|---|---|
| R1 Write `<p>/.claude/database-override.once` | dg | SEEN |
| R2 Write `<p>\.claude\DATABASE-OVERRIDE.ONCE` | dg | SEEN |
| R3 Write `…/database-override.once/.` (Win32 creates the arm) | dg | **MISSED (W1)** |
| R4 Write `…/database-override.once/x/..` (Win32 creates the arm) | dg | **MISSED (W1)** |
| R5 Write `…once::$DATA`; trailing dot or space (prefix still matches) | dg | SEEN |
| R6, R7 Write with the long-s or dotless-i look-alike (NTFS does not fold them: a different file is created, so this is not a route) | dg | MISSED, harmless |
| R8 Edit, R9 MultiEdit, R10 NotebookEdit on the arm path | dg | SEEN |
| R11 Write a script file `mk.py` whose content creates the arm | dg | MISSED (residual, by design) |
| S1 `touch`, S2 PowerShell `New-Item` (mixed case), S3 `echo >`, S4 `echo x > "<arm>"` | dg | SEEN |
| S5 `git commit -m "x" > "<arm>"` | dg | **MISSED (W2)** |
| S6 commit message, S7 grep pattern, S8 `gh pr create --body` that only mention the name (must be allowed) | dg | allowed, correct |
| S9 `python -c "open('<arm>','w')"` | dg | SEEN |
| S10 `database-override\.once`, S11 `overri''de`, S12 brace expansion, S13 `$n` join, S14 `python -c` with `'+'` join | dg | MISSED (residual) |
| S15 PowerShell `-EncodedCommand`, S16 backtick-dot, S17 string concatenation | dg | MISSED (residual) |
| S18 `python mk.py` (a script written earlier) | dg | MISSED (residual) |
| S19 `mv` onto the arm, S20 writing a claim file directly, S21 `echo … \| sh`, S22 `git -c alias…`, S23 `git commit … && touch`, S24 `tee` | dg | SEEN |
| S25 `sh -c "…overrid\x65.once"` | dg | MISSED (residual) |
| S27 `touch`, S28 `New-Item` | rg | SEEN |
| S29 commit-message mention | rg | allowed, correct |
| P8 helper removed: Write arm and `touch` arm; P8b helper and parser removed | dg, rg | SEEN |
| P9 non-ASCII payload with `touch <arm>` | dg, rg | SEEN |

**Override decisions** (armed unless noted; the command is a removal of a non-disposable database passed to `sqlcmd -Q`):
O0 not armed: BLOCK. O1 `default`: ASK, arm gone; reason `… Target: "unresolved" as written in the command.` O2 `acceptEdits`: ASK. O3 `plan`: ASK. O4 `bypassPermissions`, O5 `dontAsk`, O6 `auto`, O7 mode missing, O8 `Default`: BLOCK, arm kept. O9 stale: BLOCK, arm removed. O10 future modification time: ASK (N1). O11 human-only alone: BLOCK, arm kept. **O12 human-only plus argument-position bug: ASK. O13 human-only plus a row-deleting statement on a protected database: ASK. O14 EF forward update plus argument-position bug: ASK (B1).** O15 `git status`: ALLOW, arm kept. O16, O17 crafted targets: the target is `unresolved`. O18 no `tool_use_id`: ASK (first guard). O19 rg write without read-only: ASK, fixed wording only. O20 rg `bypassPermissions`: BLOCK.
P1 dg then rg on one id: ASK, ASK. P2 rg then dg: ASK, ASK. P3 no id: ASK, BLOCK. P4 different id: ASK, BLOCK. P5 `_plain_reason` direct: `Prod /* disposable test copy */` gives `"Prod disposable test copy"`; a newline and `--` are removed; U+202E and U+2028 are removed; the quote-forged name survives (N2). P7 retired variable set to 1, not armed: BLOCK, BLOCK.

**Files read:** `_switches.py` (whole), the diff of both guards in `e1dfa2d..adb70aa`, `db-destructive-guard.py:1572-1720` (prose masking), `:869-891`, `:1030-1068`, `:1195-1275`, `:1965-2275`, `db-research-readonly-guard.py:586-591`, the `_switches` bindings in `concept-gate.py:92,246-280` and `architecture-guard.py:74,443`, the run sheet `t3-live-prompt-trial-senior-test-engineer.md`, and the contract.

## Disposition

Back to the implementer of the helper block (`python-ai-developer`) on a new sub-task pull request into `feature/file-based-switches`:

1. Fix B1 (decide the no-prompt class from the targets) with the three armed rows named under B1.
2. Fix W1 and W2 in both guards' Arm-write code, with rows for `/.`, `/x/..` and `git commit … > "<arm>"`.
3. Fix W4 (`S_ISREG` after following the link) and N1 (no future modification time), with rows.
4. Ask the architect to add W3(a) and the allow-rule question W3(b) to the residual-risk paragraph, and to add a run-sheet step for W3(b). The documents block carries the README text.

Then re-run this gate. The re-run's Gate Output names this report in `supersedes`. The ordinary switches block is unaffected. The documents block and the final review stay held until this gate releases.
