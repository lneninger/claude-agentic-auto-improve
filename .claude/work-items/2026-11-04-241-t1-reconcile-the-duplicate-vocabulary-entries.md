---
id: 241
issue_offer: opened
title: Reconcile the duplicate vocabulary entries
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/241
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t1-reconcile-the-duplicate-vocabulary-entries
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

# Reconcile the duplicate vocabulary entries

## Problem statement
Sub-task 1 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235). The contract's handoff block below is the whole specification.

## Acceptance criteria
### 1. Reconcile the duplicate vocabulary entries (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/registries/VOCABULARY.md`

**Pre-written TASK block:**
```
TASK: Remove the two duplicate titles from VOCABULARY.md without changing any body text, so every key is unique
before the lint exists.
CONTEXT: concept contract I-7 (the one pre-layout exception); round-2 finding P2-W5.
FILES: as listed.
CONSTRAINTS:
  - "Add-on manifest": delete the top-level 2026-10-31 entry (today line 91). Append, as the last indented line under
    the 2026-10-30 entry (line 79), exactly:
    "  - **Merged duplicate (2026-10-31, `.claude/concepts/2026-10-12-dedupe-claude-config.md`, Revision 3), kept
    verbatim.** Where it says the manifest names \"the kill switches to report\", the entry above and the **Add-on**
    entry govern: no shipped add-on declares one. Text: " + the deleted entry's text after its separator, verbatim.
    The 2026-10-30 entry and the Add-on entry (lines 74-79) stay as they are.
  - "Vendored-asset drift (amendment)" x2: delete both top-level entries (lines 86, 94). Under the base entry
    "Vendored-asset drift" (line 36), after its existing 2026-10-31 Correction (line 37), append in order:
    "  - **Correction (2026-10-30, `.claude/concepts/2026-10-30-angular-tailwind-followups.md`):** " + the line-86
    text after its separator, verbatim; and
    "  - **Correction (2026-11-01, `.claude/concepts/2026-10-31-warn-on-unshipped-hook-rows.md`):** " + the line-94
    text after its separator, verbatim. Confirm each source by grep (`disabled-hook-installed`, `dangling-hook-row`);
    if another contract introduced it, use that path and say so in the PR.
  - Touch nothing else. "Placeholder slot (amendment)" is unique and stays.
  - Check by hand: no bold title appears twice at column 0; each moved body appears exactly once, unchanged.
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
