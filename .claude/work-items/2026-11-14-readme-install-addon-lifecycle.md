---
id: none
issue_offer: pending
title: Refactor the README installation documentation and add-on lifecycle
type: DOCS
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/readme-install-addon-lifecycle
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261114-feature-readme-install-addon-lifecycle
north_stars: none
contract: none
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/409
issue_link: none
status: shipped
created: 2026-11-14
---

# Refactor the README installation documentation and add-on lifecycle

## Problem statement
The README buries add-on installation ("To install one in a project") inside "Retired hooks, and how to restore one", and splits plugin installation, project setup and first use across distant sections. A developer cannot install the plugin, finish project configuration and start using `/flow` by following one contiguous section. The README must be reorganised around the lifecycle of using the plugin, with the implementation (not the old README text) as the authority.

## Acceptance criteria
- [ ] One contiguous Installation section covers provider install (Claude Code, OpenAI Codex, Cursor), `### Complete the installation in your project` (five sequential steps: what installation provides, session start, `/auto-improve-finish-install`, hook verification, first `/flow`), and ends with a completion checklist.
- [ ] Every statement about install, setup, hooks, sessions, add-ons and uninstall is verified against the source (skills, scripts, hooks, manifests); where README and source disagree, the README is corrected to match the source.
- [ ] `### Managing optional add-ons and retired hooks` sits immediately after `Updating an installed plugin`, with one table (Add-on, Assets / hook files, Functionality, Why opt-in, Install command, Uninstall command) covering `angular-tailwind`, `codegraph`, `strict-shell-gate` and any further add-on found in the repository.
- [ ] That section also holds the install procedure, the uninstall procedure with its safety guarantees, retired-hook history (including `plan-question-advisor.py`), and recovery steps. "To install one in a project" is no longer a sub-part of the retired-hooks section.
- [ ] Plugin installation and vendoring are clearly separated; the existing vendoring quick start keeps its details and states its scope.
- [ ] `Updating an installed plugin` states per provider how to update, whether finish-install is re-run, what happens to add-ons, whether a new session is needed and how to validate, without mixing in add-on updates.
- [ ] No unrelated README content is deleted; no command, filename or guarantee is invented; no duplicate or contradictory install procedure remains.
- [ ] Every internal Markdown link and heading anchor in the README resolves.
- [ ] Only `README.md` changes, unless a documentation discrepancy forces a clarification elsewhere (reported if so).

## Out of scope
- Changing plugin runtime code, manifests, hooks, skills or configuration.
- Changing the behaviour of any add-on, or un-retiring any hook.

## Known context
- Parent / epic: none
- Related items: none
- Affected areas (best guess): `README.md` only (1717 lines; install material at lines 67-111, add-on/retired-hook material around lines 111-730, vendoring quick start at line 1331).

## North-star alignment
- none — the register holds no active thought (`.claude/north-stars/` does not exist)

## Open questions from intake
- Size and route: the request is a single-file documentation refactor with no data shape or mechanism, so it is sized S and skips the contract. → **Answer:** assumed, stated here, not asked (the invocation says not to ask for approval between phases).
- Tracker issue: free-text work, no issue yet. → **Answer:** offer left `pending`; `/ship` asks once before anything is opened or pushed.

## Size
S — one markdown file, no data shape, no new mechanism; `.md` files are exempt from the concept gate. Large in effort, small in design risk.

## Routing
non-trivial by effort, trivial by design → direct implementer (no `/design-first`)
