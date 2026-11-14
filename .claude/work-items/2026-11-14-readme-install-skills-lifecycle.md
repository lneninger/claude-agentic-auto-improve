---
id: none
issue_offer: pending
title: Redesign the README installation experience around every install skill
type: DOCS
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/readme-install-skills-lifecycle
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261114-feature-readme-install-skills-lifecycle
north_stars: none
contract: none
pr: none
issue_link: unknown
status: clarified
created: 2026-11-14
---

# Redesign the README installation experience around every install skill

## Problem statement
Draft PR 409 (merged) made installation one contiguous section, but it documents only the finish-install skill and the database-guard skill in the main flow; the three add-on install skills appear only in the add-on section further down. The operator wants every skill whose name ends in `-install` in the main installation documentation, classified (required, conditional, optional), ordered by real dependencies and described attribute by attribute, with prerequisites first and the plugin-resources catalogue only after installation, verification and first use. The request text is recorded verbatim in the work item's invocation.

## Acceptance criteria
- [ ] The installation section lists every skill that ends in `-install`, found by listing `skills/` (five at intake: `auto-improve-finish-install`, `auto-improve-database-guard-install`, `auto-improve-angular-tailwind-install`, `auto-improve-codegraph-install`, `auto-improve-strict-shell-gate-install`), each with a classification (required, conditional or optional) and these attributes: exact invocation, purpose, when to run, prerequisites, actions, files affected, whether confirmation is asked, expected result, next step.
- [ ] The execution order follows the real prerequisites read from the skills and the install script (not alphabetical), shows the conditional branches, and says which skills are independent of each other.
- [ ] A Prerequisites subsection (tools, providers, compatibility) precedes the provider commands, and only states facts found in the source.
- [ ] Installation is ordered: Prerequisites, Install the plugin, Complete installation with the install skills, Verify, Start using `/flow`, ending in a checklist that covers required, conditional and chosen optional skills.
- [ ] A "Plugin resources" section (skills by intent, agents, hooks, MCP integrations, project configuration) comes after the first-use instructions and links back to the install skills without becoming their only documentation. The catalogue distinguishes installation, operational, specialized and maintenance skills.
- [ ] Order is: Overview, Installation, Plugin resources, Updating an installed plugin, Managing optional add-ons and retired hooks (immediately after Updating), vendoring quick start, configuration and advanced usage, troubleshooting.
- [ ] Updating says whether any install skill must be re-run, separating the plugin update, re-running initialization and updating add-ons.
- [ ] Troubleshooting is a symptom-to-investigation table (including "`/flow` unavailable") that links to the existing recovery material.
- [ ] No unrelated documentation is deleted, nothing is invented, every internal link and anchor resolves, and the suites that read the README stay at their baseline (only the four checks that already fail on master may fail).
- [ ] Only `README.md` changes (plus this brief).

## Out of scope
- Changing plugin runtime code, manifests, hooks or skills, or the stale wording found inside skills (reported instead).
- Version bump: `README.md` is exempt from the bump gate.

## Known context
- Parent / epic: none
- Related items: PR 409 (merged), the previous README refactor
- Affected areas (best guess): `README.md` only

## North-star alignment
- none — the register holds no active thought (`.claude/north-stars/` does not exist)

## Open questions from intake
- Base branch: the invocation asked to build on PR 409, but that PR merged, so the base is `origin/master`. → **Answer:** taken, stated here.
- Size and route: single-file documentation change with no data shape or mechanism, sized S, no contract. → **Answer:** assumed, as for the first README change.
- Whether the three `*-uninstall` skills count: their names end in `-uninstall`, not `-install`. → **Answer:** not counted as install skills; each install skill row names its uninstall skill.
- Tracker issue: free-text work, no issue. → **Answer:** offer left `pending`; `/ship` asks once.

## Size
S — one markdown file, no data shape, no new mechanism; `.md` is exempt from the concept gate. Large in effort, small in design risk.

## Routing
direct implementer (no `/design-first`)
