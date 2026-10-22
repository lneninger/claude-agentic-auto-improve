# Concept Contract — Fix the advisor's missing reference folder and the red skill-lookup test

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-22
**Requested by:** user
**Status:** approved
**Supersedes:** `.claude/concepts/followups/2026-10-22-advisor-phantom-design-refs.followup.md` (a stub; renamed to `.followup.superseded.md` by sub-task 1)
**Work Item Brief:** `.claude/work-items/2026-10-22-followups-advisor-refs-and-lookup-test.md`
**Tracking issue:** none. The brief puts opening any GitHub issue out of scope.

---

## Business Concept

- **What is this thing, in domain language?**
  Two leftovers from the web-design skills work (pull request 72), shipped as one bug-fix pull request. (1) The opt-in angular-tailwind add-on's prompt advisor tells the agent, on a layout request, to read two files in a reference folder that has never existed. Its pointer is replaced with one to the plugin's two design skills, worded as advice that the project's own documents override. (2) Two skills, `/verify-before-done` and `/ship`, still find `land_contract.py` with an old one-line lookup. That lookup ignores the install record and picks the first cache folder alphabetically, not the newest. It is replaced with the shared lookup every other skill uses. The pinned lookup test then goes from 21 failures to green. No data shape is added or changed.

- **Existing VOCABULARY.md terms that apply:** add-on (the opt-in angular-tailwind package), skill, concept contract, follow-up stub, `review.documents` (a Project profile slot).

- **New terms proposed for VOCABULARY.md:** none.

---

## End-User View

Not applicable. Reason: no Angular component, template, stylesheet, state service, route file or layout is touched. The hook prints text into an agent's prompt, and the skills are agent instructions.

---

## Data Shapes

Not applicable. Reason: no entity, value object, event or command is added or changed. The change is to a hook's printed text and to two copies of a shell snippet. The invariants that govern it are listed here.

**Invariants**

- **INV-1 (nudge names only things that exist).** The layout nudge names no filesystem path. It names exactly `agentic-auto-improve:application-design` (dense product screens) and `agentic-auto-improve:website-design` (pages). It calls both *advisory*. It says that the project's `review.documents`, and any document in the "Reference files" list above it, win. It says to continue without the skills when they are not installed (clause 4 of the External skill reference convention, applied to internal names too).
- **INV-2 (nothing else in the output moves).** The trigger condition (`TRIGGER_KEYWORDS`), the layout keyword set, `REMINDER`, `reference_section()`, the per-app appendix and the output JSON shape stay byte-identical. Only the nudge text and its suppression list change.
- **INV-3 (suppression follows the new target).** The phantom file-name tuple is deleted. The nudge is suppressed when the prompt already contains `application-design` or `website-design` (case-insensitive substring), just as it used to be suppressed when the prompt named a reference file. Renaming the `PRO_MAX_*` constants (suggested: `DESIGN_NUDGE_KEYWORDS`, `DESIGN_NUDGE_SKILLS`, `DESIGN_NUDGE`) and the comments that say "ui-ux-pro-max" is allowed. Changing the keyword set's members is not.
- **INV-4 (one shared lookup).** The lookup lines in both skills are copied verbatim from `skills/advance/SKILL.md` lines 340-357: `LANDER=` through `fi`. The variable stays `LANDER` and the script stays `.claude/scripts/land_contract.py`. Only the indentation changes, to suit each fenced block.
- **INV-5 (each lookup block ends at a run line).** `test_skill_script_lookup.py` cuts a fenced block at its first `py -3 "$VAR"` line. A block with no such line raises "has no run line", which accounts for all 13 verify-before-done failures. So the fenced block that carries the lookup must also carry its first run line:
  - **verify-before-done:** the block in item 1 ends with `py -3 "$LANDER" --help`, which moves up from item 2's block. Item 2 keeps its number and heading but becomes prose: the last line of the block above reads the help. An older script would exit 2 on the flag. An empty `LANDER` makes that line fail, which is expected, because arm 1 decides on the empty value. Items 3 onward are not renumbered.
  - **ship:** the block keeps its existing run line, `py -3 "$LANDER" --module-tags --base origin/<base> --json`, directly after the new lookup.
- **INV-6 (fallbacks preserved).** With no project copy, no plugin root, no record and no cache, `LANDER` is empty. verify-before-done arm 1 still runs prose Steps 1 to 4 ("runner not found"). ship still derives the tags by hand from `git diff --name-only`. That prose is unchanged.

