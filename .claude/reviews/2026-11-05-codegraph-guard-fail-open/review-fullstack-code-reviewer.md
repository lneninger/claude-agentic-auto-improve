# Review: fullstack-code-reviewer — 2026-11-05-codegraph-guard-fail-open (#259)

- **Contract:** `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` (approved, with the binding addendum)
- **Scope:** production code, manifests, docs and registries in the uncommitted working tree against HEAD `643b667`. The tests are reviewed by another reviewer.
- **Method:** I read the full contract, then read the three hooks, the helper and bridge diffs, the installer diff, the manifest, `hooks.json`, every skill, the README, the decision table, the agents and the registries. I also ran two probes outside the repo (in `%TEMP%\rv259probe`, against an isolated `TMP`/`HOME`):
  - the guard's decisions over: a non-git project; a linked worktree outside the main folder with a relative `gitdir:` and `commondir`; a worktree with its own index; a server present only under the main checkout (helper bound and in fallback mode); the session folder being a file; a subagent; an empty `agent_id`; upper-case `cwd`; a `.git` file with no `gitdir:` line; reordered Grep keys; a disabled server; no `cwd`;
  - `_splice_rows` with the permission entry, over five `settings.json` shapes (including CRLF and a compact single line).
- **Verdict:** `FIX THEN SHIP`. No blocker. One WARN (exit code 3 from `--check`, which the docs never mention) and eight NITs.

## Probe results (the guard)

| Case | Result | Expected |
|---|---|---|
| Non-git project, index and configured server: first, retry, third call | block / `retry-escape-used` / block | I-1 positive control, single use |
| Same session, different file | block | ticket is per call |
| Different session, same call | block | ticket is per session |
| Linked worktree outside main, relative `gitdir:`, `cwd` a subfolder | `fail-open:index-other-tree` | rule (2) fires |
| Same worktree with its own `codegraph.db` | block | rule (2) does not fire |
| Server only under the main checkout, `CLAUDE_PROJECT_DIR` = worktree (bound, then `main_checkout_root` unbound) | `configured` both times; candidate (b) gave the main folder | gate stays |
| Session folder is a file | `fail-open:state-unwritable` | step 0 |
| `agent_id: "x"` / `agent_id: ""` | allow subagent / block | step 3 keys on non-empty |
| `cwd` upper-cased (Windows) | block | no verdict depends on path case |
| `.git` file with no `gitdir:` line, index and server | `(F, None)`, block | addendum 1 |
| Grep, same input with keys in another order | `retry-escape-used` | canonical JSON |
| `disabledMcpjsonServers` in `settings.local.json` | `fail-open:server-disabled` | step 5 |
| No `cwd` in payload, `CLAUDE_PROJECT_DIR` set | block | Caller tree falls back to the variable |

The helper's `worktree_own_root` and the guard's inline copy returned identical tuples. The three copies of the walk (helper, guard, bridge) are textually identical.

`_splice_rows` with `allow_add=["mcp__codegraph__*"]` gave the right result in all five shapes: no `permissions`; an empty `allow` beside `deny`; an existing CRLF list (CRLF kept, item appended); `permissions` without `allow` (compact style kept); `{}`. Second runs add nothing, because `_plan_settings_edit` moves the entry to `allow-listed`.

## Check by check

