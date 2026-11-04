# Superseded critique round 2 and amendment-1 text — 2026-11-04-domain-split-registries

Moved out of `.claude/concepts/2026-11-04-domain-split-registries.md` on 2026-11-04 by `data-architect` (amendment 2), per the budget rule in `.claude/templates/concept-contract.md`. Part A is critic round 2 ("Pass 2 (amendment 1)"), unchanged. Part B is every passage of the amendment-1 body that amendment 2 replaced, unchanged, so the decision trail survives (the contract was never committed, so git holds no earlier copy). The live contract keeps one `→ Addressed by` line per finding.

---

## Part A — Pass 2 (amendment 1)

**Critic:** contract-critic (fresh context)
**Date:** 2026-11-04
**Verdict:** blockers-found

#### Pass-1 BLOCKER verification (checked against the contract body and the repository, not the Addressed-by text)

- **P1-B1 (S1–S6 vs §3.4)** — fixed. R1–R6 follow §3.4 in order. A1 is labelled as an addition, the marker is out of the lint, the R5 deviation is stated under R5, in Option C and in Non-Goals, and tier labels are in the digest generator.
- **P1-B2 (writer list)** — fixed. The writers are exactly those of §2.2-B. `skills/design-first/SKILL.md:166,323-325,346` match the cited lines. `skills/ship/SKILL.md` has no registry text.
- **P1-B3 (reader sweep)** — fixed. A grep of `agents/`, `skills/` and `.claude/templates/` for flat registry names or "project section" finds 15 files, and all 15 are in sub-task 6.
- **P1-B4 (plugin registries break the lint)** — partly fixed. Sub-task 1's TASK text matches the real lines: `VOCABULARY.md:79/91` "Add-on manifest", `:86/94` "Vendored-asset drift (amendment)", base entry `:36` and its Correction `:37`. That resolves R2. The underlying defect is still there: the repository's registries still fail the new lint with no sanctioned way out, through R4 (BLOCKER P2-1) and possibly A1/R1 (WARN P2-W7). The "zero findings" claim is false.
- **P1-B5 (lookup block)** — partly fixed. The skills are covered. The reviewer agent's block is claimed to be pinned but is not (WARN P2-W6).
- **P1-B6 (stale-sync)** — fixed. Stale-sync is covered by I-1, the FM, fixture (b) and `--check` exit 6. `absent` is still undefined (WARN P2-W3).

#### Findings

- **[BLOCKER] P2-1: R4 makes this repository and every migrated client permanently red, and nothing allowed can clear it**
  - **What is wrong:** R4 reuses `validate_registries.py`'s `BACKTICK_PATH` (`:56`, slash filter `:170`). The dead references in this repository's registries are not old-check-only noise:
    - `VOCABULARY.md:33,37,56-65,87-92` and `MECHANISMS.md:16,44,47-48,59-60,68-70` cite `.claude/concepts/2026-10-12-dedupe-claude-config.md` and `2026-10-07-worktree-isolation-by-default.md`, which exist nowhere in the worktree (25 occurrences).
    - `MECHANISMS.md:50` cites `tools/sync-plugin.cmd`, and there is no `tools/` folder.
    - `MECHANISMS.md:36` cites `python/scalping_strategy_rl/tests/integration/test_d3rlpy_api_pinned.py`.
    - `JOURNAL.md:204` holds `` `?? d/f.txt` `` and `:309` holds `` `"$CLAUDE_PROJECT_DIR"/.claude/hooks/x.py` ``.

    I-7 forbids rewriting an entry, and a `Correction` line cannot remove a path from the original body. So sub-task 2's "this repository's registries give zero findings" and sub-task 7's "--check-structure exits 0" cannot be reached. Once the repository is `current`, verify-before-done is NOT-READY for good. The same synced Universal tier reaches every client, which cannot edit it. Uncertain Assumptions puts the R4 risk on "every journal entry here" only.
  - **Prior artifact ignored:** JOURNAL.md 2026-10-30 "A rule that refuses must give already-delivered work a named way out"; JOURNAL.md 2026-11-01 "A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for" (the journal was never scanned before)
  - **Where in this contract:** `## Uncertain Assumptions` — "`ASSUMED`: every journal entry here passes A1 and R4"; `### 7.` — "After the writes: --check exits 0, --check-structure exits 0"
