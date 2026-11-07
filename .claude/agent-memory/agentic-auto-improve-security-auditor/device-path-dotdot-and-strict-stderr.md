---
name: device-path-dotdot-and-strict-stderr
description: Two bypass classes found in #271 hooks - \\.\C:\..\UNC\h\s passes a raw _remote_host check (host ?c:) but Win32 opens \\.\UNC\h\s; and stderr.reconfigure(encoding="utf-8") makes print strict so a lone surrogate sends block() to the allow catch-all.
metadata:
  type: feedback
---

1. Win32 collapses `..` inside `\\.\` device paths AT OPEN (`os.lstat(r'\\.\C:\..\D:\Dev')` opens D:\Dev; `\\?\` does not, winerror 123). Python `ntpath.normpath` keeps the `C:` (differs from Win32). So a raw-text host check giving `?c:` is bypassable to UNC; `nt._getfullpathname` (no I/O) shows the Win32 form. Also `\\?\Z:\` mapped drive skips realpath in `_own_spellings`.
2. `sys.stderr.reconfigure(encoding="utf-8")` sets errors=strict (was backslashreplace); any lone surrogate in banner text (env value, Grep pattern from JSON `\ud800`) raises before `sys.exit(2)` -> I-4 catch-all exits 0 = allow.

**Why:** issue #271 security pass (2026-11-06), M1 and M2; both reproduced offline.

**How to apply:** for every remote/same-host rule, add `\\.\C:\..\UNC\h\s` and `//./C:/../UNC/h/s` rows and judge `_getfullpathname`. For every hook whose block path prints, check the error handler and that exit 2 is in a finally. Related: [[unc-host-check-normpath-collapse]].
