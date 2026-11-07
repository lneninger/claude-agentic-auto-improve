# Concept Contract — Per-user session folders for the codegraph hooks, and the codegraph-tool-named refusal message (issue #271)

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-06
**Requested by:** user
**Status:** approved
**Supersedes:** none. It amends the session-folder location, decision step 0 (now step 2) and the `codegraph-tool-named` message of `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` (implemented). Everything else in that contract stands, I-4 included (restated below).
**Work Item Brief:** .claude/work-items/2026-11-06-271-session-folder-owner-and-tool-named.md
**Tracking issue:** #271
**Budget:** 12,000 tokens (body; the appended critique is not counted)

> **Protocol:** filled in by `data-architect`. The lifecycle, budget rule and handoff rules are in `.claude/templates/concept-contract.md`. Safety-critical: `/tdd-first` is mandatory and `security-auditor` reviews.

---

## Business Concept

- **What is this thing, in domain language?**
  The `codegraph` add-on's three hooks share a Session folder holding the Turn marker (`turn.json`), Retry escape tickets and small caches. Today it sits in the system temp folder, and on Windows nothing checks who owns it. If `TMP` points at a folder shared between users, another user can plant `auto-improve-codegraph-<victim session>/turn.json` and open the victim's gate, and the victim's pruner can delete another user's folders. This contract:
  1. moves every Session folder under a **Per-user session parent** only the user can write (`%LOCALAPPDATA%` on Windows, a `0700` folder in the user's cache folder on POSIX). Nothing under the system temp folder is read, written or pruned any more;
  2. makes an unusable parent or Session folder **fail closed**, with a message saying why. This reverses step 0 of 2026-11-05 (`fail-open:state-unwritable`): planted state must not open the gate, not even by breaking the folder;
  3. logs once when the gate opens from a **Foreign marker**;
  4. keeps the `codegraph-tool-named` refusal, whose message now names each entry and its layer, plus the one-step way out;
  5. adds one capability constant, a probe-order comment and corrected skill wording.
- **Existing VOCABULARY.md terms that apply:** CodeGraph, Investigation Turn (as amended 2026-11-05), Add-on hook, Add-on manifest, Retry escape, CodeGraph unavailability reason. From MECHANISMS.md: Two-layer Claude path resolution, Guard fallback mode, Delivery cleanup.
- **New terms proposed (Universal tier):**
  - **Per-user session parent:** the one folder under which the codegraph hooks keep Session folders: `<LOCALAPPDATA>\auto-improve-codegraph\` on Windows; `<XDG_CACHE_HOME, or HOME/.cache>/auto-improve-codegraph/` on POSIX, mode `0700`, owned by the user. When it cannot be used, the hooks fail closed.
  - **Foreign marker:** a `turn.json` in this session's folder that does not carry this session's tracker stamp. It still opens the gate, and it is logged once per session.
  - **Amendment to Investigation Turn:** the marker lives in the session's folder under the Per-user session parent, not under the system temp folder.

---

## End-User View

Not applicable. Reason: no Angular UI surface is touched; the change is hook behaviour, installer output and documentation.

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership |
|------|--------|------------|-----------|
| Per-user session parent | path; verdict | Resolved on every hook call from the environment at call time, never at import, so in-process tests can redirect it. A missing parent is created with `0700` (one `mkdir`, never `makedirs`). Windows: the base `%LOCALAPPDATA%` must exist and is never created. POSIX: the base is created with `0700` only when it is missing AND its own parent exists, one level only; a deeper missing chain gives `cannot-create`. No hook uses the system temp folder for a Session folder. | the three hooks (one inline copy each, pinned by a parity test) |
| Session folder (amended) | `<Per-user session parent>/auto-improve-codegraph-<session key>/` | Same contents, key and checks as 2026-11-05 (not a link, a folder, the user's own on POSIX, writable). Only the parent changes. | the three hooks |
| Turn marker (amended) | `turn.json`: `{ts, tool, summary, pid, writer, session}` | The tracker adds `writer` = `codegraph-turn-tracker` and `session` = the Session key. The guard honours any plain-file marker and uses the stamp only to detect a Foreign marker. | tracker |
| Foreign-marker notice flag | `logged-foreign-marker` | At most one record per session. The existing `KNOWN_FILE_RE` (`logged-[a-z0-9-]+`) already matches it. | guard |
| Stateless session | a Session object built when the verdict is unusable | Every read answers "absent" and every write answers False WITHOUT any filesystem call (no `lstat`, `mkdir`, `has_plain_file`, `create_once`, `ensure_folder`). `announce()` and every cache read or write use it, so nothing is created inside or through an unusable folder. | guard, tracker, reset |

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Parent base (pure rule) | Takes the environment mapping and the OS name; returns `(base path, problem)`. It reads ONLY the mapping: no `expanduser`, no `pwd`, no `os.environ`. Windows: `LOCALAPPDATA`. POSIX: `XDG_CACHE_HOME`; when that is unset or empty, `HOME` + `/.cache` (the XDG specification's own default, not a guess chain); when both are unset or empty, `unset`. A set but relative value gives `not-absolute`; it is never skipped to the next name. | Pure, so both OS branches are table-tested on every OS |
| Parent problem (closed set) | `unset`; `not-absolute`; `remote` (Windows; Remote rule); `cannot-create`; `link` (Delivery cleanup's test: `S_ISLNK` or `FILE_ATTRIBUTE_REPARSE_POINT`, never `is_junction`); `not-a-folder`; `foreign-owner` (POSIX: `st_uid` is not `os.getuid()`); `open-mode` (POSIX: `st_mode & 0o077` is not 0); `unwritable`; `check-failed` (any exception, not only OSError, raised while computing the verdict) | The reason printed and logged. The parent gets every check; the base gets only the existence, text and remote rules, because a base that is a junction is legitimate (a moved AppData). |
| Remote rule | Reuses two pinned functions verbatim: `_remote_host` (guard `:374-387`) and `_own_spellings` (guard `:403-407`, the written-then-realpath order); the tracker and reset gain byte-identical copies of both. A base is remote when any spelling `_own_spellings(base)` gives has a `_remote_host` that is not `None` and not the local-drive form `?<letter>:`. The empty host `""` (a device path naming no drive or host, such as `\\?\Volume{…}\` or `\\.\pipe\…`) counts as remote: fail closed. So `\\?\C:\…` is local and a mapped drive that resolves to `\\server\share` is remote. | `remote` problem |
| Session state verdict | `usable`, or `unusable:<Parent problem>`. A Session folder inside a usable parent that fails its own checks gives `unusable:session-<link / not-a-folder / foreign-owner / unwritable / check-failed>`. The verdict function catches `Exception` itself, and takes its file facts from `os.lstat` (so a test can fail it for one path only). | steps 2 and 8 |
| Marker stamp check | `own` when `writer` and `session` match; otherwise `foreign`, cause `missing-stamp`, `other-session` or `unreadable` | step 3 |
| Guard decision (amended) | `fail-open:state-unwritable` is removed. New block reasons: `session-state-unusable` (steps 2 and 8) and `retry-ticket-unwritten` (step 8). | See below |
| Capability constant | `TREE_HOP_REFUSAL = True` in `_project_paths.py`. **Hop proof** (one expression, used by the guard, the bridge and the installer): `getattr(_pp, "TREE_HOP_REFUSAL", False) is True`, OR the 0.15.2 helper's shape, `callable(_hop_allowed)` and `callable(worktree_own_root)`. **Meaning, per module:** in the helper the constant is a declaration ("this file carries the hop refusal"); in the bridge the export of the same name is the Hop proof computed on the helper beside the scripts (True: the bridge uses the helper's native tree functions; False: its inline copies). It says native or inline, not which release of the helper. Today it decides no verdict, because every helper that carries it also passes the second arm; it lets a later helper rename the private `_hop_allowed` without losing `index-other-tree`. `WORKTREE_OWN_ROOT_NATIVE` is removed. | The guard binds `tree_kind` and `main_checkout_root` only on the Hop proof; the bridge picks the native `worktree_own_root` only on it; the installer gives the undecidable-tree note when it fails |
| Tool-named refusal message | One line per finding: `` `<entry>` in the <layer> layer (<file>) ``, layer `user`, `project` or `local` (`_load_layers`). Then: "One step fixes it: replace each entry above with `mcp__codegraph__*`, which covers every CodeGraph tool, including future ones, and run this again." Then "Nothing was written for the codegraph add-on." Code, exit 2 and `findings` unchanged. | install refusal |
| Retry exception sentence (E1) | "Not after a `session-state-unusable` block, which offers no retry. After a `retry-ticket-unwritten` block the retry was not recorded, so the repeat is blocked once more (as `source-target`) and the identical call after it is allowed." | appended to every shipped "repeat the blocked call once" sentence |
| Logging exception sentence (E2) | "While the session folder cannot be used, these lines print on every call and nothing is logged." | appended to every shipped "logged once per session per reason" sentence |

### Guard decision order (amended and renumbered)

The old numbers are in brackets.

1. [1] No target, or only non-source targets → allow. Runs first because it needs no state.
2. [0] Resolve the Session state verdict. When it is `unusable:*`, the guard uses the Stateless session: it skips steps 3 and 7, reads and writes no cache, and runs steps 4-6. A step 4-6 allow prints its stderr line on every call and writes NO log record (no state exists to rate-limit it; this amends 2026-11-05's "once per session per reason" for the unusable state only, and E2 says so wherever that rule is shipped). Otherwise it blocks with `session-state-unusable`, writes no ticket, and logs one `block` record per call. **Per-call cost in this state:** no availability cache can be kept, so every Read, Grep and Glob on a source target recomputes both verdicts: two `lstat` calls per ancestor of the cwd and of `CLAUDE_PROJECT_DIR` for the index, the `.git` reads of the tree classification, and the JSON reads of the server layers. No subprocess, no host beyond the 2026-11-05 same-host rule. Accepted: the state is a fault the message tells the user to fix.
3. [2] The Turn marker is a plain file → allow (`turn-marker-present`). On a `foreign` stamp, also log once (see Events).
4-6. [3-5] The proof steps (`subagent`, `no-index` / `index-other-tree`, `server-not-configured` / `server-disabled`), unchanged.
7. [6] A ticket matches the call → delete it, allow (`retry-escape-used`), unchanged.
8. [7] Otherwise write the ticket and block with `source-target` (or `ambiguous-target`). When the write fails, the guard resolves the verdict again: now `unusable:*` (the folder changed after step 2, for example it became a link) → block `session-state-unusable` with that problem; still `usable` → block `retry-ticket-unwritten`. It never allows.

- **I-4 (restated from 2026-11-05):** an exception that escapes `main()` exits 0 (allow), in all three hooks (guard `:1002-1004`, tracker `:151-153`, reset `:275-277`). It stays. The verdict function and the Stateless session catch everything they raise, so a hostile folder reaches `check-failed`, never the catch-all.
- **I-6 (fail closed, scoped):** through steps 1-8, only state written by the session's own user can cause an allow. A planted, linked, foreign-owned, open-mode or broken parent or Session folder can only give a block. A Foreign marker is still the user's own state (it sits in a parent the checks proved the user's own), so it opens; the stamp only detects it (Q4). Steps 4-6 read nothing from the folder. Out of scope: the I-4 catch-all, reached only by a defect outside the verdict function.
- **I-7 (`session-state-unusable` message):** it names the parent path, the problem in plain words and that problem's fix (for example "set LOCALAPPDATA to a local folder", "run `chmod 700 <path>`", "remove the link at <path>"; for `check-failed`, the exception's type and text), plus `/auto-improve-codegraph-uninstall` followed by a new session. The block banner OMITS its retry line ("repeat this exact call once; it will be allowed and logged", guard `:918-919`) for this reason. I-2 still applies: no shell route, no individual tool name.
- **I-7b (`retry-ticket-unwritten` message):** it names the Session folder (not an OS error text: the write path returns only a bool, and this contract does not change that shape), says the usual cause is a passing lock (an antivirus or indexer) or a full disk, and replaces the banner's retry line with: "Repeat this exact call: the guard tries again to record the retry. When that works the block says `source-target`, and the identical call after it is allowed." It names a CodeGraph tool call and the uninstall skill as the other ways out. It never names LOCALAPPDATA, `chmod` or a link; a folder that became a link is diagnosed by step 8's second verdict instead.
- **I-7c (banner by reason):** `block()` chooses the retry lines by reason: `source-target` and `ambiguous-target` keep today's two lines; `session-state-unusable` has none; `retry-ticket-unwritten` has the I-7b line. The uninstall lines stay for every reason.
- **I-8 (tracker and reset):** on an unusable verdict the tracker writes no marker and prints `[codegraph-turn-tracker] the per-user session folder <path> cannot be used (<problem>); the gate stays shut`. The reset hook deletes and prunes nothing under the parent and prints the same line under its own prefix. Its legacy `<cwd>/.claude/.codegraph-used-this-turn` deletion still runs. Both exit 0.
- **I-9 (pruner):** `prune_session_folders(<Per-user session parent>)` only, and only on a usable parent verdict. The 2026-11-05 I-5 rules apply inside it unchanged. The system temp folder is never listed.

### Events

| Name | Emitter | Listeners | Payload |
|------|---------|-----------|---------|
| GuardOpenedFromForeignMarker | guard | One stderr line and `log_event(event="foreign-marker")`, once per session. The flag is created only after `log_event` did not return False (2026-11-05 addendum 6). | cause, tool, session key |
| GuardBlockedOnUnusableState | guard | I-7 banner and `log_event(event="block", reason="session-state-unusable")`, once per blocked call | tool, problem, parent path |
| GuardBlockedOnTicketWrite | guard | I-7b banner and `log_event(event="block", reason="retry-ticket-unwritten")`, once per blocked call | tool, Session folder |
| SessionStateUnusable | tracker, reset | stderr only (I-8) | problem, parent path |

### Commands

| Name | Handler | Payload | Possible rejections |
|------|---------|---------|---------------------|
| Install (amended message only) | `auto_improve_finish_install.py addon --name codegraph` | as today | `codegraph-tool-named` (exit 2), with the Tool-named refusal message |

---

## Reused Mechanisms

- **Two-layer Claude path resolution:** extended by `TREE_HOP_REFUSAL` and the Hop proof (JOURNAL 2026-11-05 "A bridge re-export that silently falls back … must say which one it gave"). `tree_kind`, `main_checkout_root` and `worktree_own_root` are consumed as-is; `_git_file_kind` gets a comment only.
- **Guard fallback mode:** extended. The guard's binding gate becomes the Hop proof instead of `callable(_hop_allowed)` alone (guard `:82`).
- **Same-host path rule (MECHANISMS.md:45):** `_remote_host` and `_own_spellings` reused verbatim; each grows from four pinned copies to six (W-14 rows at `test_codegraph_first_guard.py:1799` and `:1851`). `_hop_allowed` stays at four.
- **Delivery cleanup / Records leftover sweep:** consumed as-is through the 2026-11-05 I-5 pruner; only its root argument changes.
- **Add-on layout (amendment 2026-11-05):** extended. `released_sha256` gains the folded hashes of the 0.15.2 copies of the three hooks.
- **Preview-hash apply / `codegraph-tool-named` refusal:** consumed as-is; only the message changes.
- **Plugin version check modes:** one patch raise, 0.15.2 to 0.15.3.
- Pattern, not a registered mechanism: the session-keyed marker. Its inline copies stay inline (2026-11-05 Option D).

## New Mechanisms (if any)

None. The Per-user session parent is a location rule inside an existing pattern, not a mechanism.

---

## Extension Points

- **Three hooks:** replace `tempfile.gettempdir()` as the Session folder base with the inline Parent base rule, the Remote rule and the parent checks. Remove `fail-open:state-unwritable` from `NOTICES` and from `announce()`'s every-call branch (guard `:955-959`); add both new reasons to `REASON_TEXT`; `block()` per I-7c. The tracker stamps the marker; the reset hook prunes the parent. Docstrings to rewrite: guard `:21`, `:27-36`, `announce()` `:943`; tracker `:8-10`, `:46`; reset `:9-10`, `:18`.
- **`_project_paths.py`:** add `TREE_HOP_REFUSAL = True`; add a comment above the `commondir` hop of `_git_file_kind` (`:639-648`) pinning the probe order: (1) read the `commondir` text; (2) judge the raw relative text; (3) judge the normalised join; (4) only then `realpath`, which touches the disk; (5) judge the `realpath` form; (6) `isdir` last. No later step may move before a check, because steps 4 and 6 touch the named host.
- **`_claude_paths.py`:** export `TREE_HOP_REFUSAL` (the Hop proof, meaning per Value Objects), remove `WORKTREE_OWN_ROOT_NATIVE` (`:196-199`, `:229`), update `__all__`.
- **Installer:** `_codegraph_index_notes` (`:2608`) gates on the Hop proof; `UNDECIDABLE_TREE_NOTE` says the helper is older than the scripts. `_tool_named_refusal` builds the Tool-named refusal message.
- **`addon.json`:** add the 0.15.2 hashes to `released_sha256`.
- **Shipped text the reversal makes false.** Each sentence is edited where it stands (JOURNAL 2026-11-02); none is left beside a note that contradicts it. E1 and E2 are the Value Objects sentences.
  - `skills/auto-improve-codegraph-install/SKILL.md`:
    - `:73-74`: "under the system temp folder" → "under the Per-user session parent (`%LOCALAPPDATA%\auto-improve-codegraph\` on Windows, `~/.cache/auto-improve-codegraph/` or `$XDG_CACHE_HOME/…` on POSIX)"; "in the temp folder" → "in that parent".
    - `:78`: "**The guard is a nudge, never a wall.**" → "**The guard lets reads through when CodeGraph is provably unavailable.**"; after "and logs it", add E2; after the retry sentence, add E1, then: "An unusable session folder blocks (`session-state-unusable`), says why and how to fix it."
    - `:98` stays (true in the usable state). `:156`, `:209`: add E1 after the retry escape.
    - `:160`, `:208`: "this skill builds an index only on a yes to its offer in Step <n> (`codegraph init -i`); otherwise the user runs it".
    - `:183`: "The only leftover is the session folder under the Per-user session parent, which the reset hook prunes. Folders `auto-improve-codegraph-*` left in the system temp folder by 0.15.2 are no longer read; delete them by hand if wanted."
    - Refusals list: add `session-state-unusable` and `retry-ticket-unwritten` with their ways out.
  - `skills/auto-improve-codegraph-uninstall/SKILL.md`: `:27` as for install `:183`; `:142`: add E1.
  - `skills/auto-improve-finish-install/SKILL.md:220-221`: "the guard is a nudge: it lets reads through" → "the guard lets reads through", plus "unless its session folder cannot be used, when it blocks and says why".
  - `README.md`:
    - `:306`: "the guard is a nudge, never a wall." → "the guard lets reads through when CodeGraph is provably unavailable." (keeps the 0.15.2 heading.)
    - `:308-309`: after "logged once per session per reason in `errors.jsonl`", add E2.
    - `:314-315`: replace the `state-unwritable` sentences with "Since 0.15.3 an unusable session folder blocks instead (`session-state-unusable`); see below."
    - `:316-318`, `:569-572`: add E1.
    - `:319-323`: "`<system temp folder>/auto-improve-codegraph-<session id>/`" → the Per-user session parent path; "in the temp folder" → "in that parent".
    - `:567` stays (it describes a missing tracker, where the retry works).
    - Add a "Changed in 0.15.3" block: the move; fail closed with both new reasons; old temp folders inert and deletable by hand; the upgrade route; the upgraded-project row (a 0.15.2 `_project_paths.py` left in place passes the Hop proof, so `index-other-tree` keeps firing).
  - `.claude/references/codegraph-decision-table.md`: `:107` the new location; `:113` "in the temp folder" → "in that parent"; `:118-119` after "logs one record per session per reason", add E2; `:124` "`state-unwritable` covers an unusable session folder." → "An unusable session folder blocks with `session-state-unusable` and offers no retry."; `:128-131` add E1; `:157` "It now fails open and offers the retry escape" gains "(since 0.15.3, an unusable session folder blocks)".
  - `.claude/hooks/hooks.json:52` (comment): "lists the system temp folder" → "lists the per-user session parent".
  - Test comments and docstrings that state the old location, the old count or the old marker shape: `test_addons.py:21, 93, 295, 327`; `test_codegraph_first_guard.py:14, 30, 1342, 1533, 1747, 1778, 1791, 1815, 2206`; `test_worktree_path_guards.py:368, 392, 403, 408, 1173, 2262`; `_addon_fixture.py:391-401, 512, 517, 532-533`.
  - **Re-grep before the PR** over `README.md`, `skills/`, `.claude/references/`, `.claude/addons/`, `.claude/hooks/`, `.claude/scripts/`, `.claude/registries/`: `state-unwritable`, `system temp`, `temp folder`, `nudge`, `repeat the blocked call`, `repeat the identical`, `repeat this exact call`, `once per session per reason`, `one record per session`, `logs it`, `WORKTREE_OWN_ROOT_NATIVE`, `four textual copies`, `four copies`, `` carries `_hop_allowed` ``, `gettempdir`, `run_hook_process`. List every hit and its disposition in the PR. JOURNAL hits (for example `JOURNAL.md:421`, which names `WORKTREE_OWN_ROOT_NATIVE` as a past example) are history and stay.
- **Registries (written at review):** following the 2026-11-05 precedent at `MECHANISMS.md:107` (a false span edited in place, plus a dated correction that records the edit):
  - `MECHANISMS.md:43`: span "It also exports `WORKTREE_OWN_ROOT_NATIVE`, true only when the `_project_paths.py` beside the scripts really defines `worktree_own_root`; the installer reads it so that a missing helper makes a tree undecidable" → "It also exports `TREE_HOP_REFUSAL`, the Hop proof computed on the `_project_paths.py` beside the scripts (the helper carries the constant, or both `_hop_allowed` and `worktree_own_root`); the installer reads it so that a helper without the hop refusal makes a tree undecidable".
  - `MECHANISMS.md:45`: span "the guard binds the two functions only from a helper that carries `_hop_allowed`" → "the guard binds the two functions only on the Hop proof (`TREE_HOP_REFUSAL` is True, or `_hop_allowed` and `worktree_own_root` are both callable)"; span "`_remote_host` / `_hop_allowed` exist as four textual copies (the helper, the codegraph guard, `_claude_paths.py`, the installer) pinned by a parity row" → "`_hop_allowed` exists as four textual copies (the helper, the codegraph guard, `_claude_paths.py`, the installer); `_remote_host` and `_own_spellings` exist as six (those four plus the codegraph tracker and reset hook); each set is pinned by a parity row".
  - `MECHANISMS.md:106`: span "a nudge, never a wall" → "fails open only on proof"; span "with one stderr line and one log record per session per reason" gains "(while the session folder cannot be used: the line on every call, no record)"; span "`state-unwritable` for an unusable session folder" → "an unusable session folder blocks (`session-state-unusable`)"; span "`<system temp>/`" → "`<Per-user session parent>/`"; ways-out span "repeat the blocked call once" → "repeat the blocked call once (not after `session-state-unusable`; after `retry-ticket-unwritten`, once more)". `:107` span "`<system temp>/`" likewise. Then a dated 2026-11-06 correction naming every edit above and the constant.
  - `VOCABULARY.md:123` (Investigation Turn amendment): span "under the system temp folder" → "under the Per-user session parent"; `:124` (Retry escape): append E1; `:125` (CodeGraph unavailability reason): span "`state-unwritable` is the sixth line, for a session folder the guard cannot use" → "an unusable session folder is not a reason: it blocks (`session-state-unusable`, 2026-11-06)". Append the two new terms and a dated correction naming these edits.

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| codegraph hooks | each other | Session folder files under the Per-user session parent | marker (stamped), tickets, cache | hook ↔ hook |
| guard, bridge, installer | `_project_paths.py` | the Hop proof | `TREE_HOP_REFUSAL`, or the 0.15.2 shape | helper → consumers |
| installer | the user | refusal result | Tool-named refusal message | script → user |

There is no REST, SignalR or DTO surface. Both sides of each row are in `Files to touch`.

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold. `.claude/area-mapping.json` has an empty `areas` object (the same finding as 2026-11-05). The scan was not run here (no shell). To confirm: `py -3 .claude/scripts/cross_area_scan.py .claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md`.

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

---

## Non-Goals

- Checking the SID of the folder owner on Windows (the owner chose the parent instead).
- A hostile `gitdir:` that is a symlink to a UNC path (documented, not changed).
- Turning `codegraph-tool-named` into a finding.
- Changing the preview sentence about what `mcp__codegraph__*` auto-approves (brief Q3).
- Deleting or migrating old session folders in the system temp folder (Q3).
- Protecting a user whose own `LOCALAPPDATA`, `XDG_CACHE_HOME` or `HOME` points at a shared local folder they chose. On POSIX the owner and mode checks still catch a planted parent. On Windows the `remote` rule catches network paths, UNC and mapped drives alike, and nothing else.
- Replacing the I-4 catch-all, or changing the bool return of `Session.write` / `_atomic_write` / `ensure_folder`.

## Confidence

Confidence: Medium.
- **High:** the location rule, fail closed, the stamp, the banner and the message, verified against the hook code (guard `:262-355, 374-407, 781-836, 891-967, 1002-1004`; reset `:87-95, 205-277`; tracker `:45-153`; installer `:2496-2517, 2568-2611`; bridge `:195-229`; helper `:565-651, 688`; `_addon_fixture.py:391-542`).
- **Medium:** the test impact. Every existing `state-unwritable` row is re-stated, every isolated environment adds `LOCALAPPDATA` and `XDG_CACHE_HOME`, every fixture marker call moves to the parent, and the three leak checks change target.

## Alternatives Considered & Why Rejected

- **Option A (chosen):** a per-user parent with fail closed. One location rule closes both the plant and the cross-user prune, with no Windows security API.
- **Option B (rejected):** keep the temp folder and check the owner's SID through `ctypes`: a new native-API surface in three inline copies, and the pruner would still list a shared folder.
- **Option C (rejected):** keep step 0 fail-open. Whoever can break the folder could switch off the victim's guard; it fails criterion 9.
- **Option D (rejected):** put the parent rule in `_project_paths.py`. An add-on copies a helper only when the project lacks it, so an upgraded project would keep the old helper.
- **Option E (rejected):** gate only on the new constant. An upgraded project keeps its 0.15.2 helper, so `index-other-tree` would stop firing in every upgraded worktree.
- **Option F (rejected):** carry the OS error text to I-7b by changing `Session.write` to return a reason. It changes a shape three hooks share for one diagnostic line; the folder path and the two usual causes are enough to act on.

## Uncertain Assumptions

- `VERIFIED via codegraph-first-guard.py:787-789, 831-832`: step 0 and a failed ticket write allow today. Both become blocks.
- `VERIFIED via codegraph-first-guard.py:262-331`: `_atomic_write`, `ensure_folder` and `Session.write` catch `OSError` and return only a bool.
- `VERIFIED via codegraph-first-guard.py:918-919`: the retry line of the block banner is printed for every reason.
- `VERIFIED via codegraph-first-guard.py:360-371`: `_has_project_index` catches `ValueError` from `os.lstat` and returns False (why the check-failed row patches one path only).
- `VERIFIED via codegraph-turn-reset.py:266`: the pruner lists `tempfile.gettempdir()`.
- `VERIFIED via auto_improve_finish_install.py:924-925`: the layer labels are `user`, `project` and `local`.
- `VERIFIED via grep`: `WORKTREE_OWN_ROOT_NATIVE` is defined at `_claude_paths.py:199` and read only by the installer (`:2608`) and the tests (`test_codegraph_first_guard.py:1258`, `test_auto_improve_finish_install.py:6724`).
- `VERIFIED via grep`: `_own_spellings` has four copies (guard `:403`, helper `:594`, bridge `:144`, installer `:2597`); the isolation helpers are `af.isolated_env` (`_addon_fixture.py:531`), `codegraph_env` (`test_worktree_path_guards.py:401`) and `clean_env` (`test_addons.py:60`); `run_hook_process` exists nowhere.
- `VERIFIED via grep`: the 0.15.2 `_project_paths.py` has `_hop_allowed` (`:581`) and `worktree_own_root` (`:688`).
- `ASSUMED`: `e4f392c` holds that 0.15.2 helper and `643b667` an older helper without `_hop_allowed`. Check: `git cat-file -e e4f392c:.claude/hooks/_project_paths.py`; PowerShell `git show 643b667:.claude/hooks/_project_paths.py | Select-String _hop_allowed`. A row whose commit is absent skips with a printed reason.
- `ASSUMED`: on Windows `os.path.realpath` of a mapped network drive returns `\\server\share`. A row table-tests the Remote rule with a patched `realpath`; a separate row records (not asserts) the real behaviour when `net use` shows a mapped drive.
- `ASSUMED`: `%LOCALAPPDATA%` is set in every Windows interactive or `claude -p` session. If not, the hooks fail closed, visibly, with a named fix.

## Failure Modes & Mitigations

- **FM:** tests write into the developer's real `%LOCALAPPDATA%` or `~/.cache`.
  - **Mitigation:** `af.isolated_env`, `codegraph_env` and `clean_env` set `LOCALAPPDATA` = `<fixture home>/AppData/Local` and `XDG_CACHE_HOME` = `<fixture home>/.cache` (plus HOME, USERPROFILE, TMP, TEMP as before); in-process rows patch `os.environ`. The three leak checks snapshot the real parent and the real temp folder, in every suite that runs the hooks, for any `auto-improve-codegraph-*` name (JOURNAL 2026-10-05).
- **FM:** a fixture creates the parent with the umask's mode (`0755`), so every POSIX row fails closed with `open-mode`.
  - **Mitigation:** the fixture helpers create the parent with `os.mkdir(…, 0o700)` then `os.chmod(…, 0o700)`, never `mkdir(parents=True)`.
- **FM:** fail closed walls a session whose parent is broken (for example a read-only home in a container).
  - **Mitigation:** I-7 names the problem and the fix; steps 4-6 still let reads through where CodeGraph is provably unavailable (Q1).
- **FM:** a transient ticket-write failure walls a call with a wrong diagnosis.
  - **Mitigation:** `retry-ticket-unwritten` and I-7b; step 8's second verdict routes a folder that broke after step 2 to I-7 instead.
- **FM:** a non-OSError exception on a hostile folder reaches the I-4 catch-all and allows.
  - **Mitigation:** the verdict function and the Stateless session catch `Exception` (`check-failed`); the check-failed row in the TASK block.
- **FM:** `announce()` creates a flag inside, or through, an unusable folder.
  - **Mitigation:** the Stateless session makes no filesystem call; the announce row.
- **FM:** an upgraded project keeps its 0.15.2 helper and loses `index-other-tree`.
  - **Mitigation:** the Hop proof accepts the 0.15.2 shape; the `e4f392c` row; README states the row.
- **FM:** existing rows that expect `fail-open:state-unwritable` silently become blocks, or are deleted; existing marker rows silently become Foreign-marker rows.
  - **Mitigation:** the TASK block lists each by the state it guards and re-states it with a positive control; `af.write_marker` writes the stamped shape by default (JOURNAL 2026-11-02, 2026-10-17).
- **FM:** the pruner reaches a foreign folder through a link in the parent.
  - **Mitigation:** the I-5 link test and per-file re-check apply unchanged; folder-link rows (`mklink /J` on Windows, `os.symlink(target_is_directory=True)` on POSIX): kept, target untouched.
- **FM:** the inline copies drift apart.
  - **Mitigation:** a parity row over the Parent base rule and the problem set for the three hooks; W-14 covers six `_remote_host` and six `_own_spellings` copies.
- **FM:** a 0.15.2 hook copy stays installed after the upgrade.
  - **Mitigation:** the 0.15.2 hashes go into `released_sha256`; README gives the upgrade route (JOURNAL 2026-10-22).
- **FM:** the stamp check drops a legitimate mid-upgrade marker.
  - **Mitigation:** a Foreign marker still opens (it only logs); old markers sit in the old location, which is no longer read.

## Open Questions for User

All answered by the user on 2026-11-06 (question dialog); each accepted the recommendation.

- [x] **Q1.** What "fail closed" means for an unusable folder. **Answered 2026-11-06:** (a) no marker read, no ticket; source reads block with a fix; subagent, no-index and no-server sessions still read.
- [x] **Q2.** The POSIX location. **Answered 2026-11-06:** `$XDG_CACHE_HOME`, else `$HOME/.cache`.
- [x] **Q3.** Old session folders in the system temp folder. **Answered 2026-11-06:** left alone; hand deletion documented.
- [x] **Q4.** A Foreign marker. **Answered 2026-11-06:** opens the gate, logged once.
- [x] **Q5.** Delivery. **Answered 2026-11-06:** one delivery block, review inside `/flow`.
- Brief Q3 and Q4 carried from intake on 2026-11-06 as assumptions: the preview sentence is unchanged; the constant, the comment and the skill wording are in, the UNC symlink is out.

## Lessons referenced

- **2026-11-02 — Edit a reversed sentence where it stands:** heeded by the shipped-text list, E1, E2 and the registry span edits.
- **2026-10-04 — Check a documented guard behaviour against the guard's code:** heeded; every "nudge", "repeat once" and "logged once" sentence, and the guard's own banner (I-7c), match the new behaviour.
- **2026-11-02 — A rule titled "every" must list every line it covers:** heeded by step 2's logging rule, E2 and its sites.
- **2026-11-05 — A bridge re-export that silently falls back … must also say which one it gave:** heeded by the Hop proof and its per-module meaning.
- **2026-10-22 — Describe a broken install by the rows each install age really has:** heeded by `released_sha256`, the Hop proof's 0.15.2 arm and the README row.
- **2026-11-05 — An "older release" test fixture must be pinned to a fixed commit:** heeded by the `e4f392c` and `643b667` pins.
- **2026-11-05 — A same-host path rule must compare against both the written and the realpath form:** heeded by reusing `_remote_host` and `_own_spellings`, both pinned at six copies.
- **2026-11-05 — A hardening fix applied to a shared classifier must be checked against every consumer:** heeded; `_git_file_kind` gets a comment only.
- **2026-10-05 — A documented "missing file means the default" must read one named location only:** heeded by the mapping-only Parent base rule and the leak checks.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case:** heeded by the unset, empty and relative rows, and by the check-failed row that patches one path so step 4 cannot answer first.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** and **2026-11-02 — Name the tests a fix may change by the state they guard:** heeded by the TASK block's row list, the fixture-helper changes and the three leak checks.
- **2026-11-02 — A path that calls a command must say how it finds the command's input:** heeded; I-7b uses only what step 8 holds (the folder path), Option F.
- **2026-10-17 — Git for Windows lists files beneath an untracked junction:** heeded by I-9.
- **2026-10-28 — Guard messages must use names the guard emits:** heeded by I-7, I-7b and I-7c.
- **2026-10-28 — State the real trigger of a hook, not the printing condition:** heeded by step 2's per-call cost.
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out:** heeded by I-7 and I-7b.
- **2026-11-02 — A revision that adds a path adds its failure modes:** heeded; the catch-all, the ticket write, the old helper, `announce()`, the fixture mode and the link swap each have a failure mode.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval:** heeded by both revisions.
- Orthogonal to north-stars: none active (`.claude/north-stars/` holds no file).

## Revision note

Revision 1, 2026-11-06, after critique round 1 (1 BLOCKER, 7 WARN, 4 NIT) and Q1-Q5: shipped-text list added; I-4 restated and `check-failed` added; the Hop proof accepts the 0.15.2 helper; the Remote rule reuses `_remote_host`; the POSIX base reads only the mapping; `retry-ticket-unwritten` added; the Stateless session; the three leak checks moved; decision order renumbered.

## Divergence note (2026-11-07, merge with the hooks redesign)

While this contract was in review, master merged the codegraph hooks redesign (#261, plugin 0.16.2). Its rule G-1 reads the turn marker before the target is classified. This contract's invariant I-6 allows a marker to be read only from a session folder proven usable, so the session check now runs first, ahead of target classification. Decision order after the merge: session check, marker, targets, subagent / no index / server, ticket.

Effect: our earlier property "a non-source target resolves nothing" no longer holds. Every guarded call resolves the per-user parent, and the first call may create it (mode 0700 on POSIX), as master's step 0 already did for the old folder. An unusable state still lets non-source and no-target reads through, and still blocks a source read as `session-state-unusable`. Accepted by the code reviewer (pass 4, merge) and the security auditor (pass 5, merge) as the lesser evil: classifying first would drop G-1's saving, and reading the marker first would break I-6.

## Revision note (round 2)

Revision 2, 2026-11-06, after critique pass 2 (1 BLOCKER, 6 WARN, 6 NIT); no new user decision:
- **BLOCKER (a), repeat once:** E1 added and placed at install SKILL `:78, 156, 209`, uninstall `:142`, README `:316-318, 569-572`, decision table `:128-131`, `MECHANISMS.md:106` ways-out and `VOCABULARY.md:124`. The guard's banner (`:918-919`) now chooses its retry line by reason (I-7c): none for `session-state-unusable`, the I-7b line for `retry-ticket-unwritten`; TASK rows assert each.
- **BLOCKER (b):** the `MECHANISMS.md:106` ways-out span is in the registry list.
- **BLOCKER (c), every allow logged:** E2 added and placed at README `:308-309`, install SKILL `:78`, decision table `:118-119` (found by re-grep) and `MECHANISMS.md:106`. The re-grep list gains `repeat this exact call`, `repeat the identical`, `once per session per reason`, `one record per session`, `logs it` and the WARN 4/5 names.
- **WARN 1:** the check-failed row patches `os.lstat` only for paths inside the fixture parent and plants an index and a server, so step 4 cannot allow; a no-index control proves steps 4-6 still run.
- **WARN 2:** the OS error text is dropped from I-7b and its Event (Option F records why); the bool shape is a Non-Goal.
- **WARN 3:** the tracker and reset also copy `_own_spellings`; its W-14 row (`:1851`) grows to six copies.
- **WARN 4:** `MECHANISMS.md:43` and both `:45` spans added with replacements.
- **WARN 5:** `run_hook_process` replaced by `af.isolated_env` (`_addon_fixture.py:531`), with `codegraph_env` and `clean_env`, all verified by grep.
- **WARN 6:** the TASK block specifies the new `af.session_parent`, `af.session_folder`, `af.write_marker` (stamped by default, `stamped=False` for Foreign-marker rows), `af.remove_marker` and the fixture `LOCALAPPDATA` base; existing marker rows stay own-marker rows.
- **NITs:** the per-module meaning of `TREE_HOP_REFUSAL`; the empty host counts as remote; step 8 resolves the verdict again so a folder that became a link gets I-7, not I-7b; the per-call cost is stated in step 2; the docstring and test-comment list is completed. Critique rounds 1 and 2 stay appended for the main session to move to `.claude/contract-history/` (the precedent move was made by the main session; this agent writes only contracts and registries). The body was trimmed (answered questions to one line each, round-1 note to one paragraph), but this revision also adds text, and the size was not measured (no shell, and this repo has no `memory-health.py`). Estimated at four characters per token it is near the 12,000-token budget and may be over it; the remaining long part is the TASK block, kept whole because the implementer works from it.

---

## Implementation Handoff

There is one mergeable block on the brief's branch `fix/271-session-folder-owner-and-tool-named`, with the patch raise in this pull request (Q5). It does not split cleanly: the three hooks share the location rule and its tests, and the constant is read by the guard and the installer in the same suites.

### 1. Per-user session parent, fail closed, refusal message, housekeeping and version (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/addons/codegraph/hooks/codegraph-first-guard.py`
- `.claude/addons/codegraph/hooks/codegraph-turn-tracker.py`
- `.claude/addons/codegraph/hooks/codegraph-turn-reset.py`
- `.claude/addons/codegraph/addon.json`
- `.claude/hooks/_project_paths.py`
- `.claude/scripts/_claude_paths.py`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/hooks/hooks.json`
- `.claude/hooks/tests/test_codegraph_first_guard.py`
- `.claude/hooks/tests/test_addons.py`
- `.claude/hooks/tests/test_worktree_path_guards.py`
- `.claude/hooks/tests/_addon_fixture.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/tests/test_installed_plugin_root.py`
- `.claude/scripts/tests/test_codegraph_session_parent_docs.py` (new; added 2026-11-06 after review, both reviewers asked for it to be listed)
- `skills/auto-improve-codegraph-install/SKILL.md`
- `skills/auto-improve-codegraph-uninstall/SKILL.md`
- `skills/auto-improve-finish-install/SKILL.md`
- `.claude/references/codegraph-decision-table.md`
- `README.md`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**Pre-written TASK block:**
```
TASK: Move the codegraph hooks' Session folders under the Per-user session parent, make an unusable parent or
folder fail closed (session-state-unusable) and a failed ticket write block (retry-ticket-unwritten), choose the
block banner's retry line by reason, stamp the Turn marker and log a Foreign marker once, rewrite the
codegraph-tool-named refusal message, add TREE_HOP_REFUSAL and the Hop proof (replacing
WORKTREE_OWN_ROOT_NATIVE), add the probe-order comment, edit every shipped sentence the change makes false,
raise to 0.15.3.
CONTEXT: concept contract .claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md (Data Shapes incl.
  E1/E2, decision order 1-8, I-4, I-6..I-9, Extension Points); brief
  .claude/work-items/2026-11-06-271-session-folder-owner-and-tool-named.md; prior contract
  .claude/concepts/2026-11-05-codegraph-guard-fail-open.md (I-1..I-5 and the addenda still bind).
FILES: see Files to touch.
CONSTRAINTS:
  - Test first (/tdd-first): write every row below, see it fail on the current code, then implement.
  - Answers: Q1 (a) fail closed; Q2 XDG_CACHE_HOME else HOME/.cache; Q3 old temp folders left, documented;
    Q4 a Foreign marker opens and logs once; Q5 one block, review in /flow.
  - The parent is resolved at CALL time, inline in each hook. The Parent base rule is a pure function of
    (environment mapping, os name) that reads only the mapping: no expanduser, no pwd, no os.environ. No hook
    calls tempfile.gettempdir() for a Session folder. Parent creation: one mkdir 0700; the POSIX base one level
    only when its own parent exists; never makedirs.
  - Remote rule: _remote_host AND _own_spellings copied byte-identically into tracker and reset; remote when
    any spelling's host is not None and not "?<letter>:"; the empty host "" is remote.
  - The verdict function (file facts from os.lstat) and the Stateless session catch Exception (check-failed).
    Unusable verdict: no filesystem call through the Session object (announce() included), no marker read, no
    cache, no ticket; steps 4-6 still apply and print without a log record; otherwise block
    session-state-unusable (I-7), one block record per call. Step 8 write failure: resolve the verdict again;
    unusable -> session-state-unusable, usable -> retry-ticket-unwritten (I-7b; no OS error text; Session.write
    keeps its bool). block() per I-7c.
  - Hop proof = TREE_HOP_REFUSAL is True, or callable(_hop_allowed) and callable(worktree_own_root); used by
    the guard, the bridge (exported as TREE_HOP_REFUSAL) and the installer.
  - Fixture helpers (_addon_fixture.py), each with a rewritten docstring:
    * isolated_env(home, tmp, ...) also sets LOCALAPPDATA=<home>/AppData/Local and XDG_CACHE_HOME=<home>/.cache;
      Sandbox creates <home>/AppData/Local. codegraph_env (test_worktree_path_guards.py:401) and clean_env
      (test_addons.py:60) do the same from their fixture home. In-process rows patch os.environ.
    * new session_parent(home): <base>/auto-improve-codegraph for this OS, computed by the pure rule; created
      on demand with os.mkdir(p, 0o700) then os.chmod(p, 0o700), never mkdir(parents=True).
    * session_folder(parent, sid), write_marker(parent, sid, tool, stamped=True), remove_marker(parent, sid):
      the first argument is the parent, not the temp folder. write_marker writes {ts, tool, summary, pid,
      writer: "codegraph-turn-tracker", session: sid} by default; stamped=False writes the 0.15.2 shape.
      Every existing call site passes af.session_parent(<fixture home>) and keeps the default, so existing
      marker rows stay own-marker rows (no foreign-marker record). Criterion-4 rows use stamped=False.
  - Existing rows to RE-STATE (keep the state each guards, change the expected outcome):
    * test_codegraph_first_guard.py:488-489 (Session folder is a link) and :501-502 (is a file): now block
      session-state-unusable with problem session-link / session-not-a-folder; :524-535 (ticket cannot be
      written): now block retry-ticket-unwritten. Each gets a positive control: the same fixture with a
      usable folder blocks source-target and then allows its retry.
    * The three real-temp leak checks: test_worktree_path_guards.py:2262-2305 (W5),
      test_codegraph_first_guard.py:2324, and _addon_fixture.py:391-401 (REAL_TEMP,
      real_temp_codegraph_entries). Add REAL_PARENT (the real Per-user session parent, computed at import from
      the original os.environ by the pure rule) and real_parent_codegraph_entries(); both leak checks snapshot
      the real parent AND the real temp folder before and after, and fail on any new auto-improve-codegraph-*
      entry in either. Add the same check to test_addons.py.
    * W-14 rows: _remote_host (:1799) and _own_spellings (:1851) over six copies; _hop_allowed stays four;
      comments :1747, :1778, :1791, :1815 say which count applies.
    * Grep the test files for "state-unwritable" and "gettempdir"; list every hit and its disposition in the PR.
  - New rows, by file:
    * test_codegraph_first_guard.py:
      - criterion 2: the fixture TMP holds auto-improve-codegraph-<victim key>/turn.json; index and server
        present; the victim's first source Read -> block (source-target). Control: the same marker under the
        Per-user session parent -> allow.
      - criterion 3: an old known-file folder in the fixture TMP is untouched after reset; a folder link inside
        the parent pointing into the fixture TMP is kept and its target untouched; an old own folder in the
        parent is pruned (control). A foreign-owner row runs only as root on POSIX, else skip(...) with reason.
      - criterion 4: an unstamped, an other-session and an unreadable marker each allow and give exactly one
        foreign-marker record after two calls; a stamped own marker gives none.
      - criterion 9: each Parent problem gives session-state-unusable. Pure-rule table on every OS: Windows
        LOCALAPPDATA unset, empty, relative, \\host\share, \\?\UNC\host\share (remote), \\?\C:\x (local),
        \\?\Volume{0}\x (empty host, remote), a patched realpath mapping Z:\ to \\srv\s (remote); POSIX
        XDG_CACHE_HOME set, empty (falls to HOME), relative (not-absolute), both unset (unset). On-disk rows per
        OS: parent a junction or symlink, parent a file, POSIX mode 0o755, POSIX base missing with its parent
        missing (cannot-create). The message names the path and the fix and contains no "repeat this exact
        call", no "cat ", no "through the shell". The tracker writes no marker and prints its line; the reset
        hook deletes and prunes nothing and still removes the legacy sentinel; subagent and no-index payloads
        still allow and write no log record.
      - check-failed: project with an index and a server; os.lstat wrapped to raise ValueError only for a path
        equal to or inside the fixture parent, delegating otherwise -> guard blocks session-state-unusable,
        problem check-failed, message names ValueError; tracker writes no marker; reset deletes nothing.
        Control: same wrapper, no index -> allow fail-open:no-index, no log record.
      - announce: parent is a link to a fixture folder; a no-index allow leaves the link target unchanged.
      - retry-ticket-unwritten: the I-7b message and banner line ("tries again to record the retry"), no
        "will be allowed and logged", no LOCALAPPDATA/chmod/link text; after the write succeeds again the
        repeat blocks source-target and the identical call after it is allowed. Link swap: _atomic_write
        patched to replace the Session folder with a link and return False -> session-state-unusable, problem
        session-link.
      - banner: source-target keeps "repeat this exact call once; it will be allowed and logged".
      - parity: the three hooks' Parent base rule and problem set agree over one table.
      - Hop proof: guard with the helper pinned at e4f392c (0.15.2) binds tree_kind and main_checkout_root and
        gives index-other-tree in a linked worktree without its own index; at 643b667 they stay unbound; with
        the current helper they are bound. git cat-file -e first; skip with a printed reason if absent; never
        HEAD.
    * test_auto_improve_finish_install.py: two per-tool entries in two layers (project and local) -> exit 2,
      code codegraph-tool-named, the message contains each entry, each layer name, each file,
      "mcp__codegraph__*" and "replace"; findings carry the layer. The undecidable note when the Hop proof
      fails; rewrite the :6724 comment and the test_codegraph_first_guard.py:1258 SimpleNamespace to the
      new constant.
    * test_installed_plugin_root.py: __all__ lists TREE_HOP_REFUSAL and not WORKTREE_OWN_ROOT_NATIVE.
    * test_plugin_manifests.py: released_sha256 covers the 0.15.2 copies of the three hooks (from e4f392c).
  - Docs, docstrings, test comments and registries exactly per Extension Points (E1, E2 at every listed
    site); run its re-grep list and report every hit.
  - Raise all five version entries to 0.15.3; run py -3 .claude/scripts/check_version_bump.py.
  - Run py -3 .claude/hooks/tests/test_codegraph_first_guard.py, py -3 .claude/hooks/tests/test_addons.py,
    py -3 .claude/hooks/tests/test_worktree_path_guards.py and
    py -3 -m unittest discover -s .claude/scripts/tests -p "test_*.py"; all must pass. Report the skip count.
  - /flow's reviewer step runs security-auditor and fullstack-code-reviewer.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

`pr_merged.py` fills this list when the contract's work is merged and nothing is pending. Do not tick lines by hand.

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

**Critic:** contract-critic, two fresh passes (2026-11-06)
**Verdict:** pass 1 blockers-found (1 BLOCKER, 7 WARN, 4 NIT); pass 2 blockers-found (1 BLOCKER, 6 WARN, 6 NIT). Both rounds were revised in the body (see the revision notes above); no third critic round, by the user's decision.

The full findings are kept in `.claude/contract-history/`:
- `2026-11-06-session-folder-owner-and-tool-named.round-1.md`
- `2026-11-06-session-folder-owner-and-tool-named.round-2.md`
