# Concept Contract — Landing-time refresh of the manifest counts

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-14
**Requested by:** user
**Status:** implemented
**Implemented:** 2026-11-16, automatically, by pr_merged.py after https://github.com/lneninger/claude-agentic-auto-improve/pull/414, https://github.com/lneninger/claude-agentic-auto-improve/pull/416, https://github.com/lneninger/claude-agentic-auto-improve/pull/427; 3 checklist items from review reports, 0 with no structured evidence; not performed (disclosed on #405): none; owner confirmed resolved: none
**Work Item Brief:** .claude/work-items/2026-11-14-405-manifest-counts-landing-refresh.md
**Tracking issue:** #405
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. Implementer agents refuse to run unless `Status: approved` or `Status: implemented`. The `concept-gate.py` hook reads `Files to touch`. Lifecycle, budget rule and management commands: `.claude/templates/concept-contract.md`.

---

## Business Concept

- **What is this thing, in domain language?**
  The four plugin manifests state how many skills, agents and hooks the plugin ships, and a test pins those numbers to the tree. On a contract delivered through a parent branch, no reviewed route can correct those numbers: a sub-task may not list a manifest, and the landing's raise writes only the version fields. This contract closes that gap from both ends. (1) **The landing writes the counts.** The landing's version raise also rewrites the counts in the manifest descriptions from the tree, in the same commit, and the landing's checks then confirm that every count equals the tree. (2) **A pull request into a parent branch is not judged on counts it may not correct.** On a pull request whose base is not the default branch, the pin checks only that the counts are still refreshable, and leaves equality to the pull request that reaches the default branch. (3) **The default branch can never hold counts the landing cannot refresh**, because its full pin asserts refreshability too. Together these remove both owner-only exits of the follow-up stub. No pull request merges with `tests` red, and no recount pull request follows a landing.

- **Existing VOCABULARY.md terms that apply:** **Parent Branch Delivery Rule** (`VOCABULARY.md:74`), **Layout defect** `sub-task-raises-version` (`:75`), **Landing version raise** (`:76`), **Vendored asset** (`:34`). Also the mechanism **Plugin version check modes** (`MECHANISMS.md:95-96`).

- **New terms proposed for VOCABULARY.md** (Universal root, appended by block 1 after approval):
  - **Landing count refresh** — the rewrite of the skill, agent and hook counts in the plugin manifest descriptions that the landing makes from the tree, in the same commit as the **Landing version raise**. It changes only the number in each count. It is turned on by `contractLanding.manifestCounts`. Under `landing: manual` the operator makes it.
  - **Count deferral** — on a pull request whose base is not the default branch, the manifest count pin checks only that every count can be refreshed. Equality with the tree is judged on the pull request that reaches the default branch, which the **Landing count refresh** makes true.

### Verification against this tree (2026-11-14, worktree on the branch feature/405-landing-time-manifest-count-refresh)

| # | Claim | Found |
|---|---|---|
| V1 | The raise writes version fields only | `check_version_bump.py:111-126` (`raise_manifests`, `VERSION_FIELD` at `:78`). Commit message at `:125` |
| V2 | The count oracle lives in a test file | `count_oracles` (`test_repo_consistency.py:507-521`), `_CLAIM_RE` / `_ORACLE_NOUNS` (`:494-502`), `WORDS` / `_COUNT_RE` / `_counts` (`:72-107`), `hook_file_count` (`:94-97`), `manifest_descriptions` (`:132-137`), `MANIFEST_REQUIRED_NOUNS` and `MANIFEST_REMEDY` (`:668-681`). The test imports only the standard library (`:32-38`) |
| V3 | Three real pins read the manifests | `HookCountTests.test_manifest_descriptions_state_the_real_hook_count` (`:396-408`), `ManifestCountPinTests.test_manifest_description_counts_match_oracles` and `test_every_manifest_keeps_its_nouns` (`:703-713`) |
| V4 | CI runs them on every pull request, with no context | `version-bump.yml:24-33`. The `tests` job has no `env:` and a shallow checkout |
| V5 | P7b runs the lander's own copy of the script | `_p7b_version_raise` (`land_contract.py:3137-3144`), `SCRIPTS_DIR` (`:59`). P7b runs only when `versionRaise` is true (`:2342`). Manifests count as the landing's own paths (`:2357`) |
| V6 | R-3 halts on a description difference | `merge_version_fields` (`land_contract.py:1205-1230`). In `plugin.json` the version and description lines are adjacent, so they share one region |
| V7 | `check_version_bump.py` is vendored | `VENDORED_FILES` (`check_hook_registrations.py:38-46`). It imports only the standard library |
| V8 | Existing raise fixtures have count-free descriptions | `"kept"` (`test_check_version_bump.py:398`), `"d"` (`test_land_contract_identity.py:1126`) |
| V9 | The counts are true today | 34 skills, 15 agents, 14 hook files; they match all four descriptions. Master's version is 0.20.4 |
| V10 | The layout rule | `delivery_layout` (`pr_merged.py:1585-1638`) |
| V11 | Baseline recording runs every step twice on the default branch | `run_recording` (`land_contract.py:982-1004`): an `exit-code` step that is not `ok` returns `environment-failure` "failed on the default branch". `--exact` exits 1 on any tree not at origin/<default> minor + 1 (`check_version_bump.py:100-108`), so `--exact` can never be a configured step. The default mode exits 0 on master (empty diff, `:62-65`) |
| V12 | The parent predicate and the base comparison | `is_parent_mode` (`check_version_bump.py:133-135`) spells `base_ref != default_ref`; `main` spells it again at `:179`. The test file imports by `sys.path.insert(0, str(SCRIPTS_DIR))` (`test_check_version_bump.py:14`) |
| V13 | The configured steps today | `version-bump` (default mode), `loop-script-tests`, `hook-registration-tests`, `hook-tests` (`work-item-conventions.json:93-123`); the list is pinned at `test_land_contract_verification.py:491-494` |
| V14 | Two known failures on master | Verified by the main session on unmodified master: `py -3 -m unittest test_land_contract_verification` (from `.claude/scripts/tests`) runs 79 tests and fails exactly `RealProjectConfigTests.test_generated_drift_is_the_last_step_and_lists_the_three_sentinel_keys` ('hook-tests' != 'generated-drift') and `RealProjectConfigTests.test_the_python_scripts_command_prints_per_test_lines_and_a_per_file_line_only_for_a_crash` ('python-scripts' is None). Fixing them is out of scope |
| V15 | The landing reads master's config | Conventions are read at `origin/<default>` (`land_contract.py:2143`, baseline `:3256`); P7b passes no flag today (`:3140`) and treats any non-zero exit as a failure (`:3142`) |
| V16 | The disk measures | `hook_file_count(hooks_dir)` globs a directory (`test_repo_consistency.py:94-97`); `count_oracles(root)` globs `skills/*/SKILL.md` and `agents/*.md` (`:512-513`); the controls at `:463` and `:660` call both with temporary directories |
| V17 | The script's git reader | `_git` runs with `text=True` and no encoding (`check_version_bump.py:129-130`), so it decodes in the locale code page; `main` maps a `ValueError` (a decode error included) to exit 2 (`:192-193`). Without `-z`, `git ls-tree` quotes a path holding a non-ASCII byte, `"` or `\` (`core.quotePath`) |
| V18 | How a stub is promoted | Template: rename to `.followup.superseded.md` and add a `Superseded by:` line (`followup-stub.md:44`). House form: `**Status:** superseded` then `**Superseded by:** <path> (issue #n)` (`followups/2026-11-11-manifest-description-counts.followup.superseded.md:6-7`). `list_contracts.py` sets `superseded` from that file name (`:183-184`); it shows a pointer only for a `Supersedes:` line (`:129-134, 264-265`), so none of the nine superseded stubs shows one. `archive_stale_stubs.py` collects only names ending `.followup.md` (`:69`), so the renamed file is never archived |

---

## End-User View

Not applicable. Reason: no Angular UI surface is touched. The users are plugin maintainers running the landing.

---

## Data Shapes

### Entities

