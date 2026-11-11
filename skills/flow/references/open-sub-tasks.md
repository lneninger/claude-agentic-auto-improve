# Open the sub-tasks: points 3 to 4 of /flow Step 2.7

Moved verbatim out of `skills/flow/SKILL.md` Step 2.7. `PRM` and the parent issue number come from that step.

**Before anything below:** `len(sub_tasks) >= 2` has already been confirmed by Step 2.7, and the sub-tasks are opened in ordinal order.

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

   **Finding sub-issues in the issue list.** A sub-issue title carries
   its parent reference. Print `issueTitle.subIssue.format` and `issueTitle.subIssue.legend` from
   the project's `.claude/work-item-conventions.json`; do not restate either from memory.

   - Hide sub-issues from the list: `gh issue list --search "no:parent-issue"`.
   - List one parent's children: the `parentLink.parentListCommand` the conventions file
     declares (cited by name, not restated here).

**No new `status:` value.** Sub-issue creation sits between `designing` and `implementing` in
the brief's lifecycle, but the state store already carries the finer-grained record, and a
seventh status would need every consumer of the existing six updated for a distinction this file
does not need. This is a decision, not an omission.
