---
id: none
title: Regenerate README.md so its stated inventory matches the tree
type: DOCS
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: docs/readme-inventory-accuracy
worktree: .claude/worktrees/20260914-docs-readme-inventory-accuracy
north_stars: none - the register holds no active thought
contract: none - XS/S route, no contract required
pr: none
issue_link: unknown
status: verifying
created: 2026-09-14
---

# Regenerate README.md so its stated inventory matches the tree

## Problem statement

README.md states a specific inventory of what this repository ships -- counts of
scripts and test suites, the size of two named test suites, how many skills call a
script, and which registry files are present. Several of those statements no longer
describe the tree. The orchestrator scripts were removed in `d3a3fad` without the
script count following them down, five test suites were added without the suite count
following them up, and `INTEGRATION.md` is listed as shipped when the repository does
not contain it.

Two of the wrong numbers describe the same object: the `pr_merged.py` suite is called
"sixty cases" in one section and "fifty-seven tests" in another, so the file
contradicts itself as well as the tree.

This matters more here than in an ordinary README. The document's own stated purpose is
to tell a consuming project what it is adopting, and the section that carries the
inventory is the one a reader uses to decide whether an asset is present. A count that
is wrong in the safe direction still teaches the reader that the counts are decorative.

## Acceptance criteria

- [ ] Every count in the `## What is included` tree block matches the tree, verified by
      listing it rather than by reading the previous README.
- [ ] `INTEGRATION.md` is no longer claimed as a shipped registry file, because the
      repository does not contain it.
- [ ] The `pr_merged.py` suite is described with one number, and that number is the count
      the suite itself reports when run.
- [ ] The path-resolution suite's stated size is the count that suite reports when run.
- [ ] The count of skills that cite a script under `.claude/scripts/` matches a grep of
      `skills/`.
- [ ] No claim that was already correct is changed: skills 21, agents 14, hooks 16 + 3
      helpers + 4 data files, hook suites 3, templates 6, references 2 all stay as they are.
- [ ] The existing structure, section order and prose voice are preserved -- this is an
      accuracy pass, not a rewrite.
- [ ] `## Status` records this pass with its date.

## Out of scope

- Rewriting the README's structure, headings, or argument. The user chose the accuracy
  pass explicitly over a full rewrite.
- ~~CONTRIBUTING.md, which carries its own copy of the `INTEGRATION.md` claim.~~
  **Brought into scope on request, 2026-09-14.** See `## CONTRIBUTING.md addendum`.
- The four failing cases in `.claude/scripts/tests/test_verify_issue_link.py`. They are
  pre-existing, they fail because this repository is a template rather than a consuming
  project, and a README pass must not quietly change test code.
- Adding a generator that emits the inventory. It was offered as a third option and not
  chosen.

## Known context

- Parent / epic: none
- Related items: `d3a3fad` removed the orchestrator scripts; `1fd5cf9` was the previous
  README accuracy pass, which is why the untouched claims are trustworthy and the
  touched ones are not.
- Affected areas: `README.md` only.

## North-star alignment

- none -- the register holds no active thought. `.claude/north-stars/` does not exist in
  this repository.

## Open questions from intake

- Does "regenerate" mean an accuracy pass or a full rewrite?
  -> **Answer:** Accuracy pass, keeping the current structure and voice. Selected by the
  user when the intake question was presented.
- Should a GitHub issue be opened for this work?
  -> **Answer:** Not answered; the user moved straight to "regenerate the readme file
  again". Proceeding with `id: none`, which is the documented success path for free-text
  work. `/ship` asks once more at ship time.

## Size

S -- one file, no new data shape, no mechanism touched. Every change is a statement of
fact replaced by a verified statement of fact. README.md is on the `concept-gate.py`
trivial allowlist by both extension and filename, so no contract is required.

## Routing

XS/S -> direct edit. No `/design-first`.


## Verification

Every corrected number was taken from the tree or from the suite itself, never from the
previous README.

| Claim | Was | Now | How it was checked |
|---|---|---|---|
| workflow scripts | 19 | 12 + 2 helpers | `ls .claude/scripts/*.py` |
| script test suites | 2 | 7 | `ls .claude/scripts/tests/*.py` |
| `test_pr_merged.py` | "sixty" / "fifty-seven" | 68 | suite prints `Ran 68 tests` |
| `test_script_path_resolution.py` | 74 | 177 | suite prints `177 passed` |
| skills citing a script | six | eleven | `grep -rln '.claude/scripts/' skills/` |
| `INTEGRATION.md` shipped | claimed | removed | not present in `.claude/registries/` |

Left alone because they were already right: skills 21, agents 14, hooks 16 + 3 helpers +
4 data files, hook suites 3, templates 6, references 2, and "all sixteen are registered in
hooks.json" -- the last confirmed by diffing the registrations against the files on disk.

The `.claude/orchestrator/` paragraph was checked and kept: `pr_merged.py` writes those
stores and `plugin_doctor.py` requires them, so it survived the orchestrator-script removal.

Suites: 9 of 10 fully green. `test_verify_issue_link.py` reports 158/162 with 4 failures
that are pre-existing -- the identical four appear with this brief removed, so they are
unrelated to this change. They assert against "the REAL conventions file" and "the real
corpus", both of which are empty template content in this repository by design.


## CONTRIBUTING.md addendum

Added after the README pass, when the user asked for the same claim to be fixed in
CONTRIBUTING.md.

**It was not the same defect.** The README listed `INTEGRATION.md` in its
`## What is included` block, which enumerates shipped files, so the claim was simply
false and deletion was the fix. CONTRIBUTING.md's line is a *sync rule* -- "the Universal
section only, except `INTEGRATION.md` which is whole-file" -- and a rule is not falsified
by the file being absent.

What is wrong with it is subtler. `MECHANISMS.md` line 48 records that `INTEGRATION.md`
"is the one registry with no Universal tier at all". The two-tier split exists precisely so
the Universal half can be shared and the project half cannot. A registry with no Universal
half therefore has nothing shareable in it: every line names one project's endpoints,
DTO-to-model pairings and events. Listing it among the synced assets presents it as an
ordinary member of a set it can never legitimately join -- CONTRIBUTING.md's own
project-name check would halt the first outbound push with exit code 5, and this
repository's not shipping one is the observable evidence that it never travelled.

The replacement states that it does not travel, gives the reason, and routes the reader to
the remedy the document already defines for a one-sided file: leave it out of the `files`
array, where an undeclared file is never compared. Every term it uses -- `ONLY_IN_MAIN`,
exit code 5, the `files` array, "local asset" -- is defined elsewhere in the same document.

`MECHANISMS.md` was deliberately NOT edited. Its sentence describes how the configuration
compares the file, which remains true, and a registry is shared source of truth that a
documentation pass should not quietly rewrite. The new text is phrased to sit alongside it
rather than contradict it.
