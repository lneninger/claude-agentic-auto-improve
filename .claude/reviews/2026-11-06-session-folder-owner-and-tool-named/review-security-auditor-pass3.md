## Security Audit: issue #271, per-user session folders (pass 3, cold context, after fix round 2)

Scope: the uncommitted diff in the `20261106-bug-271-windows-session-owner-check` worktree. I attacked the current code and did not rely on the conclusions of pass 1 or pass 2. The main targets were `session_parent_base`, `block()`, `log()`, and the installer's and bridge's escaping. Contract: `.claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md` (approved).

### Method

Every probe was read-only and offline. Each ran as `py -3 -I` (Python 3.12.10) from a scratch folder outside the repo.

- **Parity.** I compared the three hooks' copies of these functions as ASTs, with docstrings stripped: `session_parent_base`, `_remote_host`, `_own_spellings`, `_create_parent`, `resolve_session_parent` and `session_folder_problem`. All three copies are identical.
- **Spelling table.** I ran 45 hand-picked spellings through `session_parent_base` with `os.path.realpath` stubbed to record its calls.
  - Each verdict was compared with `nt._getfullpathname`, the form Win32 actually opens.
  - The real `GetDriveTypeW` was used. This host has `Z:` = `DRIVE_REMOTE`, disconnected, and it was never opened.
- **Fuzz.** 150,000 random spellings were built from separators, `..`, `.`, `?`, `C:`/`Z:`, `UNC`, `GLOBALROOT`, trailing dots and spaces, `Volume{}`, `localhost` and `C$`. For every base judged usable, the fuzz checked two things:
  - the Win32 form of `base\auto-improve-codegraph` has no remote host and sits on a drive of type 2, 3 or 6;
  - no `realpath` call targets a remote form.
- **Opens on `C:` only.** `os.lstat` ran only on `C:` paths, to see how Win32 opens the triple-separator spellings.
- **Volume probe.** I listed the volumes through the mount manager with `FindFirstVolumeW` and `GetVolumePathNamesForVolumeNameW`. I then ran `_getfinalpathname` and `realpath` on this host's one volume with no drive letter.
- **`block()`.** I called it in-process with:
  - non-string fields;
  - lone surrogates in the session paths;
  - a `tool_name` and a `session.problem` whose `__str__` or `startswith` raises;
  - a `log_event` that calls `sys.exit(0)`;
  - a `log_event` that raises `KeyboardInterrupt`;
  - a strict cp1252 stderr.

### Medium

- **M1. A drive-less rooted base (`\AppData\Local`, `/AppData/Local`, `\GLOBAL??\…`) is judged local. It skips the drive table, and `realpath`, `lstat` and `mkdir` then act on the drive of the hook's cwd.**
  File: `.claude/addons/codegraph/hooks/codegraph-first-guard.py:301` and `:313-314`. The tracker (`:103+`) and reset (`:137+`) copies are identical.
  **Exploit scenario:**
  1. `LOCALAPPDATA` is `\Users\u\AppData\Local`, which has no drive.
  2. On Python 3.12, `ntpath.isabs` returns True for a rooted path without a drive. Python 3.13+ returns False, so the verdict depends on the Python version.
  3. `stripped[1:2]` is not `:`, so `GetDriveTypeW` is never asked.
  4. Reproduced: `_own_spellings` calls `realpath('\AppData\Local')`, `realpath('\AppData\Local')` again and `realpath('D:\AppData\Local')`. The `D:` comes from the probe's cwd. The verdict is `('\AppData\Local', None)`, which means usable.
  5. When the hook's cwd is a mapped drive (a project opened on `Z:`), every one of those calls goes to that drive's server before any verdict. `resolve_session_parent` then runs `lstat` and `mkdir` on `Z:\Users\u\AppData\Local\auto-improve-codegraph`.
  6. With the drive connected, `realpath` returns `\\server\share\…`, so the base is refused. The refusal comes after the contact.
  7. With `realpath` unable to resolve the root, the base is accepted and the session parent lands on the share. That is the plant-a-marker setup #271 exists to prevent.

  Pass 2's fix list asked for exactly this: "reject any raw that is rooted without a drive" and "require `^[A-Za-z]:\\`". Neither was implemented. No table row covers a rooted base without a drive.

  **Impact:** The precondition is the victim's own unusual `LOCALAPPDATA`, plus a cwd on a network drive. The network host touched is the cwd's own server, not a host an attacker picks. The bigger problems are the contract divergence ("a set but relative value gives `not-absolute`") and a verdict that differs between Python versions.

  **Fix:** On `nt`, before any other rule, return `not-absolute` when `ntpath.splitdrive(raw)[0] == ""` and `raw` does not start with two separators. That makes 3.12 behave like 3.13. Then key the drive check off `nt._getfullpathname(stripped)` and require `^[A-Za-z]:\\` there, so that a cwd-relative form can never skip `GetDriveTypeW`. Add rows for `\x` and `/x` that assert two things: the verdict is `not-absolute`, and `realpath` is never called.

