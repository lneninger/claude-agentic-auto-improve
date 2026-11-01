---
id: 153
issue_offer: pending
title: Registration checker and tests
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/153
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-31-plugin-owns-hook-mechanism-tests/t1-registration-checker-and-tests
worktree: none
north_stars: inherited from .claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md
parent_issue: 148
base: feature/148-plugin-owns-hook-mechanism-tests
contract: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/158
issue_link: deferred
status: shipped
created: 2026-11-01
---

# Registration checker and tests

Raw argument: sub-task 1 of the contract `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md`, opened by `/flow` Step 2.7 under parent issue #148.

## Problem statement
Task 1 of the approved contract `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md`. The contract is authoritative; see the parent brief `.claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md` for the work item as a whole.

## Acceptance criteria
The contract's own approved handoff block, copied verbatim:

### 1. Registration checker and tests (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/check_hook_registrations.py`
- `.claude/scripts/tests/test_check_hook_registrations.py`
- `.claude/scripts/tests/fixtures/hook-registrations/settings.json`
- `.claude/scripts/tests/fixtures/hook-registrations/hook-registration-profile.json`
- `.claude/work-item-conventions.json`

**Pre-written TASK block:**
```
TASK: Write the Hook registration check and its suite, and add the hook-registration-tests landing step.
CONTEXT: concept contract at .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md (Data Shapes:
  Hook registration profile RP-1..RP-8, Settings shape, rules HR-1..HR-5, the seven refusals, exit codes).
FILES: as listed.
CONSTRAINTS:
  - Tests first; watch them fail. Import _iter_hooks, _hook_key, _compare_extras from auto_improve_finish_install
    inside a module-level try; do not edit that file. On ImportError, main() refuses checker-dependency-missing
    (exit 2) naming the module and the five-file set; any other exception is checker-internal-error (exit 2).
  - build_hook_registration_profile takes no time argument; serialise follows RP-2. Assert that two builds from the same
    input give identical bytes.
  - Test classes, the equivalents of the five project tests: HookGatingTests.test_hook_gating (HR-3),
    RegistrationRowsUnchangedTests.test_hooks_block_equals_base_apart_from_if_keys (HR-2),
    RegistrationRowsUnchangedTests.test_row_count_is_unchanged (HR-1), ProfileSetupTests.test_profile_setup
    (round-trips and checks clean; a re-record keeps Exclusions, stale ones included),
    RegistrationCoverageTests.test_real_settings_every_registration_is_profiled_or_excluded (record from the
    shipped .claude/hooks/hooks.json inside the test, check clean, add one unrecorded row, get an HR-4 fail).
  - load_settings is the one Settings shape validator (block 2 reuses it): one error type carrying a kind
    (encoding, json, duplicate-key, not-object, shape) and the JSON path. Flag --hook-registration-profile, report
    key hook_registration_profile, codes hook-registration-profile-missing / -unreadable (naming rule).
  - Failure path: break each rule in turn; assert exit 1 naming that rule only. A fixture breaking all five gets
    five FAIL lines. Each refusal code gets exit 2: --project set with settings absent, UTF-16, invalid JSON,
    a duplicate key (top level and handler level), non-object hooks, and each malformed level (event value,
    group, group hooks absent or not a list, handler, command, args). RP-4..RP-7 breaches are hook-registration-profile-unreadable; one Exclusion covering two
    duplicate rows passes. The checker copied alone into a temporary folder exits 2 with
    checker-dependency-missing. No hooks key is valid. A row with no .py file gets the command: identity.
  - Bytecode: the checker's first statement sets sys.dont_write_bytecode = True, before the guarded import.
    Test: copy the five files into <tmp>/proj/.claude/scripts/ (a temp folder outside this repository, so no
    .gitignore hides anything; no Project profile), run the COPY in a fresh process from <tmp>/proj, once with
    py -3 -B and once with plain py -3; after each the whole <tmp>/proj tree is byte-identical (no __pycache__,
    no file written).
  - Generic fixture: no project name; paths use ${CLAUDE_PROJECT_DIR}.
  - Add {"id": "hook-registration-tests", "command": ["py","-3",
    ".claude/scripts/tests/test_check_hook_registrations.py"], "results": {"format": "exit-code"},
    "timeout_minutes": 5} after loop-script-tests, and to the block's $comment one sentence about it plus one
    naming .claude/scripts/tests/test_land_contract_verification.py as the test that reads these steps.
  - Run: py -3 .claude/scripts/tests/test_check_hook_registrations.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
  contract_status: approved
```

## Out of scope
- Anything outside this block's "Files to touch". See the parent brief for the item's out-of-scope list.

## Known context
- Parent / epic: #148
- Related items: the other sub-tasks of the same contract
- Affected areas: the files listed in the block above

## North-star alignment
- inherited from .claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md

## Open questions from intake
- none (intake is skipped for a task of an approved contract)

## Size
Task of an approved contract.

## Routing
task of .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md - dispatched by /advance
