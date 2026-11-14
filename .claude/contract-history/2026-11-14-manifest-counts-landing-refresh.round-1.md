# Contract critique, round 1 (2026-11-14)

Moved word for word out of `.claude/concepts/2026-11-14-manifest-counts-landing-refresh.md` (`## Critique`), per the contract budget rule.

**Critic:** contract-critic
**Date:** 2026-11-14
**Verdict:** blockers-found

### Findings

- **[BLOCKER] The new P8 step `manifest-counts` cannot pass on the default branch, so `--record-baseline` breaks for every later landing**
  - **What is wrong:** I-4 makes `--exact --manifest-counts` run the version check first and report both, and `--exact` exits 1 on any tree whose version is not origin/<default> minor + 1 (`check_version_bump.py:100-108`). `land_contract.py --record-baseline` runs every configured step twice in a default-branch worktree and returns `environment-failure` ("step %s failed on the default branch, so nothing can be measured") for any `exit-code` step that does not exit 0 (`land_contract.py:982-1004`, launched at `:3278`). On master 0.20.4 the step reads "must be exactly 0.21.0", so once Extension Point 3 lands, no baseline can be recorded. The existing `version-bump` step is the default mode, which exits 0 on master because the diff is empty.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery, not only the one the author had in mind" (baseline recording is a route that runs the landing's steps, and it is missing from block 1's route table). Also `MECHANISMS.md:95` (Plugin version check modes: `--exact` is a landing-only mode measured against origin/<default>).
  - **Where in this contract:** `## Data Shapes` I-4 "It runs after the version check and reports both results"; `## Extension Points` 3 `"command": [..., "--exact", "--manifest-counts", ...]`; `## Reused Mechanisms` "Landing verification steps … extended by one step".
- **[WARN] The Run lists say to run every landing verification step verbatim and to stop on red, but two steps exit 1 on a sub-task branch and at the parent tip**
  - **What is wrong:** before the landing raise, `version-bump` (default mode against origin/master, shipped files changed, version unchanged) and the new `manifest-counts` (`--exact`) both exit 1 on block 1's branch and at the parent tip. That trips block 1's own rule "A red suite in the Run list stops the block", and block 2 runs the same steps "at the parent tip". Task (4), "Measure the new step once", would therefore time a failing run.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-07 "A merge block's pull request must paste each required output, not tick a line that says it passed" ("when the implementer finds that the contract mis-predicts the code (an exit code …) … an amendment must fix the text").
  - **Where in this contract:** `## Implementation Handoff` block 1 CONSTRAINTS "and every landing verification step in .claude/work-item-conventions.json, verbatim" and "A red suite in the Run list stops the block"; block 2 "Run block 1's Run list and the landing verification steps verbatim, at the parent tip".
- **[WARN] The full pin never asserts refreshability, so master can hold a claim that is green under the full pin and refused by the refresh**
  - **What is wrong:** under I-6, only the deferred pin asserts "the Count refresh plan for HEAD has no refusal", and the full pin keeps today's equality and noun checks. The noun → measure table deliberately covers the README nouns (`_ORACLE_NOUNS`, `test_repo_consistency.py:494-498`: add-ons, working agreements, …), and `_COUNT_RE` reads "hook files" where `_CLAIM_RE` does not (`:79` and `:499-501`). So a single-block pull request into master can make a description say "3 add-ons" or "14 hook files". That passes the full pin, yet the refresh refuses it (`count-unrefreshable-noun` / `count-reader-disagreement`). From then on, every deferred sub-task pull request on every parent branch is red on a manifest it may not edit, and every landing halts `version-raise-failed`. This is the owner-exit situation that acceptance criterion 3 removes. The Failure Modes sentence also predicts the wrong refusal set.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery …" (the single-block-into-master route has no enforcement point for refreshability). Also `JOURNAL.md` 2026-11-06 "An exception sentence that names the outcome of a later call must list every outcome that call can have".
  - **Where in this contract:** `## Data Shapes` I-6 "Under deferral the equality assertions of V3 assert instead that the Count refresh plan for HEAD has no refusal"; `## Failure Modes & Mitigations` "a green master is refreshable except for `oracle-empty` and `count-unwritable`".
