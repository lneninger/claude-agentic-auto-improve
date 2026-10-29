---
id: 89
issue_offer: opened
title: Manifest and install
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/89
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-28-angular-tailwind-rule-documents/t3-manifest-and-install
worktree: none
north_stars: inherited from .claude/work-items/2026-10-28-84-angular-tailwind-rule-documents.md
parent_issue: 84
base: feature/84-angular-tailwind-rule-documents
contract: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
pr: none
issue_link: unknown
status: implementing
created: 2026-10-28
---

# Manifest and install

## Problem statement
Sub-task 3 of the approved contract `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md` (parent issue #84). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 3. Manifest and install (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/addons/angular-tailwind/addon.json`
- `.claude/addons/angular-tailwind/DISABLED.md`
- `.claude/addons/angular-tailwind/hooks/angular-tailwind-advisor.py`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/hooks/tests/_addon_fixture.py`
- `.claude/hooks/tests/test_addons.py`
- `skills/auto-improve-angular-tailwind-install/SKILL.md`

**Pre-written TASK block:**
```
TASK: Extend the add-on manifest and the install with documents, profile registration and disabled hooks, and drop
the kill switch.
CONTEXT: concept contract (Add-on manifest, Disabled hook entry, I-1 to I-6, I-9, I-10, the Install command).
FILES: as listed.
CONSTRAINTS:
  - Checkers: I-1 to I-3 in _read_addon_manifest and in addon_problems. kill_switches is optional.
    "_all_addon_hook_files" counts disabled hooks and former names.
  - Documents copy to .claude/references/angular-tailwind/ and are registered under I-6. Refusals: profile-slot-missing
    and disabled-hook-present (matches hook and former_names). The plan hash covers the profile bytes.
  - The advisor script loses only its CLAUDE_ARCH_ADVISOR check and docstring lines. released_sha256 is computed with
    _fold_text_bytes over every git revision of the file under both names.
  - DISABLED.md: what it did; its cost (a Python start on EVERY prompt, since it is registered on UserPromptSubmit with
    no matcher, 123 ms median against a 50 ms bare start on one Windows workstation, plus about 400 words of context
    when a keyword matched); why it is off; the dead "ui" keyword; how to turn it back on.
  - Tests:
    - a project that never ran the install has no documents, no rows and an unchanged profile (I-10);
    - install twice: the second preview adds nothing, the apply returns nothing-to-do, the tree is byte-identical;
    - slot cases: placeholder, none, authored list, already-listed path, missing row.
  - test_addons: the advisor tests install through af.install_disabled. WriterHarness moves to strict-shell-gate.
  - The install skill text: documents, profile, no kill switch, the new refusals.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md — dispatched by /advance