- **[BLOCKER] P2-2: Clients that have not migrated lose their only write path when they upgrade**
  - **What is wrong:** `registry_append.py` refuses `layout-not-current` on `pending` and `stale-sync` (sub-task 3 tests both). Sub-task 6 says "No hand-Edit instruction remains" in plugin-delivered agents and skills. Every client is `pending` until it migrates, so the reviewer janitor, `/journal-add` and design-first Steps 3/5 exit 3 on every write. That includes the `post-impl divergence` lessons that feed the accuracy safety net. No writer instruction says what to do on exit 3. Issue §7 keeps clients that have not migrated working, so the lint is advisory, but the writer is not.
  - **Prior artifact ignored:** issue §7 "Lint too strict for legacy clients — lint is advisory until … layout version is 2"; JOURNAL.md 2026-10-30 "A rule that refuses must give already-delivered work a named way out"
  - **Where in this contract:** `## Commands` — "`layout-not-current` … (3)"; `### 6.` — "No hand-Edit instruction remains."
- **[BLOCKER] P2-3: Migration 0001 conserves only what the strict parser recognises, so other project content is lost silently**
  - **What is wrong:** I-12 and the conservation count cover parsed entries (key, body) only. Step 5 then leaves no `## Project:` content in a root. Three kinds of content are never moved, merged or reported: non-entry lines under a `## Project:` heading (sub-headings, prose, tables, the "See domain-specific files…" line that issue §2.2-B quotes); journal entries in `## YYYY-MM-DD` form, which the current digest accepts (`generate_registry_digest.py:34`, `#{2,3}`) and the new `###`-only grammar does not; and bullet-form journals, which the digest falls back to (`:129`). The parser failure mode's fixtures cover separators, date tags and CRLF only.
  - **Prior artifact ignored:** issue §4.2 "never deletes content: an entry is moved, merged, or reported — never dropped"; JOURNAL.md 2026-11-01 "A shared reader reused by a stricter consumer …"
  - **Where in this contract:** `## Data Shapes` I-12 — "every input (key, body) maps to an output entry"; `## Failure Modes` — "fixtures for each separator, date tags, CRLF"
- **[BLOCKER] P2-4: Migration step 4 contradicts steps 2–3, so fixture (a) cannot reach `current`**
  - **What is wrong:** "A key bodiless everywhere is kept as it is". If that key sits under a `## Project:` heading in a root, or exists in both the flat and the split copy, fixture (a) contains exactly that case ("title-only journal entries … the same entry in both"). Keeping it as it is leaves a project heading in the root or a duplicate key. The tree is then `stale-sync` or red on R2 after apply. The sub-task 5 assertion "--check exits 6 on (a) … before and 0 after" and I-11 idempotence cannot both hold.
  - **Prior artifact ignored:** issue §4.2 (idempotent; merged duplicates); I-1/I-11 of this contract
  - **Where in this contract:** `Migration 0001` step 4 — "A key bodiless everywhere is kept as it is"
- **[WARN] P2-W1: Moving token-bearing Universal entries loops against the sync**
  - **What is wrong:** 0001 step 1 cannot tell a client-authored Universal entry from a plugin-delivered one. The plugin's own Universal tier names client paths: `MECHANISMS.md:35` `python/scalping_llm/`, `:36` `python/scalping_strategy_rl/…`, `:18` "lneninger". If they are moved into a client's domain file, the next plugin-to-repo sync puts them back in the root, giving a root and domain duplicate (R2). R3 then stays red on plugin-owned text the client cannot edit. No failure mode covers this.
  - **Prior artifact ignored:** `MECHANISMS.md:52` Section-scoped registry sync; `MECHANISMS.md:54` Project-name check ("a token found in a file arriving FROM the plugin means the plugin is already contaminated")
  - **Where in this contract:** `Migration 0001` step 1 — "a Universal entry containing a project token … **moves**"
- **[WARN] P2-W2: I-14 "nothing fires … retroactively" is false for clients that already have split journals**
  - **What is wrong:** the seen cache is seeded once, from the flat file only. `journal-post-approval-tracker.py:43-47` and `:177-193` show a global `_initialized` flag. When the tracker starts watching `JOURNAL/*.md`, the first edit to a domain file treats every split-only entry it has never seen as new, and each `post-*` trigger calls `record_failure`. The reference client has 345 split-only titles (issue §2.2-A). Sub-task 3 tests only the global first run.
  - **Prior artifact ignored:** JOURNAL.md 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case"
  - **Where in this contract:** `## Events` — "**I-14** … nothing fires twice or retroactively"
