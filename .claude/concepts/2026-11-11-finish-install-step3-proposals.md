# Concept Contract — /auto-improve-finish-install proposes the three per-project files (Quick start step 3)

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-11
**Requested by:** user
**Status:** approved
**Work Item Brief:** .claude/work-items/2026-11-11-21-finish-install-step3-proposals.md
**Tracking issue:** #21
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. The lifecycle and the management commands are in `.claude/templates/concept-contract.md`. Parent contract: `.claude/concepts/2026-10-04-auto-improve-finish-install-skill.md`. Detail stub: `.claude/concepts/followups/2026-10-04-auto-improve-finish-install-step3-inference.followup.md`.

---

## Business Concept

- **What is this thing, in domain language?**
  `/auto-improve-finish-install` gains a stage for Quick start step 3. After the project profile is filled (step 4), it proposes content for the three other per-project files: the area map (`.claude/area-mapping.json`), the pull-request module tags in the title conventions (`.claude/work-item-conventions.json`, `prTitle.map` and `prTitle.order` only) and the project-name token list (`.claude/.project-tokens.json`). Every proposal carries its evidence. One plan covers all three files, one confirmation releases it, and one plan hash binds the write, through a new subcommand, `project-files`, of `auto_improve_finish_install.py`. A file the team already wrote is never changed. A file with no evidence stays as scaffolded, and the report says so. Area and module proposals come only from **authored** profile slots, so step 3 reuses step 4's confirmed answers instead of inferring the repository a second time. Tokens come from a closed set of four sources and pass a set of exclusion rules. The script proposes fewer tokens rather than guessed ones, and it writes only the tokens the operator names.

- **Existing VOCABULARY.md terms that apply:** **Placeholder slot**, **Install mode**, **Vendored asset**, **Plugin repository**, **Installed plugin root**, **Memory scope** (an empty token list lowers every capture candidate). Registered mechanisms: **Project-name check**, **Project profile**, **Preview-hash apply**.

- **New terms proposed for VOCABULARY.md (Universal tier):**
  - **Unauthored project file** — one of the three step-3 files whose project-shaped part is still exactly as the doctor scaffolds it: `areas` is an empty object (area map); `prTitle.map` and `prTitle.order` are both empty lists (conventions); `tokens` is exactly `[]` (token list). It is the only kind of step-3 file `/auto-improve-finish-install` may write, and it writes only that part. Any other content makes it an **authored project file**, which is never changed. This is the file-level counterpart of a **Placeholder slot**.
  - **Token proposal** — a string the script found in one of four closed sources (`project-name`, `frontend-app`, `database`, `source-prefix`) and offers for the project-name token list, with its evidence. Excluded strings are listed separately, each with a named reason. Only the operator's explicit `--token` puts a proposal into the list. Named "proposal", not "candidate", so it cannot be confused with a memory **Capture candidate**.

---

## End-User View

**Category:** Getting Started

### What the end user sees
After the profile stage, the assistant shows one more short table. It covers three setup files: the map of the repository's areas, the labels used in pull-request titles, and the list of names that must never leak into the shared plugin. Each proposed entry sits next to the profile answer or the file that suggested it. Names it would not propose are listed with the reason. The operator picks the names to keep and confirms everything in one reply.

### What it does for the end user
Today these three files stay blank unless someone reads the setup guide and writes them by hand. A blank area map makes every plan land in one "uncategorized" bucket. A blank names list means the plugin's shared copy is not protected from this project's names. The command fills them from facts the team already confirmed, and it never invents a name.

### Connections to the rest of the system
It reads the project profile the previous stage just filled, and the database names the database protection setup may already hold. The area map feeds the plan reviewer's area checks. The title labels feed the shipping step. The names list feeds the shared-plugin sync check, the memory sharing rule and the registry check.

### Implications
The first names written change how shared memory behaves. With no list, every memory the project saves stays private to the project. With a list, a memory stays shareable unless it contains a listed name. So a short list can let a project name slip out in a memory it does not mention. The command says this in plain words and needs a separate yes for it. The command can only find names that appear in the repository. Vendor names and handbook titles are left for the team to add.

### Measures
It never changes a file the team already wrote. It never writes a name the operator did not pick. It drops names that are too short, too generic, built into the database server itself, or already used by the plugin itself, because any of those would stop every sync. It shows the exact change, refuses if anything moved between the preview and the yes, keeps a dated copy of each changed file, and writes all three files or none. Running it again changes nothing.

### How it could be improved
It could suggest vendor names from dependency lists, and it could add names to a list the team already started. Today the command only advises on an existing list and leaves the edit to the team.

---

## Data Shapes

All shapes are the script's JSON input and output, so they are value objects. Nothing is stored apart from the three files the operator approves and their backups.

### Entities

| Name | Fields | Invariants | Ownership (aggregate) |
|------|--------|------------|-----------------------|
| Area map file (existing) | `areas`: slug → {description, patterns[], seed_adjacency[]?}; other keys | Written only when unauthored. Only the `areas` value span changes, and every other byte is unchanged. The written file re-reads through `derive_area.load_area_mapping(path)` to exactly the proposed slugs and patterns. `seed_adjacency` is never written | consuming project |
| Title conventions file (existing) | `prTitle.map[]` {tag, globs[], means}, `prTitle.order[]`; other blocks | Only the value spans of `prTitle.map` and `prTitle.order` change, and only when both are empty. `issueTitle`, `issueLink`, `contractLanding` and every other byte are unchanged. `land_contract.module_tag_reading` on a sample path under each root returns that root's tag | consuming project |
| Token list file (existing) | `tokens[]`, `allowed[]`, `project`, `_`-prefixed comments | Written only when `tokens` is exactly `[]`. Only the `tokens` value span changes. The new list is exactly the operator's `--token` values in the order given, with letter-case duplicates folded. `allowed` and `project` are never written. It re-reads through `memory_boundary.token_list` and `_registry_layout.load_project_tokens` to that list | consuming project |

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Evidence (extended) | path, reason (closed set gains `profile-slot`), line (optional) | the citation beside every proposal |
| ModuleProposal | kind (closed set: `backend`, `frontend`, `tests`, `migrations`, `auth`, `safety-critical`), root, slug, tag, patterns, globs, description, evidence | one proposed area. The four kinds `backend`, `frontend`, `tests` and `migrations` also become one prTitle module each |
| TokenProposal | text, source (closed set: `project-name`, `frontend-app`, `database`, `source-prefix`), evidence[], already-listed (bool) | one row of the token table |
| TokenExclusion | text, source, reason (closed set: `too-short`, `generic-word`, `system-database`, `in-plugin-text`, `template-name`, `disposable-database`, `invalid-text`), message | a found string the script will not propose |
| ProjectFileProposal | file (closed set: `area-map`, `conventions`, `tokens`), path, values (the proposed modules or tokens), basis (closed set below), evidence[], note, advice (what would have been proposed, for `kept-authored`), unified diff, planned bytes | one file's entry. It is the profile's slot-proposal shape `{slot, values, basis, evidence, note}` with `file` in place of `slot` |
| ProjectFilesPlan | plugin-root, plugin-text-check (`checked` / `unverifiable`), files[3], modules[], token proposals[], exclusions[], source-notes[] (a skipped token source and why: `rules-unreadable`, `guard-unreadable`), not-inferred (fixed list: vendor names, handbook file names), narrows (bool), narrowing-statement, profile-note (closed set: `profile-missing`, `profile-has-placeholders`, `roots-authored-none`, or absent), backup-dir, gitignore-hint, plan-sha256 | the output of `project-files` without `--apply` |

