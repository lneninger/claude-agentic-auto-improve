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
   This runs first because the sub-issue's title below is composed from step 1's type.
2. **Find the scripts** (the first part of the one block below), before the create, because step 3 needs the title
   helper and step 5 needs the verifier.
3. **Compose the title** with `compose_subissue_title.py` (same block). A `refused` result
   halts here, names its cause, and creates nothing.
4. **Create the sub-issue** (same block), titled with step 3's composed title, with a body
   taken from the supplied `SUB_TASK` block verbatim — no brief exists yet at this point to draw
   a body from.
5. **Verify the parent link** (the block's last line; its verdict is branched on below).
6. **Write the brief** (Step 2's template, extended by the keys listed below), because its `id:`
   is the sub-issue number step 5 just confirmed `linked`. The brief's `title:` stays the
   **bare** sub-task name; the parent number lives only in `parent_issue:`.

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

**One block does the find, the compose, the create and the verify.** The scripts ship with the
plugin and with a vendored copy, the same as `/advance`'s `pr_merged.py` lookup, so the block
resolves `VPL` itself with that same lookup and then derives everything else from it. Fill each
placeholder in with its value (the four numeric or fixed-tag ones sit inside single quotes, the
two free-text ones inside quoted here-documents; keep each where it is) and run the block once, whole, in a single Bash invocation: shell variables do not survive between
invocations, and a block split in two is how a title ends up created without its parent
reference. Every `HALT` below stops the run before anything further is created or claimed.

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
py -3 "$VPL" --help >/dev/null 2>&1 || { echo "HALT: verify_parent_link.py not found; no parent-link verdict is possible, so nothing is created"; exit 2; }
CST=$(dirname "$VPL")/compose_subissue_title.py
[ -f "$CST" ] || { echo "HALT: compose_subissue_title.py not found next to verify_parent_link.py; list .claude/scripts/compose_subissue_title.py in the sync configuration files array and sync"; exit 2; }
BARE=$(cat <<'BARE_TITLE_END'
<bare title>
BARE_TITLE_END
)
P='<PARENT_ISSUE>'
P=$(printf %s "$P" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'); P=${P#\#}
case "$P" in ''|*[!0-9]*) echo "HALT: PARENT_ISSUE must be an issue number such as 638 or #638; nothing is created"; exit 2;; esac
P=$(printf %s "$P" | sed 's/^0*//')
[ -n "$P" ] && [ "${#P}" -le 18 ] || { echo "HALT: PARENT_ISSUE must be a positive number of at most 18 digits; nothing is created"; exit 2; }
OUT=$(py -3 -X utf8 "$CST" --type '<TYPE>' --parent "$P" --subtask '<k>' --title="$BARE" --conventions "${CLAUDE_PROJECT_DIR:-.}/.claude/work-item-conventions.json" --json); RC=$?
if [ "$RC" -ne 0 ]; then
  printf '%s\n' "$OUT"
  if printf '%s' "$OUT" | py -3 -X utf8 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("verdict") == "refused" else 1)' >/dev/null 2>&1; then
    echo "HALT: the title was refused (the cause is in the JSON above); nothing is created"
  else
    echo "HALT: the title helper failed (rc=$RC) without a refusal; nothing is created"
  fi
  exit 2
fi
TITLE=$(printf '%s' "$OUT" | py -3 -X utf8 -c 'import json,sys; print(json.load(sys.stdin)["title"])' 2>/dev/null | tr -d '\r')
[ -n "$TITLE" ] || { printf '%s\n' "$OUT"; echo "HALT: the title helper failed (rc=$RC): its output is not a JSON title; nothing is created"; exit 2; }
URL=$(gh issue create --parent "$P" --title "$TITLE" --body-file - <<'SUB_TASK_END'
<the supplied SUB_TASK block, verbatim>
SUB_TASK_END
)
GRC=$?
[ "$GRC" -eq 0 ] || { printf '%s\n' "$URL"; echo "HALT: gh issue create failed (exit $GRC); look for a half-created sub-issue in the tracker, and never re-run this block"; exit 2; }
LAST=$(printf '%s\n' "$URL" | tail -n 1 | tr -d '\r')
SUB=${LAST##*/}
case "$SUB" in ''|*[!0-9]*) printf '%s\n' "$URL"; echo "HALT: gh issue create returned no issue URL; there is nothing to verify, and the create block must never be re-run"; exit 2;; esac
printf 'CREATED: #%s %s\n' "$SUB" "$LAST"
py -3 "$VPL" --sub "$SUB" --parent "$P" --json
```

The block's last line prints the verifier's verdict and is step 5; read its `verdict` as described
below. The line before it, `CREATED: #<n> <url>`, is printed first so the new sub-issue's number
survives whatever the verifier then says. If the lookup comes back empty the first `HALT` fires:
the four-row verdict table below is what this mode branches on, and an unresolvable path produces
no verdict at all — that silence must never be read as `linked`, or as anything else.

**Before running the block, check the body against its delimiter.** The `SUB_TASK` text is pasted
between the `SUB_TASK_END` lines, so if any line of that text is exactly equal to `SUB_TASK_END`
(and likewise any line of the bare title is exactly equal to `BARE_TITLE_END`), the shell ends the
here-document there and the rest runs as commands. Check that no body line is equal to its
delimiter; if one is, halt and report it rather than editing the text.

**The create block must never be re-run.** Once `CREATED:` has printed, the sub-issue exists; a
second run of the create block makes a duplicate. Any follow-up — a repair, a retry of the verifier
— uses the repair block below, with the number from the `CREATED:` line.

How the block is built, and why:

- **The helper is `VPL`'s sibling**, never found by a second, independent search (that search could
  resolve to a different copy). If it is missing, an older vendored copy has
  `verify_parent_link.py` but was never given the helper: the block halts loud, names the missing
  helper, and names the fix — list `.claude/scripts/compose_subissue_title.py` in the consuming
  project's sync configuration `files` array, then sync.
