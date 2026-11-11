# Concept Contract — Follow-ups from the memory-client and cloud-engineering audit (issue 165)

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-11
**Requested by:** user
**Status:** approved
**Revision:** 2 (2026-11-11). Q1-Q7 answered. Critic BLOCKER and WARNs 1-8 folded in. Graph: nine implementation blocks and one review; block 8 depends on 3, block 10 on 1-9, every other block on none.
**Work Item Brief:** .claude/work-items/2026-11-11-165-audit-followups.md
**Tracking issue:** #165
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. Implementer agents refuse to run unless `Status: approved` or `Status: implemented`. The `concept-gate.py` hook reads `Files to touch`. Lifecycle, budget rule and management commands: `.claude/templates/concept-contract.md`.

---

## Business Concept

- **What is this thing, in domain language?**
  A cleanup bundle for the shipped plugin. Each item is a place where the plugin's own text is wrong (it repeats itself, points at files that do not exist, names agents it does not ship, states false counts) or costs tokens on every run (a 220-line step that most runs skip). One hook item is here too: it writes a false failure line on every turn. Every fix gets a pin with a planted wrong control. Behaviour questions were put to the owner and answered (Open Questions).

- **Existing VOCABULARY.md terms that apply:** **Parent Branch Delivery Rule**, **Layout defect** (`sub-task-raises-version`), **Landing version raise**, **Plugin-delivered asset**, **Project profile** (MECHANISMS), **Placeholder slot**, **Project history record**, **Memory exchange outcome**, **Flat worktree**, **Gate Output**, **Claude data root**.

- **New terms proposed for VOCABULARY.md:** none.

### Verification of every claimed defect against this tree (2026-11-11)

| # | Claim | Found | Status |
|---|---|---|---|
| V1 | `/task` holds "Step 1.5: Enter a worktree" twice | 104-118 and 120-134, word for word | open |
| V2 | Step 5c describes a recipe it does not run | 446-521. Also stale: line 444 ("go to 5c"), 453 (rule 2), 498 (VS Code paragraph: "`git worktree add` already placed…"), 559 | open |
| V3 | `/flow` Step 2.7 loads on every run | 114-333, 220 lines. Lines 186-332 apply only when `len(sub_tasks) >= 2` | open |
| V4 | Template "Chat Tool Impact" names one project's files and history | Lines 216-234 (names in block 3) | open |
| V5 | `/debug` routes to unshipped agents | Partly fixed: `docker-master-goat` is gone. Still `ingestion-data-architect` (198) and `llm-training-engineer` (201) | open (2 of 3) |
| V6 | Manifests and README say "28 skills" | The README is fixed (34 skills, 15 agents). All four manifests still say 28 skills (and 14 agents or subagents) | manifests → follow-up item |
| V7 | `memory-pager.py` logs `config-load-failed` per turn with no `memory-blocks.json` | Yes (66-71). Registered on `Stop`, no matcher. No `memory-blocks.json` at any root in this tree | open |
| V8 | Agents read a digest and INTEGRATION.md that do not exist | The per-domain list is fixed (focus rule). Unconditional reads of an absent digest or INTEGRATION.md remain in `data-architect.md:47,57,137,163`, `contract-critic.md:23,46,49,91`, `registry-scout.md:3,19`, `fullstack-code-reviewer.md:343,345`, `api-contract-reviewer.md:159`, `design-first/SKILL.md:96,212,220` | open |
| V9 | README tree counts false | `hooks/tests` 23 (tree 28), `scripts` 23+3 (27+6), `scripts/tests` 36 (45), `references` 3 (4). Hook data files: 6 `.json`, 5 without `hooks.json` | open |
| V10 | `test_pr_merged.py` count: 760 in skills, 761 in suite | `pr-merged/SKILL.md:115,121` and `advance/SKILL.md:100-101` say 760 | open |
| V11-V14 | t16 W1, I1, I2, I3 | As the review says (finish-install 92-97; `central-memory.md:18`; `contract-completion.md` lacks `default-branch-unknown`; `test_memory_off_parity.py:336-341`) | open |
| V15 | t16 I4 / t10 I4 | The reference says an empty retrieval is silent (`central-memory.md:43`). The code already writes `Memory: enabled \| <date>` for it, but the enabled branch keeps only receipts, so a re-run drops earlier `Retrieved:` and `Reported:` lines (`memory_boundary.py:774-786`) | answered Q4 |
| V16 | t16 I5 | `memory_boundary.py:770-773` keeps only receipts | answered Q5 |
| V17 | t10 I6 | `.claude/project-profile.md:38,40` | open |
| V18 | A mirror under `.claude/` | None exists (`.claude/skills/` and `.claude/agents/` are absent) | resolved |
| V19 | Existing unshipped-name guard | `test_plugin_doctor.py:295-347` would fail today on the template (`llm-training-engineer`), but it skips from a flat worktree: its parent glob finds no checkout | open (blocks 3, 4, 7) |

---

## End-User View

Not applicable. Reason: no Angular UI surface is touched; the users are plugin operators.

---

## Data Shapes

### Entities

Not applicable. Reason: no persistent entity. The one stored shape is the brief's `## Memory used` section (Value Objects).

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Count claim | surface (README line), noun, stated number, oracle | The unit block 9 pins. Oracles: skills = folders under `skills/` holding `SKILL.md` (34); agents = `agents/*.md` (15); hooks = the existing measure (a) (14); helper modules = `.claude/hooks/_*.py` (8); hook data files = `.claude/hooks/*.json` minus `hooks.json` (5); agreements = `.claude/agreements/*.md` (7); add-ons = `.claude/addons/*/addon.json` (3); templates = `.claude/templates/*` (6); references = `.claude/references/*.md` (4) |
| Text pin | file, section bounds, rule, planted-wrong fixture | Every new check. The control must fail on its fixture, and the real assertion must fail on today's tree before the fix |
| Memory used section | first line `Memory: …`, then `Retrieved:`, `Reported:`, `Captured:`, `Not sent:` | **Keep rule (Q4 + Q5):** when the new outcome carries no retrieved item and no reported entry (an `unconfigured` profile, or an `enabled` empty retrieval), `record` writes the new first line and keeps the existing `Retrieved:` and `Reported:` lines in order, then the receipts. An outcome that carries items replaces them as today |