**File bases (closed set).** The first three are the profile's own basis values, with the same meaning:
- `inferred`: unauthored, with evidence.
- `none-found`: unauthored, nothing found. The file is left as scaffolded and the note names why.
- `kept-authored`: the proposals are shown as advice only.

Four values are file-only:
- `scaffold-missing`: the file is absent. The remedy is `plugin_doctor.py --fix`.
- `unrecognised`: the file is not strict JSON, has duplicate keys or a byte order mark, or the expected member is missing or of the wrong type. It is never written.
- `skipped`: named by `--skip-file`.
- `nothing-confirmed`: tokens were proposed but no `--token` was given.

The profile's `needs-answer` basis is not used, because a step-3 file has no question that the operator's token choice does not already answer.

### Events

Not applicable. Reason: a single-shot command-line tool with no subscribers. Its outcome is its JSON and its exit code.

### Commands

| Name (imperative) | Handler | Payload | Possible rejections |
|---|---|---|---|
| ProposeProjectFiles | `auto_improve_finish_install.py project-files` | `--project`, `--token` (repeatable), `--skip-file area-map\|conventions\|tokens` (repeatable), `--claude-home` | `project-unreadable`, `plugin-source-checkout`, `token-invalid` |
| ApplyProjectFiles | `project-files --apply` | as above, plus `--expect-sha256`, `--confirm-narrowing` | all of the above, plus `changed-since-preview`, `narrowing-unconfirmed`, `write-failed` |

One new refusal code, `token-invalid` (exit class 2). A `--token` value is refused when it is empty, longer than 128 characters, holds a control or format character, or meets an exclusion rule (`too-short`, `generic-word`, `system-database`, `in-plugin-text`). The message names the rule. Every other code already exists. A file problem is a per-file basis, never a run refusal, so one unrecognised file does not block the other two. A token-source problem is never a run refusal either. When the guard rules file is present but unreadable, `_read_db_rules` returns `rules-unreadable`, and the guard file's patterns may not load (`guard-unreadable`). Either way, `project-files` turns the result into a source note and skips the `database` source. The refusal's message is copied into the note, and the other sources and files go on. These two codes are therefore never returned by `project-files`.

### Design decisions

**1. Evidence for areas and modules: authored profile slots only.** The project's own `.claude/project-profile.md` is read through the profile stage's own reader, `_load_profile_ctx`, which is reused by call. That reader can tell the three slot states apart, which `load_slot` alone cannot, because `load_slot` returns `()` for a placeholder, an authored `none` and a missing row (`pr_merged.py:95-101`). So:
- `ctx.kind(slot)` (placeholder / authored / missing) decides the state.
- `load_slot` reads the values of an `authored` slot only.

One root gives one ModuleProposal, for each authored root in `backend.roots`, `frontend.roots`, `test.roots`, `migration.root`, `auth.roots` and `safety-critical.roots`. The profile-note is decided in this order:
- `profile-missing`: there is no profile, or `_load_profile_ctx` refuses with `template-missing`.
- `profile-has-placeholders`: no root is authored, and at least one of the six slots is a placeholder or missing. The note says "fill the profile first (step 4)".
- `roots-authored-none`: all six slots are authored and none holds a root. The note says "the profile says this project has no such roots".

In all three cases the area map and the conventions are `none-found`. With at least one authored root, there is no profile-note.

Naming rules:
- The slug is the kind when the slot holds one root, and `<kind>-<last folder segment>` otherwise. It is lowercase `[a-z0-9-]`, and a collision gets `-2`, `-3` in sorted root order.
- The tag is the slug in upper case.
- Every root is normalised once, before both uses:
  - every backslash becomes `/`;
  - repeated `/` collapse to one;
  - a leading `./` is removed, and any trailing `/` is removed.
- A root that is empty after normalisation, `.`, or holds `..` or `*` gives no proposal, and the note names it.
- The area pattern is the normalised root, lowercased, plus `/...`.
- The prTitle glob is the normalised root, case kept, plus `/**`.
- `order` follows the kind order above, then the slug.
- An `auth` or `safety-critical` area's description says it is safety-critical.
- `seed_adjacency` is never proposed.

**2. Evidence for tokens: four closed sources.**
- `project-name`: the authored `project.name` slot.
- `frontend-app`: `projects` keys in an `angular.json` at the repository root or in an authored frontend root, and the `name` field (npm scope removed) of `package.json` in each authored frontend root.
- `database`: the names `_database_proposals` finds in tracked configuration files, plus the authored `protected_databases` of the project's own database-guard rules file, read by `_read_db_rules`. **`_database_proposals` is never used unfiltered.** Every name from either list is first checked against `SYSTEM_DATABASES`, a new constant in the script holding the names below, compared case-insensitively:
  - SQL Server: `master`, `model`, `msdb`, `tempdb`, `mssqlsystemresource`, `distribution`, `ssisdb`, `reportserver`, `reportservertempdb`;
  - PostgreSQL: `postgres`, `template0`, `template1`;
  - MySQL and MariaDB: `mysql`, `sys`, `information_schema`, `performance_schema`;
  - MongoDB: `admin`, `local`, `config`.

  A match is a TokenExclusion with reason `system-database`. This filter runs whatever state the plugin-text check is in. For database protection a system name was harmless; as a token it would stop every outbound sync.

  Disposable names are excluded with the guard's own patterns. The guard-file search (the plugin root's guard first, then the project's) is today written inline in `_plan_protect_databases` (`auto_improve_finish_install.py:4104-4112`). It moves into a shared helper, `_disposable_patterns_for(project, root)`, which returns the patterns, or none together with the path it tried. `_plan_protect_databases` and `project-files` both call it, and the behaviour of `protect-databases` does not change: its existing tests stay green. When the patterns cannot be loaded, or the rules file is `rules-unreadable`, the source is skipped and a source note says so.
