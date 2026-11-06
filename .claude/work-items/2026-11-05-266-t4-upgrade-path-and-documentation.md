---
id: 266
issue_offer: opened
title: Upgrade path and documentation
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/266
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-05-codegraph-hooks-redesign/t4-upgrade-path-and-documentation
worktree: none
north_stars: inherited from .claude/work-items/2026-11-05-261-codegraph-hooks-redesign.md
parent_issue: 261
base: feature/261-codegraph-hooks-redesign
contract: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/282
issue_link: deferred
status: shipped
created: 2026-11-05
---

# Upgrade path and documentation

## Problem statement
Sub-task 4 of the approved contract `.claude/concepts/2026-11-05-codegraph-hooks-redesign.md` (parent issue #261). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 4. Upgrade path and documentation (`python-ai-developer`)

**Depends on:** 2, 3

**Preconditions:** issue #259 delivered: its pull request merged into master, and master merged into feature/261-codegraph-hooks-redesign

**Files to touch:**
- `.claude/addons/codegraph/addon.json`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `skills/auto-improve-codegraph-install/SKILL.md`
- `skills/auto-improve-codegraph-uninstall/SKILL.md`
- `.claude/references/codegraph-decision-table.md`

**Pre-written TASK block:**
```
TASK: Let a project that holds an older released copy of a codegraph hook take the new one by re-running the
install skill, and document shadow mode, the report and the upgrade.
CONTEXT: contract (Upgrade the add-on in place, Reused Mechanisms, Q3).
FILES: see Files to touch.
CONSTRAINTS:
  - /tdd-first. Add to released_sha256 the folded hashes of every released #259 version of the guard and the
    reset hook up to the #261 landing (a #259 patch release included), read from master.
  - The update action sits inside the existing plan hash, takes a backup, refuses a link, and refuses an edited
    copy with addon-file-differs, naming the file and the uninstall-then-install route.
  - Tests: a released copy (updated), an edited copy (refused), an identical copy (nothing to do), a
    preview-then-changed file (changed-since-preview), a re-run (no change).
  - Docs describe the rows each install age has (JOURNAL 2026-10-22), the log path
    <project>/.claude/logs/codegraph-shadow.jsonl, the report command, and that the log is kept on uninstall.
  - Run test_addons.py unchanged.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-11-05-codegraph-hooks-redesign.md - dispatched by /advance
