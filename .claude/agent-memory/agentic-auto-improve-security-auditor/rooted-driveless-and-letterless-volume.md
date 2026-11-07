---
name: rooted-driveless-and-letterless-volume
description: #271 pass 3 classes - rooted base without drive (\x) is isabs on Py3.12 and skips GetDriveTypeW (cwd drive); `\\\?\Z:` / `\\?z:` judged local by empty-segment _remote_host; letterless volume realpath returns \\?\Volume{} (wall).
metadata:
  type: feedback
---

1. `ntpath.isabs(r"\x")` is True on 3.12, False on 3.13+. A drive check keyed on `stripped[1:2]==":"` skips it, and realpath/lstat hit the hook cwd's drive. Same for `1:\x` (non-letter drive, `isalpha` gate).
2. `_remote_host` drops empty segments: `\\\?\Z:\x` -> `?z:`; `\\?z:\x` (UNC server named `?z:`) also matches `\?[a-z]:`. Win32 rejects triple-separator with winerror 161 (verified on C:), so it fails closed only by luck.
3. On this host `_getfinalpathname(\\?\Volume{fba4...}\)` fails winerror 3 and realpath returns the Volume form: a junction into a letterless volume (FSLogix) yields empty host -> remote wall.

**Why:** found in the #271 security pass 3 (2026-11-06). Pass 2 had already asked for "reject rooted-without-drive" and for "require `[A-Za-z]:\`". The fix round skipped both.

**How to apply:** for every Windows path rule, add rows for `\x`, `/x`, `1:\x`, `\\\?\Z:\x` and `\\?z:\x`. Check that each earlier fix item really landed; do not trust the fix-round summary. Related: [[doubled-separator-and-nt-prefix-spellings]], [[device-path-dotdot-and-strict-stderr]].