**Invariants**
- I-1 Every remaining README count equals its oracle. The `hooks/tests/`, `scripts/` and `scripts/tests/` tree lines carry no number (Q1).
- I-2 No block lists a version file (`check_version_bump.MANIFESTS`). This contract does not change manifest text, and nothing in it changes the default branch except the one landing.
- I-3 The `/flow` move leaves behaviour unchanged. The guard, the status call, the `defects` stop and the `<= 1` stop stay in SKILL.md, and the `>= 2` body moves verbatim apart from its own point numbers.
- I-4 `memory-pager.py` writes no log record when no `claude_roots()` rank holds `memory-blocks.json`. A file at ANY rank is found and read. Any other load failure still logs `config-load-failed`. It always exits 0.
- I-5 The finish-install skill asks about `--fix` at most once per run, and never runs `--fix` without a yes. The four runs:
  - (a) The profile exists, so Stage 1a is skipped. The history-record check holds the only ask.
  - (b) Stage 1a asks and the user says yes. `--fix` runs, and the later check finds nothing missing, says so and asks nothing.
  - (c) Stage 1a asks and the user says no. Stage 1 says it needs a profile and moves to Stage 2. The later check reports the missing list, does not ask again, and names the command to run later.
  - (d) The doctor prints `plugin: NOT FOUND`. Whichever step reaches that first asks for the plugin path, and that ask is the run's one ask.
- I-6 The three I-M0 disabled tests in `test_memory_boundary.py` are not edited.
- I-7 The template keeps the heading `## Chat Tool Impact` and the three sanctioned answers (contract-critic item 7).

### Events

Not applicable. Reason: none emitted or listened for; log event names are unchanged.

### Commands (if any)

Not applicable. Reason: no new command, subcommand or flag.

---

## Reused Mechanisms

- `Flat worktree helper` — consumed as-is (block 1 removes the text that predates it).
- `Plugin version check modes` — consumed as-is. `MANIFESTS` and `pr_merged.py:1632-1638` (`sub-task-raises-version` while `versionRaise` is `true`) are why I-2 holds.
- `Two-tier registry with a generated complete index` — consumed as-is. Block 6 makes digest reads conditional and names the generator.
- `Two-layer Claude path resolution` — consumed as-is. `memory_blocks_path()` uses `_first_root_containing`, and block 5's test plants decoys at every `claude_roots()` rank.
- `Memory adapter` — extended by block 7: one keep rule inside `cmd_record`. No new subcommand, refusal or shape.
- `Project profile` — consumed as-is. Block 7 corrects two slots' placeholder prose, which stays a Placeholder slot.
- The `/task` and `/pr-merged` same-skill "read `references/<file>.md` in full; if unreadable, stop" rule — consumed as-is for `skills/flow/references/open-sub-tasks.md`.
- The README hook-count pin in `test_repo_consistency.py` (violation-list helpers plus positive controls; not registered) — extended by block 9.
- `test_plugin_text_scans.py` (`plugin_agent_names()`) and `test_plugin_doctor.py` (`NOT_SHIPPED`, `test_the_files_a_project_copies_carry_no_unshipped_name`) — consumed by blocks 3, 4 and 8. Block 4 reuses both helpers and writes neither again.

---

## New Mechanisms (if any)

None.

---

## Extension Points

- `skills/flow/SKILL.md` Step 2.7 point 3 becomes: "read `references/open-sub-tasks.md` in full before continuing; if it cannot be read, stop and report the missing file; do not continue from memory."
- `test_repo_consistency.py`: a `stale_component_counts(text, noun, expected)` helper plus a tree-line helper, each with broken-fixture controls (one control is a manifest-shaped description string). No assertion runs on the real manifests.
- `test_plugin_text_scans.py`: one class for the template section (block 3), one for skill test counts (block 8).
- `cmd_record` in `memory_boundary.py`: the keep rule.
- On approval the main session renames these three stubs to `.followup.superseded.md` and adds a `Superseded by:` line to each:
  - `.claude/concepts/followups/2026-11-01-token-efficiency-and-audit-defects.followup.md`
  - `.claude/concepts/followups/2026-11-03-readme-tree-counts-and-step-pins.followup.md`
  - `.claude/concepts/followups/2026-11-03-memory-boundary-review-leftovers.followup.md`
  It also writes `contract: .claude/concepts/2026-11-11-audit-followups-165.md` into the brief, which today holds `UNKNOWN`, an unset value.

---

## Integration Surfaces

Not applicable. Reason: the change is contained in plugin skill text, agents, one template, one hook, one script and their tests. No endpoint, event or DTO.

---

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold (`.claude/area-mapping.json` has `"areas": {}`).

Noticed by the architect:

| Area | Decision | Implication / Reason | Handle |
|------|----------|----------------------|--------|
| shipped agents' chat-tool text | follow-up handle | `contract-critic.md` item 7 and `fullstack-code-reviewer.md:170-178` carry the V4 text; no issue-165 stub names them | `.claude/concepts/followups/2026-11-11-agent-chat-tool-genericity.followup.md` |
| manifest description counts | follow-up handle | Q6: its own work item after the landing | `.claude/concepts/followups/2026-11-11-manifest-description-counts.followup.md` |

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

