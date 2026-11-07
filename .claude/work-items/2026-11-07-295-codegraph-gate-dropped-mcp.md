---
id: 295
issue_offer: opened
title: CodeGraph gate survives a dropped MCP connection: command-line route, per-turn health notice
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/295
labels: [enhancement]
milestone: none
project: claude-agentic-auto-improve
branch: feature/295-codegraph-gate-dropped-mcp
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261107-improvement-295-codegraph-gate-dropped-mcp
north_stars: none
contract: .claude/concepts/2026-11-07-295-codegraph-gate-dropped-mcp.md
pr: none
issue_link: unknown
status: verifying
created: 2026-11-07
---

# CodeGraph gate survives a dropped MCP connection: command-line route, per-turn health notice

Raw argument: `https://github.com/lneninger/claude-agentic-auto-improve/issues/295`

## Problem statement
The CodeGraph-first gate counts only calls made through the CodeGraph MCP connection (`mcp__codegraph__*`). When Claude Code drops that connection mid-session and never rebuilds it, nothing in the session can satisfy the gate, and nothing tells the user the connection is gone. Evidence (2026-11-06, project StockToolScalpingMachine, contract `2026-11-02-dashboard-v3`): after `/clear` the codegraph server was marked stale and never reconnected; the `codegraph` program itself was healthy, and its command line (about 0.5 s per call) mirrors the MCP tools. A test-author subagent could not Read or Edit existing test files, so a delivery step stopped half done.

The existing fail-open (#259) covers subagents, no index, another tree's index, and server not configured or disabled. It does not cover: server configured, index present, connection dropped. This item is the "tolerate it" path. Reconnecting is Claude Code's job and out of scope.

## Acceptance criteria
- [ ] A Bash `codegraph explore <term>` that exits 0 opens the gate for the turn; a failing one, `codegraph status`, `init`, `index` and `sync` do not. The Bash tool's exit code decides, not the output text. (Counted commands: `query`, `explore`, `context`, `node`, `callers`, `callees`, `impact`, `files`.)
- [ ] With the MCP connection absent and the index present, a source read is allowed after one command-line query, in the main session and in a subagent, with no bypass variable set.
- [ ] The guard's block message names both routes (an `mcp__codegraph__*` tool if present, otherwise the command-line equivalent) with a copyable command, and states that a worktree reads the main checkout's index unless one was built there.
- [ ] The per-turn notice (in `codegraph-turn-reset.py`) appears when no `codegraph serve --mcp` process exists for this session and is absent when one does; silent on a healthy session; never blocks; stays inside the existing hook's time budget; a test proves it cannot raise an exception into the turn.
- [ ] When the command-line route satisfies the gate and no MCP call has succeeded this session, one `cli-fallback (mcp-unavailable)` record is written per session to the audit log.
- [ ] A project whose vendored CodeGraph hook is older than the plugin's gets a clear finding from the installer check and from `/verify-before-done`, naming the file and both versions.
- [ ] No environment variable or setting turns the gate off (the "no kill switch" rule from #259 stays).
- [ ] The turn-marker rule keeps a single owner: the existing tracker and guard are extended, no second mechanism is added.

## Out of scope
- Reconnecting the MCP server (Claude Code owns it).
- A worktree-local index (covered by the #259 addendum).
- The upstream bug report to the Claude Code team.
- Reopening #259 or #261.

## Known context
- Related: #259 (fail-open when tools unavailable, closed), #261 (hooks redesign, closed), #262 (follow-ups from #261).
- Affected areas (best guess, to be confirmed by the contract): the plugin's `codegraph-first-guard.py`, `codegraph-turn-tracker.py`, `codegraph-turn-reset.py`, the codegraph install skill and its stale-copy check, `/verify-before-done`.

## North-star alignment
- none — the register holds no active thought (`.claude/north-stars/` does not exist).

## Open questions from intake
- The issue's three open questions are deferred to the design contract by the issue itself, as findings to research rather than missing requirements: (1) does a hook fire after `/clear`, and with which source value; (2) how the notice tells this session's server from other sessions' servers; (3) whether CodeGraph's `daemon` command changes the picture. → **Answer:** to be resolved in `/design-first`.

## Size
M — several coordinated hook changes plus an installer and verification check; the issue itself names a design contract first.

## Routing
non-trivial → /design-first (the issue states: contract first, then /tdd-first; trading-safety review not needed). This is hook work, not a safety-critical root.
