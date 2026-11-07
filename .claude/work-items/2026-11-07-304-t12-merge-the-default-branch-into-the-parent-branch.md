---
id: 304
issue_offer: opened
title: Merge the default branch into the parent branch
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/304
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t12-merge-the-default-branch-into-the-parent-branch
worktree: none
north_stars: inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md
parent_issue: 235
base: fix/235-domain-split-registries
contract: .claude/concepts/2026-11-04-domain-split-registries.md
issue_link: deferred
status: implementing
created: 2026-11-07
---

# Merge the default branch into the parent branch

## Problem statement
Sub-task 12 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235), added by amendment 5. The contract's handoff block below is the whole specification.

## Acceptance criteria
### 12. Merge the default branch into the parent branch (`python-ai-developer`)

**Depends on:** 11

**Files to touch:**
- `.claude/hooks/journal-post-approval-tracker.py`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/VOCABULARY.md`
- `.claude/registries/JOURNAL.md`
- `.claude/scripts/generate_registry_digest.py`
- `.claude/scripts/_registry_layout.py`
- `.claude/scripts/accuracy_update.py`
- `.claude/scripts/memory_boundary.py`
- `.claude/scripts/tests/test_plugin_text_scans.py`
- `.claude/scripts/tests/test_skill_script_lookup.py`
- `.claude/scripts/tests/test_registry_entries.py`
- `.claude/scripts/tests/test_registry_layout.py`
- `.claude/scripts/tests/test_memory_boundary.py`
- `skills/design-first/SKILL.md`
- `skills/verify-before-done/SKILL.md`
- `skills/auto-improve-finish-install/SKILL.md`

**Pre-written TASK block:**
```
TASK: Merge origin/master into the parent branch fix/235-domain-split-registries through this sub-task's task branch,
  resolve the 8 conflicting files by the per-file rules below, compose the two shared registry readers per Q21 (a),
  and leave every suite green, so that the re-run landing's merge of the default branch is clean.
CONTEXT: concept contract amendment 5 ("Amendment 5 record", Q21, Q22, Reused Mechanisms "Memory adapter",
  Extension Points, Failure Modes); the blocked landing run 20261107T114850Z-c28a69 (gate P7); the t11 review
  .claude/reviews/2026-11-04-domain-split-registries/t11-review-fullstack-code-reviewer.md (its Evidence table).
