---
id: 221
issue_offer: opened
title: Review merge and text fixes
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/221
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t18-review-merge-and-text-fixes
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/224
issue_link: deferred
status: shipped
created: 2026-11-03
---

# Review merge and text fixes

## Problem statement
Sub-task 18 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 18. Review merge and text fixes (`fullstack-code-reviewer`)

**Depends on:** 17

**Files to touch:**
- `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t18-review-merge-and-text-fixes-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review block 17 and write the review artefact.
CONTEXT: concept contract at .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md (Revision 8, block 17)
FILES: .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t18-review-merge-and-text-fixes-fullstack-code-reviewer.md
CONSTRAINTS:
  - Start from a cold context. Name base..head (the parent tip before the merge, and block 17's head).
  - Merge: for JOURNAL.md, MECHANISMS.md and VOCABULARY.md, every entry heading of git show
    origin/master:<path> and of the pre-merge parent tip is present exactly once, unedited, master's
    first; no conflict marker in any file. Files in block 17's Files to touch are judged on content.
    Every OTHER file the merge commit changed against the parent tip carries no hand edit, judged by git
    blob ids, not bytes on disk:
    - a file only master changed (the manifests included) is identical to its version in the master
      commit that was merged;
    - a file both sides changed and git auto-merged (pr_merged.py, test_pr_merged.py,
      skills/flow/SKILL.md, skills/pr-merged/SKILL.md) is identical to the same path in the tree that
      git merge-tree --write-tree <pre-merge parent tip> <merged master commit> prints. It cannot equal
      origin/master, because it holds both sides.
    No name is defined twice in pr_merged.py or test_pr_merged.py.
  - Text fixes: W1, I1/I2 (one Correction sub-bullet, append-only), I3 (in both README.md and
    skills/auto-improve-finish-install/SKILL.md), and I5 read as block 17 states. The JOURNAL.md
    entries are exactly J1-J11, in that order and in the Step 3 shape. Every README count is true
    against the merged tree and the suites' own output.
  - Re-run the suites block 17 lists (including test_parent_branch_rule_text.py,
    test_skill_script_lookup.py and test_cleanup_delivered.py) and the parent-mode version check; quote exit codes; a failure
    that also fails on origin/master is reported as pre-existing.
  - Six fixed sections; the file does not exist yet and you create it. Verdict line alone, exactly one
    of: "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked". Write the Gate
    Output <artefact stem>.gate.json beside it. Do NOT append to any registry yourself: report a missing
    append as a finding.
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
