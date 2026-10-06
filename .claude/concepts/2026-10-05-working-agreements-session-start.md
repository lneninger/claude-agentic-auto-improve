# Concept Contract — Deliver the user's working agreements to every session from the plugin

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-05
**Requested by:** user
**Status:** implemented
**Work item:** `.claude/work-items/2026-10-05-working-agreements-injection.md`

> **Protocol:** filled in by `data-architect`. The lifecycle and the management commands are in `.claude/templates/concept-contract.md`.

---

## Business Concept

- **What is this thing, in domain language?**
  A **working agreement** is one standing rule about how the assistant works with the user, written in plain words in its own small file. Examples: write in plain language, do every change in its own isolated checkout, stop completely when told "stop". Today these rules live only in one person's private memory folder, so a new machine or a new project never receives them. This contract adds a session-start step to the plugin: when a session opens, a new hook (`working-agreements.py`) reads the agreement files the plugin ships and any the project adds, and hands their text to the model before the first reply. The plugin ships six agreements. The first is the full plain-language rule, including the part no checker can enforce: explain every named file, class or tool the first time it is mentioned. The other five are the user's generic habits. A project adds its own agreement by dropping a file into its own `.claude/agreements/` folder. A project can add agreements but cannot replace a shipped one. The delivered text has a size limit, and the shipped plain-language agreement is never the one dropped. A project's own instructions, and any skill gate that requires asking the user, win over an agreement. This version delivers from a plugin install only; a vendored copy of the hook stays silent.

- **Existing VOCABULARY.md terms that apply:** **Plugin repository**, **Vendored asset**, **Install mode** (only `plugin` and `plugin-source` deliver; `vendored` and the vendored half of `both` stay silent), **Registration key** (the new registration is `SessionStart` + `working-agreements.py`), **Claude data root** (deliberately not used for the two agreement folders; see Design decision 2).

- **New terms proposed for VOCABULARY.md (Universal tier), appended after approval:**
  - **Working agreement** — one standing rule about how the assistant works with the user, kept as one markdown file in an agreements folder and delivered as context at session start. It is guidance read by the model, not a check: nothing blocks when it is ignored. A rule that some hook also enforces may still be an agreement, because the hook sees only part of it. Distinct from a **Guard rules file**, which configures a hook rather than instructing the model.
  - **Shipped agreement** — a working agreement that ships with the plugin in its own `.claude/agreements/` folder. It must name no project, no person, no machine path and no incident date.
  - **Project agreement** — a working agreement a consuming project keeps in its own `.claude/agreements/` folder. It is delivered beside the shipped ones and labelled as coming from the project. A project file whose name equals a shipped one is skipped and logged; it never replaces the shipped agreement.
  - **Always-kept agreement** — the shipped plain-language agreement, which the size limit never drops. The guarantee belongs to the shipped text only. No configuration and no project file can extend it to another agreement or take it away.

---

## End-User View

**Category:** Getting Started

### What the end user sees
Nothing changes on screen. When a session opens, the assistant already knows the team's standing rules about how to work: how to write, how to deliver a change, and how to respond when told to stop. The assistant follows them from its first reply, on a new machine or in a new project, without anyone copying instructions into place.

### What it does for the end user
Until now the assistant learned these habits one correction at a time, and the lessons stayed on the machine where they were taught. The writing checker could stop a message that broke the plain-language rule, but the assistant was never told the rule in the first place, so the same mistakes recurred. Now the rules arrive with the toolkit. A team can also add its own rules by writing a short file in its project, and those arrive together with the shared ones.

### Connections to the rest of the system
The plain-language agreement is the written form of the rule the end-of-turn writing checker enforces. The checker catches some breaks after a message is written. The agreement tells the assistant the whole rule before it writes anything: every fault the checker stops on, including the sentence-length and long-dash limits, plus the part about explaining every named file or tool, which the checker cannot see. When a project's own instructions or a step that must ask the user a question disagree with an agreement, those win. The worktree agreement points at the task intake command that creates an isolated checkout. The pull-request agreement matches the delivery steps the toolkit already provides.

### Implications
The rules take up a small, fixed part of the assistant's working memory in every session. That is why the delivered text has a size limit, and why a long project rule can be left out with a note saying where to read it. A rule takes effect in the next session after it is added, not in a session already running. The rules are guidance: the assistant can still slip, and only the writing checker actually stops a message. A project's own rules come from its repository, so they deserve the same trust as that project's other instructions to the assistant, and they are labelled as coming from the project. A project can add rules but cannot rewrite a shared one. In this version the rules arrive only when the toolkit is installed; a project that copied the toolkit's files in by hand receives none.

### Measures
Opening a session is never blocked or slowed by this step: if a rule file is missing, damaged or unreadable, the step records a line in its log and the session opens normally. The plain-language rule is never the one left out for size. A test fails if any shipped rule names a project, a person or a machine folder, and another fails if any of the six shared rules is missing. A copied-in version of this step stays silent, so a project set up both ways gets the rules once; the setup command also refuses that double setup. The step's log records what it handed over, not what the assistant received. The step can be switched off for one session with a single setting.

### How it could be improved
The checker cannot yet catch an unexplained file or tool name, so that part of the rule still depends on the assistant following it. Each project cannot yet change the size limit when the toolkit is installed rather than copied. A project that copies the toolkit in by hand could be supported later. The writing checker's own message still names one person and should say "the user" instead.

---

## Data Shapes

Nothing is persisted except log lines. Every shape below is read or produced within one hook run, so all are value objects.

### Entities