- `source-prefix`: the first dotted segment shared by two or more tracked `*.csproj` file names.

Vendor names and handbook file names are never inferred. They are printed under `not-inferred` for the operator to add.

**3. Exclusion rules** (applied to candidates and to every `--token`). The rules compare case-insensitively, because the three readers match that way.
- `too-short`: fewer than 4 characters.
- `generic-word`: the whole token equals, case-insensitively, one entry of `GENERIC_WORDS`, a new constant holding exactly these words:
  - **application layers:** `app`, `apps`, `application`, `api`, `apis`, `web`, `www`, `site`, `client`, `clients`, `server`, `servers`, `frontend`, `backend`, `front`, `back`, `portal`, `admin`, `worker`, `service`, `services`, `ui`;
  - **folders:** `src`, `source`, `lib`, `libs`, `main`, `master`, `core`, `common`, `shared`, `util`, `utils`, `test`, `tests`, `spec`, `docs`, `data`, `database`, `config`, `default`, `local`, `public`, `private`, `static`, `assets`, `scripts`, `tools`, `build`, `dist`;
  - **examples:** `project`, `projects`, `demo`, `sample`, `example`, `template`;
  - **plugin and agent words:** `plugin`, `plugins`, `claude`, `agent`, `agents`, `skill`, `skills`, `hook`, `hooks`.

  A word that is not listed is not generic. Changing the list is a contract amendment.
- `system-database`: equals an entry of `SYSTEM_DATABASES` (decision 2), case-insensitively.
- `template-name`: `TEMPLATE_DATABASES`.
- `disposable-database`.
- `invalid-text`: a line break, a control character, or more than 128 characters.
- `in-plugin-text`: the text occurs in a text file (at most 1 MB) under the separate plugin root's `skills/`, `agents/`, `.claude/hooks`, `scripts`, `templates`, `references`, `agreements` and `addons`, or in its registry root files. A vendored copy carries the same text, so such a token would stop every outbound sync with exit 5 and flag every Universal registry entry. The plugin root comes from `_separate_plugin_root`. When no plugin root resolves, the check is `unverifiable`. The plan says so, and the proposals are still shown, already filtered by every other rule.

**4. The narrowing statement.** Writing the first tokens into an empty list changes `memory_boundary.apply_scope_safety` (`memory_boundary.py:584-595`). Before, every memory **Capture candidate** is lowered to `project`. After, only a capture candidate that contains a listed token is lowered. The plan therefore sets `narrows` and carries a plain statement: today every memory item this project captures stays project-scoped because the list is empty; after this change an item stays global unless it contains a listed name, so a name missing from the list can leave in a global item; the sync's project-name check starts checking the listed names. The apply needs `--confirm-narrowing`, as `protect-databases` already does, or it is refused as `narrowing-unconfirmed`.

**5. Apply.** The plan hash is `_plan_digest` over, in the fixed file order, each file's old bytes (or `absent`) and its planned bytes, then the sorted `--token` list and the sorted `--skip-file` list. The apply works in this order:
1. It recomputes the plan and compares the hash.
2. It checks the `.claude` folder with `_linked_folder_refusal` and refuses a target that is a symbolic link (`write-failed`).
3. It re-reads every target.
4. It writes every `inferred` file (for tokens, only when at least one `--token` is confirmed) through `_preview_apply.stage_and_replace`. All files are written or none is.

**Backups follow the registry migration's convention, not a new one.** Their folder is `.claude/cache/finish-install/<UTC yyyymmddTHHMMSSZ>/backup/`, with a `-2`, `-3` suffix on the stamp if the folder exists. This mirrors `.claude/cache/registry-migrations/<id>-<UTC>/backup/`. `.claude/cache/` is the folder the plugin already keeps out of git (`.gitignore:36`). The apply result carries `backup-dir`, the rollback line (copy each backup back over its file), and `gitignore-hint: ".claude/cache/"`. The skill passes the hint on when the project's `.gitignore` does not cover the folder, in the same way it passes on the settings backup hint. The settings-backup convention (`<name>.bak-<stamp>` beside the target) is not used here, because `stage_and_replace` writes one backup folder for a multi-file plan.

Nothing is written when no file is in a writable state. The JSON values are spliced in place: the member's value span is found with `_open_box` and `_member_named`, and only that span is replaced. The planned bytes are parsed strictly again before the hash is computed.

**6. Doctor.** `plugin_doctor.py` gains `.claude/.project-tokens.json` as a `scaffold` requirement with `authored=True`. Its SCAFFOLDS text holds the same keys as the shipped `.claude/.project-tokens.json`, and a parity test checks this. The doctor still never overwrites a file. The `NEEDS YOU` line now names `/auto-improve-finish-install`, because the skill now proposes every file that line covers.

**7. Order in the skill.** The new stage runs after the profile stage and before the hooks stage, because it reads the confirmed profile. Its table has one row per file with the basis and the diff, one row per area or module, and one row per token proposal or exclusion. Every source note is shown too. The operator answers once with the tokens to keep, any files to skip, and yes or no to the narrowing statement when it applies.

---

## Reused Mechanisms

- **Preview-hash apply** — **extended by** the subcommand `project-files`, which returns plan, apply and refusal dicts of the same shape. This is the extension seam the entry names for issue #21. It uses `_plan_digest` and `stage_and_replace` from `_preview_apply.py`.
- **Project profile** — consumed as-is, through `_load_profile_ctx` and `ctx.kind` for the slot state, and `pr_merged.load_slot` for authored values. Persistence check: the fixes from the parent contract (the placeholder test comes before backticks, and a missing row never reaches the worked example) are what make "authored only" safe. Tests cover a placeholder profile and a profile with missing rows.
- **Project-name check** — consumed as-is. Its token file gains a writer, and the readers are unchanged.
- **Guard rules file** — consumed read-only, for its `protected_databases` list.
- **`protect-databases` helpers** — reused by call, never copied: `_database_proposals` (filtered by `SYSTEM_DATABASES`), `_read_db_rules`, `_load_disposable_patterns`, `TEMPLATE_DATABASES` and the `narrowing-unconfirmed` shape. They are **extended by** one extraction: the inline guard-file search becomes the shared `_disposable_patterns_for`, which both subcommands call (decision 2).
- **Installed plugin root / `_separate_plugin_root`** — consumed as-is for the plugin-text check.
- **`plugin_doctor` SCAFFOLDS** — extended by one entry.

