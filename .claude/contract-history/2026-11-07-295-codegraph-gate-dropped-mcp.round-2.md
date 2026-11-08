# Superseded critique round 2 — 2026-11-07-295-codegraph-gate-dropped-mcp

Moved out of `.claude/concepts/2026-11-07-295-codegraph-gate-dropped-mcp.md` on 2026-11-07 by the main session, per the budget rule in `.claude/templates/concept-contract.md`. The data-architect amended the contract body in response to these findings.

## Critique (second pass)

**Critic:** contract-critic
**Date:** 2026-11-07
**Verdict:** blockers-found

### Earlier BLOCKERs, checked against the code

- **Step 5.8 stale installer:** fixed for the check. Step 5.8 moves to the plugin-only form (`skills/verify-before-done/SKILL.md:363-379` is the model). It is not fixed for the repair route the finding names; see the new BLOCKER 2.
- **Row-missing reader:** fixed. `_existing_registrations` (`auto_improve_finish_install.py:1171-1188`) and the `to-add` key at `:1742` are `(event, file, compare_extras)`, and the key ignores the matcher. The `cli` argument does give the row its own key: `_written_hook` writes the extras into the launcher row (`:1399-1401`), and `project_hook_launcher_parts` reads them back (`.claude/hooks/_project_paths.py:1086`). `if` reaches the written row through `other_keys` (`:1403`, `:2756`) once it is in `ADDON_ROW_KEYS` (`:237`).
- **Precedence sentence:** fixed. The notice ends with the fixed sentence, and a row asserts it.

### Findings

- **[BLOCKER] The bench's pass/fail rule cannot run, and its baseline moves**
  - **What is wrong:** By default the TASK block runs `bench_codegraph_guard.py` with `--old-ref origin/master` (`bench_codegraph_guard.py:466`). `_check_old_is_259` exits when the old guard already holds `shadow_section` (`:171-174`), and master's guard does (`codegraph-first-guard.py:1436`). So the run stops before it measures anything, and "all must pass" cannot hold. With an older ref passed by hand, `old_reset_p50` is the #259 reset hook, not this branch's base. Once this change merges, `origin/master` is the new reset hook, so it would be compared with itself. The time-budget part of criterion 4 therefore has no check that can run.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-05 — "An 'older release' test fixture must be pinned to a fixed commit or a frozen copy, never to HEAD". The contract applies it to the `released_sha256` fixtures (`db61fd7`) but not to the bench baseline.
  - **Where in this contract:** `## Data Shapes → Value Objects → Notice time budget` — "fails when the reset hook's subprocess p50 with the notice exceeds `old_reset_p50` + 150 ms"
  - → Addressed by: a new `--reset-budget` bench mode that never builds the #259 `Workspace` (no `_check_old_is_259`), baselines on the constant `RESET_BASELINE_REF = "db61fd7"` via `git show`, and exits 1 on a T1/T2 breach or a missing commit; the TASK block runs that mode.
- **[BLOCKER] The repair the freshness finding names runs the stale vendored installer it was meant to avoid**
  - **What is wrong:** The finding says to re-run `/auto-improve-codegraph-install`. That skill still finds the installer project-first (`skills/auto-improve-codegraph-install/SKILL.md:34-37`), and the contract keeps that order. Two things follow:
    - A vendored 0.16.1 installer drops the new `if` key, because its `ADDON_ROW_KEYS` filter (`:2756`) does not know `if`. The row then starts the tracker after every Bash call.
    - An installer older than #259 has no `update` action for released copies, so it refuses with `addon-file-differs`.

    The plugin's own `--check` cannot see a row that lacks `if`, because `if` is not part of the key (Row-missing reader). The project the incident came from (a vendored guard older than #259) is exactly this case.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 — "A root locator can return the consumer itself under vendoring". `MECHANISMS.md:108` (the `update` action for released copies dates from #259).
  - **Where in this contract:** `## Data Shapes → Value Objects → Hook freshness finding` — "the route: re-run `/auto-improve-codegraph-install`". `## Reused Mechanisms` — "the same script stays project-first in the install skills"
  - → Addressed by: both: Step 0 of the codegraph install and uninstall skills moves to the plugin-only `FIP` lookup (no loss, since `_resolve_addon` already needs a separate plugin root), and the Row reader carries `if` so a registered row lacking it reads `addon-row-outdated` (route: uninstall, then install), with test rows.
