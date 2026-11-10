# Concept Contract — INV-O1 version row is parent-aware (issue #240, item 2)

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-10
**Requested by:** user
**Status:** approved
**Work Item Brief:** .claude/work-items/2026-11-10-240-inv-o1-parent-aware.md
**Tracking issue:** #240
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. The lifecycle, budget rule and handoff rules are in `.claude/templates/concept-contract.md`.

---

## Business Concept

- **What is this thing, in domain language?**
  The manifest suite's INV-O1 version row (`test_plugin_manifests.py`) judges every tree by one rule: a tree that differs from its merge base with `origin/master` must carry a higher version in all five declarations. The **Parent Branch Delivery Rule** says the opposite for a sub-task head (`task/<slug>/<id>`) into a parent branch: it must KEEP the version, because the landing raises it once. So every parent-branch sub-task that changes anything is red on this row by construction. This contract makes the row read the checked branch and, for a sub-task head, judge it by the parent-mode rule that `check_version_bump.py` already owns, taken through one shared reader instead of a second copy. When the branch cannot be read, the row fails and names the cause; it never skips.

- **Existing VOCABULARY.md terms that apply:**
  - **Parent Branch Delivery Rule** (`.claude/registries/VOCABULARY.md`, line 74) — the rule this row is brought into line with.
  - **Layout defect** `sub-task-raises-version` (`VOCABULARY.md`, line 75) — the same rule seen from the dispatch side; this contract does not touch it.

- **New terms proposed for VOCABULARY.md:** none. "Parent mode" is already named in the `Plugin version check modes` mechanism entry, and this contract reuses that name.

---

## End-User View

Not applicable. Reason: no Angular or other UI surface is in `Files to touch`. The change is a repository self-test and a script the plugin ships for version checking. No operator screen exists.

---

## Data Shapes

### Entities

Not applicable. Reason: nothing persists. Every shape below is read from git and the environment for one suite run, then thrown away.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Checked branch reading | `ref` (string, empty on failure), `source` (enum: `environment`, `git`), `cause` (string, empty on success) | Input to the row's mode choice. `GITHUB_HEAD_REF`, when set and non-empty after trimming, wins with source `environment`. Otherwise the current branch name comes from git (`symbolic-ref --short HEAD`) with source `git`. Every failure gives an empty `ref` and its own cause text, one per outcome (never one shared sentence): (a) detached HEAD: `symbolic-ref` exits 128 AND `git rev-parse --verify HEAD` succeeds, cause "HEAD is detached and GITHUB_HEAD_REF is unset or empty"; (b) not a repository or HEAD unreadable: `rev-parse --verify HEAD` also fails, cause "git cannot read HEAD in <root>: <git's own message>"; (c) git missing or timed out (`OSError`, `SubprocessError`), cause "git could not run: <exception type and message>". The set-but-empty or whitespace-only `GITHUB_HEAD_REF` is treated as unset. |
| Checked base | `ref` (string, or absent) | `origin/<GITHUB_BASE_REF>` when that variable is set and non-empty. Otherwise absent: a local run cannot know the parent branch. |
| Parent allowed versions | list of version strings | The output of the shared reader in `check_version_bump.py`: the versions at the base ref (when given) followed by the versions at `merge-base(origin/<default>, HEAD)`. A failed git call is raised, never returned as an empty list. |
| INV-O1 verdict | `ok` (bool), `rule` (enum: `parent`, `merge-base`, `unreadable`), `label` (string), `detail` (string) | What the row prints and passes to `check`. `rule` is `unreadable` exactly when a reading failed. In that case `ok` is false and `detail` carries the cause. |

**Invariants:**

