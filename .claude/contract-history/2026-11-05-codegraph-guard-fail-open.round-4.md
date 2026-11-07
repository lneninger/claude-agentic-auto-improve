# Superseded critique round 4 — 2026-11-05-codegraph-guard-fail-open

Moved out of `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` on 2026-11-05 by the main session, per the budget rule in `.claude/templates/concept-contract.md`. The data-architect amended the contract body in response (revision 5).

## Critique (round 4)

**Critic:** contract-critic
**Date:** 2026-11-05
**Verdict:** warnings-only

I checked each Revision 4 answer against the repository. The round-3 BLOCKER is resolved. "Project index" now means `.codegraph/codegraph.db` everywhere it is used: the Value Object, the ownership rule, the Extension Points note, the TASK constraint, the fixture bullet, FM 3, I-1 and Q7. `~/.codegraph` has no `codegraph.db`, so with fixtures under `%LOCALAPPDATA%\Temp` the decoy and no-index rows can pass. The suites pin `CLAUDE_PROJECT_DIR` to a fixture (`test_worktree_path_guards.py:378`, `test_addons.py:55`, `test_codegraph_first_guard.py:75`), and the main checkout has no `.codegraph`, so that second search root adds no real index either. The round-3 task-G WARN is resolved: `base_env` (`:376-381`) stays as it is, and `snapshot_real_home_logs` reads the test process's own `expanduser("~")` (`:589`). The round-3 pruner WARN is resolved in substance: the link test matches `cleanup_delivered.py:139-143`, and `codegraph-turn-reset.py:43` has a `__main__` guard, so the `importlib` seam is feasible.

### Findings

- **[WARN] For a linked worktree, the "root" of the Caller tree comes from functions that return the MAIN checkout's root, so rule (2) contradicts itself as written**
  - **What is wrong:** For a linked worktree, `_classify` returns `("linked-worktree", dirname(common))`, which is the main checkout (`_project_paths.py:579, 612-615`). `tree_kind` returns only the kind. No helper function returns a linked worktree's own root. (`enclosing_worktree_root`, `:518`, is based on segments and covers only `.claude/worktrees/<name>`, so it misses the "outside the main folder" layout.) Rule (2) says "its root holds no Project index, and the main checkout root does". With "root" taken from the cited functions, both refer to the same folder, so `index-other-tree` can never fire. Getting the worktree's own root needs a locator the contract does not name. The claim "consumed as-is" in Reused Mechanisms is therefore not true. The installer gets its root from `--project`, but the guard gets a `cwd` that may be a subfolder. The ownership parity test can only hold if both sides find "its root" the same way.
  - **Prior artifact ignored:** `MECHANISMS.md:43` (Two-layer Claude path resolution, tree classification: what it returns); `JOURNAL.md` 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case".
  - **Where in this contract:** `## Data Shapes → Value Objects`, Caller tree: "`root` and `kind`, from `_project_paths.tree_kind` / `main_checkout_root`". Index ownership (2): "its root holds no Project index, and the main checkout root does".
- **[WARN] The guard's own test file is not isolated from the developer's home and temp folder, although FM 1 names that as a cause of lost blocks**
  - **What is wrong:** `codegraph_env()` covers `test_worktree_path_guards.py`, and `clean_env` already redirects `HOME`/`USERPROFILE` in `test_addons.py:53-59`. But `run_hook_process` in `test_codegraph_first_guard.py:72-79`, which runs K-4, copies `os.environ` with the real `HOME`, `USERPROFILE`, `CLAUDE_CONFIG_DIR` and `TMP`. `_mcp_server_state` reads the global `mcpServers` in `~/.claude.json` and `disabledMcpjsonServers` in the user's `settings.json` (`auto_improve_finish_install.py:2085, 2095, 2097-2100`). So a developer with a global codegraph server would see the `server-not-configured` rows fail. One who disables codegraph in their user settings would see the K-4 control allow. Session folders and tickets would also land in the real temp folder. This workstation is not affected: `~/.claude.json` has no `codegraph` key. The TASK block's "New tests" list does not say which file holds them (criterion 13 allows `test_codegraph_first_guard.py` or a new file), so it cannot be checked whether the new rows are isolated.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-05 "A documented 'missing file means the default' must read one named location only"; `JOURNAL.md` 2026-10-17 "Loosening a guard rule must be checked against the guard's own test fixtures".
  - **Where in this contract:** `## Failure Modes` FM 1: "The CODEGRAPH rows point `HOME`, `USERPROFILE` and `CLAUDE_CONFIG_DIR` at a fixture home folder". TASK block, `test_codegraph_first_guard.py run_k4: the same fixture markers and a distinct session_id per CLAUDE_SKIP_CG run`.