- **[WARN] R-5 changes criterion 5's condition, and the user did not decide it**
  - **What is wrong:** Criterion 5 says one record is written when "no MCP call has succeeded this session". R-5 also writes the record after an earlier successful MCP call in the same session (`mcp_earlier: true`). The user's Q4 answer was only "the tracker". The architect added the new condition, and the brief still reads the old way.
  - **Prior artifact ignored:** `.claude/work-items/2026-11-07-295-codegraph-gate-dropped-mcp.md:36`. `JOURNAL.md` 2026-10-22 — "An accepted critic WARN or answered Open Question must amend the contract body before approval" (the brief and the contract now disagree).
  - **Where in this contract:** `## Open Questions for User` Q4 — "(Revision 1: the condition is now 'no successful MCP call this turn', R-5.)"
  - → Addressed by: R-5 follows criterion 5 literally (gate on `mcp-seen`, set by a successful MCP call); `mcp-ok` and `mcp_earlier` are removed; the mid-session drop is a known limitation with a follow-up stub.
- **[WARN] The probe never defines "candidate" or "a token naming `codegraph`"**
  - **What is wrong:** Command lines are read "for candidates only", but no rule says which images are candidates. On Windows the `.mcp.json` entry `command: codegraph` runs through an npm `.cmd` shim, so the server is a `node` process. Its token is a script path whose file name may not be `codegraph`. Under a filter by image name or by file-name token, a healthy npm install reads `absent` and shows a false notice on every prompt.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-28 — "A new term's definition must be true against every existing member" (Session server process).
  - **Where in this contract:** `## Data Shapes → Value Objects → Connection probe` — "the command line read through `NtQueryInformationProcess` class 60 for candidates only"
  - → Addressed by: candidates are every descendant of any image; a CodeGraph token is a `codegraph` basename or a `codegraph` folder segment (npm package path); `serve --mcp` with no such token is `undecidable` (silent); L4 records the real Windows command line, with a STOP rule; npm and ambiguous rows in the TASK block.
- **[WARN] `PLUGIN_ONLY_VARS` is named, but no row is said to read it**
  - **What is wrong:** `plugin_only_snippets()` selects by script name (`test_skill_script_lookup.py:452-453`), and `auto_improve_finish_install.py` is not in `PLUGIN_ONLY_SCRIPTS`. So the "project copy only gives an empty value" row (`:463-477`) never runs for `FIP`. The branch in `test_a_project_copy_of_the_script_is_found_first` (`:399-424`) would fail `FIP` as project-first. No row checks that the `FIP` block exists, as `:434-435` does for `CLN`.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-15 — "A skill that edits a block pinned by a lookup-block test must name that test".
  - **Where in this contract:** `## Reused Mechanisms` — "`test_skill_script_lookup.py` learns plugin-only variables (`PLUGIN_ONLY_VARS = ("FIP",)`)"
  - → Addressed by: the TASK block names the three edits (`plugin_only_snippets()` also selects by variable, the project-copy-first row treats `FIP` as plugin-only, a non-vacuity row per skill).
- **[WARN] Q9 leaves out what "could not check" means for the verdict**
  - **What is wrong:** Step 5.8 already says "Never report READY on it" (`skills/verify-before-done/SKILL.md:256`). So under the recommended answer, a vendored project with the add-on and no plugin install can never reach READY in `/verify-before-done`. Q9 does not say so.
  - **Prior artifact ignored:** `skills/verify-before-done/SKILL.md:256`.
  - **Where in this contract:** `## Open Questions for User` Q9 — "such a project gets 'could not check' for Step 5.8"
  - → Addressed by: Q9 now states it plainly, and that it already holds today (`_resolve_addon`, `:2699-2702`).
