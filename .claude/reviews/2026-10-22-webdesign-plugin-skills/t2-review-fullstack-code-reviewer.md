# Review: Web-design plugin skills (t1-design-skills), fullstack-code-reviewer

**Gate agent:** fullstack-code-reviewer
**Sub-task reviewed:** t1-design-skills (gate t2)
**Contract:** `.claude/concepts/2026-10-22-webdesign-plugin-skills.md` (approved)
**Reviewed on:** 2026-10-22
**Commit range reviewed:** `origin/master..working-tree`. `origin/master` and `HEAD` are both `c02d475`. The work is uncommitted on branch `feature/webdesign-plugin-skills`, so I reviewed the working tree: `git diff origin/master` (7 tracked files) plus the 4 untracked skill files.
**Verdict:** pass-with-findings

## What was checked

- **Rule ledger R01-R37: each row is in its stated destination, with its wording kept, and nowhere else. D1 is the only duplicate.** Met. A script compared every non-blank line of `origin/master:agents/ui-ux-designer.md` with the slimmed agent and the four new files.
  - Every line that carries a rule appears in exactly one destination, and it is the one the ledger names.
  - Some lines matched more than one file, but only structural ones: code fences, closing tags, the `## Design Philosophy` heading and the "Before delivering any UI work:" lead-in.
  - Some original lines matched no file. Each is an allowed edit:
    - line 5: `tools` gained `Skill` (R01);
    - lines 36, 54, 149: heading levels changed;
    - line 69: the profile-missing halt moved into D1 (R08);
    - line 76: rewritten to the External skill reference form (R10, as the ledger says);
    - lines 89-90: the list numbers "3." and "4." were dropped when R14 moved to AP and R15 moved to AG.
  - The split rows are split as the ledger says:
    - R34: lines 360, 362, 364 → AP; lines 361, 363, 365-369 → WF.
    - R35: line 377 → AP; the rest → WF.
    - R22 carries line 163 into AP.
- **The agent keeps only R01-R03, R15, R36, R37 and the "Method lives in the skills" section, and `tools` includes `Skill`.** Met.
  - `agents/ui-ux-designer.md:5` reads `tools: Read, Grep, Glob, Write, Edit, Skill, mcp__codegraph__*`.
  - The `skills: - angular` preload is unchanged, as Q2 decided.
  - The new section (`:30-39`) sits after Step 0 and before the contract requirement.
  - It invokes `agentic-auto-improve:application-design` or `agentic-auto-improve:website-design`, and stops if the skill cannot load (INV-7).
  - R15 is `:39`.
- **Step 1 of both skills covers every row of the Halt table and reads the project's profile (INV-4).** Met.
  - `skills/website-design/SKILL.md:13-28` and `skills/application-design/SKILL.md:21-36` carry the seven contract rows, word for word and in the same order.
  - `file-missing`, `row-missing` and `placeholder` are separate rows, and per-app `row-missing` is a row of its own.
  - Both read `<project root>/.claude/project-profile.md`, where the root is `CLAUDE_PROJECT_DIR`, else the repository holding the target files. Both say never to read the plugin's own copy.
  - INV-5 (no colour class before the polarity is read) is stated at `:28` and `:36`.
  - The two Step 1 blocks are identical, so D1 holds.
- **The extra `root-undeterminable` row the implementer added (not in the contract): my judgement.** Keep it. It is a justified divergence:
  - It implements the critic's WARN "The halt table has no row for a project root that cannot be determined", which the user accepted on 2026-10-22.
  - It heeds the journal entries 2026-10-15 ("must be told which project, not search for one") and 2026-10-16 ("cover both the unset root and the set-but-absent file").
  - It only adds a halt, so it cannot make a skill guess.
  - It is the first row, which is the right place: the root is needed before `file-missing` can name a path.
  - The contract's Data Shapes were never amended to include it (see F1).
- **`application-design` halts when the sibling foundation is missing (INV-3).** Met.
  - `skills/application-design/SKILL.md:38-40`: "If that file is absent, say which path you looked for (resolved against this skill's folder) and halt. Do not continue with the application layer alone."
  - INV-2 holds: the pointer at `application-patterns.md:3`, `../../website-design/references/foundation.md`, resolves to the one foundation file, and no foundation rule is restated in AS or AP (confirmed by the ledger walk).
