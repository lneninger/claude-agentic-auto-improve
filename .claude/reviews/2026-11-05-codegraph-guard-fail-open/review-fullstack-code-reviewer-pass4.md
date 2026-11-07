# Review pass 4 — fullstack-code-reviewer — codegraph guard fail-open (#259)

Contract: `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` (approved; Approval addendum 1-5, Addendum 2 items 6-10 and Addendum 3 items 11-14 read as binding).
Branch: `fix/259-codegraph-guard-fail-open`, uncommitted working tree compared with `HEAD` (643b667).
Supersedes: `review-fullstack-code-reviewer-pass3.md`.
Held for the user and not judged as regressions: the Windows owner check / per-user parent folder; `codegraph-tool-named` as a refusal.

## How this pass was run

- Read the contract and its three addenda, the pass-3 report, and the diffs of `_project_paths.py`, `_error_log.py` and `_claude_paths.py`. Read the guard's hop, walk, candidate, index-verdict and decision code, the installer's hop copy and `_codegraph_index_notes`, and the W-11/W-13/W-14 test rows.
- **Real-layout probe** (a script in the system temp folder, outside the repo, run with `py -3 -I`). It built real `git` 2.56 layouts and compared `tree_kind` / `main_checkout_root` from `HEAD:.claude/hooks/_project_paths.py` with the working copy. It also printed `worktree_own_root`. **0 differences in 18 layouts:**
  - main checkout, and a subfolder of it;
  - worktree under `<main>/.claude/worktrees/`, cwd two folders deep;
  - worktree outside the main folder;
  - worktree made with `git worktree add --relative-paths` (`gitdir: ../main/.git/worktrees/relwt`);
  - hand-written `gitdir: ../../.git/worktrees/handx`, with a `commondir` of `../..`;
  - bare-repository worktree (`linked-worktree`), `--separate-git-dir` checkout (`main-checkout`), non-git folder;
  - the same paths spelled with forward slashes, with `..` components, with doubled separators, and with mixed separators;
  - device form `\\?\C:\...` of the main checkout and of the outside worktree;
  - real UNC `\\localhost\C$\...` (the admin share, read only) for the main checkout and both worktree layouts.
  - Local relative `..` gitdirs stay decidable. The `..` refusal only applies when `_remote_host` is not `None`, so only to UNC and device paths.
- **Mapped-drive simulation with a reachable UNC.** `ntpath.realpath` was patched to map a folder to `\\localhost\C$\...`, so `isdir` still works.
  - Scenario A: the main checkout is on the "mapped drive" and the worktree is on the local volume. The outside, relative and inner worktrees read `linked-worktree` with main = the UNC form, the same as HEAD. The pass-3 W1 case 1 is closed.
  - Scenario B: the whole tree is reached through the mapped drive, and the worktree's `.git` records `gitdir: //localhost/C$/.../main/.git/worktrees/outside`. It reads `linked-worktree`, the same as HEAD. The pass-3 W1 case 2 is closed.
  - Controls: the same file naming `//fake-host-259.invalid/...` gives `undecidable`. A same-host gitdir containing `/x/../` gives `undecidable`.
- **Guard probe.** The guard was loaded beside the working helper, then beside HEAD's real helper, with `main/.codegraph/codegraph.db` planted.
  - Working helper: `index-other-tree` for all four worktree shapes and for the UNC worktree; `index-present` for the main checkout; `no-index` for the bare-repository worktree, the separate-git-dir checkout and the non-git folder.
  - HEAD's helper: `tree_kind` / `main_checkout_root` are NOT bound, and every worktree reads `index-present` (rule 2 cannot fire, as Addendum 3 item 13 says).
  - A `commondir` naming a fake host: no `isdir` / `isfile` / `exists` / `realpath` call reached the fake host in either mode.
- **Post-commit simulation of the W-13 rows** (B1 below). The test module was imported with `head_helper_text` patched to return the working copy. That is what `git show HEAD:` returns once this change is committed. Then only `run_older_helper_real` was run.
- Suites, run one at a time as scripts, in the foreground:
  - `py -3 .claude/hooks/tests/test_codegraph_first_guard.py`: exit 0, **607 passed, 0 failed, 0 skipped**.
  - `py -3 .claude/hooks/tests/test_main_checkout_guard.py`: exit 0, **57 tests OK**.
  - `py -3 .claude/hooks/tests/test_worktree_path_guards.py`: exit 0, **189 passed, 0 failed**.
  - Also these single files, not the discover run: `test_plugin_text_scans.py` (exit 0, 19 OK), `test_plugin_manifests.py` (exit 0, 190 passed) and `test_auto_improve_finish_install.py` (exit 0, 385 OK).
- I did not start any background process. I edited no production code and no test. My only repo edits are this report, its gate file, and one JOURNAL.md entry.

## (1) Addendum 3 items 11-14

