---
id: 389
issue_offer: pending
title: Review remedy F1 and F2
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/389
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-11-audit-followups-165/t12-review-remedy-f1-and-f2
worktree: none
north_stars: inherited from .claude/work-items/2026-11-11-165-audit-followups.md
parent_issue: 165
base: feature/165-audit-followups
contract: .claude/concepts/2026-11-11-audit-followups-165.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/392
issue_link: deferred
status: shipped
created: 2026-11-12
---

# Review remedy F1 and F2

## Problem statement
One task of the approved contract `.claude/concepts/2026-11-11-audit-followups-165.md` (parent issue #165), added by its Revision 4 amendment after the t10 review returned blocked. The block below is the contract's own handoff, copied verbatim.

## Acceptance criteria
### 12. Review remedy F1 and F2 (`python-ai-developer`)

**Depends on:** none — blocks 1-9 are merged; block 10 is blocked and is never a dependency

**Files to touch:**
- `.claude/templates/concept-contract.md`
- `skills/auto-improve-finish-install/SKILL.md`
- `.claude/scripts/tests/test_plugin_text_scans.py`
- `.claude/scripts/tests/test_memory_off_parity.py`

**Pre-written TASK block:**
```
TASK: Fix the t10 blockers F1 and F2 and the nit F4. TDD: write each new pin first, paste its red run on the
  parent tip, then fix, then paste the green run.
  - F1 pin (test_plugin_text_scans.py, beside TestChatToolImpactSectionIsGeneric): the WHOLE template names no
    TestTheRealPluginTree.NOT_SHIPPED name, and every backticked agent name in a "###" heading is in
    plugin_agent_names(). Import both, never copy. It runs without AGENTIC_PLUGIN_ROOT, so it never skips. Control:
    a planted "`ingestion-data-architect`" heading fails. Red today on lines 12 and 455.
  - F1 fix: line 12's implementer list names exactly pr_merged.DEFAULT_IMPLEMENTERS (replace
    `ingestion-data-architect` with `python-ai-developer` and `cloud-engineer`). Line 455 becomes
    "### 3. Data pipeline (`dotnet-backend-architect`, or the project's own ingestion agent if it declares one) —
    if applicable". Change nothing else in the template (I-7 holds).
  - F2 pin (test_memory_off_parity.py, a new Stage 2 class): in the section from "## Stage 2" to "## Stage 3",
    every sentence holding --fix says Stage 2 asks nothing about it and names the run's one ask (Stage 1a, or
    the history record check when Stage 1a was skipped). No sentence there tells the reader to offer or ask,
    with or without a condition, and none promises to run the Stage 2 preview again after --fix. Controls, each
    must FAIL: master's bullet ("Offer to run `plugin_doctor.py --fix` ... then run the preview again"); "ask the
    user whether to run --fix"; t10's conditional "if this run has not yet asked about `--fix`, ask once". The
    conditional is rejected because in run (a) it would take the run's one ask in Stage 2, before the history
    record check that I-5 (a) names as the only ask, and that check must not be edited. Control that must PASS:
    the reworded bullet below. Red today. fix_lines_without_ask must still pass on the whole file; the reworded
    bullet satisfies it with the existing ASK_WORD ("asks" comes before --fix).
  - F2 fix: reword the scaffold-missing bullet (lines 241-242) to say: the file is absent, and this command never
    creates it. Stage 2 asks nothing about `plugin_doctor.py --fix`: the run's one ask is Stage 1a's, or the
    history record check's when Stage 1a was skipped. Name the missing file and go on with the other files. Once
    --fix has created it, the next run of this skill proposes its content. The bullet promises no re-preview in
    this run. Check the wording against I-5's four runs and its rule for every other step.
  - F4: rename the module-level helper test_count_claims to count_claims_in, with its callers.
CONTEXT: concept contract at .claude/concepts/2026-11-11-audit-followups-165.md (V20, V21, I-5, Revision 4);
  review .claude/reviews/2026-11-11-audit-followups-165/t10-review-fullstack-code-reviewer.md (F1, F2, F4)
FILES: the four above
CONSTRAINTS:
  - Do NOT add "offer" (or any word) to ASK_WORD, and do not loosen fix_lines_without_ask or any existing pin.
  - Do not edit the history record check or Stage 1a text; their asks stay as they are (I-5 runs a-d).
  - Write nothing under .claude/reviews/.
  - Leave F5 and F6 alone (Q9).
  - A sub-task pull request into the parent branch does not raise the plugin version (Parent Branch Delivery
    Rule); the landing raises it once. Touch no check_version_bump.MANIFESTS file (plugin.json,
    .claude-plugin/plugin.json, .cursor-plugin/plugin.json, .claude-plugin/marketplace.json).
  - A red suite in the Run list stops the block; report it, never pass it on as outside your files.
  - Run, each with py -3 -B, and paste every summary line:
    test_plugin_doctor.py with AGENTIC_PLUGIN_ROOT set to the worktree root (PowerShell:
      $env:AGENTIC_PLUGIN_ROOT = (Get-Location).Path), zero skips and zero failures;
    test_memory_off_parity.py; test_plugin_text_scans.py; test_parent_branch_rule_text.py;
    test_ship_skill_sync.py; test_repo_consistency.py;
    py -3 .claude/scripts/check_version_bump.py --base origin/feature/165-audit-followups
      --head-ref <this branch> --default-branch master (expect the parent-mode "keeps version" line)
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-11-audit-followups-165.md
  contract_status: approved
```

## Out of scope
- Every other block of the contract. Findings F5 and F6 stay as follow-ups (Q9).

## Known context
- Parent / epic: #165
- Related items: the blocked review `.claude/reviews/2026-11-11-audit-followups-165/t10-review-fullstack-code-reviewer.md`

## North-star alignment
- none: inherited from the parent brief, whose register holds no active thought.

## Open questions from intake
- none

## Size
Not sized: a task of an approved contract.

## Routing
task of .claude/concepts/2026-11-11-audit-followups-165.md dispatched by /advance
