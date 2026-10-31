# R-10 review: fullstack-code-reviewer, parent-branch-delivery-rule (HEAD b41525d)

**Commit reviewed:** `b41525d` fix(113): limit the R-10 accept to merges before the rule, make it sticky, and read origin by full tree
**Contract:** `.claude/concepts/2026-10-30-parent-branch-delivery-rule.md` (approved; amended twice, the second time for R-10 option (a))
**Scope:** `.claude/scripts/pr_merged.py`, `.claude/scripts/land_contract.py`, `skills/advance/SKILL.md`, `skills/pr-merged/references/contract-completion.md`. I read the R-10 tests in `test_pr_merged.py:14446-14800` to check coverage. I ran no suites. I ran `git ls-tree --full-tree --name-only -z` by hand from `skills/` (git 2.56.0.windows.2) to check W-1.

**Verdict:** FIX THEN SHIP

---

## Answers to the six questions

1. **B-2 (the limit).** The check is in place and correct where it runs. The accept refuses with G-3 `merged-after-rule` when GitHub's `mergedAt >= adoptedAt` (`pr_merged.py:4346-4352`). The check uses GitHub's `mergedAt`, not the record's copy. `advance()` prints the accept only when every failure is R-8, merged strictly before the cutoff, with no delivery recorded (`:1823-1831`). Anything else prints `/design-first`. The limit is weak in three places:
   - (a) An adoption record that exists but cannot be read counts as "absent". The limit then resets to *now* and the file is rewritten. This is fail-open (BLOCKER B-1).
   - (b) "Adoption = the first R-8 write" is per contract, so the first web merges of **every** contract are always acceptable, and the loop prints the accept for them (W-1, the weakest spot; this needs your decision).
   - (c) The adoption instant is read only from the local folder. A stale worktree or two sessions running at once each write their own instant (W-2).

   Forging needs a hand edit of a tracked file. Moving `adoptedAt` later, or deleting the file, widens the accept. That is owner-level tampering and outside the threat model, but deleting the file is indistinguishable from "a pre-amendment record" (see the fix to B-1).
2. **B-1 (the sub-issue, the sticky record, G-4).** Fixed:
   - The accept closes the sub-issue (`:4380-4382`).
   - A later plain `/pr-merged <pr>` for the same URL keeps the accepted record. `accepted_here` (`:4607-4612`) is checked before `web_merged`, and `layout`, `replaces` and `note` are copied forward (`:4634-4635`).
   - The later landing reaches G-4 with the sub-issue closed. Running G-4's remedy keeps the accept (tests at `:14647-14693`).

   No other path overwrites the accepted record:
   - `--resume`, `--status` and `--preconditions` are read-only (`:4038`, `:4184-4185`).
   - The delivery loop skips any task that already has a record (`:4479`).
   - A second accept of the same PR has no `r8_ids`, so it falls through to G-1.
   - The completion flip writes no records.

   Only a *different* pull request mapped to the same sub-task replaces it, and that is correct.
3. **Accepted evidence.** A *partial* record cannot satisfy `accepted_record()`: all five clauses are required, and `:14725` tests each one. A *complete* hand-made record does satisfy it, because nothing ties `replaces` to the record or to `adoptedAt` (N-1). `accepted_blocks` comes from local records, which is correct because G-7 `records-not-local` already stops a landing whose evidence exists only on origin.
4. **W-1 (`--full-tree -z`).** Correct. From a subfolder, `--full-tree` makes both the pathspec and the output relative to the repository root (checked by hand). `_run` decodes UTF-8, and `str.strip()` does not remove NUL. With `-z`, git does not apply `core.quotePath` quoting. `file_at_commit` uses `ref:path`, which is root-relative. A subfolder named `*.yaml` makes the blob read fail, which is reported as unverifiable, so it fails closed. The one leftover is the local half: `RESULTS_DIR` reads, and now `read_adoption`, still resolve against the current folder (N-3).
5. **W-2 (`origin_unreadable`).** It never prints a refused command or the accept. `needs_accept` is gated on `not origin_unreadable` (`:4731`). The layout defect is gated the same way (`:4734`). The `origin_unreadable` arm comes before the `needs_accept` arm (`:1926-1929`) and prints the plain `/pr-merged <pr>` with the origin reason. While a Records pull request is open, origin is not read and the pointer wins (`:1923`). One cosmetic leftover: N-2.
6. **New problems:**
   - The adoption write is not "in the same write as that record". It happens after the loop, as a separate, non-atomic file write (part of B-1).
   - `--dispatch` counts as a writing run, so it can write `adoptedAt` (N-4).
   - `land_contract.build_delivery_set` does not skip `rule-adoption.yaml` (N-5).
   - No injection: `yaml.dump` of an isoformat string, and list argv everywhere.
   - CRLF is handled by PyYAML.

---

## BLOCKER

**[BLOCKER] B-1: An adoption record that cannot be read resets the limit to "now" and is then rewritten. The guard fails open, against R-10's "never rewritten".**
`pr_merged.py:3574-3584`, `:4058-4059`, `:4289-4295`, `:4649`