Not applicable. Reason: there is no persistent entity. The shapes are manifest text, a tree listing and one commit.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Count measure (rule moved; listing per consumer) | measure (`skills` / `agents` / `hooks`), path rule | One rule per measure over a list of repository-relative paths with `/` separators, compared case-sensitively. skills: `skills/<one segment>/SKILL.md`. agents: `agents/<name>.md`. hooks: `.claude/hooks/<name>.py` directly, name not starting with `_`, not `gate-launch.py`. The rule takes a path list and never touches disk or git. Each measure's root (`skills/`, `agents/`, `.claude/hooks/`) is one shared constant beside the rule. The script's listing `tree_paths(cwd)` runs `git ls-tree -r -z --name-only HEAD` and reads raw bytes: NUL-split, each path decoded as UTF-8 with `surrogateescape`, never through `_git`'s locale text decoding (V17). The test lists the files on disk (I-1) |
| Count claim (moved, unchanged) | manifest, description index, noun, measure, stated number, number form (`digits` / `word`), span | One `<number> [up to two words] <noun>` match of the shared claim reader. `subagents` maps to `agents`. The noun → measure table holds every noun the README pins read, so a manifest claim of another measure is seen too |
| Manifest count nouns (moved from the test) | manifest → required nouns | `plugin.json`: skills. `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`: skills, agents, hooks. `.cursor-plugin/plugin.json`: skills, subagents |
| Count refresh plan | per manifest: new text, rewrites (claim, old number, new number), refusals | Computed for all four manifests before anything is written. Only an empty refusal list lets anything be written |
| Count refusal | reason, kind (`description` / `read`), manifest, detail | Closed set. Kind `description`: `count-missing` (a required noun has no claim), `count-unrefreshable-noun` (a claim of a measure other than skills, agents or hooks), `count-unwritable` (a spelled count whose new value is outside one to twenty), `count-reader-disagreement` (the hook reader and the claim reader read a description differently), `description-not-located` (a description value is not found exactly once in the file text). Kind `read`: `oracle-unreadable` (the tree listing failed), `oracle-empty` (a required measure reads zero) |
| Count verdict | equality (each claim equals its measure, by both readers), noun presence, refresh plan refusals | The one judgement shared by the full pin, `--counts` and `--exact --manifest-counts` (I-4) |
| Pin context | head, base, default branch (all bare branch names), source (`env` / `git` / `none`) | Resolved by the test. `env`: all three of `MANIFEST_PIN_HEAD_REF`, `MANIFEST_PIN_BASE_REF`, `MANIFEST_PIN_DEFAULT_BRANCH` are set and non-empty. `git`: none of the three is set; head from `git rev-parse --abbrev-ref HEAD`, default from `git symbolic-ref refs/remotes/origin/HEAD` (minus `origin/`), base unknown. `none`: any other case, including one or two of the three set, or a git failure |

**Invariants**

- **I-1 One rule, one reader; the listing stays with each consumer.** Defined once, in `check_version_bump.py`: the three path rules (one function over a path list, plus the hook-name test) with their three measure roots, the git listing `tree_paths`, the claim reader (`WORDS`, `_NUM`, `_GAP_WORD`, `_COUNT_RE`, `_CLAIM_RE`, `_ORACLE_NOUNS`, `_NOUN_MEASURE`, `_counts` with its "retired" skip), the noun table and `manifest_descriptions`. The readers move verbatim and accept exactly today's forms. `test_repo_consistency.py` imports them under its current names, after `sys.path.insert(0, str(PLUGIN_ROOT / ".claude" / "scripts"))` (the entry at `test_check_version_bump.py:14`). The test keeps `hook_file_count(hooks_dir)` and `count_oracles(root)` with their signatures unchanged, as thin disk-listing wrappers. Each lists every file under its directory, recursively (`is_file()`, names as stored), joins the imported measure root with each name relative to that directory, and calls the shared rule, which drops what is nested, misnamed or excluded. `hook_file_count(hooks_dir)` must take a bare directory (the control at `:463` passes `tmp/hooks15`), so the one thing it does is prefix the imported hooks root; it holds no literal path, pattern, `_` test or `gate-launch.py` test. That join is the only rule-shaped step left in the test, and it is acceptable because the root it joins is the script's constant, so a changed root changes both consumers. `count_oracles` keeps the six README-only measures, which do not move. So no test body changes except the three V3 pins (Extension Point 5): the controls at `:463` and `:660` run unchanged and pass. The helper bodies that change are `hook_file_count`, the skills, agents and hooks entries of `count_oracles`, the imports and the removed constants. **Behaviour differences, all zero on today's tree (V9).** D1, D3 and D4 live in the two listings, not in the rule, so their rows test a listing (block 1 step (1)); D2 lives in the rule. (D1) `tree_paths` lists HEAD's tracked files, while the test lists the working tree, so an untracked or ignored skill, agent or hook counts locally but not in `--counts` (a CI checkout has neither, so CI agrees). (D2) The rule is case-sensitive, while the old glob was case-insensitive on Windows, so a `skill.md` or `X.PY` on Windows stops counting. (D3) git lists a symlink (mode 120000) as a path, while the disk wrapper keeps `is_file()`, so a symlink to a directory named `x.py` counts in git only. (D4) Removed by `-z`: without it git would quote a path holding a non-ASCII byte, `"` or `\` (V17), so the rule would miss it and the landing would write a count one lower than the pin's. `-z` is chosen over `-c core.quotePath=false` because `quotePath=false` still quotes `"`, `\` and control characters; raw-byte decoding is chosen over `_git` because the locale code page can fail or alter a UTF-8 name.
- **I-2 Numbers only.** The refresh changes only the number characters of a claim inside a description value. Every other byte of every manifest is unchanged; the file is edited as text, never re-serialised. A digit count is written in digits; a spelled count as the word for the new value (`count-unwritable` outside one to twenty).
- **I-3 All or nothing.** `--raise --manifest-counts` plans the version change and the count rewrites together. On any Count refusal it writes nothing, commits nothing and exits per I-4's mapping (1 for a `description` refusal, 2 for a `read` refusal), printing `VERSION BUMP: count refresh refused (<reason>): <manifest>: <detail>`. Otherwise one commit holds both. The message stays "chore: raise the plugin version to X at the landing" when no count changed, becomes "... to X and refresh the manifest counts at the landing" when both changed, and "chore: refresh the manifest counts at the landing" when only counts changed. A second run changes nothing.
- **I-4 One Count verdict, three readers of it.** The full pin, the new mode `--counts`, and `--exact --manifest-counts` all assert the Count verdict: equality, noun presence, and an empty refusal list. One exit mapping serves all three and `--raise --manifest-counts`, matching the script's existing meaning (1 = the check failed, 2 = it could not run): **0** the verdict holds; **1** an equality or noun failure, or a `description` refusal; **2** a `read` refusal or an unreadable manifest. `--counts` reads HEAD's manifests and HEAD's tree only; it reads no version, no `--base` and no origin ref, and writes nothing. `--exact --manifest-counts` runs the exact version check, then the Count verdict, prints both, and exits with the higher of the two codes (2 over 1 over 0). It is used only after a raise (P7b, the manual landing). P7b treats any non-zero exit as `version-raise-failed` (V15).
- **I-5 Opt-in, and no exact check as a step.** Without `--manifest-counts` or `--counts`, every existing mode behaves byte for byte as today, so the count-free fixtures (V8) are untouched. `--counts` joins the mutually exclusive mode group. `--manifest-counts` is refused, exit 2, with any mode other than `--raise` or `--exact`. The landing passes it only when `contractLanding.manifestCounts is True` in the conventions it already reads at `origin/<default>`; the key has no effect without `versionRaise`. No configured verification step may run `--exact` or `--raise` (V11).
- **I-6 The deferral rule, built on the parent predicate.** A new public `is_non_default_base(base_ref, default_ref)` holds the one base comparison (`base_ref != default_ref`; an absent base is not the default, as today). `is_parent_mode` and `main:179` call it, unchanged in behaviour. `count_pin_deferred(head_ref, base_ref, default_ref)` is exactly `default_known and (is_parent_mode(head_ref, base_ref, default_ref) or (base_ref is not None and is_non_default_base(base_ref, default_ref)))`, where `default_known` is "`default_ref` is not None and is not empty after stripping whitespace". The guard lives in this predicate and nowhere else: without it, `is_parent_mode(task head, None, "")` is True (`None != ""`, `check_version_bump.py:133-135`) and any named base differs from `""`. `is_parent_mode` gains no guard, because its caller `main` already refuses an empty default with exit 2 (`:159-162`); the pin context resolver adds none either, it only reports the empty value in the I-7 line. It spells neither `TASK_HEAD` nor the comparison. The test passes all three values in one form, bare branch names. Under deferral, the equality assertions of V3 are replaced by "the refresh plan has no refusal"; noun presence is still asserted.
- **I-7 Strict when in doubt, and never silent.** Source `none` gives the full pin (the test does not call the predicate). An empty or blank default branch gives the full pin through I-6's guard, whatever the source. Neither ever defers. A pull request into the default branch is never deferred. Every run of the pin prints one line, `manifest count pin: <deferred|full> (source <s>, head <h>, base <b>, default <d>)`, so a stale variable cannot defer the pin unseen.
- **I-8 The vendored set is unchanged.** `check_version_bump.py` gains no import beyond the standard library, so `VENDORED_FILES` stays seven files (journal 2026-11-09).
- **I-9 Derived description lines at R-3.** When `manifestCounts` is on, `merge_version_fields` also accepts a region whose two sides, after the version lines are dropped, differ only in the numbers of count claims on `"description"` lines. It takes the default branch's side, and P7b rewrites those numbers. With the key off, today's rule holds.
- **I-10 This contract's own landing is the old landing.** The landing reads its conventions at `origin/<default>` (V15). Master gains `manifestCounts` and the `manifest-counts` step only when this contract lands, so this landing runs plain `--raise` / `--exact`, no `manifest-counts` P8 step, and I-9 off. It stays green only because neither block adds, renames or deletes a file under `skills/`, `agents/` or `.claude/hooks/`, so master's counts (V9) stay true through it. Block 1's CONSTRAINTS say so. The landing pull request's CI `tests` job runs the merged tree's new full pin (equality plus an empty refusal list), so the new pin judges this landing even though the new landing steps do not. The first landing that runs the refresh is the next contract's.

