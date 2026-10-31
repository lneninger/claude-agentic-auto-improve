# Forms review — fullstack-code-reviewer

- **Commit:** `1c51beb` (feature/113-parent-branch-delivery-rule), "fixed layout warning forms, origin read for every judged contract, and the records-not-local refusal"
- **Contract:** `.claude/concepts/2026-10-30-parent-branch-delivery-rule.md` (approved; the fourth amendment: R-10 freshness refusal, N2 clearing, fixed forms)
- **Previous review:** `plain-records-review-fullstack-code-reviewer.md` (W1-W6, N1, N2)
- **Files:** `.claude/scripts/pr_merged.py`, `.claude/scripts/land_contract.py`, `skills/advance/SKILL.md`, `skills/pr-merged/SKILL.md`, `skills/pr-merged/references/contract-completion.md`
- **Run:** `test_parent_branch_rule_text` (32 tests, OK). The long suites were not run, as asked.

## Previous findings: are they closed?

| Prior | State | Evidence |
|---|---|---|
| W1: a failed lookup gave `[]` | closed | `pr_merged.py:4713-4718`: a lookup that returns None gives `unverifiable` |
| W2: origin read only when a candidate existed | closed | `pr_merged.py:4726-4735`: origin is read whenever a sub-task remains, with no candidate needed |
| W3: the freshness refusal was lost | closed | `pr_merged.py:4232-4248`: R-10 runs before G-1, for every contract, and also under `--dry-run` |
| W4: `/advance` showed the warning under one move only | closed | `skills/advance/SKILL.md:123`: a preamble line covers every move |
| W5: a failed landing listing gave `[]` | closed | `land_contract.py:2000, 2056-2058` |
| N1: no parent branch | closed | `pr_merged.py:1657` |
| N2: the warning clears once complete | closed, but the meaning of "complete" is wrong (W1 below) | `pr_merged.py:4724`, `1657` |

## Checks the caller asked for

1. **Fixed forms.** The key is absent for an unjudged contract (`layout is not None` is the gate, and `land_contract.py:2056` too). It is `[]` only after the lookup succeeded and the origin read succeeded or was not needed. It is `held` while a Records pull request is open, and `unverifiable` when the lookup or the origin read fails. The reasons are a closed set of three (a test pins it). Clearing on completion uses a wrong test of "complete" (W1). The warnings are computed only under `--status` / `--resume`. That matches the contract's surface (Data Shapes row: "`layout_warnings` in `--status --json` and in the Landing Report"; N-3: "every judged `--status` reads origin"). It does **not** hide a genuine single-branch delivery from `--status`, because the warning is derived from facts on every call. It does make "absent" ambiguous in every other mode's JSON (W2).
2. **R-10.** It comes after G-5, before G-1, and is not tied to the layout. It writes nothing on any branch and is also active under `--dry-run`. An unreadable origin gives exit 10 with an origin-naming detail. Legitimate cases pass:
   - **Fresh checkout:** local equals origin, so it passes.
   - **Records pull request already merged, stale checkout:** refused. This is the intended case, and the remedy works: a fresh flat worktree holds the records.
   - **First-ever recording:** `ls-tree` on a missing folder exits 0 with no output, so origin gives `{}` and the run passes. `test_a_layout_defect_alone_still_never_refuses_a_recording` covers it.
   - **Same delivery re-run:** R-10 is skipped, which is correct because that path writes nothing.

   No loop under the normal cwd. One cwd-dependent loop exists (N1). No unhandled exception: `_run` catches OSError and Timeout, `origin_records` turns every failure into None, and `yaml.safe_load` is guarded. One new soft dependency exists (N2).
