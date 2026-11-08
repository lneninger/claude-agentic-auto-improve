# Superseded critique round 1 — 2026-11-07-295-codegraph-gate-dropped-mcp

Moved out of `.claude/concepts/2026-11-07-295-codegraph-gate-dropped-mcp.md` on 2026-11-07 by the main session, per the budget rule in `.claude/templates/concept-contract.md`. The data-architect amended the contract body in response to these findings.

## Critique

**Critic:** contract-critic
**Date:** 2026-11-07
**Verdict:** blockers-found

> Round 1. Superseded; the main session moves it to `.claude/contract-history/2026-11-07-295-codegraph-gate-dropped-mcp.round-1.md` (the data-architect may not write there).

### Findings

- **[BLOCKER] Criterion 6 cannot be met through `/verify-before-done` in a project that vendors the installer**
  - **What is wrong:** Step 5.8's lookup takes the project's own `.claude/scripts/auto_improve_finish_install.py` before the plugin's copy (`skills/verify-before-done/SKILL.md:232-237`). The contract keeps that block unedited, so a project with a stale vendored installer runs the old `check_addon`. That code has no Hook freshness findings. This is the same stale-copy population the criterion exists for.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 — "A root locator can return the consumer itself under vendoring". `MECHANISMS.md:102` (a vendored copy of `auto_improve_finish_install.py` is a supported layout).
  - **Where in this contract:** `## Reused Mechanisms` — "reused as-is by `/verify-before-done` Step 5.8. The lookup block is not edited"
  - → Addressed by: Step 5.8 moves to the plugin-only lookup `FIP` (test gains `PLUGIN_ONLY_VARS`), and a result without `freshness` reads "could not check" (Reused Mechanisms, Extension Points, Q9).
