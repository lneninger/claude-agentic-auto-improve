# Concept Contract — CodeGraph hooks redesign: one hook, measured cost, shadow rollout (issue #261)

**Project:** claude-agentic-auto-improve
**Date:** 2026-11-05
**Requested by:** user
**Status:** implemented
**Implemented:** 2026-11-07, automatically, by pr_merged.py after https://github.com/lneninger/claude-agentic-auto-improve/pull/268, https://github.com/lneninger/claude-agentic-auto-improve/pull/274, https://github.com/lneninger/claude-agentic-auto-improve/pull/277, https://github.com/lneninger/claude-agentic-auto-improve/pull/282, https://github.com/lneninger/claude-agentic-auto-improve/pull/284, https://github.com/lneninger/claude-agentic-auto-improve/pull/289; 1 checklist items from review reports, 0 with no structured evidence; not performed: none; owner confirmed resolved: none
**Work Item Brief:** .claude/work-items/2026-11-05-261-codegraph-hooks-redesign.md
**Tracking issue:** #261
**Budget:** 12,000 tokens

> **Protocol:** filled in by `data-architect`. The lifecycle, budget rule and handoff rules are in `.claude/templates/concept-contract.md`.

---

## Business Concept

- **What is this thing?** The `codegraph` add-on asks the agent to start each Investigation Turn with CodeGraph. After #259 it uses three hooks around a per-session marker: reset (every prompt), tracker (after every CodeGraph call), guard (every `Read`, `Grep`, `Glob`). This contract designs the **one-hook** successor (issue idea 1): the guard derives "CodeGraph used since the last human prompt?" from the session transcript the host already writes. It ships that decision **in shadow** only: computed beside the live decision, logged, never enforced. It also ships a cheaper live hot path (idea 5), the measurement log (idea 6), the five live checks, and an in-place upgrade. The switch-over is the follow-up `.claude/concepts/followups/2026-11-05-codegraph-hooks-cutover.followup.md`.
- **Depends on #259.** On this branch's base (`3f795ae`) the hooks still use `<cwd>/.claude/.codegraph-used-this-turn` and the #259 brief reads `status: implementing`, so #259 (session folder, decision steps 0-7, retry escape, `released_sha256` for active hooks) is not merged. Blocks 2, 3, 4 and 5 each carry it as a Precondition, and block 2 carries a STOP rule (Failure Modes).
- **Baseline suites:** `test_codegraph_first_guard.py`, `test_worktree_path_guards.py` and `test_addons.py` as they stand on master after #259 merges. "Unedited" anywhere in this contract means unedited against that baseline, never against `3f795ae` (#259 edits all three).
- **Existing terms:** CodeGraph, Investigation Turn (`VOCABULARY.md:16`, kept), Add-on hook, Add-on manifest; from #259: Retry escape, Turn marker, Call fingerprint.
- **New terms (Universal, promoted at review):**
  - **Transcript turn state**: `open`, `closed` or `unknown:<cause>`, derived from the transcript: `open` when a CodeGraph tool use follows the last human prompt. `unknown` never blocks.
  - **Live plan**: the guard's decision computed as a pure function: decision, reason and the side effects it would apply, with none applied.
  - **Shadow decision**: the Live plan recomputed with the Transcript turn state in place of the Turn marker. Logged, never enforced, its effects discarded.
  - **Shadow record**: one measurement-log line per guarded call.

---

## End-User View

Not applicable. Reason: no Angular UI surface is touched. The change is hook behaviour, an installer upgrade, a report script and documentation.

---

## Data Shapes

### Entities

