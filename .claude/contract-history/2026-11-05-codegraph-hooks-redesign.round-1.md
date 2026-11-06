# Critique round 1 - 2026-11-05-codegraph-hooks-redesign

Moved out of the contract on approval, as `.claude/templates/concept-contract.md` requires for a superseded round.


**Critic:** contract-critic
**Date:** 2026-11-05
**Verdict:** blockers-found

### Findings

- **[BLOCKER] Issue idea 3 (do not block a Read of one named file; block only exploratory Grep and Glob) has no decision anywhere in the contract**
  - **What is wrong:** none of I1-I6, the Non-Goals or the Open Questions covers a per-tool split of the gate, so the brief's first acceptance criterion ("chooses among the six ideas ... names the ideas it rejects and why") is not met for this idea, and Q1 defers the check rather than making it.
  - **Prior artifact ignored:** `.claude/work-items/2026-11-05-261-codegraph-hooks-redesign.md:35-36` (acceptance criterion 1); the issue's idea list as read by the main session (this critic had no shell and could not run `gh issue view 261`, so the idea text is the main session's reading).
  - **Where in this contract:** `## Alternatives Considered & Why Rejected` — "The six ideas as reconstructed from the brief, the #259 contract's Non-Goals and the #259 live trial". The contract's I3 ("a once-per-session gate") is the issue's idea 2, not its idea 3.
  - → Revised by architect: Alternatives row 3 is adopt-in-shadow (measured by `tool`, never enforced here because it would break the unchanged suites), and the policy is new Q5 with one recommendation.
- **[BLOCKER] Issue idea 5 (cheaper hot path: check the marker before classifying paths, import helpers only when needed) has no decision, and the design moves the other way**
  - **What is wrong:** the live `decide()` classifies every path before it looks at the marker (`.claude/addons/codegraph/hooks/codegraph-first-guard.py:338-350`) and imports `_error_log` and `_project_paths` at module load (`:36-47`); the contract keeps `decide()` unchanged and adds a shadow section that runs before it on every guarded call, and no Alternatives row rejects or adopts the reorder or lazy imports.
  - **Prior artifact ignored:** brief acceptance criterion 1 (`work-items/...-261-...md:35-36`) and criterion 6, the per-call cost (`:47-48`); the issue's idea 5 as read by the main session.
  - **Where in this contract:** `## Extension Points` — "called once from `main()` before `decide()` ... `decide()` is unchanged"; `S-2` — "It runs before the live decision".
  - → Revised by architect: adopted live as G-1 (order 0, 2, 1, 3-7; lazy imports keeping module names and the fallback banner); outcomes unchanged so the three suites run unedited; the shadow mirrors the order (S-2) and block 3 measures the saving.
- **[BLOCKER] The Shadow record needs the live decision, but S-2 runs the shadow before the live decision, and the #259 live decision has side effects**
  - **What is wrong:** `live_decision`, `live_reason`, `outcome` and `retry_of_block` (`live_reason` is `retry-escape-used`) can only be known after the live decision. Under #259 that decision deletes a ticket at step 6 and writes one at step 7, and it writes `logged-<reason>` notice flags. A live block then leaves through `sys.exit(2)` inside `block()` (`codegraph-first-guard.py:457, 474-478`). So the shadow either calls the side-effecting decision a second time or runs after a path that exits. Both break S-1 ("never writes or consumes" a ticket) or S-3 ("byte-identical").
  - **Prior artifact ignored:** `.claude/worktrees/20261105-bug-259-codegraph-guard-fail-open/.claude/concepts/2026-11-05-codegraph-guard-fail-open.md:49, 51, 80-81` (Retry escape ticket written and consumed by the guard; Notice flag; decision steps 6-7).
  - **Where in this contract:** `### Shadow decision (invariants)` S-2 — "It runs before the live decision, and its only write is the cursor and the log line"; `### Value Objects` Shadow record — "`live_decision`, `live_reason` ... `outcome` ... `retry_of_block`".
  - → Revised by architect: G-2 fixes the order (pure Live plan, then shadow, then live effects and exit), so the shadow runs on blocks and never touches tickets or flags; `decide()` stays plan + apply for its callers; block 2 tests the ticket-once and forced-raise cases.
- **[WARN] The measurement log location is promised never to be under the home folder, but the reused locator falls back to it**
  - **What is wrong:** `_project_paths.logs_dir()` returns `HOME/.claude/logs` when `CLAUDE_PROJECT_DIR` is unset (`.claude/hooks/_project_paths.py:164-167`). The contract also leaves undeclared where the log goes when the guard's fail-soft `_pp` import is `None`, and what `codegraph_shadow_report.py` reads when `--project` is omitted.
  - **Prior artifact ignored:** `MECHANISMS.md:43` (Two-layer Claude path resolution — runtime `logs/` resolves through `project_dir()` alone); JOURNAL `2026-10-05 — A documented "missing file means the default" must read one named location only`; `.claude/hooks/tests/test_addons.py:134` (a hook falling back to the home folder is recorded as a defect).
  - **Where in this contract:** `### Entities` Measurement log — "the folder `_project_paths.logs_dir()` returns ... Never written under the home folder."
  - → Revised by architect: the path comes from `CLAUDE_PROJECT_DIR` alone (no `logs_dir()`, no `_pp` dependency); unset or no `.claude/` means no record; the report's `--project` default and its single read location are declared.
