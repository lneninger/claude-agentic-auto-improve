# Last review: fullstack-code-reviewer, parent-branch-delivery-rule (HEAD aee9cc2)

**Commit reviewed:** `aee9cc2` fix(113): an unreadable origin is unverifiable, exact origin commands, and the R-10 accept of an R-8 failure
**Contract:** `.claude/concepts/2026-10-30-parent-branch-delivery-rule.md` (approved, amended 2026-10-30 with R-10 / W7, B1, W1, W2)
**Scope:** `.claude/scripts/pr_merged.py`, `land_contract.py`, `check_version_bump.py`, `skills/advance/SKILL.md`, `skills/pr-merged/SKILL.md`, `skills/pr-merged/references/contract-completion.md`, `undeliverable-sub-task.md`, and the argv update in `.claude/scripts/tests/test_pr_merged.py`. I did not run any suites; the caller runs them separately.

**Verdict:** FIX THEN SHIP

---

## Answers to the five questions

1. **B1/W1/W2.** Every path where origin cannot be read now stops with exit 10 and `github-unverifiable` before any accept branch. That holds with or without `--accept-single-branch` and under `--dry-run`: G-7 at `pr_merged.py:4364`, R-10 at `pr_merged.py:4283`, and the listing or blob read in `origin_records` at `pr_merged.py:2901-2921`. The live report never offers `--record-delivery` or the accept when origin cannot be read, because `pr_merged.py:4619` sets the candidates to unknown and `next_command_for` then falls to the plain `/pr-merged <pr>` arm. The refspec and `GIT_TERMINAL_PROMPT=0` are correct. Two gaps remain. The new listing depends on the folder the script runs from (W-1 below). The read-only side effects are not documented (N-3).
2. **R-10 extension in `landing_evidence_holds`.** It cannot vouch for other sub-tasks: evidence is checked one sub-task at a time, and only the R-10 path writes `layout: single-branch-accepted` on a sub-task record. It does hide the bypass from the Contract Delivery Record, though. The limit "only a pull request that merged before the upgrade" is **not enforced and not even described**: the amended R-10 text and Bypass row 6 ("including one opened before this rule") drop it. My recommendation is to **keep the extension but narrow it**, and to escalate the approval scope to the user (B-2).
3. **`accept_prs` / `next_command_for`.** It prints one accept per pull request, removes duplicates, and appears only when every failure is of the R-8 kind, so other failures keep `/design-first`. It never prints a command that G-3 or `not-merged` would refuse. It can still print one that G-5 refuses (N-1). And the accept it prints leads into a G-4 refusal whose remedy undoes the accept (B-1).
4. **`land_contract.py` P0.** The halt on an unreadable contract is correct and fails closed. One small point (N-4).
5. **New issues.** One cwd fail-open regression (W-1), one loop (B-1), and one lost pointer (W-2). On Windows the paths and line endings are fine: posix paths, and `splitlines` handles CRLF. I found no injection: every argv is a list and the refspec starts with `+`, so a branch name cannot inject an option.

---

## BLOCKER

**[BLOCKER] B-1: R-10 leaves the sub-issue open, and recording that pull request again undoes the accept. G-4 points the owner straight into that loop.**
`pr_merged.py:4524-4547` (the R-8 path), `pr_merged.py:4263-4309` (R-10), `pr_merged.py:4345` (G-4)

```python
web_merged = (layout is not None and verdict == "merged" and not cross_repository
              and pr.get("baseRefName") == base and ...)
if (verdict == "merged" and task_issue is not None and not args.dry_run
        and not web_merged and ...):
    sub_issue_closed = close_sub_issue(...)
...
rec = build_record(..., failure="single-branch-delivery" if web_merged else None)
```

