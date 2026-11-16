---
id: 424
issue_offer: opened
title: Ordinary switches
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/424
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t5-ordinary-switches
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

# Ordinary switches

## Problem statement
Sub-task 5 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 5. Ordinary switches (`python-ai-developer`)

**Depends on:** 2

**Files to touch:**
- `.claude/hooks/concept-gate.py`
- `.claude/hooks/architecture-guard.py`
- `.claude/hooks/critic-verdict-tracker.py`
- `.claude/hooks/contract-status-watcher.py`
- `.claude/hooks/journal-post-approval-tracker.py`
- `.claude/hooks/integration-check.py`
- `.claude/hooks/memory-pager.py`
- `.claude/hooks/working-agreements.py`
- `.claude/hooks/plan-question-advisor.py`
- `.claude/scripts/_contract_index.py`
- `.claude/scripts/concept_changed_check.py`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/addons/strict-shell-gate/hooks/bash-gate.py`
- `.claude/addons/strict-shell-gate/addon.json`
- `.claude/switches.json`
- `.claude/hooks/tests/fixtures/gate_parity_corpus.json`
- `.claude/hooks/tests/test_contract_index.py`
- `.claude/hooks/tests/test_gate_cost.py`
- `.claude/hooks/tests/test_concept_gate_outside_project.py`
- `.claude/hooks/tests/test_changed_file_check.py`
- `.claude/hooks/tests/test_main_checkout_guard.py`
- `.claude/hooks/tests/test_shell_write_targets.py`
- `.claude/hooks/tests/test_architecture_guard_paths.py`
- `.claude/hooks/tests/test_architecture_guard_precision.py`
- `.claude/hooks/tests/test_architecture_guard_messages.py`
- `.claude/hooks/tests/test_post_edit_dispatcher.py`
- `.claude/hooks/tests/test_journal_post_approval_tracker.py`
- `.claude/hooks/tests/test_hook_data_files_project_first.py`
- `.claude/hooks/tests/test_memory_pager.py`
- `.claude/hooks/tests/test_working_agreements.py`
- `.claude/hooks/tests/test_stop_dispatcher.py`
- `.claude/hooks/tests/test_addons.py`
- `.claude/hooks/tests/_addon_fixture.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/scripts/tests/test_flat_worktree.py`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/tests/test_switch_env_scan.py`

**Pre-written TASK block:**
```
TASK: Move the nine ordinary switches to the helper, and rewrite every test that set an old
  variable to write the file setting instead. Remove the expectedFailure marks from the scan rows
  this block makes pass.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md.
FILES: as listed.
CONSTRAINTS:
  - bypass_env(project=None) and pinned_contract(project=None) keep their names. The
    changed-file check computes its tree root first and passes it.
  - _contract_index.py stays standard-library-only: remove its environment read and add
    set_mode(value). concept-gate.py and bash-gate.py read contract_index and call set_mode once.
  - addon.json helpers gain .claude/hooks/_switches.py and .claude/hooks/_error_log.py; update
    the manifest rows that pin the list.
  - Each switch gets one on row and one off row in its hook's suite, writing the file in a
    temporary project. Keep the row proving concept_gate off leaves the main-checkout guard on.
  - finish-install: replace the kill-switches readiness field with switches; add-on plans keep
    their empty kill-switches list. Import the helper fail-soft (unavailable).
  - .claude/switches.json: every key at its default, plus a $comment naming the local file.
  - Leave the CLAUDE_* strip lists alone. Do not touch any plugin version file.
  - Run every suite listed, plus test_check_hook_registrations.py.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md — dispatched by /advance
