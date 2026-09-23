---
name: flow
description: "Run the whole contract-driven delivery chain end to end in one invocation: intake, design contract, test-first implementation, adversarial review, verification, commit and pull request. Drives the working agent chain (/task, /design-first, /tdd-first, the reviewer agents, /verify-before-done, /git-commit, /ship) and pauses only at the gates a human must answer. Use when: user says /flow, 'run the whole flow', 'take this all the way to a PR', 'do the full autonomous flow', 'end to end', or hands over a request and expects a pull request back rather than a plan. Replaces the Contract Orchestrator scripts, which were removed; see the section at the end."
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

## Step 2.7: Open the sub-tasks

**Guard, checked first, before anything else in this step, on every entry — a fresh run and a
resumed one alike.** If this run's own brief carries a `parent_issue:` field, this run is one of
the sub-tasks this step creates, not the contract's parent run, and this step never executes for
it. The factory writes the same `status:` value into a sub-task's own brief that it writes into
the parent's, so `status:` alone cannot tell the two apart — `parent_issue:`, the field this
mechanism introduced, is what does. This check belongs here and not only in the resume table
below, because a resumed run is not the only way this step gets reached. Skipping is not
optional: running this step again from a sub-task's own brief would open a second set of
sub-issues against the very contract that already produced this one, which is the failure this
whole design exists to prevent.

Runs once the contract is approved, between the design gate above and implementation below —
it cannot run any earlier, because the sub-task list exists only once the contract does.

Ask the contract's own script whether it decomposes into more than one deliverable. Never answer
that by re-reading the contract's handoff section — the same rule `/advance` follows for the same
reason: two implementations of one rule will disagree.

**Finding the script, under either install mode** — the identical lookup `/advance` Step 1
already documents, reused rather than restated as a second copy:

```bash
PRM=$(ls .claude/scripts/pr_merged.py \
         "$CLAUDE_PLUGIN_ROOT/.claude/scripts/pr_merged.py" \
         ~/.claude/plugins/cache/*/agentic-auto-improve/*/.claude/scripts/pr_merged.py \
         2>/dev/null | head -1)
```

**If `PRM` comes back empty, stop and say so** — the same halt `/advance` takes, for the same
reason: every rule this step needs lives in that file.

```bash
py -3 "$PRM" --contract <slug> --status --json
```

Read `defects` and `sub_tasks` from the answer and go no further into the contract than that,
with one named exception: `sub_tasks` carries each block's identity and its heading-derived name,
never the block's own body text, because the script's `--status` mode never calls its own body
reader — that reader only runs in the release path, and only for a sub-task already merged.
Where a later step in this section needs the numbered handoff block itself, matching the heading
`sub_tasks` already gave is the one place this step reads the contract directly. No other read
into the contract is licensed here.

1. **`defects` non-empty → report each one, its block and its reason, and stop. Create nothing.**
   Asked first, before the count below, for the reason `/advance` asks it first: a contract whose
   blocks are all malformed parses to an empty task list, and opening tracker records for a plan
   that cannot be delivered makes records for work nobody can do.
2. **`len(sub_tasks) <= 1` → stop here.** No sub-issue, no state-store identity fields, no change
   to Step 3 below. This is the true no-op case, and the discriminator is the script's own
   mergeable count — never a second reading of the contract, and never a heading count taken by
   eye.
