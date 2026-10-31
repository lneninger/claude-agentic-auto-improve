# Last-fix review (fullstack-code-reviewer)

- **Commit:** `c7aeb90` on `feature/113-parent-branch-delivery-rule` ("fix(113): a failed or unverified record keeps the warning, and the landing names the listing that failed")
- **Files:** `.claude/scripts/pr_merged.py` (+8/-8), `.claude/scripts/land_contract.py` (+6/-3)
- **Contract:** `.claude/concepts/2026-10-30-parent-branch-delivery-rule.md` (approved, amended through 2026-10-31). Read: R-7 to R-10, the Amended line, Bypass rows 5 and 6, and Implementation notes "Forms review (2026-10-31)".
- **Prior review:** `forms-review-fullstack-code-reviewer.md` (W1, W2/W3, N3).
- **Not run:** the long suites (landing, cleanup), because memory is low. The commit message says these two have not been re-run on this commit either. I read the tests added in `456735a`.

## (1) W1: "delivered" is `is_delivered(tasks, records, {})`

`pr_merged.py:4724` and `:4735`. `is_delivered` (`pr_merged.py:3147-3184`) with `delivery={}`:
- `defects` is None, so that clause is skipped.
- `tasks` empty means not delivered.
- A sub-task with no record means not delivered.
- `status != "completed"` or `verified != "github"` means not delivered.
- The base clause (`:3175`) is guarded by `delivery is None`, and `{}` is not None, so it is skipped.

So the predicate is exactly "every sub-task has a record with status completed and verified github". That is R-8's W1 wording.

- A completed and verified record with `base_is_default: true` counts as delivered. That is correct here. The question is "does a sub-task remain to deliver", not "did it reach the parent". Such work is already on the default branch, and the warning's own remedy says nothing needs undoing. Once every sub-task is delivered, the warning clears (N2). The Landing Report then repeats the fact (R-9). The landing calls `layout_warnings_for` with `remaining=True`, so it still reports `single-branch-delivery` for a complete contract. That matches R-9.
- The reverse case is also correct: a completed and verified record into the parent (`base_is_default: false`) counts as delivered.
- Failed and `verified: none` records keep the warning. `TestDeliveredMeansCompletedAndVerified` (`test_pr_merged.py:14176-14208`) pins both cases, plus the positive control that a parent-base record plus a default-base record clears to `[]`. Because of that control, a later refactor of `delivery is None` into `not delivery` (an empty dict is falsy) would fail the suite.
- Multi-block contracts: tasks are non-empty and keyed by id. The local check runs first. If it is not met, `else` merges origin through `merge_evidence` (origin wins in read-only modes, because `records == stored_records`) and re-asks on the evidence. Correct.
- Single-block contracts: `layout is None`, so the branch is never entered and the key stays absent. A judged contract with zero sub-tasks now reads as not delivered, so it reads origin instead of clearing blindly through `all([]) == True`. The only possible result is `[]` or `unverifiable`, which is stricter and allowed by "[] only when every read succeeded".

## (2) N3: the failed ref is named, and a failed parent listing halts

- `layout_warnings_for(..., failed_ref)` (`pr_merged.py:1653-1656`): the detail names the ref, and the remedy is `git fetch origin <ref minus "origin/">`. `split("/", 1)[-1]` keeps names that contain a slash: `origin/docs/<slug>-records` gives `docs/<slug>-records`, and `origin/release/x` gives `release/x`. The `--status` caller passes `"origin/" + base` (`:4729`), so its output is unchanged.
- Landing (`land_contract.py:1990-2003`): `failed_listing` keeps the first non-parent ref that failed (records branch, then `origin/<default>`), and that ref is passed through at `:2061`.
- Halting on a failed parent listing is safe in practice. I checked locally: `git ls-tree -r --name-only <ref> -- <missing paths>` exits 0 with no output. `rev_parse` has already proven the ref is a commit (`:1996`). So `rc != 0` happens only on a broken or partial object store, a timeout (124) or a spawn failure (127). Those are real failures to read the landing's own input. Before this commit, they silently read as "no records and no briefs". The halt happens at P1, before any merge, push or reset, and before `judged`, so it is fail-closed for unjudged contracts too. P0, GH_REPO, fetch and the worktree are not affected: the listing still runs in `wt`, and the fetches happen before `_land`. When `--parent` is not fetched, `parent_ref` is `HEAD`, and the halt says "at HEAD". The halt also matches the existing behaviour at `:2008`, where a failed blob read on any ref already halts `unverifiable` at P1.