---

## Chat Tool Impact (REQUIRED when this contract adds or changes a REST endpoint or SignalR event)

2. **No.** This contract adds no endpoint and no event.

---

## Non-Goals

- Manifest descriptions and their drift test (follow-up item, Q6). This is the one brief criterion this contract does not deliver (scope note in the Handoff).
- The two agent passages in the first Adjacent Areas row.
- README counts outside the folder tree and the provider table (for example lines 446 and 1166).
- Generating the registry digest automatically.
- Memory behaviour beyond the keep rule.
- Seeding `MECHANISMS/general.md` (Q7).
- Instructions to write or update INTEGRATION.md (`fullstack-code-reviewer.md:301`, `contract-critic.md:153`); block 6 changes only reads.

---

## Confidence

Confidence: Medium. High on what is broken (every row re-read). Medium on the pager test's isolation: `SELF_ROOT` is the hook's own folder, so the test must run a copy of the hook from a temporary `.claude/hooks/`.

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** nine implementation blocks, one per file group, plus one review.
  - Why: each review judges one thing.
- **Option B (rejected):** three blocks, one per stub.
  - Why rejected: one review would then mix six unrelated files.
- **Option C (rejected):** fix the manifests inside this contract, or right after it by hand.
  - Why rejected: inside, it is the Layout defect `sub-task-raises-version`. By hand after the landing, it is a second, unreviewed route into the default branch with a second version raise (critic BLOCKER).
- **Option D (rejected):** move all of `/flow` Step 2.7 to the reference.
  - Why rejected: the guard and the `<= 1` stop must run on every run, and three pinned phrases would leave SKILL.md.
- **Option E (rejected, block 5):** keep one `config-absent` log record per turn or per day.
  - Why rejected: per turn is the defect itself, and per day needs a seen-state file that the absent config cannot name. The 44-day incident was a file that existed at a place the resolver did not search, and the four-rank found-rows pin that class directly.

---

## Uncertain Assumptions

- `VERIFIED via file reads 2026-11-11`: rows V1-V19 at the lines cited.
- `VERIFIED via test_parent_branch_rule_text.py:231-244, test_compose_subissue_title.py:571, test_skill_script_lookup.py:101`: these are the Step 2.7 phrases, the `no:parent-issue` check and the `rglob` lookup scan that block 2 must keep green.
- `VERIFIED via test_plugin_doctor.py:308-332`: the guard skips unless `AGENTIC_PLUGIN_ROOT` names a checkout holding `plugin.json` and `.claude/templates`.
- `VERIFIED via _project_paths.py:62-82,242-252; _error_log.py:57,108`: config is the first `claude_roots()` rank holding the file. The log folder comes from the project folder, and the logger writes only when that folder exists.
- `ASSUMED`: `test_pr_merged.py` runs 761 tests. It no longer matters after Q3.
- `ASSUMED`: the cross-area script would print nothing (not run; the area map is empty).

---

## Failure Modes & Mitigations

- **FM:** the `/flow` move drops a pinned phrase or a lookup block.
  - **Mitigation:** I-3, plus block 2's Run list (journal 2026-10-15).
- **FM:** the reference is unreadable under an install mode.
  - **Mitigation:** the read-in-full rule halts. The same-skill form is already in production use by `/task` (`references/other-trackers.md`) and `/pr-merged`. No separate trial was run for `/flow`, so the review reads it once through a plugin-cache install if one is present, or records that as not checked.
- **FM:** a count pin goes red when `master` moves before the landing.
  - **Mitigation:** Q1 keeps only slow lines. `test_repo_consistency.py` runs in CI's `tests` job (`.github/workflows/version-bump.yml`), and the landing re-runs it.
- **FM:** the manifests stay wrong after this contract lands.
  - **Mitigation:** stated in Non-Goals and in the scope note. The follow-up stub carries the criterion, and block 10 checks that the stub exists.
- **FM:** the pager fix hides a real failure.
  - **Mitigation:** I-4 rows for a malformed file and a folder in the file's place.
- **FM:** the 44-day incident returns: a config exists, the resolver misses it, and now nothing is logged.
  - **Mitigation:** block 5 plants a malformed decoy at each of the four ranks (project folder, `SELF_ROOT`, current folder, home), one rank at a time, and requires `config-load-failed` for each. That proves every rank is searched. The resolver has no fifth place. Residual risk: a file outside all four ranks is silent. That is the documented meaning of absent.
- **FM:** an empty retrieval on a re-run deletes earlier decisions (critic WARN 7).
  - **Mitigation:** the keep rule covers `enabled`-empty as well as `unconfigured`, with a round-trip row. I-6 is untouched.
- **FM:** the finish-install skill asks twice, or never asks.
  - **Mitigation:** I-5's four runs, each pinned.
- **FM:** making the template generic weakens critic item 7.
  - **Mitigation:** I-7. The pin's control plants a made-up name (journal 2026-10-05).
- **FM:** the unshipped-name guard keeps skipping, so a leak ships.
  - **Mitigation:** blocks 3, 4 and 7 run it with `AGENTIC_PLUGIN_ROOT` set to the worktree root and paste a run with zero skips.

---

## Open Questions for User

- [x] Q1 README tree counts? → Keep and pin counts on the rarely-changing lines; drop the numbers from `hooks/tests/`, `scripts/` and `scripts/tests/` (2026-11-11).
- [x] Q2 Counting rule for hook data files? → 5: the `.json` files in `.claude/hooks/` except `hooks.json` (2026-11-11).
- [x] Q3 Test count in skill text? → No count. Name the suite and its run command; a pin stops a number returning (2026-11-11).
- [x] Q4 Enabled empty retrieval? → A text fix: record the empty outcome and print one line with the suffix. Reconciled with Q5 by the keep rule so that nothing is dropped (2026-11-11).
- [x] Q5 Keep `Retrieved:` and `Reported:` under `unconfigured`? → Yes, with a round-trip test (2026-11-11).
- [x] Q6 Manifest descriptions? → Dropped from this contract. They become their own work item after the landing (follow-up stub) (2026-11-11).
- [x] Q7 Seed `MECHANISMS/general.md`? → No (2026-11-11).