3. **`len(sub_tasks) >= 2` → open one sub-task per entry, in ordinal order.**

   Before creating anything:

   ```bash
   gh --version && gh auth status
   ```

   **Unavailable → stop the run and say so.** Do not fall back to running the contract as a
   single block, and do not fall back to cutting branches from the default branch. Either
   fallback produces today's topology while the operator believes they got the new one, which is
   worse than a halt.

   For each sub-task, decide what to do from stored evidence, in this declared order — **never**
   from a title search, because two sub-tasks of one contract can legitimately share a title
   prefix, and a search that matched one would silently skip a sub-task that has none:

   1. **The state store already carries an `issue` for this sub-task** — read
      `state.sub_tasks.<sub-task-id>.issue` off the same `--status --json` answer, not a second
      query — **skip creating it**, and re-verify that stored number's Parent Link before
      trusting it, through the same verifier `/task` uses on its own create, resolved the same
      way:

      ```bash
      VPL=$(ls .claude/scripts/verify_parent_link.py \
               "$CLAUDE_PLUGIN_ROOT/.claude/scripts/verify_parent_link.py" \
               ~/.claude/plugins/cache/*/agentic-auto-improve/*/.claude/scripts/verify_parent_link.py \
               2>/dev/null | head -1)
      py -3 "$VPL" --sub <stored issue> --parent <the parent issue number> --json
      ```

      Anything other than `linked` halts this sub-task — but not "the same way a fresh create's
      own verification would": a fresh create still has `/task`'s own single repair attempt
      available before it settles on a verdict, and this read-back issues no tracker mutation of
      any kind, repair included. The halt here is still correct; it follows because this step may
      make no tracker write at all, not because it mirrors a create that can.
   2. **No state entry, but a Sub-Task Work Item already exists** whose `branch:` field equals
      `task/<contract-slug>/<sub-task-id>` exactly — the same match `/ship` Step 0 already uses to
      find a brief by its current branch — and whose `id:` is resolved → re-verify that brief's
      `id:` against the parent issue before adopting it, through the same verifier point 1 uses,
      resolved the same way:

      ```bash
      VPL=$(ls .claude/scripts/verify_parent_link.py \
               "$CLAUDE_PLUGIN_ROOT/.claude/scripts/verify_parent_link.py" \
               ~/.claude/plugins/cache/*/agentic-auto-improve/*/.claude/scripts/verify_parent_link.py \
               2>/dev/null | head -1)
      py -3 "$VPL" --sub <brief's issue id> --parent <the parent issue number> --json
      ```

      Anything other than `linked` halts this sub-task, for the same narrower reason point 1's
      halt carries. Only on `linked` → adopt that `id:` and `base:` into the state store and
      create nothing. A brief on disk is not a stronger witness than a stored number for being
      newer — if anything it is weaker, since nothing else in this design re-reads or re-checks
      it once written — so it earns the same scrutiny, not less.

      **This step does not reconcile a state entry and a brief that disagree with each other**
      about which issue a sub-task resolves to. By the declared order above, a given sub-task
      only ever consults one of the two, so a live disagreement between them is never visible
      here. What does catch a wrongly adopted number is point 4's roll-up below: an id adopted
      here that the parent's own sub-issue list does not actually carry surfaces there as a
      mismatch.
   3. **Neither** → invoke `/task` through the Skill tool in parent-aware mode, all five fields
      present every time — this mode never triggers on a subset, and a partial set produces
      neither the old path nor the new one:

      ```
      /task <the sub-task's name from its handoff heading>
      PARENT_ISSUE: <the parent issue number, from this run's own brief>
      BASE_BRANCH: <the parent branch, from this run's own brief>
      BRANCH_NAME: task/<contract-slug>/<sub-task-id>
      CONTRACT: <this run's contract path>
      SUB_TASK: <the contract's numbered handoff block, verbatim — the one named exception to
                the "go no further into the contract" rule above>
      ```

      `/task` creates the sub-issue, verifies its own Parent Link, and writes the sub-task's own
      brief. This step issues no tracker command of its own and repeats none of that work — if a
      line here starts to read like `gh issue create`, stop, because every tracker artifact in
      this design comes from `/task` and a create issued from this file duplicates the exact
      thing this feature exists to remove.

      Then find the brief `/task` just wrote — the same `branch:` match used in point 2 above —
      and read its `id:` and `base:` back. Record all three into the state store through the
      script's own writer, never by hand:

      ```bash
      py -3 "$PRM" --contract <slug> --record-subtask <sub-task-id> --issue <n> --base <branch> --brief <brief-path>
      ```

   **A create or its verification fails part-way through the set → halt, and report exactly
   which sub-tasks have an issue and which do not.** Say that re-running this step creates only
   the missing ones. **Do not roll back** — deleting tracker records to tidy a partial run loses
   more than it saves.

4. **Roll up.** Once every sub-task above has been handled, read the parent issue's own
   sub-issue list once and compare it against the sub-issue numbers just created or adopted, in
   both directions. Report the comparison.

   - **A sub-issue this run expected but the parent does not report → halt.** Something between
     creation and this check did not land.
   - **A sub-issue the parent reports that this run did not expect → name it and halt, without
     closing it.** An amended contract is the ordinary way this happens, leaving an earlier
     sub-task the contract has since dropped still open on the parent. Whether that orphan should
     be closed is not this step's call to make on a local belief about the contract's current
     shape; report it and let the operator decide.

**No new `status:` value.** Sub-issue creation sits between `designing` and `implementing` in
the brief's lifecycle, but the state store already carries the finer-grained record, and a
seventh status would need every consumer of the existing six updated for a distinction this file
does not need. This is a decision, not an omission.

## Step 3: Implement, test first

**If the contract carries sub-tasks, hand the inner loop to `/advance`.** A contract whose
`## Implementation Handoff` section holds more than one numbered sub-task is iterated a step at
a time, because each sub-task ends in a pull request somebody must merge. `/advance` takes one
step and stops; `/pr-merged` records the merge and wakes it. `/flow` keeps the outer chain and
resumes at verification once every sub-task has a completion record.

