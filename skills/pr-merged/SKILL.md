---
name: pr-merged
description: "Tell the session that one or more pull requests have merged, then release the sub-tasks that were waiting on them. Verifies each pull request really merged by asking GitHub rather than trusting the claim, writes a completion record for the finished sub-task, recomputes which dependent sub-tasks are now unblocked, and continues with them. Use when: user says /pr-merged, 'PR 40 is merged', 'these PRs merged, continue', 'pick up what was waiting on #41', or returns to a session after merging work elsewhere. Reads and writes the orchestrator's plan, result and state stores; does not run the Contract Orchestrator scripts, which are gated as unimplemented."
user_invocable: true
---

# /pr-merged — record a finished sub-task and release what it was blocking

A contract decomposes into sub-tasks. A sub-task often waits for another one to land in the
default branch. Nothing watches for that landing. When the merge happens outside the session,
the waiting sub-tasks stay waiting until a person remembers them.

This skill is how you tell the session a merge happened. It confirms the merge really
happened, records the finished sub-task, works out what that unblocks, and continues.

```
/pr-merged 40 41
   verify merged (ask GitHub)  ->  map to sub-task  ->  write completion record
   ->  recompute released sub-tasks  ->  continue
```

## The three stores, and why they stay separate

This skill reads and writes the same stores the orchestrator design defines. They are kept
apart on purpose, and merging them would lose something each one carries.

| Store | Path | Holds |
|---|---|---|
| **Plan** | The contract's `## Implementation Handoff` blocks, or `.claude/orchestrator/plans/<contract-id>/task-map.yaml` when one has been generated | The sub-tasks: identity, scope, acceptance criteria |
| **Completion** | `.claude/orchestrator/results/<contract-id>/<task-id>.yaml` | One record per **finished** sub-task |
| **State** | `.claude/orchestrator/state/<contract-id>/state.yaml` | The live machine: which sub-task is pending, running, blocked or failed |

**The completion store is the durable one.** State is a working position and can be rebuilt.
A completion record is evidence that a specific sub-task finished, with the commit that
carries it. Releases are computed from completion records, never from the live state, because
state can be lost or stale and a record cannot.

### The completion record

One file per finished sub-task, in the shape the orchestrator design already defines:

```yaml
status: completed
commit: <full hash of the merge commit>
tests_passed: true
contract_impact:
  severity: none
  requires_architect: false
  description: null
```

This skill adds provenance, so a reader can tell a real merge from a hand-written record:

```yaml
completed_by: pr-merged
pull_request: <url>
merged_at: <timestamp GitHub reported>
verified: github
```

`verified: github` is the important field. It means the merge was confirmed by asking GitHub,
not asserted by a person. A record without it must not release anything.

## The rule that governs the whole skill

**A claim that a pull request merged is a request to check, never a fact.**

The user may be misremembering. A pull request may be closed without merging. It may have
merged into something other than the default branch. Writing a completion record on an
unverified claim releases dependent work that has nothing to build on.

Nothing here acts until GitHub has said it merged. This is the same discipline the
closing-link check in `/ship` uses, and for the same reason.

## Step 0: Parse the invocation

Accept any mix of these, separated by spaces or commas:

| Form | Meaning |
|---|---|
| `40`, `#40` | Pull request in the current repository |
| `https://github.com/<owner>/<repo>/pull/40` | May be another repository; respect the owner and name in the link |
| *(nothing)* | Discover candidates and let the user pick |

With no argument:

```bash
gh pr list --state merged --author @me --limit 20 --json number,title,mergedAt,headRefName
```

Present the list. Never act on all of it unprompted.

## Step 1: Verify each pull request really merged

```bash
gh pr view <number> --json number,state,mergedAt,mergeCommit,headRefName,baseRefName,url,closingIssuesReferences
```

Judge each against this table. The set is closed, and the first match wins.

