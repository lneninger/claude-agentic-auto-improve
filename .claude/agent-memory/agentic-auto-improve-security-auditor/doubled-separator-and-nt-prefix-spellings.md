---
name: doubled-separator-and-nt-prefix-spellings
description: Remote-rule bypass spellings that survived the #271 fix round - \\.\\Z:\x (doubled separator after the device prefix) and \??\UNC\h\s (NT prefix); plus cp1252 surrogateescape stdin in hooks and the pre-try message build in block().
metadata:
  type: feedback
---

1. `\\.\\Z:\x`, `\\?\\Z:\x`, `//.//Z:/x`: `_remote_host` drops empty segments and returns `?z:`. A check keyed on `raw[4:6]` skips them, yet Win32 opens them as the drive. Verified with `os.lstat(r"\\.\\C:\Windows")`.
2. `\??\C:\Windows` opens through Win32. `\??\UNC\h\s` has a None host and is local to `_getfullpathname`, so `_own_spellings` calls realpath on it and touches the host before any verdict.
3. On Windows, hook stdin is cp1252 with surrogateescape. Test fixtures set `PYTHONIOENCODING=utf-8` and so hide it. A non-ASCII cwd becomes mojibake and the guard fails open with no-index.
4. A `try/finally: sys.exit(2)` must start at the top of `block()`. `cg_suggestion` on a non-str `file_path` or `pattern` raised before the try.

**Why:** found in the #271 security pass 2 (2026-11-06). This host has a real mapped `Z:` (`DRIVE_REMOTE`), which is useful for offline checks: stub realpath to raise so nothing reaches the network.

**How to apply:** for every Windows path rule, judge the `_getfullpathname` form with the prefix stripped, and require `X:\` plus `GetDriveTypeW` in (2, 3, 6). Add the doubled-separator and `\??\` rows. Related: [[device-path-dotdot-and-strict-stderr]], [[unc-host-check-normpath-collapse]].
