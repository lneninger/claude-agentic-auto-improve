---
id: 118
issue_offer: opened
title: Guard paths and file recognition
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/118
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-30-angular-tailwind-followups/t2-guard-paths-and-file-recognition
worktree: none
north_stars: inherited from .claude/work-items/2026-10-30-86-angular-tailwind-followups.md
parent_issue: 86
base: feature/86-angular-tailwind-followups
contract: .claude/concepts/2026-10-30-angular-tailwind-followups.md
pr: none
issue_link: unknown
status: implementing
created: 2026-10-31
---

# Guard paths and file recognition

## Problem statement
Sub-task 2 of the approved contract `.claude/concepts/2026-10-30-angular-tailwind-followups.md` (parent issue #86). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 2. Guard paths and file recognition (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/hooks/architecture-guard.py`
- `.claude/hooks/tests/test_architecture_guard_paths.py`
- `.claude/scripts/tests/test_design_document_paths.py`
- `.claude/addons/angular-tailwind/documents/TAILWINDCSS_RULES.md`
- `.claude/addons/angular-tailwind/documents/ANGULAR_CODE_RULES.md`
- `skills/promote-ui-rule/SKILL.md`

**Pre-written TASK block:**
```
TASK: Implement G-1, G-2 and G-3 with V-2 for G-1 and G-2. Pin W2 and W10.
CONTEXT: concept contract (the ledger, G-1 to G-3, V-2).
FILES: as listed.
CONSTRAINTS:
  - G-1 controls: the rules file renamed away; "apps"; a two-segment root.
  - G-2 tests: a sibling written "@Component ({" is recognised; <stem>.css; negatives index.html, main.ts,
    x.spec.ts, x.d.ts, and app.html beside an app.ts with no decorator. Forced-raise tests for G-1 and G-2.
  - G-3: the ast and string test exactly as stated. promote-ui-rule :58 and :72 as stated. Run
    test_skill_script_lookup.py. Do NOT edit the advisor script.
  - W2: no "ClientApp" and no "/features/" in the guard. W10: every repository path cited in the shipped design
    documents exists; install-time paths and the foundation.md:47 note are excluded by name.
  - Correct only the "Enforced by" lines TAILWINDCSS_RULES.md:29 and :54, and ANGULAR_CODE_RULES.md:37. Run
    test_angular_rule_coverage.py and the three guard suites unchanged.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-30-angular-tailwind-followups.md — dispatched by /advance
