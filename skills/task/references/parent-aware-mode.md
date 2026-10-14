## Parent-aware mode

A second invocation shape, used when this skill is producing one task of an already-approved
contract rather than intaking fresh work. `/flow`, once a contract is approved and declares two
or more mergeable sub-tasks, invokes this mode once per sub-task; a person does not normally
type this form by hand.

```
/task <the sub-task's name from its handoff heading>
PARENT_ISSUE: <n>
BASE_BRANCH: <the parent branch>
BRANCH_NAME: task/<contract-slug>/<sub-task-id>
CONTRACT: .claude/concepts/<slug>.md
SUB_TASK: <the contract's numbered handoff block, verbatim>
```

**All five fields above are required — this mode never triggers on a subset.** The mode reads
the sub-task name (the bare argument after `/task`), `PARENT_ISSUE`, `BASE_BRANCH`,
`BRANCH_NAME`, `CONTRACT` and `SUB_TASK`; every one of them is consumed somewhere below. An
invocation carrying some but not all five matches no row in Step 0's table. Halt and name the
missing fields — do not fill one in from context and do not treat a partial set as the no-parent
path; it is neither.

**Order of operations — stated explicitly, because two things below used to disagree about it.**
The step numbers name the no-parent path's usual sequence; this mode runs three of them in a
different order, forced by one dependency: the sub-issue create needs a title before any brief
exists to draw one from, and the brief needs an `id:` that only the create can produce.

1. **Classify the effort type**, using Step 2.5's matching procedure only — not its point 6 issue
   offer, which never fires in this mode (see below). Default the proposed type to the parent
   item's own `type:`, confirming with `AskUserQuestion` only when it cannot be derived that way.
   This runs first because the create below interpolates `[<TYPE>]` into the sub-issue's title.
2. **Create the sub-issue** (procedure below), titled from step 1's type, with a body taken from
   the supplied `SUB_TASK` block verbatim — no brief exists yet at this point to draw a body from.
