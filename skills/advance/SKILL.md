---
name: advance
description: "Move a contract forward by exactly one step. Asks the script what the next move is, then takes it: start the sub-tasks that are ready, escalate a failure to the architect, hand a finished contract to verification, or report what is blocked and why. Makes one move and stops, because a merge-gated loop suspends until somebody merges and /pr-merged wakes it. Use when: user says /advance, 'what is next on this contract', 'start the next sub-task', 'continue the contract', or after /pr-merged reports newly released sub-tasks. Never iterates on its own."
user_invocable: true
---

# /advance — move the contract one step

A contract decomposes into sub-tasks, and each one ends in a pull request somebody has to
merge. So the work cannot run start to finish on its own. It moves one step, then waits.

This skill takes that step.

```
/advance <contract>
   ask the script for the next move
   ->  dispatch what is ready     (start it, open a pull request, STOP)
   ->  escalate a failure         (architect re-entry)
   ->  hand a finished contract   (/verify-before-done)
   ->  report what is blocked     (and exactly what holds it)
```

## The rule that shapes everything here

**One move, then stop.** This skill never loops.

A merge-gated contract spends most of its life waiting for a person. The step that follows a
dispatch is a human merging a pull request, and nothing here can do that or wait for it. So
this skill acts once and hands back.

`/pr-merged` is what wakes it again. Somebody merges, that phase records the completion and
computes what it released, and `/advance` runs again to start the released work.

Between the two, that is the loop. Neither half iterates.

## Step 1: Ask the script, do not re-derive

### Finding the script, under either install mode

The script ships with the plugin **and** with a vendored copy, but it sits at a different
place in each. Resolve it once, then use the result:

```bash
PRM=$(ls .claude/scripts/pr_merged.py          "$CLAUDE_PLUGIN_ROOT/.claude/scripts/pr_merged.py"          ~/.claude/plugins/cache/*/agentic-auto-improve/*/.claude/scripts/pr_merged.py          2>/dev/null | head -1)
```

A vendored project finds the first. A plugin install finds one of the others. **If `PRM` comes
back empty, stop and say so** — the loop's every rule lives in that file, and a skill that
cannot find it can only guess at what it says.



```bash
py -3 "$PRM" --contract <slug|path> --status --json
```

The script owns every rule about sub-tasks, dependencies, records and readiness. It is covered
by 226 tests — measured by running `py -3 .claude/scripts/tests/test_pr_merged.py`, whose own
`unittest` summary line reads `Ran 226 tests ... OK` — and has been mutation-probed. **Read its
answer. Do not recompute it from the contract**, or there are two implementations of the same
rules and they will disagree.

The answer carries `next_move.action`, plus `dispatch` packets when there is something to start.

## Step 2: Take the move the script names

The action set is closed. Each one has exactly one response.

### `contract-defect` — a block cannot be delivered as written

**Checked before every other action, including `dispatch` and `nothing-planned`.** Report each
entry in `defects` with its block and its reason, then stop. Start nothing.

Two reasons exist. `no-files-but-names-an-agent` is a block that names somebody to do work and
declares no files, so it produces neither a diff nor a record and nothing could ever prove it
ran. `files-but-no-recognised-agent` is a block carrying real files whose agent matches no
entry in the project profile's `implementers` or `review-gates` slots — usually a typo, which
is why the block is still tracked rather than quietly dropped.

**The remedy is editing one line of the contract, not working around it here.** Do not invent
an agent, do not infer a file list, and do not skip the block and carry on with the rest.

This is checked first on purpose. A contract whose blocks are *all* malformed has no sub-tasks
at all, so asking "is anything planned?" first would answer `nothing-planned` about a contract
that declares nine defective blocks — which is the silent discard this action exists to end.

### `dispatch` — there is work ready to start

**Start it with the script, not by hand.** The branch, the state write and the readiness
re-check all belong to one command:

