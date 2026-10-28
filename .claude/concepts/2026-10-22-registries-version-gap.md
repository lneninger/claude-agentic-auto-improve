# Concept Contract — Version-bump check must treat files the doctor copies as shipped

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-22
**Requested by:** user
**Status:** implemented
**Implemented:** 2026-10-23, automatically, by pr_merged.py after https://github.com/lneninger/claude-agentic-auto-improve/pull/78; 2 checklist items from review reports, 0 with no structured evidence; not performed (disclosed on #77): none; owner confirmed resolved: none
**Work Item Brief:** .claude/work-items/2026-10-22-77-registries-version-gap.md
**Tracking issue:** #77

---

## Business Concept

- **What is this thing, in domain language?**
  The version-bump check decides whether a pull request changed a *shipped* file. Shipped files need a plugin version raise, because installed copies only update when the version changes. The check holds a list of exempt folders. That list includes `.claude/registries/`. But the plugin doctor copies three files from that folder into user projects: `MECHANISMS.md`, `VOCABULARY.md` and `JOURNAL.md`. So the exempt list and the doctor disagree about whether those three files reach users. This contract makes them agree, adds a test that keeps them agreeing, and writes down how often a registry append raises the version.

- **What the doctor copies, and how the check classes it today.** These are all the `plugin_doctor.REQUIREMENTS` entries that carry content from the plugin tree. Entries of kind `dir` create an empty folder and copy nothing.

  | Requirement (path = source) | Kind | `is_shipped` today | Agrees? |
  |---|---|---|---|
  | `.claude/templates/concept-contract.md` | copy | shipped | yes |
  | `.claude/registries/MECHANISMS.md` | copy | **exempt** (prefix `.claude/registries/`) | **no** |
  | `.claude/registries/VOCABULARY.md` | copy | **exempt** | **no** |
  | `.claude/registries/JOURNAL.md` | copy | **exempt** | **no** |
  | `.claude/project-profile.md` | scaffold, copied from `source` | shipped | yes |
  | `.claude/area-mapping.json`, `.claude/work-item-conventions.json` | scaffold, inline stub in the script (no `source`) | n/a; their content is `plugin_doctor.py` itself, which is shipped | yes |
  | `.claude/concepts`, `.claude/work-items`, `.claude/north-stars`, `.claude/orchestrator/results` | dir | the requirement path itself has no trailing slash, so `is_shipped(".claude/concepts")` is True; files UNDER those folders are exempt (prefix with slash) | yes. Nothing is copied, and these exemptions are out of scope. Tests assert on a file under each folder, never on the bare folder path. |
  | `.claude/settings.json` | manual | shipped (never written by the doctor) | n/a |

  The disagreement is exactly the three registry files. Today `.claude/registries/` holds only those three files.

- **A fact that bounds the stakes.** The doctor never overwrites (`apply_fixes`, "Never overwrite"). A registry append therefore reaches only projects that run `--fix` while the file is still missing, meaning new installs. The doctor alone therefore never refreshes registries in existing projects. The gap is that a new project set up from an old cached plugin gets the old seed registries. Amended after the critique: this bounds only the doctor. The section-scoped registry sync (MECHANISMS.md, "Section-scoped registry sync") updates the Universal tier of all three registries in consuming projects and can resolve to a versioned install, so a version raise can matter to existing projects too.

- **Existing terms that apply:** "Vendored asset" (VOCABULARY.md). The registries and journal belong to the "Two-tier registry" MECHANISM (MECHANISMS.md), not a vocabulary term. No other vocabulary is touched.
- **New terms proposed for VOCABULARY.md:** none.

---

## End-User View

Not applicable. Reason: no Angular or UI surface. The change touches one Python check script, its test, the project rules file and the four version manifests.

---

## Data Shapes

Not applicable. Reason: no entity, value object, event or command is introduced. The only "shape" is the classification rule `is_shipped(path)`. Its invariant is new:

- **Invariant I1:** for every `Requirement` in `plugin_doctor.REQUIREMENTS` that carries a `source`, `is_shipped(source)` is true. This is enforced by a test, never at runtime. Amended: `.github/workflows/version-bump.yml` runs the check script only, not the test suite, so the test takes effect when `/verify-before-done` and the reviewer run it. Adding the test to CI is a follow-up, not part of this change.
- **Invariant I2:** a pull request that changes any of those sources without raising the version fails the check (exit 1). This follows from I1 and the existing `evaluate`.

---

## Reused Mechanisms

- **`check_version_bump.is_shipped` / `evaluate`** (the CLAUDE.md version rule) is extended by changing `EXEMPT_PREFIXES` only. `evaluate`, `versions_in` and `main` stay as they are.
- **MECHANISMS.md entries this rule touches:** "Adaptive Engineering Journal" (its three append triggers produce registry-only changes), "Section-scoped registry sync" and "Two-tier registry" (the registries' delivery paths). None is changed.
- **`plugin_doctor.REQUIREMENTS`** is consumed as-is and read by the test through an import. The import has no side effects (verified): at module level `plugin_doctor.py` holds only stdlib imports, a dataclass, constants and function definitions. `_claude_paths` is imported lazily inside `_installed_plugin_root`. The test reaches it with the same `sys.path.insert(<scripts folder>)` the suite already uses.

## New Mechanisms (if any)

None. The test couples two existing scripts. It adds no machinery.

---

## Extension Points

- `.claude/scripts/check_version_bump.py`: the `EXEMPT_PREFIXES` tuple, plus a short comment stating the rule ("a file the doctor copies into user projects is shipped; see the test").
- `.claude/scripts/tests/test_check_version_bump.py`: new test methods (see the handoff).
- `CLAUDE.md` § "Every change to shipped plugin files bumps the plugin version": one or two sentences recording the decision. This meets acceptance criterion 3. `CLAUDE.md` is itself exempt.
- The five version entries move from 0.9.17 to 0.9.18: `plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json`, and `.claude-plugin/marketplace.json` (top-level `version` and `plugins[0].version`).

## Integration Surfaces

Not applicable. Reason: the work stays inside the plugin's Python tooling, with no API, event or DTO boundary. The CI workflow `.github/workflows/version-bump.yml` invokes the script unchanged.

## Adjacent Areas

Cross-area scan run by the main session: `cross_area_scan.py` returned no adjacent areas (the area map declares none), and `derive_area.py` returns `uncategorized`. Manual assessment of the flows this rule touches:

| Area | Decision | Implication / Reason | Handle |
|------|----------|----------------------|--------|
| registry-appending flows (reviewer janitor duties, `/journal-add`, journal appends at `/design-first` approval) | decided: accept the cost | Under the user's Q1 answer, any pull request that appends to a copied registry must raise the plugin version. These flows are not changed here. Their authors batch registry appends with a version-raising change, or raise a patch version for a registry-only pull request. The review sub-task of THIS contract must not append to registries (see the TASK constraint). | CLAUDE.md sentence; no code change to the flows |

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event.

---

## Non-Goals

- `.claude/orchestrator/state/`, which stays non-exempt by design.
- The README hooks count.
- Every other entry on the exempt list, including the four `dir` requirement folders.
- Changing the doctor (no overwrite or refresh of existing user registries).
- A runtime import of `plugin_doctor` from `check_version_bump`. The coupling lives in the test only, so the CI check keeps no new dependency.

---

## Confidence

Confidence: Medium-High. One assumption (below, ASSUMED) carries the cost estimate for Q1, and the user chose the rule knowing that cost. The classification table and the side-effect-free import were verified by reading both scripts. The commit-frequency figure is commit-level, not pull-request-level (see Q1).

## Alternatives Considered & Why Rejected

Laid out in Open Question Q1. Chosen by the user: the registries become fully non-exempt, with the test from (c) as the guard. Rejected: (d) seed-only allow-list, which bends the issue's first criterion into "unless allow-listed"; and a label-based one-time-raise rule, which needs a new mechanism.

## Uncertain Assumptions

- `VERIFIED via plugin_doctor.py:59-88`: the only `copy` requirements are the template and the three registries. `project-profile.md` is copied through `source` as a scaffold.
- `VERIFIED via check_version_bump.py:19-29`: the prefix `.claude/registries/` makes all three copied registries non-shipped. The template and the profile are shipped.
- `VERIFIED via plugin_doctor.py:9-14, 218-219`: the doctor never overwrites an existing file.
- `VERIFIED via Glob`: `.claude/registries/` contains only the three copied files today.
- `VERIFIED via manifests`: all five version entries read `0.9.17`.
- `ASSUMED`: the pull-request-level count of registry-only pull requests is low. Measured: 16 commits from master's last 120 non-merge commits touched one of the three files. 7 changed `plugin.json` in the same commit and 9 did not. A bump may sit in a sibling commit of the same pull request. If this is wrong, the cost of option (a)/(b) rises. Verification path: group those 9 commits by pull request.

## Failure Modes & Mitigations

- **FM:** a future `copy` requirement is added under an exempt prefix, and the gap silently reopens.
  - **Mitigation:** the test iterates `REQUIREMENTS`, so new entries are covered automatically whenever the suite runs (`/verify-before-done`, the reviewer). CI does not run the suite yet; that is a follow-up.
- **FM:** the test passes vacuously if `REQUIREMENTS` is renamed or emptied.
  - **Mitigation:** the test asserts it found at least the four known copied sources by name.
- **FM:** registry-only pull requests start failing CI unexpectedly.
  - **Mitigation:** CLAUDE.md states the rule. The failure message already names the files and says to raise the version.

---

## Open Questions for User

- [x] **Q1 — ANSWERED (2026-10-22): "Fully non-exempt, raise every time", i.e. option (a), with the test from (c) as the guard.** The user chose this after being shown the critic's BLOCKER and an alternative (seed-only allow-list, which was recommended). Accepted cost: any pull request that appends to a copied registry must raise the plugin version. The implementation is the same as the earlier (b)+(c) text below, because the folder holds only the three copied files. Original question text follows.
  **Q1 (original) — Does an append to the three copied registry files need a version raise, and how should the exempt list be shaped?**
  Context: the doctor copies these files only into projects that lack them, and never overwrites. A raise therefore only refreshes the seed that *new* projects receive.
  Cost data (commit-level, not pull-request-level): from master's last 120 non-merge commits, 16 touched a copied registry. 7 of them changed `plugin.json` in the same commit. 9 did not (dd68697, ee8f67f, 35ccbd6, 99f6be6, 6ffe46a, 4f8ef0c, ed5a9ac, 2091f42, 6c1404a). Most of those 9 likely sit in pull requests that already carry a bump. Appends often ride with the code that required one.
  - **(a) Make `.claude/registries/` non-exempt entirely.** Cost: every pull request that touches a registry and nothing else (a `/journal-add`, a janitor-only or record pull request) needs a five-line patch bump. Simplest rule.
  - **(b) Exempt only registry files the doctor does NOT copy.** Today the folder holds only the copied three, so in effect this equals (a): remove the prefix. A future non-copied registry file (for example a per-domain `MECHANISMS/<domain>.md`) would be shipped by default. Exempting it would take an explicit prefix later. Same cost as (a).
  - **(c) Keep them exempt, plus a test that fails when a copied file is exempt.** The test fails today, so on its own it forces (a) or (b). It is not a standalone option. It is the guard every option needs.
  - **(d) Declare the registries "seed-only".** Keep them exempt and give the test an explicit, commented allow-list of copied-but-seed files. Cost: no extra bumps. But new installs from a cached version get stale seeds, and it bends acceptance criterion 1 ("a test fails if any copied file is classed as not shipped") into "unless allow-listed". The issue author would have to accept that reading.
  - **Recommendation: (b) + (c).** Remove `.claude/registries/` from `EXEMPT_PREFIXES`, and add the test that derives the copy list from `plugin_doctor.REQUIREMENTS`. Every pull request touching a copied registry raises the patch version. Record that sentence in CLAUDE.md. Rationale: it meets all three acceptance criteria literally, and the measured cost is small. **The handoff below is written for this answer. If the user picks (d), amend the Data Shapes invariant I1 and the TASK block before approval** (JOURNAL 2026-10-22).

- [x] **Q2 — ANSWERED (2026-10-22): accepted the recommendation (CLAUDE.md sentence plus a comment beside the exempt list).** **Where should the decision be written down?** Recommendation: two places. One sentence in CLAUDE.md under the version rule, plus a one-line comment beside `EXEMPT_PREFIXES`. The alternative is the comment only, which is invisible to authors who read CLAUDE.md.

---

## Critique

**Critic:** contract-critic
**Date:** 2026-10-22
**Verdict:** blockers-found

### Findings

- **[BLOCKER] Q1's cost analysis leaves out the flows that append to registries, and this contract's own review sub-task is one of them**
  - **What is wrong:** under (b)+(c), every pull request that appends to a copied registry must raise the version. But the reviewer's janitor duty appends to MECHANISMS.md, VOCABULARY.md and JOURNAL.md "after the review passes", and a review-gate sub-task's `Files to touch` names exactly one path (the review artefact), so it can never list the five manifests. Sub-task 2 here (`t2-review-fullstack-code-reviewer.md`) merges after sub-task 1 has already used 0.9.18, so any janitor append in it fails `version-bump` CI with no way to comply as written. The same holds for the `/design-first` Step 3 journal appends made at approval, and for `/journal-add`. The Adjacent Areas row dismisses all of these as "not applicable", citing a journal lesson about amending contracts that has nothing to do with them. The 16-commit sample is the wrong measure, because it counts commits, not the pull requests these flows produce.
  - **Prior artifact ignored:** `agents/fullstack-code-reviewer.md:248-297` (Registry janitor duties); `.claude/templates/concept-contract.md:376-382` (a review gate names exactly one path); `MECHANISMS.md:40` (Adaptive Engineering Journal: three append triggers); `skills/design-first/SKILL.md:166` (journal append at approval); `skills/journal-add/SKILL.md:104` (writes only JOURNAL.md, so a `/journal-add` pull request has no manifests).
  - **Where in this contract:** `## Adjacent Areas`: "registries authoring flow (`/journal-add`, reviewer janitor appends) | not applicable | Their behaviour is unchanged"; `## Open Questions for User` Q1: "the measured cost is small".
  - → Addressed by: the user saw the BLOCKER and chose the literal rule anyway (Q1 answer (a)), accepting that registry appends raise the version. Mitigations written into the contract: the Adjacent Areas row now records the decision and the cost; the review sub-task of this contract must not append to registries (TASK constraint in block 2), and a needed append is reported in its handoff instead; the CLAUDE.md sentence tells authors to batch registry appends with a version-raising change. The cost estimate is labelled ASSUMED and commit-level.
- **[WARN] The CLAUDE.md edit leaves the "documentation only needs no bump" sentence contradicting the new rule**
  - **What is wrong:** CLAUDE.md line 16 says "A change that touches only documentation or work-item briefs needs no bump". The three registries are markdown documentation by any plain reading, and line 5's list of shipped things "(scripts, hooks, skills, agents, templates)" leaves them out. The TASK block only adds a sentence under the heading and amends neither line, so the file will state both rules.
  - **Prior artifact ignored:** `CLAUDE.md:5` and `CLAUDE.md:16`; JOURNAL 2026-10-05 "Text delivered to the model must say which rule wins against a skill's gate" (state which rule wins when two rules collide).
  - **Where in this contract:** `## Implementation Handoff` → TASK CONSTRAINTS: "CLAUDE.md: under ... add that the registries the doctor copies ... count as shipped".
  - → Addressed by: the TASK block now also amends CLAUDE.md line 5 (the shipped list) and line 16 ("documentation only needs no bump") so it states one rule.
- **[WARN] Invariant I1 is "enforced by a test" that no CI workflow runs**
  - **What is wrong:** the only workflow is `.github/workflows/version-bump.yml`, and it runs `check_version_bump.py`, never the test suite. So the new test that "keeps them agreeing", and the Failure Mode 1 mitigation ("new entries are covered automatically"), only take effect when someone runs pytest by hand. Meanwhile the CLAUDE.md rule this contract extends calls itself "enforced, not advisory".
  - **Prior artifact ignored:** `CLAUDE.md:14` ("This is enforced, not advisory"); `.github/workflows/version-bump.yml:14-15`.
  - **Where in this contract:** `## Data Shapes`: "This is enforced by a test, never at runtime."; `## Failure Modes & Mitigations` FM 1.
  - → Addressed by: the invariant and FM 1 now say the test takes effect when the suite is run (`/verify-before-done`, the reviewer); running it in CI is a recorded follow-up, not part of this change.
- **[WARN] The classification table misstates the `dir` rows, which makes TASK test (3) ambiguous**
  - **What is wrong:** the requirement paths have no trailing slash (for example `.claude/concepts`), and `is_shipped(".claude/concepts")` returns True, because `EXEMPT_PREFIXES` holds `.claude/concepts/` with the slash. So the table's "dir | exempt" is true only for files under those folders, not for the requirement path itself. An implementer who iterates `REQUIREMENTS` of kind `dir` and asserts "exempt" gets a failing test. One who asserts "as before" pins shipped=True, which contradicts the table.
  - **Prior artifact ignored:** `.claude/scripts/check_version_bump.py:19-29`; `.claude/scripts/plugin_doctor.py:60-64`; JOURNAL 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case" (a VERIFIED claim must hold on the edge input).
  - **Where in this contract:** `## Business Concept` table row "`.claude/concepts`, ... | dir | exempt"; TASK block (3): "the four dir requirements ... still classify as before".
  - → Addressed by: the table row is corrected and TASK test (3) now asserts on a file under each exempt folder, never on the bare folder path.
- **[WARN] Confidence High despite an ASSUMED entry**
  - **What is wrong:** `## Confidence` says High, while `## Uncertain Assumptions` carries one `ASSUMED` (that few pull requests touch only a registry), and that is exactly the input Q1's cost argument rests on.
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md:241-249` (Confidence format and breakdown).
  - **Where in this contract:** `## Confidence`: "Confidence: High."; `## Uncertain Assumptions`: "`ASSUMED`: the pull-request-level count of registry-only pull requests is low."
  - → Addressed by: Confidence is now Medium-High and names the assumption.
- **[WARN] The "bounds the stakes" claim leaves out the sync path**
  - **What is wrong:** "Existing projects never receive registry changes, with or without a version raise" is true only for the doctor. The section-scoped registry sync updates the Universal tier of all three registries in consuming projects, and its plugin discovery can resolve to `CLAUDE_PLUGIN_ROOT`, a versioned install. So a version raise can matter to existing projects too, and the claim understates what (d) would cost.
  - **Prior artifact ignored:** `MECHANISMS.md:46` (Bidirectional sync, plugin discovery `CLAUDE_PLUGIN_ROOT` first); `MECHANISMS.md:48` (Section-scoped registry sync); `VOCABULARY.md:32` (Vendored asset).
  - **Where in this contract:** `## Business Concept`: "Existing projects never receive registry changes, with or without a version raise."
  - → Addressed by: the claim is narrowed to the doctor and the section-scoped sync is named.
- **[WARN] Adjacent Areas still carries an unfinished task to do before approval**
  - **What is wrong:** the section says the scan was "NOT run" and "must be run by the main session before approval, and this table amended". That is an open action in prose, not a decision. The main session reports that the scan has since run and returned no areas (area map empty, derive_area gives `uncategorized`), but the section still reads as it did before the scan, and its "plugin scripts" in-scope row names an area that does not exist in `area-mapping.json`.
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md:174-184` (the single-line not-applicable form); `.claude/area-mapping.json:14` (`"areas": {}`); JOURNAL 2026-10-22 "An accepted critic WARN or answered Open Question must amend the contract body before approval".
  - **Where in this contract:** `## Adjacent Areas`: "Cross-area scan NOT run."
  - → Addressed by: the section now records the scan result (no adjacent areas) and the decision for the registry-appending flows.
- **[NIT] Reused Mechanisms cites no MECHANISMS.md entry.** The two scripts listed are not registry entries. The relevant entries are `MECHANISMS.md:40` (Adaptive Engineering Journal), `:48` (Section-scoped registry sync) and `:57` (Two-tier registry). The template expects at least one (`concept-contract.md:102`).
- **[NIT] The "Two-tier registry" is cited as a VOCABULARY.md term.** It is a MECHANISMS.md entry (`MECHANISMS.md:57`); VOCABULARY.md has no such term.
- **[NIT] Alternatives Considered only points to Q1.** Q1 does give tradeoffs, but this section itself lists no rejected option (`concept-contract.md:253-264`).
- **[NIT] The TASK block runs `py -3 -m pytest` on a unittest-style suite.** This works only if pytest is installed. `py -3 -m unittest` is what the file's own `__main__` supports (`test_check_version_bump.py:76-77`).

### Applicable journal entries

- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval**: heeded by the note in Q1 to amend invariant I1 and the TASK block when the answer is (d). Not yet heeded by the Adjacent Areas section; see the WARN above.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures**: not addressed. No harm here: the change tightens the check, and the critic confirmed that no existing fixture in `test_check_version_bump.py` uses a `.claude/registries/` path.
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate**: violated in spirit by the CLAUDE.md edit; see the WARN above.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case**: partly violated; see the WARN on the `dir` rows.

### What the critic did not check

- INTEGRATION.md and `.claude/.scout-cache/registry-digest.md` do not exist in this checkout. The integration-surface checks (items 7 and 12) were judged from the contract alone, and both are honestly not applicable.
- `.claude/north-stars/` does not exist, so there are no active north-stars and item 13 produced no findings.
- The 16/9/7 commit counts and the nine commit hashes in Q1 were not re-measured (the critic has no shell).
- The critic filled the template's empty `## Critique` placeholder in place rather than adding a second `## Critique` heading at the end of the file.

---

## Lessons referenced

- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval**: heeded by Q1's instruction to amend invariant I1 and the TASK block when the answer differs from the recommendation. Cross-reference: `.claude/registries/JOURNAL.md` § Universal lessons.
- Orthogonal to north-stars: none active.

---

## Implementation Handoff

### 1. Version check (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/check_version_bump.py`
- `.claude/scripts/tests/test_check_version_bump.py`
- `CLAUDE.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**Pre-written TASK block:**
```
TASK: Make the version-bump check treat every file plugin_doctor copies into user projects as
shipped, add a test that keeps the two scripts in agreement, record the policy, and raise the
plugin version to 0.9.18.
CONTEXT: concept contract at .claude/concepts/2026-10-22-registries-version-gap.md (Q1 answer: (a), fully non-exempt, with the test from (c))
FILES: as listed above
CONSTRAINTS:
  - check_version_bump.py: remove ".claude/registries/" from EXEMPT_PREFIXES; add a one-line
    comment there: a file plugin_doctor copies into user projects is shipped, enforced by
    test_check_version_bump.py. Do not change evaluate, versions_in or main. Do not import
    plugin_doctor from this script.
  - test_check_version_bump.py: import plugin_doctor via the existing sys.path insert (its
    import has no side effects). Add:
      (1) for every Requirement with a non-empty source, assertTrue(cvb.is_shipped(r.source))
          with the path in the failure message; plus assert the set of sources checked contains
          the template, the three registries and .claude/project-profile.md (no vacuous pass);
      (2) a registry-only change (".claude/registries/JOURNAL.md") with an unchanged version
          evaluates to 1, and with a raised version to 0;
      (3) a file UNDER each of the four dir requirement folders and under the other exempt
          prefixes still classifies as exempt (assert on e.g. ".claude/concepts/x.md", never on the
          bare folder path, which classifies as shipped); keep the existing near-miss style;
          orchestrator/state stays shipped.
    Keep all existing tests passing.
  - CLAUDE.md: under "Every change to shipped plugin files bumps the plugin version", add that
    the registries the doctor copies (MECHANISMS.md, VOCABULARY.md, JOURNAL.md) count as shipped,
    so any pull request touching them raises the patch version; note the doctor never
    overwrites, so the raise refreshes the seed new projects receive, and tell authors to batch
    registry appends (reviewer janitor entries, journal entries) with a version-raising change.
    ALSO amend the two sentences that would otherwise contradict it: CLAUDE.md line 5 (the list of
    shipped things) gains "registry seeds the doctor copies", and line 16 ("A change that touches
    only documentation or work-item briefs needs no bump") gains "except the registry files the
    doctor copies". State in the new sentence that it wins over the documentation exemption.
  - Raise all five version entries from 0.9.17 to 0.9.18 (marketplace.json: top-level and
    plugins[0]). Re-read master's version first; if it moved, use master + 1 patch.
  - Run: py -3 .claude/scripts/tests/test_check_version_bump.py (unittest-style; pytest is not
    required) and, after the commit, py -3 .claude/scripts/check_version_bump.py --base
    origin/master; report both exit codes.
  - do NOT invent new data shapes — the contract is authoritative
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-22-registries-version-gap.md
  contract_status: approved
```

### 2. Review (`fullstack-code-reviewer`)

**Depends on:** 1

**Files to touch:**
- `.claude/reviews/2026-10-22-registries-version-gap/t2-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review sub-task 1 against the contract, and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-10-22-registries-version-gap.md
FILES: .claude/reviews/2026-10-22-registries-version-gap/t2-review-fullstack-code-reviewer.md
CHECK:
  - the three copied registries now classify as shipped; no other exempt entry changed
  - the new test derives the copy list from plugin_doctor.REQUIREMENTS, fails on today's
    master classification (revert the prefix change locally to confirm), and cannot pass vacuously
  - check_version_bump.py does not import plugin_doctor
  - CLAUDE.md records the decision in Q1's answer
  - all five version entries read the same raised version; check_version_bump.py exits 0
CONSTRAINTS:
  - Write the artefact in the six-section shape the template fixes. The file does NOT
    exist yet — you create it. Nobody pre-created a stub.
  - Name the commit range you reviewed, base..head.
  - Every CHECK item appears under "## What was checked" with its own outcome.
  - Do NOT append to MECHANISMS.md, VOCABULARY.md or JOURNAL.md in this review: under the rule this
    contract introduces, such an append needs a version raise this sub-task cannot carry. If a
    janitor entry is warranted, report it in the handoff for the next version-raising change.
  - "## Evidence" carries the commands you ran with their exit codes. It is never empty.
  - End the header with the verdict line, alone on its line, exactly one of:
    "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked".
  - Also write the Gate Output, t2-review-fullstack-code-reviewer.gate.json, beside the
    report in the same diff: {"supersedes": [...], "checklist": [{"item": "<Review checklist
    line, verbatim>", "outcome": "met | partly-met | not-met | not-applicable"}]}, listing
    every Review checklist item.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-22-registries-version-gap.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

- [x] Implementation matches Data Shapes exactly — evidence: .claude/reviews/2026-10-22-registries-version-gap/t2-review-fullstack-code-reviewer.md
- [x] Reused Mechanisms are actually reused (no parallel implementations introduced) — evidence: .claude/reviews/2026-10-22-registries-version-gap/t2-review-fullstack-code-reviewer.md
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md` — not applicable (.claude/reviews/2026-10-22-registries-version-gap/t2-review-fullstack-code-reviewer.md)
- [ ] New vocabulary terms promoted to `VOCABULARY.md` — not applicable (.claude/reviews/2026-10-22-registries-version-gap/t2-review-fullstack-code-reviewer.md)
- [ ] Integration surfaces reflected on both backend and frontend sides — not applicable (.claude/reviews/2026-10-22-registries-version-gap/t2-review-fullstack-code-reviewer.md)
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced — not applicable (.claude/reviews/2026-10-22-registries-version-gap/t2-review-fullstack-code-reviewer.md)
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface) — not applicable (.claude/reviews/2026-10-22-registries-version-gap/t2-review-fullstack-code-reviewer.md)
- [x] `Status` flipped to `implemented`
