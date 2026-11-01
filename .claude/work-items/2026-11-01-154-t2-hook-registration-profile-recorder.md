---
id: 154
issue_offer: pending
title: Hook registration profile recorder
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/154
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-31-plugin-owns-hook-mechanism-tests/t2-hook-registration-profile-recorder
worktree: none
north_stars: inherited from .claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md
parent_issue: 148
base: feature/148-plugin-owns-hook-mechanism-tests
contract: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-01
---

# Hook registration profile recorder

Raw argument: sub-task 2 of the contract `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md`, opened by `/flow` Step 2.7 under parent issue #148.

## Problem statement
Task 2 of the approved contract `.claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md`. The contract is authoritative; see the parent brief `.claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md` for the work item as a whole.

## Acceptance criteria
The contract's own approved handoff block, copied verbatim:

### 2. Hook registration profile recorder (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`

**Pre-written TASK block:**
```
TASK: Add the record-registrations subcommand (preview, and --apply --expect-sha256) that writes
.claude/hook-registration-profile.json through Preview-hash apply.
CONTEXT: concept contract (Commands: Preview/Apply hook registration profile; RP-1..RP-8; naming rule).
FILES: as listed.
CONSTRAINTS:
  - Import check_hook_registrations inside the two new functions only. Add a test importing each module first in
    a fresh process, and one running `py -3 -B auto_improve_finish_install.py record-registrations` as a script
    (the installer is __main__, so a second installer copy loads; preview then apply succeeds). Pass only plain
    data between the copies (Data Shapes, The second installer copy).
  - A group with no hooks key is refused unexpected-settings-shape (tested); _parse_settings still accepts it.
  - The plan hash covers settings bytes, existing file bytes (or "absent") and planned bytes, all deterministic.
    Test: preview then apply succeeds; apply after a settings change is changed-since-preview; an unchanged
    re-record reports nothing to write and leaves the file byte-identical.
  - Add registration-settings-missing and hook-registration-profile-unreadable to REFUSAL_CODES (exit class 2).
    Read settings through check_hook_registrations.load_settings only: kind shape -> unexpected-settings-shape,
    every other kind -> malformed-settings (each malformed level and a duplicate key, tested). Reuse write-failed
    and the symbolic-link refusal.
  - Do NOT change _parse_settings. Regression test: a settings file with a handler-level breach (a handler with
    no type) is still accepted by _parse_settings, and the hooks and addon subcommands' existing tests stay green
    unchanged.
  - Keep existing Exclusions verbatim (RP-8) and list stale ones in the preview. Messages say "hook registration
    profile" in full, never bare "profile". Update the module docstring's Usage lines.
  - The existing suite stays green. Run: py -3 .claude/scripts/tests/test_auto_improve_finish_install.py
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
