---
name: realpath-form-letter-and-bare-device-drive
description: #271 pass 4 classes - drive table asked only for the written letter, not the realpath form's letter (link to disconnected mapped drive judged local); bare \\?\C: base joins to \\?\C:name (no root).
metadata:
  type: feedback
---

1. A drive-type rule applied to the written text only. `realpath` can still return `Z:\...` through its nonstrict `_readlink_deep` fallback when the target cannot be reached, and `_remote_host` returns None for any `X:\`. Stub `realpath` to return `Z:\...` to show it.
2. `\\?\C:` and `\\.\C:` (no root) pass as local. `ntpath.join` gives `\\?\C:name`, which opens the `\??\C:name` object. On this host that is winerror 2, so the result is cannot-create. `\\?\C:x` is refused, so the two are inconsistent.
3. A fuzz oracle that works: stub `realpath`, then require `GetFullPathNameW(join(base, name))` to be `[A-Za-z]:\` on a drive of type 2, 3 or 6. `.. `, `...`, `..\t` and `.. .` are NOT collapsed by `GetFullPathNameW`, so they are safe.

**Why:** found in the #271 security pass 4 (2026-11-07). Both are Low follow-ups, not blockers.

**How to apply:** for any path-locality rule, check the drive table on every spelling (written, canon, full, realpath), not only the first. Related: [[rooted-driveless-and-letterless-volume]], [[unc-host-check-normpath-collapse]].
