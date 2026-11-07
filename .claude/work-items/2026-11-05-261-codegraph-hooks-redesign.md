---
id: 261
issue_offer: pending
title: Redesign the CodeGraph hooks: fewer hooks, lower cost per call, safe rollout
type: IMPROVEMENT
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/261
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/261-codegraph-hooks-redesign
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261105-feature-261-codegraph-hooks-redesign
north_stars: none
contract: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/289
issue_link: closes
status: shipped
created: 2026-11-05
---

# Redesign the CodeGraph hooks: fewer hooks, lower cost per call, safe rollout

## Problem statement
The codegraph add-on keeps one yes/no marker file with three hooks. One hook deletes the marker on
every user prompt, one writes it after any CodeGraph tool call, and one blocks source reads when it
is missing. Each hook is a new Python process on every call, and the marker lives under the working
directory, so changing directory or entering a worktree loses it. Issue #259 fixes the immediate
failure (the guard blocks reads when CodeGraph tools are unavailable) and keeps the three hooks.
This item is the larger follow-up: a design that needs fewer hooks, costs less per call and cannot
turn into a wall. Safety comes first: nothing that works today may break, and the worst case must
be "the guard stops nudging", never "the user cannot read code".

## Acceptance criteria
- [ ] A design (concept contract) chooses among the six ideas in the issue, with the evidence for
      each choice, and names the ideas it rejects and why.
- [ ] The new logic first runs in shadow mode beside the old hooks: it only logs what it would have
      decided and enforces nothing. The old hooks are removed only in a later step, after the log
      shows the two agree across real sessions.
- [ ] Every failure path allows the call: an unreadable, missing or changed transcript format, a
      parse error, or a subagent (detected by `agent_id`) never blocks a read.
- [ ] The existing tests pass unchanged: `test_codegraph_first_guard.py`,
      `test_worktree_path_guards.py` and `test_addons.py`. New tests cover each new decision path,
      and a test proves the fail-open behaviour on a corrupt transcript.
- [ ] A project that installed the old add-on can take the new one without a manual step (the
      released-hashes mechanism from #259 is reused, not rebuilt).
- [ ] The cost per gated call is measured for the old and the new design, and both numbers are
      recorded in the contract or the pull request.
- [ ] A measurement log records reason counts and blocks followed by a retry, so later choices rest
      on data.
- [ ] The five open points are each answered by a live check or are recorded as unverified with the
      fail-open rule covering them: subagent transcript location, injected system messages versus
      user prompts, context compaction, parallel tool calls in one assistant message, and format
      stability.

## Out of scope
- The immediate fix of #259 (per-session marker folder, guard behaviour when CodeGraph tools are
  unavailable). It is a separate item and this one builds on it.
- Changing how CodeGraph itself indexes or serves code.
- Any change to the other guard hooks beyond what the three named test files cover.

## Known context
- Parent / epic: none
- Related items: #259 (the immediate fix; keeps three hooks and moves the marker to a per-session
  folder)
- Affected areas (best guess, to be confirmed by the contract):
  `.claude/addons/codegraph/` (addon.json and the three hooks),
  `.claude/hooks/tests/test_codegraph_first_guard.py`, `test_worktree_path_guards.py`,
  `test_addons.py`, `skills/auto-improve-codegraph-install/`,
  `skills/auto-improve-codegraph-uninstall/`, `.claude/references/codegraph-decision-table.md`

## North-star alignment
- none — the register holds no active thought (`.claude/north-stars/` does not exist)

## Open questions from intake
- The issue says the six ideas are "none decided" and lists open live checks. Assumption recorded
  (no blocking question asked): choosing among the ideas and running the live checks is the work of
  the design stage, not a gap in the brief. → **Answer:** assumed, to be confirmed at the contract
  gate.
- Is #259 merged, so its per-session marker and released-hashes work exist on the default branch?
  → **Answer:** to be checked by the design stage against `origin/master`. If it is not merged, the
  contract must declare the dependency.
- This guard sits on a path that can block the user from reading code, so `/tdd-first` is mandatory
  with no opt-out, and a fail-open review is required.

## Size
L — redesigns three hooks plus an add-on upgrade path, needs live experiments, a shadow-mode
rollout and cost measurements.

## Routing
non-trivial → /design-first

## Run log
- 2026-11-07: merged and recorded (https://github.com/lneninger/claude-agentic-auto-improve/pull/268, https://github.com/lneninger/claude-agentic-auto-improve/pull/274, https://github.com/lneninger/claude-agentic-auto-improve/pull/277, https://github.com/lneninger/claude-agentic-auto-improve/pull/282, https://github.com/lneninger/claude-agentic-auto-improve/pull/284, https://github.com/lneninger/claude-agentic-auto-improve/pull/289); contract 2026-11-05-codegraph-hooks-redesign flipped to implemented by pr_merged.py; owner confirmed resolved: none; not performed: none
