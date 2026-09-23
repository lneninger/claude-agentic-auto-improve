---
name: pr-merged
description: "The closing phase of one sub-task: once its pull request has merged, record the completion and work out which pending sub-tasks that releases. Verifies the merge by asking GitHub rather than trusting the claim, writes a completion record stamped verified: github, recomputes the released set, and hands that set back to its caller. Iteration belongs to /advance, not to this phase. Use when: the loop closes a sub-task, or a person says /pr-merged, 'PR 40 is merged', 'these PRs merged, continue', or returns after merging work outside a running loop. Reads a contract handoff plan and writes the result and state stores."
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

## The logic lives in a script — this file is the human front door

### Finding the script, under either install mode

The script ships with the plugin **and** with a vendored copy, but it sits at a different
place in each. Resolve it once, then use the result:

```bash
PRM=$(ls .claude/scripts/pr_merged.py          "$CLAUDE_PLUGIN_ROOT/.claude/scripts/pr_merged.py"          ~/.claude/plugins/cache/*/agentic-auto-improve/*/.claude/scripts/pr_merged.py          2>/dev/null | head -1)
```

A vendored project finds the first. A plugin install finds one of the others. **If `PRM` comes
back empty, stop and say so** — the loop's every rule lives in that file, and a skill that
cannot find it can only guess at what it says.



**One implementation, two front doors.** A skill is instructions for a model, and the
caller may be a program rather than a session, and a program cannot invoke a skill. Both call the same
script instead, and both therefore behave identically. Two implementations of these rules
would drift the moment either changed.

```bash
py -3 "$PRM" --contract <slug|path> --pr <n> [--pr <n> ...] --json
py -3 "$PRM" --contract <slug|path> --status --json   # read-only
```

This follows the pattern already used here: `/ship` shells out to `verify_issue_link.py`, and
`/design-first` to `derive_area.py`. The script owns the rules. This file explains the result
to a person and offers what to do next.

**The script is covered by tests** at `.claude/scripts/tests/test_pr_merged.py` — 226 cases over
identity, parsing, block classification, verdicts, records, releases, conflict detection, the
Hand-Resolved Summary, the Next Command and the Sub-Task Cycle. Measured by running
`py -3 .claude/scripts/tests/test_pr_merged.py` and reading its own `unittest` summary line:
`Ran 226 tests ... OK`. They were mutation-probed: disabling the verification check, reading a
missing dependency line as none, and counting scope notes as sub-tasks each turn the suite red.

**Read the script's output rather than re-deriving it.** Everything below describes what the
script does and how to act on what it returns. Where this file and the script disagree, the
script is what runs, and the disagreement is a defect in this file.

## Where this sits — a phase, not a loop

**This skill does not iterate. It closes one sub-task and hands back.**

Three levels run this project's work, and each owns exactly one thing:

| Level | Owner | Owns |
|---|---|---|
| Outer chain | `/flow` | One work item, from intake through to shipped |
| Inner loop | `/advance` | Iterating the pending sub-tasks, one step per merge |
| Sub-task phase | **this skill** | Closing out one sub-task once its work has merged |

A sub-task's life runs: implement, test, review, verify, commit, open a pull request, merge.
**This skill is what happens after that merge.** It records the completion, works out what the
completion releases, and returns that set to whoever called it. Choosing what runs next, and
starting it, belongs to the loop.

That separation is the point. If this skill also decided what to run next, there would be two
things competing to drive iteration, and they would disagree the moment either changed.

### Two ways it is invoked

Both are triggered by a session, not by a background process. Nothing calls this phase on its
own, because nothing watches for a merge. The difference is who is driving.

**`/flow` is driving.** It is carrying a work item and a merge just landed. The phase verifies,
records, recomputes and returns the released set. It asks nothing, because `/flow` already
holds the authority the operator gave it, and it continues with `/advance`.

**A person is driving.** They merged something, possibly after resolving a conflict, and came
back to say so. The phase does exactly the same four things. The only difference is the ending:
it reports the released set and points at `/advance` rather than continuing by itself.

**The work in between is identical.** Verification, the record and the release computation do
not care who called them. Only the handoff differs.

**Neither path iterates.** This phase closes one sub-task. `/advance` starts the next. A person
merging is what joins them, which is why a merge-gated contract cannot run unattended.

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
| Merged, base is not in the declared base set | `merged-elsewhere` | **Halt this one and ask.** It landed on a branch nobody declared, so dependents may still have nothing to build on |
| No such pull request | `not-found` | Skip it, and report the number |
| GitHub client missing or unauthenticated | `unverifiable` | **Halt the whole skill** |