```python
def read_adoption(contract_slug):
    ...
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except Exception:
        return None                      # unreadable == absent
    return _instant(data.get("adoptedAt")) if isinstance(data, dict) else None
...
adopted_at = read_adoption(slug)
adoption_instant = adopted_at or run_now  # None -> now -> every earlier merge is acceptable
...
if writing and adopted_at is None and ...:
    write_adoption(slug, run_now)        # and the evidence is overwritten
```

**Problem:** `read_adoption` treats three different cases as one None: "no file", "file present but unparsable", and "`adoptedAt` missing or not a timestamp". The caller then uses `run_now`, so every R-8 failure merged before this run passes G-3 `merged-after-rule`. `escalate` prints the accept for each of them, and the next writing run replaces the file with a new, later instant.

Realistic triggers in this repository's flow:
- Two worktrees each write `rule-adoption.yaml` (W-2), and their Records pull requests conflict add/add. The resolved file holds conflict markers, or one side was hand-picked.
- `write_record` truncates and then writes (`:2688-2694`), so a write that is killed part-way leaves an empty file, which reads as `{}` and then None.
- A hand edit that writes a non-ISO value.

This is the same "cannot read, so assume nothing" fail-open that B1 closed for origin.

The contract also says `adoptedAt` is written "in the same write as that record" (`:84`). The code writes the failed record in the loop (`:4636-4638`) and the adoption file only after the loop (`:4649`). If the process dies or times out in between, a failed record with no adoption file is left behind. The next run reads that as a pre-amendment record and adopts at a *later* instant, which widens the limit.

**Fix:**
```python
_ADOPTION_UNREADABLE = object()

def read_adoption(contract_slug):
    f = RESULTS_DIR / contract_slug / (ADOPTION_RECORD_NAME + ".yaml")
    if not f.is_file():
        return None
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
    except Exception:
        return _ADOPTION_UNREADABLE
    moment = _instant(data.get("adoptedAt")) if isinstance(data, dict) else None
    return moment if moment is not None else _ADOPTION_UNREADABLE
```
- When the record is unreadable, the accept exits 10 with `github-unverifiable` (a detail naming the file), `advance()` gets a cutoff of `datetime.min` (the accept is never printed, so `/design-first` is), and `_ensure_adoption` never writes.
- Also stamp `adopted_at: <instant>` into each R-8 failed record when `build_record` writes it, and use the earliest of that stamp and the file. Then a deleted or late side file cannot move the limit, a genuinely pre-amendment record is the one with no stamp, and "the same write" holds.
- Add tests:
  - a conflict-marker file
  - an empty file
  - `adoptedAt: yesterday`

  Each must refuse the accept, print `/design-first`, and leave the file byte-identical.

---

## WARN

