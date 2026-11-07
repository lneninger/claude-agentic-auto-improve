## Critique

**Critic:** contract-critic
**Date:** 2026-11-06
**Verdict:** blockers-found

I checked the fail-closed reversal against the current guard (`codegraph-first-guard.py:285-355, 781-836, 942-1004`), `addon.json`, the two codegraph skills, README, the decision table, the four registries and the 2026-11-05 contract.

### Findings

- **[BLOCKER] Shipped text that the reversal makes false is not in Extension Points, so the docs will contradict the guard**
  - **What is wrong:** These lines state the 0.15.2 behaviour as the guard's permanent nature, and the contract does not list any of them for editing:
    - `skills/auto-improve-codegraph-install/SKILL.md:78`: "**The guard is a nudge, never a wall.** … In any other session with no CodeGraph tool, **repeat the identical blocked call once**: it is allowed". In the unusable state there is no ticket, so the retry fails.
    - `SKILL.md:183`: "The only leftover is the session folder in the system temp folder".
    - `README.md:306`: "the guard is a nudge, never a wall". `README.md:314-315` describe `state-unwritable`. The contract lists only README `320-322`.
    - `.claude/references/codegraph-decision-table.md:124`: "`state-unwritable` covers an unusable session folder". The contract lists only `:107, 113`.
    - `VOCABULARY.md:125` (CodeGraph unavailability reason): "`state-unwritable` is the sixth line". The registry Extension Point names only Investigation Turn and the two new terms.
  - **What the contract adds instead:** a "Changed in 0.15.3" note and a new skill paragraph. That leaves each old sentence standing next to text that contradicts it.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04 "Check a documented guard behaviour against the guard's code" (a guard without a bypass blocks new users, and the docs must say so). `JOURNAL.md` 2026-11-02 "Edit a reversed sentence where it stands", which `## Lessons referenced` claims is heeded. `MECHANISMS.md:106` ("a nudge, never a wall") is in the list, so the gap is only in the non-registry files and VOCABULARY:125.
  - **Where in this contract:** `## Extension Points`, "Install skill: lines 73-74 … lines 160 and 208"; "`codegraph-decision-table.md:107, 113`, `README.md:320-322`"; "`VOCABULARY.md` (Investigation Turn, plus the two new terms)".

- **[WARN] I-6 ("no state the user did not write can cause an allow") is false while the guard's catch-all still allows, and I-4 is not restated**
  - **What is wrong:** `codegraph-first-guard.py:1002-1004` turns any exception from `main()` into exit 0 ("internal error (failing open)"). The 2026-11-05 I-4 ("an internal error allows") still binds, because "Everything else in that contract stands" (header). The new parent and session checks add new code paths on state an attacker controls: `lstat` of the base and the parent, `st_file_attributes`, the owner and mode checks, `os.access`.
  - **What is not said:** the contract never says that an exception other than OSError on those paths (for example ValueError from path handling) must give `unusable:*` rather than reach the catch-all. It also has no Failure Mode for that case. The tracker (`:151-153`) and the reset hook (`:275-277`) have the same catch-all.
  - **Prior artifact ignored:** `MECHANISMS.md:59` (Guard fallback mode, "Known sharp edges: … a helper that throws makes the other three gates fail open"). `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` I-4.
  - **Where in this contract:** `### Guard decision order`, "**I-6 (fail closed):** no state the user did not write can cause an allow".

- **[WARN] In an upgraded project, the "0.15.2 helper beside the 0.15.3 guard" case is the normal state, not a rare one, so `index-other-tree` stops firing in worktrees after the upgrade**
  - **What is wrong:** The add-on copies a helper "only when the project lacks it" (`addon.json` `helpers`; install `SKILL.md:24, 76`). The uninstall "never deletes a helper" (uninstall `SKILL.md:25`). So the documented upgrade route (uninstall, install, new session) leaves the project's 0.15.2 `_project_paths.py` in place.
  - **Consequence:** that helper has `_hop_allowed` (the hop refusal the old gate `callable(_hop_allowed)` at guard `:82` tested for) but has no `TREE_HOP_REFUSAL`. Under the new gate the guard never binds `tree_kind` or `main_checkout_root`, and linked-worktree sessions go from "reads let through" (2026-11-05 Q7 a) to block-then-retry.
  - **Contradiction:** the ASSUMED bullet says "the hooks and the helper ship together". The contract's own Option D says the opposite ("an add-on copies a helper only when the project lacks it").
  - **Missing:** no Failure Mode, README upgrade row or test covers the upgraded-project pair. The `e4f392c` row only proves the constant is absent from that helper.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-22 "Describe a broken install by the rows each install age really has". `MECHANISMS.md:101` (Add-on layout: "copies each named helper only when the project lacks it").
  - **Where in this contract:** `## Uncertain Assumptions`, "`ASSUMED`: a 0.15.2 helper beside the 0.15.3 guard is rare, because the hooks and the helper ship together".