For a contract with a single implementation block there is nothing to iterate, so run it
directly as below.

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

**Before invoking `/ship`, check whether this run is the parent of any sub-tasks.** Step 2.7
already answered this once, but ask again here: the run may have taken hours or days to reach
this point, and a child sub-task can still be sitting open.

**If this run's own brief carries no issue, skip this whole check and proceed to `/ship`
unchanged.** A brief with no issue has no children by definition, and querying a tracker record
that does not exist returns an error with no defined outcome — never read that as "no children
open."

Otherwise, read the child list with the command `.claude/work-item-conventions.json` names at
`issueLink.parentLink.parentListCommand`, filling in this run's own `id:` from the brief for the
placeholder that key uses. That key is the single source of truth for this query — do not write
a second copy of it here, and on any disagreement between this section and what that key names,
the key governs. Read each child's `state` in the casing that command's own JSON actually uses: a
`gh issue view --json` call reports state as `OPEN` / `CLOSED`, nested under
`.subIssues.nodes[]` — not the lowercase `open` / `closed` a `gh api .../sub_issues` call would
report for the identical children. The two `gh` forms are not interchangeable, and a check
written against the wrong one passes with every child open, which is the exact failure this step
exists to prevent. Confirm the casing against the live tracker before trusting either form.

**The query itself can fail** — `gh` missing, the token expired, the network down, or the
request erroring outright. This step runs long after intake, which is exactly when a token can
expire. Check the tool first, the way Step 2.7 already does, and **halt the run and say so** if
the command errors or returns no valid JSON. Reading a failed or unreachable query as "no
children open" would ship the parent pull request with every child still open and report
success — worse than having no gate here at all.

**An empty list is the single-block case and every ordinary item's case alike — proceed to
`/ship` exactly as below, unchanged.** A non-empty list means this run is a parent, whether or
not Step 2.7 ran in this same session — a run resumed straight from a stored `id:` reaches this
same check.

**Any child reporting `state: OPEN` → refuse to invoke `/ship`.** Report which sub-issues are
still open and stop. Do not push, do not open the pull request, and do not report a partial
success. Read the children from the parent issue itself, never from the state store, so a
sub-task somebody merged by hand outside this run still counts. This is the one gate this
mechanism adds to a step that otherwise does not change, and it is what stops the parent pull
request from merging while work beneath it is still open — the same merge that, through the
linked branch cut back at Step 1, would otherwise auto-close the parent issue regardless of
intent.

**Every child reporting `state: CLOSED`, or no children at all → proceed.**

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

## The three layers, and which one owns iteration

`/flow` is the outer layer. It is worth knowing what sits beneath it, because the middle layer
is real in the design and gated in practice.

| Layer | Owner | Owns |
|---|---|---|
| Outer chain | **`/flow`** | One work item, from intake through to shipped |
| Inner loop | **`/advance`**, with `/pr-merged` | Iterating the pending sub-tasks of one contract, one step per merge |
| Sub-task phase | `/pr-merged` | Closing one sub-task once its pull request merges |

**Today `/flow` covers the outer layer and drives implementation through agents,** because the
inner loop cannot execute a sub-task. When the loop is repaired, `/flow` hands the inner
iteration to it and keeps the outer chain. Nothing about the outer chain changes.

`/pr-merged` works under either arrangement. It closes a sub-task and returns the released set
to its caller. The loop calls it when a loop is running, and a person calls it when one is not.

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

## The inner loop, and the design that was removed

`/advance` and `/pr-merged` are the inner loop. Nothing else is.

An earlier subsystem claimed that job — eight scripts under `.claude/scripts/`, with names
beginning `orchestrator_` plus `execute_contract.py`. **They were removed on 2026-09-14.**

They never worked. The planner never parsed a contract, so every run produced zero sub-tasks,
and an empty set satisfied the completion test. A run therefore printed that the contract was
complete having written no code. No session was ever launched; that call sat commented out.
Its own thirteen-test suite passed without once calling the planner.

Three hazards came with it. It opened real tracker issues before doing any work. Its merge
step acted on whichever tree it was started from. Its dependency gate failed open, releasing a
sub-task whose parent had not merged.

**It was a different loop, not a broken version of this one.** It merged locally and never
pushed, so it had no review surface and no person in the loop. This design integrates by pull
request, which is why a person merges every sub-task.

The design record is kept, with a README stating plainly that it is a record rather than code.
Read it before rebuilding anything: the one capability it had and this design does not is an
isolated session per sub-task.

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
- **Hands the inner loop to** `/advance`, which moves a contract one sub-task at a time.
- **Pairs with** `/pr-merged`, which closes a sub-task and wakes `/advance`.
- **Replaces** the removed orchestrator scripts; their design record is at
  `.claude/orchestrator/`.
