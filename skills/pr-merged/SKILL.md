---
name: pr-merged
description: "The closing phase of one sub-task: once its pull request has merged, record the completion and work out which pending sub-tasks that releases. Verifies the merge by asking GitHub rather than trusting the claim, writes a completion record stamped verified: github, recomputes the released set, and hands that set back to its caller. Iteration belongs to the orchestrator loop, not to this phase. Use when: the loop closes a sub-task, or a person says /pr-merged, 'PR 40 is merged', 'these PRs merged, continue', or returns after merging work outside a running loop. Reads and writes the orchestrator plan, result and state stores; runs no orchestrator script."
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

## Where this sits — a phase, not a loop

**This skill does not iterate. It closes one sub-task and hands back.**

Three levels run this project's work, and each owns exactly one thing:

| Level | Owner | Owns |
|---|---|---|
| Outer chain | `/flow` | One work item, from intake through to shipped |
| Inner loop | The orchestrator | Iterating the pending sub-tasks of one contract |
| Sub-task phase | **this skill** | Closing out one sub-task once its work has merged |

A sub-task's life runs: implement, test, review, verify, commit, open a pull request, merge.
**This skill is what happens after that merge.** It records the completion, works out what the
completion releases, and returns that set to whoever called it. Choosing what runs next, and
starting it, belongs to the loop.

That separation is the point. If this skill also decided what to run next, there would be two
things competing to drive iteration, and they would disagree the moment either changed.

### Two ways it is invoked

**Called by the loop — the primary path.** The loop has a sub-task whose pull request merged.
It calls this phase with the contract, the sub-task and the pull request. The phase verifies,
records, recomputes, and returns the released set. The loop then iterates. It does not ask
the user anything, because the loop is already running under whatever authority started it.

**Called by a person — the recovery path.** Somebody merged work outside a running loop, or
no loop is running at all. They invoke `/pr-merged` with pull request numbers. The phase does
exactly the same four things. The only difference is at the end: with no loop to hand back to,
it reports the released set and asks whether to start any of it.

**The work in between is identical in both paths.** Verification, the record, and the release
computation do not care who called them. Only the handoff at the end differs.

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
tests_passed: <true | false | unknown — see below; never assume true>
tests_verified_by: <ci | local-run | none>
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

**`tests_passed` must never be asserted, only observed.** This phase watches a merge. It does
not watch a test run. Fill the field from evidence and name the evidence:

- `ci` — a status check on the merge commit reported success. Read it from the pull request.
- `local-run` — somebody ran the suite against the merge commit and said so.
- `none` — neither happened. Then `tests_passed` is `unknown`, not `true`.

**This repository has no continuous integration.** There is no workflows directory, so `ci` is
not available here today and `none` is the honest default.

**A resolved conflict invalidates any earlier result.** When a developer fixes a conflict, the
merged code differs from what the sub-task's tests ran against. Any pre-merge green is stale.
Say so in the record rather than carrying the old verdict forward.

**Releasing on `unknown` is a decision, not a default.** Report it plainly when handing back
the released set, so whoever acts on it knows the dependents are building on untested code.

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

**Called by the loop,** the input is a contract identifier, a sub-task identifier and a pull
request. Skip the discovery below; the caller already knows which sub-task this is.

**Called by a person,** accept any mix of these, separated by spaces or commas:

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
| Closed, no merge timestamp | `closed-unmerged` | **Not a skip.** The sub-task could not be delivered — see the failure section below |
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

## Step 1.5: Flag hand-resolved files in the pull request's history

A file resolved by hand during a merge was never tested in the form that landed. With no
continuous integration, it is the highest-risk content in the pull request. Find it and say so.

**Look at the history, not the merge commit.** GitHub refuses to merge a conflicted pull
request, so the pull request's own merge commit is clean by construction. The resolution
happened earlier, when somebody merged the default branch into their own to clear it.

Measured in the project this was written for: one pull request's merge commit reported no
resolved files, while a merge commit inside its branch reported fourteen.

```bash
gh pr view <number> --json commits --jq '.commits[].oid'
# then, for each commit that has two parents:
git show --cc --name-only --format="" <sha>
```

The combined diff lists only files whose content differs from **both** parents. A clean
automatic merge lists nothing. Anything listed was either a hand-resolved conflict, or a
change introduced during the merge that existed in neither side. Treat both the same way:
they entered the codebase without ever being reviewed as a normal diff.

**Report them, do not block on them.** Name the pull request, the merge commit and the files.
Releasing dependents on top is the caller's decision, and it should be an informed one.

**Where this does not work.** A squash or rebase merge produces no merge commit, so nothing is
detectable. Say that plainly rather than reporting a clean result. Check which merge style the project uses.

**What conflicts here in practice.** The files that collide most are the append-heavy shared
ones — the registries, the journal, and agent memories — not source code. A conflict in those
usually means a lost entry rather than broken behaviour, which is worth saying in the report so
the reader calibrates.

## Step 2: Map each merged pull request to a sub-task

**First, load the sub-tasks.** Take them from whichever source exists, in this order:

1. A generated `task-map.yaml` for this contract, when one exists.
2. **The contract's `## Implementation Handoff` blocks.** Each `###` block is one sub-task.
   Its heading names it, such as Backend, Frontend or Data pipeline. Its
   `**Files to touch:**` list is its scope. This is the normal source today.

**Sub-task identity is derived from the block, never stored twice.** It is
`t<ordinal>-<slug of the name>`, so `### 2. Backend (…)` is `t2-backend`. One identity names
three things: the branch `task/<contract-slug>/<id>`, the completion record
`<id>.yaml`, and the sub-task named in the pull request title.

Then match each merged pull request to a sub-task, stopping at the first hit:

