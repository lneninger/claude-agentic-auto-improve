# Concept Contract — Delivery cleanup names the Claude Code session holding a deferred worktree, and the closing messages tell the user to stop a finished session

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-18
**Requested by:** user
**Status:** approved
**Supersedes:** none (extends the standing-tree and in-use deferrals of `.claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md` and the report of `.claude/concepts/2026-10-17-worktree-removal-untracked-identical.md`; both stay `implemented` and are not edited)
**Work Item Brief:** .claude/work-items/2026-10-18-cleanup-names-the-session-holding-a-worktree.md
**Tracking issue:** none

> **Protocol:** filled in by `data-architect`. Implementers refuse to run unless `Status: approved`. The `concept-gate.py` hook reads `Files to touch`.

> **Amendment 2026-10-18 (pre-approval):** carries the user's decisions on the contract-critic findings and on Open Questions 1 to 4. Changed: HN-2, HN-3, HN-5, HN-7, HN-8, HN-9, HN-11, the placement of the lookup (HN-1, halted runs), trial A removed, the handoff and the test list. Status stays `draft`.
>
> **Approval 2026-10-30:** the user approved this contract and chose the version raise 0.10.1 → 0.11.0 (master had moved to 0.10.1 during a 12-day pause; none of the cleanup script, its tests or the three skills changed on master, so every reference in this contract still holds). The 25-second worst case of HN-2 is kept.
>
> **Amendment 2026-10-30 (post-review):** carries the main session's decisions on the findings of the code review and the test-strategy review of the implementation. Status stays `approved`. Changed:
> - **A1, HN-9 and HN-2 (safety).** On the timeout the runner ends only its own child, with `proc.kill()`. It ends no descendant: no `taskkill`, no `killpg`, no new session, no process-tree step. Why: the background supervisor can be started as a descendant of a `claude` client (its own command line carries `--origin transient --spawned-by`), so a tree kill could end the supervisor and every background session, which HN-9 forbids. `_end_own_child_tree` becomes `_end_own_child`. The tripwire forbids `taskkill` and `killpg` everywhere. "Claude agents starts no service" is no longer load-bearing.
> - **A2, HN-2 (review warning W1).** `shutil.which("claude")` is accepted only when it returns an absolute path whose folder is neither the current folder nor the main checkout root. Why: on Windows a bare-name lookup also searches the current folder, so a `claude.exe` planted in a repository would run.
> - **A3, HN-5 (review warning W2).** Only a drive path and the Git Bash drive form are accepted. A UNC or device path, or a folder holding NUL, a control character or U+FFFD, makes the record unreadable. Why: such paths can reach the network or a device before any comparison. The old claim that `os.path.realpath` never opens a file was false, and is corrected. An offline mapped drive letter is a known limitation.
> - **A4, HN-2 and HN-3.** At most 4 MiB of output is read; more reads "not in the expected form".
> - **A5, HN-2, HN-9 and Failure Modes (justified divergence).** Output goes to a temporary file, not to pipes, so nothing waits for a grandchild to close a pipe.
> - **A6, Data Shapes.** An id that fails its check is stored as null in `--json`, not left out.
> - **A7, HN-11.** In `/task`, the `shipped` note "ends with" the paragraph.
> - **A8, Uncertain Assumptions.** The record shape is now verified by running the command on 2026-10-30 (23 records). A committed fixture and the opt-in read-only trial T6 join the deliverable. A `stopped` or `done` record is still reported.
> - **A9, handoff test list.** The heavy end-to-end variants become about six StandingTree tests plus one fast, parameterised unit class. The `+k more` test checks invariants, not character counts. The tripwire is widened. A Linux CI job is recorded as a follow-up under Non-Goals.
> - Alternatives gain Options I to L, and Failure Modes gain four entries. Five journal entries dated 2026-10-30 are added to `JOURNAL.md`.
>
> **Amendment 2026-10-31 (second review):** carries the main session's decisions on a second, cold review pass of the implementation. Status stays `approved`. Changed:
> - **B1, HN-2 (planted-program guard).** `claude` is started with its working folder set to the folder that holds the resolved program, not the main checkout. (Its child-environment half, `NoDefaultCurrentDirectoryInExePath=1`, is withdrawn by C1 of the 2026-11-18 amendment below.) Why: a `.cmd` wrapper looks up its interpreter (`node`) in the current folder first, so a `node.exe` planted in the repository root would run. This is the threat A2 closes for `claude` itself. A Failure Mode and Option M are added.
> - **B2, Data Shapes.** A field that fails its check is present in `--json`, never left out: `id`, `session_id` and `started_at` as null, and `name`, `state` and `kind` as an empty text. The code already does this; the wording now matches.
> - **B3, HN-2 (justified divergence).** `_find_claude` first accepts the plain `shutil.which` hit when it passes the A2 check. Otherwise it searches the remaining absolute PATH folders by full file name. Its limit before Python 3.12 is stated.
> - **B4, HN-6.** The marks U+200E, U+200F, U+061C, U+200B and U+FEFF are also stripped from list text. (The character list is replaced by the category rule of D2 below, which still strips every one of them.)
> - **B5, HN-11.** Where the paragraph sits is now stated. Its `/advance` placement is replaced by D1 of the 2026-11-19 amendment below. In `/flow` it belongs to the final report of Step 8, not to the push confirmation prompt.
> - **B6, names.** The real-program trial is T6 (`T6RealAgentsListTests`), not T5. Every mention is fixed, including A8 above. Its checks are stated in the handoff.
> - **B7, handoff test list.** New items cover: the real constants and timeout reason pinned in one unpatched test; the `Popen` keyword arguments and the logged working folder; proof that the real-wrapper scenario ran; a tighter tripwire with aliased imports and an exact-shape `_end_own_child`; and more unit cases.
> - **B8, Non-Goals.** Five follow-ups are recorded, not implemented.
> - Five journal entries dated 2026-10-31 are added to `JOURNAL.md`.
>
> **Amendment 2026-11-18 (user rule: no created environment variables):** the user's standing rule forbids creating or proposing an environment variable as a mechanism (a toggle, override, bypass or setting); visible files or explicit arguments are used instead. Status stays `approved`. Changed:
> - **C1, HN-2 (replaces the environment half of B1).** The child no longer gets `NoDefaultCurrentDirectoryInExePath=1`. `_run_holder_list` passes no `env` argument, so the child inherits the unchanged environment on every platform. The neutral working folder of B1 (the folder that holds the resolved `claude` program) stays, and it alone closes the planted-`node.exe` case: a `.cmd` wrapper looks in the current folder first, and that folder is now the program's own, never the repository root. Updated with it: Extension Points (`_run_holder_list`), Failure Modes (planted `node.exe`), Option M, the new rejected Option N, the handoff TASK block (B1 constraint and the [B7] `Popen` test) and the review scope note.
> - **C2, HN-7 and Uncertain Assumptions.** Reading `CLAUDE_CODE_SESSION_ID` reads a variable Claude Code already provides; it creates nothing. This change introduces no new variable, switch or override anywhere. No visible-file alternative is needed, because the value is only read.
>
> **Amendment 2026-11-19 (final review, user chose the recommendations):** carries the user's decisions on the final review. Status stays `approved`. Changed:
> - **D1, HN-11 (replaces the `/advance` half of B5).** The `/advance` report block keeps master's order. It is not reordered: `Next command:` is the first of the last two lines and `Cleanup:` follows it, with `Trees:` where master has it. The closing paragraph is printed inside the report block, directly before the `- Next command:` line. The earlier wording ("follows the Cleanup line", "the Next command stays the very last line", "printed last", "after the report block") is removed. The skill's sentence "The last two lines matter most", which names the Next command and the Cleanup lines, is kept and reconciled: the paragraph is not one of those two lines. In `/flow` the paragraph still belongs to the final report of Step 8, not to the push confirmation prompt.
> - **D2, HN-6 (replaces the character list of HN-6 and B4).** List text is cleaned in a fixed order: reject non-text (D3), Unicode NFKC normalisation, drop every character whose Unicode category is Cc, Cf, Zl or Zp, then the existing replacements and the cut to 60 characters. NFKC folds lookalike separators such as U+037E and U+FF1B to `;`, which the replacement then turns into `,`. Every character stripped before is still stripped. One correction to the decision's wording: of the tag block U+E0000 to U+E007F, only U+E0001 and U+E0020 to U+E007F are category Cf and are dropped; the rest are unassigned (Cn) and are not (HN-6).
> - **D3, Data Shapes (B2).** `name`, `state` and `kind` are an empty text when the value is missing or is not a string (a boolean, a number, a list, an object or null). They are never turned into text with `str()`.
> - **D4, HN-2 (`_find_claude`).** No PATH folder is resolved before a hit. An entry is skipped only when it is empty or not absolute, and `_norm` runs only on an actual hit's folder, and once each on the current folder and the main checkout root. So a stale UNC or offline-drive PATH entry is never resolved when `claude` is absent.
> - **D5, HN-9 and [B7].** The body of `_end_own_child` is `try: proc.kill()` with `except OSError: pass`. It still holds exactly one `<first parameter>.kill()` call with no arguments, and the tripwire's shape rule is stated to match.
> - **D6, Non-Goals.** Two more follow-ups are recorded, not built: a DOS device name as the last part of a drive path, and `attach_holders` having no catch-all of its own.
> - The handoff test list is updated to match D1 to D5.
>
> **Amendment 2026-11-19 (last review):** carries the main session's decisions on the last review. Status stays `approved`. Changed:
> - **E1, Uncertain Assumptions and HN-4 (verified fact).** Checked on the user's machine on 2026-11-19 by comparing live processes with the list's `pid` field: `claude agents --json --all` lists background sessions only (every record has kind `background`). An interactive session started by typing `claude` in a PowerShell window is not in the list; the workers of background sessions are. The list is not scoped to the folder it is run from. So a terminal session, an editor or another program standing in a deferred folder is never named, and the `none-found` text must not claim that no session of any kind is in the folder.
> - **E2, wording (Business Concept, HN-4, HN-8, Failure Modes, test list).** The `none-found` bracket reads `[no background session in the list is in it]` (was `[no Claude Code session in it]`). The fixed uncut note (`HOLDER_NOTE`) reads `note: the session list shows background sessions only; a session typed into a terminal, an editor or another program may also hold this folder` (was the "only Claude Code sessions are checked, cannot rule out other programs" text). The `found` and `cannot-tell` brackets and the verdict names `found`, `none-found` and `cannot-tell` are unchanged.
> - **E3, vocabulary.** A **Folder holder** is a background Claude Code session in the session list. A Claude Code session typed into a terminal is not listed and is never a Folder holder.
> - **E4, records.** Master moved during the work: the shipped version is **0.22.0**, a minor raise from master's 0.21.0, in the five places (Extension Points item 4 and the handoff, which still said 0.10.1 → 0.11.0). `_run_holder_list` has a fifth internal result, `too-big` (output over the 4 MiB limit), mapped to the fixed reason "the session list was not in the expected form" (HN-3). A holder's JSON `cwd` goes through the same cleaning as the other list text (NFKC and control removal); it is shown in `--json` only and is never used for matching, which uses the raw record text through HN-5.
> - **E5, journal.** One entry dated 2026-11-19 is added to the journal through `registry_append.py`, the registries' single write path: re-verify an external command's output after a contract changes how it is launched, and say in user-visible text only what the list proves.

---

## Business Concept

