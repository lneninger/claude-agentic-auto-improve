## Security Audit: issue #271, per-user session folders and the tool-named refusal (pass 2, cold context, after the fix round)

Scope: the uncommitted diff in the `20261106-bug-271-windows-session-owner-check` worktree. I attacked the current code. I did not rely on pass 1's conclusions. Contract: `.claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md` (approved).

How I tested. All probes were read-only and offline, and each was run as `py -3 -I` from a scratch folder outside the repo:
- `session_parent_base` was called in-process with `os.path.realpath` stubbed, so that no spelling could reach a network host.
- `os.lstat` was run only on `C:` paths, to see how Win32 opens each spelling.
- `GetDriveTypeW` and `QueryDosDeviceW` were run over all drive letters.
- An AST parity check compared the three hooks.
- `block()` was called in-process with hostile `tool_input` values and lone surrogates.
- Raw UTF-8 bytes were piped into the guard's stdin.

This host has a real mapped network drive, `Z:`. It is `DRIVE_REMOTE`, mapped to `\Device\LanmanRedirector\;Z:...\192.168.17.128\irrigation-electron`. I never opened `Z:` itself.

Parity: `session_parent_base`, `_remote_host`, `_own_spellings`, `_create_parent`, `resolve_session_parent`, `session_folder_problem`, `_base_shown` and `_is_link_stat` are AST-identical in the guard, the tracker and the reset hook (docstrings and annotations stripped).

### Medium

- **M1 is not fully closed: a doubled separator after the device prefix sends a mapped network drive past the Remote rule.** File: `.claude/addons/codegraph/hooks/codegraph-first-guard.py:301-329`. The tracker and reset copies are identical.
  **Exploit scenario:**
  1. `LOCALAPPDATA` is set to `\\.\\Z:\x`, `\\?\\Z:\x`, `//.//Z:/x` or `\\.\/Z:\x`, where `Z:` is a mapped network drive.
  2. `_remote_host` drops empty segments and returns `?z:`, which counts as local.
  3. The mapped-drive branch runs only when `raw[4:5].isalpha() and raw[5:6] == ":"`. Here `raw[4]` is the second separator, so the branch is skipped.
  4. `_own_spellings` does not resolve a path already written in device form. So neither `realpath` nor `GetDriveTypeW` ever runs.
  5. Confirmed on this host against the real `Z:`. All four spellings return `(raw, None)`, which means usable. The single-separator controls `\\.\Z:\x` and `\\?\Z:\x` return `remote`.
  6. Win32 opens the doubled-separator form as the drive: `os.lstat(r"\\.\\C:\Windows")`, `os.lstat(r"\\?\\C:\Windows")` and `os.lstat("//.//C:/Windows")` all succeed. `_getfullpathname` gives `\\.\Z:\x`. So the Per-user session parent is created on `\\192.168.17.128\irrigation-electron`.

  A second spelling family does the same thing: the NT prefix `\??\`.
  1. `os.lstat(r"\??\C:\Windows")` succeeds. Win32 passes the `\??\` prefix to the object manager unchanged.
  2. `ntpath.isabs(r"\??\UNC\h\s")` is True. `_remote_host` returns None, because the text starts with a single separator. `_getfullpathname` gives `D:\??\UNC\h\s`, which also judges local.
  3. `_own_spellings` then calls `os.path.realpath(r"\??\UNC\h\s")`. This opens `\\h\s` (SMB, NTLM) *before* the verdict. That breaks the same-host rule's "refuse before probe" property (JOURNAL 2026-11-05).
  4. When the host answers, `realpath` returns `\\h\s` and the base is judged remote, but only after the contact. When the share root cannot be resolved (offline, or access denied at the root, both in realpath's tolerated winerror list), `realpath` returns the input unchanged. The base is then judged usable, and every later `lstat`/`mkdir`/`open` goes to the share.
  5. `\??\Z:\x` takes the same path.

  **Impact:** The contract's Non-Goals say that on Windows "the remote rule catches network paths, UNC and mapped drives alike". That claim is false for these spellings. A session parent on a share that others can write puts back the plant-a-marker attack that #271 closes (the guard opens from any plain `turn.json`, I-6). The precondition is that the victim's own `LOCALAPPDATA` holds one of these spellings, which keeps this at Medium and not High. It is the same class as pass 1's M1, and the fix round claimed to close that class.
  **Fix:** Judge the normalised form only, and key every drive check off it, never off `raw` offsets:
  1. `full = ntpath._getfullpathname(raw)`. Reject (`remote`) any `raw` whose first separator-normalised segment is `??`, and any raw that is rooted without a drive (`\x`, which resolves against the cwd's drive).
  2. Strip a leading `\\?\` or `\\.\` from `full`. Require `^[A-Za-z]:\\`, else `remote`.
  3. Call `GetDriveTypeW(letter + ":\\")` for every base, including the plain `Z:\` form. Accept only `DRIVE_REMOVABLE` (2), `DRIVE_FIXED` (3) and `DRIVE_RAMDISK` (6). Anything else, or any exception, is `remote`.
  4. Only then run `_own_spellings` on the plain drive form, which catches a symlink or junction that leads to UNC.

  Add Remote-rule table rows for `\\.\\Z:\x`, `\\?\\Z:\x`, `//.//Z:/x`, `\\.\/Z:\x`, `\??\UNC\h\s` and `\??\Z:\x`, with `GetDriveTypeW` patched to return 4 for `Z`. Add a row that asserts `realpath` is never called for a `\??\` base. Also add plain `Z:\x` with `realpath` returning its input (the unresolvable-root case), with `GetDriveTypeW` patched to 4, expecting `remote`. The current code accepts that plain `Z:\x` case, because `GetDriveTypeW` is only consulted in the device branch.

