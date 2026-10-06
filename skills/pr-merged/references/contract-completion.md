## Contract completion, delivery records and the records pull request

`/pr-merged` ends a run in one of three ways, and the script decides which, never this skill: the contract is finished and the script wrote that down, the contract is not finished and the script says exactly what is still open, or the whole contract was delivered on one branch and that delivery still has to be recorded. This reference holds what the skill does with each answer.

**The script owns every decision.** `pr_merged.py` computes the Completion Verdict, fills the Review checklist, flips `Status`, and appends the run-log line. This skill never ticks a checklist line, never edits `Status` by hand, and never decides that a verification was skipped. It runs the script, relays what the script printed, and carries the tracked files the script wrote into a small pull request after one confirmation.

### Reading the answer

Print the report's `completion:` line exactly as the script printed it, on its own line before the Next Command line. The verdict is one of seven:

| Verdict | Meaning | What this skill does |
|---|---|---|
| `not-eligible` | The contract's `Status` is not `approved`. | Report it. Nothing was written. |
| `already-implemented` | An earlier run flipped it. | Report it. Nothing was written. |
| `pending` | A condition is unmet. `reasons` names each one with its remedy. | Relay every reason and its remedy. Never work around one. |
| `not-evaluated` | Only the delivery was checked (`--status`, `--resume`). | Report it. The script's `next` is the `--dry-run` command. |
| `unverifiable` | GitHub or git stopped answering while the flip was being checked. Nothing was flipped, and any records a writing run wrote stand. | Run the script's `next` command again once GitHub and git answer. In a dry run, stop before the confirmation. |
| `would-flip` | A dry run found every condition met. | Offer the real run (see the records pull request below). |
| `flipped` | The script wrote `Status`, the Implemented line, the checklist and the run-log line. | Run the records pull request steps below. |

Exit code 10 means GitHub or git could not be verified before the run's first write, so the run wrote nothing: sign in with `gh auth login`, then run the same command again. Exit code 9 is a refused delivery from `--record-delivery`: read the `guard` and `detail` fields and relay them.

### Recording a delivery made on one branch

A contract delivered by one pull request whose branch is not `task/<contract>/<id>` maps to no sub-task, so the loop used to report every sub-task as pending and offer `/advance`. When the report shows a `delivery_candidates` entry, or the Next Command is `/pr-merged <pr> --record-delivery`, dry-run it first, then follow the fixed order of the next section (one confirmation, then one writing run):

```bash
py -3 "$PRM" --contract <slug> --pr <number or link> --record-delivery --dry-run
```

The script asks GitHub and never takes the operator's word. It refuses with exit code 9, naming the guard, unless all of these hold: the pull request is the one the contract's own brief names (its branch or its `pr:` link) and merged into the default branch; the contract has no defects and at least one sub-task; no record has failed; no sub-issue is still open; no delivery is recorded for another pull request; and no records pull request is open. When the guards pass it writes one completion record per unrecorded sub-task and one delivery record. It never overwrites a record, closes an issue or cuts a branch. The same run then evaluates completion, so it can flip in the same step. The dry run shows the outcome without writing, and the writing run is the same command without `--dry-run`. A second run for the same pull request changes nothing.

Under `/flow`, recording is pre-authorized only for the brief's own `pr:` link. A person running `/pr-merged` is told the exact command and runs it.

### The records pull request

Whenever a writing run's `written_files` is not empty, the run wrote tracked files that no earlier commit contains. Put exactly those files in a small docs-only draft pull request. The state store is git-ignored and is never staged.

A writing run flips as soon as nothing is pending, and after the flip the owner can no longer name a skipped check. So the order is fixed, and the confirmation always comes before any writing run:

1. **A read-only dry run first, in the starting tree.** The skill's first call is always the command it would run, plus `--dry-run`. When that run's Next Command is `--record-delivery`, dry-run that command too. A dry run writes nothing, and its `completion.next` commands are writing runs: the reason starts with `writing run:`, and the skill never runs one before the confirmation.
2. **Stop only when the dry run cannot be confirmed.** A `pending` dry run does NOT stop here, because the confirmation is what clears an `owner_confirmation_needed` report and records the declared skips. Stop, relay the reasons, and write nothing only when the verdict is `unverifiable` or the exit code is 2, 9 or 10.
3. **Show the one confirmation**, built from the dry run: the branch name `docs/<contract-slug>-records`; every file the writing run will carry; every unchecked checklist line (state `no-evidence` or `reported-short`), asking which of them were really skipped or impossible; every `owner_confirmation_needed` report, each with the report that fixed the problem; every `review_warnings` entry; and any blocked report still unresolved. The owner may also name a check that is not on the checklist.
4. **On yes, disclose.** Post one comment on the Tracking Issue (`completion.tracking_issue.number`) with one line per text the owner marked, in exactly this form: `Not performed (<contract-slug>): <text>`. Post nothing when nothing was marked.
5. **Run for real, once, in the starting tree.** Repeat the command without `--dry-run`, carrying every `--owner-resolved <report file>` for each report the owner confirmed and every `--skipped "<text>"` for each marked text. Normally there is exactly one writing run. If a second is needed, such as a `--pr` run for sub-task pull requests plus a `--record-delivery` run, every writing run carries the same flags. The records pull request carries the union of `written_files` from every writing run in the session.
6. **Cut the branch in a flat worktree.** Fetch `origin/<default>`, then create a worktree directly under `<repo>/.claude/worktrees/` on `docs/<contract-slug>-records`, cut from `origin/<default>`. If the name is taken, use the suffix `-2`, then `-3`. Never use a `task/...` name.
7. **Copy exactly that union of `written_files` there** from the starting tree, commit them with a message that names the contract, and push the branch.
8. **Open a draft pull request** whose body says `Refs #<tracking issue>` and never a closing keyword. Name the branch and the files in the report.
9. **Remove the records worktree.** Then name the copies left in the starting tree: they duplicate the records pull request, and a later update of that tree can refuse to overwrite them.

Under `/flow`, hand the union of `written_files` to Step 8 of `/flow` instead of committing here, and follow the same order with Step 8's confirmation as the one confirmation.

### Remedies say "a fresh worktree", never "update this tree"

Once a records pull request merges, the starting tree is behind it and holds untracked copies of its files. Never tell the operator to update that tree. Every remedy after a records pull request merges is the same: run the command again in a flat worktree cut fresh from `origin/<default>`. The script's own remedies say the same, and nothing a later run needs lives only in the git-ignored state store.
