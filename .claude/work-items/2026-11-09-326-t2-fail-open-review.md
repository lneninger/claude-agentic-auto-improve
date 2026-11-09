---
id: 326
issue_offer: pending
title: Fail-open review
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/326
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-09-codegraph-hooks-cutover/t2-fail-open-review
worktree: none
north_stars: inherited from .claude/work-items/2026-11-09-262-codegraph-hooks-cutover.md
parent_issue: 262
base: feature/262-codegraph-hooks-cutover
contract: .claude/concepts/2026-11-09-codegraph-hooks-cutover.md
pr: UNKNOWN
issue_link: unknown
status: implementing
created: 2026-11-09
---

# Fail-open review

## Problem statement
Sub-task 2 of the approved contract `.claude/concepts/2026-11-09-codegraph-hooks-cutover.md` (parent issue 262). An independent review of sub-task 1 for fail-open safety, upgrade safety and contract conformance. It depends on sub-task 1 (issue 325).

## Acceptance criteria
The contract's own approved handoff block, copied verbatim below. The contract is authoritative.

## Out of scope
- Writing or changing production code or tests; this is a review gate that writes only its review artefact and Gate Output.

## Known context
- Parent / epic: issue 262, parent branch `feature/262-codegraph-hooks-cutover`.
- Related items: sub-task 1, issue 325.

## North-star alignment
- inherited from the parent brief `.claude/work-items/2026-11-09-262-codegraph-hooks-cutover.md` (the register holds no active thought).

## Open questions from intake
- none: skipped in parent-aware mode.

## Size
Not sized here: parent-aware mode.

## Routing
task of .claude/concepts/2026-11-09-codegraph-hooks-cutover.md — dispatched by /advance

## Handoff block (verbatim from the contract)

### 2. Fail-open review (`fullstack-code-reviewer`)

**Depends on:** 1

**Files to touch:**
- `.claude/reviews/2026-11-09-codegraph-hooks-cutover/t2-fail-open-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review block 1 for fail-open safety, upgrade safety and contract conformance, and write the review artefact.
CONTEXT: concept contract .claude/concepts/2026-11-09-codegraph-hooks-cutover.md; block 1's pull request body (live smoke).
FILES: .claude/reviews/2026-11-09-codegraph-hooks-cutover/t2-fail-open-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check by name, each with its own outcome:
    (1) every unknown transcript cause allows with a logged reason, and nothing in the read can block on a guess;
    (2) C-1 order, incl. the unusable-folder rule (Q3 as answered) and no fail-open line on an allowlisted target;
    (3) C-2: no effect after the ticket can change exit code or stderr;
    (4) the block rows of the three named suites keep their assertions and gained a closed transcript (diff them);
    (5) the Bash route uses the strict Counted test, not the row's if;
    (6) tickets keyed to the prompt; an old ticket reads as absent;
    (7) the prompt row always exits 0, prunes once, keeps the notice outcomes;
    (8) retire runs in two steps (C-8): no run deletes a file whose row it removes; step B deletes only released
        copies and keeps edited ones; settings.local.json rows and edited copies at step A are refused; dangling
        rows are removed; angular-tailwind is covered; the revert-manifest test passes;
    (8a) C-7: a dispatch in the current turn reads open, and the smoke cases where the rules disagree were run
        with the expected outcomes;
    (9) released hashes: the tracker's and reset's cover every released copy, the cut-over guard's matches the
        final file;
    (10) the live smoke was run and recorded; re-run any step you can;
    (11) the report's enforced section and shadow sections are separate;
    (12) every entry in the contract's "Registry amendments at review" list is appended (VOCABULARY, MECHANISMS),
        each one checked against its cited line.
  - Six fixed sections; the commit range base..head; the file does not exist yet, you create it; "## Evidence"
    carries commands with exit codes. End the header with the verdict line alone, exactly one of
    "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked".
  - Also write the Gate Output (<artefact stem>.gate.json) beside it, listing every Review checklist item verbatim.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-09-codegraph-hooks-cutover.md
  contract_status: approved
```
