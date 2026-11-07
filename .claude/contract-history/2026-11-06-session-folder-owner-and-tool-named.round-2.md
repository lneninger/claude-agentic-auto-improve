## Critique (pass 2)

**Critic:** contract-critic
**Date:** 2026-11-06
**Verdict:** blockers-found

This is a fresh review of Revision 1. I checked it against the guard (`codegraph-first-guard.py:60-84, 200-355, 360-407, 498-623, 781-1004`), `_claude_paths.py:170-236`, `_addon_fixture.py:391-537`, the test files, README `:304-325, 564-575`, install `SKILL.md:73-78, 156-209`, `MECHANISMS.md:43-45, 59, 106-107` and JOURNAL.

**Round-1 status:**
- Resolved: I-4/I-6 scope; the old-helper pair (the Hop proof); the POSIX base purity; `announce()` writes; the three leak checks; all four NITs.
- Partly resolved: the shipped-text BLOCKER (the new reason re-opens it; see the BLOCKER below); `remote` (see the `_own_spellings` WARN); the ticket write (see the OS-error-text WARN).

### Findings

- **[BLOCKER] The revision's own new behaviours make shipped text false, and the edit list does not cover them**
  - **What is wrong:** two sentences stay false after the edits.
    - **"Repeat the blocked call once and it is allowed."** After `retry-ticket-unwritten`, no ticket exists. The repeat writes the ticket and blocks again (`source-target`), so only the third call is allowed, and none is if the write keeps failing. Every "repeat once" sentence gains an exception for `session-state-unusable` only: install `SKILL.md:78, 156, 209`; README `:316-318, 569-572`; decision table `:128-131`. The guard's own banner (`block()`, `:918-919`: "repeat this exact call once; it will be allowed and logged") is printed for every block reason. I-7b never says the banner drops that line for this reason, and the TASK row asserts only "no LOCALAPPDATA/chmod text". `MECHANISMS.md:106`'s ways-out span "repeat the blocked call once" is not in the registry span list at all, not even for `session-state-unusable`.
    - **"Every allow is logged."** Step 2 says an unusable-state allow "writes NO log record". README `:308-309` ("logged once per session per reason in `errors.jsonl`"), install `SKILL.md:78` ("prints one … line and logs it") and `MECHANISMS.md:106` ("one log record per session per reason") still say every fail-open allow is logged. None of these spans is in Extension Points.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "Check a documented guard behaviour against the guard's code"; `JOURNAL.md` 2026-11-02 "Edit a reversed sentence where it stands"; `JOURNAL.md` 2026-11-02 "A rule titled 'every' must list every line it covers".
  - **Where in this contract:** `## Extension Points`, "`:156` and `:209`: after the retry escape, add '(not when the block says `session-state-unusable`)'"; `### Guard decision order` step 2, "writes NO log record"; I-7b.

- **[WARN] The `check-failed` test row cannot pass under the decision order it tests**
  - **What is wrong:** the row says "`os.lstat` patched to raise `ValueError` -> guard blocks". With an unusable verdict, step 2 still runs steps 4-6. `_has_project_index` (`:360-371`) catches `ValueError` and returns False, so `index_verdict` (`:508-509`) gives `no-index`, and the guard allows `fail-open:no-index` instead of blocking. A process-wide patch also changes the index probe, not only the verdict function.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case" (a row must exercise the state it claims); `JOURNAL.md` 2026-11-02 "Name the tests a fix may change by the state they guard, after reading them".
  - **Where in this contract:** TASK block, "check-failed: os.lstat patched to raise ValueError -> guard blocks (not the catch-all allow)"; `## Failure Modes`, the non-OSError FM.

- **[WARN] I-7b and its Event need "the OS error text", but the write path returns only a bool**
  - **What is wrong:** `Session.write` → `_atomic_write` (`:262-281`) catches `OSError` and returns `False`. `ensure_folder` (`:308-316`) does the same, so no error text reaches step 8. The contract declares no change to either shape, but the I-7b message and the `GuardBlockedOnTicketWrite` payload both require the text.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 "A path that calls a command must say how it finds the command's input".
  - **Where in this contract:** I-7b, "names the Session folder and the OS error text"; `### Events`, GuardBlockedOnTicketWrite payload "OS error text".