---

## Reused Mechanisms

- **Shared skill script lookup** (pinned by `.claude/scripts/tests/test_skill_script_lookup.py`; contract `2026-10-12-dedupe-claude-config`) is consumed as-is. Two stale copies are brought back into line, and the test's rules and table do not change. Neither `LANDER` copy is plugin-first (`CLN`) or plugin-only (`concept_changed_check.py`), so the project-copy-first rows apply.
- **External skill reference convention** (MECHANISMS.md) is consumed in spirit. The two skills are internal (`agentic-auto-improve:`), which the convention lets a caller require. The nudge still applies clauses 2 to 4 (advisory, project wins, continue without), because an add-on hook can run where the plugin is vendored but not installed.
- **Project profile** (MECHANISMS.md) is cited by slot name only (`review.documents`). Nothing is read from the profile.
- **Guard rules file** (MECHANISMS.md) is consumed as-is. `architecture-guard.rules.json` (`reference_documents`) keeps feeding the "Reference files" list that the nudge defers to.
- **Plugin version rule** (`.claude/scripts/check_version_bump.py`) is consumed as-is. It reads five version entries from four files: `plugin.json` `version`, `.claude-plugin/plugin.json` `version`, `.cursor-plugin/plugin.json` `version`, `.claude-plugin/marketplace.json` top-level `version`, and `.claude-plugin/marketplace.json` `plugins[0].version`.

---

## New Mechanisms (if any)

None. Every change brings existing code back into line with an existing mechanism.

---

## Extension Points

- `.claude/addons/angular-tailwind/hooks/angular-tailwind-advisor.py`, lines 136-157 and 247-253: replace the nudge text and the suppression tuple (INV-1 to INV-3).
- `.claude/hooks/tests/test_addons.py`, class `AngularTailwindAddonTests` (lines 112-149): add one test method beside `test_the_css_reminder_is_printed_for_a_ui_prompt_and_reads_the_projects_rules_first`, for example `test_the_layout_nudge_names_the_design_skills_and_no_missing_path`. It reuses `run_hook` and the installed-add-on fixture. Rows:
  - (a) A layout prompt such as "design the dashboard layout" gets a context that contains both full skill names, the word "advisory" and `review.documents`, and does not contain `ui-ux-pro-max`, `~/` or `.claude/references/`.
  - (b) Every path-shaped token in the nudge portion (anything matching a `/`-separated name ending in `.md`) exists. The expected set is empty, so the assertion is "no such token". Plant a positive control with a fake `~/.claude/references/x/y.md` string and run it through the same extractor, so the check is shown to catch one (JOURNAL 2026-10-05, positive control).
  - (c) A prompt that already says "application-design" gets no nudge.
  - (d) A UI prompt with no layout keyword ("restyle the button component") gets the reminder but no nudge.
- `skills/verify-before-done/SKILL.md`, lines 34-44: INV-4 and INV-5.
- `skills/ship/SKILL.md`, line 152: INV-4. The line-153 run line stays.
- The five manifest entries listed under Reused Mechanisms: patch bump.

---

## Integration Surfaces

Not applicable. Reason: the hook writes to the host's prompt context, and the skills are markdown the agent reads. No API endpoint, SignalR event or DTO is involved.

---

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold. `.claude/area-mapping.json` declares `"areas": {}`, so the scanner has nothing to score. The architect had no shell, so the script was not run; the empty mapping makes the result certain. The two neighbours the architect noticed are handled by the brief, not here. The README hook-count drift and `check_version_bump.py` counting `.claude/reviews/` are both explicitly out of scope in the brief, which needs no stub. Finding F4 on `skills/website-design/references/foundation.md:47` belongs to the pull request 72 review.

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

---

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

---

## Non-Goals

- The README's 12-versus-17 hooks count, and `check_version_bump.py` treating `.claude/reviews/` as shipped (brief, out of scope).
- Opening any GitHub issue, including one for the superseded stub.
- Rewriting the CSS/Tailwind `REMINDER` text, or changing which prompts trigger the advisor at all.
- Changing `test_skill_script_lookup.py`. The test is correct and the skills are what was stale.
- Touching any other skill's lookup, or the F4 wording in `foundation.md`.

---

## Confidence

