---
id: 51
issue_offer: pending
title: Follow-ups from Sub-issue titles carry their parent reference (2026-10-15-subissue-title-parent-ref)
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/51
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: fix/51-doctor-scaffold-parentlink
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261111-infra-51-doctor-scaffold-parentlink
north_stars: none
contract: none
pr: none
partial: true
issue_link: unknown
status: verifying
created: 2026-11-11
---

# Follow-ups from Sub-issue titles carry their parent reference

## Problem statement
A project set up by the plugin doctor gets a `.claude/work-item-conventions.json` scaffold that lacks the `issueLink.parentLink` block and ships `issueTitle.effortTypes` as an empty list. The parent-link verifier reports `unverifiable` (`conventions-missing`) and the sub-issue title helper refuses every title as `pattern-mismatch`, so Parent-aware mode cannot work in a doctor-built project.

## Acceptance criteria
- [ ] The doctor's scaffold for `.claude/work-item-conventions.json` carries an `issueLink.parentLink` block with the same keys as the plugin's own conventions file (`createFlag`, `editFlag`, `readCommand`, `parentListCommand`, `verdicts`).
- [ ] The scaffold's `issueTitle.effortTypes` holds the nine effort tags (FEATURE, BUG, IMPROVEMENT, REFACTOR, PERF, SECURITY, DOCS, CHORE, SPIKE) from the plugin's conventions file.
- [ ] A doctor test asserts the scaffold holds every block a shipped script reads.
- [ ] A doctor test runs `compose_subissue_title.py` against the scaffold's own output and gets a composed title, not `pattern-mismatch`.
- [ ] `verify_parent_link.py` loads the scaffold's parentLink block without `conventions-missing`.

## Out of scope
- Checklist item 1 of the issue: retitling the 37 existing sub-issues of #638 in `lneninger/StockToolScalpingMachine`. It edits shared issues in another repository and the issue itself says the operator decides when and whether. Not performed; issue #51 stays open for it.
- Any change to the plugin's own `.claude/work-item-conventions.json`.

## Known context
- Parent / epic: contract `.claude/concepts/2026-10-15-subissue-title-parent-ref.md`
- Detail: `.claude/concepts/followups/2026-10-15-doctor-scaffold-parentlink.followup.md`
- Affected areas: `.claude/scripts/plugin_doctor.py`, `.claude/scripts/tests/test_plugin_doctor.py`

## North-star alignment
- none: the register holds no active thought.

## Open questions from intake
- Should the retitle checklist item be part of this run? → **Answer (assumed, no blocking question):** no. The issue marks it as needing an operator decision and it edits another repository. The pull request uses `Refs #51` (`partial: true`) so #51 stays open.

## Size
S — one scaffold dictionary edit plus tests, no new data shape or mechanism.

## Routing
non-trivial gate not required → /tdd-first directly (no contract)
