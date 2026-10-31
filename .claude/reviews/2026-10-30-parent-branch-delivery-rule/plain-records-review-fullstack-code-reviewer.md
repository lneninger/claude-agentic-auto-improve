# Plain-records review: fullstack-code-reviewer

**Reviewed:** HEAD `d6fd022` ("fix(113): records are plain and the layout is reported as a warning"), plus the test-only commit `35f6115` before it.
**Contract:** `.claude/concepts/2026-10-30-parent-branch-delivery-rule.md` (approved; amended per the user's "records are plain" direction). Sections checked: R-6, R-7, R-8, R-9, the Removed list, Bypass rows 5, 6 and 9, and the Implementation notes (B1, W1, W2, N-3, last-review W-2).
**Files:** `.claude/scripts/pr_merged.py`, `.claude/scripts/land_contract.py`, `skills/advance/SKILL.md`, `skills/pr-merged/SKILL.md`, `skills/pr-merged/references/contract-completion.md`, `skills/pr-merged/references/undeliverable-sub-task.md`, `.claude/registries/VOCABULARY.md`.
**Not run:** the long suites (landing, cleanup). Low memory, and the caller asked me not to. `py_compile` passes on both scripts.

## Answers to the six questions

1. **R-7 (records are plain): met.** No record write judges the layout:
   - `build_record` lost `failure`.
   - The sub-task loop closes the sub-issue of a web-merged pull request (`pr_merged.py:4403`).
   - `--record-delivery` has no layout refusal (`:4273`).
   - `single-branch-delivery` left `LAYOUT_DEFECT_REASONS` (`:1537`).
   - `layout_defects` gates only `dispatch` (`advance`, `:1820`).
   - The default branch is always in `declared_bases` (`:4082`), so a web merge reads as `merged` and is recorded. It is not skipped as `merged-elsewhere`.
2. **R-8 (layout warning): partly met.** It is derived from facts, blocks nothing, and has no key for single-block or exempt contracts in `--status`. But W1, W2 and N1 below apply.
3. **R-9 (the landing's own safety): structurally met, but weak as the only signal.**
   - The landing reads no record verdict. P1 completion, topology, P7 merge and P8 verification are intact.
   - Its report repeats the warning.
   - The `/advance` loop does not reliably show the warning to the user (W4). While a Records pull request is open it is suppressed, and the suppression looks like "clean" (W1). So in practice a one-branch delivery is first seen in the Landing Report.
   - The completion flip and the `/advance` loop with a one-branch delivery: `delivery-unrecorded`, then the plain `--record-delivery`, then `complete`, then `/advance` when the briefs declare a parent. This is the same as before the accept existed.
4. **Leftovers: none in production text.** No hits in scripts, skills, references, agents, `CLAUDE.md`, `MECHANISMS.md`, `INTEGRATION.md` or `VOCABULARY.md`. The remaining mentions are in:
   - negative test assertions;
   - `JOURNAL.md` (append-only history);
   - the work-item log;
   - the contract's Removed list.
5. **Kept B1/W1/W2: intact.**
   - `origin_records` is unchanged: `ls-tree --full-tree --name-only -z`, and None on any failure.
   - `fetch_default_branch` is unchanged: explicit refspec, `GIT_TERMINAL_PROMPT=0`.
   - The removed `origin_unreadable` re-read command is no longer needed, because recording no longer depends on origin.
   - The `delivery-unrecorded` commands are exact.
6. **New fail-open: yes, two (W1, W5).**
   - No Windows path or CRLF issue: values come from YAML or are `strip()`ed, and paths go through `as_posix()`.
   - No git on the wrong tree: `--full-tree` in pr_merged, `cwd=wt` in the landing.
   - No injection: every git and gh call is an argv list.

## Findings

### BLOCKER

None.

### WARN

**W1: `layout_warnings: []` when GitHub could not be asked about Records pull requests (fail-open), and also when one is open.** `.claude/scripts/pr_merged.py:4659-4660`
```python
report["layout_warnings"] = []
if _open_records() == []:
```
`open_records_pull_requests` returns None on any `gh` failure. That leaves the list empty, which reads exactly like "judged, clean".
- This is the same defect class B1 closed for origin. The rule there was "never the warning and never its absence on a failed read". Now that the warning is the only layout signal (R-9), this read can fail the same way.
- An open Records pull request also yields `[]`. That one is contract-mandated, but it cannot be told apart from clean either. The draft Records pull request usually stays open for the whole mid-flight period, so the warning is in practice suppressed until the records merge.
- No test covers the None case: `test_an_open_records_pull_request_holds_it_back` asserts only "not the warning".

Fix:
```python
if layout is not None:
    open_now = _open_records()
    if open_now is None:
        report["layout_warnings"] = [{"reason": "unverifiable",
            "detail": "GitHub could not be asked whether a Records pull request of this contract is open",
            "remedy": "check gh auth status and rerun"}]
    elif open_now:
        report["layout_warnings_deferred_to"] = open_now[0].get("url")   # or omit the key; never a bare []
    else:
        ...  # today's branch
```
The second arm needs a one-line contract note, because the reason set is closed. At minimum, the None arm must not be `[]`.

**W2: origin is read only when a known Delivery Candidate exists. This diverges from R-8, and it produces a false negative mid-flight.** `.claude/scripts/pr_merged.py:4662`
```python
held = _origin() if any(c.get("known") for c in candidates) else records
```
R-8 says the warning "is computed from the local records merged with `origin/<default>`'s records", with no condition on candidates. Here is how the gate hides a genuine single-branch delivery:
1. A sub-task pull request is web-merged into master.
2. `/pr-merged` writes its record, base_is_default true, to `docs/<slug>-records`, which targets master.
3. That Records pull request merges.
4. `/advance` then runs `--status` from a parent-branch checkout, as `skills/advance/SKILL.md:109` mandates. That checkout does not hold the record, and there is no landing pull request yet, so there is no known candidate.
5. Origin is never read, and `layout_warnings` is `[]`.

This is exactly the window where the remedy ("deliver the remaining sub-tasks through the parent branch") can still be acted on. The code comment justifies the gate ("the stale-checkout case"), but the HANDOFF and the contract do not.

Fix: read origin whenever `layout is not None` and no Records pull request is open. N-3 already documents the fetch's side effects for read-only modes. Otherwise, amend R-8 to say "origin is read only when a known candidate exists" and accept the window.

**W3: `--record-delivery` from a stale checkout writes delivery-filled records over the real parent-branch records. This is a regression of the removed `records-not-local` guard.** `.claude/scripts/pr_merged.py:4273-4293`

The setup: a checkout whose local results folder lacks the sub-task records that origin/master holds (the Records pull request merged on the web, and the checkout was never refreshed). Every guard passes:
- G-1: the candidate kind is `single-branch` from the empty local records.
- G-3 and G-4: the sub-issues are closed.
- G-6: no Records pull request is open.

The run then writes `delivered_by: contract-delivery`, `base_ref: master`, `base_is_default: true` for every sub-task. Those sub-tasks really merged into the parent branch. The consequences:
- The R-8 block right after raises a false `single-branch-delivery`, because `merge_evidence` lets this run's records override origin's.
- The next Records pull request carries modified versions of the true records.

The removed G-7 `records-not-local` refusal caught this. That check is about freshness, not layout, so R-7 ("no layout check refuses a recording") does not forbid it. It was removed only because the contract's Removed list names G-7 as a whole.

Escalate to the user: either restore a non-layout freshness guard, or accept the risk in the contract. The guard would be: when `_origin()` holds a record for a sub-task this checkout lacks, refuse with guard G-6 and reason `records-not-local`, remedy "run in a flat worktree cut fresh from origin/<default>". When origin is unreadable, exit 10 `github-unverifiable` before writing. The guard should apply to every contract, not only judged ones.

**W4: the `/advance` skill shows `layout_warnings` only under `delivery-unrecorded`.** `skills/advance/SKILL.md:337`

A sub-task web-merged mid-flight leaves the move at `dispatch`, `awaiting-merge` or `complete`. None of those sections tells the agent to read or show `layout_warnings`. The JSON field therefore reaches the user only through the Landing Report, after the remaining sub-tasks were (or were not) moved to the parent branch.

Fix: add one line to the Step 2 preamble (around `:119`): "On every move, when the status answer's `layout_warnings` is not empty, show each entry's `remedy` to the owner before taking the move. A warning blocks nothing. An `unverifiable` entry gets its re-read remedy."

**W5: the Landing Report can give `[]` on an unreadable listing, and gives `[]` for an unjudged contract.** `.claude/scripts/land_contract.py:1995-2000, 2054`
```python
if not rev_parse(wt, ref): continue
for rel in (out.splitlines() if rc == 0 else []):
...
base_report["layout_warnings"] = ... if judged else []
```
The P1 listing treats a failed `ls-tree` as "no files". So the records on `origin/<default>` or the records branch can silently drop out, and `layout_warnings_for(parent, records, [], None)` returns `[]`. That contradicts B1, "unverifiable, never an empty list". The read is old, but this commit gives it a new consumer.

Separately, an exempt contract gets `layout_warnings: []` (present and empty), which reads as judged-clean. The status side omits the key for the same contract.

Fix:
- Pass `origin_base=default` when the `default_ref` listing failed (`rc != 0`).
- Omit the key, rather than `[]`, when `judged` is false. `test_land_contract_identity.py:1392` pins "present and empty" for the judged parent case only, so it stays valid.

**W6: contract drift: `skills/pr-merged/SKILL.md` is not in `Files to touch`.**

This commit edits it, and so did `aee9cc2` earlier. Add it to the block's `Files to touch` in the contract. `derive_area.py` reports `uncategorized` for both the contract and the diff, so the area check finds no off-area drift.

### NIT

**N1: a false positive when the parent branch is unresolved.** `.claude/scripts/pr_merged.py:1657`
```python
or bool(r.get("base_ref") and r.get("base_ref") != parent_branch)
```
`parent_branch` is None when there is a `no-parent-branch`, `parent-is-default` or `ambiguous` defect. Then every completed record that has a `base_ref` fires `single-branch-delivery`. That includes records whose base is the children's declared parent under an `ambiguous` header mismatch. The defect already explains the layout. Guard it with `parent_branch is not None and ...`. The `base_is_default` arm can stay.

**N2: the warning never goes away, and its remedy does not fit a finished contract.**

For legacy #58/#82, and for any contract that is fully delivered, the warning persists after completion and still says "Deliver the remaining sub-tasks…". This is the contract's own text. Ask the user whether the remedy should drop its second sentence once `is_delivered` holds.

**N3: every judged `--status` now makes a `gh pr list` call** (`_open_records()`, `:4660`), even with no candidate. Offline, that feeds into W1.

**N4: the long suites are not yet re-run.** The landing suite (`test_land_contract*.py`) and the cleanup suite are not re-run on this commit (the commit message says so). The landing gained a new `delivery_layout` call at P1 and a new key in every halt and report. Run both before merge.

## Data-first audit

- **Data Shapes:**
  - Layout defect reasons (closed) match the contract: five, with `single-branch-delivery` removed.
  - The Layout warning reason set matches, with one undeclared addition: the code emits `unverifiable` in `layout_warnings`. R-8 and B1 require it, and VOCABULARY names it, but the Data Shapes row lists only `single-branch-delivery`. Add `unverifiable` to that row.
- **Reused mechanisms:** reused, with no parallel implementations: `delivery_candidates`, `merge_evidence`, `origin_records`, `delivery_layout` in the landing, and one `layout_warnings_for` shared by both scripts.
- **Off-area drift:** none detectable (the areas are uncategorized). W6 is the drift in `Files to touch`.
- **Registry janitor:** I am deferring the MECHANISMS entry until the verdict is ship. The entry: `layout_warnings_for` (pr_merged), a fact-derived, never-stored, non-blocking warning shared by `/pr-merged --status` and the Landing Report. Extend by: add a reason to the closed set in the contract's Data Shapes and in this one function. VOCABULARY is already updated: "Layout warning" was added, "Accepted single-branch delivery" was removed, and "Layout defect" and "Contract Delivery" were amended. INTEGRATION has no API or event surface here.

## Summary

| Severity | Count |
|---|---|
| BLOCKER | 0 |
| WARN | 6 |
| NIT | 4 |

**Verdict: fix then ship.**

**Top priority fix:** W1 and W2 together. The R-8 warning is now the only signal of a single-branch delivery. Today it is `[]` on a failed Records pull request read, and `[]` mid-flight from a parent-branch checkout because origin is not read without a candidate. Make both cases read as "not judged" or "unverifiable", never as clean. W3 needs a decision from the user, because it reverses a guard the contract removed.
