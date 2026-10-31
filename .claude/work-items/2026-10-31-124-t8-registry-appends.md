---
id: 124
issue_offer: opened
title: Registry appends
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/124
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-10-30-angular-tailwind-followups/t8-registry-appends
worktree: none
north_stars: inherited from .claude/work-items/2026-10-30-86-angular-tailwind-followups.md
parent_issue: 86
base: feature/86-angular-tailwind-followups
contract: .claude/concepts/2026-10-30-angular-tailwind-followups.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/139
issue_link: deferred
status: shipped
created: 2026-10-31
---

# Registry appends

## Problem statement
Sub-task 8 of the approved contract `.claude/concepts/2026-10-30-angular-tailwind-followups.md` (parent issue #86). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 8. Registry appends (`python-ai-developer`)

**Depends on:** 1, 3, 5

**Files to touch:**
- `.claude/registries/VOCABULARY.md`
- `.claude/registries/MECHANISMS.md`

**Pre-written TASK block:**
```
TASK: Append the "## Registry appends" text of this contract, verbatim, at the end of the Universal tier of each
file.
CONTEXT: concept contract (Registry appends, Q3). Runs only after t1, t3 and t5 have merged, so every appended
fact is already true.
FILES: as listed.
CONSTRAINTS:
  - Never edit, reorder or rewrite an existing entry. MECHANISMS.md:15 stays as it is; the CodeGraph amendment
    supersedes its bypass clause.
  - Before appending, check each appended fact against master: no add-on declares kill_switches; the codegraph
    message names no CLAUDE_SKIP_CG; --drift emits disabled-hook-installed.
  - Regenerate the digest if the generator exists (py -3 .claude/scripts/generate_registry_digest.py).
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-30-angular-tailwind-followups.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-10-30-angular-tailwind-followups.md — dispatched by /advance
