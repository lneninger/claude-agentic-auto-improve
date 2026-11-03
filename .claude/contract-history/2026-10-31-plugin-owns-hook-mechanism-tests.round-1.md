## Critique

**Critic:** contract-critic
**Date:** 2026-10-31
**Verdict:** blockers-found

### Findings

- **[BLOCKER] Apply registration profile can never succeed: the planned bytes carry `recorded_at = now`.**
  - **What is wrong:** `build_profile(settings, previous_profile|None, now)` puts a date-time in the planned bytes, and the plan hash covers the planned bytes. A preview and a later apply produce different bytes, so every apply refuses `changed-since-preview`. "Write nothing when the planned bytes equal the existing bytes" also never fires, so every re-record changes the file.
  - **Prior artifact ignored:** `MECHANISMS.md` line 64, Preview-hash apply ("The apply recomputes the plan from the same flags and refuses `changed-since-preview` on any difference … it writes nothing when there is nothing to add").
  - **Where in this contract:** `## Data Shapes → Entities` — "`recorded_at` (date-time)"; `## Extension Points` — "`build_profile(settings, previous_profile|None, now)`"; `## Commands` — "plan hash over: settings bytes, existing profile bytes (or `absent`), planned bytes"; block 2 — "Write nothing when the planned bytes equal the existing bytes".
- **[BLOCKER] Failure attribution produces nothing for `exit-code` steps, which are every step in this repository, the new one included.**
  - **What is wrong:** `read_step` sets `reading = "regression"` and leaves `new_failures` empty for `exit-code` steps (`.claude/scripts/land_contract.py:857-862`), and V2 names them `step <id>` (`:2968`). The contract defines attribution as "one entry per new failure" keyed by `suite::unit::name`, and writes the note "only when every new failure is `undetermined`". So a failing exit-code step gets no entry, and the note's condition is vacuously true or false, unspecified. All three existing steps in `.claude/work-item-conventions.json:93-111`, and the new `hook-registration-tests` step, are `exit-code`. The brief's criterion "separates … or states in the report why it cannot" is therefore unmet for this plugin's own landings.
  - **Prior artifact ignored:** Work Item Brief `.claude/work-items/2026-10-31-148-plugin-owns-hook-mechanism-tests.md` line 33 (acceptance criterion 4); `land_contract.py:857-862`.
  - **Where in this contract:** `## Data Shapes → Value Objects` — "Failure attribution | `test` (the failure id `suite::unit::name`)"; Failure attribution rules A-1 — "`trx` and `exit-code` name none"; "The note is written only when every new failure is `undetermined`".
- **[WARN] The checker's import chain is not delivered by the README's vendoring instruction, and an import failure falls outside the closed refusal set.**
  - **What is wrong:** the checker imports `auto_improve_finish_install` at module level, which imports `pr_merged` and `plugin_doctor` (`auto_improve_finish_install.py:85-86`). Block 4 tells a project to "add the checker path to its scripts tree in .sync-config.json", and names only the checker. A vendored project that follows it gets a traceback, which exits 1 ("a rule failed") and not 2 ("could not check"). Scripts are not Plugin-delivered assets.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "Detect an install mode by what the sync actually delivers"; `VOCABULARY.md` line 87, **Plugin-delivered asset** (agents and skills only).
  - **Where in this contract:** `## Uncertain Assumptions` — "consuming projects receive `.claude/scripts/*` as vendored assets once their sync config lists the new file"; block 4 — "add the checker path to its scripts tree"; the refusal table, "closed set".
- **[WARN] Malformed parts below the top-level `hooks` object are dropped silently both when recording and when checking.**
  - **What is wrong:** `settings-unreadable` covers only a non-object `hooks`. An event value that is not a list, a group that is not an object, or a handler that is not an object is skipped by `_iter_hooks` (`auto_improve_finish_install.py:1080-1091`). A profile recorded from such a file then checks clean for as long as the defect stays. Calling this VERIFIED because "the checker validates the `hooks` shape" overstates what the refusal table actually checks.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case"; `MECHANISMS.md` line 56, Guard rules file (a blocking check fails closed).
  - **Where in this contract:** `## Uncertain Assumptions` — "`_iter_hooks` skips malformed parts silently, so the checker validates the `hooks` shape before calling it"; refusal row `settings-unreadable`.
- **[WARN] "Profiled" and `test_profile_setup` may refer to the hook timing profiler, and Q2 does not put that reading to the user.**
  - **What is wrong:** the brief describes the mechanism as "hook gating, hook registration rows, setup profiling" and lists `auto_improve_finish_install.py (setup profiling)`. This repository cites a hook "profiler report of 2026-10-05". Even so, the contract maps `test_profile_setup` to "a recorded profile round-trips" and declares timing a Non-Goal. Q2 asks only whether the four rules cover the tests, and recommends "accept it as written". The definitional choice is buried in an ASSUMED line.
  - **Prior artifact ignored:** Work Item Brief lines 27 and 45; `.claude/hooks/tests/test_gate_cost.py:18-19`.
  - **Where in this contract:** `## Uncertain Assumptions` (first entry); `## Open Questions for User` Q2; `## Non-Goals` — "Measuring hook run time".