### Low

- **L1. A drive designator that is not an ASCII letter (`1:\x`, ` :\`, `.:\`) skips `GetDriveTypeW` and reaches `realpath`.**
  File: same function, `:313-314` (`letter.isalpha()` gates the drive-table call). Reproduced: the verdict for `1:\x` is usable, and `realpath('1:\x')` was called three times.
  `DefineDosDeviceW` lets any process of the user create a per-logon DOS device named `1:` that points at `\Device\Mup\host\share`. `RtlDetermineDosPathNameType` classes `1:\` as drive-absolute.
  The precondition is code already running as the user, so the impact is low. `\\?\1:\x` is already judged remote, which makes the two spellings inconsistent.
  **Fix:** Use the M1 fix: anything other than `[A-Za-z]:\` after full-path resolution is `remote`.

- **L2. Leading separators other than the exact device prefix are judged local, because `_remote_host` drops empty segments and `_LOCAL_DEVICE_HOST_RE` accepts a UNC host spelled `?z:`.**
  Reproduced verdicts: `\\\?\Z:\x`, `\\\.\Z:\x`, `\\?z:\x` and `//?z:/x` are all judged usable. Each has `Z:` (`DRIVE_REMOTE`) or a host named `?z:`, and `GetDriveTypeW` was never asked.
  - Win32 treats the triple-separator forms as UNC with an empty server. `os.lstat` on `\\\?\C:\Windows`, `\\\.\C:\Windows`, `////?/C:/Windows` and `\/\?\C:\Windows` all fail with `ERROR_BAD_PATHNAME` (161). `resolve_session_parent` then ends in `check-failed`.
  - `\\?z:\x` is a UNC path to a server literally named `?z:`. I did not open it, to avoid any name resolution.

  So these fail closed because Win32 refuses them, not because the Remote rule catches them.
  **Fix:** On `nt`, return `remote` when the separator-normalised text starts with `//` and its first four characters are not exactly `//?/` or `//./`. Every real UNC base is remote anyway, so this costs no legitimate case. Add the four rows above.

- **L3 (availability, fails closed). A profile reached through a reparse point into a volume with no drive letter is refused as `remote`, with a fix line that is false.**
  This is the FSLogix/VHDX question from pass 2. It is now partly verified on this host.
  - The mount manager lists `\\?\Volume{fba4bcd4-…}\` with no path names.
  - `nt._getfinalpathname` on that volume fails with `winerror 3`.
  - `ntpath.realpath` (non-strict) returns `\\?\Volume{fba4bcd4-…}\` unchanged.
  - CPython's `_getfinalpathname_nonstrict` handles a junction the same way. When `C:\Users\<u>` is a junction to `\??\Volume{GUID}\Profile` (the FSLogix profile-container layout, as I understand it; I did not reproduce it, because creating a junction is not read-only), the fallback follows the junction with `_readlink_deep`. It yields `\\?\Volume{GUID}\Profile\AppData\Local`.
  - `_remote_host` gives `""`, so the base is judged `remote`.

  Every source Read, Grep and Glob in an indexed project then blocks with `session-state-unusable`, and no retry is offered. The fix line says "set LOCALAPPDATA to an absolute, local folder", but it already is one.

  **Judgement:** A `\\?\Volume{GUID}\` name is minted by the mount manager only for local volumes; network shares never get one. The `realpath` form of a drive-letter base that turns out to be a volume GUID is therefore not evidence of a network path.

  **Recommendation (follow-up, not a blocker):** Accept a volume-GUID spelling that comes from the `realpath` form only when both of these hold:
  1. That exact `\\?\Volume{GUID}\` appears in the `FindFirstVolumeW`/`FindNextVolumeW` enumeration. This is a mount-manager query with no file open, so a per-logon DOS device a user defines named `Volume{…}` is not trusted.
  2. `GetDriveTypeW` on it returns 2, 3 or 6.

  Keep the written `\\?\Volume{…}` and `GLOBALROOT` forms remote. At the very least, give this case its own problem token (for example `volume-without-letter`) and an accurate fix line. Add a row that skips with a printed reason when no letterless volume reachable through a junction exists.

- **L4. Undecidable cases are refused with a misleading message, and the drive-type rule is a denylist.**
  - `except Exception: return None, "remote"` (`:320-321`). When `ctypes` cannot load, every drive-letter base on the machine becomes `remote`. That happens when WDAC or AppLocker blocks `_ctypes.pyd`, or on a stripped embedded Python. The message then reads "the setting points at a network share", which is false.
  - The rule refuses only types 0, 1 and 4, so `DRIVE_CDROM` (5) and any value not defined today proceed. That has no security effect today: 5 ends in `cannot-create`. But it contradicts the stated "2/3/6 proceed".

  **Fix:** Use an allowlist: proceed only on `(2, 3, 6)`. Report an exception as `check-failed` with the exception text as the detail. It still fails closed, and the diagnosis becomes true.

- **L5. Installer escaping covers only the refusal. The `--check` path still echoes raw entries.**
  - `_entry_shown` (`auto_improve_finish_install.py:2516-2525`) correctly escapes characters in the categories Cf, Cc, Cs, Zl and Zp, plus the backtick, and caps the length.
  - But `check_addon`'s `message` (`:2566`) and `_render_text` (`:3631`, `finding.get("entry")`) print the same entries from settings files the user may not own, with no escaping. Bidi controls and newlines reach the terminal through `addon --check`. This is pre-existing and outside the diff, but it is a sibling of the surface just fixed.
  - Invisible characters in the Mn category are not escaped either: U+034F, the variation selectors U+FE00-FE0F, and U+E0100 onward. They can hide a difference between the entry shown and the entry stored.

  **Impact:** A misleading line only.
  **Fix:** Route both sites through `_entry_shown`. Optionally also escape Mn characters that have no visible base.

- **L6. Bridge comment versus expression (pass 2 Low, unchanged).** `_claude_paths.py:196-204`: the comment says "True means this bridge uses the helper's native tree functions". A helper that declares `TREE_HOP_REFUSAL` but lacks `worktree_own_root` makes the export True while the bridge uses the inline copy. No helper has that shape today, so the impact is nil. **Fix:** Correct the comment, or export `TREE_HOP_REFUSAL and callable(_native_own_root)`.

- **L7 (pre-existing, carried, still unfixed).** The hooks read stdin through `sys.stdin.read()`. Re-verified: piped stdin on this host is `cp1252` with `surrogateescape`, and `C3 81` decodes to `'\xc3\udc81'`. A non-ASCII project path therefore fails open as `no-index`. This is outside #271. File it as its own issue if that has not been done.

### Informational

- **`block()` cannot end in exit 0.** The `try` now opens on the first statement after the nested `build` definition, and the `finally: sys.exit(2)` covers everything. All 8 hostile probes exited 2:
  - a non-string `file_path` or `pattern`;
  - surrogates in `folder` and `parent`;
  - a `tool_name` whose `__str__` raises;
  - a `session.problem` whose `startswith` raises;
  - `log_event` calling `sys.exit(0)`, overridden by the `finally`;
  - `log_event` raising `KeyboardInterrupt`;
  - `sys.stderr = None`.

  `cg_suggestion` reads only `str` values. The only route to exit 0 left is an exception in `evaluate()` reaching the I-4 catch-all, which the contract keeps. Example: `RecursionError` from a deeply nested `availability.json` in the user's own folder, or from a repo's `.mcp.json` (`_read_json_file` catches only `OSError` and `ValueError`). A repo author can already turn the gate off legitimately through `disabledMcpjsonServers`, so this adds no capability.
- **`log()` cannot hide a block record.** `block()` never calls `log()`. Its record goes through `log_event`, which never raises and returns False only when the log folder is missing or a write fails. The block record's `details` values are surrogate-escaped. One small gap: the block record carries no `session_id=session.key`, while the fail-open records do. Add it for correlation.
- **Symlink to UNC.** A local, fixed-drive base whose path holds a symbolic link to `\\h\s` reaches `realpath`, which follows it before the refusal. This is inherent: following the link is the only way to see it. Creating it needs the user's own symlink privilege, so I accept it.

### Checks that held (verified this pass)

- `\??\…` in every spelling is refused from the text, with no `realpath` call. `\\??\UNC\…` (UNC host `??`) and `\GLOBAL??\…` are covered too; the latter falls into M1.
- `\\.\\Z:\x`, `\\?\\Z:\x`, `//.//Z:/x` and plain `Z:\x` are refused through `GetDriveTypeW` = 4, with no `realpath`.
- `\\.\C:\..\UNC\h\s` and the variants `x\..\..`, `\\`-doubled and `\. .\..` are refused by the `..` rule.
- `\\.\C:\.. \UNC`, `\\.\C:\...\UNC`, `\\.\C:\x\.. .\UNC` and `\\.\C:\x\․․\UNC` (U+2024) stay on `C:`. `_getfullpathname` confirms that Win32 does not collapse those segments.
- These are all `remote`: `\\?\GLOBALROOT\…`, `\\.\GLOBALROOT\…`, `\\?\Volume{…}`, `\\.\PhysicalDrive0`, `\\localhost\C$`, `\\?\UNC\…`, `\\?\unc\…` and `\\.\unc\…`.
- `C:x` is `not-absolute`. `\\?\C:x` is `remote`. An embedded NUL is `remote`.
- The fuzz (150,000 cases) found no usable verdict whose Win32 form names a real remote host or opens a `DRIVE_REMOTE` letter. Its only hits were the M1, L1 and L2 classes, plus `ntpath.join` artefacts such as `\\?\C:` + name = `\\?\C:name`. Those end in `cannot-create`.
- On an unusable verdict, the reset hook prunes nothing (`:468-474`). The pruner keeps its link, owner and re-check rules.

### Verdict

**pass-with-conditions** (NEEDS FIXES in this agent's scale).

- **Release blockers: none.** No spelling found lets a network location become the Per-user session parent without either the victim's own odd setting or Win32 refusing the path.
- **Condition before merge:** M1, a pass 2 fix item that was not implemented. Its few lines also close L1 and L2. Add the rows for `\x`, `/x`, `1:\x`, `\\\?\Z:\x` and `\\?z:\x`.
- **Follow-ups:** L3 (the volume-GUID wall: at least a distinct problem token, ideally the mount-manager acceptance), L4, L5, L6, and L7 (file it as an issue).
