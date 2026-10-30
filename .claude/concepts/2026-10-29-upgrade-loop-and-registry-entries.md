# Concept Contract — Fix the add-on upgrade loop and write the missing registry entries

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-29
**Requested by:** user
**Work Item Brief:** .claude/work-items/2026-10-29-86-upgrade-loop-and-registry-entries.md
**Tracking issue:** #86
**Status:** approved
**Supersedes:** none
**Budget:** 12,000 tokens

> Partial work item: it references #86 and never closes it (#86 also lists unrelated deferred items). Sources: the t9 review `.claude/reviews/2026-10-28-angular-tailwind-rule-documents/t9-review-fullstack-code-reviewer.md` (F1, F5, optional F2 and F3) and the implemented contract `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md`, whose vocabulary this contract reuses unchanged.

---

## Business Concept

- **What is this thing, in domain language?**
  Two repairs to what plugin 0.10.0 shipped. **F1:** when the retired advisor's row sits only in `.claude/settings.local.json`, the `angular-tailwind` install refuses with `disabled-hook-present` and tells the user to run the uninstall. The uninstall edits only `.claude/settings.json`, so it reports `nothing-to-do`, and the install refuses again. The upgrade loops. The fix makes the **add-on removal** also take a **Disabled add-on hook**'s rows out of `settings.local.json`. It backs that file up first, through the same preview-and-hash seam it already uses for `settings.json`. **F5:** the registry entries the implemented contract promised (one mechanism, one mechanism sentence, five terms and one amendment) are written. The plugin version rises from 0.10.0 to 0.10.1.

- **Existing VOCABULARY.md terms that apply:** Registration key (rows are matched by hook file name), Placeholder slot (amended here), Install mode, Vendored-asset drift (the fold used to compare files), Project profile. The five terms below come from the implemented contract and are used in its meaning.

- **New terms for VOCABULARY.md (Universal tier). Copied verbatim from the implemented contract's Business Concept; nothing new is coined:**
  - **Add-on**, **Add-on manifest**, **Disabled add-on hook**, **Add-on document**, **Rule ID**, and the **Placeholder slot amendment**. Exact text and placement are under Data Shapes → Registry entries.

---

## End-User View

Not applicable. Reason: no Angular UI surface (component, template, stylesheet, state service, route or layout) is in any `Files to touch` list. The change is to an install script, its tests, two registries, two skills' text, the README and the plugin manifests.

---

## Data Shapes

### What the code does today (VERIFIED, read in this worktree)

| Step | Layers read or edited | Where |
|---|---|---|
| Install refusal `_disabled_hook_refusal` | Reads `project` **and** `local` rows (from `_existing_registrations`). It matches a row by hook file name only, so the folder is ignored and both `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PROJECT_DIR}` forms match. It also reads the files in `.claude/hooks/`. | `auto_improve_finish_install.py:2079-2107` (row check `:2096-2100`); test `test_a_disabled_hook_file_or_row_in_the_project_is_refused_under_either_name`, `test_auto_improve_finish_install.py:3848` |
| Removal plan `_plan_addon_removal` | Reads and splices **only** `project/.claude/settings.json` (`target`, `:2866`). `_rows_to_remove` / `_splice_rows_out` run on that file alone (`:2879-2897`). | `:2858-2929` |
| Referenced check `_referenced_hook_names` | Reads `local` and `user` rows, but only to keep a hook file in the project as `kept-referenced`. It never removes a row. A `${CLAUDE_PLUGIN_ROOT}` row is not "in the project", so it does not even mark a file. | `:2848-2855` |
| Removal apply `apply_addon_removal` | Order: `settings.json` (backup, then atomic write), then the profile, then the file deletions. `nothing-to-do` when there are no rows, no profile change and no deletions. | `:2955-3044` |

So a row only in `settings.local.json` is seen by the refusal and invisible to the removal. That is the loop.

### Settings layer edit (value object, extended)

The removal plan gains a second, optional settings edit beside the existing one. Fields (domain types):

| Field | Type | Meaning |
|---|---|---|
| `local-target` | path | `<project>/.claude/settings.local.json` (always reported) |
| `local-rows` | list of row (same shape as `rows`: event, matcher, file, registration-key, command) | the rows in that file that name a **disabled hook** (its current name or a former name, case-insensitive), in any form |
| `local-unified-diff` | text | the diff of that file, empty when no row |
| `local-source-sha256` | sha256 or `absent` | the file's bytes as read |

The apply result gains `local-removed-rows` (list of registration keys), `local-backup` (path or none) and `local-rollback` (text or none). `gitignore-hint` names `.claude/settings.local.json.bak-*` too when a local backup is taken. `new-session-note` is set when either layer lost a row.

**Scope of `local-rows` (Q1 answered: option (a)):** only rows naming a disabled hook. Those are exactly the rows the refusal reads as `local`. A `settings.local.json` row naming an active add-on hook (for example `bash-gate.py`) is still left alone, and its file is still `kept-referenced`, as today.

### Invariants (new or changed; I-7 to I-9 of the implemented contract stay)

