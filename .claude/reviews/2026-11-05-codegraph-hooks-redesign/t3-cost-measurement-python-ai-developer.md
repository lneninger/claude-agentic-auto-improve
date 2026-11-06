# t3 cost measurement — python-ai-developer

- **Gate agent:** python-ai-developer
- **Sub-task:** t3-cost-measurement (issue #265, parent issue #261)
- **Contract:** `.claude/concepts/2026-11-05-codegraph-hooks-redesign.md` (approved)
- **Reviewed on:** 2026-11-06
- **Commit range reviewed:** `1e024aa..` working tree (the three files named under Evidence were uncommitted when this was written; the main session commits them, so the range closes at that commit)
- **Environment:** Python 3.12.10 (CPython); Windows 11 (10.0.26300, `Windows-11-10.0.26300-SP0`); AMD64, Intel64 Family 6 Model 158 (GenuineIntel), 12 logical CPUs. A shared developer workstation, not an idle bench machine: the run-to-run spread below is the evidence of that.
- **Who ran what:** the bench was run by this sub-agent from the worktree, every hook in a fresh `python` process under a private temp folder (TMP/TEMP/TMPDIR, USERPROFILE/HOME and CLAUDE_CONFIG_DIR redirected, a throwaway project with a Project index and a configured server). The main session ran nothing and the real temp and home folders were not touched.

**Verdict:** pass

## What was checked

| Item the TASK block named | Outcome |
|---|---|
| Old guard: the #259 guard read with `git show origin/master:<path>` into a temp folder (the local `master` branch is stale and holds the pre-#259 sentinel guard, so it was not used; the bench refuses an old guard without `SESSION_PREFIX`) | measured, 30 runs per case |
| New guard: this branch's guard, copied into a second temp folder | measured, 30 runs per case |
| Allowlisted target (old, new) | measured, 30/30 exit 0 |
| Gated target, Turn marker present (old, new) | measured, 30/30 exit 0 |
| Gated target, Turn marker absent (old, new) | measured, 30/30 exit 2 (a real block) |
| New only: transcript open, warm and cold cursor, at 1, 10 and 50 MB (six cases) | measured, 30/30 exit 0; the transcript state reached was `open` on all 30 runs of each |
| Reset hook start (old, new) and tracker start (old, new) | measured, 30/30 exit 0 |
| Old/new delta on the allowlisted and marker-present cases, the shadow's added cost net of the G-1 saving, reported separately | measured: two supplemental cases run the new guard against a project with no `.claude` folder (no log is written), which splits the delta into G-1 saving and shadow added cost |
| p50 and p95 in ms, with Python version, OS and machine | in the table below |
| Per-turn comparison Q2 names | in the table below |
| `codegraph_shadow_report.py` per the "Report the shadow" command: exit 2 on a missing or unreadable log; fixture log with every outcome, a block plus retry pair, blocks per tool, `session_seen`, malformed lines, torn lines and two log-full lines | RED first (the module did not exist: `ModuleNotFoundError`), then GREEN: 31 tests, all pass |
| Gate Output beside this artefact; `test_plugin_manifests.py` and `test_plugin_text_scans.py` run | written; both run, results under Evidence |

## Findings

None.

## What was NOT checked

- **Real traffic.** The transcripts are synthetic (about 3 KB cycles of assistant text, a tool use and a parsed tool result, with a human prompt and a CodeGraph tool use placed 1 MB, or half the file, before the end). Real transcripts hold long lines, images and nested content; the share of lines the guard has to JSON-parse is a guess. The calls-per-turn figure Q2 needs is not measured here: it comes from the cut-over sample, so the per-turn table is shown for c = 5, 10, 20 and 50.
- **Reset hook on a first prompt.** That run also prunes old Session folders in the temp folder. The bench measures the steady state (the `pruned` flag already exists); the pruner's cost depends on how many folders the real temp folder holds.
- **Tracker fires once per CodeGraph call.** The old per-turn cost uses one tracker start, which is a floor, so the Q2 comparison below is the hard case for the new design.
- **A cold block (first block of a session).** The marker-absent case runs against a primed session, so the availability verdicts are cached; the uncached first call costs more in both designs.
- **A warm cursor with new bytes to read.** Warm means the cursor is current (nothing to read), which is what a call right after another call sees; a warm call after a long tool result reads the new bytes and sits between the warm and cold rows.
- **Other machines, other Python versions, POSIX.** One host, one interpreter.
- **Idle-machine precision.** Differences below the spread (see Evidence) are not resolved.

## Evidence

**Commands run.**

| Command | Exit |
|---|---|
| `py -3 .claude/scripts/tests/test_codegraph_shadow_report.py` before the script existed | 1 (`ModuleNotFoundError: No module named 'codegraph_shadow_report'`): RED |
| `py -3 .claude/scripts/tests/test_codegraph_shadow_report.py` after: `Ran 31 tests ... OK` | 0: GREEN |
| `py -3 .claude/hooks/tests/bench_codegraph_guard.py --runs 30` (run A, then run B; run B is tabled) | 0 both: every case measured |
| `py -3 .claude/hooks/tests/bench_codegraph_guard.py --runs 2 --sizes 1` after renaming the stand-in CodeGraph tool name | 0 |
| `py -3 .claude/scripts/tests/test_plugin_manifests.py` | 1: 189 passed, 1 failed (the version rule; see the note below) |
| `py -3 .claude/scripts/tests/test_plugin_text_scans.py` | 1: 18 passed, 1 failed (six files that are not this sub-task's; see the note below) |

**Note on the two failing suites.** Neither failure comes from this sub-task's files. `test_plugin_manifests.py` fails its merge-base rule because the branch changes shipped files (the t1 fixtures and the t2 guard) while all five version declarations still read 0.15.2; the caller's version bump clears it. `test_plugin_text_scans.py` fails `test_no_shipped_file_names_an_individual_codegraph_tool` on five t1 transcript fixtures (`compaction.jsonl`, `injected-messages.jsonl`, `parallel-calls.jsonl`, `sequential-turns.jsonl`, `subagent.jsonl`) and on the t2 test `test_codegraph_shadow.py`; the first run also listed this sub-task's `bench_codegraph_guard.py`, which was fixed (the stand-in tool name is now `mcp__codegraph__bench`) and no longer appears. The other 18 text-scan tests pass.

**The table (copy into the pull request).** Run B. 30 fresh-process runs per case, wall clock from the parent with interpreter start included, ms. old = `origin/master` @ 7ed832d, new = this branch @ 1e024aa. The plain guard cases carry a 64 KB transcript.

| Case | Design | Hook | Runs | p50 | p95 | in-process shadow_ms p50 / p95 | Transcript states reached | Measured |
|---|---|---|---|---|---|---|---|---|
| allowlisted target (README.md), no marker | old | guard | 30 | 129.7 | 163.4 |  |  | yes |
| gated target (src/app.py), marker present | old | guard | 30 | 128.8 | 155.9 |  |  | yes |
| gated target (src/app.py), marker absent: block | old | guard | 30 | 129.2 | 172.8 |  |  | yes |
| allowlisted target (README.md), no marker | new | guard | 30 | 124.9 | 204.2 | 0.0 / 0.0 | open 30 | yes |
| gated target (src/app.py), marker present | new | guard | 30 | 123.3 | 165.6 | 0.0 / 0.0 | open 30 | yes |
| gated target (src/app.py), marker absent: block | new | guard | 30 | 145.5 | 178.3 | 0.0 / 15.0 | open 30 | yes |
| allowlisted target (README.md), no marker | new-nolog | guard | 30 | 128.0 | 162.1 |  |  | yes |
| gated target (src/app.py), marker present | new-nolog | guard | 30 | 120.9 | 142.8 |  |  | yes |
| marker present, transcript open, 1 MB, warm cursor | new | guard | 30 | 121.2 | 162.9 | 0.0 / 0.0 | open 30 | yes |
| marker present, transcript open, 1 MB, cold cursor | new | guard | 30 | 128.2 | 170.6 | 15.0 / 16.0 | open 30 | yes |
| marker present, transcript open, 10 MB, warm cursor | new | guard | 30 | 119.5 | 148.2 | 0.0 / 0.0 | open 30 | yes |
| marker present, transcript open, 10 MB, cold cursor | new | guard | 30 | 136.2 | 168.1 | 16.0 / 16.0 | open 30 | yes |
| marker present, transcript open, 50 MB, warm cursor | new | guard | 30 | 116.5 | 151.1 | 0.0 / 16.0 | open 30 | yes |
| marker present, transcript open, 50 MB, cold cursor | new | guard | 30 | 135.1 | 182.9 | 15.0 / 31.0 | open 30 | yes |
| reset hook start (UserPromptSubmit) | old | reset | 30 | 104.7 | 142.5 |  |  | yes |
| tracker start (PostToolUse mcp__codegraph__*) | old | tracker | 30 | 101.4 | 157.1 |  |  | yes |
| reset hook start (UserPromptSubmit) | new | reset | 30 | 103.5 | 139.5 |  |  | yes |
| tracker start (PostToolUse mcp__codegraph__*) | new | tracker | 30 | 100.3 | 127.3 |  |  | yes |
| python start, no imports (floor) | floor | python | 30 | 43.5 | 57.6 |  |  | yes |

`new-nolog` is the new guard against a project with no `.claude` folder, so no Shadow record is written; it exists only to split the delta.

**Old to new on the two common cases** (ms; p50 and p95 differenced separately, so the columns do not add exactly). Total = new - old. G-1 saving = new with no log - old (negative is a saving). Shadow added = new - new with no log (the transcript read and the log append).

| Case | Stat | old | new, no log | new | Total | G-1 saving | Shadow added |
|---|---|---|---|---|---|---|---|
| allowlisted target | p50 | 129.7 | 128.0 | 124.9 | -4.8 | -1.7 | -3.1 |
| allowlisted target | p95 | 163.4 | 162.1 | 204.2 | +40.8 | -1.3 | +42.1 |
| gated target, marker present | p50 | 128.8 | 120.9 | 123.3 | -5.5 | -7.9 | +2.3 |
| gated target, marker present | p95 | 155.9 | 142.8 | 165.6 | +9.7 | -13.2 | +22.9 |

**Per-turn comparison (Q2).** Old per-turn cost of one reset start plus one tracker start = 104.7 + 101.4 = 206.2 ms (a floor). The criterion: the transcript path's p95 `shadow_ms` is no more than that cost divided by the median guard calls per turn (c). "Process extra p50" is the case's wall-clock p50 minus new-with-no-log, marker present (120.9 ms): the finer, noisier measure.

| Transcript case | shadow_ms p95 | Process extra p50 | Max c that meets the criterion | c=5: budget / met | c=10: budget / met | c=20: budget / met | c=50: budget / met |
|---|---|---|---|---|---|---|---|
| 1 MB, warm cursor | 0.0 | +0.3 | above any c (p95 under one tick) | 41.2 / yes | 20.6 / yes | 10.3 / yes | 4.1 / yes |
| 1 MB, cold cursor | 16.0 | +7.2 | 12.9 | 41.2 / yes | 20.6 / yes | 10.3 / no | 4.1 / no |
| 10 MB, warm cursor | 0.0 | -1.5 | above any c (p95 under one tick) | 41.2 / yes | 20.6 / yes | 10.3 / yes | 4.1 / yes |
| 10 MB, cold cursor | 16.0 | +15.3 | 12.9 | 41.2 / yes | 20.6 / yes | 10.3 / no | 4.1 / no |
| 50 MB, warm cursor | 16.0 | -4.4 | 12.9 | 41.2 / yes | 20.6 / yes | 10.3 / no | 4.1 / no |
| 50 MB, cold cursor | 31.0 | +14.2 | 6.7 | 41.2 / yes | 20.6 / no | 10.3 / no | 4.1 / no |

Reading it in per-turn terms: at the cut-over the reset and tracker starts (206 ms a turn, floor) go away and each guard call pays the transcript path instead. A cold scan costs about +7 ms (1 MB) to +15 ms (10 and 50 MB) a call at p50 and happens once per session, then the cursor makes calls warm (about 0 ms extra, within noise). At c = 20 calls a turn with every call cold the cost would be about 300 ms and exceed 206 ms, but only the first call of a session is cold, so the realistic turn cost is one cold call plus warm calls, well under the 206 ms removed. The Q2 criterion on `shadow_ms` p95 alone is met up to c of about 13 for the 16 ms rows and about 6 to 7 for the 50 MB cold row, and is not met at c = 20 or 50 for any row that read bytes, because the guard's clock resolution is coarse (next point) and the budget per call shrinks as c grows. The user decides at the cut-over whether that criterion should read `shadow_ms` p95 or the process-level extra.

**Observations for the cut-over (not findings against this gate).**
- **`shadow_ms` is quantised to about 15.6 ms on this host.** The guard measures with `time.monotonic()`, which on Windows ticks at about 15.6 ms, so `shadow_ms` takes the values 0, 15, 16, 31, 32 and the 50 ms Shadow time budget is checked on the same coarse clock (it can fire up to one tick early or late). A `shadow_ms` of 0.0 means "under one tick". `time.perf_counter()` would resolve it. This is in the guard, which is outside this sub-task's files, so it is reported to the caller and not changed.
- **A cold scan of the last 2 MB took 15 to 31 ms and never reached the 50 ms budget** in 30 runs at 10 MB and at 50 MB: no `unknown:time-exceeded` appeared in any case. Every case reached `open`.
- **The deltas are inside the noise.** Run A (same code, earlier the same hour) gave, for the allowlisted target, old 130.0 / 212.1 and new 135.0 / 218.4 (p50 / p95), and for marker present old 129.8 / 233.4 and new 127.4 / 174.0. Between the two runs the same case moved by up to 5 ms at p50 and 80 ms at p95. So: the G-1 saving on the marker-present case is a few ms at p50 in run B (-7.9) and about -0.7 in run A, and the shadow's added cost at p50 is within +-3 ms in both runs; p95 differences are dominated by workstation noise. Neither run supports "the shadow adds more than a few ms at p50".
- **The blocked-call case is the slowest new row** (145.5 against 129.2 old at p50 in run B, 149.1 against 132.6 in run A): a block writes a ticket, the availability file is read and a Shadow record is appended after the transcript read. It is a real, repeatable +13 to +16 ms at p50 on the block path only.

**Files written (the only ones).** `.claude/hooks/tests/bench_codegraph_guard.py`, `.claude/scripts/codegraph_shadow_report.py`, `.claude/scripts/tests/test_codegraph_shadow_report.py`, this report and its `.gate.json`. The plugin version was not bumped and nothing was committed.

## Disposition

Nothing. This gate releases its dependents. Verdict rule: pass when every case was measured; every one of the 19 cases was (30/30 runs with the expected exit code). For the cut-over follow-up: decide whether Q2's `shadow_ms` p95 criterion should be read on `shadow_ms` or on the process-level extra, given the 15.6 ms clock tick, and consider `time.perf_counter()` for the guard's shadow timing and budget.