- **I-1 Mode selection is one rule, owned by `check_version_bump.py`.** Parent mode applies when the head ref matches `TASK_HEAD` and the base is not `origin/<default>`. An absent base counts as "not the default", because by convention a `task/` head targets its parent branch. `main()` and the INV-O1 row both call the same predicate. Neither spells `TASK_HEAD` or the base comparison itself.
- **I-2 The parent rule is `evaluate_parent`, unchanged.** The row calls `cvb.evaluate_parent(head_versions, allowed)` and treats exit code 0 as a pass. The row's head versions are the working-tree `declared_versions` (all five), the same input the default rule already uses. It does not use `HEAD:` blobs, so uncommitted edits are judged the same way under both rules.
- **I-3 The default rule is unchanged** for every head that is not in parent mode. That covers a non-`task/` head and a `task/` head whose base is known to be `origin/master`. `version_matches_tree` and `read_merge_base_state` keep their current behaviour, and their five existing controls stay green.
- **I-4 Never a skip.** An unreadable branch, a failed merge-base or `git show`, or an unparseable manifest each produce `ok = false` with the cause named. A raised `CalledProcessError`, `OSError`, `ValueError` or `KeyError` from the shared reader becomes that verdict. It is never a pass and never a missing row.
- **I-5 Fixtures are isolated from the caller's environment.** Every fixture row passes an explicit environment mapping (empty, or one built for that row). The real `os.environ` is never passed, so a CI job that sets `GITHUB_HEAD_REF` cannot change a fixture's outcome.
- **I-6 `check_version_bump.py` keeps its exit contract** (0 / 1 / 2, where 2 means "could not run" and is never an allow), its CLI flags and its stdlib-only imports. The script is one of the seven vendored files of the Hook registration check (MECHANISMS.md line 112, corrected to seven at line 113), so it must not gain an import outside its own folder.
- **I-7 The default ref is named, not hidden.** `inv_o1_verdict` passes `origin/master` as `default_ref` (the same literal the existing reader uses at `test_plugin_manifests.py:1484`, kept as one module constant `DEFAULT_REF` in the test) to both shared functions, and `master` as the bare default branch name where the shared predicate needs it.

### Events

Not applicable. Reason: a synchronous test and a CLI script; nothing is emitted or listened to.

### Commands (if any)

Not applicable. Reason: no new command-line flag or skill command. The CLI of `check_version_bump.py` is unchanged.

---

## Reused Mechanisms

- **Plugin version check modes** (`MECHANISMS.md` line 94, `check_version_bump.py`). **Extended by** two module-level functions that are lifted out of `main()`'s inline parent branch (lines 166–172), with no behaviour change:
  - `is_parent_mode(head_ref, base_ref, default_ref) -> bool`. This is exactly today's condition `TASK_HEAD.match(head_ref) and base_ref != default_ref`, where an absent base is not the default.
  - `parent_allowed_versions(base_ref, default_ref, cwd=None) -> List[str]`. This is the existing loop over `(base, merge_base)`, with the base step skipped when `base_ref` is absent. The private `_git` gains an optional `cwd` keyword so the reader can run in a fixture repository. Every existing caller keeps calling it unchanged.
  `main()` then calls both functions. `evaluate_parent` is **consumed as-is**. The extension seam the entry names ("a new pull request kind is one mode branch in `main`") stays valid.
- **The INV-O1 merge-base reader** (`read_merge_base_state` and `version_matches_tree` in `test_plugin_manifests.py`) is **consumed as-is** for the default rule, for the default rule. Its throwaway-repo builder `_make_repo` is NOT consumed as-is for the parent path: it writes only `.claude-plugin/plugin.json`, while the shared reader runs `git show <ref>:<m>` for every entry of `cvb.MANIFESTS`. So the parent fixtures use a new builder `_make_parent_repo` (see Extension Points); `_make_repo` and its existing rows stay untouched.
- **The suite's `check()` and `sys.path` seam** (line 484 already puts `.claude/scripts` on the path) is **consumed as-is**, so `import check_version_bump as cvb` needs no new path code.

---

## New Mechanisms (if any)

None. The parent rule, its mode predicate and its reader all stay in `check_version_bump.py`. The test only reads the checked branch, which `check_version_bump.py` receives as `--head-ref` and never reads itself.

---

## Extension Points

- `check_version_bump.py`: add `is_parent_mode` and `parent_allowed_versions` beside `evaluate_parent`, give `_git` an optional `cwd`, and make `main()`'s parent branch call them. The usage docstring stays accurate.
- `test_plugin_manifests.py`, in the INV-O1 version block (lines 1466–1573):
  - Add `read_checked_branch(root, environ)`, which returns the Checked branch reading.
  - Add `inv_o1_verdict(root, environ, declared)`, which returns the INV-O1 verdict. It reads the branch. If the branch is unreadable, the verdict fails with `rule = unreadable`. In parent mode, it calls `cvb.parent_allowed_versions` and `cvb.evaluate_parent`. Otherwise, it runs today's `read_merge_base_state` and `version_matches_tree` path.
  - The live row calls `inv_o1_verdict(ROOT, os.environ, declared_versions)`.
  - Update the INV-O1 line in the module docstring (lines 52–55) and the section `print` label (line 1466) to say "parent-aware".