- **[NIT] The inline `gitdir:` candidate leaves two things unstated.** It does not say that a relative `gitdir:` is resolved against the folder holding the `.git` file. The fixture's own `repo/.git` is relative (`test_worktree_path_guards.py:331`), and `_git_file_kind` joins it to that folder (`_project_paths.py:568`). It also does not say how Guard fallback mode finds "the tree's `.git`" (an upward walk?). `## Data Shapes → Value Objects`, Main checkout candidate (b).
- **[NIT] Where `os.symlink` is refused, no test exercises the per-file re-check's clauses "the folder must still not be a link" and "real path's parent equals the folder's".** The junction case replaces the folder at the folder-test stage, not through `before_remove`. A folder-to-junction swap made through the seam would need no privilege (`test_working_agreements.py:1562-1571`). `mklink /J` has no stated POSIX counterpart. The file holding the pruner tests is not named, and the custom runners have only PASS and FAIL buckets (`test_codegraph_first_guard.py:52-59`), so "count it as skipped" has no bucket to go in. `MECHANISMS.md:76`. `## Failure Modes`, pruner FM.
- **[NIT] The codegraph rows' replacement for task G names no assertion.** The FM text says "that check is the project's own `.claude/logs` in the fixture", but no test is named. No row checks that the real temp folder gained no `auto-improve-codegraph-<this run's session id>` folder, the new place a forgotten `codegraph_env()` would leak to. `JOURNAL.md` 2026-11-02 "Name the tests a fix may change by the state they guard". `## Failure Modes`, task-G FM.
- **[NIT] Two sentences have gone stale.** `## Revision history` says "Critique rounds 1-2 are kept inline until the main session moves them", but they have been moved (`## Critique (rounds 1 and 2, moved)`). The same section also says "addressed in the body below", but the body is above it. `JOURNAL.md` 2026-11-02 "Edit a reversed sentence where it stands".
- **[NIT] The contract is over its budget.** At four characters per token I estimate about 58,000 characters (about 14,600 tokens) before round 3, and about 16,500 tokens with round 3. This is an estimate, not a measurement, against `**Budget:** 12,000 tokens`. Round 3 is superseded by this round and is still inline (`.claude/templates/concept-contract.md:22`).
- **[NIT] Criterion 9's "a test fails" is enforced locally only.** No CI workflow runs `test_plugin_manifests.py` or `test_plugin_text_scans.py`: `.github/workflows/version-bump.yml` runs only `test_check_version_bump.py` and `test_repo_consistency.py`. `JOURNAL.md` 2026-11-02 "A 'fails the build' claim must name the workflow that runs the check".
- **[NIT] Uncertain Assumptions leaves out workstation evidence on the permission form.** This workstation's own `~/.claude/settings.json:20` allows the server form `mcp__codegraph`. The brief (criterion 7) requires the wildcard, so this only bears on how much weight the fallback gets.

### Applicable journal entries

- **2026-10-04 — Detect an install mode by what the sync actually delivers / A root locator can return the consumer itself under vendoring**: heeded by the `codegraph.db` definition and the decoy tests.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case**: partly heeded. The fixture bullet is true, but see the Caller-tree WARN.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control**: heeded by the scan's planted-file controls (the contract does not cite it).
- **2026-10-05 — "missing file means the default" must read one named location only**: heeded for `test_worktree_path_guards.py` and `test_addons.py`; not for `test_codegraph_first_guard.py` (WARN).
- **2026-10-15 — A fallback that finds by prefix match must prove ownership** / **2026-10-16 — An unset ownership field is not proof of ownership**: heeded by the pruner's owner check, the known-files-only rule and the re-check (the contract does not cite these entries).
- **2026-10-17 — Git for Windows lists files beneath an untracked junction**: heeded. The link test matches Delivery cleanup.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures**: heeded for two of the three guard suites (WARN).
- **2026-11-02 — Name the tests a fix may change by the state they guard**: heeded for task G on the other three guards; for the codegraph rows, see the NIT above.
- **2026-11-02 — Edit a reversed sentence where it stands**: violated in the Revision history (NIT).
- **2026-11-02 — A "fails the build" claim must name the workflow**: not addressed (NIT).
- **2026-10-22 — An accepted critic WARN must amend the contract body**: heeded. The Index search set, FM 3, Confidence and the TASK block all carry the round-3 answers.
- The other entries listed in `## Lessons referenced` are heeded as stated.

### What the critic did not check

- **Checked and found true:**
  - Q1 to Q8 each carry a recommendation (Q4 and Q5 give a recommendation without alternatives). No Non-Goal hides a decision: the permission entry's removal is decided by Q4, and the performance redesign is anchored to #261.
  - The hidden-tell grep finds nothing in the body.
  - Acceptance criteria 1 to 13 each map to a step, an invariant, a scan or a named test. The Edit half of criterion 2 holds (`addon.json:15`). Criterion 5 now holds wherever absence can be proven.
  - The contract has one mergeable block with a `**Work Item Brief:**` header. The five `0.15.1` entries are in the four `check_version_bump.MANIFESTS` files (`:25-26`), all of which are in Files to touch.
  - The MECHANISMS.md line citations (43, 58, 72, 76, 78, 92-96) resolve.
- **Not run (no shell):** `pr_merged.py --status`, `derive_area.py`, `cross_area_scan.py`, any test, and an exact character count. `area-mapping.json` has `"areas": {}`, so the Adjacent Areas line is consistent.
- **Not checked:** whether master is still at `0.15.1`.
- **Missing input:** `.claude/registries/INTEGRATION.md` does not exist in this worktree, and `.claude/registries/` holds only the three root files. Checklist item 7 was judged from the contract: there is no REST, SignalR or DTO surface.
- **Tools:** no CodeGraph tool was available. Symbols were checked with Grep and Read.

---
