# Concept Contract — Replace environment-variable switches with file-based switches

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-16
**Requested by:** user
**Status:** approved
**Revision:** 2026-11-18, security-review remedy round 1. The security review block (`t4`, pull request 440) read `blocked`. This revision adds the fixes block, the second live trial block and the security re-review block (8, 9 and 10), re-links the documents and final review blocks to the re-review, and amends the rules and the residual risk the review found wrong. Blocks 1 to 7 keep their ordinals, headings and ids. Status is `draft` until the critic runs and the user re-approves. Second pass, same day: the user's answers ("Accept all") and the critic's round-two warnings are applied (the W2 rule narrowed, the W4 open made non-blocking, a fresh session in the second trial's step 6, the Gate Output files named in blocks 9 and 10).
**Work Item Brief:** .claude/work-items/2026-11-16-file-based-switches.md
**Parent issue:** #419 (https://github.com/lneninger/claude-agentic-auto-improve/issues/419), opened on 2026-11-16 and recorded in the brief's `id:`.
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. Implementer agents refuse to run unless `Status: approved` or `Status: implemented`. The `concept-gate.py` hook reads `Files to touch` to decide whether an edit is allowed. Lifecycle, budget rule and management commands are as in `.claude/templates/concept-contract.md`.

**Short forms used below.** JSON (JavaScript Object Notation) is the text format of the switch files. SHA-256 is a fixed-length fingerprint of a file's bytes. POSIX shells are the shells of macOS and Linux. Standard output and standard error are a hook's normal and error output streams. A byte order mark (BOM) is an invisible marker some editors put at the start of a file. UTF-8 and UTF-16 are text encodings. SDK means software development kit. The *payload* is the JSON input Claude Code sends to a hook. *Fail-soft* means a failed import leaves the defaults in force instead of stopping the hook. An *atomic rename* is a rename the operating system does in one step, so only one process can win it.

**Delivery shape.** This contract has ten mergeable blocks, so it is delivered through a parent branch (`feature/file-based-switches`, the brief's `branch:`). It needs the parent issue named above, one sub-issue per block (three new ones for blocks 8 to 10) and a landing pull request. No block raises the plugin version; the landing raises it once. The blocks are named in prose by their headings: the RED tests block, the helper block, the live trial block, the security review block, the ordinary switches block, the documents block, the final review block, the fixes block, the second live trial block and the re-review block. The graph: 1 → 2 → {3, 5}; {2, 3} → 4 (delivered, `blocked`); 2 → 8 (fixing 4's findings; 8 cannot name 4, because the loop never releases a block whose dependency reads `blocked`); 2 → 9; {8, 9} → 10; {5, 10} → 6; {5, 6, 10} → 7.

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
- **Broken-file rule.** A file that cannot be read (a permission error, a folder at that path, anything that is not a regular file once links are followed, such as a named pipe, a socket or a device, bytes that decode in no accepted encoding) or that is not a JSON object makes the helper ignore **every** switch file. Every key is then at its default. A broken personal file can therefore never leave a committed `off` in force, nor turn anything off itself. No read may wait. Where the platform offers a non-blocking open (POSIX), the file is opened non-blocking and its kind is checked on the open file itself, so a named pipe neither blocks nor can be swapped in between a check and the open; anything but a regular file is closed unread and counts as unreadable. Windows has no named pipes at a file path, but opening a link whose target is on a disconnected network drive can stall until the hook times out, and a timed-out hook is an allow (the 2026-11-06 drive-letter lesson). So on Windows a switch file that is a link is judged first by its target's drive, from the local drive table with no network access: a network drive or a `\\server\share` target counts as unreadable and is never opened. A project folder that itself sits on a network drive is out of scope.
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
- **No-prompt classes rule.** Commands the destructive guard classes as `human-only`, and the internal-error path (`_fail_closed`), never offer the prompt. Both block. The class is decided from every target the tool call matched, not from the one reason chosen for the block text: when any matched target is `human-only`, the guard does not touch the arm and blocks, whatever other reason (a protected-database write, the EF argument-position check) the same call also raised. The block text then carries the human-only instruction.
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
| Override arm claimed | database guards | `db-guard.log` | tool call identifier, outcome, permission mode |
| Override write refused | database guards | `db-guard.log`, standard error | tool, matched path or text |

### Commands

| Name | Handler | Payload | Possible rejections |
|---|---|---|---|
| Read switch | `_switches.switch(key, project=None)` | key; optional project | an unknown key raises (a programming error, caught by tests) |
| Read every switch | `_switches.effective_switches(project=None)` | optional project | none: problems are reported, never raised |
| Claim database override | `_switches.claim_database_override(project, tool_call_id)` | project; tool call identifier | returns an Override outcome; never raises |
| Name test | `_switches.names_override_file(path_or_text)` | path or masked command text | none |

---

## Reused Mechanisms

- **Two-layer Claude path resolution** (`MECHANISMS.md:46`) — consumed as-is. `project_dir()`, `state_dir()` and `main_checkout_root()` are call-time functions; the helper calls them on each read and never stores a path at import. The bridge `_claude_paths.py` is **not** extended: a script that needs the helper imports the bridge, which already appends the hooks folder to `sys.path`, then imports `_switches` fail-soft.
- **Guard fallback mode** (`:64`) — extended. Each database guard binds `claim_database_override` and `names_override_file` with `getattr`. A missing binding means no override. Each guard keeps an inline copy of the name test for the Arm-write rule, with one fallback test row per copy. Other hooks bind `switch` the same way; a missing binding means the default.
- **Guard rules file** (`:62`) — consumed as-is and not extended (see Alternatives). Its fail-closed rule for the database guard is unchanged.
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

Confidence: Medium. High on the inventory (every read found by search and opened). The live trial (t3) proved the prompt in `default` mode, the block in `bypassPermissions` and headless runs, and the `systemMessage` notice. Medium on the rest of the host behaviour: the allow-rule question and the `acceptEdits`, `plan` and `dontAsk` modes stay ASSUMED until the second live trial block runs.

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
- `ASSUMED`: the payload carries `tool_use_id`, and a block beats an ask when both guards answer one call. Neither was observed live; both rest on the documentation quoted in the helper block's pull request 432 and on the unit rows. If wrong, the second guard blocks a call the first guard asked about, which fails closed.
- `ASSUMED`: a prompt can also be answered by code the person configured: a headless run's permission-prompt tool, an SDK permission callback, or a `PermissionRequest` hook. The guard cannot tell. Verification path: none; stated as residual risk and in the README.
- `ASSUMED`: a `permissions.allow` rule in `settings.json` or `settings.local.json` that matches the command does not turn a hook's `ask` into an allow. The helper block quoted only hook-to-hook precedence ("deny > defer > ask > allow"), and an agent can write those files. If wrong, an agent can approve its own armed command with no prompt, and the override is withdrawn (user answer 2026-11-18). Verification path: the second live trial block, step 6, run in a session started after the rule was written.
- `ASSUMED`: in `acceptEdits` and `plan` mode the host shows the guard's `ask` as a prompt, and in `dontAsk` mode the guard's block holds. The first trial ran only `default`, `bypassPermissions` and headless `auto`. Verification path: the second live trial block, steps 7 to 9. A missing mode cannot be produced from a normal session; it stays covered by the unit suite only, and the run sheet says so.
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
  - **Mitigation:** the amended Broken-file rule: a non-blocking open and a kind check on the open file on POSIX; on Windows, a link to a network target is judged from the drive table and never opened. The fixes block adds a POSIX-only row and a Windows-only row.
- **FM (security review N1):** an arm dated in the future stayed fresh for ever.
  - **Mitigation:** the amended Fresh-arm rule; the fixes block adds rows.
- **Security review W5, N2 and N3, not fixed here (user answer 2026-11-18, Open Question "Prompt target for sqlcmd").** W5 (the prompt shows the target as "unresolved" for `sqlcmd -Q`, also the live trial's finding W1) is a follow-up, decided: naming that target needs a change to the guard's target binder, which is outside the review's fixes, and the host's own prompt shows the full command. N2 (the neutraliser keeps `"` and `;`) is accepted, decided: no command form the auditor tried delivered a quote-forged target, and it joins the W5 follow-up, which reworks the same reason text. N3 (the read-only guard fails open on an internal error) is accepted, decided: it predates this contract, and the destructive guard beside it fails closed and refuses the same arm writes (probe P9).

**Residual risk of the database override, in one place.** An agent can still create the arm through a route no hook sees, or ask the person to approve. The arm is not tied to a command: whichever blocked command comes next uses it up, so the agent chooses which command a person's arm is spent on. A person who armed for one command can be shown another, and for the common `sqlcmd -Q` form the prompt reason names the target only as "unresolved", so the host's own display of the full command is the only place the person sees what will run. A prompt may be answered by code the person configured (a permission-prompt tool, an SDK callback, a `PermissionRequest` hook); then the override is only as careful as that code. Whether a `permissions.allow` rule, which an agent can write, can turn the guard's `ask` into an allow is not yet proven; the second live trial block tests it (required before the re-review, user answer 2026-11-18). If the allow rule wins, the re-review blocks and the override is withdrawn: every destructive command then blocks and the person runs it in their own terminal (user answer 2026-11-18; refusing writes to the settings files was rejected). The withdrawal needs a further amendment, which this decision directs. A person who approves without reading is the remaining hole. Sessions with no prompt get no override; the person runs the command in their own terminal.

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

**Depends on:** 5, 10 — block 4 is no longer named: its record reads `blocked`, and the loop never releases a block whose dependency reads `blocked`; the re-review (10) replaces it.

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
  table of the Inventory. This block runs after the ordinary switches block (5) and the security
  re-review (10) have passed; read the re-review report
  t10-security-re-review-security-auditor.md and the second run sheet
  t9-live-prompt-trial-second-round-senior-test-engineer.md for the residual-risk wording.
FILES: as listed.
CONSTRAINTS:
  - README: replace the variable table with a switch table (key, values, default, effect,
    allowed in), show the whole switch file to edit in an editor, and add a section on the
    Database override arm with PowerShell and POSIX commands for the person's own terminal and
    the stated residual risk as the contract's "Residual risk" paragraph words it: prompts
    answered by code, the arm not tied to a command, and the allow-rule result of the second live
    trial report (t9). Add _switches.py to the helper
    lists. Leave "Change notes by version" as written and add a dated note for this change.
  - CONTRIBUTING: a new switch is one catalog entry, one README row and one on/off test pair,
    never an environment read.
  - Delete the CLAUDE_CONTRACT_SKIP and CLAUDE_VERIFY_REVIEW_GATE text as the table says.
  - INV-12 compares the README table with the catalog. K-3 becomes "concept-gate.py reads the
    concept_gate switch through the helper". Keep the add-on scan rows.
  - Registries: append through .claude/scripts/registry_append.py only. Corrections to
    "Disposable migration dry-run DB" and "Session-start context delivery", the Switch file and
    switch helper mechanism, a correction to the Add-on term, and the five new terms.
  - Do not touch any plugin version file. Run test_plugin_manifests.py,
    test_switch_env_scan.py, test_skill_script_lookup.py and validate_registries.py
    --check-structure.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

### 7. Final review (`fullstack-code-reviewer`)

**Depends on:** 5, 6, 10 — block 4 is replaced by the re-review (10), as for block 6.

**Files to touch:**
- `.claude/reviews/2026-11-16-file-based-switches/t7-final-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review the whole parent branch against the contract, and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md. This block runs
  after blocks 5, 6 and the security re-review (10) have passed; the security fixes (8) and the
  second live trial (9) are in the branch through block 10.
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
    blocked report: the t4 report must be named in the supersedes list of the passing
    re-review's Gate Output (t10-security-re-review-security-auditor.gate.json). If one is still
    effective, the verdict is blocked.
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