1. **Decision order 0-7, I-1..I-5, fail-open on internal error.** Implemented as written (`codegraph-first-guard.py:712-767`). Every exception escapes `evaluate` to `main`'s `except Exception` and exits 0 (`:918-925`). Other exits also allow: ticket write failure (`:762-763`), an unusable folder (`:719-720`), and a `log_event` failure inside `block()` (raises before `sys.exit(2)` and is caught). The block message (`:842-858`) meets I-2: it names no single tool, has no `cat`, no "shell", no `CLAUDE_SKIP_CG` and no `references/` path. No kill switch (I-3). The reset hook (I-5) uses Delivery cleanup's link test, the owner check, known names only, a per-file re-check with real-path containment, `os.rmdir`, the `before_remove` seam, and runs once per session through `pruned`.
2. **Safe direction.** Every doubt path allows, except the ones the contract deliberately biases toward the gate: server `configured` if ANY path says so; an unapproved `.mcp.json` server counts as configured (Q6 accepted block-then-retry). The positive controls still block (probes above).
3. **Retry ticket.** Its name is `ticket-<sha256(tool_name + canonical JSON)>` inside the session's own folder, so it cannot open a different call or a different session. It is deleted on use, before the allow is returned (`:753-756`), and deleted by the reset hook at the next prompt. Forging one needs a write into the user's own 0700 temp folder, which only buys a read the agent could already make. The contract accepts this.
4. **`worktree_own_root` / inline copy.** Identical code. `None` root is tested before `tree_kind` (`:441-442`; installer `:341-342`). Relative `gitdir:` is resolved against the `.git` file's folder. A submodule (`.git/modules/x`) does not match candidate (b) and reads `main-checkout`, so rule (2) cannot fire. Windows case is folded wherever two paths are compared (`_norm_path`, `normcase(realpath)`).
5. **Installer.**
   - The permission insert is a text splice inside the same plan hash. It runs through the existing three-way check in `_splice_rows`: strict parse, equality with the in-memory merge, and removal of the inserted ranges gives back the original. It is idempotent.
   - `--check` exits 0 or 1 correctly, but can exit **3**, not 2 (WARN-1).
   - The refusal lists every entry and file.
   - The released-hash removal compares folded hashes, so an edited copy is `kept-differs` (`_classify_file`).
   - Released hashes: I recomputed the folded SHA-256 of every committed add-on version. All four (guard ×2, reset, tracker) match `addon.json`.
6. **Wildcard only.** `git grep` finds no prefixed or bare legacy tool name in any shipped production file, skill, agent, registry or reference. The only hits are in tests, which are the other reviewer's scope. No shell-route advice is left in the add-on, the skills, the agents, the references or the registries. The single "edit the row through the shell" at `README.md:563` is the existing missing-hook-file route, not read advice.
7. **Docs vs behaviour.** They match, except for the `--check` exit code (WARN-1) and the NITs below.
8. **Contract divergence and the four stated deviations.**
   - *`WORKTREE_OWN_ROOT_NATIVE` flag* (`_claude_paths.py:148-153`). Justified. Addendum 2 asks the bridge to fall back to an inline copy AND asks the installer to treat a missing helper as undecidable. Those two contradict unless the bridge says which one it gave. This is a contract defect, recorded in JOURNAL (see Janitor). The result is that the bridge's inline copy has no consumer and no parity test (NIT-3).
   - *Refusal scope* (any layer, any manifest grant ending `__*`, `_named_tool_findings`). Justified. The contract's Commands row says "listing each entry and layer". The generic `__*` rule only ever fires for codegraph today.
   - *Project-layer-only insert* (`_plan_settings_edit` reads `listed` from the project file only). Justified and harmless. An entry already in the user or local layer is still written to the project file, which is the committed layer the install owns. `--check` reads every layer, so it does not care.
   - *Hook prose rewording.* Acceptable on content (I-2 is met), but the retry sentence repeats its own condition (NIT-1).
9. **Janitor.**
   - MECHANISMS: the Add-on layout and CodeGraph amendments cover the new keys, `--check` and the Retry escape. The Retry escape stays unpromoted, as the contract decided.
   - VOCABULARY: **Project index** was the contract's load-bearing term ("the ONLY meaning of 'has an index' anywhere") and was missing. I appended it.
   - JOURNAL: I appended one post-impl-divergence entry (the addendum contradiction).