### Events

Not applicable. Reason: there is no listener. The refresh is one git commit, which P8 already measures as the landing's own paths (V5).

### Commands (if any)

| Name (imperative) | Handler | Payload | Possible rejections |
|-------------------|---------|---------|---------------------|
| Raise and refresh | `check_version_bump.py --raise --manifest-counts --default-branch <b>` (P7b, or the operator) | origin/`<b>` manifests, HEAD tree, the four manifests | exit 1 on a `description` refusal; 2 on a `read` refusal or an unreadable default branch; nothing written |
| Check exact version and counts | `check_version_bump.py --exact --manifest-counts --default-branch <b>` (P7b after the raise, the operator) | HEAD manifests, HEAD tree, origin/`<b>` | the higher of the version exit and the count exit (I-4) |
| Check counts | `check_version_bump.py --counts` (the P8 step `manifest-counts`, baseline recording, anyone) | HEAD manifests, HEAD tree | exit 1 on a failed Count verdict, 2 on a `read` refusal (I-4) |
| Judge the pin | `test_repo_consistency.py` (CI `tests` job, or a local run) | Pin context | none: deferred or full, per I-6 and I-7 |

---

## Reused Mechanisms

- **Plugin version check modes** (`MECHANISMS.md:95-96`) — **extended** per its Extend-by: one mode branch `--counts`, one modifier `--manifest-counts` on `--raise` / `--exact`, and `count_pin_deferred`, which calls `is_parent_mode` per the 2026-11-10 extension. The base comparison moves into `is_non_default_base`, called by both. `MANIFESTS` stays the one list of version files.
- **The count-claim reader** (block 9 of `2026-11-11-audit-followups-165`, in `test_repo_consistency.py`) — **moved** without change into the shipped script and imported back (I-1). It has no registry entry today; Extension Point 7 records it under Plugin version check modes.
- **The contract landing** (`land_contract.py` P7b, R-3, P8 steps, `--record-baseline`) — **extended**. P7b passes the flag from config (I-5); `merge_version_fields` gains I-9; P8 gains one step. The halt stays `version-raise-failed`, its detail carrying the refusal reason. It has no registry entry today; Extension Point 7 registers it, with the rule V11 proves.
- **Persistence check:** not applicable. There is no database. The only store is one git commit on the parent branch, already attributed to the landing (`land_contract.py:2356-2357`).

---

## New Mechanisms (if any)

None. Every piece extends the mechanisms above. The "Contract landing" registry entry records existing code, not new machinery.

---

## Extension Points

