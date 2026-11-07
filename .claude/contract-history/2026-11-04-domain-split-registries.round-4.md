# Round 4 history: amendment 4 critique (moved out of the contract on 2026-11-07, amendment 5)

### Amendment 4 critique

**Critic:** contract-critic
**Date:** 2026-11-06
**Verdict:** blockers-found
**Counts:** 2 BLOCKER / 8 WARN / 4 NIT, plus one positive-evidence note (heading count corrected 2026-11-06).
**Scope:** blocks 10 and 11, "Amendment 4 record", the amended body text (`stage_and_replace` `base`, Migration report `error`, the FALSIFIED plugin-root line), Q19, Q20. Blocks 1–9 were not re-critiqued.

#### Findings

- **[BLOCKER] N1's expected outcome cannot happen under I-7.**
  - **What is wrong:** a Correction line is appended under the entry and the original span stays, so `rule_r4` (line-based, `_registry_layout.py:685-703`, no Correction awareness) still prints R4 for `` `registry_migrations/__init__.py` `` at `MECHANISMS.md:112`. Block 11 then checks "R4 no longer reports the path", which is a guaranteed miss.
  - **Prior artifact ignored:** this contract's I-7 and R4 ("Reported, never rewritten (I-7)"); `skills/validate-registries/SKILL.md:69` ("The original dead reference stays in the entry, so the validator keeps listing it").
  - **Where in this contract:** `### 10` N1 — "Afterwards --check-structure no longer prints R4 for that path."; `### 11` — "N1 (Correction line present, made by registry_append; R4 no longer reports the path)".
  - → Addressed by: blocks 10 and 11 now claim only that a Correction line naming the right path is appended with `registry_append.py --correction-of`; R4 keeps listing the original span at `MECHANISMS.md:112` (I-7, R4 rule text, `skills/validate-registries/SKILL.md`); no hand edit.
- **[BLOCKER] The W5 skip line can turn the C1 pin red, and block 10 leaves that pin's file out of its list.**
  - **What is wrong:** `ThisRepositoryTests` (`test_registry_layout.py:742-749`, rewritten by PR #288 to the same "R4 or `digest:` lines only" shape the t9 review prescribes) runs `--check-structure` on this repository, which holds `.claude-plugin/plugin.json`. The bullet says the lint "prints once" the skip line, but does not say whether that happens whenever the manifest is present or only when a candidate was actually dropped. In the first reading, the pinned suite fails. Block 10 requires that suite to exit 0 and says "test_registry_layout.py is not on its list". Older-test search (5) looks only for tests that count `universal-candidate` lines, so it misses this pin. This is the t9 C1 defect class again, inside the amendment that records the lesson about it (Q20).
  - **Prior artifact ignored:** `.claude/reviews/2026-11-04-domain-split-registries/t9-review-fullstack-code-reviewer.md` C1 and Disposition "A second proposed lesson (C1)".
  - **Where in this contract:** `### 10` W5 — "drops R3 universal-candidate advisories and prints once ..."; CONSTRAINTS — "C1 is NOT part of this block, and test_registry_layout.py is not on its list."
  - → Addressed by: the skip line prints only when at least one advisory was dropped, with the fixed prefix `advisory: R3 universal-candidate skipped`; `test_registry_layout.py` joins block 10's Files to touch, its this-repository test allows that prefix (PR #288's no-layout-advisory assertion kept), block 10 reruns the suite, and older-test search item (6) names the file.