**The declared base set** is the repository default branch plus every sub-task's own declared
base already on record in the state store. Under this contract's topology, every task pull
request merges into a parent branch rather than the default branch, so a merge landing there is
`merged`, not `merged-elsewhere` — the measured PR #173 defect this rule exists to close.
`merged-elsewhere` stays reachable for a base that is genuinely undeclared: nobody said the
dependents could build on that branch.

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

Verified on this repository: pull request #126's merge commit reports no resolved files, while
a merge commit inside its branch reports fourteen.

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
detectable. Say that plainly rather than reporting a clean result. This repository merges with
merge commits, so the check applies here.

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

## Step 2.5: Close the sub-issue, once the merge is confirmed

**Only for a sub-task that carries a sub-issue.** Under this contract's topology a task pull
request merges into its parent branch, so GitHub's own keyword auto-close never fires for it —
the resolved link and the closing action are two different things. This step is what performs
the closing action `/ship` cannot: `/ship`'s own hard rule is *never* `gh issue close` by hand,
because for a pull request based on the default branch the resolved link is the honest closing
moment. That rule does not cover a task pull request based on a parent branch, and this step is
the scoped exception, gated on a GitHub-confirmed merge, never on a local belief.

**Read before you close (I-10). Never close on a local belief that a pull request merged.**

1. `gh pr view` must already have reported this pull request MERGED — Step 1's own verification,
   never re-derived here.
2. `gh issue view <sub> --json state` — read the sub-issue's own state first, and only then decide:
   - Already `CLOSED` → record `sub_issue_closed: already-closed` and do nothing further. This is
     what makes a re-run idempotent, and it is also what happens harmlessly if two runs race, or
     if GitHub ever does close the issue itself once the parent branch reaches the default branch.
   - `OPEN` → `gh issue close <sub> --reason completed --comment "<pull request url>"`, then
     re-read the state and record `closed` or `close-failed`.

**Never close a sub-issue without first reading its own state.** A close call issued on the
strength of "the pull request merged" alone, without the read in step 2, is exactly the anti-
pattern this step exists to prevent.

## Step 3: Write the completion record

For each merged pull request that mapped to a sub-task, write
`.claude/orchestrator/results/<contract-id>/<task-id>.yaml` in the shape above, with the merge
commit GitHub reported and `verified: github`. **The record's shape gains `sub_issue_closed`**,
carrying Step 2.5's outcome (`already-closed` | `closed` | `close-failed` | `unverifiable`). The
key is **omitted entirely** when no closure was attempted — a sub-task with no sub-issue, or a
merge that never reached Step 2.5 — exactly as `review_verdict` is omitted when nothing was read.

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

- **One or more released** → name them, and offer `/advance`, which takes the next step.
  Do not start a sub-task from here; `/advance` owns dispatch.

**When every sub-task has a completion record,** hand off using the script's own `next_command`
— printed verbatim, never re-derived here (Step 7 below). Today that command is always
`/verify-before-done`; `/ship` follows verification. Do not declare the contract finished from
here. Completion
of the last sub-task is a fact this phase can report. Whether the contract is done is a verdict
that belongs to verification.