| Item | Status | Evidence |
|---|---|---|
| 11 normalise, then check | met | All four `_hop_allowed` copies judge the text and `os.path.normpath(text)`, and refuse a `..` segment when the host is not `None` (`_project_paths.py:581-591`, `codegraph-first-guard.py:390-400`, `_claude_paths.py` bridge copy, `auto_improve_finish_install.py:2584-2594`). The `commondir` join is `normpath`'d before it is checked, and the realpath'd form is checked again before `isdir` (`_project_paths.py:640-648`). |
| 12 same-host rule | met | `_own_spellings` gives the written form plus its `realpath` (local paths only). The `commondir` hop is judged against `_own_spellings(target) + _own_spellings(folder)`. Device-form own paths are judged by drive (`?c:`) or by host. The mapped-drive layouts above read as HEAD read them. |
| 13 older helper | met in the code; **the test breaks on commit (B1)** | `codegraph-first-guard.py:82-84` binds the tree functions only when `_hop_allowed` is callable. The test loads HEAD's real file, as the addendum says, but that file is the NEW helper once this lands. |
| 14 housekeeping | met | The parity row covers four modules (`test_codegraph_first_guard.py:1777-1813`, mods at `:2045`). `TICKET_RE` escapes the dot (`codegraph-turn-reset.py:46`). The server-name grammar is `auto_improve_finish_install.py:235`, plus `"__" not in` at `:2033`. MECHANISMS.md has the dated correction on line 45. `test_main_checkout_guard.py` is in Files to touch. |

## (2) Regression check against HEAD, by consumer

The classifier gives the same answer as HEAD on every real layout above, so the consumers that only call `tree_kind` / `main_checkout_root` behave as at HEAD on those layouts. Those consumers are `_main_checkout_guard.py`, `pr_merged.py` and `flat_worktree.py`; none of them is modified in this diff. No landing or cleanup script calls these functions. New `undecidable` outcomes exist only for a cross-host or `..`-climbing UNC/device pointer, a first line over 4096 bytes, and invalid UTF-8; HEAD already gave `undecidable` for invalid UTF-8. The guard and the installer were probed above.

## Findings

### `.claude/hooks/tests/test_codegraph_first_guard.py`

**[BLOCKER] B1: the W-13 "older helper" rows load `HEAD:.claude/hooks/_project_paths.py`, so they fail as soon as this change is committed.** Lines 2062-2070 (the loader), 2109-2112, 2129-2130, 2150-2154, 2196-2197 (the rows that fail).

```python
proc = subprocess.run(["git", "-C", str(af.PROJECT_ROOT), "show", "HEAD:.claude/hooks/_project_paths.py"], ...)
...
check("W-13 fixture: the helper the guard found is HEAD's (it has the tree functions and NO _hop_allowed)", ...)
```

