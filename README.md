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
>   is the opt-in `strict-shell-gate` add-on (see "Add-ons" below). The plugin now registers a launcher row on `Bash` and
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

**The plugin is the source of its hooks.** Its `.claude/hooks/hooks.json` registers thirteen
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
| PreToolUse | `Bash\|PowerShell` | `gate-launch.py` with `concept-gate.py` (the main-checkout guard and merge-direction check; the gate half allows any shell command) | yes |
| PreToolUse | `Edit\|Write\|MultiEdit\|NotebookEdit` | `architecture-guard.py` | yes |
| PreToolUse | `Edit\|Write\|MultiEdit\|NotebookEdit` | `db-destructive-guard.py` | yes |
| PreToolUse | `Bash` | `db-destructive-guard.py` | yes |
| PreToolUse | `Bash` | `db-research-readonly-guard.py` | yes |
| PreToolUse | `PowerShell` | `db-destructive-guard.py` | yes |
| PreToolUse | `PowerShell` | `db-research-readonly-guard.py` | yes |
| UserPromptSubmit | none | `plan-question-advisor.py` | no, it only adds a reminder in plan mode |
| PostToolUse | `Edit\|Write\|MultiEdit` | `post-edit-dispatcher.py` (asynchronous) | no |
| Stop | none | `stop-dispatcher.py` (runs `../scripts/concept_changed_check.py`) | yes, with a list of files no contract covers |
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
- **`stop-dispatcher`** is the single Stop seam. It runs one check inside its process:
  `../scripts/concept_changed_check.py`. If the check exits 2 the turn is stopped and its error
  text is shown. Any other failure is ignored. A later Stop check would join it without a second
  program start.
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

**Removed in 0.9.20:** the end-of-turn writing hook `plain-language-guard.py`, with its
`plain-language-guard.rules.json`. The plain-language agreement stays; only the checker is gone.
If your project vendored a copy, take it out in this order. First remove every row that runs
the hook from your `settings.json`: one on prompt submit, and in installs registered before 0.9.8
also one at turn end. Then delete the file and its rules file. Do not delete the file first: a
row that points at a missing script exits with code 2, so a prompt-submit row would block every
prompt. Start a new session afterwards. The hook's optional leftovers,
`.claude/state/plain-language-guard-<session>.json` and `.claude/logs/plain-language-guard.log`,
are never read again and you may delete them by hand.

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
  - the claim that the gate "auto-bypasses until the index exists", which the hook does not do.
    With no `mcp__codegraph__*` tool in the session, every source Read is blocked; read through
    the shell, or uninstall the add-on and start a new session.
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

### Retired hooks, and how to restore one

Version 0.7.0 retired six hooks. Version 0.9.8 brought `plan-question-advisor.py` back as a
default hook (see the table above). Version 0.9.9 brings the other five back as three **opt-in
add-ons**. The plugin ships their files under `.claude/addons/` but never registers them, so a
default install runs none of them:

| Add-on | Its hook files | What it does | Why it is not a default |
|---|---|---|---|
| `angular-tailwind` | no hook file is installed; four rule documents and a stylesheet snippet instead. The old `angular-tailwind-advisor.py` (formerly `architecture-advisor.py`) still ships but is disabled since 0.10.0 | copies the Angular, Material, Tailwind and UI-pattern rule documents into `.claude/references/angular-tailwind/` and lists them in `review.documents`; the guard's lines cite them by Rule ID | it only suits Angular plus Tailwind projects; `architecture-guard.py` still enforces at the write |
| `codegraph` | `codegraph-first-guard.py`, `codegraph-turn-tracker.py`, `codegraph-turn-reset.py` | blocks `Read` / `Grep` / `Glob` on source until a CodeGraph tool has run in the turn | it blocks every source read when the CodeGraph server is missing |
| `strict-shell-gate` | `bash-gate.py` | reads each shell command before it runs and blocks a write into a source file no approved contract covers | a program start on every shell command, and it misreads some commands (it read `--stat` as the file written in `sed -i` followed by `git diff --stat`) and cannot see what a program such as `python` or `node` writes; the Changed-file check, which stays on, catches those after the fact |

