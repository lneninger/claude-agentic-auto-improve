# Concept Contract — A /auto-improve-finish-install skill for Quick start steps 4 and 5

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-04
**Requested by:** user
**Status:** implemented
**Work item:** `.claude/work-items/2026-10-04-auto-improve-finish-install-skill.md`

> **Protocol:** filled in by `data-architect`. The lifecycle and the management commands are in `.claude/templates/concept-contract.md`.
>
> **Size note:** this plugin's copy of the template carries no size-budget rule, although the architect brief refers to one. The contract is kept as short as the eight design questions allow.

---

## Business Concept

- **What is this thing, in domain language?**
  `/auto-improve-finish-install` is a guided conversation that takes a consuming project through the two Quick start steps nobody can finish by copying files. **Step 4:** the skill looks at the repository and proposes a value for every slot of the project profile. It shows the evidence for each value, gets one confirmation, and writes only the slots that are still placeholders. **Step 5:** it works out how the plugin reached this project. For a plugin install it checks that the sixteen hooks are ready to load, and it touches no file. For a vendored copy it previews the exact `settings.json` change and writes it only after a yes, with a backup taken first. Every rule that must give the same answer twice lives in one new script, `auto_improve_finish_install.py`, with its own test suite. The skill carries only the conversation. Its name carries the plugin's name, because a user may have several plugins installed and a bare "finish install" could mean any of them.

- **Existing VOCABULARY.md terms that apply:** **Plugin repository**, **Vendored asset** (Universal Vocabulary). The "Project profile" and "Guard rules file" ideas are registered in MECHANISMS.md, not in VOCABULARY.md.

- **New terms proposed for VOCABULARY.md (Universal tier):**
  - **Install mode** — how the plugin's assets reached a consuming project. It takes one of five values. `plugin`: Claude Code's installation record covers this project and the plugin is enabled. `vendored`: the hook files and `hooks.json` sit inside the project's own `.claude/hooks/`. `both`: the two are true at once. `none`: neither is true. `plugin-source`: the project is the plugin's own checkout. It is decided only from files on disk, never from the conversation.
  - **Placeholder slot** — a project-profile slot whose value is still the template's italic prose `*(...)`, or whose row is missing. It is the only kind of slot `/auto-improve-finish-install` may write. A slot that reads `none`, or any other value, is an **authored slot** and is never changed.
  - **Registration key** — the identity of one hook registration, used to decide whether it is already present. It is the event name, the hook file name, and any arguments after the file name. Example: `UserPromptSubmit` + `plain-language-guard.py` + `--carry-forward`. The matcher and the path prefix are deliberately not part of it.

---

## End-User View

**Category:** Getting Started

### What the end user sees
After installing the plugin, the operator types one command in a new project. The assistant then walks through two short stages. In the first, it shows a table of facts about the repository: where the server code lives, where the tests live, where database changes are kept, and which reviewers exist. Each fact sits next to the file or folder that suggested it, and the operator confirms or corrects them all in one reply. In the second stage, it says plainly whether the safety checks are switched on. If they need switching on, it shows exactly what will change and waits for a yes.

### What it does for the end user
Today a new team has to read a long setup guide, fill in a form of eleven facts by hand, and, for a copied setup, edit a configuration file that decides whether the safety checks run at all. A typing mistake in that file can switch every check off without any warning, or block every action. This command does the reading and the careful editing. It never guesses on the team's behalf: any fact it cannot back with something in the repository is left blank or asked about.

### Connections to the rest of the system
It comes after the existing "create what is missing" helper, which makes the folders and blank forms, and that helper now points to this command when it finishes. The facts it writes are the ones the design and delivery flow reads to decide who builds each part of an approved plan. The safety checks it switches on include the approval gate that stops edits without an agreed plan, the database protection checks, and the code-search-first check.

### Implications
On a copied setup, switching the checks on changes how every later session behaves, so the operator must agree to it explicitly. The checks take effect only in a session started after setup; the session that ran the command keeps running without them. On Apple and Linux machines a copied setup is written with the right launch word automatically. An installed plugin cannot be fixed by this command there, because the plugin's own configuration names the Windows launcher; the command says so and offers copying the hooks into the project instead. Only Claude Code runs the safety checks: in Cursor and Codex the command fills in the profile and states that the checks are not available there.

### Measures
It never overwrites a fact the team already wrote. It never names a reviewer or builder who does not exist in the project or the plugin. It always shows the change before making it. It keeps a dated copy of the previous configuration and says how to put it back. It refuses to touch the configuration if the file is damaged, if the setup is installed twice over, or if the file changed between the preview and the yes. Running it a second time changes nothing.

### How it could be improved
It could also fill in the three other per-project files, the area map, the title conventions and the protected-names list, which today stay blank. The database protection check cannot yet be given the project's own database names when the plugin is installed rather than copied, so today it protects only made-up example names. Fixing that needs a change to the check itself.

---

## Data Shapes

All shapes are the script's JSON output and input, so they are value objects rather than entities. Nothing is persisted except the two files the operator approves.

### Entities

