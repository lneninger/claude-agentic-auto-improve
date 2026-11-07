---
id: 259
issue_offer: pending
title: codegraph-first-guard blocks all source reads when CodeGraph tools are unavailable (parent session and subagents)
type: BUG
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/259
labels: [bug]
milestone: none
project: claude-agentic-auto-improve
branch: fix/259-codegraph-guard-fail-open
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261105-bug-259-codegraph-guard-fail-open
north_stars: none
contract: .claude/concepts/2026-11-05-codegraph-guard-fail-open.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/270
issue_link: closes
status: shipped
created: 2026-11-05
---

# codegraph-first-guard blocks all source reads when CodeGraph tools are unavailable

Raw argument: `https://github.com/lneninger/claude-agentic-auto-improve/issues/259`

## Problem statement
The code-search-first guard (a hook that runs before every `Read`, `Grep` and `Glob`) blocks reads of source files until a CodeGraph tool has been called in the current turn. It does so even when no CodeGraph tool can be called: in background sessions and in subagents the tools never attached. The guard then becomes a hard wall, and a delivery step (sub-task t14 of another project's contract) could not finish. CodeGraph is a substitute for investigation, not a precondition for it, so the guard must never remove the ability to read code when that tool is unavailable.

The issue's update of 2026-11-05 adds a second defect: the plugin names individual CodeGraph tools (`codegraph_node`, `codegraph_callers`, and so on), but the server now offers only `codegraph_explore`. Names must be replaced by the wildcard `mcp__codegraph__*` everywhere.

## Acceptance criteria
- [ ] With no `mcp__codegraph__*` tool available to the caller, `Read`, `Grep` and `Glob` on a `.cs` or `.ts` file are allowed, and one log line says why.
- [ ] A subagent without CodeGraph tools can `Read` and `Edit` source files.
- [ ] With CodeGraph available and no marker for the session, the first call is still blocked, and the block message names only tools that exist (positive control test).
- [ ] Changing directory (`cd` or `EnterWorktree`) mid-turn does not re-block a session that already called CodeGraph (the marker is keyed to the session, not the working directory).
- [ ] A project with no `.codegraph/` index is allowed (the documented auto-bypass is implemented).
- [ ] An in-session, logged escape exists: after one block, the retry of the same call is allowed once, with no environment variable set beforehand.
- [ ] No file in the plugin names a specific `mcp__codegraph__codegraph_*` tool, except tests that prove the wildcard covers it. Settings template and installers allow `mcp__codegraph__*`; agent `tools:` frontmatter grants `mcp__codegraph__*`.
- [ ] The turn tracker's matcher keeps `mcp__codegraph__.*`; a test shows `codegraph_explore`, a legacy name and an unknown future name all create the marker.
- [ ] A test fails if the settings template lists a per-tool entry instead of the wildcard.
- [ ] The installer and `/verify-before-done` fail loudly when `settings.json` names a CodeGraph tool the installed server does not offer, or omits the wildcard.
- [ ] The installer can offer to build a worktree-local index, and says plainly when the index belongs to a different working tree.
- [ ] The plugin README and `.claude/references/codegraph-decision-table.md` describe the fail-open rule.
- [ ] Tests for each rule above, added to `test_codegraph_first_guard.py` (the existing guard test file) or a new file.

## Out of scope
- Diagnosing why background sessions and subagents do not receive the project's MCP tools (the issue says a separate issue should find out).
- The `bash-gate` refusing edits to test files of an already-approved contract (the issue says it deserves its own issue).
- Running `codegraph sync` on any project's index.

## Known context
- Parent / epic: none
- Related items: none linked
- Affected areas (best guess, to be confirmed by the contract): `.claude/addons/codegraph/hooks/codegraph-first-guard.py`, `codegraph-turn-tracker.py`, `codegraph-turn-reset.py`, `.claude/addons/codegraph/addon.json`, `.claude/hooks/tests/test_codegraph_first_guard.py`, `.claude/references/codegraph-decision-table.md`, `skills/auto-improve-codegraph-install/SKILL.md`, `skills/auto-improve-codegraph-uninstall/SKILL.md`, agent definitions that list `mcp__codegraph__*` tools, settings template, README.
- The issue calls the hooks `.claude/hooks/codegraph-*.py`; in this repo they live under `.claude/addons/codegraph/hooks/`. Assumed the issue means these files.

## North-star alignment
- none — the register holds no active thought (`.claude/north-stars/` does not exist).

## Open questions from intake
- None blocking. Assumption: the issue text is complete and its comment thread is empty, so its acceptance criteria stand as written.

## Size
L — touches three hooks, installers, agent definitions, a settings template, docs and tests, and changes a gate's session-identity model.

## Routing
non-trivial → /design-first

## Run log

- 2026-11-05 design stage: the contract was drafted and reviewed three times. Round 1 found 2 blockers (a missing test file; acceptance criteria 1-2 narrowed). Round 2 found 1 blocker (criterion 5 narrowed by the "undecidable" case). Round 3 found 1 blocker: the "no index" search treats any `.codegraph` folder up the path as an index, but `~/.codegraph` is CodeGraph's own data folder (no `codegraph.db`), so the allow never fires under the home folder. Retry budget used; stopped for the operator.
- Live trial (Claude Code 2.1.318): subagent payload carries `agent_id`/`agent_type`; `transcript_path` and `session_id` present in both; the permission wildcard form is not established.
- Follow-up opened: #261 (CodeGraph hook redesign, shadow-mode rollout).
- 2026-11-05 implement and review stages: contract approved (status approved, two addenda). Test-first red/green done (guard 439, worktree guards 189, add-on 28, installer 383, manifests 190, scans 19, main-checkout guard 56, all green at the last implementer run). Three review passes (code reviewer, test-strategy critic, security auditor) and two fix rounds. Third pass: 0 blockers, but both reviewers ask for more fixes. Retry budget used; stopped for the operator. Nothing is committed or pushed.
- Open after pass 3: (P3-W1) normalise before the host check on the commondir hop, in the four hop-function copies; (P3-W2 / W2) bind the guard's tree functions only when the helper carries the hop refusal, test with HEAD's real helper; (W1) a mapped-drive repository with a worktree on another volume now reads undecidable, which blocks writes in the main-checkout guard, fix needs a one-line change to Addendum 2 item 7; (W3) parity row for the four hop-function copies; (W4) MECHANISMS.md:43 correction; nits: escape the dot in TICKET_RE, no trailing underscore in the server-name grammar, list test_main_checkout_guard.py in Files to touch.
- Held for the operator, not implemented: Windows owner check or per-user parent for session folders; turning the codegraph-tool-named refusal into a finding.
- Known unrelated failure: test_verify_issue_link.py row 20 (brief 2026-11-02-171 has pr: UNKNOWN, tracked on master).
- 2026-11-05 ship: pushed fix/259-codegraph-guard-fail-open and opened draft pull request #270 (title [INFRA][TESTS][DOCS], body ends Refs #259). verify_issue_link.py returned unexpected-closing-ref: GitHub reports #259 as a closing reference of the pull request although the brief is partial. Likely cause: the branch was created with gh issue develop (linked branch). Not repaired, nothing changed on GitHub; waiting for the operator: unlink the branch in the issue Development sidebar, or accept the close and mark the item not partial. Status stays verifying; issue_link stays unknown.
- 2026-11-05: merged and recorded (https://github.com/lneninger/claude-agentic-auto-improve/pull/270); contract 2026-11-05-codegraph-guard-fail-open flipped to implemented by pr_merged.py; owner confirmed resolved: none; not performed and disclosed on #259: none
