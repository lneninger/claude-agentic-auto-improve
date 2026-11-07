# Concept Contract — Domain-split registries and journal (issue #235)

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-04
**Requested by:** user
**Status:** approved
**Work Item Brief:** .claude/work-items/2026-11-04-235-domain-split-registries.md
**Tracking issue:** pending (opened by `/design-first` Step 3.4)
**Budget:** 18,000 tokens (XL contract). Superseded text and every critique round live in `.claude/contract-history/2026-11-04-domain-split-registries.round-{1,2,3}.md`.
**Amendment:** 6 (2026-11-07). Sub-task 12's engineer stopped `has-issues` after committing the merge (merge commit `8558879`): two registry lint findings, a red bridge test and a red version-rule row that block 12 did not cover. This amendment changes block 12 only, plus I-7, Adjacent Areas (one follow-up row), Uncertain Assumptions, Failure Modes, Confidence, Lessons and block 14's CONTEXT line and amendment-6 check. It adds no block; block 12 re-runs on the same branch. Status went from `approved` back to `draft`; the owner answered "amend" to all three recommendations (2026-11-07). See "Amendment 6 record".
**Previous amendments:** 5 (2026-11-07: blocks 12–14 after the landing halted; "Amendment 5 record") and 4 (2026-11-06: blocks 10–11 after the t9 review; "Amendment 4 record"). The owner re-approved both. Amendment 3 (2026-11-04) was approved. Blocks 1–11, 13 and their completion records are unchanged.

> **Protocol:** filled in by `data-architect`. Implementers refuse to run unless `Status: approved`. `concept-gate.py` reads `Files to touch`. Lifecycle, budget rule and management commands: `.claude/templates/concept-contract.md`.

---

## Business Concept

- **What is this thing?** The three registries (mechanisms, vocabulary, journal) get a numbered **registry layout**. Layout 2 is the split form: each root file holds only the Universal tier and a fixed pointer, and project content lives in **domain files** beside it (`MECHANISMS/general.md`, `MECHANISMS/backend.md`, …). With it come one shared reader, one write path that keeps working on unmigrated projects and never writes project content into the Universal tier, the §3.4 structural lint, and a numbered **registry migration** from layout 1 to 2. The migration moves project content, including client-authored project-token entries in the Universal tier (§4.4), and never loses or invents text: what it cannot parse is kept verbatim as a **migration leftover**.
- **The defect:** a client split its registries, the plugin's tools never learned the split, writers kept appending to the flat files, and nothing noticed the copies diverge.
- **Existing VOCABULARY.md terms that apply:** Vendored asset; Plugin-delivered asset; Installed plugin root; Accepted guard limit; Ownership tier; Vendored-asset drift; Layout defect; Universal / Project tier.
- **New terms (Universal tier).** Each carries *registry* or *migration*, so none reads as the delivery terms **Layout defect** / **Layout warning**:
  - **Registry layout** — the numbered shape of one project's three registries. Layout 1 is flat; layout 2 is split, declared by `<!-- registry-layout: 2 -->` as line 1 of each root file. The marker alone never proves layout 2.
  - **Registry layout state** — `current`, `pending`, `stale-sync`, `unknown` or `absent`, computed by I-1. Not a delivery-layout value.
  - **Domain file** — a project-tier file `.claude/registries/<REGISTRY>/<domain>.md` (lowercase slug). `general` always exists under layout 2; the domain set is the files on disk (Q8). Project-owned, never synced.
  - **Registry entry key** — the normalised title (lowercased, whitespace collapsed, date tag excluded). Two entries with one key in one registry are a duplicate.
  - **Legacy registry entry** — an entry in a pre-grammar form (`## YYYY-MM-DD …` heading, or a column-0 dated journal bullet). Read, keyed and indexed like any entry, never converted.
  - **Registry migration** — a numbered, idempotent change from layout N to N+1, previewed first and applied only against the previewed hash.
  - **Migration leftover** — source text a registry migration could not parse into an entry, copied verbatim into a fenced block in that registry's `general.md`. Inert: never parsed, never a finding.

---

## End-User View

Not applicable. Reason: no Angular UI surface is touched; `Files to touch` holds Python scripts, hooks, agent and skill markdown, templates, registries and docs only.

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership |
|------|--------|------------|-----------|
| Registry (mechanisms, vocabulary, journal) | name; root file; domain files (`general`, then alphabetical); layout state | **I-1** over the three root files under the resolved `.claude/registries/`: `absent` = none exists. `unknown` = one or two missing (reason `registry-missing:<NAME>`), a marker with another value, or mixed marked/unmarked roots. `pending` = all three exist, none marked. `current` = all three marked on line 1, no root holds a `## Project:` heading or any entry or leftover below its pointer, and every `<REG>/general.md` exists. `stale-sync` = all marked but a `current` condition fails. **I-2** a layout-2 root's last section is the fixed pointer `## Project tier`: it names `<REGISTRY>/<domain>.md`, says `general.md` always exists and every `.md` in the folder is read, and lists no domain (generic, syncable). **I-3** domain files resolve from the same `.claude` root as the root file; never a union of roots. **I-4** `INTEGRATION.md` is outside the layout; the digest indexes it and R6 hashes it when present. **Tier heading** = `## Project: <name>` (layout 1) or `## Project tier` (the pointer). | the project |
| Registry entry | registry; tier (`universal`, `project:<name>` on layout 1, `domain:<slug>`); file; line; title; key; text; tags; source contract; status (`active`, `archived-title-only`, `legacy`) | **I-5** has a body unless `archived-title-only` or `legacy` (body per grammar below). **I-6** keys unique per registry. **I-7** append-only from layout 2 on: an entry is never reordered or rewritten; allowed appends are a new entry, an indented `Correction (<date>, <source>)` line, and an indented `Status: archived-title-only` line under a bodiless entry. Exceptions: sub-task 1's pre-layout reconciliation (block 12 rule (4) keeps it through the merge: the default branch's copies of the three entries it folded are deleted, not re-added); *amendment 5, block 12:* the Q22 fold, which deletes the default branch's 2026-11-05 "CodeGraph (amendment)" entry and re-adds its text verbatim as the last Correction line of the 2026-10-30 entry, and rule (5)'s move of any default-branch journal entry that git placed below the pointer to the end of the Universal tier, text unchanged; *amendment 6, block 12 rule (9):* the fold of the default branch's 2026-11-06 "CodeGraph (correction)" entry (issue #271) as the last Correction line of the 2026-11-05 "CodeGraph (correction)" entry, and the move of its column-0 VOCABULARY "Correction (2026-11-06, issue #271)" line to the last indented line of "Investigation Turn (amendment)", text unchanged. No other rewrite or reorder is allowed; header prose and leftover blocks are not entries. **I-8** fenced code blocks are never parsed. **I-8b** non-entry heading: a journal `###` heading not starting with a `YYYY-MM-DD` shape (e.g. `### Tag conventions`), or a `#`/`##` heading that is neither a tier heading nor a legacy dated heading. Its **section** runs to the next heading of the same or higher level, and every line in it is prose: never an entry, never an R1/A1 finding. **I-8c** a legacy entry is keyed (R2 applies), indexed by the digest under its tier, returned to readers, exempt from R1/A1, printed as `advisory: legacy <file>:<line>`, never converted, and never fires the tracker. | its registry |
| Registry migration | number (0001); from; to; plan; plan hash; report | **I-9** dry-run writes nothing under `.claude/registries/`. **I-10** apply writes only when the recomputed plan hash equals `--expect-sha256`. **I-11** idempotent: after a successful apply the tree is `current`; on `current` the plan is empty and exit is 0, checked before any git check (see Commands). **I-12** no loss, checked on the plan before any write. *Entries:* every input (key, text) maps to an output entry with that key holding every input line (merges per step 4), and per registry `occurrences in = kept + moved + merged away`. *Text:* after folding line endings, dropping the BOM and trimming trailing spaces, the multiset of non-blank source lines equals the multiset of non-blank destination lines, minus the lines 0001 adds and plus the removed lines, both **counted per instance** (multiset subtraction). Added lines: marker, pointer section, skeleton header, leftover heading, provenance and fence lines. Removed lines are a closed set, each listed with file:line and reason: `project-heading`; `replaced-sync-section` (the marker and pointer-section lines a stale sync delivered; on `stale-sync`, "project content" starts after the pointer section, so these lines are counted once); `merged-duplicate` (a line of a duplicate copy that also appears verbatim in the kept copy). Mismatch → `content-loss-detected`, nothing written. *Per entry (amendment 4, W3):* with the same normalisation (line endings folded, BOM dropped, trailing spaces trimmed, blank lines ignored), each key's output entry holds, as a multiset, every input line of every occurrence of that key minus that key's `merged-duplicate` lines; else `content-loss-detected`. Two output entries with one key → `conflicting-entry` naming both output locations and their first lines. **I-13** a refusal leaves every registry file byte-identical and still writes the report. | plugin (code); project (result) |

### Value Objects

