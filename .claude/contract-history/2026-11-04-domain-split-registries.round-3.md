# Superseded critique round 3 and amendment-2 text — 2026-11-04-domain-split-registries

Moved out of `.claude/concepts/2026-11-04-domain-split-registries.md` on 2026-11-04 by `data-architect` (amendment 3), per the budget rule in `.claude/templates/concept-contract.md`. Part A is critic round 3 ("Pass 3 (amendment 2)"), unchanged. Part B is the critique decision trail of rounds 1 and 2 as it stood in amendment 2, unchanged. Part C is every passage of the amendment-2 body that amendment 3 replaced or trimmed, unchanged, so the decision trail survives (the contract was never committed, so git holds no earlier copy). The live contract keeps one `→ Addressed by` line per finding.

---

## Part A — Pass 3 (amendment 2)

**Critic:** contract-critic (cold context)
**Date:** 2026-11-04
**Verdict:** blockers-found

#### Pass-2 BLOCKER verification (checked against the body and the repository)

- **P2-1 (R4 never passes)** — fixed. R4 is advisory unless `--strict`. The Path reference VO rejects `` `?? d/f.txt` `` (space, `?`) and `` `"$CLAUDE_PROJECT_DIR"/…` `` (`"`, `$`), and it still catches the retired-contract, `tools/sync-plugin.cmd` and `python/…` citations. The expected output is wrong, though (W1).
- **P2-2 (writers stop)** — the refusal is gone, but the fallback that replaces it misfiles entries (B1).
- **P2-3 (silent loss)** — mostly fixed. The text-level I-12 can be satisfied and tested, and the forced-drop test is meaningful. One gap is left in the journal merge rule (W5).
- **P2-4 (step 4 contradiction)** — fixed. Steps 3–5 leave no project heading, no duplicate and every `general.md` present, so fixtures (a) and (b) can reach `current`. One ordering gap is left for the second apply (W3).
- **Sub-task graph** — no finding. 1→2→{4,5}, 5→3, {2,3,5}→6, {3,4,5,6}→7→8 has no cycle. `VOCABULARY.md` (1, 7) and `auto_improve_finish_install.py` (5 only) are touched in a strict order, and no test file appears in two blocks.

#### Findings

- **[BLOCKER] B1: The pending/stale-sync writer fallback puts project entries into the plugin-owned Universal tier**
  - **What is wrong:** with no `## Project:` section, a non-`--universal` entry goes to "the end of the file". With no heading, the whole root is the Universal tier, so that place is inside it. Issue §2.2-B says this is exactly the reference client's shape: its flat `MECHANISMS.md` "ends with 'See domain-specific files…', so there is no project section to append to". 0001 step 2 then leaves that non-token entry in the root. The sync compares the Universal tier and can publish it to the plugin. The fallback also ignores the client's existing domain files (`--domain` "is named in the advisory and not used"), so the flat and split copies keep drifting apart, which is the defect §1 describes.
  - **Prior artifact ignored:** `MECHANISMS.md:52` Section-scoped registry sync ("everything below the first `## Project:` line is never touched"; above it is plugin-owned); issue §2.2-B and §1
  - **Where in this contract:** `## Commands` → Append — "else the last `## Project:` section, else the end of the file; a given `--domain` is named in the advisory and not used"
- **[BLOCKER] B2: `find_plugin_root` returns a vendored consumer's own tree, so every client-authored token entry counts as plugin-owned**
  - **What is wrong:** `plugin_doctor.py:173-183` tries the script's own tree first and accepts any tree that holds `.claude/templates/concept-contract.md`. A vendored client meets both conditions (the follow-up stub, item 7, confirms that vendoring is supported). There, "the plugin's Universal tier" is the client's own root, and every Universal key matches. The results:
    - Step 2 moves no token entry (`plugin-owned-token-entry`).
    - R3 only ever gives `R3 plugin-owned` advisories.
    - §4.4 (move about 100 project lines out of the Universal tier) silently never happens.

    The repository already has the guard for this: `auto_improve_finish_install._separate_plugin_root` (`:347-377`) rejects the project itself and requires the manifest name.
  - **Prior artifact ignored:** JOURNAL.md 2026-10-04 "A root locator can return the consumer itself under vendoring"; `auto_improve_finish_install.py:361-377`
  - **Where in this contract:** `## Commands` → Preview / apply — "`--plugin-root <path>` optional (default: `plugin_doctor.find_plugin_root` …)"; `## Reused Mechanisms` → Installed plugin root
