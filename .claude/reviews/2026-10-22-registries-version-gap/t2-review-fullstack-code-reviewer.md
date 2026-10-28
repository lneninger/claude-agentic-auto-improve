# Review: Version-bump check treats the doctor's copied registries as shipped (sub-task 1), fullstack-code-reviewer

**Gate agent:** fullstack-code-reviewer
**Sub-task reviewed:** 1, version check (gate t2)
**Contract:** `.claude/concepts/2026-10-22-registries-version-gap.md` (approved)
**Reviewed on:** 2026-10-22
**Commit range reviewed:** `origin/master..working-tree`. `origin/master` and `HEAD` are both `9ef9893`. The work is uncommitted on branch `fix/77-registries-version-gap`. I reviewed `git diff origin/master` (7 tracked files modified, 43 insertions, 8 deletions) and `git status` (untracked: the contract, the work item and this review folder).
**Verdict:** pass-with-findings

## What was checked

- **The three copied registries classify as shipped. No other exempt entry changed. `check_version_bump.py` does not import `plugin_doctor`, and `evaluate`, `versions_in` and `main` are untouched.** Met.
  - The only hunk in `check_version_bump.py` (lines 16-24) removes `".claude/registries/"` from `EXEMPT_PREFIXES` and adds the two-line comment the contract asks for. The other six prefixes and `EXEMPT_NAMES` are byte-identical.
  - The script still imports only `argparse`, `json`, `subprocess`, `sys` and `typing` (lines 9-15). `plugin_doctor` is not imported.
  - No `def` line is added or removed in the diff, and the hunk ends before `is_shipped`. So `is_shipped`, `evaluate`, `versions_in` and `main` are unchanged.
  - `.claude/registries/` holds only the three copied files (Glob), so no non-copied file became shipped by accident.
  - `plugin_doctor.py` is unchanged from master (`git diff --quiet` exit 0).
- **The new tests in `test_check_version_bump.py`.** Met, with two nits (F1, F2).
  - *They derive the copy list from `plugin_doctor.REQUIREMENTS`.* `test_every_file_plugin_doctor_copies_into_projects_counts_as_shipped` builds `sources` from every requirement with a non-empty `source`, and asserts that none is non-shipped. The failure message lists the offending paths. It goes through the suite's existing `sys.path.insert`.
  - *They cannot pass vacuously.* The same test asserts that the template, the three registries and `.claude/project-profile.md` are among the sources. I probed it by setting `plugin_doctor.REQUIREMENTS = []` before the test ran. It failed with "'.claude/templates/concept-contract.md' not found in []" (exit 1). A renamed `source` attribute raises `AttributeError`, which is an error, not a pass.
  - *The bare-path rule.* `test_files_under_exempt_folders_are_not_shipped_but_orchestrator_state_is` asserts only on files under each folder (`.claude/concepts/x.md`, `.claude/work-items/x.md`, `.claude/north-stars/x.md`, `.claude/orchestrator/results/x/y.yaml`, `.claude/reviews/x/y.md`). It never asserts on a bare folder path. `.claude/orchestrator/state/x.yaml` stays shipped.
  - *Registry change and the version check.* `test_a_registry_change_needs_a_bump` asserts exit 1 for a JOURNAL-only change at an unchanged version and exit 0 when the version is raised. This is invariant I2.
  - *Red before the change.* I ran the new test file against master's `check_version_bump.py` (prefix restored) in a temporary copy. Two tests failed: the copy-list test ("Lists differ: ['.claude/registries/MECHANISMS.md', …] != []") and the registry bump test ("0 != 1"). Exit 1, 15 tests, failures=2. The third new test passes on master too, which is expected: it pins classifications that did not change.
- **CLAUDE.md records the Q1 answer (a) as one consistent rule.** Met, with a nit (F3).
  - Line 5: the shipped list now ends "…templates, registry seeds the doctor copies".
  - Line 16: "A change that touches only documentation or work-item briefs needs no bump, except the registry files the doctor copies (see below)."
  - Line 18, the new paragraph: names the three files, says they "count as shipped files", that any pull request touching them raises the patch version, and that "this rule wins over the documentation exemption above". It says the doctor never overwrites, and it tells authors to batch registry appends with a change that already raises the version.
  - I read the whole file (18 lines). No other sentence exempts the registries or contradicts the rule. "Change all five places together" with four bullets is not a contradiction: the marketplace bullet names its two entries.
