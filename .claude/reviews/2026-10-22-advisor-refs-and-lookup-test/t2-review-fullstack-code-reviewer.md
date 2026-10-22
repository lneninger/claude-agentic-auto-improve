# Review: Advisor reference folder and skill-lookup test (sub-task 1), fullstack-code-reviewer

**Gate agent:** fullstack-code-reviewer
**Sub-task reviewed:** 1, advisor nudge, lookup blocks and version (gate t2)
**Contract:** `.claude/concepts/2026-10-22-advisor-refs-and-lookup-test.md` (approved)
**Reviewed on:** 2026-10-22
**Commit range reviewed:** `origin/master..working-tree`. `origin/master` and `HEAD` are both `660c0a4`. The work is uncommitted on branch `fix/followups-advisor-refs-and-lookup-test`. I reviewed `git diff origin/master` (8 tracked files modified) and the staged rename of the follow-up stub (`git status`: `RM`).
**Verdict:** pass-with-findings

## What was checked

- **INV-1: the nudge text.** Met.
  - The new `DESIGN_NUDGE` names no filesystem path.
  - It names `agentic-auto-improve:application-design` "for application screens" and `agentic-auto-improve:website-design` "for website pages". That is one line each, uses the registered Design surface terms, and does no keyword routing (Q1).
  - It calls both skills "advisory, NOT authoritative". It says the project's `review.documents`, or a document in the "Reference files" list above it, wins. It ends "If the skills are not installed, carry on without them."
  - The chart-palette sentence was dropped, as the amended Non-Goal records.
- **INV-2: nothing else in the output moves.** Met. The hook diff against master has exactly two hunks:
  - lines 136-153: the constants block;
  - lines 243-249: the suppression branch.
  - `TRIGGER_KEYWORDS`, `REMINDER`, `reference_section()`, the per-app appendix and the output JSON are outside both hunks, so they are byte-identical.
  - The layout keyword set has the same ten members. Only its name and its comment changed.
- **INV-3: suppression follows the new target.** Met.
  - The four-file `PRO_MAX_REFERENCE_FILES` tuple is gone.
  - `DESIGN_NUDGE_SKILLS = ("application-design", "website-design")` is checked as a substring of `prompt_lower`, which is case-insensitive.
  - The renames (`DESIGN_NUDGE_KEYWORDS`, `DESIGN_NUDGE_SKILLS`, `DESIGN_NUDGE`) are the contract's suggested names and are the only other edits. No test referred to the old names.
- **INV-4: both lookups match `skills/advance/SKILL.md` lines 340-357.** Met. I removed the leading indentation from advance 340-357 and from each copy, then compared them:
  - ship 152-169: `diff` exit 0;
  - verify-before-done 37-54: `diff` exit 0.
  - The variable is still `LANDER`, and the script path is still `.claude/scripts/land_contract.py`.
- **INV-5: run-line placement.** Met.
  - verify-before-done: the item 1 block ends with `py -3 "$LANDER" --help` at line 55. Item 2 keeps its number and heading, and is now prose. It names the empty-`LANDER` failure and defers to arm 1. Item 3 and later items are not renumbered.
  - ship: `py -3 "$LANDER" --module-tags --base origin/<base> --json` is at line 170, directly after the lookup's `fi`.
- **INV-6: both empty-LANDER fallbacks are intact.** Met.
  - verify-before-done: arm 1 ("`LANDER` is empty … Run Steps 1 to 4 … runner not found") is an unchanged context line in the diff.
  - ship: the prose at line 176 ("If `LANDER` comes …") and the hand derivation from `git -C <tree> diff --name-only` at line 180 are outside the diff hunk.
