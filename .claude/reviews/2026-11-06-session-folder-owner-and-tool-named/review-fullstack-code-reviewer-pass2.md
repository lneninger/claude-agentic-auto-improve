# Code review, pass 2 (cold context): 2026-11-06-session-folder-owner-and-tool-named (#271)

**Reviewer:** fullstack-code-reviewer, second pass after the fix round, 2026-11-06
**Contract:** `.claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md` (approved)
**Diff:** uncommitted worktree against `c8653e3`. There are no commits on the branch, so there is no separate "first RED commit" to compare against. I compared the test files against `c8653e3` instead: every removed line, and what replaced it.
**Scope:** Python hooks, installer, bridge, helper, manifests, docs, registries. No C# or Angular code is involved.

## What I ran and checked

- **Parity of the three hook copies.** I compared the source of every top-level name the guard, tracker and reset hook share, with an AST source-segment comparison.
  - Byte-identical: `session_parent_base`, `_base_shown`, `_create_parent`, `resolve_session_parent`, `session_folder_problem`, `_remote_host`, `_own_spellings`, `PARENT_NAME`, `PARENT_PROBLEMS`, `_LOCAL_DEVICE_HOST_RE`, `_REPARSE_POINT`, `_SESSION_ID_RE`, `SESSION_PREFIX`, `MARKER_NAME`.
  - `_is_link_stat` has the same code but a different docstring.
  - `log` differs only in its prefix.
  - `session_key` in the guard behaves the same as in the other two (it goes through `_norm_path` / `_payload_cwd`). That difference predates this change.
  - `MARKER_WRITER` is the same value in the guard and the tracker.
- **`block()` and `announce()` in the guard.**
  - Before the change, `reconfigure(encoding="utf-8")` set `errors` to strict. Now it is `errors="backslashreplace"`. For text that encodes, the output is byte-identical.
  - `block()` builds the same lines for `source-target` and `ambiguous-target`, plus the reason-specific lines from I-7c. It now ends in `finally: sys.exit(2)`.
  - The `safe` transform of `details` is the identity on valid UTF-8.
  - Exit codes are unchanged for every ordinary input. The only exit that changed: a `log_event` that raises now exits 2 instead of reaching the catch-all exit 0. That is stricter, and it matches I-6.
- **`log()` in all three hooks.** Each now makes the `errors` handler `backslashreplace` and swallows a print failure. Ordinary output and exit codes are unchanged. The catch-all's own `log()` can no longer raise a second exception.
- **`_entry_shown` in the installer.**
  - It escapes C0/C1 controls, U+2028/2029, lone surrogates and the backtick, and caps the entry at 200 characters.
  - Layer and file are taken from the installer's own values.
  - The message shape matches the contract's Tool-named refusal message.
- **Bridge.** `worktree_own_root = _native_own_root if (TREE_HOP_REFUSAL and callable(_native_own_root)) else inline`. Security-auditor L6 is fixed, and the S-L6 row passes. `__all__` lists `TREE_HOP_REFUSAL`, and `WORKTREE_OWN_ROOT_NATIVE` is gone.
- **`released_sha256`.** I recomputed the folded SHA-256 of the three hooks at `e4f392c`, where `plugin.json` is 0.15.2:
  - guard `8c44ed60…`, reset `900db4ad…`, tracker `7e2daa3a…`
  - all three are present in `addon.json`
  - the hooks did not change between `e4f392c` and `c8653e3`
  - the current files are correctly not in the list
