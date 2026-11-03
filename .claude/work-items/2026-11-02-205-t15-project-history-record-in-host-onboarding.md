---
id: 205
issue_offer: opened
title: Project history record in host onboarding
type: FEATURE
source: github
repo: lneninger/claude-agentic-auto-improve
url: https://github.com/lneninger/claude-agentic-auto-improve/issues/205
labels: []
milestone: none
project: claude-agentic-auto-improve
branch: task/2026-11-01-memory-client-and-cloud-engineering/t15-project-history-record-in-host-onboarding
worktree: none
north_stars: inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md
parent_issue: 161
base: feature/memory-client-and-cloud-engineering
contract: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
pr: https://github.com/lneninger/claude-agentic-auto-improve/pull/212
issue_link: deferred
status: shipped
created: 2026-11-02
---

# Project history record in host onboarding

## Problem statement
Sub-task 15 of the approved contract `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`, parent issue #161. Its scope is the handoff block below, copied verbatim from the contract.

## Acceptance criteria
### 15. Project history record in host onboarding (`python-ai-developer`)

**Depends on:** 14

**Files to touch:**
- `skills/auto-improve-finish-install/SKILL.md`
- `skills/design-first/SKILL.md`
- `skills/design-first/references/central-memory.md`
- `.claude/scripts/tests/test_memory_off_parity.py`
- `.claude/agreements/use-the-project-history-record.md`
- `.claude/hooks/tests/test_working_agreements.py`

