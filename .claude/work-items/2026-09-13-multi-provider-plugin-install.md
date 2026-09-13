---
id: none
title: Make this repository installable as a plugin under the Claude, Cursor and OpenAI provider mechanisms
type: FEATURE
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/multi-provider-plugin-install
worktree: .claude/worktrees/20260913-feature-multi-provider-plugin-install
north_stars: none - the register at .claude/north-stars/ does not exist
contract: UNKNOWN - filled by /design-first
pr: none
issue_link: none
status: clarified
created: 2026-09-13
---

# Make this repository installable as a plugin under the Claude, Cursor and OpenAI provider mechanisms

Raw request, verbatim: *"this plugin must be allowed to be installed using provider
mechanisms: claude, cursor, openai"*

## Problem statement

This repository holds a complete, generic Claude Code asset set — 16 skills, 14 agents,
19 hooks, 19 scripts, 6 templates, 2 references and the Universal tier of three
registries — but it can only be consumed by copying files by hand. Its own README states
the limitation plainly: *"It is not a plugin the editor can load. Claude Code's plugin
mechanism is the `enabledPlugins` and `extraKnownMarketplaces` pair in the workstation
settings file, and this repository carries no manifest and belongs to no marketplace.
Converting it is tracked as separate work."* This work item is that separate work,
widened to three providers rather than one.

Every asset that makes the set worth distributing therefore reaches a new project only
through a manual vendoring step, and a project that adopts it acquires a maintenance
burden (the bidirectional sync described in CONTRIBUTING.md) rather than a dependency.
Meanwhile all three target harnesses now ship a first-class plugin mechanism, and two of
them converge on one vendor-neutral standard, so the cost of supporting all three is far
below the cost of supporting three bespoke formats.

## Acceptance criteria

Installation, one per provider — each verified by performing the install, not by
inspecting the manifest:

- [ ] A Claude Code user can run `/plugin marketplace add lneninger/claude-agentic-auto-improve`
      and then `/plugin install <plugin-name>@<marketplace-name>`, and the install reports success.
