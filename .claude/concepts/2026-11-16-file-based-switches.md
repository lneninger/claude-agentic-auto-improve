# Concept Contract — Replace environment-variable switches with file-based switches

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-16
**Requested by:** user
**Status:** approved
**Revision 3:** 2026-11-20, security-review remedy round 3 (amendment 3). The third security review (`t12`, pull request 459) read `blocked`: finding B1 was not cleared for a third round, because the quote scanner `_starts_a_command` reads quotes with one escape model for both shells, so a trailing backslash before a closing quote (`cd "<folder>\"; <script>` in PowerShell, `cd "C:\\w\\" && <script>` in bash) or an escaped quote outside quotes still hides the human-only script; with no arm the same shapes run it with no prompt (P1, older than this contract). t12 cleared W4 (Windows) and I1 by a real pipe-link attempt. This revision adds the third fixes block (13) and the fourth security review (14), re-links the documents and final review blocks to block 14, and amends the No-prompt classes rule, adds the Audit-log rule, and updates Failure Modes, Uncertain Assumptions and the residual-risk paragraph (t12 W6 (a) to (d), and the elevation sentence, t12 N5). Blocks 1 to 12 keep their ordinals, headings and ids, and block 12's own text is unchanged. The two amendment-3 Open Questions are answered (user, 2026-11-20, "take the recommended package"): t12 P2 (a script after a shell keyword, a prefix command or inside backticks) is in block 13, and t12 I2 (a pipe link at an audit log) is in block 13, extended to both database guards (`db-guard.log` and the read-only guard's `db-research.log`). Second pass, same day: the fourth critique round's blocker (the read-only guard does write its audit to the project), five warnings and the NITs are applied, except the budget NIT. Status stays `approved` at the caller's direction; blocks 13 and 14 are not dispatched until their sub-issues exist. Preconditions for the main session before the first dispatch: the t12 report and its Gate Output are merged into the parent branch (done, pull request 459, merge `8a438e5`); sub-issues for blocks 13 and 14 are opened; the t6 and t7 briefs and sub-issues 425 and 426 are refreshed with the new Depends on lines and block text.
**Revision 2:** 2026-11-19, security-review remedy round 2 (amendment 2). The security re-review block (`t10`) read `blocked`: finding B1 was not cleared, because the human-only script is not seen when quoted text comes before it in the same call, and the same cause lets that script run with no arm at all (P1, older than this contract). This revision adds the second fixes block (11) and the third security review (12), re-links the documents and final review blocks to block 12, and amends the No-prompt classes rule, the Broken-file rule, the Guard rules file entry, Uncertain Assumptions, Failure Modes and the residual risk. Blocks 1 to 10 keep their ordinals, headings and ids, and block 10's own text is unchanged. Step 6 of the second live trial was met (with the session start time inferred, not recorded; see Uncertain Assumptions), so the override is **not** withdrawn. Status is `draft` until the user re-approves. Second pass, same day: the user's answers (destructive guard alone decides in block 11's rows; I1 in block 11; L1 accepted; no third live trial) and the critic's third-round blocker and seven warnings are applied. Preconditions for the main session before the first dispatch: the t10 report and its Gate Output are merged into the parent branch (today they sit on the t10 task branch only); sub-issues for blocks 11 and 12 are opened; the t6 and t7 briefs and sub-issues 425 and 426 are refreshed with the new Depends on lines and block text.
**Revision:** 2026-11-18, security-review remedy round 1. The security review block (`t4`, pull request 440) read `blocked`. This revision adds the fixes block, the second live trial block and the security re-review block (8, 9 and 10), re-links the documents and final review blocks to the re-review, and amends the rules and the residual risk the review found wrong. Blocks 1 to 7 keep their ordinals, headings and ids. Status is `draft` until the critic runs and the user re-approves. Second pass, same day: the user's answers ("Accept all") and the critic's round-two warnings are applied (the W2 rule narrowed, the W4 open made non-blocking, a fresh session in the second trial's step 6, the Gate Output files named in blocks 9 and 10).
**Work Item Brief:** .claude/work-items/2026-11-16-file-based-switches.md
**Parent issue:** #419 (https://github.com/lneninger/claude-agentic-auto-improve/issues/419), opened on 2026-11-16 and recorded in the brief's `id:`.
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. Implementer agents refuse to run unless `Status: approved` or `Status: implemented`. The `concept-gate.py` hook reads `Files to touch` to decide whether an edit is allowed. Lifecycle, budget rule and management commands are as in `.claude/templates/concept-contract.md`.

**Short forms used below.** JSON (JavaScript Object Notation) is the text format of the switch files. SHA-256 is a fixed-length fingerprint of a file's bytes. POSIX shells are the shells of macOS and Linux. Standard output and standard error are a hook's normal and error output streams. A byte order mark (BOM) is an invisible marker some editors put at the start of a file. UTF-8 and UTF-16 are text encodings. SDK means software development kit. The *payload* is the JSON input Claude Code sends to a hook. *Fail-soft* means a failed import leaves the defaults in force instead of stopping the hook. An *atomic rename* is a rename the operating system does in one step, so only one process can win it.

**Delivery shape.** This contract has fourteen mergeable blocks, so it is delivered through a parent branch (`feature/file-based-switches`, the brief's `branch:`). It needs the parent issue named above, one sub-issue per block (three new ones for blocks 8 to 10, two more for blocks 11 and 12, two more for blocks 13 and 14) and a landing pull request. No block raises the plugin version; the landing raises it once. The blocks are named in prose by their headings: the RED tests block, the helper block, the live trial block, the security review block, the ordinary switches block, the documents block, the final review block, the fixes block, the second live trial block, the re-review block, the second fixes block, the third security review, the third fixes block and the fourth security review. The graph: 1 → 2 → {3, 5}; {2, 3} → 4 (delivered, `blocked`); 2 → 8 (fixing 4's findings; 8 cannot name 4, because the loop never releases a block whose dependency reads `blocked`); 2 → 9; {8, 9} → 10 (delivered, `blocked`); 8 → 11 (fixing 10's findings; 11 cannot name 10, for the same reason); 11 → 12 (delivered, `blocked`); 11 → 13 (fixing 12's findings; 13 cannot name 12, for the same reason); 13 → 14; {5, 14} → 6; {5, 6, 14} → 7. Before amendment 3 the last two edges read {5, 12} → 6 and {5, 6, 12} → 7; before amendment 2 they read {5, 10} → 6 and {5, 6, 10} → 7.

---

## Business Concept

- **What is this thing, in domain language?**
  A *switch* is a named setting that turns one behaviour of a default hook or script on or off. Today each switch is an environment variable, a value set in the shell before Claude Code starts. The user finds that confusing and has banned it. After this change every switch lives in one visible file per project, `.claude/switches.json`, committed to the repository. A person may override any key for themselves in `.claude/switches.local.json`, which is never committed. One shared helper reads both files; no hook reads its own. The destructive-database override is not a switch. It becomes a one-shot *arm* file that only a person should create. Arming never allows a command by itself: it lets the next blocked command be shown to the person as a Claude Code permission prompt, once.

- **Existing VOCABULARY.md terms that apply:** Add-on (`VOCABULARY.md:79`; it has no switch, and its uninstall skill is the way out), Add-on manifest (`:84`), Guard deference (`:95`), Changed-file check (`:98`), Layout defect (`:75`), Gate launcher (`:68`), Vendored asset (`:92`). The Hand-off command term (`:140`) is deliberately **not** reused: it covers commands the cloud skill writes out and says no new authorization mechanism exists, and neither holds here.

- **New terms proposed for VOCABULARY.md (Universal root):**
  - **Switch** — a named setting a default hook or script reads to change its own behaviour. It is declared once in the Switch catalog and read only through the switch helper. Host-supplied variables and guard rules file entries are not switches.
  - **Switch file** — `<project>/.claude/switches.json`, committed, holding the project's switch values, one key per switch.
  - **Local switch file** — `<project>/.claude/switches.local.json`, never committed, holding one person's overrides. A key set here wins over the Switch file.
  - **Switch catalog** — the one list, inside the switch helper, of every switch key with its allowed values, its default and the files allowed to set it.
  - **Database override arm** — the file `<project>/.claude/database-override.once`, meant to be created by a person. It makes the next blocked destructive database command a permission prompt, once, and is used up whatever the answer.

---

## End-User View

Not applicable. Reason: `Files to touch` names no Angular component, template, stylesheet, state service, route file or shared layout; this contract changes hooks, scripts, skills and documents only.

---

## Data Shapes

### Inventory of environment reads (exhaustive, verified by search on 2026-11-16)

**Plugin-owned switches read in code — each becomes a catalog key, or the arm:**

| Old variable | Read at | New key | Values (default first) | Allowed in |
|---|---|---|---|---|
| `CLAUDE_CONCEPT_GATE` | `concept-gate.py:242`; also `concept_changed_check.py:471,520` through import | `concept_gate` | on, off | both files |
| `CLAUDE_ACTIVE_CONTRACT` | `concept-gate.py:247`; also `concept_changed_check.py:402` | `pinned_contract` | empty, a contract path | Local switch file only |
| `CLAUDE_ARCH_GUARD` | `architecture-guard.py:439` | `architecture_guard` | on, off | both |
| `CLAUDE_ACCURACY_TRACKER` | `critic-verdict-tracker.py:82`, `contract-status-watcher.py:80`, `journal-post-approval-tracker.py:58` | `accuracy_tracker` | on, off | both |
| `CLAUDE_INTEGRATION_CHECK` | `integration-check.py:95` | `integration_check` | on, off | both |
| `CLAUDE_MEMORY_PAGER` | `memory-pager.py:51` | `memory_pager` | on, off | both |
| `CLAUDE_WORKING_AGREEMENTS` | `working-agreements.py:152` | `working_agreements` | on, off | both |
| `CLAUDE_PLAN_QUESTION_ADVISOR` | `plan-question-advisor.py:65` (missing from the brief's list) | `plan_question_advisor` | on, off | both |
| `CLAUDE_CONTRACT_INDEX` | `.claude/scripts/_contract_index.py:110` | `contract_index` | on, off, trace | both |
| `CLAUDE_DESTRUCTIVE_DB_OK` | `db-destructive-guard.py:1758,1956`; `db-research-readonly-guard.py:342` | none: the Database override arm | — | — |

Text that names these variables without reading them: `concept-gate.py:27-28,673-674,713`; `architecture-guard.py:23,1263,1333`; the three trackers' docstrings; `plan-question-advisor.py:20,43`; `db-destructive-guard.py:21,35-39,1766,2041-2043`; `concept_changed_check.py:71`; `_contract_index.py:42-52`; `.claude/addons/strict-shell-gate/hooks/bash-gate.py:321`; the `$comment` of `hooks.json` (line 70); `README.md:595,757,1066-1085`; `MECHANISMS.md:20,76`; `VOCABULARY.md:82`.

**Host-supplied, kept.** `CLAUDE_PROJECT_DIR`, read at `_project_paths.py:53,945,1066,1289,1342`, `db-destructive-guard.py:415,832`, `db-research-readonly-guard.py:170`, `protected-names-warning.py:81`, `working-agreements.py:113`, `_gate_launch.py:60,75`, `_main_checkout_guard.py:820`, `cleanup_delivered.py:949-950`, `compose_subissue_title.py:109,117`, `codegraph_shadow_report.py:330`, `land_contract.py:397-405,653,3477-3485`, `pr_merged.py:1171`, `registry_append.py:418`, `registry_migrate.py:231`, `codegraph-first-guard.py:787,974` and `angular-tailwind-advisor.py:113`. `CLAUDE_PLUGIN_ROOT` at `_project_paths.py:941`, `_plugin_root.py:94`, `land_contract.py:2977`, `plugin_doctor.py:224`, `registry_migrate.py:104`. `CLAUDE_CONFIG_DIR` at `_project_paths.py:869`, `_plugin_root.py:51`, `land_contract.py:2980`, `codegraph-first-guard.py:842`. `CLAUDE_SESSION_ID` and `CLAUDE_CODE_SESSION_ID` at `_error_log.py:74` (a loop over the two names). `CLAUDE_CODE_PLUGIN_DIRS` appears in README text only.

**Platform and third-party tool plumbing, kept (a class the brief did not name).** `PATH` (`_protected_names.py:577`, `land_contract.py:3054`), `LOCALAPPDATA` (`audit-db-destructive-history.py:90`), `GH_REPO` and `GH_HOST` (`land_contract.py:3734`, `merge_direction.py:164,175`, `pr_merged.py:4452`). Reads whose name is not a literal: `_error_log.py:74` (`os.environ.get(key)`), the `${VAR}` expansion of hook-row text at `_project_paths.py:783`, and `session_parent_base(os.environ, ...)` in the three codegraph add-on hooks, which reads `LOCALAPPDATA`, `XDG_CACHE_HOME` and `HOME`. Whole-environment copies handed to child processes: `_main_checkout_guard.py:640`, `_protected_names.py:300,401`, `land_contract.py:194,2862`, `concept_changed_check.py:213`. None of these changes the plugin's own behaviour by a person's choice.

**Test-only, kept.** `DB_GUARD_FAULT_INJECTION` (`db-destructive-guard.py:1232,1474,1743`) can only turn an allow into a block. `CLAUDE_TEST_SCRATCH` (`test_contract_index.py:106`, `test_gate_cost.py:93`), `CLAUDE_GATE_COST_CONCEPTS` (`test_gate_cost.py:176`), `AGENTIC_PLUGIN_ROOT` (`test_plugin_doctor.py:316`), `GH_CONFIG_DIR`, `GITHUB_HEAD_REF`, `GITHUB_BASE_REF` and fixture variables (`STUB_*`, `PROBE_RECORD`, `CI_MARKER`, `HARMLESS_FIXTURE_VARIABLE`, `CLAUDE_PLANTED_X`) are read by tests only. The `CLAUDE_*` strip lists in tests stay, as issue 119 left them.

**Skill text that tells a person to set a variable:**

| Text | Where | Decision |
|---|---|---|
| `CLAUDE_CONTRACT_SKIP=off` | `skills/design-first/SKILL.md:162,186`; `skills/contract-accuracy/SKILL.md:64` | **Delete.** No code reads it. The skip offer already asks the user ("Run anyway"), and `/critique-now` runs the critic. |
| `CLAUDE_VERIFY_REVIEW_GATE=off` | `skills/verify-before-done/SKILL.md:228` | **Delete.** No code reads it. The way out becomes the user saying so in their own message, recorded in the commit message. |
| `CLAUDE_CONCEPT_GATE=off` | `skills/design-first/SKILL.md:423`; strict-shell-gate install `:139`, uninstall `:19,:132` | Reword to the `concept_gate` key. |
| `CLAUDE_ARCH_GUARD=off` | `skills/promote-ui-rule/SKILL.md:84,106` | Reword to the `architecture_guard` key. |
| `CLAUDE_ACTIVE_CONTRACT`, `CLAUDE_DESTRUCTIVE_DB_OK`, "kill-switches" | `skills/auto-improve-finish-install/SKILL.md:345-348` | Reword: print the `switches` report field; describe the arm. |
| `CLAUDE_DESTRUCTIVE_DB_OK` | `skills/sql-server-patterns/SKILL.md:128,186`; `skills/auto-improve-database-guard-install/SKILL.md:167` | Reword: an agent never creates the arm file. |
| `CLAUDE_SKIP_CG`, `CLAUDE_BASH_GATE` | `skills/auto-improve-codegraph-install/SKILL.md:192`; strict-shell-gate skills | Reword to "has no off switch" without naming a variable. |

### Entities

| Name | Fields | Invariants | Ownership |
|------|--------|------------|-----------|
| Switch catalog entry | key (text), allowed values (closed set), default (value), allowed in (both files, or the Local switch file only), honoured by (hook names), replaces (old variable name, for documents only) | Keys are lower-case words joined by `_`. One entry per switch. The README switch table lists exactly the catalog keys, and a test checks it. | `.claude/hooks/_switches.py` |
| Switch file and Local switch file | path; layer (project or personal); one JSON object of key to value; an optional `$comment` key, ignored | the switch rules below | the project (Switch file); one person (Local switch file) |
| Database override arm | path `<project>/.claude/database-override.once`; modification time; contents ignored | the override rules below | the person at the keyboard |
| Arm claim | path `<project>/.claude/database-override.claimed-<tool call id>` | made only by an atomic rename of the arm; removed when older than 15 minutes | the database guards |

**Switch rules.**
- **No-file rule.** A missing file, or a file that is empty or holds only whitespace, means "no settings". Every key keeps its default, and every guard stays enabled.
- **Broken-file rule.** A file that cannot be read (a permission error, a folder at that path, anything that is not a regular file once links are followed, such as a named pipe, a socket or a device, bytes that decode in no accepted encoding) or that is not a JSON object makes the helper ignore **every** switch file. Every key is then at its default. A broken personal file can therefore never leave a committed `off` in force, nor turn anything off itself. No read may wait. On every platform the file is opened read-only (non-blocking where the platform offers it, POSIX) and its kind is checked on the open file itself (`fstat`), so a named pipe neither blocks nor can be swapped in between a check and the open; anything but a regular file is closed unread and counts as unreadable. ~~Windows has no named pipes at a file path~~ *(reversed by amendment 2, re-review finding W4: a symbolic link at the switch-file path can point at a Windows named pipe, `\\.\pipe\<name>`, and reading through it hung the helper; opening it returns at once and `fstat` shows it is not a regular file, so the open-then-check now runs on Windows too)*. Opening a link whose target is on a disconnected network drive can also stall until the hook times out, and a timed-out hook is an allow (the 2026-11-06 drive-letter lesson). So on Windows a switch file that is a link is judged first by its target, from the local drive table with no network access: a network drive, a `\\server\share` target, or a device-namespace target (`\\.\…`, or `\\?\…` not followed by a drive letter) counts as unreadable and is never opened. A project folder that itself sits on a network drive is out of scope.
- **Encoding rule.** The helper reads bytes. It drops a leading UTF-8 byte order mark, decodes UTF-16 when the file starts with a UTF-16 byte order mark (what Windows PowerShell 5.1 writes with `>` or `Out-File`), and otherwise decodes UTF-8.
- **Bad-entry rule.** An unknown key is ignored. A value outside its allowed set leaves that key at its default. The exception is `contract_index`, where an unknown value means `off`, as today. A `pinned_contract` in the Switch file is ignored as misplaced.
- **Personal-wins rule.** The Local switch file wins, key by key, over the Switch file.
- **Project-folder rule.** Files are read only from `<project>/.claude/`. The project is the one the caller names; when it names none, the project comes from `CLAUDE_PROJECT_DIR`. The helper never searches the working directory, the plugin's own `.claude` folder or any other root. With no project known, every key is at its default.
- **Worktree rule.** A worktree "has its own" Local switch file when anything exists at that path, even an empty or broken file. Only a linked worktree with nothing there reads the Local switch file of its main checkout, found with `main_checkout_root`. A broken main-checkout file counts under the Broken-file rule. The Switch file always comes from the worktree itself.
- **Values.** `off` is JSON `false` or the text `off`, `0`, `false` or `no`, in any case, trimmed. `on` is JSON `true` or `on`, `1`, `true` or `yes`. These are the old variables' sets.
- **Report-once rule.** Each problem (unreadable, broken, unknown key, bad value, misplaced key) is written to the error log through `_error_log.log_event`. It is reported once per distinct file state. For a readable file the state is its SHA-256 fingerprint; for an unreadable file it is the path, the error kind and the modification time. The log record is written first. A marker file named after the state, under `_project_paths.state_dir()`, is written only after the log write succeeds. If either write fails, the problem is reported again next time and never silenced.
- **Visible-off rule.** A hook honouring a non-default value writes one line to standard error. A guard (the concept gate, the architecture guard) honouring `off` also returns the JSON field `systemMessage`, which Claude Code shows to the person. It does so once per session, per key, per value and per source file. The once-per-session marker uses the same state folder.
- **No-environment rule.** No shipped hook, script or add-on hook reads a plugin-owned switch or a retired variable from the environment. A missing or stale helper means every default, and no override.

**Override rules.**
- **Prompt-only rule.** The arm allows nothing by itself. The most it yields is a permission prompt.
- **Use-once rule.** The arm is claimed (renamed) before the prompt. One arm serves one tool call, whatever the answer.
- **Fresh-arm rule.** The arm counts only when it is a regular file (not a link or a folder) modified in the last 15 minutes and not more than 60 seconds in the future. Otherwise the guard removes it and blocks, naming the reason. The claim sweep uses the same window: a claim older than 15 minutes, or dated more than 60 seconds ahead, is removed.
- **Person-present rule.** The prompt is offered only when the payload's permission mode is one where Claude Code asks (`default`, `acceptEdits`, `plan`). For `bypassPermissions`, `dontAsk`, or a missing or unknown mode, the guard blocks. The block text then tells the person to run the command themselves, in their own terminal.
- **Arm-write rule.** Both database guards refuse a tool call that would write the arm. For the edit tools (Write, Edit, MultiEdit, NotebookEdit) that is a target path whose last part starts with `database-override.`, in any case, judged after the path is normalised the way the operating system opens it: slashes folded, `.` and `..` parts resolved, and trailing dots and spaces dropped from each part. So `<arm>/.` and `<arm>/x/..` are refused. For the shell tools (Bash, PowerShell) it is either a write target found by the shared shell parser `_shell_write_targets.parse_redirect_targets` with that name, or that name in the command text **after** the guard's existing masking of inert quoted prose. For this rule only, a `git` segment with a real output redirection to a named file (`>` or `>>`, with or without a stream number, followed by a path) is not prose, so `git commit -m "x" > "<arm>"` is refused. A stream duplication such as `2>&1` and a plain pipe `|` do not count, so `git commit -m "<mentions the name>" 2>&1 | tail` stays allowed. The masking used for destructive-command detection is unchanged, and the shared parser is not changed. So a commit message, a pull request body or a search pattern that only mentions the name is allowed, while `New-Item`, `touch`, a redirection (also after `git commit`, `git tag` or `git notes`) or a quoted path argument is refused. The check runs before Guard deference and before every other rule, in every copy of each guard, because it reads no project rules.
- **No-prompt classes rule.** Commands the destructive guard classes as `human-only`, and the internal-error path (`_fail_closed`), never offer the prompt. Both block. The class is decided from every target the tool call matched, not from the one reason chosen for the block text: when any matched target is `human-only`, the guard does not touch the arm and blocks, whatever other reason (a protected-database write, the EF argument-position check) the same call also raised. The block text then carries the human-only instruction. A human-only script is **invoked** (and so a `human-only` target) when the word that holds it, quoted or not, is the first word of a command segment, after any launcher word the guard already knows (`call`, `start`, `&`, `sh`, `cmd /c`, `-File` and the rest), wherever the segment stands in the call; segments are split on separators outside quotes (`;`, `&`, `|`, `&&`, `||`, `(`, a newline). Text inside the quoted argument of a known launcher (`bash -c "…"`, `cmd /c "…"`, `powershell -Command "…"` and the rest) is itself command text and is split the same way, so `bash -c "cd x; <script>"` is invoked. It is only **mentioned** when that word is an argument of a command that is not a launcher, such as text inside a commit message or an `echo`. The classifier may only move a form from mentioned to invoked, never the reverse: every form classed as invoked before amendment 2 stays invoked. Quoted text in an earlier segment never decides it (amendment 2, re-review findings B1 and P1: a closing quote before the script used to hide it, so the arm was claimed and, with no arm, the script was allowed). Where a quote ends depends on the shell, and the guard does not know which shell will run the text, so it does not guess one (amendment 3, t12 findings B1 and P1: one escape model for both shells misread a trailing backslash before a closing quote and an escaped quote outside quotes). The script is invoked when ANY of these four readings says so, each computed on its own: the readings the guard used before amendment 3; a bash reading (a backslash escapes the next character outside quotes and inside double quotes, nothing is escaped inside single quotes, `$'…'` takes backslash escapes, and a backtick outside single quotes opens a command segment, as `$(` does); a PowerShell reading (a backtick escapes the next character inside and outside double quotes and never opens a segment, `""` and `''` are doubled quotes, a backslash is a plain character); and a quote-blind reading (the nearest character before the script's word, skipping spaces, a folder prefix and an optional quote, is a separator: `;`, `&`, `|`, `(`, `{` or a newline, never a backtick). The backtick rule belongs to the bash reading alone, so it never conflicts with the PowerShell reading. All four readings are part of this rule; none is optional. Because the readings are joined by "any", the change can only move a form from mentioned to invoked. Text the prose masker has already blanked (commit messages, `echo` text, search patterns, pull request bodies) is not read again, so those mentions stay allowed. **Command-start words (amendment 3, t12 finding P2; user answer 2026-11-20: included).** A word that itself starts a command segment and is one of `then`, `do`, `else`, `elif`, `!`, `time`, `env`, `nohup`, `exec`, `command`, `builtin`, `nice`, `timeout`, `xargs` or `sudo` does not end the search: the next word, after any `NAME=value` assignments and that word's options, starts the command. An option is a word starting with `-`; an option that takes a value also skips its value (`nice -n 10`, `sudo -u root`, `env -u NAME`, `timeout -s KILL`; block 13 lists them), and `timeout` also skips its duration. A leading `NAME=value` assignment is skipped the same way. Exception: `command -v` and `command -V` look a name up without running it, so the next word stays **mentioned** (a named mention, not a false block).
- **Audit-log rule (amendment 3, t12 finding I2; user answer 2026-11-20: included, extended to both database guards).** No step of either database guard's audit write may wait or follow a link: the destructive guard's `<project>/.claude/logs/db-guard.log` and the read-only guard's `<project>/.claude/logs/db-research.log` (`db-research-readonly-guard.py:95-98`, written by `_audit` at `:350-364` on its block path) are treated the same. The check covers the whole audit path, not only the append. (1) Folders: each part from the folder that holds `.claude` down to the log folder is checked without following links and must be a real folder, not a link or, on Windows, any reparse point (a junction included); a missing part is created one level at a time and checked again. (2) The log: checked without following links; a link or anything but a regular file is refused. (3) Rotation: only a regular log over the size limit is rotated, and only when the rotated name is absent or itself a regular file, both checked without following links; no step follows a link to rename or remove its target. (4) The open: write-only for appending, creating when missing, non-blocking and not following links where the platform offers those flags, then a check of the open file itself (`fstat`) before any byte is written. A log that fails any step is closed unwritten, the audit record for that call is skipped, and the guard writes one line to standard error. The decision has already been made, so skipping the record never changes it. Policy difference from I1, deliberate: the rules-file reader follows a link to a local regular file (such a rules file still loads), while the audit log refuses every link, because a log has no reason to be a link and a write through one reaches a file the guard did not choose. So the Windows link-target check of the rules-file reader is not needed here: any link is refused before its target matters, and the open-then-`fstat` check covers a link swapped in after the check.
- **Variable-retired rule.** `CLAUDE_DESTRUCTIVE_DB_OK` is not read anywhere.
- **Untouched rule.** A tool call that matches no destructive or write rule leaves the arm alone.
- **Shared-claim rule.** When both database guards match one tool call, the first one renames the arm to the claim name carrying the tool call identifier (`tool_use_id`). The other guard accepts that claim for the same identifier, and both may ask. With no identifier in the payload, the second guard blocks.
- **Plain-reason rule.** The prompt reason is fixed wording: "One-shot destructive database override. A person armed it. Approve only if you mean to run this exact command." It names each target only after neutralising it. Control characters and comment markers (`/*`, `*/`, `--`, `#`) are removed, whitespace is collapsed, each target is cut to 60 characters, and each is labelled "as written in the command". The host's own prompt also shows the full command.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Switch reading | key; value in force; source (`switches.json`, `switches.local.json`, the main checkout's `switches.local.json`, or `default`); problems found | the helper's answer for one key, and one row of the finish-install `switches` report field |
| Override outcome | one of `absent`, `stale`, `unusable`, `claimed`, `claimed-by-sibling`, `no-prompt-available` | the database guards' decision input and audit reason |

### Events

| Name (past tense) | Emitter | Listeners | Payload |
|---|---|---|---|
| Switch problem reported | switch helper | the error log (`errors.jsonl`) | hook, file, problem kind, key |
| Non-default switch honoured | each hook | standard error; for a guard switched off, the person, through `systemMessage` | key, value, source file |
| Override arm claimed | database guards | `db-guard.log` (destructive guard), `db-research.log` (read-only guard) | tool call identifier, outcome, permission mode |
| Override write refused | database guards | `db-guard.log`, `db-research.log`, standard error | tool, matched path or text |

### Commands

| Name | Handler | Payload | Possible rejections |
|---|---|---|---|
| Read switch | `_switches.switch(key, project=None)` | key; optional project | an unknown key raises (a programming error, caught by tests) |
| Read every switch | `_switches.effective_switches(project=None)` | optional project | none: problems are reported, never raised |
| Claim database override | `_switches.claim_database_override(project, tool_call_id)` | project; tool call identifier | returns an Override outcome; never raises |
| Name test | `_switches.names_override_file(path_or_text)` | path or masked command text | none |
| Read regular file (amendment 2) | `_switches.read_regular_file_bytes(path)` | path | raises for anything not a regular file (a pipe, a device, a folder, a network or device-namespace link target); each caller maps that to its own fail direction: the switch helper to every default, the database guards' rules loaders to their strict default |

---

## Reused Mechanisms

- **Two-layer Claude path resolution** (`MECHANISMS.md:46`) — consumed as-is. `project_dir()`, `state_dir()` and `main_checkout_root()` are call-time functions; the helper calls them on each read and never stores a path at import. The bridge `_claude_paths.py` is **not** extended: a script that needs the helper imports the bridge, which already appends the hooks folder to `sys.path`, then imports `_switches` fail-soft.
- **Guard fallback mode** (`:64`) — extended. Each database guard binds `claim_database_override` and `names_override_file` with `getattr`. A missing binding means no override. Each guard keeps an inline copy of the name test for the Arm-write rule, with one fallback test row per copy. Other hooks bind `switch` the same way; a missing binding means the default. Amendment 3: the Audit-log rule adds no helper binding and no new helper entry point, because the audit write must work with the helper missing and is a write, not a read; each database guard carries it inline. It does not reuse the I1 link-target check, which would be dead code there: the audit log refuses every link before a target is judged (the Audit-log rule's policy difference). No new mechanism.
- **Guard rules file** (`:62`) — not extended as a switch home (see Alternatives); its reading is hardened by amendment 2. Its fail-closed rule for the database guards is unchanged. Amendment 2 (user answer 2026-11-19, Open Question "Rules-file pipe link": yes): both database guards read `db-destructive-guard.rules.json` through the same regular-file check as the switch helper (`read_regular_file_bytes`: the Windows link-target check first, then open, `fstat`, regular file only), bound from the helper with an inline fallback copy in each guard (Guard fallback mode; the read-only guard becomes a new user of it). A file that fails the check counts as unreadable, which is the existing fail-closed path. A regular file decodes exactly as today. ~~so no rules file that works now changes meaning~~ *(corrected, third critique round W6)*: one working form does change meaning: a rules file that is a link to a network drive or a `\\server\share` file loads today and now counts as unreadable, so every database is protected and the disposable exemption is withdrawn. That is accepted fail-closed behaviour (Failure Modes, I1); the way out is a regular file in the project folder.
- **Guard deference** (`VOCABULARY.md:95`) — consumed as-is. The Arm-write rule runs before it; the arm is honoured only by a guard that does not defer.
- **Main-checkout guard** (`:78`) — consumed as-is. It keeps "never add a variable, flag or file that switches it off". A test proves `concept_gate: off` leaves it enforcing.
- **Session-start context delivery** (`:76`) — extended: its way out becomes the `working_agreements` key.
- **Preview-hash apply** (`:72`) — consumed as-is. The readiness report gains a `switches` field and loses `kill-switches`. The add-on plans keep their empty `kill-switches` list.
- **Add-on layout** (`:113`) — extended: the strict-shell-gate add-on's helper list gains `_switches.py` and `_error_log.py`.
- `_shell_write_targets.parse_redirect_targets` and the destructive guard's prose masking — consumed as-is, for the Arm-write rule.
- `_error_log.log_event` — consumed as-is, for the Report-once rule.

## New Mechanisms

- **Name:** Switch file and switch helper.
- **Purpose:** one visible, layered, project-level place for every switch, read through one module.
- **Why an existing mechanism was not sufficient:**
  - *Guard rules file.* It is one file per hook, so a person must know which file turns which hook off. Five switched hooks have none. `working-agreements.rules.json` is read from the hook's own folder, which is the plugin cache under a plugin install. Rules files have no personal layer. Putting "off" into `db-destructive-guard.rules.json` would mix a bypass into the safety file.
  - *Project profile* (`MECHANISMS.md:69`). It holds facts about the project (roots, review documents, the memory server), not a person's preferences. Its rule "never invent a local-only slot" forbids the personal layer a switch needs. It has no personal file at all. It is markdown, so every hook, including the hooks on every edit and every prompt, would need a markdown table parser. The Memory adapter's "profile switch" is a project fact (which server exists), which is exactly what the profile is for.
  - *Two-layer path resolution* locates files but owns no values or defaults.
- **Proposed location:** `.claude/hooks/_switches.py`.
- **Extension seam:** a new switch is one catalog entry, one README row and one on/off test pair. It is never an environment read; the scan test fails one.
- **Will this be promoted to `MECHANISMS.md` after implementation?** yes, in the documents block.

## Extension Points

- `concept-gate.py`: `bypass_env(project=None)` and `pinned_contract(project=None)` keep their names, so the binding at `concept_changed_check.py:393` still works. They read `concept_gate` and `pinned_contract`. A relative pin resolves against the same project. The block message's "Escape hatches" lines name the file and the key.
- `concept_changed_check.py`: it computes the tree root it judges first, then calls `gate.bypass_env(root)` and `gate.pinned_contract(root)`. The edit gate and the changed-file check therefore read the switch file of the same tree, including at commit time outside any hook. A gate that does not accept the argument is called without it.
- `architecture-guard.py`, the three trackers, `integration-check.py`, `memory-pager.py`, `working-agreements.py` and `plan-question-advisor.py`: each off-check calls `switch(<key>)`.
- `_contract_index.py` stays standard-library-only and in the scripts folder. Its environment read is removed. It gains one entry point, `set_mode(value)`, bound by its callers with `getattr`. With no call, the mode is `on`, the old default. Its two callers, `concept-gate.py` and the add-on `bash-gate.py`, read `contract_index` through `_switches` and call `set_mode` once per process. So `_contract_index.py` never imports `_switches.py`.
- `.claude/addons/strict-shell-gate/addon.json`: the helper list gains `.claude/hooks/_switches.py` and `.claude/hooks/_error_log.py`, because `bash-gate.py` now reads a switch.
- `db-destructive-guard.py`: the Arm-write rule first, then Guard deference. "ALLOW path 2" becomes the arm-then-ask path. `_fail_closed` loses its override. The block text replaces the variable lines with how to arm, to run in the person's own terminal: PowerShell `New-Item -ItemType File -Force '<path>'` with any apostrophe in the path doubled, and POSIX `touch '<path>'` with any apostrophe written as `'\''`. `db-research-readonly-guard.py:342` uses the same claim and carries the same Arm-write rule.
- The ask output is the PreToolUse JSON `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": <the Plain-reason text>}}` on standard output, with exit 0.
- `auto_improve_finish_install.py`: the readiness field `switches` lists the Switch readings for the install's project. A vendored script folder without the hooks folder reports `unavailable`; `VENDORED_FILES` does not change, because the import is optional. `_scan_env_vars` stays for the add-on scan rows.
- `.gitignore`: `.claude/switches.local.json` and `.claude/database-override.*`.
- This repository commits `.claude/switches.json` with every key at its default and a `$comment` naming the local file. The README shows the whole file; a person edits it in an editor, so no shell command with nested quotes is ever needed.
- Plugin mirror: not applicable. This repository is the plugin; no copy exists under `.claude/skills` or `.claude/agents` (finding V18 of `.claude/concepts/2026-11-11-audit-followups-165.md`). What ships is `hooks.json`, the add-on manifest, the README helper lists and the version raise at the landing. The final review block checks this criterion.

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---|---|---|---|---|
| Claude Code (host) | the two database guards | PreToolUse payload | `permission_mode`, `tool_use_id` (read; ASSUMED present) | host → hook |
| the two database guards | Claude Code (host) | PreToolUse standard output | `permissionDecision: "ask"` JSON | hook → host |
| the concept gate and the architecture guard | Claude Code (host) | hook standard output | `systemMessage` JSON (ASSUMED shown to the person) | hook → host |

No API endpoint, real-time event or data-transfer object is touched. This repository has no `INTEGRATION.md`.

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold.

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

## Chat Tool Impact

No — this contract adds no REST endpoint and no real-time event, so there is nothing a chat tool could wrap.

## Non-Goals

- No new guard and no new switch: the nine keys replace existing variables one for one.
- No user-wide switch file in the home folder.
- No refusal of an agent's edit of `switches.json` (user answer below).
- The user's private global `CLAUDE.md`. The landing pull request body lists its stale lines: the "Override" paragraph of "Destructive Database Operations", `CLAUDE_SKIP_CG` under CodeGraph, and `CLAUDE_ACTIVE_CONTRACT` and `CLAUDE_CONCEPT_GATE=off` under "Escape hatches".
- Database tools reached through an MCP (Model Context Protocol) server, which no guard sees today.
- A stale vendored database guard in a consuming project still reads the old variable until that project re-vendors.
- README "Change notes by version" and dated registry history keep their old text.
- Naming the `sqlcmd -Q` target in the prompt reason (security review W5) and dropping `"` and `;` in the neutraliser (N2): a follow-up (user answer 2026-11-18, Open Question "Prompt target for sqlcmd").
- A change to `_shell_write_targets.parse_redirect_targets`: the W2 fix is made inside the Arm-write rule, so the add-on and every other caller of the shared parser are unchanged.

## Confidence

Confidence: Medium. High on the inventory (every read found by search and opened). The live trial (t3) proved the prompt in `default` mode, the block in `bypassPermissions` and headless runs, and the `systemMessage` notice. Medium on the rest of the host behaviour. The second live trial (t9, step 6) answered the allow-rule question for one rule in one settings layer. The `acceptEdits`, `plan` and `dontAsk` modes stay ASSUMED: t9 steps 7 to 9 were not run (amendment 2; Open Question "Third live trial").

## Alternatives Considered & Why Rejected

- **Chosen:** two JSON files, one helper, and an arm that leads to a permission prompt.
  - Why: one place to look; a personal override needs no commit; an arm an agent wrote still needs an answer at a prompt.
- **Delete every switch, as issue 119 did.** Rejected: issue 119 deleted the add-on switches because each add-on has an uninstall skill. A default hook has none. Without a switch, the only per-hook way out is disabling the whole plugin. Deletion is kept for the two skill-text variables that already have another way out.
- **Per-hook rules files.** Rejected: see New Mechanisms.
- **Slots in the Project profile.** Rejected: see New Mechanisms (project facts only, no local-only slot, no personal file, markdown parsing in every hook).
- **Keys in `.claude/settings.json`.** Rejected: the host owns that file and may reject unknown keys; its `env` block is environment variables again.
- **The runtime configuration table (`SystemConfigEntity`, `MECHANISMS.md:41`).** Rejected: it lives in a database behind an application; hooks have neither.
- **The brief's one-shot grant file.** Rejected: a write the guard cannot see (an encoded command, a script written earlier) would run a destructive command with nobody answering anything.
- **Always ask, with no arm.** Rejected: it drops "blocked by default", and every blocked command would become a prompt with no step outside the agent's normal tools. With the arm, a repeated prompt needs a deliberate write the guard did not see, and each claim is logged.
- **No override at all.** Kept only as the route when no prompt can be shown, or for a class that never prompts.

## Uncertain Assumptions

- `VERIFIED live via the t3 run sheet (pull request 438, verdict pass-with-findings)`: the payload carries `permission_mode`; in `default` mode the guard's `ask` shows a prompt and declining leaves no arm; `bypassPermissions` blocks; a headless run reports mode `auto` and blocks; `systemMessage` is shown to the person once per session when `concept_gate` is off.
- `ASSUMED`: the payload carries `tool_use_id`, and a block beats an ask when both guards answer one call. Neither was observed live; both rest on the documentation quoted in the helper block's pull request 432 and on the unit rows. If wrong, the second guard blocks a call the first guard asked about, which fails closed. Amendment 2: "a block beats an ask" also carries the L1 acceptance. If an ask could win over the destructive guard's human-only block, the read-only guard's ask would make that call promptable (Failure Modes, L1).
- `ASSUMED`: a prompt can also be answered by code the person configured: a headless run's permission-prompt tool, an SDK permission callback, or a `PermissionRequest` hook. The guard cannot tell. Verification path: none; stated as residual risk and in the README.
- `OBSERVED live, limited, not verified to block 9's own standard (t9 step 6, pass-with-findings; amendment 2)`: a `permissions.allow` rule that matches the command did not turn a hook's `ask` into an allow. The session's start time was never recorded; it was inferred from a session id that differed from the one before the save. Block 9's step 6 says the Observed line must show the session started after the save, "otherwise the step is void and is run again", so by the letter of that rule the step is void. The person who ran it and the re-review (t10) accepted the inference, and the user decided on 2026-11-19 against a further live trial, so the contract does not withdraw the override on this point; it names the gap as a residual (the residual-risk paragraph). Observed for one rule, `PowerShell(sqlcmd:*)`, in the project's `.claude/settings.local.json`, in `default` mode, on Claude Code 2.1.327, with the installed plugin disabled and the branch's hooks loaded through `--plugin-dir` (t9 item 1). Not proven: a `Bash(...)` rule, a user-level or managed settings rule, another host version. If a later host lets an allow rule win, an agent can approve its own armed command with no prompt, and the user's direction is to withdraw the override (user answer 2026-11-18). Before amendment 2 this bullet read `ASSUMED`, verification path "the second live trial block, step 6".
- `ASSUMED`: in `acceptEdits` and `plan` mode the host shows the guard's `ask` as a prompt, and in `dontAsk` mode the guard's block holds. The first trial ran only `default`, `bypassPermissions` and headless `auto`. The verification path was the second live trial block, steps 7 to 9; the owner closed that trial after step 6 (2026-11-18), so they rest on the unit rows and the auditor's offline probes (t10 O2, O3, O5). The code fails closed in `dontAsk`, and the two prompt modes' designed outcome is a prompt. A missing mode cannot be produced from a normal session; it stays covered by the unit suite only.
- `ASSUMED` (amendment 3): PowerShell 7 quotes the same way as Windows PowerShell 5.1 for the backslash and the backtick. t12 ran its PowerShell shapes in 5.1 only (`pwsh` is not installed on the auditor's host). The union of readings in the No-prompt classes rule does not depend on it, because it never picks one shell. Also `ASSUMED`: a hook that times out lets the call proceed (W4, I1, I2); this rests on the documentation quoted in pull request 432 and on t3 and t9, not on a live trial, and the Broken-file and Audit-log rules are designed so no read or write waits either way.
- `ASSUMED`: hook rows are read once, at session start, so a `PermissionRequest` hook an agent adds to `settings.json` acts only from the next session (`auto_improve_finish_install.py`, `NEW_SESSION_NOTE`).
- `ASSUMED`: the cross-area scan was not run (the architect has no shell). `.claude/area-mapping.json` declares `"areas": {}`, so it can score nothing. The main session runs it before approval.
- `VERIFIED via search, 2026-11-16`: the inventory above, including `CLAUDE_PLAN_QUESTION_ADVISOR` and two skill-only variables no code reads.
- `VERIFIED via .claude/hooks/_project_paths.py:51-59`: `project_dir()` returns none when `CLAUDE_PROJECT_DIR` is unset.
- `VERIFIED via .claude/scripts/_contract_index.py:1-119`: standard library only; empty means on; unknown means off with a warning.
- `VERIFIED via .claude/hooks/db-destructive-guard.py:1789-1822`: byte order mark strip, deference at `:1812`, then prose masking for shell tools at `:1822`.
- `VERIFIED via .claude/scripts/concept_changed_check.py:469-473,520-522`: the check judges the tree under the payload's `cwd` or the working directory.
- `VERIFIED via .claude/addons/strict-shell-gate/addon.json`: helpers are `_project_paths.py`, `_shell_write_targets.py` and `_contract_index.py`.
- `VERIFIED via .claude/hooks/hooks.json:84-144`: the destructive guard runs on the edit group, Bash and PowerShell; the read-only guard on Bash and PowerShell.

## Failure Modes & Mitigations

- **FM:** a person's local file in the main checkout leaks into test runs.
  - **Mitigation:** suites use temporary projects; helper rows prove the fallback applies only to a linked worktree with nothing at its own path, with a decoy planted in each other location.
- **FM:** the plugin's own `switches.json` is read for a consumer.
  - **Mitigation:** the Project-folder rule (the 2026-10-15 and 2026-10-16 locator lessons).
- **FM:** the edit gate and the changed-file check read different trees.
  - **Mitigation:** the changed-file check passes the root it judges.
- **FM:** an agent writes `concept_gate: off` during a session. Unlike an environment variable, the file takes effect on the next call.
  - **Mitigation:** the person accepted this trust level (Agent edits of the switch file, below). The Visible-off rule shows the person a `systemMessage`. The answer was re-confirmed with that notice (Open Question "Re-confirm agent edits", answered).
- **FM:** an agent creates the arm by a route the guard does not see.
  - **Mitigation:** the Prompt-only rule; the claim is used once and logged.
- **FM:** the two database guards race on one arm.
  - **Mitigation:** the Shared-claim rule.
- **FM:** a committed arm file gets a fresh time on clone.
  - **Mitigation:** the `.gitignore` entries; it still yields only a prompt.
- **FM:** the prompt text misleads the person.
  - **Mitigation:** the Plain-reason rule.
- **FM:** a file saved by Windows PowerShell 5.1 is ignored.
  - **Mitigation:** the Encoding rule.
- **FM:** sandbox tests that copy helper lists omit `_switches.py`.
  - **Mitigation:** the off rows go RED, so the omission shows.
- **FM:** a vendored finish-install folder lacks the helper.
  - **Mitigation:** fail-soft `unavailable`; the final review block runs `test_check_hook_registrations.py`.
- **FM (security review B1):** a human-only command joined in one tool call to another blocked operation became a prompt.
  - **Mitigation:** the amended No-prompt classes rule; the fixes block adds the three armed rows (O12, O13, O14 of the review).
- **FM (security review W1):** a Write to `<arm>/.` or `<arm>/x/..` created the arm unseen.
  - **Mitigation:** the amended Arm-write rule normalises the path first; the fixes block adds rows.
- **FM (security review W2):** a redirection after `git commit` to a quoted arm path was masked as prose.
  - **Mitigation:** the amended Arm-write rule; the change is scoped to that rule, because the prose masker is shared with destructive-command detection (the 2026-11-05 shared-classifier lesson).
- **FM (the W2 fix drawn too wide):** treating every redirected or piped `git` segment as non-prose would refuse the common `git commit -m "…" 2>&1 | tail`, including this contract's own deliveries whose messages name the arm.
  - **Mitigation:** only a real output redirection to a named file counts; stream duplication and pipes do not. Control rows in the fixes block. A commit whose message names the arm AND redirects to some other file is still refused; that false refusal is accepted, and the way out is to drop the redirection.
- **FM (security review W4):** a named pipe at a switch-file path hung every switch read on POSIX, so the hook timed out and the guard stopped enforcing with no notice.
  - **Mitigation:** the amended Broken-file rule: a non-blocking open and a kind check on the open file on POSIX; on Windows, a link to a network target is judged from the drive table and never opened. The fixes block adds a POSIX-only row and a Windows-only row. *Amendment 2: cleared on POSIX only (t10). See the next entry for Windows.*
- **FM (re-review W4, Windows):** a symbolic link at `switches.local.json` to a Windows named pipe (`\\.\pipe\<name>`, or the `\\?\` spelling) hangs every switch read. `_network_link_reason` read the pipe target as a local relative path, and the kind check ran on POSIX only. ~~Symbolic links need no elevation on the auditor's host.~~ *(corrected, amendment 3, t12 finding N5)* On the auditor's host a file link is created without elevation by Python's `os.symlink` and by `cmd /c mklink`; PowerShell `New-Item -ItemType SymbolicLink` refuses ("Administrator privilege required"). Both spellings are stored as `\\?\pipe\<name>`, so the open-then-`fstat` check, not the `\\.\` branch of the link-target check, is what covers them. The concept gate and the architecture guard then time out with no Visible-off notice. The database guards do not read switch files, so the override is unaffected.
  - **Mitigation:** the Broken-file rule as amended again: open, then `fstat`, regular file only, on every platform; a device-namespace link target is unreadable and never opened. Block 11 adds a Windows pipe-link row, skipped with a stated reason where a link cannot be created. *Amendment 3: cleared on Windows (t12, a real attempt with a listening pipe, links made by `os.symlink` and `mklink` in both spellings, and a directory link at `.claude`).*
- **FM (re-review B1, not cleared by block 8):** a human-only script after any quoted text in the same call (`<row delete on a protected database> ; <script>`, or the removal of a non-disposable database through `sqlcmd -Q`, then the script, in bash or PowerShell) still claims the arm and prompts. Root cause: `_in_command_position` strips from the closing quote of an earlier quoted span, so the script reads as "mentioned". Block 8's decision fix was right; its rows all put the script first, the one order that works, so the suite was green.
  - **Mitigation:** the No-prompt classes rule's invoked-or-mentioned sentence; block 11 fixes the classifier, not the decision, and copies every failing probe of t4 and t10 in the reporter's exact clause order, in bash and PowerShell. *Amendment 3: achieved for every reported t4 and t10 probe and the quoted launchers (t12), not achieved for the escape spellings in the t12 entry below.*
- **FM (re-review P1, older than this contract, same root cause):** with **no arm**, the same shapes (`echo "start" ; <script>`, `cd "<p>" && <script>`, PowerShell `Write-Host 'x'; <script>`, `echo "a" && <restore script with its recover flag>`) are allowed with no prompt. Reproduced at `cd8eb51`, before this contract. It is the 2026-05-06 incident class: an agent runs the "never by an agent" class with nobody answering anything.
  - **Mitigation:** the same classifier fix in block 11, with unarmed rows that expect a block. It gets its own change note in the documents block, because it is not caused by this contract. *Amendment 3: achieved for H1 to H5 (t12), not achieved for the nine escape spellings in the t12 entry below.*
- **FM (re-review I1, older than this contract):** a link at `<project>/.claude/hooks/db-destructive-guard.rules.json` to a named pipe hangs the destructive guard at import (plain `open()`), so the hook times out before any rule runs. The read-only guard reads the same file the same way (`db-research-readonly-guard.py:207`). If the host treats a timed-out hook as not blocking, the destructive command runs with no prompt and no arm.
  - **Mitigation (user answer 2026-11-19: include I1 in block 11):** block 11 reads the rules file in both guards through the regular-file check; a file that fails it takes the existing fail-closed path. Other hooks' rules files (the architecture guard and others) read with a plain `open()` are the same class and are out of this contract's scope; block 12 lists them as information. *Amendment 3: cleared for both guards (t12, a real attempt with the helper present, deleted and stale). The neighbours t12 listed are accepted and out of scope, as the same class with no pipe link tried against them: `architecture-guard.py` (`architecture-guard.rules.json`, `<project>/.app-rules.json`, `architecture-guard.exceptions.json`), `integration-check.py` (`integration-check.rules.json`), `working-agreements.py` (`working-agreements.rules.json`, in the plugin folder) and `protected-names-warning.py` (`_read_small`). `_protected_names.py` checks `is_file()` before reading, so a pipe fails that check instead of hanging.*
- **FM (the I1 fix, a new false block, accepted):** a rules file that is a link to a network drive or a `\\server\share` file loads today; after block 11 it counts as unreadable, so the destructive guard protects every database and the read-only guard withdraws the disposable exemption.
  - **Disposition:** accepted fail-closed behaviour, because a link to a network target is exactly the hang route the drive-letter lesson names. The block text and the documents block's change note tell the person to keep the rules file as a regular file in the project folder. Block 11 has a row for it.
- **FM (re-review L1, accepted as a design choice; user answer 2026-11-19: accept and record):** in `<script> && sqlcmd -d <db> -Q "<row delete>"`, armed, the read-only guard (which has no human-only class) claims the arm and asks, while the destructive guard blocks as human-only. The person's arm is used up by a call that cannot run. ~~The same holds for the reported orders O13, O13e and H7: block 11's read-only guard rows pin that it asks and claims the arm there, and that it allows the shapes with no database statement.~~ *(corrected, amendment 3, t12 finding W6 (d))* The same holds for H7, and for O13 and O13e only in the suite's spelling (`sqlcmd -S "(localdb)\m" -E -d <protected> …`): block 11's read-only guard rows pin that it asks and claims the arm there. On t4's literal O13 and O13e (no `-S`) the read-only guard allows and keeps the arm, which is a closed outcome, because the destructive guard blocks. It allows the shapes with no database statement. The same also holds for t12's N2a, K1 to K3 and K4 to K6: armed, both guards ask today; after block 13 the destructive guard blocks them while the read-only guard still asks. On N1a and N1b the read-only guard allows and keeps the arm (t12).
  - **Why accepted, not fixed:** the arm is one-shot and only ever yields a prompt, and fixing it means the read-only guard imports the destructive guard's human-only classifier, a new cross-guard dependency with its own fallback rows. It fails closed **only if** a hook block beats a hook ask when both guards answer one call, which is still ASSUMED (Uncertain Assumptions; the documentation quoted in pull request 432 gives "deny > defer > ask > allow", but no live trial observed it). If that assumption is wrong, the read-only guard's ask would make a human-only call promptable, the B1 class; block 12 states which way the evidence stands (t12: documentation only, no live observation), and block 14 states it again. No block text tells the person to re-arm; the destructive guard's human-only text tells them to run the command by hand. ~~The block text tells the person to re-arm.~~ *(removed, third critique round W5: no code or block writes that text)*
- **FM (t12 B1, round three, and t12 P1, older than this contract, same root cause):** the quote scanner `_starts_a_command` reads quotes with one escape model for both shells. A trailing backslash before a closing quote (PowerShell `cd "<folder>\"; <script>`, `Set-Location "C:\work\"; <script>`, `Write-Host "C:\work\"; <script>`; bash `cd "C:\\work\\" && <script>`, `echo "a\\" ; <script>`), an escaped quote outside quotes (bash `echo \" ; <script>`, PowerShell `` Write-Host `" ; <script> ``), a doubled backtick before a quote (PowerShell ``` Write-Host "a``"; <script> ```) and bash `$'a\'b'` each read as "still inside a quote". Armed, after a blocked command, both guards ask (B1); with no arm the script runs with no prompt (P1, the 2026-05-06 incident class). t12 ran every shape in a real shell with a harmless probe script, and the trailing command ran each time.
  - **Mitigation:** the No-prompt classes rule's union of readings (bash, PowerShell, quote-blind, plus the old readings); block 13 changes the classifier only and copies t12's armed rows N1a, N1b, N2a, K4 to K6 and unarmed rows N1, N1c, N2, N2b, N3 to N6, N15 in t12's exact spelling, each failing at the parent tip. The P1 shapes get a line in the documents block's change note.
- **FM (the union of readings, a new false block, accepted):** reading the text as both shells can class as invoked a script name that one shell would treat as a mention, for example a PowerShell argument wrapped in backticks, which the bash reading takes as a substitution, or a name after a doubled quote that one shell closes and the other does not.
  - **Disposition:** accepted fail-closed behaviour for new shapes no existing row covers: the result is a block naming the human-only script, and the person runs it by hand, which is what the user decided for this class. Mentions inside commit messages, `echo` text, search patterns and pull request bodies are blanked by the prose masker before the classifier runs. If any existing row (the mention and launcher controls, a block 11 row, or a row of the existing suites other than a named P1/P2-pinning row) flips, block 13 stops and reports an AMENDMENT; no reading is dropped to make it pass. `command -v` and `command -V` are a named mention, not a false block.
- **FM (t12 P2, older than this contract, outside the rule's literal definition before amendment 3):** a script after `then`, `do`, `else`, `!`, `time`, `env`, `nohup`, `exec`, `command`, `sudo` and similar words, or inside backticks, counts as mentioned. With no arm it runs with no prompt; armed after a blocked command, both guards ask (t12 N7 to N13, K1 to K3).
  - **Mitigation (user answer 2026-11-20: included in block 13):** the No-prompt classes rule's command-start words, with valued options skipped; block 13 adds t12's rows N7 to N13 and K1 to K3, one row per remaining word, and one row per valued option (`nice -n 10`, `sudo -u root`, `env -u NAME`, `timeout -s KILL 5`), plus `command -v` and `command -V` as allowed mentions.
- **FM (t12 I2, older than this contract, same class as I1, in both database guards):** a link at `<project>/.claude/logs/db-guard.log` to a named pipe that accepts and never reads hangs the destructive guard on its block path, because `_audit` appends with a plain open. t12 saw no result within 20 seconds, before this contract and at head. The read-only guard has the same code for `<project>/.claude/logs/db-research.log` (`db-research-readonly-guard.py:95-98`, `_audit` at `:350-364`, on its block path); t12 linked only `db-guard.log`, so the read-only guard's 0.13 s result there does not clear it. The same `_audit` also follows links in its folder creation, its existence and size checks, and its rotation (`db-destructive-guard.py:785-791`, `db-research-readonly-guard.py:352-358`), so a linked folder or a linked log over the size limit could make it rename or write through a target it did not choose. If the host lets a timed-out hook's call proceed (ASSUMED), the destructive command runs with no prompt and no arm.
  - **Mitigation (user answer 2026-11-20: included in block 13, extended to both guards):** the Audit-log rule over the whole audit path; block 13 adds, per guard, real Windows pipe-link rows in both spellings, folder-link rows, linked-log and linked-`.1` rotation rows, a POSIX named-pipe row, and regular-log, missing-log and normal-rotation controls.
- **FM (the I2 fix skips an audit record):** a log, or a log folder, that is a link or not a regular file (folder) loses that call's audit record; a project whose `.claude` or `.claude/logs` is deliberately a link or junction gets no audit record at all.
  - **Disposition:** accepted. The decision is unchanged, and one line goes to standard error on every skipped record. The way out is a real `.claude/logs` folder and a regular log file in the project. On Windows, which has no flag to refuse a link at open, a link swapped in between the check and the open is still caught by the `fstat` check for a pipe or device; a swap to a link whose target stalls in the open itself (a disconnected network file) is a narrow race, named here as residual.
- **Information, accepted and out of scope (amendment 3).** t12 N6: the restore script's recover flag is matched as text after the script name, so `F=--recover-missing-dev-db; <restore script> $F` is allowed with no arm (t12 N14). It is the same text-guard limit as the arm-write residual rows S10 to S14 and predates this contract. t12 N5 (how links are created on the auditor's host) is applied to the W4 (Windows) entry above. Note on names: t12's finding ids N5 and N6 are not its probe shapes N5 and N6, and t4's shared-claim probes P1 to P9 are not finding P1; this contract keeps each report's own naming and says which one it means.
- **FM (t9 steps 7 to 9 not run):** `acceptEdits`, `plan` and `dontAsk` were never run live.
  - **Disposition (user answer 2026-11-19: no third live trial):** a named residual. Each fails closed in code except the two prompt modes, whose designed outcome is a prompt; the unit rows and the auditor's offline probes cover them. No third trial block is added.
- **FM (security review N1):** an arm dated in the future stayed fresh for ever.
  - **Mitigation:** the amended Fresh-arm rule; the fixes block adds rows.
- **Security review W5, N2 and N3, not fixed here (user answer 2026-11-18, Open Question "Prompt target for sqlcmd").** W5 (the prompt shows the target as "unresolved" for `sqlcmd -Q`, also the live trial's finding W1) is a follow-up, decided: naming that target needs a change to the guard's target binder, which is outside the review's fixes, and the host's own prompt shows the full command. N2 (the neutraliser keeps `"` and `;`) is accepted, decided: no command form the auditor tried delivered a quote-forged target, and it joins the W5 follow-up, which reworks the same reason text. N3 (the read-only guard fails open on an internal error) is accepted, decided: it predates this contract, and the destructive guard beside it fails closed and refuses the same arm writes (probe P9).

**Residual risk of the database override, in one place.** An agent can still create the arm through a route no hook sees, or ask the person to approve. The arm is not tied to a command: whichever blocked command comes next uses it up, so the agent chooses which command a person's arm is spent on. A person who armed for one command can be shown another, and for the common `sqlcmd -Q` form the prompt reason names the target only as "unresolved", so the host's own display of the full command is the only place the person sees what will run. A prompt may be answered by code the person configured (a permission-prompt tool, an SDK callback, a `PermissionRequest` hook); then the override is only as careful as that code. ~~Whether a `permissions.allow` rule, which an agent can write, can turn the guard's `ask` into an allow is not yet proven; the second live trial block tests it (required before the re-review, user answer 2026-11-18).~~ *(amendment 2: answered by t9 step 6)* A `permissions.allow` rule, which an agent can write, did not turn the guard's `ask` into an allow in the second live trial (t9 step 6). That proof is narrow: one rule (`PowerShell(sqlcmd:*)`), one settings layer (the project's `settings.local.json`), `default` mode, Claude Code 2.1.327, and the branch's guard tested with the installed plugin disabled (t9 item 1). A `Bash(...)` rule, user-level or managed settings, and later host versions are untested, and the trial session's start time was inferred, not recorded, which block 9's own rule calls a void step. If an allow rule ever wins, the override is withdrawn: every destructive command then blocks and the person runs it in their own terminal (user answer 2026-11-18; refusing writes to the settings files was rejected). The withdrawal needs a further amendment, which this decision directs. While an older installed copy of the plugin is also active, its guard knows no arm and blocks, so the person sees a block, not a prompt; that fails closed. ~~Until block 11 merges: an armed call that puts a human-only script after quoted text gets a prompt for it (re-review B1); with no arm at all, such a call runs the human-only script with no prompt (re-review P1, older than this contract); a symbolic link at a switch-file path to a Windows named pipe silently stops the concept gate and the architecture guard (re-review W4); and a pipe link at the database guards' rules file can time out the guards themselves (re-review I1, in block 11 by the user's answer of 2026-11-19). After block 11, …~~ *(amendment 3, t12 finding W6 (a) to (c): block 11 merged, as `d43a285`, and closed fewer classes than this sentence said)* Block 11 closed, verified by t12 with real pipe-link attempts: the Windows pipe link at a switch-file path (W4) and at the database guards' rules file (I1); it also closed every reported t4 and t10 placement probe. Until block 13 merges: an armed call that puts a human-only script after a quoted span the guard misreads (a trailing backslash before the closing quote, an escaped quote outside quotes, in bash or PowerShell) gets a prompt for it (t12 B1); with no arm, those shapes run the human-only script with no prompt (t12 P1, older than this contract); a script after a shell keyword or prefix command (`then`, `do`, `else`, `!`, `time`, `env`, `nohup`, `exec`, `command`, `sudo` and similar) or inside backticks counts as mentioned, armed or not (t12 P2, older than this contract; in block 13 by the user's answer of 2026-11-20); and a pipe link at either database guard's audit log (`.claude/logs/db-guard.log` for the destructive guard, `.claude/logs/db-research.log` for the read-only guard) hangs that guard on its block path, and a linked log folder or a linked log over the size limit makes its rotation act through the link (t12 I2, older than this contract; in block 13, extended to both guards, by the same answer). After block 13 the audit record is skipped for a linked or non-regular log or log folder, and a link swapped in on Windows between the check and the open to a target that stalls in the open itself remains a narrow race. The restore script's recover flag passed through a variable is not seen (t12 N6, accepted). Hooks other than the database guards that read a rules file with a plain open (the architecture guard, the integration check, the working agreements hook, the protected-names warning) can be hung the same way as I1 was (accepted, out of scope). After block 13, an armed call that joins a human-only script with a database write still spends the arm on the read-only guard's ask while the destructive guard blocks (L1, accepted; for t4's O13 and O13e only in the spelling with `-S`, because without it the read-only guard allows and keeps the arm), and that stays closed only while a hook block beats a hook ask (ASSUMED). `acceptEdits`, `plan` and `dontAsk` rest on the unit rows, not a live trial. A person who approves without reading is the remaining hole. Sessions with no prompt get no override; the person runs the command in their own terminal.

## Open Questions for User

- [x] **Switch home.** Keep `.claude/switches.json` plus `.claude/switches.local.json`? **User answer (2026-11-16):** keep both; reject the Project profile, with the reasons written into New Mechanisms and Alternatives.
- [x] **Override mechanism.** **User answer (2026-11-16):** arm file plus permission prompt.
- [x] **Arm lifetime.** **User answer (2026-11-16):** 15 minutes.
- [x] **Human-only commands and guard errors.** **User answer (2026-11-16):** never prompt for them; the person runs them by hand.
- [x] **Agent edits of the switch file.** **User answer (2026-11-16):** agents are not blocked from editing `switches.json`.
- [x] **Worktree personal file.** **User answer (2026-11-16):** a worktree reads the main checkout's personal file when it has none.
- [x] **Where a pin may live.** **User answer (2026-11-16):** `pinned_contract` only in the personal file.
- [x] **Skill-only variables.** **User answer (2026-11-16):** delete `CLAUDE_CONTRACT_SKIP` and `CLAUDE_VERIFY_REVIEW_GATE`.
- [x] **Fault-injection variable.** **User answer (2026-11-16):** keep `DB_GUARD_FAULT_INJECTION` as a test-only environment variable.
- [x] **Report field name.** **User answer (2026-11-16):** rename `kill-switches` to `switches`.
- [x] **User-wide file.** **User answer (2026-11-16):** no user-wide file now.
- [x] **Re-confirm agent edits.** The earlier answer relied on "the same trust level as `settings.json`". The critic showed that is not exact: an environment variable could not change during a session, but one write to the switch file turns the concept gate off on the next call. The contract now shows the person a `systemMessage` each session a guard is off. **Recommend: keep the answer, with that notice.** **Answer taken (2026-11-16, resolved by the delivered work):** the recommendation. The contract was approved with this text and delivered on it; the notice was observed live in t3 step 4.
- [x] **Live prompt trial.** The live trial block needs you to run five short steps in a real Claude Code session and set the verdict line. **Recommend: yes.** The prompt route is the last safety control, and documentation alone does not prove host behaviour. **Answer taken (2026-11-16, resolved by the delivered work):** yes. A person ran the five steps and t3 merged as `pass-with-findings` (pull request 438).
- [x] **Second live trial before the re-review.** The security review asks whether an allow rule in your settings file can approve an armed command with no prompt, and the first trial never ran `acceptEdits`, `plan` or `dontAsk` mode. The second live trial block holds four more steps for you to run, and the re-review waits for it. **Recommend: yes, required before the re-review.** If an allow rule can skip the prompt, an agent could approve its own armed command, and the re-review cannot judge that from code. **User answer (2026-11-18):** yes, required; the re-review (block 10) depends on the second trial (block 9).
- [x] **If an allow rule skips the prompt.** Should the override then be withdrawn (every destructive command blocks, and you run it in your own terminal), or should the guard also refuse writes to the permission lists in the settings files? **Recommend: withdraw the override.** Refusing settings writes is a new guard rule with its own unseen routes, and blocking is the state the project had before the arm existed. Either answer needs a further amendment; this question only fixes the direction in advance. **User answer (2026-11-18):** withdraw the override; do not refuse writes to the settings files.
- [x] **Prompt target for sqlcmd.** The prompt names the database as "unresolved" for the usual `sqlcmd -Q` form (review W5, trial finding W1). Fix it in the fixes block now, or as a follow-up? **Recommend: follow-up.** It changes the guard's target binder, a larger change than the review's fixes, and the host's prompt already shows the full command. The main session opens the follow-up stub and its tracking issue. **User answer (2026-11-18):** follow-up, not in the fixes block; N2 stays accepted and folds into that follow-up; N3 is accepted.

**Amendment 2 (2026-11-19).** Already settled, not asked again: the override stays (step 6 was met, so the 2026-11-18 withdrawal direction is not triggered); W5, N2 and N3 keep their 2026-11-18 dispositions. Three decisions were yours, all answered on 2026-11-19:

- [x] **Rules-file pipe link.** A link at the database guards' rules file to a named pipe can hang both database guards before any rule runs (re-review I1). It is older than this contract. Fix it in block 11, by reading that file through the same regular-file check as the switch files? **Recommend: yes.** It is the same check block 11 writes for W4, a failed check takes the guards' existing fail-closed path, and the hang can let a destructive command through with no prompt. ~~If no, block 11 drops its I1 constraint and rows, and both guards' `.py` files keep only the B1 change.~~ *(third critique round NIT: the read-only guard carries no B1 change; moot after the answer)* **User answer (2026-11-19):** yes, include I1 in block 11; the read-only guard stays in block 11's file list for I1 only.
- [x] **Read-only guard spends an arm.** When a human-only script comes first and a row delete follows, the read-only guard uses up the person's arm on a prompt while the destructive guard blocks the call (re-review L1). Accept and record it, rather than fix it? **Recommend: accept.** ~~Nothing runs~~ *(corrected, third critique round W5)* Nothing runs provided a hook block beats a hook ask, which is still ASSUMED; the arm only ever yields a prompt, and the fix would make the read-only guard depend on the destructive guard's classifier. **User answer (2026-11-19):** accept and record it, with the precedence kept as ASSUMED and no claim that the block text tells the person to re-arm. Block 11's read-only guard rows only pin today's behaviour (user answer 2026-11-19 to the third-round BLOCKER: "Test the destructive guard alone").
- [x] **Third live trial.** Steps 7 to 9 of the second trial (`acceptEdits`, `plan`, `dontAsk` modes) were not run. Add a third person-run trial block for them? **Recommend: no; record the residual.** The code fails closed in `dontAsk`, a prompt is the designed outcome in the other two, the auditor's offline probes and the unit rows cover all three, and Failure Modes and the residual-risk paragraph name the gap. **User answer (2026-11-19):** no third live trial; record the steps 7 to 9 residual.

**Amendment 3 (2026-11-20).** Already settled, not asked again: B1 and P1 (round three) are fixed in block 13, as the No-prompt classes rule already requires; L1 stays accepted; W5, N2 and N3 keep their 2026-11-18 dispositions; no live trial is added. Two decisions were yours, both answered on 2026-11-20 ("take the recommended package"):

- [x] **Keyword and prefix-command starts.** A human-only script after `then`, `do`, `else`, `!`, `time`, `env`, `nohup`, `exec`, `command`, `sudo` (and the similar words the No-prompt classes rule lists), or inside backticks, counts as "mentioned" today, so with no arm it runs with no prompt (t12 P2). It is older than this contract and outside the rule's literal wording before amendment 3. Fix it in block 13?
  → Recommended: yes, include P2 in block 13. It is the same function and the same fix, with one extra row per word, and a guard that lets the human-only script run after `then` defeats the user's 2026-11-16 answer "never prompt for them; the person runs them by hand".
  **User answer (2026-11-20):** include P2 in block 13. The fourth critique round's WARN 5 is applied with it: valued options are skipped (`nice -n 10`, `sudo -u root`, `env -u NAME`, `timeout -s KILL 5`), and `command -v` / `command -V` are named mentions with an allowed row.
- [x] **Audit-log pipe link.** A link at the destructive guard's audit log (`.claude/logs/db-guard.log`) to a named pipe that never reads hangs that guard on its block path (t12 I2). It is older than this contract and the same class as I1, which you put in block 11. Fix it in block 13?
  → Recommended: yes, include I2 in block 13. The fix is small and local (refuse a link or a non-regular file before the append, check the open file before writing, skip the record on failure), the decision never depends on the record, and the hang is the same "timed-out hook" route I1 closed.
  **User answer (2026-11-20):** include I2 in block 13, extended to the read-only guard's `db-research.log`, which has the same plain-open `_audit` on its block path (fourth critique round BLOCKER). The Audit-log rule covers the whole audit path in both guards: folders, the log, rotation and the open (fourth critique round WARN 1).

---

## Critique

**Critic:** contract-critic
**Date:** 2026-11-16
**Verdict:** blockers-found

### Findings

- **[BLOCKER] The Project profile is an existing committed per-project settings file, already used as a switch, and is never weighed**
  - **What is wrong:** New Mechanisms and Alternatives reject rules files and `settings.json`, but not the Project profile, which the Memory adapter already uses as its "profile switch" (memory is off until a slot is set).
  - **Prior artifact ignored:** `MECHANISMS.md:69` (Project profile: "every project-shaped fact ... one named slot at a time"; "Never invent a local-only slot"); `MECHANISMS.md:122` (Memory adapter: "profile switch").
  - **Where in this contract:** `## New Mechanisms` — "Why an existing mechanism was not sufficient: a Guard rules file is one file per hook ..."
  → Addressed by: New Mechanisms and Alternatives now weigh the Project profile and reject it (project facts only, no local-only slot, no personal file, markdown parsing in every hook); user confirmed 2026-11-16.
- **[BLOCKER] `_contract_index.py` gains a dependency on the new helper, but the add-on helper list that vendors it is not updated**
  - **What is wrong:** `.claude/addons/strict-shell-gate/addon.json` lists `.claude/scripts/_contract_index.py` as a helper and does not list `_switches.py` or `_claude_paths.py`. It is not in any block's Files to touch. The contract also never says how `_contract_index.py`, which sits in the scripts folder, reaches `.claude/hooks/_switches.py`.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-09 — "A change that adds a module-level import to a vendored script must update the vendored-file list in the same change"; `MECHANISMS.md:113` (Add-on layout: the install "copies each named helper only when the project lacks it").
  - **Where in this contract:** `## Extension Points` — "`_contract_index._mode()`: reads `contract_index` once per process"; block 4 Files to touch.
  → Addressed by: `_contract_index.py` never imports the helper; its callers read the switch and call the new `set_mode`. `bash-gate.py` now reads a switch, so `addon.json` gains `_switches.py` and `_error_log.py`, in the ordinary switches block with its manifest tests.
- **[WARN] The text that the arm-file name test reads (D-5) is not stated, and both readings fail**
  - **What is wrong:** The destructive guard blanks quoted prose (commit messages, pull request bodies, grep patterns) before matching. Testing the raw text blocks every `git commit -m` / `gh pr create --body` / search that names `database-override.`, including this contract's own deliveries and block 3's probes. Testing the masked text can miss a quoted redirect target.
  - **Prior artifact ignored:** `.claude/hooks/db-destructive-guard.py:1820-1822` (item 7a masking); `JOURNAL.md` 2026-10-17 — "Loosening a guard rule must be checked against the guard's own test fixtures" (Apply when: "changes what a hook allows or blocks").
  - **Where in this contract:** `## Data Shapes` → D-5 — "command text (shell) contains `database-override.`".
  → Addressed by: the Arm-write rule reads the shell parser's write targets plus the masked text; the RED tests block adds allowed-mention and refused-write rows and runs the guard's existing fixtures.
- **[WARN] D-5 placement against Guard deference is unstated; only the destructive guard carries it**
  - **What is wrong:** Deference returns at `db-destructive-guard.py:1812`, before any rule. With a stale vendored project guard (a stated Non-Goal), the plugin copy defers and D-5 never runs, while the plugin's read-only guard still honours the arm.
  - **Prior artifact ignored:** `VOCABULARY.md:95` (Guard deference); `.claude/hooks/db-destructive-guard.py:1811-1813`.
  - **Where in this contract:** `## Data Shapes` → D-5 — "This check runs before every other rule".
  → Addressed by: the Arm-write rule runs before deference in both guards; a guard honours the arm only when it does not defer.
- **[WARN] The prompt can be answered by code, and the residual-risk paragraph and Alternative F's rejection do not account for it**
  - **What is wrong:** D-4 keys only on `permission_mode`. A headless run with a permission-prompt tool, a Software Development Kit (SDK) permission callback, or a `PermissionRequest` hook can approve an `ask` with no person. An agent can create the arm by routes nobody sees (the contract admits this), so it can request prompts again and again. That is the exact reason Alternative F was rejected. Verification is documentation-only, with no live trial.
  - **Prior artifact ignored:** work item brief acceptance criterion "An agent cannot grant it to itself by writing the file"; `JOURNAL.md` 2026-10-05 — "Count a host's size cap the way the host counts, and prove the cap with a real trial" (host behaviour proven only by trial); `VOCABULARY.md:140` ("The user's normal Claude Code permission prompts ... apply").
  - **Where in this contract:** `## Failure Modes & Mitigations` — "Residual risk ... Either way a person must approve that one prompt"; `## Alternatives` F — "lets an agent request prompts over and over".
  → Addressed by: the residual risk and Uncertain Assumptions now name code-answered prompts; the always-ask rejection is reworded; a new live trial block proves the host behaviour in a real session. The guard cannot detect a configured answerer, so that part stays a stated residual.
- **[WARN] The prompt reason echoes agent-written target text with no neutralising step**
  - **What is wrong:** `permissionDecisionReason` names "the targets", which come from the command the agent wrote. A crafted target such as `x /* disposable test copy */` can mislead the person at the one control left.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-05 — "Neutralise every field echoed from untrusted input, not only the body".
  - **Where in this contract:** `## Extension Points` — "`permissionDecisionReason`: <text naming the targets ...>".
  → Addressed by: the Plain-reason rule (fixed wording; targets neutralised, cut and labelled), with test rows.
- **[WARN] Agent-writable switch files lower the trust level of every guard switch, and the stated mitigation is inaccurate**
  - **What is wrong:** Today a hook reads its switch from the environment Claude Code started with, so an agent's shell cannot change it during a session. After this change, one `Write` of `.claude/switches.local.json` turns off the concept gate or the architecture guard on the very next call. The concept gate exempts every `.claude/` and `.json` path. A stderr line on exit 0 is not shown to the person.
  - **Prior artifact ignored:** `MECHANISMS.md:78` (main-checkout guard: "Never add an environment variable, flag or file that switches it off"); `JOURNAL.md` 2026-10-04 — "Check a documented guard behaviour against the guard's code".
  - **Where in this contract:** `## Failure Modes & Mitigations` — "the same trust level as today's agent-editable `settings.json`; the I-8 stderr line makes it visible"; I-8 Events row "Listeners: the person, through stderr".
  → Addressed by: the inaccurate claim is removed; the Visible-off rule adds a per-session `systemMessage` for a guard switched off; the open question "Re-confirm agent edits" asks the user again. The main-checkout guard still has no switch.
- **[WARN] The switch file is read from the project folder, but the changed-file check judges a different tree**
  - **What is wrong:** `concept_changed_check.py` judges the tree under `os.getcwd()` or the payload's `cwd` (`:469-473`, `:522`). Its `bypass_env()` would read `CLAUDE_PROJECT_DIR` only, and that is unset when the commit step runs outside a hook. So the commit check reads the defaults while the edit gate honours `concept_gate: off`. A relative `pinned_contract` resolves against the project folder, not the worktree that holds the contract.
  - **Prior artifact ignored:** `VOCABULARY.md:98` (Changed-file check: "the two can never disagree"); `JOURNAL.md` 2026-10-15 — "A script that reads a project-owned file must be told which project, not search for one".
  - **Where in this contract:** `## Data Shapes` → I-5 — "Unset project directory means defaults"; I-6.
  → Addressed by: `bypass_env` and `pinned_contract` take an explicit project; the changed-file check passes the tree root it judges, before any other step.
- **[WARN] The worktree fallback (I-6) is under-specified**
  - **What is wrong:** It does not say whether an empty, whitespace-only or malformed worktree local file counts as "its own" and so stops the fallback. It does not say whether I-2's "ignore both files" covers the main checkout's file. No test row plants a decoy in each other location.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-05 — "A documented 'missing file means the default' must read one named location only" (test the missing-file case "with a decoy in each other place").
  - **Where in this contract:** `## Data Shapes` → I-6 — "with no Local switch file of its own".
  → Addressed by: the Worktree rule (anything at the path stops the fallback; a broken main-checkout file falls under the Broken-file rule) and decoy rows in the RED tests block.
- **[WARN] The text encoding of the switch files is not declared, and the way a person writes one is not a one-line command**
  - **What is wrong:** Windows PowerShell 5.1 writes UTF-16 with `>` and a byte order mark (BOM) with `Set-Content -Encoding UTF8`. Under I-2 either one makes both files ignored. Writing a JSON value from a shell needs nested quotes.
  - **Prior artifact ignored:** `.claude/hooks/db-destructive-guard.py:1791` (the existing BOM strip); `.claude/agreements/one-line-commands-for-the-user.md` ("Never rely on nested quoting").
  - **Where in this contract:** `## Data Shapes` → Entities, Switch file row — "one JSON object of key → value".
  → Addressed by: the Encoding rule (UTF-8 byte order mark stripped, UTF-16 decoded) with rows; the README shows the whole file to edit in an editor, so no shell command is given for switches.
- **[WARN] Problem reporting (I-7) has silent paths**
  - **What is wrong:** An unreadable file is not in I-7's problem list, so a person's `off` is lost without a report. The order of the marker write and the log write is not fixed, so a marker written before a failed log write silences the problem for good.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-07 — "A fail-soft reader must not record 'seen' for what it could not read"; brief acceptance criterion "reported once".
  - **Where in this contract:** `## Data Shapes` → I-1 "unreadable ... means 'no settings'"; I-7.
  → Addressed by: unreadable moves to the Broken-file rule and the Report-once list; the log record is written first and the marker only after it succeeds.
- **[WARN] Hand-off command is reused outside its definition**
  - **What is wrong:** The term covers commands that "the cloud skill or the cloud agent writes out" and says "No new authorization mechanism exists". The database arm is a new authorization mechanism, written by a guard. No amendment is proposed.
  - **Prior artifact ignored:** `VOCABULARY.md:140`; `JOURNAL.md` 2026-10-28 — "A new term's definition must be true against every existing member".
  - **Where in this contract:** `## Data Shapes` → D-4 — "(a Hand-off command)"; `## Reused Mechanisms`.
  → Addressed by: the term is no longer reused; the Person-present rule says "run the command themselves, in their own terminal", and Business Concept says why the term does not apply.
- **[WARN] The environment-read scan cannot classify reads whose variable name is not a literal**
  - **What is wrong:** `_error_log.py:74` (`os.environ.get(key)`), `_project_paths.py:783` (a name taken from a match group) and `session_parent_base(os.environ, ...)` in the codegraph add-on have no literal name. An alias such as `e = os.environ; e.get(...)` slips past an `environ.get` / `environ[` / `getenv` pattern.
  - **Prior artifact ignored:** work item brief acceptance criterion ("checked by a test that scans ... for any remaining read of an own switch").
  - **Where in this contract:** block 1 — "Every name must be in the declared host, platform or test-only sets".
  → Addressed by: the scan parses the code with Python's `ast` module, fails any non-literal read, alias or hand-off of `os.environ` that is not on a named list of reviewed sites, and states its limit (`getattr(os, "environ")` and imports by text).
- **[WARN] One brief acceptance criterion has no home in any block**
  - **What is wrong:** "The plugin mirror is updated" is not mapped or declared not applicable, and block 6 checks "each acceptance criterion of the brief".
  - **Prior artifact ignored:** `.claude/work-items/2026-11-16-file-based-switches.md:35`.
  - **Where in this contract:** `## Implementation Handoff` → block 6.
  → Addressed by: Extension Points declares the mirror not applicable (finding V18; this repository is the plugin) and names what ships; the final review block checks it.
- **[WARN] A likely layout defect: no parent issue yet**
  - **What is wrong:** The brief has `id: none` and `issue_offer: pending`. The Delivery shape needs a parent issue, and `no-parent-issue` blocks approval and dispatch.
  - **Prior artifact ignored:** `VOCABULARY.md:75` (Layout defect).
  - **Where in this contract:** header — "It needs a parent issue, one sub-issue per block".
  → Deferred: the architect has no shell or tracker access. The header's `Parent issue` line makes it an approval precondition for the main session.
- **[WARN] The plain-language rule is broken throughout**
  - **What is wrong:** Bare-number labels (I-1 to I-9, D-1 to D-9, Q1 to Q10, "block 2"). Short forms never written out (JSON, SHA-256, POSIX, stdout, stderr). Jargon never explained ("atomic rename", "fail-soft", "dedupe marker", "payload").
  - **Prior artifact ignored:** `.claude/agreements/plain-language.md` ("Use a name, not a number"; "Write short forms out").
  - **Where in this contract:** `## Data Shapes`, `## Open Questions for User`.
  → Addressed by: rules, questions and blocks now have names; a "Short forms used below" paragraph explains each short form and term. The `### <n>.` heading numbers stay, because the sub-task loop derives identities from them.
- **[NIT] The inventory is complete for switch reads, but the "kept" list is loose** — a search of hooks, scripts, add-ons and skills found no switch read that the contract missed. The host class says "and others" and so hides `protected-names-warning.py:81`, `_gate_launch.py:60,75`, `_main_checkout_guard.py:820`, `cleanup_delivered.py:949`, `compose_subissue_title.py:109`, `codegraph_shadow_report.py:330`, `pr_merged.py:1171` and `angular-tailwind-advisor.py:113`, all of which the scan's allowed set must hold. `_error_log.py:73` is really `:74`.
- **[NIT] SystemConfigEntity (`MECHANISMS.md:41`), the Universal runtime kill-switch mechanism, is not dismissed in Alternatives** — it is database-backed and clearly unfit, but one line would close it.
- **[NIT] Re-exporting `_switches` through `_claude_paths.py` stretches that bridge** — its Extend-by covers locator functions in `_project_paths.py` (`MECHANISMS.md:46`).
- **[NIT] `contract_index` is cached once per process** — every other key is read at call time, so an in-process test that edits the file sees a stale value.
- **[NIT] Adjacent Areas is not the exact sanctioned single line** — it adds a clause and leaves an action for the main session.
- **[NIT] Chat Tool Impact reads "2. **No** — ..."** — not the sanctioned `No — UI/admin-only with justification` form. Harmless here, because the contract adds no endpoint.
- **[NIT] The printed arm command wraps the absolute path in single quotes** — a path containing an apostrophe breaks it.
- **[NIT] Contract budget** — with this critique the file likely exceeds its 12,000-token budget line.

### Applicable journal entries

- **2026-10-05 — A documented "missing file means the default" must read one named location only** — heeded by I-5. Partly not addressed for I-6, see WARN above.
- **2026-10-15 — A script that reads a project-owned file must be told which project** — heeded by I-5. Not addressed for the changed-file check, see WARN above.
- **2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file** — heeded by I-1 and I-5.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by the Inventory. The trust-level mitigation was not checked, see WARN above.
- **2026-10-05 — Never hide a forbidden name by hashing it** — heeded by block 1's planted `CLAUDE_MADE_UP_SWITCH`.
- **2026-10-05 — Neutralise every field echoed from untrusted input** — not addressed, see WARN above.
- **2026-10-05 — Do not add shared state to stop a duplicate** — heeded by D-9 (claim by rename, race stated).
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — not addressed for D-5, see WARN above.
- **2026-10-28 — A new term's definition must be true against every existing member** — heeded for Switch. Violated in spirit for Hand-off command, see WARN above.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded for the Guard rules file. The Project profile was missed, see BLOCKER above.
- **2026-11-02 — Name the tests a fix may change by the state they guard** — heeded by block 4's kept main-checkout row.

**Architect's note on the NITs (2026-11-16).** All eight are taken: the host list now names every site and `_error_log.py:74`; the runtime configuration table is dismissed in Alternatives; the bridge is not extended; `contract_index` is set once per process by its callers, and its tests run the gates as separate processes; Adjacent Areas and Chat Tool Impact use the sanctioned forms; the printed arm commands escape apostrophes; the budget is exceeded and recorded here, because the user needs this critique round beside the answers.

### Second round — 2026-11-18 (amendment: security-review remedy round 1)

**Critic:** contract-critic
**Date:** 2026-11-18
**Verdict:** warnings-only

Scope: the Revision line, blocks 8, 9 and 10, the re-linked Depends on lines of blocks 6 and 7, the rewritten No-prompt classes, Arm-write, Fresh-arm and Broken-file rules, the residual-risk paragraph and the new Open Questions, all checked against the t4 report and `.claude/scripts/pr_merged.py`.

**Verified, no finding:**
- `_parse_depends_on` (`pr_merged.py:284-291`) reads only the text before the first `—`: block 6 gives `[5, 10]`, block 7 gives `[5, 6, 10]`, block 8 gives `[2]`, block 9 gives `[2]` and block 10 gives `[8, 9]`. The trailing prose on 6, 7 and 8 does not leak a `4` into the list.
- `derive_subtask_id` (`:266-274`) gives `t8-security-review-fixes`, `t9-live-prompt-trial-second-round` and `t10-security-re-review`. The comma in block 9's heading and the unspaced hyphen in "re-review" survive the slug. The ids match the declared report file names. t1 to t7 keep their ids, so the recorded entries in `state.yaml` are not disturbed. `backfill_state` (`:785-813`) adds t8 to t10 with `base: None`, which `base_not_declared` refuses until `--record-subtask` stamps the parent branch.
- `compute_released` (`:588-633`) never consults supersession, so naming 4 would deadlock 6 and 7 on `review verdict: blocked`. The re-link through 10 is the only way through. 8 and 9 are releasable now, and 10 releases 6 and 7 only on `pass` or `pass-with-findings`.
- `read_review_set` (`:3715-3791`) matches `supersedes` by basename with the `.md` suffix, so `["t4-security-review-security-auditor.md"]` retires t4 at the completion check (`:4226-4241`). The `[]` rule for a blocked re-review is consistent with that reader.
- No block's Files to touch names a plugin version file. The `**Work Item Brief:**` header is present (Parent Branch Delivery Rule, static check only).
- The B1, W1 (path normalisation), N1 and W3 rewrites match the t4 findings and the fixes the review proposed.

### Findings

- **[WARN] The W2 fix is wider than the finding, and it will refuse ordinary piped or redirected commits that only mention the arm name**
  - **What is wrong:** The t4 fix asks that `_segment_is_prose` return False for git "when `redirected` is true". The amended Arm-write rule says "redirected **or piped**". Under `_mask_inert_prose` (`db-destructive-guard.py:1692-1719`) a `2>&1` sets `redirected` (any `>`), and `|` marks the segment piped. So `git commit -m "<text naming database-override.once>" 2>&1 | tail` loses its prose masking. The quoted message then matches the name test and is refused. This contract's own documents block will write commit messages about the arm. The control rows in block 8 test only mentions that are not piped or redirected, and no Failure Modes entry covers this new refusal path.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 — "Keep a review-fix block to the review's findings"; `JOURNAL.md` 2026-11-02 — "A revision that adds a path adds its failure modes"; `JOURNAL.md` 2026-10-17 — "Loosening a guard rule must be checked against the guard's own test fixtures" (Apply when: "changes what a hook allows or blocks"); t4 report W2 "Fix" line.
  - **Where in this contract:** `## Data Shapes` → Arm-write rule — "a `git` segment that is redirected or piped is not prose"; block 8 W2 — "Controls: a commit message, a pull request body and a search pattern that only mention the name stay allowed."
  - → Addressed by: the Arm-write rule now counts a `git` segment only when it has a real `>` or `>>` redirection to a named file; `2>&1` and plain pipes do not count, block 8 gains the piped-commit control row, and Failure Modes has an entry for the one accepted false refusal. User answer 2026-11-18: accept all.
- **[WARN] The second live trial's allow-rule step can produce a false pass, because the rule is added mid-session**
  - **What is wrong:** Step 6 adds the allow rule to `.claude/settings.local.json` "by hand, in an editor", then asks Claude to run the command. It never says whether a new session starts first. The contract already assumes the host reads hook rows once at session start. If permission rules load the same way, "the prompt still appears" proves only that the rule was not loaded, not that a hook `ask` beats an allow rule. The re-review's blocker decision for W3(b) rests on this one step. An agent's realistic route is also a write before the next session.
  - **Prior artifact ignored:** this contract's `## Uncertain Assumptions` — "hook rows are read once, at session start"; `JOURNAL.md` 2026-10-05 — "Count a host's size cap the way the host counts, and prove the cap with a real trial"; `JOURNAL.md` 2026-11-07 — "A failed tool call is a different hook event ..." (Apply when: a condition is defined "without a live trial having recorded the real" behaviour).
  - **Where in this contract:** block 9 — "(6) By hand, in an editor, add to .claude/settings.local.json an allow rule ... arm from the person's own terminal, and in default mode ask Claude to run the statement".
  - → Addressed by: block 9 step 6 now requires closing every session, saving the rule, recording its save time, then starting a NEW session and recording its start time; a session not started after the save voids the step. User answer 2026-11-18: accept all.
- **[WARN] The Broken-file rule's no-hang guarantee covers named pipes only; the timeout class W4 describes stays open through followed links**
  - **What is wrong:** W4's impact is "a hook timeout is not a block, so the edit goes through with no Visible-off notice". The amended rule stats "once links are followed" and then opens. A switch-file link whose target is a disconnected mapped drive or a hung network mount blocks in `stat` the same way. A swap between `stat` and `open` reopens the pipe case too, which is why the review offered `O_NONBLOCK` plus `fstat` as the alternative. The rule's wording "so no read can wait on a named pipe and time the hook out" is true only for the narrow case.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-06 — "Judge a drive letter with a no-I/O check before any realpath, because realpath of a mapped drive can block" (Apply when: "any opening call on a path whose drive letter may be a mapped network drive, inside a hook with a timeout"); t4 report W4 "Alternatively, open with `O_NONBLOCK` and check `fstat`".
  - **Where in this contract:** `## Data Shapes` → Broken-file rule — "The kind of file is checked before the file is opened, so no read can wait on a named pipe and time the hook out"; block 8 W4 — "stat the path following links and require a regular file before opening".
  - → Addressed by: on POSIX the file is opened non-blocking and its kind checked on the open file; on Windows a link to a network drive or share is judged from the local drive table without touching the network and counts as unreadable. The timeout is not relied on, because a timed-out hook counts as an allow. User answer 2026-11-18: accept all.
- **[WARN] The open questions on W5, N2 and an allow-rule win are already written into the body as decided**
  - **What is wrong:** The question "Prompt target for sqlcmd" is unanswered, yet Failure Modes says "W5 ... is a follow-up" and "N2 ... is accepted ... it joins the W5 follow-up". Non-Goals says the same N2 change is a follow-up "if the user agrees". The question "If an allow rule skips the prompt" is unanswered, yet the residual-risk paragraph says "if the allow rule wins, the re-review blocks and the override is withdrawn". N3's acceptance has no question at all. No follow-up stub exists under `.claude/concepts/followups/` for W5.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 — "Edit a reversed sentence where it stands"; `JOURNAL.md` 2026-10-22 — "An accepted critic WARN or answered Open Question must amend the contract body before approval" (the reverse case: the body records an answer the user has not given).
  - **Where in this contract:** `## Failure Modes & Mitigations` — "Security review W5, N2 and N3, not fixed here"; the residual-risk paragraph — "the override is withdrawn"; `## Non-Goals` — "a follow-up, if the user agrees".
  - → Addressed by: the questions are now answered by the user (2026-11-18: second trial required; withdraw the override if an allow rule skips the prompt; W5 a follow-up, N2 folded into it, N3 accepted) and the body cites those answers. Opening the W5 follow-up stub and tracking issue is a main-session step in this run.
- **[WARN] The delivered sub-task briefs for blocks 6 and 7 still carry the old graph and the old block text**
  - **What is wrong:** `.claude/work-items/2026-11-16-425-t6-documents-skills-and-registries.md:34` reads `**Depends on:** 4, 5`. `.claude/work-items/2026-11-16-426-t7-final-review.md:34` reads `**Depends on:** 4, 5, 6`. The t7 brief calls itself "The contract's own handoff block, verbatim", but it lacks the new supersedes check and the t9 README constraint. Sub-issues 425 and 426 most likely carry the same text. No block, and no step for the main session, refreshes them. The contract says it heeds the lesson on updating every summary of the block graph.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 — "After amending a contract, update every summary of the block graph".
  - **Where in this contract:** `## Lessons referenced` — "heeded by the header's Revision line and the Delivery shape's block count and graph"; blocks 6 and 7 `**Depends on:**`.
  - → Addressed by: the main session refreshes the t6 and t7 briefs and their sub-issues (425, 426) with the new Depends on lines and block text before the first dispatch, and blocks 6 and 7 TASK text was made self-consistent so it can be copied verbatim. User answer 2026-11-18: accept all.
- **[WARN] Two round-one Open Questions are still unchecked on a contract that was approved and partly delivered**
  - **What is wrong:** "Re-confirm agent edits" and "Live prompt trial" are still `[ ]`. The live trial (t3) has been delivered and recorded. So either the contract was approved with open questions, or the answers were never written back. The user re-approving this revision cannot tell which.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22 — "An accepted critic WARN or answered Open Question must amend the contract body before approval".
  - **Where in this contract:** `## Open Questions for User` — "- [ ] **Re-confirm agent edits.**", "- [ ] **Live prompt trial.**".
  - → Addressed by: both questions are now ticked with the answer taken (the recommendation for the first; the trial delivered by t3 in pull request 438 for the second). User answer 2026-11-18: accept all.
- **[NIT] Uncertain Assumptions and Confidence were not updated with what t3 and the helper block proved** — line one still lists "`permissionDecision: "ask"` shows a prompt; a block beats an ask" as ASSUMED, with a verification path through two blocks that have both been delivered (the t4 report records that the default-mode prompt and the bypass-mode block were observed live).
- **[NIT] Block 9's step 8 Expected line accepts either outcome** — "record whether a prompt appears or the host refuses", while the assumption it tests states that plan mode shows a prompt. A host refusal would pass the step without settling the assumption.
- **[NIT] The second run sheet does not record the parent-branch commit it ran against** — blocks 8 and 9 are released together, so t9 may run on pre-fix code. Step 10 records only the Claude Code version, and the re-review reads t9 as evidence for the post-fix tip.
- **[NIT] Blocks 9 and 10 write a Gate Output that their Files to touch do not list** — this follows the precedent of blocks 3, 4 and 7. `_declared_review_verdict_file` (`pr_merged.py:1133-1140`) takes the first `.claude/reviews/` entry, so a listing would need the `.md` first.
- **[NIT] A blocked re-review has no block to go to** — "the next re-review then supersedes both blocked reports" implies an eleventh block that does not exist. 6 and 7 would wait on 10's `blocked` record until a further amendment adds one.
- **[NIT] Budget rule** — the file is far past its 12,000-token line. The template says a superseded critique round moves to `.claude/contract-history/<slug>.round-<n>.md`. It was kept here at the caller's request.

### Applicable journal entries

- **2026-11-02 — After amending a contract, update every summary of the block graph** — heeded in the header and the Delivery shape; not addressed for the t6 and t7 briefs and sub-issues, see WARN above.
- **2026-11-02 — Edit a reversed sentence where it stands** — heeded for the four rewritten rules; violated in spirit by the body stating answers to open questions, see WARN above.
- **2026-11-02 — Keep a review-fix block to the review's findings** — heeded for scope (B1, W1, W2, W4 and N1 only); the W2 wording goes past the finding, see WARN above.
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded for B1, W1, W2, W4 and N1; not addressed for the new piped and redirected refusal.
- **2026-11-05 — A hardening fix applied to a shared classifier must be checked against every consumer** — heeded: the W2 change is scoped to the Arm-write rule, and `_shell_write_targets.py` and the destructive-detection masking are left unchanged.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by block 8's "run the existing guard suites unchanged ... stop and report an AMENDMENT".
- **2026-11-06 — Judge a drive letter with a no-I/O check before any realpath** — not addressed for the W4 fix's followed-link stat, see WARN above.
- **2026-10-05 — Count a host's size cap the way the host counts, and prove the cap with a real trial** — heeded by block 9; weakened by the session-reload gap, see WARN above.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded for the t4 findings; not addressed for the two unchecked round-one questions.

### What the critic did not check

- `pr_merged.py --contract 2026-11-16-file-based-switches --status --json` was not run (no shell), so `layout_defects` were not read. The missing sub-issues and briefs for t8 to t10 are expected to show until the main session opens them.
- The t4 completion record lives on the records branch and is not in this worktree. That it carries `review_verdict: blocked` is inferred from the merged report.
- `derive_area.py` was not run. `.claude/area-mapping.json` declares no areas, as round one noted.

### Third round — 2026-11-19 (amendment 2: security-review remedy round 2)

**Critic:** contract-critic
**Date:** 2026-11-19
**Verdict:** blockers-found

Scope: the Revision 2 line, blocks 11 and 12, the re-linked Depends on lines and text of blocks 6 and 7, the amended No-prompt classes and Broken-file rules, the Guard rules file entry, Uncertain Assumptions, Failure Modes, the residual-risk paragraph and the three amendment-2 Open Questions. Checked against the t10 report and its Gate Output (read-only, in the worktree `20261118-task-t10-security-re-review`), the t9 run sheet, `db-destructive-guard.py:1187-1211`, `db-research-readonly-guard.py:175-223`, `test_db_destructive_guard.py:1880-1899` and `pr_merged.py:266-291`.

**Verified, no finding:**
- No cycle in the graph. `_parse_depends_on` (`pr_merged.py:284-291`) reads the text before the first `—`: block 6 gives `[5, 12]`, block 7 gives `[5, 6, 12]`, block 11 gives `[8]`, block 12 gives `[11]`. Every block has a Depends on line. No block names 4 or 10, so no block waits on a `blocked` record. Block 8 is merged, so 11 is releasable once approved; 12 releases on 11; 6 and 7 release only on 12's `pass` or `pass-with-findings`.
- `derive_subtask_id` (`:266-274`) gives `t11-security-review-fixes-round-two` and `t12-security-re-review-round-three`. The declared report name `t12-security-re-review-round-three-security-auditor.md` matches, and block 7's supersedes check names the same Gate Output. t1 to t10 keep their ids.
- Block 11 lists every failing probe of the t10 "Human-only placement" table (H1, H3, H4, H5, H6, H7, O13, O13e) plus the B1 Fix line's `cd "<p>" && <script>` and `Write-Host 'x'; <script>` forms. It keeps O11, O12, O13b and O14 as controls, and it keeps r4.7a.12, r4.7a.12b, r4.7a.7b and r4.7a.13 (`test_db_destructive_guard.py:1884-1891`, the script named inside quotes) as must-stay-allowed controls through the "existing guard suites unchanged" rule. Block 12 re-runs them in the original order, in both shell forms.
- `db-research-readonly-guard.py:207` reads the rules file with a plain `open()`, as the I1 entry says. Its loader returns `()` on failure, which its comment (`:180-183`) defines as fail-closed. So "takes the loader's existing fail-closed result" is true for both guards.
- No block's Files to touch names a plugin version file. Blocks 11 and 12 state the parent-mode version rule. The `**Work Item Brief:**` header is present (static check only).
- The W5 follow-up stub `.claude/concepts/followups/2026-11-18-override-prompt-target-and-reason-neutraliser.followup.md` exists. The briefs for t6 and t7 still read `5, 10` and `5, 6, 10` (`2026-11-16-425-…:34`, `2026-11-16-426-…:34`), which the Revision 2 preconditions name for refresh before the first dispatch.
- No hidden-question words (`maybe`, `likely`, `probably`, `TBD`, `we could`, `not sure`, `assuming`) appear outside the Critique section. Confidence `Medium` agrees with the ASSUMED entries.

### Findings

- **[BLOCKER] Block 11's B1 and P1 rows require an outcome from the read-only guard that it cannot give, and the same block forbids changing it**
  - **What is wrong:** The rows run "both guards as separate processes" and expect "exit 2, no ask JSON, the arm still in place" (armed) or "exit 2" (no arm). The read-only guard has no human-only class. The t10 report shows that, armed, it claims the arm and asks on a `sqlcmd -d <db> -Q "<row delete>"` call joined with the script (L1, probe X1), and the t9 log shows it matches the `sqlcmd -Q` removal too (`claimed-by-sibling`). So for O13, O13e and H7 the read-only guard's process asks and renames the arm. With no arm, H1 to H5 contain no SQL, so the read-only guard allows them with exit 0. The same TASK says "Do not fix L1 and do not touch the read-only guard's decision code". As written, the block cannot go green. The implementer must either stop with an AMENDMENT or weaken the rows, which is how the block 8 rows went wrong.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-06 — "An exception sentence that names the outcome of a later call must list every outcome that call can have" (Apply when: "a contract adds a message or doc sentence that predicts the block reason, exit code or log event of a future call"); this contract's own `## Failure Modes & Mitigations` L1 entry; t10 report, finding L1 (X1, X2).
  - **Where in this contract:** block 11 TASK — "both guards as separate processes … armed, default mode, expect exit 2, no ask JSON, the arm still in place" and "no arm, expect exit 2 (blocked, not allowed)"; the same block — "Do not fix L1 and do not touch the read-only guard's decision code".
  - → Addressed by: user answer 2026-11-19 "Test the destructive guard alone": only destructive-guard rows expect a block, each in its own project with its own arm; read-only guard rows pin today's L1 behaviour (armed asks and claims on the database-write shapes, otherwise allows), and block 11's "What the rows prove" paragraph says plainly that both guards are not claimed to block.
- **[WARN] Block 11 does not force the reported probes to be red at the tip: any reported row that passes there is relabelled a control**
  - **What is wrong:** "Rows that already pass at the tip are controls; name them as controls" applies to every new row, including the copied t4 and t10 probes. Each reported probe fails at the tip by definition. So a copied probe that passes at the tip has been mistranscribed (script first, or a bare script name). The bug needs a folder separator before the script name: the strip pattern at `db-destructive-guard.py:1190-1192` ends in `[\\/]$`, and t10's H is `tools/db-protection/update-dev-database.cmd`. With a bare name, `echo "start" ; update-dev-database.cmd` already blocks at the tip. The block pins backslash paths for the PowerShell form only. A mistranscribed row can therefore pass as a "control", and the suite goes green again. That is the block 8 failure t10 describes: "its rows all put the script first, the one order that works, so the suite was green".
  - **Prior artifact ignored:** t10 report, B1 ("The fixes block's rows all put the script first … so the suite is green"); `JOURNAL.md` 2026-10-17 — "Loosening a guard rule must be checked against the guard's own test fixtures" (Apply when: "a contract changes what a hook allows or blocks").
  - **Where in this contract:** block 11 TASK — "Rows that already pass at the tip are controls; name them as controls."; "each copied from the reports' text in the reporter's exact clause order".
  - → Addressed by: the relabelling sentence is gone; every copied probe and hang row must fail at the tip, a passing copy is fixed as mistranscribed, only named controls and pins may pass, and every row uses the folder path (forward slashes in bash, backslashes in PowerShell).
- **[WARN] The new invoked-or-mentioned sentence can demote a script inside a quoted launcher argument, and no row pins that case**
  - **What is wrong:** Today `bash -c "cd x; tools/db-protection/<script>"` counts as invoked. The strip pattern matches from the opening quote, which leaves `-c`, a known launcher (`:1196-1197`). The new rule splits only on "separators outside quotes", and it tests "the word that holds it … is the first word of a command segment, after any launcher word". It does not say whether a quoted launcher argument whose script follows an inner separator (`bash -c "cd x; <script>"`, `cmd /c "echo a & <script>"`, `powershell -Command "Write-Host x; <script>"`) is invoked. t10's suggested reading ("test only whether the script is the first word of a segment") makes it mentioned, which is a new P1-class allow. A search of `.claude/hooks/tests` finds no row with that shape, so the "existing suites unchanged" rule cannot catch a regression.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-17 — "Loosening a guard rule must be checked against the guard's own test fixtures"; `.claude/hooks/db-destructive-guard.py:1187-1197` (current behaviour); `JOURNAL.md` 2026-11-02 — "A revision that adds a path adds its failure modes".
  - **Where in this contract:** `## Data Shapes` → No-prompt classes rule — "segments are split on separators outside quotes"; block 11 TASK — "Controls that must stay allowed: … that name the script inside quotes".
  - → Addressed by: the rule now treats a known launcher's quoted argument as command text and allows only mentioned-to-invoked moves; block 11 adds blocking controls for `bash -c "cd x; <script>"`, `cmd /c "echo a & <script>"` and `powershell -Command "Write-Host x; <script>"`, and block 12 re-runs them.
- **[WARN] The residual-risk paragraph names W4 and I1 "until block 11 merges", but omits B1 and P1, and its I1 clause assumes an unanswered question**
  - **What is wrong:** Until block 11 merges, the parent tip lets an armed combined call prompt for a human-only script (B1), and lets the script run with no arm and no prompt after any quoted text (P1, "critical" in t10). The paragraph that says "in one place" names neither. The I1 clause says it ends when block 11 merges. If the user answers "no" to "Rules-file pipe link", I1 stays open after block 11 merges, and the sentence is false.
  - **Prior artifact ignored:** t10 report, findings B1 and P1, and W3(b); `JOURNAL.md` 2026-10-22 — "An accepted critic WARN or answered Open Question must amend the contract body before approval" (here the reverse: the body assumes an answer that has not been given).
  - **Where in this contract:** `## Failure Modes & Mitigations` → residual-risk paragraph — "Until block 11 merges, a symbolic link at a switch-file path … and a pipe link at the database guards' rules file can time out the guards themselves".
  - → Addressed by: the "until block 11 merges" sentence now names B1 and P1 first, and the I1 clause cites the user's 2026-11-19 answer (I1 is in block 11), so it no longer rests on an open question.
- **[WARN] The allow-rule bullet is marked VERIFIED without the limit that, under block 9's own rule, voids step 6**
  - **What is wrong:** Block 9 step 6 says the Observed line must show the session start time after the save, "otherwise the step is void and is run again". The t9 Observed line says "the exact start time was not recorded". The start is inferred from a differing session id, and t10 lists this as a limit. The contract bullet states "in a session started after the rule was saved" as verified, lists the other limits, and leaves this one out. The decision not to withdraw the override rests on this bullet.
  - **Prior artifact ignored:** t9 run sheet, step 6 Observed line (`…t9-live-prompt-trial-second-round-senior-test-engineer.md:92`); t10 report, "t9 step 6" bullet ("the session start time was inferred from a differing session id, not recorded"); `JOURNAL.md` 2026-10-05 — "Count a host's size cap the way the host counts, and prove the cap with a real trial".
  - **Where in this contract:** `## Uncertain Assumptions` — "`VERIFIED live, limited (t9 step 6 …)` … in a session started after the rule was saved"; the Revision 2 line — "Step 6 of the second live trial was met".
  - → Addressed by: the bullet now reads "OBSERVED live, limited, not verified to block 9's own standard", states that the start time was inferred from a session id, quotes block 9's "void and run again" rule, and names why the override is still kept (the person and t10 accepted the inference; the user declined a further trial); the Revision 2 line and the residual-risk paragraph carry the same limit.
- **[WARN] The L1 acceptance states an ASSUMED precedence as fact and cites a block text that no block writes**
  - **What is wrong:** "it fails closed, because a hook block beats a hook ask" contradicts Uncertain Assumptions, where "a block beats an ask when both guards answer one call" is ASSUMED. t10 also says L1 fails closed only "if a block beats an ask (still `ASSUMED`)". "The block text tells the person to re-arm": no text in `.claude/hooks` says so, and no block in this contract adds it. Block 11 forbids touching the read-only guard's decisions. The destructive guard's human-only text tells the person to run the command by hand, which is the opposite advice.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 — "Check a documented guard behaviour against the guard's code"; this contract's `## Uncertain Assumptions` second bullet; t10 report, L1.
  - **Where in this contract:** `## Failure Modes & Mitigations` → "FM (re-review L1 …)" — "it fails closed, because a hook block beats a hook ask" and "The block text tells the person to re-arm."; Open Question "Read-only guard spends an arm".
  - → Addressed by: the L1 entry and its Open Question now say it fails closed only if a block beats an ask, which stays ASSUMED in Uncertain Assumptions (with the L1 consequence added there); the re-arm sentence is struck through, and no block adds such text.
- **[WARN] The I1 reuse claims that no working rules file changes meaning, but the Windows link-target check makes some working files unreadable**
  - **What is wrong:** The amendment routes the rules file through "the Windows link-target check first". A rules file that is a link to a mapped network drive or a `\\server\share` file loads today. After the change it counts as unreadable, so every database is protected and the disposable exemption is withdrawn. That is a new false block on a working install. The sentence "no rules file that works now changes meaning" is false for it. No Failure Modes entry and no block 11 row covers this, and the change note in block 6 does not mention it. The contract says it heeds the 2026-11-01 lesson for this exact reuse.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-01 — "A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for"; `MECHANISMS.md:62` (Guard rules file: "The fail direction is per hook and must be stated in the file").
  - **Where in this contract:** `## Reused Mechanisms` → Guard rules file — "A regular file decodes exactly as today, so no rules file that works now changes meaning"; `## Lessons referenced` 2026-11-01 — "a regular rules file decodes exactly as today".
  - → Addressed by: the claim is struck through and corrected in place; a new Failure Modes entry accepts the network-linked rules file as fail-closed (every database protected, disposable exemption withdrawn); block 11 adds a `\\server\share` link row per guard, and block 6's change note tells the person to keep a regular file.
- **[WARN] Block 11 asks for two new inline fallback copies of the regular-file check but only one fallback row**
  - **What is wrong:** The I1 constraint adds an inline fallback reader to each database guard, and the read-only guard is not one of the registered Guard fallback mode users. Yet the block asks for "one fallback row with the helper removed". It also does not say whether the inline copy keeps the Windows link-target check or only the open-then-`fstat` check. The registry entry requires a test per copy, per spelling, run against a stale helper as well as a deleted one.
  - **Prior artifact ignored:** `MECHANISMS.md:64` (Guard fallback mode, part 4: "Each inline copy is separate code, so each needs its own test for every spelling it must handle … Run the fallback against a stale copy of the helper, not only a deleted one").
  - **Where in this contract:** block 11 TASK, I1 — "keep an inline fallback copy in each guard … one fallback row with the helper removed".
  - → Addressed by: each inline copy must keep both the link-target check and the open-then-`fstat` check; block 11 requires, for each guard's copy, rows with the helper deleted and with a stale helper, for the `\\.\` and `\\?\` pipe-link spellings and a `\\server\share` link, plus a regular file; block 6 records the read-only guard as a new Guard fallback mode user.
- **[NIT] "Each in a bash form and a PowerShell form" is undefined for rows that only exist in PowerShell** — O13e, H3 and `Write-Host 'x'; <script>` are already the PowerShell forms. `&&` (H4, H5) does not parse in Windows PowerShell 5.1. Block 12 repeats the instruction.
- **[NIT] "Read both reports in full: they hold the exact probe texts" is not true for the destructive part** — t4 and t10 name destructive statements in words, by their own rule. The generators (`%TEMP%\t10h\gen_o13.py`, `gen_h.py`) are outside the repository. Only the clause order and the script path are exact.
- **[NIT] Open Question "Rules-file pipe link", the "no" branch** — it says "both guards' `.py` files keep only the B1 change", but the read-only guard carries no B1 change. On "no" it leaves block 11 entirely, as the note under block 11's Files to touch says.
- **[NIT] The Windows link-target check judges only the first hop** — a switch or rules file that links to a local link, which then points to a disconnected network drive, passes the check and stalls in `open` (`JOURNAL.md` 2026-11-06, drive-letter lesson). This predates amendment 2, but the rule was amended again without naming it.
- **[NIT] Block 7's CONTEXT says blocks 9 and 10 "are in the branch through block 12"** — neither is in block 12's dependency closure (12 → 11 → 8 → 2). It is true today only because both have merged.
- **[NIT] The guards will bind the helper's private `_read_regular_file_bytes`** — this cross-module entry point has no Commands row. Block 6's registry list has no correction for `MECHANISMS.md:62` (Guard rules file is now read through the helper) or `:64` (the read-only guard becomes a sixth fallback user). The Reused Mechanisms entry still opens with "not extended".
- **[NIT] `## Lessons referenced` lists "2026-11-02 — Keep a review-fix block to the review's findings" twice** — once for round one and once for block 11.
- **[NIT] Budget rule** — this third round is appended in place at the caller's request. The template moves superseded rounds to `.claude/contract-history/<slug>.round-<n>.md`.

**Architect's note on the third-round NITs (2026-11-19).**
- Bash and PowerShell forms: taken. Block 11 writes a one-shell probe once, in that shell, and keeps `&&` rows as written, because the guard judges text. Block 12 says the same.
- Exact probe texts: taken. Block 11 now says that only the clause order and the script path are exact, and that the destructive statements are rebuilt from the reports' words.
- The "no" branch of "Rules-file pipe link": taken. Struck through; the answer was yes.
- Block 7's CONTEXT: taken. It now says blocks 9 and 10 merged before block 12 was released, not that they are in its dependency chain.
- The private reader name: taken. Block 11 exposes `read_regular_file_bytes` under a public name, with a Commands row. Block 6 adds corrections for "Guard rules file" and "Guard fallback mode". The Reused Mechanisms entry no longer opens with a bare "not extended".
- The duplicate lesson: taken. The second entry is marked as the second application.
- Multi-hop links: deferred. It predates amendment 2 and is not a review finding (the lesson on keeping a review-fix block to the review's findings). Judging a link chain without any I/O is its own design question. Block 12 may record it as information.
- Budget: deferred. The rounds stay in place at the caller's request.

### Applicable journal entries

- **2026-11-02 — After amending a contract, update every summary of the block graph** — heeded by the Revision 2 line, the Delivery shape, the Depends on lines and text of blocks 6 and 7, and the precondition to refresh the t6 and t7 briefs and sub-issues 425 and 426.
- **2026-11-02 — Edit a reversed sentence where it stands** — heeded for the Windows-pipe sentence, the allow-rule bullet and the residual-risk sentence, which are struck through in place. Not addressed for the Guard rules file entry's opening "not extended" (NIT above).
- **2026-11-02 — Keep a review-fix block to the review's findings** — heeded: block 11 holds B1, P1, W4 (Windows) and I1 only, and L1 and the untried modes are dispositioned rather than coded.
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded for W4 (Windows), B1, P1, I1, L1 and the t9 residual. Not addressed for the quoted-launcher demotion or the network-linked rules file (WARNs above).
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have** — violated, see BLOCKER above.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — violated by the L1 "re-arm" claim, see WARN above.
- **2026-11-01 — A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for** — claimed heeded; not addressed for the network-linked rules file, see WARN above.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by the "existing guard suites unchanged" rule and the named retirement of P1-pinning rows. Not addressed for the quoted-launcher shape, which no fixture covers.
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them** — heeded: `test_db_destructive_guard.py` is listed only to retire, by name, rows that pin a P1 shape as allowed.
- **2026-11-05 — A hardening fix applied to a shared classifier must be checked against every consumer** — heeded: `_in_command_position` has one caller, `_human_only_script_hits` (`:1205`), which feeds `_dynamic_labels` (`:1268`) and `_bind_targets` (`:1521`). Block 11 limits the change to what that chain needs.
- **2026-11-06 — Judge a drive letter with a no-I/O check before any realpath** — heeded for the first link hop; multi-hop chains not addressed (NIT).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded for the 2026-11-18 answers. The residual-risk I1 clause pre-empts the open "Rules-file pipe link" answer (WARN above).
- **2026-10-05 — Count a host's size cap the way the host counts, and prove the cap with a real trial** — heeded by block 12's real Windows pipe-link attempt. Weakened by the unrecorded session start in t9 step 6 (WARN above).

### What the critic did not check

- `pr_merged.py --contract 2026-11-16-file-based-switches --status --json` was not run (no shell), so `layout_defects` were not read. Missing sub-issues and briefs for t11 and t12 are expected until the main session opens them.
- `derive_area.py` was not run; `.claude/area-mapping.json` declares no areas, as rounds one and two noted.
- Whether the read-only guard's process asks for O13 and H7 exactly as stated was not re-run. That finding rests on t10 L1/X1 and the t9 `claimed-by-sibling` log line.
- `.claude/north-stars/` holds no active file, so checklist item 13 produced no findings.

### Fourth round — 2026-11-20 (amendment 3: security-review remedy round 3)

**Critic:** contract-critic
**Date:** 2026-11-20
**Verdict:** blockers-found

Scope: the Revision 3 line, the Delivery shape, the No-prompt classes rule (union of readings, command-start words), the Audit-log rule, the Reused Mechanisms amendment-3 sentence, Uncertain Assumptions, the amendment-3 Failure Modes entries, the residual-risk paragraph, the amendment-3 Open Questions, the amendment-3 Lessons referenced, the Depends on lines of blocks 6 and 7, and blocks 13 and 14. Checked against the t12 report and its Gate Output, `db-destructive-guard.py` (`:454-515`, `:782-798`, `:1269-1365`, `:1844-1902`), `db-research-readonly-guard.py` (`:64-99`, `:350-364`, `:621-678`), `_project_paths.py:197-207`, `test_database_override.py:797-820`, `test_db_destructive_guard.py:1851-1891` and `pr_merged.py:266-291`.

**Verified, no finding:**
- The graph has no cycle. `_parse_depends_on` (`pr_merged.py:284-291`) reads only the text before the first `—`, so block 6 gives `[5, 14]`, block 7 `[5, 6, 14]`, block 13 `[11]` and block 14 `[13]`. The trailing prose on 6, 7, 13 and 14 names 4, 10 and 12, but the parser never sees those numbers. No block depends on a `blocked` record. Block 11 is merged (`d43a285`), so block 13 can be released as soon as it is dispatchable. Block 7's CONTEXT chain (14 → 13 → 11 → 8) is accurate.
- `derive_subtask_id` (`:266-274`) gives `t13-security-review-fixes-round-three` and `t14-security-re-review-round-four`. The second matches the declared report and Gate Output names in blocks 6, 7 and 14.
- Block 14's `supersedes` list is `[t4, t10, t12]` on a pass and `[]` on `blocked`. That agrees with block 7's completion check and with the t12 Gate Output, which holds `[]`, so t4 and t10 are still in effect until t14 passes.
- Block 13's copied-row lists match t12 exactly. The armed rows are N1a, N1b, N2a and K4 to K6. The unarmed rows are N1, N1c, N15, N5 and N6 in PowerShell and N2, N2b, N3 and N4 in bash (t12 `:42`, `:160`). The P2 rows are N7 to N13 and K1 to K3 (t12 `:45`, `:141`). Each is ALLOW or ASK at the tip, so the rule that every copied row must start red can be met.
- Union of readings against the named controls. Every MENTION_ROWS entry (`test_database_override.py:805-820`) and the must-stay-allowed rows r4.7a.6 to r4.7a.13 (`test_db_destructive_guard.py:1863-1891`) fall into one of two groups. Some sit in a quoted span of a prose command that `_mask_inert_prose` blanks to spaces, newlines included (`:1858-1865`), before the classifier runs (`:2230`). The rest are unquoted arguments whose nearest earlier non-space character, once the folder prefix is stripped, is a letter or `-`, not a separator. Neither group can be flipped by the quote-blind reading as written. LAUNCHER_ROWS already expect a block, and an "any" union cannot flip a block into an allow.
- Windows has no `O_NONBLOCK` or `O_NOFOLLOW`. Opening a link to `\\?\pipe\…` therefore connects as a client and returns at once, and `os.fstat` then reports a FIFO. So for pipe links, the Audit-log rule's real protection is checking the open file's kind before writing. The rule does name that step, and t12's proposed fix agrees with it.
- No sub-task block lists a plugin version file. Block 13 forbids touching all four version files and states the parent-mode rule. The `**Work Item Brief:**` header is present (static check only). The t6 and t7 briefs still read `5, 12` and `5, 6, 12` (`2026-11-16-425-…:34`, `2026-11-16-426-…:34`), which the Revision 3 preconditions list for refresh.
- Stale text: "until block 11", "After block 11" and the old L1 sentence are struck through where they stand. The remaining mentions of block 12 (`:8`, `:295`, `:299`, `:1311`, `:1373`) are history or correct convention. Outside the Critique section there are no hidden-question words (`maybe`, `likely`, `probably`, `TBD`, `we could`, `not sure`, `assuming`). Every "recommended, awaiting the user" clause is raised as a question under Open Questions.

### Findings

- **[BLOCKER] The I2 scope rests on a false code claim: the read-only guard does write its audit to a project path, with the same plain append on its block path**
  - **What is wrong:** `db-research-readonly-guard.py:95-98` sets `AUDIT_LOG = _pp_log.logs_dir() / "db-research.log"`, and `_project_paths.logs_dir()` (`:197-207`) returns `<project>/.claude/logs`. Its `_audit` (`:350-364`) does the same `exists()`, `stat()` and `open("a")` as the destructive guard's. It runs before the guard returns BLOCK on `writes-without-readonly` (`:654`) and on the override outcome (`:656`). So a pipe link at `.claude/logs/db-research.log` is the same I2 route against the guard that alone blocks research writes. t12's "the read-only guard finished in 0.13 s, because it does not write its audit to the project path" (t12 `:47`) explains the result wrongly: t12 linked `db-guard.log`, not `db-research.log`. The contract copies that explanation into three places: the Audit-log rule ("The read-only guard does not write its audit to a project path and is not changed"), the note under block 13's Files to touch, and the residual-risk paragraph, which names only `db-guard.log`. Block 14's pipe-link list does not include `db-research.log`, so the next review is not asked to find this.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04, "Check a documented guard behaviour against the guard's code". `JOURNAL.md` 2026-11-02, "A sweep that deletes every proven file in a folder must route EVERY local reader of that folder through the remote evidence, not only the one the contract was about". This contract applied that lesson "in spirit" to I1 by naming both database guards (`## Lessons referenced`).
  - **Where in this contract:** `## Data Shapes` → Audit-log rule, "The read-only guard does not write its audit to a project path and is not changed"; block 13, "does not write its audit to a project path, so neither B1, P1, P2 nor I2 changes it"; residual-risk paragraph, "a pipe link at the destructive guard's audit log (`.claude/logs/db-guard.log`)".
  - → Addressed by: user answer 2026-11-20 (I2 extended to both guards). The Audit-log rule names both logs with the read-only guard's lines; block 13 lists `db-research-readonly-guard.py` (its `_audit` only) with per-guard rows in `test_database_override.py`; the I2 Failure Modes entry and the residual-risk paragraph name both logs and say t12 linked only `db-guard.log`; block 14 probes both logs.
- **[WARN] The Audit-log rule is placed "before it appends", but `_audit` follows links earlier, during rotation and folder creation**
  - **What is wrong:** `_audit` (`db-destructive-guard.py:785-791`) runs `AUDIT_LOG.parent.mkdir(parents=True)`, `AUDIT_LOG.exists()`, `AUDIT_LOG.stat()` and possibly `rename` before the append, and each of those follows links. Neither the rule nor block 13's I2 item says where rotation goes or that it is subject to the no-follow check. A link at `db-guard.log` to a disconnected mapped drive or a `\\server\share` target, or a directory link at `.claude/logs` to one, would therefore stall in `exists()` or `mkdir` before any new check runs. Block 13's I2 rows use pipe links only, and a stat on a pipe returns at once, so the suite stays green. The link-target check (`_inline_link_reason`, `:454-491`) also judges only the final path and its chain, not a parent folder that is a link. The Lessons referenced entry for the drive-letter lesson says it is "heeded by the Audit-log rule".
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-06, "Judge a drive letter with a no-I/O check before any realpath, because realpath of a mapped drive can block" (Apply when: "any opening call on a path whose drive letter may be a mapped network drive, inside a hook with a timeout"). The third round's NIT on multi-hop links was deferred and is the neighbouring case.
  - **Where in this contract:** `## Data Shapes` → Audit-log rule, "Before it appends, the guard refuses a log that is a link …". Block 13 I2: "implement the Audit-log rule in _audit: check the log path without following links". `## Lessons referenced`, 2026-11-06: "heeded by the Audit-log rule".
  - → Addressed by: the Audit-log rule and block 13's I2 item now cover the folders (single-level creation, each part judged without following links, reparse points refused), the log, rotation (only a regular log, only onto an absent or regular `.1`, no following stat or exists) and the open; block 13 adds rows for a `\\server\share` log link, folder links (pipe namespace, `\\server\share`, local folder) and rotation on a linked log and a linked `.1`; the Lessons entry is reworded.
- **[WARN] Block 13's "What the rows prove" predicts a read-only guard ask on N1b, but t12 recorded an allow there, and it lists K1 to K3 without the P2 condition**
  - **What is wrong:** The paragraph says that, armed, "on the shapes that hold a database write (N1b, N2a, K1 to K6)" the read-only guard "still asks and claims the arm". t12's table (`:129`) records N1b as rg `ALLOW, arm kept`, the same split as t4's literal O13. The L1 Failure Modes entry correctly leaves N1b out ("N2a and K4 to K6 (and K1 to K3 when P2 is in block 13)"), so the two sentences disagree. Block 14 is told to report the read-only guard's outcome beside each row, and it will contradict block 13's text.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-06, "An exception sentence that names the outcome of a later call must list every outcome that call can have". The t12 report's table "B1 and P1 shapes not covered by block 11" (row N1b).
  - **Where in this contract:** block 13, "**What the rows prove, plainly.** … armed, on the shapes that hold a database write (N1b, N2a, K1 to K6), it still asks and claims the arm".
  - → Addressed by: the paragraph now gives t12's outcomes (asks on N2a and K1 to K6; allows and keeps the arm on N1a and N1b) and says K1 to K3 apply because P2 is in block 13; the L1 entry agrees.
- **[WARN] The quote-blind fallback lets the implementer delete part of a Data Shapes invariant without an amendment, and the backtick's reading is left unassigned**
  - **What is wrong:** The No-prompt classes rule states the quote-blind reading as part of the invariant ("The script is invoked when ANY of these readings says so: … and a quote-blind reading"). Block 13 then says "If the quote-blind reading alone flips one of them, drop the quote-blind reading … and say so in the pull request body". After that the rule text would be false, block 14 would judge the code against a reading that does not exist, and no Failure Modes entry names what is lost. The fallback also covers only MENTION_ROWS, LAUNCHER_ROWS, the block 11 rows and O11 to O14. If the same reading flips any other existing row, the instruction is "stop and report an AMENDMENT", so two different procedures apply to the same cause. Separately, "a backtick opens a segment" (P2) contradicts the PowerShell reading, where a backtick is an escape. The rule places the backtick only in the quote-blind list ("only under the command-start words"). If that reading is dropped, it is undefined whether N7 and K3 still have a reading that classes them as invoked.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02, "A revision that adds a path adds its failure modes". `JOURNAL.md` 2026-10-22, "An accepted critic WARN or answered Open Question must amend the contract body before approval" (here an implementer's pull request changes the Data Shape). Global protocol: implementers do not redesign data shapes.
  - **Where in this contract:** block 13, "If the quote-blind reading alone flips one of them, drop the quote-blind reading, keep the other readings, and say so in the pull request body". No-prompt classes rule: "a backtick only under the command-start words below" and "A backtick opens a segment, as `$(` already does".
  - → Addressed by: one procedure. All four readings are part of the rule and none is optional; the backtick-opens-a-segment rule belongs to the bash reading alone (the PowerShell reading treats it as an escape, the quote-blind reading never counts it), and each reading is computed on its own. Any existing row that flips, other than a named P1/P2-pinning row, stops block 13 with an AMENDMENT; no reading is dropped.
- **[WARN] The "if no" branches of the two Open Questions do not list every sentence that would become false**
  - **What is wrong:** On a "no" to I2, the question says "the Audit-log rule leaves the contract". It does not name the Reused Mechanisms sentence ("Amendment 3: the Audit-log rule reuses the destructive guard's own inline link-target check …", `:149`), the Failure Modes entry "(the I2 fix skips an audit record)", the Lessons referenced 2026-11-06 entry (`:673`) or the Uncertain Assumptions clause "the Broken-file and Audit-log rules are designed so no read or write waits". On a "no" to P2, block 13 still lists "K1 to K6" in "What the rows prove", and its existing-suite rule still retires rows that pin "t12's B1, P1 or P2 shapes". Each of these sentences would stay in an approved contract and contradict the answer.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02, "Edit a reversed sentence where it stands". The third round's NIT on the "no" branch of "Rules-file pipe link" was the same defect one round earlier.
  - **Where in this contract:** `## Open Questions for User` → Amendment 3, "If no, block 13 drops its I2 constraint and rows, the Audit-log rule leaves the contract" and "If no, block 13 drops its P2 constraint and rows (N7 to N13, K1 to K3 and the per-word rows)".
  - → Addressed by: both questions are answered yes (2026-11-20), so the "if no" branches are removed from the questions, the rules, Failure Modes, the residual-risk paragraph and blocks 6, 13 and 14.
- **[WARN] The command-start words skip only option words that start with `-`, so common option-with-value spellings stay "mentioned", and `command -v` becomes an unnamed false block**
  - **What is wrong:** The rule passes the command start "after any `NAME=value` assignments and that word's own option words (those starting with `-`, plus the duration of `timeout`)". So in `nice -n 10 <script>`, `sudo -u root <script>`, `env -u NAME <script>` and `timeout -s KILL 5 <script>`, the value (`10`, `root`, `NAME`, `KILL`) becomes the command word and the script counts as mentioned. Each of these runs the script, so the P2 class stays open for ordinary spellings. Block 14 is told to "Try further spellings of the same rule", which predicts a fifth round. In the other direction, `command -v <script>` and `type`-like lookups through `command` are only existence checks, yet they become blocks. Neither direction has a row, a Failure Modes entry or a residual. The union entry covers false blocks from reading both shells, not from the keyword list.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-19, "A review-fix block's rows must copy each failing probe in the reporter's exact clause order and in every shell form" (its point is that a fix shaped only to the reported spellings left the class open). `JOURNAL.md` 2026-11-02, "A revision that adds a path adds its failure modes".
  - **Where in this contract:** `## Data Shapes` → No-prompt classes rule, "that word's own option words (those starting with `-`, plus the duration of `timeout`)". Block 13 P2 item, "Controls that must stay allowed: the same words as plain arguments (echo then <script>, grep -n time <script>)".
  - → Addressed by: an option that takes a value skips its value (block 13 lists them per word), with rows for `nice -n 10`, `sudo -u root`, `env -u NAME` and `timeout -s KILL 5`; `command -v` and `command -V` are decided as named mentions, with allowed rows.
- **[WARN] Status is `approved` with two unchecked Open Questions, and only prose keeps blocks 13 and 14 from dispatching**
  - **What is wrong:** Block 11 is merged and block 13 depends only on 11. As soon as the precondition "sub-issues for blocks 13 and 14 are opened" is met, `compute_released` will release block 13 whatever the user has answered. Its TASK says "per the user's answers", but the body holds no answer to read. The concept gate already accepts edits to `db-destructive-guard.py` under this approved contract. The second round flagged the same state ("Two round-one Open Questions are still unchecked on a contract that was approved").
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22, "An accepted critic WARN or answered Open Question must amend the contract body before approval". Second-round WARN, "Two round-one Open Questions are still unchecked on a contract that was approved and partly delivered".
  - **Where in this contract:** Revision 3 line, "Status stays `approved` at the caller's direction; blocks 13 and 14 are not dispatched until the user has answered both questions". `## Open Questions for User`, "- [ ] **Keyword and prefix-command starts.**" and "- [ ] **Audit-log pipe link.**".
  - → Addressed by: both questions are ticked with the user's 2026-11-20 answers. Status stays `approved` at the caller's direction; the Revision 3 line says blocks 13 and 14 are not dispatched until their sub-issues exist.
- **[NIT] Refusing every link makes the reused link-target check dead code for the log's own path** — the rule refuses "a log that is a link" when it checks without following links. `_inline_link_reason` (`:454-491`) only does work when the path is a link, so it can never change the outcome there. The I1 copy follows a local link to a regular file, and the audit log now refuses one, so this is a different policy from I1. The Failure Modes entry for the skipped audit record covers the user-visible effect.
- **[NIT] Block 14 drops block 12's instruction to "state what evidence there is for 'a hook block beats a hook ask'"** — the L1 acceptance still says "block 12 states which way the evidence stands" (`:299`), and amendment 3 adds N2a and K4 to K6 to L1. The next review is no longer asked to restate that evidence.
- **[NIT] Budget rule** — this fourth round is appended in place, as the caller directed. The template moves superseded rounds to `.claude/contract-history/<slug>.round-<n>.md`.

**Architect's note on the fourth-round NITs (2026-11-20).**
- Dead link-target check: taken. The Audit-log rule no longer reuses it; the rule and Reused Mechanisms say why it would be dead code, and state the policy difference from I1 (the rules file follows a local link to a regular file; the audit log refuses every link).
- Block 12's evidence instruction: taken. Block 14 again asks for the evidence that a hook block beats a hook ask, and the L1 entry records t12's answer (documentation only).
- Budget: deferred, at the caller's request.

### Applicable journal entries

- **2026-11-02 — After amending a contract, update every summary of the block graph** — heeded by the Revision 3 line, the Delivery shape (fourteen blocks, the new edges, the earlier edges recorded), the Depends on lines and CONTEXT of blocks 6 and 7, and the precondition to refresh the t6 and t7 briefs and sub-issues 425 and 426.
- **2026-11-02 — Edit a reversed sentence where it stands** — heeded for the L1 sentence, the elevation sentence and the residual-risk sentence, which are struck through in place. Not heeded for the "if no" branches (WARN above).
- **2026-11-02 — Keep a review-fix block to the review's findings** — heeded: block 13 holds B1, P1 and, on the user's answers, P2 and I2. N5, N6 and the other hooks' plain opens are dispositioned. Its I2 scope relies on the false read-only claim (BLOCKER above).
- **2026-11-02 — A sweep … must route EVERY local reader of that folder** — violated: the read-only guard's `db-research.log` append is the same route as I2 and is declared absent (BLOCKER above).
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — violated by the claim that the read-only guard does not write its audit to the project (BLOCKER above).
- **2026-11-19 — A review-fix block's rows must copy each failing probe in the reporter's exact clause order and in every shell form** — heeded for the copied rows (t12 ids, exact spelling, each red at the tip). Weakened for P2, whose rule leaves option-with-value spellings open (WARN above).
- **2026-11-05 — A hardening fix applied to a shared classifier must be checked against every consumer of that classifier** — heeded: only the classifier chain feeding `_human_only_script_hits` changes; the prose masker and `_shell_write_targets.py` are frozen.
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have** — heeded by the L1 entry's O13 and O13e correction. Violated by block 13's "What the rows prove" on N1b (WARN above).
- **2026-11-06 — Judge a drive letter with a no-I/O check before any realpath** — claimed as heeded; not met for the rotation step and parent-folder links (WARN above).
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded for the union reading's false block and the skipped audit record. Not addressed for dropping the quote-blind reading as a fallback, or for the P2 keyword list's false blocks and misses (WARNs above).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — partly heeded: the body is marked "recommended, awaiting the user". The approved status with open questions still holds (WARN above).

### What the critic did not check

- `pr_merged.py --contract 2026-11-16-file-based-switches --status --json` was not run, because the critic has no shell. `layout_defects` were not read, so the Parent Branch Delivery Rule check is static only.
- No probe was run. That the quote-blind reading leaves the named controls alone, that the I2 rows start red, and that the read-only guard's `db-research.log` hangs on a pipe link are judged from code reading only. The prose masker's own quote pairing was not re-probed beyond t12's `mask_probe.py` result.
- CodeGraph tools were not available in this session. Symbols were located by searching the files directly.
- `derive_area.py` was not run; `.claude/area-mapping.json` declares no areas. `.claude/north-stars/` holds no active file, so checklist item 13 produced no findings.

---

## Lessons referenced

- **2026-10-15 — A script that reads a project-owned file must be told which project, not search for one** — heeded by the Project-folder rule and the changed-file check's explicit root. `JOURNAL.md`.
- **2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file** — heeded by the No-file and Project-folder rules. `JOURNAL.md`.
- **2026-10-05 — A documented "missing file means the default" must read one named location only** — heeded by the Worktree rule and its decoy rows.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by the inventory, the README table test, and the corrected trust-level claim. `JOURNAL.md`.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded by the scan test planting `CLAUDE_MADE_UP_SWITCH`. `JOURNAL.md`.
- **2026-10-05 — Neutralise every field echoed from untrusted input, not only the body** — heeded by the Plain-reason rule.
- **2026-10-05 — Count a host's size cap the way the host counts, and prove the cap with a real trial** — heeded by the live trial block.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by the Arm-write rule rows and the fixture run.
- **2026-10-28 — A new term's definition must be true against every existing member** — heeded by the Switch definition and by not reusing Hand-off command. `JOURNAL.md`.
- **2026-10-28 — State the real trigger of a hook, not the printing condition** — heeded: the helper adds two small file reads per hook start, on the registered events only. `JOURNAL.md`.
- **2026-11-07 — A fail-soft reader must not record "seen" for what it could not read** — heeded by the Report-once rule's write order.
- **2026-11-09 — A change that adds a module-level import to a vendored script must update the vendored-file list in the same change** — heeded by the `addon.json` helper list change and by keeping `_contract_index.py` free of the import.
- **2026-11-02 — After amending a contract, update every summary of the block graph** — heeded by the header's Revision line and the Delivery shape's block count and graph. `JOURNAL.md`.
- **2026-11-02 — Edit a reversed sentence where it stands** — heeded: the No-prompt classes, Arm-write, Fresh-arm and Broken-file rules and the residual-risk paragraph are edited in place, not contradicted by later bullets. `JOURNAL.md`.
- **2026-11-02 — Keep a review-fix block to the review's findings** — heeded: the fixes block holds only B1, W1, W2, W4 and N1; the host questions go to the second live trial block; the README text stays with the documents block. `JOURNAL.md`.
- **2026-11-05 — A hardening fix applied to a shared classifier must be checked against every consumer of that classifier** — heeded by scoping the W2 fix to the Arm-write rule, leaving the prose masker's destructive-detection use and the shared shell parser unchanged. `JOURNAL.md`.
- **2026-11-06 — Judge a drive letter with a no-I/O check before any realpath, because realpath of a mapped drive can block** — heeded by the Broken-file rule's Windows clause: a switch file that links to a network target is judged from the drive table and never opened, because a timed-out hook is an allow. `JOURNAL.md`.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded: each accepted review finding amends the rule it concerns, and each answered question is cited where the body relies on it. `JOURNAL.md`.
- **2026-11-01 — A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for** — heeded by amendment 2's I1 reuse: only the open-and-kind check is shared with the rules-file loaders, a regular rules file decodes exactly as today, a failed check maps to the loaders' existing fail-closed result, and the one working form that changes meaning (a rules file linked to a network target) is named and accepted in Failure Modes. `JOURNAL.md`.
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have** — heeded after the third critique round: block 11 states each guard's outcome separately, and no sentence claims both guards block. `JOURNAL.md`.
- **2026-11-02 — A sweep that deletes every proven file in a folder must route EVERY local reader of that folder through the remote evidence** — heeded in spirit by amendment 2: the rules file is read by both database guards, so the I1 fix names both readers, not only the one the auditor found. `JOURNAL.md`.
- **2026-11-02 — Keep a review-fix block to the review's findings** (second application; the first is above, for block 8) — heeded by block 11: B1, P1, W4 and I1 only; L1 and the untried modes are dispositioned in the contract, not coded; other hooks' rules files stay out of scope. `JOURNAL.md`.
- **2026-11-02 — Edit a reversed sentence where it stands** and **After amending a contract, update every summary of the block graph** — heeded by amendment 2: the Windows-pipe sentence, the allow-rule assumption and the residual-risk sentence are struck through and corrected where they stand; the header, Delivery shape, blocks 6 and 7 and the main-session preconditions carry the new graph. `JOURNAL.md`.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by block 11 in the tightening direction: the existing guard suites run unchanged, and a row that pins one of the P1 shapes as allowed is retired by name, never silently edited.
- **2026-11-19 — A review-fix block's rows must copy each failing probe in the reporter's exact clause order and in every shell form** — heeded by amendment 3: block 13 copies t12's rows by their t12 ids in t12's exact spelling and shell, each must fail at the parent tip, and block 14 re-runs them in a real shell as well as through the guard. `JOURNAL.md`.
- **2026-11-05 — A hardening fix applied to a shared classifier must be checked against every consumer of that classifier** — heeded by amendment 3: the union of readings can only move a mention to an invocation, the classifier's one consumer chain (`_human_only_script_hits`) is the only caller changed, and the mention and launcher control rows plus the existing suites guard the other direction. `JOURNAL.md`.
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded by amendment 3: the union reading's false block and the skipped audit record each have a Failure Modes entry. `JOURNAL.md`.
- **2026-11-02 — After amending a contract, update every summary of the block graph** and **Edit a reversed sentence where it stands** — heeded by amendment 3: the Revision 3 line, the Delivery shape, blocks 6 and 7, the L1 sentence, the elevation sentence and the residual-risk paragraph are edited where they stand. `JOURNAL.md`.
- **2026-11-02 — Keep a review-fix block to the review's findings** (third application) — heeded by block 13: B1, P1, P2 and I2 (I2 in both database guards) only, P2 and I2 by the user's answers of 2026-11-20; N5, N6 and the other hooks' plain opens are dispositioned in the contract, not coded. `JOURNAL.md`.
- **2026-11-06 — Judge a drive letter with a no-I/O check before any realpath** — heeded by the Audit-log rule after the fourth critique round: every step of the audit path (each folder, the log, the rotated name) is judged without following links, so no link target, network or pipe, is touched before the link is refused. `JOURNAL.md`.
- Orthogonal to north-stars: none active.

---

## Implementation Handoff

Every block below follows the template's rules for sub-task identity, one pull request per sub-task, the review artefact's six sections and its verdict line. Run every Python test with `py -3`.

### 1. RED tests (`senior-test-engineer`)

**Depends on:** none

**Files to touch:**
- `.claude/hooks/tests/test_switches.py`
- `.claude/hooks/tests/test_database_override.py`
- `.claude/scripts/tests/test_switch_env_scan.py`

**Pre-written TASK block:**
```
TASK: Write the failing tests first, for the switch helper, the database override and the
  environment-read scan. Mark every row that fails at base with unittest.expectedFailure.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (the switch
  rules, the override rules and the Inventory).
FILES: the three new test files.
CONSTRAINTS:
  - test_switches.py, temporary projects only: every switch rule and the value sets. Encoding
    rows: a UTF-8 byte order mark and a UTF-16 file are read. Broken-file rows: unreadable and
    not-an-object files leave every default and report once; the marker is not written when the
    log write fails. Worktree rows: an empty or broken own file stops the fallback; decoys in the
    working directory, the plugin's .claude folder and the main checkout (when the project is the
    main checkout) are never read. A row proves an environment variable named CLAUDE_CONCEPT_GATE
    or concept_gate changes nothing. An explicit project argument wins over CLAUDE_PROJECT_DIR.
  - test_database_override.py, both guards as separate processes. Refused: Write, Edit,
    MultiEdit and NotebookEdit targeting the arm; Bash and PowerShell with New-Item, touch, a
    redirection and a quoted path argument (both slashes, mixed case). Allowed: a commit message,
    a pull request body and a search pattern that only mention the name. Armed plus default mode
    gives the ask JSON, exit 0, and the arm gone. bypassPermissions, dontAsk and a missing mode
    block. Stale, folder and link arms block. The human-only class and an injected fault block
    when armed. CLAUDE_DESTRUCTIVE_DB_OK=1 no longer allows. A non-destructive call keeps the
    arm. Two guards on one tool_use_id both ask. The refusal still fires when the guard defers.
    The inline name-test copy works with the helper removed. A crafted target with comment
    markers appears neutralised in the reason.
  - test_switch_env_scan.py: parse every .py under .claude/hooks, .claude/scripts and
    .claude/addons/*/hooks (tests excluded) with the ast module. Literal reads must be in the
    contract's host, platform or test-only lists. Any non-literal read, alias of os.environ, or
    os.environ passed to a function must be on a named list of reviewed sites (file and
    function). Plant CLAUDE_MADE_UP_SWITCH and an alias as positive controls. Name the limit in
    the docstring. Text row: no retired variable name in shipped hooks, scripts, skills,
    CONTRIBUTING or README outside "Change notes by version". Table row: the README switch table
    equals the catalog keys.
  - The suite passes at base with expected failures only. The pull request body names each one.
  - Also run the destructive guard's existing suites at base and record them green.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 2. Switch helper and database override (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/hooks/_switches.py`
- `.claude/hooks/db-destructive-guard.py`
- `.claude/hooks/db-research-readonly-guard.py`
- `.claude/hooks/tests/test_switches.py`
- `.claude/hooks/tests/test_database_override.py`
- `.claude/hooks/tests/test_db_destructive_guard.py`
- `.claude/hooks/tests/test_db_guard_path_allowlist.py`
- `.claude/hooks/tests/test_readonly_guard_disposable_exemption.py`
- `.claude/hooks/tests/test_worktree_path_guards.py`
- `.claude/hooks/tests/fixtures/db-protection/tests/test_db_protection_scripts.py`
- `.claude/scripts/tests/test_sql_patterns_skill_sync.py`
- `skills/sql-server-patterns/SKILL.md`
- `skills/auto-improve-database-guard-install/SKILL.md`
- `.gitignore`

**Pre-written TASK block:**
```
TASK: Build the switch helper and replace the destructive-database variable with the Database
  override arm in both guards. Remove the expectedFailure marks from the helper and override rows.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md.
FILES: as listed.
CONSTRAINTS:
  - First: confirm from the Claude Code hooks documentation that the PreToolUse payload carries
    permission_mode and tool_use_id, how "ask" combines with other answers, and that
    systemMessage is shown to the person. Quote the source in the pull request. If it disagrees
    with the contract, stop and report an AMENDMENT.
  - The helper owns the catalog of nine keys exactly as the Inventory table says, and the
    Visible-off rule's systemMessage output for guards. Call-time lookups only.
  - The Arm-write rule runs before Guard deference, in both guards, with an inline copy of the
    name test in each (Guard fallback mode). Audit reasons: the Override outcome values plus
    override-file-write-refused. Remove user-override-env.
  - Reword the docstrings, block text and the two skills; no variable is named as a way out.
    Escape apostrophes in the printed arm commands.
  - Do not touch any plugin version file.
  - Run: test_switches.py, test_database_override.py, test_db_destructive_guard.py,
    test_db_guard_path_allowlist.py, test_readonly_guard_disposable_exemption.py,
    test_worktree_path_guards.py, test_sql_patterns_skill_sync.py, test_script_path_resolution.py.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 3. Live prompt trial (`senior-test-engineer`)

**Depends on:** 2

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t3-live-prompt-trial-senior-test-engineer.md`

**Pre-written TASK block:**
```
TASK: Write the run sheet for a person-run trial of the prompt route. Do not run it; a person
  runs it in a real Claude Code session and sets the verdict before this pull request merges.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (Person-present
  rule, Visible-off rule, Uncertain Assumptions).
FILES: the run sheet only. It does NOT exist yet; you create it.
CONSTRAINTS:
  - Header line, alone on its line: "**Verdict:** blocked", plus the line "Results pending: a
    person runs the steps below". Merged unchanged, it holds every block that depends on it.
  - Steps, each with a PowerShell command and an expected and an observed line: (1) arm and run
    a destructive command on a disposable-looking but non-disposable name in default mode; a
    prompt appears, and declining leaves no arm; (2) the same in bypass-permissions mode blocks;
    (3) a headless run (claude -p) with no permission tool blocks; (4) switching concept_gate off
    shows the person a message once in the session; (5) record the Claude Code version.
  - The six fixed sections. "## Evidence" holds the person's observations. Write the Gate Output
    beside it with supersedes [] and checklist [].
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 4. Security review (`security-auditor`)

**Depends on:** 2, 3

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md`

**Pre-written TASK block:**
```
TASK: Review the helper block as a safety-critical change, and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md.
FILES: .claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md
CONSTRAINTS:
  - Check each override rule against the code. Try to create the arm as an agent by every route
    you can think of (Write, Edit, shell redirection, encoded or joined paths, a script file).
    Name each route and whether the guard saw it.
  - Check that no path allows a destructive command without a prompt, that the stated residual
    risk is complete, that the prompt reason is neutralised, and that the live trial run sheet's
    observations support the Person-present rule.
  - Check the Broken-file and No-environment rules: no broken or missing file, and no missing
    helper, turns a guard off.
  - Write the artefact in the template's six-section shape. The file does NOT exist yet; you
    create it. Name the commit range reviewed, base..head. "## Evidence" lists the commands run
    with exit codes. End the header with one verdict line, alone on its line:
    "**Verdict:** pass", "**Verdict:** pass-with-findings" or "**Verdict:** blocked".
  - Also write the Gate Output <artefact stem>.gate.json beside it, as the template says.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 5. Ordinary switches (`python-ai-developer`)

**Depends on:** 2

**Files to touch:**
- `.claude/hooks/concept-gate.py`
- `.claude/hooks/architecture-guard.py`
- `.claude/hooks/critic-verdict-tracker.py`
- `.claude/hooks/contract-status-watcher.py`
- `.claude/hooks/journal-post-approval-tracker.py`
- `.claude/hooks/integration-check.py`
- `.claude/hooks/memory-pager.py`
- `.claude/hooks/working-agreements.py`
- `.claude/hooks/plan-question-advisor.py`
- `.claude/scripts/_contract_index.py`
- `.claude/scripts/concept_changed_check.py`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/addons/strict-shell-gate/hooks/bash-gate.py`
- `.claude/addons/strict-shell-gate/addon.json`
- `.claude/switches.json`
- `.claude/hooks/tests/fixtures/gate_parity_corpus.json`
- `.claude/hooks/tests/test_contract_index.py`
- `.claude/hooks/tests/test_gate_cost.py`
- `.claude/hooks/tests/test_concept_gate_outside_project.py`
- `.claude/hooks/tests/test_changed_file_check.py`
- `.claude/hooks/tests/test_main_checkout_guard.py`
- `.claude/hooks/tests/test_shell_write_targets.py`
- `.claude/hooks/tests/test_architecture_guard_paths.py`
- `.claude/hooks/tests/test_architecture_guard_precision.py`
- `.claude/hooks/tests/test_architecture_guard_messages.py`
- `.claude/hooks/tests/test_post_edit_dispatcher.py`
- `.claude/hooks/tests/test_journal_post_approval_tracker.py`
- `.claude/hooks/tests/test_hook_data_files_project_first.py`
- `.claude/hooks/tests/test_memory_pager.py`
- `.claude/hooks/tests/test_working_agreements.py`
- `.claude/hooks/tests/test_stop_dispatcher.py`
- `.claude/hooks/tests/test_addons.py`
- `.claude/hooks/tests/_addon_fixture.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/scripts/tests/test_flat_worktree.py`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/tests/test_switch_env_scan.py`

**Pre-written TASK block:**
```
TASK: Move the nine ordinary switches to the helper, and rewrite every test that set an old
  variable to write the file setting instead. Remove the expectedFailure marks from the scan rows
  this block makes pass.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md.
FILES: as listed.
CONSTRAINTS:
  - bypass_env(project=None) and pinned_contract(project=None) keep their names. The
    changed-file check computes its tree root first and passes it.
  - _contract_index.py stays standard-library-only: remove its environment read and add
    set_mode(value). concept-gate.py and bash-gate.py read contract_index and call set_mode once.
  - addon.json helpers gain .claude/hooks/_switches.py and .claude/hooks/_error_log.py; update
    the manifest rows that pin the list.
  - Each switch gets one on row and one off row in its hook's suite, writing the file in a
    temporary project. Keep the row proving concept_gate off leaves the main-checkout guard on.
  - finish-install: replace the kill-switches readiness field with switches; add-on plans keep
    their empty kill-switches list. Import the helper fail-soft (unavailable).
  - .claude/switches.json: every key at its default, plus a $comment naming the local file.
  - Leave the CLAUDE_* strip lists alone. Do not touch any plugin version file.
  - Run every suite listed, plus test_check_hook_registrations.py.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 6. Documents, skills and registries (`python-ai-developer`)

**Depends on:** 5, 14 — blocks 4, 10 and 12 are no longer named: their records read `blocked`, and the loop never releases a block whose dependency reads `blocked`; the fourth security review (14) replaces them. Before amendment 3 this line read "5, 12"; before amendment 2 it read "5, 10".

**Files to touch:**
- `README.md`
- `CONTRIBUTING.md`
- `.claude/hooks/hooks.json`
- `skills/design-first/SKILL.md`
- `skills/contract-accuracy/SKILL.md`
- `skills/verify-before-done/SKILL.md`
- `skills/promote-ui-rule/SKILL.md`
- `skills/auto-improve-finish-install/SKILL.md`
- `skills/auto-improve-strict-shell-gate-install/SKILL.md`
- `skills/auto-improve-strict-shell-gate-uninstall/SKILL.md`
- `skills/auto-improve-codegraph-install/SKILL.md`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/tests/test_switch_env_scan.py`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`

**Pre-written TASK block:**
```
TASK: Rewrite the documents and skill text for file settings, rewrite INV-12 and K-3 of
  test_plugin_manifests.py, and record the mechanism and terms in the registries. Remove the last
  expectedFailure marks.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md, the skill-text
  table of the Inventory. This block runs after the ordinary switches block (5) and the fourth
  security review (14) have passed; read the report
  t14-security-re-review-round-four-security-auditor.md, the blocked reviews
  t12-security-re-review-round-three-security-auditor.md and
  t10-security-re-review-security-auditor.md, and the second run sheet
  t9-live-prompt-trial-second-round-senior-test-engineer.md for the residual-risk wording.
FILES: as listed.
CONSTRAINTS:
  - README: replace the variable table with a switch table (key, values, default, effect,
    allowed in), show the whole switch file to edit in an editor, and add a section on the
    Database override arm with PowerShell and POSIX commands for the person's own terminal and
    the stated residual risk as the contract's "Residual risk" paragraph words it: prompts
    answered by code, the arm not tied to a command, the allow-rule result of the second live
    trial report (t9) with its limits (one rule, one settings layer, default mode, one host
    version), that an older installed copy of the plugin knows no arm and blocks, and that
    acceptEdits, plan and dontAsk were not tried live. Add _switches.py to the helper
    lists. Leave "Change notes by version" as written and add a dated note for this change. The
    note names apart, as fixes of behaviour older than this contract: a human-only script after
    quoted text in the same call was allowed with no prompt (re-review P1), including after a
    trailing backslash before a closing quote or an escaped quote (t12 P1), and a link at the
    database guards' rules file to a named pipe could hang them (I1). It also names: a
    human-only script after a shell keyword, a prefix command or inside backticks was allowed
    with no prompt (t12 P2), and a link at either database guard's audit log (db-guard.log,
    db-research.log) or log folder could hang or redirect its audit write (t12 I2); such a log
    is now skipped, so keep .claude/logs a real folder. It also says that a rules file which is a link to a network drive or share now
    counts as unreadable, so every database is protected; keep the rules file a regular file in
    the project folder. A shape the guard now reads as invoked in either shell is blocked even
    when the other shell would only mention it; the person runs it by hand.
  - CONTRIBUTING: a new switch is one catalog entry, one README row and one on/off test pair,
    never an environment read.
  - Delete the CLAUDE_CONTRACT_SKIP and CLAUDE_VERIFY_REVIEW_GATE text as the table says.
  - INV-12 compares the README table with the catalog. K-3 becomes "concept-gate.py reads the
    concept_gate switch through the helper". Keep the add-on scan rows.
  - Registries: append through .claude/scripts/registry_append.py only. Corrections to
    "Disposable migration dry-run DB" and "Session-start context delivery", the Switch file and
    switch helper mechanism, a correction to the Add-on term, and the five new terms. Amendment
    2 adds two corrections: "Guard rules file" (the database guards read it through
    read_regular_file_bytes) and "Guard fallback mode" (the read-only guard is a new user, with
    an inline regular-file reader).
  - Do not touch any plugin version file. Run test_plugin_manifests.py,
    test_switch_env_scan.py, test_skill_script_lookup.py and validate_registries.py
    --check-structure.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 7. Final review (`fullstack-code-reviewer`)

**Depends on:** 5, 6, 14 — blocks 4, 10 and 12 are replaced by the fourth security review (14), as for block 6. Before amendment 3 this line read "5, 6, 12"; before amendment 2 it read "5, 6, 10".

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t7-final-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review the whole parent branch against the contract, and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md. This block runs
  after blocks 5, 6 and the fourth security review (14) have passed. The security fixes (8, 11
  and 13) are in the branch through block 14's dependencies; the second live trial (9) and the
  blocked reviews (10 and 12) are not in that chain but merged before block 14 was released.
FILES: .claude/reviews/2026-11-16-file-based-switches/t7-final-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check each acceptance criterion of the brief (the plugin mirror as declared in Extension
    Points), every Inventory row, every switch rule, and that no expectedFailure mark is left in
    the three new test files.
  - Run the landing's own checks verbatim: the full hook and script suites,
    test_check_hook_registrations.py, validate_registries.py --check-structure, and
    check_version_bump.py in parent mode. Record each exit code.
  - List in Disposition the global CLAUDE.md lines the landing pull request body must name.
  - Check that the folder .claude/reviews/2026-11-16-file-based-switches/ holds no effective
    blocked report: the t4, t10 and t12 reports must all be named in the supersedes list of the
    passing fourth review's Gate Output
    (t14-security-re-review-round-four-security-auditor.gate.json). If one is still effective,
    the verdict is blocked.
  - Write the artefact in the template's six-section shape; the file does NOT exist yet. Name
    base..head. One verdict line, alone on its line: "**Verdict:** pass",
    "**Verdict:** pass-with-findings" or "**Verdict:** blocked". Write the Gate Output beside it.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 8. Security review fixes (`python-ai-developer`)

**Depends on:** 2 — it fixes the findings of block 4, but does not name block 4, because the loop never releases a block whose dependency reads `blocked`.

**Files to touch:**
- `.claude/hooks/db-destructive-guard.py`
- `.claude/hooks/db-research-readonly-guard.py`
- `.claude/hooks/_switches.py`
- `.claude/hooks/tests/test_database_override.py`
- `.claude/hooks/tests/test_switches.py`

**Pre-written TASK block:**
```
TASK: Fix findings B1, W1, W2, W4 and N1 of the security review, each with test rows, and
  nothing else.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (the amended
  No-prompt classes, Arm-write, Fresh-arm and Broken-file rules) and the review at
  .claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md
  (findings, probes O10 to O14, routes R3, R4 and S5).
FILES: as listed. db-research-readonly-guard.py changes only where it carries the same code
  (its inline name test and its own prose masking), so the two guards stay in step.
CONSTRAINTS:
  - Write each new row first and see it fail at the parent tip, then fix.
  - B1: decide the no-prompt class from every matched target (any target classed human-only),
    not from the chosen block reason. When true, do not claim the arm, block, and print the
    human-only instruction. Rows, armed, default mode: human-only plus the EF argument-position
    check (O12), human-only plus a row-deleting statement on a protected database (O13), an EF
    forward update plus the argument-position check (O14). Each expects exit 2, no ask JSON and
    the arm still in place. Keep the human-only-alone row (O11).
  - W1: normalise the edit tools' target path before the last-part name test (slashes folded,
    "." and ".." resolved, trailing dots and spaces dropped from each part), in the helper's name
    test and in each guard's inline copy. Rows: Write to <arm>/. and <arm>/x/.. with forward
    slashes and with backslashes, all refused. Control: a Write to
    <p>/.claude/database-override.once/../notes.md is allowed (its normalised last part is
    notes.md). One fallback row with the helper removed.
  - W2: for the Arm-write rule only, a git segment with a real output redirection to a named
    file (> or >>, with or without a stream number, followed by a path) is not prose. A stream
    duplication such as 2>&1 and a plain pipe do not count. Do not change the masking used for
    destructive-command detection, and do not change _shell_write_targets.py. Rows refused:
    git commit -m "x" > "<arm>", the same after git tag and git notes, and
    git commit -m "x" 2> "<arm>". Controls allowed: git commit -m "<names the arm>" 2>&1 | tail -n 5;
    a commit message, a pull request body and a search pattern that only mention the name.
  - W4: in the switch reader, where os.O_NONBLOCK exists (POSIX), open the file read-only and
    non-blocking, check its kind on the open descriptor (fstat), and close it unread unless it
    is a regular file; anything else is unreadable under the Broken-file rule. On Windows (no
    O_NONBLOCK, no named pipes at a file path), when the switch file is a link, judge the link
    target's drive from the local drive table with no network access first; a network drive or
    a \\server\share target is unreadable and never opened. Rows: (POSIX only, skipped
    elsewhere) a named pipe at switches.local.json gives every default and one report, and the
    hook process finishes within a short timeout, so a regression fails instead of hanging.
    (Windows only, skipped when a link cannot be created) a link at switches.local.json to a
    \\server\share path gives every default and one report, within the same timeout.
  - N1: an arm older than 15 minutes or more than 60 seconds in the future is stale: removed,
    blocked. Rows: an arm dated one day ahead blocks and is removed; an arm 30 seconds ahead
    still asks; a claim dated one day ahead is removed by the sweep.
  - Run the existing guard suites unchanged and record them green: test_db_destructive_guard.py,
    test_db_guard_path_allowlist.py, test_readonly_guard_disposable_exemption.py,
    test_worktree_path_guards.py, test_shell_write_targets.py, test_switch_env_scan.py. If any of
    their rows changes outcome, stop and report an AMENDMENT; do not edit them.
  - Plugin version (project CLAUDE.md, Parent Branch Delivery Rule): this sub-task pull request
    goes into feature/file-based-switches and does NOT raise the version. Do not touch
    plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json or
    .claude-plugin/marketplace.json. check_version_bump.py runs in parent mode on this pull
    request and requires the head's version to equal the base's. The landing raises it once.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 9. Live prompt trial, second round (`senior-test-engineer`)

**Depends on:** 2

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t9-live-prompt-trial-second-round-senior-test-engineer.md`

**Gate Output, written beside the artefact by the same agent and deliberately not listed above:** `.claude/reviews/2026-11-16-file-based-switches/t9-live-prompt-trial-second-round-senior-test-engineer.gate.json`. It is not declared because the landing's blocked-report check names a task's reports from its declared review files, and a `.gate.json` is never a report, so declaring it would make a blocked record of this block impossible to supersede.

**Pre-written TASK block:**
```
TASK: Write the run sheet for a second person-run trial of the prompt route, covering what the
  first trial and the security review left unproven. Do not run it; a person runs it in a real
  Claude Code session and sets the verdict before this pull request merges.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (Person-present
  rule, Uncertain Assumptions, the Residual risk paragraph); the first run sheet
  t3-live-prompt-trial-senior-test-engineer.md and finding W3 of the t4 security review.
FILES: the run sheet only. It does NOT exist yet; you create it.
CONSTRAINTS:
  - Header line, alone on its line: "**Verdict:** blocked", plus the line "Results pending: a
    person runs the steps below". Merged unchanged, it holds the re-review.
  - Every destructive command in the steps targets a database name that does not exist on the
    local server, so a command the host wrongly allows fails harmlessly. Name destructive
    statements in words, never as literal command text (the guard refuses such files).
  - Steps 6 to 10, numbered after the first trial's five, each with a PowerShell command, an
    Expected line and an Observed line. Before step 6, record the commit the trial runs against
    (git rev-parse HEAD in the parent-branch checkout the session starts from) in the header.
    (6) With every Claude Code session closed, add by hand, in an editor, to
    .claude/settings.local.json an allow rule matching sqlcmd for the shell tool the session
    uses (record the exact rule text). Save it, record the file's save time
    ((Get-Item .claude\settings.local.json).LastWriteTime), then start a NEW session, because
    permission rules may be read only at session start, and record that session's start time.
    The Observed line must show the session started after the save; otherwise the step is void
    and is run again. Arm from the person's own terminal, and in default mode ask Claude to run
    the statement through sqlcmd -Q. Expected: the prompt still appears;
    decline; then remove the rule. If no prompt appears, the person sets the verdict to
    blocked. (7) acceptEdits mode (claude --permission-mode acceptEdits): a prompt; declining
    leaves no arm. (8) plan mode: record whether a prompt appears or the host refuses to run
    the command; either way nothing runs unprompted. (9) dontAsk mode: blocked, arm kept; then
    remove the arm by hand. (10) Record the Claude Code version, and state that a missing
    permission mode cannot be produced from a normal session and rests on the unit rows.
  - The six fixed sections. "## Evidence" holds the person's observations. Write the Gate Output
    t9-live-prompt-trial-second-round-senior-test-engineer.gate.json beside it with
    supersedes [] and checklist []; it supersedes nothing, because the first trial's report
    stays in force.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 10. Security re-review (`security-auditor`)

**Depends on:** 8, 9

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t10-security-re-review-security-auditor.md`

**Gate Output, written beside the artefact by the same agent and deliberately not listed above:** `.claude/reviews/2026-11-16-file-based-switches/t10-security-re-review-security-auditor.gate.json`, for the same reason as block 9. It is the file whose `supersedes` list retires the t4 report.

**Pre-written TASK block:**
```
TASK: Re-review the database override after the fixes block and the second live trial, and
  write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md; the blocked
  report .claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md;
  the second run sheet t9-live-prompt-trial-second-round-senior-test-engineer.md.
FILES: .claude/reviews/2026-11-16-file-based-switches/t10-security-re-review-security-auditor.md
CONSTRAINTS:
  - Name the commit range reviewed, base..head: the fixes block's merge into the parent branch.
    Record the commit the t9 run sheet says it ran against, and say whether the reviewed guard
    files differ between that commit and your head.
  - Re-run the t4 probes that failed (O10, O12, O13, O14, R3, R4, S5) and the whole route table;
    check W4 by reading, and by running the named-pipe row if a POSIX host is available.
  - Read the t9 observations. If step 6 shows that an allow rule skipped the prompt, the
    verdict is blocked. Check that acceptEdits, plan and dontAsk behave as the Person-present
    rule says.
  - Check that the contract's Residual risk paragraph now names every class you know of,
    including W3(a) and W3(b), and that W5, N2 and N3 are dispositioned in Failure Modes.
  - Write the artefact in the template's six-section shape; the file does NOT exist yet. End the
    header with one verdict line, alone on its line: "**Verdict:** pass",
    "**Verdict:** pass-with-findings" or "**Verdict:** blocked".
  - Write the Gate Output t10-security-re-review-security-auditor.gate.json beside it, as the
    template says. On pass or pass-with-findings its supersedes list is exactly
    ["t4-security-review-security-auditor.md"]. On blocked it is [] (a report that failed to
    clear a blocker must not retire it); the next re-review then supersedes both blocked reports.
  - A blocked verdict holds blocks 6 and 7. It leads to an architect amendment of this
    contract that adds a further fix block and a further re-review block, as this round did;
    no block is added without that amendment. If the block comes from step 6 of t9 (an allow
    rule skipped the prompt), the amendment withdraws the override instead (user answer
    2026-11-18).
  - Edit no other report. Do not touch any plugin version file.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 11. Security review fixes, round two (`python-ai-developer`)

**Depends on:** 8 — it fixes the findings of the re-review (block 10), but does not name block 10, because the loop never releases a block whose dependency reads `blocked` (the same convention as block 8 and block 4).

**Files to touch:**
- `.claude/hooks/db-destructive-guard.py`
- `.claude/hooks/db-research-readonly-guard.py`
- `.claude/hooks/_switches.py`
- `.claude/hooks/tests/test_database_override.py`
- `.claude/hooks/tests/test_switches.py`
- `.claude/hooks/tests/test_db_destructive_guard.py`

`db-research-readonly-guard.py` is listed only for I1 (it reads the same rules file with a plain open, `:207`; user answer 2026-11-19: include I1). L1 is accepted, so its decision code is not changed. `test_db_destructive_guard.py` is listed only so a row that pins one of the P1 shapes as allowed can be retired by name (see the constraints); no other change to it is allowed. The rules-file reader is the switch helper's regular-file check, exposed under a public name, so no new helper file is added.

**What the rows prove, plainly (user answer 2026-11-19, "Test the destructive guard alone").** The destructive guard is the deciding guard for B1 and P1, and only its rows expect a block. The read-only guard has no human-only class and is not changed: its rows pin today's accepted behaviour (L1), which is that armed, on a shape that holds a database write, it asks and claims the arm, and on a shape with no database statement it allows, armed or not. This contract does **not** claim that both guards block these shapes. In a live session both guards run on one call, so an armed O13 or H7 spends the person's arm on the read-only guard's ask while the destructive guard blocks; whether the host then shows a prompt rests on the ASSUMED "a block beats an ask" (Uncertain Assumptions).

**Pre-written TASK block:**
```
TASK: Fix findings B1, P1, W4 (Windows) and I1 of the security re-review, each with test rows,
  and nothing else.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (the No-prompt
  classes rule's invoked-or-mentioned sentence, the Broken-file rule, the Guard rules file entry
  under Reused Mechanisms, Failure Modes); the re-review
  .claude/reviews/2026-11-16-file-based-switches/t10-security-re-review-security-auditor.md
  (findings B1, P1, W4, I1; the "Human-only placement" table H1 to H7, O13, O13b, O13e; the
  Disposition) and the first review t4-security-review-security-auditor.md (B1, probes O11 to
  O14). Read both reports in full. Their clause order and script paths are exact; their
  destructive statements are named in words by the reports' own rule, so rebuild each one from
  those words by string joining, as the existing rows do.
FILES: as listed. db-research-readonly-guard.py changes only for I1.
CONSTRAINTS:
  - RED before GREEN, in this one block (the block 8 convention): commit the new rows first, run
    them at the parent tip, and list in the pull request body each new row with its outcome at
    the tip and at your head. Every destructive-guard row copied from a reported probe (the
    "Copied probes" list below) and every hang row MUST fail (or time out) at the tip. A copied
    probe that passes at the tip has been mistranscribed (script first, or a bare script name
    with no folder): fix the row until it fails at the tip; never relabel it a control. The only
    rows allowed to pass at the tip are the ones this TASK names as controls or pins. The fix
    commit comes after.
  - B1 and P1: fix the classifier, not the decision. Change _in_command_position (and only what
    _human_only_script_hits needs from it) so the No-prompt classes rule's sentence holds. The
    change may only turn a mention into an invocation; every shape the tip classes as invoked
    stays invoked. Text inside the quoted argument of a known launcher (bash -c, sh -c, cmd /c,
    cmd /k, powershell -Command, -c, iex, Invoke-Expression) is command text: split it into
    segments the same way, and a script that starts a segment there is invoked. Do not change
    the human_only flag in _decide, which block 8 got right.
  - Script spelling in every row: the folder path, never the bare name, because the defect needs
    a folder separator before the name: tools/db-protection/update-dev-database.cmd (forward
    slashes) in the bash rows, tools\db-protection\update-dev-database.cmd in the PowerShell
    rows. A probe that exists in one shell only (O13e, H3, Write-Host 'x'; <script>) is written
    once, in that shell. A row with && keeps it as written: the guard judges text, and Windows
    PowerShell 5.1 not running && does not change the guard's verdict.
  - Copied probes, the destructive guard alone, each row in its own fresh temporary project with
    its own arm (never both guards on one arm):
      armed, default mode, expect exit 2, no ask JSON, the arm still in place, the human-only
      instruction in the block text: O13 (row delete on a protected database, then ";", then
      the script), O13e (its PowerShell form), H7 (removal of a non-disposable database
      through sqlcmd -Q, then ";", then the script), H6 (echo "a" ; the script), and the t10
      Disposition's cd "<p>" && the script and Write-Host 'x'; the script.
      no arm, expect exit 2 (blocked, not allowed): H1 echo "start" ; the script; H3 PowerShell
      Write-Host 'x'; the script; H4 cd "<p>" && the script; H5 echo "a" && the restore script
      with its recover flag.
  - Read-only guard pins (L1, accepted; today's behaviour, expected the same at the tip and at
    head, and named as pins in the pull request body): armed, O13, O13e and H7 give the ask JSON
    and the arm renamed to the claim; armed, H6 and the cd and Write-Host forms give exit 0 and
    the arm kept; no arm, H1, H3, H4 and H5 give exit 0. No row expects the read-only guard to
    block these shapes.
  - Controls (destructive guard, pass at the tip and at head): O11 (the script alone), O12,
    O13b (script first) and O14 block; invoked inside a quoted launcher argument blocks, with no
    arm: bash -c "cd x; <script>", cmd /c "echo a & <script>",
    powershell -Command "Write-Host x; <script>". Must stay allowed: a commit message, an echo
    text, a grep pattern and a pull request body that name the script inside quotes; the script
    name as an argument of another command.
  - Existing guard suites unchanged and green: test_db_destructive_guard.py,
    test_db_guard_path_allowlist.py, test_readonly_guard_disposable_exemption.py,
    test_worktree_path_guards.py, test_shell_write_targets.py, test_switch_env_scan.py, and the
    db-protection fixture suite. If a row there expects ALLOW for one of the P1 shapes (a
    human-only script invoked after quoted text), it pins the defect: retire it by name in
    test_db_destructive_guard.py, replace it with the blocking row, and name both in the pull
    request body. Any other row that changes outcome: stop and report an AMENDMENT; do not edit
    it.
  - W4 (Windows): in _read_regular_file_bytes, on every platform open with os.open (O_RDONLY,
    plus O_BINARY and O_NONBLOCK where they exist), then os.fstat on the descriptor, and close it
    unread unless S_ISREG; anything else is unreadable under the Broken-file rule. Keep the
    link-target check before the open, and fix _network_link_reason so a device-namespace target
    (\\.\..., or \\?\... not followed by a drive letter) is unreadable and never opened, instead
    of being read as a relative local path. Rows, Windows only: a symbolic link at
    switches.local.json to a listening named pipe (for example a
    multiprocessing.connection.Listener on \\.\pipe\<unique name> that accepts and never
    writes), in the \\.\ and the \\?\ spelling, gives every default and one report, with the
    hook run as a separate process under a short timeout so the row fails instead of hanging.
    Skip with the stated reason "symbolic link creation not permitted on this host" when
    os.symlink raises a privilege error; skip on POSIX with the reason that the POSIX
    named-pipe rows cover it. Keep the POSIX named-pipe rows green.
  - Expose the reader under the public name read_regular_file_bytes (the Commands row "Read
    regular file"); keep the private name as an alias for the helper's own callers.
  - I1 (user answer 2026-11-19: yes): both database guards read db-destructive-guard.rules.json
    through the same check. Bind the helper's read_regular_file_bytes with getattr; keep an
    inline fallback copy in each guard (Guard fallback mode), because the rules load at import
    and must fail closed with the helper missing. Each inline copy keeps BOTH parts: the Windows
    link-target check (network drive, \\server\share, device namespace) and the
    open-then-fstat regular-file check. A file that fails the check takes the loader's existing
    fail-closed result: the destructive guard treats every database as protected, the read-only
    guard withdraws the disposable exemption. A regular file decodes exactly as today. Rows,
    per guard: a pipe link at the rules file (the same Windows skip rules) makes the guard
    finish within the short timeout with its strict-default outcome (the destructive guard
    blocks a removal of a non-disposable database; the read-only guard blocks a write on a
    disposable-named database it would exempt today); a rules file that is a link to a
    \\server\share path takes the same strict default (accepted fail-closed behaviour, Failure
    Modes I1); a regular rules file still loads as before.
  - Fallback rows (MECHANISMS.md line 64, part 4: one test per inline copy, per spelling, run
    against a stale helper as well as a deleted one): for EACH of the two guards' inline readers,
    with the helper deleted AND with a stale helper that lacks read_regular_file_bytes, a pipe
    link in the \\.\ spelling, a pipe link in the \\?\ spelling, and a \\server\share link each
    give the strict default within the timeout; a regular rules file loads.
  - Do not fix L1 and do not touch the read-only guard's decision code (L1 is accepted in
    Failure Modes). Do not change _shell_write_targets.py or the destructive-detection masking.
  - Plugin version (project CLAUDE.md, Parent Branch Delivery Rule): this sub-task pull request
    goes into feature/file-based-switches and does NOT raise the version. Do not touch
    plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json or
    .claude-plugin/marketplace.json. check_version_bump.py runs in parent mode on this pull
    request and requires the head's version to equal the base's. The landing raises it once.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 12. Security re-review, round three (`security-auditor`)

**Depends on:** 11 — it re-reviews the findings of blocks 4 and 10, but names neither, because both records read `blocked`.

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t12-security-re-review-round-three-security-auditor.md`

**Gate Output, written beside the artefact by the same agent and deliberately not listed above:** `.claude/reviews/2026-11-16-file-based-switches/t12-security-re-review-round-three-security-auditor.gate.json`, for the same reason as blocks 9 and 10. It is the file whose `supersedes` list retires the t4 and t10 reports.

**Pre-written TASK block:**
```
TASK: Re-review the database override and the switch reader after the second fixes block, and
  write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md; the blocked
  reports .claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md
  and t10-security-re-review-security-auditor.md; the second run sheet
  t9-live-prompt-trial-second-round-senior-test-engineer.md.
FILES: .claude/reviews/2026-11-16-file-based-switches/t12-security-re-review-round-three-security-auditor.md
CONSTRAINTS:
  - Name the commit range reviewed, base..head: the second fixes block's (11) merge into the
    parent branch. Say whether the reviewed guard and helper files differ between that merge and
    your head. Work in scratch copies under %TEMP% (git archive or a clone), not in a worktree
    under the checkout.
  - Re-run every t4 and t10 probe that failed, in its ORIGINAL clause order, with the folder
    path of the script, in the bash form and the PowerShell form where the probe exists in both
    (O13e, H3 and the Write-Host form exist in PowerShell only): O13, O13e, H1, H3, H4, H5, H6,
    H7, the t10 Disposition's cd and Write-Host forms, and t4's O10, O12, O14, R3, R4 and S5.
    The destructive guard must block each; report the read-only guard's outcome beside it (L1
    is accepted: armed, it asks on the shapes with a database write), and state what evidence
    there is for "a hook block beats a hook ask". Also run the quoted-launcher rows
    (bash -c "cd x; <script>", cmd /c, powershell -Command): they must block. Then re-run the whole override
    decision set (O0 to O20), the whole route table, the shared-claim and fallback probes (P1 to
    P9), and the control rows (script mentioned inside quotes stays allowed). Report each with
    its result at head.
  - Check W4 by a real attempt on this Windows host: a symbolic link at switches.local.json to
    a listening named pipe, in the \\.\ and \\?\ spellings; the helper must finish at once with
    every default. Check I1 the same way at the rules file, for both database guards, with the
    helper present, deleted and stale. If a link cannot be created, say so; that is not a pass.
  - Check the contract's Residual risk paragraph (W3 (a) and (b) as amended, the t9 limits, the
    Windows pipe-link route) and the Failure Modes dispositions (W4, B1, P1, I1, L1 accepted,
    t9 steps 7 to 9 residual, W5, N2, N3). As information, list other hooks that read a rules
    file with a plain open (same class as I1, out of this contract's scope).
  - Run the guard suites verbatim and record each exit code: test_switches.py,
    test_database_override.py, test_db_destructive_guard.py, test_db_guard_path_allowlist.py,
    test_readonly_guard_disposable_exemption.py, test_worktree_path_guards.py,
    test_shell_write_targets.py, test_switch_env_scan.py.
  - Write the artefact in the template's six-section shape; the file does NOT exist yet. End the
    header with one verdict line, alone on its line: "**Verdict:** pass",
    "**Verdict:** pass-with-findings" or "**Verdict:** blocked".
  - Write the Gate Output t12-security-re-review-round-three-security-auditor.gate.json beside
    it, as the template says. On pass or pass-with-findings its supersedes list is exactly
    ["t4-security-review-security-auditor.md", "t10-security-re-review-security-auditor.md"].
    On blocked it is [] (a report that failed to clear a blocker must not retire one).
  - A blocked verdict holds blocks 6 and 7. It leads to an architect amendment of this
    contract that adds a further fix block and a further review block, as this round did; no
    block is added without that amendment.
  - Edit no other report. Do not touch any plugin version file.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 13. Security review fixes, round three (`python-ai-developer`)

**Depends on:** 11 — it fixes the findings of the third security review (block 12), but does not name block 12, because the loop never releases a block whose dependency reads `blocked` (the same convention as blocks 8 and 11, which name neither 4 nor 10).

**Files to touch:**
- `.claude/hooks/db-destructive-guard.py`
- `.claude/hooks/db-research-readonly-guard.py`
- `.claude/hooks/tests/test_database_override.py`
- `.claude/hooks/tests/test_db_destructive_guard.py`

`db-research-readonly-guard.py` is listed for I2 only (user answer 2026-11-20: I2 extended to both guards): its `_audit` appends to `<project>/.claude/logs/db-research.log` with a plain open on its block path, the same class as the destructive guard's `db-guard.log`. Its decision code is not changed (L1 accepted; it has no human-only class). Its I2 rows go in `test_database_override.py`, which already runs both guards as separate processes and holds block 11's pipe-link rows for both; `test_readonly_guard_disposable_exemption.py` runs unchanged. `_switches.py` is not listed: the Audit-log rule needs no helper entry point, and the classifier lives in the destructive guard. `test_db_destructive_guard.py` is listed only so a row that pins one of t12's B1, P1 or P2 shapes as allowed can be retired by name (see the constraints); no other change to it is allowed.

**What the rows prove, plainly.** As in block 11, the destructive guard is the deciding guard for B1, P1 and P2, and only its rows expect a block. This contract does not claim that the read-only guard blocks any of these shapes. Per t12, armed: on N2a and K1 to K6 (K1 to K3 apply because P2 is in this block) it asks and claims the arm (L1, accepted), and whether the host then shows a prompt rests on the ASSUMED "a block beats an ask"; on N1b and N1a it allows and keeps the arm. For I2 both guards have rows, because each writes its own audit log.

**Pre-written TASK block:**
```
TASK: Fix findings B1, P1 (round three), P2 and I2 (I2 in both database guards) of the third
  security review, each with test rows, and nothing else.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (the No-prompt
  classes rule's readings and command-start words, the Audit-log rule, Failure Modes, the
  amendment 3 Open Questions, answered 2026-11-20); the review
  .claude/reviews/2026-11-16-file-based-switches/t12-security-re-review-round-three-security-auditor.md
  (findings B1, P1, P2, I2; the Evidence table "B1 and P1 shapes not covered by block 11";
  the Disposition). Read it in full. Its row ids, clause order, script paths, quotes and escape
  characters are exact; its destructive statements are named in words by the report's own
  rule, so rebuild each one from those words by string joining, as the existing rows do. Name
  clash: t12's findings P1 and P2 are not t4's shared-claim probes P1 to P9, and t12's findings
  N5 and N6 are not its probe shapes N5 and N6; use the t12 row ids for rows.
FILES: as listed.
CONSTRAINTS:
  - RED before GREEN, in this one block (the block 8 and block 11 convention): commit the new
    rows first, run them at the parent tip, and list in the pull request body each new row with
    its outcome at the tip and at your head. Every row copied from t12 (the "Copied rows" lists
    below) and every hang row MUST fail (or time out) at the tip. A copied row that passes at
    the tip has been mistranscribed (a lost backslash or backtick, the script first, a bare
    script name with no folder): fix it until it fails at the tip; never relabel it a control.
    The only rows allowed to pass at the tip are the ones this TASK names as controls. The fix
    commit comes after.
  - B1 and P1: fix the classifier only (_starts_a_command, _in_command_position and only what
    _human_only_script_hits needs from them). Implement all four readings of the No-prompt
    classes rule and class the script as invoked when ANY of them says so: (1) the readings in
    force at the tip; (2) a bash reading: a backslash escapes the next character outside quotes
    and inside double quotes, nothing is escaped inside single quotes, $'...' takes backslash
    escapes, and a backtick outside single quotes opens a command segment (substitution), as
    $( does; (3) a PowerShell reading: a backtick escapes the next character inside and outside
    double quotes and never opens a segment, "" and '' are doubled quotes, a backslash is a
    plain character; (4) a quote-blind reading: strip the folder-prefix token and an optional
    quote before it; invoked when the nearest preceding non-space character is ; & | ( { or a
    newline (never a backtick). The backtick rule lives in the bash reading only, so it cannot
    conflict with the PowerShell reading: each reading is computed on its own and the results
    are joined by "any". All four readings are part of the Data Shapes rule; none is optional.
    Every shape the tip classes as invoked stays invoked. Do not change the human_only flag in
    _decide, the prose masker or _shell_write_targets.py.
  - Script spelling: tools/db-protection/update-dev-database.cmd (forward slashes) in bash rows,
    tools\db-protection\update-dev-database.cmd in PowerShell rows, exactly as t12 writes each
    row. A row that exists in one shell only is written once, in that shell.
  - Copied rows, the destructive guard alone, each row in its own fresh temporary project with
    its own arm (never both guards on one arm):
      armed, default mode, expect exit 2, no ask JSON, the arm still in place, the human-only
      instruction in the block text: N1a, N1b, N2a, K4, K5, K6.
      no arm, expect exit 2 (blocked, not allowed): N1, N1c, N15, N5, N6 (PowerShell) and N2,
      N2b, N3, N4 (bash).
  - P2 (user answer 2026-11-20: included): implement the command-start words of the No-prompt
    classes rule. A word that itself starts a command segment and is then, do, else, elif, !,
    time, env, nohup, exec, command, builtin, nice, timeout, xargs or sudo passes the start on
    to the next word, after skipping NAME=value assignments and that word's options. An option
    is a word starting with -; an option that takes a value also skips the next word: nice -n;
    sudo -u, -g, -h, -p, -C, -D, -r, -t, -U; env -u, -C; timeout -s, -k; xargs -I, -n, -P, -L,
    -d, -a, -E, -s; exec -a; time has no valued option. After its options, timeout also skips
    its duration. A leading NAME=value is skipped the same way. Exception: command -v and
    command -V (a lookup, not a run) keep the next word a mention. Copied rows: no arm, expect
    exit 2: N7 to N13; armed, as above: K1, K2, K3. Constructed rows, no arm, expect exit 2,
    one per remaining word (else, elif, exec, command, builtin, nice, timeout, xargs, sudo, a
    leading NAME=value) and one per valued option: nice -n 10 <script>, sudo -u root <script>,
    env -u NAME <script>, timeout -s KILL 5 <script>. A constructed row that already blocks at
    the tip is named a control. Controls that must stay allowed: command -v <script> and
    command -V <script> (named mentions, not false blocks); the same words as plain arguments
    (echo then <script>, grep -n time <script>); a script name after one of them inside a
    commit message.
  - I2 (user answer 2026-11-20: included, in BOTH database guards): implement the Audit-log
    rule in each guard's _audit (db-destructive-guard.py, db-guard.log; db-research-readonly-
    guard.py, db-research.log). Every step of the path is checked, not only the append:
      (a) the folders: walk from the folder that holds .claude (the project, or the home
          folder on the guard's no-project fallback) to the log folder (.claude, then
          .claude/logs) with lstat, never following links; each part must be a real folder,
          not a link or, on Windows, any reparse point (junction included); a missing part is
          created with a single-level mkdir and checked with lstat again; mkdir(parents=True)
          and exists() are not used;
      (b) the log: lstat it; missing goes to (d); a link, reparse point or anything but a
          regular file skips the record;
      (c) rotation: only when (b) found a regular file over the size limit; lstat the rotated
          name (.1): when it exists it must be a regular file, otherwise the record is skipped
          and nothing is renamed or removed; then remove it and rename the log; no stat() or
          exists() that follows a link;
      (d) the open: os.open with O_WRONLY | O_APPEND | O_CREAT, plus O_BINARY, O_NONBLOCK and
          O_NOFOLLOW where they exist; os.fstat the descriptor and require S_ISREG before any
          byte is written;
    on any failure close the descriptor unwritten, skip the record, write one line to standard
    error, and write no other file. The decision is never changed. Rows, per guard, the guard
    run as a separate process under a short timeout, each finishing within it with its normal
    decision (the destructive guard blocks a removal of a non-disposable database; the
    read-only guard, with no arm, blocks a write on a protected database, its block path), the record
    skipped and the link target untouched: (Windows only, skipped with the stated reason
    "symbolic link creation not permitted on this host" when os.symlink raises a privilege
    error) a link at the log to a listening named pipe that accepts and never reads, in the
    \\.\ and the \\?\ spelling; a link at the log to a \\server\share path; a directory link
    at .claude/logs into the pipe namespace; a directory link at .claude/logs to a
    \\server\share path; a
    directory link at .claude/logs to another local folder (nothing is written there);
    rotation on a linked log (a link at the log to a regular file larger than the size limit,
    made sparse: the target is neither renamed nor removed); rotation with a link at the .1
    name (its target is not removed). (POSIX only, skipped elsewhere) a named pipe at the log,
    the same. Controls, per guard: a regular log is appended as before; a missing log and a
    missing logs folder are created; a regular log over the limit rotates as before.
  - Controls that must stay green, unchanged: MENTION_ROWS and LAUNCHER_ROWS in
    test_database_override.py, every block 11 row, and O11, O12, O13b, O14. If any of them, or
    any row of the existing suites below other than a named P1/P2-pinning row, changes outcome,
    stop and report an AMENDMENT. Do not drop or weaken a reading to make a row pass.
  - Existing guard suites unchanged and green: test_switches.py, test_db_destructive_guard.py,
    test_db_guard_path_allowlist.py, test_readonly_guard_disposable_exemption.py,
    test_worktree_path_guards.py, test_shell_write_targets.py, test_switch_env_scan.py, and the
    db-protection fixture suite. If a row there expects ALLOW for one of t12's B1, P1 or P2
    shapes (a human-only script invoked after a misread quote, a keyword or prefix command, or a
    backtick), it pins the defect: retire it by name in test_db_destructive_guard.py, replace it
    with the blocking row, and name both in the pull request body. Any other row that changes
    outcome: stop and report an AMENDMENT; do not edit it.
  - Do not fix L1, N6 or the other hooks' plain opens. In the read-only guard change _audit
    only; do not touch its decision code.
  - Plugin version (project CLAUDE.md, Parent Branch Delivery Rule): this sub-task pull request
    goes into feature/file-based-switches and does NOT raise the version. Do not touch
    plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json or
    .claude-plugin/marketplace.json. check_version_bump.py runs in parent mode on this pull
    request and requires the head's version to equal the base's. The landing raises it once.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 14. Security re-review, round four (`security-auditor`)

**Depends on:** 13 — it re-reviews the findings of blocks 4, 10 and 12, but names none of them, because all three records read `blocked`.

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t14-security-re-review-round-four-security-auditor.md`

**Gate Output, written beside the artefact by the same agent and deliberately not listed above:** `.claude/reviews/2026-11-16-file-based-switches/t14-security-re-review-round-four-security-auditor.gate.json`, for the same reason as blocks 9, 10 and 12. It is the file whose `supersedes` list retires the t4, t10 and t12 reports.

**Pre-written TASK block:**
```
TASK: Re-review the database override, the human-only classifier and both database guards'
  audit writes after the third fixes block, and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (amendment 3:
  the No-prompt classes rule, the Audit-log rule, Failure Modes, the residual-risk paragraph,
  and the user's answers to the amendment 3 Open Questions); the blocked reports
  .claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md,
  t10-security-re-review-security-auditor.md and
  t12-security-re-review-round-three-security-auditor.md; the second run sheet
  t9-live-prompt-trial-second-round-senior-test-engineer.md. Naming: keep the t12 report's
  naming. "P1 to P9" are t4's shared-claim and fallback probes; "finding P1" and "finding P2"
  are t12's findings; t12's findings N5 and N6 are not its probe shapes N5 and N6. Say which
  one you mean each time.
FILES: .claude/reviews/2026-11-16-file-based-switches/t14-security-re-review-round-four-security-auditor.md
CONSTRAINTS:
  - Name the commit range reviewed, base..head: the third fixes block's (13) merge into the
    parent branch. Say whether the reviewed guard and helper files differ between that merge
    and your head. Work in scratch copies under %TEMP% (git archive or a clone), not in a
    worktree under the checkout.
  - Re-run every probe that failed in t4, t10 and t12, in its ORIGINAL clause order and spelling,
    in each shell the probe exists in, armed and unarmed as the report ran it: t4's O10, O12,
    O14, R3, R4, S5; t10's O13, O13e, H1, H3 to H7 and the Disposition's cd and Write-Host
    forms; t12's B1 and P1 shapes N1, N1a, N1b, N1c, N2, N2a, N2b, N3 to N6, N15 and K4 to K6;
    t12's P2 shapes N7 to N13 and K1 to K3, and block 13's per-word and valued-option rows.
    The destructive guard must block each; command -v and command -V <script> must stay
    allowed. Report the read-only guard's outcome beside each (L1 is accepted: armed, it asks
    on the shapes with a database write), and state what evidence there is for "a hook block
    beats a hook ask" (block 12's instruction, kept). Also run each new
    shape in a real bash and a real PowerShell with a harmless probe script, as t12 did, and
    report any shape where the real shell runs the script and the guard does not block.
  - Try further spellings of the same rule in both shells (other escapes, nested quotes, here
    strings, line continuations) and report what you find. Also try mentions that one shell
    would not run (a backtick-wrapped name in PowerShell, an escaped name in a commit message)
    and report each new false block; the union reading's false block is accepted in Failure
    Modes, but a mention row from MENTION_ROWS that now blocks is a finding.
  - Re-run the quoted-launcher rows (bash -c, sh -c, cmd /c, cmd /k, powershell -Command,
    pwsh -c, iex, Invoke-Expression): they must block. Re-run the mention controls: they must
    stay allowed. Then re-run the whole override decision set (O0 to O20), the whole route
    table, and t4's shared-claim and fallback probes P1 to P9. Report each with its result at
    head.
  - Real pipe-link attempts on this Windows host, each with a listening named pipe, in the \\.\
    and \\?\ spellings, links made by os.symlink and by cmd /c mklink: W4 at switches.local.json
    (the helper finishes at once with every default); I1 at the rules file, for both database
    guards, with the helper present, deleted and stale; I2 at <project>/.claude/logs/db-guard.log
    (destructive guard) AND at <project>/.claude/logs/db-research.log (read-only guard), each
    with a pipe that accepts and never reads: each guard finishes within a short timeout with
    its normal decision on its block path. Also, for each guard: a directory link at
    .claude/logs (into the pipe namespace and to another local folder), and a linked log over
    the size limit (rotation must neither rename nor remove the link target). If a link cannot
    be created, say so; that is not a pass.
  - Check the contract's Residual risk paragraph (it must close B1, P1, P2 and I2 (both guards)
    or name what stays open, carry the corrected L1 sentence, the t9 limits, W3 (a) and (b)) and
    the Failure Modes dispositions (W4, B1, P1, P2, I2, the union reading's false block, the
    skipped audit record, I1 and its neighbours, L1, t9 steps 7 to 9, N6, W5, N2, N3).
  - Run the guard suites verbatim and record each exit code: test_switches.py,
    test_database_override.py, test_db_destructive_guard.py, test_db_guard_path_allowlist.py,
    test_readonly_guard_disposable_exemption.py, test_worktree_path_guards.py,
    test_shell_write_targets.py, test_switch_env_scan.py.
  - Name destructive statements in words, never as literal command text. Write the artefact in
    the template's six-section shape; the file does NOT exist yet. End the header with one
    verdict line, alone on its line: "**Verdict:** pass", "**Verdict:** pass-with-findings" or
    "**Verdict:** blocked".
  - Write the Gate Output t14-security-re-review-round-four-security-auditor.gate.json beside
    it, as the template says. On pass or pass-with-findings its supersedes list is exactly
    ["t4-security-review-security-auditor.md", "t10-security-re-review-security-auditor.md",
    "t12-security-re-review-round-three-security-auditor.md"]. On blocked it is [] (a report
    that failed to clear a blocker must not retire one).
  - A blocked verdict holds blocks 6 and 7. It leads to an architect amendment of this
    contract that adds a further fix block and a further review block, as this round did; no
    block is added without that amendment.
  - Edit no other report. Do not touch any plugin version file.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both backend and frontend sides
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
- [ ] `Status` flipped to `implemented`