- **All five version entries read 0.9.18, and master reads 0.9.17.** Met. The diff changes `0.9.17` to `0.9.18` in each place, and grep of the working tree confirms:
  - `plugin.json:4`
  - `.claude-plugin/plugin.json:5`
  - `.cursor-plugin/plugin.json:3`
  - `.claude-plugin/marketplace.json:8` (top-level)
  - `.claude-plugin/marketplace.json:15` (`plugins[0]`)
- **Run list.** Met for the two commands assigned to me:
  - `test_check_version_bump.py`: exit 0, 15 tests OK.
  - `test_plugin_manifests.py`: exit 0, 138 passed, 0 failed.
  - `check_version_bump.py --base origin/master` runs in the main session after the commit.
- **Off-area drift and the Files to touch list.** No finding. Every tracked change is in sub-task 1's seven Files to touch. The untracked files are the contract, the work item and this review, all under `.claude/`. `.claude/area-mapping.json` declares no areas.
- **Non-Goals.** Respected. `.claude/orchestrator/state/` is still shipped (now pinned by a test). The other exempt entries, the doctor and the README are untouched. No runtime import was added.
- **End-User View.** Not applicable, as the contract states (no UI surface).

## Findings

- **F1 (nit): the new exempt-folder test adds no same-stem near-misses.** Location: `.claude/scripts/tests/test_check_version_bump.py`, `test_files_under_exempt_folders_are_not_shipped_but_orchestrator_state_is`.
  - The contract's test (3) says "keep the existing near-miss style". The existing test pins the trailing slash with `.claude/reviews-old/x.md` and `.claude/orchestrator/results-archive/x.yaml`. The new test has no matching rows for `.claude/concepts/`, `.claude/work-items/` or `.claude/north-stars/`.
  - Impact: low. Those prefixes were not changed here, and the slash is visible in the tuple.
  - Fix: add `self.assertTrue(cvb.is_shipped(".claude/concepts-old/x.md"))`, and the same for the other two prefixes.
- **F2 (nit): two exempt prefixes are not in the new loop.** Same test. The contract asks for files "under the other exempt prefixes" too. `.claude/scripts/tests/` is covered by the existing `test_tests_briefs_and_docs_alone_need_no_bump`, but `.github/` has no test anywhere in the file.
  - Fix: add `".github/workflows/x.yml"` to the exempt tuple.
- **F3 (nit): "raises the patch version" could be read as "patch only".** Location: `CLAUDE.md:18`. Line 5 says to use a minor bump for a new capability. A pull request that adds a capability and also appends to a registry needs a minor raise, and line 18 read literally says patch.
  - This is not a contradiction about whether to raise, which is what the CHECK item asks about, so it is a nit.
  - Fix: "raises the version (at least a patch)".
- **F4 (follow-up, outside this diff): the flows that append to registries do not yet mention the version raise.** The reviewer's janitor duties (`agents/fullstack-code-reviewer.md`, "Registry janitor duties"), `/journal-add` and the `/design-first` approval-time journal append still tell their authors to append with no word about the raise. The contract decided "no code change to the flows" (Adjacent Areas), so this is not a defect of sub-task 1. Today only CLAUDE.md carries the batching advice, and the agent prompts do not read it as a rule. Recorded so it can become a follow-up stub, together with the already-recorded follow-up of running the test suite in CI (invariant I1).

## What was NOT checked

- **`py -3 .claude/scripts/check_version_bump.py --base origin/master`.** The main session runs it after the commit. Before the commit, HEAD equals `origin/master`, so the script would compare a commit against itself and prove nothing.
- **The CI workflow `.github/workflows/version-bump.yml`.** Not run. It is unchanged, and it runs the script, not the tests.
- **The ASSUMED pull-request-level cost of registry-only pull requests (contract, Uncertain Assumptions).** Not re-measured. The user accepted the rule knowing that cost.
- **CodeGraph.** Not used. Both scripts are under `.claude/`, and the review was a diff audit of one hunk plus three new test methods. It needed no symbol tracing.