**[WARN] W-1 (needs the user's decision): "adoption = the first R-8 write" is per contract, so the user's limit ("only pull requests that merged BEFORE the upgrade") never applies to a contract's first batch of web merges, and the loop prints the bypass for them.**
`pr_merged.py:4289-4295`, `:1823-1831`; contract `:84-86`

**Problem:** A web merge always happens before the run that records it. The run that records a contract's first R-8 failure sets `adoptedAt = run_now`, which is after that merge. So the merge counts as "before the rule", and the same run's `escalate` prints `/pr-merged <pr> --record-delivery --accept-single-branch`. Take a contract approved months after the upgrade whose owner merges both sub-task pull requests into master on the web, then runs `/pr-merged 61 62`. Both pull requests are accepted, and the whole contract bypasses the parent branch with a ready-made command. The limit only catches the *second and later* recording runs of a contract. `test_the_first_r8_failure_writes_adoptedat_in_the_same_write` (`:14488`) already sets up exactly this case. Contract line 86 ("Accepted limit") discloses it, so the code matches the text. But the text replaces the user's "upgrade" with "the first time this contract fails", which is a much weaker anchor than the approval wording.

**Fix options (the user picks one):**
- (a) A repository-wide anchor. `.claude/orchestrator/results/rule-adoption.yaml` is written once by the first writing run of this code in the repository, whatever the contract. The per-contract cutoff becomes `min(repo_adopted_at, contract_adopted_at)`. This is closest to "before the upgrade".
- (b) Per contract, but written on the contract's first *writing* run of any kind (its first `--pr`, `--record-subtask` or `--dispatch`), not its first R-8 failure.
- (c) Keep it as written, and record in the contract's Amended line and in JOURNAL that the user accepted "a contract's first web merges are always acceptable".

**[WARN] W-2: The adoption instant is read only from the local folder. A stale worktree, or two sessions, each adopt their own instant, and the accept still ignores what origin holds (last-review N-5, not fixed).**
`pr_merged.py:4058`, `:4289-4295`, `:4353`

**Problem:** Here is the sequence:
1. Worktree X records the R-8 failure for t1 at A1, and its Records pull request merges, so origin now holds `adoptedAt = A1`.
2. Worktree Z was cut before that. It has no adoption file and no t1 record.
3. t2 is merged on the web at T2 > A1.
4. Z records t2: `adopted_at is None`, so it writes `adoptedAt = now > T2`.
5. The accept of t2 passes `merged-after-rule`, even though t2 merged after this contract adopted the rule.

The accept does call `_origin()` (`:4353`), but only to check that origin can be read; it throws away what it reads. Separately, `write_adoption` uses `write_text`, not an exclusive create. Two runs at the same time in one worktree both see `None`, and the later instant wins. Across worktrees, the result is an add/add conflict, which then hits B-1.

**Fix:** In `_ensure_adoption` and in the accept, also read `file_at_commit("origin/%s" % base, "<results>/<slug>/rule-adoption.yaml")`. Use the earliest readable instant; an unreadable one counts as unreadable (B-1). Never write a new instant when origin already has one; copy origin's instead. Write with `open(f, "x")`, and on `FileExistsError` re-read the file. Add a test where origin holds `adoptedAt` and the local folder does not.

---

## NIT

- **N-1** `pr_merged.py:1676-1685`: `accepted_record()` does not check that `replaces` belongs to this record. A copied or hand-made record still counts. Add `_norm(replaces.pull_request) == _norm(rec.pull_request)` and `_instant(replaces.merged_at) is not None`. The `merged_at < adoptedAt` check needs the adoption instant, which `landing_evidence_holds` does not take; you could pass it in as an optional argument.
- **N-2** `pr_merged.py:4703-4714`: when origin cannot be read, `report["delivery_candidates"]` keeps the `kind` worked out from local evidence (it can say `single-branch`) next to a move that only offers a re-read. Add `"kind_source": "local"` or drop `kind` in that case so JSON readers do not act on it. Related: `needs_accept` is set while a Records pull request is open (`:4728-4732`). The command is right because `records_pr` wins in `next_command_for`, but R-7 says it should be reported only when no Records pull request is open.
- **N-3** `pr_merged.py:3576`: `read_adoption`, like `load_records` and `write_record`, resolves `RESULTS_DIR` against the current folder, while `origin_records` now reads from the repository root. Run from a subfolder, the local half sees no adoption and no records. This was already true before and is harmless today (no records means no accept), but it is now inconsistent with W-1's fix. Anchor `RESULTS_DIR` on `git rev-parse --show-toplevel` once in `main()`.
- **N-4** `pr_merged.py:4185`, `:4649`: `--dispatch` counts as a writing run, so it writes `rule-adoption.yaml` when an old R-8 record exists. The contract says "the first *recording* run". Gate `_ensure_adoption` on `args.pr or args.record_delivery`.
- **N-5** `land_contract.py:1414-1432`: `build_delivery_set` does not skip `rule-adoption.yaml` (or `contract-delivery.yaml`). Today that is harmless, because `advance()` reads `status` and the adoption record has none. But two different adoption files on two refs (the W-2 race) halt the landing as "two different records for rule-adoption", which looks like a sub-task problem. Skip both reserved stems, as `load_records` does.
- **N-6** `pr_merged.py:4613-4621`, `:4640-4645`: the sticky rewrite calls `close_sub_issue` again on the already-closed sub-issue and calls `record_merge_in_state` with base `master`, which the accept itself never does. Both are harmless, but the two writers of an accepted record now leave different state. Make them match one way or the other.

---

## Contract audit

- **Data Shapes:** partly met. The accepted record (`layout`, `replaces{failure, pull_request, merged_at, recorded_at}`, `note`, `sub_issue_closed`), `accepted_blocks`, the `rule-adoption.yaml` location and the skip in `load_records`, `load_records_at` and `origin_records` all match. Two things diverge:
  - "Written in the same write as that record" (`:84`) is not what the code does (B-1).
  - "Never rewritten" fails for an unreadable file (B-1).

  Neither divergence is justified in a HANDOFF, so both are defects, not lessons about the contract.
- **Reused Mechanisms:** met for this commit. `write_record`, `_instant`, `close_sub_issue` and `accepted_record` are reused on both paths. The duplicate reader of committed records from the last review (`origin_records` beside `load_records_at`) remains.
- **Files touched:** all four are in `Files to touch`, so nothing is off-area. The tests changed in the paired commit `d892075` are also listed.
- **End-User View:** not applicable, because no UI is touched.
- **Registries:** no new reusable mechanism. "Rule Adoption Record" / `adoptedAt` is a contract-local term, and if W-1 (a) is chosen it becomes repository-wide and belongs in VOCABULARY. No JOURNAL entry, because no divergence is justified.

## Summary

| Severity | Count |
|---|---|
| BLOCKER | 1 |
| WARN | 2 |
| NIT | 6 |

**Verdict:** FIX THEN SHIP

**Top priority fix:** B-1. An unreadable `rule-adoption.yaml` must fail closed (accept exits 10, `/design-first` is printed, the file is never rewritten), and the adoption instant should travel inside each R-8 failed record. W-1 needs your decision before shipping: as written, every contract's first web merges are acceptable.
