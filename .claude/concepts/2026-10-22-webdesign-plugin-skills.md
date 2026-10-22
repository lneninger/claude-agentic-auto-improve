# Concept Contract — Move web-design agent knowledge into two plugin skills, and a rule for citing other plugins' skills

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-22
**Requested by:** user
**Status:** implemented
**Implemented:** 2026-10-22, automatically, by pr_merged.py after https://github.com/lneninger/claude-agentic-auto-improve/pull/72; 3 checklist items from review reports, 0 with no structured evidence; not performed: none; owner confirmed resolved: none
**Supersedes:** none
**Work Item Brief:** `.claude/work-items/2026-10-22-webdesign-plugin-skills.md`
**Tracking issue:** pending (one follow-up stub exists; `/design-first` Step 3.4 opens the issue)

> **Protocol:** filled in by `data-architect`. Implementer agents refuse to run unless `Status: approved` or `Status: implemented`. The `concept-gate.py` hook reads `Files to touch` to decide whether Edit/Write/MultiEdit is allowed.

---

## Business Concept

- **What is this thing, in domain language?**
  The `ui-ux-designer` agent carries 429 lines of design method inline. This contract moves that method into two skills the plugin ships, so it can be invoked on its own and loaded only when needed. **website-design** owns the *design foundation*: the rules every page in the project obeys (theme polarity per application, the Material-to-Tailwind token bridge, the inline-style ban, contrast, keyboard and ARIA rules, motion, the never-do list). **application-design** owns the data-dense product-screen layer on top of it (density, the trading typography scale, metric grids, badges, cards, skeletons, empty states, value flashes, live regions, the app-shell layout) and loads the foundation from its sibling. The agent keeps its role, the journal step, the contract gate and its HANDOFF protocol, and points at the skills for method. Separately, the plugin gains a written rule for citing a skill that belongs to another plugin: fully qualified name, marked advisory, absence behaviour stated, never a hard dependency.

- **Existing VOCABULARY.md terms that apply:**
  - **Placeholder slot** (Universal) — a profile slot still holding template prose, empty, or missing. Both skills halt on one.
  - **Plugin repository**, **Vendored asset** (Universal) — the two ways the skills reach a project; the sibling-file read must work in both.
  - **Install mode** (Universal) — `plugin`, `vendored`, `both`, `plugin-source`, `none`.
  - **Working agreement** (Universal) — not used; named only to say the convention is documentation, not delivered context.

- **New terms proposed for VOCABULARY.md** (Universal tier, appended after approval):
  - **Design foundation** — the set of design rules every page of a project obeys whatever kind of page it is: theme polarity per application, the token bridge, the inline-style ban, accessibility, motion and the never-do list. Owned by the `website-design` skill's `references/foundation.md`, and loaded by `application-design` before its own layer. One copy; neither skill restates it.
  - **Design surface** — the kind of thing being designed, one of two values: *application screen* (a data-dense, always-on product screen, designed with `application-design`) or *website page* (a marketing or content page, designed with `website-design`). Per-application differences come from project profile slots, never from more skills.
  - **External skill reference** — a mention, in any asset this plugin ships, of a skill owned by another plugin. It carries the fully qualified name `<plugin>:<skill>`, the word *advisory*, the precedence (this plugin's rules and the project's `review.documents` win), and what the asset does when that plugin is absent. It is never a hard dependency. Distinct from an internal reference to this plugin's own skills or agents, written `agentic-auto-improve:<name>`, which may be required.

---

## End-User View

Not applicable. Reason: `Files to touch` holds no Angular component, template, stylesheet, state service, route file or shared layout — only agent, skill, manifest and documentation markdown and JSON. No screen any end user sees changes.

---

## Data Shapes

No runtime data is introduced. The shapes below are document shapes; they are what the implementer writes and what the review gate checks.

### Entities

Not applicable. Reason: nothing here has identity that persists or changes over time; every shape is an immutable document part.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Design skill package | name (`application-design` \| `website-design`); `SKILL.md` frontmatter (name, trigger-rich description, `user_invocable: true`); `SKILL.md` body (when to use, Step 1 profile read, numbered steps, advisory references); one `references/<file>.md` read on demand | Each of the two new skills |
| Rule ledger row | rule id; source line range in `agents/ui-ux-designer.md` at `origin/master`; one-line rule summary; destination (one file, one section) | The allocation table below; the review gate verifies every row |
| Profile read outcome | slot name; outcome (`root-undeterminable` \| `usable` \| `none-authored` \| `placeholder` \| `row-missing` \| `file-missing`); what the skill does | The halt table below, written into Step 1 of both skills. Amended after approval (critic WARN 5, accepted): `root-undeterminable` halts and asks which project, never searching. It is the first row. |
| External skill reference | fully qualified name; *advisory* marker; precedence sentence; absence behaviour sentence. Amended after approval (Q1 answer): a skill that no plugin ships but the host provides is cited by its bare name and marked a host built-in, still advisory | Every mention of another plugin's skill this work adds; the convention in `CONTRIBUTING.md` |

**Invariants**

