---
id: 243
issue_offer: opened
title: Layout spec, shared reader, structure lint and digest
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/243
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t3-layout-spec-shared-reader-structure-lint-and-digest
worktree: none
north_stars: inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md
parent_issue: 235
base: fix/235-domain-split-registries
contract: .claude/concepts/2026-11-04-domain-split-registries.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/254
issue_link: deferred
status: shipped
created: 2026-11-04
---

# Layout spec, shared reader, structure lint and digest

## Problem statement
Sub-task 3 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235). The contract's handoff block below is the whole specification.

## Acceptance criteria
### 3. Layout spec, shared reader, structure lint and digest (`python-ai-developer`)

**Depends on:** 1, 2

**Files to touch:**
- `.claude/references/registry-layout.md`
- `.claude/hooks/_project_paths.py`
- `.claude/scripts/_claude_paths.py`
- `.claude/scripts/_registry_layout.py`
- `.claude/scripts/validate_registries.py`
- `.claude/scripts/generate_registry_digest.py`
- `.claude/templates/registries/MECHANISMS/general.md`
- `.claude/templates/registries/VOCABULARY/general.md`
- `.claude/templates/registries/JOURNAL/general.md`
- `.claude/scripts/tests/test_registry_layout.py`
- `.claude/scripts/tests/test_script_path_resolution.py`
- `.claude/scripts/tests/fixtures/registry-layout/...`

**Pre-written TASK block:**
```
TASK: Write the layout spec, registry_files(name, domains=None) (+ re-exports of it and checkout_equivalent_path),
_registry_layout (grammars incl. legacy entries, keys, I-8b sections, path_references, layout_state, R1-R6 and A1),
--check-structure [--strict] with advisory mode, the strict digest and the three general.md skeletons.
CONTEXT: concept contract (Entities I-1..I-8c, Value Objects, "Structural lint rules", "Import chain").
FILES: as listed.
CONSTRAINTS:
  - layout_state exactly per I-1. structure_findings takes plugin_keys (None = no resolved plugin root -> R3
    unverified, universal-candidate skipped); validate_registries resolves it via _plugin_root.separate_plugin_root,
    imported lazily. _registry_layout imports neither plugin_doctor nor any CLI script.
  - R4: candidate roots and R4_EXCLUDED_PREFIXES exactly as the contract; advisory unless --strict. Default mode
    keeps its regex and exit code.
  - Digest: drop DOMAINS; tier labels; legacy entries indexed; sources hash; full index always; exit 1 on R1/R2.
  - Spec: every normative part of this contract's Data Shapes in prose, plus "For the sync tool" (gate, exits 0/6/2,
    JSON state, stale-sync, plugin-owned token entries, Universal versus project-owned files).
  - Tests: pass + fail per rule; advisory vs current exits; --strict; every layout state incl. absent and one root
    missing; skeletons pass; CRLF; "--" separator; date tag; fenced sample ignored; `### Tag conventions` section and
    a `## Notes` section with bullets under it are prose, no finding; `## YYYY-MM-DD` and a dated journal bullet are
    legacy entries (keyed, R2 applies, advisory only, in the digest); path_references rejects `?? d/f.txt`,
    `"$CLAUDE_PROJECT_DIR"/.claude/hooks/x.py`, `../a/b.md`, `JOURNAL/frontend.md:33`, accepts `.claude/concepts/x.md`;
    an excluded prefix is skipped; a path present only under the plugin root resolves; domains= keeps general.
  - This repository: --check-structure exits 0 (state pending). Its output is the layout advisory plus R4 advisory
    lines only (expected: the paths listed under R4). Any non-R4 finding -> AMENDMENT, never suppressed; R4 lines
    beyond the expected list are listed in the PR, not an AMENDMENT.
  - Run: py -3 .claude/scripts/tests/test_registry_layout.py ; py -3 .claude/scripts/tests/test_script_path_resolution.py
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
