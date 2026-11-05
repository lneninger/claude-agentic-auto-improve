# Superseded critique round 1 — 2026-11-05-codegraph-guard-fail-open

Moved out of `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` on 2026-11-05 by the main session, per the budget rule in `.claude/templates/concept-contract.md`. The data-architect amended the contract body in response to these findings.

## Critique

**Critic:** contract-critic
**Date:** 2026-11-05
**Verdict:** blockers-found

### Findings

- **[BLOCKER] The guard's largest test suite is not in Files to touch or in the list of tests that will change**
  - **What is wrong:** `.claude/hooks/tests/test_worktree_path_guards.py` runs the codegraph guard in cases C1 to C10, the fallback-mode rows and "task 3". They expect `block` from fixtures that have no `.codegraph/` folder and no `.mcp.json`, and they set the old `<cwd>/.claude/.codegraph-used-this-turn` sentinel (`:1131-1138`). Under decision steps 4 and 5 every one of those cases returns `fail-open:no-index`. Their repeated payloads also hit the retry escape. Planting the sentinel no longer opens the gate.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-17 "Loosening a guard rule must be checked against the guard's own test fixtures"; `JOURNAL.md` 2026-11-02 "Name the tests a fix may change by the state they guard, after reading them"; `MECHANISMS.md:58` Guard fallback mode ("tested per copy in `.claude/hooks/tests/test_worktree_path_guards.py`").
  - **Where in this contract:** `## Reused Mechanisms` says "Guard fallback mode: consumed as-is". `## Lessons referenced` says both lessons were "heeded by FM 2" and "heeded by the TASK block's named test list", but that list names only `test_addons.py`, `test_codegraph_first_guard.py`, `test_auto_improve_finish_install.py` and `test_plugin_manifests.py`.
