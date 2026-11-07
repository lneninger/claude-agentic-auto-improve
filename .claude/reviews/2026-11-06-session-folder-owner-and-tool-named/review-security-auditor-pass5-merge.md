# Security Audit (pass 5, cold context): the merged codegraph hooks for issue #271

**Verdict:** pass-with-conditions
**Reviewer:** security-auditor
**Date:** 2026-11-07
**Subject:** the staged merge of `origin/master` (0.16.2, hooks redesign #261) into `fix/271-session-folder-owner-and-tool-named`, as `git diff origin/master` shows it
**Contract:** `.claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md` (approved), together with `.claude/concepts/2026-11-05-codegraph-hooks-redesign.md` (implemented on master)
**Release blockers:** none
**Follow-ups:** F1 to F5 (below), plus the informational items

I did not rely on the earlier audits' conclusions. Everything below comes from reading the merged sources and from scratch probes. The probes ran the three merged hooks, with the real `_project_paths.py` and `_error_log.py`, as subprocesses. Each one ran inside a fresh folder under `%TEMP%` with `LOCALAPPDATA`, `CLAUDE_PROJECT_DIR` and `CLAUDE_CONFIG_DIR` pointed into that folder. The folder was deleted afterwards. The probes wrote nothing in the repository, used no network and never touched `Z:`.

`.claude/project-profile.md` is the unfilled template. The `auth.roots` and `backend.roots` slots do not resolve, so the scope came from the task's file list.

## What was verified to hold

| Question | Result | Evidence |
|---|---|---|
| (1) Can state the user did not write cause an allow? | No. The Turn marker is read only when `step0_ok` is true (guard `:1120`). Tickets and caches are read through `Session.has_plain_file` / `read_json`, which return absent for a Stateless session (`:588-610`). The shadow reuses the Live plan's `step0_ok` and never calls `resolve()`. Its `Plan` is separate and its `ticket_op` and `availability_write` are never applied (`:1139-1162`, `:1166`). `apply_state` writes only through `Session.write` (`ensure_folder` refuses an unusable state) and deletes a ticket only when the plan saw it as a plain file. | Probe P6: the parent is a junction to a folder holding a planted `turn.json`. Result: exit 2, `session-state-unusable (link)`, planted file untouched. Probe P6b: the Session folder is a junction. Result: exit 2, `session-link`. P6c/P6d: reset and tracker on that junction deleted and wrote nothing. P10: the parent is a file. Result: `not-a-folder` block. |
| (2) Does resolving before classifying open a new risk? | No fail-closed break. A non-source target still reaches step 2 and is allowed while the state is unusable (P5 README, P6 README: exit 0). The only new side effect is the one `mkdir` of `<base>/auto-improve-codegraph` (and on POSIX the one-level `0700` base). It now happens on every Read/Grep/Glob instead of only on source targets. The creation is followed by a fresh `lstat` and the full parent check, so a racing link or file planted between the `FileNotFoundError` and the `mkdir` still produces `link` / `not-a-folder`. Every swap window is inside a folder only the user (or an admin) can write. | `_create_parent` `:427-453`, `resolve_session_parent` `:456-491` |
| (3) Does the shadow read or write through a link or foreign folder **in the Session folder**? | No. `use_cursor = live.step0_ok and _cursor_folder_ok(session)` (`:1788`), with `lstat`, not a link and a directory. The cursor is read through `has_plain_file`. The temp file uses `O_EXCL\|O_NOFOLLOW` and then `os.replace`. **Outside the Session folder it does** (F2). | |
| (4) Any `gettempdir` or temp-folder state left in the three hooks? | None. There is no `tempfile` import and no `gettempdir`, `TMP` or `TEMP` reference in any of the three files (AST and text scan). | |
| (5) I-4 catch-all reachable only outside the folder check; `block()` cannot exit 0 | `block()` holds: `sys.exit(2)` runs in a `finally`, `build()` falls back on any exception, stderr is reconfigured to `backslashreplace`, and log fields are surrogate-escaped. P1 (a lone surrogate in `file_path` and in `limit`) exits 2. P2/P2b (NUL in a path or pattern) exit 2. P3 (non-str fields) exits 2. The catch-all can still be reached outside the folder check from the stdin parse and the payload shape (F4). | |
| (6) `released_sha256` | Correct. The added hashes equal the LF blobs of `origin/master` (0.16.2): guard `575c83f3…c9c2`, reset `3a1658c9…925d`, tracker `7e2daa3a…1dbc`. The tracker hash is also the 0.15.2 tracker (blob unchanged since 3780c2f), so the skill's "0.15.2: all three update" line is right. No hook commit exists on master after 766423f, so 0.16.0 to 0.16.2 share one set. The installer compares the hash of the folded bytes (BOM stripped, CRLF→LF) and only for `kind == "hook"`. A link destination reads as `have=None` and is refused. The apply re-reads the bytes before the first write. An edited hook is still `addon-file-differs`. A tampered hook cannot pass as released short of a SHA-256 second preimage. | `auto_improve_finish_install.py:2299-2321`, `:2906-2933` |
| (7) Windows `session_parent_base` rule | Identical in the three hooks (AST source segments equal). The other helpers in the block are identical too: `_remote_host`, `_own_spellings`, `_create_parent`, `resolve_session_parent`, `session_folder_problem`, `_base_shown` and the constants. `_is_link_stat` and `session_key` differ only in docstring and spelling, and are semantically equal. Unchanged by the merge: `git diff --cached HEAD` has no hunk in the guard's lines 347-625, and the tracker has no diff at all. | |

## Findings

### Medium

- **F1. A retry ticket that cannot be deleted becomes an unlimited allow.** The single-use property regressed against the pre-merge branch. Location: `codegraph-first-guard.py:1159-1162` (plan) and `:1192-1196` (apply).
  **Exploit scenario:** the guard blocks `Read src/b.py` and writes `ticket-<fp>`. Something then makes the ticket undeletable: the read-only attribute (`attrib +r`), or a scanner holding the file open without `FILE_SHARE_DELETE`. From then on, every identical `Read src/b.py` in the turn is allowed as `retry-escape-used`. The plan allows because the ticket exists, `os.remove` fails, and `apply_state` "keeps the planned allow". Two identical parallel calls also both pass on one ticket. Probe P7: block, mark the ticket read-only, then retries 1, 2 and 3 all exit 0. The pre-merge branch (`HEAD:…guard.py:1013-1018`) fell through to a fresh block when the remove failed. The merge took master's "apply never re-decides" rule.
  **Impact:** the "allowed once" promise in the banner, the skill and README fails. It is limited to the identical call within one turn, and to state in the user's own folder (I-6 still holds). An agent able to set `+r` already has a shell, so the gain is small. That is why it is Medium, not High.
  **Fix:** in `apply_state`, when the planned reason is `retry-escape-used` and `os.remove` raises anything other than `FileNotFoundError`, return `("block", "source-target"/"ambiguous-target")`. Keep the planned allow only for `FileNotFoundError` (a parallel consumer). Or consume first: in `_plan` record `("consume", ticket)`, and let apply decide allow only if `os.remove` succeeded. Add a test that marks the ticket read-only and asserts that the second retry is blocked.
  **Class:** follow-up. 0.16.2 on master already ships this behaviour, so the merge does not make the released state worse. It does reopen what the pre-merge branch had closed.

- **F2. The shadow log is opened through links in the project tree.** Location: `codegraph-first-guard.py:1737-1769`.
  **Exploit scenario:** a repository commits `.claude/logs/codegraph-shadow.jsonl` as a symlink (POSIX, or Windows with symlinks enabled) to a file the victim can write, for example `~/.config/<tool>/config` or a dangling target in `~/.local/...`. `_shadow_log_path` checks `os.path.isdir(<project>/.claude)` (it follows links). `os.makedirs` follows links. `os.open(path, O_WRONLY|O_CREAT|O_APPEND)` has no `O_NOFOLLOW`, so every guarded Read/Grep/Glob appends a JSON line (about 400 bytes) to the link target, or creates it. At the cap, the `open(path, "rb")` also reads through the link.
  **Impact:** integrity damage to, or creation of, files outside the project in the user's name. The content is mostly fixed (enumerated classes, hash prefixes), so this is not code execution. A hostile repository is partly mitigated by Claude Code's folder trust. A planted link is far less visible than a hook row in `settings.json`, though.
  **Fix:** before the `makedirs`, `lstat` `<project>/.claude` and `<project>/.claude/logs` and skip the record when either is a link or reparse point. Open with `O_NOFOLLOW` where available, then check `os.fstat(fd)` against an `os.lstat(path)` that is not a link and is `S_ISREG`. Skip on any mismatch. `_error_log.log_event` (`.claude/hooks/_error_log.py:132`) has the same class (`Path.open("a")`). Fix both, or record the helper as a known gap.
  **Class:** follow-up (pre-existing in 0.16.2, not introduced by #271). It answers question (3): the shadow does write through a link, though not through the Session folder.

### Low

- **F3. The tracker loses the marker and leaks a temp file when the tool input holds a lone surrogate.** Location: `codegraph-turn-tracker.py:311, 333-341`.
  **Exploit scenario:** a `mcp__codegraph__*` call whose `query` contains `\ud800` (valid JSON, which Python decodes to a lone surrogate). `json.dumps(body, ensure_ascii=False).encode("utf-8")` raises `UnicodeEncodeError`, a `ValueError` and not an `OSError`. That skips `except OSError` and the temp-file cleanup, and reaches the I-4 catch-all ("internal error (failing open)"). Probe P8: exit 0, no `turn.json`, `.tmp-<16 hex>` left in the Session folder, and the next guarded Read is blocked.
  **Impact:** fail-closed direction (the gate stays shut after a real CodeGraph call), plus clutter. The reset hook removes `.tmp-<16 hex>` on the next prompt. The log text "failing open" is wrong for this hook.
  **Fix:** use `json.dumps(body)` (ASCII escapes), or `.encode("utf-8", "backslashreplace")`. Widen the inner `except OSError` to `except Exception` so the temp file is always removed.
  **Class:** follow-up.

- **F4. The I-4 catch-all is still reachable before and outside the folder check, from the payload shape.** Location: guard `:1821-1831`, `:798-803`.
  Deep-nesting probe: a stdin payload whose `tool_input` nests more than about 1,500 to 5,000 levels raises `RecursionError`, which is not a `JSONDecodeError`, so the result is exit 0 (allow). P4c: a non-hashable `tool_name` (`["Read"]`) raises `TypeError`, so the result is exit 0. `_read_json_file` catches only `OSError`/`ValueError`, so a deeply nested `.mcp.json` or `settings.json` also reaches the catch-all. The `tool_name` and the payload envelope come from Claude Code, not the model. Nested `tool_input` is reachable only if Claude Code accepts unknown nested parameters for Read/Grep/Glob, and its schema validation is expected to reject them (unverified here). A hostile settings file gains nothing that `disabledMcpjsonServers` does not already give.
  **Fix (hardening):** catch `RecursionError` in the stdin parse and in `_read_json_file` (the latter as `None`). Check `isinstance(tool_name, str)` before the set test.
  **Class:** follow-up. The contract scopes I-4 "out" for defects outside the verdict function, so this is not a contract divergence.

- **F5. The Session folder is resolved on every call, including non-source targets.** Location: guard `:1105-1109`.
  Every Read of a README now runs `GetDriveTypeW`, `_getfullpathname`, `realpath` (LOCALAPPDATA) and `lstat`/`mkdir` of the parent. There is no security regression (finding (2) above). Two side effects follow. First, `%LOCALAPPDATA%\auto-improve-codegraph` (on POSIX, possibly `~/.cache` at `0700`) is created even in a session that never reads source. Second, if LOCALAPPDATA's path contains a link to a UNC target, `realpath` now touches that host on non-source reads too. That host is chosen by the user or admin, not an attacker.
  **Fix:** none required. Document the creation in the install skill's file list, or defer `resolve()` until after classification on the non-source path. The latter is G-1's earlier order, and then the marker check must stay after it.
  **Class:** follow-up (documentation).

### Informational

- **No owner check on Windows.** This is a contract Non-Goal (L180, L185). If a user's own `LOCALAPPDATA` points at a local folder that other users can write (for example `C:\Shared`), another user can plant `auto-improve-codegraph\auto-improve-codegraph-<sid>\turn.json` and open the gate. The plant needs the victim's session id, a UUID. The `cwd-<16 hex>` fallback key is predictable from the cwd and is used only when Claude Code sends no valid `session_id`. Accepted residual risk, as written.
- **Lazy helper loading** (`_import_helper`, `_late`): an import failure binds `None` and the guard falls back to strict mode (fallback banner, `index-other-tree` cannot fire). This is never an allow. Only a helper that raises `SystemExit` at import, or exports a non-callable `checkout_equivalent_path`, could exit 0, and that requires write access to `.claude/hooks/`, which is code execution anyway.
- **The `\\?\` and `\\.\` spellings of a local LOCALAPPDATA** resolve to the same Session folder as the plain form (P11/P11b: a ticket written under one was consumed under the other). This is consistent and harmless.
- **The shadow record** stores `fp` (12 hex digits of SHA-256 over tool name plus input). Someone holding a dictionary of the repository's file paths can recover which files were read. Keep `.claude/logs/` out of version control (check that the project's `.gitignore` covers it).
- **`_entry_shown`** (installer `:2537-2546`) has literal invisible characters (U+034F, U+FE00-U+FE0F) in its source. Spell them as `\u034f` / `\ufe00` escapes so a reviewer can see them. Hangul fillers (U+3164, U+115F) and U+2800 are not escaped (categories Lo/So), which is a minor gap in the "cannot hide text" goal.

## Release-blocker vs follow-up

| ID | Severity | Class | Introduced by |
|---|---|---|---|
| F1 | Medium | follow-up | master 0.16.2 (`apply_state`); reopens a property the #271 branch had |
| F2 | Medium | follow-up | master 0.16.2 (shadow log); same class in `_error_log.py` |
| F3 | Low | follow-up | tracker (present before the merge) |
| F4 | Low | follow-up | all releases |
| F5 | Low | follow-up (doc) | the merge's step order (G-1) |

No finding lets state the user did not write, or an unusable, planted, linked or foreign per-user parent or Session folder, cause an allow. `session-state-unusable` and `retry-ticket-unwritten` never allow. `block()` always exits 2. The Parent base rule is identical in the three hooks and unchanged by the merge. `released_sha256` is correct.

**Conditions for "pass":** before the next minor, file F1 and F2 as tracked follow-ups (issues). F1 must at least be reflected in the "allowed once" wording, or fixed with the test described above.
