# Fix review: fix(113) close W1 to W6 and the R-8 head-branch gap

Reviewer: fullstack-code-reviewer. Scope: commit `a343ced` only (`check_version_bump.py`, `land_contract.py`, `pr_merged.py`, `version-bump.yml`), judged against the earlier report `code-review-fullstack-code-reviewer.md` and the approved contract `.claude/concepts/2026-10-30-parent-branch-delivery-rule.md`. No suites were run.

**Verdict:** FIX THEN SHIP. 0 BLOCKER, 3 WARN, 6 NIT.

## Status of the earlier findings

| Finding | Status | Where |
|---|---|---|
| W1 non-task heads into non-default bases | **Fixed** | `check_version_bump.py:158-160` |
| W2 workflow shell injection, no `permissions:` | **Fixed** | `version-bump.yml:6-7, 17-22` |
| W3 header `branch:` against the sub-task briefs' `base:` | **Fixed**, with a new R-6 gap at the landing (F2) | `pr_merged.py:1620-1624, 1686-1687`; `land_contract.py:3048-3058` |
| W4 stale checkout or legacy records steer a real landing to `--accept-single-branch` | **Not fixed.** The steer moved one command later, and an unreadable origin still fails open (F1) | `pr_merged.py:4436-4448, 4212` |
| W4 sub-point: `needs_accept` set on a failed open-records read | **Fixed** | `pr_merged.py:4464` |
| W5 matcher looser than L-3 | **Fixed**. No change on real data (see below) | `pr_merged.py:1430-1448` |
| W6 protected branches ignored | **Fixed**. A second, different reader remains (N4) | `pr_merged.py:1551-1569, 1586, 1603` |
| N3 / R-8 empty `headRefName` | **Fixed** | `pr_merged.py:4353` |

---

## WARN

**F1. W4 is not fixed. The origin read is fail-open, the `except Exception` is dead code that only hides a harness assertion, and G-7 still reads local records.** `pr_merged.py:4436-4448`, `:4212`, `:2576-2605`

1. **The degradation path is a return value, not an exception.** `_run` already catches `OSError` and `TimeoutExpired` (`:2074-2080`). `_tree_names_at` returns `[]` when `git ls-tree` fails, for example when `origin/<base>` is missing or the folder is absent. `file_at_commit` returns `None`. YAML errors are caught inside `load_records_at`. So in production an unreadable origin returns `{}`, and nothing raises. `evidence` then equals the local records, `needs_accept` is set, and R-9 prints `--accept-single-branch`. That is the original W4 behaviour. The read cannot tell "origin holds no records" from "origin could not be read".
2. **The `except Exception` catches only the test harness.** `_drive` patches `_run` with `_no_process`, which raises `AssertionError("this fixture must reach no process at all")` (`test_pr_merged.py:8717-8718, 8836`). Every `_drive` test with a layout, a known candidate and an answered open-records read now starts a git process. The production code swallows that assertion, which defeats the harness's guarantee. Production code is bent to fit the tests.
3. **Nothing fetches.** In `--status`, `fetch_default_branch` runs only for early review and `--owner-resolved` (`:3616`, `:3987`). In W4's own scenario (the Records PR merged on the web, the checkout not refreshed), `origin/<base>` is as stale as the local folder. The test `test_a_stale_checkout_does_not_steer_...` passes only because `_drive_with_origin_tree` makes origin fresh by fiat.
4. **The steer is only moved, not removed.** In the stale case, the live report now names `/pr-merged <pr> --record-delivery`. That run reaches G-7 at `:4212`, which still calls `landing_evidence_holds(layout, tasks, records, ...)` with the **local** records. It refuses `single-branch-delivery`, and its remedy text says "already merged on the default branch: the owner runs ... `--accept-single-branch`". The owner reaches the human-only accept one command later. G-7 must not simply switch to `evidence`: the loop at `:4227` would then write `contract-delivery` records for tasks whose real records exist only on origin.
5. **The legacy-records half of W4 is unaddressed.** Records from before 0.5.0 have no `base_ref`. Also, `{**origin, **records}` lets an older local record override the newer one on origin. Only records written by this run should override.

Fix:
- Delete the `try/except`. Teach `_drive` to answer `_tree_names_at` (default: an empty origin), the same way it already fakes `file_at_commit`. If a guard must stay, the only types that could reach it are `(OSError, subprocess.SubprocessError)`, and `_run` already handles those.
- Before the read, call `fetch_default_branch(base)` once, and probe with `git rev-parse --verify origin/<base>`. Make the origin read return `Optional[...]`, with `None` meaning unreadable. When it is unreadable, do **not** set `needs_accept`. Instead add a report note: "origin/<base> could not be read; run `git fetch origin <base>` and rerun".
- Merge as `{**origin, **{k: v for k, v in records.items() if stored_records.get(k) != v}}`.
- At G-7, when origin evidence holds but the local records do not, refuse with a distinct reason (for example `records-not-local`). Its remedy should be "run again in a flat worktree cut fresh from origin/<base>", the same wording G-6 already uses, and it should not name the accept.
- Add a test where `ls-tree` fails while `records_prs=[]`.