| Name | Fields | Invariants | Ownership |
|------|--------|------------|-----------|
| Transcript cursor | `transcript-cursor.json` in the #259 Session folder: `{path, identity (device + inode, or creation time where there is no inode), scanned_to (offset after the last complete or skipped line), skipping (bool: inside a skipped long line), turn, session_seen (bool, sticky), updated_at}` | Inherits #259's step-0 folder rule: read or written only when the Live plan's step 0 found the Session folder usable (never through a link or junction, a not-a-folder, or a foreign-owned folder); otherwise the scan is cold and nothing is persisted. Written only by the shadow path, after a full parse of the new bytes, as `transcript-cursor.<pid>.tmp` in the same folder then `os.replace`. An unparseable cursor reads as absent (cold scan). A different `path` or identity, or a file shorter than `scanned_to`, means a cold scan. Concurrent writers: last replace wins; a regressed cursor only re-reads bytes, and the state is a function of the bytes, so re-reading is idempotent. Never stores transcript text. | guard (shadow) |
| Measurement log | `<CLAUDE_PROJECT_DIR>/.claude/logs/codegraph-shadow.jsonl`, from the environment variable alone (not `logs_dir()`, which falls back to the home folder) | `CLAUDE_PROJECT_DIR` unset, or `<project>/.claude/` absent → no record is written (fail open). Append-only: one `os.write` per line on a file opened for append, each line at most 1 KB. The size check precedes the write; at 10 MB a `{"event":"log-full"}` line is written and writing stops. Under concurrent writers a few records or more than one `log-full` line may pass the cap; the report tolerates both. The shadow never takes a lock or waits on one; on Windows two concurrent appends can overwrite each other unseen (Uncertain Assumptions), so **every report count is a lower bound**. Holds no path, pattern, prompt text or file name. | guard (shadow) |

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| Transcript entry class | closed set: `human-prompt` (a boundary), `codegraph-use` (an assistant entry with a `tool_use` block named `mcp__codegraph__*`), `other` | The exact rule is fixed by block 1's live checks. **Fail-open bias:** only an entry positively identified as a human prompt is a boundary; tool results, injected system text, hook output, compaction summaries, sidechain prompts and unknown types are `other`. A missed boundary keeps the turn open, which allows more. |
| Transcript turn state | `open` / `closed` / `unknown:<cause>`, causes: `no-transcript` (also: not a regular file), `unreadable`, `parse-error`, `window-exceeded`, `time-exceeded`, `rewritten`, `subagent` | Replaces the Turn marker at #259 step 2, in the Shadow decision only. |
| Read limits | **true tail read**: `transcript_path` must be a regular file (`os.stat`, `S_ISREG`) before `open()`, else `unknown:no-transcript`; seek to `scanned_to`, or on a cold scan to `size - 2 MB` (the cold window equals the per-call limit), and drop the first partial line after a mid-file seek; read at most 2 MB per call; parse only complete lines (a partial last line waits) | Cost bound. **If the per-call limit is hit, the answer is `unknown:window-exceeded` even when a boundary was found**, so a stale answer is impossible; the cursor still advances over what was parsed. A cold window with no boundary is also `window-exceeded`. A single line longer than 2 MB is skipped: the cursor moves past it (`skipping` until its newline) and the record counts it in `skipped_long_line`. The whole file is never iterated. |
| Shadow time budget | 50 ms of wall clock for the whole shadow section, checked between chunks and lines | Exceeded → the shadow stops, records `unknown:time-exceeded` without writing the cursor, and the live effects proceed. 50 ms is small beside a hook's own Python start (tens of ms) and far below any hook timeout, so the shadow cannot push a live block past the host's timeout; block 3's bench shows how often a cold scan hits it. Whether Claude Code 2.1.318 lets a call through when a hook is killed at its timeout is unverified (block 1, point f). |
| Shadow record | `ts`, `session` (12 hex of SHA-256 of the Session key), `agent` (bool), `tool`, `target_class` (`allowed` / `source` / `unknown` / `not-computed`), `live_decision`, `live_reason` (the #259 reason set), `turn_marker` (bool; `null` when the Live plan allowed at step 0, before reading it), `transcript_turn`, `session_seen`, `shadow_decision`, `shadow_reason` (the live set with `turn-marker-present` replaced by `transcript-open` and `transcript-unknown`), `outcome` (`agree` / `shadow-more-open` / `shadow-more-closed`), `fp` (12 hex of the Call fingerprint), `prompt_key` (12 hex of SHA-256 of `prompt_id`, or `none`), `shadow_ms`, `bytes_read`, `skipped_long_line` (count) | One log line. `fp` pairs a block with its retry; `tool` measures idea 3; `session_seen` measures idea 2; `prompt_key` measures the prompt-id option. |
| Shadow report | per project, every count labelled a lower bound: sessions, records per `outcome`, `shadow-more-closed` by (`live_reason`, `transcript_turn`), reason counts split by `agent` (so subagent calls never merge with open-turn calls), blocks, `skipped_long_line` total, blocks followed by a retry (same `session` and `fp`), blocks per `tool` (idea 3), blocks a per-session gate would have avoided (`session_seen`, idea 2), `shadow_ms` p50 / p95, malformed and `log-full` lines | Output of `codegraph_shadow_report.py`; the cut-over evidence. |

### Guard order (invariants)

- **G-1 (idea 5, live):** the #259 order runs as 0, 2, 1, 3-7: the Turn marker is checked before path classification. Steps 1 and 2 both allow with no side effect and no output, so the decision, exit code, stdout and stderr are unchanged; only the internal reason differs when both apply. `_error_log` and `_project_paths` are imported on first use (classification, banner, log), not at module load. Every module-level name keeps its meaning and stays patchable: `log_event`, `_pp`, `_pp_checkout_equivalent_path`, and #259's getattr-bound `worktree_own_root`, `tree_kind`, `main_checkout_root` (with the inline-walk parity test), plus the marker and availability names that `load_hook` patches; the fallback-mode banner shows when the import fails. The Baseline suites' in-process rows pass unedited.
- **G-2 (pure plan, then shadow, then effects):** `main()` runs (1) the Live plan; (2) the shadow section: Transcript cursor, Shadow decision, cursor write and record append; (3) the Live plan's effects, then exit 0 or `block()` → exit 2. Every #259 effect is placed:
  - **Plan:** step 0's lazy Session-folder creation and its writability check (its result is the step-0 verdict; idempotent, identical with or without the shadow); every read, including the availability verdict computed in memory.
  - **Apply:** the `availability.json` write; the ticket delete (step 6) or write (step 7); the `logged-<reason>` notice flags; every `log_event` (GuardBlocked, RetryEscapeUsed, GuardFailedOpen); the stderr line on each `fail-open:*` and `retry-escape-used` allow and the block banner; the exit code.
  - **Ticket already gone at apply** (an identical parallel call consumed it after the plan): the planned allow stands with `retry-escape-used`; apply never re-decides. This is #259's own check-then-delete window, and it can only allow.
  - The shadow therefore runs on blocked calls, sees the live result, and cannot touch a ticket, a flag or `availability.json`. `decide()` keeps its name, signature, return and effects as plan + apply, so its existing callers see no change.
- **S-1:** the Shadow decision is the same planner with step 2 reading the Transcript turn state; `unknown:*` counts as `open`. It reuses the Live plan's step-0 and availability verdicts and recomputes neither. Steps 6-7 read whether a ticket matches and never consume or write one. Its planned effects are discarded.
- **S-2:** the shadow mirrors G-1: transcript state first, classification only when the state is `closed` (else `target_class` = `not-computed`). Its only writes are the cursor and the record. No hook, row or process start is added.
- **S-3 (cannot change behaviour):** every exception and every `SystemExit` (`BaseException`) the shadow raises is swallowed, and its duration is capped by the Shadow time budget. Exit code, stdout and stderr are byte-identical with the shadow forced to raise; the Session folder is equal under the oracle of block 2 (same file names and contents, ignoring the ticket `ts`, the `availability.json` `checked_at` and the shadow's own cursor and temp files). No kill switch, no stderr line.
- **S-4 (subagent):** with `agent_id` present no transcript is read and `transcript_turn` = `unknown:subagent`. The shadow, transcript state first, allows at its step-2 position (`unknown:*` counts as open, `shadow_reason` = `transcript-unknown`). Live may allow earlier, at step 0 or at step 2 (a subagent shares its parent's Session folder and so its marker), else at step 3. The report splits reason counts by `agent`, so subagent calls never merge with open-turn calls.

### Events

| Name | Emitter | Listeners | Payload |
|------|---------|-----------|---------|
| ShadowDecisionRecorded | guard | measurement log; `codegraph_shadow_report.py` | Shadow record |

### Commands

| Name | Handler | Payload | Possible rejections |
|------|---------|---------|---------------------|
| Report the shadow | `py -3 .claude/scripts/codegraph_shadow_report.py [--project <dir>] [--json]`, read-only; `--project` defaults to `CLAUDE_PROJECT_DIR`, then the current folder; reads only `<project>/.claude/logs/codegraph-shadow.jsonl` | the log | exit 2: log missing or unreadable (never an empty "agree"); malformed lines counted, not fatal |
| Upgrade the add-on in place | `auto_improve_finish_install.py addon --name codegraph`, preview then apply | as today | a hook whose folded hash is in `released_sha256[<hook>]` becomes `update` (backed up, then replaced) instead of `addon-file-differs`. An edited copy is still refused, naming the file and the uninstall-then-install route. |

---

## Reused Mechanisms

- **Add-on layout**: consumed. No new hook, row or manifest key.
- **Disabled add-on hook / `released_sha256`** (`MECHANISMS.md:87-91`, extended to active hooks by #259): extended by one consumer: a released hash means "unedited, safe to replace". The lists gain the #259 versions of the guard and reset hook.
- **Preview-hash apply** (`MECHANISMS.md:64`): extended with `update`, inside the same plan hash, with backup, `os.replace` and the link refusal. Its temp-file + `os.replace` write is also the cursor's write.
- **#259 Session folder, Session key, Call fingerprint, decision order**: consumed; the order is reordered per G-1 and split per G-2 with unchanged outcomes.
- **#259 pruner (I-5)**: extended: `transcript-cursor.json` and `transcript-cursor.<digits>.tmp` join its known names.
- **#259 events GuardBlocked, RetryEscapeUsed, GuardFailedOpen** (`log_event`): kept unchanged as the operational log. The shadow log does not re-derive them (see idea 6).
- **Not reused:** `plan-question-advisor.py:51-61`. Its `deque(fp, maxlen=...)` keeps the last lines but reads every byte; the Read limits require a true tail read instead.
- **Contract sub-task loop**: blocks 1 and 3 declare a `.claude/reviews/` path, so they are verdict-bearing and their dependents wait on `pass`.

## New Mechanisms (if any)

- **Name:** Shadow decision log.
- **Purpose:** run a candidate guard decision beside the live one, log both, enforce nothing.
- **Why an existing mechanism was not sufficient:** `log_event` records blocks, escapes and once-per-session fail-opens. It has no record for silent allows (allowlisted, marker present), no paired live/candidate decision, no outcome, no per-call cost. Per-call reason counts and agreement cannot be derived from it.
- **Proposed location:** one delimited section of `codegraph-first-guard.py`; report at `.claude/scripts/codegraph_shadow_report.py`.
- **Extension seam:** another guard writes Shadow records to `<project>/.claude/logs/<guard>-shadow.jsonl` with the same `outcome` set; the report takes the file.
- **Promote?** decide-at-review; promote when a second guard adopts it (JOURNAL 2026-10-28).

---

## Extension Points

- **Guard:** G-1 reorder and lazy imports; G-2 plan/apply split; the shadow section between them, wrapped per S-3.
- **Reset hook:** `transcript-cursor.json` and the cursor temp file `transcript-cursor.<digits>.tmp` added to the pruner's known names; nothing else.
- **`addon.json`:** the #259-version folded hashes of the guard and reset hook added to `released_sha256`.
- **Installer:** the `update` action and its preview wording.
- **Docs:** the install skill names the shadow log, the report and the upgrade; the uninstall skill says the log is kept; the decision table describes shadow mode.

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| Claude Code host | guard | hook stdin JSON | adds reading `transcript_path` and `prompt_id` (present per the #259 live trial) | host → hook |
| Claude Code host | guard | transcript JSONL | the entry fields block 1 records | host file → hook (read-only) |
| guard | report script | measurement log | Shadow record | hook → script |
| install script | project hooks folder | Preview-hash apply | `update` action | script → project |

No REST, SignalR or DTO surface. Both sides of each row are in `Files to touch`, apart from the host, which is read only.

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold. `.claude/area-mapping.json:14` has an empty `areas` object. Not run here (no shell); to confirm: `py -3 .claude/scripts/cross_area_scan.py .claude/concepts/2026-11-05-codegraph-hooks-redesign.md`.

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

## Chat Tool Impact

Not applicable. Reason: no REST endpoint or SignalR event is added or changed.

---

## Non-Goals

- The cut-over (enforcing the Shadow decision, retiring the tracker and reset hooks, moving pruning into the guard, changing the three existing test files): the follow-up stub.
- Any Investigation Turn policy change now: ideas 2, 3 and 4 are measured here and decided at the cut-over.
- Everything in #259; how CodeGraph indexes code; any other guard.
- Upgrading on plugin update without the install skill being run (Q3).

## Confidence

Confidence: Medium.
- **High:** S-3 and G-2 (byte-identity and effects tests); G-1 (both reordered steps are side-effect-free allows); the upgrade extension; the block graph.
- **Medium:** the transcript entry rule; it rests on block 1, on Claude Code 2.1.318 only.

## Alternatives Considered & Why Rejected

One row per idea of issue #261, numbered as the issue numbers them (Q1, resolved).

| # | Issue idea | Decision | Evidence |
|---|------------|----------|----------|
| 1 | Bounded read of the transcript END for a `mcp__codegraph__*` tool use since the last user prompt, replacing marker, tracker and reset; parse per line, look for an assistant `tool_use` block; fail open on parse trouble; subagents fail open on `agent_id` | **adopt-in-shadow** (enforced only by the follow-up) | Removes two of three hooks and the marker that is lost on a folder change. `transcript_path` and `agent_id` verified present (#259 trial). Every failure is `unknown` → allow; subagents per S-4. The five open points are block 1. |
| 2 | Keep the marker, gate once per session, drop the reset hook | **defer-with-owner** (cut-over follow-up; the user decides there) | Drops one hook against idea 1's two, and changes the Investigation Turn policy (`VOCABULARY.md:16`). The record's `session_seen` lets the report count the blocks it would have avoided (a lower bound: a cold scan sees only 2 MB). |
| 3 | Never block a Read of one named file; block only exploratory Grep and Glob | **adopt-in-shadow** (measured now; enforced at the cut-over only if Q5 = yes) | A policy change, and enforcing it now would break the unchanged-tests criterion (`test_codegraph_first_guard.py:121-129` expects a Read of source to block). The record's `tool` gives blocks per tool and their retry rate, which is the data Q5 needs. |
| 4 | Nudge before blocking: the first call is allowed with a visible hint | **defer-with-owner** (cut-over follow-up) | A policy change; it also prints on an allowed call, which S-3 forbids in shadow. #259's retry escape already lets the identical second call through; "blocks followed by a retry" measures how often a block only costs a round trip. |
| 5 | Cheaper hot path: check the marker before classifying paths; import helpers only when needed | **adopt** (live, block 2, G-1) | Today `decide()` classifies before the marker (`codegraph-first-guard.py:338-350`) and imports both helpers at load (`:36-47`). The reorder swaps two side-effect-free allow steps, so exit code and output are unchanged and the Baseline suites run unedited. Block 3 measures the saving. |
| 6 | A measurement log: reason counts, blocks followed by a retry | **adopt** (block 2, report in block 3) | #259's GuardBlocked and RetryEscapeUsed record blocks and escapes, and GuardFailedOpen only once per session per reason. The shadow log adds a record per call (silent allows included), the paired decision and outcome, the `session` + `fp` pairing, and per-call cost. It reads the live reason and adds no second ticket logic. |

**Other options considered (not issue ideas):**
- Key the marker by `prompt_id` (still needs the tracker): measured via `prompt_key` as a fallback if idea 1 disagrees.
- One script on three events: same process starts; moot under idea 1.
- An `if` condition on the guard's row: host handling for Grep/Glob unverified; deferred to the follow-up.
- Shadow as a fourth hook: one more process start per call, distorting the cost measured, and a settings change for every project.

## Uncertain Assumptions

- `VERIFIED via addon.json:12-30, guard:173-179`: this branch has the pre-#259 hooks.
- `VERIFIED via the #259 brief and contract`: `status: implementing`; its live trial verified `transcript_path`, `session_id`, `prompt_id`, `agent_id` (Claude Code 2.1.318).
- `ASSUMED`: origin/master has not merged #259 since. Verification: `git fetch; git log origin/master --oneline -- .claude/addons/codegraph`.
- `ASSUMED` (block 1 makes each VERIFIED or "unverified, covered by fail-open"): (a) subagent transcript location (S-4 never reads one); (b) injected system messages versus human prompts (fail-open bias); (c) compaction rewrites or appends (`rewritten` or `unknown` allows); (d) in parallel calls the assistant entry is flushed before the sibling's PreToolUse (if not, the shadow reads `closed` exactly as the PostToolUse tracker would); (e) format stability (`parse-error` allows; the log shows the rate).
- `ASSUMED` (unverified for Claude Code 2.1.318): a PreToolUse hook killed at its timeout lets the call through. The Shadow time budget keeps the shadow far from any timeout either way; block 1 checks it (point f).
- `ASSUMED` (not verified, accepted): on Windows, append mode through the C runtime seeks to the end and then writes, so two concurrent guard appends can overwrite each other with no malformed line left behind. Accepted as "report counts are lower bounds"; the shadow never waits on a lock.
- `ASSUMED`: the report script needs no shipped-scripts list entry. Verification: block 3 runs `test_plugin_manifests.py` and `test_plugin_text_scans.py`.
- `ASSUMED`: no existing test asserts the guard leaves `<project>/.claude/logs/` empty, or that `_project_paths` is imported at load. Verification: block 2 runs the Baseline suites unchanged.

## Failure Modes & Mitigations

- **The shadow changes a live decision, output or effect.** S-3 and G-2; tests compare exit code, stdout, stderr and the Session folder (block 2's oracle) with the shadow forced to raise, on blocked and allowed calls.
- **The shadow delays a live block past the host's timeout.** Regular-file check before `open()`; the 50 ms Shadow time budget; block 1 point (f).
- **The shadow consumes a ticket, sets a flag or writes `availability.json`.** G-2 and S-1; a test with a matching ticket shows it consumed exactly once, by the live path.
- **A stale or frozen tail answer.** A hit limit always answers `window-exceeded`; a line over 2 MB is skipped and counted.
- **The shadow writes through a planted link.** The cursor inherits #259's step-0 folder rule.
- **The reorder or lazy import changes behaviour.** G-1; the Baseline suites unedited, including the fallback-mode banner, getattr parity and `load_hook` rows.
- **Slow reads on a huge transcript.** True tail read, Read limits, time budget, cursor, `shadow_ms`, block 3's bench.
- **Concurrent guards race on the cursor or log.** Atomic replace and idempotent rescan; one write per line; torn lines and extra `log-full` lines counted by the report; lost Windows appends make every count a lower bound.
- **A crash leaves a cursor temp file and stops pruning.** `transcript-cursor.<digits>.tmp` is a known pruner name.
- **The log lands in the home folder.** The path comes from `CLAUDE_PROJECT_DIR` alone; unset → no record; tested.
- **A misclassified entry would block at the cut-over.** `shadow-more-closed`, and Q2's zero-unexplained criterion.
- **The cursor stops #259's pruner.** Known-name list plus a pruner test.
- **The log leaks paths or prompt text.** Classes, booleans and hash prefixes only; a test greps the log for the named paths.
- **The upgrade overwrites an edited hook.** `update` only for a released hash, backup first, otherwise `addon-file-differs`.
- **The transcript reading is unsound.** Block 1 is verdict-bearing; `blocked` holds blocks 2-5 and the contract is revised toward the prompt-id option.
- **#259 changes shape before merging.** Preconditions; block 2 re-reads the merged order before writing G-1/G-2. **STOP rule:** if the merged #259 order, step numbers or side-effect profile differ materially from G-1/G-2 as written, the implementer stops and returns to the user; it does not redesign.

## Open Questions for User

- [x] **Q1. The six ideas match the issue?** Resolved 2026-11-05: Alternatives now has one row per issue idea, numbered as the issue numbers them.
- [x] **Q2. Cut-over criterion** (recorded in the follow-up). Answered 2026-11-05: accepted the recommendation. At least 20 real main sessions over at least 7 days, in at least 2 projects; zero unexplained `shadow-more-closed`; the transcript path's p95 `shadow_ms` no more than the old per-turn cost of the reset and tracker starts, amortised over the median calls per turn. Read on report counts that are lower bounds (Measurement log).
- [x] **Q3. "Without a manual step."** Answered 2026-11-05: accepted the recommendation. Re-running `/auto-improve-codegraph-install` upgrades in place through its confirm-first preview (released copy backed up and replaced); no uninstall, no hand edit, no silent update on plugin update. Criterion 5 holds under this reading.
- [x] **Q4. Shadow on for every install.** Answered 2026-11-05: accepted the recommendation (yes).
- [x] **Q5. Idea 3: never block a Read of one named source file at the cut-over?** Answered 2026-11-05: accepted the recommendation. Yes at the cut-over, if over the Q2 sample more than 50% of Read-of-source blocks are followed by an identical retry within the same turn (same `session`, `fp` and `prompt_key`; the report prints this rate per `tool`). Grep and Glob stay gated; nothing changes live in this contract.

## Critique

**Round 1** (3 BLOCKER, 5 WARN, 6 NIT; all BLOCKER and WARN addressed by the architect, user approved 2026-11-05) was moved to `.claude/contract-history/2026-11-05-codegraph-hooks-redesign.round-1.md`.

### Round 2

**Critic:** contract-critic (fresh reviewer)
**Date:** 2026-11-05

**Round-1 resolutions checked against the body.** All eight round-1 items are fixed in the body: Alternatives rows 3, 5 and 6; G-1; G-2; the log path from `CLAUDE_PROJECT_DIR` alone; the cursor `os.replace`; the advisor listed as not reused; the bench with and without the shadow; Preconditions on blocks 2-5; the stub's outcome name; the Lessons title. The findings below are new, or are gaps the revision opened.

#### Findings

- **[WARN] G-2's list of effects leaves out #259 writes and output, so "the Live plan reads only" and S-3's byte-identity test are not well defined**
  - **What is wrong:** G-2 lists the live effects as "ticket delete or write, notice flags, `log_event`". Under #259 the guard also writes `availability.json` (#259 contract `:50`, "The server verdict is computed once per session"). It creates the Session folder lazily, and step 0 must find out whether the folder is "unwritable" (`:47`, `:74`). It also prints a stderr line on every `fail-open:*` and `retry-escape-used` allow (`:67`, `:101-102`). None of these is placed in plan or in effects. S-1's shadow is "the same planner", so it would recompute and write `availability.json` too. Block 2's oracle, "the Session folder is byte-identical to a run without it", cannot pass as written. The ticket `ts` and `checked_at` differ between two runs, and the shadow's own `transcript-cursor.json` exists only in the run where the shadow does not raise. The plan/apply split also turns #259's "consumed by the first identical call" (`:29`) into check-then-act. The contract does not say what the apply step does when the ticket is already gone.
  - **Prior artifact ignored:** #259 contract `.claude/worktrees/20261105-bug-259-codegraph-guard-fail-open/.claude/concepts/2026-11-05-codegraph-guard-fail-open.md:29, 47, 50, 67, 74, 101-102`; JOURNAL `2026-11-02 — A rule titled 'every' must list every line it covers`; JOURNAL `2026-11-02 — A revision that adds a path adds its failure modes`.
  - **Where in this contract:** `### Guard order (invariants)` G-2: "(1) the Live plan: reads only ... (3) the Live plan's effects (#259 ticket delete or write, notice flags, `log_event`)"; block 2 CONSTRAINTS: "exit code, stdout, stderr and the Session folder are byte-identical to a run without it".
  - → Revised by architect: G-2 now places every #259 effect in plan (step-0 folder creation and writability check) or apply (availability.json, ticket, flags, log_event, stderr, exit); a ticket gone at apply keeps the planned allow; S-1 reuses the plan's verdicts; the oracle ignores ticket `ts`, `checked_at` and the cursor files.
  - → Addressed by: the user approved the architect's revision on 2026-11-05.
- **[WARN] The shadow can still change the exit code, through time: S-3 bounds bytes and exceptions but not duration**
  - **What is wrong:** the Read limits cap bytes, but nothing requires a regular-file check on `transcript_path` before `open()` (a FIFO or device blocks) or a wall-clock budget (a slow, network or synced profile folder). If the guard is killed at the host's hook timeout, a live `block` (exit 2) never reaches `block()`, so the call is not blocked. S-3's "cannot change behaviour" then fails on exactly the path it claims to cover. The shadow sits before the effects (G-2), so the effects wait for it on every call.
  - **Prior artifact ignored:** JOURNAL `2026-10-04 — Check a documented guard behaviour against the guard's code` (the claim "cannot change behaviour" must hold for the guard's real exits); JOURNAL `2026-10-28 — State the real trigger of a hook, not the printing condition` (the cost runs on every call, blocks included).
  - **Where in this contract:** `S-3`: "Exit code, stdout, stderr and Session-folder effects are byte-identical with the shadow forced to raise"; `### Value Objects` Read limits: "Cost bound."
  - → Revised by architect: regular-file check before `open()` and a 50 ms Shadow time budget (`unknown:time-exceeded`, live proceeds); the host's timeout behaviour is an Uncertain Assumption and block 1 point (f).
  - → Addressed by: the user approved the architect's revision on 2026-11-05.
- **[WARN] The Read limits contradict each other, and one long transcript line freezes the cursor for the session**
  - **What is wrong:** a cold scan seeks to `size - 4 MB` but reads "at most 2 MB of new bytes per call". So it parses only `[size-4MB, size-2MB]` and returns a definite `open` or `closed` from bytes that are 2 MB old. The same happens on a warm call after more than 2 MB is appended. "A limit hit without a boundary yields `unknown:window-exceeded`" covers only the case with no boundary; a limit hit that does find a boundary yields a stale answer, which produces spurious `shadow-more-closed` records. Q2 requires zero of those. Also, "parse only complete lines (a partial last line waits)" never advances `scanned_to` past a single JSONL line longer than 2 MB, for example a large tool result or an image. Every later call re-reads the same 2 MB and returns `unknown` for the rest of the session.
  - **Prior artifact ignored:** JOURNAL `2026-10-05 — A size budget must bound the summary it adds, not only the items it keeps` (the bound must hold for the output it produces, here the state); the contract's own Q2 zero-unexplained criterion.
  - **Where in this contract:** `### Value Objects` Read limits: "seek to `scanned_to`, or to `size - 4 MB` on a cold scan ... read at most 2 MB of new bytes per call; parse only complete lines (a partial last line waits)".
  - → Revised by architect: the cold window equals the 2 MB per-call limit; a hit limit always answers `window-exceeded`, boundary or not; a line over 2 MB is skipped (cursor `skipping`) and counted in `skipped_long_line`.
  - → Addressed by: the user approved the architect's revision on 2026-11-05.
- **[WARN] The shadow writes into the Session folder without honouring #259's link and unusable-folder rule, and its temp file blocks #259's pruner**
  - **What is wrong:** #259 says the hooks "never read or write the folder" when it is a link or junction, not a folder, or foreign-owned (step 0). The cursor invariant does not inherit that rule, so the shadow can `os.replace` a file through a planted junction even on a call where live step 0 failed open. Separately, a crash, kill or Windows sharing violation between the temp write and `os.replace` leaves a temp file whose name is not on the pruner's list. #259's Folder test skips, and never deletes, any folder that holds "anything other than" the known names, so that Session folder is never pruned. Extension Points adds only `transcript-cursor.json`, "nothing else". `turn_marker` in the record is also undefined when step 0 allows before the marker is read.
  - **Prior artifact ignored:** #259 contract `:47` (Session folder invariant), `:74` (step 0), `:88-92` (I-5 Folder test, known names); `MECHANISMS.md:64` (Preview-hash apply, the temp-file write being reused).
  - **Where in this contract:** `### Entities` Transcript cursor: "as a temp file in the same folder then `os.replace`"; `## Extension Points`: "`transcript-cursor.json` added to the pruner's known names; nothing else".
  - → Revised by architect: the cursor inherits #259's step-0 folder rule; the temp file is `transcript-cursor.<pid>.tmp` and `transcript-cursor.<digits>.tmp` is a pruner known name; `turn_marker` is `null` on a step-0 allow.
  - → Addressed by: the user approved the architect's revision on 2026-11-05.
- **[WARN] The concurrent-append invariant assumes POSIX append semantics on a Windows-first project**
  - **What is wrong:** "one `os.write` per line on a file opened for append" is atomic with respect to the file end on POSIX. On Windows, `os.open` goes through the C runtime, whose append mode seeks to the end and then writes. Two guard processes started for parallel tool calls can therefore overwrite each other's record without leaving a malformed line, so the report cannot count the loss. The contract tolerates only "torn lines and extra `log-full` lines". The existing appender `_error_log.py:130` (buffered `open("a")`) gives no precedent either way. This is not listed under Uncertain Assumptions, and block 2's two-process test can pass by timing.
  - **Prior artifact ignored:** `.claude/hooks/_error_log.py:130`; JOURNAL `2026-11-02 — A revision that adds a path adds its failure modes`.
  - **Where in this contract:** `### Entities` Measurement log: "Append-only: one `os.write` per line on a file opened for append ... the report tolerates both."
  - → Revised by architect: an Uncertain Assumption; the shadow never waits on a lock and every report count is a lower bound (Measurement log, Shadow report, Q2); block 2's two-process test asserts only interleaving-independent properties.
  - → Addressed by: the user approved the architect's revision on 2026-11-05.
- **[WARN] #259 dependency: no stop rule if the merged order differs, and G-1 covers only the pre-#259 module names**
  - **What is wrong:** G-1 ("0, 2, 1, 3-7"), S-1 ("Steps 6-7") and the claim "Steps 1 and 2 both allow with no side effect and no output" are written against #259's unmerged text (#259 is still OPEN, and its guard in the sibling worktree is still the pre-#259 file: `decide` at `:325`, `main` at `:460`, no ticket code). The Failure Mode says only that block 2 "re-reads the merged order". It says nothing about what block 2 does if the order, the step numbers or the side-effect profile differ. An implementer may not redesign the data shapes, so this is a hidden decision. G-1 also names only `log_event`, `_pp` and `_pp_checkout_equivalent_path` as module-level names to keep. #259 adds getattr-bound `worktree_own_root`, `tree_kind` and `main_checkout_root` with an inline-walk parity test, and its `load_hook` patches "both the marker and availability" in `test_codegraph_first_guard.py`. So it is not established that lazy binding leaves those in-process rows unedited.
  - **Prior artifact ignored:** JOURNAL `2026-11-01 — After merging a base that changes the row shape a feature reads, re-check every coverage claim and round-trip test against the merged writer`; #259 contract `:61` (getattr bindings), `:522-523` (parity tests), `:553` (`load_hook` patches).
  - **Where in this contract:** `## Failure Modes & Mitigations`: "#259 changes shape before merging. Preconditions; block 2 re-reads the merged order before writing G-1/G-2."; G-1: "The module-level names (`log_event`, `_pp`, `_pp_checkout_equivalent_path`) keep their meaning".
  - → Revised by architect: a STOP rule in block 2 and the Failure Modes; G-1 now names the getattr-bound helpers and the `load_hook`-patched names, and block 2 checks those in-process rows pass unedited.
  - → Addressed by: the user approved the architect's revision on 2026-11-05.
- **[WARN] "The three suites unedited" has no named reference point, and block 5's diff baseline predates #259**
  - **What is wrong:** #259 edits all three suites (#259 Files to touch `:465-467`). Block 5 item (5) says "diff them against the parent branch's base". The parent branch's base is `3f795ae` (Business Concept), which predates #259, so the verdict-bearing review would report #259's own edits as violations. Neither G-1, block 2 nor block 5 names the intended baseline: the suites as they stand on master after the #259 merge.
  - **Prior artifact ignored:** #259 contract `:465-467, 531-553` (the tests #259 changes); JOURNAL `2026-11-02 — Name the tests a fix may change by the state they guard, after reading them`.
  - **Where in this contract:** block 5 CONSTRAINTS (5): "the three existing suites pass and are unedited (diff them against the parent branch's base)".
  - → Revised by architect: "Baseline suites" is defined in Business Concept as the three suites on master after #259 merges and used everywhere; block 5 diffs against it.
  - → Addressed by: the user approved the architect's revision on 2026-11-05.
- **[WARN] S-4 contradicts S-1 and S-2 on where a subagent call is allowed**
  - **What is wrong:** S-1 and S-2 put the transcript state first, and `unknown:*` counts as `open`, so the shadow allows `unknown:subagent` at its step-2 position and never reaches step 3. Live may also allow earlier, at step 0 or at step 2: a subagent shares its parent's Session folder (#259 `:47`), so the parent's marker opens it. "Both decisions allow at step 3" is therefore false for both. As a result `shadow_reason` merges subagent calls with open turns in the report's reason counts.
  - **Prior artifact ignored:** #259 contract `:47, 76-77`; JOURNAL `2026-11-02 — Edit a reversed sentence where it stands`.
  - **Where in this contract:** `S-4`: "Both decisions allow at step 3."
  - → Revised by architect: S-4 rewritten where it stands (shadow allows at its step-2 position with `transcript-unknown`; live at step 0, 2 or 3); the report splits reason counts by `agent`.
  - → Addressed by: the user approved the architect's revision on 2026-11-05.
- **[NIT] Budget: the file is about 51 KB, about 12.8k tokens at four characters per token, over the 12,000 line before this round.** The template's rule (`.claude/templates/concept-contract.md:22`) is that "every superseded critique round moves out of the contract to `.claude/contract-history/<slug>.round-<n>.md`". Round 1 (its Findings, Applicable journal entries, criteria map and "did not check", about 12 KB) is superseded by the revision and is the section the rule names. Q1 is already one line. Nothing else is superseded.
- **[NIT] Q5 is a genuine policy choice with one recommendation, but the recommendation is conditional and unquantified ("most Read blocks are followed by a retry"), and the follow-up stub drops the condition** — stub `:37`: "enforce if the parent's Q5 is answered yes". Q2 quantifies its threshold; Q5 does not.
- **[NIT] Block 2's G-1 test ("a source Read leaves _project_paths unimported") names no way to observe it.** In-process, the harness already imports `_project_paths` (`test_worktree_path_guards.py:77`). In a subprocess, no seam is allowed ("No environment variable is added").
- **[NIT] Block 4 adds "the folded hashes of the #259 versions"** without saying it means every released version up to the #261 landing, which matters if a #259 patch release ships first.

#### Brief acceptance criteria → blocks (round 2)

- 1 six ideas with evidence: Alternatives rows 1-6. Met.
- 2 shadow first, removal later: block 2; follow-up stub. Met.
- 3 every failure path allows (incl. `agent_id`): S-3, S-4, block 2 tests, block 5 (1). Met, subject to the WARNs on time (S-3) and on S-4's wording.
- 4 three suites unchanged, new tests, corrupt transcript: blocks 2, 4, 5. Met, but the baseline is unnamed (WARN).
- 5 upgrade without a manual step, `released_sha256`: block 4, conditional on Q3.
- 6 cost per gated call, old and new, recorded: block 3 (artefact plus the pull request table). Met.
- 7 reason counts and blocks followed by a retry: blocks 2-3 (`session` + `fp`). Met.
- 8 five open points: block 1; block 5 (9). Met.

#### Applicable journal entries (round 2)

- **2026-11-01 — After merging a base that changes the row shape a feature reads, re-check every coverage claim**: partly heeded (Preconditions; "re-read"); no stop rule, see WARN.
- **2026-11-02 — A revision that adds a path adds its failure modes**: partly heeded; the G-2 split and the Windows append path lack failure modes, see WARNs.
- **2026-11-02 — A rule titled 'every' must list every line it covers**: not met by G-2's effects list, see WARN.
- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures**: heeded. Idea 3 is not enforced, and the #612 rows still see `allow` / `block` under G-1 (the marker is patched to absent, `test_codegraph_first_guard.py:68`).
- **2026-11-02 — Edit a reversed sentence where it stands**: S-4 still reads as it did before G-1 and S-2 existed, see WARN.

#### What the critic did not check

- #259's implementation: the sibling worktree's guard is still the pre-#259 file. Every #259 claim above rests on the #259 contract text.
- Whether Claude Code's hook timeout turns a killed PreToolUse hook into "allow" in version 2.1.318. The WARN on time relies on the documented convention that non-0/2 outcomes do not block.

Round 2 verdict: clean (no BLOCKER; 8 WARN and 4 NIT left for the user)

## Lessons referenced

- **2026-10-17 — Loosening a guard rule must be checked against the guard's own test fixtures**: heeded by S-3, G-1 and the unedited suites; idea 3 is not enforced because `test_codegraph_first_guard.py` expects a Read of source to block.
- **2026-11-02 — Name the tests a fix may change by the state they guard, after reading them**: heeded; no block lists the three suites, and the follow-up names them.
- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** and **2026-10-05 — Count a host's size cap the way the host counts, and prove the cap with a real trial**: heeded by block 1, before any code.
- **2026-10-04 — Check a documented guard behaviour against the guard's code**: heeded; the advisor read is no longer cited as bounded.
- **2026-10-05 — A documented "missing file means the default" must read one named location only**: heeded by the log and report locations.
- **2026-10-05 — Neutralise every field echoed from untrusted input, not only the body**: heeded; transcript content never reaches the log.
- **2026-10-28 — State the real trigger of a hook, not the printing condition**: heeded by the cost model and block 3's with/without-shadow cases.
- **2026-10-28 — Do not promote a mechanism the registry already describes as an extension seam**: heeded; the upgrade extends `released_sha256`, the shadow log is decide-at-review.
- **2026-10-22 — Describe a broken install by the rows each install age really has**: heeded by block 4.
- **2026-11-02 — A revision that adds a path adds its failure modes**: heeded for the cursor, the log, concurrent writers, the reorder and `update`.
- **2026-11-02 — After amending a contract, update every summary of the block graph**: heeded; the Precondition summary names blocks 2-5 and each carries the line.
- Orthogonal to north-stars: none active (`.claude/north-stars/` does not exist).

---

## Implementation Handoff

Five mergeable blocks on the parent branch `feature/261-codegraph-hooks-redesign`; every sub-task branch is cut from it and targets it, and one landing raises the version. No block lists a version file. `/tdd-first` applies to blocks 2-4, with no opt-out. Blocks 1 and 3 write only `**Verdict:** pass` or `**Verdict:** blocked`, never `pass-with-findings`, because each releases work on a result that must be whole.

### 1. Live checks (`python-ai-developer`)

**Depends on:** none

**Preconditions:** Claude Code CLI with a CodeGraph MCP server, in a trusted throwaway folder outside every repository

**Files to touch:**
- `.claude/reviews/2026-11-05-codegraph-hooks-redesign/t1-live-checks-python-ai-developer.md`
- `.claude/hooks/tests/fixtures/codegraph-transcripts/README.md`
- `.claude/hooks/tests/fixtures/codegraph-transcripts/capture_probe.py`
- `.claude/hooks/tests/fixtures/codegraph-transcripts/sequential-turns.jsonl`
- `.claude/hooks/tests/fixtures/codegraph-transcripts/parallel-calls.jsonl`
- `.claude/hooks/tests/fixtures/codegraph-transcripts/compaction.jsonl`
- `.claude/hooks/tests/fixtures/codegraph-transcripts/subagent.jsonl`
- `.claude/hooks/tests/fixtures/codegraph-transcripts/injected-messages.jsonl`

**Pre-written TASK block:**
```
TASK: Answer the five open points of issue #261 by live sessions, and capture sanitised transcript fixtures.
CONTEXT: contract .claude/concepts/2026-11-05-codegraph-hooks-redesign.md (Uncertain Assumptions a-e,
  Transcript entry class); #259 contract live trial for the payload keys.
FILES: see Files to touch.
CONSTRAINTS:
  - capture_probe.py is a throwaway hook for PreToolUse, PostToolUse and UserPromptSubmit that copies the payload
    and the transcript tail at each event. Run it only in the throwaway folder, never registered in this repo.
  - Scenarios: two sequential turns with a CodeGraph call in one; a CodeGraph call and a Read in one assistant
    message; /compact mid-turn; a subagent that calls CodeGraph; a turn carrying injected system text (hook
    additionalContext, a system reminder). Where you cannot start a session, ask the main session to run it, and
    record who ran each one.
  - Point (f): give the probe's PreToolUse row a 1 s timeout and sleep 3 s, on a probe that would exit 2; record
    whether Claude Code lets the call through. Recorded either way; it does not decide the verdict.
  - Fixtures: replace every text value with "x", keep every key, type and tool name. Record the Claude Code version.
  - The artefact uses the six fixed sections. "## What was checked" has one line per point (a) to (f), each VERIFIED
    (with field paths) or "unverified - covered by fail-open because ...", and states the exact human-prompt and
    codegraph-use rule block 2 implements.
  - Verdict: pass when points (a) to (e) are answered and a codegraph-use entry is readable before the next
    sequential PreToolUse. Otherwise blocked (idea 1 is infeasible; the contract is revised). Never
    pass-with-findings.
  - Also write the Gate Output beside the artefact, as the template defines.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
  contract_status: approved
```

### 2. Shadow decision and cheaper hot path in the guard (`python-ai-developer`)

**Depends on:** 1

**Preconditions:** issue #259 delivered: its pull request merged into master, and master merged into feature/261-codegraph-hooks-redesign

**Files to touch:**
- `.claude/addons/codegraph/hooks/codegraph-first-guard.py`
- `.claude/addons/codegraph/hooks/codegraph-turn-reset.py`
- `.claude/hooks/tests/test_codegraph_shadow.py`

**Pre-written TASK block:**
```
TASK: In the guard: reorder and lazy-import per G-1; split the decision into a pure Live plan and its effects per
G-2; add the shadow section between them (Transcript cursor, entry classifier per the t1 artefact, Shadow
decision S-1..S-4, Shadow record, log location and 10 MB stop). Add transcript-cursor.json to the reset hook's
pruner names.
CONTEXT: contract Data Shapes (Guard order), Failure Modes, Alternatives rows 1, 5, 6; the t1 artefact; the merged
  #259 decision order (re-read it before writing G-1/G-2).
FILES: see Files to touch.
CONSTRAINTS:
  - STOP rule: if the merged #259 order, step numbers or side-effect profile differ materially from G-1/G-2 as
    written, stop before writing code and return to the user. Do not redesign.
  - /tdd-first: write test_codegraph_shadow.py RED first. One test per path: open, closed, each unknown cause
    (incl. a non-regular transcript_path and time-exceeded), subagent, allowlisted, not-computed, cursor rescan on
    rewrite or shrink, a corrupt cursor, partial last line, true tail read (a large transcript reads at most the
    limit), a hit limit with a boundary found answers window-exceeded, a line over 2 MB is skipped and counted,
    no cursor read or write when step 0 failed open (link or junction folder), log-full, the pruner keeping the
    cursor and its temp file known, turn_marker null on a step-0 allow, and a CORRUPT transcript (fail-open).
  - G-2 tests: a matching ticket is consumed exactly once (by the live path) and the record shows
    retry-escape-used; a ticket gone at apply keeps the allow; the shadow writes no availability.json; a blocked
    call (exit 2) still writes its record; with the shadow forced to raise an Exception and a SystemExit, exit
    code, stdout and stderr are byte-identical to a run without it, and the Session folder is equal (same file
    names and contents, ignoring the ticket ts, availability.json checked_at, and transcript-cursor.json and its
    temp files), on an allowed and on a blocked call.
  - G-1 tests: with the marker present, a source Read leaves _project_paths unimported, observed in a fresh
    subprocess that loads the guard, runs it on that payload (catching SystemExit) and prints whether
    _project_paths is in sys.modules; decide() keeps its signature and effects.
  - Log tests: CLAUDE_PROJECT_DIR unset writes no record and nothing under the home folder; no path or prompt text
    in the log; the two-process test starts the writers behind a multiprocessing barrier over many rounds and
    asserts only what holds under every interleaving: the cursor parses, every line is whole or counted
    malformed by the report, and records never exceed writes. It never asserts that no record was lost.
  - Do not edit the Baseline suites (test_codegraph_first_guard.py, test_worktree_path_guards.py, test_addons.py
    on master after #259). Run all three; they pass unchanged, including the getattr parity and load_hook rows.
    Nothing new is printed. No environment variable is added.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
  contract_status: approved
```

### 3. Cost measurement (`python-ai-developer`)

**Depends on:** 1, 2

**Preconditions:** issue #259 delivered: its pull request merged into master, and master merged into feature/261-codegraph-hooks-redesign

**Files to touch:**
- `.claude/hooks/tests/bench_codegraph_guard.py`
- `.claude/scripts/codegraph_shadow_report.py`
- `.claude/scripts/tests/test_codegraph_shadow_report.py`
- `.claude/reviews/2026-11-05-codegraph-hooks-redesign/t3-cost-measurement-python-ai-developer.md`

**Pre-written TASK block:**
```
TASK: Measure the cost per call of the old and new designs, and write the read-only shadow report.
CONTEXT: contract (Shadow report, Q2, Q5, Alternatives rows 2-6).
FILES: see Files to touch.
CONSTRAINTS:
  - The bench runs each case 30 times in fresh processes, on the #259 guard (copied from master into a temp
    folder, "old") and on this branch's guard ("new"): allowlisted target; gated target with marker present;
    gated target with marker absent; and, new only, transcript open with warm and cold cursor at 1, 10 and 50 MB.
    Also a reset hook start and a tracker start. The old/new delta on the allowlisted and marker-present cases is
    the shadow's added cost (log append included) net of the G-1 saving; report it separately. p50 and p95 in ms,
    with Python version, OS and machine.
  - The report follows the Report the shadow command. Exit 2 on a missing or unreadable log. Its tests use a
    fixture log covering every outcome, a block plus retry pair, blocks per tool, session_seen, malformed lines,
    torn lines and two log-full lines.
  - The artefact (six sections) records both designs' numbers and the per-turn comparison Q2 names. Verdict: pass
    when every case was measured. Otherwise blocked. Never pass-with-findings. Copy the table into the pull request.
  - Write the Gate Output beside the artefact. Run test_plugin_manifests.py and test_plugin_text_scans.py.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
  contract_status: approved
```

### 4. Upgrade path and documentation (`python-ai-developer`)

**Depends on:** 2, 3

**Preconditions:** issue #259 delivered: its pull request merged into master, and master merged into feature/261-codegraph-hooks-redesign

**Files to touch:**
- `.claude/addons/codegraph/addon.json`
- `.claude/scripts/auto_improve_finish_install.py`
- `.claude/scripts/tests/test_auto_improve_finish_install.py`
- `skills/auto-improve-codegraph-install/SKILL.md`
- `skills/auto-improve-codegraph-uninstall/SKILL.md`
- `.claude/references/codegraph-decision-table.md`

**Pre-written TASK block:**
```
TASK: Let a project that holds an older released copy of a codegraph hook take the new one by re-running the
install skill, and document shadow mode, the report and the upgrade.
CONTEXT: contract (Upgrade the add-on in place, Reused Mechanisms, Q3).
FILES: see Files to touch.
CONSTRAINTS:
  - /tdd-first. Add to released_sha256 the folded hashes of every released #259 version of the guard and the
    reset hook up to the #261 landing (a #259 patch release included), read from master.
  - The update action sits inside the existing plan hash, takes a backup, refuses a link, and refuses an edited
    copy with addon-file-differs, naming the file and the uninstall-then-install route.
  - Tests: a released copy (updated), an edited copy (refused), an identical copy (nothing to do), a
    preview-then-changed file (changed-since-preview), a re-run (no change).
  - Docs describe the rows each install age has (JOURNAL 2026-10-22), the log path
    <project>/.claude/logs/codegraph-shadow.jsonl, the report command, and that the log is kept on uninstall.
  - Run test_addons.py unchanged.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
  contract_status: approved
```

### 5. Fail-open review (`fullstack-code-reviewer`)

**Depends on:** 1, 2, 3, 4

**Preconditions:** issue #259 delivered: its pull request merged into master, and master merged into feature/261-codegraph-hooks-redesign

**Files to touch:**
- `.claude/reviews/2026-11-05-codegraph-hooks-redesign/t5-fail-open-review-fullstack-code-reviewer.md`

**Pre-written TASK block:**
```
TASK: Review blocks 1-4 for fail-open safety and contract conformance, and write the review artefact.
CONTEXT: contract .claude/concepts/2026-11-05-codegraph-hooks-redesign.md; the t1 and t3 artefacts.
FILES: .claude/reviews/2026-11-05-codegraph-hooks-redesign/t5-fail-open-review-fullstack-code-reviewer.md
CONSTRAINTS:
  - Check by name:
    (1) every shadow failure path allows and cannot alter exit code, stdout, stderr or the Session folder (S-3);
    (2) G-2: the shadow runs after a pure Live plan and before its effects, also on blocked calls, and never
        consumes or writes a ticket or flag;
    (3) G-1: the reorder and lazy imports keep outcomes and the fallback banner;
    (4) the corrupt-transcript test exists and passes, and the read is a true tail read;
    (5) the Baseline suites pass and are unedited (diff them against master after the #259 merge, not 3f795ae);
    (6) the log holds no path or prompt text, and nothing is written when CLAUDE_PROJECT_DIR is unset;
    (7) update replaces only released hashes;
    (8) both cost numbers, and the shadow's added cost, are recorded;
    (9) each of the five live points is answered or covered by fail-open, and point (f) is recorded;
    (10) the registries carry the proposed terms if accepted.
  - Six fixed sections, the commit range base..head, and the verdict line alone, exactly one of
    "**Verdict:** pass", "**Verdict:** pass-with-findings", "**Verdict:** blocked". The file does not exist
    yet; you create it.
  - Write the Gate Output beside it, listing every Review checklist item verbatim.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-11-05-codegraph-hooks-redesign.md
  contract_status: approved
```

---

## Review checklist (filled in after implementation)

- [ ] Implementation matches Data Shapes exactly — not applicable (.claude/reviews/2026-11-05-codegraph-hooks-redesign/t1-live-checks-python-ai-developer.md)
- [x] Reused Mechanisms are actually reused (no parallel implementations introduced) — evidence: .claude/reviews/2026-11-05-codegraph-hooks-redesign/t5-fail-open-review-fullstack-code-reviewer.md
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md` — not applicable (.claude/reviews/2026-11-05-codegraph-hooks-redesign/t1-live-checks-python-ai-developer.md)
- [ ] New vocabulary terms promoted to `VOCABULARY.md` — not applicable (.claude/reviews/2026-11-05-codegraph-hooks-redesign/t1-live-checks-python-ai-developer.md)
- [ ] Integration surfaces reflected on both backend and frontend sides — not applicable (.claude/reviews/2026-11-05-codegraph-hooks-redesign/t1-live-checks-python-ai-developer.md)
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced — not applicable (.claude/reviews/2026-11-05-codegraph-hooks-redesign/t1-live-checks-python-ai-developer.md)
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface) — not applicable (.claude/reviews/2026-11-05-codegraph-hooks-redesign/t1-live-checks-python-ai-developer.md)
- [x] `Status` flipped to `implemented`