**Problem:** R-8 deliberately does not close the sub-issue. R-10 replaces the failed record with a completed one but also never closes it. A judged contract must have a parent issue, since `no-parent-issue` is a layout defect, so the later parent-branch landing always reaches G-4. G-4 then refuses: "open sub-issue(s) would be left behind: #N; close each, or **record its own pull request**". If the owner records it (`/pr-merged <A's pr>`), the per-PR loop has no guard for an existing accepted record. It recomputes `web_merged = True` and overwrites the accepted record with a new `failed` / `single-branch-delivery` record. That brings back `escalate`, then the accept, then G-4 again. This breaks R-9 (no endless loop) and the promise in Bypass row 6(b) that "the later parent-branch landing records". The row 6 tests pass `sub_issues=[]` (`test_pr_merged.py:10519`), so they never reach this path.

**Fix (both parts):**
```python
# R-10 path, inside the loop over r8_ids, after building rec:
issue = (state.get("sub_tasks", {}).get(task.id) or {}).get("issue")
if writing and issue is not None:
    rec["sub_issue_closed"] = close_sub_issue(issue, pr.get("url", ""))

# per-PR loop: an owner's accept of THIS pull request is never re-judged (R-6 spirit)
prior = records.get(task.id) or {}
accepted_here = (prior.get("layout") == SINGLE_BRANCH_ACCEPTED
                 and _norm(str(prior.get("pull_request") or "")).rstrip("/")
                     == _norm(str(pr.get("url") or "")).rstrip("/"))
web_merged = (not accepted_here) and (layout is not None and verdict == "merged" and ...)
# and keep `layout` / `note` on the rewritten record when accepted_here
```
Add a row 6 test: a parent issue with A's sub-issue open, then accept A, then run `/pr-merged <A>` again. A's record must stay accepted, and the landing must not be refused by G-4.

---

**[BLOCKER] B-2: The user's approval limit for R-10 ("only a pull request that merged before the upgrade") appears nowhere: not in the code and not in the amended contract.**
`pr_merged.py:4263-4309`, `pr_merged.py:1803-1812`, contract R-10 (`:81-89`) and Bypass row 6 (`:104`)

**Problem:** No code compares `mergedAt` with any adoption instant, and no adoption instant is stored anywhere (a grep for `upgrade` in `pr_merged.py` finds nothing). The amended R-10 lets the accept clear any R-8 failure, and Bypass row 6 widens that to "including one opened before this rule", which means after it as well. Worse, `escalate` now actively **prints** the accept for every R-8 failure (`next_command_for`, `:1931-1938`). A web merge into the default branch made after the upgrade is therefore met with a ready-to-type bypass command, which turns the parent-branch rule into a speed bump. That is broader than what the user approved, and the contract was amended without saying so.

**Fix:** pick one option, and the user has to choose.
- (a) **Enforce the limit as approved.** Record the moment this consumer adopted the rule, for example `parentBranchRule.adoptedAt` written once into the state store or the conventions file the first time the R-8 path runs. The accept then refuses with G-3 `merged-after-rule` when `pr.mergedAt >= adoptedAt`. After that point, `escalate` prints the accept only for records whose `merged_at` falls before it, and `/design-first` for the rest.
- (b) **Ask the user to re-approve the broader R-10** as written. Then record the wider scope in the contract's Amended line and in a JOURNAL entry.

Until one of these lands, the implementation matches the amended text but not the approval, so this blocks.

**On the `landing_evidence_holds` extension itself (`:1659-1675`): keep it, but narrow it.** It is per-task. An accepted record vouches only for its own sub-task, and only R-10 writes `layout: single-branch-accepted` onto a sub-task record (the `--record-delivery` writer puts `layout` on the Contract Delivery Record, which `load_records` skips). So it cannot launder other sub-tasks. Two gaps remain:
1. It does not check `status == "completed"` or that the record is a genuine R-10 replacement. A hand-edited or merged-in record carrying `layout: single-branch-accepted` would count. Narrow the rule to: `verified == "github" and status == "completed" and layout == SINGLE_BRANCH_ACCEPTED and base_is_default is True and note starts with "replaces failed record"`.
2. The Contract Delivery Record of the later landing carries no trace that one block bypassed the parent branch, because `planned["layout"]` is set only under `--accept-single-branch`. Add `accepted_blocks: [<ids whose record is accepted>]` to `planned` whenever any evidence record is accepted. That way the Completion Verdict and the audit trail still see the bypass.

