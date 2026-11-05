# Superseded critique round 3 — 2026-11-05-codegraph-guard-fail-open

Moved out of `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` on 2026-11-05 by the main session, per the budget rule in `.claude/templates/concept-contract.md`. The data-architect amended the contract body in response (revision 4).

## Critique (round 3)

**Critic:** contract-critic
**Date:** 2026-11-05
**Verdict:** blockers-found

Each Revision 3 answer was checked against the repository and the workstation. The round-2 fixture WARN, home-settings WARN and live-trial WARN are resolved as written. The criterion-5 BLOCKER is not: the new rule fails for a different reason.

### Findings

- **[BLOCKER] The Index search set counts CodeGraph's own per-user data folder `~/.codegraph` as an index, so `no-index` never fires for any project under the home folder, and the contract's new `no-index` tests fail on this workstation**
  - **What is wrong:** `C:\Users\lneni\.codegraph\` exists and holds only `models/`, `daemons/`, `telemetry.json` and `update-check.json`. It is the CodeGraph CLI's global data folder, not a project index. A real index (`D:\Dev\HIPALANET\StockToolScalpingMachine\.codegraph\`) holds `codegraph.db` and `config.json`. The rule counts any real `<folder>/.codegraph` folder on the walk "up to the filesystem root", so for every project under the home folder `no-index` is false. That is every machine that has CodeGraph installed, which is the population that installs this add-on. Rule (3) then gives `index-present` and the gate stays, with no index anywhere. The same applies to tests. `make_tree` (`test_worktree_path_guards.py:324`) and the new non-git, undecidable and fallback `no-index` tests build their fixtures with `tempfile.mkdtemp`. The default Windows temp folder, `%LOCALAPPDATA%\Temp`, is under the home folder. The TASK block's fixture temp folder is inside that root, and its `HOME`/`USERPROFILE` redirect does not move the physical ancestors. So the `allow` rows fail here. The planted `repo/.codegraph/` is also not shown to be what keeps C1, C2, C7, C9 and task 3 blocking, because `~/.codegraph` already does that. The installer note built on the same rule says nothing in this case, so acceptance criterion 11 is silent too.
  - **Prior artifact ignored:** `.claude/work-items/2026-11-05-259-codegraph-guard-fail-open.md:36` ("A project with no `.codegraph/` index is allowed"); `JOURNAL.md` 2026-10-04 "Detect an install mode by what the sync actually delivers" (detection by the presence of a name that another producer also creates); `JOURNAL.md` 2026-10-04 "A root locator can return the consumer itself under vendoring"; round-2 BLOCKER of this contract (same criterion).
  - **Where in this contract:** `## Data Shapes → Value Objects`, Index search set: "every folder from the payload `cwd` up to the filesystem root … An entry counts only if `<folder>/.codegraph` is a real folder (not a link)." `## Failure Modes` FM 3: "the Index search set walks every ancestor, so a parent index keeps the gate." `## Confidence` lists "the index rule" as High.
- **[WARN] Redirecting `HOME`/`USERPROFILE` in `base_env` makes the suite's real-home leak check vacuous for all four guards**
  - **What is wrong:** `base_env` (`test_worktree_path_guards.py:376-381`) keeps the real home on purpose. Only `fallback_env` (`:384-388`) redirects it. `main()` brackets the whole run with `snapshot_real_home_logs` / `assert_real_home_untouched` (`:2137, 2170`, round 3 task G). That check proves no guard writes this run's data into the operator's real `~/.claude/logs`. The TASK block says "base_env sets the isolation variables above", which covers every row of concept-gate, bash-gate, db-destructive-guard and codegraph. No hook in the suite would then ever see the real home, so task G can no longer fail. The TASK block names no replacement for the guarded state.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 "Name the tests a fix may change by the state they guard, after reading them"; `JOURNAL.md` 2026-10-17 "Loosening a guard rule must be checked against the guard's own test fixtures".
  - **Where in this contract:** `## Implementation Handoff` TASK block: "base_env sets the isolation variables above; run_hook adds a fresh session_id"; `## Failure Modes` FM 1: "Every rewritten suite points `HOME`, `USERPROFILE` and `CLAUDE_CONFIG_DIR` at a fixture home folder".