3. **Verify the parent link** (procedure below).
4. **Write the brief** (Step 2's template, extended by the keys listed below), because its `id:`
   is the sub-issue number step 3 just confirmed `linked`.

**The branch name is load-bearing — never improvise it.** The delivery loop maps a merged pull
request back to its sub-task by matching its branch, exactly, against
`task/<contract-slug>/<sub-task-id>`. A branch cut under any other name — including a
plausible-looking rename — falls through to unmapped, and the merge can never be attributed to
the sub-task it closed. This is the concrete failure a hand-cut branch produced before this mode
existed; state it here so it cannot happen again through this mode either.

**Identical to the no-parent path — stated as identical here so the two never drift into two
mechanisms:**

- Step 2 writes a brief at `.claude/work-items/`, from the same template, with the same
  frontmatter keys plus the ones described below — written after the create-and-verify sequence
  above, not in Step 2's usual position; see "Order of operations" above.
- Step 2.5's effort-prefix classification reads the same `issueTitle` block from
  `.claude/work-item-conventions.json` and matches the same `pattern`. Default the proposed type
  to the parent item's own `type:`, already settled at the parent's own intake, and still confirm
  with a single `AskUserQuestion` only when it cannot be derived from that.
- Step 5's linked-branch registration is the same `gh issue develop` form with the same plain
  `git switch -c` fallback — with one difference, named in Step 5's own text: in this mode the
  branch is recorded, not cut.
- The brief is committed to the repository like any other, and it is not a product deliverable.

**Four differences from the no-parent path, each with its reason:**

1. **Step 3 (clarify before designing) is skipped.** The sub-task's acceptance criteria are its
   handoff block, already approved by the user at the contract gate. Re-interrogating them
   re-opens a decision that is not this mode's to reopen.
2. **Step 3.5 (grade against the north-stars) is skipped.** The work was graded once at the
   parent item's own intake and again when the contract was designed. Grading a task of an
   already-approved contract re-litigates a settled decision. The brief records
   `north_stars: inherited from <parent brief path>`.
3. **Step 4 (size and route) is skipped.** The route is fixed: the sub-task is dispatched to
   `/tdd-first` once it is released, never sized here. The brief records
   `Routing: task of <contract path> — dispatched by /advance`, and Step 6's handoff to
   `/design-first` never fires for a brief written in this mode.
4. **Step 5 records the supplied branch name and creates nothing.** Say this loudly, because
   ordinary Step 5 exists to create a branch. Cutting every sub-task's branch at contract-approval
   time would seed each one from a parent branch that none of its own dependencies has actually
   merged into yet. The branch is cut later, when the sub-task is released for dispatch, by the
   delivery loop's own merge-gated dispatcher — which is also where the `gh issue develop`
   registration finally runs.

**Step 2.5 point 6, the offer to open an issue, does not fire in this mode.** Creating the
sub-issue is this mode's whole purpose — the invocation itself is the request, on the same
pre-authorization terms Step 6 already grants the `/design-first` handoff. Never ask again.

**Create the sub-issue, then verify — a create's exit code is a request, never a fact:**

```
gh issue create --parent <PARENT_ISSUE> --title "[<TYPE>] <bare title>" --body "<the supplied SUB_TASK block, verbatim — no brief exists yet at this point to draw a body from>"
```

exits `0` when the request was accepted, not when the link exists. Immediately read it back.

**Finding the script, under either install mode.** The script ships with the plugin and with a
vendored copy, the same as `/advance`'s `pr_merged.py` lookup — resolve it once, the same way,
then use the result:

```bash
VPL=
S=.claude/scripts/verify_parent_link.py
if [ -f "$S" ]; then VPL=$S
elif [ -n "$CLAUDE_PLUGIN_ROOT" ] && [ -f "$CLAUDE_PLUGIN_ROOT/$S" ]; then VPL=$CLAUDE_PLUGIN_ROOT/$S
else
  # What Claude Code recorded for this plugin (this project's entry, then the user entry), then the newest cache folder by version number.
  CFG=${CLAUDE_CONFIG_DIR:-$HOME/.claude}
  ME=$(printf %s "$CLAUDE_PROJECT_DIR" | tr 'A-Z\134' 'a-z/' | tr -s /)
  REC=$(tr -d '\r\n' 2>/dev/null < "$CFG/plugins/installed_plugins.json" | grep -o '"agentic-auto-improve@[^"]*" *: *\[[^]]*]' | grep -o '{[^{}]*}' | tr '\134' / | tr -s /)
  MINE=$(printf '%s\n' "$REC" | grep '"scope" *: *"project"' | while IFS= read -r O; do
    P=$(printf %s "$O" | sed -n 's/.*"projectPath" *: *"\([^"]*\)".*/\1/p' | tr 'A-Z' 'a-z' | tr -s /)
    [ -n "$ME" ] && [ "${P%/}" = "${ME%/}" ] && printf '%s\n' "$O"
  done)
  NEWEST=$(ls -d "$CFG"/plugins/cache/*/agentic-auto-improve/*/ 2>/dev/null | sed -n 's|^\(.*/\([0-9][0-9.]*\)/\)$|\2 \1|p' | sort -rV | cut -d' ' -f2-)
  VPL=$({ printf '%s\n' "$MINE"; printf '%s\n' "$REC" | grep '"scope" *: *"user"'; } | sed -n 's/.*"installPath" *: *"\([^"]*\)".*/\1/p' | { cat; printf '%s\n' "$NEWEST"; } | while IFS= read -r D; do
    [ -n "$D" ] && [ -f "${D%/}/$S" ] && { printf '%s\n' "${D%/}/$S"; break; }
  done)
fi
py -3 "$VPL" --sub <sub> --parent <PARENT_ISSUE> --json
```

**If `VPL` comes back empty, halt loud and say so.** The four-row table below is what this mode
branches on, and an unresolvable path produces no verdict at all — that silence must never be
read as `linked`, or as anything else.

```bash
py -3 "$VPL" --sub <sub> --parent <PARENT_ISSUE> --json
```

Branch on its `verdict`. The verdict set and the repair budget both live in
`.claude/work-item-conventions.json` → `issueLink` and its nested `parentLink` block, which is
the single source of truth for both; where the table below and that file ever disagree, the
conventions file governs. The table exists because the per-verdict *action* genuinely lives
nowhere else:

| Verdict | What it means | What this mode does |
|---|---|---|
| `unverifiable` | the resolver itself could not be reached — `gh` missing, unauthenticated, or the query failed | Halt loud. The create command's own exit code is never read as the answer. |
| `no-parent` | GitHub reports no parent for the new sub-issue | Repair, up to `issueLink.maxRepairAttempts` time(s) — read the count from the conventions file, never hardcode it here: `gh issue edit <sub> --parent <PARENT_ISSUE>`, then re-run the verifier, passing `--repair-attempted`. Still `no-parent` once the budget is spent → halt. |
| `foreign-parent` | GitHub reports a parent, but it names a different issue | Halt. Never re-parent automatically — reassigning an issue's parent is a destructive tracker mutation with no undo. |
| `linked` | GitHub reports the expected parent | Proceed to write the brief. |

**Fill in every frontmatter key the skipped steps would otherwise have set.** Steps 3, 3.5 and 4
are skipped in this mode (below), and Step 5 creates nothing — which is exactly the set of steps
that ordinarily assign `id:`, `url:`, `contract:`, `worktree:` and `status:`. Nothing else in
this file fills them in for a Sub-Task Work Item, so this mode sets all five explicitly, plus the
ordinary title/type split every brief gets:

- `id:` — the sub-issue number `verify_parent_link.py` just confirmed `linked`. **Never the
  parent's number** — the parent's number lives only in `parent_issue:` below (I-2).
- `url:` and `repo:` — the created sub-issue's own link and its own owner/repository — never the
  parent issue's.
- `contract:` — the supplied `CONTRACT` value, verbatim. `/design-first` never runs in this mode,
  so nothing else will ever fill this field in.
- `worktree: none` — this mode creates no branch and no checkout; see Step 5 below.
- `status: implementing`. This is settled, not a judgment call for whoever implements this mode:
  sub-issue creation sits between two lifecycle values with no name of its own, because the
  design is already done — it IS the contract — and the next thing that happens to a Sub-Task
  Work Item is implementation.
- `title:` and `type:` — the sub-task's name from its own handoff heading, split into a bare
  title and an effort tag by Step 2.5's own matching procedure, exactly as any other brief's
  title is split — this classification runs before the create, not after (see "Order of
  operations" above).

**Write the brief with its two new frontmatter keys.** Both are single tokens with no colon —
the brief parser reads any colon-bearing line as a new key:

- `parent_issue: <n>` — the parent issue's number.
- `base: <branch name>` — the branch this sub-task's own branch will be cut from, i.e. the
  supplied `BASE_BRANCH`.

`parent_issue: none` if and only if `base:` names the repository default branch, in both
directions. A brief carrying exactly one of the two keys without the other is a defect, not a
shorthand, and halts. An ordinary brief written outside this mode carries neither key, and that
absence is not a violation of the rule above — the rule binds a brief that carries at least one
of the two keys, not every brief that has ever existed.

**The brief path and the `branch:` field, and why both are exact.** Write the brief to
`.claude/work-items/<date>-<sub-issue>-<sub-task-id>.md`, and set its `branch:` field to the
caller-supplied `task/<contract-slug>/<sub-task-id>` verbatim — never a paraphrase of it. That
exact value is what makes `/ship`'s own Step 0 branch-match lookup find this brief with no change
to that lookup, and it is the same value the delivery loop's merge-to-sub-task mapper reads back
at close time.

**Never invent the sub-task's acceptance criteria.** The `SUB_TASK` field supplied at invocation
is the contract's own numbered handoff block, already approved by the user — copy it into the
brief's `## Acceptance criteria` section rather than re-deriving or summarizing it.
