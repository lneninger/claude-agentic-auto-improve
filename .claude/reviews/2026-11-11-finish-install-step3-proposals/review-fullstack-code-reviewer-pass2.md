# Code review, pass 2: finish-install Stage 2 project files (issue #21)

- **Reviewer:** fullstack-code-reviewer
- **Date:** 2026-11-11
- **Branch:** feature/21-finish-install-step3-proposals (uncommitted, against origin/master, which reads 0.18.8)
- **Contract:** `.claude/concepts/2026-11-11-finish-install-step3-proposals.md` (approved)
- **Supersedes:** `review-fullstack-code-reviewer.md` (pass 1, verdict FIX THEN SHIP)
- **Verdict:** SHIP. One non-blocking WARN remains; the fix is a few lines.

## How this was checked

- I read the whole diff of `auto_improve_finish_install.py` (the `project-files` code, the `_render_text` branch and the `main` branch), `plugin_doctor.py`, Stage 2 of `SKILL.md`, `README.md`, the registries and the manifests. I also read the reused helpers it relies on: `_load_profile_ctx`, `_read_db_rules`, `_database_proposals`, `_disposable_patterns_for`, `_linked_folder_refusal`, `_separate_plugin_root`, `stage_and_replace`, and `land_contract.glob_regex` and `derive_area.derive_areas` for how the written patterns are matched.
- Suites: `test_auto_improve_finish_install` and `test_plugin_doctor` together ran 825 tests, OK (1 skipped), in 346 s. The finish-install suite collects 601 cases, which matches the README's new count. `test_plugin_manifests`: 262 passed. `test_skill_script_lookup`: 35 tests OK. `test_check_hook_registrations`: 73 tests OK. `check_version_bump.py` reports "no shipped plugin file changed" because it compares commits, so run it again after the commit. All five declarations read 0.19.0. Master moved after the branch point only through docs commits (#366, #368) and still reads 0.18.8, so no second raise is needed.
- Ten probes in `C:\Temp\rev21c\probe1.py` subclass `StepThreeBase` and drive `fi.main()`. Their results are quoted below.
- No CodeGraph tool was bound in this session. Symbols were traced with Grep and Read.

## Pass-1 findings: re-checked

| Pass-1 finding | Now |
|---|---|
| CRITICAL: the skill applied with the hash of a flag-less preview | **Fixed.** 2d previews again with the confirmed flags, and 2a says the first hash is not the one to apply. |
| WARN: the text renderer crashed on `nothing-to-do` | **Fixed.** Probe B: `status: nothing-to-do` with one `file … basis` line per file. The plan text now prints `plan-sha256` and the diffs. |
| WARN: absolute roots were accepted | **Fixed.** `_normalise_root` drops a leading `/` (UNC included) and a drive letter. Test at line 9024. |
| WARN: a whitespace-padded `--token` was written | **Fixed for `--token`** (refused as `invalid-text`, never stripped). The same class is still open for found strings (WARN below). |
| WARN: a symlinked target was previewed as writable | **Fixed.** `_step3_inspect` marks a link `unrecognised`. `.claude/cache/finish-install` joined the folder check. Tests at lines 9076-9124. |
| WARN: `in-plugin-text` gave no file name | **Fixed in JSON** (`(found in <file>)`). The text renderer drops it (INFO below). Including the tests folders is the accepted decision. |
| WARN: five contract points were untested | **Fixed.** Escaped key (9183), re-read mismatch (9155), text renderer (8991-9014), per-target link and folder links (9076-9124). |
| INFO: case-variant duplicate roots | **Fixed within one slot.** Across slots the pattern can still repeat (INFO below). |
| INFO: database exclusions used protect-databases wording | **Partly fixed.** `system-database` uses the token wording, but `disposable-database` still says "it can never be protected" (INFO below). |
| INFO: `EVIDENCE_REASONS` lacked `profile-slot` | **Fixed** (test file, line 154). |

## The six priorities