- **[WARN] The pruner's link test names `is_junction`, which the cited mechanism forbids, and its file-swap test needs a file symlink that Windows refuses without privilege**
  - **What is wrong:** `Path.is_junction` / `os.path.isjunction` exist only from Python 3.12. Delivery cleanup, which I-5 says it follows, detects links on every supported Python through `lstat` and `FILE_ATTRIBUTE_REPARSE_POINT`, and its suite asserts the absence of `isjunction` (`test_cleanup_delivered.py:1338`, `:2820-2839`; contract `2026-10-15-auto-cleanup-delivered-worktrees.md:113`). The swap test, "a file swapped for a link after the folder test", needs `os.symlink` on a file. The repository's own helper shows that this fails on Windows without Developer Mode or admin, and that only folders fall back to `mklink /J` (`test_working_agreements.py:1562-1571`). The contract states no skip rule and no fallback, such as a junction swapped in for the folder. It also names no seam for injecting the swap into an inline hook between the folder test and `os.remove`.
  - **Prior artifact ignored:** `MECHANISMS.md:76` Delivery cleanup; `JOURNAL.md` 2026-10-17 "Git for Windows lists files beneath an untracked junction; a parent-link check is load-bearing".
  - **Where in this contract:** `## Data Shapes → I-5`: "it is a link or junction (`lstat` / `is_junction`)"; the TASK block's new-tests line: "a file swapped for a link after the folder test".
- **[NIT] "The main checkout stays on the list under Guard fallback mode" is true only for the `.claude/worktrees/<name>` layout.** `_FALLBACK_WORKTREE_MARKER_RE` (`codegraph-first-guard.py:64-66`) matches only `/.claude/worktrees/<name>`. A worktree outside the main folder, which is the second layout the contract's own control covers, gets no candidate under fallback mode. There the server reads as `not-configured`, and `no-index` fires while the main checkout holds an index. Under Q7 (b) or (c) that is a silent fail-open. `MECHANISMS.md:58`. `## Data Shapes → Value Objects`, Server project paths row.
- **[NIT] A user decision still sits outside `## Open Questions for User`.** It is the handoff's "The user is asked to confirm this choice at approval" (review inside `/flow` rather than a second block). It was raised in round 1 and is still not a Q.
- **[NIT] An unanchored deferral sits in Non-Goals.** The Non-Goal "Performance redesign, a once-per-session gate, or a nudge-before-block policy … a separate follow-up issue that the main session opens" names no follow-up handle and no issue.
- **[NIT] The contract is about 2.5 times its 12,000-token budget.** Two critique rounds are kept inline against `.claude/templates/concept-contract.md:22`.

### Applicable journal entries

- **2026-10-04 — Detect an install mode by what the sync actually delivers**: violated by the index-presence test; see the BLOCKER.
- **2026-10-04 — A root locator can return the consumer itself under vendoring**: violated in kind, because the ancestor walk is satisfied by an unrelated `.codegraph`. See the BLOCKER.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case**: heeded. The corrected fixture bullet is true: `make_tree` `:331, 340, 354` and `_git_file_kind` `_project_paths.py:568-579` give `undecidable`, and `commondir` `../..` gives `linked-worktree` with root `<main>`.
- **2026-10-05 — A documented "missing file means the default" must read one named location only**: heeded. `_mcp_server_state` reads only `os.path.expanduser("~")` (USERPROFILE on Windows) and `_claude_home` (argument, then `CLAUDE_CONFIG_DIR`, then `~/.claude`; `auto_improve_finish_install.py:311-318, 2084-2106`). `HOME`/`USERPROFILE`/`CLAUDE_CONFIG_DIR` isolation therefore covers every layer it reads.
- **2026-10-15 — A script that reads a project-owned file must be told which project**: heeded by Server project paths, with the fallback-layout gap above (NIT).
- **2026-10-17 — Git for Windows lists files beneath an untracked junction**: partly heeded. The per-file re-check was added, but the link test does not match the mechanism; see WARN.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures**: heeded for the codegraph rows, but violated for task G; see WARN.
- **2026-11-02 — Name the tests a fix may change by the state they guard**: violated for task G; see WARN.
- **2026-11-02 — A rule titled 'every' must list every line it covers**, **2026-10-28 — Guard messages must use names the guard emits**, **2026-10-22 — Describe a broken install by the rows each install age really has**, **2026-10-30 — A rule that refuses must give already-delivered work a named way out**: heeded, unchanged since round 2.

### What the critic did not check

- Checked and found true:
  - Q1 to Q7 each carry a recommendation.
  - Acceptance criteria 1-4 and 6-13 each map to a decision step, invariant, scan or named test. Criterion 5, and the note half of criterion 11, are broken by the BLOCKER.
  - The single block holds all five `0.15.1` version entries in the four `check_version_bump.MANIFESTS` files. It has a `**Work Item Brief:**` header and no parent branch.
  - The hidden-tell grep (`maybe`/`likely`/`probably`/`TBD`/`we could`/`not sure`/`assuming`) finds nothing.
- Not run (no shell): `pr_merged.py --status`, `derive_area.py`, `cross_area_scan.py`, and any test.
- No CodeGraph tool was available; symbols were checked with Grep and Read.
- Not established: the temp folder setting of the session that will run the tests. The BLOCKER assumes the Windows default `%LOCALAPPDATA%\Temp`, which exists on this workstation.

---
