## Critique

(Rounds 1 and 2 moved to `.claude/contract-history/2026-10-31-plugin-owns-hook-mechanism-tests.round-<n>.md`.)

**Critic:** contract-critic (round 3)
**Date:** 2026-11-01
**Verdict:** warnings-only

### Round-2 findings, checked against the code

- W1 (empty list, advice true over nothing): resolved. `reasons` route confirmed at `land_contract.py:2556-2564`. The advice fact needs at least one unit and no `reasons`.
- W2 (the `next_command` seam): resolved. The allow-list is at `land_contract.py:1739-1741`. `_Halt.extra` reaches `make_report` through `:1940-1945`. The P8 halt is at `:2197`. Block 3 tests the advice through a real landing.
- W3 (FA-1 against FA-5): resolved by FA-2 (`undetermined` when both diffs change the files).
- W4 (two validators): resolved for the check and the recorder, which share one `load_settings`. `_parse_settings` (`auto_improve_finish_install.py:1286-1309`) stays the reader for `hooks` and `addon`. See NIT 3.
- W5 (issue #148's own case): resolved. The README step passes its files as arguments, so FA-4 reads `outside-diff`.
- W6 (side effects): the facts are now VERIFIED (`:80-83`). The conclusion drawn from them is wrong (WARN 1).
- All five round-2 NITs are resolved: the names are spelled in full, the landing's own paths are a separate side, terms that are not vocabulary are removed, `hook-tests` is handled and block 3 depends on block 1, and the README text names no version.

### Findings

- **[WARN] The import side effect does not stop the checker writing `__pycache__` into a vendored consumer's tree.**
  - **What is wrong:** `sys.dont_write_bytecode = True` runs inside the installer's body (`auto_improve_finish_install.py:80`), and that is after Python has compiled and cached the installer itself. The comment at `:78-79` says the flag only protects the modules imported after it. So `check_hook_registrations.py` run as `py -3 …` (no `-B`, the exact README step) writes `.claude/scripts/__pycache__/auto_improve_finish_install.*.pyc` beside a vendored copy. A consumer that does not ignore `__pycache__` then gets the P8 reason "the steps changed the worktree" (`land_contract.py:2544, 2557-2558`), which is NOT-READY from `reasons`. This repository hides the problem, because `.gitignore` lines 2-3 ignore those files. Block 1's tree-unchanged test passes without testing anything when the checker runs from the plugin folder against a temporary project, because the `.pyc` file lands outside the tree being checked.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04, "Check a documented guard behaviour against the guard's code"; `JOURNAL.md` 2026-10-04, "Detect an install mode by what the sync actually delivers" (the vendored layout is the case that matters).
  - **Where in this contract:** `## Data Shapes → Import side effects`: "suppressing bytecode only means the check writes nothing into a consumer's tree"; block 1: "a check leaves the project tree byte-identical (no __pycache__)".
- **[WARN] The advice fact's own reason applies to every exit-code unit, and every unit in this repository and the README step is exit-code.**
  - **What is wrong:** `reasons` halts are kept out of the advice because "re-recording the baseline cannot fix it". The same is true of an exit-code step: `read_step` never reads the baseline for one (`land_contract.py:857-862`). Recording refuses a step that fails on the default branch (`:998-1003`). `repeat` needs a non-empty `new_failures` (`:1499`), so the advice never escalates to `/design-first`. The command list keeps saying "Re-record the failing-test baseline for <suite ids>" with the placeholder left in (`:1506-1507`). In issue #148's case, the Q1 advice therefore leads to a re-record that cannot change the result.
  - **Prior artifact ignored:** `land_contract.py:857-862, 998-1003, 1499-1507`; `JOURNAL.md` 2026-10-30, "A rule that refuses must give already-delivered work a named way out".
  - **Where in this contract:** `## Data Shapes → The advice fact`: "A `reasons` halt is excluded because re-recording the baseline cannot fix it"; `## Extension Points → The next_command seam`: "The command list is unchanged".
- **[NIT] "The P7b commit's paths" has no fixed starting commit.** `_p7b_version_raise` may commit nothing on a second run (`land_contract.py:2165-2177`), and then `HEAD^..HEAD` is the merge commit. The contract does not say that HEAD must be captured before P7b. After an earlier run pushed at P9, `contract_diff` (`:2404`) also holds that run's version raise and the paths it resolved by hand. The Attribution sides do not describe this rerun case.
- **[NIT] The validator wording does not match the code.** It is not stated whether `load_settings` refuses a group that has no `hooks` key. `_parse_settings` accepts such a group by defaulting it to `[]` (`auto_improve_finish_install.py:1307`), so the `hooks` subcommand and the recorder can disagree about one file. Also, "duplicate keys, down to group level" is inaccurate: `_strict_pairs` checks duplicate keys at every level (`:1280-1290`), and only the shape check stops at group level.
- **[NIT] Block 3's test fixes this repository's live step ids and step count to the conventions file,** and the conventions `$comment` does not name that test. `JOURNAL.md` 2026-10-15, "A skill that edits a block pinned by a lookup-block test must name that test".
- **[NIT] The README says "running exactly" and also "or run from the installed plugin root".** In plugin mode the checker's path is not `.claude/scripts/check_hook_registrations.py`, so both cannot hold.
- **[NIT] The installer runs as `__main__`, so `record-registrations` loads a second copy of `auto_improve_finish_install`** through the checker. The "import each module first in a fresh process" test does not cover that path.
- **[NIT] This repository's `hook-registration-tests` step names only its test file.** A break in `check_hook_registrations.py` itself reads `undetermined`. The README states this limit for the dependency scripts but not for this step.

### Applicable journal entries

- **2026-10-16, "missing project file" refusal:** heeded (`paths-not-given`, `settings-missing`, `hook-registration-profile-missing`).
- **2026-10-15, a script must be told which project:** heeded (explicit paths only).
- **2026-10-04, VERIFIED parser claim:** heeded by `load_settings` and a test for each level. The side-effect conclusion is in WARN 1.
- **2026-10-04, check a documented guard behaviour against its code:** violated in prose only; see WARN 1.
- **2026-10-04, detect install mode by what the sync delivers:** heeded by the five-file set and `checker-dependency-missing`. Its vendored case is in WARN 1.
- **2026-10-05, one named location only:** heeded (project layer only).
- **2026-10-28, do not promote an extension seam:** heeded (Preview-hash apply is extended).
- **2026-10-28, a term true against every member:** heeded (Registration row identity).
- **2026-10-30, a refusal needs a named way out:** heeded for refusals. The way out the advice offers is in WARN 2.
- **2026-10-22, accepted findings amend the body:** heeded.
- **2026-10-04, a root locator under vendoring:** not addressed. The checker never calls `find_plugin_root`, though the import loads it.

### Requested checks

- **Acceptance criteria:**
  1. Met. Block 1 names the five equivalent classes.
  2. Met. HR-1 to HR-5 and exit codes 0, 1 and 2.
  3. Met. Block 5 checks that the checker is the single place, and the README tells a project to delete its copies.
  4. Met. The units, FA-1 to FA-5, the note and the empty-list text.
  5. Met. Q1 is answered in the code and in the README, subject to WARN 2.
  6. Met. Each rule is broken in turn, and the missing, UTF-16, invalid and malformed cases each exit 2.
- **Parent Branch Delivery Rule:**
  - The `**Work Item Brief:**` header is at line 8.
  - The blocks are numbered 1 to 5, with the review as block 5.
  - No Files to touch list names a `MANIFESTS` file (`check_version_bump.py:25-26`). `README.md` is exempt (`:37`).
  - P7b raises the version once.
  - The dependency of block 3 on block 1 holds under parent-branch delivery.
  - I found no layout defect by reading.

### What the critic did not check

- I did not run `pr_merged.py --contract <slug> --status --json`, `derive_area.py` or a budget measurement, because I have no shell. `memory-health.py` is absent. The contract may be near its 12,000-token budget by estimate.
- `INTEGRATION.md`, the registry digest and `.claude/north-stars/` are absent, and there is no project tier, so I applied only the Universal-tier checks.
