---
id: none
title: Deliver the user's working agreements to every session from the plugin
type: FEATURE
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/working-agreements-session-start-injection
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261005-feature-working-agreements-injection
north_stars: none
contract: .claude/concepts/2026-10-05-working-agreements-session-start.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/28
issue_link: none
status: shipped
created: 2026-10-05
---

# Deliver the user's working agreements to every session from the plugin

## Problem statement
The plugin already ships the plain-language guard, which checks a message after it is printed. The written rule behind it, including the part no checker can see (explain every named file or class on first mention), lives only in one person's private memory folder. The plugin has no hook that runs when a session opens, so it cannot hand any working rule to the model at the start. A new machine or a new project gets the checker's stops without the instruction. The same is true of the other habits the user has taught over time. The user stated on 2026-10-05 that every mechanism generally needed for the way they use Claude must be part of the plugin.

## Acceptance criteria
- [ ] In a project with the plugin installed and nothing copied into the project, a session start delivers the text of every shipped agreement to the model. A test runs the hook with a session-start payload and asserts the documented context envelope contains each shipped agreement.
- [ ] The first shipped agreement is the plain-language rule in full: names instead of bare numbers, short forms written out first, one idea per sentence, questions a newcomer can answer, and explaining every named element on first mention.
- [ ] The other shipped agreements are the generic habits: one isolated worktree per change, a branch and pull request for plugin changes, no multi-line commands for the user to paste, "stop" means stop, recommendations instead of batches of questions.
- [ ] No shipped agreement names a project, a machine path or a person. A test scans the shipped files for such tokens.
- [ ] A project can add its own agreement files, and they are delivered together with the shipped ones. A test proves both sets arrive.
- [ ] Failure path: a missing folder, an unreadable file or a malformed file makes the hook exit successfully with no output and a log line. It never blocks or delays a session start. A test covers each case.
- [ ] The delivered text is bounded by a configured size limit. Going over the limit is logged and does not drop the plain-language agreement.
- [ ] The hook is registered in the plugin's hook list, has an environment-variable escape hatch like the other hooks, and is documented in the plugin README inventory.
- [ ] The plugin version is bumped in all five manifest places so installed sessions pick the change up.
- [ ] The change reaches the plugin through a draft pull request from this branch. Nothing is pushed to master.

## Out of scope
- Removing or editing the copies of the guard already living in the consuming repository.
- Habits that name this project's paths, trading code or tools. Those stay in that project.
- Changing the plain-language guard's weights or thresholds.
- A new checker for the element-explanation rule.
- Whether a project file with the same name replaces a shipped one. The contract decides this.

## Known context
- Parent / epic: none
- Related items: plugin pull request #18 (version bump rule), plugin pull request #27 (latest merge on master)
- Affected areas (best guess, to be confirmed by the contract): `.claude/hooks/` (new hook, registration list, tests), a new folder of agreement files, `README.md`, the five manifest files, `.claude/registries/MECHANISMS.md`.

## North-star alignment
- none — the register holds no active thought (the plugin has no north-stars folder)

## Open questions from intake
- Which generic habits beyond the five named belong in the first set? → **Answer:** none. The user confirmed this scope on 2026-10-05 and offered no exclusions.
- Is a plugin-side issue wanted for this item? → **Answer:** not decided. The ship step asks once at ship time.

## Size
M — a new hook, a new content folder, a registration, documentation, tests and a version bump across several files.

## Routing
non-trivial → /design-first
