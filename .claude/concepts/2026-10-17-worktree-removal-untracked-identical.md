# Concept Contract — Landed untracked files no longer block Delivery cleanup, and the concept gate stops gating files outside every project

**Project:** claude-agentic-auto-improve
**Date:** 2026-10-17
**Requested by:** user
**Status:** approved
**Supersedes:** none (extends INV-3 and INV-4 of `.claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md`; that contract stays `implemented` and is not edited)
**Work Item Brief:** .claude/work-items/2026-10-17-worktree-removal-untracked-identical.md
**Tracking issue:** none

> **Protocol:** filled in by `data-architect`. Implementers refuse to run unless `Status: approved`. The `concept-gate.py` hook reads `Files to touch`.
>
> **Revision 1 (2026-10-17):** revised after the critique, using the user's decisions. Identity now means git's own filtered comparison. The test_contract_index sandbox gets a `.git` marker. Two more shipped statements were added to Files to touch. Five WARNs were addressed. The cross-area scan result is recorded. See "Architect's response" under Critique.

---

## Business Concept

- **What is this thing, in domain language?**
  This contract fixes two defects that showed up together, each separately.
  **(A) Delivery cleanup.** Today cleanup treats every untracked file in an owned worktree as unsaved work, so it leaves the tree as `uncommitted-changes`. That is wrong when git itself would store the file as exactly the blob `origin/<default>` already holds at the same path, because removing it loses nothing. After this change cleanup proves each untracked file identical to the landing reference, using git's own comparison. It deletes those files one at a time, last, after every other check. It then removes the tree with the same non-forced `git worktree remove` as before. An untracked file it cannot prove identical, or any other kind of change, keeps today's behaviour.
  **(B) Concept gate.** The gate exists to protect project code. A Write or Edit is allowed when the gate can prove that the target has no project marker anywhere on its path, both as written and as resolved. Inside a project nothing changes.

- **Existing VOCABULARY.md terms that apply:** **Delivery cleanup**, **Owned set**, **Standing tree** (Universal, `.claude/registries/VOCABULARY.md` lines 56-58); **Contract Delivery**; **Enclosing worktree root** (line 38), from which "Outside every project" is distinguished below.

- **New terms proposed for VOCABULARY.md (Universal, after approval):**
  - **Landed untracked file** — an untracked file in an owned worktree that meets three conditions. `origin/<default>` holds an ordinary file (a blob, mode 100644 or 100755) at the same path. The file sits under no linked folder of the tree. `git hash-object` of the file, with the clean filters and line-ending conversion git would apply when staging it, gives that blob's id. Delivery cleanup may delete such a file, last, before a non-forced removal. Any other untracked file is unsaved work.
  - **Outside every project** — a path where neither the absolute path as written nor its resolved form has a project marker (`.git`, `CLAUDE.md`, `package.json`, `pyproject.toml`, `*.sln`) on itself or on any ancestor up to the filesystem root. Every ancestor that exists must also have been checked and listed without error. The concept gate does not gate such a path. **It is not the same as `tree_kind`'s `outside-repository`** (`_project_paths.py`, MECHANISMS.md line 42). That classification reads path text and looks for `.git` only. A folder with a `CLAUDE.md` but no `.git` is `outside-repository` yet not outside every project. Neither term may stand in for the other.

---

## End-User View

Not applicable. Reason: no Angular UI surface (component, template, stylesheet, state service, route, layout) is in `Files to touch`. The operator-visible effects are the cleanup line's new bracket and one fewer gate block, both described under Data Shapes.

---

## Data Shapes

### Entities

Not applicable. Reason: neither fix introduces or changes a persisted entity. Both work on worktree state and hook input that already exist.

### Value Objects

| Name | Fields | Used as |
|------|--------|---------|
| **Untracked Comparison** (new, in memory, one per owned worktree) | ref (`origin/<default>`); identical (list of path, each with the blob id it matched); differing (list of path: absent at the ref, not a blob, a link, not a regular file, under a linked folder, resolving outside the tree, or a different id); verdict: `all-identical` \| `some-differ` \| `unverifiable`; cause (text, only when `unverifiable`) | Built at the status step of `clean_worktree`, only when every status entry is untracked |
| **Cleanup Item** (extended) | gains `identical`: a list of path (worktrees only, default empty) naming the Landed untracked files proven for this tree. Every other field is unchanged | Under `--json`. The printed `line` uses it for a removed worktree (CL-7) |
| **Project Root Scan** (new, in the gate, one per walk) | project name or none; complete (bool): every ancestor whose existence check or listing raised anything other than "not found" makes it false | The existing resolved walk produces one. `detect_project_name` returns its name. The allowance needs a second scan, of the written path, only when the first finds no project (CG-1) |

### Events

Not applicable. Reason: a CLI script and a PreToolUse hook. Neither emits nor listens to events.

### Commands (if any)

Not applicable. Reason: no CLI flag, argument or exit code changes. `cleanup_delivered.py` keeps exit codes 0, 3, 5, 10 and 2. The gate keeps exit 0 to allow and 2 to block.

### Invariants

**Cleanup (extends INV-3 and INV-4 of the 2026-10-15 contract):**

- **CL-1 (identical means identical to git).** A path is a Landed untracked file only when all of these hold:
  - its status entry is `??`;
  - `lstat` shows the entry as a regular file (not a link or junction);
  - no folder between the tree root and the file is a link (`_is_link` on each component);
  - the file's real path lies inside the tree's real root;
  - `git ls-tree` at the ref lists the path as `blob` with mode 100644 or 100755 (not 120000 or 160000);
  - `git -C <tree> hash-object -- <path>` returns that blob's id. Filters are **on**: the clean filter and the `core.autocrlf` / `eol` / `text` conversion git would apply when staging that path, which is the comparison `git status` uses for a tracked file.

  File mode is not compared. Under a conversion setting, a file that differs from the blob only in CRLF versus LF **is** identical. Any change to the content still differs. When no conversion applies, CRLF stays a difference. A path that fails one of the link or containment checks is counted as differing, so the tree is left. It is never `unverifiable` and never deleted.
