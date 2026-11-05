# t1 live checks — python-ai-developer

- **Gate agent:** python-ai-developer
- **Sub-task:** t1-live-checks (issue #263, parent issue #261)
- **Contract:** `.claude/concepts/2026-11-05-codegraph-hooks-redesign.md` (approved)
- **Reviewed on:** 2026-11-05
- **Commit range reviewed:** `233cb64..` working tree (no commit of this work existed when the artefact was written; the main session commits the files named under Evidence, so the range closes at that commit)
- **Environment:** Claude Code 2.1.318; CodeGraph 1.6.2 (`codegraph serve --mcp`, one throwaway project index); Windows 11 (10.0.26300); Python 3.12.10; model `claude-haiku-5-5` (`--model haiku`); every session non-interactive (`claude -p --output-format json`, `--setting-sources project`, `--strict-mcp-config`)
- **Who ran what:** every scenario below was run by this sub-agent in a throwaway folder under the system temp directory, outside every repository. The main session ran none and nothing was asked of the user. The probe was registered only in that folder's `.claude/settings.json`.

**Verdict:** pass

## What was checked

| Point | Outcome |
|---|---|
| (a) where a subagent's transcript is | **VERIFIED** (scenario 4). A subagent's `PreToolUse` and `PostToolUse` payloads carry `agent_id`, `agent_type`, and a `transcript_path` identical to the parent's. The subagent's own entries are in a separate file, `<transcript dir>/<session_id>/subagents/agent-<agent_id>.jsonl` (plus a `.meta.json`), every line with `isSidechain: true` and `agentId`. The parent file holds only the `Agent` tool use and its result; the subagent's CodeGraph tool use is not in it. So S-4 (no transcript read when `agent_id` is present) is right: reading the parent file for a subagent call would see a closed turn. |
| (b) injected system text versus human prompts | **VERIFIED** (scenarios 3, 4, 5). Hook `additionalContext`, project `CLAUDE.md`, date, skill listing and the other host reminders are `type: "attachment"` entries (`attachment.type` of `hook_additional_context`, `instructions`, `session_context`, `date`, ...), never `user` entries. Three `user`-typed lookalikes exist and the rule below excludes all of them: (1) tool results: `message.content` a list with a `tool_result` block, `toolUseResult` and `sourceToolAssistantUUID` keys, and the same `promptId` as the prompt; (2) a background task notification (scenario 4): an `isMeta: true` `<system-reminder>` entry plus a prompt entry with `promptSource: "system"`, `turnOrigin: "task_notification"` and an `origin` object; it also fires `UserPromptSubmit` with a new `prompt_id` whose `prompt` is the notification; (3) the compaction summary: `isCompactSummary: true`, with `promptId`, `turnOrigin`, `turnPosition` but no `promptSource`. Human prompts carry `promptSource`, `turnOrigin`, `turnPosition`, `permissionMode` and a `promptId` equal to the `prompt_id` of the `UserPromptSubmit` and of the later tool hooks. |
| (c) compaction rewrites or appends | **VERIFIED for append** (scenario 3). Manual `/compact` between turns: same inode, 264,808 to 309,698 bytes, sha-256 of the old bytes unchanged (a strict prefix); appended: a `system` entry with `subtype: "compact_boundary"` (`compactMetadata.trigger`, `logicalParentUuid`), a `user` entry with `isCompactSummary: true`, an `isMeta` caveat, the `<command-name>` entry. Automatic compaction in the middle of a turn (`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=1`): `compact_boundary` (line 49) and summary (line 53) come after the turn's tool results, and the turn's earlier `codegraph-use` (line 28) stays in the file, so it still counts after the boundary. A rewrite was not seen; covered by fail-open (see What was NOT checked). |
| (d) parallel calls: entry flushed before the sibling's `PreToolUse` | **VERIFIED for the CodeGraph-first order** (scenarios 2 and 5, three runs). A CodeGraph call plus a `Read` in one message give two `assistant` entries with the same `message.id` (`apiBlockIndex` 0 and 1), one block each. The host ran them one after the other: the `Read`'s `PreToolUse` came after the CodeGraph `PostToolUse`, and the CodeGraph `tool_use` entry was readable at that `PreToolUse` in 3 of 3 runs. A call's own `tool_use` entry is not reliably flushed at its own `PreToolUse` (absent for the first call in all three parallel runs, present in the sequential runs); this is harmless because CodeGraph calls are never guarded. The `Read`-first order was not run: unverified - covered by fail-open because the shadow then reads `closed`, exactly as the `PostToolUse` tracker would. |
| (e) format stability | **unverified - covered by fail-open because** only 2.1.318 is installed, so no second version could be compared. On this version every line of all seven captured session files parsed as JSON and the keys the rule reads (`type`, `isSidechain`, `isMeta`, `isCompactSummary`, `origin`, `toolUseResult`, `sourceToolAssistantUUID`, `promptSource`, `message.role`, `message.content[].type`, `message.content[].name`) had the types the rule expects. A change in any of them makes a line `other` or a parse error, which the contract maps to `unknown:*`, which allows. Sizes for the Read limits: a one-prompt session is about 265 KB and the largest single line about 84 KB (an `attachment`), far below the 2 MB line limit. |
| (f) a PreToolUse hook killed at its timeout (does not decide the verdict) | **VERIFIED** (scenario 6). The probe's `PreToolUse` row had `"timeout": 1`; the probe wrote its capture, slept 3 s and would then exit 2. The `Read` **went through**: `PostToolUse` fired, the model answered `done`, there was no permission denial, and the probe's post-sleep marker file was never written (killed at about 1 s, before its exit 2). Control: the same probe with `"timeout": 10` reached exit 2 and the call was refused. So in 2.1.318 a hook killed at its timeout does not block the call. |
| Readable before the next sequential `PreToolUse` | **VERIFIED**. A `codegraph-use` entry was in the transcript at every one of the 6 observed `PreToolUse` calls that follow a completed CodeGraph call (scenario 1 once, scenario 2 twice, scenario 3 automatic twice, scenario 5 once). |

**The exact rule block 2 implements.** A transcript line is parsed as JSON and classified in this order; anything that does not match is `other`:

- **`human-prompt`** (the only boundary): `type == "user"`; `isSidechain`, `isMeta` and `isCompactSummary` are not true; the keys `origin`, `toolUseResult` and `sourceToolAssistantUUID` are absent; `message.role == "user"`; `promptSource` is a string other than `"system"`; and `message.content` is a string or a list holding no block of `type == "tool_result"`.
- **`codegraph-use`**: `type == "assistant"`; `isSidechain` is not true; and `message.content` is a list holding a block with `type == "tool_use"` and a `name` starting `mcp__codegraph__`.
- **`other`**: everything else (attachments, tool results, `isMeta` reminders, task notifications, the compaction boundary and summary, `<command-name>` entries, sidechain lines, unknown types, unparseable lines).

Transcript turn state: after the last `human-prompt` in the window, `open` if a `codegraph-use` follows it, else `closed`. Run over the five committed fixtures the rule gives: sequential-turns `[3 human-prompt, 27 codegraph-use, 43 human-prompt]`; parallel-calls `[3, 27]`; compaction `[3, 28]`; injected-messages `[3, 28]`; subagent `[3]`.

**Scenarios and who ran them.**

| # | Scenario | Run by | How | Fixture |
|---|---|---|---|---|
| 1 | two sequential turns, a CodeGraph call in the first | python-ai-developer | `claude -p --session-id`, then `claude -p --resume` for the second prompt | `sequential-turns.jsonl` |
| 2 | a CodeGraph call and a `Read` in one assistant message | python-ai-developer | one prompt asking for both in one message; run twice | `parallel-calls.jsonl` |
| 3 | compaction | python-ai-developer | manual `/compact` through `--resume` (`MSYS_NO_PATHCONV=1`); automatic mid-turn with `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=1` | `compaction.jsonl` (the automatic run) |
| 4 | a subagent that calls CodeGraph | python-ai-developer | the `Agent` tool, `general-purpose`; the host ran it in the background | `subagent.jsonl` |
| 5 | a turn carrying injected text | python-ai-developer | probe in `inject` mode printing `hookSpecificOutput.additionalContext`, plus a project `CLAUDE.md` | `injected-messages.jsonl` |
| 6 | point (f) | python-ai-developer | probe in `timeout` mode, row `timeout` 1, then 10 as a control | none (payload only) |

A first attempt asked for `codegraph_search`, which this CodeGraph version does not offer to the model (it offers `codegraph_explore`); that run is not used.

## Findings

None.

## What was NOT checked

- A terminal (interactive) session. Every human prompt seen has `promptSource: "sdk"` and `turnOrigin: "sdk"` because it came through `-p`; the value for a terminal prompt is unverified. The rule tests for "a string other than `system`", not for `sdk`. If a terminal prompt lacked `promptSource`, the shadow would miss that boundary and report `shadow-more-open`, which allows more (the fail-open direction); the cut-over criterion would expose it.
- Whether a terminal `/compact` fires `UserPromptSubmit` (under `-p` it did not).
- A rewrite-style compaction, a resume that rebuilds the file, or a prefix hash for the automatic compaction run (one run, no before-hash). Covered by fail-open: the cursor's path-and-identity and shorter-than-`scanned_to` checks give a cold scan or `rewritten`, which allows.
- A parallel message with the `Read` before the CodeGraph call (point d, covered by fail-open).
- Any Claude Code version other than 2.1.318, any CodeGraph version other than 1.6.2 (point e).
- Subagents run in the foreground (the host chose a background run); a subagent's `PreToolUse` payload keys were read, not its timing.

## Evidence

- **Payload keys (2.1.318):** `UserPromptSubmit`: `session_id`, `transcript_path`, `cwd`, `prompt_id`, `permission_mode`, `hook_event_name`, `prompt`. `PreToolUse`: the same minus `prompt`, plus `effort`, `tool_name`, `tool_input`, `tool_use_id` (and `mcp_server` for MCP tools). `PostToolUse`: those plus `tool_response`, `duration_ms`. A subagent's tool events add `agent_id` and `agent_type`. `transcript_path` is `~/.claude/projects/<working folder with separators replaced by "-">/<session_id>.jsonl`.
- **Event and write order (scenario 1):** at the second prompt's `UserPromptSubmit` the new prompt's `user` entry was not yet in the transcript; at that turn's `PreToolUse` it was, as the latest `user` entry (line 43), with `promptId` equal to the payload `prompt_id`. At the `Read`'s `PreToolUse` the first turn's `codegraph-use` (line 27) was readable.
- **Classifier check:** the rule was run over the raw captures and over the five committed fixtures, with the same result (listed above), so sanitising lost nothing the rule reads.
- **Point (f) commands:** `claude -p ... --session-id 8888...` with the row at `"timeout": 1` gave `done`, `permission_denials: []`, captures `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, no `.survived-sleep` file; the same with `"timeout": 10` gave `refused` and `.survived-sleep` files for every `PreToolUse`.
- **Files written (the only ones):** `.claude/reviews/2026-11-05-codegraph-hooks-redesign/t1-live-checks-python-ai-developer.md`, its `.gate.json`, and under `.claude/hooks/tests/fixtures/codegraph-transcripts/`: `README.md`, `capture_probe.py`, `sequential-turns.jsonl` (36 KB), `parallel-calls.jsonl` (29 KB), `compaction.jsonl` (59 KB), `subagent.jsonl` (52 KB: the parent file then the subagent's file), `injected-messages.jsonl` (30 KB). Text values are `"x"`; the two departures (structural markers kept, identifiers pseudonymised `id-<n>`) are listed in the README. A search of the fixtures for the user name, the temp path, file names, prompt words and uuids found only the model name as a dictionary key.
- **Containment:** the probe was registered only in the throwaway folder's `.claude/settings.json`, never in this repository or `~/.claude`.

## Disposition

Nothing. This gate releases its dependents. Verdict rule: points (a) to (e) are answered ((a) to (d) verified, (e) unverified and covered by fail-open) and a `codegraph-use` entry was readable before the next sequential `PreToolUse`; point (f) is recorded and does not decide the verdict.

Facts block 2 should carry into its code and tests: a background task notification fires `UserPromptSubmit` (so today's reset hook resets the marker mid-turn) but is not a boundary under the rule, so the shadow may report `shadow-more-open` for those calls, which is expected; a hook killed at its timeout lets the call through, so the 50 ms Shadow time budget is a bound on cost, not on correctness; a call's own `tool_use` entry may not yet be flushed at its own `PreToolUse`.
