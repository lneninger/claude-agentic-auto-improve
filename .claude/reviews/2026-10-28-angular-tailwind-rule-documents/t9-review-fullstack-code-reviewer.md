# Review: angular-tailwind rule documents (sub-tasks 1-8), fullstack-code-reviewer

**Gate agent:** fullstack-code-reviewer
**Sub-task reviewed:** t1-rule-documents to t8-release-notes-and-upgrade-path (gate t9-review)
**Contract:** `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md` (approved)
**Reviewed on:** 2026-10-29
**Commit range reviewed:** `8b0f6fd..ea4e5df`. `8b0f6fd` is the merge base of this branch with `origin/master` (pull request #83, the last commit before the contract). `ea4e5df` is the head of `feature/84-angular-tailwind-rule-documents`, from which this branch was cut. The working tree was clean apart from this artefact.
**Verdict:** pass-with-findings

## What was checked

- **I-1 (hooks and documents not both empty).** Met. `_read_addon_manifest` refuses it (`auto_improve_finish_install.py:1884`); `addon_problems` in `test_plugin_manifests.py` carries the same check. angular-tailwind has `hooks: []` and four documents.
- **I-2 (every hook has a row; rows name a hook; rows may be empty only when hooks are).** Met. `auto_improve_finish_install.py:1890-1896`. angular-tailwind has `registrations: []`.
- **I-3 (a name in at most one of hooks, disabled hook, former names; current files exist).** Met. `_disabled_entries_problem` (`:1926-1961`) collects all three lists and refuses a duplicate; the disabled hook, its note and every document must exist in the add-on folder. Mirrored at `test_plugin_manifests.py:900-907`.
- **I-4 (angular-tailwind: no kill switch, no per-prompt row).** Met. `addon.json` has no `kill_switches` key and no row. `test_plugin_manifests.py:954-971` checks no kill switch and no row on `UserPromptSubmit`, `UserPromptExpansion`, `Stop` or `SubagentStop`. The kill switches of `codegraph` and `strict-shell-gate` are unchanged (diff of both manifests adds only `uninstall_skill`).
- **I-5 (the install never copies a disabled hook or writes its row; a project file or row under either name is "present"; the script no longer reads `CLAUDE_ARCH_ADVISOR`).** Met, with F1. `_addon_file_ops` lists hooks, documents and helpers only (`:2119-2122`). `_disabled_hook_refusal` (`:2079-2107`) matches the current and former names, case-insensitively, as a file in `.claude/hooks/` or a row in `settings.json` or `settings.local.json`. The advisor diff removes only the switch check and its docstring lines. A probe of a fresh install planned zero rows and wrote no `settings.json`.
- **`released_sha256` covers every released copy under both names.** Met. I recomputed the folded SHA-256 of every git revision of `.claude/hooks/architecture-advisor.py` and `.claude/addons/angular-tailwind/hooks/angular-tailwind-advisor.py`. That gave six hashes. The five in `addon.json` are the two `architecture-advisor.py` copies and the three released add-on copies. The sixth (`c8b57a50...`) is the current copy without the switch, which the removal accepts as "the plugin's copy" (`:2832-2833`).
- **I-6 (profile).** Met. Install: `_plan_profile_documents` (`:2158-2207`) compares through `_profile_path_key` (no backticks, forward slashes), skips listed paths, replaces a placeholder or `none`, appends to an authored list, and leaves the bytes alone when nothing is missing. Removal: `_plan_profile_removal` (`:2731-2790`) takes out exactly the add-on's paths, keeps the other entries' text, and writes `none` when nothing is left. Tests at `test_auto_improve_finish_install.py:3712-3838` and `:4951-4995` cover a placeholder, `none`, an authored list, an already-listed path, a missing row, a missing profile, install twice and an emptied slot. My probe round trip (install, reinstall `nothing-to-do`, removal) restored the original slot text.
- **I-7 (removal writes `settings.json` with a backup before any hook file is deleted).** Met. `apply_addon_removal` (`:2994-3037`) does the settings write, then the profile, then the `_remove_file` loop. `test_the_rows_are_written_before_the_first_file_is_deleted` (`:4913`) checks this with a spy on `_remove_file`.
- **I-8 (delete only identical-after-fold or released hash; differing files kept; helpers and snippet never deleted).** Met. `_classify_file` (`:2800-2810`) uses `_fold_text_bytes`. Helpers and the snippet are only reported as `kept` (`:2904-2909`). Tests at `:4845-4895` and `:5236`.
- **I-9 (plan hash covers settings, profile, stylesheet and every copied or deleted file).** Met. Install digest at `:2396-2397`; removal digest at `:2923-2926`. Tests for a changed hook file, settings file, profile and stylesheet after the preview all refuse `changed-since-preview`.
- **I-10 (no install, nothing).** Met. `test_a_project_that_never_ran_the_install_has_no_document_no_row_and_an_unchanged_profile` (`:3732`). The plugin's `hooks.json` registers no add-on hook (the manifest suite checks it, 167 passed).
- **C1 inline style (T-001, T-008).** Met in the documents, the guard and the design foundation. Partly met in the skill (F3).
  - `TAILWINDCSS_RULES.md:89-103` has the closed list (a)-(c), both C1(b) lists, the same-line rule and the colour ban.
  - `foundation.md` "Inline Style Elimination" is reworded to C1.
  - The guard's `SVG_STYLE_ELEMENTS` and `POSITIONING_PROPERTIES` (`architecture-guard.py:419-425`) match the lists exactly. `style_is_positioning_exception` reads the open tag on the same line only. Tests cover `<svg>` with fill, `<g>` and `<text>` allowed, `<div>` blocked, a split `<rect` and canvas.
- **C2 Material overrides (M-006, T-011).** Met. `ANGULAR_MATERIAL_RULES.md:54` and `TAILWINDCSS_RULES.md:124-125` state both placements and neither says "only".
- **C3 `!important` and `!`.** Met. `TAILWINDCSS_RULES.md:172`, `ANGULAR_MATERIAL_RULES.md:36` and `foundation.md:165`.
- **C4 pixel and arbitrary values.** Met. `TAILWINDCSS_RULES.md:178`. The guard's suggestion no longer cites `w-[200px]` (no match in `architecture-guard.py`; `test_suggestion_no_longer_cites_w_200px`).
- **C5 response envelope.** Met. Only the placeholder `<the success flag of the project's response envelope>` appears (`ANGULAR_CODE_RULES.md:16,150`, the skill's Data section). `isSuccess` and `/api/screeners/symbols` are gone from `agents/angular-senior-dev.md`.
- **C6 theme polarity.** Met, with a nit (F7). `TAILWINDCSS_RULES.md:190` names the slot as the only authority and says to report a mismatch.
- **Guard rule map.** Met. `RULE_MAP_EXACT` and `RULE_MAP_PREFIX` (`architecture-guard.py:300-313`) equal the contract's map. `external:` returns its own ID and no document (`:323-324`). Every name the guard emits is covered: `inline-style`, `hex-color`, `scroll-edge`, `inline-component-template`, `inline-component-styles`, `gray-utility:<label>`, `app-banned-class:<cls>`, `height-chain-warn:...`, `scss-warn:raw-property`, `scss-warn:dead-host`, `external:<id>`. The footer checks for the file under the project root from `_project_paths.project_dir()` and counts an unknown root as not installed (`:333-367`). The `sticky` check reads class attributes only, with variants (`:462-471`).
- **Rule document set.** Met. I fetched issue #84: its catalogue has 65 IDs (M-008, M-010 and T-024 do not exist). Every ID appears exactly once as a `### <ID>` heading. A-025 is in `UI-UX-PATTERNS.md`, and P-001 is the only `P` ID. The precedence paragraph appears word for word once in each document and in the skill. A-002, A-004, A-006, A-011 and A-012 read "not enforced" (checked by the coverage suite).
- **The coverage test is green.** Met. `test_angular_rule_coverage.py`: 17 tests OK, including the positive controls (a deleted rule, a deleted fragment, a duplicate, a changed paragraph, a planted token).
- **The trial evidence.** Partly met (F6). Pull request #105 pastes the output of a bash run: `agentic-auto-improve:angular-senior-dev` quoted `Rule set: angular-ui-rules` without tools. There was no PowerShell run, and the plugin was loaded with `--plugin-dir .`, not from an installed cache.
- **The upgrade note under both file names.** Met, with F1. `README.md:272-289` has a table by install age naming `angular-tailwind-advisor.py` (0.9.9 to 0.9.21, exec form) and `architecture-advisor.py` (older installs, string and exec form). The order is uninstall, install, new session, and it warns against deleting the file first. `test_every_old_row_form_under_both_names_is_removed_and_the_file_deleted` (`:4723`) covers the row forms. `DISABLED.md` covers what the hook did, its cost on every prompt, why it is off, the dead `ui` keyword and how to turn it back on.
- **The version lines.** Met, with F2 and F4. All five entries read `0.10.0`. `check_version_bump.py --base origin/master` exits 0 ("version raised to 0.10.0"). README line 241 explains why the release is 0.10.0 and not the planned 0.9.22.
- **Uninstall skills, Q8.** Met. All three manifests carry `uninstall_skill`, all three skills exist, and `test_skill_script_lookup.py` was run (see Evidence).
- **Stylesheet snippet (Q7, Q12).** Met. The snippet has the three selectors, the markers, `--scroll-edge-header-bg` with the `var(--mat-sys-surface)` default, and no `overflow-hidden`. The `--stylesheet` tests cover all-present, none-present, partial, missing, a twice-run and the removal leaving it.
- **Off-area drift.** No finding. `.claude/area-mapping.json` has `"areas": {}`, so no area can be derived. Outside the union of `Files to touch` the range changes only workflow files (briefs, the state store, completion records, `JOURNAL.md` critic appends) and `.claude/work-item-conventions.json` (F10).
- **End-User View.** Not applicable, as the contract states: no Angular UI surface of an application is touched.

## Findings

- **F1 (warning): the upgrade path loops when the old advisor row sits only in `settings.local.json`.** Locations: `.claude/scripts/auto_improve_finish_install.py:2096-2107` (the install refusal reads the `project` and `local` layers), `:2866` and `:2879` (the removal edits only `.claude/settings.json`), and `:2848-2855` (a local row only marks a file as `kept-referenced` when the file is in the project).
  - My probe put the row in `settings.local.json`, once on `${CLAUDE_PLUGIN_ROOT}/.claude/hooks/architecture-advisor.py` and once on `${CLAUDE_PROJECT_DIR}/...`, with no file present. Each time the install refused `disabled-hook-present` and said "Run /auto-improve-angular-tailwind-uninstall first". The removal then planned no row and returned `nothing-to-do`, and the install refused again.
  - The refusal does name `.claude/settings.local.json`, so a reader can fix it by hand. But the instruction it gives cannot succeed, and `README.md:282` says the uninstall "finds the row in every form above".
  - Fix (either): the removal also takes owned rows out of `settings.local.json` (with its own backup, still before any file); or, for a row only in `settings.local.json`, the refusal and the uninstall plan tell the user to delete that row by hand. Add a test either way.
- **F2 (warning): the skill count is stale in five places.** `README.md:436` ("28 skills") and the four manifest descriptions (`plugin.json:5`, `.claude-plugin/plugin.json:6`, `.cursor-plugin/plugin.json:4`, `.claude-plugin/marketplace.json:14`) say 28. `skills/` holds 32, and `README.md:128` and the README skill list already say 32. The t8 constraint was "Update the skill list and counts", and pull request #105 flagged the drift.
- **F3 (warning): the skill's T-001 line is narrower than C1.** Location: `skills/angular-ui-rules/SKILL.md`, Styling section, "**T-001** No static `style` for layout, spacing or sizing; use Tailwind utilities."
  - C1 is binding wording for t7. It says a template has no static `style` at all, apart from a closed list, and that a static `style` never carries a colour. The skill's line reads as if a static colour style were outside T-001.
  - Pull request #105 says this line was not compared with the documents.
  - Suggested line: "**T-001** No static `style="…"` in a component template. The only exceptions are run-time bindings and a positioning-only style on an SVG element or `canvas` (T-008)."
  - Lesser: the T-011 line gives only the one-component half of C2.
- **F4 (warning): the contract still says 0.9.22.** Location: the contract's Q10 and the t1 and t8 TASK blocks. The shipped version is 0.10.0 (bumped in t1, t3, t5 and t7). The README states the reason, so the divergence is justified, but the contract body was not amended. Separately, pull requests #102 (t4) and #104 (t6) changed shipped files without raising the version. The workflow checks only pull requests into `master`, so this is not enforced, but it is against the project rule.
- **F5 (warning): the registry promotions the contract names are not done.** None of these is in `MECHANISMS.md` or `VOCABULARY.md`:
  - "Disabled add-on hook" (New Mechanisms, "Promote to MECHANISMS.md: yes");
  - the one sentence for the Preview-hash apply entry about `addon-remove` and its order rule (Reused Mechanisms);
  - the five new Universal terms (Add-on, Add-on manifest, Disabled add-on hook, Add-on document, Rule ID);
  - the Placeholder slot amendment.

  I did not write them. The registries are shipped files, and this gate's `Files to touch` names only this artefact. Proposed text is under Disposition.
- **F6 (warning): the delivery trial is half of what the contract asked for.** Location: pull request #105, "Live trial". The contract asked for a PowerShell and a Bash run. Only bash ran, with `--plugin-dir .`. The ASSUMED entry is about a plugin install (the marketplace cache). The bare name resolved, so the preload works in that form. Whether it works for an installed copy, and in PowerShell, is not shown.
- **F7 (nit): two "Enforced by" and rule lines read against the settled text.**
  - `TAILWINDCSS_RULES.md:27` keeps the old hook's "ZERO static style="..." attributes allowed" next to the closed exceptions. It is kept on purpose for the coverage fragments, but it reads as a contradiction until T-008.
  - `TAILWINDCSS_RULES.md:192` says T-021 (polarity) is "Enforced by: guard blocks the banned classes of an app through T-022". The guard never checks polarity. "Not enforced; T-022 blocks an app's banned classes" would be accurate (JOURNAL 2026-10-04, "Check a documented guard behaviour against the guard's code").
- **F8 (nit): angular-tailwind still installs a helper nothing uses.** `addon.json:3-5` lists `.claude/hooks/_project_paths.py`. With `hooks: []`, a fresh install copies it into the project's `.claude/hooks/`, where it is never deleted (helpers are kept, I-8). My probe left it behind after install and removal. Dropping the helper from this manifest would stop that.
- **F9 (nit): `JOURNAL.md` had its line endings rewritten.** Commit `370e642` shows 274+/239- for this file. With `--ignore-cr-at-eol` it is 36+/1-: five critic entries were appended, and every existing line was re-ended. It is a seed the doctor copies, so the noise ships and line blame is lost.
- **F10 (nit): one file outside every `Files to touch` list.** `.claude/work-item-conventions.json` (commit `d1e9dab`, in t3's pull request) maps `README.md` to a DOCS tag. It is workflow configuration and harmless. It is listed here so the contract record is complete.

## What was NOT checked

- **A PowerShell or installed-cache trial of the preload.** I did not run `claude -p`. This review cannot start a nested Claude session, and the contract gave the trial to t7.
- **A consuming project's Tailwind 4 build of the snippet** (the ASSUMED `@apply sticky top-0 z-10`). No Angular project is available.
- **The coverage rows against companion 2 line by line.** The suite holds the map as data and is green. I checked the catalogue IDs against issue #84, but I did not diff each coverage row against the comment.
- **Cursor and Codex installs**, and the doctor's drift output with `hooks: []` (a declared follow-up).
- **The `~/.claude/logs/reviewer-verdicts.jsonl` audit line.** It is outside this worktree, and the caller limited writes to the worktree.
- **CodeGraph.** No CodeGraph tool was bound in this session. I read source sections directly, by line range.

## Evidence

Commands, run from the worktree root unless shown otherwise:

| Command | Exit | Result |
|---|---|---|
| `git merge-base HEAD origin/master` | 0 | `8b0f6fd` |
| `git rev-parse HEAD` | 0 | `ea4e5df8e4751b3bafd23a71cb7de618fcccf4b1` |
| `git diff --stat 8b0f6fd..HEAD` | 0 | 57 files, 6552+ / 444- |
| `git diff --ignore-cr-at-eol --stat 8b0f6fd..HEAD -- .claude/registries/JOURNAL.md` | 0 | 36+ / 1- (F9) |
| `git log --all --name-status -- .claude/hooks/architecture-advisor.py ...` | 0 | added `2091f42`, deleted in `304ca12` (0.7.0); add-on copy since `5876b17` (0.9.9) |
| `py -3 -I %TEMP%/t9rv/hashes.py <worktree>` (folded SHA-256 of every revision under both names) | 0 | 6 hashes: the 5 in `released_sha256` and the current copy |
| `gh issue view 84 --comments` | 0 | 65 catalogue IDs; the same set as the document headings |
| `gh pr view 105 --json body,comments` | 0 | bash trial output only (F6) |
| `py -3 .claude/hooks/tests/test_angular_rule_coverage.py` | 0 | 17 tests OK |
| `py -3 .claude/hooks/tests/test_architecture_guard_messages.py` | 0 | 24 tests OK |
| `py -3 .claude/hooks/tests/test_architecture_guard_scss.py` | 0 | 32 tests OK |
| `py -3 .claude/hooks/tests/test_hook_data_files_project_first.py` | 0 | 29 passed, 0 failed |
| `py -3 .claude/hooks/tests/test_addons.py` | 0 | 16 tests OK |
| `py -3 .claude/scripts/tests/test_angular_rule_delivery.py` | 0 | 9 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_manifests.py` | 0 | 167 passed, 0 failed |
| `py -3 .claude/scripts/tests/test_auto_improve_finish_install.py` | 0 | 304 tests OK (86 s) |
| `py -3 .claude/scripts/tests/test_check_version_bump.py` | 0 | 15 tests OK |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 0 | 8 tests OK |
| `py -3 .claude/scripts/tests/test_skill_script_lookup.py` | 0 | Ran 20 tests OK (182 s); the three uninstall skills' Step 0 blocks are scanned |
| `py -3 .claude/scripts/check_version_bump.py --base origin/master` | 0 | "version raised to 0.10.0" |
| `py -3 .claude/scripts/check_version_bump.py --base 8b0f6fd` | 0 | "version raised to 0.10.0" |
| `grep '"version"'` in the four manifests | 0 | `0.10.0` in all five entries |
| `ls skills/*/SKILL.md \| wc -l`; `grep "[0-9]* skills"` in README and manifests | 0 | 32 skills; "28 skills" at README:436 and four manifests (F2) |
| `py -3 -I %TEMP%/t9rv/freshinstall.py <worktree>` (fresh install, reinstall, removal) | 0 | 4 documents and the helper copied, 0 rows, no `settings.json`; reinstall `nothing-to-do`; removal deletes the 4 documents, the slot reverts, `_project_paths.py` stays (F8) |
| `py -3 -I %TEMP%/t9rv/localrow.py <worktree>` (advisor row only in `settings.local.json`) | 0 | install `disabled-hook-present`; removal `nothing-to-do`; install refused again (F1) |

Files read:

- The contract, in full (Data Shapes, I-1 to I-10, C1-C6, Guard rule map, Rule skill, Handoff blocks 1-9, Review checklist).
- `.claude/templates/concept-contract.md:384-406` (the artefact and Gate Output shape), and the 2026-10-22 webdesign review with its `.gate.json` as a worked example.
- `.claude/addons/angular-tailwind/addon.json`, `DISABLED.md`, `snippets/scroll-edge.scss`; the diffs of the other two manifests and of the advisor script.
- `auto_improve_finish_install.py:1858-1962, 2067-2208, 2347-2471, 2575-2640, 2731-3045`.
- `architecture-guard.py:285-475`.
- `TAILWINDCSS_RULES.md` in full; the C1-C6 grep hits in the other three documents.
- `skills/angular-ui-rules/SKILL.md`; the diffs of both agents, `foundation.md` and `README.md:225-335, 434-563`.
- The test names of the install, manifest, guard-message, add-on and coverage suites.

## Disposition

The verdict is pass-with-findings. No finding blocks merging the feature branch. Before the contract flips:

1. **F1.** Make the removal clear a disabled-hook row in `settings.local.json`, or make the refusal say to delete that row by hand. Add a test.
2. **F2.** Set the count to 32 at `README.md:436` and in the four manifest descriptions.
3. **F3.** Replace the skill's T-001 line with the C1 wording above. Optionally, complete T-011 with the multi-component half of C2.
4. **F4.** The contract owner amends Q10 and the t1 and t8 blocks to 0.10.0, with the reason the README gives.
5. **F5.** Append these to the registries, in a change that already raises the version:
   - MECHANISMS.md (Universal): `- **Disabled add-on hook** — keep a retired add-on hook shipped, documented and removable without any install writing it. \`.claude/addons/<name>/addon.json\` key \`disabled\` plus \`<addon>/DISABLED.md\`. Extend by: move the hook's name and row from \`hooks\`/\`registrations\` into \`disabled\`, with \`former_names\`, the row older installs carry and \`released_sha256\` of every released copy.`
   - MECHANISMS.md, the Preview-hash apply entry: one sentence: "`addon-remove` is the removal through the same seam: settings rows first (with a backup), then the profile, then files, and a file is deleted only when it is identical after the fold or matches a released hash."
   - VOCABULARY.md (Universal): the five terms and the Placeholder slot amendment, as worded in the contract's Business Concept.
6. **F6.** Run the trial once in PowerShell against an installed copy of the plugin, and record the output on the parent issue.
7. **F7-F10.** Optional nits.

Janitor work in this pass: none written. The registry appends (F5) are left to the caller. This gate's file list names only this artefact, and the registries are shipped files. `INTEGRATION.md` does not exist, and nothing here would need it.