None. Reason: an agreement has no identity beyond its file name, and the hook keeps no state across sessions.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| WorkingAgreement | slug (string; the file name without `.md`), title (string; the file's level-one heading), body (string; everything after the heading), origin (enum: `shipped`, `project`), source path (path), always kept (bool; true only for the shipped `plain-language`) | One deliverable rule |
| AgreementFile (on disk) | UTF-8 markdown. The first non-blank line is a level-one heading `# <title>`. At least one non-blank line follows it. File name is `<slug>.md`, lowercase kebab-case. | The authoring format |
| AgreementsRules (`working-agreements.rules.json`) | max characters (integer, default 9000; counts the whole delivered text) | The configured size limit. It has no always-keep setting. |
| DeliveryPlan | delivered (ordered list of WorkingAgreement), dropped for size (list of slug + path), skipped (list of file name + reason: `unreadable` / `malformed` / `shadows-shipped`), total characters (integer), limit (integer), over limit kept (bool) | What one run decided; logged |
| SessionStartPayload (input) | session id (string), source (enum: `startup`, `resume`, `clear`, `compact`; any other value is accepted and used as-is), the rest ignored | stdin |
| SessionStartEnvelope (output) | `hookSpecificOutput.hookEventName` = `SessionStart`, `hookSpecificOutput.additionalContext` = the delivered text | stdout, one JSON object, ASCII-only |

**Invariants.**

- **INV-1 Fail open, always.** Every path exits 0 and writes nothing to stderr. No path blocks or waits: no network, no retry loop, no lock wait.
- **INV-2 Output shape.** stdout is empty, or exactly one JSON object holding the nested envelope above. `additionalContext` is never placed at the top level, where it is ignored. The JSON is serialised ASCII-only, so a non-ASCII character in an agreement cannot break a Windows console encoding.
- **INV-3 Shipped plain-language is always kept.** Only the shipped `plain-language.md` is always kept; nothing in the rules file or the project folder changes that. When it is readable and well formed it is delivered, even when it alone exceeds the limit (logged `over-limit-kept`). Because no project file can take its place, the always-kept text is bounded by the shipped file's own size.
- **INV-4 Whole agreements only.** The size limit drops whole agreements and never truncates one. A half-delivered rule can invert its meaning.
- **INV-5 Drop order and what is counted.** `max_characters` counts the whole delivered text: the opening paragraph, every heading, every body and the closing "not delivered" line. When the text exceeds the limit, agreements are dropped in this order, re-measuring with the closing line included after each drop, until it fits: project agreements in reverse file-name order, then shipped agreements other than plain-language in reverse file-name order. The closing line names at most three dropped agreements with their paths, then a count per folder; the log names every dropped agreement. Size is measured in UTF-16 code units, as the host counts. Project files larger than four times the limit, and project files or folders that link outside their folder or the project, are skipped unread.
- **INV-6 Delivery order.** The shipped plain-language agreement first; then the other shipped agreements in file-name order; then project agreements in file-name order.
- **INV-7 Plugin installs only; vendored copies stay silent.** The hook delivers only when the folder above its own `hooks/` folder belongs to the plugin, meaning the repository root above it carries `.claude-plugin/plugin.json` naming `agentic-auto-improve`. That holds for a plugin install and for the plugin's own checkout. A vendored copy of the hook, inside a consuming project, prints nothing and logs `vendored-unsupported`. In the plugin's own checkout the shipped folder and the project folder are the same directory: it is read once and every file in it is labelled as coming from the plugin, which is accurate there.
- **INV-8 A project cannot replace a shipped agreement.** A project file whose name equals a shipped file's name is skipped and logged `shadows-shipped`, and the shipped agreement is delivered. Origin labels are always accurate: a project file is labelled "from this project", a shipped file "from the plugin".
- **INV-9 Per-file degrade.** An unreadable or malformed file is skipped and logged; the other agreements are still delivered. When nothing deliverable remains, stdout is empty. *(Open Question 2, answered.)*
- **INV-10 No duplicate suppression in the hook.** The hook keeps no marker and no time window. Duplicate registration is prevented outside the hook: a vendored copy stays silent (INV-7), the finish-install script refuses the both-copies install mode, and its readiness report checks for duplicate registrations. **Residual risk:** if the plugin's copy of this hook is registered twice by some other route, the model receives the agreements twice in that session. That costs context, not correctness.
- **INV-13 Precedence.** The delivered opening paragraph states that a project's own instructions, and a skill's explicit gate that requires asking the user (for example the design skill's Open Questions), win over any agreement. A test asserts this sentence is present.
- **INV-11 Shipped files are generic.** No shipped agreement names a project, a person, a machine path or an incident date (see Design decision 6).
- **INV-12 Escape hatch.** `CLAUDE_WORKING_AGREEMENTS` set to `off`, `0`, `false` or `no` exits 0 at once, with no output and no log line.
- **INV-14 The six required agreements ship.** The plugin's `.claude/agreements/` holds exactly the six required file names listed under "Required content". A test names all six and fails if any one is missing; it does not loop over whatever files happen to exist.

### Events

Every event is one log line in `<logs>/working-agreements.log`, where `<logs>` is `_project_paths.logs_dir()` (project-local when Claude Code supplied the project folder, the home folder's `.claude/logs` otherwise, exactly as every other hook here). The hook is the emitter and the log is the only listener.

| Name (past tense) | Emitter | Listeners | Payload |
|-------------------|---------|-----------|---------|
| AgreementsPrinted | hook | log | session id, source, printed slugs, total characters, limit. The line says "printed": it records what the hook wrote to its output, not what the host received or showed the model. |
| AgreementSkipped | hook | log | file name, reason (`unreadable` / `malformed` / `shadows-shipped`), detail |
| AgreementDroppedForSize | hook | log | slug, path, characters |
| OverLimitKept | hook | log | total characters, limit |
| ShippedFolderMissing | hook | log | the path looked for |
| VendoredCopySilent | hook | log | the hook's own folder |
| RulesLoadFailed | hook | log | error text; built-in defaults used |

### Commands (if any)

None. Reason: the hook takes no instruction; it runs once per session-start event.

### Design decisions behind the shapes

1. **Where the agreement files live and how they are named.** Shipped: `<plugin>/.claude/agreements/<slug>.md`, located from the hook's own position (the hook's directory's parent, then `agreements`). Project: `<project>/.claude/agreements/<slug>.md`, where the project root is `_project_paths.project_dir()`, which reads `CLAUDE_PROJECT_DIR`. There is **no** current-directory fallback: when that variable is unset, no project folder is read and only the shipped agreements are delivered. Only `*.md` files directly inside a folder are agreements. `README.md` and any name beginning with `_` or `.` are ignored, so a folder can carry its own notes. The folder sits under `.claude/` beside `hooks/`, because a plugin install carries the whole repository.
2. **Why not the Claude data-root search.** `claude_roots()` takes the *first* root that contains the thing sought and never unions roots. Agreements need exactly two named layers delivered together, and must never pick up the current directory's or the home folder's `.claude`. So the hook names its two folders directly, as Design decision 1 states, and reuses only `project_dir()` and `logs_dir()` as they are. No helper function is added to `_project_paths.py`, so a stale vendored helper cannot put the hook into a fallback mode.
3. **Hook name and registration.** `.claude/hooks/working-agreements.py`, registered in `.claude/hooks/hooks.json` under a new `SessionStart` event with no matcher, so it runs on startup, resume, clear and compaction. Delivery after compaction is wanted: the summary that replaces the conversation may not carry the rules. The registration key is `SessionStart` + `working-agreements.py`, no arguments.
4. **Size limit.** `max_characters` in `working-agreements.rules.json` beside the hook, default 9000 characters of delivered text, counted as INV-5 states. The shipped files are sized so they fit with room to spare: plain-language under about 1,600 characters, each of the other five under about 1,000, so at most about 6,600 plus roughly 600 of opening paragraph and headings. That leaves about 1,800 characters for project agreements. A test asserts the shipped set alone fits under the default limit with nothing dropped. The default stays under the cap Claude Code is believed to place on hook-injected context (see Uncertain Assumptions). The rules file follows the **Guard rules file** convention and states its fail direction: this hook only informs, so a missing or malformed rules file **fails soft** to the built-in defaults and logs `rules-load-failed`. It never switches delivery off.
5. **Duplicate delivery.** Claude Code runs every registration it finds. The hook does not try to detect a second copy of itself at run time: there is no marker file, no time window and no atomic claim. Duplicates are prevented where they arise. A vendored copy stays silent (INV-7). The finish-install script refuses the both-copies install mode (`install-mode-both`), and its readiness report checks for duplicate registrations (`no-duplicate-registration`). The residual risk is stated under INV-10. A project's *other* session-start hooks (for example an index refresh) do not interact with this one; they simply run alongside it.
6. **The genericity test without contaminating the plugin.** Writing the forbidden names into a plugin test would put them into the plugin. So the scan uses three sources. (a) Structural patterns: a drive-letter path, a home-folder path (`/Users/`, `/home/`, `~/.claude/projects`), an e-mail address, an ISO date, and a `github.com/<owner>` link. (b) The author name and repository owner read from `.claude-plugin/plugin.json` at test time. (c) Every token in the project's own `.claude/.project-tokens.json` when that list is non-empty; the plugin's own copy is an empty template, so this source applies wherever a consuming project has filled its list in. Matching is case-insensitive, on the text as written. Each source has a positive control that plants a **made-up word** (never a real forbidden name) in a temporary copy, with the made-up word supplied to that source by the control itself, and must fail. A consuming project keeps its own literal list of names in its token file, exactly as the existing **Project-name check** does; the plugin never holds those names.
7. **The delivered text.** One opening paragraph: "Working agreements for this session. These are the user's standing rules for how to work. Follow them in every message and action, starting with your first reply. A project's own instructions, and a skill's explicit gate that requires asking the user (for example the design skill's Open Questions), win over any agreement. Agreements marked 'from this project' come from the project's own repository." Then each agreement as `## <title> (from the plugin)` or `## <title> (from this project)`, followed by its body. When anything was dropped for size, one closing line names each dropped agreement and its path, and says to read the file if a task touches it.
8. **Version.** `0.3.2` to `0.4.0` in all five declarations, because this adds a feature. The `0.2.2` to `0.3.0` precedent for the previous feature applies.

### Required content of the shipped agreements (distilled, never copied)

Every file is written for "the user", in plain language, within the sizes in Design decision 4, with no project, person, path or date.

- **`plain-language.md`** — seven labelled rules, each opening with exactly this bold label, so a test can find all seven: **Explain every named element**, **Use a name, not a number**, **Write short forms out**, **One idea per sentence**, **Keep sentences to thirty-five words or fewer**, **Fewer than three long dashes in a sentence**, **Questions a newcomer can answer**. The two limit rules match the shipped checker's `max_sentence_words` and `max_em_dashes_per_sentence`. The element rule includes a worked example in generic terms and says plainly that no automatic checker can catch a break of it. The audience is the user and any newcomer to the project.
- **`one-worktree-per-change.md`** — a session that will change files starts from the task intake command, which creates its own isolated worktree on a fresh branch; never edit the shared main checkout. A change is finished only once it is shipped as a pull request. Read-only work needs no worktree. Re-read any fact from the brief inside the worktree before relying on it.
- **`shared-repository-changes-through-pull-requests.md`** — a change to a shared toolkit or plugin repository goes through a branch and a draft pull request, never a direct push to its main branch, even when nobody else works there. Branch before the first commit. A change spanning two repositories opens two linked draft pull requests that merge together.
- **`one-line-commands-for-the-user.md`** — when the user must run something, write a self-contained script file and give one short line that runs it. Never a multi-line block or nested quoting. If a guard blocks writing the script, say so plainly instead of reshaping the text to get past the guard.
- **`stop-means-stop.md`** — "stop" is a full halt, not a redirect. Report the current state in two or three lines and ask only whether to keep or revert it. Any reasoning in the stop message is context for a later decision, not permission to continue.
- **`recommendations-not-question-batches.md`** — lead with a recommendation: state each finding with its effect and what you recommend. Never hand the user a batch or a menu of questions. Ask a question only when a skill's gate requires asking the user, for example the design skill's Open Questions, and then ask one question at a time, each carrying its own recommendation. The file says in its own words that a project instruction or a skill's explicit gate wins over this agreement.

---

## Reused Mechanisms

- **Guard rules file** (MECHANISMS.md, Universal) — **extended by** one more rules file, `working-agreements.rules.json`, which states a fail-soft direction in the file. The plugin's `hooks/` holds four generic data files today; this makes five. Proved, as the entry requires, by a test with the rules file renamed away.
- **The carry-forward context-injection envelope** (`plain-language-guard.py:636-643`; not a registered mechanism) — consumed in shape: the same nested `hookSpecificOutput.additionalContext`, with `hookEventName` = `SessionStart`.
- **Two-layer Claude path resolution** (MECHANISMS.md, Universal) — `project_dir()` and `logs_dir()` consumed as-is. `claude_roots()` is deliberately not used (Design decision 2), and no locator is added.
- **Project-name check** (MECHANISMS.md, Universal) — consumed as-is. Its token file is one of the three sources of the genericity test, read only when non-empty. The consuming project keeps the literal names there, so the plugin never holds them.
- **Plugin registry ownership model** (MECHANISMS.md, Universal) — consumed as-is. No sync tree for `.claude/agreements` exists or is added, so nothing keeps a vendored copy equal; that is one reason vendored delivery is not supported in this version (INV-7). A project agreement is local by default because no `files` array names it.
- **The finish-install install-mode refusal and readiness check** (`auto_improve_finish_install.py:950-954` `install-mode-both`, `:1121`/`:1131` `no-duplicate-registration`; Preview-hash apply contract) — consumed as-is, as the duplicate-delivery guard (Design decision 5).
- **Registration key** (VOCABULARY.md) — consumed as-is. `auto_improve_finish_install.py` reads events generically (`:1146` filters by event only for its gate list), so a `SessionStart` registration needs no change there.
- **The per-hook log pattern** of `plain-language-guard.py` (`log_delivery`; not registered) — consumed as a pattern for the log.
- **The kill-switch convention** (README table, checked by INV-12 of `test_plugin_manifests.py`) — extended by `CLAUDE_WORKING_AGREEMENTS`.

## New Mechanisms (if any)

- **Name:** Session-start context delivery (`working-agreements.py` + `.claude/agreements/`)
- **Purpose:** hand standing guidance to the model once per session start, from two layers of plain files, inside a size budget, failing open.
- **Why an existing mechanism was not sufficient:** the plugin has no session-start hook at all (`hooks.json` registers no `SessionStart` event). The carry-forward path delivers only at user-prompt time, only a notice the guard itself saved, and only once. Folding agreements into it would make the first reply of every session run without them, and would tie unrelated content to the writing checker's state file. The memory pager stages budget proposals and never injects content.
- **Proposed location:** `.claude/hooks/working-agreements.py`, `.claude/hooks/working-agreements.rules.json`, `.claude/agreements/`.
- **Extension seam:** a new shipped agreement is a new markdown file in the plugin's folder, plus its name in the required-file test; a new project agreement is a new markdown file in the project's folder. No code change either way.
- **Will this be promoted to `MECHANISMS.md` after implementation?** yes. Proposed entry, appended by `data-architect` after implementation: "**Session-start context delivery** — `working-agreements.py` on `SessionStart` reads `<plugin>/.claude/agreements/*.md` and `<project>/.claude/agreements/*.md`, skips a project file that shares a shipped file's name, orders and size-bounds the text with `working-agreements.rules.json` (the shipped plain-language always kept, whole agreements dropped, project agreements first), states that project instructions and skill gates win, stays silent when run from a vendored copy, and prints the nested `additionalContext` envelope. Its log records what it printed, not what the host received. Fails open on every path. Extend by: adding a markdown file; never by adding code per agreement."

---

## Extension Points

- `.claude/hooks/hooks.json` — a new top-level `SessionStart` array with one group and one command: `py -3 "${CLAUDE_PLUGIN_ROOT}/.claude/hooks/working-agreements.py"`.
- `.claude/agreements/` — new folder holding the six shipped files.
- `test_plugin_manifests.py` — no edit. INV-8 picks up the new hook from disk and from `hooks.json`; INV-12 requires the new variable in the README table.
- `test_auto_improve_finish_install.py` — the one test that parses the **real** `hooks.json` (`test_the_real_plugin_hooks_json_yields_exactly_its_seventeen_registrations`, around line 1859) asserts 17 registrations from 16 files, and its fixture creates only the fake plugin's 16 hook files. It must change to 18 registrations from 17 files, its fixture must hold the new file, and it is renamed `test_the_real_plugin_hooks_json_yields_exactly_its_eighteen_registrations` with its messages updated to match. Everything else in that suite uses the fake plugin and stays at 17. No `def test_` method is added or removed, so the README's stated case count (INV-15) still holds.

## Integration Surfaces

`.claude/registries/INTEGRATION.md` does not exist in this repository. Traced by hand:

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---|---|---|---|---|
| Claude Code | `working-agreements.py` | `SessionStart` hook, stdin | SessionStartPayload | host → hook |
| `working-agreements.py` | Claude Code model context | stdout | SessionStartEnvelope | hook → host |
| `working-agreements.py` | plugin and project `.claude/agreements/` | file read | AgreementFile | read only |
| `working-agreements.py` | `<logs>/working-agreements.log` | file append | log line | hook → disk |

**Changes to existing integration surfaces:** none. No REST, SignalR or data-transfer surface exists here.

## Adjacent Areas

The cross-area scan was **not run**. This agent has no shell, so it cannot execute `cross_area_scan.py`, and the plugin's `.claude/area-mapping.json` has an empty `areas` set. Three adjacent items were found by hand:

| Area | Decision | Implication / Reason | Handle |
|------|----------|----------------------|--------|
| plain-language guard messages | follow-up handle | The shipped guard names one person in its stop message, which breaks the genericity this contract establishes. | `.claude/concepts/followups/2026-10-05-plain-language-guard-names-a-person.followup.md` (`**Issue:** pending`) |
| rules files under a plugin install | follow-up handle | `hook_file()` prefers the hook's own folder, so under an install a project cannot change this hook's size limit either. Same class as the existing stub. | `.claude/concepts/followups/2026-10-04-db-guard-rules-under-plugin-install.followup.md` (issue #21) |
| consumer sync configuration | not applicable | Vendored delivery is not supported in this version (INV-7), so no consumer needs an `.claude/agreements` sync tree; that configuration lives in the consumer anyway (Plugin registry ownership model, MECHANISMS.md). | — |

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces. The plugin has no application user interface.

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

## Non-Goals

- Removing or editing the copies of the guard, or the private memory files, in any consuming repository.
- Habits that name one project's paths, trading code or tools.
- Changing the plain-language guard's weights, thresholds or messages (see the follow-up).
- A checker for the element-explanation rule.
- Replacing or switching off a shipped agreement from a project. A project can only add agreements.
- Delivery from a vendored copy of the hook, and a sync tree for `.claude/agreements`.
- Run-time suppression of a duplicate registration inside the hook.
- Making the size limit configurable per project under a plugin install (existing stub, issue #21).
- Hooks for Cursor or Codex.

## Where this contract departs from the brief

1. **"Five manifest places."** True: five version declarations in four files (the Claude marketplace file declares it twice). The plugin's current version is `0.3.2`, not the `0.2.0` the brief cited from memory.
2. **"A malformed file makes the hook exit with no output."** Read literally, one damaged project file would silence every agreement, including plain-language. INV-9 skips only the bad file. The literal case is still met and tested whenever the bad file is the only one. The user approved this reading (Open Question 2).
3. **"A missing folder → no output and a log line." This is a deliberate departure, approved by the user.** A missing *project* folder produces no log line. Reason: most projects will never create one, so it is the normal state rather than a failure, and a line in every session's log would bury the real failures. A missing *shipped* folder is a broken install and is logged as `shipped-folder-missing`. With no project folder either, the output is empty, which is the tested case.
4. **"A project can add its own agreement files."** Adding is supported; replacing a shipped agreement by using the same file name is not (INV-8). The brief left the replacement question to the contract, and the user chose "add only".
5. **Vendored installs.** The brief speaks of a project "with the plugin installed". This version delivers only from a plugin install or the plugin's own checkout; a vendored copy stays silent (INV-7).
6. **README counts.** Recount them from the tree after the change; do not add one to stated numbers. Expected: 17 hook files over 18 registrations, 5 hook test suites, 5 generic data files in `hooks/`, and a 13-variable table of which 11 are kill switches.

## Confidence

Confidence: Medium. High on ordering, size, same-name and failure behaviour, all of which are local and testable; high on the registration and manifest effects, verified against `test_plugin_manifests.py` and the finish-install suite. Medium on the host contract: the `SessionStart` envelope and the hook-context size cap are still unverified, and the made-up-phrase trial that opens the implementation settles them.

## Alternatives Considered & Why Rejected

- **Option A (chosen):** a dedicated session-start hook that reads two folders of markdown files.
  - Why: the first reply already carries the rules, adding a rule needs no code, and the hook cannot block anything.
- **Option B (rejected):** deliver the agreements through the plain-language guard's carry-forward path on the first user prompt.
  - Why rejected: it runs only once a prompt arrives, it ties unrelated rules to the writing checker's state and kill switch, and turning the checker off would silently drop every agreement.
- **Option C (rejected):** ship a `CLAUDE.md` fragment and ask each project to paste it into its own file.
  - Why rejected: this is the manual copy step the brief exists to remove, and pasted copies drift from the plugin with no signal.
- **Option D (rejected):** one agreements file holding every rule.
  - Why rejected: a project could not add one rule beside the others, and the size limit could only truncate, which INV-4 forbids.
- **Option E (rejected):** suppress a duplicate run inside the hook with a per-session marker file and a time window.
  - Why rejected: the window can swallow a legitimate second start, the expiry step is not atomic, and the install tool already refuses the both-copies mode that causes duplicates.

## Uncertain Assumptions

- `VERIFIED via .claude/hooks/hooks.json`: no `SessionStart` event is registered; 16 hook files, 17 registrations, all in the `py -3 "${CLAUDE_PLUGIN_ROOT}/..."` string form.
- `VERIFIED via .claude/hooks/plain-language-guard.py:636-643`: the plugin already emits `{"hookSpecificOutput": {"hookEventName": ..., "additionalContext": ...}}` for `UserPromptSubmit`, with a comment that the top-level placement is ignored.
- `VERIFIED via .claude/hooks/_project_paths.py:44-149`: `project_dir()` reads `CLAUDE_PROJECT_DIR`; `hook_file()` checks the hook's own folder first; `logs_dir()` is project-local when the project is known and falls back to the home folder otherwise.
- `VERIFIED via .claude/scripts/auto_improve_finish_install.py:950-954` and `:1121`/`:1131` (cited by the critic): the both-copies install mode is refused, and the readiness report checks for duplicate registrations.
- `VERIFIED via .claude/scripts/tests/test_plugin_manifests.py`: INV-8 requires every non-underscore `.py` in `hooks/` to be registered; INV-11 requires five identical versions; INV-12 requires every `CLAUDE_*` variable a hook reads to be in the README table.
- `VERIFIED via the five manifest files`: the version is `0.3.2` everywhere; two descriptions say "16 enforcement hooks".
- `VERIFIED by trial, 2026-10-05`: a throwaway plugin (kept outside the repository, never committed) registered one `SessionStart` command hook with no matcher that printed `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "<text with a made-up phrase>"}}`. A headless session started with `claude -p` and `--plugin-dir` pointing at it, then asked for the phrase, answered with the exact phrase. So the nested envelope is delivered to the model from a plugin hook before the first reply. This replaces the old assumption and the never-run planned trial ("T7").
- `VERIFIED by trial, 2026-10-05`: the same throwaway plugin with about twelve thousand characters of filler placed BEFORE the made-up phrase, which sat at the end. The model answered NONE, so text over the cap is cut or dropped, not delivered. The default limit of 9000 characters is therefore a hard safety margin, not a preference, and INV-5 (re-measure after each drop, count the closing line) is load-bearing.
- `VERIFIED via the Claude Code hooks documentation (https://code.claude.com/docs/en/hooks), read by a research agent on 2026-10-05`: `additionalContext` supports a 10,000 character limit; plain stdout text is also added as context for this event; the sources are startup, resume, clear, compact and fork; a command hook exiting zero never blocks the session; `${CLAUDE_PLUGIN_ROOT}` expands in plugin command hooks; stdin carries `session_id`, `source`, `cwd` and `transcript_path`. The documentation does NOT say what happens above the limit (the trial above shows the text is lost) and does NOT state outright that an empty matcher covers every source (the trial covered startup only).
- `ASSUMED`: a hook with no matcher also runs for resume, clear, compact and fork. Only the startup source was run in the trial. If wrong, an agreement text is missing after a resume or a compaction, and nothing fails. Verification path: the live check in the pull request description repeats the made-up phrase after a resume.

## Failure Modes & Mitigations

- **FM:** The host ignores the envelope, so nothing is delivered and nobody notices.
  - **Mitigation:** the implementation's first step is a harmless trial with a made-up phrase that exists nowhere else, run before any test is frozen; the live check in the pull request description uses the same phrase (Open Question 1, answered). The log line is named `printed` and records only what the hook wrote, so nobody reads it as proof of receipt.
- **FM:** The plugin and a vendored copy both run, doubling the context.
  - **Mitigation:** the vendored copy stays silent (INV-7); the finish-install script refuses the both-copies mode and its readiness report checks duplicate registrations. Residual risk, in plain words: if the plugin's own copy is ever registered twice by another route, the agreements appear twice in that session. That wastes some context and changes nothing else.
- **FM:** A stale vendored agreement is delivered instead of the current shipped one.
  - **Mitigation:** cannot happen in this version, because vendored copies deliver nothing. No sync tree keeps vendored agreement files equal, so supporting vendored delivery later needs its own design.
- **FM:** A damaged or same-named project file silences or replaces the plain-language rule.
  - **Mitigation:** INV-8 (a project file can never replace a shipped one) and INV-9 (a bad file is skipped).
- **FM:** A repository plants instructions in a project agreement.
  - **Mitigation:** every agreement's origin label is accurate (INV-7, INV-8), the opening paragraph says project agreements come from the repository, and project agreements carry the same trust as the project's own `CLAUDE.md`, which Claude Code already loads.
- **FM:** An agreement overrides a skill's approval gate, for example the design skill's Open Questions.
  - **Mitigation:** the precedence sentence in the opening paragraph (INV-13), and the reworded recommendations agreement, which asks one question when a gate requires it.
- **FM:** A shipped agreement leaks a person's name, a project name or a machine path.
  - **Mitigation:** the genericity test with three sources, each with a made-up-word positive control (Design decision 6), and the **Project-name check** on outbound sync in each consuming project.
- **FM:** A Windows console encoding crashes the hook on a non-ASCII character.
  - **Mitigation:** ASCII-only JSON (INV-2), and the last-resort exit 0 (INV-1).
- **FM:** The finish-install suite turns red because it pins the real `hooks.json` count.
  - **Mitigation:** listed in Files to touch, with the exact change in Extension Points.

## Open Questions for User

Both questions are answered; the user approved every recommended answer on 2026-10-05.

- [x] **Open Question 1 — the session-start envelope has not been checked against Claude Code's documentation.** The hook would print the same nested shape the plain-language guard already uses at prompt time, with the event name changed to session start. No source available to this design session confirms that shape for session start, or the size cap. **Recommendation: proceed with it.** Before the failing tests are frozen, the implementer reads the Claude Code hooks documentation for session start and records what it says under Uncertain Assumptions. Before the pull request leaves draft, one real session is opened with the plugin, the assistant is asked for the title of its first working agreement, and the answer goes in the pull request description.
  → **Answer (user, 2026-10-05, approved with the critic's correction):** proceed with the nested envelope. The implementation's FIRST step, before any test is frozen, is one harmless session-start trial. A temporary agreement holding a made-up phrase that exists nowhere else is placed where the plugin delivers it, a session is started, and the assistant is asked to repeat the phrase. The phrase is not committed. The result, and what the Claude Code hooks documentation says about the envelope and any size cap, are recorded under Uncertain Assumptions. If the trial fails, stop and escalate. The live check in the pull request description uses the same made-up phrase, never a rule title the session might already know from memory. The log line records what the hook printed, not what the host received.
- [x] **Open Question 2 — when one agreement file is damaged, should the others still be delivered?** The brief's failure line reads as "no output at all". That means one broken project file would also silence the plain-language rule. **Recommendation: skip only the damaged file and deliver the rest, with a log line naming it.** The brief's exact case, where the damaged file is the only one, still produces no output and is tested.
  → **Answer (user, 2026-10-05):** as recommended. Skip only the damaged file and deliver the rest; the case where the damaged file is the only one still produces no output and is tested.

## Critique

**Critic:** contract-critic
**Date:** 2026-10-05
**Verdict:** blockers-found

### Findings

- **[BLOCKER] The genericity test's fourth source cannot have the positive control the contract requires without writing a forbidden name into the plugin**
  - **What is wrong:** Design decision 6 says each of the four sources "has a positive control that plants a forbidden token in a temporary copy and must fail", and the TASK block says "Never write a forbidden name in plain text anywhere in the plugin". For source (d), the planted token must hash to one of the listed digests, so the test file has to hold the plain name. The only other option is a dummy word whose digest the control adds itself, and that proves the matching code, not the real digest list. As written, the two requirements cannot both be met, and the contract does not say which one gives way.
  - **Prior artifact ignored:** `MECHANISMS.md:50` (Project-name check: the established leak guard compares literal strings from a token list kept in the consuming project, precisely so the plugin never holds the names); `JOURNAL.md:47-52` (*A VERIFIED parser claim must be tested on the unfilled and the missing case*: a control has to exercise the real input, not a stand-in).
  - **Where in this contract:** `## Data Shapes → Design decisions behind the shapes`, item 6: "Each source has a positive control that plants a forbidden token in a temporary copy and must fail"; `## Implementation Handoff` TASK: "Never write a forbidden name in plain text anywhere in the plugin."
  → Addressed by: Design decision 6 (the digest source is removed; three sources remain, and each control plants a made-up word), Reused Mechanisms (Project-name check: the consuming project keeps its literal list), and the TASK block's genericity line.

- **[BLOCKER] The shipped agreement `recommendations-not-question-batches` contradicts the plugin's own design gate, and the delivered text tells the model to follow it in every action**
  - **What is wrong:** The agreement says to "proceed on it, recording each as a named assumption" and "Do not hand the user a menu of options", with direct questions kept only for "a decision others will see". The plugin's own `/design-first` says the opposite for contract approval, which is not visible to anyone else. The opening paragraph in Design decision 7 says "Follow them in every message and action". The contract never says which wins, so every session of every consuming project gets a standing instruction that undercuts the user-approval gate the plugin exists to enforce.
  - **Prior artifact ignored:** `skills/design-first/SKILL.md:162` ("Use the `AskUserQuestion` tool to resolve each Open Question … Do NOT guess answers"); `skills/design-first/SKILL.md:290` ("Open Questions MUST be answered by the user, never guessed"); the Data-First protocol's own phase rule "Ambiguous terms become Open Questions, never guesses".
  - **Where in this contract:** `## Data Shapes → Required content of the shipped agreements`: "`recommendations-not-question-batches.md` — do the analysis, … and proceed on it … Do not hand the user a menu of options"; Design decision 7: "Follow them in every message and action, starting with your first reply."
  → Addressed by: Required content (the recommendations agreement leads with a recommendation and asks one question when a skill's gate requires it), Design decision 7 (precedence sentence in the opening paragraph), INV-13, and a TASK test case asserting the sentence.

- **[WARN] The duplicate-delivery marker solves at run time a mode the plugin already refuses, and the two racing copies deliver different text**
  - **What is wrong:** The finish-install script treats `both` as a refusal ("every hook would run twice; remove one of the two"), and its readiness report already has a `no-duplicate-registration` check. Every other hook simply runs twice in that mode. This contract adds per-hook state, a time window and a race to paper over the same case for one hook only. Worse, the two runs are not equivalent. Under INV-7 the vendored copy reads one folder and labels everything shipped, while the plugin copy reads two folders. Whichever wins the claim decides what the model receives, so the delivered set is nondeterministic between sessions.
  - **Prior artifact ignored:** `.claude/scripts/auto_improve_finish_install.py:950-954` (`install-mode-both` refusal) and `:1121`/`:1131` (`no-duplicate-registration` readiness check); `VOCABULARY.md:40` (Install mode, `both`).
  - **Where in this contract:** `## Data Shapes → Design decisions`, item 5: "At most one of two concurrent runs delivers"; INV-10.
  → Addressed by: Design decision 5 and INV-10 (the marker, window and claim are removed; the install-mode refusal and the readiness check are relied on, and the residual risk is stated), INV-7 (a vendored copy stays silent, so the two runs can no longer differ), and Alternatives Option E.

- **[WARN] The 60-second window keyed on session id and source can suppress a legitimate delivery, and the marker's expiry protocol is not atomic**
  - **What is wrong:** A real duplicate arrives within milliseconds, but the window is 60 seconds. Any two separate starts with the same session id and source inside that window lose the second delivery, even though the context was rebuilt. Examples are back-to-back compactions, or two windows resuming one session. Which sources reuse a session id is not listed under `## Uncertain Assumptions`. The contract also does not say what happens when a marker for the key already exists but is older than the window. An "atomic exclusive create" fails on an existing file, so the run must delete or replace it, and that step is not atomic. The contract's own stated priority is "a missed one is not" accepted.
  - **Prior artifact ignored:** `JOURNAL.md:40-45` (*Do not rely on a host … in a form nobody has seen work*). Session-id reuse per source is host behaviour that nobody has observed here.
  - **Where in this contract:** INV-10: "A second run for the same session id and source within 60 seconds prints nothing"; `## Data Shapes → Design decisions`, item 5: "a rare double delivery is accepted, a missed one is not."
  → Addressed by: the removal of the marker and window (Design decision 5, INV-10). With no window, no legitimate delivery can be suppressed and there is no expiry step.

- **[WARN] Under vendoring, project-only agreements are labelled "from the plugin", which defeats the origin-label mitigation**
  - **What is wrong:** INV-7 says that when the two folders resolve to the same directory, "every file counts as `shipped`". In a vendored consumer, that folder holds the project's own agreements beside the copied ones. So a repository-authored file is presented as "(from the plugin)". The prompt-injection mitigation rests entirely on that label. The opening paragraph also calls every delivered file "the user's standing rules". That is stronger framing than a project `CLAUDE.md` gets, and the mitigation claims the two are equal.
  - **Prior artifact ignored:** `JOURNAL.md:54-59` (*A root locator can return the consumer itself under vendoring*). INV-7 heeds this lesson for reading, but not for labelling.
  - **Where in this contract:** INV-7; `## Failure Modes & Mitigations`: "the delivered text labels each agreement's origin, and project agreements carry the same trust as the project's own `CLAUDE.md`".
  → Addressed by: INV-7 (vendored delivery is not supported, so the single-folder case only arises in the plugin's own checkout, where "from the plugin" is accurate), INV-8 (labels are always accurate), and the opening paragraph's precedence sentence, which ranks agreements below a project's own instructions.

- **[WARN] "Always kept" plus same-name override makes the size limit unbounded**
  - **What is wrong:** The always-kept set goes by slug (INV-3), and a same-name project file replaces the shipped one (INV-8). So a project `plain-language.md` of any length, with any content, is always delivered and logged `over-limit-kept`. The drop order then removes every other agreement, and the text can exceed the host cap that Design decision 4 sizes the default against. The Concept says plain-language "cannot be removed from that set by configuration", yet one file can replace its content entirely.
  - **Prior artifact ignored:** `MECHANISMS.md:52` (Guard rules file). The fail direction and the limits are meant to be stated and proved, not left to an unexamined interaction between two rules.
  - **Where in this contract:** INV-3, INV-5, INV-8; `## Business Concept`: "`plain-language` is always kept and cannot be removed from that set by configuration".
  → Addressed by: INV-3 and INV-8 (only the shipped plain-language text is always kept, and a same-named project file is skipped), the AgreementsRules row (no always-keep setting), and the Always-kept agreement term.

- **[WARN] Design decisions 1 and 2 contradict each other on the current-directory fallback**
  - **What is wrong:** Design decision 1 falls back to "the current directory when that variable is unset". Design decision 2 says agreements "must never pick up the current directory's or the home folder's `.claude`". Meanwhile `state_dir()` and `logs_dir()`, reused as-is, fall back to the home folder. So one run would mix three different fallbacks: agreements from the working directory, and the marker and log under the home folder.
  - **Prior artifact ignored:** `.claude/hooks/_project_paths.py:44-52`, `:125-149`; `MECHANISMS.md:42` (Two-layer Claude path resolution: runtime state "resolves through `project_dir()` alone"); `VOCABULARY.md:29` (Claude data root, rank 2 is `$PWD`).
  - **Where in this contract:** `## Data Shapes → Design decisions`, items 1 and 2.
  → Addressed by: Design decisions 1 and 2 (no current-directory fallback; with the project variable unset only shipped agreements are delivered). `state_dir()` is no longer used. The log keeps the `logs_dir()` fallback every hook here shares, stated in the Events note.

- **[WARN] Two of the four genericity sources are close to empty where the test actually runs**
  - **What is wrong:** Source (c) reads `.claude/.project-tokens.json` "under each candidate root". The plugin's own copy is a template with `"tokens": []`, so it adds nothing in the plugin checkout, which is where the shipped files live and where this suite runs. "Candidate root" is also undefined, because Design decision 2 refuses `claude_roots()`. Source (d) does not say which names go into the digest list or how text is split into words. A possessive, a dotted name, or a joined capitalised name would each slip past a whole-word match. And a SHA-256 digest of a short lowercase name can be reversed with any list of names. So "without contaminating the plugin" overstates what the digest list hides.
  - **Prior artifact ignored:** `.claude/.project-tokens.json:6` (`"tokens": []`); `MECHANISMS.md:50` (Project-name check: the token list belongs to the consuming project).
  - **Where in this contract:** `## Data Shapes → Design decisions`, item 6, sources (c) and (d).
  → Addressed by: Design decision 6. Source (d) is gone. Source (c) is defined as the project's own token file and is read only when non-empty; the contract states plainly that it adds nothing in the plugin checkout. "Candidate root" no longer appears.

- **[WARN] The plain-language agreement is called the full rule, but it leaves out two of the four faults the checker stops on**
  - **What is wrong:** The five required labels do not cover the 35-word sentence limit or the three-long-dash rule. The shipped checker weighs and stops on both. The Concept and the End-User View still say the agreement "tells the assistant the whole rule before it writes anything".
  - **Prior artifact ignored:** `.claude/hooks/plain-language-guard.rules.json:8-9` (`max_sentence_words`, `max_em_dashes_per_sentence`) and `:13-18` (`fault_weights` includes `stacked_dashes` and `sentence_length`).
  - **Where in this contract:** `## Data Shapes → Required content`: "five labelled rules"; `## End-User View → Connections`: "The agreement tells the assistant the whole rule".
  → Addressed by: Required content (seven labels, adding the thirty-five-word sentence limit and the three-long-dash limit), the End-User View Connections paragraph, and the TASK case for all seven labels.

- **[WARN] The mitigation for "the host ignores the envelope" cannot detect it, and the live check cannot tell the hook from memory**
  - **What is wrong:** The `delivered` log line records what the hook printed, not what the host consumed, so it reads identically whether the envelope works or not. The live check asks the assistant for "the title of its first working agreement". In the first consuming project, the same rule already sits in the session's own memory and project instructions, so a correct answer does not prove the hook delivered anything. Both checks are also scheduled after the code exists.
  - **Prior artifact ignored:** `JOURNAL.md:40-45` (*… prove it with one harmless invocation before the code depends on it*).
  - **Where in this contract:** `## Failure Modes & Mitigations`: "the `delivered` log line, plus one live session check before approval of the pull request"; Open Question 1.
  → Addressed by: Open Question 1's answer and the TASK block's first constraint (a made-up-phrase trial before any test is frozen; the same phrase in the pull request check), and the Events table (the line is `AgreementsPrinted` and says it records only what was printed).

- **[WARN] The mitigation for a stale vendored agreement relies on a sync entry the contract says does not exist**
  - **What is wrong:** The mitigation is "the sync tool keeps vendored copies equal". The Adjacent Areas row says a vendored consumer "needs an `.claude/agreements` tree entry in its own sync configuration" that this change does not add. Under the ownership model, an unnamed file is local and is never synced. So the copies are not kept equal, and the mitigation does not hold.
  - **Prior artifact ignored:** `MECHANISMS.md:44` (Plugin registry ownership model: "a file … that no tree's `files` array names is a local asset by default … never synced"); `JOURNAL.md:61-66` (*Detect an install mode by what the sync actually delivers*).
  - **Where in this contract:** `## Failure Modes & Mitigations`: "accepted; the sync tool keeps vendored copies equal".
  → Addressed by: INV-7 and Failure Modes (vendored delivery is not supported in this version; the false sync claim is removed), Reused Mechanisms (Plugin registry ownership model), Non-Goals, and the Adjacent Areas row.

- **[WARN] One acceptance criterion has no pinning test, and one departure from the brief is not raised as an Open Question**
  - **What is wrong:** The brief's third criterion names the five generic habits. The planned case, "every real shipped agreement appears in the envelope", walks whatever files exist, so deleting one stays green. Departure 3 (a missing project folder is silent, with no log line) changes the brief's sixth criterion's literal text. Unlike departure 2, it is not under `## Open Questions for User`.
  - **Prior artifact ignored:** `.claude/work-items/2026-10-05-working-agreements-injection.md:29` and `:32`.
  - **Where in this contract:** `## Implementation Handoff` TASK cases: "every real shipped agreement appears in the envelope"; `## Where this contract departs from the brief`, item 3.
  → Addressed by: INV-14 and the TASK case naming all six required files; departure 3, now stated as a deliberate, reasoned departure that the user approved.

- **[NIT] The renamed count leaves a lying test name.** After the change, `test_the_real_plugin_hooks_json_yields_exactly_its_seventeen_registrations` and its messages ("17 registrations (16 files)", `test_auto_improve_finish_install.py:1859-1872`) will be wrong. INV-15 counts only `def test_` lines (`test_plugin_manifests.py:370`), so a rename is free, but the TASK block does not ask for one.
  → Addressed by: Extension Points and the TASK block (renamed to `..._eighteen_registrations`, messages updated).
- **[NIT] The size budget does not say what it counts.** It is unclear whether the opening paragraph, the per-agreement headings and the closing "dropped" line count toward `max_characters`. The closing line is written after the dropping, so it can push the text past the limit.
  → Addressed by: INV-5 (the whole text counts, and the size is re-measured with the closing line after each drop) and the AgreementsRules row.
- **[NIT] The size estimate does not add up.** Six files "under about 1,200 characters" each come to up to 7,200 characters before headings, not the "about 5,000 to 6,000" stated in Design decision 4.
  → Addressed by: Design decision 4 (per-file sizes, a recomputed total, and a test that the shipped set fits with nothing dropped).
- **[NIT] "A sixth rules file" miscounts.** `MECHANISMS.md:52` names five rules files, including `integration-check.rules.json`, which this plugin does not ship. The plugin's `hooks/` holds four generic data files (`README.md:255`).
  → Addressed by: Reused Mechanisms (Guard rules file: "one more rules file"; four generic data files today, five after).

### Applicable journal entries

- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** — heeded by `## Extension Points` (the command reuses the 17 working registrations' exact form). The analogous envelope risk is only partly addressed: see the WARNs on the 60-second window and on the live check.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by the TASK cases (rules file missing, malformed, and omitting `plain-language`). Violated in spirit by source (d)'s control, see the first BLOCKER.
- **2026-10-04 — A root locator can return the consumer itself under vendoring** — heeded by INV-7 for reading. Not addressed for origin labelling, see the vendoring WARN.
- **2026-10-04 — Detect an install mode by what the sync actually delivers** — heeded by the Adjacent Areas row on the consumer sync configuration. Contradicted by the stale-agreement mitigation, see the sync WARN.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by Design decision 4 (fail-soft direction proved with the rules file renamed away).

### What the critic did not check

- The Claude Code hooks documentation for the session-start envelope and any context-size cap: this critic has no documentation or network tool, so Open Question 1 stays open exactly as the contract states it.
- The cross-area scan: no shell, and `.claude/area-mapping.json` has an empty `areas` set, so the hand-derived Adjacent Areas table was taken as given.
- North-star alignment: the plugin has no `.claude/north-stars/` directory.
- Verified as stated, with no finding: version `0.3.2` in all five declarations (`plugin.json:4`, `.claude-plugin/plugin.json:5`, `.claude-plugin/marketplace.json:8` and `:15`, `.cursor-plugin/plugin.json:3`); "16 enforcement hooks" in both Claude manifest descriptions; 17 registrations from 16 files in `hooks.json` with no `SessionStart` event; the envelope at `plain-language-guard.py:636-643`; the real-`hooks.json` test at `test_auto_improve_finish_install.py:1859` pinning 17; event-generic reading at `auto_improve_finish_install.py:1146`; twelve README variables today (`README.md:106-124`), so thirteen with eleven kill switches after the change; both cited follow-up stubs exist on disk.

## Lessons referenced

- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** — heeded by Open Question 1 and the live session check. The analogous risk here is the session-start envelope. The command string reuses the exact form the 17 working registrations already use.
- **2026-10-04 — A root locator can return the consumer itself under vendoring** — heeded by INV-7. A hook copy whose own folder is inside a consuming project would treat the project's folder as the shipped one and mislabel project files, so a vendored copy stays silent and labels stay accurate.
- **2026-10-04 — Detect an install mode by what the sync actually delivers** — heeded by Reused Mechanisms (Plugin registry ownership model) and INV-7. No sync tree delivers `.claude/agreements`, so vendored delivery is not supported rather than assumed to stay current.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by Design decision 4 and the README task: the stated fail-soft direction is tested with the rules file renamed away.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by the rules-file tests (renamed away, malformed) and by the genericity controls, each of which runs its real matching code on a planted made-up word.

Orthogonal to north-stars: none. This repository has no `.claude/north-stars/` directory, which matches the brief's pre-grade.

## Implementation Handoff

### 1. Working-agreements hook, agreement files, tests and docs (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/hooks/working-agreements.py`
- `.claude/hooks/working-agreements.rules.json`
- `.claude/hooks/tests/test_working_agreements.py`
- `.claude/agreements/plain-language.md`
- `.claude/agreements/one-worktree-per-change.md`
- `.claude/agreements/shared-repository-changes-through-pull-requests.md`
- `.claude/agreements/one-line-commands-for-the-user.md`
- `.claude/agreements/stop-means-stop.md`
- `.claude/agreements/recommendations-not-question-batches.md`
- `.claude/hooks/hooks.json`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `README.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`

**Pre-written TASK block:**
```
TASK: Deliver the session-start working-agreements hook as specified: working-agreements.py,
      its rules file, the six shipped agreement files, the SessionStart registration, the
      hook test suite, the finish-install real-hooks.json test update, the README edits and
      the 0.3.2 -> 0.4.0 bump in all five declarations.
CONTEXT: concept contract at .claude/concepts/2026-10-05-working-agreements-session-start.md
FILES: as listed under Files to touch
CONSTRAINTS:
  - FIRST STEP, before any test is frozen (Open Question 1): one harmless session-start
    trial. Put a temporary agreement holding a made-up phrase that exists nowhere else where
    the plugin delivers it, start a session, ask the assistant to repeat the phrase. Never
    commit the phrase. Read the Claude Code hooks documentation for SessionStart too. Record
    the trial result, the documented envelope and any context-size cap in the contract's
    Uncertain Assumptions. If the trial fails or the documentation contradicts INV-2, stop
    and escalate. The pull request's live check uses the same made-up phrase.
  - Then run through /tdd-first in this one branch. senior-test-engineer writes the RED
    cases first; each must fail on an assertion, never on an import.
  - Test style: a plain runnable script like test_plain_language_guard.py, running the hook
    as a subprocess with a SessionStart payload and CLAUDE_PROJECT_DIR set to a temp folder.
    For shipped-folder cases, copy the hook and its helper modules into a temp .claude/hooks
    beside a temp .claude/agreements.
  - Cases, at least: each of the six REQUIRED file names (INV-14) exists in the plugin's
    .claude/agreements and appears in the envelope, checked by name, never by looping over
    whatever files exist; the seven plain-language labels are present; the precedence
    sentence (INV-13) is in the opening paragraph; shipped plus project both arrive, each
    with its accurate origin label; a project file named like a shipped one is skipped and
    logged, and the shipped one is delivered; a project plain-language.md never displaces
    the shipped one; missing shipped folder; missing project folder is silent and logs
    nothing; CLAUDE_PROJECT_DIR unset reads no project folder; unreadable file (a directory
    carrying a .md name); each malformed kind (empty, no heading, heading only, invalid
    UTF-8); a bad file beside good ones; the damaged file as the only file gives no output;
    the shipped set alone fits the default limit with nothing dropped; over the limit drops
    project agreements first and keeps plain-language, with the closing line counted;
    plain-language alone over the limit is still delivered; rules file renamed away; rules
    file malformed; a vendored copy (no plugin manifest above it) prints nothing and logs
    vendored-unsupported; the escape hatch; empty or garbage stdin; ASCII-only output;
    the log line says printed; every failure path exits 0 with empty stderr and a log line.
  - Genericity test per design decision 6: three sources, each with a positive control
    that plants a made-up word. Never write a real forbidden name anywhere in the plugin.
  - Write the agreements from the required-content list; distil, never copy a memory file.
  - In test_auto_improve_finish_install.py change only the real-hooks.json test: 18
    registrations from 17 files, a fixture holding the new hook file, and rename it to
    test_the_real_plugin_hooks_json_yields_exactly_its_eighteen_registrations with its
    messages updated. Add or remove no def test_ method (README INV-15).
  - README: hook inventory, the components table, the "What is included" tree (agreements/
    folder), Quick start step 5, the env-variable table and its count sentence, and a short
    "Working agreements" subsection: how a project adds one, that a same-named project file
    is skipped, that project instructions and skill gates win, and that vendored delivery
    is not supported in this version. Recount every number from the tree.
  - Update "16 enforcement hooks" in both Claude manifest descriptions to the recounted figure.
  - Branch already exists; deliver as a draft pull request. Never push to master.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-05-working-agreements-session-start.md
  contract_status: approved
```

### 2. Scope note on review

There is one mergeable block, because the hook, its files, the registration, the docs and the version bump would not be useful merged apart. Review runs in the outer chain that `/flow` already drives: the code reviewer and the test-suite reviewer after GREEN, then verification. No separate review-gate block is declared, so the loop dispatches exactly one sub-task. There is no frontend work and no migration. After implementation, the data architect appends the Session-start context delivery entry to MECHANISMS.md and the four terms to VOCABULARY.md, both in the Universal tier.

## Review checklist (filled in after implementation)

- [x] Implementation matches Data Shapes exactly (divergences listed under Implementation notes below; no DeliveryPlan object, fields go to log lines)
- [x] Reused Mechanisms are actually reused (no parallel implementations introduced; the rules file is read from the hook's own folder, a deliberate narrowing of the shared helper)
- [x] New Mechanisms promoted to `MECHANISMS.md` (Session-start context delivery, Universal tier, 2026-10-05)
- [x] New vocabulary terms promoted to `VOCABULARY.md` (Working agreement, Shipped agreement, Project agreement, Always-kept agreement, Universal tier, 2026-10-05)
- [x] README counts match the tree (checked by the manifest suite and by a reviewer recount)
- [x] The made-up-phrase trial result is recorded in Uncertain Assumptions. The end-to-end live check of the real hook (shipped plus project agreement, startup source) passed on 2026-10-05 and is described in the pull request; the resume, clear and compact sources remain an assumption.
- [x] `Status` flipped to `implemented`

### Implementation notes (post-review, 2026-10-05)

Where the built hook departs from the Data Shapes and invariants above. The registry entries describe the built behaviour.

- **Closing-line bound and the hard final check (INV-5).** The closing line names at most three dropped agreements with their paths, and the rest collapse to a count per folder. If the text still exceeds the limit after every allowed drop, a counts-only closing line replaces it when that is shorter. Anything still over the limit after that is because of the shipped plain-language agreement, which is never cut, and it is logged `over-limit-kept`.
- **Rules file: own folder only, and a clamp (Design decision 4).** `working-agreements.rules.json` is read only from the hook's own folder, not through `hook_file()`'s wider search. A configured `max_characters` is clamped to 9500, because a live trial on 2026-10-05 showed the host loses hook text over about 10000 characters. A missing or malformed file, or a value that is not a positive whole number, falls back to 9000 and is logged.
- **Inline path fallback (Design decision 2).** When `_project_paths.py` cannot be imported, the hook uses its own inline copies of `project_dir()` and `logs_dir()` (the project folder from `CLAUDE_PROJECT_DIR`, the log under the project or the home folder), so it still delivers rather than going silent.
- **Project heading neutralisation (INV-8).** A "(from the ...)" origin label is stripped from a project agreement's title, and a title holding nothing else is malformed. Every line of a project body is shown quoted with a leading greater-than sign, and a project title is normalised, so project text cannot forge a plugin section or a top-level heading.
- **Case-insensitive name match (INV-8).** A project file is skipped as `shadows-shipped` when its name matches a shipped file's name ignoring case, not only on an exact match.
- **No DeliveryPlan object.** The DeliveryPlan value object was never built. Its fields go straight to log lines: printed slugs, characters and limit; each skipped file with its reason; each dropped agreement; and over-limit-kept.
