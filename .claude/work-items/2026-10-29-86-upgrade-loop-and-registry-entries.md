---
id: 86
issue_offer: pending
title: Fix the add-on upgrade loop and write the missing registry entries
type: BUG
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/86
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: fix/86-upgrade-loop-and-registry-entries
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261029-bug-86-upgrade-loop-and-registry-entries
north_stars: none
contract: .claude/concepts/2026-10-29-upgrade-loop-and-registry-entries.md
pr: none
partial: true
issue_link: unknown
status: designing
created: 2026-10-29
---

# Fix the add-on upgrade loop and write the missing registry entries

## Problem statement
Plugin 0.10.0 shipped contract `2026-10-28-angular-tailwind-rule-documents` with two review findings unfixed (review: `.claude/reviews/2026-10-28-angular-tailwind-rule-documents/t9-review-fullstack-code-reviewer.md`). **F1:** when the old angular-tailwind advisor hook entry sits only in `.claude/settings.local.json`, the install refuses with `disabled-hook-present` and says to run the uninstall, but the uninstall only edits `.claude/settings.json` and reports `nothing-to-do`, so the upgrade loops (`auto_improve_finish_install.py` lines 2096-2107 for the refusal, 2848-2855, 2866 and 2879 for the removal). **F5:** the `MECHANISMS.md` and `VOCABULARY.md` entries the contract required were never written. This work item is tracked under the follow-ups issue #86, which it references but must not close, because #86 also lists unrelated deferred items.

## Acceptance criteria
- [ ] With the old advisor row present only in `settings.local.json`, in both the `${CLAUDE_PLUGIN_ROOT}` form and the `${CLAUDE_PROJECT_DIR}` form, running the uninstall removes that row (with a backup of the file, written before any other change) and a following install no longer refuses with `disabled-hook-present`.
- [ ] Failure path: the removal leaves every other row in `settings.local.json` and `settings.json` untouched, and when no owned row exists in either layer it still reports `nothing-to-do`.
- [ ] A test plants the old row in each layer the refusal reads (`project` and `local`), asserts the refusal fires, runs the removal, and asserts the refusal clears. It fails on the current code.
- [ ] `MECHANISMS.md` (Universal section) has the "Disabled add-on hook" entry, and the Preview-hash apply entry has the `addon-remove` sentence, both worded as in the review's Disposition item 5.
- [ ] `VOCABULARY.md` (Universal section) has the five terms (Add-on, Add-on manifest, Disabled add-on hook, Add-on document, Rule ID) and the Placeholder slot amendment, as worded in the contract's Business Concept.
- [ ] The plugin version rises by one patch (0.10.0 to 0.10.1) in all five places, and `py -3 .claude/scripts/check_version_bump.py` exits 0.
- [ ] The landing gate steps pass: the version check, the loop-script tests, and the hook tests; and the install test suite (`test_auto_improve_finish_install.py`) passes.
- [ ] Optional, only if small: F2, the skill count in `README.md:436` and the four manifest descriptions reads 32, with a manifest test comparing the count in each description to the number of `skills/*/SKILL.md` files; and F3, the `skills/angular-ui-rules/SKILL.md` T-001 line reads as the review proposes.

## Out of scope
- Every item on issue #86 (guard weak spots, the other add-ons' kill switches, the disabled advisor keyword, doctor and preload gaps, candidate patterns, `.claude/rules/` delivery).
- F4 (amending the implemented contract's version wording), F6 (the PowerShell trial against an installed copy), and nits F7 to F10.
- Closing issue #86 or #84.

## Known context
- Parent / epic: #86 (open follow-ups issue), from contract #84 (closed, landed as pull request 109).
- Related items: review findings F1 to F10 in the t9 review artefact; `README.md:282` claims the uninstall "finds the row in every form above".
- Affected areas (best guess, to be confirmed by the contract): `.claude/scripts/auto_improve_finish_install.py`, `.claude/scripts/tests/test_auto_improve_finish_install.py`, `.claude/registries/MECHANISMS.md`, `.claude/registries/VOCABULARY.md`, the five version files, and optionally `README.md`, `skills/angular-ui-rules/SKILL.md`, `.claude/scripts/tests/test_plugin_manifests.py`.
- The installer rewrites user settings files, so `/tdd-first` applies: the test is written first and must fail first.

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- Which F1 fix? The review allows two: (a) the removal also takes owned rows out of `settings.local.json`, with its own backup, or (b) the refusal and the uninstall plan tell the user to delete that row by hand. → **Answer:** assumed (a), because `README.md:282` already promises the uninstall "finds the row in every form above" and (b) leaves the documented remedy unable to succeed. To be confirmed when the contract is approved.

## Size
M — a behaviour fix in the installer's settings writer plus registry appends and a version bump across five shipped files.

## Routing
non-trivial → /design-first
