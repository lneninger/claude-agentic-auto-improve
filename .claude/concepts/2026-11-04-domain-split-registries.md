# Concept Contract — Domain-split registries and journal (issue #235)

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-04
**Requested by:** user
**Status:** approved
**Work Item Brief:** .claude/work-items/2026-11-04-235-domain-split-registries.md
**Tracking issue:** pending (opened by `/design-first` Step 3.4)
**Budget:** 18,000 tokens (XL contract). Superseded text and every critique round live in `.claude/contract-history/2026-11-04-domain-split-registries.round-{1,2,3}.md`.
**Amendment:** 3 (2026-11-04), the final one. It follows critic round 3 and the user's decision "Amend once more, then I approve" (B1–B3, all WARNs and NITs).

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
| Registry entry | registry; tier (`universal`, `project:<name>` on layout 1, `domain:<slug>`); file; line; title; key; text; tags; source contract; status (`active`, `archived-title-only`, `legacy`) | **I-5** has a body unless `archived-title-only` or `legacy` (body per grammar below). **I-6** keys unique per registry. **I-7** append-only from layout 2 on: an entry is never reordered or rewritten; allowed appends are a new entry, an indented `Correction (<date>, <source>)` line, and an indented `Status: archived-title-only` line under a bodiless entry. Exceptions: sub-task 1's pre-layout reconciliation; header prose and leftover blocks are not entries. **I-8** fenced code blocks are never parsed. **I-8b** non-entry heading: a journal `###` heading not starting with a `YYYY-MM-DD` shape (e.g. `### Tag conventions`), or a `#`/`##` heading that is neither a tier heading nor a legacy dated heading. Its **section** runs to the next heading of the same or higher level, and every line in it is prose: never an entry, never an R1/A1 finding. **I-8c** a legacy entry is keyed (R2 applies), indexed by the digest under its tier, returned to readers, exempt from R1/A1, printed as `advisory: legacy <file>:<line>`, never converted, and never fires the tracker. | its registry |
| Registry migration | number (0001); from; to; plan; plan hash; report | **I-9** dry-run writes nothing under `.claude/registries/`. **I-10** apply writes only when the recomputed plan hash equals `--expect-sha256`. **I-11** idempotent: after a successful apply the tree is `current`; on `current` the plan is empty and exit is 0, checked before any git check (see Commands). **I-12** no loss, checked on the plan before any write. *Entries:* every input (key, text) maps to an output entry with that key holding every input line (merges per step 4), and per registry `occurrences in = kept + moved + merged away`. *Text:* after folding line endings, dropping the BOM and trimming trailing spaces, the multiset of non-blank source lines equals the multiset of non-blank destination lines, minus the lines 0001 adds and plus the removed lines, both **counted per instance** (multiset subtraction). Added lines: marker, pointer section, skeleton header, leftover heading, provenance and fence lines. Removed lines are a closed set, each listed with file:line and reason: `project-heading`; `replaced-sync-section` (the marker and pointer-section lines a stale sync delivered; on `stale-sync`, "project content" starts after the pointer section, so these lines are counted once); `merged-duplicate` (a line of a duplicate copy that also appears verbatim in the kept copy). Mismatch → `content-loss-detected`, nothing written. **I-13** a refusal leaves every registry file byte-identical and still writes the report. | plugin (code); project (result) |

### Value Objects