---

## Critique

**Critic:** contract-critic
**Date:** 2026-11-11
**Verdict:** blockers-found

Tree check: V1-V14 and V16-V18 were re-read and match the tree at the cited lines, apart from the partial gaps named below. Skills 34, agents 15, hook test suites 28, hook `.json` files 6. The layout rule holds: `pr_merged.py:1632-1638` raises `sub-task-raises-version` for any mergeable block that lists a `check_version_bump.MANIFESTS` file (`check_version_bump.py:25-26`), `versionRaise` is `true` (`work-item-conventions.json:90`), and no block's Files to touch lists one of the four manifests. Dependency order: blocks 3 and 8 are the only blocks that edit the same file (`test_plugin_text_scans.py`), so the 3 -> 8 edge is required and correct. Every other shared test file is only run, never edited, by more than one block.

### Findings

- **[BLOCKER] Q6's post-landing pull request opens a second delivery route and a second version raise for this contract**
  - **What is wrong:** the scope note, I-2, Extension Points ("The real-manifest assertion is added by the post-landing pull request") and Failure Modes all build in an unreviewed pull request straight to `master`. It carries this contract's work: the manifest text and a new real assertion in `test_repo_consistency.py`, which the concept gate allows only because block 9 lists that file. It also takes its own patch raise. In effect it is an undeclared eleventh mergeable block that merges into the default branch, outside block 10's review.
  - **Prior artifact ignored:** `VOCABULARY.md:74` Parent Branch Delivery Rule ("one landing pull request moves it to the default branch … raised once, during the landing"); `VOCABULARY.md:76` Landing version raise; `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery, not only the one the author had in mind".
  - **Where in this contract:** `## Implementation Handoff → Post-landing manifest descriptions (scope note)`: "After the landing, one pull request to `master` makes the change Q6 describes"; `## Open Questions for User` Q6: "takes a patch raise. The concept gate allows it".
  - → Addressed by: Q6 answered "drop". The manifest fix and its real assertion leave this contract for their own work item (`2026-11-11-manifest-description-counts.followup.md`). The post-landing pull request and its second raise are deleted, and I-2 now says only the landing reaches the default branch.
- **[WARN] The contract drops a brief acceptance criterion that block 10 is told to check**
  - **What is wrong:** the brief requires "Manifest descriptions and README state the real skill and agent counts, and a test in `test_repo_consistency.py` fails when they drift". Its Out of scope list says "The count text fix is in scope". The contract moves both out (I-2, Non-Goals) and does not amend the brief, yet block 10 must "Check each acceptance criterion of the brief".
  - **Prior artifact ignored:** `.claude/work-items/2026-11-11-165-audit-followups.md:35,46`; `JOURNAL.md` 2026-10-22 "An accepted critic WARN or answered Open Question must amend the contract body before approval".
  - **Where in this contract:** `## Non-Goals` — "Any edit to the four manifests inside this contract's sub-tasks"; block 10 CONSTRAINTS — "Check each acceptance criterion of the brief".
  - → Addressed by: the scope note "Brief criterion 5, manifest half" names the follow-up item. Block 10 judges criterion 5 as the README half here plus that stub's existence.
- **[WARN] An existing unshipped-name guard over the template and the profile is not cited, not run, and skips from a worktree**
  - **What is wrong:** `TestTheRealPluginTree.test_the_files_a_project_copies_carry_no_unshipped_name` already scans every `plugin_doctor.REQUIREMENTS` source, which includes `.claude/templates/concept-contract.md` and `.claude/project-profile.md` (`plugin_doctor.py:64-66,87-89`). It checks them against `NOT_SHIPPED`, which includes `llm-training-engineer` and `ingestion-data-architect`. Blocks 3, 4 and 7 omit `test_plugin_doctor.py` from their Run lists. The test also calls `skipTest` when the plugin checkout is not found beside the repository, which is the case from a flat worktree (parent glob at `test_plugin_doctor.py:321-323`). So it is silently skipped wherever the blocks run.
  - **Prior artifact ignored:** `.claude/scripts/tests/test_plugin_doctor.py:295-347`; `JOURNAL.md` 2026-10-05 "Never hide a forbidden name by hashing it when the test needs a positive control" (a genericity scan must prove it runs).
  - **Where in this contract:** `## Reused Mechanisms` (no mention); block 3 CONSTRAINTS — "Run: test_plugin_text_scans.py, test_parent_branch_rule_text.py, test_memory_off_parity.py".
  - → Addressed by: V19, Reused Mechanisms, and the Run lists of blocks 3, 4 and 7, which run the test with `AGENTIC_PLUGIN_ROOT` set to the worktree root and paste a run with zero skips.
- **[WARN] Block 3's pin is narrower than the rule it pins**
  - **What is wrong:** the rule is "names no consuming project's file, tool, adapter, phase, date or agent". The pin checks only source extensions (.cs .ts .py .java), a `Phase <letter><digit>` label and a hex adapter id. Several names in the section today would pass it: `feedback_service_layer_cannot_leak_exception_message_to_chat.md`, `llm-contract-reviewer`, `llm-training-engineer`, `/retrain-llm`, `create_strategy`, `POST /api/strategy-runs/...` and `2026-04-23-a2-chat-tools-start-run-pair` (template lines 218-234).
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 "A rule titled 'every' must list every line it covers".
  - **Where in this contract:** block 3 TASK — "Pin … the section names no file with a source extension (.cs .ts .py .java), no "Phase <letter><digit>" label and no hex adapter id".
  - → Addressed by: block 3's pin now has seven rules, one per class the critic listed, each with its own made-up control.