- **L-1 (rows in the project and local layers).** After a successful apply, neither `settings.json` nor `settings.local.json` holds a row naming the add-on's disabled hook under any name. So no row in those two layers makes the next install refuse `disabled-hook-present`. L-1 covers rows only. The refusal also counts a disabled-hook **file** in `.claude/hooks/`, and the removal still keeps that file in two cases. One is an edited file (`kept-differs`, I-8). The other is a file a user-layer row names inside the project (`kept-referenced`). In either case the install still refuses after the removal. Both cases are documented under Failure Modes, with what the user must do. This contract adds no behaviour for them and does not change the refusal message.
- **L-2 (other rows untouched).** Only the matched rows' bytes go, through the existing `_splice_rows_out`, plus a group, event or `hooks` key the removal leaves empty. Every other byte of either file is unchanged. A file with no matched row is not read for writing, not backed up and not rewritten.
- **L-3 (backup before any change).** When a layer has rows to remove, its own timestamped backup (`settings.local.json.bak-<UTC>` via `_backup_write`, never overwritten) is written **before any write of any kind**: both backups first (`settings.json`, then `settings.local.json`), then `settings.json`, then `settings.local.json`, then the profile, then the files. If the second backup fails, the first backup is deleted and the refusal is `write-failed` with nothing written. If the `settings.local.json` write fails after `settings.json` was written, its backup is deleted. The refusal is `write-failed`. It says how many `settings.json` rows were removed, names the `settings.json` backup path with its rollback (`copy <backup> over settings.json`), and says `settings.local.json` is unchanged. The existing profile-failure refusal (`:3029`) is left unchanged: it reports a row count only, and fixing that is not in scope.
- **L-4 (nothing to do).** With no owned row in `settings.json`, no disabled-hook row in `settings.local.json`, no profile change and no deletion, the apply returns `nothing-to-do` and writes nothing: no file and no backup.
- **L-5 (idempotent).** A second preview and apply after a successful removal returns `nothing-to-do` and leaves the tree byte-identical.
- **L-6 (hash covers the local layer).** `plan-sha256` adds the local file's old bytes (or `absent`) and new bytes (or `absent`) as two more length-prefixed parts. The apply re-reads the file and refuses `changed-since-preview` if it moved. A symbolic-link `settings.local.json` with rows to remove is refused `write-failed`, as `settings.json` is.
- **L-7 (referenced set).** `_referenced_hook_names` no longer counts a `local` row that names a disabled hook, because the same apply removes that row before any file is deleted. `user` rows and `local` rows naming an active hook still count, as today.
- **L-8 (refusal messages name the file).** A splice failure in the local file is `unexpected-settings-shape` naming `settings.local.json`. A malformed local file is already refused by `_load_layers`, which prefixes the real file name (`:880-882`). `_parse_settings` hard-codes "settings.json" in its messages (`:1290-1297`). So the new local parse in `_plan_addon_removal` must come **after** the `_referenced_hook_names` call (`:2876`): `_load_layers` then refuses a malformed local file first, with the right name.

### Registry entries (F5)

Both registries are CRLF throughout in this worktree (Grep for `\r$`: MECHANISMS.md 70 of 70 lines, VOCABULARY.md 65 of 65), and both end with CRLF. New and changed lines use CRLF. No other line is touched (review F9).