Confidence: High. Root cause of both lookup failures confirmed by reading the test's cut rule against the two blocks and by the coordinator's measured run; hook change is local text. Medium only on the version number, because master's manifest could not be read from this session (no shell).

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** Copy advance's lookup into both skills, and move verify-before-done's `--help` call into the lookup block.
  - Why: this is the shared, tested form, and the test cuts at the first run line, so the help call belongs in the same block.
- **Option B (rejected):** Teach the test to look ahead into the next fenced block for the run line.
  - Why rejected: it loosens a pinned rule ("decision 8") to protect one stale copy. Every other skill already meets the rule.
- **Option C (rejected):** Drop the layout nudge entirely.
  - Why rejected: the brief asks for the nudge to point at the design skills, and dropping it loses a useful just-in-time pointer.

---

## Uncertain Assumptions

- `ASSUMED`: master's manifests read `0.9.16`, so the new version is `0.9.17`. This worktree branched at `660c0a4` (the pull request 72 merge, which shipped 0.9.16), and pull request 73 is a draft that only adds records. If it is wrong, `check_version_bump.py` fails or two pull requests collide on one number. Verification path: the implementer runs `git fetch origin && git show origin/master:plugin.json` first, then sets the five entries to master's version plus one patch.
- `ASSUMED`: an internal skill named `agentic-auto-improve:application-design` resolves. Verified only as far as `skills/application-design/SKILL.md` declaring `name: application-design`, and the same for website-design. It matters only for the wording, since the nudge is advisory.
- `VERIFIED via .claude/scripts/tests/test_skill_script_lookup.py:101-112,158-161`: a block is cut at the first `py -3 "$VAR"` line, and a block with no such line raises the error, so every table row fails for verify-before-done.
- `VERIFIED via skills/verify-before-done/SKILL.md:36-44`: the lookup block holds no run line; `py -3 "$LANDER" --help` is in the next block.
- `VERIFIED via skills/ship/SKILL.md:151-154`: the block is `ls … | head -1` followed by the module-tags run line.
- `VERIFIED via .claude/scripts/check_version_bump.py:17-18,38-48`: there are four manifest files and five version entries (marketplace holds two).
- `VERIFIED via .claude/hooks/tests/test_addons.py:112-149`: `AngularTailwindAddonTests` is the existing home of the advisor's tests.

---

## Failure Modes & Mitigations

- **FM:** The copied lookup drifts from advance's, which is a third variant.
  - **Mitigation:** the shared-lookup test runs every copy against the same table and the resolver. It is in the run list (JOURNAL 2026-10-15, lookup-block test).
- **FM:** The verify-before-done reader skips item 2 and never sees that an empty `LANDER` must fall back.
  - **Mitigation:** item 2 stays as prose naming the empty case, and arm 1's text is unchanged (INV-5, INV-6).
- **FM:** A "no missing path" test passes because its extractor never matches anything.
  - **Mitigation:** add a positive-control row with a planted phantom path through the same extractor.
- **FM:** The nudge edit silently changes other output.
  - **Mitigation:** INV-2. The two existing advisor tests stay green, and the reviewer diffs the hook against master for any change outside the nudge region.
- **FM:** The version collides with another merged change.
  - **Mitigation:** read master's version at implementation time (Uncertain Assumptions), and run `check_version_bump.py --base origin/master` after the commit.

---

## Open Questions for User

- [x] Q1: Should the nudge name both skills on every layout prompt, or pick one by keyword (`page` gives website-design, anything else gives application-design)? **Recommendation:** name both on one line each, with a short "for …" hint. It is simpler, needs no new keyword routing, and matches the intake assumption. **User answer (2026-10-22): accepted.** INV-1 therefore means: the nudge names both skills, one line each, with a short "for …" hint, and no keyword routing. Terms follow the registered "Design surface" (application screen or website page).
- [x] Q2: Version `0.9.17`, or master's current version plus one patch if master has moved? **Recommendation:** master plus one patch, read at implementation time. It is 0.9.17 if master is still 0.9.16. **User answer (2026-10-22): accepted.** Verified by the main session: `git show origin/master:plugin.json` reads 0.9.16, so the target is 0.9.17 (the implementer still re-reads master first).

