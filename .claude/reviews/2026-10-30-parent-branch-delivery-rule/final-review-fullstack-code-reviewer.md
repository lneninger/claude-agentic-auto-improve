# Final review: fullstack-code-reviewer, feature 113 fix commit 9e54793

**Reviewed:** `git show 9e54793` (HEAD of `feature/113-parent-branch-delivery-rule`): `.claude/scripts/pr_merged.py`, `.claude/scripts/land_contract.py`, `.claude/scripts/check_version_bump.py`, read against the surrounding code and `test_pr_merged.py` (14 000-14 080).
**Contract:** `.claude/concepts/2026-10-30-parent-branch-delivery-rule.md` (approved). R-7 says "A GitHub read that fails is reported as `unverifiable`, never as a layout defect". R-9 says the move never names a command G-7 would refuse.
**Suites:** not run, as instructed. The findings below come from reading the code.

**Verdict: FIX THEN SHIP.** 1 BLOCKER, 2 WARN, 5 NIT.

| Prior finding | Status | Where |
|---|---|---|
| F1 (W4) live report, unreadable origin | **Fixed** for `needs_accept` and the `single-branch-delivery` defect. The move still names a command G-7 will refuse (B1) | `pr_merged.py:4494-4531` |
| F1 (W4) `try/except` removed, fetch then probe, `Optional` result | **Fixed** | `pr_merged.py:2854-2864` |
| F1 (W4) merge order | **Fixed**: origin wins, a record written this run wins over origin. It differs from the suggested merge in one benign way (N4) | `pr_merged.py:2867-2874` |
| F1 (W4) G-7 `records-not-local` | **Fixed when origin is readable. Not fixed when it is not**: an unreadable origin falls through to the accept (B1) | `pr_merged.py:4251-4276` |
| F2 landing P0 via `delivery_layout` | **Fixed** | `land_contract.py:3054-3064` |
| F3 `effective_base` text | **Fixed** | `pr_merged.py:1698-1701` |
| N2 empty `--default-branch` | **Fixed** in every mode (the check comes before the mode branch) | `check_version_bump.py:142-145` |
| N4 one `protectedBranches` reader, config read once | **Fixed** | `pr_merged.py:1566-1574, 1594-1596`; `land_contract.py:1986, 3033-3034` |
| N5 protected-branch wording | **Fixed** | `pr_merged.py:1627-1630` |

---

## BLOCKER

**B1. An unreadable origin still fails open at G-7. With `--accept-single-branch` it records a single-branch delivery over a possibly real landing. Without the flag, the refusal points the owner to that flag.** `pr_merged.py:4251-4276`

```python
if layout is not None and not landing_evidence_holds(layout, tasks, records, pr.get("headRefName")):
    held = _origin()
    if held is not None and landing_evidence_holds(...merge_evidence(held, records, stored_records)...):
        return _refuse("G-7", "records-not-local", ...)
    # held is None -> falls through silently
if args.accept_single_branch:
    ...                      # accepted: contract-delivery records + layout: single-branch-accepted are written
elif layout is not None and not landing_evidence_holds(layout, tasks, records, ...):
    return _refuse("G-7", "single-branch-delivery", ..., remedy="... the owner runs ... --accept-single-branch")
```

`held is None` covers two cases: the fetch failed, or `origin/<base>` is not a ref. Both are exactly the "could not be read" state that the new docstring says "proves nothing either way". In this state:

- **`--record-delivery --accept-single-branch`:** the run passes G-7, writes a `contract-delivery` record for every task that has no local record, and writes the delivery with `layout: single-branch-accepted`. That is the W4 harm: a real parent-branch landing gets the wrong name, and its records are overwritten in the stale checkout. A later push or Records PR then conflicts with origin's real records.
- **`--record-delivery` without the flag:** the run refuses `single-branch-delivery`, and the remedy names `--accept-single-branch`. The steer is still there.
- **`--dry-run`:** the same path plans `layout: single-branch-accepted` and exits 0.
- **Live report (`pr_merged.py:4519-4525`, `next_command_for` at `:1887-1893`):** with `origin_unreadable`, `needs_accept` stays unset. The candidate is still known, so the move becomes `delivery-unrecorded` and names the plain `/pr-merged <pr> --record-delivery`. That is the command G-7 refuses (above), which breaks R-9 ("never the refused command"). The refusal then names the accept, so the chain from an unreadable origin to the human-only accept is two commands long instead of one.
- **No test covers any of these.** `TestOriginEvidenceNotLocalRefusesWithADistinctReason` drives only `origin="ok"`. `test_an_unreadable_origin_never_sets_needs_accept...` asserts only that the accept is absent from the commands, not that the move offers no refused command.

