## Test Strategy Review: 2026-11-06-session-folder-owner-and-tool-named (issue #271)

Reviewer: test-strategy-critic. Diff reviewed: uncommitted worktree `20261106-bug-271-windows-session-owner-check`.

**What I ran (Windows 11, this worktree, 2026-11-06):**
- `test_codegraph_first_guard.py`: 838 passed, 0 failed, 2 skipped (Q-3 foreign-owner, Q-9 open-mode), 93 s. Both real-leak checks passed.
- `test_worktree_path_guards.py`: 190/190, 54 s. `test_addons.py`: 33 OK, 17 s.
- `test_codegraph_session_parent_docs.py`: 14 OK. `test_installed_plugin_root.py`: 18 OK.
- Installer `-k Hop -k ToolNamed -k OlderHelper`: 12 OK. `test_plugin_manifests.py`: 191 passed.

**Mutation verdicts were reached by reading the code. I did not run them.**

**The repo has no CI test job.** `.github/workflows/` holds only `version-bump.yml`. So the suite runs only on the developer's Windows machine, and any row that is POSIX-only or root-only never runs in practice.

### Verdict on the four security claims

| Claim | Proven against the real hooks? | Notes |
|---|---|---|
| (1) A planted `turn.json` or ticket in the shared temp folder opens no gate | **Yes.** Subprocess runs with real files. TMP is set to the fixture temp folder. The planted marker is stamped and a planted ticket sits beside it. A control places the same marker under the parent and the gate opens. Q-2 also checks that the temp folder is byte-identical before and after all three hooks run. | Strong. `test_addons.py` repeats the check through a second harness. |
| (2) The pruner only touches the caller's own parent | **Yes.** The reset runs as a subprocess. An old folder in TMP survives, while an own old folder is pruned (control). A junction inside the parent that points into TMP is kept, and its target is untouched. | The foreign-owner row is root-only, so it never runs (see H1). |
| (3) Fail closed on an unusable folder | **Partly.** Windows-reachable parent problems are covered on disk: not-a-folder, link, cannot-create, unset, not-absolute, remote. Each has a control. The rows also check no retry, two records for two calls, and that subagent and no-index requests are still let through. check-failed runs in-process with a fenced `os.lstat`. | Not covered: every POSIX owner/mode branch, every session-level problem except link and not-a-folder, `unwritable`, and `session-check-failed` (H1, H2, M5). |
| (4) A Foreign marker still opens the gate and is logged once | **Yes.** Subprocess runs with three causes. Each case makes two calls and asserts exactly one record naming the cause. A stamped own marker logs nothing (control). | The stderr line and the flag-after-log ordering are not asserted (L1). |

### High

- **H1: The POSIX owner and mode checks never run on the only machine that runs the suite.** `codegraph-first-guard.py` `resolve_session_parent` (the `hasattr(os, "getuid")` branch) and `session_folder_problem` (`session-foreign-owner`). Test rows: Q-3 foreign-owner (root-only skip) and Q-9 open-mode (POSIX-only skip). There are no session-level foreign-owner rows at all.
  - **Gap:** Deleting the `st_uid != os.getuid()` check, the `st_mode & 0o077` check or `session-foreign-owner` would still pass all 838 checks on Windows. Even on a POSIX machine, foreign-owner needs root. The contract's Non-Goals rely on exactly these checks ("On POSIX the owner and mode checks still catch a planted parent").
  - **Why it matters:** A planted, open-mode or foreign-owned parent or session folder would be accepted on Linux or macOS. A regression there ships unseen.
  - **Fix:** Add in-process rows on the existing `run_inproc` seam that run on every OS:
    - `mock.patch.object(os, "getuid", create=True, return_value=1000)`
    - an `os.lstat` wrapper that returns an `os.stat_result` with `st_uid=4242` or `st_mode=0o40755`, for the fenced parent and, separately, the fenced Session folder only
    - assert `session-state-unusable` with `(foreign-owner)`, `(open-mode)` and `(session-foreign-owner)`. The tracker writes nothing and the reset prunes nothing.
    - Keep the on-disk root row as a bonus.

