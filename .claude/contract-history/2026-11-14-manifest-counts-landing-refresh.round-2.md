# Contract critique, round 2 (2026-11-14)

Moved word for word out of `.claude/concepts/2026-11-14-manifest-counts-landing-refresh.md` (`## Critique`), per the contract budget rule.

### Second pass (2026-11-14)

**Critic:** contract-critic
**Date:** 2026-11-14
**Verdict:** blockers-found

Every first-pass finding is answered in the body: the step is now `--counts` (V11, I-5, Option G), the Run lists name the red-before-raise step with its reason, the full pin asserts refreshability (I-4), `count_pin_deferred` is built on `is_parent_mode` plus `is_non_default_base` (I-6), the Contract landing entry is registered (Extension Point 7), I-1 names the `sys.path` entry, and the env names are `MANIFEST_PIN_*` with all-or-none (I-7). The findings below are new.

#### Findings

- **[BLOCKER] Block 1's Run list says `test_land_contract_verification.py` exits 0, but two of its rows fail on this repository's config today, and the CONSTRAINTS forbid changing them**
  - **What is wrong:** `test_generated_drift_is_the_last_step_and_lists_the_three_sentinel_keys` (`test_land_contract_verification.py:498-504`) requires a last step `generated-drift`, and `test_the_python_scripts_command_...` (`:506-508`) requires a step `python-scripts`. Neither step exists in `.claude/work-item-conventions.json:92-124`, and neither will exist after Extension Point 3. `RealProjectConfigTests.setUp` skips only when there is no `contractLanding` block (`:474-477`). So the file is red by construction on master, on block 1's branch and at the parent tip. Block 1's CONSTRAINTS list the tests that may change, and only `:491-494` is in that file. They also say "any other result stops the block", so block 1 stops on its first Run. Block 2 inherits the same command ("Run block 1's Run list at the parent tip").
  - **Prior artifact ignored:** `.claude/reviews/2026-11-04-domain-split-registries/t18-review-fullstack-code-reviewer.md:94-98` (N3: "fails 2 rows, and both belong to master … Block 17 listed it as expected green, which was a contract mis-prediction"). Also `JOURNAL.md` 2026-11-07 "A merge block's pull request must paste each required output …" ("when the implementer finds that the contract mis-predicts the code (an exit code …) … an amendment must fix the text").
  - **Where in this contract:** `## Implementation Handoff` block 1 CONSTRAINTS: "Run (all exit 0): … test_land_contract_verification.py" and "Every command below must end at its stated exit code; any other result stops the block."
- **[WARN] I-1's "verbatim move, no test body changes" contradicts the Count measure value object, which turns the filesystem measures into path rules fed a listing**
  - **What is wrong:** `hook_file_count(hooks_dir: Path)` globs a directory (`test_repo_consistency.py:94-97`), and `count_oracles` globs `skills/*/SKILL.md` and `agents/*.md` on disk (`:512-513`). The value object says one path rule per measure, "the script feeds it the HEAD tree listing; the test feeds it the filesystem listing". A function imported "under its current name" cannot take a `Path` for the control at `:463` (`hook_file_count(dir_with(15))`) and a `git ls-tree` listing for `--counts`. That leaves three options. A filesystem adapter in the test is a second copy of the rule, against I-1 "defined once". A changed signature changes the control's body, which is not in the CONSTRAINTS list of tests that may change. A two-input function is a behaviour difference the contract does not list. The contract names none of the three.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-07 "Adapters that rebuild an old reader over a stricter grammar must list every behaviour difference". Also `JOURNAL.md` 2026-11-02 "Name the tests a fix may change by the state they guard, after reading them".
  - **Where in this contract:** `## Data Shapes` Value Objects "Count measure (moved, unchanged) … The script feeds it the HEAD tree listing; the test feeds it the filesystem listing"; I-1 "The move is verbatim … no test body changes except the three V3 pins".
- **[WARN] This contract's own landing runs neither `--manifest-counts` nor the `manifest-counts` step, so the route-table row and Q4's rationale describe a landing that will not happen**
  - **What is wrong:** the landing reads its conventions at `origin/<default>` (`land_contract.py:2143`; baseline at `:3256`), and master gains `manifestCounts` and the new step only when this contract lands. So this landing's P7b runs plain `--raise` / `--exact` (`:3140`), and its P8 has no `manifest-counts` step. The route row "landing pull request into master -> full (CI tests; P7b + P8 made it true)" is therefore not true for this contract's own landing. It is green only because block 1 adds no skill, agent or hook, and the contract never says so. Q4's rehearsal (block 2 (l)) runs `check_version_bump.py --raise --manifest-counts` by hand and never runs `land_contract.py`, so the config wiring, I-9 and P8 step selection go unexercised. That contradicts "proves the landing end to end" and "the tree the landing will produce". Its result also holds only for the `origin/master` commit it merged. Finally, it uses a fixed path (`$env:TEMP\rehearsal-405`) and has no cleanup when a command fails: a conflicted merge leaves a dirty worktree that `git worktree remove` refuses, and a re-run then fails at `worktree add`.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery, not only the one the author had in mind" (the contract's own bootstrap landing is a route). Also `JOURNAL.md` 2026-11-07 "A clean landing check goes stale when the default branch moves; re-run it immediately before launching".
  - **Where in this contract:** `## Open Questions for User` Q4 "Block 2 proves the landing end to end … the tree the landing will produce"; block 1 TASK (5) "landing pull request into master -> full (CI tests; P7b + P8 made it true)"; block 2 (l).
