---
id: 204
issue_offer: opened
title: Memory boundary review fixes
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/204
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t14-memory-boundary-review-fixes
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/207
issue_link: deferred
status: shipped
created: 2026-11-02
---

# Memory boundary review fixes

## Problem statement
Sub-task 14 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 14. Memory boundary review fixes (`python-ai-developer`)

**Depends on:** 2, 3, 4

**Files to touch:**
- `.claude/scripts/memory_boundary.py`
- `.claude/scripts/tests/test_memory_boundary.py`
- `.claude/scripts/tests/test_memory_off_parity.py`
- `.claude/scripts/generate_registry_digest.py`
- `.claude/scripts/tests/test_registry_entries.py`
- `skills/design-first/SKILL.md`
- `skills/design-first/references/central-memory.md`

**Pre-written TASK block:**
```
TASK: Fix findings B1, W1, W2, W3, I1 and I2 of the block 5 review. Tests first.
  B1: in cmd_record, refuse "not-enabled" only when the profile state is "disabled" or the outcome's state
  is "disabled". Under profile state "unconfigured", write only the line
  "Memory: unconfigured (<reason>) | <date>", with the reason taken from the profile (read_config), never
  from the outcome, and ignore any retrieved or reported entries. --receipts still requires "enabled".
  Do not change the status "line" strings (block 15 adds the printed suffix in the skill text). Rewrite
  skills/design-first/SKILL.md Step 1.5 point 3 as: print its line (one line), then record it with
  record (outcome {"state": "unconfigured", "date": "<today>"}) into the brief whose branch: is the
  branch you are on (the same rule as point 4), then go to Step 2. With no such brief, print one line
  saying the memory record was skipped for want of a brief (point 4's wording) and go to Step 2; that is
  not a failure. Only a refusal or non-zero exit from record when a brief was found is a failure under
  point 2. Delete the sentence saying a not-enabled refusal "is expected". Split test_unavailable_and_unconfigured_states_are_recorded into an
  _unavailable_ test and an _unconfigured_ test. The second asserts the "Memory: unconfigured (shape-unknown)"
  line, frontmatter bytes unchanged, no Retrieved line even when the outcome carries items, and that
  --receipts is refused with not-enabled. Add an unconfigured variant to the positive control in
  test_memory_off_parity.py; the three disabled profiles stay byte-identical.
  W1: receipt_line accepts source_ref as the object capture-candidates emits ({file, line, title, date})
  and renders "<file>:<line>" (file through clean_text, line through safe_token). It keeps accepting a
  string. Use one helper for both receipt_line and cmd_capture_request's source_ref, not a copy. Add a
  test that runs capture-candidates on a fixture, puts a candidate's own source_ref object into a receipt,
  runs record --receipts and asserts "<file>:<line>" on the Captured: and Not sent: lines.
  W2: in central-memory.md section 3, write the normalise output to a second temporary file and pass that
  file to changed-items. In cmd_changed_items, pass each input item through the same per-item rules
  normalise applies (call the same function, do not copy it) and compare versions as the normalised
  strings. Tests: a raw item with scope NOT-A-SCOPE raises no notice; an integer version 1 against a
  recorded "1" raises no notice. Update the parity test's changed-items call to use a normalised file.
  W3: map a Trigger only by an exact match of its whole value (trimmed, case-folded, surrounding backticks
  removed): "pre-approval critic" gives user-decision; "post-impl divergence" gives source-code-fact;
  "manual" and "post-approval" are skipped as ai-hypothesis; anything else is skipped as unknown-trigger.
  Tests: "manual (follow-up to a pre-approval critic finding)" and "post-approval, found after post-impl
  review" are both skipped and never offered; each of the four canonical values maps as the table says;
  on the current JOURNAL.md every entry's mapping is unchanged.
  I1: in entry_blocks, an entry's own text also ends at a blank line followed by a non-indented line that
  is not a top-level match (Candidate reading, Revision 7). Test: a planted note paragraph naming
  .claude/concepts/<slug>.md after the last bullet of a section does not make that bullet a candidate.
  TierSplitIsByteIdentical stays green.
  I2: capture-candidates --default-branch defaults to None. When it is None, bind
  pr_merged.default_branch_or_none fail-soft (the existing _bind list at memory_boundary.py:58) and call
  it with cwd=str(<--project root>), so the project's own origin/HEAD is read, never the process's
  working directory. Pass the name it returns to select_linked_brief as default_branch_name. When it
  returns None (or the function is unbound), refuse "default-branch-unknown" before anything is offered,
  with one line saying to pass --default-branch <name>; never call pr_merged.default_branch(), which
  falls back to "master" (pr_merged.py:2380-2381), and never let select_linked_brief reach it with None
  (pr_merged.py:3016). Tests: a fixture project whose origin/HEAD is main, run from a different working
  directory, links the brief through main; a fixture with no origin/HEAD and no flag refuses
  default-branch-unknown and offers nothing; an explicit --default-branch still wins.
CONTEXT: concept contract (Revision 7: Commands, Provenance mapping and Trigger matching, Candidate
  reading, Extension Points Step 1.5); the block 5 review at
  .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t5-review-memory-boundary-fullstack-code-reviewer.md
  (B1, W1-W3, I1, I2).
FILES: the seven listed.
CONSTRAINTS:
  - No new subcommand, frontmatter key, hook, store or background process. Do not bump the plugin version
    (Parent Branch Delivery Rule).
  - I-M0 holds: with memory disabled, nothing is printed and no brief is touched.
  - Do NOT change the three tests that guard I-M0 (the disabled state): in test_memory_boundary.py,
    test_disabled_refuses_not_enabled_and_writes_nothing (:742-748, assertion at :747),
    test_an_outcome_that_says_disabled_writes_nothing (:750-755, assertion at :754) and
    test_receipts_with_memory_disabled_write_nothing (:860-866, assertion at :865). They must pass
    unchanged after B1. The only existing test to change is
    test_unavailable_and_unconfigured_states_are_recorded (:796), which B1 splits. If any other test
    asserts a refusal under unconfigured, change it and say why in your HANDOFF. Name each test after
    only what it asserts (journal entry drafted in the block 5 review).
  - Keep every pin passing: Step15TextTests in test_memory_off_parity.py (the regex
    "unconfigured.{0,300}one line" must still match), test_parent_branch_rule_text.py and
    test_repo_consistency.py SENTENCE_PLACEMENT for design-first, test_skill_script_lookup.py (the lookup
    block is unchanged), and test_plugin_text_scans.py (no skill text names a memory tool).
  - The adapter still never loads the hook file and parses no registry text itself.
  - Run test_memory_boundary.py, test_memory_off_parity.py, test_registry_entries.py,
    test_plugin_text_scans.py, test_skill_script_lookup.py, test_parent_branch_rule_text.py,
    test_repo_consistency.py and the .claude/hooks/tests suite, and quote the results.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

## Out of scope
- Everything outside this sub-task's handoff block; see the other sub-tasks of the contract.

## Known context
- Parent / epic: #161 (https://github.com/lneninger/claude-agentic-auto-improve/issues/161)
- Related items: the other sub-tasks of `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`
- Affected areas: the files named in the handoff block

## North-star alignment
- inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md

## Open questions from intake
- none; the sub-task's criteria were approved at the contract gate.

## Size
Task of .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md.

## Routing
task of .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md - dispatched by /advance