- **Version.** 0.15.3 is in all five entries: `plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, and both entries in `marketplace.json`. `check_version_bump.py` says "no shipped plugin file changed", which is expected for an uncommitted diff. Re-run it after the commit.
- **INV-15.** The README states 394 cases, and the suite has 394 `def test_` methods. `README.md:372` ("grows to 385") is 0.15.2 history and does not match the INV-15 phrase.
- **Suites, each run alone:**

  | Suite | Result |
  |---|---|
  | `test_codegraph_first_guard.py` | 939 passed, 0 failed, 3 skipped (Q-3 root-only, Q-9 POSIX open-mode, T-M1 POSIX twin) |
  | `test_worktree_path_guards.py` | 190/190 |
  | `test_addons.py` | 33 OK |
  | `test_plugin_manifests.py` | 191 passed |
  | `test_installed_plugin_root.py` + `test_codegraph_session_parent_docs.py` | 40 OK |
  | installer subset (Hop, ToolNamed, refusal message, hostile/long entry, findings layer, single wildcard) | 14 OK |

- **Concurrent run (not a defect of this diff).** In my first run the three suites ran at the same time, and all three leak checks failed on `C:\Users\lneni\AppData\Local\auto-improve-codegraph\auto-improve-codegraph-abc`.
  - The folder was created at 17:35:14, along with the real parent. It holds `logged-no-index` and an `availability.json` with cwd `D:\x` and a mojibake Cyrillic user path.
  - No test in this worktree uses session `abc`. Each suite, re-run alone, adds nothing.
  - So another process ran the real 0.15.3 hook with the real environment at that moment, most likely another agent's hand probe.
  - I left the folder in place. The user may delete it.
  - This confirms test-critic L3: the real-folder leak checks false-fail when anything else on the machine runs the hooks during a suite.
- **Tests weakened?** No. Every removed test line is re-stated with the new expected outcome and a positive control:
  - step 0 became step 2: link and file now block `session-state-unusable`, with the exact problem field;
  - step 7 became step 8: `retry-ticket-unwritten`;
  - T-1 is now the stamped shape;
  - the `test_addons` marker shape asserts the exact six keys;
  - W-14 `_remote_host` / `_own_spellings` went from four copies to six, and `_hop_allowed` stays at four;
  - the fixture helpers moved from the temp folder to `af.session_parent`.
- **Stray files.** `git status --ignored` shows only the expected files, the reviewers' agent-memory notes, and the ignored `.claude/cache/`. There is no scratch.
- **Re-grep** (contract list, over README, skills, references, add-ons, hooks, scripts, registries):
  - `state-unwritable` appears only in README 0.15.3 history ("reverses 0.15.2's …").
  - `nudge` appears only in the unrelated angular-tailwind and plan-question advisors.
  - `WORKTREE_OWN_ROOT_NATIVE` appears only in the README "replaces" sentence and in JOURNAL history.
  - There is no `gettempdir` call in the three codegraph hooks. The other `gettempdir` users (`_project_paths.session_marker`, `stop-dispatcher.py`, `concept_changed_check.py`, `integration-check.py`) are out of scope; see the first pass's follow-up question.
  - Every "repeat the blocked call" and "repeat this exact call" sentence is followed by E1, except the banner's own `source-target` line, which is correct.
  - "logs one record per session per reason" carries E2 at README:339-340, the decision table at :121-122 and install SKILL:78.
  - `announce()`'s docstring states the exception itself.

---

### `.claude/addons/codegraph/hooks/codegraph-first-guard.py` (and the same block in the tracker and reset)

**[WARN]: The Windows Remote rule runs `realpath` on a drive letter before any no-I/O drive check. A disconnected mapped drive takes 21 s per call and is judged local.** `session_parent_base`, around lines 306-329, the same in all three hooks.
```python
texts = [raw]
... texts.append(full_name(raw))
for text in texts:
    for spelling in _own_spellings(text):        # realpath(text): network I/O on a mapped drive
        ...
if device and raw[5:6] == ":" and raw[4:5].isalpha():
    plain = raw[4:]
    host = _remote_host(os.path.realpath(plain))  # realpath again, BEFORE the drive table
    ...
    if ctypes.windll.kernel32.GetDriveTypeW(plain[:2] + "\\") == 4:  # only for the device form
```
**Problem**:
- **What the suite recorded.** The S-M1 recorded row in this run found a real mapped `Z:` on this machine and printed `os.path.realpath('Z:\\') -> '<no answer in 10 s>'`.
- **What I measured.** `net use` shows `Disconnected Z: \\192.168.17.128\irrigation-electron`, and `GetDriveTypeW('Z:\\')` is 4 (`DRIVE_REMOTE`). `os.path.realpath('Z:\\x')` took 21.1 s and returned `Z:\x` unchanged, not the share.
- **What happens with `LOCALAPPDATA=Z:\x`.** The plain form gets no drive-type check. It costs two `realpath` calls: about 42 s just to judge the base, and it is then judged **local**, followed by `lstat` / `mkdir` on the dead share. A hook that passes Claude Code's timeout is a non-blocking error, so the read is **allowed**. That is the fail-open the contract set out to remove (I-6).
- **What happens with the device form.** `\\?\Z:\x` is eventually refused, but only after the same `realpath` wait.
- **Why the contract does not cover this.** It assumed (ASSUMED) that a mapped drive's `realpath` gives `\\server\share`. That is false for a disconnected mapped drive.
- **Who can reach it.** Only someone who controls the environment and whose machine has a mapped drive, so WARN, not CRITICAL.

**Fix** (all three copies; the Q-parity row keeps them identical, and `_own_spellings` stays verbatim). Judge the drive letter from the local drive table first, for the plain form AND the device form, before `_own_spellings` runs:
```python
if os_name == "nt":
    ...
    drive = re.match(r"^(?:[\\/]{2}[?.][\\/])?([A-Za-z]):", raw)
    if drive:
        try:
            import ctypes
            kind = ctypes.windll.kernel32.GetDriveTypeW(drive.group(1) + ":\\")
        except Exception:  # noqa: BLE001 - undecidable is refused
            return None, "remote"
        if kind in (0, 1, 4):   # DRIVE_UNKNOWN, DRIVE_NO_ROOT_DIR, DRIVE_REMOTE: no realpath, no open
            return None, "remote"
    texts = [raw]
    ...