- **INV-1 (nothing lost, nothing doubled).** Every rule in the agent at `origin/master` appears in exactly one destination in the ledger, moved with its wording kept (only pronouns and section headings may change). The one declared exception is **D1**: the profile read-and-halt step appears in Step 1 of *both* SKILL.md files, because acceptance criterion 7 requires each skill to halt on its own.
- **INV-2 (one foundation).** The design foundation exists once, in `skills/website-design/references/foundation.md`. `application-design` reads it from the sibling skill folder; it never restates a foundation rule.
- **INV-3 (sibling present or halt).** When `application-design` cannot find `website-design/references/foundation.md` beside its own folder, it says which path it looked for and halts. It never continues with the application layer alone.
- **INV-4 (profile from the project, never the plugin).** Both skills read `<project root>/.claude/project-profile.md`, where the project root is `CLAUDE_PROJECT_DIR` when set, else the repository holding the files being designed. Never the plugin's own copy, which is a template. A template file or an unset slot falls under the halt table.
- **INV-5 (no guessed theme).** No colour class is chosen before the target application is matched to a `frontend.roots` entry and its `frontend.theme-polarity` value is read. An application with no polarity entry halts.
- **INV-6 (externals are advisory and optional).** Every External skill reference added by this work follows the convention, and every step that names one says what happens when it is absent: the skill continues without it. No step halts because an external plugin is missing.
- **INV-7 (internal references are required).** The agent invokes the skills as `agentic-auto-improve:application-design` / `agentic-auto-improve:website-design` with the Skill tool, matching the `senior-test-engineer` → `unit-testing` precedent. If the skill cannot be loaded, the agent stops and says so; it does not continue from memory.

**Halt table (Step 1 of both skills — declared duplicate D1)**

| Condition | Outcome | Skill does |
|---|---|---|
| Project root cannot be determined (added after approval, critic WARN 5) | `root-undeterminable` | Halts and asks which project; does not search. |
| Profile file absent at the project root | `file-missing` | Halts: "no project profile at `<path>`; run `/auto-improve-finish-install`". |
| `frontend.roots`, `frontend.theme-polarity` or `review.documents` row absent | `row-missing` | Halts, naming the slot. |
| Any of the three holds template `*(...)*` prose or is empty | `placeholder` | Halts, naming the slot. Never guesses a theme. |
| `frontend.roots` is `none` | `none-authored` | Halts: the project declares no frontend to design for. |
| Target application has no `frontend.theme-polarity` entry | `row-missing` (per app) | Halts, naming the application. |
| Polarity `none` for the target (a library) | `usable` | Uses token utilities only. |
| `review.documents` is `none` | `none-authored` | Continues, and says no authoritative documents exist, so the foundation and advisory sources are the only sources. |

### Rule ledger (allocation of every section of the agent at `origin/master`)

Destinations: **AG** `agents/ui-ux-designer.md` · **WS** `skills/website-design/SKILL.md` · **WF** `skills/website-design/references/foundation.md` · **AS** `skills/application-design/SKILL.md` · **AP** `skills/application-design/references/application-patterns.md`.

| Id | Lines | Rule | Dest |
|---|---|---|---|
| R01 | 1-9 | Frontmatter. `tools` gains `Skill`; `skills:` preload left unchanged (Open Question 2) | AG |
| R02 | 11 | Role statement | AG |
| R03 | 13-28 | Step 0 — `ui-evolution` journal pull, `app:` sub-tag, `recurring-mistake` | AG |
| R04 | 30-34 | Project context: always-on trading terminal, stack, users | AS |
| R05 | 36-47 | Several apps, no shared theme; read both slots first; never infer a theme from a name | WF |
| R06 | 48-52 | Polarity suffix rules (`-700`/`-100`, `-400`/`-500/15`, tokens for `both`) | WF |
| R07 | 54-63 | `@theme` bridge utilities; never `text-gray-*` / `bg-gray-*` | WF |
| R08 | 65-70 | Consult `review.documents` paths before any design answer | WF; the "profile missing → halt" sentence becomes D1 in WS and AS |
| R09 | 71-75 | Three authoritative document rows | WF |
| R10 | 76 | `/dataviz` advisory row — rewritten to the External skill reference form | AS |
| R11 | 77 | Designer domain judgement, advisory | WF |
| R12 | 79-83 | Phantom `ui-ux-pro-max` note — do not reintroduce | WF |
| R13 | 85-88 | Priority rules 1-2 (advisory loses to project rules; ignore upstream gray) | WF |
| R14 | 89 | Priority rule 3 — palette hexes in typed chart constants only | AP |
| R15 | 90 | Priority rule 4 — cite the source in HANDOFF "Key decisions" | AG |
| R16 | 94 | Philosophy 1 — information density first | AP |
| R17 | 95-98 | Philosophy 2-5 — hierarchy by weight, semantic colour, purposeful motion < 200ms, keyboard-first | WF |
| R18 | 100-118 | `mat.theme()` configuration and the bridge | WF |
| R19 | 120-130 | Token utilities in templates; no arbitrary-property syntax | WF |
| R20 | 132-147 | Inline-style elimination table; migrate what you touch | WF |
| R21 | 149-159 | Compact density | AP |
| R22 | 161-178 | Trading typography scale | AP |
| R23 | 180-197 | Metrics grid | AP |
| R24 | 199-214 | Status badges | AP |
| R25 | 216-243 | Metric card | AP |
| R26 | 245-257 | Loading skeleton | AP |
| R27 | 259-272 | Empty state | AP |
| R28 | 274-300 | Real-time value flash | AP |
| R29 | 302-308 | Contrast ratios per polarity | WF |
| R30 | 310-318 | Keyboard navigation | WF |
| R31 | 320-325 | ARIA labels on icon buttons | WF |
| R32 | 327-335 | Live regions for real-time data | AP |
| R33 | 337-355 | Sidebar + content responsive shell | AP |
| R34 | 357-369 | Checklist: lines 360, 362, 364 → AP; lines 361, 363, 365-369 → WF | AP / WF |
| R35 | 371-380 | Never-do list: line 377 (text below `text-xs`, trading monitors) → AP; every other line → WF | AP / WF |
| R36 | 382-388 | Contract requirement, UX nuance, TRIVIAL escape, new-primitive clause | AG |
| R37 | 390-429 | Input/Output contract, HANDOFF, rules | AG |