- **The CONTRIBUTING.md convention exists, every External skill reference added follows it (INV-6), and `dataviz` is cited as a host built-in (Q1).** Met.
  - `CONTRIBUTING.md` § "Referencing another plugin's skill" has four rules: name, advisory, precedence, absence. It also explains the internal reference form.
  - A search of the five files for `<word>:<word>` tokens finds only two external references.
  - `frontend-design:frontend-design` is at `website-design/SKILL.md:40`. It carries a qualified name, *advisory*, the precedence sentence, and "If the plugin is absent, continue without it".
  - `dataviz` is at `application-design/SKILL.md:48`, described as "a host built-in skill, not from a plugin". It carries *advisory*, the precedence sentence, and "If it is absent, continue without it".
  - Rule 1 of the convention gained a host built-in clause that the contract's value object does not have (see F1).
  - The `README.md` pointer sentence is present (`:471-472`).
- **The README skill list and counts and the four manifest descriptions match a listing of `skills/*/SKILL.md` (28), and the version is 0.9.16 in all five entries.** Met.
  - Listing: 28 folders. The README § Skills list (`:464-469`), sorted, is identical to that listing (`diff` exit 0).
  - `README.md:354` and `:419` both say 28.
  - The four manifest descriptions say 28: `plugin.json:5`, `.claude-plugin/plugin.json:6`, `.claude-plugin/marketplace.json:14`, `.cursor-plugin/plugin.json:4`.
  - The version is `0.9.16` at `plugin.json:4`, `.claude-plugin/plugin.json:5`, `.claude-plugin/marketplace.json:8` and `:15`, and `.cursor-plugin/plugin.json:3`.
  - No other number changed (the 17-versus-12 hook drift was left alone, as a Non-Goal says).
- **Run `check_version_bump.py --base origin/master`.** Exit 0, but the run proves nothing (see F2). It printed "no shipped plugin file changed": the script compares `origin/master...HEAD`, and HEAD is still `origin/master`. I re-ran its own `evaluate()` against the working tree. Exit 0: "version raised to 0.9.16".
- **Run `test_plugin_text_scans.py`.** Exit 0, 8 tests OK.
- **Run `test_skill_script_lookup.py`.** Exit 1, 21 failures in 20 tests. None is caused by this diff (see F3). The suite reads only skill markdown that contains `agentic-auto-improve/*/`. None of the four new files does, and none of the eleven files that do changed.
- **Run `test_check_version_bump.py`.** Exit 0, 7 tests OK.
- **Off-area drift.** No finding. `.claude/area-mapping.json` holds `"areas": {}`, so no area can be derived. The tracked diff touches exactly the eleven "Files to touch" of block 1 (seven modified, four new); nothing else in shipped paths changed.
- **End-User View.** Not applicable, as the contract states: no Angular UI surface is in `Files to touch`.

## Findings

- **F1 (warning): the contract's Data Shapes still describe the state before two accepted answers.** Locations: `skills/website-design/SKILL.md:19`, `skills/application-design/SKILL.md:27` (the `root-undeterminable` row), and `CONTRIBUTING.md` § "Referencing another plugin's skill", rule 1 (the host built-in clause).
  - Both additions are justified: one comes from the critic's WARN, which the user accepted, and the other from the Q1 answer.
  - But the contract's "Profile read outcome" value object still lists five outcomes, its Halt table has no `root-undeterminable` row, and its "External skill reference" value object still requires a fully qualified name with no built-in case.
  - INV-1 therefore reads as violated to anyone who checks the contract literally, and later readers of the contract see the wrong shape.
  - Fix: the contract owner amends the three places before the contract flips. Recorded in `JOURNAL.md` as a post-impl divergence lesson.