R-7 already gives the answer: "A GitHub read that fails is reported as `unverifiable`". Fix:

```python
if layout is not None and not landing_evidence_holds(layout, tasks, records, pr.get("headRefName")):
    held = _origin()
    if held is None:
        print(json.dumps({"error": "github-unverifiable",
                          "detail": "origin/%s could not be read, so the landing evidence cannot be checked; "
                                    "nothing was written. Run git fetch origin %s and run again." % (base, base)}))
        return 10
    if landing_evidence_holds(layout, tasks, merge_evidence(held, records, stored_records), pr.get("headRefName")):
        return _refuse("G-7", "records-not-local", ...)
```

In the live report, when `origin_unreadable` is set, the `delivery-unrecorded` move must offer the re-read (`/pr-merged <pr>` once `git fetch origin <base>` answers, or the "GitHub could not be asked" arm already at `:1894-1896`), not `--record-delivery`. One simple way: mark the candidates `known: False`, or pass a flag into `advance` / `next_command_for`.

Tests to add (exit 10, `world.snapshot()` unchanged, no `--accept-single-branch` anywhere in the output):
1. `--record-delivery --pr N` with `origin="ref-missing"`.
2. The same with `--accept-single-branch`.
3. The same with `--dry-run --accept-single-branch`. Also assert that no `delivery_planned` is reported.
4. Each of the three with `fetch_ok=False`.
5. `--status` with `origin="ref-missing"`: the commands name no `--record-delivery`.

**Is the owner's way out clear, and can it loop?** `records-not-local` itself is sound. It fires only when origin, read fresh, proves the landing and the local folder does not. A flat worktree cut from `origin/<base>` (or a `git pull`) brings the records local. The local-first check at `:4251` then passes and origin is never read again. No legitimate landing is blocked and nothing loops. The only gap is the unreadable case above.

---

## WARN

**W1. "Readable" is decided by the ref probe alone. A listing or blob read that fails after the probe still reads as "origin holds no records", which offers the accept.** `pr_merged.py:2854-2864` with `load_records_at` `:2601-2617` and `_tree_names_at` `:2595-2598`

`origin_records` returns `load_records_at(...)` once `rev-parse --verify` succeeds. But the reads after the probe still fail open:

- `_tree_names_at` returns `[]` for any non-zero `ls-tree`, for example the 60 s `_run` timeout, a lock error, or a corrupt pack.
- `file_at_commit` returning `None` is `continue`.
- A YAML error is `continue`.

So a partial or failed listing gives `{}` or fewer records. `landing_evidence_holds` is then false, `needs_accept` is set, and R-9 names the accept. G-7 does not reach `records-not-local` and falls through to the same steer. The fix review asked for "a test where `ls-tree` fails while `records_prs=[]`". The new test makes the probe fail (`ref-missing`), not the listing.

Fix:
- In `origin_records`, list with `git ls-tree --name-only origin/<base> -- <folder>/`. Exit 0 with empty output means a genuinely absent folder, and a non-zero exit means `None`.
- Return `None` if any listed `.yaml` file cannot be read or parsed. Keep `load_records_at`'s lenient behaviour for its other callers.
- Test: `origin="ok"`, with the stand-in's `ls-tree` answering `(1, "")`. Expect no accept offered and `origin_read` reported.

**W2. The fetch has no refspec, so it can succeed while `origin/<base>` stays stale. That is W4's stale-origin case again.** `pr_merged.py:2845-2850` (`git fetch origin <base>`)

`git fetch origin master` updates `refs/remotes/origin/master` only through the opportunistic update, which depends on `remote.origin.fetch` mapping that branch. In a clone narrowed with `--single-branch --branch <feature>`, or with a custom fetch refspec, the fetch exits 0, `FETCH_HEAD` moves, and `origin/master` keeps its old commit. The probe passes, and the stale tree is read as fresh: no records, so the accept is offered. `_launch_land` (`land_contract.py:3067`) already uses the explicit form for this reason.