**New text (not moved, so not in the ledger), kept to the minimum:** each SKILL.md's when-to-use, Step 1 (D1), the step that loads the foundation, and the External skill references. `website-design` adds one scoping sentence: *the application patterns file does not apply to a website page by default; use one of its patterns only when the page shows live product data.* The agent adds one section, *Method lives in the skills*: application screen → `agentic-auto-improve:application-design`, website page → `agentic-auto-improve:website-design`.

### Events

Not applicable. Reason: no runtime component emits or listens to anything.

### Commands (if any)

Not applicable. Reason: skills are invoked by the existing Skill tool and slash-command surface; no new command shape.

---

## Reused Mechanisms

- **Project profile** — consumed as-is. Both skills cite `frontend.roots`, `frontend.theme-polarity` and `review.documents`, the slots the agent already cites. No new slot is needed, so the template is untouched. **Check:** all three slots are declared in `.claude/project-profile.md` lines 28, 29 and 34.
- **Placeholder slot** reading (as defined in VOCABULARY) — consumed as-is. The halt table reuses its definition rather than inventing a "missing" rule.
- **Adaptive Engineering Journal** (`ui-evolution` tag) — consumed as-is; the Step 0 grep stays in the agent unchanged.
- **Plugin agent dispatch rule** (`agentic-auto-improve:<name>`, pinned by `.claude/scripts/tests/test_plugin_text_scans.py` scan 3) — extended by the convention: the same fully-qualified form now governs references to *other* plugins' skills, with the added advisory and absence clauses.
- **Agent-delegates-to-skill shape** (the `senior-test-engineer` → `unit-testing` refactor shipped in 0.9.14) — reused as the model: `Skill` in tools, invoke by qualified name, stop if the skill cannot load.
- **Skill `references/` folder** (`skills/pr-merged/references/`, `skills/task/references/`) — reused for the long material.
- **Version-bump check** (`.claude/scripts/check_version_bump.py`, five version entries across four manifests) — consumed as-is.

---

## New Mechanisms (if any)

- **Name:** External skill reference convention
- **Purpose:** One documented way for any shipped asset to mention a skill another plugin owns.
- **Why an existing mechanism was not sufficient:** The dispatch rule covers only this plugin's own agents, where the target is guaranteed present. An external plugin may be absent, so the rule needs two clauses the dispatch rule cannot carry: precedence and absence behaviour.
- **Proposed location:** `CONTRIBUTING.md`, new section *Referencing another plugin's skill*, with a one-sentence pointer from `README.md` § Skills.
- **Extension seam:** a later contract can add a text scan beside `test_plugin_text_scans.py` that checks each `<plugin>:<skill>` mention for the advisory and absence clauses.
- **Will this be promoted to `MECHANISMS.md` after implementation?** yes (Universal tier)

- **Name:** Sibling skill reference file
- **Purpose:** Let one shipped skill read a `references/` file owned by another shipped skill of the same plugin, so a shared rule set exists once.
- **Why an existing mechanism was not sufficient:** Today every skill reads only its own `references/`. Copying the foundation into both skills breaks INV-1 and invites drift. A third skill only for the foundation adds inventory and contradicts the brief's two-skill assumption.
- **Proposed location:** `skills/application-design/SKILL.md`, the step that loads `../website-design/references/foundation.md`.
- **Extension seam:** any later skill that needs the foundation reads the same file the same way, with the same halt on absence (INV-3).
- **Will this be promoted to `MECHANISMS.md` after implementation?** decide-at-review

---

## Extension Points

- `agents/ui-ux-designer.md` frontmatter `tools`: add `Skill`.
- `agents/ui-ux-designer.md` body: new section *Method lives in the skills*, placed after Step 0 and before the contract requirement.
- `skills/` root: two new folders. Root placement is required (CONTRIBUTING.md § Proposing a new generic asset, item 7).
- `CONTRIBUTING.md`: new section *Referencing another plugin's skill*.
- `README.md`: § Skills name list; § What is included `skills/` count; § What each provider actually gets skills row; one pointer sentence to the convention.
- Manifests: the skill count in each `description` (`plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`) and `version` in all five entries.

---

## Integration Surfaces

