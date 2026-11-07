# CodeGraph decision table — full version with worked examples

The condensed table lives in [CLAUDE.md](../../CLAUDE.md) → "CodeGraph (PRIMARY investigation
tool)". This is the long form: the same routing plus worked examples, the retired gate, and the
failure modes that have actually bitten this project.

> **Provenance.** Reconstructed on 2026-08-25. `CLAUDE.md` cited this path for the worked-example
> version while the file was missing from disk.

---

## The rule

**Every codebase question starts with a CodeGraph call.** This is guidance, not a gate by default: the plugin
ships the code-search-first hook as the opt-in `codegraph` add-on, installed by
`auto-improve-codegraph-install`, so a `Read` / `Grep` / `Glob` is blocked for want of a CodeGraph
call only in a project that installed it. The routing below still says which tool answers which question best.

## Routing

| Question | Ask CodeGraph for | Where to call |
|---|---|---|
| "Where is `X` defined?" | a symbol lookup, then the symbol's members | Main session |
| "Who calls `X`?" | the callers of the symbol | Main session |
| "What does `X` call?" | the callees of the symbol | Main session |
| "What breaks if I change `X`?" | the impact of the symbol | Main session |
| "List source files matching pattern" | the indexed files | Main session |
| "Is the index alive / fresh?" | the index status (or run `codegraph status`) | Main session |
| "Explain the area around `X`" (broad) | a focused context for the area | **Explore subagent only** |
| "Map a feature from scratch" | a broad exploration | **Explore subagent only** |
| "Read a markdown / config file" | nothing (`Read`, no CodeGraph call needed) | Main session |
| "Read a file CodeGraph just pointed to" | nothing (`Read`) | Main session |

Say `mcp__codegraph__*`, never one tool's name: a server offers different tools from one release to the
next (the current one offers only its explore tool), and the permission entry an install writes is the
wildcard `mcp__codegraph__*` for the same reason.

### Why the main-session / subagent split

The heavy questions (a broad exploration, a focused context) return **full source sections from many
files in one call** — they fill main-session context fast. Delegate them to an Explore subagent,
which reads the heavy result and returns a focused summary.

The lightweight questions return small structured records and are safe to ask directly.

When spawning an Explore agent, include this directive verbatim:

> CodeGraph is your primary tool. Start with a broad exploration or a focused context question,
> through a `mcp__codegraph__*` tool. Do NOT re-read files CodeGraph already returned source for — its sections are
> complete and authoritative. Only fall back to `Read` / `Grep` / `Glob` for files CodeGraph
> doesn't index (markdown, JSON, config, generated code).

## Worked examples

### "Why does the screener return no rows for AAPL?"

Wrong: `Grep -r "AAPL" src/` → would be noise; ask CodeGraph instead.

Right:
1. Ask CodeGraph for `StockScreenerService` → locates the type.
2. Ask for the members of the hit → members and file:line.
3. Ask for the callees of the filter method → shows it reads `StockFundamentals` locally.
4. Now `Read` the file.

### "If I rename `StrategyStatus.Paused`, what breaks?"

1. Ask CodeGraph for `StrategyStatus` → the enum node.
2. Ask for its impact → the blast radius across backend and generated clients.
3. Cross-check the Angular side by hand: **generated TypeScript is not reliably indexed.** The
   `.ts` client is regenerated from C#, so the impact answer may not show the frontend consumers
   at all. Confirm with `git grep` on `**/generated/` under the `frontend.root-container` slot of
   `.claude/project-profile.md`.

### "Map the recording capture feature"

Do **not** ask a broad exploration question in the main session. Dispatch an Explore subagent with the
directive above and a scope ("recording capture: entities, services, hub, Angular state") and keep
only its summary.

### "Where is the JWT secret read?"

1. Ask CodeGraph for `JwtSettings`.
2. Ask for the callers of the settings type → the DI registration and the token service.
3. `Read` `Program.cs` and the service.

## Retired gate (0.7.0)

Three hooks used to turn the rule above into a block. The plugin retired them in 0.7.0 and now ships
them again as the opt-in `codegraph` add-on (never registered by the plugin itself):