For a contract with two or more mergeable sub-tasks, the end of the contract is also its
**parent** pull request, not any sub-task's own. The rule that the parent must not be marked
ready while any child issue is still open (the topology contract's I-12) is not enforced by any
step yet, so the operator must confirm every sub-issue is closed before marking the parent pull
request ready.

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

**Render every entry in the JSON report's `hand_resolved` list by printing its own `reading`
field verbatim — never collapse it, and never derive a reading yourself from `merge_commits`
and `files`.** `pr_merged.py`'s `_render_hand_resolved_reading` computes the reading once and
stamps it onto every entry — a seeded stored-record entry, a not-recorded placeholder, and an
entry measured this run alike — before either of its own output branches reads it. Re-deriving
the same reading here would be a second implementation of the same rule, which is exactly the
drift Alternatives Considered rejects; it also risks disagreeing with the script's own wording,
which is the overclaim the Hand-Resolved Summary exists to prevent.

For reference only, never as a decision rule to re-derive, `reading` is always one of four
shapes:

- `not-recorded` — a completion record written before this field existed, or a stored
  `hand_resolved` value the script could not read (hand-edited or partially-migrated)
- `not detectable (...)` — nothing was genuinely inspectable: zero, missing or otherwise
  malformed `merge_commits`, or a `files` value the script could not read as a list of strings
- `clean` — at least one merge commit was inspected and none was conflicted
- the comma-separated file list — files differing from both parents of an inspected merge
  commit, resolved by hand or changed during the merge

Print each entry as `<sub-task>[ #<pr>]: <reading>` (`h.get("reading")`), naming the pull
request only when the entry carries one — a seeded or not-recorded entry does not.

**The closing line is the script's own `next_command`, printed verbatim — never composed
prose.** `report["next_command"]["commands"]`, joined by `", then "`, or, when that list is
empty, `"none — " + report["next_command"]["reason"]`.

```
### PR-MERGED REPORT
- Verified merged: <number -> sub-task, one line each>
- Skipped: <number — verdict, one line each>
- Unmapped: <numbers that matched no sub-task>
- Contract defects: <block id — reason (files-but-no-recognised-agent | no-files-but-names-an-agent), one line each | none>
- Hand-resolved: <sub-task[ #pr] — <entry's own `reading` field, printed verbatim>, one line each | none>
- Completion records written: <paths>
- Review verdicts: <sub-task — pass | pass-with-findings | blocked | unreadable, one line each | none read this run>
- Released: <sub-tasks now unblocked, and what released them>
- Still blocked: <sub-task — waiting on X>
- Failed: <sub-task — severity, one-line reason, and what it now blocks | none>
- Contract complete: <yes — /verify-before-done, printed verbatim by the script (for two or more mergeable sub-tasks, the end-of-contract hand-off is the parent pull request; confirm every sub-issue is closed before marking it ready — I-12 is not enforced by any step yet) | no, N sub-tasks remain | blocked on architect re-entry>
- Cleanup: <removed, or offered and declined>
- Next command: <report["next_command"], rendered exactly as the rule above says>
```

State what was skipped as plainly as what succeeded.

## The stores, and the design that defined them

This phase writes to `.claude/orchestrator/results/` and `state/`, and reads a plan. Those
paths come from an earlier subsystem that specified three stores and never filled any of them.

**That subsystem's scripts were removed on 2026-09-14.** Its planner never parsed a contract
and no session was ever launched, so the completion store was created, read in two places, and
never written to once. Both readers invented success when they found nothing.

The store names are kept because the design behind them was right: a plan of sub-tasks, one
durable record per finished sub-task, and a working position rebuilt from those records. This
phase is the producer that store never had.

Its design record stays under `.claude/orchestrator/`, with a README saying plainly that it is
a record rather than running code.

**Do not model this phase's dependency check on the removed one.** That gate failed open: the
executor named a branch with a date appended, the lookup omitted the date, and on the miss it
released the child anyway. This phase computes releases from completion records, which carry
no naming convention to get wrong.

### Where the sub-tasks come from

Contracts written from the standard template carry an `## Implementation Handoff` section, with
one block per agent — implementer and review gate alike — and a `**Files to touch:**` list inside
each. **That list is what makes a block a sub-task, not who is assigned to it.** A review gate
declares its artefact and is waited on for a merge exactly as an implementer is. A block naming
an agent with no file list is a contract defect that halts the plan. That is the plan this phase
walks, and it needs no planner to produce it.

The removed planner looked for a `## Task Decomposition` heading instead, which no contract
ever wrote. That mismatch is the whole reason its plan store stayed empty.

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
- **Closing a sub-issue on a local belief that a pull request merged.** Step 1's GitHub
  verification must already have confirmed the merge before Step 2.5 runs.
- **Closing a sub-issue without first reading the issue's own state.** I-10's read-before-close
  ordering is what makes a re-run idempotent; skipping it risks a redundant mutation and a
  comment posted twice.
- **Rendering a zero `merge_commits` count as "none detected" or "clean".** It means nothing
  was inspectable, not that nothing was found — the exact overclaim the Hand-Resolved Summary's
  three-field shape exists to prevent.
- **Collapsing the four hand-resolved readings into a bare file list.** An empty list from a
  genuinely clean merge and an empty list from an uninspectable one are different claims; render
  both distinctly.
- **Composing the closing "next command" line as prose.** Print `report["next_command"]`
  verbatim — a second implementation of a rule the script owns is how the two drift.

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
- **Hands a finished contract to** `/verify-before-done` — the script's printed `next_command`,
  whatever the sub-task count; `/ship` follows verification. For a contract with two or more mergeable
  sub-tasks, the end-of-contract pull request is the parent one; confirming every child issue is
  closed before marking it ready is on the operator today, since the topology contract's I-12
  children-still-open gate is not implemented by any step (see
  `.claude/concepts/followups/2026-09-23-complete-move-routes-parent-pull-request.followup.md`).
- **Complements** `/ship`, which opens pull requests. This skill handles what happens after
  one merges.
- **Implemented by** `.claude/scripts/pr_merged.py`, which the loop calls directly.
- **Does not depend on** the removed orchestrator scripts; its design record is at
  `.claude/orchestrator/`.