- **Legitimate local users whose profile sits on a volume with no drive letter are likely refused as `remote`, and the fix text then tells them something false.** File: `codegraph-first-guard.py:313-317`, through `_own_spellings` → `os.path.realpath`. Unverified on this host; it needs a junction or symlink to a letterless volume, and creating one would not have been a read-only probe.
  **Scenario:**
  1. On FSLogix or VHDX profile containers (Azure Virtual Desktop, Citrix, many VDI fleets), `C:\Users\<u>` is a reparse point into an attached volume that has no DOS drive letter.
  2. With `VOLUME_NAME_DOS`, `GetFinalPathNameByHandle` cannot name a drive letter for that volume. CPython's non-strict `realpath` then falls back to `_readlink_deep`, which returns the reparse target `\\?\Volume{GUID}\...`.
  3. `_remote_host` gives `""`, which the rule treats as remote by design.
  4. From then on, every source Read/Grep/Glob on an indexed project blocks with `session-state-unusable`, and no retry is offered. The fix line says "set LOCALAPPDATA to an absolute, local folder you own", but the folder already is local.

  The contract itself says a base that is a junction "is legitimate (a moved AppData)". It also made the empty host remote. These two rules collide whenever the junction's target is a volume GUID path.
  **Impact:** No security loss, because this fails closed. It is an availability wall for a whole class of enterprise Windows users, with a misleading diagnosis.
  **Fix:**
  1. When the only spelling with a non-local host is the `realpath` form, and that form starts with `\\?\Volume{`, take its volume GUID path. Map it with `GetVolumePathNamesForVolumeNameW`. Judge it local when `GetDriveTypeW` on the volume root (`\\?\Volume{GUID}\`) returns 2, 3 or 6.
  2. Or, at the least, give `remote` a distinct problem token for "volume without a drive letter", with an accurate fix.
  3. Record the real behaviour with a row that skips with a reason when no letterless volume exists.

- **Pre-existing, outside this diff: on Windows the guard decodes stdin as cp1252 with `surrogateescape`. Any non-ASCII project path therefore becomes mojibake and fails open as `no-index`.** File: `codegraph-first-guard.py:1285` (`sys.stdin.read()`). The tracker (`:335`) and reset (`:453`) read stdin the same way.
  **Scenario:**
  1. Confirmed on this host: piped `sys.stdin.encoding` is `cp1252` and `errors` is `surrogateescape`. The UTF-8 bytes `C3 81 D1 81` ("Ás") decode to `'Ã\udc81Ñ\udc81'`.
  2. Claude Code writes UTF-8 JSON. So a payload whose `cwd` is `C:\Users\José\proj` or `C:\Users\Сергей\proj` reaches `index_verdict` as a path that does not exist.
  3. `fail-open:no-index` follows on every call. The server check misreads the config the same way.
  4. The same decoding is how lone surrogates (pass 1's M2 trigger) reach the guard naturally, with no hostile input at all.
  5. The test fixtures hide this. They run every hook with `PYTHONIOENCODING=utf-8` (`.claude/hooks/tests/_addon_fixture.py:625`, `.claude/hooks/tests/test_addons.py:85`), so no row ever sees the production decoding.

  **Impact:** The gate silently does nothing for every Windows user whose project path or user name has a non-ASCII character. This is not a cross-user exploit. It is not introduced by #271 and does not block this merge, but it should be filed.
  **Fix:** In all three hooks, read `sys.stdin.buffer.read()` and decode it as UTF-8 (`errors="surrogateescape"` keeps the I-4 behaviour on garbage). Add a row that runs a hook with `PYTHONIOENCODING` removed and a non-ASCII `cwd`.

### Low / Informational

- **`block()` still builds its message outside the `try/finally`. A non-string field of `tool_input` raises before `sys.exit(2)` and ends in the I-4 catch-all, which allows.** File: `codegraph-first-guard.py:1142` (`cg_suggestion`), lines 1100-1106 and 1119-1122.
  Confirmed in-process:
  - `block("source-target", "Read", {"file_path": 1, "path": "src/a.cs"})` raises `TypeError` (from `Path(1)`).
  - `block(..., "Grep", {"pattern": 5, "path": "src/a.cs"})` raises `TypeError` (from `5[:80]`).
  - In both cases `evaluate` had decided "block", because `extract_targets` takes the first *string* field (`path`), while `cg_suggestion` takes the first *truthy* field.

  Lone surrogates in every printed field, and in the log details, now print as escapes and exit 2. Both the `session-state-unusable` and the `retry-ticket-unwritten` banners were probed. So M2 is closed for text.
  Reachability depends on the host validating the tool schema before PreToolUse. Claude Code's schemas make `file_path` and `pattern` strings, which is why this is Low and not Medium.
  **Fix:** Start the `try:` at the first line of `block()`, so that `finally: sys.exit(2)` covers building the message. In `cg_suggestion`, read only `str` values, with the same key order as `extract_targets`. Add rows for both payloads above.

- **`_entry_shown` does not escape bidi and zero-width format characters.** File: `.claude/scripts/auto_improve_finish_install.py:2511`. `_ENTRY_UNSAFE_RE` covers C0, DEL, C1, U+2028/2029, surrogates and the backtick. It does not cover U+200B-U+200F, U+202A-U+202E, U+2066-U+2069 or U+FEFF. A `permissions.allow` entry in a cloned repo's `.claude/settings.json` (text the user may not own) can show the user a different tool name from the one stored (the Trojan Source pattern). The impact is a misleading refusal line, nothing more. **Fix:** Add `\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff` to the class. Better still, escape every character for which `unicodedata.category(ch)` is `Cf`, `Cc`, `Cs`, `Zl` or `Zp`.

- **The bridge's `TREE_HOP_REFUSAL` can be True while it uses the inline `worktree_own_root`.** File: `.claude/scripts/_claude_paths.py:201-204`. A helper that declares the constant but lacks `worktree_own_root` makes the export True, but the bridge picks `_inline_worktree_own_root`. The comment says "True means this bridge uses the helper's native tree functions". No real helper has this shape today, so the impact is nil. The text and the expression disagree. **Fix:** Pick one of the two:
  - export `TREE_HOP_REFUSAL and callable(_native_own_root)`;
  - correct the comment.

- **POSIX: the parent's owner and mode are checked, but its base is not. A base that another user can write leaves a check-to-use window.** File: `resolve_session_parent`, `:383-401`. If the attacker owns `$XDG_CACHE_HOME`, they can rename the victim's checked `auto-improve-codegraph` folder and put a folder of their own in its place between step 2 and `has_plain_file` or `open`. That plants a marker. This falls under the contract's Non-Goal (a shared folder the user chose), but the Non-Goal's sentence "the owner and mode checks still catch a planted parent" is only true without that race. **Fix (optional):** Also check `os.lstat(base)` for `st_uid in (getuid(), 0)` and no world or group write without the sticky bit. Or open the parent with `O_DIRECTORY|O_NOFOLLOW` and use `dir_fd` for every later access.

- **Info: the Parent base is no longer pure.** The contract says the Parent base rule "reads ONLY the mapping". On Windows it now does I/O: `realpath`, `GetDriveTypeW`, and `_getfullpathname`, which depends on the cwd for a rooted base. The contract's Remote rule does require `_own_spellings`, so this is a divergence the contract itself caused. The data-architect should restate it, so that "pure" means "no other environment source".

### Checks that held

- `\\.\C:\..\UNC\h\s`, `//./C:/../UNC/h/s` and the mixed-slash, `\/.\` and `x\..\..` variants are all judged `remote`.
- `\\?\UNC\…`, `\\?\unc\…`, `\\.\UNC\…`, `\\?\GLOBALROOT\…` (both forms), `\\.\pipe\…`, `\\?\Volume{…}`, `\\localhost\C$`, `\\127.0.0.1\c$` and `\\h\s\..\..\C:\x` are all `remote`.
- `C:x` is `not-absolute`.
- `\\.\C:\.. \UNC\h\s` (trailing space) and `\\.\C:\...\UNC\h\s` stay on `C:`. Win32 does not collapse those segments, as `_getfullpathname` confirms.
- Single-separator device spellings of the real mapped `Z:` are `remote`.
- On an unusable verdict, the tracker writes no marker and the reset hook deletes and prunes nothing.
- Tracker and reset messages use `errors="backslashreplace"` and always exit 0. A print failure there cannot open the gate. It can only skip a marker, which keeps the gate shut.
- `log_event` takes no lock and does not sleep, so the block path cannot hang into a hook timeout.
- The guard's Hop proof (`:91-95`) matches the contract's expression.

### Verdict

**pass-with-conditions** (in the agent's own scale: NEEDS FIXES). Pass 1's M2 is closed for text. Pass 1's M1 is not closed: the doubled-separator device spelling and the `\??\` prefix both bypass the Remote rule, and the first was reproduced against a real mapped network drive on this host. Conditions before merge:
1. The M1 residual fix and its rows.
2. Widening `block()`'s `try`.

The volume-GUID wall should get at least a recorded row and a distinct message. The stdin decoding issue should be filed as its own issue.