## Evidence

Commands, run from the worktree root unless shown otherwise:

| Command | Exit | Result |
|---|---|---|
| `git rev-parse --short origin/master` ; `git rev-parse --short HEAD` | 0 | both `9ef9893` |
| `git status --short` | 0 | 7 tracked files modified; untracked: the contract, the work item, this review folder |
| `git diff origin/master --stat` | 0 | 7 files, 43 insertions, 8 deletions |
| `git diff origin/master` | 0 | check script: one hunk (comment plus prefix removed); tests: one import and three methods; CLAUDE.md: lines 5 and 16 amended, one paragraph added; five version lines 0.9.17 → 0.9.18 |
| `git diff origin/master -- .claude/scripts/check_version_bump.py \| grep -c "^[-+]def"` | 0 | `0`: no function added or removed |
| `grep -n "import" .claude/scripts/check_version_bump.py` | 0 | stdlib only; no `plugin_doctor` |
| `git diff --quiet origin/master -- .claude/scripts/plugin_doctor.py` | 0 | doctor unchanged |
| `grep -n '"version"'` over the four manifest files | 0 | five entries, all `0.9.18` |
| Glob `.claude/registries/**` | n/a | exactly MECHANISMS.md, VOCABULARY.md, JOURNAL.md |
| `py -3 .claude/scripts/tests/test_check_version_bump.py` | 0 | Ran 15 tests, OK |
| `py -3 .claude/scripts/tests/test_plugin_manifests.py` | 0 | 138 passed, 0 failed |
| `py -3 -I %TEMP%/rv-77-redcheck/scripts/tests/test_check_version_bump.py` (the new test file against master's `check_version_bump.py`, exported with `git show origin/master:…`, plus the unchanged doctor) | 1 | FAILED (failures=2): the copy-list test and `test_a_registry_change_needs_a_bump`. Red before the change. |
| `py -3 -I %TEMP%/rv-77-redcheck/vacuity_probe.py <worktree>/.claude/scripts` (runs the copy-list test with `plugin_doctor.REQUIREMENTS = []`) | 1 | FAILED: "'.claude/templates/concept-contract.md' not found in []". Not vacuous. |
| `py -3 .claude/scripts/check_version_bump.py --base origin/master` | n/a | main session, after the commit |

Files read:

- The contract, in full.
- `CLAUDE.md`, in full.
- `.claude/scripts/check_version_bump.py:1-60` and `.claude/scripts/plugin_doctor.py:1-100` (the `REQUIREMENTS` list).
- `.claude/scripts/tests/test_check_version_bump.py`, the existing tests and the three new methods.
- `.claude/reviews/2026-10-22-advisor-refs-and-lookup-test/t2-review-fullstack-code-reviewer.md` and its `.gate.json`, for the six-section shape.

## Disposition

The verdict is pass-with-findings. Nothing blocks the commit.

1. **After the commit.** Run `py -3 .claude/scripts/check_version_bump.py --base origin/master` and confirm "version raised to 0.9.18".
2. **F1, F2 (optional, before the commit).** Add the near-miss rows and a `.github/` row to the exempt-folder test. Both are test-only and need no further version change, since the pull request already raises to 0.9.18.
3. **F3 (optional).** Change "raises the patch version" to "raises the version (at least a patch)" in CLAUDE.md.
4. **F4.** File a follow-up stub: teach the three registry-appending flows about the version raise, and run the test suite in CI.

Janitor work in this pass. Per the TASK constraint, nothing is appended to the registries here:

- **MECHANISMS.md:** nothing warranted. No new mechanism; the test couples two existing scripts.
- **VOCABULARY.md:** nothing warranted.
- **JOURNAL.md:** nothing warranted. There was no divergence from the contract, and no ASSUMED item was falsified.
- **INTEGRATION.md:** not present, and nothing here would need it.