## New Mechanisms (if any)

None. Every new piece is a subcommand on Preview-hash apply's declared seam.

---

## Extension Points

- `auto_improve_finish_install.py`: the subparser `project-files` in `build_parser`, a branch in `main`, `token-invalid` in `REFUSAL_CODES` (exit class 2), `profile-slot` in the Evidence reasons, the constants `SYSTEM_DATABASES` and `GENERIC_WORDS`, and the extracted `_disposable_patterns_for`. **Imports:** `stage_and_replace` is added to the existing `from _preview_apply import _atomic_write, _plan_digest` line (`auto_improve_finish_install.py:130`). That is a new name from a module this script already imports and that is already vendored beside it, so the vendored-file list does not change. No module that this script does not already import is imported at module level. The round-trip readers (`derive_area`, `land_contract`, `memory_boundary`, `_registry_layout`) are imported in tests only. If the implementation needs any other module at run time, it imports it inside the function, guarded so that a missing module gives a source note and not a crash.
- `plugin_doctor.py`: the new entry in `REQUIREMENTS` and `SCAFFOLDS`, and the text of the `NEEDS YOU` line.
- `skills/auto-improve-finish-install/SKILL.md`: the new stage. The diagram, the frontmatter description, the doctor `--fix` list (which gains `.claude/.project-tokens.json`), Closing, Anti-patterns ("never propose or type a token the script did not list or the operator did not name"), and "When NOT to use" (remove the step-3 exclusion). Every stage-number reference in the file is updated.
- `README.md`, every line the change makes false:
  - **962-965**: the four files are "authored by you". This becomes: the doctor scaffolds them, and `/auto-improve-finish-install` proposes their content for you to confirm.
  - **997**: `.project-tokens.json TEMPLATE - empty token array`. This stays true of the plugin's own file, and gains "the doctor scaffolds a copy in a project".
  - **1312-1314**: "ships with `"tokens": []`". This becomes: the doctor scaffolds it with an empty list, and the skill can fill it.
  - **1330-1331**: "a plugin install delivers steps 1 to 3 for you". This is false, because an install never delivers the step-3 files (departure 1). It becomes: an install delivers steps 1 and 2; for step 3, run the doctor and then `/auto-improve-finish-install`.
  - **1353-1357**: Quick start step 3 becomes "run `/auto-improve-finish-install`", with the by-hand text kept as the fallback.
  - **1365-1367**: in the same rewritten paragraph, the README says the doctor scaffolds `issueTitle.effortTypes` empty, but `plugin_doctor.py:114-124` fills all nine, so that sentence is corrected.

## Integration Surfaces

`.claude/registries/INTEGRATION.md` does not exist in this repository. The surfaces were traced by hand:

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---|---|---|---|---|
| SKILL.md | `auto_improve_finish_install.py project-files` | command line, `--json` | ProjectFilesPlan, Refusal | skill → script → skill |
| script | `<project>/.claude/{area-mapping.json, work-item-conventions.json, .project-tokens.json}` | file read and write, exact path only | the three entities | script → project |
| script | `<project>/.claude/project-profile.md`, `<project>/.claude/hooks/db-destructive-guard.rules.json`, tracked config files | read only | slots, names | read |
| script | separate plugin root's shipped text | read only | text | read |

**Changes to existing integration surfaces:** none. There is no REST, SignalR or DTO surface.

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold.

(The scan could not be executed in the design session, which had no shell. With `areas: {}` in `.claude/area-mapping.json`, `derive_area` can only return the fallback, so no adjacent area can score.)

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

## Non-Goals

- Item 1 of issue #21 (database guard rules under a plugin install). **Verified already delivered:** `db-destructive-guard.py:407-415` reads the rules file only from `<CLAUDE_PROJECT_DIR>/.claude/hooks/` (INV-O3), and `README.md:201` states the fail-closed case.
- Appending to an authored token list, or editing `allowed`, `project`, `seed_adjacency`, or any conventions block other than `prTitle.map` and `prTitle.order`.
- Creating an absent step-3 file from the script. The doctor creates, and this command fills.
- Any change to a hook, to `derive_area.py`, `memory_boundary.py`, `_registry_layout.py`, or the sync tool.
- Inferring vendor names, handbook names, theme polarity or adjacency.

## Where this contract departs from the brief

1. **"Scaffolded empty by `plugin_doctor.py`" is false for `.project-tokens.json`.** The doctor's `REQUIREMENTS` (`plugin_doctor.py:58-98`) has no token entry, so under a plugin install the file is absent. Decision 6 adds the entry.
2. **"A wrong token silently weakens the check" is half true.** An extra or wrong token is loud: the sync stops with exit 5, memory items are lowered, and R3 raises an advisory. Two cases are silent. One is a missing token. The other is the first token written, which turns memory scope from fail-closed into per-token (decision 4). The design answers both: tokens are written only when the operator names them, the narrowing needs its own yes, and the `in-plugin-text` rule stops a loud token from blocking every sync.
3. **The conventions file is mostly generic, not empty.** Only `prTitle.map` and `prTitle.order` are project-shaped (`plugin_doctor.py:132`), so only those are proposed.
4. **The slot-proposal shape is reused, with four file-only basis values added.** ProjectFileProposal is the profile's `{slot, values, basis, evidence, note}` with `file` in place of `slot`. It keeps the basis values `inferred`, `none-found` and `kept-authored` with their profile meanings, and it adds `scaffold-missing`, `unrecognised`, `skipped` and `nothing-confirmed`. The profile has no word for any of these four, because a profile row cannot be absent from a file the doctor did not create, nor be unparseable JSON.
5. **The README lines the brief named are not the whole set.** The brief names lines near 964, 997, 1312 and 1354. This change also makes 1330-1331 false (a plugin install "delivers steps 1 to 3"), and 1365-1367 is already false. Both are added to the edit list. None of the brief's lines is dropped: 997 is kept in the list and still corrected.

