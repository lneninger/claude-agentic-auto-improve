---
id: 305
issue_offer: opened
title: Fix the t11 review findings
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/305
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t13-fix-the-t11-review-findings
worktree: none
north_stars: inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md
parent_issue: 235
base: fix/235-domain-split-registries
contract: .claude/concepts/2026-11-04-domain-split-registries.md
issue_link: deferred
status: implementing
created: 2026-11-07
---

# Fix the t11 review findings

## Problem statement
Sub-task 13 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235), added by amendment 5. The contract's handoff block below is the whole specification.

## Acceptance criteria
### 13. Fix the t11 review findings (`python-ai-developer`)

**Depends on:** 12

**Files to touch:**
- `.claude/scripts/accuracy_update.py`
- `.claude/hooks/tests/test_journal_post_approval_tracker.py`
- `README.md`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/JOURNAL.md`

**Pre-written TASK block:**
```
TASK: Fix t11 W1 (the degraded tracker must seed nothing), fix t11 N2 (exit 2 also means plan-build-failed) in the
  README and the "Registry migration runner" entry, and, as a second stated purpose, append the amendment-5 lesson
  batch (the t11 lesson, the landing lesson and the three amendment-5 critique lessons).
CONTEXT: concept contract amendment 5 ("Amendment 5 record"), "Import chain", Events I-14; review
  .claude/reviews/2026-11-04-domain-split-registries/t11-review-fullstack-code-reviewer.md (W1, N2, Disposition).
