# Review: 2026-11-13-audit-followups-165-chores — fullstack-code-reviewer

**Contract:** `.claude/concepts/2026-11-13-audit-followups-165-chores.md` (approved)
**Branch / tree:** `feature/354-audit-followups-165-chores`, uncommitted working tree, base `origin/master` 2fb4770 (`plugin.json` at 0.20.1)
**Scope:** production files of the single block, in part order (1) manifests, (2) agent text, (3) F5/F6 nits. The tests were read only to judge the pins.

Suites run in this tree (`py -3 -B`): `test_repo_consistency.py` 35 OK; `test_plugin_text_scans.py` 61 OK; `test_flat_worktree.py` 35 OK; `test_agent_skill_preloads.py` 11 OK (HEAD also has 11 `def test_`, so I-7 holds); `test_check_version_bump.py` 53 OK. I did not run `test_plugin_manifests.py`; its 2 known failures are the caller's proven baseline on clean master and are not counted here.

---

## Part 1: manifests

### `plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`

No findings. The diff changes only the four count-bearing description strings (28 -> 34 skills, 14 -> 15 agents/subagents, hooks stay at 14) and the five version fields (0.20.1 -> 0.20.2). The marketplace top-level description (no count) is untouched. Nothing else in the files moved. This meets I-2. `origin/master:plugin.json` still reads 0.20.1, so 0.20.2 is one patch step above it today.

**[INFO]: The version check has not judged this change yet**
`py -3 .claude/scripts/check_version_bump.py` prints "no shipped plugin file changed; no version bump needed" because the work is still uncommitted. That output proves nothing about I-2. Run it again after the commit, and paste the result in the pull request.

Pin (`ManifestCountPinTests`): it reads the real manifests and `count_oracles(PLUGIN_ROOT)` at test time, so no number is written into the test. It checks each file's nouns (I-1), and its controls cover a wrong number per noun, a dropped number and `subagents` mapping to the agent oracle. The failure message names exits (i) and (ii) and the stub. The pin is adequate.

---

## Part 2: agent text

### `agents/fullstack-code-reviewer.md`

**[WARN]: Clause (c) of the training-data check says "raise nothing whatever the answer is", which contradicts (a) and (b)** — Line 172
```
- **(c) Otherwise raise nothing.** This also holds when no contract is under review, whatever the contract's `## Chat Tool Impact` answer is, or if the answer is missing. Stating this limit is deliberate: the reviewer does not guess.
```
**Problem**: In I-5, "whatever that contract's `## Chat Tool Impact` answer is, or if the answer is missing" applies to the whole section: (a) and (b) fire on any answer, including a missing one. The implementation attached that clause to (c), the "raise nothing" branch. Read as written, it tells the reviewer to raise nothing whatever the answer is and to raise nothing when the answer is missing. That contradicts (a) and (b), and a literal reader can take it as a reason to skip both. "When no contract is under review, whatever the contract's answer is" also contradicts itself, because with no contract there is no answer. This is the one place where the new text is less accurate than I-5 requires. The pins cannot catch it, because they check genericity and not meaning.
```
Take every fact for this check from the contract under review and the diff, and nothing else. It applies whatever the contract's `## Chat Tool Impact` answer is, or if that answer is missing. Do not work out for yourself which file plays which role in the project's chat-tool surface.

- **(a)** ... (unchanged)
- **(b)** ... (unchanged)
- **(c) Otherwise raise nothing.** This also holds when no contract is under review. Stating this limit is deliberate: the reviewer does not guess.
```

---

**[INFO]: Question: should (b) fire on a "Deferred" answer?** — Line 171
The template (`.claude/templates/concept-contract.md:232`) says a Deferred contract "MUST NOT ship synthetic training examples", and the training agent refuses to generate data in that case. Under a Deferred answer, (b) still asks the author whether "training examples need an update". The expected answer is "no", so this does no harm, but the question is noise. The behaviour follows I-5 to the letter ("whatever that contract's answer is"), so this is not an implementation defect. If the owner wants it fixed, the next contract that touches the reviewer can tune it. No change is required now.

Checked and clean:
- (a), (b) and the closing line match I-5 (a)/(b) and the template's wording "the project's model-training agent or skill, if it has one" (`concept-contract.md:228`, `:232`).
- The text names no profile slot, no `sentinel-paths` file, no project file name, folder or agent. `ChatToolDefinitions.cs`, `SystemPromptBuilder.cs`, `ChatToolExecutor.cs`, `python/training-data/synthetic/` and `llm-training-engineer` are all gone, and a grep of `agents/` for them finds nothing.
- The text does not work out any file's role.
- Both findings are WARNINGs and never blocking.

### `agents/contract-critic.md`

No defects. Item 7 keeps "BLOCKER if hit", its trigger and `## Chat Tool Impact`. It quotes the template's three answer heads word for word without the final period: `Yes — this contract adds a chat tool`, `No — this endpoint/event is UI-only or admin-only`, `Deferred to a follow-up mini-phase` (`concept-contract.md:222/230/232`). The consuming-project precedent slug is replaced by the template's "Why this section exists", which meets I-3.

