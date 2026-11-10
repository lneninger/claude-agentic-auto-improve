# Superseded critique round 1 — 2026-11-04-domain-split-registries

Moved out of `.claude/concepts/2026-11-04-domain-split-registries.md` on 2026-11-04 by `data-architect` (amendment 2), per the budget rule in `.claude/templates/concept-contract.md`. Amendment 1 answered these findings (the `→ Addressed by` lines below are amendment 1's); round 2 then verified them (see `.round-2.md`). The text below is the round as it stood in the contract, unchanged.

## Critique

**Critic:** contract-critic
**Date:** 2026-11-04
**Verdict:** blockers-found

### Findings

- **[BLOCKER] S1–S6 are not the six rules of issue §3.4 (acceptance criterion 4 unmet)**
  - **What is wrong:** §3.4 lists six rules: a journal heading without `Apply when:`; a title in more than one file; a project entry above the pointer in a root file; dead file references in any registry file; a domain file not in the declared `registries.domains`, or a declared domain file missing; a digest older than any registry file, or an entry missing from the digest. S1 (marker) and S6 (malformed) are not in §3.4. The dead-reference rule appears only as an Extension Point, and the digest-staleness rule is missing entirely. S5 checks slugs instead of a declared set, and Option C rejects the §3.1.2 profile slot without saying that the issue asks for it. §3.4's "the digest labels flat-journal entries by tier correctly" is missing too.
  - **Prior artifact ignored:** issue #235 §3.4 and §5 AC 4; `.claude/work-items/2026-11-04-235-domain-split-registries.md:40`
  - **Where in this contract:** `## Data Shapes` — "ASSUMED to match issue §3.4, see Q13"
  - → Addressed by: rules rewritten as R1–R6 in §3.4 order (incl. R4 dead references and R6 digest-stale), A1 kept and marked as an addition, the marker moved out of the lint into the layout state, R5's deviation from `registries.domains` stated plainly, and tier labelling added to the digest generator.
- **[BLOCKER] The writer list does not match §2.2-B (acceptance criterion 2 unmet)**
  - **What is wrong:** §2.2-B names the fullstack-code-reviewer janitor, journal-add, design-first **Steps 3 and 5**, and data-architect; §3.2 adds `skills/ship` as a journal pointer. The contract puts in promote-ui-rule, which §2.2-C lists as a reader, and leaves out design-first Step 5. Its reviewer prompt at `skills/design-first/SKILL.md:323-325` says "append it" to the flat MECHANISMS, VOCABULARY and JOURNAL files.
  - **Prior artifact ignored:** issue §2.2-B, §3.2; brief line 38
  - **Where in this contract:** `### 5.` CONSTRAINTS — "Writers (journal-add, design-first Step 3, … promote-ui-rule Step 5 via /journal-add)"
  - → Addressed by: writers are now exactly §2.2-B (reviewer janitor, journal-add, design-first Steps 3 and 5 incl. lines 166 and 323-325, data-architect append rules); promote-ui-rule is a reader; ship decided under Q11.
- **[BLOCKER] The reader sweep misses shipped files that read or edit the flat registries**
  - **What is wrong:** `skills/application-design/SKILL.md:11` and `skills/website-design/SKILL.md:11` grep the flat `JOURNAL.md` for `ui-evolution`, which is the defect §2.2-C reports for ui-ux-designer. `skills/validate-registries/SKILL.md:3,50` limits itself to the flat files and tells the reader to edit the registry directly. `skills/north-star/SKILL.md:106` cites "MECHANISMS.md (project section)", which layout 2 removes. None of these is in any Files to touch list, so block 5's text scan either fails or never sees them.
  - **Prior artifact ignored:** JOURNAL.md 2026-11-02 "A sweep … must route EVERY local reader …" (claimed as heeded)
  - **Where in this contract:** `## Integration Surfaces` — "every registry reader (6 scripts, 4 agents, 5 skills)"
  - → Addressed by: sub-task 6 now covers those four skills plus every §2.2-C reader and the templates `concept-contract.md`, `north-star.md`, `followup-stub.md`; CONTRIBUTING.md is in sub-task 7; the text scan covers agents, skills and templates.
- **[BLOCKER] The plugin's own registries break S4 and I-6, and nothing gives them a way out**
  - **What is wrong:** VOCABULARY.md has the same title twice, with different bodies: "Add-on manifest" (`VOCABULARY.md:79`, `:91`) and "Vendored-asset drift (amendment)" (`:86`, `:94`). "<term> (amendment)" is a deliberate convention for repeated titles. So block 1's "expected: S1 only" is false. Block 6's "--check-structure exits 0" cannot be reached without rewriting entries, which I-7 forbids. Migration 0001's same-key/different-body rule refuses `conflicting-entry`. `archived-title-only` covers bodiless entries only.
  - **Prior artifact ignored:** JOURNAL.md 2026-10-30 "A rule that refuses must give already-delivered work a named way out"; 2026-11-01 "A shared reader reused by a stricter consumer must be re-checked …"
  - **Where in this contract:** `### 1.` — "the repository's own registries checked (expected: S1 only, until block 6)"; `## Uncertain Assumptions` covers S6 only
  - → Addressed by: new sub-task 1 reconciles both duplicates by hand into `Correction` lines with the exact wording in its TASK block (approved with the contract), I-7 names it as the one pre-layout exception and replaces the "(amendment)" convention, the expected lint result is corrected to zero findings, and 0001's conflict rule now says how the operator resolves.
- **[BLOCKER] Block 5 adds script calls to skills that carry lookup blocks, but its test list leaves out the lookup test, and it never says how a client finds the script**
  - **What is wrong:** design-first, promote-ui-rule, verify-before-done and ship each carry `py -3 "$…"` lookup blocks. Block 5 adds `registry_append.py` and `--check-structure` commands to them, but runs only `test_plugin_text_scans.py`, not `.claude/scripts/tests/test_skill_script_lookup.py`. "one PowerShell-runnable registry_append.py command each" never says how an agent or skill in a client project finds the script. Under a plugin-delivered install the client's `.claude/scripts/` does not contain it.
  - **Prior artifact ignored:** JOURNAL.md 2026-10-15 "A skill that edits a block pinned by a lookup-block test must name that test"; 2026-10-15 "Locate a script from the plugin root …"
  - **Where in this contract:** `### 5.` — "Run: py -3 .claude/scripts/tests/test_plugin_text_scans.py"
  - → Addressed by: sub-task 6 reuses the standard lookup block (Reused Mechanisms "Script lookup block"), passes `--project "$CLAUDE_PROJECT_DIR"`, lists and runs `test_skill_script_lookup.py`, and routes data-architect's appends through its caller (Q14).
- **[BLOCKER] Today's sync can deliver the layout-2 marker into a layout-1 client, and I-1 then reports that client as current**
  - **What is wrong:** until the follow-up lands, the existing sync copies the plugin's Universal tier into a client's flat root, above the client's own `## Project:` sections. After block 6 that tier starts with `<!-- registry-layout: 2 -->` and ends with `## Project tier`. I-1 then reads layout 2, `--check` exits 0 and 0001 does nothing (I-11), while the project content stays in the root and S2 stays red with no remedy. No failure mode covers this case.
  - **Prior artifact ignored:** `MECHANISMS.md:52` Section-scoped registry sync ("compares and updates the Universal section alone"); JOURNAL.md 2026-10-04 "Detect an install mode by what the sync actually delivers"
  - **Where in this contract:** `## Data Shapes` I-1 — "no marker = layout 1"; `## Failure Modes & Mitigations` has no such row
  - → Addressed by: I-1 requires marker AND no project content in roots AND `general.md` present; the new state `stale-sync` makes `--check` exit 6, 0001 migrates it (I-11), and a failure mode plus a `stale-sync` fixture in sub-task 5 cover it.
- **[WARN] Migration 0001 ignores §4.4 (move project-token lines) without raising it as an Open Question**
  - **What is wrong:** §4.4 asks 0001 to move project-token lines out of the Universal tier into domain files. The contract only reports them, in a Non-Goal, so a client stays blocked at the sync's exit-5 project-name check.
  - **Prior artifact ignored:** issue §4.4; `MECHANISMS.md:54` Project-name check
  - **Where in this contract:** `## Non-Goals` — "Moving Universal entries that name a project automatically (reported only)"
  - → Addressed by: 0001 step 1 moves token-bearing Universal entries (user decision b), lists each move, reports token lines outside entries, and keeps I-12 and the count-conservation test; the Non-Goal is removed.
- **[WARN] 0001's classification and report shape differ from §4.2, and no Open Question says so**
  - **What is wrong:** §4.2 classifies entries in this order: domain membership, then `Tags:`, then the source contract's area, then `general`. It asks for a `registry-migration-report.md` that lists bodiless orphans with a recovery hint, plus anything unclassified. The contract sends every project entry to `general.md` and writes only a JSON report.
  - **Prior artifact ignored:** issue §4.2
  - **Where in this contract:** `## Commands` — "Entries under any `## Project:` heading move to `general.md`"
  - → Addressed by: 0001 step 2 uses the §4.2 order, and the report is `registry-migration-report.md` plus `report.json`, listing orphans with a recovery hint and unclassified entries.
- **[WARN] The journal entry key includes the date, but the issue's uniqueness rule is by title**
  - **What is wrong:** §3.1.4 and §3.4 define a duplicate as one title in more than one file, and the client's counts ("titles present in both copies") are by title. With a date+title key, the same lesson under two dates escapes S4 and the 0001 merge.
  - **Prior artifact ignored:** issue §3.1.4, §3.4, §2.2-A
  - **Where in this contract:** `## Business Concept` — "for the journal the date plus normalised title"
  - → Addressed by: the key is the normalised title for all three registries (this repo's 41 journal titles verified unique); I-14 keeps the tracker's date+title signature as a separate thing.
- **[WARN] S1 makes verify-before-done fail on every layout-1 client, but §7 says the lint is advisory until layout 2**
  - **What is wrong:** S1 is a NOT-READY reason, so every client that upgrades before migrating fails verify-before-done, and so does this repository between blocks 5 and 6. Q10 covers the landing only.
  - **Prior artifact ignored:** issue §7 "lint is advisory until the client's applied layout version is 2"
  - **Where in this contract:** `## Extension Points` — "a finding is a NOT-READY reason"
  - → Addressed by: the lint is advisory (exit 0 plus an `advisory:` line) whenever the layout state is not `current`, and verify-before-done treats only exit 1 as NOT-READY.
- **[WARN] Several items the issue asks for are dropped without being raised as questions**
  - **What is wrong:** the dropped items are: the doctor's "client has body-less journal entries: N" (§4.2); "say which domains map to which contract focus" for data-architect and contract-critic (§3.3); `registry_files(name, domains=None)` (§3.3); `--domain` / `--from-file` / `--universal`, with the domain defaulting from `area-mapping.json` (§3.2). The contract uses `--tier` instead.
  - **Prior artifact ignored:** issue §3.2, §3.3, §4.2
  - **Where in this contract:** `## Commands` "Append registry entry"; `### 4.` Doctor constraint
  - → Addressed by: all four are now included: the doctor count (sub-task 5), the focus-to-domain rule for data-architect and contract-critic (sub-task 6), `registry_files(name, domains=None)` (Reused Mechanisms), and `--universal`/`--domain`/`--from-file` with the area-mapping default (Commands).
- **[WARN] Preview-hash apply is re-implemented beside the original rather than extended**
  - **What is wrong:** the mechanism's Extend-by line is "return plan, apply and refusal dicts of the same shape from a new subcommand". The contract rebuilds the hash, backup, `os.replace` and symlink refusal in a new script and never pins the plan-hash definition (a length-prefixed SHA-256), so two hash definitions can drift apart. Reused Mechanisms says "the reason is recorded in New Mechanisms", but the runner's entry gives no reason for not importing it.
  - **Prior artifact ignored:** `MECHANISMS.md:64` Preview-hash apply; JOURNAL.md 2026-10-28 "Do not promote a mechanism the registry already describes as an extension seam"
  - **Where in this contract:** `## Reused Mechanisms` — "Not by import … the reason is recorded in New Mechanisms"
  - → Addressed by: `_plan_digest` and `_atomic_write` are imported (one definition, pinned by a test), the plan parts are written out, and the reason for not adding a finish-install subcommand is stated (Reused Mechanisms, Option E).
- **[WARN] The Value Objects table has no invariant column**
  - **What is wrong:** it does not say which fields can be empty: the report's refusal code, `moved (from, to)`, and the Layout state's found layout when `absent`.
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md` Data Shapes
  - **Where in this contract:** `### Value Objects` — "Migration report" and "Layout state" rows
  - → Addressed by: an Invariants column now states emptiness for every value object.
- **[WARN] The follow-up stub does not anchor the rest of acceptance criteria 7 and 9**
  - **What is wrong:** the stub leaves out §4.2's repo-to-plugin refusal ("refuses to publish registry files whose layout version differs"). It also leaves out the `registry_layout` config key and `.sync-state` applied version, and the `tools/SYNC.md` 4.3 procedure ("sync docs updated").
  - **Prior artifact ignored:** issue §4.2, §5 AC 7 and AC 9
  - **Where in this contract:** `.claude/concepts/followups/2026-11-04-sync-tool-registry-layout-gate.followup.md` § "Suggested next step"
  - → Addressed by: the stub now lists the repo-to-plugin refusal, the `registry_layout` key, the applied-layout state, the `stale-sync` handling and the `tools/SYNC.md` 4.3 procedure.
- **[NIT] Count mismatch** — "6 scripts, 4 agents, 5 skills", but block 5 lists six skills.
  - → Addressed by: Integration Surfaces lists 6 scripts + 1 hook, 4 agents, 9 skills, 3 templates, matching sub-task 6.
- **[NIT] Second meaning of "layout"** — "Registry layout" and "Layout state" give "layout" a second meaning beside "Layout defect" and "Layout warning" (`VOCABULARY.md:70,72`). They are not synonyms, but readers of `--status --json` may confuse them.
  - → Addressed by: every new term carries "Registry" ("Registry layout state"), and the Business Concept says it is not a delivery-layout value.
- **[NIT] ship is listed for a block that expects to leave it unchanged** — `skills/ship/SKILL.md` is in block 5's Files to touch, although the grep found no registry text in it (verified) and Q11 expects no change. The concept gate still allows edits to it.
  - → Addressed by: removed from every Files to touch (Q11).
- **[NIT] Budget** — with this critique the contract probably exceeds its 12,000-token budget.
  - → Addressed by: questions shrunk to one line each; Budget raised to 18,000 with the reason in the header.

### Applicable journal entries

- **2026-11-02 — A sweep … must route EVERY local reader** — violated, see BLOCKER 3
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — heeded for bodiless entries; violated for duplicates (BLOCKER 4)
- **2026-11-01 — A shared reader reused by a stricter consumer …** — heeded for separators; violated for "(amendment)" duplicates (BLOCKER 4)
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test …** — violated (BLOCKER 5)
- **2026-10-15 — Locate a script from the plugin root …** — violated (BLOCKER 5)
- **2026-10-04 — Detect an install mode by what the sync actually delivers** — violated (BLOCKER 6)
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — partly heeded (layout reader); see WARN on Preview-hash apply
- **2026-10-30 — One shared reader must own the filtering** — heeded by `_registry_layout`
- **2026-10-15 / 2026-10-16 — project must be told / both refusal cases** — heeded by required `--project` and `project-undetermined`, unset and absent
- **2026-10-17 — Judge "identical" by git's view** — heeded by I-12 (line endings folded, BOM dropped)
- **2026-10-28 — A new term's definition must be true against every existing member** — heeded ("layout 1 = every unmarked file")
- **2026-10-22 — An accepted critic WARN … must amend the contract body** — applies at approval (Q13 now answerable from the issue text)
- **2026-10-30 — A delivery rule must name every route into delivery** — not addressed (the contract adds no delivery rule)

### What the critic did not check

- `pr_merged.py --contract … --status --json` was not run (no shell). Checked by hand instead: headings 1–7 parse; `python-ai-developer` is in `DEFAULT_IMPLEMENTERS` (`pr_merged.py:51-57`) and `fullstack-code-reviewer` is in `DEFAULT_REVIEW_GATES` (`:62-71`); every block has `Depends on` and Files; no block lists a `MANIFESTS` file (`check_version_bump.py:25`), so `sub-task-raises-version` cannot fire. The Work Item Brief header is present.
- `INTEGRATION.md` and `.claude/.scout-cache/registry-digest.md` are absent in this worktree. The registries have no project tier, so only the Universal tier was checked.
- `derive_area.py` / `cross_area_scan.py` were not run. `area-mapping.json` is empty, so fallback was assumed.
- There are no active north-stars, so item 13 does not apply.
