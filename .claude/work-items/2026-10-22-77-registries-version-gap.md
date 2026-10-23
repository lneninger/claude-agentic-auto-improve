---
id: 77
issue_offer: pending
title: Version-bump check exempts registry files that the plugin copies into user projects
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/77
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: fix/77-registries-version-gap
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261022-bug-77-registries-version-gap
north_stars: none
contract: .claude/concepts/2026-10-22-registries-version-gap.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/78
issue_link: closes
status: shipped
created: 2026-10-22
---

# Version-bump check exempts registry files that the plugin copies into user projects

Raw invocation: `#77 (new worktree; do not offer to open another issue, the issue already exists)`

## Problem statement
The version-bump check (`.claude/scripts/check_version_bump.py`) lists `.claude/registries/` as a folder that never needs a plugin version raise. But the plugin's doctor script (`.claude/scripts/plugin_doctor.py`, requirement entries for `MECHANISMS.md`, `VOCABULARY.md` and `JOURNAL.md`) copies those three registry files into user projects. An edit to one of them therefore reaches users, yet triggers no version raise, so users who already installed the current version never receive the change. Verified against `origin/master` when the issue was filed. The issue has no comments and no labels.

## Acceptance criteria
Taken from the issue body:
- [ ] A test fails if any file the doctor copies into user projects is classed as not shipped.
- [ ] The exempt list and the doctor's copy list agree.
- [ ] The decision on how often registry appends should raise the version is written down.

## Out of scope
- `.claude/orchestrator/state/`, which stays non-exempt by design.
- The README hooks count.
- Anything else on the exempt list.

## Known context
- Parent / epic: none
- Related items: pull request 75 (exempted `.claude/orchestrator/results/` and `.claude/reviews/`; its reviewer found this gap), issue 77 is this item
- Trade-off the issue names: registry entries are also appended during ordinary work, so making the whole folder non-exempt would demand a version raise for every append. The contract has to decide this.
- Affected areas (best guess): `.claude/scripts/check_version_bump.py`, `.claude/scripts/plugin_doctor.py` (read only), `.claude/scripts/tests/test_check_version_bump.py`, the four manifests (version raise)

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- How should the exempt list treat the three copied files while the folder's other files stay exempt, and does an append to them need a version raise? → **Answer:** this is the design decision the issue's third criterion asks for. It goes to the contract as an open question with a recommendation, for the user to answer at the approval gate.
- Which version number? → **Answer (assumption):** master's current version plus one patch, read at implementation time. Master is at 0.9.17, so 0.9.18.

## Size
M — a policy decision, a change to a shipped script's classification rule, and a new test that couples two scripts.

## Routing
non-trivial → /design-first