- New fixture builder `_make_parent_repo(name, version, with_origin_master)` in the same temporary folder: it writes a manifest for EVERY entry of `cvb.MANIFESTS` (all carrying `version`; the marketplace file with both its entries), commits, and optionally creates `origin/master`. A fixture's `declared` argument is the list of version strings read back from that fixture's working-tree copies of `cvb.MANIFESTS` through `cvb.versions_in`, so a fixture edit of the version is seen exactly as the live row sees the real tree.
- New fixture rows, all in throwaway repositories under the existing `mb-controls-` temporary folder:
  - **F-1 (acceptance):** branch `task/demo/t1` with a changed file and the declared version `1.2.3` equal to the merge base's, with an empty environment. The verdict passes with `rule = parent`.
  - **F-2 (acceptance):** branch `fix/demo` (a head into the default branch) with a changed file and the version kept at `1.2.3`, with an empty environment. The verdict fails with `rule = merge-base`.
  - **F-3:** the same `task/` head declaring `1.2.4`, a raise. The verdict fails with `rule = parent`, because a sub-task never raises.
  - **F-4:** a detached HEAD (`checkout -q --detach`) with an empty environment. The verdict fails with `rule = unreadable`, and the cause is the detached-HEAD text of outcome (a). A second sub-row points the check at a folder that is not a repository: it fails with the outcome (b) text, not the detached-HEAD text.
  - **F-5:** a detached HEAD with `{GITHUB_HEAD_REF: task/demo/t1, GITHUB_BASE_REF: parent}`, where `refs/remotes/origin/parent` points at a commit that declares `1.2.3`. The verdict passes with `rule = parent`. This proves that a branch name and base supplied through the environment, on a detached checkout, are read and that the reader's base-ref step runs. It does not prove a CI path: no configured workflow runs this suite today.
  - **F-7:** `GITHUB_HEAD_REF` and `GITHUB_BASE_REF` set to `""` and to whitespace. Both are treated as unset: on a `fix/demo` branch the verdict is `rule = merge-base`, and on a detached HEAD it is `rule = unreadable`.
  - **F-6:** `{GITHUB_HEAD_REF: task/demo/t1, GITHUB_BASE_REF: master}`, a task head into the default branch, with a changed file and the version kept. The verdict fails with `rule = merge-base`, which proves I-1's base comparison.
- `test_check_version_bump.py`: add one unit row each for `is_parent_mode`, with three cases (task head and non-default base, task head and default base, task head and absent base), and for `parent_allowed_versions(None, ...)`, which reads the merge-base step only. The existing parent-mode CLI rows (lines 263–320) are the regression proof for I-6.
- Version: a **patch** raise in all five declarations, one patch above `origin/master`'s version when the pull request opens. That is 0.18.1 → 0.18.2 today (see Q2).

---

## Integration Surfaces

Not applicable. Reason: the change stays inside the plugin's Python tooling layer. There is no API, event, DTO or frontend boundary. The one cross-file seam, the test importing `check_version_bump`, is in-process and within one layer.

---

## Adjacent Areas

The cross-area scan (`py -3 .claude/scripts/cross_area_scan.py`) was run by the main session on 2026-11-10 and reported no adjacent area above threshold (the CodeGraph signal was skipped because its `impact` subcommand failed). Areas found by reading:

| Area | Decision | Implication / Reason | Handle |
|------|----------|----------------------|--------|
| version-bump CI workflow (`.github/workflows/version-bump.yml`) | not applicable | Its run line and flags are unchanged (I-6). JOURNAL 2026-10-30 "Widening a CI trigger changes who the check judges" applies only to `on:` or filter edits, and this contract makes none. | — |
| landing and records (`land_contract.py`, `pr_merged.py`) | not applicable | They import only `MANIFESTS` and run `--raise` / `--exact` (MECHANISMS.md line 94). Neither name changes. | — |
| making the suite a landing step (`work-item-conventions.json`) | not applicable | The brief excludes it by name (Out of scope). It stays recorded on the #240 issue body and in the follow-up stub (commit `7a0458f`), so no new handle is needed. The stub's own point that the row passes trivially after a landing is a Non-Goal below. | — |

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