- **[BLOCKER] `addon-row-missing` does not name its reader or the row forms it must recognise**
  - **What is wrong:** Add-on rows are written as Project hook launcher rows (`py -3 -c <launcher source> <class> <script>`, installer `:59, :1385-1401`). Older installs carry exec-form rows, and hand-written rows exist too. The new Bash row also carries `if`. The contract says only "a manifest row that no settings layer has", so a working launcher row can be reported missing.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-01 — "A shared reader reused by a stricter consumer must be re-checked against the forms its errors were harmless for". `JOURNAL.md` 2026-11-01 — "After merging a base that changes the row shape a feature reads, re-check every coverage claim and round-trip test against the merged writer".
  - **Where in this contract:** `## Data Shapes → Value Objects → Hook freshness finding` — "`addon-row-missing` (`{event, matcher, hook}` of a manifest row that no settings layer has)"
  - → Addressed by: the Row-missing reader value object (`_existing_registrations` / `_hook_key`, the install's own `to-add` key) with per-form rows; reading it also showed the key ignores matcher, so the new row gets `args: ["cli"]`.
- **[BLOCKER] The Connection notice gives the model an instruction and does not say which rule wins**
  - **What is wrong:** `additionalContext` tells the model to run `codegraph explore` in Bash. It does not say that a project instruction or a skill's explicit gate wins (for example the strict shell gate add-on, or a skill that forbids shell commands). The lesson is not listed under Lessons referenced.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-05 — "Text delivered to the model must say which rule wins against a skill's gate".
  - **Where in this contract:** `## Data Shapes → Value Objects → Connection notice (output)` — "meanwhile `codegraph explore "<term>"` in Bash opens the gate for the turn"
  - → Addressed by: the notice ends with a fixed, exact precedence sentence, asserted by a notice row; the lesson is listed.
- **[WARN] The "existing hook's time budget" in criterion 4 has no pass or fail check**
  - **What is wrong:** No time budget for the reset hook exists. The 100 ms figure is new and is checked only between steps, but a guard import by `importlib`, a Toolhelp32 snapshot and `ps` are single steps that cannot be interrupted. The bench only "reports p50 / p95" and asserts nothing.
  - **Prior artifact ignored:** the brief's criterion 4 ("stays inside the existing hook's time budget"). `bench_codegraph_guard.py:383-403` (the only existing reset cost figure, `old_reset_p50`).
  - **Where in this contract:** `## Data Shapes → Value Objects → Notice time budget` — "`bench_codegraph_guard.py` reports the reset hook's p50 / p95 with the notice"
  - → Addressed by: Notice time budget now names the single steps and two failing bench thresholds (Revision 2: against a pinned `db61fd7` baseline in a `--reset-budget` mode).
- **[WARN] An accepted false notice contradicts criterion 4, and the decision sits in Failure Modes**
  - **What is wrong:** Criterion 4 says "silent on a healthy session". The contract accepts a false notice on a slow first prompt without asking the user.
  - **Prior artifact ignored:** the brief's criterion 4.
  - **Where in this contract:** `## Failure Modes & Mitigations` — "A slow server start on the first prompt may give one false notice, which is accepted"
  - → Addressed by: moved to the user as Q11 with a recommendation.
- **[WARN] The probe's present / absent rule is tested only against a stub**
  - **What is wrong:** The seam replaces the whole probe, so the Host walk, the skip list, the depth limit, the `serve` + `--mcp` + `codegraph` token match and the rule that an unreadable command line gives `undecidable` have no unit row. Only the one-off live trial L4 exercises them.
  - **Prior artifact ignored:** the brief's criterion 4 ("appears when no `codegraph serve --mcp` process exists … absent when one does").
  - **Where in this contract:** `## Decision invariants` R-4 — "a module-level probe function a test replaces"
  - → Addressed by: the probe's rules are a pure function over a process table; the seam replaces only the table reader; probe rule rows in the TASK block.
- **[WARN] The `cli-fallback` record misses a drop in the middle of a session and counts failed MCP calls as successes**
  - **What is wrong:** `mcp-used` stays set for the whole session. When the connection drops after any earlier MCP call in the same session, which is the brief's main scenario, the record is never written. The flag is also set on any MCP PostToolUse, and the tracker fires on errored calls too (`codegraph-turn-tracker.py:6`, "even with an error"). Criterion 5 says "succeeded".
  - **Prior artifact ignored:** the brief's Problem statement and criterion 5.
  - **Where in this contract:** `## Data Shapes → Entities → MCP-seen flag` — "Created by the tracker after any `mcp__codegraph__*` PostToolUse … sticky for the session"
  - → Addressed by: Revision 2: `mcp-seen` is set only by a successful MCP call (L7), per criterion 5. The mid-session drop is a documented known limitation with a follow-up stub (main session decision, 2026-11-07).
- **[WARN] The subagent row for criterion 2 passes whether or not the command-line call worked**
  - **What is wrong:** Guard step 3 already allows every subagent read without a marker (`codegraph-first-guard.py:932-935`, `fail-open:subagent`). The row proves nothing unless it asserts the reason `turn-marker-present`.
  - **Prior artifact ignored:** `VOCABULARY.md:125` (CodeGraph unavailability reason `subagent`).
  - **Where in this contract:** `## Implementation Handoff` TASK — "one counted CLI call then a source Read -> allowed, in the main session and with agent_id"
  - → Addressed by: the AC2 rows assert reason `turn-marker-present`.
- **[WARN] R-1 says the guard reads only whether `turn.json` exists, but Q5 has the guard read a field from it**
  - **What is wrong:** The Turn marker row says it is "read for presence only by the guard", yet the Shadow extension reads `marker_route` from the marker's JSON.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 — "Edit a reversed sentence where it stands". `MECHANISMS.md:106`.
  - **Where in this contract:** `## Data Shapes → Entities → Turn marker (amended)` against `## Extension Points → Shadow (Q5)` — "read inside the shadow section's budget"
  - → Addressed by: the Turn marker row and R-1 now say the decision reads presence only and the Shadow section alone reads `route`.
- **[WARN] A `codegraph` call made with the PowerShell tool never counts, and the contract does not say this is out of scope**
  - **What is wrong:** The new row matches `Bash` only, and the Counted command test parses POSIX shell syntax. The plugin registers its own shell rows on `Bash|PowerShell`, and Non-Goals is silent on PowerShell.
  - **Prior artifact ignored:** `.claude/hooks/hooks.json:37, :104`. `VOCABULARY.md:65` (Gate launcher correction).
  - **Where in this contract:** `## Data Shapes → Entities → Add-on manifest (amended)` — "`{event: PostToolUse, matcher: Bash, …}`"
  - → Addressed by: a Non-Goal; the banner and the notice name the Bash tool; Q10.
- **[WARN] Projects that keep a Hook registration profile will fail `row-count-unchanged` after the upgrade**
  - **What is wrong:** The fourth row changes the row count. No failure mode or document says the project must re-record its profile.
  - **Prior artifact ignored:** `MECHANISMS.md:102` (Hook registration check). `VOCABULARY.md:104`.
  - **Where in this contract:** `## Failure Modes & Mitigations` — no entry. `## Reused Mechanisms` — "Hook registration check (`:102`): consumed"
  - → Addressed by: an FM, and the install skill and README tell the project to re-run `record-registrations`.
- **[WARN] The Hook freshness check may cover every add-on, and its relation to `--drift` is not stated**
  - **What is wrong:** `check_addon` takes any add-on name. `strict-shell-gate/addon.json` has no `released_sha256`, so an unedited older `bash-gate.py` would read `addon-hook-differs` / `edited`. Which add-ons must satisfy the label invariant is not stated. `addon-hook-differs` and `addon-hook-missing` also duplicate the `content-differs` / `one-sided` findings that `--drift` already gives for the same files, under different codes.
  - **Prior artifact ignored:** `MECHANISMS.md:108` (`released_sha256` is optional). `MECHANISMS.md:49`. `VOCABULARY.md:36-37`.
  - **Where in this contract:** `## Data Shapes → Value Objects → Hook freshness finding`. `## Reused Mechanisms` — "Considered, not extended"
  - → Addressed by: freshness applies only to manifests with `released_sha256` (`freshness: not-applicable` otherwise); Revision 2 replaces `addon-hook-differs` with the note `addon-hook-unrecognised`; the overlap with `--drift` is stated.
- **[WARN] The reset hook has no source for the `<term>` in the notice**
  - **What is wrong:** The reset hook has no tool input. If `<term>` comes from the prompt, it is untrusted text echoed to both the user and the model.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-05 — "Neutralise every field echoed from untrusted input, not only the body".
  - **Where in this contract:** `## Data Shapes → Value Objects → Connection notice (output)` — "`codegraph explore "<term>"`"
  - → Addressed by: the notice text is fixed (`codegraph explore "SymbolName"`); nothing is echoed; a row asserts no prompt text appears.
- **[WARN] Criteria 3, 7 and 8 have no named test**
  - **What is wrong:** No needle row checks the banner's two routes, the copyable command, the worktree sentence or the neutralisation probe. K-4 (`test_codegraph_first_guard.py:283-296`) covers the guard and `CLAUDE_SKIP_CG` only, not the new tracker or reset code. No check pins "three hook files, one tracker".
  - **Prior artifact ignored:** the brief's criteria 3, 7 and 8. `JOURNAL.md` 2026-10-05 — "Neutralise every field…" ("probe each with the payload").
  - **Where in this contract:** `## Implementation Handoff` TASK CONSTRAINTS
  - → Addressed by: AC3, AC7 and AC8 rows in the TASK block.
- **[NIT] Two `## Critique` headings** — the architect left an empty `## Critique` heading at line 206, so the file now has two of them.
  - → Addressed by: the empty heading is removed.
- **[NIT] Extra text in Adjacent Areas** — the section adds prose after the sanctioned single line. `derive_area.py` was not run; `area-mapping.json:14` has no areas, so the scan should return no signal.
  - → Addressed by: the section is the single sanctioned line.
- **[NIT] `_mcp_server_state` is the installer's name** — the guard's mirror is `_server_state_at` / `server_verdict` (`codegraph-first-guard.py:600-678`). The contract does not say whether `server_starts_process` joins the P-1 parity test (`test_codegraph_first_guard.py:787`).
  - → Addressed by: names corrected; R-3 says `server_starts_process` has no installer mirror and gets its own rows, not P-1.
- **[NIT] R-3 says the notice "writes no file"** — loading the guard by path with `importlib` writes `__pycache__/codegraph-first-guard.*.pyc` into the project's hooks folder unless bytecode writing is off.
  - → Addressed by: R-3 sets `sys.dont_write_bytecode`; a row asserts no `__pycache__`.
- **[NIT] "Host process" is defined by a universal claim** — "This is the Claude Code process" is false on any host that starts hooks through a wrapper that is not on the skip list. The word "host" already has a general meaning in the registries (`JOURNAL.md` 2026-10-28, "A new term's definition must be true against every existing member"; `JOURNAL.md` 2026-11-02, "Search a proposed term…").
  - → Addressed by: renamed Hook host process; trusted only for a known-host image, else `undecidable`.
- **[NIT] Windows full paths never count** — `shlex.split(posix=True)` drops the backslashes in `C:\…\codegraph.cmd explore x`, so such a call is not counted. This errs the safe way but is not stated (`JOURNAL.md` 2026-11-01, shlex forms).
  - → Addressed by: stated in the Counted command test and Non-Goals, with a row.
- **[NIT] The F-questions leave the test reading to the implementer** — F5 loosens every "empty reset output" assertion before anyone has read them. This only partly heeds `JOURNAL.md` 2026-11-02, "Name the tests a fix may change by the state they guard, after reading them". `test_plugin_doctor.py:918-920, :1399` names the codegraph hooks but is missing from F1.
  - → Addressed by: F5 now changes only rows whose fixture meets every Notice precondition; `test_plugin_doctor.py` joins F1 and Files to touch; F8 added.
- **[NIT] `summary` is undefined for a `cli` marker** — the Turn marker row says what `tool` holds for the `cli` route, but not what `summary` holds.
  - → Addressed by: the Turn marker row defines `summary` for `cli`.

### Applicable journal entries

- **2026-10-04 — A root locator can return the consumer itself under vendoring** — violated, see BLOCKER above.
- **2026-11-01 — A shared reader reused by a stricter consumer…** and **2026-11-01 — After merging a base that changes the row shape…** — violated, see BLOCKER above.
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate** — violated, see BLOCKER above.
- **2026-10-05 — Neutralise every field echoed from untrusted input** — heeded for the banner's Copyable command; not addressed for the notice's `<term>` (WARN).
- **2026-10-04 — Do not rely on a host expanding a variable…** and **2026-10-05 — Count a host's size cap… prove with a real trial** — heeded by L1-L6 and the STOP rules.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded. The cited lines (`addon.json:12-30`, tracker `:134-142`, reset `:258-271`, guard `:1056-1104`, `check_hook_registrations.py:237, 277`, `plugin_doctor.py:272-278`) match the files.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded by F1-F7, with the gap noted in the NIT.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded. Leaving the block untouched is what causes the first BLOCKER.
- **2026-10-22 — Describe a broken install by the rows each install age really has** — heeded by `addon-row-missing` and the 0.16.1 row.
- **2026-10-28 — State the real trigger of a hook** — heeded by the `hooks.json` cost text.
- **2026-10-28 — Guard messages must use names the guard emits** — heeded by R-2.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded.
- **2026-11-02 — A revision that adds a path adds its failure modes** — heeded in part: there is no failure mode for PowerShell or for the registration profile.
- **2026-11-05 — An "older release" test fixture must be pinned to a fixed commit** — heeded by `db61fd7`.

### What the critic did not check

- `pr_merged.py --contract <slug> --status --json`, `derive_area.py` and `cross_area_scan.py` were not run, because this agent has no shell. The handoff has one mergeable block, so checklist item 14 has nothing to trigger.
- `.claude/registries/INTEGRATION.md` does not exist in this repository, and there are no per-domain registry files. The Universal tier only was read.
- Live trials L1-L6 and the evidence outside this worktree (`StockToolScalpingMachine/.mcp.json`, the daemon file) were not checked.
- The 12,000-token budget was not measured.

---
