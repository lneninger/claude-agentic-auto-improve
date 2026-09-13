---
name: flow
description: "Run the whole contract-driven delivery chain end to end in one invocation: intake, design contract, test-first implementation, adversarial review, verification, commit and pull request. Drives the working agent chain (/task, /design-first, /tdd-first, the reviewer agents, /verify-before-done, /git-commit, /ship) and pauses only at the gates a human must answer. Use when: user says /flow, 'run the whole flow', 'take this all the way to a PR', 'do the full autonomous flow', 'end to end', or hands over a request and expects a pull request back rather than a plan. Does NOT drive the Contract Orchestrator scripts under .claude/scripts/ — that scaffold is gated as unimplemented; see the section at the end."
user_invocable: true
---

# /flow — the contract-driven delivery chain, end to end

One invocation, one delivery. `/flow` runs every stage of the chain in order and stops only
where a person has to decide something.

```
/flow
  └─ /task ─→ /design-first ─→ /tdd-first ─→ reviewers ─→ /verify-before-done ─→ /git-commit ─→ /ship
       │           │                │             │                │                  │           │
     brief      CONTRACT         red then      adversarial      build, tests,       staged      draft
                 GATE (*)         green          agents          drift, gates       commit       PR
```

The contract gate, marked above, is the one stop that can never be automated away.
Everything else runs without asking.

## Context — why this skill exists

Each stage of the chain already has a skill, and each skill already says which one comes
next. What nothing owned was the run itself. An operator who wanted a request carried all
the way to an open pull request had to type seven invocations and carry the handoff shape
between each pair by hand. Where an operator stopped typing, the chain stopped, usually
after the contract and before any code.

`/flow` owns the run. It holds the work item identity across every stage, it knows which
stops are real and which are habit, and it can pick a half-finished run back up from disk
instead of starting over.

**What `/flow` is not.** It does not restate the rules of the stages it calls, and it does
not override them. Every stage skill remains the authority on its own steps. If this file
and a stage skill disagree about that stage, the stage skill wins and the disagreement is
a defect in this file.

## Step 0: Parse the invocation and set the autonomy level

The argument is whatever `/task` accepts: a GitHub issue number such as `#123`, an issue
link, a Jira or Azure DevOps key, free prose, or nothing at all.

Read one optional trailing flag. It sets how far the run goes before it hands back:

| Flag | Runs through | Use when |
|---|---|---|
| *(none)* | The whole chain, ending at a draft pull request | The default, and what most operators want |
| `--to-contract` | Intake and design only, stopping at the approved contract | The design is the deliverable, or the work will be implemented elsewhere |
| `--to-green` | Everything up to a passing test suite, no commit and no pull request | The operator wants to read the diff before anything is recorded |
| `--to-commit` | Everything up to a local commit, no push and no pull request | Work stays on the machine for now |

Announce the parsed target in one line before starting. An operator who meant
`--to-green` and got a pull request has lost something they cannot take back quietly.

## Step 1: Intake

Invoke `/task` through the Skill tool with the argument verbatim.

`/task` produces the Work Item Brief at `.claude/work-items/<date>-<slug>.md`, grades the
item against the active north-stars, sizes it, and creates the branch or the parallel
worktree. Let it do all of that. Do not pre-empt its clarifying questions, and do not
answer them on the operator's behalf.

**Carry two things out of this stage and hold them for the whole run:** the brief path and
the branch name. Every later stage reads the brief rather than a paraphrase of it, and
`/ship` pushes the branch that actually holds the commits.

**If `/task` created a worktree, settle the working directory here.** Enter it, or state
its path in every later handoff. A contract implemented in the parent tree while the branch
lives in the worktree produces a branch with no commits, and nothing notices until `/ship`.

**Routing.** `/task` sizes the item and picks the route. Honour it:

- **Extra small or small** — skip Step 2 entirely and go to Step 3. For a bug, run `/debug`
  first and let its root cause become the regression test.
- **Medium, large or extra large** — continue to Step 2. This is not negotiable; where a
  concept gate hook is installed it blocks the writes anyway.

