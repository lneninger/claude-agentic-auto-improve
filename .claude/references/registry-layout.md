# Registry layout

The normative description of how a project's three registries (mechanisms, vocabulary, journal) are laid out on disk, how the plugin's tools read and write them, and how the sync tool must treat them. The code that implements the reading side is `.claude/scripts/_registry_layout.py`; when the two disagree, fix the one that is wrong and say so in the pull request.

Contract: `.claude/concepts/2026-11-04-domain-split-registries.md` (issue 235).

## 1. Terms

- **Registry layout** is the numbered shape of one project's three registries. Layout 1 is flat: each root file (`MECHANISMS.md`, `VOCABULARY.md`, `JOURNAL.md`) holds a Universal tier and one `## Project: <name>` section per project. Layout 2 is split: each root holds only the Universal tier and a fixed pointer, and project content lives in domain files beside it.
- **Root file**: `.claude/registries/<REGISTRY>.md`. **Domain file**: `.claude/registries/<REGISTRY>/<domain>.md`, a lowercase slug (`[a-z0-9]` words joined by single hyphens). The domain file `general.md` always exists under layout 2. The domain set is whatever `.md` files are on disk; no profile slot lists it.
- **Registry entry key**: the entry title with its date tag removed, lowercased and with runs of whitespace collapsed to one space. Two entries with one key in one registry are a duplicate.
- **Legacy registry entry**: an entry in a pre-grammar form (section 5.3). It is read, keyed and indexed like any entry and never converted.
- **Registry migration**: a numbered, idempotent change from layout N to N+1, previewed first and applied only against the previewed hash. **Migration leftover**: source text a migration could not parse into an entry, kept verbatim in a fenced block (section 8).
- **Tier heading**: `## Project: <name>` (layout 1), `## Project tier` (the pointer), or a `## Universal...` heading. Text above the first tier heading is Universal.

## 2. The marker

A layout-2 root file carries `<!-- registry-layout: 2 -->` as its **line 1**. A marker on any other line does not count. The marker alone never proves layout 2: the state (section 3) also checks the content.

## 3. Layout state (I-1)

The state is computed over the three root files in one resolved `.claude/registries/` folder:

| State | Condition |
|-------|-----------|
| `absent` | none of the three root files exists |
| `unknown` | one or two root files are missing (reason `registry-missing:<NAME>`), or a marker has a value other than `2`, or some roots are marked and others are not |
| `pending` | all three exist and none is marked |
| `current` | all three are marked on line 1, no root holds a `## Project:` heading or any entry or leftover below its pointer, and every `<REGISTRY>/general.md` exists |
| `stale-sync` | all three are marked but a `current` condition fails |

`stale-sync` is what a sync that delivered new roots over a tree still holding project sections produces: the marker and pointer arrive, the project content stays above or below them.

The state as data has these fields: `state`, `marker` (the value found, or `none`), `layout_current` (2), `reasons` (non-empty for `stale-sync` and `unknown`), and `remedy`. The remedy is `registry_migrate.py --dry-run` for `pending` and `stale-sync`, `plugin_doctor.py --fix` for `absent` and `registry-missing`, and for the other `unknown` causes "make the root markers agree, then re-run `--check`". The state is not a delivery-layout value.

## 4. Files

### 4.1 Roots (I-2)

The last section of a layout-2 root is the fixed pointer `## Project tier`. It names `<REGISTRY>/<domain>.md`, says that `general.md` always exists and that every `.md` file in the folder is read, and lists no domain. It is generic text, so the sync can deliver it. The reader exposes it as `pointer_section(registry)`.

### 4.2 Domain files (I-3, I-4)

- Domain files are resolved from the SAME `.claude` root as the root file, never from a union of roots. `registry_files(name, domains=None)` (in `.claude/hooks/_project_paths.py`, re-exported by `.claude/scripts/_claude_paths.py` together with `checkout_equivalent_path`) returns the root file, then `general.md`, then the other domain files alphabetically; only files that exist; `domains` restricts the domain files and always keeps `general`.
- Domain files are project-owned and never synced.
- `INTEGRATION.md` is outside the layout. It has no domain folder. The digest indexes it and the digest hash (R6) covers it when present.

## 5. Entries

### 5.1 Mechanism and vocabulary entries