Fix: `["git", "fetch", "origin", "+refs/heads/%s:refs/remotes/origin/%s" % (base, base)]`. The early-review caller at `:4032` gets the same guarantee for free.

A fetch that succeeds against a remote that is itself behind cannot be defended against. Origin is the source of truth by definition. Not a finding.

---

## NIT

- **N1. The new `--status` network call is acceptable and bounded, with one refinement.** It runs only when there is a layout, a known candidate and an answered open-records `gh` read, so the mode is already on the network. `_run`'s 60 s timeout maps a hang to `None`, which fails closed after B1. However, `subprocess.run` inherits stdin and sets no `GIT_TERMINAL_PROMPT=0`. On Windows, Git Credential Manager can show a dialog, and the "read-only" status can then sit for 60 s. Consider `env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}` on this fetch. The fetch also writes `refs/remotes/origin/<base>` in a read-only mode. That is ref metadata, not the tree or the records, and it is acceptable, but state it in the `--status` docs.
- **N2.** `land_contract.py:3058` recomputes `(known or {}).get("contractLanding") if isinstance(...)` when `landing_cfg` is already in scope (`:3033`). Pass `landing_cfg if isinstance(landing_cfg, dict) else {}`, or bind it once.
- **N3.** `land_contract.py:3049-3053`: if the contract file cannot be read, `contract_text = ""` gives zero blocks and `delivery_layout` returns None. The header check is then skipped silently. The old code still ran `select_linked_brief` against the disk briefs. Later phases probably catch a missing contract, but a parent-branch landing that cannot read its own contract should `finish("unverifiable", "P0", ...)` here and not proceed.
- **N4.** `merge_evidence` keeps an unchanged local record that origin does not hold. The fix review's suggestion, `{**origin, **changed}`, drops it. In the live report, a local-only stale record can therefore still count as landing evidence. That errs away from the accept, and it matches G-7's local-first check, so it is not harmful. The docstring should say so, so the next reader does not "fix" one path without the other.
- **N5.** `check_version_bump.py:142-146` tests `args.default_branch.strip()` but builds `default_ref` from the unstripped value. A padded `" master"` would make every base non-default and skip the check (exit 0). Use the stripped value.

## Checked, no finding

- **F2 ordering.** `delivery_layout` runs after `declared_topology` and before `GH_REPO`, the fetch and the worktree. It receives `config`, so it makes no git call against the process cwd (no wrong-tree read). With `known is None`, `{}` is passed, which is not `None`, so it is still git-free.
- **F2 behaviour by contract shape.** Single-block contracts and exempt statuses get `None`, so there is no halt (R-6). With no header brief, `no-parent-branch` is added, which is not one of the two halted reasons, and the earlier topology gate decides as before. Halt names `ambiguous-parent` and `parent-is-default` are both in the outcome vocabulary and have remedies (`land_contract.py:72-73, 112-114`). The layout's own remedy is passed through.
- **F3.** A header-against-children mismatch with agreeing children now returns the layout defect's `detail -- remedy`. When the children themselves disagree, the old text with the `--record-subtask` escape remains.
- **`protected_branches`.** A non-dict config gives `{}`. A non-list value gives `[default]`. Non-string entries are dropped. The default is always included. The landing previously left the default out when a list was given; it now includes it, which is correct under L-4. No other `protectedBranches` reader remains in `.claude/scripts`.
- **Shared state.** `_origin()` is cached once per run, so G-7 and the live report share one fetch. Records are replaced, not mutated in place (`:4295`, `:4435`), so the shallow `stored_records` copy is a valid "written this run" test.
- **Injection, paths, line endings.** `base` comes from `symbolic-ref`. Refspecs are prefixed with `+refs/heads/`. `RESULTS_DIR.as_posix()` is used. YAML parses CRLF. No new problem.

## Off-area drift / integration

- All three files are in the contract's Files to touch. No drift.
- No API, DTO or SignalR surface, so INTEGRATION.md is not applicable.
- MECHANISMS.md, VOCABULARY.md and JOURNAL.md: nothing new. B1 and W1-W2 are implementation gaps against R-7 as written, not contract defects.
