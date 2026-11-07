# Concept Contract — CodeGraph gate survives a dropped MCP connection: command-line route, per-turn connection notice (issue #295)

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-07
**Requested by:** user
**Work Item Brief:** .claude/work-items/2026-11-07-295-codegraph-gate-dropped-mcp.md
**Status:** approved
**Tracking issue:** #295
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. The lifecycle, budget rule and handoff rules are in `.claude/templates/concept-contract.md`.
> **Revision 3 (2026-11-07):** records the user's answers to Q9-Q11 and the live-trial decision (approval first; trials are the implementer's step 0), and answers the third-pass WARNs. Edits stand where they apply; each finding carries `→ Addressed by:`.

---

## Business Concept

- **What is this thing?** After #259 and #261 the `codegraph` add-on's guard lets reads through when CodeGraph is provably unavailable. It has no answer when the server is configured, the index exists, and Claude Code dropped the MCP connection mid-session (seen 2026-11-06 in StockToolScalpingMachine after `/clear`). Only the Retry escape opens the gate, and nothing tells the user. The `codegraph` program still works and its command line mirrors the MCP tools. This contract adds:
  1. **Command-line route.** A Bash call of a Counted command that succeeds opens the Investigation Turn, like an `mcp__codegraph__*` call. The tracker owns it (one writer of the Turn marker).
  2. **Two-route block message.** The banner names the MCP route, a copyable command-line equivalent, and which index a worktree reads.
  3. **Connection notice.** At each prompt the reset hook says so when no `codegraph serve --mcp` process belongs to this session. Silent on a healthy session, never blocks, and yields to a project instruction or a skill's gate.
  4. **Audit record.** One `cli-fallback` record (reason `mcp-unavailable`) per session, when the command-line route opens the gate and no MCP call has succeeded this session (brief criterion 5, literally).
  5. **Hook freshness check.** `addon --check` names an add-on hook that is an older release than the plugin's (both version labels), a manifest row no settings layer has, and a row that lacks its manifest `if`. The check (`/verify-before-done` Step 5.8) and the repair (the codegraph install and uninstall skills) both run the plugin's own installer, so a stale vendored installer can neither hide nor recreate the staleness. This addresses the root cause of the 2026-11-06 report (a vendored guard older than #259's `fail-open:subagent`).
  6. **No kill switch.** No variable or setting turns the gate, the route or the notice off (I-3 of #259).
- **Existing terms:** CodeGraph, Investigation Turn and its amendment (`VOCABULARY.md:16, 123`), Retry escape (`:124`), CodeGraph unavailability reason (`:125`), Project index (`:126`), Transcript turn state / Shadow record (`:127, 130`), Add-on hook, Add-on manifest, Hook registration profile (`:104`), Installed plugin root (`:88`). "Turn marker" and "Session folder" are #259 contract terms.
- **New terms proposed (Universal, promoted at review):**
  - **Command-line route**: a Bash tool call whose command starts with the bare word `codegraph` followed by a space, passes the Counted command test, and arrives as `PostToolUse` (Success signal). The row's `if: "Bash(codegraph *)"` is not a starts-with test (it matches each sub-command of a compound command and strips `VAR=` prefixes), so the tracker applies its own strict token-0 test. The tracker counts it like an MCP call. `codegraph.exe`, `codegraph.cmd` and path forms are not the route.
  - **Counted command**: the closed set `query`, `explore`, `context`, `node`, `callers`, `callees`, `impact`, `files`. Every other subcommand (`status`, `init`, `index`, `sync`, `serve`, `daemon`, …) is not counted.
  - **Session server process**: a descendant of this session's Hook host process whose command line holds the tokens `serve` and `--mcp` and a CodeGraph token (Connection probe).
  - **Hook host process**: the nearest ancestor of a hook process that is not a Python interpreter or launcher and not a shell, trusted only when its image is in the known-host set `{claude}` (case-insensitive, `.exe` stripped) recorded from live trial L4. The set comes from one trial on one install kind (native `claude.exe`); on any other kind (for example npm `node`) the probe is `undecidable` and the notice stays silent, an accepted limitation that criterion 4 does not reach.
  - **Connection notice**: the reset hook's per-prompt message that this session has no Session server process.

---

## End-User View

Not applicable. Reason: no Angular UI surface is touched. The change is hook behaviour, installer output and documentation.

---

## Data Shapes

### Entities (Session folder of #259 unless stated)

| Name | Fields | Invariants | Ownership |
|------|--------|------------|-----------|
| Turn marker (amended) | `turn.json`: `{ts, tool, summary, pid, route}`; `route` is `mcp` or `cli` only. For `cli`, `tool` is `codegraph <subcommand>` and `summary` the subcommand plus its first argument, neutralised like the Copyable command | Written only by the tracker, deleted only by the reset hook. Each counted call rewrites it; `route` is `mcp` once any MCP call of the turn wrote it (`mcp` > `cli`: "cli, then MCP" ends as `mcp`; "MCP, then cli" stays `mcp`). A failed Bash or MCP call arrives as `PostToolUseFailure`, for which no row is registered, so it never reaches the tracker and writes no marker (L1, L7). The guard's decision reads presence only; only the Shadow section reads `route`. No `route` (older tracker) means `mcp`. | tracker |
| MCP-seen flag | `mcp-seen`, empty file, sticky for the session | Created by the tracker after any `mcp__codegraph__*` PostToolUse (only successful calls arrive there; L7). Deleted only by the pruner. | tracker |
| CLI-fallback flag | `logged-cli-fallback` (the `logged-<reason>` form) | Created only after the record landed (`log_event` did not return False). | tracker |
| Add-on manifest (amended) | (a) new row `{event: PostToolUse, matcher: Bash, hook: codegraph-turn-tracker.py, args: ["cli"], if: "Bash(codegraph *)"}`; (b) optional `released_versions: {<hook>: {<folded sha256>: <release label>}}` | (a) The install matches rows on `(event, file, compare_extras)`, not matcher (`auto_improve_finish_install.py:1742`); the `cli` argument gives the row its own key, so the old MCP tracker row does not count as it. The tracker decides by `tool_name`; the argument is row identity only. `if` joins `ADDON_ROW_KEYS`, a non-empty string when present. (b) `released_sha256[h]` lists **released copies only** (`MECHANISMS.md:108`): the hook as shipped at each commit that set a plugin release version. Unreleased in-between commits are never listed. Every listed hash has a `released_versions` label: the EARLIEST release that shipped that copy (a copy unchanged across 0.9.9-0.15.1 is labelled `0.9.9`), so the finding reads "your copy is from 0.9.9; the plugin is 0.16.4", and every label key is listed (test-enforced for each manifest carrying `released_sha256`). An already-listed hash that matches no release: the implementer stops and reports; no invented label. | addon.json |

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Counted command test | Bash PostToolUse command. (1) `run_in_background` not true. (2) After removing one trailing ` 2>&1`, no `;` `&` `\|` `<` `>` `` ` `` `$(` or newline. (3) `shlex.split(posix=True)` succeeds. (4) The raw text starts with `codegraph ` and token 0 is exactly `codegraph`. The row's `if: "Bash(codegraph *)"` is NOT a starts-with test (L2): it matches each sub-command of a compound command and strips leading `VAR=` assignments, so `cd x && codegraph …`, `ls && codegraph …` and `FOO=1 codegraph …` all start the tracker; this strict token-0 test is what refuses them. Path forms do not pass the `if` at all. (5) Token 1 is a Counted command. Not counted: `codegraph.exe …`, `codegraph.cmd …`, any path form (`/c/bin/codegraph …`, `C:\…\codegraph …`), `cd x && …`, `npx codegraph …`, `VAR=1 codegraph …`, pipes. The banner and the notice teach the bare form | the tracker's Bash branch |
| Success signal | **Fixed by L1 and L7: the event name.** `hook_event_name` is `PostToolUse`. A non-zero Bash exit and an errored MCP call arrive as `PostToolUseFailure` (with an `error` field and no `tool_response`), which has no registered row. A Bash `tool_response` is an object with no exit-code field (`stdout`, `stderr`, `interrupted`, …); an MCP `tool_response` is a list of content blocks. So no universal shape rule on `tool_response` applies; the Bash branch also refuses `interrupted: true`. Output text is never read, so an exit-0 "no results" answer counts (L6, L7 soft failures; accepted). STOP rules (L1, L7): not fired | "succeeds", both routes |
| Copyable command | `codegraph explore "<term>"`. `<term>` from the name or pattern `cg_suggestion` computes: keep `[A-Za-z0-9_.-]` and spaces, fold other runs to one space, strip leading `-` and `.` (so it never reads as an option; JOURNAL 2026-10-16), trim to 80, fall back to `Symbol` | the banner only (JOURNAL 2026-10-05) |
| Connection probe | `present` / `absent` / `undecidable`. Finds the Hook host process by walking up from the hook (≤ 8 hops), skipping `{python, python3, pythonw, py, bash, sh, dash, zsh, cmd, powershell, pwsh, env}`; an image outside the known-host set → `undecidable`. The known-host set is `{claude}` (image name compared case-insensitively with `.exe` stripped; L4 saw native `claude.exe` only). **Candidates:** every descendant of the Host within depth 4, of any image, minus the hook's own ancestor chain; the command line of each is read. **CodeGraph token:** a token whose basename, lower-cased, minus `.exe`/`.cmd`/`.bat`/`.js`/`.mjs`/`.cjs`, is `codegraph`, or whose path has a folder segment `codegraph` (an npm package folder, so a `node …\node_modules\…\codegraph\…\x.js serve --mcp` server matches). Tokens are compared after stripping `"` quotes and `^` carets. One server appears as THREE descendants (L4): a `cmd.exe /d /s /c "codegraph ^"serve^" ^"--mcp^""` shim and two `node.exe …\codegraph\…\codegraph.js serve --mcp` processes (the first with quoted `"serve" "--mcp"`); any one match is `present`. A candidate with `serve` and `--mcp` but no CodeGraph token, or with an unreadable command line → `undecidable`. `absent` only when the table was read, the Host found and trusted, and no candidate matched or was ambiguous. Tables: Windows Toolhelp32 via `ctypes`, command lines via `NtQueryInformationProcess` class 60; Linux `/proc`; macOS `ps -axo pid=,ppid=,command=` (timeout = remaining budget); other platforms `undecidable` | the notice. The rules are a pure function over a table of `(pid, parent, image, command line)`; only the reader is platform code |
| Notice time budget | 100 ms wall clock for the section, checked between steps (the guard import, the table read and `ps` are single steps). Pass/fail in the bench's `--reset-budget` mode (Extension Points): **T1** subprocess p50 of this reset hook (fixture meeting every precondition, real probe) ≤ baseline p50 + 150 ms; **T2** in-process notice-section p95 (real probe, 20 runs) ≤ 150 ms. Baseline = the reset hook at the pinned commit `db61fd7` (0.16.1), never `origin/master` or `HEAD`. **Completion check:** the section is a module-level function `notice_section(payload)` returning a closed-set outcome (`shown`, `silent:probe-present`, `silent:precondition`, `silent:host-untrusted`, `silent:undecidable`, `silent:import-failed`, `silent:budget`, `silent:error`); `main` ignores it, so nothing is printed or written. Before T1 the bench calls it in process, with natural Host detection, on the T1 fixture and the installed new-side copy (sibling guard included), and fails ("this run would not measure the probe") unless the outcome is `shown` or `silent:probe-present`. T2 requires that outcome on every run. So an early exit (missing guard, untrusted Host, budget hit) fails instead of passing fast; the bench must therefore run from a Claude Code session | brief criterion 4's "existing hook's time budget" |
| Notice preconditions | ALL: no `agent_id`; server `configured` and index `index-present` for the payload `cwd` (guard's `availability_plan`); `server_starts_process(p)` true, where `p` is the first path `server_verdict` judges for which `_server_state_at(p)` is `configured`, and the function re-reads that path's selected `codegraph` entry for a non-empty `command` (`url`-only is false); probe `absent` | otherwise silent |
| Connection notice (output) | One JSON object: `systemMessage` (user) and `hookSpecificOutput: {hookEventName: UserPromptSubmit, additionalContext}` (model), same fixed text; nothing from the prompt or payload is echoed. It says no `codegraph serve --mcp` process belongs to this session, so the MCP tools are likely gone; `/mcp` can reconnect; meanwhile a Counted command such as `codegraph explore "SymbolName"` in the Bash tool opens the gate for the turn; in a worktree the command line reads the main checkout's index unless one was built there. It ends exactly: **"A project instruction or a skill's explicit gate that forbids shell commands wins over this notice; follow that rule instead."** | per prompt while the condition holds; shape checked by L3 |
| Hook freshness result | Only for an add-on whose manifest carries `released_sha256` (today `codegraph`); others return `freshness: not-applicable` and their old output. **Findings** (exit 1): `addon-hook-outdated` `{file, project-version, plugin-version}` (hash listed; label from `released_versions`); `addon-hook-missing`; `addon-row-missing` `{event, matcher, hook, args}`; `addon-row-outdated` `{event, matcher, hook, args, key: "if", want, have}` (the row is registered but its `if` differs from the manifest's). **Note** (exit unchanged, never NOT READY): `addon-hook-unrecognised` (hash neither listed nor the plugin's copy: an edited copy, or one from a newer plugin than the one that ran; the note names the version that ran). Plugin version: first of `check_version_bump.MANIFESTS` at the root `_resolve_addon` returned (`_separate_plugin_root`, never the project), else `unknown`. JSON always carries `freshness: checked` or `not-applicable`. Route: outdated or missing hook / missing row → re-run `/auto-improve-codegraph-install`; outdated row → `/auto-improve-codegraph-uninstall` then install (an install never rewrites a row) | `addon --check` |
| Row reader | `_existing_registrations` (user, project, local layers) via `_hook_key`, which reads Project hook launcher rows, exec-form rows and shell-string rows; each found entry gains its `if` value (additive). Missing = no registration with the manifest row's `(event, file, compare_extras)`, the install's own `to-add` key, so check and install agree (JOURNAL 2026-11-01). Outdated = a registration with that key whose `if` differs from a manifest row that has one | `addon-row-missing`, `addon-row-outdated` |

### Decision invariants

- **R-1 (single owner):** the tracker is the only writer of `turn.json` and `mcp-seen`; the reset hook the only deleter of `turn.json`; the guard's decision reads presence only, its Shadow section alone reads `route`. No new hook file, marker or turn rule; the new row reuses the tracker.
- **R-2 (guard decision unchanged):** steps 0, 2, 1, 3–7 of #259 / #261 are unchanged; only the banner text changes. I-2 of #259 holds: no MCP tool name, no `cat`, no "through the shell".
- **R-3 (notice cannot hurt):** the section runs after marker and ticket deletion and pruning, wrapped so nothing it raises (`BaseException` included) changes exit 0 or the deletions; on error or timeout stdout stays empty. It writes no file: it sets `sys.dont_write_bytecode` before loading the sibling guard by path (`importlib`). `server_starts_process` has no installer mirror, so it gets its own rows, not the P-1 parity test.
- **R-4 (no kill switch):** no new environment variable or setting. Tests replace only the table-reader function in process.
- **R-5 (audit, criterion 5):** the tracker writes `log_event(hook="codegraph-turn-tracker", event="cli-fallback", session_id, details={reason: "mcp-unavailable", command: <subcommand>})` when it accepts a counted command-line call (Counted command test + Success signal) while `mcp-seen` and `logged-cli-fallback` are both absent, whatever the marker held before. An errored MCP call never suppresses it: it arrives as `PostToolUseFailure`, never reaches the tracker, and so never sets `mcp-seen` (criterion 5). `_error_log` is imported on first use; on import failure it is a no-op and no flag is set. **Known limitation:** a drop after an earlier successful MCP call in the same session writes no record; follow-up `.claude/concepts/followups/2026-11-07-cli-fallback-mid-session-drop.followup.md`.

### Events

| Name | Emitter | Listeners | Payload |
|------|---------|-----------|---------|
| CommandLineRouteUsed | tracker | `turn.json` (route `cli`) | subcommand, summary |
| CliFallbackRecorded | tracker | `log_event` (`cli-fallback`), once per session | reason `mcp-unavailable`, subcommand |
| ConnectionNoticeShown | reset hook | user (`systemMessage`), model (`additionalContext`); not logged | the fixed text |

### Commands

| Name | Handler | Payload | Possible rejections |
|------|---------|---------|---------------------|
| Check the add-on (extended) | `auto_improve_finish_install.py addon --name <add-on> --project . --check [--json]`, read-only | settings layers, project hook files, manifest | exit 1 with findings; exit 2 when it could not check (incl. no separate plugin root, `:2699-2702`) |

---

## Reused Mechanisms

- **#259 Session folder, Turn marker, Retry escape, decision order, `logged-<reason>`**: consumed; marker gains `route`, folder gains `mcp-seen` (joins `KNOWN_FILE_RE`).
- **#261 hot path, lazy imports, Shadow decision**: unchanged in the live path; Shadow record gains `marker_route` (Q5).
- **Add-on layout + amendment** (`MECHANISMS.md:101, 108`): one row, the `if` key, optional `released_versions`, validated in `_read_addon_manifest`, `addon_problems`, `_addon_fixture`.
- **Preview-hash apply** (`:65`): consumed; the `cli` argument makes the row an ordinary `to-add`.
- **`_existing_registrations` / `_hook_key` and the `to-add` key**: the Row reader, plus the additive `if` field.
- **`addon --check`** (#259): extended with the Hook freshness result.
- **Plugin-only script lookup** (the form `/verify-before-done` uses for `concept_changed_check.py`; JOURNAL 2026-10-04, `MECHANISMS.md:102`): Step 5.8 and Step 0 of both codegraph add-on skills use it, under the variable `FIP`. Nothing is lost: without a separate plugin root, the install, removal and check already refuse (`_resolve_addon`, `:2699-2702`). `test_skill_script_lookup.py` learns `PLUGIN_ONLY_VARS = ("FIP",)` beside `PLUGIN_ONLY_SCRIPTS`, because the script stays project-first elsewhere.
- **Guard server-state mirror** (`_server_state_at` / `server_verdict`): extended by `server_starts_process`.
- **Hook registration check** (`:102`): understands `if` (`check_hook_registrations.py:237, 277`); a project with a profile re-records with `record-registrations`.
- **Plugin version check modes** (`:86`): `MANIFESTS`; one patch raise.
- **Considered, not extended:** `plugin_doctor.py --drift` (`:272-278`) is the maintainer's content diff, names no version, and Step 5.8 does not run it; overlap with `addon-hook-missing` is intended.

## New Mechanisms (if any)

None. The Connection probe stays a private function of the reset hook; promotion is not proposed.

---

## Extension Points

- **Tracker:** Bash branch (Counted command test + Success signal) writes the `cli` marker and applies R-5; the MCP branch creates `mcp-seen` on a success.
- **Guard:** banner (two routes, Copyable command, worktree sentence); `server_starts_process(path)`.
- **Reset hook:** the notice section (R-3); `mcp-seen` in `KNOWN_FILE_RE`.
- **`addon.json`:** the row; `released_sha256` additions (released copies only); `released_versions`.
- **Installer:** `ADDON_ROW_KEYS += ("if",)`; the Row reader's `if` field; the Hook freshness result.
- **Bench:** a new `--reset-budget` mode in `bench_codegraph_guard.py`. It never builds the #259 `Workspace`, so `_check_old_is_259` does not run and the default mode is unchanged. It reads the baseline reset hook (and its helpers) with `git show` at the constant `RESET_BASELINE_REF = "db61fd7"`, runs the completion check, checks T1 and T2, and exits 1 on an incomplete run, a breach, or when that commit is absent (with "fetch the full history"). No CI workflow runs the bench or the suites (`.github/workflows/` holds only `version-bump.yml`); the gate is the TASK block's run and the reviewer's re-run.
- **Shadow (Q5):** `marker_route` (`mcp` / `cli` / `null`); `codegraph_shadow_report.py` groups `shadow-more-closed` by it, labelling `cli` "explained (command-line route)"; one line in the cut-over stub.
- **Skills:** codegraph install skill (Step 0 → `FIP`; four rows; the route; the notice and a possible first-prompt false notice; upgrade-age row for 0.16.1; re-record a Hook registration profile with `record-registrations`); uninstall skill (Step 0 → `FIP`; four rows); `/verify-before-done` Step 5.8 (`FIP`; the four finding codes and the note; a result without `freshness` reads "could not check", NOT READY).
- **Docs:** `codegraph-decision-table.md`; README "Changed in 0.16.4" (with the profile note); the `hooks.json` add-on cost text (the tracker also starts after each Bash call the `if` admits, or every Bash call on a host that ignores `if`; JOURNAL 2026-10-28).
- **Registries (post-approval):** a dated CodeGraph amendment ("run a Counted command in Bash") and the five terms.

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| Claude Code host | tracker | PostToolUse stdin (Bash, MCP) | `tool_input.command`, `run_in_background`, `tool_response` (L1, L7) | host → hook |
| Claude Code host | reset hook | UserPromptSubmit stdin / stdout JSON | `session_id`, `cwd`, `agent_id`; `systemMessage`, `additionalContext` (L3) | host ↔ hook |
| reset hook | guard module | `importlib` by sibling path | `availability_plan`, `_server_state_at`, `server_starts_process` | hook → hook |
| tracker | guard | Session folder | `turn.json`, `mcp-seen` | hook → hook |
| install script | project settings | Preview-hash apply | row with `args: ["cli"]` and `if` | script → project |
| three skills | plugin installer | plugin-only lookup `FIP` | `--check --json` with `freshness`; install / removal plans | skill → script |

No REST, SignalR or DTO surface. Both sides of each row are in `Files to touch`, apart from the host.

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold.

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

---

## Non-Goals

- Reconnecting the MCP server; the upstream report; a worktree-local index; reopening #259 / #261.
- Counting compound, piped, `npx`, environment-prefixed or backslash-path command lines, or calls made with the PowerShell tool (Q10).
- Recording a drop after an earlier successful MCP call in the same session (R-5 known limitation; follow-up stub).
- The CodeGraph daemon as a health signal (U-3); teaching the transcript rule the route (cut-over follow-up).
- Hook freshness for add-ons without `released_sha256`; agent files' CodeGraph wording; `plugin_doctor --drift`.
- A notice in subagents or on `SessionStart` (U-1).
- A notice on the install kind L4 did not record (native `claude` versus npm `node`): the Host is untrusted there, so the probe is `undecidable` and the notice is silent (accepted limitation).
- Counting `codegraph.exe`, `codegraph.cmd` or path forms: the row's `if` never starts the tracker for them.

## Confidence

Confidence: Medium. High on R-1/R-2/R-5, the row key, the Row reader and `--check` (read against the code). Medium on the probe and notice output (L3, L4). Low until L1/L7 on the Success signal. The trials gate the first code edit, not approval (user decision, 2026-11-07).

## Alternatives Considered & Why Rejected

- **A (chosen):** count the command line in the existing tracker on a new `if`-narrowed Bash row with its own `cli` argument; probe processes in the reset hook. One turn rule, no hot-path cost, one probe per prompt.
- **B:** the guard reads the transcript for a Bash `codegraph` call. Rejected: the exit code is in a later `tool_result` (output parsing on every Read) and a second turn rule.
- **C:** a live CodeGraph daemon means "connected". Rejected: one daemon per index root serves every session (U-3).
- **D:** fail open on `absent`. Rejected: disables the guard on an unproven scan.
- **E:** widen the tracker row's matcher, or add matcher to the install key. Rejected: an upgrade never rewrites a row; the key change alters every install's `to-add`.
- **F:** keep the skills project-first and only flag a result without `freshness`. Rejected: detects but never answers, and the repair would still run the stale installer.
- **G:** baseline the bench on `origin/master`. Rejected: it moves on merge and trips `_check_old_is_259` (JOURNAL 2026-11-05).

## Uncertain Assumptions

- `VERIFIED via addon.json:12-30, tracker:134-142, reset:258-271, guard:1056-1104`: three rows; the tracker ignores non-MCP tools; the reset hook prints nothing; the banner names only `mcp__codegraph__*`.
- `VERIFIED via auto_improve_finish_install.py:1084-1099, 1171-1188, 1742, 2699-2702`: `_hook_key` reads launcher, exec-form and shell-string rows; `to-add` keys on `(event, file, compare_extras)`; `_resolve_addon` requires a plugin root separate from the project.
- `VERIFIED via bench_codegraph_guard.py:146, 171-174, 466`: the default mode needs a #259 old ref and exits on a guard holding `shadow_section`.
- `VERIFIED via StockToolScalpingMachine/.mcp.json:3-10`: `command: codegraph, args: [serve, --mcp]`.
- `VERIFIED via ~/.codegraph/daemons/743675661e37870a.json` (U-3): one daemon per index root; its command line holds no `serve --mcp`.
- `VERIFIED via 2026-10-05-working-agreements-session-start.md:68` (U-1): `SessionStart` sources. `ASSUMED` (L5): `/clear` starts a new `session_id` and the next prompt fires `UserPromptSubmit`.
- `VERIFIED (L4, native claude.exe only)`: the server is a non-detached descendant of `claude.exe` (hook chain python ← py ← bash ← bash ← claude.exe); it appears as three processes (cmd shim + two node) and both CodeGraph-token rules match. `UNVERIFIED`: npm `node`-hosted Claude Code and other install kinds (silent there).
- `VERIFIED (L1, L7)`: success is the event name; failures arrive as `PostToolUseFailure`; Bash `tool_response` has no exit-code field; MCP `tool_response` is a list. Exit-0 soft failures ("No relevant code found", an unindexed `projectPath`) arrive as `PostToolUse` and count (accepted; output never read).
- `VERIFIED (L2)`: the host honours `if: "Bash(codegraph *)"` on PostToolUse, but it matches per sub-command and strips `VAR=` prefixes (not a starts-with test).
- `VERIFIED (L3)`: the `systemMessage` + `additionalContext` object is accepted; the model receives `additionalContext`, and `systemMessage` is shown as a notice.
- `VERIFIED (L6)`: `codegraph explore x` exits 0 with an index (also for "no results") and from a subfolder, and exits 1 with no index or an unknown flag.
- `ASSUMED`: the hooks at `db61fd7` equal the 0.16.1 release; the implementer confirms `git diff ec882ad db61fd7 -- .claude/addons/codegraph/hooks` is empty, else pins to the release commit.
- **Live trials L1-L7 (user decision, 2026-11-07):** approval comes first. The trials are the implementer's step 0, run in a throwaway trusted folder before any code edit, with results recorded in the implementer's HANDOFF. They gate the first code edit: the implementer STOPS and reports if L1 shows no structured failure signal for a Bash call, if L7 cannot tell an errored MCP call from a successful one, or if L4 matches neither CodeGraph-token rule (or shows a detached server). Results (claude 2.1.319 native, codegraph 1.6.2, Windows 11): L1 VERIFIED, L2 VERIFIED, L3 VERIFIED, L4 VERIFIED (native `claude.exe` only), L5 UNVERIFIED (`claude -p "/clear"` does not run the prompt path, so the interactive `/clear` behaviour stays `ASSUMED`), L6 VERIFIED, L7 VERIFIED. No STOP rule fired. Evidence: `C:\Users\lneni\.claude\jobs\beed435b\tmp\trials\RESULTS.md` (raw logs beside it).

## Failure Modes & Mitigations

- A failed `codegraph` call opens the gate → Success signal (L1), STOP rule, output never read.
- `codegraph explore x; cat secret.cs` counts → control operators refused.
- A false notice on a healthy session → `undecidable` is silent; known-host set; ambiguous candidates silent; `url` servers excluded; first-prompt case is Q11.
- The notice slows or breaks the prompt → budget with T1/T2, R-3 wrapper, `SystemExit` / `RuntimeError` rows.
- The upgrade never adds the Bash row → the `cli` argument; a 0.16.1 plan has exactly one `to-add`.
- A stale vendored installer hides or recreates stale hooks or drops `if` → `FIP` in all three skills; `addon-row-outdated`; a result without `freshness` is "could not check".
- A working row reported missing → shared Row reader and key; per-form rows.
- An unedited copy from a newer plugin than the one that ran → a note, never NOT READY.
- A Hook registration profile fails `row-count-unchanged` → `record-registrations` in the install skill and README.
- Existing suites change outcome. One question per change, answered by READING the hits first: (F1) a 4th row: `registrations`, `to-add`, "three rows" in `test_addons.py`, `test_auto_improve_finish_install.py`, `_addon_fixture.py`, `test_plugin_doctor.py:918-920, 1399`; (F2) `ADDON_ROW_KEYS`, `statusMessage`; (F3) `--check`, `check_addon`, `codegraph-wildcard-missing` (fixtures without hook files get `addon-hook-missing`; give them the plugin's copies); (F4) `shell`, `cat `, `mcp__codegraph__\*` in the guard suites and `test_worktree_path_guards.py`; (F5) each "empty reset output" assertion and its guarded state, changing only rows whose fixture meets every precondition; (F6) `test_codegraph_shadow.py`, `test_codegraph_shadow_report.py`; (F7) `KNOWN_FILE_RE`; (F8) `FI` in `test_skill_script_lookup.py` and any test pinning the two add-on skills' Step 0.
- Subprocess reset rows find the developer's real server → decisions asserted in process; subprocess rows use `codegraph_env()` and assert only exit 0 and "empty or one JSON object".
- CLI-opened turns pollute the cut-over evidence → `marker_route`.

## Open Questions for User

- [x] Q1. Decomposition → Answer (user, 2026-11-07): one mergeable block; live trials (now L1-L7) are the implementer's step 0 (see the live-trial timing answer).
- [x] Q2. Notice channel → Answer (user, 2026-11-07): shown to the user and given to the model.
- [x] Q3. Narrow the row with `if: "Bash(codegraph *)"` → Answer (user, 2026-11-07): yes.
- [x] Q4. Who writes `cli-fallback` → Answer (user, 2026-11-07): the tracker; condition per brief criterion 5 (main session decision, 2026-11-07).
- [x] Q5. Shadow `marker_route` → Answer (user, 2026-11-07): yes.
- [x] Q6. Version labels → Answer (user, 2026-11-07): `released_versions`.
- [x] Q7. `addon-row-missing` → Answer (user, 2026-11-07): yes.
- [x] Q8. Command form → Answer (user, 2026-11-07): strict, one simple command, optional trailing ` 2>&1`.
- [x] **Q9. Vendored project with no plugin install.** Under the plugin-only lookup, Step 5.8 finds no installer and reports "could not check", and Step 5.8 never reports READY on that. **Such a project can never reach READY in `/verify-before-done` while the add-on is installed.** This is already true today: without a separate plugin root, `check_addon` refuses (`:2699-2702`). **(recommended): accept.** Alternative: fall back to the project copy when no plugin install exists, which still exits 2 at `_resolve_addon`.
  → Answer (user, 2026-11-07): accepted as recommended (accept).
- [x] **Q10. PowerShell tool.** **(recommended): out of scope**; the route and notice name the Bash tool. Alternative: matcher `Bash|PowerShell` with a second `if`, needing its own live trial.
  → Answer (user, 2026-11-07): accepted as recommended (PowerShell out of scope).
- [x] **Q11. First-prompt false notice.** A server still starting can read `absent`. **(recommended): accept one notice, stated in the install skill.** Alternative: notice only after two consecutive `absent` prompts (a per-session flag file; every real notice one prompt later).
  → Answer (user, 2026-11-07): accepted as recommended (accept one possible false notice; the install skill states it).
- [x] Live-trial timing → Answer (user, 2026-11-07): approval before the trials; L1-L7 are the implementer's step 0 and gate the first code edit (STOP rules in Uncertain Assumptions).

## Lessons referenced

- **2026-10-04 — A root locator can return the consumer itself under vendoring**: `FIP` in Step 5.8 and both add-on skills; `_separate_plugin_root`.
- **2026-11-05 — An "older release" test fixture must be pinned to a fixed commit**: `RESET_BASELINE_REF` and the `db61fd7` fixtures, which fail (not skip) when absent.
- **2026-11-01 — A shared reader reused by a stricter consumer…** and **2026-11-01 — After merging a base that changes the row shape…**: the Row reader and its per-form rows.
- **2026-10-05 — Text delivered to the model must say which rule wins**: the notice's fixed closing sentence.
- **2026-10-05 — Neutralise every field echoed from untrusted input** and **2026-10-16 — Never let free text start an argument handed to a native program**: the Copyable command; the notice's fixed text.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body**: R-5 follows brief criterion 5; Q4 one line.
- **2026-10-22 — Describe a broken install by the rows each install age really has**: 0.16.1 upgrade row, `addon-row-missing`, `addon-row-outdated`.
- **2026-10-28 — A new term's definition must be true against every existing member** and **2026-11-02 — Search a proposed term…**: Hook host process; CodeGraph token covering npm shims; `addon-hook-unrecognised` instead of "edited".
- **2026-11-02 — A "fails the build" claim must name the workflow**: no workflow runs the bench or suites; stated.
- **2026-11-05 — A bridge re-export that silently falls back must say which one it gave**: `notice_section`'s closed-set outcome and the bench's completion check.
- **2026-10-17 — Loosening a guard rule must be checked against its fixtures** and **2026-11-02 — Name the tests a fix may change…**: F1-F8.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test**: `test_skill_script_lookup.py` with `PLUGIN_ONLY_VARS` rows.
- **2026-10-28 — State the real trigger of a hook** and **— Guard messages must use names the guard emits**: `hooks.json` cost text; R-2.
- **2026-10-04 — Do not rely on a host expanding a variable…**, **2026-10-05 — prove with a real trial**, **2026-10-04 — Check a documented guard behaviour against the code**: L1-L7, STOP rules, VERIFIED citations.
- **2026-10-28 — Do not promote a mechanism the registry describes as an extension seam**: no new mechanism.
- **2026-11-02 — A revision that adds a path adds its failure modes**: each new path has an FM.
- Orthogonal to north-stars: none active (`.claude/north-stars/` does not exist; brief `north_stars: none` confirmed).

---

## Implementation Handoff

One mergeable block (Q1). The review runs as `/flow`'s reviewer step. The patch raise to 0.16.4 is in this pull request.

### 1. Command-line route, connection notice and hook freshness check (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/addons/codegraph/hooks/codegraph-first-guard.py`
- `.claude/addons/codegraph/hooks/codegraph-turn-tracker.py`
- `.claude/addons/codegraph/hooks/codegraph-turn-reset.py`
- `.claude/addons/codegraph/addon.json`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/codegraph_shadow_report.py`
- `.claude/hooks/hooks.json`
- `.claude/hooks/tests/test_codegraph_first_guard.py`
- `.claude/hooks/tests/test_codegraph_shadow.py`
- `.claude/hooks/tests/test_addons.py`
- `.claude/hooks/tests/_addon_fixture.py`
- `.claude/hooks/tests/test_worktree_path_guards.py`
- `.claude/hooks/tests/bench_codegraph_guard.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/tests/test_plugin_text_scans.py`
- `.claude/scripts/tests/test_codegraph_shadow_report.py`
- `.claude/scripts/tests/test_skill_script_lookup.py`
- `.claude/scripts/tests/test_plugin_doctor.py`
- `.claude/concepts/followups/2026-11-05-codegraph-hooks-cutover.followup.md`
- `skills/auto-improve-codegraph-install/SKILL.md`
- `skills/auto-improve-codegraph-uninstall/SKILL.md`
- `skills/verify-before-done/SKILL.md`
- `.claude/references/codegraph-decision-table.md`
- `README.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**Pre-written TASK block:**
```
TASK: Add the CodeGraph command-line route to the existing tracker (new Bash row, args ["cli"], if), the
two-route banner, the per-prompt Connection notice, the once-per-session cli-fallback record, the Hook freshness
result in addon --check, the plugin-only FIP lookup in three skills, the bench's --reset-budget mode, the Shadow
record's marker_route, docs, and raise to 0.16.4.
CONTEXT: concept contract .claude/concepts/2026-11-07-295-codegraph-gate-dropped-mcp.md (Data Shapes, R-1..R-5,
  Uncertain Assumptions); brief .claude/work-items/2026-11-07-295-codegraph-gate-dropped-mcp.md.
FILES: see Files to touch.
CONSTRAINTS:
  - STEP 0, before any code edit: run live trials L1-L7 in a throwaway trusted folder (never the main checkout)
    and record each result in your HANDOFF. STOP and report to the user, editing nothing, if L1 shows no
    structured failure signal for a Bash call, L7 cannot tell an errored MCP call from a successful one, or L4
    shows a detached server or a real server command line that neither CodeGraph-token rule matches.
  - Tests first (/tdd-first). The contract is authoritative; do not redesign shapes.
  - Success signal exactly as L1 / L7 recorded. Never parse output.
  - Counted command rows: each "codegraph <Counted command> ..." success -> marker route cli;
    status/init/index/sync/serve/daemon, failure payload, run_in_background, "codegraph explore x; cat a.cs",
    pipes, "cd x && ...", "npx codegraph ...", "VAR=1 codegraph ...", "codegraph.exe explore y",
    "codegraph.cmd explore y", "/c/bin/codegraph explore y", "C:\x\codegraph explore y" -> no marker. A row
    asserts the tracker's own token-0 test refuses the compound and VAR= forms the "Bash(codegraph *)" if admits.
    Marker route rows: cli then mcp -> mcp; mcp then cli -> mcp; a PostToolUseFailure payload -> no marker.
  - AC2 rows: no MCP call, index present, server configured, one counted CLI call, then a source Read -> allowed
    with reason turn-marker-present, in the main session AND with agent_id.
  - AC3 rows: banner names both routes, holds codegraph explore "<term>" and the worktree sentence; a pattern with
    ; $( ` | newline, a leading "-x", and a 200-char name -> neutralised, no leading - or ., <= 80, "Symbol"
    fallback; I-2 needles stay green.
  - Probe rows over a synthetic table: host walk, skip list, 8 hops, unknown Host image -> undecidable, depth 4,
    native "codegraph serve --mcp" -> present, npm "node ...\node_modules\...\codegraph\dist\x.js serve --mcp"
    -> present, the L4 three-process shape (cmd shim with ^" quoting + two node.exe) -> present, Host image
    "Claude.EXE" -> trusted, "node other.js serve --mcp" -> undecidable, daemon only -> absent, unreadable command line ->
    undecidable. Notice rows: present -> silent; absent -> one JSON object, systemMessage == additionalContext,
    ends with the exact precedence sentence, no prompt text; undecidable, agent_id, no index, url-only -> silent;
    table reader raising SystemExit / RuntimeError -> exit 0, empty stdout, marker and tickets deleted, no
    __pycache__ in the hooks folder.
  - bench --reset-budget: baseline via git show RESET_BASELINE_REF ("db61fd7"); completion check (in-process
    notice_section outcome must be shown or silent:probe-present, else exit 1 "this run would not measure the
    probe"); T1 and T2 as written, T2 requiring that outcome on every run; exit 1 on an incomplete run, a breach or
    a missing commit; the default mode untouched. Unit rows: notice_section returns each closed-set outcome
    (guard sibling missing -> silent:import-failed; untrusted Host -> silent:host-untrusted; forced slow step ->
    silent:budget) and main prints nothing for any silent outcome.
  - R-5 rows: accepted cli call with no mcp-seen -> one record; a second cli turn -> none; successful MCP then cli
    -> none; an errored MCP call (PostToolUseFailure, never seen) then cli -> one record. Pruner knows mcp-seen and
    logged-cli-fallback.
  - released_versions labels each hash with the EARLIEST release that shipped it.
  - AC7 rows: the three hooks read no new environment variable (scan against the #259 allow-list); no setting
    disables the route or notice. AC8 rows: addon.json lists exactly three hook files; only the tracker writes
    turn.json / mcp-seen (text scan).
  - addon.json: new row; ADDON_ROW_KEYS gains "if"; released_sha256 gains released copies only (hook at each
    version-setting commit); released_versions labels every hash. A 0.16.1 install's plan has exactly one to-add.
  - check_addon rows: launcher, exec-form, shell-string rows, a row with if, rows in user / local layers -> not
    missing; 0.16.1 settings -> Bash row missing; Bash row without if -> addon-row-outdated; older release copy
    from git show db61fd7 -> addon-hook-outdated with both labels; unknown hash -> note addon-hook-unrecognised,
    exit 0; strict-shell-gate output unchanged and freshness not-applicable. db61fd7 rows FAIL when the commit is
    absent, never skip and never HEAD.
  - Skills: Step 5.8 and Step 0 of both codegraph add-on skills use the plugin-only form into FIP. In
    test_skill_script_lookup.py add PLUGIN_ONLY_VARS = ("FIP",); plugin_only_snippets() also selects by it; the
    project-copy-first row treats FIP as plugin-only; a non-vacuity row asserts a FIP block in each of the three
    skills. A text-scan row asserts Step 5.8 names the four finding codes, the note and the freshness rule.
  - Shadow marker_route; report grouping; one line in the cut-over stub.
  - Answer F1-F8 by reading the hits before editing; fix only fixtures, never a guarded state.
  - Docs as in Extension Points. Raise all four version files to 0.16.4; run py -3 .claude/scripts/check_version_bump.py.
  - Run py -3 .claude/hooks/tests/test_codegraph_first_guard.py, test_codegraph_shadow.py, test_addons.py,
    test_worktree_path_guards.py, py -3 .claude/hooks/tests/bench_codegraph_guard.py --reset-budget, and
    py -3 -m unittest discover -s .claude/scripts/tests -p "test_*.py"; all must pass.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-07-295-codegraph-gate-dropped-mcp.md
  contract_status: approved
```

---

## Post-implementation amendment (2026-11-07)

The live trials (`C:\Users\lneni\.claude\jobs\beed435b\tmp\trials\RESULTS.md`) forced four departures, accepted and already followed by the code and tests (JOURNAL 2026-10-22). The body above is amended where each applies.

1. **No `mcp-error` route.** `route` is only `mcp` or `cli`. A failed Bash or MCP call arrives as `PostToolUseFailure`, for which no row is registered, so it never reaches the tracker (Turn marker, MCP-seen flag, R-5, Shadow `marker_route`, TASK rows).
2. **Success signal is the event name.** `PostToolUse` alone means success. A Bash `tool_response` is an object with no exit-code field, and an MCP `tool_response` is a list, so the draft's "`tool_response` is an object" rule is dropped. Exit-0 soft failures count (output is never read).
3. **The row's `if` is not a starts-with test.** `Bash(codegraph *)` matches each sub-command of a compound command and strips `VAR=` prefixes, so the tracker applies its own strict token-0 test (Command-line route term, Counted command test step 4).
4. **Probe shape from L4.** One server appears as three descendant processes (a `cmd` shim and two `node` processes), with `^"` and `"` quoting that the probe strips before matching. The known-host set is `{claude}`, compared case-insensitively with `.exe` stripped.
5. **Release number.** Master moved on to 0.16.3 (#271, per-user session parent) while this change was in progress, and it was merged into the branch, so this change releases as 0.16.4. `released_versions` labels are the earliest release on master's first-parent line: 0.9.10 for the three oldest copies, and 0.16.3 for all three master 0.16.3 copies, the tracker included.

---

## Review checklist (filled in after implementation)

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both sides
- [ ] `INTEGRATION.md` updated if new surfaces were introduced
- [ ] No orphaned DTO/model mismatches
- [ ] `Status` flipped to `implemented`

---

## Critique

> Round 1 (3 BLOCKER, 12 WARN, 8 NIT, all addressed) was moved to `.claude/contract-history/2026-11-07-295-codegraph-gate-dropped-mcp.round-1.md`. Round 2 follows.

> Round 2 (2 BLOCKER, 7 WARN, 8 NIT, all addressed) was moved to `.claude/contract-history/2026-11-07-295-codegraph-gate-dropped-mcp.round-2.md`. Round 3 follows.

## Critique (third pass)

**Critic:** contract-critic
**Date:** 2026-11-07
**Verdict:** warnings-only

**No BLOCKER remains.** Both second-pass BLOCKERs are fixed, checked against the files:

- **The bench:** `--reset-budget` never builds `Workspace`, so `_check_old_is_259` (called from `Workspace.__init__`, `bench_codegraph_guard.py:146, 171-174`) cannot stop it. It pins its baseline to `db61fd7` and fails when that commit is absent. The default mode and its broken `origin/master` default (`:466`) are left alone, and the TASK block no longer runs them.
- **The repair route:** both add-on skills' Step 0 is project-first today (install `SKILL.md:34-37`, uninstall `:40-42`). It moves to the plugin-only form that `verify-before-done/SKILL.md:363-379` already uses. Moving it costs nothing: a vendored script already looks past the project for its add-ons folder (`_separate_plugin_root`, `auto_improve_finish_install.py:381-392`), and it refuses when it finds no plugin root (`:2699-2702`). `addon-row-outdated` catches a row an older installer wrote without `if`. `ADDON_ROW_KEYS` (`:237`) is the filter that dropped `if`. The test edits are specific enough to write: `plugin_only_snippets()` (`test_skill_script_lookup.py:452-453`), the project-first branch (`:414`) and the empty-value row (`:463-477`). An older installer reading the new manifest tolerates the new keys, because `_read_addon_manifest` (`:2002-2076`) does not reject unknown keys.

### Findings

- **[WARN] The time-budget check can pass while measuring a run that stopped early**
  - **What is wrong:** T1 and T2 time the run but never check where it stopped. R-3 turns any failure into silence, and so do the 100 ms section budget and an untrusted Host. So a run that never reached the command-line reads still passes. Three such cases: the new-side copy lacks the sibling guard (an import error, swallowed); the bench is started from a terminal whose top process is not in the known-host set (`undecidable` before any candidate is read); the guard import alone takes more than 100 ms (the section stops every time). In each case stdout is empty and fast, and the bench reports a pass. The same "silent and fast" outcome also hides the notice from criterion 4 on that machine.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-05 — "A bridge re-export that silently falls back to an inline copy must also say which one it gave" (a silent fallback needs a signal that says which path ran).
  - **Where in this contract:** `## Data Shapes → Value Objects → Notice time budget` — "**T1** subprocess p50 of this reset hook (fixture meeting every precondition, real probe)"
  - → Addressed by: `notice_section(payload)` returns a closed-set outcome (printed nowhere); the bench's completion check fails unless it is `shown` or `silent:probe-present` before T1 and on every T2 run, so a missing guard, an untrusted Host or a budget hit fails; unit rows for each outcome.
- **[WARN] The R-5 row "errored MCP then cli → one record" contradicts the Turn marker rule within one turn**
  - **What is wrong:** An errored MCP call still writes the marker, with route `mcp`. A later `cli` call in the same turn "keeps `mcp`". R-5 fires only "when it writes a `cli` marker", and in that case the gate was already open from the MCP marker, not the command line. Read literally, the row expects no record. Read as across turns, it expects one. The row does not say which. Also, there is no STOP rule for L7. If L7 shows that an errored MCP call cannot be told apart from a successful one, `mcp-seen` is set on every call, and this row cannot be built.
  - **Prior artifact ignored:** `.claude/work-items/2026-11-07-295-codegraph-gate-dropped-mcp.md:36` ("when the command-line route satisfies the gate"). `JOURNAL.md` 2026-10-22 — "An accepted critic WARN or answered Open Question must amend the contract body before approval" (Q4's condition is not stated for this case).
  - **Where in this contract:** `## Implementation Handoff` TASK block — "errored MCP then cli -> one record". `## Data Shapes → Entities → Turn marker (amended)` — "a later `cli` call keeps `mcp`"
  - → Addressed by: an errored MCP call now writes route `mcp-error`, ranked below `cli` (`mcp` > `cli` > `mcp-error`), so "errored MCP, then cli" ends as `cli`; R-5 fires on an accepted command-line call whatever the marker held, gated only by `mcp-seen` (successful MCP calls only); same-turn row; a STOP rule for L7. (Superseded by the post-implementation amendment: L7 showed errored calls arrive as `PostToolUseFailure`, so `mcp-error` was dropped.)
- **[WARN] The Counted command test counts commands the row's `if` never lets reach the tracker**
  - **What is wrong:** The test counts `codegraph.exe` and `codegraph.cmd` by basename, and a forward-slash path such as `/c/bin/codegraph explore x` the same way. The TASK block asserts that those basenames count. But `if: "Bash(codegraph *)"` admits only commands that start with `codegraph `. On a host that honours `if` (L2), those forms never start the tracker. The in-process rows pass while the live route stays shut. So the definition of **Command-line route** in the vocabulary is false for exactly these forms.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-28 — "State the real trigger of a hook, not the printing condition", and 2026-10-28 — "A new term's definition must be true against every existing member".
  - **Where in this contract:** `## Data Shapes → Value Objects → Counted command test` — "(4) Basename of token 0 ... minus `.exe`/`.cmd`/`.bat`". TASK block — "codegraph.exe / .cmd basenames count"
  - → Addressed by: the Counted command is narrowed to what `if: "Bash(codegraph *)"` admits (text starts with `codegraph `, token 0 exactly `codegraph`); `.exe`, `.cmd` and path forms are not counted (rows, Non-Goal), and the Command-line route definition says so.
- **[NIT] `released_versions` maps a hash to one release label, but one hook copy usually shipped in many releases** (the install skill's age table lists "0.9.9 to 0.15.1" as one row). The contract does not say whether a label may name a range or must name the first or last release. Without that, the implementer has to pick one, and "both versions" in criterion 6 reads differently depending on the pick.
  - → Addressed by: the label is the EARLIEST release that shipped the copy (Add-on manifest row, TASK block).
- **[NIT] The known-host set comes from a single L4 trial**, so an install of the other kind (native `claude` versus `node` from npm) gets `undecidable` and never sees the notice. That failure is safe (silent), but the contract does not name this group as one criterion 4 does not reach.
  - → Addressed by: the Hook host process term and a Non-Goal name the other install kind as silent, an accepted limitation.
- **[NIT] The second round was not moved out of the contract**, although revision 2 superseded it (`.claude/templates/concept-contract.md:22`), and with this third pass the file is likely over its 12,000-token **Budget**. Moving it is the main session's job, as with round 1.
  - → Addressed by: left to the main session, as instructed.

### Acceptance criteria against named rows

- **1:** covered by the Counted command rows and the failure-payload row (live forms: see WARN 3).
- **2:** covered by the AC2 rows. The marker check comes before the subagent step (`codegraph-first-guard.py:920` before `:932-935`), so `turn-marker-present` is right with `agent_id` as well.
- **3:** covered by the AC3 rows.
- **4:** present and absent, silence, and the no-exception rule are covered by the probe and notice rows and the `SystemExit` / `RuntimeError` rows. The time budget is covered by `--reset-budget` T1/T2, with WARN 1.
- **5:** covered by the R-5 rows, with WARN 2 on the errored-MCP case.
- **6:** covered by the `check_addon` rows (`addon-hook-outdated` with both labels from `db61fd7`) and the Step 5.8 text-scan row.
- **7:** covered by the AC7 rows.
- **8:** covered by the AC8 rows.

### Applicable journal entries

- **2026-11-05 — An "older release" test fixture must be pinned to a fixed commit** — heeded by `RESET_BASELINE_REF` and the `db61fd7` rows, which fail rather than skip when the commit is absent.
- **2026-10-04 — A root locator can return the consumer itself under vendoring** — heeded by `FIP` in all three skills.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded; the three edits are named.
- **2026-10-28 — State the real trigger of a hook** — heeded for the `hooks.json` cost text, missed for the Counted command forms (WARN 3).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body** — R-5 now matches the brief, with one gap left (WARN 2).
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded. `--reset-budget`, `addon-row-outdated` and `addon-hook-unrecognised` each have a failure-mode line.

### What the critic did not check

- No shell, so the bench, `derive_area.py`, `pr_merged.py --status` (there is one block, so item 14 does not apply), and `git cat-file -e db61fd7` were not run. `db61fd7` is this branch's base commit, as `git log` shows.
- Q1-Q8 were not re-opened; Q9-Q11 remain the user's.
