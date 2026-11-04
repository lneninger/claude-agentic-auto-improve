---
id: 245
issue_offer: opened
title: Script readers through the resolver
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/245
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t5-script-readers-through-the-resolver
worktree: none
north_stars: inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md
parent_issue: 235
base: fix/235-domain-split-registries
contract: .claude/concepts/2026-11-04-domain-split-registries.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-04
---

# Script readers through the resolver

## Problem statement
Sub-task 5 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235). The contract's handoff block below is the whole specification.

## Acceptance criteria
### 5. Script readers through the resolver (`python-ai-developer`)

**Depends on:** 3

**Files to touch:**
- `.claude/scripts/cross_area_scan.py`
- `.claude/scripts/north_star_review.py`
- `.claude/scripts/tests/test_registry_readers.py`

**Pre-written TASK block:**
```
TASK: Route the journal and mechanisms reads of cross_area_scan.py and north_star_review.py through registry_files /
_registry_layout, keeping their scores and output shapes.
CONTEXT: concept contract (Reused Mechanisms, I-3, I-8c).
FILES: as listed.
CONSTRAINTS:
  - journal_repo_root() keeps anchoring on the root file. No union of roots.
  - Tests: an entry only in JOURNAL/frontend.md and one only in MECHANISMS/backend.md are seen by each reader; a
    legacy entry is seen; a flat layout-1 fixture gives the same result as before this change.
  - Run: py -3 .claude/scripts/tests/test_registry_readers.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

## Out of scope
- Everything outside the files listed in the handoff block.

## Known context
- Parent / epic: #235
- Contract: .claude/concepts/2026-11-04-domain-split-registries.md

## North-star alignment
- inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md

## Open questions from intake
- none

## Size
Task of an approved contract; not sized here.

## Routing
task of .claude/concepts/2026-11-04-domain-split-registries.md - dispatched by /advance