| Name | Fields | Invariants | Ownership (aggregate) |
|------|--------|------------|-----------------------|
| Project profile file (existing, `.claude/project-profile.md`) | slot table rows: slot name, value | Every slot the plugin template declares is present after an apply. An authored slot's text survives byte for byte. Text outside placeholder rows is untouched, except the template's leading `**TEMPLATE.**` paragraph, which is replaced by one provenance line. Every written value re-reads through `pr_merged.load_slot` to the confirmed values | the consuming project |
| Project settings file (existing, `.claude/settings.json`) | hooks: event → list of groups(matcher?, hooks[command, args?]); other keys | Unrelated keys and existing registrations survive in meaning and in order. The script never adds a registration key that already exists in any layer; duplicates already present are left untouched and reported. Nothing is written when nothing is missing, so a re-run gives a byte-identical file | the consuming project |

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Evidence | path (project-relative), reason (closed set: `manifest`, `folder-name`, `config-entry`, `file-exists`, `git-remote`, `agent-file`) | the citation beside a proposal |
| SlotProposal | slot, values (list of strings or `none`), basis (`inferred` / `needs-answer` / `kept-authored` / `none-found`), evidence (list of Evidence), note | one row of the step-4 table |
| ProfilePlan | target path, existed (bool), source-sha256, plan-sha256, proposals (list of SlotProposal), rows to fill, rows to add, unified diff, local agents (names present in the project's `.claude/agents/` and absent from the plugin set) | the output of `profile` without `--apply` |
| InstallModeVerdict | mode (closed set: `plugin`, `vendored`, `both`, `none`, `plugin-source`), facts (list of fact name + observed value + path read), enabled (bool or null) | the first section of `hooks` output |
| HookRegistration | event, matcher (or absent), command, registration key | one of the 17 source registrations in `hooks.json` (16 hook files; `plain-language-guard.py` is registered twice) |
| SettingsPlan | target path, source-sha256 (or `absent`), plan-sha256, to-add (list of HookRegistration), already-present (list with layer: user / project / local, and a flag for a different matcher or a foreign path), interpreter (`py -3` or `python3`), disable-all-hooks (bool), unified diff | the output of `hooks` for a vendored project |
| ReadinessReport | install mode, install path, installed version, marketplace-declared version, hooks registered count, unresolved commands, interpreter found (bool), each hook compiles (bool + failures), disable-all-hooks (bool), duplicate vendored registration (bool), kill switches (names read from the hook sources), database-guard rules state (`absent-fail-closed` / `template-placeholders` / `configured`), not-verifiable (fixed list) | the output of `hooks` for a plugin install |
| Refusal | code (closed set below), message naming the reason, path | every stop; always written with nothing changed |

**Refusal codes (closed set):** `project-unreadable`, `template-missing`, `hooks-json-missing`, `hook-file-missing`, `interpreter-not-found`, `malformed-settings`, `unexpected-settings-shape`, `install-mode-both`, `install-mode-none`, `install-record-unreadable`, `plugin-source-checkout`, `plugin-disabled`, `provider-has-no-hooks`, `unknown-slot`, `slot-unanswered`, `slot-already-authored`, `unknown-agent`, `changed-since-preview`, `write-failed`, `plugin-install-needs-no-registration`, `invalid-slot-value`.

### Events

Not applicable. Reason: the script is a single-shot command-line tool with no subscribers. Its outcome is its JSON output and exit code.

### Commands (if any)

| Name (imperative) | Handler | Payload | Possible rejections |
|---|---|---|---|
| ProposeProfile | `auto_improve_finish_install.py profile` | project root | `project-unreadable`, `template-missing`, `plugin-source-checkout` |
| ApplyProfile | `auto_improve_finish_install.py profile --apply` | project root, one `--set slot=value[,value]` per placeholder slot, `--expect-sha256` | `unknown-slot`, `slot-unanswered`, `slot-already-authored`, `unknown-agent`, `invalid-slot-value`, `changed-since-preview`, `plugin-source-checkout`, `write-failed` |
| PlanHooks | `auto_improve_finish_install.py hooks` | project root, platform, provider, Claude home | every install-mode refusal, `hooks-json-missing`, `malformed-settings`, `unexpected-settings-shape`, `provider-has-no-hooks` |
| ApplyHooks | `auto_improve_finish_install.py hooks --apply` | as PlanHooks plus `--expect-sha256`, optional `--skip <hook>` (repeatable) | all of PlanHooks, plus `hook-file-missing`, `interpreter-not-found`, `changed-since-preview`, `write-failed`; refused outright unless the mode is `vendored`, with `plugin-install-needs-no-registration` for a `plugin` install |

### Design decisions behind the shapes (settles the eight design questions)

**1. Slot inference.** The walk skips `.git`, `.claude`, `node_modules`, `bin`, `obj`, `dist`, `build`, `vendor`, `venv`, `.venv` and `__pycache__`, stops at depth 6, and sorts its output so two runs agree.

| Slot | Inferred from | Otherwise |
|---|---|---|
| `project.name` | the repository name in the `origin` remote URL; else the name of the main checkout's folder, read through the git common directory. A worktree folder name such as `20261004-feature-...` is never used | `needs-answer` |
| `backend.roots` | folders holding `*.csproj` (not test projects), `go.mod`, `pom.xml` / `build.gradle*` or `Cargo.toml`; a `pyproject.toml` / `setup.py` folder only when it is not the repository root. A `package.json` dependency such as `express` is never used, because a server-rendered front end carries it too | `none-found` → `none` |
| `frontend.roots` | `angular.json` `projects.*.root` entries; folders holding `vite.config.*`, `next.config.*`, `nuxt.config.*` or `svelte.config.*` | `none-found` → `none` |
| `frontend.theme-polarity` | never inferred | `needs-answer` per frontend root; `none` when `frontend.roots` is `none` |
| `test.roots` | `*.Tests.csproj` / `*Tests.csproj` folders; folders named `tests`, `test`, `__tests__` or `spec` that hold source files; `testpaths` in `pyproject.toml` | `none-found` → `none` |
| `migration.root` | a `Migrations` folder holding `*.cs`; `alembic/versions`; `prisma/migrations`; `db/migrate`; `src/main/resources/db/migration`; `migrations` folders beside a Django `manage.py` or a knex config. Several candidates → `needs-answer` listing them | `none-found` → `none` |
| `auth.roots` | folders named `Auth`, `auth`, `Authentication`, `Identity` are listed as candidates and offered to the operator; a folder name is a guess, so the basis is `needs-answer`, never `inferred` | `none-found` → `none` |
| `safety-critical.roots` | never inferred | `needs-answer`; `none` if the operator gives nothing |
| `review.documents` | root files that exist: `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `TESTING*.md`, `ARCHITECTURE.md` | `none-found` → `none` |
| `implementers`, `review-gates` | `none` (accept the plugin's own) when the project's `.claude/agents/` holds no agent outside the plugin set. When it does, each local agent is listed as `needs-answer`, with no role assigned | — |

**Written form and unanswered slots.** Every written value is a list of backticked entries separated by commas, or the word `none`, so `load_slot` reads it back. `ApplyProfile` needs one `--set` per placeholder slot. Where the operator gives nothing for a slot that is never inferred, the skill passes `none` explicitly, so `slot-unanswered` is raised only if the skill forgot to ask. A per-root theme polarity is written as one entry per root in the form `<root>=<polarity>`, because `load_slot` returns a flat list.

**The agent rule.** A name is valid only if `<name>.md` exists in the project's `.claude/agents/`, the plugin's `agents/`, or the plugin's `.claude/agents/`. Any other name is refused with `unknown-agent` before anything is written. **Filling a role slot replaces the plugin defaults; it does not add to them.** `load_slot` returns the listed names, and `DEFAULT_IMPLEMENTERS` applies only when the slot is empty (`pr_merged.py:141-159`). So when a role slot is filled, the proposal is the plugin defaults for that role plus the local agents the operator assigns to it. Writing only the local names would make every plugin agent unrecognised.

**The never-overwrite rule (a refinement of the brief).** The script reads slot names from the plugin template's table, never from a list of its own, so a slot added to the template later flows through automatically. Placeholder slots are filled. Missing rows are appended to the table. An authored slot is never changed: a `--set` on one is refused with `slot-already-authored`, and a proposal that differs from it is reported as advice only. This is what lets the documented order work, where `plugin_doctor.py --fix` first scaffolds a profile full of placeholders and `/auto-improve-finish-install` then fills it.

**2. Install mode.** It is decided from facts on disk, and each fact is reported with the path that was read.
- **Installed:** `<claude-home>/plugins/installed_plugins.json` has a key `agentic-auto-improve@<any>` with an entry whose `scope` is `user`, or whose `scope` is `project` / `local` and whose `projectPath` matches the project root (paths normalised; case ignored on Windows). The entry's `installPath` must also exist. `<claude-home>` is `--claude-home`, else `CLAUDE_CONFIG_DIR`, else `~/.claude`.
- **Several plugins installed:** the script reads only entries whose key starts with `agentic-auto-improve@` and ignores every other plugin, in the installation record, in `enabledPlugins` and in the settings hooks. If this plugin is installed from more than one marketplace, the entry whose `installPath` contains the running script is used; if none matches, the refusal is `install-record-unreadable`, naming both entries. Another plugin's hook files are never touched, and another plugin's registration counts as present only when its registration key matches exactly.
- **Enabled:** `enabledPlugins["agentic-auto-improve@<mkt>"]` is read from user, then project, then local settings, and the most specific layer wins. A plugin that is installed but has no `enabledPlugins` entry in any layer the script can read is reported as not enabled, and the message says that managed settings and `--settings` are not read.
- **Vendored:** the project's `.claude/hooks/concept-gate.py` exists. The project's own `hooks.json` is not required, because the sync never delivers it to a consumer.
- **Plugin source:** the project root's `.claude-plugin/plugin.json` names `agentic-auto-improve`.

The verdict is one of `plugin`, `vendored`, `both`, `none` or `plugin-source`. **Precedence:** `plugin-source` is tested first and stops everything; then `both`, `plugin`, `vendored`, `none`. A record file that exists but cannot be read, parsed or recognised is refused as `install-record-unreadable`, never reported as `none`. `hooks-json-missing` applies when neither the project's nor the plugin's `hooks.json` can be found. A plugin install that is not enabled is refused as `plugin-disabled`, unless the project also has a vendored copy: then the verdict is `vendored`, because a plugin switched off for this project cannot duplicate the hooks. Every mode except `plugin` and `vendored` stops with its named refusal and writes nothing. `both` stops because every hook would run twice; the message names the two facts and says to remove one of them.

**3. Vendored merge.** The steps run in this order:
1. **Source and text changes.** The source is the project's own `.claude/hooks/hooks.json` when it exists, otherwise the plugin's `hooks.json` found by the plugin-root lookup in decision 5; it is never read from a path the script guessed. Each registration is written in the `command` + `args` form that a real consumer already uses (`command` is `py` with `-3` as the first argument, or `python3`; the hook path is an argument, `${CLAUDE_PROJECT_DIR}/.claude/hooks/<file>`), not the string form, because nobody has shown that the string form expands the variable. On a host where the platform is not `win32`, the launcher `py` with its `-3` argument becomes `python3`. `--platform` overrides the platform for tests.
2. **Shape check.** The target is parsed as strict JSON. A parse failure is refused as `malformed-settings`, naming the line and column. The same refusal applies to a user or local settings file that exists but cannot be parsed, because its registrations would otherwise be invisible and duplicates would be added. An unreadable file (permissions, a lock) is refused as `project-unreadable` on a read and `write-failed` on a write, never a crash. A top level that is not an object, a `hooks` value that is not an object, or an event that is not a list is refused as `unexpected-settings-shape`.
3. **Presence check.** A source registration is present if any hook under the same event, in the user, project or local settings, has the same registration key. Both the string form and the `command` + `args` form are recognised. A match with a different matcher or a foreign path is reported, never added. The report names the coverage gap this can hide, for example the plugin's database guard matching no `PowerShell` tool.
4. **Appending.** A missing registration is appended to the existing group with the identical matcher, or to a new group at the end of that event's list. Existing order is preserved.
5. **Output format.** The file is read as UTF-8; a byte order mark is tolerated and written back. The line ending and the indent width are detected from the file and reused (two spaces and a line feed only for a new file). Insertion order and non-ASCII text are kept, and there is a trailing newline. Duplicate keys at any level are refused as `malformed-settings`, because a standard parser would drop one silently. The file is re-serialised, so the preview diff can show reflowed lines as well as the added registrations; meaning is kept, and the diff is exactly what will be written.
6. **Nothing to add.** If nothing is missing, the script writes nothing: no backup, no rewrite.
7. **Apply checks.** The preview reports a `plan-sha256`: a SHA-256 over the settings file bytes (or the word `absent`), the planned output bytes, and the sorted `--skip` list. `--apply` requires `--expect-sha256` equal to it, so a changed flag, a changed settings layer or a changed source `hooks.json` between preview and apply is refused as `changed-since-preview`. The operator never confirms one change and receives another. Every referenced hook file must exist; otherwise `hook-file-missing`, because a missing script exits 2 and blocks every tool call. The interpreter must be found on PATH; otherwise `interpreter-not-found`, because a missing program fails open silently.
8. **Writing.** The backup goes to `.claude/settings.json.bak-<UTC yyyymmddTHHMMSSZ>`, and an existing backup is never overwritten. A same-second collision adds a numeric suffix. The write goes to a temporary file in the same folder, then is renamed into place. If the rename fails (for example another program holds the file), the temporary file and the backup this run created are removed, the original is untouched, and the refusal is `write-failed`. The skill tells the operator to add `.claude/settings.json.bak-*` to `.gitignore`.
9. **Rollback.** Rollback is copying the backup back. The skill prints that one-line command.

`--skip <hook>` leaves named hooks out. The README already invites a vendoring user to "register only the hooks you want".

**4. "Live" for a plugin install.** The script reports **ready to load** and never claims **live**. It verifies:
- the installation record and the enabled flag;
- that the install path's `.claude-plugin/plugin.json` `hooks` field resolves;
- that all 17 registrations resolve to files under the install path;
- that the launcher named by the commands (`py`) is found on PATH;
- that every hook file compiles, checked in memory with no `.pyc` written;
- that `disableAllHooks` is not true in any layer;
- that the project's `settings.json` does not register the same keys a second time;
- that the installed version matches the version the local marketplace clone declares.

It then reports four more things: the environment variables, read from the hook sources by the pattern `environ.get("CLAUDE_...")` (excluding `CLAUDE_PROJECT_DIR`), where most are kill switches and two are an approval pin and a one-shot approval; the gate list; the database-guard rules state; and a plain note that the code-search-first check blocks source reads until a CodeGraph tool has run, has no bypass when no CodeGraph index exists, and is silenced for one session by `CLAUDE_SKIP_CG=1`.

The `not-verifiable` list is fixed and always printed:
- that the running session loaded the hooks (a session started before install or enable runs without them);
- that a project-scope trust prompt was accepted;
- that a hook's imports of its sibling helpers succeed at run time.

Under a plugin install on macOS or Linux the cached `hooks.json` launches `py -3`, so the report says not ready and says plainly that this command cannot fix it. The options it names are to copy the hooks into the project instead, or to wait for a per-platform hooks format. The skill closes with a first-session check for the operator. In a new session, an edit to a source file with no approved contract should be blocked by the concept gate.

**5. Script, not doctor extension.** The new script is `.claude/scripts/auto_improve_finish_install.py`. Its two subcommands are `profile` and `hooks`. Its flags are `--project`, `--json`, `--apply`, `--expect-sha256`, `--set`, `--skip`, `--platform`, `--provider claude|cursor|codex` and `--claude-home`. Exit codes: `0` for a plan produced, an apply done, or nothing to do; `2` for a refusal the operator can correct; `3` for an environment problem (`project-unreadable`, `template-missing`, `hooks-json-missing`). It reuses `find_plugin_root` from `plugin_doctor.py`, and `load_slot`, `DEFAULT_IMPLEMENTERS` and `DEFAULT_REVIEW_GATES` from `pr_merged.py`, by import. Both are siblings in `.claude/scripts/` under either install mode, so the imports work in both. The skill resolves the script with an explicit ordered test (the vendored path, then `$CLAUDE_PLUGIN_ROOT`, then the provider cache with the newest version first) rather than copying `/advance`'s `ls` of three paths, because `ls` sorts its operands and does not keep the stated order. If none is found it stops and says so. It runs `py -3` on Windows and `python3` elsewhere.

**6. Providers.** On Cursor and Codex the skill runs step 4 in full, because the profile is provider-neutral. For step 5 it runs `hooks --provider cursor|codex`, which returns `provider-has-no-hooks`. It then says hooks are Claude-only in this release and writes nothing.

**7. Version and README.** The version goes from `0.2.2` to **`0.3.0`** in all five declarations (`plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` twice, `.cursor-plugin/plugin.json`), because a new user-facing skill is a feature. The README changes are:
- Quick start steps 4 and 5 become "run `/auto-improve-finish-install`", with the by-hand text kept as the fallback.
- The "21 skills" count changes in both places it appears, and `auto-improve-finish-install` is added to the Skills list.
- The scripts and suites counts are **recounted from the tree**. They are already stale: the tree holds 13 workflow scripts and 8 suites against the stated 12 and 7, and after this change it holds 14 and 9.
- The "eleven skills cite scripts" count is recounted.
- The kill-switch table is completed. It lists 6 variables, while the hooks read 12. `/auto-improve-finish-install` reports all 12, and the two must agree.
- The "Let the doctor" section points at `/auto-improve-finish-install`.
- The two statements this contract proved false are corrected in `README.md`: that an unconfigured install treats every database as protected, and that the code-search-first check bypasses itself when no CodeGraph index exists. The matching comment in `.claude/hooks/hooks.json` is corrected too (comment text only, no behaviour change).
- The stale test count for `test_pr_merged.py` is recounted from the suite.

**8. Test plan** (for `/tdd-first`; every case must fail first on an assertion, not on a missing import). The suite is `.claude/scripts/tests/test_auto_improve_finish_install.py` in `unittest` style, and every case uses a temporary directory and a fake Claude home. The first commit adds the module with every function returning an empty or `not-implemented` result, so each test fails on an assertion and not on an import.

- **Inference:**
  - each slot's evidence rule finds its marker, and finds nothing in an empty repository;
  - a worktree folder name is not used as `project.name`;
  - excluded folders are skipped;
  - two runs give identical output.
- **Profile apply:**
  - placeholder rows are filled and authored rows are kept byte for byte, with a positive control that changes an authored row by hand and shows the comparison catches it;
  - a missing row is appended;
  - `slot-already-authored`, `slot-unanswered`, `unknown-slot` and `unknown-agent` are refused with no file change;
  - a role slot keeps the plugin defaults;
  - the written file re-reads through `pr_merged.load_slot`.
- **Install mode:**
  - each of the five verdicts comes from a fake record and tree;
  - user scope versus project scope, with a case-different path on Windows;
  - an enabled flag overridden by a more specific layer gives `plugin-disabled`;
  - two other plugins installed beside this one change no verdict, and a second marketplace copy of this plugin is resolved by the script's own location.
- **Merge:**
  - the first run adds 17 registrations;
  - a second run writes nothing, so the file's bytes and modification time are unchanged and no backup exists;
  - unrelated keys and a user's own hook survive;
  - an existing registration with a different matcher, or in the local or user layer, is not duplicated;
  - the `command` + `args` form is recognised as present;
  - the `plain-language-guard` pair stays two distinct keys;
  - `--skip` works.
- **Swap:**
  - `linux` and `darwin` produce `python3` and `win32` keeps `py -3`;
  - `${CLAUDE_PLUGIN_ROOT}` never survives, with a positive control that plants one and shows the check fails.
- **Safety:**
  - a backup is created before the write and is equal to the old bytes;
  - a second backup does not overwrite the first;
  - the `malformed-settings`, `unexpected-settings-shape`, `hooks-json-missing`, `hook-file-missing`, `interpreter-not-found` and `changed-since-preview` refusals each leave the directory tree byte-identical;
  - declining, meaning a plan with no `--apply`, writes nothing, with a positive control that runs the same command with `--apply` and shows the tree changes;
  - each refusal assertion pairs the unchanged tree with an assertion on the refusal code and the exit code, so it cannot pass against a script that does nothing;
  - the refusals with no earlier test are each covered: `project-unreadable`, `template-missing`, `provider-has-no-hooks`, `install-record-unreadable`, `plugin-source-checkout`, `write-failed`, `changed-since-preview` on the profile apply, and `hooks --apply` under a `plugin` mode;
  - exit code `2` versus `3` is asserted for one refusal of each class.
- **Readiness:**
  - an unresolved command, a hook that does not compile, `disableAllHooks`, a version mismatch and a missing launcher are each reported;
  - the database rules state takes all three values.
- **Others:**
  - doctor: the settings line and the profile line name `/auto-improve-finish-install` (in `test_plugin_doctor.py`);
  - manifests: a new INV-11 checks that the version is identical in all five declarations, and a new INV-12 checks that the README's environment-variable table agrees with the variables the hook sources read (in `test_plugin_manifests.py`);
  - `load_slot` (in `test_pr_merged.py`): an unfilled `frontend.theme-polarity` row reads as unfilled, and a missing row never returns the worked-example values.

---

## Reused Mechanisms

- **Project profile** (MECHANISMS.md, Universal) — consumed as-is. Values are written into the existing slot table. Slot names are read from the template, so no slot list is duplicated. The parser is `pr_merged.load_slot` (`.claude/scripts/pr_merged.py:69`), imported rather than re-implemented. **This change fixes two defects in it** (the critic's second blocker): it tests for the template's placeholder prose before it takes backticked values, and a missing slot row never falls through to the worked-example block. The fix ships with its own tests in `test_pr_merged.py`.
- **Guard rules file** (MECHANISMS.md, Universal) — consumed read-only, to report the database guard's real state. The fail-direction rule in that entry is what makes the `template-placeholders` state worth reporting.
- **`plugin_doctor.find_plugin_root`** (`.claude/scripts/plugin_doctor.py:125`; not a registered mechanism) — consumed for its `$CLAUDE_PLUGIN_ROOT` and cache lookups only. Its first check, the script's own grandparent, returns a vendored project itself, so the new script wraps it: a root equal to the project is never accepted as the plugin template source, and neither is a project that is itself the plugin's own checkout (its `.claude-plugin/plugin.json` names `agentic-auto-improve`, the `plugin-source` fact of decision 2). A separate plugin root, which carries that same manifest, is accepted. After the project is rejected the lookup continues to `CLAUDE_PLUGIN_ROOT`, then the script's own location, then the provider cache under the given Claude home only, newest version first; it never stops at the first candidate. The cache is searched under `--claude-home` or `CLAUDE_CONFIG_DIR` when either is given, and under `~/.claude` only when neither is. A candidate must carry a `.claude-plugin/plugin.json` that names `agentic-auto-improve`, so another plugin's tree is skipped even when `CLAUDE_PLUGIN_ROOT` points at it. The root that was chosen is reported in the result (`plugin-root`), and the skill shows it to the operator. When no separate plugin root exists, slot names come from the project's own profile table and missing-row detection is reported as unavailable. `template-missing` applies only when neither source exists.
- **The `/advance` script-resolution idiom** (`skills/advance/SKILL.md:43-49`; README "What each provider actually gets") — consumed as-is, as the README tells new skills to do.
- **Two-layer Claude path resolution** (MECHANISMS.md) — deliberately **not** used, and its rule is respected. The script locates nothing through `claude_roots()`, because it addresses an explicit `--project`. The one home-directory read is Claude Code's machine-level installation record and user settings. These are not repository data, and the read is redirectable through `--claude-home` / `CLAUDE_CONFIG_DIR`, so a test never touches the real home directory.

## New Mechanisms (if any)

- **Name:** Preview-hash apply (`auto_improve_finish_install.py`)
- **Purpose:** to change a user-owned configuration file only in the exact state the operator was shown. Each apply has a dry-run diff, a SHA-256 of the previewed bytes, a refusal on mismatch, a timestamped backup, an atomic replace, and no write when nothing changes.
- **Why an existing mechanism was not sufficient:** `plugin_doctor.py` is built on "never write `settings.json`", and a test pins that rule (`test_settings_is_manual_and_never_written`). Its only write path is creating a file that is absent. It has no preview, no backup and no consent step. Folding a consented edit of an existing file into it would invert a tested rule of that tool, rather than extend it. `pr_merged.py` writes only its own state stores. No registered mechanism edits a file the operator owns.
- **Proposed location:** `.claude/scripts/auto_improve_finish_install.py`
- **Extension seam:** the follow-up for step 3 (`.claude/concepts/followups/2026-10-04-auto-improve-finish-install-step3-inference.followup.md`) adds a subcommand that reuses the same plan / apply / refusal shapes.
- **Will this be promoted to `MECHANISMS.md` after implementation?** decide-at-review

---

## Extension Points

- `skills/auto-improve-finish-install/SKILL.md` — a new skill directory at the plugin root. All three providers discover it from there, with no manifest change (INV-5 and INV-6 of `test_plugin_manifests.py`).
- `plugin_doctor.py` — the `Requirement.why` text for `.claude/settings.json` and for the project profile name `/auto-improve-finish-install`, and so does the `left alone` line. The `NEEDS YOU` line is shared by three files and is not repointed. The message text changes only; the rules do not.
- `test_plugin_manifests.py` — a new INV-11 checks that the version is identical in all five declarations.
- The README sections listed in Design decision 7.

## Integration Surfaces

`.claude/registries/INTEGRATION.md` does not exist in this repository, so no surface map was available. The surfaces are traced by hand:

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---|---|---|---|---|
| `skills/auto-improve-finish-install/SKILL.md` | `auto_improve_finish_install.py` | command line, `--json` | ProfilePlan, InstallModeVerdict, SettingsPlan, ReadinessReport, Refusal | skill → script → skill |
| `auto_improve_finish_install.py` | project `.claude/project-profile.md` | file write | Project profile file | script → project |
| `auto_improve_finish_install.py` | `pr_merged.py` (`load_slot`) | Python import | profile text | script → script |
| `auto_improve_finish_install.py` | project `.claude/settings.json` (+ local, user) | file read; write to project only | Project settings file | both |
| `auto_improve_finish_install.py` | `<claude-home>/plugins/installed_plugins.json` | file read | installation record (`version: 2`, `plugins.<name>@<mkt>[]` of scope / projectPath / installPath / version) | read only |

**Changes to existing integration surfaces:** none. There is no REST, SignalR or DTO surface.

## Adjacent Areas

Not applicable. Reason: the cross-area scan was **not run**. This agent has no shell, so it cannot execute `cross_area_scan.py`. The scan would also return nothing here, because the plugin's `.claude/area-mapping.json` has an empty `areas` set. Two follow-ups were noticed by hand and anchored: `.claude/concepts/followups/2026-10-04-db-guard-rules-under-plugin-install.followup.md` and `.claude/concepts/followups/2026-10-04-auto-improve-finish-install-step3-inference.followup.md`. Both carry `**Issue:** pending`.

## UI Implications

Not applicable. Reason: there is no frontend consumer. The plugin has no application UI, and `frontend.roots` is a placeholder in its own template profile.

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

## Non-Goals

- Quick start step 3: area map, title conventions, token list (see the follow-up).
- Step 6: the sync configuration, and any contribution back to the plugin.
- Any change to a hook's behaviour. This includes making the database guard configurable under a plugin install (see the follow-up).
- Hook registration for Cursor or Codex, and a per-platform branch in `hooks.json`.
- Mirroring the skill into any consuming repository.
- A rollback flag. Rollback is a one-line copy of the printed backup.

## Where this contract departs from the brief

Each item complies with the brief where the brief is true, and states where the code says otherwise.

1. **"The database guards fail closed."** This is false as a blanket statement. The guard fails closed only when its rules file is missing or empty (`db-destructive-guard.py:305-343`). The shipped rules file names `AcmeApp` and `AcmeApp_Testing`, so under a plugin install, and under an unedited vendored copy, its per-name write protection covers only those fictional names. The generic drop/truncate bank still applies to any database name without a disposable suffix. `/auto-improve-finish-install` reports the real state, one of three, instead of the brief's sentence.
2. **"Confirms the sixteen hooks are actually live."** Nothing outside a running session can observe that. The script reports **ready to load**, lists exactly what it verified and what it could not, and hands the operator a first-session check. On this workstation, the installed copy is `0.2.0` while the repository declares `0.2.2`, and this design session ran `0.2.0`'s hooks. That is the drift the version check exists to show.
3. **"An existing profile is never overwritten."** This is refined to: authored slots are never changed, and placeholder slots are filled after the diff and one confirmation. A literal reading would dead-end the documented order, because `plugin_doctor.py --fix` always creates the profile first.
4. **"Sixteen hooks"** means 16 hook files and **17 registrations**, since `plain-language-guard.py` is registered on two events. The idempotence key carries arguments for that reason.
5. **`$CLAUDE_PROJECT_DIR`** is written as `${CLAUDE_PROJECT_DIR}`: the same variable, in the braced form the source already uses and that a consuming project's `settings.json` already uses.
6. **README counts and the kill-switch table were already wrong before this change** (13/8 against 12/7; 6 of 12 variables). The implementer recounts them; adding one to each would only carry the error forward.

## Confidence

Confidence: Medium. High on the merge, the refusals and the profile round-trip, all verified against `hooks.json`, `pr_merged.py` and `plugin_doctor.py`. Medium on install-mode facts, where the record schema was verified on one workstation but layer precedence and `CLAUDE_CONFIG_DIR` were not verified. The variable-expansion risk is removed from the default path by writing the `command` + `args` form, which still needs the implementer's proof run.

## Alternatives Considered & Why Rejected

- **Option A (chosen):** a new `auto_improve_finish_install.py` with plan/apply subcommands, plus a conversational skill.
  - Why: it keeps the doctor's tested "never write settings" rule intact, and it puts every deterministic rule under a test suite.
- **Option B (rejected):** extend `plugin_doctor.py` with `--profile` and `--hooks`.
  - Why rejected: it inverts a rule the doctor's suite pins, and it mixes "create what is absent" with "edit what the operator owns" in one tool whose README promise is that it never does the second.
- **Option C (rejected):** the skill alone, with the model inferring and editing JSON by itself.
  - Why rejected: idempotence, byte preservation and the interpreter swap would be redone by judgement on every run, and nothing could test them. That is the defect the brief's script criterion exists to prevent.

## Uncertain Assumptions

- `VERIFIED via .claude/hooks/hooks.json`: 17 registrations, 16 distinct files, all in the `py -3 "${CLAUDE_PLUGIN_ROOT}/..."` string form.
- `VERIFIED via .claude/scripts/pr_merged.py:69-159`: a filled role slot replaces the defaults. `CORRECTED at critique`: `load_slot` takes backticked values before it tests for placeholder prose (`:88-91`), so it misreads an unfilled `frontend.theme-polarity` row, and a missing row falls through to the worked example. This change fixes both.
- `VERIFIED via C:\Users\lneni\.claude\plugins\installed_plugins.json`: the record has `version: 2`, entries keyed `<name>@<marketplace>`, and fields `scope` (`user` / `project`), `projectPath`, `installPath`, `version`.
- `VERIFIED via this session's hook banner`: Claude Code expands `${CLAUDE_PLUGIN_ROOT}` inside a string-form command on Windows.
- `ASSUMED`: Claude Code also expands `${CLAUDE_PROJECT_DIR}` inside a string-form command, not only in `args`. It matters because an unexpanded path would make every hook a missing-file exit 2. Verification path: the implementer checks the Claude Code hooks documentation (context7). **Resolved at approval:** the merge always emits the `command` + `args` form, so the default path no longer relies on this assumption. The implementer still proves, with one harmless hook invocation, that the `args` form runs before the code depends on it. **VERIFIED at implementation (2026-10-04) via the Claude Code hooks documentation, https://code.claude.com/docs/en/hooks, section "Exec form and shell form":** when `args` is set the hook runs in exec form, `command` is resolved as an executable on `PATH` and spawned directly with no shell, and `${CLAUDE_PROJECT_DIR}` is substituted into each `args` element as a plain string wherever the hook is defined; the documentation recommends this form whenever a hook references a path placeholder. On Windows `command` must be a real executable, which `py` (`py.exe`) is. The documentation therefore stands in for the proof run, and this assumption is closed.
- `ASSUMED`: settings precedence for `enabledPlugins` and `disableAllHooks` runs local over project over user, with managed settings ignored. Verification path: the Claude Code settings documentation.
- `ASSUMED`: Claude Code honours `CLAUDE_CONFIG_DIR` for the plugins folder. The `--claude-home` flag makes this harmless for tests either way.
- `ASSUMED`: `$CLAUDE_PLUGIN_ROOT` is set in a skill's shell. The `/advance` idiom's cache-glob fallback covers the case where it is not.

## Failure Modes & Mitigations

- **FM:** A registered command points at a missing file, and every tool call is blocked with exit 2.
  - **Mitigation:** the pre-write `hook-file-missing` refusal.
- **FM:** The interpreter is absent, and every hook fails open silently.
  - **Mitigation:** the `interpreter-not-found` refusal for vendored installs; for plugin installs, the readiness report says "not ready".
- **FM:** The file changed between preview and yes.
  - **Mitigation:** the `--expect-sha256` refusal.
- **FM:** Duplicate registration through the plugin plus a vendored copy, or through another settings layer.
  - **Mitigation:** the `install-mode-both` refusal, plus the cross-layer registration key.
- **FM:** A wrong agent name halts every later contract loop.
  - **Mitigation:** the `unknown-agent` refusal, plus the defaults-preserving role proposal.
- **FM:** The cache glob picks an older plugin version.
  - **Mitigation:** older versions do not contain `auto_improve_finish_install.py`, so `ls` skips them. The readiness version check reports the drift.
- **FM:** The operator believes the database is protected when it is not.
  - **Mitigation:** the rules state is reported as one of three values, never as a slogan; follow-up stub.
- **FM:** The first consumer, StockToolScalpingMachine, is a live `both` case today: its `settings.json` registers the hooks while the plugin is enabled at user scope, so every hook runs twice.
  - **Mitigation:** the `install-mode-both` refusal names it. Removing one of the two registrations is that repository's decision and is outside this change.

## Open Questions for User

- [x] **Accept the six departures from the brief listed above?** The three that change behaviour are reporting "ready to load" instead of "live", reporting the database guard's real rules state, and filling placeholder slots instead of refusing any existing profile. **Recommendation: accept all six.** Each one follows from code cited in that section, and the alternative is a skill that tells the operator something false on its first run.
  → **Answer (user, 2026-10-04, "approve as recommended"):** accepted, all six.

> **Clarifications recorded at the test review, 2026-10-04 (no change of intent, so no re-approval).** The pre-implementation test review found two gaps in the wording. (1) The closed refusal set had no code for `hooks --apply` under a `plugin` install, which must never write; the code is `plugin-install-needs-no-registration` (exit class `2`). (2) Decision 1's template-source rule is read as: the project itself, or a project that is the plugin's own checkout, is never the template source; a separate plugin root is accepted. Both follow from decisions 2 and 3 as approved.
>
> **Second round, after the post-implementation reviews (2026-10-04).** The code review and the test review found three defects and some smaller gaps. The contract now states: a copied-in project reaches the merge by falling through to `CLAUDE_PLUGIN_ROOT` and the cache for the plugin's `hooks.json`; a disabled plugin plus a vendored copy is `vendored`, not `both` (decision 2); the preview reports a `plan-sha256` that binds the planned change, so `--skip` given only at apply time is refused (decision 3, step 7); `--set` values with a newline, a pipe or a backtick are refused as `invalid-slot-value`; agent names are matched with exact case; the readiness report carries `mode`; a failed write removes the backup it created; and an unreadable or malformed settings file in any layer is a named refusal, not a crash. None of this changes intent, so there is no re-approval.
>
> **Third round, after the second review pass (2026-10-04).** The second pass found no blocker and six warnings, and the contract now states: the profile plan also reports a `plan-sha256` (over the profile bytes or `absent`, and the planned output bytes), and the profile apply requires it, so a template that changes between preview and apply is refused as `changed-since-preview`; the cache lookup is confined to the given Claude home and never reads the real `~/.claude` when another home is named; a candidate plugin root must carry this plugin's manifest and the chosen root is reported; a settings file that is a symbolic link is refused as `write-failed` with a message saying so, and is never written through or over; readiness and mode detection read every settings layer strictly, so a malformed layer is `malformed-settings` naming that file and a layer of the wrong shape is `unexpected-settings-shape`, on the plugin path as on the vendored one. No new refusal code is added.

## Critique

**Critic:** contract-critic
**Date:** 2026-10-04
**Verdict:** blockers-found

> **Scope of this pass.** This repository's `JOURNAL.md` has no entries and no `INTEGRATION.md` or north-star register exists. So most findings cite code, the registered mechanisms in `MECHANISMS.md`, and the template. Where a finding relies on the first consuming repository (`D:\Dev\HIPALANET\StockToolScalpingMachine`), that repository was read only, as evidence of how a real consumer looks. None of its registries are cited as this project's.
>
> **The six departures from the brief, checked against the code.** Departure 1 is true: `db-destructive-guard.py:305-343` fails closed only when `protected_databases` is empty, and the shipped rules file names `AcmeApp` and `AcmeApp_Testing` (`db-destructive-guard.rules.json:10-13`). Departure 2 is honest. Departure 3 is not really a departure, since the brief itself says "shows the difference and asks". Departure 4 is true: `hooks.json` carries 17 registrations over 16 files. Departure 6 is true: the tree holds 13 workflow scripts and 8 suites, and the hooks read 12 distinct `CLAUDE_*` variables apart from `CLAUDE_PROJECT_DIR`. Departure 5 is only half true; see the first blocker.

### Findings

- **[BLOCKER] The `${CLAUDE_PROJECT_DIR}` assumption can lock every tool call, and the declared mitigation cannot see it**
  - **What is wrong:** if Claude Code does not expand `${CLAUDE_PROJECT_DIR}` inside a string-form command, Python is handed a literal path and exits with code 2, which blocks every tool call. The `hook-file-missing` pre-check tests the path the script itself expanded, so it passes. The fallback form the TASK block prescribes (`command` + `args`) is equally unverified. The only consumer using it registers every hook that way (`StockToolScalpingMachine/.claude/settings.json:119-121`). In this critic's own session, the single observed block came from the plugin's string-form copy at `0.2.0`, not from that file's `args`-form copy at `:141-147`. Departure 5's support, "the braced form ... a consuming project's `settings.json` already uses", is true only inside `args`.
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md:268`, which lets an implementer flip an `ASSUMED` item, but this one decides whether the write bricks the session. `README.md:304-307` also prescribes `$CLAUDE_PROJECT_DIR` without evidence that it expands.
  - **Where in this contract:** `## Uncertain Assumptions` — "`ASSUMED`: Claude Code also expands `${CLAUDE_PROJECT_DIR}` inside a string-form command"; `## Failure Modes & Mitigations` — "Mitigation: the pre-write `hook-file-missing` refusal".
  - **→ Addressed by: the merge always writes the `command` + `args` form, so the default path no longer depends on string-form expansion (decision 3, step 1). The implementer proves the `args` form runs before relying on it, and says how in the pull request.**

- **[BLOCKER] The `load_slot` row marked VERIFIED is false, and the reused parser misreads two kinds of profile row**
  - **What is wrong:** `pr_merged.py:88-90` takes backticked values before the italic-placeholder test at `:91` is ever reached. The template's `frontend.theme-polarity` placeholder contains backticks (`project-profile.md:29`), so `load_slot` returns `light`, `dark`, `both` for an unfilled slot. If the slots-table row is missing, `re.search` falls through to the "Worked shape" block (`project-profile.md:61-65`) and returns the `AcmeApp` / `acme-*` example values. With `load_slot` as "the parser", the one slot the contract says is "never inferred" is classified `kept-authored` and its `--set` is refused as `slot-already-authored`. `README.md:372-374` ("the machinery reads each slot as unfilled") is false for that slot today.
  - **Prior artifact ignored:** `MECHANISMS.md:56` (Project profile: an empty slot must read as empty); `.claude/templates/concept-contract.md:109` (do not mark a mechanism "consumed as-is" when a check fails).
  - **Where in this contract:** `## Uncertain Assumptions` — "`VERIFIED via .claude/scripts/pr_merged.py:69-159`: `load_slot` treats `*(` and `none` as empty"; `## Reused Mechanisms` — "The parser is `pr_merged.load_slot` ... imported rather than re-implemented".
  - **→ Addressed by: `load_slot` is fixed at the source in `pr_merged.py` (placeholder test before backticks; a missing row never reaches the worked example), with its own RED tests; the VERIFIED line is corrected. `pr_merged.py` and `test_pr_merged.py` join Files to touch.**

- **[BLOCKER] `find_plugin_root`, reused as-is, returns the consuming project itself under a vendored install**
  - **What is wrong:** `plugin_doctor.py:134-143` tries the script's own grandparent first, and accepts it if `.claude/templates/concept-contract.md` exists. A vendored project has that file (`README.md:279-280`). So under the vendored mode, "the plugin template" is the very profile being filled. A missing row can never be detected, and every vendored agent counts as a plugin agent, so the "local agents" list is always empty. In the plugin's own checkout the same collapse happens. `ProposeProfile` and `ApplyProfile` carry no `plugin-source-checkout` refusal, so `/auto-improve-finish-install` run here would overwrite the shipped template's `**TEMPLATE.**` paragraph and placeholders.
  - **Prior artifact ignored:** `MECHANISMS.md:56` ("Blank template ships in the plugin at the same path"); `.claude/templates/concept-contract.md:109`.
  - **Where in this contract:** `## Reused Mechanisms` — "`plugin_doctor.find_plugin_root` ... consumed as-is"; `### Commands` — ProposeProfile / ApplyProfile rejection columns.
  - **→ Addressed by: the project itself, or a checkout naming `agentic-auto-improve`, is never accepted as the template source; `plugin-source-checkout` now applies to both profile commands; with no separate plugin root, slot names come from the project's own table and missing-row detection is reported unavailable.**

- **[BLOCKER] The vendored mode requires a file the sync deliberately never delivers**
  - **What is wrong:** vendored detection requires `.claude/hooks/hooks.json`, and the merge source is "the project's own vendored `hooks.json`, never the plugin cache". The sync configuration declares that file `plugin_only`, because a consumer registers hooks in `settings.json` instead (`StockToolScalpingMachine/.claude/.sync-config.json:239-243`). That repository has no `.claude/hooks/hooks.json`. So the plugin's only sync-maintained consumer never reads as `vendored`. And `hooks-json-missing` can never fire in the vendored mode it exists for, because detection already demanded the file. The brief's failure-path criterion "a missing `hooks.json` ... stop with a named reason" is answered by `install-mode-none` instead.
  - **Prior artifact ignored:** `MECHANISMS.md:44` (Plugin registry ownership model) and `MECHANISMS.md:46` (Bidirectional sync), which govern what a consumer receives.
  - **Where in this contract:** `### Design decisions` item 2 — "**Vendored:** both the project's `.claude/hooks/hooks.json` and `.claude/hooks/concept-gate.py` exist"; item 3 step 1.
  - **→ Addressed by: vendored is detected by `concept-gate.py` being present; the merge source is the project's `hooks.json` if it exists, otherwise the plugin's; `hooks-json-missing` now fires only when neither exists.**

- **[BLOCKER] A first-time user without CodeGraph reaches a session that cannot read source, and nothing reports it**
  - **What is wrong:** `codegraph-first-guard.py:321-330` blocks every source `Read`, `Grep` and `Glob` until a CodeGraph tool has run in the turn. It has no "no index" bypass, and its only escape is `CLAUDE_SKIP_CG`. `README.md:112-113` says it "auto-bypasses when no CodeGraph index exists", which the code does not do. The readiness report verifies eight facts and names three things it cannot verify, and CodeGraph availability is in neither list. The End-User View promises the operator a working set of checks.
  - **Prior artifact ignored:** `MECHANISMS.md:15` (CodeGraph mechanism, whose only bypass is `CLAUDE_SKIP_CG=1`); the contract's own Open Question reasoning that the alternative "is a skill that tells the operator something false on its first run".
  - **Where in this contract:** `### Design decisions` item 4 — the "verifies" and `not-verifiable` lists; `## End-User View → Connections` — "the code-search-first check".
  - **→ Addressed by: the readiness report carries a plain note that the code-search-first check blocks source reads until a CodeGraph tool has run and has no bypass without an index (silence one session with `CLAUDE_SKIP_CG=1`); the false README sentence is corrected in this change.**

- **[WARN] Two statements the contract proved false stay in files this change edits**
  - **What is wrong:** `README.md:110-111` and `hooks.json:17-21` still say an unconfigured install treats every database as protected. The README is edited in the same pull request, and `/auto-improve-finish-install` will report `template-placeholders` beside it. The correction is deferred to a follow-up whose own next step says to fix the README sentence.
  - **Prior artifact ignored:** `MECHANISMS.md:52` (Guard rules file: the fail direction "must be stated in the file").
  - **Where in this contract:** `### Design decisions` item 7, whose README list omits it; `2026-10-04-db-guard-rules-under-plugin-install.followup.md:20`.
  - **→ Addressed by: both false statements are corrected in `README.md` and in the `hooks.json` comment in this change (decision 7); `hooks.json` joins Files to touch, comment text only.**

- **[WARN] The doctor's `NEEDS YOU` line is shared by three files, and `/auto-improve-finish-install` fills only one**
  - **What is wrong:** `plugin_doctor.py:249` prints `NEEDS YOU` for every `authored=True` requirement: the profile, `area-mapping.json` and `work-item-conventions.json` (`:71-79`). Pointing that line at `/auto-improve-finish-install` tells the operator `/auto-improve-finish-install` fills the two files the Non-Goals exclude. The settings message is the `left alone` line at `:251`, not `NEEDS YOU`.
  - **Prior artifact ignored:** `2026-10-04-auto-improve-finish-install-step3-inference.followup.md` (step 3 deferred).
  - **Where in this contract:** `## Extension Points` — "the `Requirement.why` text for `.claude/settings.json`, and the `NEEDS YOU` line, both name `/auto-improve-finish-install`".
  - **→ Addressed by: the `NEEDS YOU` line is not repointed; only the settings and profile `why` text and the `left alone` line name the skill.**

- **[WARN] The settings rewrite leaves encoding, line endings and the Windows replace undefined**
  - **What is wrong:** a byte order mark makes strict parsing fail, so a file Claude Code accepts would be refused as `malformed-settings`, or the mark is silently dropped. Windows tools that write one include `Set-Content -Encoding UTF8` in PowerShell 5. A line-ending or indent mismatch makes the "exact change" diff cover the whole file. Duplicate keys collapse silently under a standard parser. A rename that fails because another process holds the file has no refusal code and no clean-up rule. A same-second backup collision has no stated outcome. "In meaning" is honest, but none of these behaviours is decided.
  - **Prior artifact ignored:** `VOCABULARY.md:35` (Vendored-asset drift), which records that line endings and a byte order mark change bytes without changing meaning.
  - **Where in this contract:** `### Design decisions` item 3, steps 2, 5 and 8.
  - **→ Addressed by: byte order mark tolerated and preserved, line ending and indent detected and reused, duplicate keys refused, rename failure refused as `write-failed` with the original untouched, backup collisions numbered, and a `.gitignore` hint (decision 3, steps 5 and 8).**

- **[WARN] The "no registration key twice" invariant is false on the real consumer, and ignoring the matcher hides coverage gaps**
  - **What is wrong:** `StockToolScalpingMachine/.claude/settings.json:131`, `:161` and `:176` register `db-destructive-guard.py` three times under `PreToolUse`, so the key repeats, and a script that preserves registrations cannot establish the invariant. Because the key omits the matcher, a guard present only on `PowerShell` counts as present, so the `Bash|Edit|Write|MultiEdit` registration is never added. The reverse also holds. The plugin's own `hooks.json:41-61` matches no `PowerShell` tool, which that consumer registers at `:170-183`. The readiness report will call the database guards "on" for a Windows session whose primary shell is unmatched.
  - **Prior artifact ignored:** `MECHANISMS.md:52`, which makes the database guard a blocking safety layer, so its coverage must be stated.
  - **Where in this contract:** `## Data Shapes → Entities` — "No registration key appears twice"; `## Business Concept` — "The matcher and the path prefix are deliberately not part of it".
  - **→ Addressed by: the invariant is reworded to what the script can guarantee (never adds an existing key; leaves existing duplicates alone and reports them), and the report names matcher coverage gaps such as the missing `PowerShell` match.**

- **[WARN] Install-mode detection has no named failure for an unreadable record, and no precedence**
  - **What is wrong:** the record format matches this machine (`C:\Users\lneni\.claude\plugins\installed_plugins.json:1-67`: `version: 2`, `scope`, `projectPath`, `installPath`). But no refusal names a missing, unparseable or unknown-version record, so a format change surfaces as `install-mode-none`, with the wrong cause. The plugin's own checkout satisfies `plugin`, `vendored` and `plugin-source` at once on this machine (user-scope entry at `:57-65`). No order between the five verdicts is stated.
  - **Prior artifact ignored:** `MECHANISMS.md:42` ("Two failure classes, deliberately different"), which requires a resolver to say which class a missing input falls into.
  - **Where in this contract:** `### Design decisions` item 2; the refusal-code closed set.
  - **→ Addressed by: new refusal `install-record-unreadable`, a stated precedence (plugin-source first, then both, plugin, vendored, none), and, from the user's later point about several plugins, a rule that only this plugin's entries are read.**

- **[WARN] The reused resolution idiom does not run in the order the contract states, and the mitigation lapses after one release**
  - **What is wrong:** `skills/advance/SKILL.md:44` passes three paths to `ls` and keeps the first line. `ls` sorts its operands, so the order is by name, not vendored, then `$CLAUDE_PLUGIN_ROOT`, then cache. A `/c/...` cache path sorts before a `C:\...` plugin root. "Older versions do not contain `auto_improve_finish_install.py`" stops being true at the second release that ships the file. The cache glob also hard-codes `~/.claude` (`plugin_doctor.py:140`) while the contract resolves the Claude home through `--claude-home` and `CLAUDE_CONFIG_DIR`.
  - **Prior artifact ignored:** `README.md:88-90` (the documented resolution order).
  - **Where in this contract:** `### Design decisions` item 5 — "the vendored path, then `$CLAUDE_PLUGIN_ROOT`, then the provider cache glob"; `## Failure Modes` — "The cache glob picks an older plugin version".
  - **→ Addressed by: the skill uses an explicit ordered test with the newest cache version first instead of copying the `ls` idiom (decision 5).**

- **[WARN] The test plan has cases that cannot fail first, and five refusal paths with no test**
  - **What is wrong:** "declining ... writes nothing", and each refusal asserted only as "leaves the tree byte-identical", pass against a script that does nothing. That breaks the contract's own "every case must fail first on an assertion". No mechanism is named for an assertion-first red state on a module that does not yet exist. These have no test: `project-unreadable` (a brief criterion), `template-missing`, `provider-has-no-hooks`, `hooks --apply` refused under the `plugin` mode, and `changed-since-preview` on the profile apply. The split between exit 2 and exit 3, and the agreement between the README variable table and the 12 variables read from source, also have none.
  - **Prior artifact ignored:** `test_plugin_doctor.py:179-186`, the suite's own positive-control precedent for an absence assertion.
  - **Where in this contract:** `### Design decisions` item 8, the Safety and Readiness lists.
  - **→ Addressed by: positive control for the decline case, every refusal pairs its unchanged-tree assertion with a code and exit-code assertion, the missing refusals plus the new ones get tests, the exit-code split is tested, and the first commit is a stub that makes tests fail on assertions.**

- **[WARN] The profile-apply rules contradict each other on what an unanswered slot becomes**
  - **What is wrong:** `safety-critical.roots` is "`none` if the operator gives nothing", while `ApplyProfile` needs one `--set` per placeholder slot or refuses `slot-unanswered`. The written form, backticked list or plain text, is never stated, so the `load_slot` round trip is ambiguous. `load_slot` returns a list for `a, b` only when each value is backticked. A per-root `frontend.theme-polarity` cannot survive `load_slot`'s flat list.
  - **Prior artifact ignored:** `MECHANISMS.md:56` (an empty slot reads `none`, so the empty value must be explicit).
  - **Where in this contract:** `### Design decisions` item 1 — the `safety-critical.roots` and `frontend.theme-polarity` rows; `### Commands` — ApplyProfile.
  - **→ Addressed by: a written-form rule (backticked list or `none`, `<root>=<polarity>` entries) and the rule that the skill passes `none` explicitly for an unanswered never-inferred slot.**

- **[WARN] Two inference rules can produce a confidently wrong value**
  - **What is wrong:** a `package.json` that depends on `express` marks a backend root, but an Angular server-rendering front end carries that dependency. The same folder then becomes a backend root and a frontend root. A `pyproject.toml` at the repository root makes the whole repository a backend root. `auth.roots` from a folder name is labelled `inferred` though the contract itself calls it "a name match only", which is a guess the brief forbids.
  - **Prior artifact ignored:** `README.md:374` ("A confidently wrong profile is worse than an obviously empty one").
  - **Where in this contract:** `### Design decisions` item 1 — the `backend.roots` and `auth.roots` rows.
  - **→ Addressed by: the `express` rule and a root-level `pyproject.toml` rule are dropped from `backend.roots`, and `auth.roots` is `needs-answer` with candidates listed.**

- **[WARN] The End-User View overstates what happens on macOS and Linux**
  - **What is wrong:** it says the command "chooses" the launch word automatically. That is true only for a vendored copy. Under a plugin install the cached `hooks.json` says `py -3` (`hooks.json:12-15`), so on macOS and Linux no hook can launch. Editing the cache is lost at the next update (`README.md:131-134`). The readiness report will say "not ready", and the End-User View never tells the operator that this case cannot be fixed by the command.
  - **Prior artifact ignored:** `README.md:131-134` (Known limitations).
  - **Where in this contract:** `## End-User View → Implications` — "On Apple and Linux machines the checks are switched on with a different launch word ... and the command chooses it automatically".
  - **→ Addressed by: the End-User View and the readiness report now say that a plugin install on macOS or Linux cannot be fixed by this command, and name the options.**

- **[WARN] The Confidence line uses a value the template does not allow, beside four `ASSUMED` items**
  - **What is wrong:** the format is `High`, `Medium` or `Low`. "Medium-High" opens with a High reading while four `ASSUMED` rows stand, and one of them decides whether every hook blocks.
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md:243`.
  - **Where in this contract:** `## Confidence` — "Confidence: Medium-High."
  - **→ Addressed by: Confidence is now `Medium`.**

- **[NIT] The one sub-task's TASK block hands the failing tests to a different agent** — the heading resolves `python-ai-developer` (`pr_merged.py:330` picks one agent per block), while the TASK block says `senior-test-engineer` writes the failing tests "in this one branch". Who dispatches the second agent is not stated.
- **[NIT] Two of the twelve variables are not kill switches** — `CLAUDE_ACTIVE_CONTRACT` pins a contract and `CLAUDE_DESTRUCTIVE_DB_OK` is a one-shot approval (`README.md:120`, `:122`). Calling all twelve "kill switches" mislabels them.
- **[NIT] The README recount misses a stale test count** — `README.md:269` and `:346` say "sixty-eight" tests for `test_pr_merged.py`, while `skills/advance/SKILL.md:58` records 313 measured.
- **[NIT] Backups land as untracked files in the repository** — `.claude/settings.json.bak-*` has no ignore rule and no clean-up rule.
- **[NIT] The marketplace clone the version check reads is not located** — the readiness report compares against "the version the local marketplace clone declares", but no path is given for that clone.
- **[NIT] Adjacent Areas uses non-canonical wording** — the sanctioned single line is "Not applicable. Reason: cross-area scan returned no signal above the threshold." The area map is empty, so no area derives, and the hand-derivation itself is not raised.
- **[NIT] Both follow-up stubs carry `**Issue:** pending`** — neither deferral is visible outside the stub register yet.
- **[NIT] The first real consumer is a live `both` case today, and the contract does not name it** — `StockToolScalpingMachine` registers the hooks in `settings.json`, while the plugin is enabled at user scope (`C:\Users\lneni\.claude\settings.json:207`). Every hook runs twice there.

**Nit responses.** Addressed: the TASK block's two-agent wording is explained in the scope note; the twelve variables are described as environment variables, not all kill switches; the `test_pr_merged.py` count is recounted; backups get a `.gitignore` hint; the marketplace clone for the version check is `<claude-home>/plugins/marketplaces/<marketplace>/`; the live `both` case on the first consumer is now named under Failure Modes. Rejected: the Adjacent Areas wording, because the scan truly did not run and the canonical sentence would claim it did. Handled after approval: the tracking issue for the two follow-up stubs.

### Applicable journal entries

- None. `.claude/registries/JOURNAL.md` holds no entries in either tier, so there was nothing to match. The contract's `## Lessons referenced` says the same, correctly.

### What the critic did not check

- Claude Code's own documentation on hook-command expansion, the `args` field and settings precedence. No documentation tool was available to this pass, so those three remain the contract's `ASSUMED` items.
- North-star alignment (checklist 13): this repository has no `.claude/north-stars/` directory, so the exception applies.
- `INTEGRATION.md` (checklist 7): absent here. The contract adds no REST, SignalR or data-transfer surface, so `## Chat Tool Impact` being "Not applicable" is correct.
- `derive_area.py` was not run, because this pass has no shell. The empty `areas` set in `.claude/area-mapping.json` means it can only return the fallback.

## Lessons referenced

No applicable lessons in JOURNAL.md at draft time. The plugin's Universal journal is empty, and this repository has no project tier and no domain journal files.

Orthogonal to north-stars: none. This repository has no `.claude/north-stars/` directory. That matches the brief's pre-grade.

## Implementation Handoff

### 1. The auto-improve-finish-install skill, script and docs (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `skills/auto-improve-finish-install/SKILL.md`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/scripts/plugin_doctor.py`
- `.claude/scripts/tests/test_plugin_doctor.py`
- `.claude/scripts/tests/test_plugin_manifests.py`
- `.claude/scripts/pr_merged.py`
- `.claude/scripts/tests/test_pr_merged.py`
- `.claude/hooks/hooks.json`
- `README.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`

**Pre-written TASK block:**
```
TASK: Deliver /auto-improve-finish-install as specified: auto_improve_finish_install.py (profile and hooks subcommands, the
      shapes, refusal codes and exit codes in Data Shapes), its unittest suite, the
      skill, the doctor message change, manifest INV-11, the README edits in design
      decision 7, and the 0.2.2 -> 0.3.0 bump in all five declarations.
CONTEXT: concept contract at .claude/concepts/2026-10-04-auto-improve-finish-install-skill.md
FILES: as listed under Files to touch
CONSTRAINTS:
  - Run through /tdd-first in this one branch: senior-test-engineer writes the RED cases
    from design decision 8 first; each must fail on an assertion, never on an import.
  - Reuse by import: find_plugin_root (plugin_doctor), load_slot, DEFAULT_IMPLEMENTERS,
    DEFAULT_REVIEW_GATES (pr_merged). Do not re-implement any of them.
  - Read slot names from the plugin template table; never hard-code the eleven.
  - Never write a file without a preview hash match; write nothing when nothing changes.
  - Tests use temp directories and --claude-home; never read the real home directory.
  - Emit the command + args form in the merge, and prove it runs with one harmless
    hook invocation before relying on it. Say how you proved it in the pull request.
  - Fix load_slot in pr_merged.py (placeholder test before backticks; a missing row
    never falls through to the worked example) with its own RED test first.
  - Never accept the project itself as the plugin template source (design decision 1).
  - Several plugins may be installed: read only entries for agentic-auto-improve and
    ignore every other plugin (design decision 2).
  - Recount README inventory from the tree; do not increment stated numbers.
  - The skill follows the /advance resolution idiom and the existing SKILL.md
    frontmatter (name, description, user_invocable).
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-04-auto-improve-finish-install-skill.md
  contract_status: approved
```

### 2. Scope note on review

There is one mergeable block, because the deliverables share a version bump and a README and would not be useful merged apart. Review runs in the outer chain that `/flow` already drives: the code reviewer and the test-suite reviewer after GREEN, then verification. No separate review-gate block is declared, so the loop dispatches exactly one sub-task. There is no frontend work, no migration and no hook behaviour change. `/tdd-first` itself dispatches `senior-test-engineer` for the failing tests, inside this one block, so no second sub-task exists.

## Review checklist (filled in after implementation)

- [x] Implementation matches Data Shapes exactly. Divergences, all justified by the reviews and recorded in the notes above `## Critique`: both plans report `plan-sha256`; the readiness report carries `mode`, `plugin-root`, `platform-note`, `manifest-hooks-resolves`; the refusal set grew to 21 codes (`plugin-install-needs-no-registration`, `invalid-slot-value`).
- [x] Reused Mechanisms are actually reused: `find_plugin_root` (wrapped), `load_slot` (fixed at the source), `DEFAULT_IMPLEMENTERS`, `DEFAULT_REVIEW_GATES` are imported, none re-implemented.
- [x] New Mechanisms promoted to `MECHANISMS.md` (Preview-hash apply).
- [x] New vocabulary terms promoted to `VOCABULARY.md` (Install mode, Placeholder slot, Registration key).
- [x] README counts match the tree (22 skills, 14 agents, 16 hook files over 17 registrations, 14 workflow scripts, 9 script suites, 4 hook suites, a 12-variable table checked by INV-12, the suite count checked by INV-15).
- [x] `Status` flipped to `implemented`.

### Implementation notes (post-review, 2026-10-04)

- **Review path:** test-strategy critic before implementation (two blockers fixed), then a code review and a test review after it (three blockers and ten warnings fixed in a second round), then a second code review (six warnings fixed in a third round, no blocker open). Final suites: main 199 tests, manifests 49 checks, `pr_merged` 319, doctor 24, all passing.
- **Resolved assumption:** `${CLAUDE_PROJECT_DIR}` is expanded in the `command` + `args` form (Claude Code hooks documentation, exec form), so the merge writes that form.
- **Implementer choices the reviewers accepted:** the profile apply writes no backup (the plan hash protects it); a role slot is written exactly as given, with the plugin defaults carried in the proposal; an install record with an unrecognised `version` is refused as `install-record-unreadable`; with several marketplace copies the one holding the running script is used.
- **Known and left open (follow-ups, issue #21):** the database guard cannot take project-specific rules under a plugin install; step 3 of the Quick start (the other three per-project files) is not inferred. Not checked by any test: that a running Claude Code session actually loaded the hooks (the report lists this as not verifiable).
- **Real-world check (read-only):** run against the ScalpingMachine repository, the profile plan kept every authored slot and the hooks plan refused with `install-mode-both`, which is that repository's live double registration today.
