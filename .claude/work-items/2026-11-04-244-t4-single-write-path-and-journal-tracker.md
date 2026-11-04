---
id: 244
issue_offer: opened
title: Single write path and journal tracker
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/244
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t4-single-write-path-and-journal-tracker
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

# Single write path and journal tracker

## Problem statement
Sub-task 4 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235). The contract's handoff block below is the whole specification.

## Acceptance criteria
### 4. Single write path and journal tracker (`python-ai-developer`)

**Depends on:** 2, 3

**Files to touch:**
- `.claude/scripts/registry_append.py`
- `.claude/scripts/accuracy_update.py`
- `.claude/hooks/journal-post-approval-tracker.py`
- `.claude/scripts/tests/test_registry_append.py`
- `.claude/hooks/tests/test_journal_post_approval_tracker.py`

**Pre-written TASK block:**
```
TASK: Write registry_append.py (Command "Append registry entry") and move the tracker's parse/seen/fire logic into
accuracy_update.process_journal_change(files, fresh=()); the hook becomes a thin wrapper matching every journal file.
CONTEXT: concept contract (Commands, Events I-14, I-5..I-8c).
FILES: as listed.
CONSTRAINTS:
  - Options, domain choice, placement, rejections and exits exactly as Commands; --project required; writes through
    _preview_apply._atomic_write, never a local copy; calls process_journal_change with fresh.
  - Signature stays sha1(date|title). seeded_files keyed by checkout_equivalent_path per I-14, incl. old-cache upgrade.
    Hook exits 0 always (one stderr line if the entry point is missing).
  - Tests: one per rejection (incl. project-undetermined unset and absent, layout-unknown, registries-absent,
    no-universal-tier). current: --universal before the pointer, --domain, area default, general fallback,
    unknown-domain, append lands above the leftovers heading. pending, fixture = root with NO `## Project:` section
    (issue 2.2-B, ends with "See domain-specific files..."): a non-universal entry lands in the existing domain file,
    else in general.md created from the skeleton; the root's bytes are unchanged; an unknown --domain falls back to
    general and is named; --universal lands at the root's Universal end; advisory line; exit 0. stale-sync:
    --universal before the synced pointer; a project entry goes to a domain file. --correction-of;
    --archive-title-only and its refusal on a bodied entry. Tracker: a post-impl divergence entry by script fires
    once, a later hand edit does not re-fire; a hand Edit to a seeded JOURNAL/general.md fires; an unseeded domain
    file with post-* entries is seeded with zero fires; an old cache seeds domain files without firing; a script
    entry in a new domain file fires (fresh); the same journal file edited from two worktrees (paths under
    .claude/worktrees/a/ and /b/) seeds once and a new hand post-* entry fires exactly once; the Accepted guard limit
    (hand entry in a file whose checkout-equivalent path was never seen) is pinned.
  - Run: py -3 .claude/scripts/tests/test_registry_append.py ; py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py
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