- **[WARN] Block 6's list of "every" INTEGRATION.md instruction is incomplete, and the same absent-file reads remain in other shipped agents**
  - **What is wrong:** `agents/data-architect.md:163` also relies on "INTEGRATION.md's frontend section", but the list does not name it. Line 111 is a CodeGraph allowlist statement, not a read instruction. The unconditional reads of the digest and INTEGRATION.md also appear in `contract-critic.md` (3), `registry-scout.md` (2), `fullstack-code-reviewer.md`, `api-contract-reviewer.md` and `skills/design-first/SKILL.md`. Neither Non-Goals nor Adjacent Areas names them.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 "A rule titled 'every' must list every line it covers"; `JOURNAL.md` 2026-11-02 "A sweep that deletes every proven file in a folder must route EVERY local reader of that folder…".
  - **Where in this contract:** block 6 TASK — "Make every INTEGRATION.md instruction (lines 57, 111, 137) read "where the project keeps one"".
  - → Addressed by: block 6 now covers every read line in V8 across six files (line 163 added, line 111 dropped as not a read). Write and update instructions are a named Non-Goal.
- **[WARN] The pager test's isolation assumption names two of the resolver's four roots**
  - **What is wrong:** `claude_roots()` (`_project_paths.py:62-82`) searches four roots in order: `CLAUDE_PROJECT_DIR`, then `SELF_ROOT` (the hook's own `.claude`, `_project_paths.py:44`), then the current working directory's `.claude`, then home. The assumption isolates only the project dir and home, so a `memory-blocks.json` placed later in the repository's own `.claude`, or in the current folder, hides the absent row. No row plants a decoy in each other root.
  - **Prior artifact ignored:** `MECHANISMS.md:46` Two-layer Claude path resolution; `JOURNAL.md` 2026-10-05 "A documented "missing file means the default" must read one named location only" (test the missing case with a decoy in each other place).
  - **Where in this contract:** `## Uncertain Assumptions` — "the pager test can isolate the config path with `CLAUDE_PROJECT_DIR` plus `HOME` and `USERPROFILE`".
  - → Addressed by: block 5 runs a copy of the hook from a temporary `.claude/hooks/`, so `SELF_ROOT` is temporary. It isolates all four ranks for the absent row and plants a decoy at each rank in turn.
- **[WARN] Failure Modes omit the incident class the pager's absent-file log line once exposed**
  - **What is wrong:** the code records that the same quiet `config-load-failed` line was the only trace of a resolver that could not find a file that did exist: 398 times over 44 days. Block 5 makes absence leave no trace at all. The "pager fix hides a real failure" mitigation covers only a malformed file and a folder in the file's place, not a file at a root the resolver does not search.
  - **Prior artifact ignored:** `.claude/hooks/_project_paths.py:245-250` and `.claude/hooks/_memory_common.py:86-91` (incident record); `MECHANISMS.md:46` (missing data file fails open "at a correctly-resolved root").
  - **Where in this contract:** `## Failure Modes & Mitigations` — "I-4 has a malformed-file row and a folder-in-place row, both of which must log."
  - → Addressed by: a new Failure Mode, and Option E. Absence keeps no trace. The four-rank found-rows prove the resolver searches every rank, and the residual risk is stated.
- **[WARN] Q4's recommended `record` call on an empty retrieval newly drops earlier decisions, with no failure mode**
  - **What is wrong:** the `enabled` branch of `cmd_record` (`memory_boundary.py:774-786`) rebuilds the section from the new outcome and keeps only `Captured:` and `Not sent:` lines. So an empty retrieval on a re-run of `/design-first` deletes the brief's earlier `Retrieved:` and `Reported:` lines. That is the same loss Q5 gives as its reason for changing the `unconfigured` branch.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 "A revision that adds a path adds its failure modes".
  - **Where in this contract:** `## Open Questions for User` Q4 — "the session calls `record` with the empty outcome … This is a text change only".
  - → Addressed by: the keep rule (Data Shapes) applies to `enabled`-empty and to `unconfigured`. A round-trip row and a Failure Mode cover it.
- **[WARN] "Asked at most once per run" does not cover the run in which Stage 1a is skipped or answered no**
  - **What is wrong:** Stage 1a runs only when no profile exists (`auto-improve-finish-install/SKILL.md:99-100`). The sentence "The history-record check does not ask again" predicts the later step's behaviour but lists neither the skipped-1a case, where that check holds the only ask, nor the "no" case.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-06 "An exception sentence that names the outcome of a later call must list every outcome that call can have"; `JOURNAL.md` 2026-11-02 "Describe a fixer a skill runs by everything it writes, and keep the skill's confirm-first promise".
  - **Where in this contract:** I-5 — "the user is asked at most once per run"; block 7 TASK — "The history-record check does not ask again (I-5)".
  - → Addressed by: I-5 lists four runs (skipped, yes, no, plugin not found), each pinned in block 7.
- **[NIT] Block 4's new agent-name pin re-implements helpers that already exist** — `plugin_agent_names()` (`test_plugin_text_scans.py:110`) and `NOT_SHIPPED` (`test_plugin_doctor.py:305`) already list the shipped and the unshipped agents.
- **[NIT] Block 1 keeps a paragraph that relies on the command it deletes** — the VS Code window paragraph (`skills/task/SKILL.md:498`) says "`git worktree add` already placed a correct copy".
- **[NIT] The FM's trial evidence covers a different read form** — `MECHANISMS.md:92` records a trial of a sibling `../<sibling>/references/` read, not the same-skill `references/` read that block 2 uses.
- **[NIT] Block 9's edge on block 2 is overstated** — no README tree line counts `skills/flow/references/` (`README.md:981` counts skills, `:992` counts `.claude/references/`). Only block 5's new hook suite is counted, and only if Q1 keeps the `hooks/tests/` number.
- **[NIT] Block 10 writes a file its Files to touch does not list** — the `.gate.json` artefact is named in CONSTRAINTS only.
- **[NIT] The three stubs to be superseded are not named by path** — `## Extension Points` says "the three issue-165 stubs". The paths are in the brief (line 25). The brief's `contract: UNKNOWN` (line 15) reads as unset to the Brief linkage matcher (`MECHANISMS.md:93`).

NIT dispositions: block 4 reuses both helpers. Block 1 rewords line 498. The FM now cites production use instead of the trial. Block 9 depends on none: Q1 drops the `hooks/tests/` number, so nothing it counts is added by another block. The `.gate.json` stays off Files to touch, as the template's Gate Output rule requires. The stub paths and the brief's `contract:` write are in Extension Points.

### Applicable journal entries

- **2026-10-30 — A delivery rule must name every route into delivery** — violated, see BLOCKER above.
- **2026-11-02 — A rule titled 'every' must list every line it covers** — heeded by I-5 and block 7's I1 pin; violated in part by blocks 3 and 6, see WARNs above.
- **2026-10-05 — A documented "missing file means the default" must read one named location only** — not addressed, see WARN (pager isolation).
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded for Stage 1a "no" and the reference read; not addressed for Q4's new `record` call, see WARN.
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have** — not addressed, see WARN (I-5).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — not yet triggered; it binds the Q1-Q7 answers. The brief mismatch WARN is the first case.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by block 2's Run list.
- **2026-10-28 — State the real trigger of a hook, not the printing condition** — heeded by V7 (`hooks.json` Stop row, no matcher).
- **2026-11-02 — Describe a fixer a skill runs by everything it writes, and keep the skill's confirm-first promise** — heeded by block 7 W1.
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them** — heeded by I-6.
- **2026-11-02 — A "fails the build" claim must name the workflow that runs the check** — heeded: `test_repo_consistency.py` runs in the `tests` job of `.github/workflows/version-bump.yml:24-33`.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded by block 3's made-up control name.
- **2026-11-06 — A sub-task that flips the state an earlier sub-task's test pins must re-run that suite** — heeded by block 10's Run list.

---

## Lessons referenced

- **2026-10-30 — A delivery rule must name every route into delivery** — heeded by I-2 and Q6 (one landing, no second route).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval** — heeded by Revision 2 (Data Shapes keep rule, I-4, I-5, blocks 3-7 and 9).
- **2026-10-05 — A documented "missing file means the default" must read one named location only** — heeded by block 5's four-rank decoys.
- **2026-11-06 — An exception sentence that names the outcome of a later call must list every outcome that call can have** — heeded by I-5's four runs.
- **2026-11-02 — A rule titled 'every' must list every line it covers** — heeded by I-5, the pins of blocks 3 and 7, and block 6's line list.
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded by the Q4/Q5 Failure Mode and the incident Failure Mode.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by block 2's Run list.
- **2026-10-28 — State the real trigger of a hook, not the printing condition** — heeded by V7.
- **2026-11-02 — Describe a fixer a skill runs by everything it writes, and keep the skill's confirm-first promise** — heeded by block 7 W1.
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them** — heeded by I-6.
- **2026-11-02 — A "fails the build" claim must name the workflow that runs the check** — heeded by the count Failure Mode.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded by the made-up controls in block 3 and the guard run with zero skips.
- **2026-11-06 — A sub-task that flips the state an earlier sub-task's test pins must re-run that suite** — heeded by block 10's Run list.
- **2026-11-03 — A stop list checked against a moving default branch needs a rule for changes outside the edited lines** — heeded by block 9's pre-check.
- Orthogonal to north-stars: none active (`.claude/north-stars/` is absent).

---

## Implementation Handoff

Ten blocks: nine implementation blocks and one review. Block 8 depends on 3, block 10 on 1-9, the rest on none. The parent branch is `feature/165-audit-followups`. No block lists a version file. Each pull request pastes, for every new pin, the failing run from before the fix and the passing run after it. Run every suite with `py -3 -B <path>`. `test_plugin_doctor.py` runs with the root set; in PowerShell: `$env:AGENTIC_PLUGIN_ROOT = (Get-Location).Path; py -3 -B .claude/scripts/tests/test_plugin_doctor.py`.

### 1. Task skill worktree text (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `skills/task/SKILL.md`
- `.claude/scripts/tests/test_flat_worktree.py`

**Pre-written TASK block:**
```
TASK: Delete the second Step 1.5 (lines 120-134). In 5c, delete the "Create it" gh / git worktree add blocks and
  the "Enter it only if" paragraph. Rule 2 becomes "created by flat_worktree.py (Step 1.5), never by EnterWorktree's
  name: form". Line 498 becomes "the worktree checkout already placed a correct copy". Keep the naming, rules 1 and
  3-5, the base proof (on the plan's path), the gitignore check, the VS Code window and the lifecycle. Line 444
  points a new item at Step 1.5's flat_worktree.py command. Delete the line-559 paragraph. Pin in
  test_flat_worktree.py, with planted controls: exactly one Step 1.5 heading, and no "git worktree add" command
  line in 5c.
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V1, V2)
FILES: the two above
CONSTRAINTS:
  - Run: test_flat_worktree.py, test_parent_branch_rule_text.py, test_ship_skill_sync.py, test_memory_off_parity.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

### 2. Flow Step 2.7 reference move (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `skills/flow/SKILL.md`
- `skills/flow/references/open-sub-tasks.md`
- `.claude/scripts/tests/test_parent_branch_rule_text.py`
- `.claude/scripts/tests/test_compose_subissue_title.py`

**Pre-written TASK block:**
```
TASK: Move Step 2.7 point 3 onward verbatim into skills/flow/references/open-sub-tasks.md: the gh check, the
  per-sub-task decision with both verify_parent_link.py lookup blocks, the /task call, the partial-failure rule,
  point 4, "Finding sub-issues" and "No new status:". Replace it with the Extension Points line. Keep the guard, the
  Parent Branch Delivery Rule paragraph, the PRM lookup and status call, and points 1 and 2. Retarget the
  no:parent-issue check to SKILL.md plus the reference. Add FlowTextTests, with planted controls: Step 2.7 names the
  reference and the read-in-full and stop rule; the reference holds --record-subtask, verify_parent_link.py and
  no:parent-issue.
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V3, I-3)
FILES: the four above
CONSTRAINTS:
  - Run: test_parent_branch_rule_text.py, test_compose_subissue_title.py, test_skill_script_lookup.py (slow),
    test_memory_off_parity.py, test_pr_merged.py
  - report SKILL.md line counts before and after
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