```bash
py -3 "$PRM" --contract <slug> --dispatch <sub-task-id> --json
```

It cuts the branch from a freshly fetched default branch, records the sub-task as
`awaiting-merge` with that branch in the state store, and returns the packet. It refuses with
`not-released` if the sub-task's dependencies have not landed, so a wrong identity cannot start
work that has nothing to build on. Add `--dry-run` to see the packet without cutting anything.


Each packet names the sub-task, its branch, its agent, its file scope, the pre-written TASK
block the architect wrote into the contract, the Sub-Task Cycle, and the sub-task's own
identity.

**The Sub-Task Cycle** — `cycle` (always exactly one stage, since this repository's
decomposition rule already splits a red stage and a green stage across two separate blocks,
each with its own pull request — decided by what the block DECLARES, never by who is assigned)
and `cycle_basis` (which declaration decided it).

**Render `cycle_basis` before dispatching**, so an operator can tell a stage the contract asked
for from an unphased stage the loop fell back to:

| `cycle_basis` | What decided the stage |
|---|---|
| `verdict-bearing` | the block's `Files to touch` names a path under `.claude/reviews/` |
| `declared-phase` | the block's own TASK block declares `phase: RED` or `phase: GREEN` |
| `no-declared-phase` | the block declared neither — the packet's `unphased` stage is the loop's own fallback, never a stage the contract asked for |

Each `stage["stage"]` is one of exactly four names — `review`, `red`, `green`, `unphased`. **Never
print a stage word the packet did not ship.**

