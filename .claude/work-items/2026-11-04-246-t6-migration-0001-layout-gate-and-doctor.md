---
id: 246
issue_offer: opened
title: Migration 0001, layout gate and doctor
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/246
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t6-migration-0001-layout-gate-and-doctor
worktree: none
north_stars: inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md
parent_issue: 235
base: fix/235-domain-split-registries
contract: .claude/concepts/2026-11-04-domain-split-registries.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/273
issue_link: deferred
status: shipped
created: 2026-11-04
---

# Migration 0001, layout gate and doctor

## Problem statement
Sub-task 6 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235). The contract's handoff block below is the whole specification.

## Acceptance criteria
### 6. Migration 0001, layout gate and doctor (`python-ai-developer`)

**Depends on:** 2, 3

**Files to touch:**
- `.claude/scripts/registry_migrate.py`
- `.claude/scripts/registry_migrations/__init__.py`
- `.claude/scripts/registry_migrations/m0001_domain_split.py`
- `.claude/scripts/plugin_doctor.py`
- `.claude/scripts/tests/test_registry_migrate.py`
- `.claude/scripts/tests/test_plugin_doctor.py`
- `.claude/scripts/tests/fixtures/registry-migration/...`

**Pre-written TASK block:**
```
TASK: Write the migration runner, migration 0001 and --check; add the doctor's layout line, body-less journal count,
--json key registry_layout and the three general.md copy requirements.
CONTEXT: concept contract (I-9..I-13, Commands incl. "Order", "Plan hash", "Shared helpers", "Migration 0001"
steps 1-6, Migration leftover block, Plugin root resolution, Registry layout state).
FILES: as listed.
CONSTRAINTS:
  - Uses _preview_apply (_plan_digest, stage_and_replace) and _plugin_root.separate_plugin_root; never imports
    finish-install. Backups only under <report folder>/backup/. plugin_doctor imports _registry_layout lazily and
    reports a missing module by name.
  - Fixtures: (a) the client's state: a heading-less root ending "See domain-specific files...", title-only entries,
    flat-only, split-only, the same bodiless entry in flat and split, a bodiless entry under ## Project:, Tags/source
    contracts that classify, a client-authored token entry, a plugin-owned token entry (fake plugin root with
    manifest), a token-free client-authored Universal entry, a token header line, prose + sub-heading + table under
    ## Project:, a ## YYYY-MM-DD entry and a dated journal bullet under ## Project:, `### Tag conventions`, a fenced
    sample, a journal key with a Lesson-only copy beside a bodied copy; (b) stale-sync; (c) a same-field
    different-text conflict; (d) vendored: no plugin root except the project itself.
  - Tests: dry-run writes nothing; apply with the dry-run hash succeeds; (a) and (b) are `current` after apply; a
    second apply on the still-uncommitted tree exits 0 with an empty plan and equal bytes; --check exits 6 before and
    0 after; I-12 entry and per-instance text checks, incl. a forced plan dropping one prose line ->
    content-loss-detected; leftovers verbatim and last in general.md; legacy entries moved verbatim, not into
    leftovers; removed lines listed by reason; §4.2 order; client token entry moved, plugin-owned one kept,
    universal-candidate listed and kept; (d) -> every token entry unverified and kept, report names the reason; the
    Lesson-only copy's lines appended under the kept entry, nothing lost; orphans listed with a ready-to-run
    --archive-title-only line, not marked; conflicting-entry and uncommitted-registry-changes refuse, write the
    report, leave files byte-identical; changed-since-preview; forced replace failure restores every file and leaves
    no file under .claude/registries/ other than the originals; hash equals _plan_digest over the stated parts;
    project-undetermined unset and absent.
  - Doctor: report-only; --fix never migrates; existing suite green.
  - Run: py -3 .claude/scripts/tests/test_registry_migrate.py ; py -3 .claude/scripts/tests/test_plugin_doctor.py ;
    py -3 .claude/scripts/tests/test_check_version_bump.py
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
