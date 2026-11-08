---
id: 319
issue_offer: opened
title: Merge the default branch into the parent branch again
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/319
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t15-merge-the-default-branch-into-the-parent-branch-again
worktree: none
north_stars: inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md
parent_issue: 235
base: fix/235-domain-split-registries
contract: .claude/concepts/2026-11-04-domain-split-registries.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-08
---

# Merge the default branch into the parent branch again

## Problem statement
Sub-task 15 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235), added by amendment 7. The default branch moved after the t14 review's clean landing check (a241f5c, then aa3f715, now 50bfc2a), and a live merge check now conflicts in `MECHANISMS.md` and `VOCABULARY.md`, which the landing cannot resolve. The contract's handoff block below is the whole specification.

## Acceptance criteria
### 15. Merge the default branch into the parent branch again (`python-ai-developer`)

**Depends on:** 14

**Files to touch:**
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `.claude/registries/JOURNAL.md`

**Pre-written TASK block:**
```
TASK: Merge origin/master (aa3f715 or later) into the parent branch fix/235-domain-split-registries through this
  sub-task's task branch, resolve the conflicts in MECHANISMS.md and VOCABULARY.md by the per-file rules below,
  append the two journal lessons quoted in the "Amendment 7 record" (Q25), and leave every suite green, so that the
  landing's merge of the default branch is clean.
CONTEXT: concept contract amendment 7 ("Amendment 7 record", Q23-Q25); block 12 (the first merge, its rules (0), (3),
  (4), (5) and (9), which this block narrows); the t14 review
  .claude/reviews/2026-11-04-domain-split-registries/t14-review-fullstack-code-reviewer.md (its last check, W1, N2).
FILES: as listed. Every other file the merge changes (the four version manifests, the work-item brief, anything else
  the default branch changed) arrives from origin/master through git, not by an edit.
CONSTRAINTS:
  - Run first, on the task branch task/2026-11-04-domain-split-registries/t15-... (the loop cuts it from
    origin/fix/235-domain-split-registries): git fetch origin ; git merge-base HEAD origin/master (expected 88f4d32;
    call it <base>; 9a1b452a or 28f0b18 means an earlier merge was lost: stop) ; git log --oneline <base>..origin/master
    ; git diff --stat <base> origin/master ; git merge-tree --write-tree --name-only origin/master HEAD (expected exit
    1, conflicting paths exactly .claude/registries/MECHANISMS.md and .claude/registries/VOCABULARY.md). Only the
    merge-base line and the merge-tree line can stop the run: a different merge base stops it, and any other
    conflicting path stops the sub-task with AMENDMENT; never resolve a path outside Files to touch. The git log and
    git diff --stat outputs are informational: paste them raw in the pull request. A normal run shows the commits
    a88a2f8, a241f5c and aa3f715 (or later) and a stat over docs, records, registries and manifests, but whatever
    they show, the deleted-names check below is what judges the changed .py files.
  - Deleted-names check (textual conflicts hide semantic ones). The amendment record assumes nothing about which
    .py files the default branch changed over <base>..origin/master (a88a2f8, a241f5c, aa3f715 and later); this
    check measures it. (1) List them: git diff --name-only <base> origin/master -- '*.py', and paste the list (or
    "none"). (2) For each listed file, git grep -n -w in origin/master's copy (git grep -n -w -e <name> ...
    origin/master -- <file>) for the names this contract removed: tier_split, DOMAINS, DEFAULT_DOMAINS,
    parse_entries, _journal_entries, _SOURCE_VALUE, and grd.read / grd.entries / grd.OUT. (3) One stop rule: a hit
    stops the sub-task with AMENDMENT, naming the file, line and name; a listed file with no hit is recorded in the
    pull request as "<file>: no hit" and the check continues.
  - Route: git merge --no-ff origin/master on the task branch. Put only the conflict resolutions in the merge commit
    (two parents: the parent-branch tip and the origin/master commit), so git show --remerge-diff <merge> shows them
    alone; a rule (5') move, if needed, is one separate commit after it. Open the pull request into
    fix/235-domain-split-registries. Its description's first line says: "Owner: merge this pull request with Create a
    merge commit, never Squash and merge or Rebase and merge." Never rebase, amend or force-push; never push to the
    parent branch directly.
  - Resume: if origin/master moves again before the pull request merges, run git merge --no-ff origin/master on the
    same branch (a second ordinary merge commit), with its own <base> (git merge-base HEAD origin/master before it)
    and "parent tip" = HEAD just before it, the same rules, and the full Run list again. A conflict outside Files to
    touch stops with AMENDMENT.
  - Read both sides first: for each conflicting path, git show origin/master:<path>, git show
    origin/fix/235-domain-split-registries:<path>, git diff <base> origin/master -- <path> and git diff <base>
    origin/fix/235-domain-split-registries -- <path>. In the pull request, paste what each side added since <base>.
  - Per-file rules:
    (0) Block 12's rule (0) with <base> in place of 9a1b452a: a base line one side left unchanged and the other side
        deleted or rewrote belongs to the rewrite only. In particular the Q22 fold and the two rule-(9) folds stay
        folded: the default branch's top-level 2026-11-06 "CodeGraph (correction)" entry and its column-0
        "Correction (2026-11-06, issue #271):" VOCABULARY line are base lines the parent rewrote and are not restored.
    (3') MECHANISMS.md: the parent's layout-2 shape wins (marker on line 1, the Universal tier, the "## Project tier"
        pointer as the last section). Every entry the default branch added since <base> goes in verbatim at the end
        of the Universal tier, after the parent tip's last Universal entry and its Correction lines, and before the
        pointer (at amendment time: "Project hook launcher" (2026-11-07)). A Correction line the default branch added
        under an existing entry stays under that entry, after that entry's existing indented lines (at amendment
        time: "Correction (2026-11-07, ... Revision 9, block 38)" under "Guard fallback mode"). No entry text changes.
    (4') VOCABULARY.md: the same rule (at amendment time: the term "Project hook launcher" (2026-11-07) at the end of
        the Universal tier, before the pointer; the two 2026-11-07 Correction lines under "Gate launcher" and "Guard
        deference"). Block 1's folds and rule (9)'s fold stay as they are.
    (5') JOURNAL.md, placement (only if the merge changes it): every entry the default branch added since <base>
        sits above the "## Project tier" pointer; move any that git placed below it to the end of the Universal tier,
        in its own commit, listed in the pull request. If the merge does not change JOURNAL.md, this rule moves
        nothing. (JOURNAL.md is touched in every case by the journal appends below.)
  - Journal appends (Q25, owner 2026-11-07): after the merge commit and any rule (5') commit, and before the Run
    list, append both lessons quoted in the "Amendment 7 record" (this amendment's "A clean landing check goes stale
    when the default branch moves; re-run it immediately before launching" and t14's "A merge block's pull request
    must paste each required output, not tick a line that says it passed"), verbatim, one call each:
    py -3 .claude/scripts/registry_append.py --project . --registry journal --universal with the lesson as its entry
    file. Never hand-edit JOURNAL.md (I-7). Commit both appends as one commit of their own, never inside a merge
    commit. Show each printed file:line. Then check: each title occurs exactly once in JOURNAL.md (git grep -c -F
    "<title>" -- .claude/registries/JOURNAL.md prints 1), and each sits above the "## Project tier" pointer (its
    line number is lower than the pointer's). These appends are in this pull request, so the parent commit that
    block 16's last check names already contains them. If origin/master moves after the append commit (Resume), the
    new merge commit comes after it; re-run this check on the new head, and never append a second time.
  - Base-line check (block 12's, narrowed): for each resolved path, for each side B in {origin/master, the parent tip}
    and the other side A, take the non-blank base lines B removed (the "-" lines of git diff --unified=0 <base> <B> --
    <path>); each must occur in the merged file no more often than in B's version plus the copies A added beyond the
    base (multiset counts). Lost-lines check, the reverse: every line either side added since <base> occurs in the
    merged file. Write both as a throwaway script outside the repository (for example under $env:TEMP), run them per
    merge commit with its own <base> and parent tip, and paste the raw output: zero surviving and zero lost lines, or
    each one named with its reason.
  - Head proof: for each merge commit of origin/master this block made, git rev-list --parents -n 1 <merge> prints
    three hashes (name both parents); git merge-tree --write-tree --name-only origin/master HEAD exits 0 and lists
    no conflicting path.
  - Version: edit no version file. git diff <merged origin/master commit> HEAD -- plugin.json .claude-plugin
    .cursor-plugin is empty, so the parent's version equals origin/master's at the merged commit (0.16.4 at amendment
    time; print it). py -3 .claude/scripts/check_version_bump.py --base origin/fix/235-domain-split-registries
    --default-branch master --head-ref <this task branch> exits 0 with "keeps version <that version>". The landing
    raises it once, later.
  - Older-test search, one question per change, each with its own grep and its result in the pull request: (1) tests
    that count entries, titles or keys on the live MECHANISMS.md or VOCABULARY.md; (2) tests that pin a line number of
    a live registry entry or of the "## Project tier" pointer; (3) tests that assert the count in the "advisory: R3
    universal-candidate skipped" line (22 at t14; the merge adds Universal entries); (4) tests that assert the literal
    version 0.16.3.
  - Run, every one exit 0 unless said: the 14 suites of block 12's Run list, py -3
    .claude/scripts/tests/test_registry_entries.py, py -3 .claude/scripts/tests/test_memory_boundary.py, every test
    file in .claude/hooks/tests (the landing's step), and every test file listed by git diff --name-only
    <base>..origin/master -- .claude/scripts/tests .claude/hooks/tests (paste the list, or "none"). py -3
    .claude/scripts/tests/test_plugin_manifests.py exits non-zero with exactly one failing row, the amendment-6
    exception, now printed with the new merge base's version ("tree differs from the merge base (<version>)"); any
    other red row is a real failure. Repeat block 12's "Expected red, owner-accepted" paragraph in the pull request.
    Live: py -3 .claude/scripts/registry_migrate.py --check --project . (exit 0, current); py -3
    .claude/scripts/validate_registries.py --check-structure --project . (exit 0; only R4, digest: and at most one
    "advisory: R3 universal-candidate skipped" line; any R1, R2, R3, R5, A1 line -> stop and report AMENDMENT, never
    suppressed); py -3 .claude/scripts/plugin_doctor.py --project . ; py -3 .claude/scripts/generate_registry_digest.py
    (exit 0; delete the gitignored output afterwards); single definitions: git grep -n -w -e "def _atomic_write" -e
    "def _plan_digest" -e "def _separate_plugin_root" -- .claude/scripts prints exactly five lines:
    _preview_apply.py (def _plan_digest, def _atomic_write), _plugin_root.py (def _separate_plugin_root),
    land_contract.py (def _atomic_write) and memory_boundary.py (def _atomic_write), the last two the default
    branch's own (amendment 7, t14 N2). -w (whole word) keeps pr_merged.py's def _atomic_write_bytes out. Any other
    line stops the sub-task with AMENDMENT, naming the file.
  - Evidence (t14 W1): paste every output this TASK names, raw, in the pull request description or one pull request
    comment. A ticked line that says a check passed is not evidence.
  - If the Changed-file check, a loop gate or a CI gate rejects a file because the merge's changed files exceed this
    list, stop and report; do not narrow the merge.
  - Expected report: after this pull request merges, pr_merged reports the merge commit's hand-resolved files
    (MECHANISMS.md and VOCABULARY.md; JOURNAL.md only if rule (5') moved an entry; the append commit is an ordinary
    commit, not a resolution). Say so in the pull request.
  - Expected outputs, besides the Run list: the two registry_append.py file:line lines; the two "1" counts and the
    two line numbers above the pointer from the journal appends check; the single-definitions five lines.
  - No other registry append, and no push to the parent branch directly: the two Q25 lessons enter only through
    this pull request.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

## Out of scope
- Anything outside the files and constraints of the handoff block above.
- The t14 nits N1 and N3 (Q24: owner accepted keeping them out).

## Known context
- Parent / epic: #235
- Related items: t14 review (#306), t12 merge (#304)
- Affected areas: see the handoff block's Files to touch

## North-star alignment
- inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md

## Open questions from intake
- none

## Size
Sub-task of an approved contract.

## Routing
task of .claude/concepts/2026-11-04-domain-split-registries.md - dispatched by /advance