| Retired hook | What it did |
|---|---|
| code-search-first guard | Blocked `Read`/`Grep`/`Glob` on source paths until a CodeGraph tool had run in the turn. |
| CodeGraph turn tracker | Created the per-turn marker after a CodeGraph call. |
| CodeGraph turn reset | Deleted the marker at every new prompt. |

A project that wants the block back runs `/auto-improve-codegraph-install`; the README's "Retired hooks" section says how.

The plugin registers no hook that refreshes the index, and no part of it runs `codegraph mark-dirty`
or `codegraph sync-if-dirty`. Keeping the index fresh belongs to the CodeGraph MCP server, whose
file watcher notices edits on its own. If the index is stale anyway, the user runs `codegraph sync`
or `codegraph init -i`.

## When the `codegraph` add-on is installed

A project that ran `/auto-improve-codegraph-install` has the block back, as three hooks that share
one session folder, `<Per-user session parent>/auto-improve-codegraph-<session id>/`. The Per-user session
parent is `%LOCALAPPDATA%\auto-improve-codegraph\` on Windows and `$XDG_CACHE_HOME/auto-improve-codegraph/`
(else `~/.cache/auto-improve-codegraph/`, mode `0700`) on POSIX; the system temp folder is never used:

| Hook | Event | Effect |
|---|---|---|
| `codegraph-first-guard.py` | PreToolUse on `Read`/`Grep`/`Glob` | **Blocks with exit code 2** if the session's `turn.json` marker is missing, the target is a source path and CodeGraph is available. The message says to ask CodeGraph through a `mcp__codegraph__*` tool. |
| `codegraph-turn-tracker.py` | PostToolUse on `mcp__codegraph__*` | Writes the session's `turn.json` marker, whatever the tool is called. |
| `codegraph-turn-reset.py` | UserPromptSubmit | Deletes the marker and the retry tickets, so every new user turn opens a fresh investigation budget. It also prunes old session folders in that parent, once per session. |

The marker belongs to the session, not to a directory, so `cd` or `EnterWorktree` does not close the
gate again.

**The installed guard fails open when CodeGraph is provably unavailable.** It lets the read through,
prints `[codegraph-first-guard] allowed (fail-open:<reason>)` and logs one record per session per
reason. While the session folder cannot be used, these lines print on every call and nothing is logged. The reasons are: `no-index` (no `.codegraph/codegraph.db` in the project, its parents or the
main checkout; CodeGraph's own per-user `~/.codegraph` has no `codegraph.db` and does not count),
`index-other-tree` (a linked worktree without its own index, whose only index belongs to the main
checkout, so its answers would be stale), `server-not-configured`, `server-disabled`, and `subagent`
(the payload carries an `agent_id`). An unusable session folder blocks with `session-state-unusable` and offers no retry. A subagent
shares its parent's session, so a CodeGraph call by either opens the gate for both until the next
prompt.

**The retry escape.** In any other session where no `mcp__codegraph__*` tool is available (a
background session, say), repeat the blocked call once, exactly: it is allowed and logged as
`retry-escape`. A different call is blocked again, and the next prompt clears the escape. Not after a
`session-state-unusable` block, which offers no retry. After a `retry-ticket-unwritten` block the retry was
not recorded, so the repeat is blocked once more (as `source-target` or `ambiguous-target`) and the identical call after it is
allowed. There is no bypass variable.

**Ways out.** Run `/auto-improve-codegraph-uninstall` and start a new session. To stop the block for
good, that uninstall skill removes the three hooks' rows from the project's `settings.json`; only when
a hook cannot run does the user remove a row by hand (the README table "Ways out when a hook cannot
run"). A stale index is fixed with `codegraph sync` or `codegraph init -i`. `addon --name codegraph
--check` judges the permission entry. The README's "Retired hooks" section lists the add-ons and their
skills.

## Allowlist — paths the retired gate skipped

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

**The gate used to have no escape without an index.** Before 0.7.0 the hook hard-blocked `Read`/`Grep`/`Glob` when the MCP server was absent, which is one reason it was retired, and the add-on's copy did the same until 0.15.2. It now fails open and offers the retry escape (since 0.15.3, an unusable session folder blocks); see "When the `codegraph` add-on is installed" above.

## Index health

- Index dead or stale: run `codegraph sync` or `codegraph init -i`, then resume normally.