## Confidence

Confidence: Medium. High on the readers, the states and the reuse, which were checked against `memory_boundary.py`, `_registry_layout.py`, `derive_area.py`, `plugin_doctor.py` and the `protect-databases` code. Medium on the nested value splice and on the case behaviour of `module_tag_reading`. The sync tool lives outside this repository, so its handling of an absent file is not verified.

## Alternatives Considered & Why Rejected

- **Option A (chosen):** one `project-files` subcommand: one plan, one hash and one all-or-nothing write over three files.
  - Why: it meets "one confirmation" literally, and it reuses `stage_and_replace`.
- **Option B (rejected):** three subcommands, one per file.
  - Why rejected: three previews and three yeses, which contradicts the one-confirmation criterion. A half-applied set is also possible.
- **Option C (rejected):** infer the roots afresh from the repository, as the profile stage does.
  - Why rejected: a second inference of the same facts can disagree with the answers the operator just confirmed. Reading authored slots gives one source of truth.
- **Option D (rejected):** let `plugin_doctor.py --fix` write the content.
  - Why rejected: the doctor's tested rule is that it never edits an existing file.

## Uncertain Assumptions

- `VERIFIED via .claude/scripts/memory_boundary.py:487-495,584-595`: the token list is read from the project's path only, and an empty list lowers every candidate.
- `VERIFIED via .claude/scripts/_registry_layout.py:655-665`: it reads with `utf-8-sig` and uses `tokens` and `allowed`.
- `VERIFIED via .claude/scripts/derive_area.py:36-64`: it reads with plain `utf-8`, so a byte order mark gives `{}`. Hence the `unrecognised` state, and nothing is written to such a file.
- `VERIFIED via .claude/scripts/plugin_doctor.py:58-165`: there is no token scaffold, the conventions scaffold has empty `prTitle` lists, and `effortTypes` is filled.
- `VERIFIED via .claude/scripts/auto_improve_finish_install.py:3918-4146`: the `protect-databases` helpers and the narrowing pattern.
- `ASSUMED`: the sync tool (`tools/sync-plugin.ps1`, in the consuming repository) treats an absent file like an empty list and matches tokens as case-insensitive substrings, as `MECHANISMS.md` states. If it does not, the `in-plugin-text` rule may be stricter than needed, but it is never weaker. Verification path: read that script in a consumer.
- `ASSUMED`: `_open_box` and `_member_named` locate a nested member (`prTitle` → `map`) by opening the inner box. Verification path: a byte-identity test outside the spliced spans.
- `ASSUMED`: `land_contract.module_tag_reading` matches globs case-sensitively. Verification path: the round-trip test with a mixed-case root.
- `VERIFIED via .claude/scripts/auto_improve_finish_install.py:395-447,703-729`: `_load_profile_ctx` and `ctx.kind` separate placeholder, authored and missing rows. `VERIFIED via .gitignore:36`: `.claude/cache/` is ignored in this repository.

*Session note (not a design assumption):* no CodeGraph tool was available in the design session, so the code was read with Grep and Read.

## Failure Modes & Mitigations

- **FM:** A wrong or generic token blocks every outbound sync.
  - **Mitigation:** the exclusion rules, including `in-plugin-text`. Tokens are written only when named. This is the **Project-name check**'s own direction rule.
- **FM:** A partial token list leaks a project name in a global memory item.
  - **Mitigation:** the narrowing statement and `--confirm-narrowing`, the same pattern as `protect-databases`.
- **FM:** An authored file is overwritten.
  - **Mitigation:** the Unauthored project file test, the per-file bases, and an apply that re-reads each target under the plan hash (**Preview-hash apply**).
- **FM:** A step-3 file is read through a multi-root locator, so the plugin's own copy is filled or judged.
  - **Mitigation:** exact `<project>/.claude/<file>` paths only. `area_mapping_path()` and `work_item_conventions_path()` are never used.
- **FM:** A server system database name (`master`, `postgres`, ...) found in config becomes a token and stops every sync.
  - **Mitigation:** the `SYSTEM_DATABASES` exclusion, which runs whatever state the plugin-text check is in (the **Project-name check** must stay passable).
- **FM:** A malformed guard rules file turns the whole run into a refusal.
  - **Mitigation:** `rules-unreadable` and `guard-unreadable` become a source note, and the `database` source is skipped.
- **FM:** Backups are committed by accident.
  - **Mitigation:** they go under `.claude/cache/`, following the **Registry migration runner** convention, and the result carries a `gitignore-hint`.
- **FM:** A profile root written with a backslash or a trailing slash gives a glob that never matches.
  - **Mitigation:** decision 1's normalisation, plus a round-trip test using such roots.
- **FM:** A failure after one file is replaced leaves a mixed state.
  - **Mitigation:** `stage_and_replace` restores every file.
- **FM:** A new module-level import breaks a vendored copy.
  - **Mitigation:** no new module is imported. `stage_and_replace` is a new name from the already-vendored `_preview_apply`, and the round-trip readers are imported in tests only.
- **FM:** The profile is unfilled, so the stage proposes nothing and looks broken.
  - **Mitigation:** the `none-found` basis plus the profile-note, which tells `profile-has-placeholders` apart from `roots-authored-none`.

## Open Questions for User

- [x] **Accept the departures above, and confirm the brief's acceptance criteria as read here?** → **Answer (user, 2026-11-11):** accepted (departures 1-3 as asked; 4 and 5 record the critique fixes).
- [x] **Should an existing, non-empty token list receive appended tokens?** → **Answer (user, 2026-11-11):** no. Advice only.
- [x] **Should the first tokens always need `--confirm-narrowing`?** → **Answer (user, 2026-11-11):** yes, always.
- [x] **Should the doctor scaffold `.project-tokens.json`?** → **Answer (user, 2026-11-11):** yes.

## Critique

**Critic:** contract-critic
**Date:** 2026-11-11
**Verdict:** blockers-found

Code claims checked against the code. These hold: there is no token entry in the doctor's `REQUIREMENTS` or `SCAFFOLDS` (`plugin_doctor.py:58-165`); the empty-list narrowing is at `memory_boundary.py:584-595`; INV-O3 is at `db-destructive-guard.py:407-433` and `db-research-readonly-guard.py:162-170`, with `README.md:201`; `effortTypes` is filled (`plugin_doctor.py:114-124`); `_open_box`, `_member_named`, `_linked_folder_refusal`, `_read_db_rules`, `_load_disposable_patterns`, `_database_proposals`, `TEMPLATE_DATABASES` and `stage_and_replace` exist where the contract cites them. The 0.18.8 -> 0.19.0 minor raise in one pull request follows `CLAUDE.md` lines 5-16 (`MANIFESTS`, `check_version_bump.py:25`), and checklist item 14 is not triggered because there is only one mergeable block.

