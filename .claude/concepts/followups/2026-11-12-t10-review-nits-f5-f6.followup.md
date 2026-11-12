# Follow-up — t10 review nits F5 and F6 (task skill path name, preload test setup)

**Parent contract:** `.claude/concepts/2026-11-11-audit-followups-165.md`
**Derived from:** owner decision Q9 (2026-11-12) on the t10 review findings, not an Adjacent Areas scan (the area map is empty)
**Date:** 2026-11-12
**Status:** stub
**Estimated scope:** trivial
**Issue:** #354

## What was noticed

The block-10 review of the parent contract (`.claude/reviews/2026-11-11-audit-followups-165/t10-review-fullstack-code-reviewer.md`) raised two nits that the owner kept out of the remedy (parent contract `## Open Questions for User` Q9, `## Non-Goals`). F5: in `skills/task/SKILL.md` the 5c base proof now says `<plan path>` (about line 467), but the VS Code window paragraph (about line 482) still writes `.claude/worktrees/<wt>`. It is one location with two names. F6: in `.claude/scripts/tests/test_agent_skill_preloads.py` the two tests block 4 added repeat the same `sys.path` setup and import lines. A `setUpClass` would hold them once.

## Why it was deferred

The owner folded only F4 into the remedy, so remedy blocks 12 and 13 judge only the t10 blockers and F3.

## Suggested next step

Make one small change after the parent contract lands. F5: use one name for the worktree path in both paragraphs, and run `test_flat_worktree.py`, `test_parent_branch_rule_text.py` and `test_ship_skill_sync.py`. F6: move the shared setup into `setUpClass`, and run `test_agent_skill_preloads.py`. Both are shipped files, so the change raises the plugin version.

## Pre-derived context

- **Adjacent area:** none (`.claude/area-mapping.json` has no areas)
- **Files implicated:**
  - `skills/task/SKILL.md`
  - `.claude/scripts/tests/test_agent_skill_preloads.py`
- **Mechanisms touched:**
  - `Flat worktree helper` (F5 wording only)
- **Journal entries to re-read when promoting:**
  - `2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test`
