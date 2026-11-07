## Security Audit: issue #271, per-user session parent (pass 4, cold context, after fix round 3)

Scope: `session_parent_base` and `resolve_session_parent` in the three hooks under `.claude/addons/codegraph/hooks/`, plus the installer's `_entry_shown` sites. I tested the current uncommitted diff in the `20261106-bug-271-windows-session-owner-check` worktree. I did not rely on what passes 1 to 3 concluded. Contract: `.claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md` (approved).

### Method

All probes were read-only and offline. They ran on Python 3.12.10 from a scratch folder outside the repo. Only `C:` was ever opened. `Z:` (`DRIVE_REMOTE`, disconnected) was asked about only through `GetDriveTypeW`, which reads the drive table and opens nothing.

- **Parity.** I extracted these functions and constants from each hook and diffed them: `session_parent_base`, `_base_shown`, `_create_parent`, `resolve_session_parent`, `session_folder_problem`, `_remote_host`, `_own_spellings`, `_is_link_stat`, `PARENT_PROBLEMS` and `_LOCAL_DEVICE_HOST_RE`.
- **Fuzz.** I ran 158,550 bases through all three copies, with `os.path.realpath` stubbed so the probe could record its calls.
  - 8,550 bases came from a structured product of three parts:
    - 19 prefixes, among them `\\?\`, `\\.\`, `//?/`, `\\?/`, `/\?\`, `\??\`, `/??/`, a triple separator, `\\?\\`, `\`, `/`, `\\?` and `\\??\`.
    - 30 drive parts, among them fullwidth `Ｃ:`, `C：`, `1:`, ` C:`, `C: `, `C:.`, `UNC\h\s`, `GLOBALROOT`, `Volume{}`, `PIPE`, and the `..` variants `.. `, `.. .`, `..\t`, `...`, `....`, ` ..` and `..::$DATA`.
    - 15 suffixes, covering 8.3 names, ADS, trailing dots and spaces, and `..` chains.
  - 150,000 bases were random strings over separators, fullwidth and division-slash lookalikes, `?`, `.`, `:`, `UNC`, `GLOBALROOT`, `Mup`, tab and `~1`.
  - The oracle for each base had three checks:
    - the three copies return the same verdict;
    - every `realpath` call targets a text whose `GetFullPathNameW` form is `[A-Za-z]:\` on a drive of type 2, 3 or 6;
    - for every base judged usable, `GetFullPathNameW(join(base, "auto-improve-codegraph"))` satisfies the same rule.
- **Rows.** I ran 37 hand-picked rows and recorded the `realpath` calls for each.
- **Drive type.** I stubbed `GetDriveTypeW` to return 0 through 7 and -1. I also stubbed it to raise, and set `sys.modules["ctypes"] = None`.

### Answers to the five questions

1. **Pass-3 M1, L1 and L2 are closed.** Each row below gives its verdict with zero `realpath` calls, in all three copies:
   - `not-absolute`: `\x`, `/x`, `\AppData\Local`, `\GLOBAL??\C:\x`, `1:\x`, ` :\x`, `.:\x` and fullwidth `Ｃ:\x`.
   - `remote`: `\\\?\Z:\x`, `\\\.\Z:\x`, `\\?z:\x`, `//?z:/x`, `////?/C:/Windows` and `\/\?\C:\Windows`.
   - The fixes for pass-3 L4 and L5 also landed:
     - Drive types 0, 1, 4, 5, 7 and -1 are `remote`, and only 2, 3 and 6 proceed.
     - A `GetDriveTypeW` that raises gives `check-failed` with `OSError: …`. A missing `ctypes` gives `check-failed` with `ModuleNotFoundError: …`. Both reach `resolve_session_parent` with the detail kept.
     - The installer's `--check` message (`auto_improve_finish_install.py:2567`) and `_render_text` (`:3632`) now go through `_entry_shown`. U+034F, U+FE00-FE0F and U+E0100-E01EF are escaped (verified).
2. **No written spelling reaches `realpath`, `lstat` or `mkdir` on a network or drive-less location.** The fuzz found no `realpath` call on a non-local text. Its only usable verdicts whose opened form fails the oracle are the bare device-drive bases `\\?\C:` and `\\.\C:`, in every separator spelling (L2 below). They end in `FileNotFoundError` (winerror 2) and then `cannot-create`.
   - `\\.\C:\.. \UNC\h\s`, `\.. .\`, `\..\t\`, `\...\` and `\....\` are judged local, and they are local. `GetFullPathNameW` does not collapse those segments, so the path opened stays on `C:`.
   - One gap remains, and it is not a spelling: the drive table is never asked about a drive letter that only the `realpath` form contains (L1).
3. **The new order refuses no legitimate local base.** These are all usable:
   - `C:\Users\x\AppData\Local`, `\\?\C:\Users\x\AppData\Local`, `\\.\C:\…` and `C:/Users/x/AppData/Local`;
   - a lower-case form with a doubled trailing separator, the 8.3 form, and this host's real `LOCALAPPDATA`.

   The `//` rule and the drive-less rule are both gated on `os_name == "nt"`, so POSIX does not change. On POSIX:
   - `/home/u/.cache` and `//srv/share` are usable;
   - `relative` and `\\x` are `not-absolute`;
   - `HOME` plus `.cache` is the fallback, and an empty environment gives `unset`.

   This host has no `subst` drives. Creating one is not read-only, so I did not test one. A `subst` of a local folder reports `DRIVE_FIXED` by documented behaviour. A junction to another lettered local volume resolves through `realpath` to `X:\…` and is accepted. The letterless-volume junction is the known FSLogix wall, which is out of scope and not made worse.
