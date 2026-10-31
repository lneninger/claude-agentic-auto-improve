---
id: 119
issue_offer: opened
title: Remove the add-on kill switches
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/119
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-30-angular-tailwind-followups/t3-remove-the-add-on-kill-switches
worktree: none
north_stars: inherited from .claude/work-items/2026-10-30-86-angular-tailwind-followups.md
parent_issue: 86
base: feature/86-angular-tailwind-followups
contract: .claude/concepts/2026-10-30-angular-tailwind-followups.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/131
issue_link: deferred
status: shipped
created: 2026-10-31
---

# Remove the add-on kill switches

## Problem statement
Sub-task 3 of the approved contract `.claude/concepts/2026-10-30-angular-tailwind-followups.md` (parent issue #86). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 3. Remove the add-on kill switches (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/addons/codegraph/addon.json`
- `.claude/addons/strict-shell-gate/addon.json`
- `.claude/addons/codegraph/hooks/codegraph-first-guard.py`
- `.claude/addons/strict-shell-gate/hooks/bash-gate.py`
- `skills/auto-improve-codegraph-install/SKILL.md`
- `skills/auto-improve-codegraph-uninstall/SKILL.md`
- `skills/auto-improve-strict-shell-gate-install/SKILL.md`
- `skills/auto-improve-strict-shell-gate-uninstall/SKILL.md`
- `.claude/references/codegraph-decision-table.md`
- `README.md`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/hooks/tests/test_contract_index.py`
- `.claude/hooks/tests/test_main_checkout_guard.py`
- `.claude/hooks/tests/test_shell_write_targets.py`
- `.claude/hooks/tests/test_codegraph_first_guard.py`

**Pre-written TASK block:**
```
TASK: Implement K-1 to K-4: remove CLAUDE_SKIP_CG, CLAUDE_BASH_GATE and the add-on's use of CLAUDE_CONCEPT_GATE.
CONTEXT: concept contract (Kill-switch removal; the ASSUMED narrow reading).
FILES: as listed.
CONSTRAINTS:
  - Hooks: delete the switch checks and the docstring and message lines that name them. The codegraph block
    message is the K-4 text. Do NOT touch concept-gate.py or concept_changed_check.py.
  - Skills, the decision table and README (:268, :341): no kill switch. Add the K-4 table to README. Replace the
    uninstall skills' "never edit settings.json by hand" lines (strict-shell-gate uninstall :17 and :128, and
    the codegraph equivalents) with the K-4 wording. State that CLAUDE_CONCEPT_GATE=off no longer turns off the
    shell gate.
  - Tests:
    * test_plugin_manifests: K-1, K-2 (with its positive control), K-3.
    * test_auto_improve_finish_install: the :250 fake drops its CLAUDE_BASH_GATE line; :2785 expects
      {CLAUDE_CONCEPT_GATE, CLAUDE_ARCH_GUARD}; :3412, :3420 and :4881 expect an empty kill-switches list.
    * test_contract_index section (f): the bash-gate rows prove the switches have no effect.
    * test_main_checkout_guard: the :889-891 comment only.
    * test_shell_write_targets: K-4 reachability, and the import-failure message names removing the row.
    * test_codegraph_first_guard: CLAUDE_SKIP_CG=1 no longer bypasses; the message checks of K-4.
  - Leave the environment strip lists (test_flat_worktree.py:62, test_shell_write_targets.py:227-228,
    test_worktree_path_guards.py:379) as they are: they guard against a shell that still sets an old value.
  - Pull request body: the three lines of the user's global CLAUDE.md that only the user changes.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-30-angular-tailwind-followups.md — dispatched by /advance