- **F2 (warning): `check_version_bump.py` passes without checking anything while the work is uncommitted.** Location: `.claude/scripts/check_version_bump.py:75-77`, which reads `git diff origin/master...HEAD` and `git show HEAD:<manifest>`.
  - With HEAD equal to `origin/master`, it reports "no shipped plugin file changed" and exits 0, whatever the working tree holds.
  - In this review the working tree is correct: `evaluate()`, fed the working-tree diff, the untracked files and the manifests on disk, returns "version raised to 0.9.16".
  - The gate's own command alone is not evidence of the bump. Re-run it after the commit, before the pull request.
- **F3 (warning): `test_skill_script_lookup.py` is red, and this diff did not cause it.** All 21 failures are in two blocks:
  - `skills/verify-before-done/SKILL.md:36`, with 13 failures. Its block "has no run line of the form py -3 "$VAR" ...", so every behaviour test on it fails too.
  - `skills/ship/SKILL.md:151`, with 8 failures. Its lookup returns `''` or the wrong cache version.
  - The suite scans only blocks containing `agentic-auto-improve/*/` (`test_skill_script_lookup.py:20, 89-91`).
  - The new skills contain no such block. None of the eleven scanned files is in this diff, and HEAD is `origin/master`. So the failures come from `origin/master` or this environment.
  - It must not be reported as passing. It needs its own follow-up issue; it is not a reason to block this change.
- **F4 (nit): a moved note now describes the wrong file.** Location: `skills/website-design/references/foundation.md:47`. R12 kept its wording, "Earlier revisions of this file cited a curated `~/.claude/references/ui-ux-pro-max/` extract". "This file" is now `foundation.md`, which never cited it; the note was about `agents/ui-ux-designer.md`. INV-1 allows only pronoun and heading changes, so replacing "this file" with "the `ui-ux-designer` agent" falls within it.
- **F5 (nit): the optional sibling read in `website-design` does not say what happens when the file is absent.** Location: `skills/website-design/SKILL.md:36`, which points at `../application-design/references/application-patterns.md` "only when the page shows live product data". Both skills ship together, so this is low risk. But the Sibling skill reference file mechanism says every read should say what happens on absence. A clause "if it is absent, design without it" would close it.
- **F6 (nit): some short connecting notes go beyond the contract's "New text" list.** Locations: `foundation.md:3, :65, :152, :164`; `application-patterns.md:3, :203, :208`; `agents/ui-ux-designer.md:37` (the "The skills hold ..." summary sentence).
  - Each one points to where the rest of a split section went, or adds the trading-wording note that the user's answer to WARN 7 asked for.
  - None of them states a design rule, so INV-1 is not broken. They are listed here so the next reader of the ledger is not surprised by them.
- **F7 (nit, not caused by this diff): the version check counts review artefacts as shipped files.** Location: `check_version_bump.py:19-28`. `.claude/reviews/` is not in `EXEMPT_PREFIXES`, so this review's own artefact counts as shipped (seen in the working-tree run). Here it changes nothing, because the bump is present. A docs-only review pull request would be asked for a version bump it does not need.

## What was NOT checked

- **The sibling-path read under a live skill invocation.** I did not invoke the Skill tool. The contract records the main session's trial (plugin cache and this repository). Cursor and Codex installs are still not trialled. The MECHANISMS entry carries the copy-into-both-skills fallback.
- **Whether `dataviz` really is a host built-in.** I took Q1's answer as given. I have no installed-plugin list to confirm it.
- **The `plugin-dev:plugin-validator` run** (acceptance criterion 8). The contract assigns it to the main session at `/verify-before-done` (scope note 3).
- **Whether the `test_skill_script_lookup.py` failures also occur on a clean `origin/master` checkout.** I showed they do not depend on this diff, by what the suite scans and what changed. I did not create a separate worktree to reproduce them.
- **The design rules themselves.** Their accuracy is a Non-Goal: rules move with their wording kept.
- **CodeGraph.** It was not used; every reviewed file is markdown or JSON, which the gate allowlist covers.

## Evidence

Commands, run from the worktree root unless shown otherwise:

| Command | Exit | Result |
|---|---|---|
| `git status --short` ; `git diff origin/master --stat` | 0 | 7 tracked files modified; untracked: 4 skill files, contract, follow-up stub, work item |
| `git rev-parse HEAD origin/master` | 0 | both `c02d475e62a6e18ce2c9e3a23bc59d641b6f4ad2` |
| `git show origin/master:agents/ui-ux-designer.md > %TEMP%/rv/orig.md` | 0 | 429-line source for the ledger |
| `py -3 -I %TEMP%/rv/walk.py <worktree>` (per-line placement of the original in AG/WS/WF/AS/AP) | 0 | only the structural lines and allowed edits listed under "What was checked" |
| `ls skills/*/SKILL.md` sorted vs README `:464-469` sorted, `diff` | 0 | 28 = 28, `LISTS_MATCH` |
| `grep` for skill counts and `"version"` in README and the four manifests | 0 | 28 everywhere; 0.9.16 in five entries |
| `grep -o` for `<word>:<word>` in the five reviewed files | 0 | external: `frontend-design:frontend-design` only (plus host built-in `dataviz` by name) |
| `grep -rlF "agentic-auto-improve/*/" skills/` | 0 | 11 files, none of them in this diff, none of them a new skill |
| `py -3 .claude/scripts/check_version_bump.py --base origin/master` | 0 | "no shipped plugin file changed; no version bump needed" (does nothing here, see F2) |
| `py -3 -I %TEMP%/rv/wtbump.py <worktree>` (calls `evaluate()` on the working tree) | 0 | "version raised to 0.9.16" |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 0 | Ran 8 tests, OK |
| `py -3 .claude/scripts/tests/test_skill_script_lookup.py` | 1 | Ran 20 tests, FAILED (failures=21), twice (223.8s, 188.5s). Every failure is in block `verify-before-done/SKILL.md:36` or `ship/SKILL.md:151`, and neither file is in the diff |
| `py -3 .claude/scripts/tests/test_check_version_bump.py` | 0 | Ran 7 tests, OK |

Files read:

- The contract, in full. I used the halt table, the ledger, INV-1 to INV-7, the critique, the user's answers and the Review checklist.
- `.claude/templates/concept-contract.md:384-403`, the six-section artefact shape.
- `.claude/reviews/2026-10-15-auto-cleanup-delivered-worktrees/fullstack-code-reviewer-pass2.md` and its `.gate.json`, as a worked example.
- `origin/master:agents/ui-ux-designer.md`, in full.
- The five destination files, in full: `agents/ui-ux-designer.md`, `skills/website-design/SKILL.md`, `skills/website-design/references/foundation.md`, `skills/application-design/SKILL.md` and `skills/application-design/references/application-patterns.md`.
- The diffs of `CONTRIBUTING.md`, `README.md` and the four manifests.
- `.claude/scripts/check_version_bump.py:1-90`.
- The head of `.claude/scripts/tests/test_skill_script_lookup.py`, for what it scans.
- `.claude/registries/MECHANISMS.md`, `VOCABULARY.md` and `JOURNAL.md`, for the janitor appends.

## Disposition

The verdict is pass-with-findings. Nothing here blocks the dependents, but the following must happen before the contract continues:

1. **F1.** The contract owner amends three things in `.claude/concepts/2026-10-22-webdesign-plugin-skills.md`:
   - add `root-undeterminable` to the outcome list of the "Profile read outcome" value object;
   - add the row to the Halt table;
   - add the host built-in clause to the "External skill reference" value object.
2. **F2.** After the commit, re-run `py -3 .claude/scripts/check_version_bump.py --base origin/master` and confirm "version raised to 0.9.16" before the pull request opens.
3. **F3.** File a follow-up issue for the red `test_skill_script_lookup.py` on `origin/master`. Do not report it as passing.
4. **F4-F7.** Optional nits. F4 and F5 are one-line wording fixes within INV-1.

Janitor work done in this pass:
- **MECHANISMS.md** (Universal): added "External skill reference convention" and "Sibling skill reference file". The contract left the second one as decide-at-review; I promoted it because it has two users.
- **VOCABULARY.md** (Universal): added "Design foundation", "Design surface" and "External skill reference".
- **JOURNAL.md** (Universal): added "An accepted critic WARN or answered Open Question must amend the contract body before approval", with Trigger `post-impl divergence`.
- **INTEGRATION.md**: not present in this repository, and nothing here would need it.