Off-area drift check: `.claude/area-mapping.json` has an empty `areas` object, so no file maps to an area and nothing can drift. Every changed production file is in the contract's `Files to touch`. The untracked `.claude/tdd-scratch-20261105-259.md` is not in that list and must not be committed (NIT-8).

End-User View: not applicable. No Angular UI surface.

---

## Findings

### `.claude/scripts/auto_improve_finish_install.py`

**[WARN-1]: `addon --check` can exit 3, but the contract, the README and `/verify-before-done` all say "2 when it could not check"** — lines 2261-2268 (`check_addon`), 915-931 (`_load_layers`), 182-183 and 3640 (`EXIT_CLASS`)
```python
problem, layers = _load_layers(project, found["home"])
if problem:
    return problem          # project-unreadable -> EXIT_ENVIRONMENT (3)
...
return EXIT_CLASS[result["code"]] if _is_refusal(result) else EXIT_OK
```
**Problem:** These refusals are in `_ENVIRONMENT_CODES`, so they exit 3:
- `project-unreadable`, from a settings layer `_load_layers` cannot read;
- `addon-manifest-missing` and `template-missing`, from `_resolve_addon`.

Three places promise otherwise:
- the contract's Commands row says "exit 2 when it could not check";
- `README.md:93-95` says "2 when a settings layer could not be read";
- `skills/verify-before-done/SKILL.md` Step 5.8 lists only 0, 1 and 2.

An agent that gets 3 has no instruction for it. The step's whole point is that "could not check" is NOT READY, so this is the gap that matters. Only `malformed-settings` and `unexpected-settings-shape` reach 2 today.
```python
# in main(), the --check branch
if args.check:
    result = check_addon(project, args.name, home, provider=args.provider)
...
if result.get("status") == "checked" and not result.get("ok"):
    return EXIT_FINDINGS
if args.command == "addon" and getattr(args, "check", False) and _is_refusal(result):
    return EXIT_REFUSED      # --check: any refusal means "could not check" (2)
```
(Or keep 3 and add "`3`: could not check (environment): NOT READY" to the skill and README. The contract asks for 2.)

**[NIT-2]: `--check` combined with `--apply` silently does only the check** — line 3616. `addon --check --apply --expect-sha256 …` takes the check branch and ignores the apply. Make the two options mutually exclusive in argparse (`add_mutually_exclusive_group`).

**[NIT-4]: Under an older helper the installer withholds even the provable "no index" note** — line 302. `_codegraph_index_notes` returns `UNDECIDABLE_TREE_NOTE` before rule (1). Rule (1) needs no tree helper. The guard (inline walk) would fail open with `no-index` in that project, but the preview says "undecidable". This is addendum-conformant ("treats a missing helper as undecidable"), so it is only a NIT. Running rule (1) first and giving the undecidable note only for rule (2) would keep the guard and the installer in agreement.

### `.claude/addons/codegraph/hooks/codegraph-first-guard.py`

**[NIT-1]: The retry sentence states its condition twice** — lines 849-851
```
"If no mcp__codegraph__* tool is available to you in this session,",
"repeat this exact call once if no CodeGraph tool is available to you;",
"it will be allowed and logged. To remove the guard instead, run",
```
**Problem:** The contract's I-2 phrase was kept verbatim and a second copy of its condition was prepended, so the agent reads "if no tool … repeat … if no tool". Keep the contract phrase alone:
```
"Repeat this exact call once if no CodeGraph tool is available to you;",
"it will be allowed and logged. To remove the guard instead, run",
```
(Any test needle on the I-2 phrase still matches.)

**[NIT-5]: `fail-open:state-unwritable` writes a log record on every call** — line 885. Without a usable folder no `logged-` flag can be created, so every Read/Grep/Glob appends to `errors.jsonl` for the rest of the session. The contract's Notice flag says "at most one per session per reason". A process-local guard cannot help, because each call is a new process. The cleanest fix is to accept it and say so in the docstring and the README's fail-open bullet ("logged on every call, because the guard has nowhere to record that it already did").

