# Concept Contract — The plugin owns the hook-registration checks

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-31 (amended 2026-11-01 after critique rounds 1 to 3 and the user's answers)
**Requested by:** user
**Status:** approved
**Supersedes:** none
**Work Item Brief:** .claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md
**Tracking issue:** #148
**Budget:** 12,000 tokens

---

## Business Concept

- **What is this thing, in domain language?**
  Hook registrations are a plugin mechanism, but the tests that guard them live in one consuming project (issue #148). When that project's default branch changes a registration, the tests fail inside an unrelated contract's landing, and gate P8 offers only a baseline re-record, which can hide a real break. This contract moves the rules into the plugin. A **Hook registration check** is a read-only script that judges a project's settings file against that project's **Hook registration profile** (a committed record of the rows the project expects) and passes, or names each broken **Registration rule**. The finish-install script gains a consented `record-registrations` subcommand that writes the Hook registration profile. The P8 landing report gives each new failure unit a **Failure attribution**, so the operator can tell a failure the contract caused from one the default branch brought in, or reads why that cannot be told.

- **Naming rule.** The bare word "profile" already means the **Project profile** (a `MECHANISMS.md` entry) and its `profile` subcommand. This contract never uses it alone: the concept is always "Hook registration profile", the subcommand is `record-registrations`, and every identifier that names the concept spells it in full: refusal codes `hook-registration-profile-missing` and `hook-registration-profile-unreadable`, the flag `--hook-registration-profile`, the report key `hook_registration_profile`, and every operator message. The file name `.claude/hook-registration-profile.json` stays as answered in Q4.

- **Existing VOCABULARY.md terms that apply:** **Registration key** (row identity; reused, unchanged); **Vendored asset**; **Plugin-delivered asset** (scripts are not one); **Landing version raise**; **Ownership tier** (the Hook registration profile is a local asset). The landing's `report.json` and its `next_command` field, and the Verification Record, are script outputs named here by their file and key, not vocabulary terms.

- **New terms proposed for VOCABULARY.md** (Universal tier, appended by block 4):
  - **Registration row** — one handler object inside `hooks.<event>[n].hooks[]` of a settings file. Its identity is the event, the matcher (empty when absent), the identity text (below) and its occurrence number among rows sharing the first three. Identity text: the **Registration key** for a `command` row naming a `.py` file; `command:` plus its command and arguments joined by single spaces for a `command` row naming none; `<type>:` plus the row's canonical JSON without `if` for a row of any other `type`.
  - **Hook registration profile** — `.claude/hook-registration-profile.json`. A project-owned record of the rows a project expects in its `.claude/settings.json`: each row's content apart from `if`, its `if` value, the total row count, and deliberate Exclusions with a reason each. Written by the finish-install `record-registrations` subcommand, or by hand for Exclusions. Never synced. Not the **Project profile**.
  - **Registration rule** — one of five named rules the Hook registration check applies: `row-count-unchanged`, `rows-unchanged-apart-from-if`, `if-keys-unchanged`, `every-registration-profiled-or-excluded`, `every-exclusion-matches-a-row`. "Profiled" means recorded in the Hook registration profile, never the hook timing profiler.
  - **Failure attribution** — the landing's reading of where one new P8 failure unit comes from: `in-diff`, `outside-diff` or `undetermined`, each with a one-line reason. A unit is a named failed test, or the whole step when the step names none. Only a file the unit names can decide `in-diff` or `outside-diff`; a path match that merely made the step run never does. Advisory only: it never changes a verdict, a gate or an exit code.

---

## End-User View

Not applicable. Reason: no Angular UI surface is touched. The users are operators running plugin scripts.

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership (aggregate) |
|------|--------|------------|-----------------------|
| Hook registration profile | `format` (integer, `1`); `settings_path` (string, always `.claude/settings.json`); `row_count` (integer ≥ 0); `registrations` (list of Profiled row, in settings file order); `excluded` (list of Exclusion, in their existing order) | RP-1 the content is a pure function of the settings rows and the existing Exclusions: no time, hash, host or absolute path is stored, so an unchanged re-record produces identical bytes (B1). RP-2 serialisation is fixed: UTF-8 without a byte-order mark, two-space indent, keys in the order listed, one trailing newline. RP-3 `row_count` equals the number of settings rows when recorded, excluded rows included. RP-4 every Profiled row identity is unique. RP-5 every Exclusion has a non-empty `reason`. RP-6 no Exclusion can match a Profiled row's identity (a row is never both expected and excluded). RP-7 no two Exclusions can match the same row: identical entries, and an entry without a matcher beside one with a matcher for the same event and identity text, both break it. RP-8 a re-record keeps every existing Exclusion verbatim, including one that now matches no row. A profile that breaks RP-4..RP-7, has an unknown `format`, or lacks a field is unreadable (exit 2), never a pass and never an empty profile. | The consuming project (a local asset, never synced). |

The record time is deliberately not stored: the file's git history carries it. Hashing never covers a value outside these fields.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Registration row identity | event (string); matcher (string, empty when absent); identity text; occurrence (integer from 1, in file order) | The match key between settings rows and profile entries. Path prefixes do not change it, because the Registration key ignores them, so a path change shows as a content change. |
| Profiled row | identity; `row` (the handler object without `if`, as written); `if` (string, or absent) | One expected row. |
| Exclusion | event; identity text; matcher (optional, meaning any matcher); `reason` (non-empty string) | Exempts rows of that identity from HR-2, HR-3 and HR-4 (never from HR-1). It carries no occurrence, so it covers every occurrence of that identity: excluding one of two duplicate rows excludes both, on purpose. |
| Rule result | `rule` (one of the five Registration rules); `status` (`pass` / `fail`); `findings` (list of {identity, detail}) | One line of output. All five rules are always evaluated, with no short-circuit. |
| Check report | `status` (`pass` / `fail` / `could-not-check`); `settings`; `hook_registration_profile` (paths); `rules` (five Rule results, empty when the check could not run); `refusal` ({code, message, path}, or absent); `remedy` (string) | The `--json` output. The text form prints one `PASS <rule>` / `FAIL <rule>: <detail>` line per rule, then the remedy. |
| Failure attribution | `unit` (a failure id `suite::unit::name`, or `step <id>`); `unit_kind` (`test` / `step`); `attribution` (`in-diff` / `outside-diff` / `undetermined`); `reason` (non-empty string) | One entry per failure unit in the Verification Record. |

**Settings shape** (judged on the project layer `.claude/settings.json` only). One validator, `load_settings` in `check_hook_registrations.py`, is the only reader of this shape, and both the check and `record-registrations` call it; neither has a second copy. It reads the bytes as UTF-8 (a byte-order mark is accepted), parses JSON refusing duplicate keys at any level, requires an object, then validates the whole `hooks` tree before any row is read: `hooks` is an object; each event value is a list; each group is an object whose `matcher`, if present, is a string and whose `hooks` key is present and a list (a group with no `hooks` key is refused, kind `shape`); each handler is an object with a string `type`; a `command` handler carries a string `command`, and `args`, if present, is a list of strings. A breach raises one error with a kind (`encoding`, `json`, `duplicate-key`, `not-object`, `shape`) and the JSON path. The check maps every kind to `settings-unreadable`; the recorder maps `shape` to `unexpected-settings-shape` and the rest to `malformed-settings`. A file with no `hooks` key is valid and has zero rows. Group keys other than `matcher` and `hooks` are not judged. The installer's existing `_parse_settings` is NOT changed: it keeps its current checks (duplicate keys at every level; shape only down to group level; a group with no `hooks` key defaults to `[]`, `auto_improve_finish_install.py:1307`), and the `hooks` and `addon` subcommands that use it behave exactly as before. So on a file with a `hooks`-less group the `hooks` subcommand reads zero rows there while the recorder refuses: deliberate, because a check must not guess.

**Rule semantics:**

- **HR-1 `row-count-unchanged`.** The settings row count equals `row_count`. The finding names both numbers.
- **HR-2 `rows-unchanged-apart-from-if`.** Each Profiled row has a settings row of the same identity whose handler object, without `if`, is JSON-equal to `row` (key order ignored, values exact). The finding says `missing` or names the differing keys.
- **HR-3 `if-keys-unchanged`.** For each matched Profiled row, the `if` values are equal. Absent on both sides is equal; present on one side only is a finding.
- **HR-4 `every-registration-profiled-or-excluded`.** Every settings row matches a Profiled row or an Exclusion. The finding names the identity.
- **HR-5 `every-exclusion-matches-a-row`.** Every Exclusion matches at least one settings row. A stale Exclusion is a finding naming it and saying "remove it from the hook registration profile".

**Could-not-check refusals** (exit 2, closed set; none is ever a pass):

| Code | When |
|---|---|
| `paths-not-given` | Neither `--project` nor both `--settings` and `--hook-registration-profile` were given. No environment variable and no working-directory fallback. |
| `settings-missing` | The settings path is absent, including root set but file absent. |
| `settings-unreadable` | `load_settings` refuses the file (any error kind above). |
| `hook-registration-profile-missing` | The Hook registration profile is absent. The remedy names `record-registrations`. |
| `hook-registration-profile-unreadable` | The Hook registration profile is unreadable (RP invariants). |
| `checker-dependency-missing` | A module the check imports cannot be imported, for example when only the checker was vendored (W1). The message names the module and the file set to vendor. |
| `checker-internal-error` | Any other unexpected exception. One line with its type and message, never a traceback that exits 1. |

**Import side effects and bytecode (known limit).** The installer sets `sys.dont_write_bytecode = True` and puts its own folder first on `sys.path` (`auto_improve_finish_install.py:78-83`), but the flag is set inside its body, after Python has already cached the installer itself; a plain `py -3` run therefore writes `__pycache__/auto_improve_finish_install.*.pyc` beside a vendored copy, and a consumer that does not ignore `__pycache__` then halts P8 on "the steps changed the worktree". Two defences: the checker sets the same flag as its first statement, before its guarded import; and the README step runs `py -3 -B`. The `sys.path` change is tolerated (one-shot process; the folder is the checker's own). Remaining limit, stated in the README: a harness that imports the checker as a module without `-B` can still cache the checker itself. This repository's `.gitignore` hides `__pycache__`, so block 1 tests from a copy outside this repository.

**The second installer copy.** `record-registrations` runs the installer as `__main__`; its function-level `import check_hook_registrations` makes the checker import `auto_improve_finish_install` again, a second module object. Harmless by construction: the second body only defines names and repeats the two idempotent side effects above, its `__main__` guard does not run, the checker uses only the stateless readers `_iter_hooks`, `_hook_key`, `_compare_extras`, and only plain dicts, lists and bytes cross between the copies (no class, exception or `isinstance` check from one copy is used by the other; the `load_settings` error type lives in the checker, which loads once). Block 2 tests the subcommand run as a script.

Exit codes: `0` pass, `1` at least one rule failed, `2` could not check.

**Failure units** (B2). On a `NOT-READY` verdict, every step whose reading is `regression` yields units: one per name in its `new_failures`, or, when it records no names (every `exit-code` step, and so every step in this repository), exactly one unit `step <id>` of kind `step`. On any other verdict `new_failures_attributed` is `[]` and `attribution_note` is absent.

**The empty list on `NOT-READY`.** `_p8_verify` also reaches `NOT-READY` from its `reasons` alone (worktree changed, forbidden paths, missing review coverage; `land_contract.py:2556-2564`) with no regression step. Then the list is `[]` and the note is "no step regressed, so there is nothing to attribute; the verdict comes from: <reasons>". When reasons and regression steps both exist, units are attributed as usual and the note also names the reasons.

**Files a unit names.** A `vitest-json` unit names its path. A `unittest-text` unit names the file made from its module segments (all but the class) joined with `/` plus `.py`, matched as a whole-segment path suffix of diff paths; it names the file only when exactly one diff path matches, and names none for `__main__` or an ambiguous match. A `step` unit names every command argument that does not start with `-` and equals a diff path after `\` becomes `/` (so a step that passes its input files as arguments names them; an inline `-c` command names none). A `trx` unit names none.

**Attribution sides.** *Contract diff* is merge-base(default, parent)..parent (the existing `contract_diff`). *Default-branch diff* is the P7 merge's diff, captured before P7b reassigns `merge_diff` (`land_contract.py:2175`), minus the hand-resolved paths. *Landing's own paths* are diff(HEAD captured after P7 and before P7b, HEAD after P7b), which is empty when P7b commits nothing (never `HEAD^..HEAD`), plus this run's hand-resolved paths, plus every version file the version raise manages (`check_version_bump.py` `MANIFESTS`) whether or not this run commits one. The last term covers a rerun after an earlier run pushed at P9: `contract_diff` then also holds that run's version raise, which FA-1 still catches. Limit: an earlier run's hand-resolved paths are not recorded, so on such a rerun they sit in the contract diff and can read `in-diff`; accepted because attribution is advisory. Step applicability is unchanged (it still uses the post-P7b `merge_diff`).

**Failure attribution rules** (pure, in order, first match wins). Only *named files* (above) decide a side.

- **FA-1.** A named file is among the landing's own paths → `undetermined` ("the landing itself changes <file> (version raise or hand-resolved merge)").
- **FA-2.** Named files are in both the contract diff and the default-branch diff (the same file or different ones) → `undetermined` ("both the contract's diff and the default branch's diff change files the failure names: <files>").
- **FA-3.** Named files are in the contract diff only → `in-diff` ("only the contract's diff changes <file>, which the failure names").
- **FA-4.** Named files are in the default-branch diff only → `outside-diff` ("only the default branch's diff changes <file>, which the failure names").
- **FA-5.** No named file is in any diff → `undetermined`, with the first reason that applies: `the step names no file, so a failure cannot be traced to a diff` (an inline command); `the step's when_paths match <side(s)>, which shows only why the step ran, not what failed`; `no file the failure names is in either diff`.

A `when_paths` match is never enough for `in-diff` or `outside-diff`, because it says why a step ran, not what it read.

The Verification Record gains `new_failures_attributed` and `attribution_note`. The note is written when the list is empty (text above) or when no entry is `in-diff` or `outside-diff` (it lists the distinct reasons). Existing keys are unchanged. The `verification-not-ready` detail adds `in the contract's diff: …; outside it: …; undetermined: …`, naming units.

**The advice facts.** Re-recording the baseline can change the result only for a named regression (a `test` unit): `read_step` never reads the baseline for an exit-code step (`land_contract.py:857-862`), recording refuses a step that fails on the default branch (`:998-1003`), and `repeat` needs non-empty `new_failures` (`:1499`). Hence two facts, both false unless `reasons` is empty and at least one unit exists (never vacuously true):
- `all_outside_diff` — every unit is `outside-diff` AND at least one unit has kind `test`.
- `step_failures_only` — every unit has kind `step` (whatever its attribution).
They are mutually exclusive. When neither is true, the existing advice is unchanged.

### Events

Not applicable. Reason: scripts with no event bus. Results are exit codes and reports.

### Commands (if any)

| Name (imperative) | Handler | Payload | Possible rejections |
|-------------------|---------|---------|---------------------|
| Check hook registrations | `.claude/scripts/check_hook_registrations.py` | `--project <root>` or `--settings <path> --hook-registration-profile <path>`; `--json` | the seven could-not-check codes |
| Preview hook registration profile | `auto_improve_finish_install.py record-registrations --project <root> [--json]` | — | `project-unreadable`, `malformed-settings` and `unexpected-settings-shape` (both from `load_settings`, mapped as above), new `registration-settings-missing`, new `hook-registration-profile-unreadable` (an unreadable existing file is never overwritten, because that would lose its Exclusions). The preview lists stale Exclusions it keeps. |
| Apply hook registration profile | same, plus `--apply --expect-sha256 <plan hash>` | plan hash over: settings bytes, existing file bytes (or `absent`), planned bytes; all three are deterministic by RP-1 | `changed-since-preview`, `write-failed`, and every preview refusal; a symbolic-link target is refused. Planned bytes equal to existing bytes → nothing to write. |

---

## Reused Mechanisms

- **Registration key** and `_iter_hooks` / `_hook_key` / `_compare_extras` in `auto_improve_finish_install.py`: **consumed as-is** by a guarded import, so the checker reads rows exactly as the installer writes them. The checker applies `_compare_extras` itself to match `_Registration.key`, and runs `load_settings` before calling `_iter_hooks`, which skips malformed parts silently. `_parse_settings` is not reused and not changed (see Settings shape).
- **Preview-hash apply**: **extended by** the `record-registrations` subcommand, as its Extend-by line describes. It reuses the backup, the temporary-file-then-`os.replace` write, the symbolic-link refusal, nothing-to-write and the `EXIT_CLASS` map. Two refusal codes join `REFUSAL_CODES`, both exit class 2.
- **Guard rules file**, fail-direction clause: **consumed as a rule.** The check blocks, so every missing, malformed or unimportable input is exit 2.
- **Plugin version check modes**: **consumed as-is.** No sub-task touches a `MANIFESTS` file; P7b raises the version at landing.
- **Brief linkage selector**, **Merge-direction check**, **Parent Branch Delivery Rule**: consumed as-is.
- **Section-scoped registry sync**: block 4 appends to the Universal tier only.

---

## New Mechanisms (if any)

- **Name:** Hook registration check.
- **Purpose:** the one plugin-owned place where the five Registration rules live. A project runs it against its own settings, so it carries no copy of the tests.
- **Why an existing mechanism was not sufficient:** `plugin_doctor.py --drift` compares files with the plugin's copies, not settings rows with a project-owned expectation, and its exit and no-write rules belong to install drift. The finish-install readiness checks judge rows against the plugin's `hooks.json`, not against the project's own record. Neither can say "this row's `if` changed" or "a row exists that nobody recorded".
- **Proposed location:** `.claude/scripts/check_hook_registrations.py` (a vendored script), tests under `.claude/scripts/tests/`.
- **Extension seam:** a new rule is one entry in the rule tuple, one pure function `(settings rows, registration profile) → findings`, and one test pair.
- **Will this be promoted to `MECHANISMS.md` after implementation?** yes (block 4).

---

## Extension Points

- `check_hook_registrations.py` exposes pure `load_settings(bytes) → settings` (the one Settings shape validator; raises one error type carrying the kind and JSON path), `read_rows(settings)`, `build_hook_registration_profile(settings, previous|None)` (no time argument), `serialise(hook_registration_profile) → bytes`, `check(settings, hook_registration_profile) → [Rule result]`, and `main()`. The installer import sits in a `try` at module level; on `ImportError`, `main()` refuses `checker-dependency-missing`.
- `auto_improve_finish_install.py` adds the `record-registrations` subparser and `propose_hook_registration_profile` / `apply_hook_registration_profile`, importing `check_hook_registrations` inside those functions only (no circular import; the second installer copy this loads is covered under Data Shapes), and reading settings through its `load_settings`. `_parse_settings`, `hooks` and `addon` are untouched.
- `land_contract.py` adds pure `failure_units(readings)` and `attribute_failure(unit, step, sides, expand)` (`sides` = contract diff, default-branch diff, landing's own paths), called from `_p8_verify`, and extends `details["verification-not-ready"]`. `_land` captures the P7 merge diff before line 2175 reassigns it, and the P7b commit's paths.
- **The `next_command` seam.** `make_report` hands `next_command_for_outcome` only an allow-listed set of facts (`land_contract.py:1739-1741`). The P8 halt (`raise halt("verification-not-ready", …)`, `:2197`) passes `all_outside_diff` and `step_failures_only`, and both join that allow-list; without it the facts would land in the report body and never reach the advice. `next_command_for_outcome("verification-not-ready")` (not `verify_here`) returns `outside_diff` equal to `all_outside_diff` (false when absent). Order: the `repeat` branch first (unchanged; it never fires for step units); then, when `step_failures_only`, commands are `[advance_line]` only and the reason is "the failing steps are read by exit code, which the baseline does not cover, so re-recording cannot change the result: check whether the default branch fails the same step (<ids>); if it does, fix it there, then rerun" — no re-record line; otherwise the existing branch, with the Q1 advice prefixed when `all_outside_diff` is true.
- `.claude/work-item-conventions.json` → `contractLanding.verification.steps` gains `hook-registration-tests`, running `py -3 .claude/scripts/tests/test_check_hook_registrations.py`, read by exit code. It applies from the landing after this one, because P8 reads the config from `origin/<default>`.
- **A consuming project's landing step** (documented in the README by block 4) passes its inputs as arguments: `py -3 -B .claude/scripts/check_hook_registrations.py --settings .claude/settings.json --hook-registration-profile .claude/hook-registration-profile.json`, with no `when_paths`, from the vendored five-file set (the only supported way: the step must name the checker at a path inside the repository). The step unit then names the checker and both project files, so in issue #148's case (the default branch changes `.claude/settings.json`, the contract does not) FA-4 reads `outside-diff`, and `step_failures_only` steers the operator to the default branch instead of a re-record. Chosen over `when_paths` because a path match never decides a side (FA-5), and over leaving it `undetermined` because the brief asks for the split in exactly this case. The four dependency scripts are not named; a failure caused only by one of them is `undetermined`, stated in the README.

---

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| check_hook_registrations.py | auto_improve_finish_install.py | guarded Python import | rows, Registration key | checker → installer readers |
| auto_improve_finish_install.py (record-registrations) | check_hook_registrations.py | function-level import | Hook registration profile | installer → shape owner |
| A consuming project's landing step | check_hook_registrations.py | subprocess, exit code | Check report | project → plugin script |
| land_contract.py `_p8_verify` → P8 halt → `make_report` | Verification Record, `report.json` and its `next_command` | JSON record; the `make_report` fact allow-list | Failure attribution, `all_outside_diff`, `step_failures_only` | script → `/advance` |

**Changes to existing integration surfaces:**
- [ ] The Verification Record gains two keys, additively. `_read_json` and the cached-READY reuse ignore unknown keys.
- [ ] `make_report`'s fact allow-list gains `all_outside_diff` and `step_failures_only`; `next_command` for `verification-not-ready` gains `outside_diff`, and drops the re-record command when every unit is a step. `/advance` reads it as data. No skill text changes.

---

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold.

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

---

## Chat Tool Impact (REQUIRED when this contract adds or changes a REST endpoint or SignalR event)

2. **No.** No REST endpoint or SignalR event is added. These are local scripts.

---

## Non-Goals

- Any edit in the consuming project (`StockToolScalpingMachine`), and deciding whether it re-records its baseline.
- Measuring hook run time (Q2: "profiled" is not the timing profiler).
- Judging the user or local settings layers, group keys other than `matcher`, or committing a Hook registration profile for the plugin's own `hooks.json` (Q3).
- Changing the P8 verdict, gate order, exit codes or baseline format. Attribution is advice.
- Attribution in `--verify-here`; its record keeps its current keys.
- Running the default branch's suites automatically during a landing.
- Raising the plugin version in any sub-task.

---

## Confidence

Confidence: High on the checker, its refusals, the single validator and the P8 seam (lines cited under Uncertain Assumptions). Medium on the import chain: `pr_merged.py` and `plugin_doctor.py` import-time behaviour was not traced line by line; it rests on block 1's copy-outside-the-repository test. Medium-High on rule coverage of the project's five tests (mapping accepted in Q2).

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** a standalone read-only checker, a committed Hook registration profile, a recorder in finish-install, advisory attribution in P8. A registration change must be re-recorded in the same pull request, so it shows in that diff and not in someone else's landing.
- **Option B (rejected):** a `--registrations` mode of `plugin_doctor.py`. Its suite pins "never write an existing file", so it cannot hold the recorder; splitting rules from recorder gives two readers of one shape.
- **Option C (rejected):** compare settings with the same file at a git ref. That is the coupling that broke the landing: the base moves with the default branch.
- **Option D (rejected):** attribution that changes the verdict. It would turn a heuristic into a gate that can ship a real break.
- **Option E (rejected, W1):** a self-contained checker with its own copy of the Registration key logic. Two readers of one shape drift; a guarded import with a named exit-2 refusal and a documented file set keeps one reader and still fails closed.

---

## Uncertain Assumptions

- `ASSUMED`: Claude Code's hook `if` is opaque to the checker: compared as JSON, never interpreted.
- `ASSUMED`: a consuming project receives `.claude/scripts/*` only as vendored assets its sync config lists (scripts are not Plugin-delivered assets). The checker's import chain is `check_hook_registrations.py` → `auto_improve_finish_install.py` → `pr_merged.py` + `plugin_doctor.py`, and `pr_merged.py` → `check_version_bump.py`. Block 4's README lists all five files, and `checker-dependency-missing` names them when one is absent. Verification path: block 1's test runs the checker alone in a temporary folder and asserts exit 2 with that code.
- `VERIFIED via .claude/scripts/auto_improve_finish_install.py:78-83`: the installer sets `sys.dont_write_bytecode = True` only after it was itself cached, and inserts its own folder into `sys.path` (Data Shapes, Import side effects and bytecode).
- `ASSUMED`: importing `pr_merged` and `plugin_doctor` writes nothing and needs no Project profile. Verification path: block 1 runs the checker in a fresh process from a temporary project with no Project profile and asserts the tree is byte-identical afterwards.
- `VERIFIED via .claude/scripts/auto_improve_finish_install.py:1030-1107, 1277-1308`: `_hook_key` returns none for a row with no `.py` file, hence the `command:` identity. `_iter_hooks` skips malformed parts silently, and `_parse_settings` refuses duplicate keys at every level but checks shape only to group level and defaults a missing group `hooks` to `[]`; hence the one `load_settings` validator, tested at each malformed level (event value, group, group `hooks`, handler, `command`, `args`) and for duplicate keys, in both the check and the recorder.
- `VERIFIED via .claude/scripts/land_contract.py:857-862, 2968`: an `exit-code` step's reading is `regression` with empty `new_failures`, and V2 names it `step <id>`; hence the step unit.
- `VERIFIED via .claude/scripts/land_contract.py:1496-1510, 1736-1752, 2165-2177, 2197, 2556-2564`: the `verification-not-ready` advice and its `<suite ids>` placeholder, the fact allow-list, P7b (may commit nothing; reassigns `merge_diff`), the P8 halt's keywords, and the `reasons`-only route to `NOT-READY`.
- `VERIFIED via .claude/work-item-conventions.json:91-112`: every step reads by exit code and none has `when_paths`.
- `VERIFIED via .claude/scripts/land_contract.py:1315-1334, 2404, 2175`: steps apply on contract diff ∪ merge diff, both computed in `_land`.
- `VERIFIED via .claude/hooks/hooks.json`: the plugin's rows carry no `if`.
- `VERIFIED via .claude/area-mapping.json`: its `areas` object is empty, which is why the cross-area scan has no signal; the main session may re-run `py -3 .claude/scripts/cross_area_scan.py` to confirm.

---

## Failure Modes & Mitigations

- **FM:** a missing, garbled or partly malformed input reads as a pass. **Mitigation:** the seven exit-2 codes and the whole-tree settings shape, each tested, including root set but file absent.
- **FM:** a vendored checker without its dependencies exits 1 with a traceback, read as "a rule failed". **Mitigation:** `checker-dependency-missing` and `checker-internal-error`, exit 2.
- **FM:** preview and apply never agree, or an unchanged re-record rewrites the file. **Mitigation:** RP-1 and RP-2 (no volatile value); block 2 tests preview → apply success and re-record → nothing to write.
- **FM:** a re-record drops hand-written Exclusions. **Mitigation:** RP-8 and the `hook-registration-profile-unreadable` refusal.
- **FM:** a hand edit lists a row as expected and excluded, or duplicates an Exclusion. **Mitigation:** RP-6 and RP-7 make the file unreadable; HR-5 names a stale Exclusion.
- **FM:** PowerShell 5.1 redirection writes UTF-16. **Mitigation:** the recorder writes UTF-8 itself; UTF-16 is refused, never a pass.
- **FM:** an add-on install writes rows and the check fails. **Mitigation:** intended and visible in that pull request; the remedy names `record-registrations`.
- **FM:** attribution names the wrong side. **Mitigation:** it never changes the verdict; only named files decide a side; a file in both diffs, or changed by the landing itself, is `undetermined`; reasons state what changed, not what caused the failure; the advice says to confirm on the default branch first.
- **FM:** attribution says nothing for exit-code steps. **Mitigation:** the step unit, the FA-5 reasons and the note; block 3 tests it on this repository's own steps.
- **FM:** the advice sends the operator to a re-record that cannot change the result (a `reasons` halt, or exit-code steps only). **Mitigation:** both advice facts need no reasons and at least one unit; `all_outside_diff` needs a `test` unit; `step_failures_only` drops the re-record command and points to the default branch; tested.
- **FM:** the advice is right in a unit test but never reaches a real report. **Mitigation:** both facts join the `make_report` allow-list, and block 3 tests both branches through an end-to-end landing fixture.
- **FM:** a vendored checker writes `__pycache__` and the landing halts on "the steps changed the worktree". **Mitigation:** the checker sets `dont_write_bytecode` before its import, the README step uses `-B`, and block 1 tests a copy outside this repository.
- **FM:** the new validator changes how the `hooks` or `addon` subcommands read settings. **Mitigation:** `_parse_settings` is untouched; block 2 adds a regression test.
- **FM:** circular import. **Mitigation:** function-level import in the installer; a fresh-process import test for each module.

---

## Open Questions for User

- [x] **Q1: where does "check the default branch before re-recording" belong?** Answer (2026-11-01, user accepted): in `land_contract.py`, as the `next_command` reason, only when every new failure unit is `outside-diff`; not in the checker's output. Narrowed after rounds 2 and 3 (user accepted): only when the halt has no `reasons` and at least one unit is a named regression the baseline covers; when every unit is an exit-code step, the reason says "check whether the default branch fails the same step" and no re-record is suggested (The advice facts).
- [x] **Q2: do the rules cover the project's five tests, and does "profiled" mean the timing profiler?** Answer (2026-11-01, user accepted): the mapping stands (`test_hook_gating` → HR-3, `..._apart_from_if_keys` → HR-2, `test_row_count_is_unchanged` → HR-1, `test_profile_setup` → record round-trips and checks clean, `..._profiled_or_excluded` → HR-4 on the shipped `hooks.json`); "profiled" means recorded in the Hook registration profile; further rules come later through the extension seam.
- [x] **Q3: should the plugin commit a Hook registration profile for its own `hooks.json`?** Answer (2026-11-01, user accepted): no; the test records one on the fly.
- [x] **Q4: is `.claude/hook-registration-profile.json` the name and location?** Answer (2026-11-01, user accepted): yes.

No question is open.

---

## Critique

(Rounds 1 to 3 moved to `.claude/contract-history/2026-10-31-plugin-owns-hook-mechanism-tests.round-<n>.md`. Round 3 ended with 0 BLOCKER, 2 WARN, 6 NIT; the user accepted all eight fixes on 2026-11-01 and a fourth critic pass was skipped by the user's choice.)

## Lessons referenced

- **2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file** — heeded by `paths-not-given`, `settings-missing`, `hook-registration-profile-missing`, with block 1 tests.
- **2026-10-15 — A script that reads a project-owned file must be told which project** — heeded: explicit paths only.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by the one `load_settings` validator (duplicate keys included), a test per malformed level, and the installer's import side effects recorded as VERIFIED rather than assumed away.
- **2026-10-04 — Detect an install mode by what the sync actually delivers** — heeded by `checker-dependency-missing` and the five-file vendored set in the README.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded: every refusal exits 2, tested.
- **2026-10-05 — A documented "missing file means the default" must read one named location only** — heeded: project layer only.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded: the recorder extends Preview-hash apply.
- **2026-10-28 — A new term's definition must be true against every existing member** — heeded: Registration row identity covers rows with no `.py` file and non-command types.
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — heeded: attribution adds no refusal; remedies name `record-registrations`.
- **2026-10-30 — Widening a CI trigger changes who the check judges** — heeded: the new landing step names the landing it first applies to.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded: block 3's test derives steps from the conventions file, and block 1's `$comment` names it.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded by this amendment (every round-1 to round-3 finding the user accepted, and every answer, is in the body and the handoff blocks).
- Orthogonal to north-stars: none active (`.claude/north-stars/` is absent; the brief's grade is confirmed).

---

## Implementation Handoff

**Delivery:** parent branch `feature/148-plugin-owns-hook-mechanism-tests` (Parent Branch Delivery Rule). No block lists a version file. The landing's P7b raises the version once (0.12.1 → 0.13.0).

### 1. Registration checker and tests (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/check_hook_registrations.py`
- `.claude/scripts/tests/test_check_hook_registrations.py`
- `.claude/scripts/tests/fixtures/hook-registrations/settings.json`
- `.claude/scripts/tests/fixtures/hook-registrations/hook-registration-profile.json`
- `.claude/work-item-conventions.json`

**Pre-written TASK block:**
```
TASK: Write the Hook registration check and its suite, and add the hook-registration-tests landing step.
CONTEXT: concept contract at .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md (Data Shapes:
  Hook registration profile RP-1..RP-8, Settings shape, rules HR-1..HR-5, the seven refusals, exit codes).
FILES: as listed.
CONSTRAINTS:
  - Tests first; watch them fail. Import _iter_hooks, _hook_key, _compare_extras from auto_improve_finish_install
    inside a module-level try; do not edit that file. On ImportError, main() refuses checker-dependency-missing
    (exit 2) naming the module and the five-file set; any other exception is checker-internal-error (exit 2).
  - build_hook_registration_profile takes no time argument; serialise follows RP-2. Assert that two builds from the same
    input give identical bytes.
  - Test classes, the equivalents of the five project tests: HookGatingTests.test_hook_gating (HR-3),
    RegistrationRowsUnchangedTests.test_hooks_block_equals_base_apart_from_if_keys (HR-2),
    RegistrationRowsUnchangedTests.test_row_count_is_unchanged (HR-1), ProfileSetupTests.test_profile_setup
    (round-trips and checks clean; a re-record keeps Exclusions, stale ones included),
    RegistrationCoverageTests.test_real_settings_every_registration_is_profiled_or_excluded (record from the
    shipped .claude/hooks/hooks.json inside the test, check clean, add one unrecorded row, get an HR-4 fail).
  - load_settings is the one Settings shape validator (block 2 reuses it): one error type carrying a kind
    (encoding, json, duplicate-key, not-object, shape) and the JSON path. Flag --hook-registration-profile, report
    key hook_registration_profile, codes hook-registration-profile-missing / -unreadable (naming rule).
  - Failure path: break each rule in turn; assert exit 1 naming that rule only. A fixture breaking all five gets
    five FAIL lines. Each refusal code gets exit 2: --project set with settings absent, UTF-16, invalid JSON,
    a duplicate key (top level and handler level), non-object hooks, and each malformed level (event value,
    group, group hooks absent or not a list, handler, command, args). RP-4..RP-7 breaches are hook-registration-profile-unreadable; one Exclusion covering two
    duplicate rows passes. The checker copied alone into a temporary folder exits 2 with
    checker-dependency-missing. No hooks key is valid. A row with no .py file gets the command: identity.
  - Bytecode: the checker's first statement sets sys.dont_write_bytecode = True, before the guarded import.
    Test: copy the five files into <tmp>/proj/.claude/scripts/ (a temp folder outside this repository, so no
    .gitignore hides anything; no Project profile), run the COPY in a fresh process from <tmp>/proj, once with
    py -3 -B and once with plain py -3; after each the whole <tmp>/proj tree is byte-identical (no __pycache__,
    no file written).
  - Generic fixture: no project name; paths use ${CLAUDE_PROJECT_DIR}.
  - Add {"id": "hook-registration-tests", "command": ["py","-3",
    ".claude/scripts/tests/test_check_hook_registrations.py"], "results": {"format": "exit-code"},
    "timeout_minutes": 5} after loop-script-tests, and to the block's $comment one sentence about it plus one
    naming .claude/scripts/tests/test_land_contract_verification.py as the test that reads these steps.
  - Run: py -3 .claude/scripts/tests/test_check_hook_registrations.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
  contract_status: approved
```

### 2. Hook registration profile recorder (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`

**Pre-written TASK block:**
```
TASK: Add the record-registrations subcommand (preview, and --apply --expect-sha256) that writes
.claude/hook-registration-profile.json through Preview-hash apply.
CONTEXT: concept contract (Commands: Preview/Apply hook registration profile; RP-1..RP-8; naming rule).
FILES: as listed.
CONSTRAINTS:
  - Import check_hook_registrations inside the two new functions only. Add a test importing each module first in
    a fresh process, and one running `py -3 -B auto_improve_finish_install.py record-registrations` as a script
    (the installer is __main__, so a second installer copy loads; preview then apply succeeds). Pass only plain
    data between the copies (Data Shapes, The second installer copy).
  - A group with no hooks key is refused unexpected-settings-shape (tested); _parse_settings still accepts it.
  - The plan hash covers settings bytes, existing file bytes (or "absent") and planned bytes, all deterministic.
    Test: preview then apply succeeds; apply after a settings change is changed-since-preview; an unchanged
    re-record reports nothing to write and leaves the file byte-identical.
  - Add registration-settings-missing and hook-registration-profile-unreadable to REFUSAL_CODES (exit class 2).
    Read settings through check_hook_registrations.load_settings only: kind shape -> unexpected-settings-shape,
    every other kind -> malformed-settings (each malformed level and a duplicate key, tested). Reuse write-failed
    and the symbolic-link refusal.
  - Do NOT change _parse_settings. Regression test: a settings file with a handler-level breach (a handler with
    no type) is still accepted by _parse_settings, and the hooks and addon subcommands' existing tests stay green
    unchanged.
  - Keep existing Exclusions verbatim (RP-8) and list stale ones in the preview. Messages say "hook registration
    profile" in full, never bare "profile". Update the module docstring's Usage lines.
  - The existing suite stays green. Run: py -3 .claude/scripts/tests/test_auto_improve_finish_install.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
  contract_status: approved
```

### 3. Failure attribution in the landing report (`python-ai-developer`)

**Depends on:** 1 (its test reads the conventions file, whose step list block 1 extends)

**Files to touch:**
- `.claude/scripts/land_contract.py`
- `.claude/scripts/tests/test_land_contract_verification.py`
- `.claude/scripts/tests/test_land_contract.py`

**Pre-written TASK block:**
```
TASK: Build failure units, attribute each (FA-1..FA-5), record them in the Verification Record, split the
verification-not-ready detail, and carry the Q1 advice into report.json's next_command.
CONTEXT: concept contract (Data Shapes: Failure units, The empty list, Files a unit names, Attribution sides,
  FA rules, The advice facts; Extension Points: The next_command seam; Q1).
FILES: as listed.
CONSTRAINTS:
  - failure_units and attribute_failure are pure. Pass the three sides separately (never a union): contract
    diff; the P7 merge diff captured before P7b reassigns merge_diff, minus hand-resolved paths; landing's own
    paths = diff(HEAD captured before P7b, HEAD after P7b) (empty when P7b commits nothing) plus hand-resolved
    paths plus the MANIFESTS version files. Step applicability keeps using the post-P7b merge_diff.
  - A regression step with no named failures yields exactly one unit "step <id>". On a non-NOT-READY verdict the
    list is [] and there is no note. unittest-text names a file by whole-segment path suffix, unique match only.
  - Only named files decide in-diff/outside-diff; a when_paths match only feeds an FA-5 reason.
  - Add all_outside_diff and step_failures_only (The advice facts) to the P8 halt's keywords AND to make_report's
    fact allow-list. next_command: repeat branch first, unchanged; then step_failures_only -> [advance_line] and
    the "check whether the default branch fails the same step" reason, no re-record line; otherwise the existing
    branch, returning outside_diff and prefixing the Q1 advice when all_outside_diff is true.
  - Verdict, gate order, exit codes, baseline format and the --verify-here record are unchanged. New keys are
    additive. TestVerificationRecordShape and the existing tests stay green unchanged.
  - Tests (unit): one per rule FA-1..FA-5, each with a control; a file in both diffs is undetermined; a file
    changed only by the version-raise commit, or a version file when P7b committed nothing, is undetermined.
    Load this repository's .claude/work-item-conventions.json steps and fail each as exit-code, deriving every
    expectation from the loaded steps (no hard-coded step id or count): every step gets one entry with a
    non-empty reason and the note is written; for each step whose command names a file (rule in Files a unit
    names), that file in the contract diff gives in-diff and in the default-branch diff only gives outside-diff;
    each step naming no file stays undetermined with the "names no file" reason. Assert at least one step of
    each kind exists, so the test cannot pass vacuously.
  - Tests (issue #148 case): a step shaped like the README step (py -3 -B check_hook_registrations.py --settings
    .claude/settings.json --hook-registration-profile .claude/hook-registration-profile.json, no when_paths)
    with .claude/settings.json in the default-branch diff only gives outside-diff, step_failures_only true,
    all_outside_diff false.
  - Tests (empty list): a NOT-READY from reasons only (forbidden path, every step ok) gives [], the
    "no step regressed" note naming the reason, both facts false and no advice.
  - Tests (real report path, in test_land_contract.py, using its end-to-end landing fixture), both branches:
    (a) a named test regression attributed outside-diff halts verification-not-ready and report.json's
    next_command carries outside_diff true, the Q1 advice and the re-record command; (b) an exit-code step
    failing outside-diff carries outside_diff false, the "default branch fails the same step" reason and no
    re-record command; a control with an in-diff failure carries neither advice. The repeat-after-re-record
    branch keeps precedence and shows no advice.
  - Run: py -3 .claude/scripts/tests/test_land_contract_verification.py and
    py -3 .claude/scripts/tests/test_land_contract.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
  contract_status: approved
```

### 4. Registry appends and release notes (`python-ai-developer`)

**Depends on:** 1, 2, 3

**Files to touch:**
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `README.md`

**Pre-written TASK block:**
```
TASK: Append the four proposed VOCABULARY terms (Registration row, Hook registration profile, Registration rule,
Failure attribution) and a MECHANISMS entry "Hook registration check" (Extend-by: one rule tuple entry, one pure
function, one test pair) to the Universal tier. Add one correction line under Preview-hash apply naming the
record-registrations subcommand. In README, add a short "Checking your hook registrations" section and a
change note headed "Hook registration checks (issue #148)".
CONTEXT: concept contract (New terms, naming rule, New Mechanisms, Extension Points, Q1-Q4 as answered).
FILES: as listed.
CONSTRAINTS:
  - Append only, at the end of the Universal tier. Never edit or reorder an existing entry. Regenerate the digest
    if the generator exists. Never write bare "profile" for the new concept. Add no entry for report.json or
    next_command (they are script outputs, not terms).
  - The README text is version-agnostic: no version number anywhere in the new text, so it cannot go stale
    before the landing's version raise, which is the only place the number is set. No version file edit.
  - The README section tells a project to: record its hook registration profile (record-registrations); vendor
    all five files (check_hook_registrations.py, auto_improve_finish_install.py, pr_merged.py, plugin_doctor.py,
    check_version_bump.py) through .sync-config.json (the only supported way for the landing step, which must
    name the checker at a path inside the repository; never say "or run from the plugin root"); add a landing
    step running exactly: py -3 -B .claude/scripts/check_hook_registrations.py --settings .claude/settings.json
    --hook-registration-profile .claude/hook-registration-profile.json (no when_paths), and why: -B and the
    checker keep Python from writing __pycache__ into the tree (which would halt the landing on "the steps
    changed the worktree"; a harness importing the checker without -B can still cache it), and naming the input
    files lets the landing say whether a failure came from the contract or the default branch, while a failure
    caused only by one of the four dependency scripts reads as undetermined; delete its own hook-registration
    tests and baseline entries. Every command in a form that runs in PowerShell.
  - Also state, for this repository: its hook-registration-tests landing step names only its test file, so a
    break in check_hook_registrations.py itself reads undetermined there ("no file the failure names is in
    either diff"), because the suite reaches the checker by import, not as a step argument.
  - State Q1's answer in the note, as narrowed: the advice only for named regressions; for exit-code steps,
    check whether the default branch fails the same step, never a re-record.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
  contract_status: approved
```

### 5. Review (`fullstack-code-reviewer`)

**Depends on:** 4

**Files to touch:**
- `.claude/reviews/2026-10-31-plugin-owns-hook-mechanism-tests/t5-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review sub-tasks 1-4 against this contract and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
FILES: .claude/reviews/2026-10-31-plugin-owns-hook-mechanism-tests/t5-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check:
    * HR-1..HR-5, RP-1..RP-8, the Settings shape and the seven refusal codes, each with a test;
    * the profile bytes hold no volatile value, and preview → apply succeeds;
    * the five equivalent tests exist and run;
    * the checker is the only place the rules live;
    * every exit-code step gets a step unit with a reason; FA-1..FA-5 are advisory (verdict, exit codes unchanged);
      only named files decide a side; a reasons-only NOT-READY gives [] and no advice;
    * all_outside_diff needs a named test unit; step_failures_only drops the re-record command and names the
      default-branch check; both are in make_report's allow-list and reach report.json through real landing
      tests, one per branch;
    * landing's own paths use HEAD captured before P7b and include the version files;
    * the checker sets dont_write_bytecode before its import, and the tree-unchanged test runs a copy outside
      this repository; record-registrations is tested run as a script;
    * one Settings shape validator (load_settings) serves both check and recorder and refuses a hooks-less
      group; _parse_settings unchanged;
    * block 3's conventions test hard-codes no step id or count, and the conventions $comment names it;
    * the Q1 answer (as narrowed) is in the code and the README; the README lists the five-file vendored set,
      the py -3 -B explicit-argument step with no plugin-root alternative, the undetermined limit for this
      repository's own step, and no version number;
    * no bare "profile" names the new concept; no module-level circular import;
    * no sub-task pull request changes a version file; the registry appends are verbatim and Universal-tier.
  - Write the six-section artefact. The file does NOT exist yet; you create it. Name the commit range base..head.
  - "## Evidence" lists the commands with their exit codes and is never empty.
  - The header ends with exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings",
    "**Verdict:** blocked".
  - Write the Gate Output <artefact stem>.gate.json beside it, covering every Review checklist item.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-31-plugin-owns-hook-mechanism-tests.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both backend and frontend sides
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
- [ ] `Status` flipped to `implemented`