## Step 2: Design — and the one human gate

Invoke `/design-first` through the Skill tool, passing the brief path rather than a
retelling of the request:

```
TASK: <brief title>
CONTEXT: Work Item Brief at .claude/work-items/<file>.md — read it first; it carries the
         acceptance criteria, the out-of-scope list and the intake answers. Do not
         re-derive requirements from the chat.
WORK_ITEM: <id> (<url>)
NORTH_STARS: <the grades from the brief, verbatim — or 'none'>
```

`/design-first` dispatches `data-architect` to draft the contract and `contract-critic` to
attack it. Both dispatches are pre-authorized by the `/flow` invocation and are not
separate decisions to put to the operator.

**Then the run stops.** The contract goes to the operator, every open question is answered
by them, every blocker from the critic gets an explicit response, and the operator alone
flips the status to approved. Do not guess an answer. Do not approve a contract. Do not
read silence as agreement.

This is the gate the whole protocol is built around. A chain that approves its own designs
is not autonomous, it is unsupervised.

When the contract is approved, write its path into the brief's `contract:` field and set
`status: designing`. If the target was `--to-contract`, report and stop here.

**On `/design-first` Step 3.5.** That step carries a gate covering the Contract
Orchestrator. Respect it: under `/flow`, always take the traditional workflow and go to
Step 4. The closing section of this file records why.

## Step 3: Implement, test first

Invoke `/tdd-first` through the Skill tool with the contract path.

It runs the cycle the protocol mandates. `senior-test-engineer` writes failing tests and no
implementation. The suite runs and has to fail on an assertion, because a failure from a
compilation error or a dependency injection error is not a red state. Then the implementer
agent writes the least code that turns the suite green. The suite runs again, and nothing
that passed before may now fail.

Pick the implementer from the ones the consuming project installs. This plugin ships
`dotnet-backend-architect`, `angular-senior-dev` and `python-ai-developer`; a project may
add its own.

Set the brief's `status: implementing` when this stage starts.

**Two rules that `/flow` must not let slip, because they are what the cycle is for:**

- **Never let an implementer edit a test to make it pass.** If an implementer reports that
  a test is wrong, halt the stage and return to the test author. Silently corrected tests
  are how a suite goes green while the behaviour stays broken.
- **Never accept a green claim without the run.** Redirect the suite output to a log and
  read the exit code. A build that never ran exits zero through a pipe.

If the target was `--to-green`, report the passing suite and stop here.

## Step 4: Review, with fresh agents every time

Dispatch `fullstack-code-reviewer` through the Agent tool against the production code, and
`test-strategy-critic` against the test suite. These review different things and neither
substitutes for the other: one asks whether the code is right, the other asks whether the
tests are worth having.

Add a domain reviewer whenever the diff touches its ground. The reviewers this plugin ships:

| Diff touches | Also dispatch |
|---|---|
| Authentication, credentials, encryption, ownership checks | `security-auditor` |
| Database migrations | `migration-safety-reviewer` |
| Controllers, request or response types, generated client models | `api-contract-reviewer` |
| Queries, repositories, index strategy | `sql-performance-reviewer` |

**A consuming project adds its own rows.** Anything that can move money, send an order,
or touch a regulated surface deserves a dedicated reviewer, and only the project knows
which paths those are. Record those rows in the project's own copy of this table.

Dispatch independent reviewers in a single message so they run at the same time.

**Every review pass gets a new agent.** For a second pass after fixes, dispatch a fresh
instance rather than messaging the one that already reviewed. The earlier instance carries
its own findings and the implementer's reasoning, and both bias the second look. A clean
re-review needs a cold context, and one extra dispatch is cheaper than a missed regression.

The main session never reviews its own implementers inline. Prose saying the diff looks
fine does not satisfy this stage.

## Step 5: Verify

Invoke `/verify-before-done`. It runs the builds, the test suites, the generated-model
drift check, the migration safety check, the safety-critical review gate, the handoff
completeness check and commit hygiene, then reports a verdict.

