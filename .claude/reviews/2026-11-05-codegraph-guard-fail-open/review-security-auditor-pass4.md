# Security Audit, pass 4 (final, fresh context): issue #259 change set (uncommitted, fix/259-codegraph-guard-fail-open)

Reviewer: security-auditor, 2026-11-05
Contract: `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` (approved; Addendum 3 items 11-14 read as binding)
Earlier passes: `review-security-auditor.md`, `-pass2.md`, `-pass3.md` (P3-W1, P3-W2, P3-N1, P3-N2)
HELD for the user, not reported as regressions: the Windows owner check / per-user parent folder; turning
codegraph-tool-named from a refusal into a finding.

Method: static read of `_project_paths.py:561-722`, guard `:61-88` and `:357-520`, bridge `_claude_paths.py:100-236`,
installer `:235`, `:2025-2084`, `:2550-2662`, reset hook `:40-278`, HEAD's helper (`git show HEAD:...`). Offline
probes only (Python 3.12.10, `ntpath.normpath`, the helper's `_remote_host` / `_hop_allowed` exec'd from source; no
path opened). `py -3 .claude/hooks/tests/test_codegraph_first_guard.py`: 607 passed, 0 failed, 0 skipped.
No CodeGraph tool was available in this session; symbols were traced with Grep and Read.

## BLOCKER

None.

## WARN

None.

## NIT

- **P4-N1. The commondir hop's allowed host set includes `realpath(target)`, and target is pointer data.**
  `_project_paths.py:643` `hop = _own_spellings(target) + _own_spellings(folder)`. Addendum 3 item 12 asks for this
  ("judged against the folder it hops from"), and it is needed: a worktree on `C:` whose gitdir is `Z:\repo\.git\...`
  (mapped) has `realpath(common)` = `\\srv\...`, which `:647` can only accept if `srv` is in the set. Not exploitable:
  `realpath(target)` runs only when target's text is local, and only after `os.path.isdir(target)` (`:634`) has
  already followed the same path, so any host it can add was already contacted by that `isdir` (a victim's own mapped
  server, or the out-of-scope local-symlink-to-UNC residual). A UNC target's host had to be in the own set already.
  Fix (optional): a one-line comment at `:643` saying why `realpath(target)` adds no new host, so a later reorder that
  puts `_own_spellings(target)` before the `isdir` at `:634` is caught in review.
- **P4-N2. The guard and the installer gate the older-helper case on different symbols.** Guard
  `codegraph-first-guard.py:82` tests `callable(_pp._hop_allowed)`; installer `auto_improve_finish_install.py:2608`
  tests `WORKTREE_OWN_ROOT_NATIVE` (`_claude_paths.py:179-181`, presence of `worktree_own_root`); guard `:81` binds
  `worktree_own_root` ungated. Equivalent for every helper that exists: `git log -S` finds neither `worktree_own_root`
  nor `_hop_allowed` anywhere in history, so both arrive together in this release. A later helper that renames the
  private `_hop_allowed` disables `index-other-tree` in the guard (safe direction) while the installer keeps giving
  verdicts (drift, not exposure). Fix (optional): one exported capability constant in the helper (for example
  `HOP_REFUSAL = True`) that the guard, the bridge and the installer all test.
- **Carried residuals (unchanged, out of scope for a text check).** P2-N5 `C:foo` drive-relative gitdir (local only).
  A LOCAL path component that is a symbolic link to a UNC target is followed by `isdir` / `isfile` / `realpath`
  before any post-resolution check; this now also covers `realpath(folder)` in `_own_spellings`, which adds no host
  that the walk's own `exists` / `isdir` calls had not already reached. Needs symlink-creation rights at extraction
  and is followed equally by git and by the agent's own Read.

## Verified closed