- **[BLOCKER] B3: The `seeded_files` change stops hand-written `post-*` entries from firing in every new worktree, and Q17 understates this**
  - **What is wrong:** the seen cache is machine-wide (`journal-post-approval-tracker.py:46-47`, `Path.home()/.claude/state`), and `seeded_files` holds resolved absolute paths. Each worktree's journal files have new absolute paths. So the first hand Edit of each journal file in each worktree seeds the file and does not fire, even when that Edit is the one adding the `post-*` entry. Today `_initialized` and `sigs` are global, so that entry fires. The main-checkout guard means every edit in this repository happens in a worktree, so the limit applies to nearly every hand entry, including ones in the root `JOURNAL.md`, not to "a journal file the tracker has never seen". The resolver already provides a path key that is the same in every worktree.
  - **Prior artifact ignored:** `MECHANISMS.md:43` (`checkout_equivalent_path`); `MECHANISMS.md:68` Main-checkout guard; issue §5 AC "fires for an entry written to any journal file"
  - **Where in this contract:** `## Events` I-14 — "`seeded_files` (resolved absolute paths)"; `## Open Questions` Q17
- **[WARN] W1: R4's expected output in sub-tasks 2 and 7 is incomplete, and the VO has false positives it does not name**
  - **What is wrong:** the VO also flags these paths, which do not exist in the worktree:
    - consumer or generated files: `.claude/.sync-config.json` (`MECHANISMS.md:16,46,47,50,100`; `VOCABULARY.md:34`), `.claude/settings.json` (`VOCABULARY.md:76,103`; `MECHANISMS.md:46,64,101`), `.claude/hook-registration-profile.json`, `.claude/.sync-state/conflicts.json`, `.codegraph/config.json`, `.claude/.scout-cache/registry-digest.md`;
    - `tools/sync-plugin.ps1` and `tests/integration/conftest.py`;
    - two live but relative paths: `../website-design/references/foundation.md` and `../application-design/references/application-patterns.md` (`MECHANISMS.md:83`).

    So "no other line … emit AMENDMENT" fires on a correct implementation. The "candidate roots" are not defined for `--check-structure`. A `file:line` span (issue §2.1 `JOURNAL/frontend.md:33`) is never checked at all, because `:` is outside the allowed characters.
  - **Prior artifact ignored:** JOURNAL.md 2026-11-01 "A shared reader reused by a stricter consumer …"; `validate_registries.py:59,173` (the old check skipped `.`-leading spans, so these were never seen before)
  - **Where in this contract:** `### 2.` — "R4 advisory lines for the retired-contract citations, tools/sync-plugin.cmd and the python/... path, and no other R-rule"
- **[WARN] W2: "Extracted unchanged" `_atomic_write` cannot do "every temp file first, then replace in order"**
  - **What is wrong:** `_atomic_write` (`auto_improve_finish_install.py:380-394`) writes its own `.<name>.tmp-<pid>` and replaces it in one call. Staging every temp file before the first replace therefore needs new staging code, or it pre-writes files that `_atomic_write` then overwrites under the same name.
  - **Prior artifact ignored:** `MECHANISMS.md:64` Preview-hash apply
  - **Where in this contract:** `Migration 0001` step 6 — "writes every backup … and every temp file first, then replaces in order with `_atomic_write`"
- **[WARN] W3: Backups land inside `.claude/registries/`, and the second apply's check order is undefined**
  - **What is wrong:** `_backup_write` (`:1805-1821`) writes `<name>.bak-<stamp>` beside its target. That leaves untracked files under `.claude/registries/` and its domain folders, which the procedure's "commit" step would commit. `uncommitted-registry-changes` would also refuse until they are removed. Nothing says whether that guard runs before the empty-plan exit 0. If it does, the test "a second apply is a no-op (exit 0)" on an uncommitted tree fails.
  - **Prior artifact ignored:** `MECHANISMS.md:64` (backup designed for `settings.json`); issue §7 "refuses on uncommitted registry changes"
  - **Where in this contract:** `### 5.` Tests — "a second apply is a no-op (exit 0, bytes equal)"; `### 7.` client procedure