---

## WARN

**[WARN] W-1: The new origin listing depends on the folder the script runs from, so run from a subfolder it reads "no records". That is the W1 failure again.**
`pr_merged.py:2901`
```python
code, out = _run(["git", "ls-tree", "--name-only", ref, "--", folder + "/"])
```
**Problem:** In this form, git treats the path argument as relative to the current folder and prints names relative to it as well. The `_tree_names_at` it replaces deliberately used `<ref>:<folder>` so that "the answer never depends on the folder the process stands in" (its own docstring, `:2619-2625`). Run from any folder other than the repository root, the path matches nothing, exit is 0, `found` is `{}`, and the result is "readable, no records". That is exactly the fail-open W1 meant to close. Separately, `core.quotePath` quotes any non-ASCII file name, so `file_at_commit` then fails and that contract becomes permanently `unverifiable`.
**Fix:**
```python
code, out = _run(["git", "ls-tree", "--full-tree", "--name-only", "-z", ref, "--", folder + "/"])
...
for path in (p for p in out.split("\0") if p):
```
`--full-tree` makes both the path argument and the output relative to the repository root. `-z` stops the quoting. Add an argv-pinning test for the exact form. If the contract's W1 note must stay byte-exact, amend it to name the `--full-tree` form.

---

**[WARN] W-2: When origin cannot be read, the live report also loses the "merge the open Records pull request" pointer, and its reason blames GitHub.**
`pr_merged.py:4614-4632`, `pr_merged.py:1916`

**Problem:** Origin is read even while a Records pull request is open, because the guard only asks that `_open_records()` is not None. When that read fails, every candidate is set to unknown (`:4619`). `records_pr_url` is computed afterwards and only from known candidates (`:4628-4632`), so the move stops naming the open Records pull request, which is the correct next step. Instead it shows `/pr-merged <pr>` with the reason "GitHub could not be asked", which is wrong because GitHub answered and origin did not. Setting the candidates to unknown also changes `report["delivery_candidates"]`, so the JSON then says GitHub did not answer about a candidate it did answer about.
**Fix:** read origin only when `_open_records() == []`, because an open Records pull request already holds back the defect and the accept. Copy the candidates before setting them to unknown, or set a separate `origin_unverifiable` flag. In `next_command_for`, use the reason "origin/<default> could not be read; run git fetch origin <default> and rerun" when that flag is set.

---

**[WARN] W-3: R-10 overwrites the failure record, which goes against the skill's own rule "Deleting a failure record ... should be visible as a pattern".**
`pr_merged.py:4296-4306`, `skills/pr-merged/SKILL.md:~591`

**Problem:** `write_record` replaces the file. The only trace left is the free-text `note`. The original `contract_impact`, the time of the failure, and the fact that a second R-8 on the same sub-task would be a pattern are all lost outside git history.
**Fix:** keep the replaced record in a structured form, for example `rec["replaces"] = {"status": "failed", "failure": R8_FAILURE, "merged_at": old.get("merged_at"), "pull_request": old.get("pull_request")}`. Amend R-10's "What it writes" list in the same change.

---

## NIT