1. **Stage 2 and the plan fields agree end to end; one confirmation.** They hold. The first preview has no flags and already carries `narrows-if-tokens: true` and the `narrowing-statement` while the token file is empty and not skipped (probe B), so the narrowing question is asked in the same reply as the tokens and skips. 2d previews again with exactly those flags. `--confirm-narrowing` is outside the hash, so the apply uses the 2d hash unchanged. A **no** to narrowing means `--skip-file tokens` or no `--token`. Probe C: with `--skip-file tokens`, `narrows` and `narrows-if-tokens` are false, the apply without `--confirm-narrowing` is `applied`, and the token file is byte-identical. Without confirmation, the narrowing apply is refused `narrowing-unconfirmed` (exit 2) and writes nothing. With it, all three files are written. Every field Stage 2 names (`files`, `modules`, `token-proposals`, `exclusions`, `source-notes`, `not-inferred`, `narrows`, `narrows-if-tokens`, `narrowing-statement`, `profile-note`, `plugin-text-check`, `backup-dir`, `gitignore-hint`, `plan-sha256`; apply: `status`, `written`, `backup-dir`, `rollback`) exists in the script's output.
2. **No wrong token can be written.** Holds. Only `--token` values are written. Each one passes `_token_refusal`, which refuses: empty; leading or trailing whitespace; over 128 characters; Cc, Cf, Cs, Zl or Zp characters; a non-space Zs character; `system-database` (checked before length, in any letter case); `too-short`; `generic-word`; and `in-plugin-text`. The refusal runs at preview and again at apply. The one gap is in what is proposed, not in what is written (WARN below).
3. **An authored file is never overwritten.** Holds. Only an unauthored file has planned bytes. The hash binds old and planned bytes, and the apply re-reads every target before `stage_and_replace`.
4. **All or none.** Holds. There is a single `stage_and_replace(writes, backup_dir, base=project)` call. Probe F turned `.claude/cache/finish-install` into a plain file: the apply was refused `write-failed` at the backup step, and the snapshot of the tree was unchanged.
5. **Preview and apply agree on links and unsafe roots.** Holds. Probe G replaced `.claude` with a directory junction. The preview marked all three files `unrecognised`, naming the link, and the apply refused `write-failed`. Roots are normalised in the shared `_plan_project_files`, so the preview and the apply cannot differ.
6. **Text mode renders every status.** Holds. Probe B shows the plan, `REFUSED narrowing-unconfirmed`, `applied` (with written files, backups, gitignore hint and rollback line) and `nothing-to-do`.

## Findings

### `.claude/scripts/auto_improve_finish_install.py`

**[WARN]: A found string with leading or trailing whitespace is offered as a token proposal, but the same text as `--token` is refused** (`_TokenRules.reason`, called from `_step3_token_candidates`)

```
def reason(self, text, proposal, disposable=None):
    if not text or len(text) > TOKEN_MAX_LENGTH or _unsafe_character(text):
        return "invalid-text"
    ...
# the whitespace rule lives only in _token_refusal:
elif token != token.strip():
    reason, message = "invalid-text", "it begins or ends with whitespace; ..."
```

**Problem.** Probe A tracked `angular.json` with the project key `"zorbexshell "`. The plan listed `zorbexshell ` under `token-proposals`. Passing it back with `--token "zorbexshell "`, as Stage 2c tells the operator to do, was refused `token-invalid (invalid-text)`, exit 2. Contract decision 3 applies the exclusion rules "to candidates and to every `--token`". Pass 1 fixed the `--token` side, but only that one instance. The effect is a second question in a flow promised to have one, because Stage 2d then asks for another token. Nothing wrong is written. The same applies to a `package.json` name, a `.csproj` prefix with a leading space, or a guard-file `protected_databases` entry with surrounding whitespace.

**Fix.** Put the strip test inside `reason`, so both callers share it. Also add a test that plants a padded `angular.json` key and asserts an `invalid-text` exclusion.

```
if not text or text != text.strip() or len(text) > TOKEN_MAX_LENGTH or _unsafe_character(text):
    return "invalid-text"
```