- **[WARN] "profile" becomes a third overloaded noun inside one script.**
  - **What is wrong:** `auto_improve_finish_install.py` already has a `profile` subcommand that writes the Project profile (`:3066`), and refusals there say "the profile path is not a file" (`:441`). The new `registration-profile` subcommand, the term **Registration profile** and the brief's "setup profiling" make "profile" ambiguous in operator output and in refusal messages.
  - **Prior artifact ignored:** `MECHANISMS.md` line 62, **Project profile**.
  - **Where in this contract:** `## Business Concept → New terms` — "**Registration profile** — `.claude/hook-registration-profile.json`"; Q4.
- **[WARN] Rule labels `A-n` and `P-n` collide with the registered Rule ID series.**
  - **What is wrong:** **Rule ID** reserves `A-nnn` for Angular rules and `P-nnn` for plugin-owned patterns, cited by guard messages and tests. Blocks 3 and 5 put "A-1..A-5" and "P-1..P-5" into test names and review checks.
  - **Prior artifact ignored:** `VOCABULARY.md` line 82, **Rule ID**.
  - **Where in this contract:** `## Data Shapes` — "P-1 … P-5", "A-1 … A-5"; block 3 — "one test per rule A-1..A-5".
- **[WARN] Missing invariants for a hand-edited profile.**
  - **What is wrong:** P-4 keeps excluded rows out of `registrations` on a re-record only. P-5 does not make a hand-written overlap between `registrations` and `excluded` unreadable, does not require Exclusions to be unique, and says nothing about a stale Exclusion that matches no row. An Exclusion has no occurrence number, so excluding one of two duplicate rows excludes both, which is undeclared.
  - **Prior artifact ignored:** `MECHANISMS.md` line 56, Guard rules file (fail closed on an input the blocking check cannot trust).
  - **Where in this contract:** `## Data Shapes → Entities` — P-4 and P-5; `## Value Objects` — "Exclusion | event; identity text; matcher (optional, meaning any matcher)".
- **[NIT] A-1 matches a `unittest-text` test file by base name across the whole diff.** Same-named test files in `.claude/hooks/tests/` and `.claude/scripts/tests/` can mis-attribute a failure. It is advisory, but the reason line would then be confidently wrong.
- **[NIT] The `Adjacent Areas` line does not match the template's exception text exactly, because extra sentences follow it.** The scan's outcome is still honest: `.claude/area-mapping.json:14` has `"areas": {}`.

### Applicable journal entries

- **2026-10-16 — "Missing project file" refusal covers unset root and set-but-absent file:** heeded by `paths-not-given` / `settings-missing` / `profile-missing`.
- **2026-10-15 — A script that reads a project-owned file must be told which project:** heeded by the explicit `--project` / `--settings --profile` paths.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case:** partly heeded (no `hooks` key, non-object `hooks`); see the second WARN.
- **2026-10-04 — Detect an install mode by what the sync actually delivers:** violated in substance; see the first WARN. It is graded WARN because the contract hoists the dependency as ASSUMED.
- **2026-10-04 — Check a documented guard behaviour against the guard's code:** heeded by the fail-closed refusals, with exit 2 never a pass.
- **2026-10-05 — A documented "missing file means the default" must read one named location only:** heeded, because the checker reads the project layer only.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam:** heeded, because the recorder extends Preview-hash apply.
- **2026-10-28 — A new term's definition must be true against every existing member:** heeded by the `command:` identity for rows with no `.py` file.
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out:** heeded, because attribution adds no refusal and the remedy names the record command.
- **2026-10-30 — Widening a CI trigger changes who the check judges:** not addressed. No CI trigger changes. The new landing step has no `when_paths`, and its first landing is named.
- **2026-10-30 — A delivery rule must name every route into delivery:** not addressed. Delivery rules are consumed, not changed.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval:** pending, at approval.

### Parent Branch Delivery Rule and helper reuse (requested checks)

- The `**Work Item Brief:**` header is present (line 8). There are five numbered blocks. No block's Files to touch lists a `MANIFESTS` file (`check_version_bump.py:25-26`), and P7b raises the version at landing. No layout defect was found by reading.
- `_iter_hooks` (`auto_improve_finish_install.py:1080`), `_hook_key` (`:1030`) and `_compare_extras` (`:1041`) exist under those names. `_hook_key` returns the raw arguments, so the checker must apply `_compare_extras` itself to match the Registration key (`_Registration.key`, `:1075-1077`). `REFUSAL_CODES`, `EXIT_CLASS`, `malformed-settings`, `unexpected-settings-shape`, `project-unreadable` and `changed-since-preview` exist. `_p8_verify`, `read_step`, `applicable_steps` and `next_command_for_outcome` exist at the cited seams.
- Acceptance criteria: 1, 2, 3, 5 and 6 are covered by blocks 1, 2, 4 and 5. Criterion 4 is not covered for `exit-code` steps (second BLOCKER).

### What the critic did not check

- `pr_merged.py --contract <slug> --status --json` was not run, because the critic has no shell. The delivery layout was checked by reading only.
- `.claude/registries/INTEGRATION.md` and `.claude/.scout-cache/registry-digest.md` do not exist in this worktree. No project tier exists in MECHANISMS, VOCABULARY or JOURNAL, so only Universal-tier checks were applied.
- `.claude/north-stars/` is absent, so checklist item 13 produced no findings.
- This `## Critique` section fills the template's in-body placeholder heading instead of adding a second heading at the end of the file.

---
