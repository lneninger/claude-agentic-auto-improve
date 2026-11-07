# Code review, pass 3 (cold context): 2026-11-06-session-folder-owner-and-tool-named (#271)

**Reviewer:** fullstack-code-reviewer, third pass, 2026-11-06
**Contract:** `.claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md` (approved)
**Diff:** uncommitted worktree against `c8653e3` (no commits on the branch). Test files compared line by line against `c8653e3`.
**Scope:** Python hooks, installer, bridge, helper, manifests, docs, registries. No C# or Angular code.

## What I ran and checked myself

| Check | Result |
|---|---|
| `test_codegraph_first_guard.py` (alone) | 1158 passed, 0 failed, 3 skipped (Q-3 root-only, Q-9 POSIX open-mode, T-M1 POSIX twin: all POSIX/root-only on Windows) |
| `test_worktree_path_guards.py` | 190/190 |
| `test_addons.py` | 33 OK |
| `test_plugin_manifests.py` | 191 passed, 0 failed |
| `test_installed_plugin_root` + `test_codegraph_session_parent_docs` | 42 OK |
| installer subset (`-k ToolNamed Hop tool_named refusal entry undecidable`) | 35 OK |
| full `unittest discover -s .claude/scripts/tests` (finished after the first draft, 3944 s) | **FAILED: 2608 run, 3 failures, 4 errors.** One error is caused by this diff (WARN below: `test_plugin_manifests` cannot be imported under discover). The other six are in files this diff does not touch: `test_script_path_resolution`, `test_ship_skill_sync` and `test_sql_patterns_skill_sync` call `sys.exit` at import; `test_land_contract` flags `skills/ship/SKILL.md` `gh-pr-merge`; and there are two `test_land_contract_verification` real-config rows. Confirm on `c8653e3` that these six also fail there before the PR. |
| `check_version_bump.py` | "no shipped plugin file changed" (expected for an uncommitted diff; re-run after the commit) |
| Parity, AST over the three hooks (own script) | Source-identical: `session_parent_base`, `_base_shown`, `_create_parent`, `resolve_session_parent`, `session_folder_problem`, `_remote_host`, `_own_spellings`, `PARENT_NAME`, `PARENT_PROBLEMS`, `_LOCAL_DEVICE_HOST_RE`, `_REPARSE_POINT`, `_SESSION_ID_RE`, `SESSION_PREFIX`, `MARKER_NAME`. `_is_link_stat`: code identical, docstring differs (allowed). `MARKER_WRITER`: guard = tracker (reset does not need it). |
| `released_sha256` (own script, BOM + CRLF fold) | guard `8c44ed60…`, reset `900db4ad…`, tracker `7e2daa3a…` at `e4f392c` are listed; `c8653e3` copies are byte-identical to `e4f392c`; current copies correctly absent |
| Version | 0.15.3 in `plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, both `marketplace.json` entries |
| INV-15 count | README:1040 says 395 cases; `def test_` in `test_auto_improve_finish_install.py` = 395. README:372 ("grows to 385") is 0.15.2 history |
| `git status --ignored` | Only expected files, three reviewer agent-memory notes, ignored `__pycache__/` and `.claude/cache/`. No scratch |
| Tests weakened? | No. All 80 removed test lines are re-stated: step 0/7 rows now assert `session-state-unusable` / `retry-ticket-unwritten` with controls; "nothing written through the link" kept (:508, :2883, :3061); marker shape asserts the exact six keys (test_addons:415); W-14 grew to six copies for `_remote_host`/`_own_spellings`, `_hop_allowed` stays four (`run_hop_rows(mods, six)`); fixture helpers moved to `af.session_parent` |
| Files to touch | Complete: the new docs test is now listed (contract :322). Every changed file is listed or is a reviewer write (JOURNAL, agent-memory, reviews) |

### `block()` / `announce()` / `log()` for ordinary inputs

Compared with `c8653e3`:
- `source-target` / `ambiguous-target` banners are line-for-line the old banner; `details` is still `{tool, reason}`.
- `cg_suggestion` now reads only `str` fields; for string inputs the output is unchanged (same key order `file_path` → `filePath` → `path`).
- `block()` now builds the message inside `try … finally: sys.exit(2)`, with a minimal fallback banner if building raises (security pass-2 Low closed).
- `log()` / `announce()` add `errors="backslashreplace"`; encodable text prints byte-identically.
- Only exit-code change: a `log_event` that raises now exits 2 (was: the catch-all exit 0). That is stricter and matches I-6.

### `_entry_shown`, bridge, Hop proof

- `_entry_shown` now escapes every `Cf`/`Cc`/`Cs`/`Zl`/`Zp` character plus the backtick, caps at 200 characters (security pass-2 bidi/zero-width Low closed). Layer and file come from the installer. The message matches the contract's Tool-named refusal message.
- Bridge: `worktree_own_root = _native_own_root if (TREE_HOP_REFUSAL and callable(_native_own_root)) else inline` — never `None` (S-L6 rows pass). Installer gates on `getattr(api, "TREE_HOP_REFUSAL", False) is not True`. Guard Hop proof matches the contract expression.

---

### `.claude/addons/codegraph/hooks/codegraph-first-guard.py` (same block in the tracker and the reset hook)

**[WARN]: A drive-less rooted base (`\x`, `/x`) skips the drive table, so the cwd's mapped drive is judged only by `realpath`** — `session_parent_base`, lines 301-333 (all three copies)
```python
if not path_module.isabs(raw):          # Python 3.12: ntpath.isabs("\\x") is True
    return None, "not-absolute"
