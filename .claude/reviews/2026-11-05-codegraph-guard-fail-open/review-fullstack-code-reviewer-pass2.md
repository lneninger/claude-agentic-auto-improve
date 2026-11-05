# Review (pass 2, fresh context) — fullstack-code-reviewer — codegraph-guard-fail-open (#259)

- **Contract:** `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` (approved, with the binding Approval addendum)
- **Branch / tree:** `fix/259-codegraph-guard-fail-open`, uncommitted working tree compared with `HEAD` (643b667)
- **Date:** 2026-11-05
- **Supersedes:** `review-fullstack-code-reviewer.md` (pass 1)
- **Verdict:** `FIX THEN SHIP`. One BLOCKER (a regression in a shared mechanism, reproduced), one WARN, five NITs.

## What was run

| Suite | Result |
|---|---|
| `py -3 .claude/hooks/tests/test_codegraph_first_guard.py` | 382 passed, 0 failed, 0 skipped |
| `py -3 .claude/hooks/tests/test_addons.py` | 28 tests OK |
| `py -3 .claude/hooks/tests/test_worktree_path_guards.py` | 189 passed, 0 failed |
| `py -3 .claude/hooks/tests/test_main_checkout_guard.py` (not in the block; run because the BLOCKER reaches it) | 55 tests OK (no fixture covers the regressed layouts) |
| `py -3 -m unittest discover -s .claude/scripts/tests -p "test_*.py"` | started, then stopped by Claude Code because the system ran low on memory (not a test failure). **No result was observed. The next agent must run it and record the result.** |

Two throwaway probes, run with `py -3 -I` from a scratch folder under the system temp folder (no git command, no project file touched):
1. `tree_kind` / `main_checkout_root` on a hand-built bare-repository worktree (`repo.git/worktrees/wt/commondir` = `../..`, `wt/.git` = `gitdir: <abs>/repo.git/worktrees/wt`) and a `--separate-git-dir` checkout (`sep/.git` = `gitdir: <abs>/sepgit`), with the working-tree `_project_paths.py` and with `HEAD`'s copy.
2. `_main_checkout_guard.decide` on a `Write` inside that bare-repository worktree, with each copy of `_project_paths.py`.

```
new bare-repo worktree: undecidable None | separate-git-dir: undecidable None
old bare-repo worktree: linked-worktree <root> | separate-git-dir: main-checkout <root>\sep
new block Reason: Write target: the tree of the target cannot be decided
old allow
```

---

## Findings

### `.claude/hooks/_project_paths.py`

**[BLOCKER]: The gitdir hardening changed `tree_kind` for every consumer. Bare-repository worktrees and `--separate-git-dir` checkouts now read `undecidable`, so the main-checkout guard blocks every write in them.** Lines 561-575 (`_gitdir_pointer`), 587-589 (`_git_file_kind`)

```python
def _git_file_kind(gitfile: str, folder: str) -> tuple[str, str | None]:
    try:
        target = _gitdir_pointer(folder, _read_gitdir_line(gitfile))
        if target is None:                 # None when the target holds neither /.git/worktrees/ nor /.git/modules/
            return "undecidable", None
```

**Problem.** The security pass's W3 asked for the `/.git/worktrees/`-or-`/.git/modules/` refusal in `worktree_own_root` *and* in `_git_file_kind`. In `worktree_own_root` it is harmless, because only candidate (b) reads that gitdir. In `_git_file_kind` it changes the shared tree classification (`MECHANISMS.md:43`). The contract says `tree_kind` and `main_checkout_root` are "consumed as-is" (Reused Mechanisms). Three common layouts have no `/.git/` segment in their gitdir:
- a worktree of a bare repository (`…/repo.git/worktrees/wt`). This is the usual `git clone --bare` plus `git worktree add` workflow;
- a checkout made with `git init --separate-git-dir` / `git clone --separate-git-dir` (`gitdir: /elsewhere/gitdir`);
- any tree whose git directory is on a network share (the UNC refusal). There the session's own folder is often on the same share.