- **[WARN] W4: The extraction breaks vendored `auto_improve_finish_install.py` (and `plugin_doctor.py` → `_registry_layout`) until the other repository's follow-up lands**
  - **What is wrong:** a file that no tree's `files` array names is never synced. A consumer that receives the new finish-install or doctor, without the two new modules, fails at import. The FM's mitigation ("the lookup block resolves") covers locating a script, not resolving a module import.
  - **Prior artifact ignored:** `MECHANISMS.md:46` ownership model ("a file no tree's `files` array names is a local asset … never synced"); the follow-up stub, item 7, which states the failure
  - **Where in this contract:** `## Failure Modes` — "a client has the scripts but not `_preview_apply.py`/`_registry_layout.py`"
- **[WARN] W5: Step 4's journal "bodiless" copy may hold text that is then discarded**
  - **What is wrong:** for the journal, "has a body" means `Apply when:` text. Take a copy with Trigger and Lesson but no `Apply when:`, beside a bodied copy. Step 4 lists its lines as `merged-duplicate`, so the text check passes while the unique Lesson text is lost. Read the other way, it is a body that maps to no output, which gives `content-loss-detected` with no named resolution. The VO never defines what a journal entry's "body" is.
  - **Prior artifact ignored:** issue §4.2 "never deletes content"; JOURNAL.md 2026-10-30 "A rule that refuses must give already-delivered work a named way out"
  - **Where in this contract:** `Migration 0001` step 4 — "one bodiless copy and one bodied copy: the bodied copy is kept"
- **[WARN] W6: Q16's reason is false for client-authored legacy entries, and the strict digest drops entries it indexes today**
  - **What is wrong:** "a conversion would be undone by the next sync" only holds for plugin-owned text. A client's `## YYYY-MM-DD` lessons in a root with no heading are not synced back. The digest's `DATED = ^#{2,3}` (`generate_registry_digest.py:34`) indexes them today. Under the strict reader they become `advisory: unparsed`, and under `## Project:` they become fenced leftovers. Either way they drop out of the index, the readers and the tracker.
  - **Prior artifact ignored:** `MECHANISMS.md:63` ("The index is never trimmed"); JOURNAL.md 2026-11-01 "A shared reader reused by a stricter consumer …"
  - **Where in this contract:** `## Open Questions` Q16 — "The Universal tier is plugin-owned and synced, so a conversion would be undone by the next sync"
- **[WARN] W7: Client-authored Universal entries without tokens never leave the root**
  - **What is wrong:** 0001 already reads the plugin's Universal keys, but it uses them only for token entries. A client root with no heading reaches `current` with its project entries still in the root. Issue §6 expects "~102 flat-only entries to merge into domain files", and the thin-root rule stays unenforced for those entries.
  - **Prior artifact ignored:** issue §2.2-D and §6; `MECHANISMS.md:63` ("a thin top-level file holding only the Universal tier")
  - **Where in this contract:** `Migration 0001` step 2 — "Entries … stay in place … otherwise it moves like a project entry" (tokens only)
- **[WARN] W8: New domain-file appends land under the "not parsed as entries" heading**
  - **What is wrong:** `registry_append.py` appends "at the end of … the domain file", and 0001 puts the `## Migration 0001 leftovers (not parsed as entries)` section into `general.md`. I-8b says a non-entry heading's "lines are section prose". It does not say whether that means the heading line only or the whole section below it. So every entry appended to `general.md` after migration is either misleadingly placed or not parsed.
  - **Prior artifact ignored:** JOURNAL.md 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case"
  - **Where in this contract:** `## Commands` → Append — "appends at the end … of the domain file"; Value Objects → Migration leftover block
- **[NIT] Budget.** The Read tool counts 25,712 tokens for lines 1–549 of 665. By the template's four-characters-per-token rule the contract is far above 18,000, so a claim of about 17.5K is not credible.
- **[NIT] Double classification.** I-8b makes every non-tier `##` heading a non-entry heading, which covers `## YYYY-MM-DD`. Steps 1–3, A1 and the leftover reasons treat the same heading as a legacy form. "Tier heading" is never defined.
- **[NIT] Project-name match.** "the `## Project: <name>` section matching the project folder's name" reads the worktree's slug under `--project "$CLAUDE_PROJECT_DIR"` in a worktree (JOURNAL.md 2026-10-15 "…must be told which project").
- **[NIT] I-12 wording.** "Minus the lines 0001 adds" must be counted per instance, or a source fence line identical to an added fence line cancels out. On stale-sync, "everything below the synced pointer" also covers the pointer's own body lines, which `replaced-sync-section` claims as well.