- **[WARN] P2-W3: The state `absent` is used but never defined**
  - **What is wrong:** I-1 defines current, stale-sync, pending and unknown. `absent` appears in Value Objects, in `--check` (exit 0) and in the doctor remedy. It is never defined, and neither is the case where one of the three registries is missing while the others are marked. The follow-up stub records "applied layout" on any exit 0, which includes `absent`.
  - **Prior artifact ignored:** JOURNAL.md 2026-10-28 "A new term's definition must be true against every existing member"
  - **Where in this contract:** `## Data Shapes` I-1; `## Commands` "Check layout" — "0 `current` or `absent`"
- **[WARN] P2-W4: The import-side-effects assumption can be checked now, and it is false**
  - **What is wrong:** importing the module has these effects:
    - `auto_improve_finish_install.py:93` sets `sys.dont_write_bytecode = True` for the whole process.
    - `:95-96` runs `sys.path.insert(0, …)`, which `MECHANISMS.md:43` forbids: "never `insert(0, …)`".
    - `:98-99` also imports `pr_merged` and `plugin_doctor`.

    Also, step 5 requires "timestamped backups", but the existing never-overwrite `_backup_write` (`:1805`) is not in the import list. That is a third piece of Preview-hash apply rebuilt alongside the original.
  - **Prior artifact ignored:** `MECHANISMS.md:64` Preview-hash apply; `MECHANISMS.md:43` Two-layer Claude path resolution
  - **Where in this contract:** `## Uncertain Assumptions` — "`ASSUMED`: importing `auto_improve_finish_install` has no side effects beyond definitions"
- **[WARN] P2-W5: Sub-task 1 makes a contradicting body a "Correction", which reverses what it means**
  - **What is wrong:** the 2026-10-31 "Add-on manifest" text says the manifest names "the kill switches to report" (`VOCABULARY.md:91`). That contradicts `:75` ("It declares no kill switch") and `:79` ("no shipped add-on declares it"). Filing it as a Correction under the 2026-10-30 entry tells readers the older statement supersedes the newer one, and the user never decided which is true. The new Vendored-asset lines `Correction (2026-10-30):` also leave out the `<source>` that the Commands format `Correction (<date>, <source>)` requires.
  - **Prior artifact ignored:** JOURNAL.md 2026-10-28 "A new term's definition must be true against every existing member"; `VOCABULARY.md:74-79,91`
  - **Where in this contract:** `### 1.` CONSTRAINTS — "add under the 2026-10-30 entry … the deleted entry's text … verbatim"
- **[WARN] P2-W6: The lookup pin does not cover the reviewer agent**
  - **What is wrong:** `test_skill_script_lookup.py:58,91` scans `skills/**/*.md` only. The contract says the block is reused "in every skill and in the reviewer agent, pinned by `test_skill_script_lookup.py`", but `agents/fullstack-code-reviewer.md` is not pinned.
  - **Prior artifact ignored:** JOURNAL.md 2026-10-15 "A skill that edits a block pinned by a lookup-block test must name that test"; 2026-10-15 "Locate a script from the plugin root …"
  - **Where in this contract:** `## Reused Mechanisms` — "Script lookup block … in every skill and in the reviewer agent, pinned by `test_skill_script_lookup.py`"
- **[WARN] P2-W7: A1 and R1 do not say what happens to a `###` heading that is not an entry**
  - **What is wrong:** `JOURNAL.md:28` `### Tag conventions` is outside a fence. Under A1 ("a non-date") or R1 ("a journal heading without `Apply when:`") it is a finding in this repository. The ASSUMED line does not cover it.
  - **Prior artifact ignored:** JOURNAL.md 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case"
  - **Where in this contract:** `### Structural lint rules` — R1, A1; `## Uncertain Assumptions`
- **[WARN] P2-W8: The Q14 route has a sender but no receiver**
  - **What is wrong:** data-architect writes entry files under `.claude/cache/registry-appends/` and lists commands in its HANDOFF. No sub-task tells design-first, the caller, to run those commands, so promoted mechanisms and terms can stay as unexecuted cache files.
  - **Prior artifact ignored:** `MECHANISMS.md:5` (data-architect appends when a contract is promoted); `MECHANISMS.md:41` Adaptive Engineering Journal (append triggers)
  - **Where in this contract:** `### 6.` CONSTRAINTS — "lists the exact command per entry in its HANDOFF for the caller to run (Q14)"