| What GitHub reports | Verdict | Do |
|---|---|---|
| Merged, with a timestamp and a merge commit | `merged` | Continue with this one |
| State open | `not-merged` | Skip it, and say so. Write nothing |
| Closed, no merge timestamp | `closed-unmerged` | Skip it. Closed is not delivered |
| Merged, base is not the default branch | `merged-elsewhere` | **Halt this one and ask.** It landed on a branch, so dependents may still have nothing to build on |
| No such pull request | `not-found` | Skip it, and report the number |
| GitHub client missing or unauthenticated | `unverifiable` | **Halt the whole skill** |

**On `unverifiable`, stop everything.** Without GitHub there is no way to tell a merged pull
request from a closed one, and guessing writes a lie into the completion store. Tell the user:

```
winget install --id GitHub.cli
gh auth login
```

Do not install it yourself. Do not reach the GitHub interface with a token taken from the
environment.

## Step 2: Map each merged pull request to a sub-task

**First, load the sub-tasks.** Take them from whichever source exists, in this order:

1. A generated `task-map.yaml` for this contract, when one exists.
2. **The contract's `## Implementation Handoff` blocks.** Each `###` block is one sub-task.
   Its heading names it, such as Backend, Frontend or Data pipeline. Its
   `**Files to touch:**` list is its scope. This is the normal source today.

Then match each merged pull request to a sub-task, stopping at the first hit:

1. The head branch matches a sub-task's branch in the state store.
2. The head branch or the pull request title names the sub-task, such as `backend` or
   `frontend`.
3. **The files the pull request changed fall inside exactly one sub-task's
   `Files to touch` list.** This is the most reliable signal, because that list is the same
   one the concept gate enforces during implementation.

**A pull request that matches no sub-task is reported, never guessed at.** Say which number
could not be placed and carry on with the rest.

**A pull request that matches two sub-tasks** means an identifier is ambiguous. Halt that one
and show both rather than picking.

**If the contract has neither a generated plan nor handoff blocks,** say so and stop.
Do not invent a decomposition.

## Step 3: Write the completion record

For each merged pull request that mapped to a sub-task, write
`.claude/orchestrator/results/<contract-id>/<task-id>.yaml` in the shape above, with the merge
commit GitHub reported and `verified: github`.

**A completion record is append-only in spirit.** If one already exists for that sub-task,
do not silently overwrite it. Show both and ask. Two different commits claiming to finish the
same sub-task means either the work shipped twice or the mapping is wrong, and both need a
person.

Then update the state store to mark that sub-task completed, so the live position agrees with
the evidence.

## Step 4: Recompute which sub-tasks are released

For every sub-task with no completion record, work out what it depends on.

**Where dependencies come from.** A generated plan states them outright. Handoff blocks do
not, so derive them the same way `/design-first` already does when it dispatches: two
sub-tasks whose `Files to touch` lists **overlap** must run in order, and two whose lists are
disjoint are independent. Where the order is genuinely ambiguous, say so and ask rather than
picking one.

Then, for each dependency, look for a completion record carrying `verified: github`.

- **Every dependency has a verified record** → the sub-task is **released**.
- **Any dependency has no record** → it stays blocked. Name which dependency holds it.
- **A dependency names a sub-task not in the plan** → report it, and leave the sub-task
  blocked.

That last rule carries the weight. Treating an unresolvable dependency as satisfied is how a
gate stops gating while still looking like it works. That is the exact defect found in the
orchestrator's own gate, and this skill must not repeat it.

**Compute releases from completion records only.** Do not read the live state to decide a
release. State can be stale; a record is evidence.

## Step 5: Continue the released sub-tasks

Report the released set first, then act.

- **One sub-task released** → start it, using its scope and acceptance criteria from the plan.
  Run it through `/tdd-first` with the contract as its authority.
- **Several released** → list them and ask which to start. Each is a full implementation run.
- **None released** → say so, and name what each blocked sub-task still waits for. This is a
  normal and common outcome.

When every sub-task in the plan has a completion record, the contract's implementation is
done. Hand off to `/verify-before-done`, then `/ship`, rather than declaring it finished here.

## Step 6: Offer to clean up

A merged pull request leaves its branch and often a worktree behind. Offer once, and only for
branches this run verified as merged:

```bash
git worktree remove .claude/worktrees/<name>
git worktree prune
git branch -d <branch>
```

Never delete a worktree directory with a plain remove. That leaves stale metadata, and git
keeps the branch reserved.

## Step 7: Report

```
### PR-MERGED REPORT
- Verified merged: <number -> sub-task, one line each>
- Skipped: <number — verdict, one line each>
- Unmapped: <numbers that matched no sub-task>
- Completion records written: <paths>
- Released: <sub-tasks now unblocked, and what released them>
- Still blocked: <sub-task — waiting on X>
- Contract complete: <yes, hand to /verify-before-done | no, N sub-tasks remain>
- Cleanup: <removed, or offered and declined>
```

State what was skipped as plainly as what succeeded.

## What exists today, and what does not

**The decomposition usually already exists.** Contracts written from the standard template
carry an `## Implementation Handoff` section, with one block per implementer and a
`**Files to touch:**` list inside each. Each block is a sub-task with a name and a scope.
That is the plan this skill walks. In the project this skill was first written for, 132 of
146 contracts carried that section and 117 carried the file list, so expect most contracts to
be usable without any extra authoring.

What is missing is narrower than it first appears:

- **No generated `task-map.yaml` is produced.** The orchestrator's planner never parses the
  contract, so it always produces an empty graph. It looks for a `Task Decomposition`
  section, which no contract has. It does not read the handoff blocks, which nearly all
  contracts do have. That mismatch is the whole reason the plan store is empty.
- **No completion record has ever been written.** The store is created, its path is recorded
  in state, and two consumers read it. Nothing produces one. The intended producer was the
  task-executor session, which is never launched.
- **Both readers invent success when a record is absent.** The launcher's fallback returns a
  completed status with tests passed, citing whatever commit the worktree already sat on. The
  final reviewer treats a missing record as simulation mode and skips its check. So an empty
  completion store currently reads as a fully successful contract.

**This skill is the missing producer.** It writes the first real completion records, and it
takes its sub-tasks from the handoff blocks rather than waiting for a planner repair. The
plugin ships those seven orchestrator scripts but not their design notes or tests, so this
section and the gate in `/design-first` are the only record a fresh checkout has.

Two follow-ups belong to the orchestrator, not to this skill. The two fallbacks above should
be removed, or they will keep masking an empty store. The planner should read handoff blocks
rather than a section no contract writes.

**A separate note on the orchestrator's own gate.** Do not reuse its dependency check as a
model. Verified by testing it in a throwaway repository: the executor names task branches with
a date appended, the gate looks them up without one, and on that miss the loop's copy fails
open and releases the child anyway. A second copy of the same check in the launcher answers
the opposite on identical input. This skill computes releases from completion records instead,
which have no naming dependency at all.

## Anti-patterns (halt immediately)

- **Writing a completion record on the user's word alone.** Ask GitHub. Everything rests on
  this.
- **Treating a closed pull request as delivered.** Closed without merging is the opposite.
- **Treating an unresolvable dependency as satisfied.** That is the orchestrator's own defect.
- **Computing a release from the live state instead of completion records.** State goes stale.
- **Overwriting an existing completion record silently.** Two commits for one sub-task needs a
  person.
- **Inventing a sub-task graph** when the contract has no decomposition. Report it instead.
- **Guessing which sub-task a pull request belongs to.** Report the unmapped number.
- **Starting several released sub-tasks without asking.** Each is a full run.

## When NOT to use this skill

- A pull request you are about to open. That is `/ship`.
- A whole work item with no sub-tasks, which you want to resume. Invoke `/flow` with the brief.
- Checking what is in flight with nothing merged. That is `/list-contracts`.

## Skill integrations

- **Reads** the plan store, and **writes** the completion and state stores.
- **Hands released sub-tasks to** `/tdd-first`, with the contract as the authority.
- **Hands a finished contract to** `/verify-before-done`, then `/ship`.
- **Complements** `/ship`, which opens pull requests. This skill handles what happens after
  one merges.
- **Does not run** `.claude/scripts/execute_contract.py`.