- **[WARN] The Remote rule's "written, then realpath" order is `_own_spellings`, a fifth pinned copy the contract does not name**
  - **What is wrong:** the order the contract cites (`:407`) is `_own_spellings`, not `_remote_host`. `_own_spellings` exists as four copies pinned by its own W-14 row (`test_codegraph_first_guard.py:1851`). The tracker and the reset hook are told to copy only `_remote_host`, and the parity row grows only for `_remote_host`. So their realpath step is either an unpinned fifth and sixth `_own_spellings` or a new inline variant.
  - **Prior artifact ignored:** `MECHANISMS.md:45` (the copies "pinned by a parity row"); `.claude/reviews/2026-11-05-codegraph-guard-fail-open/review-fullstack-code-reviewer-pass4.md:107` ("`_own_spellings` is identical in the four copies but not pinned (N1)").
  - **Where in this contract:** `### Value Objects`, Remote rule; `## Reused Mechanisms`, "the W-14 parity row grows from four copies to six"; TASK block, "W-14 covers six _remote_host copies".

- **[WARN] Registry spans that this change makes false are missing from the span list**
  - **What is wrong:** three `MECHANISMS.md` statements become false and none is listed.
    - `MECHANISMS.md:43`: "It also exports `WORKTREE_OWN_ROOT_NATIVE` … the installer reads it". The contract removes it.
    - `MECHANISMS.md:45`: "the guard binds the two functions only from a helper that carries `_hop_allowed`". It becomes the Hop proof.
    - `MECHANISMS.md:45`: "`_remote_host` / `_hop_allowed` exist as four textual copies". `_remote_host` becomes six.
  - The re-grep list (`state-unwritable`, `temp folder`, `nudge` …) would catch none of these three.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 "Edit a reversed sentence where it stands"; the `MECHANISMS.md:107` in-place-correction precedent that the contract itself cites.
  - **Where in this contract:** `## Extension Points`, "Registries (written at review)", which lists `MECHANISMS.md:106` and `:107` only.

- **[WARN] The isolation mitigation names a helper that does not exist and omits the one the guard suite uses**
  - **What is wrong:** `run_hook_process` exists in no file under `.claude/` except two contracts. The guard suite and `_addon_fixture` isolate through `af.isolated_env` (`_addon_fixture.py:531-537`; used at `test_codegraph_first_guard.py:150, 312, 1367`), which sets only HOME, USERPROFILE, TMP, TEMP and TMPDIR, and the contract never names it. Two fixture helpers also keep the old shape, and neither is listed:
    - `af.session_folder(temp, …)` (`:511-513`) roots the Session folder at the temp folder.
    - `af.write_marker` (`:516-522`) writes an unstamped `{ts, tool, summary, pid}`. Every existing marker row (`test_worktree_path_guards.py:1180-1303`, guard `:608`) therefore becomes a Foreign-marker row and gains a `foreign-marker` record. The criterion-4 "stamped own marker" control needs a stamped writer the fixture lacks.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 "Name the tests a fix may change by the state they guard, after reading them"; `JOURNAL.md` 2026-10-17 "Loosening a guard rule must be checked against the guard's own test fixtures".
  - **Where in this contract:** `## Failure Modes`, first FM, "`codegraph_env()`, `run_hook_process` and `clean_env` set …"; TASK block, "Isolation: codegraph_env(), clean_env and run_hook_process".

