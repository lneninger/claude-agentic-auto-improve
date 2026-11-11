# Code review: finish-install Stage 2 project-file token proposals (issue #21)

- **Reviewer:** fullstack-code-reviewer
- **Date:** 2026-11-11
- **Branch:** feature/21-finish-install-step3-proposals (uncommitted, against origin/master at 0.18.8)
- **Contract:** `.claude/concepts/2026-11-11-finish-install-step3-proposals.md` (approved)
- **Verdict:** FIX THEN SHIP

## How this was checked

- I read the whole diff of `auto_improve_finish_install.py`, `plugin_doctor.py`, `SKILL.md`, `README.md` and the four manifests. I also read the reused helpers: `_load_profile_ctx`, `_open_box`, `_member_named`, `_block_json`, `_linked_folder_refusal`, `_read_db_rules`, `_database_proposals` and `_preview_apply.stage_and_replace` / `_plan_digest`.
- Suites: `test_auto_improve_finish_install` + `test_plugin_doctor`: 780 tests, OK (1 skipped), 274 s. `test_skill_script_lookup` + `test_plugin_manifests`: 262 passed. `check_version_bump.py` says "no shipped plugin file changed". It compares commits, so rerun it after the commit.
- 8 probes in `C:\Temp\rev21\probe_step3.py`. They subclass `StepThreeBase` and drive `main()`. The results are quoted under each finding.
- No new module-level import: the only import change is `stage_and_replace` added to the existing `_preview_apply` line. `copy`, `difflib`, `posixpath` and `unicodedata` were already imported.
- CodeGraph tools were not bound in this session. Symbols were traced with Grep and Read.

## What holds (checked against the priorities)

- **An authored file is never overwritten.** `_step3_authored` checks `areas == {}`, both `prTitle` lists empty, and `tokens == []`. Any other content gives `kept-authored` with no planned bytes. A file that is not strict JSON, has a BOM or a duplicate key, or has the wrong member type is `unrecognised` and is never written.
- **All or none.** Every write goes through one `stage_and_replace` call with `base=project`. The injected replace-failure test restores all three files.
- **`--confirm-narrowing` gate.** `narrows` is true exactly when the token file is `inferred`, which means it currently holds `[]`. The apply refuses `narrowing-unconfirmed` before any write, and a positive control writes once the flag is given.
- **Splice correctness.** Only the value spans returned by `_member_named` are replaced. The result is re-parsed strictly and compared with a deep copy where only the target members changed. CRLF is detected and used. BOM files are refused, never spliced. A key written with an escape raises `_SpliceRefused`, which becomes `unrecognised`.
- **Preview hash.** `_plan_digest` is length-prefixed. It covers each file's old bytes (or `absent`), its planned bytes, the sorted tokens and the sorted skip list. Everything the apply writes is the planned bytes, so every input that changes a write changes the hash. Token order changes the planned bytes, so it is covered too.
- **System names, generic words, plugin text.** `SYSTEM_DATABASES` and `GENERIC_WORDS` exactly equal the contract lists (a test pins this). The system-database filter runs whatever state the plugin-text check is in, and it covers both `_database_proposals` output and the guard's `protected_databases`.
- **Reuse.** `_disposable_patterns_for` is extracted and `protect-databases` calls it. Nothing listed under Reused Mechanisms was copied.

## Findings

### `skills/auto-improve-finish-install/SKILL.md`

**[CRITICAL]: Following Stage 2 as written, the apply always fails with `changed-since-preview` whenever any `--token` or `--skip-file` is chosen, and the recovery loops** (Stage 2, sections 2a and 2d)

```
### 2a. Preview
$PY "$FI" project-files --project . --json
...
### 2d. Write
$PY "$FI" project-files --project . [--token <text>]... [--skip-file <file>]... --apply \
    --expect-sha256 <plan-sha256 from the preview> [--confirm-narrowing]
Pass the SAME `--token` and `--skip-file` flags as at preview time, because the hash covers them.
- `changed-since-preview`: ... Go back to 2a, preview again, show the new table, and ask again.
```

**Problem.** The 2a preview passes no flags. The operator then picks tokens in 2c, and the token list is part of the hash (decision 5). So the `plan-sha256` from 2a can never match an apply that has tokens or skips: the token file's planned bytes and the sorted-token part both differ. The documented recovery ("go back to 2a … ask again") runs the flag-less preview again, so it never converges, and it asks the operator a second time, which breaks the one-confirmation rule. Nothing is ever written in this case (the refusal fails closed). But the main path of the stage, writing the first tokens, is unreachable through the skill. The sibling skill already solves this: `skills/auto-improve-database-guard-install/SKILL.md:102` says "Run the preview again with every confirmed name, **passing the names at preview time too**".

**Fix.** Add a step between 2c and 2d:

```
### 2c'. Preview the confirmed answer
$PY "$FI" project-files --project . --json [--token <text>]... [--skip-file <file>]...
Use this plan-sha256 for the apply. If any file's basis or diff differs from the table the user
confirmed (other than the token file now showing the named tokens), show the new table and ask again.
```

In 2d, also change "the plan-sha256 from the preview" to "from the preview in 2c'".

---

### `.claude/scripts/auto_improve_finish_install.py`

**[WARN]: The text renderer crashes on the `nothing-to-do` apply result** (`_render_text`, the `else` branch around line 5005; result built in `apply_project_files`)

```
return {"status": "nothing-to-do", "files": [{"file": e["file"], "basis": e["basis"]} for e in plan["files"]]}
...
else:
    for item in result.get("files", []):
        out.append("  file %-60s %s" % (item["path"], item["action"]))
```

**Problem.** Probe P1 ran a second apply without `--json` and got `CRASH KeyError: 'path'`. A person who reruns the command by hand gets a traceback instead of "nothing to do", even though the contract says "Running it again changes nothing". The text renderer for this subcommand is untested. Probe P1b also shows that the text preview prints neither the per-file `unified-diff` nor the `plan-sha256`, so a text-mode preview cannot be applied or reviewed.

**Fix.** Give `nothing-to-do` its own branch, for example `elif result.get("status") == "nothing-to-do": out += ["  step-3 file %-14s %s" % (i["file"], i["basis"]) for i in result["files"]]`. Print each file's `unified-diff` and the `plan-sha256` in the preview branch. Add text-mode tests for the plan, the applied result and the `nothing-to-do` result.

---

**[WARN]: Absolute profile roots are accepted, so the areas and globs can never match, and the frontend lookups read outside the project** (`_normalise_root`)

```
text = re.sub(r"/+", "/", raw.strip().replace("\\", "/"))
...
if text in ("", ".") or "*" in text or ".." in text:
    return None
```

**Problem.** Probe P2 used `backend.roots = /srv/Api/` and `frontend.roots = C:/Outside/Web`. They produced modules with patterns `/srv/api/...` and `c:/outside/web/...` and globs `/srv/Api/**` and `C:/Outside/Web/**`. `derive_area` and `module_tag_reading` compare repository-relative paths, so these areas are dead on arrival and are written into an authored file permanently. For a drive-letter root, `project / Path("C:", "Outside", ...)` drops the project prefix, so `_step3_token_candidates` reads `angular.json` and `package.json` outside the repository. The contract's rejection list (empty, `.`, `..`, `*`) does not name absolute forms, so this is a contract gap (journal entry appended).

**Fix.** Reject a root that starts with `/`, matches `^[A-Za-z]:`, or starts with `//` after normalisation, and name it in the dropped-roots note. Add a test row for each form.

---

**[WARN]: A `--token` with leading or trailing whitespace is accepted and written as-is** (`_token_refusal` / `_TokenRules.reason`)

**Problem.** Probe P3 passed `--token " Zorbex "`. It was accepted, and the token file was written as `"tokens": [" Zorbex "]`. The sync and `memory_boundary` match case-insensitive substrings, so the space-padded token misses `Zorbex.Api`, `(Zorbex)` and any occurrence at the start or end of a line. The protection is silently narrower than the operator believes. This is the silent direction that departure 2 of the contract warns about. Space (`Zs`) is not in `_ENTRY_UNSAFE_CATEGORIES`, and the only whitespace test is `not token.strip()`.

**Fix.** Refuse `token != token.strip()` as `invalid-text`. Do not strip silently, because the operator has to see exactly what is written. Add a test.

---

**[WARN]: The preview promises a write that the apply always refuses (symlinked target), and the link checks are untested** (`_step3_inspect`; `apply_project_files`, the link loop)

**Problem.** Probe P4 made `.claude/.project-tokens.json` a symbolic link to a file outside the project. The preview reported `basis: inferred` with a diff, and the apply then refused `write-failed`. `_step3_inspect` uses `path.is_file()`, which follows the link, so the plan the operator confirms cannot be executed. Three other points are also unverified: no test covers the per-target link refusal or the `.claude` / `.claude/cache` `_linked_folder_refusal`, and `.claude/cache/finish-install` itself is never checked. A junction there would make `stage_and_replace` copy the backups outside the project.

**Fix.** In `_step3_inspect`, mark an `os.path.islink` target as `unrecognised` ("a symbolic link; edit the file it points to by hand"), so preview and apply agree. Add `.claude/cache/finish-install` to the folders passed to `_linked_folder_refusal`. Add tests for a linked target, a linked `.claude` and a linked `.claude/cache`, skipping when the platform denies the right to create links.

---

**[WARN]: `in-plugin-text` scans the plugin's test fixtures, so a real consumer's own name can never be written, and the refusal does not say where the name occurs** (`PLUGIN_TEXT_FOLDERS`, `_plugin_text_corpus`, `TOKEN_EXCLUSION_MESSAGES["in-plugin-text"]`)

