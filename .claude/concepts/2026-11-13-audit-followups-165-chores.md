# Concept Contract — Follow-ups from the issue-165 audit: manifest counts, agent chat-tool text, review nits F5 and F6

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-13
**Requested by:** user
**Status:** approved
**Work Item Brief:** .claude/work-items/2026-11-13-354-audit-followups-165-chores.md
**Tracking issue:** #354
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. Implementer agents refuse to run unless `Status: approved` or `Status: implemented`. The `concept-gate.py` hook reads `Files to touch`. Lifecycle, budget rule and management commands: `.claude/templates/concept-contract.md`.

---

## Business Concept

- **What is this thing, in domain language?**
  A small cleanup chore for the shipped plugin, made of the three items the issue-165 contract (`.claude/concepts/2026-11-11-audit-followups-165.md`, landed) moved out. (1) The four plugin manifests state wrong counts ("28 skills", "14 agents"); the tree has 34 skills and 15 agents. They get the real counts and a drift test that reads the real manifests. (2) Two shipped agents still carry one consuming project's chat-tool file names, folder, agent and contract. They get generic text, and the template pin from block 3 of the parent grows to cover them. (3) Two review nits from the parent's block-10 review: the `/task` skill names one path two ways (F5), and two tests repeat their import setup (F6). The change touches shipped files, so the plugin version goes up one patch step.

- **Existing VOCABULARY.md terms that apply:** **Parent Branch Delivery Rule** (`VOCABULARY.md:74`), **Layout defect** `sub-task-raises-version` (`:75`), **Plugin-delivered asset** (`:92`), **Flat worktree**, **Project profile** (MECHANISMS), **Placeholder slot**.

- **New terms proposed for VOCABULARY.md:** none. The three value-object names below (Count claim, Genericity passage, Text pin) are this contract's labels for test shapes inside two test files; no operator, skill or agent meets them, so they are not domain terms. The reviewer's janitor step may still promote one if a later contract reuses it.

### Verification against this tree (2026-11-13)

| # | Claim | Found |
|---|---|---|
| V1 | Manifest descriptions are stale | `plugin.json:5` "28 skills"; `.claude-plugin/plugin.json:6` and `.claude-plugin/marketplace.json:14` "28 skills, 14 agents and 14 hooks"; `.cursor-plugin/plugin.json:4` "28 skills and 14 subagents". The marketplace top-level description (`:7`) has no count. All five version fields read `0.20.1` |
| V2 | The tree | 34 `skills/*/SKILL.md`, 15 `agents/*.md` (Glob, 2026-11-13) |
| V3 | Block 9's count helpers exist | `count_oracles`, `claim_violations`, `_CLAIM_RE` (`test_repo_consistency.py:503-529`); `subagents` maps to the agent measure (`:491`). `manifest_descriptions` (`:128-133`) and `MANIFESTS` (`:59-64`) exist. No real assertion reads a manifest for skills or agents (`:583`) |
| V4 | Critic item 7 cites a consuming project's contract | `agents/contract-critic.md:72`: "reference `2026-04-21-strategy-learner-phase-a2-...` as the precedent" |
| V5 | The reviewer's training-data section is project text | `agents/fullstack-code-reviewer.md:166-178`: `ChatToolDefinitions.cs`, `SystemPromptBuilder.cs`, `ChatToolExecutor.cs`, `python/training-data/synthetic/`, `llm-training-engineer`, and lines 173-176 (strategy creation, watchlist and screener, scheduling and backtest) |
| V6 | Block 3's pin | `TestChatToolImpactSectionIsGeneric` and `chat_tool_violations` (rules 1-7), `test_plugin_text_scans.py:664-773`. No rule catches a bare folder path such as `python/training-data/synthetic/` |
| V7 | F5 | `skills/task/SKILL.md:456-457` write `<plan path>`; `:467` and `:482` write `.claude/worktrees/<wt>`; `:475` writes `<repo>/.claude/worktrees/<wt>/`; `:442` says `<wt>` is used "in the commands below". Step 1.5 (`:118`) defines the plan's `path` |
| V8 | F6 | `test_agent_skill_preloads.py:100-126`: two tests repeat the same `sys.path` loop and two imports |
| V9 | A single block is not judged by the layout rule | `delivery_layout` returns `None` below two mergeable blocks (`pr_merged.py:1585-1587`), so `sub-task-raises-version` (`:1632-1638`) cannot fire on one block |

---

## End-User View

Not applicable. Reason: no Angular UI surface is touched; the users are plugin operators.

---

## Data Shapes

### Entities