...
letter = (stripped if stripped[1:2] == ":" else "")[:1]   # "" for "\x": no GetDriveTypeW
...
texts.append(full_name(stripped))       # "\x" -> "<cwd drive>:\x", judged only through _own_spellings -> realpath
```
**Problem**:
- Reproduced in-process (fake `realpath` that records, fake `GetDriveTypeW` that answers `DRIVE_REMOTE` for every letter): `LOCALAPPDATA=\x\y` and `/x/y` return `(raw, None)` (usable). `GetDriveTypeW` is never called; `realpath` is called on `D:\x\y`. The control `Z:\x` and `\\?\\Z:\x` return `remote` with only the drive-table call.
- When the hook's cwd is on a mapped drive (projects on a network drive are not rare), `\x` resolves to that drive. A disconnected drive costs about 21 s per `realpath` (pass 2 measured it), returns the input unchanged and is judged **local**; a connected one is caught only because `realpath` happens to reach `\\server\share` after contacting it. That is exactly the class pass 2 closed for `Z:\x` and the doubled-separator spellings; security-auditor pass 2 named this spelling in its fix step 1 ("Reject … any raw that is rooted without a drive"), and it was not done. No row covers it (`grep rooted|without a drive` in the guard suite: nothing).
- The behaviour also depends on the Python version: from 3.13 `ntpath.isabs("\\x")` is False and the same value gives `not-absolute`.
- Who can reach it: only someone who sets the victim's own `LOCALAPPDATA`, with the cwd on a mapped drive. Same precondition as pass-2 M1, hence WARN.

**Fix** (all three copies; Q-parity keeps them identical):
```python
if not path_module.isabs(raw):
    return None, "not-absolute"
if os_name == "nt" and not ntpath.splitdrive(raw)[0]:
    return None, "not-absolute"   # rooted without a drive resolves against the cwd's drive: never judged, same on every Python
