---
id: none
issue_offer: pending
title: Fix the advisor's missing reference folder and the red skill-lookup test
type: BUG
source: free-text
repo: lneninger/claude-agentic-auto-improve
url: none
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: fix/followups-advisor-refs-and-lookup-test
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261022-bug-followups-advisor-refs-and-lookup-test
north_stars: none
contract: .claude/concepts/2026-10-22-advisor-refs-and-lookup-test.md
pr: UNKNOWN
issue_link: unknown
status: designing
created: 2026-10-22
---

# Fix the advisor's missing reference folder and the red skill-lookup test

Raw invocation: `Fix two follow-ups from the web-design skills contract (pull request 72, merged). (1) The angular-tailwind add-on's reminder hook ... points at a design-reference folder that does not exist ... (2) test_skill_script_lookup.py fails 21 times, in the lookup block at skills/verify-before-done/SKILL.md line 36 (13 failures) and skills/ship/SKILL.md line 151 (8 failures); find the root cause and fix it. Deliver as one pull request.`

## Problem statement
Two defects were left over from the web-design skills work (pull request 72).

1. The opt-in angular-tailwind add-on has a hook (`.claude/addons/angular-tailwind/hooks/angular-tailwind-advisor.py`) that tells the agent to read four files under `~/.claude/references/ui-ux-pro-max/`. That folder never existed. The agent file that used to cite it recorded this twice. The right target now is the `agentic-auto-improve:application-design` skill (and `website-design`).
2. `.claude/scripts/tests/test_skill_script_lookup.py` fails 21 times. The failures are in the script-finding block of `skills/verify-before-done/SKILL.md` (line 37, 13 failures) and `skills/ship/SKILL.md` (line 152, 8 failures). Both still use the old one-line `ls ... | head -1` lookup for `land_contract.py`. That form picks an old cache folder (for example 0.3.1) ahead of a newer one (0.8.1), and ignores the install record. Every other skill (for example `skills/advance/SKILL.md` lines 337-359) carries the shared, tested lookup instead. The root cause is the two stale blocks, confirmed by reading; the test run will confirm it.

## Acceptance criteria
- [ ] The advisor hook's layout nudge no longer names any path that does not exist. It points at the two design skills by their full names and says the skills are advisory and that the project's `review.documents` win.
- [ ] A test proves the nudge never names a path under `~/.claude/references/ui-ux-pro-max/` (or any path that does not exist).
- [ ] The advisor's reference-file list for the phantom folder is removed or no longer printed; nothing else in the hook's output changes.
- [ ] The lookup blocks in `skills/verify-before-done/SKILL.md` and `skills/ship/SKILL.md` use the same shared lookup as `skills/advance/SKILL.md`, with the variable still named `LANDER` and the script still `land_contract.py`.
- [ ] `py -3 .claude/scripts/tests/test_skill_script_lookup.py` ends with `OK` and exit code 0.
- [ ] Failure path: with no plugin install and no project copy, `LANDER` comes out empty and both skills still tell the reader to fall back (verify-before-done keeps its prose steps; ship keeps its hand-derivation).
- [ ] The plugin version is raised and all manifests agree; `check_version_bump.py --base origin/master` passes after the commit.
- [ ] The follow-up detail file records the issue as not opened and is marked superseded by the new contract.

## Out of scope
- The 12-versus-17 hooks count drift in the README.
- `check_version_bump.py` counting `.claude/reviews/` as shipped files.
- Opening any GitHub issue.
- Rewriting the add-on's CSS/Tailwind reminder text.

## Known context
- Parent / epic: none (follow-ups of `.claude/concepts/2026-10-22-webdesign-plugin-skills.md`, delivered by pull request 72)
- Related items: pull request 72 (merged), pull request 73 (records, draft)
- Affected areas (best guess): `.claude/addons/angular-tailwind/hooks/angular-tailwind-advisor.py`, its test file, `skills/verify-before-done/SKILL.md`, `skills/ship/SKILL.md`, the manifests, `.claude/concepts/followups/2026-10-22-advisor-phantom-design-refs.followup.md`

## North-star alignment
- none — the register holds no active thought

## Open questions from intake
- One pull request or two? → **Answer:** one, as the user asked.
- Which design skills does the nudge name? → **Answer (assumption):** `agentic-auto-improve:application-design` for layout requests, with `website-design` named for page requests; both advisory.
- Should the version bump be a patch? → **Answer (assumption):** yes, 0.9.17, after pull request 73 and any other change on master are accounted for (check master's current version first).

## Size
M — a hook text change with a new test, plus two skill blocks that a pinned test covers; no data shape, but it edits Python and touches a tested mechanism.

## Routing
non-trivial → /design-first
