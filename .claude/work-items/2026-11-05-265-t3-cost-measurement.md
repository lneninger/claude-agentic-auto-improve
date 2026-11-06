---
id: 265
issue_offer: opened
title: Cost measurement
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/265
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-05-codegraph-hooks-redesign/t3-cost-measurement
worktree: none
north_stars: inherited from .claude/work-items/2026-11-05-261-codegraph-hooks-redesign.md
parent_issue: 261
base: feature/261-codegraph-hooks-redesign
contract: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/277
issue_link: deferred
status: shipped
created: 2026-11-05
---

# Cost measurement

## Problem statement
Sub-task 3 of the approved contract `.claude/concepts/2026-11-05-codegraph-hooks-redesign.md` (parent issue #261). The contract is authoritative.

## Acceptance criteria
The contract's own handoff block, verbatim:

### 3. Cost measurement (`python-ai-developer`)

**Depends on:** 1, 2

**Preconditions:** issue #259 delivered: its pull request merged into master, and master merged into feature/261-codegraph-hooks-redesign

**Files to touch:**
- `.claude/hooks/tests/bench_codegraph_guard.py`
- `.claude/scripts/codegraph_shadow_report.py`
- `.claude/scripts/tests/test_codegraph_shadow_report.py`
- `.claude/reviews/2026-11-05-codegraph-hooks-redesign/t3-cost-measurement-python-ai-developer.md`

**Pre-written TASK block:**
```
TASK: Measure the cost per call of the old and new designs, and write the read-only shadow report.
CONTEXT: contract (Shadow report, Q2, Q5, Alternatives rows 2-6).
FILES: see Files to touch.
CONSTRAINTS:
  - The bench runs each case 30 times in fresh processes, on the #259 guard (copied from master into a temp
    folder, "old") and on this branch's guard ("new"): allowlisted target; gated target with marker present;
    gated target with marker absent; and, new only, transcript open with warm and cold cursor at 1, 10 and 50 MB.
    Also a reset hook start and a tracker start. The old/new delta on the allowlisted and marker-present cases is
    the shadow's added cost (log append included) net of the G-1 saving; report it separately. p50 and p95 in ms,
    with Python version, OS and machine.
  - The report follows the Report the shadow command. Exit 2 on a missing or unreadable log. Its tests use a
    fixture log covering every outcome, a block plus retry pair, blocks per tool, session_seen, malformed lines,
    torn lines and two log-full lines.
  - The artefact (six sections) records both designs' numbers and the per-turn comparison Q2 names. Verdict: pass
    when every case was measured. Otherwise blocked. Never pass-with-findings. Copy the table into the pull request.
  - Write the Gate Output beside the artefact. Run test_plugin_manifests.py and test_plugin_text_scans.py.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
  contract_status: approved
```

## Routing
task of .claude/concepts/2026-11-05-codegraph-hooks-redesign.md - dispatched by /advance