- **[NIT] Round 1 stays inside the contract.** Template `.claude/templates/concept-contract.md:22` moves every superseded critique round to `.claude/contract-history/<slug>.round-<n>.md` (precedent: `2026-11-05-codegraph-guard-fail-open.round-1.md` … `round-4.md`). At four characters per token, the body above `## Critique` looks larger than its 12,000-token budget. I estimated this and did not measure it.
- **[NIT] The bridge's `TREE_HOP_REFUSAL` shares the helper constant's name but not its meaning.** In the bridge it is the computed Hop proof, so it is True for a 0.15.2 helper that has no such constant. It tells native from inline, not "which helper it got", which is what `### Value Objects` claims. The constant also never decides a verdict today, because every helper that carries it also satisfies the second arm (`## Uncertain Assumptions`, `:581`/`:688` VERIFIED bullet).
- **[NIT] An empty host from `_remote_host` is not classified.** `_remote_host` returns `""` for `\\?\Volume{…}\` or `\\.\pipe\…` (`:386`). "A host that is not the local-drive form" leaves open whether `""` counts as remote.
- **[NIT] I-7b's "never names a link" can misdiagnose.** `Session.write` re-runs `folder_usable` (`:329, 316`). A folder that becomes a link between step 2 and step 8 gives `retry-ticket-unwritten`, and its message blames a lock or a full disk.
- **[NIT] In the unusable state, `server_verdict` and `index_verdict` run on every Read, Grep and Glob, because no availability cache can be kept.** The per-call cost is not stated. `JOURNAL.md` 2026-10-28 "State the real trigger of a hook, not the printing condition".
- **[NIT] The docstring and test-comment lists are incomplete, though the re-grep would catch the gaps.** Missing: tracker `:46`, reset `:10`, `test_addons.py:21`, `test_codegraph_first_guard.py:14, 30, 1342, 1533, 2206`, `test_worktree_path_guards.py:368, 392, 403, 408`, `_addon_fixture.py:512, 533`.

### Applicable journal entries

- **2026-10-04 — Check a documented guard behaviour against the guard's code**: violated for `retry-ticket-unwritten` and the unlogged unusable-state allows (BLOCKER).
- **2026-11-02 — Edit a reversed sentence where it stands**: heeded for the round-1 list; violated for `MECHANISMS.md:43, 45, 106` ways-out and the logging sentences (BLOCKER, WARN).
- **2026-11-02 — A rule titled 'every' must list every line it covers**: violated; the "logged once per session per reason" sentences are not amended (BLOCKER).
- **2026-11-02 — Name the tests a fix may change by the state they guard**: heeded for `:488-535` and the leak checks; violated for `isolated_env`, `session_folder`, `write_marker` and the `check-failed` row (WARN).
- **2026-11-02 — A path that calls a command must say how it finds the command's input**: violated for the OS error text (WARN).
- **2026-11-05 — A same-host path rule must compare against both the written and the realpath form**: heeded in substance; the `_own_spellings` copies are unpinned (WARN).
- **2026-10-22 — Describe a broken install by the rows each install age really has**: heeded by the Hop proof's 0.15.2 arm, Option E, the FM and the README row.
- **2026-11-05 — A bridge re-export … must say which one it gave**: heeded, with the naming NIT above.
- **2026-11-05 — An "older release" test fixture must be pinned to a fixed commit**: heeded (`e4f392c`, `643b667`, `git cat-file -e`, skip, never HEAD).
- **2026-11-05 — A hardening fix applied to a shared classifier must be checked against every consumer**: heeded; `_git_file_kind` gets a comment only.
- **2026-10-05 — A documented "missing file means the default" must read one named location only**: heeded; the mapping-only Parent base rule.
- **2026-11-02 — A revision that adds a path adds its failure modes**: heeded; the catch-all, the ticket write, the old helper and `announce()` each have an FM.
- **2026-10-28 — Guard messages must use names the guard emits**: heeded by I-7 and I-7b, apart from the shared banner line (BLOCKER).
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out**: heeded by I-7 and I-7b.
- **2026-10-17 — Git for Windows lists files beneath an untracked junction**: heeded by I-9 and the folder-link rows.
- **2026-10-22 — An accepted critic WARN … must amend the contract body before approval**: heeded; the round-1 findings are in the body.

### What the critic did not check

- Not run (no shell): `derive_area.py` / `cross_area_scan.py`, `pr_merged.py --contract … --status --json`, `git cat-file -e e4f392c` / `643b667`, any test, or a token count. Delivery has one block and the brief header is present, so item 14 raises nothing.
- No CodeGraph tool was available. I checked symbols with Read and Grep on the hook, bridge, fixture and test files.
- No north-star check: `.claude/north-stars/` does not exist.