- **What is this thing, in domain language?**
  When Delivery cleanup (the script that removes a delivered work item's worktrees and branches) has to leave a worktree because some process is using its folder, today it says only `deferred: standing-tree` or `in-use`. The user then has to hunt for the process by hand. After this change the cleanup asks Claude Code's own session list, the read-only command `claude agents --json --all`, which Claude Code documents and which prints one record per session with its id, working folder, name and state. Every Claude Code session whose working folder is that worktree or a folder inside it is a **Folder holder**. The report names each holder, marks the session that is running the cleanup as "this session", and prints the exact `claude stop <id>` command for every other holder, all of them, never cut. The user runs that command; the cleanup itself never stops another session. When the list cannot be read, the report says it cannot tell, and why. The list shows background Claude Code sessions only (verified 2026-11-19, E1), so a Claude Code session typed into a terminal, an editor or another program holding the folder is never named. When no listed session is in the folder the report says `no background session in the list is in it`, and its fixed note says that such a session or program may still hold the folder (E2).
  Separately, the closing messages of `/flow` (where it reports `shipped`), `/advance` (where it reports a delivered cleanup) and `/task` (its note on the `shipped` status) carry one fixed, conditional paragraph: once the pull request is merged and the work is delivered, end the session with `/stop` before the cleanup runs, because `/exit` only detaches and a background session keeps its folder in use for hours.

- **Existing VOCABULARY.md terms that apply:** **Contract Delivery** (line 47), **Delivery cleanup** (line 56), **Standing tree** (line 58), **Owned set** (line 57), **Landed untracked file** (line 59), **Main checkout** (line 54), **Flat worktree** (line 55). All in the Universal section of `.claude/registries/VOCABULARY.md`.

- **New terms proposed for VOCABULARY.md (Universal, after approval; not written to the registry by this draft):**
  - **Folder holder** — a **background Claude Code session in the session list, and only that,** whose working folder, as Claude Code's own session list (`claude agents --json --all`) reports it, is a deferred worktree's folder or lies inside it, by the same folder comparison the Standing tree rule uses (HN-5). The list shows background sessions only (E1), so a Claude Code session typed into a terminal is not listed and is never a Folder holder (E3). This is narrower than "holds" in **Standing tree**, which covers any process: a terminal session, editor or other program can hold a deferred tree's folder and is still never a Folder holder, because the list does not show it.
  - **Holder reading** — the answer Delivery cleanup records on a deferred worktree about its Folder holders: `found` (at least one holder), `none-found` (the list was read in full and no listed background session is inside the folder; it says nothing about sessions or programs the list does not show, E1), or `cannot-tell` (the list could not be read or trusted, with a fixed reason). It is made only after the deferral is decided and never changes the deferral, the reason, the outcome or the exit code.

---

## End-User View

Not applicable. Reason: no Angular UI surface (component, template, stylesheet, state service, route or layout) is in `Files to touch`. The user-visible effects are a new bracket and new uncut parts in the one-line cleanup report, and one fixed paragraph in three skills' closing messages, all specified under Data Shapes.

---

## Data Shapes

### Entities

Not applicable. Reason: nothing is persisted. The session list is read once, in memory, during one cleanup run.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| **Session Record** (new, in memory, one per record of the list) | `id`: text, kept only when it is exactly 8 lowercase hex characters, else null (in `--json` the key is present with the value null, never left out); `session_id`: text, kept only when it has the 8-4-4-4-12 lowercase hex form of a UUID, else null; `cwd`: text (the working folder); `name`, `state`, `kind`: cleaned text (see invariant HN-6), or an empty text when the value is missing or is not a string (a boolean, a number, a list, an object or null); such a value is never turned into text with `str()` (D3); `started_at`: whole number of milliseconds since 1970, else null (a non-integer and a boolean both become null). In `--json` every one of these keys is present; a field that fails its check is written as null or an empty text, never left out. The record's `pid` and `status` keys are ignored | Parsed from one object in the list. A record whose `cwd` is missing, not text, empty, not in an accepted path form (HN-5), holds a forbidden character (HN-5), or makes the folder comparison raise, is an **unreadable record** |
| **Session List Reading** (new, in memory, at most one per run) | `verdict`: `read` \| `cannot-tell`; `reason`: one fixed text (only for `cannot-tell`); `records`: list of Session Record; `unreadable`: count of unreadable records; `this_session`: the id of the record recognised as the running session, or none | Produced by one call of `claude agents --json --all`, made only when at least one worktree was deferred as `standing-tree` or `in-use` |
| **Holder** (new, inside a Holder Reading) | `id`, `session_id`, `name`, `state`, `kind`, `started_at` (copied from the Session Record and always present: `id`, `session_id` and `started_at` are null when they are null there, and `name`, `state` and `kind` are an empty text when they are empty there); `cwd` (cleaned like the other list text: NFKC, then control and format characters removed (E4); display only, in `--json` only, never in the line and never used for matching, which uses the raw record text through HN-5); `this_session`: yes/no; `stop_command`: `claude stop <id>` or none | One Folder holder |
| **Holder Reading** (new, on a deferred worktree item only) | `verdict`: `found` \| `none-found` \| `cannot-tell`; `reason`: fixed text, only for `cannot-tell`; `sessions`: list of Holder (empty unless `found`); `this_session_recognised`: yes/no | The new `holders` field of a Cleanup Item whose action is `deferred` and whose reason is `standing-tree` or `in-use`. No other item gains the field |
| **Cleanup Item** (extended) | gains `holders` (a Holder Reading) on the deferred items above only. Every other field, and every other item, is byte-identical to today | Under `--json` |
| **Cleanup Report** (extended) | gains `stop_commands` (list of text, only when non-empty) and `holder_lookup` (`{verdict, reason, this_session}`, only when a lookup ran). Nothing else changes | Under `--json`; the printed `line` changes as in HN-8 |

### Events

Not applicable. Reason: a command-line script; it neither emits nor listens to events.

### Commands (if any)

Not applicable. Reason: no flag, argument or exit code is added or changed. `cleanup_delivered.py` keeps exit codes 0, 3, 5, 10 and 2. The one new outbound call is the read-only `claude agents --json --all`, described in HN-2.

### Invariants

- **HN-1 — The reading comes after the decision and cannot change it, halted runs included.** The lookup runs once per run, in `cleanup()` **after the whole `if not run.halted:` block** (orphan report, `clean_branches`, `clean_remote`) and before `finish_command` and `build_line`. So it also runs when the run stopped part-way (`run.halted`), over the items already in `run.items`: an item deferred before the halt still gets its Holder reading. It runs only when at least one item has action `deferred` with reason `standing-tree` (any platform, including dry run) or `in-use` (Windows, from the rename probe). It writes only the `holders` field of those items and the two report fields. Action, reason, files, detail, outcome, exit code and the finish command are computed exactly as today; a test compares them with and without a list that names holders, in a normal run and in a halted run.
- **HN-2 — One fixed, read-only command, with a ceiling that holds for a wrapper too.** The program is found with `shutil.which("claude")`, which honours Windows' list of program extensions, so `claude.exe` and `claude.cmd` are both found. **The result is accepted only when it is an absolute path and its folder, compared with `_norm`, is neither the current folder nor the main checkout root.** Otherwise the lookup reads `launch-failed` with "the claude command was not found". The reason: on Windows a lookup by bare name also searches the current folder, and the cleanup runs from inside a repository, so a `claude.exe` planted there would otherwise run. **The search is done by `_find_claude` (a justified divergence, 2026-10-31):** it first takes the plain `shutil.which("claude")` hit when that hit passes the check above. If it does not, `_find_claude` searches the PATH folders by full file name (`shutil.which` given the full path of `<folder>/claude`). **No PATH folder is resolved before a hit (D4, 2026-11-19):** an entry is skipped only when it is empty or not absolute, with text checks alone. `_norm` runs only on the folder of an actual hit, and once each on the current folder and the main checkout root; a hit whose folder equals either of those is skipped and the search goes on. So a stale UNC or offline-drive PATH entry is never resolved when `claude` is absent. **Limit:** before Python 3.12, `shutil.which` given a full path does not try the Windows program extensions (`.exe`, `.cmd`), so on those versions the fallback finds only an extension-less file named `claude`; the first, plain lookup still finds `claude.exe` and `claude.cmd`. The program is started by one dedicated runner, `_run_holder_list`, not by `_exec` (which stays unchanged, 120 seconds, for git and gh). The runner starts it with:
  - the fixed argument list `agents --json --all`;
  - no shell;
  - **a neutral working folder: the folder that holds the resolved `claude` program** (the folder part of its absolute path), never the main checkout (amended 2026-10-31, B1);
  - **no `env` argument: the child inherits the unchanged environment on every platform** (amended 2026-11-18, C1). No variable is set, added or removed for the child. The neutral working folder above is what stops a `.cmd` wrapper from finding a planted interpreter: the wrapper looks up `node` in the current folder first, and that folder is the program's own folder, never the repository root, so a `node.exe` planted in the repository root is not found. This is the same threat the folder check above closes for `claude` itself;
  - standard input closed;
  - standard output written to a **temporary file, not a pipe** (a justified divergence from the first wording, which said pipes), and standard error discarded, since no reason ever quotes it (HN-3).

  It waits at most `HOLDER_TIMEOUT_SECONDS = 15` (a fixed constant, no flag) for the child to exit. When that time passes, it calls `_end_own_child(proc)` (HN-9) and then waits at most `HOLDER_END_GRACE_SECONDS = 5` for that one child to go. After that it stops waiting. Nothing waits for a grandchild: the output is in a file, so no grandchild can hold a pipe open. The whole lookup, the command and its waits, therefore ends within 15 + 5 + 5 = 25 seconds, even when `claude` is a `.cmd` wrapper whose real program keeps running.
  - **Output limit:** at most `HOLDER_OUTPUT_LIMIT_BYTES = 4 * 1024 * 1024` bytes (4 MiB) of the output file is read. More than that reads as "the session list was not in the expected form". The bytes read are decoded as UTF-8 with replacement.
  - **What the 25 seconds does not cover:** the per-record path checks of HN-5. `os.path.realpath` on an offline mapped drive letter can take longer. This is a known limitation and is not fixed here.

  Nothing taken from the list, a path or the environment ever enters an argument list, and no other process is started.
- **HN-3 — Fail closed to `cannot-tell`, with a fixed reason.** The runner returns one of five closed results — `answer`, `timeout`, `launch-failed`, `exit <n>` and `too-big` (output over the 4 MiB limit; added 2026-11-19, E4) — so a timeout and a non-zero exit are never confused. Each of these makes the Session List Reading `cannot-tell`, and every deferred item's Holder Reading `cannot-tell` with the same reason:
  - `claude` is not found, or `shutil.which` returns a relative path or a path in the current folder or the main checkout root (HN-2) → "the claude command was not found";
  - the program cannot be started (`OSError`) → "the claude command could not be started";
  - the time ceiling passes → "claude agents gave no answer within 15 seconds";
  - a non-zero exit → "claude agents exited with code <n>";
  - output over 4 MiB (the `too-big` result), or output that is not JSON, not a list, or holds an element that is not an object → "the session list was not in the expected form";
  - any exception anywhere in the lookup → "the session list could not be read (<exception type name>)".

  The reason never quotes the command's output or its error stream. A failed read never turns a deferral into `removed`, never makes a tree free, and never changes the exit code.
- **HN-4 — An unreadable record is not proof of absence.** A list holding unreadable records still names the holders it can match (`found`). But when no holder matched and any record was unreadable, the item reads `cannot-tell` with "<n> session records had no readable working folder", never `none-found`. **Even a clean `none-found` is not proof that the folder is free (2026-11-19, E1):** the list shows background sessions only, every record has kind `background`, and a Claude Code session typed into a terminal, an editor or another program is never in it. So the `none-found` text says only that no background session in the list is in the folder (HN-8), never that no session of any kind holds it.
- **HN-5 — The same folder comparison as the deferral.** A record is a holder of a worktree exactly when `_inside(record_cwd, worktree_path)` is true, using the existing private helpers `_norm` (real path, then case folding on Windows) and `_inside` (equal, or inside after a separator) at `cleanup_delivered.py` lines 104-110, which `Run.is_standing` already uses at lines 379-380 to decide the standing-tree deferral. No second matcher is written, so the holder report cannot contradict the deferral: a folder reached through a link or a short Windows name compares the same way in both. `_norm` resolves the record's folder text through `os.path.realpath`. **On Windows that call opens the path** to resolve links. (The first wording said it "never opens a file or lists a folder", which was false.) So text-only checks run first and decide which `cwd` forms reach it; these are decided here, not left to the implementer:
  - **Any platform:** a `cwd` that holds NUL, any control character (U+0000 to U+001F, U+007F, U+0080 to U+009F) or the replacement character U+FFFD makes the record unreadable.
  - **On Windows:** only two forms are accepted:
    - a drive path, `X:\…` or `X:/…`;
    - the Git Bash drive form, `/<letter>` or `/<letter>/<rest>` with one ASCII letter, which becomes `<LETTER>:/` or `<LETTER>:/<rest>`.

    A UNC path (`\\host\share…`) and any device form (`\\.\…` or `\\?\…`, `\\?\UNC\…` included) make the record unreadable and are never passed to `realpath`, because they can reach the network or a device. Any other form (a relative path, `/tmp/…`, `/cygdrive/…`) also makes the record unreadable. An unreadable record never yields `none-found` (HN-4): the reading is `cannot-tell`.
  - **On POSIX:** only a path starting with `/` is accepted; anything else makes the record unreadable.
  - **Known limitation:** a drive letter mapped to an offline network share passes these checks, and `realpath` on it can block. The 25-second bound of HN-2 covers the command, not these path checks. This is not fixed here.

  A `cwd` for which `_inside` raises (for example `ValueError` on an embedded null) makes that record unreadable; it does not end the lookup. A folder named `tree-2` never matches `tree`.
- **HN-6 — Untrusted text is neutralised before it is shown.** `name`, `state` and `kind` from the list are cleaned in this order (amended 2026-11-19, D2; it replaces the character list of the first wording and of B4):
  1. **Reject non-text.** A value that is missing or is not a string becomes an empty text (D3), never `str()` of the value.
  2. **NFKC normalisation** (Unicode compatibility composition). This folds lookalike separators, such as U+037E (Greek question mark) and U+FF1B (fullwidth semicolon), to `;`, and fullwidth quotes and brackets to their ASCII forms, so step 4 catches them.
  3. **Drop every character whose Unicode category is Cc, Cf, Zl or Zp.** This covers the ASCII controls, the C1 range U+0080 to U+009F, U+2028 and U+2029, the direction controls U+202A to U+202E and U+2066 to U+2069, the marks U+200E, U+200F, U+061C, U+200B and U+FEFF, and also U+200C, U+200D, U+2060 to U+2064, U+00AD, U+180E, U+FFF9 to U+FFFB and the assigned tag characters (U+E0001 and U+E0020 to U+E007F, all category Cf). Every character stripped before this amendment is still stripped. Note: U+E0000 and U+E0002 to U+E001F are unassigned (category Cn), so this rule does not drop them; they carry no meaning in any font and cannot forge a part of the line, because the replacements of step 4 still apply.
  4. **Replacements:** `;` becomes `,`, `"` becomes `'`, `[` becomes `(` and `]` becomes `)`.
  5. **Cut** to 60 characters. Every `state` value is shown as it is after cleaning, unknown ones included, with no wording of its own (Open Question 3). The `id` is shown, and a stop command is printed, only when the id passed its format check in the Session Record. A holder whose id failed is shown as "a session with an unreadable id" and gets no stop command.
- **HN-7 — This session is recognised only by an exact match on `CLAUDE_CODE_SESSION_ID`.** The running session is never recognised by folder, because two sessions can share one folder (the incident behind this work). The cleanup reads one variable, `CLAUDE_CODE_SESSION_ID`, which holds the running session's full id (a UUID). This was checked in a real session on 2026-10-18: its value matched that session's `sessionId` field in `claude agents --json --all` exactly. A record is "this session" when its `session_id` equals the variable's value exactly, character for character, and the match counts only when exactly one record matches. No other variable is read: `CLAUDE_SESSION_ID`, `CLAUDE_JOB_DIR` (whose last folder name is the 8-character id) and `CLAUDE_CODE_AGENT` are ignored. An unset or empty variable means "not recognised". **Reading this variable creates nothing (2026-11-18, C2):** `CLAUDE_CODE_SESSION_ID` is provided by the host program, Claude Code, and the cleanup only reads it. This change introduces no new environment variable, switch or override anywhere, so no visible-file alternative is needed. A recognised holder is labelled "(this session)" and gets no stop command, because the finish command already covers it. When the session is not recognised and at least one stop command is printed, the line carries the fixed warning in HN-8.
- **HN-8 — The one-line report.** `build_line` stays pure: it derives everything below from the items, so `PureLogicUnitTests` can feed it synthetic items.
  - **Bracket** on each deferred item that carries `holders`, after the reason:
    - `found`: `[held by <holder>, <holder>]`, where a holder is written `<id> "<name>" <state>`, or `<id> (this session)` for the running session. An empty name is left out.
    - `none-found`: `[no background session in the list is in it]` (amended 2026-11-19, E2; was `[no Claude Code session in it]`).
    - `cannot-tell`: `[cannot tell which session holds it: <reason>]`.

    The holder list inside a bracket goes through the existing shortening steps, using each step's file cap, and shows `+k more` past the cap. At the last step every list is dropped, as today. The bracket is the cuttable part; the stop commands below are not.
  - **Uncut part.** This part is never shortened. It follows any `; repair:` parts and comes before `; finish:`, in this order:
    1. **The fixed note** (`HOLDER_NOTE`), whenever any item carries `holders`: `; note: the session list shows background sessions only; a session typed into a terminal, an editor or another program may also hold this folder` (amended 2026-11-19, E2; it replaces the "only Claude Code sessions are checked" text).
    2. **The fixed warning**, when a stop command is printed and the session was not recognised: `; warning: the running session was not recognised, so one stop command may be its own`.
    3. **One `; stop: claude stop <id>` per distinct session**, in first-seen order, never for "this session", **every one of them, with no cap**, on the same never-cut rule as the finish command (the brief's acceptance criterion).
  - **Finish part.** `; finish: <command>` stays last, exactly once. The line exceeds 600 characters only when the counts and the uncut parts alone exceed it, which is today's rule for the finish command; everything else is bounded by the existing shortening steps. `stop_commands` in `--json` is exactly the list the line prints, computed by the same helper.
- **HN-9 — Read only, with one stated exception.** The cleanup never stops, signals or changes another session or process. It runs no `claude stop`, `kill` or `rm`, and it never reads another process's memory or command line. **The one exception is its own `claude agents` child, and only after the time ceiling:** `_end_own_child(proc)` calls `proc.kill()` on the `Popen` the runner itself created, and does nothing else. Its body is `try: proc.kill()` with `except OSError: pass` (amended 2026-11-19, D5): a child that already exited cannot make the timeout branch raise. That body still holds exactly one `<first parameter>.kill()` call with no arguments. **It never ends a descendant of that child.** There is no `taskkill` (with or without `/T`), no `os.killpg`, no `start_new_session` or new process group, and no process-tree step of any kind. The reason: Claude Code's background supervisor can be started as a descendant of a `claude` client (the supervisor's own command line carries `--origin transient --spawned-by`). A tree kill could therefore end the supervisor and every background session, which this invariant forbids. A grandchild left running after the timeout is acceptable: the output goes to a temporary file (HN-2), so nothing waits for it, and the 25-second bound still holds. `_end_own_child` has exactly one caller, the timeout branch of `_run_holder_list`, and `proc.kill()` appears only inside `_run_holder_list`'s timeout path through that helper. The tests prove both halves of this rule.
- **HN-10 — No change for anything else.** A worktree that is removed, left for another reason, or not deferred keeps today's report text and JSON byte for byte. A run with nothing deferred never starts `claude`. The no-force rule, its tests and the Landed-untracked steps are unchanged.
- **HN-11 — The closing paragraph is conditional, and VOCABULARY's meaning of "delivered" wins.** This exact paragraph, on one line, is pinned:

  > Once the pull request is merged and the work is delivered, end this session with `/stop` before the delivery cleanup runs (or runs again): a session left running keeps its worktree folder in use, and the cleanup then has to leave that folder behind. `/exit` only detaches and leaves the session running; from another terminal, `claude stop <id>` stops it, where `<id>` is the 8-character id that `claude agents` shows.

  "Delivered" here means **Contract Delivery** as `VOCABULARY.md` line 47 defines it (the GitHub-verified merge into the default branch, never inferred), and **Delivery cleanup** (line 56) keeps its rule of reading "not delivered yet" until then. **Where the paragraph and the vocabulary could disagree, the vocabulary wins:** the paragraph never states that delivery has happened, only what to do once it has, and no skill may reword it into a claim that the work is delivered. It appears exactly once in each of these sections:
  - `skills/flow/SKILL.md`, at the end of `## Step 8`, where `/flow` reports `shipped`. At that moment the pull request may still be a draft, which is why the paragraph is conditional. The paragraph belongs to Step 8's final report, never to the push confirmation prompt;
  - `skills/advance/SKILL.md`, in `## Step 3`, in the report block. It is printed only when the Cleanup line has the delivered form `CLEANUP <slug>: removed …`, so never on "not delivered yet", never on "unverifiable", and never when no line was produced. It is printed inside the report block, directly before the `- Next command:` line, and the report block keeps master's order (D1);
  - `skills/task/SKILL.md`, in `## Status lifecycle`, as the note on the `shipped` status. That note introduces the paragraph with the words "ends with" (never "may end with"). It is **not** in `## Step 6`, which is the automatic hand-off to `/design-first` and not a report.

  Next to the paragraph, each skill says in its own words: the paragraph is advice to the user; the model must not run `/stop`, `claude stop` or any other stop itself; and a user instruction to keep working takes precedence over it.

  **Where the paragraph sits (amended 2026-10-31, B5; the `/advance` half replaced 2026-11-19, D1).**
  - **`/advance`:** the report block is not reordered; it keeps master's order, with `Next command:` the first of the last two lines, `Cleanup:` after it, and `Trees:` where master has it. `skills/advance/SKILL.md` gains one plain sentence: the paragraph is printed inside the report block, directly before the `- Next command:` line, and the Next command line keeps master's position. The skill's existing sentence "The last two lines matter most" (the Next command and the Cleanup lines) stays true and is reconciled in the same place: the paragraph is not one of those two lines and does not move them.
  - **`/flow`:** the paragraph is the end of Step 8's final report, and it is never part of the push confirmation prompt. This sentence is added to `skills/flow/SKILL.md`, next to the pinned paragraph, in those words or the skill's own.

---

## Reused Mechanisms

- **Delivery cleanup** (`MECHANISMS.md` line 67) — **extended by** the Holder reading. It reuses:
  - `_norm` and `_inside` (lines 104-110), the folder comparison the standing-tree rule uses through `Run.is_standing` (lines 379-380), unchanged, as the only holder matcher (HN-5);
  - `_clean`, extended by a stricter cleaner for list text;
  - `_listing`, the `build_line` shortening steps, the uncut tail rule of the finish command, `Run.finish_needed` and `_left_entry` (which gains the bracket);
  - the test world: `write_exe`, the `Tools` fake-program folder and `run_in_process`.

  `_exec` is **not** reused for the lookup: it folds a timeout and a launch error into exit code 1, and it reads output through pipes, which a wrapper's grandchild can hold open past the ceiling. So it stays unchanged for git and gh. Persistence check: there is no database. Closed-set check: no reason, action or outcome value is added; `holders` is a new field, not a new reason.
- **Standing tree** detection (VOCABULARY line 58) — **consumed as-is**. The standing folders (working directory, `CLAUDE_PROJECT_DIR`, `--from`) still decide the deferral. The Holder reading only explains it, with the same comparison.
- **Main-checkout guard** (line 61) and **Flat worktree helper** (line 63) — consumed as-is, untouched.

---

## New Mechanisms (if any)

None. The holder lookup is a step of Delivery cleanup and has no other caller. A shared "session list reader" would be premature with one consumer; if a second caller appears, the reviewer may promote it then.

---

## Extension Points

1. `.claude/scripts/cleanup_delivered.py`:
   - The constants `HOLDER_TIMEOUT_SECONDS = 15`, `HOLDER_END_GRACE_SECONDS = 5` and `HOLDER_OUTPUT_LIMIT_BYTES = 4 * 1024 * 1024`.
   - `_find_claude` — the program check of HN-2: the plain `shutil.which("claude")` hit accepted only as an absolute path outside the current folder and the main checkout root, then the PATH-folder fallback (B3), which skips only empty or non-absolute entries and runs `_norm` only on a hit's folder (D4).
   - `_run_holder_list(exe, cwd)` — the runner of HN-2, with `cwd` the folder of the resolved program (B1) and no `env` argument, so the child inherits the unchanged environment (C1), output to temporary files, returning the five closed results of HN-3 (`too-big` included, E4).
   - `_end_own_child(proc)` — HN-9's one exception (`try: proc.kill()` / `except OSError: pass`, D5), called only from the runner's timeout branch. It replaces `_end_own_child_tree`.
   - `_read_session_list` — the list reader that returns the Session List Reading (HN-3, HN-4).
   - `_holder_path` — the `cwd` form and character step (HN-5) in front of the existing `_inside`; no new matcher.
   - `_holders_for` — builds one Holder Reading from the Session List Reading and a tree.
   - A text cleaner for list text (HN-6, in the D2 order: non-text rejected, NFKC, categories Cc, Cf, Zl and Zp dropped, replacements, cut).
   - A this-session finder that reads `CLAUDE_CODE_SESSION_ID` only (HN-7).
   - A step in `cleanup()` after the `if not run.halted:` block and before `finish_command` that fills `holders` on the qualifying items (HN-1).
   - A helper that returns the stop commands from the items (HN-8), used by both `build_line` and the report.
   - `_left_entry` renders the bracket, and `build_line` builds the uncut part in HN-8 order.
   - The module docstring's rule list gains the Holder-reading rule and the read-only rule with its one exception.
2. `.claude/scripts/tests/test_cleanup_delivered.py`, the new fixture `.claude/scripts/tests/fixtures/claude_agents_list.json`, and trial T6 (`T6RealAgentsListTests`) in `.claude/scripts/tests/test_cleanup_delivered_trials.py`. The tests are listed in the handoff.
3. `skills/flow/SKILL.md` (`## Step 8`), `skills/advance/SKILL.md` (`## Step 3`), `skills/task/SKILL.md` (`## Status lifecycle`): the HN-11 paragraph and the precedence sentence. In `/advance` the paragraph sits inside the report block, directly before the `- Next command:` line, with the block in master's order (D1).
4. Version 0.10.1 → 0.11.0 (a minor raise, because this is a new capability; the user chose it on 2026-10-30 after master moved from 0.9.11 to 0.10.1). **Superseded 2026-11-19 (E4):** master moved again during the work, and the shipped version is **0.22.0**, a minor raise from master's 0.21.0. The raise goes in all five declarations: `plugin.json`, `.claude-plugin/plugin.json`, `.cursor-plugin/plugin.json` and `.claude-plugin/marketplace.json` (two entries). This repository is the plugin, and `CONTRIBUTING.md` ("edit the file wherever you are working, at its ordinary path") means the edit in place is the plugin copy. `test_check_version_bump.py` fails a shipped script change without a higher version.

---

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| `cleanup_delivered.py` | Claude Code CLI (`claude agents --json --all`) | child process, read-only | JSON list of session records | script → external program → script |
| `cleanup_delivered.py` | `/pr-merged` Step 7 and `/advance` Step 3 | the printed `line`, quoted verbatim | Cleanup Report `line` (new bracket and uncut parts) | script → skill text |
| `skills/flow`, `skills/advance`, `skills/task` | the user | closing message text | the HN-11 paragraph | skill → user |

**Changes to existing integration surfaces:** the `line` gains a bracket and uncut parts, and is still one line. The skills print it unchanged, so no skill's cleanup wiring is edited. The JSON gains `holders`, `stop_commands` and `holder_lookup`, only in the cases HN-1 names. No frontend, no API.

---

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold. (The contract's area derives as `uncategorized`, the fallback bucket, and the scan reported no adjacent area.)

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

---

## Chat Tool Impact

2. **No —** no REST endpoint or SignalR event is added or changed. The change is to a local maintenance script and three skill texts.

---

## Non-Goals

- Stopping, signalling or changing any session or process from the cleanup, even when asked, apart from ending its own timed-out `claude agents` child with `proc.kill()` (HN-9). Ending that child's descendants is out of scope by design. The cleanup names and prints; the user runs the command.
- Bounding the time of the per-record path checks on an offline mapped drive letter (HN-5, known limitation).
- A Linux CI job that runs the in-process test classes. This is a follow-up and is out of scope here; today the POSIX branches are proven only where the suite is run on POSIX.
- Follow-ups recorded on 2026-10-31 (B8), tracked in the final report and not implemented here:
  - moving the five world-based `HolderFailurePathTests` variants into fast unit subtests of `_read_session_list`;
  - routing the end-to-end link test's deferral through the link itself;
  - calling `_norm` once per record instead of twice (this halves the delay on an offline drive);
  - bounding the size of the temporary output file, not only the bytes read from it.
  - (The Linux CI job above is the fifth.)
- Follow-ups recorded on 2026-11-19 (D6), raised by the final review and not built now:
  - a DOS device name (`CON`, `NUL`, `COM1`, `CONIN$` and the like) as the last part of an accepted drive path still reaches `realpath`. The risk is low: the open requests no access;
  - `attach_holders` has no catch-all of its own. The final review judged it safe by construction today; a catch-all would guard against a future change.
- A session stopping itself at the end of a run (an opt-in follow-up named in the brief's Out of scope list).
- Naming terminals, editors, Claude Code sessions typed into a terminal (not in the list, E1) or any non-Claude-Code program holding the folder, and reading any process's memory, command line or handle table.
- Changing what is deferred, the reasons, the rename probe, the standing-folder rule, the no-force rule or the Landed-untracked steps.
- Changing Claude Code itself, its idle timer or the left-arrow behaviour; reporting documentation problems.
- Recognising "this session" from anything other than an exact match on `CLAUDE_CODE_SESSION_ID` (HN-7).
- Filtering sessions by state: `--all` stays, and every match is reported, ended sessions included if the list shows them (Open Question 4).

---

## Confidence

Confidence: Medium-High. High on placement, the unchanged decisions and the report rules, all read in source (`cleanup_delivered.py:104-110, 379-380, 538-637, 872-985`; the test file's `StandingTreeTests`, `PureLogicUnitTests`, `ForbiddenTokenScanTests`, `SkillWiringTests`). The two CLI facts that were open are now verified in this session: `claude stop` takes the 8-character id, and `CLAUDE_CODE_SESSION_ID` equals the list's `sessionId`. What stays medium: the exact `cwd` form Claude Code prints on Windows (HN-5 accepts both the native and the Git Bash form) and whether `--all` lists ended sessions (every match is reported either way).
Update 2026-10-30: the record shape is now verified on one real machine (23 records, Uncertain Assumptions, A8). Every `cwd` was a drive path, and `done` and `stopped` records are listed. What stays medium after that: names other than ASCII, and `cwd` forms on other machines. The fixture and trial T6 cover both. One limitation is known and not fixed: an offline mapped drive letter (HN-5).

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** after the deferral, ask Claude Code's own session list once and match working folders with the deferral's own comparison; name the holders and print every stop command.
  - Why: the command is documented, read-only and cross-platform. It needs no new dependency and gives exactly the id the user needs to type. The user chose it at intake.
- **Option B (rejected):** read each process's working folder from its memory (the process environment block), as the incident's hand-written scripts did.
  - Why rejected: it reads other processes' memory, a safety check stopped it in the first design pass, and the user ruled it out.
- **Option C (rejected):** list the processes holding a handle in the folder (Windows Restart Manager, `handle.exe`, `lsof`).
  - Why rejected: it needs a native API or a third-party tool, which means a new dependency. It differs per platform and still cannot give a `claude stop` id.
- **Option D (rejected):** recognise "this session" by its working folder.
  - Why rejected: in the incident, two sessions shared the folder. Folder matching would hide the other session's stop command.
- **Option E (rejected):** run the lookup before the probe and let it decide the deferral.
  - Why rejected: an unreadable or empty list would then be able to make a held tree look free (journal lesson 2026-10-16).
- **Option F (rejected):** a separate text-only path matcher for holders.
  - Why rejected: it can disagree with `_inside`, so the report could say `none-found` about a tree the deferral found held through a link or a short name (critic WARN; user decision 2026-10-18).
- **Option G (rejected):** print at most five stop commands, then a count.
  - Why rejected: the brief requires that a stop command is never cut. The user chose every command, with the rest of the line bounded by the existing shortening steps.
- **Option H (rejected):** recognise this session through `CLAUDE_JOB_DIR` or `CLAUDE_SESSION_ID` as well.
  - Why rejected: `CLAUDE_CODE_SESSION_ID` gives the full id and matches exactly; more variables only add ways to match the wrong record.
- **Option I (rejected 2026-10-30):** on timeout, end the child's whole process tree (`taskkill /T /F`, `os.killpg` on a new session).
  - Why rejected: the background supervisor can be a descendant of a `claude` client, so a tree kill could end the supervisor and every background session (HN-9). With output in a temporary file, the time bound holds without ending descendants.
- **Option J (rejected 2026-10-30):** read the output through pipes with a bounded wait, and close the pipes by force.
  - Why rejected: a grandchild can keep a pipe open, and without a tree kill the wait has nothing to end it. A temporary file needs no wait at all (A5).
- **Option K (rejected 2026-10-30):** accept whatever `shutil.which("claude")` returns.
  - Why rejected: on Windows a bare-name lookup also searches the current folder, so a `claude.exe` planted in the repository would run (A2, review warning W1).
- **Option L (rejected 2026-10-30):** accept UNC and device paths as `cwd` and pass them to `realpath`.
  - Why rejected: on Windows `realpath` opens the path, which can reach a network host or a device. Such a record reads unreadable, so the reading is `cannot-tell` (A3, review warning W2).
- **Option M (rejected 2026-10-31):** start `claude` with the main checkout as its working folder.
  - Why rejected: a `.cmd` wrapper looks up its interpreter in the current folder first, so a `node.exe` planted in the repository root would run. Starting from the resolved program's own folder closes this (B1, C1).
- **Option N (rejected 2026-11-18):** set `NoDefaultCurrentDirectoryInExePath` in the child environment.
  - Why rejected: it creates an environment variable, which the user's standing rule forbids, and the neutral working folder already covers the planted-interpreter case (C1).

---

## Uncertain Assumptions

- `VERIFIED via .claude/scripts/cleanup_delivered.py:591-593, 628-631`: `standing-tree` and `in-use` are the only reasons with action `deferred`, and each sets `run.finish_needed`.
- `VERIFIED via .claude/scripts/cleanup_delivered.py:888-906`: the tail (repairs, finish) is never cut; the line can exceed 600 only by the tail.
- `VERIFIED via .claude/scripts/cleanup_delivered.py:104-110, 379-380`: `_norm` and `_inside` are the comparison `Run.is_standing` uses; `_inside` compares after `os.sep`, so `tree-2` is not inside `tree`.
- `VERIFIED via .claude/scripts/cleanup_delivered.py:75-80`: `_exec` folds `TimeoutExpired` and `OSError` into exit code 1, which is why the lookup has its own runner.
- `VERIFIED via .claude/scripts/cleanup_delivered.py:953-980`: the orphan report, `clean_branches` and `clean_remote` sit inside `if not run.halted:`, and `finish_command` and `build_line` follow it; the lookup goes between them.
- `VERIFIED via .claude/scripts/tests/test_cleanup_delivered.py:2803-2818, 2075-2088, 1927-1943`: three things are pinned. The finish command is last and whole. It appears exactly once. The line is at most 600 characters in the synthetic and the long-root cases.
- `VERIFIED via .claude/scripts/tests/test_flat_worktree.py:263-284`: `write_exe` writes `name.exe` on Windows, so a fake `claude.exe` in `Tools.bin` is found first by `shutil.which`; a `.cmd` wrapper test needs its own folder holding no `claude.exe`.
- `VERIFIED via .claude/scripts/tests/test_flat_worktree.py:62-79`: `clean_env` does not strip `CLAUDE_CODE_SESSION_ID`, so the suite must strip it itself, or a run inside a real session would leak its id into the tests.
- `VERIFIED by running claude agents --json --all on the user's machine (2026-10-30, 23 records)`: the shape of the output.
  - The top level is a bare list. Standard output has no byte-order mark and no banner.
  - Each record has the keys `cwd` (text), `id` (text), `kind` (text), `name` (text), `pid` (whole number), `sessionId` (text), `startedAt` (whole number, milliseconds), `state` (text) and `status` (text).
  - Observed values: `id` was 8 lowercase hex characters in 23 of 23 records, and `sessionId` a lowercase UUID in 23 of 23. `kind` was only `background`, and `state` was one of `blocked`, `done`, `stopped` and `working`.
  - On this machine the names were ASCII only, and every `cwd` was a drive path.
  - The cleanup ignores `pid` and `status`.
  - A `stopped` or `done` record is still reported when its folder matches. A `done` background session (idle) did hold a folder in the incident behind this work.
  - **Part of the deliverable:** a committed fixture of this shape, `.claude/scripts/tests/fixtures/claude_agents_list.json`, with synthetic values and one name other than ASCII written as raw UTF-8. Also part of it is trial T6 (`T6RealAgentsListTests`) in `test_cleanup_delivered_trials.py`: opt-in and read-only, it skips when `claude` is absent, and it runs the real command and checks the parse with the production helpers.
- `VERIFIED on the user's machine (2026-11-19, E1), by comparing live processes with the list's `pid` field`: `claude agents --json --all` lists background sessions only; every record has kind `background`. An interactive session started by typing `claude` in a PowerShell window (parent process `powershell.exe`, command line a bare `claude.exe`) is not in the list, while the workers of background sessions are. The list is not scoped to the folder it is run from: it showed sessions of several projects. So a terminal session, an editor or another program standing in a deferred folder is never named, which is why the `none-found` text and the fixed note say only what the list proves (HN-4, HN-8).
- `VERIFIED via a check in a real session (user, 2026-10-18)`: `CLAUDE_CODE_SESSION_ID` holds the running session's full UUID and equals that session's `sessionId` in the list exactly. `CLAUDE_JOB_DIR` (last folder name = 8-character id) and `CLAUDE_CODE_AGENT` are also set; neither is read. `CLAUDE_CODE_SESSION_ID` is provided by Claude Code itself and is only read, never created or set (2026-11-18, C2). No new environment variable, switch or override is introduced anywhere by this change, so no visible-file alternative is needed.
- `VERIFIED via claude stop --help (user, 2026-10-18)`: "Usage: claude stop <id>", the 8-character `id` the list shows.
- `ASSUMED, partly verified 2026-10-30`: on Windows, Claude Code prints `cwd` as a native path. All 23 records on one machine were drive paths. If another machine prints the Git Bash form, HN-5's rewrite handles it. A UNC path, a device path or any other form reads as unreadable, so the item says `cannot-tell`, never a false `none-found`.
- `VERIFIED 2026-10-30 (was ASSUMED)`: `--all` lists ended sessions; `done` and `stopped` were seen. Decided either way (Open Question 4): every match is reported; a needless stop command costs less than a hidden holder.
- `ASSUMED, no longer load-bearing (2026-10-30)`: running `claude agents` registers no session and starts no background service. Since A1 the cleanup ends no descendant of its child, so even if the command started a service, the cleanup would not end it. The call-log test still proves the cleanup calls nothing else.
- `VERIFIED via the code review (2026-10-30)`: on Windows `os.path.realpath` opens the path to resolve links, which is why HN-5 filters forms before calling it. A drive letter mapped to an offline share can still block there; this is a known limitation, not covered by the 25-second bound.

---

## Failure Modes & Mitigations

- **FM:** the list is unreadable, slow or malformed, and a held tree is reported free.
  - **Mitigation:** HN-1, HN-3 and HN-4. The reading cannot change the decision, and every failure reads `cannot-tell`. Tests cover a missing program, a launch failure, a timeout, a non-zero exit, garbage output and an exception.
- **FM:** `claude` is a `.cmd` wrapper; on timeout only `cmd.exe` is killed, the real program keeps running, and the cleanup hangs waiting for its output.
  - **Mitigation:** HN-2 and HN-9. The output goes to a temporary file, not a pipe, so nothing waits for the real program. `_end_own_child` ends only the runner's own child, and the lookup ends within 25 seconds. A test runs a real `.cmd` wrapper whose child keeps running past the ceiling. It checks the time bound and that the cleanup returns `cannot-tell`; it does not require the grandchild to end (journal 2026-10-04, on proving host behaviour with a real invocation).
- **FM:** a tree kill on timeout ends Claude Code's background supervisor, and with it every background session.
  - **Mitigation:** HN-9 forbids ending any descendant. No `taskkill`, `killpg` or new session is used. The tripwire forbids `taskkill` and `killpg` everywhere and allows `proc.kill()` only inside `_run_holder_list`.
- **FM:** a `claude.exe` planted in the repository runs when the cleanup looks up `claude`.
  - **Mitigation:** HN-2 accepts only an absolute path whose folder is neither the current folder nor the main checkout root. A test plants a fake in the current folder and expects "the claude command was not found".
- **FM:** `claude` is a `.cmd` wrapper, and the interpreter it calls (`node`) is looked up in the current folder first, so a `node.exe` planted in the repository root runs.
  - **Mitigation:** HN-2 (B1). The runner starts `claude` with its working folder set to the resolved program's own folder, never the main checkout, so the wrapper's current-folder lookup finds only that folder. This neutral folder is the whole mitigation; no environment variable is set (C1). A test asserts the `Popen` keyword arguments (`cwd` equals that folder, no `env` passed) and the logged working folder.
- **FM:** a `cwd` naming a UNC or device path makes `realpath` reach a network host or a device.
  - **Mitigation:** HN-5 rejects these forms, and any NUL, control character or U+FFFD, before `realpath`; such a record is unreadable. An offline mapped drive letter remains a known limitation.
- **FM:** a huge or endless output fills memory.
  - **Mitigation:** HN-2 reads at most 4 MiB; more reads "not in the expected form".
- **FM:** the report says the folder holds no session when a Claude Code session typed into a terminal, an editor or another program is standing in it, so the user looks no further (2026-11-19, E1).
  - **Mitigation:** E2. The `none-found` bracket reads `[no background session in the list is in it]`, and the fixed note says the list shows background sessions only and that a session typed into a terminal, an editor or another program may also hold the folder. Tests pin both texts and the absence of the old ones.
- **FM:** the holder report contradicts the deferral (a link or a short name).
  - **Mitigation:** HN-5 uses the deferral's own `_inside`. A test holds the tree through a link.
- **FM:** a session's name forges a `; stop:` or `; finish:` part, a bracket, or a new line.
  - **Mitigation:** HN-6 cleaning. A probe test uses a name holding `; finish: rm -rf ~"]\n\u2028`. Journal 2026-10-05, on neutralising echoed fields. A lookalike separator (U+037E, U+FF1B) or an invisible format character (a tag character, U+2060) is folded or dropped by D2's NFKC and category steps before the replacements run.
- **FM:** a stale UNC or offline-drive entry on PATH is resolved while `claude` is searched for, and the lookup blocks or reaches the network.
  - **Mitigation:** D4. `_find_claude` skips PATH entries by text checks only and runs `_norm` only on an actual hit's folder.
- **FM:** a printed stop command carries attacker text or hits the wrong session.
  - **Mitigation:** the id must pass the 8-hex check, so nothing free-text enters the command. Journal 2026-10-16, on free text handed to a native program from Git Bash.
- **FM:** many holders push the line far past 600 characters.
  - **Mitigation:** each stop command is short and fixed in form (21 characters); the brackets, note and warning are bounded or fixed. A probe uses twenty holders with a 600-character finish command and checks that every stop is present and the finish stays last and whole. A second test checks the `+k more` invariants: shown + k equals the holders, k > 0, every stop present, line at most 600 (journal 2026-10-05, on bounding the summary).
- **FM:** the user stops the session that ran the cleanup and loses the run's output.
  - **Mitigation:** HN-7. A recognised session gets no stop command, and an unrecognised one brings the fixed warning.
- **FM:** a test reaches the developer's real `claude` and real sessions.
  - **Mitigation:** every world installs a fake `claude` that prints `[]`. Failure paths patch `shutil.which` or `_run_holder_list` in process. The call-log invariant fails the test on any `claude` call other than `agents --json --all`. The only test that runs the real command is trial T6, which is opt-in and read-only.
- **FM:** the fake drifts from the real output, and the tests pass against a shape the real command never prints.
  - **Mitigation:** the committed fixture copies the shape verified on 2026-10-30 (A8), and trial T6 checks the real output with the production helpers.
- **FM:** the closing paragraph tells the user the work is delivered when it is only a draft pull request.
  - **Mitigation:** HN-11's conditional wording, VOCABULARY's meaning of "delivered" winning, and the `/advance` condition on the `removed` form.
- **FM:** the model reads the closing paragraph as an order and runs `/stop` mid-chain.
  - **Mitigation:** HN-11's precedence sentence (journal 2026-10-05, on text delivered to the model), and the paragraph is out of `/task` Step 6.

---

## Open Questions for User

- [x] **Open Question 1 — Which id does `claude stop` take?** The list gives both an 8-character `id` and the full `sessionId`. **Recommendation:** print `claude stop <8-character id>` only if trial A shows `claude stop --help` (or the documentation) accepts it. Otherwise print the full `sessionId`, checked against the UUID form, and still show the 8-character id in the bracket.
  - **Answer (user, 2026-10-18):** `claude stop` takes `<id>`, the 8-character `id` the list shows (verified from `claude stop --help`: "Usage: claude stop <id>"). Print the short id. No trial needed.
- [x] **Open Question 2 — How long to wait for `claude agents` before `cannot-tell`?** **Recommendation:** a fixed 15 seconds, as the constant `HOLDER_TIMEOUT_SECONDS`, with no flag. That is long enough for a cold start of the CLI and short enough not to stall `/advance`. Only deferred runs pay it.
  - **Answer (user, 2026-10-18):** accepted. `HOLDER_TIMEOUT_SECONDS = 15`, no flag; it also holds for a `.cmd` wrapper (HN-2, HN-9).
- [x] **Open Question 3 — Do state values other than `done` need their own wording?** **Recommendation:** no. Show the cleaned state as it is, for every value including unknown ones, and add no closed set now. The user reads `done`, `running` or anything else and decides.
  - **Answer (user, 2026-10-18):** accepted. No special wording per state; every state value is shown cleaned, unknown ones included (HN-6).
- [x] **Open Question 4 — If trial A shows that `--all` also lists ended sessions, what then?** **Recommendation:** keep `--all`, as decided at intake. Leave out only the state values that trial A shows to mean "process ended", and list them in this contract by amendment. Otherwise report every match, because a needless stop command costs less than a hidden holder.
  - **Answer (user, 2026-10-18):** keep `--all` and report every match, ended sessions included if the list shows them. No state is filtered out.

---

## Critique

**Critic:** contract-critic
**Date:** 2026-10-18
**Verdict:** blockers-found

### Findings

- **[BLOCKER] The pinned closing paragraph says "Delivered." at the end of `/flow`, where nothing has been delivered yet**
  - **What is wrong:** HN-11 prints the paragraph, unconditionally, at the end of `/flow` Step 8. `/flow` ends at "shipped": its Step 7 has `/ship` open a *draft* pull request and set `status: shipped` (`skills/flow/SKILL.md` lines 497-506), and its own layer table says it runs "from intake through to shipped" (line 557). At that moment nothing is merged, so the cleanup itself would answer "not delivered yet". The sentence the test pins word for word therefore tells the user something false in one of its three places. `/advance` and `/task` have a "delivered" condition in HN-11; `/flow` has none.
  - **Prior artifact ignored:** `VOCABULARY.md` line 47, **Contract Delivery** (the GitHub-verified merge into the default branch, "never inferred"), and line 56, **Delivery cleanup** ("reads 'not delivered yet' until then").
  - **Where in this contract:** `## Data Shapes → HN-11` — "`skills/flow/SKILL.md`, at the end of `## Step 8`" with the paragraph opening "Delivered."
  - → Addressed by: HN-11 now pins a conditional paragraph ("Once the pull request is merged and the work is delivered, …"), says VOCABULARY's Contract Delivery meaning wins and the paragraph never claims delivery, and keeps it at the end of `/flow` Step 8 where `shipped` is reported.

- **[WARN] `/task` Step 6 is not an end-of-run report, so "printed when the chain it started ends delivered" has nowhere to happen**
  - **What is wrong:** `/task` Step 6 is the automatic, pre-authorised hand-off to `/design-first` (`skills/task/SKILL.md` lines 525-561). `/task` hands over mid-chain and never sees the chain end, so the condition HN-11 gives it cannot be observed from that step. A "Delivered. End this session" paragraph placed inside a step that says "the chain runs itself" also pulls against that step's own instruction. The brief placed the paragraph in "each skill's existing end-of-run report section", and `/task` has no such section.
  - **Prior artifact ignored:** the brief's intake answer (`.claude/work-items/2026-10-18-cleanup-names-the-session-holding-a-worktree.md` line 58), and `JOURNAL.md` **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate** ("Check each shipped rule against the skills that already exist before approving it").
  - **Where in this contract:** `## Data Shapes → HN-11` — "`skills/task/SKILL.md`, at the end of `## Step 6`, printed when the chain it started ends delivered."
  - → Addressed by: the paragraph moves out of `/task` Step 6 into `## Status lifecycle` as the note on the `shipped` status; the SkillWiringTests check names that section.

- **[WARN] The new path matcher sits beside the folder comparison the standing-tree rule already uses, and the contract does not name that comparison**
  - **What is wrong:** the standing-tree rule decides the deferral with the private helpers `_norm` (real path, then Windows case folding) and `_inside` (equal, or inside), in `cleanup_delivered.py` lines 104-110, called from `Run.is_standing` at lines 379-380. HN-5 defines a second comparison that works on path text only. The contract does not list `_norm` or `_inside` under Reused Mechanisms and does not say why they cannot be reused. HN-5's reason for the difference, that a record's folder is never resolved, is sound, but it is never stated against the existing helper. Because the two comparisons differ, the explanation can contradict the decision: a folder reached through a link or a short (8.3) Windows name can be "inside" for the deferral and still read `none-found` for the holders.
  - **Prior artifact ignored:** `MECHANISMS.md` line 67, **Delivery cleanup** (the standing-tree rule is part of it), and `VOCABULARY.md` line 58, **Standing tree**.
  - **Where in this contract:** `## Data Shapes → HN-5` — "Matching by path text only", and `## Extension Points` item 1 — "A path matcher (HN-5)."
  - → Addressed by: HN-5 now calls the existing `_norm` / `_inside` (named in Reused Mechanisms), drops the separate matcher (Option F rejected), and adds a link test.

- **[WARN] The time limit cannot be enforced when `claude` is a `.cmd` wrapper on Windows, and the fake test program cannot show this**
  - **What is wrong:** HN-2 expects `claude.cmd` to be found. On Windows, Python's `subprocess.run` handles a timeout by killing only the process it started and then waiting, with no limit, for that process's output to close. For a `.cmd` wrapper the process it started is the Windows command interpreter (`cmd.exe`), and the real program it launches keeps the output open, so the cleanup can hang well past `HOLDER_TIMEOUT_SECONDS`. The test fake is a different kind of program: `write_exe` (`test_flat_worktree.py` lines 263-284) builds a single `.exe` launcher, so the timeout test passes in a setup the real install may not have. No entry under Failure Modes covers a hang, and trial A does not exercise the timeout.
  - **Prior artifact ignored:** `JOURNAL.md` **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** ("prove it with one harmless invocation before the code depends on it"), and **2026-10-16 — Never let free text start an argument handed to a native program from Git Bash** ("A test that passes the value as an argument list without a shell cannot show this; only a replay in the real shell can").
  - **Where in this contract:** `## Data Shapes → HN-2` — "`claude.exe` and `claude.cmd` are both found … and a time ceiling", and `## Failure Modes & Mitigations` — "a timeout" is listed only as a tested input.
  - → Addressed by: HN-2's own runner and HN-9's single exception end the whole child tree on timeout with bounded pipe waits (25 s worst case); `shutil.which` kept; a real-wrapper test whose child keeps running past the ceiling; a hang Failure Mode added.

- **[WARN] The five-command cap contradicts an acceptance criterion, and the conflict is not raised with the user**
  - **What is wrong:** the brief requires that each `claude stop <session id>` command "is never cut by the line's length limit, on the same rule as the existing finish command". HN-8 prints at most five and replaces the rest with `+k more sessions, see --json stop_commands`. The cap is a reasonable answer to the size-budget lesson, but it changes an acceptance criterion. That is the user's call, and the contract records it as a settled invariant instead of an Open Question.
  - **Prior artifact ignored:** the brief's acceptance criterion (`.claude/work-items/2026-10-18-cleanup-names-the-session-holding-a-worktree.md` line 33), and `JOURNAL.md` **2026-10-05 — A size budget must bound the summary it adds, not only the items it keeps** (the lesson behind the cap, which makes the conflict real rather than accidental).
  - **Where in this contract:** `## Data Shapes → HN-8` — "at most five of them. Past five comes one `; stop: +k more sessions, see --json stop_commands`."
  - → Addressed by: the user chose no cap; HN-8 prints every stop command in the never-cut part, the rest of the line stays bounded by the existing shortening steps, and the twenty-holder test asserts all twenty.

- **[WARN] Two design decisions are left to the implementer, which contradicts the hand-off's own amendment rule**
  - **What is wrong:** HN-7 lets the implementer choose which environment variables the code reads ("the code reads only the variables the trial saw set"). The Uncertain Assumptions let the implementer add a path rule ("a Git Bash form gets one more normalising rule if seen"). The pre-written TASK block says the opposite: "if any differs from the contract, stop and report an AMENDMENT, do not guess". These are Open Questions placed in the invariants and the assumptions, so whatever trial A finds becomes part of the design without the user seeing it.
  - **Prior artifact ignored:** `JOURNAL.md` **2026-10-17 — Git for Windows lists files beneath an untracked junction; a parent-link check is load-bearing** (the last contract on this script had an ASSUMED platform behaviour turn out false after implementation), and **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work**.
  - **Where in this contract:** `## Data Shapes → HN-7` — "The implementer's first step records it in a trial, and the code reads only the variables the trial saw set"; `## Uncertain Assumptions` — "a Git Bash form gets one more normalising rule if seen"; `## Implementation Handoff` — "stop and report an AMENDMENT, do not guess".
  - → Addressed by: HN-7 reads only `CLAUDE_CODE_SESSION_ID` with an exact match (verified in a real session), HN-5 decides the Git Bash and other `cwd` forms in the contract, and trial A is removed; an unset-variable unit test stays.

- **[NIT] A timeout and a non-zero exit may look the same through `_exec`** — `_exec` (`cleanup_delivered.py` lines 75-80) turns a timeout or a launch error into exit code 1, with the cause only in its error text. HN-3 needs separate reasons for "gave no answer within <n> seconds" and "exited with code <n>", and it forbids quoting the error text. The contract does not say how the list reader tells the two apart once the call goes through `_exec`.
  - → Addressed by: the lookup no longer goes through `_exec`; `_run_holder_list` returns the closed results `answer`, `timeout`, `launch-failed`, `exit <n>`, each with its own fixed reason (HN-3).
- **[NIT] A halted run is not covered** — Extension Points places the lookup "after `clean_remote`". In `cleanup()` that call sits inside `if not run.halted:` (`cleanup_delivered.py` lines 962-968). A run that stops part-way, the halt rule in `MECHANISMS.md` line 67, can have earlier items already deferred as `standing-tree`. HN-1 does not say whether those items get a Holder reading.
  - → Addressed by: HN-1 and Extension Points place the lookup after the whole `if not run.halted:` block, so items deferred before a halt still get a Holder reading; a halted-run test is added.
- **[NIT] The Adjacent Areas line is not the standard wording and still carries an instruction for someone else to act on** — "the main session should run it before approval and amend this line". The caller has since confirmed that the cross-area scan found nothing and the area derives as `uncategorized` (the fallback bucket), so the content is accurate. Only the wording and the leftover instruction are off.
  - → Addressed by: the section now uses the standard line and records the scan result (area `uncategorized`, no adjacent area above threshold).
- **[NIT] "Folder holder" can be misread as any program holding the folder** — `VOCABULARY.md` line 58 (**Standing tree**) already uses "holds" for any process, including a shell or another program. The new term narrows "holder" to Claude Code sessions, so a terminal that holds a deferred tree "holds" it but is not a "Folder holder".
  - → Addressed by: the proposed definition now says a Claude Code session only, and states how it is narrower than "holds" in Standing tree.
- **[NIT] Lessons referenced leaves out a lesson the contract does follow** — trial A follows **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work**, but that entry is not in `## Lessons referenced`.
  - → Addressed by: the entry is now in Lessons referenced, heeded by the real-session check of `CLAUDE_CODE_SESSION_ID` and the real-wrapper timeout test.

### Applicable journal entries

- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** — heeded by trial A, which checks the environment variables and `claude stop --help` before any code depends on them. Partly undercut by the WARN on decisions left to the implementer, and not exercised for the timeout path (WARN above).
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by the list-reader tests (missing program, `{}`, `[1]`, a record with no `cwd`, an id in the wrong form).
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded by the `process_control_hits` tripwire, which plants each forbidden call in plain form.
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate** — heeded by HN-11's precedence sentence. Violated in part for `/task` Step 6 (WARN above).
- **2026-10-05 — A size budget must bound the summary it adds, not only the items it keeps** — heeded by HN-8 (five stop commands, then a count) and the twenty-holder test. It is also the source of the conflict with the brief (WARN above).
- **2026-10-05 — Neutralise every field echoed from untrusted input, not only the body** — heeded by HN-6 (name, state and kind cleaned; the working folder never in the line; the id format-checked) and the forging test.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded: no lookup block is touched, and `test_skill_script_lookup.py` is on the run list.
- **2026-10-16 — An unset ownership field is not proof of ownership** — heeded by HN-3 and HN-4 (an unread or partly unreadable list reads `cannot-tell`, never `none-found`) and by rejecting Option E.
- **2026-10-16 — Never let free text start an argument handed to a native program from Git Bash** — heeded by HN-2 (fixed argument list) and HN-6 (a stop command holds only a format-checked id). Its replay point is cited in the timeout WARN above.
- **2026-10-16 — A skill step that moves the shell must come after every later step that reads the working tree** — not addressed. The contract does not need to, because the skill edits add text only and no `cd`.
- **2026-10-17 — Git for Windows lists files beneath an untracked junction; a parent-link check is load-bearing** — not addressed directly. Nothing is deleted from a git-listed path. It is cited in the WARN on decisions left to the implementer, as the precedent for an ASSUMED platform behaviour turning out false.
- Remaining entries (install mode, root locator, guard documentation, shared-state markers, rules-file defaults, host size cap, cleanup trigger timing, script location, brief-linkage readers, tracker titles, project-file refusals, loosening a guard, line endings) — not addressed. None of them matches this contract.

### What the critic did not check

- `.claude/registries/INTEGRATION.md` does not exist in this worktree, so the integration-surface check used the contract's own table only. No surface crosses a backend-to-frontend boundary, so checklist item 7 does not apply.
- `.claude/.scout-cache/registry-digest.md` does not exist. The three registries were read in full instead, and no per-domain project files exist under `.claude/registries/`.
- CodeGraph tools were not available in this session. Source claims were checked with direct reads of `cleanup_delivered.py`, `test_flat_worktree.py` and the three skill files.
- `.claude/north-stars/` holds no files, so checklist item 13 produced no findings.
- The critic placed this critique in the contract's existing empty `## Critique` slot, as the template lays it out, rather than adding a second `## Critique` heading at the end of the file.

---

## Lessons referenced

- **2026-10-04 — Do not rely on a host expanding a variable in a form nobody has seen work** — heeded by HN-7 (the session variable was checked in a real session before the design depends on it) and by the real `.cmd` wrapper timeout test (HN-2).
- **2026-10-05 — Neutralise every field echoed from untrusted input, not only the body** — heeded by HN-6 (name, state and kind cleaned; cwd never shown in the line) and the forging probe test.
- **2026-10-05 — A size budget must bound the summary it adds, not only the items it keeps** — heeded by HN-8: the cuttable brackets stay under the existing shortening steps, the note and warning are fixed, and each stop command is short and fixed in form; the twenty-holder probe checks the line exceeds 600 only by the counts and uncut parts. The user chose not to cap stop commands (acceptance criterion wins).
- **2026-10-16 — An unset ownership field is not proof of ownership** — heeded by HN-3 and HN-4. A failed read or an unreadable record never reads as `none-found` or as a free tree, and Option E is rejected.
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by tests that feed the list reader a missing program, an empty list, a non-list, a record without `cwd`, a `cwd` in an unaccepted form, and an id of the wrong form.
- **2026-10-16 — Never let free text start an argument handed to a native program from Git Bash** — heeded by HN-2 (a fixed argument list) and HN-6 (a stop command carries only a format-checked id).
- **2026-10-05 — Text delivered to the model must say which rule wins against a skill's gate** — heeded by HN-11's precedence sentence, its "VOCABULARY wins" rule, and its placement outside `/task` Step 6.
- **2026-10-05 — Never hide a forbidden name by hashing it when the test needs a positive control** — heeded by the new process-control tripwire, which plants each forbidden call in plain form as its positive control.
- **2026-10-15 — A skill that edits a block pinned by a lookup-block test must name that test** — heeded by keeping the closing paragraph out of the `CLN` lookup block, and by listing `test_skill_script_lookup.py` in the run-green list.
- **2026-10-15 — Reuse the existing brief-linkage reader; a second one misses edge cases** — heeded in spirit by HN-5: the holder match reuses `_inside` instead of a second comparison.
- **2026-10-18 — A subprocess timeout on Windows does not hold for a .cmd wrapper unless the child tree is ended** — its time-bound point is heeded through the temporary file (HN-2). Its "end the whole child tree" advice is overridden here by the 2026-10-30 lesson on shared supervisors (HN-9).
- **2026-10-30 post-review lessons (added by the amendment)** — heeded as follows:
  - never resolving a program by bare name after moving into a repository: HN-2;
  - ending only your own child when a tool can start a shared supervisor: HN-9;
  - backing a fake CLI with a captured real payload and an opt-in trial: the fixture and T6;
  - testing a stated time ceiling over the whole operation: the wrapper test;
  - keeping pure-parsing variants in a fast unit test: the parameterised unit class.
- **2026-10-31 second-review lessons (added by the second amendment)** — heeded as follows:
  - starting third-party tools from a neutral folder: HN-2 (B1) and Option M. The lesson's `NoDefaultCurrentDirectoryInExePath` half is not applied here, because the user's standing rule forbids creating an environment variable (C1, Option N);
  - a timeout or kill test must prove its scenario happened: the pidfile check in the real-wrapper test (B7);
  - one unpatched test pins a patched constant and its derived text: the pinned-constants test (B7);
  - a name-based tripwire must flag aliased imports and check exemptions by exact shape: the tightened tripwire (B7);
  - "printed last" text must say which ending wins: HN-11 (B5, and D1, which drops "printed last" and names the exact position in `/advance`).
- **2026-11-19 — Re-verify an external command's output after a contract changes how it is launched, and say in user-visible text only what the list proves (added by the last-review amendment)** — heeded by E1 (the list's coverage re-checked against live processes and recorded as VERIFIED) and E2 (the `none-found` bracket and the fixed note say only what the list proves).
- No active north-star: `.claude/north-stars/` holds no files, which confirms the brief's `north_stars: none`. Orthogonal to north-stars: none registered.

---

## Implementation Handoff

### 1. Holder reading, read-only proof, closing paragraph and version (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/cleanup_delivered.py`
- `.claude/scripts/tests/test_cleanup_delivered.py`
- `.claude/scripts/tests/test_cleanup_delivered_trials.py`
- `.claude/scripts/tests/fixtures/claude_agents_list.json`
- `skills/flow/SKILL.md`
- `skills/advance/SKILL.md`
- `skills/task/SKILL.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.cursor-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

**Pre-written TASK block:**
```
TASK: When Delivery cleanup defers a worktree as standing-tree or in-use, read Claude Code's
      session list once (claude agents --json --all), name each session whose working folder is
      inside that worktree (by the existing _inside), print `claude stop <id>` for every holder
      except the running session, with no cap, and say plainly when it cannot tell. Never stop
      anything except the cleanup's own timed-out claude child, with proc.kill() only and never
      its descendants. Add the fixed conditional
      closing paragraph to /flow, /advance and /task. Raise the version from 0.10.1 to 0.11.0
      (superseded 2026-11-19, E4: the shipped version is 0.22.0, a minor raise from master's
      0.21.0).
CONTEXT: concept contract at .claude/concepts/2026-10-18-cleanup-names-worktree-holder.md
         brief .claude/work-items/2026-10-18-cleanup-names-the-session-holding-a-worktree.md
FILES: the Files to touch list above
CONSTRAINTS:
  - No trial step: the CLI facts are settled in the contract (HN-5, HN-7, Open Questions 1-4).
    If anything you observe contradicts the contract, stop and report an AMENDMENT; do not
    guess and do not adopt a new rule. Never run `claude stop` or any real `claude` command;
    the only exception is trial T6 below, which runs the read-only `claude agents --json --all`
    and only when it is opted in.
  - FAILING TESTS FIRST. Write every test below and record which fail before any production edit.
    Do not weaken an existing test.
  - AMENDED 2026-10-30 (post-review): the code already exists. Bring it and its tests in line
    with A1-A9 of the contract's amendment note: replace _end_own_child_tree by _end_own_child
    (proc.kill() only; remove every taskkill, killpg and start_new_session); standard output
    to a temporary file with the 4 MiB limit; the shutil.which folder check; the HN-5 form and character
    rules; id stored as null in --json when it fails its check; "ends with" in /task. Replace
    the heavy end-to-end variants with the structure below. Record RED for the new and changed
    tests before the production edits.
  - AMENDED 2026-10-31 (second review): bring the code and tests in line with B1-B7 of the
    contract's amendment note: cwd = os.path.dirname(resolved claude path) (B1); null / empty-text
    fields stay present in --json (B2); document the _find_claude fallback and its pre-3.12
    limit in the module docstring (B3); strip U+200E, U+200F, U+061C, U+200B, U+FEFF (B4,
    now covered by the D2 category rule); the B5 placement sentence in /flow Step 8 (the
    /advance half is replaced by D1 below); rename trial T5 to T6
    (T6RealAgentsListTests) everywhere (B6); the new test items marked [B7] below. Do NOT
    implement the B8 follow-ups (Non-Goals). Record RED for new tests before production edits.
  - AMENDED 2026-11-18 (user rule: no created environment variables): C1 of the amendment note.
    _run_holder_list passes NO env argument to Popen; the child inherits the unchanged
    environment on every platform. Remove any NoDefaultCurrentDirectoryInExePath code, docstring
    text and test assertion. Keep cwd = os.path.dirname(resolved claude path). Never create, set
    or propose an environment variable as a toggle, override or setting; CLAUDE_CODE_SESSION_ID
    is only read (C2).
  - AMENDED 2026-11-19 (final review): D1-D5 of the amendment note. D1: do NOT reorder the
    /advance report block; keep master's order (`- Next command:` the first of the last two
    lines, then `- Cleanup:`, with `- Trees:` where master has it). Print the paragraph inside
    the block, directly before the `- Next command:` line. Remove the sentences "the paragraph
    follows the Cleanup line", "the Next command stays the very last line", "printed last" and
    "After the report block" from /advance; add one plain sentence saying the paragraph sits
    directly before the Next command line, inside the block, and that the Next command line
    keeps master's position; reconcile the skill's sentence "The last two lines matter most"
    with it. /flow is unchanged (Step 8 final report, never the push confirmation prompt).
    Take the block order from master's skills/advance/SKILL.md, not from this branch's copy.
    D2: clean list text in the order non-text rejected, unicodedata.normalize("NFKC"), drop
    unicodedata.category in {Cc, Cf, Zl, Zp}, replacements, cut to 60; remove the code-point
    list. D3: a non-string name/state/kind is an empty text, never str(value). D4: _find_claude
    never calls realpath or _norm on a PATH folder before a hit; it skips only empty or
    non-absolute entries and applies _norm to a hit's folder and once each to the current
    folder and the main root. D5: _end_own_child is `try: proc.kill()` / `except OSError: pass`.
    Do NOT build the D6 follow-ups. Record RED for new and changed tests before production edits.
  - AMENDED 2026-11-19 (last review): E1-E4 of the amendment note. E2: the none-found bracket is
    `[no background session in the list is in it]`, and HOLDER_NOTE is `note: the session list
    shows background sessions only; a session typed into a terminal, an editor or another
    program may also hold this folder`. Tests assert both new texts exactly and that neither
    "no Claude Code session in it" nor "only Claude Code sessions are checked" appears in the
    line or the source. The found and cannot-tell brackets and the verdict names are unchanged.
    E4: _run_holder_list's fifth result too-big maps to "the session list was not in the
    expected form"; a holder's JSON cwd is cleaned like the other list text (NFKC, control and
    format characters removed), display only, never used for matching. Version 0.22.0 in all
    five declarations.
  - Test world: build_world installs a fake `claude` with write_exe ONCE per Tools folder (like
    install_gh). It reads claude_config.json (stdout text, exit code, sleep seconds) and logs
    argv to claude_calls.jsonl. Its default prints `[]`. A cleanup env wrapper in this file
    strips CLAUDE_CODE_SESSION_ID, CLAUDE_SESSION_ID and CLAUDE_JOB_DIR unless a test sets them.
    assert_call_log_invariants gains: every claude call's argv is exactly
    ["agents", "--json", "--all"].
  - Fixture: commit .claude/scripts/tests/fixtures/claude_agents_list.json, a bare list in the
    shape verified on 2026-10-30 (keys cwd, id, kind, name, pid, sessionId, startedAt, state,
    status; no byte-order mark, no banner). Use synthetic values, states blocked, done, stopped
    and working, and one name other than ASCII written as raw UTF-8 (not a \u escape). The unit
    class below parses it with the production helpers.
  - StandingTreeTests, end to end, about six tests. All run with --dry-run except the halted
    run. Extend assertDeferredWithOneFinishLine: the item carries holders, finish stays last and
    appears once, and every `; stop:` part comes before `; finish:`.
      1 found, with the HN-1 comparison: --from the feature tree, a list holding one session
        whose cwd is <fw>/src (id bbfa6fec, name "worker", state done) -> found; the bracket
        reads `[held by bbfa6fec "worker" done]`; `; stop: claude stop bbfa6fec` is in the
        line; stop_commands == ["claude stop bbfa6fec"]; action, reason, exit code and finish
        command equal those of the same run with the default `[]` list
      2 two deferred trees with different holders -> each bracket names its own holder; both
        stops present, in first-seen order
      3 a halted run (not dry run): a tree deferred as standing-tree, then a halt on a tree
        planned after it, built as the link-target-vanished or failed rename-back test builds
        theirs -> the deferred item carries holders; outcome partial and exit code equal to
        the same run with the default `[]` list (HN-1)
      4 nothing deferred -> claude_calls.jsonl is empty; the report has no holders,
        stop_commands or holder_lookup key; the line is byte-identical to the run without the
        lookup
      5 link: a holder cwd that reaches the tree through a link (symlink on POSIX, junction on
        Windows; skip visibly if the link cannot be made) -> found, the same as the deferral
      6 in-use (Windows): the in-use test (test_a_tree_another_process_holds_reads_in_use...)
        also asserts holders is present (none-found with the `[]` default, bracket
        `[no background session in the list is in it]`) and the E2 note is present
  - One fast unit class, parameterised (subTest), with _run_holder_list patched to return each
    closed result and output; no git world. It covers _read_session_list, _holder_path and
    _holders_for:
      * results: launch-failed, timeout, exit 3, too-big (E4), answer. Each failure gives its fixed reason;
        the timeout reason never says "exited with code", and the exit reason never says "no
        answer within";
      * shutil.which -> None; -> a relative path; -> a path in the current folder; -> a path in
        the main checkout root: each gives "the claude command was not found", and _run_holder_list
        is never called;
      * output: "not json"; `{}`; `[1]`; a byte-order mark or a banner before the list; more than
        HOLDER_OUTPUT_LIMIT_BYTES -> "not in the expected form"; the committed fixture -> read
        with every field as HN-2 and Data Shapes say, the name other than ASCII intact;
      * records: no cwd and no match -> cannot-tell, "1 session records had no readable working
        folder"; the same plus one matching record -> found; an id "BBFA6FEC;rm" -> id null in
        the JSON (key present) and no stop command; pid and status ignored;
      * cwd forms: a drive path with `\` and with `/` -> accepted; Git Bash `/<drive>/<rest>` ->
        accepted on Windows; `\\host\share\x`, `\\.\x`, `\\?\C:\x`, `\\?\UNC\h\s` -> unreadable
        and realpath never called (patched recorder); `/tmp/x`, `/cygdrive/c/x`, a relative path
        -> unreadable on Windows; a cwd holding NUL, "\x1b", "\x85" or U+FFFD -> unreadable;
        `<fw>-2` does not match `<fw>`;
      * an 8.3 short name of the tree -> found; skip visibly (skipTest with the reason) when 8.3
        names are off on the volume;
      * HN-7: CLAUDE_CODE_SESSION_ID unset, or empty -> not recognised and the fixed warning when
        a stop is printed; only CLAUDE_SESSION_ID or only CLAUDE_JOB_DIR set -> not recognised;
        the value in upper case -> not recognised; equal to a holder's sessionId -> "(this
        session)", no stop for it; with a second holder exactly one stop and no warning; not
        recognised with two holders -> two stops plus the warning;
      * the reader raising RuntimeError -> "the session list could not be read (RuntimeError)".
      * [B7] a byte-order mark before the list, and a banner line before the list, each as its
        own case -> "not in the expected form";
      * [B7] a drive path written with `/` (C:/x) -> accepted and compared like C:\x;
      * [B7] pid and status ignored: records differing only in them read identically;
      * [B7] started_at: a non-integer (1.5, "123") and a boolean (true) -> null, key present;
        session_id failing the UUID form -> null, key present; name/state/kind not a string
        (true, 5, 1.5, [], {}, null) -> empty text, key present, and never the str() form such
        as "True" or "5" (B2, D3);
      * [B7, D2] list text holding U+200E, U+200F, U+061C, U+200B or U+FEFF -> stripped (B4);
        also U+200C, U+200D, U+2060, U+2064, U+00AD, U+180E, U+FFF9, U+FFFB, U+E0001, U+E0020,
        U+E0041 and U+E007F -> stripped (assert the category, Cf, inside the test too); every character the first list stripped (a C0 control, U+0085,
        U+009F, U+2028, U+2029, U+202A, U+202E, U+2066, U+2069) -> still stripped;
      * [D2] U+037E and U+FF1B each become `,` (NFKC folds them to `;`, then the replacement);
        a fullwidth quote U+FF02 becomes `'` and fullwidth brackets U+FF3B / U+FF3D become `(`
        / `)`; the order is proved by a case where a character is dropped only after NFKC;
      * [D4] _find_claude with shutil.which("claude") failing the check: PATH entries that are
        empty or relative are skipped; with no hit anywhere, _norm and os.path.realpath
        (patched recorders) are never called on a PATH folder, including a `\\host\share`
        entry; with a hit, _norm runs on that hit's folder only; a hit in the current folder or
        the main root is skipped and the search continues.
      * [D5] _end_own_child on a Popen whose kill() raises OSError (the child already exited)
        -> returns without raising, and the timeout reading still gives its fixed reason.
  - [B7] Pinned constants, one UNPATCHED test: HOLDER_TIMEOUT_SECONDS == 15,
    HOLDER_END_GRACE_SECONDS == 5, and with _run_holder_list returning timeout the reason is
    exactly "claude agents gave no answer within 15 seconds".
  - [B7] Popen arguments: record the keyword arguments _run_holder_list passes to Popen and
    assert stdin is subprocess.DEVNULL, stderr is subprocess.DEVNULL, stdout is a file object
    and not subprocess.PIPE, shell is falsy, cwd == os.path.dirname(resolved claude path), and
    no env keyword is passed (absent or None, on every platform; C1). In a world run, the fake logs its
    working folder and the test asserts it equals the fake's own folder, not the main checkout.
  - Real wrapper timeout test (both platforms): a wrapper alone in its own folder first on PATH,
    with no claude.exe beside it: on Windows `claude.cmd` that calls the fake with %*, on POSIX
    an sh script `claude` that runs the fake as a child and cannot exec it (the script does work
    after the fake returns, so exec is not possible). The fake sleeps 60. Patch
    HOLDER_TIMEOUT_SECONDS=2 and HOLDER_END_GRACE_SECONDS=2. Assert: shutil.which picks the
    wrapper; the lookup reads cannot-tell with the timeout reason; the whole cleanup call,
    per-record path checks included, returns within 2 + 2 + 2 + 3 seconds. Do not assert that
    the grandchild has ended (A1), and do not sleep after the timeout.
    [B7] The test must prove its scenario ran: the fake writes its own pid to a pidfile on
    start; after the call the pidfile exists and that pid is alive, else the test fails with
    "scenario not exercised". It also asserts that production started the wrapper (the
    recorded Popen argv[0] is the wrapper path). The test cleans the grandchild up itself
    afterwards, outside the timed call.
  - Read-only proof:
      (a) In process, patch os.kill, subprocess.Popen.kill, subprocess.Popen.terminate,
          subprocess.Popen.send_signal and _end_own_child with recorders, and record every
          subprocess argv. In the found, none-found and failure runs: zero calls. In the timeout
          run: _end_own_child called exactly once, with the Popen _run_holder_list created, and
          Popen.kill called once on that Popen; os.kill, terminate and send_signal never called;
          no argv other than the claude one.
      (b) A source tripwire, process_control_hits, beside forbidden_hits and over the same
          code_tokens. It flags, everywhere and with no exemption: taskkill, killpg,
          start_new_session, os.kill, terminate, send_signal, signal, system, popen, startfile,
          TerminateProcess, OpenProcess, run, call, check_call, check_output, every spawn* and
          exec* name, posix_spawn; bare strings "stop", "kill", "taskkill", "pkill", "killall",
          "Stop-Process", "rm", "del" and "rmdir"; any string holding "claude stop" that is
          passed in an argument list; and `.split()` or shlex.split applied to text starting with
          "claude stop". Exactly three exemptions exist, each for one name only:
          subprocess.run inside _exec (the existing git and gh runner, unchanged); Popen
          inside _run_holder_list; and the kill attribute (proc.kill()) inside _end_own_child,
          which is reachable only from _run_holder_list. Any load of the name _end_own_child
          other than its single call in the timeout branch of _run_holder_list is flagged (by
          AST). Tests: a planted positive control for each token outside those places; a
          planted taskkill or killpg inside _exec, _run_holder_list or _end_own_child is still
          flagged, as is a run call in any function other than _exec; the exempt set is exactly
          those three pairs; a negative control proving the text "claude stop %s" used to build
          a message is not flagged; and the real source passes. The existing
          ForbiddenTokenScanTests stay green.
          [B7, amended D5] Tightened: the body of _end_own_child must be, by AST shape
          (a docstring aside), exactly one try statement whose body is exactly one expression
          statement that calls `<its first parameter>.kill()` with no arguments, with exactly
          one handler, `except OSError:`, whose body is only `pass`, and no else or finally.
          So the function holds exactly one `<first parameter>.kill()` call with no arguments;
          anything else is flagged (a bare except, a broader exception, a second call, a kill
          with arguments). Also flag, everywhere:
          `import subprocess as <alias>`, `from subprocess import ...`, `from os import ...`,
          asyncio.create_subprocess_exec / create_subprocess_shell (any
          asyncio.create_subprocess_*), any import of pty or ctypes, and the names
          CreateProcess, CreateJobObject and TerminateJobObject. Each new rule has its own
          planted positive control.
  - PureLogicUnitTests, with build_line on synthetic items and a short synthetic finish command:
      * the bracket forms for found, none-found (`[no background session in the list is in
        it]`, E2) and cannot-tell, asserted through build_line, and the E2 note text exactly;
      * `+k more`: assert invariants only, never character counts: shown + k == the holders,
        k > 0, every stop present, and the line is at most 600 characters;
      * every stop command printed, no cap, none cut at any shortening step;
      * the HN-8 order (repair, note, warning, stops, finish);
      * [B7] cross-item first-seen stop order: two deferred items, the second naming a session
        already named by the first plus a new one -> each stop once, in first-seen order
        across items, and stop_commands equals the printed order;
      * the existing 600-character finish test, unchanged;
      * a test with 20 holders and a 600-character finish: all 20 stops present, stop_commands
        has 20 entries, and the finish stays last and whole;
      * the forging probe: name `x; finish: rm -rf ~"]` plus "\n", "\u2028", "\x1b[31m" and
        a 200-character tail -> exactly one "; finish: ", no control or separator
        characters, the name cut to 60 characters, and no stop for an id "BBFA6FEC;rm".
  - SkillWiringTests: with read_skill and section, the HN-11 paragraph, copied verbatim from the
    contract (it starts "Once the pull request is merged and the work is delivered"), appears
    exactly once in section(flow, "Step 8"), section(advance, "Step 3") and
    section(task, "Status lifecycle"), and does not appear in section(task, "Step 6"). Each of
    the three sections also says the model must not run /stop itself. No section contains the
    old opening "Delivered. End this session". [D1] In section(advance, "Step 3"): the report
    block's line order equals master's (`- Next command:` before `- Cleanup:`, `- Trees:` where
    master has it); the paragraph is inside the report block, directly before the
    `- Next command:` line; the section says so in one sentence and says the Next command line
    keeps its position; "The last two lines matter most" is still present; and none of "follows
    the `Cleanup:` line", "the very last line", "printed last" or "After the report block"
    appears. [B5] section(flow, "Step 8") says the paragraph belongs to the final report, not
    to the push confirmation prompt.
  - Trial T6 (T6RealAgentsListTests) in test_cleanup_delivered_trials.py, opt-in like the
    file's other trials. It skips with a visible reason when `claude` is absent, and is
    read-only: it runs only `claude agents --json --all` and never `claude stop`. It runs
    through _read_session_list, from the main root, and parses with the production helpers
    (_read_session_list, _holder_path). It checks: a bare list; each record an object whose
    key set is a superset of {cwd, id, kind, name, pid, sessionId, startedAt, state, status};
    id 8 lowercase hex or null; sessionId a lowercase UUID or null. A cwd that _holder_path
    does not accept is counted as unreadable, never a failure. It prints counts only, never
    names or folders.
  - GREEN: implement HN-1 to HN-11 exactly. Add the HN-11 paragraph and the precedence
    sentence to the three skills; in /advance, state that it is printed only when the Cleanup
    line has the `removed` form. Do not touch any CLN lookup block. Leave _exec unchanged.
    Update the module docstring's rule list. Version 0.10.1 -> 0.11.0 in all five declarations
    (superseded 2026-11-19, E4: 0.22.0, a minor raise from master's 0.21.0).
  - Run green: test_cleanup_delivered.py (whole), test_cleanup_delivered_trials.py,
    test_skill_script_lookup.py, test_plugin_manifests.py, test_check_version_bump.py. Report
    the RED list, then the GREEN run, with exit codes.
  - Do not invent data shapes; the contract is authoritative. Do not edit any registry or an
    earlier contract.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-18-cleanup-names-worktree-holder.md
  contract_status: approved
```

### 2. Scope note on review

This contract has one sub-task, not several, for two reasons. Every part ships in the plugin, and `test_check_version_bump.py` requires a higher version for each shipped change, so splitting the script, the tests and the skills into separate pull requests would force several version bumps for one feature. Each pull request would also leave the line format and its tests out of step. The precedent `2026-10-17-worktree-removal-untracked-identical` made the same call.

There is no separate review sub-task. The ordinary `/ship` review applies. The reviewer checks:
- HN-1: the outcome, exit code and finish command are unchanged by the reading, halted runs included.
- HN-2 and HN-9: the lookup ends within the bounded time with a real wrapper. The only process it ends is its own child, with `proc.kill()`, and never a descendant. `claude` is never taken from the current folder or the main checkout root, and it is started from its own folder (B1) with no `env` argument, so no environment variable is set for the child (C1).
- No new environment variable, switch or override exists anywhere in the change; `CLAUDE_CODE_SESSION_ID` is only read (C2).
- HN-3 and HN-4: every failure reads `cannot-tell`, with timeout and exit code kept apart.
- HN-5: the holder match is the existing `_inside`, with no second matcher. UNC, device and control-character paths never reach `realpath`.
- HN-6: cleaning in the D2 order (non-text rejected per D3, NFKC, categories Cc, Cf, Zl and Zp dropped, replacements, cut), and the forging probe.
- D4: no PATH folder is resolved before a hit in `_find_claude`. D5: `_end_own_child` is `try: proc.kill()` / `except OSError: pass` and nothing else.
- HN-7: only `CLAUDE_CODE_SESSION_ID` is read, by exact match.
- HN-8: every stop command printed, none cut.
- HN-11: the conditional paragraph, in `/task`'s `## Status lifecycle` and not in Step 6; in `/advance` inside the report block directly before `- Next command:`, with the block in master's order (D1).
- The RED list was recorded before GREEN.

After merge, the reviewer extends the **Delivery cleanup** entry in `MECHANISMS.md` with the Holder reading and promotes **Folder holder** and **Holder reading** to `VOCABULARY.md`.

---

## Review checklist (filled in after implementation)

`pr_merged.py` fills this list when the contract's work is merged and nothing is pending. Do not tick lines by hand.

- [ ] Implementation matches Data Shapes exactly
- [ ] Reused Mechanisms are actually reused (no parallel implementations introduced)
- [ ] New Mechanisms (if any) promoted to `MECHANISMS.md`
- [ ] New vocabulary terms promoted to `VOCABULARY.md`
- [ ] Integration surfaces reflected on both backend and frontend sides
- [ ] `INTEGRATION.md` updated if new API endpoints, SignalR events, or DTO shapes were introduced
- [ ] No orphaned DTO/model mismatches (C# DTO shape matches TypeScript interface)
- [ ] `Status` flipped to `implemented`
