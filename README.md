# claude-agentic-auto-improve

> **Breaking change in 0.8.0: edits and writes in a repository's main checkout are refused.**
>
> - **What is blocked.** In each consuming repository, the plugin's concept-gate entry now runs
>   through a gate launcher (`gate-launch.py`) that first refuses `Edit`, `Write`, `MultiEdit` and
>   `NotebookEdit` aimed at the repository's *main checkout* (the original checkout, whose `.git` is a
>   folder). Linked worktrees are not affected. There is **no off switch**: no environment variable,
>   flag or file turns it off.
> - **Shell commands are guarded from 0.9.8.** Before 0.9.8 only the edit tools were covered, because
>   the shell check lived in `bash-gate.py`, which the plugin did not register. Since 0.9.9 that gate
>   is the opt-in `strict-shell-gate` add-on (see [Managing optional add-ons and retired hooks](#managing-optional-add-ons-and-retired-hooks)). The plugin now registers a launcher row on `Bash` and
>   `PowerShell` that runs the same main-checkout guard, and the merge-direction check for `gh` pull
>   request commands, before every shell command. It reads the files a command writes with the shared
>   parser `_shell_write_targets.py`. `/ship` still runs `merge_direction.py` before it opens a pull
>   request.
> - **What to do.** Start each change in a fresh flat worktree: `/task` creates one under
>   `.claude/worktrees/` and enters it; or run `py -3 .claude/scripts/flat_worktree.py --create --action
>   <feature|bug|infra> --slug <name> --detached origin/<default>` and `EnterWorktree` into the path it
>   prints.
> - **Repair path.** Hooks load from the plugin's install folder, not from your repository. If the guard
>   answers wrongly, the repair is a fixed plugin version, or reinstalling the previous version. An
>   older consumer worktree does not help, because it runs the same installed hooks. A vendored copy
>   needs `auto_improve_finish_install.py` from this version, which rewrites the launcher's gate
>   argument to the project's own hooks folder; an unrewritten row blocks loudly with the banner
>   `MAIN CHECKOUT (launcher misregistered)`.

A reusable repository holding the project-independent half of a Claude Code setup:
generic agents, skills, hooks, workflow scripts, templates, references and the Universal
tier of the registries, for any project following the Data-First Engineering Protocol.

## What this is, and what it is not

It is consumed two ways, and both are supported.

**As an installable plugin.** The repository carries a manifest for each of three provider
mechanisms and hosts its own marketplace, so Claude Code, Cursor and OpenAI Codex can each
install it directly from git. See [Installation](#installation) below. Assets load from the
provider's plugin cache and are not copied into your repository.

**As a vendoring source.** A place to copy files from, so a new project can adopt the same
workflow without assembling it by hand. The copies are committed in the consuming
repository, so that repository works when this checkout is absent, and they can be edited
in place and synced back. See [Quick start in a new project (vendoring)](#quick-start-in-a-new-project-vendoring).

Pick vendoring when you intend to modify the assets or need them present offline; pick the
plugin when you want a dependency rather than a fork. **The two are not yet reconciled** —
see [Known limitations](#known-limitations) before mixing them.

**To install the plugin, go straight to [Installation](#installation).**

## Features

- **A delivery chain you start with one command.** `/flow` carries a request through intake, a design contract that you approve, test-first implementation, adversarial review, verification, a commit and a draft pull request. It stops only where a person has to decide.
- **Gates that run in every Claude Code session.** The plugin registers them itself: the concept gate (no edit to a non-trivial file without an approved contract), the main-checkout guard, the architecture guard, the two database guards and the end-of-turn Changed-file check. See [What the plugin's hooks do](#what-the-plugins-hooks-do).
- **Working agreements.** Standing rules about how the assistant works with you, delivered when a session starts. See [Working agreements](#working-agreements).
- **Skills and agents.** The stages of the chain, the reviewers, the implementers and the one-time setup skills. See [What is included](#what-is-included).
- **A project history record.** Registries, concept contracts and work item briefs, committed in your repository. See [The Project history record](#the-project-history-record).
- **Optional add-ons.** Stack-specific or stricter checks that you install per project. See [Managing optional add-ons and retired hooks](#managing-optional-add-ons-and-retired-hooks).
- **Optional memory client and cloud engineering.** Both stay off until your project profile switches them on. See [Memory client and cloud engineering](#memory-client-and-cloud-engineering).

## Installation

Installing the plugin has two parts, and both are on this page, in order. First you install it through your provider, which delivers the plugin's skills, agents and hooks. Then you finish the setup inside your project, which creates the files that describe *your* repository. When the checklist at the end of [Complete the installation in your project](#complete-the-installation-in-your-project) is ticked, you are ready to run `/flow`. You need nothing else from this README to get there.

This is the **plugin route**. Copying the assets into your repository instead is **vendoring**, a separate procedure described in [Quick start in a new project (vendoring)](#quick-start-in-a-new-project-vendoring). Do not combine the two.

### Install the plugin

The repository is its own marketplace, so no separate marketplace repository is involved.

#### Claude Code

```
/plugin marketplace add lneninger/claude-agentic-auto-improve
/plugin install agentic-auto-improve@auto-improve
```

#### OpenAI Codex

```bash
codex plugin marketplace add lneninger/claude-agentic-auto-improve
```

Then install `agentic-auto-improve` from `/plugins`. Start a new session afterwards; Codex
does not load a plugin's skills into the session that installed it.

#### Cursor

Run `/add-plugin` and give it this repository. Cursor reads the root `plugin.json`
(the vendor-neutral Agent Plugins manifest) and `.cursor-plugin/plugin.json` beside it.

### Complete the installation in your project

The provider install gives you the plugin. It does not know your repository. These five steps finish the job. Follow them in order, in the project where you will use the plugin.

#### Step 1: Know what the install gave you and what stays yours

| Layer | What it holds | Where it lives | Who keeps it current |
|---|---|---|---|
| **Plugin-owned** | The skills (the slash commands), the agents, the hooks and their registration, the working agreements, the scripts, the templates, the references and the Universal tier of the registries | The provider's plugin cache. For Claude Code that is `~/.claude/plugins/cache/auto-improve/agentic-auto-improve/<version>/`. It is **not** inside your repository | The plugin. A new version replaces it (see [Updating an installed plugin](#updating-an-installed-plugin)) |
| **Project-owned** | `.claude/project-profile.md`, `.claude/area-mapping.json`, `.claude/work-item-conventions.json` and `.claude/.project-tokens.json`; your registries' project tier, your concept contracts (`.claude/concepts/`) and your work item briefs (`.claude/work-items/`) | Your repository's `.claude/` folder. Commit these files | You. Step 3 creates and fills them |
| **Optional add-ons** | Opt-in checks and rule documents | Files copied into your project, plus rows in your `.claude/settings.json` | You, through each add-on's own install and uninstall skills (see [Managing optional add-ons and retired hooks](#managing-optional-add-ons-and-retired-hooks)) |

Three things follow from that table.

- **Installing turns enforcement on.** On Claude Code the plugin's own `hooks.json` registers its hooks. They are gates, not suggestions: from the next session on, an edit to a non-trivial file is blocked until an approved concept contract names it, and edits in a repository's main checkout are refused.
- **You never copy a plugin-owned file into your project to make the plugin work.** The skills find the plugin's scripts themselves.
- **You never register the plugin's hooks in your own `settings.json`.** Claude Code does not merge a project hook with the same command in a plugin's `hooks.json`; both run. A hook registered on both sides therefore runs twice. Your `settings.json` holds only hooks that are yours, plus the rows of add-ons you choose to install.

Hooks are Claude Code only in this release. Cursor and OpenAI Codex receive the skills (and, on Cursor, the agents), not the hooks. [What each provider actually gets](#what-each-provider-actually-gets) has the full table.

#### Step 2: Start a new session

Claude Code reads hook registrations once, when a session starts. A session that was already open during the install does not run the plugin's hooks. Start **one** new session in your project after installing, and run Step 3 in it. Step 3 writes project files only and registers nothing under a plugin install, so you need no second restart after it.

- **Claude Code:** start a new session after `/plugin install`.
- **OpenAI Codex:** start a new session after installing from `/plugins`. Codex does not load a plugin's skills into the session that installed it. Codex runs no hooks, so nothing else needs a restart.
- **Cursor:** this repository does not document or test Cursor's session behaviour. If `/auto-improve-finish-install` is not offered after the install, start a new session before Step 3. Cursor runs no hooks either.

#### Step 3: Complete the project setup with `/auto-improve-finish-install`

```
/auto-improve-finish-install
```

Run it once per project, from your project's folder, in the new session. The name carries the plugin's name because you may have several plugins installed.

The plugin cannot copy some things for you, because they describe your repository: the project profile, and three files built from it. The skill looks at your repository, shows each proposed value next to the file that suggested it, asks once, and writes only what is still a placeholder. A script, `auto_improve_finish_install.py`, holds every rule, and the skill only carries the conversation. Each write is bound to a plan hash: if a file changes between the preview and the write, the write is refused as `changed-since-preview` and you see a fresh preview.

**First, one question about scaffolding.** If `.claude/project-profile.md` does not exist, the skill runs the doctor (`plugin_doctor.py`) in report mode, which writes nothing, and shows you the whole list of what its fix would create. Only after your yes does it run the fix. The fix never overwrites a file that exists. It creates:

- the folders `.claude/concepts/`, `.claude/work-items/`, `.claude/north-stars/` and `.claude/orchestrator/results/`;
- copies from the plugin: `.claude/templates/concept-contract.md`, and the three registries `MECHANISMS.md`, `VOCABULARY.md` and `JOURNAL.md` under `.claude/registries/`, each with a `general.md` skeleton in its own folder;
- scaffolds with placeholders, never invented values: `.claude/project-profile.md`, `.claude/area-mapping.json`, `.claude/work-item-conventions.json` and `.claude/.project-tokens.json`.

It leaves `.claude/settings.json` alone.

**Then three stages.**

| Stage | What it does | What you review or confirm |
|---|---|---|
| **1. Project profile** | Fills the placeholder slots of `.claude/project-profile.md` from evidence in your repository. Each slot is `inferred` (a marker was found), `needs-answer` (the script will not guess), `kept-authored` (you already wrote it) or `none-found` (it becomes `none`) | One confirmation of the whole table. It asks only about the `needs-answer` slots: the theme polarity of each frontend root, the safety-critical roots, which candidate folders are auth roots, and whether each local agent is an implementer, a review gate or neither |
| **2. Project files** | From the profile, proposes `.claude/area-mapping.json`, the `prTitle.map` and `prTitle.order` entries of `.claude/work-item-conventions.json`, and `.claude/.project-tokens.json` | The diff for each file. The tokens to keep: only a token you name is ever written. A separate yes or no when the token list is still empty, because filling it changes how shared memory items are scoped. Any file you want skipped |
| **3. Hooks** | Plugin install: prints a readiness report and writes nothing. Vendored copy: shows the `settings.json` change as a diff and writes it, with a backup, only after your yes | Under a plugin install, nothing. [Step 4](#step-4-verify-the-installation) explains the report |

The profile matters even under a plugin install. A generic agent cites a profile slot by name rather than a literal path, so every slot must be present, and an empty slot reads `none`. The profile is the only file you must author for the agents to be correct, and this skill drafts it for you.

**It never guesses and never overwrites.** A slot you wrote, and a step-3 file you wrote, are never changed. If your value differs from what the script would propose, the skill shows both and leaves yours. Declining at any question writes nothing. Before Stage 2 replaces a file, it copies the old one into a backup folder under `.claude/cache/finish-install/` and prints the path. (Stage 1 rewrites only the placeholder slots of the profile, bound to the plan hash, and takes no backup. A vendored Stage 3 backs up `settings.json` beside it as `settings.json.bak-<UTC stamp>`.) If your `.gitignore` does not cover `.claude/cache/`, add it.

**You can run it again safely.** A second run changes nothing: authored slots and files stay as they are, and nothing is rewritten when everything is already present.

**If setup is incomplete.**

- You answered no to a question: nothing was written. Run `/auto-improve-finish-install` again when you are ready.
- Stage 2 says the profile is missing or still has placeholders: finish Stage 1, then run the skill again.
- Stage 2 reports a file as `scaffold-missing`: the doctor's fix has not run. Run the skill again and say yes at the scaffolding question.
- The doctor prints `plugin: NOT FOUND`: the skill asks you for the plugin's path, once.
- A refusal with exit code `2` can be corrected, and `3` is an environment problem. In both, nothing was changed, and the message names the reason.
- `plugin-source-checkout`: you ran it inside the plugin's own checkout. Run it in your project instead.

**Commit what it created.** The registries, contracts and briefs are your project's design history, and the profile files are the team's shared configuration. Commit them. Never delete, gitignore or bypass the registries.

**If your project has a database,** also run `/auto-improve-database-guard-install`. It finds the database names in your tracked configuration files, shows each with the file and line that names it, asks which to protect, and appends only those names to the guard's rules file. Until you do, the plugin's database guards treat every database as protected. That is strict on purpose, and naming your databases narrows it, so the skill asks a separate yes or no before it does. It never removes a name, and it prints the server-trigger line for a person to run.

#### Step 4: Verify the installation

Registration belongs to the plugin, so verifying only reads. Nothing here asks you to register a hook.

**On Claude Code,** run `/auto-improve-finish-install` again, which is safe, and read its hooks stage. Under a plugin install the stage gives you a readiness report, and the skill reads it out in plain words. Behind it are these fields. A healthy report shows:

- `mode: plugin` and `ready: true`, with the verdict "ready to load (not proof the running session loaded them)";
- all ten checks passing: `enabled`, `manifest-hooks-resolves`, `hooks-registered`, `commands-resolve`, `launcher-found`, `hooks-compile`, `hooks-not-disabled`, `no-duplicate-registration`, `version-matches-marketplace` and `platform-launcher`.

"Ready to load" is not "live". The report cannot see that your running session loaded the hooks, that a project trust prompt was accepted, or that a hook's imports of its helper files succeed at run time. So finish with one real test. **In a new session, ask for an edit to a source file that no approved contract covers.** The concept gate should block it. In a repository's main checkout you will see the `MAIN CHECKOUT` banner instead, from the guard that refuses edits there. Either block proves the hooks are loaded.

**Reading a problem.**

| What you see | What it means | What to do |
|---|---|---|
| The hooks stage stops with `plugin-disabled` or `install-mode-none` | The plugin is installed but not enabled, or this project is not a plugin install at all | Enable or install the plugin, then start a new session. Do not add hooks by hand |
| The hooks stage stops with `install-mode-both`, or the report shows `duplicate-vendored-registration` | The same hooks are registered by the plugin and by your project's settings, so each runs twice | Remove the registration on one side. Which side is your decision. For a plugin user, remove the project's copies of the plugin's hooks |
| `commands-resolve`, `launcher-found` or `hooks-compile` fails | A hook cannot start | Update or reinstall the plugin. Do not edit the cache: the next update replaces it |
| `disable-all-hooks` is true | `disableAllHooks` is set in a settings file | Remove that setting, then start a new session |
| `version-matches-marketplace` fails | The installed copy and the marketplace clone differ | Run the update commands in [Updating an installed plugin](#updating-an-installed-plugin) |
| A platform note on macOS or Linux | The cached `hooks.json` launches `py -3`, which does not exist there, so no hook can start | A plugin install cannot fix this, and an edit to the cache is lost at the next update. Copy the hooks into the project instead, as described in [Quick start in a new project (vendoring)](#quick-start-in-a-new-project-vendoring), or wait for a per-platform hooks format |
| The test edit is not blocked in a new session | That session did not load the hooks | Check the report, then start a new session |

**Recovering without duplicating registrations.** To repair a plugin install, enable, update or reinstall the plugin and start a new session. Do not add the plugin's rows to your `settings.json`. The script refuses to: `hooks --apply` under a plugin install is rejected as `plugin-install-needs-no-registration`.

**Plugin-managed hooks and optional add-ons are different things.** The plugin's hooks come from its own `hooks.json`, and your `settings.json` holds none of them. The only hook rows you should find in your `settings.json` are your own and those of add-ons you installed on purpose. The strict shell gate and the code-search-first guard are add-ons: they are off unless you install them (see [Managing optional add-ons and retired hooks](#managing-optional-add-ons-and-retired-hooks)).

**On Cursor and Codex,** hooks do not exist, so there is nothing to register or verify. `/auto-improve-finish-install` runs Stages 1 and 2 in full. Its hooks stage answers `provider-has-no-hooks` and writes nothing.

#### Step 5: Start using the plugin

`/flow` is the front door. Give it an issue number, a link, or a sentence describing the work:

```
/flow <an issue number, a link, or a sentence describing the work>
```

It runs the chain in order and pauses only where a person has to decide. The first time, expect this:

1. **It announces how far it will go.** By default that is a draft pull request. The flags `--to-contract`, `--to-green` and `--to-commit` stop earlier.
2. **Intake.** `/task` first puts the work in a worktree of its own under `.claude/worktrees/` and asks once: a new worktree, or the current checkout. Take the new worktree. In a main checkout it refuses the other answer, because edits there are refused. It then writes a work item brief to `.claude/work-items/` inside that worktree, asks about anything ambiguous, and sizes the item.
3. **Design.** A medium or larger item gets a concept contract in `.claude/concepts/`. The run stops there. You answer the open questions and you approve the contract. Nothing approves it for you. An extra small or small item skips this step.
4. **Build and check.** Failing tests come first, then the code, then reviewer agents and the verification run.
5. **Commit and pull request.** It asks before it commits and before it pushes. The pull request is a draft.

No further setup is needed if Steps 1 to 4 are done, with one exception. If you pass an issue number, or want the draft pull request opened, the GitHub CLI must be installed and signed in (`gh auth status`; `gh auth login` if it is not). A free-text request works for intake without it. For work split across several sub-tasks, see [When a contract has several sub-tasks](#when-a-contract-has-several-sub-tasks).

#### Installation is complete when

- [ ] You installed the plugin through your provider and started a new session afterwards (Claude Code and Codex).
- [ ] `/auto-improve-finish-install` finished Stages 1 and 2: `.claude/project-profile.md` has no placeholder slot left (an empty slot reads `none`), and `.claude/area-mapping.json`, `.claude/work-item-conventions.json` and `.claude/.project-tokens.json` exist.
- [ ] The doctor's scaffold exists: `.claude/registries/`, `.claude/concepts/`, `.claude/work-items/` and `.claude/templates/concept-contract.md`. You committed the files.
- [ ] Claude Code only: the hooks stage reported `mode: plugin` and `ready: true` with no failed check, and your `.claude/settings.json` registers none of the plugin's hooks.
- [ ] Claude Code only: in a new session, an edit to a source file with no approved contract was blocked.
- [ ] If you will pass issue numbers or open pull requests: `gh auth status` succeeds.
- [ ] If your project has a database: you ran `/auto-improve-database-guard-install`, or you chose to keep every database protected.

On Cursor and Codex the hooks items (the fourth and fifth) do not apply. When every item that applies is ticked, run `/flow`.

### Updating an installed plugin

This section covers the **plugin**. Add-ons you installed in a project are updated separately (see [Updating an installed add-on](#updating-an-installed-add-on)), because a plugin update never touches them.

**Claude Code.** A merged change reaches a running session only when the plugin's version number
changes. Sessions run the hooks from the versioned install cache, at
`~/.claude/plugins/cache/auto-improve/agentic-auto-improve/<version>/`, and not from the
marketplace clone. These two commands refresh them:

```
claude plugin marketplace update auto-improve
claude plugin update agentic-auto-improve@auto-improve
```

The second command answers "already at the latest version" and leaves the cache alone when
the version is unchanged. So a fix merged without a version bump never reaches an installed
copy. (For maintainers: the version is declared in five places, and all five must change together:
`plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (twice) and
`.cursor-plugin/plugin.json`.)

**OpenAI Codex and Cursor.** This repository documents and tests update commands for Claude Code only. For these two, use the provider's own plugin update.

**After the update:**

- **Start a new session.** Hooks are read when a session starts, so the running session keeps the old ones.
- **Your project configuration is not regenerated.** A plugin update replaces plugin-owned assets in the cache. Your profile, your step-3 files, your registries, contracts and briefs stay exactly as they are.
- **You do not have to run `/auto-improve-finish-install` again.** Running it is safe, because it changes nothing that you wrote. It is useful when a release adds a profile slot: its preview lists any row your profile lacks (`rows-to-add`), and it never changes a slot you wrote.
- **Add-ons stay as they were.** Their files and `settings.json` rows were copied into your project, and the plugin update does not rewrite them.
- **Validate the update.** Search the cache folder (not the marketplace clone) for the new version's folder. Then run `/auto-improve-finish-install` and read its hooks stage: a failed `version-matches-marketplace` check means the installed copy and the marketplace clone differ.

### Managing optional add-ons and retired hooks

This section is the reference for the whole life of an add-on: choosing one, installing it, updating it, removing it, and recovering when something goes wrong. It also keeps the history of the hooks that were retired, and says which of them can be brought back.

An **add-on** is an opt-in set of files that the plugin ships under `.claude/addons/` but never registers. The plugin's own `hooks.json` knows nothing about add-ons, so a default install runs none of them. Each add-on has an install skill and an uninstall skill. They are the only supported way to add or remove one.

Four kinds of hook exist, and the difference matters when you read a `settings.json`:

| Kind | Hooks | Registered by | Where it runs from |
|---|---|---|---|
| **Default plugin hooks** | The thirteen registrations in [What the plugin's hooks do](#what-the-plugins-hooks-do), including `plan-question-advisor.py` since 0.9.8 | The plugin's `hooks.json`, automatically | The plugin cache. Your `settings.json` holds none of them |
| **Optional add-on hooks** | `codegraph-first-guard.py` and `bash-gate.py` | Your project's `.claude/settings.json`, written by the add-on's install skill | Copied into your project's `.claude/hooks/` |
| **Retired hooks** (disabled) | `angular-tailwind-advisor.py`, `codegraph-turn-tracker.py` and `codegraph-turn-reset.py` | Nothing. No install copies or registers them | The files still ship in the add-on folders. Only a project with an older install still carries them |
| **Removed** | `plain-language-guard.py` (removed in 0.9.20) | Nothing | Gone. [Removed in 0.9.20](#change-notes-by-version) says how to take out a vendored copy |

#### Available add-ons

| Add-on | Assets / hook files | Functionality | Why it is opt-in | Install command | Uninstall command |
|---|---|---|---|---|---|
| `angular-tailwind` | No hook. Four rule documents in `.claude/references/angular-tailwind/`, listed in the profile's `review.documents` slot; optional stylesheet snippet; helper `_project_paths.py` | Rule documents with stable Rule IDs (`A-nnn`, `M-nnn`, `T-nnn`, `P-nnn`) that `architecture-guard.py` cites and agents read. Needs a project profile with a `review.documents` row | Suits only Angular plus Tailwind projects. The guard already enforces at the write | `/auto-improve-angular-tailwind-install` | `/auto-improve-angular-tailwind-uninstall` |
| `codegraph` | `codegraph-first-guard.py` in `.claude/hooks/` with two rows (`PreToolUse` on `Read\|Grep\|Glob`, and `UserPromptSubmit` with the argument `notice`); helpers `_project_paths.py` and `_error_log.py`; the `mcp__codegraph__*` permission entry | Blocks a source `Read`, `Grep` or `Glob` until a CodeGraph call has run in the turn; lets reads through when CodeGraph is provably unavailable. Needs the CodeGraph MCP server | Two program starts (every `Read`, `Grep` and `Glob`, and every prompt), plus one blocked round trip per new source call while the gate is closed | `/auto-improve-codegraph-install` | `/auto-improve-codegraph-uninstall` |
| `strict-shell-gate` | `bash-gate.py` in `.claude/hooks/` with one row (`PreToolUse` on `Bash`); helpers `_project_paths.py`, `_shell_write_targets.py` and `.claude/scripts/_contract_index.py` | Reads each shell command before it runs and blocks a write into a source file that no approved contract covers | A program start on every shell command. It misreads some commands and cannot see what a program writes (details below) | `/auto-improve-strict-shell-gate-install` | `/auto-improve-strict-shell-gate-uninstall` |

Notes that apply to all three:

- **No add-on has a kill switch.** The way out of an add-on is its uninstall skill. See "No add-on has a kill switch" in [Change notes by version](#change-notes-by-version) for the variables that are no longer read.
- **Add-ons are Claude Code only.** Do not use the add-on skills on Cursor or OpenAI Codex: hooks are Claude-only in this release.
- **Run them inside your project.** Run inside the plugin's own checkout, an add-on skill is refused as `plugin-source-checkout`.
- **`angular-tailwind` in detail.** It starts no program on any prompt. The scroll-edge classes (`.scroll-edge`, `.scroll-edge-content`, `.scroll-edge-header`) are appended to a global stylesheet only when you name one with `--stylesheet`. The skill offers the candidates and asks. No uninstall takes the snippet out again.
- **`codegraph` in detail.** The install stops with a plain message (`codegraph-mcp-not-configured`) when the CodeGraph MCP server is not configured, has no command or url, or is listed as disabled. It does not check that the server is running. See [When CodeGraph is unavailable](#when-codegraph-is-unavailable) below.
- **`strict-shell-gate` in detail.** Its reasons to stay opt-in are measured. The parser read `--stat` as the file written in `sed -i` followed by `git diff --stat`, and blocked a correct command. It sees only the command line, so it cannot see what `python script.py` or `node build.js` writes. The Changed-file check, which stays on whatever you decide, catches those writes after the fact. Choose this add-on only if you want the early block and accept the false alarms.

#### Installing an add-on

1. **Choose.** Use the table above. Each add-on stands alone, and none installs another. Before an add-on that writes to the project profile (`angular-tailwind`), finish [Step 3](#step-3-complete-the-project-setup-with-auto-improve-finish-install) of the installation, or the install stops with `profile-slot-missing` and writes nothing.
2. **Invoke its install skill** from your project, for example `/auto-improve-strict-shell-gate-install`. The skill finds the installer script itself. `codegraph` uses the plugin's copy only, because a vendored installer can be older than the hooks it manages. The other two look for a vendored copy in your project first and then for the plugin's.
3. **Read the preview.** The skill runs `auto_improve_finish_install.py addon --name <add-on> --project .`, which writes nothing, and shows you in plain words: each file it would copy and the action for it (`copy`, `present`, `update` or `keep-existing`); the exact `unified-diff` of `.claude/settings.json` and how many rows it adds; the profile change and the stylesheet change, for `angular-tailwind`; the permission entry, for `codegraph`; any notes; and that the add-on has no kill switch. For `strict-shell-gate` it first reads you what it gets wrong. It then asks **one** question. A no writes nothing.
4. **What your yes approves.** Exactly the bytes in that preview, and no more. The apply carries the preview's plan hash, so if a file or the plugin's copy changed since you looked, the apply is refused as `changed-since-preview` and you see a new preview.
5. **What is created or changed.** The add-on's hook files go into `.claude/hooks/`. New rows go into `.claude/settings.json`, after a timestamped backup (`settings.json.bak-<UTC stamp>`) when the file already exists. `angular-tailwind` instead copies documents and appends their paths to `review.documents`, and writes no row and no backup in a normal install (the one exception is retiring an old advisor row, below). `codegraph` also adds `mcp__codegraph__*` to `permissions.allow`.
6. **How the rows are written.** Each row is a Project hook launcher row, `py -3 -c <launcher program> <class> <hook file>`, which runs the hook from your project's `.claude/hooks/` (see [Project hook launcher](#project-hook-launcher)). `PreToolUse` rows get the class `block` and every other event gets `warn`. The rows are inserted into your existing `settings.json` as text, so every other byte of the file stays as it was. A folder the install would write into that is a link to somewhere else (a junction on Windows) is refused. The hook files are copied first and the rows written last, so a row never points at a file that is not there.
7. **Helpers and dependencies.** A helper file is copied only when your project lacks it, and an existing one is never overwritten. The install never removes a row or a file, and it never overwrites a file that differs from the plugin's copy: it refuses with `addon-file-differs` instead. The one exception is the retirement of a disabled hook (see [Retired hooks and restoration](#retired-hooks-and-restoration)). A prerequisite that is missing, such as the CodeGraph server, stops the install before it writes.
8. **Start a new session.** Claude Code reads hook rows once, when a session starts, so the rows take effect only in a new session. `angular-tailwind` writes no row, so a normal install needs no new session: its documents are files that agents read through `review.documents`. When it retires an old advisor row it does need one (see [Retired hooks and restoration](#retired-hooks-and-restoration)).
9. **Validate.** Run the install skill again: its preview finds nothing left to write (every file `present` or `keep-existing`, no row to add). Then, in a new session, see the add-on act: a source `Read` before any CodeGraph call is blocked with the guard's banner (`codegraph`); a shell command that writes to a source file with no approved contract is blocked (`strict-shell-gate`). For `codegraph`, `auto_improve_finish_install.py addon --name codegraph --check` is a read-only check of the permission entry and of hook freshness (exit `0` clean, `1` findings, `2` could not check). `plugin_doctor.py --drift` compares an installed add-on's files with the plugin's.

Refusals leave everything as it was. The ones you may meet: `addon-file-differs` (a file of the add-on exists in your project and differs; compare it with the plugin's copy, then follow [Recovery and troubleshooting](#recovery-and-troubleshooting)), `disabled-hook-present`, `changed-since-preview`, `write-failed` (for example `.claude/settings.json` is a symbolic link; edit the file the link points to by hand, or replace the link with a real folder), `project-hook-launcher-missing` and `addon-unknown`.

#### Updating an installed add-on

A plugin update does not change the add-on files in your project, and the add-on skills do not update themselves. How an add-on is updated depends on the add-on.

- **`codegraph`:** re-run `/auto-improve-codegraph-install`. A hook file that is an unedited copy of an older release is saved as `<hook>.bak-<UTC stamp>` and replaced. A missing row is added. A row is never rewritten: when a registered row differs from the manifest's (its `if`), `addon --name codegraph --check` reports `addon-row-outdated`, and the route is `/auto-improve-codegraph-uninstall` and then the install again. `addon --name codegraph --check` and `/verify-before-done` Step 5.8 name an outdated hook. Moving a project from a release before 0.17.0 takes two runs with a new session between them; see [Retired hooks and restoration](#retired-hooks-and-restoration). A project that records its hook registrations must re-record them afterwards (see [Checking your hook registrations](#checking-your-hook-registrations)), because the row count can change.
- **`strict-shell-gate` and `angular-tailwind`:** the plugin keeps no list of their earlier releases, so a file in your project that differs from the plugin's copy is refused as `addon-file-differs`. Compare it with the plugin's copy and move any edits of yours over. Then run the uninstall skill, which keeps a file that differs. Remove the old file by hand and run the install skill again. For `strict-shell-gate`, start a new session after the uninstall and before you delete the file, because the open session still holds the row, and a row whose file is missing stops every shell command.

#### Uninstalling an add-on

Run the add-on's uninstall skill, for example `/auto-improve-codegraph-uninstall`. It runs `auto_improve_finish_install.py addon-remove --name <add-on>`. It previews every row, file and profile entry it would change, asks **once**, and writes only after your yes. The safety rules are these:

- **Order.** It writes `settings.json` first, with a backup, then the project profile (`angular-tailwind`), and deletes files last. A hook row that points at a missing script blocks the event, so the row must go before the file. Never delete a hook file by hand before its row is gone.
- **Plan hash.** The apply carries the preview's plan hash. Anything that moved since the preview is refused as `changed-since-preview`.
- **Backup.** `settings.json.bak-<UTC stamp>` is written before the file is replaced, and the skill prints the copy command that puts it back. Add `.claude/settings.json.bak-*` to your `.gitignore`.
- **Files that you edited are kept.** A hook file is deleted only when it is identical to the plugin's copy (line endings and a leading byte order mark ignored) or, for an add-on whose manifest lists earlier releases (`codegraph` and the disabled hooks), matches a copy an earlier release shipped. `strict-shell-gate` lists none, so only an identical copy is deleted. A file that differs is kept and reported as `kept-differs`. Its row is still removed.
- **Files that another row still names are kept.** A row in `settings.local.json` or your user settings that still names the file keeps it, as `kept-referenced`. Remove that row first.
- **Helpers are never deleted.** `_project_paths.py`, `_error_log.py`, `_shell_write_targets.py` and `.claude/scripts/_contract_index.py` stay, because other hooks use them.
- **Other things deliberately stay.** The `mcp__codegraph__*` permission entry stays (it is harmless without the hooks). The stylesheet snippet of `angular-tailwind` stays in your stylesheet, and the block between its two marker comments can be deleted by hand. The `codegraph` measurement log under `.claude/logs/` and the hook backups (`*.bak-*`) stay. Delete them yourself if you want them gone.
- **`angular-tailwind` removes exactly its four document paths** from `review.documents`. Every other entry keeps its own text, and an empty slot reads `none`. It also cleans up the retired advisor under either file name.
- **Nothing unrelated is touched.** The profile slots, your other settings rows and the plugin's own hooks are not changed, and the concept gate and the Changed-file check stay on.
- **Already removed.** A file that is gone is reported as `absent`. If there is no row and every file is `absent`, the add-on is not installed: the skill says so and writes nothing. A second run after a removal changes nothing.
- **Start a new session** after a removal that took a row out. The open session still runs the hook.

If `settings.json` is too irregular to edit safely, the skill refuses (`malformed-settings` or `unexpected-settings-shape`), writes nothing, and names the file. Remove the add-on's rows by hand, then run the skill again.

#### Retired hooks and restoration

**What happened, in order.**

- **0.7.0** retired six hooks, when the plugin took over its hooks and reduced the number of gates: `plan-question-advisor.py`, `architecture-advisor.py`, `bash-gate.py` and the CodeGraph guard, tracker and reset hook.
- **0.9.8** brought `plan-question-advisor.py` back as a **default** hook. The repository records the change but no separate reason for it. What is documented is what the hook does: on a prompt sent in plan mode it adds a short reminder that points at the `plan-questions` skill. It never blocks, and the `CLAUDE_PLAN_QUESTION_ADVISOR=off` variable turns it off. Unlike the add-on hooks, it is registered by the plugin itself, so you do nothing to get it.
- **0.9.9** brought the other five back as three opt-in add-ons: `angular-tailwind` (the advisor), `codegraph` (the CodeGraph guard, tracker and reset hook) and `strict-shell-gate` (`bash-gate.py`). The plugin ships their files under `.claude/addons/` but never registers them.
- **0.10.0** disabled the angular advisor. **0.17.0** disabled the CodeGraph tracker and reset hooks. 0.9.20 removed `plain-language-guard.py` outright.

**Why the others stay opt-in, and why the disabled ones are disabled.**

- **`angular-tailwind-advisor.py`** (formerly `architecture-advisor.py`). It was registered on `UserPromptSubmit` with no matcher, so Claude Code started a Python program on **every** prompt, whether or not the prompt was about UI. Only its output depended on keywords. The median of seven runs was 123 ms against 50 ms for a bare Python start. That was measured once, on one Windows workstation, for issue #84, and not again. It also added about 400 words of context whenever a keyword matched. The rules now live in four rule documents, a skill and a Rule ID on each guard line, none of which starts a program on a prompt. It never blocked anything, and `architecture-guard.py` was and is the enforcement. Its `DISABLED.md` lists two defects to fix before turning it back on: the keyword `ui` can never match, because the keyword pattern needs at least three characters, and a fallback reads a rules file from your home folder, outside the project.
- **`codegraph-turn-tracker.py` and `codegraph-turn-reset.py`.** The tracker ran after each CodeGraph call and wrote a marker file. The reset hook ran on every prompt and deleted the marker. Since 0.17.0 the guard decides from the session transcript, so the two have nothing left to do. Claude Code started one Python process for every prompt and one for every CodeGraph call. The timing run measured about 104.7 ms for the reset hook and about 101.4 ms for the tracker at the median, on one Windows workstation. The prompt row keeps one per-prompt start, because the connection notice has to run on every prompt.
- **`codegraph-first-guard.py`** costs two program starts and a blocked round trip per new source call while the gate is closed. It is useless without the CodeGraph server.
- **`bash-gate.py`** costs a program start on every shell command, misreads some commands and cannot see what a program writes.
- **The four post-edit checks are not retired.** They still exist as files and run, but inside `post-edit-dispatcher.py` rather than as four separate hook entries.

**Which retired hooks can be restored, and when.** A project cannot restore a disabled hook on its own, and no install skill will copy one back. Bringing one back is a **change to the plugin** (its `addon.json`, its version and its tests), described in the `DISABLED.md` file inside the add-on folder: `.claude/addons/angular-tailwind/DISABLED.md` and `.claude/addons/codegraph/DISABLED.md`. Consider it only for a concrete reason:

- the CodeGraph guard blocks a call you judge wrong, and you have reported it. The measurement log, `<project>/.claude/logs/codegraph-shadow.jsonl`, cannot tell a wrong block from a right one, so your report is the rollback signal;
- you want the per-prompt Angular reminder back and accept a program start on every prompt, after the two defects above are fixed.

For one project, the quick route is `/auto-improve-codegraph-uninstall` and a new session. It turns the gate off for that project until you install the add-on again.

**Leftovers of retired hooks in a project.** An older install may still hold their files or rows. The add-on install retires them in two steps, with a new session between, because a session that is already open still holds the rows it loaded and a row that names a missing script fails:

1. **Step A** (the first run) removes the rows from `.claude/settings.json` and deletes no file.
2. **Step B** (a later run, after a new session) deletes each file that is an unedited released copy and keeps an edited one, which it lists. It never refuses.

Until step B has run, `plugin_doctor.py --drift` reports the leftover files as `disabled-hook-installed`. They do nothing. The install is refused as `disabled-hook-present` (nothing written) when a row for a retired hook is in `.claude/settings.local.json`, or when step A finds an edited copy of a hook whose row it would remove. Run the add-on's uninstall skill in those cases, because it keeps an edited file.

#### Recovery and troubleshooting

**Which situation are you in?**

| Situation | What happens | What to do |
|---|---|---|
| A hook cannot run | A launcher row of class `block` (every `PreToolUse` row) stops the call and names the file. A `warn` row prints the message and lets the call through. An older plain row that names a missing script makes Python exit with code 2, which on `UserPromptSubmit` blocks every prompt | Run the add-on's uninstall skill. If the hook cannot run at all, use the table under [Ways out when a hook cannot run](#ways-out-when-a-hook-cannot-run) |
| A hook file or a helper file is missing, the row is still there | The row's class decides, as above. `bash-gate.py` with its parser file missing exits with an error that names the file, so a gate that stopped reading is loud, not silent | If you can still run shell commands, run the install skill again. It copies a missing hook file, and a helper file when the project lacks it, and writes no second row. If the missing file stops the shell itself (`bash-gate.py`) or every read (`codegraph-first-guard.py`), the install skill cannot run: use the table under [Ways out when a hook cannot run](#ways-out-when-a-hook-cannot-run) |
| The launcher is missing or invalid | The install refuses with `project-hook-launcher-missing` (exit code `3`) because the project's hooks folder has no usable `_project_paths.py` with the launcher. A class that is neither `block` nor `warn` makes the launcher print a message, run nothing and exit with code `1` | Bring the project's hooks folder to the same release as the scripts, then run the install again. Never write a row by hand to get past it |
| The install stopped half-way | Hook files are written first and rows last, so a row never points at a file that is not there. The worst case is a file with no row, which does nothing | Run the install skill again. Identical files are left alone and a row that exists is not written twice |
| The uninstall stopped half-way | Rows come out first and files last, so the worst case is a file with no row, which does nothing | Run the uninstall skill again. A second run finds nothing more to remove |
| A file differs from the plugin's copy | The install refuses with `addon-file-differs` and writes nothing. The uninstall keeps the file (`kept-differs`) | Compare the file with the plugin's copy at `.claude/addons/<add-on>/hooks/` in the plugin and move your edits over. Then run the uninstall skill, rename or remove the file by hand, and run the install again. Never copy the plugin's file over it blindly |
| You need your old `settings.json` back | A backup was written before every replacement | Copy `.claude/settings.json.bak-<UTC stamp>` over `.claude/settings.json`. The skill printed the exact command as its `rollback` line |
| The whole session is blocked by a hook | | Start Claude Code with `claude --settings '{"disableAllHooks": true}'`, repair the project, then start a normal session |

The scripts never overwrite a file that differs and never rewrite a row, so none of these routes silently replaces your configuration.

##### Ways out when a hook cannot run

In normal operation the uninstall skill is the way out. When an add-on's hook cannot run, its row
has to come out of `.claude/settings.json` by hand. Which route works depends on which hook fails.
The table describes rows in the earlier form, which name the file directly. A launcher row (see
[Project hook launcher](#project-hook-launcher)) whose file is missing exits by its class instead:
`block` rows (the `PreToolUse` ones) still stop the call with a message that names the file, and
`warn` rows print the message and let the prompt through.

| Failure | What you see | Route |
|---|---|---|
| `bash-gate.py` cannot import its parser | the hook's own message, which names `_shell_write_targets.py` | remove the row with the Edit tool. `bash-gate.py` judges only Bash, and the concept gate allows `.claude/` files |
| `bash-gate.py` is missing | Python's own error, exit 2, on every Bash call | the same Edit-tool route |
| `codegraph-first-guard.py` is missing | Python's error on every Read, Grep and Glob, including the read of `settings.json` that Edit needs first | edit the row through the shell, or edit the file outside the session |
| `codegraph-turn-reset.py` is missing (a project still on 0.16.x, before step A of the 0.17.0 upgrade) | with a launcher row, a warning on `UserPromptSubmit`; with a plain row written before the launcher, Python's error, so every prompt is blocked | edit `.claude/settings.json` outside the session, in an editor, or run `/auto-improve-codegraph-install` in a new session |
| `codegraph-turn-tracker.py` is missing (the same projects) | an error after each CodeGraph call; its marker is not read by a 0.17.0 guard, so nothing else changes | as for a missing `codegraph-first-guard.py` |

##### When CodeGraph is unavailable

A session with no `mcp__codegraph__*` tool is not a failure of the hook. Since 0.15.2 the guard
lets the read through when it can prove CodeGraph is unavailable (no index, no configured server,
a disabled server, a subagent, an index that belongs to another working tree); in any other
session, repeat the blocked call once and it is allowed and logged. Not after a `session-state-unusable` block, which offers no retry. After a `retry-ticket-unwritten` block the retry was not recorded, so the repeat is blocked once more (as `source-target` or `ambiguous-target`) and the identical call after it is allowed. `/auto-improve-codegraph-uninstall`
followed by a new session removes the guard. If the CodeGraph index is stale, run `codegraph sync`
or `codegraph init -i`.

## Quick start in a new project (vendoring)

> **This section is for vendoring. It is not how you install the plugin.** If you installed the
> plugin through a provider, do not follow these steps: your procedure is
> [Complete the installation in your project](#complete-the-installation-in-your-project).
> Following both would put plugin-owned files in your repository and register the plugin's hooks
> twice.
>
> You may have several plugins installed. The skill that finishes this one is named
> `auto-improve-finish-install`, so its name says which plugin it belongs to.

Vendoring copies the assets you want into your repository, so that it works when this checkout is
absent, and your project keeps them. The two routes differ like this:

| | Plugin installation | Vendoring (this section) |
|---|---|---|
| How the assets arrive | Through the provider's plugin mechanism. Skills, agents and hooks stay in the plugin cache | You copy them into your repository's `.claude/` |
| Hooks | Registered by the plugin's own `hooks.json`. Your `settings.json` registers none of them | You register them in `.claude/settings.json`. `/auto-improve-finish-install` shows the exact change and writes it after your yes |
| Project configuration | `/auto-improve-finish-install` | The same skill, after the copy steps below |
| Who maintains the files | The plugin. A new version replaces its assets | Your project, locally. You can edit them in place and sync them back (see [Ownership and direction](#ownership-and-direction)) |
| Updates | [Updating an installed plugin](#updating-an-installed-plugin) | Your sync workflow, configured in `.claude/.sync-config.json` (see step 6 and [CONTRIBUTING.md](CONTRIBUTING.md)) |
| What not to do | Copy plugin-owned files into your project, or register the plugin's hooks by hand | Register a hook that a plugin install also registers (it would run twice), or point a hook command at this checkout (see step 5) |

The two routes are not yet reconciled; see [Known limitations](#known-limitations) before mixing them.

1. **Copy the trees.** Copy the root-level `skills` and `agents` directories, and
   `.claude/hooks`, `scripts`, `templates` and `references`, into your project's
   `.claude/`, at their ordinary paths — so this repository's root `skills/` becomes your
   `.claude/skills/`, and its root `agents/` becomes your `.claude/agents/`. Do not create
   a subdirectory named after this repository; one copy, in the normal place.

   The two root directories are deliberately not where a vendoring consumer puts them. They
   sit at this repository's root because a plugin's components must, and they move into
   `.claude/` on the way into yours because that is where a project keeps them.

2. **Copy the registries.** They arrive in registry layout 2: the three root files hold the
   Universal tier and a `## Project tier` pointer, and `.claude/templates/registries/`
   holds the `general.md` skeleton for each registry folder. Put your own entries in
   `.claude/registries/<REGISTRY>/<domain>.md` with `registry_append.py`. Everything in
   those folders stays yours and is never synced. A project that still has `## Project:`
   sections follows "Moving a project onto registry layout 2" below.

3. **Fill in the project-shaped files: run `/auto-improve-finish-install`.** The doctor
   (`plugin_doctor.py --fix`) scaffolds `area-mapping.json`, `work-item-conventions.json` and
   `.project-tokens.json`, and the skill's second stage proposes their content from the
   profile you confirmed in step 4 (run its profile stage first). It shows each proposal next
   to the evidence that suggested it, writes the files after one confirmation, and never
   changes a file you already wrote. A token is written only when you name it.

   *By hand instead:* `area-mapping.json`, `work-item-conventions.json`,
   `project-profile.md` and `.project-tokens.json` ship with their schema and an empty
   content set, because their shape is generic and their content is not.
   `.project-tokens.json` is the one to fill in first: an unguarded outbound sync is how
   contamination spreads.

   **Upgrading from before 0.9.3:** `work-item-conventions.json` is project-owned and sync
   never rewrites it, so add the `issueTitle.subIssue` block (`$comment`, `legend` and
   `format`) from this repository's copy into yours. Until you do, `/task` Parent-aware mode
   refuses to open sub-issues (`conventions-missing`) rather than create a title without the
   parent. A vendoring project must also list `.claude/scripts/compose_subissue_title.py` in
   its sync configuration's `files` array, or the helper is never delivered. A project whose
   conventions file was built by the doctor already carries all nine effort tags in
   `issueTitle.effortTypes`, because the doctor scaffolds them, so it needs no fill-in there.
   Only `prTitle.map` and `prTitle.order` are project-shaped, and `/auto-improve-finish-install`
   proposes them (step 3).

   **Upgrading from before 0.9.4:** `/task`, `/design-first` and `/ship` now record the outcome
   of the issue offer (the question "should this work get a tracker issue?") in the brief, in an
   `issue_offer:` line. A new switch, `issueLink.requireRecordedOffer`, makes the link checker
   (`verify_issue_link.py`) stop when a brief has no issue and no recorded answer. **This
   repository's switch is `true`.** If you copy the `issueLink` block from this repository's
   copy into yours, leave `requireRecordedOffer` at `false` unless you want that stop. Turning
   it on needs the offer keys (`offerOutcomeField`, `offerOutcomes`, `offerReasonField`,
   `offerReasons`) and the `verdicts` list in your own conventions file: the checker reads the
   switch and those keys only from the conventions file in the same `.claude` folder as the
   brief, never from another project, and a switch that is on with any of them missing stops
   with `conventions-missing`. A missing switch or a missing file means off, so your projects
   keep today's behavior until you opt in. A conventions file beside the brief that exists but
   is not valid JSON stops the check even when the switch is off, because the switch cannot be
   read. One change reaches projects with the switch off: a
   brief with no issue that is found only through the work-items folder lookup, not at the path
   you passed, now stops with `brief-path-unresolved`. Pass the brief path as it exists from
   the current directory (`/ship` does).

4. **Write `.claude/project-profile.md`: run `/auto-improve-finish-install`.** It looks at
   your repository, shows each proposed value next to the file that suggested it, and writes
   the slots that are still placeholders after one confirmation. It never overwrites a slot
   you wrote.

   *By hand instead:* the profile is the only file you must author to make the
   fifteen agents correct, and it is required under a plugin install too. A generic agent
   cites a slot by name rather than a literal path, so every slot must be present, and an
   empty slot reads `none`.

5. **Register the hooks: the same `/auto-improve-finish-install` command does this as its
   third stage.** Under a plugin install it checks that the hooks are ready to load and
   writes nothing. Under a vendored copy it shows the exact `settings.json` change as a diff,
   asks, and writes it with a backup. The file is re-serialised, so the diff can show reflowed
   lines; the meaning is kept, and the diff is exactly what will be written. Either way, the
   hooks apply only in a session started afterwards.

   *By hand instead:* register the hooks in your `.claude/settings.json`, pathing every command through
   `$CLAUDE_PROJECT_DIR/.claude/hooks/`. `.claude/hooks/hooks.json` in this repository is
   the worked example: it registers all thirteen against the right events and matchers, so
   copy its entries and swap `${CLAUDE_PLUGIN_ROOT}` for `$CLAUDE_PROJECT_DIR`. A plugin
   install does this step for you and needs no `settings.json` edit, and a project that
   installs the plugin registers none of these hooks itself. A vendored copy of
   `working-agreements.py` prints nothing, because the shipped agreements arrive only
   with a plugin install; see [Working agreements](#working-agreements).
   Do not point a hook command at this checkout:
   `_project_paths.py` resolves a hook's `.claude` root from the hook file's own location,
   so a hook run from here would add this repository's registries as a second search root
   and could answer a lookup your project meant to answer itself.

6. **Add your sync configuration** at `.claude/.sync-config.json` and the tool that reads
   it. See CONTRIBUTING.md.

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

## Configuration and reference

Reference material for the plugin you installed above: what each hook does and which environment variable switches it off, release notes, the project hook launcher, the development workflow, what each provider gets, and the known limitations. You do not need any of it to install the plugin.

### What the plugin's hooks do

**The plugin is the source of its hooks.** Its `.claude/hooks/hooks.json` registers thirteen
entries that run its fourteen hooks, and they are active in every session that starts while the plugin is enabled. They are gates, not suggestions.
Installing and verifying them is covered in [Installation](#installation); this section is the reference.

**A project registers none of them itself.** Claude Code does not merge a project hook with the
same command in a plugin's `hooks.json`; both run. So a hook that your own `settings.json` also
registers runs twice. Your `settings.json` holds only the hooks that are yours.

What the plugin registers. Every entry is in exec form (`"command": "py"`, `"args": ["-3",
"${CLAUDE_PLUGIN_ROOT}/.claude/hooks/<script>"]`), so no shell parses it and
`${CLAUDE_PLUGIN_ROOT}` always names the running version:

| Event | Matcher | Hook | Blocks |
|---|---|---|---|
| SessionStart | none | `working-agreements.py` | no, it only adds text |
| PreToolUse | `Edit\|Write\|MultiEdit\|NotebookEdit` | `concept-gate.py` | yes |
| PreToolUse | `Bash\|PowerShell` | `gate-launch.py` with `concept-gate.py` (the main-checkout guard and merge-direction check; the gate half allows any shell command) | yes |
| PreToolUse | `Edit\|Write\|MultiEdit\|NotebookEdit` | `architecture-guard.py` | yes |
| PreToolUse | `Edit\|Write\|MultiEdit\|NotebookEdit` | `db-destructive-guard.py` | yes |
| PreToolUse | `Bash` | `db-destructive-guard.py` | yes |
| PreToolUse | `Bash` | `db-research-readonly-guard.py` | yes |
| PreToolUse | `PowerShell` | `db-destructive-guard.py` | yes |
| PreToolUse | `PowerShell` | `db-research-readonly-guard.py` | yes |
| UserPromptSubmit | none | `plan-question-advisor.py` | no, it only adds a reminder in plan mode |
| PostToolUse | `Edit\|Write\|MultiEdit` | `post-edit-dispatcher.py` (asynchronous) | no |
| Stop | none | `stop-dispatcher.py` (runs `../scripts/concept_changed_check.py`, then `protected-names-warning.py`) | yes, with a list of files no contract covers; the warning never stops a turn |
| Stop | none | `memory-pager.py` (asynchronous) | no |

- **`concept-gate`** blocks `Edit` / `Write` / `MultiEdit` on non-trivial files inside a project
  until an approved concept contract names them (a file with no `.git`, `CLAUDE.md`, `package.json`,
  `pyproject.toml` or `*.sln` anywhere on its path is outside every project and is not gated).
  Run `/design-first` to produce one.
- **`architecture-guard`** blocks banned patterns at the write, using the project's own rules.
- **`db-destructive-guard`** and **`db-research-readonly-guard`** block database operations
  that could destroy data. As of 0.7.0 the plugin registers both guards itself. The destructive
  guard now runs on the edit group, `Bash` and `PowerShell`; the read-only guard runs on `Bash`
  and `PowerShell` and **has left the edit group**. Before 0.7.0 the guards ran on
  `Bash|Edit|Write|MultiEdit` and never on PowerShell.
  **A project that registers its own copy of a guard makes the plugin's copy stand down.** The
  plugin copy exits without acting, and writes a `deferred` line to the project's
  `db-guard.log`, only when all of these hold: the project's `settings.json` (and, when the
  session runs in a git worktree, that worktree's) has a `PreToolUse` row for the same tool
  that launches `<project>/.claude/hooks/<guard>` by that exact path; that file exists; the
  row is not `"async": true` and its timeout is at least the plugin's own; neither settings
  file sets `disableAllHooks`; and the row was in place when the session started. The last
  condition is read from a marker that the plugin's `SessionStart` hook writes for `startup`
  and `resume`. If any of this is in doubt, or anything fails, the plugin copy acts as it did
  before. The worst result is a guard that runs twice, never a call that no guard checks.
- **The shell row** launches `gate-launch.py` with `concept-gate.py` on `Bash` and `PowerShell`.
  The launcher runs the main-checkout guard and the merge-direction check before the gate; the
  gate half does nothing on a shell command, because the concept gate allows any tool that is
  not an edit. The guard reads the files a command writes with `_shell_write_targets.py`, a
  helper that ships beside it and is never registered. It costs one program start per shell
  command.
- **`stop-dispatcher`** is the single Stop seam. It runs two checks inside its process:
  `../scripts/concept_changed_check.py`, then `protected-names-warning.py`. If a check exits 2 the
  turn is stopped and its error text is shown. Any other failure is ignored. A later Stop check
  would join them without a second program start.
- **`protected-names-warning`** is the turn-end half of the Protected-name check. It compares the
  protected database names in this tree's `.claude/hooks/db-destructive-guard.rules.json` (and in
  the `CLAUDE_PROJECT_DIR` tree) with the same file at the tip of the local default-branch ref,
  using `_protected_names.py`. A removal, a respelling or an added space gives one `systemMessage`
  per session and set. It never stops a turn, never fetches, and makes no git call when neither
  the rules file nor the default-branch ref changed since its last run in the session. The same
  check runs from `.claude/scripts/protected_names_check.py` (exit 0 passes, 10 names removed,
  11 malformed, 12 unverifiable) in `/verify-before-done` Step 5.7 and in the contract landing.
- **`concept_changed_check.py`** (the Changed-file check, in the scripts folder) is the default enforcement of the concept
  rule for files a shell command or a program writes, which the edit-tool gate cannot see. At
  the end of a turn it asks git which files changed since the session started and judges each
  through `concept-gate.py`'s own matcher. It stops the turn once for a file no approved
  contract covers, never twice for the same set, and only notes files that the committed
  attribute files of `HEAD` mark `linguist-generated` (an untracked `.gitattributes`, the private
  `.git/info/attributes` file and a user-wide attributes file never count, and a
  `linguist-generated` line in `info/attributes` turns the exemption off for the whole run).
  `concept_changed_check.py --staged` runs the same judgement on the staged files at commit time;
  generated files do not stop the commit, but one line on standard error names them. It fails
  open when git is missing or slow.
- **`plan-question-advisor`** adds a short reminder to prompts sent in plan mode, pointing at
  the `plan-questions` skill.
- **`post-edit-dispatcher`** runs four small checks after an edit inside one process, in this
  order: `integration-check.py`, `critic-verdict-tracker.py`, `contract-status-watcher.py` and
  `journal-post-approval-tracker.py`. One check that fails never stops the next, and its output
  joins theirs, each part named by its file. Four process starts per edit became one.
- **`memory-pager`** stages a proposal when an always-loaded memory surface goes over budget.

**The guards read your rules, never the plugin's template.** Both database guards read
`<your project>/.claude/hooks/db-destructive-guard.rules.json` and nothing else. The file that
ships inside the plugin is only a template naming the fictional databases `AcmeApp` and
`AcmeApp_Testing`; it is never read. When your file is missing, unreadable or names no
database, or when `CLAUDE_PROJECT_DIR` is not set, the guards **fail closed**: every database is
treated as protected, and only a disposable suffix gets through. Copy the template to your own
`.claude/hooks/` and replace the names. No database name is built into the guard.

**The advisory hooks read your rules first.** `architecture-guard.rules.json`,
`architecture-guard.exceptions.json` and
`integration-check.rules.json` are read from your project's `.claude/hooks/` when it has them,
and from the template beside the hook otherwise.

Seven of the ten variables below are kill switches, set by you and never by an agent. Three are
not: `CLAUDE_ACTIVE_CONTRACT` is an approval pin, `CLAUDE_DESTRUCTIVE_DB_OK` is a one-shot
approval and `CLAUDE_CONFIG_DIR` names a folder. This table lists exactly the variables the hooks read, and a test (INV-12 in
`test_plugin_manifests.py`) fails when the two disagree.

| Variable | Effect |
|---|---|
| `CLAUDE_CONCEPT_GATE=off` | disable the concept gate and the Changed-file check (not the strict-shell-gate add-on) |
| `CLAUDE_PLAN_QUESTION_ADVISOR=off` | disable the plan-question advisor |
| `CLAUDE_ARCH_GUARD=off` | disable the architecture guard |
| `CLAUDE_INTEGRATION_CHECK=off` | disable the integration check (one piece of the dispatcher) |
| `CLAUDE_MEMORY_PAGER=off` | disable the memory pager |
| `CLAUDE_ACCURACY_TRACKER=off` | stop the three contract-accuracy trackers (the rest of the dispatcher) |
| `CLAUDE_WORKING_AGREEMENTS=off` | skip the working agreements at session start |
| `CLAUDE_ACTIVE_CONTRACT=<path>` | approval pin: pin one approved contract |
| `CLAUDE_DESTRUCTIVE_DB_OK=1` | one-shot approval for a destructive database operation |
| `CLAUDE_CONFIG_DIR=<path>` | where Claude Code keeps its configuration; the installed-plugin lookup reads `plugins/installed_plugins.json` and `plugins/cache/` there (default `~/.claude`) |

An `off` switch also accepts `0`, `false` and `no`. Beside the table, `CLAUDE_CONTRACT_INDEX=off`
turns the contract-lookup index off for concept-gate, which then reads every contract file itself.
To take the assets without the enforcement, vendor the repository instead of installing it and
register only the hooks you want.

### Change notes by version

Dated notes on changes to the hooks, the add-ons and the registries, kept as they were written. The upgrade tables for add-ons are here. The steps to install, update and remove an add-on are in [Managing optional add-ons and retired hooks](#managing-optional-add-ons-and-retired-hooks).

**Removed in 0.9.20:** the end-of-turn writing hook `plain-language-guard.py`, with its
`plain-language-guard.rules.json`. The plain-language agreement stays; only the checker is gone.
If your project vendored a copy, take it out in this order. First remove every row that runs
the hook from your `settings.json`: one on prompt submit, and in installs registered before 0.9.8
also one at turn end. Then delete the file and its rules file. Do not delete the file first: a
row that points at a missing script exits with code 2, so a prompt-submit row would block every
prompt. Start a new session afterwards. The hook's optional leftovers,
`.claude/state/plain-language-guard-<session>.json` and `.claude/logs/plain-language-guard.log`,
are never read again and you may delete them by hand. Since 0.12.4,
`plugin_doctor.py --drift` reports such a row as `dangling-hook-row` when it is an old
exec-form row (written before 0.12.3), a hand-written row that plainly launches a Python
script, or, since 0.14.5, a Project hook launcher row whose script is in none of the launcher's
folders (see the `--drift` paragraph).

**Changed in 0.9.21:** `architecture-guard.py` knows a component without view encapsulation
(`ViewEncapsulation.None`): `:host` matches nothing there, so it warns about a `:host` rule and
accepts a rule scoped under the component's element selector. The `angular-tailwind` add-on's
reminder says the same. The CodeGraph decision table gains a section for projects that installed
the `codegraph` add-on, and the contract template gains a token budget line and rule.

**Changed in 0.10.0 (the `angular-tailwind` rule documents, issue #84):** the `angular-tailwind`
add-on no longer starts a program on every prompt. The manifests read 0.10.0; the work was planned
as 0.9.22, and the version moved on while its sub-tasks were merged.

- **Four rule documents.** `ANGULAR_CODE_RULES.md`, `ANGULAR_MATERIAL_RULES.md`,
  `TAILWINDCSS_RULES.md` and `UI-UX-PATTERNS.md`. The install copies them to
  `.claude/references/angular-tailwind/` and lists them in the `review.documents` row of the
  project profile. It appends only paths not already listed, and writes nothing when all four
  are there. The add-on also ships a stylesheet snippet (`.scroll-edge`, `.scroll-edge-content`,
  `.scroll-edge-header`); the install appends it to a global stylesheet you name with
  `--stylesheet`, and no uninstall takes it out again.
- **A new skill, `angular-ui-rules`.** It carries the short rule list, keyed by Rule ID, and
  points at the documents. It always ships, and `angular-senior-dev` and `ui-ux-designer` preload
  it. When the documents are not installed, it says so and works from its short list.
- **The guard names the rule.** `architecture-guard.py` prints a Rule ID on every block and warn
  line (`A-nnn` Angular code, `M-nnn` Material, `T-nnn` Tailwind and styling, `P-nnn` patterns),
  then one footer line. The footer names the installed document when the file exists in the
  project, and otherwise says the rule text is not installed and which skill installs it.
- **Uninstall skills.** `/auto-improve-angular-tailwind-uninstall`, `/auto-improve-codegraph-uninstall`
  and `/auto-improve-strict-shell-gate-uninstall`, each paired with its install skill. They run
  `auto_improve_finish_install.py addon-remove`, which previews, asks once, writes `settings.json`
  first (with a backup), then the profile, then deletes files. A second run changes nothing. It
  keeps any file you edited, every helper file and the stylesheet snippet.
- **The advisor is disabled.** `angular-tailwind-advisor.py` still ships in the add-on folder,
  but no install copies it or writes its row. `.claude/addons/angular-tailwind/DISABLED.md` says
  what it did, what it cost, why it is off and how to turn it back on.

**No add-on has a kill switch.** `CLAUDE_SKIP_CG` (codegraph) and `CLAUDE_BASH_GATE`
(strict-shell-gate) are no longer read, and **`CLAUDE_CONCEPT_GATE=off` no longer turns off the
strict-shell-gate add-on**: it still turns off the concept gate and the Changed-file check, and
nothing else. The way out of an add-on is its uninstall skill. The retired `CLAUDE_ARCH_ADVISOR`
is no longer read either. If your own `CLAUDE.md` or shell profile tells you to set one of these
variables, take the line out: it does nothing now.

**Upgrading a project that has the old advisor.** Which rows the project carries depends on
when it installed. Every one is a `UserPromptSubmit` row with no matcher:

| Install age | Row in `settings.json` | File it names |
|---|---|---|
| add-on install, 0.9.9 to 0.9.21 | one row in exec form (`"command": "py"` with `"args": ["-3", ...]`, or `python3`) on `${CLAUDE_PROJECT_DIR}/.claude/hooks/...` | `angular-tailwind-advisor.py` |
| older installs, and hand copies of the plugin's own row (the plugin registered it itself up to 0.6.x; 0.7.0 took that out) | one row, either the string form `py -3 "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/..."` or `py -3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/..."`, or the exec form | `architecture-advisor.py` |

The steps, in this order:

1. Run `/auto-improve-angular-tailwind-uninstall`. It finds the row in every form above, under
   either file name, removes the row first and the file after. Do not delete the file yourself
   first: a row that points at a missing script exits with code 2 and blocks every prompt.
2. Run `/auto-improve-angular-tailwind-install` to put the documents, the profile entries and the
   stylesheet snippet in. Until step 1 has run, the install refuses with `disabled-hook-present`.
3. Start a new session. Claude Code reads hook rows once, when a session starts.

A project that never installed the add-on needs nothing: it gets no document and no row.

**What the change costs.** Before: the advisor was registered on `UserPromptSubmit` with no
matcher, so Claude Code started a Python program on every prompt, whether or not the prompt was
about UI. The median of seven runs was 123 ms against 50 ms for a bare Python start. It was
measured once, on one Windows workstation, for issue #84, and was not measured again. After:
the add-on registers no row on any event that runs per prompt, so no program starts for Angular
rules. That is proven by the manifest checker (`test_plugin_manifests.py`) and by the install
test (zero `UserPromptSubmit` rows written), not by a timing run.

**Changed in 0.17.0 (the `codegraph` guard decides from the session transcript, issue #262):** the add-on used to run three
hooks. The guard blocked source reads. The tracker wrote a marker file, `turn.json`, after each CodeGraph call. The reset hook
deleted that marker at each prompt. The cut-over keeps one hook file and retires the other two. Five changes:

- **The guard reads the transcript.** The transcript is the log file Claude Code writes for each session. A turn is the span
  after the last human prompt. Three things open it, each counted when the main session issues the call, whether or not the call
  succeeds: an `mcp__codegraph__*` tool use, a Bash call of a Counted `codegraph` command (the plain form of the 0.16.5
  command-line route), and an `Agent` or `Task` tool use, which is a subagent dispatch. A new human prompt closes the turn. A
  background task notification does not. A read that is not a clear open or closed answer (no transcript, an unreadable line, a
  window with no prompt in it, a rewritten file) is let through with a logged reason, `fail-open:transcript-<cause>`.
- **Two rows, one file.** The guard's file now has the `PreToolUse` row and a `UserPromptSubmit` row with the argument `notice`.
  The prompt row prunes old session folders once per session and shows the connection notice. It never blocks a prompt.
- **The tracker and the reset hook are disabled.** They still ship, under `disabled` in `addon.json`, with a note,
  `.claude/addons/codegraph/DISABLED.md`. No install copies them or writes their rows.
- **The retry escape is keyed to the prompt.** A retry ticket now matches only inside the prompt that issued it, so no hook has to
  delete tickets at a prompt any more.
- **The measurement log keeps writing.** Each guarded call appends one `enforced` record to
  `.claude/logs/codegraph-shadow.jsonl`, up to 10 MB. `codegraph_shadow_report.py` has an `enforced` section with the share of
  gated calls that failed open on the transcript, and says when the cap was reached. The log cannot tell a wrong block from a
  right one: report a block you judge wrong. The rollback rule is in `.claude/addons/codegraph/DISABLED.md`.

There is still no kill switch.

**Upgrading takes two runs of `/auto-improve-codegraph-install`, with a new session between them.** The first run (step A) removes
the tracker's and the reset hook's rows from `.claude/settings.json`, updates the guard and adds its prompt row. It deletes no
file, because a session that is already open still holds the old rows, and a row that points at a missing script fails. The second
run (step B) deletes the two leftover files when they are unedited released copies, and keeps an edited copy. The same two steps
now apply to the `angular-tailwind` add-on's retired advisor, which the install used to refuse. A `settings.local.json` row for a
retired hook is still refused as `disabled-hook-present`. A project with a Hook registration profile re-records it after step A,
because the row count went from four to two.

**Changed in 0.16.5 (the `codegraph` gate survives a dropped MCP connection, issue #295):** when Claude Code drops the
CodeGraph MCP connection in the middle of a session (seen after `/clear`), the index and the server entry are still
there, so the guard kept blocking and nothing said why. Five changes, all in the `codegraph` add-on:

- **A command-line route.** A Bash call of `codegraph query|explore|context|node|callers|callees|impact|files ...` that
  succeeds opens the turn like an `mcp__codegraph__*` call. It must be one plain command (an optional trailing `2>&1`;
  no pipe, `&&`, `cd`, variable prefix or path form), and a failed call opens nothing. The tracker handles it: a new
  fourth row, `PostToolUse` on `Bash` with `if: "Bash(codegraph *)"` and the argument `cli`. The marker gains a `route`
  (`mcp` or `cli`), and the Shadow record a `marker_route`, so the cut-over report can tell a command-line turn from an MCP
  one.
- **A two-route block message.** The banner names the MCP route, a copyable `codegraph explore "<term>"`, and says that
  in a worktree the command line reads the main checkout's index unless one was built there.
- **A connection notice.** At each prompt the reset hook says so when the server is configured and the index exists but no
  `codegraph serve --mcp` process belongs to this session. It is silent on a healthy session, for a subagent, and when it
  cannot tell; it never blocks; on the first prompt of a session it can be wrong while the server is still starting.
  A project instruction or a skill's gate that forbids shell commands wins over it.
- **One audit record.** The first successful command-line call of a session with no successful MCP call logs a
  `cli-fallback` record (`reason: mcp-unavailable`) in `errors.jsonl`.
- **A hook freshness check.** `addon --check` (and `/verify-before-done` Step 5.8) names an add-on hook that is an older
  release than the plugin's (both versions), a manifest row no settings layer has, and a row that lacks its `if`. The
  manifest gains `released_versions` (a release label per released hash) and the row key `if`. The two codegraph add-on
  skills and Step 5.8 now find the installer through the plugin only (`FIP`), because a stale vendored installer could
  neither see nor repair a stale hook.

There is still no kill switch: no variable or setting turns the gate, the route or the notice off.

**Upgrading.** Re-run `/auto-improve-codegraph-install`: the preview adds exactly one row (the Bash row) and replaces the
unedited older hook files. **A project with a Hook registration profile** (recorded with `record-registrations`) must
re-record it afterwards (`py -3 .claude/scripts/auto_improve_finish_install.py record-registrations --project .`, then
`--apply --expect-sha256 <plan hash>`), because the profile counts rows and there is now a fourth. A Bash row that an
older installer wrote without its `if` is reported as `addon-row-outdated`: run `/auto-improve-codegraph-uninstall`, then
the install again. After upgrading, `/verify-before-done` Step 5.8 reports NOT READY for a project still on 0.16.4 or earlier until the
codegraph add-on install is re-run (intended: its Bash row and hook copies are missing).

**Changed in 0.16.3 (the `codegraph` session folder moves to a per-user parent and fails closed, issue #271):**

- **The move.** The `codegraph` add-on's hooks keep every session folder under the Per-user session parent: `%LOCALAPPDATA%\auto-improve-codegraph\`
  on Windows; `$XDG_CACHE_HOME/auto-improve-codegraph/`, else `~/.cache/auto-improve-codegraph/` (mode `0700`, owned by
  you), on POSIX. Nothing in the system temp folder is read, written or pruned any more, so a `TMP` shared between users
  cannot carry a planted `turn.json` that opens your gate, and your pruner cannot delete another user's folders. The
  folders `auto-improve-codegraph-*` that 0.15.2 left in the system temp folder are inert (no longer read); delete them by
  hand if you want.
- **It fails closed.** When the parent or the session folder cannot be used (a link, a file, another user's folder, a folder
  open to other users, a network path (this check runs on Windows only), an unset or relative `LOCALAPPDATA` on Windows, a relative `XDG_CACHE_HOME`, or neither `XDG_CACHE_HOME` nor `HOME` set), a source read is blocked as
  `session-state-unusable`: the message names the folder, the problem in plain words and its fix, and offers no retry. The
  tracker writes no marker and the reset hook prunes nothing, and each prints that the gate stays shut. A ticket write that
  fails blocks as `retry-ticket-unwritten` (usually a passing lock or a full disk). This reverses 0.15.2's
  `state-unwritable` fail-open. A subagent, a project with no index and a project with no configured server are still let
  through.
- **A Foreign marker is logged.** The tracker stamps `turn.json` with `writer` and `session`. A marker without this
  session's stamp still opens the gate (it sits in a parent proven to be yours), and the guard logs it once per session
  (`foreign-marker`, with the cause).
- **The refusal says what to do.** `codegraph-tool-named` stays a refusal; its message now lists each entry with its layer and
  file, then the one step that fixes it: replace each entry with `mcp__codegraph__*`. One capability constant,
  `TREE_HOP_REFUSAL`, replaces `WORKTREE_OWN_ROOT_NATIVE`.
- **Upgrading.** The 0.15.2 and 0.16.2 hook copies are in `released_sha256`, so the route is the in-place one:
  re-run `/auto-improve-codegraph-install` (it backs up an unedited older copy as `<hook>.bak-<UTC stamp>` and replaces
  it), then start a new session.

| Install age | What it has | Route |
|---|---|---|
| 0.15.2 or 0.16.0 to 0.16.2, hook files unedited | session folders in the system temp folder, the older hooks | re-run the install, new session; the old temp folders are ignored |
| an upgraded project that keeps its 0.15.2 `_project_paths.py` | a helper with `_hop_allowed` and `worktree_own_root`, no `TREE_HOP_REFUSAL` | nothing to do: it passes the Hop proof, so `index-other-tree` keeps firing |
| installed from this release | nothing to do | run `addon --name codegraph --check` |

**Changed in 0.15.2 (the `codegraph` guard fails open, issue #259):** the guard lets reads through when CodeGraph is provably unavailable.

- **It lets reads through when CodeGraph is provably unavailable**, and prints one
  `[codegraph-first-guard] allowed (fail-open:<reason>)` line, logged once per session per reason in
  `errors.jsonl`. While the session folder cannot be used, these lines print on every call and nothing is logged. The reasons: `no-index` (no `.codegraph/codegraph.db` in the project, its parents or
  the main checkout; a `.codegraph` folder without `codegraph.db` is not an index), `index-other-tree`
  (a linked worktree with no index of its own, whose only index belongs to the main checkout),
  `server-not-configured`, `server-disabled` and `subagent` (the payload carries an `agent_id`).
  Since 0.16.3 an unusable session folder blocks instead (`session-state-unusable`); see below.
- **The retry escape replaces the shell advice.** The block message no longer teaches reading through
  the shell. Repeat the identical blocked call once and it is allowed and logged as `retry-escape`;
  the next prompt clears it. Not after a `session-state-unusable` block, which offers no retry. After a `retry-ticket-unwritten` block the retry was not recorded, so the repeat is blocked once more (as `source-target` or `ambiguous-target`) and the identical call after it is allowed. No environment variable is involved.
- **The turn marker belongs to the session.** It is `turn.json` in
  `<Per-user session parent>/auto-improve-codegraph-<session id>/` (the parent is `%LOCALAPPDATA%\auto-improve-codegraph\`
  on Windows, `$XDG_CACHE_HOME/auto-improve-codegraph/` or `~/.cache/auto-improve-codegraph/` on POSIX; 0.15.2 used
  the system temp folder), no longer
  `<cwd>/.claude/.codegraph-used-this-turn`, so `cd` or `EnterWorktree` does not close the gate. The reset
  hook prunes old session folders in that parent once per session (never through a link, never a
  folder holding a file it does not know, only after 7 days).
- **Wildcard only.** No shipped file names an individual CodeGraph tool; the server now offers only
  its explore tool. `addon.json` gains `permissions_allow` (`mcp__codegraph__*`, written to
  `permissions.allow` by the install, kept on uninstall) and `released_sha256` (so the uninstall deletes an
  unedited old hook copy). `auto_improve_finish_install.py addon --name codegraph --check` is a read-only
  check: exit 0 clean, 1 with findings (`codegraph-wildcard-missing`, `codegraph-tool-named`), 2 when it could not
  check (any refusal: a settings layer or the project cannot be read, the add-on manifest is missing or unusable). The install refuses with `codegraph-tool-named` when a layer names a
  single tool. `/verify-before-done` runs the check when the guard is registered.
- **Upgrading.** The rows an old install carries are the same three, but the old hook files differ from the new
  ones, so the install refuses with `addon-file-differs`. By install age:

| Install age | What it has | Route |
|---|---|---|
| 0.9.9 to 0.15.1, hook files unedited | the old hooks, the sentinel under `<cwd>/.claude/` | `/auto-improve-codegraph-uninstall` (deletes the unedited old copies through the released hashes), then `/auto-improve-codegraph-install`, then a new session |
| a copy from before 0.9.9, when the guard was a core hook | the guard file under `.claude/hooks/` that no add-on put there | the uninstall keeps it (`kept-differs`) unless it matches a released hash; compare it with the plugin's copy, delete it by hand, then install |
| any age, a hook file edited by your team | your edited copy | the uninstall keeps it (`kept-differs`); compare it with the plugin's copy, move your edits over, delete it, then install |
| installed from this release | nothing to do | run `addon --name codegraph --check` to confirm the permission entry |

The `test_auto_improve_finish_install.py` suite grows to 394 cases.

**Changed in 0.14.5 (the settings writer refuses without the Project hook launcher):** four changes.

- **The writer refuses instead of falling back.** When the hooks folder beside the scripts has no
  usable `_project_paths.py` with the launcher, the vendored hooks install and every add-on install
  that writes a row refuse with `project-hook-launcher-missing` (exit 3), in the preview and in the
  apply, before `settings.json` is read for writing. Nothing is written and no backup is made. The
  earlier-form fallback and its preview note are gone. Bring the project's hooks folder to the same
  release as the scripts, then run the install again.
- **`_claude_paths` raises `ImportError` for a hooks folder from before the launcher.** The message
  names that `_project_paths.py` and each missing name, so the callers that guard the import
  (`plugin_doctor.py`, `pr_merged.py`) degrade instead of failing with `AttributeError`.
- **The `_launcher_api()` docstring is true.** A failed import is retried on every call, a successful
  one stays loaded for the life of the process, and `None` makes the install refuse.
- **`plugin_doctor.py --drift` reads launcher rows.** A launcher row whose script is in none of the
  launcher's folders is a `dangling-hook-row`, like an old-form row. No new finding kind.

The manifests read 0.14.5.

**Changed in 0.14.4 (tests only):** 14 older test cases are repaired ahead of the launcher writer
refusal. Two fixtures change with no rule change: the doctor suite's launcher-row helper now writes
each row's script, and the installer suite's vendored consumer copies the real `_project_paths.py`.
One rule changes: a launcher row whose script is deleted now gives exactly one dangling-hook-row
finding (its four script-deleted subtests are red until the writer refusal merges). No shipped
behaviour changed. The manifests read 0.14.4.

**Changed in 0.14.1 (tests only):** the installer suite's insertion-point rule is narrower: a changed
line passes only when one inserted run is a bare comma or holds a whole added row, so a script name
already on a line no longer vouches for a whitespace re-layout of it. New rows (red until the next
release) pin that the settings writer refuses without the Project hook launcher, that `_claude_paths`
raises `ImportError` for a hooks folder from an older release, and that the dangling-row reader reads
launcher rows. No shipped behaviour changed. The manifests read 0.14.1.

**Changed in 0.14.0 (issue #178):** `/pr-merged` no longer leaves its completion records behind as
untracked files in the tree it ran from. After the records are pushed to the stable branch
`docs/<contract-slug>-records`, the new `pr_merged.py --sweep-records` deletes each starting-tree
copy that is identical to a copy on `origin/<default>` (or on that branch's tip while its pull
request is open), and keeps and names every other copy. The records step is
`/pr-merged --records <contract-slug>`; every records push to the stable branch now runs without a
prompt, and a closed or merged records pull request is re-opened as a draft from the same branch.
`--status --json` gains `records_reading`, `records_unpushed`, `records_differing`,
`records_stranded` and `records_untracked`; the Next Command puts the records step first, and
`--dispatch` refuses with exit 12 while records are unpushed or cannot be read, so `/advance` never
dispatches on top of them. Both skills end with one `tree <root>: clean` line per tree touched.
**A project that vendors `pr_merged.py` must sync it (`tools/sync-plugin.cmd`)**, or the skills halt
with "this `pr_merged.py` predates 0.14.0". The manifests read 0.14.0.

**Changed in 0.12.5 (tests only):** the installer, guard-deference and launcher test files now pin the
Project hook launcher row form (`py -3 -c <source> <class> <script>`) that 0.12.3 started writing, and
one new pair of rows pins the earlier-form fallback when no launcher is available. No shipped behaviour
changed. The manifests read 0.12.5.

**Changed in 0.12.4 (issue #71, follow-up 1):** `plugin_doctor.py --drift` warns about a project
hook row that launches a file that is not there, such as a row for a hook the plugin no longer
ships. The finding kind is `dangling-hook-row`. It covers rows written before 0.12.3 (the old
exec-form rows) and hand-written rows that plainly launch a Python script; Project hook launcher
rows (what the installer writes since 0.12.3) are skipped, because the launcher falls back on its
own when a project file is missing. It is read-only, needs no plugin, and is still
listed when the comparison exits `4`. The manifests read 0.12.4.

**Changed in 0.12.0 (follow-ups to the `angular-tailwind` rule documents, issue #86):** this
release closes the items the 0.10.0 work left open. The manifests read 0.12.0. It has eight
parts.

- **Guard fixes.** `architecture-guard.py` is the default hook that checks Angular and Tailwind
  edits before they are written. It now judges the whole file once per call, using the **post-edit
  view**: the text the file will hold after the Write, Edit or MultiEdit. Before, a rule that
  needs the whole file (the height chain, and the inline `template:` and `styles:` checks) saw
  only the edited fragment. Other fixes:
  - a template reference variable such as `<input #add>` is no longer read as the colour `#add`;
  - the guard finds `.app-rules.json` under whatever folder holds the apps, not only `projects`;
  - the guard recognises Angular 20 file names: a `.html`, `.scss`, `.css` or `.ts` file counts as
    a component file when its `.ts` sibling holds `@Component(`;
  - no code path in the guard builds a path into your home folder;
  - the `promote-ui-rule` skill runs the guard through a lookup block, and the "Enforced by"
    lines of the rule documents that these fixes made false are corrected.
- **Known limits.** Some gaps are accepted, listed in a "Known limits" block in the guard's
  docstring, and each is pinned by a test. Two edits that together form `text-gray-500` pass,
  because each edit is judged on its own new text. An edit that completes a violation already on
  disk passes. Stylesheet rules only warn. `relative` and `absolute` are never checked. A
  3- or 6-character token with no digit, such as `  #fff` alone after whitespace, is read as a
  template reference variable. A file with no recognised name is scanned only when its `.ts`
  sibling already holds `@Component(`.
- **Removed switches.** No add-on has a kill switch now. `CLAUDE_SKIP_CG` (codegraph) and
  `CLAUDE_BASH_GATE` (strict-shell-gate) are no longer read, and neither shipped `addon.json`
  declares `kill_switches`. The install plan still lists `kill-switches`, as an empty list.
  **`CLAUDE_CONCEPT_GATE=off` no longer turns off the strict-shell-gate add-on.** It still turns
  off the concept gate and the Changed-file check, which are default hooks.
- **Ways out (the K-4 routes).** The uninstall skill is the normal way out of an add-on. When a
  hook cannot run, remove its row from `.claude/settings.json` by hand. The table under "Ways out
  when a hook cannot run" gives the route for each hook. The codegraph block message is now plain
  text that names `/auto-improve-codegraph-uninstall`. The uninstall skills no longer say "never
  edit `settings.json` by hand"; they say the skill never does, and that you do only when a hook
  cannot run.
- **Three lines of your global `~/.claude/CLAUDE.md` that only you can change.** The plugin
  never edits that file. Three lines are now false or only partly true:
  - the CodeGraph bypass "set `CLAUDE_SKIP_CG=1`", which does nothing now;
  - "Disable the gate entirely: `CLAUDE_CONCEPT_GATE=off`", which no longer covers the shell gate;
  - the claim that the gate "auto-bypasses until the index exists", which was untrue of 0.12.x.
    Since 0.15.2 it is true: with no index (`.codegraph/codegraph.db`) the guard lets reads
    through. See "Changed in 0.15.2".
- **Doctor.** `plugin_doctor.py --drift` reports a new kind of finding,
  `disabled-hook-installed`. A **disabled hook** is one an add-on still ships but no longer
  installs (the advisor is one). The doctor reports its file in `.claude/hooks/`, and its row in
  `.claude/settings.json` or `.claude/settings.local.json`, under the current name or a former
  name. It also compares add-on **documents** in pairs: the project copy under
  `.claude/references/<add-on>/` against the plugin's copy under
  `.claude/addons/<add-on>/documents/`. A pair is `content-differs` or `one-sided`. `--drift`
  never writes. The doctor does not read the user-level settings layer, so a disabled hook row
  there is refused by the install but not reported by the doctor.
- **Removed preload.** `python-ai-developer` no longer preloads a skill that was never shipped.
  A new test checks that every skill named in an agent's `skills:` list exists under `skills/`.
- **Patterns.** `UI-UX-PATTERNS.md` ships one new plugin pattern, **P-002, Table column
  alignment**: numeric columns and their headers right-aligned, text columns left-aligned. It is
  not enforced by the guard. Three candidates were rejected and are listed under "Patterns this
  plugin does not ship": the status badge and the card surface (product data and product look),
  and the constrained panel (a project class name; `T-014` already bounds height).
  The advisor's `DISABLED.md` now names both defects to fix before turning it back on: the dead
  `ui` keyword, and a fallback that reads the home folder.
- **Rules route trial.** `.claude/references/claude-rules-route-trial.md` records a live try of
  a `.claude/rules/` file with a `paths:` filter, on Claude Code 2.1.316. It did not load at
  session start. It loaded once the session opened a matching file, and again inside a subagent
  that opened one. So it gives no guidance before a matching file is read. The trial was three
  headless runs only.
- **Registry promotions.** `VOCABULARY.md` gains Add-on, Add-on manifest, Add-on document,
  Disabled add-on hook, Rule ID, Post-edit view and Accepted guard limit, plus amendments to
  Placeholder slot and Vendored-asset drift. `MECHANISMS.md` gains Disabled add-on hook and an
  amendment to CodeGraph that replaces its bypass clause. Existing entries are not edited.

**Hook registration checks (issue #148).** A hook registration is one handler row under
`hooks` in a project's `.claude/settings.json`. The tests that guard those rows used to live in
one consuming project, so a registration change on the default branch broke an unrelated
contract's landing. The plugin now owns the checks. What it adds:

- **The check.** `.claude/scripts/check_hook_registrations.py` is read-only. It judges the
  settings file against the project's **hook registration profile**, a committed record of the
  rows the project expects (`.claude/hook-registration-profile.json`). It applies five named
  rules: the row count is unchanged; rows are unchanged apart from `if`; the `if` values are
  unchanged; every row is recorded or deliberately excluded; every exclusion still matches a row.
  It exits 0 on a pass, 1 when a rule fails, and 2 when it could not check. Exit 2 is never a
  pass: a missing, unreadable or unimportable input is refused by name.
- **The recorder.** `auto_improve_finish_install.py record-registrations` previews the hook
  registration profile, then writes it with `--apply --expect-sha256 <plan hash>`. It keeps every
  exclusion you wrote by hand. An unchanged re-record writes nothing.
- **Failure attribution in the landing report.** When verification stops a landing, the report
  now says for each new failure whether it comes from the contract's diff (`in-diff`), from the
  default branch's diff (`outside-diff`), or cannot be told (`undetermined`), with a one-line
  reason. Only a file the failure itself names can decide a side. This is advice only: it never
  changes the verdict, a gate or an exit code.
- **What the advice says (the answer to the question of where "check the default branch before
  re-recording" belongs).** It sits in the landing report's `next_command`, not in the checker.
  The re-record advice appears only when every new failure is an `outside-diff` named test
  regression, because only a named regression can change after a baseline re-record. A step that
  is read by its exit code is not covered by the baseline. For those steps the report tells you to
  check whether the default branch fails the same step, and it never suggests a re-record.
- **This repository's own step.** The `hook-registration-tests` landing step runs the checker's
  test suite and names only that test file. A break in `check_hook_registrations.py` itself
  therefore reads `undetermined` here, with the reason "no file the failure names is in either
  diff", because the suite reaches the checker by import and not as a step argument.
- **Registries.** `VOCABULARY.md` gains Registration row, Hook registration profile,
  Registration rule and Failure attribution. `MECHANISMS.md` gains Hook registration check and a
  correction line under Preview-hash apply. Existing entries are not edited.

**Domain-split registries (issue #235).** A client split its registries into per-domain files, the
plugin's tools never learned the split, writers kept appending to the flat files, and nothing
noticed that the copies had diverged. The registries now have a numbered **registry layout**.
Layout 1 is the flat form. Layout 2 is the split form: `MECHANISMS.md`, `VOCABULARY.md` and
`JOURNAL.md` hold only the Universal tier and a fixed `## Project tier` pointer, they are marked
`<!-- registry-layout: 2 -->` on line 1, and project content lives in domain files such as
`.claude/registries/MECHANISMS/general.md`. `general.md` always exists, and every `.md` file in a
registry's folder is read. What it adds:

- **One reader.** `.claude/scripts/_registry_layout.py` owns the marker, the entry grammars, the
  entry keys and the layout state (`current`, `pending`, `stale-sync`, `unknown`, `absent`). The
  digest generator, the tracker hook and the other registry readers go through it and through
  `registry_files()` in `_project_paths.py`, so a domain file is never missed.
- **One write path.** `.claude/scripts/registry_append.py` appends an entry, a `Correction` line
  or an `archived-title-only` mark. On layout 2 a project entry goes to a domain file and never
  into a root. On layout 1 the writer keeps working: a project entry goes to a domain file
  (`general.md` is created when missing), never into a root, and the writer prints an advisory
  telling you to run the migration.
- **A structure lint.** `validate_registries.py --check-structure [--strict]` applies rules R1 to
  R6 and the advisory A1. Exit 1 is a finding; exit 0 with advisory lines is not. The digest
  generator exits 1 on R1 and R2.
- **A migration.** `.claude/scripts/registry_migrate.py` runs migration 0001 from layout 1 (or a
  stale sync) to layout 2. It previews first, applies only against the previewed hash, and loses
  and invents nothing. `--check` prints the layout state and is the gate a sync tool calls: exit
  0 for `current` or `absent`, 6 for `pending` or `stale-sync`, 2 for `unknown`.
- **Moved helpers.** `_plan_digest` and `_atomic_write` moved from
  `auto_improve_finish_install.py` into `.claude/scripts/_preview_apply.py`, which also gains
  `stage_and_replace`. The guarded plugin-root lookup moved into `.claude/scripts/_plugin_root.py`.
  `auto_improve_finish_install.py` now imports `_preview_apply.py` and `_plugin_root.py`.

**If you copy the scripts into your project, copy these new files with the updated scripts.** A
copy of `auto_improve_finish_install.py` or `registry_migrate.py` without them fails on import.

- `.claude/scripts/_registry_layout.py`
- `.claude/scripts/_preview_apply.py`
- `.claude/scripts/_plugin_root.py`
- `.claude/scripts/registry_append.py`
- `.claude/scripts/registry_migrate.py`
- `.claude/scripts/registry_migrations/` (the whole folder)
- `.claude/references/registry-layout.md`
- `.claude/templates/registries/` (the three `general.md` skeletons, one per registry folder)

To move a project onto layout 2, follow "Moving a project onto registry layout 2" below. This
repository's own registries are on layout 2, and the registry entries for the new terms and
mechanisms were appended with `registry_append.py --universal`. Existing entries are not edited.

### Project hook launcher

Since 0.12.3, a hook row that this plugin writes into a project's `settings.json` (the vendored
hooks step and every add-on install) does not name the hook file directly. It runs a short
program that finds the hook file and runs it:

```json
{ "type": "command", "command": "py", "args": ["-3", "-c", "<launcher program>", "<class>", "<hook file>"] }
```

Off Windows the command is `python3` and the `"-3"` is left out. Any extra argument the hook takes
comes after the hook file. The program is the launcher, and it is the only copy of that text:
`PROJECT_HOOK_LAUNCHER_SOURCE` in `.claude/hooks/_project_paths.py`. The row writer writes it, and the
database guards' stand-down check compares to it. The plugin registers no launcher file, and its
`hooks.json` is unchanged.

**What it fixes.** Claude Code fixes the value of `CLAUDE_PROJECT_DIR` when a session starts. If a
session moves into a worktree and the folder it started in is then removed, a row that names
`${CLAUDE_PROJECT_DIR}/.claude/hooks/<file>.py` points at nothing. Python exits with code 2 for a
missing script, and on `UserPromptSubmit` that blocks every prompt, so the session cannot recover.

**Why the program sits inside the row.** The obvious design is a launcher file in the plugin that
every row names. It does not work. The plugin's cache folder changes with each version and differs
on each machine, so a committed row cannot name it. `${CLAUDE_PLUGIN_ROOT}` does not expand in a
project's `settings.json`: with the plugin installed and Claude Code 2.1.302, a project row that
used it did not run. And a committed row that names a file a teammate does not have wedges that
teammate, because a missing script exits with code 2. A program carried in the row needs nothing on
disk to start, so it works in a vendored project and for a teammate without the plugin.

**What the launcher does.**

1. It looks for `<CLAUDE_PROJECT_DIR>/.claude/hooks/<file>` and runs that.
2. If that file is gone, it falls back to the main checkout. It takes the text of `CLAUDE_PROJECT_DIR`,
   removes every `.claude/worktrees/<name>` part, and looks in `.claude/hooks/` of what is left.
3. It runs the hook in the same Python process. The hook sees the same arguments, standard input,
   working folder and environment, and its exit code, output and error text pass through unchanged.
   The launcher never reads standard input, never changes the working folder, never sets a variable,
   and prints nothing when it succeeds.
4. If the file is found in neither place, it prints one message on standard error. The message names
   the class, the file and every path it tried, and tells you to restart Claude Code from an
   existing checkout. It then exits by the row's class.

**The two classes.** A row has the class `block` or `warn`, and nothing else is accepted.

| Class | Written for | File missing everywhere | Why |
|---|---|---|---|
| `block` | every `PreToolUse` row | exit 2, the tool call is stopped | a guard that cannot be found must not let the call through |
| `warn` | every other event | exit 1, the message shows, nothing is blocked | exit 2 outside `PreToolUse` is the wedge described above |

A class that is neither makes the launcher print a message, run nothing and exit 1. A hook file
name that is not a bare `.py` name (a folder separator, a drive colon, no `.py`) is refused by the
class's exit code. An error inside the hook itself is not the launcher's: an uncaught exception
exits 1, as it does when the file is run directly, except that its traceback also shows a `<string>`
frame and a `runpy` frame.

**When the plugin's own guards step down.** If your project registers its own copy of
`db-destructive-guard.py` or `db-research-readonly-guard.py`, the plugin's copy and yours both run,
unless your row proves it runs your copy. A launcher row counts as that proof only when all
three hold: its program is byte-equal to the installed plugin's own text, its class is exactly
`block`, and its file is a bare `.py` name equal to the guard's file. Anything else (an older text,
a hand-written row, a `warn` row) fails the check and both copies run. The direction of every
failure is that a guard runs twice, never that none runs. The first line of the program carries a
version (`v1`). A release that changes the text raises it, and until a project's rows are rewritten
the two guards both run. The writer never rewrites a row you already have; `plugin_doctor.py --drift`
reads a launcher row as the file it launches, so it still reports a hook registered on both sides.
If the scripts are run from a copy whose `_project_paths.py` has no launcher (a stub, or a vendored
copy from before 0.12.3), the vendored hooks install and every add-on install that writes a row
refuse, in the preview and in the apply, with `project-hook-launcher-missing` (exit 3). That is so
whatever the plan would add, because without the launcher the writer cannot read a launcher row
you already have. The message names `<project>/.claude/hooks/_project_paths.py`; bring the hooks
folder to the same release as the scripts and run the install again. The settings file and its
folder stay as they were, and no backup is written. Since 0.14.5 the writer no longer falls back to
the earlier form that names `${CLAUDE_PROJECT_DIR}/.claude/hooks/<file>`. It still reads such a row
you wrote by hand or an older release wrote, and it still never removes or rewrites a row.

**Limits.** These are known and accepted.

- **R1, the fallback runs the main checkout's copy.** That copy may be older or newer than the
  branch the session works on. The session keeps working, but not with its own branch's hooks.
- **R2, hooks may decide differently during a fallback.** `CLAUDE_PROJECT_DIR` still names the
  removed folder, so a hook that writes a log or state file under it writes nothing there. The
  plugin's database guards also act beside your copies, and each reads its rules from its own place,
  so the stricter answer wins: more blocks, never fewer. `codegraph-first-guard.py` may block source
  reads. The cure is the message's advice: restart Claude Code from an existing checkout.
- **R3, no fallback outside a worktree folder.** If the session's folder was not under
  `<main>/.claude/worktrees/`, there is nothing to fall back to, and the class rule applies.
- **R4, a missing `codegraph-first-guard.py` only warns on its prompt row.** The prompt row is a `warn`
  launcher row, so a missing file prints the message and lets the prompt through. The `PreToolUse` row blocks.
- **R5, a syntax error in the launcher text** would make every launcher row exit 1, because Python
  cannot catch it. The tests compile the text and compare the rows to it byte for byte.
- **R6, a database guard missing in both places** blocks through the launcher with exit 2 on
  `PreToolUse`. The plugin's own copy also acts.

The launcher text is long, and when a `block` row blocks, Claude Code prints the whole command in
its message. That is a cost of carrying the program inside the row.

### Local development workflow

To change the plugin and try the change in a real project before it is released:

1. Make a plugin worktree from fresh `origin/master` and edit there.
2. Run the plugin's suites in that worktree, for example
   `py -3 .claude/scripts/tests/test_plugin_manifests.py`. The plugin can be tested alone.
3. From the consuming project, run `claude --plugin-dir <that worktree>`. It replaces the
   installed copy of the same name for that one session, running from the folder itself with no
   cache copy. After an edit, run `/reload-plugins`. `CLAUDE_CODE_PLUGIN_DIRS` does the same from
   the shell. Project and local settings cannot set it.
4. Bump all five version declarations, merge, then run the marketplace update and the plugin
   update under "Updating an installed plugin", start a new session, and confirm the new
   version's folder in the plugin cache.

To switch the installed plugin off for a session while you compare, set
`"agentic-auto-improve@auto-improve": false` under `enabledPlugins` in the project's
`.claude/settings.local.json`, and put the value back afterwards.

### Restoring an earlier version

- **Revert the release.** Revert its pull request with a version number above the bad one, then
  run the two update commands above. The version has to go up, or an installed copy never
  refreshes.
- **For one session.** Check out the previous tag in a worktree and run `claude --plugin-dir`
  on it.
- **Reinstall.** Install the previous version again from the marketplace.

### Running a hook through an HTTP host (optional)

Every hook this plugin ships is a **command hook**: Claude Code starts a Python process for
each event, reads its exit code and goes on. Nothing here uses `type: "http"` and the plugin
does not install a host, so out of the box there is nothing to switch on. An HTTP hook is
something you add yourself, in your own settings, when starting Python on every tool call is
too slow for a hook you are willing to see fail open.

**Fail open is the rule that decides what may use it.** An HTTP hook blocks only when the
host answers with a 2xx status and a JSON body that says to block. A connection that cannot
be made, a non-2xx status and a timeout are all treated as non-blocking errors, so the tool
call goes ahead. A host that is down therefore removes the gate it was running. For that
reason the gates in the list above (`concept-gate`, `architecture-guard` and both database
guards) stay command hooks. Put only advisory hooks behind a host, such as the post-edit
dispatcher or the memory pager. For a hard allow or
deny, use a `permissions.deny` rule, which Claude Code enforces without any process.

**How to turn one on.**

1. Write a small local HTTP host that accepts `POST`, reads the event JSON from the request
   body, and replies `200` with a JSON body. An empty object `{}` means "no objection". To
   block a `PreToolUse` call, return the same decision shape a command hook prints, with
   `hookSpecificOutput.permissionDecision` set to `deny` and a `permissionDecisionReason`.
   Bind it to `127.0.0.1` only, on a fixed port such as `8765`, and answer fast, because
   Claude Code waits for it.
2. Register it in your own `.claude/settings.json` (or `settings.local.json`), not in the
   plugin:

   ```json
   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Edit|Write|MultiEdit",
           "hooks": [
             { "type": "http", "url": "http://127.0.0.1:8765/pre-tool-use", "timeout": 5 }
           ]
         }
       ]
     }
   }
   ```

3. Start the host before the session. Edits to a settings file are picked up while a session
   runs, but the host is your own process, so Claude Code does not start or restart it.
4. Check it from a request, not from the config: make one tool call that should reach the
   host and look at the host's own log. A silent miss looks exactly like success, because
   failing open is quiet.

Hooks from every settings file, and from the plugin, are merged and all of them run. If you
move a plugin hook behind a host, also turn the plugin's copy off with its kill switch from
the table above, or the event is handled twice. To get out of a hook that blocks everything,
start Claude Code with `claude --settings '{"disableAllHooks": true}'`.

### What each provider actually gets

Support is tiered, because the three mechanisms do not carry the same component types.
This table is the honest version — an install that silently loads nothing is the failure
this repository has already been bitten by once, so the gaps are stated rather than implied.

| Component | Claude Code | Cursor | OpenAI Codex |
|---|---|---|---|
| 34 skills | yes | yes | yes |
| 15 agents | yes | yes | no — not a component of the portable Agent Plugins standard |
| 14 hooks | yes | no | no |
| 7 working agreements, delivered by a hook | yes | no | no |
| scripts, templates, references, registries | yes, in the plugin's own tree | yes | yes |

**Corrected 2026-09-13.** This row used to read `vendoring only`, and that was wrong. An
install copies the whole repository into the provider's cache, script files included — the
`superpowers` plugin ships Python the same way and its files sit in that cache today.

What was actually missing was a way for a skill to *find* them. A skill citing
`.claude/scripts/<name>.py` is naming a path inside **your** repository, which exists when you
vendor and does not when you install.

Skills that call a script now resolve it first, in one fixed order: the vendored path, then
`$CLAUDE_PLUGIN_ROOT`, then the install that `installed_plugins.json` records (the entry for
this project first, then the user entry), then the newest cache folder, compared as numbers so
`0.10.0` beats `0.9.0`. Every skill that needs a script carries the same shell snippet for
this, and `test_skill_script_lookup.py` runs each copy against a table of cases. A skill added
later should copy the snippet rather than assume a vendored layout. The same order is
available to Python as `installed_plugin_root()` in `.claude/hooks/_project_paths.py`, which
`.claude/scripts/_claude_paths.py` re-exports.

The templates are copied into your repository by the doctor (`plugin_doctor.py --fix`, which
`/auto-improve-finish-install` offers to run), because a concept contract is a
file **in** your repository rather than one read from the plugin.

Cursor and OpenAI both read the **Agent Plugins** open standard
(`https://agent-plugins.org`), which is why one root `plugin.json` serves both. Claude Code
uses its own format at `.claude-plugin/plugin.json`. Hooks are Claude-only in this release:
Claude's event names, its `${CLAUDE_PLUGIN_ROOT}` substitution and its blocking-exit-code
contract have no tested equivalent in the other two runtimes, and shipping an untested
translation would be worse than shipping none.

### Known limitations

- **The hook entries launch `py -3`**, the Windows Python launcher, matching the
  invocation every hook docstring in this repository already specifies. On macOS and Linux a
  plugin install cannot start any hook, and an edit to the cached `hooks.json` is lost at the next
  update, so do not make one. Copy the hooks into the project instead (see
  [Quick start in a new project (vendoring)](#quick-start-in-a-new-project-vendoring)), where
  `/auto-improve-finish-install` registers them with `python3`, or wait for a per-platform hooks
  format. The format has no per-platform branch, so this is documented rather than solved.
- **Plugin install and vendoring are not reconciled.** Under an install the assets live in
  the provider's cache, so a skill or hook that resolves a path such as
  `.claude/scripts/cross_area_scan.py` inside *your* repository will not find it there.
  `_project_paths.py` searches `CLAUDE_PROJECT_DIR`, then its own location, then the current
  directory, then `~/.claude`, which mostly absorbs this — but it is not yet proven for
  every skill. Vendoring remains the path with no such gap.
- **The four per-project configuration files cannot be delivered by an install.**
  `project-profile.md`, `area-mapping.json`, `work-item-conventions.json` and
  `.project-tokens.json` describe *your* repository, so an install cannot ship them. The
  doctor (`plugin_doctor.py --fix`) scaffolds them in your own `.claude/`, and
  `/auto-improve-finish-install` proposes their content for you to confirm, even when the
  rest arrives as a plugin.
- **Not listed in any public directory yet.** Installation is direct from this git
  repository. Cursor's marketplace and OpenAI's plugin directory both require a submission
  and review that is tracked separately.

## What is included

```
plugin.json                  Agent Plugins manifest -- Cursor and OpenAI Codex
.claude-plugin/
  plugin.json                Claude Code manifest
  marketplace.json           Claude Code marketplace (this repository hosts itself)
.cursor-plugin/
  plugin.json                Cursor-specific manifest (adds agents)
.agents/plugins/
  marketplace.json           OpenAI Codex marketplace
skills/          34 generic skills          (plugin root -- all three providers)
agents/          15 generic agents          (plugin root -- Claude and Cursor)
.claude/
  agreements/    7 shipped working agreements, delivered at session start
  addons/        3 opt-in add-ons (addon.json + hook files), never registered by hooks.json
  hooks/         14 generic hooks, a gate launcher, 8 shared helper modules, 5 generic data files
    hooks.json   Claude hook registration, referenced by .claude-plugin/plugin.json
    tests/       hook test suites
  scripts/       workflow scripts and shared helper modules
    tests/       suites, including the path-resolution suite
  templates/     6 document templates
  references/    4 reference documents
  registries/    MECHANISMS.md, VOCABULARY.md, JOURNAL.md (Universal tier only)
  area-mapping.json          TEMPLATE - schema intact, empty content set
  work-item-conventions.json TEMPLATE - schema intact, empty content set
  project-profile.md         TEMPLATE - blank slot table
  .project-tokens.json       TEMPLATE - empty token array (the doctor scaffolds a copy in a project)
README.md
CONTRIBUTING.md
LICENSE
```

**`skills/` and `agents/` sit at the repository root, not under `.claude/`.** That is what
makes them discoverable by all three providers without a redirect, and it is required
rather than stylistic: the portable Agent Plugins manifest that Cursor and OpenAI read has
no component-path fields at all, so a skill anywhere but the plugin root is invisible to
Codex. Every other tree stays under `.claude/`, and `hooks/` in particular **must** —
`_project_paths.py` resolves its search root as the directory two levels above a hook file,
so a hook moved to the repository root would resolve every registry, area-map and contract
lookup against the wrong directory and miss silently.

At runtime the loop also writes two stores under `.claude/orchestrator/`: `results/`
holds one completion record per finished sub-task and is the durable evidence, while
`state/` holds the working position and can be rebuilt from the records. Commit the
first; ignore the second.

### Agents

data-architect, contract-critic, fullstack-code-reviewer, senior-test-engineer,
test-strategy-critic, migration-safety-reviewer, security-auditor,
sql-performance-reviewer, api-contract-reviewer, ui-ux-designer,
dotnet-backend-architect, angular-senior-dev, python-ai-developer, registry-scout,
cloud-engineer.

### Skills

flow, task, design-first, tdd-first, advance, pr-merged, verify-before-done,
git-commit, ship, debug, north-star, north-star-review, list-contracts,
contract-accuracy, critique-now, cross-impact, journal-add, plan-questions,
validate-registries, promote-ui-rule, sql-server-patterns, auto-improve-finish-install,
auto-improve-database-guard-install, auto-improve-angular-tailwind-install, auto-improve-angular-tailwind-uninstall,
auto-improve-codegraph-install, auto-improve-codegraph-uninstall,
auto-improve-strict-shell-gate-install, auto-improve-strict-shell-gate-uninstall,
angular-ui-rules, unit-testing, application-design, website-design, cloud-engineering.

A skill or agent that mentions a skill owned by another plugin follows the rule in
[CONTRIBUTING.md](CONTRIBUTING.md) → "Referencing another plugin's skill".

`auto-improve-finish-install` is not a stage of the chain below. It is a one-time setup
skill, run once per project after the plugin is installed (see
[Complete the installation in your project](#complete-the-installation-in-your-project)). Its name carries the plugin's name
because you may have several plugins installed. The three `auto-improve-*-install` add-on skills
after it are not stages either: each installs one opt-in add-on, and its paired
`auto-improve-*-uninstall` skill removes it (see [Managing optional add-ons and retired hooks](#managing-optional-add-ons-and-retired-hooks)).
`auto-improve-database-guard-install` is a one-time setup skill too: it appends your project's own
database names to the database guard's rules file (`protected_databases`), never removes one, and
prints the server-trigger line for a person to run.
`angular-ui-rules` is a rule skill, not a stage: the Angular agents preload it.

The rest form one chain, and each stage hands the next a written artefact rather than a memory
of the conversation:

```
/flow   the front door. Runs everything below, pausing only where you must decide.
  |
  +-- /task               Work Item Brief    .claude/work-items/
  +-- /design-first       concept contract   .claude/concepts/   (you approve it)
  +-- /tdd-first          failing tests first
  +-- reviewers           adversarial critique
  +-- /verify-before-done build, tests, drift    (blocks the word "done")
  +-- /git-commit         the commits
  +-- /ship               pull request, and a closing link GitHub actually resolved
```

When a contract declares more than one sub-task, the middle of that chain iterates
instead of running straight through. Each sub-task ends in a pull request somebody
has to merge, so it moves one step at a time:

```
/advance      start what is ready, open a pull request, stop
(you merge)   the only step in the whole chain a machine cannot take
/pr-merged    confirm with GitHub, record it, say what that released
              -> /advance again
```

Neither half loops. A person merging is what joins them.

### Hooks

concept-gate, architecture-guard, db-destructive-guard,
db-research-readonly-guard, memory-pager, working-agreements, post-edit-dispatcher, and the
four checks the dispatcher runs: integration-check, critic-verdict-tracker,
contract-status-watcher, journal-post-approval-tracker. Since 0.9.8 also plan-question-advisor
and stop-dispatcher. Since 0.18.4 also protected-names-warning. That is fourteen hook files. The
Changed-file check the Stop dispatcher runs
is not a hook file: it is the script
`.claude/scripts/concept_changed_check.py`. Beside the hook files
sit the gate launcher `gate-launch.py` and the shared helpers `_error_log.py`, `_gate_launch.py`,
`_memory_common.py`, `_project_paths.py`, `_main_checkout_guard.py`, `_shell_write_targets.py`
(the shell parser the guard reads write targets with), `_protected_names.py` (the Protected-name
check's logic) and
`_inprocess_hook.py` (the dispatchers' in-process runner), and the generic data files
`architecture-guard.rules.json`, `architecture-guard.exceptions.json`,
`integration-check.rules.json`,
`db-destructive-guard.rules.json` and `working-agreements.rules.json`.

All fourteen hook files are accounted for in `.claude/hooks/hooks.json`, which the Claude
manifest references: nine are registered there directly (`concept-gate.py` through the gate
launcher), four are named in the post-edit dispatcher's constant list and one
(`protected-names-warning.py`) in the Stop dispatcher's list, which also names the Changed-file
check script.
That makes thirteen registrations: the nine files registered directly make nine entries, plus
two more for `db-destructive-guard.py` (three matchers in all), one more for
`db-research-readonly-guard.py` (two matchers) and one more for the gate launcher (two matchers),
while the four post-edit checks share one dispatcher row. The file plus those lists are the single registration point:
adding a hook without adding it to one of them ships a file nothing runs, and a test
(INV-8 in `test_plugin_manifests.py`) fails on it.

**A hook keeps its per-project settings in a `<hook-name>.rules.json` file beside it**, so the
hook body names no project. Those files ship as templates carrying deliberately fictional
placeholder values. They are not safe defaults, and a guard is only as correct as the file you
replace them with. A hook running from the plugin reads your project's copy in
`<project>/.claude/hooks/` first, and the advisory hooks fall back to the template. The database
guards never fall back to it (see above).

**The fail direction is per hook and is stated in each rules file.** A hook that BLOCKS
fails **closed** when its rules file is missing or empty: `db-destructive-guard.py` with no
protected database names treats every database as protected. A hook that only WARNS may fail
soft: `integration-check.py` with no markers warns about nothing.
Never copy the soft choice to a guard that blocks.

### Working agreements

A working agreement is one standing rule about how the assistant works with you, written in
plain words in its own markdown file. When a session opens, `working-agreements.py` reads
the files and hands their text to the assistant before its first reply. The plugin ships seven
in `.claude/agreements/`: plain language, one worktree per change, shared repository changes
through pull requests, one-line commands for the user, stop means stop,
recommendations instead of question batches, and use the project history record. The
seventh tells the assistant that the registries and the concept contracts are the project's
memory and design history, to be read and used, and that a central memory system, when a
project switches one on, only supplements them (see
[Memory client and cloud engineering](#memory-client-and-cloud-engineering)).

- **Add your own** by writing a markdown file in your project's `.claude/agreements/`. The
  first line is a level-one heading, and some text follows it. Project files arrive after the
  shipped ones and are labelled "from this project". Every line of a project agreement is
  shown quoted, so project text cannot pose as a shipped section.
- **You cannot replace a shipped one.** A project file with the same name as a shipped file
  is skipped, and the skip is logged.
- **Project instructions and skill gates win.** The assistant is told that your project's own
  instructions, and any skill step that requires asking you, win over every agreement.
- **A size limit applies.** `working-agreements.rules.json` sets it, 9000 characters by
  default, counted in UTF-16 units as the host counts. Whole agreements are dropped, project
  ones first. The closing line names at most three dropped agreements with their paths, then
  gives a count per folder; the log names every dropped agreement. The shipped plain-language
  agreement is never dropped. A project file that links outside its folder, or is larger than
  four times the limit, is skipped without being read in full.
- **One dispatch rule travels with the opening paragraph.** `working-agreements.rules.json`
  carries a `dispatch_rule` text: a subagent the plugin ships is dispatched as
  `agentic-auto-improve:<name>`, and the bare name is for a project that carries its own
  `.claude/agents/<name>.md`. Empty or missing, it adds nothing.
- **Plugin installs only.** A vendored copy of the hook prints nothing in this version.
- **Guidance, not a check.** Nothing blocks when an agreement is ignored. A new agreement
  takes effect in the next session. Switch the hook off with `CLAUDE_WORKING_AGREEMENTS=off`.

### Scripts and templates are not optional

The design-first agent runs `cross_area_scan.py` and `derive_area.py` by path, thirteen skills
cite scripts in `.claude/scripts/`, and every concept contract is a copy of
`templates/concept-contract.md`. The contract sub-task loop is the newest of these:
`pr_merged.py` holds every rule about sub-tasks, dependencies, records and readiness, and
both `/advance` and `/pr-merged` call it rather than reimplementing it. Its suite is
`scripts/tests/test_pr_merged.py`, 761 cases including the placeholder trap that an
unfilled `implementers` slot would otherwise walk into. The finish-install script,
`auto_improve_finish_install.py`, follows the same pattern: every rule lives in the script,
and `scripts/tests/test_auto_improve_finish_install.py` holds its 601 cases. `scripts/tests/test_script_path_resolution.py` is the
182-check suite for the two-layer path resolver. Shipping the resolver without its suite
would ship the part that can be wrong and leave behind the part that would say so.

## Memory client and cloud engineering

Two optional capabilities. Each is **off until a project switches it on** in its project
profile. With both off, every brief, every Step 1.5 run and every capture step is what
it was before they existed. The Project history record rule below applies whatever the switches say.

### The Project history record

A project's own file-based record of its design history, committed in its repository. It
holds the registries under `.claude/registries/` (`MECHANISMS.md`, `VOCABULARY.md`,
`JOURNAL.md`, and `INTEGRATION.md` where the project keeps one), the concept contracts and
follow-up stubs under `.claude/concepts/`, and the Work Item Briefs under
`.claude/work-items/`. It is not the `memory: project` agent memory under
`.claude/agent-memory/`.

- **Who reads it.** `/design-first` and the data-architect read it on every design, in every
  memory state, including when memory is off.
- **Who appends to it, and only after something was confirmed.** `/task` writes the brief and
  the data-architect writes the contract. `/design-first` Steps 3 and 5 append to `JOURNAL.md`
  only the critic findings you confirmed. `fullstack-code-reviewer` appends on a justified
  contract divergence and, as janitor, to `MECHANISMS.md` and `VOCABULARY.md`. `/journal-add`
  appends a manual lesson. The contract-critic appends only its Critique section to the contract under review, and never writes a registry.
- **Who does neither.** A route with no design step (a direct edit of an extra-small or small
  change, `/debug`, `/git-commit`, `/ship`) neither reads nor appends it. Not every flow
  touches it.
- **The Central Memory System only supplements it.** A memory item never replaces, hides or
  skips a read of it, and a local entry wins a conflict until you decide.
- **Where you meet it.** The seventh shipped working agreement states it at every session
  start. `/auto-improve-finish-install` has a section for it, runs the doctor in report mode,
  lists exactly what `--fix` would create, and runs `--fix` only after you say yes. Every line
  `/design-first` Step 1.5 prints, in any state but `disabled`, ends with
  `; design continues from the project history record (registries and concept contracts)`.

### Architecture

The memory capability makes the plugin a careful *client* of a **Central Memory System**: a
separate product, in another repository, that holds engineering knowledge across projects and
is reached only over MCP (Model Context Protocol). The plugin stores no memory, runs nothing
in the background and adds no hook. It touches that system at two call sites only.

```
/flow  (or /task directly)
  |
  +-- /task               Work Item Brief      .claude/work-items/
  |
  +-- /design-first
  |     Step 1.5   MEMORY CALL SITE 1: retrieve
  |                status -> one retrieve call -> normalise -> you mark which items apply
  |                -> the data-architect receives only the items you marked
  |     Step 2..5  the data-architect drafts; you approve the concept contract
  |
  +-- /tdd-first, reviewers, /verify-before-done, /git-commit, /ship
  |
  (you merge the pull request)
  |
  +-- /pr-merged  (or /flow, at its Step 8)
        records confirmation -> ONE writing run -> verdict "flipped"
              |
              +-- MEMORY CALL SITE 2: capture (its own separate question)
                  asked only after the writing run returned flipped
                  candidates -> you untick what not to send -> one send each
                  -> receipts written to the linked brief -> records pull request
```

The two sites are different moments with different questions. Retrieval happens before the
draft and is bound to non-trivial design. Capture happens after the delivery's writing run
returned `flipped`, is **never** folded into the earlier records confirmation and is never
built from the dry run. Under `/flow`, Step 8's single confirmation is unchanged and the
capture question follows the writing run.

**The memory boundary.** One file knows the Central Memory System's tool names and shapes:
`.claude/scripts/memory_boundary.py`, the *Memory adapter*, with its tests in
`.claude/scripts/tests/test_memory_boundary.py`. Everything else, the skills, the agents and
the registries, says only "the configured retrieve tool" and "the configured capture tool". A
scan in `test_plugin_text_scans.py` fails when any other shipped file names a memory tool.
Every field the server returns is untrusted: the adapter validates it, caps it and strips
anything that could pass as markup before an item is shown or written anywhere.

**The configuration slots.** Nine rows in `.claude/project-profile.md`, all starting as
placeholders, which read as off:

| Slot | Meaning |
|---|---|
| `memory.server` | MCP server name. Unset turns memory off |
| `memory.retrieve-tool` | tool name on that server that retrieves items |
| `memory.capture-tool` | tool name that stores a captured item. Unset turns capture off |
| `memory.shape` | which request and response shape the adapter speaks (`v0` is the first) |
| `memory.project-key` | key that scopes memory to this project, or `none` |
| `cloud.providers` | `azure`, `aws`, `gcp`, or `none`. `none` turns the cloud capability off |
| `cloud.iac` | `terraform`, `bicep`, `docker`, `kubernetes`, or `none` |
| `cloud.roots` | infrastructure source roots, or `none` |
| `cloud.mcp-server` | external cloud-management MCP server name; a slot only, no adapter yet |

Memory has three states. `disabled` (no server): nothing is printed and nothing is written.
`unconfigured` (a server, but a missing retrieve tool or an unknown shape): one line is
printed and recorded in the brief. `enabled`: retrieval runs, and capture runs only if the
capture tool is also set.

**MCP integration.**

- **Main session only.** A configured MCP server is called from the main session, never from
  a subagent. A plugin agent's tool line is fixed text and cannot name a server a project
  chooses. Subagents receive results as findings passed to them.
- **Tool names live in the slots**, not in any skill or agent.
- **The shapes live in one script**, `memory_boundary.py`. A new response shape is one new
  profile inside it plus a `memory.shape` value.
- **One attempt, bounded by the host's MCP timeout.** There is no retry and no polling. An
  error, a timeout or an absent tool is recorded as `unavailable`, printed as one line, and
  design goes on. If a send fails during capture, sending stops and every remaining confirmed
  candidate is recorded as not sent.

**Lifecycle separation.** The Central Memory System owns an item's lifecycle (`proposed`,
`validated`, `superseded`, `conflicting`). The plugin never changes an item's status. When it
captures, it only claims `proposed`, at the weakest provenance the evidence supports
(`user-decision` or `source-code-fact`; a manual or post-approval journal entry is never
sent). A captured item is `global` or `project` scope: the registry tier gives the starting
scope, and the project-name check can lower `global` to `project`, never the reverse. The
brief records every item used and every item sent, with ids and versions, in its
`## Memory used` section. It is also separate from three other things named "memory": agent
memory under `.claude/agent-memory/`, the memory pager, and your private auto-memory.

**Cloud engineering.** When `cloud.providers` names at least one provider, the plugin adds
the `cloud-engineering` skill (provider references are read only for the providers you
selected), the `cloud-engineer` agent, an infrastructure-as-code checklist in the security
auditor, and deployment validation through the existing verification steps. The scope rule:
they design, review, validate with non-mutating commands only, and troubleshoot. They **never
run a deploy, apply, create, update or destroy command against a live environment**. They
write it out, in a block labelled "for the user to run", and hand it to you. The plugin adds
**no permission mechanism**: your normal Claude Code permission prompts and the existing
destructive-operation guards apply to those commands unchanged.

### Known limitations

- **Shape `v0` is provisional.** It is a guess at what the Central Memory System returns, and
  it can change when that system's interface is final.
- **There is no capture retry.** A candidate recorded as not sent is not offered again
  automatically.
- **A changed item is found only when it is re-returned.** The change check compares retrieved
  items with the briefs in the current worktree, which are a snapshot of the branch base.
  An item that changed but is not returned by a later retrieval is not noticed, and briefs
  merged later are not seen.
- **An empty project-name token list keeps all capture project-scoped.**
  The doctor scaffolds `.claude/.project-tokens.json` with `"tokens": []`, and an empty or
  missing list fails closed: every candidate is lowered to `project`. `/auto-improve-finish-install`
  can fill the list, and writes a token only when you name it. Fill the list to let a candidate
  stay `global`.
- **Cursor and Codex MCP naming is untested.** Only the Claude Code form of the tool id is
  assumed, and not yet checked (next item).
- **The tool id form and the host timeout are unverified.** The `mcp__<server>__<tool>` id form
  and the host's MCP timeout returning an error are assumptions. The block 3 stub-server
  trials, one with a stub server and one with a server that never answers, left no recorded
  evidence (review item I3 of the t5 review). **A project should not set `memory.shape` until
  that trial is run.**
- **The cloud scope rule is enforced in text only.** The enforcement is the skill and agent
  text, a text scan (`test_cloud_text_scans.py`), your own permission prompts and the existing
  guards. Nothing in the plugin blocks a live-changing command by itself.
- **A cloud-management MCP server is deferred.** `cloud.mcp-server` is a slot with no adapter;
  nothing calls it.

## Using the chain day to day

You start the chain with `/flow`; see [Step 5 of the installation](#step-5-start-using-the-plugin). The sections below cover what happens when a contract has several sub-tasks, what the chain refuses to do, and how to let the doctor create what is missing.

### When a contract has several sub-tasks

A contract's `## Implementation Handoff` section may declare more than one sub-task, each with
its own `Depends on:` line. Then the work is iterated one step per merge, because every
sub-task ends in a pull request somebody has to merge.

Three things drive that, and none of them loops on its own:

| You type | What happens |
|---|---|
| `/advance <contract>` | Starts whatever is ready, opens a pull request, and stops |
| *(you merge the pull request)* | The only step a machine cannot take |
| `/pr-merged <number>` | Confirms the merge with GitHub, records it, and says what it released |

Then `/advance` again. Between those, that is the loop.

A contract with a parent branch ends differently. Once every sub-task has a completion record,
`/pr-merged` hands straight to `/advance`, which starts a background landing script
(`.claude/scripts/land_contract.py`). The script verifies the parent branch, opens the parent pull
request and merges it with no question asked, so that one merge is the only one a machine takes.
`/ship` still never merges: it opens drafts, and the landing script owns the parent merge. A fresh
project ships an empty `contractLanding` block in `.claude/work-item-conventions.json`, so landing
stops with `landing-not-configured` until the project declares its own verification steps.

The rules live in `.claude/scripts/pr_merged.py`, which both a person and a caller invoke, so
neither can drift from the other. It carries 761 tests.

### What it will refuse to do

It will not release a sub-task whose dependency has not landed. It will not treat a contract
with no sub-tasks as finished. It will not record a merge it did not confirm with GitHub, and
it will not claim tests passed when nothing ran them.

Each refusal exists because the mechanism it replaced did the opposite.

### Let the doctor create what is missing

Rather than working through the Quick start steps by hand, run the doctor. Under a plugin install,
`/auto-improve-finish-install` finds and runs it for you. The commands below assume the scripts are in
your project's `.claude/scripts/` (a vendored copy):

```bash
py -3 .claude/scripts/plugin_doctor.py                # report what is missing
py -3 .claude/scripts/plugin_doctor.py --fix          # create what is safe
py -3 .claude/scripts/plugin_doctor.py --drift        # compare the project with the installed plugin
```

`--drift` reads and never writes. It compares the files the project's `.sync-config.json`
declares with the installed plugin's, and it reports a hook registered by both sides. It exits
`0` when the comparison ran and nothing counted, `1` when something did, and `4` when it could
not compare (no plugin found, a folder missing, a file that does not parse, or no file pair
compared). `--json` adds the `compared` count, so a caller can tell an empty comparison from a
clean one, `compared_addons` counts the installed add-on files it compared (they are never
counted in `compared`), and `--ignore-repo-owned` prints a repository-owned finding as `reported` instead of
counting it.

`--drift` also reports `dangling-hook-row`: a row in the project's `settings.json` or
`settings.local.json` that launches a `.py` file that is not on disk (for a `gate-launch.py` row,
also the launcher's `_gate_launch.py` body and the gate argument). This is not drift, because no
plugin copy is compared. It covers rows written before 0.12.3 (the old exec-form rows) and
hand-written rows that plainly launch a Python script. Since 0.14.5 it also covers Project hook
launcher rows (what the installer writes since 0.12.3): a launcher row is dangling when its script is
a file in none of the folders the launcher tries (the project's `.claude/hooks/`, then the main
checkout's when the project folder is a worktree), and it gives the same finding as an old-form row.
The row is read by the launcher's own reader, so a launcher row that reader does not recognise (an
older program text, or scripts run beside a hooks folder from before the launcher) is handled as
before. It reads the project alone, so it is listed even when the comparison
cannot run and the run exits `4`. The finding path is
`<layer>:<event>:<matcher>:<role>:<path as written>`, and its remedy is: restore the file if the
plugin still ships it, otherwise remove the row. The doctor never edits a settings file. Paths
that use any variable other than the project folder, or a leading `~`, are never reported. A row
is checked only when it plainly launches a Python script, in shell form or in exec form alike; all
other shapes are skipped.

It creates the directories, copies the templates and registries out of the plugin, and
scaffolds the configuration files. It is safe to re-run: a second pass finds nothing to do.

Two things it will not do, both on purpose.

**It never overwrites.** A file that exists is yours, whatever it contains.

**It never invents a value that describes your repository.** `project-profile.md` arrives with
the template's placeholders intact, so the machinery reads each slot as unfilled rather than as
a wrong answer. A confidently wrong profile is worse than an obviously empty one. The report
lists those files under `NEEDS YOU`.

It also leaves `.claude/settings.json` alone and says so. Under a plugin install nothing needs
registering, because the plugin registers its own hooks. In a vendored project, registering the
hooks turns enforcement on, and that is your decision rather than a script's: run
`/auto-improve-finish-install`, which shows the exact change, asks, and only then writes it,
with a backup. That skill also fills in the profile slots the doctor left as placeholders.

## Checking your hook registrations

A hook registration is one handler row under `hooks` in your project's `.claude/settings.json`.
The plugin can check that nobody added, removed or changed such a row by accident. The check
compares the settings file with your **hook registration profile**, a file you commit that lists
the rows you expect. Follow these steps in your project.

1. **Record your hook registration profile.** Preview first, then apply with the hash the preview
   prints:

   ```powershell
   py -3 -B .claude/scripts/auto_improve_finish_install.py record-registrations --project .
   py -3 -B .claude/scripts/auto_improve_finish_install.py record-registrations --project . --apply --expect-sha256 <plan hash>
   ```

   This writes `.claude/hook-registration-profile.json`. Commit it. Whenever a pull request
   changes a registration on purpose, run the two commands again in that same pull request. To
   exempt a row on purpose, add an exclusion with a reason to the file by hand. A re-record keeps it.

2. **Vendor seven files.** List these files in your `.claude/.sync-config.json`, so the sync tool
   copies them into your `.claude/scripts/` folder: `check_hook_registrations.py`,
   `auto_improve_finish_install.py`, `pr_merged.py`, `plugin_doctor.py`,
   `check_version_bump.py`, `_preview_apply.py` and `_plugin_root.py`. The checker imports the
   other six. With only the checker present it
   exits 2 with `checker-dependency-missing` and names the files. Vendoring is the only supported
   way, because the landing step must name the checker at a path inside your repository.

3. **Add a landing step.** In your landing verification steps, add one that runs exactly this
   command, with no `when_paths`:

   ```powershell
   py -3 -B .claude/scripts/check_hook_registrations.py --settings .claude/settings.json --hook-registration-profile .claude/hook-registration-profile.json
   ```

   The step reads its result from the exit code. Run the same line yourself before you push.

Why the step looks like this:

- `-B`, together with the checker's own setting, keeps Python from writing a `__pycache__`
  folder. A cache folder in the tree would halt the landing on "the steps changed the worktree".
  A harness that imports the checker as a module without `-B` can still cache the checker itself.
- The step passes the settings file and the hook registration profile as arguments, so the
  landing can see which files the failure names. It can then say whether a failure came from the
  contract or from the default branch. A failure caused only by one of the four dependency
  scripts reads as `undetermined`, because the step does not name them.

When you adopt this, delete your own hook-registration tests and their baseline entries. The
plugin's check replaces them.

## Moving a project onto registry layout 2

Do this in your project when `py -3 .claude/scripts/registry_migrate.py --check --project .`
exits 6 (`pending` or `stale-sync`). Nothing forces it on you: until you do, writers keep
working. `registry_append.py` puts a project entry into a domain file (it creates `general.md`
when it is missing) and never into a root, and it prints an advisory that names the migration.
Run the steps in order. Use the scripts you copied, with the new files listed in "Domain-split
registries (issue #235)" above.

1. **Commit your registry changes.** The migration refuses with `uncommitted-registry-changes`
   when `.claude/registries/` has uncommitted changes, and with `not-a-git-tree` outside a
   repository.

   ```powershell
   git add .claude/registries
   git commit -m "chore: commit registries before migration 0001"
   ```

2. **Preview.** This writes nothing under `.claude/registries/`. It prints the plan hash and
   writes a report folder under `.claude/cache/registry-migrations/`.

   ```powershell
   py -3 .claude/scripts/registry_migrate.py --dry-run --project .
   ```

3. **Read `registry-migration-report.md`** in that folder. Look at these parts:
   - *Migration leftovers*: text that could not be read as an entry. It is copied verbatim into
     a fenced block at the end of that registry's `general.md` and is never lost.
   - *Plugin-owned token entries*: Universal entries owned by the plugin that name one of your
     project tokens. They stay in place, because the next sync would restore them. The fix
     belongs in the plugin's copy of the entry.
   - *Unverified token entries*: entries the migration could not judge because it found no
     installed plugin root. They stay where they are.
   - *Universal candidates*: entries without a project token in a root that has no
     `## Project: <name>` heading. They are reported and not moved. To move them, add a
     `## Project: <name>` heading above them while still on layout 1, commit, and run the
     preview again. That heading is the one hand edit this procedure allows.
   - *Orphans*: entries without a body. Each comes with a ready-to-run
     `registry_append.py --archive-title-only "<title>"` line.

4. **Resolve any `conflicting-entry`.** It means two copies of one entry differ in a field. The
   refusal names every location and each version's first line. On layout 1, keep one version,
   rename one title, or fold one version into a `Correction` line; commit; run the preview again.

5. **Apply**, with the hash the preview printed:

   ```powershell
   py -3 .claude/scripts/registry_migrate.py --apply --project . --expect-sha256 <plan hash>
   ```

   It refuses with `changed-since-preview` if anything changed since the preview. Every other
   refusal also leaves the registry files byte-identical. The refusal codes are
   `project-undetermined`, `not-a-git-tree`, `uncommitted-registry-changes`,
   `conflicting-entry`, `unknown-layout`, `changed-since-preview`, `content-loss-detected`,
   `symlink-target` and `write-failed`. Exit 3 is a refusal, and exit 2 is a bad argument, or
   `plan-build-failed` (an exception while building the plan; the report is still written and
   names the error).

6. **Check the result.**

   ```powershell
   py -3 .claude/scripts/registry_migrate.py --check --project .
   py -3 .claude/scripts/validate_registries.py --check-structure --project .
   py -3 .claude/scripts/generate_registry_digest.py
   ```

   `--check` must exit 0 (`current`). `--check-structure` exits 0; advisory lines (for example
   `advisory: R4` for a path that exists in no search root, or `advisory: leftover`) do not
   fail it, and any other finding does. The digest generator exits 0.

7. **Commit.** The backups of the replaced files sit under
   `.claude/cache/registry-migrations/`, not in the registries.

   ```powershell
   git add .claude/registries
   git commit -m "chore: move registries to layout 2"
   ```

8. **Recover or mark orphans.** For each bodiless entry, either restore its body from your own
   backups or mark it with the line from the report:

   ```powershell
   py -3 .claude/scripts/registry_append.py --project . --registry journal --archive-title-only "<title>"
   ```

**Stale sync.** If a sync delivered the layout 2 root files over a project that still had
`## Project:` sections, `--check` reports `stale-sync` and exits 6. The same steps repair it.
Until the sync tool halts on exit 6 by itself, run `--check` before you sync. That is a
follow-up for the sync tool, which lives outside this repository
(`.claude/concepts/followups/2026-11-04-sync-tool-registry-layout-gate.followup.md`). The sync
tool's file lists must also include the new modules.

## Useful plugins

Other Claude Code plugins that work well beside this one. None is required. Each row gives
what the plugin does, where its documentation lives, and how much it matters for a project
that uses this plugin's delivery chain.

Importance levels: **High** means install it early, because the problem it solves shows up
quickly. **Medium** means it helps in common situations. **Low** means it is nice to have.

| Plugin | What it does | Documentation | Importance |
|---|---|---|---|
| `mgorkemuz/claude-code-shepherd` | Tracks the background processes Claude Code's Bash tool starts (for example `npm run dev` or `vitest --watch`), and lets you stash, kill or restore them. It cleans up orphaned processes left by a crashed session on the next launch, so they stop holding ports and memory. Requires `jq`; macOS and Linux only. | [github.com/mgorkemuz/claude-code-shepherd](https://github.com/mgorkemuz/claude-code-shepherd) | Medium. High if you run several parallel sessions or worktrees, because each one can leave dev servers behind. |

Install it with `/plugin marketplace add mgorkemuz/claude-code-shepherd`, then
`/plugin install shepherd@shepherd`.

## Documentation

- [CONTRIBUTING.md](CONTRIBUTING.md) — sync workflow, the project-name check, conflict
  resolution, and **what may not ship**: the rule that an asset must state its own state,
  and that nothing ships which is only safe because a separate document warns about it
- `.claude/hooks/tests/` and `.claude/scripts/tests/` — the suites
- Each agent and skill — its own `## When to Use` section

## Status

Extracted from a first consuming project on 2026-09-10; inventory completed and the
ownership and direction model corrected on 2026-09-12. Made installable under the Claude
Code, Cursor and OpenAI Codex plugin mechanisms on 2026-09-13. The contract sub-task
loop — `/flow`, `/advance`, `/pr-merged` and `pr_merged.py` — landed the same day, with
`plugin_doctor.py` to bootstrap a consuming project. The stated inventory was
reconciled against the tree again on 2026-09-14, after the orchestrator scripts were
withdrawn and five test suites were added without the counts following either move. On
2026-10-04 the `/auto-improve-finish-install` skill landed, with its script
`auto_improve_finish_install.py`, and every inventory count in this file was recounted from
the tree rather than incremented. See [Known limitations](#known-limitations) for what that
release does not yet cover.