FILES: as listed.
CONSTRAINTS:
  - Run first, from the parent tip, and stop with a report if it fails: git fetch origin ; git merge-base
    origin/master origin/fix/235-domain-split-registries. The printed commit must not be 9a1b452a (9a1b452a means
    sub-task 12's merge reached the parent branch without its origin/master parent: squashed or rebased). Then git
    rev-list --parents -n 1 <t12 merge commit, named in t12's report> prints three hashes, and git merge-base
    --is-ancestor <t12 merge commit> origin/fix/235-domain-split-registries exits 0. Put the outputs in the pull
    request.
  - Cut this branch from the parent branch after sub-task 12's pull request merged (Depends on 12). It runs on the
    merged tracker, which already uses rl.source_value.
  - Why the lessons are here and not in block 12 (default-branch JOURNAL 2026-11-02 "Keep a review-fix block to the
    review's findings"): every journal append of amendment 5 is batched into one block after the merge, so block
    12's merge commit holds only resolutions and its rule (5) move, and the journal changes once. The batch is
    named in the TASK line as a separate purpose; it adds no code change.
  - W1: in accuracy_update.process_journal_change, before _load_seen(), check that _registry_layout can be imported.
    When it cannot: write one stderr line naming the module, log_event(hook="accuracy",
    event="journal-tracker-reader-missing", ...) (the default branch's event name, so log readers keep one name),
    and return [] without reading or writing the cache. Nothing is seeded, nothing fires, a fresh signature included.
    parse_journal_entries keeps its own fail-soft path for other callers.
    Extend test (d) (with _registry_layout hidden in a subprocess, temporary home): (d1) a cache that holds the file
    as seeded under the old reader (value true) is byte-identical after process_journal_change; (d2) with no cache,
    no cache file exists afterwards; (d3) then, in a fresh subprocess with the module present, an unrelated line is
    appended to the journal and the file is processed. Zero fires, and the file is now recorded {"reader": 2}. Keep
    the existing (d) assertions (_DEPS_OK of both hooks, record_clean, one stderr line), and assert the log event.
  - N2: README.md, at the migration procedure's refusal paragraph (t11 cites :1312-1316, re-find it after the
    merge): exit 2 is "a bad argument, or plan-build-failed (an exception while building the plan; the report is
    still written and names the error)". MECHANISMS: run registry_append.py --project . --registry mechanisms
    --correction-of "Registry migration runner" --source "t11 review N2", with an entry file saying that
    plan-build-failed exits 2 and writes the report with error, and that every other refusal exits 3. Never hand-edit
    the entry (I-7). Show the printed file:line.
  - Lessons: run registry_append.py --project . --registry journal --universal for (1) the t11 Disposition's
    "2026-11-07 — A fail-soft reader must not record "seen" for what it could not read", verbatim, and (2)
    "2026-11-07 — A parent branch that shares files with a moving default branch must take the default branch in
    through a sub-task before its landing". Trigger: post-impl divergence. Source contract: this contract.
    Lesson: the landing merges the default branch and resolves only union and regenerated paths. When the default
    branch rewrote a file the parent branch also rewrote (here the journal tracker, moved by each side onto a
    different shared reader), the landing halts. As soon as both sides touch one file, merge the default branch into
    the parent branch through a reviewed sub-task, decide which shared reader survives, and run the default branch's
    new suites there. Apply when: a contract delivered through a parent branch changes a file the default branch has
    changed since the parent branch was cut. Tags: parent-branch, landing, merge, shared-reader,
    unresolvable-conflict. Then, same command, Trigger: pre-approval critic, Source contract: this contract:
    (3) "2026-11-07 — Merge rules written for a long-lived branch must heed the default branch's journal, not only
    the branch's own". Lesson: a lesson the default branch added after the branch was cut is not in the branch's
    journal, yet it arrives with the merge and binds it; read the default branch's JOURNAL.md (git show
    origin/<default>:.claude/registries/JOURNAL.md) before writing conflict-resolution rules. Apply when: a
    contract writes rules for merging the default branch into a parent or other long-lived branch. Tags: merge,
    journal, parent-branch, conflict-resolution.
    (4) "2026-11-07 — No tool enforces how a pull request into a parent branch is merged; the next block must prove
    it". Lesson: the repository allows merge commit, squash and rebase, and the Merge-direction check judges only the
    target. When a sub-task's value depends on a merge commit (a merge of the default branch), say so to the owner
    in its pull request, and open the next block with a check from the parent tip that the default branch's merge
    base moved. Apply when: a sub-task's pull request must be merged with a merge commit. Tags: merge-method,
    parent-branch, squash, run-first.
    (5) "2026-11-07 — Adapters that rebuild an old reader over a stricter grammar must list every behaviour
    difference". Lesson: keeping the old reader's tests as acceptance tests proves only the forms those fixtures
    hold; read both readers side by side, list each form they read differently (fences, prose sections, legacy
    headings, continuation, field repeats), and pin each with a fixture row. Apply when: a contract replaces a
    reader's body with an adapter over another reader and keeps the old names. Tags: adapter, shared-reader,
    behaviour-difference, fixtures. Show each printed file:line.
  - Older-test search, one question per change, each with its own grep and result in the pull request: (1) tests that
    assert the cache after a run with _registry_layout missing; (2) tests that assert exit-2 wording in README or
    MECHANISMS; (3) tests that count journal entries on the live JOURNAL.md.
  - Version: no version file. Parent mode: check_version_bump.py --base origin/fix/235-domain-split-registries
    --default-branch master --head-ref <this task branch> exits 0 (the head's version equals the base's).
  - Run, every one exit 0: py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py ;
    py -3 .claude/scripts/tests/test_registry_entries.py ; py -3 .claude/scripts/tests/test_registry_layout.py ;
    py -3 .claude/scripts/tests/test_registry_append.py ; py -3 .claude/scripts/tests/test_plugin_text_scans.py ;
    py -3 .claude/scripts/validate_registries.py --check-structure --project . (same allowed lines as block 12).
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

## Out of scope
- Anything outside the files and constraints of the handoff block above.

## Known context
- Parent / epic: #235
- Related items: none
- Affected areas: see the handoff block's Files to touch

## North-star alignment
- inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md

## Open questions from intake
- none

## Size
Sub-task of an approved contract.

## Routing
task of .claude/concepts/2026-11-04-domain-split-registries.md - dispatched by /advance