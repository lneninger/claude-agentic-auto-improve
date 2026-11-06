---
id: 248
issue_offer: opened
title: Plugin registries on layout 2, registry appends and docs
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/248
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t8-plugin-registries-on-layout-2-registry-appends-and-docs
worktree: none
north_stars: inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md
parent_issue: 235
base: fix/235-domain-split-registries
contract: .claude/concepts/2026-11-04-domain-split-registries.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/280
issue_link: deferred
status: shipped
created: 2026-11-04
---

# Plugin registries on layout 2, registry appends and docs

## Problem statement
Sub-task 8 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235). The contract's handoff block below is the whole specification.

## Acceptance criteria
### 8. Plugin registries on layout 2, registry appends and docs (`python-ai-developer`)

**Depends on:** 4, 5, 6, 7

**Files to touch:**
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `.claude/registries/JOURNAL.md`
- `.claude/registries/MECHANISMS/general.md`
- `.claude/registries/VOCABULARY/general.md`
- `.claude/registries/JOURNAL/general.md`
- `README.md`
- `CONTRIBUTING.md`

**Pre-written TASK block:**
```
TASK: Run migration 0001 on this repository (dry-run, then apply with the hash). Then append with registry_append.py
--universal: the seven VOCABULARY terms; MECHANISMS entries "Registry layout reader" and "Registry migration runner";
Correction lines under "Two-tier registry with a generated complete index", "Two-layer Claude path resolution",
"Adaptive Engineering Journal", "Section-scoped registry sync", "Preview-hash apply" (helpers in _preview_apply.py,
stage_and_replace added, second user registry_migrate) and VOCABULARY "Installed plugin root" (the guarded lookup is
_plugin_root.separate_plugin_root). Write the README change note "Domain-split registries (issue #235)" and the client
procedure "Moving a project onto registry layout 2"; update CONTRIBUTING.md's registry-sync paragraph.
CONTEXT: concept contract (Business Concept, New Mechanisms, Reused Mechanisms, "Import chain", Q4, Q15-Q18).
FILES: as listed.
CONSTRAINTS:
  - Never hand-edit a registry entry. Root header prose (e.g. JOURNAL.md:10 "Project sections hold ...") is not an
    entry and is updated by hand to describe layout 2.
  - Expected after the writes: --check exits 0 (current). --check-structure exits 0 and prints R4 advisory lines only
    (any other finding -> AMENDMENT). The digest exits 0.
  - README change note lists every new file a copied-script client must copy with the updated scripts:
    .claude/scripts/_registry_layout.py, _preview_apply.py, _plugin_root.py, registry_append.py, registry_migrate.py,
    registry_migrations/, .claude/references/registry-layout.md, .claude/templates/registries/; and says that
    auto_improve_finish_install.py now imports _preview_apply.py and _plugin_root.py.
  - Client procedure, PowerShell (issue §4.3): commit registry changes; registry_migrate.py --dry-run --project .;
    read registry-migration-report.md (leftovers, plugin-owned and unverified token entries, universal candidates
    and the Q18 heading step, orphans with ready-to-run lines); resolve any conflicting-entry; --apply
    --expect-sha256 <hash>; --check-structure; regenerate the digest; commit (backups sit under
    .claude/cache/registry-migrations/, not in the registries); recover or mark orphans. Say writers keep working
    before migration (domain-file fallback + advisory). Name the refusal codes, stale-sync and the sync-tool follow-up.
  - No version number in the text; no version file edit.
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
