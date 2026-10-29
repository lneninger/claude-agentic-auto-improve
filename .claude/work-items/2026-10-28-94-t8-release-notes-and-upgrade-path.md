---
id: 94
issue_offer: opened
title: Release notes and upgrade path
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/94
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-28-angular-tailwind-rule-documents/t8-release-notes-and-upgrade-path
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

# Release notes and upgrade path

## Problem statement
Sub-task 8 of the approved contract `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md` (parent issue #84). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 8. Release notes and upgrade path (`python-ai-developer`)

**Depends on:** 2, 3, 4, 5, 6, 7

**Files to touch:**
- `README.md`

**Pre-written TASK block:**
```
TASK: Write the 0.9.22 release note, the upgrade note, the timing record and the add-on table update.
CONTEXT: concept contract (Q6, Q10, Disabled hook entry, JOURNAL 2026-10-22).
FILES: README.md
CONSTRAINTS:
  - "Changed in 0.9.22": documents, the skill, guard Rule IDs and footer, uninstall skills, the disabled advisor.
  - Upgrade: list the rows each install age carries, as t4 found them (an add-on install since 0.9.9 has one
    UserPromptSubmit row on angular-tailwind-advisor.py; older installs name architecture-advisor.py). Run the
    uninstall skill, then the install skill, then start a new session.
  - Timing:
    - before: a Python start on every prompt (no matcher), 123 ms median of seven runs against a 50 ms bare start,
      measured once on one Windows workstation for issue #84, not re-measured;
    - after: no row on any per-prompt event, so no program starts for Angular rules. This is proven by the manifest
      checker and by the install test (zero UserPromptSubmit rows written), not by a timing run.
  - Say the kill switches of codegraph and strict-shell-gate are unchanged.
  - The README version line is 0.9.22. Update the skill list and counts.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md — dispatched by /advance