- **[WARN] The W1 signature pin reads as a pin on live repository state.**
  - **What is wrong:** "the signature set of this repository's journal (the 41 existing entries) is identical before and after" breaks as soon as block 10's own Q20 bullet appends two journal entries, and again on every later append, unless the "frozen fixture" is a frozen copy of the text rather than of the live file. The contract does not say which.
  - **Prior artifact ignored:** t9 review C1 (a test that pins state a later write changes).
  - **Where in this contract:** `### 10` W1 — "Compute the expected set in the test from today's regex as a frozen fixture".
  - → Addressed by: block 10 W1 pins the 41 signatures against a frozen fixture file, `.claude/hooks/tests/fixtures/journal-signatures-2026-11-06.md` (a byte copy of `JOURNAL.md` taken before block 10's appends), never the live `JOURNAL.md`.
- **[WARN] I-14 ("nothing fires retroactively") is proven only on this repository's 41 headings.**
  - **What is wrong:** the two parsers do not accept the same headings. The new one matches `_HEADING` `[ \t]+` and `_J_HEADER` `(\S.*?)` (`_registry_layout.py:59,62`); the old `_ENTRY_HEADER` uses multiline `\s+` and `(.+?)` (`accuracy_update.py:404`). Any heading that only the new parser accepts becomes a new signature in an already-seeded client file, and it fires on the first edit after upgrade. Neither a test nor a Failure Mode covers new ⊆ old on client journals.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case".
  - **Where in this contract:** `### 10` W1; `## Failure Modes & Mitigations` (no amendment-4 entry).
  - → Addressed by: I-14 now records the seeding reader in `seeded_files` and re-seeds a file seeded under the old reader once, firing nothing; a Failure Mode entry and a block 10 test row on a client-shaped journal whose headings the two patterns read differently.
- **[WARN] W1 widens accuracy_update's import chain without amending "Import chain".**
  - **What is wrong:** `accuracy_update` is also imported, fail-soft, by `critic-verdict-tracker.py:68` and `contract-status-watcher.py:68`. A hard import of `_registry_layout` would silently stop critic and status accuracy tracking on a copied-script client that lacks that module. The "Import chain" bullet still names only the journal tracker's degradation.
  - **Prior artifact ignored:** this contract's "Import chain (kept minimal)" bullet (amendment 3, approved).
  - **Where in this contract:** `### 10` W1 — "builds its entries from _registry_layout.parse_text".
  - → Addressed by: "Import chain" amended: `accuracy_update` imports `_registry_layout` lazily inside `parse_journal_entries`, names `critic-verdict-tracker.py` and `contract-status-watcher.py` and their quiet fail-soft import, and block 10 adds a test that both hooks still import `accuracy_update` with `_registry_layout` hidden.
- **[WARN] The Migration report `error` case has no mode and no refusal code.**
  - **What is wrong:** the VO allows modes `dry-run`, `apply` and `refused`, and the refusal code is "empty unless `refused`". The closed refusal set has no build-error code, so the `mode` and `refusal code` values of a report written with `error` are undeclared.
  - **Prior artifact ignored:** this contract's Migration report VO row and the `Preview / apply migration` Rejections column.
  - **Where in this contract:** `### Value Objects` Migration report — "error (amendment 4, N2)"; `### 10` N2.
  - → Addressed by: the Migration report VO sets mode `refused` and refusal code `plan-build-failed` for the error case, and `plan-build-failed` (exit 2) joins the closed Rejections set of Preview / apply migration.
- **[WARN] W3's per-entry containment does not say how lines are normalised or what happens with two output entries for one key.**
  - **What is wrong:** the I-12 text check folds line endings, the BOM and trailing spaces, but the new per-entry multiset check does not say it does the same, so a CRLF client could read as `content-loss-detected`. It also does not say what happens when step 4 appends a differing heading line, which yields two output entries with one key.
  - **Prior artifact ignored:** this contract's I-12 (*Text* normalisation clause).
  - **Where in this contract:** `### 10` W3 — "verify_plan parses each output entry and requires that its line multiset contains that set".
  - → Addressed by: I-12 "Per entry" clause and block 10 W3 apply I-12's normalisation (line endings, BOM, trailing spaces, blank lines); step 4 treats the heading line as a field, and two output entries with one key refuse `conflicting-entry`; CRLF and differing-date test rows.
- **[WARN] W4 points the old fence-toggle scanner at `general.md`, where migration leftovers live.**
  - **What is wrong:** `extract_entries` toggles on any line that starts with three backticks (`validate_registries.py:158-165`). Leftover blocks use "a fence longer than any backtick run inside", so a leftover that contains a three-backtick run flips the toggle. The default report then reports paths inside the leftover and skips real entries after it. That contradicts "Inert: never parsed, never a finding", and no leftover fixture is listed.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-01 "A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for"; this contract's Migration leftover block VO.
  - **Where in this contract:** `### 10` W4 — "The regex, the flags and the exit rule do not change."
  - → Addressed by: the default mode ignores each file from the `## Migration 0001 leftovers (not parsed as entries)` heading on, so leftovers never produce findings (R4 rule text, block 10 W4); a test with a leftover holding a three-backtick run and a dead path.
- **[WARN] Conditional text survives into an approved TASK block.**
  - **What is wrong:** "Q20 (when answered yes)" and "If Q19 is answered otherwise, this bullet was rewritten before approval; follow the approved text" stay in the TASK block. Files to touch lists `.claude/registries/JOURNAL.md` with no condition, while the Amendment 4 record says "(and `JOURNAL.md` under Q20)".
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22 "An accepted critic WARN or answered Open Question must amend the contract body before approval".
  - **Where in this contract:** `### 10` CONSTRAINTS (W5 and Q20 bullets); `## Amendment 4 record` Delivery bullet.
  - → Addressed by: Q19 and Q20 are answered; block 10's TASK block has no conditional wording, `JOURNAL.md` stays in its Files to touch unconditionally, and the Amendment 4 record's Delivery bullet drops "under Q20".
- **[WARN] PR #288 is a route into the parent branch outside the plan, and the gate on it is advisory.**
  - **What is wrong:** preconditions are "information for the operator, never a gate" (`pr_merged.py:1175`). t8 is already completed, so t10 is released as soon as the contract is re-approved, and it can be dispatched before #288 merges. "Cut this branch after that merge" then rests on operator discipline. The amendment also does not name #288's head kind: a `task/*` head runs in parent mode, and any other head is not checked (`check_version_bump.py:10`).
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-30 "A delivery rule must name every route into delivery, not only the one the author had in mind".
  - **Where in this contract:** `### 10` — "**Preconditions:** pull-request lneninger/claude-agentic-auto-improve#288"; `## Amendment 4 record` C1 bullet.
  - → Addressed by: the Amendment 4 record names #288's head `fix/235-pin-current-layout-in-layout-test` (not `task/*`, so `check_version_bump.py` does not check it in parent mode, and t11 checks it changes no version file) and states that Preconditions are information only, not a gate (`pr_merged.py` ~1175); block 10's TASK opens with a Run-first line to confirm #288 is merged before starting.
- **[NIT] W5 calls a private helper and its tests sit in the wrong file.** It calls `_plugin_root._manifest_names_plugin`, a private name; `## Extension Points` lists only `separate_plugin_root`. Its tests live in `test_validate_registries_default.py`, although they test `--check-structure`.
  - → Disposition: the W5 tests move to `test_registry_layout.py` (now on block 10's list). The private name stays (one definition in the same plugin, already imported back by finish-install) and is recorded under Extension Points as consumed.
- **[NIT] W4 leaves the `--json` shape undefined.** The default `--json` shape (`validate_registries.py:313-317`, one `mechanisms` dict and one `vocabulary` dict) is not defined for per-file blocks.
  - → Disposition: block 10 W4 keeps the `mechanisms` and `vocabulary` keys with today's shape, aggregated over all files, and adds one key `files` (one block per file read, in `registry_files` order). Additive only.
- **[NIT] Block 11's Files to touch omits the Gate Output its TASK requires.** It lists only the `.md`, not `t11-review-fullstack-code-reviewer.gate.json` (same as block 9; `.json` is gate-exempt).
  - → Disposition: noted, not changed. A review gate's Files to touch names exactly one path (the artefact); the `.gate.json` is gate-exempt and the TASK block already requires it.
- **[NIT] `## Confidence` was not revisited for amendment 4.** It still cites only the amendment-3 re-reads.
  - → Disposition: `## Confidence` now cites the amendment-4 re-reads and the one medium point (re-seed timing).
- **[NIT] Verified as correct (positive evidence).**
  - (1) *Depends on 8* is right. `compute_released` (`pr_merged.py:623-625`) treats a dependency whose `review_verdict` is not pass as unmet forever, and t9's existing record means it is skipped rather than re-released.
  - (2) The Preconditions line parses: it is column-0 (`:1180`), the `pull-request` head is recognised, and `_PR_SHORT_REF` matches (`:1183`).
  - (3) Supersession works. `read_review_set` matches the basename (`:3755-3758`), the gate name `t11-review-fullstack-code-reviewer.gate.json` follows the `name[:-3] + ".gate.json"` rule (`:3734`), and `t9-review-fullstack-code-reviewer.md` exists in the folder. `effective_blocked_reports` (`:4084-4086`) then drops t9, whatever t11's own verdict is.
  - (5) Neither block lists a version file, which matches the repository `CLAUDE.md` Parent Branch Delivery Rule.
  - → Disposition: positive evidence; no change. The new fixture file in block 10 is not a version file, so (5) still holds.

#### Applicable journal entries (amendment 4)

- **2026-10-30 — One shared reader must own the filtering** — heeded by block 10 W1.
- **2026-10-04 — A root locator can return the consumer itself under vendoring** — heeded by Q19 (a): only an advisory is dropped.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — partly heeded (fence, path-length and misattached-line fixtures). Not addressed for client signature parity; see WARN.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body** — heeded in intent by Q19 ("Either way the block is edited before re-approval"). Conditional text is left behind; see WARN.
- **2026-11-01 — A shared reader reused by a stricter consumer…** — not addressed for W4 leftovers; see WARN.
- **2026-10-30 — A delivery rule must name every route into delivery** — partly heeded (Amendment 4 Delivery bullet). Not addressed for PR #288; see WARN.

#### What the critic did not check

- No shell, so `pr_merged.py --contract 2026-11-04-domain-split-registries --status --json` (item 14 `layout_defects`) was not run. Item 14 was judged from the text: the header and the Work Item Brief are present, and neither block lists a version file.
- Whether PR #288 exists, its head branch and its diff (no `gh`).

---