```
Rows: `\x`, `/x/y` → `not-absolute`, with a `realpath` fake that raises if called; parity row over the three hooks. Note that `splitdrive` of a device or UNC spelling is non-empty, so the existing rows are unaffected.

---

**[INFO]: `PARENT_PROBLEMS` is not in the parity row** (`test_codegraph_first_guard.py:2661`, `SHARED_CONSTANTS`). It is identical today (I checked). Add it next to `PARENT_NAME`.

**[INFO, carried from pass 1/2, optional]:** a `check-failed` raised inside `session_parent_base` still prints `Problem:   -- …` with an empty path (`parent = ""` at :381). Showing `_base_shown(os.environ, os.name)` there would name the setting.

**[INFO, contract-mandated, no action]:** on an unusable verdict the reset hook deletes nothing (I-8), so a marker written in turn N survives a prompt whose verdict was unusable; if the folder becomes usable again within the session, turn N+1 opens from it. It is the user's own state (I-6 holds) and the contract chose this; noting it as a test-worthy edge.

---

### `.claude/scripts/tests/test_plugin_manifests.py`

**[WARN]: The new 0.15.2-hash row runs `git` in the checkout at import, so the module fails to import under `unittest discover`** — lines 1075-1095 (added by this diff)
```python
_probe = _subprocess.run(["git", "-C", str(af.PROJECT_ROOT), "cat-file", "-e", "e4f392c^{commit}"], capture_output=True)
```
**Problem**:
- Run alone, the file passes (191 passed).
- Under the contract's mandated `py -3 -m unittest discover -s .claude/scripts/tests -p "test_*.py"`, `test_land_contract_identity` has already installed its process-wide guard against git runs in the checkout. The guard raises `RuntimeError: test suite attempted git run inside the checkout …` at module import, and discover reports `ERROR: test_plugin_manifests (unittest.loader._FailedTest)`.
- So all 191 manifest checks vanish from the discover run, not only the new row. The guard says "Never patch this guard away; patch the edge in the failing test instead."
- The contract's TASK block says the discover "must pass"; this diff turns a previously importable module into an import error.

**Fix**: pin the three folded 0.15.2 hashes as literals in the row. A fixed commit never changes, and I recomputed them: `8c44ed60…`, `900db4ad…`, `7e2daa3a…`. Assert that each is in `released_sha256`. Keep the `e4f392c` recompute only as an optional cross-check, wrapped so that a `RuntimeError` or `OSError` from the launcher prints a SKIP with the reason. Never let it raise at import. Then re-run the full discover and confirm that `test_plugin_manifests` runs inside it.

---

### `.claude/scripts/_claude_paths.py`

**[INFO, carried from pass 2 (both reviewers), still open]: the comment says True means "native"** — lines 196-201
```
True means this bridge uses the helper's native tree functions, False its inline copies
```
A helper that declares `TREE_HOP_REFUSAL = True` but has no callable `worktree_own_root` gives True and the inline copy (the S-L6 row proves exactly this). Fix: "True: the helper's tree functions are trusted; `worktree_own_root` is native when the helper has it, else the inline copy."

---

### `README.md` and `skills/auto-improve-codegraph-install/SKILL.md`

**[INFO]: "an unset … `XDG_CACHE_HOME`" is not a failure** — README:316, install SKILL:182 (`session-state-unusable` bullet)
```
an unset or relative `LOCALAPPDATA` / `XDG_CACHE_HOME`
```
An unset `XDG_CACHE_HOME` falls back to `HOME/.cache` (code :292-296); only both unset gives `unset`. Rewrite: "an unset or relative `LOCALAPPDATA`, a relative `XDG_CACHE_HOME`, or neither `XDG_CACHE_HOME` nor `HOME` set". "a network path" is detected on Windows only (Non-Goal); "a network path (Windows)" would be exact.

Everything else in the re-grep list reads true against the code:
- `state-unwritable`: only README 0.15.3 history ("reverses 0.15.2's …").
- `nudge`: only the unrelated angular-tailwind and plan-question advisors.
- `WORKTREE_OWN_ROOT_NATIVE`: only README "replaces" and JOURNAL/MECHANISMS correction history.
- `gettempdir`: none in the three codegraph hooks. Other users are out of scope (follow-ups below).
- `system temp` / `temp folder`: every hit says the temp folder is no longer used, or is unrelated (design-first, pr-merged, unit-testing references; guard :884 comment about background output files).
- E1 follows every "repeat the blocked call" sentence: README :347, :603; install SKILL :156, :214; uninstall SKILL :142; decision table :132-135; VOCABULARY Retry escape; MECHANISMS :106. The banner's own `source-target` line has none, correctly.
- **Pass-2 README WARN resolved:** the "It fails closed" bullet no longer carries E1; `E1_SITES` README count is 2.
- E2 follows "logged once per session per reason" at README :340, decision table :122, install SKILL :78, MECHANISMS :106.
- Install SKILL "Step 2 offer" claim (:160, :213) matches Step 2 (:131).

---

### Status of every earlier finding

| Earlier finding | Status now |
|---|---|
| CR pass 2 WARN: realpath before the drive table, plain `Z:` no drive check | **Resolved** for every lettered spelling (plain, device, doubled separator): drive table first, `(0,1,4)` and any exception → `remote`. **Residual:** the drive-less rooted spelling (WARN above) |
| CR pass 2 WARN: README third E1 copy | **Resolved** |
| CR pass 2 WARN: Files to touch omits docs test | **Resolved** (contract :322) |
| CR pass 2 INFO: `_is_link_stat`, constants not in parity | **Resolved** (`SHARED_NODOC_FUNCTIONS`, `SHARED_CONSTANTS`, mutation proof). Residual: `PARENT_PROBLEMS` (INFO) |
| CR pass 2 INFO: bridge comment | **Open** (INFO above) |
| CR INFO: `Session.path` stateless, empty check-failed path | Open, optional |
| SA pass 2 M1: doubled separator, `\??\` | **Resolved** (text-level refusal of `/??/`, separator collapse after the prefix, rows for each spelling incl. "realpath is NEVER called"). Residual: rooted without drive (WARN above) |
| SA pass 2 M: letterless-volume profile (FSLogix/VHDX) refused as `remote` with a false fix line | **Not fixed, not recorded.** Fails closed (no security loss). Needs a follow-up issue and one PR sentence |
| SA pass 2 M (pre-existing): stdin decoded as cp1252 on Windows | **Not in scope**; follow-up issue |
| SA pass 2 Low: `block()` builds outside `try` | **Resolved** |
| SA pass 2 Low: bidi/zero-width in `_entry_shown` | **Resolved** |
| SA pass 2 Low: bridge True with inline copy | Code safe (never `None`); comment open (INFO) |
| SA pass 2 Low: POSIX base writable by others (rename race) | Open; Non-Goal adjacent; follow-up |
| SA pass 2 Info: Parent base not pure on Windows | Open; contract text should say "reads no other environment source" (divergence the contract caused) |
| TC M5: `unwritable` on Windows ACLs | Partly (faked `os.access` rows); unchanged |
| TC L3: real-folder leak checks flaky under concurrent hook runs | Confirmed in pass 2; unchanged; follow-up |

### Contract alignment

- Data shapes, decision order 1-8, I-4, I-6..I-9, I-7/I-7b/I-7c banners, the stamp, the Foreign-marker notice, the Stateless session, the Hop proof in three consumers, the refusal message: match.
- **Divergence (partly-met):** the Remote rule's promise "catches network paths, UNC and mapped drives alike" is not kept for a drive-less rooted base (WARN), and the Parent base is not pure on Windows (it calls `GetDriveTypeW`, `_getfullpathname`, `realpath`); the second was forced by the contract's own Remote rule. The JOURNAL already carries the mapped-drive lesson; no new entry needed beyond it.
- Off-area drift: none (empty area map; Adjacent Areas not applicable). End-User View: not applicable. No REST/SignalR/DTO surface.

### Registries (janitor)

- **MECHANISMS.md:** no new mechanism. The 2026-11-06 span edits (:43, :45, :106, :107) and the dated correction (:108) read true against the code.
- **VOCABULARY.md:** "Per-user session parent", "Foreign marker" and the correction are present and accurate.
- **JOURNAL.md:** the two 2026-11-06 entries (E1 reason list; drive table before realpath) cover this pass's WARN class; I add nothing.
- **INTEGRATION.md:** nothing to update.

### Follow-ups that should become separate issues

1. **Windows stdin decoding.** All three hooks read `sys.stdin.read()` as cp1252 (`surrogateescape`); a non-ASCII `cwd` (for example `C:\Users\José\…`) becomes mojibake and fails open as `no-index` on every call. Fixtures hide it with `PYTHONIOENCODING=utf-8`. Fix: `sys.stdin.buffer.read().decode("utf-8", "surrogateescape")` plus a row without `PYTHONIOENCODING`.
2. **Other per-session state in the shared temp folder.** `_project_paths.session_marker` (:949-952, used by `stop-dispatcher.py:168`), `concept_changed_check.py:159`, and `integration-check.py:41` (one fixed `claude-integration-check.json`, not even per session) keep state under `tempfile.gettempdir()`, with the same cross-user plant/delete exposure #271 closed for codegraph.
3. **Letterless-volume profiles (FSLogix/VHDX).** `realpath` can give `\\?\Volume{GUID}\…`, which the Remote rule treats as remote; the user gets a fix line ("set LOCALAPPDATA to a local folder") that is false. Map the volume GUID via `GetVolumePathNamesForVolumeNameW` / `GetDriveTypeW` on the volume root, or give it its own problem token; add a recorded row.
4. **POSIX base owned or writable by another user** (rename race between the check and the use): check `lstat(base)` owner/mode, or open the parent `O_DIRECTORY|O_NOFOLLOW` and use `dir_fd`.
5. **Leak checks false-fail under concurrent hook runs** (pass 2 observed it): scope the check to the fixture session keys, or mark it advisory.
6. Contract wording: restate "pure" for the Parent base as "reads no environment source but the mapping" (Windows I/O is required by the Remote rule).

---

### Summary

| Severity | Count |
|---|---|
| [CRITICAL] | 0 |
| [WARN] | 2 |
| [INFO] | 5 |

**Verdict**: `FIX THEN SHIP`

**Addendum (after the full discover finished):** a second WARN blocks merge as well. The new manifest row makes `test_plugin_manifests` fail to import under the contract's own `unittest discover` command; see its section. It is a small test-only fix.

**Honest call on merge:** nothing here is a CRITICAL. The first WARN is a two-line fix plus two rows, in the same class the two earlier rounds treated as a merge condition, so I would fix it before merging rather than defer it; its real-world reach is small (a user's own `LOCALAPPDATA` set to a drive-less path, with the project on a mapped drive). If the user prefers to ship now, it must go into the follow-up list with the others and the PR must say the Remote rule does not cover a drive-less rooted `LOCALAPPDATA`. All suites pass; parity, hashes, version, counts and doc sentences check out.

**Top priority fix**: in `session_parent_base` (all three copies) refuse a Windows base with no drive (`ntpath.splitdrive(raw)[0] == ""`) as `not-absolute` before any spelling is resolved, with rows proving `realpath` is never called for `\x` and `/x/y`.
