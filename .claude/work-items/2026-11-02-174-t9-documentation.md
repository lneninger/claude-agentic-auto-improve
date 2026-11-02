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
pr: UNKNOWN
issue_link: unknown
status: implementing
created: 2026-11-02
---

# Documentation

## Problem statement
Sub-task 9 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 9. Documentation (`python-ai-developer`)

**Depends on:** 5, 8

**Files to touch:**
- `README.md`
- `CONTRIBUTING.md`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`

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
  and the existing guards; cloud-management MCP deferred). Update the
  README skill and agent counts. In CONTRIBUTING, add the rule: no shipped file (check_version_bump
  is_shipped) but memory_boundary.py names a memory tool. Append the Memory adapter entry to the Universal
  tier of MECHANISMS.md and the confirmed terms (Business Concept list) to VOCABULARY.md.
CONTEXT: concept contract (whole).
FILES: the four listed.
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