Not applicable. Reason: no persistent entity; the change is shipped text, manifest strings and tests.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Count claim (reused from the parent) | surface (one manifest description), noun, stated number, oracle | The unit the new drift test pins. Oracles come from `count_oracles` (skills, agents; "subagents" reads agents; hooks as today) |
| Genericity passage | file, bounds, rules 1-8 | The three passages the pin scans: the template's `## Chat Tool Impact` section (unchanged bounds), critic item 7 (the one line that starts `7. **Integration surface omission`), and the reviewer's section from `## LLM Training Data Maintenance` to the next `## ` heading |
| Text pin | file, bounds, rule, planted-wrong fixture | Every new check. The control fails on its made-up fixture, and the real assertion fails on today's tree before the fix |

**Rule 8 (new):** a passage names no folder path outside `.claude/`. A segment is one or more word characters, `.` or `-`, so it may start with `.`; a backtick, space or other character ends it. A path is `/`-separated segments with two boundaries, like rule 5's (`test_plugin_text_scans.py:673`): it starts where the previous character is not a segment character or `/`, and it ends where the next character is not one either (a sentence-ending `.` is not part of the path). It fires when it has one or more segments followed by a final `/`, or three or more segments with no final `/`. A two-segment form with no final `/` (`frob/data`) does not fire, because it cannot be told from prose such as `and/or`; that residual is stated, not hidden. A path whose first segment is exactly `.claude` does not fire. Must fire: `frob/train-data/synthetic/`, `` `frob/data/` ``, `.frob/zed/`, `frob/train-data/synthetic`. Must not fire: `UI/admin-only`, `endpoint/event`, `` `rest`/`docs` ``, `and/or`, `frob/data`, `.claude/frob/`, `.claude/hooks/sentinel-paths.json`.

**Invariants**
- I-1 Every count claim in every manifest description equals its oracle, read at test time and never written into the test as a number. Each of the four plugin descriptions keeps its nouns: all four state skills; `.claude-plugin/plugin.json` and the marketplace plugin entry also state agents and hooks; `.cursor-plugin/plugin.json` also states subagents. A description that drops one of its nouns fails, so the test proves it read a count.
- I-2 In the manifests only the four description strings and the five version fields change. The five versions are equal and one patch step above the default branch's version at merge time.
- I-3 Critic item 7 keeps its BLOCKER severity, its trigger and the heading `## Chat Tool Impact`. Its three sanctioned answers become the template's own answer heads, quoted word for word without the final period: `Yes — this contract adds a chat tool`, `No — this endpoint/event is UI-only or admin-only`, `Deferred to a follow-up mini-phase` (`concept-contract.md:222`, `:230`, `:232`). Its precedent becomes the template's `## Chat Tool Impact` section ("Why this section exists"), not a contract. The pin reads the three heads from the template at test time, so the critic and its authority cannot drift apart; nothing in the test freezes them.
- I-4 All three Genericity passages pass rules 1-8 against `plugin_agent_names()` and the shipped skill names. Rule 8's two-segment exemption is what lets item 7 keep `endpoint/event` (I-3) and still pass; the real item-7 assertion proves both at once.
- I-5 The reviewer section names no project-profile slot, cites no sentinel file and works out no file's role itself. It reads only the contract under review and the diff, whatever that contract's `## Chat Tool Impact` answer is, or if the answer is missing. (a) When the diff touches a file that the contract names as the project's chat-tool definition, executor or system-prompt file (in any section; answer 1's "Sentinel files to touch" line is one such place), the reviewer raises a WARNING if neither the diff nor the contract covers training examples for the change. (b) When the contract names no such file but its `## Integration Surfaces` names a REST endpoint or SignalR event, the reviewer raises one WARNING that asks the author whether a changed file is one of those three files and, if so, whether training examples need an update. (c) Otherwise, and when no contract is under review, the section raises nothing (a stated residual). Both findings are WARNINGs, never blocking. The agent to launch is "the project's model-training agent or skill, if it has one", the template's wording (`concept-contract.md:228`, `:232`).
- I-6 In `/task` Step 5c the worktree's path has one name, `<plan path>`: the plan's `path` from Step 1.5, read from the plan and never rebuilt from the folder name. `<wt>` no longer appears in Step 5c. Line 442 keeps the folder-name rule as the helper applies it (`MECHANISMS.md:82`, `VOCABULARY.md:61`): `<YYYYMMDD>-<action>-<slug>`, cut at a hyphen to at most 60 characters, with `-2` to `-9` added when the name is taken. That is why the path is read from the plan.
- I-7 F6 changes no test name, assertion or count: the "Ran N tests" line of `test_agent_skill_preloads.py` is the same before and after.
- I-8 `HookCountTests` and `ReadmeCountPinTests` are not edited, apart from the I-2 wording of the latter's docstring if the implementer needs it to stay true.

### Events

Not applicable. Reason: none emitted or listened for.

### Commands (if any)

Not applicable. Reason: no new command, subcommand or flag.

---

## Reused Mechanisms

