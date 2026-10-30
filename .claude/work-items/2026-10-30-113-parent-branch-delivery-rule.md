---
id: 113
issue_offer: pending
title: A multi-sub-task contract is always delivered through a parent branch, and the version is raised once at landing
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/113
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/113-parent-branch-delivery-rule
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261030-feature-113-parent-branch-delivery-rule
north_stars: none
contract: .claude/concepts/2026-10-30-parent-branch-delivery-rule.md
pr: none
issue_link: unknown
status: implementing
created: 2026-10-30
---

# A multi-sub-task contract is always delivered through a parent branch, and the version is raised once at landing

## Problem statement
How a contract with several sub-tasks is delivered (through a parent branch, or one pull request each straight to the default branch) is decided by nobody. Contract 84 went through a parent branch. Contract 86 was drafted for the default branch, because a critic blocker about the version check was fixed with a per-sub-task version raise, and the contract template, the architect, the critic and the status script all stay silent about it. The status script falls back to the default branch without reporting a defect. The user's decision, 2026-10-30: the layout must be a rule and not a decision, and the version is bumped once, after the default branch is merged into the parent branch, against the default branch.

## Acceptance criteria
From the issue's Acceptance section, restated as testable conditions:
- [ ] A contract with two or more sub-tasks cannot reach `Status: approved` through `/design-first` while it plans a version raise per sub-task, plans sub-task pull requests to the default branch, or names no parent branch.
- [ ] `pr_merged.py --status` reports a defect for a multi-sub-task contract whose parent branch cannot be found, and never reports the default branch as a sub-task base for it.
- [ ] The version is raised exactly once, at landing, computed against the default branch after the default branch has been merged into the parent branch; a sub-task pull request into the parent branch does not raise it. A single-block contract still raises it in its own pull request.
- [ ] The contract template, `data-architect`, `contract-critic`, `/design-first` and `/flow` Step 2.7 state the rule; each change has a test.
- [ ] Contracts 84 and 86 stay consistent with the rule (86's Rule V is amended in its own work item, not here).

## Out of scope
- Amending contract 86 or opening its sub-issues (issue 86 stays paused until this lands).
- Changing what a single-block contract does.
- Any other `/flow` behaviour.

## Known context
- Parent / epic: none (follow-up found while running `/flow` on issue 86)
- Related items: #86, #84
- Affected areas (best guess, to be confirmed by the contract): `.claude/templates/concept-contract.md`, `agents/data-architect.md`, `agents/contract-critic.md`, `skills/design-first/SKILL.md`, `skills/flow/SKILL.md`, `.claude/scripts/pr_merged.py` and tests, `.claude/scripts/check_version_bump.py`, `CLAUDE.md`
- Evidence in the issue body: `pr_merged.py` `effective_base` around line 1500; contract 84's nine briefs (`parent_issue: 84`, `base: feature/84-...`).

## North-star alignment
- none — the register holds no active thought (`.claude/north-stars/` does not exist)

## Open questions from intake
- Is "bumped after the merge against master" read as: merge the default branch into the parent branch, then compute and commit the single raise against the default branch, then land? → **Answer:** Assumption, recorded in the issue: yes. The contract carries it as an Open Question for the user to confirm at the gate.
- Does the rule need a user choice anywhere? → **Answer:** No. The user decided the layout is a rule; the contract must not offer a choice.

## Size
L — touches the contract template, two agents, two skills, the delivery script, the version check and the project rules; changes a rule that governs every multi-sub-task contract.

## Routing
non-trivial → /design-first
