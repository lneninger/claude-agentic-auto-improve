---
id: 21
issue_offer: pending
title: Follow-ups from the auto-improve-finish-install skill (2026-10-04-auto-improve-finish-install-skill)
type: CHORE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/21
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: feature/21-finish-install-step3-proposals
worktree: D:\Dev\HIPALANET\claude-agentic-auto-improve\.claude\worktrees\20261111-infra-21-finish-install-followups
north_stars: none
contract: .claude/concepts/2026-11-11-finish-install-step3-proposals.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/373
issue_link: closes
status: shipped
created: 2026-11-11
---

# Follow-ups from the auto-improve-finish-install skill

## Problem statement
The issue (opened 2026-10-04) lists two follow-ups deferred from the `/auto-improve-finish-install` skill. Re-read against current master, the first is already delivered and only the second remains.

1. **Database guard rules under a plugin install: already delivered.** Master now reads `db-destructive-guard.rules.json` from `<CLAUDE_PROJECT_DIR>/.claude/hooks/` and nowhere else (INV-O3, in `db-destructive-guard.py` and `db-research-readonly-guard.py`). `README.md` line 201 states that the guards fail closed when the project has no rules file or `CLAUDE_PROJECT_DIR` is unset. The issue's "Decision needed first" was settled by that change.
2. **Quick start step 3 proposals: still open.** `/auto-improve-finish-install` fills `project-profile.md` and registers hooks, but `area-mapping.json`, `work-item-conventions.json` and `.project-tokens.json` are still scaffolded empty by `plugin_doctor.py`. An empty `.project-tokens.json` leaves the outbound memory sync unguarded (the project-name check reads it). An empty area map makes every contract derive `uncategorized`.

## Acceptance criteria
Derived from the follow-up note's "Suggested next step"; the issue itself states none. Confirm them at the contract gate.
- [ ] `/auto-improve-finish-install` proposes content for `area-mapping.json`, `work-item-conventions.json` and `.project-tokens.json`, each with the repository evidence behind it, and writes nothing before one user confirmation.
- [ ] The proposals reuse the existing slot-proposal shape and preview-hash apply rule of `auto_improve_finish_install.py`; no second apply mechanism is created.
- [ ] A slot or file the user already authored is never overwritten.
- [ ] A token the evidence cannot support is not proposed: the skill proposes fewer tokens, never guessed ones, because a wrong token silently weakens the project-name check.
- [ ] Failure path: when the repository gives no evidence, the file stays as scaffolded and the report says so.
- [ ] A test fails without the change and passes with it for each of the three files, including the unauthored-file and no-evidence cases.
- [ ] The README claim about these files (lines near 964, 997, 1312 and 1354) matches what the skill now does.

## Out of scope
- The database guard rules (item 1): already delivered; closed by this item's brief note, not re-done.
- Any change to what an individual hook does.
- Registering hooks and filling `project-profile.md` (the parent skill's own job).

## Known context
- Parent contract: `.claude/concepts/2026-10-04-auto-improve-finish-install-skill.md`
- Stubs: `.claude/concepts/followups/2026-10-04-auto-improve-finish-install-step3-inference.followup.md` and `2026-10-04-db-guard-rules-under-plugin-install.followup.md`
- Related: #351 (hook-text genericity scan), #165 (another follow-up umbrella)
- Affected areas: `.claude/scripts/auto_improve_finish_install.py`, `.claude/scripts/plugin_doctor.py`, `skills/auto-improve-finish-install/SKILL.md`, `README.md`

## North-star alignment
- none: the register holds no active thought (`.claude/north-stars/` does not exist).

## Open questions from intake
- Is item 1 still wanted as written? → **Assumed answer:** no. Master already contains the project-first rules lookup and the README sentence, so item 1 is closed by evidence. The issue checkbox should be ticked at ship time with a pointer to the INV-O3 change.
- Which evidence may support an area map or a token list? → left to the contract; this is a design question, not an intake gap.

## Size
M: new inference logic in a script plus doctor and skill changes, and a risk (wrong token) that warrants a contract.

## Routing
non-trivial → /design-first

## Run log
- 2026-11-11: contract approved by the operator ("approve with recommendations"); four open questions answered per the recommendations.
- Item 1 of the issue (database guard rules) was already delivered on master (INV-O3); closed by evidence, not re-done.
- Assumption made without asking: the plugin-text token check keeps scanning the plugin's tests folders (strict); only its message was improved to name the matching file.
- Review rounds: two fix rounds after independent reviews (one critical each, both fail-safe); third fresh review said SHIP.
- Known follow-up, not fixed (non-blocking, fails safe): a found name with leading or trailing whitespace (e.g. an angular.json key "zorbexshell ") is still shown as a token proposal, then refused when passed back as --token. Fix: add the whitespace rule to _TokenRules.reason plus one test. Also minor: text-mode exclusion lines omit the message; disposable-database exclusion reuses protect-databases wording.
- Contract note: its ProjectFilesPlan row should list the extra plan field narrows-if-tokens when the status flips to implemented.
- 2026-11-11: merged and recorded (https://github.com/lneninger/claude-agentic-auto-improve/pull/373); contract 2026-11-11-finish-install-step3-proposals flipped to implemented by pr_merged.py; owner confirmed resolved: none; not performed and disclosed on #21: Implementation matches Data Shapes exactly | Integration surfaces reflected on both backend and frontend sides | `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced | No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