- **[WARN] `count_pin_deferred` writes out the base-branch comparison again instead of calling the public parent predicate**
  - **What is wrong:** the registry's Extend-by says that a second consumer of the parent rule calls `is_parent_mode` / `parent_allowed_versions` / `evaluate_parent` and "never re-spells `TASK_HEAD` or the base comparison". The new predicate reuses `TASK_HEAD` but redefines the comparison with different handling of an unknown base and an empty default. Under Q2's narrower answer it would be exactly `is_parent_mode`. Under the wider answer it is a second, differing definition of "a pull request into a non-default base".
  - **Prior artifact ignored:** `MECHANISMS.md:96` (Plugin version check modes, Extension 2026-11-10, issue #240).
  - **Where in this contract:** `## Reused Mechanisms` "the public predicate `count_pin_deferred` beside `is_parent_mode`, which it reuses for `TASK_HEAD`"; `## Data Shapes` I-6.
- **[NIT] Three cited "mechanisms" have no MECHANISMS.md entry** — "Count-claim oracle", "Landing P7b and R-3" and "Landing verification steps" appear under `## Reused Mechanisms`, but `MECHANISMS.md` mentions the landing only inside line 95, and `MECHANISMS/general.md` is empty. Extension Point 7 records only an extension under Plugin version check modes, so the I-9 rule and the new step stay unregistered.
- **[NIT] I-1 says the move needs "no test body changes"** — but Extension Point 5 changes the bodies of the three V3 pins. Also, `test_repo_consistency.py` imports only the standard library today (`:32-38`) and CI runs it as a script from `tests/`, so the import back needs a `sys.path` entry the contract does not name.
- **[NIT] The generic env names can defer the pin locally without anyone noticing** — a `BASE_REF` / `DEFAULT_BRANCH` left over in a developer's shell gives `source: env` and a deferral on any branch. I-7 ("strict when in doubt") covers an unresolvable context, not a stale but valid one.

### Applicable journal entries

- **2026-10-30 — A delivery rule must name every route into delivery, not only the one the author had in mind** — violated, see the BLOCKER (baseline recording) and the third WARN (single-block route into master).
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — heeded by "A branch in flight on the day this ships" (sync sub-task).
- **2026-10-30 — One shared reader must own the filtering, not only the selection** — heeded by I-1 / I-4.
- **2026-10-30 — Widening a CI trigger changes who the check judges; list every pull request kind the old filter excluded** — heeded by I-6, I-7, Q2 and block 1's route table (5).
- **2026-11-01 — A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for** — heeded by I-2 and the `count-reader-disagreement` refusal (the reader now drives a writer). Gap: see the third WARN.
- **2026-11-02 — A "fails the build" claim must name the workflow that runs the check** — heeded by V4 and Extension Point 4 (`version-bump.yml` `tests` job).
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them** — heeded by block 1 CONSTRAINTS.
- **2026-11-06 — A sub-task that flips the state an earlier sub-task's test pins must re-run that suite** — heeded by the Run list.
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have** — violated, see the third WARN (the Failure Modes refusal set).
- **2026-11-07 — A parent branch that shares files with a moving default branch must take the default branch in through a sub-task before its landing** — heeded by the in-flight handling.
- **2026-11-07 — Merge rules written for a long-lived branch must heed the default branch's journal, not only the branch's own** — not addressed. The contract did not need to: I-9 is written on a branch cut from the current master tip, so the two journals are identical.
- **2026-11-07 — Adapters that rebuild an old reader over a stricter grammar must list every behaviour difference** — heeded by I-1 (verbatim move, controls kept).
- **2026-11-07 — A merge block's pull request must paste each required output** — heeded by the evidence lists. Violated in spirit by the Run-list wording, see the first WARN.
- **2026-11-09 — A change that adds a module-level import to a vendored script must update the vendored-file list in the same change** — heeded by I-8, Option D and `test_check_hook_registrations.py` in the Run list.

### What the critic did not check

- `.claude/registries/INTEGRATION.md` and `.claude/.scout-cache/registry-digest.md` do not exist in this worktree, so I read the registries directly and found no integration-surface map to compare against.
- Checklist item 14: I have no shell, so I could not run `pr_merged.py --contract 2026-11-14-manifest-counts-landing-refresh --status --json`. From reading `delivery_layout` (`pr_merged.py:1572-1640`) and the brief: neither block lists a `MANIFESTS` path, the `**Work Item Brief:**` header is present, and the brief's `branch:` is not the default branch, so I found no layout defect.
- Checklist item 11: `derive_area.py` was not run. `.claude/area-mapping.json` has `"areas": {}`, so it can return only the fallback.
- Checklist item 13: `.claude/north-stars/` is absent, so there were no findings.