### 3. Template chat-tool genericity (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/templates/concept-contract.md`
- `.claude/scripts/tests/test_plugin_text_scans.py`

**Pre-written TASK block:**
```
TASK: Rewrite "## Chat Tool Impact" so it names no consuming project's file, tool, endpoint, adapter, phase,
  contract, memory note or agent. Cite "the project's chat-tool definition, executor and system-prompt files (the
  rest/docs lists in .claude/hooks/sentinel-paths.json, where the project keeps one)" and "the project's
  model-training agent or skill, if it has one". Replace the history paragraph with one generic sentence. Keep I-7.
  Pin the section with seven rules, each with a made-up control (for example "FooTools.cs", "frob-reviewer",
  "/retrain-frob"):
  (1) no file name with a source extension (.cs .ts .py .java)
  (2) no "Phase <letter><digit>" label
  (3) no hex id of six or more characters
  (4) no backticked agent-shaped name outside plugin_agent_names()
  (5) no slash command that is not a skills/ folder
  (6) no "<HTTP verb> /api/" route
  (7) no dated contract slug and no "feedback_*.md" note
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V4, V19)
FILES: the two above
CONSTRAINTS:
  - Run: test_plugin_text_scans.py, test_plugin_doctor.py (AGENTIC_PLUGIN_ROOT set, zero skips),
    test_parent_branch_rule_text.py, test_memory_off_parity.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

### 4. Debug routing to shipped agents (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `skills/debug/SKILL.md`
- `.claude/scripts/tests/test_agent_skill_preloads.py`

**Pre-written TASK block:**
```
TASK: Route ingestion jobs to "`dotnet-backend-architect`, or the project's own ingestion agent if it declares one".
  Route the LLM pipeline and Python sidecar to `python-ai-developer`, "or the project's own model-training agent if it
  declares one". Pin beside test_debug_routes_container_bugs_to_cloud_engineer, reusing plugin_agent_names() and
  TestTheRealPluginTree.NOT_SHIPPED (import, never copy): every backticked agent-shaped name in "Choose the agent by
  area" is shipped. The control plants "`llm-training-engineer`".
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V5)
FILES: the two above
CONSTRAINTS:
  - Run: test_agent_skill_preloads.py, test_plugin_text_scans.py, test_plugin_doctor.py (root set, zero skips)
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