- `Plugin version check modes` — consumed as-is. Default mode (raised against `--base`) judges this single pull request. `MANIFESTS` is why the work stays one block (V9).
- Block 9's Count-claim oracle (`count_oracles`, `claim_violations`, `manifest_descriptions`, in `test_repo_consistency.py`) — extended by one test class that applies them to the real manifests. Nothing is re-implemented.
- Block 3's genericity pin (`chat_tool_violations`, `chat_tool_section`, `plugin_agent_names`, `skill_names`, `_section`, in `test_plugin_text_scans.py`) — extended by rule 8 and by two more passages.
- `Project profile` — not used. No slot holds which agent trains a model, which file plays which chat-tool role, or where training examples live (`implementers`, `project-profile.md:35`; `review.documents`, `:34`), so the reviewer text names none (I-5). It needs none of those facts: a file's role comes only from the contract under review, and when the contract is silent the reviewer asks instead of inferring. So the `MECHANISMS.md:69` rule (a fact no slot covers is a template defect) is not hit, and no slot is added. Brief criterion 5 ("cites the project-profile slots") is narrowed to this (Q2, accepted by the owner).
- `Flat worktree helper` — consumed as-is; F5 names its plan's `path` one way.

---

## New Mechanisms (if any)

None.

---

## Extension Points

- `test_repo_consistency.py`: a new class (for example `ManifestCountPinTests`) beside `ReadmeCountPinTests`, plus a line (5) in the module docstring. Its failure message names the remedy: correct the description in the same pull request, or, when the change is on a parent branch, take the owner-only exits in Failure Modes and see the follow-up stub below.
- `test_plugin_text_scans.py`: rule 8 joins `chat_tool_violations` with the made-up controls listed under Rule 8. Two new real assertions, one per agent passage, each asserting that the passage was found and is non-empty; the reviewer's also holds no `project-profile` and no `sentinel-paths`. One I-3 assertion on critic item 7: it reads the three answer heads from the template's `## Chat Tool Impact` section and asserts each is in item 7, with `BLOCKER`, `## Chat Tool Impact` and "Why this section exists". Its planted control, an item 7 that still says `Yes — declares schema`, fails.
- `test_flat_worktree.py`: one pin on the text from `### 5c` to `### 5d`. It reads the real skill only, never the fixture at `test_flat_worktree.py:834`. Its assertions, each with a made-up 5c that fails it:
  - no `<wt>` anywhere, prose or command (covers 467, 475, 482). Fails on: a 5c with one prose `.claude/worktrees/<wt>/`.
  - `<plan path>` in each of the three command blocks (today `:454-458`, `:466-468`, `:481-483`). Fails on: a 5c whose second block names neither `<wt>` nor `<plan path>`.
  - `<plan path>` in the bullet that starts "Every folder OUTSIDE the repo". Fails on: a 5c whose bullet names neither.
  - the line-442 text (I-6) holds `60 characters`, `-2`, `-9` and `Step 1.5`. Fails on: a 5c whose line drops the 60-character cut, and one that drops the suffix.
  - One made-up 5c that meets all four passes.
- On approval the main session renames the three stubs to `.followup.superseded.md` with a `Superseded by: .claude/concepts/2026-11-13-audit-followups-165-chores.md` line: `.claude/concepts/followups/2026-11-11-manifest-description-counts.followup.md`, `.../2026-11-11-agent-chat-tool-genericity.followup.md`, `.../2026-11-12-t10-review-nits-f5-f6.followup.md`. It also writes `contract: .claude/concepts/2026-11-13-audit-followups-165-chores.md` into the brief, which today holds `UNKNOWN`.

---

## Integration Surfaces

Not applicable. Reason: plugin manifests, two agent texts, one skill text and their tests; no endpoint, event or DTO.

---

## Adjacent Areas

Not applicable. Reason: `.claude/area-mapping.json` declares no areas (`"areas": {}`), so `derive_area.py` puts this contract in the `uncategorized` fallback (run by the main session) and there is no area to score. `cross_area_scan.py` was not run, because the architect has no shell, so no scan result is claimed.

Noticed by the architect:

| Area | Decision | Implication / Reason | Handle |
|------|----------|----------------------|--------|
| manifest counts under a parent branch | follow-up handle | The new pin (and the existing hook pin) goes red on a sub-task that adds a skill, agent or hook, and neither a sub-task nor the landing may correct a manifest description | `.claude/concepts/followups/2026-11-13-manifest-counts-under-parent-branch.followup.md` |

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

---

## Chat Tool Impact (REQUIRED when this contract adds or changes a REST endpoint or SignalR event)

2. **No.** This contract adds no endpoint and no event.

---

## Non-Goals

- Any other consuming-project text in shipped files beyond critic item 7 and the reviewer's training-data section.
- The template's `## Chat Tool Impact` heading and its three answers (block 3 of the parent keeps them).
- Any count outside the four manifest descriptions; the README pins stay with the parent's block 9.
- Review findings F1-F4 of the parent's reviews.
- Teaching the landing to refresh manifest counts (follow-up stub, Q1 answered (a)).
- A new project-profile slot for training data (Alternatives, option E).

---

