# CodeGraph decision table — full version with worked examples

The condensed table lives in [CLAUDE.md](../../CLAUDE.md) → "CodeGraph (PRIMARY investigation
tool)". This is the long form: the same routing plus worked examples, the gate mechanics, and the
failure modes that have actually bitten this project.

> **Provenance.** Reconstructed on 2026-08-25. `CLAUDE.md` cited this path for the worked-example
> version while the file was missing from disk.

---

## The rule

**Every codebase question starts with a CodeGraph call.** `Read` / `Grep` / `Glob` on source paths
are blocked at the hook layer until at least one `mcp__codegraph__*` tool has been called in the
current turn.

## Routing

| Question | Tool | Where to call |
|---|---|---|
| "Where is `X` defined?" | `codegraph_search` → `codegraph_node` | Main session |
| "Who calls `X`?" | `codegraph_callers` | Main session |
| "What does `X` call?" | `codegraph_callees` | Main session |
| "What breaks if I change `X`?" | `codegraph_impact` | Main session |
| "List source files matching pattern" | `codegraph_files` | Main session |
| "Is the index alive / fresh?" | `codegraph_status` | Main session |
| "Explain the area around `X`" (broad) | `codegraph_context` | **Explore subagent only** |
| "Map a feature from scratch" | `codegraph_explore` | **Explore subagent only** |
| "Read a markdown / config file" | `Read` (gate does not apply) | Main session |
| "Read a file CodeGraph just pointed to" | `Read` (sentinel set, gate open) | Main session |

### Why the main-session / subagent split

The heavy tools (`codegraph_explore`, `codegraph_context`) return **full source sections from many
files in one call** — they fill main-session context fast. Delegate them to an Explore subagent,
which reads the heavy result and returns a focused summary.

The lightweight tools return small structured records and are safe to call directly.

When spawning an Explore agent, include this directive verbatim:

> CodeGraph is your primary tool. Start with `codegraph_explore` (broad map) or `codegraph_context`
> (focused area). Do NOT re-read files CodeGraph already returned source for — its sections are
> complete and authoritative. Only fall back to `Read` / `Grep` / `Glob` for files CodeGraph
> doesn't index (markdown, JSON, config, generated code).

## Worked examples

### "Why does the screener return no rows for AAPL?"

Wrong: `Grep -r "AAPL" src/` → blocked by the gate, and would be noise anyway.

Right:
1. `codegraph_search("StockScreenerService")` → locates the type.
2. `codegraph_node` on the hit → members and file:line.
3. `codegraph_callees` on the filter method → shows it reads `StockFundamentals` locally.
4. Now `Read` the file — the sentinel is set, the gate is open.

### "If I rename `StrategyStatus.Paused`, what breaks?"

1. `codegraph_search("StrategyStatus")` → the enum node.
2. `codegraph_impact` on it → the blast radius across backend and generated clients.
3. Cross-check the Angular side by hand: **generated TypeScript is not reliably indexed.** The
   `.ts` client is regenerated from C#, so `codegraph_impact` may not show the frontend consumers
   at all. Confirm with `git grep` on `ClientApp/**/generated/`.

### "Map the recording capture feature"

Do **not** call `codegraph_explore` in the main session. Dispatch an Explore subagent with the
directive above and a scope ("recording capture: entities, services, hub, Angular state") and keep
only its summary.

### "Where is the JWT secret read?"

1. `codegraph_search("JwtSettings")`.
2. `codegraph_callers` on the settings type → the DI registration and the token service.
3. `Read` `Program.cs` and the service — gate is open.

## Gate mechanics

| Hook | Event | Effect |
|---|---|---|
| `codegraph-first-guard.py` | PreToolUse on `Read`/`Grep`/`Glob` | **Blocks with exit code 2** if the sentinel is missing and the target is a source path. The message names the CodeGraph tool to use instead. |
| `codegraph-turn-tracker.py` | PostToolUse on `mcp__codegraph__*` | Creates `<cwd>/.claude/.codegraph-used-this-turn`. |
| `codegraph-turn-reset.py` | UserPromptSubmit | Deletes the sentinel — every new user turn opens a fresh investigation budget. |

Lifecycle hooks that keep the index fresh (not part of the gate): `SessionStart` →
`codegraph sync-if-dirty`; PostToolUse on Edit/Write/MultiEdit → `codegraph mark-dirty` (async);
`Stop` → `codegraph sync-if-dirty`.

## Allowlist — the gate does not apply

- **Extensions:** `.md`, `.json`, `.yaml`, `.toml`, `.ini`, `.env`, `.lock`, `.log`, `.csv`, `.sql`,
  `.http`, `.gitignore`, `.editorconfig`
- **Path segments:** `/.claude/`, `/.git/`, `/node_modules/`, `/bin/`, `/obj/`, `/dist/`, `/build/`,
  `/Migrations/`, `/generated/`, `/assets/wiki/`, `/__pycache__/`, `/.venv/`, `/venv/`,
  `/concepts/`, `/.codegraph/`
- **Filenames:** `CLAUDE.md`, `MECHANISMS.md`, `VOCABULARY.md`, `JOURNAL.md`, `INTEGRATION.md`,
  `memory.md`, `README.md`, `.gitkeep`

## Failure modes seen in this project

**The index is wrong in both directions.** It reports phantom files that do not exist *and* misses
real ones, while `codegraph status` says "up to date". **Trust it for relationships; never for file
existence or inventories.** Confirm on disk before asserting a file exists or that a count is
complete.

**The documented auto-bypass does not exist.** `CLAUDE.md` claims the gate auto-bypasses when
CodeGraph is unavailable. It does not — the hook still hard-blocks `Read`/`Grep`/`Glob` when the
MCP server is absent. Workaround: read via Bash (`cat`, `sed -n`) which the gate does not intercept.

**Worktree paths bypass the gate.** `.claude/worktrees/` matches the allowlist's `/.claude/`
segment, so an agent working in a worktree can `Grep` source directly. Do not build an argument on
the assumption that the gate held there.

## Escape hatches

- One-shot: the **user** (not an agent) sets `CLAUDE_SKIP_CG=1`.
- Index dead or stale: run `codegraph sync` or `codegraph init -i`, then resume normally.
