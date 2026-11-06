---
id: 247
issue_offer: opened
title: Agent, skill and template instructions
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/247
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t7-agent-skill-and-template-instructions
worktree: none
north_stars: inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md
parent_issue: 235
base: fix/235-domain-split-registries
contract: .claude/concepts/2026-11-04-domain-split-registries.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/278
issue_link: deferred
status: shipped
created: 2026-11-04
---

# Agent, skill and template instructions

## Problem statement
Sub-task 7 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235). The contract's handoff block below is the whole specification.

## Acceptance criteria
### 7. Agent, skill and template instructions (`python-ai-developer`)

**Depends on:** 3, 4, 6

**Files to touch:**
- `agents/data-architect.md`
- `agents/contract-critic.md`
- `agents/ui-ux-designer.md`
- `agents/fullstack-code-reviewer.md`
- `agents/registry-scout.md`
- `skills/journal-add/SKILL.md`
- `skills/design-first/SKILL.md`
- `skills/cross-impact/SKILL.md`
- `skills/promote-ui-rule/SKILL.md`
- `skills/verify-before-done/SKILL.md`
- `skills/application-design/SKILL.md`
- `skills/website-design/SKILL.md`
- `skills/validate-registries/SKILL.md`
- `skills/north-star/SKILL.md`
- `.claude/templates/concept-contract.md`
- `.claude/templates/north-star.md`
- `.claude/templates/followup-stub.md`
- `.claude/scripts/tests/test_plugin_text_scans.py`
- `.claude/scripts/tests/test_skill_script_lookup.py`

**Pre-written TASK block:**
```
TASK: Point every §2.2-B writer at registry_append.py and every reader at root + domain files; add design-first's
receiver for data-architect's appends; wire --check-structure into verify-before-done; extend the text scan and the
lookup pin to agents.
CONTEXT: concept contract (Integration Surfaces, Commands, Reused Mechanisms "Script lookup block", Q10, Q11, Q14).
FILES: as listed.
CONSTRAINTS:
  - Writers: fullstack-code-reviewer janitor duties; journal-add; design-first Step 3 (~166) and Step 5 (~323-325,
    346); data-architect append rules. Each runs the lookup block for registry_append.py with
    --project "$CLAUDE_PROJECT_DIR" (plugin-generic entries: --universal) and states: "on a project not yet on
    registry layout 2 it appends to a domain file and prints an advisory line; that is success. Exit 2: fix the entry
    file and re-run. Exit 3: stop and show the message to the user." No hand-Edit instruction for an entry remains.
  - Q14 receiver: design-first gains "Run the data-architect's registry appends", referenced after Step 2 and
    wherever data-architect is re-invoked to promote: for each `Registry appends:` line in a data-architect HANDOFF,
    run it in order through the lookup block, show the printed file:line, stop at the first exit 2 or 3 and show it,
    delete the entry file after success. data-architect writes each entry under .claude/cache/registry-appends/,
    lists the commands under `Registry appends:` and names that section as the step that runs them.
  - Readers: data-architect and contract-critic name MECHANISMS/general.md, VOCABULARY/general.md, JOURNAL/general.md,
    drop the fixed {backend,frontend,data,trading} list, and state the focus rule: root + general.md always; plus each
    domain file named after the contract's derived or adjacent area or focus when it exists; else every domain file.
    design-first :16, :62-63, :137 name root + domain files. ui-ux-designer, application-design, website-design,
    promote-ui-rule search JOURNAL.md and JOURNAL/*.md; cross-impact names the domain files; validate-registries
    describes --check-structure, --strict, R4 advisory and its exclusions, and routes fixes through
    registry_append.py (--correction-of); registry-scout says the generator writes the full index (legacy entries
    included) and exits 1 naming R1/R2 findings; north-star skill and template, concept-contract and followup-stub
    templates drop "project section" / "under <project>" for the domain form.
  - verify-before-done: a step running validate_registries.py --check-structure via the lookup block; exit 1 is
    NOT-READY; exit 0 with advisory lines is not.
  - Leave skills/ship/SKILL.md unchanged (Q11).
  - Text scan: the §2.2-B writers name registry_append.py and the layout-2 fallback sentence; data-architect and
    contract-critic name general.md; data-architect names the receiver section and design-first contains it; no
    shipped agent, skill or template names a flat registry path without the domain form, says "project section", or
    instructs appending to a registry by Edit. Lookup pin: scans agents/*.md as well as skills/**/*.md.
  - Run: py -3 .claude/scripts/tests/test_plugin_text_scans.py ; py -3 .claude/scripts/tests/test_skill_script_lookup.py
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
