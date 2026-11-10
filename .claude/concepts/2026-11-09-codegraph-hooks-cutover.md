# Concept Contract — CodeGraph hooks cut-over: the guard decides from the transcript; tracker and reset retire (issue #262)

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-09
**Requested by:** user
**Status:** implemented
**Implemented:** 2026-11-10, automatically, by pr_merged.py after https://github.com/lneninger/claude-agentic-auto-improve/pull/331, https://github.com/lneninger/claude-agentic-auto-improve/pull/334, https://github.com/lneninger/claude-agentic-auto-improve/pull/340; 3 checklist items from review reports, 0 with no structured evidence; not performed (disclosed on #262): New vocabulary terms promoted to `VOCABULARY.md`; owner confirmed resolved: none
**Work Item Brief:** .claude/work-items/2026-11-09-262-codegraph-hooks-cutover.md
**Tracking issue:** #262
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. The lifecycle, budget rule and handoff rules are in `.claude/templates/concept-contract.md`.

---

## Business Concept

- **What is this thing?** The `codegraph` add-on asks the agent to start each Investigation Turn with CodeGraph. Today three hooks share that job. The **guard** (`codegraph-first-guard.py`) blocks `Read`, `Grep` and `Glob` on source files. The **tracker** (`codegraph-turn-tracker.py`) writes the Turn marker `turn.json` after a CodeGraph call. The **reset hook** (`codegraph-turn-reset.py`) deletes that marker at every prompt. It also clears stale session folders and prints the Connection notice. The parent contract `2026-11-05-codegraph-hooks-redesign` (issue #261) taught the guard a second way to answer "was CodeGraph used since the last human prompt?". The guard reads the end of the session transcript, the log file Claude Code itself writes. That answer ran in **shadow** only: computed and logged, never enforced. This contract is the **cut-over**. The guard now decides from the Transcript turn state. The tracker and the reset hook become Disabled add-on hooks: they still ship with the plugin, but no install writes them. Their two remaining duties, clearing old session folders and the Connection notice, move into the guard's file. An existing install upgrades by re-running the install skill.
- **What does not change:** the guard blocks nothing it does not block today. It may allow slightly more, in the three ways Q1 lists (answered). Also unchanged: the retry escape (the identical repeat of a blocked call is allowed once), the fail-open proof steps, `session-state-unusable`, and the rule that there is no kill switch. Ideas 2, 3 and 4 and the `if` narrowing stay deferred to `.claude/concepts/followups/2026-11-09-codegraph-turn-policy-decisions.followup.md` (issue #262 stays open for them).
- **What the waiver costs, and what replaces the evidence.** Before a cut-over, the parent's Q2 rule required 20 real sessions over 7 days in 2 projects, with zero unexplained `shadow-more-closed` (calls the new rule would block and the old rule let through). The user waived that rule on 2026-11-09, when no shadow log existed anywhere. **Risk added:** nobody has measured how often the transcript rule blocks a call that the marker rule allowed in real use. Only the t1 live checks and synthetic fixtures back the rule (`.claude/reviews/2026-11-05-codegraph-hooks-redesign/t1-live-checks-python-ai-developer.md`). A misread boundary (an entry wrongly taken for a human prompt) would close the gate mid-turn. **The cost of one false block is bounded:** the retry escape lets the identical repeat through, so a false block costs one extra round trip. It never stops work. **Five safeguards replace the evidence:**
  1. **Fail open.** Every transcript read that is not a clear `open` or `closed` answer allows, with a logged reason. That covers a missing, unreadable or unparseable transcript, a read past the scan window, a timeout, a rewritten file and an internal error.
  2. **Measurement continues.** The Measurement log keeps writing after the cut-over, one record per guarded call, now with `outcome: enforced`, until its 10 MB cap. The report reads it and says when the cap was hit (Q5). **What the log can show:** how often the gate fails open on the transcript, and by which cause; blocks per tool; blocks followed by an identical retry; reasons; cost. **What it cannot show:** whether a single block was right or wrong. The old rule no longer runs beside the new one, so a false block is recorded exactly like a true one. False blocks are found only when the user reports a block they judge wrong. That is why the rollback rule counts user reports (Q4).
  3. **A live smoke check before merge**, including the cases where the old and new rules **disagree** (block 1). Real `claude -p` sessions are run against the installed cut-over, and the main session runs the one interactive case.
  4. **An independent fail-open review gate** (block 2).
  5. **A documented rollback with a dated check** (Q4). The check is a 7-day report run, owned by the user and anchored in `.claude/concepts/followups/2026-11-09-codegraph-cutover-7-day-check.followup.md`. The rollback is per project at once, or for the whole plugin by a revert release.
- **Existing terms:** CodeGraph, Investigation Turn (`VOCABULARY.md:16`, `:136`), Turn marker, Retry escape, Session folder, Per-user session parent, Transcript turn state (`:132`), Live plan (`:133`), Shadow decision (`:134`), Shadow record (`:135`), Counted command (`:138`), Connection notice, Disabled add-on hook (`:82`), Add-on manifest.
- **Registry amendments at review (Universal).** Block 2's check (12) audits this whole list. Each entry is appended as a dated amendment or correction; earlier text is never edited in place.
  - **VOCABULARY, Investigation Turn** (`:16`, `:125`, `:136`): a turn is the span between two human prompts in the transcript (`human-prompt` entries). A background task notification fires the prompt event but does not end a turn (t1, point b). Three things open a turn, each counted when the main session issues the call, whether or not it succeeds (Q1): a `mcp__codegraph__*` tool use, a Counted command in the Bash tool, or an `Agent` / `Task` tool use (a subagent dispatch, C-7). This replaces the shared-folder rule of `:125`.
  - **VOCABULARY, Transcript turn state** (`:132`): enforced. `codegraph-use` also covers a Bash Counted command; the new class `subagent-dispatch` opens the turn; new cause `unknown:error`.
  - **VOCABULARY, Turn marker, Shadow decision** (`:134`) **and Foreign marker** (`:130`): retired at the cut-over. `turn.json` is neither read nor written, and the foreign-marker check is removed.
  - **VOCABULARY, Live plan** (`:133`): `main()` applies the effects in the C-2 order. There is no shadow step any more.
  - **VOCABULARY, Shadow record** (`:135`): after the cut-over it is a **Measurement record** with `outcome: enforced`. It holds no paired decision.
  - **VOCABULARY, Retry escape** (`:126`): a ticket is valid only within the prompt that issued it, identified by `prompt_key` (12 hex characters of the SHA-256 of `prompt_id`). No hook clears tickets at a prompt any more. A prompt, which is what `prompt_id` names, can be shorter than a turn: a task notification starts a new prompt but not a new turn. A ticket therefore expires there, exactly as today's reset hook deleted it at every prompt.
  - **VOCABULARY, Command-line route** (`:137`) **and Counted command** (`:138`): counted by the guard from the transcript, not by a tracker `PostToolUse`; a failed attempt counts too. The exit-0 rule is retired.
  - **VOCABULARY, Connection notice:** printed by the guard file on its prompt row (`args: ["notice"]`).
  - **MECHANISMS, CodeGraph amendments** (`:107`, `:111`): one hook file, two rows. The guard owns the command-line route, the pruning and the notice. The tracker and the reset hook are disabled.
  - **MECHANISMS, the inline-copy parity counts** (`:45`, `:109`): the disabled tracker and reset copies leave the parity set. The implementer states the new counts from the code.
  - **MECHANISMS, Disabled add-on hook** (`:89-93`): the "Enforced by" line gains the `retire` op of the install (C-8). The refusal `disabled-hook-present` now covers only an edited copy and a `settings.local.json` row. `registration` may be a list.
- **New terms:** none.

---

## End-User View

Not applicable. Reason: no Angular UI surface is touched. The change is hook behaviour, an installer upgrade, a report script and documentation.

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership |
|------|--------|------------|-----------|
| Transcript cursor (amended) | as the parent (`path`, `identity`, `scanned_to`, `skipping`, `turn`, `session_seen`, `updated_at`), plus `open_route` (`mcp` / `cli` / `agent` / null: the strongest route that opened the current turn; `mcp` beats `cli`, which beats `agent`), `open_command` (the Counted subcommand of a `cli` opening, else null), `mcp_seen` (bool, sticky: a `mcp__codegraph__*` use seen this session) | Unchanged rules: inside a usable, existing Session folder only, never through a link; temp file then `os.replace`. **New:** it is written at apply time as a live effect, and the guard may create the Session folder first (the reset hook that used to create it retires). A cursor missing a new field is read as absent, which forces a cold scan. A failed write is ignored. | guard |
| Retry escape ticket (amended) | `ticket-<64 hex>` body `{ts, tool, fingerprint, prompt_key}` | It matches only when the file is a plain file, its JSON parses and its `prompt_key` equals the call's. An old ticket (no key), an unparseable ticket or one from another prompt reads as absent, and step 7 overwrites it. No hook deletes tickets at a prompt any more; the pruner removes them with the folder. | guard |
| Measurement log (amended) | `<CLAUDE_PROJECT_DIR>/.claude/logs/codegraph-shadow.jsonl`, unchanged path, 10 MB stop, 1 KB lines | Every parent invariant holds. The log now holds shadow-era records (written before the upgrade) followed by enforced records. Counts stay lower bounds. | guard |
| Session folder (amended) | as #259/#271; `turn.json` and `mcp-seen` are no longer written | `KNOWN_FILE_RE` keeps every old name (`turn.json`, `mcp-seen`, `pruned`, cursor names), so a folder left by an older release still prunes. | guard |

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Transcript entry class (amended) | `human-prompt` (unchanged t1 rule); `codegraph-use` with a route: `mcp` (an assistant, non-sidechain entry whose content holds a `tool_use` block named `mcp__codegraph__*`), or `cli` (the same entry, with a `tool_use` named `Bash` whose `input.command` passes the tracker's strict Counted-command test and whose `input.run_in_background` is not true); `subagent-dispatch` (an assistant, non-sidechain entry with a `tool_use` named `Agent` or `Task`, C-7); `other` | The strict test moves verbatim from the tracker's `counted_subcommand`: one simple command, an optional trailing ` 2>&1`, no control operator, token 0 exactly `codegraph`, token 1 in the Counted set. The byte pre-filter also admits lines holding `codegraph ` or `"Agent"` or `"Task"`. |
| Transcript turn state (enforced) | `open` / `closed` / `unknown:<cause>`, causes as the parent, plus `error` (an exception inside the read) | The live step 1 input. |
| Turn read limits | parent values unchanged (2 MB read and cold window, 2 MB line skip, 50 ms budget); the clock becomes `time.perf_counter()` | t3 found `time.monotonic()` ticks in 15.6 ms steps on Windows, so the 50 ms budget fired a tick early or late. |
| Guard reasons (amended) | new: `transcript-open` (silent allow), `fail-open:transcript-<cause>` (one stderr line, one log record per session per reason, like every fail-open); removed: `turn-marker-present`; `fail-open:subagent` unchanged | The closed reason set. |
| Measurement record (enforced) | the Shadow record's keys, with `outcome` = `enforced`, `live_*` = the enforced decision and reason, `shadow_*` equal to `live_*`, `turn_marker` = null, `marker_route` replaced by `turn_route` (`mcp` / `cli` / `agent` / null), `shadow_ms` = the turn read's cost | Keeping the keys lets the report's block, retry, tool and `session_seen` counters read it as they are. It carries no second decision, so it cannot mark a block as false (Business Concept, safeguard 2). |

### Guard order (invariants)

- **C-1 (decision order).** Steps run in this order:
  - **0. Session state.** Unchanged.
  - **1. Transcript turn state.** It is read only when step 0 found the Session folder usable, and the cursor is used. An unusable folder skips this step and the state reads `closed`, which is exactly today's "the marker is not read from an unusable folder" (Q3). `open` (opened by any route: `mcp`, `cli` or `agent`, C-7) allows `transcript-open`. A call made inside a subagent (`agent_id` present) reads no transcript: its state is `unknown:subagent`.
  - **2. Targets.** No target, or only non-source targets: allow, silently.
  - **3. Subagent.** `fail-open:subagent`.
  - **3a. Unknown state.** Any other `unknown:<cause>` allows `fail-open:transcript-<cause>`. This step comes after classification, so a `README.md` read prints no fail-open line.
  - **4-5. Index and server.** Unchanged.
  - **6. Ticket.** Matched by fingerprint and `prompt_key`.
  - **7. Block.** Unchanged, including `session-state-unusable` and `retry-ticket-unwritten`.
- **C-2 (plan, then effects).** This is the parent's G-2. The Live plan reads, the transcript included. Apply then runs these effects in order:
  - `availability.json`;
  - the ticket;
  - the cursor write;
  - the `cli-fallback` record (C-4);
  - notice flags and `log_event`;
  - one Measurement record;
  - stderr, then the exit code.

  Nothing after the ticket can change the decision. Each later effect is wrapped, so an exception (`BaseException` included) is swallowed. `decide()`, `evaluate()` and `plan_live()` keep their names, signatures and returns.
- **C-3 (cost).** The parent's G-1 holds: the lazy imports and the patchable module names keep their meaning. The transcript is read before classification. The warm read costs about 0 ms. The cold read costs 7 to 15 ms at p50 and happens once per session (t3 table).
- **C-4 (`cli-fallback` record, moved from the tracker).** When step 1 reads `open` with `open_route` = `cli` and the cursor's `mcp_seen` is false, apply writes one `log_event(hook="codegraph-first-guard", event="cli-fallback", details={"reason": "mcp-unavailable", "command": <open_command>})` per session, and `logged-cli-fallback` only after it lands. What changes: the record now lands at the turn's first guarded call, not at the Bash call. A turn with no guarded call writes none. `mcp_seen` from a cold scan is a lower bound.
- **C-5 (prompt row).** `codegraph-first-guard.py notice` on `UserPromptSubmit` runs two duties:
  1. Once per session (the `pruned` flag), it creates the folder and prunes it. The code moves verbatim from the reset hook: `_first_prompt_of_session`, `prune_session_folders` and the Folder test.
  2. It runs the Connection notice (`notice_section` and the probe, verbatim, calling the guard's own functions, with no load by path). The 100 ms budget and the closed outcome set are unchanged.

  It always exits 0 and never blocks a prompt. Whatever it raises is swallowed. It writes no bytecode. On an unusable folder it prunes nothing and prints the reset hook's one line, with no "gate stays shut" claim. It deletes no ticket, no marker and no legacy sentinel. The install writes its row as a `warn` launcher row (`_written_hook` picks `warn` for every non-`PreToolUse` event).
- **C-6 (one inline copy).** The Per-user session parent code now has one active copy, in the guard. The parity test drops the two disabled files, which stay byte-identical to their last release.
- **C-7 (a subagent dispatch opens the main session's turn).** Today a subagent shares its parent's Session folder, so its CodeGraph call opens the parent's gate. The parent transcript holds only the `Agent` tool use and its result, not the subagent's calls (t1, point a). So under the transcript rule, a turn in which the main session issued an `Agent` (or older `Task`) tool use after the last human prompt reads `open`, with route `agent`, whether or not the subagent used CodeGraph.
  - **Invariant:** every turn the old rule opened through a subagent, the new rule also opens. The rule may also open turns whose subagent never called CodeGraph. That errs toward allowing (Q1).
  - **No cli-fallback record:** an `agent` route writes no `cli-fallback` record.
  - **Calls inside the subagent are unchanged:** the subagent's own guarded calls still allow at step 3 (`fail-open:subagent`).
- **C-8 (retire in two steps; applies to every add-on with a Disabled add-on hook).** The install's `retire` op never deletes a file in the run that removes a row naming it. An already-open session keeps the rows it loaded at its start, whichever form they take:
  - **Plain exec-form rows** are written by installs before the Project hook launcher (`MECHANISMS.md:113`, 2026-11-07). If the file is missing, Python exits 2, and on `UserPromptSubmit` that blocks the prompt.
  - **Launcher rows** come after it. If the file is missing, the launcher exits 1 for `warn`.

  The file must therefore still exist for the rest of that session. Which release first wrote launcher rows for the codegraph add-on is ASSUMED; block 1 reads it from the release commits and writes the age table into the install skill.
  - **Step A (the first run that finds retired rows).** It removes from `settings.json` (the project layer) every row naming a disabled hook, by current or former name. It does this whether or not the file exists, so a project with rows but no files (Dangling hook rows) is healed by the same step. It leaves every file on disk. It does all the usual install work in the same plan hash: guard update, new rows. The preview and the result say "start a new session, then run this install again to delete the leftover files".
  - **Step B (any later run in which no project or local row names the hook).** It deletes the file only when it is a plain file whose folded hash is in the entry's `released_sha256` (the removal's I-8 rule). An edited copy is kept and listed under `kept` with the removal's `kept-differs` reason. It never refuses, so a leftover edited file cannot wall future installs. Step B is optional: a leftover released copy is inert, and `plugin_doctor.py --drift` reports it as `disabled-hook-installed` until it goes.
  - **Refusals (`disabled-hook-present`, nothing written):** a `settings.local.json` row naming a disabled hook, because the install does not write that layer. Also step A when the retired file present is an edited copy, because removing its row would silently switch off the user's own edits; the route is the uninstall skill. The user-layer settings are **not** read by this check, today or after: the code reads only the project and local layers (`auto_improve_finish_install.py:2274-2275`). No install writes a user-layer row for an add-on hook, so a hand-written user-layer row naming a retired project hook is outside the install's reach (Non-Goals).
  - **Same-session risk:** the installer cannot tell whether a new session has started. Step B run in the session that ran step A could delete a file that a loaded plain-form row still names. The install skill therefore asks the user to confirm that a new session has started before it applies a step-B deletion (Q7).
  - **Every add-on:** the `retire` op reads every manifest's `disabled` list, so it changes the `angular-tailwind` install too. A project still carrying `angular-tailwind-advisor.py` or `architecture-advisor.py`, with its `UserPromptSubmit` row, used to be refused and sent to the uninstall skill. A re-run of `/auto-improve-angular-tailwind-install` now removes that row (step A) and, in a later run, deletes an unedited released copy (step B). That add-on's install skill and its `DISABLED.md` section "To remove it from a project that has it" are updated to match, and block 1 adds the same test rows for it.

### Events

| Name | Emitter | Listeners | Payload |
|------|---------|-----------|---------|
| MeasurementRecorded | guard (apply) | measurement log; `codegraph_shadow_report.py` | Measurement record (enforced) |
| GuardFailedOpen (extended) | guard | `log_event` log | `{reason: transcript-<cause>, tool}`, once per session per reason |
| CliFallbackRecorded (moved) | guard (apply) | `log_event` log | as #295 |
| ConnectionNoticeShown (moved) | guard, prompt row | user (`systemMessage`), model (`additionalContext`) | the fixed #295 text |

### Commands

| Name | Handler | Payload | Possible rejections |
|------|---------|---------|---------------------|
| Upgrade the add-on in place (extended) | `auto_improve_finish_install.py addon --name codegraph`, preview then `--apply --expect-sha256` | as today | The `retire` op runs in two steps, per C-8, inside the same plan hash, for every add-on with a `disabled` list. **Step A** removes the retired rows from `settings.json` (the removal's `_rows_to_remove` / `_settings_without`) and keeps the files. **Step B**, in a later run with no row left, deletes unedited released copies and keeps edited ones under `kept`. Refused as `disabled-hook-present`, with nothing written: a `settings.local.json` row naming a disabled hook, or step A with an edited retired copy present. The refusal names the row or file and the uninstall route. The preview lists every step-A and step-B op and the new-session note. |
| Report (extended) | `codegraph_shadow_report.py` | the log | `enforced` joins the outcome set. Records with that outcome are counted in their own "enforced" section: records; reasons split by `agent`; the share of gated calls that are `fail-open:transcript-*` (the Q4 number); blocks; blocks followed by an identical retry (`session`, `fp`, `prompt_key`); blocks per `tool`; `transcript_turn` causes; `shadow_ms` p50 / p95. When the log holds a `log-full` line, the report prints "measurement stopped at the 10 MB cap at <ts>" from that line. The shadow sections count only shadow-era records. Exit codes are unchanged. |
| Roll back | documented in `.claude/addons/codegraph/DISABLED.md` and the install skill | — | **Per project, at once:** `/auto-improve-codegraph-uninstall`, then a new session. **Plugin-wide:** a revert release moves both hooks back into `hooks` and lists the cut-over guard's folded hash in the guard's `released_sha256`, so the update action takes the copy back. A re-run of the install then restores the files and adds the rows. A leftover `notice` row runs the old guard, which exits 0 for any payload without `tool_name` (`codegraph-first-guard.py:1898-1900`). Block 1 tests this path with a revert-manifest fixture. |

---

## Reused Mechanisms

- **Disabled add-on hook** (`MECHANISMS.md:89-93`): extended by the tracker and reset entries. Its Extend-by line says it: "move a hook's name and row … into `disabled`, and add its released hashes". Each entry's `registration` may now be one row object or a list of them. The tracker has two rows, and the validator `_disabled_entries_problem` accepts both forms. The released hashes move from the top-level `released_sha256` into each entry. The two hooks' `released_versions` keys go too, because that map covers only active hooks.
- **Preview-hash apply** (`MECHANISMS.md:66`): extended by the two-step `retire` op (C-8), inside the existing plan hash. It reuses the removal's row-removal rule, and its file-deletion and `kept-differs` rules. Per JOURNAL 2026-10-28, the removal of what an apply wrote extends the apply entry; it is not a new mechanism.
- **Add-on layout** (`:102`, `:110`, `:112`): the manifest now carries one hook, two rows (`PreToolUse` with no args, `UserPromptSubmit` with `notice`) and a `disabled` list. Row identity is `(event, file, args)`, so the prompt row is a new row and `addon --check` reports it as `addon-row-missing` until the upgrade runs. The guard's previous released copies stay listed, and the cut-over copy is added with its label.
- **Hook freshness** (#295): consumed as is. A project on 0.16.x shows `addon-hook-outdated` for the guard and `addon-row-missing` for the prompt row, both routed to "re-run the install".
- **Transcript cursor, Read limits, entry classifier** (Data Shapes of `.claude/concepts/2026-11-05-codegraph-hooks-redesign.md`): extended as in Data Shapes. These are parent-contract components with no MECHANISMS.md entry, so they are cited by contract, not by registry line.
- **Shadow decision log** (that contract's New Mechanisms; promotion was "decide-at-review" and has not happened): consumed in enforced mode. Still not promoted, because a second guard has not adopted it.
- **#259 decision order, Retry escape, `logged-<reason>`, `log_event`:** consumed. The reasons are extended, and the ticket is keyed to the prompt.
- **#295 Counted command test, `notice_section`, Connection probe:** moved verbatim into the guard.
- **Contract sub-task loop:** two mergeable blocks on the parent branch `feature/262-codegraph-hooks-cutover`.

## New Mechanisms (if any)

None. Every change extends a mechanism named above.

---

## Extension Points

- **Guard:**
  - The shadow branch of `_plan` is removed.
  - Step 1 reads the Transcript turn state (C-1).
  - Step 3a is added.
  - Tickets are keyed to the prompt.
  - Apply effects follow C-2.
  - C-4 and C-5 are added.
  - A `notice` argument branch comes first in `main()`.
  - The foreign-marker code goes.
  - The header docstring is rewritten. It currently describes three hooks.
- **`addon.json`:** `hooks` holds the guard alone; `registrations` holds the two guard rows; `disabled` holds the tracker and reset entries, with note `DISABLED.md`; `released_sha256` and `released_versions` change as above.
- **`DISABLED.md` (new):** what each hook did, where each duty went, the cost removed (one process start per prompt and per CodeGraph call; t3: reset 104.7 ms and tracker 101.4 ms at p50, of which the notice row keeps the per-prompt start), how to turn them back on (the rollback), and how to remove them from a project.
- **Installer:** the two-step `retire` op (C-8), its preview wording, and the validator's `registration` list form.
- **Report:** the `enforced` outcome and its section, the fail-open share, and the cap line.
- **Docs:**
  - the codegraph install skill: the upgrade-age table (which release wrote plain or launcher rows, what each age has, what step A and step B do); the new-session confirmation before step B; the rollback;
  - the codegraph uninstall skill: one hook, two possibly-present retired ones;
  - the angular-tailwind install skill and `.claude/addons/angular-tailwind/DISABLED.md`: the advisor now retires in place (C-8);
  - the decision table: enforced, not shadow;
  - `README.md`: its four mentions.

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| Claude Code host | guard | `PreToolUse` stdin | `transcript_path`, `prompt_id`, `agent_id` (t1: present in 2.1.318) | host → hook |
| Claude Code host | guard (`notice`) | `UserPromptSubmit` stdin / stdout JSON | as #295 | host ↔ hook |
| Claude Code host | guard | transcript JSONL, read-only | t1 entry fields, plus `tool_use` `name: "Bash"` and `input.command` (verified, see Uncertain Assumptions) | host file → hook |
| guard | report | measurement log | Measurement record (enforced) | hook → script |
| install script | project settings and hooks folder | Preview-hash apply | `retire` op | script → project |

No REST, SignalR or DTO surface. Both sides of each row are in `Files to touch`, except the host, which is only read.

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold. `.claude/area-mapping.json` has an empty `areas` object, and the orchestrator's `derive_area` result is `uncategorized`. The architect has no shell, so the main session runs `py -3 .claude/scripts/cross_area_scan.py .claude/concepts/2026-11-09-codegraph-hooks-cutover.md` before approval. If it prints any area, this section is revised.

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

---

## Non-Goals

- Ideas 2, 3 and 4, the `if` narrowing, and any new block. These are in the follow-up stub named in Business Concept. The only behaviour changes are the three allow-more ones Q1 accepted.
- Rows in the user-layer settings. The `retire` check reads the project and local layers only, as today, and no install writes a user-layer add-on row.
- Any change to a project outside this repository. The two Scalping projects upgrade by their own re-run of the install skill.
- Redesigning the measurement log or the report beyond the `enforced` outcome.
- Deleting the legacy `<cwd>/.claude/.codegraph-used-this-turn` file. No hook has read it since #259, so a leftover copy is inert.
- The mid-session MCP drop record (`2026-11-07-cli-fallback-mid-session-drop.followup.md`). Its implicated files become the guard; the main session updates the stub.
- Upgrading without re-running the install skill (parent Q3).

## Confidence

Confidence: Medium.
- **High:** the fail-open paths, C-1 and C-2 (they reuse the parent's tested read and its plan/apply split), and step A and step B of the upgrade (they reuse the removal's tested rules and never delete a file a row names).
- **Medium:**
  - the rollback: until block 1's revert-manifest test passes, only the old guard's early exit is verified;
  - the same-session step-B case, which rests on the user confirming a new session;
  - how real sessions behave under the transcript rule, because the waiver removed the measurement. The smoke cases where the rules disagree, user reports and the 7-day check are what move this.

## Alternatives Considered & Why Rejected

- **A (chosen):**
  - The guard decides from the transcript.
  - Both hooks retire.
  - Pruning and the notice move to a prompt row of the guard's own file.
  - The CLI route and a subagent dispatch are counted from the transcript.
  - Retirement runs in two steps.
  - Why: two hook files and three rows go, no #295 behaviour is lost, and no turn the old rule opened is closed. The notice row costs the same one start per prompt that the reset hook already paid, minus the reset hook's load of the guard module by path.
- **B (rejected): retire the reset hook with no prompt row, and drop the Connection notice.** This breaks a #295 acceptance criterion that shipped two days ago. The notice is the only signal that tells the user to run `/mcp`.
- **C (rejected): keep the reset hook as a notice-only hook.** This contradicts acceptance criterion 2, and it keeps a second copy of the Per-user session parent code.
- **D (rejected): print the notice inside the block banner.** The user never sees it, because the banner goes to the model, and it would say nothing on turns that are not blocked.
- **E (rejected): leave the CLI route uncounted.** The brief's criterion 4 asks for it. Without it, every turn opened only by a Bash Counted command (the #295 route for a dropped connection) would block. That would be a new block, which the cut-over must not add. The same reasoning gives C-7: without it, a turn opened through a subagent would block.
- **E2 (rejected): open the main turn only when the subagent's own transcript shows a CodeGraph call.** That means finding and reading `subagents/agent-<id>.jsonl` for every dispatch in the turn. Its cost has no bound in the time budget, and it opens no turn that C-7 leaves closed in the direction that matters (C-7 only allows more).
- **I (rejected): retire in one run, deleting files right after their rows.** A session that loaded plain exec-form rows would then hit a missing script: Python exits 2, and on `UserPromptSubmit` that blocks every prompt until restart (BLOCKER 2 of the critique; user answer 2026-11-09).
- **F (rejected): count a CodeGraph call only when the transcript shows it succeeded**, pairing the `tool_use` with a later `tool_result` that has no `is_error`. That needs a pending-id set in the cursor, and t1 never checked when a `tool_result` is written relative to the next `PreToolUse`. The cost of counting attempts is that a failed call opens the turn, which errs toward allowing more (Q1).
- **G (rejected): a kill switch or marker fallback as the rollback.** That would break I-3 of #259 (no kill switch). Uninstall and a revert release are the rollback.
- **H (rejected): three blocks, with the installer split from the guard.** On the parent branch the manifest and the `retire` op must land together, or every re-install refuses with `disabled-hook-present` in between.

## Uncertain Assumptions

- `VERIFIED via t1 artefact`: `prompt_id` equals the human prompt's `promptId` and is carried by later tool hooks. A hook killed at its timeout lets the call through. A subagent's entries are in another file, and the parent file holds only the `Agent` tool use and its result (`:17`, `:31`). So a call made inside a subagent reads no transcript (S-4), and the parent's turn is opened by the dispatch entry instead (C-7).
- `ASSUMED`: the dispatch tool is named `Agent` (2.1.318, t1) or `Task` (older hosts), and its `tool_use` entry is in the parent transcript before the next main-session `PreToolUse`. t1 saw this for CodeGraph `tool_use` entries, not dispatch entries. Verification: the smoke case "subagent dispatch, then Read".
- `ASSUMED`: which codegraph release first wrote Project hook launcher rows; older installs carry plain exec-form rows. Verification: block 1 reads the release commits and writes the age table into the install skill. C-8 is safe for both forms either way.
- `VERIFIED via this workstation's interactive transcript` (`~/.claude/projects/D--Dev-HIPALANET-claude-agentic-auto-improve/f4ab933d-….jsonl`, read on 2026-11-09): terminal prompts carry `promptSource` `typed` and `suggestion_accepted`. Both are strings other than `system`, so the t1 rule finds them. This closes t1's main "not checked" item. Bash `tool_use` blocks have the shape `{"name":"Bash","input":{"command":…}}`.
- `VERIFIED via codegraph-first-guard.py:1888-1900`: the current guard exits 0 when `tool_name` is not `Read`, `Grep` or `Glob`, so a leftover `notice` row after a rollback is harmless.
- `VERIFIED via auto_improve_finish_install.py:2257-2285, 2288-2344, 3159-3196, 1406`: the install refuses on a disabled hook (file, or a project or local row only, `:2274-2275`), the removal has reusable row and file rules, and the launcher class is chosen by event. The removal deletes no file while a row names it (`:3124-3126`, I-7). That comment records that a plain row pointing at a missing script exits 2.
- `VERIFIED via test grep`: `test_codegraph_first_guard.py` and `test_worktree_path_guards.py` send no `transcript_path`. Without a fixture change, their block rows would read `fail-open:transcript-no-transcript` and allow.
- `ASSUMED`: `test_plugin_doctor.py` builds its codegraph rows from synthetic fixtures (`:918-920`, `:1399`), so it is not edited. Verification: block 1 runs it unedited.
- `ASSUMED`: the released copies of the tracker and reset at 0.16.4 and 0.16.5 are among the listed hashes, or can be computed. Verification: block 1 folds every released copy from the release commits.
- `ASSUMED`: Claude Code reads hook rows at session start (the removal's `REMOVAL_SESSION_NOTE`). If it hot-reloads them, the new-session note is merely redundant.

## Failure Modes & Mitigations

- **A misread boundary blocks mid-turn (the risk the waiver adds).** The fail-open bias holds: only a positively identified human prompt is a boundary. The retry escape bounds the cost to one round trip. The log cannot mark such a block as false, so detection rests on user reports, which trigger a rollback under Q4, and on the disagreement cases of the smoke check.
- **A turn opened through a subagent blocks the main session's next Read.** C-7: a dispatch opens the turn. There is a guard row for it and a smoke case.
- **The host stops sending `transcript_path`, or changes the format.** The answer is `unknown`, which allows with `fail-open:transcript-<cause>`, logged once per session. The gate then fails open, and the log makes that visible.
- **The block rows of the suites silently fail open.** The fixtures get a closed transcript, so the rows keep their outcomes (JOURNAL 2026-10-17).
- **A stale ticket opens a later turn.** Tickets are keyed by `prompt_key`. A ticket with no key reads as absent.
- **The upgrade removes a file that a loaded row still names.** C-8: step A never deletes a file. In the session that ran it, the old rows keep running their still-present files, whether the rows are plain exec-form or launcher rows, so nothing exits 2 or 1 there. The old reset hook in that session can still delete tickets and print its own notice, which is harmless and ends at the new session.
- **Step B runs in the same session as step A.** A loaded plain-form `UserPromptSubmit` row would then exit 2 and block prompts until restart. The skill asks for confirmation that a new session has started before a step-B deletion (Q7). Recovery is to start a new session, where the row is gone.
- **The project has retired rows but no files (Dangling hook rows).** Step A removes the rows anyway. A plain row was already failing in the current session before the install; the new session heals it.
- **The upgrade deletes an edited hook.** Step B deletes only released copies, and an edited one is kept under `kept-differs`. Step A refuses while an edited copy is present.
- **The `angular-tailwind` install changes behaviour.** Its advisor now retires in place instead of refusing (C-8). It has its own test rows and doc updates in block 1.
- **A new guard copy and an old reset hook both register (two notices).** Step A removes the old rows in the same apply that adds the guard's prompt row, so from the next session only one notice runs. In the current session only the old rows run: rows are read at session start.
- **Pruning or the notice blocks or slows a prompt.** They run on a `warn` row, always exit 0, keep the 100 ms notice budget, prune once per session and write no bytecode.
- **A crash in a late apply effect changes the decision.** Each effect after the ticket is wrapped (C-2).
- **The cut-over guard's hash is missing from `released_sha256`, so the next release reads it as edited.** Block 1 adds it with its label, and block 2 checks it against the final file.
- **A hand-installed project has the retired files but no rows.** Step B deletes the unedited files and keeps an edited one under `kept`.
- **The measurement log reaches its cap.** It stops writing, and the report prints when it stopped. The 7-day check is run before a busy project could fill 10 MB: about 25,000 calls at about 400 bytes per record.
- **The `cli-fallback` record is lost or doubled.** C-4 writes the flag only after the record lands. A turn with no guarded call writes none, which is stated in the install skill.

## Open Questions for User

- [x] **Q1. Turn definition at the cut-over?** Answer (user, 2026-11-09): accept. A task notification does not end a turn, a CodeGraph call counts when issued even if it fails, and a subagent dispatch opens the turn (C-7). All three allow more, none blocks more.
- [x] **Q2. Where the Connection notice and pruning live?** Answer (user, 2026-11-09): on a `UserPromptSubmit` row of the guard's own file (`notice`), as recommended.
- [x] **Q3. Unusable session folder?** Answer (user, 2026-11-09): keep today's `session-state-unusable` block; the transcript is not read.
- [x] **Q4. Rollback rule?** Answer (user, 2026-11-09): after 7 days in the two Scalping projects, run the report. Roll back if over 10% of gated calls fail open on the transcript, or if the user reports any block they judge wrong. The check is anchored in `.claude/concepts/followups/2026-11-09-codegraph-cutover-7-day-check.followup.md` (owner: the user).
- [x] **Q5. Measurement log after the cut-over?** Answer (user, 2026-11-09): stays on, capped at 10 MB (not "indefinitely"); the report says when the cap was hit.
- [x] **Q6. Host with no `prompt_id`?** Answer (user, 2026-11-09): a ticket keyed `none` may match.
- [x] **Q7. How does the install guard against step B running in the same session as step A?** Answer (user, 2026-11-09): ask once, delete only on yes, as recommended below. (New, raised by the two-step answer.) The installer cannot tell whether a new session has started. **Recommendation:** when a step-B deletion is planned, the install skill asks one yes/no question, "Have you started a new session since the last install run?", and applies the deletion only on yes. On no, it applies the rest of the plan with the deletion left out, and says to re-run after restarting. Alternative: no question, with the risk stated in the preview only. That is cheaper, but a plain-form install could then block prompts until restart.

## Critique

**Critic:** contract-critic
**Date:** 2026-11-09
**Verdict:** blockers-found

### Findings

- **[BLOCKER] The cut-over adds a block: a CodeGraph call made by a subagent no longer opens the main session's turn**
  - **What is wrong:** under the marker rule, a subagent shared its parent's Session folder, so its `mcp__codegraph__*` call opened the gate for the main session. Under the transcript rule, the main session's transcript holds only the `Agent` tool use and its result, so the turn reads `closed`, and the main session's next source `Read` is now blocked. That is the delegate-to-Explore-then-Read workflow the decision table recommends. Q1 says "Both changes allow more, never block more", and Alternative E rejects a design because "That would be a new block, which the cut-over must not add". This third difference is missing from both, and from the live smoke list.
  - **Prior artifact ignored:** `VOCABULARY.md:125` (Investigation Turn amendment: "a CodeGraph call by either opens the gate for both until the next prompt"); `.claude/reviews/2026-11-05-codegraph-hooks-redesign/t1-live-checks-python-ai-developer.md:17` ("The parent file holds only the `Agent` tool use and its result; the subagent's CodeGraph tool use is not in it") and `:31` (the subagent fixture classifies as `[3]`: a prompt and no `codegraph-use`); the work item brief's Out of scope: "Any change to what the guard blocks".
  - **Where in this contract:** `## Open Questions for User` Q1: "Both changes allow more, never block more."; `## Uncertain Assumptions`: "A subagent's entries are in another file, so S-4 stays."
  - -> Addressed by: C-7 (an `Agent` / `Task` dispatch in the current turn reads `open`, with its invariant), the `subagent-dispatch` entry class, a guard test row and a smoke case in block 1, the rewritten t1 VERIFIED line plus a new ASSUMED line on the dispatch's name and flush timing, Q1 (three allow-more changes), Alternative E (now also justifies C-7) and E2, and the Non-Goals and "What does not change" wording. User decision 2026-11-09.
- **[BLOCKER] The mid-session upgrade failure mode assumes every install has launcher rows**
  - **What is wrong:** the contract predicts that, in the session that ran the upgrade, the still-loaded old reset and tracker rows print "a non-blocking `warn` line (a missing file exits 1 for `warn`)". That holds only for Project hook launcher rows. Add-on rows written before the launcher existed are plain exec-form rows. The installer's own comment says such a row "points at a missing script exits 2 and would block every prompt". The `retire` op deletes the files in the same session, while those rows stay loaded until a new session starts (the contract's own third ASSUMED item). The contract never says which install ages carry which row form.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22 "Describe a broken install by the rows each install age really has"; `JOURNAL.md` 2026-11-06 "An exception sentence that names the outcome of a later call must list every outcome that call can have"; `.claude/scripts/auto_improve_finish_install.py:3125-3126` (I-7 rationale); `MECHANISMS.md:113` (Project hook launcher, 2026-11-07, which came after the add-on shipped on 2026-10-31, `MECHANISMS.md:16`).
  - **Where in this contract:** `## Failure Modes & Mitigations`: "The launcher then prints a non-blocking `warn` line (a missing file exits 1 for `warn`)."
  - -> Addressed by: C-8, per the user's decision (2026-11-09). Retirement now runs in two steps. Step A removes the rows and keeps the files, so a loaded row of either form still finds its script. Step B deletes leftover unedited copies in a later run and never in the run that removed the row. C-8 names both row forms and their missing-file exits (plain exec-form exits 2, launcher `warn` exits 1). The release that switched forms is ASSUMED, and block 1 writes the age table. The same-session step-B risk is a Failure Mode and the new Q7. Alternative I records the one-step design as rejected.
- **[WARN] Safeguard 2 and the Q4 trigger cannot detect the risk the waiver adds (false blocks)**
  - **What is wrong:** the enforced Measurement record sets `shadow_*` equal to `live_*` and `turn_marker` to null, so a false block is recorded exactly like a true one, and "blocks followed by an identical retry" cannot tell them apart. The second Q4 condition ("a block … that the retry did not clear") is almost never met, because the Retry escape clears every identical retry by design. The first condition detects only the gate failing open. There is also a 10 MB stop on the log, which silently ends the "indefinite" measurement of Q5. The 7-day report run has no owner and no artefact: the follow-up stub schedules the report for the policy decisions only, not for the rollback check.
  - **Prior artifact ignored:** `VOCABULARY.md:135` (the Shadow record pairs the live and the shadow decision; that pairing is the evidence of a false block); `.claude/concepts/followups/2026-11-09-codegraph-turn-policy-decisions.followup.md` § Suggested next step (it does not name the Q4 check); `JOURNAL.md` 2026-10-15 "A cleanup wired to run before its own trigger event has fired never runs".
  - **Where in this contract:** `## Business Concept` safeguard 2: "It is also the early warning for false blocks."; Q4: "the user sees a block right after a CodeGraph call in the same turn that the retry did not clear"; Q5: "yes, indefinitely".
  - -> Addressed by:
    - Safeguard 2 now says plainly what the log can and cannot show: it cannot tell a false block from a true one.
    - Q4 (user answer) drops the condition that could never fire and adds "the user reports any block they judge wrong". Its 10% fail-open share is a number the report now prints.
    - Q5 (user answer) removes "indefinitely", and the report prints when the 10 MB cap stopped the log.
    - The 7-day check has an owner (the user) and an anchor: `.claude/concepts/followups/2026-11-09-codegraph-cutover-7-day-check.followup.md`, Issue #262 (JOURNAL 2026-10-15).
- **[WARN] The live smoke check (safeguard 3) runs only paths where the two rules already agree**
  - **What is wrong:** the five smoke steps (block, retry, MCP-then-Read, Bash-then-Read, next prompt) are all cases where the marker rule and the transcript rule give the same answer. None of the cases where they differ is run: a subagent's CodeGraph call, a background task notification, a failed CodeGraph call, compaction, or an interactive terminal session. Yet t1 left the interactive-session, terminal `/compact` and foreground-subagent cases open.
  - **Prior artifact ignored:** `t1-live-checks-python-ai-developer.md:50-57` (What was NOT checked); `JOURNAL.md` 2026-11-07 "A failed tool call is a different hook event…" (only a live trial caught that contract's wrong rules).
  - **Where in this contract:** `## Implementation Handoff` block 1, Live smoke: "a source Read with no CodeGraph call is blocked … the notice row exits 0".
  - -> Addressed by: block 1's live smoke now also runs the cases where the two rules disagree, each with its expected new outcome:
    - a subagent that calls CodeGraph, then a main-session Read: allowed;
    - a subagent that does not call CodeGraph, then a Read: allowed under C-7;
    - a failed CodeGraph MCP call, then a Read: allowed;
    - a background task notification mid-turn, then a Read: allowed;
    - automatic compaction mid-turn after a CodeGraph call, then a Read: allowed;
    - one interactive terminal session, run by the main session because a subagent cannot type prompts: blocked, then allowed after CodeGraph, then blocked after the next typed prompt.

    Any deviation from the expected outcome stops block 1 and returns to the user. The terminal `/compact` and foreground-subagent cases are run where the host allows, and are otherwise recorded as not run.
- **[WARN] `retire` changes the install for every add-on with a Disabled add-on hook, not only codegraph**
  - **What is wrong:** `retire` "covers each Disabled add-on hook the project carries". The `angular-tailwind` add-on already declares `angular-tailwind-advisor.py` (former name `architecture-advisor.py`) under `disabled`. A re-run of that add-on's install would therefore delete the file and rewrite the settings row where it used to refuse. The contract does not name that add-on, its install skill, or a test for it, in Non-Goals, Failure Modes or Files to touch.
  - **Prior artifact ignored:** `MECHANISMS.md:89-93` (Disabled add-on hook, enforced by the install refusal `disabled-hook-present`; contract `2026-10-28-angular-tailwind-rule-documents`); `.claude/addons/angular-tailwind/addon.json:25-37`.
  - **Where in this contract:** `## Data Shapes` → Commands, Upgrade row: "A new `retire` op … covers each Disabled add-on hook the project carries."
  - -> Addressed by: C-8 "Every add-on" states that `retire` applies to every add-on with a `disabled` list, and says what changes for `angular-tailwind`: its advisor's row is removed in step A and an unedited copy is deleted in step B, where the install used to refuse. Its install skill and `DISABLED.md` are in block 1's Files to touch, with test rows, and there is a Failure Mode for it.
- **[WARN] `retire` has no outcome for a project that has the retired rows but not the files**
  - **What is wrong:** retire applies only when "(a) the file … is a plain file whose folded hash is in that entry's `released_sha256`". A project whose tracker or reset file was deleted by hand, but whose rows remain (a Dangling hook row), matches neither retire nor the edited-copy refusal. The contract does not say whether the install removes those rows, refuses, or leaves them. Leaving them breaks brief criterion 7 ("removes the retired rows"). The converse case (files but no rows) does have a Failure Mode.
  - **Prior artifact ignored:** `VOCABULARY.md:95` (Dangling hook row); `JOURNAL.md` 2026-11-02 "A revision that adds a path adds its failure modes".
  - **Where in this contract:** `## Failure Modes & Mitigations`: "A hand-installed project has the retired files but no rows."; no entry for the opposite case.
  - -> Addressed by: C-8 step A removes the retired rows whether or not the file exists, so Dangling hook rows are healed (brief criterion 7). There is a Failure Mode for it and a block 1 test row.
- **[WARN] "A user-layer row is still refused" describes code that does not refuse it**
  - **What is wrong:** `_disabled_hook_refusal` checks only rows whose layer is `project` or `local` (`row["layer"] in ("project", "local")`). A user-layer row naming a disabled hook is not refused there today, so "still" claims something the cited code does not do. The VERIFIED line for those line numbers covers only the project and local layers.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "Check a documented guard behaviour against the guard's code"; `.claude/scripts/auto_improve_finish_install.py:2274-2275`.
  - **Where in this contract:** `## Data Shapes` → Commands: "An edited copy, a row in `settings.local.json` or a user-layer row is still refused as `disabled-hook-present`".
  - -> Addressed by: the claim is corrected to match the code. The check reads the project and local layers only, today and after (C-8, the Upgrade row, and the VERIFIED line citing `:2274-2275`). A user-layer row is a stated Non-Goal, because no install writes one. I chose not to extend the check to the user layer: the install cannot write that layer, so it could only refuse there. A refusal with no install-side fix adds friction without protecting anything the add-on wrote.
- **[WARN] Registry amendments are incomplete, and block 2 audits only the ones listed**
  - **What is wrong:** Business Concept amends six terms, but several more registry entries become false at the cut-over and are not listed:
    - Command-line route (`VOCABULARY.md:137`: "reaches the tracker as a `PostToolUse` event … The tracker counts it").
    - Counted command (`:138`: an exit-0 rule; a failed attempt now counts).
    - Foreign marker (`:130`: the code is removed by an Extension Point, but the term is not retired).
    - Live plan (`:133`: "`main()` applies them after the shadow").
    - Retry escape (`:126`: "cleared by the next prompt"; no hook clears tickets any more).
    - The CodeGraph amendments (`MECHANISMS.md:107`, `:111`: three hooks; the tracker owns the CLI route; the reset hook prunes and prints the notice).
    - The six-copy parity count (`MECHANISMS.md:45`, `:109`).
    - Disabled add-on hook's "Enforced by" line (`MECHANISMS.md:91`).

    Block 2 check (12) audits only "registry amendments listed in the contract's Business Concept".
  - **Prior artifact ignored:** the entries cited above; `JOURNAL.md` 2026-10-28 "A new term's definition must be true against every existing member".
  - **Where in this contract:** `## Business Concept` → "Terms amended at review (Universal)"; block 2 CONSTRAINTS (12).
  - -> Addressed by: Business Concept's "Registry amendments at review" now lists every entry the critic named, each with its line: Command-line route, Counted command, Foreign marker, Live plan, Retry escape, the two CodeGraph MECHANISMS amendments, the parity counts, and Disabled add-on hook's "Enforced by" line. Block 2's check (12) audits the whole list.
- **[NIT] The Transcript cursor, Read limits, entry classifier and Shadow decision log are cited by issue number only.** None of them has a MECHANISMS.md entry, so "Reused Mechanisms" cites mechanisms that the registry does not hold.
  - -> Addressed by: Reused Mechanisms now cites them by the parent contract's path, and says they are not registry entries. The Shadow decision log's promotion is still pending.
- **[NIT] Ticket scope and turn scope differ.** A background task notification fires a new `prompt_id` (t1 point b) but no longer ends the Investigation Turn. A ticket keyed by `prompt_key` therefore expires in the middle of a turn. This costs the same as the old reset hook, which deleted tickets at every prompt, but the two amended definitions now disagree about scope.
  - -> Addressed by: the Retry escape amendment now says explicitly that a ticket's scope is the prompt, which can be shorter than the turn, and that it expires at a task notification exactly as today. This is kept deliberately, and the definitions no longer contradict each other.
- **[NIT] Confidence rates the rollback "High", but no block tests a revert release** or the leftover `notice` row on a reverted install. Only the old guard's early exit is VERIFIED (`:1888-1900`).
  - -> Addressed by: the rollback is moved to Medium in Confidence. Block 1 adds a revert-manifest test: a manifest with both hooks back in `hooks` and the cut-over guard's hash released updates the guard, restores both files and rows, and the leftover `notice` row exits 0. Confidence may rise only once that test passes.
- **[NIT] Adjacent Areas carries the exception line plus "The scan was not run here (no shell)".** The orchestrator's `derive_area` result (`uncategorized`, a fallback) makes the exception honest, but the text admits the scan itself was not run.
  - -> Addressed by: the section now cites the `derive_area` result and hands the scan to the main session before approval, with a rule to revise the section if the scan prints an area. I kept the statement that the architect did not run it, because it is true and removing it would overclaim.

### Applicable journal entries

- **2026-10-04 — Check a documented guard behaviour against the guard's code** — violated, see the WARN on the user-layer refusal; heeded for the leftover `notice` row (VERIFIED `:1888-1900`).
- **2026-10-05 — Do not add shared state to stop a duplicate the install tool already refuses** — heeded by the Failure Mode on two notices (it relies on the install, not on a marker).
- **2026-10-15 — A cleanup wired to run before its own trigger event has fired never runs** — not addressed: the 7-day rollback check in Q4 has no anchored step, see the WARN above.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by block 1 (block rows gain a CLOSED transcript).
- **2026-10-22 — Describe a broken install by the rows each install age really has** — violated, see BLOCKER 2.
- **2026-10-28 — State the real trigger of a hook, not the printing condition** — heeded by `## Extension Points` → `DISABLED.md` (the notice row keeps one start per prompt).
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded by `## New Mechanisms` (none).
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — heeded: `retire` refusals name the uninstall route.
- **2026-11-02 — Name the tests a fix may change by the state they guard** — heeded by block 1 CONSTRAINTS.
- **2026-11-02 — A revision that adds a path adds its failure modes** — partly heeded; the rows-without-files path is missing (WARN).
- **2026-11-02 — A rule titled 'every' must list every line it covers** — heeded by C-2.
- **2026-11-05 — An "older release" test fixture must be pinned** — heeded by `RESET_BASELINE_REF` and the frozen disabled files.
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome** — violated, see BLOCKER 2 (the `warn` exit-1 prediction).
- **2026-11-07 — A contract that reorders a hook's decision steps must be re-read against every contract that reorders the same steps** — heeded (no other open contract edits the guard).
- **2026-11-07 — A failed tool call is a different hook event, and a row's `if` matches each sub-command** — heeded by Q1 / Alternative F and the strict Counted test.

### What the critic did not check

- `.claude/registries/INTEGRATION.md` does not exist in this tree, and the registries have no per-domain project-tier files; only the Universal tiers were read.
- `pr_merged.py --contract <slug> --status --json` (item 14) was not run because no shell was available. By reading the contract: two mergeable blocks, a `**Work Item Brief:**` header present, and no version file in any Files to touch.
- `derive_area.py` / `cross_area_scan.py` were not run; the orchestrator's `uncategorized` result was taken as given.
- Whether released 0.16.x codegraph installs carry plain exec-form or launcher rows was not established from release commits (it bears on BLOCKER 2's exposure).

## Lessons referenced

- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures**: heeded by Failure Modes and block 1. The block rows get a closed transcript instead of weaker assertions.
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them**: heeded. Block 1 names each changed row group by its state, and the unchangeable groups by theirs.
- **2026-10-22 — Describe a broken install by the rows each install age really has**: heeded by C-8, which names both row forms and their missing-file exits, and by the age table block 1 writes.
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome**: heeded by C-8 and Failure Modes (exit 2 for a plain row, exit 1 for a launcher `warn` row).
- **2026-10-15 — A cleanup wired to run before its own trigger event has fired never runs**: heeded. The 7-day check has an owner and its own stub.
- **2026-10-04 — Check a documented guard behaviour against the guard's code**: heeded. The layer claim of the refusal now matches `:2274-2275`.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam**: heeded. `retire` extends Preview-hash apply and the Disabled add-on hook, so New Mechanisms is none.
- **2026-11-02 — A revision that adds a path adds its failure modes**: heeded. The prompt row, `retire`, tickets and C-4 each have a failure mode.
- **2026-11-07 — A failed tool call is a different hook event, and a row's `if` matches each sub-command**: heeded. Counting attempts is a stated decision (Q1, Alternative F), and the strict Counted test is kept, not the row's `if`.
- **2026-11-07 — A contract that reorders a hook's decision steps must be re-read against every contract that reorders the same steps**: heeded. No other draft or approved contract edits the guard (2026-11-09).
- **2026-11-05 — An "older release" test fixture must be pinned to a fixed commit or a frozen copy**: heeded. The bench keeps `RESET_BASELINE_REF`, and the disabled files stay frozen.
- **2026-11-02 — A rule titled 'every' must list every line it covers**: heeded by C-2's ordered effect list and the closed reason set.
- Orthogonal to north-stars: none active (`.claude/north-stars/` does not exist).

---

## Implementation Handoff

There are two mergeable blocks on the parent branch `feature/262-codegraph-hooks-cutover`. Every sub-task branch is cut from it and targets it, and one landing raises the version. No block lists a version file.

### 1. Cut-over (`python-ai-developer`)

**Depends on:** none

**Preconditions:** Claude Code CLI with a CodeGraph MCP server, in a trusted throwaway folder outside every repository

**Files to touch:**
- `.claude/addons/codegraph/addon.json`
- `.claude/addons/codegraph/DISABLED.md`
- `.claude/addons/codegraph/hooks/codegraph-first-guard.py`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/codegraph_shadow_report.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/tests/test_codegraph_shadow_report.py`
- `.claude/hooks/tests/_addon_fixture.py`
- `.claude/hooks/tests/test_codegraph_first_guard.py`
- `.claude/hooks/tests/test_worktree_path_guards.py`
- `.claude/hooks/tests/test_addons.py`
- `.claude/hooks/tests/test_codegraph_shadow.py`
- `.claude/hooks/tests/bench_codegraph_guard.py`
- `skills/auto-improve-codegraph-install/SKILL.md`
- `skills/auto-improve-codegraph-uninstall/SKILL.md`
- `skills/auto-improve-angular-tailwind-install/SKILL.md`
- `.claude/addons/angular-tailwind/DISABLED.md`
- `.claude/references/codegraph-decision-table.md`
- `README.md`

**Pre-written TASK block:**
```
TASK: Cut the codegraph add-on over: the guard decides from the Transcript turn state (C-1..C-6), the tracker and
reset hooks become Disabled add-on hooks, pruning and the Connection notice move to the guard's prompt row, the
install retires the two hooks in place, the report reads enforced records.
CONTEXT: contract .claude/concepts/2026-11-09-codegraph-hooks-cutover.md (Data Shapes, Commands, Failure Modes);
  parent contract 2026-11-05-codegraph-hooks-redesign; the t1 and t3 artefacts under
  .claude/reviews/2026-11-05-codegraph-hooks-redesign/.
FILES: see Files to touch. codegraph-turn-tracker.py and codegraph-turn-reset.py are NOT edited (frozen).
CONSTRAINTS:
  - /tdd-first: write the new rows RED first.
  - Guard rows: open via mcp, via a Bash Counted command (strict form; a compound command, a background run and
    a non-counted subcommand stay closed) and via an Agent or Task dispatch in the current turn (C-7, route agent,
    no cli-fallback record); a dispatch before the last human prompt does not open; closed after a new human prompt; a task notification does not close;
    each unknown cause incl. error allows fail-open:transcript-<cause> with one stderr line and one record per
    session; an allowlisted target with an unknown state prints nothing; unusable folder: no transcript read,
    session-state-unusable as today; ticket from another prompt or with no key is absent; cli-fallback once per
    session only when mcp_seen is false; every late apply effect forced to raise leaves exit code and stderr
    unchanged; the enforced Measurement record shape; perf_counter timing.
  - Prompt row: prunes once per session, notice outcomes as #295, exit 0 when anything raises (SystemExit
    included), no __pycache__, no ticket deleted.
  - Changed test groups, by the state they guard: rows that open the gate by writing turn.json (tracker stamp,
    foreign marker) become transcript-open rows; rows that expect a block gain a CLOSED transcript (never weaker
    assertions); pruner and notice rows load from the guard; AC8 (three hook files) becomes one hook plus two
    disabled; the inline-copy parity set drops the two disabled files; test_addons' end-to-end flow uses a
    transcript. Unchanged outcomes: classification (#612) rows, proof-step rows, session-state-unusable,
    retry-ticket-unwritten, fallback-mode banner, getattr parity, load_hook rows, and the shadow tests of the read
    limits, cursor and long-line skip (kept, now on the live read).
  - Manifest: move the tracker's and reset's released hashes into their disabled entries, folded from every
    released copy (read each release commit); registration may be a list (validator + test); add the cut-over
    guard's folded hash to released_sha256, labelled with the version the landing will raise to
    (check_version_bump.py --exact), and recompute it after the last edit to the guard.
  - Installer retire op in TWO STEPS per C-8, for every add-on with a disabled list. Tests:
    - a 0.16.x install (released tracker and reset, four rows) runs step A: one hook, two rows, and both retired
      files still on disk; the next run is step B: the files are deleted;
    - no run deletes a file whose row it removes;
    - rows but no files: step A removes the rows;
    - files but no rows: step B deletes the released copies and keeps an edited one under kept;
    - an edited retired copy present at step A is refused;
    - a settings.local.json row is refused;
    - a user-layer row is ignored, as today;
    - preview then a changed file gives changed-since-preview;
    - a re-run after step B changes nothing;
    - uninstall after the upgrade works;
    - the same step-A and step-B rows for angular-tailwind (advisor under its current and its former name);
    - a revert-manifest fixture: both hooks back in hooks and the cut-over guard's hash released; the install
      updates the guard and restores both files and rows, and the leftover notice row exits 0.

    Read the release commits to find which release first wrote launcher rows. Write the upgrade-age table into
    the codegraph install skill. Add the new-session question before a step-B deletion if Q7 is answered yes.
  - Report: the enforced outcome and section, the fail-open share, and the cap line from a log-full line; shadow
    sections ignore enforced records; fixture tests.
  - Live smoke. Record the commands, outputs and Claude Code version in the pull request body.
    Setup: install this branch's add-on into a throwaway project at the 0.16.5 state; re-run the install
    (step A shown, then applied); start a new session; re-run (step B).
    Agreeing cases, with claude -p:
    - a source Read with no CodeGraph call is blocked, and its identical retry is allowed;
    - a codegraph_explore MCP call, then a Read: allowed;
    - a Bash "codegraph explore X", then a Read: allowed;
    - the next prompt's Read is blocked again;
    - the notice row exits 0.
    Cases where the old and new rules DISAGREE, each with its expected new outcome:
    - a subagent calls CodeGraph, then a main Read: allowed;
    - a subagent without CodeGraph, then a Read: allowed;
    - a failed CodeGraph MCP call, then a Read: allowed;
    - a background task notification mid-turn, then a Read: allowed;
    - automatic compaction mid-turn after a CodeGraph call, then a Read: allowed;
    - an interactive terminal session (ask the main session to run it): blocked, then allowed after CodeGraph,
      then blocked after the next typed prompt.
    Any outcome other than the expected one: stop and return to the user. A case the host cannot run is recorded
    as not run, with the reason.
  - Run test_codegraph_first_guard.py, test_worktree_path_guards.py, test_addons.py, test_codegraph_shadow.py,
    test_auto_improve_finish_install.py, test_plugin_manifests.py, test_plugin_doctor.py (unedited),
    test_plugin_text_scans.py, test_codegraph_shadow_report.py; report each exit code as read from the run.
  - No environment variable, no kill switch, nothing printed on an allowed call except a fail-open or retry line.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-09-codegraph-hooks-cutover.md
  contract_status: approved
```

### 2. Fail-open review (`fullstack-code-reviewer`)

**Depends on:** 1

**Files to touch:**
- `.claude/reviews/2026-11-09-codegraph-hooks-cutover/t2-fail-open-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review block 1 for fail-open safety, upgrade safety and contract conformance, and write the review artefact.
CONTEXT: concept contract .claude/concepts/2026-11-09-codegraph-hooks-cutover.md; block 1's pull request body (live smoke).
FILES: .claude/reviews/2026-11-09-codegraph-hooks-cutover/t2-fail-open-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check by name, each with its own outcome:
    (1) every unknown transcript cause allows with a logged reason, and nothing in the read can block on a guess;
    (2) C-1 order, incl. the unusable-folder rule (Q3 as answered) and no fail-open line on an allowlisted target;
    (3) C-2: no effect after the ticket can change exit code or stderr;
    (4) the block rows of the three named suites keep their assertions and gained a closed transcript (diff them);
    (5) the Bash route uses the strict Counted test, not the row's if;
    (6) tickets keyed to the prompt; an old ticket reads as absent;
    (7) the prompt row always exits 0, prunes once, keeps the notice outcomes;
    (8) retire runs in two steps (C-8): no run deletes a file whose row it removes; step B deletes only released
        copies and keeps edited ones; settings.local.json rows and edited copies at step A are refused; dangling
        rows are removed; angular-tailwind is covered; the revert-manifest test passes;
    (8a) C-7: a dispatch in the current turn reads open, and the smoke cases where the rules disagree were run
        with the expected outcomes;
    (9) released hashes: the tracker's and reset's cover every released copy, the cut-over guard's matches the
        final file;
    (10) the live smoke was run and recorded; re-run any step you can;
    (11) the report's enforced section and shadow sections are separate;
    (12) every entry in the contract's "Registry amendments at review" list is appended (VOCABULARY, MECHANISMS),
        each one checked against its cited line.
  - Six fixed sections; the commit range base..head; the file does not exist yet, you create it; "## Evidence"
    carries commands with exit codes. End the header with the verdict line alone, exactly one of
    "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked".
  - Also write the Gate Output (<artefact stem>.gate.json) beside it, listing every Review checklist item verbatim.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-09-codegraph-hooks-cutover.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

`pr_merged.py` fills this list when the contract's work is merged and nothing is pending. Do not tick lines by hand.

- [x] Implementation matches Data Shapes exactly — evidence: .claude/reviews/2026-11-09-codegraph-hooks-cutover/t2-fail-open-review-fullstack-code-reviewer.md
- [x] Reused Mechanisms are actually reused (no parallel implementations introduced) — evidence: .claude/reviews/2026-11-09-codegraph-hooks-cutover/t2-fail-open-review-fullstack-code-reviewer.md
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md` — not applicable (.claude/reviews/2026-11-09-codegraph-hooks-cutover/t2-fail-open-review-fullstack-code-reviewer.md)
- [ ] New vocabulary terms promoted to `VOCABULARY.md` — not performed (disclosed on #262)
- [x] Integration surfaces reflected on both backend and frontend sides — evidence: .claude/reviews/2026-11-09-codegraph-hooks-cutover/t2-fail-open-review-fullstack-code-reviewer.md
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced — not applicable (.claude/reviews/2026-11-09-codegraph-hooks-cutover/t2-fail-open-review-fullstack-code-reviewer.md)
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface) — not applicable (.claude/reviews/2026-11-09-codegraph-hooks-cutover/t2-fail-open-review-fullstack-code-reviewer.md)
- [x] `Status` flipped to `implemented`