- **The new test method in `.claude/hooks/tests/test_addons.py`.** Partly met (see F1).
  - `test_the_layout_nudge_names_the_design_skills_and_no_path_and_is_suppressed_when_they_are_named` sits in `AngularTailwindAddonTests`. It uses `run_hook` and the installed-add-on fixture.
  - Row (a) asserts both full skill names and the absence of `ui-ux-pro-max`, `~/` and `.claude/references/`. It does not assert "advisory", `review.documents` or the carry-on clause, though the contract's row (a) lists the first two.
  - Row (b) defines the region as starting at the second `[architecture-advisor]` marker. It extracts `~/`, `.claude/`, drive-letter and slash-separated file-extension tokens, which matches the amended definition. The positive control is real: three fake paths, one of each kind, are planted, and the test asserts at least 3 hits through the same extractor. The region is then asserted to have none, so the count can only be met by catching all three plants.
  - Row (c) uses "design the dashboard layout using application-design" and the website-design variant. Each carries a layout keyword, as the critique amendment requires. A control asserts that the CSS reminder still prints.
  - Row (d) uses "restyle the component styles", not the contract's example. That prompt still meets the row's purpose: a UI prompt with no layout word. A control asserts that the reminder prints.
  - Red-on-old: I ran the method against a copy of master's hook, swapped into the test's temporary project only. It fails at row (a), so the test catches the old behaviour. Row (c) is not reached in that run. On reading, it would also fail on the old hook, because the old suppression tuple held only `.md` file names.
- **Run list.** Met for the three commands I ran (see Evidence):
  - `test_addons.py`: exit 0, 14 tests;
  - `test_plugin_manifests.py`: exit 0, 138 passed;
  - `test_ship_skill_sync.py`: exit 0, 104 passed.
  - `test_skill_script_lookup.py`: not run by me. I relied on the main session's run (see What was NOT checked).
  - `check_version_bump.py`: the main session runs it after the commit.
- **The five version entries.** Met. All five read `0.9.17`, one patch above master's `0.9.16`, per the diff's `-`/`+` lines:
  - `plugin.json:4`
  - `.claude-plugin/plugin.json:5`
  - `.cursor-plugin/plugin.json:3`
  - `.claude-plugin/marketplace.json:8` (top-level)
  - `.claude-plugin/marketplace.json:15` (`plugins[0]`)
- **The superseded stub.** Met.
  - `git status` shows it renamed to `.claude/concepts/followups/2026-10-22-advisor-phantom-design-refs.followup.superseded.md`.
  - Its first line under the title is `**Superseded by:** .claude/concepts/2026-10-22-advisor-refs-and-lookup-test.md`.
  - `**Status:** superseded`.
  - `**Issue:** not opened (out of scope per the brief)`.
- **Off-area drift and the Files to touch list.** No finding.
  - Every tracked change is in the ten Files to touch.
  - The untracked files are the contract, the work item and this review, all under `.claude/`.
  - `.claude/area-mapping.json` declares no areas.
  - `test_skill_script_lookup.py`, `README.md` and the other skills are untouched.
- **End-User View.** Not applicable, as the contract states.

## Findings

- **F1 (warning): row (a) does not pin INV-1's precedence and absence clauses.** Location: `.claude/hooks/tests/test_addons.py`, the row (a) block of the new method (the `for needle in (...)` loop).
  - Problem: the contract's row (a) requires the context to contain "the word "advisory" and `review.documents`". The test asserts only the two skill names and three banned strings.
  - Impact: a later edit could drop "the project file wins" or "carry on without them" and the test would stay green. Those are the clauses JOURNAL 2026-10-05 ("Text delivered to the model must say which rule wins") exists to protect.
  - The hook text itself is correct today, so this does not block.
  - Fix: extend the needle tuple to `("agentic-auto-improve:application-design", "agentic-auto-improve:website-design", "advisory", "review.documents", "not installed")`.
- **F2 (nit): row (d)'s prompt differs from the contract's example.** The test uses "restyle the component styles". The contract suggests "restyle the button component". Both are UI prompts with no layout keyword, and the reminder control proves the trigger fired. No change needed. It is recorded so a reader of the contract is not surprised.
- **F3 (nit): the nudge says "advisory" twice.** The header says "consider these plugin skills (advisory)", and the next line says "They are advisory, NOT authoritative". This is harmless prompt text. Removing the parenthetical would save a few tokens on every layout prompt.

## What was NOT checked

