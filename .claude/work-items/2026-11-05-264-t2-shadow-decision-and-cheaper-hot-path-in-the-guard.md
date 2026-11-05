---
id: 264
issue_offer: opened
title: Shadow decision and cheaper hot path in the guard
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/264
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-05-codegraph-hooks-redesign/t2-shadow-decision-and-cheaper-hot-path-in-the-guard
worktree: none
north_stars: inherited from .claude/work-items/2026-11-05-261-codegraph-hooks-redesign.md
parent_issue: 261
base: feature/261-codegraph-hooks-redesign
contract: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-05
---

# Shadow decision and cheaper hot path in the guard

## Problem statement
Sub-task 2 of the approved contract `.claude/concepts/2026-11-05-codegraph-hooks-redesign.md` (parent issue #261). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 2. Shadow decision and cheaper hot path in the guard (`python-ai-developer`)

**Depends on:** 1

**Preconditions:** issue #259 delivered: its pull request merged into master, and master merged into feature/261-codegraph-hooks-redesign

**Files to touch:**
- `.claude/addons/codegraph/hooks/codegraph-first-guard.py`
- `.claude/addons/codegraph/hooks/codegraph-turn-reset.py`
- `.claude/hooks/tests/test_codegraph_shadow.py`

**Pre-written TASK block:**
```
TASK: In the guard: reorder and lazy-import per G-1; split the decision into a pure Live plan and its effects per
G-2; add the shadow section between them (Transcript cursor, entry classifier per the t1 artefact, Shadow
decision S-1..S-4, Shadow record, log location and 10 MB stop). Add transcript-cursor.json to the reset hook's
pruner names.
CONTEXT: contract Data Shapes (Guard order), Failure Modes, Alternatives rows 1, 5, 6; the t1 artefact; the merged
  #259 decision order (re-read it before writing G-1/G-2).
FILES: see Files to touch.
CONSTRAINTS:
  - STOP rule: if the merged #259 order, step numbers or side-effect profile differ materially from G-1/G-2 as
    written, stop before writing code and return to the user. Do not redesign.
  - /tdd-first: write test_codegraph_shadow.py RED first. One test per path: open, closed, each unknown cause
    (incl. a non-regular transcript_path and time-exceeded), subagent, allowlisted, not-computed, cursor rescan on
    rewrite or shrink, a corrupt cursor, partial last line, true tail read (a large transcript reads at most the
    limit), a hit limit with a boundary found answers window-exceeded, a line over 2 MB is skipped and counted,
    no cursor read or write when step 0 failed open (link or junction folder), log-full, the pruner keeping the
    cursor and its temp file known, turn_marker null on a step-0 allow, and a CORRUPT transcript (fail-open).
  - G-2 tests: a matching ticket is consumed exactly once (by the live path) and the record shows
    retry-escape-used; a ticket gone at apply keeps the allow; the shadow writes no availability.json; a blocked
    call (exit 2) still writes its record; with the shadow forced to raise an Exception and a SystemExit, exit
    code, stdout and stderr are byte-identical to a run without it, and the Session folder is equal (same file
    names and contents, ignoring the ticket ts, availability.json checked_at, and transcript-cursor.json and its
    temp files), on an allowed and on a blocked call.
  - G-1 tests: with the marker present, a source Read leaves _project_paths unimported, observed in a fresh
    subprocess that loads the guard, runs it on that payload (catching SystemExit) and prints whether
    _project_paths is in sys.modules; decide() keeps its signature and effects.
  - Log tests: CLAUDE_PROJECT_DIR unset writes no record and nothing under the home folder; no path or prompt text
    in the log; the two-process test starts the writers behind a multiprocessing barrier over many rounds and
    asserts only what holds under every interleaving: the cursor parses, every line is whole or counted
    malformed by the report, and records never exceed writes. It never asserts that no record was lost.
  - Do not edit the Baseline suites (test_codegraph_first_guard.py, test_worktree_path_guards.py, test_addons.py
    on master after #259). Run all three; they pass unchanged, including the getattr parity and load_hook rows.
    Nothing new is printed. No environment variable is added.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-11-05-codegraph-hooks-redesign.md - dispatched by /advance