---

## Chat Tool Impact

2. No. This contract adds no REST endpoint or SignalR event.

---

## Non-Goals

- Issue #240 item 1: the sync tool (`tools/sync-plugin.ps1`), which lives in another repository. The PR uses `Refs #240`.
- Making `test_plugin_manifests.py` a landing verification step or a CI step.
- Options (b), which exempts `task/` heads, and (c), which drops the row.
- Judging a non-`task/` head into a non-default base (a stacked pull request) the way `check_version_bump.py` does, where it is "not checked". The row keeps today's merge-base rule for such heads. The brief does not ask for it, and no workflow runs this suite today, so the difference is not observable in CI.
- Proving the landing's version raise. After a landing merges the parent into the default branch the merge base is the head itself, so the row passes trivially and never proves the raise (stub, 2026-11-07). The landing's own `--exact` / `--raise` checks own that proof; this row does not.
- Superseding the follow-up stub. The stub (commit `7a0458f`) is not on master. It is renamed `.followup.superseded.md` with a `Superseded by:` line by whichever change brings it onto master; this change leaves it alone.
- Replacing the test's own `VERSION_FILES` / `MANIFESTS` lists with `cvb.MANIFESTS`.
- Any change to `evaluate_parent`, `evaluate`, `--exact` or `--raise`.

---

## Confidence

Confidence: Medium. The parent rule, its predicate and the row's reader were read line by line, and the change is a lift with no behaviour change plus one dispatch. Two assumptions remain unverified: the local-without-base assumption (answered by the user as Q1, so now a decision) and the version of `origin/master` at pull request time. The cross-area scan has since been run and is clean.

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** Lift the parent predicate and the reader into named functions in `check_version_bump.py`, and have the row call them with its own branch reading and working-tree versions.
  - Why: one copy of the rule (acceptance criterion 2), no subprocess parsing, and fixtures can run in any folder.
- **Option B (rejected):** The row runs `check_version_bump.py --head-ref <ref> --base <base>` as a subprocess and reads its exit code.
  - Why rejected: it judges `HEAD:` blobs, not the working tree, so it disagrees with the default rule on uncommitted edits (I-2). It also needs a base that a local run does not have, and it maps exit 2 through a second interpretation layer.
- **Option C (rejected):** Re-spell the parent rule in the test, as "version equals merge-base version".
  - Why rejected: a second copy of the rule is forbidden by acceptance criterion 2, and it drifts. JOURNAL 2026-10-30 "One shared reader must own the filtering" says the same.

---

## Uncertain Assumptions

- `VERIFIED via check_version_bump.py:166-172`: parent mode is `TASK_HEAD.match(head_ref) and base != default_ref`. The allowed versions are those at base and at `merge-base(default_ref, HEAD)`.
- `VERIFIED via test_plugin_manifests.py:1478-1534`: the row today reads the working-tree `declared_versions` and fails, without skipping, when git cannot be read.
- `VERIFIED via test_plugin_manifests.py:484`: `.claude/scripts` is on `sys.path` before the INV-O1 block.
- `VERIFIED via check_version_bump.py:29` and `MECHANISMS.md` line 112: `.claude/scripts/tests/` is exempt from the bump, but `check_version_bump.py` is shipped (and vendored). So this PR needs a patch raise.
- `ASSUMED`: a local `task/` head, with no `GITHUB_BASE_REF`, targets a parent branch, so parent mode applies and only the merge-base version is allowed. If a `task/` head targeted master directly, a local run would wrongly apply parent mode. CI with `GITHUB_BASE_REF=master` is still correct (F-6). Verification: Q1.
- `ASSUMED`: `origin/master` still declares 0.18.1 when the PR opens. If master moved, the raise is one patch above its value. Verification: `git show origin/master:.claude-plugin/plugin.json` at PR time.
- `VERIFIED` by running `py -3 .claude/scripts/cross_area_scan.py` on this contract (2026-11-10): no adjacent area above threshold.