- **`py -3 .claude/scripts/tests/test_skill_script_lookup.py`.** I did not run it, because it takes about 4 minutes and the main session was already running it. I relied on that run. The "21 failures to green" claim rests on it. My own evidence for INV-4 and INV-5 is the verbatim `diff` against advance and the run-line placement. Those are the two causes the contract names for the 21 failures.
- **`py -3 .claude/scripts/check_version_bump.py --base origin/master`.** The main session runs it after the commit. Before the commit, HEAD equals `origin/master`, so the script would report "no shipped plugin file changed" and prove nothing (the same caveat as F2 of the 2026-10-22 webdesign review).
- **Row (c) red on the old hook, run in isolation.** My red-on-old run stopped at row (a). Row (c) is red on the old hook by reading, not by a run.
- **Live resolution of `agentic-auto-improve:application-design` by a host.** It is advisory text, and it is ASSUMED in the contract.
- **CodeGraph.** Not used. The hook and test are Python, but the review was a diff audit of the two hunks named in the contract and needed no symbol tracing.

## Evidence

Commands, run from the worktree root unless shown otherwise:

| Command | Exit | Result |
|---|---|---|
| `git rev-parse --short origin/master` ; `git rev-parse --short HEAD` | 0 | both `660c0a4` |
| `git status --short` | 0 | 8 tracked files modified; stub `RM` to `.followup.superseded.md`; untracked: contract, work item, this review folder |
| `git diff origin/master --stat` | 0 | 9 files, 119 insertions, 32 deletions |
| `git diff origin/master -- <hook> skills/ plugin.json .claude-plugin .cursor-plugin` | 0 | hook: two hunks (constants, suppression); skills: lookup blocks only; five version lines 0.9.16 → 0.9.17 |
| `git diff -M origin/master -- .claude/concepts/followups/` | 0 | rename, plus the Superseded-by, Status and Issue lines |
| `git diff origin/master -- .claude/hooks/tests/test_addons.py` | 0 | one new method, 59 lines |
| `sed -n '340,357p' skills/advance/SKILL.md \| sed 's/^   //'` vs `sed -n '152,169p' skills/ship/SKILL.md`, `diff` | 0 | identical |
| same vs `sed -n '37,54p' skills/verify-before-done/SKILL.md \| sed 's/^   //'`, `diff` | 0 | identical |
| `py -3 .claude/hooks/tests/test_addons.py` | 0 | Ran 14 tests, OK |
| `py -3 .claude/scripts/tests/test_plugin_manifests.py` | 0 | 138 passed, 0 failed |
| `py -3 .claude/scripts/tests/test_ship_skill_sync.py` | 0 | 104 passed, 0 failed |
| `py -3 -I %TEMP%/rvcode-advisor/redcheck.py <worktree>` (the new method against master's nudge and suppression tuple, swapped into the fixture's temporary project only) | 1 | FAILED at row (a): "'agentic-auto-improve:application-design' not found" in the old nudge, so the test is red on the old hook |
| `py -3 .claude/scripts/tests/test_skill_script_lookup.py` | n/a | not run here; relied on the main session's run |
| `py -3 .claude/scripts/check_version_bump.py --base origin/master` | n/a | main session, after the commit |

Files read:

- The contract, in full.
- `.claude/reviews/2026-10-22-webdesign-plugin-skills/t2-review-fullstack-code-reviewer.md` and its `.gate.json`, for the six-section shape.
- `.claude/hooks/tests/test_addons.py:1-125`, for the fixture.
- The diffs listed above.
- `skills/ship/SKILL.md` around lines 152-180, via grep, for the fallback prose.

## Disposition

The verdict is pass-with-findings. Nothing blocks the commit.

1. **F1 (recommended before the commit).** Add `"advisory"`, `"review.documents"` and `"not installed"` to row (a)'s needle tuple, so that INV-1's precedence and absence clauses are pinned.
2. **After the commit.** Run `py -3 .claude/scripts/check_version_bump.py --base origin/master` and confirm "version raised to 0.9.17". Confirm that the main session's `test_skill_script_lookup.py` run ended OK.
3. **F2, F3.** Optional.

Janitor work in this pass:

- **MECHANISMS.md:** nothing to add. No new mechanism; existing ones were brought back into line.
- **VOCABULARY.md:** nothing to add.
- **JOURNAL.md:** nothing to add. There was no divergence from the contract, and no ASSUMED item was falsified.
- **INTEGRATION.md:** not present, and nothing here would need it.