- **[WARN] The `remote` parent problem is a fifth definition of "remote path", and it disagrees with the four copies pinned by parity**
  - **What is wrong:** `_remote_host` (guard `:374-387`, plus the helper, the bridge and the installer, pinned by the W-14 parity rows) treats `\\?\C:\…` as a local drive. It also judges the realpath form, so a mapped drive (`Z:` resolving to `\\server\share`) is seen as remote.
  - **How the new rule differs:** it is "a leading pair of separators of either kind" on the written text only. So it calls a local device-form path remote, and it lets a mapped network drive through.
  - **Effect on the Non-Goal:** the Non-Goal says "On Windows the `remote` rule catches only network paths". In fact it misses the commonest network form (a mapped drive) and catches one local form.
  - **Prior artifact ignored:** `MECHANISMS.md:45` (Correction 2026-11-05: same-host judged "on both the written and the `os.path.realpath` form"; "a local drive is not remote"; four textual copies pinned by parity). `JOURNAL.md` 2026-11-05 "A same-host path rule must compare against both the written and the realpath form".
  - **Where in this contract:** `## Data Shapes → Value Objects`, Parent problem: "`remote` (Windows only: a UNC or device path, that is, a leading pair of separators of either kind)"; `## Non-Goals`, last bullet.

- **[WARN] The POSIX Parent base rule is neither pure nor single-location, so the "unset HOME" test row cannot give `unset`**
  - **Not pure:** `expanduser("~")` ignores the passed environment mapping and reads the process `os.environ`. With `HOME` unset on POSIX it falls back to the password database (`pwd.getpwuid(os.getuid())`). So with "unset HOME with no XDG_CACHE_HOME", the specified rule returns the real home, not `unset`.
  - **Cross-OS table test:** run on Windows, `expanduser` answers from `USERPROFILE`. So the table test of the POSIX branch "on every OS" depends on the host machine.
  - **Chain:** the order XDG_CACHE_HOME, then HOME, then pwd is the fallback chain the cited lesson forbids. The contract claims the lesson is heeded only for "no fallback chain on Windows".
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-05 "A documented 'missing file means the default' must read one named location only". `JOURNAL.md` 2026-10-04 "A VERIFIED parser claim must be tested on the unfilled and the missing case".
  - **Where in this contract:** `## Data Shapes → Value Objects`, Parent base: "Takes the environment mapping and the OS name … else `expanduser("~")/.cache`". TASK block, criterion 9: "POSIX: unset HOME with no XDG_CACHE_HOME".

- **[WARN] A ticket write that fails at step 7 blocks with `session-state-unusable`, but no Parent problem names that cause, so I-7 cannot give a true fix**
  - **What is wrong:** I-7 requires "the problem in plain words, and the fix for that problem". A step-7 write fails inside a folder that passed step 0. On Windows the usual causes are an antivirus or indexer lock on `os.replace`, or a full disk.
  - **Missing:** the closed set has no transient cause. The only near fit is `unwritable`, whose fix text points at LOCALAPPDATA, `chmod` or a link, and that would be a wrong diagnosis.
  - **Behaviour change:** before, this case allowed. Now it walls the call with a message that does not apply, and it has no Failure Mode.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 "A revision that adds a path adds its failure modes". `JOURNAL.md` 2026-10-28 "Guard messages must use names the guard emits".
  - **Where in this contract:** `### Guard decision order`, "6-7 … A ticket write that fails at step 7 now blocks with `session-state-unusable`"; Parent problem closed set.

- **[WARN] Logging and flag writes in the unusable state are unspecified, and today's `announce` path writes into the folder**
  - **What is wrong:** When the state is unusable, steps 3-5 still allow. Today's `announce()` (guard `:942-967`) then calls `session.has_plain_file(flag)` and `session.create_once(flag)`, which calls `ensure_folder()` and so `os.mkdir`, inside the folder judged unusable. If the parent is a planted link, that mkdir lands in the link's target.
  - **What the contract says:** only "Their stderr line prints on every call, because no flag can be written". It does not forbid the attempt. It also does not say whether `log_event(event="fail-open")` now fires on every call (a log flood in `.claude/logs`) or not at all. The 2026-11-05 Events row promised once per session per reason.
  - **Prior artifact ignored:** `.claude/concepts/2026-11-05-codegraph-guard-fail-open.md` Events (GuardFailedOpen, "once per session per reason") and Addendum 6. `JOURNAL.md` 2026-11-02 "A rule titled 'every' must list every line it covers".
  - **Where in this contract:** `### Guard decision order`, step 0: "steps 3-5 still apply … Their stderr line prints on every call, because no flag can be written".

