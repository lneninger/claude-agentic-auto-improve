# Concept Contract — The code-search-first guard fails open when CodeGraph is unavailable (issue #259)

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-05 (revision 5, after the fourth critique and the user's answers)
**Requested by:** user
**Status:** implemented
**Implemented:** 2026-11-05, automatically, by pr_merged.py after https://github.com/lneninger/claude-agentic-auto-improve/pull/270; 0 checklist items from review reports, 7 with no structured evidence; not performed (disclosed on #259): none; owner confirmed resolved: none
**Approved:** 2026-11-05 by the user ("approve with addendum"), after five critique rounds; see `## Approval addendum (binding)`.
**Work Item Brief:** .claude/work-items/2026-11-05-259-codegraph-guard-fail-open.md
**Tracking issue:** #259
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. The lifecycle, budget rule and handoff rules are in `.claude/templates/concept-contract.md`.

---

## Business Concept

- **What is this thing, in domain language?**
  The `codegraph` add-on's guard asks the agent to start an investigation with CodeGraph. Today it treats CodeGraph as a precondition. With no CodeGraph tool attached (a background session, a subagent, no index, a server removed after install), every source `Read`, `Grep` and `Glob` is blocked. Its own message then advises reading through the shell, which goes around the gate. A separate case: a worktree session whose CodeGraph answers come from the main checkout's index, which lacks the branch's changes. CodeGraph IS attached there, but its answers about this tree are stale (Q7). This contract turns the guard into what the protocol intends, a **nudge that never removes the ability to read code**:
  1. **Fail open** when CodeGraph is provably unavailable, or provably answers for another tree (Q7), with one logged line saying why.
  2. **Retry escape**: the identical retry of a blocked call is allowed once and logged. This replaces the shell advice. No environment variable is involved.
  3. **Session-keyed marker**: `cd` or `EnterWorktree` does not close the gate again.
  4. **Wildcard only**: no shipped file names an individual CodeGraph tool, either as `mcp__codegraph__codegraph_<x>` or as a bare legacy name (see the scan). The server now offers only `codegraph_explore`.
  5. **Upgrade path** for projects that installed the old hooks.
- The guard's matcher is `Read|Grep|Glob` (`addon.json:15`), so it never gates `Edit`. A subagent that can `Read` can therefore `Edit` (acceptance criterion 2, the Edit half).
- **Existing VOCABULARY.md terms:** CodeGraph, Investigation Turn (amended), Add-on hook, Add-on manifest, Installed plugin root. "Tree kind" is a MECHANISMS.md term (`MECHANISMS.md:43, 72`), not a VOCABULARY.md one.
- **Acceptance criterion 9** (a test fails if the settings template lists a per-tool entry): the plugin ships no settings template (VERIFIED). The template's role is played by `addon.json` `permissions_allow`, which the install writes. Criterion 9 is answered by the `test_plugin_manifests.py` test "permissions_allow is the wildcard only" (it fails on any per-tool entry) together with the shipped-file scan.
- **New terms proposed (Universal):**
  - **Retry escape**: this guard's single-use allowance for the identical repeat of a call it just blocked. It is issued at the block, consumed by the first identical retry in the same session and turn, logged, and cleared at the next prompt.
  - **CodeGraph unavailability reason**: the closed set `no-index`, `index-other-tree`, `server-not-configured`, `server-disabled`, `subagent`.
  - **Amendment to Investigation Turn**: the marker is `turn.json` in the session's folder under the system temp folder, not `<cwd>/.claude/.codegraph-used-this-turn`.

---

## End-User View

Not applicable. Reason: no Angular UI surface is touched. The change is hook behaviour, installer output and documentation.

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership |
|------|--------|------------|-----------|
| Session folder | `<system temp>/auto-improve-codegraph-<session key>/` | One per Session key, created lazily by any of the three hooks. A subagent's payload carries the PARENT session's `session_id` (live trial), so a subagent shares its parent's folder. The hooks never read or write the folder, and the guard falls to decision step 0, when it is a link or junction, is not a folder, or (on POSIX) is owned by another user. | the three hooks |
| Turn marker | `turn.json`: `{ts, tool, summary, pid}` | Written by the tracker after ANY `mcp__codegraph__` tool (legacy, current or future name). Deleted by the reset hook. Read by the guard. | tracker / reset |
| Retry escape ticket | `ticket-<call fingerprint>`: `{ts, tool, fingerprint}` | Written by the guard at a block. Consumed (deleted) by the first identical call, which is allowed. Deleted by the reset hook. | guard |
| Availability cache | `availability.json`: `{server: configured / not-configured / disabled, trees: {<normalised payload cwd>: index-present / index-other-tree / no-index}, checked_at}` | The server verdict is computed once per session. The index verdict is computed once per distinct payload `cwd` (a few `stat` calls, no subprocess). Staleness can only fail open (an index built mid-session is seen next session). | guard |
| Notice flag | `logged-<reason>` | At most one log record per session per fail-open reason. | guard |
| Prune flag | `pruned` | The reset hook prunes the temp folder at most once per session: on the first prompt, and never again while this flag exists. | reset |

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Session key | `session_id` when it matches `[A-Za-z0-9][A-Za-z0-9._-]{0,127}` (the grammar of `_project_paths._SESSION_ID_RE`); else `cwd-` + 16 hex digits of SHA-256 of the normalised payload `cwd` (process cwd when absent) | Session folder name |
| Call fingerprint | SHA-256 of `tool_name` + canonical JSON of `tool_input` (sorted keys) | identity of "the same call" |
| Own tree root (the one shared rule) | `worktree_own_root(path)`, a NEW function in `.claude/hooks/_project_paths.py`. It is the only definition; the installer imports it through a re-export line in `.claude/scripts/_claude_paths.py`. Walk up from the nearest existing ancestor of `path` to the first folder F that holds a `.git` entry. Return `(F, gitdir)`, where `gitdir` is `None` when `.git` is a folder (a main checkout), or, when `.git` is a FILE whose first line is `gitdir: X`, X resolved against F when it is relative, normalised, with forward slashes. Return `(None, None)` when no `.git` exists up to the root or the file is unreadable. It reads `.git` entries only: no subprocess, no environment. `main_checkout_root` cannot serve here, because for a linked worktree it returns the MAIN checkout's root (`_project_paths.py:579, 612-615`). `enclosing_worktree_root` cannot either, because it covers only `.claude/worktrees/<name>`. | the Caller tree root for both the guard and the installer |
| Caller tree | `root` = `worktree_own_root(cwd)[0]`, where `cwd` is the payload `cwd` for the guard (else `CLAUDE_PROJECT_DIR`) and `--project` for the installer. `kind` = `tree_kind(root)`. `main` = `main_checkout_root(root)`. The guard binds `worktree_own_root`, `tree_kind` and `main_checkout_root` with `getattr` (Guard fallback mode). When `worktree_own_root` is unbound, the guard uses an inline copy of the same walk, pinned to the helper by a parity test. When `tree_kind` or `main_checkout_root` is unbound, `kind` is `unknown`. | the index rule and the server paths |
| Project index | `<folder>/.codegraph/codegraph.db` is a regular file. Neither the file nor `.codegraph` may be a link. A `.codegraph` folder without `codegraph.db` is NOT an index: CodeGraph's own per-user data folder `~/.codegraph` (daemons, models, telemetry, update-check; verified by the main session on 2026-11-05) has that shape. | the ONLY meaning of "has an index" anywhere in this contract: guard rule, installer note, fixtures, tests |
| Index search set | every folder from the payload `cwd` up to the filesystem root, every folder from `CLAUDE_PROJECT_DIR` up to the root, and the Main checkout candidate | proving absence of a Project index; no tree kind is needed |
| Main checkout candidate | the first that applies: (a) `main_checkout_root(<path>)` when bound and decidable; (b) when `worktree_own_root(path)` (or its inline copy) returns a `gitdir` containing `/.git/worktrees/`, the text before `/.git/worktrees/`. The `.git` file is found by that same upward walk, and a relative `gitdir:` is resolved against the folder holding the `.git` file. This needs no `commondir`, so it covers a worktree outside the main folder under Guard fallback mode. In the legacy fixture, `repo/.git` (`gitdir: ../.git/worktrees/dummy`) resolves to the fixture's temp root, which holds no index and no server, so it changes no verdict there; (c) the text before the last worktree segment matched by the guard's existing `_FALLBACK_WORKTREE_MARKER_RE`; (d) none | the Index search set and the server paths |
| Index ownership (the rule the guard and the installer share) | Evaluated in order. (1) `no-index`: no folder in the Index search set holds a Project index. This works for every tree kind, so acceptance criterion 5 is met wherever absence is provable. (2) `index-other-tree`: the Caller tree `kind` is `linked-worktree` (bound helpers only), the Caller tree `root` (the worktree's OWN root, from `worktree_own_root`) holds no Project index, and `main` (a different folder) does. (3) `index-present`: anything else. The gate stays. | decision step 4 and the installer note (acceptance criterion 11) |
| Server project paths | the ordered list `[CLAUDE_PROJECT_DIR, Main checkout candidate(CLAUDE_PROJECT_DIR)]`, falling back to the payload `cwd` and its candidate when the variable is unset. `configured` if ANY path yields a configured, non-disabled entry under the `_mcp_server_state` rule. The candidate has a fallback, so the main checkout stays on the list under Guard fallback mode. | decision step 5. Biased toward `configured`, so a server recorded under the main checkout's path keeps the gate in a worktree session. |
| Guard decision | `allow` or `block` + reason: `no-target`, `non-source-target`, `turn-marker-present`, `fail-open:<unavailability reason>`, `fail-open:state-unwritable`, `retry-escape-used`, `source-target`, `ambiguous-target` | every `allow` with a `fail-open:` or `retry-escape-used` reason prints one stderr line `[codegraph-first-guard] allowed (<reason>): <sentence>` |
| Manifest permission grant | addon.json `permissions_allow`, exactly `["mcp__codegraph__*"]` for codegraph | entries the install adds to `permissions.allow`. Never a per-tool name. `--check` accepts either `mcp__codegraph__*` or the server form `mcp__codegraph` as the wildcard, so a switch to the server form (see Uncertain Assumptions) needs only the manifest value changed. |
| Manifest released hashes | addon.json `released_sha256`: `{<active hook>: [sha256 hex]}`, same fold as `disabled[].released_sha256` | `addon-remove` deletes an unedited old copy |
| CodeGraph permission finding | `{code: codegraph-tool-named / codegraph-wildcard-missing, layer, entry}` | install refusal and `--check` |

### Guard decision order (invariants)

0. The Session folder is unusable (a link, not a folder, owned by another POSIX user, or unwritable) → allow (`fail-open:state-unwritable`). A guard that cannot record an escape must not block. A planted folder can only cause an allow, which is acceptable for a nudge.
1. No target → allow. Every target in the non-source allowlist → allow. Both unchanged.
2. The Turn marker exists → allow.
3. The payload carries a non-empty `agent_id` → allow (`fail-open:subagent`). The live trial verified that a subagent's payload carries `agent_id` and the main session's does not. Policy (Q1, answered a): every subagent's reads are let through.
4. Index ownership is `no-index`, or `index-other-tree` (kept as a reason to let reads through; Q7 answered a) → allow with that reason.
5. The server verdict is `not-configured` or `disabled` → allow with that reason.
6. A ticket matches the Call fingerprint → delete it, allow (`retry-escape-used`).
7. Otherwise write the ticket and block.
- **I-1 (positive control):** with an index present (in a main checkout, a non-git project or an undecidable tree; or in a linked worktree that has its own Project index), a configured server, no `agent_id` and no marker, the first source call blocks. Only its identical retry passes. Under Q7(a), a linked worktree WITHOUT its own index has no positive control. The controls that keep the gate proven are the main-checkout session and the worktree that owns an index (which the install skill offers to build).
- **I-2:** the block message names no individual tool, no bare legacy name and no shell route (`cat`, `sed`, "through the shell"). It names `mcp__codegraph__*`, the retry escape ("repeat this exact call once if no CodeGraph tool is available to you; it will be allowed and logged"), `/auto-improve-codegraph-uninstall` with "new session", `codegraph sync`, `codegraph init -i` and `/auto-improve-codegraph-install`. It names no `CLAUDE_SKIP_CG` and no `references/` path.
- **I-3:** the guard has no kill switch. No variable switches it off. `CLAUDE_PROJECT_DIR` and `TMP`/`TEMP` only locate the project and the temp folder.
- **I-4:** an internal error allows (exit 0), as today.
- **I-5 (reset and pruning):** the reset hook deletes this session's `turn.json` and tickets, and a legacy `<cwd>/.claude/.codegraph-used-this-turn` if present. Pruning runs once per session (Prune flag) and follows Delivery cleanup (`MECHANISMS.md:76`) and the Records leftover sweep (`MECHANISMS.md:78`).
  - **Link test** (Delivery cleanup's, on every supported Python): `os.lstat`, then a link means `stat.S_ISLNK`, or on Windows `st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT`. Never `is_junction` / `isjunction` (Python 3.12+ only).
  - **Folder test.** For each entry in the temp folder named `auto-improve-codegraph-*`, skip it (never delete) when any of these holds:
    - it is a link (Link test), or not a folder;
    - on POSIX, its owner is not the current user;
    - it holds anything other than plain, non-link files named `turn.json`, `availability.json`, `pruned`, `logged-<reason>` or `ticket-<64 hex>`;
    - its newest file is younger than 7 days.
  - **Per-file re-check, immediately before each `os.remove`:** `lstat` the file again. It must still be a plain file, not a link, with a known name. Its real path's parent must equal the folder's real path, and the folder must still not be a link. On any mismatch, stop and keep the folder.
  - **Folder removal:** re-`lstat` the folder, then `os.rmdir`. Never `rmtree`. Any failure keeps the rest.
  - **Test seam:** the reset hook's prune function takes an optional `before_remove(path)` callable, default a no-op. It is called after the folder test and immediately before each per-file re-check. A test loads the hook module with `importlib` and passes a callable that swaps the entry.

### Events

| Name | Emitter | Listeners | Payload |
|------|---------|-----------|---------|
| GuardFailedOpen | guard | stderr every time; `log_event(hook="codegraph-first-guard", event="fail-open")` once per session per reason | reason, tool |
| RetryEscapeUsed | guard | stderr; `log_event(event="retry-escape")` every time | tool, fingerprint prefix |
| GuardBlocked | guard | stderr banner; `log_event(event="block")` (unchanged) | tool, reason |

### Commands

| Name | Handler | Payload | Possible rejections |
|------|---------|---------|---------------------|
| Check the add-on's settings | `auto_improve_finish_install.py addon --name codegraph --project . --check` (read-only) | settings layers | exit 1 with findings; exit 2 when it could not check |
| Install (extended) | `addon --name codegraph` preview / apply | as today, plus the `permissions_allow` insert in the same plan hash, and an index-ownership note from the shared rule | `codegraph-tool-named` (exit 2), listing each entry and layer |
| Remove (extended) | `addon-remove --name codegraph` | as today | a hook whose folded hash is in `released_sha256` becomes `delete`. The permission entry is left and listed under `kept`. |

---

## Reused Mechanisms

- **Add-on layout**: extended with the optional manifest keys `permissions_allow` and `released_sha256`, validated in `_read_addon_manifest`, `addon_problems` and `_addon_fixture`.
- **Disabled add-on hook**: its released-hash rule is extended to active hooks. Same hash, same fold, same deleter.
- **Preview-hash apply**: extended. The permission insert joins the plan, and `--check` is a read-only mode of `addon`.
- **Two-layer Claude path resolution, tree classification**: EXTENDED by one function, `worktree_own_root`, in `_project_paths.py`, plus one re-export line in `_claude_paths.py`. This is the entry's own Extend-by. `tree_kind` and `main_checkout_root` are consumed as-is. Index ownership is one rule, with no subprocess.
- **Guard fallback mode**: extended. The guard binds `tree_kind` and `main_checkout_root` with `getattr`. When either is missing or stale:
  - `index-other-tree` cannot fire;
  - `no-index` still can (it needs no tree kind);
  - the Main checkout candidate falls back to the inline `gitdir:` parse, then to the existing worktree-marker regex.

  The existing worktree fallback is unchanged.
- **`_mcp_server_state`** (install script): its rule is mirrored in step 5, and a parity test pins the copy.
- **Delivery cleanup / Records leftover sweep**: their link and one-file-at-a-time deletion rules govern the pruner (I-5).
- **Memory adapter scan** (`shipped_files` in `test_plugin_text_scans.py`): consumed. A sibling scan covers CodeGraph tool names.
- **Plugin version check modes**: one block, patch raise.
- Pattern, not a registered mechanism: the session-keyed temp marker of `_project_paths.py:811-831` and `stop-dispatcher.py`. It is copied inline in the three hooks, because an add-on copies a helper only when the project lacks it.

## New Mechanisms (if any)

None. Decide at review whether the Retry escape should be promoted, once a second guard adopts it.

---

## Extension Points

- **`addon.json`:**
  - add `permissions_allow` and `released_sha256`, with the folded hashes of every committed version of the three hooks since the add-on was created;
  - keep the matcher `mcp__codegraph__.*`.
- **`auto_improve_finish_install.py`:**
  - manifest validation for the two keys;
  - the permission insert;
  - the `codegraph-tool-named` refusal;
  - `--check`;
  - released hashes in `addon-remove`;
  - the preview note from the shared index-ownership rule (Project index = `.codegraph/codegraph.db`): "the index at <main>/.codegraph belongs to the main checkout, so the guard lets reads through in this worktree" or "no index: the guard lets every read through until one exists". A `.codegraph` folder with no `codegraph.db` is named as "not an index".
- **Install skill:**
  - show the permission entry and relay the index note;
  - offer once to run `codegraph init -i` in this working tree (only on a yes);
  - describe the five fail-open reasons and the retry escape, and drop the shell advice;
  - list the refusal;
  - give the upgrade route (uninstall skill, this skill, a new session).
- **Uninstall skill:**
  - the leftover is now the session folder in the system temp folder, which the reset hook prunes;
  - the permission entry is kept;
  - an unedited old hook copy is deleted through the released hashes;
  - restate the upgrade route;
  - drop the shell advice and the "read through the shell" way out.
- **`/verify-before-done`:** one step runs `--check` when `.claude/settings.json` has a `codegraph-first-guard.py` row. Exit 1 or 2 means NOT READY.
  - It finds `auto_improve_finish_install.py` through the standard lookup block, copied verbatim from Step 0 of `skills/auto-improve-codegraph-install/SKILL.md` (variable `FI`, ending at a line that runs the script).
  - If the lookup finds nothing, the step says so and reports "could not check", never READY.
  - `.claude/scripts/tests/test_skill_script_lookup.py` scans every skill's lookup blocks and pins this one. It is expected to pass unchanged and is run.
- **`skills/auto-improve-finish-install/SKILL.md:218-219, 329`:** say the add-on lets reads through when CodeGraph is unavailable.
- **`.claude/hooks/hooks.json:51`** (comment text): replace "a gate that blocks every source read when the CodeGraph server is missing" with the true cost:
  - three program starts: on every Read, Grep and Glob; on every prompt (the reset hook, which also lists the system temp folder once per session to prune); and after every CodeGraph call;
  - plus one blocked round trip per new source call while the gate is closed.

### Wildcard and legacy-name reach (every line found by the reference sweep)

| File | Lines | Change |
|------|-------|--------|
| guard | 377-405, 437-439 | rewritten by I-2 |
| `agents/data-architect.md` | 105-117 (search, node, callers, callees, impact, files, context, status) | tool-agnostic sequence: "ask CodeGraph (`mcp__codegraph__*`, for example the explore tool your server offers)" |
| `agents/{api-contract-reviewer, fullstack-code-reviewer, migration-safety-reviewer, security-auditor, sql-performance-reviewer, test-strategy-critic}.md:14`, `agents/contract-critic.md:18` | body text | same wording; `tools:` lines unchanged |
| `.claude/references/codegraph-decision-table.md` | routing table 21-32, worked examples 49-80, retired-gate and installed sections 82-126, failure modes 145 (22 tool-name hits plus the shell advice at 114-120) | tool-agnostic routing by question; examples use "a CodeGraph query"; the installed section describes fail-open, the retry escape and the session folder |
| `.claude/registries/VOCABULARY.md` | 13 (`mcp__codegraph__codegraph_*`), 14-15 (`codegraph_search`, `codegraph_node`, `codegraph_callers`, `codegraph_callees`, `codegraph_impact`), 16 (`<cwd>` sentinel) | edit the name spans in place (Q2) and append dated corrections, including the Investigation Turn amendment |
| `.claude/registries/MECHANISMS.md` | 15 (tool list, `<cwd>` sentinel, `CLAUDE_SKIP_CG`), 92-96 (ways out list "read through the shell") | edit the name span in place (Q2); append dated corrections replacing the sentinel and ways-out text with fail-open and the retry escape |
| `README.md` | 404, 478, 528-535, plus a new "Changed in 0.15.2" note | fail-open, the retry escape, no shell advice, the upgrade route (rows per install age) |
| `skills/auto-improve-codegraph-install/SKILL.md` | 72-76, 93-95, 151, 201 | marker location, the shell advice, fail-open |
| `skills/auto-improve-codegraph-uninstall/SKILL.md` | 26, 139 | as in Extension Points |

**Not affected (checked):**
- `.claude/scripts/cross_area_scan.py` uses the `codegraph` CLI (`codegraph impact`). `codegraph_impact_files` and `codegraph_signal` are Python names, not MCP tools, and the word-boundary scan does not match them.
- `skills/cross-impact/SKILL.md` describes the same CLI signal.
- `skills/north-star-review/SKILL.md` and `.claude/scripts/north_star_review.py` name the CLI and the `.codegraph` folder only.

**Scan** (`test_plugin_text_scans.py`): no shipped file contains `mcp__codegraph__codegraph_`, and none contains a bare legacy name matching `\bcodegraph_(search|node|callers|callees|impact|files|status|context)\b`. The only exemption is the two test files that prove the wildcard covers legacy names: `.claude/hooks/tests/test_addons.py` and `.claude/hooks/tests/test_codegraph_first_guard.py`. Planted-file controls show that another file under `.claude/hooks/tests/`, a registry and an agent are all caught. A second assertion requires every agent whose `tools:` line grants CodeGraph to grant exactly `mcp__codegraph__*`. README is not shipped (`check_version_bump.EXEMPT_NAMES`), so it is edited but not scanned.

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| Claude Code host | codegraph hooks | hook stdin JSON | `session_id`, `cwd`, `agent_id` (subagents only; verified), `tool_name`, `tool_input` | host → hook |
| codegraph hooks | each other | Session folder files | marker, tickets, cache | hook ↔ hook |
| install script | project `.claude/settings.json` | Preview-hash apply | hook rows + permission entry | script → project |

No REST, SignalR or DTO surface. Both sides of each row are in `Files to touch`.

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold. `.claude/area-mapping.json` has an empty `areas` object, so no area can score. Not run here (no shell). To confirm: `py -3 .claude/scripts/cross_area_scan.py .claude/concepts/2026-11-05-codegraph-guard-fail-open.md`.

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

---

## Non-Goals

- Finding out why background sessions and subagents get no MCP tools (separate issue).
- The `bash-gate` test-file refusal (separate issue).
- Running `codegraph sync` on any index. Building one happens only on a yes in the install skill.
- Asking the running server which tools it offers (Q3).
- Removing the permission entry on uninstall.
- Performance redesign, a once-per-session gate, or a nudge-before-block policy: issue #261 (https://github.com/lneninger/claude-agentic-auto-improve/issues/261).

## Confidence

Confidence: Medium.
- **High:** the decision order, the marker model, the payload fields (live trial), the wildcard reach and the test impact. The test impact was read against the hook and the seven test files the block changes: `test_codegraph_first_guard.py`, `test_addons.py`, `test_worktree_path_guards.py`, `_addon_fixture.py`, `test_auto_improve_finish_install.py`, `test_plugin_manifests.py` and `test_plugin_text_scans.py`, plus a sweep of the whole worktree.
- **Medium:** the index rule. The tree kind is verified against `_project_paths.py:561-615`, and the index shape against one real index and `~/.codegraph` on this workstation only; other CodeGraph versions may lay out `.codegraph` differently. Also the installer extensions (the permission insert is a new edit kind for `_plan_settings_edit`).
- **Low:** whether the host honours `mcp__codegraph__*` as a permission rule. This is not established; the fallback is stated.

## Alternatives Considered & Why Rejected

- **Option A (chosen):**
  - What: layered proof of unavailability (five reasons), a single-use retry escape as the backstop, session-folder markers, and index ownership decided by `.git` entries.
  - Why: every case is either detected or costs one round trip. The positive control holds, and nothing slow runs on the hot path.
- **Option B (rejected):**
  - What: decide ownership with `codegraph status` or by reading the index's own metadata.
  - Why rejected: a subprocess on every Read is slow, and the index format is not a contract. Even cached per session, the first call pays the start-up cost and the CLI may be absent.
- **Option C (rejected):**
  - What: keep the marker under the project, keyed by session.
  - Why rejected: "the project" is derived from a directory that `EnterWorktree` changes, which is the defect being fixed.
- **Option D (rejected):**
  - What: put the marker helpers in `_project_paths.py`.
  - Why rejected: existing installs keep their old helper, because an add-on copies a helper only when the project lacks it.
- **Option E (rejected):**
  - What: a retry escape that opens the whole turn.
  - Why rejected: one retry would switch the guard off for the turn even where CodeGraph works.
- **Option F (rejected):**
  - What: keep the shell advice in the block message.
  - Why rejected: it teaches a route that defeats the gate and every other read guard. The retry escape is the sanctioned, logged way past.

## Uncertain Assumptions

- `VERIFIED via live trial 2026-11-05` (Claude Code 2.1.318, throwaway folder outside every repository, run by the main session): a subagent's PreToolUse payload carries `agent_id` (a non-empty string) and `agent_type` (seen: `general-purpose`). The main session's payload has neither key. Step 3 keys on `agent_id`.
- `VERIFIED via live trial 2026-11-05`: the payload keys are `cwd`, `effort`, `hook_event_name`, `permission_mode`, `prompt_id`, `session_id`, `tool_input`, `tool_name`, `tool_use_id`, `transcript_path`, plus `mcp_server` for MCP tools and `agent_id` / `agent_type` for subagents. `session_id` is present, so the Session key has evidence. A subagent's payload carries the PARENT session's `session_id`, so a subagent shares its parent's Session folder: a CodeGraph call by either opens the gate for both until the next prompt.
- `VERIFIED via live trial 2026-11-05`: the hook saw the CodeGraph tool as `mcp__codegraph__codegraph_explore`, with `mcp_server` in the payload. The tracker's prefix test covers it.
- `ASSUMED` (not established by the trial): `permissions.allow: ["mcp__codegraph__*"]` is honoured.
  - The trial could not tell: the tool ran both with the wildcard allowed and with an empty allow list, and project `permissions.allow` entries were ignored in an untrusted folder.
  - **Fallback:** if the form proves not to be honoured, change `permissions_allow` to `mcp__codegraph`. `--check` already accepts both forms.
  - `VERIFIED by the critic, round 4`: this workstation's own `~/.claude/settings.json:20` allows the server form `mcp__codegraph`. The server form is therefore in real use. The brief (criterion 7) still requires the wildcard, so the install writes `mcp__codegraph__*`. This evidence only strengthens the fallback.
  - **Suggested discriminating trial** (not a precondition; record its result in the pull request): use a trusted folder with an approved server (`enabledMcpjsonServers: ["codegraph"]`) and an index. Put `mcp__codegraph__*` in `permissions.deny`. If the CodeGraph call is refused, the wildcard form is parsed.
- `ASSUMED` (not established): no background-session signal beyond `CLAUDE_CODE_ENTRYPOINT=sdk-cli`, which was seen in a `claude -p` run. Q6 stays as written.
- `ASSUMED`: Claude Code reads MCP configuration once per session, so a per-session server cache is correct. If wrong, the cache can only fail open.
- `VERIFIED via guard:173-179, 349-358, 437-439`: the marker is under `Path.cwd()`, only the marker opens the gate, and the block message advises the shell.
- `VERIFIED via test_worktree_path_guards.py:323-381, 1131-1273, 1372-1990, 2145-2164` and `_project_paths.py:561-604`: the fixture trees have no `.codegraph/` and no `.mcp.json`, and the C-series plants `<dir>/.claude/.codegraph-used-this-turn`. **Correction of revision 2:** every fixture tree reads `undecidable`, not `linked-worktree`.
  - `repo/.git` is a file pointing at `../.git/worktrees/dummy`, which does not exist.
  - `wt/.git` and `wt2/.git` point under `repo/.git/worktrees/…`, which cannot exist.
  - `_git_file_kind` returns `undecidable` when the target folder is missing (`:568-570`).

  So `index-other-tree` never fires in these fixtures, and without a planted Project index `no-index` would. `~/.codegraph` (no `codegraph.db`) is an ancestor of the default Windows temp folder, but it does not count. So the planted `repo/.codegraph/codegraph.db` (an ancestor of `wt` and `wt2`) is what keeps C1, C2, C7, C9 and task 3 blocking. The TASK block's control proves it: the same case with the file removed allows.
- `VERIFIED by the main session, 2026-11-05`: `C:\Users\lneni\.codegraph` holds `daemons`, `models`, `telemetry-queue.jsonl`, `telemetry.json` and `update-check.json`, and no `codegraph.db`. A real project index holds `codegraph.db` and `config.json`.
- `VERIFIED via _project_paths.py:571-579`: a real `index-other-tree` control needs four things:
  - a main `.git` folder;
  - `<main>/.git/worktrees/<name>/commondir` holding `../..` (without it the worktree reads `main-checkout`);
  - a worktree `.git` file `gitdir: <main>/.git/worktrees/<name>`;
  - `codegraph.db` under the main checkout only.

  Cover both layouts: a worktree under `<main>/.claude/worktrees/`, and one outside the main folder. In each layout the payload `cwd` is a SUBFOLDER of the worktree, so the upward walk is exercised.
  - **Rule (2) fires:** the worktree root has no `codegraph.db` and the main checkout has one, so the result is `index-other-tree` and the call is allowed.
  - **Rule (2) does not fire:** the same layout with `codegraph.db` also in the worktree root gives `index-present`, so the call is blocked.

  Run once with the gitdir written as an absolute path and once as a relative one (`gitdir: ../main/.git/worktrees/<name>` for the outside layout).
- `VERIFIED via auto_improve_finish_install.py:2086, 2101-2106`: `.claude.json` project entries count only under the exact project path given.
- `VERIFIED via sweep`: the lines in the reach table. All 15 agents' `tools:` lines already carry `mcp__codegraph__*`. The plugin ships no settings template.

### Live trial

Done on 2026-11-05 by the main session. Its results are recorded as the `VERIFIED via live trial` and `ASSUMED (not established)` bullets above. No trial is outstanding before dispatch. The suggested permission-form trial is optional, and its result goes in the pull request.

## Failure Modes & Mitigations

- **FM:** existing guard suites lose their blocks. Three causes: the fixtures have no index or server, repeated payloads hit the escape, or the developer's real home settings make the server verdict `disabled` or `configured`.
  - **Mitigation:** the fixtures get the markers the rules key on, plus a fresh `session_id` per run, per suite as listed in the TASK block (JOURNAL 2026-10-17). The CODEGRAPH rows point `HOME`, `USERPROFILE` and `CLAUDE_CONFIG_DIR` at a fixture home folder, and `TMP`/`TEMP` at a fixture temp folder. That covers `codegraph_env()` in `test_worktree_path_guards.py`, `clean_env` in `test_addons.py`, and `run_hook_process` in `test_codegraph_first_guard.py` (today it copies `os.environ` at `:72-79`; it must set these five variables too). A decoy `disabledMcpjsonServers` outside the read layers is ignored (JOURNAL 2026-10-05). Positive controls still block.
- **FM:** the home isolation makes task G (`snapshot_real_home_logs` / `assert_real_home_untouched`, `test_worktree_path_guards.py:581-610, 2137, 2170`) unable to fail.
  - **Mitigation:** the isolation goes in a new `codegraph_env()`, used only by codegraph rows. `base_env` is unchanged, so concept-gate, bash-gate and db-destructive-guard rows still see the real home, and task G still guards them. The snapshot reads the test process's own `expanduser("~")`, which no row changes. The codegraph guard logs through `_project_paths.logs_dir()` (project-local), so task G is not its leak check; for codegraph rows that check is the project's own `.claude/logs` in the fixture.
- **FM:** a `.codegraph` folder that is not a project index (CodeGraph's per-user `~/.codegraph`) makes `no-index` never fire for projects under the home folder.
  - **Mitigation:** a Project index requires `codegraph.db`. A test plants a decoy `.codegraph` without it in a parent of the fixture and gets `no-index`. Each no-index test first asserts that no ancestor of its fixture root holds a real `codegraph.db`, and fails loudly naming the folder if one does.
- **FM:** under Guard fallback mode, a worktree outside the main folder has no main checkout candidate, so the server reads `not-configured` and `no-index` fires.
  - **Mitigation:** candidate (b), from the inline copy of the `worktree_own_root` walk (relative `gitdir:` resolved against the `.git` file's folder), covers that layout without the helper. If even that fails (a malformed `.git` file), the guard allows, which fails toward reading. That is acceptable: it is a nudge, the case needs a stale helper plus a broken `.git` file, and the allow is logged with its reason. A fallback-mode row tests a worktree outside the main folder with the server only under the main path: the gate stays.
- **FM:** the retry escape becomes a habit.
  - **Mitigation:** accepted by design. Each use is logged as `retry-escape` for `/audit-errors`.
- **FM:** a worktree session reads a main-checkout server as absent.
  - **Mitigation:** Server project paths include the main checkout candidate, biased toward `configured`.
- **FM:** `index-other-tree` is never exercised by the legacy fixtures.
  - **Mitigation:** the `commondir` controls in both layouts, from a subfolder `cwd`, with an absolute and a relative `gitdir:`. Rule (2) fires when the worktree root has no index, and does not fire (block) when it has one.
- **FM:** `index-other-tree` turns the guard off in ordinary worktree sessions.
  - **Mitigation:** Q7. The worktree-local index offer restores the gate.
- **FM:** the pruner deletes through a link, another user's data, or an entry swapped between the folder test and the removal.
  - **Mitigation:** I-5 (Delivery cleanup's link test, owner check, known files only, a per-file re-check with containment, no `rmtree`). The tests, through the `before_remove` seam:
    - no symlink needed: replace a known file with a FOLDER of the same name (kept), and rename a known file to an unknown name (kept);
    - a folder link in place of a session folder at the folder-test stage (kept);
    - through the seam, the session folder itself swapped for a folder link after the folder test: rename it away and create the link at its path. This tests the re-check clauses "the folder must still not be a link" and "real path's parent equals the folder's". Kept, and nothing in the link's target is deleted. It needs no privilege, so it runs even where `os.symlink` on a file is refused;
    - a file symlink swapped in, run only when `os.symlink` succeeds. When the OS refuses (Windows without Developer Mode or admin), print `SKIP: file symlink refused by the OS (needs Developer Mode or admin)`. This is the pattern of `test_working_agreements.py:1562-1571`;
    - a foreign file (kept) and a young folder (kept).

    **Folder link per platform:** on Windows `mklink /J` (a junction, no privilege). On POSIX, `os.symlink(target, link, target_is_directory=True)` (no privilege). Both are run; neither is Windows-only.

    **Skip bucket:** the custom runners (`test_codegraph_first_guard.py:52-59`) have only PASS and FAIL. Add a third list, `SKIPPED`, with a `skip(name, reason)` helper. The summary line prints `N passed, M failed, K skipped`. A skip never fails the run, and it is never counted as a pass.

    No test uses `is_junction`.
- **FM:** the session folder is planted as a link to open the gate.
  - **Mitigation:** step 0 never reads a linked folder, and allows only with a logged reason. The planter could equally read the files through the shell.
- **FM:** the guard's copy of the server rule, or the ownership rule, drifts from the installer.
  - **Mitigation:** parity tests over shared fixtures.
- **FM:** old installs cannot take the fix.
  - **Mitigation:** released hashes, the uninstall-then-install route, and the README upgrade note (JOURNAL 2026-10-22).
- **FM:** the permission insert corrupts `settings.json`.
  - **Mitigation:** Preview-hash apply. A test shows the other bytes are unchanged and a second run adds nothing.
- **FM:** `--check` passes on an unreadable layer.
  - **Mitigation:** exit 2.
- **FM:** a stale ownership cache keeps failing open after an index is built.
  - **Mitigation:** this fails toward reading, the next session re-checks, and the install skill says to start a new session.

## Open Questions for User

Defaults are assumed if unanswered.

- [x] **Q1. Subagent policy.**
  - The live trial verified that a subagent's payload carries `agent_id` and `agent_type`.
  - Options: fail open for every subagent (recommended: the issue reports subagents do not get the tools, and the rule needs no agent-file lookup), or only for one whose agent definition (found by `agent_type`) lacks the `mcp__codegraph__*` grant.
  - A subagent shares its parent's marker, so after the parent calls CodeGraph the subagent's reads pass anyway.
  - **Answered 2026-11-05: (a) every subagent lets reads through (the recommendation).**
- [x] **Q2. Registries.**
  - Recommended: edit only the tool-name and sentinel spans of `MECHANISMS.md:15, 92-96` and `VOCABULARY.md:13-16` in place, and append dated corrections.
  - The alternative is to exempt the registries from the scan, which keeps wrong names in the seed copied into new projects.
  - **Answered 2026-11-05: edit in place with dated corrections (the recommendation).**
- [x] **Q3. "A tool the installed server does not offer".**
  - Recommended: the static rule, where any per-tool name is a finding.
  - The alternative is a live probe through the CLI, as a follow-up.
  - **Answered 2026-11-05: the static rule (the recommendation).**
- [x] **Q4. Install writes the permission entry.**
  - Recommended: yes, inside the preview and plan hash, and kept on uninstall.
  - **Answered 2026-11-05: yes; the permission entry is kept on uninstall (the recommendation; the user said "keep the permission entry").**
- [x] **Q5. Escape scope.**
  - Recommended: per call, single use, until the next prompt.
  - **Answered 2026-11-05: per call, single use (the recommendation).**
- [x] **Q6. Acceptance criteria 1 and 2 when unavailability cannot be proven.**
  - The brief says reads "are allowed". A background main session cannot be told apart from a session that has CodeGraph. The trial found only `CLAUDE_CODE_ENTRYPOINT=sdk-cli`, which every `claude -p` run carries, tools or not. Under this contract such a session gets block-then-retry: one extra round trip per new source call, never a wall.
  - Subagents are covered by step 3 (verified).
  - **Recommended (a):** accept that narrowing, and meet the criteria literally only where unavailability is proven.
  - **(b):** fail open when `CLAUDE_CODE_ENTRYPOINT` is `sdk-cli`. Every `claude -p` session would then skip the guard, even with CodeGraph attached.
  - **(c):** fail open on everything, which removes the guard.
  - **Answered 2026-11-05: (a) block, then retry (the recommendation).**
- [x] **Q7. Index that belongs to another working tree (`index-other-tree`).**
  - The plugin's default flow works in linked worktrees, and a worktree normally has no index of its own. With this reason, every source read in such a worktree is allowed (with one logged line per session), even though the CodeGraph server is attached and answering from the main checkout's index. The guard is then effectively off there, and acceptance criterion 3's positive control holds only in main-checkout sessions and in worktrees that own an index.
  - The case for it: the main index lacks the branch's changes, so "ask CodeGraph first" points at stale answers for exactly the files being changed.
  - **Recommended (a):** keep it as a fail-open reason (the user brought it into scope). The install skill offers to build a worktree-local index, which brings the gate back in that worktree.
  - **(b):** make it a notice only. The gate stays, and the block message says the index belongs to the main checkout and names `codegraph init -i`.
  - **(c):** drop the reason and keep only the installer note (acceptance criterion 11).
  - **Answered 2026-11-05: (a) keep `index-other-tree` as a reason to let reads through (the recommendation).**
- [x] **Q8. The review runs inside `/flow`'s reviewer step, not as a second handoff block.**
  - A second block (a review gate) would make this a two-block contract under the Parent Branch Delivery Rule: a parent branch, sub-issues and a landing, for a bug fix.
  - **Recommended: yes**, review in `/flow`. The alternative is a review block run by the `fullstack-code-reviewer` agent, whose artefact goes to `.claude/reviews/2026-11-05-codegraph-guard-fail-open/t2-review-fullstack-code-reviewer.md`, with a parent branch.
  - **Answered 2026-11-05: yes, review inside `/flow`, single block (the recommendation).**

## Critique (rounds 1 and 2, moved)

Rounds 1 and 2 were resolved and moved on 2026-11-05 to `.claude/contract-history/2026-11-05-codegraph-guard-fail-open.round-1.md` and `.round-2.md`.
Round 1: 2 blockers (a missing test file; acceptance criteria 1-2 narrowed). Round 2: 1 blocker (criterion 5 narrowed by the undecidable case). All were addressed in the body above.

## Revision history

- **Revision 2** (round 1):
  - `test_worktree_path_guards.py` added to the block.
  - Q6.
  - Server project paths.
  - The reach table and the scan.
  - I-5 and step 0.
- **Revision 3** (round 2):
  - Criterion 5 handled by the Index search set.
  - The fixture tree-kind correction.
  - Q7.
  - Home isolation.
  - The live-trial results.
  - The pruner's per-file re-check.
  - The NITs.
- **Revision 4** (round 3):
  - "Project index" means `.codegraph/codegraph.db` everywhere, with decoy tests.
  - The home isolation moves to `codegraph_env()`, so task G still guards the other three guards.
  - The pruner uses Delivery cleanup's link test (no `is_junction`), a `before_remove` seam, privilege-free swap tests and a symlink skip rule.
  - The inline `gitdir:` candidate covers a worktree outside the main folder under fallback mode.
  - Q8.
  - The Non-Goal points at #261.
  - The response tables are trimmed.
- **Revision 5** (round 4, and the user's answers):
  - Q1-Q8 answered.
  - `worktree_own_root` is defined in one place, with relative `gitdir:` handling.
  - Isolation for `test_codegraph_first_guard.py`, and the file named for each new test.
  - A skip bucket, the folder-link test per platform, and the seam test for the folder-link re-check.
  - The server-form evidence is recorded.

## Lessons referenced

- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures**: heeded by the per-suite fixture list and positive controls.
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them**: heeded by the TASK block's suite-by-suite list.
- **2026-10-15 — A script that reads a project-owned file must be told which project**: heeded by Server project paths.
- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work**, and **2026-10-05 — Count a host's size cap… prove with a real trial**: heeded. The live trial ran before the tests were frozen; the unestablished permission form keeps a fallback.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case**: heeded by the corrected fixture-tree bullet and the `commondir` control.
- **2026-10-05 — A documented "missing file means the default" must read one named location only**: heeded by the fixture home folder and the decoy test.
- **2026-10-15 — Locate a script from the plugin root…** and **A skill that edits a block pinned by a lookup-block test must name that test**: heeded in the `/verify-before-done` Extension Point.
- **2026-10-17 — Git for Windows lists files beneath an untracked junction**: heeded by I-5 (per-file re-check) and step 0.
- **2026-10-28 — State the real trigger of a hook, not the printing condition**: heeded by the `hooks.json` cost text, which includes the reset hook.
- **2026-11-02 — After amending a contract, update every summary of the block graph**: heeded in Confidence and the Revision history.
- **2026-10-04 — Detect an install mode by what the sync actually delivers** and **A root locator can return the consumer itself under vendoring**: heeded by the Project index definition (`codegraph.db`, not a folder name that `~/.codegraph` also has), with decoy tests.
- **2026-11-02 — A rule titled 'every' must list every line it covers**: heeded by the reach table and the scan.
- **2026-10-04 — Check a documented guard behaviour against the guard's code**: heeded by the VERIFIED citations and the removal of the shell advice.
- **2026-10-22 — Describe a broken install by the rows each install age really has**: heeded by the upgrade note and the released hashes.
- **2026-10-28 — Guard messages must use names the guard emits**: heeded by I-2.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam**: heeded. Everything is an extension.
- **2026-10-28 — A new term's definition must be true against every existing member**: heeded. The Retry escape is scoped to this guard.
- **2026-11-02 — Describe a fixer a skill runs by everything it writes**: heeded by the permission entry in the preview and the uninstall's kept list.
- **2026-11-02 — A revision that adds a path adds its failure modes**: heeded. The new reason, step 0, the pruner and the server paths each have a failure mode.
- Orthogonal to north-stars: none active (`.claude/north-stars/` does not exist).

---

## Approval addendum (binding)

Added by the main session at approval, 2026-11-05, to close the round-5 findings. The implementer treats these as part of the contract.

1. **Non-git projects (round-5 WARN 2).** `worktree_own_root(path)` returns `(None, None)` when no folder up the path has a `.git` entry, or when it cannot read the `.git` file. A readable `.git` FILE with no `gitdir:` line returns `(F, None)` and is treated as an undecidable tree. The caller must test `root is None` BEFORE calling `tree_kind` or `main_checkout_root`, and must never pass `None` to either. For `root is None` the index-ownership rule uses only the Project index search (rule 1, `no-index`), never rule 2. Add unit rows: no `.git` anywhere, an unreadable `.git` file, and a `.git` file with no `gitdir:` line. I-1's non-git positive control must still block when a Project index exists and the server is configured.
2. **Older helper beside newer scripts (round-5 WARN 1).** `_claude_paths.py` must not make a bare `_pp.worktree_own_root` call. Follow `_claude_paths.py:69-86`: look the name up with `getattr`, and when it is missing fall back to an inline copy of the same walk. Add `worktree_own_root` to `__all__` (checked by `test_installed_plugin_root.py:248`). `_launcher_api` in the installer must not crash on a missing name: the installer treats a missing helper as "undecidable", refuses nothing for it, and prints one plain note. Add a test where the scripts sit beside an older `_project_paths.py` without the function.
3. **Isolated temp folder for in-process rows (round-5 NIT).** The in-process rows in `test_codegraph_first_guard.py` that call `guard.decide` (including the `#612-C` block that writes a ticket) must also run with `TMP`/`TEMP` pointed at the fixture temp folder.
4. **Mechanism registry (round-5 NIT).** Update `MECHANISMS.md:43` (two-layer path resolution) to list `worktree_own_root`, and put the helper's own unit rows in the mechanism's own test file as well as `test_codegraph_first_guard.py`.
5. **Size (round-5 WARN 3).** The contract is over its 12,000-token budget. Round 4 has been moved to `.claude/contract-history/`. The one-line shrink of the answered Open Questions is left as a documentation clean-up for the reviewer step; it changes no decision and blocks nothing.

### Addendum 2 — review-round amendments (main session, 2026-11-05, after the user's "Go" and the review passes)

6. **`.claude/hooks/_error_log.py` is also in Files to touch.** `log_event` returns True when it wrote a record and False otherwise, so the guard can create the once-per-session flag only after a record landed. Callers that ignore the return value are unaffected; an older copy returning `None` is treated as "written". Justified by the code reviewer's second pass.
7. **Pointer hops.** A `gitdir:` or `commondir` target that is a UNC or device path is refused (undecidable) unless it names the same host as the tree's own path, at EVERY hop, before any check on disk and again after `realpath`, with a 4096-byte cap and strict UTF-8, in `worktree_own_root`, `_git_file_kind`, both inline copies, and on the caller side (the guard's `_main_candidate` and the installer's `main_candidate`) so an older helper cannot reopen it. The marker rule ("contains `/.git/worktrees/` or `/.git/modules/`") applies ONLY in `worktree_own_root` and its inline copies, NOT in `_git_file_kind` or `tree_kind`: worktrees of a bare repository and `--separate-git-dir` checkouts keep their original classification (`linked-worktree`, `main-checkout`). Regression rows: a bare-repository worktree reads `linked-worktree`; a separate-git-dir checkout reads `main-checkout`; a `_main_checkout_guard.decide` Write in a bare-repository worktree is allowed.
8. **Pruner.** `KNOWN_FILE_RE` includes the `.tmp-<16 hex>` atomic-write siblings, with a test row.
9. **Grant grammar.** The prerequisite server name must match `[A-Za-z0-9][A-Za-z0-9_-]*` with no `__`.
10. **Held for the user (not implemented):** the Windows owner check or per-user parent for session folders, and turning `codegraph-tool-named` from a refusal into a finding.

### Addendum 3 — third review round (user: "fix and continue", 2026-11-05)

11. **Normalise, then check.** Every host check (`_remote_host` / `_hop_allowed`, four textual copies: helper, guard, bridge, installer) judges the text AND `os.path.normpath(text)`, and refuses any `..` segment inside a UNC or device path. The `commondir` join in `_git_file_kind` is normalised before the check. The string that is checked is the string that is opened.
12. **Same-host rule, amends item 7.** The allowed host set comes from BOTH the written form and the `os.path.realpath` form of the tree's own path (a mapped drive resolves to `\\server\share`; both count), and the `commondir` hop is judged against the folder it hops from. A device-form own path (`\\?\C:\...`, `\\?\UNC\host\...`) is judged by its drive or host: a local drive is not remote. A mapped-drive repository with a worktree on another volume, and a tree opened through `Z:` whose `gitdir:` is recorded as a UNC path, therefore stay decidable (they read as HEAD read them).
13. **Older helper.** The guard binds `tree_kind` and `main_checkout_root` from the helper only when the helper carries the hop refusal (`_hop_allowed` is callable), mirroring the installer's `WORKTREE_OWN_ROOT_NATIVE` gate. With an older helper `index-other-tree` cannot fire (already the documented behaviour). Tests for "an older helper" load the real 0.15.1 `_project_paths.py` pinned to the base commit `643b667` (`git show 643b667:.claude/hooks/_project_paths.py`, checked with `git cat-file -e`; the row skips with a printed reason when that commit is unavailable, for example in a shallow clone) and record probes of a fake host. They must NOT use `HEAD`: once this change is committed, HEAD is the new helper and the fixture would invalidate itself. Lambda stand-ins are not accepted.
14. **Housekeeping.** A table-driven parity row pins the four copies of `_remote_host` / `_hop_allowed`; `MECHANISMS.md:43` gets a dated correction (the full set of `(folder, None)` cases and the new `undecidable` outcomes of `tree_kind` / `main_checkout_root`); `TICKET_RE` in the reset hook escapes the dot of `.tmp-`; the prerequisite server-name grammar becomes `[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9-])?` with no `__`; `.claude/hooks/tests/test_main_checkout_guard.py` is added to Files to touch. `.claude/tdd-scratch-20261105-259.md` is never committed.

## Implementation Handoff

One mergeable block on the brief's branch `fix/259-codegraph-guard-fail-open`, with the patch raise in this pull request and no parent branch. The review runs as `/flow`'s reviewer step rather than as a second block (Q8). The work does not split cleanly: the guard, the fixtures and the installer share the manifest keys and the index-ownership rule.

### 1. Guard, tracker, reset, installer, docs and version (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/addons/codegraph/hooks/codegraph-first-guard.py`
- `.claude/addons/codegraph/hooks/codegraph-turn-tracker.py`
- `.claude/addons/codegraph/hooks/codegraph-turn-reset.py`
- `.claude/addons/codegraph/addon.json`
- `.claude/hooks/hooks.json`
- `.claude/hooks/_project_paths.py`
- `.claude/scripts/_claude_paths.py`
- `.claude/hooks/tests/test_codegraph_first_guard.py`
- `.claude/hooks/tests/test_addons.py`
- `.claude/hooks/tests/test_worktree_path_guards.py`
- `.claude/hooks/tests/_addon_fixture.py`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/tests/test_plugin_text_scans.py`
- `skills/auto-improve-codegraph-install/SKILL.md`
- `skills/auto-improve-codegraph-uninstall/SKILL.md`
- `skills/auto-improve-finish-install/SKILL.md`
- `skills/verify-before-done/SKILL.md`
- `.claude/references/codegraph-decision-table.md`
- `README.md`
- `agents/data-architect.md`
- `agents/contract-critic.md`
- `agents/api-contract-reviewer.md`
- `agents/fullstack-code-reviewer.md`
- `agents/migration-safety-reviewer.md`
- `agents/sql-performance-reviewer.md`
- `agents/test-strategy-critic.md`
- `agents/security-auditor.md`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**Pre-written TASK block:**
```
TASK: Make the codegraph guard fail open on the five unavailability reasons, add the single-use retry escape
(replacing the shell advice), key the turn marker to the session, apply the wildcard rule to every line in the
reach table, extend the installer (permission entry, --check, released hashes, shared index-ownership note),
update docs, raise the version to 0.15.2.
CONTEXT: concept contract .claude/concepts/2026-11-05-codegraph-guard-fail-open.md (Data Shapes, decision order
  0-7, I-1..I-5, reach table, live-trial results); brief .claude/work-items/2026-11-05-259-codegraph-guard-fail-open.md.
FILES: see Files to touch.
CONSTRAINTS:
  - The "Approval addendum (binding)" section above is part of this contract: non-git handling of worktree_own_root,
    the getattr fallback and __all__ for the re-export, isolated TMP/TEMP for in-process rows, and the MECHANISMS.md:43 update.
  - Step 3 keys on a non-empty agent_id (verified). permissions_allow is mcp__codegraph__*; --check accepts
    mcp__codegraph__* or mcp__codegraph. Optionally run the deny-form permission trial in Uncertain Assumptions
    and record the result in the PR.
  - Answers recorded 2026-11-05: Q1 a, Q2 in place with dated corrections, Q3 static, Q4 yes (permission entry
    kept on uninstall), Q5 per call single use, Q6 a, Q7 a, Q8 yes.
  - Add worktree_own_root(path) to _project_paths.py (the Own tree root row) and one re-export line to
    _claude_paths.py. The installer and the guard both take the Caller tree root from it. The guard binds it with
    getattr and keeps an inline copy of the walk (relative gitdir: resolved against the .git file's folder).
  - "Has an index" means a Project index: .codegraph/codegraph.db is a regular file, and neither it nor
    .codegraph is a link. Use this in the guard, the installer note, the fixtures and the tests.
  - Session key, fingerprint and pruner inline in each hook. Index ownership: Index search set first (no-index,
    any tree kind); index-other-tree only through getattr-bound tree_kind / main_checkout_root. The Main
    checkout candidate is main_checkout_root, then the gitdir from worktree_own_root (or its inline copy), then
    _FALLBACK_WORKTREE_MARKER_RE.
  - Pruner per I-5: Delivery cleanup's lstat + S_ISLNK + FILE_ATTRIBUTE_REPARSE_POINT link test, never
    is_junction/isjunction; per-file re-check; once per session; a before_remove(path) seam with a no-op default.
  - Parity tests (in test_codegraph_first_guard.py): the guard's server rule vs _mcp_server_state; the guard's
    ownership verdict vs the installer note; and the guard's inline walk vs _project_paths.worktree_own_root. All
    run over shared fixtures: main checkout, linked worktree with and without its own index in both layouts, an
    absolute and a relative gitdir:, a cwd that is a subfolder of the worktree, a non-git project with and without
    an index, and a server under the main checkout's path only.
  - Codegraph rows isolate the developer's machine through a new codegraph_env(): HOME, USERPROFILE and
    CLAUDE_CONFIG_DIR point at a fixture home folder, TMP and TEMP at a fixture temp folder. base_env stays
    unchanged, so the concept-gate, bash-gate and db-destructive-guard rows keep the real home, and task G
    (snapshot_real_home_logs / assert_real_home_untouched, ~2137/~2170) can still fail for them. Do not weaken task G.
  - Tests that change, and how (keep every guarded state; change only fixtures):
    * test_worktree_path_guards.py (C1-C10, run_fallback_cases, task E, task F, fallback table, stale-helper
      rows ~1552, task 3 ~1981): make_tree plants repo/.codegraph/codegraph.db (an ancestor of wt and wt2) and
      a .mcp.json codegraph entry in repo, wt and wt2. Every fixture tree reads "undecidable", so
      index-other-tree cannot fire. The planted codegraph.db is what stops no-index (~/.codegraph has no
      codegraph.db and does not count). A control proves it: C1 with codegraph.db removed -> allow
      (fail-open:no-index). Codegraph rows use codegraph_env(); run_hook adds a fresh session_id to any payload
      lacking one.
      _write_sentinel/_remove_sentinel become session-folder marker writers for an explicit per-case session_id.
      C5/C6: marker in the case's own session -> allow. C8 is restated: marker only in ANOTHER session's folder,
      plus a legacy <repo>/.claude/.codegraph-used-this-turn file -> block. Add C11: marker written with cwd=repo,
      call with cwd=wt, same session_id -> allow (marker survives a directory change).
      C1, C2, C7, C9, task 3 and the fallback rows stay block (the positive controls).
    * test_addons.py CodegraphAddonTests (lines 277-313, including the codegraph_search/codegraph_node tracker
      payloads at 287-305, which stay as legacy-name coverage): the fixture gets .codegraph/codegraph.db and .mcp.json,
      payloads carry session_id, TMP/TEMP are per test, and sentinel() points at the session folder's turn.json.
    * test_codegraph_first_guard.py run_k4: the same fixture markers and a distinct session_id per
      CLAUDE_SKIP_CG run. run_hook_process (:72-79) stops inheriting the real HOME, USERPROFILE,
      CLAUDE_CONFIG_DIR, TMP and TEMP; it sets them to fixture folders, as codegraph_env() does. Every row in this
      file that reads server state or writes a session folder uses that environment. The runner gains a SKIPPED
      list and a skip(name, reason) helper; the summary prints "N passed, M failed, K skipped", and a skip never
      fails the run. Replace the "shell" needle with the retry-escape wording and assert "cat " and "through
      the shell" are absent. load_hook patches both the marker and availability, so the #612 rows are unchanged.
    * test_auto_improve_finish_install.py (ADDON_SPECS codegraph, install rows) and test_plugin_manifests.py
      (addon_problems): the new keys and the permission insert.
  - New tests, by file:
    * .claude/hooks/tests/test_codegraph_first_guard.py (isolated environment):
      - each fail-open reason (Read, Grep and Glob on .cs and .ts; one log record after two calls);
      - no-index in a non-git folder, in an undecidable tree and under Guard fallback mode, each with a twin
        holding codegraph.db -> block. Each no-index test first asserts that no ancestor of its fixture root
        holds a real codegraph.db, and fails naming the folder if one does. They must pass with the fixture root
        under the system temp folder inside the home folder;
      - a decoy .codegraph WITHOUT codegraph.db (daemons/, telemetry.json) in a parent folder -> no-index still
        fires; the same decoy with codegraph.db -> block;
      - index-other-tree with a real main .git folder, .git/worktrees/<name>/commondir and a worktree .git file,
        in both layouts, cwd a subfolder of the worktree, gitdir: absolute and relative. Rule (2) fires (no
        codegraph.db in the worktree root -> allow); rule (2) does not fire (codegraph.db in the worktree root
        -> block);
      - worktree_own_root unit rows: main checkout; linked worktree (absolute and relative gitdir:); no .git ->
        (None, None); unreadable .git file;
      - a worktree session whose server sits only under the main checkout's path -> gated, with the helper
        bound and under Guard fallback mode, for both layouts;
      - a decoy disabledMcpjsonServers outside the read layers is ignored;
      - a subagent payload (agent_id + agent_type) -> allow; the same payload without them -> block;
      - step 0 with a linked session folder; I-1; the escape is single use and cleared by reset;
      - the tracker for codegraph_explore (with mcp_server in the payload), codegraph_search and
        codegraph_zz_future_tool;
      - pruner tests (the reset hook loaded by importlib) through the before_remove seam:
        . a known file replaced by a same-named folder (kept);
        . a known file renamed to an unknown name (kept);
        . the session folder swapped for a folder link after the folder test (kept; the link's target untouched);
          mklink /J on Windows, os.symlink(target_is_directory=True) on POSIX; no privilege needed;
        . a folder link at the folder-test stage (kept);
        . a file symlink only when os.symlink succeeds, else skip(...) with "file symlink refused by the OS
          (needs Developer Mode or admin)";
        . a foreign file and a young folder (kept);
        . an old known-file folder deleted file by file;
        . once per session.
    * .claude/hooks/tests/test_worktree_path_guards.py: C11 (the marker survives a directory change), the
      C1-without-codegraph.db control, and the fallback-mode row for a worktree outside the main folder.
    * .claude/scripts/tests/test_plugin_manifests.py: the manifest keys; permissions_allow is the wildcard only
      (acceptance criterion 9).
    * .claude/scripts/tests/test_auto_improve_finish_install.py: the permission insert (other bytes unchanged,
      second run adds nothing); --check exit 0/1/2; the codegraph-tool-named refusal; addon-remove deletes a
      released old copy; the preview index notes (main checkout, a worktree under .claude/worktrees, a worktree
      outside the main folder with a relative gitdir:, no index, and a .codegraph without codegraph.db).
    * .claude/scripts/tests/test_plugin_text_scans.py: the scan.
  - /verify-before-done uses the standard lookup block (see Extension Points); test_skill_script_lookup.py runs
    under unittest discover.
  - Scan per the contract (prefixed and bare legacy names; two exempt test files; planted controls; the
    agents tools-line assertion).
  - Registries per Q2's answer; README "Changed in 0.15.2" and the upgrade route with rows per install age.
  - Raise all five version entries; run py -3 .claude/scripts/check_version_bump.py.
  - Run py -3 .claude/hooks/tests/test_codegraph_first_guard.py, py -3 .claude/hooks/tests/test_addons.py,
    py -3 .claude/hooks/tests/test_worktree_path_guards.py and
    py -3 -m unittest discover -s .claude/scripts/tests -p "test_*.py"; all must pass.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-05-codegraph-guard-fail-open.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

- [ ] Implementation matches Data Shapes exactly — no structured evidence
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced) — no structured evidence
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md` — no structured evidence
- [ ] New vocabulary terms promoted to `VOCABULARY.md` — no structured evidence
- [ ] Integration surfaces reflected on both sides — no structured evidence
- [ ] `INTEGRATION.md` updated if new surfaces were introduced — no structured evidence
- [ ] No orphaned DTO/model mismatches — no structured evidence
- [x] `Status` flipped to `implemented`

---

## Critique (round 3, moved)

Round 3 was resolved and moved on 2026-11-05 to `.claude/contract-history/2026-11-05-codegraph-guard-fail-open.round-3.md`. It found 1 blocker (the no-index search counted `~/.codegraph`, which holds no `codegraph.db`), 2 warnings and 4 nits. All were addressed in revision 4.

## Critique (round 4, moved)

Round 4 was resolved and moved on 2026-11-05 to `.claude/contract-history/2026-11-05-codegraph-guard-fail-open.round-4.md`. It found 0 blockers, 2 warnings (the worktree-ownership rule could never fire; one test file used the real home and temp folder) and 7 nits. All were addressed in revision 5.

## Critique (round 5)

**Critic:** contract-critic
**Date:** 2026-11-05
**Verdict:** warnings-only

I checked Revision 5 against the repository. The round-4 Caller-tree WARN is resolved in substance. With `root = worktree_own_root(cwd)[0]`, a linked worktree's own folder is the root. `tree_kind(root)` walks to the worktree's `.git` file and returns `linked-worktree` when `commondir` exists (`_project_paths.py:571-579`). `main_checkout_root(root)` returns `dirname(realpath(common))`, which is the main folder (`:576, 579`). So root and main now differ, and rule (2) fires when only the main folder holds `codegraph.db`. It does not fire when the worktree root holds one too. For the layout under `<main>/.claude/worktrees/<name>`, the main folder is an ancestor of the payload `cwd`, so rule (1) cannot pre-empt rule (2). For the layout outside the main folder, the candidate puts the main folder in the Index search set.

Layouts checked by reading the code, not by running it:
- **Submodule `.git` file** (`gitdir: ../.git/modules/x`): no `commondir`, so the kind is `main-checkout`. Candidate (b) does not match `/.git/worktrees/`. Rule (2) cannot fire.
- **Bare-repository worktree** (`…/repo.git/worktrees/x`): candidate (b) does not match. `main_checkout_root` returns the bare folder's parent, which normally holds no index, so the verdict is `index-present`. This fails toward gating.
- **`gitdir` pointing at a missing folder**: `worktree_own_root` still returns the text, so candidate (b) applies. This matches the legacy-fixture sentence in candidate (b).
- **Windows drive or case differences**: they only add duplicate members to the Index search set or extra cache keys. No verdict depends on comparing path text.

Stale-helper behaviour on the guard side is safe. The guard already binds `checkout_equivalent_path` with `getattr` (`codegraph-first-guard.py:45-53`). `tree_kind` and `main_checkout_root` predate this release, so a missing `worktree_own_root` falls to the inline copy, and rule (2) still fires there.

`_project_paths.py` has a single copy in the worktree. No byte-identical mirror exists. The suites that build an "older release" file derive it from the current file (`test_auto_improve_finish_install.py:4490-4495`, `test_plugin_doctor.py:1249-1255`). `test_gate_cost.py:69-70` pins the file at a fixed commit. The one patch raise in Files to touch covers the new file content. The `SKIPPED` bucket is feasible: the runner is a plain accumulator (`test_codegraph_first_guard.py:49-59, 177-178`).

### Findings

- **[WARN] The re-export is a bare attribute read, so a scripts copy beside an older `_project_paths.py` crashes at import with AttributeError instead of degrading**
  - **What is wrong:** The contract adds "one re-export line" (`worktree_own_root = _pp.worktree_own_root`). `_claude_paths.py:69-86` exists because a `_project_paths.py` from an earlier release "imports cleanly and lacks them, so a bare attribute read below would raise AttributeError, which the callers that guard this import (they catch ImportError) would not catch". The callers are `_launcher_api` (`auto_improve_finish_install.py:118-121`, which catches only `ImportError` and `SystemExit`) and the doctor's three callers (`test_plugin_doctor.py:1237-1241`). Helpers are copied "only when the project lacks it" (`test_auto_improve_finish_install.py:3525`). So a project holding a 0.15.1 `_project_paths.py` (which has the launcher names) next to 0.15.2 scripts would now raise AttributeError from every script that imports the bridge. Today the same copy works or refuses cleanly. The contract does not add `worktree_own_root` to the missing-name check, and it does not say the installer reaches the function through the `ImportError`-guarded path.
  - **Prior artifact ignored:** `MECHANISMS.md:43` (Two-layer Claude path resolution: "a missing resolver raises `ImportError`"); `.claude/scripts/_claude_paths.py:69-86` (the launcher-surface precedent, Revision 19).
  - **Where in this contract:** `## Data Shapes → Value Objects`, Own tree root: "the installer imports it through a re-export line in `.claude/scripts/_claude_paths.py`". `## Reused Mechanisms`: "plus one re-export line in `_claude_paths.py`".
- **[WARN] The Caller tree is undefined when `worktree_own_root` returns `(None, None)`, and that is the non-git project, one of I-1's positive controls**
  - **What is wrong:** The Own tree root row returns `(None, None)` when no `.git` entry exists up to the filesystem root, which is every non-git project. The Caller tree row then sets `kind = tree_kind(root)` and `main = main_checkout_root(root)` with `root = None`. `_classify` calls `os.path.abspath(None)`, which raises TypeError, and its handler catches only `(OSError, ValueError)` (`_project_paths.py:586-604`). The contract does not say what `kind`, `main` or rule (2)'s "Caller tree root holds no Project index" mean for a `None` root. Taken literally, the guard reaches I-4 ("an internal error allows"). Then I-1's control "with an index present (… a non-git project …) … the first source call blocks" fails. The parity fixtures ("a non-git project with and without an index") would expose this, but the implementer would have to invent the rule. The row also does not define the return value for a `.git` file that can be read but has no `gitdir:` line (or an empty one). `None` in the second slot already means ".git is a folder". The unit rows cover "unreadable" only.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case"; `MECHANISMS.md:43` (tree classification returns `outside-repository` for this case, not an error).
  - **Where in this contract:** `## Data Shapes → Value Objects`, Caller tree: "`root` = `worktree_own_root(cwd)[0]` … `kind` = `tree_kind(root)`". Own tree root: "Return `(None, None)` when no `.git` exists up to the root or the file is unreadable".
- **[WARN] The contract is about twice its budget, and the template's shrink rule for resolved questions is not applied**
  - **What is wrong:** The Read tool measured the 671-line file at about 28,000 tokens, including line-number prefixes. Without round 4 (lines 618-671, about 4,000 tokens) and the prefixes, I estimate the body at roughly 22,000-24,000 tokens against `**Budget:** 12,000 tokens`. This is an estimate: I counted no characters and did not run `memory-health.py`. The template says "resolved questions shrink to one line each (the question, and the answer with its date)". Q1-Q8 are all answered, but they still carry their option lists (lines 335-375). Revision 5 has also answered round 4, but round 4 is still inline.
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md:22` (Budget rule).
  - **Where in this contract:** `## Open Questions for User` Q1-Q8; `## Critique (round 4)`.
- **[NIT] `__all__` is not mentioned.** The bridge lists every re-export in `__all__` (`_claude_paths.py:120-145`), and `test_installed_plugin_root.py:248` asserts a new name appears there. "One re-export line" understates the change. `## Reused Mechanisms`.
- **[NIT] The unit rows for `worktree_own_root` go in the guard's suite, not in the mechanism's test file.** `MECHANISMS.md:43` names `test_worktree_path_guards.py` as the tree-classification tests. Nothing in Extension Points records the new function in that entry, as its own "Extend by" and the 2026-10-31 correction did for `installed_plugin_root`. TASK block, "worktree_own_root unit rows"; `## Extension Points`.
- **[NIT] The in-process rows in `test_codegraph_first_guard.py` still write to the real temp folder.** `run()` calls `guard.decide` in the test process. That process has the real `TMP` and `HOME`, and `tempfile` has already cached its temp folder at `:109`. The `#612-C` control is a block, so step 7 writes a ticket into a real `auto-improve-codegraph-cwd-<hash>` folder. "load_hook patches both the marker and availability" does not cover the ticket write. This contradicts "Every row in this file that reads server state or writes a session folder uses that environment". `JOURNAL.md` 2026-10-05 "missing file means the default must read one named location only". TASK block, `test_codegraph_first_guard.py` bullet.
- **[NIT] Two sentences still read as if the questions were open.** Step 3 says "Q1 decides the policy", and step 4 says "`index-other-tree` (subject to Q7)". Both are answered (Q1 a, Q7 a). `JOURNAL.md` 2026-11-02 "Edit a reversed sentence where it stands". `## Data Shapes → Guard decision order`.

### Applicable journal entries

- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case**: heeded for absolute and relative `gitdir:`, a missing `.git` and an unreadable file. Violated for a readable `.git` file with no usable `gitdir:` line and for the `None` root (WARN).
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures**: heeded. `run_hook_process` isolation was added. The in-process rows are a NIT.
- **2026-10-05 — "missing file means the default" must read one named location only**: heeded for the subprocess rows; the in-process rows are a NIT.
- **2026-11-02 — Edit a reversed sentence where it stands**: heeded for the round-4 Revision-history NIT. Still open for the step 3 and step 4 sentences (NIT).
- **2026-10-22 — An accepted critic WARN must amend the contract body**: heeded. Both round-4 WARNs are carried into Data Shapes, FM 1 and the TASK block.
- The other entries in `## Lessons referenced` are heeded as stated.

### What the critic did not check

- **Checked and found consistent with Q1-Q8:** permission entry kept on uninstall (Commands, Non-Goals, uninstall Extension Point); Q2 in-place edits (reach table); Q6 (a); Q7 (a); Q8 single block. The hidden-tell grep finds nothing in the body. There is one mergeable block, the `**Work Item Brief:**` header is present, and the brief file exists.
- **Not run (no shell):** any test, `memory-health.py`, `pr_merged.py --status`, `derive_area.py`, and an exact character count. The budget figure is an estimate.
- **Not checked:** whether the core hooks install (not the add-on) refreshes an existing `_project_paths.py` on upgrade. That decides how often the mixed-release case in WARN 1 occurs in practice.
- **Tools:** no CodeGraph tool was available. Symbols were checked with Grep and Read.
