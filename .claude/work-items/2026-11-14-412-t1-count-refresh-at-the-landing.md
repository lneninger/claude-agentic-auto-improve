---
id: 412
issue_offer: n/a
title: Count refresh at the landing
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/412
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-14-manifest-counts-landing-refresh/t1-count-refresh-at-the-landing
worktree: none
north_stars: inherited from .claude/work-items/2026-11-14-405-manifest-counts-landing-refresh.md
contract: .claude/concepts/2026-11-14-manifest-counts-landing-refresh.md
parent_issue: 405
base: feature/405-landing-time-manifest-count-refresh
pr: pending
issue_link: unknown
status: implementing
created: 2026-11-14
---

# Count refresh at the landing

## Acceptance criteria

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

## Routing
task of .claude/concepts/2026-11-14-manifest-counts-landing-refresh.md — dispatched by /advance