- **[WARN] After the move, the existing real-temp leak checks can no longer fail, and the new leak row checks only one prefix in one suite**
  - **What is wrong:** `test_worktree_path_guards.py:2262-2305` (W5) and `test_codegraph_first_guard.py:2324` snapshot `_addon_fixture.REAL_TEMP` (`_addon_fixture.py:391-396`) for new `auto-improve-codegraph-*` entries. After this change no hook writes there, so both checks pass whatever happens.
  - **New row:** it covers only `test_codegraph_first_guard.py` and only names starting with `t271-`. The other suites mint their own session ids, so a leak into the real `%LOCALAPPDATA%` or `~/.cache` parent from those suites goes unseen.
  - **Missing from the TASK block:** it does not name the three existing leak checks among the rows to re-state.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-11-02 "Name the tests a fix may change by the state they guard, after reading them". `JOURNAL.md` 2026-10-17 "Loosening a guard rule must be checked against the guard's own test fixtures".
  - **Where in this contract:** `## Failure Modes & Mitigations`, first FM: "assert afterwards that no folder there contains the suite's session-id prefix `t271-`"; TASK block, "leak row".

- **[NIT] An empty `## Critique` placeholder sits at line 229**, between `## Open Questions for User` and `## Lessons referenced`. This critique is appended at the end per protocol, so the file now has two `## Critique` headings.
- **[NIT] The decision order lists "1." before "0."** The text and the TASK block say step 1 now runs first. Renumbering would match the module docstring the implementer rewrites (guard `:28`).
- **[NIT] I-6 says "state the user did not write", but a Foreign marker (state "this session's tracker did not write") still opens.** The two are reconciled only by the same-user argument in Q4, which I-6 does not cite.
- **[NIT] "POSIX: the base is created with `0700` when it is missing" does not say whether it creates one level or the full chain.** With a deep, missing `XDG_CACHE_HOME`, the hooks would create folders that the environment variable names.

### Applicable journal entries

- **2026-10-04 — Check a documented guard behaviour against the guard's code**: violated; see the BLOCKER.
- **2026-11-02 — Edit a reversed sentence where it stands**: heeded for `MECHANISMS.md:106-107`; violated for install SKILL:78/183, README:306/314-315, decision-table:124 and VOCABULARY:125 (BLOCKER).
- **2026-10-05 — A documented "missing file means the default" must read one named location only**: heeded on Windows; violated on POSIX (WARN).
- **2026-11-05 — A same-host path rule must compare against both the written and the realpath form**: not applied to the new `remote` rule (WARN).
- **2026-10-22 — Describe a broken install by the rows each install age really has**: heeded for the hooks (`released_sha256`); violated for the helper, which an upgrade does not replace (WARN).
- **2026-11-02 — Name the tests a fix may change by the state they guard**: heeded for the `state-unwritable` rows; violated for the three leak checks (WARN).
- **2026-11-02 — A revision that adds a path adds its failure modes**: partly heeded. The catch-all allow, the transient ticket failure and the old-helper pair have no Failure Mode (WARNs).
- **2026-11-05 — A bridge re-export that silently falls back … must say which one it gave**: heeded by `TREE_HOP_REFUSAL`.
- **2026-11-05 — An "older release" test fixture must be pinned to a fixed commit**: heeded by the `e4f392c` / `643b667` pins with `git cat-file -e` and a skip.
- **2026-11-05 — A hardening fix applied to a shared classifier must be checked against every consumer**: heeded. `_git_file_kind` gets a comment only.
- **2026-10-17 — Git for Windows lists files beneath an untracked junction**: heeded by the folder-link rows inside the parent (I-9).
- **2026-10-28 — Guard messages must use names the guard emits**: heeded by I-7 (uninstall skill named, no shell route), apart from the step-7 cause (WARN).
- **2026-10-30 — A rule that refuses must give already-delivered work a named way out**: heeded. I-7 names the fix and `/auto-improve-codegraph-uninstall` plus a new session.
- **2026-10-28 — A new term's definition must be true against every existing member**: heeded. Both new terms are scoped to the codegraph hooks.
- **2026-10-22 — An accepted critic WARN or answered Open Question must amend the contract body before approval**: not addressed yet (pre-approval); it applies when Q1-Q5 and these findings are answered.

### What the critic did not check

- Not run (no shell): `derive_area.py` / `cross_area_scan.py` (area-mapping `areas` is empty, so the Adjacent Areas exception holds), `pr_merged.py --contract … --status --json` (one mergeable block, the `**Work Item Brief:**` header is present and the brief exists), `git cat-file -e e4f392c:…`, any test.
- The token count against the 12,000 budget was not measured. The file is about 360 lines, which looks within budget.
- No CodeGraph tool was available. Symbols were checked with Grep and Read on the hook files and the registries.
- No north-star check: `.claude/north-stars/` does not exist.

---