| Name | Fields | Invariants | Used as |
|------|--------|------------|---------|
| M/V entry grammar | `- **<title>**` at column 0, optional `*(<date>)*`, separator (`—` written; `—`, `--`, `-` read), body; continuation = following lines indented 2+ spaces until the next column-0 `- **` or a heading; forms `  - **Correction (<date>, <source>):** …`, `  - **Status:** archived-title-only` | title non-empty; body = text after the separator plus continuation, excluding `Status:` lines | parser input |
| Journal entry grammar | `### YYYY-MM-DD <sep> <title>` (the tracker's `ENTRY_HEADER` separators); fields Trigger, Source contract, Lesson, Apply when, Tags; optional Areas, Status | **text** = every line after the heading up to the next heading; "has a body" (R1, I-5) = an `Apply when:` field with text (§3.4) | parser input |
| Legacy entry grammar | `## YYYY-MM-DD <sep> <title>` plus lines to the next heading; or, in a journal file outside any entry, a column-0 `- ` line whose text starts with a `YYYY-MM-DD` date, plus its indented continuation | title = text after the date and separator | parser input (I-8c) |
| Path reference | one backticked span | made only of letters, digits, `_ - . / \`; contains `/` or `\`; ends in `.<1-8 letters or digits>`; does not start with `/`, `./` or `../`. So `` `?? d/f.txt` ``, `` `"$CLAUDE_PROJECT_DIR"/…` ``, `` `../website-design/references/foundation.md` `` and any `file:line` span are not references (file:line citations are not checked; Non-Goals) | `_registry_layout.path_references`, R4 |
| Migration leftover block | source file; line range; reason (`project-prose`, `non-entry-heading`); verbatim lines | under the one `## Migration 0001 leftovers (not parsed as entries)` heading, which is the **last** section of `<REG>/general.md` (an I-8b section: the whole section is prose); one `<!-- leftover from <file>:<a>-<b>, <reason> -->` line, then a fence longer than any backtick run inside; content byte-equal to source after folding | 0001 output; lint prints `advisory: leftover <file>:<line>` |
| Structure finding | rule id; file; line; key; message; remedy; severity (`finding`, `advisory`) | rule id R1–R6 or A1; file and line always set; key empty only for R4–R6 | lint, digest, migration report |
| Migration report | number; project; mode (`dry-run`, `apply`, `refused`); refusal code; plan hash; plugin root used or `unverified` + reason; per registry: kept, moved (key, from, to, reason), merged duplicates, appended merge lines, bodiless orphans (hint + ready-to-run `--archive-title-only` line), unclassified, token entries moved, plugin-owned token entries, unverified token entries, universal candidates, unmovable token lines, legacy entries, leftovers, removed lines, conflicts (key, locations, differing field, each version's first line), counts; error (amendment 4, N2) | refusal code empty unless `refused`; every list present, possibly empty; plan hash in every mode, except `none` when the plan could not be built; error is empty unless the plan could not be built, and then the mode is `refused`, the refusal code is `plan-build-failed`, error holds the exception type and message, every list is empty, the report is still written, no registry file is touched (I-13) and the exit is 2 | `registry-migration-report.md` + `report.json` in `<project>/.claude/cache/registry-migrations/0001-<UTC>/`, JSON on stdout |
| Registry layout state | state; found marker (value or `none`); layout current (2); reasons; remedy | marker `none` for `pending`/`absent`; reasons non-empty for `stale-sync`/`unknown`; remedy `registry_migrate.py --dry-run` (pending, stale-sync), `plugin_doctor.py --fix` (absent, registry-missing), else "make the root markers agree, then re-run `--check`" | `layout_state`, `--check`, doctor, lint mode, `registry_append.py` |
| Plugin root resolution | path or none; reason (`same-as-project`, `no-manifest`, `not-found`) | resolved only by `_plugin_root.separate_plugin_root(project, plugin_root, needs=<all three root registries exist>)`; never the project's own tree; none → every token entry is `unverified` and stays | 0001 step 2, R3, R4 candidate roots |

### Structural lint rules (validate_registries.py --check-structure [--project] [--strict]), issue §3.4 order

- **R1 bodiless-entry** — a journal entry without `Apply when:` text; *addition:* an M/V entry with an empty body. `archived-title-only`, legacy entries and I-8b sections are exempt.
- **R2 duplicate-title** — a key present more than once across root and domain files; every location reported.
- **R3 project-entry-above-pointer** — in a root: a `## Project:` heading, or an entry or leftover below the pointer. Plus, when `.claude/.project-tokens.json` lists tokens, a token-bearing Universal entry (case-insensitive, `allowed` honoured) that is **client-authored** (key absent from the resolved plugin root's Universal tier). A hit in a plugin-owned entry is advisory `R3 plugin-owned`. With no resolved plugin root, every hit is advisory `R3 unverified`. Client-authored Universal entries without a token are advisory `R3 universal-candidate`. *Amendment 4 (Q19 a):* when the project holds this plugin's own manifest (`_manifest_names_plugin(project)`), the `universal-candidate` advisories are dropped, and only when at least one was dropped the lint prints exactly one line, `advisory: R3 universal-candidate skipped: <N> entries; this project holds the plugin's own manifest` (fixed prefix `advisory: R3 universal-candidate skipped`, ASCII only). Token findings, `plugin-owned`, `unverified` and every other result are unchanged.
- **R4 dead-file-reference — ADVISORY.** Each Path reference in a registry file (fences and leftovers skipped) is resolved against the **candidate roots**: the project root (the folder holding `.claude/`), then the resolved plugin root when there is one. A reference whose path starts with an **excluded prefix** is skipped: `.claude/settings.json`, `.claude/settings.local.json`, `.claude/.sync-config.json`, `.claude/.sync-state/`, `.claude/hook-registration-profile.json`, `.claude/.scout-cache/`, `.claude/cache/`, `.claude/logs/`, `.codegraph/` (consumer-only or generated; the closed list lives in `_registry_layout` and the spec). Others resolving under no candidate print `advisory: R4 <file>:<line> <path>`; exit unchanged except under `--strict`. Expected on this repository: the retired-contract citations (`2026-10-12-dedupe-claude-config.md`, `2026-10-07-worktree-isolation-by-default.md`), `tools/sync-plugin.cmd`, `tools/sync-plugin.ps1`, `python/scalping_strategy_rl/…`, `tests/integration/conftest.py`. Reported, never rewritten (I-7); an appended `Correction` line naming the right path does not silence it, because the original span stays (amendment 4, N1). The default (non-structure) mode keeps its regex and exit code; from amendment 4 (W4) it reads every file of `registry_files`, and in each file it ignores everything from the `## Migration 0001 leftovers (not parsed as entries)` heading on, so leftovers never produce a default-mode finding.
- **R5 domain-file-invalid** — deliberate deviation from §3.1.2/§3.4: on-disk discovery, no `registries.domains` slot (Q8). Fires on `general.md` missing, a non-slug name, a nested folder, an `INTEGRATION/` folder; applies when a domain folder exists or the state is `current`/`stale-sync`.
- **R6 digest-stale** — the digest records `<!-- registry-sources-sha256: <hex> -->` over every file it reads (registry files + `INTEGRATION.md` when present, sorted path, normalised bytes). Fires when the digest exists and the line is missing or differs, or a registry key (legacy included) is absent from it. Absent digest prints `digest: absent`.
- **A1 malformed-entry** — *addition beyond §3.4.* Journal: a `###` heading starting with a `YYYY-MM-DD` shape that has an invalid date, no separator, a missing required field, or a Trigger outside {`pre-approval critic`, `post-approval`, `post-impl divergence`, `manual`}. M/V: a column-0 `- **title**` with no separator. Legacy entries are not A1.
- **Mode (§7):** not `current` → every finding is advisory, plus `advisory: registry layout <state> — <remedy>`, exit 0. On `current`: exit 1 on any R1, R2, R3 (non-advisory), R5, R6 or A1 finding (R4 too under `--strict`), else 0. Exit 2 = could not check (including a missing new module, named).
- **Digest generator:** no hard-coded `DOMAINS`; reads through the resolver; tier labels (`Universal`, `project:<name>`, `domain:<slug>`); always writes the complete index (legacy entries included, as `DATED` indexes them today), the INTEGRATION section and the sources hash; exits 1 naming each R1/R2 finding (Q9).

### Events

| Name | Emitter | Listeners | Payload |
|------|---------|-----------|---------|
| Journal entry appended | `registry_append.py` (calls the listener directly, passing the new signature as `fresh`) or an Edit/Write on any journal file (`post-edit-dispatcher.py` → tracker) | `accuracy_update.process_journal_change(files, fresh=())` → `record_failure(area, contract, "post-approval-journal")` for `post-*` triggers | **I-14** signature stays `sha1(date + "\|" + title)`. The machine-wide seen cache gains `seeded_files`, keyed by `checkout_equivalent_path(resolved path)` (`MECHANISMS.md:43`; case-folded on Windows), so a file seeded in one checkout is seeded in every worktree of it. Each file of `registry_files("JOURNAL.md")` whose key is not seeded is seeded first (signatures marked seen, nothing fires); new signatures in seeded files fire, plus any `fresh` one. An old cache (`_initialized`, no `seeded_files`) counts as having seeded the root `JOURNAL.md` key only. *Reader change (amendment 4):* each `seeded_files` value records the reader that seeded it (`reader: 2` = `_registry_layout`); a file seeded under an earlier reader (no `reader` value) is re-seeded once on its next read with the current reader (every signature it yields marked seen, nothing fires except a `fresh` one), so a heading the old and new journal patterns read differently never fires after an upgrade, on any client journal. Nothing fires retroactively or twice. **Accepted guard limit** (pinned by a test, Q17): a hand-written `post-*` entry in a journal file whose checkout-equivalent path this machine's cache has never seen does not fire, and neither does one hand-written in the same edit that triggers a file's reader re-seed; the script path does. |
| Registry layout migrated | `registry_migrate.py --apply` | operator, doctor | Migration report |

### Commands

| Name | Handler | Payload | Rejections (closed set; exit) |
|------|---------|---------|------------------------|
| Append registry entry | `registry_append.py` | `--project` (required), `--registry mechanisms\|vocabulary\|journal`, `--from-file <entry.md\|->`, then `--universal`, or `--domain <slug>` [`--create-domain`], or neither. **Domain choice** (non-`--universal`): `--domain` when that file exists (or `--create-domain`), else the source contract's area via `derive_area` when that file exists, else `general`; the choice is printed. **Placement on `current`:** `--universal` → end of the Universal tier, before the pointer; else end of the domain file's entries, before the leftovers heading when present. **Placement on `pending`/`stale-sync`:** a non-`--universal` entry goes to the domain file chosen as above, with `general.md` created from the skeleton when missing (an unknown `--domain` without `--create-domain` falls back to `general`, named in the advisory); it is **never** written into a root file. `--universal` → end of the root's Universal tier (before a synced pointer, else before the first `## Project:`, else end of file). Both print `advisory: registry layout <state> — appended to <file>:<line>; run registry_migrate.py --dry-run`, exit 0. Writes via `_atomic_write`; prints `file:line`. | `bodiless-input`, `duplicate-entry` (root + all domain files), `malformed-input`, `unknown-domain` (`current` only), `no-universal-tier` (`--universal` and the root holds no title heading and no entry above its first tier heading), `correction-target-missing`, `archive-target-missing`, `archive-target-has-body` (2); `layout-unknown`, `registries-absent`, `project-undetermined`, `write-failed` (3) |
| Check registry structure | `validate_registries.py --check-structure [--project] [--strict]` | — | 0 / 1 / 2 per Mode |
| Check layout | `registry_migrate.py --check --project <root>` | — | prints the layout state as JSON; 0 `current`/`absent`; 6 `pending`/`stale-sync`; 2 `unknown` or unreadable |
| Preview / apply migration | `registry_migrate.py --dry-run` / `--apply --expect-sha256 <h>`; `--project` required; `--plugin-root <path>` optional, passed to `separate_plugin_root` as its override (rejected when it is the project or names another plugin → `unverified`) | **Order:** (1) arguments and project; (2) layout state — on `current` with an empty plan, print the report and exit 0; (3) `not-a-git-tree`, then `uncommitted-registry-changes` (git status of `.claude/registries/` only); (4) plan, I-12, hash compare (apply); (5) stage and replace. Dry-run runs (1)–(4). | `project-undetermined` (unset or absent), `not-a-git-tree`, `uncommitted-registry-changes`, `conflicting-entry`, `unknown-layout`, `changed-since-preview`, `content-loss-detected`, `symlink-target`, `write-failed` (3); `plan-build-failed` (2; amendment 4: an exception while building the plan, report written with `error`); bad arguments 2 |

**Plan hash:** `_plan_digest` over `b"registry-migration"`, `b"0001"`, then per file to write in sorted POSIX relative-path order: path, input bytes or `absent`, planned output bytes. The report is outside the plan.

**Shared helpers.**
- `_preview_apply.py` — `_plan_digest` and `_atomic_write` **extracted unchanged** from `auto_improve_finish_install.py` (finish-install imports them back; `_backup_write` stays in finish-install, unused here). **New code:** `stage_and_replace(writes, backup_dir, base=None)`: (a) write every planned output to `.<name>.stage-<pid>` beside its target; any failure deletes all stage files and every folder step (a) created, and returns `write-failed` with no target touched; (b) copy every existing target into `backup_dir / target.relative_to(base)` (`base` defaults to the common parent folder of the targets; 0001 passes the project root; a target outside `base` → `write-failed` before step (a)) (amendment 4, W2); (c) `os.replace` each stage file onto its target in plan order; (d) on a replace failure, restore every already-replaced target from `backup_dir` (delete targets that did not exist), delete the remaining stage files, remove every folder step (a) created that is now empty (amendment 4, N3), return `write-failed`. 0001's `backup_dir` = `<report folder>/backup/`, never under `.claude/registries/`.
- `_plugin_root.py` — `_separate_plugin_root` (`auto_improve_finish_install.py:347-377`) and the helpers it calls (`_same_dir`, `_norm`, `_manifest_names_plugin`, `_load_json_lenient`, `_claude_home`, `_version_key`, `_cache_roots`, `PLUGIN_NAME`) **extracted unchanged**, exported as `separate_plugin_root`; its "own copy" candidate is this module's tree (same folder as before). `find_plugin_root` is imported from `plugin_doctor` inside the function only. Finish-install imports every moved name back (one definition each).
- **Import chain (kept minimal):** `_preview_apply` and `_plugin_root` import the standard library only and change no `sys` state at import. `_registry_layout` imports the standard library and `_claude_paths`. Finish-install hard-imports `_preview_apply` and `_plugin_root`. `plugin_doctor` and `validate_registries --check-structure` import the new modules lazily and, on `ImportError`, report the missing module by name (doctor: one line, other checks unaffected; lint: exit 2). The tracker hook exits 0 with one stderr line if the new `accuracy_update` entry point is missing. *Amendment 4 (W1):* `accuracy_update` imports `_registry_layout` **lazily**, inside `parse_journal_entries` only; on `ImportError` that function writes one stderr line naming the module and returns no entries (nothing fires, nothing is seeded). Its module-level imports stay as today, so `critic-verdict-tracker.py:68` and `contract-status-watcher.py:68`, which import `accuracy_update` inside a fail-soft `try` (`_DEPS_OK = False` on any exception, silently), keep recording critic and status accuracy on a copied-script client that lacks `_registry_layout`. A test pins this for both hooks. *Amendment 5 (WARN 3):* the parent's `generate_registry_digest.py:39` imports `_registry_layout` at module level, so on a copied-script client that lacks it, `memory_boundary._bind("generate_registry_digest", …)` yields `None` for every name and memory capture refuses `reader-unavailable`, where the default branch's capture works. Accepted: the README copy list names `_registry_layout` (sub-task 8). `memory_boundary` binds `registry_files_in` fail-soft, never by a module-level import: `_bind("_registry_layout", "registry_files_in")`; when it is `None`, `select_candidates` refuses `reader-unavailable` exactly as it does for missing readers, and every other subcommand (retrieval included) keeps working. A block 12 test pins it.

**Migration 0001 (layout 1 or `stale-sync` → 2), per registry:**
1. **Parse** roots and domain files into entries, legacy entries, I-8b sections and fences.
2. **Universal tier** (above the first `## Project:`; on `stale-sync`, above the synced pointer section). Header prose, I-8b sections, fences and plugin-owned entries stay. Plugin keys come from the Plugin root resolution:
   - token-bearing, key in the plugin's Universal tier → stays (`plugin-owned-token-entry`; moving it loops through the next sync);
   - token-bearing, no resolved plugin root → stays (`token-entry-unverified`; re-run with `--plugin-root`);
   - token-bearing, client-authored → moves like a project entry (step 3);
   - no token, client-authored → stays, listed as `universal-candidate` (W7);
   - a token line outside any entry → stays, `unmovable-token-line`.

   About §6's "~102 flat-only entries to merge into domain files": entries under a `## Project:` heading move (step 3); client-authored entries in a heading-less root without a token are reported, not moved. To move them, the operator adds a `## Project: <name>` heading above them while still on layout 1, commits, and re-runs the dry-run (Q18).
3. **Project content** (under each `## Project:`; on `stale-sync`, after the pointer section). Entries and legacy entries move verbatim, in §4.2 order: the domain file already holding the key, then a `Tags:` value equal to an existing domain-file name, then the source contract's area when that file exists, then `general` (listed as unclassified). Prose, I-8b sections, tables and legacy pointer lines ("See domain-specific files…") go verbatim into leftover blocks. `## Project:` heading lines are removed and listed. 0001 creates no domain file except `general.md`.
4. **Same key in more than one place** (after step 3):
   - identical text, or one copy's lines all appear verbatim in the other: one copy is kept at the destination (an existing domain-file location wins), the other's lines are `merged-duplicate`;
   - otherwise compare field by field (journal fields; for M/V the body is one field): when no field present in both copies differs, the kept copy is the bodied one (else the domain-file one) and each line of the other copy not already present is **appended verbatim** under the kept entry, listed as an appended merge line; nothing is discarded;
   - a field present in both copies with different text → refuse `conflicting-entry`, naming every location, the field and each version's first line. The heading line counts as a field (amendment 4, W3): two copies whose heading lines differ (for example only in the date) conflict, so step 4 never appends a line that parses as a heading. **Way out:** on layout 1, keep one version, rename one title, or fold one version into a `Correction` line; commit; re-run the dry-run.
5. **Bodiless keys** go through steps 3–4 like any entry. Each is listed as a bodiless orphan with the hint "recover the body from your own backups, or mark it" and a ready-to-run `registry_append.py --archive-title-only "<title>"` line (Q15). 0001 never invents or marks text.
6. **Write.** The marker, exactly one pointer section, `general.md` from the skeleton when missing, moved entries above the leftovers section, the leftovers section last. I-12 first, then `stage_and_replace`.

**Post-condition:** no project heading, no entry or leftover below a pointer, no duplicate key, every `general.md` present → `current`; `--check` exits 0; a second apply has an empty plan and exits 0 before any git check. R1 may still be red on orphans (§4.3 step 5, by design).

---

## Reused Mechanisms

- **Two-tier registry with a generated complete index** — extended: its thin-root shape becomes layout 2; the generator reads through the resolver, labels tiers, writes a sources hash, keeps legacy entries in the index, exits 1 on R1/R2.
- **Two-layer Claude path resolution** — extended by `registry_files(name, domains=None)` in `_project_paths.py` (root, then `general`, then other domain files alphabetically; existing files only; `domains` restricts and always keeps `general`) and consumed via `checkout_equivalent_path` for I-14. `_claude_paths.py` re-exports both. No `sys.path.insert(0, …)` (`MECHANISMS.md:43`).
- **Preview-hash apply** — shared by extraction of `_plan_digest` and `_atomic_write` into `_preview_apply.py`; the staged multi-file replace is the only new code. Not a wholesale import of finish-install (it sets `sys.dont_write_bytecode` and `sys.path` at import, `:93-99`); not a copy; not a finish-install subcommand (Option E).
- **Installed plugin root** — consumed through `_plugin_root.separate_plugin_root`, the existing guard that rejects the project's own tree and requires this plugin's manifest (JOURNAL 2026-10-04). Never `find_plugin_root` alone.
- **Project-name check** — consumed: 0001 and R3 read `.claude/.project-tokens.json` the way the sync does.
- **Adaptive Engineering Journal** — extended: entries in domain files; `Status: archived-title-only`; append path `registry_append.py`.
- **Section-scoped registry sync** — consumed: under layout 2 the root is whole-file Universal content plus the pointer; domain folders are project-owned.
- **Plugin doctor** — extended: three `copy` requirements for the skeletons, a report-only layout-state line, "body-less journal entries: N", `--json` key `registry_layout`.
- **Post-edit dispatcher**, **Plugin version check modes**, **Parent Branch Delivery Rule** — consumed as-is.
- **Memory adapter** (`memory_boundary.py`, the default branch's `469f51f`) — consumed and re-routed (amendment 5, Q21): it keeps binding `generate_registry_digest.entry_blocks`, `journal_entries` and `BULLET`, which become re-exports of adapters in `_registry_layout`, and its registry file list comes from `_registry_layout.registry_files_in` instead of a fixed `DOMAINS` list.
- **Script lookup block** (`skills/verify-before-done/SKILL.md` Step 1) — reused verbatim for `registry_append.py` and `validate_registries.py` in every skill and in `agents/fullstack-code-reviewer.md`, always with `--project "$CLAUDE_PROJECT_DIR"`; `test_skill_script_lookup.py` widens its scan to `agents/*.md`.

## New Mechanisms (if any)

- **Registry layout reader** (`.claude/scripts/_registry_layout.py`) — sole owner of the marker, grammars, keys, path references, I-8b/I-8c, layout state and R1–R6/A1. **Why not existing:** the grammar exists twice with different rules (digest `BULLET`/`DATED`, tracker `ENTRY_HEADER`), neither knows bodies, keys or fences, and `_project_paths.py` must stay a fail-soft locator (JOURNAL 2026-10-30 "One shared reader must own the filtering"). **Promote:** yes.
- **Registry migration runner** (`.claude/scripts/registry_migrate.py` + `registry_migrations/`) — numbered, previewed, idempotent migrations and the layout gate. **Why not existing:** no migration framework exists; the doctor pins "never write an existing file"; finish-install owns the profile and settings files. **Seam:** migration N+1 = one module + one list entry. **Promote:** yes.

---

## Extension Points

- `_project_paths.registry_files`; `_claude_paths` re-exports `registry_files`, `checkout_equivalent_path`.
- `_registry_layout`: `LAYOUT_CURRENT = 2`, `MARKER`, `REGISTRIES`, `R4_EXCLUDED_PREFIXES`, `parse_entries`, `entry_key`, `path_references`, `layout_state`, `structure_findings(…, plugin_keys=None)`.
- `_preview_apply`: `_plan_digest`, `_atomic_write`, `stage_and_replace`. `_plugin_root`: `separate_plugin_root`.
- `_plugin_root._manifest_names_plugin` is consumed (amendment 4, Q19 a) by `--check-structure` for the R3 `universal-candidate` skip. It stays private (one definition, same plugin, already imported back by finish-install); it is listed here so the consumer is on record.
- *Amendment 5 (Q21):* `_registry_layout.source_value(raw)` (the Source contract rule the default branch shipped: the rest of the line, backticks and padding trimmed, the unset forms `none`, `n/a`, `na`, `unknown`, `tbd`, empty and `<…>` read empty), used by `accuracy_update.parse_journal_entries` and the adapters; `_registry_layout.entry_blocks(text, pattern=None, per_domain=False)` and `journal_entries(text, per_domain=False)`, adapters over `parse_text` that return the default branch's dict shapes; `generate_registry_digest` re-exports both and `BULLET`.
- `validate_registries.py --check-structure [--strict]`; `accuracy_update.process_journal_change(files, fresh=())` (the hook becomes a thin wrapper whose `is_journal` matches any `registry_files("JOURNAL.md")` file at call time).
- `plugin_doctor.REQUIREMENTS` + report lines + `--json` key; `registry_migrations/__init__.py` list, `m0001_domain_split.py`.
- `skills/verify-before-done/SKILL.md` step running `--check-structure` (exit 1 NOT-READY; exit 0 with advisories is not); `skills/design-first/SKILL.md` section "Run the data-architect's registry appends" (Q14); `.claude/references/registry-layout.md` § "For the sync tool".

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| tracker hook, `registry_append.py` | `accuracy_update.py` | in-process call | changed journal files, `fresh` signatures | hook/script → script |
| readers: `validate_registries`, `generate_registry_digest`, `cross_area_scan`, `north_star_review`, `accuracy_update`, `plugin_doctor`, tracker hook, `memory_boundary` (amendment 5); 5 agents (incl. `registry-scout`); 9 skills; 3 templates | `_registry_layout` / `registry_files` | import / documented read order | Registry entry | reader → resolver |
| writers: `fullstack-code-reviewer` janitor, `journal-add`, design-first Steps 3 and 5, `data-architect` append rules (§2.2-B) | `registry_append.py` | lookup block + subprocess (data-architect's via design-first's receiver, Q14) | entry file | writer → script |
| `registry_migrate.py`, R3, R4 | installed plugin root | `separate_plugin_root` | plugin Universal keys, candidate root | script → plugin copy |
| finish-install | `_preview_apply`, `_plugin_root` | import (moved names) | — | script → helper |
| sync tool (other repository) | `registry_migrate.py --check` | subprocess exit code + JSON | Registry layout state | external → plugin (follow-up) |

No REST, SignalR or DTO surface; INTEGRATION.md does not apply.

## Adjacent Areas

The architect has no shell and did not run the scanner; `.claude/area-mapping.json` has an empty `areas` map, so it can return no adjacency. The main session should run `py -3 .claude/scripts/cross_area_scan.py .claude/concepts/2026-11-04-domain-split-registries.md` to confirm.

| Area | Decision | Implication / Reason | Handle |
|------|----------|----------------------|--------|
| sync-tool (other repository) | follow-up handle | `tools/sync-plugin.ps1` must halt on `pending`/`stale-sync`, refuse cross-layout publishing, record the applied layout only on `current`, add the new modules to its `files` arrays, and handle the plugin-owned-token loop. Not in this repository. | `.claude/concepts/followups/2026-11-04-sync-tool-registry-layout-gate.followup.md` |
| version-rule (amendment 6) | follow-up handle | The default branch's INV-O1 row in `test_plugin_manifests.py` contradicts the Parent Branch Delivery Rule for every parent-branch sub-task, not only t12 to t14. This contract accepts its own red row; the rule conflict needs its own contract. | `.claude/concepts/followups/2026-11-07-inv-o1-parent-branch-conflict.followup.md` |

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

## Non-Goals

- Recovering the client's lost journal bodies; running the migration in the client; editing client registry files.
- Editing `tools/sync-plugin.ps1`, `.claude/.sync-config.json` or `tools/SYNC.md` (follow-up stub).
- A `registries.domains` profile slot (Q8; deviation stated under R5).
- Rewriting dead references or client tokens in the plugin's Universal tier (`MECHANISMS.md:18,35,36`); checking `file:line` citations.
- Converting legacy entries (Q16); moving client-authored token-free Universal entries (W7, Q18); splitting `INTEGRATION.md`; moving the tracker cache to `state_dir()`.
- A landing verification step for the lint (Q10); changing `skills/ship/SKILL.md` (Q11); a bulk `--archive-title-only` (Q15).

## Confidence

Confidence: Medium-High. High on what exists (amendment 3 re-read `_separate_plugin_root` and its helpers `:284-377`, `_atomic_write` `:380-394`, `checkout_equivalent_path` `_project_paths.py:486`, and the `.gitignore` entry for `.claude/cache/`). Medium on multi-file rollback on Windows and on M/V header bullets parsing (Uncertain Assumptions). Full rationale: round-3 history, Part C. Amendment 4 re-read `accuracy_update.py:40-78,404-438` (the old `_ENTRY_HEADER` and its body cut), `critic-verdict-tracker.py:66-72` and `contract-status-watcher.py:68` (fail-soft imports of `accuracy_update`), and `test_registry_layout.py:737-749` (the this-repository pin). Medium on whether the first post-upgrade re-seed lands before a client's next hand-written `post-*` entry (Accepted guard limit). Amendment 5 re-read both copies of `journal-post-approval-tracker.py` (the parent's thin wrapper; the default branch's caller of `generate_registry_digest.journal_entries`), the default branch's `generate_registry_digest.py:55-184` (`entry_blocks`, `journal_entries`, `_source_value`), `memory_boundary.py:28-61,499-568` (its `_bind` of those names and its fixed-`DOMAINS` file list), `test_registry_entries.py`, `accuracy_update.py:404-446,525-610`, `_registry_layout.py:440-481` (`registry_files_in`) and `check_version_bump.py:62-182` (parent mode). The default branch's copies were read from a checkout of a branch cut from it, not from `origin/master` itself, so block 12 re-reads each one with `git show origin/master:<path>`. Medium on the size of the default branch's other changes (153 commits; only the conflicting files and the reader overlap were read). The critique fold (2026-11-07) re-read `_registry_layout.parse_text`, `_field_map`, `_make_entry` and `fence_mask` (`:153-437`), and, in the default-branch-derived tree `20261107-docs-journal-moving-base-stop-list`, `generate_registry_digest.py:55-184`, `memory_boundary.py:51-61,499-568`, `VOCABULARY.md:79-94` and `JOURNAL.md:411-416`; the adapter differences in block 12 come from that reading. Medium-Low on the merge method holding, because only an instruction to the owner controls it (block 13's Run-first line catches a failure, it does not prevent one), and on the default branch staying conflict-free until the landing. Amendment 6 read the t12 branch's `MECHANISMS.md:119-120`, `VOCABULARY.md:140-146`, `_claude_paths.py:61-117,200-209` and the call sites of `registry_files` / `registry_files_in` (`accuracy_update.py:559`, the tracker's `is_journal`, `memory_boundary.py:500-505`, `validate_registries.py:62`), the Q-hop rows of `test_codegraph_first_guard.py:3195-3240` and `test_plugin_manifests.py:1331-1395`. High on the two folds and the version row. The critique fold (2026-11-07) re-read, in the t12 tree, `_claude_paths.py:55-117,200-216`, the Q-hop rows `test_codegraph_first_guard.py:3178-3264` (with the `643b667` precedent at `:2145-2166`), `test_plugin_manifests.py:1331-1397`, `accuracy_update.py:486-583` and `journal-post-approval-tracker.py:40-114`. Medium-High on the bridge now: the closed set rests on the caller's verified fact (neither helper defines `registry_files` / `registry_files_in`), on the default branch's bridge passing the Q-hop rows beside both helpers, and on one ASSUMED fact (`checkout_equivalent_path` is in both helpers), which the frozen-helper and Q-hop rows prove at import.

## Alternatives Considered & Why Rejected

- **A (chosen):** marker + state, shared reader, single writer with a domain-file fallback, §3.4 lint with R4 advisory, numbered migration with leftovers; sync tool via follow-up.
- **B** revert to flat (the split holds content the flat copy lacks). **C** `registries.domains` slot (Q8). **D** hand edits + lint afterwards. **E** finish-install subcommand (two owners). **F** R4 failing on `current` (red forever under I-7). **G** writer refusing on unmigrated layouts (no write path). **H** writer falling back to the flat root (puts project content into the plugin-owned tier; round-3 B1).

## Uncertain Assumptions

- `VERIFIED via .claude/registries/*.md`: flat registries, no `## Project:` heading, no domain folder, 41 unique journal titles; `JOURNAL.md:28` `### Tag conventions` outside a fence; VOCABULARY duplicates at `:79/:91` and `:86/:94`. This repository's `.project-tokens.json` `tokens` list is empty.
- `VERIFIED via auto_improve_finish_install.py:94,284-394`: `_SCRIPTS_DIR`, `_norm`, `_same_dir`, `_manifest_names_plugin`, `_cache_roots`, `_separate_plugin_root`, `_atomic_write`; callers of `_separate_plugin_root` at `:474,1735,2403` keep working through the import-back.
- `VERIFIED via _project_paths.py:486`: `checkout_equivalent_path` strips `.claude/worktrees/<name>/` segments.
- `FALSIFIED` (t9 review W5, 2026-11-06): on this repository `separate_plugin_root` returns none unless a cache copy exists. A cache copy does exist (`~/.claude/plugins/cache/auto-improve`, an older installed release), so the plugin's own new Universal entries read as client-authored and print 9 `R3 universal-candidate` advisories (exit 0). Tokens are empty, so nothing moves. The remedy is Q19 (answered (a): skip only that advisory when the project holds the plugin's own manifest). `ASSUMED`: M/V header bullets parse as the digest's `BULLET` reads them today. Verification for both: sub-task 3 runs `--check-structure`; any non-R4 finding is reported as AMENDMENT, never suppressed.
- *Amendment 5.* `VERIFIED via check_version_bump.py:163-174`: in parent mode the allowed versions are the base's and the one at `merge-base(origin/<default>, HEAD)`. After the merge, that merge base is the merged default-branch commit, so a head that carries the default branch's version passes. `VERIFIED via the default branch's MECHANISMS.md:93,106`: the default branch holds two entries titled "CodeGraph (amendment)" (dated 2026-10-30 and 2026-11-05), which form one key (Q22). `VERIFIED via memory_boundary.py:60,500`: the adapter binds `DOMAINS` and falls back to its own default list, so a domain file outside that list is never read. `VERIFIED by the amendment-5 critic via concept_changed_check.py and concept-gate.py:201-222` (critic NIT; not re-read by the architect): the Changed-file check judges every changed file (turn end) and staged file (`--staged`, from `/git-commit` and `/verify-before-done`) against Files to touch, but every code path the default branch changed lies under `.claude/` or has a doc or config extension, which the gate allows, so the t12 merge passes it. The t12 diff holds every file the default branch changed; if that check, or any loop or CI gate, still rejects a file, block 12 stops and reports instead of narrowing the merge. `VERIFIED via a default-branch-derived tree (VOCABULARY.md:79,86,91,94)`: the default branch's copies of the three entries block 1 folded are byte-equal to the text block 1 kept, so rule (4) deletes them with nothing to carry over.
- *Amendment 6.* `VERIFIED by the caller's shell (2026-11-07)`: neither `e4f392c` nor `643b667` defines `registry_files` or `registry_files_in` in `.claude/hooks/_project_paths.py`; `e4f392c` defines `worktree_own_root`, `643b667` does not. `VERIFIED via the Q-hop rows (test_codegraph_first_guard.py:3214-3236)`: the default branch's bridge imports beside both helpers, so every bare name it reads (the resolver names and the five launcher names, checked at import by `_claude_paths.py:74-87`) exists in both. `VERIFIED via the t12 _claude_paths.py:97-101`: the parent branch added three bare reads to the bridge: `registry_files`, `registry_files_in` and `checkout_equivalent_path`. `ASSUMED`: both helpers define `checkout_equivalent_path` (the hooks have bound it with `getattr` since before both pins, `concept-gate.py:96-105`, and amendment 3 read it in the parent's base tree). Check: PowerShell `git show 643b667:.claude/hooks/_project_paths.py | Select-String "def checkout_equivalent_path"`, and the same for `e4f392c`; block 12's frozen-helper row and the two Q-hop rows fail at import if it is false.

## Failure Modes & Mitigations

- **A reader keeps reading one flat file** → every reader uses `registry_files`; sub-task 7's text scan fails on any shipped agent, skill or template naming a flat path without the domain form or saying "project section".
- **The strict parser drops forms the old regexes read** → legacy entries (I-8c), I-8b sections, leftovers, text-level I-12; fixtures cover separators, date tags, CRLF, `## YYYY-MM-DD`, bullet journals, prose under `## Project:`, `### Tag conventions`, this repository's registries.
- **The writer misfiles project entries on unmigrated clients** → the fallback writes only domain files; the root is written only for `--universal`.
- **A vendored client's tree is taken for the plugin** → `separate_plugin_root`; none → `unverified`, nothing moved.
- **The tracker fires retroactively, or misses entries in worktrees** → `seeded_files` keyed checkout-independently; tests for both.
- **The new journal reader yields a signature the old regex never did, on a client journal already seeded** (amendment 4) → `seeded_files` records the reader; a file seeded under the old reader is re-seeded once, nothing fires; a client-shaped fixture whose headings the two patterns read differently pins it.
- **A copied-script client lacks `_registry_layout` after W1** (amendment 4) → `accuracy_update` imports it lazily; the critic-verdict and contract-status hooks keep importing `accuracy_update`; a test pins both.
- **A token entry moved by 0001 comes back with the next sync** → plugin-owned entries never move; R3 advisory; follow-up stub.
- **The migration half-writes** → stage all, back up outside the registries, replace, restore on failure (`write-failed`).
- **The lint is red on unmigrated clients, legacy titles or historical paths** → advisory mode until `current`, R4 advisory, `archived-title-only`.
- **Stale sync** (marker above `## Project:` sections) → `stale-sync`, `--check` exits 6, 0001 migrates.
- **A copied-script client lacks the new modules** → import chain kept minimal (above); the README change note (sub-task 8) and the follow-up stub (item 7) list every new file to copy.
- **The reference client's 266 orphans keep verify-before-done NOT-READY** → by design (§4.3 step 5); one ready-to-run `--archive-title-only` line per orphan.
- **The gate reads the plugin's own registries under a plugin install** → `--project` required; `project-undetermined`.
- **Two shared registry readers meet in one merge** (amendment 5): this contract's `_registry_layout` and the default branch's `generate_registry_digest.entry_blocks` / `journal_entries` → one grammar survives (Q21). The default branch's names stay as adapters, so the memory adapter's fail-soft binding keeps working. Its file list goes through `registry_files_in`, and a layout-2 round-trip test pins it (JOURNAL 2026-11-01, merged writer).
- **The merge pull request is squashed or rebased** (amendment 5) → the default-branch parent is lost, and the landing conflicts again. No tool can prevent it: the repository allows merge commit, squash and rebase, and the Merge-direction check judges targets, not methods. The controls are: block 12 proves its own head (two-parent merge commit, `git merge-tree --write-tree origin/master HEAD` clean) and its pull request body tells the owner to merge with "Create a merge commit"; block 13's Run-first line refuses to start when the parent's merge base with `origin/master` is still `9a1b452a`, so a lost parent is caught before more work is built on it.
- **The default branch moves again before the landing** (amendment 5) → the landing configuration declares no `unionPaths` and no `regenerators` (`land_contract.py:1028-1040`), so any conflicting path halts it. The three registries and `README.md` are the default branch's busiest files, and a journal-append branch (`20261107-docs-journal-moving-base-stop-list`) is in flight. Mitigation: block 14's last check is a live `git merge-tree --write-tree --name-only origin/master origin/fix/235-domain-split-registries`, so a conflict that returned after t12 is caught at review time and blocks the verdict, and its report ends with the exact landing command. The remedy for a returned conflict is a second, small merge block added by amendment, written like block 12.
- **Moving entries re-keys memory capture candidates** (amendment 5, critic NIT) → `memory_boundary.py:546,551` keys an M/V candidate by `file|tier|title|line`, so block 12's placement (and 0001 on clients) changes those keys, and a contract whose capture ran before the move is offered its entries again. Accepted: receipts are per contract brief, and the user clears every offered item; journal candidates keep `sig`, which does not change.
- **The default branch adds registry text that breaks the lint on the merged tree** (amendment 6: a second "CodeGraph (correction)" key, R2, and a column-0 VOCABULARY Correction line, A1) → block 12 rule (9) folds both as I-7 exceptions. The lint must print no R1/R2/R3/R5/A1 line, and a new merge of `origin/master` repeats the check. The lint is a real gate: `/verify-before-done` runs Step 5.6 on every scope. The folds also re-key memory capture candidates (`memory_boundary.py` keys an M/V candidate by `file|tier|title|line`), as the amendment-5 move does: the folded entry's line becomes a Correction line, so its old key is offered once more. Accepted on the same grounds (per-brief receipts, the user clears every item).
- **The bridge meets an older `_project_paths.py`** (amendment 6) → the closed set of names that can be missing is `registry_files` and `registry_files_in` (Uncertain Assumptions). The bridge binds those two with `getattr`; a missing one becomes a stand-in that raises `ImportError` on each call. Every constant and every other name stays a bare read, and none is missing. Outcomes: `accuracy_update.process_journal_change` catches it (empty list); `memory_boundary` refuses `reader-unavailable`; the tracker hook calls the hooks-side helper directly, gets `AttributeError` and now logs `journal-tracker-reader-missing` before it returns (block 12). The registry CLI scripts (`validate_registries`, `cross_area_scan`, `north_star_review`, `generate_registry_digest`, `registry_append`, `registry_migrate`) now stop at their first registry read with a traceback, exit 1. That is NEW behaviour: the default branch's bridge imports beside both helpers, and those scripts ran there. The owner accepted it (2026-11-07) over a root-only fallback. Frozen-helper, CLI and hook rows pin it.
- **The merge-base version row is red until the landing** (amendment 6) → the INV-O1 row of `test_plugin_manifests.py` needs a raised version, and parent mode forbids a sub-task to raise it. The owner accepted it (2026-11-07) as the only expected-red row. **No gate checks it:** `/verify-before-done` treats `.claude/` and `.md` changes as docs-only (`skills/verify-before-done/SKILL.md:26`, Steps 6 and 7), and the landing's four verification steps (`version-bump`, `test_pr_merged.py`, `test_check_hook_registrations.py`, `.claude/hooks/tests`; `work-item-conventions.json` ~88-124) do not include it. The real gates are the registry lint (Step 5.6, every scope) and the hooks-tests folder (which holds `test_codegraph_first_guard.py`), so rule (9) and the bridge fix are required. The real version proof is the landing's own `--raise` then `--exact` (P7b) and its `version-bump` step. Blocks 12 and 14 run the suite by hand so the single red row is on record. A re-run after the landing proves nothing, because the merge base is then the head itself. The rule conflict is general, so it has a follow-up: `.claude/concepts/followups/2026-11-07-inv-o1-parent-branch-conflict.followup.md`.

## Open Questions for User

- [x] **Q1–Q15** → Answered (user, 2026-11-04; wording in round-2 history). Q1 split layout; Q2 `archived-title-only`; Q3 `general` always; Q4 Python gate + stub; Q5 one contract, parent branch; Q6 `[BUG]`; Q7 spec path; Q8 on-disk domains; Q9 full digest, exit 1; Q10 lint in verify-before-done; Q11 `ship` unchanged; Q12 report folder; Q13 issue verbatim; Q14 design-first runs data-architect's appends; Q15 operator marks orphans.
- [ ] **Q16 Legacy entries** — **Recommendation:** keep them verbatim, never converted: read, keyed, indexed and moved like entries (I-8c), so nothing drops out of the digest or the readers. Conversion would rewrite an entry's text (I-7), and the legacy form has no field layout to convert from. Non-blocking; proceeding on this.
- [ ] **Q17 Tracker on a never-seen journal file** — **Recommendation:** accept as an Accepted guard limit. With checkout-independent keys, the limit applies only to a journal file whose main-checkout path this machine has never seen (the first hand edit of a newly created domain file, or a fresh machine), not to worktrees. The alternative fires on every historical entry of a client's split journals. The script path always fires. Non-blocking.
- [ ] **Q18 Moving token-free client entries out of a heading-less root** (new) — **Recommendation:** 0001 reports them as `universal-candidate` and the client procedure tells the operator to add a `## Project: <name>` heading above them on layout 1 and re-run the dry-run. This is the one hand edit the procedure allows (a heading, not an entry). Auto-moving would need 0001 to judge "project vs universal" without tokens and could strip genuine Universal content. Non-blocking.
- [x] **Q19 (amendment 4) False `universal-candidate` advisories on the plugin's own repository (t9 W5)** → Answered (owner, 2026-11-06): (a), skip only that advisory when the project holds the plugin's own manifest, and print one line (wording under R3).
- [x] **Q20 (amendment 4) Append the two lessons the t9 review proposed** → Answered (owner, 2026-11-06): yes, block 10 appends both with `registry_append.py --registry journal --universal`.
- [x] **Q21 (amendment 5) Which shared registry reader survives the merge** → Answered (owner, 2026-11-07): (a), `_registry_layout` stays the only grammar; the default branch's `entry_blocks` and `journal_entries` become adapters on it that return its output shapes, `generate_registry_digest` re-exports them plus `BULLET`, and `memory_boundary` lists files through `registry_files_in` (block 12).
- [x] **Q22 (amendment 5) The default branch's two "CodeGraph (amendment)" entries** → Answered (owner, 2026-11-07): fold the 2026-11-05 entry verbatim as a Correction line under the 2026-10-30 entry (block 12 rule (3); I-7 exception).

---

## Critique

Full critic text of every round is in history: round 1 (6 BLOCKER / 8 WARN / 4 NIT) in `.round-1.md`; round 2 (4 / 8 / 7) in `.round-2.md`; round 3, "Pass 3 (amendment 2)" (3 / 8 / 4), with the rounds-1–2 decision trail and the replaced amendment-2 text, in `.claude/contract-history/2026-11-04-domain-split-registries.round-3.md`. No further critic round runs on blocks 1–9 (user decision). Amendment 4 had its own round (2 / 8 / 4, below), every finding accepted by the owner on 2026-11-06.

- **Rounds 1–2** → addressed by amendments 1 and 2; round 3 verified them, with the gaps carried as B1, W5, W3 (trail: round-3 history, Part B).

- **B1** → Addressed by: Commands "Placement on `pending`/`stale-sync`", `no-universal-tier`, Option H, sub-task 4 tests.
- **B2** → Addressed by: `_plugin_root.separate_plugin_root`, Plugin root resolution VO, sub-tasks 2 and 6 vendored fixtures.
- **B3** → Addressed by: I-14 checkout-equivalent key, Q17, sub-task 4 two-worktree test.
- **W1** → R4 candidate roots, excluded prefixes, expected list. **W2** → `stage_and_replace`. **W3** → `backup_dir`, Commands "Order". **W4** → "Import chain", README file list, stub item 7. **W5** → step 4 field-wise merge. **W6** → Legacy entry (I-8c), Q16. **W7** → `universal-candidate`, Q18. **W8** → I-8b section scope, leftovers last.
- **NITs** → trimmed into history (no token size claimed); tier heading defined; `## Project:` placement removed; I-12 per-instance counting.

### Amendment 4 critique

Moved to `.claude/contract-history/2026-11-04-domain-split-registries.round-4.md` (2 BLOCKER / 8 WARN / 4 NIT, every finding accepted by the owner on 2026-11-06). Moved on 2026-11-07 to bring the contract back under its token budget.

### Amendment 5 critique

Moved to `.claude/contract-history/2026-11-04-domain-split-registries.round-5.md` (1 BLOCKER / 6 WARN / 5 NIT, every finding accepted by the owner on 2026-11-07 and addressed in blocks 12 to 14; the "Addressed by" trail is in that file). Moved to bring the contract back under its token budget.

### Amendment 6 critique

Moved to `.claude/contract-history/2026-11-04-domain-split-registries.round-6.md` (0 BLOCKER / 7 WARN / 6 NIT, every finding accepted by the owner on 2026-11-07 and addressed in block 12, block 14 and the Amendment 6 record; the "Addressed by" trail is in that file).

## Lessons referenced

- **2026-10-04 — A root locator can return the consumer itself under vendoring** — heeded by `separate_plugin_root`, the Plugin root resolution VO and the vendored fixtures.
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — heeded by R4 advisory, the domain-file fallback, `archived-title-only`, the conflict way out, and Q18's heading step.
- **2026-11-01 — A shared reader reused by a stricter consumer must be re-checked …** — heeded by legacy entries staying indexed, the R4 exclusions and expected list, and the default mode left unchanged.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by I-8b section scope, the unseeded-file and two-worktree tracker tests, and the leftover fixtures.
- **2026-10-28 — A new term's definition must be true against every existing member** — heeded by the `absent`/`unknown` definitions and sub-task 1's Add-on wording.
- **2026-11-02 — A sweep … must route EVERY local reader …** — heeded by the reader inventory and the text scan.
- **2026-10-30 — One shared reader must own the filtering** — heeded by `_registry_layout`.
- **2026-10-04 — Detect an install mode by what the sync actually delivers** — heeded by `stale-sync` and the plugin-owned-token rule.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** and **— Locate a script from the plugin root …** — heeded by the lookup block and the widened pin.
- **2026-10-15 / 2026-10-16 — project must be told / both refusal cases** — heeded by the required `--project` and `project-undetermined`.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded: Preview-hash apply and the plugin-root guard are shared by extraction; only the reader and the runner are new.
- **2026-10-17 — Judge "identical to master" by git's view** — heeded by I-12 folding and R6's content hash.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded: every round-3 finding changes the body.
- **Amendment 4:** *2026-10-30 One shared reader must own the filtering* and *2026-11-01 A shared reader reused by a stricter consumer…* are heeded by block 10's W1 (the tracker reads through `rl.parse_text`, and the signatures are pinned on the 41 existing entries). *2026-10-04 A root locator can return the consumer itself under vendoring* is heeded by Q19 (a): only an advisory is dropped. *2026-10-04 A VERIFIED parser claim must be tested on the unfilled and the missing case* is heeded by the fence, path-length, misattached-line and domain-only fixtures, and by the client-shaped signature-parity row with the reader re-seed (critic WARN 2). *2026-10-22 An accepted critic WARN … must amend the contract body* is heeded: each t9 finding and each amendment-4 critique finding changes the body or a block, and the TASK block carries no conditional text. *2026-11-01 A shared reader reused by a stricter consumer…* is also heeded by the default mode ignoring leftovers (critic WARN 6). *2026-10-30 A delivery rule must name every route into delivery* is heeded by naming PR #288's head and the Run-first line (critic WARN 8). The t9 C1 lesson (Q20, appended by block 10) is heeded by block 10 putting `test_registry_layout.py` on its list, widening its pin for the skip line and running all 13 t9 suites.
- **Amendment 5:** *2026-10-30 One shared reader must own the filtering* is heeded by Q21 (a): one grammar, and the default branch's names become adapters. *2026-11-02 A sweep … must route EVERY local reader* is heeded by routing `memory_boundary.py`, a reader the default branch added, through `registry_files_in`. *2026-11-01 After merging a base that changes the row shape a feature reads …* is heeded by block 12's layout-2 round-trip test for the memory adapter and by its rerun of the default branch's suites. *2026-10-15 Reuse the existing brief-linkage reader; a second one misses edge cases* is heeded by keeping the default branch's Source contract rule and its `subs` shape instead of a second reader. *2026-10-30 A delivery rule must name every route into delivery* is heeded by naming the merge route, which is a task branch, a merge commit and a pull request merged with a merge commit, never squash, plus the landing re-run. *2026-10-17 Judge "identical to master" by git's view* is heeded by the `git merge-tree` clean check. The t9 C1 lesson (a sub-task that flips the state an earlier pin reads must re-run that suite) is heeded by block 12 running every t11 suite and every suite the default branch changed.
- **Amendment 5 critique fold (2026-11-07):** *2026-11-03 When resolving a conflict hunk by keeping both sides, drop the base lines the other side rewrote* (default branch, `JOURNAL.md:411`; it arrives with this merge and is not yet in the parent's journal) is heeded by block 12 rule (0) and its Base-line check. *2026-11-01 A shared reader reused by a stricter consumer must be re-checked …* and *2026-10-04 A VERIFIED parser claim must be tested …* are heeded by block 12's Adapter differences D1–D5 and J1–J5 and their fixture rows. *2026-10-22 An accepted critic WARN … must amend the contract body* is heeded by I-7, "Import chain", Failure Modes and rule (4) changing in the body, with no conditional left in blocks 12–14. *2026-11-03 A stop list checked against a moving default branch needs a rule for changes outside the edited lines* (default branch) is heeded by block 14's final live `git merge-tree` check. *2026-11-02 A revision that adds a path adds its failure modes* (default branch) is heeded by the merge-method and moving-branch Failure Modes citing a mechanism. *2026-11-02 Keep a review-fix block to the review's findings* (default branch) is heeded by block 13's TASK line naming the lesson batch as a second, stated purpose. *2026-10-30 A delivery rule must name every route into delivery* is heeded by the merge-method route being checked at block 12's head and at block 13's start.
- **Amendment 6:** *2026-11-05 A bridge re-export that silently falls back to an inline copy must also say which one it gave* is heeded: the stand-in is no inline copy, and the `ImportError` it raises is the one signal callers read, so no new export is needed. *2026-11-05 An "older release" test fixture must be pinned to a fixed commit or a frozen copy, never to HEAD* is heeded in full by the frozen-helper, CLI and hook rows: they read the helper at the fixed commit `643b667`, check it with `git cat-file -e`, and SKIP with a printed reason when it is absent, as the Q-hop rows do. *2026-11-05 A hardening fix applied to a shared classifier must be checked against every consumer* and *2026-11-06 An exception sentence that names the outcome of a later call must list every outcome that call can have* are heeded by the closed name list, the per-name call-site rule, and the INV-O1 exception naming every gate and its outcome (critique fold). *2026-11-06 A sub-task that flips the state an earlier sub-task's test pins must re-run that suite* is heeded by naming the merge-base version row and its exit at the landing. *2026-10-22 An accepted critic WARN or answered Open Question must amend the contract body* is heeded by I-7 and Failure Modes changing in the body.
- Orthogonal to north-stars: none active.

## Amendment 4 record (2026-11-06)

- **Reason:** `.claude/reviews/2026-11-04-domain-split-registries/t9-review-fullstack-code-reviewer.md` returned `**Verdict:** blocked` (range `dca00fd..70c8e6b`) with C1, W1–W5 and N1–N3.
- **C1** (stale pin at `test_registry_layout.py:747`): fixed by draft PR #288 into the parent branch, head `fix/235-pin-current-layout-in-layout-test`. That PR is outside the plan. Its head is not `task/*`, so `check_version_bump.py` does not run in parent mode on it; t11 checks that the range changes no version file. Block 10 declares #288 under **Preconditions**, which is information for the operator only and never a gate (`pr_merged.py` ~line 1175): t10 is released on re-approval whether or not #288 has merged. Block 10's TASK therefore opens with a Run-first line telling the implementer to confirm #288 is merged into the parent branch before starting.
- **W1–W4, N1–N3:** block 10. **W5:** Q19 answered (a) by the owner, 2026-11-06. **Lessons:** Q20 answered yes; block 10 appends both.
- **Body changes:** `stage_and_replace` gains `base` and folder cleanup (W2, N3). The Migration report gains `error`, with mode `refused` and refusal code `plan-build-failed` (N2, critic WARN 4). The plugin-root assumption is marked FALSIFIED (W5). After the amendment-4 critique: R3 gains the `universal-candidate` skip and its line; R4 states a Correction line does not silence it, and the default mode ignores leftovers; I-12 gains the per-entry clause; step 4 treats the heading line as a field; I-14 gains the reader re-seed; "Import chain" makes `accuracy_update`'s import of `_registry_layout` lazy and names both fail-soft hooks; two Failure Modes; Extension Points records `_manifest_names_plugin`; Confidence updated.
- **Critique resolution (owner, 2026-11-06):** both BLOCKERs and all 8 WARNs accepted and addressed (see "→ Addressed by" lines under `### Amendment 4 critique`); each NIT addressed or noted there. N1 now claims only the appended Correction line; R4 keeps listing `MECHANISMS.md:112`.
- **Delivery:** blocks 10 and 11 are sub-tasks into `fix/235-domain-split-registries`, and neither raises the version. Block 10 touches `.claude/registries/MECHANISMS.md` and `.claude/registries/JOURNAL.md`, which count as shipped files. The landing's single minor raise covers them.
- **Ordering:** block 10 depends on 8, not 9, because a `blocked` review releases nothing. Block 11 supersedes the t9 report through its Gate Output, which makes t9 no longer effective.

## Amendment 5 record (2026-11-07)

- **Reason:** the landing run `20261107T114850Z-c28a69` ended `unresolvable-conflict` at gate P7: "`.claude/hooks/journal-post-approval-tracker.py` conflicts and is neither a union path nor regenerated". The script's remedy is to merge the default branch into the parent branch by hand, as a remedy sub-task. `git merge-tree` of `origin/fix/235-domain-split-registries` with `origin/master` (merge base `9a1b452a`, master 153 commits ahead) lists 8 conflicting files: the hook, `MECHANISMS.md`, `VOCABULARY.md`, `generate_registry_digest.py`, `test_plugin_text_scans.py`, `test_skill_script_lookup.py`, `skills/design-first/SKILL.md` and `skills/verify-before-done/SKILL.md`. The landing names only the first conflict it meets.
- **t11 findings:** `pass-with-findings`. W1 (the degraded tracker marks a file seeded) and N2 (README and the migration-runner entry omit `plan-build-failed` from exit 2) go to block 13, and the t11 proposed lesson is appended there. t11 N1 (the C1 pin does not call `--check`) is not taken: t11 judged it equivalent and asked for no action.
- **The reader overlap (Q21):** the default branch's `469f51f` moved the hook onto `generate_registry_digest.journal_entries`. This contract's t4 (`80e151f`) moved the hook's logic into `accuracy_update.process_journal_change`, which t10 put onto `_registry_layout.parse_text`. The parent's thin wrapper survives. The default branch's two readers survive as adapters over `_registry_layout`, and its better Source contract rule becomes `_registry_layout.source_value`.
- **Body changes:** Reused Mechanisms gains Memory adapter. Extension Points gains `source_value` and the two adapters. The Integration Surfaces readers row gains `memory_boundary`. Uncertain Assumptions, Failure Modes, Confidence and Lessons each gain amendment-5 lines. Q19 and Q20 shrink to one line each (budget rule).
- **Version:** no block edits a version file. The merge brings the default branch's manifests in unchanged, so the parent branch's version becomes the default branch's version at the merged commit (0.16.x at draft time). `check_version_bump.py` parent mode then passes for t12 because the head's version equals the one at `merge-base(origin/master, HEAD)`, which is the merged commit (`:166-172`). It passes for t13 and t14 because the head's version equals the base's. The landing then runs `--raise`, which writes minor + 1 with patch 0 relative to `origin/master`'s version at landing time (`exact_version`, `:91-97`), and `--exact` checks it. The parent's old 0.14.5 no longer matters. The registry files that blocks 12 and 13 touch are covered by that single raise.
- **Delivery route:** t12's head is the loop's `task/2026-11-04-domain-split-registries/t12-…` branch, cut from the parent branch. The merge commit of `origin/master` is made on that task branch and enters the parent branch through its pull request. That pull request is merged with a merge commit, never squashed or rebased, because squashing drops the default-branch parent and the landing would conflict again. **The instruction to the owner, in the pull request description ("merge with Create a merge commit"), is the only control:** the repository allows merge commit, squash and rebase, and no tool here judges the method. Block 12 proves its own head before the merge; block 13's Run-first line detects a lost parent after it and stops. `pr_merged` will report t12's merge commit as hand-resolved files (`skills/pr-merged/SKILL.md:255-269`, report, not block); that report is expected. After t14 passes, the landing is re-run with the command block 14's report ends with.
- **Ordering:** block 12 depends on 11 (`pass-with-findings` releases, per `compute_released`). Block 13 depends on 12, because both change `accuracy_update.py`, `MECHANISMS.md` and `JOURNAL.md`, and W1's test must run on the merged tracker. Block 14 depends on 12 and 13 and supersedes t11.
- **Budget:** the contract was already above its 18,000-token budget before this amendment. Before the owner re-approves, the main session moves `### Amendment 4 critique` into `.claude/contract-history/2026-11-04-domain-split-registries.round-4.md` and leaves a one-line pointer. This amendment may write only the contract file, so it does not move it.
- **Critique resolution (owner, 2026-11-07):** the BLOCKER, all 6 WARNs and all 5 NITs accepted and fixed in the body (see the "-> Addressed by" lines under `### Amendment 5 critique`); Q21 answered (a) and Q22 answered (fold), both 2026-11-07. Body changes: I-7 exceptions; "Import chain" (memory adapter); Uncertain Assumptions (Changed-file check, VOCABULARY copies byte-equal); three Failure Modes rewritten or added; block 12 gains rule (0), the Base-line check, the Adapter differences with fixtures, the fail-soft `registry_files_in` test, the head proof and the expected `pr_merged` report, and rule (4) loses its conditional; block 13 gains a Run-first merge-base check and the critique's three lessons; block 14 ends with the live `git merge-tree` check and the landing command. Registry appends stay planned in block 13, which ships under the landing's version raise.

## Amendment 6 record (2026-11-07)

- **Reason:** sub-task 12 (issue 304) stopped `has-issues` on its branch `task/2026-11-04-domain-split-registries/t12-merge-the-default-branch-into-the-parent-branch`. It had already committed the merge of `origin/master` (`28f0b18`, version 0.16.3) as `8558879`, then `5d82089`, `b201dac`, `20d1a80` and `8cfa2c0`. It found three problems block 12 did not cover. The owner answered "amend" to each recommendation (2026-11-07).
- **(1) Lint, verified by re-running `--check-structure --project .` (exit 1):** R2: the default branch added two top-level "CodeGraph (correction)" entries (2026-11-05, issue #259, and 2026-11-06, issue #271; `MECHANISMS.md:119-120` on the t12 branch). A1: it added a column-0 line "Correction (2026-11-06, issue #271):" with no separator (`VOCABULARY.md:146`). That line corrects the Investigation Turn amendment first, then Retry escape and CodeGraph unavailability reason. The fix is block 12 rule (9), with both folds recorded as I-7 exceptions (shaped like Q22).
- **(2) Bridge:** two Q-hop rows of `test_codegraph_first_guard.py`, a test the default branch changed, fail with `AttributeError("module '_project_paths' has no attribute 'registry_files'")`. They copy the current `_claude_paths.py` beside an older `_project_paths.py`, whose bare reads at `:99-100` raise at import. The fix is the bridge constraint of block 12, `_claude_paths.py` and `test_script_path_resolution.py` added to its Files to touch, and a frozen-helper row written red first.
- **(3) Version row:** `test_plugin_manifests.py` (INV-O1, "the version obeys the merge-base rule") requires a tree that differs from its merge base with `origin/master` to carry a higher version, and parent mode (`check_version_bump.py`) requires a sub-task to keep it. Both cannot hold before the landing's raise. No gate runs that suite: `/verify-before-done` treats `.claude/` and `.md` changes as docs-only (`skills/verify-before-done/SKILL.md:26`, Steps 6 and 7), and the landing's verification runs four steps (`version-bump`, `test_pr_merged.py`, `test_check_hook_registrations.py`, all of `.claude/hooks/tests`; `work-item-conventions.json` ~88-124), none of them `test_plugin_manifests.py`. The real blockers are elsewhere: `/verify-before-done` Step 5.6 (the registry lint) runs on every scope, which makes (1) required, and the hooks-tests folder holds `test_codegraph_first_guard.py`, which makes (2) required. The real version proof is the landing's own `--raise` then `--exact` (P7b) and its `version-bump` step. This is an owner-accepted exception: one row is expected red from t12 to the landing, checked by no gate. Blocks 12 and 14 run the suite by hand and record that it is the only red row (191 pass and 1 fail on the head at amendment time). After the landing, the merge base is the head itself, so the row passes trivially and proves nothing; the landing report's raise and exact outcomes are the check. The conflict is structural (every parent-branch sub-task fails the row), so it has a follow-up: `.claude/concepts/followups/2026-11-07-inv-o1-parent-branch-conflict.followup.md` (Issue pending).
- **Moving default branch:** block 12 keeps the re-fetch and the `git merge-tree --write-tree origin/master HEAD` proof. If `origin/master` moves again before the pull request merges, the engineer merges it onto the same branch as a second, ordinary merge commit. Never amend, rebase or force-push.
- **Body changes:** header, I-7, three Failure Modes, Confidence and Lessons. Block 12 gains the Resume constraint, rule (9), the Bridge constraint, two test rows and the expected-red row, and adds two files to its Files to touch. Block 14 gains one check line. No registry append (the lessons heeded already exist). Critique fold: Adjacent Areas (one row), Uncertain Assumptions (one line), Failure Modes (three rewritten), Confidence, Lessons; block 12's Resume, Route, rule (9), Bridge (closed list, call sites, hook event), Base-line check, three test rows, Run exception and Expected report; block 14's CONTEXT line and amendment-6 check. One follow-up stub.
- **Budget:** the contract is over its 18,000-token budget. The caller moves the `### Amendment 6 critique` text to `.claude/contract-history/2026-11-04-domain-split-registries.round-6.md` and leaves a one-line pointer, as for rounds 4 and 5.
- **Critique resolution (owner, 2026-11-07):** all accepted (0 BLOCKER, 7 WARN, 6 NIT); see the "-> Addressed by" lines under `### Amendment 6 critique`.

---

## Implementation Handoff

**Delivery:** parent branch `fix/235-domain-split-registries` (Parent Branch Delivery Rule). No block lists a version file; the landing raises the version once. Every block writes its tests first and watches them fail. Commands in docs are PowerShell-runnable; fixtures carry no project name.

### 1. Reconcile the duplicate vocabulary entries (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/registries/VOCABULARY.md`

**Pre-written TASK block:**
```
TASK: Remove the two duplicate titles from VOCABULARY.md without changing any body text, so every key is unique
before the lint exists.
CONTEXT: concept contract I-7 (the one pre-layout exception); round-2 finding P2-W5.
FILES: as listed.
CONSTRAINTS:
  - "Add-on manifest": delete the top-level 2026-10-31 entry (today line 91). Append, as the last indented line under
    the 2026-10-30 entry (line 79), exactly:
    "  - **Merged duplicate (2026-10-31, `.claude/concepts/2026-10-12-dedupe-claude-config.md`, Revision 3), kept
    verbatim.** Where it says the manifest names \"the kill switches to report\", the entry above and the **Add-on**
    entry govern: no shipped add-on declares one. Text: " + the deleted entry's text after its separator, verbatim.
    The 2026-10-30 entry and the Add-on entry (lines 74-79) stay as they are.
  - "Vendored-asset drift (amendment)" x2: delete both top-level entries (lines 86, 94). Under the base entry
    "Vendored-asset drift" (line 36), after its existing 2026-10-31 Correction (line 37), append in order:
    "  - **Correction (2026-10-30, `.claude/concepts/2026-10-30-angular-tailwind-followups.md`):** " + the line-86
    text after its separator, verbatim; and
    "  - **Correction (2026-11-01, `.claude/concepts/2026-10-31-warn-on-unshipped-hook-rows.md`):** " + the line-94
    text after its separator, verbatim. Confirm each source by grep (`disabled-hook-installed`, `dangling-hook-row`);
    if another contract introduced it, use that path and say so in the PR.
  - Touch nothing else. "Placeholder slot (amendment)" is unique and stays.
  - Check by hand: no bold title appears twice at column 0; each moved body appears exactly once, unchanged.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 2. Extract the shared apply and plugin-root helpers (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/_preview_apply.py`
- `.claude/scripts/_plugin_root.py`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_preview_apply.py`
- `.claude/scripts/tests/test_plugin_root.py`

**Pre-written TASK block:**
```
TASK: Extract _plan_digest and _atomic_write into _preview_apply.py and _separate_plugin_root with its helpers into
_plugin_root.py, unchanged, and import every moved name back in auto_improve_finish_install.py; add the new
stage_and_replace to _preview_apply.py.
CONTEXT: concept contract ("Shared helpers", "Import chain", Plugin root resolution VO, Reused Mechanisms).
FILES: as listed.
CONSTRAINTS:
  - Moved names: _plan_digest, _atomic_write; _separate_plugin_root (exported also as separate_plugin_root),
    _same_dir, _norm, _manifest_names_plugin, _load_json_lenient, _claude_home, _version_key, _cache_roots,
    PLUGIN_NAME. Read :180-394 first; a helper also used elsewhere in finish-install is imported back, never copied.
    _backup_write stays where it is. find_plugin_root is imported from plugin_doctor inside the function only.
  - Both modules: stdlib only at import, no sys mutation, no sys.path change. finish-install behaviour unchanged.
  - stage_and_replace(writes, backup_dir) exactly per the contract steps (a)-(d).
  - Tests: finish-install's names are the moved objects; a clean-process import of each module leaves
    sys.dont_write_bytecode and sys.path unchanged; stage_and_replace: success; staging failure touches no target;
    replace failure on the 2nd of 3 restores the 1st and deletes a created file; backups land only in backup_dir.
    separate_plugin_root: the project's own tree is rejected (vendored fixture: project holds the plugin's template,
    scripts and even a copied manifest; no other candidate -> None); a cache copy with the manifest is returned; an
    override equal to the project -> None.
  - Run: py -3 .claude/scripts/tests/test_preview_apply.py ; py -3 .claude/scripts/tests/test_plugin_root.py ;
    py -3 .claude/scripts/tests/test_auto_improve_finish_install.py ; py -3 .claude/scripts/tests/test_check_version_bump.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 3. Layout spec, shared reader, structure lint and digest (`python-ai-developer`)

**Depends on:** 1, 2

**Files to touch:**
- `.claude/references/registry-layout.md`
- `.claude/hooks/_project_paths.py`
- `.claude/scripts/_claude_paths.py`
- `.claude/scripts/_registry_layout.py`
- `.claude/scripts/validate_registries.py`
- `.claude/scripts/generate_registry_digest.py`
- `.claude/templates/registries/MECHANISMS/general.md`
- `.claude/templates/registries/VOCABULARY/general.md`
- `.claude/templates/registries/JOURNAL/general.md`
- `.claude/scripts/tests/test_registry_layout.py`
- `.claude/scripts/tests/test_script_path_resolution.py`
- `.claude/scripts/tests/fixtures/registry-layout/...`

**Pre-written TASK block:**
```
TASK: Write the layout spec, registry_files(name, domains=None) (+ re-exports of it and checkout_equivalent_path),
_registry_layout (grammars incl. legacy entries, keys, I-8b sections, path_references, layout_state, R1-R6 and A1),
--check-structure [--strict] with advisory mode, the strict digest and the three general.md skeletons.
CONTEXT: concept contract (Entities I-1..I-8c, Value Objects, "Structural lint rules", "Import chain").
FILES: as listed.
CONSTRAINTS:
  - layout_state exactly per I-1. structure_findings takes plugin_keys (None = no resolved plugin root -> R3
    unverified, universal-candidate skipped); validate_registries resolves it via _plugin_root.separate_plugin_root,
    imported lazily. _registry_layout imports neither plugin_doctor nor any CLI script.
  - R4: candidate roots and R4_EXCLUDED_PREFIXES exactly as the contract; advisory unless --strict. Default mode
    keeps its regex and exit code.
  - Digest: drop DOMAINS; tier labels; legacy entries indexed; sources hash; full index always; exit 1 on R1/R2.
  - Spec: every normative part of this contract's Data Shapes in prose, plus "For the sync tool" (gate, exits 0/6/2,
    JSON state, stale-sync, plugin-owned token entries, Universal versus project-owned files).
  - Tests: pass + fail per rule; advisory vs current exits; --strict; every layout state incl. absent and one root
    missing; skeletons pass; CRLF; "--" separator; date tag; fenced sample ignored; `### Tag conventions` section and
    a `## Notes` section with bullets under it are prose, no finding; `## YYYY-MM-DD` and a dated journal bullet are
    legacy entries (keyed, R2 applies, advisory only, in the digest); path_references rejects `?? d/f.txt`,
    `"$CLAUDE_PROJECT_DIR"/.claude/hooks/x.py`, `../a/b.md`, `JOURNAL/frontend.md:33`, accepts `.claude/concepts/x.md`;
    an excluded prefix is skipped; a path present only under the plugin root resolves; domains= keeps general.
  - This repository: --check-structure exits 0 (state pending). Its output is the layout advisory plus R4 advisory
    lines only (expected: the paths listed under R4). Any non-R4 finding -> AMENDMENT, never suppressed; R4 lines
    beyond the expected list are listed in the PR, not an AMENDMENT.
  - Run: py -3 .claude/scripts/tests/test_registry_layout.py ; py -3 .claude/scripts/tests/test_script_path_resolution.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 4. Single write path and journal tracker (`python-ai-developer`)

**Depends on:** 2, 3

**Files to touch:**
- `.claude/scripts/registry_append.py`
- `.claude/scripts/accuracy_update.py`
- `.claude/hooks/journal-post-approval-tracker.py`
- `.claude/scripts/tests/test_registry_append.py`
- `.claude/hooks/tests/test_journal_post_approval_tracker.py`

**Pre-written TASK block:**
```
TASK: Write registry_append.py (Command "Append registry entry") and move the tracker's parse/seen/fire logic into
accuracy_update.process_journal_change(files, fresh=()); the hook becomes a thin wrapper matching every journal file.
CONTEXT: concept contract (Commands, Events I-14, I-5..I-8c).
FILES: as listed.
CONSTRAINTS:
  - Options, domain choice, placement, rejections and exits exactly as Commands; --project required; writes through
    _preview_apply._atomic_write, never a local copy; calls process_journal_change with fresh.
  - Signature stays sha1(date|title). seeded_files keyed by checkout_equivalent_path per I-14, incl. old-cache upgrade.
    Hook exits 0 always (one stderr line if the entry point is missing).
  - Tests: one per rejection (incl. project-undetermined unset and absent, layout-unknown, registries-absent,
    no-universal-tier). current: --universal before the pointer, --domain, area default, general fallback,
    unknown-domain, append lands above the leftovers heading. pending, fixture = root with NO `## Project:` section
    (issue 2.2-B, ends with "See domain-specific files..."): a non-universal entry lands in the existing domain file,
    else in general.md created from the skeleton; the root's bytes are unchanged; an unknown --domain falls back to
    general and is named; --universal lands at the root's Universal end; advisory line; exit 0. stale-sync:
    --universal before the synced pointer; a project entry goes to a domain file. --correction-of;
    --archive-title-only and its refusal on a bodied entry. Tracker: a post-impl divergence entry by script fires
    once, a later hand edit does not re-fire; a hand Edit to a seeded JOURNAL/general.md fires; an unseeded domain
    file with post-* entries is seeded with zero fires; an old cache seeds domain files without firing; a script
    entry in a new domain file fires (fresh); the same journal file edited from two worktrees (paths under
    .claude/worktrees/a/ and /b/) seeds once and a new hand post-* entry fires exactly once; the Accepted guard limit
    (hand entry in a file whose checkout-equivalent path was never seen) is pinned.
  - Run: py -3 .claude/scripts/tests/test_registry_append.py ; py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 5. Script readers through the resolver (`python-ai-developer`)

**Depends on:** 3

**Files to touch:**
- `.claude/scripts/cross_area_scan.py`
- `.claude/scripts/north_star_review.py`
- `.claude/scripts/tests/test_registry_readers.py`

**Pre-written TASK block:**
```
TASK: Route the journal and mechanisms reads of cross_area_scan.py and north_star_review.py through registry_files /
_registry_layout, keeping their scores and output shapes.
CONTEXT: concept contract (Reused Mechanisms, I-3, I-8c).
FILES: as listed.
CONSTRAINTS:
  - journal_repo_root() keeps anchoring on the root file. No union of roots.
  - Tests: an entry only in JOURNAL/frontend.md and one only in MECHANISMS/backend.md are seen by each reader; a
    legacy entry is seen; a flat layout-1 fixture gives the same result as before this change.
  - Run: py -3 .claude/scripts/tests/test_registry_readers.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 6. Migration 0001, layout gate and doctor (`python-ai-developer`)

**Depends on:** 2, 3

**Files to touch:**
- `.claude/scripts/registry_migrate.py`
- `.claude/scripts/registry_migrations/__init__.py`
- `.claude/scripts/registry_migrations/m0001_domain_split.py`
- `.claude/scripts/plugin_doctor.py`
- `.claude/scripts/tests/test_registry_migrate.py`
- `.claude/scripts/tests/test_plugin_doctor.py`
- `.claude/scripts/tests/fixtures/registry-migration/...`

**Pre-written TASK block:**
```
TASK: Write the migration runner, migration 0001 and --check; add the doctor's layout line, body-less journal count,
--json key registry_layout and the three general.md copy requirements.
CONTEXT: concept contract (I-9..I-13, Commands incl. "Order", "Plan hash", "Shared helpers", "Migration 0001"
steps 1-6, Migration leftover block, Plugin root resolution, Registry layout state).
FILES: as listed.
CONSTRAINTS:
  - Uses _preview_apply (_plan_digest, stage_and_replace) and _plugin_root.separate_plugin_root; never imports
    finish-install. Backups only under <report folder>/backup/. plugin_doctor imports _registry_layout lazily and
    reports a missing module by name.
  - Fixtures: (a) the client's state: a heading-less root ending "See domain-specific files...", title-only entries,
    flat-only, split-only, the same bodiless entry in flat and split, a bodiless entry under ## Project:, Tags/source
    contracts that classify, a client-authored token entry, a plugin-owned token entry (fake plugin root with
    manifest), a token-free client-authored Universal entry, a token header line, prose + sub-heading + table under
    ## Project:, a ## YYYY-MM-DD entry and a dated journal bullet under ## Project:, `### Tag conventions`, a fenced
    sample, a journal key with a Lesson-only copy beside a bodied copy; (b) stale-sync; (c) a same-field
    different-text conflict; (d) vendored: no plugin root except the project itself.
  - Tests: dry-run writes nothing; apply with the dry-run hash succeeds; (a) and (b) are `current` after apply; a
    second apply on the still-uncommitted tree exits 0 with an empty plan and equal bytes; --check exits 6 before and
    0 after; I-12 entry and per-instance text checks, incl. a forced plan dropping one prose line ->
    content-loss-detected; leftovers verbatim and last in general.md; legacy entries moved verbatim, not into
    leftovers; removed lines listed by reason; §4.2 order; client token entry moved, plugin-owned one kept,
    universal-candidate listed and kept; (d) -> every token entry unverified and kept, report names the reason; the
    Lesson-only copy's lines appended under the kept entry, nothing lost; orphans listed with a ready-to-run
    --archive-title-only line, not marked; conflicting-entry and uncommitted-registry-changes refuse, write the
    report, leave files byte-identical; changed-since-preview; forced replace failure restores every file and leaves
    no file under .claude/registries/ other than the originals; hash equals _plan_digest over the stated parts;
    project-undetermined unset and absent.
  - Doctor: report-only; --fix never migrates; existing suite green.
  - Run: py -3 .claude/scripts/tests/test_registry_migrate.py ; py -3 .claude/scripts/tests/test_plugin_doctor.py ;
    py -3 .claude/scripts/tests/test_check_version_bump.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 7. Agent, skill and template instructions (`python-ai-developer`)

**Depends on:** 3, 4, 6

**Files to touch:**
- `agents/data-architect.md`
- `agents/contract-critic.md`
- `agents/ui-ux-designer.md`
- `agents/fullstack-code-reviewer.md`
- `agents/registry-scout.md`
- `skills/journal-add/SKILL.md`
- `skills/design-first/SKILL.md`
- `skills/cross-impact/SKILL.md`
- `skills/promote-ui-rule/SKILL.md`
- `skills/verify-before-done/SKILL.md`
- `skills/application-design/SKILL.md`
- `skills/website-design/SKILL.md`
- `skills/validate-registries/SKILL.md`
- `skills/north-star/SKILL.md`
- `.claude/templates/concept-contract.md`
- `.claude/templates/north-star.md`
- `.claude/templates/followup-stub.md`
- `.claude/scripts/tests/test_plugin_text_scans.py`
- `.claude/scripts/tests/test_skill_script_lookup.py`

**Pre-written TASK block:**
```
TASK: Point every §2.2-B writer at registry_append.py and every reader at root + domain files; add design-first's
receiver for data-architect's appends; wire --check-structure into verify-before-done; extend the text scan and the
lookup pin to agents.
CONTEXT: concept contract (Integration Surfaces, Commands, Reused Mechanisms "Script lookup block", Q10, Q11, Q14).
FILES: as listed.
CONSTRAINTS:
  - Writers: fullstack-code-reviewer janitor duties; journal-add; design-first Step 3 (~166) and Step 5 (~323-325,
    346); data-architect append rules. Each runs the lookup block for registry_append.py with
    --project "$CLAUDE_PROJECT_DIR" (plugin-generic entries: --universal) and states: "on a project not yet on
    registry layout 2 it appends to a domain file and prints an advisory line; that is success. Exit 2: fix the entry
    file and re-run. Exit 3: stop and show the message to the user." No hand-Edit instruction for an entry remains.
  - Q14 receiver: design-first gains "Run the data-architect's registry appends", referenced after Step 2 and
    wherever data-architect is re-invoked to promote: for each `Registry appends:` line in a data-architect HANDOFF,
    run it in order through the lookup block, show the printed file:line, stop at the first exit 2 or 3 and show it,
    delete the entry file after success. data-architect writes each entry under .claude/cache/registry-appends/,
    lists the commands under `Registry appends:` and names that section as the step that runs them.
  - Readers: data-architect and contract-critic name MECHANISMS/general.md, VOCABULARY/general.md, JOURNAL/general.md,
    drop the fixed {backend,frontend,data,trading} list, and state the focus rule: root + general.md always; plus each
    domain file named after the contract's derived or adjacent area or focus when it exists; else every domain file.
    design-first :16, :62-63, :137 name root + domain files. ui-ux-designer, application-design, website-design,
    promote-ui-rule search JOURNAL.md and JOURNAL/*.md; cross-impact names the domain files; validate-registries
    describes --check-structure, --strict, R4 advisory and its exclusions, and routes fixes through
    registry_append.py (--correction-of); registry-scout says the generator writes the full index (legacy entries
    included) and exits 1 naming R1/R2 findings; north-star skill and template, concept-contract and followup-stub
    templates drop "project section" / "under <project>" for the domain form.
  - verify-before-done: a step running validate_registries.py --check-structure via the lookup block; exit 1 is
    NOT-READY; exit 0 with advisory lines is not.
  - Leave skills/ship/SKILL.md unchanged (Q11).
  - Text scan: the §2.2-B writers name registry_append.py and the layout-2 fallback sentence; data-architect and
    contract-critic name general.md; data-architect names the receiver section and design-first contains it; no
    shipped agent, skill or template names a flat registry path without the domain form, says "project section", or
    instructs appending to a registry by Edit. Lookup pin: scans agents/*.md as well as skills/**/*.md.
  - Run: py -3 .claude/scripts/tests/test_plugin_text_scans.py ; py -3 .claude/scripts/tests/test_skill_script_lookup.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 8. Plugin registries on layout 2, registry appends and docs (`python-ai-developer`)

**Depends on:** 4, 5, 6, 7

**Files to touch:**
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `.claude/registries/JOURNAL.md`
- `.claude/registries/MECHANISMS/general.md`
- `.claude/registries/VOCABULARY/general.md`
- `.claude/registries/JOURNAL/general.md`
- `README.md`
- `CONTRIBUTING.md`

**Pre-written TASK block:**
```
TASK: Run migration 0001 on this repository (dry-run, then apply with the hash). Then append with registry_append.py
--universal: the seven VOCABULARY terms; MECHANISMS entries "Registry layout reader" and "Registry migration runner";
Correction lines under "Two-tier registry with a generated complete index", "Two-layer Claude path resolution",
"Adaptive Engineering Journal", "Section-scoped registry sync", "Preview-hash apply" (helpers in _preview_apply.py,
stage_and_replace added, second user registry_migrate) and VOCABULARY "Installed plugin root" (the guarded lookup is
_plugin_root.separate_plugin_root). Write the README change note "Domain-split registries (issue #235)" and the client
procedure "Moving a project onto registry layout 2"; update CONTRIBUTING.md's registry-sync paragraph.
CONTEXT: concept contract (Business Concept, New Mechanisms, Reused Mechanisms, "Import chain", Q4, Q15-Q18).
FILES: as listed.
CONSTRAINTS:
  - Never hand-edit a registry entry. Root header prose (e.g. JOURNAL.md:10 "Project sections hold ...") is not an
    entry and is updated by hand to describe layout 2.
  - Expected after the writes: --check exits 0 (current). --check-structure exits 0 and prints R4 advisory lines only
    (any other finding -> AMENDMENT). The digest exits 0.
  - README change note lists every new file a copied-script client must copy with the updated scripts:
    .claude/scripts/_registry_layout.py, _preview_apply.py, _plugin_root.py, registry_append.py, registry_migrate.py,
    registry_migrations/, .claude/references/registry-layout.md, .claude/templates/registries/; and says that
    auto_improve_finish_install.py now imports _preview_apply.py and _plugin_root.py.
  - Client procedure, PowerShell (issue §4.3): commit registry changes; registry_migrate.py --dry-run --project .;
    read registry-migration-report.md (leftovers, plugin-owned and unverified token entries, universal candidates
    and the Q18 heading step, orphans with ready-to-run lines); resolve any conflicting-entry; --apply
    --expect-sha256 <hash>; --check-structure; regenerate the digest; commit (backups sit under
    .claude/cache/registry-migrations/, not in the registries); recover or mark orphans. Say writers keep working
    before migration (domain-file fallback + advisory). Name the refusal codes, stale-sync and the sync-tool follow-up.
  - No version number in the text; no version file edit.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 9. Review (`fullstack-code-reviewer`)

**Depends on:** 8

**Files to touch:**
- `.claude/reviews/2026-11-04-domain-split-registries/t9-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review sub-tasks 1-8 against this contract and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-04-domain-split-registries.md
FILES: .claude/reviews/2026-11-04-domain-split-registries/t9-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check, one line each, every brief acceptance criterion: spec + markers; single write path (the four §2.2-B
    writers, the domain-file fallback that never writes project content into a root, the rejection tests); every
    reader on the resolver, with general.md named; R1-R6 (R4 advisory) + advisory mode + verify-before-done + strict
    digest with tier labels and legacy entries; the tracker fires for any journal file, once across worktrees, with
    no retroactive fires; 0001 dry-run/apply/idempotence/entry and text no-loss on the client, stale-sync and
    vendored fixtures; leftovers; token entries (plugin-owned and unverified kept); the gate exits 6/0 and the
    doctor reports the state; skeletons; the README note, file list and procedure; refusals leave files unchanged
    and write a report.
  - Also check I-1..I-14; the stated deviations (R5 vs registries.domains, A1, R4 advisory, ship unchanged);
    _preview_apply and _plugin_root as the single definitions; no reader still reads one flat file; no sub-task pull
    request changes a version file.
  - Write the six-section artefact. The file does NOT exist yet; you create it. Name the commit range base..head.
  - "## Evidence" lists the commands with their exit codes and is never empty.
  - The header ends with exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings",
    "**Verdict:** blocked".
  - Write the Gate Output <artefact stem>.gate.json beside it, covering every Review checklist item.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 10. Fix the t9 review findings (`python-ai-developer`)

**Depends on:** 8

**Preconditions:** pull-request lneninger/claude-agentic-auto-improve#288

**Files to touch:**
- `.claude/scripts/accuracy_update.py`
- `.claude/hooks/tests/test_journal_post_approval_tracker.py`
- `.claude/hooks/tests/fixtures/journal-signatures-2026-11-06.md`
- `.claude/scripts/_preview_apply.py`
- `.claude/scripts/tests/test_preview_apply.py`
- `.claude/scripts/registry_migrate.py`
- `.claude/scripts/registry_migrations/m0001_domain_split.py`
- `.claude/scripts/tests/test_registry_migrate.py`
- `.claude/scripts/validate_registries.py`
- `.claude/scripts/tests/test_validate_registries_default.py`
- `.claude/scripts/tests/test_registry_layout.py`
- `.claude/references/registry-layout.md`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/JOURNAL.md`

**Pre-written TASK block:**
```
TASK: Fix t9 review findings W1-W4, N1-N3 and W5 (Q19 answer (a)); append the two Q20 lessons. Each fix comes with
  its tests.
CONTEXT: concept contract amendment 4 ("Amendment 4 record", "Shared helpers" incl. "Import chain", R3, R4, I-12,
  I-14, step 4, Migration report VO, Q19, Q20, "Amendment 4 critique"); review
  .claude/reviews/2026-11-04-domain-split-registries/t9-review-fullstack-code-reviewer.md.
FILES: as listed.
CONSTRAINTS:
  - Run first, before any edit: gh pr view 288 --repo lneninger/claude-agentic-auto-improve --json state,mergedAt,baseRefName
    must show state MERGED into fix/235-domain-split-registries. If it does not, stop and report; do not start. The
    Preconditions line is information only (pr_merged.py ~line 1175 never gates on it). Cut this branch from the parent
    branch after that merge. PR #288 (head fix/235-pin-current-layout-in-layout-test) fixed C1; C1 is not re-fixed here.
  - W1: accuracy_update.parse_journal_entries builds its entries from _registry_layout.parse_text(text, "JOURNAL", ...),
    keeping journal entries only (never legacy entries, I-8c; never inside fences, I-8). Delete _ENTRY_HEADER and keep no
    other journal heading regex in this file. The signature stays sha1(date|title), with the title taken exactly as today.
    Import _registry_layout lazily inside parse_journal_entries; on ImportError write one stderr line naming the module
    and return no entries. Module-level imports stay as today ("Import chain").
    I-14 reader re-seed: each seeded_files value records reader 2; a file whose value has no reader is re-seeded once
    on its next read with the new reader (all its signatures marked seen, nothing fires except a fresh one).
    Tests (test_journal_post_approval_tracker.py):
      (a) a dated ### heading inside a fence, added to a seeded file, fires zero times;
      (b) frozen signature pin: create .claude/hooks/tests/fixtures/journal-signatures-2026-11-06.md as a byte copy of
          .claude/registries/JOURNAL.md taken BEFORE this block's Q20 appends (41 entries). The test computes the
          expected set from that fixture with a copy of today's _ENTRY_HEADER held as a test constant, and the actual
          set from the new code on the same fixture; the two are identical and hold 41 signatures. Never read the live
          JOURNAL.md in this test, so this block's appends and later appends never turn it red;
      (c) client parity row: a client-shaped journal whose headings the old and new patterns read differently (at
          least a heading inside a fence, a tab after the date, no space after the separator, a heading the old \s+
          reads across a line break, CRLF line endings), seeded under the old reader (cache value with no reader),
          then read by the new code: zero fires; then one new post-approval heading appended: exactly one fire;
      (d) with _registry_layout hidden (sys.modules entry set to None in a subprocess), critic-verdict-tracker.py and
          contract-status-watcher.py both still import accuracy_update (their _DEPS_OK is true), and
          accuracy_update.record_clean still runs; parse_journal_entries returns no entries and writes one stderr line.
  - W2: stage_and_replace(writes, backup_dir, base=None). Back up to backup_dir / target.relative_to(base). base defaults
    to the common parent folder of the targets. A target outside base returns write-failed before any stage file is
    written. registry_migrate passes the project root. Tests: the backup path equals backup_dir / relative path; a fixture
    nested deep enough that the old absolute-path rule would pass 260 characters while the new path stays under it
    (assert on the computed length, no long-path OS setting needed); a target outside base -> write-failed, every
    target unchanged.
  - N3: remember the folders step (a) created. After a staging failure or a rollback, remove the ones that are empty.
    Test: a new MECHANISMS/ folder made by a failed run is gone afterwards; a folder that existed before stays.
  - W3: per key, _plan_registry records the multiset of input lines of every occurrence, minus that key's merged-duplicate
    removed lines. verify_plan parses each output entry and requires that its line multiset contains that set; otherwise
    content-loss-detected. Both sides are normalised exactly as I-12's text check: line endings folded, BOM dropped,
    trailing spaces trimmed, blank lines ignored. Step 4 treats the heading line as a field, so two copies whose heading
    lines differ refuse conflicting-entry and step 4 never appends a heading line. If the plan still holds two output
    entries with one key, verify_plan refuses conflicting-entry naming both output locations and their first lines. The
    key-set and count checks stay. Tests: a forced plan that moves one body line from one entry to another ->
    content-loss-detected, files byte-identical, report written; the existing merge fixture (the Lesson-only copy
    appended under the bodied one) still passes; a CRLF + BOM + trailing-space client fixture -> no
    content-loss-detected; two copies whose headings differ only in the date -> conflicting-entry, files byte-identical.
  - N2: an exception in build_plan writes the report through Run.finish with mode refused, refusal code
    plan-build-failed, `error` set (exception type and message), every list empty and plan hash `none`, then exits 2
    (Migration report VO; Commands Rejections). No registry file is touched. Test: a forced build_plan exception gives
    exit 2, registry files byte-identical, and a report folder whose report.json has mode refused, refusal code
    plan-build-failed and the error.
  - W4: the default (no-flag) mode iterates registry_files("MECHANISMS.md") and registry_files("VOCABULARY.md")
    (through _claude_paths, same root, I-3) and prints one report block per file. In each file it ignores every line
    from the "## Migration 0001 leftovers (not parsed as entries)" heading on, so leftovers never produce findings.
    The regex, the flags and the exit rule do not change. --json keeps the mechanisms and vocabulary keys with today's
    shape, aggregated over all files, and adds one key "files" (one block per file, registry_files order). Tests (new
    file test_validate_registries_default.py, temp project only): a dead path only in MECHANISMS/backend.md is reported
    under that file and gives exit 1; a flat layout-1 fixture prints the same blocks and the same --json mechanisms and
    vocabulary values as before; a layout-2 fixture with no dead path gives exit 0; a general.md whose leftovers
    section holds a three-backtick run and a dead path gives no finding from the leftover and still reports a dead
    path in an entry above it.
  - W5 (Q19 answer (a)): when _plugin_root._manifest_names_plugin(project) is true, --check-structure drops every R3
    universal-candidate advisory. Only when at least one was dropped it prints exactly one line, ASCII only:
    "advisory: R3 universal-candidate skipped: <N> entries; this project holds the plugin's own manifest"
    (fixed prefix "advisory: R3 universal-candidate skipped"). Token findings, R3 plugin-owned, R3 unverified and every
    other result are unchanged. Document this in registry-layout.md under R3. Tests in test_registry_layout.py: a
    project with the manifest and candidates gets the skip line (N correct) and no candidates; the same project with
    the manifest and no candidates gets no skip line; the same fixture without the manifest still lists the candidates;
    a token-bearing client-authored entry stays a finding with the manifest present.
    In ThisRepositoryTests (as rewritten by PR #288), add "advisory: R3 universal-candidate skipped" to the allowed
    line prefixes, beside "advisory: R4 " and "digest: ". Keep PR #288's assertion that no layout advisory line is
    printed; change nothing else in that test.
  - N1: never edit the entry by hand (I-7). Run registry_append.py --project . --registry mechanisms --correction-of
    "Registry migration runner" --source "t9 review N1" with an entry file whose text names
    .claude/scripts/registry_migrations/__init__.py. Show the printed file:line in the PR. R4 keeps listing the original
    span at MECHANISMS.md:112 (I-7; skills/validate-registries/SKILL.md says the validator keeps listing it); that is
    expected and not a failure.
  - Q20: append the two proposed lessons with registry_append.py --project . --registry journal --universal, Trigger
    "post-impl divergence", Source contract this contract. W5 lesson: the review's text, worded for answer (a) (skip
    only the universal-candidate advisory when the project holds the plugin's own manifest, print one line, never
    downgrade a finding). C1 lesson: the wording under "A second proposed lesson". Show each printed file:line in the PR.
    Take the W1 fixture copy before these appends.
  - Older-test search, one question per change, each with its own grep and its result in the PR: (1) tests asserting
    _ENTRY_HEADER or parse_journal_entries output, or reading the live JOURNAL.md signature set; (2) tests asserting a
    backup path layout or calling stage_and_replace positionally; (3) tests asserting verify_plan messages or the
    report's mode/refusal values; (4) tests asserting the default report's exact text, block count or --json shape;
    (5) tests counting R3 universal-candidate lines on a fixture that holds the manifest; (6) tests that run
    --check-structure on this repository and restrict its output lines, starting with
    .claude/scripts/tests/test_registry_layout.py ThisRepositoryTests; (7) tests or hooks that import accuracy_update
    and depend on its import-time behaviour (at least critic-verdict-tracker.py, contract-status-watcher.py,
    journal-post-approval-tracker.py).
  - Version: no version file. This sub-task PR goes into the parent branch, and the landing raises the version once
    (MECHANISMS.md and JOURNAL.md are shipped registry seeds).
  - Run, all 13 t9 suites plus the new one, every one exit 0 (test_registry_layout.py is on this block's list and is
    rerun after the W5 change; --check-structure on this repository prints only R4, digest: and at most one
    "advisory: R3 universal-candidate skipped" line):
    py -3 .claude/scripts/tests/test_preview_apply.py ; py -3 .claude/scripts/tests/test_plugin_root.py ;
    py -3 .claude/scripts/tests/test_registry_layout.py ; py -3 .claude/scripts/tests/test_script_path_resolution.py ;
    py -3 .claude/scripts/tests/test_registry_append.py ; py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py ;
    py -3 .claude/scripts/tests/test_registry_readers.py ; py -3 .claude/scripts/tests/test_registry_migrate.py ;
    py -3 .claude/scripts/tests/test_plugin_doctor.py ; py -3 .claude/scripts/tests/test_plugin_text_scans.py ;
    py -3 .claude/scripts/tests/test_skill_script_lookup.py ; py -3 .claude/scripts/tests/test_auto_improve_finish_install.py ;
    py -3 .claude/scripts/tests/test_check_version_bump.py ; py -3 .claude/scripts/tests/test_validate_registries_default.py ;
    py -3 .claude/scripts/registry_migrate.py --check --project . ;
    py -3 .claude/scripts/validate_registries.py --check-structure --project .
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 11. Review (`fullstack-code-reviewer`)

**Depends on:** 10

**Files to touch:**
- `.claude/reviews/2026-11-04-domain-split-registries/t11-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Re-review the contract's delivered work after the t9 blocked verdict, and write a superseding review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-04-domain-split-registries.md (amendment 4); blocked report
  .claude/reviews/2026-11-04-domain-split-registries/t9-review-fullstack-code-reviewer.md.
FILES: .claude/reviews/2026-11-04-domain-split-registries/t11-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Header names "Supersedes: .claude/reviews/2026-11-04-domain-split-registries/t9-review-fullstack-code-reviewer.md".
    The Gate Output t11-review-fullstack-code-reviewer.gate.json sets
    "supersedes": ["t9-review-fullstack-code-reviewer.md"] and lists every Review checklist item verbatim.
  - Commit range: dca00fd..<merge commit of sub-task 10>. List the first-parent merges inside it, including
    PR #285 (t9), PR #288 (C1) and sub-task 10's PR.
  - Check, one line each: C1 fixed (test_registry_layout.py exits 0; pin asserts no layout advisory and
    --check exits 0); W1 (no journal heading regex outside _registry_layout; fence test; 41 signatures unchanged);
    W1 also: signature pin reads the frozen fixture, never the live JOURNAL.md; client parity row fires zero;
    accuracy_update imports _registry_layout lazily and both fail-soft hooks still import it;
    W2 (relative backup path; path-length test); W3 (per-entry line containment with I-12 normalisation;
    misattached-line, CRLF and differing-date tests); W4 (default mode reads domain files, ignores leftovers, --json
    adds "files"; tests); W5 per Q19 (a) (skip line only when a candidate was dropped, fixed prefix; ThisRepositoryTests
    allows that prefix and still asserts no layout advisory line); N1 (a Correction line naming
    .claude/scripts/registry_migrations/__init__.py is present under "Registry migration runner", made by
    registry_append --correction-of; R4 still lists the original span at MECHANISMS.md:112, as I-7 requires);
    N2 (mode refused, refusal code plan-build-failed, exit 2); N3; both Q20 lessons appended to JOURNAL.md;
    every t9 "Met" item still holds; no version file changed in the range beyond the test fixture.
  - Re-run every suite in the t9 Evidence table, all 13 including test_registry_layout.py, plus
    test_validate_registries_default.py, and the live commands --check, --dry-run, --check-structure (with and without
    --strict), plugin_doctor --project . (--json too), and check_version_bump.py in parent mode.
  - Write the six-section artefact. The file does NOT exist yet; you create it. "## Evidence" lists every command with
    its exit code and is never empty.
  - The header ends with exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings",
    "**Verdict:** blocked".
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 12. Merge the default branch into the parent branch (`python-ai-developer`)

**Depends on:** 11

**Files to touch:**
- `.claude/hooks/journal-post-approval-tracker.py`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `.claude/registries/JOURNAL.md`
- `.claude/scripts/generate_registry_digest.py`
- `.claude/scripts/_registry_layout.py`
- `.claude/scripts/accuracy_update.py`
- `.claude/scripts/memory_boundary.py`
- `.claude/scripts/_claude_paths.py`
- `.claude/scripts/tests/test_plugin_text_scans.py`
- `.claude/scripts/tests/test_skill_script_lookup.py`
- `.claude/scripts/tests/test_registry_entries.py`
- `.claude/scripts/tests/test_registry_layout.py`
- `.claude/scripts/tests/test_memory_boundary.py`
- `.claude/scripts/tests/test_script_path_resolution.py`
- `skills/design-first/SKILL.md`
- `skills/verify-before-done/SKILL.md`
- `skills/auto-improve-finish-install/SKILL.md`

**Pre-written TASK block:**
```
TASK: Merge origin/master into the parent branch fix/235-domain-split-registries through this sub-task's task branch,
  resolve the 8 conflicting files by the per-file rules below, compose the two shared registry readers per Q21 (a),
  and leave every suite green, so that the re-run landing's merge of the default branch is clean.
CONTEXT: concept contract amendment 5 ("Amendment 5 record", Q21, Q22, Reused Mechanisms "Memory adapter",
  Extension Points, Failure Modes) and amendment 6 ("Amendment 6 record"); the blocked landing run
  20261107T114850Z-c28a69 (gate P7); the t11 review
  .claude/reviews/2026-11-04-domain-split-registries/t11-review-fullstack-code-reviewer.md (its Evidence table).
FILES: as listed. Every other file the merge changes arrives from origin/master through git, not by an edit.
CONSTRAINTS:
  - Resume (amendment 6). The branch task/2026-11-04-domain-split-registries/t12-merge-the-default-branch-into-the-
    parent-branch already holds the merge commit 8558879 (origin/master 28f0b18) and 5d82089, b201dac, 20d1a80 and
    8cfa2c0. Keep them. Make every amendment-6 change as a new commit on top. Never amend, rebase or force-push.
    Run git fetch origin. If origin/master is past the commit you merged, run git merge --no-ff origin/master on
    the same branch: a second, ordinary merge commit, resolved by the per-file rules below, with the full Run list
    re-run after it. Repeat whenever it moves before the pull request merges. Each merge has its own base: before
    that merge, run git merge-base HEAD origin/master and record the commit (for a second merge it is 28f0b18, the
    first merged origin/master commit, or whichever commit it prints). For that merge, rule (0) and the Base-line
    check use that base wherever they say 9a1b452a, and "the parent tip" means HEAD just before that merge. Run them
    per merge commit, each with its own base, and paste each output in the pull request. The head proof, the Route
    line's remerge-diff and the Expected report name every merge commit of origin/master on the branch, and
    git merge-tree --write-tree origin/master HEAD exits 0 on the final head.
  - Route. Done for t12 by 8558879: do not merge again except as the Resume constraint says. This sub-task's head is
    the loop's task branch task/2026-11-04-domain-split-registries/t12-..., cut from
    origin/fix/235-domain-split-registries. The first merge was: git fetch origin ; git merge --no-ff origin/master.
    Resolve, then commit the merge ON THE TASK BRANCH (two parents: the parent-branch tip and the origin/master commit). Put the
    conflict resolutions in the merge commit. Make the Q21 composition and the test changes as separate commits after
    it, so that git show --remerge-diff <merge> shows the resolutions alone. Open the pull request into
    fix/235-domain-split-registries. It must be merged with a merge commit, never squash or rebase (squashing drops
    the origin/master parent and the landing conflicts again). The pull request description's first line says:
    "Owner: merge this pull request with Create a merge commit, never Squash and merge or Rebase and merge." No tool
    enforces the method (the repository allows all three); that sentence is the only control, and block 13's
    Run-first line detects a failure. Never rebase the task branch. Never push to the parent branch directly.
  - Head proof, before opening the pull request, each output in your report and the pull request: for each merge
    commit of origin/master on the branch, git rev-list --parents -n 1 <merge commit> prints three hashes (the commit and its two parents: the parent-branch tip and the
    origin/master commit you merged; name both); git merge-tree --write-tree origin/master HEAD exits 0.
  - Read both sides first: for each conflicting path, git show origin/master:<path> and git show
    origin/fix/235-domain-split-registries:<path>, and git log --oneline 9a1b452a..origin/master -- <path>. In the
    pull request, cite for each file what each side added since 9a1b452a.
  - Per-file rules:
    (0) Base diff first (JOURNAL 2026-11-03, default branch, "When resolving a conflict hunk by keeping both sides,
        drop the base lines the other side rewrote"; it arrives with this merge). Before resolving any path under
        rules (3)-(8), run git diff 9a1b452a origin/master -- <path> and git diff 9a1b452a
        origin/fix/235-domain-split-registries -- <path>. A base line that one side left unchanged and the other side
        deleted or rewrote belongs to the rewrite only: it is not kept. "Keep both", "keep every test from both
        sides" and "united" below mean both sides' ADDED and CHANGED lines, never a base line that either side
        removed. Where both sides rewrote one base line differently, the per-file rule says which text governs.
    (1) .claude/hooks/journal-post-approval-tracker.py: the parent's thin wrapper wins whole (its logic lives in
        accuracy_update.process_journal_change, t4/t10). The default branch's change (469f51f: parse_entries calling
        generate_registry_digest.journal_entries, the _journal_entries binding, the journal-tracker-reader-missing
        log) is superseded as follows. The grammar is _registry_layout's. The Source contract rule moves to
        accuracy_update (see Q21 below). The reader-missing path is accuracy_update's lazy import (block 13 adds the
        log event under the default branch's event name). The merged file contains no regex and no parse_entries.
    (2) .claude/scripts/generate_registry_digest.py: the parent's file wins as the body: the resolver, tier labels,
        legacy entries, the sources hash, exit 1 on R1/R2, no DOMAINS. Re-add only the public names that
        memory_boundary.py binds, entry_blocks, journal_entries and BULLET, as re-exports of the _registry_layout
        adapters (Q21). DOMAINS, tier_split, read and entries are not restored. Their only users on origin/master are
        memory_boundary.py (DOMAINS, re-routed below) and test_registry_entries.py (rewritten below); confirm with
        git grep on the merge before deleting.
    (3) .claude/registries/MECHANISMS.md: the parent's layout-2 shape wins (marker on line 1, the Universal tier, the
        "## Project tier" pointer as the last section, project content in MECHANISMS/general.md). Every entry the
        default branch added since 9a1b452a goes in verbatim at the end of the Universal tier, after "Registry
        migration runner" and its Correction lines, and before the pointer: "Memory adapter" (2026-11-02),
        "CodeGraph (amendment)" (2026-11-05, issue #259), "CodeGraph (correction)" and "Add-on layout (amendment)".
        A Correction line the default branch added under an existing entry stays under that entry. Q22: the
        2026-11-05 "CodeGraph (amendment)" is folded in as the last indented line of the 2026-10-30 "CodeGraph
        (amendment)" entry, exactly "  - **Correction (2026-11-05, issue #259):** " followed by its text after the
        separator, verbatim. No other entry text changes.
    (4) .claude/registries/VOCABULARY.md: the parent's layout-2 shape and block 1's reconciliation win (the
        duplicate "Add-on manifest" and the two "Vendored-asset drift (amendment)" entries stay folded). Delete the
        default branch's copies of those three entries (its VOCABULARY.md:79/86/91/94 at draft time). They are
        byte-equal to the text block 1 kept (verified against a default-branch-derived tree, 2026-11-07). Check it:
        each deleted line's text after its "*(date)* — " separator appears verbatim in the matching kept entry or
        Correction / Merged duplicate line; put the three comparisons in the pull request. A mismatch stops the
        sub-task with AMENDMENT; never reword. The default branch's new terms ("Central
        Memory System" through "Shadow record", 24 entries) go in verbatim at the end of the Universal tier, after
        the seven terms block 8 appended, and before the pointer.
    (5) .claude/registries/JOURNAL.md (auto-merged): check that every entry the default branch added sits above the
        "## Project tier" pointer. Move any that git placed below it to the end of the Universal tier. This is the
        only reordering allowed, and you list it in the pull request.
    (6) .claude/scripts/tests/test_plugin_text_scans.py and test_skill_script_lookup.py: keep every test from both
        sides under rule (0): a test or assertion one side deleted or rewrote is not restored. The parent's scan rules (domain form, registry_append.py, no Edit-append, agents/*.md in the lookup
        pin) apply to every shipped file of the merge, including the ones the default branch added. Where a default
        branch file breaks a parent rule, fix that file, never the rule. Known case:
        skills/auto-improve-finish-install/SKILL.md:290 lists the three root registries the doctor seeds; add their
        <REG>/general.md skeletons (block 6's copy requirements).
    (7) skills/design-first/SKILL.md: keep both under rule (0); a base step or sentence one side rewrote appears
        once, in its rewritten form, never beside it. The default branch's Step 1.5 "Consult the Central Memory System"
        and every memory text, and the parent's "Run the data-architect's registry appends" section (after Step 2)
        and its registry_append.py writer text. Where both changed one sentence about appending a journal or
        registry entry, the parent's text governs the write (registry_append.py, no Edit) and the default branch's
        memory clauses are kept beside it.
    (8) skills/verify-before-done/SKILL.md: keep both steps in numeric order: 5.5, the parent's 5.6 "Registry
        structure lint", then the default branch's 5.8 "The codegraph add-on's settings check". Every other hunk
        is united under rule (0), not chosen: each side's added and changed lines, and no base line either side
        removed or rewrote. Rules (3)-(5) follow rule (0) too: an entry or Correction line either side removed
        from a root (the parent's moves into <REG>/general.md included) is not restored there.
    (9) Amendment 6 folds (I-7 exceptions, like Q22; one commit after the merge, the lines quoted in the pull
        request). MECHANISMS.md: the 2026-11-06 "CodeGraph (correction)" entry (issue #271) becomes the last
        indented line of the 2026-11-05 "CodeGraph (correction)" entry, exactly "  - **Correction (2026-11-06,
        issue #271, `.claude/concepts/2026-11-06-session-folder-owner-and-tool-named.md`):** " followed by its text
        after the separator, verbatim. VOCABULARY.md: the column-0 line "- **Correction (2026-11-06, issue #271):**
        the Investigation Turn amendment now places …" moves to the last indented line of the "Investigation Turn
        (amendment)" entry (2026-11-05). Only its indentation changes: it starts with exactly two spaces,
        "  - **Correction (2026-11-06, issue #271):**", as the M/V Correction form does. Read both lines with git show
        origin/master:<path> first; a text that differs from the t12 branch's copy stops the sub-task with
        AMENDMENT. No other entry text changes.
  - Bridge (amendment 6). .claude/scripts/_claude_paths.py reads registry_files and registry_files_in with getattr,
    as it reads worktree_own_root. When the helper beside it has a name, the bridge re-exports the helper's
    function itself, so case 12's identity pin holds. When it lacks one, the bridge binds a stand-in of that name
    that raises ImportError on every call. The message names the function, the helper's file and the launcher
    check's remedy ("Bring the hooks folder to the same release as the scripts"). Never an inline copy and never a
    root-file-only fallback: block 3 has one resolver, and a root-only list is the "reader keeps reading one flat
    file" failure. The ImportError is the only signal callers read; add no export. Both names stay in __all__.
    Closed list (verified 2026-11-07; Uncertain Assumptions, amendment 6). The only names that can be missing
    beside e4f392c or 643b667 are registry_files and registry_files_in: neither helper defines them, and every
    other name the default branch's bridge reads is present in both (the Q-hop rows import that bridge beside
    both). Stand-ins go to those two functions only. Every other name stays a bare read, exactly as now:
      - checkout_equivalent_path, the third name this contract added to the bridge (_claude_paths.py:101), is
        present in both helpers (VERIFIED 2026-11-07 by `git show <commit>:.claude/hooks/_project_paths.py`:
        `def checkout_equivalent_path` is at line 486 in both e4f392c and 643b667; re-run the check once and put
        its output in the pull request). It gets no stand-in, because journal_file_key calls it outside any try (accuracy_update.py:545,
        the first statement that touches it in process_journal_change), and a stand-in there would turn a degraded
        run into an exception. If the check finds it absent, stop with AMENDMENT.
      - The constants PROJECT_HOOK_LAUNCHER_SOURCE, HOOK_CLASS_BLOCK and HOOK_CLASS_WARN, and the two launcher
        functions, are never missing beside either helper: the launcher-surface check (_claude_paths.py:74-87)
        refuses a helper without them at import with its own ImportError, on purpose. Leave that check and those
        reads unchanged; a constant cannot raise "on call". The frozen-helper row asserts the three constants are
        the helper's own values.
    Call sites of the two names, each outcome beside an older helper:
      - the tracker hook's is_journal calls the hooks-side helper directly (_pp.registry_files, not the bridge;
        journal-post-approval-tracker.py:80-84), so it gets AttributeError, not the stand-in. Today its except
        returns False and the hook exits 0 in silence. Fix (this file is on the list): when that call raises and
        the path's name looks like a journal (JOURNAL.md, or JOURNAL/<x>.md), write one stderr line naming
        registry_files and the helper's file, call log_event(hook="journal-post-approval-tracker",
        event="journal-tracker-reader-missing", ...) (the default branch's event name, as block 13 uses), and
        return False: the edit goes untracked and nothing is seeded. Any other path returns False with no output.
      - accuracy_update.process_journal_change: registry_files is called inside try (:558-561), so the listed
        files are empty; the changed files are still keyed by journal_file_key (checkout_equivalent_path, present).
        It is reached only from the script path (registry_append), because the hook stops at is_journal first.
      - _registry_layout.py:25 imports registry_files_in from the bridge and gets the stand-in; its two calls
        (:568, :596) raise ImportError to their callers. memory_boundary binds _registry_layout.registry_files_in
        through _bind and so receives the stand-in, not None: memory_boundary._registry_files turns an ImportError
        from its lister into Refusal("reader-unavailable", …), and the "lister is None" branch (:503-505) stays
        for a missing module.
      - registry_migrations/m0001_domain_split.py:36 imports registry_files_in and calls it while building the
        plan (_plan_registry, :426), so registry_migrate refuses plan-build-failed, exit 2, with the ImportError
        in the report's error (amendment 4); no registry file is touched.
      - validate_registries, cross_area_scan, north_star_review, generate_registry_digest and registry_append stop
        at their first registry read with an uncaught ImportError: traceback, exit 1, its last line naming the
        function, the helper's file and the remedy. This is NEW behaviour (the default branch's bridge imports
        beside both helpers and those scripts run), accepted by the owner on 2026-11-07 over a root-only
        fallback. cross_area_scan and north_star_review feed the data-architect's Step 4.5 and the critic, so the
        message must name the remedy.
  - Base-line check (BLOCKER fix), for each of the seven united paths (MECHANISMS.md, VOCABULARY.md, JOURNAL.md,
    test_plugin_text_scans.py, test_skill_script_lookup.py, skills/design-first/SKILL.md,
    skills/verify-before-done/SKILL.md): for each side B in {origin/master, the parent tip} and the other side A,
    take the non-blank base lines B removed (the "-" lines of git diff --unified=0 9a1b452a <B> -- <path>). Each
    such line must occur in the merged file no more often than in B's version plus the copies A added beyond the
    base (multiset counts). Write the check as a throwaway script outside the repository (for example under
    $env:TEMP), run it on each merge commit of origin/master with that merge's own base and parent tip (Resume),
    and paste each output in the pull request: zero surviving lines, or each one named with the reason it is also
    present on side B. A surviving line is fixed in that merge commit while it is uncommitted, otherwise in a new
    commit on top (never amend).
  - Q21 (a) composition (not a conflict, but required for a working merge):
    _registry_layout gains source_value(raw), the default branch's _source_value rule unchanged (the rest of the
    line, backticks and padding trimmed; '', none, n/a, na, unknown, tbd and anything starting with "<" read
    empty). It also gains entry_blocks(text, pattern=None, per_domain=False) and journal_entries(text,
    per_domain=False), adapters over parse_text (kind "domain" when per_domain, else "root"; one M/V grammar, so
    pattern is accepted for signature compatibility and not used). They return exactly the default branch's dict
    keys: entry_blocks gives title, line, tier, text and subs (each sub has line and text, with deeper continuation
    folded in); journal_entries gives sig, date, title, line, tier, trigger, source and text, entries of kind
    "entry" only. The tier is "Universal" only when per_domain is false, parse_text's tier is "universal", and a
    "## Universal" heading precedes the entry in its file; otherwise it is "Project" (the default branch's
    fail-closed rule for memory scope). journal_entries' text is the heading line plus every line of the entry,
    as the default branch's is; trigger is fields["trigger"] trimmed and lower-cased (the default branch's rule,
    pinned by JournalEntriesTests: "Pre-Approval Critic" -> "pre-approval critic"); source is
    source_value(fields["source contract"]). entry_blocks returns kind "entry" and kind "legacy" (I-8c: legacy
    entries are returned to readers); journal_entries returns kind "entry" only (malformed ones included).
    Adapter differences from the default branch's functions (read from both: _registry_layout.py:173-190,230-244,
    327-437 and the default branch's generate_registry_digest.py:55-176). These are all of them; each is intended,
    because parse_text is the one grammar, and each gets one fixture row:
      D1 fences: a "- **x**" line inside a fence is not an entry, and a column-0 fence line ends the open entry
         (default branch: an entry, and the fence lines folded into the text).
      D2 I-8b sections: bullets under a "##" heading that is no tier heading ("## Universal...", "## Project:",
         "## Project tier"), no dated heading and not the leftovers heading are prose to the next "#"/"##"
         heading, never entries (default branch: entries, tier unchanged).
      D3 legacy headings: "## YYYY-MM-DD ..." in a mechanism or vocabulary file is a legacy entry (title = text
         after the date and separator; text = its lines to the next heading) (default branch: a heading that
         ends the previous entry, never an entry).
      D4 continuation: an entry continues only on blank lines and lines indented 2+ spaces; a non-blank column-0
         line or a one-space-indented line ends it (default branch: such a line continued the entry when no blank
         line preceded it).
      D5 below the pointer: an entry after "## Project tier" is "Project" (default branch: the tier the last
         "## Universal" set). R3 makes such an entry a finding on current.
      J1 fences: a "### YYYY-MM-DD" heading inside a fence is not an entry; its lines stay in the open entry's text.
      J2 I-8b sections: journal entries under a non-tier "##" heading (e.g. "## Notes") are prose (default branch:
         entries).
      J3 text end: an entry's text ends at the next heading of any level, so a "###" non-entry heading ("### Tag
         conventions") or a "####" sub-heading ends it (default branch: only the next entry header or a "## "
         line).
      J4 separator: a "### YYYY-MM-DD" heading with no separator, or with an en dash, is a (malformed, A1) entry
         (default branch: not an entry; its lines fold into the previous entry's text).
      J5 fields: when an entry has two Trigger or Source contract lines the last wins, and lines indented under a
         field fold into its value (_field_map; default branch: the first line wins, its own line only).
    accuracy_update.parse_journal_entries takes source_contract from rl.source_value(entry.fields
    ["source contract"]) instead of _SOURCE_VALUE, and _SOURCE_VALUE is deleted. memory_boundary._registry_files
    lists files with registry_files_in(<project>/.claude/registries, "<NAME>.md") in resolver order, bound
    fail-soft as _RL = _bind("_registry_layout", "registry_files_in") (never a module-level import). When it is
    None, select_candidates raises Refusal("reader-unavailable", ...) exactly as for missing readers ("Import
    chain", amendment 5). A file under <NAME>/ is per_domain. The is_shipped filter and the fail-soft _bind stay.
    The DOMAINS binding and DEFAULT_DOMAINS go. Moving entries changes the M/V candidate keys (Failure Modes);
    say so in the pull request.
  - Tests:
    test_registry_entries.py: EntryBlocksTests and JournalEntriesTests stay unchanged as the adapters' acceptance
    tests. Add AdapterDifferenceTests: one fixture row per difference D1-D5 and J1-J5 above, each asserting the
    adapter's result (written first and watched fail before the adapters exist), plus a legacy-kind row for
    entry_blocks. TierSplitIsByteIdentical is deleted:
    it pinned the pre-contract digest byte for byte, and this contract's Digest generator replaces that digest
    (test_registry_layout.py's digest tests cover it). Say so in the pull request. HookCallerTests becomes
    AccuracyParserTests, which tests accuracy_update.parse_journal_entries: the same keys; parity of sig, date,
    title and trigger with the default branch's old_parse_entries oracle on
    .claude/hooks/tests/fixtures/journal-signatures-2026-11-06.md (the frozen copy, never the live JOURNAL.md);
    and the "only the listed source forms differ" row, unchanged. The missing-reader row moves to block 13. Delete
    it here, and name test (d) of test_journal_post_approval_tracker.py as its current cover.
    test_registry_layout.py: source_value and both adapters' tier rule (a root entry under "## Universal", a root
    entry before any "##" heading, a domain-file entry).
    test_memory_boundary.py: a layout-2 round trip (JOURNAL 2026-11-01). A temporary project on layout 2 with a
    Universal entry in the root and entries naming the slug in JOURNAL/general.md and MECHANISMS/backend.md. Assert
    that capture-candidates offers the domain-file entries with scope "project" and the root entry as Universal
    before the token rule. A domain file named outside the old DOMAINS list (e.g. JOURNAL/ops.md) is read.
    A hidden-module row: in a subprocess with _registry_layout hidden, import memory_boundary succeeds, a
    retrieval subcommand still runs, and capture-candidates refuses reader-unavailable. Keep every existing row
    green. Amendment 6 adds a stand-in row. With registry_files_in bound to a function that raises ImportError,
    capture-candidates refuses reader-unavailable and a retrieval subcommand still runs.
    test_script_path_resolution.py (amendment 6): add case "registry_files beside an older helper". Read the
    helper text of git show 643b667:.claude/hooks/_project_paths.py (a fixed commit) as the Q-hop precedent does
    (test_codegraph_first_guard.py:2153-2166, 3179-3191): git cat-file -e 643b667^{commit} first; when it fails,
    or git show fails, the row SKIPS and prints the reason (for example "commit 643b667 is not available (shallow
    clone?)"), per JOURNAL 2026-11-05; it never fails on a missing commit and never reads HEAD. Write the text into a
    temporary hooks folder, with a copy of the current _claude_paths.py in a scripts folder beside it, laid out as
    the Q-hop rows do. In a subprocess: import _claude_paths succeeds; registry_files("JOURNAL.md") and
    registry_files_in(<folder>, "JOURNAL.md") each raise ImportError whose message names the function and that
    helper's file; both names are in __all__; checkout_equivalent_path is the helper's own function; and
    PROJECT_HOOK_LAUNCHER_SOURCE, HOOK_CLASS_BLOCK and HOOK_CLASS_WARN equal the helper's values (no stand-in).
    Two more rows share that helper text and its skip: (CLI) copy the current .claude/scripts folder (without
    tests) as the scripts folder and run py -3 validate_registries.py --check-structure --project <temporary
    layout-2 project> there: exit 1, stderr holds no AttributeError, and its last line is the ImportError naming
    registry_files, the helper's file and "Bring the hooks folder to the same release as the scripts". (hook) copy
    the current journal-post-approval-tracker.py and _error_log.py into the hooks folder and run it with an Edit
    payload on <project>/.claude/registries/JOURNAL.md, a temporary home and the log folder redirected as test (d)
    of test_journal_post_approval_tracker.py does: exit 0, one stderr line naming registry_files, one
    journal-tracker-reader-missing event, and no tracker cache file. Write all three first and watch them fail
    (AttributeError at import; the CLI row's last line is an AttributeError; the hook row sees no stderr line and
    no event) before the bridge and hook changes. Then the two Q-hop rows of
    .claude/hooks/tests/test_codegraph_first_guard.py ("Q-hop [0.15.2 helper (e4f392c)]" and "Q-hop [older helper
    (643b667)]: the bridge imports beside that helper") pass, with no edit to that file.
  - Older-test search, one question per change, each with its own grep and its result in the pull request: (1) tests
    or scripts that call grd.tier_split, grd.read, grd.entries, grd.DOMAINS or grd.OUT; (2) tests that read the
    hook's parse_entries or _journal_entries; (3) tests that assert accuracy_update's source_contract for a
    multi-word or N/A source; (4) tests that pin memory_boundary's file list or DOMAINS; (5) tests that run
    --check-structure or --check on this repository and restrict its output (ThisRepositoryTests); (6) tests that
    count registry entries, titles or keys on the live registries.
  - Run, every one exit 0: the 14 suites of the t11 Evidence table
    (py -3 .claude/scripts/tests/test_preview_apply.py ; test_plugin_root.py ; test_registry_layout.py ;
    test_script_path_resolution.py ; test_registry_append.py ; py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py ;
    test_registry_readers.py ; test_registry_migrate.py ; test_plugin_doctor.py ; test_plugin_text_scans.py ;
    test_skill_script_lookup.py ; test_auto_improve_finish_install.py ; test_check_version_bump.py ;
    test_validate_registries_default.py, each under .claude/scripts/tests/ unless named), plus
    py -3 .claude/scripts/tests/test_registry_entries.py ; py -3 .claude/scripts/tests/test_memory_boundary.py, plus
    every test file listed by git diff --name-only 9a1b452a..origin/master -- .claude/scripts/tests .claude/hooks/tests
    (list them with their exits in the pull request), plus py -3 .claude/scripts/tests/test_script_path_resolution.py.
    The one exception (amendment 6, accepted by the owner on 2026-11-07) is
    py -3 .claude/scripts/tests/test_plugin_manifests.py. Run it anyway, by hand: no gate runs it
    (/verify-before-done treats this diff as docs-only; the landing's four verification steps do not include it).
    It exits non-zero with exactly one failing row, printed as "the version obeys the merge-base rule: tree differs
    from the merge base (0.16.3), so all five declarations exceed it" (the version in parentheses is the version at
    git merge-base HEAD origin/master, 0.16.3 at amendment time; it changes with a second merge). At amendment time
    that was 191 pass and 1 fail. The count may change; the single failing row may not. That row needs a raised
    version, and parent mode forbids a sub-task to raise it. Paste the suite's summary and its failing line in the
    pull request, so the exception is on record. Any other red row in that suite is a real failure. The pull
    request description says, in a paragraph of its own: "Expected red, owner-accepted (contract amendment 6):
    test_plugin_manifests.py INV-O1 'the version obeys the merge-base rule' cannot pass on a parent-branch sub-task.
    No gate runs this suite. The version proof is the landing's check_version_bump.py --raise then --exact and its
    version-bump step. The general conflict is tracked by
    .claude/concepts/followups/2026-11-07-inv-o1-parent-branch-conflict.followup.md." The real gates for this diff
    are the registry lint below (verify-before-done Step 5.6) and .claude/hooks/tests (the landing). Live: py -3 .claude/scripts/registry_migrate.py --check
    --project . (exit 0, current); py -3 .claude/scripts/validate_registries.py --check-structure --project . (exit
    0; only R4, digest: and at most one "advisory: R3 universal-candidate skipped" line; any R1, R2, R3, R5, A1 line
    -> stop and report AMENDMENT, never suppressed; after rule (9), none may remain); py -3 .claude/scripts/plugin_doctor.py --project . ;
    py -3 .claude/scripts/generate_registry_digest.py (exit 0); single definitions: git grep -n "def _atomic_write\|def
    _plan_digest\|def _separate_plugin_root" .claude/scripts shows only _preview_apply.py and _plugin_root.py.
  - Clean landing proof: git merge-tree --write-tree --name-only origin/master HEAD exits 0 and lists no conflict.
    Put its output in the pull request.
  - Version: edit no version file. The manifests equal origin/master's at the merged commit (git diff <merged
    origin/master commit> HEAD -- plugin.json .claude-plugin .cursor-plugin is empty). Run py -3
    .claude/scripts/check_version_bump.py --base origin/fix/235-domain-split-registries --default-branch master
    --head-ref <this task branch>: it must exit 0 with "keeps version", because the head's version equals the one at
    merge-base(origin/master, HEAD). The landing raises it once, later.
  - If the Changed-file check (concept_changed_check.py, turn end or --staged), a loop gate or a CI gate rejects a
    file because the merge's changed files exceed this list, stop and report; do not narrow the merge (Uncertain
    Assumptions, amendment 5).
  - Expected report: after this pull request merges, pr_merged reports the merge commit's hand-resolved files
    (skills/pr-merged/SKILL.md:255-269; it reports, it does not block). Say in the pull request that the report is
    expected, and list the files it should name for each merge commit of origin/master on the branch: the files
    resolved or edited in that merge commit (for 8558879: the 8 conflicting files, JOURNAL.md when rule (5) moved an
    entry, and any file rule (6) fixed there; for any later merge, the files it resolved).
  - Registry append: after the merge commit, run registry_append.py --project . --registry mechanisms
    --correction-of "Memory adapter" --source "amendment 5, Q21" with an entry file saying its registry reads go
    through _registry_layout (registry_files_in; entry_blocks and journal_entries adapters re-exported by
    generate_registry_digest). Show the printed file:line.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 13. Fix the t11 review findings (`python-ai-developer`)

**Depends on:** 12

**Files to touch:**
- `.claude/scripts/accuracy_update.py`
- `.claude/hooks/tests/test_journal_post_approval_tracker.py`
- `README.md`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/JOURNAL.md`

**Pre-written TASK block:**
```
TASK: Fix t11 W1 (the degraded tracker must seed nothing), fix t11 N2 (exit 2 also means plan-build-failed) in the
  README and the "Registry migration runner" entry, and, as a second stated purpose, append the amendment-5 lesson
  batch (the t11 lesson, the landing lesson and the three amendment-5 critique lessons).
CONTEXT: concept contract amendment 5 ("Amendment 5 record"), "Import chain", Events I-14; review
  .claude/reviews/2026-11-04-domain-split-registries/t11-review-fullstack-code-reviewer.md (W1, N2, Disposition).
FILES: as listed.
CONSTRAINTS:
  - Run first, from the parent tip, and stop with a report if it fails: git fetch origin ; git merge-base
    origin/master origin/fix/235-domain-split-registries. The printed commit must not be 9a1b452a (9a1b452a means
    sub-task 12's merge reached the parent branch without its origin/master parent: squashed or rebased). Then git
    rev-list --parents -n 1 <t12 merge commit, named in t12's report> prints three hashes, and git merge-base
    --is-ancestor <t12 merge commit> origin/fix/235-domain-split-registries exits 0. Put the outputs in the pull
    request.
  - Cut this branch from the parent branch after sub-task 12's pull request merged (Depends on 12). It runs on the
    merged tracker, which already uses rl.source_value.
  - Why the lessons are here and not in block 12 (default-branch JOURNAL 2026-11-02 "Keep a review-fix block to the
    review's findings"): every journal append of amendment 5 is batched into one block after the merge, so block
    12's merge commit holds only resolutions and its rule (5) move, and the journal changes once. The batch is
    named in the TASK line as a separate purpose; it adds no code change.
  - W1: in accuracy_update.process_journal_change, before _load_seen(), check that _registry_layout can be imported.
    When it cannot: write one stderr line naming the module, log_event(hook="accuracy",
    event="journal-tracker-reader-missing", ...) (the default branch's event name, so log readers keep one name),
    and return [] without reading or writing the cache. Nothing is seeded, nothing fires, a fresh signature included.
    parse_journal_entries keeps its own fail-soft path for other callers.
    Extend test (d) (with _registry_layout hidden in a subprocess, temporary home): (d1) a cache that holds the file
    as seeded under the old reader (value true) is byte-identical after process_journal_change; (d2) with no cache,
    no cache file exists afterwards; (d3) then, in a fresh subprocess with the module present, an unrelated line is
    appended to the journal and the file is processed. Zero fires, and the file is now recorded {"reader": 2}. Keep
    the existing (d) assertions (_DEPS_OK of both hooks, record_clean, one stderr line), and assert the log event.
  - N2: README.md, at the migration procedure's refusal paragraph (t11 cites :1312-1316, re-find it after the
    merge): exit 2 is "a bad argument, or plan-build-failed (an exception while building the plan; the report is
    still written and names the error)". MECHANISMS: run registry_append.py --project . --registry mechanisms
    --correction-of "Registry migration runner" --source "t11 review N2", with an entry file saying that
    plan-build-failed exits 2 and writes the report with error, and that every other refusal exits 3. Never hand-edit
    the entry (I-7). Show the printed file:line.
  - Lessons: run registry_append.py --project . --registry journal --universal for (1) the t11 Disposition's
    "2026-11-07 — A fail-soft reader must not record "seen" for what it could not read", verbatim, and (2)
    "2026-11-07 — A parent branch that shares files with a moving default branch must take the default branch in
    through a sub-task before its landing". Trigger: post-impl divergence. Source contract: this contract.
    Lesson: the landing merges the default branch and resolves only union and regenerated paths. When the default
    branch rewrote a file the parent branch also rewrote (here the journal tracker, moved by each side onto a
    different shared reader), the landing halts. As soon as both sides touch one file, merge the default branch into
    the parent branch through a reviewed sub-task, decide which shared reader survives, and run the default branch's
    new suites there. Apply when: a contract delivered through a parent branch changes a file the default branch has
    changed since the parent branch was cut. Tags: parent-branch, landing, merge, shared-reader,
    unresolvable-conflict. Then, same command, Trigger: pre-approval critic, Source contract: this contract:
    (3) "2026-11-07 — Merge rules written for a long-lived branch must heed the default branch's journal, not only
    the branch's own". Lesson: a lesson the default branch added after the branch was cut is not in the branch's
    journal, yet it arrives with the merge and binds it; read the default branch's JOURNAL.md (git show
    origin/<default>:.claude/registries/JOURNAL.md) before writing conflict-resolution rules. Apply when: a
    contract writes rules for merging the default branch into a parent or other long-lived branch. Tags: merge,
    journal, parent-branch, conflict-resolution.
    (4) "2026-11-07 — No tool enforces how a pull request into a parent branch is merged; the next block must prove
    it". Lesson: the repository allows merge commit, squash and rebase, and the Merge-direction check judges only the
    target. When a sub-task's value depends on a merge commit (a merge of the default branch), say so to the owner
    in its pull request, and open the next block with a check from the parent tip that the default branch's merge
    base moved. Apply when: a sub-task's pull request must be merged with a merge commit. Tags: merge-method,
    parent-branch, squash, run-first.
    (5) "2026-11-07 — Adapters that rebuild an old reader over a stricter grammar must list every behaviour
    difference". Lesson: keeping the old reader's tests as acceptance tests proves only the forms those fixtures
    hold; read both readers side by side, list each form they read differently (fences, prose sections, legacy
    headings, continuation, field repeats), and pin each with a fixture row. Apply when: a contract replaces a
    reader's body with an adapter over another reader and keeps the old names. Tags: adapter, shared-reader,
    behaviour-difference, fixtures. Show each printed file:line.
  - Older-test search, one question per change, each with its own grep and result in the pull request: (1) tests that
    assert the cache after a run with _registry_layout missing; (2) tests that assert exit-2 wording in README or
    MECHANISMS; (3) tests that count journal entries on the live JOURNAL.md.
  - Version: no version file. Parent mode: check_version_bump.py --base origin/fix/235-domain-split-registries
    --default-branch master --head-ref <this task branch> exits 0 (the head's version equals the base's).
  - Run, every one exit 0: py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py ;
    py -3 .claude/scripts/tests/test_registry_entries.py ; py -3 .claude/scripts/tests/test_registry_layout.py ;
    py -3 .claude/scripts/tests/test_registry_append.py ; py -3 .claude/scripts/tests/test_plugin_text_scans.py ;
    py -3 .claude/scripts/validate_registries.py --check-structure --project . (same allowed lines as block 12).
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

### 14. Review (`fullstack-code-reviewer`)

**Depends on:** 12, 13

**Files to touch:**
- `.claude/reviews/2026-11-04-domain-split-registries/t14-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review sub-tasks 12 and 13 (the merge of the default branch and the t11 fixes), and write a review artefact
  that supersedes t11.
CONTEXT: concept contract at .claude/concepts/2026-11-04-domain-split-registries.md (amendments 5 and 6; "Amendment 6
  record" and its critique fold); superseded report
  .claude/reviews/2026-11-04-domain-split-registries/t11-review-fullstack-code-reviewer.md.
FILES: .claude/reviews/2026-11-04-domain-split-registries/t14-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Header names "Supersedes: .claude/reviews/2026-11-04-domain-split-registries/t11-review-fullstack-code-reviewer.md".
    The Gate Output t14-review-fullstack-code-reviewer.gate.json sets
    "supersedes": ["t11-review-fullstack-code-reviewer.md"] and lists every Review checklist item verbatim.
  - Commit range: 43e802c..<merge commit of sub-task 13>. List the first-parent merges inside it (sub-task 12's and
    13's pull requests). Read the merge with git show --remerge-diff <t12 merge commit>, not the full diff against
    the parent branch, which holds all 153 default-branch commits.
  - Check, one line each:
    the t12 merge commit has two parents, one of them an origin/master commit, and its pull request was merged with
    a merge commit (git merge-base origin/master origin/fix/235-domain-split-registries is not 9a1b452a; block
    13's Run-first outputs are in its pull request);
    rule (0) held: the Base-line check output in t12's pull request shows zero surviving base lines (re-run it on
    two of the seven paths, skills/design-first/SKILL.md and MECHANISMS.md);
    the adapters' D1-D5 and J1-J5 rows exist and pass, and memory_boundary binds registry_files_in through _bind
    (hidden-module row passes);
    each of the 8 files follows its per-file rule in block 12 (hook = the parent's wrapper, no regex; digest = the
    parent's body plus the re-exports only; MECHANISMS and VOCABULARY on layout 2 with every default-branch entry
    verbatim above the pointer; Q22 fold exact; JOURNAL entries above the pointer; both skills keep both sides; scans
    keep both sides' tests);
    Q21 (a): one grammar (no dated-heading or bullet regex outside _registry_layout.py and test oracles);
    source_value used by accuracy_update and journal_entries; memory_boundary lists files through registry_files_in
    and reads a domain file outside the old DOMAINS list; EntryBlocksTests and JournalEntriesTests unchanged;
    the TierSplitIsByteIdentical deletion is justified in the pull request;
    t11 W1 fixed (cache byte-identical and nothing seeded when the reader is missing; the later healthy run fires
    zero; the journal-tracker-reader-missing event logged); t11 N2 (README sentence; Correction line under
    "Registry migration runner" made by registry_append); all five 2026-11-07 lessons appended;
    no version file edited by hand; the parent branch's version equals origin/master's at the merged commit;
    check_version_bump.py in parent mode exits 0; every t11 "Met" item still holds;
    amendment 6: rule (9)'s two folds exact; stand-ins only for registry_files and registry_files_in (the closed
    list), checkout_equivalent_path and the launcher constants bare; the frozen-helper, CLI and hook rows and the
    Q-hop rows pass or SKIP with a printed reason (a skip is recorded, never counted as a pass); the tracker hook
    logs journal-tracker-reader-missing; every t12 merge of origin/master read with --remerge-diff, each with its
    own Base-line check output; test_plugin_manifests.py fails exactly one row, the merge-base-rule row. That row
    is the owner-accepted exception, not a finding, and no gate runs the suite. Any other red row is one. Write in
    "## Evidence" that the version proof is the landing's own check_version_bump.py --raise then --exact (P7b) and
    its version-bump verification step, not a re-run of test_plugin_manifests.py after the landing (the merge base
    is then the head itself, so the row passes trivially), and that the operator reads the landing report's raise
    and exact outcomes (each must exit 0, with the raised version minor + 1, patch 0, over origin/master's).
  - Re-run every suite in the t11 Evidence table, plus test_registry_entries.py, test_memory_boundary.py,
    test_plugin_manifests.py (the one expected-red row above) and every
    test file the default branch changed since 9a1b452a, and the live commands --check, --check-structure (with and
    without --strict), the digest generator, plugin_doctor --project . (--json too) and check_version_bump.py in
    parent mode.
  - Last check, run live after every other check: git fetch origin ; git merge-tree --write-tree --name-only
    origin/master origin/fix/235-domain-split-registries. Record origin/master's commit and the exit code. Exit 0
    with no conflicting path: the landing can merge cleanly. Any conflicting path (the default branch moved again
    after t12; the registries and README.md are its busiest files, and the landing has no union paths or
    regenerators, land_contract.py:1028-1040): list each path as a finding and set "**Verdict:** blocked", because
    the landing would halt on it; the remedy is a second, small merge block added by amendment, written like block 12.
  - End "## Evidence" with the exact landing command for the operator, unrun by you: in Claude Code,
    /advance 2026-11-04-domain-split-registries (it launches py -3 .claude/scripts/land_contract.py --contract
    2026-11-04-domain-split-registries --json in the background). The operator re-runs the last check just before
    launching it.
  - Write the six-section artefact. The file does NOT exist yet; you create it. "## Evidence" lists every command with
    its exit code and is never empty.
  - The header ends with exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings",
    "**Verdict:** blocked".
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

`pr_merged.py` fills this list when the contract's work is merged and nothing is pending. Do not tick lines by hand.

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both backend and frontend sides
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
- [ ] `Status` flipped to `implemented`