```
Then add these rule-table rows:
- a plain `Z:\x` with the fake drive table saying `DRIVE_REMOTE` and a `realpath` fake that **raises if called**, giving `remote`, which proves no `realpath` runs;
- the same for `\\?\Z:\x`;
- a control: `C:\x` with a fixed drive stays local.

The current fake `realpath` maps `Z:` to the share, so it hides the hang. Also tell the user in the PR that the contract's ASSUMED line about mapped-drive `realpath` is falsified for a disconnected drive. A JOURNAL entry is appended.

---

**[INFO]: The parity row does not cover `_is_link_stat` or the module constants** (`test_codegraph_first_guard.py:2636`, `SHARED_VERDICT_FUNCTIONS`)
- **Problem.** `resolve_session_parent` and `session_folder_problem` call `_is_link_stat`. A tracker copy that dropped the `FILE_ATTRIBUTE_REPARSE_POINT` arm would write markers through a junction the guard refuses, and no parity row would notice.
- **Not covered.** `_LOCAL_DEVICE_HOST_RE`, `PARENT_NAME` and `_REPARSE_POINT` are not covered either. They are identical today; I checked.
- **Fix.** Add `_is_link_stat` to `SHARED_VERDICT_FUNCTIONS`, comparing the code without the docstring, or align the three docstrings. Add an `ast.Assign` comparison for the three constants.

**[INFO, carried from pass 1, still open, optional]:**
- `Session.path()` on a stateless session still returns a cwd-relative name. Every caller is still gated.
- A `check-failed` raised inside `session_parent_base` still shows an empty path in the banner (`parent = ""`).

**[INFO]: The bridge comment says True means "native"; there is one edge where that is not so** (`_claude_paths.py:196-201`). When a helper declares `TREE_HOP_REFUSAL = True` but has no callable `worktree_own_root`, `TREE_HOP_REFUSAL` is True and the bridge uses the inline copy. Correct the comment to read "True: the tree functions are trusted; `worktree_own_root` is native when the helper has it".

---

### `README.md`

**[WARN]: The third README copy of E1 has nothing to attach to, and it reads as a false limit on the fail-open cases** (line 319-320, inside the 0.15.3 "It fails closed" bullet)
```
... A subagent, a project with no index and a project with no configured server are still let
through. Not after a `session-state-unusable` block, which offers no retry. After a `retry-ticket-unwritten` block ...
```
**Problem**:
- The fix round removed the dangling E2 from this bullet (pass-1 INFO) and put E1 there instead. E1 is an exception to a "repeat the blocked call once" sentence, and this bullet has none.
- Right after "still let through", "Not after a `session-state-unusable` block" reads as "subagent / no-index / no-server reads are not let through after an unusable-folder block". That is false: steps 4-6 still run in the unusable state (code lines 985-999; Q-9 rows).
- The contract never listed this site. `test_codegraph_session_parent_docs.py` (`E1_SITES` README count 3) now pins the misplaced copy.

**Fix**: drop E1 from this bullet, since the retry rule is already stated where the retry escape is described (:347, :603), and set the README count in `E1_SITES` to 2. Alternatively, rewrite it so it has a referent: "The retry escape does not apply after a `session-state-unusable` block; after a `retry-ticket-unwritten` block the repeat is blocked once more (as `source-target` or `ambiguous-target`) and the identical call after it is allowed."

---

### `.claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md`

**[WARN, carried from pass 1, still open]: Files to touch omits `.claude/scripts/tests/test_codegraph_session_parent_docs.py`.** The new test file is still not listed. It is test-only and under `.claude/`. Add it to Files to touch, or name it in the PR as a test-only addition. `.claude/registries/JOURNAL.md` is a reviewer write, so it is not a drift.

---

### Status of every first-pass finding

| Pass-1 finding | Status |
|---|---|
| CR W: E1 / banner name only `source-target` | **Resolved.** Banner at :1181-1182, 10 doc sites, C-W1 row incl. a pattern-only Grep → `ambiguous-target` control |
| CR W: no textual parity of the verdict functions | **Resolved.** `SHARED_VERDICT_FUNCTIONS` + mutation proof (3 mutations bite). Residual: `_is_link_stat`, constants (INFO above) |
| CR W: install SKILL "before 0.15.2" | **Resolved** (:158 "before 0.15.3"; pinned) |
| CR W: Files to touch omits the docs test | **Open** (above) |
| CR I: MECHANISMS "is fails", VOCABULARY lowercase | **Resolved** (pinned) |
| CR I: README dangling E2 | **Replaced by a dangling E1** (WARN above) |
| CR I: `Session.path`, empty check-failed path | Open, optional |
| SA M1: device-path `..` / device-form mapped drive | **Resolved for the text forms** (rows for `\\.\C:\..\UNC`, `//./C:/../`, `\\?\Z:\`, `\\.\Z:\`, controls). **Residual WARN:** realpath before the drive table; plain `Z:` has no drive-type check; disconnected drive hangs and is judged local |
| SA M2: lone surrogate → catch-all allow | **Resolved.** `errors="backslashreplace"` in `block()`/`announce()`/`log()`, `finally: sys.exit(2)`, log details sanitised; S-M2 rows for Grep/Glob/Read + `LOCALAPPDATA` route |
| SA L1 POSIX rename race, L3 raw env text in stderr, L5 reset transient, L7 RecursionError | Open (hardening; out of contract scope). L3 partly: log record sanitised, stderr lines still carry raw newlines |
| SA L4 entry echo | **Resolved** (`_entry_shown`, hostile and long-entry rows) |
| SA L6 bridge `None` | **Resolved** (S-L6 row) |
| TC H1 owner/mode never run | **Resolved** (T-H1 matrix on every OS, fake uid, per-path stat override) |
| TC H2 `session-check-failed` untested | **Resolved** (T-H2 + no-index control) |
| TC M1 Windows base never created | **Resolved** (T-M1 `LocalMissing`; POSIX twin skips on Windows) |
| TC M2 mapped drive only via patched realpath | **Resolved as asked** (recorded row), and it recorded the hang behind the WARN above |
| TC M3 `names_problem` too loose | **Resolved** (`(token)` + exact record field) |
| TC M4 doc tests once-per-file | **Resolved** (per-site E1 invariant, "repeat … followed by E1 within 400 chars"). Pins the misplaced README site (above) |
| TC M5 `unwritable` on Windows | Partly. Faked `os.access` rows exist. The Windows ACL behaviour and the I-7b wording question were not escalated |
| TC L1 foreign-marker stderr and flag order | **Resolved** (`run_foreign_marker_order`) |
| TC L3 leak-check gaps and flakiness | Gaps resolved (T-L3). Flakiness confirmed by my concurrent run (see above) |