Set the brief's `status: verifying`.

**A failure here ends the stage and sends the run back.** Do not carry a failing verdict
forward with a note promising to fix it later. That is the single behaviour this gate
exists to prevent.

Two traps worth naming, because both have produced false green runs:

- **A green run has a shelf life.** It expires the moment a parallel agent writes to the
  tree. If anything was dispatched after the suite ran, run it again.
- **Read the exit code, never a tail of the output.** A command that never ran can still
  end a pipeline quietly.

## Step 6: Commit

`/verify-before-done` fires its commit step on its own when the verdict is ready. It stages
the working copy, drafts a commit message in the project's style, and asks once before
committing.

Let that ask reach the operator. Committing is a recorded act, and `/flow` does not hold
an authorization for it.

If that step does not fire, invoke `/git-commit` instead and let it run its own staging and
confirmation.

**Stage narrowly.** Other sessions may share the working tree, and a whole feature
belonging to somebody else can appear mid-run. Verify that what you stage is what this run
produced.

If the target was `--to-commit`, report and stop here.

## Step 7: Ship

Invoke `/ship`. It re-runs the verification gate, commits anything outstanding, pushes the
branch from the tree that holds the commits, and opens a draft pull request linked back to
the work item.

Pushing and opening a pull request are outward-facing. `/ship` confirms before it acts and
`/flow` does not waive that confirmation.

Set the brief's `status: shipped` and write the pull request link into its `pr:` field.

## Where the run stops, and where it does not

The distinction matters more than any other part of this file. An operator who cannot
predict where the chain pauses will either sit watching it or walk away at the wrong time.

**Pre-authorized by the `/flow` invocation — never ask:**

- Dispatching any agent named in this file, including the design and critique agents
- Moving from one stage to the next once that stage's gate has passed
- Creating the branch or the worktree, and entering it
- Writing and rewriting the Work Item Brief and its status field
- Running builds, test suites and the verification gauntlet
- Re-running a stage after a failure, within the retry budget below

**Always the operator's call — never assume:**

- Approving a concept contract, and answering each of its open questions
- Responding to a critic blocker, whether by fixing it, deferring it or rejecting it
- Accepting a conflict with an active north-star
- The commit confirmation, the push, and opening the pull request
- Anything destructive against a database, which the guard hooks block regardless
- Widening the scope past what the brief's acceptance criteria say

**Retry budget.** A stage may be retried twice. On the third failure, stop the run, write
what failed into the brief under a `## Run log` heading, and hand back. A chain that
retries forever burns an afternoon and reports nothing.

## Resuming a run

`/flow` is resumable because the Work Item Brief records where the run got to. Invoke
`/flow` with the brief path or the issue number and read the `status:` field:

| `status:` | Resume at |
|---|---|
| `intake` | Step 1, finish clarification |
| `clarified` | Step 2, design |
| `designing` | Step 2's gate — the contract exists but is not approved |
| `implementing` | Step 3, and re-run the suite before trusting any earlier green |
| `verifying` | Step 5 |
| `shipped` | Nothing to do; report the pull request link |

**A run can also be resumed by a merge.** When a contract's work is split across sub-tasks,
one sub-task often waits for another to land in the default branch. Nothing watches for that.
Tell the session with `/pr-merged <numbers>`. It confirms the merge with GitHub, records the
finished sub-task, works out which sub-tasks that releases, and continues them.

**Re-read the brief on resume rather than trusting the conversation.** A resumed run is
usually a new session, and the tree has moved since. Check the branch, check the worktree
path, and confirm the file list the brief names still exists before acting on it.

## The Contract Orchestrator is NOT wired

This plugin ships seven scripts that read as a working orchestrator:
`execute_contract.py`, `orchestrator_loop.py`, `orchestrator_task_planner.py`,
`task_executor_launcher.py`, `generate_task_execution_packet.py`, `final_reviewer.py` and
`orchestrator_github_integration.py`. It does **not** ship the design notes or the tests
that go with them, so a fresh checkout carries no record that they are stubs. The gate in
`/design-first` Step 3.5 and this section are that record.

