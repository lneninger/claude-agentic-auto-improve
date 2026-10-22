---
id: none
issue_offer: pending
title: Move web-design agent knowledge into plugin skills, one per application design and website design
type: IMPROVEMENT
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/webdesign-plugin-skills
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261022-feature-webdesign-plugin-skills
north_stars: none
contract: .claude/concepts/2026-10-22-webdesign-plugin-skills.md
pr: UNKNOWN
issue_link: unknown
status: designing
created: 2026-10-22
---

# Move web-design agent knowledge into plugin skills, one per application design and website design

Raw invocation: `move webdesign agent details for a plugin skill. Create skill for each application and web site design. Check also how to best use external plugins references in this documentation...C:\Users\lneni\drop-scalpingmachine-prefix-dbs.ps1`

## Problem statement
The `ui-ux-designer` agent (`agents/ui-ux-designer.md`, 429 lines) holds all design knowledge inline:
the Material and Tailwind theming rules, component patterns, accessibility checklist and the
trading-terminal philosophy. Knowledge in an agent is loaded whole on every dispatch and cannot be
invoked on its own. Application UI (a data-dense, always-on product screen) and website design
(a marketing or content page) need different guidance, and today neither can be reached as a skill.
The plugin also has no documented rule for how its docs should point at skills that belong to other
plugins (for example `frontend-design:frontend-design` and `/dataviz`), which may not be installed.

## Acceptance criteria
- [ ] Two new skills exist under `skills/`: one for application design, one for website design. Each has a `SKILL.md` with a trigger-rich description, and long reference material sits in a `references/` file loaded on demand.
- [ ] The design detail now in `agents/ui-ux-designer.md` is moved into those skills. Nothing is lost: a diff of rules shows each rule in the agent file now lives in exactly one skill or stays in the agent.
- [ ] `agents/ui-ux-designer.md` keeps only its role, the mandatory journal step, the contract gate and the HANDOFF protocol, and points to the skills for method.
- [ ] A documented convention (in `README.md` or `CONTRIBUTING.md`) says how to reference another plugin's skill: name it fully qualified, mark it advisory, and state what the plugin does when it is absent. Every external reference added by this work follows it.
- [ ] No external plugin is made a hard dependency: with those plugins absent, the new skills still work.
- [ ] `README.md` skill inventory and the skill count in `plugin.json` description are updated; the inventory accuracy check used by this repo passes.
- [ ] Failure path: if the project profile slots the skills read (`frontend.roots`, `frontend.theme-polarity`, `review.documents`) are missing, the skills say so and halt instead of guessing a theme.
- [ ] Plugin version is bumped and the validator (`plugin-dev:plugin-validator`) reports no errors.

## Out of scope
- Rewriting the design rules themselves. They move; they are not redesigned.
- Running, editing or deleting anything because of `C:\Users\lneni\drop-scalpingmachine-prefix-dbs.ps1` (see Open questions).
- Installing or vendoring any external plugin.

## Known context
- Parent / epic: none
- Related items: none
- Affected areas (best guess): `agents/ui-ux-designer.md`, new `skills/<application-design>/` and `skills/<website-design>/`, `README.md`, `CONTRIBUTING.md`, `plugin.json`, `.cursor-plugin/plugin.json` if present.
- Existing references to `ui-ux-designer` in `skills/debug`, `skills/tdd-first`, `skills/journal-add` stay valid because the agent remains.

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- What is the PowerShell script path at the end of the request? → **Answer (assumption, not confirmed):** it is a stray paste. The file is a database-drop script for another project, unrelated to plugin skills, and the user's own rules block destructive database operations. It is not read into this work and not run. Tell me if you meant it as a style example for something.
- "Skill for each application and web site design": one skill each, or one per application root? → **Answer (assumption):** exactly two skills, one for applications and one for websites. Per-application differences come from the project profile slots, not from more skills.
- Skill names? → **Answer (assumption):** `application-design` and `website-design`; the contract may rename them.
- Should the agent be deleted? → **Answer (assumption):** no. It stays as the contract-gated implementer that applies the skills.
- Issue offer: not asked in this run (invoked without a tracker issue). `issue_offer` stays `pending`.

## Size
M — two new skills, an agent refactor and a documentation convention; no data shape, but new mechanisms (skills) are created.

## Routing
non-trivial → /design-first