#### Applicable journal entries (pass 3)

- **2026-10-04 — A root locator can return the consumer itself under vendoring** — violated, see B2 (also missing from `## Lessons referenced`)
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — heeded by R4 advisory and the writer fallback; see B1 and W5 for the gaps
- **2026-11-01 — A shared reader reused by a stricter consumer …** — partly heeded; see W1 and W6
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded for `### Tag conventions`; not for I-8b's scope (W8)
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded by the extraction; see W2 and W4

#### What the critic did not check (pass 3)

- No shell, so `wc`, `validate_registries.py`, `pr_merged.py --status --json` and `cross_area_scan.py` were not run. R4 hits come from a Glob/Grep approximation of the VO.
- CodeGraph tools were not available; source was read directly.
- The reference client's root shape (heading or no heading) is taken from issue §2.2-B, not seen. B1 and W7 depend on it.

---

## Part B — Critique decision trail as of amendment 2

Both rounds are kept verbatim in history, per the budget rule. Round 1 (contract-critic, 2026-11-04, blockers-found, 6 BLOCKER / 8 WARN / 4 NIT) is in `.claude/contract-history/2026-11-04-domain-split-registries.round-1.md`. Round 2 (contract-critic, 2026-11-04, blockers-found, 4 BLOCKER / 8 WARN / 7 NIT) is in `.round-2.md`, together with the amendment-1 text that amendment 2 replaced. The decision trail follows.

### Round 1 — addressed by amendment 1; round 2's verification
- B1 rules vs §3.4 → R1–R6 + A1. Verified fixed.
- B2 writer list → exactly §2.2-B. Verified fixed.
- B3 reader sweep → sub-task 6 list. Verified fixed.
- B4 plugin duplicates → sub-task 1. Partly fixed; the rest is P2-1, P2-W5, P2-W7.
- B5 lookup block → Script lookup block. Partly fixed; the rest is P2-W6.
- B6 stale-sync → I-1. Verified fixed; the rest is P2-W3.
- 8 WARN, 4 NIT → as recorded in the round-1 file.

### Round 2 — addressed by amendment 2
- **P2-1** R4 can never pass → Addressed by: R4 is advisory (`--strict` opt-in); Path reference VO excludes `?? d/f.txt` and `"$CLAUDE_PROJECT_DIR"/…`; historical paths reported, not rewritten; sub-task 2/7 expectations corrected.
- **P2-2** writers stop on unmigrated clients → Addressed by: Commands "By layout state" (legacy flat location + advisory, exit 0); refusals only for malformed input, `layout-unknown`, `registries-absent`; sub-task 6 skill wording; Option G.
- **P2-3** silent content loss → Addressed by: 0001 step 3 leftovers, Migration leftover VO and term, I-8b, text-level I-12 with closed removed-line set, fixtures in sub-task 5.
- **P2-4** step 4 contradiction → Addressed by: steps 4–5 and the post-condition; fixture (a) asserts `current` after apply.
- **P2-W1** token loop → Addressed by: step 2 plugin-owned rule, R3 advisory forms, `--plugin-root`, FM, follow-up stub.
- **P2-W2** retroactive fires → Addressed by: I-14 `seeded_files`, `fresh`, Q17.
- **P2-W3** `absent` undefined → Addressed by: I-1 and the term definition; stub records applied layout on `current` only.
- **P2-W4** import side effects → Addressed by: extraction into `_preview_apply.py` (incl. `_backup_write`), sub-task 5.
- **P2-W5** Correction reverses meaning → Addressed by: sub-task 1 quoted wording ("Merged duplicate … the entry above and the Add-on entry govern"); sources added to both Vendored-asset lines.
- **P2-W6** reviewer not pinned → Addressed by: `test_skill_script_lookup.py` scans `agents/*.md` (sub-task 6).
- **P2-W7** non-entry headings → Addressed by: I-8b; R1/A1 exemptions; `### Tag conventions` stays in place.
- **P2-W8** Q14 no receiver → Addressed by: design-first section (sub-task 6), data-architect rule names it.
- **NITs** → budget: history files; Q14/Q15 ticked; `test_check_version_bump.py` and finish-install suite run in sub-task 5; design-first `:16,62-63,137` in sub-task 6; `agents/registry-scout.md` added and I-4 states digest/R6 coverage; I-7 names the `Status:` line and the grammar has its form; 266 orphans → ready-to-run lines + FM.

