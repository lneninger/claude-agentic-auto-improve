---
id: 240
issue_offer: pending
title: Follow-ups from Domain-split registries (2026-11-04-domain-split-registries)
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/240
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: fix/240-inv-o1-parent-aware
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261110-chore-240-inv-o1-parent-branch
north_stars: none
contract: .claude/concepts/2026-11-10-inv-o1-parent-aware.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/344
partial: true
issue_link: refs
status: shipped
created: 2026-11-10
---

# Follow-ups from Domain-split registries (2026-11-04-domain-split-registries)

## Problem statement
The merge-base version row (INV-O1) in `test_plugin_manifests.py` demands that any tree differing from its merge base with `origin/master` carries a higher version in all five declarations. The project's Parent Branch Delivery Rule says a `task/<slug>/<id>` head into a parent branch must keep the version, because the landing raises it once. So every parent-branch sub-task that changes anything fails this row by construction. No configured gate runs the suite today, so the row is red and nothing reads it. Detail: follow-up stub `2026-11-07-inv-o1-parent-branch-conflict.followup.md` (committed on branch history at `7a0458f`, not yet on master).

The issue lists two checklist items. Item 1 (the PowerShell sync tool halting on a pending registry-layout migration) lives in a different repository that owns `tools/sync-plugin.ps1`; the issue itself says it cannot be done here. This run takes item 2 only.

## Acceptance criteria
- [ ] When the checked branch (HEAD's branch, or the `GITHUB_HEAD_REF` CI passes) matches `task/<slug>/<id>`, the INV-O1 row applies the parent-mode rule of `check_version_bump.py` (version equals the base's version, or the version at the merge base with the default branch) instead of demanding a raise.
- [ ] The row reuses `check_version_bump.py`'s parent-mode logic through one shared reader; no second copy of the rule.
- [ ] If the branch cannot be read, the row still FAILS and names the cause. It never skips.
- [ ] A fixture row proves a `task/` head whose version equals its base's version passes.
- [ ] A fixture row proves a default-branch head that changes files but keeps the version still fails.
- [ ] The full `test_plugin_manifests.py` run reports no failure on this branch.

## Out of scope
- Issue item 1: the sync tool (`tools/sync-plugin.ps1`, `.claude/.sync-config.json`, `tools/SYNC.md`). It belongs to another repository; the checkbox stays open on the issue, which is why `partial: true` (the pull request uses `Refs #240`, not a closing keyword).
- Making `test_plugin_manifests.py` a landing verification step in `work-item-conventions.json` (mentioned in the stub only as a conditional; not in the issue's item).
- Options (b) exempt `task/` heads and (c) drop the row.

## Known context
- Parent / epic: parent contract `.claude/concepts/2026-11-04-domain-split-registries.md` (branch `fix/235-domain-split-registries`)
- Related items: #235
- Affected areas: `.claude/scripts/tests/test_plugin_manifests.py` (INV-O1 block), `.claude/scripts/check_version_bump.py` (parent mode)
- Mechanism touched: the Parent Branch Delivery Rule (project `CLAUDE.md`)

## North-star alignment
- none, the register holds no active thought (`.claude/north-stars/` is empty or absent)

## Open questions from intake
- Which repository owns the sync tool? → **Answer (assumption, recommended by the issue itself):** not this repository, so item 1 is out of scope here and left open on the issue.
- Which option for the row? → **Answer (assumption):** option (a), the stub's own recommendation: make the row parent-aware.

## Size
M — touches the version rule's test and the shared parent-mode reader in `check_version_bump.py`, a mechanism the Parent Branch Delivery Rule depends on; unsure sizes are treated as non-trivial.

## Routing
non-trivial → /design-first

## Run log
- 2026-11-10: pull request #344 opened as a draft. Closing-link check returned `unexpected-closing-ref`: the brief is partial (issue #240 item 1 stays open, so the body says `Refs #240`), but GitHub reports #240 as a closing reference. Cause: the branch was created with `gh issue develop`, which registers it as the issue's linked branch, so merging would close #240. Status stayed `verifying` until the link was removed.
- 2026-11-10: the API cannot disconnect a pull request from an issue (the link had become a connected event; `deleteLinkedBranch` had no identifier to act on), so the owner removed #240 from the pull request's Development panel on GitHub. The closing-link check was re-run and returned `exempt-partial` (`issue_link: refs`); status set to `shipped`.
- 2026-11-10: merged and recorded (https://github.com/lneninger/claude-agentic-auto-improve/pull/344); contract 2026-11-10-inv-o1-parent-aware flipped to implemented by pr_merged.py; owner confirmed resolved: none; not performed and disclosed on #240: none