**Pre-written TASK block:**
```
TASK: State the Project history record requirement (Business Concept, Revision 7) in host onboarding,
  on every printed line of /design-first Step 1.5, and in one shipped session-start agreement.
  1. skills/auto-improve-finish-install/SKILL.md: add a section "The project history record" after Stage 2
     and before "Add-ons". It says that the project's record of its design history is its Project history
     record: .claude/registries/MECHANISMS.md, VOCABULARY.md and JOURNAL.md (seeded by the doctor),
     INTEGRATION.md where the project keeps one (no seed exists for it), the concept contracts and
     follow-up stubs under .claude/concepts/, and the Work Item Briefs under .claude/work-items/.
     Who uses it, exactly: /design-first and the data-architect read it on every design. /task writes the
     brief and the data-architect the contract. /design-first appends to JOURNAL.md only the critic
     findings the user confirmed (Steps 3 and 5); fullstack-code-reviewer appends on a justified contract
     divergence and, as janitor, to MECHANISMS.md and VOCABULARY.md; /journal-add appends a manual lesson.
     The contract-critic reads it and never appends. Do not say that anything appends "on every run".
     Commit these files, and never delete, gitignore or bypass them. The Central Memory System, when a
     project switches it on through the memory.* profile slots, only supplements them: it never replaces
     or hides them, and a local entry wins a conflict until the user decides.
     The check (Open Question 23, "Report, then ask before --fix"): run the doctor in report mode
     ($PY "<dir of FI>/plugin_doctor.py" --project .). If it prints "plugin:  NOT FOUND - pass --plugin",
     say in one line that the registries cannot be seeded and ask for the plugin path; offer --fix only
     with --plugin <path>. If it lists any "missing" entry, show the user that whole list as exactly what
     --fix would create: --fix creates every missing requirement in the doctor's REQUIREMENTS, not only the
     registries (for example .claude/north-stars, .claude/orchestrator/results, the contract template,
     .claude/area-mapping.json and .claude/work-item-conventions.json); it never overwrites and leaves
     .claude/settings.json alone. Run $PY "<dir of FI>/plugin_doctor.py" --fix only after the user says
     yes; never run it on its own. Add one Closing bullet (which history-record files exist and which the
     doctor created, if the user agreed) and one Anti-patterns bullet (treating the Central Memory System
     as the project's record, skipping the registries, or running --fix without asking).
  2. skills/design-first/SKILL.md Step 1.5: add one lead sentence. The project's design history is its
     Project history record (the registries, including INTEGRATION.md where present, the concept contracts
     and the briefs). Step 2 and the architect read it in every memory state, including disabled. The
     Central Memory System only supplements it: its items never replace, hide or skip a registry read. In
     point 1, add after the existing sentences that the Project history record is read as always. Nothing
     is printed or written on disabled. Every line Step 1.5 prints in any other state ends with the fixed
     suffix "; design continues from the project history record (registries and concept contracts)": the
     point 2 failure line, the point 3 status line and its skipped-for-want-of-a-brief line (block 14's
     text), and the point 4 skipped-for-want-of-a-brief line. The skill text appends the suffix when it
     prints; memory_boundary.py is not changed.
  3. references/central-memory.md, Ground rules: add the same rule. Each one-line "unavailable" print ends
     with the same suffix.
  4. test_memory_off_parity.py: add a ProjectHistoryRecordTextTests class. It pins that the finish-install
     section names the three seeded registries, INTEGRATION.md, .claude/concepts/ and .claude/work-items/,
     says the Central Memory System only supplements them, runs plugin_doctor.py in report mode, and asks
     before --fix (a "--fix" mention is preceded within the section by a confirmation sentence); that it
     does not contain "on every run" next to "append". It pins the Step 1.5 lead sentence, the suffix on
     points 2, 3 and 4, and the central-memory.md ground rule. It pins that Step 1.5 point 1 still prints
     nothing and writes nothing on disabled.
  5. .claude/agreements/use-the-project-history-record.md (new shipped agreement, user answer "Yes, add a
     session-start agreement"): first line "# Use the Project History Record", then three or four short
     sentences, under about 400 characters in all. It says: the registries (.claude/registries/) and the
     concept contracts (.claude/concepts/) are the project's memory and its design history; read them and
     use them; a central MCP memory system, when one is switched on, only supplements them and never
     replaces them. It names no project, person, machine path, incident date, MCP server or memory tool.
  6. .claude/hooks/tests/test_working_agreements.py: add the file to REQUIRED and add a SHIPPED_PHRASES
     row for it (for example "project's memory", "only supplements", "concept contracts"). Rename
     case_real_shipped_folder_is_exactly_the_six_required_files and
     case_s3_the_phrase_table_covers_exactly_the_six_required_files (and their add() labels and messages)
     to say seven, so each test is named after what it asserts.
CONTEXT: concept contract (Revision 7: Business Concept "Project history record", Extension Points
  (Step 1.5, /auto-improve-finish-install, Shipped agreements), Reused Mechanisms row "Telling a host
  project...", Alternatives Considered Options I-K, Failure Modes (Revision 7 entries), Open Questions 22
  and 23 as answered); MECHANISMS.md "Session-start context delivery".
FILES: the six listed.
CONSTRAINTS:
  - Text and tests only. Do not touch auto_improve_finish_install.py, plugin_doctor.py, the doctor's
    REQUIREMENTS, memory_boundary.py, working-agreements.py, working-agreements.rules.json, any settings
    file, any hook code, agents/data-architect.md (its rule 9 already ranks items below the registries)
    or any registry. Add no seed or template for INTEGRATION.md (Open Question 22). No new store, seed,
    hook or frontmatter key. Do not bump the plugin version.
  - The shipped agreement set must still fit the default limit with nothing dropped
    (case_real_shipped_set_fits_default_limit_with_nothing_dropped, 9000 characters), plain-language must
    stay first (INV-6), and the new file must pass every real-file case in test_working_agreements.py.
    test_plugin_text_scans.py scans .claude/agreements/, so the agreement names no memory tool.
  - test_plugin_manifests.py INV-14: every --flag the finish-install text names must exist in
    auto_improve_finish_install's parser unless the line names plugin_doctor, so keep each doctor command
    on a line that names plugin_doctor.py. INV-13: frontmatter name and user_invocable unchanged, and the
    description stays non-empty.
  - Keep passing, without editing them: test_plugin_manifests.py, test_skill_script_lookup.py (the lookup
    blocks in finish-install and design-first are unchanged), test_parent_branch_rule_text.py,
    test_repo_consistency.py, test_plugin_text_scans.py (no memory tool name in any text),
    test_auto_improve_finish_install.py and test_plugin_doctor.py. Also keep Step15TextTests passing
    (the disabled regex "disabled.{0,300}print(s)? nothing.{0,200}writ(e|es) nothing", so the new
    sentence goes after it). If one of these pins must change, stop and report it; do not edit the file.
  - Run the suites named above plus test_memory_off_parity.py and
    py -3 .claude/hooks/tests/test_working_agreements.py, and quote the results.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md
  contract_status: approved
```

## Out of scope
- Everything outside this sub-task's handoff block; see the other sub-tasks of the contract.

## Known context
- Parent / epic: #161 (https://github.com/lneninger/claude-agentic-auto-improve/issues/161)
- Related items: the other sub-tasks of `.claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md`
- Affected areas: the files named in the handoff block

## North-star alignment
- inherited from .claude/work-items/2026-11-01-memory-client-and-cloud-engineering.md

## Open questions from intake
- none; the sub-task's criteria were approved at the contract gate.

## Size
Task of .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md.

## Routing
task of .claude/concepts/2026-11-01-memory-client-and-cloud-engineering.md - dispatched by /advance