They now classify as `undecidable` (probe 1). Consumers:
- `_main_checkout_guard._check_tree` (`.claude/hooks/_main_checkout_guard.py:118-119`) raises `Block(… "the tree of the target cannot be decided")` for an undecidable tree. Probe 2 shows a `Write` inside a bare-repository worktree going from `allow` to `block`. The main-checkout guard is a default, enforcing hook, so a user on that layout loses every Write, Edit and shell write. The add-on's guard wanted to stay a nudge; this change turns a core guard into a wall.
- `pr_merged.py:3293` now skips these trees, because their kind is neither `main-checkout` nor `linked-worktree`.
- `flat_worktree.py:177` and the installer (`auto_improve_finish_install.py:2611`) report them differently.

No suite catches it: `test_main_checkout_guard.py` and `test_worktree_path_guards.py` have no bare-repository or separate-git-dir fixture. The new U-H rows in `test_codegraph_first_guard.py:985-1007` *assert* the regressed behaviour for `gitdir: ../elsewhere-259`.

The leak W3 targets already existed: `git status` at session start follows the same line, as W3's own "Mitigating fact" says. It does not justify changing the classification for local, legitimate layouts.

```python
# Fix: keep the classification rule of HEAD in _git_file_kind; harden only the read and the UNC/device probe.
def _git_file_kind(gitfile: str, folder: str) -> tuple[str, str | None]:
    try:
        first = _read_gitdir_line(gitfile)                       # 4096-byte cap, strict UTF-8: keep
        raw = first[len("gitdir:"):].strip() if first.startswith("gitdir:") else ""
        if not raw:
            return "undecidable", None
        target = os.path.normpath(os.path.join(folder, raw))
        if _is_unc_or_device(target) and not _same_unc_host(target, folder):   # refuse only a jump to ANOTHER host
            return "undecidable", None
        ...  # isdir / commondir exactly as HEAD
```

Keep the `/.git/worktrees|modules/` marker rule in `worktree_own_root` and its two inline copies only. Add regression rows:
- bare-repository worktree → `linked-worktree`, with `main` = the bare folder's parent;
- separate-git-dir checkout → `main-checkout`;
- a `_main_checkout_guard.decide` `Write` inside a bare-repository worktree → `allow`.

Change the U-H `_git_file_kind` rows so the "neither marker" line is no longer expected to be undecidable.

---

**[NIT]: `_SESSION_ID_RE` was tightened in the shared helper, which also governs the database guard's session-start marker** — Line 880

```python
_SESSION_ID_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9_-])?")
```

