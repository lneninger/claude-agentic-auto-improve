---
id: 156
issue_offer: pending
title: Registry appends and release notes
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/156
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-31-plugin-owns-hook-mechanism-tests/t4-registry-appends-and-release-notes
worktree: none
north_stars: inherited from .claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md
parent_issue: 148
base: feature/148-plugin-owns-hook-mechanism-tests
contract: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/162
issue_link: deferred
status: shipped
created: 2026-11-01
---

# Registry appends and release notes

Raw argument: sub-task 4 of the contract `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md`, opened by `/flow` Step 2.7 under parent issue #148.

## Problem statement
Task 4 of the approved contract `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md`. The contract is authoritative; see the parent brief `.claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md` for the work item as a whole.

## Acceptance criteria
The contract's own approved handoff block, copied verbatim:

### 4. Registry appends and release notes (`python-ai-developer`)

**Depends on:** 1, 2, 3

**Files to touch:**
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `README.md`

**Pre-written TASK block:**
```
TASK: Append the four proposed VOCABULARY terms (Registration row, Hook registration profile, Registration rule,
Failure attribution) and a MECHANISMS entry "Hook registration check" (Extend-by: one rule tuple entry, one pure
function, one test pair) to the Universal tier. Add one correction line under Preview-hash apply naming the
record-registrations subcommand. In README, add a short "Checking your hook registrations" section and a
change note headed "Hook registration checks (issue #148)".
CONTEXT: concept contract (New terms, naming rule, New Mechanisms, Extension Points, Q1-Q4 as answered).
FILES: as listed.
CONSTRAINTS:
  - Append only, at the end of the Universal tier. Never edit or reorder an existing entry. Regenerate the digest
    if the generator exists. Never write bare "profile" for the new concept. Add no entry for report.json or
    next_command (they are script outputs, not terms).
  - The README text is version-agnostic: no version number anywhere in the new text, so it cannot go stale
    before the landing's version raise, which is the only place the number is set. No version file edit.
  - The README section tells a project to: record its hook registration profile (record-registrations); vendor
    all five files (check_hook_registrations.py, auto_improve_finish_install.py, pr_merged.py, plugin_doctor.py,
    check_version_bump.py) through .sync-config.json (the only supported way for the landing step, which must
    name the checker at a path inside the repository; never say "or run from the plugin root"); add a landing
    step running exactly: py -3 -B .claude/scripts/check_hook_registrations.py --settings .claude/settings.json
    --hook-registration-profile .claude/hook-registration-profile.json (no when_paths), and why: -B and the
    checker keep Python from writing __pycache__ into the tree (which would halt the landing on "the steps
    changed the worktree"; a harness importing the checker without -B can still cache it), and naming the input
    files lets the landing say whether a failure came from the contract or the default branch, while a failure
    caused only by one of the four dependency scripts reads as undetermined; delete its own hook-registration
    tests and baseline entries. Every command in a form that runs in PowerShell.
  - Also state, for this repository: its hook-registration-tests landing step names only its test file, so a
    break in check_hook_registrations.py itself reads undetermined there ("no file the failure names is in
    either diff"), because the suite reaches the checker by import, not as a step argument.
  - State Q1's answer in the note, as narrowed: the advice only for named regressions; for exit-code steps,
    check whether the default branch fails the same step, never a re-record.
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
