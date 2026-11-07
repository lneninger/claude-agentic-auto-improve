# Review — fullstack-code-reviewer — pass 3 (fresh context, final)

Contract: `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` (approved; Approval addendum 1-5 and Addendum 2 items 6-10 read as binding)
Branch: `fix/259-codegraph-guard-fail-open`, uncommitted working tree compared with `HEAD` (643b667).
Supersedes: `review-fullstack-code-reviewer-pass2.md`.

## How this pass was run

- I read the diff of `_project_paths.py`, `_error_log.py` and `_claude_paths.py` against `HEAD`, plus the guard, the installer's index-note block, the reset hook's file rules, the hop and regression test rows, README, MECHANISMS.md and JOURNAL.md.
- **Classifier comparison script** (outside the repo, in the system temp folder, using real `git` layouts). It loads `HEAD:.claude/hooks/_project_paths.py` and the working copy side by side and compares `_classify`:
  - main checkout, worktree under `<main>/.claude/worktrees/` (cwd a subfolder), worktree outside the main folder, bare-repository worktree, `--separate-git-dir` checkout, non-git folder: **identical to HEAD** in all six.
  - simulated mapped drive (where `os.path.realpath` turns `<main>` into `\\server\share\main`, which CPython ≥3.8 does on Windows for a mapped network drive): the worktree under `<main>` is identical to HEAD. **The worktree outside the main folder changes from `linked-worktree` (HEAD) to `undecidable` (new)** (W1).
- **AST comparison of the four copies of `_remote_host` / `_hop_allowed`** (helper, guard, bridge, installer, with annotations and docstrings stripped): identical.
- **Older-helper probe script.** The guard was loaded with `HEAD`'s real `tree_kind` / `main_checkout_root` bound and `worktree_own_root` unbound. Its `_main_candidate` on a tree whose `commondir` names `//fake-host-259.invalid/share/.git` made `realpath` and `isdir` calls on the fake host (W2).
- Suites, run one at a time as scripts:
  - `py -3 .claude/hooks/tests/test_codegraph_first_guard.py`: exit 0, **439 passed, 0 failed, 0 skipped**.
  - `py -3 .claude/hooks/tests/test_main_checkout_guard.py`: exit 0, **56 tests OK**.
  - `py -3 .claude/hooks/tests/test_worktree_path_guards.py`: exit 0, **189 passed, 0 failed**.
  - Also `py -3 .claude/scripts/tests/test_plugin_text_scans.py` (one file, not the discover run): exit 0.
- No production code or test file was edited.

## (1) Classifier: HEAD's classification is kept for the shapes pass 2 named

`_git_file_kind` now differs from HEAD only in:
- the capped, strict read;
- the cross-host refusal at each hop.

The `/.git/worktrees/`-or-`/.git/modules/` marker rule lives only in `_gitdir_pointer` (used by `worktree_own_root`), in the guard's `_inline_own_root.pointer` and in the bridge's `_inline_worktree_own_root.pointer`. Results:
- A bare-repository worktree reads `linked-worktree`, with main = the bare folder's parent. Checked on a real `git clone --bare` + `git worktree add`, and by V-B1.
- A `--separate-git-dir` checkout reads `main-checkout`.
- `test_main_checkout_guard.py:718` allows a Write in a bare-repository worktree.
- The pass-2 BLOCKER is closed.

### Every caller, and what it does with `undecidable`