---

## Failure Modes & Mitigations

- **FM:** A fixture inherits CI's `GITHUB_HEAD_REF` and flips its outcome.
  - **Mitigation:** I-5. An explicit environment mapping is passed to every fixture row.
- **FM:** The refactor of `main()` changes parent-mode CLI behaviour.
  - **Mitigation:** the existing parent-mode rows in `test_check_version_bump.py` (lines 263–320) must stay green, and the new unit rows pin the predicate.
- **FM:** A detached HEAD locally reads as "no branch", and that silently passes.
  - **Mitigation:** I-4 and F-4. Unreadable is a FAIL that names the cause.
- **FM:** The shared reader raises inside the suite and aborts the whole run, so later rows never print.
  - **Mitigation:** `inv_o1_verdict` catches the same exception set as `main()` and returns `rule = unreadable`.
- **FM:** `check_version_bump.py` gains a non-stdlib import and breaks the vendored Hook registration check copy.
  - **Mitigation:** I-6. The reviewer checks the import block.

---

## Open Questions for User

- [x] **Q1 — Local `task/` runs without a known base.** A local run cannot see the parent branch, so the row allows only the merge-base version. Accept that, or skip parent mode locally unless `GITHUB_BASE_REF` is set? **Recommendation:** accept it. `task/` heads target parent branches by the delivery rule. With the alternative, the row would stay red locally on every sub-task, which is the bug being fixed.
  → **Answer (user, 2026-11-10, "approve with recommendations"):** accept the recommendation.
- [x] **Q2 — Do the script edits count as shipped?** Yes. `check_version_bump.py` sits under `.claude/scripts/`, which is not an exempt prefix, and it is a vendored file of the Hook registration check. The two test files are exempt (`.claude/scripts/tests/`). So this single-block PR to master raises a **patch**, 0.18.1 → 0.18.2: it fixes a red row and adds no capability. **Recommendation:** patch raise in this PR.
  → **Answer (user, 2026-11-10):** accept the recommendation.
- [x] **Q3 — One block.** The review runs as `/flow`'s reviewer step, not as a review block, so no parent branch or parent issue is needed. **Recommendation:** keep one block.
  → **Answer (user, 2026-11-10):** accept the recommendation.

---

## Critique

**Critic:** contract-critic
**Date:** 2026-11-10
**Verdict:** blockers-found

### Findings

- **[BLOCKER] The fixture repository cannot reach `rule = parent`: `_make_repo` is not "consumed as-is" for the parent path**
  - **What is wrong:** `_make_repo` (`test_plugin_manifests.py:1541-1550`) writes only `.claude-plugin/plugin.json`, but the shared reader the contract routes F-1, F-3 and F-5 through runs `git show <ref>:<m>` for every entry of `cvb.MANIFESTS` (`check_version_bump.py:25-26, 170`), so `plugin.json`, `.cursor-plugin/plugin.json` and `.claude-plugin/marketplace.json` are missing, `CalledProcessError` is raised, and by I-4 the verdict becomes `rule = unreadable`, not `parent`. Acceptance fixture F-1 cannot pass as written. The contract also does not say where a fixture's `declared` argument comes from: `collect_versions` reads `VERSION_FILES`, which the fixture repository does not hold either.
  - **Prior artifact ignored:** `MECHANISMS.md` line 94 ("`MANIFESTS` is the one list of version files"); template rule "Validation rule for consumed as-is" (`.claude/templates/concept-contract.md:109-114`: if a check fails, the change goes in Extension Points).
  - **Where in this contract:** `## Reused Mechanisms`: "The new fixture rows reuse `_make_repo` and add one `checkout -b` call."; `## Extension Points` F-1, F-3, F-5.
  - → Addressed by: Reused Mechanisms now says `_make_repo` is not consumed as-is; Extension Points adds `_make_parent_repo` (writes every `cvb.MANIFESTS` entry) and states where a fixture's `declared` comes from.