---

## Part C — Amendment-2 passages replaced or trimmed by amendment 3

### Header line
**Budget:** 18,000 tokens (raised from 12,000 at amendment 1 for an XL contract; superseded rounds live in `.claude/contract-history/`)
**Amendment:** 2 (2026-11-04). It follows critic round 2 and the user's decision "accept all recommended fixes" (B-new-1..4, all WARNs and NITs, Q14 and Q15). Rounds 1 and 2 and the replaced amendment-1 text are in `.claude/contract-history/2026-11-04-domain-split-registries.round-1.md` and `.round-2.md`.

### Entities → Registry entry (I-8b)
**I-8b** non-entry heading: in the journal, a `###` heading whose text does not start with a `YYYY-MM-DD` shape (e.g. `### Tag conventions`), and any `#`/`##` heading other than a tier heading. Its lines are section prose: never an entry, never an R1/A1 finding.

### Entities → Registry migration (I-11, I-12)
**I-11** idempotent: a successful apply leaves the tree `current`, and on `current` the plan is empty and exit is 0; `stale-sync` is not current and is migrated. **I-12** no loss, checked on the plan before any write. *Entries:* every input (key, body) maps to an output entry with that key and body, and per registry `occurrences in = kept + moved + merged away`. *Text:* line endings are folded, the BOM dropped and trailing spaces trimmed; the multiset of non-blank source lines must equal the multiset of non-blank destination lines, minus the lines 0001 adds (marker, pointer, skeleton header, leftover heading, provenance and fence lines), plus the removed lines. Removed lines are a closed set, and each is listed with file:line and reason: `project-heading` (a `## Project:` line), `replaced-sync-section` (the marker and pointer lines a stale sync delivered, rewritten once), and `merged-duplicate` (the lines of a second identical copy, or of a bodiless copy of a bodied key). On any mismatch, refuse `content-loss-detected` and write nothing.