### Contract alignment

- **Data shapes match:**
  - the Parent base rule and problem set;
  - one-level creation, with the Windows base never created;
  - the stamped marker and `logged-foreign-marker`;
  - the Stateless session (no filesystem call while `problem` is set; `announce()` returns before any flag);
  - the decision order 1-8, with a step-8 re-resolve that never allows;
  - I-7 / I-7b / I-7c banners;
  - I-8 tracker and reset;
  - I-9 pruner on the usable parent only;
  - the Hop proof in the guard, bridge and installer;
  - the Tool-named refusal message.
- **Divergence: none,** apart from the falsified ASSUMED mapped-drive line, which is recorded in the JOURNAL.
- **Off-area drift:** none. The area map is empty and Adjacent Areas is not applicable.
- **End-User View:** not applicable.
- **Integration consistency:** no REST, SignalR or DTO surface.

### Registries (janitor)

- **MECHANISMS.md:** no new mechanism. The 2026-11-06 span edits and the correction read true against the code.
- **VOCABULARY.md:** "Per-user session parent" and "Foreign marker" are present and accurate.
- **JOURNAL.md:** one entry appended, "Judge a drive letter with a no-I/O check before any realpath, because realpath of a mapped drive can block", with `Trigger: post-impl divergence`. It batches into this change's 0.15.3 raise.
- **INTEGRATION.md:** nothing to update.

---

### Summary

| Severity | Count |
|---|---|
| [CRITICAL] | 0 |
| [WARN] | 3 |
| [INFO] | 3 |

**Verdict**: `FIX THEN SHIP`

**Top priority fix**: In `session_parent_base` (all three copies), ask `GetDriveTypeW` before any `realpath` for a drive-letter base, plain or device form, and refuse `DRIVE_REMOTE` / unknown / no-root as `remote`. A disconnected mapped drive currently costs about 42 s per hook call and is judged local, so the hook can time out into an allow.
