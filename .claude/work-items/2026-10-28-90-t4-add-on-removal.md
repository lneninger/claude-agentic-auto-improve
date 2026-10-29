---
id: 90
issue_offer: opened
title: Add-on removal
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/90
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-28-angular-tailwind-rule-documents/t4-add-on-removal
worktree: none
north_stars: inherited from .claude/work-items/2026-10-28-84-angular-tailwind-rule-documents.md
parent_issue: 84
base: feature/84-angular-tailwind-rule-documents
contract: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/102
issue_link: deferred
status: shipped
created: 2026-10-28
---

# Add-on removal

## Problem statement
Sub-task 4 of the approved contract `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md` (parent issue #84). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 4. Add-on removal (`python-ai-developer`)

**Depends on:** 3

**Files to touch:**
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/hooks/tests/_addon_fixture.py`
- `.claude/addons/angular-tailwind/addon.json`
- `.claude/addons/codegraph/addon.json`
- `.claude/addons/strict-shell-gate/addon.json`
- `skills/auto-improve-angular-tailwind-uninstall/SKILL.md`
- `skills/auto-improve-codegraph-uninstall/SKILL.md`
- `skills/auto-improve-strict-shell-gate-uninstall/SKILL.md`
- `skills/auto-improve-angular-tailwind-install/SKILL.md`
- `skills/auto-improve-codegraph-install/SKILL.md`
- `skills/auto-improve-strict-shell-gate-install/SKILL.md`

**Pre-written TASK block:**
```
TASK: Add the addon-remove subcommand (the Preview-hash apply extension) and one uninstall skill per add-on.
CONTEXT: concept contract (Removal plan, I-6 to I-8, Q6-Q8, the ASSUMED rows under architecture-advisor.py).
FILES: as listed.
CONSTRAINTS:
  - Before writing fixtures, read the git history of .claude/hooks/hooks.json and of the add-on for every row that
    named angular-tailwind-advisor.py or architecture-advisor.py, and build one fixture per row form.
  - Preview, then apply with plan-sha256. Rows go first (with a backup), then the profile (the slot becomes none when
    empty), then the files. A second run returns nothing-to-do with a byte-identical tree.
  - Delete only files that are identical after the fold or match a released hash. Never delete helpers or the snippet.
    The kill switches of codegraph and strict-shell-gate are left as they are.
  - The uninstall skills copy the install skill's Step 0 lookup block unchanged. Run test_skill_script_lookup.py.
  - Tests: twice-run; a differing file kept; old installs under both names cleaned; a missing profile slot;
    rows-before-files ordering.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md — dispatched by /advance