- **N-1** `pr_merged.py:1803-1812`: `accept_prs` is printed even when a delivery is already recorded for another pull request. G-5 (`:4255`) refuses the accept before R-10 runs, so in that edge case R-9 prints a refused command. Gate `accept_prs` on `delivery is None` (pass it into `advance`, or filter the arm in the caller).
- **N-2** `pr_merged.py:482-486`: `_pr_reference` falls back to the raw link text, so a record whose `pull_request` is not `/pull/<n>` (one with a trailing `#…` or `?…`, or a hand edit) produces `/pr-merged <garbage> --record-delivery --accept-single-branch`. Return `None` when no number matches, so `all(accepts)` fails and `/design-first` is kept.
- **N-3** `pr_merged.py:2873-2885`: the fetch has side effects that should be documented. It changes `refs/remotes/origin/<base>`, which every worktree and the main checkout share, and it writes `FETCH_HEAD` and may trigger auto-maintenance. All of that also happens under `--status` and `--dry-run`. Add `--no-write-fetch-head` (git 2.29 or later) and say in the docstring that a read-only run refreshes the tracking branch. `GIT_TERMINAL_PROMPT=0` does not cover an SSH passphrase or host-key prompt, so for an `ssh://` remote set `GIT_SSH_COMMAND` to `ssh -o BatchMode=yes` when the user has not set it. The 60 s `_run` timeout is the only backstop today.
- **N-4** `land_contract.py:3052-3054`: a contract file that is *missing* (`FileNotFoundError`) is reported as `unverifiable`, which tells the owner to retry, and a retry cannot help. Name the path and add `remedy="restore .claude/concepts/<slug>.md on the parent branch, then rerun"`. The halt is still correct.
- **N-5** `pr_merged.py:4283`: R-10 reads origin only to check that it can be read and ignores what it holds. If origin already holds a completed record for that sub-task, for example an accept already merged from another worktree, the stale local failed record is accepted again and conflicts with the next Records pull request. Apply `merge_evidence(held, records, stored_records)`. When the sub-task is no longer failed there, refuse with G-7 `records-not-local`.
- **N-6** `skills/pr-merged/references/contract-completion.md:35`: the text says the accept refuses while a sub-task is awaiting merge. The R-10 branch does not check `awaiting_merge`, which only the delivery branch checks. Make the text say that only the delivery form checks it.
- **N-7** `pr_merged.py:4359-4378`, carried over from earlier work and not a regression: `--accept-single-branch` with *local* landing evidence still stamps a real parent-branch landing as `single-branch-accepted`. The comment at `:4361` names this mislabel. Consider refusing the accept when `landing_evidence_holds` is already true, because the plain command is the right one then.

`check_version_bump.py:142` (strip once, then use the value for both the ref and the check) is correct and has no finding.

---

## Contract audit

- **Data Shapes:** R-10's record matches the contract: `completed`, `verified: github`, `base_ref` and `base_is_default` as GitHub reports them, `layout`, and `note`. Only partly met overall: the approval limit is missing (B-2), and the delivery record does not show accepted blocks.
- **Reused Mechanisms:** `origin_records` now re-implements `load_records_at`, stricter and in a different listing form (W-1), so there are now two readers of committed records with different failure semantics. Acceptable for B1's need to fail closed, but `load_records_at` should take a `strict=True` mode rather than live alongside a copy. Partly met.
- **Files touched:** every changed file is listed in `Files to touch`. No change is outside the declared area.
- **End-User View:** no UI surface is touched, so it does not apply.
- **Registries:** no new reusable mechanism or vocabulary term (`single-branch-accepted` is already contract vocabulary). No JOURNAL entry: R-10 was amended into the contract before implementation, so it is not a divergence found after implementation. B-2 is an approval-scope question for the user, not a lesson from the contract.

## Summary

| Severity | Count |
|---|---|
| BLOCKER | 2 |
| WARN | 3 |
| NIT | 7 |

**Verdict:** FIX THEN SHIP

**Top priority fix:** B-1. Close the sub-issue in the R-10 accept, and make the per-PR recording keep an accepted record of the same pull request. Without both, the standard layout (a parent issue with sub-issues) loops between G-4 and R-8 and the later landing never records. B-2 needs a decision from the user, not just code.