### `.claude/scripts/_claude_paths.py`

**[NIT-3]: The bridge's inline copy of the walk has no consumer and no parity test** — lines 114-153. The only consumer, `_codegraph_index_notes`, refuses to use `worktree_own_root` unless `WORKTREE_OWN_ROOT_NATIVE` is true. So `_inline_worktree_own_root` is a third copy of the walk that nothing runs and nothing pins. The guard's copy is pinned by the contract's parity test; this one is not, and `git grep` finds no test that names it. Add it to the guard's parity rows (same fixtures, compare with `_project_paths.worktree_own_root`). Otherwise it will drift unseen until the first caller trusts it.

### `.claude/registries/MECHANISMS.md`

**[NIT-6]: Q2 was "edit the name spans in place and append dated corrections"; line 15's sentinel and bypass text were also rewritten in place** — line 10 of the diff (entry line 15). The reach table says: edit the tool-name span in place, and *append* dated corrections that replace the sentinel and ways-out text. The implementation rewrote `<cwd>/.claude/.codegraph-used-this-turn` and `Bypass: CLAUDE_SKIP_CG=1` in place as well, and also appended the 2026-11-05 amendment. Nothing is wrong today, but the original text the amendment "supersedes" is gone. Restore the sentinel and bypass clauses on line 15 (only the tool-name span changes) and let the appended amendment carry the correction. The same entry still cites `~/.claude/hooks/codegraph-first-guard.py`. That is pre-existing and covered by the 2026-10-31 correction, so it is not this change's finding.

### `README.md`

**[NIT-7]: The upgrade table has no row for the pre-add-on core-hook copies** — the new "Upgrading" table. Before 0.9.9 the guard was a core hook (`.claude/hooks/codegraph-first-guard.py`, commits `6c1404a`, `6ffe46a`), and those folded hashes are not in `released_sha256`. The contract scopes the hashes to "since the add-on was created", so the removal correctly keeps such a copy as `kept-differs`. The README, though, files that case under "a hook file edited by your team", which is not what happened. Add one row: "before 0.9.9 (core hook): kept as `kept-differs`; delete it by hand after the uninstall, then install".

### Working tree

**[NIT-8]: `.claude/tdd-scratch-20261105-259.md` is a scratch file outside `Files to touch`.** Delete it, or leave it out of the commit.

### Not findings (checked and correct)

- `log_event(..., session_id=...)`: `_error_log.log_event` has had the `session_id` keyword since its first commit (`6c1404a`), so an old project helper does not break `announce`.
- `_read_addon_manifest` rejects `released_sha256` keys that are not active hooks and any value that is not lowercase hex.
- `apply_addon` needs `py` / `python3` on PATH only when a row is added (`payload["to-add"]`). A permission-only apply does not.
- The `hooks.json` comment states the real triggers, including the reset hook's once-per-session prune.
- All five version declarations read 0.15.2.

---

## Summary

| Severity | Count |
|---|---|
| [CRITICAL] / BLOCKER | 0 |
| [WARN] | 1 |
| [NIT] | 8 |

**Verdict:** `FIX THEN SHIP`

**Top priority fix:** WARN-1. Make `addon --check` return 2 for every refusal, or document 3 in `/verify-before-done` Step 5.8 and the README, so that "could not check" can never be misread.

## Janitor actions taken

- `VOCABULARY.md`: appended **Project index** (2026-11-05).
- `JOURNAL.md`: appended "A bridge re-export that silently falls back to an inline copy must also say which one it gave" (Trigger: post-impl divergence).
- `MECHANISMS.md`: no append. The implementer's two 2026-11-05 amendments cover the new keys, `--check` and `worktree_own_root`. Only the `WORKTREE_OWN_ROOT_NATIVE` flag is unmentioned; fold it into NIT-3's fix.
- `INTEGRATION.md`: not applicable (no REST, SignalR or DTO surface).
