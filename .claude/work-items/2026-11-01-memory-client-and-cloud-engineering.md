---
id: 161
issue_offer: opened
title: Memory-system client boundary and cloud engineering capability
type: FEATURE
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/161
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/memory-client-and-cloud-engineering
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261101-feature-memory-client-and-cloud-engineering
north_stars: none
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/236
issue_link: closes
status: shipped
created: 2026-11-01
---

# Memory-system client boundary and cloud engineering capability

## Problem statement
The plugin is a working, contract-driven delivery framework. It has no way to consume or contribute knowledge held by a separate Central Memory System (a different product in another repository, reached over the Model Context Protocol, MCP). It also has no cloud engineering capability. The work is to audit the plugin, then add an optional, configurable memory client boundary and evaluate and add a provider-independent cloud engineering capability, without rebuilding anything that already works and without implementing the memory system here.

## Acceptance criteria
- [ ] A read-only audit of the repository is written down before any design: components, their responsibilities, what works, what is missing, what to keep, what could conflict. It covers skills, agents, hooks, scripts, registries, agent memory, the project profile, context loading and external integrations.
- [ ] The audit and a prioritized implementation plan (changes, files, dependencies, risks, validation criteria) reach you for approval before any architectural change is made.
- [ ] Memory integration is off by default. With it off, or with the memory server unreachable, every existing skill and flow behaves as it does today. A test proves this.
- [ ] Memory integration extends the plugin's existing memory-like mechanisms. It adds no second store, no database and no background process. A reviewer can name the existing mechanism each part attaches to.
- [ ] The plugin calls only the two MCP operations `memory_retrieve` and `memory_capture`, through one adapter point. No other component names memory tools directly. The tool names and shapes are configuration, so a contract change touches one place.
- [ ] Retrieved knowledge is labelled by scope (global or project) and status (proposed, validated, superseded, conflicting). It is never adopted automatically. Applicability to the current project is a recorded decision.
- [ ] Captured knowledge carries provenance (user decision, source-code fact, test-confirmed, AI hypothesis). An AI hypothesis is never captured as validated.
- [ ] The memory identifiers and versions used by a task are recorded in its brief, and conflicts or superseded entries are reported.
- [ ] A changed memory can at most propose a new work item. It never edits project code.
- [ ] The cloud engineering evaluation states which of the listed areas the plugin covers today and which it does not. Any new capability is enabled per project through the project profile, per provider (Azure, AWS, Google Cloud), and never by where an MCP server runs.
- [ ] Deployment and destructive cloud operations require explicit authorization and respect the existing destructive-operation guards.
- [ ] Documentation describes the architecture, the memory boundary, configuration, MCP integration, lifecycle separation, new capabilities and known limitations.
- [ ] The plugin's existing test suites and validation scripts still pass.

## Out of scope
- The Memory Engine, the Neo4j database and the Memory MCP server. They live in another repository.
- Any new database, microservice or background service.
- Unrelated refactoring of existing skills, agents or hooks.

## Known context
- Parent / epic: none
- Related items: none
- Clarification from the user at intake: memory management is a capability that does not exist in the plugin yet, so every improvement about it is to be associated with the existing mechanisms rather than introduced as a new parallel mechanism.
- Affected areas (best guess, to be confirmed by the audit and the contract): `skills/`, `agents/`, `.claude/project-profile.md`, `.claude/registries/`, `.claude/agent-memory/`, `.claude/scripts/`, `.claude/templates/`, `plugin.json`, documentation.

## North-star alignment
- none — the register holds no active thought (`.claude/north-stars/` does not exist).

## Open questions from intake
- Open a tracker issue for this work? → **Answer:** yes (user replied "accept all" to the recommendation). Opened as issue #161.
- Effort type → **Answer:** FEATURE (the memory capability does not exist yet).

## Size
XL — a new optional integration boundary, a possible new capability, changes across several component kinds, and a documentation set.

## Routing
non-trivial → /design-first. The first deliverable is the read-only audit and plan; implementation waits for an approved contract.
