# t9 review — fullstack-code-reviewer

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t9-review (issue #249, parent issue #235)
- **Contract:** `.claude/concepts/2026-11-04-domain-split-registries.md` (approved, amendment 3)
- **Reviewed on:** 2026-11-06
- **Commit range reviewed:** `dca00fd..70c8e6b` (parent branch `fix/235-domain-split-registries`, from the commit that added the approved contract and the nine briefs to the merge of pull request #280, t8)
- **Sub-task merges in the range (first parent):** t1 `c844c53` (#250), t2 `603a816` (#252), t3 `d21919b` (#254), t4 `e041320` (#256), t5 `094a01b` (#258), t6 `d70f793` (#273), t7 `9be2508` (#278), t8 `70c8e6b` (#280)

**Verdict:** blocked

## What was checked

Each brief acceptance criterion is on one line. The outcome comes first, then the evidence.

- **Spec and markers.** Met. `.claude/references/registry-layout.md` exists, carries "## 12. For the sync tool", every rule id and every `R4_EXCLUDED_PREFIXES` entry (`SpecTests` passes). Line 1 of all three root files is `<!-- registry-layout: 2 -->`, and `--check` reports `current`.
- **Single write path, the four §2.2-B writers.** Met. `agents/fullstack-code-reviewer.md`, `skills/journal-add/SKILL.md`, `skills/design-first/SKILL.md` (Steps 3 and 5, plus the receiver "Run the data-architect's registry appends") and `agents/data-architect.md` (`Registry appends:` under `.claude/cache/registry-appends/`) all name `registry_append.py` through the lookup block with `--project "$CLAUDE_PROJECT_DIR"`. `test_plugin_text_scans.py` pins the fallback sentence and the absence of Edit-append instructions.
- **Domain-file fallback never writes project content into a root.** Met. In `registry_append.py:317-329`, the non-`--universal` branch only ever targets `<REG>/<slug>.md`. On `pending`/`stale-sync`, an unknown `--domain` falls back to `general` and the advisory names it. Tests: pending root with no `## Project:` section (root bytes unchanged), and stale-sync.
- **Rejection tests.** Met. `test_registry_append.py` has one test per closed-set code, including `project-undetermined` (unset and absent), `layout-unknown`, `registries-absent` and `no-universal-tier`: 29 tests, exit 0.
- **Every reader on the resolver, with general.md named.** Partly met. `cross_area_scan`, `north_star_review`, the digest, `accuracy_update`, the tracker hook, `plugin_doctor` and `--check-structure` read through `registry_files` / `_registry_layout`. `data-architect` and `contract-critic` name all three `general.md` files and the focus rule. The exception is the default (non-structure) mode of `validate_registries.py`, which still reads only the two root files (W4).
- **R1-R6 (R4 advisory), advisory mode, verify-before-done.** Met. `test_registry_layout.py` has a pass and a fail case per rule, the advisory and `current` exits, and `--strict`. Live: `--check-structure` exits 0 on `current`, with advisory lines only, and `--strict` exits 1 (R4). `skills/verify-before-done/SKILL.md:253` runs `--check-structure` and says that exit 1 is NOT-READY.
- **Strict digest with tier labels and legacy entries.** Met by tests. `generate_registry_digest.py` drops `DOMAINS`, groups by `rl.tier_label`, writes `SOURCES_LINE` and indexes legacy entries. I did not run the generator live, because it writes `.claude/.scout-cache/registry-digest.md`, which is outside this task's two-file write list.
- **Tracker: any journal file, once across worktrees, no retroactive fires.** Met. `process_journal_change` keys `seeded_files` by `checkout_equivalent_path` (case-folded on Windows) and seeds unseeded files without firing. `fresh` always fires. The old-cache upgrade seeds the root key only. All 13 tracker tests pass, including the two-worktree test and the pinned Accepted guard limit. The one gap is the grammar (W1).
- **0001 dry-run / apply / idempotence / entry and text no-loss, on the client, stale-sync and vendored fixtures.** Partly met. Dry-run writes nothing, apply with the hash makes both fixtures `current`, and a second apply has an empty plan before any git check. Text-level I-12 is a per-instance multiset check, and a forced plan that drops a line gives `content-loss-detected`. However, the entry-level I-12 check compares only the key sets and the counts (W3). All 33 tests pass.
- **Leftovers.** Met. `test_leftovers_are_verbatim_and_the_last_section_of_general`. Leftovers sit under the one heading, as the last section of `general.md`, and are excluded from R4 and the tracker.
- **Token entries (plugin-owned and unverified kept).** Met. `test_token_entries_universal_candidates_and_token_lines` and `test_without_a_separate_plugin_root_every_token_entry_is_unverified_and_kept` (vendored fixture (d)) pass, and the report names the reason.
- **The gate exits 6/0 and the doctor reports the state.** Met. `--check` exits 0 here (`current`). Tests cover 6 before and 0 after, 6 for stale-sync, and 0 for absent / 2 for unknown. Doctor: "registry layout: current", "body-less journal entries: 0", the `--json` key `registry_layout`, and the three `general.md` `copy` requirements (`plugin_doctor.py:78-86`).
- **Skeletons.** Met. `.claude/templates/registries/<REG>/general.md` is byte-identical (`cmp`) to `.claude/registries/<REG>/general.md` for all three registries.
- **README note, file list and procedure.** Met. "Domain-split registries (issue #235)" (`README.md:468`) lists all eight new paths and the finish-install import. "Moving a project onto registry layout 2" (`README.md:1262`) gives the PowerShell-runnable steps, the refusal codes, stale-sync, the orphan `--archive-title-only` line and the sync-tool follow-up.
- **Refusals leave files unchanged and write a report.** Met for every refusal code after the project is known: `Run.finish` writes `report.json` and the `.md` before it exits. The conflict, uncommitted, changed-since-preview and forced-replace-failure tests assert byte-identical files. With `project-undetermined` there is nowhere to write a report, which is acceptable.
- **I-1..I-14.** I-1 met (`_registry_layout.layout_state:520-554` follows the definition clause by clause). I-2 and I-3 met. I-4 met (R6 hashes `INTEGRATION.md` when present). I-5 to I-8c met in `_registry_layout`, but I-8 is not honoured by the tracker's own parser (W1). I-9, I-10, I-11 and I-13 met. I-12 partly met (W3). I-14 met.
- **Stated deviations.** Met. R5 uses on-disk discovery with no `registries.domains` slot. A1 is implemented as a separate rule. R4 is advisory except under `--strict`. `skills/ship/SKILL.md` has a 0-line diff in the range.
- **`_preview_apply` and `_plugin_root` as the single definitions.** Met. `_plan_digest`, `_atomic_write`, `stage_and_replace`, `_separate_plugin_root` and its helpers are defined once, in those modules. `auto_improve_finish_install.py` drops its copies and imports them back. Other `_norm` / `_atomic_write` definitions (`land_contract.py`, `cleanup_delivered.py`, `flat_worktree.py`, `pr_merged.py`) are unrelated helpers that predate this contract. `registry_migrate` never imports finish-install (test).
- **No reader still reads one flat file.** Partly met (W4).
- **No sub-task pull request changes a version file.** Met. No manifest is in `git diff --name-only dca00fd..HEAD` (only the fixture `tests/fixtures/registry-migration/plugin/.claude-plugin/plugin.json`). `check_version_bump.py` in parent mode exits 0: "sub-task pull request keeps version 0.14.5; the landing raises it".
- **Off-area drift.** Nothing to compare. `.claude/area-mapping.json` has an empty `areas` map, so `derive_area.py` returns `uncategorized` for the contract and for every file. Every changed file is on a sub-task's `Files to touch` list, apart from the eight brief bookkeeping edits under `.claude/work-items/`.

## Findings

### C1 (critical) — `test_registry_layout.py` exits 1 on the parent branch: the pin still expects `pending`. `.claude/scripts/tests/test_registry_layout.py:747`

```python
self.assertTrue(lines[0].startswith("advisory: registry layout pending"), lines[:3])
```

t3 pinned the state of this repository when it was still flat. t8 then migrated the repository to layout 2, as the contract requires, so `--check-structure` no longer prints the layout advisory, and the first line is now an R4 line. The assertion fails (73 tests, 1 failure). The product is right and the pin is stale. However, the contract's own suite is red on the branch that is about to land. No CI workflow runs the unittest suites (only `version-bump.yml`), so nothing caught it. t8's brief had no `Run:` line, so t8 never re-ran t3's suite after flipping the state the suite pins.

Fix: pin the post-t8 state, so the test keeps guarding the "R4 advisory lines only" expectation from t8's brief.

```python
lines = [ln for ln in done.stdout.splitlines() if ln.strip()]
self.assertFalse(any(ln.startswith("advisory: registry layout") for ln in lines), lines[:3])  # current since t8
for ln in lines:
    self.assertTrue(ln.startswith("advisory: R4 ") or ln.startswith("digest: "), ln)
```

Also run `registry_migrate.py --check --project <repo>` in the same test and assert exit 0.

### W1 (warning) — The tracker keeps its own journal grammar, and that grammar ignores fences (I-8). `.claude/scripts/accuracy_update.py:404-438`

`_ENTRY_HEADER` moved from the hook into `accuracy_update` unchanged. `parse_journal_entries` scans the raw text. The contract makes `_registry_layout` the sole owner of the grammars, and names "tracker `ENTRY_HEADER`" as one of the two duplicates it replaces. This is now a third grammar beside `rl.parse_text`. It also parses inside fenced blocks. A `### 2026-…` heading in a fenced sample, or in a migration-leftover fence in `JOURNAL/general.md` (I-8: "fenced code blocks are never parsed"), gets a signature and can fire. Seeding makes this unlikely on a first sight, but a fenced dated heading added later to a seeded file fires. No test covers a fence for the tracker (`test_journal_post_approval_tracker.py` has none).

Fix: build the entries from `rl.parse_text(text, "JOURNAL", kind=...)`, keeping entries of kind `entry` only (legacy entries never fire, I-8c). Keep the signature as `sha1(date|title)`, with the title taken from the heading exactly as today, and pin with a test that signatures are unchanged on this repository's 41 entries. Add a fenced-heading test that expects zero fires.

### W2 (warning) — `stage_and_replace` backs up under the whole absolute path, not the relative path. On this worktree that is 274 characters. `.claude/scripts/_preview_apply.py:58-61`

```python
resolved = Path(os.path.abspath(str(target)))
return Path(*resolved.parts[1:]) if resolved.anchor else resolved
```

The contract says `backup_dir/<relative path>`. The implementation repeats the whole drive-less absolute path under a backup folder that already sits deep inside the project. For `VOCABULARY/general.md` in this worktree, the backup path measures 274 characters, past Windows' 260-character `MAX_PATH`. On a machine without `LongPathsEnabled`, step (b) fails and the migration refuses with `write-failed`. That is safe, because nothing is changed, but a client in a deep checkout or worktree cannot migrate, and the message points at a backup, not at path length.

Fix: back up relative to the common parent of the targets (or take an optional `base` that defaults to it). `registry_migrate` passes the project, so the backups land at `backup/.claude/registries/...`. Add a test that the backup path for a target is `backup_dir / target.relative_to(base)`.

### W3 (warning) — The entry-level I-12 check compares only keys and counts, not "the output entry with that key holds every input line". `.claude/scripts/registry_migrations/m0001_domain_split.py:739-744`

I-12 *Entries* requires every input (key, text) to map to an output entry with that key that holds every input line. `verify_plan` checks `set(out_keys) == set(in_keys)` and the count. The text check is one multiset per registry, so a planning bug that attaches a body line to the wrong entry (for example in the merge or append path of step 4) passes both checks. The tests pass because the planner is correct today. The guard the contract asked for, which would catch a future planner bug, is weaker than specified.

Fix: in `_plan_registry`, record per key the multiset of the input lines of every occurrence, minus its `merged-duplicate` removed lines. In `verify_plan`, parse each output entry and require that its line multiset contains that set. Add a forced-plan test that moves one body line between two entries and expects `content-loss-detected`.

### W4 (warning) — The default mode of `validate_registries.py` still reads only the two root files. `.claude/scripts/validate_registries.py:44-49, 215-217`

`mechanisms_file()` and `vocabulary_file()` return only `MECHANISMS.md` and `VOCABULARY.md`. On a layout-2 project, every project mechanism and term is in a domain file, and the dead-path report (`/validate-registries` with no flag) never looks at one. The contract keeps the default mode's regex and exit code, but its reader inventory lists `validate_registries` as a reader through the resolver, and the brief asks that "no reader still reads one flat file". R4 under `--check-structure` does cover the domain files, so the gap is limited to the default report. However, that report is the one `/validate-registries` shows first. The default mode exits 1 on this repository both before and after the range, because of pre-existing placeholder spans, so this is not a new red exit.

Fix: iterate `registry_files("MECHANISMS.md")` and `registry_files("VOCABULARY.md")` in `print_report`, with one block per file. Keep the regex and the exit rule. Add a test with a dead path only in `MECHANISMS/backend.md`.

### W5 (warning) — On this repository, `--check-structure` prints 9 `R3 universal-candidate` advisories, because the plugin root resolves to an older installed copy. Live run; contract "Uncertain Assumptions"

The contract assumed that `separate_plugin_root` returns none on this repository "unless a cache copy exists". A cache copy does exist (`~/.claude/plugins/cache/auto-improve`). It is the installed, older release, and it lacks the entries t8 just appended. So the plugin's own new Universal entries ("Registry layout reader", "Registry migration runner" and the seven terms) are reported as client-authored. The exit is 0 and every line is advisory. However, t8's expected output, "R4 advisory lines only", holds only with `--plugin-root` forced to a missing folder, which is what the test does. A maintainer who runs the lint on the plugin repository sees false "move it" advice for the plugin's own entries.

Fix (pick one, and record it): treat a project that holds this plugin's own manifest (`_manifest_names_plugin(project)`) as the plugin source and skip `universal-candidate`, or document the behaviour in the spec and in `skills/validate-registries/SKILL.md`. The `ASSUMED` line flipped to `FALSIFIED`. The JOURNAL entry is proposed under Disposition.

### N1 (nit) — A new t8 entry cites a path that is not repo-relative. `.claude/registries/MECHANISMS.md:112`

The "Registry migration runner" entry cites `` `registry_migrations/__init__.py` ``, which R4 reports as dead. It should be `.claude/scripts/registry_migrations/__init__.py`. Two other R4 lines are also beyond the contract's expected list: `MECHANISMS.md:77` `.claude/hooks/bash-gate.py` (pre-existing; the hook moved into the strict-shell-gate add-on) and `VOCABULARY.md:114` `MECHANISMS/backend.md` (an example path). The contract wanted lines beyond the expected list "listed in the PR", and I did not find them in the t3 or t8 records. Fix: `registry_append.py --registry mechanisms --correction-of "Registry migration runner"` with the full path. Do not edit the entry (I-7).

### N2 (nit) — `registry_migrate` builds the plan before the git checks, and a plan-build exception exits 2 without a report. `.claude/scripts/registry_migrate.py:263-285`

The contract's Order puts the plan at step (4), after git. Building it earlier writes nothing, so I-9 holds, and it lets refusals report the plan hash. However, an exception in `build_plan` returns `EXIT_BAD` straight away, with no report, even inside a git tree with uncommitted changes. Fix: catch the exception, then record it through `job.finish(EXIT_BAD, ...)` so the report folder still says what happened, or move the build after step (3).

### N3 (nit) — A rollback can leave an empty new domain folder. `.claude/scripts/_preview_apply.py:88`

Step (a) runs `target.parent.mkdir(...)`. If a later step fails, `MECHANISMS/` (for a new `general.md`) stays as an empty folder, and R5 then applies, because a domain folder exists. That folder is advisory only on a `pending` tree. Fix: remember the folders that step (a) created, and remove them if they are empty after the rollback.

## What was NOT checked

- The digest generator was not run live. It writes `.claude/.scout-cache/registry-digest.md`, outside this task's write list. Its behaviour is taken from `test_registry_layout.py` (digest tests pass) and from a code read.
- `registry_migrate.py --apply` was not re-run on this repository. The tree is already `current`, and a `--dry-run` on `current` returned an empty plan (`files: []`, exit 0). That dry-run wrote a report folder under `.claude/cache/registry-migrations/`, and I removed it, so the worktree holds only this artefact and its Gate Output.
- Real Windows long-path behaviour (W2) was measured, not reproduced: the path length was computed, and no copy was attempted with `LongPathsEnabled` off.
- The sync-tool follow-up (`tools/sync-plugin.ps1`) is out of scope by contract.
- `tools/SYNC.md` and the other repository were not read.

## Evidence

All commands were run from the worktree root, `py -3` on Windows (Git Bash).

| Command | Exit | Result |
|---|---|---|
| `py -3 .claude/scripts/tests/test_preview_apply.py` | 0 | 9 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_root.py` | 0 | 8 tests OK |
| `py -3 .claude/scripts/tests/test_registry_layout.py` | **1** | 73 tests, 1 failure: `ThisRepositoryTests.test_check_structure_exits_zero_with_only_layout_and_r4_output` (C1) |
| `py -3 .claude/scripts/tests/test_script_path_resolution.py` | 0 | 193 passed, 0 failed |
| `py -3 .claude/scripts/tests/test_registry_append.py` | 0 | 29 tests OK |
| `py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py` | 0 | 13 tests OK |
| `py -3 .claude/scripts/tests/test_registry_readers.py` | 0 | 13 tests OK |
| `py -3 .claude/scripts/tests/test_registry_migrate.py` | 0 | 33 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_doctor.py` | 0 | 209 tests OK (1 skipped) |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 0 | 18 tests OK |
| `py -3 .claude/scripts/tests/test_skill_script_lookup.py` | 0 | 26 tests OK |
| `py -3 .claude/scripts/tests/test_auto_improve_finish_install.py` | 0 | 344 tests OK (the import-back of the moved names) |
| `py -3 .claude/scripts/tests/test_check_version_bump.py` | 0 | 46 tests OK |
| `py -3 .claude/scripts/registry_migrate.py --check --project .` | 0 | `{"state": "current", "marker": "2", "reasons": []}` |
| `py -3 .claude/scripts/registry_migrate.py --dry-run --project .` | 0 | `files: []`, `layout_state.state: current` (I-11) |
| `py -3 .claude/scripts/validate_registries.py --check-structure --project .` | 0 | 9 `R3 universal-candidate` advisories (W5), 32 `R4` advisories, `digest: absent` |
| `py -3 .claude/scripts/validate_registries.py --check-structure --project . --plugin-root ./no-such-plugin` | 0 | R4 advisories plus `digest: absent` only |
| `py -3 .claude/scripts/validate_registries.py --check-structure --strict --project .` | 1 | R4 counts under `--strict`, as specified |
| `py -3 .claude/scripts/validate_registries.py` (default mode) | 1 | pre-existing placeholder spans (for example `VOCABULARY.md:15`, present at `dca00fd`); domain files not scanned (W4) |
| `py -3 .claude/scripts/plugin_doctor.py --project .` | 0 | `registry layout: current`, `body-less journal entries: 0` |
| `py -3 .claude/scripts/plugin_doctor.py --project . --json` | 0 | `registry_layout.state = current`, `bodyless_journal_entries = 0` |
| `py -3 .claude/scripts/check_version_bump.py --base fix/235-domain-split-registries --default-branch master --head-ref task/2026-11-04-domain-split-registries/t9-review` | 0 | "sub-task pull request keeps version 0.14.5; the landing raises it" |
| `py -3 .claude/scripts/check_version_bump.py` (default mode, against master) | 1 | expected before the landing raise (Parent Branch Delivery Rule) |
| `py -3 .claude/scripts/derive_area.py .claude/concepts/2026-11-04-domain-split-registries.md` | 0 | `uncategorized` (empty area map) |
| `git diff --name-only dca00fd..HEAD` filtered for `plugin.json` / `marketplace.json` | 0 | only the test fixture `tests/fixtures/registry-migration/plugin/.claude-plugin/plugin.json` |
| `git diff dca00fd..HEAD -- skills/ship/SKILL.md` | 0 | 0 lines (Q11) |
| `cmp .claude/templates/registries/<REG>/general.md .claude/registries/<REG>/general.md` (x3) | 0 | identical |

## Disposition

- **Blocked on C1.** One fix sub-task (owner: `python-ai-developer`) should update the stale pin in `test_registry_layout.py:747`, then re-run the full list above and expect every suite at exit 0. The test file is on sub-task 3's list, so the fix stays inside the contract's files.
- **W1-W4 should be fixed in the same fix sub-task, or filed as one follow-up.** Each comes with its test. W2 and W3 are guard strength, not current misbehaviour. W1 and W4 are contract alignment ("sole owner of the grammars", "no reader reads one flat file").
- **W5:** decide between the code change and the documentation. Either way, record the falsified assumption.
- **N1-N3:** optional. N1 goes through `registry_append.py --correction-of` only.
- **Registry janitor.** The two new mechanisms and the seven terms are already promoted by t8, so there is nothing to append. INTEGRATION.md does not apply: no REST, SignalR or DTO surface. This task may write only this artefact and its Gate Output, so the JOURNAL entry below is proposed, not appended. The landing or the fix sub-task appends it with `registry_append.py --registry journal --universal` (or into `JOURNAL/general.md`), batched with the landing's version raise:

  ```markdown
  ### 2026-11-06 — A plugin repository that is also installed resolves its own older copy as "the plugin"
  - **Trigger:** post-impl divergence
  - **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
  - **Lesson:** When a check compares a project against "the installed plugin", decide explicitly what happens when the project IS the plugin's source and an older installed copy exists; a stale cache copy turns the plugin's newest entries into "client-authored" findings.
  - **Apply when:** a contract resolves a separate plugin root (separate_plugin_root, find_plugin_root) to classify ownership, and the plugin's own repository is one of the projects it runs on.
  - **Tags:** plugin-root, vendoring, ownership, cache-copy, assumption-falsified
  ```

- **A second proposed lesson (C1), for the same append:** a sub-task that changes the state that an earlier sub-task's test pins must re-run that suite. Briefs that flip repository state (migration applies, registry rewrites) need a `Run:` line that names every suite pinning that state.
