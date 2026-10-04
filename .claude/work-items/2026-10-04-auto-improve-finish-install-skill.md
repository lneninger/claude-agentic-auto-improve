---
id: none
title: A /auto-improve-finish-install skill that carries a consuming project through Quick start steps 4 and 5
type: FEATURE
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/auto-improve-finish-install-skill
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261004-feature-auto-improve-finish-install-skill
north_stars: none - the register holds no active thought
contract: .claude/concepts/2026-10-04-auto-improve-finish-install-skill.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/22
issue_link: unknown
status: shipped
created: 2026-10-04
---

# A /auto-improve-finish-install skill that carries a consuming project through Quick start steps 4 and 5

Raw request, verbatim: "plugin must help (like by skill use) the installation steps 4, 5.
must be simplier for the plugin user to get it up and running"

## Problem statement

The README's "Quick start in a new project" lists six steps. Steps 4 and 5 are the two a
person cannot finish by copying files, so they are where a new user stalls:

- **Step 4, write `.claude/project-profile.md`.** It is the one file that makes the fourteen
  agents correct, and it is required under a plugin install too. Every one of eleven slots
  must be present, an empty slot reads `none`, and a wrong agent name in `implementers`
  halts the whole contract loop. Today the user gets a template with placeholders and has to
  work out their own source roots, test roots, migration directory and safety-critical paths
  by hand.
- **Step 5, register the hooks.** A plugin install registers them automatically, so the user
  has nothing to do and nothing tells them whether it worked. A vendored install must copy
  sixteen entries out of `hooks.json` into their own `settings.json`, swap
  `${CLAUDE_PLUGIN_ROOT}` for `$CLAUDE_PROJECT_DIR`, and on macOS or Linux change `py -3` to
  `python3` throughout. That is error-prone hand editing of a file that controls whether the
  enforcement gates run at all.

`plugin_doctor.py` already creates the directories and scaffolds the templates, but it is a
script the user must know to run, it leaves the profile's placeholders untouched on purpose,
and it deliberately does not touch `settings.json`. No skill drives any of it.

## Acceptance criteria

- [ ] A new skill `auto-improve-finish-install` ships at `skills/auto-improve-finish-install/SKILL.md` and is discoverable under all
      three providers the way the existing skills are. Invoking `/auto-improve-finish-install` in a project with
      the plugin installed walks the user through step 4 and then step 5 without them
      having to read the README.
- [ ] **Step 4.** The skill inspects the consuming repository, proposes a value for every one
      of the eleven profile slots with the evidence it used for each, asks the user to
      confirm or correct the whole set once, and only then writes `.claude/project-profile.md`.
      Every slot is present in the result; a slot it found nothing for is written `none`,
      never blank and never guessed.
- [ ] **Step 4 never invents.** A proposed `implementers` or `review-gates` value names only
      agents that exist in the project's `.claude/agents/` or the plugin's own set. A name
      that resolves in neither is refused before the file is written. An existing profile is
      never overwritten; the skill shows the difference and asks.
- [ ] **Step 5, plugin install.** The skill detects that the plugin is installed rather than
      vendored and makes no `settings.json` edit. It confirms the sixteen hooks are actually
      live (not merely listed) and tells the user which enforcement gates are now on, what the
      kill-switch variables are, and that the database guards fail closed.
- [ ] **Step 5, vendored.** The skill registers the sixteen hooks into the project's
      `.claude/settings.json` with every command pathed through `$CLAUDE_PROJECT_DIR`, and on
      a non-Windows host substitutes `python3` for `py -3`. It shows the user the exact
      change and asks before writing, because registration turns enforcement on.
- [ ] **Step 5 is safe to repeat and safe to refuse.** Re-running adds nothing a second time.
      Existing user hooks and unrelated settings keys survive byte for byte in meaning. A
      backup of the prior `settings.json` is taken before any write. Declining leaves every
      file untouched.