Not applicable. Reason: the change is contained in shipped markdown and manifest metadata; no API endpoint, SignalR event or DTO crosses a layer. The agent-to-skill invocation is a call within the plugin and is listed under Extension Points.

---

## Adjacent Areas

The cross-area scan has no signal to score: `.claude/area-mapping.json` holds `"areas": {}` in this repository. One area noticed by the architect:

| Area | Decision | Implication / Reason | Handle |
|------|----------|----------------------|--------|
| angular-tailwind add-on (not in the area map) | follow-up handle | Its advisor hook still nudges toward the phantom `~/.claude/references/ui-ux-pro-max/` catalogue that the agent's own note (moved here to WF, R12) says never existed; after this lands the natural target is the application-design skill. | `.claude/concepts/followups/2026-10-22-advisor-phantom-design-refs.followup.md` |

---

## UI Implications

Not applicable. Reason: documentation-and-skill contract with no frontend consumer in Integration Surfaces; no application screen changes.

---

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

---

## Non-Goals

- Rewriting, merging or correcting any design rule. Rules move with their wording kept.
- Adding website-specific design rules beyond the single scoping sentence.
- The agent's `skills: - angular` preload (pre-existing; Open Question 2).
- The advisor hook's phantom paths (follow-up stub).
- An automated scan for the convention (seam named under New Mechanisms).
- Other stale manifest numbers (hook count 17 vs README 12). Only the skill count is corrected.
- Installing, vendoring or pinning any external plugin.
- Anything about `C:\Users\lneni\drop-scalpingmachine-prefix-dbs.ps1`. It is not read and not run.

---

## Confidence

Confidence: Medium. High on the rule ledger (built line by line from the agent at `origin/master`) and on the manifest and inventory edits. Medium on the sibling-file read under Cursor and Codex, where no trial has been run. Medium on the `/dataviz` qualified name, which is unknown (Open Question 1).

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** The foundation lives in `website-design/references/foundation.md`; `application-design` adds the dense layer and reads the foundation from its sibling.
  - Why: one copy of every rule, both skills get a `references/` file, and the dependency runs from the specialised layer to the general one.
- **Option B (rejected):** The foundation lives in `application-design`, and `website-design` reads it.
  - Why rejected: `website-design` would have no reference material of its own (fails acceptance criterion 1), and the general layer would sit under the specialised skill.
- **Option C (rejected):** A third skill, `design-foundation`.
  - Why rejected: contradicts the brief's two-skill assumption and adds a skill nobody invokes directly.
- **Option D (rejected):** Duplicate the foundation in both skills.
  - Why rejected: breaks "exactly one" in acceptance criterion 2, and the copies drift.
- **Option E (rejected):** Preload the skills through the agent's `skills:` frontmatter instead of invoking them with the Skill tool.
  - Why rejected: it loads both skills whole on every dispatch, which is the cost this work removes, and the 0.9.14 precedent uses the Skill tool.

---

## Uncertain Assumptions

- `VERIFIED via agents/ui-ux-designer.md` (429 lines, read in full): every section is allocated in the ledger.
- `VERIFIED via .claude/project-profile.md:28,29,34`: the three slots exist in the template.
- `VERIFIED via agents/senior-test-engineer.md:4,15`: the delegate-to-skill precedent (`Skill` in tools, qualified name, stop if unloadable).
- `VERIFIED via Glob skills/*/SKILL.md`: 26 skills on disk today. README says 25 and its name list lacks `unit-testing`; the manifests say 22. Both are pre-existing drift that this change has to correct for the inventory to pass. Expected after: 28. The implementer recounts by listing.
- `VERIFIED via .claude/scripts/check_version_bump.py:17-18`: four manifests, five version entries.
- `VERIFIED via .claude/area-mapping.json:14`: `"areas": {}`, so the cross-area scan cannot score anything.
- `ASSUMED`: Claude Code shows a skill's base directory when it loads, so `../website-design/references/foundation.md` resolves under both plugin and vendored installs. It matters because, if wrong, `application-design` halts by INV-3 every time. Verification path: the implementer invokes `application-design` once from this worktree and records the path it resolved.
- `ASSUMED`: Cursor and Codex keep sibling skill folders together, as the root `skills/` layout implies. Verification path: not trialled; stated under Failure Modes.
- `ASSUMED`: `frontend-design:frontend-design` is the correct qualified name, as the brief states. Verification path: the installed-plugin list on the workstation.
- `ASSUMED`: the `plugin-dev:plugin-validator` agent is available to the main session. If it is not, the run is recorded as a Not-performed item (scope note 3).
- Not run: CodeGraph tools and a shell were not available to this architect run. The investigation is markdown-only, and every claim above was read from the file itself.

---

## Failure Modes & Mitigations

- **FM:** A rule is dropped, or lands in two places, during the move.
  - **Mitigation:** The rule ledger is the allocation. The review gate walks every row against the diff (INV-1).
- **FM:** `application-design` runs without the foundation and suggests theme-wrong colours.
  - **Mitigation:** INV-3 halt naming the path looked for.
- **FM:** Under a plugin install a skill reads the plugin's own template profile and "succeeds".
  - **Mitigation:** INV-4 (project root, never plugin), and the template's placeholders fall into the halt table anyway. Heeds the 2026-10-15 and 2026-10-16 journal lessons.