- **[NIT] Budget.** The contract is about 25.8K tokens against its 18,000 budget. `.claude/templates/concept-contract.md:22` says superseded rounds move to `.claude/contract-history/<slug>.round-<n>.md`. Round 1 is kept here because the caller asked for it.
- **[NIT] Q14 and Q15 are still unticked.** The body already follows their recommendations. Both need a dated answer before approval (JOURNAL.md 2026-10-22).
- **[NIT] Missing test in sub-task 5.** It changes `plugin_doctor.REQUIREMENTS` but does not run `test_check_version_bump.py`, which pins every REQUIREMENTS source as shipped (`:79-91`).
- **[NIT] Unlisted reader lines in design-first.** `skills/design-first/SKILL.md:16,62-63,137` name flat registry paths as reader inputs, and the sub-task 6 reader bullet does not list them.
- **[NIT] registry-scout is out of date.** `agents/registry-scout.md:23` still says the generator "verifies every reference before writing", which Q9 changes, and it is in no Files to touch. The contract does not say whether the digest and R6's sources hash still cover `INTEGRATION.md` (I-4).
- **[NIT] Status line vs I-7.** I-7 allows only new entries or `Correction` lines, yet `--archive-title-only` appends a `Status:` line. The mechanism/vocabulary entry grammar has no Status form, although Q2 covers all three registries.
- **[NIT] Marking 266 orphans one by one.** Under Q15, after migration the reference client's 266 orphans make verify-before-done NOT-READY on every task until each one is marked with `--archive-title-only`, one command per title. This is consistent with the issue but deserves stating.

#### Applicable journal entries (pass 2)

- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — violated, see P2-1 and P2-2
- **2026-11-01 — A shared reader reused by a stricter consumer …** — violated, see P2-1 and P2-3
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — not addressed, see P2-W2 and P2-W7
- **2026-10-28 — A new term's definition must be true against every existing member** — violated for `absent` (P2-W3) and in sub-task 1 (P2-W5)
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded for skills, not for the agent (P2-W6)
- **2026-10-04 — Detect an install mode by what the sync actually delivers** — heeded by `stale-sync`
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded (Option E), but see P2-W4 on `_backup_write`
- **2026-10-22 — An accepted critic WARN … must amend the contract body before approval** — pending for Q14 and Q15

#### What the critic did not check (pass 2)

- No shell, so `validate_registries.py`, `pr_merged.py --status --json` and `cross_area_scan.py` were not run. The R4 findings above come from reading the regex and checking each cited path with Glob.
- CodeGraph tools were unavailable in this session, so source files were read directly.

---

## Part B — Amendment-1 passages replaced by amendment 2 (verbatim)

### Header

```
**Budget:** 18,000 tokens (raised from 12,000 at amendment 1: an XL contract whose critique round must stay in place until the next critic run)
**Amendment:** 1 (2026-11-04) — critic round 1 and the user's decision "accept all recommended answers and amend". The issue text (§2.2-B, §2.2-C, §3.4, §4.2, §4.4, §5) is now authoritative and was read verbatim.
```

### Business Concept — term "Registry layout state"

```
  - **Registry layout state** — `current`, `pending`, `stale-sync`, `unknown` or `absent`, computed from the files (Value Objects). Not a delivery-layout value.
```

### Entities (rows Registry, Registry entry, Registry migration)

