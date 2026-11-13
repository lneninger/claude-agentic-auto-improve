## Test Strategy Review: 2026-11-13-audit-followups-165-chores

Scope: the uncommitted diff on `feature/354-audit-followups-165-chores`, covering `ManifestCountPinTests` (test_repo_consistency.py), rule 8 and `TestAgentPassagesAreGeneric` (test_plugin_text_scans.py), `Step5cWorktreePathTests` (test_flat_worktree.py) and the F6 move into `DebugAreaRoutingTests` (test_agent_skill_preloads.py). I checked them against contract I-1 to I-8.

What I ran on this tree. All four suites are green: test_repo_consistency 35 OK, test_plugin_text_scans 61 OK, test_agent_skill_preloads 11 OK, Step5c + TaskSkillWorktreeText 13 OK. I also ran no-file probes (`py -3 -B -` on stdin) of `folder_paths`, `chat_tool_violations`, `reviewer_training_section` and `step_5c_problems`. Their outputs are quoted below. I ran no mutation pass, so the "would stay green" claims marked *(read, not run)* come from reading the code.

What holds up:
- I-1, the manifest pin. The real test reads `count_oracles(PLUGIN_ROOT)` when it runs and hard-codes no number. The noun-presence check closes the vacuous cases: if a count is written in a form `_CLAIM_RE` cannot read ("34+ skills", "dozens of skills", more than two gap words), there is no claim, the noun counts as missing, and the test fails loudly.
- Rule 8's must-fire and must-not-fire controls really fire and really stay quiet, for the reasons the contract gives. I traced each one through the regex, and the extra `in frob/data/.` control does exercise the `rstrip(".")` path.
- F6 changes nothing that is tested: 11 `def test_` before (HEAD) and 11 after, the same names, and "Ran 11 tests". Doing the `TestTheRealPluginTree` import inside `setUpClass` keeps unittest from collecting that class a second time in this module.

### Critical (false confidence / missing protection on a contract Invariant)

- **The positive half of I-5 has no test. The reviewer section can be emptied and the suite stays green** (test_plugin_text_scans.py `test_reviewer_training_section_is_found_and_names_no_consuming_projects_artefact`, `..._names_no_profile_slot_and_no_sentinel_file`)
  **Gap:** both reviewer tests guard against vacuity with `assertTrue(section.strip())`. But `_section` returns the heading line too, so a section that is only a heading passes the guard. Probe: `reviewer_training_section("## LLM Training Data Maintenance\n\n## Next\n")` returns `'## LLM Training Data Maintenance\n'`, and `.strip()` is truthy. Everything else is a negative check (no rule 1-8 hit, no `project-profile`, no `sentinel-paths`). I-5's required behaviour is never asserted: (a) raises a WARNING when the contract names a chat-tool file and training examples are missing, (b) raises one WARNING asking the question when only an endpoint or event is named, (c) otherwise raises nothing, "never blocking", and the template's agent wording "the project's model-training agent or skill, if it has one".
  **Why it matters:** this is the passage whose content the contract rewrote. A later edit that deletes (a) to (c), or that turns the WARNING into a BLOCKER, passes all three tests. The suite checks only that the passage is generic, not that it still does its job.
  **Fix:** add one real assertion on the section body below the heading: it is non-empty, and it holds the three (a), (b), (c) markers, `WARNING`, `never blocking` and the template phrase `model-training agent or skill, if it has one`. Read that phrase from `concept-contract.md:228` or `:232` at test time rather than freezing it, in the way I-3 reads the answer heads. Add a planted control: a heading-only section and one with "BLOCKER" in place of "never blocking", both of which must fail. Change the vacuity guard so it tests the body, not `section.strip()`.

### High