`- **<title>**` at column 0, then an optional date tag `*(<date>)*`, then a separator, then the body. The separator is written as an em dash; an em dash, `--` or a hyphen followed by whitespace is read. The body is the text after the separator plus the continuation: the following lines indented two or more spaces, up to the next column-0 `- **` bullet or a heading. Two indented forms are special: `  - **Correction (<date>, <source>):** ...` and `  - **Status:** archived-title-only`. The `Status:` line is not part of the body. The title must be non-empty.

### 5.2 Journal entries

A third-level heading `### YYYY-MM-DD <separator> <title>`, with the separators `—`, `--` and `-` (the same ones the journal tracker accepts), then the fields `Trigger`, `Source contract`, `Lesson`, `Apply when` and `Tags` as bold-label bullets, and optionally `Areas` and `Status`. The entry text is every line after the heading up to the next heading. An entry **has a body** when its `Apply when:` field has text. `Trigger` is one of `pre-approval critic`, `post-approval`, `post-impl divergence`, `manual`.

### 5.3 Legacy entries (I-8c)

- A second-level heading `## YYYY-MM-DD <separator> <title>` plus the lines up to the next heading, or
- in a journal file, outside any entry, a column-0 `- ` line whose text starts with a `YYYY-MM-DD` date, plus its indented continuation.

The title is the text after the date and the separator. A legacy entry is keyed (R2 applies), indexed by the digest under its tier, returned to readers, exempt from R1 and A1, printed as `advisory: legacy <file>:<line>`, never converted, and never fires the journal tracker.

### 5.4 Invariants

- **I-5** An entry has a body unless it is `archived-title-only` or legacy.
- **I-6** Keys are unique per registry, across the root and every domain file.
- **I-7** From layout 2 on a registry is append-only: an entry is never reordered or rewritten. The allowed appends are a new entry, an indented `Correction (<date>, <source>)` line, and an indented `Status: archived-title-only` line under a bodiless entry. Header prose and leftover blocks are not entries. The one exception is the reconciliation done before the layout existed.
- **I-8** Fenced code blocks are never parsed. A fence closes only on a fence of the same character that is at least as long, so a longer fence can hold a shorter one.
- **I-8b** A non-entry heading is a journal `###` heading that does not start with a `YYYY-MM-DD` shape (for example `### Tag conventions`), or a `#` or `##` heading that is neither a tier heading nor a legacy dated heading. Its **section** runs to the next heading of the same or a higher level, and every line in it is prose: never an entry, never an R1 or A1 finding. The level-1 file title is the one exception: it opens no section, so entries of a domain file may follow it directly.

### 5.5 Entry as data

An entry has: registry; tier (`universal`, `project:<name>` on layout 1, `domain:<slug>`); file; line; title; key; text; tags; source contract; status (`active`, `archived-title-only`, `legacy`).

## 6. Path references (R4)