FILES: as listed. Every other file the merge changes arrives from origin/master through git, not by an edit.
CONSTRAINTS:
  - Route. This sub-task's head is the loop's task branch task/2026-11-04-domain-split-registries/t12-..., cut from
    origin/fix/235-domain-split-registries. Run: git fetch origin ; git merge --no-ff origin/master. Resolve, then
    commit the merge ON THE TASK BRANCH (two parents: the parent-branch tip and the origin/master commit). Put the
    conflict resolutions in the merge commit. Make the Q21 composition and the test changes as separate commits after
    it, so that git show --remerge-diff <merge> shows the resolutions alone. Open the pull request into
    fix/235-domain-split-registries. It must be merged with a merge commit, never squash or rebase (squashing drops
    the origin/master parent and the landing conflicts again). The pull request description's first line says:
    "Owner: merge this pull request with Create a merge commit, never Squash and merge or Rebase and merge." No tool
    enforces the method (the repository allows all three); that sentence is the only control, and block 13's
    Run-first line detects a failure. Never rebase the task branch. Never push to the parent branch directly.
  - Head proof, before opening the pull request, each output in your report and the pull request: git rev-list
    --parents -n 1 <merge commit> prints three hashes (the commit and its two parents: the parent-branch tip and the
    origin/master commit you merged; name both); git merge-tree --write-tree origin/master HEAD exits 0.
  - Read both sides first: for each conflicting path, git show origin/master:<path> and git show
    origin/fix/235-domain-split-registries:<path>, and git log --oneline 9a1b452a..origin/master -- <path>. In the
    pull request, cite for each file what each side added since 9a1b452a.
  - Per-file rules:
    (0) Base diff first (JOURNAL 2026-11-03, default branch, "When resolving a conflict hunk by keeping both sides,
        drop the base lines the other side rewrote"; it arrives with this merge). Before resolving any path under
        rules (3)-(8), run git diff 9a1b452a origin/master -- <path> and git diff 9a1b452a
        origin/fix/235-domain-split-registries -- <path>. A base line that one side left unchanged and the other side
        deleted or rewrote belongs to the rewrite only: it is not kept. "Keep both", "keep every test from both
        sides" and "united" below mean both sides' ADDED and CHANGED lines, never a base line that either side
        removed. Where both sides rewrote one base line differently, the per-file rule says which text governs.
    (1) .claude/hooks/journal-post-approval-tracker.py: the parent's thin wrapper wins whole (its logic lives in
        accuracy_update.process_journal_change, t4/t10). The default branch's change (469f51f: parse_entries calling
        generate_registry_digest.journal_entries, the _journal_entries binding, the journal-tracker-reader-missing
        log) is superseded as follows. The grammar is _registry_layout's. The Source contract rule moves to
        accuracy_update (see Q21 below). The reader-missing path is accuracy_update's lazy import (block 13 adds the
        log event under the default branch's event name). The merged file contains no regex and no parse_entries.
    (2) .claude/scripts/generate_registry_digest.py: the parent's file wins as the body: the resolver, tier labels,
        legacy entries, the sources hash, exit 1 on R1/R2, no DOMAINS. Re-add only the public names that
        memory_boundary.py binds, entry_blocks, journal_entries and BULLET, as re-exports of the _registry_layout
        adapters (Q21). DOMAINS, tier_split, read and entries are not restored. Their only users on origin/master are
        memory_boundary.py (DOMAINS, re-routed below) and test_registry_entries.py (rewritten below); confirm with
        git grep on the merge before deleting.
    (3) .claude/registries/MECHANISMS.md: the parent's layout-2 shape wins (marker on line 1, the Universal tier, the
        "## Project tier" pointer as the last section, project content in MECHANISMS/general.md). Every entry the
        default branch added since 9a1b452a goes in verbatim at the end of the Universal tier, after "Registry
        migration runner" and its Correction lines, and before the pointer: "Memory adapter" (2026-11-02),
        "CodeGraph (amendment)" (2026-11-05, issue #259), "CodeGraph (correction)" and "Add-on layout (amendment)".
        A Correction line the default branch added under an existing entry stays under that entry. Q22: the
        2026-11-05 "CodeGraph (amendment)" is folded in as the last indented line of the 2026-10-30 "CodeGraph
        (amendment)" entry, exactly "  - **Correction (2026-11-05, issue #259):** " followed by its text after the
        separator, verbatim. No other entry text changes.
    (4) .claude/registries/VOCABULARY.md: the parent's layout-2 shape and block 1's reconciliation win (the
        duplicate "Add-on manifest" and the two "Vendored-asset drift (amendment)" entries stay folded). Delete the
        default branch's copies of those three entries (its VOCABULARY.md:79/86/91/94 at draft time). They are
        byte-equal to the text block 1 kept (verified against a default-branch-derived tree, 2026-11-07). Check it:
        each deleted line's text after its "*(date)* — " separator appears verbatim in the matching kept entry or
        Correction / Merged duplicate line; put the three comparisons in the pull request. A mismatch stops the
        sub-task with AMENDMENT; never reword. The default branch's new terms ("Central
        Memory System" through "Shadow record", 24 entries) go in verbatim at the end of the Universal tier, after
        the seven terms block 8 appended, and before the pointer.
    (5) .claude/registries/JOURNAL.md (auto-merged): check that every entry the default branch added sits above the
        "## Project tier" pointer. Move any that git placed below it to the end of the Universal tier. This is the
        only reordering allowed, and you list it in the pull request.
    (6) .claude/scripts/tests/test_plugin_text_scans.py and test_skill_script_lookup.py: keep every test from both
        sides under rule (0): a test or assertion one side deleted or rewrote is not restored. The parent's scan rules (domain form, registry_append.py, no Edit-append, agents/*.md in the lookup
        pin) apply to every shipped file of the merge, including the ones the default branch added. Where a default
        branch file breaks a parent rule, fix that file, never the rule. Known case:
        skills/auto-improve-finish-install/SKILL.md:290 lists the three root registries the doctor seeds; add their
        <REG>/general.md skeletons (block 6's copy requirements).
    (7) skills/design-first/SKILL.md: keep both under rule (0); a base step or sentence one side rewrote appears
        once, in its rewritten form, never beside it. The default branch's Step 1.5 "Consult the Central Memory System"
        and every memory text, and the parent's "Run the data-architect's registry appends" section (after Step 2)
        and its registry_append.py writer text. Where both changed one sentence about appending a journal or
        registry entry, the parent's text governs the write (registry_append.py, no Edit) and the default branch's
        memory clauses are kept beside it.
    (8) skills/verify-before-done/SKILL.md: keep both steps in numeric order: 5.5, the parent's 5.6 "Registry
        structure lint", then the default branch's 5.8 "The codegraph add-on's settings check". Every other hunk
        is united under rule (0), not chosen: each side's added and changed lines, and no base line either side
        removed or rewrote. Rules (3)-(5) follow rule (0) too: an entry or Correction line either side removed
        from a root (the parent's moves into <REG>/general.md included) is not restored there.
  - Base-line check (BLOCKER fix), for each of the seven united paths (MECHANISMS.md, VOCABULARY.md, JOURNAL.md,
    test_plugin_text_scans.py, test_skill_script_lookup.py, skills/design-first/SKILL.md,
    skills/verify-before-done/SKILL.md): for each side B in {origin/master, the parent tip} and the other side A,
    take the non-blank base lines B removed (the "-" lines of git diff --unified=0 9a1b452a <B> -- <path>). Each
    such line must occur in the merged file no more often than in B's version plus the copies A added beyond the
    base (multiset counts). Write the check as a throwaway script outside the repository (for example under
    $env:TEMP), run it on the merge commit, and paste its output in the pull request: zero surviving lines, or each
    one named with the reason it is also present on side B. A surviving line is fixed in the merge commit.
  - Q21 (a) composition (not a conflict, but required for a working merge):
    _registry_layout gains source_value(raw), the default branch's _source_value rule unchanged (the rest of the
    line, backticks and padding trimmed; '', none, n/a, na, unknown, tbd and anything starting with "<" read
    empty). It also gains entry_blocks(text, pattern=None, per_domain=False) and journal_entries(text,
    per_domain=False), adapters over parse_text (kind "domain" when per_domain, else "root"; one M/V grammar, so
    pattern is accepted for signature compatibility and not used). They return exactly the default branch's dict
    keys: entry_blocks gives title, line, tier, text and subs (each sub has line and text, with deeper continuation
    folded in); journal_entries gives sig, date, title, line, tier, trigger, source and text, entries of kind
    "entry" only. The tier is "Universal" only when per_domain is false, parse_text's tier is "universal", and a
    "## Universal" heading precedes the entry in its file; otherwise it is "Project" (the default branch's
    fail-closed rule for memory scope). journal_entries' text is the heading line plus every line of the entry,
    as the default branch's is; trigger is fields["trigger"] trimmed and lower-cased (the default branch's rule,
    pinned by JournalEntriesTests: "Pre-Approval Critic" -> "pre-approval critic"); source is
    source_value(fields["source contract"]). entry_blocks returns kind "entry" and kind "legacy" (I-8c: legacy
    entries are returned to readers); journal_entries returns kind "entry" only (malformed ones included).
    Adapter differences from the default branch's functions (read from both: _registry_layout.py:173-190,230-244,
    327-437 and the default branch's generate_registry_digest.py:55-176). These are all of them; each is intended,
    because parse_text is the one grammar, and each gets one fixture row:
      D1 fences: a "- **x**" line inside a fence is not an entry, and a column-0 fence line ends the open entry
         (default branch: an entry, and the fence lines folded into the text).
      D2 I-8b sections: bullets under a "##" heading that is no tier heading ("## Universal...", "## Project:",
         "## Project tier"), no dated heading and not the leftovers heading are prose to the next "#"/"##"
         heading, never entries (default branch: entries, tier unchanged).
      D3 legacy headings: "## YYYY-MM-DD ..." in a mechanism or vocabulary file is a legacy entry (title = text
         after the date and separator; text = its lines to the next heading) (default branch: a heading that
         ends the previous entry, never an entry).
      D4 continuation: an entry continues only on blank lines and lines indented 2+ spaces; a non-blank column-0
         line or a one-space-indented line ends it (default branch: such a line continued the entry when no blank
         line preceded it).
      D5 below the pointer: an entry after "## Project tier" is "Project" (default branch: the tier the last
         "## Universal" set). R3 makes such an entry a finding on current.
      J1 fences: a "### YYYY-MM-DD" heading inside a fence is not an entry; its lines stay in the open entry's text.
      J2 I-8b sections: journal entries under a non-tier "##" heading (e.g. "## Notes") are prose (default branch:
         entries).
      J3 text end: an entry's text ends at the next heading of any level, so a "###" non-entry heading ("### Tag
         conventions") or a "####" sub-heading ends it (default branch: only the next entry header or a "## "
         line).
      J4 separator: a "### YYYY-MM-DD" heading with no separator, or with an en dash, is a (malformed, A1) entry
         (default branch: not an entry; its lines fold into the previous entry's text).
      J5 fields: when an entry has two Trigger or Source contract lines the last wins, and lines indented under a
         field fold into its value (_field_map; default branch: the first line wins, its own line only).
    accuracy_update.parse_journal_entries takes source_contract from rl.source_value(entry.fields
    ["source contract"]) instead of _SOURCE_VALUE, and _SOURCE_VALUE is deleted. memory_boundary._registry_files
    lists files with registry_files_in(<project>/.claude/registries, "<NAME>.md") in resolver order, bound
    fail-soft as _RL = _bind("_registry_layout", "registry_files_in") (never a module-level import). When it is
    None, select_candidates raises Refusal("reader-unavailable", ...) exactly as for missing readers ("Import
    chain", amendment 5). A file under <NAME>/ is per_domain. The is_shipped filter and the fail-soft _bind stay.
    The DOMAINS binding and DEFAULT_DOMAINS go. Moving entries changes the M/V candidate keys (Failure Modes);
    say so in the pull request.
  - Tests:
    test_registry_entries.py: EntryBlocksTests and JournalEntriesTests stay unchanged as the adapters' acceptance
    tests. Add AdapterDifferenceTests: one fixture row per difference D1-D5 and J1-J5 above, each asserting the
    adapter's result (written first and watched fail before the adapters exist), plus a legacy-kind row for
    entry_blocks. TierSplitIsByteIdentical is deleted:
    it pinned the pre-contract digest byte for byte, and this contract's Digest generator replaces that digest
    (test_registry_layout.py's digest tests cover it). Say so in the pull request. HookCallerTests becomes
    AccuracyParserTests, which tests accuracy_update.parse_journal_entries: the same keys; parity of sig, date,
    title and trigger with the default branch's old_parse_entries oracle on
    .claude/hooks/tests/fixtures/journal-signatures-2026-11-06.md (the frozen copy, never the live JOURNAL.md);
    and the "only the listed source forms differ" row, unchanged. The missing-reader row moves to block 13. Delete
    it here, and name test (d) of test_journal_post_approval_tracker.py as its current cover.
    test_registry_layout.py: source_value and both adapters' tier rule (a root entry under "## Universal", a root
    entry before any "##" heading, a domain-file entry).
    test_memory_boundary.py: a layout-2 round trip (JOURNAL 2026-11-01). A temporary project on layout 2 with a
    Universal entry in the root and entries naming the slug in JOURNAL/general.md and MECHANISMS/backend.md. Assert
    that capture-candidates offers the domain-file entries with scope "project" and the root entry as Universal
    before the token rule. A domain file named outside the old DOMAINS list (e.g. JOURNAL/ops.md) is read.
    A hidden-module row: in a subprocess with _registry_layout hidden, import memory_boundary succeeds, a
    retrieval subcommand still runs, and capture-candidates refuses reader-unavailable. Keep every existing row
    green.
  - Older-test search, one question per change, each with its own grep and its result in the pull request: (1) tests
    or scripts that call grd.tier_split, grd.read, grd.entries, grd.DOMAINS or grd.OUT; (2) tests that read the
    hook's parse_entries or _journal_entries; (3) tests that assert accuracy_update's source_contract for a
    multi-word or N/A source; (4) tests that pin memory_boundary's file list or DOMAINS; (5) tests that run
    --check-structure or --check on this repository and restrict its output (ThisRepositoryTests); (6) tests that
    count registry entries, titles or keys on the live registries.
  - Run, every one exit 0: the 14 suites of the t11 Evidence table
    (py -3 .claude/scripts/tests/test_preview_apply.py ; test_plugin_root.py ; test_registry_layout.py ;
    test_script_path_resolution.py ; test_registry_append.py ; py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py ;
    test_registry_readers.py ; test_registry_migrate.py ; test_plugin_doctor.py ; test_plugin_text_scans.py ;
    test_skill_script_lookup.py ; test_auto_improve_finish_install.py ; test_check_version_bump.py ;
    test_validate_registries_default.py, each under .claude/scripts/tests/ unless named), plus
    py -3 .claude/scripts/tests/test_registry_entries.py ; py -3 .claude/scripts/tests/test_memory_boundary.py, plus
    every test file listed by git diff --name-only 9a1b452a..origin/master -- .claude/scripts/tests .claude/hooks/tests
    (list them with their exits in the pull request). Live: py -3 .claude/scripts/registry_migrate.py --check
    --project . (exit 0, current); py -3 .claude/scripts/validate_registries.py --check-structure --project . (exit
    0; only R4, digest: and at most one "advisory: R3 universal-candidate skipped" line; any R1, R2, R3, R5, A1 line
    -> stop and report AMENDMENT, never suppressed); py -3 .claude/scripts/plugin_doctor.py --project . ;
    py -3 .claude/scripts/generate_registry_digest.py (exit 0); single definitions: git grep -n "def _atomic_write\|def
    _plan_digest\|def _separate_plugin_root" .claude/scripts shows only _preview_apply.py and _plugin_root.py.
  - Clean landing proof: git merge-tree --write-tree --name-only origin/master HEAD exits 0 and lists no conflict.
    Put its output in the pull request.
  - Version: edit no version file. The manifests equal origin/master's at the merged commit (git diff <merged
    origin/master commit> HEAD -- plugin.json .claude-plugin .cursor-plugin is empty). Run py -3
    .claude/scripts/check_version_bump.py --base origin/fix/235-domain-split-registries --default-branch master
    --head-ref <this task branch>: it must exit 0 with "keeps version", because the head's version equals the one at
    merge-base(origin/master, HEAD). The landing raises it once, later.
  - If the Changed-file check (concept_changed_check.py, turn end or --staged), a loop gate or a CI gate rejects a
    file because the merge's changed files exceed this list, stop and report; do not narrow the merge (Uncertain
    Assumptions, amendment 5).
  - Expected report: after this pull request merges, pr_merged reports the merge commit's hand-resolved files
    (skills/pr-merged/SKILL.md:255-269; it reports, it does not block). Say in the pull request that the report is
    expected, and list the files it should name: the files resolved or edited in the merge commit (the 8
    conflicting files, JOURNAL.md when rule (5) moved an entry, and any file rule (6) fixed there).
  - Registry append: after the merge commit, run registry_append.py --project . --registry mechanisms
    --correction-of "Memory adapter" --source "amendment 5, Q21" with an entry file saying its registry reads go
    through _registry_layout (registry_files_in; entry_blocks and journal_entries adapters re-exported by
    generate_registry_digest). Show the printed file:line.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

## Out of scope
- Anything outside the files and constraints of the handoff block above.

## Known context
- Parent / epic: #235
- Related items: none
- Affected areas: see the handoff block's Files to touch

## North-star alignment
- inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md

## Open questions from intake
- none

## Size
Sub-task of an approved contract.

## Routing
task of .claude/concepts/2026-11-04-domain-split-registries.md - dispatched by /advance