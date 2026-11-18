---
id: 425
issue_offer: opened
title: Documents, skills and registries
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/425
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-16-file-based-switches/t6-documents-skills-and-registries
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

# Documents, skills and registries

## Problem statement
Sub-task 6 of the approved contract `.claude/concepts/2026-11-16-file-based-switches.md` (parent issue #419). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 6. Documents, skills and registries (`python-ai-developer`)

**Depends on:** 5, 10 — block 4 is no longer named: its record reads `blocked`, and the loop never releases a block whose dependency reads `blocked`; the re-review (10) replaces it.

**Files to touch:**
- `README.md`
- `CONTRIBUTING.md`
- `.claude/hooks/hooks.json`
- `skills/design-first/SKILL.md`
- `skills/contract-accuracy/SKILL.md`
- `skills/verify-before-done/SKILL.md`
- `skills/promote-ui-rule/SKILL.md`
- `skills/auto-improve-finish-install/SKILL.md`
- `skills/auto-improve-strict-shell-gate-install/SKILL.md`
- `skills/auto-improve-strict-shell-gate-uninstall/SKILL.md`
- `skills/auto-improve-codegraph-install/SKILL.md`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/tests/test_switch_env_scan.py`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`

**Pre-written TASK block:**
```
TASK: Rewrite the documents and skill text for file settings, rewrite INV-12 and K-3 of
  test_plugin_manifests.py, and record the mechanism and terms in the registries. Remove the last
  expectedFailure marks.
CONTEXT: concept contract at .claude/concepts/2026-11-16-file-based-switches.md, the skill-text
  table of the Inventory. This block runs after the ordinary switches block (5) and the security
  re-review (10) have passed; read the re-review report
  t10-security-re-review-security-auditor.md and the second run sheet
  t9-live-prompt-trial-second-round-senior-test-engineer.md for the residual-risk wording.
FILES: as listed.
CONSTRAINTS:
  - README: replace the variable table with a switch table (key, values, default, effect,
    allowed in), show the whole switch file to edit in an editor, and add a section on the
    Database override arm with PowerShell and POSIX commands for the person's own terminal and
    the stated residual risk as the contract's "Residual risk" paragraph words it: prompts
    answered by code, the arm not tied to a command, and the allow-rule result of the second live
    trial report (t9). Add _switches.py to the helper
    lists. Leave "Change notes by version" as written and add a dated note for this change.
  - CONTRIBUTING: a new switch is one catalog entry, one README row and one on/off test pair,
    never an environment read.
  - Delete the CLAUDE_CONTRACT_SKIP and CLAUDE_VERIFY_REVIEW_GATE text as the table says.
  - INV-12 compares the README table with the catalog. K-3 becomes "concept-gate.py reads the
    concept_gate switch through the helper". Keep the add-on scan rows.
  - Registries: append through .claude/scripts/registry_append.py only. Corrections to
    "Disposable migration dry-run DB" and "Session-start context delivery", the Switch file and
    switch helper mechanism, a correction to the Add-on term, and the five new terms.
  - Do not touch any plugin version file. Run test_plugin_manifests.py,
    test_switch_env_scan.py, test_skill_script_lookup.py and validate_registries.py
    --check-structure.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md — dispatched by /advance
