# CodeGraph transcript fixtures (issue #261, block 1)

Sanitised copies of real Claude Code session transcripts, captured to fix the transcript entry rule that block 2 of
`.claude/concepts/2026-11-05-codegraph-hooks-redesign.md` implements. The findings are in
`.claude/reviews/2026-11-05-codegraph-hooks-redesign/t1-live-checks-python-ai-developer.md`.

- **Claude Code:** 2.1.318 (the only version these were captured on). **CodeGraph:** 1.6.2 (MCP server `codegraph serve --mcp`).
- **Captured:** 2026-11-05, Windows 11, non-interactive `claude -p` sessions with `--model haiku`, in a throwaway folder
  outside every repository. Every session was run by the `python-ai-developer` sub-agent; none by the main session.
- **Not covered:** an interactive (terminal UI) session. All human prompts here carry `promptSource: "sdk"` and
  `turnOrigin: "sdk"` because they came through `-p`.

## Files

| File | Scenario | Lines of interest (0-based) |
|---|---|---|
| `sequential-turns.jsonl` | two human prompts in one session (`--resume`); a CodeGraph call in the first, a `Read` in the second | prompt 3, `codegraph-use` 27, prompt 43 |
| `parallel-calls.jsonl` | one assistant message with a CodeGraph call and a `Read` (two assistant entries, one message id) | prompt 3, `codegraph-use` 27, `Read` tool use 28 |
| `compaction.jsonl` | automatic compaction in the middle of a turn (`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=1`) | prompt 3, `codegraph-use` 28, `compact_boundary` 49, summary 53 |
| `subagent.jsonl` | the **parent** session (lines 0-49: a background `Agent` call, then the injected `task-notification` entries at 41-42) followed by the **subagent's own** file (lines 50-74, all `isSidechain: true`). In the host the two are separate files | parent prompt 3; task-notification 41-42 |
| `injected-messages.jsonl` | a turn with hook `additionalContext` (`UserPromptSubmit`), a project `CLAUDE.md` and the host's own reminders, then a CodeGraph call and a `Read` | prompt 3, `hook_additional_context` attachment 12, `codegraph-use` 28 |
| `capture_probe.py` | the throwaway probe that took the payloads. Not a hook of this repository; register it only in a throwaway folder | |

## Sanitising

Every JSON line is kept, in order. Every string value is replaced by `"x"` **except**:

- structural markers, kept verbatim: the values of the keys `type`, `role`, `subtype`, `userType`, `promptSource`,
  `turnOrigin`, `permissionMode`, `stop_reason`, `kind`, `operation`, `level`, `trigger`, and `name` (tool names, such as
  `mcp__codegraph__codegraph_explore`, `Read`, `Agent`), `attributionMcpServer`, `attributionMcpTool`;
- identifiers (keys ending in `Uuid`, `UUID`, `Id`, `ID`, or named `id`, `requestRef`, `toolUseID`, `runId`): replaced by a
  stable pseudonym `id-<n>` (the same input gives the same pseudonym across one file) so that links such as `promptId`
  and `tool_use` ids can still be compared. This is the one departure from "replace every text value with x".

Every key, number, boolean, null and array shape is kept. No path, prompt text, tool output, branch name or user name
survives; the model name survives only as a dictionary key (`haiku`).

## The rule these fixtures pin (also in the artefact)

- `human-prompt`: `type == "user"`, `isSidechain`, `isMeta` and `isCompactSummary` not true, no `origin`, `toolUseResult`
  or `sourceToolAssistantUUID` key, `message.role == "user"`, `promptSource` a string other than `"system"`, and
  `message.content` a string or a list with no `tool_result` block.
- `codegraph-use`: `type == "assistant"`, `isSidechain` not true, and a `message.content` block with
  `type == "tool_use"` and a `name` starting `mcp__codegraph__`.
- everything else is `other`.

Classifying these files gives: sequential-turns `[3 human-prompt, 27 codegraph-use, 43 human-prompt]`; parallel-calls
`[3, 27]`; compaction `[3, 28]`; injected-messages `[3, 28]`; subagent `[3]` (the task-notification, the `isMeta`
reminder and every `isSidechain` line are `other`).