| Name | Fields | Invariants | Used as |
|------|--------|------------|---------|
| M/V entry grammar | `- **<title>**` at column 0, optional `*(<date>)*`, separator (`—` written; `—`, `--`, `-` read), body; continuation = following lines indented 2+ spaces until the next column-0 `- **` or a heading; forms `  - **Correction (<date>, <source>):** …`, `  - **Status:** archived-title-only` | title non-empty; body = text after the separator plus continuation, excluding `Status:` lines | parser input |
| Journal entry grammar | `### YYYY-MM-DD <sep> <title>` (the tracker's `ENTRY_HEADER` separators); fields Trigger, Source contract, Lesson, Apply when, Tags; optional Areas, Status | **text** = every line after the heading up to the next heading; "has a body" (R1, I-5) = an `Apply when:` field with text (§3.4) | parser input |
| Legacy entry grammar | `## YYYY-MM-DD <sep> <title>` plus lines to the next heading; or, in a journal file outside any entry, a column-0 `- ` line whose text starts with a `YYYY-MM-DD` date, plus its indented continuation | title = text after the date and separator | parser input (I-8c) |
| Path reference | one backticked span | made only of letters, digits, `_ - . / \`; contains `/` or `\`; ends in `.<1-8 letters or digits>`; does not start with `/`, `./` or `../`. So `` `?? d/f.txt` ``, `` `"$CLAUDE_PROJECT_DIR"/…` ``, `` `../website-design/references/foundation.md` `` and any `file:line` span are not references (file:line citations are not checked; Non-Goals) | `_registry_layout.path_references`, R4 |
| Migration leftover block | source file; line range; reason (`project-prose`, `non-entry-heading`); verbatim lines | under the one `## Migration 0001 leftovers (not parsed as entries)` heading, which is the **last** section of `<REG>/general.md` (an I-8b section: the whole section is prose); one `<!-- leftover from <file>:<a>-<b>, <reason> -->` line, then a fence longer than any backtick run inside; content byte-equal to source after folding | 0001 output; lint prints `advisory: leftover <file>:<line>` |
| Structure finding | rule id; file; line; key; message; remedy; severity (`finding`, `advisory`) | rule id R1–R6 or A1; file and line always set; key empty only for R4–R6 | lint, digest, migration report |
| Migration report | number; project; mode (`dry-run`, `apply`, `refused`); refusal code; plan hash; plugin root used or `unverified` + reason; per registry: kept, moved (key, from, to, reason), merged duplicates, appended merge lines, bodiless orphans (hint + ready-to-run `--archive-title-only` line), unclassified, token entries moved, plugin-owned token entries, unverified token entries, universal candidates, unmovable token lines, legacy entries, leftovers, removed lines, conflicts (key, locations, differing field, each version's first line), counts | refusal code empty unless `refused`; every list present, possibly empty; plan hash in every mode | `registry-migration-report.md` + `report.json` in `<project>/.claude/cache/registry-migrations/0001-<UTC>/`, JSON on stdout |
| Registry layout state | state; found marker (value or `none`); layout current (2); reasons; remedy | marker `none` for `pending`/`absent`; reasons non-empty for `stale-sync`/`unknown`; remedy `registry_migrate.py --dry-run` (pending, stale-sync), `plugin_doctor.py --fix` (absent, registry-missing), else "make the root markers agree, then re-run `--check`" | `layout_state`, `--check`, doctor, lint mode, `registry_append.py` |
| Plugin root resolution | path or none; reason (`same-as-project`, `no-manifest`, `not-found`) | resolved only by `_plugin_root.separate_plugin_root(project, plugin_root, needs=<all three root registries exist>)`; never the project's own tree; none → every token entry is `unverified` and stays | 0001 step 2, R3, R4 candidate roots |

### Structural lint rules (validate_registries.py --check-structure [--project] [--strict]), issue §3.4 order

- **R1 bodiless-entry** — a journal entry without `Apply when:` text; *addition:* an M/V entry with an empty body. `archived-title-only`, legacy entries and I-8b sections are exempt.
- **R2 duplicate-title** — a key present more than once across root and domain files; every location reported.
- **R3 project-entry-above-pointer** — in a root: a `## Project:` heading, or an entry or leftover below the pointer. Plus, when `.claude/.project-tokens.json` lists tokens, a token-bearing Universal entry (case-insensitive, `allowed` honoured) that is **client-authored** (key absent from the resolved plugin root's Universal tier). A hit in a plugin-owned entry is advisory `R3 plugin-owned`. With no resolved plugin root, every hit is advisory `R3 unverified`. Client-authored Universal entries without a token are advisory `R3 universal-candidate`.
- **R4 dead-file-reference — ADVISORY.** Each Path reference in a registry file (fences and leftovers skipped) is resolved against the **candidate roots**: the project root (the folder holding `.claude/`), then the resolved plugin root when there is one. A reference whose path starts with an **excluded prefix** is skipped: `.claude/settings.json`, `.claude/settings.local.json`, `.claude/.sync-config.json`, `.claude/.sync-state/`, `.claude/hook-registration-profile.json`, `.claude/.scout-cache/`, `.claude/cache/`, `.claude/logs/`, `.codegraph/` (consumer-only or generated; the closed list lives in `_registry_layout` and the spec). Others resolving under no candidate print `advisory: R4 <file>:<line> <path>`; exit unchanged except under `--strict`. Expected on this repository: the retired-contract citations (`2026-10-12-dedupe-claude-config.md`, `2026-10-07-worktree-isolation-by-default.md`), `tools/sync-plugin.cmd`, `tools/sync-plugin.ps1`, `python/scalping_strategy_rl/…`, `tests/integration/conftest.py`. Reported, never rewritten (I-7). The default (non-structure) mode keeps its regex and exit code.
- **R5 domain-file-invalid** — deliberate deviation from §3.1.2/§3.4: on-disk discovery, no `registries.domains` slot (Q8). Fires on `general.md` missing, a non-slug name, a nested folder, an `INTEGRATION/` folder; applies when a domain folder exists or the state is `current`/`stale-sync`.
- **R6 digest-stale** — the digest records `<!-- registry-sources-sha256: <hex> -->` over every file it reads (registry files + `INTEGRATION.md` when present, sorted path, normalised bytes). Fires when the digest exists and the line is missing or differs, or a registry key (legacy included) is absent from it. Absent digest prints `digest: absent`.
- **A1 malformed-entry** — *addition beyond §3.4.* Journal: a `###` heading starting with a `YYYY-MM-DD` shape that has an invalid date, no separator, a missing required field, or a Trigger outside {`pre-approval critic`, `post-approval`, `post-impl divergence`, `manual`}. M/V: a column-0 `- **title**` with no separator. Legacy entries are not A1.
- **Mode (§7):** not `current` → every finding is advisory, plus `advisory: registry layout <state> — <remedy>`, exit 0. On `current`: exit 1 on any R1, R2, R3 (non-advisory), R5, R6 or A1 finding (R4 too under `--strict`), else 0. Exit 2 = could not check (including a missing new module, named).
- **Digest generator:** no hard-coded `DOMAINS`; reads through the resolver; tier labels (`Universal`, `project:<name>`, `domain:<slug>`); always writes the complete index (legacy entries included, as `DATED` indexes them today), the INTEGRATION section and the sources hash; exits 1 naming each R1/R2 finding (Q9).

### Events

| Name | Emitter | Listeners | Payload |
|------|---------|-----------|---------|
| Journal entry appended | `registry_append.py` (calls the listener directly, passing the new signature as `fresh`) or an Edit/Write on any journal file (`post-edit-dispatcher.py` → tracker) | `accuracy_update.process_journal_change(files, fresh=())` → `record_failure(area, contract, "post-approval-journal")` for `post-*` triggers | **I-14** signature stays `sha1(date + "\|" + title)`. The machine-wide seen cache gains `seeded_files`, keyed by `checkout_equivalent_path(resolved path)` (`MECHANISMS.md:43`; case-folded on Windows), so a file seeded in one checkout is seeded in every worktree of it. Each file of `registry_files("JOURNAL.md")` whose key is not seeded is seeded first (signatures marked seen, nothing fires); new signatures in seeded files fire, plus any `fresh` one. An old cache (`_initialized`, no `seeded_files`) counts as having seeded the root `JOURNAL.md` key only. Nothing fires retroactively or twice. **Accepted guard limit** (pinned by a test, Q17): a hand-written `post-*` entry in a journal file whose checkout-equivalent path this machine's cache has never seen does not fire; the script path does. |
| Registry layout migrated | `registry_migrate.py --apply` | operator, doctor | Migration report |

### Commands

| Name | Handler | Payload | Rejections (closed set; exit) |
|------|---------|---------|------------------------|
| Append registry entry | `registry_append.py` | `--project` (required), `--registry mechanisms\|vocabulary\|journal`, `--from-file <entry.md\|->`, then `--universal`, or `--domain <slug>` [`--create-domain`], or neither. **Domain choice** (non-`--universal`): `--domain` when that file exists (or `--create-domain`), else the source contract's area via `derive_area` when that file exists, else `general`; the choice is printed. **Placement on `current`:** `--universal` → end of the Universal tier, before the pointer; else end of the domain file's entries, before the leftovers heading when present. **Placement on `pending`/`stale-sync`:** a non-`--universal` entry goes to the domain file chosen as above, with `general.md` created from the skeleton when missing (an unknown `--domain` without `--create-domain` falls back to `general`, named in the advisory); it is **never** written into a root file. `--universal` → end of the root's Universal tier (before a synced pointer, else before the first `## Project:`, else end of file). Both print `advisory: registry layout <state> — appended to <file>:<line>; run registry_migrate.py --dry-run`, exit 0. Writes via `_atomic_write`; prints `file:line`. | `bodiless-input`, `duplicate-entry` (root + all domain files), `malformed-input`, `unknown-domain` (`current` only), `no-universal-tier` (`--universal` and the root holds no title heading and no entry above its first tier heading), `correction-target-missing`, `archive-target-missing`, `archive-target-has-body` (2); `layout-unknown`, `registries-absent`, `project-undetermined`, `write-failed` (3) |
| Check registry structure | `validate_registries.py --check-structure [--project] [--strict]` | — | 0 / 1 / 2 per Mode |
| Check layout | `registry_migrate.py --check --project <root>` | — | prints the layout state as JSON; 0 `current`/`absent`; 6 `pending`/`stale-sync`; 2 `unknown` or unreadable |
| Preview / apply migration | `registry_migrate.py --dry-run` / `--apply --expect-sha256 <h>`; `--project` required; `--plugin-root <path>` optional, passed to `separate_plugin_root` as its override (rejected when it is the project or names another plugin → `unverified`) | **Order:** (1) arguments and project; (2) layout state — on `current` with an empty plan, print the report and exit 0; (3) `not-a-git-tree`, then `uncommitted-registry-changes` (git status of `.claude/registries/` only); (4) plan, I-12, hash compare (apply); (5) stage and replace. Dry-run runs (1)–(4). | `project-undetermined` (unset or absent), `not-a-git-tree`, `uncommitted-registry-changes`, `conflicting-entry`, `unknown-layout`, `changed-since-preview`, `content-loss-detected`, `symlink-target`, `write-failed` (3); bad arguments 2 |

**Plan hash:** `_plan_digest` over `b"registry-migration"`, `b"0001"`, then per file to write in sorted POSIX relative-path order: path, input bytes or `absent`, planned output bytes. The report is outside the plan.

**Shared helpers.**
- `_preview_apply.py` — `_plan_digest` and `_atomic_write` **extracted unchanged** from `auto_improve_finish_install.py` (finish-install imports them back; `_backup_write` stays in finish-install, unused here). **New code:** `stage_and_replace(writes, backup_dir)`: (a) write every planned output to `.<name>.stage-<pid>` beside its target; any failure deletes all stage files and returns `write-failed` with no target touched; (b) copy every existing target into `backup_dir/<relative path>`; (c) `os.replace` each stage file onto its target in plan order; (d) on a replace failure, restore every already-replaced target from `backup_dir` (delete targets that did not exist), delete the remaining stage files, return `write-failed`. 0001's `backup_dir` = `<report folder>/backup/`, never under `.claude/registries/`.
- `_plugin_root.py` — `_separate_plugin_root` (`auto_improve_finish_install.py:347-377`) and the helpers it calls (`_same_dir`, `_norm`, `_manifest_names_plugin`, `_load_json_lenient`, `_claude_home`, `_version_key`, `_cache_roots`, `PLUGIN_NAME`) **extracted unchanged**, exported as `separate_plugin_root`; its "own copy" candidate is this module's tree (same folder as before). `find_plugin_root` is imported from `plugin_doctor` inside the function only. Finish-install imports every moved name back (one definition each).
- **Import chain (kept minimal):** `_preview_apply` and `_plugin_root` import the standard library only and change no `sys` state at import. `_registry_layout` imports the standard library and `_claude_paths`. Finish-install hard-imports `_preview_apply` and `_plugin_root`. `plugin_doctor` and `validate_registries --check-structure` import the new modules lazily and, on `ImportError`, report the missing module by name (doctor: one line, other checks unaffected; lint: exit 2). The tracker hook exits 0 with one stderr line if the new `accuracy_update` entry point is missing.

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
   - a field present in both copies with different text → refuse `conflicting-entry`, naming every location, the field and each version's first line. **Way out:** on layout 1, keep one version, rename one title, or fold one version into a `Correction` line; commit; re-run the dry-run.
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
- **Script lookup block** (`skills/verify-before-done/SKILL.md` Step 1) — reused verbatim for `registry_append.py` and `validate_registries.py` in every skill and in `agents/fullstack-code-reviewer.md`, always with `--project "$CLAUDE_PROJECT_DIR"`; `test_skill_script_lookup.py` widens its scan to `agents/*.md`.

## New Mechanisms (if any)

- **Registry layout reader** (`.claude/scripts/_registry_layout.py`) — sole owner of the marker, grammars, keys, path references, I-8b/I-8c, layout state and R1–R6/A1. **Why not existing:** the grammar exists twice with different rules (digest `BULLET`/`DATED`, tracker `ENTRY_HEADER`), neither knows bodies, keys or fences, and `_project_paths.py` must stay a fail-soft locator (JOURNAL 2026-10-30 "One shared reader must own the filtering"). **Promote:** yes.
- **Registry migration runner** (`.claude/scripts/registry_migrate.py` + `registry_migrations/`) — numbered, previewed, idempotent migrations and the layout gate. **Why not existing:** no migration framework exists; the doctor pins "never write an existing file"; finish-install owns the profile and settings files. **Seam:** migration N+1 = one module + one list entry. **Promote:** yes.

---

## Extension Points

- `_project_paths.registry_files`; `_claude_paths` re-exports `registry_files`, `checkout_equivalent_path`.
- `_registry_layout`: `LAYOUT_CURRENT = 2`, `MARKER`, `REGISTRIES`, `R4_EXCLUDED_PREFIXES`, `parse_entries`, `entry_key`, `path_references`, `layout_state`, `structure_findings(…, plugin_keys=None)`.
- `_preview_apply`: `_plan_digest`, `_atomic_write`, `stage_and_replace`. `_plugin_root`: `separate_plugin_root`.
- `validate_registries.py --check-structure [--strict]`; `accuracy_update.process_journal_change(files, fresh=())` (the hook becomes a thin wrapper whose `is_journal` matches any `registry_files("JOURNAL.md")` file at call time).
- `plugin_doctor.REQUIREMENTS` + report lines + `--json` key; `registry_migrations/__init__.py` list, `m0001_domain_split.py`.
- `skills/verify-before-done/SKILL.md` step running `--check-structure` (exit 1 NOT-READY; exit 0 with advisories is not); `skills/design-first/SKILL.md` section "Run the data-architect's registry appends" (Q14); `.claude/references/registry-layout.md` § "For the sync tool".

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| tracker hook, `registry_append.py` | `accuracy_update.py` | in-process call | changed journal files, `fresh` signatures | hook/script → script |
| readers: `validate_registries`, `generate_registry_digest`, `cross_area_scan`, `north_star_review`, `accuracy_update`, `plugin_doctor`, tracker hook; 5 agents (incl. `registry-scout`); 9 skills; 3 templates | `_registry_layout` / `registry_files` | import / documented read order | Registry entry | reader → resolver |
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

Confidence: Medium-High. High on what exists (amendment 3 re-read `_separate_plugin_root` and its helpers `:284-377`, `_atomic_write` `:380-394`, `checkout_equivalent_path` `_project_paths.py:486`, and the `.gitignore` entry for `.claude/cache/`). Medium on multi-file rollback on Windows and on M/V header bullets parsing (Uncertain Assumptions). Full rationale: round-3 history, Part C.

## Alternatives Considered & Why Rejected

- **A (chosen):** marker + state, shared reader, single writer with a domain-file fallback, §3.4 lint with R4 advisory, numbered migration with leftovers; sync tool via follow-up.
- **B** revert to flat (the split holds content the flat copy lacks). **C** `registries.domains` slot (Q8). **D** hand edits + lint afterwards. **E** finish-install subcommand (two owners). **F** R4 failing on `current` (red forever under I-7). **G** writer refusing on unmigrated layouts (no write path). **H** writer falling back to the flat root (puts project content into the plugin-owned tier; round-3 B1).

## Uncertain Assumptions

- `VERIFIED via .claude/registries/*.md`: flat registries, no `## Project:` heading, no domain folder, 41 unique journal titles; `JOURNAL.md:28` `### Tag conventions` outside a fence; VOCABULARY duplicates at `:79/:91` and `:86/:94`. This repository's `.project-tokens.json` `tokens` list is empty.
- `VERIFIED via auto_improve_finish_install.py:94,284-394`: `_SCRIPTS_DIR`, `_norm`, `_same_dir`, `_manifest_names_plugin`, `_cache_roots`, `_separate_plugin_root`, `_atomic_write`; callers of `_separate_plugin_root` at `:474,1735,2403` keep working through the import-back.
- `VERIFIED via _project_paths.py:486`: `checkout_equivalent_path` strips `.claude/worktrees/<name>/` segments.
- `ASSUMED`: on this repository `separate_plugin_root` returns none (the project is the plugin tree) unless a cache copy exists, so R3/R4 use the project root only; tokens are empty, so nothing moves. `ASSUMED`: M/V header bullets parse as the digest's `BULLET` reads them today. Verification for both: sub-task 3 runs `--check-structure`; any non-R4 finding is reported as AMENDMENT, never suppressed.

## Failure Modes & Mitigations

- **A reader keeps reading one flat file** → every reader uses `registry_files`; sub-task 7's text scan fails on any shipped agent, skill or template naming a flat path without the domain form or saying "project section".
- **The strict parser drops forms the old regexes read** → legacy entries (I-8c), I-8b sections, leftovers, text-level I-12; fixtures cover separators, date tags, CRLF, `## YYYY-MM-DD`, bullet journals, prose under `## Project:`, `### Tag conventions`, this repository's registries.
- **The writer misfiles project entries on unmigrated clients** → the fallback writes only domain files; the root is written only for `--universal`.
- **A vendored client's tree is taken for the plugin** → `separate_plugin_root`; none → `unverified`, nothing moved.
- **The tracker fires retroactively, or misses entries in worktrees** → `seeded_files` keyed checkout-independently; tests for both.
- **A token entry moved by 0001 comes back with the next sync** → plugin-owned entries never move; R3 advisory; follow-up stub.
- **The migration half-writes** → stage all, back up outside the registries, replace, restore on failure (`write-failed`).
- **The lint is red on unmigrated clients, legacy titles or historical paths** → advisory mode until `current`, R4 advisory, `archived-title-only`.
- **Stale sync** (marker above `## Project:` sections) → `stale-sync`, `--check` exits 6, 0001 migrates.
- **A copied-script client lacks the new modules** → import chain kept minimal (above); the README change note (sub-task 8) and the follow-up stub (item 7) list every new file to copy.
- **The reference client's 266 orphans keep verify-before-done NOT-READY** → by design (§4.3 step 5); one ready-to-run `--archive-title-only` line per orphan.
- **The gate reads the plugin's own registries under a plugin install** → `--project` required; `project-undetermined`.

## Open Questions for User

- [x] **Q1–Q15** → Answered (user, 2026-11-04; wording in round-2 history). Q1 split layout; Q2 `archived-title-only`; Q3 `general` always; Q4 Python gate + stub; Q5 one contract, parent branch; Q6 `[BUG]`; Q7 spec path; Q8 on-disk domains; Q9 full digest, exit 1; Q10 lint in verify-before-done; Q11 `ship` unchanged; Q12 report folder; Q13 issue verbatim; Q14 design-first runs data-architect's appends; Q15 operator marks orphans.
- [ ] **Q16 Legacy entries** — **Recommendation:** keep them verbatim, never converted: read, keyed, indexed and moved like entries (I-8c), so nothing drops out of the digest or the readers. Conversion would rewrite an entry's text (I-7), and the legacy form has no field layout to convert from. Non-blocking; proceeding on this.
- [ ] **Q17 Tracker on a never-seen journal file** — **Recommendation:** accept as an Accepted guard limit. With checkout-independent keys, the limit applies only to a journal file whose main-checkout path this machine has never seen (the first hand edit of a newly created domain file, or a fresh machine), not to worktrees. The alternative fires on every historical entry of a client's split journals. The script path always fires. Non-blocking.
- [ ] **Q18 Moving token-free client entries out of a heading-less root** (new) — **Recommendation:** 0001 reports them as `universal-candidate` and the client procedure tells the operator to add a `## Project: <name>` heading above them on layout 1 and re-run the dry-run. This is the one hand edit the procedure allows (a heading, not an entry). Auto-moving would need 0001 to judge "project vs universal" without tokens and could strip genuine Universal content. Non-blocking.

---

## Critique

Full critic text of every round is in history: round 1 (6 BLOCKER / 8 WARN / 4 NIT) in `.round-1.md`; round 2 (4 / 8 / 7) in `.round-2.md`; round 3, "Pass 3 (amendment 2)" (3 / 8 / 4), with the rounds-1–2 decision trail and the replaced amendment-2 text, in `.claude/contract-history/2026-11-04-domain-split-registries.round-3.md`. No further critic round runs (user decision).

- **Rounds 1–2** → addressed by amendments 1 and 2; round 3 verified them, with the gaps carried as B1, W5, W3 (trail: round-3 history, Part B).

- **B1** → Addressed by: Commands "Placement on `pending`/`stale-sync`", `no-universal-tier`, Option H, sub-task 4 tests.
- **B2** → Addressed by: `_plugin_root.separate_plugin_root`, Plugin root resolution VO, sub-tasks 2 and 6 vendored fixtures.
- **B3** → Addressed by: I-14 checkout-equivalent key, Q17, sub-task 4 two-worktree test.
- **W1** → R4 candidate roots, excluded prefixes, expected list. **W2** → `stage_and_replace`. **W3** → `backup_dir`, Commands "Order". **W4** → "Import chain", README file list, stub item 7. **W5** → step 4 field-wise merge. **W6** → Legacy entry (I-8c), Q16. **W7** → `universal-candidate`, Q18. **W8** → I-8b section scope, leftovers last.
- **NITs** → trimmed into history (no token size claimed); tier heading defined; `## Project:` placement removed; I-12 per-instance counting.

---

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
- Orthogonal to north-stars: none active.

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