3. **Landing Report.** Absent when unjudged, `unverifiable` on a failed listing, and otherwise `layout_warnings_for(...)`. It never halts. There is a contract inconsistency on clearing (W3), and the detail names the wrong ref (N3).
4. **R-7 intact.** R-10 compares only whether a record exists (`tid not in records`). It reads no `base_ref`, no `base_is_default` and no parent branch. No other refusal on the recording path reads the layout (`pr_merged.py:4293`). The per-PR path writes only the mapped sub-task's own record, and closes its sub-issue when merged into any accepted base (`pr_merged.py:4423-4431`).
5. **Leftovers.** No removed symbol is left in the scripts or skills. Hits appear only in history comments in tests and in the work-item log. `test_parent_branch_rule_text.py:288` still lists `"G-7"` as a removed token, although G-7 is live again (N4).
6. **Fail-open, Windows, wrong tree, injection.** No shell strings: every git call is an argv list. Paths use `as_posix()` and `--full-tree -z`. `splitlines()` handles CRLF. `land_contract` runs git in `wt` throughout. There is one fail-open, and it is advisory: W1.

---

## Findings

### WARN

**W1: a failed record counts as "delivered", so the warning clears while a sub-task still remains** (`.claude/scripts/pr_merged.py:4724` and `:4735`)
```python
elif all(t.id in records for t in tasks):
    report["layout_warnings"] = []  # nothing remains to deliver: the warning clears
...
remaining=any(t.id not in evidence for t in tasks))
```
**Problem.** R-8 (N2) clears the warning only when "no sub-task remains to deliver". A sub-task whose pull request closed without merging has a record with `status: failed`. That sub-task has not been delivered: `is_delivered` (`pr_merged.py:3169`) rejects any record that is not `completed` + `verified: github`. Here, merely having a record counts as delivered.

Take t1 merged into the default branch on the web (a genuine single-branch delivery) and t2 failed. Then `--status` reports `[]`, the form the contract reserves for "every read succeeded with nothing to report". This is a fail-open on the very form this commit was meant to fix, and `/advance` would show no remedy. It is advisory only, so it does not block shipping on its own, but it reproduces the class of W1 from the previous review. No test covers a failed record.

**Fix.** Use the one shared reading of "delivered":
```python
def _delivered(rec): return bool(rec) and rec.get("status") == "completed" and rec.get("verified") == "github"
elif all(_delivered(records.get(t.id)) for t in tasks):
...
remaining=any(not _delivered(evidence.get(t.id)) for t in tasks))
```
Alternatively, use `is_delivered(tasks, records, delivery, defects)[0]`, which also covers a Contract Delivery Record. Add a test: t1 off the parent branch, t2 failed, so `single-branch-delivery` is present.

**W2: in a judged contract's non-status JSON, "absent" is overloaded** (`.claude/scripts/pr_merged.py:4712`, `:4674-4704`)
**Problem.** R-8 says "The key is absent for an unjudged contract". After this commit the key is also absent for a **judged** contract in these outputs: `--pr` recording runs, `--record-delivery`, `--dry-run`, plain runs and `--preconditions`. The last one returns at `:4704`, before the block. The previous code emitted the key in every mode.

Recording runs skipping the warning is defensible: no extra fetch, and the contract names `--status --json` as the surface. But a consumer that reads a recording run's JSON and sees no key would conclude "not judged". `skills/pr-merged/SKILL.md:589` describes the forms under `--status --json` only, and nothing tells the skill to run `--status` after recording a web merge in order to see the warning (Bypass row 6).

The contract's "origin is read whenever the contract is judged" does not limit itself to read-only modes either. N-3 lists `--dry-run` among the modes that fetch, but the code excludes `--dry-run`. This is a divergence the HANDOFF does not declare.

**Fix (pick one).**
- (a) Amend R-8 in one line: "present only in `--status` / `--resume` output, and in the Landing Report; elsewhere absent whatever the judgement". Add a step to `/pr-merged`: after a recording run of a judged contract, run `--status --json` and show `layout_warnings`.
- (b) Emit the key in every mode, at the cost of one fetch per recording run.

**W3: the contract contradicts itself on the Landing Report, and the code takes one side silently** (`.claude/scripts/land_contract.py:2057`)
**Problem.**
- R-8/N2: the warning clears once the contract is complete.
- R-9 and Bypass row 6: the later landing's report repeats the warning.
- The landing halts with `not-complete` unless the move is `complete` (`land_contract.py:2020`). So under R-8 the Landing Report would always be `[]`, and row 6 could never hold.
- The code calls `layout_warnings_for(...)` with the default `remaining=True`, which means it repeats the warning (row 6). That violates R-8's literal text.
- R-9 also lists `held` among the landing's forms, yet the landing never asks about open Records pull requests and never produces `held`. That is correct in practice, because the records branch being open is the landing's normal input.

