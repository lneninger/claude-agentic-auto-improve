# claude-agentic-auto-improve

A reusable repository holding the project-independent half of a Claude Code setup:
generic agents, skills, hooks, workflow scripts, templates, references and the Universal
tier of the registries, for any project following the Data-First Engineering Protocol.

## What this is, and what it is not

It is consumed two ways, and both are supported.

**As an installable plugin.** The repository carries a manifest for each of three provider
mechanisms and hosts its own marketplace, so Claude Code, Cursor and OpenAI Codex can each
install it directly from git. See [Installing](#installing) below. Assets load from the
provider's plugin cache and are not copied into your repository.

**As a vendoring source.** A place to copy files from, so a new project can adopt the same
workflow without assembling it by hand. The copies are committed in the consuming
repository, so that repository works when this checkout is absent, and they can be edited
in place and synced back. See [Quick start in a new project](#quick-start-in-a-new-project).

Pick vendoring when you intend to modify the assets or need them present offline; pick the
plugin when you want a dependency rather than a fork. **The two are not yet reconciled** —
see [Known limitations](#known-limitations) before mixing them.

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

## Installing

The repository is its own marketplace, so no separate marketplace repository is involved.

**Claude Code**

```
/plugin marketplace add lneninger/claude-agentic-auto-improve
/plugin install agentic-auto-improve@auto-improve
```

**OpenAI Codex**

```bash
codex plugin marketplace add lneninger/claude-agentic-auto-improve
```

Then install `agentic-auto-improve` from `/plugins`. Start a new session afterwards; Codex
does not load a plugin's skills into the session that installed it.

**Cursor**

Run `/add-plugin` and give it this repository. Cursor reads the root `plugin.json`
(the vendor-neutral Agent Plugins manifest) and `.cursor-plugin/plugin.json` beside it.

### Updating an installed plugin

A merged change reaches a running Claude Code session only when the plugin's version number
changes. Sessions run the hooks from the versioned install cache, at
`~/.claude/plugins/cache/auto-improve/agentic-auto-improve/<version>/`, and not from the
marketplace clone. These two commands refresh them:

```
claude plugin marketplace update auto-improve
claude plugin update agentic-auto-improve@auto-improve
```

The second command answers "already at the latest version" and leaves the cache alone when
the version is unchanged. So a fix merged without a version bump never reaches an installed
copy. The version is declared in five places, and all five must change together:
`plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (twice) and
`.cursor-plugin/plugin.json`. Start a new session afterwards, because hooks are read when a
session starts. To check which copy is live, search the cache and not the marketplace clone.

### Installing the hooks turns on enforcement

**The plugin is the source of its hooks.** Its `.claude/hooks/hooks.json` registers twelve
hooks, and they are active the moment the plugin is enabled. They are gates, not suggestions.

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
| PreToolUse | `Edit\|Write\|MultiEdit\|NotebookEdit` | `architecture-guard.py` | yes |
| PreToolUse | `Edit\|Write\|MultiEdit\|NotebookEdit` | `db-destructive-guard.py` | yes |
| PreToolUse | `Bash` | `db-destructive-guard.py` | yes |
| PreToolUse | `Bash` | `db-research-readonly-guard.py` | yes |
| PreToolUse | `PowerShell` | `db-destructive-guard.py` | yes |
| PreToolUse | `PowerShell` | `db-research-readonly-guard.py` | yes |
| UserPromptSubmit | none | `plain-language-guard.py --carry-forward` | no, it only hands over a saved note |
| PostToolUse | `Edit\|Write\|MultiEdit` | `post-edit-dispatcher.py` (asynchronous) | no |
| Stop | none | `plain-language-guard.py` | yes, with a short correction request |
| Stop | none | `memory-pager.py` (asynchronous) | no |

- **`concept-gate`** blocks `Edit` / `Write` / `MultiEdit` on non-trivial files until an
  approved concept contract names them. Run `/design-first` to produce one.
- **`architecture-guard`** blocks banned patterns at the write, using the project's own rules.
- **`db-destructive-guard`** and **`db-research-readonly-guard`** block database operations
  that could destroy data. As of 0.7.0 the plugin registers both guards itself. The destructive
  guard now runs on the edit group, `Bash` and `PowerShell`; the read-only guard runs on `Bash`
  and `PowerShell` and **has left the edit group**. Before 0.7.0 the guards ran on
  `Bash|Edit|Write|MultiEdit` and never on PowerShell.
- **`plain-language-guard`** checks that the assistant's prose reads plainly.
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
`architecture-guard.exceptions.json`, `plain-language-guard.rules.json` and
`integration-check.rules.json` are read from your project's `.claude/hooks/` when it has them,
and from the template beside the hook otherwise.

Seven of the nine variables below are kill switches, set by you and never by an agent. Two are
not: `CLAUDE_ACTIVE_CONTRACT` is an approval pin and `CLAUDE_DESTRUCTIVE_DB_OK` is a one-shot
approval. This table lists exactly the variables the hooks read, and a test (INV-12 in
`test_plugin_manifests.py`) fails when the two disagree.

| Variable | Effect |
|---|---|
| `CLAUDE_CONCEPT_GATE=off` | disable the concept gate |
| `CLAUDE_ARCH_GUARD=off` | disable the architecture guard |
| `CLAUDE_PLAIN_LANGUAGE_GUARD=off` | disable the plain-language guard |
| `CLAUDE_INTEGRATION_CHECK=off` | disable the integration check (one piece of the dispatcher) |
| `CLAUDE_MEMORY_PAGER=off` | disable the memory pager |
| `CLAUDE_ACCURACY_TRACKER=off` | stop the three contract-accuracy trackers (the rest of the dispatcher) |
| `CLAUDE_WORKING_AGREEMENTS=off` | skip the working agreements at session start |
| `CLAUDE_ACTIVE_CONTRACT=<path>` | approval pin: pin one approved contract |
| `CLAUDE_DESTRUCTIVE_DB_OK=1` | one-shot approval for a destructive database operation |

An `off` switch also accepts `0`, `false` and `no`. Beside the table, `CLAUDE_CONTRACT_INDEX=off`
turns the contract-lookup index off for concept-gate, which then reads every contract file itself.
To take the assets without the enforcement, vendor the repository instead of installing it and
register only the hooks you want.

### Retired hooks, and how to restore one

Version 0.7.0 retired six hooks. The plugin neither ships nor registers them any more:

| Retired hook | What it did | Why it went |
|---|---|---|
| `bash-gate.py` | blocked shell writes into source files without a contract | the slowest Bash hook, and it refused legitimate writes; `concept-gate` still gates every edit tool |
| `codegraph-first-guard.py` | blocked `Read` / `Grep` / `Glob` on source until a CodeGraph tool had run | the slowest single cost per read, and unusable by an agent without CodeGraph tools |
| `codegraph-turn-tracker.py`, `codegraph-turn-reset.py` | kept the per-turn marker the guard above read | they existed only for that guard |
| `architecture-advisor.py` | a keyword reminder at every prompt | the guard still enforces at the write |
| `plan-question-advisor.py` | scanned the transcript at every prompt | the `plan-questions` skill stays and is invoked by name |

The four post-edit checks are not retired: they still exist as files and run, but inside
`post-edit-dispatcher.py` rather than as four registrations.

**To restore a retired hook in one project**, take its file from the last release that had it
(0.6.2) and register it yourself, because the plugin no longer carries it:

1. Copy the file from that release's folder in the plugin cache, or from the repository at that
   tag with `git show <tag>:.claude/hooks/<name>`, into your project's `.claude/hooks/`.
   Bring `_project_paths.py`, `_error_log.py`, `_contract_files.py` and `_contract_index.py` along
   when it imports them.
2. Register it in your own `.claude/settings.local.json` (this machine only) or
   `.claude/settings.json` (the team), under the event and matcher in the table above.
3. Start a new session. Hooks are read when a session starts.

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
| 22 skills | yes | yes | yes |
| 14 agents | yes | yes | no — not a component of the portable Agent Plugins standard |
| 12 hooks | yes | no | no |
| 6 working agreements, delivered by a hook | yes | no | no |
| scripts, templates, references, registries | yes, in the plugin's own tree | yes | yes |

**Corrected 2026-09-13.** This row used to read `vendoring only`, and that was wrong. An
install copies the whole repository into the provider's cache, script files included — the
`superpowers` plugin ships Python the same way and its files sit in that cache today.

What was actually missing was a way for a skill to *find* them. A skill citing
`.claude/scripts/<name>.py` is naming a path inside **your** repository, which exists when you
vendor and does not when you install.

Skills that call a script now resolve it first, trying the vendored path, then
`$CLAUDE_PLUGIN_ROOT`, then the provider's cache. `/advance` and `/pr-merged` do this, and any
skill added later should copy the pattern rather than assume a vendored layout.
`/auto-improve-finish-install` does it with an explicit ordered test, because `ls` on several
paths sorts them and so loses the order.

The templates still need copying by hand under an install, because a concept contract is a
file **in** your repository rather than one read from the plugin.

Cursor and OpenAI both read the **Agent Plugins** open standard
(`https://agent-plugins.org`), which is why one root `plugin.json` serves both. Claude Code
uses its own format at `.claude-plugin/plugin.json`. Hooks are Claude-only in this release:
Claude's event names, its `${CLAUDE_PLUGIN_ROOT}` substitution and its blocking-exit-code
contract have no tested equivalent in the other two runtimes, and shipping an untested
translation would be worse than shipping none.

### Known limitations

- **The hook entries launch `py -3`**, the Windows Python launcher, matching the
  invocation every hook docstring in this repository already specifies. On macOS and Linux,
  change `"command": "py"` to `"python3"` and drop the `"-3"` argument throughout
  `.claude/hooks/hooks.json`. The format has no per-platform branch, so this is documented
  rather than solved.
- **Plugin install and vendoring are not reconciled.** Under an install the assets live in
  the provider's cache, so a skill or hook that resolves a path such as
  `.claude/scripts/cross_area_scan.py` inside *your* repository will not find it there.
  `_project_paths.py` searches `CLAUDE_PROJECT_DIR`, then its own location, then the current
  directory, then `~/.claude`, which mostly absorbs this — but it is not yet proven for
  every skill. Vendoring remains the path with no such gap.
- **The four per-project configuration files cannot be delivered by an install.**
  `project-profile.md`, `area-mapping.json`, `work-item-conventions.json` and
  `.project-tokens.json` describe *your* repository, so you must author them at
  `.claude/` in your own project even when the rest arrives as a plugin.
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
skills/          22 generic skills          (plugin root -- all three providers)
agents/          14 generic agents          (plugin root -- Claude and Cursor)
.claude/
  agreements/    6 shipped working agreements, delivered at session start
  hooks/         12 generic hooks, 4 shared helper modules, 6 generic data files
    hooks.json   Claude hook registration, referenced by .claude-plugin/plugin.json
    tests/       9 hook test suites
  scripts/       15 workflow scripts, 3 shared helper modules
    tests/       11 suites, including the path-resolution suite
  templates/     6 document templates
  references/    2 reference documents
  registries/    MECHANISMS.md, VOCABULARY.md, JOURNAL.md (Universal tier only)
  area-mapping.json          TEMPLATE - schema intact, empty content set
  work-item-conventions.json TEMPLATE - schema intact, empty content set
  project-profile.md         TEMPLATE - blank slot table
  .project-tokens.json       TEMPLATE - empty token array
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
dotnet-backend-architect, angular-senior-dev, python-ai-developer, registry-scout.

### Skills

flow, task, design-first, tdd-first, advance, pr-merged, verify-before-done,
git-commit, ship, debug, north-star, north-star-review, list-contracts,
contract-accuracy, critique-now, cross-impact, journal-add, plan-questions,
validate-registries, promote-ui-rule, sql-server-patterns, auto-improve-finish-install.

`auto-improve-finish-install` is not a stage of the chain below. It is a one-time setup
skill, run once per project after the plugin is installed. Its name carries the plugin's name
because you may have several plugins installed.

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

concept-gate, architecture-guard, plain-language-guard, db-destructive-guard,
db-research-readonly-guard, memory-pager, working-agreements, post-edit-dispatcher, and the
four checks the dispatcher runs: integration-check, critic-verdict-tracker,
contract-status-watcher, journal-post-approval-tracker. That is twelve hook files. Beside them
sit the shared helpers `_error_log.py`, `_memory_common.py`, `_project_paths.py` and
`_inprocess_hook.py` (the dispatcher's in-process runner), and the generic data files
`architecture-guard.rules.json`, `architecture-guard.exceptions.json`,
`plain-language-guard.rules.json`, `integration-check.rules.json`,
`db-destructive-guard.rules.json` and `working-agreements.rules.json`.

All twelve hook files are accounted for in `.claude/hooks/hooks.json`, which the Claude
manifest references: eight are registered there directly and the four checks are named in the
dispatcher's constant list. That makes twelve registrations, because `plain-language-guard.py`
is registered on two events and `db-destructive-guard.py` on three matchers, while the four
checks share the dispatcher's one. The file plus that list are the single registration point:
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
the files and hands their text to the assistant before its first reply. The plugin ships six
in `.claude/agreements/`: plain language, one worktree per change, shared repository changes
through pull requests, one-line commands for the user, stop means stop, and
recommendations instead of question batches.

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
- **Plugin installs only.** A vendored copy of the hook prints nothing in this version.
- **Guidance, not a check.** Nothing blocks when an agreement is ignored. A new agreement
  takes effect in the next session. Switch the hook off with `CLAUDE_WORKING_AGREEMENTS=off`.

### Scripts and templates are not optional

The design-first agent runs `cross_area_scan.py` and `derive_area.py` by path, thirteen skills
cite scripts in `.claude/scripts/`, and every concept contract is a copy of
`templates/concept-contract.md`. The contract sub-task loop is the newest of these:
`pr_merged.py` holds every rule about sub-tasks, dependencies, records and readiness, and
both `/advance` and `/pr-merged` call it rather than reimplementing it. Its suite is
`scripts/tests/test_pr_merged.py`, 484 cases including the placeholder trap that an
unfilled `implementers` slot would otherwise walk into. The finish-install script,
`auto_improve_finish_install.py`, follows the same pattern: every rule lives in the script,
and `scripts/tests/test_auto_improve_finish_install.py` holds its 199 cases. `scripts/tests/test_script_path_resolution.py` is the
177-check suite for the two-layer path resolver. Shipping the resolver without its suite
would ship the part that can be wrong and leave behind the part that would say so.

## Quick start in a new project

> Vendoring, not installing. To install instead, see [Installing](#installing) — you can
> skip to step 4, since a plugin install delivers steps 1 to 3 for you.
>
> You may have several plugins installed. The skill that finishes this one is named
> `auto-improve-finish-install`, so its name says which plugin it belongs to.

1. **Copy the trees.** Copy the root-level `skills` and `agents` directories, and
   `.claude/hooks`, `scripts`, `templates` and `references`, into your project's
   `.claude/`, at their ordinary paths — so this repository's root `skills/` becomes your
   `.claude/skills/`, and its root `agents/` becomes your `.claude/agents/`. Do not create
   a subdirectory named after this repository; one copy, in the normal place.

   The two root directories are deliberately not where a vendoring consumer puts them. They
   sit at this repository's root because a plugin's components must, and they move into
   `.claude/` on the way into yours because that is where a project keeps them.

2. **Copy the registries** and add your own `## Project: <name>` section below the
   Universal tier in each. Everything below the first `## Project:` line stays yours and
   is never synced.

3. **Fill in the four templates.** `area-mapping.json`, `work-item-conventions.json`,
   `project-profile.md` and `.project-tokens.json` ship with their schema and an empty
   content set, because their shape is generic and their content is not.
   `.project-tokens.json` is the one to fill in first: an unguarded outbound sync is how
   contamination spreads.

4. **Write `.claude/project-profile.md`: run `/auto-improve-finish-install`.** It looks at
   your repository, shows each proposed value next to the file that suggested it, and writes
   the slots that are still placeholders after one confirmation. It never overwrites a slot
   you wrote.

   *By hand instead:* the profile is the only file you must author to make the
   fourteen agents correct, and it is required under a plugin install too. A generic agent
   cites a slot by name rather than a literal path, so every slot must be present, and an
   empty slot reads `none`.

5. **Register the hooks: the same `/auto-improve-finish-install` command does this as its
   second stage.** Under a plugin install it checks that the hooks are ready to load and
   writes nothing. Under a vendored copy it shows the exact `settings.json` change as a diff,
   asks, and writes it with a backup. The file is re-serialised, so the diff can show reflowed
   lines; the meaning is kept, and the diff is exactly what will be written. Either way, the
   hooks apply only in a session started afterwards.

   *By hand instead:* register the hooks in your `.claude/settings.json`, pathing every command through
   `$CLAUDE_PROJECT_DIR/.claude/hooks/`. `.claude/hooks/hooks.json` in this repository is
   the worked example: it registers all twelve against the right events and matchers, so
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

## Where to start once it is installed

**Once per project, type `/auto-improve-finish-install`.** It finishes the two Quick start
steps that nobody can finish by copying files: the project profile, and the hooks. Run it
again whenever you like. A second run changes nothing. Under Cursor and Codex it fills in the
profile and says that hooks are Claude-only in this release.

**Then type `/flow`.** That is the front door, and everything else is reached through it.

```
/flow <an issue number, a link, or a sentence describing the work>
```

It runs the chain in order: intake, a concept contract you approve, test-first implementation,
adversarial review, verification, a commit, and a draft pull request. It pauses only where a
person has to decide, and the contract gate is the one stop that can never be automated away.

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
neither can drift from the other. It carries 484 tests.

### What it will refuse to do

It will not release a sub-task whose dependency has not landed. It will not treat a contract
with no sub-tasks as finished. It will not record a merge it did not confirm with GitHub, and
it will not claim tests passed when nothing ran them.

Each refusal exists because the mechanism it replaced did the opposite.

### Let the doctor create what is missing

Rather than working through the steps above by hand, run:

```bash
py -3 .claude/scripts/plugin_doctor.py                # report what is missing
py -3 .claude/scripts/plugin_doctor.py --fix          # create what is safe
```

It creates the directories, copies the templates and registries out of the plugin, and
scaffolds the configuration files. It is safe to re-run: a second pass finds nothing to do.

Two things it will not do, both on purpose.

**It never overwrites.** A file that exists is yours, whatever it contains.

**It never invents a value that describes your repository.** `project-profile.md` arrives with
the template's placeholders intact, so the machinery reads each slot as unfilled rather than as
a wrong answer. A confidently wrong profile is worse than an obviously empty one. The report
lists those files under `NEEDS YOU`.

It also leaves `.claude/settings.json` alone and says so. Registering the hooks turns
enforcement on, and that is your decision rather than a script's. When you are ready,
run `/auto-improve-finish-install`: it shows the exact change, asks, and only then writes
it, with a backup. That skill also fills in the profile slots the doctor left as
placeholders.

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