**Problem.** The corpus includes `.claude/scripts` and `.claude/hooks`, together with their `tests/` subfolders. In this plugin, `git grep -il scalpingmachine` finds about 10 files under `.claude/hooks/tests/` and `.claude/scripts/tests/`. So in that consumer the project's primary token is excluded as a proposal, and `--token ScalpingMachine` is refused as `token-invalid`. The message reads only "the text occurs in the plugin's own shipped files". The operator gets no file name and no remedy: the plugin is already contaminated, and the fix is in the plugin or in an `allowed` entry. The contract accepts "stricter, never weaker". But scanning both the root folders and the `.claude/` folders, tests included, was the implementer's own reading, and whether the sync ships those test folders is unverified (contract ASSUMED).

**Question for the user:** should `tests/` subfolders be left out of the corpus? Either way, the exclusion and refusal message should name the first plugin file that matched and say "the plugin already carries this name; clean the plugin or add an `allowed` entry".

---

**[WARN]: Contract points the implementer listed as untested are still untested** (test file, the `StepThree*` classes)

**Problem.** Five points have no test:

- the splice-failure path: an escaped key such as `"\u0074okens": []` should give `unrecognised`, and no test covers it;
- the re-read before write: a mismatch injected between the plan and the re-read;
- the text renderer (see the crash above);
- the per-target link check;
- the `.claude/cache` link check.

Each of these is a defined contract behaviour, and an untested branch here is where the crash above was hiding.

**Fix.** Add one test per item. Use `mock.patch.object(Path, "read_bytes", …)` scoped to the second call for the re-read.

---

**[INFO]: Case-variant duplicate roots become two areas with the same pattern** (`_step3_modules`). Probe P5 used `src/Api, SRC/api` and got `backend-api` and `backend-api-2`, both with the pattern `src/api/...`. Deduplicate on the lowercase form.

**[INFO]: Exclusion rule order.** The implementation applies the rules in this order: `invalid-text`, `system-database`, `too-short`, `generic-word`, `template-name`, `disposable-database`, `in-plugin-text`. The contract states no order, so this is a choice, not a divergence. One effect: `sys` reports `system-database`, not `too-short`. That is acceptable.

**[INFO]: The token table borrows protect-databases wording.** A database exclusion from `_database_proposals` carries the message "it can never be protected, because it is meant to be dropped". That reads oddly in the token table. Use `TOKEN_EXCLUSION_MESSAGES[reason]` instead.

**[INFO]: `planned-bytes` is a length, not the bytes.** The contract says "planned bytes". Carrying the length in the JSON is sensible, but the contract wording should be read that way.

**[INFO]: A stale test constant.** `EVIDENCE_REASONS` in the test file (line 154) does not include `profile-slot`. It is only used for profile proposals, so nothing fails, but the closed set the contract extends is not pinned.

### `.claude/scripts/plugin_doctor.py`, `README.md`, manifests

No defects. The token scaffold has the shipped file's keys, and a parity test checks this. `project` is `""` and `tokens` is `[]`. The `NEEDS YOU` line now covers the four `authored=True` scaffolds, all of which the skill proposes. The README edits cover every line listed in Extension Points, and the case count of 557 matches `def test_` in the file. All four manifests read 0.19.0, and master is at 0.18.8.

## Contract audit

- **Data Shapes:** partly met. The shapes match. The divergences are: the `nothing-to-do` apply status, which is not named in the contract but is pinned by the tests; `planned-bytes` as a length; and the absolute-root gap, which is a contract defect.
- **Reused Mechanisms:** met.
- **New Mechanisms:** none, as declared. A Correction under **Preview-hash apply** was appended.
- **Files to touch:** the diff touches exactly the 10 listed files.
- **Off-area drift:** cannot score. `.claude/area-mapping.json` has `areas: {}`, so every file derives to the fallback. The contract's Adjacent Areas section says the same.
- **End-User View:** present, with the Category line and the six sub-sections, and no code identifiers in the prose. The implementation matches its promises, except "Running it again changes nothing", which crashes in text mode (see the renderer WARN).

## Registry janitor

- `MECHANISMS.md:75`: Correction under **Preview-hash apply** for `project-files`.
- `VOCABULARY.md:161, 163`: **Unauthored project file** and **Token proposal** (Universal tier).
- `JOURNAL.md:557`: *2026-11-11 — A path-normalisation rule that lists the unsafe forms must also reject absolute paths* (post-impl divergence).

All four were appended with `registry_append.py`, under the 0.19.0 raise that is already in this change.

## Summary

| Severity | Count |
|---|---|
| [CRITICAL] | 1 |
| [WARN] | 6 |
| [INFO] | 5 |

**Verdict:** FIX THEN SHIP

**Top priority fix:** SKILL Stage 2 must run the preview again with the confirmed `--token` and `--skip-file` flags before the apply. Otherwise the stage can never write tokens.
