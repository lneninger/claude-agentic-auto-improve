---
id: 227
issue_offer: opened
title: Fix merged records steps and tree counts
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/227
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t19-fix-merged-records-steps-and-tree-counts
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

# Fix merged records steps and tree counts

## Problem statement
Sub-task 19 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 19. Fix merged records steps and tree counts (`python-ai-developer`)

*Revision 9 (2026-11-03), a fix sub-task.* Revision 9 is approved by the user on 2026-11-03, including Question 33. The user accepted the recommendations of Open Questions 29-32 and asked for the eight `## Critique (Revision 9)` warnings to be folded in; blocks 19 and 20 carry both. Question 33 (the manifest descriptions) changes neither block. `Status` stays `approved` in the header for the blocks already delivered. It adds no data shape, mechanism or term. Blocks 1-18 keep their identities and records, and block 18's `blocked` artefact stays as recorded.

**Why.** Block 17 merged (#223), and its review, block 18 (#224, `.claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t18-review-merge-and-text-fixes-fullstack-code-reviewer.md`), returned `**Verdict:** blocked`. The landing (`land_contract.py`) then halted at gate P3. The review found the merge otherwise exact, with one blocker and one warning:
- **B1 (blocker).** In `skills/pr-merged/references/contract-completion.md`, the hand resolution kept both sides of the conflict hunk whole. The parent side was step 5a followed by the base's unchanged steps 6-9; the `master` side was master's rewritten steps 6-9. So the merged file holds the base's old steps 6-9 (first line "6. **Cut the branch in a flat worktree.**", last line "9. **Remove the records worktree.** Then name the copies left in the starting tree ...") right after step 5a, then master's steps 6-9 (first line "6. **Put the stable branch in a flat worktree.**"). The old step 6 cuts the records branch from `origin/<default>`, which master's step 6 and `skills/pr-merged/SKILL.md` ("One stable branch, added to and never re-cut") forbid. Confirmed on 2026-11-03 in the landing worktree, at lines 89-92 then 93-96; the line numbers are not the locator.
- **W1 (warning).** Four folder-tree counts in `README.md` are false against the merged tree. The merge did not cause them; both sides and the merge base had them already. Measured on 2026-11-03 in the landing worktree:

  | Tree line | README says | Tree has |
  |---|---|---|
  | `hooks/tests/` | 9 hook test suites | 23 `test_*.py` files |
  | `scripts/` | 15 workflow scripts, 3 shared helper modules | 23 workflow scripts and 3 helper modules (`_claude_paths.py`, `_contract_files.py`, `_contract_index.py`) |
  | `scripts/tests/` | 11 suites | 36 `test_*.py` files |
  | `references/` | 2 reference documents | 3 files |

- **Found while drafting this revision.** `test_parent_branch_rule_text.py` (class `CaptureAtDeliveryTextTests`, the step 5a test) ends step 5a's section at the heading `6. **Cut the branch`, which is the line B1 deletes. The test's `section` helper runs to the end of the file when the end heading is absent, so the test would still pass but would no longer pin step 5a alone. The end marker has to move.

**Decided, not fixed here (Critique Revision 9).**
- **The other tree counts.** Block 19 changes only the four counts W1 names, and block 20 judges only those four (critic WARN 5). The tree's other counts are reported by block 20 as information, never as a finding against block 19. Why not widen block 19 instead: the next suspect, "6 generic data files" in `.claude/hooks/`, depends on whether `hooks.json` counts as a data file. The folder holds six `.json` files, but `hooks.json` has its own tree line, which leaves five. That is a counting rule to decide, not a fact to correct, so it goes to the follow-up stub with the tree-count pin.
- **t18 I1, the manifest descriptions** ("28 skills", 14 agents; the tree has 33 and 15). Neither block can fix them, because a sub-task never lists a version file. The landing does not fix them either, despite what block 11 says (see the Revision 9 correction there). Who fixes them is Open Question 33; the stub records it.
- **Pull request #223's description**, which t18 did not check. Dropped by decision: no gate reads it, it does not ship, and the record of what block 17 did is its commits and the t18 artefact. Block 20 lists it under What was NOT checked.

**What the t18 review recorded beyond its artefact (Open Question 29).** The t18 artefact was committed with the placeholder row `SUITES_PENDING` in Evidence and the bullet "The hook suites under `.claude/hooks/tests/`: see Evidence for what finished" under What was NOT checked. The reviewer's hand-back gave the missing rows: `test_skill_script_lookup.py` 29 OK; `test_cleanup_delivered.py` 126 OK (1 skipped); `test_pr_merged.py` 761 OK; `test_auto_improve_finish_install.py` 344 run with 5 failures (`TestLauncherFallbackNote` 1, `TestLauncherSurfaceMissingRefusal` 4), which also fail on `origin/master` and so are pre-existing; and 22 hook suites exited 0. They are recorded here. The t18 artefact is not edited: block 20's artefact supersedes it and carries the full table.

**A second hand merge is not planned.** After block 17, the parent branch's manifests equal 274bf1e's, so master's version change in 0061212 is a one-sided change and merges without a conflict. The t18 review (I2) found that master's commits after 274bf1e touch no registry, no `README.md` and no file block 17 resolved by hand. The same must hold for the two files block 17 text-fixed after the merge, `CONTRIBUTING.md` and `skills/auto-improve-finish-install/SKILL.md`. That fact is unverified by this contract (no shell), so block 19 checks it before editing, and block 20 runs `git merge-tree` against `origin/master`. If either finds an overlap, the contract is amended first, with the Revision 8 remedy pattern. The landing then merges `master` again and raises the version to **0.15.0** while `master` is on 0.14.

**Deferred (Open Question 30).** Pinning the README folder-tree counts in `test_repo_consistency.py` (F2) goes to `.claude/concepts/followups/2026-11-03-readme-tree-counts-and-step-pins.followup.md`, `**Issue:** pending`.

**Main-session actions, outside any block:**
- Fast-forward the parent worktree to `origin/feature/memory-client-and-cloud-engineering` before committing this amendment. The local branch was at fdd7640 when Revision 9 was drafted and did not yet hold #223 or #224. The amendment touches only the contract and the new stub, and neither of those merges changed them.
- Append the t18 reviewer-verdict line (t18 Disposition item 5) to `~/.claude/logs/reviewer-verdicts.jsonl`.
- Open the tracking issue for the new stub (`/design-first` Step 3.4), and the two sub-issues and briefs for blocks 19 and 20, as commit fdd7640 did for Revision 8.
- `contract-critic` ran on Revision 9 (`## Critique (Revision 9)`, warnings only). The user had its eight warnings folded in on 2026-11-03.

**Depends on:** 17

**Files to touch:**
- `skills/pr-merged/references/contract-completion.md`
- `README.md`
- `.claude/registries/JOURNAL.md`
- `.claude/scripts/tests/test_parent_branch_rule_text.py`

No version file is listed: the landing raises once (Parent Branch Delivery Rule). `JOURNAL.md` is a shipped registry, and its append rides here for the same reasons as J1-J11 in block 17.

**Pre-written TASK block:**
```
TASK: On the sub-task branch (cut from origin/feature/memory-client-and-cloud-engineering, which holds
  #223 and #224), fix the t18 review's B1 and W1, fix the step 5a test's end marker, pin the step order,
  and append the journal entry J12. One commit.
  Pre-check (before any edit):
  - git fetch origin, then git diff --name-only 274bf1e origin/master, and quote the output (274bf1e is
    the master commit block 17 merged). Stop list: any file in Files to touch; JOURNAL.md, MECHANISMS.md,
    VOCABULARY.md; CONTRIBUTING.md and skills/auto-improve-finish-install/SKILL.md (block 17 text-fixed
    them after the merge). If the output lists a file on the stop list, stop and report it, editing
    nothing: the contract must be amended first (a second hand merge may be needed).
  B1, skills/pr-merged/references/contract-completion.md, section "The records pull request":
  - Delete the four lines of the first steps 6-9 that follow step 5a. Locate them by text, not by line
    number: they start with "6. **Cut the branch in a flat worktree.**", "7. **Copy exactly that union
    of `written_files` there**", "8. **Open a draft pull request**" (the FIRST such line, the one
    without "when no open pull request has") and "9. **Remove the records worktree.** Then name the
    copies left in the starting tree". Delete nothing else.
  - Afterwards: the section's top-level steps read 1, 2, 3, 4, 5, 5a, 6, 7, 8, 9, each exactly once and
    in that order. Steps 6-9 equal master's, judged by git's view, never by raw bytes on disk (journal
    2026-10-17; this worktree is Windows and line ends differ):
    git diff 274bf1e -- skills/pr-merged/references/contract-completion.md shows no added or removed
    line that starts with "6. **", "7. **", "8. **" or "9. **". Every line that diff does show belongs
    to this contract's side (step 5a, its sub-steps and code block, and the capture-question sentences
    in the records-step paragraph and the "Under /flow" paragraph). The commit's own diff
    (git diff HEAD~1 -- <same path>) removes exactly the four lines above and adds none. The phrase
    "Cut the branch in a flat worktree" appears nowhere in the file.
  W1, README.md, the folder tree (the block that lists skills/, agents/ and .claude/):
  - Rewrite the four counts by measuring the tree you are editing, not by copying the contract:
    "hooks/tests/" = number of test_*.py files in .claude/hooks/tests/; "scripts/" = number of .py files
    directly in .claude/scripts/ not starting with "_" (workflow scripts) and number starting with "_"
    (shared helper modules); "scripts/tests/" = number of test_*.py files in .claude/scripts/tests/
    (keep ", including the path-resolution suite"); "references/" = number of files in
    .claude/references/. On 2026-11-03 these measured 23; 23 and 3; 36; 3. If your measurement
    differs, write yours and say so in the hand-back. Change no other README line, including the
    tree's other counts (such as "6 generic data files"): they go to the follow-up stub.
  Test, .claude/scripts/tests/test_parent_branch_rule_text.py, class CaptureAtDeliveryTextTests:
  - In the step 5a test, change the section end heading from "6. **Cut the branch" to
    "6. **Put the stable branch". Change none of its assertions.
  - Add one module-level pure function, records_step_labels(text), which takes the file's text (a
    string, not a path) and returns the labels of the top-level steps in the section that starts at the
    line "### The records pull request" and ends at the next line starting "### ", in file order. It
    works on the raw text, line by line, and NEVER through squash, flat or section: those squash all
    whitespace, newlines included, and would merge step 5a's own sub-steps into the list. A top-level
    step is a line matching ^(\d+a?)\. \*\* in column 0 (no leading space). Step 5a's six sub-steps
    ("   1. **Read the candidates" to "   6. **No outcome of this step", after the code block) are
    indented by three spaces, so they are excluded; so is anything inside the ``` code block. Normalise
    "\r\n" to "\n" before splitting.
  - Add the step-order test in CaptureAtDeliveryTextTests: records_step_labels(self.read(self.CC))
    equals ["1", "2", "3", "4", "5", "5a", "6", "7", "8", "9"].
  - Add a control test that calls the same function on a short fixture string held in the test: a
    copy of the section's shape with a planted second "6. **" line is reported (the list is not equal),
    and the same fixture with an indented "   1. **" sub-step is NOT counted. A comment says the
    function takes text so that a reviewer can run it on a git show copy of an older file.
  - Run the function on the pre-fix file and quote the result. In PowerShell, from the worktree root:
    git show HEAD~1:skills/pr-merged/references/contract-completion.md | py -3 -I -c "import sys; sys.path.insert(0, '.claude/scripts/tests'); import test_parent_branch_rule_text as t; print(t.records_step_labels(sys.stdin.read()))"
    The pre-fix result lists 6, 7, 8 and 9 twice; the same command with HEAD lists each once.
  J12, .claude/registries/JOURNAL.md:
  - Append after the last entry (J11, "A \"fails the build\" claim must name the workflow that runs the
    check") and before the closing "---" and comment, verbatim from the t18 artefact's Disposition
    item 4:
    ### 2026-11-03 — When resolving a conflict hunk by keeping both sides, drop the base lines the other side rewrote
    - **Trigger:** post-impl divergence
    - **Source contract:** .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
    - **Lesson:** Before keeping both sides of a conflict hunk, diff each side against the merge base; lines one side left unchanged and the other side rewrote belong to the rewrite only, or the merge restores deleted text beside its replacement.
    - **Apply when:** a merge resolves a prose or procedure conflict "keeping both behaviours", especially numbered steps
    - **Tags:** merge, conflict-resolution, base-text, duplicate-steps
CONTEXT: concept contract, block 19 (Revision 9 note); the t18 review
  .claude/reviews/2026-11-01-memory-client-and-cloud-engineering/t18-review-merge-and-text-fixes-fullstack-code-reviewer.md
  (B1, W1, Disposition items 1, 2 and 4).
FILES: as listed.
CONSTRAINTS:
  - Edit only the four files listed. Do not edit the t18 review artefact or its .gate.json (Open
    Question 29). Do not edit MECHANISMS.md or VOCABULARY.md (the t18 review owes no append there).
  - Never edit plugin.json, .claude-plugin/plugin.json, .cursor-plugin/plugin.json or
    .claude-plugin/marketplace.json. The branch keeps 0.14.2; the landing raises once.
  - Registry text names no memory tool literally.
  - Run, and report the exit code and case count of: test_parent_branch_rule_text.py,
    test_skill_script_lookup.py, test_cleanup_delivered.py, test_pr_merged.py (on its own),
    test_registry_entries.py, test_repo_consistency.py, test_plugin_text_scans.py,
    test_plugin_manifests.py (one failure, "the version obeys the merge-base rule", is by design on a
    parent branch, as the t10 and t18 reviews recorded), and
    py -3 .claude/scripts/check_version_bump.py --base origin/feature/memory-client-and-cloud-engineering
    --default-branch master --head-ref <this branch>. Report the pre-fix and head output of the
    records_step_labels command above. A failure
    that also fails on origin/master is reported as such, with the origin/master run quoted, and is not
    fixed here.
  - Every command in a form that runs in PowerShell.
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