| Caller | Call | On `undecidable` / `None` |
|---|---|---|
| `_main_checkout_guard.py:109-112` `_in_main` | `tree_kind`, `main_checkout_root` | treated as main checkout → **write blocked** |
| `_main_checkout_guard.py:118` `_check_tree` | `tree_kind` | **Block** "the tree of the target cannot be decided" |
| `_main_checkout_guard.py:479` (worktree add) | `main_checkout_root` | `None` root → not the flat folder → falls to `_check_tree` |
| `_main_checkout_guard.py:822-825` `decide` | `tree_kind`, `main_checkout_root` on the realpath'd session dir | `ctx.any_main=True` → every main-checkout-kind target counts as the session's |
| `pr_merged.py:3276-3296` (records sweep) | `main_checkout_root`, `tree_kind` | refuses `not-this-repository`, exit 2, before any delete (fails safe) |
| `flat_worktree.py:177, 205` | `main_checkout_root`, `tree_kind` | `main_root is None` → refused (fails safe) |
| `codegraph-first-guard.py:442-458` `_main_candidate` | `main_checkout_root` (then the inline walk, then the marker regex) | falls to candidate (b)/(c) |
| `codegraph-first-guard.py:488-497` `index_verdict` rule 2 | `worktree_own_root`, `tree_kind`, `main_checkout_root` | rule 2 does not fire → `index-present`, the gate stays (block-then-retry) |
| `auto_improve_finish_install.py:2586-2644` `_codegraph_index_notes` | the same three, through the bridge | an older helper gives `UNDECIDABLE_TREE_NOTE`; otherwise no claim |
| `_claude_paths.py:179-181` | `getattr` re-export of `worktree_own_root` | inline copy; `WORKTREE_OWN_ROOT_NATIVE=False` |

No landing or cleanup script calls these functions. `git_landing` / `cleanup` have no hits.

### The hop refusal against ordinary layouts

- Local layouts (all six above): unchanged.
- Repository genuinely on a UNC path, with the worktree on the same host: every hop names the same host → allowed (`hop //server/... vs //SERVER/...` → True; V-W1 same-host rows).
- Repository on a mapped drive, worktree under `<main>/.claude/worktrees/`: unchanged. The first two hops are drive-letter (local) paths. After `realpath`, `common` and `realpath(folder)` are both `\\server\share\...`.
- **Repository on a mapped drive, worktree on another volume:** regressed → W1.
- **Tree reached through a drive letter whose `gitdir:` was recorded in UNC form** (`git worktree add` run from a UNC working directory): the first hop compares `\\server` with the unresolved `Z:` folder → refused → `undecidable`. HEAD decided it. → W1.
- Exactly-4096-byte first line with no newline → `""` → undecidable. 4095 bytes + `\n` → read. A CRLF line → `\r` stripped. Invalid UTF-8 → `UnicodeDecodeError` → caught → undecidable, as HEAD did. All checked directly against `_read_gitdir_line`.

## Findings

### `.claude/hooks/_project_paths.py`

**[WARN] W1: the post-`realpath` same-host test makes a mapped-drive repository with a worktree on another volume `undecidable`, so the main-checkout guard now blocks every write there.** Lines 612, 615, 622, 625

```python
if not raw or not _hop_allowed(raw, folder):              # 612: compares with the UNRESOLVED folder (Z:\...)
...
common = os.path.realpath(joined)                         # Z:\repo\.git -> \\server\share\repo\.git
if not _hop_allowed(common, os.path.realpath(folder)) ... # 625: own = C:\wt (local) -> refused
```

**Problem.** CPython's `ntpath.realpath` turns a mapped network drive into its UNC form.
- **Case 1.** Worktree `C:\wt`, main `Z:\repo` (mapped). The `gitdir:` and `commondir` hops are drive-letter paths and pass. `realpath` then yields `\\server\share\repo\.git`. That is compared with `realpath(C:\wt)`, which is local, so it is refused. Result: `undecidable`, where HEAD said `linked-worktree`. Reproduced with a simulated `realpath`; the comparison script printed `wt-outside same=False HEAD=('linked-worktree', '\\server\share\main') NEW=('undecidable', None)`.
- **Case 2.** The first hop compares against the unresolved `folder`. A `Z:` tree whose `.git` says `gitdir: //server/share/...` is therefore refused too.
- **Effect on the callers above.** The main-checkout guard blocks every Write/Edit in that worktree (`_check_tree`, `_in_main`). `pr_merged --sweep-records` and `flat_worktree` refuse.
- **The security goal is not served.** The SMB connection to that host already exists: the drive is mapped, and the `isdir(target)` on `Z:` already reached it. The refusal protects nothing there.
- It is the pass-2 failure class (a hardening rule walls an enforcing caller), on a narrower layout.
- **The same effect on the caller side.** `codegraph-first-guard.py:493` and `auto_improve_finish_install.py:2634` compare a realpath'd `main` (UNC) with an unresolved `root` (`Z:`). So `index-other-tree` can never fire on a mapped drive, which fails toward gating.

