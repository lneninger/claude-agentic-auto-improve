---
id: 167
issue_offer: opened
title: Memory adapter and degradation tests
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/167
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t2-memory-adapter-and-degradation-tests
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/179
issue_link: deferred
status: shipped
created: 2026-11-02
---

# Memory adapter and degradation tests

## Problem statement
Sub-task 2 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 2. Memory adapter and degradation tests (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/scripts/memory_boundary.py`
- `.claude/scripts/tests/test_memory_boundary.py`
- `.claude/scripts/tests/test_plugin_text_scans.py`
- `.claude/scripts/generate_registry_digest.py`
- `.claude/hooks/journal-post-approval-tracker.py`
- `.claude/scripts/tests/test_registry_entries.py`

**Pre-written TASK block:**
```
TASK: Write memory_boundary.py with the subcommands status, retrieve-request, normalise, capture-candidates,
  capture-request, record, check-contract and changed-items, exactly as the contract's Commands table
  defines them, plus shape profile v0, marked provisional. The default tool names memory_retrieve and
  memory_capture live ONLY here. Tests first.
CONTEXT: concept contract (Data Shapes incl. "Candidate reading", "Provenance mapping", "Duplicate
  protection"; Commands; Failure Modes).
FILES: the six listed.
CONSTRAINTS:
  - Extend the shared registry reader in generate_registry_digest.py: add entry_blocks(text, pattern,
    per_domain=False) and journal_entries(text, per_domain=False) exactly as "Candidate reading" defines
    them. Both take TEXT (full own text, indented sub-bullets with lines; tier from the text's own
    headings; an entry before any tier heading is Project; per_domain=True makes all Project;
    sig/trigger/source). Rewrite tier_split(path, pattern) as read() then entry_blocks, keeping its
    signature and (title, line) shape. Byte-identical test: keep the pre-change tier_split verbatim in
    the test; run main() with cwd set to a temporary copy of the registries, once patched to the old
    function and once with the new; compare the two outputs byte for byte, on the current registries and
    on fixtures with a pre-heading entry and Correction sub-bullets. No golden file.
  - journal-post-approval-tracker.py: parse_entries(text) keeps its signature and becomes a thin caller of
    journal_entries(text), returning the keys it returns today, imported
    normally from the scripts folder and bound with getattr after a fail-soft import (a missing reader
    makes the hook skip and log). No other behaviour change except the listed Source forms.
  - test_registry_entries.py: Correction sub-bullets attach to their parent; a bullet ends at the next
    top-level match or heading; journal tier from "## Universal" / "## Project:" and per-domain files;
    Source contract with spaces, N/A, none, empty, placeholder and an absolute Windows path; the
    hook's sig/trigger/source on the current JOURNAL.md equal the old regex output except those forms.
  - memory_boundary.py imports load_slot and select_linked_brief from pr_merged, entry_blocks and
    journal_entries from generate_registry_digest, and is_shipped from check_version_bump. All are
    fail-soft and bound with getattr; append to sys.path, never insert. It never loads the hook file and
    parses no registry text itself.
  - Candidates only from entries whose OWN line names the contract (journal Source line; bullet text
    without sub-bullets); a naming Correction is its own correction-entry and never makes its parent one.
  - capture-candidates takes --run-report (the live writing run's JSON). It refuses not-flipped and
    brief-not-carried before producing anything; source-code-fact rests on that report's flipped verdict.
  - Every subcommand takes --project explicitly; never search for a profile or the token list.
  - status always exits 0. Profile absent, slot unset and placeholder all read "disabled"; test each.
  - record with state "disabled" refuses "not-enabled" and writes nothing (test: brief bytes unchanged).
    record --receipts takes --run-report <the report> and refuses "brief-not-carried" unless the brief is
    in that report's written_files.
  - The id/version pattern excludes "@". normalise keeps at most the first 8 accepted items (server
    order) and counts the rest as over-limit; test with a server response of 20 items.
  - normalise applies the per-field rules of the "Retrieved memory item" row to EVERY field; a test probes
    each field with a line separator, "## ", "|" and a backtick. Key = id+version; first wins.
  - Provenance exactly as the table: manual/post-approval give ai-hypothesis; test-confirmed is never
    produced. capture-request refuses ai-hypothesis and any status other than proposed.
  - Scope safety reads <project>/.claude/.project-tokens.json only. A token hit lowers to project; a
    missing or empty list lowers every candidate. Test both, plus a hit, with decoys in other locations.
  - Name matching: the stem rule with "/" and "\" separators; test an absolute Windows Source contract.
  - Single-adapter scan in test_plugin_text_scans.py: walk the named shipped folders listed in Extension
    Points from Path(__file__).parents[3] (never cwd, never a walk from the repo root), exclude every path
    with a .claude/worktrees/ segment, then filter by is_shipped(). Only .claude/scripts/memory_boundary.py
    may contain memory_retrieve or memory_capture. Positive controls: a planted made-up shipped-path file
    is caught; a planted copy under .claude/worktrees/x/ is ignored.
  - Run the existing suites in .claude/scripts/tests and .claude/hooks/tests; all must pass.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```


## Out of scope
- Everything outside this sub-task's handoff block; see the other sub-tasks of the contract.

## Known context
- Parent / epic: #161 (https://github.com/lneninger/claude-agentic-auto-improve/issues/161)
- Related items: the other sub-tasks of `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`
- Affected areas: the files named in the handoff block

## North-star alignment
- inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md

## Open questions from intake
- none; the sub-task's criteria were approved at the contract gate.

## Size
Task of .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md.

## Routing
task of .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md - dispatched by /advance
