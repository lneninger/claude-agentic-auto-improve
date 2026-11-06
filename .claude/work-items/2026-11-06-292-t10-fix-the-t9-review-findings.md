---
id: 292
issue_offer: opened
title: Fix the t9 review findings
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/292
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t10-fix-the-t9-review-findings
worktree: none
north_stars: inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md
parent_issue: 235
base: fix/235-domain-split-registries
contract: .claude/concepts/2026-11-04-domain-split-registries.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-06
---

# Fix the t9 review findings

## Problem statement
Sub-task 10 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235), added by amendment 4 after the t9 review returned `blocked`. The contract's handoff block below is the whole specification.

## Acceptance criteria
### 10. Fix the t9 review findings (`python-ai-developer`)

**Depends on:** 8

**Preconditions:** pull-request lneninger/claude-agentic-auto-improve#288

**Files to touch:**
- `.claude/scripts/accuracy_update.py`
- `.claude/hooks/tests/test_journal_post_approval_tracker.py`
- `.claude/hooks/tests/fixtures/journal-signatures-2026-11-06.md`
- `.claude/scripts/_preview_apply.py`
- `.claude/scripts/tests/test_preview_apply.py`
- `.claude/scripts/registry_migrate.py`
- `.claude/scripts/registry_migrations/m0001_domain_split.py`
- `.claude/scripts/tests/test_registry_migrate.py`
- `.claude/scripts/validate_registries.py`
- `.claude/scripts/tests/test_validate_registries_default.py`
- `.claude/scripts/tests/test_registry_layout.py`
- `.claude/references/registry-layout.md`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/JOURNAL.md`

**Pre-written TASK block:**
```
TASK: Fix t9 review findings W1-W4, N1-N3 and W5 (Q19 answer (a)); append the two Q20 lessons. Each fix comes with
  its tests.
CONTEXT: concept contract amendment 4 ("Amendment 4 record", "Shared helpers" incl. "Import chain", R3, R4, I-12,
  I-14, step 4, Migration report VO, Q19, Q20, "Amendment 4 critique"); review
  .claude/reviews/2026-11-04-domain-split-registries/t9-review-fullstack-code-reviewer.md.
