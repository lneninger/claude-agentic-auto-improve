---
id: 421
issue_offer: opened
title: Switch helper and database override
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/421
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t2-switch-helper-and-database-override
worktree: none
north_stars: inherited from .claude/work-items/2026-11-16-file-based-switches.md
parent_issue: 419
base: feature/file-based-switches
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-16
---

# Switch helper and database override

## Problem statement
Sub-task 2 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 2. Switch helper and database override (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/hooks/_switches.py`
- `.claude/hooks/db-destructive-guard.py`
- `.claude/hooks/db-research-readonly-guard.py`
- `.claude/hooks/tests/test_switches.py`
- `.claude/hooks/tests/test_database_override.py`
- `.claude/hooks/tests/test_db_destructive_guard.py`
- `.claude/hooks/tests/test_db_guard_path_allowlist.py`
- `.claude/hooks/tests/test_readonly_guard_disposable_exemption.py`
- `.claude/hooks/tests/test_worktree_path_guards.py`
- `.claude/hooks/tests/fixtures/db-protection/tests/test_db_protection_scripts.py`
- `.claude/scripts/tests/test_sql_patterns_skill_sync.py`
- `skills/sql-server-patterns/SKILL.md`
- `skills/auto-improve-database-guard-install/SKILL.md`
- `.gitignore`

**Pre-written TASK block:**
```
TASK: Build the switch helper and replace the destructive-database variable with the Database
  override arm in both guards. Remove the expectedFailure marks from the helper and override rows.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md.
FILES: as listed.
CONSTRAINTS:
  - First: confirm from the Claude Code hooks documentation that the PreToolUse payload carries
    permission_mode and tool_use_id, how "ask" combines with other answers, and that
    systemMessage is shown to the person. Quote the source in the pull request. If it disagrees
    with the contract, stop and report an AMENDMENT.
  - The helper owns the catalog of nine keys exactly as the Inventory table says, and the
    Visible-off rule's systemMessage output for guards. Call-time lookups only.
  - The Arm-write rule runs before Guard deference, in both guards, with an inline copy of the
    name test in each (Guard fallback mode). Audit reasons: the Override outcome values plus
    override-file-write-refused. Remove user-override-env.
  - Reword the docstrings, block text and the two skills; no variable is named as a way out.
    Escape apostrophes in the printed arm commands.
  - Do not touch any plugin version file.
  - Run: test_switches.py, test_database_override.py, test_db_destructive_guard.py,
    test_db_guard_path_allowlist.py, test_readonly_guard_disposable_exemption.py,
    test_worktree_path_guards.py, test_sql_patterns_skill_sync.py, test_script_path_resolution.py.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md — dispatched by /advance