- **[WARN] Concurrent writers of the cursor and the log have no invariant or failure mode**
  - **What is wrong:** parallel tool calls in one assistant message start several guard processes in the same Session folder at once (subagents share the parent's folder per #259). Nothing declares an atomic cursor write (temp file plus `os.replace`), append atomicity for JSONL lines, or how the "single final `log-full` line" holds under a race. Uncertain Assumption (d) covers transcript flush order, not concurrent cursor writes.
  - **Prior artifact ignored:** JOURNAL `2026-11-02 — A revision that adds a path adds its failure modes`; `MECHANISMS.md:64` (Preview-hash apply's temp-file plus `os.replace` write, the repository's sanctioned atomic write); #259 contract `:47` (one folder shared by subagents).
  - **Where in this contract:** `### Entities` Transcript cursor — "Written only by the shadow path, and only after a full parse of the new bytes"; Measurement log — "after a single final `{"event":"log-full"}` line".
  - → Revised by architect: cursor written temp + `os.replace`, last writer wins, rescan idempotent; one `os.write` per line of at most 1 KB; extra `log-full` lines and torn lines tolerated and counted; a failure mode and a block 2 test added.
- **[WARN] The cited "bounded" transcript read is not bounded in bytes**
  - **What is wrong:** `plan-question-advisor.py:56-57` iterates the whole file through `deque(fp, maxlen=...)`. It keeps the last lines but reads every byte, so it is the opposite of the 4 MB / 2 MB Read limits the contract reuses it for.
  - **Prior artifact ignored:** `.claude/hooks/plan-question-advisor.py:51-61` (the cited source itself); JOURNAL `2026-10-04 — Check a documented guard behaviour against the guard's code`.
  - **Where in this contract:** `## Reused Mechanisms` — "the bounded, `errors="replace"` read that fails to 'no signal'. Reused as the pattern."
  - → Revised by architect: listed as not reused, with what it really does; Read limits now require a true tail read (seek, drop the first partial line, never iterate the file), tested in block 2.
- **[WARN] The measurement half of the New Mechanism partly duplicates #259's guard events, and issue idea 6 (a measurement log) has no Alternatives row**
  - **What is wrong:** #259 already logs every block (`GuardBlocked`), every retry escape with a fingerprint prefix (`RetryEscapeUsed`) and fail-open reasons. Those events are the "blocks followed by a retry" and reason-count data of acceptance criterion 7. The contract builds `retry_of_block` and reason counts again in a parallel file. Its justification only says that `log_event` lacks a paired live/candidate record.
  - **Prior artifact ignored:** #259 contract `:101-103` (Events table); the extend-before-create rule in the registry header (`MECHANISMS.md:3`).
  - **Where in this contract:** `## New Mechanisms` — "`_error_log.log_event` records events (block, fail-open) and has no paired live/candidate record and no outcome classification."
  - → Revised by architect: idea 6 row added with the #259 overlap and what the shadow log adds (per-call silent allows, paired decision, pairing keys, cost); `retry_of_block` dropped (derived from `live_reason`); #259 events kept unchanged.
- **[WARN] The shadow adds a file append to every guarded call in real sessions, including allowlisted targets, and that cost is not in the bench**
  - **What is wrong:** S-4 writes a Shadow record for an allowlisted target (today an early allow with no I/O), and the bench's "allowlisted target" case does not separate the run with the shadow from the run without it. So the measured per-call cost understates what installs pay during shadow, and Q4 makes shadow the default for every install.
  - **Prior artifact ignored:** JOURNAL `2026-10-28 — State the real trigger of a hook, not the printing condition`; brief acceptance criterion 6 (`work-items/...-261-...md:47-48`).
  - **Where in this contract:** `S-4` — "a target in the non-source allowlist is logged with its reason"; block 3 CONSTRAINTS — "allowlisted target; gated target with marker present (old); ...".
  - → Revised by architect: block 3 runs every case on the #259 guard and on this branch's guard, so the allowlisted and marker-present cases report the shadow's added cost (log append included) separately.
- **[NIT] "Every block except 1 carries it as a Precondition" is false** — blocks 3 and 5 have no `**Preconditions:**` line (only transitive via block 2). JOURNAL `2026-11-02 — After amending a contract, update every summary of the block graph`.
- **[NIT] The follow-up stub names the outcome `new-more-closed`; the contract names it `shadow-more-closed`** — `.claude/concepts/followups/2026-11-05-codegraph-hooks-cutover.followup.md:16`.
- **[NIT] `## Lessons referenced` cites "2026-10-05 — prove with a real trial"; the journal title is "Count a host's size cap the way the host counts, and prove the cap with a real trial"** — `JOURNAL.md:117`.
- **[NIT] Acceptance criterion 5 ("without a manual step") is met only under Q3's recommended reading** — re-running the install skill is itself a manual step. Q3 hoists this correctly; the user's answer decides whether criterion 5 holds.
- **[NIT] Budget** — the contract was already close to its 12,000-token line before this critique; with it, the file likely exceeds the budget (`.claude/templates/concept-contract.md:22`).
- **[NIT] Registry tiers absent in this worktree** — no `## Project:` section and no per-domain files under `.claude/registries/MECHANISMS/` (described at `MECHANISMS.md:63`), no `.claude/.scout-cache/registry-digest.md`, no `.claude/registries/INTEGRATION.md`. Universal tier only was checked.

### Applicable journal entries

- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** — heeded by block 1 (live checks before any code), in spirit; no new host-read row is written.
- **2026-10-04 — Check a documented guard behaviour against the guard's code** — violated in a reused citation, see WARN "bounded transcript read".
- **2026-10-05 — Neutralise every field echoed from untrusted input** — heeded by the Shadow record (classes, booleans, hash prefixes only) and the leak test.
- **2026-10-05 — A documented "missing file means the default" must read one named location only** — not addressed for the log location, see WARN on `logs_dir()`.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures** — heeded: the installer's `addon-file-differs` fixtures (`test_auto_improve_finish_install.py:4121-4151`) use edited content, so they stay refused under `update`.
- **2026-10-22 — Describe a broken install by the rows each install age really has** — heeded by block 4 CONSTRAINTS.
- **2026-10-28 — State the real trigger of a hook, not the printing condition** — partly heeded (no new process start). The per-call log append is not costed, see WARN.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam** — heeded (upgrade extends Disabled add-on hook / `released_sha256`; shadow log decide-at-review).
- **2026-11-01 — After merging a base that changes the row shape a feature reads, re-check every coverage claim** — heeded by the #259 Precondition and block 2's "re-read the merged decision order".
- **2026-11-02 — Name the tests a fix may change by the state they guard** — heeded (the three suites are named unchangeable; the follow-up owns their change).
- **2026-11-02 — A revision that adds a path adds its failure modes** — not addressed for concurrent writers, see WARN.
- **2026-11-02 — After amending a contract, update every summary of the block graph** — minor drift, see NIT on Preconditions.

### Brief acceptance criteria → handoff blocks (main-session check 2)

- Six ideas chosen with evidence — **not met** (BLOCKERs on ideas 3 and 5; idea 6 adopted without a row).
- Shadow mode, old hooks removed later — block 2; removal in the follow-up stub.
- Every failure path allows (unreadable, missing, changed format, parse error, subagent) — block 2 tests (each `unknown` cause, subagent, corrupt transcript); block 5 item (1)-(2).
- Three existing test files unchanged, new tests per path, corrupt-transcript test — block 2 (and block 4 for `test_addons.py`); block 5 item (3).
- Upgrade without a manual step, reusing `released_sha256` — block 4; conditional on Q3.
- Cost per gated call, old and new, recorded — block 3 (artefact plus pull request table); see WARN on the allowlisted case.
- Measurement log with reason counts and blocks followed by a retry — blocks 2-3; see WARN on overlap with #259 events.
- Five open points answered or covered by fail-open — block 1; block 5 item (7).

### What the critic did not check

- `gh issue view 261 --json body`: no shell tool in this run. The idea comparison rests on the main session's reading of issues 3, 5 and 6. The issue's ideas 1 and 4 were not reported, so the contract's I2, I5 and I6 could not be matched to issue text.
- `git log origin/master ... -- .claude/addons/codegraph` and `--grep=259`: no shell. The local remote-tracking ref `.git/refs/remotes/origin/master` reads `3f795aed`, the branch base. As of the last fetch, #259 is not on master, and the #259 brief still reads `status: implementing`, `pr: UNKNOWN`. A fresh fetch was not possible.
- `pr_merged.py --contract 2026-11-05-codegraph-hooks-redesign --status --json` (`defects`, `layout_defects`): no shell. Manual reading: the `**Work Item Brief:**` header is present for five blocks, no block lists a plugin version file, and sub-tasks target the parent branch. The brief's frontmatter still reads `contract: none`, which the header-first selector (`MECHANISMS.md:84`) tolerates.
- `cross_area_scan.py` / `derive_area.py`: not run. `.claude/area-mapping.json:14` has an empty `areas` object, so the exception for the Adjacent Areas single line applies.
- North-star alignment: `.claude/north-stars/` does not exist; no findings by rule 13.c.
- Placement: this critique fills the template's empty `## Critique` slot (before `## Lessons referenced`, per `.claude/templates/concept-contract.md:324`) rather than adding a second `## Critique` heading at the end of the file.


## User response (2026-11-05)

The user answered `approve` to the plan: accept the recommended answers to Q2-Q5 and fold every finding into the contract.
Each BLOCKER and WARN above was addressed by the architect (see its `Revised by architect` line) and re-checked by a fresh critic in round 2, which found no BLOCKER.