- **H2: `session-check-failed` (an exception on the Session folder, inside a usable parent) is untested. This is the exact bug class FM "a non-OSError exception … reaches the I-4 catch-all and allows" names.** `run_check_failed` fences `lstat_for=parent`, so `resolve_session_parent` returns `check-failed` before `session_folder_problem` ever runs.
  - **Gap:** Removing either `except Exception` in `session_folder_problem` would let a `ValueError` escape `Session.resolve()` into the `main()` catch-all, which exits 0 (allow). No row would notice.
  - **Why it matters:** A hostile Session folder could open the gate. That is the I-6 violation the contract added `check-failed` to prevent.
  - **Fix:** Add a second fence, `lstat_for=pfolder(sb, session)`, with an index and a server present. Assert exit 2, `(session-check-failed)`, `ValueError` in the message and no marker. Keep a no-index control. As a general rule, fence each verdict level separately.

### Medium

- **M1: The Windows rule that the base is never created is untested.**
  - **Gap:** Q-9 "the base folder is missing" uses `missing-a/missing-b/Local`, two missing levels. Without the `if os.name == "nt": return "cannot-create"` branch in `_create_parent`, `mkdir(base)` still fails, so the row passes either way.
  - **Fix:** Add a Windows row with `LOCALAPPDATA=<home>/AppData/LocalMissing`, whose own parent exists. Assert `(cannot-create)` and that the folder is still absent afterwards. Add the POSIX twin, where the base's parent exists, the base is created at mode 0700 and the result is usable.