- **[BLOCKER] Acceptance criteria 1 and 2 are narrowed in Non-Goals instead of being asked as an Open Question**
  - **What is wrong:** the brief says that with no CodeGraph tool available, `Read`, `Grep` and `Glob` "are allowed, and one log line says why", and that a subagent without the tools can read. The contract allows the call outright only when unavailability can be proven. A background main session (the issue's lead case) gets block-then-retry on every new call. So does a subagent if `agent_id` turns out to be absent (ASSUMED). That trade is decided in a Non-Goal and never offered to the user.
  - **Prior artifact ignored:** `.claude/work-items/2026-11-05-259-codegraph-guard-fail-open.md:32-33` (acceptance criteria).
  - **Where in this contract:** `## Non-Goals` — "Detecting a background main session by itself. The retry escape covers it."; `## Open Questions for User` holds no question about it.
- **[WARN] Decision step 5 does not say which project path it checks, and the result is cached for the whole session**
  - **What is wrong:** `_mcp_server_state(server, project, …)` counts a `.claude.json` project entry only when its key matches the `project` it is given (`auto_improve_finish_install.py:2086, 2101-2106`). Step 4 names its roots (`CLAUDE_PROJECT_DIR`, main checkout, payload `cwd`). Step 5 names none. Sessions in a linked worktree are the plugin's default. In one of them, a local-scope server recorded under the main checkout's path can read as `not-configured`. The guard then fails open for the whole session (the cache is per session), and the positive control is lost without any notice. No test in the TASK block covers a worktree.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-15 "A script that reads a project-owned file must be told which project, not search for one"; `MECHANISMS.md:72` Flat worktree.
  - **Where in this contract:** `## Data Shapes → Guard decision order` step 5 — "The places looked at are those of `auto_improve_finish_install._mcp_server_state`"; the Server availability cache row — "Computed once per session".
- **[WARN] Two host behaviours stay ASSUMED until after the tests are frozen**
  - **What is wrong:** the install writes `mcp__codegraph__*` into `permissions.allow`, which the host reads, and decision step 3 keys on `agent_id`. Both are ASSUMED. The TASK block asks only for the `agent_id` result to be recorded "in the PR", and asks for no trial of the permission form. Repo evidence: `session_id` is read from hook payloads by existing hooks, including a PreToolUse guard (`db-destructive-guard.py:1795`, `stop-dispatcher.py:107-111`, `_project_paths.py:843`), and `.claude/logs/accuracy.jsonl` in the main checkout holds real session UUIDs. No hook, test or log in the repository reads or records `agent_id` or `agent_type`.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "Do not rely on a host expanding a variable in a form nobody has seen work"; `JOURNAL.md` 2026-10-05 "Count a host's size cap the way the host counts, and prove the cap with a real trial" ("put the trial result in the contract before freezing tests").
  - **Where in this contract:** `## Uncertain Assumptions` bullets 1–2; the TASK block — "Record in the PR whether a live subagent payload carried agent_id".
- **[WARN] The wildcard-only claim covers more text than the scan and the edit list reach**
  - **What is wrong:** the scan looks only for `mcp__codegraph__codegraph_` and skips `README.md` (`test_plugin_text_scans.py:276`). It misses bare names of tools that no longer exist: `VOCABULARY.md:14-15` (Symbol Node, Code Edge), `agents/data-architect.md:110` (`codegraph_context`), 17 places in `codegraph-decision-table.md`, and guard line 383. The registry edit list names only `MECHANISMS.md:15` and `VOCABULARY.md:13`. That leaves VOCABULARY 14–15 untouched. `MECHANISMS.md:15` also states the `<cwd>` sentinel gate, and the ways-out list at `MECHANISMS.md:92` lacks fail-open and the retry escape. Neither line gets a correction.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 "A rule titled 'every' must list every line it covers"; `JOURNAL.md` 2026-10-04 "Check a documented guard behaviour against the guard's code".
  - **Where in this contract:** `## Business Concept` item 4 — "every grant, permission, message and document uses `mcp__codegraph__*`"; the TASK block's "Registries (Q2 default)" line.
- **[WARN] The new folder pruner in the shared system temp folder has no link or ownership rule**
  - **What is wrong:** the reset hook deletes every `auto-improve-codegraph-*` folder older than 7 days in `tempfile.gettempdir()`. That is a recursive deleter in a folder other users and processes share. The contract states no rule for links or junctions, and none for non-folder or foreign-owned entries. Its mitigation is "best effort" and cites no mechanism. The convention it says it reuses (`_project_paths.py:827-831`) writes single files and never prunes, so the pruning is new.
  - **Prior artifact ignored:** `MECHANISMS.md:76` Delivery cleanup ("never `rmtree`", link checks before each removal); `MECHANISMS.md:78` Records leftover sweep (`unsafe` for links); `JOURNAL.md` 2026-10-17 "Git for Windows lists files beneath an untracked junction…"; `JOURNAL.md` 2026-11-02 "A revision that adds a path adds its failure modes".
  - **Where in this contract:** `## Failure Modes & Mitigations` — "the reset hook prunes `auto-improve-codegraph-*` folders older than 7 days, best effort."
- **[NIT] An unregistered mechanism is listed as reused** — `## Reused Mechanisms` "Session-keyed temp marker" has no `MECHANISMS.md` entry.
- **[NIT] I-3 is literally false** — step 4 reads `CLAUDE_PROJECT_DIR`, and the Session folder follows `TMP`/`TEMP` (the TASK block sets both per test). "No environment variable changes any decision" should say it means no kill switch.
- **[NIT] The scan's exemption is wider than the acceptance criterion's** — acceptance criterion 7 exempts only "tests that prove the wildcard covers it". The new scan exempts all of `.claude/hooks/tests/`, while the memory scan it copies gives that folder no exemption (`test_plugin_text_scans.py:215-216`).
- **[NIT] The uninstall skill is in Files to touch with no stated change** — `skills/auto-improve-codegraph-uninstall/SKILL.md` has no Extension Points entry.
- **[NIT] The Edit half of acceptance criterion 2 is met but not stated** — the guard's matcher is `Read|Grep|Glob` (`addon.json:15`), so the guard never gates Edit. The contract never says so.
- **[NIT] The review is kept out of the handoff on purpose** — the handoff says the review runs inside `/flow` "so that a second block does not force the Parent Branch Delivery Rule" (`VOCABULARY.md:69` counts a review gate as a block). The user should confirm that choice.

### Applicable journal entries

- **2026-10-04 — Do not rely on a host expanding a variable…** — not addressed; see WARN (host behaviours).
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded for the README and the decision table; partly unmet for the registries (see WARN on the wildcard claim).
- **2026-10-05 — Never hide a forbidden name by hashing it…** — heeded: the scan plants files as controls.
- **2026-10-05 — Count a host's size cap… prove with a real trial** — not addressed; see WARN (host behaviours).
- **2026-10-15 — A script that reads a project-owned file must be told which project** — violated; see WARN on step 5.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — violated; see the first BLOCKER.
- **2026-10-17 — Git for Windows lists files beneath an untracked junction** — not addressed; see WARN on the pruner.
- **2026-10-22 — Describe a broken install by the rows each install age really has** — heeded by the upgrade note and `released_sha256`.
- **2026-10-28 — State the real trigger of a hook** — heeded: the availability cache is per session and only the index check runs on each call.
- **2026-10-28 — A new term's definition must be true against every existing member** — heeded: Retry escape is defined for this one guard.
- **2026-10-28 — Guard messages must use names the guard emits…** — heeded by I-2.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded: `--check`, the permission insert and the released hashes extend existing entries.
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out** — heeded by the uninstall-then-install route and the per-entry `codegraph-tool-named` message.
- **2026-11-02 — Name the tests a fix may change…** — violated; see the first BLOCKER.
- **2026-11-02 — Describe a fixer a skill runs by everything it writes** — heeded: the preview shows the permission and uninstall lists it as kept.
- **2026-11-02 — A revision that adds a path adds its failure modes** — mostly heeded; the pruner's failure mode cites no mechanism.
- **2026-11-02 — A rule titled 'every' must list every line it covers** — violated; see WARN on the wildcard claim.

### What the critic did not check

- `.claude/.scout-cache/registry-digest.md` and the per-domain registry files named at `MECHANISMS.md:63` do not exist in this worktree, so only the Universal tier was read. `INTEGRATION.md` does not exist.
- `derive_area.py`, `cross_area_scan.py` and `pr_merged.py --status` were not run (no shell). The Adjacent Areas line was accepted on the stated empty `areas`, and the Parent Branch check on the stated single block.
- No CodeGraph tool was available. Symbols were checked with Grep and Read.
- `.claude/north-stars/` does not exist, so checklist item 13 has no findings.

---
