---
id: 405
issue_offer: pending
title: Follow-ups from Audit follow-ups chores for issue 354 (2026-11-13-audit-followups-165-chores)
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/405
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/405-landing-time-manifest-count-refresh
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261114-infra-405-manifest-counts-landing-refresh
north_stars: none
contract: .claude/concepts/2026-11-14-manifest-counts-landing-refresh.md
pr: pending
issue_link: unknown
status: designing
created: 2026-11-14
---

# Follow-ups from Audit follow-ups chores for issue 354 (2026-11-13-audit-followups-165-chores)

## Problem statement
The contract `.claude/concepts/2026-11-13-audit-followups-165-chores.md` (work item #354) pinned the skill and agent counts in the four plugin manifest descriptions against the tree, the same way `HookCountTests` already pins the hook count. The continuous-integration `tests` job runs that pin on every pull request, including a sub-task pull request into a parent branch. A sub-task may not list a manifest, and the landing's version raise writes only the version fields. So a multi-sub-task contract that adds a skill, an agent or a hook turns the `tests` job red on its sub-task, and no reviewed route (a sub-task or the landing) can correct a manifest description. The owner answered on 2026-11-13 that real counts stay in the descriptions and the refresh at landing time is designed separately. This item is that design and its delivery.

Source: issue #405 and the follow-up stub `.claude/concepts/followups/2026-11-13-manifest-counts-under-parent-branch.followup.md`.

## Acceptance criteria
- [ ] A count refresh runs at landing time: the landing rewrites the skill, agent and hook counts in the four manifest descriptions from the count oracles (`count_oracles`), in the same commit as the version raise (the stub's design (a), chosen by the owner).
- [ ] A check in the style of the existing `--exact` mode verifies, after the refresh, that every description count equals the tree.
- [ ] The design makes both owner-only exits of the stub unnecessary: no sub-task pull request or landing pull request has to merge with the `tests` job red, and no single-block recount pull request has to follow the landing.
- [ ] The design says how a parent branch still in flight on the day this ships is handled.
- [ ] Failure path: when a description holds no recognizable count, or a count cannot be read from the oracles, the landing stops with a named error and writes nothing, instead of writing a wrong number.
- [ ] Tests cover the refresh, the check, the failure path, and the repository consistency pin, and the existing suites for the touched scripts still pass.

## Out of scope
- Number-free manifest descriptions (design (b)), declined by the owner on 2026-11-13.
- Changing which counts the descriptions carry, or any other text in the manifests.
- Any other landing change that the stub does not name.

## Known context
- Parent / epic: contract `.claude/concepts/2026-11-13-audit-followups-165-chores.md`, work item #354 (shipped as pull request #406)
- Related items: #354, #165, #406; journal entries 2026-10-30 (two entries), 2026-11-02 and 2026-11-07 named in the stub
- Affected areas (best guess, to be confirmed by the contract): `.claude/scripts/check_version_bump.py` (`--raise`), `.claude/scripts/land_contract.py` (P7b), `.claude/scripts/tests/test_repo_consistency.py`, and the four manifests `plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`; mechanism `Plugin version check modes`. Because these are shipped plugin files, the plugin mirror and a version raise are likely part of delivery.

## North-star alignment
- none — the register holds no active thought (`.claude/north-stars/` does not exist)

## Open questions from intake
- Which design? → **Answer (from the stub, no blocking question):** design (a), real counts rewritten by the landing, as the owner chose on 2026-11-13.
- Single block or several? → **Answer (assumed):** left to the architect. The manifests are version files a sub-task may not list, so the architect must justify any split against the `sub-task-raises-version` rule; the owner decides at the contract gate.

## Size
M — changes the landing and the version-check script, adds tests, touches shipped plugin files and their manifests; delivery machinery with its own design.

## Routing
non-trivial → /design-first
