# Concept Contract — Replace environment-variable switches with file-based switches

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-16
**Requested by:** user
**Status:** approved
**Revision 5:** 2026-11-22, block 15 amendment (amendment 5, narrow). Sub-task t15 (block 15) was dispatched and stopped on the block's own AMENDMENT rule, with no change made. Two lines of block 15 could not both hold. The existing row `r4.16.7` in `test_db_destructive_guard.py` (`:1917`) reads each script in `_DEV_SCRIPTS` with `sed -n` and expects an allow, and block 15 listed `r4.16.1` to `r4.16.9` as controls that must stay green. But the same block removes `sed` from the closed mention list and requires the constructed row `sed -n 1p <script>` to block. Only one instance flips, the update script (`update-dev-database.cmd`, human-only). The `restore-latest.cmd` instance carries no recover flag, so it is not human-only and stays allowed. The other two scripts are not human-only entries. This revision keeps `sed` out of the list. It retires the update-script instance of `r4.16.7` by its exact name (`r4.16.7 sed -n of update-dev-database.cmd  [passes today]`), replaces it with the blocking row `r4.16.7b`, and takes that instance out of the controls that must stay green. That is the only retirement amendment 5 makes. Every other existing allow row that flips still stops block 15 with an AMENDMENT report, and block 15 adds no word to the mention list. The user chose this on 2026-11-22 ("Retire only this row (Recommended)"). The first pass of this revision also drafted a standing retirement rule. The user did not choose it, and it is removed (sixth critique round, BLOCKERs 1 and 2). The text changed is this line; the No-prompt classes rule's Mention positions sentence and its "keep their outcomes" sentence; the inverted-classifier Failure Modes disposition; the residual-risk paragraph's false-block sentence; the amendment-4 recommendation notes and the Amendment 5 Open Question; Lessons referenced; block 15's Depends on note, file note, TASK CONTEXT, and its P3, controls, retirement, older-test search and suite-run constraints; and block 16's CONTEXT and retirement check. Every other block, every dependency and the Delivery shape are unchanged (still sixteen blocks, same graph). The amendment-5 Open Question is answered (user, 2026-11-22). Status is `draft` until the main session's final check. The main session then flips it back to `approved`, which releases block 15 again (its only dependency, block 13, is merged).
**Revision 4:** 2026-11-21, security-review remedy round 4 (amendment 4). The fourth security review (`t14`, pull request 466) read `blocked`. Block 13 cleared every t4, t10 and t12 probe and t12's I2 in both guards (real pipe-link attempts, with a live control at `4a67d1a`), and W4 and I1 still hold. But two spelling classes inside the No-prompt classes rule's own definition still read as "mentioned": a quote opened mid-word right before the script name, and an apostrophe in a `#` comment on an `echo`, `Write-Host`, `git commit` or `grep` line (t14 B1, round four; with no arm the script runs, t14 P1). The comment apostrophe sits in the shared prose masker and also hides every destructive statement on later lines, so an EF removal of the configured database is allowed by both guards with no arm (t14 Q1, critical, older than this contract). t14 also found long valued options not skipped (P2), command starts outside the rule's word lists (P3), the name matched as literal text only (T1), a hard link at either audit log (L2) and stale contract text (W7). This revision adds the fourth fixes block (15) and the fifth security review (16), re-links the documents and final review blocks to block 16, and amends the No-prompt classes rule (mid-word quote, comment-aware masking, long valued options, mention positions, name matching), the Audit-log rule (link count), Reused Mechanisms, Non-Goals, Uncertain Assumptions, Failure Modes and the residual-risk paragraph. The fix of P3 is a design change: the human-only classifier is inverted to fail closed (every visible occurrence of a human-only script name is invoked unless it stands in a named mention position). Blocks 1 to 14 keep their ordinals, headings and ids, and block 14's own text is unchanged. Two decisions were the user's (Open Questions, amendment 4): Q1 (make the shared masker comment-aware, which changes destructive-command detection for everyone) and the inverted classifier with its false-block cost. **Both are answered yes (user, 2026-11-21)**, and the body states both as decided; the "if no" branches are closed. Second pass, 2026-11-21: the fifth critique round's three BLOCKERs and six WARNs are applied in the text (the comment rule is decided by both shells' own quote and escape readings; continuation joining is done per reading, as added readings; both Arm-write consumers get rows and the arm-write comment route is named; rows that cannot fail at the tip get a named-mutation proof; `sed`, `less` and `more` leave the mention list, and `rg` and `git grep` get argument rules; exception (b) follows the whole pipeline; every here-document spelling is named; the Arm-write rule's masking sentence is edited where it stands). The four NITs are deferred, each with its reason under the finding. **Status stays `draft`** until the main session's final check (the amendment-2 handling): block 15 depends only on block 13, which is merged, so an `approved` status releases block 15 at once. Preconditions for the main session before the first dispatch: the t14 report and its Gate Output are merged into the parent branch (done, pull request 466, merge `693a7a4`); sub-issues for blocks 15 and 16 are opened; the t6 and t7 briefs and sub-issues 425 and 426 are refreshed with the new Depends on lines and block text.
**Revision 3:** 2026-11-20, security-review remedy round 3 (amendment 3). The third security review (`t12`, pull request 459) read `blocked`: finding B1 was not cleared for a third round, because the quote scanner `_starts_a_command` reads quotes with one escape model for both shells, so a trailing backslash before a closing quote (`cd "<folder>\"; <script>` in PowerShell, `cd "C:\\w\\" && <script>` in bash) or an escaped quote outside quotes still hides the human-only script; with no arm the same shapes run it with no prompt (P1, older than this contract). t12 cleared W4 (Windows) and I1 by a real pipe-link attempt. This revision adds the third fixes block (13) and the fourth security review (14), re-links the documents and final review blocks to block 14, and amends the No-prompt classes rule, adds the Audit-log rule, and updates Failure Modes, Uncertain Assumptions and the residual-risk paragraph (t12 W6 (a) to (d), and the elevation sentence, t12 N5). Blocks 1 to 12 keep their ordinals, headings and ids, and block 12's own text is unchanged. The two amendment-3 Open Questions are answered (user, 2026-11-20, "take the recommended package"): t12 P2 (a script after a shell keyword, a prefix command or inside backticks) is in block 13, and t12 I2 (a pipe link at an audit log) is in block 13, extended to both database guards (`db-guard.log` and the read-only guard's `db-research.log`). Second pass, same day: the fourth critique round's blocker (the read-only guard does write its audit to the project), five warnings and the NITs are applied, except the budget NIT. Status stays `approved` at the caller's direction; blocks 13 and 14 are not dispatched until their sub-issues exist. Preconditions for the main session before the first dispatch: the t12 report and its Gate Output are merged into the parent branch (done, pull request 459, merge `8a438e5`); sub-issues for blocks 13 and 14 are opened; the t6 and t7 briefs and sub-issues 425 and 426 are refreshed with the new Depends on lines and block text.
**Revision 2:** 2026-11-19, security-review remedy round 2 (amendment 2). The security re-review block (`t10`) read `blocked`: finding B1 was not cleared, because the human-only script is not seen when quoted text comes before it in the same call, and the same cause lets that script run with no arm at all (P1, older than this contract). This revision adds the second fixes block (11) and the third security review (12), re-links the documents and final review blocks to block 12, and amends the No-prompt classes rule, the Broken-file rule, the Guard rules file entry, Uncertain Assumptions, Failure Modes and the residual risk. Blocks 1 to 10 keep their ordinals, headings and ids, and block 10's own text is unchanged. Step 6 of the second live trial was met (with the session start time inferred, not recorded; see Uncertain Assumptions), so the override is **not** withdrawn. Status is `draft` until the user re-approves. Second pass, same day: the user's answers (destructive guard alone decides in block 11's rows; I1 in block 11; L1 accepted; no third live trial) and the critic's third-round blocker and seven warnings are applied. Preconditions for the main session before the first dispatch: the t10 report and its Gate Output are merged into the parent branch (today they sit on the t10 task branch only); sub-issues for blocks 11 and 12 are opened; the t6 and t7 briefs and sub-issues 425 and 426 are refreshed with the new Depends on lines and block text.
**Revision:** 2026-11-18, security-review remedy round 1. The security review block (`t4`, pull request 440) read `blocked`. This revision adds the fixes block, the second live trial block and the security re-review block (8, 9 and 10), re-links the documents and final review blocks to the re-review, and amends the rules and the residual risk the review found wrong. Blocks 1 to 7 keep their ordinals, headings and ids. Status is `draft` until the critic runs and the user re-approves. Second pass, same day: the user's answers ("Accept all") and the critic's round-two warnings are applied (the W2 rule narrowed, the W4 open made non-blocking, a fresh session in the second trial's step 6, the Gate Output files named in blocks 9 and 10).
**Work Item Brief:** .claude/work-items/2026-11-16-file-based-switches.md
**Parent issue:** #419 (https://github.com/lneninger/claude-agentic-auto-improve/issues/419), opened on 2026-11-16 and recorded in the brief's `id:`.
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. Implementer agents refuse to run unless `Status: approved` or `Status: implemented`. The `concept-gate.py` hook reads `Files to touch` to decide whether an edit is allowed. Lifecycle, budget rule and management commands are as in `.claude/templates/concept-contract.md`.

**Short forms used below.** JSON (JavaScript Object Notation) is the text format of the switch files. SHA-256 is a fixed-length fingerprint of a file's bytes. POSIX shells are the shells of macOS and Linux. Standard output and standard error are a hook's normal and error output streams. A byte order mark (BOM) is an invisible marker some editors put at the start of a file. UTF-8 and UTF-16 are text encodings. SDK means software development kit. The *payload* is the JSON input Claude Code sends to a hook. *Fail-soft* means a failed import leaves the defaults in force instead of stopping the hook. An *atomic rename* is a rename the operating system does in one step, so only one process can win it.

**Delivery shape.** This contract has sixteen mergeable blocks, so it is delivered through a parent branch (`feature/file-based-switches`, the brief's `branch:`). It needs the parent issue named above, one sub-issue per block (three new ones for blocks 8 to 10, two more for blocks 11 and 12, two more for blocks 13 and 14, two more for blocks 15 and 16) and a landing pull request. No block raises the plugin version; the landing raises it once. The blocks are named in prose by their headings: the RED tests block, the helper block, the live trial block, the security review block, the ordinary switches block, the documents block, the final review block, the fixes block, the second live trial block, the re-review block, the second fixes block, the third security review, the third fixes block, the fourth security review, the fourth fixes block and the fifth security review. The graph: 1 → 2 → {3, 5}; {2, 3} → 4 (delivered, `blocked`); 2 → 8 (fixing 4's findings; 8 cannot name 4, because the loop never releases a block whose dependency reads `blocked`); 2 → 9; {8, 9} → 10 (delivered, `blocked`); 8 → 11 (fixing 10's findings; 11 cannot name 10, for the same reason); 11 → 12 (delivered, `blocked`); 11 → 13 (fixing 12's findings; 13 cannot name 12, for the same reason); 13 → 14 (delivered, `blocked`); 13 → 15 (fixing 14's findings; 15 cannot name 14, for the same reason); 15 → 16; {5, 16} → 6; {5, 6, 16} → 7. Before amendment 4 the last two edges read {5, 14} → 6 and {5, 6, 14} → 7; before amendment 3, {5, 12} → 6 and {5, 6, 12} → 7; before amendment 2, {5, 10} → 6 and {5, 6, 10} → 7.

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
- **Arm-write rule.** Both database guards refuse a tool call that would write the arm. For the edit tools (Write, Edit, MultiEdit, NotebookEdit) that is a target path whose last part starts with `database-override.`, in any case, judged after the path is normalised the way the operating system opens it: slashes folded, `.` and `..` parts resolved, and trailing dots and spaces dropped from each part. So `<arm>/.` and `<arm>/x/..` are refused. For the shell tools (Bash, PowerShell) it is either a write target found by the shared shell parser `_shell_write_targets.parse_redirect_targets` with that name, or that name in the command text **after** the guard's masking of inert quoted prose (comment-aware since amendment 4, see the No-prompt classes rule's "Comment-aware masker"). For this rule only, a `git` segment with a real output redirection to a named file (`>` or `>>`, with or without a stream number, followed by a path) is not prose, so `git commit -m "x" > "<arm>"` is refused. A stream duplication such as `2>&1` and a plain pipe `|` do not count, so `git commit -m "<mentions the name>" 2>&1 | tail` stays allowed. ~~The masking used for destructive-command detection is unchanged, and the shared parser is not changed.~~ *(amendment 4, fifth critique round WARN; user answer 2026-11-21 to "Comment-aware masker": yes)* The git-redirection exception above is still for this rule only, and the shared parser is not changed. The masker itself changed in amendment 4 for every consumer, this rule included: it blanks a comment only where both shell readings agree on it. Before block 15, an arm write (`New-Item`, `touch`) on a line after a `#` comment holding an apostrophe was hidden from this test by the same span that hid the human-only script (t14 B1 (b)); block 15 has a row for it in each guard. So a commit message, a pull request body or a search pattern that only mentions the name is allowed, while `New-Item`, `touch`, a redirection (also after `git commit`, `git tag` or `git notes`) or a quoted path argument is refused. The check runs before Guard deference and before every other rule, in every copy of each guard, because it reads no project rules.
- **No-prompt classes rule.** Commands the destructive guard classes as `human-only`, and the internal-error path (`_fail_closed`), never offer the prompt. Both block. The class is decided from every target the tool call matched, not from the one reason chosen for the block text: when any matched target is `human-only`, the guard does not touch the arm and blocks, whatever other reason (a protected-database write, the EF argument-position check) the same call also raised. The block text then carries the human-only instruction. A human-only script is **invoked** (and so a `human-only` target) when the word that holds it, quoted or not, is the first word of a command segment (a quote opened inside that word, as in `tools/db-protection/"<script>"` or `"$PWD"/tools/db-protection/'<script>'`, belongs to the word, in every reading; amendment 4, t14 finding B1 (a)), after any launcher word the guard already knows (`call`, `start`, `&`, `sh`, `cmd /c`, `-File` and the rest), wherever the segment stands in the call; segments are split on separators outside quotes (`;`, `&`, `|`, `&&`, `||`, `(`, a newline). Text inside the quoted argument of a known launcher (`bash -c "…"`, `cmd /c "…"`, `powershell -Command "…"` and the rest) is itself command text and is split the same way, so `bash -c "cd x; <script>"` is invoked. ~~It is only **mentioned** when that word is an argument of a command that is not a launcher, such as text inside a commit message or an `echo`.~~ *(reversed by amendment 4, t14 finding P3, by the user's yes of 2026-11-21 to the Open Question "Inverted human-only classifier": a script is mentioned only in a named mention position, see "Mention positions" at the end of this rule)* The classifier may only move a form from mentioned to invoked, never the reverse: every form classed as invoked before amendment 2 stays invoked. One exception, by amendment 4 (t14 B1 (b) and Q1, by the user's yes of 2026-11-21 to the Open Question "Comment-aware masker"): text that the bash reading and the PowerShell reading both treat as a comment, at the same `#`, is blanked by the masker (below), so a name that stands only inside such a comment is no longer read at all. Nothing else in amendment 4 removes a reading or replaces one: continuation joining and empty-quote removal (Name matching, below) add readings beside the unjoined ones, so they too can only move a form toward invoked. Quoted text in an earlier segment never decides it (amendment 2, re-review findings B1 and P1: a closing quote before the script used to hide it, so the arm was claimed and, with no arm, the script was allowed). Where a quote ends depends on the shell, and the guard does not know which shell will run the text, so it does not guess one (amendment 3, t12 findings B1 and P1: one escape model for both shells misread a trailing backslash before a closing quote and an escaped quote outside quotes). The script is invoked when ANY of these four readings says so, each computed on its own: the readings the guard used before amendment 3; a bash reading (a backslash escapes the next character outside quotes and inside double quotes, nothing is escaped inside single quotes, `$'…'` takes backslash escapes, and a backtick outside single quotes opens a command segment, as `$(` does); a PowerShell reading (a backtick escapes the next character inside and outside double quotes and never opens a segment, `""` and `''` are doubled quotes, a backslash is a plain character); and a quote-blind reading (the nearest character before the script's word, skipping spaces, a folder prefix and an optional quote, is a separator: `;`, `&`, `|`, `(`, `{` or a newline, never a backtick). The backtick rule belongs to the bash reading alone, so it never conflicts with the PowerShell reading. All four readings are part of this rule; none is optional. Because the readings are joined by "any", the change can only move a form from mentioned to invoked. Text the prose masker has already blanked (commit messages, `echo` text, search patterns, pull request bodies) is not read again, so those mentions stay allowed. **Comment-aware masker (amendment 4, t14 findings B1 (b) and Q1; user answer 2026-11-21: yes, for all four consumers; revised after the fifth critique round).** The masker pairs quotes only in code, never in a comment: before amendment 4 an apostrophe in a `#` comment opened a quoted "span" that ran across lines to the next apostrophe, and the whole span was blanked as `echo` prose, hiding the human-only script, every destructive statement and every arm write inside it. Every rule below is written so that the masker blanks only what every shell that can receive the text ignores, because blanking less is always the fail-closed direction. **Which reading decides.** Whether a `#` is "outside quotes" and "starts a word" is never decided by the masker's own quote pairing (`_skip_quoted`, which closes a double-quoted span at the first `"` and has no escape model). It is decided by the bash reading and the PowerShell reading of this rule, each with its own escape model as defined above, each scanning the whole text from its start and recognising its own shell's comments, here-documents or here-strings and block comments, so that its quote state after each of them is right. A line comment is blanked only where **both** readings start a line comment at the same `#`. Where they disagree, nothing from that `#` is blanked: an escaped quote before it (bash `echo "a\" # b"`, PowerShell ``Write-Host "a`" # b"``), an escaped space before it (bash `echo a\ # …`, PowerShell ``echo a` # …``), a `$'…'` span, a doubled quote, or any construct only one shell knows. After a disagreement each reading keeps its own quote state, and a later `#` is again blanked only where both agree. (1) In a reading, a `#` starts a line comment when, in that reading, it is outside quotes, not escaped, and starts a word: at the start of the text or a line, or after an unescaped space or tab, `;`, `|`, `&`, `(` or `)`. The comment ends at the end of that physical line in both shells; a trailing backslash or backtick inside a comment does not continue it. A blanked comment is never scanned for quotes. (2) Not a comment in the reading that knows the construct, so never blanked (each follows from the agreement rule, and each is named so it gets rows): a bash here-document body, in every delimiter spelling (`<<WORD`, `<< WORD`, `<<'WORD'`, `<<"WORD"`, `<<\WORD`, a partly quoted tag such as `<<E"O"F`, and `<<-WORD`, whose end line may start with tabs), from the line after the start to the first line that is exactly the tag (after leading tabs for `<<-`), or to the end of the text when no such line exists, whose `#` may be data such as a T-SQL temporary table name; a `<<` outside quotes in the bash reading that the guard cannot parse as one of these starts, and is not `<<<`, ends comment blanking for the rest of the text; a PowerShell here-string, from `@"` or `@'` at the end of a line to a line that starts with `"@` or `'@`; and the rest of a line after PowerShell's stop-parsing token `--%`, whose rest goes to a native program as written. (3) Inside a PowerShell block comment, from `<#` outside quotes in the PowerShell reading to the next `#>`, nothing is blanked and no quote opens a span; a block comment never counts as agreement with a bash line comment. Its lines stay visible, because bash runs every line after the first. The masker has four consumers, all of them get the change, and each gets rows in block 15 (destructive-command detection: the Q1 rows and the masker exclusion and escape rows; each Arm-write test: an arm write after a comment apostrophe, one row set per guard; the human-only classifier: the B1 (b) rows): the destructive guard's destructive-command detection (`db-destructive-guard.py:2471`), its Arm-write test (`:2289`, `redirect_is_code`), the read-only guard's Arm-write test, which loads the destructive guard's masker (`db-research-readonly-guard.py:501-518`), and the human-only classifier, which reads the masked text. The read-only guard's write detection reads the raw text and is not changed. **Command-start words (amendment 3, t12 finding P2; user answer 2026-11-20: included).** A word that itself starts a command segment and is one of `then`, `do`, `else`, `elif`, `!`, `time`, `env`, `nohup`, `exec`, `command`, `builtin`, `nice`, `timeout`, `xargs` or `sudo` does not end the search: the next word, after any `NAME=value` assignments and that word's options, starts the command. An option is a word starting with `-`; an option that takes a value also skips its value, in its short or its long spelling, whether the value is in the next word or after `=` (`nice -n 10`, `sudo -u root`, `env -u NAME`, `timeout -s KILL`; amendment 4, t14 finding P2: also `timeout --signal KILL`, `env --unset NAME`, `nice --adjustment 10`, `xargs --max-args 1`, `sudo --user root`; blocks 13 and 15 list them), and `timeout` also skips its duration. A leading `NAME=value` assignment is skipped the same way. Exception: `command -v` and `command -V` look a name up without running it, so the next word stays **mentioned** (a named mention, not a false block). **Mention positions (amendment 4, t14 finding P3; a design change; user answer 2026-11-21: yes, fail-closed inversion with the closed mention list; revised after the fifth critique round).** Three rounds extended the list of invoking contexts, and each review found more. The test is therefore inverted to fail closed. Every occurrence of a human-only script name that the masker leaves visible is **invoked**. It is **mentioned** only when every reading that sees the occurrence places it in a mention position (an occurrence that exists only in an added joined or spliced reading, Name matching below, is judged by the readings that see it). A mention position is an argument word, or a redirection target, of a segment whose command word (found after launchers and command-start words, as above) is one of these: `echo`, `printf`, `Write-Host`, `Write-Output`, `write`, `cat`, `type`, `Get-Content`, `gc`, `head`, `tail`, `wc`, `grep`, `rg` (argument rule below), `Select-String`, `sls`, `ls`, `dir`, `gci`, `Get-ChildItem`, `Get-Item`, `gi`, `Test-Path`, `cp`, `mv`, `rm`, `chmod`, `Copy-Item`, `Move-Item`, `Remove-Item`, `Rename-Item`, `which`, `where.exe`, `Get-Command`, `command -v` / `command -V`, and `git` followed directly (only `-C <folder>` or `--no-pager` may come between) by `add`, `blame`, `commit`, `diff`, `grep` (argument rule below), `log`, `ls-files`, `mv`, `restore`, `rm`, `show` or `status`. PowerShell words match in any case. ~~`less`, `more`, `sed`~~ *(removed after the fifth critique round: each can run a program from its own arguments in the same command, `sed` through its `e` command or `s///e` flag, also from a program file given with `-f`, and `less` and `more` through a `+` or `!` command, and no argument rule for them is reliable; a name after one of them is now a false block, Failure Modes)*. **Argument rules (fifth critique round).** `rg` is a mention command only when no word of its segment starts with `--pre` (this catches `--pre`, `--pre=…` and `--pre-glob`, which run a program on each file searched). `git grep` is a mention command only when no word of its segment after `grep` starts with `--o` (catching `--open-files-in-pager` and every abbreviation of it git accepts) and no word that starts with a single `-` contains the letter `O` (catching `-O`, `-O<pager>` and a bundle such as `-nO`). **Environment rule (fifth critique round).** A mention command configured by the same call is not a mention command: an occurrence is invoked when its segment has a `NAME=value` word before its command word (also after `env`), or when an earlier segment of the call sets or exports an environment variable (bash `export`, `declare -x`, `typeset -x`, `set -a`, a bare `NAME=value` segment; PowerShell `$env:NAME =`, `Set-Item env:`, `New-Item env:`, `[Environment]::SetEnvironmentVariable`). So `RIPGREP_CONFIG_PATH=<file> rg x <script>` (a config file can add `--pre`), `GIT_EXTERNAL_DIFF=bash git diff -- <script>` and `$env:GIT_PAGER = 'bash'; git grep …` are invoked. Configuration written outside the call's text (a git filter, `diff.external`, `textconv`, `core.pager`, `core.fsmonitor` or hook in the repository's configuration, a ripgrep config file, or an environment variable left by an earlier tool call) can still turn a listed command into a launcher; that is the named text-guard limit below. ~~Block 15 may add a read-only word that an existing must-stay-allowed row needs, naming the word and the row in its pull request body.~~ *(amendment 5, sixth critique round BLOCKER 1: this permission and a retirement rule could not both hold; user answer 2026-11-22: "Retire only this row")* The list is closed for block 15: block 15 adds no word to it. A word that can run a program from its arguments, its environment or its own options is never added (a launcher, a command-start word, `find`, `xargs`, `env`, `source`, `.`, `trap`, `eval`, `Start-Process`, `start`, `Invoke-Item`, `sed`, `less`, `more`, `awk`, `vim`, `git` with `-c` or `--config-env`, `rebase` or `bisect`). ~~If an existing must-stay-allowed row needs one of these, block 15 stops and reports an AMENDMENT.~~ *(amendment 5: widened to every word, below)* Exactly one existing allow row is retired by name because of the list: `r4.16.7 sed -n of update-dev-database.cmd  [passes today]`, the `sed -n` read of the update script, replaced by the blocking row `r4.16.7b` (block 15's constraints). Any other existing allow row that flips under the mention list, whatever word it needs, stops block 15 with an AMENDMENT report. Block 15 neither adds the word nor retires or edits the row. The amendment decides. A quoted string that is the whole value of a variable assignment (PowerShell `$x = "…"`, bash `X="…"`) is also a mention position, because running it later goes through the variable, which is the text-guard limit below. Three exceptions class a mention position as invoked: (a) the occurrence lies inside a substitution (`$(…)`, backticks, `<(…)`, `>(…)`, PowerShell `$(…)`, `@(…)` or a parenthesised expression), unless that substitution is itself, judged the same way outward, an argument word of a mention position; or the segment follows PowerShell's call operator `&` or dot-source `.`. So `$(cat <script>)` as a command, `` `<script>` ``, `eval "$(cat <script>)"`, `bash <(cat <script>)` and `& (Get-Item <script>)` are invoked, while `echo $(cat <script>)` stays a mention. (b) The segment's output reaches a segment whose command word is not a mention command, through a pipe (`|`, bash `|&`), through any chain of pipes, or through a redirection into a process substitution (`> >(…)`): every later segment of the pipeline must itself be a mention position segment, or the occurrence is invoked (`cat <script> | bash`, `cat <script> | grep . | cmd`, `Get-Content <script> | Out-String | iex`, `cat <script> > >(bash)`; fifth critique round: before, only the next segment was looked at). (c) The name is a redirection target of a segment whose command word is not a mention command (`bash < <script>`). Anything else (an unknown command, `find -exec`, `if`, `while`, `eval`, `Start-Process`, `cmd //c`, `--%` and every form the guard does not know) is invoked, and the result is a block that names the script. That is the outcome the user chose for this class. The cost is false blocks: an agent that names the script after a command not in the list (for example `find . -name <script>` or `code <script>`) is blocked and told the script is for a person (Failure Modes, "the inverted classifier"). The scope is the human-only **script** names (`_human_only_script_hits`, shell tools only). The forward EF update class and every other destructive pattern are unchanged. MENTION_ROWS, LAUNCHER_ROWS and every must-stay-allowed row named in block 15 keep their outcomes (since amendment 5, that list leaves out the update-script instance of r4.16.7, which block 15 retires by name and replaces with `r4.16.7b`; this is the only exception). **Name matching (amendment 4, t14 finding T1).** A human-only entry matches its name with or without its `.cmd` or `.bat` extension, with trailing dots (and trailing spaces inside a quoted word), when the next character is not a word character, a dot or a hyphen. So PowerShell `tools\db-protection\update-dev-database`, which Windows resolves through `PATHEXT`, is the script. ~~Before the name is matched, and before the restore script's recover flag is checked, the guard joins bash backslash-newline and PowerShell backtick-newline continuations and removes an empty quote pair (`''` or `""`) that touches a non-space character.~~ *(revised after the fifth critique round BLOCKER: a join applied to the whole text turned PowerShell `Write-Host a \` and a script on the next line, which PowerShell runs, into a mention, and a global backtick join deleted the bash reading's backtick opener)* Each continuation is joined only in the reading of the shell that continues it, and each joined reading is **added** beside the unjoined readings, never in place of them. The added bash reading joins a backslash-newline outside single quotes and outside a bash comment. The added PowerShell reading joins a backtick-newline outside single quotes and outside a PowerShell comment. Comments are recognised first, in each reading, as the Comment-aware masker defines them, and a trailing backslash or backtick inside a comment is never a continuation, so joining never pulls the next line into a comment. The empty-quote splice (removing `''` or `""` that touches a non-space character) is also an added reading per shell. The masker runs before all of this, on the original text, and blanks with spaces that keep every newline. The classifier then judges every occurrence in every reading, unjoined, joined and spliced, as the Mention positions sentence says. Because readings are only added, the join and the splice can only move a form from mentioned to invoked. The restore script's recover flag is looked for on the physical line and in the rest of each joined reading's line. A name built at run time stays outside a text guard: concatenation (`& ('tools\db-protection\' + '<script>')`), a variable, an encoded command (`-EncodedCommand`) or a copy of the script under another name. So does a listed mention command that configuration written outside the call's text turns into a launcher (Mention positions, Environment rule), and a shell other than bash and PowerShell reading the text with other comment or quote rules. That is the named text-guard limit for the human-only class, in the residual-risk paragraph, the same limit as the arm-write residual rows S10 to S17 and t12's N6.
- **Audit-log rule (amendment 3, t12 finding I2; user answer 2026-11-20: included, extended to both database guards).** No step of either database guard's audit write may wait or follow a link: the destructive guard's `<project>/.claude/logs/db-guard.log` and the read-only guard's `<project>/.claude/logs/db-research.log` (`db-research-readonly-guard.py:95-98`, written by `_audit` at `:350-364` on its block path) are treated the same. The check covers the whole audit path, not only the append. (1) Folders: each part from the folder that holds `.claude` down to the log folder is checked without following links and must be a real folder, not a link or, on Windows, any reparse point (a junction included); a missing part is created one level at a time and checked again. (2) The log: checked without following links; a link or anything but a regular file is refused. (3) Rotation: only a regular log over the size limit is rotated, and only when the rotated name is absent or itself a regular file, both checked without following links; no step follows a link to rename or remove its target. (4) The open: write-only for appending, creating when missing, non-blocking and not following links where the platform offers those flags, then a check of the open file itself (`fstat`) before any byte is written: it must be a regular file with a link count of one (amendment 4, t14 finding L2: a hard link is a regular file to both checks, so without the count the record lands in whatever file the link shares). A log that fails any step is closed unwritten, the audit record for that call is skipped, and the guard writes one line to standard error. The decision has already been made, so skipping the record never changes it. Policy difference from I1, deliberate: the rules-file reader follows a link to a local regular file (such a rules file still loads), while the audit log refuses every link, because a log has no reason to be a link and a write through one reaches a file the guard did not choose. So the Windows link-target check of the rules-file reader is not needed here: any link is refused before its target matters, and the open-then-`fstat` check covers a link swapped in after the check.
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
- `_shell_write_targets.parse_redirect_targets` — consumed as-is, for the Arm-write rule. The destructive guard's prose masking ~~— consumed as-is, for the Arm-write rule~~ *(amendment 4, t14 B1 (b) and Q1, by the user's yes of 2026-11-21 to "Comment-aware masker")* is extended, not replaced: it becomes comment-aware (the No-prompt classes rule's "Comment-aware masker"), with the comment decided by the bash and PowerShell readings the classifier already defines, not by the masker's own quote pairing. It is a shared classifier, so its four consumers are named there, and each gets rows in block 15 (the 2026-11-05 shared-classifier lesson): destructive-command detection, the destructive guard's Arm-write test, the read-only guard's Arm-write test (which loads the destructive guard's masker and is not edited) and the human-only classifier. The human-only classifier keeps its four readings, gains added joined and spliced readings per shell, and gains the mention positions (by the user's yes of 2026-11-21 to "Inverted human-only classifier"). No new mechanism.
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
- Closing the text-guard limit for a human-only script name built at run time (concatenation, a variable, `-EncodedCommand`, a copy under another name), run through a listed mention command that configuration written outside the call's text turns into a launcher (a git filter, `diff.external`, `textconv`, `core.pager`, `core.fsmonitor` or hook; a ripgrep config file; an environment variable left by an earlier tool call), or read by a shell other than bash and PowerShell. It is named in the residual-risk paragraph and Failure Modes (amendment 4, t14 T1; fifth critique round). A mention command that runs a program from its own arguments in the same call is not in this limit: `sed`, `less` and `more` left the list, and `rg --pre`, `git grep -O` and an environment change in the same call are invoked (No-prompt classes rule, Mention positions).

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
- `ASSUMED` (amendment 4): a `#` that starts a word, outside quotes, begins a comment to the end of the line in bash (non-interactive, where `interactive_comments` is on by default), Windows PowerShell 5.1 and PowerShell 7, and neither shell continues a comment onto the next line with a trailing backslash or backtick. t14 ran bash and 5.1 only. Also `ASSUMED`: zsh, which the Bash tool may use on macOS, treats a word-start `#` the same way in a non-interactive shell; it was not run. The masker blanks only where the bash and PowerShell readings agree on the comment, and its exclusions (every here-document spelling, an unparsable `<<`, a PowerShell here-string, the rest of a line after `--%`, a block comment) leave text visible where this is uncertain, so a wrong assumption there costs a false block, not an allow; a here-document or here-string start the guard parses wrongly is the remaining risk, and block 15 has a row per spelling. Also `ASSUMED`: the mention list covers the ordinary ways an agent names a human-only script; if it does not, the cost is a false block, which the user's answer of 2026-11-21 accepts. Also `ASSUMED`, from each tool's own documentation and not from a run: with the argument rules, no listed word runs a program from its own arguments (ripgrep's `--pre` and git grep's `-O` are the ones found; ripgrep takes no abbreviated long options; git's abbreviations of `--open-files-in-pager` all start with `--o`). If a listed word can, the cost is an allow, so block 16 is told to try each listed word's options.
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
  - **Why accepted, not fixed:** the arm is one-shot and only ever yields a prompt, and fixing it means the read-only guard imports the destructive guard's human-only classifier, a new cross-guard dependency with its own fallback rows. It fails closed **only if** a hook block beats a hook ask when both guards answer one call, which is still ASSUMED (Uncertain Assumptions; the documentation quoted in pull request 432 gives "deny > defer > ask > allow", but no live trial observed it). If that assumption is wrong, the read-only guard's ask would make a human-only call promptable, the B1 class; block 12 states which way the evidence stands (t12: documentation only, no live observation), and block 14 states it again (t14: still documentation only, pull request 432; never seen live), and block 16 states it again. No block text tells the person to re-arm; the destructive guard's human-only text tells them to run the command by hand. ~~The block text tells the person to re-arm.~~ *(removed, third critique round W5: no code or block writes that text)*
- **FM (t12 B1, round three, and t12 P1, older than this contract, same root cause):** the quote scanner `_starts_a_command` reads quotes with one escape model for both shells. A trailing backslash before a closing quote (PowerShell `cd "<folder>\"; <script>`, `Set-Location "C:\work\"; <script>`, `Write-Host "C:\work\"; <script>`; bash `cd "C:\\work\\" && <script>`, `echo "a\\" ; <script>`), an escaped quote outside quotes (bash `echo \" ; <script>`, PowerShell `` Write-Host `" ; <script> ``), a doubled backtick before a quote (PowerShell ``` Write-Host "a``"; <script> ```) and bash `$'a\'b'` each read as "still inside a quote". Armed, after a blocked command, both guards ask (B1); with no arm the script runs with no prompt (P1, the 2026-05-06 incident class). t12 ran every shape in a real shell with a harmless probe script, and the trailing command ran each time.
  - **Mitigation:** the No-prompt classes rule's union of readings (bash, PowerShell, quote-blind, plus the old readings); block 13 changes the classifier only and copies t12's armed rows N1a, N1b, N2a, K4 to K6 and unarmed rows N1, N1c, N2, N2b, N3 to N6, N15 in t12's exact spelling, each failing at the parent tip. The P1 shapes get a line in the documents block's change note. *Amendment 4: achieved for every t12 row, in both shells (t14). Not achieved for the two spelling classes in the t14 entry below.*
- **FM (the union of readings, a new false block, accepted):** reading the text as both shells can class as invoked a script name that one shell would treat as a mention, for example a PowerShell argument wrapped in backticks, which the bash reading takes as a substitution, or a name after a doubled quote that one shell closes and the other does not.
  - **Disposition:** accepted fail-closed behaviour for new shapes no existing row covers: the result is a block naming the human-only script, and the person runs it by hand, which is what the user decided for this class. ~~Mentions inside commit messages, `echo` text, search patterns and pull request bodies are blanked by the prose masker before the classifier runs.~~ *(corrected, amendment 4, t14 W7 (d) and F1)* The prose masker blanks mentions inside commit messages, `echo` text, search patterns and pull request bodies before the classifier runs. It does not blank a double-quoted span that holds a backtick. So in PowerShell, `Write-Host` text or a commit message that wraps the name in backticks blocks (t14 M1, M1b), and so does a `cat <<'EOF'` body with the name on its own line (M4) and `command -pv <script>` (X49). These are accepted false blocks of this class. The same commit message in bash single quotes stays allowed (M1c). If any existing row (the mention and launcher controls, a block 11 row, or a row of the existing suites other than a named P1/P2-pinning row) flips, block 13 stops and reports an AMENDMENT; no reading is dropped to make it pass. `command -v` and `command -V` are a named mention, not a false block.
- **FM (t12 P2, older than this contract, outside the rule's literal definition before amendment 3):** a script after `then`, `do`, `else`, `!`, `time`, `env`, `nohup`, `exec`, `command`, `sudo` and similar words, or inside backticks, counts as mentioned. With no arm it runs with no prompt; armed after a blocked command, both guards ask (t12 N7 to N13, K1 to K3).
  - **Mitigation (user answer 2026-11-20: included in block 13):** the No-prompt classes rule's command-start words, with valued options skipped; block 13 adds t12's rows N7 to N13 and K1 to K3, one row per remaining word, and one row per valued option (`nice -n 10`, `sudo -u root`, `env -u NAME`, `timeout -s KILL 5`), plus `command -v` and `command -V` as allowed mentions. *Amendment 4: achieved for every row block 13 named (t14 W1 to W10, V1 to V7). Not achieved for long valued options with a separate value (t14 P2) or for the command starts outside the word list (t14 P3), in the t14 entries below.*
- **FM (t12 I2, older than this contract, same class as I1, in both database guards):** a link at `<project>/.claude/logs/db-guard.log` to a named pipe that accepts and never reads hangs the destructive guard on its block path, because `_audit` appends with a plain open. t12 saw no result within 20 seconds, before this contract and at head. The read-only guard has the same code for `<project>/.claude/logs/db-research.log` (`db-research-readonly-guard.py:95-98`, `_audit` at `:350-364`, on its block path); t12 linked only `db-guard.log`, so the read-only guard's 0.13 s result there does not clear it. The same `_audit` also follows links in its folder creation, its existence and size checks, and its rotation (`db-destructive-guard.py:785-791`, `db-research-readonly-guard.py:352-358`), so a linked folder or a linked log over the size limit could make it rename or write through a target it did not choose. If the host lets a timed-out hook's call proceed (ASSUMED), the destructive command runs with no prompt and no arm.
  - **Mitigation (user answer 2026-11-20: included in block 13, extended to both guards):** the Audit-log rule over the whole audit path; block 13 adds, per guard, real Windows pipe-link rows in both spellings, folder-link rows, linked-log and linked-`.1` rotation rows, a POSIX named-pipe row, and regular-log, missing-log and normal-rotation controls. *Amendment 4: cleared in both guards (t14, a real attempt with a pipe that accepts and never reads; at `4a67d1a` the same cases give no result within 10 s). A hard link is t14 L2, below.*
- **FM (the I2 fix skips an audit record):** a log, or a log folder, that is a link or not a regular file (folder) loses that call's audit record; a project whose `.claude` or `.claude/logs` is deliberately a link or junction gets no audit record at all.
  - **Disposition:** accepted. The decision is unchanged, and one line goes to standard error on every skipped record. The way out is a real `.claude/logs` folder and a regular log file in the project. On Windows, which has no flag to refuse a link at open, a link swapped in between the check and the open is still caught by the `fstat` check for a pipe or device; a swap to a link whose target stalls in the open itself (a disconnected network file) is a narrow race, named here as residual.
- **Information, accepted and out of scope (amendment 3).** t12 N6: the restore script's recover flag is matched as text after the script name, so `F=--recover-missing-dev-db; <restore script> $F` is allowed with no arm (t12 N14). It is the same text-guard limit as the arm-write residual rows S10 to S14 and predates this contract. t12 N5 (how links are created on the auditor's host) is applied to the W4 (Windows) entry above. Note on names: t12's finding ids N5 and N6 are not its probe shapes N5 and N6, and t4's shared-claim probes P1 to P9 are not finding P1; this contract keeps each report's own naming and says which one it means.
- **FM (t14 B1, round four, and t14 P1, older than this contract, same root cause):** two spelling classes inside the No-prompt classes rule's own definition read as "mentioned". (a) A quote opened mid-word right before the name (bash `tools/db-protection/"<script>"`, `echo a; tools/db-protection/'<script>'`, `"$PWD"/tools/db-protection/"<script>"`; PowerShell with forward slashes). Every reading ended inside the quote, and the quote-blind reading stripped a quote only before the folder prefix. (b) An apostrophe in a `#` comment on an `echo`, `Write-Host`, `git commit` or `grep` line. The masker paired it with the next apostrophe anywhere later and blanked the lines between as `echo` prose. Armed, both guards ask (A1, A1p, X3a, X3h). In X1e the destructive guard allows and keeps the arm, because the span also hid the removal. With no arm the script runs, as seen in a real Git Bash and Windows PowerShell 5.1 (X1, X1c, X1d, X1p, X3, X3b, X3f, X3g, X3i). Each shape is ALLOW or ASK at `4a67d1a` and at `cd8eb51`.
  - **Mitigation:** the No-prompt classes rule's mid-word quote clause and its Comment-aware masker. Block 15 copies t14's armed and unarmed rows in t14's exact spelling and shell, adds class rows for both classes in both shells (the reviewer's process lesson: each round copied only the last report's shapes), and requires every row to fail at the parent tip. The P1 shapes get a line in the documents block's change note.
- **FM (t14 Q1, critical, older than this contract, in the shared prose masker):** the same comment apostrophe hides every destructive statement up to the next apostrophe from the destructive guard. An EF removal of a non-disposable database sent that way is allowed by both guards, with no arm and no prompt (D2, D4, D5). So is an empty-table statement on a protected database (D6). A removal through `sqlcmd` is allowed by the destructive guard and blocked by the read-only guard only because it sees a write without the read-only intent (D1, D3). Armed, the EF removal is allowed and the arm kept (D8). Identical at `cd8eb51`, `4a67d1a` and `4a817cb`. This is the reference incident's own command.
  - **Mitigation (user answer 2026-11-21: yes, block 15 makes the shared masker comment-aware for all four consumers):** the Comment-aware masker in block 15, with destructive-guard rows D1 to D6 in both shells expecting a block, D8 expecting the normal armed ask (the arm claimed, not an allow), and masker controls.
- **FM (the comment-aware masker, a loosening in one direction):** text after a `#` that starts a word is now blanked. A destructive statement, a human-only name or an arm name that stands only in such a comment no longer blocks or is no longer refused, and before amendment 4 it may have been. That is correct for both shells, which never run a comment. The risks are text a shell does not treat as a comment: a here-document body in any delimiter spelling (a T-SQL `#temp` name before a destructive statement on the same line), a PowerShell here-string, the rest of a line after PowerShell `--%`, a `#` inside a word (`$#`, `${#x}`, `a#b`), a PowerShell block comment, whose later lines bash runs, and (fifth critique round BLOCKER) a `#` that one shell reads inside a quote or a word because of an escape the masker's own quote pairing does not model: bash `echo "a\" # b"; <EF removal>`, PowerShell ``Write-Host "a`" # b"; <EF removal>``, and the escaped-space forms bash `echo a\ # ; …` and PowerShell ``echo a` # ; …``. Each shell reads `# b` as text there and then runs the removal.
  - **Mitigation:** the masker rule blanks a comment only where the bash and PowerShell readings, each with its own escape model, agree on it at the same `#`; it never uses the masker's single quote pairing for that decision, and each exclusion follows from the agreement. Block 15 has a row for each exclusion and each escape spelling that expects a block, in the destructive-command form, the human-only form and the arm-write form, and every existing guard-suite row must keep its outcome. Most of these rows already block at the tip, because today's masker has no comment blanking, so each carries a named-mutation proof instead of a red-at-tip run (block 15, row kinds). The one allowed exception is a row whose flipped text stands entirely inside a comment as the rule defines it. That row is retired by name as the intended change, and any other flip stops the block with an AMENDMENT (the 2026-10-17 loosening lesson).
- **FM (fifth critique round BLOCKER, the comment apostrophe hides an arm write):** both Arm-write tests search the masked text, and `parse_redirect_targets` sees redirections only. So `echo "x"  # don't`, then on the next line `New-Item -ItemType File .claude/database-override.once` (or bash `touch` of the same path), then `echo 'y'`, is not refused at the tip by either guard: the same span that hid the human-only script hides the arm write.
  - **Mitigation:** the comment-aware masker, which both Arm-write tests consume (the read-only guard by loading the destructive guard's masker, so with no edit to its own code). Block 15 adds, in `test_database_override.py`, the arm-write comment rows per guard in bash and PowerShell, expecting the arm-write refusal, plus the escape spellings in arm-write form and a control (a line that only names the arm inside a comment both readings agree on is allowed). Until block 15 merges the route stays open; it yields at most a prompt, by the Prompt-only rule, and the claim is logged. Block 16 re-runs it in both guards.
- **FM (fifth critique round BLOCKER, continuation joining across shells):** a join applied to the whole text can turn an invocation into a mention: PowerShell treats a trailing `\` as a plain character, so `Write-Host a \` and the script on the next line runs the script, but a joined text reads it as a `Write-Host` argument; and a global backtick-newline join deletes the bash reading's backtick opener.
  - **Mitigation:** the Name matching sentence: each continuation is joined only in its own shell's reading, as an added reading beside the unjoined ones, outside comments, after comments are recognised. Block 15 has cross-shell rows (the PowerShell trailing backslash, the bash backtick before a newline, a bash comment ending in a backslash and a PowerShell comment ending in a backtick, each before the script on the next line), expecting a block, each with a named-mutation proof.
- **FM (t14 P2, high, long valued options):** an option that takes a value was skipped only in the short spellings block 13 listed. So `timeout --signal KILL 5 <script>`, `env --unset NAME <script>`, `nice --adjustment 10 <script>`, `echo x | xargs --max-args 1 <script>` and `sudo --user root <script>` read as mentions (X41 to X45). Armed after a removal, both guards ask (A41).
  - **Mitigation:** the long spellings in the command-start words, in block 15. With the inverted classifier a missed value would give a false block, not an allow; the long spellings still matter so that `nice --adjustment 10 cat <script>` stays a mention.
- **FM (t14 P3, high, older than this contract, command starts outside the rule's word lists):** bash `if`, `while`, `until`, `eval`, `eval "…"`, `find -exec`, a leading redirection, Git Bash `cmd //c`, `stdbuf`, `case`, `coproc` and `trap`; PowerShell `Start-Process` with options, `start -Wait`, `& (Get-Item …)` and `cmd /c --%`; cmd `start /wait` and `start ""`. With no arm, each ran the script in a real shell (X4 to X11, X13, X14, X16, X18 to X20, X53, X86, X87b, X88b, X89b). Armed after a removal, both guards ask (A4, A7, A10, A11, A13, A53). `winpty`, `setsid`, `doas`, `unbuffer`, `watch`, `flock` and `ionice` were not run (X15, X17, X80 to X84).
  - **Mitigation (a design change; user answer 2026-11-21: yes, fail-closed inversion with the closed mention list):** the Mention positions sentence of the No-prompt classes rule. Every visible occurrence is invoked unless every reading puts it in a named mention position. Block 15 adds every t14 P3 row, a row per mention word that must stay allowed, rows for exceptions (a), (b) and (c) including the multi-hop pipe and substitution forms, and the untried words as constructed rows.
- **FM (the inverted classifier, a new false block, accepted by the user's yes of 2026-11-21):** a human-only script name after a command the mention list does not hold is blocked. Examples are `find . -name <script>`, `code <script>`, `dos2unix <script>`, `tee <copy> < <script>`, `cat <script> | tee x`, a name inside a heredoc body the masker does not blank, and (fifth critique round) a name after `sed`, `less` or `more`, after `rg` with any `--pre…` word, after `git grep` with `-O` or a `--o…` word, or after any environment change in the same call (`LC_ALL=C grep x <script>`).
  - **Disposition:** accepted fail-closed behaviour, as for the union of readings. The block names the script and says a person runs it. The agent's way out is a listed read command (`cat`, `Get-Content`, `grep`, `git show`). The must-stay-allowed rows (MENTION_ROWS, r4.7a.6 to r4.7a.13, r4.16.1 to r4.16.9 except the update-script instance of r4.16.7, t14's CV1, CV2, CW1 to CW5, M1c, M2, M2p, M3, M3b and the `#` comment naming the script) keep passing. ~~Block 15 adds a word to the list only for an existing must-stay-allowed row, never a word that can run a program.~~ *(amendment 5: block 15 adds no word)* ~~If such a row needs `sed`, `less`, `more` or another word of that kind, block 15 stops with an AMENDMENT.~~ *(amendment 5: t15 stopped on this sentence for r4.16.7)* The `sed -n` read of `update-dev-database.cmd` in r4.16.7 pins the false block this entry accepts. By the user's answer of 2026-11-22 ("Retire only this row"), block 15 retires that one row by its exact name and puts the blocking row `r4.16.7b` in its place. Every other flip of an existing allow row still stops block 15 with an AMENDMENT report.
- **FM (fifth critique round WARN, a mention command that can run a program):** the list as first written held `sed` (its `e` command), `rg` (`--pre <command>` runs a program on each file searched) and `git grep` (`-O<pager>` / `--open-files-in-pager`), and `less` and `more` (a `+` or `!` command). Under the inverted classifier `rg --pre tools/db-protection/update-dev-database.cmd x .` would have been a mention, so an allow, while the script runs. An environment change in the same call can do the same through a listed word (`RIPGREP_CONFIG_PATH`, `GIT_EXTERNAL_DIFF`, `GIT_CONFIG_COUNT` and its keys, `GIT_PAGER`).
  - **Mitigation:** `sed`, `less` and `more` leave the list; `rg` and `git grep` get argument rules; the Environment rule makes any environment change in the call, or a `NAME=value` before the command word, end the mention position. Block 15 has rows for each, expecting a block. **Named limit (Non-Goals, residual-risk paragraph):** configuration written outside the call's text, such as a git filter, `diff.external`, `textconv`, `core.pager`, `core.fsmonitor` or a git hook, a ripgrep config file, or an environment variable left by an earlier tool call, can turn a listed command into a launcher with nothing in the command text to see. A text guard cannot judge it.
- **FM (fifth critique round WARN, the pipeline beyond one hop):** exception (b) as first written looked at the next segment only, so `cat <script> | grep . | cmd` and `Get-Content <script> | Out-String | iex` stayed mentions while the last segment runs the script's text.
  - **Mitigation:** exception (b) now requires every later segment of the pipeline to be a mention segment, and also covers a redirection into a process substitution; exception (a) covers an occurrence inside any substitution whose result is not itself a mention argument (`eval "$(cat <script>)"`, `bash <(cat <script>)`). Block 15 has one-, two- and three-hop rows in both shells and the substitution rows, expecting a block, and a control `cat <script> | grep . | head` that stays allowed.
- **FM (t14 T1, high, older than this contract, the name matched as literal text):** PowerShell `tools\db-protection\update-dev-database` with no extension, which Windows resolves through `PATHEXT` (X21), Git Bash `cmd //c` with no extension (X21b), a bash backslash-newline continuation inside the name (X23), a bash `''` splice inside the name (X24), and the restore script's recover flag on the line after a bash or PowerShell continuation (X22, X22p). Each ran in a real shell. Armed after a removal, both guards ask (A21). Concatenation (X25) is the same text-guard limit as the arm-write residual rows S10 to S17.
  - **Mitigation:** the Name matching sentence of the No-prompt classes rule (joins and splices per shell, as added readings), in block 15, with rows X21, X21b, X22, X22p, X23, X24 and A21, the cross-shell continuation rows of the entry above, and controls that a different file whose name starts with the stem (`update-dev-database.md`, `update-dev-database-notes.txt`) is not the script. X25, a variable, `-EncodedCommand` and a copy under another name are the named text-guard limit (Non-Goals, residual-risk paragraph).
- **FM (t14 L2, low, older than this contract):** a hard link at `db-guard.log` or `db-research.log` is a regular file to `lstat` and `fstat`, so the audit record is appended to whatever file the link shares (a user file grew from 11 bytes to 739 and 335 bytes).
  - **Mitigation:** the Audit-log rule's link-count check, in both guards' `_audit`, with a hard-link row per guard (the record skipped, the other file unchanged, the decision unchanged) in block 15.
- **FM (t9 steps 7 to 9 not run):** `acceptEdits`, `plan` and `dontAsk` were never run live.
  - **Disposition (user answer 2026-11-19: no third live trial):** a named residual. Each fails closed in code except the two prompt modes, whose designed outcome is a prompt; the unit rows and the auditor's offline probes cover them. No third trial block is added.
- **FM (security review N1):** an arm dated in the future stayed fresh for ever.
  - **Mitigation:** the amended Fresh-arm rule; the fixes block adds rows.
- **Security review W5, N2 and N3, not fixed here (user answer 2026-11-18, Open Question "Prompt target for sqlcmd").** W5 (the prompt shows the target as "unresolved" for `sqlcmd -Q`, also the live trial's finding W1) is a follow-up, decided: naming that target needs a change to the guard's target binder, which is outside the review's fixes, and the host's own prompt shows the full command. N2 (the neutraliser keeps `"` and `;`) is accepted, decided: no command form the auditor tried delivered a quote-forged target, and it joins the W5 follow-up, which reworks the same reason text. N3 (the read-only guard fails open on an internal error) is accepted, decided: it predates this contract, and the destructive guard beside it fails closed and refuses the same arm writes (probe P9).

**Residual risk of the database override, in one place.** An agent can still create the arm through a route no hook sees, or ask the person to approve. The arm is not tied to a command: whichever blocked command comes next uses it up, so the agent chooses which command a person's arm is spent on. A person who armed for one command can be shown another, and for the common `sqlcmd -Q` form the prompt reason names the target only as "unresolved", so the host's own display of the full command is the only place the person sees what will run. A prompt may be answered by code the person configured (a permission-prompt tool, an SDK callback, a `PermissionRequest` hook); then the override is only as careful as that code. ~~Whether a `permissions.allow` rule, which an agent can write, can turn the guard's `ask` into an allow is not yet proven; the second live trial block tests it (required before the re-review, user answer 2026-11-18).~~ *(amendment 2: answered by t9 step 6)* A `permissions.allow` rule, which an agent can write, did not turn the guard's `ask` into an allow in the second live trial (t9 step 6). That proof is narrow: one rule (`PowerShell(sqlcmd:*)`), one settings layer (the project's `settings.local.json`), `default` mode, Claude Code 2.1.327, and the branch's guard tested with the installed plugin disabled (t9 item 1). A `Bash(...)` rule, user-level or managed settings, and later host versions are untested, and the trial session's start time was inferred, not recorded, which block 9's own rule calls a void step. If an allow rule ever wins, the override is withdrawn: every destructive command then blocks and the person runs it in their own terminal (user answer 2026-11-18; refusing writes to the settings files was rejected). The withdrawal needs a further amendment, which this decision directs. While an older installed copy of the plugin is also active, its guard knows no arm and blocks, so the person sees a block, not a prompt; that fails closed. ~~Until block 11 merges: an armed call that puts a human-only script after quoted text gets a prompt for it (re-review B1); with no arm at all, such a call runs the human-only script with no prompt (re-review P1, older than this contract); a symbolic link at a switch-file path to a Windows named pipe silently stops the concept gate and the architecture guard (re-review W4); and a pipe link at the database guards' rules file can time out the guards themselves (re-review I1, in block 11 by the user's answer of 2026-11-19). After block 11, …~~ *(amendment 3, t12 finding W6 (a) to (c): block 11 merged, as `d43a285`, and closed fewer classes than this sentence said)* Block 11 closed, verified by t12 with real pipe-link attempts: the Windows pipe link at a switch-file path (W4) and at the database guards' rules file (I1); it also closed every reported t4 and t10 placement probe. ~~Until block 13 merges: an armed call that puts a human-only script after a quoted span the guard misreads (…) gets a prompt for it (t12 B1); with no arm, those shapes run the human-only script with no prompt (t12 P1, …); a script after a shell keyword or prefix command (…) counts as mentioned, armed or not (t12 P2, …); and a pipe link at either database guard's audit log (…) hangs that guard on its block path (…) (t12 I2, …).~~ *(amendment 4, t14 finding W7 (a) to (c): block 13 merged, as `4a817cb`, and closed fewer classes than this sentence said)* Block 13 closed, verified by t14: every t12 B1, P1 and P2 row in both shells, the per-word and short valued-option rows, and the audit-log pipe link in both guards (I2, by a real attempt with a live control at `4a67d1a`). Until block 15 merges, these stay open. An armed call that puts a human-only script after a quote opened mid-word before its name, or after a `#` comment holding an apostrophe on an `echo`, `Write-Host`, `git commit` or `grep` line, gets a prompt for it, and in one PowerShell shape (X1e) an allow (t14 B1). With no arm, those shapes run the script with no prompt (t14 P1, older than this contract). The same comment apostrophe hides every destructive statement on later lines, so an EF removal of the configured database is allowed by both guards with no arm (t14 Q1, critical, older than this contract; in block 15 by the user's yes of 2026-11-21 to "Comment-aware masker"). The same span hides an arm write (`New-Item` or `touch` of the arm path) on a later line from both guards' Arm-write tests, so neither refuses it; it still yields at most a prompt (fifth critique round; in block 15). A script after a long valued option with a separate value counts as mentioned (t14 P2). So does a script after a command start outside the rule's word lists (`if`, `while`, `eval`, `find -exec`, `cmd //c`, `Start-Process`, `--%` and the rest; t14 P3, older than this contract; in block 15 as the inverted classifier, by the user's yes of 2026-11-21 to "Inverted human-only classifier"). So does a call with no extension, a continuation or empty-quote splice inside the name, or the recover flag after a continuation (t14 T1, older than this contract). And a hard link at either audit log receives the record (t14 L2, older than this contract). After block 15, a human-only script name built at run time stays outside the guard: concatenation, a variable, `-EncodedCommand`, a copy under another name. So does a listed mention command that configuration written outside the call's text turns into a launcher: a git filter, `diff.external`, `textconv`, `core.pager`, `core.fsmonitor` or hook in the repository's configuration, a ripgrep config file, or an environment variable left by an earlier tool call. So does a shell other than bash and PowerShell that reads the text by other comment or quote rules (zsh is ASSUMED to read a word-start `#` as bash does). A mention command that runs a program from its own arguments or from an environment change in the same call is not in this limit: `sed`, `less` and `more` are no longer mention commands, and `rg` with a `--pre…` word, `git grep` with `-O` or a `--o…` word, and any environment change in the call are invoked (fifth critique round). This is the named text-guard limit for the human-only class (Non-Goals, Failure Modes), and it is the same limit as the arm-write residual rows S10 to S17 and t12's N6. With the inverted classifier, a name after a command the mention list does not hold is a false block, which is accepted; the one existing test row that pinned such a read as allowed (the `sed -n` read of the update script in r4.16.7) is retired by name, with `r4.16.7b` blocking in its place (amendment 5, user answer 2026-11-22), so no row keeps the old allow. Any other such row found by block 15 stops it with an AMENDMENT report, so no further row is retired without an amendment. With the comment-aware masker, a destructive statement, a human-only name or an arm name standing only in a comment both shell readings agree on is no longer seen, which is the intended loosening; a here-document or here-string start the guard parses wrongly is the remaining risk of that loosening (Uncertain Assumptions). After block 13 the audit record is skipped for a linked or non-regular log or log folder (after block 15, also for a hard-linked log), and a link swapped in on Windows between the check and the open to a target that stalls in the open itself remains a narrow race. The restore script's recover flag passed through a variable is not seen (t12 N6, accepted). Hooks other than the database guards that read a rules file with a plain open (the architecture guard, the integration check, the working agreements hook, the protected-names warning) can be hung the same way as I1 was (accepted, out of scope). After block 15 (before amendment 4 this read "After block 13"), an armed call that joins a human-only script with a database write still spends the arm on the read-only guard's ask while the destructive guard blocks (L1, accepted; for t4's O13 and O13e only in the spelling with `-S`, because without it the read-only guard allows and keeps the arm), and that stays closed only while a hook block beats a hook ask (ASSUMED). `acceptEdits`, `plan` and `dontAsk` rest on the unit rows, not a live trial. A person who approves without reading is the remaining hole. Sessions with no prompt get no override; the person runs the command in their own terminal.

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

**Amendment 4 (2026-11-21).** Already settled, not asked again. Block 15 fixes B1 and P1 (round four), because the No-prompt classes rule already requires it. It also fixes P2 (long valued options), because the rule's own sentence already says an option that takes a value skips its value. T1 is fixed for the extension-less call, continuations and empty-quote splices, because these are natural spellings that the rule's "invoked" already covers. The rest of T1 stays the named text-guard limit. L2 is fixed in both guards, because it is one more check on the open file the Audit-log rule already makes. W7 is fixed in this text. L1 stays accepted. W5, N2 and N3 keep their 2026-11-18 dispositions. No live trial is added. Two decisions were yours, both answered yes on 2026-11-21. Status stays `draft` until the main session's final check; the main session then flips Status to `approved`.

- [x] **Comment-aware masker.** An apostrophe in a `#` comment (for example "# don't skip the cleanup") makes the shared prose masker hide every line after it, up to the next apostrophe, from the destructive guard. An EF removal of the configured database sent that way is allowed by both guards with no arm and no prompt (t14 Q1). That is the reference incident's own command. The masker is older than this contract and is used by all destructive-command detection, not only by the override. Should block 15 make the masker comment-aware for everyone?
  → Recommended: **yes**. Block 15 already has to make the masker comment-aware for the human-only script (t14 B1 (b), the same root cause), and a contraction in a comment is ordinary agent text, not an evasion. The change blanks only text that every shell receiving it ignores, and blanks nothing in a here-document body, after `--%`, inside a word or inside a PowerShell block comment. Every existing guard-suite row must keep its outcome. The one exception is a row whose text stands entirely inside a comment, which block 15 retires by name. *(amendment 5: one more row is retired by name, for a reason that has nothing to do with the masker: the update-script instance of r4.16.7, replaced by `r4.16.7b`; see the Amendment 5 question)*
  ~~If **no**: the comment-aware rule is applied only to the copy of the text that the human-only classifier reads. …~~ *(closed by the user's yes of 2026-11-21; the fifth critique round's WARN found the branch's list of sentences incomplete, so it is removed rather than completed, and every sentence that depended on the answer is restated as decided)*
  **User answer (2026-11-21):** "**Yes.** Block 15 makes the shared prose masker comment-aware for all four consumers."
- [x] **Inverted human-only classifier.** Three rounds have added contexts that count as running a human-only script, and each review found more. With no arm, 19 more shapes ran the script in a real shell (`if`, `while`, `eval`, `find -exec`, Git Bash `cmd //c`, `Start-Process`, `cmd /c --%` and the rest; t14 P3). Should block 15 invert the test, so that every visible occurrence of the script name counts as running it unless it stands after a named read-only command (`cat`, `Get-Content`, `grep`, `echo`, `git show` and the others the No-prompt classes rule lists)?
  → Recommended: **yes**. An unknown form then fails closed with a block that names the script, which is what you decided for this class on 2026-11-16 ("never prompt for them; the person runs them by hand"). Each mention becomes a named, tested row, instead of a fifth word list. The cost is false blocks. An agent that names the script after a command outside the list (`find . -name <script>`, `code <script>`) is blocked and told a person runs it, and it can use a listed read command instead. MENTION_ROWS, LAUNCHER_ROWS and every must-stay-allowed row keep passing *(amendment 5: except the update-script instance of r4.16.7, a `sed` read that the shortened list makes a false block; see the Amendment 5 question)*.
  ~~If **no**: block 15 extends the word lists instead, with t14's enumeration. …~~ *(closed by the user's yes of 2026-11-21, for the same reason as above)*
  **User answer (2026-11-21):** "**Yes.** Fail-closed inversion with the closed mention list." The fifth critique round then shortened the list (`sed`, `less` and `more` removed) and added argument rules for `rg` and `git grep` and the Environment rule; the list stays closed, and a word is added only as the Mention positions sentence allows (since amendment 5: not by block 15; only by a further amendment).

**Amendment 5 (2026-11-22).** Already settled, not asked again: the inverted classifier and the shortened mention list (your yes of 2026-11-21 and the fifth critique round); `sed` stays a word that can run a program (its `e` command, the `s///e` flag and `-f`). One decision was yours, answered on 2026-11-22:

- [x] **Retire the old `sed` read row.** An existing test row reads the update script (`update-dev-database.cmd`, which only a person runs) with `sed` and expects it to be allowed. The contract has taken `sed` off the list of read commands, because `sed` can run a program, so that read is now blocked. Block 15 stopped because it was told both to keep that row and to block that read. Should block 15 retire that one row by name and put a blocking row in its place?
  → Recommended: **retire only this row**. It follows your 2026-11-21 answer (fail closed, a closed list of read commands). The same reads of the other three scripts stay allowed, including the restore script, which is not person-only without its recover flag. An agent that needs to read the update script uses `cat`, `grep` or `Get-Content`, and the existing rows for those stay allowed. Any other row that flips still stops block 15 with an AMENDMENT report.
  ~~Also adopt a standing rule, so that block 15 retires, the same way, any other old row that flips only because of a word the list leaves out, under three conditions.~~ *(not chosen, 2026-11-22; closed. The sixth critique round found that it conflicted with the "add a read-only word" permission and could retire named controls.)*
  ~~If **no**: `sed` goes back on the list with a rule about its arguments.~~ *(not chosen, 2026-11-22; closed. The contract records that no reliable argument rule exists for `sed`.)*
  **User answer (2026-11-22):** "**Retire only this row (Recommended)**". Block 15 retires `r4.16.7 sed -n of update-dev-database.cmd  [passes today]` by name and adds `r4.16.7b`. `sed` stays off the mention list. Every other flip stops block 15 with an AMENDMENT report.

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

### Fifth round — 2026-11-21 (amendment 4: security-review remedy round 4)

**Critic:** contract-critic
**Date:** 2026-11-21
**Verdict:** blockers-found

Scope: amendment 4 only. That is the Revision 4 line, the Delivery shape, the No-prompt classes rule (mid-word quote, Comment-aware masker, long valued options, Mention positions, Name matching), the Audit-log rule's link count, the Reused Mechanisms masker line, the Non-Goals entry, the amendment-4 Uncertain Assumptions, the t14 Failure Modes entries, the residual-risk paragraph, the amendment-4 Open Questions, the amendment-4 Lessons referenced entries, the Depends on lines of blocks 6 and 7, and blocks 15 and 16. These were checked against the t14 report (findings, the "New shapes at head" and "Q1 at head" tables, the Disposition) and against `db-destructive-guard.py` (`:1996-2143`, `:2289`, `:2464-2499`), `db-research-readonly-guard.py:501-547` and `test_db_destructive_guard.py:1855-1920`.

**Verified, no finding:**
- Every t14 finding has a place. B1, P1, P2 and L2 are fixed in block 15. T1 is fixed for the extension-less call, continuations, splices and the continued flag, and X25 and the rest are a named limit (Non-Goals, residual). Q1 and P3 are tied to the two Open Questions. W7 (a) to (d) are edited where they stand. F1 (M1, M1b, M4, X49) is an accepted false block in the union entry and in block 15.
- The graph has no cycle and agrees everywhere. The Delivery shape (sixteen blocks; 13 → 15, 15 → 16, {5, 16} → 6, {5, 6, 16} → 7, with the earlier edges recorded) matches the Depends on lines. Those lines are block 6 `5, 16`, block 7 `5, 6, 16`, block 15 `13` and block 16 `15`, and the text before the first `—` holds only those numbers. Block 7's CONTEXT chain (16 → 15 → 13 → 11 → 8) is right. Block 13 is merged (`4a817cb`), so the Revision 4 reason for `draft` holds.
- Block 16 can retire all four blocked reports. Its re-run list covers each failing t4, t10 and t12 probe and every t14 row the report marks ALLOW or ASK at head, except the untried words (NIT below). Its `supersedes` list is exactly the t4, t10, t12 and t14 file names on a pass and `[]` on blocked, and block 7's completion check names the same four.
- The consumer claims match the code. Destructive detection masks at `:2471`, the destructive guard's Arm-write test at `:2289` (`redirect_is_code=True`), and the read-only guard's Arm-write test loads the destructive guard's masker (`db-research-readonly-guard.py:501-518`, used at `:543`). The read-only guard's write detection reads raw text.
- The must-stay-allowed controls exist: r4.7a.6 to r4.7a.13, r4.7a.7b, r4.7a.12b and r4.16.1 to r4.16.9 (`test_db_destructive_guard.py:1863-1920`). The heredoc commit and pull request rows r4.7a.9 and r4.7a.11 are among them.
- No destructive statement is written as literal command text anywhere in the contract ("EF removal", "a removal of a non-disposable database", "an empty-table statement"). Blocks 15 and 16 both repeat the rule. No hidden-question word appears outside the Critique section. Confidence `Medium` agrees with the ASSUMED entries.
- Blocks 15 and 16 forbid touching the four version files and state parent mode. The `**Work Item Brief:**` header is present (static check only).

### Findings

- **[BLOCKER] The comment rule's "outside quotes" is decided by the masker's single quote model, so an escaped quote or an escaped space before a `#` opens a new blanking route**
  - **What is wrong:** `_skip_quoted` (`db-destructive-guard.py:1996-2019`) closes a double-quoted span at the first `"` and has no escape model. Today the `unsafe` flag (`:2120-2128`) stops a span with an escaped quote from being blanked, but it governs only span blanking, and rule (1) is a new blanking that does not depend on it. In bash `echo "a\" # b"; <EF removal>` and in PowerShell ``Write-Host "a`" # b"; <EF removal>``, the masker sees the `#` after a closed span, so as a word start outside quotes. It blanks the rest of the line, yet both shells read `# b` as string text and then run the removal. The same holds for an escaped space before `#` (bash `echo a\ # ; …`, PowerShell ``echo a` # ; …``), where the shell's `#` sits inside the word. The rule's own aim is to blank "only what every shell that can receive the text ignores". But it never says which quote reading decides "outside quotes". The four exclusions (here-document body, `--%`, `#` inside a word, `<# … #>`) and block 15's exclusion rows cover none of these spellings. On a yes to Q1, this brings the Q1 class back for EF removals, which the read-only guard does not match (t14 D0e). On a no, it brings back P1 for the human-only script.
  - **Prior artifact ignored:** the t12 report's B1 and P1 root cause ("one escape model for both shells") and this contract's own sentence written for it ("Where a quote ends depends on the shell, and the guard does not know which shell will run the text, so it does not guess one"). `JOURNAL.md` 2026-10-17, "Loosening a guard rule must be checked against the guard's own test fixtures". `JOURNAL.md` 2026-11-19, "A review-fix block's rows must copy each failing probe … in every shell form". Lessons referenced claims both as heeded for amendment 4.
  - **Where in this contract:** `## Data Shapes` → No-prompt classes rule, "(1) A `#` that starts a word (at the start of the text or a line, or after a space, …), outside quotes, starts a comment"; block 15, "Masker exclusion rows, each expecting exit 2: a here-document …; a PowerShell line with --% …; a # inside a word …; a PowerShell <# block".
  - → Addressed by: the Comment-aware masker's "Which reading decides" (a comment is blanked only where the bash and PowerShell readings, each with its own escape model, start one at the same `#`; `_skip_quoted` never decides it), the loosening Failure Modes entry, and block 15's escape rows (both escaped-quote and both escaped-space spellings, `$'…'`, a doubled quote) in destructive, human-only and arm-write form, each with a named-mutation proof.
- **[BLOCKER] Continuation joining is applied to the text as a whole, so it can turn a PowerShell invocation into a mention**
  - **What is wrong:** The Name matching sentence and block 15's T1 item join "bash backslash-newline and PowerShell backtick-newline continuations" before the name match. Neither is tied to its shell's reading. PowerShell treats a trailing `\` as a plain character, so `Write-Host a \` followed by a newline and `tools\db-protection\update-dev-database.cmd` runs the script on its own line. The parent tip classes it as invoked, because a newline splits segments. Joined, it reads as a `Write-Host` argument in every reading, and so as a mention, which is an allow. In the other direction, the bash reading counts a backtick outside single quotes as opening a command segment. A global backtick-newline join deletes that opener. Either way the change can move a form from invoked to mentioned. The rule forbids that ("The classifier may only move a form from mentioned to invoked, never the reverse") and lists only comment blanking as an exception. Block 15's older-test search (4) only asks which existing rows hold a trailing backslash or backtick. No row pins the cross-shell case. The order of joining and comment blanking is also not stated, and joining first would pull the next line into a bash comment.
  - **Prior artifact ignored:** the same t12 root cause and contract sentence as above. `JOURNAL.md` 2026-11-05, "A hardening fix applied to a shared classifier must be checked against every consumer of that classifier" (checking the direction a change can move an outcome). `JOURNAL.md` 2026-10-17 (loosening).
  - **Where in this contract:** `## Data Shapes` → No-prompt classes rule, Name matching, "the guard joins bash backslash-newline and PowerShell backtick-newline continuations"; block 15 T1, "join bash backslash-newline and PowerShell backtick-newline continuations … before the name match".
  - → Addressed by: the Name matching sentence (each continuation joined only in its own shell's reading, as an added reading beside the unjoined ones, outside comments, after comments are recognised; the masker runs first on the original text), the "may only move mentioned to invoked" sentence (joins and splices only add readings), a new Failure Modes entry, and block 15's T1 item with four cross-shell rows.
- **[BLOCKER] The two Arm-write consumers of the masker get no rows, and the comment apostrophe hides an arm write today**
  - **What is wrong:** Reused Mechanisms says the masker's "four consumers are named there, and each gets a row in block 15", and the amendment-4 Lessons entry says "each gets rows". Block 15 has rows for destructive detection (D1 to D6, D8, the exclusion rows) and for the human-only classifier. It has no row for either Arm-write test. Both tests search the masked text (`:2289`; `db-research-readonly-guard.py:543-545`), and `parse_redirect_targets` sees only redirections. So `echo "x"  # don't`, then `New-Item -ItemType File .claude/database-override.once` (or `touch`), then `echo 'y'` is likely not refused at the tip, by the same span t14 found for the script name. That route is not named in Failure Modes, the residual-risk paragraph or block 16's route re-run. The Q1 "if no" branch keeps both Arm-write tests on today's masker without naming the route as a residual.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-05, "A hardening fix applied to a shared classifier must be checked against every consumer of that classifier", which the contract claims as heeded at `## Lessons referenced` (amendment 4, second application). `JOURNAL.md` 2026-11-02, "A revision that adds a path adds its failure modes".
  - **Where in this contract:** `## Reused Mechanisms`, "its four consumers are named there, and each gets a row in block 15"; `## Lessons referenced`, "names its four consumers (destructive-command detection, both Arm-write tests, the human-only classifier), and each gets rows"; block 15, the Q1 and masker rows.
  - → Addressed by: block 15's arm-write comment rows per guard (destructive and read-only) in `test_database_override.py`, in bash and PowerShell, plus escape spellings and a control; the route is named in the Arm-write rule, a new Failure Modes entry, the residual-risk paragraph's "Until block 15" list and block 16's re-run list; the "if no" branch is closed.
- **[WARN] Block 15's "every row must fail at the tip" rule cannot be met by several rows the same block requires**
  - **What is wrong:** The constraint says "The only rows allowed to pass at the tip are the ones this TASK names as controls". Several required rows are not named as controls, yet they very likely pass at the tip:
    - The four masker exclusion rows (a here-document with `#temp`, `--%`, `$#` / `${#x}` / `a#b`, `<#`). Each expects exit 2 and holds no apostrophe, so today's masker leaves the removal visible.
    - The P2 constructed rows "after =". t14 records `--signal=KILL` as already blocking.
    - The exception (a) row when written as a backtick or `$(` substitution. Block 13 and t14 X30 to X32 already block these.
    - The "Allowed rows, one per mention word". `cat <script>` and the others are allowed at the tip.
    The relabel path ("A class row that already blocks at the tip is named a control") covers class rows only, and "never relabel it a control" covers copied rows. So the implementer has no sanctioned way out.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-19, "A review-fix block's rows must copy each failing probe …" (the red-at-tip discipline it led to). The block 13 convention this block inherits.
  - **Where in this contract:** block 15, "Every row copied from t14 and every class row below MUST fail at the tip … The only rows allowed to pass at the tip are the ones this TASK names as controls."
  - → Addressed by: block 15's four row kinds (copied rows fail at the tip; class rows fail at the tip or move to the mutation kind; mutation rows, whose expected outcome already holds at the tip, are proved by failing under a named mutation of the fix run in a scratch copy; controls pass at both, and each mention-word row also fails under "the mention list is empty"). The exclusion, escape, here-document, `=`-valued P2, backtick and `$(` exception (a), and cross-shell rows are named as mutation rows.
- **[WARN] The mention list holds words that can run a named program, which goes against the rule's own test for adding a word**
  - **What is wrong:** The rule forbids adding "a word that can run a program". The base list already holds three such words:
    - `rg`, whose `--pre <command>` runs a program on each file it searches.
    - `git grep`, whose `-O<pager>` / `--open-files-in-pager` runs the named program.
    - `sed`, whose `e` command runs text.
    Under the inverted classifier, `rg --pre tools/db-protection/update-dev-database.cmd x .` is a mention, so an allow, and the script runs. The residual-risk paragraph and Non-Goals name only `sed`'s `e`. Block 16 then reports any shape inside that limit as "information, not a finding", so the next review is told to wave these through. Neither the Failure Modes entry for the inverted classifier nor the ASSUMED "the mention list covers the ordinary ways" names this direction.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02, "A revision that adds a path adds its failure modes". `JOURNAL.md` 2026-10-04, "Check a documented guard behaviour against the guard's code" (here, against the tool's own options).
  - **Where in this contract:** `## Data Shapes` → Mention positions, "`grep`, `rg`, … `git` followed directly … by … `grep`" and "It may never add a word that can run a program"; residual-risk paragraph, "a mention command that can itself run text (`sed`'s `e` command)".
  - → Addressed by: `sed`, `less` and `more` removed from the list; argument rules for `rg` (`--pre…`) and `git grep` (`-O`, a bundle holding `O`, `--o…`); the Environment rule (an environment change in the call ends the mention position); a new Failure Modes entry; configuration written outside the call named as a text-guard limit in Non-Goals, Failure Modes and the residual-risk paragraph; block 15 rows; block 16 told these are findings, not information.
- **[WARN] Exception (b) looks one pipe hop ahead only**
  - **What is wrong:** "the segment's output is piped (`|`) into a segment whose command word is not itself a mention command" is judged on the next segment only. So `cat <script> | grep . | cmd` and `Get-Content <script> | Out-String | iex` stay mentions, because `grep` and `Out-String` are listed or harmless, yet the last segment runs the script's text. cmd runs the commands it reads on standard input. The inverted design exists to stop exactly this pattern of adding one more context at a time. Block 15 asks for "one row each for exceptions (a), (b) and (c)", which in practice is one hop.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-19, "A review-fix block's rows must copy each failing probe … in every shell form". The t14 process lesson that block 15 itself quotes ("each earlier round copied only the last report's shapes").
  - **Where in this contract:** `## Data Shapes` → Mention positions, exception "(b) the segment's output is piped (`|`) into a segment whose command word is not itself a mention command"; block 15 P3, "one row each for exceptions (a), (b) and (c)".
  - → Addressed by: exception (b) now requires every later segment of the pipeline to be a mention segment and covers a redirection into a process substitution; exception (a) covers an occurrence inside any substitution not itself a mention argument; a new Failure Modes entry; block 15 rows for one, two and three hops in both shells, the substitution forms and a multi-hop control.
- **[WARN] The here-document exclusion is defined by one delimiter spelling, and block 15 tests one spelling**
  - **What is wrong:** The exclusion covers "the lines after `<<WORD` up to `WORD`". It does not name `<<'WORD'`, `<<"WORD"`, `<<-WORD` (tab-stripped ending) or `<< WORD`. The masker already knows quoted tags inside `$(` (`_HEREDOC_SUB_RE`, three tag groups). If a here-document start is missed, a T-SQL `#temp` after a space in its body starts a "comment", and the destructive statement after it on that line is blanked from destructive detection. For `sqlcmd` the read-only guard's raw-text write check is a backstop. Armed, that check only asks, so the destructive guard stops being the deciding guard. Block 15 has one exclusion row in one spelling.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-17, "Loosening a guard rule must be checked against the guard's own test fixtures". `JOURNAL.md` 2026-11-19 (every spelling, not the reported one).
  - **Where in this contract:** `## Data Shapes` → Comment-aware masker, "This rule does not apply inside a here-document body (the lines after `<<WORD` up to `WORD`)"; block 15, "a here-document fed to sqlcmd whose line holds a #temp table name and then a removal".
  - → Addressed by: the masker rule's (2) names every delimiter spelling (`<<WORD`, `<< WORD`, `<<'WORD'`, `<<"WORD"`, `<<\WORD`, a partly quoted tag, `<<-WORD` with a tab-indented end), an unterminated body, an unparsable `<<` (ends blanking for the rest of the text) and PowerShell here-strings; block 15 has one mutation row per spelling; the Uncertain Assumptions entry names a mis-parsed start as the remaining risk.
- **[WARN] The "if no" branches still do not list every sentence that would become false (the fourth round's WARN, again)**
  - **What is wrong:** The "Comment-aware masker" no-branch says "D1 to D6 leave block 15". It leaves out three things:
    - D8 and the destructive-detection masker exclusion rows and controls.
    - The amendment-4 Lessons entries "names its four consumers … and each gets rows" and "comment blanking is the one loosening".
    - The Uncertain Assumptions comment clause, and the Arm-write route above.
    The "Inverted human-only classifier" no-branch leaves out four more:
    - The P2 Failure Modes sentence "With the inverted classifier a missed value would give a false block, not an allow".
    - The Reused Mechanisms clause "gains the mention positions".
    - The Uncertain Assumptions clause "the mention list covers the ordinary ways".
    - Block 6's change-note text, which is conditional but names the list.
    Each would stay in an approved contract and contradict the answer.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02, "Edit a reversed sentence where it stands". The fourth round's WARN, "The 'if no' branches of the two Open Questions do not list every sentence that would become false". The amendment-4 Lessons entry claiming "each 'if no' names the sentences it would change".
  - **Where in this contract:** `## Open Questions for User` → Amendment 4, "The architect makes that change before re-approval, in the No-prompt classes rule's 'Comment-aware masker' sentence, Reused Mechanisms, the two masker Failure Modes entries, the residual-risk paragraph, and blocks 6, 15 and 16", and the matching list under "Inverted human-only classifier".
  - → Addressed by: both answers are yes (2026-11-21), so both "if no" branches are struck as closed, and every sentence that depended on the answer is restated as decided where it stands: Revision 4, the No-prompt classes rule (the reversed "only mentioned" note, the one-exception sentence, the Comment-aware masker and Mention positions headings), Reused Mechanisms, the Q1, P3 and inverted-classifier Failure Modes entries, the residual-risk paragraph, Uncertain Assumptions, the amendment-4 Lessons entries, block 6's change note and blocks 15 and 16.
- **[WARN] The Arm-write rule still says the destructive-detection masking is unchanged**
  - **What is wrong:** On the recommended answer, amendment 4 changes the masking used for destructive-command detection. The Arm-write rule still reads "The masking used for destructive-command detection is unchanged, and the shared parser is not changed", and "after the guard's existing masking of inert quoted prose". Revision 4 and the amendment-4 Lessons entry list the sentences edited where they stand, and this one is not among them.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02, "Edit a reversed sentence where it stands".
  - **Where in this contract:** `## Data Shapes` → Arm-write rule, "The masking used for destructive-command detection is unchanged".
  - → Addressed by: the sentence is struck and corrected where it stands (the git-redirection exception stays for this rule only and the shared parser is unchanged, but the masker is comment-aware for every consumer, this rule included), and "the guard's existing masking" now reads "the guard's masking … (comment-aware since amendment 4)".
- **[NIT] Block 16 does not re-run the untried words** — t14's table records X15, X17 and X80 to X84 as dg ALLOW at head (only the real-shell run was missing), and block 15 builds them as rows. Block 16's re-run list skips them, so the review that retires t14 is not asked to judge them.
  - → Deferred: by the user's direction of 2026-11-21 (NITs deferred); block 16 already runs "each new class row of block 15" in a real bash and PowerShell, and block 15 builds X15, X17 and X80 to X84 as rows.
- **[NIT] The retire-by-name instruction names one file** — block 15 retires a defect-pinning row "in test_db_destructive_guard.py" when it sits in any of the listed suites, but `test_db_guard_path_allowlist.py`, `test_worktree_path_guards.py` and the fixture suite are not in Files to touch, so the concept gate refuses that edit. The AMENDMENT stop covers the outcome, but the two sentences disagree.
  - → Deferred: by the user's direction of 2026-11-21; the concept gate refuses an edit outside Files to touch, so the outcome is the AMENDMENT stop either way.
- **[NIT] The union-false-block disposition still names block 13 as the block that stops** — "If any existing row … flips, block 13 stops and reports an AMENDMENT" sits in an entry that amendment 4 edited, while block 15 now carries that duty.
  - → Deferred: by the user's direction of 2026-11-21; block 15's own TASK carries the stop rule, and no agent reads its instructions from that Failure Modes entry.
- **[NIT] Budget rule** — the file is far over its 12,000-token budget, and the template moves superseded rounds to `.claude/contract-history/<slug>.round-<n>.md`. This round is appended in place, as the caller directed.
  - → Deferred: by the user's direction of 2026-11-21; moving earlier rounds to `.claude/contract-history/` is a separate housekeeping change, and this revision was directed to be made in place.

### Applicable journal entries

- **2026-11-02 — After amending a contract, update every summary of the block graph** — heeded by the Revision 4 line, the Delivery shape, the Depends on lines and CONTEXT of blocks 6 and 7, and the precondition to refresh the t6 and t7 briefs and sub-issues 425 and 426.
- **2026-11-02 — Edit a reversed sentence where it stands** — heeded for the residual-risk "Until block 13" sentence, the "only mentioned" sentence, the union disposition and the Reused Mechanisms masker line. Not heeded for the Arm-write rule's masking sentence or for the "if no" branches (WARNs above).
- **2026-11-02 — Keep a review-fix block to the review's findings** — heeded: block 15 holds B1, P1, P2, P3, T1 and L2, plus Q1 on the answer, and the rest of T1 is a named limit.
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded for the masker's loosening and the inverted classifier's false blocks. Not addressed for the mention words that run programs or the Arm-write route (BLOCKER and WARN above).
- **2026-11-05 — A hardening fix applied to a shared classifier must be checked against every consumer** — violated for both Arm-write consumers (BLOCKER above), and the direction check for continuation joining is missing (BLOCKER above).
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by the older-test search and the retire-by-name rule. Violated by the escaped-quote and escaped-space spellings and the here-document delimiter spellings of the one loosening (BLOCKER and WARN above).
- **2026-11-19 — A review-fix block's rows must copy each failing probe in the reporter's exact clause order and in every shell form** — heeded for the copied t14 rows and the two class-row sets. Weakened by the one-hop exception (b), the one-spelling here-document row and the red-at-tip rule that some required rows cannot meet (WARNs above).
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have** — heeded by block 15's "What the rows prove" and the D8 row (an armed ask, not a block, stated per guard).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded: Status is `draft` until both answers exist, and the body is marked "recommended, awaiting the user".
- **2026-11-06 — Judge a drive letter with a no-I/O check before any realpath** — not addressed, because the L2 link-count check reads `fstat` on an already-open descriptor and adds no path resolution.

### What the critic did not check

- `pr_merged.py --contract 2026-11-16-file-based-switches --status --json` was not run (no shell), so `layout_defects` were not read. The Parent Branch Delivery Rule check is static only.
- No probe was run. The escaped-quote and escaped-space comment routes, the PowerShell trailing-backslash join, the comment-apostrophe arm write, `rg --pre` and `git grep -O` under the inverted list, and the multi-hop pipe are all judged from reading `_skip_quoted`, `_mask_inert_prose` and `_arm_write_match` and the rule text, not from a run at the tip.
- CodeGraph tools were not available in this session, so symbols were located by searching the files directly. `derive_area.py` was not run (`.claude/area-mapping.json` declares no areas). `.claude/north-stars/` holds no active file.

### Sixth round — 2026-11-22 (amendment 5: block 15 retirement of r4.16.7)

**Critic:** contract-critic
**Date:** 2026-11-22
**Verdict:** blockers-found

Scope: amendment 5 only. That is the Revision 5 line, the Mention positions sentence's edited AMENDMENT clause and its "keep their outcomes" sentence, the inverted-classifier Failure Modes disposition, the residual-risk false-block sentence, the amendment-4 recommendation note, the Amendment 5 Open Question, the amendment-5 Lessons referenced entries, block 15 (Depends on note, file note, CONTEXT, P3, controls, the r4.16.7 retirement, older-test search item 7, the standing rule with conditions (a) to (c)) and block 16 (CONTEXT, the retirement check). These were checked against `test_db_destructive_guard.py:1599` (`_DEV_SCRIPTS`), `:1855-1920` (r4.7a and r4.16 rows) and `test_database_override.py:797-820` (LAUNCHER_ROWS, MENTION_ROWS).

**Verified, no finding:**
- The conflict is real and the first case is described rightly. `:1917` builds `sed -n '1,60p' tools/db-protection/<s>` as an allow for all four entries of `_DEV_SCRIPTS`, and block 15 also requires the constructed `sed -n 1p <script>` row to block. Only the update-script instance is human-only: restore-latest.cmd carries no recover flag on that line, and the other two scripts are not human-only entries. "The other three r4.16.7 instances" is the right count.
- r4.16.7b can fail at the parent tip and pass at head. At the tip the name is an argument of a non-launcher command, so it is mentioned and allowed (the row is labelled `[passes today]`). At head `sed` is off the list, so the name is invoked. The row expects exit 2 and the human-only instruction, uses the same command text with no arm, and is a kind (2) row.
- Every list that named r4.16.1 to r4.16.9 now carries the update-script exception: the No-prompt classes rule (`keep their outcomes`), the inverted-classifier disposition, the amendment-4 recommendation note, block 15's controls, and block 16, which also confirms that the restore-latest.cmd instance still allows. Block 15 keeps that instance as a named control.
- The graph and the block count are unchanged. Block 15's Depends on still begins `13 —`, Status is `draft`, and the Revision 5 reason for `draft` holds (block 13 is merged). Blocks 15 and 16 still forbid the four version files and state parent mode.
- No destructive statement is written as literal command text in the amendment-5 text. The only new command text is the `sed -n` read.

### Findings

- **[BLOCKER] Block 15's standing rule forbids what the Mention positions sentence allows, for a read-only word the list never held**
  - **What is wrong:** The Mention positions sentence scopes retirement to a row that needs a word that can run a program ("An existing allow row that needs one of these is not met by adding the word. If the row's only difference … is a word the contract removed or never listed, block 15 retires it"). It also still says "Block 15 may add a read-only word that an existing must-stay-allowed row needs", and block 15's P3 item repeats that permission. Block 15's standing rule has no program-running limit: any allow row that flips "ONLY because the closed mention list does not hold a word the contract removed or never listed (sed, less, more and the like)" is retired, and "Do not add the word to the list to keep the old row". For an existing allow row that reads the update script through a read-only word the list never held (for example `stat`, `file` or `od`), one line says add the word and the other says retire the row and do not add it. These are two lines of block 15 that cannot both hold, which is the exact defect that stopped t15. "and the like" leaves the class open, so the implementer decides alone which branch applies.
  - **Prior artifact ignored:** the t15 stop recorded in the Revision 5 line ("Two lines of block 15 could not both hold"). `JOURNAL.md` 2026-11-02, "Edit a reversed sentence where it stands" (the permission sentence was not edited). `JOURNAL.md` 2026-11-02, "Name the tests a fix may change by the state they guard, after reading them".
  - **Where in this contract:** `## Data Shapes` → Mention positions, "Block 15 may add a read-only word that an existing must-stay-allowed row needs" and "is not met by adding the word"; block 15 P3, "You may add a read-only word to the list only for an existing must-stay-allowed row"; block 15 suites, "a word the contract removed or never listed (sed, less, more and the like) … Do not add the word to the list to keep the old row".
  - → Addressed by: the standing rule is removed (user answer 2026-11-22), the add-a-word permission is struck in Mention positions, the disposition and block 15 P3, and all three now say the same thing: block 15 adds no word, retires only r4.16.7's update-script instance, and stops with an AMENDMENT on any other flip.
- **[BLOCKER] The standing rule's "never listed" clause covers must-stay-green controls the same block calls unchanged, including the decided pull-request-body mentions**
  - **What is wrong:** `gh` is a word the contract never listed. r4.7a.10 and r4.7a.11 (`test_db_destructive_guard.py:1876-1883`) and MENTION_ROWS `pr-body` (`test_database_override.py:812-813`) name the update script inside a `gh pr create --body` argument, and r4.7a.11 puts it inside `$(cat <<'EOF' …)` in that body. Under the inverted classifier these stay allowed only while the masker blanks the whole body. Exception (a) does not save r4.7a.11, because `gh` is not a mention command. If a block 15 masker change leaves that body visible, the row flips with `gh` as the command word in front of the name, the same script and the same arm state. Condition (a) as written is then met. The standing rule covers both files ("an existing ALLOW row in test_db_destructive_guard.py or test_database_override.py") and does not exempt the named controls. So a regression in the shared masker could be filed as a "pinned false block" and retired, while block 15's controls item says r4.7a.6 to r4.7a.13 and MENTION_ROWS stay "green, unchanged". The No-prompt classes rule says pull request body mentions "stay allowed", and the inverted-classifier disposition says the named controls "keep passing" with only the r4.16.7 exception. The same three-way conflict appears whenever any named control's command word is off the list.
  - **Prior artifact ignored:** the No-prompt classes rule's own sentence, "Text the prose masker has already blanked (commit messages, `echo` text, search patterns, pull request bodies) is not read again, so those mentions stay allowed". The user's 2026-11-21 yes to "Comment-aware masker", whose recommendation reads "Every existing guard-suite row must keep its outcome. The one exception is a row whose text stands entirely inside a comment". `JOURNAL.md` 2026-11-02, "Name the tests a fix may change by the state they guard, after reading them". The fifth round's note that r4.7a.9 and r4.7a.11 are among the controls.
  - **Where in this contract:** block 15 suites, "an existing ALLOW row in test_db_destructive_guard.py or test_database_override.py … that flips to a block ONLY because the closed mention list does not hold a word the contract removed or never listed"; block 15 controls, "Controls that must stay green, unchanged: MENTION_ROWS … r4.7a.6 to r4.7a.13 … except the one instance retired below"; `## Failure Modes & Mitigations`, "The must-stay-allowed rows (MENTION_ROWS, r4.7a.6 to r4.7a.13, r4.16.1 to r4.16.9 except the update-script instance of r4.16.7 …) keep passing".
  - → Addressed by: the standing rule is removed, so no class of rows can be retired. Named controls (r4.7a.10, r4.7a.11, MENTION_ROWS `pr-body` and the rest) stay green and unchanged, and a flip of any of them stops block 15 with an AMENDMENT report.
- **[WARN] Condition (a) cannot be checked from what the pull request records**
  - **What is wrong:** "the same script, the same arm state, no other changed reading" is judged by the implementer whose fix caused the flip. Condition (b) records only names and old and new outcomes, and no condition requires evidence that the word is the sole cause. For example, no condition asks that the same text with a listed word in its place still allows at head. For r4.16.7 that evidence exists by chance (r4.16.6 `cat` of the same script stays a control), but the contract does not name it as the pair, and the standing rule does not ask for a pair. A flip caused by an over-matching name rule or a masker regression therefore looks the same in the pull request body as a pinned false block. Block 16 is told to check (a), but from the listing alone it has nothing to check against.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-17, "Loosening a guard rule must be checked against the guard's own test fixtures". `JOURNAL.md` 2026-11-07, "A merge block's pull request must paste each required output, not tick a line that says it passed".
  - **Where in this contract:** block 15 suites, "(a) The old row's only difference from a blocking shape is that word: the same script, the same arm state, no other changed reading"; block 16, "Check each retirement block 15's pull request lists against conditions (a) to (c) of that rule".
  - → Addressed by: resolved by the standing rule's removal (condition (a) no longer exists). For the one retirement left, block 15 names its pair, r4.16.6 (`cat` of the same script), as a control that must stay allowed, which shows that only the word changed.
- **[WARN] Condition (c) asks the replacement row only for exit 2, so a crash or another rule's block satisfies it**
  - **What is wrong:** r4.16.7b asks for exit 2 with the human-only instruction, fails at the parent tip and passes at head. The standing rule's (c) asks only "a replacing blocking row … expecting exit 2, with the same command text". It does not ask for the human-only reason in the block text or for red at the parent tip. `_fail_closed` also exits 2 (No-prompt classes rule), and so does any other blocking rule. A replacement that passes because the guard's new code raises, or because another rule matched, meets (c) and proves nothing about the classifier. The four row kinds do not cover it either: a replacement is not a copied row and not one of the named class rows, so the red-at-tip rule is not clearly bound to it.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-19, "A review-fix block's rows must copy each failing probe …" (the red-at-tip discipline). `JOURNAL.md` 2026-11-06, "An exception sentence that names the outcome of a later call must list every outcome that call can have".
  - **Where in this contract:** block 15 suites, "(c) A replacing blocking row is added for each, named \"<old id>b …\", expecting exit 2, with the same command text".
  - → Addressed by: resolved by the standing rule's removal (condition (c) no longer exists). The one replacement, r4.16.7b, already asks for exit 2 with the human-only instruction, as a kind (2) row that fails at the parent tip.
- **[WARN] Block 16 is told that an unlisted flip is a finding, but not how to find one**
  - **What is wrong:** A retired row is removed from its comprehension or list, so the suites stay green and nothing fails. Block 16 names the commit range and re-runs the suites, but nothing tells it to diff `test_db_destructive_guard.py` and `test_database_override.py` over that range for `_ok` rows or MENTION_ROWS entries removed, renamed, or changed from allow to block. Without that diff, "so is a flipped allow row that was not listed" depends on the auditor noticing a row that is gone.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-07, "No tool enforces how a pull request into a parent branch is merged; the next block must prove it" (the next block proves the property with a named check). `JOURNAL.md` 2026-11-06, "A sub-task that flips the state an earlier sub-task's test pins must re-run that suite".
  - **Where in this contract:** block 16, "A retirement that fails any of them is a finding, and so is a flipped allow row that was not listed".
  - → Addressed by: mostly resolved by the standing rule's removal. Block 16 also now diffs `test_db_destructive_guard.py` and `test_database_override.py` over the reviewed range for allow rows and MENTION_ROWS entries that were removed, renamed or changed to a block. Only r4.16.7's update-script instance may be among them, plus any row block 15 retired under its amendment-4 rules and named in its pull request. Any other is a finding.
- **[WARN] The Open Question bundles two decisions, its "if no" reopens a settled one, and the body already cites an answer that does not exist**
  - **What is wrong:** The question asks the user to approve, in one answer, the narrow retirement of one row and a standing rule that delegates future retirements to the implementer. There is no way to answer yes to the first and no to the second. The "if no" branch puts `sed` back on the list, which the same paragraph calls "Already settled, not asked again", and which the branch itself calls unsafe. The natural no (retire r4.16.7 only, and keep the AMENDMENT stop for every other flip) is not offered. The branch names none of the sentences it would make false (the Revision 5 line, the Mention positions sentence, the disposition, the residual-risk sentence, block 15's three items and block 16), which repeats the fourth and fifth rounds' WARN. The box is unchecked, yet block 15 says "the user's answer to the Amendment 5 Open Question". The amendment-5 Lessons entry says "The change only settles a conflict between two lines of block 15", but the standing rule also changes how block 15 treats rows nobody has read yet.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22, "An accepted critic WARN or answered Open Question must amend the contract body before approval". `JOURNAL.md` 2026-11-02, "Edit a reversed sentence where it stands". `JOURNAL.md` 2026-11-02, "Keep a review-fix block to the review's findings". The fifth round's WARN, "The 'if no' branches still do not list every sentence that would become false".
  - **Where in this contract:** `## Open Questions for User` → Amendment 5, "Should block 15 retire that one row by name, … and, from now on, retire the same way any other old row …" and "If **no**: `sed` goes back on the list"; block 15, "Retire r4.16.7 for update-dev-database.cmd by name (amendment 5, the user's answer to the Amendment 5 Open Question)"; `## Lessons referenced`, "The change only settles a conflict between two lines of block 15".
  - → Addressed by: resolved by the user's answer of 2026-11-22 ("Retire only this row (Recommended)"), recorded under the question, with the bundled standing rule and the `sed`-back branch struck as not chosen. The box is checked, so block 15's citation of the answer is true, and the Lessons entry is reworded.
- **[NIT] The retired row's exact name** — condition (b) requires "its exact name", but the row at `:1917` is "r4.16.7 sed -n of update-dev-database.cmd  [passes today]", and block 15 quotes it without the suffix.
  - → Addressed by: every mention of the retired row (Revision 5, Mention positions, block 15's retirement item, the Open Question answer) now quotes the exact name with the `  [passes today]` suffix.
- **[NIT] "the command word in front of the name"** — in r4.16.7, `-n '1,60p'` stands between `sed` and the name. A literal reader of (a) may say the first case itself fails the condition. "The segment's command word" is the rule's own term.
  - → Addressed by: resolved by the standing rule's removal, which takes condition (a) with it.
- **[NIT] Block 16's CONTEXT narrows the rule** — it describes "retiring a row pinned by a removed mention word", while Revision 5 and block 15 say "removed or never listed". Block 16 checks against block 15's wording, but the summary disagrees.
  - → Addressed by: block 16's CONTEXT now names the one retirement (r4.16.7's update-script instance, replaced by r4.16.7b) and the AMENDMENT stop for every other flip.
- **[NIT] The 2026-11-21 recommendation's "one exception" sentence is not annotated** — "Every existing guard-suite row must keep its outcome. The one exception is a row whose text stands entirely inside a comment" now has a second exception class, and the amendment-4 inverted-classifier recommendation got a note but this sentence did not.
  - → Addressed by: the sentence now carries an amendment-5 note naming the one extra retirement.
- **[NIT] Budget rule** — the file stays far over its 12,000-token budget. This round is appended in place, as the caller directed.
  - → Deferred: the caller directed an in-place revision of amendment 5. Compressing a contract with fifteen delivered or dispatched blocks would rewrite text that merged reviews cite, which is out of scope for this amendment.

### Applicable journal entries

- **2026-11-02 — After amending a contract, update every summary of the block graph** — heeded: the Revision 5 line says sixteen blocks with the same graph, and the Depends on line is unchanged in its numbers.
- **2026-11-02 — Edit a reversed sentence where it stands** — heeded for the AMENDMENT clause in Mention positions and in the disposition (struck and replaced beside it). Not heeded for the "may add a read-only word" permission or for the 2026-11-21 "one exception" sentence (BLOCKER and NIT above).
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded for r4.16.7, which was read, retired by name and replaced. Weakened for the standing rule, whose conditions cannot show the flip's cause (WARN above).
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them** — heeded for r4.16.7. Violated by the standing rule, which lets the implementer retire unread rows by class, including named controls (BLOCKER above).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — not heeded: the body cites an answer the unchecked box has not given (WARN above).
- **2026-11-02 — Keep a review-fix block to the review's findings** — heeded for files and blocks (none added). The Lessons claim that the change "only settles a conflict" understates the standing rule (WARN above).
- **2026-11-07 — No tool enforces how a pull request into a parent branch is merged; the next block must prove it** — not addressed for unlisted retirements (WARN above).
- **2026-11-19 — A review-fix block's rows must copy each failing probe …** — heeded by r4.16.7b (red at the tip, the human-only reason). Not carried into condition (c) (WARN above).

### What the critic did not check

- No probe or suite was run. Whether the shared masker blanks the `gh pr create --body` spans of r4.7a.10, r4.7a.11 and MENTION_ROWS `pr-body` after block 15 was judged from the rule text, not from a run.
- `pr_merged.py --contract 2026-11-16-file-based-switches --status --json` was not run (no shell), so the Parent Branch Delivery Rule check is static only. MECHANISMS.md and VOCABULARY.md were consulted only for overlap, because amendment 5 adds no data shape, mechanism or term. CodeGraph tools were not available, so the test files were searched directly. `.claude/north-stars/` holds no active file.

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
- **2026-11-05 — A hardening fix applied to a shared classifier must be checked against every consumer of that classifier** — heeded by scoping the W2 fix to the Arm-write rule, leaving the prose masker's destructive-detection use and the shared shell parser unchanged. (Amendment 4 later made the masker itself comment-aware for every consumer, by the user's answer of 2026-11-21; the W2 git-redirection exception is still for the Arm-write rule only.) `JOURNAL.md`.
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
- **2026-11-19 — A review-fix block's rows must copy each failing probe in the reporter's exact clause order and in every shell form** (second application) — heeded by amendment 4: block 15 copies t14's rows by their t14 ids in t14's exact spelling and shell, each failing at the parent tip. It also adds class rows for the two new classes (a `#` comment with an apostrophe before the target line, a quote opened mid-word before the name), in bash and PowerShell, so that the fix is not shaped only to the reported spellings (t14's process lesson). `JOURNAL.md`.
- **2026-11-05 — A hardening fix applied to a shared classifier must be checked against every consumer of that classifier** (second application) — heeded by amendment 4: the comment-aware masker names its four consumers (destructive-command detection, both Arm-write tests, the human-only classifier), and each gets rows; the two Arm-write consumers' rows were added after the fifth critique round, with the arm-write comment route named. The direction of every change is checked: comment blanking is the one change that hides text, and continuation joining and empty-quote removal are added readings that can only move a form toward invoked. Because it changes destructive-command detection for everyone, the change went to the user as an Open Question, as I1 and I2 did (answered yes, 2026-11-21). `JOURNAL.md`.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by amendment 4: comment blanking is the one loosening, decided by both shells' own quote and escape readings. Its exclusions (every here-document spelling, an unparsable `<<`, PowerShell here-strings, `--%`, inside a word, PowerShell block comment) and its escape spellings (escaped quote and escaped space in each shell, `$'…'`, a doubled quote) each get a blocking row, proved by a named mutation where the row already blocks at the tip, and any existing row that flips stops block 15, except a row whose text is entirely a comment, which is retired by name. `JOURNAL.md`.
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have** — heeded by block 15's D8 row: armed, the EF removal expects the normal armed ask with the arm claimed, not a block. The destructive guard's outcome is stated apart from the read-only guard's. `JOURNAL.md`.
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded by amendment 4: the comment-aware masker's loosening, the inverted classifier's false blocks, and (after the fifth critique round) the arm-write comment route, cross-shell continuation joining, mention commands that can run a program, and the pipeline beyond one hop each have a Failure Modes entry. `JOURNAL.md`.
- **2026-11-02 — After amending a contract, update every summary of the block graph** and **Edit a reversed sentence where it stands** — heeded by amendment 4: the Revision 4 line, the Delivery shape (sixteen blocks, the new edges, earlier edges recorded), the Depends on lines and CONTEXT of blocks 6 and 7, the "only mentioned" sentence, the union-false-block disposition, the "consumed as-is" masker line and the residual-risk paragraph's "Until block 13" and "After block 13" sentences are edited where they stand (t14 W7); after the fifth critique round also the Arm-write rule's "masking … is unchanged" sentence, the Name matching join sentence and the mention list. `JOURNAL.md`.
- **2026-11-02 — Keep a review-fix block to the review's findings** (fourth application) — heeded by block 15: B1, P1, P2, P3, T1 and L2, plus Q1 by the user's yes of 2026-11-21. The fifth critique round's additions (the arm-write comment rows, the argument and Environment rules, the multi-hop exception) close gaps inside those same findings, not new findings. The rest of T1 is a named limit in Non-Goals, not code. `JOURNAL.md`.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded by amendment 4: both questions were answered yes on 2026-11-21, the answers are recorded verbatim under them, the "if no" branches are struck as closed, and every sentence that depended on an answer is restated as decided where it stands; each fifth-round BLOCKER and WARN amends the body and is marked "Addressed by" under the finding. Status stays `draft` until the main session's final check. `JOURNAL.md`.
- **2026-11-19 — A review-fix block's rows must copy each failing probe in the reporter's exact clause order and in every shell form** (third application) — heeded after the fifth critique round: every new row class (escape spellings, here-document spellings, cross-shell continuations, multi-hop pipes, arm-write comments) is written in both shells, and a row that cannot fail at the tip is proved by a named mutation instead of being waved through. `JOURNAL.md`.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded after the fifth critique round, against the tools' own options: the mention list drops `sed`, `less` and `more`, and gets argument rules for `rg --pre` and `git grep -O`, because each can run a program from its arguments. `JOURNAL.md`.
- **2026-11-02 — After amending a contract, update every summary of the block graph** and **Edit a reversed sentence where it stands** — heeded by amendment 5: the old "stop with an AMENDMENT" sentence and the "may add a read-only word" permission are struck where they stand (the Mention positions sentence, the inverted-classifier disposition, block 15 P3) and replaced beside them by one closed rule: no word is added, one named row is retired, and every other flip stops with an AMENDMENT. The 2026-11-21 "one exception" sentence carries a note. Every list of controls that named r4.16.1 to r4.16.9 is edited in place: the No-prompt classes rule, Failure Modes, the amendment-4 recommendation, block 15's controls and older-test search, and block 16. The Revision 5 line says the graph and the block count are unchanged. `JOURNAL.md`.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** (tightening direction, as for block 11) — heeded by amendment 5: the one row that flips under the shortened list, read by the architect and named by its exact name, is retired and replaced by a blocking row, never edited silently. Its pair r4.16.6 (`cat` of the same script) stays a control. No row is retired by class (user answer 2026-11-22). `JOURNAL.md`.
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them** — heeded by amendment 5: the only row block 15 may change for the mention list is named after reading `test_db_destructive_guard.py:1917`. Every unread row that flips stops block 15 with an AMENDMENT report. `JOURNAL.md`.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded by amendment 5: the user's answer of 2026-11-22 is recorded under the question, the unchosen options are struck as closed, and each sixth-round finding is marked "Addressed by" or "Deferred". `JOURNAL.md`.
- **2026-11-02 — Keep a review-fix block to the review's findings** (fifth application) — heeded by amendment 5: no new finding, file or block. The change settles one conflict between two lines of block 15 by retiring one named row, and adds no standing rule. `JOURNAL.md`.
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

**Depends on:** 5, 16 — blocks 4, 10, 12 and 14 are no longer named: their records read `blocked`, and the loop never releases a block whose dependency reads `blocked`; the fifth security review (16) replaces them. Before amendment 4 this line read "5, 14"; before amendment 3, "5, 12"; before amendment 2, "5, 10".

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
  table of the Inventory. This block runs after the ordinary switches block (5) and the fifth
  security review (16) have passed; read the report
  t16-security-re-review-round-five-security-auditor.md, the blocked reviews
  t14-security-re-review-round-four-security-auditor.md,
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
    when the other shell would only mention it; the person runs it by hand. Amendment 4 adds,
    as fixes of behaviour older than this contract: a human-only script after a quote opened
    mid-word before its name, or after an apostrophe in a # comment, was allowed with no prompt
    (t14 B1, P1); a script after a long valued option or a command start outside the guard's
    lists (if, while, eval, find -exec, cmd //c, Start-Process, cmd /c --% and the rest) was
    allowed (t14 P2, P3); a call with no extension or with a continuation inside the name was
    not seen (t14 T1); a hard link at either audit log received the record (t14 L2). By the
    user's answers of 2026-11-21 (both yes): an apostrophe in a # comment hid later destructive
    statements, including an EF removal of the configured database, from both guards (t14 Q1),
    and hid an arm write from both guards' arm-write check; a statement, script name or arm
    name that stands only in a # comment both shells read as a comment no longer blocks. A
    human-only script name now blocks wherever it appears, except after the listed read
    commands (cat, Get-Content, grep, echo, git show and the others); list them, say that sed,
    less and more are not among them, that rg with --pre, git grep with -O and any environment
    change in the same call block, and that an agent that is blocked uses a listed command or
    asks the person. Name the text-guard limit: a name built at run time, or a listed command
    turned into a launcher by configuration written outside the call, is not seen.
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

**Depends on:** 5, 6, 16 — blocks 4, 10, 12 and 14 are replaced by the fifth security review (16), as for block 6. Before amendment 4 this line read "5, 6, 14"; before amendment 3, "5, 6, 12"; before amendment 2, "5, 6, 10".

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t7-final-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review the whole parent branch against the contract, and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md. This block runs
  after blocks 5, 6 and the fifth security review (16) have passed. The security fixes (8, 11,
  13 and 15) are in the branch through block 16's dependencies; the second live trial (9) and
  the blocked reviews (10, 12 and 14) are not in that chain but merged before block 16 was
  released.
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
    blocked report: the t4, t10, t12 and t14 reports must all be named in the supersedes list
    of the passing fifth review's Gate Output
    (t16-security-re-review-round-five-security-auditor.gate.json). If one is still effective,
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

### 15. Security review fixes, round four (`python-ai-developer`)

**Depends on:** 13 — it fixes the findings of the fourth security review (block 14), but does not name block 14, because the loop never releases a block whose dependency reads `blocked` (the same convention as blocks 8, 11 and 13, which name neither 4, 10 nor 12). It is not dispatched until the contract is re-approved with the amendment-4 answers and (after t15 stopped on 2026-11-22 with no change) the amendment-5 answer (given 2026-11-22: retire only the update-script instance of r4.16.7).

**Files to touch:**
- `.claude/hooks/db-destructive-guard.py`
- `.claude/hooks/db-research-readonly-guard.py`
- `.claude/hooks/tests/test_database_override.py`
- `.claude/hooks/tests/test_db_destructive_guard.py`

`db-research-readonly-guard.py` is listed for L2 only (its `_audit`). Its decision code is not changed (L1 stays accepted; it has no human-only class). It gets the comment-aware masker without an edit, because its Arm-write test loads the destructive guard's masker (`:501-518`). Its L2 row and its arm-write comment rows go in `test_database_override.py`, beside block 13's I2 rows and the destructive guard's arm-write comment rows. `test_db_destructive_guard.py` is listed for two things: the Q1 rows D1 to D6 and D8 and the masker exclusion rows, which are destructive-command detection rows and belong with that suite; and the retirement, by name, of a row that pins one of t14's shapes as allowed, plus (amendment 5) the one named retirement of the update-script instance of r4.16.7, replaced by r4.16.7b (see the constraints). `_switches.py` and `_shell_write_targets.py` are not listed and are not changed.

**What the rows prove, plainly.** As in blocks 11 and 13, the destructive guard is the deciding guard for B1, P1, P2, P3 and T1, and only its rows expect a block. This contract does not claim that the read-only guard blocks any of these shapes. Per t14, armed, the read-only guard asks and claims the arm on the shapes that hold a database write (A1, A1p, X1e, X3a, X3h, A4, A7, A10, A11, A13, A21, A41, A53; L1, accepted), and whether the host then shows a prompt rests on the ASSUMED "a block beats an ask". For Q1 the rows are the destructive guard's: D1 to D6 expect a block, and D8, armed, expects the normal armed ask with the arm claimed, because an EF removal is not human-only. The read-only guard's outcome on D1 and D3 (a block, from its own write check) is not changed and is not the evidence. For L2 both guards have a row, because each writes its own audit log. For the arm-write comment route both guards have rows, because each runs its own Arm-write test; each guard's refusal is its own evidence.

**Pre-written TASK block:**
```
TASK: Fix findings B1 (round four), P1, P2, P3, T1, L2 and Q1 of the fourth security review
  (Q1 and the inverted classifier by the user's answers of 2026-11-21, both yes), each with
  test rows, and nothing else.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (the No-prompt
  classes rule: the mid-word quote clause, the Comment-aware masker, the command-start words,
  Mention positions and Name matching; the Audit-log rule's link-count check; Failure Modes;
  the amendment-4 and amendment-5 Open Questions and the user's answers recorded there); the review
  .claude/reviews/2026-11-16-file-based-switches/t14-security-re-review-round-four-security-auditor.md
  (findings B1, P1, Q1, P2, P3, T1, L2, F1; the Evidence tables "New shapes at head" and "Q1 at
  head"; the Disposition). Read it in full. Its row ids, clause order, script paths, quotes,
  comment text and escape characters are exact; its destructive statements are named in
  words by the report's own rule, so rebuild each one from those words by string joining, as
  the existing rows do. Naming: t14's findings P1, P2 and P3 are not t4's probes P1 to P9;
  use the t14 row ids (X, A, D, V, W, CV, CW, M) for rows.
FILES: as listed.
CONSTRAINTS:
  - RED before GREEN, in this one block (the block 8, 11 and 13 convention): commit the new
    rows first, run them at the parent tip, and list in the pull request body each new row
    under its kind, with its outcome at the tip and at your head. The fix commit comes after.
    Every row is one of four kinds, and no other kind exists:
    (1) Copied rows, every row copied from t14. Each MUST fail at the tip. A copied row that
    passes at the tip has been mistranscribed (a lost backslash, backtick or apostrophe, the
    comment on the wrong line, a backslash path where t14 used forward slashes): fix it until
    it fails at the tip; never relabel it.
    (2) Class rows: the two class sets, the arm-write comment rows, the multi-hop pipe and
    substitution rows, and the constructed P2 and P3 rows with a separate value or word. Each
    is expected to fail at the tip. One that already has its expected outcome at the tip
    moves to kind (3), named so in the pull request body.
    (3) Mutation rows: a row whose expected outcome already holds at the tip, because the
    shape it guards only becomes dangerous with this fix. These are named here: the masker
    exclusion and escape rows, the here-document spelling rows, the cross-shell continuation
    rows, the P2 rows with the value after =, exception (a) written as a backtick or $(
    command, and any class row moved from kind (2). Such a row cannot fail at the tip, so its
    proof is a named mutation of your fix (for example "the comment rule uses the bash reading
    only", "the here-document start knows only <<WORD", "joining is applied to the whole
    text", "exception (b) looks at the next segment only", "the long option is skipped only
    with a separate value"). Apply the mutation in a scratch copy, show the row fails under
    it, do not commit it, and record the mutation and the result in the pull request body.
    (4) Controls: rows this TASK names as must stay allowed, or as already blocking at the tip
    (D0, D0e, D7). Each passes at the tip and at your head. Each allowed mention-word row is
    also shown to fail under the mutation "the mention list is empty".
  - Process lesson from t14 (each earlier round copied only the last report's shapes): besides
    the copied rows, write class rows for the two new classes, in bash AND PowerShell, each
    failing at the tip: (i) a # comment holding an apostrophe on the line before the script,
    on an echo / Write-Host, git commit -m, grep / Select-String and gh pr create line, and
    one with the comment at the end of a line that itself does something; (ii) a quote opened
    mid-word right before the script name, single and double quote, forward-slash and
    backslash prefix (backslash in bash only where bash keeps it), after a separator, after a
    command-start word (then, sudo) and inside a launcher's quoted argument. A class row that
    already blocks at the tip is a kind (3) mutation row, with its mutation named.
  - Script spelling: tools/db-protection/update-dev-database.cmd in bash rows and
    tools\db-protection\update-dev-database.cmd in PowerShell rows, except where t14 writes a
    forward-slash PowerShell row (X3f, X3g, X3h): copy each row exactly as t14 writes it. A row
    that exists in one shell only is written once, in that shell. Each row runs the
    destructive guard alone, in its own fresh temporary project with its own arm.
  - B1 and P1. (a) Mid-word quote: in each of the four readings, a quote opened inside the
    word that holds the name belongs to that word, so the word is judged by its position;
    the quote-blind reading also strips a quote after the folder prefix and quotes inside it.
    (b) Comment-aware masker, for all four consumers (user answer 2026-11-21: yes), as the
    No-prompt classes rule words it. The bash reading and the PowerShell reading, each with
    its own escape model and each recognising its own comments, here-documents or
    here-strings and block comments, decide whether a # is outside quotes and starts a word
    (start of text or line, unescaped space or tab, ; | & ( )); _skip_quoted's pairing never
    decides it. A line comment is blanked to the end of its physical line only where both
    readings start one at the same #, and is never scanned for quotes. Nothing is blanked in
    a here-document body (every delimiter spelling the rule names, to the exact end line or
    to the end of the text), after an unparsable << that is not <<<, in a PowerShell
    here-string, on a line after --%, or inside <# ... #>, where no quote opens a span.
    Arm-write comment rows, in test_database_override.py, per guard (destructive and
    read-only), each guard as a separate process, in bash (touch) and PowerShell (New-Item
    -ItemType File): a line echo "x"  # don't, then on the next line the arm write of the
    path .claude/database-override.once, then echo 'y'; expect the arm-write refusal, exit 2. Control: a line that only names the arm inside a comment both readings agree on
    is allowed. Copied rows, armed, default mode, expect exit 2, no ask JSON, the
    arm still in place, the human-only instruction in the block text: A1, A1p, X1e, X3a, X3h.
    No arm, expect exit 2: X1, X1c, X1d, X3, X3b, X3i (bash); X1p, X3f, X3g (PowerShell).
  - Q1 (user answer 2026-11-21: yes), in test_db_destructive_guard.py, each in
    t14's shell and also in the other shell: D1 and D3 (comment apostrophe, then a removal of
    a non-disposable database through sqlcmd), D2, D4 and D5 (the same with an EF removal,
    including after a git commit -m line), D6 (an empty-table statement on a protected
    database through sqlcmd -d): expect exit 2. D8 (armed, the EF removal after a comment
    apostrophe): expect the ask JSON, exit 0, the arm claimed. Controls that already block at
    the tip: D0, D0e, D7. Masker exclusion rows (kind 3), each expecting exit 2: a
    here-document fed to sqlcmd whose body line holds a #temp table name and then a removal
    of a non-disposable database, once per delimiter spelling (<<WORD, << WORD, <<'WORD',
    <<"WORD", <<\WORD, <<E"O"F, and <<-WORD with a tab-indented end line), once with no end
    line, and once after an unparsable <<; a PowerShell here-string (@" and @') holding the
    same line; a PowerShell line with --% then # then a removal; a # inside a word ($#,
    ${#x}, a#b) before a removal on the same line; a PowerShell <# block whose second line is
    a removal. Escape rows (kind 3), each expecting exit 2, each in three forms (an EF
    removal after it; the human-only script after it; an arm write after it, per guard, in
    test_database_override.py): bash echo "a\" # b"; then the form; PowerShell
    Write-Host "a`" # b"; then the form; bash echo a\ # ; then the form; PowerShell
    echo a` # ; then the form; a bash $'…' span holding \' before the #; a PowerShell
    doubled quote before the #. Masker controls that must stay allowed: a commit message, an echo text and a pull
    request body holding # and apostrophes inside their quotes; a # comment that names the
    script; a # comment that names a destructive statement.
  - P2: add the long spellings of every valued option block 13 lists (--signal, --kill-after,
    --user, --group, --host, --prompt, --close-from, --chdir, --role, --type, --other-user,
    --unset, --adjustment, --replace, --max-args, --max-procs, --max-lines, --delimiter,
    --arg-file, --eof, --max-chars), the value in the next word or after =. Copied rows, no
    arm, expect exit 2: X41, X42, X43, X44, X45; armed, as above: A41. Constructed rows, one
    per long option, no arm, expect exit 2: with the value in the next word (kind 2) and
    after = (kind 3; t14 records --signal=KILL as already blocking). Control that must stay
    allowed: nice --adjustment 10 cat <script> (a mention after a valued long option).
  - P3 (user answer 2026-11-21: yes, fail-closed inversion with the closed mention list):
    implement the Mention positions sentence in _human_only_script_hits and only what it
    needs from _in_command_position. Every visible occurrence is invoked unless EVERY reading
    that sees it places it in a mention position (the closed word list in the rule, without
    sed, less and more; rg and git grep only under their argument rules; git with the listed
    subcommands; command -v / -V), and never after an environment change in the same call
    (the Environment rule), with exceptions (a) inside any substitution that is not itself
    a mention argument, or after & / . , (b) output reaching any non-mention segment through
    any chain of pipes or a redirection into a process substitution, (c) a redirection target
    of a non-mention command. Copied rows, no arm, expect exit 2: X4 to X11, X16, X18, X19,
    X20 (bash); X13, X14, X53, X86, X87b, X88b, X89b (PowerShell). Armed, as above: A4, A7,
    A10, A11, A13, A53. Constructed rows, no arm, expect exit 2: X15 winpty, X17 setsid, X80
    to X84 (doas, unbuffer, watch -n 1, flock, ionice); exception (a): $(cat <script>) as a
    command, eval "$(cat <script>)", bash <(cat <script>), PowerShell & (Get-Item <script>),
    and the backtick form (kind 3 where it already blocks); exception (b): cat <script> |
    bash, cat <script> | grep . | cmd, cat <script> | grep . | head -n 99 | sh,
    cat <script> > >(bash), PowerShell Get-Content <script> | iex and Get-Content <script> |
    Out-String | iex; exception (c): bash < <script>; the argument and Environment rules:
    rg --pre <script> x ., rg --pre=<script> x ., git grep -O<script> x, git grep -nO x --
    <script>, git grep --open-files-in-pager x -- <script>, RIPGREP_CONFIG_PATH=cfg rg x
    <script>, GIT_EXTERNAL_DIFF=bash git diff -- <script>, export X=1; cat <script>,
    PowerShell $env:GIT_PAGER = 'x'; git log -- <script>; the removed words: sed -n 1p
    <script>, less <script>, more <script>; and find . -name <script> (an accepted false
    block, named so in the pull request body, as are the removed-word rows). Allowed rows,
    one per mention word of the rule, each with the bare script path as its argument, in the
    shell the word belongs to, and one per shell for a quoted assignment value ($x =
    "<script>", X="<script>"), plus echo $(cat <script>) and cat <script> | grep . | head. Add
    no word to the mention list (amendment 5, user answer 2026-11-22), and never a word that
    can run a program from its arguments, its environment or its options. One existing allow
    row flips under the list and is retired by name: the update-script instance of r4.16.7
    (the retirement item below). If any other existing must-stay-allowed row flips under the
    list, whatever word it needs, stop and report an AMENDMENT. Do not add the word, and do
    not retire or edit the row.
  - T1: implement the Name matching sentence: the stem with or without .cmd or .bat and with
    trailing dots, not followed by a word character, dot or hyphen. Joining is per reading and
    only adds readings: an added bash reading joins backslash-newline outside single quotes and
    outside a bash comment; an added PowerShell reading joins backtick-newline outside single
    quotes and outside a PowerShell comment; an added splice reading per shell removes an
    empty quote pair touching a non-space character. Recognise comments first in each reading;
    never join a continuation inside a comment; never join on the whole text and never drop
    the unjoined readings. The masker runs before this on the original text. Look for the
    recover flag on the physical line and in the rest of each joined reading's line.
    Cross-shell rows (kind 3), no arm, expect exit 2: PowerShell Write-Host a \ then the
    script on the next line; bash echo ` then a newline and the script followed by `; a bash
    # comment ending in \ then the script on the next line; a PowerShell # comment ending in
    a backtick then the script on the next line (mutation: "joining is applied to the whole
    text"). Copied rows, no arm, expect exit 2: X21 (PowerShell),
    X21b, X23, X24, X22 (bash), X22p (PowerShell); armed, as above: A21. Controls that must stay
    allowed: cat tools/db-protection/update-dev-database.md and
    cat tools/db-protection/update-dev-database-notes.txt (another file, not the script). X25
    (concatenation) is the named text-guard limit: no row.
  - L2: in each guard's _audit, after the fstat check, require a link count of one before any
    byte is written; otherwise close the descriptor unwritten, skip the record and write the
    one standard-error line, as the Audit-log rule says. Rows, per guard, the guard as a
    separate process: a hard link at the log (os.link) to a file outside .claude/logs; the
    guard gives its normal block, the record is skipped, the other file is unchanged.
    Controls: block 13's regular-log, missing-log and rotation rows stay green.
  - Controls that must stay green, unchanged: MENTION_ROWS and LAUNCHER_ROWS in
    test_database_override.py, every block 11 and block 13 row, O11, O12, O13b, O14, and the
    must-stay-allowed rows r4.7a.6 to r4.7a.13 (with r4.7a.7b and r4.7a.12b) and r4.16.1 to
    r4.16.9 in test_db_destructive_guard.py, except the one instance retired below
    (amendment 5). The other three r4.16.7 instances stay controls, unchanged:
    restore-latest.cmd (no recover flag, so not human-only), verify-migration.cmd and
    check-protection-status.cmd. Keep the restore-latest.cmd instance as a named control, and
    keep r4.16.6 (cat of update-dev-database.cmd) as the retired row's pair: same script,
    same arm state, a listed word, still allowed.
    Add as allowed rows t14's controls CV1, CV2, CW1 to CW5, M1c, M2, M2p, M3, M3b and the #
    comment that names the script; add M1, M1b, M4 and X49 as rows that expect a block
    (accepted false blocks, Failure Modes).
  - Retire r4.16.7 for update-dev-database.cmd by name (amendment 5, the user's answer of
    2026-11-22 to the Amendment 5 Open Question: "Retire only this row (Recommended)"). This
    is the only row retired because of the mention list. The row
    "r4.16.7 sed -n of update-dev-database.cmd  [passes today]" expects an allow for a sed
    read of a human-only script, and sed has left the mention list. Remove that one instance
    from the r4.16.7 comprehension and leave the other three as they are.
    Add a row named "r4.16.7b sed -n of update-dev-database.cmd, blocked after sed left the
    mention list". It uses the same command text and no arm, and it expects exit 2 with the
    human-only instruction in the block text. It is a kind (2) row, filed with the constructed
    P3 removed-word rows. It fails at the parent tip, where it allows, and passes at your
    head. In the pull request body, name the old row by its exact name (with the suffix) and
    the new row, with the old expectation (allow) and the new one (block, exit 2).
    This row and the constructed "sed -n 1p <script>" row both stand.
  - Older-test search, one question per change, before the fix commit, recorded in the pull
    request body with the patterns used: (1) comment blanking: which existing rows hold a #
    outside quotes; (2) the inverted classifier: which existing ALLOW rows name a human-only
    script outside a quoted prose span; (3) the stem match: which existing rows name the stem
    without its extension; (4) continuation joining and empty-pair removal: which rows hold a
    trailing backslash or backtick before a newline, or '' / "", and in which shell; (5) the
    link count: which audit rows use a log with more than one link; (6) the Arm-write tests:
    which existing arm-write rows, in either guard, hold a # outside quotes; (7) the shortened
    mention list and the Environment rule: which existing ALLOW rows name a human-only script
    after sed, less, more, rg, git grep or an environment change. One answer to (7) is already
    known and is not a control: the update-script instance of r4.16.7, retired above
    (amendment 5). The restore-latest.cmd instance is not an answer to (7), because without
    the recover flag it is not human-only. Report every other answer. If any other answer to
    (7) flips at your head, stop and report an AMENDMENT. Then run the full guard suites on the
    fix commit.
  - Existing guard suites unchanged and green: test_switches.py, test_db_destructive_guard.py,
    test_db_guard_path_allowlist.py, test_readonly_guard_disposable_exemption.py,
    test_worktree_path_guards.py, test_shell_write_targets.py, test_switch_env_scan.py, and the
    db-protection fixture suite. If a row there expects ALLOW for one of t14's B1, P1, P2, P3
    or T1 shapes, it pins the defect: retire it by name in test_db_destructive_guard.py,
    replace it with the blocking row, and name both in the pull request body. A row whose
    flipped text stands entirely inside a # comment as the masker rule defines it is retired
    the same way, as the one intended loosening. The update-script instance of r4.16.7 is
    retired as the item above says (amendment 5); no other row is retired because of the
    mention list. Any other row that changes outcome, in any suite: stop and report an
    AMENDMENT; do not edit it, do not add a word to the mention list, and do not drop or
    weaken a reading or a list entry to make a row pass.
  - Do not fix L1, the other hooks' plain opens, or the text-guard limit (concatenation, a
    variable, -EncodedCommand, a copy under another name). Do not change the human_only flag
    in _decide, the forward EF update class, _shell_write_targets.py or _switches.py. In the
    read-only guard change _audit only.
  - Name destructive statements in words in the pull request body, never as literal command
    text.
  - Plugin version (project CLAUDE.md, Parent Branch Delivery Rule): this sub-task pull request
    goes into feature/file-based-switches and does NOT raise the version. Do not touch
    plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json or
    .claude-plugin/marketplace.json. check_version_bump.py runs in parent mode on this pull
    request and requires the head's version to equal the base's. The landing raises it once.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 16. Security re-review, round five (`security-auditor`)

**Depends on:** 15 — it re-reviews the findings of blocks 4, 10, 12 and 14, but names none of them, because all four records read `blocked`.

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t16-security-re-review-round-five-security-auditor.md`

**Gate Output, written beside the artefact by the same agent and deliberately not listed above:** `.claude/reviews/2026-11-16-file-based-switches/t16-security-re-review-round-five-security-auditor.gate.json`, for the same reason as blocks 9, 10, 12 and 14. It is the file whose `supersedes` list retires the t4, t10, t12 and t14 reports.

**Pre-written TASK block:**
```
TASK: Re-review the database override, the human-only classifier, the comment-aware prose
  masker and both database guards' audit writes after the fourth fixes block, and write the
  review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md (amendment 4:
  the No-prompt classes rule, the Audit-log rule, Failure Modes, the residual-risk paragraph,
  Non-Goals, and the user's answers to the amendment-4 Open Questions; amendment 5: the one
  named retirement, the update-script instance of r4.16.7, replaced by r4.16.7b, and the
  AMENDMENT stop for every other flip, by the user's answer of 2026-11-22); the blocked reports
  .claude/reviews/2026-11-16-file-based-switches/t4-security-review-security-auditor.md,
  t10-security-re-review-security-auditor.md,
  t12-security-re-review-round-three-security-auditor.md and
  t14-security-re-review-round-four-security-auditor.md; the second run sheet
  t9-live-prompt-trial-second-round-senior-test-engineer.md. Naming: keep the t14 report's
  naming. "P1 to P9" are t4's shared-claim and fallback probes; "finding P1", "finding P2"
  and "finding P3" are t14's findings; t12's findings N5 and N6 are not its probe shapes N5
  and N6. Say which one you mean each time.
FILES: .claude/reviews/2026-11-16-file-based-switches/t16-security-re-review-round-five-security-auditor.md
CONSTRAINTS:
  - Name the commit range reviewed, base..head: the fourth fixes block's (15) merge into the
    parent branch. Say whether the reviewed guard and helper files differ between that merge
    and your head. Work in scratch copies under %TEMP% (git archive or a clone), not in a
    worktree under the checkout.
  - Re-run every probe that failed in t4, t10, t12 and t14, in its ORIGINAL clause order and
    spelling, in each shell the probe exists in, armed and unarmed as the report ran it:
    t4's O10, O12, O14, R3, R4, S5; t10's O13, O13e, H1, H3 to H7 and the Disposition's cd and
    Write-Host forms; t12's N1 to N6, N1a to N1c, N2a, N2b, N15, K1 to K6 and N7 to N13; block
    13's per-word and valued-option rows; t14's A1, A1p, X1e, X3a, X3h, X1, X1c, X1d, X1p, X3,
    X3b, X3f, X3g, X3i, X41 to X45, A41, X4 to X11, X13, X14, X16, X18 to X20, X53, X86, X87b,
    X88b, X89b, A4, A7, A10, A11, A13, A53, X21, X21b, X22, X22p, X23, X24, A21, and D1 to D6
    and D8 (Q1 is in block 15 by the user's answer of 2026-11-21). The destructive guard must
    block each, except D8, which must give the normal armed ask with the arm claimed. Also
    re-run block 15's arm-write comment rows in BOTH guards (each must refuse the arm write),
    its escape and here-document rows, its cross-shell continuation rows, and its multi-hop
    pipe, substitution, argument-rule and Environment-rule rows. Report the
    read-only guard's outcome beside each (L1 is accepted: armed, it asks on the shapes with a
    database write), and state what evidence there is for "a hook block beats a hook ask"
    (block 12's instruction, kept). Also run each t14 shape and each new class row of block 15
    in a real bash and a real PowerShell with a harmless probe script, as t14 did, and report
    any shape where the real shell runs the script and the guard does not block.
  - Try further spellings of the two t14 classes (a # comment with an apostrophe before the
    target line; a quote opened mid-word before the name) in both shells, of the masker
    exclusions (every here-document and here-string spelling, --%, # inside a word,
    <# ... #>), and of a # that one shell reads inside a quote or a word because of an
    escape (escaped quotes, escaped spaces, $'…', doubled quotes), each in the destructive,
    human-only and arm-write forms. The classifier is inverted by the user's answer of
    2026-11-21: try mentions after read commands outside the list and report each false
    block; the inverted classifier's false block is accepted in Failure Modes, but a
    must-stay-allowed row that now blocks is a finding, and an occurrence the guard classes
    as a mention while a real shell runs the script is a finding. The update-script instance
    of r4.16.7 ("r4.16.7 sed -n of update-dev-database.cmd  [passes today]"), retired by name
    and replaced by r4.16.7b (amendment 5), is not a must-stay-allowed row; confirm that
    r4.16.7b blocks with the human-only instruction and that r4.16.6 (cat of the same script)
    still allows. Diff test_db_destructive_guard.py and test_database_override.py over the
    reviewed range, and list every allow row or MENTION_ROWS entry that was removed, renamed
    or changed to expect a block. Only that one instance may be retired because of the mention
    list; besides it, only a row block 15's pull request names under its amendment-4 rules (a
    row pinning a t14 shape, a row standing entirely inside an agreed comment) may appear, and
    each must match its rule. Any other entry in that list is a finding.
    Confirm that the restore-latest.cmd instance of r4.16.7 still allows. Try each listed mention
    word's own options for one that runs a program (as rg --pre and git grep -O do), longer
    pipelines and nested substitutions, and continuations read by the other shell.
  - Trust boundary: the residual-risk paragraph names a text-guard limit for the human-only
    class (a name built at run time: concatenation, a variable, -EncodedCommand, a copy under
    another name; a listed command turned into a launcher by configuration written outside
    the call's text; a shell other than bash and PowerShell). A shape inside that limit is
    reported as information, not a finding, unless it is wider than the paragraph states. A
    shape outside it is a finding. A listed mention word that runs a program from its own
    arguments or from an environment change in the same call is outside the limit, so it is
    a finding.
  - Re-run the quoted-launcher rows (bash -c, sh -c, cmd /c, cmd /k, powershell -Command,
    pwsh -c, iex, Invoke-Expression): they must block. Re-run the mention controls
    (MENTION_ROWS, t14's CV1, CV2, CW1 to CW5, M1c, M2, M2p, M3, M3b): they must stay allowed.
    Then re-run the whole override decision set (O0 to O20), the whole route table, and t4's
    shared-claim and fallback probes P1 to P9. Report each with its result at head.
  - Real link attempts on this Windows host: W4 at switches.local.json and I1 at the rules
    file, as t14 ran them (both spellings, os.symlink and cmd /c mklink, the helper present,
    deleted and stale); I2 at db-guard.log and db-research.log (pipe link, folder links,
    rotation on a linked log and a linked .1), as t14 ran them; and L2: a hard link at each
    log to a file outside .claude/logs, which must receive no record. If a link cannot be
    created, say so; that is not a pass.
  - Check the contract's Residual risk paragraph (it must close B1, P1, P2, P3, T1, L2, Q1
    and the arm-write comment route, or name what stays open; carry the text-guard limit,
    the corrected L1 sentence, the t9 limits, W3 (a) and (b)) and the Failure Modes
    dispositions (the t14 B1 and P1 entry, Q1, the comment-aware masker's loosening, the
    arm-write comment route, cross-shell continuation joining, P2, P3, the inverted
    classifier's false block, mention commands that can run a program, the pipeline beyond
    one hop, T1, L2, and every earlier entry t14 checked).
  - Run the guard suites verbatim and record each exit code: test_switches.py,
    test_database_override.py, test_db_destructive_guard.py, test_db_guard_path_allowlist.py,
    test_readonly_guard_disposable_exemption.py, test_worktree_path_guards.py,
    test_shell_write_targets.py, test_switch_env_scan.py.
  - Name destructive statements in words, never as literal command text. Write the artefact in
    the template's six-section shape; the file does NOT exist yet. End the header with one
    verdict line, alone on its line: "**Verdict:** pass", "**Verdict:** pass-with-findings" or
    "**Verdict:** blocked".
  - Write the Gate Output t16-security-re-review-round-five-security-auditor.gate.json beside
    it, as the template says. On pass or pass-with-findings its supersedes list is exactly
    ["t4-security-review-security-auditor.md", "t10-security-re-review-security-auditor.md",
    "t12-security-re-review-round-three-security-auditor.md",
    "t14-security-re-review-round-four-security-auditor.md"]. On blocked it is [] (a report
    that failed to clear a blocker must not retire one).
  - A blocked verdict holds blocks 6 and 7. It leads to an architect amendment of this
    contract, which either adds a further fix block and a further review block, as this round
    did, or records the remaining shapes as stated residuals with the user's agreement. No
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