**F2. The new landing P0 `ambiguous-parent` check ignores R-6, and it is a second implementation of the `delivery_layout` check.** `land_contract.py:3048-3058`
- **Ordering is correct.** The check runs after `declared_topology` and before `GH_REPO`, the fetch and the worktree, using only local disk reads.
- **Contracts that keep the old path are unaffected:**
  - With no sub-task `base:`, the contract returns `not-applicable` earlier.
  - With no header brief, `linked` is None and the check is skipped.
- **The problem: no status or block-count gate.** The landing check does not consult `read_contract_status` or the mergeable-block count. R-6 says "Status decides who is judged ... new refusals apply only to new recordings". An exempt contract with a parent branch whose old header brief's `branch:` differs from the children's `base:` now halts at the landing, while `/pr-merged` (`delivery_layout` returns None) says nothing.
- **Reason codes diverge.** A header brief at `branch: master` with children at `base: feat-x` gets `ambiguous-parent` here, and `parent-is-default` in `delivery_layout`.
- **Placeholder tests diverge.** The test here (`""`, `none`, `unknown`, `<`) is a third copy of the placeholder rule. It does not match the matcher's new `tbd` / `n/a`.

Fix: gate the check on `read_contract_status(contract_text) in JUDGED_STATUSES`. Better, call `pr_merged.delivery_layout(...)` and halt on its `ambiguous` / `parent-is-default` defect. That gives one check, one reason vocabulary and R-6 for free.

**F3. `effective_base` refuses the header mismatch with the wrong explanation.** `pr_merged.py:1686-1691`
The new `any(d["reason"] == "ambiguous" ...)` branch reuses the text "the Sub-Task Work Items of this contract disagree on base: or parent_issue:". For the new header-against-children defect, that is false: the children agree, and the header brief disagrees with them. The operator is told to make the children agree, which they already do. Fix: when the refusal comes from a layout defect, pass that defect's `detail` and `remedy` through.

---

## NIT

- **N1 (W1 hole question).** A sub-task PR whose head is misnamed (not `task/*`) into the parent branch is now unchecked in CI, which is the same reach CI had before 113 (master-only). The hole is bounded. P7b `--raise` writes minor + 1 ("already at" when the sub-task chose exactly that), and P8 `--exact` halts any other value at the landing. R-8 / `map_pr_to_subtask` may also not map such a PR. Acceptable. Consider stating in the docstring that `--exact` is the backstop.
- **N2 (W1).** If `--default-branch` arrives empty, `default_ref` is `origin/`. Every base then differs from it, so a non-task PR **into master** would skip the check (exit 0). GitHub always fills `repository.default_branch` for `pull_request`, but this tool's rule is "exit 2, never an allow". Return 2 on an empty `--default-branch` (`check_version_bump.py:146-147`).
- **N3 (W2).** The env quoting is correct. `contents: read` is sufficient: checkout with `fetch-depth: 0`, `merge-base` and `show` need only read access, and `--raise` (which commits) never runs in CI. No step needs more. No finding.
- **N4 (W6).** An absent key, `[]`, or a non-list gives `[default]`, which is correct and matches the landing for absent and `[]`. But the landing keeps its own reader (`land_contract.py:3033`, and `:1986`): `list(... or [default])`. On a malformed string value (`"release"`), it gives `['r','e','l',...]` while `protected_branches` gives `[default]`. Two readers of one key with different malformed-value semantics are a parallel implementation. Have the landing call `pr_merged.protected_branches`. Also, `_landing_config` is read twice per `delivery_layout` call (once for `version_raise_on`, once for `protected_branches`), which costs two `git show` calls. Read it once.
- **N5 (W6).** The `parent-is-default` topology arm (`pr_merged.py:1625-1626`) still says "declare the default branch as their base" when the base is a non-default protected branch.
- **N6 (W5).** On real data the matcher change is a no-op. All 15 distinct `contract:` values in `.claude/work-items/*.md` (12 contract paths, plus `none`, `none - XS/S route...` and `none - L item delivered...`) were compared against every slug under `.claude/concepts/` with the old any-token matcher and the new first-word stem matcher: **0 differences**. Remaining edges, none present today:
  - `none(pending)`, written with no space, reads `other`.
  - A value with a leading word such as `see .claude/concepts/x.md` used to match and now does not.

## Integration checks

- `landing_evidence_holds` is called at the live report with `evidence` and at G-7 with `records`. This is the cross-path drift in F1.
- `advance()` receives the local `records` with candidates computed from `evidence`, so its `kind` and its delivery reasons come from two sources. This works today only because `is_delivered` is not consulted for `kind`.
- No DTO, API or SignalR surface. INTEGRATION.md: not applicable.
- Off-area drift: none. All four files are in the contract's Files to touch.

## Janitor

- MECHANISMS.md: updated the "Brief linkage selector and matcher" entry (the first-word stem rule, `TBD` / `n/a`) and the "Plugin version check modes" entry (a non-task head into a non-default base is not checked).
- VOCABULARY.md / JOURNAL.md: nothing new. F1 to F3 are implementation gaps, not contract defects.