**Do not run them, and do not offer them as a working choice.** Verified by reading the
source on 2026-09-13:

1. **The planner always yields zero tasks.** `TaskPlanner._load_contract` returns a
   hardcoded dictionary and never reads the contract markdown. `plan_tasks` hands back the
   empty dictionary it started with.
2. **Zero tasks makes the run claim success.** `_execute_next_tasks` asks whether all tasks
   completed, and Python's `all` over an empty collection answers yes. The loop moves to
   verifying, the final reviewer walks the same empty collection, and the program prints
   that execution is complete. Nothing was written.
3. **No Claude session is ever launched.** `_spawn_claude_session` touches a marker file
   and returns success; the launch line beside it is commented out. `_collect_result` then
   finds no result file, falls through to a fallback, and reports the task completed with
   tests passed, citing whatever commit the worktree already sat on.
4. **The packet generator call raises a type error.** The launcher passes three arguments
   to a constructor that declares four, in a different order.
5. **Architect re-entry blocks on console input,** with the agent dispatch commented out.
   An unattended run cannot answer it.
6. **A merge acts on the primary working tree.** `_merge_to_master` checks out the default
   branch and merges with no working directory set, so it acts on whichever tree the
   orchestrator was started from.
7. **A run opens real tracker issues first.** `_start_execution` shells out to the GitHub
   client to create an issue for the contract and one per task, before any work happens.
8. **Contract lookup can pick the wrong file** — the first contract found containing the
   text `Status: approved`, which need not be the one requested.
9. **The test suite that exists in the origin project is green and proves nothing.** It
   runs thirteen tests in about a fifth of a second and never calls `plan_tasks`, so the
   planner stub is never exercised.

**Lift this gate only when the stubs are real and a test proves a task's work actually
landed** — a commit the orchestrator did not invent. A positive control is required: a task
that fails must make the run fail. Until then, the agent chain above is the autonomy that
exists.

## Anti-patterns (halt immediately)

- **Approving the contract yourself,** or reading silence as approval. The gate is the
  protocol; a chain without it is unsupervised, not autonomous.
- **Asking permission for a stage transition the invocation already authorized.** It
  strands a run mid-chain and makes the operator type what they typed already.
- **Skipping intake because the request looks clear.** Requests that look clear are the
  ones that ship the wrong thing, which is why `/task` exists.
- **Letting an implementer edit a test to reach green.** Halt and return to the test author.
- **Believing a green suite you did not watch run.** Read the exit code.
- **Carrying a failed verification forward** with a promise to fix it after the pull
  request. The gate exists precisely to stop that.
- **Re-using a reviewer agent for a second pass.** Its context is already primed.
- **Running the Contract Orchestrator,** or presenting it to the operator as a working
  option. See the section above.
- **Widening scope mid-run** because a stage surfaced something adjacent. Finish the item,
  record the adjacency in the brief, and let the operator decide whether it becomes work.

## When NOT to use this skill

- Pure research, code reading, or a question with no deliverable. Answer it.
- A single trivial edit, such as a typo, a log line or a version bump. Just make it.
- Work already mid-chain. Resume it from the brief rather than re-running intake.
- When the operator asked for one specific stage. Run that stage, not the chain.

## Skill integrations

- **Composes** `/task`, `/design-first`, `/debug`, `/tdd-first`, `/verify-before-done`,
  `/git-commit` and `/ship`, in that order, without restating or overriding any of them.
- **Dispatches** `data-architect`, `contract-critic`, `senior-test-engineer`, the
  implementer agents, `fullstack-code-reviewer`, `test-strategy-critic`, and whichever
  domain reviewers the diff calls for.
- **Reads and writes** the Work Item Brief at `.claude/work-items/`, which is what makes a
  run resumable across sessions.
- **Pairs with** `/pr-merged`, which resumes a run when a sub-task's dependency merges.
- **Deliberately does not drive** `.claude/scripts/execute_contract.py`.