- [ ] The deterministic parts (slot inference evidence, hook-entry merge, interpreter swap,
      idempotence, install-mode detection) live in a script with its own test suite, in the
      style of `plugin_doctor.py` and `.claude/scripts/tests/`; the skill carries only the
      conversation. Every test fails first for an assertion reason.
- [ ] **Failure paths.** Malformed `settings.json`, an unreadable repository, an unknown
      install mode and a missing `hooks.json` each stop with a named reason and write nothing.
- [ ] The README's Quick start steps 4 and 5 are rewritten to say "run `/auto-improve-finish-install`" with the
      by-hand procedure kept as the fallback, the inventory counts (skills, scripts, suites)
      are updated to match the tree, and `plugin_doctor.py`'s closing note about
      `settings.json` points at `/auto-improve-finish-install`.
- [ ] The version is bumped in all five declarations so an installed copy actually receives
      the skill (a merged change that keeps the old number never reaches running sessions).

## Out of scope

- Quick start step 3, the other three per-project files (`area-mapping.json`,
  `work-item-conventions.json`, `.project-tokens.json`). The doctor already scaffolds them;
  filling them by inference is a separate and riskier feature, noted as a follow-up.
- Step 6, the sync configuration, and anything about contributing back to the plugin.
- Making hooks work on macOS or Linux without the interpreter swap (the format has no
  per-platform branch), and any change to what an individual hook does.
- Cursor and OpenAI Codex hook registration. Hooks remain Claude-only in this release.
- Mirroring the new skill into the ScalpingMachine repository. That arrives through the sync
  after this merges and is that repository's own work item.

## Known context

- Parent / epic: none
- Related items: the README's "Let the doctor create what is missing" section and
  `.claude/scripts/plugin_doctor.py` (its two rules: never overwrite, never invent an authored
  value). The new skill must honour both.
- Affected areas (best guess, to be confirmed by the contract): `skills/auto-improve-finish-install/`,
  `.claude/scripts/` (one new script, one new test suite), `.claude/scripts/plugin_doctor.py`
  (message only), `README.md`, and the five version declarations.
- The plugin repository is a different repository from the one this run was started in. The
  brief, the contract, the branch and the pull request all live here, in the worktree named
  above. Per project memory this repository takes changes by branch and pull request only,
  and the branch has no upstream so a bare push cannot reach master.

## North-star alignment

- none - the register holds no active thought (this repository has no `.claude/north-stars/`).

## Open questions from intake

The operator's standing preference is a recommendation over a question batch, so each gap
below was closed with a recommended default instead of an interrupt. Every one is correctable
at the contract gate, which is the real approval point.

- Is this a new skill, a change to `plugin_doctor.py`, or both? → **Answer (assumed):** a new
  skill, because the request says "by skill use". The doctor stays the bootstrap for files and
  directories; the skill is the guided conversation for the two steps that need judgement.
- Which repository and where does the work live? → **Answer (assumed):** the plugin repository,
  because the plugin is what the user wants changed and a fix finished anywhere else does not
  reach plugin users.
- Does "steps 4, 5" mean the Quick start numbering? → **Answer (assumed):** yes, steps 4
  (profile) and 5 (hooks). It is the only numbered list in the README where those two are the
  ones that need a person.
- Should the skill create a tracker issue? → **Answer (assumed):** no. The request is free
  text and the operator declined question prompts; `/ship` will offer once at ship time.
- Should hook registration happen without asking? → **Answer (assumed):** no. It turns
  enforcement on and changes a file the user owns, so it shows the diff and asks.
- Can several plugins be installed at once? → **Answer (user, 2026-10-04):** yes. The skill name carries the plugin's name, and the script reads only this plugin's entries and ignores every other plugin.

## Size

M - one new skill, one new script with a test suite, and edits to the README and five
manifests. Several design choices (how slots are inferred, how the merge stays idempotent,
what "live" means for an installed hook) need a contract.

## Routing

non-trivial -> /design-first. TDD is the default flow. Not on a safety-critical path, but the
`settings.json` write is user-owned state, so the contract must name backup and rollback.