### 5. Memory pager absent config (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/hooks/memory-pager.py`
- `.claude/hooks/tests/test_memory_pager.py`

**Pre-written TASK block:**
```
TASK: When the resolved config path is not a file at any claude_roots() rank (FileNotFoundError), memory-pager.py
  writes no log record and exits 0. Every other failure keeps config-load-failed (I-4). Suite test_memory_pager.py
  copies the hook and its helpers into a temporary <tmp>/.claude/hooks/, so SELF_ROOT is temporary. It runs the hook
  by subprocess with CLAUDE_PROJECT_DIR, cwd, HOME and USERPROFILE all temporary, and an existing log folder.
  Rows:
  - absent at all four ranks: no config-load-failed, exit 0 (must fail on today's code; paste it)
  - a malformed decoy at each rank in turn (project, SELF_ROOT, cwd, home): config-load-failed each time
  - a folder in the file's place: logs
  - CLAUDE_MEMORY_PAGER=off: nothing
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V7, I-4, Option E)
FILES: the two above
CONSTRAINTS:
  - do not edit _memory_common.py or _project_paths.py
  - Run: test_memory_pager.py, test_memory_common.py, test_protected_names_warning.py, test_hook_data_files_project_first.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

### 6. Registry reads in agents and design-first (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `agents/data-architect.md`
- `agents/contract-critic.md`
- `agents/registry-scout.md`
- `agents/fullstack-code-reviewer.md`
- `agents/api-contract-reviewer.md`
- `skills/design-first/SKILL.md`

**Pre-written TASK block:**
```
TASK: At every read line listed in V8, the digest is read "when it exists (made by py -3
  .claude/scripts/generate_registry_digest.py); otherwise read the registries directly". Every INTEGRATION.md
  read becomes "where the project keeps one", and without it the agent works from the code it investigated.
  registry-scout reports the digest as absent and names the generator. design-first SKILL.md:96 passes
  registry_digest only when the file exists. Write and update instructions are unchanged.
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V8)
FILES: the six above
CONSTRAINTS:
  - leave the focus rule, memory rule 9, critic item 7 and the Parent Branch lines untouched
  - Run: test_plugin_text_scans.py, test_memory_off_parity.py, test_parent_branch_rule_text.py,
    test_repo_consistency.py, test_skill_script_lookup.py (slow)
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