- **M2: A mapped drive is shown to be remote only through a patched `realpath`.** The `rule_rows` entry is `"Z:\\x" -> \\srv\s\x`.
  - The patch looks up the exact string, so a normalisation change makes the row fail loudly. It hides no bug in the rule.
  - The ASSUMED CPython behaviour (a mapped drive's `realpath` returns the UNC form) is never observed. The contract's "a separate row records (not asserts) the real behaviour when `net use` shows a mapped drive" is missing, so the suite is weaker than the contract here.
  - The on-disk `remote` row uses a literal UNC path, which `_own_spellings` never resolves, so only the written-form arm is exercised on disk.
  - **Fix:** Add the recording row. Find any drive whose `GetDriveTypeW` is `DRIVE_REMOTE` (or parse `net use`), print `os.path.realpath(<drive>:\\)`, and skip with a reason when there is none.

- **M3: `names_problem` is too loose to tell one diagnosis from another.**
  - It accepts the token, OR the plain-word form (`link`, `remote`, `unset`, `not a folder`) anywhere in stderr, OR the token anywhere in any block record of the project.
  - For `session-link` the fallback is just "link". So a guard that misdiagnosed the session link as a parent `(link)` passes the step-2 row. The link-swap row passes the same way.
  - The step-2 "plain FILE" row's log assertion uses `any(...)` over the same `project` the link row already logged `session-state-unusable` into, so it passes on the link row's record.
  - **Fix:** The guard prints `(<token>)` verbatim (`unusable_lines`). Assert `"(%s)" % token in stderr`, assert the record's problem field exactly, and give each row its own project or compare record counts.

- **M4: The docs tests prove E1/E2 are present once per file, not at every site; several of their asserts are brittle.** `test_codegraph_session_parent_docs.py`.
  - **Gap:** `assertHas(INSTALL_SKILL, E1_HEAD)` passes with one occurrence. The contract requires E1 at install `:78/:156/:209`, README `:316-318` and `:569-572`, the decision table, `MECHANISMS.md:106` and `VOCABULARY.md:124`. E1_TAIL is checked only in the install skill. E1 and E2 are not checked at all in MECHANISMS or VOCABULARY. Deleting E1 from two of three install sites passes.
  - **Brittle:** whole-sentence `assertHas` on new prose, for example "An unusable session folder blocks (`session-state-unusable`), says why and how to fix it." and "unless its session folder cannot be used, when it blocks and says why". These break on harmless rewording and protect nothing behavioural.
  - **Valuable, keep:** the `assertLacks` rows and `TestShippedCodeCarriesNoRemovedNames`, which guard against a false sentence or a removed name coming back. E1 and E2 are contract-fixed text, so pinning them exactly is fair.
  - **Fix:** Replace the presence checks with an invariant: in each shipped file, every sentence matching `repeat (the blocked|this exact) call once` is followed within N characters by E1_HEAD, and every `once per session per reason` is followed by E2. Drop the exact-prose `assertHas` on non-contract sentences, or reduce each to its load-bearing token (`session-state-unusable`).

- **M5: `unwritable` and `session-unwritable` have no row, and on Windows they are probably unreachable.**
  - CPython's Windows `os.access(dir, W_OK)` ignores the read-only attribute on directories, so a parent the user's ACL denies passes as usable. Every block then lands on `retry-ticket-unwritten`, whose message says "a passing lock or a full disk". That is the wrong diagnosis, and no test shows it.
  - **Fix:** On POSIX (and in-process via the H1 seam), add a `chmod 0o500` parent row expecting `(unwritable)`. On Windows, record the behaviour of a deny-write ACL parent, or state in the contract that `unwritable` is POSIX-only and lands on I-7b on Windows. Escalate the wording question to the user; do not decide it in tests.

### Low / Nit

- **L1:** Q-4 asserts neither the Foreign-marker stderr line (the Events row says "one stderr line") nor that the `logged-foreign-marker` flag is created only after `log_event` did not return False (2026-11-05 addendum 6).
- **L2:** The Stateless session's "no filesystem call" is shown only as "nothing written through a link" (Q-announce, Q-9 link). A stray `lstat` or `mkdir` that fails harmlessly would pass. This is acceptable for the security claim, which is about writes.
- **L3: Leak checks.**
  - `real_parent_codegraph_entries()` diffs only prefixed names. It would miss a run that creates `REAL_PARENT` itself, or a `.tmp-*` or non-prefixed entry in it.
  - Both real-folder snapshots and `INPROC_LEAKS` (the `errors.jsonl` size compare) can false-fail when a live Claude session on the same machine starts or logs during the 93 s run. That makes them flaky, though it hides nothing.
  - Leaks I checked and found clean: `tempfile.tempdir` pinned in-process, `LOG_DIR` redirected, every sandbox removed (checked by the suite), `mkdtemp`+`addCleanup` in `test_addons.py`.
- **L4:** The `released_sha256` 0.15.2 row in `test_plugin_manifests.py` prints `SKIP` outside the suite's counted skip tally, so a shallow clone hides it from the reported skip count.
- **L5:** `Q-parity` over `session_parent_base` largely duplicates the per-hook literal table, which already pins each hook. It is cheap, so keep it. The AST `gettempdir()` call check is a good structural guard.

### Recommended test-suite shape

Keep every subprocess row for claims 1, 2 and 4 as they are: real hooks, real files, each with a control. Change the rest:
1. Add one in-process "verdict-level matrix" on `run_inproc`. Rows: {parent, Session folder} × {foreign-owner, open-mode (parent only), unwritable, check-failed}, with an injected `os.getuid` and a per-path `lstat` stat override. It runs on every OS.
2. Add the two `cannot-create` boundary rows (Windows: base missing, parent present; POSIX: one-level create).
3. Add one recorded, non-asserting mapped-drive row.
4. Tighten `names_problem` to `(<token>)` plus the exact record field.
5. Rewrite the doc tests as per-site E1/E2 invariants plus the existing `assertLacks` guards.

### Verdict

**NEEDS FIXES.** Claims 1, 2 and 4 are proven against the real hooks. Claim 3 is not: the POSIX owner/mode branch never runs, and the session-level `check-failed` path that guards the I-4 catch-all has no test.
