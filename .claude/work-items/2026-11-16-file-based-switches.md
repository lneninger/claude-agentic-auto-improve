---
id: 419
issue_offer: opened
title: Replace environment-variable switches with file-based switches
type: IMPROVEMENT
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/419
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/file-based-switches
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261116-feature-file-based-switches
north_stars: none
contract: .claude/concepts/2026-11-16-file-based-switches.md
pr: none
issue_link: unknown
status: designing
created: 2026-11-16
---

# Replace environment-variable switches with file-based switches

## Problem statement
The user finds environment variables a confusing way to switch a guard or a behaviour on or off, and has made "no environment variables as a mechanism" a mandatory rule. Several hooks and scripts of this plugin still read their own switches from environment variables, for example the concept-gate bypass, the pinned contract and the destructive-database override. Each of those switches must become a visible, file-based setting. Variables that Claude Code itself supplies to a hook are not switches and stay.

## Acceptance criteria
- [ ] Every switch the plugin owns and reads from the environment is replaced by a setting read from a file. The inventory of those switches is produced by the contract and checked by a test that scans the shipped hooks and scripts for any remaining read of an own switch.
- [ ] A single shared helper reads the settings. Project defaults come from one committed file, `.claude/switches.json`. An optional uncommitted file, `.claude/switches.local.json`, overrides it for one person. Every hook uses that helper, so no hook parses a settings file of its own.
- [ ] A missing, empty or unreadable settings file leaves every guard in its current default state (enabled). A malformed file is reported once in the hook's error log and never turns a guard off.
- [ ] Setting a switch in the file changes the behaviour exactly as the old variable did. A test per switch proves the on state and the off state.
- [ ] The destructive-database override is human-only. An agent cannot grant it to itself by writing the file. The contract picks the mechanism (recommended: a one-shot override file that the guard deletes after one use, and that the guard itself refuses to let an agent write), and a test proves an agent write is blocked.
- [ ] The variables Claude Code supplies (`CLAUDE_PROJECT_DIR`, `CLAUDE_PLUGIN_ROOT`, `CLAUDE_CONFIG_DIR`, `CLAUDE_SESSION_ID`, `CLAUDE_CODE_SESSION_ID`) are still read, and a test proves they are not treated as switches.
- [ ] README, CONTRIBUTING, the skills, the registry entries and the user-facing guard messages describe the file setting and no longer name an environment variable as a way to switch anything.
- [ ] The plugin mirror is updated and the plugin version is bumped, following the pattern of the earlier mirror changes.
- [ ] The existing test suite passes, with the tests that set an old variable rewritten to write the file setting instead.

## Out of scope
- The variables Claude Code supplies to hooks (listed above). They are plumbing, not switches.
- Test-only fault-injection variables such as `DB_GUARD_FAULT_INJECTION`, unless the contract decides they are also confusing switches. The contract states its decision.
- The user's private global instructions file, which only the user edits. The pull request body lists the lines that become stale there.
- Adding any new guard or any new switch.

## Known context
- Parent / epic: none
- Related items: `.claude/work-items/2026-10-31-119-t3-remove-the-add-on-kill-switches.md` (issue 119) already removed `CLAUDE_SKIP_CG`, `CLAUDE_BASH_GATE` and the add-ons' use of `CLAUDE_CONCEPT_GATE`. The plain-language guard hook is also gone. This item covers the default hooks' switches that remain. The contract must reconcile with that item's reasoning for removing kill switches outright, and record why these switches become file settings instead of being deleted.
- Affected areas (best guess, to be confirmed by the contract): the switch reads in `.claude/hooks/concept-gate.py` (`CLAUDE_CONCEPT_GATE`, `CLAUDE_ACTIVE_CONTRACT`), `architecture-guard.py` (`CLAUDE_ARCH_GUARD`), `critic-verdict-tracker.py`, `contract-status-watcher.py` and `journal-post-approval-tracker.py` (`CLAUDE_ACCURACY_TRACKER`), `integration-check.py` (`CLAUDE_INTEGRATION_CHECK`), `memory-pager.py`, `working-agreements.py` (`CLAUDE_WORKING_AGREEMENTS`), `db-destructive-guard.py` and `db-research-readonly-guard.py` (`CLAUDE_DESTRUCTIVE_DB_OK`), `.claude/scripts/_contract_index.py` (`CLAUDE_CONTRACT_INDEX`), their tests, `README.md`, `CONTRIBUTING.md`, the skills that name a variable, and the registries. The contract produces the exhaustive inventory.

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- Which file holds the switches, and who may change it? → **Answer (from the invocation, a stated assumption):** `.claude/switches.json` committed for project defaults, `.claude/switches.local.json` uncommitted for personal overrides, one key per switch, one shared reader.
- How does a human-only override survive when an agent can write files? → **Answer (stated assumption, contract to confirm):** a one-shot override file that the guard consumes after one use and that the guard blocks agents from writing.
- Is the safety-critical path involved? → **Answer:** yes. The destructive-database guard is a safety-critical path, so `/tdd-first` is mandatory with no opt-out and a security reviewer is required.
- Should an issue be opened for this item? → **Answer:** not yet asked. `issue_offer` stays `pending`, and `/ship` asks before the pull request.

## Size
L — about a dozen hooks and scripts, their tests, several skills and documents, the plugin mirror and a version bump, plus one safety-critical design decision.

## Routing
non-trivial → /design-first
