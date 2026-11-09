---
id: 327
issue_offer: opened
title: Complete the hook registration check's vendored file list
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/327
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-04-domain-split-registries/t17-complete-the-hook-registration-check-s-vendored-file-list
worktree: none
north_stars: inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md
parent_issue: 235
base: fix/235-domain-split-registries
contract: .claude/concepts/2026-11-04-domain-split-registries.md
pr: none
issue_link: unknown
status: implementing
created: 2026-11-09
---

# Complete the hook registration check's vendored file list

## Problem statement
Sub-task 17 of the approved contract `.claude/concepts/2026-11-04-domain-split-registries.md` (parent issue #235), added by amendment 10. The landing run 20261109T154140Z-97de67 halted at gate P8 because `test_check_hook_registrations.py` failed 3 of 72 tests: the checker's vendored-file list names five files while sub-task 2 added two module-level imports (`_preview_apply.py`, `_plugin_root.py`). The contract's handoff block below is the whole specification.

## Acceptance criteria
### 17. Complete the hook registration check's vendored file list (`python-ai-developer`)

**Depends on:** 16

**Files to touch:**
- `.claude/scripts/check_hook_registrations.py`
- `.claude/scripts/tests/test_check_hook_registrations.py`
- `README.md`
- `.claude/registries/MECHANISMS.md`
- `.claude/registries/JOURNAL.md`

**Pre-written TASK block:**
```
TASK: Make the Hook registration check's vendored file list complete: add _preview_apply.py and _plugin_root.py to
  VENDORED_FILES, make the refusal text and the tests read that one list, correct README step 2, and add one
  Correction line under the "Hook registration check" mechanism entry, so that the landing's hook-registration-tests
  step passes; and append the amendment-10 journal lesson.
CONTEXT: concept contract amendment 10 ("Amendment 10 record" with every file:line and its critique fold; Q28, Q29;
  "Import chain"; block 2).
  Landing run 20261109T154140Z-97de67, gate P8; its log is in the main checkout at
  .claude/logs/landing/2026-11-04-domain-split-registries/20261109T154140Z-97de67/hook-registration-tests/output.log.
FILES: as listed. No other file changes.
CONSTRAINTS:
  - First step, on the task branch: git fetch origin ; git merge --ff-only origin/fix/235-domain-split-registries.
    It is a fast-forward or "Already up to date". If it is neither, stop and report. Follow the contract as it
    stands after this step (amendment 10).
  - RED proof, before any edit: py -3 .claude/scripts/tests/test_check_hook_registrations.py exits 1 with
    "FAILED (failures=3)". The three failing tests are test_a_vendored_copy_leaves_the_tree_byte_identical_with_dash_B,
    test_a_vendored_copy_leaves_the_tree_byte_identical_without_dash_B and
    test_the_vendored_copy_fails_the_same_way_as_the_repository_copy, each with "cannot import the module
    '_preview_apply'". Paste the raw output. If the failures differ, stop and report AMENDMENT.
  - Tests first (test_check_hook_registrations.py):
    (t1) Delete the FIVE_FILES literal (:28-34). After "import check_hook_registrations as chk" add
        VENDORED_FILES = chk.VENDORED_FILES. Every use (:712, :808, :830, :845) reads that name, so the tests can
        never hold a second copy of the set.
    (t2) Rename test_dependency_import_failure_is_exit_2_naming_the_five_files to
        test_dependency_import_failure_is_exit_2_naming_every_vendored_file. Its body is unchanged apart from the
        name it loops over.
    (t3) Add one pin test: chk.VENDORED_FILES equals exactly ("check_hook_registrations.py",
        "auto_improve_finish_install.py", "pr_merged.py", "plugin_doctor.py", "check_version_bump.py",
        "_preview_apply.py", "_plugin_root.py"), in that order.
    Run the suite: it exits 1 with 4 failures (the three above and the pin). Paste the output.
    Leave every other "five" in the file alone: it counts Registration rules or test classes, not files.
  - Checker (check_hook_registrations.py):
    (c1) VENDORED_FILES gains "_preview_apply.py" and "_plugin_root.py" after "check_version_bump.py".
    (c2) The checker-dependency-missing message and its remedy (:512-514) take the count from len(VENDORED_FILES)
        and name no number word: "Vendor all %d files together into one folder: %s" and "Copy the %d files listed
        above next to check_hook_registrations.py, then rerun."
    (c3) The docstring (:14-15) names all seven files. The comment at :32 ("its four dependencies") says the folder
        holds the other files of VENDORED_FILES.
    Nothing else changes: the refusal code, the exit codes, the guarded import at :49-52 and the bytecode flag
    order (pinned by test_the_bytecode_flag_is_the_first_statement_before_the_guarded_import) stay as they are.
  - README.md step 2 (:1501-1506): "Vendor seven files.", listing the seven names in VENDORED_FILES order, and "The
    checker imports the other six." No other README line changes.
  - MECHANISMS.md: one Correction line, through the single write path (I-7; never hand-edit), in a commit of its own
    (Q29: the owner may drop that commit). In PowerShell:
    'A vendored copy needs seven files in one folder, not five: the five named above plus `_preview_apply.py` and `_plugin_root.py`, which `auto_improve_finish_install.py` imports at module level since issue #235 (sub-task 2). `VENDORED_FILES` in `check_hook_registrations.py` is the one list; its refusal message and its tests read it.' | py -3 .claude/scripts/registry_append.py --project . --registry mechanisms --from-file - --correction-of "Hook registration check" --source "issue #235, amendment 10"
    The single quotes are required: in PowerShell a backtick inside double quotes is an escape character. Paste
    the printed file:line. correction-target-missing, or any other rejection, stops the sub-task with AMENDMENT.
    Then git show --stat HEAD lists only MECHANISMS.md, with 1 insertion, and the new line sits directly under
    the entry's last line. The entry's original "needs five files" text stays: a Correction line is an append (I-7).
  - Journal lesson (Q28, owner 2026-11-09; the Q20 and Q25 precedent): append the lesson quoted at the end of the
    "Amendment 10 record" (title "A change that adds a module-level import to a vendored script must update the
    vendored-file list in the same change"), verbatim, in a commit of its own (the owner may drop it), never inside
    another commit and never by hand-editing JOURNAL.md (I-7). The text holds an em dash, so write the entry file
    without a byte-order mark and do not pipe it. In PowerShell:
    $p = Join-Path $env:TEMP 't17-lesson.md' ; [IO.File]::WriteAllText($p, <the quoted entry as a single-quoted here-string @'...'@>)
    py -3 .claude/scripts/registry_append.py --project . --registry journal --universal --from-file $p
    Paste the printed file:line. Then:
    git grep -c -F "A change that adds a module-level import to a vendored script" -- .claude/registries/JOURNAL.md
    prints ".claude/registries/JOURNAL.md:1", and the entry's line number is lower than the "## Project tier"
    pointer's. A rejection stops the sub-task with AMENDMENT. The entry enters the parent branch only through this
    pull request, under the landing's single raise; no version file changes.
  - Run each literal command in this block once before relying on it, and record its exit code. git grep exits 1
    when nothing matches. git has no -x switch (t16 N1): to match a whole line, use git grep -c -E "^...$".
  - Older-test search, one question per change, each with its own command and its raw result:
    (1) tests that assert the refusal or remedy wording:
        git grep -n -E "five files|Vendor all|Copy the" -- .claude/scripts/tests .claude/hooks/tests
    (2) tests that pin README step 2:
        git grep -n -F -e "Vendor five files" -e "imports the other four" -- .claude/scripts/tests .claude/hooks/tests
    (3) tests that pin the mechanism entry or MECHANISMS.md lines or counts:
        git grep -n -F "Hook registration check" -- .claude/scripts/tests .claude/hooks/tests
        Run every file this search names.
    (5) tests that count or key entries of the live JOURNAL.md (the lesson adds one Universal entry):
        git grep -n -l -F "registries/JOURNAL.md" -- .claude/scripts/tests .claude/hooks/tests
        Run every file this search names, plus test_registry_entries.py and test_registry_layout.py.
    (4) other readers of the set, run after every commit of this block (the pathspec keeps out .claude/concepts,
        whose contract text names both identifiers):
        git grep -c -w -e VENDORED_FILES -e FIVE_FILES -- .claude/scripts README.md .claude/registries
        Expected: exactly three files, .claude/scripts/check_hook_registrations.py,
        .claude/scripts/tests/test_check_hook_registrations.py and .claude/registries/MECHANISMS.md (the Correction
        line), exit 0.
        git grep -c -w FIVE_FILES -- .claude/scripts README.md .claude/registries
        Expected: no output, exit 1.
    A hit that this change breaks is fixed only if its file is in Files to touch. Otherwise stop and report
    AMENDMENT.
  - Run (GREEN), each exit 0 unless stated. First, the landing's four verification steps. Read their commands from
    .claude/work-item-conventions.json contractLanding.verification.steps, which land_contract.py reads. The lines
    below are copies of that file. Compare each one with it before you run it, record that they match, and run the
    file's version if they differ. land_contract.py --verify-here runs those steps itself, but it is not usable
    here: it reads .claude/test-baseline.json from origin/master first, and with that file absent it ends
    "no-baseline" at gate V1 without running any step (land_contract.py:3124-3128).
    (v1) version-bump, in parent mode for a sub-task:
         py -3 .claude/scripts/check_version_bump.py --base origin/fix/235-domain-split-registries --default-branch
         master --head-ref <this task branch>
         Expected: "keeps version <v>", where <v> is the base's version (0.16.5 per t16). The landing runs its bare
         form, py -3 .claude/scripts/check_version_bump.py, after its own raise.
    (v2) py -3 .claude/scripts/tests/test_pr_merged.py (about 23 minutes).
    (v3) py -3 .claude/scripts/tests/test_check_hook_registrations.py, 73 tests, OK.
    (v4) the hook-tests step, verbatim:
         py -3 -c "import glob,subprocess,sys; fs=sorted(f for f in glob.glob('.claude/hooks/tests/test_*.py') if not f.endswith('test_gate_cost.py')); rcs=[subprocess.call([sys.executable,f]) for f in fs]; sys.exit(1 if (not fs or any(rcs)) else 0)"
    Then these suites:
      py -3 .claude/scripts/tests/test_auto_improve_finish_install.py
      py -3 .claude/scripts/tests/test_preview_apply.py
      py -3 .claude/scripts/tests/test_plugin_root.py
      py -3 .claude/scripts/tests/test_land_contract_verification.py
      py -3 .claude/scripts/tests/test_registry_append.py
      py -3 .claude/scripts/tests/test_registry_layout.py
      py -3 .claude/scripts/tests/test_plugin_text_scans.py
      py -3 .claude/scripts/tests/test_plugin_manifests.py
        This one exits non-zero with exactly one failing row, the amendment-6 INV-O1 exception. Any other red row
        is a real failure.
    Then live:
      py -3 .claude/scripts/registry_migrate.py --check --project .
        Expected: exit 0, state current.
      py -3 .claude/scripts/validate_registries.py --check-structure --project .
        Expected: exit 0, printing only R4 lines, the digest: line and at most one "advisory: R3 universal-candidate
        skipped" line. Any R1, R2, R3, R5 or A1 line stops the sub-task with AMENDMENT.
  - Version: edit no version file. Only the landing raises the version.
  - Route: an ordinary task-branch pull request into fix/235-domain-split-registries. No merge of origin/master,
    no push to the parent branch, no rebase, amend or force-push. Block 18's live last check judges whether
    origin/master has moved into a conflict.
  - Evidence (t14 W1): paste every output this TASK names, raw, in the pull request description or one pull request
    comment. A ticked line is not evidence.
  - No registry append besides the MECHANISMS.md Correction line and the journal lesson.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-04-domain-split-registries.md
  contract_status: approved
```

## Out of scope
- Anything outside the files and constraints of the handoff block above.

## Known context
- Parent / epic: #235
- Related items: sub-task 16 (#320), the landing report of run 20261109T154140Z-97de67
- Affected areas: see the handoff block's Files to touch

## North-star alignment
- inherited from .claude/work-items/2026-11-04-235-domain-split-registries.md

## Open questions from intake
- none

## Size
Sub-task of an approved contract.

## Routing
task of .claude/concepts/2026-11-04-domain-split-registries.md - dispatched by /advance