**Amendments after the critique (user accepted all, 2026-10-22):**
- Hook test row (c) ("a prompt that already names a skill gets no nudge") must use a prompt that also carries a layout keyword, so it fails on the old code. Row (b) defines the nudge region as the text between the nudge's first line and its end, and checks for any path-shaped token (`~/`, `.claude/references/`, a drive letter or a slash-separated name ending in a file extension), not only names ending in `.md`, with the planted fake path as the positive control.
- Run list gains `py -3 .claude/scripts/tests/test_ship_skill_sync.py`, because it also reads `skills/ship/SKILL.md`.
- Non-goal added: the dropped nudge sentence that palette hexes are chart-config colours only, never theme-token replacements, is not restated elsewhere; the rule lives in the project's `review.documents` and in the foundation file of the website-design skill. The constants in the hook may be renamed only if the test is updated in the same change.
- Earlier fix of the same phantom folder is recorded at MECHANISMS.md line 15; this change extends it to the add-on.
- Confidence is Medium-High: the lookup root cause is measured (21 failures, both kinds); the skill-name wording rests on the skills declaring their names.

---

## Critique

**Critic:** contract-critic
**Date:** 2026-10-22
**Verdict:** warnings-only

### Findings

- **[WARN] The new advisor test rows can pass on the old code or miss what INV-1 forbids**
  - **What is wrong:** Row (c) has no control, so it can pass for the wrong reason. The hook tokenises with `[a-zA-Z][a-zA-Z-]{2,}` (advisor line 221), so "application-design" is one token and supplies neither the trigger word `design` nor a layout keyword. A prompt such as "use application-design" makes the hook exit silently. That passes on both the old and the new hook. The row is only red on the old code if the prompt also carries a layout keyword, and the contract does not say so. Row (b) has two gaps of its own. It does not define where "the nudge portion" begins. Its extractor matches only `/`-separated names ending in `.md`, while INV-1 says "names no filesystem path". A directory or non-`.md` phantom would get through.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-05, "Never hide a forbidden name by hashing it when the test needs a positive control" (every scan must be shown able to fail). Also the suite's own control convention at `.claude/hooks/tests/test_addons.py:145-146`, where a "no reminder" row first proves that a UI prompt does get one.
  - **Where in this contract:** `## Extension Points`, "(c) A prompt that already says "application-design" gets no nudge." and "(b) Every path-shaped token in the nudge portion (anything matching a `/`-separated name ending in `.md`) exists."
- **[WARN] Confidence says High while two assumptions are still ASSUMED**
  - **What is wrong:** The Confidence verdict contradicts the uncertainty list. It also gives itself a split grade ("Medium only on the version"). The main session has since measured `origin/master` `plugin.json` at `0.9.16`. That should turn the first assumption into VERIFIED and answer Q2, but the contract body has not been updated.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22, "An accepted critic WARN or answered Open Question must amend the contract body before approval".
  - **Where in this contract:** `## Confidence`, "Confidence: High." against `## Uncertain Assumptions`, "`ASSUMED`: master's manifests read `0.9.16`" and "`ASSUMED`: an internal skill named `agentic-auto-improve:application-design` resolves."
- **[WARN] The nudge wording uses its own words for the two design surfaces and lists vocabulary terms that do not exist**
  - **What is wrong:** VOCABULARY.md already defines **Design surface**. It has two values: *application screen* (`application-design`) and *website page* (`website-design`). INV-1 and Q1 say "dense product screens" and "pages" instead. Q1's alternative ("`page` gives website-design") also conflicts with the term: a dashboard page is an application screen. None of "add-on", "skill", "concept contract", "follow-up stub" or `review.documents` is a VOCABULARY.md entry. The terms that do apply, **Design surface**, **External skill reference** and **Tracking Issue**, are not listed.
  - **Prior artifact ignored:** `VOCABULARY.md:64` (Design surface), `VOCABULARY.md:65` (External skill reference), `VOCABULARY.md:52` (Tracking Issue).
  - **Where in this contract:** `## Business Concept`, "Existing VOCABULARY.md terms that apply: add-on (the opt-in angular-tailwind package), skill, concept contract, follow-up stub, `review.documents`". Also `## Data Shapes` INV-1, "(dense product screens) ... (pages)".