## (3) R-7

Intact. The diff touches only the read-only `--status`/`--resume` branch (`pr_merged.py:4712`, guarded by `read_only`) and the landing's report. No recording path calls `layout_warnings_for` or the new predicate (I grepped the callers: `cleanup_delivered.py:270`, `pr_merged.py:1802/3651/4505` are unchanged and pass a real `delivery` or None).

## (4) New fail-open, Windows, wrong tree, injection

None found.
- The ref strings come from `slug` and `parent`, which are already used in the same `_git` argv list. No shell is involved.
- The remedy is text only and is never executed.
- `splitlines()` handles CRLF.
- Every git call uses `cwd=wt`.

---

## Findings

### BLOCKER
None.

### WARN

**W1: the halt on a failed parent listing goes against R-9's text, and the contract does not record it.** `land_contract.py:2000-2002`
```python
if ref == parent_ref:  # the parent's records and briefs cannot be read: nothing can be judged
    raise _Halt("unverifiable", "P1", "cannot list the records and briefs at %s" % ref)
```
R-9 says: "A failed listing gives `unverifiable`. The landing never halts on any of them (W3)." Bypass row 6 says "`unverifiable` for a failed ... landing listing". The 2026-10-31 forms-review note describes N3 only as "the landing's `unverifiable` detail and remedy name the ref whose listing failed". The behaviour itself is right. The parent's briefs feed `declared_topology` and `select_linked_brief`, which R-9 names as the landing's own safety. Without them, P1 cannot identify the parent, so a halt is the fail-closed answer, consistent with `:2008`. But this is a behaviour change that the commit message declares and the contract does not. A later reviewer reading R-9 literally would call it a regression. The test `test_the_parent_branch_listing` (`test_land_contract_identity.py`, added in `456735a`) accepts `("landed", "unverifiable")`, so it does not pin the halt either.
**Fix (contract text plus test, no production change):** add one sentence to R-9: "A failed read of the parent's own records and briefs (its listing, or any blob read) halts `unverifiable` at P1, because P1 cannot identify the parent without them. A failed listing of the Records branch or `origin/<default>` only gives the `unverifiable` warning, and the landing goes on." Then narrow `test_the_parent_branch_listing` to assert `outcome == "unverifiable"` and `gate == "P1"`, with nothing pushed.

### NIT

**N1: the new halt carries no remedy.** `land_contract.py:2002`. The `layout_warnings` form tells the operator to run `git fetch origin <branch>`, but this halt says nothing. Add `remedy="run git fetch origin %s and rerun" % parent`. When `parent_ref` is `HEAD`, also say that the worktree's objects could not be read.

**N2: a failed Records-branch listing can still surface as `not-complete` with the wrong remedy.** `land_contract.py:2003` and `:2023-2027`. This predates the commit, but now it stands next to the new parent halt. If `origin/docs/<slug>-records` fails to list and that branch is the only place a record lives, the move is not `complete`. The landing then halts `not-complete` with "commit the record to docs/<slug>-records and push it", although the record is there and only unreadable. The halt is fail-closed, but the reason is misleading. Fix: when `move != complete` and `failed_listing` is set, halt `unverifiable` naming `failed_listing`.

**N3: `{}` as a "skip the base check" sentinel is implicit.** `pr_merged.py:4724` and `:4735`. The meaning depends on `delivery is None` at `:3175`. The positive-control test guards it, so this is a NIT. A keyword such as `is_delivered(..., check_base=False)` would say what it means.

**N4: `off_parent` counts unverified completed records as evidence.** `pr_merged.py:1659-1662`. This predates the commit. The test is `status == "completed"` without `verified == "github"`, so a `verified: none` record counts as evidence for the warning while it does not count as delivered. That leans toward warning, which is fine for an advisory signal, but the two readings now differ. If R-8 means "a completion record" as "a record `is_delivered` counts", add the `verified` check.

---

## Summary

| Severity | Count |
|---|---|
| BLOCKER | 0 |
| WARN | 1 |
| NIT | 4 |

**Verdict:** fix then ship. The code is correct. W1 needs one sentence added to R-9 and a narrower assertion in the parent-listing test. The two long suites (landing, cleanup) must be re-run on this commit before merge.

**Top priority fix:** add the parent-read halt to R-9 and pin it in `test_the_parent_branch_listing`.
