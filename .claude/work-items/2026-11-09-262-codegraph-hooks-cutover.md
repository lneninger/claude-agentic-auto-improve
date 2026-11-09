---
id: 262
issue_offer: pending
title: Follow-ups from CodeGraph hooks redesign (2026-11-05-codegraph-hooks-redesign)
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/262
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/262-codegraph-hooks-cutover
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261109-infra-262-codegraph-hooks-cutover
north_stars: none
contract: .claude/concepts/2026-11-09-codegraph-hooks-cutover.md
pr: UNKNOWN
issue_link: unknown
status: designing
created: 2026-11-09
---

# Follow-ups from CodeGraph hooks redesign (2026-11-05-codegraph-hooks-redesign)

## Problem statement
The parent contract `.claude/concepts/2026-11-05-codegraph-hooks-redesign.md` (issue 261, closed) shipped the one-hook, transcript-based turn decision only in shadow mode. The old three-hook design (reset, tracker, guard around a per-session marker) still decides. This item is the deferred cut-over: the guard decides from the transcript turn state and the tracker and reset hooks retire.

**Waiver recorded.** The issue says this work may start only when the shadow report meets the parent's switch-over rule (20 real main sessions, 7 days, 2 projects, zero unexplained `shadow-more-closed`, p95 within the old cost). On 2026-11-09 the user explicitly waived that threshold and asked to start intake. At that date no shadow log existed anywhere; the add-on was installed in `StockToolScalpingMachine` and `StockToolScalpingMachine.Playwright` the same day. The cut-over is therefore designed without the evidence the parent contract required.

## Acceptance criteria
Taken from the issue checklist and the followup stub `.claude/concepts/followups/2026-11-05-codegraph-hooks-cutover.followup.md`. The policy decisions (ideas 2 to 4, the `if` narrowing) are out of scope per the intake answer.
- [ ] The guard (`.claude/addons/codegraph/hooks/codegraph-first-guard.py`) decides "CodeGraph used since the last human prompt" from the transcript turn state, with no marker file.
- [ ] `codegraph-turn-tracker.py` and `codegraph-turn-reset.py` move to the `disabled` list of `.claude/addons/codegraph/addon.json` with their released hashes, and are no longer registered by a new install.
- [ ] The reset hook's once-per-session pruning of old session folders now runs from the guard.
- [ ] A turn opened by a counted `codegraph` command in Bash is not blocked (issue 295 command-line route): the transcript rule counts that Bash call, or the design states why not.
- [ ] Failure path: when the transcript is missing, unreadable or past the scan window, the guard fails open with a logged reason and never blocks on a guess.
- [ ] `test_codegraph_first_guard.py`, `test_worktree_path_guards.py` and `test_addons.py` are updated to match, and the suite passes with an exit code read from a run.
- [ ] An existing install upgrades in place: re-running the install skill removes the retired rows and keeps the project working.

## Out of scope
- Any change to a project outside this repository (the two Scalping projects only supply data).
- The shadow measurement log and report themselves (shipped by the parent).
- Ideas 2 (gate once per session), 3 (never block a Read of one named file), 4 (nudge before blocking) and the `if` narrowing of the guard's registration row. They stay deferred until shadow data exists; issue 262 stays open for them.
- Any change to what the guard blocks. The cut-over keeps today's blocking policy.

## Known context
- Parent / epic: issue 261 (closed), contract `.claude/concepts/2026-11-05-codegraph-hooks-redesign.md`.
- Related items: issue 295 (command-line route).
- Affected areas (best guess): `.claude/addons/codegraph/`, `.claude/hooks/tests/`, the plugin mirror of the add-on.

## North-star alignment
- none: the register holds no active thought (`.claude/north-stars/` does not exist).

## Open questions from intake
- With no shadow data, the issue's decisions on idea 2 (gate once per session), idea 3 (never block a Read of one named file), idea 4 (nudge before blocking) and the `if` narrowing cannot be made from evidence. Do they stay deferred, or are they decided now on judgment? → **Answer:** cut-over only (user, 2026-11-09). The four policy decisions stay deferred, with the issue's checklist items 2 and 3 left open for when shadow data exists. No blocking behaviour changes in this item.

## Size
L: changes a guard hook used by every install, retires two hooks, adds an upgrade path and edits three test files.

## Routing
non-trivial → /design-first