FILES: as listed.
CONSTRAINTS:
  - Run first, before any edit: gh pr view 288 --repo lneninger/claude-agentic-auto-improve --json state,mergedAt,baseRefName
    must show state MERGED into fix/235-domain-split-registries. If it does not, stop and report; do not start. The
    Preconditions line is information only (pr_merged.py ~line 1175 never gates on it). Cut this branch from the parent
    branch after that merge. PR #288 (head fix/235-pin-current-layout-in-layout-test) fixed C1; C1 is not re-fixed here.
  - W1: accuracy_update.parse_journal_entries builds its entries from _registry_layout.parse_text(text, "JOURNAL", ...),
    keeping journal entries only (never legacy entries, I-8c; never inside fences, I-8). Delete _ENTRY_HEADER and keep no
    other journal heading regex in this file. The signature stays sha1(date|title), with the title taken exactly as today.
    Import _registry_layout lazily inside parse_journal_entries; on ImportError write one stderr line naming the module
    and return no entries. Module-level imports stay as today ("Import chain").
    I-14 reader re-seed: each seeded_files value records reader 2; a file whose value has no reader is re-seeded once
    on its next read with the new reader (all its signatures marked seen, nothing fires except a fresh one).
    Tests (test_journal_post_approval_tracker.py):
      (a) a dated ### heading inside a fence, added to a seeded file, fires zero times;
      (b) frozen signature pin: create .claude/hooks/tests/fixtures/journal-signatures-2026-11-06.md as a byte copy of
          .claude/registries/JOURNAL.md taken BEFORE this block's Q20 appends (41 entries). The test computes the
          expected set from that fixture with a copy of today's _ENTRY_HEADER held as a test constant, and the actual
          set from the new code on the same fixture; the two are identical and hold 41 signatures. Never read the live
          JOURNAL.md in this test, so this block's appends and later appends never turn it red;
      (c) client parity row: a client-shaped journal whose headings the old and new patterns read differently (at
          least a heading inside a fence, a tab after the date, no space after the separator, a heading the old \s+
          reads across a line break, CRLF line endings), seeded under the old reader (cache value with no reader),
          then read by the new code: zero fires; then one new post-approval heading appended: exactly one fire;
      (d) with _registry_layout hidden (sys.modules entry set to None in a subprocess), critic-verdict-tracker.py and
          contract-status-watcher.py both still import accuracy_update (their _DEPS_OK is true), and
          accuracy_update.record_clean still runs; parse_journal_entries returns no entries and writes one stderr line.
  - W2: stage_and_replace(writes, backup_dir, base=None). Back up to backup_dir / target.relative_to(base). base defaults
    to the common parent folder of the targets. A target outside base returns write-failed before any stage file is
    written. registry_migrate passes the project root. Tests: the backup path equals backup_dir / relative path; a fixture
    nested deep enough that the old absolute-path rule would pass 260 characters while the new path stays under it
    (assert on the computed length, no long-path OS setting needed); a target outside base -> write-failed, every
    target unchanged.
  - N3: remember the folders step (a) created. After a staging failure or a rollback, remove the ones that are empty.
    Test: a new MECHANISMS/ folder made by a failed run is gone afterwards; a folder that existed before stays.
  - W3: per key, _plan_registry records the multiset of input lines of every occurrence, minus that key's merged-duplicate
    removed lines. verify_plan parses each output entry and requires that its line multiset contains that set; otherwise
    content-loss-detected. Both sides are normalised exactly as I-12's text check: line endings folded, BOM dropped,
    trailing spaces trimmed, blank lines ignored. Step 4 treats the heading line as a field, so two copies whose heading
    lines differ refuse conflicting-entry and step 4 never appends a heading line. If the plan still holds two output
    entries with one key, verify_plan refuses conflicting-entry naming both output locations and their first lines. The
    key-set and count checks stay. Tests: a forced plan that moves one body line from one entry to another ->
    content-loss-detected, files byte-identical, report written; the existing merge fixture (the Lesson-only copy
    appended under the bodied one) still passes; a CRLF + BOM + trailing-space client fixture -> no
    content-loss-detected; two copies whose headings differ only in the date -> conflicting-entry, files byte-identical.
  - N2: an exception in build_plan writes the report through Run.finish with mode refused, refusal code
    plan-build-failed, `error` set (exception type and message), every list empty and plan hash `none`, then exits 2
    (Migration report VO; Commands Rejections). No registry file is touched. Test: a forced build_plan exception gives
    exit 2, registry files byte-identical, and a report folder whose report.json has mode refused, refusal code
    plan-build-failed and the error.
  - W4: the default (no-flag) mode iterates registry_files("MECHANISMS.md") and registry_files("VOCABULARY.md")
    (through _claude_paths, same root, I-3) and prints one report block per file. In each file it ignores every line
    from the "## Migration 0001 leftovers (not parsed as entries)" heading on, so leftovers never produce findings.
    The regex, the flags and the exit rule do not change. --json keeps the mechanisms and vocabulary keys with today's
    shape, aggregated over all files, and adds one key "files" (one block per file, registry_files order). Tests (new
    file test_validate_registries_default.py, temp project only): a dead path only in MECHANISMS/backend.md is reported
    under that file and gives exit 1; a flat layout-1 fixture prints the same blocks and the same --json mechanisms and
    vocabulary values as before; a layout-2 fixture with no dead path gives exit 0; a general.md whose leftovers
    section holds a three-backtick run and a dead path gives no finding from the leftover and still reports a dead
    path in an entry above it.
  - W5 (Q19 answer (a)): when _plugin_root._manifest_names_plugin(project) is true, --check-structure drops every R3
    universal-candidate advisory. Only when at least one was dropped it prints exactly one line, ASCII only:
    "advisory: R3 universal-candidate skipped: <N> entries; this project holds the plugin's own manifest"
    (fixed prefix "advisory: R3 universal-candidate skipped"). Token findings, R3 plugin-owned, R3 unverified and every
    other result are unchanged. Document this in registry-layout.md under R3. Tests in test_registry_layout.py: a
    project with the manifest and candidates gets the skip line (N correct) and no candidates; the same project with
    the manifest and no candidates gets no skip line; the same fixture without the manifest still lists the candidates;
    a token-bearing client-authored entry stays a finding with the manifest present.
    In ThisRepositoryTests (as rewritten by PR #288), add "advisory: R3 universal-candidate skipped" to the allowed
    line prefixes, beside "advisory: R4 " and "digest: ". Keep PR #288's assertion that no layout advisory line is
    printed; change nothing else in that test.
  - N1: never edit the entry by hand (I-7). Run registry_append.py --project . --registry mechanisms --correction-of
    "Registry migration runner" --source "t9 review N1" with an entry file whose text names
    .claude/scripts/registry_migrations/__init__.py. Show the printed file:line in the PR. R4 keeps listing the original
    span at MECHANISMS.md:112 (I-7; skills/validate-registries/SKILL.md says the validator keeps listing it); that is
    expected and not a failure.
  - Q20: append the two proposed lessons with registry_append.py --project . --registry journal --universal, Trigger
    "post-impl divergence", Source contract this contract. W5 lesson: the review's text, worded for answer (a) (skip
    only the universal-candidate advisory when the project holds the plugin's own manifest, print one line, never
    downgrade a finding). C1 lesson: the wording under "A second proposed lesson". Show each printed file:line in the PR.
    Take the W1 fixture copy before these appends.
  - Older-test search, one question per change, each with its own grep and its result in the PR: (1) tests asserting
    _ENTRY_HEADER or parse_journal_entries output, or reading the live JOURNAL.md signature set; (2) tests asserting a
    backup path layout or calling stage_and_replace positionally; (3) tests asserting verify_plan messages or the
    report's mode/refusal values; (4) tests asserting the default report's exact text, block count or --json shape;
    (5) tests counting R3 universal-candidate lines on a fixture that holds the manifest; (6) tests that run
    --check-structure on this repository and restrict its output lines, starting with
    .claude/scripts/tests/test_registry_layout.py ThisRepositoryTests; (7) tests or hooks that import accuracy_update
    and depend on its import-time behaviour (at least critic-verdict-tracker.py, contract-status-watcher.py,
    journal-post-approval-tracker.py).
  - Version: no version file. This sub-task PR goes into the parent branch, and the landing raises the version once
    (MECHANISMS.md and JOURNAL.md are shipped registry seeds).
  - Run, all 13 t9 suites plus the new one, every one exit 0 (test_registry_layout.py is on this block's list and is
    rerun after the W5 change; --check-structure on this repository prints only R4, digest: and at most one
    "advisory: R3 universal-candidate skipped" line):
    py -3 .claude/scripts/tests/test_preview_apply.py ; py -3 .claude/scripts/tests/test_plugin_root.py ;
    py -3 .claude/scripts/tests/test_registry_layout.py ; py -3 .claude/scripts/tests/test_script_path_resolution.py ;
    py -3 .claude/scripts/tests/test_registry_append.py ; py -3 .claude/hooks/tests/test_journal_post_approval_tracker.py ;
    py -3 .claude/scripts/tests/test_registry_readers.py ; py -3 .claude/scripts/tests/test_registry_migrate.py ;
    py -3 .claude/scripts/tests/test_plugin_doctor.py ; py -3 .claude/scripts/tests/test_plugin_text_scans.py ;
    py -3 .claude/scripts/tests/test_skill_script_lookup.py ; py -3 .claude/scripts/tests/test_auto_improve_finish_install.py ;
    py -3 .claude/scripts/tests/test_check_version_bump.py ; py -3 .claude/scripts/tests/test_validate_registries_default.py ;
    py -3 .claude/scripts/registry_migrate.py --check --project . ;
    py -3 .claude/scripts/validate_registries.py --check-structure --project .
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

## Out of scope
- Everything outside the files listed in the handoff block.

## Known context
- Parent / epic: #235
- Contract: .claude/concepts/2026-11-04-domain-split-registries.md

## North-star alignment
- inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md

## Open questions from intake
- none

## Size
Task of an approved contract; not sized here.

## Routing
task of .claude/concepts/2026-11-04-domain-split-registries.md - dispatched by /advance