A **path reference** is one backticked span made only of letters, digits and `_ - . / \`, that contains `/` or `\`, ends in `.<1 to 8 letters or digits>`, and does not start with `/`, `./` or `../`. So `` `?? d/f.txt` ``, `` `"$CLAUDE_PROJECT_DIR"/.claude/hooks/x.py` ``, `` `../a/b.md` `` and any `file:line` span are not references; `file:line` citations are not checked.

Each reference in a registry file (fenced blocks and leftover sections skipped) is resolved against the **candidate roots**: the project root (the folder holding `.claude/`), then the resolved plugin root when there is one. A reference whose path starts with an **excluded prefix** is skipped, because it is consumer-only or generated:

`.claude/settings.json`, `.claude/settings.local.json`, `.claude/.sync-config.json`, `.claude/.sync-state/`, `.claude/hook-registration-profile.json`, `.claude/.scout-cache/`, `.claude/cache/`, `.claude/logs/`, `.codegraph/`.

The closed list is `R4_EXCLUDED_PREFIXES` in `_registry_layout.py`. A reference that resolves under no candidate root is reported, never rewritten (I-7).

## 7. The structure lint

`py -3 .claude/scripts/validate_registries.py --check-structure --project "$CLAUDE_PROJECT_DIR" [--strict] [--plugin-root <path>]`

| Rule | Meaning |
|------|---------|
| R1 bodiless-entry | a journal entry without `Apply when:` text; a mechanism or vocabulary entry with an empty body. `archived-title-only`, legacy entries and I-8b sections are exempt |
| R2 duplicate-title | a key present more than once across the root and domain files of one registry; every location is reported |
| R3 project-entry-above-pointer | in a root: a `## Project:` heading, or an entry or leftover below the pointer. Also, when `.claude/.project-tokens.json` lists tokens, a token-bearing Universal entry (case-insensitive; every `allowed` string removed first) that is client-authored, meaning its key is absent from the resolved plugin root's Universal tier. A hit in a plugin-owned entry is advisory (`R3 plugin-owned`). With no resolved plugin root every token hit is advisory (`R3 unverified`). A client-authored Universal entry without a token is advisory (`R3 universal-candidate`) |
| R4 dead-file-reference | advisory: a path reference (section 6) that resolves nowhere |
| R5 domain-file-invalid | `general.md` missing; a domain file name that is not a slug; a nested folder in a domain folder; an `INTEGRATION/` folder. Applies when a domain folder exists or the state is `current` or `stale-sync`. Domain files are discovered on disk (there is no `registries.domains` slot) |
| R6 digest-stale | the digest `.claude/.scout-cache/registry-digest.md` exists and its `<!-- registry-sources-sha256: <hex> -->` line is missing or differs, or a registry key (legacy included) is absent from it. The hash covers every registry file plus `INTEGRATION.md` when present, in sorted relative-path order, over bytes with the byte order mark dropped and line endings folded to LF. An absent digest prints `digest: absent` |
| A1 malformed-entry | journal: a `###` heading starting with a `YYYY-MM-DD` shape that has an invalid date, no separator, a missing required field, or a Trigger outside the four values. Mechanism or vocabulary: a column-0 `- **title**` with no separator. Legacy entries are not A1 |

**Mode.** When the state is not `current`, every finding is advisory and one line `advisory: registry layout <state> — <remedy>` is printed first; the exit code is 0. On `current`, the exit code is 1 on any R1, R2, R3 (non-advisory), R5, R6 or A1 finding, and also on R4 under `--strict`; otherwise 0. Exit 2 means the check could not run, including a missing new module, which is named. The default mode of `validate_registries.py` (no `--check-structure`) keeps its own regex and exit code.

Lines are `finding: <rule> <file>:<line> ...` or `advisory: <rule> <file>:<line> ...`, plus `advisory: legacy <file>:<line>` for each legacy entry and `advisory: leftover <file>:<line>` for each leftover block.

## 8. Migration

Migration `0001` moves a layout-1 or `stale-sync` tree to layout 2. It is run by `registry_migrate.py`:

- `--dry-run` previews, writes nothing under `.claude/registries/` (I-9) and prints the plan hash.
- `--apply --expect-sha256 <hash>` writes only when the recomputed plan hash equals the previewed one (I-10).
- It is idempotent: after a successful apply the tree is `current`, and on `current` the plan is empty and the exit is 0, checked before any git check (I-11).
- It loses nothing and invents nothing (I-12). Entries: every input (key, text) maps to an output entry with that key holding every input line. Text: after folding line endings, dropping the byte order mark and trimming trailing spaces, the multiset of non-blank source lines equals the multiset of non-blank destination lines, minus the lines 0001 adds (marker, pointer section, skeleton header, leftover heading, provenance and fence lines) and plus the lines it removes, both counted per instance. Removed lines are a closed set, each listed with file, line and reason: `project-heading`, `replaced-sync-section`, `merged-duplicate`. A mismatch stops with `content-loss-detected` and nothing is written.
- A refusal leaves every registry file byte-identical and still writes the report (I-13).
- Project content includes client-authored project-token entries found in the Universal tier. Plugin-owned entries never move.

A **migration leftover** block sits under the single `## Migration 0001 leftovers (not parsed as entries)` heading, which is the last section of `<REGISTRY>/general.md` and an I-8b section: one `<!-- leftover from <file>:<a>-<b>, <reason> -->` line (reason `project-prose` or `non-entry-heading`), then a fence longer than any backtick run inside, with content equal to the source after line-ending folding. It is inert: never parsed, never a finding.

The report is written as `registry-migration-report.md` and `report.json` under `.claude/cache/registry-migrations/0001-<UTC>/`, and the JSON is printed. The plan hash is `_plan_digest` over `b"registry-migration"`, `b"0001"`, then per file to write in sorted POSIX relative-path order: the path, the input bytes or `absent`, and the planned output bytes. The report is outside the plan.