4. **`check-failed` cannot turn into an allow.** In `resolve_session_parent`, every exception, including one raised by `session_parent_base`, returns `check-failed`. The resulting `Session.problem` makes the session stateless. `evaluate` step 8 (`codegraph-first-guard.py:1024-1030`) returns `block` / `session-state-unusable` whenever `problem` is set, and the retry ticket is never readable in a stateless session. The fail-open reasons (steps 1-6) do not depend on Session state, as the contract intends.
5. **The three hook copies are identical in code.** The only differences are a docstring on `_is_link_stat` ("(junction)") and the position of the section comment above `PARENT_NAME`. All verdicts in the fuzz agreed across the copies.

### Low

- **L1. A drive letter that appears only in the `realpath` form is never checked in the drive table. A link from a local base to a mapped drive is judged local when `realpath` cannot reach the target.**
  File: `codegraph-first-guard.py:317-340`. The tracker (`:137+`) and reset copies are identical. `GetDriveTypeW` is asked only about `stripped`'s letter. For `realpath` outputs, the loop at `:336-340` checks only `_remote_host`, and that returns `None` for any `X:\…`.
  Reproduced with a stubbed `realpath`: `C:\l\AppData\Local` resolves to `Z:\share\AppData\Local`, and the verdict is `('C:\\l\\AppData\\Local', None)`. The same base written directly as `Z:\…` gives `remote`.

  **Exploit scenario:**
  1. The user's own `LOCALAPPDATA` chain holds a directory symlink to a mapped drive, for example `mklink /D C:\l Z:\x`.
  2. The mapped drive is disconnected, or its target denies `GetFinalPathNameByHandle`.
  3. `realpath` falls back to `_readlink_deep` and returns `Z:\x\…` instead of `\\?\UNC\server\…`.
  4. The base is judged local, and `lstat` and `mkdir` then act through the link on the mapped drive.

  When the drive is connected, `realpath` returns the UNC form and the base is refused, after the contact pass 3 already accepted as inherent.

  **Impact:** The preconditions are the victim's own symlink (symlink privilege or developer mode) and a mapped drive that does not resolve. No attacker-chosen spelling reaches this. This class is not new in this round.
  **Fix:** In the `texts` loop, also run every spelling whose separator-normalised form starts with `[A-Za-z]:/` (and every `\\?\X:` / `\\.\X:` form) through the same `GetDriveTypeW` allowlist (2, 3, 6). That covers the `realpath` outputs. Add a row with `realpath` stubbed to return `Z:\…`.

- **L2. A bare device drive base (`\\?\C:`, `\\.\C:`, `//?/C:`, `\\?/C:`, `/\?\C:`, `\/.\C:`) is judged usable. The text judged is `C:\`, but the object opened is `\??\C:auto-improve-codegraph`.**
  File: `:312-340`. `ntpath.join(r"\\?\C:", name)` gives `\\?\C:auto-improve-codegraph`, which has no root separator.
  - `os.lstat` on it gives `FileNotFoundError` (winerror 2), so the result is `cannot-create`, which fails closed.
  - It is inconsistent with `\\?\C:x`, which is refused as `remote` because `_remote_host` sees a 3-character segment.
  - Residual risk: a per-logon DOS device that the user's own process defines under the name `C:auto-improve-codegraph`, pointing at `\Device\Mup\…`, would be followed. The precondition is code already running as the user.

  **Fix:** On `nt`, for a device form, require `rest[2:3] == "\\"` (a root after the drive), or else return `not-absolute`. Add rows for `\\?\C:` and `\\.\C:`.

### Informational

- `_entry_shown` (`auto_improve_finish_install.py:2521`) writes U+034F and U+FE00/U+FE0F as literal invisible characters in the source. Spell them as `"\u034f"`, `"\ufe00"` and `"\ufe0f"` so a reviewer can see them.
- The Hangul fillers U+115F, U+3164 and U+FFA0 (category Lo, invisible) are not escaped. This is a cosmetic, misleading-line risk only.
- The finding's `file` field is printed unescaped. It is a path the installer built, not settings text, so the risk is negligible.

### Verdict

**pass**

- **Release blockers: none.** M1, L1 and L2 from pass 3 are closed, along with L4 and L5. No written spelling of `LOCALAPPDATA` gets a network or drive-less location judged usable. `check-failed` always blocks, and the copies match.
- **Follow-ups (non-blocking):**
  - L1: check the drive table for drive letters in the `realpath` form.
  - L2: reject a bare device drive with no root.
  - The Informational escaping nits.
- **Out of scope, not made worse:** non-ASCII stdin decoding, other modules' temp-folder state, the FSLogix volume-GUID wall, and the POSIX base race.