- **Rule 8 cannot see the most common path form in this plugin: a path rooted at a placeholder, home or absolute prefix** (test_plugin_text_scans.py `_FOLDER_PATH_RE`, lookbehind `(?<![\w.\-/])`)
  **Gap:** because `/` is in the lookbehind, a path whose first segment follows a `/` never matches. Probe output (rules that fire, from `chat_tool_violations`):
  ```
  '<repo>/python/training-data/synthetic/' [] []
  '`<repo>/frob/data/`'                    [] []
  '~/frob/train-data/'                     [] []
  '/srv/frob/train-data/'                  [] []
  'C:\\frob\\train\\data'                  [] []
  'python/training-data/synthetic/'        [8]
  ```
  So the exact text this contract removed, written in the plugin's own `<repo>/...` idiom (used throughout the shipped agents and skills), passes rules 1 to 8. The contract states only the two-segment residual (`frob/data`). The prefix-anchored residual is neither stated nor controlled. The regex matches the contract's wording ("previous character is not a segment character or `/`"), so this is a spec gap that the tests faithfully encode, not an implementation slip.
  **Why it matters:** I-4 says the passages "name no folder path outside `.claude/`". A reviewer who rewrites the training-data bullet as `<repo>/python/training-data/synthetic/` brings back the consuming-project folder this contract removed, and nothing stops it.
  **Fix:** escalate to the owner. Rule 8 should also start a path after a placeholder (`<...>/`), `~/` or a leading `/`. The `.claude` exemption then applies to the first real segment, so `<repo>/.claude/...` stays exempt. Add these as must-fire controls: `<repo>/frob/data/`, `~/frob/data/`, `/srv/frob/data/`. Add `<repo>/.claude/hooks/` and `the /design-first skill` as must-not-fire. If the owner keeps the narrow rule, the contract must state the prefix-anchored residual next to the two-segment one, and a must-not-fire control must record it so the blind spot is documented rather than hidden.

- **The Step 5c controls exercise a twin helper that the real assertions never call** (test_flat_worktree.py, `step_5c_problems` vs `test_step_5c_names_no_wt_anywhere`, `..._in_each_of_the_three_command_blocks`, `..._in_the_outside_the_repo_bullet`, `..._folder_name_line_keeps_...`)
  **Gap:** the five `test_control_*` tests feed `step_5c_problems` and prove it fails on each planted 5c. The four real tests re-implement the same four checks inline: their own `FENCE_RE.findall`, their own `startswith("- **Every folder OUTSIDE the repo")`, their own needle loop. The real tests never call `step_5c_problems`. The repo's own convention, stated in the test_repo_consistency.py docstring, is that "each positive control feeds the SAME helper". Today the two copies agree (probe: `step_5c_problems(real 5c) == []`), but the controls prove nothing about the code that guards the real skill.
  **Why it matters:** if one copy is edited (a bullet prefix changed, a needle dropped, the fence regex loosened in a real test), the controls stay green and the real pin goes quietly weaker.
  **Fix:** make the real assertion `self.assertEqual(step_5c_problems(self.real_section()), [])`, or have each real test assert that the matching problem string is absent from `step_5c_problems(real)`. Delete the inline copies.

### Medium

- **The I-6 "one name" pin forbids only the literal `<wt>`, so rebuilding the path under any other placeholder passes** (test_flat_worktree.py `step_5c_problems`, `test_step_5c_names_no_wt_anywhere`)
  **Gap:** probe output: `made_up_5c(prose="Open `.claude/worktrees/<folder>/` in a window.")` gives `[]`, and a second block `code -n ".claude/worktrees/<slug>/x" # <plan path>` also gives `[]`, because the presence check is satisfied by a comment. I-6's invariant is "never rebuilt from the folder name". The test checks for one spelling of the old name, not for the rebuild.
  **Fix:** also assert that no `.claude/worktrees/<` (a placeholder segment under the worktrees folder) appears anywhere in 5c, and that no command block names both `.claude/worktrees/` and `<plan path>`. The plain `.claude/worktrees/` prose in 5c (the gitignore and `..` sentences) stays legal. Add a planted control for each check.

- **Critic item 7 is read as a single physical line** (test_plugin_text_scans.py `agent_item_7`)
  **Gap:** `agent_item_7` returns only the line that starts with `7. **Integration surface omission`. If the item is wrapped or gains a continuation line, any project-specific text on later lines is never scanned by rules 1 to 8. The I-3 heads check might still pass if the heads stay on line one.
  **Fix:** take the item from its line up to the next `^\d+\. \*\*` item or the next heading. Add a control in which a second line of item 7 carries `frob/train-data/synthetic/` and must fire rule 8.

### Low / Nit