**To install one in a project**, run its skill. Each one previews the files and the
`settings.json` change, asks once, and writes only after a yes:

| Add-on | Install skill | Uninstall skill |
|---|---|---|
| `angular-tailwind` | `/auto-improve-angular-tailwind-install` | `/auto-improve-angular-tailwind-uninstall` |
| `codegraph` | `/auto-improve-codegraph-install` (stops with a plain message when the CodeGraph MCP server is not configured, has no command or url, or is listed as disabled) | `/auto-improve-codegraph-uninstall` |
| `strict-shell-gate` | `/auto-improve-strict-shell-gate-install` | `/auto-improve-strict-shell-gate-uninstall` |

Each install skill runs `auto_improve_finish_install.py addon --name <add-on>`. The script copies the
add-on's hook files and the helper files its `addon.json` names (a helper only when the project
lacks it), then writes the rows as Project hook launcher rows that run `<file>` from your project's
`.claude/hooks/` (see [Project hook launcher](#project-hook-launcher)), through
the same preview, plan hash, backup and symbolic-link refusal as the hooks step. The rows are
inserted into the existing `settings.json` as text, so every other byte of the file (escapes,
one-line lists, line endings, byte order mark) stays as it was, and a folder it would write into
that is a link to somewhere else (a junction on Windows) is refused. An add-on that ships rule
documents (`angular-tailwind`) also copies them and appends their paths to `review.documents`,
which needs a project profile with that row (otherwise it stops with `profile-slot-missing`). The
install never removes a row or a file and never overwrites a file that differs; start a new
session afterwards, because hooks are read when a session starts. `plugin_doctor.py --drift`
compares an installed add-on's files with the plugin's.

**To remove an add-on**, run its uninstall skill. It runs `auto_improve_finish_install.py
addon-remove --name <add-on>`: it previews the rows, files and profile entries, asks once, and
writes `settings.json` first (with a backup), the profile next and deletes files last. Do not
delete a hook file by hand before its row is gone: a row in the earlier form that points at a
missing script exits with code 2 and blocks every prompt (a launcher row exits by its class
instead; see [Project hook launcher](#project-hook-launcher)). It deletes a file only when it is identical to the plugin's
copy (line endings and a leading byte order mark ignored) or matches a copy an earlier release
shipped; an edited file is kept and reported. Helper files and the stylesheet snippet are never
deleted. A second run finds nothing to do. The skill never edits `settings.json` by hand; only when a
hook cannot run, as in the table below, do you remove its row by hand.

#### Ways out when a hook cannot run

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
| `codegraph-turn-reset.py` is missing | Python's error on `UserPromptSubmit`, so every prompt is blocked | edit `.claude/settings.json` outside the session, in an editor |
| `codegraph-turn-tracker.py` is missing | an error after each CodeGraph call; the marker is never set, so reads stay blocked | as for a missing `codegraph-first-guard.py` |

A session with no `mcp__codegraph__*` tool is not a failure of the hook, but every source Read
is blocked, because the guard never checks for an index. Reading through the shell works, as does
running `/auto-improve-codegraph-uninstall` and then starting a new session. If the CodeGraph index
is stale, run `codegraph sync` or `codegraph init -i`.

The four post-edit checks are not retired: they still exist as files and run, but inside
`post-edit-dispatcher.py` rather than as four separate hook entries.

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
copy from before 0.12.3), the writer falls back to the earlier form that names
`${CLAUDE_PROJECT_DIR}/.claude/hooks/<file>` and says so in the preview's notes.

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
- **R4, a missing `codegraph-turn-tracker.py` only warns.** The CodeGraph gate then blocks every
  source read by its own decision.
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
| 28 skills | yes | yes | yes |
| 14 agents | yes | yes | no — not a component of the portable Agent Plugins standard |
| 13 hooks | yes | no | no |
| 6 working agreements, delivered by a hook | yes | no | no |
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
skills/          32 generic skills          (plugin root -- all three providers)
agents/          14 generic agents          (plugin root -- Claude and Cursor)
.claude/
  agreements/    6 shipped working agreements, delivered at session start
  addons/        3 opt-in add-ons (addon.json + hook files), never registered by hooks.json
  hooks/         13 generic hooks, a gate launcher, 7 shared helper modules, 6 generic data files
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
validate-registries, promote-ui-rule, sql-server-patterns, auto-improve-finish-install,
auto-improve-angular-tailwind-install, auto-improve-angular-tailwind-uninstall,
auto-improve-codegraph-install, auto-improve-codegraph-uninstall,
auto-improve-strict-shell-gate-install, auto-improve-strict-shell-gate-uninstall,
angular-ui-rules, unit-testing, application-design, website-design.

A skill or agent that mentions a skill owned by another plugin follows the rule in
[CONTRIBUTING.md](CONTRIBUTING.md) → "Referencing another plugin's skill".

`auto-improve-finish-install` is not a stage of the chain below. It is a one-time setup
skill, run once per project after the plugin is installed. Its name carries the plugin's name
because you may have several plugins installed. The three `auto-improve-*-install` skills
after it are not stages either: each installs one opt-in add-on, and its paired
`auto-improve-*-uninstall` skill removes it (see "Retired hooks, and how to restore one").
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
and stop-dispatcher. That is thirteen hook files. The Changed-file check the Stop dispatcher runs
is not a hook file: it is the script
`.claude/scripts/concept_changed_check.py`. Beside the hook files
sit the gate launcher `gate-launch.py` and the shared helpers `_error_log.py`, `_gate_launch.py`,
`_memory_common.py`, `_project_paths.py`, `_main_checkout_guard.py`, `_shell_write_targets.py`
(the shell parser the guard reads write targets with) and
`_inprocess_hook.py` (the dispatchers' in-process runner), and the generic data files
`architecture-guard.rules.json`, `architecture-guard.exceptions.json`,
`integration-check.rules.json`,
`db-destructive-guard.rules.json` and `working-agreements.rules.json`.

All thirteen hook files are accounted for in `.claude/hooks/hooks.json`, which the Claude
manifest references: nine are registered there directly (`concept-gate.py` through the gate
launcher) and four are named in the post-edit dispatcher's constant list. The Stop dispatcher's
list names only the Changed-file check script.
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
`scripts/tests/test_pr_merged.py`, 539 cases including the placeholder trap that an
unfilled `implementers` slot would otherwise walk into. The finish-install script,
`auto_improve_finish_install.py`, follows the same pattern: every rule lives in the script,
and `scripts/tests/test_auto_improve_finish_install.py` holds its 308 cases. `scripts/tests/test_script_path_resolution.py` is the
182-check suite for the two-layer path resolver. Shipping the resolver without its suite
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

   **Upgrading from before 0.9.3:** `work-item-conventions.json` is project-owned and sync
   never rewrites it, so add the `issueTitle.subIssue` block (`$comment`, `legend` and
   `format`) from this repository's copy into yours. Until you do, `/task` Parent-aware mode
   refuses to open sub-issues (`conventions-missing`) rather than create a title without the
   parent. A vendoring project must also list `.claude/scripts/compose_subissue_title.py` in
   its sync configuration's `files` array, or the helper is never delivered. A project whose
   conventions file was built by the doctor must also fill in `issueTitle.effortTypes`, which
   the doctor scaffolds empty, until the follow-up lands (issue #51); an empty list makes every
   effort tag fail `pattern-mismatch`.

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
neither can drift from the other. It carries 575 tests.

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