**The sub-task's own identity** is read by the caller out of its state entry rather than
re-derived: `issue` (its own sub-issue number, or `null` when none is recorded yet — never the
parent's issue), `base` (the branch its branch and its pull request are cut from — the parent
branch for a Sub-Task Work Item, the default branch for an ordinary one), `brief` (the path to
its Work Item Brief), and `needs_issue` (true only once the contract declares two or more
mergeable sub-tasks and this one's `issue` is still `null`).

**One released sub-task** → start it. **Several** → list them and ask which. Each is a full
implementation run, and starting three at once spends a lot of work on the operator's behalf.

For the one being started:

1. **The branch already exists** — the dispatch command cut it and recorded it in state.
2. **Dispatch every stage of `cycle`, in order, as its own fresh subagent.** This project's own
   decomposition already splits red and green across two separate sub-tasks (Non-Goals), so
   `cycle` in practice carries exactly one stage — but the loop reads however many the contract
   declares, never a fixed count this prose assumes. For each stage, launch a **fresh subagent**
   of `stage["agent"]` — never this session — and give it exactly four things: the contract path
   (`packet["contract"]`), the packet's own pre-written TASK block (`packet["task_block"]`), the
   packet's file list (`packet["files"]`), and the branch (`packet["branch"]`).
   `stage["isolation"]` is always the constant `fresh-subagent`: that constant IS the isolation
   an operator used to have to produce by remembering to `/clear` between sub-tasks, and the loop
   now produces it by launching a new subagent per stage instead.
3. **Run `/ship`** to open a draft pull request for that sub-task, and only that sub-task. This
   stays in the main session and is unchanged — Non-Goals rules out the dispatched subagent
   opening its own pull request.
4. **Stop.** Report the pull request and say plainly that the contract now waits for a merge,
   and that `/pr-merged` is what continues it.

**A packet flagged `needs_agent` names no recognised agent.** Refuse it the same way. Say which
sub-task is missing one, and that its heading must name an agent from the project profile's
`implementers` or `review-gates` slots. Do not pick an agent that looks right — the packet is
JSON another model reads, and a guessed name sends real work to the wrong specialist.

**This refusal cannot arise from the loop's own dispatch, and that is deliberate.** A block whose
agent is unrecognised is already a defect, and defects are asked about before anything is
dispatched, so the earlier question always catches it first. The refusal is kept as a guard for a
packet built by hand — `build_dispatch` is public and a caller may construct one directly. Kept
rather than deleted on the operator's decision of 2026-09-16, recorded so nobody removes it as
dead code or re-derives the contradiction.

**A packet flagged `needs_issue` has no sub-issue recorded for it.** Refuse it — but say plainly
that, unlike `needs_agent` above, this refusal *does* arise from the loop's own dispatch. By the
time the script computes `needs_issue`, `--dispatch` has already cut the branch and written
`awaiting-merge` into the sub-task's state entry — both happen before the flag is even checked.
So "stop" here does not undo either one: the branch exists, and the next `--status` call reports
this sub-task as out for merge, waiting on a pull request that was never opened. Say which
sub-task is missing its sub-issue, and say this plainly rather than reporting a clean halt.

**The remedy closes the gap forward; it does not abandon the branch.** Create the sub-issue now
(the same `gh issue create --parent` form Parent-aware mode uses), then stamp it into the
already-dispatched sub-task's state entry:

```bash
py -3 "$PRM" --contract <slug> --record-subtask <sub-task-id> --issue <n> --base <base> --brief <brief>
```

(Run `/task` in Parent-aware mode first if this sub-task has no brief yet — `--record-subtask`
requires one.) Then continue on the branch `--dispatch` already cut: run `/tdd-first` and `/ship`
as normal. Do not re-dispatch; the branch and its `awaiting-merge` state already exist, and
dispatching again would cut a second branch for the same sub-task. Never link the pull request at
the parent issue, and never retarget it at the default branch — both are forbidden by name in the
work item: the sub-issue is this task's own, and the base is the parent branch, not a substitute
for either.

**A packet flagged `needs_authoring` has no TASK block in the contract.** Do not write one and
carry on. Say which sub-task is missing it, and that the contract needs amending. Inventing the
instruction defeats the point of the architect having written it.

**One pull request per sub-task, always.** Bundling two is what makes a merge unable to say
which sub-task it closed.

### `escalate` — a sub-task could not be delivered

Report the failed sub-task, its severity and its reason, then name every sub-task now blocked
behind it.

Route to architect re-entry. Concretely that means `/design-first` amending the contract. Do
not start anything, and do not retry the sub-task from here — whether to retry is one of the
decisions the architect makes.

### `complete` — every sub-task has a record

Say so, then hand off using the closing call's `next_command`, printed verbatim (Step 3 below).
Today that is `/verify-before-done`, followed by `/ship` for the contract as a whole. For a
contract with two or more mergeable sub-tasks, confirm every sub-issue is closed before the
contract's parent pull request is marked ready — nothing enforces it yet.

**Do not declare the contract finished here.** That the last sub-task closed is a fact this
skill can report. Whether the contract is done is a verdict belonging to verification.

### `awaiting-merge` — a sub-task is out for merge

Say which sub-task, and which pull request it waits on. Do not start anything else and do
not treat it as stuck. It is suspended, and `/pr-merged` is what resumes it.

This state is the one the previous orchestrator never had. Without it, a sub-task waiting
on an open pull request is indistinguishable from one that is genuinely blocked.

### `blocked` — sub-tasks remain and none is ready

Report each blocked sub-task with what holds it, straight from the script. Common causes are a
dependency with no completion record yet, a dependency that failed, and a contract with no
`Depends on:` line.

That last one is a contract defect, not a wait. Say so, because nothing will ever unblock it on
its own.

### `nothing-planned` — the contract declares no sub-tasks

Say that plainly. **Never read it as complete.** An empty plan reported as a finished contract
is the exact defect that had the previous orchestrator announcing success having written no
code.

The fix is to give the contract an `## Implementation Handoff` section with numbered sub-task
blocks. `/design-first` is where that happens.

## Step 3: Report, in the same shape every time

**First, make one more call to the script — read-only, and AFTER the move this skill just
took:**

```bash
py -3 "$PRM" --contract <slug> --status --json
```

**The closing line comes from THIS call's `next_command`, never from Step 1's.** Step 1's
answer described the state *before* this skill acted; printing it as the closing line says
"clear, then advance" at the exact moment this skill is about to dispatch — the stale-answer
defect this ordering exists to remove. The script computes the Next Command; this skill only
prints it verbatim, exactly as `pr_merged.py`'s own human-readable output does.

```
### ADVANCE REPORT
- Contract: <slug>  (<n> sub-tasks)
- Next move: <action>
- Contract defects: <block — reason, one line each | none>
- Started: <sub-task -> branch -> cycle stage(s) dispatched -> pull request url, or none>
- Failed: <sub-task — severity, reason | none>
- Blocked: <sub-task <- what holds it, one line each | none>
- Waiting on: <the merge this now needs, or nothing>
- Next command: <the FINAL call's next_command.commands, joined by ", then ", or "none — <reason>">
```

The last two lines matter most. An operator who cannot see what the contract is waiting for,
and what to type next, will either sit watching it or walk away at the wrong moment. **The next
command is the script's own field, read after the move — never a line this skill composes.**

## Where this sits

| Layer | Owner | Owns |
|---|---|---|
| Outer chain | `/flow` | One work item, from intake through to shipped |
| **Inner loop** | **this skill, with `/pr-merged`** | One contract's sub-tasks, a step at a time |
| Sub-task closing | `/pr-merged` | Recording a merge and computing what it released |

`/flow` hands the inner loop here once a contract is approved and carries sub-tasks. For a
contract with a single implementation block there is nothing to iterate, and `/flow` runs it
directly.

## What is pre-authorized, and what is not

**Pre-authorized when `/flow` or the operator invoked this:** reading the script's answer,
creating the branch the packet names, dispatching the packet's cycle stage(s) as fresh
subagents, and reporting.

**Always the operator's call:** which sub-task to start when several are released, the commit
confirmation, opening the pull request, amending a contract after an escalation, and anything
that would start work the script did not release.

## Anti-patterns (halt immediately)

- **Looping.** Take one move and stop. The next move needs a human merge that cannot happen
  while this is running.
- **Recomputing readiness from the contract** instead of reading the script's answer. Two
  implementations of one rule will disagree.
- **Starting a sub-task the script did not release.** Its dependencies have not landed.
- **Writing a TASK block for a packet flagged as needing authoring.** Report the gap.
- **Bundling two sub-tasks into one pull request.** The merge then cannot say what it closed.
- **Reading `nothing-planned` as complete.** That is the defect this whole design exists to
  avoid.
- **Declaring the contract finished** because the last sub-task closed. Verification decides.
- **Retrying a failed sub-task** without the architect. Whether to retry is their decision.
- **Running a cycle stage inline, in this session,** instead of dispatching it as a fresh
  subagent. `stage["isolation"]` is the constant `fresh-subagent` for a reason.
- **Naming a cycle stage the packet did not ship,** or inferring one from `agent_role`. The
  closed set is `review`, `red`, `green`, `unphased`, read off `stage["stage"]` for each entry
  of `cycle`, in order — never `cycle[0]` alone.
- **Printing Step 1's `next_command` as the closing line.** It describes the state before this
  skill acted. Only a call made *after* the move reflects what changed.

## When NOT to use this skill

- A work item with no contract, or a contract with one implementation block. Use `/flow`.
- A pull request that just merged. Use `/pr-merged`, which then tells you to come back here.
- Checking state without acting. Run the script with `--status` and read it.

## Skill integrations

- **Reads** `.claude/scripts/pr_merged.py`, which owns the rules and the tests.
- **Runs** `/tdd-first` for a dispatched sub-task, then `/ship` for its pull request.
- **Paired with** `/pr-merged`, which closes a sub-task and wakes this skill.
- **Called by** `/flow`, which owns the work item around the contract.
- **Escalates to** `/design-first` on a failure, and to `/verify-before-done` on completion.