### Findings

- **[BLOCKER] The database token source can propose server system names, because the reused reader was never re-checked for its new purpose**
  - **What is wrong:** `_database_proposals` removes only `tempdb` and disposable names (`auto_improve_finish_install.py:3939`). So `Database=master`, `model`, `msdb` and `postgres` in tracked config come through as TokenCandidates, and neither the `generic-word` stop list nor any other exclusion names them. When the plugin-text check is `unverifiable`, nothing catches them, and a written `master` would stop every outbound sync. That breaks the brief's criterion that "a token the evidence cannot support is not proposed".
  - **Prior artifact ignored:** `JOURNAL.md` — *2026-11-01 — A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for*. For database protection a system name was harmless (protecting `master` costs nothing). As a token it is not.
  - **Where in this contract:** `## Data Shapes → Design decisions 2` — "`database`: the names `_database_proposals` finds in tracked configuration files"; decision 3 lists no system-database rule.
  - **→ Addressed by:** decision 2 adds `SYSTEM_DATABASES`, an explicit list for SQL Server, PostgreSQL, MySQL and MongoDB, applied to both database lists whatever the plugin-text state. Decision 3 adds the `system-database` exclusion and refusal rule, and a Failure Modes entry is added. `_database_proposals` is never used unfiltered.
- **[WARN] The per-proposal shape is a new vocabulary, not the profile's slot-proposal shape, and this departure is not listed**
  - **What is wrong:** profile proposals are `{slot, values, basis, evidence, note}` with `basis` values `inferred`, `none-found` and `kept-authored` (`auto_improve_finish_install.py:726-729`). ProjectFilePlan uses `state` with `proposed` and `no-evidence` instead. `## Where this contract departs from the brief` does not name this.
  - **Prior artifact ignored:** the brief's criterion "reuse the existing slot-proposal shape" (`.claude/work-items/2026-11-11-21-finish-install-step3-proposals.md:33`); the follow-up stub's "Reuse the parent's slot-proposal shape" (`followups/2026-10-04-auto-improve-finish-install-step3-inference.followup.md:20`); `MECHANISMS.md:72` (Preview-hash apply: "dicts of the same shape").
  - **Where in this contract:** `## Data Shapes → Value Objects` — "ProjectFilePlan | file …, state (closed set below)".
  - **→ Addressed by:** aligned to the profile's basis. ProjectFileProposal is now `{file, values, basis, evidence, note}`, with `proposed` renamed to `inferred` and `no-evidence` renamed to `none-found`. The four values that exist only for files are listed as departure 4.
- **[WARN] What happens when the guard rules file is unreadable is not stated**
  - **What is wrong:** when the rules file is present but malformed, `_read_db_rules` returns a `rules-unreadable` refusal (`auto_improve_finish_install.py:3864-3878`). The Commands table and the file states never list it, so the skill text will have to make up a behaviour. The contract says a file problem is "never a run refusal", but it does not say this one is turned into a skipped source.
  - **Prior artifact ignored:** `JOURNAL.md` — *2026-11-02 — A skill written around an adapter refusal hides a contract divergence*.
  - **Where in this contract:** `## Commands` — "Possible rejections | `project-unreadable`, `plugin-source-checkout`, `token-invalid`".
  - **→ Addressed by:** the paragraph under the Commands table and decision 2. `rules-unreadable` and `guard-unreadable` become a `source-notes` entry: the `database` source is skipped, and the run is never refused. The new plan field `source-notes` carries the note.
