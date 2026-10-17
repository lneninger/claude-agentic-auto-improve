# Debug notes: own-repo work ships with no issue (issue 57)

- Symptom: most merged pull requests in this repo close no issue; briefs record `id: none`.
- Trigger: any free-text `/task` run, or any run that starts at `/design-first`, in this repo.
- Expected: work ends with an issue that the pull request closes, or an explicit recorded decline.
- Scope: always on this path; issues 47 and 50 closed correctly because they began as real issues.

## Phase 1: REPRODUCE
- Repro type: deterministic (read from history, then replayed with the verifier).
- Minimum steps:
  1. Take the brief `.claude/work-items/2026-10-15-subissue-title-parent-ref.md` (`id: none`, pull request 55).
  2. Run `py -3 .claude/scripts/verify_issue_link.py --brief <it> --pr 55 --json`.
- Observed symptom: verdict `not-applicable`, exit 0, `issue_link: none`. A success, no warning.
- Captured evidence: the brief's open-questions line "Open a tracker issue for this work? -> Assumed: no (id none). /ship Step 3.5 will ask once more at ship time." and its run log "closing link: not applicable, no tracker issue".

## Phase 2: ISOLATE
- Technique used: read each shipped pull request's brief and body.
- Per pull request:
  - 55: intake answered the issue offer by assumption ("no"), and `/ship` Step 3.5 never asked. Both asks are prose only.
  - 54: the run began at `/design-first` with no `/task`. `skills/design-first/SKILL.md` Step 3.6 writes a brief with `id: none` and, by its own text, asks nothing.
  - 53: records-only pull request with `Refs #50`. Correct, not a defect.
  - 41 to 46: tasks of larger contracts, linked to a parent. Out of this item's scope.
- Suspect region (narrowest): `.claude/scripts/verify_issue_link.py:463` (absent id returns success) together with `skills/task/SKILL.md` Step 2.5 point 6, `skills/ship/SKILL.md` Step 3.5, `skills/design-first/SKILL.md` Step 3.6.

## Phase 3: HYPOTHESIZE
- Root cause: "no issue" is one undifferentiated state. The brief cannot say whether the user declined, the offer was never made, or an agent assumed an answer. The offer is prose with no script check, so skipping it looks identical to declining. The verifier treats it as success, and the briefless path never offers at all.
- Why this explains the symptom: every route to `id: none` ends in `not-applicable`, exit 0, so nothing in the chain ever stops.
- Predictions:
  - If true: a brief with `id: none` and no recorded decision ships green (observed above).
  - If true: the three call sites share no field recording the offer's outcome (confirmed by reading them).
  - If false: the alternative is that the user declined every offer on purpose; the brief for 55 contradicts this (the answer was "assumed", not asked).

## Phase 4: VERIFY
- Verification design: replay the verifier on the pull request 55 brief.
- Observation: `not-applicable`, exit 0.
- Verdict: CONFIRMED.

## Proposed fix shape (for the contract, not yet designed)
- A recorded outcome of the issue offer in the brief (accepted, declined by the user, not asked), written by the three call sites.
- A repo-level switch in `.claude/work-item-conventions.json` that makes `/ship` halt on an absent id with no recorded user decline. This repo turns it on; other projects keep today's behaviour.
- `design-first` Step 3.6 makes the same offer instead of writing `id: none` silently.