- **FM:** An absent external plugin stalls a skill.
  - **Mitigation:** INV-6: each external step states "continue without it".
- **FM:** The inventory counts drift again.
  - **Mitigation:** Counts are recounted by listing `skills/*/SKILL.md`, never from the previous README (the 2026-09-14 accuracy-pass method).
- **FM:** A version bump is missed in one manifest.
  - **Mitigation:** `check_version_bump.py` fails on disagreement; the review gate runs it.

---

## Open Questions for User

- [x] **Q1 — Which plugin provides `/dataviz`?** The convention needs `<plugin>:dataviz`. Recommendation: tell me the plugin name. If you prefer not to, the implementer reads it from the workstation's installed-plugin list, and halts rather than guessing if no plugin there ships it.
- [x] **Q2 — The agent's `skills: - angular` preload.** It names a skill outside this plugin and predates this work. Recommendation: leave it unchanged here, since the brief scopes the convention to references this work adds, and decide it in the follow-up. The alternative is to remove it now and add an advisory row for it.
- [x] **Q3 — Foundation placement and the website scoping sentence.** Recommendation: Option A (foundation in `website-design`), plus the one scoping sentence quoted under Data Shapes as the only new website guidance.
- [x] **Q4 — Version.** Recommendation: 0.9.16, a patch bump, matching 0.9.14 for the comparable unit-testing move.
- [x] **Q5 — Where the convention lives.** Recommendation: `CONTRIBUTING.md` as the full rule, with a one-sentence pointer in `README.md` § Skills.

- **User answer (2026-10-22):** accepted the recommendations for Q1-Q5 and for every WARN and NIT, as the critic described them. WARN 1 is answered by each skill pointing to the agent's journal-lessons step; WARN 7 keeps the trading wording with a note. The user chose to have the main session run the sibling-path trial (see BLOCKER).

---

## Critique

**Critic:** contract-critic
**Date:** 2026-10-22
**Verdict:** blockers-found

### Findings

- **[BLOCKER] The one trial of the assumed sibling-file read is given to an agent that cannot run it**
  - **What is wrong:** Option A, INV-3 and the "Sibling skill reference file" mechanism all depend on the host resolving `../website-design/references/foundation.md` against the skill's base directory. Nobody has seen that work, and the contract marks it ASSUMED. The only proof is the block-1 constraint "Invoke application-design once from this worktree and record … the foundation path it resolved". Block 1 is assigned to `ui-ux-designer`, whose tools when dispatched are `Read, Grep, Glob, Write, Edit, mcp__codegraph__*` (`agents/ui-ux-designer.md:5`): no `Skill` and no `Bash`. Adding `Skill` to that file during the run does not change the instance already running. So the design is approved, and then built, on host behaviour that is never trialled.
  - **Prior artifact ignored:** `JOURNAL.md:40-45 — 2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work` ("prove it with one harmless invocation before the code depends on it"). The match is by analogy: a path the host resolves inside shipped text, rather than a variable it expands. The working precedent the contract cites carries `Skill` in its own tools (`agents/senior-test-engineer.md:4`).
  - **Where in this contract:** `## Implementation Handoff → 1. Design skills (ui-ux-designer)` — "Invoke application-design once from this worktree and record in the HANDOFF the foundation path it resolved"; `## Uncertain Assumptions` — "Verification path: the implementer invokes `application-design` once from this worktree".
  - → Addressed by: the user chose "main session runs the path test first" (2026-10-22). Trial run from the main session with a shell: from the installed cache copy `plugins/cache/auto-improve/agentic-auto-improve/0.9.13/skills/task`, `../design-first/SKILL.md` resolved and read; from this repository's `skills/task`, `../debug/SKILL.md` resolved and read. Not trialled: Cursor and Codex installs. Block 1 must keep the fallback of copying `foundation.md` into both skills if a later install mode fails the path read.
- **[WARN] Calling a skill on its own skips the ui-evolution journal pull, the only loop that carries UI lessons forward**
  - **What is wrong:** R03 (Step 0, which pulls journal entries tagged `ui-evolution` and treats `recurring-mistake` as load-bearing) stays in the agent only. Both skills are `user_invocable: true`, and being "invoked on its own" is the stated purpose. So a direct `/application-design` or `/website-design` run applies the theme rules without any recorded UI lesson.
  - **Prior artifact ignored:** `MECHANISMS.md:40 — Adaptive Engineering Journal`; `JOURNAL.md:30` tag convention (`ui-evolution` = "re-read by `ui-ux-designer` on every invocation"); `agents/ui-ux-designer.md:28` ("skipping it makes the designer … a one-shot generator").
  - **Where in this contract:** `## Reused Mechanisms` — "Adaptive Engineering Journal (`ui-evolution` tag) — consumed as-is; the Step 0 grep stays in the agent unchanged."
