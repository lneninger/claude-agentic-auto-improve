---
id: 228
issue_offer: opened
title: Re-review merge fix
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/228
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t20-re-review-merge-fix
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: UNKNOWN
issue_link: unknown
status: implementing
created: 2026-11-03
---

# Re-review merge fix

## Problem statement
Sub-task 20 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 20. Re-review merge fix (`fullstack-code-reviewer`)

**Depends on:** 17, 19

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t20-re-review-merge-fix-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 17 and 19 together and write the review artefact. This review supersedes the block
  18 review (t18-review-merge-and-text-fixes-fullstack-code-reviewer.md).
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  (Revision 9, block 19; Revision 8, block 17)
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t20-re-review-merge-fix-fullstack-code-reviewer.md
CONSTRAINTS:
  - Start from a cold context. Do not read the t18 review before forming your own findings. Read it
    afterwards only to confirm B1 and W1 are cleared. Name base..head: the parent tip before block 17's
    merge (fdd7640) and block 19's head; name block 19's own range separately.
  - Block 17 again, on the current tree, judged by git blob ids, not bytes on disk: the checks of block
    18's CONSTRAINTS (registries, conflict markers, files outside block 17's Files to touch, no name
    defined twice). Block 19 adds to these checks exactly: one file outside block 17's Files to touch,
    .claude/scripts/tests/test_parent_branch_rule_text.py; and, inside block 17's Files to touch, the
    four-line deletion in contract-completion.md, the four README count lines and one appended JOURNAL.md
    entry. MECHANISMS.md and VOCABULARY.md are unchanged by block 19.
  - B1: in skills/pr-merged/references/contract-completion.md, section "The records pull request", the
    top-level steps (column 0; step 5a's indented sub-steps 1-6 are not top-level) read 1, 2, 3, 4, 5,
    5a, 6, 7, 8, 9, once each and in order. Steps 6-9 equal master's by git's view, never by raw bytes
    on disk (journal 2026-10-17): git diff 274bf1e <block 19 head> -- <path> shows no added or removed
    line that starts with "6. **", "7. **", "8. **" or "9. **", and every line it does show belongs to
    this contract's side. Step 5a is unchanged (git diff <block 19 base> <block 19 head> -- <path>
    removes exactly the four old step lines and adds none). "Cut the branch in a flat worktree"
    appears nowhere. Then read skills/flow/SKILL.md and skills/pr-merged/SKILL.md end to end for any
    other base text restored beside its rewrite (the t18 review did not), and report what you find.
  - W1: the four counts block 19 may change ("hooks/tests/", "scripts/" workflow scripts and helper
    modules, "scripts/tests/", "references/") are true against the tree, measured by you with block 19's
    counting rules. No other README line changed. Any other tree count you find false (such as "6
    generic data files", which depends on whether hooks.json counts) is reported as information and
    pointed at the follow-up stub, never as a finding against block 19.
  - Test: the step 5a test's section ends at "6. **Put the stable branch"; its assertions are
    unchanged. records_step_labels(text) is a module-level function that takes text, reads raw lines
    (not squash, flat or section) and counts only column-0 steps. The step-order test and the control
    exist and pass on head. Show the test fails on the pre-fix file by running, in PowerShell from the
    worktree root, with <block 19 base> = the parent tip block 19 was cut from:
    git show <block 19 base>:skills/pr-merged/references/contract-completion.md | py -3 -I -c "import sys; sys.path.insert(0, '.claude/scripts/tests'); import test_parent_branch_rule_text as t; print(t.records_step_labels(sys.stdin.read()))"
    Quote both outputs: the base lists 6, 7, 8 and 9 twice, so the step-order test's equality fails
    there; the same command with <block 19 head> lists each once.
  - J12: one entry appended after J11, before the closing lines, verbatim as block 19 states. No other
    registry line changed.
  - Scope: block 19's commits touch only its four files, plus the usual Work Item Brief bookkeeping
    commit (the t19 brief's front matter: pr:, issue_link:, status:), which is not a shipped file and is
    reported as a note, as t18 did for 4707150. Any other path is a finding. The t18 artefact and its
    .gate.json are unchanged since #224 (git diff on them is empty).
  - Not checked, by decision: the description of pull request #223 (no gate reads it and it does not
    ship). List it under What was NOT checked.
  - Second merge: run git fetch origin, then git merge-tree --write-tree --name-only <block 19 head>
    origin/master, and quote it. Report whether the landing's merge conflicts, and on which files.
  - Re-run, each as its own row with exit code and case count: test_pr_merged.py (alone); every
    .claude/hooks/tests/test_*.py except test_gate_cost.py, one row per suite; test_plugin_text_scans.py,
    test_registry_entries.py, test_repo_consistency.py, test_memory_boundary.py,
    test_memory_off_parity.py, test_plugin_manifests.py, test_auto_improve_finish_install.py,
    test_check_version_bump.py, test_parent_branch_rule_text.py, test_skill_script_lookup.py,
    test_cleanup_delivered.py; and the parent-mode version check. A failure that also fails on
    origin/master is reported as pre-existing, with the origin/master run quoted. No placeholder row:
    a suite that could not finish gets a row saying so, and that is a finding.
  - Six fixed sections; the file does not exist yet and you create it. The Scope section says
    "Supersedes: t18-review-merge-and-text-fixes-fullstack-code-reviewer.md". Verdict line alone,
    exactly one of: "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked".
    Write the Gate Output <artefact stem>.gate.json beside it, and set its supersedes field to
    ["t18-review-merge-and-text-fixes-fullstack-code-reviewer.md"]. Do NOT edit the t18 artefact and do
    NOT append to any registry yourself: report a missing append as a finding.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

---

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