**Fix.** Amend the contract with one sentence: "The Landing Report is the one place the warning is shown on a complete contract; `held` does not apply to the landing, which reads the records branch itself". The alternative is to pass `remaining=False` and drop row 6's "repeats it". Either way, the HANDOFF must say which one.

### NIT

**N1: R-10 refuses for good when the script runs from a subfolder with a contract path** (`.claude/scripts/pr_merged.py:2574` vs `:2876`)
**Problem.** `load_records` reads `RESULTS_DIR` relative to the cwd. `origin_records` uses `--full-tree`, so it ignores the cwd (deliberately, per W1 of the implementation notes). From a subfolder, `find_contract(<path>)` succeeds and `records == {}`, so G-7 refuses on every run. The remedy, a fresh worktree, does not fix it, so an operator who follows it exactly loops. This fails closed (exit 9, nothing written), and it is better than the old behaviour, which wrote into a subfolder-relative path.

**Fix.** Resolve `RESULTS_DIR` against `git rev-parse --show-toplevel` once in `main()`, or refuse with `run from the repository root` when the cwd is not the top level.

**N2: `--record-delivery` now depends on `origin/HEAD`** (`pr_merged.py:2379-2380`, `:4237-4243`)
**Problem.** When `refs/remotes/origin/HEAD` is unset (a repository made by `git init` + `remote add`), `default_branch()` falls back to `master`. On a `main` repository the fetch then fails, and every `--record-delivery`, dry run included, exits 10 with the remedy `git fetch origin master`, which cannot succeed.

**Fix.** Make the remedy `git remote set-head origin -a`, then rerun, when `default_branch_or_none()` is None.

**N3: the landing's `unverifiable` detail names `origin/<default>` even when the failed listing was the parent or records ref** (`land_contract.py:2000, 2058`)
**Problem.** The detail and the remedy (`git fetch origin <default>`) can point at the wrong ref.

**Fix.** Record which ref failed, and pass a detail that names that ref.

**N4: the text test still forbids `G-7`, and G-7 is live again** (`.claude/scripts/tests/test_parent_branch_rule_text.py:288`)
**Problem.** The skills cannot name the guard the script prints (`"guard": "G-7"`). `contract-completion.md` works around this with "exits 9 with the reason `records-not-local`".

**Fix.** Narrow the token to the removed meaning, for example `G-7 single-branch`. This is a test edit, so it belongs to the implementer.

**N5: no test pins R-10's unreadable-origin branch** (`pr_merged.py:4238-4243`)
**Problem.** `TestRecordingRefusesStaleLocalRecords` covers the refusals and the positive control, but nothing covers exit 10 when the origin cannot be read on `--record-delivery`. A regression to `held = _origin() or {}` (fail-open) would pass the suite.

**Fix.** Add the test, with `origin="ref-missing"`, exit 10, nothing written, and the same under `--dry-run`.

---

## Data-First audit

- **Data Shapes:** partly met. W1 (the meaning of "complete"), W2 (absent in modes other than status) and W3 (the landing's clearing and `held`) are divergences from R-8/R-9's literal text. None is declared in the HANDOFF.
- **Reused Mechanisms:** met. One `layout_warnings_for`, shared by both scripts. `_origin()` is cached once per run. `_refuse` and `_open_records` are reused. W1's fix should reuse `is_delivered`, not a new predicate.
- **Files to touch:** all five files are in the contract's list. No off-area drift.
- **Registries:** no new mechanism or term. INTEGRATION has no change of surface.

## Summary

| Severity | Count |
|---|---|
| BLOCKER | 0 |
| WARN | 3 |
| NIT | 5 |

**Verdict: fix then ship.**

**Top priority fix:** W1. Count only a `completed` + `verified: github` record as delivered when clearing the warning, and add the t1-off-parent / t2-failed test. W2 and W3 need a one-line contract amendment each, or the alternative code change.
