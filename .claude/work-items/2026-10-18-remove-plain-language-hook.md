---
id: none
issue_offer: declined
title: Remove the plain-language guard hook from the plugin
type: CHORE
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: infra/remove-plain-language-hook
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261018-infra-remove-plain-language-hook
north_stars: none
parent_issue: none
base: master
contract: .claude/concepts/2026-10-18-remove-plain-language-hook.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/82
issue_link: none
status: shipped
created: 2026-10-18
---

# Remove the plain-language guard hook from the plugin

## Problem statement
The user asked, verbatim: "remove the hook for plain language". The plugin ships a hook called the plain-language guard (`plain-language-guard.py`). It checks the assistant's prose at the end of each turn and asks for a rewrite when a sentence is too long, a short form is not spelled out, or dashes are stacked. The same file has a second entry point (`--carry-forward`) that runs when the user submits a prompt and hands over a saved correction note. The user no longer wants this hook to run.

Assumptions (the user prefers a stated call over a blocking question; each is open to correction at the contract approval step):
- "The hook" means the guard in both of its registrations (end of turn and prompt submit). It does not mean the plain-language *agreement*, which is advice text delivered at session start by a different hook (`working-agreements.py`). That advice stays.
- Because the checker disappears, the agreement's closing sentence ("The end-of-turn writing checker catches some of these breaks.") becomes false, so it is corrected in the same change.
- Removal means deleting the guard, its rules file and its tests from the plugin, and every registration and list that names it. It does not mean leaving the file in place switched off.

## Acceptance criteria
- [ ] `hooks.json` registers no entry that runs `plain-language-guard.py`, neither the prompt-submit entry nor the Stop entry. The Stop group still runs the Changed-file check and the memory pager as before.
- [ ] `stop-dispatcher.py` no longer lists the guard among its members, and the rest of the Stop behaviour (exit codes, merged output, missing-member notice) is unchanged. Its tests are updated and pass.
- [ ] `plain-language-guard.py`, `plain-language-guard.rules.json` and `test_plain_language_guard.py` no longer exist in the repository.
- [ ] The manifest tests, the project-first data-file test and the finish-install script with its tests no longer expect the guard, including the counts of hook files and registrations they assert. All pass.
- [ ] The plain-language agreement stays delivered at session start and is never dropped for size (`ALWAYS_KEPT_SLUG` behaviour is unchanged), and its text no longer claims a checker exists.
- [ ] `README.md`, `MECHANISMS.md` and `VOCABULARY.md` carry no claim that the guard exists. A search for `plain-language-guard` finds only history records (past contracts, work items), never live code, configuration or documentation.
- [ ] Failure path: a project that still registers the guard in its own settings does not crash the plugin; the plugin just no longer ships the file. The change notes this for existing installs.
- [ ] The plugin version is bumped in `plugin.json` and `marketplace.json`, and the change reaches the plugin copy the way earlier fixes did.

## Out of scope
- Removing or rewording the plain-language agreement itself.
- Any other hook, including the memory pager and the Changed-file check.
- Rewriting past contracts, work items and the follow-up note about the guard naming a person; those are history. The follow-up note becomes moot and is closed with a one-line pointer instead.

## Known context
- Parent / epic: none
- Related items: `.claude/concepts/followups/2026-10-05-plain-language-guard-names-a-person.followup.md` (about the guard's stop message; moot once the guard is gone)
- Affected areas (best guess, to be confirmed by the contract): `.claude/hooks/` (`hooks.json`, `stop-dispatcher.py`, the guard and its rules file, `tests/`), `.claude/scripts/auto_improve_finish_install.py` and its tests, `.claude/scripts/tests/test_plugin_manifests.py`, `.claude/agreements/plain-language.md`, `README.md`, `.claude/registries/`, `.claude-plugin/`

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- Does "the hook for plain language" also mean the plain-language agreement text? → **Answer:** assumed no (see Assumptions); to be confirmed when the contract is approved.

## Size
M — removes a registered mechanism and touches the dispatcher, the install script, three test suites, documentation and the plugin version.

## Routing
non-trivial → /design-first