- **[BLOCKER] The cause text for an unreadable branch is predicted wrongly for two of its three failure kinds**
  - **What is wrong:** Data Shapes says each failure (detached HEAD, git failure, missing repository) gives "a cause that names what could not be read", but the TASK block tells the implementer "failure -> empty ref + cause naming detached HEAD / GITHUB_HEAD_REF" for every failure. `git symbolic-ref --short HEAD` exits 128 for a detached HEAD and for a non-repository alike, so a "detached HEAD" cause is false for a git failure or a missing repository. The source stub lists this lesson under "Journal entries to re-read when promoting", and `## Lessons referenced` omits it.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-06, "An exception sentence that names the outcome of a later call must list every outcome that call can have"; stub `2026-11-07-inv-o1-parent-branch-conflict.followup.md` (`Pre-derived context`, Journal entries to re-read).
  - **Where in this contract:** `## Data Shapes → Value Objects`, row "Checked branch reading", versus `## Implementation Handoff`, TASK block: "failure -> empty ref + cause naming detached HEAD / GITHUB_HEAD_REF".
  - → Addressed by: the Checked branch reading row now lists each failure outcome with its own cause text; F-4 pins the detached and not-a-repository causes apart; the TASK block carries the same list; the 2026-11-06 lesson is added to Lessons referenced.
- **[WARN] Confidence is High while three entries are ASSUMED**
  - **What is wrong:** the verdict reads "Confidence: High", and in the same line it says "Medium" on two of the three ASSUMED entries. Three `ASSUMED` lines remain (local `task/` base, `origin/master` at 0.18.1, the cross-area scan).
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md:244-252` (`## Confidence` format).
  - **Where in this contract:** `## Confidence`: "Confidence: High. ... It is Medium only on the local-without-base assumption (Q1) and on the cross-area scan not having been run."
  - → Addressed by: Confidence lowered to Medium and the two remaining assumptions named.
- **[WARN] A defect the source stub recorded is dropped without a Non-Goal**
  - **What is wrong:** the stub records that after a landing the merge base is the head itself, so the row "passes trivially, so it never proves the landing's raise either". The contract neither covers this nor lists it under `## Non-Goals`, so the only record of it is lost when the stub is superseded.
  - **Prior artifact ignored:** stub `2026-11-07-inv-o1-parent-branch-conflict.followup.md` line 14 (read from the `20261109-pr-merged-domain-split-registries` worktree; it is the same file as commit `7a0458f`).
  - **Where in this contract:** `## Non-Goals` (no entry for it).
  - → Addressed by: a Non-Goal now records the point and names the landing's own checks as its owner.
- **NITs (all seven):** → Addressed by: I-6 says seven; I-7 names the default ref; F-5 no longer claims a CI path; Adjacent Areas row 3 is anchored; a Non-Goal says who supersedes the stub; F-7 pins the empty-environment case; the CI-trigger lesson is regraded below.
- **[NIT] Stale vendored-file count** — I-6 says `check_version_bump.py` is "one of the five vendored files" (`MECHANISMS.md` line 112). The correction at line 113 (2026-11-09) makes it seven (`VENDORED_FILES`). The invariant's conclusion still holds: no new import.
- **[NIT] Journal entry misgraded as "not triggered"** — the `Apply when:` of `JOURNAL.md` 2026-10-30 "Widening a CI trigger changes who the check judges" includes "or adds a mode keyed on a head-ref pattern", which this contract does. Its head/base pairs are in fact enumerated across I-1, I-3, Non-Goals and F-1..F-6. One pair is justified only for local runs: in CI, a non-`task/` head with a non-default `GITHUB_BASE_REF` gets the merge-base rule where `check_version_bump.py` says "not checked". The Non-Goal's reason ("a local run cannot know the base") does not hold there.
- **[NIT] The default ref given to the shared reader is never named** — `inv_o1_verdict` passes a `default_ref` to `cvb.is_parent_mode` and `cvb.parent_allowed_versions`, but no section says where it comes from (the existing reader hard-codes `origin/master`, `test_plugin_manifests.py:1484`). See `JOURNAL.md` 2026-11-02, "A path that calls a command must say how it finds the command's input".
- **[NIT] "Proves the CI path" with no CI running the suite** — F-5 "proves the CI path", yet the brief and the stub (line 14) both say no configured gate runs `test_plugin_manifests.py`. The fixture proves that the environment is read, not a CI path (`JOURNAL.md` 2026-11-02, "A 'fails the build' claim must name the workflow that runs the check").
- **[NIT] Unanchored citation in Adjacent Areas row 3** — "already tracked on #240 / the stub": the stub is not on this branch or on `origin/master` (only in commit `7a0458f` and one other worktree). The row cites no MECHANISMS.md line or JOURNAL.md entry.
- **[NIT] Stub lifecycle not closed** — the stub's lifecycle says the promoting contract supersedes it (rename to `.followup.superseded.md` plus a `Superseded by:` line). The contract does not say which change does this, and the stub is not on this branch.
- **[NIT] No fixture for the set-but-empty environment value** — `GITHUB_HEAD_REF` / `GITHUB_BASE_REF` set to `""` or whitespace is specified ("non-empty after trimming") but no F-row pins it (`JOURNAL.md` 2026-10-04, "A VERIFIED parser claim must be tested on the unfilled and the missing case").