- **[WARN] The `--counts` step turns count drift on master into a halt of every landing and of baseline recording, and no failure mode names it**
  - **What is wrong:** before this change, a count drift on master (a pull request merged with `tests` red, which today's `MANIFEST_REMEDY` exit (ii) explicitly allows, `test_repo_consistency.py:674-681`) reddened only CI. With `manifest-counts` configured, `run_recording` returns `environment-failure` for any `exit-code` step that is not `ok` (`land_contract.py:1000-1004`). P8 also halts every parent-branch landing, because the merged tree carries master's drift. The FM "A configured step is red on the default branch" is mitigated only by "the step is `--counts`". That covers a tree whose counts are true, not one whose counts have drifted.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 "A revision that adds a path adds its failure modes".
  - **Where in this contract:** `## Failure Modes & Mitigations` "A configured step is red on the default branch, so `--record-baseline` breaks. **Mitigation:** the step is `--counts` (V11, I-5) …".
- **[NIT] One Count verdict, two exit codes for the same refusal** — I-3 gives exit 2 for every Count refusal under `--raise`, while I-4 gives `--counts` exit 1 for a failed verdict and 2 only for `oracle-*`. The precedence between a version exit and a count exit under `--exact --manifest-counts` is also unstated (Commands table: "exit 1 on drift, 2 when it could not read").
- **[NIT] The follow-up stub this contract delivers stays `**Status:** stub`** — `.claude/concepts/followups/2026-11-13-manifest-counts-under-parent-branch.followup.md:6`. No block lists it, and `MANIFEST_REMEDY` stops citing it (Extension Point 5).
- **[NIT] The superseded first critique round and the two-line resolved questions stay inline** — `.claude/templates/concept-contract.md:22` moves a superseded round to `.claude/contract-history/<slug>.round-<n>.md` and shrinks each resolved question to one line. This second pass is appended here only because the orchestrator asked for it.

#### Checked against the tree, no finding

- `--counts` on master: after landing, master's script has the mode and master's full pin asserts equality plus an empty refusal list. The step writes nothing (P8 `tree_unchanged`, `land_contract.py:3181-3182`; `__pycache__/` is ignored, `.gitignore:2-3`), so `run_recording` reads `ok`. Option G and V11 match `check_version_bump.py:62-65, 100-108` and `land_contract.py:994-1005`.
- The first-pass BLOCKER is resolved: no configured step runs `--exact` or `--raise`, and a test pins that.
- I-6 matches `is_parent_mode` (`check_version_bump.py:133-135`) and `main:179`, and heeds `MECHANISMS.md:96`. I-7's all-or-none env rule gives `none` → full on any partial set. The workflow runs on `pull_request` only (`version-bump.yml:3-4`), so no push run feeds empty refs.
- Extension Point 4 does not trip the existing workflow pins: `test_the_refs_go_through_env_and_are_quoted_in_the_run_line` takes the first `run:` step (the `version-bump` job, `test_check_version_bump.py:578-585`), and `ci_violations` reads only `run:` lines (`test_repo_consistency.py:211-224`).
- Today's descriptions (`plugin.json:5`, `.claude-plugin/plugin.json:6`, `.claude-plugin/marketplace.json:7,14`, `.cursor-plugin/plugin.json:4`) use digits only, and both readers read "14 hooks" alike, so U-4 is plausible.
- Block 2 `.gate.json` versus `Files to touch`: not a defect. `.claude/templates/concept-contract.md:410` says that the Gate Output "is not listed in `Files to touch`, which keeps naming exactly one path; the off-list check counts it as part of the declared artefact", and `pr_merged.py:3725-3751` pairs it by stem.
- `test_parent_branch_rule_text.py:330-331`, `skills/advance/SKILL.md:378-379`, `test_land_contract_verification.py:491-494` and every Run-list test file exist as cited.

#### Applicable journal entries

- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded: every first-pass finding is folded into I-1 to I-9, Extension Points 3, 5 and 7, and Option G.
- **2026-10-30 — A delivery rule must name every route into delivery** — violated, see the third WARN (the bootstrap landing).
- **2026-11-02 — A revision that adds a path adds its failure modes** — violated, see the fourth WARN.
- **2026-11-02 — Name the tests a fix may change by the state they guard** — violated, see the second WARN (`:463`, `:660` controls).
- **2026-11-07 — Adapters that rebuild an old reader … must list every behaviour difference** — violated, see the second WARN.
- **2026-11-07 — A clean landing check goes stale when the default branch moves** — not addressed by Q4, see the third WARN.
- **2026-11-07 — A merge block's pull request must paste each required output** — violated, see the BLOCKER.
- **2026-11-09 — A module-level import to a vendored script must update the vendored-file list** — heeded by I-8 and `test_check_hook_registrations.py` in the Run list.

#### What the critic did not check

- I had no shell, so I did not run any suite. Whether `test_pr_merged.py`, the hook tests or `test_plugin_manifests.py` are green today is unverified. The BLOCKER rests on reading the code.
- I did not run `pr_merged.py --contract … --status --json` (checklist item 14). The first-pass reading still holds, because neither block lists a manifest.