## Confidence

Confidence: Medium. Strong: V1-V9, the hook oracle (14) and `origin/master` at 0.20.1 were read from this tree, and the text edits are small and pinned. Weak: three things only a shell or the merge moment can show. `master` may move before the merge. `cross_area_scan.py` was not run. Whether a branch on `origin` adds or removes a skill or agent is unchecked (the Run-first check in the TASK block measures it; a branch that was never pushed stays unseen). The parent-branch gap itself (Q1) is deferred to the stub, not closed.

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** one single-block contract, one pull request to `master`, one patch raise; review through `/flow`'s reviewer step.
  - Why: the manifests are version files. A single block is not judged by the layout rule (V9), so it may list them, and there is one route into the default branch and one raise (journal 2026-10-30).
- **Option B (rejected):** one block per stub plus a review gate, on a parent branch.
  - Why rejected: two or more mergeable blocks bring in the Parent Branch Delivery Rule, and the manifest block becomes the Layout defect `sub-task-raises-version`.
- **Option C (rejected):** the manifests as one single-block work item, the other two items as a second one.
  - Why rejected: two deliveries and two version raises for an M-size chore, with no review gain; the three edits touch disjoint files.
- **Option D (offered as Q1):** number-free manifest descriptions with a pin that they stay number-free.
  - Why not chosen by default: the owner asked twice for real counts and a drift test (parent Q6, brief criteria 1-2).
