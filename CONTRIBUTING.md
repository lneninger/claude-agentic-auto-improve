# Contributing to claude-agentic-auto-improve

How changes travel between this repository and a consuming project, how conflicts are
resolved, and what will refuse a change.

## Direction: one rule, both ways

**Every synced tree is bidirectional. Neither repository is authoritative.**

> **Corrected 2026-09-12.** The previous version of this document said, two lines apart,
> that this repository was authoritative for agents and that the main repository was the
> canonical source for everything else. Both cannot be true and neither was enforced. The
> one-way rule is withdrawn. It also protected the wrong direction: this repository's
> copies carry a consuming project's names, so a one-way pull pushed that contamination
> downstream into every other consuming project, and a project that repaired a file
> locally lost the repair at the next sync.

What replaces it is a check a tool can run, described below.

## Synced assets

The tree list, each tree's file list and the registry list all come from the consuming
project's `.claude/.sync-config.json`. That file is the single source of truth and the
sync script reads it; nothing about the synced set is hard-coded in the script.

- `skills/` and `agents/` — **at this repository's root**, mapping to the consuming
  project's `.claude/skills/` and `.claude/agents/`
- `.claude/hooks/`, `scripts/`, `templates/`, `references/`
- `.claude/registries/` — the Universal section only, above the first `## Project:`
  heading, except `INTEGRATION.md` which is whole-file

> **The two root trees are a path mapping, not a path match.** They live at the root here
> because a plugin's components must be discoverable there — the portable Agent Plugins
> manifest that Cursor and OpenAI Codex read has no component-path fields, so a skill
> outside the plugin root is invisible to them. A consuming project still keeps its copies
> under `.claude/`. A `.sync-config.json` tree entry therefore needs both sides of the
> mapping, and a configuration written before 2026-09-13 that assumes `.claude/skills`
> on both sides will report every skill as `ONLY_IN_MAIN`.

A file that no `files` array names is a local asset by default: it stays in the consuming
project and is never compared.

## The project-name check

**Before the sync writes anything into this repository, it searches every outbound file
for each literal string in the consuming project's `.claude/.project-tokens.json`** — the
repository name, the front-end application names, the database names, the source prefix,
the vendor names the domain uses and the project's own handbook file names.

Any hit halts the run with **exit code 5** and a report naming the file, the token and the
line. Nothing is copied.

It runs **outbound only**. A token found in a file arriving from here means this
repository is already contaminated, and refusing the pull would leave the consumer stuck
with the contaminated copy it already has.

A deliberate false positive is declared as an **exact string** in the `allowed` array with
a one-line reason. **It is never a file name.** Exempting a whole file exempts every
reference added to it later, which is how a file becomes permanently unguarded.

## Making a change

Edit the file wherever you are working, at its ordinary path, then sync. There is one copy
per repository and no subdirectory owns anything.

Two obligations come with editing a generic file:

1. **Do not write a project reference into it.** If it needs a project-shaped fact, cite a
   slot in `project-profile.md` by name, or move the constant into a
   `<hook-name>.rules.json` file beside the hook.
2. **If an agent needs a fact no profile slot covers, add the slot to
   `.claude/project-profile.md` here, in the same change**, so every consuming project
   gains it at once. Never invent a slot that exists in only one project.

## Conflict resolution

A conflict is reported when the configuration names a file and the two sides disagree
about it. Three kinds:

- `CONFLICT` — both sides hold it and the content differs
- `ONLY_IN_MAIN` / `ONLY_IN_PLUGIN` — the configuration names it but one side lacks it
- `REGISTRY_CONFLICT` — the Universal sections of a registry file differ

**One rule for every tree: read both versions and merge by hand.** No side wins by being
newer. A timestamp says which checkout was touched last, not which change is right, and a
checkout rewrites timestamps anyway.

For a one-sided file, decide whether it should exist on the other side. If it should, copy
it there. If it should not, remove it from that tree's `files` array — a file that is not
declared is not compared.

Then re-run the sync with `--resolve`.

### How content is compared

Line endings are folded and a leading UTF-8 byte order mark is stripped before hashing.
This repository stores line-feed endings and marks its registry files; a consuming project
on Windows typically stores carriage-return plus line-feed and no mark. Neither difference
changes meaning, and comparing raw bytes once reported eighteen conflicts that no edit
could ever clear — which trains an operator to reach for `--force`, the one path that
silently overwrites real divergence.

## Exit codes

| Code | Meaning | Action |
|---|---|---|
| 0 | Success | None |
| 2 | Conflict | Resolve and re-run |
| 3 | Marker exists | Re-run with `--resolve`, or delete the marker |
| 4 | Bad environment | Including: this repository was not found. The message names both locations tried. |
| 5 | Project-name check failed | Remove the reference, or declare the exact string in `allowed` with a reason. Nothing was copied. |

## Finding this repository

Two layers, in order:

1. the `CLAUDE_PLUGIN_ROOT` environment variable
2. the conventional sibling directory beside the consuming repository

> **`CLAUDE_PLUGIN_ROOT` now has two meanings, and they agree.** The sync tool reads it as
> "where this repository is checked out." Claude Code independently substitutes it in a
> plugin's hook commands as "where this plugin is installed" — which is
> `.claude/hooks/hooks.json`'s only way to path its own scripts. Under a plugin install both
> resolve to the same directory, so nothing breaks. Do not repurpose the name for anything
> a third reader would resolve differently.

A git worktree is not beside this checkout, so **from a worktree set `CLAUDE_PLUGIN_ROOT`
first**. There is deliberately no git-submodule layer: submodules behave badly in a
worktree workflow.

## Registries

- Edit only the Universal section, above the first `## Project:` heading.
- Everything from that heading to the end of the file belongs to the consuming project and
  is never compared or copied.
- **A cross-project mechanism entry must live in the Universal tier.** An entry below the
  project heading can never reach this repository, so filing one there silently guarantees
  no other project sees it. Three entries were misfiled that way until 2026-09-12.

## Proposing a new generic asset

1. Satisfy yourself it is genuinely generic, not domain-specific wearing a general name.
2. Place it in the consuming project at its ordinary path.
3. Add its path to the matching tree's `files` array in `.claude/.sync-config.json`.
4. Run the sync. If the project-name check refuses it, the asset is not generic yet.
5. Add it to the list in [README.md](README.md).
6. **If it is a hook, register it in `.claude/hooks/hooks.json`.** That file is the single
   registration point for the plugin install, so a hook added to the tree but not to it
   ships as a file nothing ever runs — the silent-success failure this repository has
   already been bitten by once.
7. **If it is a skill or an agent, put it at the repository root** (`skills/<name>/SKILL.md`
   or `agents/<name>.md`), not under `.claude/`. Anywhere else and the three plugin
   mechanisms will not find it.

## Troubleshooting

**The marker will not clear.** Delete `.claude\.sync-state\conflicts.json` in the
consuming project and re-run.

**"Plugin repository not found."** That is exit code 4, and the message names both
locations it tried. Set `CLAUDE_PLUGIN_ROOT`.

**The sync reports nothing and exits 0.** Check that it ran at all. A wrapper script that
returns 0 having done nothing looks exactly like a clean sync — that was the real state of
this tooling from its first commit until 2026-09-12.