- **CL-2 (any other change keeps today's path exactly).** If any status entry is not `??` (modified, staged, deleted, renamed or conflicted), no comparison runs. The item reads `uncommitted-changes` with `files` exactly as today (acceptance criterion 3).
- **CL-3 (fail closed).** Each of these leaves the tree `left`, reason `unverifiable`, with `detail` naming the cause. Nothing is deleted. A path absent at the ref is a definite answer, never `unverifiable`: the file is simply listed as differing (acceptance criterion 6).
  - the ref listing fails;
  - `hash-object` fails or returns the wrong number of ids;
  - a path cannot be hashed.
- **CL-4 (non-identical untracked still blocks).** On `some-differ` the item reads `uncommitted-changes`. `files` lists only the differing paths and `identical` lists the proven ones. Nothing is deleted (acceptance criterion 2).
- **CL-5 (delete last, re-checked file by file).** Within the existing order of `clean_worktree`:
  1. Unchanged checks: lock, folder present, status (with the comparison), HEAD an ancestor of the ref, ignored and tracked listings, nested-worktree scan, standing tree.
  2. Dry run returns here. It reports `identical` and deletes nothing.
  3. The vanished-link halt.
  4. The Windows rename probe.
  5. **Re-read status.** It must hold exactly the same set of `??` paths. A changed set reads `uncommitted-changes`; a read failure reads `unverifiable`. Nothing is deleted in either case.
  6. **For each Landed untracked file, in turn:** re-check its link and containment conditions, re-hash that one file (`hash-object` as in CL-1), and, only if the id still matches, delete it at once. A mismatch stops the loop. The tree reads `uncommitted-changes`, `files` names the changed file and `detail` lists the files already deleted (each verified a moment before). A re-hash failure stops the same way with `unverifiable`.
  7. Untracked links are removed (INV-4 unchanged: still immediately before removal).
  8. `git worktree remove <path>` runs, never forced (acceptance criterion 4).

  **Accepted residual window:** a write landing between one file's re-hash returning and that file's delete is lost. The window is one file's length, not the whole tree's. On POSIX nothing narrows it further, because the rename probe does not run there, and on Windows the probe cannot see a Git Bash shell (VOCABULARY **Standing tree**). It is accepted because the file was verified identical to the ref milliseconds earlier and nothing is expected to write into a delivered tree.
- **CL-6 (single-file deletes only).** Each file is removed alone with a single-file delete. There is never a directory delete, `rmtree`, `git clean` or `git rm`. Folders the deletes leave empty are left for `git worktree remove`. A delete that raises stops the tree at once: it reads `remove-failed`, and `detail` names the failing file and the files already deleted. No link is removed and `git worktree remove` is not run.
- **CL-7 (the report explains it).** For a worktree whose `identical` list is non-empty and whose action is `removed`, the printed line renders `<name> [identical to <ref>: a, b, +k more]`, using the existing per-item caps of `build_line`. The 600-character bound and the cap ladder are unchanged. Dry run prints the same bracket (acceptance criterion 5).
- **CL-8 (no new reason, no new exit code).** The reason closed set of the 2026-10-15 contract is unchanged. INV-5 is unchanged: no `--force`, no prune, no rmtree, no switch or checkout.

**Concept gate:**

- **CG-1 (allow outside every project, written and resolved).** A target is allowed only when two scans both find no project and both are complete:
  - **Resolved scan:** the existing walk of `detect_project_name`, over the target made absolute and resolved.
  - **Written scan:** the same walk over `os.path.abspath(target)` (made absolute against the hook's working directory, `..` folded, links **not** followed).

  A link inside a project that points to a marker-less folder therefore stays gated, because the written scan finds the project. A link outside that points into a project stays gated because the resolved scan finds it. The written scan runs only when the resolved scan found no project. When the two paths are equal it is skipped. Acceptance criterion 7.
- **CG-2 (cannot prove means gated).** Each ancestor gets one existence check and, if it exists, one listing, both inside the scan's error handling:
  - "not found" or "not a directory" from the existence check: the ancestor is skipped, as today (a new file in a new folder).
  - Any other error from the existence check or the listing (permission, I/O): `complete` is false.

  This replaces today's `parent.is_dir()` outside the `try` (`concept-gate.py:309`). On Python 3.13 and later that call silently answers false. On 3.12 and earlier it raises, and the gate then fails open. After the change the scan never raises, and an incomplete scan never allows. The project name an incomplete scan returns for an in-project target is unchanged: the first marker found.
- **CG-3 (in-project unchanged).** The marker set, the contract lookup, the trivial list, the pinned contract and the block banner are unchanged. The allowance sits after the pinned-contract step and before the contract scan in `resolve_target`. It returns `(True, None, None)` and prints nothing, like every other allow.
- **CG-4 (no extra cost in a project).** A target inside a project pays only today's resolved walk, which stops at the first marker. `test_gate_cost.py` is not moved.
- **CG-5 (multi-target).** Each target is judged separately. If one target is outside every project and another is an uncovered in-project file, the call is still blocked, and the banner names the in-project target.
- **CG-6 (every caller of resolve_target inherits it).** The planned `concept-changed-check.py` (block 17 of `2026-10-12-dedupe-claude-config`, not yet in this tree) judges changed files through this `resolve_target`. Once it lands, a file written by the shell outside every project is not stopped either. That is consistent with CG-1, and it is stated here so the reader does not mistake it for an accident.

---

## Reused Mechanisms

- **Delivery cleanup** (`MECHANISMS.md` line 67) — **extended by** the Landed-untracked step in `clean_worktree`. It reuses `_status_files` (split into entries with their status codes), `_is_link`, `run.ref`, `_left`, the `unverifiable` and `remove-failed` reasons, the `build_line` caps and the wrapper-git test world. Persistence check: not applicable, since there is no database. Closed-set check: no reason value is added.
- **Guard fallback mode** (line 54) — **consumed as-is**. The allowance reads no `_project_paths` function, so the inline fallback and its banner are untouched. CG-2 closes this gate's own raise-and-fail-open path in the scan. The known sharp edge listed for that mechanism (a helper that throws) is left as it is.
- **Two-layer Claude path resolution → path classification** (line 42) — **consumed as-is, and kept distinct**: `tree_kind` and `outside-repository` are not used or changed. See the vocabulary note.
- **Main-checkout guard, hosted by the gate launcher** (line 61) — **consumed as-is**. It still runs before the gate, and a target outside every project is never the main checkout.
- **Flat worktree helper** (line 63) — consumed as-is, through `flat_worktree.worktree_entries` and `is_flat`.

---

## New Mechanisms (if any)

None. Both changes extend existing code paths.

---

## Extension Points

1. `cleanup_delivered.py`:
   - `_status_files` gains each entry's status code; its existing list output stays available.
   - A comparison helper builds the Untracked Comparison with one `git -C <tree> ls-tree -r -z --full-tree <ref>`. It then runs `git -C <tree> hash-object -- <paths>` (filters on), in chunks so each command line stays under 8000 characters. It also does an `lstat` and a parent-link check per path.
   - `clean_worktree` calls the helper at the status step, then runs the CL-5 per-file re-hash-and-delete loop.
   - `_wt_item` gains `identical: []`.
   - `build_line` renders removed worktrees through a new per-item renderer beside `_left_entry`.
   - The module docstring's rule list gains the Landed-untracked rule.
2. `concept-gate.py`:
   - One `PROJECT_MARKERS` constant.
   - One private scan function giving (name, complete) for a given start path, with the existence check inside the error handling (CG-2).
   - `detect_project_name` returns the resolved scan's name, unchanged in value.
   - `resolve_target` gains the CG-1 step.
   - The module docstring gains one line.
3. Shipped statements that the gate blocks every non-trivial file (journal 2026-10-04) each gain "inside a project" wording:
   - `README.md` line 136;
   - `skills/design-first/SKILL.md` line 18;
   - `.claude/hooks/hooks.json` line 35 (the BLAST RADIUS text).
4. `.claude/hooks/tests/test_contract_index.py`: `Sandbox.__init__` creates a `.git` marker (an empty folder) at the sandbox root, so every block and index row still exercises the gate. If a `.git` folder changes any non-gate row there (a `tree_kind`-reading row), use a `CLAUDE.md` file instead and say which was used.
5. Version 0.9.7 → 0.9.8 in all five declarations: `plugin.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (two entries) and `.cursor-plugin/plugin.json`.

---

## Integration Surfaces

| Source Module | Target Module | Mechanism | Data Shape | Direction |
|---------------|---------------|-----------|------------|-----------|
| `cleanup_delivered.py` | `/pr-merged` Step 7 and `/advance` | the printed `line`, quoted verbatim | Cleanup Report `line` (gains the CL-7 bracket) | script → skill text |
| `concept-gate.py` | `_gate_launch.py` (via `runpy`) | exit code and stderr | allow or block | hook → launcher |
| `concept-gate.py` `resolve_target` | planned `concept-changed-check.py` (not in tree) | in-process call | allow or block per target | hook → hook (CG-6) |

**Changes to existing integration surfaces:** none in shape. The `line` stays a single line of at most 600 characters, and the skills print it unchanged, so no skill's cleanup text is edited. The JSON item gains one list field. No frontend, no API.

---

## Adjacent Areas

Not applicable. Reason: cross-area scan returned no signal above the threshold. The orchestrator ran `cross_area_scan.py` on this contract and reported bucket `uncategorized` with nothing above the threshold; `.claude/area-mapping.json` declares no areas.

---

## UI Implications

Not applicable. Reason: backend-only contract with no frontend consumer in Integration Surfaces.

---

## Chat Tool Impact

2. **No —** no REST endpoint or SignalR event is added or changed. The change is to a local maintenance script and a hook, with no chat surface.

---

## Non-Goals

- Removing a tree the session stands in. The standing-tree deferral is unchanged.
- Treating a differing untracked file, an ignored file or a tracked change as safe. Forcing any removal.
- Comparing with filters off, or folding line endings beyond what git's own staging conversion does.
- Changing what the gate trusts inside a project, the marker set, the trivial list or the contract format.
- The main-checkout guard, `bash-gate.py`, and `tree_kind`.
- Making `test_changed_file_check.py` green. It is red by design until block 17 of `2026-10-12-dedupe-claude-config` adds its check.
- The user's global `~/.claude/CLAUDE.md` text, the 2026-10-15 contract and the reference agent-memory note.

---

## Confidence

Confidence: Medium-High. High on the gate rules and the cleanup ordering, both read in source. Medium on two git behaviours that the RED tests pin: a non-forced `git worktree remove` accepting the empty folders left behind, and `hash-object` with filters folding CRLF under an explicitly set `core.autocrlf=true` in the test world.

---

## Alternatives Considered & Why Rejected

- **Option A (chosen):** prove each untracked file identical by git's filtered blob id, delete only those, last, re-hashing each just before its delete, then run a non-forced removal. On the gate side, allow only a path that is project-less both as written and as resolved.
  - Why: every deleted file is what git would have staged as the blob on the ref, INV-5 holds, and both defects close with no new reason or flag.
- **Option B (rejected):** strict raw bytes (`hash-object --no-filters`).
  - Why rejected: under `core.autocrlf=true`, which is Git for Windows' default, a checked-out text file has CRLF while the blob has LF. It would never match, so the reported bug would survive on Windows. This repeats the raw-byte trap recorded for **Bidirectional sync** (MECHANISMS.md line 46). User decision 1.
- **Option C (rejected):** `git worktree remove --force` when every untracked file is identical.
  - Why rejected: INV-5 and its test forbid it, and a forced removal also deletes a file modified between the check and the removal.
- **Option D (rejected):** `git clean -f -- <paths>`.
  - Why rejected: `clean` is in the suite's mutating set and `-f` trips the no-force tripwire; single-file deletes are narrower.
- **Option E (rejected):** stop listing identical files as changes without deleting them.
  - Why rejected: a non-forced `git worktree remove` refuses a tree with untracked files.
- **Option F (rejected, gate):** add `.cmd` and other script extensions to the trivial list.
  - Why rejected: that ungates scripts inside projects too.
- **Option G (rejected, gate):** walk only the resolved path, which is today's walk.
  - Why rejected: a junction from a project into a marker-less folder would open the gate (critic WARN).
- **Option H (rejected, gate):** allow only the home folder.
  - Why rejected: the brief's intake answer covers the whole no-project case, and %TEMP% harnesses hit the same block.

---

## Uncertain Assumptions

- `VERIFIED via .claude/scripts/cleanup_delivered.py:391-407, 449-455`: `_status_files` returns every `??` path as a change, and `clean_worktree` leaves the tree `uncommitted-changes` before any other check.
- `VERIFIED via .claude/scripts/cleanup_delivered.py:533`: removal is `git worktree remove <path>` without force; `test_cleanup_delivered.py:2435` and the call-log invariant forbid force.
- `VERIFIED via .claude/scripts/tests/test_cleanup_delivered.py:1353`: the existing untracked test uses a file absent from master, so it stays green under CL-4.
- `VERIFIED via .claude/hooks/concept-gate.py:308-314`: `parent.is_dir()` sits outside the `try`; only `iterdir` is guarded. CG-2 replaces this.
- `VERIFIED via .claude/hooks/tests/test_contract_index.py:105, 199-232` (critic): the sandbox under the temp folder has no project marker. That is why Extension Point 4 adds one.
- `VERIFIED via .claude/hooks/tests/test_changed_file_check.py:40` (critic): the suite is red by design. It is removed from the run-green list.
- `VERIFIED via skills/design-first/SKILL.md:18` and `.claude/hooks/hooks.json:35`: both say the gate blocks every non-trivial file.
- `ASSUMED`: a non-forced `git worktree remove` succeeds once only empty untracked folders remain. Verification path: RED test 3.
- `ASSUMED`: the test world's wrapper `git` passes `hash-object` and `ls-tree` through, and `set_git_fail` can fail each one. Verification path: RED test 8 and the fixture control.
- `ASSUMED`: the system temp folder on test hosts has no project marker on its path. Verification path: G1's own precondition, which fails loudly and names the marker.
- `ASSUMED`: git does not list files beneath an untracked junction or symlink folder. CL-1's parent-link check is defence in depth either way. Verification path: RED test 12b.

---

## Failure Modes & Mitigations

- **FM:** a file changes after the comparison and is deleted with its new content.
  - **Mitigation:** CL-5 step 5 re-reads status, and step 6 re-hashes each file immediately before its own delete. The residual one-file window is stated and accepted (CL-5). It is not attributed to the rename probe, which skips POSIX and cannot see Git Bash.
- **FM:** git's conversion makes a file look identical whose exact bytes are not on master (for example CRLF versus LF).
  - **Mitigation:** accepted by user decision 1. This is the same judgement `git status` makes for a tracked file, and a real content change still differs (RED test 6c).
- **FM:** a file is reached through a linked parent folder, and the delete removes a file outside the tree.
  - **Mitigation:** CL-1's parent-link and containment checks, repeated in CL-5 step 6. The tree is left (RED test 12b).
- **FM:** the deletes succeed, then `git worktree remove` fails.
  - **Mitigation:** every deleted file is on the ref and `detail` lists them. The existing `remove-failed` handling and orphan report apply.
- **FM:** a ref or hash read fails and the tree is treated as identical.
  - **Mitigation:** CL-3 (`unverifiable`); the wrapper fails each call in RED test 8.
- **FM:** an unreadable or unstattable ancestor, a relative path, or a link makes the gate believe there is no project.
  - **Mitigation:** CG-1's two scans and CG-2's complete flag; G3, G4, G4b and G6.
- **FM:** a consumer's own project sits under a folder with no marker and its code becomes ungated.
  - **Mitigation:** accepted and stated in all three shipped statements. A git checkout always carries `.git`.

---

## Open Questions for User

All are answered. Status stays `draft` until the user approves.

- [x] **Q1 — Strict bytes or folded line endings?** **Answer (user, 2026-10-17):** decide "identical" the way git stages the file, with `hash-object` filters and autocrlf applied, against the blob at `origin/<default>`. A real content change must still differ. Applied in CL-1 and RED tests 6a-6c.
- [x] **Q2 — A folder on the path that cannot be listed or checked.** **Answer (assumed, unchanged by the user):** gated as today (CG-2). This now covers the existence check too, not only the listing.
- [x] **Q3 — Report `identical` when the tree is left for another reason?** **Answer (assumed):** yes in `--json` whenever a comparison ran. The printed bracket appears only on removed or dry-run trees.
- [x] **Q4 — The critic's BLOCKER: keep "no marker means allowed"?** **Answer (user, 2026-10-17):** keep it. Fix the tests by giving the `test_contract_index.py` sandbox a `.git` marker. Add the `skills/design-first/SKILL.md:18` and `hooks.json:35` wording to Files to touch, and drop `test_changed_file_check.py` from the run-green list.

---

## Critique

**Critic:** contract-critic
**Date:** 2026-10-17
**Verdict:** blockers-found

### Findings

- **[BLOCKER] CG-1 turns the blocks that the existing contract-index suite expects into allows, so the handoff's own rules contradict each other.**
  - **What is wrong:** `test_contract_index.py` builds every Sandbox under the system temp folder (`scratch_parent()` returns `tempfile.gettempdir()`, line 105; `Sandbox.__init__`, lines 199-232). The sandbox gets `.claude/hooks`, `scripts` and `concepts` but no `.git`, `CLAUDE.md`, `package.json`, `pyproject.toml` or `*.sln`. Its targets (`src/feat/uncovered.cs`, the `wt1` targets) are therefore outside every project. CG-1 allows them before the contract scan, so the rows that expect exit 2 (lines 542, 604, 633, 698, 710, 726, 738, 1003, 1461) flip to allow. The rows that count index hits (`warm.hits(v) > 0`) stop being met too, because the index is never read. The handoff also says "Do not weaken an existing test" and lists `test_contract_index.py` under "Run green". Both rules cannot hold together.
  - **Prior artifact ignored:** `.claude/hooks/tests/test_contract_index.py:105, 199-250` (the gate's own suite, which the contract names). The contract's own ASSUMED line ("the system temp folder on the test hosts has no project marker") is the exact condition that breaks this suite. The contract applies it only to the new G1 test.
  - **Where in this contract:** `## Data Shapes → Invariants` CG-3 "In-project unchanged" and CG-1. `## Implementation Handoff` "Run green: … test_contract_index.py" and "Do not weaken an existing test."
- **[WARN] One suite in the run-green list is red by design, and the ASSUMED line describes it wrongly.**
  - **What is wrong:** `test_changed_file_check.py:40` says "RED TODAY: `concept-changed-check.py` does not exist yet (block 17 adds it), so every row fails". The suite cannot go green in this change. The contract's ASSUMED line expects only a "same verdicts as the gate" row to fail. The suite's docstring (lines 11-12) also says that the planned check judges each changed file "through `concept-gate.py`'s own `resolve_target`". So the CG-1 allowance will apply to shell-written files as well once block 17 lands, and the contract does not state that.
  - **Prior artifact ignored:** `.claude/hooks/tests/test_changed_file_check.py:2-12, 40` (contract `2026-10-12-dedupe-claude-config`, block 16/17, in the consuming repository).
  - **Where in this contract:** `## Uncertain Assumptions`: "`concept-changed-check.py` … is absent from this tree … its 'same verdicts as the gate' test will fail and name it". `## Implementation Handoff`: "Run green: … test_changed_file_check.py".
- **[WARN] The strict byte comparison repeats a line-ending false negative this repository has already documented, and it may not fix the reported bug on Windows.**
  - **What is wrong:** with `core.autocrlf=true` (Git for Windows' installer default), a text file that git checked out has CRLF endings while the blob has LF. CL-1 compares `--no-filters` bytes, so such a file is never "identical" and the tree stays, which is the symptom the brief reports. The brief only says the file was "byte for byte the same" and does not say what it was compared against. Q1's recommended answer does not mention the earlier lesson. The Alternatives section does not consider git's own filtered comparison, the one `git status` uses to call a tracked file unmodified.
  - **Prior artifact ignored:** `MECHANISMS.md` line 46 (**Bidirectional sync**): the sync tool "hashed raw bytes across a line-ending and byte-order-mark boundary, reporting eighteen conflicts that no edit could ever clear and training the operator to reach for `-Force`". Also `VOCABULARY.md` line 35, **Vendored-asset drift** ("after normalising encoding — folding line endings").
  - **Where in this contract:** `## Open Questions for User` Q1 "Assumed answer (recommended): strict raw bytes". `## Data Shapes → Invariants` CL-1 "no line endings are folded".
- **[WARN] FM-1's mitigation claims protection the rename probe does not give, and the window between the re-check and the delete is not stated.**
  - **What is wrong:** in CL-5 the probe is step 4 and the re-verify is step 5, so the probe says nothing about the time between the re-hash (step 5) and `os.remove` (step 6). A write that lands in that window is deleted. The probe runs only on Windows (INV-6 skips it on POSIX), and the registry says it "cannot see a Git Bash shell". The contract presents the residual window as covered, not as an accepted risk.
  - **Prior artifact ignored:** `VOCABULARY.md` line 58 (**Standing tree**: "on Windows only, by a rename probe that cannot see a Git Bash shell"). `.claude/concepts/2026-10-15-auto-cleanup-delivered-worktrees.md` INV-6 (line 124: "On POSIX … the probe is skipped").
  - **Where in this contract:** `## Failure Modes & Mitigations` FM 1: "The Windows probe has already shown nobody holds the folder (INV-6, **Delivery cleanup**)."
- **[WARN] CL-1 checks only the last part of the path for a link, yet the file deletes run before the link removal.**
  - **What is wrong:** CL-1 calls `lstat` on the file entry itself. CL-5 deletes files at step 6, before untracked links are removed at step 7. The contract has no invariant and no test for a status path whose parent folder is an untracked junction or symlink. If git ever lists a file through such a parent, CL-6's single-file delete removes a file outside the worktree. The script already has a link walker (`_walk`, `find_links`, using `_is_link`) for exactly this tree.
  - **Prior artifact ignored:** `MECHANISMS.md` line 67 (**Delivery cleanup**: "untracked junctions and symlinks are removed alone, last"). 2026-10-15 contract INV-4 (line 111).
  - **Where in this contract:** `## Data Shapes → Invariants` CL-1: "`lstat` shows the worktree entry as a regular file (not a link or junction)". RED test 12 covers only "an untracked symlink at a landed path".
- **[WARN] CG-2 covers a folder that cannot be listed, but not a folder whose existence check itself fails.**
  - **What is wrong:** in `concept-gate.py:309` the `parent.is_dir()` call sits outside the `try`. Python 3.13 and later answer `False` on any `OSError`, so an existing folder that cannot be checked counts as "does not exist", is skipped, and `complete` stays true. CG-1 then allows the target. On 3.12 and earlier the `PermissionError` escapes `resolve_target`, and `main` fails open with exit 0. The VERIFIED line ("skips unlistable ancestors") reads only the `iterdir` branch, and test G4 patches only the listing.
  - **Prior artifact ignored:** `MECHANISMS.md` line 54, **Guard fallback mode** known sharp edge: "a helper that throws makes the other three gates fail open". `JOURNAL.md` 2026-10-16, "An unset ownership field is not proof of ownership": absence of evidence must not count as proof.
  - **Where in this contract:** `## Data Shapes → Invariants` CG-2: "An ancestor that exists but raises on listing makes `complete` false". `## Uncertain Assumptions`: "VERIFIED via … concept-gate.py:297-319".
- **[WARN] CG-1 walks only the resolved path, so a link from inside a project to a folder with no marker opens the gate.**
  - **What is wrong:** CG-1 resolves the target before walking up, which follows junctions and symlinks. A file under `<project>/src/shared`, where `shared` is a junction to a folder with no marker, resolves outside every project and is allowed, although its written path lies inside the project. Today the same resolved walk only chooses the contract-lookup name, and the file is still blocked. With this change it becomes an allow. The path-classification helpers in this repository deliberately classify by path text. No failure mode or test covers a linked target.
  - **Prior artifact ignored:** `MECHANISMS.md` line 42 (**Two-layer Claude path resolution → Path classification for guards**: the classifiers "take one path string and read no file"). `VOCABULARY.md` line 38 (**Enclosing worktree root**: "computed from the path text alone").
  - **Where in this contract:** `## Data Shapes → Invariants` CG-1: "The walk starts from the target made absolute against the hook's working directory and then resolved."
- **[WARN] Two shipped statements that the gate blocks every non-trivial file stay unchanged.**
  - **What is wrong:** the README line and the gate docstring are updated. Two other shipped statements are not, and neither file is in Files to touch: `skills/design-first/SKILL.md:18` ("blocks Edit/Write on non-trivial files without an approved contract") and the `.claude/hooks/hooks.json:35` BLAST RADIUS text ("concept-gate blocks Edit/Write on non-trivial files until an approved concept contract exists"). After this change both overstate what the gate does.
  - **Prior artifact ignored:** `JOURNAL.md` 2026-10-04, "Check a documented guard behaviour against the guard's code".
  - **Where in this contract:** `## Implementation Handoff → Files to touch` (README.md only). `## Lessons referenced`: "heeded by the README line and the gate docstring".
- **[NIT] The Adjacent Areas text is out of date.** It says the scanner "was **not run**". The orchestrator reports that the scan ran and found nothing above the threshold (bucket `uncategorized`). `.claude/area-mapping.json` declares no areas, so the row slugs `hooks`, `skills` and `main-checkout guard` are not areas the scanner knows. The section's sanctioned single-line form fits this result.
- **[NIT] The proposed term "Outside every project" sits beside an existing classification with a different meaning, and the two are not told apart.** `tree_kind` returns `outside-repository` (`MECHANISMS.md` line 42) by looking for `.git` only. The new term uses five markers. The vocabulary entry should say they are distinct, so neither is read as a synonym for the other.

### Applicable journal entries

- **2026-10-04: Check a documented guard behaviour against the guard's code.** Heeded in part: the README line and the docstring are updated. Not addressed for `skills/design-first/SKILL.md:18` and `hooks.json:35` (see WARN above).
- **2026-10-04: A VERIFIED parser claim must be tested on the unfilled and the missing case.** Heeded in part: cleanup tests 5 and 8 cover the absent path and the failed listing. The VERIFIED claim about `detect_project_name` was not tested on a folder whose existence check fails (see the CG-2 WARN).
- **2026-10-15: A fallback that finds "the brief" by the caller's own branch must prove the brief belongs to this contract.** Heeded by placing the step inside `clean_worktree`. No new source of ownership is added.
- **2026-10-16: An unset ownership field is not proof of ownership.** Heeded by CL-1 and CL-3: a matching blob id is required, and a failed read never counts as identical.

### What the critic did not check

- `.claude/registries/INTEGRATION.md` does not exist in this tree. Item 7 was judged from the contract alone; there is no REST, SignalR or frontend DTO surface.
- `.claude/.scout-cache/registry-digest.md` does not exist. The registries were read whole; the project tier has no per-domain files.
- `.claude/north-stars/` holds no files, so item 13 produced no findings.
- The critic did not test whether Git for Windows lists files beneath an untracked junction. The CL-1 WARN is about a gap in the contract, not a reproduced defect.

### Architect's response (revision 1, 2026-10-17)

- **BLOCKER (contract-index sandbox):** the rule is kept (user decision Q4). Extension Point 4 and the handoff give the `Sandbox` a `.git` marker. `test_contract_index.py` is in Files to touch and stays in the run-green list, with no row weakened.
- **WARN (changed-file check):** removed from the run-green list, the ASSUMED line replaced by a VERIFIED one, and CG-6 states the inheritance.
- **WARN (strict bytes):** CL-1 now uses git's filtered `hash-object` (user decision Q1). Strict bytes moved to rejected Option B, citing **Bidirectional sync**. Tests 6a-6c cover it.
- **WARN (probe claim, window):** CL-5 step 6 re-hashes each file immediately before its own delete. The one-file residual window is stated as accepted, and FM 1 no longer credits the probe.
- **WARN (linked parent folders):** CL-1 adds a parent-link check and a containment check, repeated before each delete. A failing path counts as differing, so the tree is left. RED test 12b covers it.
- **WARN (existence check outside try):** CG-2 puts the existence check inside the scan's error handling, and only "not found" or "not a directory" skips an ancestor. G4b covers it.
- **WARN (junction into a marker-less folder):** CG-1 requires both the written and the resolved scans to be clean. G6 covers it, and rejected Option G records the alternative.
- **WARN (shipped statements):** `skills/design-first/SKILL.md` and `.claude/hooks/hooks.json` are added to Files to touch (Extension Point 3).
- **NIT (Adjacent Areas):** replaced by the sanctioned single line with the scan result.
- **NIT (term vs `outside-repository`):** the vocabulary entry now states the difference.

---

## Lessons referenced

- **2026-10-04 — Check a documented guard behaviour against the guard's code** — heeded by updating all three shipped statements (README, `design-first` SKILL, `hooks.json`) and the docstring, with G1-G6 proving the behaviour. Cross-reference: JOURNAL.md § Universal lessons.
- **2026-10-16 — An unset ownership field is not proof of ownership** — heeded by CL-1 and CL-3 (a matching filtered blob id is required; a read failure never counts as identical) and by CG-2 (an ancestor that cannot be checked never counts as absent).
- **2026-10-04 — A VERIFIED parser claim must be tested on the unfilled and the missing case** — heeded by the tests for an absent path, a failed listing, a failed existence check (G4b) and a failed listing (G4).
- **2026-10-15 — A fallback that finds "the brief" by the caller's own branch must prove the brief belongs to this contract** — heeded indirectly: the step sits inside `clean_worktree` and adds no new source of ownership.
- Orthogonal to north-stars: none. The register holds no active thought, which confirms the brief's `north_stars: none`.

---

## Implementation Handoff

### 1. Landed untracked files, the outside-every-project allowance, docs and version (`python-ai-developer`)

**Depends on:** none

**Files to touch:**
- `.claude/scripts/cleanup_delivered.py`
- `.claude/scripts/tests/test_cleanup_delivered.py`
- `.claude/hooks/concept-gate.py`
- `.claude/hooks/tests/test_concept_gate_outside_project.py`
- `.claude/hooks/tests/test_contract_index.py`
- `.claude/hooks/hooks.json`
- `skills/design-first/SKILL.md`
- `README.md`
- `plugin.json`
- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`

**Pre-written TASK block:**
```
TASK: Let Delivery cleanup delete untracked files that git would store as exactly the blob at
      origin/<default> (last, after every check, each re-hashed just before its delete, then a
      non-forced removal), and let the concept gate allow a target that lies provably outside
      every project, both as written and as resolved.
CONTEXT: concept contract at .claude/concepts/2026-10-17-worktree-removal-untracked-identical.md
         brief .claude/work-items/2026-10-17-worktree-removal-untracked-identical.md
FILES: the Files to touch list above
CONSTRAINTS:
  - FAILING TESTS FIRST. Write every test below, run them, and record which fail before any
    production edit (RED). Then make them pass (GREEN). Do not weaken an existing test.
  - RED, cleanup (new class in test_cleanup_delivered.py, CleanupCase, deliver() in setUp).
    Add a fixture helper land_on_master(w, files) shaped like add_sibling_item: commit the
    files on w.ghub master and push. Unless a case says otherwise, write each untracked copy
    with write_bytes of the exact bytes from `git cat-file blob origin/master:<path>`.
      1 fixture control: after land_on_master the tree's HEAD is still an ancestor of
        origin/master and `git status --porcelain` lists only the copy as `??`.
      2 the only untracked file is identical -> tree removed (assertGone), its branch removed
        as for a clean tree, item.identical names the path, the printed line carries
        "[identical to origin/master: <path>]", outcome cleaned, exit 0   (AC1, AC5)
      3 the identical file sits in a subfolder HEAD does not have -> still removed (pins the
        empty-folder assumption)
      4 untracked file with different content at a landed path -> left uncommitted-changes,
        files names it, file intact, tree kept                          (AC2)
      5 untracked file at a path origin/master lacks, next to an identical one -> left
        uncommitted-changes, files lists only the absent one, identical lists the other,
        neither deleted                                                  (AC2, CL-4)
      6a with `git config core.autocrlf true` set in the world's main repository (shared by its
         worktrees), the landed LF text written untracked with CRLF endings -> identical,
         tree removed                                                    (CL-1, Q1)
      6b the same CRLF copy with core.autocrlf explicitly false and no .gitattributes ->
         differs, left (proves git's view is used, not a fold of our own)
      6c with core.autocrlf true, CRLF copy with one word changed -> differs, left, intact
      7 identical untracked + a modified tracked file -> left exactly as today, both paths
        in files, no ls-tree or hash-object call in the call log; same for a staged change
                                                                          (AC3, CL-2)
      8 set_git_fail(["ls-tree"]) and, separately, set_git_fail(["hash-object"]) -> left
        unverifiable, file intact, no worktree remove call               (AC6, CL-3)
      9 ordering: identical file + unpushed commit; identical file + standing tree
        (--from the tree); identical file + locked; identical file + --dry-run -> the file
        is still on disk in each case                                    (AC4, CL-5)
     10 call-log order for case 2: a hash-object for the file comes after the status re-read
        and before its delete. The only mutating git call is a `worktree remove` with no
        -f or --force. The existing no-force tests and
        test_the_real_source_has_no_force_no_prune_and_no_rmtree stay green  (AC4, CL-8)
     11 per-file re-check: two identical files; run_in_process with os.remove wrapped so that
        after the first delete it rewrites the second file's content -> tree left
        uncommitted-changes naming the second file, its new bytes intact, detail lists the
        first as deleted, no worktree remove call                       (CL-5 step 6)
     12a an untracked symlink at a landed path is never identical, so the tree is left
     12b a landed file reached through an untracked linked folder (a junction on Windows,
         a symlink elsewhere, to a folder outside the tree holding the same bytes) -> tree
         left, the target folder's file intact. Record whether git listed the file through
         the link at all (it verifies the ASSUMED line either way). Skip 12a and 12b only on
         hosts that cannot create links, as the existing link tests do.
  - RED, gate (new unittest file .claude/hooks/tests/test_concept_gate_outside_project.py;
    run the hook as a subprocess with a Write payload, CLAUDE_CONCEPT_GATE and
    CLAUDE_ACTIVE_CONTRACT removed from env):
      G1 a .cmd target and a .py target in a fresh mkdtemp under the system temp folder -> exit
         0, no "[concept-gate] BLOCKED". The precondition is asserted by the test's OWN
         ancestor walk: if a marker is found, FAIL naming it (never skip)  (AC7)
      G2 control: the same names inside a temp project (CLAUDE.md marker; and a .git folder
         variant) -> exit 2 with "no approved contract's 'Files to touch' list references this
         file"                                                            (AC7, CG-3)
      G3 relative target "x.py" with cwd = <temp project>/sub (sub has no marker) -> exit 2
      G4 in-process: load concept-gate.py by path, patch the LISTING of one existing ancestor
         of the G1 target to raise PermissionError -> resolve_target returns not allowed
      G4b in-process: patch the EXISTENCE CHECK of one existing ancestor (the stat call your
         scan uses) to raise PermissionError -> not allowed, and resolve_target does not
         raise                                                            (CG-2)
      G5 a payload with two targets (edits[] carries one outside every project and one
         uncovered in a temp project) -> exit 2 naming the in-project target (CG-5)
      G6 a temp project with src/shared as a directory link (a junction on Windows, a symlink
         elsewhere) to a marker-less temp folder; target <project>/src/shared/x.py -> exit 2.
         Reverse: a marker-less folder holding a link into the temp project; a target through
         it -> exit 2. Skip only when the host refuses to create links, and say so (CG-1)
  - Existing suite fix: in test_contract_index.py Sandbox.__init__, create a `.git` folder at
    the sandbox root so its block and index rows keep exercising the gate. If that folder
    changes any row that reads tree_kind, use a CLAUDE.md file instead, and say which you used
    and why. No row's expectation changes.
  - GREEN, cleanup: implement CL-1..CL-8 exactly. Filters ON for hash-object (no
    --no-filters). Keep the reason closed set, the exit codes and INV-5. Deletes are
    single-file (os.remove after the lstat, parent-link and containment checks). No rmtree,
    no git clean, no git rm, no directory delete. Follow the order in CL-5, with step 6's
    per-file re-hash immediately before each delete. Update the module docstring's rule list.
  - GREEN, gate: one PROJECT_MARKERS constant. One scan function (start path -> name,
    complete) with the existence check and the listing both inside its error handling;
    only "not found" or "not a directory" skips an ancestor. detect_project_name returns the
    resolved scan's name, unchanged in value. resolve_target adds the CG-1 step (resolved
    scan clean and complete, AND written-path scan of os.path.abspath clean and complete)
    after the pinned step and before the contract scan. No stderr on that allow. Add one line
    to the module docstring. Do not touch the fallback-mode code or the banner.
  - Shipped wording, each saying the gate covers non-trivial files inside a project and does
    not gate a file outside every project (no .git, CLAUDE.md, package.json, pyproject.toml
    or *.sln on its path): README.md line 136; skills/design-first/SKILL.md line 18;
    .claude/hooks/hooks.json line 35 (keep the JSON valid and the string-array shape).
  - Version 0.9.7 -> 0.9.8 in all five declarations.
  - Run green: test_cleanup_delivered.py (whole), test_concept_gate_outside_project.py,
    .claude/hooks/tests/test_contract_index.py, test_worktree_path_guards.py,
    test_main_checkout_guard.py, test_shell_write_targets.py,
    .claude/scripts/tests/test_plugin_manifests.py, test_check_version_bump.py. Do NOT
    include test_changed_file_check.py (red by design until block 17 of
    2026-10-12-dedupe-claude-config). Report the RED list and the GREEN run with exit codes.
  - Do not invent new data shapes; the contract is authoritative. Do not edit the 2026-10-15
    contract or any registry.
PRIOR_FINDINGS:
  contract_path: .claude/concepts/2026-10-17-worktree-removal-untracked-identical.md
  contract_status: approved
```

### 2. Scope note on review

There is no separate review sub-task. The ordinary `/ship` review applies. The reviewer checks:
- CL-1 to CL-8 against the call log, especially filters on, the per-file re-hash before each delete, the parent-link check and no force.
- CG-1 to CG-6, especially the two scans, the existence check inside the error handling, and the sandbox marker.
- The RED list was recorded before GREEN.

After merge, the reviewer extends the **Delivery cleanup** entry in `MECHANISMS.md` (Landed untracked files and the CL-5 order) and promotes the two vocabulary terms with the `outside-repository` distinction.

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