1. `check_version_bump.py`: the moved reader (I-1); `MANIFEST_COUNT_NOUNS` beside `MANIFESTS`; a pure refresh planner and Count verdict over (manifest texts, measures, noun table); `--counts` in the mode group and `--manifest-counts` for `--raise` (I-3) and `--exact` (I-4); the measure roots and `tree_paths(cwd)` (`git ls-tree -r -z --name-only HEAD`, raw bytes, I-1 D4); `is_non_default_base` and `count_pin_deferred` with its empty-default guard (I-6), with `is_parent_mode` and `main:179` calling the former. Docstring and exit-code text updated.
2. `land_contract.py`: `_p7b_version_raise(wt, default, counts)` appends `--manifest-counts` to both runs when `config.get("manifestCounts") is True`. `merge_version_fields` gets a `counts_derived` parameter from the same key at the `version-fields` call site (`:2627`) and masks claims with the shared reader (I-9). P7b and R-3 docstrings updated.
3. `.claude/work-item-conventions.json`: `contractLanding.manifestCounts: true`. The step `{"id": "manifest-counts", "command": ["py", "-3", ".claude/scripts/check_version_bump.py", "--counts"], "results": {"format": "exit-code"}, "measured_minutes": <measured>, "timeout_minutes": 5}` goes second. The `$comment` gains one sentence on each, and one sentence that a step must pass on the default branch because baseline recording runs it there.
4. `.github/workflows/version-bump.yml`: the `tests` step that runs `test_repo_consistency.py` gets `env:` with `MANIFEST_PIN_BASE_REF: ${{ github.base_ref }}`, `MANIFEST_PIN_HEAD_REF: ${{ github.head_ref }}`, `MANIFEST_PIN_DEFAULT_BRANCH: ${{ github.event.repository.default_branch }}`. Nothing is interpolated in `run:`.
5. `test_repo_consistency.py`: the `sys.path` entry of I-1, the imports, and its copies dropped. The three V3 pins apply I-4, I-6 and I-7; the full pin gains the refusal assertion. `MANIFEST_REMEDY` drops exits (i) and (ii) and says "into the default branch, correct the numbers in this pull request; on a parent branch, the landing refreshes them", citing this contract. A wiring check asserts the three `env:` names. Docstring section (5) updated.
6. `CLAUDE.md` line 16: one sentence on the Landing count refresh. The two manual commands gain `--manifest-counts`. The strings `--raise` and `--exact` stay (`test_parent_branch_rule_text.py:330-331`).
7. The registries (block 1): append the two VOCABULARY terms. Under **Plugin version check modes** append: "**Extension (2026-11-14, issue #405):** `--counts` checks the skill, agent and hook counts of the manifest descriptions against HEAD's tree (no version read, safe on the default branch); `--manifest-counts` on `--raise` / `--exact` refreshes and checks them (numbers only, all or nothing, named Count refusals). The Count-claim reader moved here from `test_repo_consistency.py`, which imports it; extend it here, never in a test. `tree_paths` lists HEAD with `git ls-tree -r -z` read as raw bytes, never through `_git`, so no path is quoted or re-encoded. `is_non_default_base` is the one base comparison; `count_pin_deferred` (built on `is_parent_mode`, and False whenever the default branch is empty) defers the manifest pin on a pull request into a non-default base. Switch: `contractLanding.manifestCounts`. Contract: `.claude/concepts/2026-11-14-manifest-counts-landing-refresh.md`." Append a new Universal entry: "- **Contract landing** *(registered 2026-11-14, issue #405)* — `.claude/scripts/land_contract.py` lands a parent-branch contract. P7b (`_p7b_version_raise`) runs the lander's own `check_version_bump.py --raise` then `--exact`, adding `--manifest-counts` when `contractLanding.manifestCounts` is true. R-3 (`merge_version_fields`) accepts a conflict region that differs only in `"version"` lines, and with `manifestCounts` on also in count numbers on `"description"` lines. P8 runs `contractLanding.verification.steps` in the landing checkout and merges nothing unless every step exits 0. `--record-baseline` runs every step twice on a default-branch checkout and refuses on any `exit-code` step that is not 0, so every configured step must pass on the default branch: never `--exact` or `--raise` (pinned by `test_land_contract_verification.py`). Extend by: a new check is one step entry with its measured minutes, plus the step list in that test. Contract: `.claude/concepts/2026-11-14-manifest-counts-landing-refresh.md`."
8. The follow-up stub this contract delivers (block 1), promoted the template's way in the house form (V18): rename `.claude/concepts/followups/2026-11-13-manifest-counts-under-parent-branch.followup.md` to `…-parent-branch.followup.superseded.md` with `git mv`, set `**Status:** superseded`, and add directly under it a line reading `**Superseded by:**`, then this contract's path in backticks, then `(issue #405)`. No other byte changes. `list_contracts.py` then lists it as superseded and `archive_stale_stubs.py` no longer collects it (V18). The old path stays cited in history only (the 2026-11-13 contract and this contract's brief), as for the nine stubs already superseded; after Extension Point 5 no test cites it (today only `MANIFEST_REMEDY`, `test_repo_consistency.py:680`).

---

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| `land_contract.py` P7b | `check_version_bump.py` | subprocess, exit code and stdout | flag set, Count refusal message | landing → script |
| `land_contract.py` P8 and `--record-baseline` | `check_version_bump.py` (merged tree copy) | verification step `manifest-counts` (`--counts`) | exit code | landing → script |
| `land_contract.py` R-3 | `check_version_bump.py` | import | shared claim reader | import |
| `test_repo_consistency.py` | `check_version_bump.py` | import | measures, readers, noun tables, Count verdict, `count_pin_deferred` | import |
| `version-bump.yml` `tests` job | `test_repo_consistency.py` | `env:` | Pin context | CI → test |

**Changes to existing integration surfaces:**
- [ ] P7b arguments: `land_contract.py` ↔ `check_version_bump.py` (both in block 1)
- [ ] Pin context: `version-bump.yml` ↔ `test_repo_consistency.py` (both in block 1)
- [ ] The moved reader: `check_version_bump.py` ↔ `test_repo_consistency.py` (both in block 1)

---

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold. `.claude/area-mapping.json` holds no areas (`"areas": {}`), so the scanner has nothing to score. The data-architect has no shell; block 1's Run-first runs the scan and records it.

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

---

## Non-Goals

- Number-free descriptions (design (b), declined by the owner on 2026-11-13).
- Changing which counts the descriptions carry, or any other manifest text. No manifest is edited by this contract; its version is raised by its own landing.
- README count pins (`ReadmeCountPinTests`, the README hook and registration tests): a sub-task may edit the README, so they keep full mode everywhere.
- A new landing outcome. A refusal reuses `version-raise-failed`.
- `pr_merged.py`, the `sub-task-raises-version` rule, and the behaviour of the version-bump job's modes.
- The two known failures in `test_land_contract_verification.py` (V14). They fail before and after this contract, which does not touch them.
- Running the refresh at this contract's own landing (I-10).

---

## Confidence

Confidence: Medium. High on the data shapes and the P7b, R-3, baseline and pin facts (each read in this worktree), and on V14 (run by the main session). Medium on how the landing is launched for an in-flight branch (U-1) and which branches are in flight (U-2); both are measured by block 1's Run-first.

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** a flag-gated refresh inside `--raise` / `--exact`, a version-free `--counts` mode as the P8 step, refreshability in the full pin, Count deferral built on `is_parent_mode`, and I-9 at R-3.
  - Why: every route stays green with no owner exit, the step passes on the default branch, and no module joins the vendored set.
- **Option B (rejected):** the refresh alone, with the pin unchanged. A sub-task that adds a skill still turns `tests` red; exit (ii) survives.
- **Option C (rejected):** pin parent-mode descriptions to the merge-base tree's counts. Needs full history and git in the test, and catches nothing, since a sub-task cannot edit a manifest (V10).
- **Option D (rejected):** a new shipped module for the reader. The vendored set would grow (journal 2026-11-09).
- **Option E (rejected):** refresh whenever `versionRaise` is on. Every count-free fixture (V8) would halt with `count-missing`.
- **Option F (rejected):** the refresh inside `land_contract.py`. The `landing: manual` operator would lose it.
- **Option G (rejected):** the P8 step runs `--exact --manifest-counts`, or a step excluded from baseline recording. The first is red on the default branch (V11); the second needs a new exclusion rule in `run_recording` for a check that has no reason to read the version.

---

## Uncertain Assumptions

- `ASSUMED` U-1: an in-flight parent branch may be landed by a lander copy older than this change, because the lookup takes the session checkout's `.claude/scripts/land_contract.py` first (`skills/advance/SKILL.md:378-379`). An old P7b passes no flag. Mitigation: the P8 `--counts` step runs the merged tree's script and halts before any merge.
- `ASSUMED` U-2: which remote branches are in flight with a skill, agent or hook added or removed. Verification path: block 1's Run-first, output pasted. Reported, not a stop.
- `ASSUMED` U-3: GitHub fills `github.base_ref` and `github.head_ref` for `pull_request` events, as the `version-bump` job already relies on (`version-bump.yml:18-22`). Verification path: the sub-task pull request's `tests` log shows the I-7 line with `deferred (source env`.
- `ASSUMED` U-4: today's manifest descriptions give an empty refusal list. Verification path: block 1's full pin run with the refusal assertion, on this branch, whose manifests equal master's.
- `ASSUMED` U-5: git for Windows refuses a path holding `\` in the index, and an unprivileged Windows session refuses `os.symlink`, so the D4 backslash row and the D3 disk row may skip there; CI (Linux) runs both. Verification path: block 1's pasted run names each skip and its reason; block 2 (a) reports it.
- `VERIFIED via the code read in V1 to V13 and V15 to V18`: every file and line cited.
- `VERIFIED via derive_subtask_id` (`pr_merged.py:266-274`): the headings give `t1-count-refresh-at-the-landing` and `t2-review`.

**A branch in flight on the day this ships.** It takes the default branch in through a sync sub-task (journal 2026-11-07) before its next sub-task pull request and its landing. The sync sub-task is a `task/*` head into the parent branch, so its own `tests` run is deferred, and so are later ones. Its landing refreshes the counts: P7b does it when the lander is current; otherwise the P8 step halts the landing and the relaunch from the synced checkout refreshes them. No recount pull request is needed.

---

## Failure Modes & Mitigations

- **FM:** The refresh and the pin read a description differently. **Mitigation:** I-1 and the one Count verdict (I-4).
- **FM:** The count-free fixtures, or a consumer's manifests, halt the raise. **Mitigation:** I-5 opt-in; `RaiseTests`, `ExactModeTests` and `TestP7bVersionRaise` run unchanged.
- **FM:** A vendored copy breaks on a new import. **Mitigation:** I-8, with `test_check_hook_registrations.py` in the Run list.
- **FM:** The deferral switches the pin off into master, or a stale shell variable defers it. **Mitigation:** I-6, I-7 (all three variables or none; the printed line), a positive control row for base equal to default, a row for one variable set alone, and the env wiring check.
- **FM:** A configured step is red on the default branch, so `--record-baseline` breaks. **Mitigation:** the step is `--counts` (V11, I-5), a `run_recording` row, and a check that no step's command holds `--exact` or `--raise`.
- **FM:** The counts on master drift (a pull request merged with `tests` red, or a direct push), so `--counts` is red on the default branch. **Effect:** `--record-baseline` refuses with `environment-failure`, naming the step `manifest-counts`, until master is fixed. A landing with a current lander is not blocked, because P7b refreshes the counts from the merged tree before P8 runs. A landing by an old lander (U-1) halts at P8. **What the owner does:** merge one single-block pull request into master that corrects the numbers (a single block may list the manifests; its full pin proves the fix), then re-run `--record-baseline` or relaunch the landing. The red `tests` job on master is the early signal, and `MANIFEST_REMEDY` names this fix.
- **FM:** A transient git failure reads as zero skills. **Mitigation:** `oracle-unreadable` and `oracle-empty` exit 2 and write nothing.
- **FM:** The refresh rewrites other text or reorders the JSON. **Mitigation:** I-2, with a byte comparison of every byte outside the number spans.
- **FM:** A re-run of the landing hits a description conflict at P7. **Mitigation:** I-9, with rows in `test_land_contract_conflicts.py`; with the key off, today's halt is kept.
- **FM:** A refusal halts a landing. **Mitigation:** the halt names the reason and the manifest. Master's full pin asserts an empty refusal list (I-4), so a description master accepts is always refreshable as written. The refusals a landing can still meet are only those caused by the tree moving since master: `count-unwritable` (a spelled count pushed outside one to twenty), `oracle-empty` and `oracle-unreadable`. Each is a named halt, fixed by an ordinary pull request into master (respelling the count in digits), then a sync sub-task.
- **FM:** The `landing: manual` operator forgets the flag. **Mitigation:** `CLAUDE.md` names it; the landing pull request's full pin is red before merge.
- **FM:** A test asserts the old commit message. **Mitigation:** I-3 keeps it when no count changed.
- **FM:** This contract's own landing adds a counted file and lands untrue counts, because the new steps are not yet on master. **Mitigation:** I-10, and block 1's constraint against touching `skills/`, `agents/` or `.claude/hooks/`.
- **FM:** The moved rule counts differently from the disk glob. **Mitigation:** I-1 lists D1 to D4, each with a row that fails if its listing changes (block 1 step (1)) and a mutation in block 2 (k); the controls at `:463` and `:660` run unchanged.

---

## Open Questions for User

- [x] **Q1 Delivery: two blocks or one?** — Two blocks, implementation plus a fullstack-code-reviewer gate, on a parent branch for #405 (owner, 2026-11-14).
- [x] **Q2 Deferral scope?** — Every pull request into a non-default base, realised by I-6 (owner, 2026-11-14).
- [x] **Q3 A P8 `manifest-counts` step?** — Yes; it runs `--counts`, which passes on the default branch (owner, 2026-11-14).
- [x] **Q4 A landing rehearsal in block 2?** — Allowed, with the critic's fixes: it checks only the version-bump and manifest-counts steps, cleans up on failure, uses a unique temp path, and is valid only for the master commit it merged (owner, 2026-11-14; block 2 (l)).
- [x] **Q5 The two failures in `test_land_contract_verification.py` (V14)?** — Name them as known failures, failing before and after with every other test passing; fixing them is out of scope and their rows are not altered (owner, 2026-11-14).
- [x] **Q6 Moving the superseded critique rounds out of the contract?** — Yes. Rounds 1 and 2 were moved word for word to `.claude/contract-history/2026-11-14-manifest-counts-landing-refresh.round-1.md` and `.round-2.md`, with a pointer left in `## Critique` (owner, 2026-11-14).

---

## Critique

**Earlier rounds:** round 1 (verdict blockers-found) is in `.claude/contract-history/2026-11-14-manifest-counts-landing-refresh.round-1.md` and round 2 (verdict blockers-found) in `.claude/contract-history/2026-11-14-manifest-counts-landing-refresh.round-2.md`. Both were moved word for word. Every finding in them is answered in the body below; the owner chose to address all of them (2026-11-14).

**Owner responses (2026-11-14):** the owner chose to address every finding of all three passes and to approve without a fourth review (no blocker was open after the third pass).
- Second-pass BLOCKER (two existing tests already fail) → Addressed by: named as known failures in block 1, block 2, the constraints and the non-goals (Q5).
- Third-pass WARN (empty default branch), WARN (D1/D3 rows cannot fail), WARN (D4 git quoting), WARN (stub promotion status) → Addressed by: the predicate guard in I-6, listing-level rows for D1/D3/D4 with `tree_paths`, and the rename to `.followup.superseded.md` with a `Superseded by:` line; the third-pass NITs are also addressed.

### Third pass (2026-11-14)

**Critic:** contract-critic
**Date:** 2026-11-14
**Verdict:** warnings-only

The second-pass BLOCKER is resolved. Block 1 records a known-failure baseline before any change (exit 1, 79 tests, exactly the two V14 rows). It keeps `test_land_contract_verification` out of the "all exit 0" list and names it under "Known failures" with "79 plus the rows step (4) adds". Block 2 inherits the same rule, the CONSTRAINTS forbid touching the two rows, and the Non-Goals exclude fixing them. Adding `manifest-counts` second leaves `hook-tests` last, so the generated-drift message is unchanged (`test_land_contract_verification.py:498-508`). The remaining second-pass WARNs and NITs are answered in the body. The findings below are new or still open.

#### Findings

- **[WARN] Step (1)'s D1 and D3 rows "over a path list" cannot show the difference they name**
  - **What is wrong:** D1 (HEAD's tracked files against the working tree) and D3 (`is_file()` in the disk wrapper against a git symlink path) are differences in the listing, not in the rule. The same path list gives the same count from both consumers, so a rule-only row "over a path list (the rule never reads disk)" passes whether the difference exists or not. Only D2 (case sensitivity) is a property of the rule. Block 2 (a) only checks "the D1 to D3 rows exist", so no reviewer step catches this.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-07 "Adapters that rebuild an old reader over a stricter grammar must list every behaviour difference" (listing a difference is not proving it). The listing sources are cited at `test_repo_consistency.py:94-97, 512-513`.
  - **Where in this contract:** `## Implementation Handoff` block 1 step (1): "one row per behaviour difference D1 to D3 of I-1 over a path list (the rule never reads disk)"; block 2 (a) "the D1 to D3 rows exist".
- **[WARN] A fourth behaviour difference is missing: `git ls-tree -r --name-only` quotes unusual paths**
  - **What is wrong:** without `-z`, git quotes a path that holds a non-ASCII byte, a `"` or a `\` (default `core.quotePath`) as `"skills/caf\303\251/SKILL.md"`. That string does not match `skills/<one segment>/SKILL.md`. Such a skill, agent or hook counts in the disk wrapper but not in `--counts` or P7b, so the landing would write a count one lower than the pin's. The listing command is fixed verbatim in the Value Objects row and Extension Point 1, and I-1 says D1 to D3 is the whole list of differences.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-07 "Adapters that rebuild an old reader over a stricter grammar must list every behaviour difference".
  - **Where in this contract:** `## Data Shapes` Value Objects, Count measure: "The script builds the list from `git ls-tree -r --name-only HEAD`"; I-1 "Behaviour differences, all zero on today's tree (V9): (D1) … (D2) … (D3) …".
- **[WARN] I-6 defines `count_pin_deferred` "exactly" by a formula that defers on an empty default branch, but I-7 and the route table say that case gives the full pin**
  - **What is wrong:** `is_parent_mode(head, None, "")` is True for a task head (`None != ""`, `check_version_bump.py:133-135`), and `base is not None and base != ""` is True for any named base. So the I-6 formula returns deferred where I-7 promises "an empty default branch gives the full pin, never the deferral". The guard has to live in the context resolver, as the script's own empty-default refusal lives in `main` (`:159-162`) and not in the predicate. The contract never says where it lives, so the route row "empty default branch -> full" can be written against `count_pin_deferred` and fail, or against the resolver and leave the predicate unguarded.
  - **Prior artifact ignored:** `MECHANISMS.md:96` (Plugin version check modes, Extension 2026-11-10: a second consumer reuses the predicate, so its edge cases come with it). Also `JOURNAL.md` 2026-11-06 "An exception sentence that names the outcome of a later call must list every outcome that call can have".
  - **Where in this contract:** `## Data Shapes` I-6 "`count_pin_deferred(head_ref, base_ref, default_ref)` is exactly `is_parent_mode(...) or (base_ref is not None and is_non_default_base(...))`"; I-7 "Source `none`, or an empty default branch, gives the full pin"; block 1 step (5) "empty default branch -> full".
- **[WARN] The stub promotion in Extension Point 8 invents a status that the stub lifecycle tooling does not know, and skips the documented promotion**
  - **What is wrong:** the stub template says a promoted stub is renamed to `.followup.superseded.md` and gains a `Superseded by:` line at the top (`.claude/templates/followup-stub.md:44`). `list_contracts.py` recognises exactly that name (`:183-184`) and has no `promoted` entry in `STATUS_ORDER` or `STATUS_ICONS` (`:57-77`). It would therefore list the stub as `[?]` and sort it last, with no "superseded by" pointer. The value `promoted` keeps `archive_stale_stubs.py` from reaping the stub (`:17-18`) only through that script's defensive fallback, not through a supported lifecycle state.
  - **Prior artifact ignored:** `.claude/templates/followup-stub.md:44`; `.claude/scripts/list_contracts.py:57-77, 183-184`.
  - **Where in this contract:** `## Extension Points` 8 "set `**Status:** promoted` and add, under it, `**Promoted to:** …`"; block 2 (m) "The follow-up stub reads "**Status:** promoted"".
- **[NIT] The rehearsal never runs a count rewrite** — under I-10 the parent adds no counted file, and master's full pin keeps master's counts true. So in (l), `--raise --manifest-counts` always writes zero count rewrites and exercises only the "raise … at the landing" message path. Its own landing also runs plain `--raise` / `--exact` (I-10). "Checks ONLY the shipped script's raise-and-refresh" therefore overstates what it covers. The rewrite path rests only on the step (2) and (3) fixtures. Likewise, "run twice, as baseline recording does" runs on a raised merge tree, not on a default-branch checkout.
- **[NIT] The hook wrapper has to rebuild the `.claude/hooks/` prefix itself** — the control at `test_repo_consistency.py:463` passes a bare temporary directory (`tmp/hooks15`), so `hook_file_count(hooks_dir)` can only produce "repository-relative paths" by adding `.claude/hooks/` itself. That is part of the path rule held in the test, against I-1 "Neither holds a pattern".
- **[NIT] Still open: the budget** — the contract is about 28,500 tokens against `**Budget:** 12,000 tokens`. Even with the first two critique rounds moved out (Q6), the body alone is well over budget (`.claude/templates/concept-contract.md:22`). Q6 covers the round move only.

#### Checked against the tree, no finding

- I-10: neither block's `Files to touch` names a path under `skills/`, `agents/` or `.claude/hooks/`. P7b today passes only `--raise` / `--exact` (`land_contract.py:3140-3143`) and gates on `versionRaise` (`:2342`). No configured step runs `test_repo_consistency.py` (`work-item-conventions.json:92-124`). On a `pull_request` event the CI `tests` job runs the workflow from the merge commit, so the new env wiring and full pin judge the landing pull request.
- Exit mapping: I-3, I-4, the Commands table, the Failure Modes (`oracle-*` exit 2) and step (2) agree, and they match the script's existing meaning (1 = failed, 2 = could not run, `check_version_bump.py:12-14`).
- Rehearsal mechanics: `@()` runs the configured `version-bump` command (`work-item-conventions.json:95`, default `--base origin/master`, `check_version_bump.py:151`), which exits 0 after the raise. It uses a unique temp path, cleanup is in `finally`, and it records its master commit.
- Thin wrappers: the controls at `:463` and `:660` keep their call shapes. No other test module imports from `test_repo_consistency.py`. `land_contract.py` already imports from `check_version_bump` (`:65`), and `VENDORED_FILES` is unchanged (`check_hook_registrations.py:38-46`).
- D2 is real: `Path.glob` matches case-insensitively on Windows. D3 is real: `is_file()` follows a symlink, so a symlink to a directory is excluded on disk.
- No hidden Open Question tells in the body. Q6 is hoisted correctly.

#### Applicable journal entries

- **2026-11-07 — Adapters that rebuild an old reader over a stricter grammar must list every behaviour difference** — violated, see the first two WARNs (D1/D3 untested, D4 missing).
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have** — violated, see the third WARN (empty default).
- **2026-11-07 — A merge block's pull request must paste each required output** — heeded: the known-failure baseline and the Run lists give each command its exit code (second-pass BLOCKER resolved).
- **2026-10-30 — A delivery rule must name every route into delivery** — heeded by I-10 and the bootstrap-landing route row.
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded by the master-drift failure mode.
- **2026-11-07 — A clean landing check goes stale when the default branch moves** — heeded by (l), which records `$m`.
- **2026-11-11 — A path-normalisation rule that lists the unsafe forms must also reject absolute paths** — not addressed. The contract did not need to: the paths come from git and from a fixed directory walk, not from an operator.

#### What the critic did not check

- I had no shell, so I ran no suite and no `git ls-tree`. The D4 finding rests on git's documented `core.quotePath` behaviour, not on a run.
- I did not run `pr_merged.py --contract … --status --json` (checklist item 14). Neither block lists a manifest, and the `**Work Item Brief:**` header is present.

---

## Lessons referenced

- **2026-10-30 — A delivery rule must name every route into delivery, not only the one the author had in mind** — heeded by the route table in block 1's TASK: single block into master, sub-task, sync sub-task, this contract's own landing (I-10), later landings, manual landing, hand-named pull request into a non-default base, and baseline recording. Each has its enforcement point and a test row.
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — heeded by "A branch in flight on the day this ships" (the sync sub-task).
- **2026-10-30 — Widening a CI trigger changes who the check judges; list every pull request kind the old filter excluded** — heeded by I-6, I-7 and Q2.
- **2026-10-30 — One shared reader must own the filtering, not only the selection** — heeded by I-1 and the one Count verdict (I-4).
- **2026-11-01 — A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for** — heeded by I-4: the full pin now asserts the writer's refusal set, so a form the old pin tolerated cannot reach master.
- **2026-11-02 — A "fails the build" claim must name the workflow that runs the check** — heeded by V4 and Extension Point 4.
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them** — heeded by block 1's CONSTRAINTS and I-1.
- **2026-11-06 — A sub-task that flips the state an earlier sub-task's test pins must re-run that suite** — heeded by the Run list.
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have** — heeded by the Failure Modes refusal sentence, which names the three refusals a landing can still meet, and by I-6, whose formula carries the empty-default guard that I-7 promises.
- **2026-11-07 — A parent branch that shares files with a moving default branch must take the default branch in through a sub-task before its landing** — heeded by the in-flight handling.
- **2026-11-07 — Adapters that rebuild an old reader over a stricter grammar must list every behaviour difference** — heeded by I-1: the rule moves, the listing stays, and D1 to D4 are listed, each tested against the listing or rule it lives in.
- **2026-11-07 — A merge block's pull request must paste each required output** — heeded by the Run lists, which give each command its expected exit code, name the two known failures (V14) and leave out the one step that is red by construction before the raise, with the reason. Prior artifact heeded: `.claude/reviews/2026-11-04-domain-split-registries/t18-review-fullstack-code-reviewer.md:94-98` (N3).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded: each second-pass finding and each owner answer amends I-1, I-3, I-4, I-10, Extension Point 8, the Failure Modes and both blocks.
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded by the master-drift failure mode and the bootstrap-landing failure mode.
- **2026-11-07 — A clean landing check goes stale when the default branch moves; re-run it immediately before launching** — heeded by block 2 (l), which records the master commit it merged and is valid only for that commit.
- **2026-11-09 — A change that adds a module-level import to a vendored script must update the vendored-file list in the same change** — heeded by I-8 and Option D.
- Orthogonal to north-stars: none active (`.claude/north-stars/` is absent).

---

## Implementation Handoff

Two mergeable blocks (Q1), so the Parent Branch Delivery Rule applies. Parent branch `feature/405-landing-time-manifest-count-refresh`, parent issue #405. Block 1's branch is `task/2026-11-14-manifest-counts-landing-refresh/t1-count-refresh-at-the-landing`. Block 2 depends on block 1. Neither block lists a manifest: the landing raises 0.20.4 to 0.21.0. Run every suite with `py -3 -B <path>`.

**Why the `version-bump` step is not run verbatim before the landing.** In default mode it compares against origin/master; shipped files changed and the version is unchanged until the landing raises it, so it exits 1 by construction on a sub-task branch and at the parent tip. Block 1 runs it in parent mode (expected 0); block 2 runs it verbatim in the rehearsal, after the raise (expected 0).

### 1. Count refresh at the landing (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/check_version_bump.py`
- `.claude/scripts/land_contract.py`
- `.claude/work-item-conventions.json`
- `.github/workflows/version-bump.yml`
- `CLAUDE.md`
- `.claude/scripts/tests/test_check_version_bump.py`
- `.claude/scripts/tests/test_repo_consistency.py`
- `.claude/scripts/tests/test_land_contract.py`
- `.claude/scripts/tests/test_land_contract_identity.py`
- `.claude/scripts/tests/test_land_contract_conflicts.py`
- `.claude/scripts/tests/test_land_contract_verification.py`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `.claude/concepts/followups/2026-11-13-manifest-counts-under-parent-branch.followup.md` (renamed away)
- `.claude/concepts/followups/2026-11-13-manifest-counts-under-parent-branch.followup.superseded.md`

**Pre-written TASK block:**
```
TASK: Build the Landing count refresh and the Count deferral, exactly as Data Shapes I-1 to I-10 and
  Extension Points 1 to 8 define them.
  Before any change, run the known-failure baseline (from .claude/scripts/tests) and paste it:
    py -3 -B -m unittest test_land_contract_verification
  Expected: exit 1, "Ran 79 tests", FAILED (failures=2), the two failures being exactly
  RealProjectConfigTests.test_generated_drift_is_the_last_step_and_lists_the_three_sentinel_keys and
  RealProjectConfigTests.test_the_python_scripts_command_prints_per_test_lines_and_a_per_file_line_only_for_a_crash
  (V14). Any other result stops the block.
  Run-first (paste the raw output into the pull request; it is reported, not a stop). In PowerShell:
    git fetch origin --prune
    git for-each-ref --format='%(refname:short)' refs/remotes/origin | Where-Object { $_ -notin 'origin','origin/HEAD','origin/master' } | ForEach-Object { $d = git diff --name-status --diff-filter=AD "origin/master...$_" -- 'skills/*/SKILL.md' 'agents/*.md' '.claude/hooks/*.py'; if ($d) { $_; $d } }
    py -3 .claude/scripts/cross_area_scan.py .claude/concepts/2026-11-14-manifest-counts-landing-refresh.md
  Then, in this order:
  (1) Move the rule and the reader (I-1) and import them back with the named sys.path entry;
      hook_file_count and count_oracles become disk-listing wrappers with unchanged signatures.
      Paste "Ran N tests" for test_repo_consistency.py before and after the move, with no other
      change: N is equal, the suite is green, and the controls at :463 and :660 are unchanged.
      Then add one row per behaviour difference of I-1, each asserting the number on BOTH sides
      so it fails if the listing it names changes. D1, D3 and D4 are listing rows, in a new class
      in test_repo_consistency.py (it already imports the script and holds the disk wrappers),
      each in a temporary git repository:
        D1: one committed skill, one untracked and one ignored skill on disk: the skills measure
            over tree_paths(repo) is 1, count_oracles(repo)["skills"] is 3.
        D3: a mode-120000 entry .claude/hooks/x.py added with git update-index --cacheinfo and
            committed: the hooks measure over tree_paths is 1; on disk, a symlink x.py to a
            directory gives hook_file_count 0 (skipped, with the reason printed, when the OS
            refuses os.symlink).
        D4: skills whose segment holds a non-ASCII letter (on disk) and a " (index only, via
            update-index): tree_paths returns them byte-exact and the rule counts them; a
            segment with \ is added the same way, skipped with the reason printed when git
            refuses the path.
      D2 is a rule row in test_check_version_bump.py: skills/a/skill.md and .claude/hooks/X.PY
      count 0.
  (2) The refresh, the Count verdict and the modes (I-2 to I-5). In test_check_version_bump.py: a
      rewrite per noun (skills, agents, subagents, hooks); a byte comparison outside the number
      spans; the spelled-count form; each Count refusal reason, with no file changed and no commit;
      the three commit messages; idempotence; the I-4 exit mapping under --raise --manifest-counts
      and --counts (1 for each description refusal, 2 for each read refusal) and no write; under
      --exact --manifest-counts every pair of version exit and count exit gives the higher code;
      --manifest-counts refused without --raise or --exact;
      is_non_default_base, and is_parent_mode unchanged over its existing rows; RaiseTests and
      ExactModeTests unchanged and green.
  (3) The landing (Extension Point 2, I-9). In test_land_contract_identity.py: a P7b landing with
      manifestCounts on, whose parent branch added a skill, lands with the refreshed count and
      --exact --manifest-counts at exit 0; the same landing with a refusal halts
      version-raise-failed naming the reason; manifestCounts off leaves the counts alone. In
      test_land_contract_conflicts.py: a version-plus-description region is accepted with the key
      on, refused with the key off, and refused when a non-number word differs.
  (4) Conventions and baseline (Extension Point 3). In test_land_contract.py: run_recording over a
      default-branch fixture whose steps include manifest-counts returns baseline-recorded. In
      test_land_contract_verification.py: the step list gains manifest-counts second, and no
      step's command contains --exact or --raise. Measure "py -3 .claude/scripts/check_version_bump.py
      --counts" once on this branch (it exits 0 here) and record measured_minutes and the date.
  (5) The pin (I-4, I-6, I-7, Extension Points 4 and 5). Route table, one test row each, with its
      enforcement point:
        single block into master (base = default)           -> full pin, refusal asserted (CI tests)
        sub-task, task head into the parent                 -> deferred (CI tests)
        sync sub-task into the parent                       -> deferred (CI tests)
        hand-named head into a non-default base             -> deferred (CI tests)
        this contract's own landing (I-10)                  -> full (CI tests); master's config runs
                                                               plain --raise/--exact and no
                                                               manifest-counts step; true because no
                                                               counted file is touched
        a later landing pull request into master            -> full (CI tests; P7b + P8 made it true)
        manual landing                                      -> full (CI tests; CLAUDE.md commands)
        baseline recording on the default branch            -> --counts exits 0 (row in step (4))
        local run, git source, task head, no base           -> deferred
        local run, git source, other head                   -> full
        one or two MANIFEST_PIN_* variables set             -> full (source none)
        empty or blank default branch, any head and base    -> full: count_pin_deferred
                                                               returns False (I-6 guard),
                                                               asserted on the predicate
                                                               itself, task head and base
                                                               None included
      Show the deferred assertion failing on a description with its noun removed, and the full
      pin failing on a description that says "3 add-ons" and on one that says "14 hook files".
  (6) CLAUDE.md (Extension Point 6), then the registry appends (Extension Point 7), text as written.
  (7) Supersede the follow-up stub with git mv, the Status line and the Superseded by line,
      exactly as Extension Point 8 says. Paste "py -3 .claude/scripts/list_contracts.py" showing
      it as superseded, and "py -3 .claude/scripts/archive_stale_stubs.py" (dry run) not naming it.
  Paste the full pin run twice, with the I-7 line. In PowerShell: first plain on this branch
  (deferred, source git), then with $env:MANIFEST_PIN_BASE_REF='master';
  $env:MANIFEST_PIN_HEAD_REF='feature/x'; $env:MANIFEST_PIN_DEFAULT_BRANCH='master' (full, green:
  this also proves U-4), then Remove-Item Env:MANIFEST_PIN_BASE_REF,Env:MANIFEST_PIN_HEAD_REF,Env:MANIFEST_PIN_DEFAULT_BRANCH.
CONTEXT: concept contract at .claude/concepts/2026-11-14-manifest-counts-landing-refresh.md
FILES: the fifteen above (the stub counts twice: its old path is removed, its new path added)
CONSTRAINTS:
  - Edit no manifest. Never list or touch plugin.json, .claude-plugin/*, .cursor-plugin/plugin.json.
  - Add, rename or delete no file under skills/, agents/ or .claude/hooks/ (I-10): this contract's
    own landing runs master's old steps, so its counts must stay true untouched.
  - check_version_bump.py imports the standard library only (I-8); VENDORED_FILES is unchanged.
  - Tests that may change: the three V3 pins, MANIFEST_REQUIRED_NOUNS (now imported),
    MANIFEST_REMEDY, and the step list at test_land_contract_verification.py:491-494. Helper bodies
    that may change: hook_file_count, the skills, agents and hooks entries of count_oracles, the
    imports and the removed constants (I-1). New rows are added, never edited in: the D1, D3
    and D4 class in test_repo_consistency.py and every row in steps (1) to (5). Do NOT change ReadmeCountPinTests, the README hook and
    registration tests, the existing controls (:463, :660 included), any count-free fixture, or the
    two known-failure rows of V14. Fixing those two is out of scope.
  - Without --manifest-counts or --counts every existing mode is byte for byte unchanged.
  - Every command below must end at its stated exit code; any other result stops the block. Report
    it, never pass it on. If the contract mis-predicts an exit code, stop and ask for an amendment.
  - Run (all exit 0): test_check_version_bump.py, test_repo_consistency.py, test_land_contract.py,
    test_land_contract_identity.py, test_land_contract_conflicts.py,
    test_check_hook_registrations.py, test_plugin_manifests.py,
    test_parent_branch_rule_text.py, test_plugin_text_scans.py, test_pr_merged.py (slow).
    Known failures (exit 1 expected, before and after): from .claude/scripts/tests,
    "py -3 -B -m unittest test_land_contract_verification" fails exactly the two V14 tests, with
    the same messages, and every other test passes (the count is 79 plus the rows step (4) adds).
    A third failure, or either of the two passing, stops the block.
    The landing steps (all exit 0): manifest-counts, loop-script-tests, hook-registration-tests and
    hook-tests, verbatim from .claude/work-item-conventions.json; and the version check in parent
    mode, not verbatim (see the note above this block):
      py -3 .claude/scripts/check_version_bump.py --base origin/feature/405-landing-time-manifest-count-refresh --default-branch master --head-ref task/2026-11-14-manifest-counts-landing-refresh/t1-count-refresh-at-the-landing
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-14-manifest-counts-landing-refresh.md
  contract_status: approved
```

### 2. Review (`fullstack-code-reviewer`)

**Depends on:** 1 — there is nothing to review until block 1 has merged into the parent branch

**Files to touch:**
- `.claude/reviews/2026-11-14-manifest-counts-landing-refresh/t2-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review block 1 against this contract, and write the review artefact.
  Check, each with its own outcome:
  (a) I-1, one rule and one reader: no second copy of a path rule, reader or noun table in the
      test (the wrappers only list disk and join the imported root); the sys.path entry is the
      named one; the controls at :463 and :660 are unchanged. The D1, D3 and D4 rows call
      tree_paths and the disk wrappers, never the rule alone, and assert both sides' numbers;
      the D2 row calls the rule. tree_paths uses -z and reads bytes, not _git (D4). Read each
      row's skip reason in the run output and say whether it skipped on your platform.
  (b) I-2 and I-3: numbers only, all or nothing, the three commit messages.
  (c) I-4 and I-5: one Count verdict used by the full pin, --counts and --exact --manifest-counts;
      the one exit mapping and the higher-code rule; opt-in behaviour without the flags; no step
      runs --exact or --raise.
  (d) I-6 and I-7: count_pin_deferred calls is_parent_mode and is_non_default_base and spells
      neither TASK_HEAD nor the comparison; the empty-default guard is in count_pin_deferred
      and is_parent_mode is unchanged; every route-table row; no deferral into the default
      branch; the printed pin line.
  (e) I-8: the vendored set is unchanged; run test_check_hook_registrations.py.
  (f) I-9 at R-3.
  (g) The P8 step, its test list, and the run_recording row.
  (h) The env wiring in version-bump.yml: the three MANIFEST_PIN_* names, no ${{ }} in run:.
  (i) CLAUDE.md and the registry appends match Extension Points 6 and 7.
  (j) The Run-first output, the known-failure baseline and the two pin runs were pasted.
  (k) RED by mutation. Make count_pin_deferred return True always; then make the refresh write a
      wrong number; then drop the refusal assertion from the full pin; then drop the empty-default
      guard; then make tree_paths list the working tree (D1); then drop is_file() from the
      disk wrappers (D3, where it ran unskipped); then drop -z from tree_paths (D4). Under each
      mutation a named test fails. Revert every mutation afterwards.
  (l) The rehearsal (Q4). It checks ONLY that, on one merged tree, the shipped script accepts
      --raise --manifest-counts and --exact --manifest-counts with an empty refusal list and
      raises the version with the "raise ... at the landing" message, and that the version-bump
      and manifest-counts steps then exit 0. It rewrites no count: under I-10 the parent adds
      no counted file and master's full pin keeps master's counts true, so the plan has zero
      rewrites. The rewrite path, the other two commit messages, the config wiring, I-9 and P8
      step selection rest on the rows of block 1 steps (2) to (4); it does not run
      land_contract.py. It is valid only for the origin/master commit it records:
      if origin/master moves before the landing, it is stale. In PowerShell, from the parent tip:
        git fetch origin
        $m = git rev-parse origin/master; "rehearsal merged origin/master $m"
        $r = Join-Path $env:TEMP ("rehearsal-405-" + [guid]::NewGuid().ToString('N'))
        git worktree add --detach $r origin/feature/405-landing-time-manifest-count-refresh
        if ($LASTEXITCODE -ne 0) { throw "worktree add failed ($LASTEXITCODE)" }
        try {
          Push-Location $r
          git merge --no-edit $m; if ($LASTEXITCODE -ne 0) { throw "merge failed ($LASTEXITCODE)" }
          $runs = @(@('--raise','--manifest-counts','--default-branch','master'),
                    @('--exact','--manifest-counts','--default-branch','master'),
                    @(), @('--counts'), @('--counts'))
          foreach ($a in $runs) {
            py -3 -B .claude/scripts/check_version_bump.py @a
            "exit $LASTEXITCODE for: $($a -join ' ')"
            if ($LASTEXITCODE -ne 0) { throw "rehearsal stopped" }
          }
        } finally {
          Pop-Location
          git worktree remove --force $r
          git worktree prune
        }
      Every run is expected to exit 0. The last three are the version-bump step and the
      manifest-counts step, from the conventions file; the second --counts run shows it wrote
      nothing. This is not baseline recording, which runs on a default-branch checkout; that
      route rests on the run_recording row of block 1 step (4). The
      raise is a local commit in $r; never push from $r. A failure is a finding, and the finally
      block still removes $r.
  (m) The follow-up stub is renamed to ...parent-branch.followup.superseded.md (git shows a
      rename), reads "**Status:** superseded" with the "**Superseded by:**" line under it and no
      other change (Extension Point 8); list_contracts.py lists it as superseded and
      archive_stale_stubs.py (dry run) does not name it. No file under skills/, agents/ or
      .claude/hooks/ changed (I-10).
  Run block 1's Run list at the parent tip, except its parent-mode version line, which (l) replaces.
  The known failures stay exactly the two V14 tests, every other test in that file passing; their
  rows are not altered, and fixing them is out of scope.
CONTEXT: concept contract at .claude/concepts/2026-11-14-manifest-counts-landing-refresh.md
FILES: .claude/reviews/2026-11-14-manifest-counts-landing-refresh/t2-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Write the artefact in the six-section shape the template fixes. The file does NOT exist yet;
    you create it. Nobody pre-created a stub, and you must not treat its absence as anything but
    "this review has not run".
  - Name the commit range you reviewed, base..head.
  - Every item (a) to (m) appears under "## What was checked" with its own outcome.
  - "## Evidence" carries the commands you ran with their exit codes. It is never empty.
  - End the header with the verdict line, alone on its line, exactly one of:
    "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked".
  - Also write the Gate Output, <artefact stem>.gate.json, beside the report in the same diff:
    {"supersedes": [], "checklist": [{"item": "<a Review checklist line, verbatim>", "outcome":
    "met | partly-met | not-met | not-applicable"}]}, listing every Review checklist item.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-14-manifest-counts-landing-refresh.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

`pr_merged.py` fills this list when the contract's work is merged and nothing is pending. Do not tick lines by hand.

- [x] Implementation matches Data Shapes exactly — evidence: .claude/reviews/2026-11-14-manifest-counts-landing-refresh/t2-review-fullstack-code-reviewer.md
- [x] Reused Mechanisms are actually reused (no parallel implementations introduced) — evidence: .claude/reviews/2026-11-14-manifest-counts-landing-refresh/t2-review-fullstack-code-reviewer.md
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md` — not applicable (.claude/reviews/2026-11-14-manifest-counts-landing-refresh/t2-review-fullstack-code-reviewer.md)
- [x] New vocabulary terms promoted to `VOCABULARY.md` — evidence: .claude/reviews/2026-11-14-manifest-counts-landing-refresh/t2-review-fullstack-code-reviewer.md
- [ ] Integration surfaces reflected on both backend and frontend sides — not applicable (.claude/reviews/2026-11-14-manifest-counts-landing-refresh/t2-review-fullstack-code-reviewer.md)
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced — not applicable (.claude/reviews/2026-11-14-manifest-counts-landing-refresh/t2-review-fullstack-code-reviewer.md)
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface) — not applicable (.claude/reviews/2026-11-14-manifest-counts-landing-refresh/t2-review-fullstack-code-reviewer.md)
- [x] `Status` flipped to `implemented`
