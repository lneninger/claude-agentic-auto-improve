# t11 review — fullstack-code-reviewer

- **Gate agent:** fullstack-code-reviewer
- **Sub-task:** t11-review (issue #293, parent issue #235)
- **Contract:** `.claude/concepts/2026-11-04-domain-split-registries.md` (approved, amendment 4)
- **Supersedes:** .claude/reviews/2026-11-04-domain-split-registries/t9-review-fullstack-code-reviewer.md
- **Reviewed on:** 2026-11-07
- **Commit range reviewed:** `dca00fd..ae1c3e4` (parent branch `fix/235-domain-split-registries`, from the commit that added the approved contract and the nine briefs to the merge of pull request #294, t10). The deep read covers `70c8e6b..ae1c3e4` (everything after t8); the t9 "Met" items were re-checked over the whole range.
- **Sub-task merges in the range (first parent):** t1 `c844c53` (#250), t2 `603a816` (#252), t3 `d21919b` (#254), t4 `e041320` (#256), t5 `094a01b` (#258), t6 `d70f793` (#273), t7 `9be2508` (#278), t8 `70c8e6b` (#280), t9 review `fd45bea` (#285), C1 fix `c8b46ca` (#288), amendment 4 `cdb4751` (#290), t10 `ae1c3e4` (#294). One direct first-parent commit: `e1e2bc6` (briefs for sub-tasks 10 and 11).

**Verdict:** pass-with-findings

## What was checked

Each item is on one line. The outcome comes first, then the evidence.

- **C1 fixed.** Met. `test_registry_layout.py` exits 0 (77 tests). `ThisRepositoryTests` (`test_registry_layout.py:801-816`) asserts that no line starts with `advisory: registry layout` and that every line is R4, `digest:` or the R3 skip line. `registry_migrate.py --check --project .` exits 0 with `current`. The pin itself does not call `--check` (see N1 below). A missing layout advisory line already means the state is `current`, so that is equivalent.
- **W1, one grammar.** Met. `_ENTRY_HEADER`, `_TRIGGER_LINE` and `_SOURCE_LINE` are gone from `accuracy_update.py`. A repository-wide grep for a dated-heading regex in `.py` files finds only `_registry_layout.py:61-70,282` and the test constant `OLD_ENTRY_HEADER` (`test_journal_post_approval_tracker.py:38`). `parse_journal_entries` keeps only entries of kind `entry` from `rl.parse_text`, so legacy entries and fenced headings are excluded.
- **W1, fence test.** Met. `test_a_dated_heading_inside_a_fence_added_to_a_seeded_file_fires_zero_times` covers a fence under a section and a fence at the top level. Both give zero fires.
- **W1, 41 signatures unchanged, frozen fixture.** Met. `test_signatures_of_the_frozen_journal_copy_are_unchanged` reads only `FIXTURE`. The fixture's blob `4782e06` is byte-identical to `JOURNAL.md` at `70c8e6b`, which is before the Q20 appends. Old and new signature sets are equal, with 41 each. The live `JOURNAL.md` is never read.
- **W1, client parity row.** Met. `test_client_journal_seeded_by_the_old_reader_is_reseeded_once_without_firing` builds a CRLF journal with a fenced heading, a tab after the date, no space after the separator, and a heading that the old `\s+` reads across a line break. It asserts that the two readers differ, then seeds the file with `seeded_files: {key: true}`. The first run gives zero fires and leaves `{"reader": 2}`. One appended heading then gives exactly one fire.
- **W1, lazy import and the fail-soft hooks.** Met as specified, with a defect in the degraded path (W1 below). `_registry_layout` is imported inside `parse_journal_entries` only, and the module-level imports (`accuracy_update.py:40-65`) are unchanged. `test_without_the_layout_module_the_hooks_still_import_and_parsing_yields_nothing` sets `sys.modules['_registry_layout'] = None` in a subprocess, then asserts that `_DEPS_OK is True` for both `critic-verdict-tracker.py` and `contract-status-watcher.py`, that `record_clean` runs, and that exactly one stderr line names the module.
- **W2.** Met. `stage_and_replace(writes, backup_dir, base=None)` backs up to `backup_dir / relpath(target, base)`. `base` defaults to the common parent, and a target outside `base` returns `write-failed` before step (a) (`_preview_apply.py:117-123`). `registry_migrate.py:326` passes `base=project`. Tests: `test_backup_path_is_backup_dir_joined_with_the_path_relative_to_base`, `test_base_defaults_to_the_common_parent_folder_of_the_targets`, `test_a_deep_checkout_stays_under_max_path_with_the_relative_layout` (asserts on the computed length), `test_a_target_outside_base_is_write_failed_before_any_stage_file`, and `test_w2_backups_land_under_the_path_relative_to_the_project`.
- **W3.** Met. `_plan_registry` records `key_lines` per key: the lines of a single copy, or the sum over every copy minus that group's `merged-duplicate` lines. `verify_plan` requires each output entry's line multiset to contain that set. `_nonblank` applies the I-12 normalisation (`rstrip` folds `\r` and trailing spaces, blank lines are dropped, and the BOM is removed at load). Two output entries with one key give `ConflictingEntryProblem` (code `conflicting-entry`), naming each location and first line. A heading that differs between copies is refused in `_merge_group` (`field: "heading"`). The key-set and count checks stay. Tests: misattached line (`test_w3_a_forced_plan_that_moves_a_body_line_between_entries_is_content_loss`), CRLF+BOM+trailing space, headings that differ only in the date, two output entries with one key, and the existing merge fixture (`test_the_lesson_only_copy_is_appended_under_the_kept_entry`), which still passes.
- **W4.** Met. The default mode iterates `registry_files` through `_claude_paths` (`validate_registries.py:56-62,367-376`), prints one block per file (live output: `MECHANISMS.md`, `MECHANISMS/general.md`, `VOCABULARY.md`, `VOCABULARY/general.md`), and stops at the leftovers heading outside a fence. `--json` keeps `mechanisms`/`vocabulary` (aggregated, `file` = the root file) and adds `files`. The regex, flags and exit rule are unchanged. `test_validate_registries_default.py` covers a domain-only dead path (exit 1), flat-layout parity of the blocks and JSON, a clean layout-2 project (exit 0), and leftovers with a fence and a dead path above them.
- **W5 per Q19 (a).** Met. `validate_registries.py:335-352` drops only R3 `universal-candidate` when `_manifest_names_plugin(project_root)` is true, and prints the fixed ASCII line only when the count is above 0. Live: `advisory: R3 universal-candidate skipped: 11 entries; this project holds the plugin's own manifest`. That is the 9 from t9 plus the 2 Q20 lessons, which the older installed copy lacks. The four Q19 tests are in `PluginOwnManifestSkipTests`, including one where a token-bearing entry stays a `finding` (exit 1). `ThisRepositoryTests` allows the prefix and still asserts that there is no layout advisory line. The spec R3 row is updated.
- **N1.** Met. `MECHANISMS.md:113` reads `  - **Correction (2026-11-06, t9 review N1):** The migration package is `.claude/scripts/registry_migrations/__init__.py`; ...`. That is the exact shape `registry_append.py:360` emits for `--correction-of` with `--source "t9 review N1"`, and the entry line itself is unchanged in the diff. R4 still prints `advisory: R4 .claude/registries/MECHANISMS.md:112 registry_migrations/__init__.py`, as I-7 requires.
- **N2.** Met. A `build_plan` exception now goes through `job.finish(EXIT_BAD, ("plan-build-failed", ...))` with `files`/`conflicts`/`registries` empty, `plan_hash: "none"` and `error` set. `Run.finish` sets `mode: refused` and writes both report files. `test_n2_a_plan_build_exception_writes_a_refused_report_and_exits_2` asserts exit 2, byte-identical files, and every report field.
- **N3.** Met. `_missing_folders` records what step (a) creates, and `_remove_created_folders` removes them, deepest first and only when empty, after a staging, backup or replace failure. Tests: `test_a_folder_made_by_a_failed_run_is_removed_and_an_existing_one_stays`, `test_a_folder_made_before_a_staging_failure_is_removed`, `test_n3_a_folder_made_by_a_failed_run_is_gone_and_an_existing_one_stays`.
- **Both Q20 lessons.** Met. `JOURNAL.md:333-345` holds "A plugin repository that is also installed resolves its own older copy as "the plugin"" (worded for answer (a)) and "A sub-task that flips the state an earlier sub-task's test pins must re-run that suite". Both are Universal, both have Trigger `post-impl divergence`, and both have this contract as their source.
- **Every t9 "Met" item still holds.** Met. Markers: line 1 of all three roots is `<!-- registry-layout: 2 -->`, and `--check` gives `current`. Skeletons: `cmp` shows identity for all three. `skills/ship/SKILL.md`: 0-line diff over the range. `test_plugin_text_scans.py`, `test_registry_append.py`, `test_registry_readers.py`, `test_registry_migrate.py`, `test_plugin_doctor.py`, `test_auto_improve_finish_install.py` and `test_skill_script_lookup.py` all exit 0. Doctor: `registry layout: current`, `body-less journal entries: 0`. `--check-structure` exits 0, and exits 1 under `--strict` (R4). The t9 "Partly met" items (readers, Data Shapes I-8 and I-12, no flat reader) are now met through W1, W3 and W4.
- **No version file changed in the range beyond the test fixture.** Met. `git diff --name-only dca00fd..ae1c3e4` filtered for `plugin.json` / `marketplace.json` returns only `.claude/scripts/tests/fixtures/registry-migration/plugin/.claude-plugin/plugin.json`. PR #288 (head `fix/235-…`, not checked in parent mode) changed only `test_registry_layout.py`. `check_version_bump.py` in parent mode exits 0.
- **Off-area drift.** Nothing to compare. `derive_area.py` returns `uncategorized`, because the area map is empty. Every file changed in `70c8e6b..ae1c3e4` is on block 10's Files to touch, or is a contract, review or brief bookkeeping file.

## Findings

### W1 (warning) — When `_registry_layout` cannot be imported, the tracker still marks the journal file as seeded by reader 2, so a later run fires every old entry. `.claude/scripts/accuracy_update.py:576-586`

```python
entries = parse_journal_entries(text)          # [] when _registry_layout cannot be imported
was_seeded = _seeded_by_current_reader(seeded.get(key))
...
seeded[key] = {"reader": JOURNAL_READER}       # written even though nothing was read
```

The contract ("Import chain", amendment 4) says that on `ImportError` the function "returns no entries (nothing fires, **nothing is seeded**)". I-14 says "Nothing fires retroactively or twice". Here the empty list is indistinguishable from an empty journal. The file is saved as `{"reader": 2}` with no signatures. Once `_registry_layout` is present, the next edit of that file treats every existing entry as new, and each `post-*` entry calls `record_failure`. A file seeded under the old reader (`true`) is also overwritten to `{"reader": 2}` without the re-seed. That reopens the old-versus-new pattern gap that the reader re-seed exists to close.

Reproduced with an isolated probe, outside the worktree, with a temporary cache. Run 1, with `sys.modules['_registry_layout'] = None`, left the cache at `"sigs": {}, "seeded_files": {"…/journal.md": {"reader": 2}}`. Run 2, with the module restored and one unrelated line appended, fired the historical `2026-01-01` `post-impl divergence` entry and called `record_failure` once. Exposure: the copied-script client that the contract names (it copies the new `accuracy_update.py` before `_registry_layout.py`). The damage is lowered accuracy, so the change is conservative: the client runs more critic passes and skips none. But it corrupts machine-wide state against a stated invariant. Test (d) checks only the parse result, not the cache.

Fix: tell "reader unavailable" apart from "no entries", and leave the cache untouched in that case.

```python
def _journal_reader_available() -> bool:
    try:
        import _registry_layout  # noqa: F401
        return True
    except ImportError:
        return False

# in process_journal_change, before _load_seen():
if not _journal_reader_available():
    return []          # parse_journal_entries already wrote the one stderr line; nothing seeded, nothing fires
```

Extend test (d): in the same subprocess, call `process_journal_change` with a temporary home, and assert that the cache file is unchanged (or absent). Then restore the module, edit the file, and assert that nothing fires (first sight, so the file is seeded).

### N1 (nit) — The C1 pin does not run `registry_migrate.py --check` on this repository. `.claude/scripts/tests/test_registry_layout.py:801-816`

The t9 fix suggested asserting `--check` exit 0 in the same test. PR #288 asserts only that no layout advisory line appears, which is equivalent, because the lint prints that line whenever the state is not `current`. The live `--check` exits 0. No action is required. Adding the call would make the pin's intent explicit. The test name still says "only_layout_and_r4_output".

### N2 (nit) — The README procedure still says that exit 2 is "a bad argument". `README.md:1312-1316`

`plan-build-failed` now also exits 2, and it writes a report with `error`. The README refusal paragraph, and the "Registry migration runner" entry (`MECHANISMS.md:112`, refusals exit 3), do not mention it. Neither file is on block 10's list, so this is a doc follow-up, not drift. Fix: one sentence in the README: "Exit 2 is a bad argument or `plan-build-failed` (the report names the error)". For the registry, add a `--correction-of` line if it is wanted.

## What was NOT checked

- I did not run the digest generator live. It writes `.claude/.scout-cache/registry-digest.md`, which is outside this task's write list. Its behaviour comes from the passing `test_registry_layout.py` digest tests.
- I did not re-run `registry_migrate.py --apply` on this repository, because the tree is `current`. Two `--dry-run` runs returned `files: []` and wrote report folders under `.claude/cache/registry-migrations/`. I removed those, so the worktree holds only this artefact and its Gate Output.
- I did not reproduce Windows long-path behaviour with `LongPathsEnabled` off. W2 is checked by the computed-length test.
- I did not verify the older-test search results and the printed file:line evidence, which t10's brief says live in PR #294's description. I did not open the PR.
- `tools/sync-plugin.ps1` and `tools/SYNC.md` (the sync-tool follow-up) are out of scope by contract.

## Evidence

All commands were run from the worktree root, `py -3` on Windows (Git Bash), with `PYTHONIOENCODING=utf-8`.

| Command | Exit | Result |
|---|---|---|
| `py -3 .claude/scripts/tests/test_preview_apply.py` | 0 | 15 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_root.py` | 0 | 8 tests OK |
| `py -3 .claude/scripts/tests/test_registry_layout.py` | 0 | 77 tests OK (C1 fixed; W5 tests) |
| `py -3 .claude/scripts/tests/test_script_path_resolution.py` | 0 | 193 passed, 0 failed |
| `py -3 .claude/scripts/tests/test_registry_append.py` | 0 | 29 tests OK |
| `py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py` | 0 | 17 tests OK (4 new `GrammarTests`) |
| `py -3 .claude/scripts/tests/test_registry_readers.py` | 0 | 13 tests OK |
| `py -3 .claude/scripts/tests/test_registry_migrate.py` | 0 | 40 tests OK (7 new `FixTheT9ReviewTests`) |
| `py -3 .claude/scripts/tests/test_plugin_doctor.py` | 0 | 209 tests OK (1 skipped) |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 0 | 18 tests OK |
| `py -3 .claude/scripts/tests/test_skill_script_lookup.py` | 0 | 26 tests OK |
| `py -3 .claude/scripts/tests/test_auto_improve_finish_install.py` | 0 | 344 tests OK |
| `py -3 .claude/scripts/tests/test_check_version_bump.py` | 0 | 46 tests OK |
| `py -3 .claude/scripts/tests/test_validate_registries_default.py` | 0 | 7 tests OK (W4) |
| `py -3 .claude/scripts/registry_migrate.py --check --project .` | 0 | `{"state": "current", "marker": "2", "reasons": []}` |
| `py -3 .claude/scripts/registry_migrate.py --dry-run --project .` (x2) | 0 | `mode: dry-run`, `files: []`, `layout_state.state: current`, `error: ""` (I-11) |
| `py -3 .claude/scripts/validate_registries.py --check-structure --project .` | 0 | 32 `R4` advisories (incl. `MECHANISMS.md:112 registry_migrations/__init__.py`), one `advisory: R3 universal-candidate skipped: 11 entries; …`, `digest: absent`; no layout advisory |
| `py -3 .claude/scripts/validate_registries.py --check-structure --project . --plugin-root ./no-such-plugin` | 0 | R4 advisories plus `digest: absent` only |
| `py -3 .claude/scripts/validate_registries.py --check-structure --strict --project .` | 1 | R4 counts under `--strict`, as specified |
| `py -3 .claude/scripts/validate_registries.py` (default mode) | 1 | four blocks: `MECHANISMS.md` 19 dead, `MECHANISMS/general.md` 0/0, `VOCABULARY.md` 5 dead, `VOCABULARY/general.md` 0/0; exit 1 is pre-existing (t9) |
| `py -3 .claude/scripts/validate_registries.py --json` | 1 | `mechanisms`, `vocabulary` (aggregated) and `files` (4 blocks) |
| `py -3 .claude/scripts/plugin_doctor.py --project .` | 0 | `registry layout: current`, `body-less journal entries: 0` |
| `py -3 .claude/scripts/plugin_doctor.py --project . --json` | 0 | `registry_layout.state = current`, `bodyless_journal_entries = 0` |
| `py -3 .claude/scripts/check_version_bump.py --base fix/235-domain-split-registries --default-branch master --head-ref task/2026-11-04-domain-split-registries/t11-review` | 0 | "sub-task pull request keeps version 0.14.5; the landing raises it" |
| `py -3 .claude/scripts/derive_area.py .claude/concepts/2026-11-04-domain-split-registries.md` | 0 | `uncategorized` (empty area map) |
| `git diff --name-only dca00fd..ae1c3e4` filtered for `plugin.json` / `marketplace.json` | 0 | only `.claude/scripts/tests/fixtures/registry-migration/plugin/.claude-plugin/plugin.json` |
| `git diff --stat dca00fd..ae1c3e4 -- skills/ship/SKILL.md` | 0 | empty (Q11) |
| `git rev-parse 70c8e6b:.claude/registries/JOURNAL.md ae1c3e4:.claude/hooks/tests/fixtures/journal-signatures-2026-11-06.md` | 0 | both `4782e062b99d…`: the fixture is a byte copy taken before the Q20 appends |
| `cmp .claude/templates/registries/<REG>/general.md .claude/registries/<REG>/general.md` (x3) | 0 | identical |
| `head -1` of the three root registries | 0 | `<!-- registry-layout: 2 -->` on each |
| `grep` for `\d{4}-\d{2}-\d{2}` and `###` regexes in `.claude/**/*.py` | 0 | production hits only in `_registry_layout.py`; test constant `OLD_ENTRY_HEADER` |
| W1 probe (`probe_seed.py`, temp folder outside the worktree, patched cache path; deleted afterwards) | 0 | degraded run left `seeded_files: {…: {"reader": 2}}` with `sigs: {}`; next run fired the historical entry and called `record_failure` once |

## Disposition

- **Pass with findings.** C1 and every t9 warning and nit are fixed, each with its tests. All 14 suites and every live command behave as the contract says. Nothing blocks the landing.
- **W1 (this report)** should be fixed before or with the landing, because it is a stated-invariant violation (I-14, "nothing is seeded") in a path the contract designed for. The fix is about five lines in `accuracy_update.py` plus an extension of test (d) in `test_journal_post_approval_tracker.py`. Both files are already on block 10's list, so a follow-up sub-task (owner: `python-ai-developer`) stays inside the contract's files. If it is deferred, file it as a follow-up of issue #235.
- **N1, N2:** optional. N2 changes the README and (through `--correction-of` only) a registry entry, so batch it with the landing's version raise.
- **Registry janitor.** No new mechanism or term in `70c8e6b..ae1c3e4`. The `PlanProblem`/`ConflictingEntryProblem` refusal carrier and the `JOURNAL_READER` re-seed marker are internal to the two existing mechanisms. INTEGRATION.md does not apply: there is no REST, SignalR or DTO surface. Both Q20 lessons are already appended. This task may write only this artefact and its Gate Output, so the lesson below is proposed, not appended. If it is wanted, the landing appends it with `registry_append.py --registry journal --universal`, batched with the version raise:

  ```markdown
  ### 2026-11-07 — A fail-soft reader must not record "seen" for what it could not read
  - **Trigger:** post-impl divergence
  - **Source contract:** .claude/concepts/2026-11-04-domain-split-registries.md
  - **Lesson:** When a reader degrades to "no entries" because a dependency is missing, the caller must tell that apart from an empty file and skip every state write (seen sets, seeded markers, reader versions); otherwise the first healthy run treats all history as new.
  - **Apply when:** a tracker or cache keys "already processed" on the output of a parser that has an ImportError or fail-soft path returning an empty result.
  - **Tags:** fail-soft, seen-cache, retroactive-fire, lazy-import, degraded-path
  ```