**Fix.** Judge each hop against the hosts the tree already reaches: the unresolved folder AND its realpath. For the `commondir` hop, also accept the realpath of the folder it hops from:

```python
own_hosts = {_remote_host(folder), _remote_host(os.path.realpath(folder))}
def _hop_ok(t): h = _remote_host(t); return h is None or (bool(h) and h in own_hosts)
...
common = os.path.realpath(joined)
if not (_hop_ok(common) or _remote_host(common) == _remote_host(os.path.realpath(target))) or not os.path.isdir(common):
    return "undecidable", None
```

Mirror the rule in the two inline copies and the two caller-side checks. Compare with `os.path.realpath(root)` / `os.path.realpath(path)` there. Add a row with a patched `realpath` that maps `<main>` to `\\server\share` (the comparison script's technique), for the outside-volume layout. This changes the wording of Addendum 2 item 7 ("the same host as the tree's own path"), so it needs one contract line. Alternatively, the user accepts the regression in writing and the README names it.

**[NIT] N1: a device-form own path is refused even when it names a local drive or the same host.** Lines 565-580

`_remote_host` returns `""` in two cases:
- `\\?\C:\...`;
- `\\.\UNC\host\share`, which is a valid device form of a UNC path. Only `\\?\UNC\` is parsed for its host.

`_hop_allowed` then refuses both, even when the target is the same local drive. A payload `cwd` / `CLAUDE_PROJECT_DIR` in `\\?\` form (or a `realpath` that kept the prefix) turns an ordinary tree `undecidable`, so the main-checkout guard blocks. The input is rare. Either parse `\\.\UNC\` like `\\?\UNC\`, and strip `\\?\X:\` / `\\.\X:\` to a local drive path before the host test, or document the refusal.

**[NIT] N2: shared `_SESSION_ID_RE` changed outside the contract.** Line 906

The grammar now rejects a trailing `.`. It feeds `session_marker_path`, which the database guard's deferral uses. The change is justified, because Windows strips a trailing dot, and benign, because Claude Code session ids are UUIDs. But the contract's Session key row cites the old grammar, and no note records the change to a shared mechanism. Add one sentence to MECHANISMS.md or to the contract.

### `.claude/addons/codegraph/hooks/codegraph-first-guard.py`

**[WARN] W2: the caller-side hop check runs AFTER the older helper's call, so an older `_project_paths.py` still probes the other host, now on every Read/Grep/Glob.** Lines 442-447, 489-492

```python
if _pp_main_checkout_root is not None:
    found = _pp_main_checkout_root(path)        # HEAD's helper: isdir()/realpath() on //other-host/... happen HERE
    if found and _hop_allowed(found, path):     # the refusal only discards the answer
```

**Problem.** Addendum 2 item 7 puts the refusal on the caller side "so an older helper cannot reopen it". The add-on copies `_project_paths.py` only when the project lacks it, so an upgraded project commonly holds the 0.15.1 helper. That helper has `tree_kind` / `main_checkout_root` but no hop refusal and no `worktree_own_root`. The probe script ran the guard with HEAD's real functions bound. It recorded `realpath(//fake-host-259.invalid/share/.git)` and `isdir(//fake-host-259.invalid/share/.git)`. In HEAD, the codegraph guard never called the classifier, so this is a new probe path on reads.

The V-W1 "older helper" rows (`test_codegraph_first_guard.py:1223-1224, 1235-1236`) stand the older helper in with `lambda path: "linked-worktree"` / `lambda path: remote`. Those make no file-system call, so the "probes nothing" check cannot fail. The installer is safe, because `_codegraph_index_notes` refuses a verdict unless `WORKTREE_OWN_ROOT_NATIVE`.

**Fix.** Call the helper's tree functions only when it is the hardened release, the release that defines `worktree_own_root`. Otherwise use Guard fallback mode, where the inline walk is hardened:

```python
_HELPER_HARDENED = _pp_worktree_own_root is not None
_pp_tree_kind = getattr(_pp, "tree_kind", None) if _HELPER_HARDENED else None
_pp_main_checkout_root = getattr(_pp, "main_checkout_root", None) if _HELPER_HARDENED else None
```

Under an older helper rule 2 then cannot fire. That is the contract's own Guard fallback rule for unbound tree functions. The round-5 critique note "rule (2) still fires there" needs one contract line. In the test, replace the lambdas with HEAD's real functions, loaded from `git show HEAD:.claude/hooks/_project_paths.py` or from a frozen copy in the fixture.

### `.claude/hooks/tests/test_codegraph_first_guard.py` (and the installer test)

**[WARN] W3: no row pins the four copies of `_remote_host` / `_hop_allowed` to each other.** No test file names either function.

The copies:
- helper `_project_paths.py:565-580`;
- guard `codegraph-first-guard.py:370-386`;
- bridge `_claude_paths.py:114-129`;
- installer `auto_improve_finish_install.py:2568-2583`.

They are identical today: an AST comparison with annotations and docstrings stripped gives `identical: True` for both functions. Coverage today:
- **U parity** compares the three `worktree_own_root` walks, on local fixtures only.
- **U-H** runs the hostile rows per walk copy.
- **The installer's copy** is exercised only through "probes nothing" rows.

No row checks same-host acceptance or the device forms across the four copies. A later edit to one copy (for W1 or N1) can drift silently. That is the failure mode the contract's parity rule exists for.

**Fix.** Add one table-driven row that loads all four modules and asserts equal answers over the same inputs. Use: local, `//h/s` vs `//H/s`, `//h/s` vs `//g/s`, `\\?\UNC\h\s`, `\\.\UNC\h\s`, `\\?\C:\x`, `""`, and `//`. Or add an AST-equality row like this pass's script.

### `.claude/registries/MECHANISMS.md`

**[WARN] W4: line 43 does not record that `tree_kind` / `main_checkout_root` now refuse cross-host pointers, and it understates when `worktree_own_root` returns `(folder, None)`.** Line 43

The entry says `(folder, None)` means "a readable file with no `gitdir:` line". The implementation also returns it for:
- a bare-repository worktree;
- a `--separate-git-dir` checkout;
- a gitdir naming another host;
- a gitdir without the `/.git/worktrees|modules/` marker;
- a first line cut off at 4096 bytes.

The shared classifier gained new `undecidable` outcomes, at each hop and after `realpath`, and nothing in the registry says so. The new JOURNAL lesson ("list its callers and the action each takes on the new outcome") depends on consumers finding that out in the registry.

**Fix.** Append a dated correction: the marker rule and the `(folder, None)` cases of `worktree_own_root`; the cross-host / 4096-byte / strict-UTF-8 `undecidable` outcomes of `tree_kind` and `main_checkout_root`; "callers that block on `undecidable` (the main-checkout guard) inherit them".

### `.claude/addons/codegraph/hooks/codegraph-turn-reset.py`

**[NIT] N3: unescaped dot in `TICKET_RE`.** Line 46

`r"ticket-[0-9a-f]{64}|.tmp-[0-9a-f]{16}"` matches `xtmp-...`. `KNOWN_FILE_RE` (line 50) escapes it. Make it `\.tmp-`. The effect is limited to plain files inside the session's own folder.

### Files to touch

**[NIT] N4: three paths outside the Files-to-touch list.**
- `.claude/hooks/tests/test_main_checkout_guard.py` is changed (+37). Addendum 2 item 7 requires its regression row but does not list the file; add it.
- `.claude/tdd-scratch-20261105-259.md` is untracked and not git-ignored. Do not commit it.
- `.claude/agent-memory/agentic-auto-improve-test-strategy-critic/*` belongs to another agent's memory and is outside the contract. Confirm it is intended for this pull request.

`.claude/hooks/_error_log.py` is covered by Addendum 2 item 6. The guard creates the `logged-<reason>` flag only when `log_event` did not return `False` (`codegraph-first-guard.py:940-945`). A `None` return from an older copy counts as written. Other callers ignore the value. This item is met.

## (2)-(6) Other checks: no finding

- **(2) Copies in step:** yes (AST-identical). They are not pinned (W3).
- **(3) Older helper:** the installer refuses a verdict (`WORKTREE_OWN_ROOT_NATIVE`) → met. The guard → W2.
- **(4) Invariants and held items:**
  - **I-1 to I-5:** exercised by the guard suite (positive controls, I-2 message scan, the escape's single use, the pruner seams; 439/0/0).
  - **No kill switch:** the guard reads only `CLAUDE_PROJECT_DIR` and `CLAUDE_CONFIG_DIR`.
  - **Fail-open on internal errors:** `main()` turns any `Exception` into exit 0.
  - **Wildcard only:** the text-scan suite passes. Prefixed or bare names appear only in the two exempt files and in unshipped `.claude/scripts/tests/*`.
  - **Held items:** not implemented. `folder_usable` checks the owner only where `os.getuid` exists. `codegraph-tool-named` is still a refusal (`_tool_named_refusal`).
  - **Items 8 and 9:** `KNOWN_FILE_RE` includes `\.tmp-[0-9a-f]{16}`, and the server name grammar is `[A-Za-z0-9][A-Za-z0-9_-]*`.
- **(5) Files to touch:** see N4.
- **(6) Docs:**
  - The README states 383 cases for `test_auto_improve_finish_install.py`, and `def test_` counts 383 (HEAD: 344).
  - The upgrade table has rows per install age.
  - The hooks.json cost text names three program starts.
  - The MECHANISMS.md CodeGraph correction line replaces the sentinel and the shell way out.
  - W4 is the one gap.

## Contract audit

| Item | Outcome |
|---|---|
| Data Shapes (Own tree root, Caller tree, Index ownership, Session key) | partly met: N2 changes the shared Session-key grammar silently. W1 changes a classifier outcome the contract says is consumed as-is, by Addendum 2's own rule. |
| Reused Mechanisms (tree classification consumed as-is) | partly met: HEAD's classification is restored for local layouts. Mapped-drive cross-volume is a regression (W1). |
| Addendum 2 item 7 (older helper cannot reopen the hop) | not met on the guard side (W2); met on the installer side |
| Addendum 2 items 6, 8, 9, 10 | met |
| Off-area drift | `.claude/area-mapping.json` has no areas, so no area can score. N4 lists the file-level drift. |
| End-User View | not applicable (no UI surface) |

## Summary

| Severity | Count |
|---|---|
| [BLOCKER] | 0 |
| [WARN] | 4 |
| [NIT] | 4 |

**Verdict:** FIX THEN SHIP.

**Top priority fix:** W2 is a security claim of the contract that does not hold, and its test cannot fail. Bind the helper's tree functions only when the helper is the hardened release, and test with HEAD's real functions. Then fix W1, or get the user's written acceptance of it, because it walls writes in an enforcing guard.