- **[NIT] The run list leaves out a second test that pins `skills/ship/SKILL.md`** — `.claude/scripts/tests/test_ship_skill_sync.py:56` reads the same file this contract edits (INV-S1 to INV-S7). The edit at line 152 is unlikely to touch what it pins, but the run list names only the lookup test for that file. This applies `JOURNAL.md` 2026-10-15, "A skill that edits a block pinned by a lookup-block test must name that test", by analogy.
- **[NIT] The earlier fix for this same phantom folder is not cited, and the chart-colour warning is dropped silently** — `MECHANISMS.md:15` records that the identical `ui-ux-pro-max/` citation in `CLAUDE.md` was repointed to `review.documents` plus `dataviz`. The current nudge also says "Palette hexes there are chart-config-only colors, NEVER theme-token replacements" (advisor line 156). INV-1 replaces that sentence with nothing, and no Non-Goal records the loss. Reaching the same rule through `application-design`'s own `dataviz` citation (`MECHANISMS.md:69`) is plausible but unstated.
- **[NIT] Adjacent Areas has extra text, and the scanner was not run** — the exact single-line "not applicable" form is followed by four more sentences, and `derive_area.py` was not run ("The architect had no shell"). The result is still certain, because `.claude/area-mapping.json:14` reads `"areas": {}`.
- **[NIT] INV-3 leaves an optional rename to the implementer** — "Renaming the `PRO_MAX_*` constants (suggested: ...) ... is allowed" is a choice the user has not seen. The reviewer's "diff against master" check in sub-task 2 will then have to tell renames apart from changes in behaviour.

### Applicable journal entries

- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by INV-5 and the sub-task 1 run list. Checked against the test: `test_skill_script_lookup.py:101-107` cuts at the first `RUN_LINE` match, and `:158-161` raises "has no run line". verify-before-done fails all 13 rows (12 `each()` rows plus `test_every_block_ends...`). ship's `ls | head -1` fails exactly 8 (it passes 0.10.0-vs-0.9.0, which sorts first alphabetically, plus project-copy, plugin-root and nothing-found). Both counts match the measured 21. INV-4's range `skills/advance/SKILL.md:340-357` is right: 340 is `LANDER=`, 357 is `fi`, and 358 is advance's own run line.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded for row (b) (the planted phantom path). Not carried to row (c); see WARN above.
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate** — heeded by INV-1 (`review.documents` and the "Reference files" list win).
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by INV-3, which was written from the hook's lines 247-253 rather than from the stub.
- **2026-10-04 — A root locator can return the consumer itself under vendoring** — heeded by `## Reused Mechanisms`. It states that the project-copy-first rows apply to both `LANDER` copies, which is the test's intended behaviour (`test_skill_script_lookup.py:399-424`).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — not yet addressed. It applies at approval time to Q1 (INV-1 wording) and Q2 (the version assumption); see WARN above.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — not addressed. The contract did not need to, because the advisor never blocks (`test_addons.py:133`, "an advisor never blocks").
- **2026-10-16 — A skill step that moves the shell must come after every later step that reads the working tree** — not addressed. The contract did not need to, because neither edited block runs `cd`.

### What the critic did not check

- `.claude/registries/INTEGRATION.md` does not exist in this worktree, so checklist item 7 was judged from the contract alone. It was not applicable anyway: no endpoint or DTO is involved.
- `.claude/.scout-cache/registry-digest.md` is absent, so the registries were read directly. MECHANISMS, VOCABULARY and JOURNAL have no project-tier or per-domain files here, so only the Universal tier was checked.
- `.claude/north-stars/` is absent, so there are no active north-stars and item 13 produces no findings.
- The bash lookup was not run. The 13 + 8 failure split was derived by reading the test and checked against the main session's measured count.

---

## Lessons referenced

- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test**: heeded by INV-5 and the sub-task 1 run list, which names `test_skill_script_lookup.py`.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control**: heeded by Extension Points, test row (b).
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate**: heeded by INV-1, where the project's `review.documents` win.
- **2026-10-04 — Check a documented guard behaviour against the guard's code**: heeded by reading the hook's suppression logic (lines 247-253) before specifying INV-3, rather than trusting the stub's description.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval**: noted for the approval pass. Q1's answer must be written into INV-1.
- Orthogonal to north-stars: none active.

---

## Implementation Handoff

### 1. Advisor nudge, lookup blocks and version (`python-ai-developer`)

**Depends on:** none

**Preconditions:** master's plugin version read with git show origin/master:plugin.json