**[INFO]: "the template" is unnamed in item 7** — Line 72
Item 7 says "point to the template's `## Chat Tool Impact` section" but never names the file. Rule 8 exempts `.claude/` paths, so writing `.claude/templates/concept-contract.md` would pass the pin and save the critic a lookup. This is optional; elsewhere the critic already reads the template by that path.

Pins (`TestAgentPassagesAreGeneric`, rule 8):
- Rule 8 matches the Data Shapes definition: the segment set, both boundaries, the trailing `.` strip, the two-segment exemption and the `.claude` exemption.
- Its controls include all four must-fire and all seven must-not-fire cases, plus `in frob/data/.` and `/design-first`.
- The I-3 pin reads the heads from the template at test time, and the control with the old `Yes — declares schema` fails as required.
- The pins are adequate.

---

## Part 3: F5 / F6 nits

### `skills/task/SKILL.md`

No defects. `<wt>` is gone from Step 5c. Lines 456, 457, 467, 475 and 482 all say `<plan path>`. Line 442 keeps the folder-name rule with the 60-character cut at a hyphen and the `-2` to `-9` suffix, which matches `MECHANISMS.md:82`. It defines `<plan path>` as the plan's `path` from Step 1.5, read from the plan, which meets I-6. Line 475 still reads correctly: `..` of a flat path under `.claude/worktrees/` is `.claude/worktrees/`.

**[INFO]: "Both prefixes are required:" now follows the plan-path sentence** — Line 442
The colon used to introduce the prefix bullets right after the folder-name pattern. The new path sentence now sits between them, so the line reads slightly out of order. A possible fix is to move the `<plan path>` sentence to its own paragraph after the examples (line 448). This is cosmetic. The F5 pin keys on `60 characters`, `-2`, `-9` and `Step 1.5` within 5c, so moving the sentence keeps it green.

### `test_agent_skill_preloads.py` (F6, read only)
The run count is the same before and after (11 `def test_` at HEAD and in the tree, "Ran 11 tests" OK), which meets I-7.

---

## Contract audit