(`_token_refusal` can keep its own clearer message for the whitespace case.)

---

**[INFO]: The text renderer prints an exclusion's reason but not its message** (`_render_text`, the `excluded` line). In text mode the `(found in <plugin file>)` detail of `in-plugin-text`, the reason pass 1 asked for, is lost. Add `item["message"]` to the line.

**[INFO]: A `disposable-database` exclusion still carries protect-databases wording** (`_step3_token_candidates`, the `excluded` loop). The message reads "it can never be protected, because it is meant to be dropped". Use `TOKEN_EXCLUSION_MESSAGES["disposable-database"]` for that reason too.

**[INFO]: The same root in two slots gives two areas with one pattern.** Probe E used `backend.roots = src/` and `frontend.roots = Src/`, which gave `backend` and `frontend`, both `src/...`. `derive_areas` collects every matching area, so nothing breaks. It is noted only because the within-slot dedupe now exists.

**[INFO]: The preview can say `inferred` when the apply will fail at the backup step.** Probe F shows this when `.claude/cache/finish-install` is a plain file. It fails closed and the tree is unchanged, so nothing needs to change.

**[INFO]: Module evidence does not name the slot.** Stage 2b asks for "the profile slot that named its root", but the evidence is `{path: .claude/project-profile.md, reason: profile-slot}` with no slot. The assistant must map it from `kind`. Adding the slot name to the evidence, or wording 2b as "the kind", would close this.

### `skills/auto-improve-finish-install/SKILL.md`

No defects. One wording nit: the `token-invalid` bullet in 2d lists "empty, too long, a control character, …". It omits leading or trailing whitespace and format characters, which the script also refuses.

### `.claude/scripts/plugin_doctor.py`, `README.md`, registries, manifests

No defects. The token scaffold carries the shipped file's keys, and a parity test pins them. `NEEDS YOU` covers the four `authored=True` scaffolds, and the skill proposes all four. The README covers every line in Extension Points. The 601-case count is correct.

## Contract audit

- **Data Shapes: partly met. Every divergence is justified.**
  - `narrows-if-tokens` is an extra plan field. Without it, the narrowing question cannot be asked before the tokens are chosen. It is recorded in `JOURNAL.md` ("A consent question whose trigger depends on the operator's own answer…"), but the contract's ProjectFilesPlan row was not amended.
  - Absolute roots are rejected. This is a contract gap, journaled.
  - `planned-bytes` is a byte count.
  - `nothing-to-do` is an apply status the contract does not name.
  - `PLUGIN_TEXT_FOLDERS` scans both the root and the `.claude/` folders. That is stricter, and it is the accepted decision.
- **Reused Mechanisms: met.** `_disposable_patterns_for` was extracted and `protect-databases` calls it. Nothing was copied.
- **New Mechanisms:** none, as declared.
- **Files to touch:** the 10 listed files, plus the registry appends (allowed by Implementation Handoff section 2) and agent-memory notes (not shipped code).
- **Off-area drift:** not scorable. `.claude/area-mapping.json` has `areas: {}`, so every path derives to the fallback, as the contract's Adjacent Areas section states.
- **End-User View:** present and compliant. The shipped behaviour matches it, including "Running it again changes nothing" (probe B, `nothing-to-do`).

## Registry janitor

Nothing new to append. Pass 1 and the implementer already added:

- the `MECHANISMS.md` Correction under Preview-hash apply;
- the two `VOCABULARY.md` terms;
- the two `JOURNAL.md` post-impl-divergence entries.

The WARN above is a residual instance of the pass-1 whitespace finding. It is not a new lesson.

## Summary

| Severity | Count |
|---|---|
| [CRITICAL] | 0 |
| [WARN] | 1 |
| [INFO] | 5 |

**Verdict:** SHIP. The WARN is recommended before merge, but it does not block: no wrong token can be written.

**Top priority fix:** apply the whitespace rule inside `_TokenRules.reason`, so a padded found string is excluded rather than proposed and then refused.
