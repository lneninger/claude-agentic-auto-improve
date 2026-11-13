---
id: 354
issue_offer: pending
title: Follow-ups from Audit follow-ups for issue 165 (2026-11-11-audit-followups-165)
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/354
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/354-audit-followups-165-chores
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261113-infra-354-audit-followups-165
north_stars: none
contract: .claude/concepts/2026-11-13-audit-followups-165-chores.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/406
issue_link: closes
status: shipped
created: 2026-11-13
---

# Follow-ups from Audit follow-ups for issue 165 (2026-11-11-audit-followups-165)

## Problem statement
The contract `.claude/concepts/2026-11-11-audit-followups-165.md` (work item #165) deferred three findings that were outside its scope. Its landing is merged (pull request #401 and the records pull requests #402 and #403), so the wait that the first finding named is over. The findings are: the four plugin manifests state wrong skill and agent counts; two shipped agents carry chat-tool text from a consuming project; and two review nits from the block-10 review remain open.

## Acceptance criteria
- [ ] The description strings of the four manifests (`plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.cursor-plugin/plugin.json`) state the real skill and agent counts (the follow-up records 34 skills and 15 agents; the contract re-counts them from the tree).
- [ ] A test in `.claude/scripts/tests/test_repo_consistency.py` reads the real manifests, uses the count helper that block 9 of #165 shipped, and fails when a description count differs from the tree.
- [ ] The plugin version is raised by one patch step in every manifest, as the version-raise rule requires for shipped files.
- [ ] `agents/contract-critic.md` (checklist item 7) no longer cites a consuming project's contract as its precedent, and keeps the template heading and its three sanctioned answers.
- [ ] `agents/fullstack-code-reviewer.md` (lines 170-178) no longer names `ChatToolDefinitions.cs`, `SystemPromptBuilder.cs`, `python/training-data/synthetic/` or the `llm-training-engineer` agent; it cites the project-profile slots and `.claude/hooks/sentinel-paths.json` instead.
- [ ] The existing template pin of block 3 is extended to cover the two agent files, so the consuming-project names cannot return.
- [ ] F5: `skills/task/SKILL.md` uses one name for the worktree path in the base-proof paragraph and the VS Code window paragraph; `test_flat_worktree.py`, `test_parent_branch_rule_text.py` and `test_ship_skill_sync.py` pass.
- [ ] F6: the two tests in `.claude/scripts/tests/test_agent_skill_preloads.py` share their `sys.path` setup and imports through one `setUpClass`; the file passes.

## Out of scope
- Any other consuming-project text in the shipped files beyond the two named agent passages.
- Changing the template's "Chat Tool Impact" heading or its three sanctioned answers (block 3 keeps them on purpose).
- Any other count in the repository documents beyond the four manifest descriptions (the README pins stay with block 9).
- Other review findings from the #165 reviews (F1 to F4 were handled in the remedy blocks).

## Known context
- Parent / epic: contract `.claude/concepts/2026-11-11-audit-followups-165.md`, parent issue #165 (landed)
- Related items: #165; follow-up stubs under `.claude/concepts/followups/2026-11-11-manifest-description-counts.followup.md`, `.../2026-11-11-agent-chat-tool-genericity.followup.md`, `.../2026-11-12-t10-review-nits-f5-f6.followup.md`
- Affected areas (best guess, to be confirmed by the contract): the four manifest files; `agents/contract-critic.md`; `agents/fullstack-code-reviewer.md`; `skills/task/SKILL.md`; `.claude/scripts/tests/test_repo_consistency.py`; `.claude/scripts/tests/test_agent_skill_preloads.py`

## North-star alignment
- none — the register holds no active thought (`.claude/north-stars/` does not exist)

## Open questions from intake
- Single block or several? → **Answer (assumed, no blocking question):** one single-block contract. The three items are small, share one version raise, and the manifests are version files that a sub-task may not list, so splitting would recreate the `sub-task-raises-version` defect. The architect may propose otherwise and the owner decides at the contract gate.
- How big is the version raise? → **Answer (assumed):** one patch step, as the first item states.

## Size
M — three independent edits across shipped agent, skill, manifest and test files, plus a version raise; touches a pinned template test.

## Routing
non-trivial → /design-first
