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

**Depends on:** 5, 14 — blocks 4, 10 and 12 are no longer named: their records read `blocked`, and the loop never releases a block whose dependency reads `blocked`; the fourth security review (14) replaces them. Before amendment 3 this line read "5, 12"; before amendment 2 it read "5, 10".

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
  table of the Inventory. This block runs after the ordinary switches block (5) and the fourth
  security review (14) have passed; read the report
  t14-security-re-review-round-four-security-auditor.md, the blocked reviews
  t12-security-re-review-round-three-security-auditor.md and
  t10-security-re-review-security-auditor.md, and the second run sheet
  t9-live-prompt-trial-second-round-senior-test-engineer.md for the residual-risk wording.
FILES: as listed.
CONSTRAINTS:
  - README: replace the variable table with a switch table (key, values, default, effect,
    allowed in), show the whole switch file to edit in an editor, and add a section on the
    Database override arm with PowerShell and POSIX commands for the person's own terminal and
    the stated residual risk as the contract's "Residual risk" paragraph words it: prompts
    answered by code, the arm not tied to a command, the allow-rule result of the second live
    trial report (t9) with its limits (one rule, one settings layer, default mode, one host
    version), that an older installed copy of the plugin knows no arm and blocks, and that
    acceptEdits, plan and dontAsk were not tried live. Add _switches.py to the helper
    lists. Leave "Change notes by version" as written and add a dated note for this change. The
    note names apart, as fixes of behaviour older than this contract: a human-only script after
    quoted text in the same call was allowed with no prompt (re-review P1), including after a
    trailing backslash before a closing quote or an escaped quote (t12 P1), and a link at the
    database guards' rules file to a named pipe could hang them (I1). It also names: a
    human-only script after a shell keyword, a prefix command or inside backticks was allowed
    with no prompt (t12 P2), and a link at either database guard's audit log (db-guard.log,
    db-research.log) or log folder could hang or redirect its audit write (t12 I2); such a log
    is now skipped, so keep .claude/logs a real folder. It also says that a rules file which is a link to a network drive or share now
    counts as unreadable, so every database is protected; keep the rules file a regular file in
    the project folder. A shape the guard now reads as invoked in either shell is blocked even
    when the other shell would only mention it; the person runs it by hand.
  - CONTRIBUTING: a new switch is one catalog entry, one README row and one on/off test pair,
    never an environment read.
  - Delete the CLAUDE_CONTRACT_SKIP and CLAUDE_VERIFY_REVIEW_GATE text as the table says.
  - INV-12 compares the README table with the catalog. K-3 becomes "concept-gate.py reads the
    concept_gate switch through the helper". Keep the add-on scan rows.
  - Registries: append through .claude/scripts/registry_append.py only. Corrections to
    "Disposable migration dry-run DB" and "Session-start context delivery", the Switch file and
    switch helper mechanism, a correction to the Add-on term, and the five new terms. Amendment
    2 adds two corrections: "Guard rules file" (the database guards read it through
    read_regular_file_bytes) and "Guard fallback mode" (the read-only guard is a new user, with
    an inline regular-file reader).
  - Do not touch any plugin version file. Run test_plugin_manifests.py,
    test_switch_env_scan.py, test_skill_script_lookup.py and validate_registries.py
    --check-structure.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-16-file-based-switches.md
  contract_status: approved
```

---

## Routing
task of .claude/concepts/2026-11-16-file-based-switches.md — dispatched by /advance