### Applicable journal entries

- **2026-10-30 — One shared reader must own the filtering, not only the selection** — heeded by I-1 (the predicate moves into `check_version_bump.py`, and both callers use it).
- **2026-10-30 — A delivery rule must name every route into delivery** — heeded by F-1..F-7 (local branch, detached plus environment, task head into master, unreadable).
- **2026-10-30 — Widening a CI trigger changes who the check judges** — heeded in substance (pairs enumerated) but graded "not triggered"; see the NIT above.
- **2026-11-05 — An "older release" test fixture must be pinned** — heeded by the throwaway-repository fixtures.
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome** — violated, see the BLOCKER above.
- **2026-11-06 — A sub-task that flips the state an earlier sub-task's test pins must re-run that suite** — heeded by the TASK block's Run list (it includes `test_plugin_manifests.py`, which pins the version), though `## Lessons referenced` does not cite it.
- **2026-11-09 — A change that adds a module-level import to a vendored script must update the vendored-file list** — heeded by I-6 (no new import) and by `test_check_hook_registrations.py` in the Run list.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — partly addressed; see the NIT above.

### What the critic did not check

- `derive_area.py`, `cross_area_scan.py` and `pr_merged.py --contract <slug> --status --json` were not run (no shell in this agent). Checklist items 11a and 14 were judged by reading only: one mergeable block, Work Item Brief header present, so no layout defect is expected.
- `git show 7a0458f:...` was not run. The stub was read from `D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261109-pr-merged-domain-split-registries\.claude\concepts\followups\2026-11-07-inv-o1-parent-branch-conflict.followup.md`.
- `.claude/registries/INTEGRATION.md` does not exist in this tree. The project domain files (`MECHANISMS/general.md`, `VOCABULARY/general.md`, `JOURNAL/general.md`) hold no entries.
- Whether `test_plugin_manifests.py` has other failing rows today (acceptance criterion 6) was not run.
- Verified claims: `EXEMPT_PREFIXES` (`check_version_bump.py:29-31`) exempts `.claude/scripts/tests/`, `.claude/concepts/` and `.claude/work-items/` but not `.claude/scripts/check_version_bump.py`, so a patch raise is required (project `CLAUDE.md` line 5: patch for a fix). `MECHANISMS.md` line 94 matches the parent-mode code at `check_version_bump.py:163-174`. Line numbers 484, 1466-1573 and 52-55 of `test_plugin_manifests.py` are accurate.

---

## Lessons referenced

- **2026-10-30 — One shared reader must own the filtering, not only the selection** — heeded by I-1. The mode predicate, not only the reader, moves into `check_version_bump.py`, and both callers use it. Cross-reference: `JOURNAL.md`.
- **2026-10-30 — A delivery rule must name every route into delivery** — heeded by the fixture set. It covers a local branch (F-1 to F-3), a detached CI checkout (F-5), a task head into master (F-6), and an unreadable branch (F-4). Cross-reference: `JOURNAL.md`.
- **2026-10-30 — Widening a CI trigger changes who the check judges** — heeded in substance. The entry's "adds a mode keyed on a head-ref pattern" clause applies; every head and base pair is enumerated in I-1, I-3, the Non-Goals and F-1 to F-7, and no workflow edit is made. Cross-reference: `JOURNAL.md`.
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have** — heeded: the Checked branch reading row and F-4 list every outcome of the branch read with its own cause. Cross-reference: `JOURNAL.md`.
- **2026-11-06 — A sub-task that flips the state an earlier sub-task's test pins must re-run that suite** — heeded: the Run list includes `test_plugin_manifests.py`, which pins the version. Cross-reference: `JOURNAL.md`.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by F-7 (set-but-empty environment values). Cross-reference: `JOURNAL.md`.
- **2026-11-05 — An "older release" test fixture must be pinned** — heeded: the fixtures build their own throwaway repositories and never read this repository's `HEAD:` as a baseline. Cross-reference: `JOURNAL.md`.
- Orthogonal to north-stars: none active (`.claude/north-stars/` is absent).

