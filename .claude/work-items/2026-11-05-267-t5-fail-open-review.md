---
id: 267
issue_offer: opened
title: Fail-open review
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/267
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-05-codegraph-hooks-redesign/t5-fail-open-review
worktree: none
north_stars: inherited from .claude/work-items/2026-11-05-261-codegraph-hooks-redesign.md
parent_issue: 261
base: feature/261-codegraph-hooks-redesign
contract: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/284
issue_link: deferred
status: shipped
created: 2026-11-05
---

# Fail-open review

## Problem statement
Sub-task 5 of the approved contract `.claude/concepts/2026-11-05-codegraph-hooks-redesign.md` (parent issue #261). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 5. Fail-open review (`fullstack-code-reviewer`)

**Depends on:** 1, 2, 3, 4

**Preconditions:** issue #259 delivered: its pull request merged into master, and master merged into feature/261-codegraph-hooks-redesign

**Files to touch:**
- `.claude/reviews/2026-11-05-codegraph-hooks-redesign/t5-fail-open-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 1-4 for fail-open safety and contract conformance, and write the review artefact.
CONTEXT: contract .claude/concepts/2026-11-05-codegraph-hooks-redesign.md; the t1 and t3 artefacts.
FILES: .claude/reviews/2026-11-05-codegraph-hooks-redesign/t5-fail-open-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check by name:
    (1) every shadow failure path allows and cannot alter exit code, stdout, stderr or the Session folder (S-3);
    (2) G-2: the shadow runs after a pure Live plan and before its effects, also on blocked calls, and never
        consumes or writes a ticket or flag;
    (3) G-1: the reorder and lazy imports keep outcomes and the fallback banner;
    (4) the corrupt-transcript test exists and passes, and the read is a true tail read;
    (5) the Baseline suites pass and are unedited (diff them against master after the #259 merge, not 3f795ae);
    (6) the log holds no path or prompt text, and nothing is written when CLAUDE_PROJECT_DIR is unset;
    (7) update replaces only released hashes;
    (8) both cost numbers, and the shadow's added cost, are recorded;
    (9) each of the five live points is answered or covered by fail-open, and point (f) is recorded;
    (10) the registries carry the proposed terms if accepted.
  - Six fixed sections, the commit range base..head, and the verdict line alone, exactly one of
    "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked". The file does not exist
    yet; you create it.
  - Write the Gate Output beside it, listing every Review checklist item verbatim.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
  contract_status: approved
```

---

## Routing
task of .claude/concepts/2026-11-05-codegraph-hooks-redesign.md - dispatched by /advance