### 7. Memory boundary review leftovers (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `skills/auto-improve-finish-install/SKILL.md`
- `skills/design-first/references/central-memory.md`
- `skills/pr-merged/references/contract-completion.md`
- `.claude/project-profile.md`
- `.claude/scripts/memory_boundary.py`
- `.claude/scripts/tests/test_memory_boundary.py`
- `.claude/scripts/tests/test_memory_off_parity.py`

**Pre-written TASK block:**
```
TASK: The changes:
  - W1: Stage 1a runs plugin_doctor.py --project ., shows the missing list as what --fix would create, asks once,
    and runs --fix only on yes. The four runs of I-5 apply.
  - I1: the line-18 example carries the suffix.
  - I2: 5a.1 names default-branch-unknown, and the one re-run uses --default-branch with a name read from
    "git symbolic-ref refs/remotes/origin/HEAD" or from the user, never a guessed one.
  - I3: word-bounded ask pattern, looking back only within the paragraph, extended to every --fix line in the file.
  - Q4: section 3 records the empty outcome and prints one line with the suffix.
  - Q5 and Q4: the keep rule in cmd_record (Data Shapes).
  - I6: the retrieve-tool and shape rows say `none` with a server set reports unconfigured.
  Pins with controls:
  - I1: every backticked "Memory: unavailable" example ends with the suffix
  - I2
  - I-5's four runs
  - W1: a planted bare Stage 1a --fix fails
  - the round trip: enabled with items, then enabled empty (kept), then unconfigured (kept), then enabled with new
    items (replaced)
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V11-V17, I-5, I-6)
FILES: the seven above
CONSTRAINTS:
  - I-6; contract-completion.md step labels unchanged (records_step_labels)
  - Run: test_memory_off_parity.py, test_memory_boundary.py, test_parent_branch_rule_text.py,
    test_plugin_text_scans.py, test_plugin_doctor.py (root set, zero skips)
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

### 8. Skill test-count text (`python-ai-developer`)

**Depends on:** 3 — both edit `test_plugin_text_scans.py`

**Files to touch:**
- `skills/pr-merged/SKILL.md`
- `skills/advance/SKILL.md`
- `.claude/scripts/tests/test_plugin_text_scans.py`

**Pre-written TASK block:**
```
TASK: Replace "760 cases" and "Ran 760 tests" with the suite path, its run command and "its unittest summary line
  must end OK". Pin: neither file states a digit count of tests or cases for test_pr_merged.py. The control plants
  "Ran 760 tests".
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V10, Q3)
FILES: the three above
CONSTRAINTS:
  - Run: test_plugin_text_scans.py, test_parent_branch_rule_text.py, test_pr_merged.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

### 9. README counts and count pins (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `README.md`
- `.claude/scripts/tests/test_repo_consistency.py`

**Pre-written TASK block:**
```
TASK: Remove the numbers from the hooks/tests, scripts and scripts/tests tree lines. Correct the hooks line to
  "5 generic data files" and references to 4. Pin every remaining tree and provider-table count against its
  Count-claim oracle, with skill, agent and subagent measures. Helpers return violation lists, with broken-fixture
  controls; one control is a manifest-shaped description string. No assertion runs on the real manifests (I-2).
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V9, Q1, Q2)
FILES: the two above
CONSTRAINTS:
  - first run: git diff of README.md between the parent branch and origin/master. A hunk inside the tree or the
    provider table halts the block. Other hunks are fine when git merge-tree is clean (paste both).
  - each new real assertion fails on today's README (paste)
  - Run: test_repo_consistency.py, test_check_version_bump.py
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

### 10. Review (`fullstack-code-reviewer`)

**Depends on:** 1, 2, 3, 4, 5, 6, 7, 8, 9

**Files to touch:**
- `.claude/reviews/2026-11-11-audit-followups-165/t10-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 1-9 on the parent branch tip, and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md
FILES: .claude/reviews/2026-11-11-audit-followups-165/t10-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check each brief acceptance criterion. Criterion 5 is judged as the README half delivered here plus the
    existence of .claude/concepts/followups/2026-11-11-manifest-description-counts.followup.md, which names both the
    description fix and the drift test. Also check I-1..I-7, and that each new pin's control fails on its fixture.
  - Re-run on the tip: every suite named in blocks 1-9, test_skill_script_lookup.py, test_check_version_bump.py,
    and test_plugin_doctor.py with AGENTIC_PLUGIN_ROOT set (zero skips).
  - Confirm that no block touched a check_version_bump.MANIFESTS file.
  - The file does NOT exist yet: you create it; nobody pre-created a stub. Six sections in the template's order;
    name the commit range base..head; "## Evidence" lists commands with exit codes and is never empty.
  - The header ends with the verdict line, alone, exactly one of: "**Verdict:** pass",
    "**Verdict:** pass-with-findings", "**Verdict:** blocked".
  - Also write <artefact stem>.gate.json in the same diff: {"supersedes": [], "checklist": [{"item": "<Review
    checklist line, verbatim>", "outcome": "met | partly-met | not-met | not-applicable"}]} for every line.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

### Brief criterion 5, manifest half (scope note)

Not a sub-task. It names no agent and has no Files to touch. The owner moved the manifest descriptions and their drift test to their own work item, to start after this contract lands: `.claude/concepts/followups/2026-11-11-manifest-description-counts.followup.md`. This contract creates no pull request to the default branch other than the landing, and raises the version once, at the landing.

---

## Review checklist (filled in after implementation)

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both backend and frontend sides
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
- [ ] `Status` flipped to `implemented`
