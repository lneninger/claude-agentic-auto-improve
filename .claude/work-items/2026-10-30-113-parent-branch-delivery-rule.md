---
id: 113
issue_offer: pending
title: A multi-sub-task contract is always delivered through a parent branch, and the version is raised once at landing
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/113
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/113-parent-branch-delivery-rule
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261030-feature-113-parent-branch-delivery-rule
north_stars: none
contract: .claude/concepts/2026-10-30-parent-branch-delivery-rule.md
pr: none
issue_link: unknown
status: implementing
created: 2026-10-30
---

# A multi-sub-task contract is always delivered through a parent branch, and the version is raised once at landing

## Problem statement
How a contract with several sub-tasks is delivered (through a parent branch, or one pull request each straight to the default branch) is decided by nobody. Contract 84 went through a parent branch. Contract 86 was drafted for the default branch, because a critic blocker about the version check was fixed with a per-sub-task version raise, and the contract template, the architect, the critic and the status script all stay silent about it. The status script falls back to the default branch without reporting a defect. The user's decision, 2026-10-30: the layout must be a rule and not a decision, and the version is bumped once, after the default branch is merged into the parent branch, against the default branch.

## Acceptance criteria
From the issue's Acceptance section, restated as testable conditions:
- [ ] A contract with two or more sub-tasks cannot reach `Status: approved` through `/design-first` while it plans a version raise per sub-task, plans sub-task pull requests to the default branch, or names no parent branch.
- [ ] `pr_merged.py --status` reports a defect for a multi-sub-task contract whose parent branch cannot be found, and never reports the default branch as a sub-task base for it.
- [ ] The version is raised exactly once, at landing, computed against the default branch after the default branch has been merged into the parent branch; a sub-task pull request into the parent branch does not raise it. A single-block contract still raises it in its own pull request.
- [ ] The contract template, `data-architect`, `contract-critic`, `/design-first` and `/flow` Step 2.7 state the rule; each change has a test.
- [ ] Contracts 84 and 86 stay consistent with the rule (86's Rule V is amended in its own work item, not here).

## Out of scope
- Amending contract 86 or opening its sub-issues (issue 86 stays paused until this lands).
- Changing what a single-block contract does.
- Any other `/flow` behaviour.

## Known context
- Parent / epic: none (follow-up found while running `/flow` on issue 86)
- Related items: #86, #84
- Affected areas (best guess, to be confirmed by the contract): `.claude/templates/concept-contract.md`, `agents/data-architect.md`, `agents/contract-critic.md`, `skills/design-first/SKILL.md`, `skills/flow/SKILL.md`, `.claude/scripts/pr_merged.py` and tests, `.claude/scripts/check_version_bump.py`, `CLAUDE.md`
- Evidence in the issue body: `pr_merged.py` `effective_base` around line 1500; contract 84's nine briefs (`parent_issue: 84`, `base: feature/84-...`).

## North-star alignment
- none — the register holds no active thought (`.claude/north-stars/` does not exist)

## Open questions from intake
- Is "bumped after the merge against master" read as: merge the default branch into the parent branch, then compute and commit the single raise against the default branch, then land? → **Answer:** Assumption, recorded in the issue: yes. The contract carries it as an Open Question for the user to confirm at the gate.
- Does the rule need a user choice anywhere? → **Answer:** No. The user decided the layout is a rule; the contract must not offer a choice.

## Size
L — touches the contract template, two agents, two skills, the delivery script, the version check and the project rules; changes a rule that governs every multi-sub-task contract.

## Routing
non-trivial → /design-first

## Run log

Run of `/flow` on issue 113, 2026-10-30. Stopped at the review stage: the retry budget (two retries) is spent.

- **Intake and design:** brief written, contract drafted and attacked by three critic rounds, approved by the user with Q1 yes and Q2 refuse.
- **Test first:** failing tests written, then the implementation made them pass (version 0.11.0, 31 files across the delivery scripts, skills, agents, template, registry and manifests).
- **Review 1** (fresh code reviewer and test critic): no blockers in the code review, 7 warnings (W1 to W7); the test critic found 2 blockers (two R-7 evidence mutations survived, and the reader-parity test did not drive the real readers). W1 to W6 and the test findings were fixed test-first. **W7 was not fixed**: it is a contract defect and needs the user's decision (see below).
- **Review 2** (fresh reviewer on the fix commit): 3 warnings. F1 (W4 not truly fixed), F2 (landing P0 check ignored exempt contracts), F3 (wrong refusal text). Fixed test-first.
- **Review 3** (fresh reviewer on the final fix commit, `final-review-fullstack-code-reviewer.md`): **1 blocker, 2 warnings.**
  - **B1 `pr_merged.py` around 4251-4276 and 4519-4525:** when the fetch of the default branch fails or `origin/<base>` cannot be read, G-7 falls through silently. With `--accept-single-branch` it can write a delivery over a real parent-branch landing; without the flag it refuses and tells the owner to run the accept; `--dry-run` plans the accepted delivery. The live report then offers the plain `--record-delivery`, which breaks R-9. Fix: exit 10 `github-unverifiable` when the origin read is `None`, before the accept branch; the live report offers a re-read.
  - **W1 `pr_merged.py` around 2854-2864:** after the ref probe passes, a failed `ls-tree` or an unreadable record still reads as "origin holds no records". Fix: list with `ls-tree <ref> -- <folder>/`, return `None` on any failure.
  - **W2 `pr_merged.py` around 2845-2850:** `git fetch origin <base>` has no refspec, so in a narrowed clone `origin/<base>` can stay stale. Fix: `+refs/heads/<base>:refs/remotes/origin/<base>`.
  - Nits: set `GIT_TERMINAL_PROMPT=0` on the status fetch; an unreadable contract at landing P0 should stop as unverifiable; a padded `--default-branch` value.
- **Open:** code-review **W7** (an R-8 failed record plus guard G-3 leaves no exit for a sub-task pull request that was opened into the default branch before the upgrade). Needs a contract amendment decided by the user.
- **State at hand-back:** all work is committed locally on `feature/113-parent-branch-delivery-rule` (no push, no pull request). The suites last confirmed green on the final code: `test_pr_merged.py` 643 tests. The landing and cleanup suites were still running on it. Known old failures unrelated to this branch: `TestContainmentScanner` real tree (`skills/ship/SKILL.md` holds `gh pr merge`), and the brief-corpus and project-config suites.

### Run log, second hand-back (after the user approved one more fix cycle and the W7 amendment)

- **Done:** the contract was amended with R-10 (accepting an R-8 failure) and the B1/W1/W2 notes; failing tests were written, then the code, then the skill text. B1 (an unreadable origin), W1 and W2 from the previous hand-back are fixed.
- **Review 4** (fresh reviewer on the last fix commit, `last-review-fullstack-code-reviewer.md`): **2 blockers, 3 warnings, 7 nits.** Verdict: fix then ship.
  - **B-1 `pr_merged.py` around 4263-4309 and 4524-4547:** the R-10 accept leaves the sub-issue open, so the later landing reaches G-4; recording that pull request again with plain `/pr-merged` rewrites the accepted record as a failed R-8 record, which loops back to escalate. The row 6 tests use `sub_issues=[]`, so they never reach this path. Fix: close the sub-issue in the R-10 path, and do not treat a web merge as new when the existing record is an accepted one for the same pull request.
  - **B-2 `pr_merged.py` around 1803-1812 and 4263-4309, contract R-10 and row 6 (needs a user decision):** the user approved R-10 only for pull requests that merged before the upgrade. No code compares the merge time with an adoption time, and the amended contract does not state the limit. Because escalate now prints the accept for every R-8 failure, a web merge made after the upgrade gets a ready-made bypass command. Option (a): store an adoption time once, refuse with G-3 `merged-after-rule` when the merge is later, and print `/design-first` for those records. Option (b): re-approve the broader R-10 as written. The reviewer also recommends counting an accepted record as landing evidence only when it is `completed`, `base_is_default` is true and it carries the replacement note, and stamping `accepted_blocks` on the Contract Delivery Record.
  - **W-1 `pr_merged.py:2901`:** `git ls-tree <ref> -- <folder>/` depends on the folder the script runs from; from a subfolder it lists nothing, exits 0 and reads as "no records" (the W1 failure again). Use `--full-tree -z`.
  - **W-2 `pr_merged.py` around 4614-4632:** when origin cannot be read and a Records pull request is open, the pointer to it is lost and the reason blames GitHub.
  - **W-3 `pr_merged.py:4296`:** the accept overwrites the failure record; keep a structured `replaces` entry.
  - Nits: the accept command can print a command that G-5 refuses; the fetch side effects in read-only modes are undocumented; a missing contract file needs a restore remedy at P0; others are listed in the report.
- **Suites on the final code:** `test_pr_merged.py` (660 tests, per the test author), the landing suite and the cleanup suite were started in the background on the commit before this review; results were not collected when the run stopped.
- **State at hand-back:** everything is committed locally on `feature/113-parent-branch-delivery-rule`; nothing is pushed and no pull request is open.

### Run log, third hand-back (after the user approved the fix cycle with option (a))

- **Done:** the contract was amended again (R-10 limited to merges before `adoptedAt`, narrowed landing evidence and `accepted_blocks`); failing tests, then the code. B-1 (sub-issue left open, accept undone by re-recording), W-1 (ls-tree depending on the folder), W-2 and W-3 of the previous review are fixed. `test_pr_merged.py` 686 tests passed and ten further suites exited 0 per the implementer.
- **Review 5** (fresh reviewer, `r10-review-fullstack-code-reviewer.md`): **1 blocker, 2 warnings, 6 nits.** Verdict: fix then ship.
  - **B-1 `pr_merged.py` around 3574-3584, 4058-4059, 4289-4295, 4649:** `read_adoption` returns None for a rule-adoption file that is absent, unparsable (conflict markers, an empty file from an interrupted write) or holds a non-timestamp. None means "now", so every earlier R-8 merge becomes acceptable and the file is then overwritten. This is a fail-open in the limit itself. Fix: a present-but-unreadable file is unverifiable (exit 10, print `/design-first`, never write); stamp `adopted_at` inside each R-8 failed record and use the earliest value.
  - **W-1 (needs a user decision):** adoption is anchored on each contract's first R-8 write, so every contract's first batch of web merges is always accepted, which voids the "only merges before the upgrade" limit for exactly the cases that matter. Options: (a) a repository-wide anchor, the earliest of repo and contract; (b) adopt on the contract's first writing run of any kind; (c) keep it and record the acceptance.
  - **W-2:** the adoption instant is read only locally; origin is ignored and the write is not an exclusive create, so a stale worktree or two sessions can each set their own.
  - Nits: bind `replaces` to its record, `--dispatch` can write adoption, `build_delivery_set` does not skip the adoption file, and others in the report.
- **Pattern:** every fix cycle since the W7 amendment has found a new defect in the R-10 exit or its adoption-time limit, while the rest of the rule (layout, parent branch, single version raise, fail-closed origin read, G-7 accept for legacy shapes) has been clean in the last two reviews. Reviewer 5 confirmed B-1, W-1 and W-2 of review 4 are fixed.
- **Not run on the final code:** `test_land_contract.py` and `test_cleanup_delivered.py`; Claude Code stopped them earlier for low memory. Last results on an earlier commit: landing 305 tests with one old unrelated failure (`gh pr merge` text in `skills/ship/SKILL.md`); cleanup 126 passed.
- **State at hand-back:** everything is committed locally on `feature/113-parent-branch-delivery-rule`; nothing is pushed and no pull request is open.