- **P3-W1 (normalise, then check).** `_git_file_kind:642` normalises `joined` before `_hop_allowed`, and every copy
  of `_hop_allowed` judges the text AND `os.path.normpath(text)` and refuses any `..` segment in a UNC or device
  path (helper `:581-591`, guard `:390-400`, bridge, installer `:2584-2594`). `normpath` is idempotent on every probe
  form, so the checked string is the string `realpath` opens. Probe table (own host `srv`):
  `\\?\UNC\srv\..\attacker\s`, `\\?\UNC\srv\share\..\..\attacker\s`, `//?/UNC/srv/../attacker/s`,
  `\\?\UNC\srv\\..\attacker`, `\\?\UNC\srv\share\.\..\x`, `\\?\UNC\srv\share\x\..`: all refused.
  `\\.\UNC\...`, `\\?\GLOBALROOT\Device\Mup\...`, `\\srv@SSL\...`, `\\\attacker\...`: refused (host `""` or foreign).
  Accepted forms (`\\?\UNC\\srv\share`, `\\srv\\attacker\share`, `...\x\.. ` with a trailing space,
  `...\x\...\attacker`) all stay on `srv` before and after `normpath` and under Win32 normalisation (separator
  collapse; trailing-dot/space trimming applies to the last segment only, after relative components are evaluated).
  Fuzz: 200,000 random strings and 200,000 relative commondir texts joined onto a `\\?\UNC\srv\...` gitdir; zero
  cases where `_hop_allowed` passed and `normpath` named a host other than `srv`. Test rows exist
  (`test_codegraph_first_guard.py:1758-1761`, `:1839-1844`, `:1876-1878`).
- **Device-form own paths.** `\\?\X:` and `\\.\X:` map to `"?x:"`; no remote form maps to a drive host
  (`\\?\GLOBALROOT`, `\\?\Volume{...}`, `\\.\UNC`, `\\?\C:..` all give `""`). A plain `C:\repo` own path never admits
  a `\\?\C:` target (stricter than needed, safe).
- **`_own_spellings` on the tree's own path.** `realpath` runs only when the written form is local (`:598`), so a
  UNC or device own path is never resolved. For a local own path, `realpath` reaches only hosts the walk's own
  `exists` / `isdir` already reached (mapped drive = the victim's own server). Pointer data never enters the own set
  except via P4-N1, which is sanctioned and adds no host.
- **P3-W2 (older helper).** Guard `:82-84` binds `tree_kind` / `main_checkout_root` only when `_hop_allowed` is
  callable. Every use of `_pp` in the guard: `:65` import, `:72-74` `checkout_equivalent_path` (pure in HEAD's helper,
  `:486-515`: no filesystem access), `:81` `worktree_own_root` (absent from every released helper), `:82-84`.
  `_main_candidate:464` and `index_verdict:511` call the tree functions only through the gated names. Installer is
  gated equally (`:2608`; the bridge's ungated `tree_kind` / `main_checkout_root` re-exports are used by
  `_main_checkout_guard.py`, `pr_merged.py`, `flat_worktree.py`, which ship with the helper and are not in the
  mixed-version scenario). Test W-13 loads HEAD's real helper, proves its `main_checkout_root` probes the fake host
  (control), then shows the guard's `_main_candidate`, `index_verdict`, `decide` and the installer's
  `_codegraph_index_notes` probe nothing under it (all PASS).
- **Parity (item 14).** AST comparison, docstrings and annotations stripped: `_remote_host`, `_hop_allowed`,
  `_own_spellings` identical in all four files; guard and bridge `pointer` identical; helper `_gitdir_pointer` equal
  in logic (uses `_GITDIR_MARKERS`).
- **Pruner.** `TICKET_RE` (`reset:46`) now escapes the dot; `KNOWN_FILE_RE` (`:50`) unchanged and escaped; both
  `fullmatch`. Deletion requires a plain non-link file whose real parent is the folder, re-checked before each
  `os.remove`; folders go with `os.rmdir` only. Session id grammar (`:53`, guard `:206`, tracker `:37`) has no
  separator and cannot start with `.`. Nothing beyond the listed names can be deleted.
- **Server-name grammar and `_grant_server`.** `_SERVER_NAME_RE` (`:235`) is
  `[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9-])?` under `fullmatch`, plus the `__` ban (`:2033`): no trailing `_`, no
  `__`, ASCII only. `_grant_server` (`:2079-2084`) is exact equality against `mcp__<s>__*` / `mcp__<s>`.
- **Other path operations.** Session-folder writer (`_atomic_write`, O_EXCL + O_NOFOLLOW, `os.replace`), reader
  (lstat plain-file test), tracker writer, pruner, index `lstat`, settings readers: unchanged since pass 3; no new
  read, write, delete or follow outside them. `_main_checkout_guard` treats the new `undecidable` outcomes as a block
  (`:110`, `:118`), so the helper change tightens that guard rather than loosening it.

## Verdict

SAFE TO MERGE. P3-W1 and P3-W2 are closed with real-helper tests; no new path reaches a UNC or device host before
its refusal. Two optional NITs.