- **Data Shapes (I-1..I-8):** no structural divergence. I-5's text is weakened by the misplaced clause (WARN above), but this is a wording defect in the implementation, not a contract defect. I-8: `HookCountTests` and `ReadmeCountPinTests` are not touched by the diff; only the module docstring gained a line (5).
- **Reused Mechanisms:** the Count-claim oracle, the genericity pin and the Flat worktree helper are extended or consumed, with no parallel implementation.
- **New Mechanisms:** none, as declared. Rule 8 is one more rule in an existing helper.
- **Files to touch:** all 11 production and test files are listed. The other changes are the three stub renames to `.followup.superseded.md` (the main session's duty in Extension Points), the work-item brief, the contract and its round-1 history, and the new follow-up stub. All of them are under `.claude/` and were expected.
- **Off-area drift:** not applicable. `.claude/area-mapping.json` declares `"areas": {}`, so everything falls into `uncategorized` and there is no declared area to drift from.
- **End-User View:** not applicable (no Angular surface).
- **Integration consistency:** no endpoint, event or DTO.

## Registry janitor

- `MECHANISMS.md`: nothing to append. Rule 8 lives inside the existing genericity pin's entry area.
- `VOCABULARY.md`: nothing. The contract's three value-object names are still test-internal, and no later contract has reused them.
- `INTEGRATION.md`: nothing.
- `JOURNAL.md`: nothing. There was no justified divergence, no unforeseen failure mode and no falsified assumption. The WARN is an implementation slip that the contract had worded correctly.
- `~/.claude/logs/reviewer-verdicts.jsonl`: not written. The caller limited writes to this worktree. The line to append is:
  `{"ts":"2026-11-13T00:00:00Z","contract_path":"D:\\Dev\\HIPALANET\\claude-agentic-auto-improve\\.claude\\worktrees\\20261113-infra-354-audit-followups-165\\.claude\\concepts\\2026-11-13-audit-followups-165-chores.md","divergence":false,"drift_summary":"none (reviewer clause (c) misplaces I-5's 'whatever the answer' scope; wording fix)","critical_count":0,"warn_count":1}`

---

### Summary

| Severity | Count |
|---|---|
| [CRITICAL] | 0 |
| [WARN] | 1 |
| [INFO] | 4 |

**Verdict**: `FIX THEN SHIP`

**Top priority fix**: in `agents/fullstack-code-reviewer.md` line 172, move "whatever the contract's `## Chat Tool Impact` answer is, or if the answer is missing" out of clause (c) and into the lead sentence, so it scopes (a) and (b) as I-5 says.

### HANDOFF
- **Status:** has-issues
- **Files reviewed:** plugin.json, .claude-plugin/plugin.json, .claude-plugin/marketplace.json, .cursor-plugin/plugin.json, agents/contract-critic.md, agents/fullstack-code-reviewer.md, skills/task/SKILL.md (all under the worktree root); test pins read in test_repo_consistency.py, test_plugin_text_scans.py, test_flat_worktree.py, test_agent_skill_preloads.py
- **Issues to fix:**
  - [WARN] agents/fullstack-code-reviewer.md:172: clause (c) carries I-5's "whatever the answer / if missing" scope, so it reads as "raise nothing" on any answer and contradicts (a)/(b). Move it to the lead sentence.
- **Safe to test:** yes
- **Warnings:**
  - INFO: re-run check_version_bump.py after the commit (it currently sees no change).
  - INFO: item 7 could name `.claude/templates/concept-contract.md`.
  - INFO: SKILL.md:442 "Both prefixes are required:" now trails the plan-path sentence.
  - INFO: should (b) fire on a Deferred answer? This is a question for the owner and follows I-5 as written.
  - The reviewer-verdicts JSONL line was not written (outside the worktree). The text is in the report.
- **Context for next agent:** the fix is one sentence. All the pins stay green after it, because the passage gains no path, slot or hyphenated name.
- **Recommended next:** back-to-implementer
- **Suggested input for next agent:**
  TASK: In agents/fullstack-code-reviewer.md `## LLM Training Data Maintenance`, move "whatever the contract's `## Chat Tool Impact` answer is, or if the answer is missing" from clause (c) into the lead sentence. Leave (c) as "Otherwise raise nothing. This also holds when no contract is under review." Re-run test_plugin_text_scans.py.
  FILES: agents/fullstack-code-reviewer.md
  FOCUS: I-5 fidelity; keep the rules 1-8 pin green.

```yaml
findings:
  - id: F1
    severity: Soft
    file: agents/fullstack-code-reviewer.md:172
    description: The I-5 clause that scopes the whole check ("whatever the answer is, or if missing") is attached to the raise-nothing branch (c), so it contradicts (a) and (b).
    proposed_feedback_rule:
      name: feedback_scope_clause_on_the_rule_not_the_exception.md
      body: |
        When an invariant says a whole rule applies "whatever X is", put that clause in the rule's lead sentence, never inside its "otherwise" or residual branch.
        **Why:** in 2026-11-13 audit-followups-165-chores, the reviewer's clause (c) "raise nothing" took I-5's "whatever the answer is, or if missing" and read as an order to skip (a) and (b).
        **How to apply:** when you turn an invariant with lettered branches into agent text, check every scoping phrase: does it qualify the rule or one branch? Read the residual branch on its own and make sure it does not cancel the others.
  - id: F2
    severity: Safe
    file: agents/contract-critic.md:72
    description: Item 7 points to "the template" without naming its path.
    no_rule_needed:
      reason: The critic already reads .claude/templates/concept-contract.md by path elsewhere in its steps, so the omission costs a lookup and causes no misbehaviour. An optional clarity tweak needs no recurring rule.
  - id: F3
    severity: Safe
    file: skills/task/SKILL.md:442
    description: The colon of "Both prefixes are required:" no longer sits next to the pattern it introduces.
    no_rule_needed:
      reason: Prose order only, with no behaviour and no pinned text involved. A linter-class readability nit that a rule would not prevent better than normal review.
  - id: F4
    severity: Safe
    file: agents/fullstack-code-reviewer.md:171
    description: Question for the owner. Clause (b) asks about training examples even under a Deferred answer, whose template text forbids shipping them.
    no_rule_needed:
      reason: The behaviour follows the approved I-5 ("whatever the answer"), so it is an owner design choice and not a defect class. Any change belongs to a future contract touching I-5.
  - id: F5
    severity: Safe
    file: (process) check_version_bump.py
    description: The version check run on an uncommitted tree reports no shipped change, which proves nothing about I-2.
    no_rule_needed:
      reason: Already covered by the contract's Implementation Handoff and journal 2026-11-07 ("paste each required output"). The pasted output must come from the committed branch.
```