- **[WARN] `released_sha256` is widened to versions that were never released**
  - **What is wrong:** The registry defines `released_sha256` as "the folded hashes of its released copies". The contract adds "every committed hook version not yet listed" and requires a "release label" for each one. A hash from a commit between releases has no release to name, and the finding promises "both versions".
  - **Prior artifact ignored:** `MECHANISMS.md:108` (Add-on layout amendment).
  - **Where in this contract:** `## Data Shapes → Entities → Add-on manifest (amended)` — "`released_sha256` gains the folded hashes of every committed hook version not yet listed"
  - → Addressed by: released copies only (the hook at each version-setting commit); an existing hash with no release stops the implementer.
- **[WARN] An unedited copy that is newer than the plugin the lookup chose is reported as `edited`**
  - **What is wrong:** The lookup prefers the recorded install path over a newer cache folder (`test_skill_script_lookup.py:341-352`). A project whose hooks came from a newer plugin than the recorded one has a hash that is not in the older manifest. It reads `addon-hook-differs`, `project-version: edited`, and the verdict is NOT READY.
  - **Prior artifact ignored:** `VOCABULARY.md:88` (Installed plugin root). `JOURNAL.md` 2026-10-28 — "A new term's definition must be true against every existing member" (the codes claim "edited").
  - **Where in this contract:** `## Data Shapes → Value Objects → Hook freshness finding` — "`addon-hook-differs` (an edited or unknown copy; `project-version` is `edited`)"
  - → Addressed by: `addon-hook-differs` is replaced by the note `addon-hook-unrecognised` (edited, or from a newer plugin than the one that ran), which never makes the verdict NOT READY.
- **[WARN] The first critique round was not moved out of the contract**
  - **What is wrong:** The template's budget rule moves every superseded critique round to `.claude/contract-history/<slug>.round-<n>.md` and shrinks each resolved question to one line. The revision keeps round 1 inline, Q1-Q8 keep their options, and the file is likely over its 12,000-token budget. This pass was appended as the caller instructed.
  - **Prior artifact ignored:** `.claude/templates/concept-contract.md:22`. The precedent is `.claude/contract-history/2026-11-05-codegraph-guard-fail-open.round-1.md`.
  - **Where in this contract:** `## Critique` (round 1, kept in place).
  - → Addressed by: Q1-Q8 are one line each and the body is trimmed. The move of round 1 is left to the main session (the precedent file was moved by it, and the data-architect may write only to `concepts/` and `registries/`); round 1 carries a note naming the target path.
- **[NIT] `server_starts_process` reads "the entry `_server_state_at` already selected"**, but `_server_state_at` returns a string, and `server_verdict` judges two paths (`codegraph-first-guard.py:665-677`). The contract does not say which path's entry is read.
  - → Addressed by: Notice preconditions: the first path `server_verdict` judges whose `_server_state_at` is `configured`; the function re-reads that path's entry.
- **[NIT] The Copyable command's term may start with `-`**, because `-` is an allowed character. A pattern such as `-x` is then handed to `codegraph` as an option (`JOURNAL.md` 2026-10-16, "Never let free text start an argument handed to a native program from Git Bash").
  - → Addressed by: leading `-` and `.` are stripped; a `-x` row.
- **[NIT] The Hook host process definition holds an unproven set ("expected `claude`, `node`")** while L4 is pending. The proposed vocabulary text must change once L4 lands.
  - → Addressed by: the term now says "the known-host set recorded from live trial L4", with no names.