- **Option E (rejected):** add a training-data slot to the project profile.
  - Why rejected: no existing slot holds the fact (the critic's BLOCKER), and a new slot would be a new mechanism with no consuming project asking for it. The Project profile rule (`MECHANISMS.md:69`) requires a slot only when an agent *needs* a fact no slot covers. I-5 removes the need: the reviewer takes a file's role only from the contract under review, asks a WARNING question when the contract is silent, and names the agent in the template's generic words. If a later project wants the reviewer to know its training folder, that is the time to add a slot, in the same change, as the rule says.

---

## Uncertain Assumptions

- `VERIFIED via file reads and Glob 2026-11-13`: V1-V9 at the lines cited.
- `VERIFIED via test_plugin_text_scans.py:739` and the template's lines 216-234: `UI-only/admin-only` and `` `rest`/`docs` `` already pass rule 5; the template section's only slashed forms are `endpoint/event` and `` `rest`/`docs` `` (two segments, no final `/`) and `.claude/hooks/sentinel-paths.json` (exempt), so rule 8 leaves the template green.
- `VERIFIED via grep of .claude/scripts/tests`: no test pins Step 5c's `.claude/worktrees/<wt>` lines; the one hit (`test_flat_worktree.py:834`) is a planted control for "no git worktree add", which the F5 edit does not touch.
- `VERIFIED via .git/refs/remotes/origin/master` (2fb4770, this branch's base) and `plugin.json:4`: `master` was at `0.20.1` at the last fetch. `ASSUMED`: it is still there when the pull request merges. If it moved, the raise is one patch above `master`'s version, and all five fields move together. Verification: `py -3 .claude/scripts/check_version_bump.py` before committing.
- `VERIFIED via Glob of .claude/hooks/*.py` against `hook_file_count` (`test_repo_consistency.py:90-93`): 14 hook files (15 non-underscore `.py`, minus `gate-launch.py`), so the "14 hooks" in the two descriptions stays.
- `VERIFIED via .claude/area-mapping.json:14`: `"areas": {}`. `NOT RUN` (no shell): `cross_area_scan.py`.
- `VERIFIED via grep of .claude/concepts` in this tree: only two contracts read `Status: approved` (`2026-10-16-recorded-issue-offer-outcome`, `2026-10-30-parent-branch-delivery-rule`), and neither lists a new skill, agent or hook file. `ASSUMED`: no branch on `origin` adds or removes a skill or agent. A contract may live only on its own branch, so the check reads branches, not contracts. Run-first, which lists, per remote branch, every `skills/*/SKILL.md` or `agents/*.md` it added or deleted since it left `master` (empty output means nothing to stop for):
  ```powershell
  git fetch origin
  git branch -r --format="%(refname:short)" | Where-Object { $_ -like "origin/*" -and $_ -ne "origin/master" -and $_ -ne "origin/HEAD" } | ForEach-Object { $b = $_; git diff --name-status --diff-filter=AD "origin/master...$b" -- "skills/*/SKILL.md" "agents/*.md" | ForEach-Object { "$b $_" } }
  ```
  The hook count is left out: its pin already exists and has the same gap (stub).

---

## Failure Modes & Mitigations

- **FM:** a skill or agent lands on `master` before this pull request merges, so the new pin is red.
  - **Mitigation:** the pin reads the oracle at run time (I-1). CI's `tests` job runs `test_repo_consistency.py` on the pull request (`.github/workflows/version-bump.yml:24-33`), and `/ship` re-runs it after taking in `master`.
- **FM:** another pull request takes `0.20.2` first.
  - **Mitigation:** `Plugin version check modes` default mode fails the check; raise again one patch above `master`.
- **FM:** a later multi-sub-task contract adds a skill or agent, and its sub-task cannot correct a manifest.
  - **Mitigation:** the pin's failure message names the follow-up stub, which carries the design (Q1 answered (a)). The hook pin has the same gap today.
- **FM:** a parent branch already in flight has merged sub-tasks that add or remove a skill or agent. From its sync sub-task on (journal 2026-11-07), every route it takes turns red on the new pin.
  - **Way out (owner-only, journal 2026-10-30):** the implementer pastes the Run-first check (Uncertain Assumptions) before merging. If it lists a branch, the owner picks an exit; the pin's failure message names both. (i) Recommended: hold this pull request until that branch lands, then recount; no route turns red. (ii) Otherwise, per route: the sync sub-task, each later sub-task and the landing pull request merge with `tests` red on this pin alone, each recording a finding in its review artefact that cites the stub; `master` after the landing goes green through a single-block recount pull request (it may list the manifests, V9; one patch raise), which is the next pull request merged into `master`. Detail is in the stub, whose design removes the need for both exits.
- **FM:** rule 8 fires on generic prose.
  - **Mitigation:** its must-not-fire controls (Rule 8) include `UI/admin-only`, `endpoint/event`, `` `rest`/`docs` `` and `and/or` (journal 2026-10-05: made-up names only).
- **FM:** the critic rewrite weakens item 7.
  - **Mitigation:** the I-3 pin.
- **FM:** the reviewer text points at a slot or file that does not hold the fact it needs.
  - **Mitigation:** I-5 names no profile slot and no sentinel file; the real assertion on the reviewer passage checks that it holds no `project-profile` and no `sentinel-paths` string.
- **FM:** the F6 refactor drops or renames a test.
  - **Mitigation:** I-7; the pull request pastes the "Ran N tests" line from before and after.

---

## Open Questions for User

- [x] **Q1 — the new pin widens the parent-branch gap: real counts or number-free descriptions?** Answered by the owner, 2026-11-13: (a) real counts; the landing-time refresh is designed in the follow-up stub.
- [x] **Q2 — may brief criterion 5 be narrowed so the reviewer passage cites no project-profile slot (I-5)?** Answered by the owner, 2026-11-13: accepted.
- [x] **Q3 — one single-block contract (one pull request, one patch raise), departing from journal 2026-11-02's review-fix rule?** Answered by the owner, 2026-11-13: confirmed (Option A).

---

## Critique

**Round 1** (1 BLOCKER, 5 WARN, 3 NIT; superseded by the revision and judged again below) moved to `.claude/contract-history/2026-11-13-audit-followups-165-chores.round-1.md`.

### Second pass

**Critic:** contract-critic (cold context)
**Date:** 2026-11-13
**Verdict:** warnings-only

#### Status of the first pass's findings

- **[BLOCKER] I-5 sends the reviewer to two profile slots**: resolved as worded. I-5 and Option E name no slot, and the reviewer pin checks for no `project-profile` string. A gap remains in the replacement source; see the first new WARN.
- **[WARN] Rule 8 vs `UI/admin-only`**: resolved. The final-`/` lookahead (not followed by a word character, `-` or `.`) lets `UI/admin-only` pass, the same way rule 5's lookbehind does (`test_plugin_text_scans.py:673`, `:739`).
- **[WARN] Confidence High over ASSUMED entries**: resolved (`Confidence: Medium`, with the weak areas named).
- **[WARN] `<plan path>` misstates the folder name**: resolved in I-6 and TASK (3), which keep the 60-character cut and the `-2` to `-9` suffix (`MECHANISMS.md:82`). The new text is not pinned (NIT below).
- **[WARN] In-flight parent branches have no way out**: partly resolved. There is a Failure Mode with two owner-only exits, and the stub repeats them. The exits and the Run-first check have new gaps (WARNs below).
- **[WARN] Claimed heed of "Keep a review-fix block to the review's findings"**: resolved. The contract now records it as a departure. The owner's sign-off on that departure is still in prose, not in Open Questions (WARN below).
- **NITs (Adjacent Areas wording, F5 pin prose coverage, value-object names)**: resolved. The F5 pin now asserts no `<wt>` anywhere in 5c. The follow-up stub cited in Adjacent Areas exists on disk.

#### Findings

- **[WARN] I-5's second trigger source exists only when the contract answers "Yes", and the diff does not say which file plays which role**
  - → Addressed by: the second revision of I-5 (reviewer trigger reads only the contract under review and the diff, for any answer; owner asked for the revision 2026-11-13).
  - **What is wrong:** I-5 says the reviewer finds the chat-tool definition, executor and system-prompt files in "the diff, and the `## Chat Tool Impact` answer ... (its 'Sentinel files to touch' line)". In the template, that line is a sub-bullet of answer 1 only (`concept-contract.md:222-228`). Answers 2 and 3 (`:230`, `:232`) have no such line. A diff lists changed paths but not their roles. So for a "No", "Deferred" or missing answer, the reviewer still has to work out which changed file is the chat-tool definition, which is a fact no declared source holds. The claim that "the reviewer needs neither fact" is stronger than the text supports, and this is the same `MECHANISMS.md:69` fact gap that the first BLOCKER was about, moved to a new place.
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md:222-232`; `MECHANISMS.md:69` (Project profile: "an agent needing a fact no slot covers is a defect in the template").
  - **Where in this contract:** `## Data Shapes → Invariants` I-5: "which it finds in two places that really hold them: the diff, and the `## Chat Tool Impact` answer of the contract under review (its 'Sentinel files to touch' line)"; `## Reused Mechanisms` Project profile: "It needs neither fact".
- **[WARN] I-3 freezes three answer strings that do not match the template section it now cites as the precedent**
  - → Addressed by: I-3 now quotes the template's own answer heads, read at test time; owner asked for the revision 2026-11-13.
  - **What is wrong:** I-3 keeps item 7's `Yes — declares schema`, `No — UI/admin-only with justification`, `Deferred — names follow-up contract` word for word, and makes the template's `## Chat Tool Impact` section the precedent. That section's answers read "Yes — this contract adds a chat tool", "No — this endpoint/event is UI-only or admin-only" and "Deferred to a follow-up mini-phase". Item 7 fires on a contract "set to anything other than the three sanctioned answers", so the pin would lock in a mismatch between the critic and the authority it points to. A strict critic would flag a contract that follows the template exactly. Non-Goals also excludes the template's answers from this change.
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md:222`, `:230`, `:232`.
  - **Where in this contract:** `## Data Shapes → Invariants` I-3: "the three sanctioned answers word for word ... Its precedent becomes the template's own `## Chat Tool Impact` section".
- **[WARN] Exit (ii) covers only the sync sub-task. The later sub-tasks, the landing and `master` after the landing stay red with no named exit**
  - → Addressed by: the Failure Mode names an exit for every route (detail in the follow-up stub); owner asked for the revision 2026-11-13.
  - **What is wrong:** under exit (ii), the parent branch keeps the stale description after its sync sub-task merges red, because no sub-task and not the landing may correct it (the contract's own Q1 and the stub's "What was noticed"). Every later sub-task pull request, the landing pull request into `master`, and `master` itself after the landing then fail the same pin. Exit (ii) names only "that branch's sync sub-task". The way out does not cover every route that turns red, and no step makes `master` green after the landing.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery, not only the one the author had in mind"; `JOURNAL.md` 2026-10-30 "A rule that refuses must give already-delivered work a named way out" ("make the loop's next command name it": here a test failure message names the exit, not the loop's next command).
  - **Where in this contract:** `## Failure Modes & Mitigations` "(ii) Merge that branch's sync sub-task with the `tests` job red on this pin alone"; `followups/2026-11-13-manifest-counts-under-parent-branch.followup.md` "Way out until this stub is delivered".
- **[WARN] The Run-first check does not measure the condition it is meant to detect**
  - → Addressed by: the Run-first check is a per-branch `git diff --diff-filter=AD` for skill and agent additions; the never-pushed-branch gap is stated in Confidence.
  - **What is wrong:** the Failure Mode depends on whether an in-flight parent branch "has merged sub-tasks that add a skill, agent or hook". The named check is `git branch -r` plus `pr_merged.py --contract <slug> --status --json`. That JSON reports layout, `parent_branch` and `sub_task_count` (`pr_merged.py:1639`), not which files the branch added. The check also finds only contracts present in this tree, and a parent branch's contract may exist only on that branch. The TASK block's "stop and report if it finds a branch" therefore triggers on any parent branch and cannot rule out an unseen one.
  - **Prior artifact ignored:** `.claude/scripts/pr_merged.py:1639` (status payload fields); `JOURNAL.md` 2026-11-07 "A merge block's pull request must paste each required output, not tick a line that says it passed" (a pasted output must prove the claim).
  - **Where in this contract:** `## Uncertain Assumptions` "Run-first: `git branch -r --list \"origin/*\"`, then `py -3 .claude/scripts/pr_merged.py --contract <slug> --status --json` for each multi-block contract".
- **[WARN] Two owner decisions are left in prose instead of under Open Questions**
  - → Addressed by: Q2 (criterion 5 narrowing) and Q3 (single block) are answered Open Questions, both answered by the owner on 2026-11-13.
  - **What is wrong:** both sentences defer a decision to "when approving" without listing it as a question. Brief criterion 5 is narrowed "as a PROPOSAL ... the owner confirms or rejects the narrowing when approving", and the review-fix departure says "the owner confirms it when approving". `## Open Questions for User` holds only the answered Q1.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22 "An accepted critic WARN or answered Open Question must amend the contract body before approval"; critic checklist item 4 (hidden Open Questions).
  - **Where in this contract:** `## Reused Mechanisms` Project profile bullet: "is narrowed to this as a PROPOSAL"; `## Lessons referenced` 2026-11-02 bullet: "the owner confirms it when approving".
- **[WARN] The Step 5c pin's presence half has no control that fails**
  - → Addressed by: each presence assertion of the Step 5c pin has a planted failing control.
  - **What is wrong:** the planted controls are one 5c with a prose `.claude/worktrees/<wt>/` (fires the absence check) and one with `<plan path>` only (passes). Nothing proves the presence assertions fail, for example with a command block that has neither `<wt>` nor `<plan path>`. The contract's own Text pin value object requires that "the control fails on its made-up fixture" for "every new check".
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-05 "Never hide a forbidden name by hashing it when the test needs a positive control"; this contract's `## Data Shapes → Value Objects` "Text pin".
  - **Where in this contract:** `## Extension Points` `test_flat_worktree.py` bullet: "The controls are a made-up 5c with one prose `.claude/worktrees/<wt>/` (fires) and one with `<plan path>` only (passes)".
- **[NIT] The Step 5c pin does not cover the new line-442 text, and "both command blocks" is ambiguous** — Step 5c has three code blocks (`SKILL.md:454-458`, `:466-468`, `:481-483`). The pin says "both", and nothing asserts that the 60-character cut and the `-2` to `-9` suffix that fixed the first-pass WARN are kept (`JOURNAL.md` 2026-11-02 "A rule titled 'every' must list every line it covers").
- **[NIT] Rule 8 does not declare its segment character set, and a folder written without a trailing `/` passes** — the `.claude` exemption implies segments may start with `.` (so `.github/workflows/` should fire), but the set is not stated. `frob/train-data/synthetic` with no final `/` passes rule 8 and rule 1 alike, yet I-4 says the passage "names no folder path".
- **[NIT] The budget rule is not applied to this revision** — the answered Q1 still carries the full drafted question, and the superseded first critique round is still inline, where `.claude/templates/concept-contract.md:22` says it should move to `.claude/contract-history/<slug>.round-<n>.md`. The caller told the critic to keep it, so the critic did not move it.

#### Applicable journal entries (second pass)

- **2026-10-30 — A rule that refuses must give already-delivered work a named way out**: partly heeded. There are owner-only exits, but they cover only the sync sub-task (WARN above).
- **2026-10-30 — A delivery rule must name every route into delivery**: violated for the routes after the sync sub-task (WARN above).
- **2026-11-07 — A parent branch ... must take the default branch in through a sub-task before its landing**: heeded by the Failure Mode that names the sync sub-task.
- **2026-11-02 — Keep a review-fix block to the review's findings**: heeded as a recorded departure. The owner's sign-off is not hoisted (WARN above).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval**: mostly heeded (I-3, I-4, I-6, Confidence and the Failure Mode were amended). Two decisions are still in prose.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control**: heeded for rule 8, not for the presence half of the 5c pin.

#### What the critic did not check (second pass)

- No shell: `pr_merged.py --status`, `derive_area.py` and the suites were not run. The `pr_merged.py` payload fields were read at `:1639` only.
- Rule 8 was judged against the passages as they stand today and the I-5 wording, not against the reviewer text that will be written.

---

## Lessons referenced

- **2026-10-30 — A delivery rule must name every route into delivery, not only the one the author had in mind** — heeded by Option A (one pull request, one raise) and by the follow-up stub, which names the route the new pin cannot cover.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded by rule 8's made-up controls, the I-3 control and one failing control per assertion of the Step 5c pin; no consuming-project name is planted.
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — heeded by the in-flight parent-branch Failure Mode: exits (i) and (ii) name every route that turns red (sync sub-task, later sub-tasks, landing pull request, `master` after the landing), in the pin's failure message and in the follow-up stub.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded by Q1-Q3, each also written into the body (stub, Reused Mechanisms, Option A).
- **2026-11-07 — A parent branch that shares files with a moving default branch must take the default branch in through a sub-task before its landing** — heeded by the same Failure Mode, which names the sync sub-task as where the pin turns red.
- **2026-11-02 — A rule titled 'every' must list every line it covers** — heeded by I-1 (each description's nouns) and I-6, whose pin covers each of lines 467, 475 (prose) and 482 (no `<wt>`), each of the three command blocks, and the new line-442 text.
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them** — heeded by I-7 and I-8.
- **2026-11-02 — A "fails the build" claim must name the workflow that runs the check** — heeded by the first Failure Mode (`version-bump.yml`, `tests` job).
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by the Run list (`test_skill_script_lookup.py`), since F5 edits two command blocks in `/task`.
- **2026-11-02 — Keep a review-fix block to the review's findings** — departed from, by decision. Block 1 puts the F5 and F6 review fixes beside two new requirements. A separate block would be a second mergeable block, which brings in the Parent Branch Delivery Rule and turns the manifests into `sub-task-raises-version` (Option A). The owner confirmed the single block on 2026-11-13 (Q3). What is kept: F5 and F6 stay limited to what the review found, and the TASK block numbers the three parts so `/flow`'s reviewer can judge each one apart.
- Orthogonal to north-stars: none active (`.claude/north-stars/` is absent).

---

## Implementation Handoff

One mergeable block, so the Parent Branch Delivery Rule does not apply: one pull request from `feature/354-audit-followups-165-chores` to `master`, reviewed by `/flow`'s reviewer step. The block itself raises the version, in the same pull request. No review block, because a second mergeable block would make the manifests a Layout defect. Run every suite with `py -3 -B <path>`. `test_plugin_doctor.py` runs with the root set; in PowerShell: `$env:AGENTIC_PLUGIN_ROOT = (Get-Location).Path; py -3 -B .claude/scripts/tests/test_plugin_doctor.py`.

### 1. Manifest counts, agent chat-tool text and review nits (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`
- `.claude/scripts/tests/test_repo_consistency.py`
- `agents/contract-critic.md`
- `agents/fullstack-code-reviewer.md`
- `.claude/scripts/tests/test_plugin_text_scans.py`
- `skills/task/SKILL.md`
- `.claude/scripts/tests/test_flat_worktree.py`
- `.claude/scripts/tests/test_agent_skill_preloads.py`

**Pre-written TASK block:**
```
TASK: Three items, in this order.
  (1) Manifests. Correct the four plugin descriptions to the oracle counts (today 34 skills, 15 agents or
      subagents, 14 hooks), changing only the numbers. Raise all five version fields one patch step above
      master's (today 0.20.1 -> 0.20.2). In test_repo_consistency.py add a class that reads the real
      manifests with manifest_descriptions and checks every description with claim_violations against
      count_oracles(PLUGIN_ROOT) (I-1), plus the noun-presence check of I-1. Its failure message names the
      remedy, the owner-only exits (i) and (ii) of the in-flight Failure Mode, and
      .claude/concepts/followups/2026-11-13-manifest-counts-under-parent-branch.followup.md.
      Paste its failing run on today's manifests, then the passing run. Run-first: paste the output of the
      PowerShell branch check in Uncertain Assumptions before committing; stop and report if it lists any
      branch (the owner picks an exit).
  (2) Agent text. Critic item 7: replace its three answer strings with the template's answer heads and
      its precedent clause with a pointer to the template's "## Chat Tool Impact" section ("Why this
      section exists"), keeping I-3. Reviewer section "## LLM Training Data Maintenance": rewrite lines
      168-178 to I-5 (a), (b), (c). Name no profile slot and no sentinel file. In
      test_plugin_text_scans.py add rule 8 to chat_tool_violations as Data Shapes defines it (segment
      characters, both boundaries, the two-segment exemption, the .claude exemption), with the four
      must-fire and seven must-not-fire controls listed there. Apply rules 1-8 to both agent passages, and
      add the item-7 pin and its control, all as Extension Points says. Paste the failing runs on today's
      agents, then the passing runs.
  (3) Nits. F5: in skills/task/SKILL.md Step 5c, use <plan path> for every mention of the worktree's path
      (lines 467, 475, 482; 456-457 already do). Rewrite line 442 to I-6: keep the folder-name rule with
      the 60-character cut and the -2 to -9 suffix, define <plan path> as the plan's path from Step 1.5, and
      drop <wt> from Step 5c. Pin it in test_flat_worktree.py as Extension Points says: four assertions,
      each with its failing made-up 5c, and one made-up 5c that passes. F6: move the two debug-routing tests of test_agent_skill_preloads.py and
      their helper into one class whose setUpClass does the sys.path setup and the two imports once (I-7).
CONTEXT: concept contract at .claude/concepts/2026-11-13-audit-followups-165-chores.md
FILES: the eleven above
CONSTRAINTS:
  - I-2: in the manifests change only the description strings and the version fields
  - I-8: do not edit HookCountTests or ReadmeCountPinTests (docstring wording only, if needed)
  - no backticked hyphenated name other than a plugin agent in the two agent passages (rule 4); cite
    no project-profile slot (I-5)
  - a red suite in the Run list stops the block; report it, never pass it on
  - Run: test_repo_consistency.py, test_check_version_bump.py, test_plugin_manifests.py,
    test_plugin_text_scans.py, test_parent_branch_rule_text.py, test_plugin_doctor.py (root set, zero
    skips), test_flat_worktree.py, test_ship_skill_sync.py, test_memory_off_parity.py,
    test_agent_skill_preloads.py (paste "Ran N tests" before and after), test_skill_script_lookup.py (slow),
    and py -3 .claude/scripts/check_version_bump.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-13-audit-followups-165-chores.md
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