- **[WARN] The sibling-file read is new path logic beside a shipped, tested way for a skill to find plugin files**
  - **What is wrong:** The plugin already ships a fixed lookup order for a skill to find its own plugin's files: vendored path, then `$CLAUDE_PLUGIN_ROOT`, then `installed_plugins.json`, then the newest cache folder. It is pinned by `test_skill_script_lookup.py`, and the README says "a skill added later should copy the snippet rather than assume a vendored layout". The contract adds a relative `../` read instead, and Alternatives Considered never weighs the existing lookup.
  - **Prior artifact ignored:** `README.md:368-375`; `JOURNAL.md:131-136 — 2026-10-15 — Locate a script from the plugin root, never from the main checkout after moving there`. This is not a MECHANISMS.md entry, so it is not raised as a reuse BLOCKER.
  - **Where in this contract:** `## New Mechanisms` — "Sibling skill reference file … the step that loads `../website-design/references/foundation.md`".
- **[WARN] INV-1 allows one exception (D1), but the ledger rewrites R10 as well**
  - **What is wrong:** INV-1 says rules move "with [their] wording kept (only pronouns and section headings may change)" and names D1 as "the one declared exception". R10 is "rewritten to the External skill reference form", and R08's halt sentence is recast as the halt table. A reviewer checking INV-1 literally against the diff will flag R10 as a violation.
  - **Prior artifact ignored:** Work Item Brief acceptance criterion 2 (`.claude/work-items/2026-10-22-webdesign-plugin-skills.md:37`), which INV-1 implements.
  - **Where in this contract:** `## Data Shapes → Invariants` — "The one declared exception is **D1**"; `Rule ledger` R10 — "rewritten to the External skill reference form".
- **[WARN] Uncertain Assumptions points to a Failure Mode that does not exist**
  - **What is wrong:** The Cursor/Codex sibling-layout assumption says "not trialled; stated under Failure Modes". No Failure Modes row covers Cursor or Codex. The only near row is INV-3's halt, which turns a wrong assumption into a skill that always halts on those providers, and nothing mitigates that.
  - **Prior artifact ignored:** `README.md:352-354` (the providers table promises skills work under Cursor and Codex: "yes").
  - **Where in this contract:** `## Uncertain Assumptions` — "`ASSUMED`: Cursor and Codex keep sibling skill folders together … Verification path: not trialled; stated under Failure Modes."
- **[WARN] The halt table has no row for a project root that cannot be determined**
  - **What is wrong:** INV-4 falls back from `CLAUDE_PROJECT_DIR` to "the repository holding the files being designed". That is a search, and it has no answer when the screen or page is new and no target file exists yet. The halt table has no `root-undeterminable` row, so the skill has to guess.
  - **Prior artifact ignored:** `JOURNAL.md:166-171 — 2026-10-15 — A script that reads a project-owned file must be told which project, not search for one` ("refuse when it cannot be determined"); `JOURNAL.md:187-192 — 2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file`.
  - **Where in this contract:** `## Data Shapes → Invariants` INV-4 — "else the repository holding the files being designed".
- **[WARN] `row-missing` is split out of the registered Placeholder slot term while the contract claims to reuse that term as it stands**
  - **What is wrong:** The registered term already counts a missing row as a placeholder slot. The Profile read outcome value object makes `row-missing` a separate outcome from `placeholder`, so the vocabulary now has two partitions of the same states.
  - **Prior artifact ignored:** `VOCABULARY.md:41 — Placeholder slot` ("… or an empty cell, or whose row is missing").
  - **Where in this contract:** `## Reused Mechanisms` — "The halt table reuses its definition rather than inventing a 'missing' rule"; `## Data Shapes → Value Objects` — "outcome (`usable` | `none-authored` | `placeholder` | `row-missing` | `file-missing`)".
- **[WARN] Trading-specific content ships under generic skill names, and INV-1 forbids fixing it**
  - **What is wrong:** R04 ("Real-time algorithmic trading terminal", "Power traders") and R22 ("Trading typography scale") land in `application-design`. R17 (profit/loss/buy/sell semantic colours) lands in the website foundation. Meanwhile the proposed term **Design surface** defines both surfaces generically. INV-1 rules out any rewording, so this tension is a design decision the contract makes without saying so; it is not raised as an Open Question.
  - **Prior artifact ignored:** `CONTRIBUTING.md:154` ("genuinely generic, not domain-specific wearing a general name").
  - **Where in this contract:** `## Rule ledger` R04 → AS, R17 → WF, R22 → AP; `## Business Concept` — "**Design surface** … *application screen* (a data-dense, always-on product screen …)".
- **[NIT] Three Reused Mechanisms have no MECHANISMS.md entry, and one is mis-attributed** — "Plugin agent dispatch rule … pinned by … scan 3" is pinned only for `subagent_type` literals that name plugin *agents* (`.claude/scripts/tests/test_plugin_text_scans.py:16-21, 85-98`); no scan pins skill references. "Agent-delegates-to-skill shape" and "Skill `references/` folder" are not registered at all.
- **[NIT] "README says 25" is half the story** — `README.md:419` says 25, but `README.md:354` (§ What each provider actually gets) says 22. Extension Points does cover both places.
- **[NIT] Acceptance criterion 6 names an "inventory accuracy check" that does not exist as automation** — no script or test under `.claude/scripts` or `.claude/hooks` checks skill counts. The contract replaces it with a manual listing but never says so.
- **[NIT] R22's one-line summary leaves out line 163** — line 163 is a rule ("read the design-pattern document named by the `review.documents` slot for the complete pattern catalog"). It moves to AP silently, while the authority rows (R09) go to WF.
- **[NIT] R11 moves "`/ui-ux-designer` domain judgement" into a skill** — the foundation would then cite the agent that loads it, and on standalone runs that agent is absent.
- **[NIT] Chat Tool Impact uses "Not applicable"** instead of one of the three sanctioned answers. It is harmless here, because Integration Surfaces is empty.

