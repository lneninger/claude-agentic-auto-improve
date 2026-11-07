---
id: 174
issue_offer: opened
title: Documentation
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/174
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t9-documentation
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/216
issue_link: deferred
status: shipped
created: 2026-11-02
---

# Documentation

## Problem statement
Sub-task 9 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 9. Documentation (`python-ai-developer`)

**Depends on:** 13, 14, 15, 16

**Files to touch:**
- `README.md`
- `CONTRIBUTING.md`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `.claude/registries/JOURNAL.md`

**Pre-written TASK block:**
```
TASK: Document the architecture (one diagram of the delivery chain with the two memory call sites:
  /design-first Step 1.5, and the separate capture question after the flip in /pr-merged or /flow), the memory boundary, the
  configuration slots, MCP integration (main session only, tool names in slots, shapes in one script,
  one attempt bounded by the host MCP timeout), lifecycle separation, the cloud capability with its scope
  rule (it never runs live-changing commands, hands them to the user, and adds no permission mechanism),
  and Known limitations (shape v0 provisional; no capture retry; changed items found only when
  re-returned; an empty project-name token list keeps all capture project-scoped; Cursor and Codex MCP
  naming untested; the cloud scope rule is enforced in text only, by the user's own permission prompts
  and the existing guards; cloud-management MCP deferred; AND, from review I3 of the t5 review: the
  mcp__<server>__<tool> id form and the host MCP timeout returning an error are unverified, because the
  block 3 stub-server trials left no recorded evidence, so a project should not set memory.shape until
  that trial is run). Document the Project history record (Revision 7) exactly as the Business Concept
  term defines it: what it holds, that /design-first and the data-architect read it, which confirmed
  steps append to it, and that the Central Memory System only supplements it; do not claim that every
  flow reads or appends it. Update the README skill and agent counts, and the working-agreement count and
  list (README "6 working agreements" rows and the agreements paragraph) to seven, naming the block 15
  agreement. In CONTRIBUTING, add the rule: no shipped file (check_version_bump
  is_shipped) but memory_boundary.py names a memory tool. Append the Memory adapter entry to the Universal
  tier of MECHANISMS.md and the confirmed terms (Business Concept list, including Project history record)
  to VOCABULARY.md. Append to JOURNAL.md the entry the t5 review's Disposition item 6 drafts ("A skill
  written around an adapter refusal hides a contract divergence"), verbatim, plus the pre-approval critic
  entries the user confirmed for the Revision 7 critique, as the main session records them at approval.
CONTEXT: concept contract (whole); the t5 review at
  .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t5-review-memory-boundary-fullstack-code-reviewer.md
  (I3 and Disposition items 5 and 6) and the block 16 re-review.
FILES: the five listed.
CONSTRAINTS: plain language; no version files; counts must match skills/ and agents/. README and
  CONTRIBUTING are exempt from the single-adapter scan by is_shipped, so they may name the two tools.
  Registry appends are append-only and go in the Universal tier. The registries are shipped and are
  NOT exempt from the scan: the Memory adapter entry and every memory term say "the configured retrieve
  tool" and "the configured capture tool", never the literal names. Run test_plugin_text_scans.py after
  the appends.
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