1. The head branch is `task/<contract-slug>/<id>`. This is the normal case and it is exact.
2. The pull request title names the identity.
3. The state store records that branch against a sub-task.

All three are string matches against a derived identity. **There is no heuristic over file
lists,** because there no longer needs to be one — the branch carries the answer.

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

**Dependencies are read, never derived.** Every sub-task block carries a `Depends on:` line
holding either `none` or the ordinals it waits for. Read it. Do not infer ordering from
anything else.

**Never derive dependencies from overlapping file lists.** That was an earlier rule here and it
was wrong. Overlapping files mean two writers could clobber each other. They say nothing about
one thing needing another to exist first. Backend and frontend touch entirely different files,
and the frontend still needs the endpoint before it can call it, so the rule gets the most
common case in this project exactly backwards.

**A sub-task with no `Depends on:` line is a defect in the contract, not a sub-task with no
dependencies.** Report it and leave the sub-task blocked. Guessing `none` releases work that
may have nothing to build on.

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

## Step 5: Hand the released set back — do not iterate

This phase ends by returning three things: the sub-task it closed, the set that closing
released, and the set still blocked with what each is waiting for.

**What happens next depends on who called.**

**The loop called.** Return the sets and stop. Do not start a sub-task, do not ask the user
anything, and do not decide an order. The loop owns iteration, and it already holds the
authority it was started under. A phase that starts work behind its caller's back produces two
things driving the same queue.

**A person called.** There is no loop to hand back to, so report and offer:

- **One released** → name it, and offer to start it through `/tdd-first`, with the contract as
  its authority.
- **Several released** → list them and ask which to start. Each is a full implementation run.
- **None released** → say so, and name what each blocked sub-task is waiting for. This is a
  normal and common outcome, not a failure.

**When every sub-task has a completion record,** say that the contract's implementation is
complete and hand to `/verify-before-done`, then `/ship`. Do not declare the contract finished
from here. Completion of the last sub-task is a fact this phase can report. Whether the
contract is done is a verdict that belongs to verification.

## When a sub-task cannot be delivered

A pull request closed without merging is not a skip. It means the sub-task could not be
delivered as the contract specified it. So does an implementer that halts because the tests
cannot be made to pass.

**That is evidence about the design, not only about the code.** A sub-task nobody can build
means the decomposition was wrong. It goes to the architect, not to a failure report.

### Write a failure record, in the channel that already exists

The orchestrator already carries an escalation channel and reads it: `contract_impact` with
`requires_architect`. Use it rather than inventing a second path.

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
- Hand-resolved files: <pr -> merge commit -> files, or none detected, or not detectable (squash/rebase)>
- Completion records written: <paths>
- Released: <sub-tasks now unblocked, and what released them>
- Still blocked: <sub-task — waiting on X>
- Failed: <sub-task — severity, one-line reason, and what it now blocks | none>
- Contract complete: <yes, hand to /verify-before-done | no, N sub-tasks remain | blocked on architect re-entry>
- Cleanup: <removed, or offered and declined>
```

State what was skipped as plainly as what succeeded.

## What exists today, and what does not

**The decomposition usually already exists.** Contracts written from the standard template
carry an `## Implementation Handoff` section, with one block per implementer and a
`**Files to touch:**` list inside each. Each block is a sub-task with a name and a scope.
That is the plan this phase walks. In the project it was first written for, 132 of 146
contracts carried that section and 117 carried the file list.

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
- **Writing `tests_passed: true` because a merge happened.** A merge is not a test run.
  Record what was observed, and `unknown` when nothing was.
- **Treating a closed pull request as delivered.** Closed without merging is the opposite.
- **Treating a closed pull request as a skip.** It is a failed sub-task and it escalates.
- **Releasing dependents of a failed sub-task.** They would build on work that does not exist.
- **Deleting a failure record when the architect supersedes it.** A second failure on the same
  sub-task should be visible as a pattern.
- **Treating an unresolvable dependency as satisfied.** That is the orchestrator's own defect.
- **Computing a release from the live state instead of completion records.** State goes stale.
- **Overwriting an existing completion record silently.** Two commits for one sub-task needs a
  person.
- **Inventing a sub-task graph** when the contract has no decomposition. Report it instead.
- **Deriving a dependency from overlapping file lists.** Overlap means two writers could
  clash. It does not mean one needs the other first.
- **Reading a missing `Depends on:` line as `none`.** It is a contract defect. Report it.
- **Guessing which sub-task a pull request belongs to.** Report the unmapped number.
- **Starting several released sub-tasks without asking,** on the person-called path. Each is
  a full run.
- **Starting anything at all when the loop called you.** Return the sets and stop. Two
  things driving one queue will disagree the moment either changes.
- **Declaring the contract finished** because the last sub-task closed. That verdict belongs
  to `/verify-before-done`.

## When NOT to use this skill

- A pull request you are about to open. That is `/ship`.
- A whole work item with no sub-tasks, which you want to resume. Invoke `/flow` with the brief.
- Checking what is in flight with nothing merged. That is `/list-contracts`.

## Skill integrations

- **Reads** the plan store, and **writes** the completion and state stores.
- **Is a phase of** the orchestrator's loop, which owns iteration over a contract's
  sub-tasks. This skill closes one sub-task and returns; it never iterates.
- **Sits inside** `/flow`, which owns the outer chain for one whole work item.
- **Offers released sub-tasks to** `/tdd-first` on the person-called path only, with the
  contract as the authority.
- **Hands a finished contract to** `/verify-before-done`, then `/ship`.
- **Complements** `/ship`, which opens pull requests. This skill handles what happens after
  one merges.
- **Does not run** `.claude/scripts/execute_contract.py`.