## 9. Writing entries

All writes go through `registry_append.py --project <root> --registry mechanisms|vocabulary|journal --from-file <entry.md|->`, then `--universal`, or `--domain <slug>` [`--create-domain`], or neither. On `current`, a Universal entry goes to the end of the Universal tier before the pointer, and any other entry to the end of the chosen domain file, above the leftovers section. On `pending` and `stale-sync`, a non-Universal entry goes to a domain file (`general.md` is created from the skeleton when missing) and is **never** written into a root; a Universal entry goes to the end of the root's Universal tier. Both print `advisory: registry layout <state> — appended to <file>:<line>; run registry_migrate.py --dry-run`. The domain is `--domain` when that file exists, else the source contract's area when that file exists, else `general`.

The skeletons for the three `general.md` files ship in `.claude/templates/registries/<REGISTRY>/general.md`.

## 10. Journal tracker

A journal entry appended by the script, or by an Edit or Write on any journal file, may fire the accuracy tracker for `post-*` triggers. The signature stays `sha1(date + "|" + title)`. The machine-wide seen cache keeps `seeded_files`, keyed by `checkout_equivalent_path` of the resolved path, so a file seeded in one checkout is seeded in every worktree of it. A file not yet seeded is seeded first (its signatures are marked seen and nothing fires); new signatures in seeded files fire. Nothing fires retroactively or twice. **Accepted guard limit:** a hand-written `post-*` entry in a journal file whose checkout-equivalent path this machine has never seen does not fire; the script path does.

## 11. Plugin root resolution

The plugin root (for R3 Universal keys, R4 candidate roots and the migration's token rule) is resolved only by `_plugin_root.separate_plugin_root(project, plugin_root, needs=<all three root registries exist>)`. It never returns the project's own tree and requires this plugin's manifest. When it returns none, every token entry is `unverified` and stays where it is.

## 12. For the sync tool

The sync tool (a separate program that copies plugin files into a project and back) must treat the layout as follows.

**Gate.** Before it publishes or pulls registry files, run `py -3 .claude/scripts/registry_migrate.py --check --project <root>`. It prints the layout state as JSON, for example `{"state": "pending", "marker": "none", "layout_current": 2, "reasons": [], "remedy": "registry_migrate.py --dry-run"}`.

| Exit | State | The sync tool must |
|------|-------|--------------------|
| 0 | `current` or `absent` | go on (`absent`: the doctor creates the files) |
| 6 | `pending` or `stale-sync` | halt, show the `remedy`, and not write any registry root; the operator runs the migration |
| 2 | `unknown`, or the check could not run | halt and show the `reasons` |

A tool that cannot run the check (an old copy without `registry_migrate.py`) must treat that as exit 2.

**Cross-layout publishing.** Never publish a layout-1 root over a layout-2 root, or the reverse. Record the applied layout only after a run that ended in `current`.

**Stale sync.** A sync that delivers a layout-2 root over a tree that still holds `## Project:` sections produces `stale-sync`. The tool should treat that as a failed run to repair (run the migration), not as a clean sync.

**Universal versus project-owned files.** The root files `MECHANISMS.md`, `VOCABULARY.md` and `JOURNAL.md` are whole-file Universal content plus the pointer: the sync owns them under layout 2. Everything under `.claude/registries/<REGISTRY>/` is project-owned and is never read, written, compared or deleted by the sync. The skeleton files under `.claude/templates/registries/` are plugin files and sync like any template.

**Plugin-owned token entries.** When the project-token check (the outbound scan for names listed in `.claude/.project-tokens.json`) hits a Universal entry that the plugin itself owns, moving it into a domain file does not help: the next sync restores it. The migration therefore leaves such entries in place and reports them (`plugin-owned-token-entry`); the lint reports them as `advisory: R3 plugin-owned`. The fix belongs in the plugin's copy of the entry. The sync tool should not loop on them.

**New files.** The sync tool's file lists must include the new modules: `_registry_layout.py`, `_preview_apply.py`, `_plugin_root.py`, `registry_migrate.py`, the `registry_migrations/` folder, `registry_append.py`, and the three skeleton templates.