| Registry | Section | Placement | Text |
|---|---|---|---|
| MECHANISMS.md | Universal Patterns | new line directly after line 70 (Sibling skill reference file), the last entry | `- **Disabled add-on hook** *(2026-10-29)* — keep a retired add-on hook shipped, documented and removable without any install writing it. `.claude/addons/<name>/addon.json` key `disabled` plus `<addon>/DISABLED.md`. Extend by: move the hook's name and row from `hooks`/`registrations` into `disabled`, with `former_names`, the row older installs carry and `released_sha256` of every released copy. Contract: `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md`.` |
| MECHANISMS.md | Universal Patterns, line 58 (Preview-hash apply) | one sentence inserted immediately before ` Extend by:` in that line | `` `addon-remove` is the removal through the same seam: settings rows first (in `settings.json` and, for a disabled add-on hook, `settings.local.json`, each with its own backup taken before any write), then the profile, then files, and a file is deleted only when it is identical after the fold or matches a released hash. `` (the review's Disposition wording, plus the local-layer clause this fix makes true; Q2 answered: accepted) |
| VOCABULARY.md | Universal Vocabulary | five new lines directly after line 65 (External skill reference), in this order: Add-on, Add-on manifest, Disabled add-on hook, Add-on document, Rule ID | each `- **<Term>** *(2026-10-29)* — <definition verbatim from the implemented contract's Business Concept, lines 23-27> Introduced by `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md`.` |
| VOCABULARY.md | Universal Vocabulary, line 41 (Placeholder slot) | text appended to the end of that line (Q4 answered: accepted) | `One exception: in `review.documents`, an add-on install may append its own Add-on document paths and the add-on removal may remove exactly those paths. No other entry and no other slot is changed by either. Amended *(2026-10-29)* by `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md`.` |

**CRLF proof (the check that tests the claim).** After the edit, a `\r$` line count gives MECHANISMS.md **71 of 71** lines and VOCABULARY.md **70 of 70**. A new line ending in LF lowers the first number. Scope check: `git diff --numstat` gives MECHANISMS.md `2 1` and VOCABULARY.md `6 1`. That shows no other line was rewritten, but it cannot prove CRLF.

### Version (patch, 0.10.0 → 0.10.1), all five places

`plugin.json:4`, `.claude-plugin/plugin.json:5`, `.cursor-plugin/plugin.json:3`, `.claude-plugin/marketplace.json:8` (top level) and `.claude-plugin/marketplace.json:15` (plugin entry).

### F2 and F3 (Q3 answered: include both)

- **F2.** "28 skills" becomes 32, the number of `skills/*/SKILL.md` files, at `README.md:436`, `plugin.json:5`, `.claude-plugin/plugin.json:6`, `.cursor-plugin/plugin.json:4` and `.claude-plugin/marketplace.json:14`. A new manifest check, `INV-15`, in `test_plugin_manifests.py` covers all five places. It finds `(\d+) skills` in each of the four descriptions and in the README table row (`| <n> skills |`), and asserts each equals the number of `skills/*/SKILL.md` files. It also runs against a copy holding a wrong count, as a positive control. Four of the five lines are in files this change already edits for the version, and the check stops the drift coming back. The agent and hook counts in the same descriptions are not checked (Non-Goals).
- **F3.** `skills/angular-ui-rules/SKILL.md:35` becomes: `- **T-001** No static `style="…"` in a component template. The only exceptions are run-time bindings and a positioning-only style on an SVG element or `canvas` (T-008).` It is one line and worth including. T-011 is left as it is (the review's "lesser" note).

### Events / Commands

Not applicable. Reason: no domain events. The only command is the existing `addon-remove` subcommand (preview, then `--apply --expect-sha256`), whose plan and result shapes are extended above. Its refusal codes stay the closed set it has.

---

## Reused Mechanisms

- **Preview-hash apply** (MECHANISMS.md:58) — **extended by** a second settings target in the `addon-remove` plan: two more digest parts, a second backup through `_backup_write`, and a second `_atomic_write`. The refusal codes stay the same closed set. No new seam.
- **Registration key** matching via `_owned_row` / `_rows_to_remove` / `_splice_rows_out` — consumed as-is, with the disabled-name subset of `_owned_hook_names` as the name set for the local file.
- **Disabled add-on hook** (being promoted by this contract from the implemented one) — consumed as-is. `disabled[].hook` and `former_names` give the local name set.
- **Section-scoped registry sync** (MECHANISMS.md:48) — the entries go in the Universal tier so they reach the plugin.

## New Mechanisms (if any)

None. F1 extends Preview-hash apply (JOURNAL 2026-10-28, "Do not promote a mechanism the registry already describes as an extension seam"). The MECHANISMS.md "Disabled add-on hook" line promotes a mechanism the implemented contract already approved ("Promote to MECHANISMS.md: yes"); this contract adds no new one.

## Extension Points

- `_plan_addon_removal`: read and parse `settings.local.json`, plan `local-rows` with the disabled-name set, splice, diff, add two digest parts, and return the local bytes in the payload. The local read and parse go **after** the `_referenced_hook_names` call (`:2876`), so `_load_layers` names a malformed local file correctly (L-8).
- `_referenced_hook_names`: take the disabled-name set and drop `local` rows naming one (L-7).
- `apply_addon_removal`: re-read check for both files, both backups, two writes, the profile, then the files (L-3). Widen the `nothing-to-do` test (L-4).
- `skills/auto-improve-angular-tailwind-uninstall/SKILL.md`: the description. The intro paragraph at line 20 ("The script writes `settings.json` first (with a backup)") becomes: "The script writes `settings.json` first, and `settings.local.json` too when a retired advisor row sits there, each with its own backup, then the profile, and deletes a file last." Also the "will not do" list, Step 1 (`local-rows`), Step 2 (show local rows and their backup) and Step 3 (`local-removed-rows`, `local-backup`). Step 0 is **not** touched: `test_skill_script_lookup.py` pins it (JOURNAL 2026-10-15).
- `README.md:262`: "writes `settings.json` first (with a backup)" becomes "writes `settings.json` first, and `settings.local.json` too for the retired advisor's rows, each with its own backup,". `README.md:275`: the table header "Row in `settings.json`" becomes "Row in `settings.json` or `settings.local.json`". Line 282 is unchanged; with the new header it is true.

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---|---|---|---|---|
| `auto_improve_finish_install.py addon-remove` | `skills/auto-improve-angular-tailwind-uninstall/SKILL.md` | JSON on stdout (`--json`) | RemovalPlan + apply result, extended by the `local-*` fields | script → skill |

- [x] Both sides are in Files to touch: the script (block 2) and the skill (block 2). No REST, SignalR or DTO surface; `INTEGRATION.md` does not exist in this repository.

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold.

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

## Non-Goals

- Every item on issue #86. This includes the guard weak spots, the other add-ons' kill switches, the disabled advisor keyword, the doctor and preload gaps, the candidate patterns and `.claude/rules/` delivery.
- Removing `settings.local.json` rows that name an **active** add-on hook (Q1), and any user-layer row (`~/.claude/settings.json`). The refusal does not read a row in either. But a user-layer row that names a disabled-hook file inside the project keeps that file (`kept-referenced`), and the refusal counts the file. So the install still refuses until the user removes that user-level entry. The same holds for an edited disabled-hook file (`kept-differs`). Both cases are documented under Failure Modes; this contract adds no behaviour for them.
- F4 (amending the implemented contract), F6 (the PowerShell trial), and F7 to F10. The agent and hook counts in the manifest descriptions.
- Closing #86 or #84. The codegraph and strict-shell-gate uninstall skills: they declare no disabled hook, so their behaviour does not change.

## Confidence

Confidence: High. Every assumption is verified (the layers line by line, no pinned hash or key set, 32 skills), and the fix reuses existing splice and backup functions. The weakest point is L-3's two-file failure handling, which needs its own tests (block 1).

## Alternatives Considered & Why Rejected

- **A (chosen):** the removal also takes the disabled hook's rows out of `settings.local.json`, with its own backup, through the same plan hash.
  - Why: it makes the refusal's own remedy succeed for every row the refusal reads (intake answer). `README.md:282` becomes accurate only together with the header edit at `README.md:275` (block 3), because "every form above" refers to that table.
- **B (rejected):** the refusal and the plan tell the user to delete the local row by hand.
  - Why rejected: the documented remedy would still fail, and the user would edit a settings file by hand, which the uninstall skill warns against.
- **C (rejected):** the removal takes every owned row (active hooks too) out of `settings.local.json`.
  - Why rejected: no install ever writes that file, so such a row is the user's own choice. It would change two other add-ons' uninstall behaviour and break `test_a_file_a_local_settings_row_still_names_is_kept` (`:4872`) for no loop it fixes.

## Uncertain Assumptions

- `VERIFIED via auto_improve_finish_install.py:2097`: the refusal matches `row["file"]` by name for `project` and `local` only, with no folder check. So both path forms are already covered by name matching.
- `VERIFIED via :2590-2593`: `_owned_row` matches by file name in any form, so `_splice_rows_out` works unchanged on the local file.
- `VERIFIED via :1734-1750`: `_backup_write` names the backup from `target.name`, so the local backup is `settings.local.json.bak-<stamp>`.
- `VERIFIED via .claude/hooks/tests/_addon_fixture.py:96-111`: `OLD_ROW_FORMS` holds `plugin-string` (`${CLAUDE_PLUGIN_ROOT}`) and three `${CLAUDE_PROJECT_DIR}` forms.
- `VERIFIED via test_auto_improve_finish_install.py (contract-critic check, 2026-10-29)`: no test holds a 64-hex literal or asserts the key set of a removal plan or result dict. So the two added digest parts and the new `local-*` fields break no existing test.
- `VERIFIED via skills/*/SKILL.md (contract-critic check, 2026-10-29)`: 32 files match, so the count is 32.

## Failure Modes & Mitigations

- **FM:** the local file changes between preview and apply. **Mitigation:** L-6 and Preview-hash apply's `changed-since-preview`.
- **FM:** a partial write leaves `settings.json` edited and `settings.local.json` not. **Mitigation:** L-3 takes both backups first and names what was done. A re-run plans only what is left, and the refusal no longer loops on the `project` row.
- **FM:** a hook file is deleted while a local row still names it, so every prompt exits 2. **Mitigation:** the local rows are removed before any file (L-3), and L-7 narrows the referenced set only to rows that the same apply removes.
- **FM:** the registry edit rewrites the line endings or adds an LF line (F9). **Mitigation:** the `\r$` count (71/71, 70/70) proves CRLF, and the numstat `2 1` / `6 1` proves no other line changed.
- **FM:** the project's disabled-hook file was edited, so the removal keeps it (`kept-differs`, I-8), and the install still refuses `disabled-hook-present` because of the file. **Mitigation:** the removal's `kept` list names the file and the reason. The user compares it with the plugin's copy and deletes the file by hand; its row is already gone, so deleting it cannot block a prompt. Then the install runs. No new behaviour.
- **FM:** a user-level row (`~/.claude/settings.json`) names the disabled-hook file inside the project, so the removal keeps the file (`kept-referenced`), and the install still refuses. **Mitigation:** the `kept` reason already says a user settings row still names the file. The user removes that user-level entry first, then runs the uninstall again, which deletes the file, then the install. No new behaviour; the refusal message is unchanged.

## Open Questions for User

- [x] **Q1 — Which `settings.local.json` rows does the removal take out?** Options: (a) only rows naming a disabled hook (current or former name), or (b) every row naming any hook the add-on owns. **Recommendation: (a).** It is exactly the set the refusal reads, so it ends the loop. It leaves the two other add-ons' behaviour and the existing `kept-referenced` test as they are, and no install ever wrote such a row. The contract is drafted on (a).
  - → Answer (user, 2026-10-29): option (a). Only rows naming a disabled hook (current or former name) are taken out of `settings.local.json`.
- [x] **Q2 — The Preview-hash apply sentence.** The review's Disposition wording says "settings rows first (with a backup)". After this fix that is incomplete. **Recommendation:** use the Disposition sentence with the local-layer clause shown under Registry entries. Strict verbatim wording would describe behaviour that no longer exists.
  - → Answer (user, 2026-10-29): accepted. Use the Disposition sentence plus the clause naming `settings.local.json` and its own backup.
- [x] **Q3 — Include F2 and F3?** **Recommendation: yes, both.** They are small, F2's lines sit in files the version bump already edits, and F2 gets a check so the count cannot drift again.
  - → Answer (user, 2026-10-29): include both F2 and F3.
- [x] **Q4 — Registry form.** **Recommendation:** append the Placeholder slot sentence to the existing line 41 (one changed line) rather than add a second Placeholder entry. Give each new entry the `*(2026-10-29)*` marker and the contract pointer its neighbours carry. The definitions stay verbatim.
  - → Answer (user, 2026-10-29): accepted. The sentence is appended to line 41, with the date marker and the contract pointer.

---

## Critique

**Critic:** contract-critic
**Date:** 2026-10-29
**Verdict:** warnings-only

### Findings

- **[WARN] The removal still leaves two cases where the install refuses again, and Non-Goals says they cannot happen**
  - **What is wrong:** the refusal also fires on a disabled-hook *file* in `.claude/hooks/` (`auto_improve_finish_install.py:2090-2092`). The removal keeps that file in two cases this contract does not change. (1) It differs from the plugin's copy and from every released hash, so it is `kept-differs` (`:2810`). (2) A `user`-layer row names it inside the project, so it is `kept-referenced` (`:2853-2855`, `:2822-2823`). Either way the next install refuses `disabled-hook-present` with the same "run the uninstall" remedy. L-1 is worded "because of a row", which leaves this out without saying so. Non-Goals goes further and states "The refusal reads neither, so neither loops", which is false for a user row once a project file exists.
  - **Prior artifact ignored:** `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md` I-8 (line 120, a differing file is kept) and I-5 (the refusal counts the file); `JOURNAL.md` 2026-10-22, "Describe a broken install by the rows each install age really has"
  - **Where in this contract:** `## Non-Goals`: "The refusal reads neither, so neither loops." `## Data Shapes → Invariants` L-1: "does not refuse `disabled-hook-present` because of a row". `## Failure Modes & Mitigations` has no entry for either case.
  - → Addressed by: L-1 now says it covers rows in the project and local layers and names both file cases. Non-Goals is corrected. Two Failure Modes entries say what the user must do (delete the edited file by hand; remove the user-level entry). No new behaviour, and the refusal message is unchanged.
- **[WARN] Confidence is "High" while two Uncertain Assumptions are `ASSUMED`**
  - **What is wrong:** the verdict contradicts the inventory. Both assumptions hold on the critic's check, so the risk is small: `test_auto_improve_finish_install.py` has no 64-hex literal and no assertion on the key set of a plan or result dict, and `skills/*/SKILL.md` matches 32 files. They are still labelled ASSUMED.
  - **Prior artifact ignored:** contract-critic checklist item 5 (Confidence vs Uncertain Assumptions)
  - **Where in this contract:** `## Confidence`: "Confidence: High." `## Uncertain Assumptions`: "`ASSUMED`: no existing test pins the exact `plan-sha256` value…" and "`ASSUMED`: the skill count is 32"
  - → Addressed by: both entries are relabelled VERIFIED, citing the critic's check. The Confidence line now rests on all assumptions being verified.
- **[WARN] Text that will describe the removal as editing `settings.json` only is not in any Files-to-touch list or Extension Point**
  - **What is wrong:** after F1, three passages describe the removal wrongly, and none is scheduled for an edit. `README.md:262` says "first (with a backup)". The upgrade-note table header at `README.md:275` reads "Row in `settings.json`" and leaves out the local layer. The uninstall skill's intro paragraph (`SKILL.md:20`) says "The script writes `settings.json` first (with a backup)". It sits outside the description, the "will not do" list and Steps 1-3, which are the only parts Extension Points names. `README.md` is in block 3 for the skill count alone. Alternative A also claims the fix "makes `README.md:282` … true". That line already refers to the table "above", which lists `settings.json` rows only.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22, "Describe a broken install by the rows each install age really has" (tag `readme-note`); `JOURNAL.md` 2026-10-04, "Check a documented guard behaviour against the guard's code"
  - **Where in this contract:** `## Extension Points`: "the description, the "will not do" list, Step 1 …, Step 2 … and Step 3". `## Alternatives Considered` A: "makes `README.md:282` (…) true"
  - → Addressed by: `README.md:262` and the `:275` header are added to block 3, and the skill's intro paragraph (line 20) to block 2. Extension Points names all three. Alternative A no longer claims line 282 is true on its own.
- **[NIT] Wrong test citation** — `## Data Shapes` row 1 says "test at `:2096-2100`". Those are the refusal's own code lines. The refusal test is `test_a_disabled_hook_file_or_row_in_the_project_is_refused_under_either_name` at `test_auto_improve_finish_install.py:3848`.
- **[NIT] The numstat check cannot prove "New and changed lines use CRLF"** — an LF-terminated new line still gives `2 1` / `6 1` with and without `--ignore-cr-at-eol`, because only whole-file rewrites move numstat. A `\r$` line count (71/71 and 70/70 after the edit) would test the claim. Related: `JOURNAL.md` 2026-10-17, "Judge 'identical to master' by git's view".
- **[NIT] L-8 holds only under an unstated order** — `_parse_settings` hard-codes "settings.json" in its messages (`:1290-1297`). Only `_load_layers` (`:880-882`) prefixes the real file name. A malformed local file is refused with the right name only if the new local parse in `_plan_addon_removal` comes after the `_referenced_hook_names` call (`:2876`). Neither Extension Points nor block 2 says so.
- **[NIT] INV-15 leaves out one of the five places F2 edits** — it checks the four manifest descriptions, not `README.md:436`, so the README table count can drift again.
- **[NIT] Block 4 writes a file its own Files-to-touch list does not name** — the Gate Output `t4-review-fullstack-code-reviewer.gate.json` is required by the TASK block but not listed.
- **[NIT] L-3's partial-failure refusal does not name the `settings.json` backup** — after `settings.json` is rewritten and the local write fails, the refusal reports only a row count. The user has no rollback path in hand. The existing profile-failure refusal (`:3029`) has the same gap.
- **[NIT] Adjacent Areas adds text after the sanctioned single line** — this is harmless, because `.claude/area-mapping.json` has `"areas": {}` and no area can be derived.

### Applicable journal entries

- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded by `## New Mechanisms` (none; F1 extends Preview-hash apply at MECHANISMS.md:58)
- **2026-10-28 — A new term's definition must be true against every existing member** — heeded by `## Data Shapes → Registry entries` (verbatim definitions from the implemented contract, lines 23-27, which name the two add-ons that keep their switches)
- **2026-10-28 — A rule that writes a slot the vocabulary calls frozen needs a vocabulary amendment** — heeded by the Placeholder slot amendment at VOCABULARY.md:41
- **2026-10-22 — Describe a broken install by the rows each install age really has** — heeded in part: block 1 covers every `OLD_ROW_FORMS` form in both layers. The README upgrade note and the file-only cases are not addressed (WARNs above).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — not yet applicable. It applies when Q1-Q4 and these findings are answered.
- **2026-10-17 — Judge "identical to master" by git's view, not raw bytes, on Windows** — heeded by the numstat check with and without `--ignore-cr-at-eol` (with the NIT above)
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by keeping `:4872` and `:3848` unchanged. The refusal rule itself is not changed.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by block 2 (Step 0 untouched, `test_skill_script_lookup.py` in the run list)
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by `## Data Shapes → What the code does today` (refusal and removal verified line by line). Not heeded for the README and skill intro text (WARN above).
- **2026-10-16 — An unset ownership field is not proof of ownership** — not addressed. The contract did not need to: the local name set comes from the manifest's `disabled` entries, not from a fallback.

### What the critic did not check

- `INTEGRATION.md` does not exist in this repository, so the integration-surface check (item 7) had no map to compare against. No REST, SignalR or DTO surface is involved.
- `.claude/north-stars/` holds no file, so item 13 produced no findings.
- CodeGraph tools were not available in this run. Code claims were checked by reading `auto_improve_finish_install.py` and the test file directly.
- Whether `git diff --numstat` honours `--ignore-cr-at-eol` on the installed git version was not run.

---

## Lessons referenced

- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded by New Mechanisms (none) and Reused Mechanisms (F1 extends Preview-hash apply).
- **2026-10-28 — A rule that writes a slot the vocabulary calls frozen needs a vocabulary amendment** — heeded by writing the Placeholder slot amendment the implemented contract promised.
- **2026-10-28 — A new term's definition must be true against every existing member** — heeded by copying the critic-corrected Add-on definition verbatim (it names the two add-ons that keep switches), not a shortened one.
- **2026-10-22 — Describe a broken install by the rows each install age really has** — heeded by the failing test covering all four `OLD_ROW_FORMS` under both file names in both layers.
- **2026-10-17 — Judge "identical to master" by git's view, not raw bytes, on Windows** — heeded by the registry `\r$` line count (71/71, 70/70) as the CRLF proof, with numstat as the scope check (F9).
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by the README `:262` / `:275` and skill line 20 edits, which make the documented removal match the code.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by block 2: the uninstall skill's Step 0 is untouched and `test_skill_script_lookup.py` runs.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by keeping `:4872` and the refusal test `:3848` unchanged and green.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded by this revision: the Q1 to Q4 answers and every critic finding are written into Data Shapes, Failure Modes, Non-Goals, Extension Points and the handoff blocks.
- Orthogonal to north-stars: none active (brief: `north_stars: none`; the register holds no active thought).

---

## Implementation Handoff

All four sub-tasks land on the parent branch `fix/86-upgrade-loop-and-registry-entries`. One pull request into `master` carries them, with the version raise from block 3, so `check_version_bump.py` sees shipped files and a raised version together.

### 1. Failing test (`senior-test-engineer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/tests/test_auto_improve_finish_install.py`

**Pre-written TASK block:**
```
TASK: Write the failing-first tests for the add-on upgrade loop (review F1). Do not touch the script.
CONTEXT: concept contract at .claude/concepts/2026-10-29-upgrade-loop-and-registry-entries.md (Data Shapes,
  L-1 to L-8). /tdd-first applies: these tests must FAIL on the current code, and you report which fail and why.
FILES: .claude/scripts/tests/test_auto_improve_finish_install.py
CONSTRAINTS:
  - In TestAddonRemoval add test_a_disabled_hook_row_in_either_settings_layer_is_cleared_so_the_install_runs.
    Subtests: layer in (project settings.json, local settings.local.json) x form in af.OLD_ROW_FORMS (plugin-string
    is the ${CLAUDE_PLUGIN_ROOT} form, the other three ${CLAUDE_PROJECT_DIR}) x name in (DISABLED_ADVISOR,
    DISABLED_FORMER). No hook file. One unrelated row (OTHER_ROW) in the same file, and a non-hooks key.
    Steps: install preview refuses disabled-hook-present; removal preview lists the row (rows or local-rows); apply
    is "applied" with a backup of that layer's file; the unrelated row and key survive; the other layer's file is
    byte-identical and has no backup; the install no longer refuses disabled-hook-present; a second removal is
    nothing-to-do with a byte-identical tree. Reset .claude between subtests.
  - Also add: (a) a disabled-hook file in .claude/hooks/ named only by a local row is deleted after the row goes (was
    kept-referenced); (b) both backups exist before the first _atomic_write call (spy, as at :4913); (c) a local file
    changed after the preview refuses changed-since-preview and writes nothing; (d) a local file with no disabled-
    hook row is neither backed up nor rewritten; (e) a local backup failure writes nothing and removes the first
    backup; (f) a symbolic-link settings.local.json with a row refuses write-failed (skip where links are unavailable);
    (g) a settings.local.json write failure after settings.json was written refuses write-failed, and its message
    names the settings.json backup path and its rollback; (h) a malformed settings.local.json is refused with a
    message naming settings.local.json, not settings.json (L-8).
  - Do not test the two file cases of L-1 (kept-differs, kept-referenced by a user row) as fixed: no behaviour
    changes for them.
  - Leave test_a_file_a_local_settings_row_still_names_is_kept (:4872) and the refusal test (:3848) unchanged.
  - Plan and result fields are the contract's names: local-target, local-rows, local-unified-diff,
    local-source-sha256, local-removed-rows, local-backup, local-rollback.
  - Run py -3 .claude/scripts/tests/test_auto_improve_finish_install.py. Paste which new tests fail, and that every
    old test still passes.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-29-upgrade-loop-and-registry-entries.md
  contract_status: approved
```

### 2. Local-layer removal (`python-ai-developer`)

**Depends on:** 1

**Files to touch:**
- `.claude/scripts/auto_improve_finish_install.py`
- `skills/auto-improve-angular-tailwind-uninstall/SKILL.md`

**Pre-written TASK block:**
```
TASK: Make addon-remove take a disabled add-on hook's rows out of settings.local.json, so the tests from sub-task 1
pass.
CONTEXT: concept contract at .claude/concepts/2026-10-29-upgrade-loop-and-registry-entries.md (Settings layer edit,
  L-1 to L-8, Extension Points).
FILES: as listed.
CONSTRAINTS:
  - Extend _plan_addon_removal, _referenced_hook_names and apply_addon_removal only. Reuse _parse_settings,
    _rows_to_remove, _splice_rows_out, _backup_write, _atomic_write and _plan_digest. No new module, no new refusal
    code. The local name set is the disabled hooks' names and former names, lowercased.
  - The local read and parse in _plan_addon_removal go AFTER the _referenced_hook_names call (:2876), so that
    _load_layers names a malformed local file (L-8).
  - Order (L-3): all re-read checks, then both backups, then settings.json, then settings.local.json, then the
    profile, then the files. Use the failure handling stated in L-3. The local-write-failure refusal names the
    settings.json backup path and its rollback. Leave the profile-failure refusal (:3029) as it is.
  - Plan digest: append the local old and new bytes (or b"absent") as the last two parts.
  - Update the removal section's header comment (:2563-2567) and the apply docstring to name both files.
  - KEPT_REASONS["kept-referenced"] stays true: a user row, or a local row naming an active hook.
  - Skill: update the description, the intro paragraph at line 20 (the contract's replacement sentence), the "will
    not do" list, and Steps 1-3 for the local-* fields and the second backup. Do NOT edit Step 0. README.md is
    sub-task 3's; do not edit it here.
  - Run: test_auto_improve_finish_install.py (all green, including sub-task 1's), test_skill_script_lookup.py,
    test_addons.py, test_plugin_manifests.py. Paste the exit codes.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-29-upgrade-loop-and-registry-entries.md
  contract_status: approved
```

### 3. Registries and version (`python-ai-developer`)

**Depends on:** 2

**Files to touch:**
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `README.md`
- `skills/angular-ui-rules/SKILL.md`
- `.claude/scripts/tests/test_plugin_manifests.py`

**Pre-written TASK block:**
```
TASK: Write the registry entries (review F5), raise the version to 0.10.1, fix the skill count and the T-001 line
(F2, F3), and correct the README's removal text.
CONTEXT: concept contract at .claude/concepts/2026-10-29-upgrade-loop-and-registry-entries.md (Registry entries,
  Version, F2 and F3, Extension Points).
FILES: as listed.
CONSTRAINTS:
  - Registry text and placement exactly as the Registry entries table says. The five definitions are verbatim from
    .claude/concepts/2026-10-28-angular-tailwind-rule-documents.md lines 23-27. Line 41 gets the amendment sentence
    with its date marker and contract pointer. Both files are CRLF: keep CRLF on new and changed lines and change
    no other line. Prove CRLF with a \r$ line count: MECHANISMS.md 71 of 71, VOCABULARY.md 70 of 70. Prove scope
    with git diff --numstat: MECHANISMS.md "2 1", VOCABULARY.md "6 1".
  - README.md:262 and the table header at README.md:275: the contract's replacement text (Extension Points).
    Leave line 282 as it is.
  - Version 0.10.1 in all five places: plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json and both
    entries of .claude-plugin/marketplace.json.
  - F2: write 32 (the skills/*/SKILL.md count; recount) for "28 skills" at README.md:436 and in the four manifest
    descriptions. Add INV-15 to test_plugin_manifests.py (docstring line and check). It covers all five places:
    the four descriptions and the README table row. Include a positive control on a wrong count.
  - F3: replace skills/angular-ui-rules/SKILL.md:35 with the contract's T-001 line. Run
    .claude/scripts/tests/test_angular_rule_delivery.py and .claude/hooks/tests/test_angular_rule_coverage.py.
  - Run py -3 .claude/scripts/check_version_bump.py (exit 0), test_plugin_manifests.py and
    test_check_version_bump.py. Paste the exit codes.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-29-upgrade-loop-and-registry-entries.md
  contract_status: approved
```

### 4. Review (`fullstack-code-reviewer`)

**Depends on:** 1, 2, 3

**Files to touch:**
- `.claude/reviews/2026-10-29-upgrade-loop-and-registry-entries/t4-review-fullstack-code-reviewer.md`

The gate also writes its Gate Output, `.claude/reviews/2026-10-29-upgrade-loop-and-registry-entries/t4-review-fullstack-code-reviewer.gate.json`, in the same diff. It is named here, not as a second bullet, because the template requires a review gate's list to name exactly one path. The off-list check counts the Gate Output as part of the declared artefact.

**Pre-written TASK block:**
```
TASK: Review sub-tasks 1-3 against this contract and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-10-29-upgrade-loop-and-registry-entries.md
FILES: .claude/reviews/2026-10-29-upgrade-loop-and-registry-entries/t4-review-fullstack-code-reviewer.md (and its
  Gate Output t4-review-fullstack-code-reviewer.gate.json beside it)
CONSTRAINTS:
  - Check: L-1 to L-8 against the code. Check that sub-task 1's tests failed before sub-task 2 (from its pull request)
    and pass now. Probe the loop: a local-only row in each OLD_ROW_FORM, then install, remove, install. Check the
    registry text and placement, the \r$ counts (71/71, 70/70) and the numstat, all five version entries,
    check_version_bump.py, F2's count and INV-15 over all five places, and F3's line. Check README.md:262 and :275
    and the skill's line 20 against the code. Check that the uninstall skill's Step 0 is unchanged, and that the two
    file cases of L-1 are documented, not changed.
  - Run: test_auto_improve_finish_install.py, test_plugin_manifests.py, test_skill_script_lookup.py, test_addons.py,
    test_angular_rule_delivery.py, test_angular_rule_coverage.py, test_check_version_bump.py,
    check_version_bump.py --base origin/master.
  - Write the six-section artefact. The file does NOT exist yet; you create it. Name the commit range base..head.
  - "## Evidence" lists the commands with their exit codes and is never empty.
  - The header ends with exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked".
  - Write the Gate Output <artefact stem>.gate.json beside it, covering every Review checklist item.
  - Janitor: the registry appends are sub-task 3's. Add nothing new unless the diff introduces something new.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-29-upgrade-loop-and-registry-entries.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

`pr_merged.py` fills this list when the contract's work is merged and nothing is pending: a line is checked only when an effective review report's Gate Output says `met`, and every other line stays unchecked with the reason. Do not tick lines by hand.

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both backend and frontend sides
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
- [ ] `Status` flipped to `implemented`