**Problem.** Today HEAD is 643b667, which holds the 0.15.1 helper, so the rows pass. After the commit, HEAD's helper is this change's helper. It has `_hop_allowed` and `worktree_own_root`, and it probes nothing. I simulated that state by patching `head_helper_text` to return the working copy. **Five rows FAIL:**
- `W-13 fixture` (the helper "has NO _hop_allowed");
- `W-13 control` (HEAD's `main_checkout_root` "probes the fake host");
- `W-13: the guard does not bind HEAD's tree_kind`;
- `W-13: ... does not bind HEAD's main_checkout_root`;
- `W-13 installer: ... one plain note` (it gets `[]`).

The suite then exits non-zero on this pull request's own head commit, on `master` after the merge, and in every later run. That breaks the TASK block's "all must pass". The contract's own wording (Addendum 3 item 13, "`git show HEAD:...`") carries the defect, so the implementer followed it literally. JOURNAL lesson appended.

**Fix.** Pin the older release explicitly, and skip when it is not reachable:

```python
OLDER_HELPER_REF = "643b667"  # last commit before #259 (0.15.1); a tag works too
proc = subprocess.run(["git", "-C", str(af.PROJECT_ROOT), "show", f"{OLDER_HELPER_REF}:.claude/hooks/_project_paths.py"], ...)
```

Even better, check in a frozen copy, for example `.claude/hooks/tests/fixtures/_project_paths_0_15_1.py`. It needs no git history, so it also works in a shallow clone. Keep the fixture check ("NO `_hop_allowed`"): it is the tripwire that proves the pin is right. Add one line to Addendum 3 item 13 that replaces `HEAD` with the pinned ref.

---

**[NIT] N1: the parity row does not pin `_own_spellings`, and it calls `_hop_allowed` only with one own spelling.** Lines 1801-1813

`_own_spellings` is a fifth function with four textual copies (helper `:594-598`, guard `:403-407`, bridge, installer `:2597-2601`). The `*also` argument, which is the item-12 realpath half, is never passed in the parity table. A later edit to one copy's realpath handling would not be caught. Add `_own_spellings` to the `_remote_host` loop, and add a `(target, own, realpath_form)` row to the `_hop_allowed` loop.

### `.claude/hooks/_project_paths.py` (and the three copies)

**[NIT] N2: device forms that are still refused outright.** Lines 565-578
- `\\.\UNC\host\share` returns `""`, so it is always refused. Only `\\?\UNC\` is parsed for its host.
- A device-form target on a local drive (`\\?\C:\...`) is refused when the tree's own path is written plainly (`C:\repo`), because `?c:` is not in the allowed set.

git never writes either form into `gitdir:` / `commondir`, so no real layout is affected (the device-form own-path probes above match HEAD). The four copies agree, and the parity row pins them. Either document the refusal in the MECHANISMS.md correction, or map `\\?\X:` / `\\.\X:` to local and parse `\\.\UNC\`.

**[NIT] N3: the shared `_SESSION_ID_RE` grammar changed and is still not recorded** (`_project_paths.py:928`; carried over from pass-3 N2). The contract's Session key row (line 58) still cites `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`. The new grammar forbids a trailing `.`. The change is benign, because session ids are UUIDs, but the contract or MECHANISMS.md should say so in one line, since `session_marker_path` (the database guard's deferral) shares it.

### Files to touch audit (item 5)

**[NIT] N4: paths outside the Files-to-touch list, and what must not be committed.**
- Covered by addenda: `.claude/hooks/_error_log.py` (Addendum 2 item 6; `log_event` returns a bool, and the guard creates the `logged-` flag only when the return is not `False`, at `codegraph-first-guard.py:962-967`) and `.claude/hooks/tests/test_main_checkout_guard.py` (Addendum 3 item 14).
- Process artefacts, expected in the pull request: the concept contract, `.claude/contract-history/*.round-1..4.md`, `.claude/work-items/2026-11-05-259-...md`, `.claude/reviews/2026-11-05-codegraph-guard-fail-open/*`, and the four 2026-11-05 entries in `.claude/registries/JOURNAL.md` (three from reviewers, one from this pass).
- **Other agents' memory, outside the contract, which the user must decide on:** `.claude/agent-memory/agentic-auto-improve-test-strategy-critic/MEMORY.md` (modified), `.../swap-tests-vs-abort-on-failure.md` (new), and `.claude/agent-memory/agentic-auto-improve-security-auditor/` (new: `MEMORY.md` and `unc-host-check-normpath-collapse.md`).
- **Must NOT be committed:** `.claude/tdd-scratch-20261105-259.md`. It is untracked and not git-ignored (`git check-ignore` exits 1), so a blanket `git add .claude/` would pick it up.

## (3) Copies in step

`_remote_host` and `_hop_allowed` are textually identical in all four copies (side-by-side read; only the type annotations differ), and the W-14 parity rows pass. The walk (`worktree_own_root` and its two inline copies) is pinned by the U and V rows. `_own_spellings` is identical in the four copies but not pinned (N1).

## (4) Invariants

- **Decision order 0-7:** matches the contract (`codegraph-first-guard.py:787-836`).
- **I-1:** positive controls block in the suites.
- **I-2:** the block message (`:911-927`) names `mcp__codegraph__*`, the retry escape, the uninstall skill with "new session", `codegraph sync`, `codegraph init -i` and the install skill. It names no single tool, no shell route, no `CLAUDE_SKIP_CG` and no `references/` path.
- **I-3:** no kill switch. The guard reads only `CLAUDE_PROJECT_DIR`, `CLAUDE_CONFIG_DIR` and the temp folder.
- **I-4:** `__main__` turns any `Exception` into exit 0 (`:997-1004`). Internal errors in the tree calls are caught locally, and the gate stays.
- **I-5:** the pruner rows (X, X-8) pass.
- **Wildcard only:** `permissions_allow` is `mcp__codegraph__*`, and the text-scan suite passes.

## (6) README and docs counts

- The README says `test_auto_improve_finish_install.py` has 385 cases. `def test_` counts 385, and the run reports 385.
- The 0.15.2 note and the upgrade table by install age are present.
- All five version entries read 0.15.2: `plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, and the two entries in `marketplace.json`.
- `check_version_bump.py` reports "no shipped plugin file changed" only because nothing is committed yet. Re-run it after the commit.

## Contract audit

| Item | Outcome |
|---|---|
| Data Shapes | met, apart from N3 (the Session-key grammar text is stale) |
| Reused Mechanisms (tree classification consumed as-is) | met: identical to HEAD on 18 real layouts, plus mapped-drive scenarios A and B |
| Addendum 3 items 11, 12, 14 | met |
| Addendum 3 item 13 | met in the code; the test is self-invalidating (B1) |
| Off-area drift | `.claude/area-mapping.json` has no areas, so none can score. File-level drift is listed in N4. |
| End-User View | not applicable (no UI surface) |

## Summary

| Severity | Count |
|---|---|
| [BLOCKER] | 1 |
| [WARN] | 0 |
| [NIT] | 4 |

**Verdict:** FIX THEN SHIP. The production code is clean: no regression on any real layout, every invariant holds, and pass 3's W1-W4 and N3 are closed. The one blocker is a test row that goes red the moment the change is committed.

**Top priority fix:** B1. Pin the W-13 older helper to `643b667` (or a frozen fixture copy) instead of `HEAD`, and add one line to Addendum 3 item 13. Then commit without `.claude/tdd-scratch-20261105-259.md`.
