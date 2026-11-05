---
name: unc-host-check-normpath-collapse
description: When auditing a UNC/remote-host refusal in this repo's path helpers, check that the host is parsed AFTER normpath; Python 3.12 normpath collapses \\?\UNC\a\..\b to host b, and realpath normalises before opening.
metadata:
  type: feedback
---

A host check on un-normalised text is bypassable: `ntpath.normpath(r"\\?\UNC\srv\..\attacker\s")` gives `\\?\UNC\attacker\s` (Python 3.12.10), and `ntpath.realpath` calls `normpath` then `_getfinalpathname` (an open) before any post-check. Plain `\\srv\share\..\..` does NOT climb past the share.

**Why:** issue #259 pass 3 found the commondir hop in `_project_paths._git_file_kind` checked `joined` raw while `realpath(joined)` opened the collapsed path (NTLM leak to another host when the tree is on a UNC path).

**How to apply:** for every "refuse before probe" check, confirm the checked string is byte-for-byte what the probe opens (normpath first), and add a `..` row with a `\\?\UNC\` prefix. Also check whether callers bind an OLDER helper version whose functions probe before returning; caller-side checks after the call do not help. Probe offline with `nt._getfullpathname` / `ntpath.normpath` (no I/O).

Pass 4 (2026-11-05) method that worked fast: AST-compare the four copies (helper, guard, bridge, installer) with docstrings/annotations stripped, then fuzz `_hop_allowed` (random atoms `\ / .. . srv attacker UNC ? C: ...`) asserting host(normpath(x)) is None or own whenever allowed. When a "same-host" set is widened by `realpath` of pointer data, check the realpath runs only AFTER an `isdir` that already followed the same path (then it adds no new host).