- **[WARN] The guard-file search must be copied, because it is not a callable helper**
  - **What is wrong:** `_load_disposable_patterns` takes one guard path. The search (plugin root guard first, then the project's) is inline inside `_plan_protect_databases` (`auto_improve_finish_install.py:4104-4112`). "Reused by call, never copied" cannot be met as written.
  - **Prior artifact ignored:** `JOURNAL.md` — *2026-10-15 — Reuse the existing brief-linkage reader; a second one misses edge cases* (same class: a second copy of a lookup).
  - **Where in this contract:** `## Reused Mechanisms` — "`protect-databases` helpers … reused by call, never copied".
  - **→ Addressed by:** decision 2 moves the search into the shared `_disposable_patterns_for(project, root)`. `_plan_protect_databases` and `project-files` both call it, and the existing `protect-databases` tests stay green. Reused Mechanisms and Extension Points now say this.
- **[WARN] A third backup convention, with no gitignore hint**
  - **What is wrong:** today finish-install backs up to `<name>.bak-<stamp>` beside the target and returns a `gitignore-hint` (`auto_improve_finish_install.py:1822-1824, 1941`). The registry migrations back up under `.claude/cache/registry-migrations/`. This contract adds `.claude/.finish-install-backups/`, with no hint, no ignore rule and no Integration Surfaces row, so consumers get untracked backup files that can be committed.
  - **Prior artifact ignored:** `MECHANISMS.md:72` (Preview-hash apply) and `MECHANISMS.md:118` (Registry migration runner backup location).
  - **Where in this contract:** `## Design decisions 5` — "backups in `.claude/.finish-install-backups/<UTC yyyymmddTHHMMSSZ>/`".
  - **→ Addressed by:** decision 5 now reuses the registry migration's convention under the git-ignored `.claude/cache/`: `.claude/cache/finish-install/<UTC>/backup/`. The apply result carries `backup-dir`, the rollback line and `gitignore-hint: ".claude/cache/"`, which the skill passes on. A Failure Modes entry is added.
- **[WARN] `load_slot` cannot tell a placeholder from an authored `none` or a missing row, but decision 1 depends on that difference**
  - **What is wrong:** `load_slot` returns `()` for all three (`pr_merged.py:95-101`). So "when every one of these slots is a placeholder … fill the profile first" would also fire for a profile whose roots are authored `none`. The contract does not name the reader that makes the distinction (the profile stage uses `ctx.kind`, `auto_improve_finish_install.py:708, 720`).
  - **Prior artifact ignored:** `JOURNAL.md` — *2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case*.
  - **Where in this contract:** `## Design decisions 1` — "read through `pr_merged.load_slot` … A `none` slot or a placeholder slot gives nothing. When every one of these slots is a placeholder".
  - **→ Addressed by:** decision 1 reads the slot state through `_load_profile_ctx` / `ctx.kind`, and uses `load_slot` for authored values only. The closed profile-note set is `profile-missing`, `profile-has-placeholders` and `roots-authored-none`, which tells a placeholder apart from an authored `none`. The TASK block adds a test row for each.
- **[WARN] A hidden Open Question: the "fixed" stop list is open-ended**
  - **What is wrong:** "for example" leaves the implementer to choose the closed set that decides which tokens are refused. That choice changes `token-invalid` behaviour, and it is not hoisted as a question.
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md` → `## Open Questions for User` ("Must be resolved before `Status` flips").
  - **Where in this contract:** `## Design decisions 3` — "`generic-word`: on a fixed stop list in the script, for example `app`, `api`, …".
  - **→ Addressed by:** decision 3 now defines `GENERIC_WORDS` as an exact closed list, matched on the whole token without letter case. Changing the list is a contract amendment.
- **[WARN] Two README lines the change makes false are not touched**
  - **What is wrong:** `README.md:1330-1331` says a plugin install "delivers steps 1 to 3 for you". That contradicts departure 1 (the token file is absent under an install) and the new stage. The brief also names line 997, and the contract neither edits it nor lists it as a departure.
  - **Prior artifact ignored:** the brief's criterion "The README claim about these files (lines near 964, 997, 1312 and 1354) matches what the skill now does" (`.claude/work-items/2026-11-11-21-finish-install-step3-proposals.md:38`).
  - **Where in this contract:** `## Extension Points` — "`README.md`: lines 962-965, 1312-1314 and 1353-1357".
  - **→ Addressed by:** Extension Points now lists, each with its new reading, lines 962-965, 997, 1312-1314, 1330-1331, 1353-1357 and 1365-1367. Departure 5 records the lines added beyond the brief's list.
- **[WARN] The prTitle glob has no normalisation rule**
  - **What is wrong:** the area pattern is normalised (lowercase, forward slashes), but `<root>/**` is not. A profile root written with a backslash or a trailing slash gives a glob that `path_matches` never matches, because only the path side is normalised (`land_contract.py:620-622`). The round-trip test as written uses a clean root.
  - **Prior artifact ignored:** `land_contract.py:620-622` (only the path side is normalised); `JOURNAL.md` — *2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case*.
  - **Where in this contract:** `## Design decisions 1` — "The prTitle glob is `<root>/**`".
  - **→ Addressed by:** decision 1 now normalises every root before both uses: backslashes become `/`, repeated `/` collapse, and a leading `./` and any trailing `/` are removed. Unsafe roots are rejected. The TASK block adds a round-trip test with a backslash root and a trailing-slash root.
- **[NIT] Adjacent Areas does not use the sanctioned sentence and says the scan was not run.** With `areas: {}`, `derive_area` can only return the fallback, so this is not a BLOCKER (checklist 11.f).
  - **→ Addressed by:** the sanctioned sentence, followed by a one-line note on why the scan could not run.
- **[NIT] `INTEGRATION.md` is absent from `.claude/registries/`.** The contract says so and traced the surfaces by hand.
  - **→ Addressed by:** no change. The surfaces stay traced by hand.
- **[NIT] "Token candidate" sits beside the existing "Capture candidate" (`VOCABULARY.md:136`), and decision 4 says "every capture candidate".** Check both readings per *2026-11-02 — Search a proposed term against agent frontmatter and host docs before adding it*.
  - **→ Addressed by:** the term is renamed **Token proposal** (TokenProposal), and decision 4 now names **Capture candidate** explicitly.
- **[NIT] "No new module-level import" is ambiguous for `stage_and_replace`.** It is not imported today (`auto_improve_finish_install.py:130` imports only `_atomic_write, _plan_digest`). Adding it to that line is a new name from an already-vendored module, not a new module.
  - **→ Addressed by:** Extension Points states the rule. `stage_and_replace` joins the existing `_preview_apply` import line, and no module that is not already imported is imported at module level. Any other run-time module is imported inside a function, guarded.
- **[NIT] The last ASSUMED item ("no CodeGraph tool was available") is a note about the session, not a design assumption.**
  - **→ Addressed by:** it is moved to a session note below Uncertain Assumptions.

### Applicable journal entries

- **2026-11-01 — A shared reader reused by a stricter consumer must be re-checked** — violated, see the BLOCKER above.
- **2026-11-02 — A skill written around an adapter refusal hides a contract divergence** — partly violated, see the WARN on `rules-unreadable`.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by the tests in the TASK block; see the WARN on placeholder versus `none`.
- **2026-10-04 — A root locator can return the consumer itself under vendoring** — heeded by `_separate_plugin_root`.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by the Non-Goals item 1 check (confirmed at `db-destructive-guard.py:407-433`).
- **2026-10-05 — Never hide a forbidden name by hashing it** — heeded by the planted-word `in-plugin-text` test.
- **2026-10-05 — A documented "missing file means the default" must read one named location only** — heeded by exact `<project>/.claude/<file>` paths.
- **2026-10-15 — A script that reads a project-owned file must be told which project** — heeded by the exact-path rule.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by the Run list (`test_skill_script_lookup.py`).
- **2026-10-16 — A "missing project file" refusal must cover both cases** — heeded by `scaffold-missing`.
- **2026-10-28 — A new term's definition must be true against every existing member** — heeded: "Unauthored project file" holds for the token file only once decision 6 lands.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded by New Mechanisms: none.
- **2026-10-28 — A rule that writes a slot the vocabulary calls frozen needs a vocabulary amendment** — not addressed (no profile slot is written).
- **2026-11-02 — Describe a fixer a skill runs by everything it writes** — heeded by the SKILL.md `--fix` list.
- **2026-11-02 — Search a proposed term against agent frontmatter and host docs** — see the NIT on "Token candidate".
- **2026-11-06 — A plugin repository that is also installed resolves its own older copy as "the plugin"** — heeded by `plugin-source-checkout`.
- **2026-11-07 — A merge block's pull request must paste each required output** — heeded by "Paste each output in the PR".
- **2026-11-09 — A change that adds a module-level import to a vendored script must update the vendored-file list** — heeded; see the NIT on `stage_and_replace`.
- **2026-10-30 — A delivery rule must name every route into delivery** — not addressed (the delivery rules are not changed).

### What the critic did not check

- `derive_area.py` and `pr_merged.py --status --json` were not executed (no shell in this run). The Adjacent Areas and Parent Branch findings were reasoned from `.claude/area-mapping.json` (`areas: {}`) and the single mergeable block.
- `tools/sync-plugin.ps1` lives outside this repository and was not read.
- No CodeGraph tool was available. The symbols were verified with Grep and Read on `.claude/` paths.
- The project tier domain files (`MECHANISMS/general.md`, `VOCABULARY/general.md`, `JOURNAL/general.md`) hold no entries, so the reuse check covered the Universal tier only.

## Lessons referenced

- **2026-10-15 — A script that reads a project-owned file must be told which project, not search for one** — heeded by the exact-path rule (Integration Surfaces, Failure Modes).
- **2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file** — heeded by the `scaffold-missing` state with no fallthrough.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded by the literal tokens and the planted made-up word in the `in-plugin-text` test.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by the test with a placeholder profile and missing rows.
- **2026-10-04 — A root locator can return the consumer itself under vendoring** — heeded by `_separate_plugin_root` for the plugin text.
- **2026-11-06 — A plugin repository that is also installed resolves its own older copy as "the plugin"** — heeded by the `plugin-source-checkout` refusal.
- **2026-11-02 — Describe a fixer a skill runs by everything it writes** — heeded by the SKILL.md `--fix` list gaining the token file.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded by New Mechanisms: none.
- **2026-11-09 — A change that adds a module-level import to a vendored script must update the vendored-file list** — heeded by "no new module-level import" and by the Run list.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by departure 2 and the Non-Goals verification of item 1.
- **2026-10-28 — A rule that writes a slot the vocabulary calls frozen needs a vocabulary amendment** — heeded: no authored file is written, so the new term mirrors **Placeholder slot** without amending it.
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded by one FM for each new path.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by the Run list.
- **2026-11-01 — A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for** — heeded (after critique) by the `SYSTEM_DATABASES` filter on `_database_proposals`.
- **2026-11-02 — A skill written around an adapter refusal hides a contract divergence** — heeded (after critique) by stating that `rules-unreadable` becomes a source note.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded: every finding above is amended in Data Shapes, the decisions and the TASK block, not only noted.

Orthogonal to north-stars: none. `.claude/north-stars/` does not exist, which matches the brief's pre-grade.

## Implementation Handoff

### 1. Quick start step 3 proposals in finish-install (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `.claude/scripts/plugin_doctor.py`
- `.claude/scripts/tests/test_plugin_doctor.py`
- `skills/auto-improve-finish-install/SKILL.md`
- `README.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`

**Pre-written TASK block:**
```
TASK: Add the project-files subcommand (Data Shapes, decisions 1-5), the doctor's token
      scaffold and NEEDS YOU text (decision 6), the new skill stage (decision 7), the
      README edits (Extension Points), and a minor raise 0.18.8 -> 0.19.0 in all five
      declarations (re-raise if master moves first).
CONTEXT: concept contract at .claude/concepts/2026-11-11-finish-install-step3-proposals.md
FILES: as listed under Files to touch
CONSTRAINTS:
  - Run through /tdd-first in this one branch; every RED case fails on an assertion.
  - Tests, per file (area map, conventions, tokens): inferred; none-found leaves the
    file byte-identical and the note names why (profile-missing,
    profile-has-placeholders and roots-authored-none each get a row); kept-authored leaves the file
    byte-identical and shows the advice (positive control: an edited authored file is
    detected); scaffold-missing; unrecognised (BOM, duplicate key); bytes outside the
    spliced spans unchanged; round trip through derive_area.load_area_mapping,
    land_contract.module_tag_reading, memory_boundary.token_list and
    _registry_layout.load_project_tokens. The prTitle and area round trip includes a
    root written with backslashes and one with a trailing slash.
  - Tokens: each source finds its proposal; Database=master, postgres and msdb in a
    tracked config are excluded as system-database with the plugin-text check
    unverifiable; a malformed rules file gives a source note, skips the database
    source and does not refuse the run; each exclusion reason has a row, with
    in-plugin-text proven by planting a made-up word in a fake plugin root; only --token
    values are written; no --token gives nothing-confirmed; the first write without
    --confirm-narrowing is refused narrowing-unconfirmed, with a positive control that
    writes with it; token-invalid for each rule.
  - Common: changed-since-preview (file edited; --token set changed); --skip-file;
    plugin-source-checkout; an injected replace failure restores all three files; a
    second run writes nothing; the backups land under .claude/cache/finish-install/
    and the result carries the gitignore-hint; every refusal asserts the code, the
    exit code and an unchanged tree.
  - Extract _disposable_patterns_for from _plan_protect_databases. The existing
    protect-databases tests must stay green, unchanged.
  - Read <project>/.claude/<file> only; never area_mapping_path() or
    work_item_conventions_path().
  - Reuse by call: _load_profile_ctx, load_slot, _database_proposals (always filtered
    by SYSTEM_DATABASES), _read_db_rules, _disposable_patterns_for,
    _separate_plugin_root, _plan_digest, stage_and_replace, _open_box, _member_named,
    _linked_folder_refusal. Copy none of them.
  - Imports: add stage_and_replace to the existing _preview_apply import line. Import
    no module that is not already imported at module level; any other run-time
    module is imported inside the function, guarded.
  - Doctor: a parity test that its token scaffold has the shipped template's keys.
  - Run: test_auto_improve_finish_install.py, test_plugin_doctor.py,
    test_plugin_manifests.py, test_check_hook_registrations.py,
    test_skill_script_lookup.py, check_version_bump.py. Paste each output in the PR.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-finish-install-step3-proposals.md
  contract_status: approved
```

### 2. Scope note on review and delivery

There is one mergeable block, because the script, the doctor, the skill and the README share one version raise and would not be useful merged apart. So this contract is delivered as one pull request, not through a parent branch. Review runs in the outer chain that `/flow` already drives: the code reviewer and the test-suite reviewer after GREEN, then verification. If the reviewer's janitor appends to `MECHANISMS.md` (a Correction under Preview-hash apply for `project-files`) or to `VOCABULARY.md` (the two proposed terms), it does so in the same branch, under the same raise. There is no frontend work, no migration and no hook change.

## Review checklist (filled in after implementation)

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both backend and frontend sides
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
- [ ] `Status` flipped to `implemented`