**Files to touch:**
- `.claude/addons/angular-tailwind/hooks/angular-tailwind-advisor.py`
- `.claude/hooks/tests/test_addons.py`
- `skills/verify-before-done/SKILL.md`
- `skills/ship/SKILL.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.claude/concepts/followups/2026-10-22-advisor-phantom-design-refs.followup.md`
- `.claude/concepts/followups/2026-10-22-advisor-phantom-design-refs.followup.superseded.md`

**Pre-written TASK block:**
```
TASK: Replace the advisor's phantom-path layout nudge with a pointer to the two design skills, give the
      two stale land_contract.py lookups the shared lookup, bump the plugin version, and supersede the stub.
CONTEXT: concept contract at .claude/concepts/2026-10-22-advisor-refs-and-lookup-test.md
FILES: the ten files listed under Files to touch
CONSTRAINTS:
  - Test first: add the AngularTailwindAddonTests method (rows a-d, with the positive control in b) and
    see it fail before editing the hook.
  - Hook: honour INV-1, INV-2 and INV-3. The keyword set's members, REMINDER, reference_section and the
    output shape must stay byte-identical.
  - Skills: copy skills/advance/SKILL.md lines 340-357 verbatim (re-indented only). In verify-before-done,
    the lookup block ends with `py -3 "$LANDER" --help` and item 2 becomes prose (INV-5); do not renumber
    items 3 onward. In ship, keep the --module-tags run line right after the lookup. Keep both empty-LANDER
    fallbacks word for word (INV-6).
  - Version: run `git show origin/master:plugin.json`, then set master's version plus one patch in all
    five entries: plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json, and
    .claude-plugin/marketplace.json (top-level version and plugins[0].version).
  - Stub: git mv it to .followup.superseded.md. Add "**Superseded by:**
    .claude/concepts/2026-10-22-advisor-refs-and-lookup-test.md" as its first line under the title. Set
    "**Status:** superseded" and "**Issue:** not opened (out of scope per the brief)".
  - Run list (all must exit 0):
      py -3 .claude/scripts/tests/test_skill_script_lookup.py      (must end OK)
      py -3 .claude/hooks/tests/test_addons.py
      py -3 .claude/scripts/tests/test_plugin_manifests.py
      py -3 .claude/scripts/tests/test_ship_skill_sync.py
      py -3 .claude/scripts/check_version_bump.py --base origin/master   (after the commit)
  - Test rows (post-critique): row (c) must carry a layout keyword so it is red on the old hook; row (b)
    checks every path-shaped token (not only .md names) and keeps the planted fake path as its positive
    control. See the amendments under Open Questions.
  - Do NOT edit test_skill_script_lookup.py, README.md, or any other skill.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-22-advisor-refs-and-lookup-test.md
  contract_status: approved
```

### 2. Review (`fullstack-code-reviewer`)

**Depends on:** 1

**Files to touch:**
- `.claude/reviews/2026-10-22-advisor-refs-and-lookup-test/t2-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review sub-task 1 against this contract, and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-10-22-advisor-refs-and-lookup-test.md
FILES: .claude/reviews/2026-10-22-advisor-refs-and-lookup-test/t2-review-fullstack-code-reviewer.md
CHECK (each appears under "## What was checked" with its own outcome):
  - INV-1..INV-3: the nudge text, the suppression and no change outside the nudge region (diff the hook against master)
  - INV-4..INV-6: both lookups match advance 340-357; the run-line placement; both fallbacks intact
  - the new test rows a-d exist and the positive control is real
  - the four run-list commands with their exit codes, plus check_version_bump.py --base origin/master
  - the five version entries agree and are one patch above master
  - the stub is renamed and carries Superseded by, Status superseded and the issue not opened
CONSTRAINTS:
  - Write the artefact in the six-section shape the template fixes. The file does NOT exist yet; you
    create it, and its absence means only "this review has not run".
  - Name the commit range reviewed, base..head.
  - "## Evidence" carries the commands run with their exit codes. It is never empty.
  - End the header with the verdict line, alone on its line, exactly one of:
    "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked".
  - Also write the Gate Output, t2-review-fullstack-code-reviewer.gate.json, beside the report in the same
    diff: {"supersedes": [], "checklist": [{"item": "<Review checklist line verbatim>", "outcome":
    "met | partly-met | not-met | not-applicable"}]}. List every Review checklist item.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-22-advisor-refs-and-lookup-test.md
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