---

## Implementation Handoff

One mergeable block (Q3). The review runs as `/flow`'s reviewer step. The patch raise to 0.18.2 is in this pull request.

### 1. Parent-aware INV-O1 row and shared parent reader (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/check_version_bump.py`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/tests/test_check_version_bump.py`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**Pre-written TASK block:**
```
TASK: Make the INV-O1 version row in test_plugin_manifests.py parent-aware by reusing check_version_bump.py's
parent-mode rule through one shared reader, add fixtures F-1..F-7, and raise the plugin version one patch.
CONTEXT: concept contract .claude/concepts/2026-11-10-inv-o1-parent-aware.md (Data Shapes I-1..I-6, Extension
  Points); brief .claude/work-items/2026-11-10-240-inv-o1-parent-aware.md.
FILES: see Files to touch.
CONSTRAINTS:
  - Tests first (/tdd-first). The contract is authoritative; do not redesign shapes.
  - check_version_bump.py: lift is_parent_mode(head_ref, base_ref, default_ref) and
    parent_allowed_versions(base_ref, default_ref, cwd=None) out of main(); _git gains an optional cwd keyword;
    main() calls both; evaluate_parent, evaluate, --exact, --raise, flags, exit codes and stdlib-only imports
    unchanged (I-6).
  - test_plugin_manifests.py: add read_checked_branch(root, environ) (GITHUB_HEAD_REF trimmed wins, else
    git symbolic-ref --short HEAD; set-but-empty or whitespace value = unset; on failure an empty ref plus
    ONE OF THREE distinct causes exactly as Data Shapes lists them: detached HEAD, git cannot read HEAD / not a
    repository, git could not run. Never one shared cause sentence) and
    inv_o1_verdict(root, environ, declared). Parent mode via cvb.is_parent_mode with base origin/<GITHUB_BASE_REF>
    or absent; allowed via cvb.parent_allowed_versions; verdict via cvb.evaluate_parent on the working-tree
    declared versions. Otherwise today's read_merge_base_state + version_matches_tree path, unchanged.
    Catch CalledProcessError/OSError/ValueError/KeyError -> rule unreadable, FAIL with cause. Never skip.
    Do not spell TASK_HEAD or the parent rule in the test.
  - Fixtures F-1..F-7 exactly as Extension Points lists, each with an explicit environ mapping, never os.environ
    (I-5). Build parent fixtures with the new _make_parent_repo (writes every cvb.MANIFESTS entry; _make_repo is
    NOT enough for the parent path); declared = versions read back from the fixture's working tree via
    cvb.versions_in. Pass DEFAULT_REF (origin/master) as default_ref (I-7). The five existing INV-O1 controls
    and five reader controls stay green.
  - Update the INV-O1 docstring entry and the section print label to say parent-aware.
  - test_check_version_bump.py: unit rows for is_parent_mode (three cases) and parent_allowed_versions(None, ...);
    existing parent-mode CLI rows stay green.
  - Patch raise in all five declarations to one patch above origin/master's version (0.18.2 if master is at 0.18.1).
  Run (all must exit 0, quote each exit code in the HANDOFF):
    py -3 .claude/scripts/tests/test_plugin_manifests.py
    py -3 .claude/scripts/tests/test_check_version_bump.py
    py -3 .claude/scripts/check_version_bump.py --base origin/master --default-branch master --head-ref fix/240-inv-o1-parent-aware
    py -3 .claude/scripts/tests/test_check_hook_registrations.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-10-inv-o1-parent-aware.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

`pr_merged.py` fills this list when the contract's work is merged and nothing is pending. Do not tick lines by hand.

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both backend and frontend sides
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
- [ ] `Status` flipped to `implemented`
