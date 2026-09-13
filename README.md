# claude-agentic-auto-improve

A reusable repository holding the project-independent half of a Claude Code setup:
generic agents, skills, hooks, workflow scripts, templates, references and the Universal
tier of the registries, for any project following the Data-First Engineering Protocol.

## What this is, and what it is not

It is a **vendoring source**: a place to copy files from, so a new project can adopt the
same workflow without assembling it by hand. The copies are committed in the consuming
repository, so that repository works when this checkout is absent.

It is **not** a plugin the editor can load. Claude Code's plugin mechanism is the
`enabledPlugins` and `extraKnownMarketplaces` pair in the workstation settings file, and
this repository carries no manifest and belongs to no marketplace. Converting it is
tracked as separate work.

## Ownership and direction

**Every synced tree is bidirectional.** No tree is one-way and neither repository is
authoritative by position. Divergence is settled by reading both versions and merging,
never by a rule about which side wins.

Ownership is a field in the consuming project's `.claude/.sync-config.json`, not a
directory on disk. Each tree entry carries a `path`, an `ownership_tier`, a `direction`
and a `files` array naming exactly which paths are shared. A file that no `files` array
names is a local asset and is never synced.

Protection against project-specific content reaching this repository is the
**project-name check** in the sync tool, described under "Contributing" below. It is not a
direction rule. The one-way rule that used to guard agents protected the wrong direction:
this repository's own copies carry a consuming project's names, so a one-way pull pushed
that contamination downstream into every other consuming project.

## What is included

```
.claude/
  agents/        13 generic agents
  skills/        16 generic skills
  hooks/         19 generic hooks, 3 shared helper modules, 3 generic data files
    tests/       3 hook test suites
  scripts/       19 workflow scripts
    tests/       2 suites, including the path-resolution suite
  templates/     6 document templates
  references/    2 reference documents
  registries/    MECHANISMS.md, VOCABULARY.md, JOURNAL.md (Universal tier only)
                 INTEGRATION.md (whole file)
  area-mapping.json          TEMPLATE - schema intact, empty content set
  work-item-conventions.json TEMPLATE - schema intact, empty content set
  project-profile.md         TEMPLATE - blank slot table
  .project-tokens.json       TEMPLATE - empty token array
README.md
CONTRIBUTING.md
```

### Agents

data-architect, contract-critic, fullstack-code-reviewer, senior-test-engineer,
test-strategy-critic, migration-safety-reviewer, security-auditor,
sql-performance-reviewer, api-contract-reviewer, ui-ux-designer,
dotnet-backend-architect, angular-senior-dev, python-ai-developer.

### Skills

design-first, tdd-first, debug, verify-before-done, north-star, north-star-review,
list-contracts, task, contract-accuracy, critique-now, cross-impact, journal-add,
plan-questions, validate-registries, promote-ui-rule, git-commit.

### Hooks

concept-gate, architecture-guard, bash-gate, architecture-advisor, codegraph-first-guard,
codegraph-turn-tracker, codegraph-turn-reset, plain-language-guard, db-destructive-guard,
db-research-readonly-guard, integration-check, plan-question-advisor,
critic-verdict-tracker, contract-status-watcher, journal-post-approval-tracker,
memory-pager, plus the shared helpers `_error_log.py`, `_memory_common.py` and
`_project_paths.py`, and the generic data files `architecture-guard.rules.json`,
`architecture-guard.exceptions.json` and `plain-language-guard.rules.json`.

**A guard hook keeps its per-project settings in a `<hook-name>.rules.json` file beside
it**, so the hook body names no project. A rules file holding one project's own constants
stays in that project and is not shipped here — `db-destructive-guard.rules.json` and
`integration-check.rules.json` are the two examples.

**The fail direction is per hook and is stated in each rules file.** A hook that BLOCKS
fails **closed** when its rules file is missing: `db-destructive-guard.py` with no
configuration treats every database as protected. A hook that only WARNS may fail soft.
Never copy the soft choice to a guard that blocks.

### Scripts and templates are not optional

The design-first agent runs `cross_area_scan.py` and `derive_area.py` by path, five skills
cite scripts in `.claude/scripts/`, and every concept contract is a copy of
`templates/concept-contract.md`. `scripts/tests/test_script_path_resolution.py` is the
74-case suite for the two-layer path resolver. Shipping the resolver without its suite
would ship the part that can be wrong and leave behind the part that would say so.

## Quick start in a new project

1. **Copy the trees.** Copy `.claude/agents`, `skills`, `hooks`, `scripts`, `templates`
   and `references` into your project's `.claude/`, at their ordinary paths. Do not create
   a subdirectory named after this repository; one copy, in the normal place.

2. **Copy the registries** and add your own `## Project: <name>` section below the
   Universal tier in each. Everything below the first `## Project:` line stays yours and
   is never synced.

3. **Fill in the four templates.** `area-mapping.json`, `work-item-conventions.json`,
   `project-profile.md` and `.project-tokens.json` ship with their schema and an empty
   content set, because their shape is generic and their content is not.
   `.project-tokens.json` is the one to fill in first: an unguarded outbound sync is how
   contamination spreads.

4. **Write `.claude/project-profile.md`.** It is the only file you must author to make the
   thirteen vendored agents correct. A generic agent cites a slot by name rather than a
   literal path, so every slot must be present, and an empty slot reads `none`.

5. **Register the hooks** in your `.claude/settings.json`, pathing every command through
   `$CLAUDE_PROJECT_DIR/.claude/hooks/`. Do not point a hook command at this checkout:
   `_project_paths.py` resolves a hook's `.claude` root from the hook file's own location,
   so a hook run from here would add this repository's registries as a second search root
   and could answer a lookup your project meant to answer itself.

6. **Add your sync configuration** at `.claude/.sync-config.json` and the tool that reads
   it. See CONTRIBUTING.md.

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md) — sync workflow, the project-name check, conflict resolution
- `.claude/hooks/tests/` and `.claude/scripts/tests/` — the suites
- Each agent and skill — its own `## When to Use` section

## Status

Extracted from a first consuming project on 2026-09-10; inventory completed and the
ownership and direction model corrected on 2026-09-12.