**Problem.** The contract cites this regex only as "the grammar" the three add-on hooks copy. Editing the original changes `_marker_path` (`:886-890`, the database guard's session-start marker): a session id ending in `.` now gets no marker. Claude Code session ids are UUIDs, and a trailing `.` is stripped by Windows anyway, so the change is harmless and arguably a fix. It is still a behaviour change in a shared mechanism that the contract did not list. Record it in the contract's Revision history, or in the PR body.

### `.claude/hooks/_error_log.py` (NOT in Files to touch)

**[WARN]: Out-of-contract file; the change is safe, but the contract must list it** — Lines 88, 110, 133, 136

```python
) -> bool:
    ...
            return False   # no log folder
    ...
        return True
```

**Judgement.** The deviation is justified. Without a return value the guard cannot create `logged-<reason>` only after a written record, which is the security pass's fix. I checked compatibility in all three directions:
- **Every other caller:** a repo-wide search finds no assignment from `log_event(...)`, no `if log_event(...)` and no `return log_event(...)` other than `codegraph-first-guard.py:921`. Every other hook ignores the value, so it is unaffected.
- **A project with an older `_error_log.py`:** the old function returns `None`, and the guard tests `written is not False` (`guard:925`), so it takes the record as written and creates the flag. That is the pre-fix behaviour, never a crash.
- **No `_error_log.py` at all:** the guard's fallback stub (`guard:58-59`) returns `None`. Same as above.
- **Side effect to know:** with logging not enabled (no `LOG_DIR`, the default), `log_event` returns `False`, so the flag is never created and every fail-open call repeats one `exists()` stat. That cost is negligible, and it means a log folder created mid-session still gets its record.

**Problem.** The file is not in the contract's `Files to touch`. Per the Data-First protocol, the contract must be updated, or the PR body must carry a recorded justification, before merge.
```
Fix: add `.claude/hooks/_error_log.py` to Files to touch (Revision history line: "log_event returns bool; callers that ignore it are unaffected; an older copy returns None, which the guard treats as written").
```
**[NIT]** The docstring's `event: one of {"block", "warn", "redirect", "reconcile"}` (`:96`) is now stale: the guard emits `fail-open` and `retry-escape`.

### `.claude/addons/codegraph/hooks/codegraph-turn-reset.py`

**[NIT]: An orphaned `.tmp-<hex>` file makes a session folder unprunable forever** — Line 50

```python
KNOWN_FILE_RE = re.compile(r"turn\.json|availability\.json|pruned|logged-[a-z0-9-]+|ticket-[0-9a-f]{64}")
```

**Problem.** The guard (`_atomic_write`, `guard:263`) and the tracker (`:107`) create `.tmp-<16 hex>` siblings. Both remove them on an `OSError`, but a hook killed between `os.open` and `os.replace` (the host's hook timeout, or a closed console) leaves one behind. `_eligible_files` then sees an unknown name and keeps the folder for good. The folder is small, but it is a leak the pruner was built to prevent.
```python
KNOWN_FILE_RE = re.compile(r"turn\.json|availability\.json|pruned|logged-[a-z0-9-]+|ticket-[0-9a-f]{64}|\.tmp-[0-9a-f]{16}")
```
(The 7-day age test still protects a live write.)

### `.claude/addons/codegraph/hooks/codegraph-first-guard.py`

**[NIT]: `state-unwritable` is logged on every call, including markdown, config and no-target calls** — Lines 746-748, 914-918

**Problem.** Step 0 runs before step 1, as the contract orders. In a session whose folder is unusable, every `Read` of a `.md` file therefore prints the notice and appends an `errors.jsonl` record. The README documents the per-call logging, but not that it covers non-source reads. Question for the author: was this intended? Running step 1's no-target and non-source exits before step 0 changes no verdict, because both allow, and would limit the noise to gated calls. If the contract order is meant literally, leave it as it is.

Verified as correct in this file (no finding):
- `_atomic_write` (`:258-278`) is sound. The temp name is random, created with `O_EXCL|O_NOFOLLOW|O_BINARY` and mode `0o600`, and `os.replace` replaces a link planted at the final name instead of writing through it. A failed replace onto a folder returns `False` and the guard fails open. The L rows pass, including the hard-link case.
- The `logged-<reason>` flag is created only after `log_event` reports a write (`:921-926`).
- `_inline_own_root` matches the helper, and the U-parity rows pass.
- I-4 holds: `main` catches every non-`SystemExit` exception and exits 0 (`:956-963`).
- I-3 holds: no variable switches the guard off, and `CLAUDE_SKIP_CG` is absent.
- I-2 holds: the block message names `mcp__codegraph__*`, the retry escape, the uninstall skill with a new session, `codegraph sync`, `codegraph init -i` and the install skill, and no shell route.
- Steps 0-7 match the contract's order.

### `.claude/scripts/auto_improve_finish_install.py`

**[NIT]: `--check` silently ignores `--stylesheet`, and `--expect-sha256` when given without `--apply`** — Lines 3634-3637

**Problem.** `--check` together with `--apply` is refused through `parser.error`. A `--check` call that also passes `--stylesheet` or a hash runs the check and drops those options without a word. This is harmless because the check only reads, but the refusal is inconsistent.

Verified (no finding):
- `--check` exits 2 for every refusal (`:3655-3659`) and 1 for findings.
- `permissions_allow` entries are validated against the add-on's own prerequisite servers (`_grant_server`, `:2055-2060`).
- The "covers every current and future tool" sentence is in the preview notes (`:2723-2725`).
- `released_sha256` is folded into the removal's deletable hashes (`:3162`), and the permission entry is listed under `kept` (`:3240`).
- `_codegraph_index_notes` refuses a verdict when the helper lacks `worktree_own_root` (addendum 2), and the U-parity and P-2 rows pass.

### `.claude/scripts/_claude_paths.py`

No finding. `worktree_own_root` is looked up with `getattr` (`:159`) and falls back to the inline copy. It is listed in `__all__` together with `WORKTREE_OWN_ROOT_NATIVE`, which follows the `:69-86` precedent (addendum 2). The inline copy matches the helper, and a parity row pins it.

### Untracked file

**[NIT]: `.claude/tdd-scratch-20261105-259.md` is a scratch file.** Do not add it to the commit, or delete it before committing.

---

## Contract audit

| Check | Result |
|---|---|
| Decision order 0-7 | matches (`guard:740-795`) |
| I-1 positive control | holds. The suites pass with C1, C2, C7, C9, task 3, the fallback rows and the non-git control blocking |
| I-2 block message | holds |
| I-3 no kill switch | holds |
| I-4 fail open on own error | holds in all three hooks |
| I-5 pruner (link test without `is_junction`, owner check, known names, per-file re-check, `rmdir` only, once per session, `before_remove` seam) | holds. See the `.tmp-` NIT |
| Wildcard only | holds. The repo-wide search finds individual tool names only in the two exempt hook tests, in `.claude/scripts/tests/*` (not shipped; the scan builds its own needles from parts) and in contracts, work items and contract history (not shipped). Every agent `tools:` line grants exactly `mcp__codegraph__*` |
| Held items NOT implemented | confirmed. The owner check is POSIX-only (`hasattr(os, "getuid")`), with no Windows owner check, and `--check` refusals stay exit 2 and are not turned into findings |
| Approval addendum 1-4 | met (a `None` root is tested before `tree_kind`; the `getattr` re-export plus `__all__` and the installer's undecidable note; isolated `TMP`/`TEMP` for in-process rows; `MECHANISMS.md:43` lists `worktree_own_root`) |
| Docs (README "Changed in 0.15.2", upgrade table, MECHANISMS amendment plus dated correction, VOCABULARY) | consistent with the code. `MECHANISMS.md:15` keeps its 2026-08-25 sentinel wording, and `:106` adds the dated correction, which follows the reach table (name span edited in place, corrections appended) |
| Files outside Files to touch | `.claude/hooks/_error_log.py` (WARN above). The `.claude/agent-memory/…`, `.claude/registries/JOURNAL.md` and `.claude/reviews/…` changes are process files and acceptable. `.claude/tdd-scratch-…md` must not be committed |
| Contract drift (Reused Mechanisms: `tree_kind` consumed as-is) | **violated** by the `_git_file_kind` change (BLOCKER) |
| Off-area drift | `.claude/area-mapping.json` has an empty `areas` object, so no area can be derived. Not applicable |
| End-User View | not applicable (no UI surface) |
| INTEGRATION.md | not applicable (no REST, SignalR or DTO surface) |

## Summary

| Severity | Count |
|---|---|
| BLOCKER | 1 |
| WARN | 1 |
| NIT | 5 |

**Verdict:** `FIX THEN SHIP`.

**Top priority fix:** restore HEAD's classification rule in `_project_paths._git_file_kind`. Keep the 4096-byte cap, strict decoding and a cross-host UNC/device refusal; drop the `/.git/worktrees|modules/` requirement there. Add bare-repository-worktree, separate-git-dir and main-checkout-guard regression rows.