- **I-3 does not catch an item 7 that keeps the old answers next to the new ones.** `item_7_problems` checks only that each template head is present, so an item listing six sanctioned answers (old and new) passes. Add a check that the item has exactly three backticked answers in the sanctioned list, or keep the old strings as a must-be-absent list.
- **`"-2"` and `"-9"` are bare substring needles.** Probe: the rule line `**Name the directory `20261113-2x-9y`**, cut to 60 characters, see Step 1.5.` gives `[]` although it has no suffix rule. Needle on `` `-2` to `-9` `` instead.
- **`len(blocks) != 3` ties the 5c pin to exactly three fenced blocks.** Adding a fourth, harmless block (for example a PowerShell twin, which the owner's Windows-command rule makes likely) turns it red without any behaviour change. Better: "every command block names `<plan path>`, and there is at least one".
- **`test_every_manifest_keeps_its_nouns` repeats the noun half of `test_manifest_description_counts_match_oracles`**, because `manifest_violations` already includes `manifest_noun_violations`. The per-manifest `subTest` message justifies it, but drop the noun half from one of the two or say why both exist. The hook counts in the two `.claude-plugin` manifests are also still pinned by `HookCountTests`. I-8 forbids editing that class, so this overlap is accepted.
- **The marketplace noun check passes if any description holds the nouns.** If the counts moved from the plugin entry to the top-level description, the check would still pass. That is within the contract ("met by any description of the file"). Noted, not a defect.

### Recommended test-suite shape

- Keep the manifest pin as it is.
- Rule 8: add a prefix-anchored must-fire row (`<repo>/`, `~/`, `/`) and an exemption row for `<repo>/.claude/`, after the owner decides on the rule.
- Reviewer section: one real positive-content assertion for I-5 (a), (b), (c), WARNING-only, and the template agent phrase, plus two planted controls (heading-only, BLOCKER).
- Step 5c: one real test that calls `step_5c_problems`, plus a "no `.claude/worktrees/<`" check with its control.
- Item 7: extract to the next item, with a control on a two-line item.

That is about five tests added or changed. No new suite.

### Verdict

NEEDS FIXES. The manifest pin and the F6 move hold. The reviewer-section tests pass on an empty section, rule 8 misses `<repo>/`-rooted paths, and the 5c controls exercise a helper that the real assertions never call.

### HANDOFF
- **Status:** needs-fixes
- **Files reviewed:**
  - D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261113-infra-354-audit-followups-165\.claude\scripts\tests\test_repo_consistency.py
  - D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261113-infra-354-audit-followups-165\.claude\scripts\tests\test_plugin_text_scans.py
  - D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261113-infra-354-audit-followups-165\.claude\scripts\tests\test_flat_worktree.py
  - D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261113-infra-354-audit-followups-165\.claude\scripts\tests\test_agent_skill_preloads.py
  - D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261113-infra-354-audit-followups-165\agents\contract-critic.md
  - D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261113-infra-354-audit-followups-165\agents\fullstack-code-reviewer.md
  - D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261113-infra-354-audit-followups-165\skills\task\SKILL.md
  - D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261113-infra-354-audit-followups-165\.claude\concepts\2026-11-13-audit-followups-165-chores.md
- **Critical findings:** F1. The positive half of I-5 has no test, and a heading-only reviewer section passes all three reviewer tests (the vacuity guard tests `section.strip()`, which includes the heading).
- **Contract alignment:** divergent. The tests match Extension Points, but I-5's positive behaviour is not tested, and rule 8 encodes a spec gap (`<repo>/`-rooted paths) that the contract does not state as a residual.
- **Recommended suite shape:** the manifest pin unchanged; rule 8 with prefix-anchored rows; one positive I-5 assertion with two controls; the 5c real test calling `step_5c_problems`, plus a "no `.claude/worktrees/<`" check; item 7 extracted to the next item.
- **Warnings:** the 5c twin helper (the controls never protect the real code); a `<wt>`-only absence check; one-line item-7 extraction; `-2`/`-9` substring needles; the fixed count of three fenced blocks; a redundant noun check across the two manifest tests. I ran no mutation pass; these verdicts come from probes and reading.
- **Context for next agent:** the rule-8 prefix question needs an owner decision before a test is changed (the contract's Data Shapes defines the lookbehind). F1, F3, F4 and F5 are test-only changes that fit within I-5, I-6 and I-3 as written.
- **Recommended next:** senior-test-engineer (F1, F3, F4, F5); owner decision on F2 first.
- **Suggested input for next agent:**
  TASK: In test_plugin_text_scans.py add a real I-5 assertion on the body of the reviewer's `## LLM Training Data Maintenance` section: (a)/(b)/(c), WARNING-only and never blocking, and the template's "model-training agent or skill, if it has one" phrase read from concept-contract.md. Add controls for a heading-only section and a BLOCKER section. Make `agent_item_7` read to the next numbered item, with a two-line control. In test_flat_worktree.py make the real Step 5c tests call `step_5c_problems`, and add a "no `.claude/worktrees/<`" check with a control. Needle `` `-2` to `-9` ``. If the owner approves, widen rule 8 to placeholder, `~/` and `/` roots, with controls.
  FILES: .claude/scripts/tests/test_plugin_text_scans.py, .claude/scripts/tests/test_flat_worktree.py
  FOCUS: I-5 positive behaviour, I-6 "never rebuilt", I-3 one-item scope, I-4 (rule 8 prefix residual)

```yaml
findings:
  - id: F1
    severity: Breaking
    file: .claude/scripts/tests/test_plugin_text_scans.py:TestAgentPassagesAreGeneric (reviewer tests)
    description: Vacuity guard uses section.strip() on a slice that includes the heading; the I-5 positive behaviour is unasserted, so an emptied section passes.
    proposed_feedback_rule:
      name: feedback_text_pin_guards_the_body.md
      body: |
        A text pin's "section was found" guard must test the body below the heading, and a pinned passage needs at least one positive-content assertion besides its negative scans.
        **Why:** _section returns the heading line, so a heading-only passage passed every genericity test in the 2026-11-13 review.
        **How to apply:** strip the heading before the non-empty check; add a planted heading-only control that must fail.
  - id: F2
    severity: Soft
    file: .claude/scripts/tests/test_plugin_text_scans.py:_FOLDER_PATH_RE
    description: Rule 8 never fires on paths rooted at <repo>/, ~/, / or a drive letter; the removed training folder rewritten as <repo>/python/training-data/synthetic/ passes rules 1-8.
    proposed_feedback_rule:
      name: feedback_path_scans_cover_placeholder_roots.md
      body: |
        A scan that bans folder paths must include must-fire controls for the plugin's own path idioms: <repo>/..., ~/..., /abs/..., and drive-letter paths.
        **Why:** rule 8's lookbehind excluded any segment after "/", so <repo>/-rooted paths escaped (2026-11-13).
        **How to apply:** in every path-scan contract, list the rooted forms as must-fire or as an explicitly stated residual with a control.
  - id: F3
    severity: Soft
    file: .claude/scripts/tests/test_flat_worktree.py:Step5cWorktreePathTests
    description: Controls test step_5c_problems; real assertions re-implement the checks inline and never call it.
    no_rule_needed:
      reason: The repo convention "each positive control feeds the SAME helper as the real test" is already written as the module rule in test_repo_consistency.py's docstring; this is a lapse against it, not a new class. The fix is to cite that convention in the senior-test-engineer task.
      existing_rule: .claude/scripts/tests/test_repo_consistency.py (module docstring, "each positive control feeds the SAME helper")
  - id: F4
    severity: Soft
    file: .claude/scripts/tests/test_flat_worktree.py:step_5c_problems
    description: The I-6 pin bans only the literal <wt>; rebuilding the path with another placeholder under .claude/worktrees/ passes.
    proposed_feedback_rule:
      name: feedback_pin_the_invariant_not_the_old_token.md
      body: |
        When a pin enforces "X is never done", assert the shape of X, not only the absence of the token the old text happened to use.
        **Why:** the Step 5c pin banned `<wt>` but accepted `.claude/worktrees/<folder>/`, which is the same rebuild (2026-11-13).
        **How to apply:** add one planted control that does the forbidden thing with a fresh spelling.
  - id: F5
    severity: Soft
    file: .claude/scripts/tests/test_plugin_text_scans.py:agent_item_7
    description: Item 7 is extracted as one physical line; continuation lines escape rules 1-8.
    no_rule_needed:
      reason: Specific to a one-line extractor chosen by this contract's Extension Points; it is covered once F1's rule (the guard tests the real passage bounds) is applied to the extractor, and no other pin extracts a list item by first line.
  - id: F6
    severity: Safe
    file: .claude/scripts/tests/test_flat_worktree.py:step_5c_problems / test_repo_consistency.py:ManifestCountPinTests
    description: Substring needles "-2"/"-9", the exact count of three fenced blocks, and a duplicated noun check.
    no_rule_needed:
      reason: Nits; the needle and count couplings fail loudly, not silently, and the duplicate gives a per-manifest subTest message. They are fixed inside F3/F4's rewrite.
```