- **The project's conventions file is passed explicitly** with `--conventions`, so the plugin's own
  copy is never read in its place. The title shape is declared once, in that file's
  `issueTitle.subIssue`; to see it, print `issueTitle.subIssue.format` and
  `issueTitle.subIssue.legend` from there. This document does not restate either.
- **`<k>` is the sub-task's ordinal** from its id in the handoff plan (`t16` gives `16`).
- **The parent, effort tag, ordinal and sub-issue number are written in single quotes** because
  each is a number or a fixed tag that can never hold a single quote; inside single quotes the shell
  expands nothing, so a pasted `$(...)` stays literal text and fails the digits check instead of
  running. The shell trims only leading and trailing whitespace, removes at most one leading `#`,
  rejects anything not all digits (internal whitespace included) with a named `HALT`, and strips
  leading zeros (`0638` is `638`) before `gh`, the helper and the verifier see the value.
- **The bare title and the body each enter through a quoted here-document**, each with its own
  delimiter, so no character in either can alter the command. The title is handed over as
  `--title="$BARE"`, one word, so a title that begins with dashes is still a value, not an option.
  The body goes to `gh` with `--body-file -`, never inline as `--body`.
- **Never retry with a title that lacks the parent reference.**

Exit `0` is `composed`; exit `2` is `refused`, and nothing is created. The refusal's JSON carries
`cause`, `reason` and `remediation`. The causes, in the order the helper checks them:

| Cause | What it means |
|---|---|
| `conventions-missing` | the conventions file, its `issueTitle` block, `issueTitle.subIssue.format`, or a present and valid `issueTitle.pattern` is absent or unreadable (or the project root could not be determined) — add the block named in `remediation` |
| `format-malformed` | the declared format lacks or repeats a placeholder, or is not led by the effort tag |
| `parent-missing` | `PARENT_ISSUE` is empty (or only a `#`) |
| `parent-not-positive-integer` | `PARENT_ISSUE` is not a positive integer (one leading `#` is allowed) |
| `subtask-missing` | no sub-task ordinal was supplied |
| `subtask-not-positive-integer` | the sub-task ordinal is not a positive integer (`16`, not `t16`) |
| `bare-title-invalid` | the bare title is empty, spans lines, holds a control character, or already starts with an effort tag |
| `pattern-mismatch` | the effort tag is not a declared one, or the composed title fails `issueTitle.pattern` |

**The create is a request, never a fact.** `gh issue create` exits `0` when the request was
accepted, not when the link exists — which is why the block reads the link back with the verifier
immediately, using the sub-issue number it parsed from the created URL.

Branch on the verifier's `verdict`. The verdict set and the repair budget both live in
`.claude/work-item-conventions.json` → `issueLink` and its nested `parentLink` block, which is
the single source of truth for both; where the table below and that file ever disagree, the
conventions file governs. The table exists because the per-verdict *action* genuinely lives
nowhere else:

| Verdict | What it means | What this mode does |
|---|---|---|
| `unverifiable` | the resolver itself could not be reached — `gh` missing, unauthenticated, or the query failed | Halt loud. The create command's own exit code is never read as the answer. |
| `no-parent` | GitHub reports no parent for the new sub-issue | Run the repair block below, never the create block, up to `issueLink.maxRepairAttempts` time(s) — read the count from the conventions file, never hardcode it here. Still `no-parent` once the budget is spent → halt. |
| `foreign-parent` | GitHub reports a parent, but it names a different issue | Halt. Never re-parent automatically — reassigning an issue's parent is a destructive tracker mutation with no undo. |
| `linked` | GitHub reports the expected parent | Proceed to write the brief. |

**The repair block** is for the `no-parent` verdict only. It looks the scripts up the same way,
attaches the existing sub-issue to its parent with `gh issue edit`, and re-runs the verifier with
`--repair-attempted`. Fill in the sub-issue number from the `CREATED:` line and the parent number;
run it once per repair attempt, whole, in a single Bash invocation. It creates nothing.

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
py -3 "$VPL" --help >/dev/null 2>&1 || { echo "HALT: verify_parent_link.py not found; no parent-link verdict is possible, so nothing is repaired"; exit 2; }
P='<PARENT_ISSUE>'
P=$(printf %s "$P" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'); P=${P#\#}
case "$P" in ''|*[!0-9]*) echo "HALT: PARENT_ISSUE must be an issue number such as 638 or #638; nothing is repaired"; exit 2;; esac
P=$(printf %s "$P" | sed 's/^0*//')
[ -n "$P" ] && [ "${#P}" -le 18 ] || { echo "HALT: PARENT_ISSUE must be a positive number of at most 18 digits; nothing is repaired"; exit 2; }
SUB='<sub>'
SUB=$(printf %s "$SUB" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'); SUB=${SUB#\#}
case "$SUB" in ''|*[!0-9]*) echo "HALT: the sub-issue number must be digits (take it from the CREATED line); nothing is repaired"; exit 2;; esac
SUB=$(printf %s "$SUB" | sed 's/^0*//')
[ -n "$SUB" ] && [ "${#SUB}" -le 18 ] || { echo "HALT: the sub-issue number must be a positive number of at most 18 digits; nothing is repaired"; exit 2; }
gh issue edit "$SUB" --parent "$P" || { echo "HALT: gh issue edit failed; the parent link is not repaired"; exit 2; }
py -3 "$VPL" --sub "$SUB" --parent "$P" --repair-attempted --json
```

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
