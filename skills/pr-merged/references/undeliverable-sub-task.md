## When a sub-task cannot be delivered

A pull request closed without merging is not a skip. It means the sub-task could not be
delivered as the contract specified it. So does an implementer that halts because the tests
cannot be made to pass.

**That is evidence about the design, not only about the code.** A sub-task nobody can build
means the decomposition was wrong. It goes to the architect, not to a failure report.

### Write a failure record, in the channel that already exists

The escalation channel is `contract_impact` with `requires_architect`, inherited from the
removed design because the shape was right. Use it rather than inventing a second path.

```yaml
status: failed
commit: null
tests_passed: unknown
tests_verified_by: none
contract_impact:
  requires_architect: true
  severity: <high | medium | low>
  description: <why this sub-task could not be delivered, in one or two sentences>
completed_by: pr-merged
pull_request: <url of the closed pull request>
verified: github
```

**Severity is about the blast radius on the contract, not on the sub-task.** High means other
sub-tasks are built on an assumption this failure disproves. Medium means this sub-task needs
respecifying and the rest stand. Low means the approach was wrong but the specification holds.

### A sub-task merged into the default branch on the web

In a contract with two or more mergeable blocks, a sub-task pull request should target the parent branch. The merge-direction check cannot stop one that is merged into the default branch on the web, and that is not an undeliverable sub-task: the work is done. This phase records it after the merge as an ordinary completion (status `completed`, `verified: github`, `base_is_default: true`) and closes its sub-issue. The layout is reported as a warning instead: `--status --json` lists `single-branch-delivery` in `layout_warnings`, with the remedy that this work is already on the default branch and is recorded as done, nothing needs undoing, and the remaining sub-tasks go through the parent branch (`/flow` Step 2.7, then `/advance`). The warning blocks nothing. A contract with a single mergeable block is unchanged: that merge completes the sub-task.

### Release nothing

**A failed sub-task releases none of its dependents.** They were going to build on work that
does not exist. Leave them blocked, and name the failed sub-task as what blocks them.

This is the one case where the blocked state is correct and must not be cleared by a person
calling this phase again. It clears when the contract is amended.

### Hand back an escalation, not a released set

The return is different in shape. Say that the sub-task failed, give the severity and the
description, and name every sub-task now blocked behind it.

The loop routes that to architect re-entry and pauses. A person is told the contract needs
amending, and that `/design-first` is where that happens.

### The three things the architect can decide

**The decomposition was wrong.** The contract is amended, the sub-tasks are respecified, and
the failure record stays as history explaining why.

**The sub-task was unnecessary.** It becomes a `no-work-required` completion, which releases
its dependents normally. The failure record is superseded, never deleted.

**The specification was right and the approach was wrong.** The same sub-task is retried. The
failure record stays, so a second failure on the same sub-task is visible as a pattern rather
than read as a first attempt.

### Tests that cannot pass never reach this phase

No pull request merges, so nothing calls it. That failure surfaces from the implementer
halting during `/tdd-first`. The record shape above is the same, and whoever is driving writes
it. This phase owns the closed-pull-request path only.
