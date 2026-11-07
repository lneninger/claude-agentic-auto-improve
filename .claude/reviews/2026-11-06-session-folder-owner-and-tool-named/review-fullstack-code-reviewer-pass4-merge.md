# Review pass 4 (merge of origin/master), fullstack-code-reviewer

**Scope:** the staged, uncommitted merge of `origin/master` (merge head `bc398b5`, 0.16.2) into
`fix/271-session-folder-owner-and-tool-named` (pre-merge head `e9cbc05` / `3eba585`, 0.15.3). The pull request will hold
`git diff origin/master`. Cold context: nothing from passes 1-3 was taken on trust.

**Contracts:** `.claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md` (approved, this PR) and
`.claude/concepts/2026-11-05-codegraph-hooks-redesign.md` (master, #261).

**Method:** a three-way read of the guard (merge base `c8653e3`, master `bc398b5`, ours `e9cbc05`, merged working tree),
the full merged guard read line by line, the `master -> merged` diff read hunk by hunk, AST parity of the three hooks,
folded hashes recomputed from git objects, probes in a scratch folder (`C:\Temp\rv271p4\`), the bench run once with a
scratch `LOCALAPPDATA`, and the suites (results below).

---

## Verdict up front

**Shippable after one small fix (FIX THEN SHIP).** The guard merge is right. Master's redesign is intact and so is #271.
No CRITICAL. One WARN is a merge casualty that has to be fixed before merging: master's new bench script was never moved to
the Per-user session parent. It cannot measure the merged guard, and run as documented it writes session folders into the
developer's real `%LOCALAPPDATA%`. The other WARN is a missing test row for the one path the merge order created.

---

## 1. The guard merge (the main risk)

`diff master.py merged.py` holds only #271's changes, and nothing of master's is missing or edited outside them. Checked
item by item:

| Master behaviour (#261) | State in the merged file |
|---|---|
| Lazy imports (G-1): `_import_helper`, `_load_log_event`, `_load_project_paths`, module `__getattr__`, `_late` | Unchanged apart from the Hop proof expression (ours). `resolve_session_parent` imports neither helper, so SH-G1a (marker present, `_project_paths` and `_error_log` left unimported) still holds. |
| Marker before classification (G-1) | Kept: step 1 marker, step 2 targets. |
| Plan / apply split (G-2): `Plan`, `_plan`, `plan_live`, `apply_state`, `evaluate`, `decide` signature | Kept. `apply_state` still never re-decides an allow; ours only replaces the old `fail-open:state-unwritable` return with the re-resolve that gives `session-state-unusable` or `retry-ticket-unwritten`. |
| Shadow decision (S-1..S-4): `shadow_section`, `read_transcript`, cursor, log, `BaseException` swallow in `main` | Byte-identical to master. `use_cursor = live.step0_ok and _cursor_folder_ok(...)`, so an unusable state reads and writes no cursor (the Stateless rule holds for the shadow too). |
| Reset hook pruner knows `transcript-cursor.json` / `.<pid>.tmp` | Kept in the merged reset hook (`KNOWN_FILE_RE`, docstring). |
| Text-scan fix (`CG_EXEMPT_RECORDED`, folder-prefix exemption plus its narrowness control) | Kept in `test_plugin_text_scans.py`. |

| #271 behaviour | State in the merged file |
|---|---|
| Per-user parent, pure base rule, Remote rule, drive table before realpath, splitdrive refusal | Present, `:351-514`. |
| Stateless session (no fs call while `problem` is set: `ensure_folder`, `has_plain_file`, `read_json`, `create_once`, `announce`) | Present. An unresolved `Session` starts as `check-failed`, so it is stateless by default. |
| Fail closed at step 7 without a ticket; one block record per call | `_plan:1166-1170`, `block()`. |
| `retry-ticket-unwritten`, the link-swap re-resolve | `apply_state:1197-1202`. |
| Banner by reason (I-7c), escaped output (`backslashreplace`, `safe` details), `build()` fallback | `block():1323-1416`. |
| Foreign marker, logged once, flag after the record | `marker_cause`, `note_foreign_marker`, `main:1846-1850`. |
| `check-failed` from any exception in the verdict | `resolve_session_parent:490`, `session_folder_problem:501,512`. |
| Hop proof / `TREE_HOP_REFUSAL` | Guard `:146-151`, helper `:565`, bridge `:202-204,233`, installer `:2645`. `WORKTREE_OWN_ROOT_NATIVE` is gone from shipped code. |

**Probe (subprocess, scratch home):** with `LOCALAPPDATA` relative, unset and usable, a `Read` of `README.md`, a `Read`
with no target and a `Glob **/*.md` each exit 0 with empty stderr. A `Read` of `a.py` blocks in all three cases
(`session-state-unusable` for the first two, `source-target` for the usable one). An unusable state creates nothing under
the home folder.

### The bent contract detail: accept it

The contract's step 1 runs classification first, so that nothing is resolved for a non-source target. Master's G-1 runs
the marker check before classification. I-6 allows the marker to be read only from a folder proven usable. So in the
merged order the verdict must come first. The other ways out are worse:

- Classify first: this drops G-1's saving on the commonest call, a source read after a CodeGraph call, and breaks
  SH-G1a/SH-G1b, which the redesign contract says must pass unedited.
- Read the marker before the verdict: this breaks I-6, the whole point of #271.

**What it costs**, measured (`probe_cost.py`, Windows 11, Python 3.12.10):

- `import ctypes` takes 7.9 ms the first time, and every call on Windows reaches it, because `LOCALAPPDATA` has a drive
  letter.
- `resolve_session_parent` then takes about 0.8 ms a call.
- On a non-source call that is the first of its session, the parent is created (one `mkdir 0700` in the user's own base).

The visible outcome does not change: the exit code and the empty stderr are the same as the contract's order gives
(probe). **Keep the merged order. Write it into the contract as a divergence note**: the reviewer leaves the contract
untouched, so the implementer or `/pr-merged` adds it. I recorded the lesson in JOURNAL (see Registries).

## 2. Shared functions across the three hooks

AST comparison of every top-level function and constant the three hooks share. These are SAME:

- `session_parent_base`, `_base_shown`, `_create_parent`, `resolve_session_parent`, `session_folder_problem`
- `_remote_host`, `_own_spellings`
- `PARENT_NAME`, `PARENT_PROBLEMS`, `_LOCAL_DEVICE_HOST_RE`, `_SESSION_ID_RE`, `_REPARSE_POINT`, `SESSION_PREFIX`,
  `MARKER_NAME`
- `MARKER_WRITER` (guard and tracker)

`_is_link_stat` differs in its docstring only. `session_key` is written differently in the guard but computes the same
value. Both were already like that before #271, and the merge did not touch them.

## 3. `addon.json` and the pinned hashes

I recomputed the folded SHA-256 (BOM stripped, CRLF to LF) from the git objects:

| Ref | guard | reset | tracker |
|---|---|---|---|
| `e4f392c` (0.15.2) | `8c44ed60…` | `900db4ad…` | `7e2daa3a…` |
| `bc398b5` (0.16.2) | `575c83f3…` | `3a1658c9…` | `7e2daa3a…` |

- All six values are in `released_sha256`.
- `test_plugin_manifests.py` pins both sets as literals.
- `test_auto_improve_finish_install.py::test_the_shipped_manifest_lists_every_released_version…` pins the 0.16.2 guard
  and reset hashes as literals too.
- The only guard commits on master between 0.15.2 and 0.16.2 are `e4f392c` and `fa3c3eb` (0.16.0), and `fa3c3eb` has the
  0.16.2 hashes. So no released copy is missing.
- The 0.15.3 copies (`e9cbc05`) were never released, so leaving them out is right.

## 4. Version

- All five entries read 0.16.3 (`plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, and both
  entries in `marketplace.json`). That is a patch raise over master's 0.16.2.
- `check_version_bump.py` run on the uncommitted merge reads the committed HEAD (0.15.3), so it reports "still 0.15.3".
  That is expected before the merge commit. Run it again after committing.

## 5. Shipped text against the merged code

**Re-grep** (the contract's list, over README, skills, references, addons, hooks, scripts and registries; JOURNAL is
history). Each remaining hit:

- README `:310, :312, :333, :352`: "system temp folder" as the old location in the 0.16.3 block and its upgrade row.
  Correct.
- README `:319`, "reverses 0.15.2's `state-unwritable` fail-open". Correct.
- README `:326`, "replaces `WORKTREE_OWN_ROOT_NATIVE`". Correct.
- Install skill `:173`: the 0.15.2 temp folders. Correct.
- Uninstall skill `:27`: the Per-user session parent. Correct.
- Decision table `:109`: "the system temp folder is never used". Correct.
- Hook docstrings: "never read, written or pruned". Correct.
- Guard `:979`: the #612 comment about a background command's file in the temp folder. Unrelated, stays.
- `nudge` appears only in the angular-tailwind advisor and `plan-question-advisor.py`. Unrelated.
- `gettempdir` appears in `_project_paths.session_marker`, `stop-dispatcher.py`, `integration-check.py` and
  `concept_changed_check.py`. Out of scope; pass 3 follow-up 2 covers them.
- `run_hook_process`, `four copies` and `four textual copies`: no hits.

**Wording since the merge:**

- README has "Changed in 0.16.3" and "Since 0.16.3 an unusable session folder blocks instead".
- The decision table has "(since 0.16.3, an unusable session folder blocks)".
- No "0.15.3" is left in shipped text. The only one is a test comment that explains the merge.
- The install skill's upgrade paragraph is master's in-place route. It gains the 0.15.2 entry (the tracker stamps the
  marker, the temp folders are ignored) and a "0.16.0 to 0.16.2" entry. Both match the code and `released_sha256`.

**README case counts:** README says `test_auto_improve_finish_install.py` holds 408 cases (`:1041`), and the file has 408
`def test_` methods. `test_pr_merged.py`: README says 761, the file has 761. The "grows to 394 cases" line (`:373`) sits in
the 0.15.2 block and is history.

**Registries:**

- MECHANISMS `:43, :45, :106, :107` were edited in place, with the 2026-11-06 correction.
- VOCABULARY `:123-125` were edited, with the two new terms and the correction.
- Master's #261 vocabulary is intact (Transcript turn state, Live plan, Shadow decision).
- Master's "Live plan … none applied" does not quite fit, because `resolve()` can create the parent (INFO-1).

## 6. Test edits forced by the merge

None of them weakens an assertion:

- **SH-K1** (`test_codegraph_shadow.py:363-366`): restated from "allow, `fail-open:state-unwritable`" to "exit 2,
  `session-state-unusable`, `turn_marker` null". The cursor checks next to it (planted cursor not read, link target
  untouched) are unchanged. This is the contract's own required outcome change.
- **SH-L1** (`:663-669`): before, nothing at all could be written under the home folder. Now the exception is the
  Per-user session parent subtree, which the sandbox puts in the fixture home. The shadow log itself is still caught
  anywhere under the sandbox root by the `tree_has_log` check two lines above. So the narrowing exempts only the live
  gate's own state.
- The other shadow rows moved `af.write_marker` / `af.session_folder` from the fixture TMP to `af.session_parent(home)`.
  The default `stamped=True` keeps them as own-marker rows.
- `test_codegraph_session_parent_docs.py`: the "before 0.15.3" upgrade assertion was replaced by three in-place
  assertions plus the kept `assertLacks`. This follows master's #266 route, and the old sentence is false now.
- `test_plugin_manifests.py` and `test_auto_improve_finish_install.py`: they only add pinned literals.

## 7. Stray files

- `git status --untracked-files=all` shows only this report.
- `__pycache__` is gitignored, and `git diff --cached --check` is clean.
- `git diff origin/master` shows `D .claude/orchestrator/results/2026-11-04-domain-split-registries/t11-review.yaml`.
  That is not a deletion in this branch. `origin/master` moved to `3757e30` (records only) after the merge head
  `bc398b5`. GitHub's merge-base diff will not show it, but merging `origin/master` again before the push keeps local
  diffs honest (INFO-3).

---

## Findings

### `.claude/hooks/tests/bench_codegraph_guard.py`

**[WARN]: the bench was never moved to the Per-user session parent. It cannot measure the merged guard, and it writes into
the real `%LOCALAPPDATA%`.** Lines 177-185 and 202-207.

```python
def env(self, project: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_")}
    env.update({..., "TMP": str(self.tmp), "TEMP": str(self.tmp), "TMPDIR": str(self.tmp),
                "USERPROFILE": str(self.home), "HOME": str(self.home)})
...
def folder(self, session: str) -> Path:
    return self.tmp / (SESSION_PREFIX + session)
```

**Problem:**

- The child environment inherits the real `LOCALAPPDATA` and `XDG_CACHE_HOME`, so the "new" hooks keep their session
  folders under the developer's real Per-user session parent. The bench's cleanup removes only its own temp folder, so
  those folders stay.
- `put_marker` and `drop_tickets` work in `TMP`, where the merged guard no longer looks.
- I ran it once with `--old-ref c8653e3` and a scratch `LOCALAPPDATA`. Four "new" cases came back NOT measured: marker
  present, marker present with no log, marker absent (block), and the cold cursor. Seven
  `auto-improve-codegraph-bench-new-*` folders appeared in the scratch parent.
- The default `--old-ref origin/master` now holds the shadow, so `_check_old_is_259` stops a plain run before it starts.
- This is the instrument the cut-over follow-up's Q2 criterion depends on.

**Fix:**

```python
def env(self, project: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE_")}
    env.update({..., "LOCALAPPDATA": str(self.home / "AppData" / "Local"),
                "XDG_CACHE_HOME": str(self.home / ".cache")})
    return env

def folder(self, session: str, design: str) -> Path:
    if design == "old":
        return self.tmp / (SESSION_PREFIX + session)
    base = self.home / "AppData" / "Local" if os.name == "nt" else self.home / ".cache"
    parent = base / "auto-improve-codegraph"   # os.mkdir(parent, 0o700) + os.chmod, never parents=True
    return parent / (SESSION_PREFIX + session)
```

Also:

- Create `<home>/AppData/Local` (and a 0700 `.cache` on POSIX) in `__init__`.
- Pass `design` through `put_marker`, `drop_tickets` and `drop_cursor`.
- Stamp the "new" marker (`writer`, `session`), so that the Foreign-marker notice does not add to its cost.
- Document that `--old-ref` must name a pre-shadow ref (for example `c8653e3`) now that master holds the shadow.
- Re-run with `--runs 30` and put the table in the PR (see INFO-2).

### `.claude/hooks/tests/test_codegraph_first_guard.py`

**[WARN]: no test row covers the path the merge order created: an unusable Session state with a non-source target or no
target.**

**Problem:**

- Under the contract's order, classification ran before the verdict, so a markdown read with a broken parent could not
  touch the verdict.
- In the merged order the verdict runs first. The silent allow now depends on two things: step 1 skipping the marker read
  (`turn_marker=None`), and step 2 still running after an unusable verdict.
- Nothing pins that. A later change that blocks early on `not plan.step0_ok`, the natural "fail fast" edit, would block
  every README, config and `.claude/` read whenever `LOCALAPPDATA` is broken, and no suite would fail.
- My probe shows the behaviour is right today.

**Fix:** add rows in the criterion-9 block. Each state should be checked on its own: `LOCALAPPDATA` relative, and the
Session folder a link. For each one:

- (a) `Read README.md` gives exit 0, empty stderr and no `block` record.
- (b) `Read {}` (no target) gives exit 0, empty stderr and no `block` record.
- (c) `Glob **/*.md` gives exit 0.
- (d) Control: `Read a.py` in the same fixture blocks `session-state-unusable`.

Also add one in-process row: `guard.decide("Read", {"file_path": ".../n.md"}, payload)` with the parent a link returns
`("allow", "non-source-target")`, and the link target is unchanged.

### `.claude/addons/codegraph/hooks/codegraph-first-guard.py`

**[INFO-1]: "pure" / "writes nothing" no longer matches what the Live plan does.** Lines 50 and 1091.

- Line 50 says the Live plan is "a pure function: it reads, it writes nothing".
- Line 1091 says "it writes nothing but the Session folder's lazy creation". `resolve()` creates the Per-user session
  parent (and on POSIX possibly the base), never the Session folder.
- Master's VOCABULARY "Live plan … none applied" has the same gap.
- G-2 allows step 0's lazy creation, so the behaviour is in contract. Only the words are off. Change both docstrings to
  "it writes nothing but the per-user session parent's lazy creation (step 0)".

**[INFO-2]: the cost of the hot path was not measured again after the merge.**

- Every guard call on Windows now pays the first `ctypes` import (about 7.9 ms) plus about 0.8 ms of verdict. That
  includes the marker-present and allowlisted calls that G-1 made cheaper.
- #261's t3 run measured G-1's saving at -0.7 to -7.9 ms p50, so on Windows the merge most likely uses it up.
- The tracker and the reset hook pay the same cost, which raises the "old per-turn cost" that the cut-over's Q2
  criterion is measured against.
- No shipped text makes a number claim, so this is not a defect. Re-measure after the bench fix and put the table in the
  PR.

**[INFO-6]: `session_parent_base` docstring.** Line 365 says "Exactly one of the two is None", but the `check-failed`
branch (line 402) returns a 3-tuple `(None, "check-failed", text)`. The caller handles it (line 469). Only the docstring
is wrong, and it is wrong in all three copies (parity keeps them identical).

### `.claude/concepts/followups/2026-11-05-codegraph-hooks-cutover.followup.md` (master's stub)

**[INFO-4]: the cut-over stub carries none of #271's invariants.**

- It plans to move the reset hook's pruning into the guard and to decide from the transcript instead of the marker.
- It does not say that the one-hook design must keep:
  - I-6, fail closed through the Stateless session and `session-state-unusable`;
  - I-9, pruning only the Per-user session parent and only on a usable verdict;
  - the Transcript cursor under the Per-user session parent.
- It also does not record that a `shadow-more-open` record can now come from an unusable state: the live guard blocks
  and the transcript says open.
- Add these to the stub's pre-derived context, so the cut-over contract cannot quietly bring back `state-unwritable`.

### `skills/auto-improve-codegraph-install/SKILL.md`

**[INFO-5]: the "0.16.0 to 0.16.2" entry (line 174) leaves out that those releases kept their session folders in the
system temp folder.** The 0.15.2 entry says it, and the README row covers both. Add one clause.

### Workstation note (not a code defect)

**[INFO-7]:** `%LOCALAPPDATA%\auto-improve-codegraph\auto-improve-codegraph-abc\` (`availability.json`,
`logged-no-index`) was created on 2026-11-06 at 17:35 in the real Per-user session parent. No test in the repository uses
session id `abc`, so it is probably a manual probe from an earlier pass. Delete it by hand. The leak checks would have
caught a test.

**[INFO-3]:** see section 7 (master moved after the merge head).

---

## Suites

Run on the merged working tree. The hook suites ran one at a time, in the foreground.

| Suite | Result |
|---|---|
| `test_codegraph_first_guard.py` | 1377 passed, 0 failed, 3 skipped (both real-parent isolation rows pass) |
| `test_codegraph_shadow.py` | 118 passed, 0 failed, 0 skipped |
| `test_addons.py` | 33 tests OK |
| `test_worktree_path_guards.py` | 190 passed, 0 failed (real-parent leak check passes) |
| `test_plugin_manifests.py` | 192 passed, 0 failed |
| `test_codegraph_session_parent_docs`, `test_plugin_text_scans`, `test_installed_plugin_root` | 65 tests OK |
| `test_codegraph_shadow_report` | 31 tests OK |
| `test_auto_improve_finish_install` (`-k odegraph -k Hop -k ool_named -k orktreeOwnRoot`) | 73 tests OK |
| `unittest discover -s .claude/scripts/tests` (background, 76 min) | Ran 2656: 3 failures, 4 errors, 4 skipped. None of them comes from this PR, but I did not run master's discover to compare. (1) `test_plugin_manifests` fails to import because `test_land_contract_identity`'s git guard, loaded earlier in the same process, refuses its import-time `git rev-parse HEAD`. That call (`read_merge_base_state(ROOT)`) is already on master at `bc398b5:1354`, and the file passes alone (192/192). (2) `test_script_path_resolution`, `test_ship_skill_sync` and `test_sql_patterns_skill_sync` are script-style modules that call `sys.exit(0)` when imported. (3) `test_land_contract` (finds `gh-pr-merge` in `skills/ship/SKILL.md`) and two `test_land_contract_verification` real-config rows fail. This PR touches neither those test files, `skills/ship` nor `.claude/work-item-conventions.json`. They belong in a separate issue, not in this merge. |
| `check_version_bump.py` | reads the committed HEAD (0.15.3) before the merge commit. Run it again after committing. |

---

## Registries (janitor)

- **JOURNAL.md:** I appended one entry, "2026-11-07 — A contract that reorders a hook's decision steps must be re-read
  against every contract that reorders the same steps before either merges" (post-impl divergence: the bent order, the
  stale bench and docs). It is a shipped registry, and this PR already raises the version to 0.16.3, so it needs no
  separate raise.
- **MECHANISMS.md / VOCABULARY.md:** the merge adds no new mechanism or term. The 2026-11-06 entries read true of the
  merged code, apart from INFO-1's "none applied" wording.
- **INTEGRATION.md:** not applicable (no REST, SignalR or DTO surface).
- **Contract:** left untouched (Status and checklist belong to `/pr-merged`). A divergence note for the step order should
  be added by the implementer (section 1).

## Follow-ups

1. Fix the bench (the WARN), re-run it (`--runs 30`, a pre-shadow `--old-ref`, a scratch `LOCALAPPDATA`) and table the
   merged hot-path cost (INFO-2).
2. Write the step-order divergence into the #271 contract (an addendum: the verdict runs before the marker and the
   targets; the parent is created on any first call; the measured cost).
3. Update the cut-over stub #262 with #271's invariants (INFO-4).
4. Passes 1-3 follow-ups still open: Windows stdin decoding, other per-session state in the shared temp folder,
   letterless-volume profiles, POSIX base race, leak checks under concurrent hook runs.
5. Consider caching nothing and importing `ctypes` lazily only when a drive letter is present. It always is for
   `LOCALAPPDATA`, so the real saving would need a drive-type check with no `ctypes` (for example `os.stat` on the drive
   root with `st_file_attributes`). That is a design change for the cut-over contract to weigh, not this PR.

---

### Summary

| Severity | Count |
|---|---|
| [CRITICAL] | 0 |
| [WARN] | 2 |
| [INFO] | 7 |

**Verdict**: `FIX THEN SHIP`

**Top priority fix**: move `bench_codegraph_guard.py` to the Per-user session parent (environment, `folder()`, a stamped
marker), so that it no longer writes into the real `%LOCALAPPDATA%` and can measure the merged guard. Then add the
unusable-state non-source rows.