- [ ] A Cursor user can install this repository as a plugin (via `/add-plugin` against the
      repository, per Cursor's documented flow) and the install reports success.
- [ ] An OpenAI Codex user can run `codex plugin marketplace add lneninger/claude-agentic-auto-improve`
      and install the plugin, and the install reports success.

Loading — an install that succeeds but loads nothing is the failure this item exists to
prevent, so each provider gets an explicit load assertion:

- [ ] After the Claude install, all 16 skills are listed by the harness, and invoking one
      of them (`/list-contracts`) runs to completion rather than erroring on a missing path.
- [ ] After the Claude install, all 14 agents are offered as subagent types.
- [ ] After the Cursor install, Cursor lists the shipped skills.
- [ ] After the Codex install, Codex lists the shipped skills (`skills/<name>/SKILL.md`
      is the one component shape all three providers share, so it is the portability floor).

Failure paths — the criteria that stop this shipping as a silent no-op:

- [ ] A provider that cannot carry part of the asset set states so in its documented
      support matrix. Loading zero skills while reporting a successful install is a defect,
      not a partial success. (This repository has already been bitten by exactly this class
      of bug: CONTRIBUTING.md records that *"a wrapper script that returns 0 having done
      nothing looks exactly like a clean sync"* was the real state of the sync tooling from
      its first commit until 2026-09-12.)
- [ ] A skill or hook that resolves a path which does not exist under a plugin install
      fails with a message naming the missing path, rather than silently doing nothing.
      This specifically covers `_project_paths.py`, which resolves its `.claude` root from
      the hook file's own location and would therefore resolve into the read-only plugin
      cache rather than the consuming project.

Supporting artefacts:

- [ ] Each manifest validates against its provider's published schema.
- [ ] A `LICENSE` file exists at the repository root and its SPDX identifier is declared in
      every manifest. The repository is public and currently carries no license, which
      makes it legally unreusable regardless of any manifest.
- [ ] README.md's claim that this is *not* a loadable plugin is corrected in the same change
      that makes it false, and gains a per-provider install section and support matrix.
- [ ] The existing vendoring path still works after the change: either the tree paths named
      in CONTRIBUTING.md and in a consuming project's `.sync-config.json` still resolve, or
      CONTRIBUTING.md is updated in the same change to describe the new ones.

## Out of scope

- **Public directory listings.** Cursor's marketplace requires manual review of an
  open-source repository; OpenAI has its own submission flow. Both are external approval
  waits this item cannot close on. Self-hosted installation direct from this git repository
  is the deliverable. Listing becomes a follow-up item.
- **Translating hooks to Cursor's and Codex's hook event models.** Claude's event names
  (`PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `SessionStart`, `Stop`), its
  `${CLAUDE_PLUGIN_ROOT}` substitution and the `py -3` invocation are Claude-specific.
  Shipping untested translations to two other runtimes would ship exactly the silent-no-op
  failure the criteria above forbid.
- **Reconciling vendoring against plugin install as competing distribution models.** See
  Assumption 2 — this item makes install work alongside vendoring and defers the
  reconciliation.
- **Bundling MCP servers.** This repository ships none.
- **Authoring the four per-project templates on a consumer's behalf.** `project-profile.md`,
  `area-mapping.json`, `work-item-conventions.json` and `.project-tokens.json` must be filled
  in by the consuming project; a read-only plugin install cannot write them. How an installed
  plugin prompts for or locates them is a design question for the contract, not a criterion here.

## Known context

- Parent / epic: none
- Related items: none. The repository has zero GitHub issues; PRs #1 through #4 are merged.
- Affected areas (best guess, to be confirmed by the contract): repository root (new manifest
  files, `LICENSE`), `README.md`, `CONTRIBUTING.md`, and — depending on the layout decision
  below — potentially the location of `.claude/skills/`, `.claude/agents/`, `.claude/hooks/`,
  `.claude/scripts/`, `.claude/templates/`, `.claude/references/` and `.claude/registries/`.

### Provider mechanisms as verified on 2026-09-13

Verified against each provider's live documentation, not from memory.

| Provider | Manifest path | Component discovery | Install command |
|---|---|---|---|
| Claude Code | `.claude-plugin/plugin.json` (only `name` required; manifest itself optional) | Defaults `skills/`, `agents/`, `commands/`, `hooks/hooks.json`, `.mcp.json`, `bin/` — **and manifest path fields redirect them**, e.g. `"skills": "./.claude/skills/"` | `/plugin marketplace add owner/repo` then `/plugin install name@marketplace` |
| Cursor | `plugin.json` at root (Agent Plugins standard) **or** `.cursor-plugin/plugin.json` | Cursor's own format has redirectable path fields: `rules`, `agents`, `skills`, `commands`, `hooks`, `mcpServers`, `variables`. Defaults are root-level `skills/`, `rules/`, `agents/`, `commands/`, `hooks/hooks.json`, `mcp.json` | `/add-plugin`; multi-plugin repos use `.cursor-plugin/marketplace.json` |
| OpenAI Codex | `plugin.json` at plugin root, fallback `.codex-plugin/plugin.json`, `$schema: https://agent-plugins.org/schemas/1.0.0/plugin.schema.json` | `skills/<name>/SKILL.md`, `mcp.json`, `hooks/hooks.json`, `assets/` — **all at root; the portable schema has no component-path fields**, only metadata plus `extensions` | `codex plugin marketplace add owner/repo`; marketplace at `.agents/plugins/marketplace.json` |

Marketplace manifests, for a repository that hosts its own: Claude
`.claude-plugin/marketplace.json` (`name`, `owner`, `plugins[]` required), Cursor
`.cursor-plugin/marketplace.json` (`name`, `owner`, `plugins[]`), OpenAI
`.agents/plugins/marketplace.json` (`name`, `plugins[]` with `source`/`policy`).

**Cursor and OpenAI converge on the Agent Plugins open standard**
(`https://github.com/agentplugins/agent-plugins-spec`); Cursor's documentation states that
a conformant plugin *"loads in Cursor without changes."* Claude Code keeps its own format.
Two manifests, not three, may therefore be sufficient — this is for the contract to confirm.

### What already fits, and what does not

Fits: skills are already `.claude/skills/<name>/SKILL.md`, which is the exact shape all
three providers expect. Agents are already flat `.md` files with YAML frontmatter, which
Claude and Cursor both accept.

Does not fit:

1. **Every asset lives under `.claude/`, and the portable manifest cannot redirect.** Claude
   and Cursor can be pointed at `.claude/*` through manifest path fields. The Agent Plugins
   manifest that OpenAI reads has no such fields, so OpenAI/Codex is the provider that
   plausibly requires files at the repository root. This is the central design question.
2. **No `hooks/hooks.json` exists anywhere in the repository.** README.md instructs consumers
   to hand-register all 19 hooks in their own `.claude/settings.json`. Shipping hooks through
   a plugin is therefore new authoring, not a manifest line.
3. **`${CLAUDE_PLUGIN_ROOT}` is already in use here for a different purpose.** CONTRIBUTING.md
   defines it as the environment variable the sync tool reads to locate this repository.
   Claude Code independently defines it as the substitution for an installed plugin's own
   root. Under an install the two happen to coincide, but the collision needs stating.
4. **The repository is public and has no `LICENSE`.**

## North-star alignment

none — the register holds no active thought. `.claude/north-stars/` does not exist in this
repository, so Step 3.5 had nothing to grade against, and this brief's grade is the whole
north-star record for the item. Nothing in the intake text voiced an aspiration separable
from the concrete request, so no new north-star was captured.

## Open questions from intake

The user was presented with four blocking questions covering layout, the distribution model,
per-provider parity and publication scope. They declined to answer and instructed the work to
continue. Each is therefore recorded below with the assumption taken in its place. **These are
assumptions, not answers** — `/design-first` must surface every one of them again in its own
Step 3, where the user is the gate.

- **Q1. Where do the component trees live?** The Agent Plugins standard discovers at the
  plugin root; everything here is under `.claude/`. Three shapes were put forward: move the
  trees to the repository root; keep `.claude/` and redirect via manifest path fields only
  (which leaves OpenAI unsupported); or keep `.claude/` authoritative and generate a
  root-level mirror. → **Assumption:** unresolved by design. This is the contract's central
  question and the acceptance criteria above are deliberately written against installation
  outcomes rather than file locations, so any of the three layouts can satisfy them.
- **Q2. Does plugin install replace the vendoring model or sit beside it?** → **Assumption:**
  it sits beside it, additively. Vendoring and its bidirectional sync remain the documented
  path for projects that edit assets in place; plugin install is a second, read-only
  consumption path. The `_project_paths.py` resolution problem is called out as a failure-path
  criterion above but its full reconciliation is out of scope. This is the least destructive
  reading and does not strand existing consumers.
- **Q3. What ships per provider?** → **Assumption:** tiered. Skills on all three providers;
  agents on Claude and Cursor; hooks on Claude only, with a documented support matrix stating
  the gaps. Full parity would require hook translations testable against three runtimes;
  skills-only would mean a Claude user who installs the plugin loses all 14 agents and every
  guard hook, which is worse than the status quo.
- **Q4. How far does "allowed to be installed" go?** → **Assumption:** self-hosted
  installation direct from this git repository, plus a `LICENSE`. Public directory submission
  is a follow-up item, because it depends on external review this item cannot close on.

## Size

**L** — three provider mechanisms, at least two manifest formats plus up to three marketplace
manifests, a possible relocation of seven asset trees that every skill and the sync
configuration reference by path, first-time authoring of a hook configuration for 19 hooks, a
new `LICENSE`, and corrections to both README.md and CONTRIBUTING.md whose current text
asserts the opposite of what this delivers. The layout decision alone is load-bearing enough
to change the shape of every other part.

## Routing

non-trivial → `/design-first` (mandatory for M/L/XL)