### Value Objects → Journal entry grammar
| Journal entry grammar | `### YYYY-MM-DD <sep> <title>` (the tracker's `ENTRY_HEADER` separators); fields Trigger, Source contract, Lesson, Apply when, Tags; optional Areas, Status | "has a body" = an `Apply when:` field with text (§3.4); a `## YYYY-MM-DD` heading or a column-0 bullet outside an entry is not an entry (legacy form, see 0001 step 3) | parser input |

### Value Objects → Migration leftover block
| Migration leftover block | source file; line range; reason (`project-prose`, `legacy-dated-heading`, `legacy-bullet-journal`, `non-entry-heading`); verbatim lines | under the one `## Migration 0001 leftovers (not parsed as entries)` heading of `<REG>/general.md`; one `<!-- leftover from <file>:<a>-<b>, <reason> -->` line, then a fence longer than any backtick run inside it; content byte-equal to source after line-ending folding | 0001 output; lint prints `advisory: leftover <file>:<line>` |

### Value Objects → Migration report
| Migration report | number; project; mode (`dry-run`, `apply`, `refused`); refusal code; plan hash; per registry: kept, moved (key, from, to, reason), merged duplicates, bodiless orphans (hint + ready-to-run `--archive-title-only` command), unclassified, token entries moved, plugin-owned token entries, unverified token entries, unmovable token lines, unparsed Universal lines, leftovers, removed lines, conflicts (key, locations, first body line), counts | refusal code empty unless mode is `refused`; every list may be empty, never absent; plan hash in every mode | `registry-migration-report.md` + `report.json` in `<project>/.claude/cache/registry-migrations/0001-<UTC>/`, JSON on stdout |

### Structural lint rules → R3, R4, A1, Digest
- **R3 project-entry-above-pointer** — in a root file: a `## Project:` heading, or an entry or leftover below the pointer. Also, when `.claude/.project-tokens.json` lists tokens, a Universal entry that holds a token (case-insensitive, `allowed` honoured) and is **client-authored**, meaning its key is not in the Installed plugin root's Universal tier of that registry. A token hit in a plugin-owned entry is advisory `R3 plugin-owned` (the plugin is contaminated; the client cannot edit it). When the plugin copy cannot be read, every token hit is advisory `R3 unverified`.
- **R4 dead-file-reference — ADVISORY.** It lists every Path reference in every registry file (root, domain and journal; fences and leftovers skipped) that resolves under no candidate root, as `advisory: R4 <file>:<line> <path>`. It never changes the exit code, except under `--strict`, where it counts as a finding. Reason: historical citations cannot be rewritten (I-7). This repository has about 25 citations of retired concept contracts (`2026-10-12-dedupe-claude-config.md`, `2026-10-07-worktree-isolation-by-default.md`), plus `tools/sync-plugin.cmd` and `python/scalping_strategy_rl/…`. They are reported and never rewritten. The default (non-structure) mode of `validate_registries.py` keeps its own regex and exit code, unchanged.
- **A1 malformed-entry** — *addition beyond §3.4.* In the journal, it fires on a `###` heading starting with a `YYYY-MM-DD` shape that has an invalid date, no separator, a missing required field, or a Trigger outside {`pre-approval critic`, `post-approval`, `post-impl divergence`, `manual`}. In M/V, it fires on a column-0 `- **title**` with no separator. It is kept because `registry_append.py` refuses the same input. Legacy forms in the Universal tier (`## YYYY-MM-DD`, bullet-form journal lines) are not A1; they print `advisory: unparsed <file>:<line>` (Q16).

### Events → Journal entry appended (I-14)
**I-14** the signature stays `sha1(date + "\|" + title)`, separate from the entry key. The seen cache gains `seeded_files` (resolved absolute paths). On every call, each file of `registry_files("JOURNAL.md")` that is not yet seeded is seeded first: its signatures are marked seen and nothing fires. Only new signatures in already-seeded files fire, plus any `fresh` signature. An old cache (`_initialized` without `seeded_files`) counts as having seeded the root `JOURNAL.md` only. So a client's 345 split-only entries never fire retroactively, and nothing fires twice. **Accepted guard limit** (pinned by a test): a hand-written `post-*` entry in a journal file the tracker has never seen does not fire; the script path does.

### Commands → Append registry entry, Preview / apply
| Append registry entry | `registry_append.py` | `--project` (required), `--registry mechanisms\|vocabulary\|journal`, `--from-file <entry.md\|->`, then `--universal`, `--domain <slug>` [`--create-domain`], or neither (domain = the source contract's area via `derive_area` when that file exists, else `general`, printed). Modes: `--correction-of <title>`; `--archive-title-only <title>`. **By layout state:** on `current`, appends at the end of the Universal tier (before the pointer) or of the domain file. On `pending`/`stale-sync`, appends to the **legacy flat location** and prints `advisory: registry layout <state> — appended to <ROOT>.md:<line>; run registry_migrate.py --dry-run`, exit 0. `--universal` goes to the end of the Universal tier (before a synced pointer, else before the first `## Project:`, else at the end of the file). Otherwise the entry goes to the end of the `## Project: <name>` section matching the project folder's name, else the last `## Project:` section, else the end of the file; a given `--domain` is named in the advisory and not used. The temp file is written with `_atomic_write` and the script prints `file:line`. | `bodiless-input`, `duplicate-entry` (across root and all domain files), `malformed-input`, `unknown-domain` (only on `current`), `correction-target-missing`, `archive-target-missing`, `archive-target-has-body` (2); `layout-unknown`, `registries-absent`, `project-undetermined`, `write-failed` (3). There is no layout refusal on `pending`/`stale-sync`. |
| Preview / apply migration | `registry_migrate.py --dry-run` / `--apply --expect-sha256 <h>`, `--project` required, `--plugin-root <path>` optional (default: `plugin_doctor.find_plugin_root`, the Installed plugin root order) | — | `project-undetermined` (unset and absent), `not-a-git-tree`, `uncommitted-registry-changes`, `conflicting-entry`, `unknown-layout`, `changed-since-preview`, `content-loss-detected`, `symlink-target`, `write-failed` (3); bad arguments 2 |

### Plan hash paragraph
**Plan hash:** `_plan_digest`, over `b"registry-migration"`, `b"0001"`, then per file to write in sorted POSIX relative-path order: path, input bytes or `absent`, planned output bytes. The report is outside the plan. `_plan_digest`, `_atomic_write` and `_backup_write` are **extracted unchanged** from `auto_improve_finish_install.py` into `.claude/scripts/_preview_apply.py`, which uses the standard library only and changes no `sys` state at import. Finish-install imports them back, so one definition exists; a test asserts that finish-install's names are the same objects.

### Migration 0001 steps 1–4 and 6
1. **Parse** every root and domain file into entries, non-entry sections (I-8b), fenced blocks, and legacy forms (`## YYYY-MM-DD` entries, column-0 bullet journal entries).
2. **Universal tier** (above the first `## Project:`; on `stale-sync`, above the synced pointer). Entries, header prose, non-entry headings such as `### Tag conventions`, and fences stay in place. Legacy forms stay too, listed as `unparsed-universal` (Q16). A token-bearing entry depends on the plugin's Universal tier (§4.4, when tokens exist):
   - when its key is in the plugin's Universal tier, it stays (`plugin-owned-token-entry`), because moving it loops: the next sync would put it back and R2 would fire;
   - when the plugin copy cannot be read, it stays (`token-entry-unverified`, re-run with `--plugin-root`);
   - otherwise it moves like a project entry.

   A token line outside any entry is listed as `unmovable-token-line`.
3. **Project content** (under each `## Project:` heading; on `stale-sync`, everything below the synced pointer). Entries move to a destination chosen in §4.2 order: the domain file already holding that key, then a `Tags:` value equal to an existing domain-file name, then the source contract's area when that file exists, then `general` (listed as unclassified). Everything else (prose, sub-headings, tables, legacy pointer lines such as "See domain-specific files…", `## YYYY-MM-DD` entries, bullet-form journal entries) goes **verbatim** into leftover blocks in `general.md`. `## Project:` heading lines are removed and listed. 0001 creates no domain file except `general.md`.
4. **Same key in more than one place** (root and domains, after step 3):
   - identical bodies, both-empty included: merged into one copy at the destination (an existing domain-file location wins), and the other copies are listed as `merged-duplicate`;
   - one bodiless copy and one bodied copy: the bodied copy is kept and the bodiless copy is listed as `merged-duplicate`;
   - two different non-empty bodies: refuse `conflicting-entry`, and the report names every location and each body's first line.

   The operator resolves a conflict by hand while still on layout 1 (keep one body, rename one title, or fold one body into a `Correction` line), commits, and re-runs the dry-run.
6. **Write.** 0001 writes the marker, exactly one pointer section, `general.md` from the skeleton when missing, and the leftover section. I-12 is checked first. The apply writes every backup (`_backup_write`) and every temp file first, then replaces in order with `_atomic_write`; on a failure it restores every replaced file (`write-failed`).

### Reused Mechanisms → Preview-hash apply, Installed plugin root
- **Preview-hash apply** — shared by **extraction**. The three helpers move unchanged into `_preview_apply.py`, and finish-install imports them back. This is not a wholesale import: importing finish-install sets `sys.dont_write_bytecode` (`:93`), inserts into `sys.path` (`:95-96`) and pulls in `pr_merged`/`plugin_doctor` (`:98-99`). It is not a copy either, because a copy needs a drift test and still gives two definitions. It is not a finish-install subcommand, because that script owns the profile and settings files (Option E). The multi-file rollback is the only new code.
- **Installed plugin root** — consumed through `plugin_doctor.find_plugin_root`. `plugin_doctor` does no module-level `sys` mutation. It gives 0001 and R3 the plugin's Universal keys, to tell plugin-owned entries from client-authored ones.

### Confidence
Confidence: Medium-High. Confidence is high on what exists; amendment 2 re-read the finish-install imports, the doctor imports, the tracker cache, the digest regexes, the lookup-test scan roots and `VOCABULARY.md:75,79,91`. It is medium on multi-file rollback on Windows and on how header bullets parse in M/V roots (Uncertain Assumptions).

### Alternatives Considered & Why Rejected
- **Option A (chosen):** layout marker, layout state, shared reader, single writer with legacy fallback, §3.4 lint with R4 advisory, numbered migration with leftovers. The sync tool comes later, through the follow-up.
- **Option B (rejected):** revert to flat registries. The client's split holds content the flat copy lacks.
- **Option C (rejected, deviation from §3.1.2):** a `registries.domains` slot (Q8).
- **Option D (rejected):** hand edits with a lint afterwards. The script refuses bad input before the write.
- **Option E (rejected):** a finish-install migration subcommand, which would give two owners' files to one script.
- **Option F (rejected):** R4 failing on `current`. Historical citations cannot change under I-7, so R4 would be red forever.
- **Option G (rejected):** the writer refusing on unmigrated layouts. Every client would lose its write path, including the `post-impl divergence` lessons.

### Uncertain Assumptions (full amendment-2 list)
- `VERIFIED via .claude/registries/*.md`: the plugin's registries are flat, with no `## Project:` heading and no domain folder, and the 41 journal titles are unique. `JOURNAL.md:28` `### Tag conventions` is outside a fence, and `:19` is inside one. VOCABULARY repeats "Add-on manifest" (`:79`, `:91`) and "Vendored-asset drift (amendment)" (`:86`, `:94`).
- `VERIFIED via grep of .claude/addons`: no `addon.json` declares `kill_switches` (only `angular-tailwind/DISABLED.md` names it), so `VOCABULARY.md:75,79` describe the code.
- `VERIFIED via .claude/.project-tokens.json`: this repository's `tokens` list is empty, so R3 and 0001 move nothing here.
- `VERIFIED via auto_improve_finish_install.py:93-99,275,380,1805`: the side effects named under Preview-hash apply, and the three helpers. Via `plugin_doctor.py`: no module-level `sys.` statement, and `find_plugin_root` at `:163`.
- `VERIFIED via journal-post-approval-tracker.py:43-47,177-193`: one global `_initialized` flag and a flat-file path, which is why `seeded_files` is needed.
- `VERIFIED via agents/*.md frontmatter`: `data-architect` has no shell tool; `fullstack-code-reviewer` has `Bash`.
- `ASSUMED`: on this repository, `--check-structure` gives no finding other than R4 advisories. Its column-0 bullets in the M/V headers are expected to parse as before, since the digest's `BULLET` reads them today. Verification: sub-task 2 runs it, and any other finding is reported as AMENDMENT, never suppressed.

### Failure Modes (replaced entries)
- **FM:** a client has the scripts but not `_preview_apply.py`/`_registry_layout.py`, so the import fails. **Mitigation:** both are in the plugin's scripts folder that the lookup block resolves, and the follow-up stub lists them for the sync's `files` arrays.
- **FM:** the migration half-writes on a locked file. **Mitigation:** backups first, restore on failure, `write-failed`.

### Open Questions Q16, Q17 (amendment-2 wording)
- [ ] **Q16 Legacy-form entries in the Universal tier** (`## YYYY-MM-DD` or bullet-form journal lines above the first `## Project:`) — new in amendment 2. **Recommendation:** leave them in place, reported as `unparsed-universal` by 0001 and as `advisory: unparsed` by the lint, never converted. The Universal tier is plugin-owned and synced, so a conversion would be undone by the next sync. None exists in this repository. Proceeding on this unless you object.
- [ ] **Q17 Tracker on a never-seen journal file** — new in amendment 2. **Recommendation:** accept, as an **Accepted guard limit** pinned by a test, that a hand-written `post-*` entry in a journal file the tracker has never seen does not fire. The alternative fires on every historical entry of a client's split journals (P2-W2). The script path always fires. Proceeding on this unless you object.

### Sub-task constraints replaced (amendment-2 numbering)
- Sub-task 2: "This repository: --check-structure exits 0 (state pending, advisory). Its output has R4 advisory lines for the retired-contract citations, tools/sync-plugin.cmd and the python/... path, and no other R-rule or A1 line. If any other line appears, emit AMENDMENT; never suppress."
- Sub-task 3 tests: "pending: flat placement for --universal / matching ## Project: / last ## Project: / end of file, advisory line, exit 0, --domain named in the advisory; … the Accepted guard limit (hand entry in a never-seen file does not fire) is pinned."
- Sub-task 5: "Extract _plan_digest, _atomic_write and _backup_write unchanged into _preview_apply.py and import them back in auto_improve_finish_install.py" (the extraction moves to the new sub-task 2 in amendment 3, without `_backup_write`).