- **[NIT] `## New Mechanisms` defers a decision ("Decide at review whether to promote it")** that is not under Open Questions.
  - → Addressed by: promotion is not proposed; no deferred decision.
- **[NIT] The `db61fd7` rows "skip with a printed reason when absent"**, so in a shallow clone the criterion 6 rows pass without checking anything. No CI workflow runs the bench either (`JOURNAL.md` 2026-11-02, "A 'fails the build' claim must name the workflow that runs the check").
  - → Addressed by: the rows and the bench fail when the commit is absent; Extension Points states that no workflow runs them (only `version-bump.yml` exists) and names the gate.
- **[NIT] The Turn marker row does not say whether a `cli` call rewrites an existing `mcp` marker, or the other way round.** That choice decides `marker_route` in the Shadow record.
  - → Addressed by: `route` is `mcp` once any MCP call of the turn wrote it; rows for both orders.
- **[NIT] No row covers the `/verify-before-done` half of criterion 6.** Only the lookup test touches Step 5.8. Nothing asserts that the step names `addon-hook-outdated`, `addon-row-missing` or the `freshness` rule.
  - → Addressed by: a text-scan row on Step 5.8 for the four codes, the note and the `freshness` rule.
- **[NIT] The brief still has `contract: UNKNOWN`** (`.claude/work-items/2026-11-07-295-codegraph-gate-dropped-mcp.md:15`).
  - → Addressed by: not editable by the data-architect; the main session sets it to this contract's path.

### Acceptance criteria against named rows

- **1 (counted command, exit decides):** covered by the Counted command rows in the TASK block.
- **2 (main session and subagent):** covered by the AC2 rows, which assert `turn-marker-present`.
- **3 (banner):** covered by the AC3 needle rows.
- **4 (notice):**
  - Covered: present or absent (probe rule rows), silent on a healthy session, and exception rows (`SystemExit` / `RuntimeError`).
  - Not covered: the time budget. Its bench cannot run (BLOCKER 1).
- **5 (`cli-fallback`):** R-5 rows exist, but they test a condition that differs from the criterion (WARN).
- **6 (freshness):** `check_addon` rows are covered. No row covers `/verify-before-done` (NIT).
- **7 (no kill switch):** covered by the AC7 rows.
- **8 (single owner):** covered by the AC8 rows.

### Applicable journal entries

- **2026-11-05 — An "older release" test fixture must be pinned to a fixed commit** — heeded for the check fixtures; violated by the bench baseline (BLOCKER 1).
- **2026-10-04 — A root locator can return the consumer itself under vendoring** — heeded for Step 5.8; violated by the repair route (BLOCKER 2).
- **2026-11-01 — A shared reader reused by a stricter consumer…** and **2026-11-01 — After merging a base that changes the row shape…** — heeded by the Row-missing reader (checked against the code above).
- **2026-10-05 — Text delivered to the model must say which rule wins** — heeded by the notice's fixed closing sentence.
- **2026-10-05 — Neutralise every field echoed from untrusted input** — heeded by the Copyable command and the fixed notice text.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — named, but the rows that must read the new constant are not (WARN).
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body** — not met for Q4 against the brief (WARN).
- **2026-10-28 — A new term's definition must be true against every existing member** — not met for Session server process and for `edited` (WARNs).
- **2026-10-16 — Never let free text start an argument…** — not addressed (NIT).
- **2026-11-02 — A "fails the build" claim must name the workflow** — not addressed for the bench (NIT).
- **2026-10-28 — State the real trigger of a hook** — heeded. The `hooks.json` add-on cost text exists (`hooks.json:47-56`) and is the right place.

### What the critic did not check

- No shell, so `pr_merged.py --status`, `derive_area.py`, the bench itself and live trials L1-L7 were not run. The bench failure comes from reading its code (`:146`, `:171-174`, `:466`).
- `INTEGRATION.md` and the per-domain registry files do not exist. Only the Universal tier was read.
- The token budget was estimated, not measured.

---