```
| Registry (mechanisms, vocabulary, journal) | name; root file; domain files (`general`, then alphabetical); layout state | **I-1** layout 2 is `current` only when ALL hold: every root file's first line is exactly the marker; no root file holds a `## Project:` heading or any entry below its `## Project tier` pointer; every registry has `<REG>/general.md`. Marker present but another condition failing = `stale-sync`. No marker anywhere = `pending`. A marker with another value, or root files that disagree = `unknown`. **I-2** a layout-2 root's last section is the fixed pointer `## Project tier` naming `<REGISTRY>/<domain>.md`, saying `general.md` always exists and that every `.md` in the folder is read; it lists no domain, so it stays generic and syncable. **I-3** domain files are resolved from the same `.claude` root the root file was found in; never a union of roots. **I-4** `INTEGRATION.md` is outside the layout. | the project |
| Registry entry | registry; tier (`universal`, `project:<name>` on layout 1, `domain:<slug>`); file; line; title; key; body; tags; source contract; status (`active`, `archived-title-only`) | **I-5** body non-empty unless status is `archived-title-only`. **I-6** keys unique per registry. **I-7** append-only from layout 2 on: an existing entry is never reordered or rewritten; a refinement is a new entry or an indented `Correction` line under it; the `<term> (amendment)` convention is replaced by `Correction` lines. Sub-task 1's reconciliation is the one user-approved exception, made before layout 2 exists. **I-8** fenced code blocks are never parsed as entries. | its registry |
| Registry migration | number (0001); from; to; plan; plan hash; report | **I-9** dry-run writes nothing under `.claude/registries/`. **I-10** apply writes only when the recomputed plan hash equals `--expect-sha256`. **I-11** idempotent: on `current` the plan is empty and exit is 0; `stale-sync` is NOT current and is migrated. **I-12** no content loss: every input (key, body) maps to an output entry with that key and body (line endings folded, BOM dropped), and per registry `occurrences in = kept + moved + merged away`; otherwise refuse `content-loss-detected` and write nothing. **I-13** a refusal leaves every registry file byte-identical and still writes the report. | plugin (code); project (result) |
```

### Value Objects (rows entry grammar, Migration report, Registry layout state)

```
| Mechanism / vocabulary entry grammar | `- **<title>**`, optional `*(<date>)*`, separator (`—` written; `—`, `--`, `-` read), body; continuation = following lines indented 2+ spaces until the next column-0 `- **` or a heading | title non-empty; body = text after separator plus continuation | parser input |
| Journal entry grammar | `### YYYY-MM-DD <sep> <title>` (the tracker's `ENTRY_HEADER` separators); fields Trigger, Source contract, Lesson, Apply when, Tags; optional Areas, Status | "has a body" = an `Apply when:` field with text (§3.4) | parser input |
| Migration report | number; project; mode (`dry-run`, `apply`, `refused`); refusal code; plan hash; per registry: kept, moved (key, from, to, reason), merged duplicates, bodiless orphans (with recovery hint), unclassified (fell to `general`), project-token entries moved, unmovable token lines, conflicts (key, locations), counts | refusal code empty unless mode is `refused`; moved/merged/orphans/conflicts may be empty lists, never absent; plan hash present in every mode | `registry-migration-report.md` + `report.json` in `<project>/.claude/cache/registry-migrations/0001-<UTC>/`, JSON also on stdout |
| Registry layout state | state; found marker (value or `none`); layout current (2); reasons; remedy | found marker is `none` for `pending` and `absent`; reasons non-empty for `stale-sync` and `unknown`; remedy names `registry_migrate.py --dry-run` (pending, stale-sync) or `plugin_doctor.py --fix` (absent) | `_registry_layout.layout_state`, `--check`, doctor, lint mode, `registry_append.py` |
```

### Structural lint rules (R1, R3, R4, R6, A1, Mode, Digest)

```
- **R1 bodiless-entry** — a journal heading without `Apply when:` text (§3.4). *Addition:* a mechanism/vocabulary entry with an empty body, because I-5 and the digest's "fail on bodiless" apply to all three. `archived-title-only` entries are exempt (Q2).
- **R3 project-entry-above-pointer** — in a root file: a `## Project:` heading, an entry below the pointer, or (when `.claude/.project-tokens.json` exists) a Universal entry containing a token, case-insensitively, as the Project-name check reads it.
- **R4 dead-file-reference** — today's backticked-path check, over every registry file including the journal and domain files.
- **R6 digest-stale** — the digest records `<!-- registry-sources-sha256: <hex> -->` over every registry file read (sorted path, normalised bytes); R6 fires when the digest exists and that line is missing or differs, or a registry key is absent from it. A content hash, not timestamps, because a checkout rewrites timestamps (VOCABULARY "Vendored-asset drift"). An absent digest is no finding and is printed as `digest: absent`.
- **A1 malformed-entry** — *addition beyond §3.4:* a journal entry missing a required field, a non-date, a Trigger outside {`pre-approval critic`, `post-approval`, `post-impl divergence`, `manual`}, or an M/V heading with no separator. Kept because `registry_append.py` refuses the same input; without A1 a hand-written entry escapes the grammar the writer enforces. The layout marker is NOT a lint rule; it belongs to the layout state.
- **Mode (issue §7):** when the layout state is not `current`, the lint prints findings plus `advisory: registry layout <state> — <remedy>` and exits 0. On `current`: exit 0 clean, 1 findings. Exit 2 could not check.
- **Digest generator:** drops the hard-coded `DOMAINS`; reads through the resolver; labels each entry's tier from its file and heading (`Universal`, `project:<name>` on layout 1, `domain:<slug>`); always writes the complete index plus the sources hash; exits 1 naming each R1/R2 finding (Q9).
```

### Events (row Journal entry appended)

```
| Journal entry appended | `registry_append.py` (calls the listener directly, §3.2) or an Edit/Write on any journal file (`post-edit-dispatcher.py` → tracker) | `accuracy_update.process_journal_change(files)` → `record_failure(area, contract, "post-approval-journal")` for `post-*` triggers | journal files changed. **I-14** the seen-signature stays `sha1(date + "|" + title)`, unrelated to the entry key, so the seen cache stays valid and nothing fires twice or retroactively. |
```

### Commands (rows Append, Check layout, Preview / apply)

```
| Append registry entry | `registry_append.py` | `--project` (required), `--registry mechanisms\|vocabulary\|journal`, `--from-file <entry.md\|->` (one entry in the registry's grammar), then one of `--universal`, `--domain <slug>` [`--create-domain`], or neither: domain = the source contract's area (`derive_area` over `area-mapping.json`) when that domain file exists, else `general`, printed. Modes: `--correction-of <title>` (appends an indented `Correction (<date>, <source>)` line); `--archive-title-only <title>` (appends a `Status: archived-title-only` line to a bodiless entry). | `bodiless-input`, `duplicate-entry`, `malformed-input`, `unknown-domain`, `correction-target-missing`, `archive-target-missing`, `archive-target-has-body` (2); `layout-not-current`, `project-undetermined`, `write-failed` (3). Appends at the end of the Universal tier (before the pointer) or the domain file, via a temp file and `os.replace`; prints `file:line`. |
| Check layout | `registry_migrate.py --check --project <root>` | — | 0 `current` or `absent`; 6 `pending` or `stale-sync`; 2 `unknown` or unreadable |
| Preview / apply migration | `registry_migrate.py --dry-run` / `--apply --expect-sha256 <h>`, `--project` required | — | `project-undetermined` (unset and absent), `not-a-git-tree`, `uncommitted-registry-changes`, `conflicting-entry`, `unknown-layout`, `changed-since-preview`, `content-loss-detected`, `symlink-target`, `write-failed` (3); bad arguments 2 |
```

### Plan hash and Migration 0001

```
**Plan hash:** `auto_improve_finish_install._plan_digest` imported unchanged (the length-prefixed SHA-256 of "Preview-hash apply"), over `b"registry-migration"`, `b"0001"`, then per file to write in sorted POSIX relative-path order: path, input bytes or `absent`, planned output bytes. The report is outside the plan. A test pins the runner's hash equal to `_plan_digest` over the same parts, so one definition exists.

**Migration 0001 (layout 1 or `stale-sync` → 2), per registry:**
1. Universal entries stay in the root, except a Universal entry containing a project token (§4.4, when `.project-tokens.json` exists), which **moves** like a project entry; each move is listed. A token line outside any entry (header prose) is listed as `unmovable-token-line` and not moved.
2. Every entry under a `## Project:` heading (and, on `stale-sync`, every entry below the synced pointer) moves. Destination, in §4.2 order: the domain file already holding that key → a `Tags:` value equal to an existing domain-file name → the source contract's area (`derive_area`) when that domain file exists → `general` (listed as unclassified). 0001 creates no domain file except `general.md`.
3. Same key, equal bodies → one copy, at the existing domain-file location. One bodiless and one bodied → the bodied one. **Same key, different non-empty bodies → refuse `conflicting-entry`**; the report names every location and each body's first line. The operator resolves by hand while still on layout 1 (hand edits are allowed before migration): keep one body, rename one title with a distinguishing suffix, or fold the later body into a `Correction` line under the earlier one; commit; re-run the dry-run.
4. A key bodiless everywhere is kept as it is and listed as a bodiless orphan with the hint "recover the body from your own backups, or mark it with `registry_append.py --archive-title-only`" (§4.3 step 5; Q15). Never invented text.
5. Writes the marker, exactly one pointer section, and `general.md` from the skeleton when missing. Multi-file apply: all temp files and timestamped backups first, replace in order, and on a failure restore every replaced file (`write-failed`).
```

### Reused Mechanisms (Preview-hash apply, Project-name check, Script lookup block)

```
- **Preview-hash apply** — consumed **by import**: `_plan_digest` and `_atomic_write` from `auto_improve_finish_install.py`. Not extended by a new subcommand of that script, although its Extend-by suggests one, because that script owns the project profile and settings files; making it the owner of registry migrations would give one script two owners' files with different lifecycles (sync versus install). Only the multi-file rollback is new code.
- **Project-name check** — consumed: 0001 and R3 read `.claude/.project-tokens.json` the way the sync does (case-insensitive literal tokens, `allowed` exemptions honoured).
- **Script lookup block** (the "Find the script" block of `skills/verify-before-done/SKILL.md` Step 1: project copy, `CLAUDE_PLUGIN_ROOT`, `installed_plugins.json`, newest cache folder) — reused verbatim for `registry_append.py` and `validate_registries.py` in every skill and in the reviewer agent, pinned by `test_skill_script_lookup.py`. The command always passes `--project "$CLAUDE_PROJECT_DIR"`, so a plugin-root script writes the client's registries.
```

### Uncertain Assumptions

```
- `VERIFIED via .claude/registries/*.md`: the plugin's registries are flat, have no `## Project:` heading and no domain folder; the journal's 41 titles are unique; VOCABULARY repeats "Add-on manifest" (`:79`, `:91`) and "Vendored-asset drift (amendment)" (`:86`, `:94`) with different bodies.
- `VERIFIED via .claude/scripts/auto_improve_finish_install.py:275,380`: `_plan_digest(*parts)` and `_atomic_write` exist as module functions.
- `VERIFIED via agents/*.md frontmatter`: `data-architect` has no shell tool; `fullstack-code-reviewer` has `Bash`.
- `VERIFIED via grep`: `skills/ship/SKILL.md` has no registry text; §2.2-B does not name it.
- `ASSUMED`: every journal entry here passes A1 and R4. Verification: sub-task 2 runs the lint on this repository; any finding is reported as AMENDMENT, never suppressed.
- `ASSUMED`: importing `auto_improve_finish_install` has no side effects beyond definitions. Verification: sub-task 5's hash-pin test imports it in a clean process.
```

### Failure Modes (rows replaced)

```
- **FM:** the strict parser rejects forms the old regexes tolerated. **Mitigation:** fixtures for each separator, date tags, CRLF, and this repository's registries (JOURNAL 2026-11-01).
- **FM:** the tracker fires twice or retroactively. **Mitigation:** I-14; one seen cache; a test appends by script, then edits, and asserts one fire.
- **FM:** a plugin-delivered client has no `.claude/scripts/registry_append.py`. **Mitigation:** the standard lookup block, pinned by `test_skill_script_lookup.py`; `--project` passed explicitly (JOURNAL 2026-10-15 ×2).
```

### Open Questions Q14, Q15

```
- [ ] **Q14 data-architect has no shell** — it cannot run `registry_append.py`. **Recommendation:** its append rules say to write each entry to a file under `.claude/cache/registry-appends/` and list the exact `registry_append.py` command per entry in its HANDOFF, which the caller runs; no tool grant. Proceeding on this unless you object.
- [ ] **Q15 Who marks orphans** — the earlier draft had 0001 mark bodiless orphans; issue §4.3 step 5 leaves that choice to the operator. **Recommendation:** 0001 reports orphans only; the operator marks with `registry_append.py --archive-title-only <title>` after trying recovery, so the red lint keeps telling them recovery is pending. Proceeding on this unless you object.
```

### Sub-task 1 TASK block CONSTRAINTS

```
  - "Add-on manifest": delete the top-level 2026-10-31 entry (today ~line 91) and add under the 2026-10-30 entry
    (~line 79) the indented line
    "  - **Correction (2026-10-31, `.claude/concepts/2026-10-12-dedupe-claude-config.md`, Revision 3):** " followed
    by the deleted entry's text after its separator, verbatim.
  - "Vendored-asset drift (amendment)" x2: delete both top-level entries (~86, ~94) and add under the base entry
    "Vendored-asset drift" (~36), after its existing 2026-10-31 Correction line (appended, nothing reordered):
    "  - **Correction (2026-10-30):** " + the 2026-10-30 text verbatim, and
    "  - **Correction (2026-11-01):** " + the 2026-11-01 text verbatim.
  - Touch nothing else. "Placeholder slot (amendment)" is unique and stays.
  - Check by hand: no bold title appears twice at column 0; the three bodies appear once each, unchanged.
```

### Sub-task 2 TASK block CONSTRAINTS (Tests line)

```
  - Tests: pass + fail per rule; advisory vs current exit codes; each layout state incl. stale-sync; skeletons pass;
    missing domain folder; CRLF; "--" separator; date tag; fenced sample entry ignored; domains= filter keeps
    general; this repository's registries give zero findings (if not, emit AMENDMENT; never suppress).
```

### Sub-task 3 TASK block CONSTRAINTS

```
  - Options, defaults, rejection codes and exits exactly as the Commands table; --project required; atomic write;
    prints file:line and the chosen destination; calls process_journal_change after a journal write.
  - Signature stays sha1(date|title) (I-14). Hook resolves journal files at call time; still exits 0 always.
  - Tests: one per rejection (incl. project-undetermined unset and absent, layout-not-current on pending and
    stale-sync); --universal, --domain, default from a source contract's area, fallback to general; --correction-of;
    --archive-title-only on a bodiless entry and its refusal on a bodied one; a post-impl divergence entry appended by
    the script resets the bucket once; the same entry then edited by hand does not fire again; a hand Edit to
    JOURNAL/general.md fires; first run seeds without firing.
```

### Sub-task 5 (Files to touch, CONSTRAINTS)

```
**Files to touch:**
- `.claude/scripts/registry_migrate.py`
- `.claude/scripts/registry_migrations/__init__.py`
- `.claude/scripts/registry_migrations/m0001_domain_split.py`
- `.claude/scripts/plugin_doctor.py`
- `.claude/scripts/tests/test_registry_migrate.py`
- `.claude/scripts/tests/test_plugin_doctor.py`
- `.claude/scripts/tests/fixtures/registry-migration/...`

  - Import _plan_digest and _atomic_write from auto_improve_finish_install; do not edit that script.
  - Fixtures: (a) the client's state: title-only journal entries, flat-only entries, split-only entries, the same
    entry in both, Tags and source contracts that classify to existing domains, a project-token entry and a token
    header line in the Universal tier, a .project-tokens.json; (b) stale-sync: marker + pointer above ## Project:
    sections; (c) a same-title different-body conflict.
  - Tests: dry-run writes nothing; apply with the dry-run hash succeeds; second apply is a no-op (exit 0, bytes
    equal); no-content-loss and entry-count conservation per registry; classification order of §4.2; token entry
    moved and listed; orphans listed with the hint, not marked; conflicting-entry and uncommitted-registry-changes
    each refuse, write the report and leave every registry byte-identical; changed-since-preview; a forced write
    failure restores every file; --check exits 6 on (a) and (b) before and 0 after; hash equals _plan_digest over the
    stated parts; project-undetermined for unset and absent.
  - Doctor: report-only; --fix never migrates; existing suite green.
  - Run: py -3 .claude/scripts/tests/test_registry_migrate.py ; py -3 .claude/scripts/tests/test_plugin_doctor.py
```

### Sub-task 6 (Writers bullet, Readers bullet, Text scan bullet)

```
  - Writers: fullstack-code-reviewer janitor duties; journal-add; design-first Step 3 (~line 166) and Step 5
    (~lines 323-325 and 346); data-architect append rules. Each runs the standard lookup block (verify-before-done
    Step 1 form) for registry_append.py with --project "$CLAUDE_PROJECT_DIR"; plugin-generic entries use
    --universal. data-architect has no shell: it writes each entry file under .claude/cache/registry-appends/ and
    lists the exact command per entry in its HANDOFF for the caller to run (Q14). No hand-Edit instruction remains.
  - Readers: data-architect and contract-critic name MECHANISMS/general.md, VOCABULARY/general.md, JOURNAL/general.md,
    drop the fixed {backend,frontend,data,trading} list, and state the focus rule: always the root and general.md;
    plus each domain file whose name equals the contract's derived area or an adjacent area, or its focus
    (backend, frontend, data) when that file exists; when none matches, every domain file. ui-ux-designer,
    application-design, website-design and promote-ui-rule search JOURNAL.md and JOURNAL/*.md. cross-impact names the
    domain files. validate-registries describes --check-structure and routes fixes through registry_append.py
    (--correction-of). north-star skill and template, concept-contract and followup-stub templates drop
    "project section" / "under <project>" wording for the domain-file form.
  - Text scan: the §2.2-B writers name registry_append.py; data-architect and contract-critic name general.md; no
    shipped agent, skill or template names a flat registry path without the domain form, says "project section",
    or instructs appending to a registry by Edit. Lookup pin: test_skill_script_lookup.py covers every new block.
```

### Sub-task 7 CONSTRAINTS (first bullet)

```
  - Never hand-edit a registry. After the writes: --check exits 0, --check-structure exits 0, the digest exits 0.
```
