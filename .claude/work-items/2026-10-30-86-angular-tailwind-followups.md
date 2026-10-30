---
id: 86
issue_offer: pending
title: Follow-ups from Replace the angular-tailwind prompt hook with rule documents and a skill (2026-10-28-angular-tailwind-rule-documents)
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/86
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/86-angular-tailwind-followups
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261030-infra-86-angular-tailwind-followups
north_stars: none
contract: .claude/concepts/2026-10-30-angular-tailwind-followups.md
pr: none
issue_link: unknown
status: designing
created: 2026-10-30
---

# Follow-ups from the angular-tailwind rule documents contract

## Problem statement
Issue #84 replaced the angular-tailwind prompt hook with rule documents and a skill. Its contract (`.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md`) deliberately left six groups of work open. Detail lives in the stub `.claude/concepts/followups/2026-10-28-angular-tailwind-deferred-items.followup.md`. This item carries those groups to delivery.

## Acceptance criteria
Taken from the six checkboxes of the issue, one criterion each. The issue gives no further wording, so each criterion is the checkbox itself; a testable form is fixed by the contract.
- [ ] Guard weak spots in `.claude/hooks/architecture-guard.py` are each fixed or explicitly recorded as accepted: hard-coded `projects`, `/ClientApp/`, `/features/` folder names; only `*.component.*` files scanned; hex regex matching `#add`; `relative` and `absolute` never checked; multi-edit gap; height-chain sees only the edited fragment; stylesheet rules only warn; stale global-hooks-folder pointers (including the guard docstring's `~/.claude/hooks/architecture-guard.exceptions.json` and a design document citing a reference path that does not exist).
- [ ] The maintainer's decision on the kill switches of `codegraph` (`CLAUDE_SKIP_CG`) and `strict-shell-gate` (`CLAUDE_BASH_GATE`, `CLAUDE_CONCEPT_GATE`) is recorded, and `.claude/addons/codegraph/addon.json` and `.claude/addons/strict-shell-gate/addon.json` match it.
- [ ] The disabled advisor keyword `ui`, which can never match (the pattern needs three characters), is corrected or its limit stays documented in `DISABLED.md`.
- [ ] `plugin_doctor.py --drift` compares add-on documents and reports a disabled add-on hook that is still installed; `python-ai-developer` no longer preloads the `python-ai` skill the plugin does not ship (or the skill ships).
- [ ] Each candidate pattern (status badge, table rules beyond T-023, card surface, `constrained-panel`) is either added to `.claude/addons/angular-tailwind/documents/UI-UX-PATTERNS.md` or recorded as rejected, on the maintainer's decision.
- [ ] The delivery route through project `.claude/rules/` files with path frontmatter is tested and the outcome recorded.

## Out of scope
- Anything outside the six groups above.
- Changing the settled rules and conflicts of issue #84.

## Known context
- Parent / epic: issue #84 and its contract `.claude/concepts/2026-10-28-angular-tailwind-rule-documents.md`
- Related items: #84
- Affected areas (best guess): `.claude/hooks/architecture-guard.py`, `.claude/scripts/plugin_doctor.py`, `agents/python-ai-developer.md`, `.claude/addons/angular-tailwind/documents/UI-UX-PATTERNS.md`, `.claude/addons/codegraph/addon.json`, `.claude/addons/strict-shell-gate/addon.json`
- Journal lessons to re-read: 2026-10-17 (loosening a guard rule against its test fixtures), 2026-10-04 (check a documented guard behaviour against the code)
- The issue has one comment, three "Not performed" notes from the contract's closing checklist; they add no requirement.

## North-star alignment
- none — the register holds no active thought (`.claude/north-stars/` does not exist)

## Open questions from intake
- Two groups need a maintainer decision (kill switches; candidate patterns). → **Answer:** Assumption, no answer was available in this background run: these go to `/design-first` as Open Questions, where the maintainer answers them at the contract gate, before any rule text or addon change is written. The stub's own suggested next step says the same.
- Is all six groups one delivery or several? → **Answer:** Assumption: one contract with a sub-task per group, as the stub suggests for the guard group; the contract may split further.

## Size
L — six groups across a guard hook, a doctor script, an agent file, two addon manifests and a patterns document, with two maintainer decisions.

## Routing
non-trivial → /design-first