### Applicable journal entries

- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** — violated, see BLOCKER above.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by `## Data Shapes → Halt table` (placeholder, row-missing and file-missing are walked separately by the review CHECK).
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate** — heeded by the External skill reference value object (precedence sentence) and INV-6.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by the block-2 run list (`test_skill_script_lookup.py`).
- **2026-10-15 — A script that reads a project-owned file must be told which project, not search for one** — partly heeded by INV-4; see WARN (no undeterminable-root row).
- **2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file** — partly heeded (`file-missing` is its own row); see WARN.
- **2026-10-15 — Locate a script from the plugin root, never from the main checkout after moving there** — not addressed; the skills run no script, but the same principle bears on the sibling-file read (see WARN).
- **2026-10-04 — Detect an install mode by what the sync actually delivers** — not addressed. The contract cites it as heeded, but nothing in this work detects an install mode by file presence.

### What the critic did not check

- No project tier exists in MECHANISMS.md, VOCABULARY.md or JOURNAL.md; `INTEGRATION.md` and `.scout-cache/registry-digest.md` are absent. The checks used the Universal tier only.
- `.claude/north-stars/` does not exist, so item 13 produced no findings.
- The ledger line ranges R01-R37 were checked against the worktree's `agents/ui-ux-designer.md` (430 physical lines, last content line 429), not against `origin/master` directly; no shell was available. Every range matches the worktree file, and every non-blank, non-heading line is allocated.
- Counts and versions confirmed: 26 `skills/*/SKILL.md` on disk; the manifests say 22 in all four descriptions (`plugin.json:5`, `.claude-plugin/plugin.json:6`, `.claude-plugin/marketplace.json:14`, `.cursor-plugin/plugin.json:4`); five version entries (`plugin.json:4`, `.claude-plugin/plugin.json:5`, `.cursor-plugin/plugin.json:3`, `.claude-plugin/marketplace.json:8` and `:15`), matching `check_version_bump.py:17-18` and `versions_in` at `:38-48`. `.agents/plugins/marketplace.json` carries neither a version nor a count.
- `derive_area.py` was not run. `area-mapping.json` holds `"areas": {}`, so no non-fallback area can exist, and the one follow-up stub exists on disk.

---

## Lessons referenced

- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate** — heeded by the External skill reference value object and INV-6: every advisory mention states that this plugin's rules and `review.documents` win.
- **2026-10-15 — A script that reads a project-owned file must be told which project, not search for one** — heeded by INV-4.
- **2026-10-16 — A "missing project file" refusal must cover both the unset root and the set-but-absent file** — heeded by the halt table (`file-missing`, `row-missing`, `placeholder` are separate rows).
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by the review gate checklist, which walks the placeholder and missing-row rows of the halt table in the skill text.
- **2026-10-04 — Detect an install mode by what the sync actually delivers** — heeded by INV-3 and the sibling-file ASSUMED entry: the foundation must resolve in plugin and vendored layouts, or halt.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by the run list: `test_skill_script_lookup.py` scans every skill markdown file, so it is run even though the new skills carry no lookup block.
- Orthogonal to north-stars: none active (`.claude/north-stars/` holds no active thought; the brief's pre-grade `none` is confirmed).

---

## Implementation Handoff

### 1. Design skills (`ui-ux-designer`)

**Depends on:** none

**Files to touch:**
- `agents/ui-ux-designer.md`
- `skills/website-design/SKILL.md`
- `skills/website-design/references/foundation.md`
- `skills/application-design/SKILL.md`
- `skills/application-design/references/application-patterns.md`
- `CONTRIBUTING.md`
- `README.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`

**Pre-written TASK block:**
```
TASK: Move the design method out of agents/ui-ux-designer.md into two new skills, website-design
  (owns the design foundation) and application-design (the dense product-screen layer, which reads
  the foundation from its sibling), slim the agent, document the External skill reference
  convention, and update the inventory, the skill counts and the version.
CONTEXT: concept contract at .claude/concepts/2026-10-22-webdesign-plugin-skills.md. The Work Item
  Brief is .claude/work-items/2026-10-22-webdesign-plugin-skills.md. Do NOT read or run
  C:\Users\lneni\drop-scalpingmachine-prefix-dbs.ps1.
FILES: the eleven paths under "Files to touch" of block 1, and nothing else.
CONSTRAINTS:
  - The Rule ledger is authoritative. Move every row to its stated destination with its wording
    kept. Do not rewrite, merge or correct a rule. D1 (the profile read-and-halt step in Step 1
    of both SKILL.md files) is the only permitted duplicate.
  - Write each SKILL.md with frontmatter name, a trigger-rich description, and
    user_invocable: true. Keep long material in the references/ file.
  - Write Step 1 of both skills from the Halt table exactly. The profile is
    <project root>/.claude/project-profile.md (INV-4), never the plugin's own copy.
  - application-design loads ../website-design/references/foundation.md and halts, naming the
    path, when that file is absent (INV-3).
  - Every External skill reference: fully qualified name, the word advisory, the precedence
    sentence, and "if absent, continue without it". frontend-design:frontend-design goes in
    website-design only; the dataviz row goes in application-design, using the name the user
    gives in Q1.
  - Agent: tools gains Skill. Keep R01-R03, R15, R36 and R37. Add the section "Method lives in
    the skills", which invokes agentic-auto-improve:application-design or
    agentic-auto-improve:website-design and stops if the skill cannot load. Leave the skills:
    preload as Q2 decides.
  - CONTRIBUTING.md: a new section "Referencing another plugin's skill". README.md: the § Skills
    list (add unit-testing, application-design, website-design), the counts in § What is
    included and § What each provider actually gets, and one pointer sentence. Count by listing
    skills/*/SKILL.md, never from the old README.
  - Manifests: the skill count in all four descriptions; version 0.9.16 (or as Q4 decides) in
    all five entries. Change no other number.
  - Invoke application-design once from this worktree and record in the HANDOFF the foundation
    path it resolved (this verifies the ASSUMED sibling read).
  - Do not invent data shapes. The contract is authoritative.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-22-webdesign-plugin-skills.md
  contract_status: approved
```

### 2. Review (`fullstack-code-reviewer`)

**Depends on:** 1

**Files to touch:**
- `.claude/reviews/2026-10-22-webdesign-plugin-skills/t2-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review sub-task t1-design-skills against the contract, and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-10-22-webdesign-plugin-skills.md
FILES: .claude/reviews/2026-10-22-webdesign-plugin-skills/t2-review-fullstack-code-reviewer.md
CHECK (each item is its own line under "## What was checked"):
  - Every Rule ledger row R01-R37 is present in its stated destination, with wording kept,
    and in no other place (diff origin/master..head of agents/ui-ux-designer.md against the
    four new files). D1 is the only duplicate.
  - The agent keeps only R01-R03, R15, R36, R37 and the "Method lives in the skills" section;
    tools includes Skill.
  - Step 1 of both skills covers every row of the Halt table, including placeholder,
    row-missing and file-missing as separate cases, and reads the project's profile (INV-4).
  - application-design halts when the sibling foundation is missing (INV-3).
  - The CONTRIBUTING.md convention exists, and every External skill reference added follows it
    (INV-6).
  - The README skill list and counts and the four manifest descriptions match a listing of
    skills/*/SKILL.md.
  - Run: py -3 .claude/scripts/check_version_bump.py --base origin/master
  - Run: py -3 .claude/scripts/tests/test_plugin_text_scans.py
  - Run: py -3 .claude/scripts/tests/test_skill_script_lookup.py
  - Run: py -3 .claude/scripts/tests/test_check_version_bump.py
CONSTRAINTS:
  - Write the artefact in the six-section shape the template fixes. The file does NOT exist
    yet; you create it. Nobody pre-created a stub, and you must not treat its absence as
    anything but "this review has not run".
  - Name the commit range you reviewed, base..head.
  - "## Evidence" carries the commands with their exit codes, and the files read. It is never
    empty.
  - End the header with the verdict line, alone on its line, exactly one of:
    "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked".
  - Also write the Gate Output, t2-review-fullstack-code-reviewer.gate.json, beside the report
    in the same diff: {"supersedes": [], "checklist": [{"item": "<a Review checklist line,
    verbatim>", "outcome": "met | partly-met | not-met | not-applicable"}]}, listing every
    Review checklist item.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-22-webdesign-plugin-skills.md
  contract_status: approved
```

### 3. Scope note on plugin validation

The `plugin-dev:plugin-validator` run (acceptance criterion 8) belongs to the main session at `/verify-before-done`. Neither sub-task agent can dispatch another agent. The run itself follows the convention this contract adds: if the `plugin-dev` plugin is absent, the run is declared a Not-performed item with a Disclosure line, and nothing is installed.

---

## Review checklist (filled in after implementation)

- [ ] Implementation matches Data Shapes exactly — partly-met (.claude/reviews/2026-10-22-webdesign-plugin-skills/t2-review-fullstack-code-reviewer.md)
- [x] Reused Mechanisms are actually reused (no parallel implementations introduced) — evidence: .claude/reviews/2026-10-22-webdesign-plugin-skills/t2-review-fullstack-code-reviewer.md
- [x] New Mechanisms (if any) promoted to `MECHANISMS.md` — evidence: .claude/reviews/2026-10-22-webdesign-plugin-skills/t2-review-fullstack-code-reviewer.md
- [x] New vocabulary terms promoted to `VOCABULARY.md` — evidence: .claude/reviews/2026-10-22-webdesign-plugin-skills/t2-review-fullstack-code-reviewer.md
- [ ] Integration surfaces reflected on both backend and frontend sides — not applicable (.claude/reviews/2026-10-22-webdesign-plugin-skills/t2-review-fullstack-code-reviewer.md)
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced — not applicable (.claude/reviews/2026-10-22-webdesign-plugin-skills/t2-review-fullstack-code-reviewer.md)
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface) — not applicable (.claude/reviews/2026-10-22-webdesign-plugin-skills/t2-review-fullstack-code-reviewer.md)
- [x] `Status` flipped to `implemented`
